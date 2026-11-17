"""Artifact gates exercise the actual compiler/archive and detect metadata drift."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class BuildTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.build'),'candidate builder missing')
        self.assertIsNotNone(importlib.util.find_spec('tools.verify_release'),'artifact verifier missing')
        from tools.build import build
        from tools.verify_release import verify_release
        return build,verify_release

    def test_candidate_rebuild_is_deterministic_and_verifier_checks_actual_bytes(self):
        build,verify=self.api()
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            out=Path(tmp);first=build(ROOT/'inputs/original.w3x',out/'a');second=build(ROOT/'inputs/original.w3x',out/'b')
            p=Path(first['path']);self.assertEqual(p.read_bytes(),Path(second['path']).read_bytes())
            result=verify(p);self.assertTrue(result['offline_passed']);self.assertFalse(result['runtime_verified'])
            self.assertGreater(result['preserved_blocks'],1300)
            report=p.with_suffix('.json');data=json.loads(report.read_text(encoding='utf8'))
            data['members']['war3map.j']='0'*64;report.write_text(json.dumps(data),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'member'):verify(p)

    def test_actual_compile_error_prevents_final_map_promotion(self):
        build,_=self.api()
        from tools.selection_stage import prepare_selection
        def broken(raw):
            script,assets,report=prepare_selection(raw)
            return script+b'\nfunction Broken takes nothing returns nothing\ncall MissingNative()\nendfunction\n',assets,report
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            out=Path(tmp)/'out'
            with patch('tools.build_checkpoint.prepare_selection',side_effect=broken):
                with self.assertRaises(RuntimeError):build(ROOT/'inputs/original.w3x',out)
            self.assertEqual(list(out.glob('*.w3x')),[])

    def test_wrong_original_and_existing_candidate_are_rejected(self):
        build,_=self.api()
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            out=Path(tmp);bad=out/'bad.w3x';bad.write_bytes(b'wrong source')
            with self.assertRaises(ValueError):build(bad,out/'result')
            self.assertFalse((out/'result').exists())
            from tools.build import NAME
            target=out/'existing';target.mkdir();(target/NAME).write_bytes(b'keep')
            with self.assertRaises(FileExistsError):build(ROOT/'inputs/original.w3x',target)
            self.assertEqual((target/NAME).read_bytes(),b'keep')
