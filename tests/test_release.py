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
