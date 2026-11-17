import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class JassTests(unittest.TestCase):
    def test_accept_valid_and_reject_bad_call(self):
        if importlib.util.find_spec('tools.check_jass') is None:
            self.fail('JASS checker is missing')
        from tools.check_jass import check_jass
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as tmp:
            script = Path(tmp) / 'test.j'
            script.write_text('function test takes nothing returns nothing\ncall BJDebugMsg("ok")\nendfunction\n')
            self.assertTrue(check_jass(script, ROOT / 'vendor/jass-1.27.1')['passed'])
            script.write_text('function test takes nothing returns nothing\ncall MissingFunction()\nendfunction\n')
            result = check_jass(script, ROOT / 'vendor/jass-1.27.1')
            self.assertFalse(result['passed'])
            self.assertIn('MissingFunction', result['output'])

    def test_original_script_has_no_compiler_errors(self):
        if importlib.util.find_spec('tools.check_jass') is None:
            self.fail('JASS checker is missing')
        from tools.check_jass import check_jass
        result = check_jass(ROOT / 'scratch/baseline/war3map.j', ROOT / 'vendor/jass-1.27.1')
        self.assertTrue(result['passed'], result['output'])
