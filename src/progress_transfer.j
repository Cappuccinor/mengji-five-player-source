// Chat events are synchronized. Only their native sender owns this transfer slot.
globals
boolean MJ_ProgressDifficultyGrace=false
hashtable MJ_ProgressTransfers=null
boolean array MJ_ProgressImportPending
boolean MJ_ProgressStartDeferred=false
endglobals

function MJ_InitProgressTransfers takes nothing returns nothing
    call MJ_InitProgress()
    if MJ_ProgressTransfers==null then
        set MJ_ProgressTransfers=InitHashtable()
    endif
endfunction

function MJ_IsProgressImportPending takes player p returns boolean
    local integer who=MJ_Index(p)
    if who<0 then
        return false
    endif
    return MJ_ProgressImportPending[who]
endfunction

function MJ_AnyProgressImportPending takes nothing returns boolean
    local integer i=0
    loop
        exitwhen i>=5
        if MJ_ProgressImportPending[i] then
            return true
        endif
        set i=i+1
    endloop
    return false
endfunction

function MJ_CancelProgressTransfer takes player p returns nothing
    local integer who=MJ_Index(p)
    call MJ_InitProgressTransfers()
    if who<0 then
        return
    endif
    set MJ_ProgressImportPending[who]=false
    call FlushChildHashtable(MJ_ProgressTransfers,who)
endfunction

function MJ_ReceiveProgressChunk takes player p,integer index,integer total,string text returns boolean
    local integer who=MJ_Index(p)
    local integer i=0
    local string previous=""
    call MJ_InitProgressTransfers()
    if MJ_ProgressLocked or who<0 or total<1 or total>43 or index<0 or index>=total then
        return false
    endif
    if text==null or StringLength(text)<1 or StringLength(text)>96 then
        return false
    endif
    if index<total-1 and StringLength(text)!=96 then
        return false
    endif
    loop
        exitwhen i>=StringLength(text)
        if MJ_ProgressCharacter(SubString(text,i,i+1))<0 then
            return false
        endif
        set i=i+1
    endloop
    if MJ_ProgressImportPending[who] then
        if LoadInteger(MJ_ProgressTransfers,who,-1)!=total then
            return false
        endif
    else
        call FlushChildHashtable(MJ_ProgressTransfers,who)
        call SaveInteger(MJ_ProgressTransfers,who,-1,total)
        set MJ_ProgressImportPending[who]=true
    endif
    set previous=LoadStr(MJ_ProgressTransfers,who,index)
    if previous!=null and StringLength(previous)>0 then
        return previous==text
    endif
    call SaveStr(MJ_ProgressTransfers,who,index,text)
    call SaveInteger(MJ_ProgressTransfers,who,-2,LoadInteger(MJ_ProgressTransfers,who,-2)+1)
    return true
endfunction

function MJ_ApplyProgressTransfer takes player p returns boolean
    local integer who=MJ_Index(p)
    local integer i=0
    local integer total=0
    local string text=""
    call MJ_InitProgressTransfers()
    if MJ_ProgressLocked or who<0 then
        return false
    endif
    if not MJ_ProgressImportPending[who] then
        return false
    endif
    set total=LoadInteger(MJ_ProgressTransfers,who,-1)
    if LoadInteger(MJ_ProgressTransfers,who,-2)!=total then
        return false
    endif
    loop
        exitwhen i>=total
        set text=text+LoadStr(MJ_ProgressTransfers,who,i)
        set i=i+1
    endloop
    if MJ_ImportProgress(p,text) then
        call MJ_CancelProgressTransfer(p)
        return true
    endif
    return false
endfunction

function MJ_LoadProgress takes player p returns nothing
    // A fresh player gets defaults. Only an explicit synchronized import restores a prior game.
    call MJ_InitProgress()
endfunction

function MJ_SaveProgress takes player p returns nothing
    local integer who=MJ_Index(p)
    call MJ_InitProgressTransfers()
    if who>=0 then
        call SaveStr(MJ_ProgressTransfers,who,-10,MJ_ExportProgress(p))
    endif
endfunction
