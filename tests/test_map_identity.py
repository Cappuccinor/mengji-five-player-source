from pathlib import Path
import unittest
from tools.map_identity import TITLE,rename_header,rename_info,rename_script

ROOT=Path(__file__).resolve().parents[1]

class MapIdentityTests(unittest.TestCase):
    def test_title_changes_preserve_other_metadata_and_archive_offsets(self):
        raw=(ROOT/'inputs/original.w3x').read_bytes()
        changed=rename_header(raw)
        old_end=raw.index(b'\0',8);new_end=changed.index(b'\0',8)
        self.assertEqual(changed[8:new_end].decode(),TITLE)
        self.assertEqual(raw[old_end+1:old_end+9],changed[new_end+1:new_end+9])
        self.assertEqual(raw[512:],changed[512:])
        info=(ROOT/'scratch/baseline/war3map.w3i').read_bytes()
        edited=rename_info(info)
        self.assertEqual(edited[12:edited.index(b'\0',12)].decode(),TITLE)
        self.assertEqual(info[info.index(b'\0',12):],edited[edited.index(b'\0',12):])
        script=(ROOT/'scratch/baseline/war3map.j').read_bytes()
        self.assertIn(('call SetMapName("'+TITLE+'")').encode(),rename_script(script))
