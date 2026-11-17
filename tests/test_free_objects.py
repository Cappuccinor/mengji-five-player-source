"""Actual patched JASS at native boundaries; never a Warcraft runtime claim."""
from collections import defaultdict
import importlib
from pathlib import Path
import re
import tempfile
import unittest

from tools.check_jass import check_jass
from tools.combat_stage import prepare_combat
from tools.hero_catalog import sections, slk
from tools.layout_stage import prepare_layout
from tools.lane_stage import prepare_lane
from tools.object_stage import prepare_object_script, prepare_objects
from tools.patching import functions
from tools.platform_stage import prepare_platform
from tools.player_stage import prepare_players
from tools.selection_stage import prepare_selection
from tests.combat_harness import run_functions
from tests.jass_subset import expression

ROOT=Path(__file__).resolve().parents[1]
BAG=int.from_bytes(b'IM5F','big')
PENDANT=int.from_bytes(b'IM5G','big')


class FreeObjectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        members,_=prepare_layout(ROOT/'scratch/baseline')
        raw,_=prepare_players(members['war3map.j'])
        raw,_=prepare_lane(raw)
        raw,_=prepare_object_script(raw)
        raw,_=prepare_combat(raw)
        cls.before,_=prepare_platform(raw)
        cls.objects,_=prepare_objects(ROOT/'inputs/original.w3x')

    def stage(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.free_objects_stage'),
                             'fifth infinite bag and VIP2 choice stage is missing')
        return importlib.import_module('tools.free_objects_stage')

    def output(self):
        raw,report=self.stage().prepare_free_object_script(self.before)
        return raw,functions(raw.decode()),report

    def test_real_object_clone_preserves_all_existing_rows_and_gameplay_fields(self):
        replacement,report=self.stage().prepare_free_objects(self.objects)
        self.assertEqual(set(replacement),{r'Units\ItemData.slk',r'Units\ItemStrings.txt',r'Units\CampaignAbilityStrings.txt'})
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'table'
            for name,parser in [(r'Units\ItemData.slk',slk),(r'Units\ItemStrings.txt',sections)]:
                path.write_bytes(self.objects[name]);before=parser(path)
                path.write_bytes(replacement[name]);after=parser(path)
                self.assertEqual(set(after)-set(before),{'IM5F','IM5G'})
                for key,value in before.items():self.assertEqual(after[key],value)
                for old,new in [('I05J','IM5F'),('I040','IM5G')]:
                    expected=dict(before[old])
                    if parser==slk:expected['itemID']=new
                    self.assertEqual(after[new],expected)
        self.assertFalse(report['runtime_verified'])

    def test_pre_stage_drift_and_reapplication_are_rejected(self):
        stage=self.stage();raw,_,_=self.output()
        with self.assertRaises(ValueError):stage.prepare_free_object_script(raw)
        with self.assertRaises(ValueError):stage.prepare_free_object_script(self.before.replace(b'set IL[4]=',b'set IL[9]='))
        modified=dict(self.objects);modified[r'Units\ItemData.slk']+=b'\n'
        with self.assertRaises(ValueError):stage.prepare_free_objects(modified)
        replacement,_=stage.prepare_free_objects(self.objects)
        with self.assertRaises(ValueError):stage.prepare_free_objects(dict(self.objects,**replacement))

    def test_fifth_bag_damage_and_kill_predicates_accept_only_eligible_inventory(self):
        _,f,_=self.output()
        self.assertRegex(f['uW'][0],r'set IL\[6\]=\$494D3546')
        for name in ['xa','xd','xi','BDV']:
            line=next(l for l in f[name][0].splitlines() if l.startswith('if ') and '$4930354A' in l)
            predicate=re.sub(r'\$([0-9A-F]+)',r'0x\1',line[3:-5])
            for inventory,owned,want in [({BAG},True,True),(set(),True,False),({BAG},False,name!='BDV')]:
                env=dict(cx=lambda u,item:item in inventory,GetEventDamageSource=lambda:105,
                         HQ={5:105},GetPlayerId=lambda p:p,GetOwningPlayer=lambda u:5,
                         GetKillingUnitBJ=lambda:105,DzAPI_Map_HasMallItem=lambda p,key:owned)
                self.assertEqual(eval(expression(predicate),{},env),want,(name,inventory,owned))

    def test_fifth_bag_upgrade_changes_its_own_tooltip_and_keeps_cost(self):
        _,f,_=self.output();env=run_functions(f['zC'][0]);table={};written=[];cost=[];lookups=[]
        def load(t,p,k):return table.get((t,p,k),0)
        env.update(EK=1,DI=2,IL={6:BAG},HQ={5:105},F5=0,
            GetTriggeringTrigger=lambda:7,GetTriggerUnit=lambda:105,GetOwningPlayer=lambda u:5,
            GetHandleId=lambda h:h,GetConvertedPlayerId=lambda p:p+1,GetPlayerState=lambda *a:500,
            PLAYER_STATE_RESOURCE_LUMBER=1,LoadInteger=load,
            SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            SaveStr=lambda t,p,k,v:table.__setitem__((t,p,k),v),LoadStr=lambda t,p,k:table.get((t,p,k),''),
            cV=lambda unit,rawcode:(lookups.append(rawcode) or 888),
            AdjustPlayerStateBJ=lambda value,p,state:cost.append(value),
            GetItemTypeId=lambda item:BAG,GetItemName=lambda item:'bag',I2S=str,
            EXSetItemDataString=lambda item,field,value:written.append(item),
            EXGetItemDataString=lambda *a:'',LoadItemHandle=lambda t,p,k:table.get((t,p,k)),
            SaveItemHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            sM=lambda *a:0)
        for native in ['UnitRemoveItemSwapped','UnitAddItem','DisplayTextToPlayer','DestroyEffect','FlushChildHashtable']:
            env[native]=lambda *a:None
        env['zC']()
        self.assertEqual(lookups,[BAG]);self.assertEqual(cost,[-1]);self.assertEqual(set(written),{BAG})
        self.assertEqual(table[(2,5,0x5378A8C7)],1)

    def test_one_bag_restriction_excludes_the_item_itself_and_unrelated_slots(self):
        _,f,_=self.output()
        line=next(l for l in f['zN'][0].splitlines() if l.startswith('if UnitItemInSlotBJ(') and '$4930354A' in l)
        predicate=expression(re.sub(r'\$([0-9A-F]+)',r'0x\1',line[3:-5]))
        for other,rawcode,want in [(77,BAG,False),(None,0,False),(88,BAG,True),(88,0x4930384C,True),(88,0x49303030,False)]:
            env=dict(GetManipulatedItem=lambda:77,GetTriggerUnit=lambda:105,Gi=1,
                UnitItemInSlotBJ=lambda *a:other,IsUnitType=lambda *a:True,UNIT_TYPE_HERO=1,
                GetItemTypeId=lambda item:BAG if item==77 else rawcode,
                GetItemType=lambda item:4 if item==77 or rawcode in [BAG,0x4930384C] else 1,
                ITEM_TYPE_ARTIFACT=1,ITEM_TYPE_PURCHASABLE=2,ITEM_TYPE_CAMPAIGN=3)
            self.assertEqual(eval(predicate,{},env),want)

    def test_fifth_infernal_award_creates_one_pendant_and_updates_only_its_type(self):
        _,f,_=self.output();env=run_functions(f['BPS'][0]);table={};created=[];written=[];types={};rolls=iter([4,9])
        def load(t,p,k):return table.get((t,p,k),0)
        def create(rawcode,hero):
            created.append((rawcode,hero));types[888]=rawcode;env['bj_lastCreatedItem']=888
        env.update(EK=1,DI=2,BN=3,HQ={5:105},bj_lastCreatedItem=999,
            GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,GetDyingUnit=lambda:206,
            GetOwningPlayer=lambda u:6,MJ_HumanOf=lambda p:5,Player=lambda p:p,GetPlayerId=lambda p:p,
            GetPlayerName=str,GetPlayersAll=lambda:3,StringHash=lambda _:99,
            LoadBoolean=lambda *a:True,LoadInteger=load,LoadReal=load,
            LoadStr=lambda t,p,k:table.get((t,p,k),''),
            LoadPlayerHandle=lambda t,p,k:table.get((t,p,k)),
            LoadItemHandle=lambda t,p,k:table.get((t,p,k)),
            GetItemTypeId=lambda item:types.get(item,0),GetUnitTypeId=lambda hero:0,
            SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            SaveReal=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            SaveStr=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            SavePlayerHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            SaveItemHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            UnitAddItemByIdSwapped=create,GetRandomInt=lambda lo,hi:next(rolls),Uo=lambda _:False,I2S=str,
            EXSetItemDataString=lambda rawcode,field,value:written.append(rawcode),
            EXGetItemDataString=lambda *a:'',ej=lambda rawcode,*a:self.assertEqual(rawcode,PENDANT),
            sM=lambda *a:None)
        for native in ['PlaySoundBJ','DisplayTimedTextToForce','SetItemPlayer','SetItemInvulnerable',
                       'UnitRemoveItemSwapped','DoNothing','UnitAddItem','DestroyEffect','FlushChildHashtable']:
            env[native]=lambda *a:None
        env['BPS']();env['BPS']()
        self.assertEqual(created,[(PENDANT,105)])
        self.assertEqual(table[(2,5,0x46C76F13)],888)
        self.assertEqual(table[(2,5,0xAF1AC911)],2)
        self.assertTrue(written);self.assertEqual(set(written),{PENDANT})

    def dialog_env(self,f,name,passive=False):
        helper=''.join(m[0] for n,m in f.items() if n.startswith('MJ_FreeDialog'))
        env=run_functions(helper+f[name][0]);table={};changes=[];button=[66 if passive else 61];sender=[5]
        dialogs={'Fm':10,'Fo':11,'Fn':12,'Fp':13,'Fq':20,'Fr':21,'Fs':22,'Ft':23,
                 'MJ_FreeActiveDialog':15,'MJ_FreePassiveDialog':25}
        env.update(dialogs)
        env.update(EK=1,DI=2,Fa=3,HQ=defaultdict(int,{5:105}),Fu=defaultdict(lambda:-1,{5:5}),
            Fl=defaultdict(int,{5:1}),GI={i:i for i in [11,12,21,22,31,32,41,42,61,62,16,17,26,27,36,37,46,47,66,67]},
            GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,GetPlayerId=lambda p:p,
            GetTriggerPlayer=lambda:sender[0],GetClickedDialogBJ=lambda:25 if passive else 15,
            GetClickedButtonBJ=lambda:button[0],IsPlayerInForce=lambda p,force:p==5,
            LoadInteger=lambda t,p,k:table.get((t,p,k),0),
            SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
            UnitRemoveAbility=lambda hero,abil:changes.append(('remove',hero,abil)),
            UnitAddAbility=lambda hero,abil:changes.append(('add',hero,abil)),
            GetUnitTypeId=lambda unit:0,FlushChildHashtable=lambda *a:None,
            LoadEffectHandle=lambda *a:None,DestroyEffect=lambda *a:None)
        table[(2,105,0xDC9C3938 if passive else 0x582FA68A)]=700
        table[(2,1,0xDC9C3938 if passive else 0x582FA68A)]=701
        return env,changes,button,sender,table

    def test_fifth_active_and_passive_choices_apply_only_once_to_the_sender(self):
        _,f,_=self.output()
        for name,passive in [('BB0',False),('BB2',True)]:
            env,changes,button,sender,table=self.dialog_env(f,name,passive)
            env[name]()
            self.assertEqual(changes,[('remove',105,700),('add',105,701)])
            self.assertEqual(env['Fu'][5],-1)
            env[name]();self.assertEqual(len(changes),2,'replayed choice applied twice')
            for bad_sender,bad_button in [(0,66 if passive else 61),(5,16 if passive else 11)]:
                env,changes,button,sender,table=self.dialog_env(f,name,passive)
                sender[0]=bad_sender;button[0]=bad_button;env[name]()
                self.assertEqual(changes,[],'foreign sender or other player button accepted')
            env,changes,button,sender,table=self.dialog_env(f,name,passive)
            button[0]=67 if passive else 62;env[name]()
            self.assertEqual(changes,[],'keep changed skill')

    def test_both_fifth_dialogs_are_created_and_registered_with_their_real_handlers(self):
        _,f,_=self.output();body=f['sT'][0]
        scalar=set(re.findall(r'^set (\w+)=',body,re.M))
        arrays=set(re.findall(r'^set (\w+)\[',body,re.M))
        declarations='globals\n'+''.join('integer '+n+'=0\n' for n in scalar)+''.join('integer array '+n+'\n' for n in arrays)+'endglobals\n'
        env=run_functions(declarations+body);handles=iter(range(1,100))
        for native in ['CreateForce','CreateGroup','CreateTimer','DialogCreate']:env[native]=lambda:next(handles)
        env['sT']()
        active=env['MJ_FreeActiveDialog'];passive=env['MJ_FreePassiveDialog']
        self.assertNotEqual(active,passive);self.assertTrue(active and passive)
        self.assertEqual(env['Fu'][5],-1)
        for name,want in [('BB1',active),('BB3',passive)]:
            registration=[];registered=run_functions(f[name][0]);registered.update(env)
            registered.update(CreateTrigger=lambda:99,DisableTrigger=lambda *a:None,
                TriggerRegisterDialogEvent=lambda trig,dialog:registration.append(dialog),
                TriggerAddAction=lambda *a:None,BB0=lambda:None,BB2=lambda:None)
            registered[name]()
            self.assertIn(want,registration);self.assertEqual(len(registration),5)

    def test_actual_book_use_opens_fifth_dialog_and_sets_its_button_indices(self):
        _,f,_=self.output()
        for item,expected_dialog,indices in [(0x4930314A,15,(61,62)),(0x4930314F,25,(66,67))]:
            env=run_functions(f['Ty'][0]+f['BBq'][0]);table={};buttons=[];shown=[];cleared=[]
            def load(t,p,k):return table.get((t,p,k),1000 if p==99 else 0)
            def message(dialog,text):self.assertEqual(dialog,expected_dialog)
            def add_button(dialog,text):
                self.assertEqual(dialog,expected_dialog)
                buttons.append(100+len(buttons));env['bj_lastCreatedButton']=buttons[-1]
            env.update(EK=1,DI=2,D4=4,GI={},HQ={5:105},Fl=defaultdict(int),Fu=defaultdict(lambda:-1),
                Fm=10,Fo=11,Fn=12,Fp=13,Fq=20,Fr=21,Fs=22,Ft=23,
                MJ_FreeActiveDialog=15,MJ_FreePassiveDialog=25,MD=91,MF=92,
                GetTriggeringTrigger=lambda:7,GetHandleId=lambda h:h,GetTriggerUnit=lambda:105,
                GetOwningPlayer=lambda u:5,GetPlayerId=lambda p:p,GetConvertedPlayerId=lambda p:p+1,
                Player=lambda p:p,GetManipulatedItem=lambda:500,GetItemTypeId=lambda _:item,
                GetUnitTypeId=lambda _:0,Uo=lambda _:False,GetRandomInt=lambda lo,hi:lo,
                IsUnitType=lambda *a:False,UNIT_TYPE_HERO=1,UNIT_TYPE_MELEE_ATTACKER=2,UNIT_TYPE_RANGED_ATTACKER=3,
                StringHash=lambda _:99,LoadBoolean=lambda *a:False,LoadInteger=load,
                LoadUnitHandle=lambda *a:None,
                SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                SaveStr=lambda t,p,k,v:table.__setitem__((t,p,k),v),LoadStr=lambda t,p,k:table.get((t,p,k),''),
                HaveSavedInteger=lambda *a:True,DzAPI_Map_HasMallItem=lambda p,key:key=='VIP2',
                SaveDialogHandle=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                LoadDialogHandle=lambda t,p,k:table.get((t,p,k)),
                DialogClear=lambda d:cleared.append(d),DialogSetMessage=message,
                DialogAddButtonBJ=add_button,
                GetLastCreatedButtonBJ=lambda:buttons[-1],DialogDisplayBJ=lambda yes,d,p:shown.append((d,p)),
                SubString=lambda text,a,b:text[a:b],GetAbilityName=lambda _:'name',
                EnableTrigger=lambda *a:None,FlushChildHashtable=lambda *a:None,DoNothing=lambda:None)
            env['BBq']()
            self.assertEqual(cleared,[expected_dialog]);self.assertEqual(shown,[(expected_dialog,5)])
            self.assertEqual([env['GI'][i] for i in indices],[100,101]);self.assertEqual(env['Fu'][5],5)

    def test_combined_preselection_script_compiles(self):
        raw,_,report=self.output();final,_,_=prepare_selection(raw)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j';path.write_bytes(final)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])
        self.assertFalse(report['runtime_verified'])


if __name__=='__main__':unittest.main()
