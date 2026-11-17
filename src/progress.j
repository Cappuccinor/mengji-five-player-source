// MJ5_LOCAL_V1 is a standalone record. No account or original platform native is used.
globals
boolean MJ_ProgressInitialized=false
boolean MJ_ProgressLocked=false
hashtable MJ_Progress=null
hashtable MJ_ProgressStage=null
hashtable MJ_ProgressCharacters=null
endglobals

function MJ_InitProgress takes nothing returns nothing
    local integer i=0
    local string c=""
    if MJ_ProgressInitialized then
        return
    endif
    set MJ_ProgressInitialized=true
    set MJ_Progress=InitHashtable()
    set MJ_ProgressStage=InitHashtable()
    set MJ_ProgressCharacters=InitHashtable()
    call MJ_InitProgressSchema()
    loop
        exitwhen i>=StringLength(MJ_ProgressAlphabet)
        set c=SubString(MJ_ProgressAlphabet,i,i+1)
        if i>=10 and i<36 then
            call SaveInteger(MJ_ProgressCharacters,0,StringHash(c),i+1)
            call SaveStr(MJ_ProgressCharacters,0,StringHash(c),c)
        endif
        set i=i+1
    endloop
endfunction

function MJ_ProgressCharacter takes string c returns integer
    local integer digit=0
    local integer i=62
    local string lower=""
    if c==null or StringLength(c)!=1 then
        return -1
    endif
    set digit=S2I(c)
    if digit>=0 and digit<=9 and I2S(digit)==c then
        return digit
    endif
    set lower=StringCase(c,false)
    if LoadStr(MJ_ProgressCharacters,0,StringHash(lower))==lower then
        set digit=LoadInteger(MJ_ProgressCharacters,0,StringHash(lower))-1
        if c==lower then
            return digit
        elseif c==StringCase(lower,true) then
            return digit+26
        endif
    endif
    // Hashing merges case and slash variants. Punctuation uses exact comparisons.
    loop
        exitwhen i>=StringLength(MJ_ProgressAlphabet)
        if SubString(MJ_ProgressAlphabet,i,i+1)==c then
            return i
        endif
        set i=i+1
    endloop
    return -1
endfunction

function MJ_FindProgressKey takes string key returns integer
    local integer i=0
    loop
        exitwhen i>=MJ_ProgressKeyCount
        if MJ_ProgressKeys[i]==key then
            return i
        endif
        set i=i+1
    endloop
    return -1
endfunction

function MJ_ValidProgressString takes string value returns boolean
    local integer i=0
    if value==null then
        return false
    endif
    if StringLength(value)!=0 and StringLength(value)!=63 then
        return false
    endif
    loop
        exitwhen i>=StringLength(value)
        if MJ_ProgressCharacter(SubString(value,i,i+1))<0 then
            return false
        endif
        set i=i+1
    endloop
    return true
endfunction

function MJ_GetInt takes player p,string key returns integer
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("I"+key)
    if who<0 or id<0 then
        return 0
    endif
    return LoadInteger(MJ_Progress,who,id)
endfunction

function MJ_SetInt takes player p,string key,integer value returns nothing
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("I"+key)
    if who<0 or id<0 then
        return
    endif
    if value<0 then
        set value=0
    elseif value>MJ_ProgressMax[id] then
        set value=MJ_ProgressMax[id]
    endif
    call SaveInteger(MJ_Progress,who,id,value)
endfunction

function MJ_GetBool takes player p,string key returns boolean
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("B"+key)
    if who<0 or id<0 then
        return false
    endif
    return LoadBoolean(MJ_Progress,who,id)
endfunction

function MJ_SetBool takes player p,string key,boolean value returns nothing
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("B"+key)
    if who<0 or id<0 then
        return
    endif
    call SaveBoolean(MJ_Progress,who,id,value)
endfunction

function MJ_GetString takes player p,string key returns string
    local integer who=MJ_Index(p)
    local integer id=0
    local string value=""
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("S"+key)
    if who<0 or id<0 then
        return ""
    endif
    set value=LoadStr(MJ_Progress,who,id)
    if value==null then
        return ""
    endif
    return value
