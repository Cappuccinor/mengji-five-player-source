import importlib
from pathlib import Path
import unittest
from tests.progress_harness import progress_environment
from tools.progress_schema import progress_module

ROOT=Path(__file__).resolve().parents[1]
TAGS=['VIP0','VIP1','VIP2','VIP3','PTLB','LWJ','S1CB','S1ZQ','S1CH','S2ZQ','TXZ','TRE','PET1','PET2','IMBAG','3FJT','BOOKD','BOOKC','BOOKB','BOOKA','BAG3','TXCH1','ZBQ1','JBLB','MCLB','S2CH']

class FreeRulesTests(unittest.TestCase):
    def environment(self):
        path=ROOT/'src/free_rules.j';self.assertTrue(path.exists(),'explicit free rules missing')
        e=progress_environment(progress_module()+path.read_text(encoding='utf8'))
        e.update(Fa=1,IsPlayerInForce=lambda p,f:p in [0,1,2,3,5],GetHandleId=lambda h:h)
        return e

    def test_known_free_content_available_to_all_five_but_unknown_and_npc_rejected(self):
        e=self.environment()
        for p in [0,1,2,3,5]:
            for tag in TAGS:self.assertTrue(e['MJ_ContentAvailable'](p,tag),(p,tag))
        for p in [4,6,7]:self.assertFalse(e['MJ_ContentAvailable'](p,'VIP1'))
        self.assertFalse(e['MJ_ContentAvailable'](0,'UNREVIEWED'))
        e['MJ_FreeVipPreset']=1
        self.assertTrue(e['MJ_ContentAvailable'](5,'VIP1'));self.assertFalse(e['MJ_ContentAvailable'](5,'VIP2'))

    def test_source_claims_are_once_per_player_and_run_and_never_during_selection(self):
        e=self.environment()
        self.assertFalse(e['MJ_ClaimReward'](5,'BOOKC'))
        e['MJ_FreePhase']=1
        for p in [0,1,2,3,5]:
            for tag in ['VIP0','VIP3','BOOKD','BOOKC','BOOKB','BOOKA','BAG3','IMBAG','PTLB','3FJT']:
                self.assertTrue(e['MJ_ClaimReward'](p,tag));self.assertFalse(e['MJ_ClaimReward'](p,tag))
        self.assertFalse(e['MJ_ClaimReward'](5,'UNREVIEWED'))
        e['MJ_FreePhase']=2;self.assertFalse(e['MJ_ClaimReward'](5,'BOOKA'))

    def test_pass_requires_real_progress_and_each_tier_only_once(self):
        e=self.environment();e['MJ_FreePhase']=2
        self.assertTrue(e['MJ_ClaimPassReward'](5,0));self.assertFalse(e['MJ_ClaimPassReward'](5,0))
        for tier,points in enumerate([50,150,300,500,800,1200],1):
            e['MJ_SetInt'](5,'TGDS',points-1);self.assertFalse(e['MJ_ClaimPassReward'](5,tier))
            e['MJ_SetInt'](5,'TGDS',points);self.assertTrue(e['MJ_ClaimPassReward'](5,tier));self.assertFalse(e['MJ_ClaimPassReward'](5,tier))
        self.assertFalse(e['MJ_ClaimPassReward'](5,7));self.assertEqual(e['MJ_GetInt'](0,'TGDS'),0)
        e['MJ_FreePhase']=0;self.assertFalse(e['MJ_ClaimPassReward'](0,0))

    def test_legacy_grab_mode_first_opening_is_allowed_after_original_game_timer_starts(self):
        e=self.environment();self.assertFalse(e['MJ_BeginHeroOpening'](5))
        e['MJ_FreePhase']=2;self.assertTrue(e['MJ_BeginHeroOpening'](5))
        self.assertFalse(e['MJ_BeginHeroOpening'](5));self.assertFalse(e['MJ_BeginHeroOpening'](4))

    def test_full_set_per_hero_and_pets_keep_distinct_once_tokens(self):
        e=self.environment();e['MJ_FreePhase']=1
        self.assertTrue(e['MJ_ClaimFullSet'](5,500));self.assertFalse(e['MJ_ClaimFullSet'](5,500))
        self.assertTrue(e['MJ_ClaimFullSet'](5,501))
        self.assertTrue(e['MJ_BeginFreeHelper'](5,'PET1'));self.assertTrue(e['MJ_BeginFreeHelper'](5,'PET2'))
        self.assertFalse(e['MJ_BeginFreeHelper'](5,'PET1'));self.assertFalse(e['MJ_BeginFreeHelper'](5,'PET2'))
        self.assertEqual(e['MJ_GetInt'](5,'HFS'),0);self.assertEqual(e['MJ_GetString'](5,'SLD[0]'),'')


class FreeStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.layout_stage import prepare_layout
        from tools.player_stage import prepare_players
        from tools.lane_stage import prepare_lane
        from tools.object_stage import prepare_object_script
        from tools.combat_stage import prepare_combat
        from tools.platform_stage import prepare_platform
        m,_=prepare_layout(ROOT/'scratch/baseline');s,_=prepare_players(m['war3map.j']);s,_=prepare_lane(s)
        s,_=prepare_object_script(s);s,_=prepare_combat(s);s,_=prepare_platform(s)
        from tools.free_objects_stage import prepare_free_object_script
        cls.before,_=prepare_free_object_script(s)

    def output(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.free_stage'),'free stage missing')
        from tools.free_stage import prepare_free
        from tools.patching import functions
        s,r=prepare_free(self.before);return s,functions(s.decode()),r

    def environment(self,body):
        e=progress_environment(progress_module()+(ROOT/'src/free_rules.j').read_text(encoding='utf8')+body)
        e.update(Fa=1,IsPlayerInForce=lambda p,f:p in [0,1,2,3,5],GetHandleId=lambda h:h)
        return e

    def test_mall_calls_replaced_only_with_explicit_local_policy_and_combination_compiles(self):
        import tempfile
        from tools.player_stage import calls
        from tools.selection_stage import prepare_selection
        from tools.check_jass import check_jass
        s,f,r=self.output();self.assertEqual(list(calls(s.decode(),'DzAPI_Map_HasMallItem')),[])
        self.assertIn('MJ_ApplyFreeEffects',f);self.assertFalse(r['runtime_verified'])
        final,_,_=prepare_selection(s)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            p=Path(tmp)/'map.j';p.write_bytes(final);result=check_jass(p,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])

    def test_original_pass_handler_direct_spell_cannot_bypass_tier_or_repeat_bulk(self):
        from collections import defaultdict
        _,f,_=self.output();e=self.environment(f['BRc'][0]+f['BRd'][0]);gold=[];spell=[0x41304E41]
        e.update(EK={},DI={},HQ=defaultdict(lambda:500),MJ_FreePhase=2,GetTriggeringTrigger=lambda:7,
            GetTriggerUnit=lambda:500,GetOwningPlayer=lambda u:5,GetPlayerId=lambda p:p,
            GetSpellAbilityId=lambda:spell[0],Uo=lambda chance:False,
            UnitAddItemByIdSwapped=lambda *a:None,AdjustPlayerStateBJ=lambda amount,*a:gold.append(amount),
            DisplayTimedTextToForce=lambda *a:None,GetPlayersAll=lambda:1,GetPlayerName=lambda p:'p',
            SetPlayerAbilityAvailable=lambda *a:None,ModifyHeroStat=lambda *a:None,
            GetManipulatedItem=lambda:0,RemoveItem=lambda *a:None,
            PLAYER_STATE_RESOURCE_GOLD=1,PLAYER_STATE_RESOURCE_LUMBER=2,
            bj_HEROSTAT_INT=1,bj_HEROSTAT_AGI=2,bj_HEROSTAT_STR=3,bj_MODIFYMETHOD_ADD=1)
        e['BRd']();self.assertEqual(gold,[])
        e['MJ_SetInt'](5,'TGDS',50);spell[0]=0x41304F32;e['BRd']();self.assertEqual(gold,[1000,1500,1])
        gold.clear();e['BRd']();self.assertEqual(gold,[])
        spell[0]=0x41304D45;e['BRd']();self.assertEqual(gold,[])
        e['MJ_FreePhase']=0;self.assertFalse(e['BRc']())

    def test_original_fox_callbacks_do_not_grow_during_wait_or_off_state(self):
        _,f,_=self.output()
        for name in ['vz','v7','wI','BPk']:
            e=self.environment(f[name][0]);stats=[];alive=[True]
            e.update(EK={},DI={},HQ={5:500},GetExpiredTimer=lambda:7,LoadPlayerHandle=lambda *a:5,
                LoadUnitHandle=lambda *a:500,IsUnitAliveBJ=lambda u:alive[0],GetPlayerId=lambda p:p,
                GetPlayerSlotState=lambda p:1,PLAYER_SLOT_STATE_PLAYING=1,
                ModifyHeroStat=lambda *a:stats.append(a),LoadReal=lambda *a:0,SaveReal=lambda *a:None,
                bj_HEROSTAT_STR=1,bj_HEROSTAT_AGI=2,bj_HEROSTAT_INT=3,bj_MODIFYMETHOD_ADD=1)
            e[name]();self.assertEqual(stats,[])
            e['MJ_FreePhase']=2;e['SaveInteger'](e['DI'],5,0xE6B6E229,2);e[name]();self.assertEqual(stats,[])
            e['SaveInteger'](e['DI'],5,0xE6B6E229,0);alive[0]=False;e[name]();self.assertEqual(stats,[])
            alive[0]=True;e[name]();self.assertEqual(len(stats),3)

    def test_actual_start_benefits_create_each_pet_once_and_credit_the_enumerated_player(self):
        _,f,_=self.output();e=self.environment(f['v1'][0]);created=[];timers=[];xp=[]
        e.update(EK={},DI={},HQ={5:500},MJ_FreePhase=1,GetTriggeringTrigger=lambda:7,
            GetEnumPlayer=lambda:5,GetTriggerUnit=lambda:900,GetOwningPlayer=lambda u:0,
            GetPlayerId=lambda p:p,GetUnitTypeId=lambda u:100,ee=lambda s:0,mv=lambda *a:'',r4=lambda *a:False,
            LoadReal=lambda *a:0,SaveReal=lambda *a:None,Uo=lambda c:False,GetRandomInt=lambda a,b:a,
            AdjustPlayerStateBJ=lambda *a:None,DisplayTimedTextToPlayer=lambda *a:None,
            GetPlayerHandicapXPBJ=lambda p:100,SetPlayerHandicapXPBJ=lambda p,value:xp.append((p,value)),
            SetPlayerAbilityAvailable=lambda *a:None,LoadLocationHandle=lambda *a:0,bj_UNIT_FACING=0,
            CreateNUnitsAtLoc=lambda *a:created.append(a),fy=lambda *a:None,bj_lastCreatedUnit=600,
            SaveUnitHandle=lambda *a:None,CreateTimer=lambda:70,SavePlayerHandle=lambda *a:None,
            TimerStart=lambda *a:timers.append(a),PLAYER_STATE_RESOURCE_GOLD=1,vz=lambda:None,v0=lambda:None)
        e['v1']();e['v1']()
        self.assertEqual([args[1] for args in created],[0x65303055,0x6E303147])
        self.assertEqual(len(timers),2);self.assertEqual(xp,[(5,120.)])

    def test_initialization_chain_cannot_dispatch_twice_or_rewind_playing_phase(self):
        _,f,_=self.output();e=self.environment(f['uJ'][0]);timers=[]
        e.update(MJ_AnyProgressImportPending=lambda:False,MJ_LockProgress=lambda:None,
            CreateTimer=lambda:7,TimerStart=lambda *a:timers.append(a),GetTriggeringTrigger=lambda:9,
            DisableTrigger=lambda *a:None)
        for name in ['uB','uC','uD','uE','uF','uG','uH','uI']:e[name]=lambda:None
        e['uJ']();e['uJ']();self.assertEqual(len(timers),8);self.assertEqual(e['MJ_FreePhase'],1)
        e['MJ_FreePhase']=2;e['uJ']();self.assertEqual(e['MJ_FreePhase'],2);self.assertEqual(len(timers),8)

    def test_manual_gift_waits_for_playing_and_preserves_once_flag(self):
        _,f,_=self.output()
        e=self.environment((ROOT/'src/local_account_rules.j').read_text(encoding='utf8')+f['BQp'][0]);gold=[]
        e.update(EK={},DI={},HQ={5:99},GetTriggeringTrigger=lambda:9,
            GetSpellAbilityId=lambda:0x41304548,GetTriggerUnit=lambda:99,GetOwningPlayer=lambda u:5,
            GetPlayerId=lambda p:p,GetManipulatedItem=lambda:None,RemoveItem=lambda i:None,
            PLAYER_STATE_RESOURCE_GOLD=0,AdjustPlayerStateBJ=lambda value,p,state:gold.append((value,p)),
            bj_HEROSTAT_INT=0,bj_HEROSTAT_AGI=1,bj_HEROSTAT_STR=2,bj_MODIFYMETHOD_ADD=0,
            ModifyHeroStat=lambda *a:None,DestroyEffect=lambda *a:None,sM=lambda *a:None,
            DisplayTimedTextToPlayer=lambda *a:None,DisplayTextToPlayer=lambda *a:None,
            SetPlayerAbilityAvailable=lambda *a:None)
        for phase in [0,1]:
            e['MJ_FreePhase']=phase;e['BQp']();self.assertEqual(gold,[]);self.assertEqual(e['DI'],{})
        e['MJ_FreePhase']=2;e['BQp']();e['BQp']();self.assertEqual(gold,[(1666,5)])

    def test_grab_owner_is_captured_before_old_unit_is_removed(self):
        _,f,_=self.output();body=f['u7'][0].split('call SetUnitPositionLoc(',1)[0]+'endfunction\n'
        e=self.environment(body);removed=[False]
        def replace_unit(*args):
            removed[0]=True;e['bj_lastReplacedUnit']=600
        e.update(EK={},DI={},HQ={0:100},MJ_FreePhase=1,GetTriggeringTrigger=lambda:7,
            GetTriggerUnit=lambda:900,GetOwningPlayer=lambda u:0 if removed[0] else 5,
            GetPlayerId=lambda p:p,SaveLocationHandle=lambda *a:None,GetUnitLoc=lambda *a:0,
            LoadLocationHandle=lambda *a:0,DestroyEffect=lambda *a:None,sL=lambda *a:None,
            RemoveLocation=lambda *a:None,GetUnitTypeId=lambda *a:1,bj_UNIT_STATE_METHOD_DEFAULTS=0,
            cl=replace_unit)
        e['u7']();self.assertEqual(e['HQ'],{0:100,5:600})
