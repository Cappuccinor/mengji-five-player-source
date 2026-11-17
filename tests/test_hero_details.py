import ast
from pathlib import Path
import re
import unittest
from tools import hero_catalog as catalog
from tools.patching import functions
from tests.jass_subset import execute

ROOT=Path(__file__).resolve().parents[1]

class HeroDetailsTests(unittest.TestCase):
    def test_generated_pages_reassemble_every_complete_description(self):
        heroes=catalog.build_catalog(ROOT/'scratch/extracted')
        emitted=catalog.emit_metadata_jass(heroes)
        pages={int(i):ast.literal_eval(s).replace('|n','\n') for i,s in re.findall(r'set MJ_HeroDetailPages\[(\d+)\]=(.*)',emitted)}
        starts={int(i):int(v) for i,v in re.findall(r'set MJ_HeroDetailStart\[(\d+)\]=(\d+)',emitted)}
        counts={int(i):int(v) for i,v in re.findall(r'set MJ_HeroDetailCount\[(\d+)\]=(\d+)',emitted)}
        self.assertEqual(len(starts),158)
        for i,h in enumerate(heroes):
            expected=h['description']+''.join('\n'+s['name']+': '+(s['description'] or '原对象未提供完整说明') for s in h['skills'])
            actual=[pages[j] for j in range(starts[i],starts[i]+counts[i])]
            self.assertEqual(''.join(actual),expected,h['id'])
            self.assertTrue(all(len(p)<=180 and p.count('\n')<=5 for p in actual))
        self.assertLess(len(pages),8192)
        self.assertEqual((ROOT/'src/hero_metadata.j').read_text(encoding='utf8'),emitted)

    def test_color_codes_are_removed_before_unicode_paging(self):
        self.assertEqual(catalog.clean('|Cff00ff00中文|R|cffffffff说明|r'), '中文说明')

    def test_object_control_bytes_never_enter_generated_script(self):
        heroes=catalog.build_catalog(ROOT/'scratch/extracted')
        emitted=catalog.emit_metadata_jass(heroes)
        self.assertEqual([ord(c) for c in emitted if ord(c)<32 and c not in '\t\n\r'],[])
        self.assertEqual(catalog.clean('甲\x13乙\x0e丙\x04丁|n说明'),'甲乙丙丁\n说明')
        heroes[0]['icon']='icon\x00path'
        self.assertNotIn('\x00',catalog.emit_metadata_jass(heroes))

    def test_build_checker_rejects_binary_control_text_even_if_pjass_accepts_it(self):
        import tempfile
        from tools.check_jass import check_jass
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as folder:
            path=Path(folder)/'bad.j'
            path.write_text('function main takes nothing returns nothing\ncall BJDebugMsg("bad\x04text")\nendfunction\n',encoding='utf8')
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertFalse(result['passed'])
            self.assertIn('control byte',result['output'])

    def test_unicode_and_empty_pages(self):
        self.assertTrue(hasattr(catalog,'detail_pages'))
        for text in ['', '中文😀。'*200, '\n'*30, 'x'*2000]:
            pages=catalog.detail_pages(text)
            self.assertEqual(''.join(pages),text)
            self.assertGreaterEqual(len(pages),1)
            self.assertTrue(all(len(p)<=180 and p.count('\n')<=5 for p in pages))

    def test_actual_jass_local_paging_bounds_and_preview_reset(self):
        ui=(ROOT/'src/hero_ui.j').read_text(encoding='utf8')
        f=functions(ui)
        required=['MJ_RenderHeroDetail','MJ_OnDetailPrevious','MJ_OnDetailNext','MJ_OnHeroPreview']
        for name in required: self.assertIn(name,f)
        code='globals\ninteger MJ_LocalPreview=-1\ninteger MJ_LocalDetailPage=0\nendglobals\n'+''.join(f[n][0] for n in required)
        env=execute(code); rendered=[]
        env.update(MJ_HeroCount=2,MJ_HeroDetailStart={0:0,1:3},MJ_HeroDetailCount={0:3,1:1},
                   MJ_HeroDetailPages={0:'甲',1:'乙',2:'丙',3:'丁'},MJ_HeroNames={0:'一',1:'二'},
                   MJ_UIDetail=10,MJ_UIDetailPage=11,MJ_UIFrames=12,
                   GetLocalPlayer=lambda:0,DzGetTriggerUIEventPlayer=lambda:0,
                   DzGetTriggerUIEventFrame=lambda:1,LoadInteger=lambda *args:1,
                   I2S=str,DzFrameSetText=lambda f,t:rendered.append((f,t)))
        env['MJ_OnDetailNext'](); self.assertEqual(env['MJ_LocalPreview'],-1)
        env['MJ_OnHeroPreview'](); self.assertEqual(env['MJ_LocalDetailPage'],0)
        for _ in range(10): env['MJ_OnDetailNext']()
        self.assertEqual(env['MJ_LocalDetailPage'],2)
        self.assertIn((10,'|cff55ccff一|r|n丙'),rendered)
        env['DzGetTriggerUIEventPlayer']=lambda:1
        env['MJ_OnDetailPrevious'](); self.assertEqual(env['MJ_LocalDetailPage'],2)
        env['DzGetTriggerUIEventPlayer']=lambda:0
        for _ in range(10): env['MJ_OnDetailPrevious']()
        self.assertEqual(env['MJ_LocalDetailPage'],0)
        env['MJ_OnDetailNext']()
        env['LoadInteger']=lambda *args:2
        env['MJ_OnHeroPreview'](); self.assertEqual(env['MJ_LocalDetailPage'],0)
        env['MJ_OnDetailNext'](); self.assertEqual(env['MJ_LocalDetailPage'],0)
        for name in required:
            self.assertNotIn('DzSyncData',f[name][0])
            self.assertNotIn('CreateUnit',f[name][0])
        for name in ['MJ_OnDetailPrevious','MJ_OnDetailNext']:
            self.assertIn('function '+name+',false)',ui)
