"""Prepare geometry/config members. This stage alone is NOT a playable build."""
import hashlib
from pathlib import Path
from tools.map_layout import extend_terrain,extend_pathing,extend_shadow,extend_doodads,extend_info
from tools.patching import functions,replace_function,inject_module

ROOT=Path(__file__).resolve().parents[1]
SCRIPT_HASH='95e678ea586d153fc154d99fed0ae9718b382d86aee2b1b7a670194208950633'


def prepare_layout(baseline: Path) -> tuple[dict,dict]:
    raw=(baseline/'war3map.j').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SCRIPT_HASH:
        raise ValueError('script baseline hash mismatch')
    source=raw.decode('utf8').replace('\r\n','\n')
    original=functions(source)
    patches=[]

    def patch(name,new):
        nonlocal source
        old=original[name][0]
        digest=hashlib.sha256(old.encode()).hexdigest()
        source=replace_function(source,name,digest,new)
        patches.append(dict(function=name,original_sha256=digest,replacement_sha256=hashlib.sha256(new.encode()).hexdigest()))

    body=original['BUM'][0]
    added=''
    for slot,start,race,kind in [(5,9,'HUMAN','USER'),(6,10,'UNDEAD','COMPUTER')]:
        added+=f'call SetPlayerStartLocation(Player({slot}),{start})\ncall ForcePlayerStartLocation(Player({slot}),{start})\n'
        added+=f'call SetPlayerColor(Player({slot}),ConvertPlayerColor({slot}))\ncall SetPlayerRacePreference(Player({slot}),RACE_PREF_{race})\n'
        added+=f'call SetPlayerRaceSelectable(Player({slot}),false)\ncall SetPlayerController(Player({slot}),MAP_CONTROL_{kind})\n'
    patch('BUM',body.replace('endfunction',added+'endfunction'))
    body=original['BUN'][0]
    added='call SetPlayerTeam(Player(5),0)\ncall SetPlayerTeam(Player(6),1)\ncall SetPlayerState(Player(5),PLAYER_STATE_ALLIED_VICTORY,1)\ncall SetPlayerState(Player(6),PLAYER_STATE_ALLIED_VICTORY,1)\n'
    for slot,new_slot in [(p,5) for p in range(5)]+[(p,6) for p in range(8,12)]:
        added+=f'call SetPlayerAllianceStateAllyBJ(Player({slot}),Player({new_slot}),true)\ncall SetPlayerAllianceStateAllyBJ(Player({new_slot}),Player({slot}),true)\n'
    patch('BUN',body.replace('endfunction',added+'endfunction'))
    body='function BUO takes nothing returns nothing\n'
    for start in [0,1,2,3,9]:
        body+=f'call SetStartLocPrioCount({start},4)\n'
        for idx,other in enumerate(i for i in [0,1,2,3,9] if i!=start):
            body+=f'call SetStartLocPrio({start},{idx},{other},MAP_LOC_PRIO_HIGH)\n'
    patch('BUO',body+'endfunction\n')
    body=original['config'][0].replace('SetPlayers(9)','SetPlayers(11)').replace('SetTeams(9)','SetTeams(2)')
    body=body.replace('call BUM()','call DefineStartLocation(9,4736.,640.)\ncall DefineStartLocation(10,6912.,2816.)\ncall BUM()')
    patch('config',body)
    body=original['main'][0].replace('3072.-GetCameraMargin(CAMERA_MARGIN_RIGHT)','7168.-GetCameraMargin(CAMERA_MARGIN_RIGHT)')
    patch('main',body)
    source=inject_module(source,(ROOT/'src/roster.j').read_text(encoding='utf8'))
    members={'war3map.j':source.encode('utf8')}
    for name,fn in [('war3map.w3e',extend_terrain),('war3map.wpm',extend_pathing),('war3map.shd',extend_shadow),('war3map.doo',extend_doodads),('war3map.w3i',extend_info)]:
        members[name]=fn((baseline/name).read_bytes())
    manifest=dict(stage='geometry and lobby only; gameplay not integrated',human_slots=[0,1,2,3,5],enemy_slots=[8,9,10,11,6],
                  original_world_origin=[-4096,-4096],terrain_cells=[96,64],playable_cells=[80,48],
                  fifth_translation=[4096,0],fifth_spawn=[6784,2688],fifth_hero_normal=[4992,896],fifth_hero_separated=[5760,1664],
                  fifth_battle_rect=[5120,1024,7232,3136],patches=patches,runtime_verified=False)
    return members,manifest
