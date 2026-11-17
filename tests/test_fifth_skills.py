"""Execute patched production functions against native doubles; no engine claim."""
from collections import defaultdict
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

from tests.combat_harness import run_functions
from tools.check_jass import check_jass
from tools.combat_stage import prepare_combat
from tools.free_objects_stage import prepare_free_object_script
from tools.free_stage import prepare_free
from tools.gameplay_stage import prepare_gameplay
from tools.lane_stage import prepare_lane
from tools.layout_stage import prepare_layout
from tools.object_stage import prepare_object_script
from tools.patching import functions
from tools.platform_stage import prepare_platform
from tools.player_stage import prepare_players
from tools.selection_stage import prepare_selection

ROOT=Path(__file__).resolve().parents[1]
SLOTS=[0,1,2,3,5]
COIN=int.from_bytes(b'H00D','big')
KING=int.from_bytes(b'H02H','big')


class FifthSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        members,_=prepare_layout(ROOT/'scratch/baseline');raw=members['war3map.j']
        for stage in [prepare_players,prepare_lane,prepare_object_script,prepare_combat,
                      prepare_platform,prepare_free_object_script,prepare_free]:
            raw,_=stage(raw)
        cls.before=raw

    def output(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.fifth_skill_stage'),
                             'fifth skill dispatch stage is missing')
        stage=importlib.import_module('tools.fifth_skill_stage')
        raw,report=stage.prepare_fifth_skills(self.before)
        return raw,functions(raw.decode()),report

    def environment(self,f,names):
        env=run_functions(''.join(f[n][0] for n in names));table={};gold=[]
        active=set(SLOTS);types={};distances=defaultdict(lambda:9999.)
        def load(t,p,k):return table.get((t,p,k),0)
        def save(t,p,k,v):table[t,p,k]=v
        env.update(EK=1,DI=2,Fa=10,Fb=20,HQ=defaultdict(lambda:None,{i:100+i for i in SLOTS}),
            MJ_Player=lambda i:SLOTS[i],Player=lambda p:p,GetPlayerId=lambda p:p,
            GetHandleId=lambda h:0 if h is None else h,GetTriggeringTrigger=lambda:7,
            GetTriggerUnit=lambda:200,GetOwningPlayer=lambda u:u-100,
            StringHash=lambda text:99,LoadInteger=load,SaveInteger=save,
            SaveStr=save,LoadStr=lambda t,p,k:table.get((t,p,k),''),S2I=int,
            LoadReal=load,SaveReal=save,LoadBoolean=lambda t,p,k:bool(load(t,p,k)),
            GetUnitTypeId=lambda u:types.get(u,0),
            IsPlayerInForce=lambda p,force:p in active,
            IsUnitInForce=lambda u,force:u in {200,201,202},
            bt=lambda a,b:distances[b],PLAYER_STATE_RESOURCE_GOLD=1,
            AdjustPlayerStateBJ=lambda amount,p,state:gold.append((p,amount)),
            I2R=float,I2S=str,IsUnitAliveBJ=lambda u:u is not None)
        return env,table,gold,active,types,distances

    def test_sand_coin_team_kill_rewards_each_roster_position_equally(self):
        _,f,_=self.output()
        for slot in SLOTS:
            env,table,gold,active,types,_=self.environment(f,['MJ_FifthSandCoinReward'])
            types[100+slot]=COIN;table[2,99,0x8B909B14]=7
            killer=next(p for p in SLOTS if p!=slot)
            env['MJ_FifthSandCoinReward'](killer)
            self.assertEqual(gold,[(slot,21)],slot)
            gold.clear();env['MJ_FifthSandCoinReward'](slot)
            self.assertEqual(gold,[],('own kill',slot))
            table[2,99,0xA63650E]=True;env['MJ_FifthSandCoinReward'](killer)
            self.assertEqual(gold,[],('mode gate',slot))
            table[2,99,0xA63650E]=False;active.remove(slot)
            env['MJ_FifthSandCoinReward'](killer);self.assertEqual(gold,[],('left',slot))
        # Preserve one recipient, rather than multiplying a legacy unique-hero reward.
        env,table,gold,_,types,_=self.environment(f,['MJ_FifthSandCoinReward'])
        types[100]=COIN;types[105]=COIN;table[2,99,0x8B909B14]=5
        env['MJ_FifthSandCoinReward'](1);self.assertEqual(gold,[(0,15)])

    def test_actual_kill_dispatch_calls_reward_and_preserves_free_bag_policy(self):
        _,f,_=self.output();before=functions(self.before.decode())['BDV'][0]
        self.assertIn('call MJ_FifthSandCoinReward(GetOwningPlayer(GetKillingUnitBJ()))',f['BDV'][0])
        for line in before.splitlines():
            if 'MJ_ContentAvailable(' in line or '$494D3546' in line:
                self.assertIn(line,f['BDV'][0])
        for slot in SLOTS:
            env,table,gold,_,types,_=self.environment(f,['MJ_FifthSandCoinReward','BDV'])
            killer=next(p for p in SLOTS if p!=slot)
            types[100+slot]=COIN;table[2,99,0x8B909B14]=7
            env.update(GetKillingUnitBJ=lambda:100+killer,GetDyingUnit=lambda:200,
                GetUnitLoc=lambda u:77,SaveLocationHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                LoadLocationHandle=lambda t,p,k:table.get((t,p,k)),
                LoadUnitHandle=lambda *a:None,LoadItemHandle=lambda *a:None,
                UnitHasItem=lambda *a:False,cx=lambda *a:False,
                MJ_ContentAvailable=lambda *a:False,
                GroupAddUnit=lambda *a:None,Fz=22,
                GetUnitLevel=lambda u:0,Uo=lambda chance:False,
                RemoveLocation=lambda *a:None,FlushChildHashtable=lambda *a:None)
            env['BDV']();self.assertEqual(gold,[(slot,21)],slot)

    def test_actual_passive_condition_requires_enemy_distance_and_active_owner_for_all_five(self):
        _,f,_=self.output()
        for slot in SLOTS:
            env,table,_,active,_,distances=self.environment(f,['MJ_FifthSpellPassiveOwner','BMP'])
            table[2,100+slot,0x99CB8E52]=309;distances[100+slot]=700.
            self.assertTrue(env['BMP'](),slot)
            distances[100+slot]=700.01;self.assertFalse(env['BMP'](),('range',slot))
            distances[100+slot]=0.;env['GetTriggerUnit']=lambda:104
            self.assertFalse(env['BMP'](),('human/NPC spell',slot))
            env['GetTriggerUnit']=lambda:200;active.remove(slot)
            self.assertFalse(env['BMP'](),('left',slot))
            active.add(slot);table[2,100+slot,0x99CB8E52]=308
            self.assertFalse(env['BMP'](),('other passive',slot))

    def test_actual_passive_action_damage_and_filter_use_fifth_hero_and_never_stale_owner(self):
        _,f,_=self.output()
        for slot in SLOTS:
            env,table,_,_,_,distances=self.environment(f,['MJ_FifthSpellPassiveOwner','BMS','BMQ','BMR'])
            table[2,100+slot,0x99CB8E52]=309;distances[100+slot]=500.;damage=[];current=[None]
            def enumerate_targets(radius,location,predicate):
                result=[]
                for unit in [201,202,104]:
                    current[0]=unit
                    if predicate():result.append(unit)
                return result
            def for_group(group,callback):
                for unit in group:current[0]=unit;callback()
            env.update(GetFilterUnit=lambda:current[0],GetEnumUnit=lambda:current[0],
                IsUnitAliveBJ=lambda u:u!=202,GetUnitLoc=lambda u:77,
                SaveLocationHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                LoadLocationHandle=lambda t,p,k:table.get((t,p,k)),
                SaveGroupHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                LoadGroupHandle=lambda t,p,k:table.get((t,p,k)),
                GetHeroInt=lambda u,bonus:30,GetHeroStr=lambda u,bonus:20,
                sL=lambda *a:0,DestroyEffect=lambda *a:None,Condition=lambda callback:callback,
                cX=enumerate_targets,ForGroupBJ=for_group,GroupClear=lambda *a:None,
                DestroyGroup=lambda *a:None,RemoveLocation=lambda *a:None,
                FlushChildHashtable=lambda *a:None,ATTACK_TYPE_NORMAL=1,DAMAGE_TYPE_COLD=2,WEAPON_TYPE_WHOKNOWS=3,
                UnitDamageTarget=lambda source,target,amount,*a:damage.append((source,target,amount)))
            env['BMS']();self.assertEqual(damage,[(100+slot,201,300.)],slot)
            damage.clear();distances[100+slot]=701.;env['BMS']()
            self.assertEqual(damage,[],('no stale selection',slot))
        env,table,_,_,_,distances=self.environment(f,['MJ_FifthSpellPassiveOwner'])
        for slot in [0,5]:table[2,100+slot,0x99CB8E52]=309;distances[100+slot]=1.
        self.assertEqual(env['MJ_FifthSpellPassiveOwner'](200),0)

    def test_actual_random_king_level_reward_pays_only_active_teammates_for_every_owner(self):
        _,f,_=self.output()
        for slot in SLOTS:
            env,table,gold,active,types,_=self.environment(f,['MJ_FifthTeammateGold','ws'])
            types[100+slot]=KING
            env.update(GetTriggerUnit=lambda:100+slot,GetRandomInt=lambda a,b:3,
                GetHeroLevel=lambda u:4,LoadUnitHandle=lambda *a:None,
                Uo=lambda chance:False,
                IsUnitAliveBJ=lambda u:False,IsUnitType=lambda *a:False,UNIT_TYPE_HERO=1,
                DisplayTimedTextToForce=lambda *a:None,GetPlayersAll=lambda:99,
                FlushChildHashtable=lambda *a:None,KillUnit=lambda *a:None,
                DisplayTimedTextToPlayer=lambda *a:None)
            env['ws']();self.assertEqual(gold,[(p,12000) for p in SLOTS if p!=slot],slot)
            gold.clear();active.remove(next(p for p in SLOTS if p!=slot));env['ws']()
            self.assertEqual(gold,[(p,12000) for p in SLOTS if p!=slot and p in active])
            gold.clear();table[2,99,0xA63650E]=True;env['ws']();self.assertEqual(gold,[])

    def test_pinned_drift_reapplication_and_unreviewed_changes_are_rejected(self):
        raw,after,report=self.output();stage=importlib.import_module('tools.fifth_skill_stage')
        with self.assertRaises(ValueError):stage.prepare_fifth_skills(raw)
        with self.assertRaises(ValueError):stage.prepare_fifth_skills(self.before.replace(b'GetRandomInt(1,5)',b'GetRandomInt(1,6)'))
        before=functions(self.before.decode());changed={n for n in before if before[n][0]!=after[n][0]}
        self.assertEqual(changed,{'BDV','BMP','BMS','ws'})
        self.assertFalse(report['runtime_verified'])

    def test_combined_gameplay_skill_selection_output_compiles(self):
        self.output();stage=importlib.import_module('tools.fifth_skill_stage')
        raw,_=prepare_gameplay(self.before);raw,_=stage.prepare_fifth_skills(raw)
        raw,_,_=prepare_selection(raw)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j';path.write_bytes(raw)
            compiler=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(compiler['passed'],compiler['output'])


if __name__=='__main__':unittest.main()
