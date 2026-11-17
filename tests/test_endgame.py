"""Endgame actions executed with native doubles, not a Warcraft runtime."""
import unittest
import re
from pathlib import Path
from tools.patching import functions
from tests.progress_harness import progress_environment

ROOT=Path(__file__).resolve().parents[1]

class EndgameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_gameplay import GameplayTests
        GameplayTests.setUpClass()
        from tools.gameplay_stage import prepare_gameplay
        cls.before,_=prepare_gameplay(GameplayTests.before)

    def output(self):
        from tools.endgame_stage import prepare_endgame
        raw,_=prepare_endgame(self.before)
        return functions(raw.decode())

    def test_terminal_stops_every_phase_once(self):
        f=self.output()
        source=(ROOT/'src/endgame.j').read_text(encoding='utf8')
        e=progress_environment(source)
        disabled=[];paused=[]
        e.update(**{n:n for n in ['Ja','JY','JW','JX','JT','Fw']},DisableTrigger=disabled.append,PauseTimer=paused.append)
        self.assertTrue(e['MJ_BeginDefeat']())
        self.assertFalse(e['MJ_BeginDefeat']())
        self.assertEqual(disabled,['Ja','JY','JW','JX','JT'])
        self.assertEqual(paused,['Fw'])
        body=f['BR6'][0]
        self.assertLess(body.index('MJ_BeginDefeat'),body.index('DestroyTrigger'))

    def test_zero_survivor_branch_only_dispatches_terminal_on_empty_force(self):
        f=self.output()
        for name in ['BOb','BOi','BOp','BOw','MJ5_FailLane']:
            body=f[name][0]
            start=body.index('if CountPlayersInForceBJ(Fa)==0 then')
            end=body.index('call PlaySoundBJ(k)',start)
            branch=body[start:end]+'call RecordWinner()\nendif\n'
            for count in [0,1,2,4,5]:
                e=progress_environment('function test takes nothing returns nothing\n'+branch+'endfunction\n')
                events=[]
                e.update(Fa=1,K4=4,CountPlayersInForceBJ=lambda _:count,EnableTrigger=lambda t:events.append('enable'),
                         TriggerExecute=lambda t:events.append('defeat'),RecordWinner=lambda:events.append('winner'))
                e['test']()
                self.assertEqual(events,['enable','defeat'] if count==0 else ['winner'] if count==1 else [],(name,count))

    def test_boss_transition_and_victory_unchanged(self):
        f=self.output();before=functions(self.before.decode())
        self.assertEqual(f['BR1'][0],before['BR1'][0])
        self.assertEqual(f['BQU'][0],before['BQU'][0])

    def test_reapplication_rejected(self):
        from tools.endgame_stage import prepare_endgame
        raw,_=prepare_endgame(self.before)
        with self.assertRaises(ValueError):prepare_endgame(raw)

    def test_actual_terminal_body_defeats_online_roster_once_in_each_mode(self):
        f=self.output()
        module=(ROOT/'src/endgame.j').read_text(encoding='utf8')+(ROOT/'src/gameplay.j').read_text(encoding='utf8')
        for roster in [[0,1,2,3,5],[5],[0],[]]:
            for mode in range(4):
                e=progress_environment(module+f['BR6'][0]);ended=[];paused=[]
                e.update(EK={},DI={},Fa=1,GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,
                    **{n:n for n in ['BO','j','n','BK','BL','GX','HV','K2','K1','Ja','JY','JW','JX','JT','Fw','Ld','CP','Jf']},
                    bj_lastCreatedEffect=1,CAMERA_FIELD_ROTATION=1,GetPlayableMapRect=lambda:1,
                    Condition=lambda f:f,LoadGroupHandle=lambda *a:1,cY=lambda *a:1,LoadUnitHandle=lambda *a:1,
                    IsUnitAliveBJ=lambda u:True,BR3=lambda:None,BR4=lambda:None,BR5=lambda:None,
                    MJ_Player=lambda i:[0,1,2,3,5][i],MJ_IsActive=lambda i:[0,1,2,3,5][i] in roster,
                    CustomDefeatBJ=lambda p,msg:ended.append(p),LoadStr=lambda t,p,k:t.get(('str',p,k),''),
                    PauseTimer=paused.append)
                for native in re.findall(r'^\s*call (\w+)\(',module+f['BR6'][0],re.M):
                    if native not in e:e[native]=lambda *a:None
                if mode==0:e['SaveInteger'](e['DI'],'全局',0xEEFCB876,10)
                if mode==1:e['SaveBoolean'](e['DI'],'全局',0x9D29CC1F,True)
                if mode==2:e['SaveBoolean'](e['DI'],'全局',0x88CEC9C2,True)
                e['BR6']();e['BR6']()
                self.assertEqual(ended,roster,(roster,mode))
                self.assertEqual(paused,['Fw'])
