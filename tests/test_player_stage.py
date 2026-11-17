"""Static regression tests for reviewed player callsites; no game-engine claim."""
from pathlib import Path
import tempfile
import unittest
from tools.layout_stage import prepare_layout
from tools.patching import functions
from tools.check_jass import check_jass

ROOT = Path(__file__).resolve().parents[1]


class PlayerStageTests(unittest.TestCase):
    def test_five_player_calls_preserve_non_player_loops_and_compile(self):
        from tools.player_stage import prepare_players
        members, _ = prepare_layout(ROOT/'scratch/baseline')
        before = members['war3map.j'].decode()
        after, report = prepare_players(members['war3map.j'])
        f, old = functions(after.decode()), functions(before)
        self.assertEqual(report['expanded_player_loops'], 33)
        for name in ['BCd','BGX','BHH','BD5','y3','y5','y7','BBy','BFz','BHL','BHX','BKO']:
            self.assertEqual(f[name][0], old[name][0], name)
        self.assertIn('exitwhen Gi>99', f['BQm'][0])
        self.assertIn('exitwhen Gi>12', f['BQm'][0])
        self.assertNotIn('HQ[Gi-1]', f['v4'][0])
        self.assertIn('MJ_HumanOf(GetOwningPlayer(GetDyingUnit()))', f['zI'][0])
        self.assertIn('MJ_EnemyOf(GetOwningPlayer(GetTriggerUnit()))', f['zF'][0])
        self.assertNotIn('ConvertedPlayer(Gi+8)', after.decode())
        self.assertEqual(report['monster_sum_replacements'], 11)
        self.assertIn('exitwhen Gi>6', f['vv'][0])
        self.assertIn('GetHandleId(Player(5)),$D98597C0', f['vv'][0])
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            p=Path(tmp)/'war3map.j'; p.write_bytes(after)
            result=check_jass(p,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'], result['output'])

    def test_call_rewriter_ignores_strings_and_preserves_nested_arguments(self):
        from tools.player_stage import rewrite_offsets
        actual='ConvertedPlayer(GetConvertedPlayerId(LoadPlayerHandle(EK,GetHandleId(t),$A))+8)'
        text='call Foo('+actual+')\ncall Print("'+actual+'")\n// '+actual+'\n'
        changed, count=rewrite_offsets(text)
        self.assertEqual(count,1)
        self.assertIn('Foo(MJ_EnemyOf(LoadPlayerHandle(EK,GetHandleId(t),$A)))',changed)
        self.assertIn('Print("'+actual+'")',changed)
        self.assertIn('// '+actual,changed)

    def test_reapplying_stage_is_rejected(self):
        from tools.player_stage import prepare_players
        members,_=prepare_layout(ROOT/'scratch/baseline')
        modified,_=prepare_players(members['war3map.j'])
        with self.assertRaises(ValueError):
            prepare_players(modified)
