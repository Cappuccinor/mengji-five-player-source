"""Independent fifth infinite bag and VIP skill-choice objects, before free policy."""
import hashlib
import json
from pathlib import Path
import re

from tools.lane_stage import once
from tools.object_stage import clone_sections, clone_slk
from tools.patching import functions, replace_function
from tools.player_stage import calls

ROOT=Path(__file__).resolve().parents[1]
BAG='$494D3546'  # IM5F; separate from the fifteen existing IM50..IM5E items.
SOURCE_BAG='$4930354A'  # Actual original I05J object.
PENDANT='$494D3547'  # IM5G, cloned from original fourth-player I040.


def _baselines():
    return json.loads((ROOT/'data/free-objects-stage-baselines.json').read_text(encoding='utf8'))


def prepare_free_objects(members):
    """Accept four pinned object_stage tables; clone items and correct paid labels."""
    expected=_baselines()['members']
    for name,digest in expected.items():
        if name not in members or hashlib.sha256(members[name]).hexdigest()!=digest:
            raise ValueError('free object table baseline drift: '+name)
    clones={'I05J':'IM5F','I040':'IM5G'}
    result={
        r'Units\ItemData.slk':clone_slk(members[r'Units\ItemData.slk'],clones),
        r'Units\ItemStrings.txt':clone_sections(members[r'Units\ItemStrings.txt'],clones),
    }
    from tools.paid_content_objects import free_ability_text
    result[r'Units\CampaignAbilityStrings.txt']=free_ability_text(members[r'Units\CampaignAbilityStrings.txt'])
    return result,dict(items=clones,converted_player_id=6,runtime_verified=False,
                       members={n:hashlib.sha256(raw).hexdigest() for n,raw in result.items()})


def _dialog_module():
    result='globals\ndialog MJ_FreeActiveDialog=null\ndialog MJ_FreePassiveDialog=null\nendglobals\n'
    result+='function MJ_FreeDialogOwner takes dialog chosen,boolean passive returns integer\n'
    for passive,dialogs in [(False,['Fm','Fo','Fn','Fp','MJ_FreeActiveDialog']),
                           (True,['Fq','Fr','Fs','Ft','MJ_FreePassiveDialog'])]:
        result+='if '+('passive' if passive else 'not passive')+' then\n'
        for index,name in zip([0,1,2,3,5],dialogs):
            result+=f'if chosen=={name} then\nreturn {index}\nendif\n'
        result+='endif\n'
    return result+'return -1\nendfunction\n'


def _choice_handler(body,passive):
    """Resolve the actual event sender before touching HQ or consuming pending state."""
    offset=6 if passive else 1
    locals_end=re.match(r'^function[^\n]+\n(?:local [^\n]*\n)*',body).end()
    prefix='local integer MJ_FreeDialogIndex=-1\n'
    prefix+=f'set MJ_FreeDialogIndex=MJ_FreeDialogOwner(GetClickedDialogBJ(),{str(passive).lower()})\n'
    prefix+='if MJ_FreeDialogIndex<0 then\nreturn\nendif\n'
    prefix+='if GetPlayerId(GetTriggerPlayer())!=MJ_FreeDialogIndex or Fu[MJ_FreeDialogIndex]!=MJ_FreeDialogIndex or HQ[MJ_FreeDialogIndex]==null or not IsPlayerInForce(GetTriggerPlayer(),Fa) then\nreturn\nendif\n'
    prefix+=f'if GetClickedButtonBJ()!=GI[(MJ_FreeDialogIndex+1)*10+{offset}] and GetClickedButtonBJ()!=GI[(MJ_FreeDialogIndex+1)*10+{offset+1}] then\nreturn\nendif\n'
    body=body[:locals_end]+prefix+body[locals_end:]
    start=body.index('if GetClickedDialogBJ()=='+('Fq' if passive else 'Fm')+' then\n')
    if passive:
        end=body.index('if LoadInteger(DI,GetHandleId(HQ[',start)
    else:
        end=body.index('if GetClickedButtonBJ()==GI[11]',start)
    body=body[:start]+'call SaveInteger(EK,GetHandleId(GetTriggeringTrigger())*F5,$25DAB820,MJ_FreeDialogIndex)\nset Fu[MJ_FreeDialogIndex]=-1\n'+body[end:]
    for old,new in ([(46,66),(47,67)] if passive else [(41,61),(42,62)]):
        needle=f'GetClickedButtonBJ()==GI[{old}] then'
        body=once(body,needle,f'GetClickedButtonBJ()==GI[{old}] or GetClickedButtonBJ()==GI[{new}] then')
    return body


