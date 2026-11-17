"""Build an independent candidate, preserving the original and all opaque resources."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from tools.archive import BASELINE
from tools.build_checkpoint import build_checkpoint
from tools.verify_release import verify_release

ROOT=Path(__file__).resolve().parents[1]
NAME='梦迹沙河2-五人免费版-待联机验证.w3x'


def build(source,out):
    source=Path(source).resolve();out=Path(out).resolve()
    if hashlib.sha256(source.read_bytes()).hexdigest()!=BASELINE:raise ValueError('source baseline hash mismatch')
    target=out/NAME
    if target==source:raise ValueError('source and destination must differ')
    if target.exists() or target.with_suffix('.json').exists():raise FileExistsError(target)
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out,prefix='build-') as tmp:
        stage=Path(tmp)/NAME
        report=build_checkpoint(source,stage)
        verified=verify_release(stage)
        verified["path"]=str(target)
        report.update(status='OFFLINE_CANDIDATE_RUNTIME_PENDING',path=str(target),runtime_verified=False,
            playable_verified=False,multiplayer_verified=False,offline_verification=verified)
        # Promote only after compilation, opaque-resource checks and packed read-back.
        with target.open('xb') as stream:stream.write(stage.read_bytes())
        with target.with_suffix('.json').open('x',encoding='utf8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'inputs/original.w3x')
    parser.add_argument('--out',type=Path,default=ROOT/'dist')
    args=parser.parse_args();result=build(args.source,args.out)
    print(json.dumps(dict(path=result['path'],sha256=result['archive']['sha256'],status=result['status']),ensure_ascii=False,indent=2))
