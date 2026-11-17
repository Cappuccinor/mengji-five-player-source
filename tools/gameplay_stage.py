"""Final audited death and end-of-game roster integration."""
import hashlib
import json
from pathlib import Path
import re
from tools.patching import functions,replace_function
from tools.lane_stage import once
from tools.progress_schema import progress_module

ROOT=Path(__file__).resolve().parents[1]


def prepare_gameplay(raw):
    source=raw.decode('utf8').replace('\r\n','\n');original=functions(source)
    pinned=json.loads((ROOT/'data/gameplay-stage-baselines.json').read_text(encoding='utf8'))
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('gameplay baseline drift: '+name)
    if 'MJ_DefeatActivePlayers' in original:raise ValueError('gameplay stage already applied')
    death='function x2 takes nothing returns boolean\nlocal unit dying=GetDyingUnit()\nlocal player owner=GetOwningPlayer(dying)\nlocal integer who=MJ_Index(owner)\n'
    death+='if who<0 then\nreturn false\nendif\n'
    death+='return MJ_IsActive(who) and IsPlayerInForce(owner,Fa) and IsUnitType(dying,UNIT_TYPE_HERO) and not cx(dying,$49303350) and not IsUnitIllusionBJ(dying) and dying==HQ[GetPlayerId(owner)]\nendfunction\n'
    body=original['BR6'][0]
    pattern=r'^call CustomDefeatBJ\(Player\(0\),(.*?)\)\ncall CustomDefeatBJ\(Player\(1\),\1\)\ncall CustomDefeatBJ\(Player\(2\),\1\)\ncall CustomDefeatBJ\(Player\(3\),\1\)\n'
    body,count=re.subn(pattern,lambda m:'call MJ_DefeatActivePlayers('+m[1]+')\n',body,flags=re.M)
    if count!=4:raise ValueError('global defeat branches drift')
    changes=[]
    for name,replacement in [('x2',death),('BR6',body)]:
        source=replace_function(source,name,pinned[name],replacement)
        changes.append(dict(function=name,original_sha256=pinned[name],new_sha256=hashlib.sha256(replacement.encode()).hexdigest()))
    progress=progress_module();g=re.search(r'^globals\n.*?^endglobals\n',progress,re.M|re.S)
    source=once(source,progress[g.end():],progress[g.end():]+(ROOT/'src/gameplay.j').read_text(encoding='utf8'))
    return source.encode(),dict(changes=changes,runtime_verified=False)
