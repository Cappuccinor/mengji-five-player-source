"""Connect the pure selection state machine and UI to the original start chain."""
import hashlib
from pathlib import Path
import re
from tools.patching import functions,replace_function,inject_module
from tools.hero_catalog import build_catalog,emit_ids_jass,emit_metadata_jass

ROOT=Path(__file__).resolve().parents[1]


def prepare_selection(raw: bytes):
    source=raw.decode('utf8').replace('\r\n','\n')
    original=functions(source)
    changes=[]
    progress_chat=(ROOT/'src/progress_chat.j').read_text(encoding='utf-8-sig')
    difficulty_menu=functions(progress_chat)['MJ_BuildDifficultyMenu'][0]
    def patch(name,body):
        nonlocal source
        if name in ['s1','s2','tQ','tW','tY','ti']:
            body=body.replace('GetPlayerName(Player(0))','GetPlayerName(MJ_SelectionHost())')
            body=body.replace('TU(Player(0),"GG")','TU(MJ_SelectionHost(),"GG")')
            body=re.sub(r'DialogDisplayBJ\((true|false),(Fq|Fm),Player\(0\)\)',r'DialogDisplayBJ(\1,\2,MJ_SelectionHost())',body)
        old=original[name][0]
        digest=hashlib.sha256(old.encode()).hexdigest()
        source=replace_function(source,name,digest,body)
        changes.append(dict(function=name,original_sha256=digest))
    body=original['tY'][0]
    body=body.replace('call DialogDisplayBJ(true,Fq,Player(0))','call DialogAddButtonBJ(Fq,"全英雄自选（无限时）")\nset MJ_SelectModeButton=GetLastCreatedButtonBJ()\ncall DialogDisplayBJ(true,Fq,MJ_SelectionHost())')
    body=body.replace('GetPlayerName(Player(0))','GetPlayerName(MJ_SelectionHost())')
    patch('tY',body)
    body=original['ti'][0]
    marker='set F5=F5+3\n'
    branch='if GetClickedButtonBJ()==MJ_SelectModeButton then\ncall DisableTrigger(GetTriggeringTrigger())\ncall DialogDisplayBJ(false,Fq,GetTriggerPlayer())\ncall MJ_SelectStart()\nreturn\nendif\n'
    if body.count(marker)!=1:
        raise ValueError('ti insertion point mismatch')
    patch('ti',body.replace(marker,branch+marker))
    for name in ['s2','tQ','tW']:
        old=original[name][0]
        condition='if TU(Player(0),"GG")>=2 or CountPlayersInForceBJ(Fa)==4 then'
        if old.count(condition)!=1:
            raise ValueError('menu eligibility mismatch: '+name)
        body=old.replace(condition,'if true then')
        if name in ['s2','tQ']:
            mode_gate='if TU(Player(0),"GG")>=1 and LoadBoolean'
            if body.count(mode_gate)!=1:
                raise ValueError('mode eligibility mismatch: '+name)
            body=body.replace(mode_gate,'if LoadBoolean')
        if name=='s2':
            start=body.rindex('call DialogClear(Fq)')
            end=body.index('call EnableTrigger(GM)',start)
            menu=body[start:end]
            if menu.count('set GI[')!=10 or menu.count('TU(Player(0),"GG")')!=9:
                raise ValueError('difficulty menu anchor drift')
            body=body[:start]+'call MJ_BuildDifficultyMenu()\n'+body[end:]
        patch(name,body)
    body=original['s1'][0]
    marker='set F5=F5+3\n'
    # This timer action has its own locals; insert after them, before side effects.
    first=next(line for line in body.splitlines()[1:] if not line.startswith('local '))
    guard='if MJ_AllHeroMode and MJ_SelectState==1 then\ncall DestroyTimer(GetExpiredTimer())\nreturn\nendif\n'
    patch('s1',body.replace(first+'\n',guard+first+'\n',1))
    body=original['ux'][0]
    line=next(line for line in body.splitlines() if line.startswith('set Gj=PlaceRandomUnit('))
    chosen='set Gj=CreateUnit(GetEnumPlayer(),MJ_Chosen[MJ_Index(GetEnumPlayer())],GetLocationX(LoadLocationHandle(DI,GetHandleId(GetEnumPlayer()),$1E9008DF)),GetLocationY(LoadLocationHandle(DI,GetHandleId(GetEnumPlayer()),$1E9008DF)),270.)'
    patch('ux',body.replace(line,'if MJ_AllHeroMode then\n'+chosen+'\nelse\n'+line+'\nendif',1))
    body=original['us'][0]
    marker='call StartTimerBJ(Fw,true,1.)'
    if body.count(marker)!=1:
        raise ValueError('us timer start mismatch')
    patch('us',body.replace(marker,'if MJ_AllHeroMode then\nset MJ_SelectState=3\nendif\n'+marker))
    body=original['BOK'][0]
    marker=next(line for line in body.splitlines()[1:] if not line.startswith('local '))+'\n'
    guard=''
    if 'MJ_CancelProgressTransfer' in original:
        guard='call MJ_CancelProgressTransfer(GetTriggerPlayer())\n'
    guard+='if MJ_Index(GetTriggerPlayer())<0 or not IsPlayerInForce(GetTriggerPlayer(),Fa) then\nreturn\nendif\n'
    if 'MJ_ContentAvailable' in original:
        guard+='if (MJ_AllHeroMode and MJ_SelectState<3) or MJ_FreePhase==0 then\ncall ForceRemovePlayer(Fa,GetTriggerPlayer())\ncall MJ_ReopenConfigMenus()\nreturn\nendif\n'
    else:
        guard+='if MJ_AllHeroMode and MJ_SelectState<3 then\ncall ForceRemovePlayer(Fa,GetTriggerPlayer())\nreturn\nendif\n'
    if body.count(marker)!=1: raise ValueError('leave guard anchor drift')
    patch('BOK',body.replace(marker,guard+marker,1))
    # Reassemble with roster first; forward calls are not legal in plain JASS.
    roster=(ROOT/'src/roster.j').read_text(encoding='utf8')
    if source.count(roster)!=1:
        raise ValueError('roster module missing or duplicate')
    source=source.replace(roster,'',1)
    heroes=build_catalog(ROOT/'scratch/extracted')
    progress=[]
    if 'MJ_InitProgress' in functions(source):
        from tools.progress_schema import progress_module
        module=progress_module()
        globals_match=re.search(r'^globals\n(.*?)^endglobals\n',module,re.M|re.S)
        progress_body=module[globals_match.end():]
        if source.count(progress_body)!=1 or source.count(globals_match[1])!=1:
            raise ValueError('progress module missing or duplicate')
        source=source.replace(progress_body,'',1).replace(globals_match[1],'',1)
        progress=[module]
    ui=(ROOT/'src/hero_ui.j').read_text(encoding='utf8')
    chat=[]
    if progress:
        marker='    if payload=="C" then\n'
        guard='    if MJ_IsProgressImportPending(sender) and payload!="C" then\n        call DisplayTimedTextToPlayer(sender,0,0,8.,"请先完成或取消进度导入，再准备。")\n        return\n    endif\n'
        if ui.count(marker)!=1:raise ValueError('progress selection guard drift')
        ui=ui.replace(marker,guard+marker,1)
        chat=[progress_chat.replace(difficulty_menu,'',1)]
    if 'MJ_ContentAvailable' in original:
        chat.append((ROOT/'src/config_menus.j').read_text(encoding='utf-8-sig'))
    modules=[roster]+progress+[(ROOT/'src/selection_state.j').read_text(encoding='utf8'),emit_ids_jass(heroes),emit_metadata_jass(heroes),ui,difficulty_menu]+chat
    globals_parts=[]
    natives=[]
    bodies=[]
    for module in modules:
        for m in re.finditer(r'^globals\n(.*?)^endglobals\n',module,re.M|re.S):
            globals_parts.append(m[1])
        module=re.sub(r'^globals\n.*?^endglobals\n','',module,flags=re.M|re.S)
        natives.extend(re.findall(r'^native .+\n',module,re.M))
        module=re.sub(r'^native .+\n','',module,flags=re.M)
        bodies.append(module)
    merged='globals\n'+''.join(globals_parts)+'endglobals\n'+''.join(natives)+''.join(bodies)
    source=inject_module(source,merged)
    # Git autocrlf must not change packed member hashes between Windows checkouts.
    assets={'MJ5\\'+name:(ROOT/'src/ui'/name).read_bytes().replace(b'\r\n',b'\n')
            for name in ['hero.fdf','hero.toc']}
    return source.encode('utf8'),assets,dict(hero_count=len(heroes),changes=changes,new_natives=[n.strip() for n in natives],runtime_verified=False)
