"""Register this file in CLO once, then run it once per CLO session."""
import builtins
from pathlib import Path
import runpy

if getattr(builtins, "_CLO3D_MCP_ACTIVE", False):
    print("CLO MCP bridge is already running. Do not start it again.")
else:
    runpy.run_path(str(Path(__file__).resolve().with_name("clo_bridge.py")), run_name="__main__")
