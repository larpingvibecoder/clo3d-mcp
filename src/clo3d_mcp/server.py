"""clo3d-mcp: MCP server that drives CLO3D for garment creation and modification.

Architecture:  MCP client  --stdio-->  this server  --TCP JSON-lines-->  clo_bridge.py inside CLO  -->  CLO API
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image
from mcp_types import ContentBlock, TextContent

from . import drafting, __version__
from .avatar_measure import measure_avatar
from .client import CloBridgeError, CloClient, CloNotConnected

PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parents[1]
BRIDGE_DIR = PKG_DIR / "_bridge"
if not BRIDGE_DIR.is_dir():
    BRIDGE_DIR = REPO_DIR / "bridge"
BRIDGE_FILE = BRIDGE_DIR / "clo_bridge.py"
STATE_DIR = Path(os.environ.get("CLO_MCP_STATE", Path.home() / ".clo3d-mcp"))
SNAP_DIR = STATE_DIR / "snapshots"
CHECKPOINT_DIR = STATE_DIR / "checkpoints"
MEASURE_DIR = STATE_DIR / "measurements"
CALIB_DIR = STATE_DIR / "calibration"
for d in (SNAP_DIR, CHECKPOINT_DIR, MEASURE_DIR, CALIB_DIR):
    d.mkdir(parents=True, exist_ok=True)
DEFAULT_ASSETS = Path(os.environ.get("CLO_MCP_ASSETS", Path.home() / "Documents" / "clo" / "CLO Assets"))
CLO_APP = os.environ.get("CLO_APP_PATH", "/Applications/CLO.app")

INSTRUCTIONS = """Tools for driving CLO3D (garment CAD + cloth simulation) through a Python bridge running inside CLO.
Start with clo_status. If the bridge is down, follow its instructions (one click in CLO: Plugins > start_bridge).
Typical flows:
  * One-prompt garment: garment_build(spec) drafts pattern pieces from the avatar's measurements, places them on the
    avatar, sews, applies fabric/colour, simulates and returns snapshots. Use garment_plan_preview first if unsure.
  * Iterate: garment_rebuild(changes) re-drafts with modified spec fields (e.g. {"length": "midi", "neckline": "v"}).
  * Customise an existing garment: scene_open (.zprj/.zpac), pattern_list(detail) to see pieces/lines, then
    pattern_edit_points / pattern_ops / fabric_* / sew, simulate, snapshot.
  * Full coverage: clo_api_catalog discovers live APIs; clo_api_describe provides signatures and types;
    clo_api_call invokes them. For UI-only features use clo_control_guide and desktop tools.
    Observe UI before and after each action; never blindly retry timed-out mutations.
  * Live reference: clo_api_search to find CLO API functions, then clo_run_python (modules import_api, export_api,
    fabric_api, pattern_api, utility_api, ApiTypes are pre-imported; set `result` to return data).
