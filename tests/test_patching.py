import importlib.util
import hashlib
import unittest

SOURCE='globals\ninteger old=0\nendglobals\nfunction first takes nothing returns nothing\nendfunction\n'


class PatchingTests(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec('tools.patching') is None:
            self.fail('Function patcher is missing')
        from tools import patching
        self.api=patching

    def test_function_edit_is_scoped_and_checks_original(self):
        old=SOURCE[SOURCE.index('function'):]
        sha=hashlib.sha256(old.encode()).hexdigest()
        new='function first takes nothing returns nothing\ncall BJDebugMsg("edited")\nendfunction\n'
        self.assertEqual(self.api.replace_function(SOURCE,'first',sha,new),SOURCE[:SOURCE.index('function')]+new)
        with self.assertRaisesRegex(ValueError,'hash'):
            self.api.replace_function(SOURCE.replace('returns nothing','returns integer'),'first',sha,new)

    def test_missing_or_duplicate_function_fails_closed(self):
        with self.assertRaises(ValueError):
            self.api.replace_function(SOURCE,'unknown','bad','')
        with self.assertRaises(ValueError):
            self.api.replace_function(SOURCE+SOURCE[SOURCE.index('function'):],'first','bad','')

    def test_module_globals_and_functions_have_valid_order(self):
        module='globals\ninteger added=1\nendglobals\nfunction added takes nothing returns nothing\nendfunction\n'
        result=self.api.inject_module(SOURCE,module)
        self.assertEqual(result,'globals\ninteger old=0\ninteger added=1\nendglobals\nfunction added takes nothing returns nothing\nendfunction\nfunction first takes nothing returns nothing\nendfunction\n')
