"""Final geometry migration after the hash-pinned legacy gameplay patches."""
import hashlib
import math
import re
from pathlib import Path
from tools.patching import functions, replace_function, inject_module
from tools.player_stage import calls
from tools.radial_layout import forward, lane_matrix, ANGLES, SIGNS, LIMIT, build_geometry

ROOT=Path(__file__).resolve().parents[1]
REGIONS=[
    'BY Bd Bh Bi Bq Bv Bz B3 B7 B8 B9 CK'.split(),
    'BZ Be Bj Bk Br Bw B0 B4 CB CC CD CL'.split(),
    'Ba Bf Bl Bm Bs Bx B1 B5 CE CF CG CM'.split(),
    'Bb Bg Bn Bo Bt By B2 B6 CH CI CJ CN Bp'.split(),
    ['MJ5_'+n for n in 'BZ Be Bj Bk Br Bw B0 B4 CB CC CD CL'.split()],
]
REGION_LANE={name:i for i,names in enumerate(REGIONS) for name in names}
HOUSES={'Cy':0,'C0':1,'C2':2,'C4':3,'MJ5_C0':4}
SHOP_LANES={n:i for i,names in enumerate([['Ci','Cm','Cn'],['Cj','Cl','Ct'],['Co','Cv','Cw'],['Ck','Cp','Cq']]) for n in names}
SHOP_TYPES={'$6E303041':0,'$6E6D726B':1,'$6E676164':2}

def shop_point(lane,kind):
    angle=math.radians(ANGLES[lane]);r=1450.+300.*kind;v=-650.
    return r*math.cos(angle)-v*math.sin(angle),r*math.sin(angle)+v*math.cos(angle)

NUMBER=re.compile(r'^-?(?:\d+(?:\.\d*)?|\.\d+)$')


def number(value):
    value=round(value,6)
    if abs(value)<0.0000005:value=0.
    return str(value) if '.' in str(value) else str(value)+'.'


def point(x,y):
    if x>3400:
        if y<0:return 640.,-4500.,None
        a,b=forward(4,x,y);return a,b,4
    if abs(x)<=768 and y>=2304:return x,y-6064,None
    if abs(x)<=768 and y<=-2304:return x,y-1800,None
    if max(abs(x),abs(y))<=512:return x,y,None
    lane=0 if x<0 and y>=0 else 1 if x>=0 and y>=0 else 2 if x<0 else 3
    a,b=forward(lane,x,y);return a,b,lane


def facing(lane,angle):
    if lane is None:return angle
    x,y=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    a,b,c,d=lane_matrix(lane)
    return math.degrees(math.atan2(c*x+d*y,a*x+b*y))%360