Units are millimetres, Y up. Always look at a snapshot after simulating to judge the result."""

server = MCPServer("clo3d", instructions=INSTRUCTIONS, version=__version__)
_client = CloClient()
_state: dict[str, Any] = {"last_spec": None, "last_plan": None}


# ----------------------------------------------------------------------------- helpers

def _text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, indent=1, default=str)


def _t(s: str) -> TextContent:
    return TextContent(type="text", text=s)


async def _call(cmd: str, params: dict | None = None, timeout: float | None = None):
    def run():
        return _client.call(cmd, params or {}, timeout=timeout)
    return await anyio.to_thread.run_sync(run)


def _bridge_status() -> dict:
    status = {"bridge": "down", "clo_running": False}
    try:
        out = subprocess.run(["pgrep", "-f", "CLO_Standalone"], capture_output=True, text=True, timeout=5)
        status["clo_running"] = bool(out.stdout.strip())
    except Exception:
        pass
    try:
        status.update(_client.ping())
        status["bridge"] = "up"
    except Exception as exc:
        status["error"] = str(exc)
    sf = STATE_DIR / "bridge_status.json"
    if sf.exists():
        try:
            status["status_file"] = json.loads(sf.read_text())
        except Exception:
            pass
    return status


START_HELP = (
    "The CLO bridge is not reachable. To start it (CLO must be open):\n"
    "  1. In CLO click the menu  Plugins > start_bridge   (registered one-click launcher), or\n"
    "  2. Edit > Python Script, paste this line and press Run ONCE (never press Run again while it serves):\n"
    f"     import runpy; runpy.run_path({str(BRIDGE_FILE)!r}, run_name='__main__')\n"
    "  3. If CLO is not open, clo_launch() opens it; then use the menu item.\n"
    "The bridge keeps CLO's UI responsive; stop it with clo_stop_bridge when you want to run other scripts."
)


def _assets_folder(info: dict | None = None) -> Path:
    if info and info.get("asset_folder"):
        return Path(info["asset_folder"])
    return DEFAULT_ASSETS


def _find_fabric(stem_or_path: str, assets: Path) -> str | None:
    if os.path.isabs(stem_or_path) and os.path.exists(stem_or_path):
        return stem_or_path
    fab_dir = assets / "Fabric"
    cand = fab_dir / f"{stem_or_path}.zfab"
    if cand.exists():
        return str(cand)
    low = stem_or_path.lower()
    for p in glob.glob(str(fab_dir / "**" / "*.zfab"), recursive=True):
        if low in os.path.basename(p).lower():
            return p
    return None


AVATAR_ALIASES = {
    "mia": "Female/FV2.1_Mia.avt", "female": "Female/FV2.1_Mia.avt", "woman": "Female/FV2.1_Mia.avt",
    "luka": "Male/MV2.1_Luka.avt", "male": "Male/MV2.1_Luka.avt", "man": "Male/MV2.1_Luka.avt",
    "female mannequin": "Mannequin/FV2.1_Mannequin.avt", "male mannequin": "Mannequin/MV2.1_Mannequin.avt",
    "melody": "Kid/KV1.1G_Melody_(7-20).avt", "girl": "Kid/KV1.1G_Melody_(7-20).avt",
    "oliver": "Kid/KV1.1B_Oliver_(7-20).avt", "boy": "Kid/KV1.1B_Oliver_(7-20).avt",
}


def _find_avatar(name_or_path: str | None, assets: Path) -> str | None:
    if not name_or_path:
        name_or_path = "mia"
    if os.path.isabs(name_or_path) and os.path.exists(name_or_path):
        return name_or_path
    key = name_or_path.lower().strip()
    if key in AVATAR_ALIASES:
        p = assets / "Avatar" / AVATAR_ALIASES[key]
        if p.exists():
            return str(p)
    for p in glob.glob(str(assets / "Avatar" / "**" / "*.avt"), recursive=True):
        if key in os.path.basename(p).lower():
            return p
    return None


async def _get_body(avatar_name: str, force_refresh: bool = False) -> tuple[drafting.Body, str]:
    """Body measurements for the avatar currently in the scene: cache -> CLO API -> OBJ analysis -> defaults."""
    cache = MEASURE_DIR / f"{avatar_name}.json"
    if cache.exists() and not force_refresh:
        data = json.loads(cache.read_text())
        if data.get("measurements"):
            return drafting.Body.from_clo(data["measurements"]), f"cached CLO measurements ({cache.name})"
    info = await _call("avatar_info")
    meas = info.get("measurements") or {}
    if meas:
        cache.write_text(json.dumps({"avatar": avatar_name, "measurements": meas, "time": time.time()}, indent=1))
        return drafting.Body.from_clo(meas), "CLO avatar measurements"
    # OBJ fallback
    try:
        obj_path = str(STATE_DIR / f"{avatar_name}_avatar.obj")
        await _call("export_file", {"path": obj_path, "garment": False, "avatar": True}, timeout=300)
        m = await anyio.to_thread.run_sync(lambda: measure_avatar(obj_path))
        return drafting.Body.from_obj_measure(m), ("approximate measurements from the avatar mesh (open Avatar > Avatar Editor once "
                                                   "in CLO and rerun avatar_measurements to get CLO's exact values)")
    except Exception as exc:
        return drafting.Body(), f"default female measurements (measurement failed: {exc})"


async def _calibration(avatar_name: str, names: list[str]) -> dict:
    """World centre [y, x, z] of a test piece placed at each arrangement point (cached per avatar)."""
    cache = CALIB_DIR / f"{avatar_name}.json"
    data = {"avatar": avatar_name, "points": {}}
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
        except Exception:
            pass
    missing = [n for n in names if n not in data.get("points", {})]
    for n in missing:
        try:
            r = await _call("calibrate_arrangement", {"names": [n]}, timeout=120)
            data.setdefault("points", {})[n] = r["points"].get(n)
        except Exception:
            data.setdefault("points", {})[n] = None
    cache.write_text(json.dumps(data, indent=1))
    return data["points"]


FRONT_CANDIDATES = ["Body_Front_Center_1", "Body_Front_Center_2", "Body_Front_Center_3", "Body_Front_Waist", "Body_Front_Center_5", "Leg_Skirt_Front"]
BACK_CANDIDATES = ["Body_Back_Center_1", "Body_Back_Center_2", "Body_Back_Center_3", "Body_Back_Waist", "Body_Back_Center_5", "Leg_Skirt_Back"]


def _choose_points(plan: drafting.Plan, calib: dict) -> list[str]:
    notes = []
    for p in plan.pieces:
        if p.role in ("bodice_front", "skirt_front", "bodice_back", "skirt_back"):
            cands = FRONT_CANDIDATES if p.role.endswith("front") else BACK_CANDIDATES
            target = p.centre_height()
            best = None
            for n in cands:
                c = calib.get(n)
                if not c:
                    continue
                y = c[1] if isinstance(c, list) else c.get("y", 0)
                penalty = abs(y - target) + (60.0 if y < target - 15 else 0.0)   # prefer landing slightly high
                if best is None or penalty < best[0]:
                    best = (penalty, n, y)
            if best:
                p.arrangement = best[1]
                notes.append(f"{p.name}: centre {target:.0f} -> {best[1]} ({best[2]:.0f})")
    return notes


def _snapshot_blocks(res: dict, caption: str = "") -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    if caption:
        blocks.append(_t(caption))
    for img in res.get("images", []):
        path = img.get("path")
        if path and os.path.exists(path):
            blocks.append(_t(f"[{img.get('view')} view] {path}"))
            blocks.append(Image(path=path).to_image_content())
        else:
            blocks.append(_t(f"snapshot failed for view {img.get('view')}: {path!r}"))
    return blocks


# ----------------------------------------------------------------------------- status / raw access

@server.tool()
async def clo_status() -> dict:
    """Check whether CLO is running and the in-CLO bridge is reachable. Returns instructions when it is not."""
    st = await anyio.to_thread.run_sync(_bridge_status)
    if st["bridge"] != "up":
        st["how_to_start"] = START_HELP
    return st


@server.tool()
async def clo_launch(with_bridge: bool = True) -> str:
    """Launch CLO (macOS). Passing -python clo_bridge.py is attempted, but CLO 2026.1 did not run it at startup in testing,
    so after CLO is up start the bridge with the menu item Plugins > start_bridge (or ask the user to click it)."""
    st = _bridge_status()
    if st.get("clo_running"):
        return "CLO is already running. " + ("Bridge is up." if st["bridge"] == "up" else START_HELP)
    args = ["open", "-a", CLO_APP]
    if with_bridge:
        args += ["--args", "-python", str(BRIDGE_FILE)]
    subprocess.Popen(args)
    return ("CLO is starting. Wait ~60 s (login, splash, possible notice dialog), then start the bridge with the CLO menu "
            "Plugins > start_bridge and call clo_status.")


@server.tool()
async def clo_stop_bridge() -> str:
    """Stop the bridge loop inside CLO (frees the Python editor; CLO keeps running)."""
    try:
        await _call("stop", timeout=10)
        return "bridge stopped"
    except Exception as exc:
        (STATE_DIR / "bridge.stop").touch()
        return f"stop requested via stop-file ({exc})"


@server.tool()
async def clo_run_python(code: str, timeout_seconds: float = 600) -> dict:
    """Run Python inside CLO with the CLO API modules pre-imported (import_api, export_api, fabric_api, pattern_api,
    utility_api, rest_api, ApiTypes). A single expression returns its value; otherwise assign to `result`.
    stdout is captured. Coordinates: mm, Y up. Example: pattern_api.GetPatternCount()"""
    return await _call("exec", {"code": code}, timeout=timeout_seconds)


@server.tool()
async def clo_api_search(query: str, limit: int = 40) -> str:
    """Search names and docstrings in the running CLO API. Requires the bridge. Use clo_api_catalog for pagination."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    from .capabilities import runtime_call
    page = await runtime_call(_call, BRIDGE_DIR, 'catalog', query=query, limit=limit)
    return _text(page)


