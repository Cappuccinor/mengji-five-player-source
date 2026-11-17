"""Five equal spokes around one hub. Shared numeric source for terrain and JASS."""
import math
import struct
from collections import deque
from pathlib import Path
from tools.map_layout import read_terrain, read_doodads, read_info, write_info, extend_info

ANGLES = (90,18,-54,-126,162)
SIGNS = ((-1,1),(1,1),(-1,-1),(1,-1),(1,1))
LATERAL = 0.65
ORIGIN = -6144
CELLS = 96
GRID = CELLS*4
LIMIT = 5120


def lane_matrix(lane):
    theta=math.radians(ANGLES[lane]); c,s=math.cos(theta),math.sin(theta)
    sx,sy=SIGNS[lane]; k=math.sqrt(0.5)
    return ((c+s*LATERAL)*sx*k,(c-s*LATERAL)*sy*k,
            (s-c*LATERAL)*sx*k,(s+c*LATERAL)*sy*k)


def forward(lane,x,y):
    if lane==4:x-=4096
    a,b,c,d=lane_matrix(lane)
    return a*x+b*y,c*x+d*y


def inverse(lane,x,y):
    a,b,c,d=lane_matrix(lane); det=a*d-b*c
    ox=(d*x-b*y)/det; oy=(-c*x+a*y)/det
    return ox+(4096 if lane==4 else 0),oy


def contains(lane,rect,x,y):
    ox,oy=inverse(lane,x,y)
    return rect[0]-1e-6<=ox<=rect[2]+1e-6 and rect[1]-1e-6<=oy<=rect[3]+1e-6


def radial_coordinates(lane,x,y):
    angle=math.radians(ANGLES[lane]);c,s=math.cos(angle),math.sin(angle)
    return c*x+s*y,-s*x+c*y


def surface(x,y):
    """0 wilderness, 1 field, 2 route paving, 3 hub, 4 side arena.

    The old auxiliary (CO) arena is moved to the gap below the two lower roads.
    It remains a teleport destination; it is not a sixth lane.
    """
    radius=math.hypot(x,y)
    if radius<=800:return 3
    if abs(x)<=512 and -3520<=y<=-2880:return 4
    if abs(x)<=800 and -5000<=y<=-4000:return 4
    for i in range(5):
        r,v=radial_coordinates(i,x,y)
        # Preserve the authored quadrant rather than clipping it to an invented
        # wedge. The original northern selection/southern auxiliary rooms are
        # relocated separately above, so must not be cloned into combat lanes.
        sx,sy=inverse(i,x,y)
        if i==4:sx-=4096
        sx*=SIGNS[i][0];sy*=SIGNS[i][1]
        combat=(0<=sx<=3136 and 0<=sy<=3136 and not (sx<=768 and sy>=2304))
        # Retain precisely the existing flat shop landing's old envelope.
        landing=(1200<=r<=2300 and -950<=v<=150 and abs(v)<=min(1100,.55*r))
        if combat or landing:
            if abs(v)<190 or (r-3801.4)**2+v*v<410**2:return 2
            return 1
    return 0


