// Standalone benefits: clear counts are real MJ5_LOCAL_V1 progress, never platform levels.
globals
// 1 cooperative bonus, 2 star gift; these former guild groups are exclusive.
integer MJ_LocalGuildPreset=1
// 0 none, 1 old return bonus, 2 recent return bonus; never stack both.
integer MJ_LocalReturnPreset=2
boolean MJ_LocalWelcomeBenefits=true
boolean MJ_LocalGiftBenefits=true
boolean MJ_LocalCosmetics=true
boolean MJ_LocalLadderBenefit=true
endglobals

function MJ_LocalBenefitClears takes player p returns integer
    local integer clears=0
    if MJ_Index(p)<0 then
        return 0
    endif
    set clears=MJ_GetInt(p,"GGC")
    if clears>100 then
        return 100
    endif
    if clears<0 then
        return 0
    endif
    return clears
endfunction

function MJ_LocalAccountBenefit takes player p,string key returns boolean
    if MJ_FreePhase<1 or MJ_Index(p)<0 or not IsPlayerInForce(p,Fa) then
        return false
    endif
    if key=="COOPERATIVE" then
        return MJ_LocalGuildPreset==1
    elseif key=="STAR_GUILD" then
        return MJ_LocalGuildPreset==2
    elseif key=="RETURN_RECENT" then
        return MJ_LocalWelcomeBenefits and MJ_LocalReturnPreset==2
    elseif key=="RETURN_OLD" then
        return MJ_LocalWelcomeBenefits and MJ_LocalReturnPreset==1
    elseif key=="BLUE_BONUS" or key=="APPRECIATOR" or key=="COLLECTOR" then
        return MJ_LocalWelcomeBenefits
    elseif key=="RATING_GIFT" or key=="REMASTER_GIFT" or key=="VOTE_GIFT" then
        return MJ_LocalGiftBenefits
    elseif key=="RANK_COSMETIC" or key=="STAR_COSMETIC" or key=="NAMED_COSMETIC" or key=="DONATION_COSMETIC" then
        return MJ_LocalCosmetics
    elseif key=="LADDER_REWARD" then
        return MJ_LocalLadderBenefit
    endif
    return false
endfunction

function MJ_LocalNotice takes nothing returns string
    return "本版免费内容与独立进度只在本地图内生效；本版通关次数与原平台账号无关。"
endfunction
