"""Build an explicitly incomplete development checkpoint, never a release."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from tools.archive import update_archive
from tools.check_jass import check_jass
from tools.prepare_workspace import prepare_workspace
from tools.layout_stage import prepare_layout
from tools.player_stage import prepare_players
from tools.lane_stage import prepare_lane
from tools.selection_stage import prepare_selection
from tools.object_stage import prepare_objects, prepare_object_script
from tools.combat_stage import prepare_combat
from tools.platform_stage import prepare_platform
from tools.free_objects_stage import prepare_free_object_script,prepare_free_objects
from tools.free_stage import prepare_free
from tools.gameplay_stage import prepare_gameplay
from tools.fifth_skill_stage import prepare_fifth_skills
from tools.map_identity import TITLE,rename_info,rename_script
from tools.local_names import namespace_new_locals
from tools.radial_stage import prepare_radial
from tools.endgame_stage import prepare_endgame

ROOT=Path(__file__).resolve().parents[1]
PENDING=[
    'Fifth-player exclusive objects require in-game pickup, upgrade and tooltip validation.',
    'Audited fifth-lane combat, legacy modes and player-specific skills require engine validation.',
    'Free content and standalone progress require actual client restart and effect validation.',
    'No Warcraft III or KK runtime, UI, 15-minute wait or five-client synchronization validation.',
]


def build_checkpoint(source:Path,destination:Path):
    if destination.exists(): raise FileExistsError(destination)
    prepare_workspace(source)
    members,layout=prepare_layout(ROOT/'scratch/baseline')
    script,players=prepare_players(members['war3map.j'])
    script,lane=prepare_lane(script)
    script,object_script=prepare_object_script(script)
    objects,object_report=prepare_objects(source)
    members.update(objects)
    script,combat=prepare_combat(script)
    script,platform=prepare_platform(script)
    script,free_object_script=prepare_free_object_script(script)
    free_objects,free_object_report=prepare_free_objects(objects)
    members.update(free_objects)
    script,free=prepare_free(script)
    script,gameplay=prepare_gameplay(script)
    script,fifth_skills=prepare_fifth_skills(script)
    script,assets,selection=prepare_selection(script)
    script,endgame=prepare_endgame(script)
    script,radial_members,radial=prepare_radial(script,ROOT/'scratch/baseline')
    members.update(radial_members)
    script=rename_script(script)
    script=namespace_new_locals(script)
    members['war3map.w3i']=rename_info(members['war3map.w3i'])
    members['war3map.j']=script; members.update(assets)
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as tmp:
        path=Path(tmp)/'war3map.j';path.write_bytes(script)
        compiler=check_jass(path,ROOT/'vendor/jass-1.27.1')
    if not compiler['passed']: raise RuntimeError(compiler['output'])
    archive=update_archive(source,destination,members,map_title=TITLE)
    report=dict(status='INCOMPLETE_DEVELOPMENT_CHECKPOINT',playable_verified=False,runtime_verified=False,
        map_title=TITLE,pending=PENDING,endgame=endgame,radial=radial,fifth_skills=fifth_skills,gameplay=gameplay,free=free,free_object_script=free_object_script,free_objects=free_object_report,platform=platform,combat=combat,objects=object_report,object_script=object_script,layout=layout,players=players,lane=lane,selection=selection,
        compiler=compiler,archive=archive,
        members={n:hashlib.sha256(b).hexdigest() for n,b in members.items()})
    destination.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'inputs/original.w3x')
    parser.add_argument('--out',type=Path,default=ROOT/'dist/development-only-not-playable.w3x')
    args=parser.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    report=build_checkpoint(args.source,args.out)
    print(json.dumps(dict(status=report['status'],path=str(args.out),pending=PENDING),indent=2))