def path_index(x,y):
    return max(0,min(GRID-1,int((y-ORIGIN)//32)))*GRID+max(0,min(GRID-1,int((x-ORIGIN)//32)))


def decoration_exclusion(x,y):
    # Keep the existing decorative set stable while restoring combat ground.
    # Expanding the visual terrain footprint must not silently remove objects
    # on authored impassable shoulders. Object restoration is a separate pass.
    if math.hypot(x,y)<=800:return True
    if abs(x)<=512 and -3520<=y<=-2880:return True
    if abs(x)<=800 and -5000<=y<=-4000:return True
    return any(600<=r<=4550 and abs(v)<=min(1100,.55*r)
               for r,v in (radial_coordinates(i,x,y) for i in range(5)))


def reachable(pathing):
    start=path_index(0,0); seen={start}; pending=deque([start])
    while pending:
        p=pending.popleft();x=p%GRID;y=p//GRID
        for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            q=ny*GRID+nx
            if 0<=nx<GRID and 0<=ny<GRID and q not in seen and not pathing[q]&2:
                seen.add(q);pending.append(q)
    return seen


def minimap(baseline):
    # Reproject the original authored preview with the terrain. The footprint
    # still comes from the new pathing, but no invented grass palette remains.
    raw=(baseline/'war3mapMap.tga').read_bytes()
    width,height=struct.unpack_from('<HH',raw,12)
    if raw[2]!=2 or raw[16]!=24:raise ValueError('unexpected source minimap format')
    origin_top=bool(raw[17]&32);start=18+raw[0]
    source_limit=read_info((baseline/'war3map.w3i').read_bytes())['size'][0]*64.
    size=256
    pixels=bytearray()
    for y in range(size):
        wy=LIMIT-(y+0.5)*LIMIT*2/size
        for x in range(size):
            wx=-LIMIT+(x+0.5)*LIMIT*2/size
            if not surface(wx,wy):
                pixels.append(0);continue
            sx,sy=terrain_source(wx,wy)
            px=max(0,min(width-1,int((sx/source_limit+1)*width/2)))
            py=max(0,min(height-1,int((1-sy/source_limit)*height/2)))
            if not origin_top:py=height-1-py
            b,g,r=raw[start+(py*width+px)*3:start+(py*width+px)*3+3]
            pixels.append((r//32)*32+(g//32)*4+b//64)
    palette=b''.join(bytes(((i%4)*85,((i//4)%8)*255//7,(i//32)*255//7,255)) for i in range(256))
    offset=156+1024
    header=struct.pack('<4s6I',b'BLP1',1,0,size,size,5,0)
    header+=struct.pack('<16I',offset,*([0]*15))+struct.pack('<16I',len(pixels),*([0]*15))
    return header+palette+pixels


def minimap_tga(blp):
    # The original also includes a TGA. Classic Warcraft prefers it to the BLP.
    size=256;palette=blp[156:1180];indices=blp[1180:]
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,size,size,24,32)
    return header+b''.join(palette[i*4:i*4+3] for i in indices)


def terrain_source(x,y):
    """Map the five spokes back to the original terrain, including shared areas."""
    if abs(x)<=512 and -3520<=y<=-2880:return x,y+6064
    if abs(x)<=800 and -5000<=y<=-4000:return x,y+1800
    if math.hypot(x,y)<=800:return x,y
    lane=max(range(5),key=lambda i:radial_coordinates(i,x,y)[0])
    sx,sy=inverse(lane,x,y)
    return sx-(4096 if lane==4 else 0),sy


def sample_terrain(source,x,y):
    sx,sy=terrain_source(x,y)
    fx=max(0.,min(source['width']-1.,(sx-source['origin'][0])/128.))
    fy=max(0.,min(source['height']-1.,(sy-source['origin'][1])/128.))
    def vertex(ix,iy):
        return struct.unpack_from('<HHBBB',source['rows'][iy],ix*7)
    nearest=vertex(round(fx),round(fy))
    # Interpolate fine ground relief while retaining original cliff layers,
    # cliff textures, water and ramps on the destination terrain grid.
    ix,iy=int(fx),int(fy);dx,dy=fx-ix,fy-iy
    height=0.
    for nx,wx in ((ix,1.-dx),(min(ix+1,source['width']-1),dx)):
        for ny,wy in ((iy,1.-dy),(min(iy+1,source['height']-1),dy)):
            v=vertex(nx,ny)
            height+=v[0]*wx*wy
    # Each complete shop set has a flat landing connected across to its road.
    # Source cliffs are preserved elsewhere, not underneath building footprints.
    for lane in range(5):
        r,v=radial_coordinates(lane,x,y)
        if 1200<=r<=2300 and -950<=v<=150:
            return struct.pack('<HHBBB',8192,8192,nearest[2]&15,nearest[3],0xF2)
    return struct.pack('<HHBBB',max(0,min(65535,round(height))),nearest[1],
                       nearest[2]&0x5F,nearest[3],nearest[4])


def source_ground_z(source,x,y):
    ix=max(0,min(source['width']-1,round((x-source['origin'][0])/128)))
    iy=max(0,min(source['height']-1,round((y-source['origin'][1])/128)))
    v=struct.unpack_from('<HHBBB',source['rows'][iy],ix*7)
    return (v[0]-8192)/4.+((v[4]&15)-2)*128.


def build_pathing(baseline,terrain):
    """Reproject authored lane restrictions; retain explicit shared landings.

    Doodad/building footprints remain an engine concern and are not encoded
    here. This restores the source WPM, not the removed decorative objects.
    """
    raw=(baseline/'war3map.wpm').read_bytes()
    if raw[:4]!=b'MP3W':raise ValueError('unsupported source pathing format')
    version,width,height=struct.unpack_from('<III',raw,4)
    if version!=0 or len(raw)!=16+width*height:
        raise ValueError('invalid source pathing extent')
    if (width,height)!=((terrain['width']-1)*4,(terrain['height']-1)*4):
        raise ValueError('source terrain/pathing dimensions differ')
    ox,oy=terrain['origin'];source=raw[16:];grid=bytearray()
    for iy in range(GRID):
        for ix in range(GRID):
            x,y=ORIGIN+(ix+.5)*32,ORIGIN+(iy+.5)*32
            area=surface(x,y)
            if not area:
                grid.append(10);continue
            # These spaces were deliberately relocated and flattened. Keep
            # their existing access, including the short road-side shop joins.
            if area in (3,4) or any(1200<=r<=2300 and -950<=v<=150
                    for r,v in (radial_coordinates(i,x,y) for i in range(5))):
                grid.append(0);continue
            sx,sy=terrain_source(x,y)
            col,row=int((sx-ox)//32),int((sy-oy)//32)
            grid.append(source[row*width+col] if 0<=col<width and 0<=row<height else 10)
    return bytes(grid)


def build_geometry(baseline:Path):
    source=read_terrain((baseline/'war3map.w3e').read_bytes())
    header=bytearray(source['header']);pos=source['dimension_offset']
    struct.pack_into('<IIff',header,pos,CELLS+1,CELLS+1,ORIGIN,ORIGIN)
    vertices=bytearray()
    for iy in range(CELLS+1):
        for ix in range(CELLS+1):
            x=ORIGIN+ix*128;y=ORIGIN+iy*128
            vertices+=sample_terrain(source,x,y)
    grid=build_pathing(baseline,source)
    # Symmetric set of outer-lane decorations; avoid invisible pathing blockers
    # by keeping imported doodads outside the walkable lane footprint.
    parsed=read_doodads((baseline/'war3map.doo').read_bytes());records=[]
    for record in parsed['records']:
        x,y,z=struct.unpack_from('<fff',record,8)
        angle=struct.unpack_from('<f',record,20)[0]
        if not (x>0 and y>0 and math.hypot(x,y)>1700):continue
        for lane in range(5):
            sx,sy=SIGNS[lane];ox,oy=x*sx,y*sy
            if lane==4:ox+=4096
            nx,ny=forward(lane,ox,oy)
            if decoration_exclusion(nx,ny) or max(abs(nx),abs(ny))>4900:continue
            clone=bytearray(record)
            target=struct.unpack('<HHBBB',sample_terrain(source,nx,ny))
            target_z=(target[0]-8192)/4.+((target[4]&15)-2)*128.
            struct.pack_into('<fff',clone,8,nx,ny,z-source_ground_z(source,x,y)+target_z)
            struct.pack_into('<f',clone,20,angle+math.radians(ANGLES[lane]-45))
            struct.pack_into('<I',clone,len(clone)-4,len(records)+1);records.append(bytes(clone))
    doodads=parsed['header']+struct.pack('<I',len(records))+b''.join(records)+parsed['tail']
    info=read_info(extend_info((baseline/'war3map.w3i').read_bytes()))
    info['camera']=(-LIMIT,-LIMIT,-LIMIT,LIMIT,LIMIT,LIMIT,LIMIT,-LIMIT)
    info['size']=(80,80)
    for p in info['players']:
        if p['id'] in [0,1,2,3,5]:p['x'],p['y']=0.,0.
        if p['id'] in [8,9,10,11,6]:
            lane=[8,9,10,11,6].index(p['id']);sx,sy=SIGNS[lane]
            p['x'],p['y']=forward(lane,2688*sx+(4096 if lane==4 else 0),2688*sy)
    connected=reachable(grid);routes=[]
    for i in range(5):
        sx,sy=SIGNS[i];spawn=forward(i,2688*sx+(4096 if i==4 else 0),2688*sy)
        routes.append(dict(lane=i,angle=ANGLES[i],spawn=spawn,
                           spawn_to_center_connected=path_index(*spawn) in connected))
    mini=minimap(baseline)
    members={'war3map.w3e':bytes(header)+vertices,'war3map.wpm':b'MP3W'+struct.pack('<III',0,GRID,GRID)+grid,
             'war3map.shd':bytes(GRID*GRID),'war3map.doo':doodads,
             'war3map.w3i':write_info(info),'war3mapMap.blp':mini,'war3mapMap.tga':minimap_tga(mini)}
    return members,dict(layout='five radial lanes',routes=routes,terrain_cells=[96,96],
                        bounds=[-LIMIT,-LIMIT,LIMIT,LIMIT],doodads=len(records),runtime_verified=False)
