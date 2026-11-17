// Deterministic core: logical player indices 0..4, no local UI or timers.
globals
integer MJ_SelectState=0
integer MJ_StartRequests=0
integer MJ_HeroCount=0
integer array MJ_HeroIds
integer array MJ_Chosen
boolean array MJ_Ready
boolean array MJ_Present
endglobals

function MJ_ResetSelection takes nothing returns nothing
    local integer i=0
    set MJ_SelectState=0
    set MJ_StartRequests=0
    loop
        exitwhen i>=5
        set MJ_Chosen[i]=0
        set MJ_Ready[i]=false
        set MJ_Present[i]=false
        set i=i+1
    endloop
endfunction

function MJ_JoinSelection takes integer i returns nothing
    if MJ_SelectState==0 and i>=0 and i<5 then
        set MJ_Present[i]=true
    endif
endfunction

function MJ_BeginSelection takes nothing returns nothing
    if MJ_SelectState==0 then
        set MJ_SelectState=1
    endif
endfunction

function MJ_IsHero takes integer hero returns boolean
    local integer i=0
    if hero==0 then
        return false
    endif
    loop
        exitwhen i>=MJ_HeroCount
        if MJ_HeroIds[i]==hero then
            return true
        endif
        set i=i+1
    endloop
    return false
endfunction

function MJ_TryStart takes nothing returns nothing
    local integer i=0
    local integer j=0
    local integer count=0
    if MJ_SelectState!=1 then
        return
    endif
    loop
        exitwhen i>=5
        if MJ_Present[i] then
            set count=count+1
            if not MJ_Ready[i] or not MJ_IsHero(MJ_Chosen[i]) then
                return
            endif
            set j=0
            loop
                exitwhen j>=i
                if MJ_Present[j] and MJ_Chosen[j]==MJ_Chosen[i] then
                    return
                endif
                set j=j+1
            endloop
        endif
        set i=i+1
    endloop
    if count>0 then
        set MJ_SelectState=2
        set MJ_StartRequests=MJ_StartRequests+1
    endif
endfunction

function MJ_ConfirmHero takes integer i,integer hero returns boolean
    local integer j=0
    if MJ_SelectState!=1 or i<0 or i>=5 then
        return false
    endif
    if not MJ_Present[i] or MJ_Ready[i] or not MJ_IsHero(hero) then
        return false
    endif
    loop
        exitwhen j>=5
        if MJ_Present[j] and MJ_Ready[j] and MJ_Chosen[j]==hero then
            return false
        endif
        set j=j+1
    endloop
    set MJ_Chosen[i]=hero
    set MJ_Ready[i]=true
    call MJ_TryStart()
    return true
endfunction

function MJ_CancelReady takes integer i returns boolean
    if MJ_SelectState!=1 or i<0 or i>=5 then
        return false
    endif
    if not MJ_Present[i] or not MJ_Ready[i] then
        return false
    endif
    set MJ_Ready[i]=false
    set MJ_Chosen[i]=0
    return true
endfunction

function MJ_LeaveSelection takes integer i returns nothing
    // Once Starting, the chosen ids are a locked initialization snapshot.
    // Gameplay's leave handler owns departures after that boundary.
    if MJ_SelectState!=1 or i<0 or i>=5 then
        return
    endif
    set MJ_Present[i]=false
    set MJ_Ready[i]=false
    set MJ_Chosen[i]=0
    call MJ_TryStart()
endfunction
