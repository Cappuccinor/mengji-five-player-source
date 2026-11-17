"""Run progress JASS logic with string/hashtable native boundaries, not Warcraft."""
from collections import defaultdict
import re
from tests.combat_harness import run_functions


def progress_environment(source):
    source=re.sub(r'^(string|hashtable) (array )?',r'integer \2',source,flags=re.M)
    source=re.sub(r'\breturns (string|player)\b','returns integer',source)
    source=re.sub(r'local (string|hashtable|trigger) (\w+)(?=[=\n])',r'local integer \2',source)
    env=run_functions(source)
    def load(table,kind,p,k,default):return table.get((kind,p,k),default)
    def save(table,kind,p,k,value):table[kind,p,k]=value
    def flush(table,p):
        for pair in [pair for pair in table if pair[1]==p]:del table[pair]
    env.update(InitHashtable=dict,Player=lambda p:p,StringLength=lambda s:len(s or ''),SubString=lambda s,a,b:(s or '')[int(a):int(b)],
        I2S=lambda v:str(int(v)),S2I=lambda s:int(s) if re.fullmatch(r'[+-]?[0-9]+',s or '') else 0,
        StringCase=lambda s,upper:s.upper() if upper else s.lower(),I2R=float,R2I=int,ModuloInteger=lambda a,b:a%b,
        StringHash=lambda s:s.upper().replace('/','\\'),MJ_Index=lambda p:{0:0,1:1,2:2,3:3,5:4}.get(p,-1),
        MJ_Player=lambda i:[0,1,2,3,5][i],
        LoadInteger=lambda t,p,k:load(t,'int',p,k,0),SaveInteger=lambda t,p,k,v:save(t,'int',p,k,v),
        LoadBoolean=lambda t,p,k:load(t,'bool',p,k,False),SaveBoolean=lambda t,p,k,v:save(t,'bool',p,k,v),
        LoadStr=lambda t,p,k:load(t,'str',p,k,None),SaveStr=lambda t,p,k,v:save(t,'str',p,k,v),
        FlushChildHashtable=flush,RemoveSavedInteger=lambda t,p,k:t.pop(('int',p,k),None),
        RemoveSavedBoolean=lambda t,p,k:t.pop(('bool',p,k),None),RemoveSavedString=lambda t,p,k:t.pop(('str',p,k),None))
    env.setdefault('MJ_SelectionHost',lambda:0)
    return env
