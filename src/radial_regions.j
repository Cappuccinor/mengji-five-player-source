globals
hashtable MJ_RadialData=InitHashtable()
region MJ_RadialTarget=null
rect MJ_RadialArea=null
integer MJ_RadialRequested=0
integer MJ_RadialRegistered=0
group MJ_SelectionDisplays=CreateGroup()
endglobals

// Only registered staging/display units are eligible. A preview promoted to
// the player's actual hero is explicitly protected, even if still registered.
function MJ_ClearSelectionDisplay takes unit candidate returns nothing
    if IsUnitInGroup(candidate,MJ_SelectionDisplays) then
        call GroupRemoveUnit(MJ_SelectionDisplays,candidate)
        if candidate!=HQ[GetPlayerId(GetOwningPlayer(candidate))] then
            call RemoveUnit(candidate)
        endif
    endif
endfunction

function MJ_RadialRect takes real x0,real y0,real x1,real y1,real a,real b,real c,real d returns rect
    local real lx=RMinBJ(a*x0,a*x1)+RMinBJ(b*y0,b*y1)
    local real hx=RMaxBJ(a*x0,a*x1)+RMaxBJ(b*y0,b*y1)
    local real ly=RMinBJ(c*x0,c*x1)+RMinBJ(d*y0,d*y1)
    local real hy=RMaxBJ(c*x0,c*x1)+RMaxBJ(d*y0,d*y1)
    local rect area=Rect(lx,ly,hx,hy)
    local integer key=GetHandleId(area)
    call SaveReal(MJ_RadialData,key,0,x0)
    call SaveReal(MJ_RadialData,key,1,y0)
    call SaveReal(MJ_RadialData,key,2,x1)
    call SaveReal(MJ_RadialData,key,3,y1)
    call SaveReal(MJ_RadialData,key,4,a)
    call SaveReal(MJ_RadialData,key,5,b)
    call SaveReal(MJ_RadialData,key,6,c)
    call SaveReal(MJ_RadialData,key,7,d)
    call SaveReal(MJ_RadialData,key,8,a*d-b*c)
    return area
endfunction

function MJ_RadialContains takes rect area,real x,real y returns boolean
    local integer key=GetHandleId(area)
    local real det=LoadReal(MJ_RadialData,key,8)
    local real u=0.
    local real v=0.
    if det==0. then
        return RectContainsCoords(area,x,y)
    endif
    set u=(LoadReal(MJ_RadialData,key,7)*x-LoadReal(MJ_RadialData,key,5)*y)/det
    set v=(-LoadReal(MJ_RadialData,key,6)*x+LoadReal(MJ_RadialData,key,4)*y)/det
    return u>=LoadReal(MJ_RadialData,key,0) and u<=LoadReal(MJ_RadialData,key,2) and v>=LoadReal(MJ_RadialData,key,1) and v<=LoadReal(MJ_RadialData,key,3)
endfunction

function MJ_RadialContainsUnit takes rect area,unit who returns boolean
    return MJ_RadialContains(area,GetUnitX(who),GetUnitY(who))
endfunction

function MJ_RadialRandomLoc takes rect area returns location
    local integer key=GetHandleId(area)
    local real u=0.
    local real v=0.
    if LoadReal(MJ_RadialData,key,8)==0. then
        return GetRandomLocInRect(area)
    endif
    set u=GetRandomReal(LoadReal(MJ_RadialData,key,0),LoadReal(MJ_RadialData,key,2))
    set v=GetRandomReal(LoadReal(MJ_RadialData,key,1),LoadReal(MJ_RadialData,key,3))
    return Location(LoadReal(MJ_RadialData,key,4)*u+LoadReal(MJ_RadialData,key,5)*v,LoadReal(MJ_RadialData,key,6)*u+LoadReal(MJ_RadialData,key,7)*v)
endfunction

