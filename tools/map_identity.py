"""One visible identity for the map list, room metadata and running script."""
import struct

TITLE='梦迹沙河2·五路同心 [测试06]'


def rename_info(raw, title=TITLE):
    if struct.unpack_from('<I',raw)[0]!=25:
        raise ValueError('unsupported map info version')
    end=raw.index(b'\0',12)
    return raw[:12]+title.encode('utf8')+raw[end:]


def rename_script(raw, title=TITLE):
    old=b'call SetMapName("'+ '|cffffffcc梦迹沙河|r2'.encode('utf8')+b'")'
    if raw.count(old)!=1:
        raise ValueError('map title anchor drift')
    raw=raw.replace(old,b'call SetMapName("'+title.encode('utf8')+b'")',1)
    # These scoreboard labels prefix the remaining-time value, not a result.
    raw=raw.replace(' - 游戏胜利 - '.encode(), ' - 距通关 - '.encode())
    return raw.replace(' - 胜利 - '.encode(), ' - 距通关 - '.encode())


def rename_header(raw, title=TITLE):
    if raw[:4]!=b'HM3W' or raw[512:516]!=b'MPQ\x1a':
        raise ValueError('unsupported map wrapper')
    end=raw.index(b'\0',8,512)
    if any(raw[end+9:512]):
        raise ValueError('unknown non-padding header content')
    header=raw[:8]+title.encode('utf8')+b'\0'+raw[end+1:end+9]
    if len(header)>512:
        raise ValueError('map title exceeds wrapper')
    return header.ljust(512,b'\0')+raw[512:]
