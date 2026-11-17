from pathlib import Path
import tempfile
import unittest
from tools.archive import BASELINE
import hashlib

ROOT=Path(__file__).resolve().parents[1]


class PrepareWorkspaceTests(unittest.TestCase):
    def test_materialize_original_inputs_in_another_directory(self):
        from tools.prepare_workspace import prepare_workspace
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            target=Path(tmp)
            report=prepare_workspace(ROOT/'inputs/original.w3x', target)
            self.assertEqual(report['source_sha256'],BASELINE)
            self.assertEqual(hashlib.sha256((target/'scratch/baseline/war3map.j').read_bytes()).hexdigest(),
                             '95e678ea586d153fc154d99fed0ae9718b382d86aee2b1b7a670194208950633')
            self.assertTrue((target/'scratch/extracted/Units_CampaignUnitStrings.txt').exists())
            self.assertEqual(len(list((target/'scratch/extracted').glob('*AbilityStrings.txt'))),8)
            # Re-running doesn't destroy unrelated files or silently overwrite edits.
            sentinel=target/'scratch/baseline/keep.txt'; sentinel.write_text('keep')
            prepare_workspace(ROOT/'inputs/original.w3x',target)
            self.assertEqual(sentinel.read_text(),'keep')
            script=target/'scratch/baseline/war3map.j'; script.write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError,'existing'):
                prepare_workspace(ROOT/'inputs/original.w3x',target)
            self.assertEqual(script.read_bytes(),b'edited')

    def test_wrong_input_does_not_create_baseline(self):
        from tools.prepare_workspace import prepare_workspace
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            target=Path(tmp); source=target/'bad.w3x'; source.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'baseline'):
                prepare_workspace(source,target)
            self.assertFalse((target/'scratch/baseline').exists())
