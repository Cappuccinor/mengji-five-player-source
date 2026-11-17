import re
import unittest
from collections import defaultdict
from tests import test_free_rules
ROOT=test_free_rules.ROOT
from tests.progress_harness import progress_environment
from tools.progress_schema import progress_module
from tools.archive import read_member
from tools.object_stage import prepare_objects
from tools.free_objects_stage import prepare_free_objects

class PaidAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_free_rules.FreeStageTests.setUpClass()
        from tools.free_stage import prepare_free
        from tools.patching import functions
        cls.f=functions(prepare_free(test_free_rules.FreeStageTests.before)[0].decode())

    def environment(self,body):
        e=progress_environment(progress_module()+(ROOT/'src/free_rules.j').read_text(encoding='utf8')+(ROOT/'src/local_account_rules.j').read_text(encoding='utf8')+body)
        real={}
        e.update(DI={},EK={},Fa=1,Fu={},HQ={p:100+p for p in [0,1,2,3,5]},MJ_FreePhase=1,
            IsPlayerInForce=lambda p,f:p in [0,1,2,3,5], GetHandleId=lambda x:x,GetPlayerId=lambda p:p,
            LoadReal=lambda t,p,k:real.get((p,k),0.),SaveReal=lambda t,p,k,v:real.__setitem__((p,k),v),
            GetPlayerController=lambda p:1,MAP_CONTROL_USER=1,GetPlayerSlotState=lambda p:1,PLAYER_SLOT_STATE_PLAYING=1,
            GetPlayerName=lambda p:'player',SetPlayerName=lambda *a:None,
            GetPlayerHandicapXPBJ=lambda p:100,SetPlayerHandicapXPBJ=lambda *a:None,
            SetPlayerAbilityAvailable=lambda *a:None,AdjustPlayerStateBJ=lambda *a:None,
            PLAYER_STATE_RESOURCE_GOLD=0,SetPlayerTechMaxAllowedSwap=lambda *a:None,
            EnableTrigger=lambda *a:None,In=1,SetPlayerStateBJ=lambda *a:None,PLAYER_STATE_RESOURCE_LUMBER=1,PLAYER_STATE_RESOURCE_FOOD_CAP=2,PLAYER_STATE_RESOURCE_FOOD_USED=3,
            r4=lambda p,key,i:False,r5=lambda *a:None,TU=lambda p,key:e['MJ_GetInt'](p,key),
            TT=lambda p,key,v:e['MJ_SetInt'](p,key,v),TZ=lambda p,key:False)
        return e

    def test_zero_progress_paid_ui_dependencies_reached_for_each_human(self):
        e=self.environment(self.f['MJ_ApplyFreeEffects'][0]);tech={};availability={}
        e['SetPlayerAbilityAvailable']=lambda p,code,on:availability.__setitem__((p,code),on)
        e['SetPlayerTechResearchedSwap']=lambda code,level,p:tech.__setitem__((p,code),level)
        for p in [0,1,2,3,5]:
            e['MJ_ApplyFreeEffects'](p)
            for code,level in [('R008',3),('R006',1),('R00I',2),('R000',1),('R002',1),('R005',1),('R00J',1),('R00K',1),('R00P',1)]:
                self.assertGreaterEqual(tech.get((p,int.from_bytes(code.encode(),'big')),0),level,(p,code))
            for code in ['A01G','A01H','A01I','A0O4']:
                self.assertTrue(availability.get((p,int.from_bytes(code.encode(),'big')),True),(p,code))
            for key in ['GGC','HFS','GG','TGDS','DS100']:
                self.assertEqual(e['MJ_GetInt'](p,key),0,key)
            for code in ['R00B','R00E','R00G','R00O','R001','R009','R00D','R00L']:
                self.assertNotIn((p,int.from_bytes(code.encode(),'big')),tech)

    def test_paid_tooltips_no_longer_demand_purchases_and_growth_requires_survive(self):
        before,_=prepare_objects(ROOT/'inputs/original.w3x'); patched,_=prepare_free_objects(before)
        text=patched.get(r'Units\CampaignAbilityStrings.txt',before[r'Units\CampaignAbilityStrings.txt']).decode('utf8')
        self.assertFalse('在平台商城购买永久解锁' in text)
        self.assertFalse('购买商城内所有道具后自动激活' in text)
        self.assertFalse('打赏活动专属' in text)
        for key in ['A05L','A0CA','A099','A0N8']:
            section=lambda t:re.search(r'^\['+key+r'\]\r?\n.*?(?=^\[|\Z)',t,re.M|re.S)[0]
            self.assertEqual(section(text),section(before[r'Units\CampaignAbilityStrings.txt'].decode('utf8')))


    def test_equipping_paid_mount_wing_title_replaces_previous_effect_once(self):
        for name,spells,field,expected in [
            ('BR9',['A0LW','A0O4','A0LW'],0x23C06BBA,[.08,.07,.08]),
            ('BSN',['A0CC','A0CE','A0CC'],0xF0BCBFE,[.14,.05,.14]),
            ('BSQ',['A0LX','A0AN','A0LX'],0xFF8B58BE,[.5,.3,.5]),
        ]:
            e=self.environment(self.f[name][0]);spell=[0];removed=[];created=[];abilities=set()
            e.update(GetTriggerUnit=lambda:105,GetOwningPlayer=lambda u:5,GetSpellAbilityId=lambda:spell[0],
                GetPlayerName=lambda p:'player',LoadTimerHandle=lambda *a:1,PauseTimer=lambda *a:None,
                UnitRemoveAbility=lambda u,a:abilities.discard(a),UnitAddAbility=lambda u,a:abilities.add(a),
                SetUnitFlyHeight=lambda *a:None,IssueImmediateOrder=lambda *a:None,
                DisplayTextToPlayer=lambda *a:None,DestroyEffect=lambda h:removed.append(h),
                LoadEffectHandle=lambda t,p,k:e['LoadInteger'](t,p,k),
                SaveEffectHandle=lambda t,p,k,v:e['SaveInteger'](t,p,k,v),
                sR=lambda *a:created.append(a),bj_lastCreatedEffect=999)
            e['SaveStr'](e['DI'],5,0xC5531991,'player')
            for code,value in zip(spells,expected):
                spell[0]=int.from_bytes(code.encode(),'big');e[name]()
                self.assertAlmostEqual(e['LoadReal'](e['DI'],105,field),value,(name,code))
            if name=='BR9':self.assertEqual(abilities,{0x416D7266,0x41304C59})
            if name=='BSN':self.assertEqual(len(created),3);self.assertEqual(removed,[0,999,999])
