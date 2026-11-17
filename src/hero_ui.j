globals
boolean MJ_AllHeroMode=false
boolean MJ_StartDispatched=false
button MJ_SelectModeButton=null
integer MJ_UIRoot=0
integer MJ_UIDetail=0
integer MJ_UIDetailPage=0
integer MJ_LocalDetailPage=0
integer MJ_UIStatus=0
integer MJ_LocalPreview=-1
integer array MJ_UIIcons
hashtable MJ_UIFrames=InitHashtable()
endglobals

// Signatures sourced from JapiNative; actual KK runtime compatibility is pending.
native DzTriggerRegisterSyncData takes trigger trig,string prefix,boolean server returns nothing
native DzSyncData takes string prefix,string data returns nothing
native DzGetTriggerSyncData takes nothing returns string
native DzGetTriggerSyncPlayer takes nothing returns player
native DzCreateFrameByTagName takes string frameType,string name,integer parent,string template,integer id returns integer
native DzFrameSetScriptByCode takes integer frame,integer eventId,code funcHandle,boolean sync returns nothing
native DzGetTriggerUIEventPlayer takes nothing returns player
native DzGetTriggerUIEventFrame takes nothing returns integer

function MJ_HeroCatalogIndex takes integer hero returns integer
    local integer i=0
    loop
        exitwhen i>=MJ_HeroCount
        if MJ_HeroIds[i]==hero then
            return i
        endif
        set i=i+1
    endloop
    return -1
endfunction

function MJ_SelectionHost takes nothing returns player
    local integer i=0
    loop
        exitwhen i>=5
        if MJ_IsActive(i) and IsPlayerInForce(MJ_Player(i),Fa) then
            return MJ_Player(i)
        endif
        set i=i+1
    endloop
    return Player(0)
endfunction

function MJ_RefreshSelectionUI takes nothing returns nothing
    local integer i=0
    local integer j=0
    local integer heroIndex=0
    local boolean occupied=false
    local string status="准备状态|n"
    loop
        exitwhen i>=5
        if MJ_Present[i] then
            set heroIndex=MJ_HeroCatalogIndex(MJ_Chosen[i])
            if MJ_Ready[i] and heroIndex>=0 then
                set status=status+GetPlayerName(MJ_Player(i))+": |cff55ff88已准备|r "+MJ_HeroNames[heroIndex]+"|n"
            else
                set status=status+GetPlayerName(MJ_Player(i))+": 选择中|n"
            endif
        endif
        set i=i+1
    endloop
    call DzFrameSetText(MJ_UIStatus,status)
    set i=0
    loop
        exitwhen i>=MJ_HeroCount
        set occupied=false
        set j=0
        loop
            exitwhen j>=5
            if MJ_Present[j] and MJ_Ready[j] and MJ_Chosen[j]==MJ_HeroIds[i] then
                set occupied=true
            endif
            set j=j+1
        endloop
        if occupied then
            call DzFrameSetVertexColor(MJ_UIIcons[i],DzGetColor(90,90,90,255))
        else
            call DzFrameSetVertexColor(MJ_UIIcons[i],DzGetColor(255,255,255,255))
        endif
        set i=i+1
    endloop
endfunction

function MJ_StartGame takes nothing returns nothing
    if MJ_SelectState!=2 or MJ_StartDispatched then
        return
    endif
    set MJ_StartDispatched=true
    call DzFrameShow(MJ_UIRoot,false)
    // Preserve the original staged initialization, including ux hero setup.
    call TriggerExecute(GL)
endfunction

function MJ_ApplySelection takes player sender,string payload returns nothing
    local integer i=MJ_Index(sender)
    local integer hero=0
    local boolean accepted=false
    local string number=""
    if not MJ_AllHeroMode or MJ_SelectState!=1 or i<0 then
        return
    endif
    if payload=="C" then
        set accepted=MJ_CancelReady(i)
    elseif SubString(payload,0,2)=="R:" and StringLength(payload)<=13 then
        set number=SubString(payload,2,StringLength(payload))
        set hero=S2I(number)
        if I2S(hero)==number then
            set accepted=MJ_ConfirmHero(i,hero)
        endif
    endif
    if not accepted then
        call DisplayTimedTextToPlayer(sender,0,0,4.,"该英雄已被选择，或当前无法确认。请重新选择。")
    endif
    call MJ_RefreshSelectionUI()
    call MJ_StartGame()
endfunction

function MJ_OnSelectionSync takes nothing returns nothing
    call MJ_ApplySelection(DzGetTriggerSyncPlayer(),DzGetTriggerSyncData())
endfunction

