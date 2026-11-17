"""Route progress locally and remove audited account writes/legacy account penalties."""
import hashlib
import json
from pathlib import Path
import re
from tools.patching import functions,replace_function,inject_module
from tools.player_stage import calls
from tools.lane_stage import block,once
from tools.progress_schema import progress_module,emit_schema

ROOT=Path(__file__).resolve().parents[1]
WRAPPERS={
'TT':'function TT takes player GC,string GH,integer Ee returns nothing\ncall MJ_SetInt(GC,GH,Ee)\nendfunction\n',
'TU':'function TU takes player GC,string GH returns integer\nreturn MJ_GetInt(GC,GH)\nendfunction\n',
'TY':'function TY takes player GC,string GH,boolean Ee returns nothing\ncall MJ_SetBool(GC,GH,Ee)\nendfunction\n',
'TZ':'function TZ takes player GC,string GH returns boolean\nreturn MJ_GetBool(GC,GH)\nendfunction\n',
'Ta':'function Ta takes player GC,string GH,string Ee returns nothing\ncall MJ_SetString(GC,GH,Ee)\nendfunction\n',
'Tg':'function Tg takes player GC,string GH returns nothing\ncall MJ_DeleteProgressKey(GC,GH)\nendfunction\n',
'mp':'function mp takes player GC,string GH returns boolean\nreturn StringLength(MJ_GetString(GC,GH))>0\nendfunction\n',
'mr':'function mr takes player GC,string GH returns string\nreturn MJ_GetString(GC,GH)\nendfunction\n',
'ms':'function ms takes player GC,string GH,string Ee returns nothing\ncall MJ_SetString(GC,GH,Ee)\nendfunction\n',
'Ty':'function Ty takes player GC,string GD,string GE,integer Ee returns nothing\nreturn\nendfunction\n'}
WRITES=['DzAPI_Map_Stat_SetStat','DzAPI_Map_Ladder_SetStat','DzAPI_Map_Ladder_SetPlayerStat']


