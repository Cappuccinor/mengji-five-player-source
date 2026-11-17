import math
import re
import struct
from pathlib import Path
import unittest

from tools.radial_layout import forward, inverse, lane_matrix, build_geometry, contains, reachable, path_index
from tools.map_layout import read_terrain, read_info
from tools.radial_stage import prepare_radial, REGION_LANE
from tools.archive import read_member
from tools.patching import functions

ROOT = Path(__file__).resolve().parents[1]


class RadialLayoutTests(unittest.TestCase):
    def test_original_combat_walkable_footprint_is_not_clipped_by_wedge(self):
        from tools.radial_layout import surface, SIGNS
        original=(ROOT/'scratch/baseline/war3map.wpm').read_bytes()[16:]
        for lane,(sx,sy) in enumerate(SIGNS):
            checked=0
            for row in range(98):
                for col in range(98):
                    x,y=(col+.5)*32,(row+.5)*32
                    # These original noncombat rooms have separate destinations.
                    if x<=768 and y>=2304:continue
                    ox,oy=sx*x,sy*y
                    index=int((oy+4096)//32)*256+int((ox+4096)//32)
                    if original[index]&2:continue
                    nx,ny=forward(lane,ox+(4096 if lane==4 else 0),oy)
                    self.assertNotEqual(surface(nx,ny),0,(lane,ox,oy,nx,ny))
                    checked+=1
            self.assertGreater(checked,5900)

    def test_authored_lane_pathing_flags_survive_rotation(self):
        from tools.radial_layout import ORIGIN, GRID, surface, terrain_source, radial_coordinates
        members,_=build_geometry(ROOT/'scratch/baseline')
        original=(ROOT/'scratch/baseline/war3map.wpm').read_bytes()
        terrain=read_terrain((ROOT/'scratch/baseline/war3map.w3e').read_bytes())
        _,width,height=struct.unpack_from('<III',original,4)
        grid=members['war3map.wpm'][16:]
        blocked=[0]*5
        # Outside intentional shop/hub overrides, compare the archived authored
        # flags themselves, including narrow channel shoulders, in every lane.
        for iy in range(GRID):
            for ix in range(GRID):
                x,y=ORIGIN+(ix+.5)*32,ORIGIN+(iy+.5)*32
                if surface(x,y) not in (1,2):continue
                lane=max(range(5),key=lambda i:radial_coordinates(i,x,y)[0])
                r,v=radial_coordinates(lane,x,y)
                if not 2400<r<3200:continue
                sx,sy=terrain_source(x,y)
                ox=int((sx-terrain['origin'][0])//32)
                oy=int((sy-terrain['origin'][1])//32)
                self.assertTrue(0<=ox<width and 0<=oy<height)
                expected=original[16+oy*width+ox]
                self.assertEqual(grid[iy*GRID+ix],expected,(lane,r,v))
                if expected&2:blocked[lane]+=1
        self.assertTrue(all(count>100 for count in blocked),blocked)

    def test_restored_channels_connect_spawns_and_shop_approaches(self):
        from tools.radial_stage import shop_point
        members,report=build_geometry(ROOT/'scratch/baseline')
        grid=members['war3map.wpm'][16:];connected=reachable(grid)
        self.assertTrue(all(r['spawn_to_center_connected'] for r in report['routes']))
        for lane in range(5):
            for kind in range(3):
                x,y=shop_point(lane,kind)
                # Include landing room around each building, not only its center.
                for dx,dy in [(0,0),(96,0),(-96,0),(0,96),(0,-96)]:
                    self.assertIn(path_index(x+dx,y+dy),connected,(lane,kind,dx,dy))
        for x,y in [(0,0),(0,-3200),(0,-4500)]:
            self.assertFalse(grid[path_index(x,y)]&2)

    def test_five_spawns_equal_radius_and_72_degree_spacing(self):
        canonical = [(-2688,2688),(2688,2688),(-2688,-2688),(2688,-2688),(6784,2688)]
        points = [forward(i,*p) for i,p in enumerate(canonical)]
        radii = [math.hypot(*p) for p in points]
        self.assertLess(max(radii)-min(radii),0.001)
        angles = sorted(math.degrees(math.atan2(y,x)) % 360 for x,y in points)
        gaps = [(angles[(i+1)%5]-angles[i])%360 for i in range(5)]
        for gap in gaps:self.assertAlmostEqual(gap,72)
        for i,p in enumerate(canonical):
            for a,b in zip(inverse(i,*points[i]),p):self.assertAlmostEqual(a,b)

    def test_rotated_region_does_not_admit_its_bounding_box_corners(self):
        rect=(2304,2304,3072,3072)
        points=[forward(1,x,y) for x in (2304,3072) for y in (2304,3072)]
        box_corner=(min(p[0] for p in points),min(p[1] for p in points))
        self.assertFalse(contains(1,rect,*box_corner))
        self.assertTrue(contains(1,rect,*forward(1,2688,2688)))

    def test_geometry_is_square_and_all_five_routes_connect_to_center(self):
        members, report = build_geometry(ROOT/'scratch/baseline')
        terrain=read_terrain(members['war3map.w3e'])
        self.assertEqual((terrain['width'],terrain['height']),(97,97))
        self.assertEqual(terrain['origin'],(-6144,-6144))
        self.assertEqual(len(report['routes']),5)
        self.assertTrue(all(r['spawn_to_center_connected'] for r in report['routes']))
        self.assertTrue('war3mapMap.tga' in members)
        self.assertEqual(struct.unpack_from('<HH',members['war3mapMap.tga'],12),(256,256))
        self.assertNotEqual(members['war3mapMap.blp'],(ROOT/'scratch/baseline/war3mapMap.blp').read_bytes() if (ROOT/'scratch/baseline/war3mapMap.blp').exists() else b'')

    def test_terrain_uses_original_materials_and_height_variation(self):
        members,_=build_geometry(ROOT/'scratch/baseline')
        original=read_terrain((ROOT/'scratch/baseline/war3map.w3e').read_bytes())
        current=read_terrain(members['war3map.w3e'])
        original_tiles={r[i+4]&15 for r in original['rows'] for i in range(0,len(r),7)}
        current_tiles={r[i+4]&15 for r in current['rows'] for i in range(0,len(r),7)}
        self.assertTrue(current_tiles<=original_tiles)
        self.assertIn(6,current_tiles)
        heights={struct.unpack_from('<H',r,i)[0] for r in current['rows'] for i in range(0,len(r),7)}
        self.assertGreater(len(heights),10)

    def test_shop_landings_are_flat_and_decorations_keep_elevation(self):
        from tools.radial_stage import shop_point
        from tools.map_layout import read_doodads
        members,_=build_geometry(ROOT/'scratch/baseline')
        t=read_terrain(members['war3map.w3e'])
        for lane in range(5):
            for kind in range(3):
                x,y=shop_point(lane,kind);ix=round((x+6144)/128);iy=round((y+6144)/128)
                for row in range(iy-1,iy+2):
                    for col in range(ix-1,ix+2):
                        ground,water,flags,var,cliff=struct.unpack_from('<HHBBB',t['rows'][row],col*7)
                        self.assertEqual((ground,cliff&15),(8192,2),(lane,kind,row,col))
        raised=[struct.unpack_from('<f',r,16)[0] for r in read_doodads(members['war3map.doo'])['records'] if r[:4]==b'D008']
        self.assertEqual(len(raised),5)
        self.assertTrue(all(z>100 for z in raised))

    def test_each_lane_has_one_of_each_original_shop_type(self):
        raw=read_member(ROOT/'maps/MJ5-ui-03.w3x','war3map.j')
        script,_,_=prepare_radial(raw,ROOT/'scratch/baseline')
        sg=functions(script.decode())['sg'][0]
        lanes=[[] for _ in range(5)]
        positions=[[] for _ in range(5)]
        angles=[90,18,-54,-126,162]
        for typ,x,y in re.findall(r'CreateUnit\(Ch,\$(6E303041|6E6D726B|6E676164),(-?[0-9.]+),(-?[0-9.]+),',sg):
            angle=math.degrees(math.atan2(float(y),float(x)))
            lane=min(range(5),key=lambda i:abs((angle-angles[i]+180)%360-180))
            lanes[lane].append(typ)
            positions[lane].append((float(x),float(y)))
        for shops in lanes:self.assertCountEqual(shops,['6E303041','6E6D726B','6E676164'])
        for points in positions:
            self.assertLessEqual(max(math.dist(a,b) for a in points for b in points),700)

    def test_actual_script_consumers_use_transformed_regions(self):
        raw=read_member(ROOT/'maps/MJ5-ui-03.w3x','war3map.j')
        script,members,report=prepare_radial(raw,ROOT/'scratch/baseline')
        f=functions(script.decode())
        self.assertEqual(f['sk'][0].count('=MJ_RadialRect('),len(REGION_LANE))
        self.assertIn('MJ_RadialAddRegion(D9,GU)',f['cv'][0])
        self.assertIn('MJ_RadialContainsUnit(',f['BOB'][0])
        self.assertIn('MJ_RadialRandomLoc(',f['BC4'][0])
        self.assertIn('MJ_RadialGroupEnum(',f['cY'][0])
        self.assertNotIn('7168.',f['main'][0])
        # The old remote fifth-house position is gone; fifth starts at the hub.
        self.assertNotIn('4096.,448.',f['sa'][0])
        self.assertIn('DefineStartLocation(9,0.0,0.0)',f['config'][0])
        self.assertGreater(len(report['static_coordinates']),150)
        self.assertIn('call ExecuteFunc("BP0")',f['BUK'][0])
        self.assertEqual([float(v) for v in re.search(r'set Bu=Rect\(([^)]+)\)',f['sk'][0])[1].split(',')],[-384,-3408,384,-2992])
        self.assertIn('MJ_ClearSelectionDisplay(GetEnumUnit())',f['uZ'][0])
        self.assertIn('MJ_ClearSelectionDisplay(GetEnumUnit())',f['v6'][0])
        for creator in ['tc','to']:
            self.assertIn('GroupAddUnit(MJ_SelectionDisplays,Gj)',f[creator][0])
        grid=members['war3map.wpm'][16:];connected=reachable(grid)
        self.assertNotIn(path_index(0,-3200),connected)
        self.assertEqual(grid[path_index(0,-3200)],0)
        spawn_radii=[]
        for name in ['BY','BZ','Ba','Bb','MJ5_BZ']:
            args=[float(x) for x in re.search('set '+name+r'=MJ_RadialRect\(([^)]+)\)',f['sk'][0])[1].split(',')]
            x0,y0,x1,y1,a,b,c,d=args;u=(x0+x1)/2;v=(y0+y1)/2
            spawn_radii.append(math.hypot(a*u+b*v,c*u+d*v))
        self.assertLess(max(spawn_radii)-min(spawn_radii),0.01)