@server.tool()
async def clo_api_doc(function_name: str) -> str:
    """Read live documentation for a CLO function. Prefer a qualified name such as pattern_api.GetPatternCount."""
    from .capabilities import runtime_call
    if '.' in function_name:
        return _text(await runtime_call(_call, BRIDGE_DIR, 'describe', name=function_name))
    page = await runtime_call(_call, BRIDGE_DIR, 'catalog', query=function_name, limit=500)
    matches = [e['name'] for e in page['entries'] if e['name'].split('.')[-1] == function_name]
    if len(matches) != 1:
        return _text({'matches': matches, 'help': 'Use a qualified name from clo_api_catalog.'})
    return _text(await runtime_call(_call, BRIDGE_DIR, 'describe', name=matches[0]))


# ----------------------------------------------------------------------------- scene

@server.tool()
async def scene_info() -> dict:
    """Current CLO scene: project, avatars, pattern pieces (with arrangement point and fabric), fabrics, colorways, seams."""
    return await _call("scene_info")


@server.tool()
async def scene_clear(keep_avatar: bool = True) -> dict:
    """Delete all pattern pieces (keep_avatar=True) or start a fresh project (keep_avatar=False)."""
    if keep_avatar:
        return await _call("clear_garment")
    return await _call("new_project")


