// Must be run in a real Warcraft client; compilation alone is not a pass.
function MJ_TestRoster takes nothing returns nothing
    local integer i=0
    local integer failures=0
    loop
        exitwhen i>=5
        if MJ_Index(MJ_Player(i))!=i or MJ_HumanOf(MJ_Enemy(i))!=MJ_Player(i) or MJ_EnemyOf(MJ_Player(i))!=MJ_Enemy(i) then
            set failures=failures+1
        endif
        set i=i+1
    endloop
    if MJ_Player(4)!=Player(5) or MJ_Enemy(4)!=Player(6) or MJ_Row(Player(5))!=6 then
        set failures=failures+1
    endif
    if MJ_Index(Player(4))!=-1 or MJ_Index(Player(7))!=-1 or MJ_Player(-1)!=null or MJ_Player(5)!=null then
        set failures=failures+1
    endif
    call BJDebugMsg("MJ roster assertion failures: "+I2S(failures))
endfunction
