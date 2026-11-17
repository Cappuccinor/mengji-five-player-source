import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.check_jass import check_jass
from tools.layout_stage import prepare_layout

ROOT=Path(__file__).resolve().parents[1]


class AssetPortabilityTests(unittest.TestCase):
    def test_windows_checkout_line_endings_do_not_change_packed_ui(self):
        from tools.layout_stage import prepare_layout
        from tools.selection_stage import prepare_selection
        members,_=prepare_layout(ROOT/'scratch/baseline')
        _,expected,_=prepare_selection(members['war3map.j'])
        original_read=Path.read_bytes
        def windows_read(path):
            data=original_read(path)
            if path.suffix in ['.fdf','.toc']:
                return data.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
            return data
        with patch.object(Path,'read_bytes',windows_read):
            _,actual,_=prepare_selection(members['war3map.j'])
        self.assertEqual(expected,actual)


class SelectionBuildTests(unittest.TestCase):
    def test_actual_integrated_selection_script_compiles(self):
        if importlib.util.find_spec('tools.selection_stage') is None:
            self.fail('Selection integration is missing')
        from tools.selection_stage import prepare_selection
        members,_=prepare_layout(ROOT/'scratch/baseline')
        script,assets,report=prepare_selection(members['war3map.j'])
        self.assertEqual(report['hero_count'],158)
        self.assertIn('MJ5\\hero.fdf',assets)
        self.assertIn('MJ5\\hero.toc',assets)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j'
            path.write_bytes(script)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])
