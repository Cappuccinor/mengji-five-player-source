globals
boolean MJ_ProgressChatInitialized=false
endglobals

function MJ_ShowProgressExport takes player p,integer page,boolean fresh returns nothing
    local integer who=MJ_Index(p)
    local integer total=0
    local integer index=0
    local integer stop=0
    local string text=""
    call MJ_InitProgressTransfers()
    if who<0 then
        return
    endif
    if MJ_IsProgressImportPending(p) then
        call DisplayTimedTextToPlayer(p,0,0,8.,"请先用 -mjapply 完成导入，或用 -mjcancel 取消导入。")
        return
    endif
    set text=LoadStr(MJ_ProgressTransfers,who,-10)
    if fresh or text==null or StringLength(text)==0 then
        call MJ_SaveProgress(p)
        set text=LoadStr(MJ_ProgressTransfers,who,-10)
    endif
    set total=R2I((I2R(StringLength(text))+95.)/96.)
    set index=(page-1)*8
    if page<1 or index>=total then
        call DisplayTimedTextToPlayer(p,0,0,8.,"导出页码无效。输入 -mjsave 重新生成第一页。")
        return
    endif
    set stop=index+8
    call DisplayTimedTextToPlayer(p,0,0,40.,"梦迹五人版独立进度码，第 "+I2S(page)+" 页。下局开局前依次发送下列命令，最后发送 -mjapply。")
    loop
        exitwhen index>=total or index>=stop
        call DisplayTimedTextToPlayer(p,0,0,60.,"-mjload "+I2S(index+1)+"/"+I2S(total)+" "+SubString(text,index*96,(index+1)*96))
        set index=index+1
    endloop
    if index<total then
        call DisplayTimedTextToPlayer(p,0,0,40.,"还有后续内容，输入 -mjsave "+I2S(page+1)+" 显示下一页；不要漏段。")
    else
        call DisplayTimedTextToPlayer(p,0,0,40.,"已显示到最后一段。请在退出地图前保存所有段落。此码独立于原平台账号。")
    endif
endfunction

function MJ_BuildDifficultyMenu takes nothing returns nothing
call DialogClear(Fq)
call DialogSetMessage(Fq,"选择难度")
call DialogAddButtonBJ(Fq,"|Cff00FF00难度1|r")
set GI[1]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|CffFFFF00难度2|r")
set GI[2]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|CffFF8000难度3|r")
set GI[3]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|CffFF0000难度4|r")
set GI[4]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|CffB399FF难度5|r")
set GI[5]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|cffff99cc难度6|r")
set GI[6]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|cffc0c0c0难度7|r")
set GI[7]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|cfffdfdfd难度0|r")
set GI[8]=GetLastCreatedButtonBJ()
call DialogAddButtonBJ(Fq,"|Cff00FFFF大闯关|r")
set GI[10]=GetLastCreatedButtonBJ()
if CountPlayersInForceBJ(Fa)>1 then
call DialogAddButtonBJ(Fq,"|CffFFA64D吃鸡模式|r")
set GI[96]=GetLastCreatedButtonBJ()
else
endif
endfunction

function MJ_RefreshProgressDifficulty takes player p returns nothing
    if p!=MJ_SelectionHost() or not IsTriggerEnabled(GM) or LoadInteger(DI,StringHash("全局"),$F1B419D0)!=0 then
        return
    endif
call MJ_BuildDifficultyMenu()
call EnableTrigger(GM)
call DialogDisplayBJ(true,Fq,MJ_SelectionHost())
set MJ_ProgressDifficultyGrace=true
endfunction

function MJ_OnProgressChat takes nothing returns nothing
    local player p=GetTriggerPlayer()
    local integer who=MJ_Index(p)
    local string text=GetEventPlayerChatString()
    local integer slash=0
    local integer gap=0
    local integer index=0
    local integer total=0
    local integer page=0
    local boolean accepted=false
    if who<0 then
        return
    endif
    if text=="-mjsave" then
        call MJ_ShowProgressExport(p,1,true)
    elseif SubString(text,0,8)=="-mjsave " then
        call MJ_InitProgress()
        set page=MJ_ParseProgressNatural(SubString(text,8,StringLength(text)))
        if page>0 and page<=6 then
            call MJ_ShowProgressExport(p,page,false)
        endif
    elseif text=="-mjcancel" then
        call MJ_CancelProgressTransfer(p)
        call DisplayTimedTextToPlayer(p,0,0,8.,"已取消导入，现有进度未改变。")
    elseif text=="-mjapply" then
        if MJ_ApplyProgressTransfer(p) then
            call MJ_RefreshProgressDifficulty(p)
            call DisplayTimedTextToPlayer(p,0,0,10.,"独立进度已导入。现在可以选择英雄并准备。")
        else
            call DisplayTimedTextToPlayer(p,0,0,10.,"导入未完成：请检查缺失段、版本和校验；也可能已经开局。现有进度未改变。输入 -mjcancel 可取消。")
        endif
    elseif SubString(text,0,8)=="-mjload " then
        call MJ_InitProgressTransfers()
        set slash=8
        loop
            exitwhen slash>=StringLength(text) or SubString(text,slash,slash+1)=="/"
            set slash=slash+1
        endloop
        set gap=slash+1
        loop
            exitwhen gap>=StringLength(text) or SubString(text,gap,gap+1)==" "
            set gap=gap+1
        endloop
        if slash<StringLength(text) and gap<StringLength(text) then
            set index=MJ_ParseProgressNatural(SubString(text,8,slash))
            set total=MJ_ParseProgressNatural(SubString(text,slash+1,gap))
            set accepted=MJ_ReceiveProgressChunk(p,index-1,total,SubString(text,gap+1,StringLength(text)))
        endif
        if accepted then
            if MJ_AllHeroMode and MJ_SelectState==1 then
                call MJ_CancelReady(who)
                call MJ_RefreshSelectionUI()
            endif
            call DisplayTimedTextToPlayer(p,0,0,8.,"已接收第 "+I2S(index)+"/"+I2S(total)+" 段。收齐后输入 -mjapply；取消用 -mjcancel。")
        else
            call DisplayTimedTextToPlayer(p,0,0,8.,"进度段未接收：格式、顺序编号或内容冲突，或已经开局。需要重来时先输入 -mjcancel。")
        endif
    else
        call DisplayTimedTextToPlayer(p,0,0,12.,"进度命令：-mjsave 导出；-mjsave 页码 翻页；-mjload 序号/总段数 内容 接收；-mjapply 导入；-mjcancel 取消。只在开局前可导入。")
    endif
    set p=null
endfunction

function MJ_ProgressRetryStart takes nothing returns nothing
    if MJ_AnyProgressImportPending() then
        call TimerStart(GetExpiredTimer(),1.,false,function MJ_ProgressRetryStart)
        return
    endif
    set MJ_ProgressStartDeferred=false
    call DestroyTimer(GetExpiredTimer())
    call TriggerExecute(GN)
endfunction

function MJ_InitProgressChat takes nothing returns nothing
    local integer i=0
    local trigger chat=null
    if MJ_ProgressChatInitialized then
        return
    endif
    set MJ_ProgressChatInitialized=true
    call MJ_InitProgressTransfers()
    set chat=CreateTrigger()
    loop
        exitwhen i>=5
        call TriggerRegisterPlayerChatEvent(chat,MJ_Player(i),"-mj",false)
        set i=i+1
    endloop
    call TriggerAddAction(chat,function MJ_OnProgressChat)
    set chat=null
endfunction
