from pathlib import Path
import importlib.util
import tempfile
import unittest
from tools.check_jass import check_jass
from tools.map_layout import read_info

ROOT=Path(__file__).resolve().parents[1]


class LayoutBuildTests(unittest.TestCase):
    def test_layout_stage_has_coherent_member_dimensions_and_compiles(self):
        if importlib.util.find_spec('tools.layout_stage') is None:
            self.fail('Layout stage integration is missing')
        from tools.layout_stage import prepare_layout
        members,manifest=prepare_layout(ROOT/'scratch/baseline')
        self.assertEqual(read_info(members['war3map.w3i'])['size'],(80,48))
        self.assertEqual(len(members['war3map.shd']),384*256)
        self.assertEqual(len(manifest['human_slots']),5)
        self.assertTrue(set(manifest['human_slots']).isdisjoint(set(manifest['enemy_slots'])))
        self.assertNotIn(4,manifest['human_slots'])
        self.assertNotIn(7,manifest['human_slots'])
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            script=Path(tmp)/'war3map.j'
            script.write_bytes(members['war3map.j'])
            result=check_jass(script,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])
