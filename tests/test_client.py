import json
import unittest
from unittest.mock import patch
from clo3d_mcp.client import CloClient, CloBridgeError

class Socket:
    def __init__(self, mode): self.mode = mode
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def settimeout(self, value): pass
    def sendall(self, data):
        request = json.loads(data)
        response = json.dumps({'id': 'wrong' if self.mode == 'wrong' else request['id'], 'ok':True,'result':42}).encode()
        self.chunks = [response[:8], response[8:] + (b'' if self.mode == 'truncated' else b'\n'), b'']
    def recv(self, count): return self.chunks.pop(0)

class ClientTests(unittest.TestCase):
    def test_fragmented(self):
        with patch('socket.create_connection',return_value=Socket('ok')):
            self.assertEqual(CloClient().ping(),42)
    def test_wrong_id_and_truncation(self):
        for mode in ('wrong','truncated'):
            with patch('socket.create_connection',return_value=Socket(mode)):
                with self.assertRaises(CloBridgeError): CloClient().ping()
