import importlib
import math
from pathlib import Path
import tempfile
import unittest
from tools.layout_stage import prepare_layout
from tools.player_stage import prepare_players
from tools.lane_stage import prepare_lane
from tools.object_stage import prepare_object_script
from tools.selection_stage import prepare_selection
from tools.patching import functions
from tools.check_jass import check_jass
from tests.combat_harness import run_functions

ROOT=Path(__file__).resolve().parents[1]
HUMANS=[0,1,2,3,5]
ENEMIES=[8,9,10,11,6]

class CombatStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        members,_=prepare_layout(ROOT/'scratch/baseline')
        script,_=prepare_players(members['war3map.j']);script,_=prepare_lane(script)
        cls.before,_=prepare_object_script(script)

    def stage(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.combat_stage'),'combat stage is missing')
        return importlib.import_module('tools.combat_stage')

    def output(self):
        script,report=self.stage().prepare_combat(self.before)
        return script,functions(script.decode()),report

    def shared_environment(self):
        _,f,_=self.output()
        env=run_functions(''.join(f[n][0] for n in ['MJ_CombatLaneAlive','MJ_LiveLaneCount','MJ_SpawnContribution','MJ_RefreshSpawnIntervals']))
        active=set(HUMANS);food=dict.fromkeys(ENEMIES,1);weights={}
        env.update(DI=1,Fa=2,PLAYER_STATE_RESOURCE_FOOD_USED=3,
            MJ_Player=lambda i:HUMANS[i],MJ_Enemy=lambda i:ENEMIES[i],MJ_IsActive=lambda i:HUMANS[i] in active,
            GetHandleId=lambda p:p,IsPlayerInForce=lambda p,_:p in active,
            LoadUnitHandle=lambda table,p,key:100+p,IsUnitAliveBJ=lambda u:u-100 in active,
            GetPlayerState=lambda p,_:food[p],I2R=float,Pow=math.pow,
            SaveReal=lambda table,p,key,v:weights.__setitem__(p,v))
        return env,active,food,weights

    def test_shared_spawn_intervals_include_fifth_lane_and_exclude_own_monsters(self):
        env,active,food,weights=self.shared_environment()
        env['MJ_RefreshSpawnIntervals']()
        for p in HUMANS:self.assertAlmostEqual(weights[p],.2)
        food[6]=32
        env['MJ_RefreshSpawnIntervals']()
        for p in [0,1,2,3]:self.assertAlmostEqual(weights[p],.35)
        self.assertAlmostEqual(weights[5],.2)

    def test_one_or_zero_live_lanes_never_divide_by_zero_or_retain_stale_weight(self):
        env,active,food,weights=self.shared_environment()
        weights.update(dict.fromkeys(HUMANS,99.))
        active.intersection_update({5});env['MJ_RefreshSpawnIntervals']()
        expected=dict.fromkeys(HUMANS,0.);expected[5]=1.
        self.assertEqual(weights,expected)
        active.clear();env['MJ_RefreshSpawnIntervals']()
        self.assertEqual(weights,dict.fromkeys(HUMANS,0.))

    def test_all_five_redistributors_spawn_for_other_live_lanes_only(self):
        _,f,_=self.output()
        for slot,name in zip(HUMANS,['BDB','BDD','BDF','BDH','MJ5_Redistribute']):
            env=run_functions(f[name][0]);table={};created=[];active=set(HUMANS)
            def load(t,p,k):return table.get((t,p,k),0)
            def save(t,p,k,v):table[t,p,k]=v
            def create(n,code,owner,location,facing):
                created.append(owner);env['bj_lastCreatedUnit']=200+owner
            env.update(EK=1,DI=2,HV=3,MAP_CONTROL_USER=4,PLAYER_SLOT_STATE_PLAYING=5,
                UNIT_STATE_MAX_LIFE=6,GetTriggeringTrigger=lambda:100,GetHandleId=lambda h:h,
                MJ_Human1=lambda i:HUMANS[i-1],MJ_Enemy1=lambda i:ENEMIES[i-1],
                GetPlayerController=lambda p:4,GetPlayerSlotState=lambda p:5,
                IsPlayerInForce=lambda p,_:p in active,Fa=9,
                LoadInteger=load,LoadPlayerHandle=load,LoadReal=load,LoadLocationHandle=load,
                SaveInteger=save,SavePlayerHandle=save,SaveReal=save,SaveLocationHandle=save,SaveUnitHandle=save,SaveBoolean=save,
                LoadUnitHandle=lambda t,p,k:1000+p,IsUnitAliveBJ=lambda u:u-1000 in HUMANS,
                LoadRectHandle=lambda t,p,k:p,GetRandomLocInRect=lambda rect:rect,
                GetRandomInt=lambda lo,hi:hi if hi==200 else lo,StringHash=lambda s:99,
                CreateNUnitsAtLoc=create,I2R=float,R2I=int,Pow=math.pow,Uo=lambda p:False,
                GetUnitTypeId=lambda u:0,ConvertUnitState=lambda state:state,GetUnitState=lambda *a:1.)
            for native in ['SetUnitState','SetUnitLifePercentBJ','IssuePointOrderLoc','RemoveLocation','FlushChildHashtable']:
                env[native]=lambda *a:None
            env[name]()
            self.assertEqual(created,[e for p,e in zip(HUMANS,ENEMIES) if p!=slot])
            created.clear();active.discard(1);env[name]()
            self.assertEqual(created,[e for p,e in zip(HUMANS,ENEMIES) if p!=slot and p!=1])

    def test_fifth_lane_warning_and_failure_dispatch_respect_membership(self):
        _,f,_=self.output();env=run_functions(f['BPL'][0]);table={};active=set(HUMANS);food=dict.fromkeys(ENEMIES,0);triggered=[];warned=[]
        env.update(EK=1,DI=2,Fa=3,HQ={p:100+p for p in HUMANS},MJ5_Failure=55,
            HR=50,HS=51,HT=52,HU=53,t=1,Y=2,
            Player=lambda p:p,GetTriggeringTrigger=lambda:10,GetHandleId=lambda h:h,
            StringHash=lambda s:99,I2R=float,R2I=int,PLAYER_STATE_RESOURCE_FOOD_USED=3,
            LoadInteger=lambda t,p,k:90 if k==0xB02D0480 else table.get((t,p,k),0),
            SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            LoadBoolean=lambda *a:True,GetUnitTypeId=lambda u:0,
            GetPlayerState=lambda p,_:food[p],IsPlayerInForce=lambda p,_:p in active,
            PlaySoundBJ=lambda *a:None,EnableTrigger=lambda *a:None,
            TriggerExecute=lambda t:triggered.append(t),
            DisplayTimedTextToPlayer=lambda p,*a:warned.append(p),FlushChildHashtable=lambda *a:None)
        food[6]=77;env['BPL']();self.assertEqual(warned,[5]);self.assertEqual(triggered,[])
        food[6]=90;warned.clear();env['BPL']();self.assertEqual(triggered,[55])
        active.discard(5);triggered.clear();env['BPL']();self.assertEqual(triggered,[])

    def test_fifth_failure_removes_only_own_units_monsters_and_own_npc_region(self):
        _,f,_=self.output();env=run_functions(''.join(f[n][0] for n in ['BOd','BOe','BOf','MJ5_FailLane']))
        active=set(HUMANS);removed=[];gates=[];board=[];enum=[None]
        units={p:[100+p] for p in HUMANS+ENEMIES};units[4]=[401,405]
        regions={p:1000+p for p in HUMANS};groups=[]
        def cZ(rect,owner):
            result=[405] if owner==4 and rect==1005 else list(units.get(owner,[]))
            groups.append((rect,owner));return result
        def each(group,callback):
            for u in group:enum[0]=u;callback()
        env.update(EK=1,DI=2,Fa=3,JF=4,Fc=5,HQ={p:100+p for p in HUMANS},BO=1,
            Player=lambda p:p,GetPlayerId=lambda p:p,GetHandleId=lambda h:h,
            MJ_EnemyOf=lambda p:dict(zip(HUMANS,ENEMIES))[p],MJ_Row=lambda p:HUMANS.index(p)+2,
            IsPlayerInForce=lambda p,_:p in active,LoadBoolean=lambda *a:False,
            GetTriggeringTrigger=lambda:55,GetUnitTypeId=lambda u:0,GetPlayerName=str,
            LoadLocationHandle=lambda *a:0,LoadUnitHandle=lambda *a:None,
            LoadRectHandle=lambda t,p,k:regions[p],GetEntireMapRect=lambda:999,
            GetPlayersAll=lambda:active,GetEnumUnit=lambda:enum[0],cZ=cZ,ForGroupBJ=each,
            ForceRemovePlayer=lambda _,p:active.discard(p),CountPlayersInForceBJ=lambda _:len(active),
            RemoveUnit=lambda u:removed.append(u),
            ch=lambda table,col,row,text:board.append(row),ce=lambda *a:None,StringHash=lambda _:99)
        for name in ['DisableTrigger','DestroyTrigger','PlaySoundBJ','SetTerrainTypeBJ','DisplayTimedTextToForce','GroupRemoveUnit']:
            env[name]=lambda *a:None
        env['MJ5_FailLane']()
        self.assertEqual(active,{0,1,2,3});self.assertIn(105,removed);self.assertIn(106,removed);self.assertIn(405,removed)
        self.assertNotIn(101,removed);self.assertNotIn(109,removed);self.assertNotIn(401,removed)
        self.assertEqual(set(board),{6});self.assertEqual(groups,[(999,5),(999,6),(1005,4)])
        before=list(removed);env['MJ5_FailLane']();self.assertEqual(removed,before)

    def test_fifth_leave_event_registered_and_full_result_compiles(self):
        script,f,report=self.output();env=run_functions(f['BOL'][0]);registered=[]
        env.update(Player=lambda p:p,CreateTrigger=lambda:1,
            TriggerRegisterPlayerEventLeave=lambda t,p:registered.append(p),
            TriggerAddAction=lambda *a:None,BOK=lambda:None)
        env['BOL']();self.assertEqual(registered,HUMANS)
        final,_,_=prepare_selection(script)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j';path.write_bytes(final)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])
        self.assertFalse(report['runtime_verified'])

    def test_changed_inputs_and_reapplying_stage_are_rejected(self):
        stage=self.stage()
        with self.assertRaises(ValueError):stage.prepare_combat(self.before.replace(b'if Gi!=1 then',b'if Gi!=2 then'))
        script,_=stage.prepare_combat(self.before)
        with self.assertRaises(ValueError):stage.prepare_combat(script)

    def test_leave_during_selection_or_starting_does_not_run_battle_cleanup_or_victory(self):
        script,_,_=self.output();final,_,_=prepare_selection(script);body=functions(final.decode())['BOK'][0]
        for state in [1,2]:
            env=run_functions(body);active={0,5};calls=[]
            env.update(MJ_AllHeroMode=True,MJ_SelectState=state,Fa=1,DI=2,
                StringHash=lambda s:99,GetHandleId=lambda p:p,
                MJ_Index=lambda p:4 if p==5 else p,GetTriggerPlayer=lambda:5,
                IsPlayerInForce=lambda p,_:p in active,
                ForceRemovePlayer=lambda _,p:active.discard(p))
            def unexpected(*args):raise AssertionError('battle side effect during selection')
            env['LoadBoolean']=unexpected
            env['BOK']()
            self.assertEqual(active,{0})

    def test_global_grace_and_reward_flags_require_their_mode_and_threshold(self):
        from tests.jass_subset import expression
        import re
        _,f,_=self.output()
        body=f['BO9'][0]
        predicates=[line[3:-5] for line in body.splitlines() if line.startswith('if ') and ('DzAPI_Map_HasMallItem(Player(0)' in line or any('LoadBoolean(DI,GetHandleId(Player(0)),'+key in line for key in ['$66DBBCC9','$B0CC1918']))]
        self.assertEqual(len(predicates),3)
        for flag_owner in HUMANS:
            for eligible_mode in [False,True]:
                for total,expected in [(10,False),(95,True)]:
                    def load_bool(table,parent,key):
                        if key==0x88CEC9C2:return not eligible_mode
                        return parent==flag_owner
                    env=dict(DI=1,Fa=2,IsPlayerInForce=lambda p,_:p in HUMANS,
                        StringHash=lambda s:99,Player=lambda p:p,GetHandleId=lambda h:h,
                        LoadBoolean=load_bool,DzAPI_Map_HasMallItem=lambda p,key:p==flag_owner,
                        MJ_TotalMonsters=lambda:total,R2I=int,I2R=float,LoadInteger=lambda *a:100)
                    results=[eval(expression(re.sub(r'\$([0-9A-F]+)',r'0x\1',predicate)),{},env) for predicate in predicates]
                    self.assertEqual(results,[eligible_mode,expected,expected])

    def test_packaged_checkpoint_contains_combat_stage(self):
        from tools.build_checkpoint import build_checkpoint
        from tools.archive import read_member
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            dest=Path(tmp)/'combat-checkpoint.w3x';report=build_checkpoint(ROOT/'inputs/original.w3x',dest)
            self.assertIn('combat',report)
            script=read_member(dest,'war3map.j')
            self.assertIn('MJ5_FailLane',functions(script.decode()))
            self.assertFalse(report['playable_verified'])

    def test_fifth_leave_cleans_only_human_five_enemy_six_and_closes_fifth_gate_once(self):
        script,_,_=self.output();final,_,_=prepare_selection(script);f=functions(final.decode())
        env=run_functions(''.join(f[n][0] for n in ['BOI','BOJ','BOK']))
        active=set(HUMANS);removed=[];groups=[];gates=[];rows=[];table={};enum=[None]
        def each(group,callback):
            for u in group:enum[0]=u;callback()
        def cz(rect,owner):groups.append(owner);return [100+owner]
        env.update(MJ_AllHeroMode=False,MJ_SelectState=3,MJ_Index=lambda p:4 if p==5 else p,
            Fa=1,DI=2,EK=3,JF=4,Fc=5,HQ={p:100+p for p in HUMANS},BE=0,bj_GATEOPERATION_CLOSE=7,MJ5_CX=555,
            MJ_EnemyOf=lambda p:dict(zip(HUMANS,ENEMIES))[p],MJ_Row=lambda p:HUMANS.index(p)+2,
            GetTriggerPlayer=lambda:5,IsPlayerInForce=lambda p,_:p in active,
            GetHandleId=lambda h:h,Player=lambda p:p,GetPlayerId=lambda p:p,GetPlayerName=str,
            LoadBoolean=lambda *a:False,LoadUnitHandle=lambda *a:None,GetUnitTypeId=lambda u:0,
            GetPlayersAll=lambda:active,GetEntireMapRect=lambda:0,cZ=cz,ForGroupBJ=each,GetEnumUnit=lambda:enum[0],
            RemoveUnit=lambda u:removed.append(u),ForceRemovePlayer=lambda _,p:active.discard(p),
            CountPlayersInForceBJ=lambda _:len(active),GetPlayerTechCountSimple=lambda *a:0,
            StringHash=lambda _:99,LoadInteger=lambda t,p,k:450,
            SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            ch=lambda table,col,row,text:rows.append(row),ce=lambda *a:None,
            ModifyGateBJ=lambda action,gate:gates.append((action,gate)))
        for name in ['PlaySoundBJ','DisplayTimedTextToForce','SaveBoolean','GroupRemoveUnit']:
            env[name]=lambda *a:None
        env['BOK']()
        self.assertEqual(groups,[5,6]);self.assertEqual(active,{0,1,2,3})
        self.assertEqual([u for u in removed if u is not None],[105,106]);self.assertEqual(set(rows),{6})
        self.assertEqual(gates,[(7,555)])
        before=(list(removed),dict(table));env['BOK']();self.assertEqual((removed,table),before)

    def test_kick_vote_fifth_logical_index_never_selects_npc(self):
        _,f,_=self.output();env=run_functions(f['BN3'][0]);selected=[]
        for index,expected in [('1',0),('5',5),('6',None),('0',None)]:
            selected.clear()
            env.update(EK=1,DI=2,GetTriggeringTrigger=lambda:10,GetTriggerPlayer=lambda:0,GetHandleId=lambda h:h,
                LoadInteger=lambda *a:0,LoadBoolean=lambda *a:False,
                SaveInteger=lambda *a:None,SavePlayerHandle=lambda t,p,k,v:selected.append(v),
                LoadPlayerHandle=lambda *a:selected[-1],GetEventPlayerChatString=lambda:'-kick'+index,
                SubStringBJ=lambda value,start,end:value[start-1:end],S2I=int,
                MJ_Human1=lambda i:HUMANS[i-1],DisplayTextToPlayer=lambda *a:None,FlushChildHashtable=lambda *a:None)
            env['BN3']();self.assertEqual(selected,[] if expected is None else [expected])

    def test_eliminated_players_cannot_supply_global_grace_or_reward_flags(self):
        from tests.jass_subset import expression
        import re
        _,f,_=self.output()
        predicates=[line[3:-5] for line in f['BO9'][0].splitlines() if line.startswith('if ') and ('DzAPI_Map_HasMallItem(Player(0)' in line or any('LoadBoolean(DI,GetHandleId(Player(0)),'+key in line for key in ['$66DBBCC9','$B0CC1918']))]
        active={0,1,2,3}
        env=dict(DI=1,Fa=2,StringHash=lambda s:99,Player=lambda p:p,GetHandleId=lambda p:p,
            LoadBoolean=lambda t,p,k:False if k==0x88CEC9C2 else p==5,
            DzAPI_Map_HasMallItem=lambda p,key:p==5,IsPlayerInForce=lambda p,_:p in active,
            MJ_TotalMonsters=lambda:95,R2I=int,I2R=float,LoadInteger=lambda *a:100)
        results=[eval(expression(re.sub(r'\$([0-9A-F]+)',r'0x\1',predicate)),{},env) for predicate in predicates]
        self.assertEqual(results,[False,False,False])

    def test_spawn_consumer_schedules_positive_intervals_only_for_live_members(self):
        env,active,food,intervals=self.shared_environment();_,f,_=self.output()
        scheduler=run_functions(f['BC5'][0]);table={};scheduled=[];created=[]
        def load(t,p,k):return table.get((t,p,k),0)
        def save(t,p,k,v):table[t,p,k]=v
        def timer():created.append(700+len(created));return created[-1]
        scheduler.update(EK=1,DI=2,Fa=3,MAP_CONTROL_USER=4,PLAYER_SLOT_STATE_PLAYING=5,
            MJ_Human1=lambda i:HUMANS[i-1],MJ_Enemy1=lambda i:ENEMIES[i-1],
            GetTriggeringTrigger=lambda:99,GetHandleId=lambda h:h,
            LoadInteger=load,SaveInteger=save,LoadPlayerHandle=load,SavePlayerHandle=save,
            LoadLocationHandle=load,SaveLocationHandle=save,SaveUnitHandle=save,
            LoadUnitHandle=lambda t,p,k:100+p,IsUnitAliveBJ=lambda u:u-100 in active,
            IsPlayerInForce=lambda p,_:p in active,GetPlayerController=lambda p:4,
            GetPlayerSlotState=lambda p:5 if p in active else 0,
            LoadReal=lambda t,p,k:intervals.get(p,0.),R2I=int,CreateTimer=timer,
            BC4=lambda:None,TimerStart=lambda t,interval,repeat,callback:scheduled.append((table[1,t,0xA59BB4C6],interval)),
            FlushChildHashtable=lambda *a:None)
        for players,expected in [({5},[(5,1.)]),(set(),[]),({0,5},[(0,.2),(5,.2)])]:
            active.clear();active.update(players);env['MJ_RefreshSpawnIntervals']();scheduled.clear();created.clear()
            scheduler['BC5']()
            self.assertEqual(scheduled,expected)
            self.assertEqual(len(created),len(expected))
        active.clear();active.add(5);intervals.update(dict.fromkeys(HUMANS,1.))
        scheduler['GetPlayerSlotState']=lambda p:5
        scheduler['IsUnitAliveBJ']=lambda u:True
        scheduled.clear();created.clear();scheduler['BC5']()
        self.assertEqual(scheduled,[(5,1.)])
        intervals[5]=0.;scheduled.clear();created.clear();scheduler['BC5']()
        self.assertEqual(scheduled,[]);self.assertEqual(created,[])

    def test_delayed_spawn_timer_stops_after_owner_removed_even_if_base_still_alive(self):
        _,f,_=self.output();env=run_functions(f['BC4'][0]);table={(1,88,0xA59BB4C6):5,(1,88,0xA8E3A26B):10};destroyed=[]
        def unexpected(*a):raise AssertionError('spawn attempted after membership removal')
        env.update(EK=1,DI=2,Fa=3,GY=4,GetExpiredTimer=lambda:88,GetHandleId=lambda h:h,
            LoadInteger=lambda t,p,k:table.get((t,p,k),0),SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            LoadPlayerHandle=lambda t,p,k:table.get((t,p,k),0),LoadUnitHandle=lambda *a:105,IsUnitAliveBJ=lambda u:True,
            IsPlayerInForce=lambda p,_:False,IsTriggerEnabled=lambda t:True,
            StringHash=lambda s:99,GetRandomInt=unexpected,FlushChildHashtable=lambda *a:None,
            DestroyTimer=lambda t:destroyed.append(t))
        env['BC4']();self.assertEqual(destroyed,[88])
