globals
boolean MJ_DefeatStarted=false
endglobals
function MJ_BeginDefeat takes nothing returns boolean
    if MJ_DefeatStarted then
        return false
    endif
    set MJ_DefeatStarted=true
    call DisableTrigger(Ja)
    call DisableTrigger(JY)
    call DisableTrigger(JW)
    call DisableTrigger(JX)
    call DisableTrigger(JT)
    call PauseTimer(Fw)
    return true
endfunction
