"""Audited free entry points, source quotas and gameplay-only recurring effects."""
import hashlib
import json
from pathlib import Path
import re
from tools.patching import functions, replace_function
from tools.player_stage import calls
from tools.lane_stage import once, block
from tools.progress_schema import progress_module

ROOT=Path(__file__).resolve().parents[1]


def prefix_guard(body, guard):
    at=re.match(r'^function[^\n]+\n(?:local [^\n]*\n)*',body).end()
    return body[:at]+guard+body[at:]


def prepare_free(raw):
    source=raw.decode('utf8').replace('\r\n','\n');original=functions(source)
    pinned=json.loads((ROOT/'data/free-stage-baselines.json').read_text(encoding='utf8'))
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('free baseline drift: '+name)
    if 'MJ_ContentAvailable' in original:raise ValueError('free stage already applied')
    policy=json.loads((ROOT/'data/entitlements.json').read_text(encoding='utf8'))
    bodies={n:b[0] for n,b in original.items()};replaced=0
    for name,body in list(bodies.items()):
        for start,end,args in reversed(list(calls(body,'DzAPI_Map_HasMallItem'))):
            tag=re.search(r',"([^"\n]+)"$',args)
            if tag is None or tag[1] not in policy['tags']:raise ValueError('unaudited mall key: '+name)
            body=body[:start]+'MJ_ContentAvailable('+args+')'+body[end:];replaced+=1
        bodies[name]=body
    # This separate adapter is audited against the same pinned pre-free functions.
    from tools.local_account_policy import apply_account_policy
    bodies,account=apply_account_policy(bodies)
    account_module=(ROOT/'src/local_account_rules.j').read_text(encoding='utf-8-sig')

    bodies['uJ']=prefix_guard(bodies['uJ'],'if MJ_FreePhase!=0 then\nreturn\nendif\n')
    bodies['uJ']=once(bodies['uJ'],'call MJ_LockProgress()\n','call MJ_LockProgress()\nset MJ_FreePhase=1\n')
    bodies['us']=prefix_guard(bodies['us'],'if MJ_FreePhase==2 then\nreturn\nendif\nset MJ_FreePhase=2\n')
    # uY runs for all legacy/new initialization paths. Preserve its effects and use p.
    body=bodies['uY'].replace('function uY takes nothing','function MJ_ApplyFreeEffects takes player p').replace('GetEnumPlayer()','p')
    # Donation content used DS/nickname research, not a mall tag. Apply after
    # all legacy writes, without fabricating donation or progression records.
    body=once(body,'set Fu[GetPlayerId(p)]=-1\n',
        'if MJ_LocalAccountBenefit(p,"DONATION_COSMETIC") then\ncall SetPlayerTechResearchedSwap($52303038,3,p)\nendif\nset Fu[GetPlayerId(p)]=-1\n')
    body=prefix_guard(body,'local integer who=MJ_Index(p)\nif who<0 or MJ_FreePhase<1 or not IsPlayerInForce(p,Fa) then\nreturn\nendif\nif MJ_FreeEffectsApplied[who] then\nreturn\nendif\nset MJ_FreeEffectsApplied[who]=true\n')
    bodies['uY']=body+'function uY takes nothing returns nothing\ncall MJ_ApplyFreeEffects(GetEnumPlayer())\nendfunction\n'

    for name,player in [('ux','GetEnumPlayer()'),('u7','GetOwningPlayer(GetTriggerUnit())')]:
        body=prefix_guard(bodies[name],'if not MJ_BeginHeroOpening('+player+') then\nreturn\nendif\n')
        # The same mode's implicit C-book/BAG3 sources share their explicit free quota.
        for key in ['BOOKC','BAG3']:
            condition=next(l for l in body.splitlines() if l.startswith('if ') and f'MJ_ContentAvailable({player},"{key}")' in l)
            predicate=condition[3:-5]
            if key=='BOOKC' and name=='u7':
                predicate=predicate.replace(' and LoadInteger(DI,StringHash("全局"),$818FF5CF)==2 or ', ' and (LoadInteger(DI,StringHash("全局"),$818FF5CF)==2 or ')+')'
            if key=='BAG3' and name=='u7':
                predicate=predicate.replace(f'MJ_ContentAvailable({player},"BAG3")==true or LoadInteger(DI,StringHash("全局"),$818FF5CF)==1',f'(MJ_ContentAvailable({player},"BAG3")==true or LoadInteger(DI,StringHash("全局"),$818FF5CF)==1)')
            body=once(body,condition,'if ('+predicate+') and MJ_ClaimReward('+player+',"'+key+'") then')
        for key in ['LWJ','PTLB','3FJT','IMBAG','VIP3','VIP0','BOOKD','BOOKB','BOOKA']:
            old=f'MJ_ContentAvailable({player},"{key}")'
            body=once(body,old,f'MJ_ClaimReward({player},"{key}")')
        condition=f'if MJ_ContentAvailable({player},"TRE")==true then'
        old=block(body,condition)+'call SaveUnitHandle(DI,GetHandleId('+player+'),$52513C84,bj_lastCreatedUnit)\n'
        body=once(body,old,f'if MJ_BeginFreeHelper({player},"TRE") then\n'+old+'endif\n')
        bodies[name]=body

    # cl removes the original trigger unit: retain its owner before replacement.
    bodies['u7']=prefix_guard(bodies['u7'].replace('GetOwningPlayer(GetTriggerUnit())','MJ_OpeningPlayer'),
        'local player MJ_OpeningPlayer=GetOwningPlayer(GetTriggerUnit())\n')
    owner='GetOwningPlayer(GetTriggerUnit())'
    bodies['BQp']=prefix_guard(bodies['BQp'],'if not MJ_IsFreePlaying('+owner+') then\nreturn\nendif\n')
    spells=['41304D44','41304D45','41304D46','41304D47','41304D48','41304D49','41304E41']
    bodies['BRc']='function BRc takes nothing returns boolean\nreturn MJ_IsFreePlaying('+owner+') and MJ_ContentAvailable('+owner+',"TXZ") and ('+' or '.join('GetSpellAbilityId()==$'+v for v in ['41304F32']+spells)+')\nendfunction\n'
    body=bodies['BRd']
    conditions=[l for l in body.splitlines() if l.startswith('if LoadBoolean(DI,') and 'GetSpellAbilityId()' in l]
    if len(conditions)!=7:raise ValueError('pass reward guards drift')
    for tier,(condition,spell) in enumerate(zip(conditions,spells)):
        body=once(body,condition,'if (GetSpellAbilityId()==$'+spell+' or GetSpellAbilityId()==$41304F32) and MJ_ClaimPassReward('+owner+','+str(tier)+') then')
    bodies['BRd']=prefix_guard(body,'if not MJ_IsFreePlaying('+owner+') then\nreturn\nendif\n')

    # A persistent timer skips disabled growth. Toggling it back on never creates another.
    timer_player='LoadPlayerHandle(EK,GetHandleId(GetExpiredTimer()),$A59BB4C6)'
    for name in ['vz','v7','wI','BPk']:
        body=bodies[name];condition=next(l for l in body.splitlines() if l.startswith('if '))
        before,after=condition[3:-5].split(' and IsUnitAliveBJ',1)
        body=once(body,condition,'if MJ_IsFreePlaying('+timer_player+') and ('+before+') and IsUnitAliveBJ'+after+' then')
        body=once(body,'else\ncall FlushChildHashtable(EK,GetHandleId(GetExpiredTimer()))\ncall DestroyTimer(GetExpiredTimer())\nendif','endif')
        bodies[name]=body
    for name in ['v0','wJ']:
        body=bodies[name]
        body=body.replace('if IsUnitAliveBJ','if MJ_IsFreePlaying('+timer_player+') and IsUnitAliveBJ',1)
        body=once(body,'else\ncall FlushChildHashtable(EK,GetHandleId(GetExpiredTimer()))\ncall DestroyTimer(GetExpiredTimer())\nendif','endif')
        bodies[name]=body
    body=bodies['BPl']
    old='set GB=CreateTimer()\ncall SavePlayerHandle(EK,GetHandleId(GB),$A59BB4C6,'+owner+')\ncall TimerStart(GB,30.,true,function BPk)\n'
    bodies['BPl']=once(body,old,'')

    for name in ['v1','v8','wK','wW','wZ']:
        body=bodies[name];player='GetEnumPlayer()' if name in ['v1','v8','wK'] else owner
        condition=next(l for l in body.splitlines() if l.startswith('if ') and l.count('MJ_ContentAvailable(')>=5)
        old=block(body,condition)
        fixed=old.replace(condition,'if MJ_ClaimFullSet('+player+',HQ[GetPlayerId('+player+')]) then',1)
        if name in ['wW','wZ']:
            body=once(body,old,fixed)
        else:
            body=once(body,old,'')
            body=prefix_guard(body,fixed)
        if name in ['v1','v8','wK']:
            body=prefix_guard(body,'if not MJ_BeginHeroBenefits('+player+',HQ[GetPlayerId('+player+')]) then\nreturn\nendif\n')
            body=body.replace('call SetPlayerHandicapXPBJ(GetOwningPlayer(GetTriggerUnit()),GetPlayerHandicapXPBJ(GetOwningPlayer(GetTriggerUnit()))+20.)','call SetPlayerHandicapXPBJ(GetEnumPlayer(),GetPlayerHandicapXPBJ(GetEnumPlayer())+20.)')
            for key in ['PET1','PET2']:
                conditions=[l for l in body.splitlines() if l.startswith('if ') and f'MJ_ContentAvailable({player},"{key}")' in l]
                if not conditions:continue
                condition=conditions[0]
                body=once(body,condition,'if ('+condition[3:-5]+') and MJ_BeginFreeHelper('+player+',"'+key+'") then')
            # Initial envelope reward is independent of later wave milestone rewards.
            body=body.replace(f'MJ_ContentAvailable({player},"TXCH1")',f'MJ_ClaimReward({player},"TXCH1")')
        bodies[name]=body
    # uY's collection research unlock uses the configured preset, not fake ownership.
    body=bodies['uY'];condition=next(l for l in body.splitlines() if l.startswith('if ') and l.count('MJ_ContentAvailable(')>=5)
    bodies['uY']=once(body,condition,'if MJ_FreeFullSet then')

    for name in ['v3','wB']:
        body=bodies[name]
        body=body.replace('MJ_ContentAvailable(GetEnumPlayer(),"ZBQ1")','MJ_ClaimFreeMilestone(GetEnumPlayer(),"ZBQ1",LoadInteger(DI,StringHash("全局"),$8B909B14))')
        body=body.replace('MJ_ContentAvailable(GetEnumPlayer(),"TXCH1")','MJ_ClaimFreeMilestone(GetEnumPlayer(),"TXCH1",LoadInteger(DI,StringHash("全局"),$8B909B14))')
        bodies[name]=prefix_guard(body,'if not MJ_IsFreePlaying(GetEnumPlayer()) then\nreturn\nendif\n')
    for name in ['wL','vq']:
        bodies[name]=prefix_guard(bodies[name],'if not MJ_IsFreePlaying(GetEnumPlayer()) then\nreturn\nendif\n')
    for name in ['BRU','BRX']:
        body=bodies[name];line=next(l for l in body.splitlines() if 'TriggerRegisterPlayerChatEvent' in l and 'Player(3)' in l)
        bodies[name]=once(body,line+'\n',line+'\n'+line.replace('Player(3)','Player(5)')+'\n')

    # Manual, durable once/profile mastery gift. No automatic mastery is granted.
    body=bodies['BBy'];condition=next(l for l in body.splitlines() if l.startswith('if ') and '"LWJ"' in l)
    old=block(body,condition);new=old.replace(condition,'if MJ_IsFreePlaying('+owner+') and '+condition[3:],1).replace('GetRandomInt(1,148)','GetRandomInt(1,158)')
    counter='call SaveInteger(DI,GetHandleId('+owner+'),$302FFF73,LoadInteger(DI,GetHandleId('+owner+'),$302FFF73)+1)\n'
    if new.count(counter)!=2:raise ValueError('LWJ mastery counter drift')
    # Last increment duplicated the earlier count; maintain one count and one persistence write.
    at=new.rfind(counter);new=new[:at]+new[at+len(counter):]
    bodies['BBy']=once(body,old,new)

    changes=[]
    for name,body in bodies.items():
        if body!=original[name][0]:
            if name not in pinned:raise ValueError('unreviewed free function: '+name)
            source=replace_function(source,name,pinned[name],body)
            changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    module=(ROOT/'src/free_rules.j').read_text(encoding='utf-8-sig')+'\n'+account_module
    declarations=re.findall(r'^globals\n(.*?)^endglobals\n',module,re.M|re.S)
    module=re.sub(r'^globals\n.*?^endglobals\n','',module,flags=re.M|re.S)
    progress=progress_module();g=re.search(r'^globals\n.*?^endglobals\n',progress,re.M|re.S)
    source=once(source,progress[g.end():],progress[g.end():]+module)
    source=once(source,'\nendglobals\n','\n'+''.join(declarations)+'endglobals\n')
    if list(calls(source,'DzAPI_Map_HasMallItem')):raise ValueError('mall calls remain')
    return source.encode(),dict(mall_calls_replaced=replaced,changes=changes,account_policy=account,runtime_verified=False)