function MJ_RadialGroupEnum takes group units,rect area,boolexpr predicate returns nothing
    local group found=null
    local unit who=null
    if LoadReal(MJ_RadialData,GetHandleId(area),8)==0. then
        call GroupEnumUnitsInRect(units,area,predicate)
        return
    endif
    set found=CreateGroup()
    call GroupEnumUnitsInRect(found,area,predicate)
    call GroupClear(units)
    loop
        set who=FirstOfGroup(found)
        exitwhen who==null
        call GroupRemoveUnit(found,who)
        if MJ_RadialContainsUnit(area,who) then
            call GroupAddUnit(units,who)
        endif
    endloop
    call DestroyGroup(found)
    set found=null
endfunction

function MJ_RadialFloorCell takes real value returns real
    local real result=I2R(R2I(value/32.))*32.
    if result>value then
        set result=result-32.
    endif
    return result
endfunction

function MJ_RadialRegionWorker takes nothing returns nothing
    local region target=MJ_RadialTarget
    local rect area=MJ_RadialArea
    local integer key=GetHandleId(area)
    local real det=LoadReal(MJ_RadialData,key,8)
    local real ia=0.
    local real ib=0.
    local real ic=0.
    local real id=0.
    local real y=0.
    local real lo=0.
    local real hi=0.
    local real left=0.
    local real right=0.
    local real t0=0.
    local real t1=0.
    local boolean valid=true
    local rect strip=null
    if det==0. then
        call RegionAddRect(target,area)
        return
    endif
    set ia=LoadReal(MJ_RadialData,key,7)/det
    set ib=-LoadReal(MJ_RadialData,key,5)/det
    set ic=-LoadReal(MJ_RadialData,key,6)/det
    set id=LoadReal(MJ_RadialData,key,4)/det
    set y=MJ_RadialFloorCell(GetRectMinY(area))+16.
    loop
        exitwhen y>GetRectMaxY(area)
        set lo=GetRectMinX(area)
        set hi=GetRectMaxX(area)
        set valid=true
        if RAbsBJ(ia)<0.000001 then
            set valid=ib*y>=LoadReal(MJ_RadialData,key,0) and ib*y<=LoadReal(MJ_RadialData,key,2)
        else
            set t0=(LoadReal(MJ_RadialData,key,0)-ib*y)/ia
            set t1=(LoadReal(MJ_RadialData,key,2)-ib*y)/ia
            set lo=RMaxBJ(lo,RMinBJ(t0,t1))
            set hi=RMinBJ(hi,RMaxBJ(t0,t1))
        endif
        if RAbsBJ(ic)<0.000001 then
            set valid=valid and id*y>=LoadReal(MJ_RadialData,key,1) and id*y<=LoadReal(MJ_RadialData,key,3)
        else
            set t0=(LoadReal(MJ_RadialData,key,1)-id*y)/ic
            set t1=(LoadReal(MJ_RadialData,key,3)-id*y)/ic
            set lo=RMaxBJ(lo,RMinBJ(t0,t1))
            set hi=RMinBJ(hi,RMaxBJ(t0,t1))
        endif
        set left=MJ_RadialFloorCell(lo)+16.
        if left<lo then
            set left=left+32.
        endif
        set right=MJ_RadialFloorCell(hi)+16.
        if right>hi then
            set right=right-32.
        endif
        if valid and left<=right then
            set strip=Rect(left-15.,y-15.,right+15.,y+15.)
            call RegionAddRect(target,strip)
            call RemoveRect(strip)
        endif
        set y=y+32.
    endloop
    set strip=null
    set MJ_RadialRegistered=MJ_RadialRegistered+1
    set target=null
    set area=null
endfunction

function MJ_RadialAddRegion takes region target,rect area returns nothing
    if LoadReal(MJ_RadialData,GetHandleId(area),8)==0. then
        call RegionAddRect(target,area)
        return
    endif
    set MJ_RadialRequested=MJ_RadialRequested+1
    set MJ_RadialTarget=target
    set MJ_RadialArea=area
    call ExecuteFunc("MJ_RadialRegionWorker")
    set MJ_RadialTarget=null
    set MJ_RadialArea=null
endfunction
