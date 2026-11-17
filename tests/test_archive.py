"""Catch destructive output paths, baseline drift, and MPQ resource loss."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'inputs/original.w3x'
BASELINE = 'f5aa029c5d43f49ee9d6bf3d710d54714528450cecf9b27ae2dc539bde765853'


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec('tools.archive') is None:
            self.fail('Archive update implementation is missing')
        from tools import archive
        self.api = archive
        (ROOT / 'scratch').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'scratch')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'test.w3x'

    def test_reject_source_as_destination(self):
        with self.assertRaisesRegex(ValueError, 'source|destination'):
            self.api.update_archive(SOURCE, SOURCE, {})
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), BASELINE)

    def test_reject_wrong_baseline(self):
        source = Path(self.tmp.name) / 'wrong.w3x'
        source.write_bytes(b'not the approved map')
        with self.assertRaisesRegex(ValueError, 'baseline'):
            self.api.update_archive(source, self.out, {})
        self.assertFalse(self.out.exists())

    def test_identity_copy_preserves_all_blocks(self):
        report = self.api.update_archive(SOURCE, self.out, {})
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(), BASELINE)
        self.assertGreaterEqual(report['preserved_blocks'], 1300)

    def test_replace_script_preserves_unknown_members(self):
        original = self.api.read_member(SOURCE, 'war3map.j')
        edited = original + b'\n// archive integration test\n'
        report = self.api.update_archive(SOURCE, self.out, {'war3map.j': edited})
        self.assertEqual(self.api.read_member(self.out, 'war3map.j'), edited)
        self.assertGreaterEqual(report['preserved_blocks'], 1300)
        self.assertTrue(report['unknown_members_preserved'])
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), BASELINE)

    def test_reject_existing_destination(self):
        self.out.write_bytes(b'keep this file')
        with self.assertRaises(FileExistsError):
            self.api.update_archive(SOURCE, self.out, {})
        self.assertEqual(self.out.read_bytes(), b'keep this file')

    def test_preservation_rejects_corrupted_resource(self):
        raw = SOURCE.read_bytes()
        import io, sys
        sys.path.insert(0, str(ROOT / 'vendor'))
        import mpyq
        table = mpyq.MPQArchive(io.BytesIO(raw[512:]), listfile=False)
        block = next(b for b in table.block_table if b.archived_size > 10000)
        corrupted = bytearray(raw)
        corrupted[512 + block.offset + 20] ^= 1
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.api.verify_preservation(raw, bytes(corrupted), {})


if __name__ == '__main__':
    unittest.main()
