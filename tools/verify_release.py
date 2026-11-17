"""Check the actual candidate bytes; runtime and multiplayer remain separate gates."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from tools.archive import BASELINE,read_member,verify_preservation
from tools.check_jass import check_jass
from tools.patching import functions
from tools.player_stage import calls

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={'war3map.j','war3map.w3e','war3map.wpm','war3map.shd','war3map.doo','war3map.w3i','war3mapMap.blp','war3mapMap.tga',
    r'Units\ItemData.slk',r'Units\ItemStrings.txt',r'Units\AbilityData.slk',r'Units\CampaignAbilityStrings.txt',
    r'MJ5\hero.fdf',r'MJ5\hero.toc'}
FORBIDDEN=['DzAPI_Map_SaveServerValue','DzAPI_Map_GetServerValue','DzAPI_Map_Stat_SetStat',
    'DzAPI_Map_Ladder_SetStat','DzAPI_Map_Ladder_SetPlayerStat','DzAPI_Map_HasMallItem',
    'DzAPI_Map_GetMapLevel','DzAPI_Map_GetLadderLevel','DzAPI_Map_GetGuildName',
    'DzAPI_Map_GetMapLevelRank','DzAPI_Map_IsBlueVIP','DzAPI_Map_GetMapConfig',
    'RequestExtraBooleanData','RequestExtraIntegerData','RequestExtraStringData']


def verify_release(path):
    path=Path(path).resolve()
    if path.is_dir():
        candidates=list(path.glob('*待联机验证.w3x'))
        if len(candidates)!=1:raise ValueError('specify one candidate map file')
        path=candidates[0]
    report=json.loads(path.with_suffix('.json').read_text(encoding='utf8'))
    original=(ROOT/'inputs/original.w3x').read_bytes()
    if hashlib.sha256(original).hexdigest()!=BASELINE:raise ValueError('source baseline changed')
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if report['archive']['sha256']!=digest:raise ValueError('archive hash mismatch')
    if set(report['members'])!=REQUIRED:raise ValueError('missing or unexpected member inventory')
    members={name:read_member(path,name) for name in report['members']}
    for name,content in members.items():
        if hashlib.sha256(content).hexdigest()!=report['members'][name]:raise ValueError('member hash mismatch: '+name)
    preservation=verify_preservation(original,raw,members)
    script=members['war3map.j'].decode('utf8');f=functions(script)
    for native in FORBIDDEN:
        if list(calls(script,native)):raise ValueError('forbidden account call: '+native)
    for name in ['MJ_ContentAvailable','MJ_ApplyFreeEffects','MJ_ClaimReward','MJ_ImportProgress',
                 'MJ_OnProgressChat','MJ_SelectStart','MJ_StartGame','MJ_FreeDialogOwner',
                 'MJ_FifthSandCoinReward','MJ_DefeatActivePlayers','MJ_ReopenConfigMenus','MJ_RenderHeroDetail']:
        if name not in f:raise ValueError('missing integrated function: '+name)
    for stage in ['radial','fifth_skills','gameplay','platform','free','free_objects','free_object_script','combat','objects','selection','layout','players','lane']:
        if stage not in report:raise ValueError('missing stage evidence: '+stage)
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
        source=Path(tmp)/'war3map.j';source.write_bytes(members['war3map.j'])
        compiler=check_jass(source,ROOT/'vendor/jass-1.27.1')
    if not compiler['passed']:raise ValueError('candidate compile failed: '+compiler['output'])
    return dict(path=str(path),sha256=digest,offline_passed=True,runtime_verified=False,
        multiplayer_verified=False,compiler=compiler,**preservation)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('path',type=Path)
    args=parser.parse_args();print(json.dumps(verify_release(args.path),ensure_ascii=False,indent=2))