@server.tool()
async def scene_open(path: str, mode: str = "replace") -> dict:
    """Open a file in CLO: .zprj (project), .zpac (garment), .avt (avatar), .dxf (patterns), pattern .json, .obj/.fbx.
    mode 'replace' or 'append'."""
    if not os.path.exists(path):
        raise ValueError(f"file not found: {path}")
    return await _call("open_file", {"path": path, "mode": mode}, timeout=600)


@server.tool()
async def scene_save(path: str, thumbnail: bool = True) -> dict:
    """Save the project (.zprj) or garment (.zpac) to a path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return await _call("save_project", {"path": path, "thumbnail": thumbnail}, timeout=600)


@server.tool()
async def scene_export(path: str, include_avatar: bool = False, colorways: bool = False) -> dict:
    """Export the garment: .obj, .fbx, .glb, .gltf, .dxf (patterns), .json (CLO pattern JSON), .zprj, .zpac."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return await _call("export_file", {"path": path, "avatar": include_avatar, "colorways": colorways}, timeout=900)


@server.tool()
async def snapshot(views: list[str] | None = None, label: str = "") -> list[ContentBlock]:
    """Capture the 3D window from one or more views and return the images. views: front, back, left, right, 3/4-right,
    3/4-left, top. Default: front and 3/4-right."""
    views = views or ["front", "3/4-right"]
    res = await _call("snapshot", {"views": views, "folder": str(SNAP_DIR), "prefix": (label or "snap").replace(" ", "_")}, timeout=300)
    return _snapshot_blocks(res)


@server.tool()
async def snapshot_2d() -> list[ContentBlock]:
    """Capture the 2D pattern window (pattern pieces layout)."""
    res = await _call("snapshot_2d", {"folder": str(SNAP_DIR)}, timeout=300)
    path = res.get("path")
    if path and os.path.exists(path):
        return [_t(f"2D snapshot: {path}"), Image(path=path).to_image_content()]
    return [_t(f"2D snapshot failed: {res}")]


# ----------------------------------------------------------------------------- avatar

@server.tool()
async def avatar_list() -> dict:
    """Avatars in the scene and the .avt files available in the CLO asset library."""
    info = await _call("scene_info")
    assets = _assets_folder(info)
    files = sorted(glob.glob(str(assets / "Avatar" / "**" / "*.avt"), recursive=True))
    return {"in_scene": info.get("avatars", []), "library": files, "aliases": sorted(AVATAR_ALIASES)}


