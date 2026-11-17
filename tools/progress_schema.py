"""Emit the explicit audited progress schema; no platform state is read."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def emit_schema(data):
    canonical=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    tag=hashlib.sha256(canonical.encode()).hexdigest()[:8]
    quote=lambda text:json.dumps(text,ensure_ascii=False)
    lines=['globals','integer MJ_ProgressKeyCount=0','string array MJ_ProgressKeys','integer array MJ_ProgressKinds','integer array MJ_ProgressMax','integer array MJ_MasteryKeys',f'string MJ_ProgressAlphabet={quote(data["alphabet"])}',f'string MJ_ProgressHeader="MJ5_LOCAL_V1:{tag}:"','endglobals','function MJ_InitProgressSchema takes nothing returns nothing',f'    set MJ_ProgressKeyCount={len(data["keys"])}']
    for i,item in enumerate(data['keys']):
        lines += [f'    set MJ_ProgressKeys[{i}]={quote(item["key"])}',f'    set MJ_ProgressKinds[{i}]={item["kind"]}',f'    set MJ_ProgressMax[{i}]={item["max"]}']
        if item['key'].startswith('SSLD['):lines.append(f'    set MJ_MasteryKeys[{int(item["key"][5:-1])}]={i}')
    return '\n'.join(lines+['endfunction',''])


def progress_module():
    import re
    parts=[(ROOT/'src/progress_schema.j').read_text(encoding='utf-8-sig'),(ROOT/'src/progress.j').read_text(encoding='utf-8-sig'),(ROOT/'src/progress_transfer.j').read_text(encoding='utf-8-sig')]
    declarations=[];bodies=[]
    for part in parts:
        part=part.replace('\r\n','\n')
        declarations.extend(re.findall(r'^globals\n(.*?)^endglobals\n',part,re.M|re.S))
        bodies.append(re.sub(r'^globals\n.*?^endglobals\n','',part,flags=re.M|re.S))
    return 'globals\n'+''.join(declarations)+'endglobals\n'+''.join(bodies)


if __name__=='__main__':
    data=json.loads((ROOT/'data/progress-keys.json').read_text(encoding='utf8'))
    (ROOT/'src/progress_schema.j').write_text(emit_schema(data),encoding='utf8')