def prepare_platform(raw):
    source=raw.decode('utf8').replace('\r\n','\n');original=functions(source)
    pinned=json.loads((ROOT/'data/platform-stage-baselines.json').read_text(encoding='utf8'))
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:raise ValueError('platform baseline drift: '+name)
    if 'MJ_InitProgress' in original:raise ValueError('platform stage already applied')
    data=json.loads((ROOT/'data/progress-keys.json').read_text(encoding='utf8'))
    if (ROOT/'src/progress_schema.j').read_text(encoding='utf-8-sig').replace('\r\n','\n')!=emit_schema(data):raise ValueError('progress schema source stale')
    bodies={n:m[0] for n,m in original.items()};bodies.update(WRAPPERS)
    for name in ['t5','t8']:
        bodies[name]=f'function {name} takes nothing returns nothing\ncall MJ_InitProgress()\ncall DisableTrigger(GetTriggeringTrigger())\ncall DestroyTrigger(GetTriggeringTrigger())\nendfunction\n'
    bodies['t7']='function t7 takes nothing returns nothing\ncall FlushChildHashtable(EK,GetHandleId(GetExpiredTimer()))\ncall DestroyTimer(GetExpiredTimer())\nendfunction\n'
    body=bodies['un'];condition=next(l for l in body.splitlines() if l.startswith('if ') and ',$DF3ECBC7)>500 then' in l)
    body=once(body,block(body,condition),'')
    condition=next(l for l in body.splitlines() if l.startswith('if DzAPI_Map_GetMapLevel('))
    bodies['un']=once(body,block(body,condition),'')
    body=bodies['vu'];condition=next(l for l in body.splitlines() if l.startswith('if ') and '$BC468F0D)+199' in l)
    bodies['vu']=once(body,block(body,condition),'')
    for name in ['v4','wR']:
        body=bodies[name];condition=next(l for l in body.splitlines() if l.startswith('if DzAPI_Map_GetMapLevel(') and '$F96A1C62' in l)
        old=block(body,condition)
        # The else path is the ordinary mastery write; retain it rather than erase growth.
        tail=old.rsplit('\nelse\n',1)[1]
        if not tail.endswith('endif\n'):raise ValueError('mastery account branch drift')
        bodies[name]=once(body,old,tail[:-len('endif\n')])
    body=bodies['uY']
    for predicate in [lambda l:'$781A40EB)>=10 and TZ(' in l,lambda l:'$24502D41)>RequestExtraIntegerData(45,' in l]:
        condition=next(l for l in body.splitlines() if l.startswith('if ') and predicate(l))
        body=once(body,block(body,condition),'')
    # The display's own-game count uses the standalone counter, not old account matches.
    body=body.replace('RequestExtraIntegerData(45,GetEnumPlayer(),null,null,false,0,0,0)','MJ_GetInt(GetEnumPlayer(),"GGC")')
    bodies['uY']=body
    # All initialization paths flow through GN/uJ, including the direct legacy path.
    body=bodies['uJ'];prefix=re.match(r'^function[^\n]+\n(?:local [^\n]*\n)*',body).end()
    guard='if MJ_AnyProgressImportPending() then\nif not MJ_ProgressStartDeferred then\nset MJ_ProgressStartDeferred=true\nset GB=CreateTimer()\ncall TimerStart(GB,1.,false,function MJ_ProgressRetryStart)\nendif\nreturn\nendif\n'
    bodies['uJ']=body[:prefix]+guard+'call MJ_LockProgress()\n'+body[prefix:]
    for name in ['ti','s1']:
        body=bodies[name];prefix=re.match(r'^function[^\n]+\n(?:local [^\n]*\n)*',body).end()
        guard='if MJ_AnyProgressImportPending() then\n'
        if name=='s1':
            guard+='call TimerStart(GetExpiredTimer(),1.,false,function s1)\n'
        else:
            guard+='call DialogDisplayBJ(true,Fq,GetTriggerPlayer())\ncall DisplayTimedTextToPlayer(GetTriggerPlayer(),0,0,8.,"有人正在导入进度，完成或取消后再开局。")\n'
        guard+='return\nendif\n'
        if name=='s1':
            guard+='if MJ_ProgressDifficultyGrace and IsTriggerEnabled(GM) and LoadInteger(DI,StringHash("全局"),$F1B419D0)==0 then\nset MJ_ProgressDifficultyGrace=false\ncall TimerStart(GetExpiredTimer(),20.,false,function s1)\nreturn\nendif\n'
        bodies[name]=body[:prefix]+guard+body[prefix:]
    bodies['main']=once(bodies['main'],'endfunction\n','call MJ_InitProgressChat()\nendfunction\n')
    removed=[]
    for name,body in list(bodies.items()):
        for native in WRITES+['RequestExtraBooleanData']:
            edits=[]
            for start,end,args in calls(body,native):
                if native=='RequestExtraBooleanData' and args.split(',',1)[0] not in ['34','42']:continue
                line_start=body.rfind('\n',0,start)+1
                if body[line_start:start]!='call ':raise ValueError('expected standalone side-effect call: '+name+'/'+native)
                if body[end:end+1]!='\n':raise ValueError('side-effect call line drift')
                edits.append((line_start,end+1))
            for start,end in reversed(edits):body=body[:start]+body[end:]
            if edits:removed.append(dict(function=name,native=native,count=len(edits)))
        bodies[name]=body
    changes=[]
    for name,body in bodies.items():
        if body!=original[name][0]:
            if name not in pinned:raise ValueError('unreviewed platform change: '+name)
            source=replace_function(source,name,pinned[name],body)
            changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    module=progress_module();declarations=re.search(r'^globals\n(.*?)^endglobals\n',module,re.M|re.S)
    roster=(ROOT/'src/roster.j').read_text(encoding='utf8')
    source=once(source,roster,roster+module[declarations.end():])
    source=once(source,'\nendglobals\n','\n'+declarations[1]+'endglobals\n')
    for native in WRITES+['DzAPI_Map_SaveServerValue','DzAPI_Map_GetServerValue']:
        if list(calls(source,native)):raise ValueError('original cloud calls remain: '+native)
    return source.encode(),dict(namespace='MJ5_LOCAL_V1',changes=changes,removed_side_effects=removed,runtime_verified=False,
        remaining='free-content policy, remaining read-only platform adapters and runtime validation')
