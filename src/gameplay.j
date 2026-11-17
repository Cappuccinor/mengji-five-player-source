function MJ_DefeatActivePlayers takes string reason returns nothing
    local integer i=0
    loop
        exitwhen i>=5
        if MJ_IsActive(i) then
            call CustomDefeatBJ(MJ_Player(i),reason)
        endif
        set i=i+1
    endloop
endfunction
