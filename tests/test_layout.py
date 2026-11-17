"""Verify map binary roundtrips and preservation of original world space."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'scratch/baseline'


class LayoutTests(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec('tools.map_layout') is None:
            self.fail('Binary layout implementation is missing')
        from tools import map_layout
        self.api = map_layout

    def test_terrain_preserves_original_vertices_and_copies_east_extension(self):
        original = (BASE / 'war3map.w3e').read_bytes()
        info = self.api.read_terrain(original)
        self.assertEqual((info['width'], info['height'], info['origin']), (65, 65, (-4096.0, -4096.0)))
        edited = self.api.extend_terrain(original)
        expanded = self.api.read_terrain(edited)
        self.assertEqual((expanded['width'], expanded['height'], expanded['origin']), (97, 65, (-4096.0, -4096.0)))
        for y in range(65):
            self.assertEqual(expanded['rows'][y][:65*7], info['rows'][y])
            self.assertEqual(expanded['rows'][y][65*7:], info['rows'][y][33*7:])

    def test_path_grid_retains_old_cells_and_fifth_spawn_is_walkable(self):
        original = (BASE / 'war3map.wpm').read_bytes()
        edited = self.api.extend_pathing(original)
        self.assertEqual(struct.unpack_from('<II', edited, 8), (384, 256))
        for y in range(256):
            self.assertEqual(edited[16+y*384:16+y*384+256], original[16+y*256:16+(y+1)*256])
        for x,y in [(6784,2688),(5760,1664),(4736,640)]:
            cell = edited[16 + int((y+4096)/32)*384 + int((x+4096)/32)]
            self.assertEqual(cell & 2, 0, (x,y,cell))

    def test_shadow_dimensions_and_original_values(self):
        original = (BASE / 'war3map.shd').read_bytes()
        edited = self.api.extend_shadow(original)
        self.assertEqual(len(edited), 384*256)
        for y in range(256):
            self.assertEqual(edited[y*384:y*384+256], original[y*256:(y+1)*256])

    def test_info_roundtrip_and_five_human_slots(self):
        original = (BASE / 'war3map.w3i').read_bytes()
        parsed = self.api.read_info(original)
        self.assertEqual(self.api.write_info(parsed), original)
        edited = self.api.read_info(self.api.extend_info(original))
        self.assertEqual(sorted(p['id'] for p in edited['players'] if p['type']==1), [0,1,2,3,5])
        self.assertEqual(sorted(p['id'] for p in edited['players'] if p['type']==2), [4,6,8,9,10,11])
        self.assertEqual(edited['size'], (80,48))
        self.assertEqual(edited['tail'], parsed['tail'])
        self.assertEqual(edited['forces'][0]['mask'], 63)
        self.assertEqual(edited['forces'][1]['mask'], 3904)

    def test_bad_dimensions_fail_closed(self):
        bad = bytearray((BASE/'war3map.wpm').read_bytes())
        struct.pack_into('<I',bad,8,123)
        with self.assertRaises(ValueError):
            self.api.extend_pathing(bytes(bad))

    def test_fifth_lane_doodads_have_new_ids_and_shifted_coordinates(self):
        original = (BASE/'war3map.doo').read_bytes()
        if not hasattr(self.api,'extend_doodads'):
            self.fail('Doodad extension is missing')
        old = self.api.read_doodads(original)
        new = self.api.read_doodads(self.api.extend_doodads(original))
        self.assertEqual(new['records'][:109],old['records'])
        self.assertGreater(len(new['records']),109)
        ids=[struct.unpack_from('<I',r,len(r)-4)[0] for r in new['records']]
        self.assertEqual(len(ids),len(set(ids)))
        expected=[r for r in old['records'] if 0 <= struct.unpack_from('<f',r,8)[0] <= 3136 and 0 <= struct.unpack_from('<f',r,12)[0] <=3136]
        for a,b in zip(expected,new['records'][109:]):
            self.assertAlmostEqual(struct.unpack_from('<f',b,8)[0]-struct.unpack_from('<f',a,8)[0],4096,places=2)
            self.assertEqual(a[12:len(a)-4],b[12:len(b)-4])