@server.tool()
async def avatar_load(name_or_path: str = "mia", replace: bool = True) -> dict:
    """Load an avatar by alias (mia, luka, female mannequin, male mannequin, melody, oliver), file name or path."""
    info = await _call("scene_info")
    path = _find_avatar(name_or_path, _assets_folder(info))
    if not path:
        raise ValueError(f"no avatar matching {name_or_path!r}")
    return await _call("load_avatar", {"path": path, "replace": replace}, timeout=600)


@server.tool()
async def avatar_measurements(refresh: bool = False) -> dict:
    """Body measurements (mm) of the avatar in the scene, used for drafting. Source: CLO's measurement API (needs the
    Avatar Editor opened once per session in CLO), a cache, or an approximation from the avatar mesh."""
    info = await _call("scene_info")
    if not info.get("avatars"):
        raise ValueError("no avatar in the scene; call avatar_load first")
    body, source = await _get_body(info["avatars"][0], force_refresh=refresh)
    return {"avatar": info["avatars"][0], "source": source, "body": body.__dict__}


@server.tool()
async def arrangement_points() -> dict:
    """List the avatar's arrangement points (names used to place pattern pieces on the body)."""
    r = await _call("arrangement_points")
    return {"count": len(r["points"]), "names": [p["ArrangementName"] for p in r["points"]]}


# ----------------------------------------------------------------------------- patterns

@server.tool()
async def pattern_list(detail: bool = False) -> dict:
    """List pattern pieces (index, name, arrangement, fabric, bbox). detail=True adds each outline line with its
    length/location (line indices are what sew() uses) and the seam groups per piece."""
    return await _call("pattern_list", {"detail": detail})


@server.tool()
async def pattern_info(pattern: str) -> dict:
    """Full information about one piece (by name or index): lines, points (2D mm), arrangement, fabric, seams."""
    return await _call("pattern_info", {"pattern": pattern})


@server.tool()
async def pattern_create(points: list[list[float]], name: str = "", arrangement: str = "") -> dict:
    """Create a pattern piece from outline points [[x, y, type], ...] in mm (Y up). type 0 = corner (default),
    2 = spline curve point, 3 = bezier control point. Lines are numbered by corner order (line i joins corner i to
    i+1). Optionally place it on an arrangement point (see arrangement_points)."""
    return await _call("create_pattern", {"points": points, "name": name, "arrangement": arrangement})


@server.tool()
async def pattern_delete(patterns: list[str]) -> dict:
    """Delete pieces by name or index."""
    return await _call("delete_patterns", {"patterns": patterns})


@server.tool()
async def pattern_set_arrangement(pattern: str, point: str) -> dict:
    """Place a piece on an avatar arrangement point (e.g. Body_Front_Center_3, Leg_Skirt_Back, Arm_Outside_2_L)."""
    return await _call("set_arrangement", {"pattern": pattern, "point": point})


@server.tool()
async def pattern_edit_points(pattern: str, moves: list[dict]) -> dict:
    """Move outline points of a piece. moves: [{"point": i, "x": .., "y": ..}] absolute or [{"point": i, "dx": .., "dy": ..}]
    relative (mm, 2D pattern space). Use pattern_info to see point indices/positions. Only corner points are indexed;
    curve (spline) points on an edge stay where they are, so moving corners of a curved hem distorts it. For built
    garments prefer garment_rebuild({"length": ...}); use this for straight-edged pieces or small tweaks, then simulate."""
    return await _call("move_points", {"pattern": pattern, "moves": moves})


@server.tool()
async def pattern_ops(pattern: str, op: str, args: dict | None = None) -> dict:
    """Piece operations. op: rename{name}, move_2d{x,y|dx,dy}, flip{horizontal,each}, copy{dx,dy}, symmetry{with_sewing},
    unfold{line,half_symmetry}, layer{layer}, particle_distance{mm}, freeze{on}, hide{on}, strengthen{on},
    elastic{line,on,total_length,strength}, shirring{line,on}, delete_line{line}, delete_point{point}."""
    return await _call("pattern_ops", {"pattern": pattern, "op": op, "args": args or {}})


# ----------------------------------------------------------------------------- sewing

