"""Regression coverage for distribution, offline preview, and bridge startup safeguards."""
import asyncio
import builtins
import importlib.util
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from clo3d_mcp import __version__
from clo3d_mcp import server

ROOT = Path(__file__).resolve().parents[1]


def test_bridge_files_available():
    for name in ('start_bridge.py', 'clo_bridge.py', 'clo_ops.py', 'runtime_api.py'):
        assert (server.BRIDGE_DIR / name).is_file()


def test_offline_preview_does_not_contact_clo():
    with patch.object(server, '_call', AsyncMock(side_effect=AssertionError('must stay offline'))):
        result = asyncio.run(server.garment_plan_preview({'silhouette': 'slip'}))
    assert result['pieces']


def test_scene_preview_does_not_load_an_avatar():
    with patch.object(server, '_call', AsyncMock(return_value={'avatars': []})) as call:
        with pytest.raises(ValueError, match='Load an avatar'):
            asyncio.run(server.garment_plan_preview({}, use_scene_measurements=True))
        call.assert_awaited_once_with('scene_info')


def test_launcher_handles_spaces_and_renamed_checkout(tmp_path):
    folder = tmp_path / 'some other checkout'
    folder.mkdir()
    (folder / 'start_bridge.py').write_text((ROOT / 'bridge/start_bridge.py').read_text())
    with patch.object(builtins, '_CLO3D_MCP_ACTIVE', False, create=True), patch('runpy.run_path') as run:
        exec(compile((folder/'start_bridge.py').read_text(), str(folder/'start_bridge.py'), 'exec'), {'__file__': str(folder/'start_bridge.py')})
    run.assert_called_once_with(str(folder/'clo_bridge.py'), run_name='__main__')


def test_duplicate_launcher_does_not_reenter():
    with patch.object(builtins, '_CLO3D_MCP_ACTIVE', True, create=True), patch('runpy.run_path') as run:
        exec(compile((ROOT/'bridge/start_bridge.py').read_text(), '<launcher>', 'exec'), {'__file__': str(ROOT/'bridge/start_bridge.py')})
    run.assert_not_called()


def load_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv('CLO_MCP_STATE', str(tmp_path))
    monkeypatch.setenv('CLO_MCP_HOST', '127.0.0.1')
    spec = importlib.util.spec_from_file_location('release_bridge_test', ROOT/'bridge/clo_bridge.py')
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    return bridge


def test_bridge_rejects_malformed_requests(tmp_path, monkeypatch):
    b = load_bridge(tmp_path, monkeypatch)
    for bad in ([], None, 2, {'cmd': []}, {'cmd': 'ping', 'params': [1]}, {'cmd': 'ping', 'params': []}):
        assert b.dispatch(bad)['ok'] is False
    assert b.dispatch({'id': '1', 'cmd': 'ping'})['ok'] is True
    assert b.BRIDGE_VERSION == __version__


def test_bridge_refuses_to_freeze_ui(tmp_path, monkeypatch):
    b = load_bridge(tmp_path, monkeypatch)
    with patch.object(b, '_load_process_events', return_value=False), patch.object(b.socket, 'socket') as sock:
        b.serve()
    sock.assert_not_called()
    assert (tmp_path/'bridge_status.json').is_file()


def test_client_rejects_network_host():
    from clo3d_mcp.client import CloClient
    with pytest.raises(ValueError, match='loopback'):
        CloClient(host='0.0.0.0')


def test_bridge_rejects_network_host(monkeypatch, tmp_path):
    monkeypatch.setenv('CLO_MCP_HOST', '0.0.0.0')
    with pytest.raises(ValueError, match='loopback'):
        runpy.run_path(str(ROOT/'bridge/clo_bridge.py'), run_name='test')


def test_runtime_syntax_error_does_not_repeat_code(tmp_path, monkeypatch):
    b = load_bridge(tmp_path, monkeypatch)
    calls = []
    def fail():
        calls.append(1)
        raise SyntaxError("raised by the called function")
    b.NS['fail'] = fail
    with pytest.raises(SyntaxError):
        b.cmd_exec({'code': 'fail()'})
    assert calls == [1]


