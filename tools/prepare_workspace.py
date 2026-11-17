"""Recreate ignored analysis inputs from the included, hash-locked original map."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.archive import BASELINE, read_member

ROOT=Path(__file__).resolve().parents[1]
BASE_MEMBERS=['war3map.j','war3map.w3i','war3map.w3e','war3map.wpm','war3map.shd','war3map.doo','war3mapMap.tga']
CATALOG_MEMBERS=['war3map.j',r'Units\CampaignUnitStrings.txt',r'Units\UnitAbilities.slk']+[
    'Units\\'+race+'AbilityStrings.txt' for race in
    ['Campaign','Common','Human','Item','Neutral','NightElf','Orc','Undead']]


def prepare_workspace(source: Path, root: Path=ROOT):
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=BASELINE:
        raise ValueError('source baseline hash mismatch')
    pending={}
    for name in BASE_MEMBERS:
        pending[root/'scratch/baseline'/name]=read_member(source,name)
    for name in CATALOG_MEMBERS:
        pending[root/'scratch/extracted'/name.replace('\\','_')]=read_member(source,name)
    # Validate the full set before writing anything. Never erase a modified local input.
    for path,content in pending.items():
        if path.exists() and path.read_bytes()!=content:
            raise ValueError('existing derived input differs: '+str(path))
    for path,content in pending.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as fp: fp.write(content)
    return dict(source_sha256=digest,files=len(pending),runtime_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT/'inputs/original.w3x')
    args=parser.parse_args()
    print(json.dumps(prepare_workspace(args.source),indent=2))