endfunction

function MJ_SetString takes player p,string key,string value returns nothing
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey("S"+key)
    if who<0 or id<0 or not MJ_ValidProgressString(value) then
        return
    endif
    call SaveStr(MJ_Progress,who,id,value)
endfunction

function MJ_DeleteProgressKey takes player p,string key returns nothing
    local integer who=MJ_Index(p)
    local integer id=0
    call MJ_InitProgress()
    set id=MJ_FindProgressKey(key)
    if who<0 or id<0 then
        return
    endif
    call RemoveSavedInteger(MJ_Progress,who,id)
    call RemoveSavedBoolean(MJ_Progress,who,id)
    call RemoveSavedString(MJ_Progress,who,id)
endfunction

function MJ_LockProgress takes nothing returns nothing
    call MJ_InitProgress()
    set MJ_ProgressLocked=true
endfunction

function MJ_ParseProgressNatural takes string text returns integer
    local integer i=0
    local integer digit=0
    local integer value=0
    if text==null or StringLength(text)==0 or StringLength(text)>10 then
        return -1
    endif
    if StringLength(text)>1 and SubString(text,0,1)=="0" then
        return -1
    endif
    loop
        exitwhen i>=StringLength(text)
        set digit=MJ_ProgressCharacter(SubString(text,i,i+1))
        if digit<0 or digit>9 then
            return -1
        endif
        if value>214748364 or (value==214748364 and digit>7) then
            return -1
        endif
        set value=value*10+digit
        set i=i+1
    endloop
    return value
endfunction

function MJ_ProgressChecksum takes string text returns integer
    local integer i=0
    local integer value=1
    local integer digit=0
    loop
        exitwhen i>=StringLength(text)
        set digit=MJ_ProgressCharacter(SubString(text,i,i+1))
        if digit<0 then
            return -1
        endif
        set value=ModuloInteger(value*31+digit+1,65521)
        set i=i+1
    endloop
    return value
endfunction

function MJ_HexDigit takes string c returns integer
    local integer i=0
    loop
        exitwhen i>=16
        if SubString("0123456789ABCDEF",i,i+1)==c then
            return i
        endif
        set i=i+1
    endloop
    return -1
endfunction

function MJ_EncodeProgressString takes string value returns string
    local integer i=0
    local integer digit=0
    local integer high=0
    local string out=""
    loop
        exitwhen i>=StringLength(value)
        set digit=MJ_ProgressCharacter(SubString(value,i,i+1))
        if digit<0 then
            return ""
        endif
        set high=R2I(I2R(digit)/16.)
        set out=out+SubString("0123456789ABCDEF",high,high+1)+SubString("0123456789ABCDEF",ModuloInteger(digit,16),ModuloInteger(digit,16)+1)
        set i=i+1
    endloop
    return out
endfunction

function MJ_DecodeProgressString takes string text returns string
    local integer i=0
    local integer high=0
    local integer low=0
    local integer digit=0
    local string out=""
    if ModuloInteger(StringLength(text),2)!=0 or StringLength(text)>126 then
        return null
    endif
    loop
        exitwhen i>=StringLength(text)
        set high=MJ_HexDigit(SubString(text,i,i+1))
        set low=MJ_HexDigit(SubString(text,i+1,i+2))
        set digit=high*16+low
        if high<0 or low<0 or digit>=StringLength(MJ_ProgressAlphabet) then
            return null
        endif
        set out=out+SubString(MJ_ProgressAlphabet,digit,digit+1)
        set i=i+2
    endloop
    if not MJ_ValidProgressString(out) then
        return null
    endif
    return out
endfunction

