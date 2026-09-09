import time
import unittest
from unittest.mock import Mock
from clo3d_mcp.desktop import Desktop

class DesktopGuards(unittest.TestCase):
    def setUp(self):
        self.desktop=Desktop()
        self.desktop.backend=Mock(side_effect=AssertionError('Must not access desktop for invalid input'))
    def action(self, token, action='click', **kwargs):
        params=dict(element=None,value='',x=0,y=0,end_x=0,end_y=0,keycode=0,modifiers=[])
        params.update(kwargs)
        return self.desktop.action(token,action,**params)
    def test_missing_and_expired_snapshot(self):
        with self.assertRaises(ValueError): self.action('missing')
        self.desktop.token='old'
        self.desktop.observed_at=time.monotonic()-61
        with self.assertRaises(ValueError): self.action('old')
        self.desktop.backend.assert_not_called()
    def test_invalid_input(self):
        self.desktop.token='fresh'
        self.desktop.observed_at=time.monotonic()
        for kwargs in ({'x':float('nan')},{'keycode':128},{'modifiers':['unknown']}):
            with self.assertRaises(ValueError): self.action('fresh',**kwargs)
        with self.assertRaises(ValueError): self.action('fresh','unknown')
        self.desktop.backend.assert_not_called()
