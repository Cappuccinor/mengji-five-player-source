// Per-lane spawn intervals use live roster members; singleton keeps initial cadence.
function MJ_CombatLaneAlive takes integer i returns boolean
    return MJ_IsActive(i) and IsPlayerInForce(MJ_Player(i),Fa) and IsUnitAliveBJ(LoadUnitHandle(DI,GetHandleId(MJ_Player(i)),$9DC2FEEA))
endfunction

function MJ_LiveLaneCount takes nothing returns integer
    local integer i=0
    local integer count=0
    loop
        exitwhen i>=5
        if MJ_CombatLaneAlive(i) then
            set count=count+1
        endif
        set i=i+1
    endloop
    return count
endfunction

function MJ_SpawnContribution takes integer i,integer count returns real
    local integer monsters=0
    if count<=1 or not MJ_CombatLaneAlive(i) then
        return 0.
    endif
    set monsters=GetPlayerState(MJ_Enemy(i),PLAYER_STATE_RESOURCE_FOOD_USED)
    if monsters<1 then
        set monsters=1
    endif
    return Pow(I2R(monsters),.4)*.2/I2R(count-1)
endfunction

function MJ_RefreshSpawnIntervals takes nothing returns nothing
    local integer i=0
    local integer j=0
    local integer count=MJ_LiveLaneCount()
    local real interval=0.
    loop
        exitwhen i>=5
        set interval=0.
        if count==1 and MJ_CombatLaneAlive(i) then
            set interval=1.
        elseif count>1 and MJ_CombatLaneAlive(i) then
            set j=0
            loop
                exitwhen j>=5
                if i!=j then
                    set interval=interval+MJ_SpawnContribution(j,count)
                endif
                set j=j+1
            endloop
        endif
        call SaveReal(DI,GetHandleId(MJ_Player(i)),$42264FE6,interval)
        set i=i+1
    endloop
endfunction
