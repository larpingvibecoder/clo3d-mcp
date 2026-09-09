import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runtime_test', Path(__file__).resolve().parents[1] / 'bridge/runtime_api.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

class Options:
    def __init__(self):
        self.width = 1

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch.dict(sys.modules, {'ApiTypes': types.SimpleNamespace(Options=Options), 'pattern_api': types.SimpleNamespace(GetCount=lambda: 3, ReadWidth=lambda o: o.width)})
        self.modules.start()
    def tearDown(self):
        self.modules.stop()
        runtime._HANDLES.clear()
    def test_typed_arguments(self):
        self.assertEqual(runtime.invoke('pattern_api.ReadWidth', [{'$type':'ApiTypes.Options','fields':{'width':42}}]),42)
    def test_handle_roundtrip(self):
        result = runtime.invoke('ApiTypes.Options')
        self.assertEqual(runtime.invoke('pattern_api.ReadWidth',[{'$handle':result['$handle']}]),1)
        self.assertEqual(runtime.release([result['$handle']]), {'released':1})
        with self.assertRaises(KeyError): runtime.decode({'$handle':result['$handle']})
    def test_reject_private_and_non_clo(self):
        for name in ('os.system','pattern_api.__dict__','pattern_api.GetCount()'):
            with self.assertRaises(ValueError): runtime.resolve(name)
    def test_catalog_pagination(self):
        first = runtime.catalog(module='pattern_api',limit=1)
        second = runtime.catalog(module='pattern_api',offset=first['next_offset'],limit=1)
        self.assertEqual(first['total'],2)
        self.assertNotEqual(first['entries'],second['entries'])
        self.assertIsNone(second['next_offset'])
    def test_unknown_field(self):
        with self.assertRaises(ValueError): runtime.decode({'$type':'ApiTypes.Options','fields':{'typo':1}})

if __name__ == '__main__': unittest.main()
