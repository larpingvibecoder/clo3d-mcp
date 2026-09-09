"""clo3d-mcp bridge -- runs INSIDE CLO (Edit > Python Script, or `CLO -python <this file>`).

Design (verified on CLO 2026.1 / embedded Python 3.11):
  * CLO runs scripts on its main (UI) thread, and background Python threads are
    frozen as soon as the script returns (the GIL is never released while idle),
    so a listener thread cannot survive on its own.
  * QCoreApplication::processEvents is reachable through ctypes, so this script
    keeps running on the main thread as a *serve loop* that pumps Qt events
    between socket polls. The CLO UI stays interactive while the bridge waits.
  * Each request runs synchronously on the main thread (the only place the CLO
    API is guaranteed safe). CLO is busy only while a command executes, exactly
    like clicking the same action by hand.

Wire protocol: newline-delimited JSON over TCP 127.0.0.1:5077 (see clo_client.py).
  request : {"id": str, "cmd": str, "params": {...}}
  response: {"id": str, "ok": true, "result": ...} | {"id": str, "ok": false, "error": str, "traceback": str}
"""
import builtins
import ctypes
import io
import json
import os
import select
import socket
import sys
import time
import traceback

BRIDGE_VERSION = "0.1.0a1"
HOST = os.environ.get("CLO_MCP_HOST", "127.0.0.1")
if HOST not in {"127.0.0.1", "localhost"}:
    raise ValueError("CLO MCP only supports a local loopback host (127.0.0.1 or localhost)")
PORT = int(os.environ.get("CLO_MCP_PORT", "5077"))
STATE_DIR = os.path.abspath(os.path.expanduser(os.environ.get("CLO_MCP_STATE", "~/.clo3d-mcp")))
STATUS_FILE = os.path.join(STATE_DIR, "bridge_status.json")
STOP_FILE = os.path.join(STATE_DIR, "bridge.stop")
LOG_FILE = os.path.join(STATE_DIR, "bridge.log")
BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None

os.makedirs(STATE_DIR, exist_ok=True)


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print("[clo3d-mcp] " + msg)
    except Exception:
        pass


# --------------------------------------------------------------------------- Qt event pump
_process_events = None


def _load_process_events():
    global _process_events
    lib = ctypes.CDLL(None)
    for sym in ("_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEE",
                "_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEEi"):
        try:
            fn = getattr(lib, sym)
        except AttributeError:
            continue
        if sym.endswith("Ei"):
            fn.argtypes = [ctypes.c_int, ctypes.c_int]
            fn.restype = None
            _process_events = lambda: fn(0, 5)
        else:
            fn.argtypes = [ctypes.c_int]
            fn.restype = None
            _process_events = lambda: fn(0)   # QEventLoop::AllEvents
        return True
    return False


def pump():
    if _process_events is not None:
        _process_events()


# --------------------------------------------------------------------------- API namespace
def _api_namespace():
    ns = {"__name__": "clo3d_mcp_exec", "__builtins__": builtins}
    for mod in ("import_api", "export_api", "fabric_api", "pattern_api", "utility_api", "rest_api", "ApiTypes"):
        try:
            ns[mod] = __import__(mod)
        except Exception as exc:
            log("warning: cannot import %s: %r" % (mod, exc))
    import math
    ns.update({"json": json, "os": os, "sys": sys, "math": math, "time": time, "pump": pump, "log": log})
    return ns


NS = _api_namespace()


