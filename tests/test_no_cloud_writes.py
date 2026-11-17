import importlib
from pathlib import Path
import re
import tempfile
import unittest
from tools.layout_stage import prepare_layout
from tools.player_stage import prepare_players,calls
from tools.lane_stage import prepare_lane
from tools.object_stage import prepare_object_script
from tools.combat_stage import prepare_combat
from tools.selection_stage import prepare_selection
from tools.patching import functions
from tools.check_jass import check_jass
from tests.progress_harness import progress_environment

ROOT=Path(__file__).resolve().parents[1]

class PlatformStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m,_=prepare_layout(ROOT/'scratch/baseline');s,_=prepare_players(m['war3map.j']);s,_=prepare_lane(s);s,_=prepare_object_script(s);cls.before,_=prepare_combat(s)

    def stage(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.platform_stage'),'isolated platform stage missing')
        return importlib.import_module('tools.platform_stage')

    def output(self):
        script,report=self.stage().prepare_platform(self.before)
        return script,functions(script.decode()),report

    def test_all_original_cloud_write_and_purchase_consumption_calls_are_gone(self):
        script,f,report=self.output();text=script.decode()
        for native in ['DzAPI_Map_SaveServerValue','DzAPI_Map_GetServerValue','DzAPI_Map_Stat_SetStat','DzAPI_Map_Ladder_SetStat','DzAPI_Map_Ladder_SetPlayerStat']:
            self.assertEqual(list(calls(text,native)),[],native)
        for _,_,args in calls(text,'RequestExtraBooleanData'):
            self.assertNotIn(args.split(',',1)[0],['34','42'])
        self.assertEqual(len(list(calls(text,'EXExecuteScript'))),29)
        self.assertFalse(report['runtime_verified'])

    def test_both_original_storage_interfaces_share_the_new_progress(self):
        _,f,_=self.output()
        names=['MJ_InitProgressSchema']+[name for name in f if name.startswith('MJ_') and ('Progress' in name or name in ['MJ_GetInt','MJ_SetInt','MJ_GetBool','MJ_SetBool','MJ_GetString','MJ_SetString','MJ_HexDigit'])]
        names=list(dict.fromkeys(names))
        # Full schema/core globals plus patched wrapper bodies, excluding UI/gameplay natives.
        src=(ROOT/'src/progress_schema.j').read_text(encoding='utf8')+(ROOT/'src/progress.j').read_text(encoding='utf8')
        src+=''.join(f[n][0] for n in ['TT','TU','TY','TZ','Ta','Tg','mp','mr','ms'])
        e=progress_environment(src);e['TT'](5,'SCORE',123);self.assertEqual(e['TU'](5,'SCORE'),123)
        e['ms'](5,'SLD[0]','0'*63);self.assertEqual(e['mr'](5,'SLD[0]'),'0'*63)
        e['TY'](5,'LWJT',True);self.assertTrue(e['TZ'](5,'LWJT'))
        self.assertEqual(e['TU'](0,'SCORE'),0)
        e['Tg'](5,'ISCORE');self.assertEqual(e['TU'](5,'SCORE'),0)

    def test_combined_selection_progress_script_compiles(self):
        script,_,_=self.output();final,_,_=prepare_selection(script)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j';path.write_bytes(final)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])

    def test_changed_or_repeated_stage_input_is_rejected(self):
        stage=self.stage()
        with self.assertRaises(ValueError):stage.prepare_platform(self.before.replace(b'set GH="I"+GH',b'set GH="X"+GH',1))
        script,_=stage.prepare_platform(self.before)
        with self.assertRaises(ValueError):stage.prepare_platform(script)

    def test_packaged_checkpoint_has_standalone_progress_and_no_original_cloud_calls(self):
        from tools.build_checkpoint import build_checkpoint
        from tools.archive import read_member
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            target=Path(tmp)/'standalone.w3x';report=build_checkpoint(ROOT/'inputs/original.w3x',target)
            self.assertIn('platform',report)
            script=read_member(target,'war3map.j').decode()
            for native in ['DzAPI_Map_SaveServerValue','DzAPI_Map_GetServerValue','DzAPI_Map_Stat_SetStat','DzAPI_Map_Ladder_SetStat','DzAPI_Map_Ladder_SetPlayerStat']:
                self.assertEqual(list(calls(script,native)),[])
            self.assertIn('MJ_OnProgressChat',functions(script))

    def test_old_reset_timer_no_longer_erases_mastery_and_normal_mastery_summary_survives(self):
        from tests.combat_harness import run_functions
        _,f,_=self.output();destroyed=[];flushed=[]
        e=run_functions(f['t7'][0]);e.update(EK=1,GetExpiredTimer=lambda:88,GetHandleId=lambda h:h,
            FlushChildHashtable=lambda table,p:flushed.append(p),DestroyTimer=lambda t:destroyed.append(t))
        e['t7']();self.assertEqual(destroyed,[88]);self.assertEqual(flushed,[88])
        e=run_functions(f['un'][0]);values={0x312C4181:158,0xD3FCBFB3:500,0xB6EBBBCC:500,0xB3C7E815:500,0x124BD03A:1,0x46651AD3:2,0xFC60C5BC:3};summary={}
        def save(table,parent,key,value):
            if table==1:values[key]=value
            else:summary[parent,key]=value
        e.update(EK=1,DI=2,GetExpiredTimer=lambda:88,GetHandleId=lambda h:h,
            LoadInteger=lambda t,p,k:values.get(k,0),SaveInteger=save,LoadPlayerHandle=lambda *a:5,
            FlushChildHashtable=lambda *a:None,DestroyTimer=lambda *a:None)
        e['un']();self.assertEqual(summary[5,0xF96A1C62],500);self.assertEqual(summary[5,0xC40625EA],500)

    def test_pending_menu_click_is_redisplayed_and_restored_difficulty_gets_grace(self):
        from tests.combat_harness import run_functions
        _,f,_=self.output();shown=[];timers=[]
        e=run_functions(f['ti'][0]);e.update(EK=1,Fq=22,GetHandleId=lambda h:h,GetTriggeringTrigger=lambda:3,
            LoadInteger=lambda *a:0,MJ_AnyProgressImportPending=lambda:True,GetTriggerPlayer=lambda:5,
            DisplayTimedTextToPlayer=lambda *a:None,DialogDisplayBJ=lambda *a:shown.append(a))
        e['ti']();self.assertEqual(shown,[(True,22,5)])
        e=run_functions('globals\nboolean MJ_ProgressDifficultyGrace=false\nendglobals\n'+f['s1'][0]);e.update(MJ_AllHeroMode=False,DI=1,GM=2,MJ_ProgressDifficultyGrace=True,
            MJ_AnyProgressImportPending=lambda:False,IsTriggerEnabled=lambda t:True,
            StringHash=lambda s:s,LoadInteger=lambda *a:0,GetExpiredTimer=lambda:7,
            TimerStart=lambda *a:timers.append(a))
        e['s1']();self.assertFalse(e['MJ_ProgressDifficultyGrace']);self.assertEqual(timers[0][:3],(7,20.,False))
