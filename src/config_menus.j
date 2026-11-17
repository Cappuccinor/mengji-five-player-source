function MJ_ReopenConfigMenus takes nothing returns nothing
    local player host=MJ_SelectionHost()
    if MJ_FreePhase!=0 or MJ_AllHeroMode or CountPlayersInForceBJ(Fa)==0 then
        return
    endif
    if IsTriggerEnabled(GM) then
        call MJ_RefreshProgressDifficulty(host)
    elseif IsTriggerEnabled(GJ) or IsTriggerEnabled(Gg) then
        call DialogDisplayBJ(true,Fq,host)
    endif
    set host=null
endfunction
