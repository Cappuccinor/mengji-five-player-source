import math
import re
import unittest
from pathlib import Path
from tools.archive import read_member
from tools.patching import functions
from tools.radial_stage import prepare_radial

ROOT=Path(__file__).resolve().parents[1]
class VictoryLayoutTests(unittest.TestCase):
    def test_public_shop_clears_pyramid_construction_area(self):
        raw=read_member(ROOT/'maps/MJ5-ui-03.w3x','war3map.j')
        script,_,_=prepare_radial(raw,ROOT/'scratch/baseline')
        sg=functions(script.decode())['sg'][0]
        m=re.search(r'set Cr=CreateUnit\(Ch,\$6E303051,(-?[0-9.]+),(-?[0-9.]+),',sg)
        self.assertIsNotNone(m)
        x,y=map(float,m.groups())
        # BX is the authored 832x832 construction search area. Keep the
        # public shop's 4x4 (128-unit) pathing footprint outside it.
        self.assertGreaterEqual(max(abs(x),abs(y))-64,416)
        self.assertLess(math.hypot(x,y)+64,800) # accessible shared hub