function MJ_OnSelectionLeave takes nothing returns nothing
    if MJ_AllHeroMode and MJ_SelectState==1 then
        call MJ_LeaveSelection(MJ_Index(GetTriggerPlayer()))
        call MJ_RefreshSelectionUI()
        call MJ_StartGame()
    endif
endfunction

// Called only by local preview/paging handlers; no synchronized state changes.
function MJ_RenderHeroDetail takes nothing returns nothing
    if MJ_LocalPreview<0 or MJ_LocalPreview>=MJ_HeroCount then
        return
    endif
    call DzFrameSetText(MJ_UIDetail,"|cff55ccff"+MJ_HeroNames[MJ_LocalPreview]+"|r|n"+MJ_HeroDetailPages[MJ_HeroDetailStart[MJ_LocalPreview]+MJ_LocalDetailPage])
    call DzFrameSetText(MJ_UIDetailPage,I2S(MJ_LocalDetailPage+1)+" / "+I2S(MJ_HeroDetailCount[MJ_LocalPreview]))
endfunction

function MJ_OnDetailPrevious takes nothing returns nothing
    if GetLocalPlayer()==DzGetTriggerUIEventPlayer() and MJ_LocalPreview>=0 and MJ_LocalPreview<MJ_HeroCount then
        if MJ_LocalDetailPage>0 then
            set MJ_LocalDetailPage=MJ_LocalDetailPage-1
        endif
        call MJ_RenderHeroDetail()
    endif
endfunction

function MJ_OnDetailNext takes nothing returns nothing
    if GetLocalPlayer()==DzGetTriggerUIEventPlayer() and MJ_LocalPreview>=0 and MJ_LocalPreview<MJ_HeroCount then
        if MJ_LocalDetailPage+1<MJ_HeroDetailCount[MJ_LocalPreview] then
            set MJ_LocalDetailPage=MJ_LocalDetailPage+1
        endif
        call MJ_RenderHeroDetail()
    endif
endfunction

function MJ_OnHeroPreview takes nothing returns nothing
    local integer index=LoadInteger(MJ_UIFrames,DzGetTriggerUIEventFrame(),0)-1
    if GetLocalPlayer()==DzGetTriggerUIEventPlayer() and index>=0 and index<MJ_HeroCount then
        set MJ_LocalPreview=index
        set MJ_LocalDetailPage=0
        call MJ_RenderHeroDetail()
    endif
endfunction

function MJ_OnReadyClick takes nothing returns nothing
    if GetLocalPlayer()==DzGetTriggerUIEventPlayer() and MJ_Index(GetLocalPlayer())>=0 and MJ_LocalPreview>=0 then
        call DzSyncData("MJ5SELECT","R:"+I2S(MJ_HeroIds[MJ_LocalPreview]))
    endif
endfunction

function MJ_OnCancelClick takes nothing returns nothing
    if GetLocalPlayer()==DzGetTriggerUIEventPlayer() and MJ_Index(GetLocalPlayer())>=0 then
        call DzSyncData("MJ5SELECT","C")
    endif
endfunction

