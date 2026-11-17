from pathlib import Path
import tempfile
import unittest
from tools.layout_stage import prepare_layout
from tools.player_stage import prepare_players
from tools.selection_stage import prepare_selection
from tools.patching import functions
from tools.check_jass import check_jass

ROOT=Path(__file__).resolve().parents[1]


class LaneStageTests(unittest.TestCase):
    def test_fifth_lane_initialization_and_combined_selection_compile(self):
        from tools.lane_stage import prepare_lane
        members,_=prepare_layout(ROOT/'scratch/baseline')
        player_script,_=prepare_players(members['war3map.j'])
        script,report=prepare_lane(player_script)
        f=functions(script.decode())
        self.assertIn('set MJ5_BZ=Rect(6400.,2304.,7168.,3072.)',f['sk'][0])
        self.assertIn('set MJ5_C1=CreateUnit(Ch,$6E303033,4736.,640.,225.)',f['sa'][0])
        self.assertIn('set Ch=Player(5)',f['sa'][0])
        self.assertIn('set MJ5_C8=CreateUnit(Ch,$68303031,4734.6,1151.7,45.)',f['sf'][0])
        self.assertIn('call ForceAddPlayerSimple(Player(5),Fa)',f['s2'][0])
        self.assertIn('call ForceAddPlayerSimple(Player(6),Fb)',f['s2'][0])
        self.assertIn('GetHandleId(Player(5)),$9DC2FEEA,MJ5_C1',f['s2'][0])
        self.assertIn('GetHandleId(Player(5)),$1E9008DF,GetRectCenter(MJ5_Be)',f['uW'][0])
        self.assertIn('Location(5632.,2816.)',f['uW'][0])
        self.assertIn('function MJ5_uN',f['uW'][0])
        self.assertNotIn('Player(1)',f['MJ5_uN'][0])
        self.assertIn('call RemoveUnit(MJ5_C1)',f['uW'][0])
        self.assertIn('call SetUnitOwner(GetTriggerUnit(),Player(5),true)',f['BOB'][0])
        self.assertIn('call MultiboardSetRowCount(JF,6)',f['us'][0])
        self.assertIn('exitwhen Gi>6',f['us'][0])
        self.assertIn('call KillUnit(MJ5_C0)',f['BQV'][0])
        self.assertFalse(report['runtime_verified'])
        final,_,_=prepare_selection(script)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j'; path.write_bytes(final)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])

    def test_missing_expected_block_stops_patch(self):
        from tools.lane_stage import prepare_lane
        members,_=prepare_layout(ROOT/'scratch/baseline')
        with self.assertRaises(ValueError):
            prepare_lane(members['war3map.j'].replace(b'set C1=CreateUnit',b'set C1=OtherUnit'))
