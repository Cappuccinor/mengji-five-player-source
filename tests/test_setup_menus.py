import importlib
from pathlib import Path
import unittest
from tools.patching import functions
from tools.progress_schema import progress_module
from tests.progress_harness import progress_environment
ROOT=Path(__file__).resolve().parents[1]

class SetupMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_free_rules import FreeStageTests
        FreeStageTests.setUpClass()
        from tools.free_stage import prepare_free
        from tools.selection_stage import prepare_selection
        s,_=prepare_free(FreeStageTests.before);s,_,_=prepare_selection(s);cls.f=functions(s.decode())

    def test_host_departure_reopens_each_configuration_menu_for_next_present_human(self):
        self.assertTrue('MJ_ReopenConfigMenus' in self.f,'menu migration helper missing')
        for enabled in [10,11,12]:
            code=progress_module()+''.join(self.f[n][0] for n in ['MJ_SelectionHost','MJ_BuildDifficultyMenu','MJ_RefreshProgressDifficulty','MJ_ReopenConfigMenus','BOK'] if n in self.f)
            e=progress_environment(code);humans={0,1,2,3,5};shown=[];buttons=[]
            e.update(EK={},DI={},Fa=1,GM=10,GJ=11,Gg=12,Fq=2,GI={},MJ_AllHeroMode=False,MJ_FreePhase=0,
                GetTriggerPlayer=lambda:0,GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,
                MJ_IsActive=lambda i:[0,1,2,3,5][i] in humans,
                IsPlayerInForce=lambda p,f:p in humans,ForceRemovePlayer=lambda f,p:humans.discard(p),
                IsTriggerEnabled=lambda t:t==enabled,CountPlayersInForceBJ=lambda f:len(humans),
                DialogDisplayBJ=lambda show,d,p:shown.append((show,d,p)),DialogClear=lambda d:buttons.clear(),
                DialogSetMessage=lambda *a:None,DialogAddButtonBJ=lambda d,t:buttons.append(t),
                GetLastCreatedButtonBJ=lambda:len(buttons),EnableTrigger=lambda t:None)
            e['BOK']()
            self.assertEqual(shown,[(True,2,1)]);self.assertNotIn(0,humans)
            if enabled==10:self.assertEqual(set(e['GI']),{1,2,3,4,5,6,7,8,10,96})

    def test_restoring_current_host_progress_after_red_departure_refreshes_that_host_menu(self):
        self.assertTrue('MJ_ReopenConfigMenus' in self.f,'menu migration helper missing')
        f=self.f;code=progress_module()+''.join(f[n][0] for n in ['MJ_SelectionHost','MJ_BuildDifficultyMenu','MJ_RefreshProgressDifficulty'] if n in f)
        e=progress_environment(code);shown=[]
        e.update(GM=10,Fq=2,Fa=1,DI={},GI={},MJ_IsActive=lambda i:i==4,
            IsPlayerInForce=lambda p,f:p==5,IsTriggerEnabled=lambda t:True,
            CountPlayersInForceBJ=lambda f:1,DialogClear=lambda d:None,DialogSetMessage=lambda *a:None,
            DialogAddButtonBJ=lambda *a:None,GetLastCreatedButtonBJ=lambda:1,EnableTrigger=lambda t:None,
            DialogDisplayBJ=lambda show,d,p:shown.append(p))
        e['MJ_RefreshProgressDifficulty'](5);self.assertEqual(shown,[5])

    def test_fresh_and_restored_progress_show_same_full_difficulty_menu(self):
        s2=self.f['s2'][0]
        # Execute the real initial-menu branch independently of world setup natives.
        start=s2.rindex('call DialogClear(Fq)') if 'call MJ_BuildDifficultyMenu()' not in s2 else s2.index('call MJ_BuildDifficultyMenu()')
        end=s2.index('call DialogDisplayBJ(true,Fq,MJ_SelectionHost())',start)+len('call DialogDisplayBJ(true,Fq,MJ_SelectionHost())')
        initial='function InitialMenu takes nothing returns nothing\n'+s2[start:end]+'\nendfunction\n'
        code=progress_module()+''.join(self.f[n][0] for n in ['MJ_SelectionHost','MJ_BuildDifficultyMenu','MJ_RefreshProgressDifficulty'] if n in self.f)+initial
        for count in [1,2,5]:
            e=progress_environment(code);buttons=[];shown=[]
            e.update(GM=10,Fq=2,Fa=1,DI={},GI={},MJ_IsActive=lambda i:i==0,
                IsPlayerInForce=lambda p,f:p==0,IsTriggerEnabled=lambda t:True,
                CountPlayersInForceBJ=lambda f:count,DialogClear=lambda d:buttons.clear(),
                DialogSetMessage=lambda *a:None,DialogAddButtonBJ=lambda d,t:buttons.append(t),
                GetLastCreatedButtonBJ=lambda:len(buttons),EnableTrigger=lambda t:None,
                DialogDisplayBJ=lambda show,d,p:shown.append(p))
            e['TU']=e['MJ_GetInt']
            for progress in [0,1,5,10]:
                e['MJ_SetInt'](0,'GG',progress)
                for menu in ['InitialMenu','MJ_RefreshProgressDifficulty']:
                    e['GI']={}
                    e[menu](*([0] if menu=='MJ_RefreshProgressDifficulty' else []))
                    expected={1,2,3,4,5,6,7,8,10}|({96} if count>1 else set())
                    self.assertEqual(set(e['GI']),expected,(count,progress,menu))
                    self.assertEqual(e['MJ_GetInt'](0,'GG'),progress)
                self.assertEqual(shown[-2:],[0,0])

    def test_mode_choices_do_not_require_prior_clearance(self):
        for name in ['s2','tQ']:
            self.assertNotIn('"GG")>=1 and LoadBoolean',self.f[name][0])
            self.assertIn('$9D29CC1F)==false',self.f[name][0])
        self.assertIn('$9DBE7FC4)==false',self.f['tQ'][0])
