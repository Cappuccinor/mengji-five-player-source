"""Remaining full-script player predicates, using actual patched JASS bodies."""
import importlib.util
from pathlib import Path
import re
import unittest
from tests.progress_harness import progress_environment
from tools.patching import functions

ROOT=Path(__file__).resolve().parents[1]

class GameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_free_rules import FreeStageTests
        FreeStageTests.setUpClass()
        from tools.free_stage import prepare_free
        cls.before,_=prepare_free(FreeStageTests.before)

    def output(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.gameplay_stage'),'remaining gameplay stage missing')
        from tools.gameplay_stage import prepare_gameplay
        s,r=prepare_gameplay(self.before);return s,functions(s.decode()),r

    def test_actual_death_filter_handles_all_five_and_rejects_cross_illusions_and_eliminated_players(self):
        _,f,_=self.output();e=progress_environment(f['x2'][0]);owner=[5];cross=[False];illusion=[False];active=[True]
        e.update(Fa=1,HQ={i:100+i for i in [0,1,2,3,5]},GetDyingUnit=lambda:100+owner[0],
            GetOwningPlayer=lambda u:owner[0],GetPlayerId=lambda p:p,MJ_Index=lambda p:{0:0,1:1,2:2,3:3,5:4}.get(p,-1),
            MJ_IsActive=lambda i:active[0],IsUnitType=lambda *a:True,UNIT_TYPE_HERO=1,
            IsPlayerInForce=lambda *a:active[0],IsUnitInForce=lambda *a:active[0],
            cx=lambda *a:cross[0],IsUnitIllusionBJ=lambda u:illusion[0])
        for p in [0,1,2,3,5]:
            owner[0]=p;self.assertTrue(e['x2']())
            cross[0]=True;self.assertFalse(e['x2']());cross[0]=False
            illusion[0]=True;self.assertFalse(e['x2']());illusion[0]=False
            active[0]=False;self.assertFalse(e['x2']());active[0]=True
        owner[0]=4;self.assertFalse(e['x2']())

    def test_global_failure_ends_every_active_human_in_each_result_branch(self):
        _,f,_=self.output();module=(ROOT/'src/gameplay.j').read_text(encoding='utf8')
        for mode in range(4):
            e=progress_environment(module+f['BR6'][0]);ended=[]
            e.update(EK={},DI={},Fa=1,GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,
                BO=1,j=1,n=1,BK=1,BL=1,GX=1,HV=1,K2=1,K1=1,Ja=1,JY=1,JW=1,Ld=1,CP=1,Jf=1,
                bj_lastCreatedEffect=1,CAMERA_FIELD_ROTATION=1,GetPlayableMapRect=lambda:1,
                Condition=lambda f:f,LoadGroupHandle=lambda *a:1,cY=lambda *a:1,LoadUnitHandle=lambda *a:1,
                IsUnitAliveBJ=lambda u:True,BR3=lambda:None,BR4=lambda:None,BR5=lambda:None,
                MJ_Player=lambda i:[0,1,2,3,5][i],MJ_IsActive=lambda i:True,IsPlayerInForce=lambda p,f:True,
                CustomDefeatBJ=lambda p,msg:ended.append(p),LoadStr=lambda t,p,k:t.get(('str',p,k),''))
            for native in re.findall(r'^call (\w+)\(',f['BR6'][0],re.M):
                if native not in e:e[native]=lambda *a:None
            if mode==0:e['SaveInteger'](e['DI'],'全局',0xEEFCB876,10)
            if mode==1:e['SaveBoolean'](e['DI'],'全局',0x9D29CC1F,True)
            if mode==2:e['SaveBoolean'](e['DI'],'全局',0x88CEC9C2,True)
            e['BR6']();self.assertEqual(ended,[0,1,2,3,5],mode)

    def test_global_failure_also_ends_online_spectator_who_left_combat_force(self):
        module=(ROOT/'src/gameplay.j').read_text(encoding='utf8');e=progress_environment(module);ended=[]
        e.update(Fa=1,IsPlayerInForce=lambda p,f:p in [0,1,2,3],MJ_IsActive=lambda i:True,
            MJ_Player=lambda i:[0,1,2,3,5][i],CustomDefeatBJ=lambda p,msg:ended.append(p))
        e['MJ_DefeatActivePlayers']('end');self.assertEqual(ended,[0,1,2,3,5])
