"""Compile the actual roster and its in-game assertion harness; not runtime proof."""
from pathlib import Path
import tempfile
import unittest
from tools.check_jass import check_jass

ROOT=Path(__file__).resolve().parents[1]


class RosterCompileTests(unittest.TestCase):
    def test_roster_and_in_game_assertions_compile(self):
        module=ROOT/'src/roster.j'
        harness=ROOT/'tests/runtime/roster_test.j'
        self.assertTrue(module.exists(),'Roster implementation is missing')
        self.assertTrue(harness.exists(),'In-game assertion harness is missing')
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            script=Path(tmp)/'roster.j'
            script.write_bytes(module.read_bytes()+harness.read_bytes())
            result=check_jass(script,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])
