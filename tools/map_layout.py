"""Narrow, validated v25 map geometry transforms; original cells stay fixed."""
from __future__ import annotations
import copy
import struct


def read_terrain(data: bytes) -> dict:
    if data[:4] != b'W3E!' or struct.unpack_from('<I', data, 4)[0] != 11:
        raise ValueError('unsupported terrain format')
    pos = 13
    for _ in range(2):
        count = struct.unpack_from('<I', data, pos)[0]
        if count > 256:
            raise ValueError('invalid terrain tileset count')
        pos += 4 + count * 4
    width, height, x, y = struct.unpack_from('<IIff', data, pos)
    start = pos + 16
    if len(data) != start + width * height * 7:
        raise ValueError('invalid terrain vertex extent')
    return dict(width=width, height=height, origin=(x,y), header=data[:start],
                dimension_offset=pos, rows=[data[start+i*width*7:start+(i+1)*width*7] for i in range(height)])


def extend_terrain(data: bytes) -> bytes:
    t = read_terrain(data)
    if (t['width'],t['height'],t['origin']) != (65,65,(-4096.0,-4096.0)):
        raise ValueError('terrain differs from approved baseline geometry')
    header = bytearray(t['header'])
    struct.pack_into('<I', header, t['dimension_offset'], 97)
    return bytes(header) + b''.join(row+row[33*7:] for row in t['rows'])


def _extend_grid(data: bytes) -> bytes:
    if len(data) != 256*256:
        raise ValueError('expected 256 by 256 grid')
    return b''.join(data[y*256:(y+1)*256] + data[y*256+128:(y+1)*256] for y in range(256))


def extend_pathing(data: bytes) -> bytes:
    if data[:4] != b'MP3W' or struct.unpack_from('<III',data,4) != (0,256,256):
        raise ValueError('unsupported pathing grid')
    return b'MP3W' + struct.pack('<III',0,384,256) + _extend_grid(data[16:])


def extend_shadow(data: bytes) -> bytes:
    return _extend_grid(data)


def read_doodads(data: bytes) -> dict:
    if data[:4] != b'W3do' or struct.unpack_from('<II',data,4) != (8,11):
        raise ValueError('unsupported doodad format')
    count=struct.unpack_from('<I',data,12)[0]
    if count>100000:
        raise ValueError('invalid doodad count')
    records=[]
    pos=16
    for _ in range(count):
        start=pos
        sets=struct.unpack_from('<I',data,pos+42)[0]
        pos+=46
        if sets>1000:
            raise ValueError('invalid doodad item sets')
        for _ in range(sets):
            items=struct.unpack_from('<I',data,pos)[0]
            if items>1000:
                raise ValueError('invalid doodad items')
            pos+=4+items*8
        pos+=4
        if pos>len(data):
            raise ValueError('truncated doodad')
        records.append(data[start:pos])
    if data[pos:] != bytes(8):
        raise ValueError('unsupported special doodads: explicit extension required')
    return dict(header=data[:12],records=records,tail=data[pos:])


def extend_doodads(data: bytes) -> bytes:
    parsed=read_doodads(data)
    records=parsed['records'][:]
    next_id=max(struct.unpack_from('<I',r,len(r)-4)[0] for r in records)+1
    for record in parsed['records']:
        x,y=struct.unpack_from('<ff',record,8)
        if 0 <= x <= 3136 and 0 <= y <= 3136:
            clone=bytearray(record)
            struct.pack_into('<f',clone,8,x+4096)
            struct.pack_into('<I',clone,len(clone)-4,next_id)
            records.append(bytes(clone))
            next_id+=1
    return parsed['header']+struct.pack('<I',len(records))+b''.join(records)+parsed['tail']


class _Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def number(self, fmt):
        result = struct.unpack_from('<'+fmt, self.data, self.pos)
        self.pos += struct.calcsize('<'+fmt)
        return result[0] if len(result)==1 else result

    def string(self):
        end = self.data.index(b'\0', self.pos)
        result = self.data[self.pos:end]
        self.pos = end+1
        return result


def read_info(data: bytes) -> dict:
    r = _Reader(data)
    if r.number('I') != 25:
        raise ValueError('only classic w3i format 25 is supported')
    r.pos = 12
    for _ in range(4):
        r.string()
    camera_offset = r.pos
    camera = r.number('8f')
    r.number('4i')
    size_offset = r.pos
    size = r.number('2i')
    r.number('IBi')  # flags, tileset, loading-screen background
    for _ in range(4):
        r.string()
    r.number('i')
    for _ in range(4):
        r.string()
    r.number('Ifff4BI')  # fog style, range, density, color, weather
    r.string()
    r.number('5B')  # light and water color
    player_offset = r.pos
    count = r.number('I')
    if count > 12:
        raise ValueError('unexpected player count')
    players = []
    for _ in range(count):
        slot, kind, race, fixed = r.number('4i')
        name = r.string()
        x,y,low,high = r.number('ffII')
        players.append(dict(id=slot,type=kind,race=race,fixed=fixed,name=name,x=x,y=y,low=low,high=high))
    force_count = r.number('I')
    if force_count > 12:
        raise ValueError('unexpected force count')
    forces = []
    for _ in range(force_count):
        flags,mask = r.number('II')
        forces.append(dict(flags=flags,mask=mask,name=r.string()))
    return dict(prefix=data[:player_offset],camera_offset=camera_offset,size_offset=size_offset,
                camera=camera,size=size,players=players,forces=forces,tail=data[r.pos:])


def write_info(info: dict) -> bytes:
    out = bytearray(info['prefix'])
    struct.pack_into('<8f',out,info['camera_offset'],*info['camera'])
    struct.pack_into('<2i',out,info['size_offset'],*info['size'])
    out += struct.pack('<I',len(info['players']))
    for p in info['players']:
        out += struct.pack('<4i',p['id'],p['type'],p['race'],p['fixed'])
        out += p['name']+b'\0'+struct.pack('<ffII',p['x'],p['y'],p['low'],p['high'])
    out += struct.pack('<I',len(info['forces']))
    for f in info['forces']:
        out += struct.pack('<II',f['flags'],f['mask'])+f['name']+b'\0'
    return bytes(out)+info['tail']


def extend_info(data: bytes) -> bytes:
    info = read_info(data)
    if info['size'] != (48,48) or [p['id'] for p in info['players']] != [0,1,2,3,4,8,9,10,11]:
        raise ValueError('w3i does not match approved player geometry')
    new_player = copy.deepcopy(info['players'][1])
    new_player.update(id=5,name='玩家五'.encode('utf8'),x=4736.0,y=640.0,low=0,high=15)
    new_enemy = copy.deepcopy(info['players'][6])
    new_enemy.update(id=6,name='第五路怪物'.encode('utf8'),x=6912.0,y=2816.0,low=0,high=0)
    info['players'] += [new_player,new_enemy]
    info['players'].sort(key=lambda p:p['id'])
    for p in info['players']:
        if p['id'] in [0,1,2,3]:
            p['high'] |= 1<<5
    if len(info['forces']) != 2 or info['forces'][1]['mask'] != 3840:
        raise ValueError('unexpected baseline forces')
    # Original first force includes unused slot bits. Slot 6 is now an enemy,
    # so adding a second force bit without removing the old one is incorrect.
    info['forces'][0]['mask'] = 63
    info['forces'][1]['mask'] = 3904
    camera=list(info['camera'])
    right=max(camera[::2])
    for i in (0,2,4,6):
        if camera[i]==right:
            camera[i]+=4096.0
    info['camera']=tuple(camera)
    info['size']=(80,48)
    return write_info(info)
