"""TCP client for the clo3d-mcp bridge running inside CLO (newline-delimited JSON)."""
from __future__ import annotations

import json
import os
import socket
import uuid


class CloBridgeError(RuntimeError):
    def __init__(self, message: str, traceback_text: str = ""):
        super().__init__(message)
        self.traceback_text = traceback_text


class CloNotConnected(RuntimeError):
    pass


class CloClient:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 600.0):
        self.host = host or os.environ.get("CLO_MCP_HOST", "127.0.0.1")
        if self.host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Only local loopback connections are supported")
        self.port = int(port or os.environ.get("CLO_MCP_PORT", "5077"))
        self.timeout = timeout

    def call(self, cmd: str, params: dict | None = None, timeout: float | None = None):
        request = {"id": uuid.uuid4().hex, "cmd": cmd, "params": params or {}}
        payload = (json.dumps(request) + "\n").encode("utf-8")
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5.0)
        except OSError as exc:
            raise CloNotConnected(
                f"Cannot reach the CLO bridge on {self.host}:{self.port} ({exc}). "
                "Start it inside CLO (Edit > Python Script > run clo_bridge.py) or use the clo_status tool."
            ) from exc
        with sock:
            sock.settimeout(self.timeout if timeout is None else timeout)
            sock.sendall(payload)
            chunks = []
            size = 0
            while True:
                try:
                    chunk = sock.recv(1 << 20)
                except OSError as exc:
                    raise CloBridgeError("Bridge response interrupted; operation outcome unknown. Inspect CLO before retrying.") from exc
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > 64 * 1024 * 1024:
                    raise CloBridgeError("Bridge response exceeds 64 MiB; request smaller pages")
                if b"\n" in chunk:
                    break
        raw = b"".join(chunks)
        if not raw:
            raise CloBridgeError("empty response from CLO bridge (bridge stopped mid-call?)")
        if not raw.endswith(b"\n"):
            raise CloBridgeError("Truncated bridge response; operation outcome unknown. Inspect CLO before retrying.")
        try:
            response = json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise CloBridgeError("Invalid bridge JSON response; operation outcome unknown") from exc
        if not isinstance(response, dict) or response.get("id") != request["id"]:
            raise CloBridgeError("Bridge response ID mismatch; operation outcome unknown")
        if not response.get("ok"):
            raise CloBridgeError(response.get("error", "unknown error"), response.get("traceback", ""))
        return response.get("result")

    def exec(self, code: str, timeout: float | None = None):
        """Run Python inside CLO. Returns {'value': ..., 'stdout': ...}."""
        return self.call("exec", {"code": code}, timeout=timeout)

    def ping(self) -> dict:
        return self.call("ping", timeout=10)


if __name__ == "__main__":
    import sys
    c = CloClient()
    if len(sys.argv) > 1:
        print(json.dumps(c.exec(" ".join(sys.argv[1:])), indent=1))
    else:
        print(json.dumps(c.ping(), indent=1))