function MJ_CreateSelectionUI takes nothing returns nothing
    local integer i=0
    local integer frame=0
    local integer parent=DzGetGameUI()
    local integer row=0
    local integer col=0
    call DzLoadToc("MJ5\\hero.toc")
    set MJ_UIRoot=DzCreateFrameByTagName("BACKDROP","MJ5Panel",parent,"",0)
    call DzFrameSetSize(MJ_UIRoot,0.77,0.55)
    call DzFrameSetPoint(MJ_UIRoot,0,parent,0,0.015,-0.02)
    call DzFrameSetTexture(MJ_UIRoot,"UI\\Widgets\\EscMenu\\Human\\human-options-menu-background.blp",0)
    set frame=DzCreateFrameByTagName("TEXT","MJ5Title",MJ_UIRoot,"MJ5Text",0)
    call DzFrameSetSize(frame,0.72,0.025)
    call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.02,-0.015)
    call DzFrameSetText(frame,"全英雄自选 · 无时间限制 · 所有人准备后开始 · 灰色头像表示已被选择")
    loop
        exitwhen i>=MJ_HeroCount
        set row=i/20
        set col=i-row*20
        set frame=DzCreateFrameByTagName("GLUETEXTBUTTON","MJ5Hero"+I2S(i),MJ_UIRoot,"ScriptDialogButton",0)
        call DzFrameSetSize(frame,0.032,0.032)
        call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.035+I2R(col)*0.035,-0.055-I2R(row)*0.035)
        call SaveInteger(MJ_UIFrames,frame,0,i+1)
        call DzFrameSetScriptByCode(frame,1,function MJ_OnHeroPreview,false)
        set MJ_UIIcons[i]=DzCreateFrameByTagName("BACKDROP","MJ5Icon"+I2S(i),frame,"",0)
        call DzFrameSetSize(MJ_UIIcons[i],0.029,0.029)
        call DzFrameSetPoint(MJ_UIIcons[i],4,frame,4,0.,0.)
        call DzFrameSetTexture(MJ_UIIcons[i],MJ_HeroIcons[i],0)
        set i=i+1
    endloop
    set MJ_UIDetail=DzCreateFrameByTagName("TEXT","MJ5Detail",MJ_UIRoot,"MJ5Text",0)
    call DzFrameSetSize(MJ_UIDetail,0.45,0.105)
    call DzFrameSetPoint(MJ_UIDetail,0,MJ_UIRoot,0,0.025,-0.35)
    call DzFrameSetText(MJ_UIDetail,"点击任一英雄查看说明，再按“确定英雄 / 准备”。")
    set frame=DzCreateFrameByTagName("GLUETEXTBUTTON","MJ5DetailPrevious",MJ_UIRoot,"ScriptDialogButton",0)
    call DzFrameSetSize(frame,0.09,0.026)
    call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.025,-0.465)
    call DzFrameSetText(frame,"上页")
    call DzFrameSetScriptByCode(frame,1,function MJ_OnDetailPrevious,false)
    set MJ_UIDetailPage=DzCreateFrameByTagName("TEXT","MJ5DetailPage",MJ_UIRoot,"MJ5Text",0)
    call DzFrameSetSize(MJ_UIDetailPage,0.12,0.025)
    call DzFrameSetPoint(MJ_UIDetailPage,0,MJ_UIRoot,0,0.135,-0.47)
    call DzFrameSetText(MJ_UIDetailPage,"0 / 0")
    set frame=DzCreateFrameByTagName("GLUETEXTBUTTON","MJ5DetailNext",MJ_UIRoot,"ScriptDialogButton",0)
    call DzFrameSetSize(frame,0.09,0.026)
    call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.265,-0.465)
    call DzFrameSetText(frame,"下页")
    call DzFrameSetScriptByCode(frame,1,function MJ_OnDetailNext,false)
    set MJ_UIStatus=DzCreateFrameByTagName("TEXT","MJ5Status",MJ_UIRoot,"MJ5Text",0)
    call DzFrameSetSize(MJ_UIStatus,0.265,0.14)
    call DzFrameSetPoint(MJ_UIStatus,0,MJ_UIRoot,0,0.49,-0.35)
    set frame=DzCreateFrameByTagName("GLUETEXTBUTTON","MJ5Ready",MJ_UIRoot,"ScriptDialogButton",0)
    call DzFrameSetSize(frame,0.19,0.035)
    call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.17,-0.50)
    call DzFrameSetText(frame,"确定英雄 / 准备")
    call DzFrameSetScriptByCode(frame,1,function MJ_OnReadyClick,false)
    set frame=DzCreateFrameByTagName("GLUETEXTBUTTON","MJ5Cancel",MJ_UIRoot,"ScriptDialogButton",0)
    call DzFrameSetSize(frame,0.19,0.035)
    call DzFrameSetPoint(frame,0,MJ_UIRoot,0,0.42,-0.50)
    call DzFrameSetText(frame,"取消准备")
    call DzFrameSetScriptByCode(frame,1,function MJ_OnCancelClick,false)
endfunction

function MJ_SelectStart takes nothing returns nothing
    local integer i=0
    local trigger sync=CreateTrigger()
    local trigger leave=CreateTrigger()
    if MJ_AllHeroMode then
        call DestroyTrigger(sync)
        call DestroyTrigger(leave)
        return
    endif
    set MJ_AllHeroMode=true
    set MJ_StartDispatched=false
    call MJ_ResetSelection()
    call MJ_InitHeroIds()
    call MJ_InitHeroMetadata()
    loop
        exitwhen i>=5
        if MJ_IsActive(i) then
            call MJ_JoinSelection(i)
        endif
        call TriggerRegisterPlayerEvent(leave,MJ_Player(i),EVENT_PLAYER_LEAVE)
        set i=i+1
    endloop
    call TriggerAddAction(leave,function MJ_OnSelectionLeave)
    call DzTriggerRegisterSyncData(sync,"MJ5SELECT",false)
    call TriggerAddAction(sync,function MJ_OnSelectionSync)
    call MJ_BeginSelection()
    call MJ_CreateSelectionUI()
    call MJ_RefreshSelectionUI()
    set sync=null
    set leave=null
endfunction