def prepare_radial(raw,baseline):
    source=raw.decode('utf8').replace('\r\n','\n');indexed=functions(source)
    if 'MJ_RadialRect' in indexed:raise ValueError('radial stage already applied')
    changes=[];coords=[];bodies={n:m[0] for n,m in indexed.items()}
    def patch(name,body):
        nonlocal source
        old=bodies[name]
        if old==body:return
        source=replace_function(source,name,hashlib.sha256(old.encode()).hexdigest(),body)
        bodies[name]=body
        changes.append(name)
    body=indexed['sk'][0]
    original_rects={name:[float(v) for v in args.split(',')]
                    for name,args in re.findall(r'set (\w+)=Rect\(([^\n]+)\)',body)}
    def region(match):
        name,args=match.groups();values=[float(v) for v in args.split(',')]
        if name in REGION_LANE:
            lane=REGION_LANE[name]
            index=REGIONS[lane].index(name)
            if index<12:
                # Use one canonical lane footprint, including the slightly
                # narrower original SW spawn, to keep all five areas equal.
                x0,y0,x1,y1=original_rects[REGIONS[1][index]]
                sx,sy=SIGNS[lane]
                values=[min(x0*sx,x1*sx),min(y0*sy,y1*sy),max(x0*sx,x1*sx),max(y0*sy,y1*sy)]
            values+=list(lane_matrix(lane))
            return 'set '+name+'=MJ_RadialRect('+','.join(map(number,values))+')'
        if name=='Bu':values=[-384,-3408,384,-2992]
        if name=='CO':values=[-768,-4872,768,-4104]
        return 'set '+name+'=Rect('+','.join(map(number,values))+')'
    body=re.sub(r'set (\w+)=Rect\(([^\n]+)\)',region,body)
    patch('sk',body)
    specs={'Location':(0,1,None),'CreateUnit':(2,3,4),'CreateItem':(1,2,None),
           'CreateDestructable':(1,2,3),'IssueBuildOrderById':(2,3,None),
           'CameraSetupSetDestPosition':(1,2,None),'DefineStartLocation':(1,2,None)}
    for name,m in list(functions(source).items()):
        if name=='sk':continue
        body=m[0];edits=[]
        for call,(xi,yi,ai) in specs.items():
            for start,end,args in calls(body,call):
                values=args.split(',')
                if len(values)<=max(xi,yi) or not NUMBER.fullmatch(values[xi]) or not NUMBER.fullmatch(values[yi]):continue
                x,y=float(values[xi]),float(values[yi]);nx,ny,lane=point(x,y)
                line=body[body.rfind('\n',0,start)+1:start]
                var=re.search(r'set (\w+)=$',line)
                if name=='sg' and call=='CreateUnit' and values[1] in SHOP_TYPES:
                    lane=4 if x>3400 else SHOP_LANES[var[1]]
                    nx,ny=shop_point(lane,SHOP_TYPES[values[1]])
                if call=='CreateUnit' and var and var[1] in HOUSES:
                    lane=HOUSES[var[1]];angle=math.radians(ANGLES[lane]+36);nx,ny=700*math.cos(angle),700*math.sin(angle)
                if call=='CreateUnit' and x==0 and y==1152:
                    # Keep the public shop outside BX and the pyramid construction footprint.
                    nx,ny,lane=-480.,-480.,None
                if call=='CreateDestructable' and var and var[1] in ['CZ','Ca','Cb','Cc','Cd','Ce','Cf','Cg']:
                    # Former four-way center walls are decorative in the side arena;
                    # retain handles for the original later RemoveDestructable calls.
                    nx,ny=x,y-4500;lane=None
                if call=='DefineStartLocation' and values[0] in ['0','1','2','3','4','9']:
                    nx,ny,lane=0.,0.,None
                values[xi],values[yi]=number(nx),number(ny)
                if ai is not None and NUMBER.fullmatch(values[ai]):values[ai]=number(facing(lane,float(values[ai])))
                replacement=call+'('+','.join(values)+')'
                if call=='CreateUnit' and abs(x)<=768 and y>=2304:
                    if not var:raise ValueError('selection display must have a unit handle')
                    replacement+='\ncall GroupAddUnit(MJ_SelectionDisplays,'+var[1]+')'
                if replacement!=body[start:end]:
                    edits.append((start,end,replacement));coords.append(dict(function=name,call=call,old=[x,y],new=[nx,ny]))
        for start,end,replacement in sorted(edits,reverse=True):body=body[:start]+replacement+body[end:]
        patch(name,body)
    for name in ['tc','to']:
        body=functions(source)[name][0]
        body,count=re.subn(r'(set Gj=PlaceRandomUnit\([^\n]+\))',r'\1\ncall GroupAddUnit(MJ_SelectionDisplays,Gj)',body)
        if count!=1:raise ValueError('selection display producer drift: '+name)
        patch(name,body)
    for name in ['uZ','v6']:
        body=functions(source)[name][0]
        if body.count('call RemoveUnit(GetEnumUnit())')!=1:raise ValueError('selection cleanup drift')
        patch(name,body.replace('call RemoveUnit(GetEnumUnit())','call MJ_ClearSelectionDisplay(GetEnumUnit())'))
    body=functions(source)['main'][0]
    body=re.sub(r'call SetCameraBounds\([^\n]+\)',
                'call SetCameraBounds(-5120.+GetCameraMargin(CAMERA_MARGIN_LEFT),-5120.+GetCameraMargin(CAMERA_MARGIN_BOTTOM),5120.-GetCameraMargin(CAMERA_MARGIN_RIGHT),5120.-GetCameraMargin(CAMERA_MARGIN_TOP),-5120.+GetCameraMargin(CAMERA_MARGIN_LEFT),5120.-GetCameraMargin(CAMERA_MARGIN_TOP),5120.-GetCameraMargin(CAMERA_MARGIN_RIGHT),-5120.+GetCameraMargin(CAMERA_MARGIN_BOTTOM))',body)
    patch('main',body)
    # Each original initializer is synchronous and takes no arguments. Give
    # these independent registrations their own Warcraft instruction budget.
    body=re.sub(r'^call (\w+)\(\)$',r'call ExecuteFunc("\1")',functions(source)['BUK'][0],flags=re.M)
    patch('BUK',body)
    # Every existing consumer of static regions must share exact geometry.
    substitutions={'RectContainsUnit':'MJ_RadialContainsUnit','GetRandomLocInRect':'MJ_RadialRandomLoc',
                   'GroupEnumUnitsInRect':'MJ_RadialGroupEnum','RegionAddRect':'MJ_RadialAddRegion'}
    for old,new in substitutions.items():source=re.sub(r'\b'+old+r'\(',new+'(',source)
    source=inject_module(source,(ROOT/'src/radial_regions.j').read_text(encoding='utf8'))
    members,geometry=build_geometry(baseline)
    return source.encode(),members,dict(geometry=geometry,changed_functions=changes,static_coordinates=coords,
                                        polygon_regions=len(REGION_LANE),runtime_verified=False)
