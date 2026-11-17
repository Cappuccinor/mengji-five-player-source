"""Generate the entire distinct original hero pool with object metadata."""
import json
from pathlib import Path
import re
import unicodedata


def _text(path):
    lines=[]
    for raw in path.read_bytes().splitlines():
        try:
            lines.append(raw.decode('utf-8-sig'))
        except UnicodeDecodeError:
            lines.append(raw.decode('gb18030'))
    return '\n'.join(lines)


def sections(path):
    out={}
    current=None
    for line in _text(path).splitlines():
        if re.fullmatch(r'\[[^\]]+\]',line):
            current=line[1:-1]
            out.setdefault(current,{})
        elif current and '=' in line:
            key,value=line.split('=',1)
            out[current][key]=value
    return out


def slk(path):
    rows={}
    x=y=1
    for line in _text(path).splitlines():
        if not line.startswith('C;'):
            continue
        match=re.search(r';X(\d+)',line)
        if match:
            x=int(match[1])
        match=re.search(r';Y(\d+)',line)
        if match:
            y=int(match[1])
        match=re.search(r';K(.*)$',line)
        if match:
            value=match[1]
            if value.startswith('"') and value.endswith('"'):
                value=value[1:-1].replace('""','"')
            rows.setdefault(y,{})[x]=value
    header=rows.pop(1)
    return {row[1]:{header[x]:value for x,value in row.items()} for _,row in sorted(rows.items())}


def printable_text(value):
    # Some source object descriptions contain binary C0 bytes (not game markup).
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','',value)


def clean(value):
    return re.sub(r'\|c[0-9a-fA-F]{8}|\|r','',printable_text(value),flags=re.I).replace('|n','\n')


def build_catalog(extracted: Path) -> list[dict]:
    script=_text(extracted/'war3map.j')
    pool=re.findall(r'call UnitPoolAddUnitType\(Gk\[0\],\$([0-9A-Fa-f]{8}),([^\)]+)\)',script)
    ids=list(dict.fromkeys(bytes.fromhex(code).decode('ascii') for code,_ in pool))
    if len(ids)!=158:
        raise ValueError('unexpected original hero pool size')
    units=sections(extracted/'Units_CampaignUnitStrings.txt')
    abilities=slk(extracted/'Units_UnitAbilities.slk')
    descriptions={}
    for path in sorted(extracted.glob('Units_*AbilityStrings.txt')):
        for key,value in sections(path).items():
            descriptions.setdefault(key,{}).update(value)
    result=[]
    for uid in ids:
        unit=units.get(uid,{})
        ability=abilities.get(uid,{})
        skills=[]
        codes=','.join([ability.get('heroAbilList',''),ability.get('abilList','')]).split(',')
        for code in dict.fromkeys(codes):
            if not code or code in ('_','AInv','Aloc'):
                continue
            meta=descriptions.get(code,{})
            skills.append(dict(id=code,name=clean(meta.get('Name',code)),
                               description=clean(meta.get('Researchubertip',meta.get('Ubertip',''))),
                               text_resolved=bool(meta)))
        result.append(dict(id=uid,rawcode=int.from_bytes(uid.encode('ascii'),'big'),name=clean(unit.get('Name','')),
                           icon=(unit.get('Art') or unit.get('ScoreScreenIcon','')).split(',')[0],
                           icon_source='Art' if unit.get('Art') else 'ScoreScreenIcon',description=clean(unit.get('Ubertip','')),
                           skills=skills,runtime_validated=False))
    return result


def emit_ids_jass(heroes):
    lines=['function MJ_InitHeroIds takes nothing returns nothing',f'    set MJ_HeroCount={len(heroes)}']
    for i,hero in enumerate(heroes):
        lines.append(f'    set MJ_HeroIds[{i}]={hero["rawcode"]}')
    return '\n'.join(lines+['endfunction',''])


def detail_pages(text):
    """Lossless Unicode pages: <=180 characters, six estimated 42-column rows.

    Prefer paragraph/sentence boundaries. Width is conservative layout guidance,
    not evidence about the client's actual font metrics.
    """
    pages=[]
    while text:
        column=0
        rows=1
        end=0
        boundary=0
        for i,char in enumerate(text[:180]):
            width=2 if unicodedata.east_asian_width(char) in ('W','F') else 1
            next_row=rows+(1 if char=='\n' or column+width>42 else 0)
            if next_row>6:
                break
            rows=next_row
            column=0 if char=='\n' else (width if column+width>42 else column+width)
            end=i+1
            if char in '\n。！？；.!?;':
                boundary=end
        if end<len(text) and boundary>=end//2:
            end=boundary
        pages.append(text[:end])
        text=text[end:]
    return pages or ['']


def emit_metadata_jass(heroes):
    def quote(s):
        return '"'+printable_text(s).replace('\\','\\\\').replace('"','\\"').replace('\n','|n').replace('\r','')+'"'
    lines=['globals','string array MJ_HeroNames','string array MJ_HeroIcons','string array MJ_HeroDetailPages','integer array MJ_HeroDetailStart','integer array MJ_HeroDetailCount','endglobals',
           'function MJ_InitHeroMetadata takes nothing returns nothing']
    page_index=0
    for i,hero in enumerate(heroes):
        detail=hero['description']
        for skill in hero['skills']:
            detail+='\n'+skill['name']+': '+(skill['description'] or '原对象未提供完整说明')
        lines += [f'    set MJ_HeroNames[{i}]={quote(hero["name"])}',f'    set MJ_HeroIcons[{i}]={quote(hero["icon"])}',
                  f'    set MJ_HeroDetailStart[{i}]={page_index}']
        pages=detail_pages(detail)
        lines.append(f'    set MJ_HeroDetailCount[{i}]={len(pages)}')
        for page in pages:
            lines.append(f'    set MJ_HeroDetailPages[{page_index}]={quote(page)}')
            page_index+=1
    if page_index>8192:
        raise ValueError('hero detail pages exceed classic JASS array capacity')
    return '\n'.join(lines+['endfunction',''])


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    heroes=build_catalog(root/'scratch/extracted')
    (root/'data/heroes.json').write_text(json.dumps(heroes,ensure_ascii=False,indent=2),encoding='utf8')
    (root/'src/hero_ids.j').write_text(emit_ids_jass(heroes),encoding='utf8')
    (root/'src/hero_metadata.j').write_text(emit_metadata_jass(heroes),encoding='utf8')
    print(f'Generated {len(heroes)} distinct candidate heroes; runtime validation remains pending.')
