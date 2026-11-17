// Logical indices are 0..4. Existing HQ arrays retain actual player slots.
function MJ_Player takes integer i returns player
    if i>=0 and i<4 then
        return Player(i)
    elseif i==4 then
        return Player(5)
    endif
    return null
endfunction

function MJ_Enemy takes integer i returns player
    if i>=0 and i<4 then
        return Player(i+8)
    elseif i==4 then
        return Player(6)
    endif
    return null
endfunction

function MJ_Index takes player p returns integer
    local integer slot=GetPlayerId(p)
    if p==null then
        return -1
    elseif slot>=0 and slot<4 then
        return slot
    elseif slot==5 then
        return 4
    endif
    return -1
endfunction

function MJ_EnemyOf takes player p returns player
    return MJ_Enemy(MJ_Index(p))
endfunction

function MJ_HumanOf takes player p returns player
    local integer slot=GetPlayerId(p)
    if p==null then
        return null
    elseif slot>=8 and slot<=11 then
        return MJ_Player(slot-8)
    elseif slot==6 then
        return MJ_Player(4)
    endif
    return null
endfunction

function MJ_IsActive takes integer i returns boolean
    local player p=MJ_Player(i)
    local boolean active=false
    if p!=null then
        set active=GetPlayerController(p)==MAP_CONTROL_USER and GetPlayerSlotState(p)==PLAYER_SLOT_STATE_PLAYING
    endif
    set p=null
    return active
endfunction

function MJ_TotalMonsters takes nothing returns integer
    local integer i=0
    local integer count=0
    loop
        exitwhen i>=5
        set count=count+GetPlayerState(MJ_Enemy(i),PLAYER_STATE_RESOURCE_FOOD_USED)
        set i=i+1
    endloop
    return count
endfunction

// One-based adapters are only for reviewed GUI player loops / scoreboard rows.
function MJ_Human1 takes integer i returns player
    return MJ_Player(i-1)
endfunction

function MJ_Enemy1 takes integer i returns player
    return MJ_Enemy(i-1)
endfunction

function MJ_Row takes player p returns integer
    return MJ_Index(p)+2
endfunction
