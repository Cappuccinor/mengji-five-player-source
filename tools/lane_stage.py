"""Add translated northeast-lane units/regions and their initialization hooks.

This does not yet complete fifth-player damage sharing, failure or item objects.
"""
import hashlib
import re
from tools.patching import functions,replace_function
from tools.player_stage import code_mask,calls

REGIONS='BZ Be Bj Bk Br Bw B0 B4 CB CC CD CL'.split()
UNITS=['C0','C1','C8','C9']
NAMES={name:'MJ5_'+name for name in REGIONS+UNITS+['CX','uN','uO']}
ACTIVE='if GetPlayerSlotState(Player(1))==PLAYER_SLOT_STATE_PLAYING and GetPlayerController(Player(1))==MAP_CONTROL_USER then'


def rename_code(body,names):
    edits=[(m.start(),m.end(),names[m[0]]) for m in re.finditer(r'\b\w+\b',code_mask(body)) if m[0] in names]
    for a,b,value in reversed(edits): body=body[:a]+value+body[b:]
    return body


def block(body,condition):
    lines=body.splitlines(keepends=True)
    matches=[i for i,l in enumerate(lines) if l.rstrip('\n')==condition]
    if len(matches)!=1: raise ValueError('expected unique block: '+condition)
    start=matches[0]; depth=0
    for end in range(start,len(lines)):
        line=lines[end].strip()
        if line.startswith('if ') and line.endswith(' then'): depth+=1
        elif line=='endif': depth-=1
        if depth==0:
            return ''.join(lines[start:end+1])
    raise ValueError('unterminated block')


def shift_literal_calls(body):
    # Only whitelisted coordinate arguments are changed, never IDs/timers/angles.
    for name,indices in [('Rect',[0,2]),('CreateUnit',[2]),('CreateDestructable',[1]),('Location',[0]),('IssueBuildOrderById',[2])]:
        edits=[]
        for a,b,args in calls(body,name):
            values=args.split(',')
            if name=='Location' and not re.fullmatch(r'-?\d+\.?\d*',values[0]):
                continue
            for idx in indices:
                if not re.fullmatch(r'-?\d+\.?\d*',values[idx]):
                    raise ValueError('nonliteral coordinate: '+name)
                n=float(values[idx])+4096
                values[idx]=(f'{n:.6f}'.rstrip('0').rstrip('.')+'.') if n.is_integer() else f'{n:.6f}'.rstrip('0')
            edits.append((a,b,name+'('+','.join(values)+')'))
        for a,b,new in reversed(edits): body=body[:a]+new+body[b:]
    return body


def translate(body):
    return shift_literal_calls(rename_code(body,NAMES)).replace('Player(1)','Player(5)').replace('Player(9)','Player(6)')


def once(body,old,new):
    if body.count(old)!=1: raise ValueError('lane anchor mismatch: '+old[:100])
    return body.replace(old,new,1)