@server.tool()
async def sew(pattern_a: str, line_a: int, pattern_b: str, line_b: int, dir_a: bool = True, dir_b: bool = True) -> dict:
    """Sew line_a of pattern_a to line_b of pattern_b (segment sewing). Directions follow each line's point order;
    when the two lines run in opposite physical directions set dir_b=False (e.g. front right side <-> back left side
    with clockwise outlines). Check the result with simulate + snapshot; there is no API to remove a seam, so save a
    checkpoint first."""
    return await _call("sew", {"pattern_a": pattern_a, "line_a": line_a, "pattern_b": pattern_b, "line_b": line_b, "dir_a": dir_a, "dir_b": dir_b})


@server.tool()
async def seams_list() -> dict:
    """List sewing groups and the pieces involved."""
    return await _call("seams")


# ----------------------------------------------------------------------------- fabrics

@server.tool()
async def fabric_library(filter: str = "") -> dict:
    """List .zfab fabrics available in the CLO asset library (optionally filtered by substring)."""
    info = await _call("scene_info")
    assets = _assets_folder(info)
    files = sorted(glob.glob(str(assets / "Fabric" / "**" / "*.zfab"), recursive=True))
    names = [os.path.basename(f) for f in files]
    if filter:
        names = [n for n in names if filter.lower() in n.lower()]
    return {"folder": str(assets / "Fabric"), "fabrics": names, "keywords": sorted({k for keys, _ in drafting.FABRIC_KEYWORDS for k in keys})}


@server.tool()
async def fabric_list() -> dict:
    """Fabrics currently in the project's object browser."""
    return await _call("fabric_list")


@server.tool()
async def fabric_apply(fabric: str, color: str = "", patterns: list[str] | None = None, texture_image: str = "") -> dict:
    """Add a fabric (keyword like 'satin', 'chiffon', 'denim', 'jersey'..., a library file name, or a .zfab path) and
    assign it to the given pieces (default: all). Optional colour ('#hex' or a colour name) and base texture image."""
    info = await _call("scene_info")
    assets = _assets_folder(info)
    stem, matched = drafting.fabric_file_for(fabric)
    path = _find_fabric(stem, assets) or _find_fabric(fabric, assets)
    if not path:
        raise ValueError(f"no fabric file for {fabric!r} (matched {matched}); see fabric_library")
    added = await _call("add_fabric", {"path": path})
    res = {"fabric": added, "matched": matched, "file": path}
    res["assigned"] = await _call("assign_fabric", {"fabric_index": added["index"], "patterns": patterns})
    if color:
        rgb = drafting.parse_color(color)
        res["color"] = await _call("set_fabric_color", {"fabric_index": added["index"], "rgb": rgb})
        res["rgb"] = rgb
    if texture_image:
        res["texture"] = await _call("set_fabric_texture", {"fabric_index": added["index"], "path": texture_image})
    return res


@server.tool()
async def fabric_set_color(fabric_index: int, color: str) -> dict:
    """Set the base colour of a fabric already in the project ('#hex' or colour name)."""
    rgb = drafting.parse_color(color)
    r = await _call("set_fabric_color", {"fabric_index": fabric_index, "rgb": rgb})
    return {"rgb": rgb, "result": r}


@server.tool()
async def fabric_set_texture(fabric_index: int, image_path: str, map: str = "base") -> dict:
    """Apply an image as a fabric's base colour texture (or normal/roughness/opacity map)."""
    return await _call("set_fabric_texture", {"fabric_index": fabric_index, "path": image_path, "map": map})


# ----------------------------------------------------------------------------- simulation

@server.tool()
async def simulate(steps: int = 100, particle_distance: float | None = None, quality: int | None = None) -> dict:
    """Run the cloth simulation for N steps (about 30 steps per simulated second). quality: 0 normal, 1 stable,
    2 accurate, 3 GPU-fast. particle_distance in mm (smaller = finer, slower; 20 default, 10 for final quality)."""
    return await _call("simulate", {"steps": steps, "particle_distance": particle_distance, "quality": quality}, timeout=1800)


@server.tool()
async def simulation_reset() -> dict:
    """Reset the garment to its arrangement positions (undo the simulation drape)."""
    return await _call("reset_arrangement")


# ----------------------------------------------------------------------------- checkpoints

@server.tool()
async def checkpoint_save(name: str = "") -> dict:
    """Save the current project as a named checkpoint (.zprj under ~/.clo3d-mcp/checkpoints) so a failed edit or
    seam can be undone with checkpoint_restore."""
    name = name or time.strftime("cp_%Y%m%d_%H%M%S")
    path = str(CHECKPOINT_DIR / f"{name}.zprj")
    r = await _call("save_project", {"path": path, "thumbnail": False}, timeout=600)
    return {"name": name, "path": r.get("path", path)}


