"""Audited fifth-lane redistribution, shared damage, failure and leave hooks."""
import hashlib
import json
from pathlib import Path
from tools.patching import functions, replace_function
from tools.lane_stage import block, once, rename_code

ROOT=Path(__file__).resolve().parents[1]


def prepare_combat(raw):
    source=raw.decode('utf8').replace('\r\n','\n'); original=functions(source)
    pinned=json.loads((ROOT/'data/combat-stage-baselines.json').read_text(encoding='utf8'))
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('combat baseline drift: '+name)
    if 'MJ5_FailLane' in original: raise ValueError('combat stage already applied')
    bodies={n:original[n][0] for n in pinned};changes=[]
    def append(name,extra):
        bodies[name]=once(bodies[name],'endfunction\n',extra+'endfunction\n')
    def insert_before(name,extra):
        nonlocal source
        pos=functions(source)[name].start();source=source[:pos]+extra+source[pos:]

    # The existing four functions are identical except the excluded logical lane.
    template=original['BDD'][0]
    for name,index in [('BDB',1),('BDF',3),('BDH',4)]:
        normalized=original[name][0].replace('function '+name+' ','function BDD ').replace(f'if Gi!={index} then','if Gi!=2 then')
        if normalized!=template:raise ValueError('redistributor family drift: '+name)
    redistribution=template.replace('function BDD ','function MJ5_Redistribute ').replace('if Gi!=2 then','if Gi!=5 then')
    # Do not send new monsters to a lane already eliminated from the game force.
    for name in ['BDB','BDD','BDF','BDH']:
        bodies[name]=once(bodies[name],'if Gi!=','if IsPlayerInForce(MJ_Human1(Gi),Fa) and Gi!=')
    redistribution=once(redistribution,'if Gi!=','if IsPlayerInForce(MJ_Human1(Gi),Fa) and Gi!=')
    append('BDI','set MJ5_Redistribution=CreateTrigger()\ncall DisableTrigger(MJ5_Redistribution)\ncall TriggerAddAction(MJ5_Redistribution,function MJ5_Redistribute)\n')
    body=bodies['BDV'];old='if GetOwningPlayer(GetKillingUnitBJ())==Player(3) then\ncall TriggerExecute(Mw)\nelse\nendif'
    bodies['BDV']=once(body,old,old[:-len('endif')]+'if GetOwningPlayer(GetKillingUnitBJ())==Player(5) then\ncall TriggerExecute(MJ5_Redistribution)\nendif\nendif')

    # Replace only the audited contribution block, leaving wave timers/other modes intact.
    body=bodies['wG'];start=body.index('if IsUnitAliveBJ(Cz)==true then\n');end=body.index('call TriggerExecute(GY)\n',start)
    body=body[:start]+'call MJ_RefreshSpawnIntervals()\n'+body[end:]
    anchor='call SaveReal(DI,GetHandleId(Player(3)),$42264FE6,1.)\n'
    bodies['wG']=once(body,anchor,anchor+anchor.replace('Player(3)','Player(5)'))

    # A zero/removed-lane interval must never reach 10./interval or TimerStart.
    body=bodies['BC5']
    condition=next(line for line in body.splitlines() if line.startswith('if GetPlayerController('))
    owner='LoadPlayerHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$A59BB4C6)'
    positive='LoadReal(DI,GetHandleId('+owner+'),$42264FE6)>0.'
    bodies['BC5']=once(body,condition,condition[:-5]+' and IsPlayerInForce('+owner+',Fa) and '+positive+' then')
    body=bodies['BC4']
    condition=next(line for line in body.splitlines() if line.startswith('if IsUnitAliveBJ('))
    owner='LoadPlayerHandle(EK,GetHandleId(GetExpiredTimer()),$A59BB4C6)'
    bodies['BC4']=once(body,condition,'if IsPlayerInForce('+owner+',Fa) and '+condition[3:])

    # Same protection behavior as the NE lane, mapped to the fifth human/enemy.
    filter_code=original['BPF'][0].replace('function BPF ','function MJ5_ProtectionFilter ').replace('Player(9)','Player(6)')
    body=bodies['BPL']
    for human,enemy in [(0,8),(1,9),(2,10),(3,11)]:
        condition=f'if GetPlayerState(Player({enemy}),PLAYER_STATE_RESOURCE_FOOD_USED)>=R2I(I2R(LoadInteger(DI,StringHash("全局"),$B02D0480)+LoadInteger(DI,GetHandleId(Player({human})),$ECB99D6C))*1.) then'
        branch=block(body,condition)
        guarded=f'if IsPlayerInForce(Player({human}),Fa) then\n'+branch+'endif\n'
        body=once(body,branch,guarded)
        if human==1:
            fifth=guarded.replace('Player(1)','Player(5)').replace('Player(9)','Player(6)').replace('HQ[1]','HQ[5]')
            fifth=rename_code(fifth,{'HS':'MJ5_Failure','BPF':'MJ5_ProtectionFilter'})
    marker='call FlushChildHashtable(EK,GetHandleId(GetTriggeringTrigger())*F5)\n'
    bodies['BPL']=once(body,marker,fifth+marker)
    body=bodies['BPC'];tail=body.splitlines()[1].removeprefix('return ').split(' or ')[-1]
    bodies['BPC']=once(body,tail+'\n',tail+' or '+tail.replace('Player(11)','Player(6)')+'\n')

    # Global warning and grace-period predicates include all five humans, under the threshold/mode guard.
    body=bodies['BO9'];lines=body.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if line.startswith('if ') and 'DzAPI_Map_HasMallItem(Player(0),"VIP3")' in line:
            checks=' or '.join(f'(IsPlayerInForce(Player({p}),Fa) and DzAPI_Map_HasMallItem(Player({p}),"VIP3")==true)' for p in [0,1,2,3,5])
            lines[i]='if LoadBoolean(DI,StringHash("全局"),$88CEC9C2)==false and ('+checks+') then\n'
        for key in ['$66DBBCC9','$B0CC1918']:
            if line.startswith('if ') and 'LoadBoolean(DI,GetHandleId(Player(0)),'+key in line:
                threshold=line.split(' and ',1)[0]
                checks=' or '.join(f'(IsPlayerInForce(Player({p}),Fa) and LoadBoolean(DI,GetHandleId(Player({p})),{key})==true)' for p in [0,1,2,3,5])
                lines[i]=threshold+' and ('+checks+') then\n'
    bodies['BO9']=''.join(lines)

    # Reuse the existing cleanup callbacks; their group selectors are lane-specific.
    failure=original['BOi'][0].replace('function BOi ','function MJ5_FailLane ').replace('Player(1)','Player(5)')
    def guard_failure(body,p):
        marker=next(l for l in body.splitlines()[1:] if not l.startswith('local '))+'\n'
        return once(body,marker,f'if not IsPlayerInForce(Player({p}),Fa) then\nreturn\nendif\n'+marker)
    for name,p in [('BOb',0),('BOi',1),('BOp',2),('BOw',3)]:bodies[name]=guard_failure(bodies[name],p)
    failure=guard_failure(failure,5)
    append('BOx','set MJ5_Failure=CreateTrigger()\ncall DisableTrigger(MJ5_Failure)\ncall TriggerAddAction(MJ5_Failure,function MJ5_FailLane)\n')
    for name in ['wG','BOK','BOT','BOb','BOi','BOp','BOw']:
        for action in ['EnableTrigger','DisableTrigger']:
            anchor=f'call {action}(HU)\n'
            if anchor in bodies[name]:bodies[name]=once(bodies[name],anchor,anchor+f'call {action}(MJ5_Failure)\n')
    failure=once(failure,'call DisableTrigger(HU)\n','call DisableTrigger(HU)\ncall DisableTrigger(MJ5_Failure)\n')
    body=bodies['tq'];anchor='if GetEnumPlayer()==Player(3) then\ncall EnableTrigger(HU)\ncall TriggerExecute(HU)\nelse\nendif'
    bodies['tq']=once(body,anchor,anchor[:-len('endif')]+'if GetEnumPlayer()==Player(5) then\ncall EnableTrigger(MJ5_Failure)\ncall TriggerExecute(MJ5_Failure)\nendif\nendif')

    # Actual leave registration was previously restricted to four slots.
    append('BOL','call TriggerRegisterPlayerEventLeave(Q2,Player(5))\n')
    for name,selector in [('BOK','GetTriggerPlayer()'),('BOT','GetTriggerPlayer()'),('BN3','LoadPlayerHandle(EK,GetHandleId(GetTriggeringTrigger())*F5,$A59BB4C6)')]:
        branch=block(bodies[name],f'if {selector}==Player(1) then')
        extra=branch.replace('Player(1)','Player(5)').replace('bj_GATEOPERATION_CLOSE,CX','bj_GATEOPERATION_CLOSE,MJ5_CX')
        bodies[name]=once(bodies[name],branch,branch+extra)
    # Logical vote index 5 maps to actual human slot 5, never NPC Player(4).
    body=bodies['BN3'];expression='S2I(SubStringBJ(GetEventPlayerChatString(),6,6))'
    body=once(body,expression+'<=4',expression+'<=5')
    body=once(body,'ConvertedPlayer('+expression+')','MJ_Human1('+expression+')')
    body=body.replace('-kick4','-kick5').replace('1-4代表玩家数','1-5代表逻辑玩家序号')
    bodies['BN3']=body
    # Explicit four-slot global defeat paths also need the fifth human.
    for name in ['BOT']:
        lines=bodies[name].splitlines(keepends=True)
        for i in range(len(lines)-1,-1,-1):
            if lines[i].startswith('call CustomDefeatBJ(Player(3),'):
                lines.insert(i+1,lines[i].replace('Player(3)','Player(5)'))
        bodies[name]=''.join(lines)

    for name,body in bodies.items():
        if body!=original[name][0]:
            source=replace_function(source,name,pinned[name],body)
            changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    insert_before('wG',(ROOT/'src/combat_state.j').read_text(encoding='utf-8-sig').replace('\r\n','\n')+'\n')
    insert_before('BDI',redistribution+'\n')
    insert_before('BOx',failure+'\n')
    insert_before('BPL',filter_code+'\n')
    source=once(source,'\nendglobals\n','\ntrigger MJ5_Redistribution=null\ntrigger MJ5_Failure=null\nendglobals\n')
    return source.encode(),dict(changes=changes,human_slot=5,enemy_slot=6,runtime_verified=False,
        remaining='legacy modes, platform isolation, UI/start boundary and engine/multiplayer validation')