def prepare_free_object_script(raw):
    source=raw.decode('utf8').replace('\r\n','\n');original=functions(source)
    pinned=_baselines()['functions']
    if 'MJ_FreeDialogOwner' in original:raise ValueError('free object script stage already applied')
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('free object script baseline drift: '+name)
    bodies={name:original[name][0] for name in pinned}
    bodies['uW']=once(bodies['uW'],'set IL[4]=$49303555\n','set IL[4]=$49303555\nset IL[6]='+BAG+'\n')
    # All three income-damage handlers enumerate the original four bag types.
    for name in ['xa','xd','xi']:
        body=bodies[name];edits=[]
        for start,end,args in calls(body,'cx'):
            if args.endswith(','+SOURCE_BAG):
                if body[end:end+6]!='==true':raise ValueError('bag income predicate drift: '+name)
                edits.append((start,end+6,'('+body[start:end+6]+' or cx('+args.rsplit(',',1)[0]+','+BAG+')==true)'))
        if len(edits)!=1:raise ValueError('bag income count drift: '+name)
        for start,end,new in reversed(edits):body=body[:start]+new+body[end:]
        bodies[name]=body
    body=bodies['BDV']
    line=next(l for l in body.splitlines() if l.startswith('if ') and SOURCE_BAG in l)
    gate,predicates=line[3:-5].split(' and ',1)
    last=next(args for _,_,args in calls(predicates,'cx') if args.endswith(',$49303555'))
    replacement='if '+gate+' and ('+predicates+' or cx('+last.rsplit(',',1)[0]+','+BAG+')==true) then'
    bodies['BDV']=once(body,line,replacement)
    body=bodies['yz'];lines=body.splitlines(keepends=True)
    index=next(i for i,l in enumerate(lines) if '$D14F34A9,$49303555)' in l)
    pair=''.join(lines[index:index+2])
    bodies['yz']=once(body,pair,pair+pair.replace('$49303555',BAG))
    body=bodies['yz'];lines=body.splitlines(keepends=True)
    index=next(i for i,l in enumerate(lines) if '$D14F34A9,$49303430)' in l)
    pair=''.join(lines[index:index+2])
    bodies['yz']=once(body,pair,pair+pair.replace('$49303430',PENDANT))
    # Keep the original same-category restriction, with a grouped one-golden-bag rule.
    body=bodies['zN'];line=next(l for l in body.splitlines() if l.startswith('if UnitItemInSlotBJ(') and SOURCE_BAG in l)
    other='UnitItemInSlotBJ(GetTriggerUnit(),Gi)';item='GetManipulatedItem()'
    ids=['$49303834','$4930384B','$4930384C','$4930384D','$49303334',SOURCE_BAG,'$4930354C','$4930354E','$49303555',BAG]
    def bag(handle):return '('+' or '.join(f'GetItemTypeId({handle})=={code}' for code in ids)+')'
    categories='('+' or '.join(f'GetItemType({item})=={kind}' for kind in ['ITEM_TYPE_ARTIFACT','ITEM_TYPE_PURCHASABLE','ITEM_TYPE_CAMPAIGN'])+')'
    restriction=f'if {other}!={item} and IsUnitType(GetTriggerUnit(),UNIT_TYPE_HERO)==true and ((GetItemType({other})==GetItemType({item}) and {categories}) or ({bag(item)} and {bag(other)})) then'
    bodies['zN']=once(body,line,restriction)
    body=bodies['zN'];needle='GetItemTypeId(GetManipulatedItem())==$49303430'
    bodies['zN']=once(body,needle,'('+needle+' or GetItemTypeId(GetManipulatedItem())=='+PENDANT+')')
    body=bodies['BPS'];owner='LoadPlayerHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$A59BB4C6)'
    anchor='call UnitAddItemByIdSwapped($49303430,HQ[GetPlayerId('+owner+')])\nelse\nendif'
    replacement='call UnitAddItemByIdSwapped($49303430,HQ[GetPlayerId('+owner+')])\nelse\nif '+owner+'==Player(5) then\ncall UnitAddItemByIdSwapped('+PENDANT+',HQ[GetPlayerId('+owner+')])\nendif\nendif'
    bodies['BPS']=once(body,anchor,replacement)
    bodies['sT']=once(bodies['sT'],'set Ft=DialogCreate()\n','set Ft=DialogCreate()\nset MJ_FreeActiveDialog=DialogCreate()\nset MJ_FreePassiveDialog=DialogCreate()\nset Fu[5]=-1\n')
    body=bodies['BBq']
    for old,new in [('Fp','MJ_FreeActiveDialog'),('Ft','MJ_FreePassiveDialog')]:
        anchor=f'call SaveDialogHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$DFB448FB,{old})\nelse\nendif'
        addition=f'call SaveDialogHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$DFB448FB,{old})\nelse\nif GetOwningPlayer(GetTriggerUnit())==Player(5) then\ncall DialogClear({new})\ncall SaveDialogHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$DFB448FB,{new})\nendif\nendif'
        body=once(body,anchor,addition)
    bodies['BBq']=body
    bodies['BB0']=_choice_handler(bodies['BB0'],False)
    bodies['BB2']=_choice_handler(bodies['BB2'],True)
    for name,trig,old,new in [('BB1','MD','Fp','MJ_FreeActiveDialog'),('BB3','MF','Ft','MJ_FreePassiveDialog')]:
        anchor=f'call TriggerRegisterDialogEvent({trig},{old})\n'
        bodies[name]=once(bodies[name],anchor,anchor+f'call TriggerRegisterDialogEvent({trig},{new})\n')
    changes=[]
    for name,body in bodies.items():
        if body!=original[name][0]:
            source=replace_function(source,name,pinned[name],body)
            changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    # Selection reassembles the exact roster/progress modules; do not split their
    # leading comment from the first function when adding these helpers.
    module=_dialog_module();declarations=re.match(r'^globals\n(.*?)endglobals\n',module,re.S)
    source=once(source,'\nendglobals\n','\n'+declarations[1]+'endglobals\n')
    roster=(ROOT/'src/roster.j').read_text(encoding='utf8')
    source=once(source,roster,roster+module[declarations.end():])
    return source.encode(),dict(changes=changes,item='IM5F',pendant='IM5G',converted_player_id=6,
        audited_unchanged=['zC'],dialogs=['MJ_FreeActiveDialog','MJ_FreePassiveDialog'],runtime_verified=False)