@server.tool()
async def checkpoint_restore(name: str) -> dict:
    """Reload a checkpoint saved with checkpoint_save (replaces the scene)."""
    path = CHECKPOINT_DIR / f"{name}.zprj"
    if not path.exists():
        raise ValueError(f"no checkpoint {name}; see checkpoint_list")
    return await _call("open_file", {"path": str(path), "mode": "replace"}, timeout=600)


@server.tool()
async def checkpoint_list() -> dict:
    """List saved checkpoints."""
    files = sorted(CHECKPOINT_DIR.glob("*.zprj"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"checkpoints": [{"name": p.stem, "path": str(p), "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))} for p in files]}


# ----------------------------------------------------------------------------- one-prompt garment builder

SPEC_DOC = """spec fields (all optional, defaults in brackets):
  garment: dress | top | skirt [dress]
  silhouette (dress): sheath, pencil, bodycon, shift, a-line, tent, slip, strapless, tube, mermaid, fit-and-flare, skater,
      empire, babydoll, ball gown, princess, gathered, tiered, drop-waist, shirt-dress, peplum [a-line]
  length: micro, mini, above-knee, knee, below-knee, midi, tea, ankle, maxi, floor, or mm above floor [knee]
      (tops: cropped, waist, hip, tunic)
  neckline: round, crew, scoop, v, deep-v, square, sweetheart, boat, high, off-shoulder, halter, straight [round]
  back_neckline: round, scoop, v, deep-v, open, high, square [round]
  sleeve: none, cap, short, elbow, three-quarter, long [none];  sleeve_style: fitted, regular, puff, bishop, flutter, bell [regular]
  straps: none, thin, wide (slip-style);  strapless: true/false
  waist: natural, empire, drop, high [natural]
  skirt (two-piece dresses/skirts): straight, pencil, a-line, flare, half-circle, full-circle, gathered, tiered, mermaid
  fit: bodycon, fitted, regular, loose, oversized;  ease: {bust, waist, hip} mm overrides
  fabric: free text (satin, silk, chiffon, crepe, cotton, denim, jersey, velvet, tulle, lace, wool, linen ...)
  color: '#hex' or a colour name;  avatar: mia | luka | mannequin | path
  gather_ratio, tiers, simulate_steps, particle_distance"""


async def _ensure_avatar(spec: dict) -> dict:
    info = await _call("scene_info")
    if not info.get("avatars"):
        path = _find_avatar(spec.get("avatar"), _assets_folder(info))
        if not path:
            raise ValueError("no avatar in scene and none found in the library")
        await _call("load_avatar", {"path": path, "replace": True}, timeout=600)
        info = await _call("scene_info")
    return info


@server.tool()
async def garment_plan_preview(spec: dict, use_scene_measurements: bool = False) -> dict:
    """Preview pattern pieces without modifying garments. Defaults to standard measurements and does not contact CLO.
    Set use_scene_measurements=True to measure an already-loaded avatar (may export a temporary OBJ).
    """ + SPEC_DOC
    body, source = drafting.Body(), "standard default measurements; not fitted to a live avatar"
    if use_scene_measurements:
        info = await _call("scene_info")
        if not info.get("avatars"):
            raise ValueError("Load an avatar in CLO first, or preview with use_scene_measurements=False")
        body, source = await _get_body(info["avatars"][0])
    plan = drafting.plan_garment(spec, body)
    d = plan.to_dict()
    for p in d["pieces"]:
        p.pop("points", None)
    d["measurement_source"] = source
    d["normalized_spec"] = plan.spec
    return d


@server.tool()
async def garment_build(spec: dict, simulate_steps: int | None = None, snapshots: bool = True,
                        replace_existing: bool = True, views: list[str] | None = None) -> list[ContentBlock]:
    """Make a complete garment from ONE spec: drafts the pieces from the avatar's measurements, creates them in CLO,
    places them on the avatar, sews, applies fabric + colour, simulates and returns snapshots. Loads the default
    female avatar (Mia) if the scene has none. Existing pattern pieces are replaced (a checkpoint is saved first).
    """ + SPEC_DOC
    info = await _ensure_avatar(spec)
    avatar = info["avatars"][0]
    body, source = await _get_body(avatar)
    plan = drafting.plan_garment(spec, body)
    calib = await _calibration(avatar, FRONT_CANDIDATES + BACK_CANDIDATES)
    arr_notes = _choose_points(plan, calib)
    assets = _assets_folder(info)
    fab_path = _find_fabric(plan.fabric.get("library_stem", ""), assets)
    plan.fabric["path"] = fab_path
    plan_dict = plan.to_dict()
    checkpoint = None
    if replace_existing and info.get("pattern_count"):
        cp = str(CHECKPOINT_DIR / time.strftime("auto_before_build_%Y%m%d_%H%M%S.zprj"))
        try:
            await _call("save_project", {"path": cp, "thumbnail": False}, timeout=600)
            checkpoint = cp
        except Exception:
            pass
    report = await _call("build_garment", {"plan": plan_dict, "options": {"replace": replace_existing}}, timeout=900)
    steps = plan.simulation["steps"] if simulate_steps is None else int(simulate_steps)
    sim = None
    if steps > 0:
        sim = await _call("simulate", {"steps": steps}, timeout=1800)
        if any(int(p.get("layer", 0)) for p in plan_dict["pieces"]):
            # stacked pieces: once settled, drop the layers and let the drape relax
            await _call("reset_layers", {}, timeout=120)
            sim2 = await _call("simulate", {"steps": max(30, steps // 4)}, timeout=1800)
            sim["extra_steps_after_layer_reset"] = sim2.get("steps")
        if plan_dict.get("merge_pairs"):
            merged = await _call("merge_pieces", {"pairs": plan_dict["merge_pairs"]}, timeout=300)
            sim["merged_pieces"] = merged.get("merged")
            report["pieces"] = {n: i for i, n in enumerate(merged.get("names", []))}
            await _call("simulate", {"steps": 30}, timeout=1800)
    _state["last_spec"] = plan.spec
    _state["last_plan"] = plan_dict
    summary = {
        "spec": plan.spec,
        "avatar": avatar,
        "measurements": source,
        "pieces": {p["name"]: {"index": report["pieces"].get(p["name"]), "arrangement": p["arrangement"], "lines": [(e["line"], e["name"], e["length"]) for e in p["edges"]]} for p in plan_dict["pieces"]},
        "seams": report.get("seams"),
        "fabric": {"file": fab_path, "matched": plan.fabric.get("matched"), "color": plan.fabric.get("color")},
        "arrangement": arr_notes,
        "warnings": report.get("warnings", []),
        "notes": plan.notes,
        "simulation": sim,
        "checkpoint_before_build": checkpoint,
    }
    blocks: list[ContentBlock] = [_t(_text(summary))]
    if snapshots:
        res = await _call("snapshot", {"views": views or ["front", "3/4-right", "back"], "folder": str(SNAP_DIR), "prefix": "build"}, timeout=300)
        blocks.extend(_snapshot_blocks(res, "Snapshots after simulation (judge fit, seams, drape; fix with garment_rebuild or pattern tools):"))
    return blocks


@server.tool()
async def garment_rebuild(changes: dict, simulate_steps: int | None = None, snapshots: bool = True) -> list[ContentBlock]:
    """Re-draft the last built garment with modified spec fields (e.g. {"length": "midi"}, {"neckline": "v", "sleeve": "long"},
    {"color": "navy"}, {"fit": "loose"}). Replaces the pieces in CLO and re-simulates."""
    if not _state.get("last_spec"):
        raise ValueError("nothing built yet in this session; call garment_build")
    spec = dict(_state["last_spec"])
    spec.update(changes or {})
    return await garment_build(spec, simulate_steps=simulate_steps, snapshots=snapshots, replace_existing=True)


@server.tool()
async def garment_last_spec() -> dict:
    """The normalized spec and plan summary of the last garment built in this session."""
    return {"spec": _state.get("last_spec"), "pieces": [p["name"] for p in (_state.get("last_plan") or {}).get("pieces", [])]}


from .capabilities import register as register_capabilities
register_capabilities(server, _call, BRIDGE_DIR)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