def prepare_lane(raw):
    source=raw.decode('utf8').replace('\r\n','\n'); original=functions(source); changes=[]
    if 'unit MJ5_C0' in source: raise ValueError('lane already applied')
    def patch(name,new):
        nonlocal source
        old=original[name][0]; digest=hashlib.sha256(old.encode()).hexdigest()
        source=replace_function(source,name,digest,new)
        changes.append(dict(function=name,original_sha256=digest,new_sha256=hashlib.sha256(new.encode()).hexdigest()))
    def append(name,extra):
        patch(name,once(original[name][0],'endfunction\n',extra+'endfunction\n'))

    body=original['sk'][0]
    rects=''.join(next(l+'\n' for l in body.splitlines() if l.startswith('set '+n+'=Rect(')) for n in REGIONS)
    append('sk',translate(rects))
    body=original['sa'][0]
    if 'set C1=CreateUnit(Ch,$6E303033,640.,640.,225.)' not in body:
        raise ValueError('helper baseline drift')
    unit_lines=''.join(l+'\n' for l in body.splitlines() if l.startswith(('set C0=','set C1=','set Cr=')))
    # Fifth personal bases use the translated NE geometry; preview remains in the shared lobby.
    append('sa','set Ch=Player(5)\n'+translate(unit_lines))
    append('sZ','set Ch=Player(5)\nset Cr=CreateUnit(Ch,$6E636F70,320.,2752.,270.)\n')
    builders=''.join(l+'\n' for l in original['sf'][0].splitlines() if l.startswith(('set C8=','set C9=')))
    if len(builders.splitlines())!=2: raise ValueError('builder baseline drift')
    append('sf',translate(builders))  # Ch remains NPC Player(4).
    gate=next(l+'\n' for l in original['sV'][0].splitlines() if l.startswith('set CX='))
    append('sV',translate(gate))
    # Three ordinary NE-side shops; these are neutral, not owned by a human slot.
    shops=''
    for line in original['sg'][0].splitlines():
        if line.startswith(('set Cj=','set Ct=','set Cq=')):
            shops+=re.sub(r'^set \w+=','set Cr=',line)+'\n'
    append('sg',shift_literal_calls(shops))

    body=original['s2'][0]
    extra=translate(block(body,ACTIVE))
    body=once(body,'call ForForce(Fa,function sm)\n',extra+'call ForForce(Fa,function sm)\n')
    bindings=''.join(l+'\n' for l in body.splitlines() if 'GetHandleId(Player(1))' in l and any(k in l for k in ['$8096117C','$D3771A32','$80B2890C']))
    if len(bindings.splitlines())!=3: raise ValueError('lane binding drift')
    body=once(body,bindings,bindings+translate(bindings)); patch('s2',body)

    body=original['uW'][0]
    for region in ['Be','Bw']:
        line=next(l+'\n' for l in body.splitlines() if 'GetHandleId(Player(1)),$1E9008DF,GetRectCenter('+region+')' in l)
        body=once(body,line,line+translate(line))
    extra=translate(block(body,ACTIVE))
    body=once(body,'call SaveStr(DI,4,$79A4CC5B,"血厚")\n',extra+'call SaveStr(DI,4,$79A4CC5B,"血厚")\n')
    patch('uW',body)
    # Timer callbacks must be declared before uW; they use fifth-player text tags.
    cloned=translate(original['uN'][0])+translate(original['uO'][0])
    point=functions(source)['uW'].start(); source=source[:point]+cloned+source[point:]

    body=original['wE'][0]
    active=block(body,'if GetEnumPlayer()==Player(1) then')
    # Just the NE branch before its top-level else, followed by a complete endif.
    branch=active.split('\nelse\n',1)[0]+'\nendif\n'
    marker='call RemoveLocation('
    position=body.index(marker)
    patch('wE',body[:position]+translate(branch)+body[position:])

    body=original['BOB'][0]
    condition='if RectContainsUnit(Bj,GetTriggerUnit())==true or RectContainsUnit(Bk,GetTriggerUnit())==true or RectContainsUnit(B0,GetTriggerUnit())==true or RectContainsUnit(B4,GetTriggerUnit())==true then'
    active=block(body,condition)
    # The first nested endif closes the tower-one/tower-two message branch.
    branch=active[:active.index('\nendif\n')+len('\nendif\n')]+'endif\n'
    end_of_chain='endif\nendif\nendif\nendif\nset Gi=1\n'
    body=once(body,end_of_chain,'endif\nendif\nendif\nendif\n'+translate(branch)+'set Gi=1\n')
    patch('BOB',body)
    append('BEJ','call cv(JU,MJ5_BZ)\n')
    append('BPu','call cv(GZ,MJ5_CB)\ncall cv(GZ,MJ5_CC)\ncall cv(GZ,MJ5_CD)\n')
    # The extra lane gets its own region trigger, using the existing return-home action.
    condition=original['BPy'][0].replace('function BPy ','function MJ5_RejectOtherPlayer ').replace('Player(1)','Player(5)')
    point=functions(source)['BP0'].start(); source=source[:point]+condition+source[point:]
    append('BP0','set MJ5_Border=CreateTrigger()\ncall DisableTrigger(MJ5_Border)\ncall cv(MJ5_Border,MJ5_Br)\ncall cv(MJ5_Border,MJ5_CL)\ncall TriggerAddCondition(MJ5_Border,Condition(function MJ5_RejectOtherPlayer))\ncall TriggerAddAction(MJ5_Border,function BPz)\n')
    # Toggle alongside the original separated-lane border in every original callsite.
    for name,m in list(functions(source).items()):
        body=m[0]
        for action in ['EnableTrigger','DisableTrigger']:
            body=body.replace(f'call {action}(Gb)\n',f'call {action}(Gb)\ncall {action}(MJ5_Border)\n') if name!='BP0' else body
        if body!=m[0]:
            source=replace_function(source,name,hashlib.sha256(m[0].encode()).hexdigest(),body)
            changes.append(dict(function=name,reason='toggle fifth lane border with NE border'))
    body=functions(source)['us'][0]
    row_block=block(body,'if GetPlayerController(Player(3))==MAP_CONTROL_USER and GetPlayerSlotState(Player(3))==PLAYER_SLOT_STATE_PLAYING then')
    body=once(body,row_block,'call MultiboardSetRowCount(JF,6)\n')
    body=once(body,'exitwhen Gi>5','exitwhen Gi>6')
    body=body.replace('ConvertedPlayer(Gi-1)','MJ_Human1(Gi-1)').replace('HQ[Gi-2]','HQ[GetPlayerId(MJ_Human1(Gi-1))]')
    # us may already have border toggles; patch against its current fingerprint.
    old=functions(source)['us'][0]
    source=replace_function(source,'us',hashlib.sha256(old.encode()).hexdigest(),body)
    changes.append(dict(function='us',reason='allocate and initialize header plus five logical rows'))
    patch('BQV',once(original['BQV'][0],'call KillUnit(C0)\n','call KillUnit(C0)\ncall KillUnit(MJ5_C0)\n'))
    declarations=''.join('rect MJ5_'+n+'=null\n' for n in REGIONS)+''.join('unit MJ5_'+n+'=null\n' for n in UNITS)
    declarations+='destructable MJ5_CX=null\ntrigger MJ5_Border=null\n'
    source=source.replace('\nendglobals\n','\n'+declarations+'endglobals\n',1)
    return source.encode('utf8'),dict(changes=changes,translated_regions=REGIONS,translation=[4096,0],
        npc_owner=4,human_owner=5,enemy_owner=6,runtime_verified=False,
        remaining='exclusive item/ability objects, shared damage, failure/distribution branches, platform isolation')
