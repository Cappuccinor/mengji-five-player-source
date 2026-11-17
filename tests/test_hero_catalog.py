import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
EXTRACTED=ROOT/'scratch/extracted'


class CatalogTests(unittest.TestCase):
    def test_all_pool_heroes_have_identity_icon_and_skill_metadata(self):
        if importlib.util.find_spec('tools.hero_catalog') is None:
            self.fail('Hero catalog generator is missing')
        from tools.hero_catalog import build_catalog
        heroes=build_catalog(EXTRACTED)
        ids=[h['id'] for h in heroes]
        self.assertEqual(len(ids),158)
        self.assertEqual(len(set(ids)),158)
        self.assertEqual(ids.count('U00S'),1)
        author=next(h for h in heroes if h['id']=='U00S')
        self.assertEqual(author['name'],'地图作者')
        for h in heroes:
            self.assertTrue(h['name'],h['id'])
            self.assertTrue(h['icon'],h['id'])
            self.assertIn('skills',h)
            self.assertEqual(h['rawcode'],int.from_bytes(h['id'].encode('ascii'),'big'))

    def test_generated_catalog_initializes_real_jass_core(self):
        if importlib.util.find_spec('tools.hero_catalog') is None:
            self.fail('Hero catalog generator is missing')
        from tools.hero_catalog import build_catalog,emit_ids_jass
        from tests.jass_subset import execute
        heroes=build_catalog(EXTRACTED)
        core=(ROOT/'src/selection_state.j').read_text(encoding='utf8')
        env=execute(core+emit_ids_jass(heroes))
        env['MJ_InitHeroIds']()
        self.assertEqual(env['MJ_HeroCount'],158)
        self.assertTrue(env['MJ_IsHero'](int.from_bytes(b'U00S','big')))
        self.assertFalse(env['MJ_IsHero'](int.from_bytes(b'zzzz','big')))
