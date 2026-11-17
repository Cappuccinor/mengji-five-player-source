"""Pinned fifth-player skill dispatch, after free policy and before selection."""
import hashlib
import json
from pathlib import Path
import re

from tools.lane_stage import block,once
from tools.patching import functions,replace_function

ROOT=Path(__file__).resolve().parents[1]


def _module():
    # Original unique-hero skills select one owner, never a new stacking bonus.
    return '''function MJ_FifthSandCoinReward takes player killer returns nothing
local integer i=0
local player p=null
if LoadBoolean(DI,StringHash("全局"),$A63650E) or GetUnitTypeId(HQ[GetPlayerId(killer)])==$48303044 then
return
endif
loop
exitwhen i>=5
set p=MJ_Player(i)
if IsPlayerInForce(p,Fa) and HQ[GetPlayerId(p)]!=null and GetUnitTypeId(HQ[GetPlayerId(p)])==$48303044 then
call AdjustPlayerStateBJ(3*LoadInteger(DI,StringHash("全局"),$8B909B14),p,PLAYER_STATE_RESOURCE_GOLD)
set p=null
return
endif
set i=i+1
endloop
set p=null
endfunction

function MJ_FifthSpellPassiveOwner takes unit caster returns integer
local integer i=0
local integer slot=-1
local player p=null
if not IsUnitInForce(caster,Fb) then
return -1
endif
loop
exitwhen i>=5
set p=MJ_Player(i)
set slot=GetPlayerId(p)
if IsPlayerInForce(p,Fa) and HQ[slot]!=null and bt(caster,HQ[slot])<=700. and LoadInteger(DI,GetHandleId(HQ[slot]),$99CB8E52)==309 then
set p=null
return slot
endif
set i=i+1
endloop
set p=null
return -1
endfunction

function MJ_FifthTeammateGold takes player owner,integer amount returns nothing
local integer i=0
local player p=null
loop
exitwhen i>=5
set p=MJ_Player(i)
if p!=owner and IsPlayerInForce(p,Fa) then
call AdjustPlayerStateBJ(amount,p,PLAYER_STATE_RESOURCE_GOLD)
endif
set i=i+1
endloop
set p=null
endfunction
'''


def prepare_fifth_skills(raw):
    source=raw.decode('utf8').replace('\r\n','\n');original=functions(source)
    pinned=json.loads((ROOT/'data/fifth-skill-stage-baselines.json').read_text(encoding='utf8'))['functions']
    if 'MJ_FifthSandCoinReward' in original:raise ValueError('fifth skill stage already applied')
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('fifth skill baseline drift: '+name)
    bodies={name:original[name][0] for name in ['BDV','BMP','BMS','ws']}
    body=bodies['BDV']
    condition=next(line for line in body.splitlines() if line.startswith('if ') and
                   'GetKillingUnitBJ()' in line and 'GetUnitTypeId(HQ[0])==$48303044' in line)
    bodies['BDV']=once(body,block(body,condition),
        'call MJ_FifthSandCoinReward(GetOwningPlayer(GetKillingUnitBJ()))\n')
    bodies['BMP']='function BMP takes nothing returns boolean\nreturn MJ_FifthSpellPassiveOwner(GetTriggerUnit())>=0\nendfunction\n'
    body=bodies['BMS'];locals_end=re.match(r'^function[^\n]+\n(?:local [^\n]*\n)*',body).end()
    guard='local integer MJ_FifthOwner=MJ_FifthSpellPassiveOwner(GetTriggerUnit())\nif MJ_FifthOwner<0 then\nreturn\nendif\n'
    body=body[:locals_end]+guard+body[locals_end:]
    condition=next(line for line in body.splitlines() if line.startswith('if bt(') and 'HQ[0]' in line)
    bodies['BMS']=once(body,block(body,condition),
        'call SaveInteger(EK,GetHandleId(GetTriggeringTrigger())*F5,$25DAB820,MJ_FifthOwner)\n')
    body=bodies['ws'];old=''
    for slot in range(4):
        old+=block(body,f'if GetOwningPlayer(GetTriggerUnit())!=Player({slot}) then')
    bodies['ws']=once(body,old,
        'call MJ_FifthTeammateGold(GetOwningPlayer(GetTriggerUnit()),LoadInteger(EK,GetHandleId(GetTriggeringTrigger())*F5,$9DA51395))\n')
    changes=[]
    for name,body in bodies.items():
        source=replace_function(source,name,pinned[name],body)
        changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    # bt is an original JASS helper: insert after its declaration and before ws,
    # the earliest changed consumer. Preserve roster/progress module boundaries.
    source=once(source,bodies['ws'],_module()+bodies['ws'])
    return source.encode(),dict(changes=changes,audited_unchanged=['BMQ','BMR','BMT'],
        human_slots=[0,1,2,3,5],single_recipient_skills=['sand_coin','spell_passive_309'],
        runtime_verified=False)
