"""Clone independent fifth-player item and tooltip objects, preserving original bytes."""
import hashlib
import json
from pathlib import Path
import re
from tools.archive import BASELINE, read_member
from tools.patching import functions, replace_function
from tools.lane_stage import once
from tools.player_stage import calls

ITEM_SOURCES=['I000','I00D','I00E','I00F','I06H','I002','I00G','I00H','I00I','I06K','I001','I00J','I00K','I00L','I06E']
ITEM_CLONES={old:'IM5'+format(i,'X') for i,old in enumerate(ITEM_SOURCES)}
ABILITY_CLONES={'A01P':'AMJ5'}
ROOT=Path(__file__).resolve().parents[1]


def clone_slk(raw,clones):
    # The hash-locked original uses one explicit row header followed by X cells.
    headers=list(re.finditer(rb'^C;X1;Y(\d+);K"([^"\r\n]+)"\r?\n',raw,re.M))
    rows={m[2].decode('ascii'):(m,raw[m.start():headers[i+1].start() if i+1<len(headers) else raw.rfind(b'\nE')+1]) for i,m in enumerate(headers)}
    if len(rows)!=len(headers): raise ValueError('duplicate SLK object')
    bounds=re.search(rb'^B;X\d+;Y(\d+);D0\r?$',raw,re.M)
    if not bounds or not raw.endswith(b'\nE'): raise ValueError('unsupported SLK layout')
    row_count=int(bounds[1])
    if max(int(m[1]) for m in headers)!=row_count: raise ValueError('SLK bounds mismatch')
    extra=[]
    for old,new in clones.items():
        if old not in rows or new in rows: raise ValueError('missing source or colliding object: '+new)
        m,body=rows[old]; row_count+=1
        header=b'C;X1;Y'+str(row_count).encode()+b';K"'+new.encode()+b'"\r\n'
        extra.append(header+body[m.end()-m.start():])
    result=raw[:bounds.start(1)]+str(row_count).encode()+raw[bounds.end(1):]
    return result[:-1]+b''.join(extra)+b'E'


def clone_sections(raw,clones):
    headers=list(re.finditer(rb'^\[([^\]\r\n]+)\]\r?\n',raw,re.M))
    rows={m[1].decode('ascii'):(m,raw[m.start():headers[i+1].start() if i+1<len(headers) else len(raw)]) for i,m in enumerate(headers)}
    if len(rows)!=len(headers): raise ValueError('duplicate text object')
    extra=[]
    for old,new in clones.items():
        if old not in rows or new in rows: raise ValueError('missing source or colliding object: '+new)
        m,body=rows[old]
        extra.append(b'['+new.encode()+b']\r\n'+body[m.end()-m.start():])
    return raw+b'\r\n'+b'\r\n'.join(extra)


def prepare_objects(source):
    if hashlib.sha256(source.read_bytes()).hexdigest()!=BASELINE: raise ValueError('source baseline hash mismatch')
    members={}
    for name,clone,ids in [(r'Units\ItemData.slk',clone_slk,ITEM_CLONES),(r'Units\ItemStrings.txt',clone_sections,ITEM_CLONES),(r'Units\AbilityData.slk',clone_slk,ABILITY_CLONES),(r'Units\CampaignAbilityStrings.txt',clone_sections,ABILITY_CLONES)]:
        members[name]=clone(read_member(source,name),ids)
    return members,dict(items=ITEM_CLONES,abilities=ABILITY_CLONES,runtime_verified=False)


def prepare_object_script(raw):
    source=raw.decode('utf8').replace('\r\n','\n'); original=functions(source); changes=[]
    pinned=json.loads((ROOT/'data/object-stage-baselines.json').read_text(encoding='utf8'))
    for name,digests in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest() not in digests:
            raise ValueError('object stage baseline drift: '+name)
    def patch(name,new):
        nonlocal source
        digest=hashlib.sha256(original[name][0].encode()).hexdigest()
        source=replace_function(source,name,digest,new)
        changes.append(dict(function=name,original_sha256=digest,new_sha256=hashlib.sha256(new.encode()).hexdigest()))
    body=original['uW'][0]
    for i,(old,new) in enumerate(ITEM_CLONES.items()):
        array=['II','IJ','IK'][i//5]; tier=i%5
        anchor=f'set {array}[{tier*10+1}]=$'+old.encode().hex().upper()+'\n'
        addition=f'set {array}[{tier*10+6}]=$'+new.encode().hex().upper()+'\n'
        if addition in body: raise ValueError('object stage already applied')
        body=once(body,anchor,anchor+addition)
    patch('uW',body)
    for name in ['yt','yv','yx']:
        body=original[name][0]
        body=once(body,'exitwhen Gi>4','exitwhen Gi>6')
        body=once(body,'set Gi=Gi+1\n','set Gi=Gi+1\nif Gi==5 then\nset Gi=6\nendif\n')
        patch(name,body)
    for name in ['ux','u1','u4','u7','wW','wZ','we']:
        body=original[name][0]
        line=next(l for l in body.splitlines() if '$41303150' in l)
        lines=body.splitlines(); condition=lines[lines.index(line)-1]
        if not condition.endswith('==Player(3) then'): raise ValueError('ability dispatch drift')
        old=condition+'\n'+line+'\nelse\nendif'
        new=condition+'\n'+line+'\nelse\n'+condition.replace('Player(3)','Player(5)')+'\n'+line.replace('$41303150','$414D4A35')+'\nendif\nendif'
        patch(name,once(body,old,new))
    body=original['US'][0]
    anchor='call SaveInteger(D,$41303150,0,OrderId("waterelemental"))\n'
    patch('US',once(body,anchor,anchor+anchor.replace('$41303150','$414D4A35')))
    patch('wu',once(original['wu'][0],'GetSpellAbilityId()==$41303150','GetSpellAbilityId()==$41303150 or GetSpellAbilityId()==$414D4A35'))
    body=original['xa'][0]; edits=[]
    sword_ids={'$'+old.encode().hex().upper():'$'+new.encode().hex().upper() for old,new in list(ITEM_CLONES.items())[:5]}
    for start,end,args in calls(body,'cx'):
        unit,rawcode=args.rsplit(',',1)
        if rawcode in sword_ids:
            # Preserve the original predicate precedence and add the same tier's independent type.
            if body[end:end+6]!='==true': raise ValueError('unexpected sword predicate')
            edits.append((start,end+6,'('+body[start:end+6]+' or cx('+unit+','+sword_ids[rawcode]+')==true)'))
    if len(edits)!=13: raise ValueError('sword predicate count drift')
    for start,end,replacement in reversed(edits): body=body[:start]+replacement+body[end:]
    patch('xa',body)
    return source.encode(),dict(changes=changes,converted_player_id=6,runtime_verified=False)
