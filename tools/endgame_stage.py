"""Stop phase clocks on terminal defeat and settle empty personal-failure rosters."""
import hashlib
import json
from pathlib import Path
from tools.patching import functions, replace_function, inject_module
from tools.lane_stage import once

ROOT=Path(__file__).resolve().parents[1]


def prepare_endgame(raw):
    source=raw.decode('utf8').replace('\r\n','\n')
    original=functions(source)
    if 'MJ_BeginDefeat' in original:
        raise ValueError('endgame stage already applied')
    pinned=json.loads((ROOT/'data/endgame-stage-baselines.json').read_text(encoding='utf8'))
    changes=[]
    for name,digest in pinned.items():
        if name not in original or hashlib.sha256(original[name][0].encode()).hexdigest()!=digest:
            raise ValueError('endgame baseline drift: '+name)
        body=original[name][0]
        if name=='BR6':
            body=once(body,'set F5=F5+3\n','if not MJ_BeginDefeat() then\nreturn\nendif\nset F5=F5+3\n')
        else:
            body=once(body,'if CountPlayersInForceBJ(Fa)==1 then\n',
                'if CountPlayersInForceBJ(Fa)==0 then\ncall EnableTrigger(K4)\ncall TriggerExecute(K4)\nelseif CountPlayersInForceBJ(Fa)==1 then\n')
        source=replace_function(source,name,digest,body)
        changes.append(dict(function=name,original_sha256=digest,new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    source=inject_module(source,(ROOT/'src/endgame.j').read_text(encoding='utf8'))
    return source.encode(),dict(changes=changes,runtime_verified=False)
