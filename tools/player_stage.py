"""Reviewed player loops/ownership only. Lane lifecycle remains a separate stage."""
import hashlib
import re
from tools.patching import functions, replace_function

LOOPS = {name:1 for name in 't8 ul uo wC wR BBD BCr BCu BCw BCz BC1 BC5 BC7 BDB BDD BDF BDH BOK BOT BOb BOi BOp BOw BQm BR1'.split()}
LOOPS.update(v4=3, BBI=2, BBY=3)
OFFSET_FUNCTIONS = set('zF zI z7 BBB BBD BBG BDN BDV BEF BL8 BN3 BOK BOT BOb BOi BOp BOw BPS BPY BPb BPt BQX'.split())
SUM_COUNTS = dict(v4=2, wC=2, wG=1, BO3=1, BO9=5)
SUM = '+'.join(f'GetPlayerState(Player({i}),PLAYER_STATE_RESOURCE_FOOD_USED)' for i in [8,9])+'+('+ '+'.join(f'GetPlayerState(Player({i}),PLAYER_STATE_RESOURCE_FOOD_USED)' for i in [10,11])+')'


def code_mask(source):
    """Keep offsets while hiding quoted strings, rawcodes and line comments."""
    return re.sub(r'"(?:\\.|[^"\\])*"|\x27[^\x27]*\x27|//[^\n]*',
                  lambda m: ''.join('\n' if c=='\n' else ' ' for c in m[0]), source)


def calls(source, name):
    mask=code_mask(source)
    for match in re.finditer(r'\b'+re.escape(name)+r'\(',mask):
        start=match.end(); depth=1; pos=start
        while pos<len(mask) and depth:
            depth += (mask[pos]=='(')-(mask[pos]==')')
            pos+=1
        if depth:
            raise ValueError('unbalanced call '+name)
        yield match.start(),pos,source[start:pos-1]


def rewrite_offsets(body):
    edits=[]
    for start,end,args in calls(body,'ConvertedPlayer'):
        match=re.fullmatch(r'GetConvertedPlayerId\((.*)\)([+-])8',args,re.S)
        if match:
            inner=list(calls(args,'GetConvertedPlayerId'))
            if len(inner)!=1 or inner[0][1]!=len(args)-2:
                raise ValueError('unexpected nested player offset')
            edits.append((start,end,('MJ_EnemyOf' if match[2]=='+' else 'MJ_HumanOf')+'('+match[1]+')'))
    for start,end,new in reversed(edits):
        body=body[:start]+new+body[end:]
    return body,len(edits)


def expand_loops(body, expected):
    lines=body.splitlines(keepends=True)
    stack=[]; ranges=[]
    for i,line in enumerate(lines):
        if line.strip()=='loop': stack.append(i)
        elif line.strip()=='endloop':
            start=stack.pop()
            if any(l.strip()=='exitwhen Gi>4' for l in lines[start:i]):
                ranges.append((start,i+1))
    # These reviewed loops are not nested inside another Gi loop.
    if len(ranges)!=expected:
        raise ValueError(f'player loop count mismatch: {len(ranges)} != {expected}')
    for start,end in reversed(sorted(ranges)):
        old=''.join(lines[start:end])
        if old.count('exitwhen Gi>4')!=1:
            raise ValueError('ambiguous player loop')
        new=old.replace('exitwhen Gi>4','exitwhen Gi>5')
        new=new.replace('ConvertedPlayer(Gi+8)','MJ_Enemy1(Gi)').replace('ConvertedPlayer(Gi)','MJ_Human1(Gi)')
        new=new.replace('HQ[Gi-1]','HQ[GetPlayerId(MJ_Human1(Gi))]')
        lines[start:end]=[new]
    return ''.join(lines)


def prepare_players(raw):
    source=raw.decode('utf8').replace('\r\n','\n')
    original=functions(source)
    changes=[]; expanded=offsets=sums=0
    for name,match in original.items():
        old=match[0]; body=old
        if name in LOOPS:
            body=expand_loops(body,LOOPS[name]); expanded+=LOOPS[name]
        if name in OFFSET_FUNCTIONS:
            body,count=rewrite_offsets(body)
            if not count: raise ValueError('missing ownership offset: '+name)
            offsets+=count
        if name in SUM_COUNTS:
            count=body.count(SUM)
            if count!=SUM_COUNTS[name]: raise ValueError('monster sum count mismatch: '+name)
            body=body.replace(SUM,'MJ_TotalMonsters()'); sums+=count
        if name=='BCu':
            old_condition='GetPlayerController(MJ_Human1(Gi))==MAP_CONTROL_USER and LoadBoolean(DI,StringHash("全局"),$88CEC9C2)==true or (GetPlayerSlotState(MJ_Human1(Gi))==PLAYER_SLOT_STATE_PLAYING and IsPlayerInForce(MJ_Human1(Gi),Fa)==true)'
            if body.count(old_condition)!=1: raise ValueError('BCu predicate drift')
            # Both modes require a real playing human; ordinary mode also requires membership.
            body=body.replace(old_condition,'MJ_IsActive(Gi-1) and (LoadBoolean(DI,StringHash("全局"),$88CEC9C2)==true or IsPlayerInForce(MJ_Human1(Gi),Fa)==true)')
        if name=='vv':
            body=body.replace('exitwhen Gi>5','exitwhen Gi>6')
            body=body.replace('ConvertedPlayer(Gi-1)','MJ_Human1(Gi-1)').replace('ConvertedPlayer(Gi+7)','MJ_Enemy1(Gi-1)')
            body=body.replace('HQ[Gi-2]','HQ[GetPlayerId(MJ_Human1(Gi-1))]')
            last='LoadInteger(DI,GetHandleId(MJ_Human1(Gi-1)),$D98597C0)>=LoadInteger(DI,GetHandleId(Player(3)),$D98597C0)'
            if body.count(last)!=1: raise ValueError('score leader comparison drift')
            body=body.replace(last,last+' and '+last.replace('Player(3)','Player(5)'))
        if name in {'BN3','BOK','BOT','BOb','BOi','BOp','BOw'}:
            lines=[]
            for line in body.splitlines(keepends=True):
                if re.match(r'call (ch|ce)\(JF,',line):
                    edits=[]
                    for a,b,args in calls(line,'GetConvertedPlayerId'):
                        if line[b:b+2]=='+1': edits.append((a,b+2,'MJ_Row('+args+')'))
                    for a,b,value in reversed(edits): line=line[:a]+value+line[b:]
                lines.append(line)
            body=''.join(lines)
        if old!=body:
            digest=hashlib.sha256(old.encode()).hexdigest()
            source=replace_function(source,name,digest,body)
            changes.append(dict(function=name,original_sha256=digest,new_sha256=hashlib.sha256(body.encode()).hexdigest()))
    if expanded!=33 or sums!=11: raise ValueError('incomplete audited player patch')
    return source.encode('utf8'),dict(expanded_player_loops=expanded,ownership_replacements=offsets,
        monster_sum_replacements=sums,changes=changes,runtime_verified=False,
        remaining='lane units, item objects, failure branches, scoreboard allocation, platform isolation')