def test_bridge_binds_msvc_qt_symbols(tmp_path, monkeypatch):
    """Windows Qt builds export MSVC-mangled names; the int-timeout overload must get two int arguments."""
    b = load_bridge(tmp_path, monkeypatch)
    calls = []
    class FakeFn:
        def __call__(self, *args):
            calls.append(args)
    class FakeLib:
        pass
    lib = FakeLib()
    setattr(lib, b._MSVC_SYMBOLS[1], FakeFn())
    assert b._bind_process_events(lib, b._MSVC_SYMBOLS) is True
    b.pump()
    assert calls == [(0, 5)]
    assert b._bind_process_events(FakeLib(), b._MSVC_SYMBOLS) is False


def test_bridge_qt_lookup_failure_is_reported_not_raised(tmp_path, monkeypatch):
    b = load_bridge(tmp_path, monkeypatch)
    def broken():
        raise OSError('no Qt here')
        yield
    with patch.object(b, '_qt_libraries', broken):
        assert b._load_process_events() is False


def test_clo_executable_accepts_install_folder(tmp_path):
    exe = tmp_path / 'CLO_Standalone_OnlineAuth_x64.exe'
    exe.write_bytes(b'')
    assert server._clo_executable(str(tmp_path)) == str(exe)
    assert server._clo_executable(str(exe)) == str(exe)


def test_windows_process_check_uses_tasklist(monkeypatch):
    monkeypatch.setattr(server, 'IS_WINDOWS', True)
    result = type('R', (), {'stdout': '"CLO_Standalone_OnlineAuth_x64.exe","1234","Console","1","2,000,000 K"\n'})()
    with patch.object(server.subprocess, 'run', return_value=result) as run:
        assert server._clo_running() is True
    assert run.call_args.args[0][0] == 'tasklist'
    result.stdout = 'INFO: No tasks are running which match the specified criteria.\n'
    with patch.object(server.subprocess, 'run', return_value=result):
        assert server._clo_running() is False


def test_pump_crash_stops_bridge_and_records_status(tmp_path, monkeypatch):
    """A native fault in processEvents (OSError on Windows) must end the loop, not pump again."""
    import json
    monkeypatch.setenv('CLO_MCP_PORT', '0')
    b = load_bridge(tmp_path, monkeypatch)
    calls = []
    def crash():
        calls.append(1)
        raise OSError('exception: access violation reading 0x0000000000000010')
    with patch.object(b, '_load_process_events', return_value=True), patch.object(b, '_load_ops'), \
            patch.object(b, '_process_events', crash):
        b.serve()
    assert calls == [1]
    assert json.loads((tmp_path/'bridge_status.json').read_text())['state'] == 'pump_error'
    assert 'Qt event pump failed' in (tmp_path/'bridge.log').read_text()
    assert builtins._CLO3D_MCP_ACTIVE is False


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Qt lookup')
def test_windows_qt_bound_with_gil_held(tmp_path, monkeypatch):
    """CLO runs Python inside Qt event handlers; the call must not release the GIL (PyDLL, not CDLL)."""
    b = load_bridge(tmp_path, monkeypatch)
    class Kernel32:
        class GetModuleHandleW:
            argtypes = restype = None
            def __new__(cls, name):
                return 1234 if name == 'Qt6Core.dll' else None
    with patch.object(b.ctypes, 'WinDLL', return_value=Kernel32), \
            patch.object(b.ctypes, 'PyDLL') as pydll, patch.object(b.ctypes, 'CDLL') as cdll:
        libs = list(b._qt_libraries())
    assert len(libs) == 1 and libs[0][1] is b._MSVC_SYMBOLS
    pydll.assert_called_once_with('Qt6Core.dll', handle=1234)
    cdll.assert_not_called()
