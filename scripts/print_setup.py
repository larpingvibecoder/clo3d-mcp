"""Print configuration for this installation. Does not edit client settings or start CLO."""
import json
import shlex
import sys
from pathlib import Path
from clo3d_mcp.server import BRIDGE_DIR

python = str(Path(sys.executable).absolute())
launcher = str(BRIDGE_DIR / "start_bridge.py")
print("1. CLO registration (run once in CLO's Python editor, while the bridge is stopped):")
print(f"import utility_api; utility_api.RegisterPythonScript({launcher!r}, 'Plugins')")
print("\n2. Direct CLO startup alternative (run ONCE per session, while the bridge is stopped):")
print(f"import runpy; runpy.run_path({launcher!r}, run_name='__main__')")
print("\n3. Codex CLI registration (run in Terminal, requires Codex CLI):")
print("codex mcp add clo3d -- " + shlex.join([python, "-m", "clo3d_mcp.server"]))
print("\n4. Generic MCP JSON (merge into the client's existing mcpServers section):")
print(json.dumps({"mcpServers": {"clo3d": {"command": python, "args": ["-m", "clo3d_mcp.server"]}}}, indent=2))