def _jsonable(value):
    """Best-effort conversion of CLO API return values into JSON-serialisable data."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        pass
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dict__") and value.__dict__:
        return {k: _jsonable(v) for k, v in vars(value).items() if not k.startswith("_")}
    attrs = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(value, name)
        except Exception:
            continue
        if callable(attr):
            continue
        attrs[name] = _jsonable(attr)
    return attrs if attrs else str(value)


# --------------------------------------------------------------------------- command handlers
def cmd_ping(params):
    return {"bridge": BRIDGE_VERSION, "pid": os.getpid(), "python": sys.version.split()[0],
            "clo": _clo_version(), "port": PORT}


def _clo_version():
    try:
        u = NS["utility_api"]
        return "%d.%d.%d" % (u.GetMajorVersion(), u.GetMinorVersion(), u.GetPatchVersion())
    except Exception:
        return "unknown"


def cmd_exec(params):
    """Execute Python inside CLO. `code` may set `result`; a single expression returns its value.
    stdout is captured and returned as `stdout`."""
    code = params.get("code", "")
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    ns = NS if params.get("persistent", True) else dict(NS)
    ns.pop("result", None)
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = buf
    sys.stderr = buf
    value = None
    try:
        try:
            compiled = compile(code, "<clo3d-mcp>", "eval")
        except SyntaxError:
            compiled = compile(code, "<clo3d-mcp>", "exec")
            exec(compiled, ns)
            value = ns.get("result", None)
        else:
            value = eval(compiled, ns)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return {"value": _jsonable(value), "stdout": buf.getvalue()}


def cmd_stop(params):
    raise _Stop()


def cmd_reload_ops(params):
    """Re-import clo_ops.py (hot reload during development)."""
    _load_ops(force=True)
    return {"ops": sorted(k for k in HANDLERS if k not in BASE_HANDLERS)}


class _Stop(Exception):
    pass


BASE_HANDLERS = {"ping": cmd_ping, "exec": cmd_exec, "stop": cmd_stop, "reload_ops": cmd_reload_ops}
HANDLERS = dict(BASE_HANDLERS)


def _load_ops(force=False):
    """clo_ops.py (same folder) registers high-level garment operations into HANDLERS."""
    if BRIDGE_DIR is None:
        return
    if BRIDGE_DIR not in sys.path:
        sys.path.insert(0, BRIDGE_DIR)
    try:
        import importlib
        if "clo_ops" in sys.modules and force:
            ops = importlib.reload(sys.modules["clo_ops"])
        else:
            ops = importlib.import_module("clo_ops")
        for k in list(HANDLERS):
            if k not in BASE_HANDLERS:
                del HANDLERS[k]
        HANDLERS.update(ops.register(NS, log))
        log("loaded clo_ops: %d commands" % (len(HANDLERS) - len(BASE_HANDLERS)))
    except Exception:
        log("clo_ops load failed:\n" + traceback.format_exc())


def dispatch(request):
    if not isinstance(request, dict):
        return {"id": None, "ok": False, "error": "request must be a JSON object"}
    rid = request.get("id")
    cmd = request.get("cmd")
    params = request.get("params", {})
    if params is None:
        params = {}
    if not isinstance(cmd, str) or not isinstance(params, dict):
        return {"id": rid, "ok": False, "error": "cmd must be a string and params an object"}
    handler = HANDLERS.get(cmd)
    if handler is None:
        return {"id": rid, "ok": False, "error": "unknown command: %r (known: %s)" % (cmd, sorted(HANDLERS))}
    t0 = time.time()
    try:
        result = handler(params)
        return {"id": rid, "ok": True, "result": _jsonable(result), "ms": int((time.time() - t0) * 1000)}
    except _Stop:
        raise
    except Exception as exc:
        return {"id": rid, "ok": False, "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(), "ms": int((time.time() - t0) * 1000)}


# --------------------------------------------------------------------------- status file
def write_status(state):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"state": state, "pid": os.getpid(), "port": PORT, "host": HOST,
                       "version": BRIDGE_VERSION, "clo": _clo_version(), "time": time.time()}, f)
    except Exception:
        pass


# --------------------------------------------------------------------------- serve loop
def serve():
    if getattr(builtins, "_CLO3D_MCP_ACTIVE", False):
        log("bridge already active in this CLO session; not starting a second loop")
        return
    if not _load_process_events():
        log("QCoreApplication::processEvents not found; refusing to start to avoid freezing CLO")
        write_status("unsupported_qt")
        return
    _load_ops()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((HOST, PORT))
    except OSError as exc:
        log("cannot bind %s:%d (%s) -- another bridge running?" % (HOST, PORT, exc))
        srv.close()
        return
    srv.listen(16)
    srv.setblocking(False)
    builtins._CLO3D_MCP_ACTIVE = True
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    write_status("running")
    log("bridge %s listening on %s:%d (CLO %s)" % (BRIDGE_VERSION, HOST, PORT, _clo_version()))
    clients = {}          # sock -> bytearray buffer
    last_status = time.time()
    stopping = False
    try:
        while not stopping:
            try:
                readable, _, _ = select.select([srv] + list(clients), [], [], 0.02)
            except (OSError, ValueError):
                readable = []
            for s in readable:
                if s is srv:
                    try:
                        conn, _ = srv.accept()
                        conn.setblocking(False)
                        clients[conn] = bytearray()
                    except OSError:
                        pass
                    continue
                buf = clients[s]
                try:
                    chunk = s.recv(1 << 20)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError:
                    chunk = b""
                if not chunk:
                    clients.pop(s, None)
                    try:
                        s.close()
                    except OSError:
                        pass
                    continue
                buf.extend(chunk)
                if len(buf) > 8 * 1024 * 1024:
                    clients.pop(s, None)
                    s.close()
                    continue
                while b"\n" in buf:
                    line, _, rest = bytes(buf).partition(b"\n")
                    buf[:] = rest
                    if not line.strip():
                        continue
                    try:
                        request = json.loads(line.decode("utf-8"))
                    except Exception as exc:
                        response = {"ok": False, "error": "bad JSON: %s" % exc}
                    else:
                        try:
                            response = dispatch(request)
                        except _Stop:
                            response = {"id": request.get("id"), "ok": True, "result": {"stopping": True}}
                            stopping = True
                    _send(s, response)
            pump()
            now = time.time()
            if now - last_status > 3:
                last_status = now
                write_status("running")
                if os.path.exists(STOP_FILE):
                    stopping = True
    finally:
        for s in clients:
            try:
                s.close()
            except OSError:
                pass
        srv.close()
        builtins._CLO3D_MCP_ACTIVE = False
        write_status("stopped")
        if os.path.exists(STOP_FILE):
            try:
                os.remove(STOP_FILE)
            except OSError:
                pass
        log("bridge stopped")


def _send(sock, response):
    data = (json.dumps(response, default=str) + "\n").encode("utf-8")
    sock.settimeout(5.0)
    try:
        sock.sendall(data)
    except OSError:
        pass
    finally:
        try:
            sock.setblocking(False)
        except OSError:
            pass


if __name__ == "__main__":
    serve()
