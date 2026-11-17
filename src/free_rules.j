// Local free policy. No platform ownership, balances or historical rank is invented.
globals
integer MJ_FreeVipPreset=3
boolean MJ_FreeFullSet=true
// 0 configuring/selecting; 1 authorized initialization; 2 gameplay.
integer MJ_FreePhase=0
hashtable MJ_FreeState=null
boolean array MJ_HeroOpeningApplied
boolean array MJ_FreeEffectsApplied
endglobals

function MJ_InitFreeRules takes nothing returns nothing
    if MJ_FreeState==null then
        set MJ_FreeState=InitHashtable()
    endif
endfunction

function MJ_ContentAvailable takes player p,string key returns boolean
    if MJ_Index(p)<0 or not IsPlayerInForce(p,Fa) then
        return false
    endif
    if key=="VIP0" then
        return true
    elseif key=="VIP1" then
        return MJ_FreeVipPreset>=1
    elseif key=="VIP2" then
        return MJ_FreeVipPreset>=2
    elseif key=="VIP3" then
        return MJ_FreeVipPreset>=3
    endif
    return key=="PTLB" or key=="LWJ" or key=="S1CB" or key=="S1ZQ" or key=="S1CH" or key=="S2ZQ" or key=="TXZ" or key=="TRE" or key=="PET1" or key=="PET2" or key=="IMBAG" or key=="3FJT" or key=="BOOKD" or key=="BOOKC" or key=="BOOKB" or key=="BOOKA" or key=="BAG3" or key=="TXCH1" or key=="ZBQ1" or key=="JBLB" or key=="MCLB" or key=="S2CH"
endfunction

function MJ_ClaimReward takes player p,string key returns boolean
    local integer who=MJ_Index(p)
    if MJ_FreePhase<1 or not MJ_ContentAvailable(p,key) then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadBoolean(MJ_FreeState,who,StringHash("kit:"+key)) then
        return false
    endif
    call SaveBoolean(MJ_FreeState,who,StringHash("kit:"+key),true)
    return true
endfunction

function MJ_BeginFreeHelper takes player p,string key returns boolean
    local integer who=MJ_Index(p)
    if MJ_FreePhase<1 or not MJ_ContentAvailable(p,key) then
        return false
    endif
    if key!="PET1" and key!="PET2" and key!="TRE" then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadBoolean(MJ_FreeState,who,StringHash("helper:"+key)) then
        return false
    endif
    call SaveBoolean(MJ_FreeState,who,StringHash("helper:"+key),true)
    return true
endfunction

function MJ_ClaimFullSet takes player p,unit hero returns boolean
    if MJ_FreePhase<1 or not MJ_FreeFullSet or hero==null or MJ_Index(p)<0 or not IsPlayerInForce(p,Fa) then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadBoolean(MJ_FreeState,GetHandleId(hero),StringHash("fullset:hero")) then
        return false
    endif
    call SaveBoolean(MJ_FreeState,GetHandleId(hero),StringHash("fullset:hero"),true)
    return true
endfunction

function MJ_IsFreePlaying takes player p returns boolean
    return MJ_FreePhase==2 and MJ_Index(p)>=0 and IsPlayerInForce(p,Fa)
endfunction

function MJ_ClaimPassReward takes player p,integer tier returns boolean
    local integer required=0
    local integer who=MJ_Index(p)
    if not MJ_IsFreePlaying(p) or not MJ_ContentAvailable(p,"TXZ") or tier<0 or tier>6 then
        return false
    endif
    if tier==1 then
        set required=50
    elseif tier==2 then
        set required=150
    elseif tier==3 then
        set required=300
    elseif tier==4 then
        set required=500
    elseif tier==5 then
        set required=800
    elseif tier==6 then
        set required=1200
    endif
    if MJ_GetInt(p,"TGDS")<required then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadBoolean(MJ_FreeState,who,StringHash("pass:"+I2S(tier))) then
        return false
    endif
    call SaveBoolean(MJ_FreeState,who,StringHash("pass:"+I2S(tier)),true)
    return true
endfunction

function MJ_ClaimFreeMilestone takes player p,string key,integer milestone returns boolean
    local integer who=MJ_Index(p)
    if not MJ_IsFreePlaying(p) or milestone<=0 or not MJ_ContentAvailable(p,key) then
        return false
    endif
    if key!="ZBQ1" and key!="TXCH1" then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadInteger(MJ_FreeState,who,StringHash("milestone:"+key))>=milestone then
        return false
    endif
    call SaveInteger(MJ_FreeState,who,StringHash("milestone:"+key),milestone)
    return true
endfunction

function MJ_BeginHeroOpening takes player p returns boolean
    local integer who=MJ_Index(p)
    if MJ_FreePhase<1 or who<0 or not IsPlayerInForce(p,Fa) then
        return false
    endif
    if MJ_HeroOpeningApplied[who] then
        return false
    endif
    set MJ_HeroOpeningApplied[who]=true
    return true
endfunction

function MJ_BeginHeroBenefits takes player p,unit hero returns boolean
    if MJ_FreePhase<1 or MJ_Index(p)<0 or hero==null or not IsPlayerInForce(p,Fa) then
        return false
    endif
    call MJ_InitFreeRules()
    if LoadBoolean(MJ_FreeState,GetHandleId(hero),StringHash("start:hero")) then
        return false
    endif
    call SaveBoolean(MJ_FreeState,GetHandleId(hero),StringHash("start:hero"),true)
    return true
endfunction