function MJ_ValidateProgressMastery takes integer who returns boolean
    local integer hero=1
    local integer j=0
    local integer position=0
    local integer segment=0
    local integer offset=0
    local integer value=0
    local integer digit=0
    local string piece=""
    loop
        exitwhen hero>158
        set j=0
        set value=0
        loop
            exitwhen j>=3
            set position=hero*3-1+j
            set segment=R2I(I2R(position)/63.)
            set offset=ModuloInteger(position,63)
            set piece=LoadStr(MJ_ProgressStage,who,MJ_MasteryKeys[segment])
            set digit=0
            if piece!=null and StringLength(piece)>0 then
                set digit=MJ_ProgressCharacter(SubString(piece,offset,offset+1))
            endif
            set value=value*StringLength(MJ_ProgressAlphabet)+digit
            if digit<0 or value>500 then
                return false
            endif
            set j=j+1
        endloop
        set hero=hero+1
    endloop
    return true
endfunction

function MJ_ExportProgress takes player p returns string
    local integer who=MJ_Index(p)
    local integer i=0
    local string out=""
    local string value=""
    call MJ_InitProgress()
    if who<0 then
        return ""
    endif
    set out=MJ_ProgressHeader
    loop
        exitwhen i>=MJ_ProgressKeyCount
        if MJ_ProgressKinds[i]==1 then
            set out=out+I2S(LoadInteger(MJ_Progress,who,i))
        elseif MJ_ProgressKinds[i]==2 then
            if LoadBoolean(MJ_Progress,who,i) then
                set out=out+"1"
            else
                set out=out+"0"
            endif
        else
            set value=LoadStr(MJ_Progress,who,i)
            if value!=null then
                set out=out+MJ_EncodeProgressString(value)
            endif
        endif
        set out=out+";"
        set i=i+1
    endloop
    return out+"#"+I2S(MJ_ProgressChecksum(out))
endfunction

function MJ_ImportProgress takes player p,string text returns boolean
    local integer who=MJ_Index(p)
    local integer i=0
    local integer position=0
    local integer start=0
    local integer value=0
    local string token=""
    local string decoded=""
    call MJ_InitProgress()
    if MJ_ProgressLocked or who<0 or text==null or StringLength(text)>4096 then
        return false
    endif
    set position=StringLength(MJ_ProgressHeader)
    if SubString(text,0,position)!=MJ_ProgressHeader then
        return false
    endif
    call FlushChildHashtable(MJ_ProgressStage,who)
    loop
        exitwhen i>=MJ_ProgressKeyCount
        set start=position
        loop
            exitwhen position>=StringLength(text) or SubString(text,position,position+1)==";"
            set position=position+1
        endloop
        if position>=StringLength(text) then
            return false
        endif
        set token=SubString(text,start,position)
        if MJ_ProgressKinds[i]==3 then
            set decoded=MJ_DecodeProgressString(token)
            if decoded==null then
                return false
            endif
            call SaveStr(MJ_ProgressStage,who,i,decoded)
        else
            set value=MJ_ParseProgressNatural(token)
            if value<0 or value>MJ_ProgressMax[i] then
                return false
            endif
            if MJ_ProgressKinds[i]==1 then
                call SaveInteger(MJ_ProgressStage,who,i,value)
            else
                call SaveBoolean(MJ_ProgressStage,who,i,value==1)
            endif
        endif
        set position=position+1
        set i=i+1
    endloop
    if SubString(text,position,position+1)!="#" then
        return false
    endif
    set value=MJ_ParseProgressNatural(SubString(text,position+1,StringLength(text)))
    if value<0 or value!=MJ_ProgressChecksum(SubString(text,0,position)) then
        return false
    endif
    if not MJ_ValidateProgressMastery(who) then
        return false
    endif
    set i=0
    loop
        exitwhen i>=MJ_ProgressKeyCount
        if MJ_ProgressKinds[i]==1 then
            call SaveInteger(MJ_Progress,who,i,LoadInteger(MJ_ProgressStage,who,i))
        elseif MJ_ProgressKinds[i]==2 then
            call SaveBoolean(MJ_Progress,who,i,LoadBoolean(MJ_ProgressStage,who,i))
        else
            call SaveStr(MJ_Progress,who,i,LoadStr(MJ_ProgressStage,who,i))
        endif
        set i=i+1
    endloop
    call FlushChildHashtable(MJ_ProgressStage,who)
    return true
endfunction
