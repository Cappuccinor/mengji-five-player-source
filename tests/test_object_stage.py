import importlib
from pathlib import Path
import re
import tempfile
import unittest
from tools.archive import read_member
from tools.hero_catalog import slk, sections
from tools.layout_stage import prepare_layout
from tools.player_stage import prepare_players
from tools.lane_stage import prepare_lane
from tools.selection_stage import prepare_selection
from tools.patching import functions
from tools.check_jass import check_jass

ROOT=Path(__file__).resolve().parents[1]

class ObjectStageTests(unittest.TestCase):
    def stage(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.object_stage'), 'fifth-player object stage is missing')
        return importlib.import_module('tools.object_stage')

    def test_clones_preserve_existing_objects_and_all_gameplay_fields(self):
        stage=self.stage()
        members,_=stage.prepare_objects(ROOT/'inputs/original.w3x')
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'table'
            for member,parser,identity,count in [(r'Units\ItemData.slk',slk,'itemID',15),(r'Units\AbilityData.slk',slk,'alias',1),(r'Units\ItemStrings.txt',sections,None,15),(r'Units\CampaignAbilityStrings.txt',sections,None,1)]:
                path.write_bytes(read_member(ROOT/'inputs/original.w3x',member)); before=parser(path)
                path.write_bytes(members[member]); after=parser(path)
                self.assertEqual(len(after),len(before)+count)
                for key,value in before.items(): self.assertEqual(after[key],value)
                for old,new in [('I000','IM50'),('I06H','IM54')] if count==15 else [('A01P','AMJ5')]:
                    expected=dict(before[old])
                    if identity: expected[identity]=new
                    self.assertEqual(after[new],expected)

    def test_fifth_slot_array_values_and_combined_script_compile(self):
        stage=self.stage()
        members,_=prepare_layout(ROOT/'scratch/baseline')
        script,_=prepare_players(members['war3map.j']);script,_=prepare_lane(script)
        script,_=stage.prepare_object_script(script)
        f=functions(script.decode())
        arrays={name:{} for name in ['II','IJ','IK']}
        for name,index,value in re.findall(r'set (I[IJK])\[(\d+)\]=\$([0-9A-F]{8})',f['uW'][0]):
            arrays[name][int(index)]=bytes.fromhex(value).decode()
        self.assertEqual([arrays['II'].get(i) for i in [6,16,26,36,46]],['IM50','IM51','IM52','IM53','IM54'])
        self.assertEqual([arrays['IJ'].get(i) for i in [6,16,26,36,46]],['IM55','IM56','IM57','IM58','IM59'])
        self.assertEqual([arrays['IK'].get(i) for i in [6,16,26,36,46]],['IM5A','IM5B','IM5C','IM5D','IM5E'])
        for name in arrays: self.assertNotIn(5,arrays[name])
        final,_,_=prepare_selection(script)
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            path=Path(tmp)/'war3map.j';path.write_bytes(final)
            result=check_jass(path,ROOT/'vendor/jass-1.27.1')
            self.assertTrue(result['passed'],result['output'])

    def test_object_collision_and_changed_script_are_rejected(self):
        stage=self.stage()
        raw=read_member(ROOT/'inputs/original.w3x',r'Units\ItemData.slk')
        with self.assertRaises(ValueError): stage.clone_slk(raw,{'I000':'I002'})
        raw=Path(ROOT/'scratch/baseline/war3map.j').read_bytes()
        with self.assertRaises(ValueError): stage.prepare_object_script(raw.replace(b'exitwhen Gi>4',b'exitwhen Gi>3'))

    def test_initializers_write_all_five_humans_without_npc_or_zero_ids(self):
        from tests.jass_subset import execute
        stage=self.stage()
        script,_=stage.prepare_object_script((ROOT/'scratch/baseline/war3map.j').read_bytes())
        f=functions(script.decode())
        arrays={name:{} for name in ['II','IJ','IK']}
        for name,index,value in re.findall(r'set (I[IJK])\[(\d+)\]=\$([0-9A-F]{8})',f['uW'][0]): arrays[name][int(index)]=int(value,16)
        for name,array in [('yt','II'),('yv','IJ'),('yx','IK')]:
            code=f[name][0].replace('local integer Gi\n','local integer Gi=0\n')
            code=re.sub(r'\$([0-9A-F]+)',r'0x\1',code)
            env=execute(code); table={}; written=[]
            env.update(arrays);env.update(EK=1,DI=2)
            env.update(GetTriggeringTrigger=lambda:7,GetHandleId=lambda x:x,
                LoadInteger=lambda t,p,k:table.get((t,p,k),0),
                LoadStr=lambda t,p,k:table.get((t,p,k),''),
                SaveInteger=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                SaveStr=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                SaveReal=lambda t,p,k,v:table.__setitem__((t,p,k),v),
                EXSetItemDataString=lambda item,field,value:written.append((item,field,value)),
                DisableTrigger=lambda t:None,FlushChildHashtable=lambda t,p:None)
            env[name]()
            self.assertEqual(len(written),50)
            self.assertEqual(set(item for item,_,_ in written),set(arrays[array].values()))
            self.assertNotIn(0,[item for item,_,_ in written])

    def test_checkpoint_contains_new_objects_and_valid_script(self):
        from tools.build_checkpoint import build_checkpoint
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
            dest=Path(tmp)/'checkpoint.w3x'
            report=build_checkpoint(ROOT/'inputs/original.w3x',dest)
            self.assertIn('objects',report)
            table=read_member(dest,r'Units\ItemData.slk')
            self.assertIn(b'K"IM5E"',table)
            self.assertIn(b'$414D4A35',read_member(dest,'war3map.j'))
            self.assertFalse(report['playable_verified'])

    def test_ability_dispatch_is_independent_for_every_human_and_excludes_npc(self):
        from tools.lane_stage import block
        from tests.jass_subset import execute
        stage=self.stage()
        script,_=stage.prepare_object_script((ROOT/'scratch/baseline/war3map.j').read_bytes())
        f=functions(script.decode())
        for name in ['ux','u1','u4','u7','wW','wZ','we']:
            body=f[name][0]
            # Select the complete original dispatch beginning at the first attribute ability.
            lines=body.splitlines(); index=next(i for i,l in enumerate(lines) if '$41303034' in l)
            dispatch=block('\n'.join(lines[index-1:])+'\n',lines[index-1])
            code='function Dispatch takes nothing returns nothing\n'+dispatch.replace('else\nendif','endif')+'endfunction\n'
            env=execute(re.sub(r'\$([0-9A-F]+)',r'0x\1',code))
            for player,ability in [(0,'A004'),(1,'A01N'),(2,'A01O'),(3,'A01P'),(5,'AMJ5'),(4,None),(7,None)]:
                added=[]
                env.update(HQ={i:100+i for i in range(8)},EK=1,
                    GetEnumPlayer=lambda:player,GetPlayerId=lambda p:p,Player=lambda p:p,
                    GetTriggerPlayer=lambda:player,GetTriggerUnit=lambda:100+player,GetOwningPlayer=lambda u:u-100,
                    GetTriggeringTrigger=lambda:10,GetHandleId=lambda h:h,
                    LoadInteger=lambda *args:player,LoadStr=lambda *args:'',
                    UnitAddAbility=lambda unit,aid:added.append((unit,aid)),
                    ZG=lambda unit,aid,*args:added.append((unit,aid)))
                env['Dispatch']()
                self.assertEqual(added,[] if ability is None else [(100+player,int.from_bytes(ability.encode(),'big'))])

    def test_existing_player_assignment_drift_is_rejected(self):
        stage=self.stage()
        raw=(ROOT/'scratch/baseline/war3map.j').read_bytes()
        with self.assertRaises(ValueError):
            stage.prepare_object_script(raw.replace(b'set II[2]=$49303050',b'set II[2]=$49303030'))

    def test_sword_proc_predicates_and_tiers_match_original_for_fifth_player(self):
        from tests.jass_subset import expression
        stage=self.stage()
        script,_=stage.prepare_object_script((ROOT/'scratch/baseline/war3map.j').read_bytes())
        body=functions(script.decode())['xa'][0]
        predicates=[l[3:-5] for l in body.splitlines() if l.startswith('if ') and 'cx(' in l and any(code in l for code in ['$49303030','$49303648','$49303046','$49303045','$49303044'])]
        self.assertEqual(len(predicates),5)
        for tier,(old,new) in enumerate([('I000','IM50'),('I00D','IM51'),('I00E','IM52'),('I00F','IM53'),('I06H','IM54')]):
            outcomes=[]
            for item in [old,new]:
                code=int.from_bytes(item.encode(),'big')
                env=dict(EXGetEventDamageData=lambda _:1,LQ=0,Uo=lambda _:True,
                    GetUnitTypeId=lambda _:0,GetEventDamageSource=lambda:100,
                    GetOwningPlayer=lambda _:5,GetPlayerId=lambda p:p,HQ={5:100},
                    cx=lambda unit,raw:unit==100 and raw==code)
                outcomes.append([eval(expression(re.sub(r'\$([0-9A-F]+)',r'0x\1',p)),{},env) for p in predicates])
            self.assertTrue(outcomes[1][0],new)
            self.assertEqual(outcomes[0],outcomes[1],new)

    def test_fifth_attribute_ability_is_accepted_by_spell_condition(self):
        from tests.jass_subset import execute
        stage=self.stage()
        script,_=stage.prepare_object_script((ROOT/'scratch/baseline/war3map.j').read_bytes())
        code=functions(script.decode())['wu'][0]
        env=execute(re.sub(r'\$([0-9A-F]+)',r'0x\1',code))
        for ability,expected in [('AMJ5',True),('A004',True),('A01P',True),('AInv',False)]:
            env['GetSpellAbilityId']=lambda:int.from_bytes(ability.encode(),'big')
            self.assertEqual(env['wu'](),expected)
