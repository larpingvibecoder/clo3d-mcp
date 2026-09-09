"""Validate the built wheel in an isolated environment and working directory.
Run after uv build: uv run --no-editable python scripts/check_wheel.py
"""
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
wheel = root / 'dist/clo3d_mcp-0.1.0a1-py3-none-any.whl'
assert wheel.is_file(), 'Run uv build first'
with zipfile.ZipFile(wheel) as z:
    names = set(z.namelist())
    for name in ('server.py', 'client.py', '_bridge/start_bridge.py', '_bridge/clo_bridge.py', '_bridge/clo_ops.py', '_bridge/runtime_api.py'):
        assert 'clo3d_mcp/' + name in names, name
    assert not any('__pycache__' in n or '/data/api_' in n for n in names)
    assert any(n.endswith('/licenses/LICENSE') for n in names)
with tempfile.TemporaryDirectory(prefix='clo release wheel ') as tmp:
    temp = Path(tmp)
    subprocess.run(['uv', 'venv', '--python', '3.12', str(temp/'venv')], check=True)
    python = temp/'venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run(['uv', 'pip', 'install', '--python', str(python), str(wheel)], check=True)
    env = dict(os.environ, CLO_MCP_STATE=str(temp/'state'))
    env.pop('PYTHONPATH', None)
    subprocess.run([str(python), '-c', "from clo3d_mcp.server import BRIDGE_DIR; assert (BRIDGE_DIR/'start_bridge.py').is_file(); print('PASS: installed bridge resources')"], cwd=tmp, env=env, check=True)
    subprocess.run([str(python), str(root/'tests/smoke_stdio.py')], cwd=tmp, env=env, check=True)
print('PASS: isolated wheel install and MCP startup, from a path containing spaces')
