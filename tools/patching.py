"""Apply reviewed function patches only when their original text matches."""
import hashlib
import re


def functions(source: str) -> dict:
    result={}
    for match in re.finditer(r'^function (\w+) takes[^\n]*\n.*?^endfunction\n?',source,re.M|re.S):
        name=match[1]
        if name in result:
            raise ValueError('duplicate function: '+name)
        result[name]=match
    return result


def replace_function(source: str, name: str, expected_sha256: str, replacement: str) -> str:
    indexed=functions(source)
    if name not in indexed:
        raise ValueError('missing function: '+name)
    match=indexed[name]
    if hashlib.sha256(match[0].encode('utf8')).hexdigest()!=expected_sha256:
        raise ValueError('original function hash mismatch: '+name)
    return source[:match.start()]+replacement+source[match.end():]


def inject_module(source: str, module: str) -> str:
    module_globals=re.search(r'^globals\n(.*?)^endglobals\n',module,re.M|re.S)
    if module_globals:
        end=re.search(r'^endglobals$',source,re.M)
        if not end:
            raise ValueError('source globals block missing')
        source=source[:end.start()]+module_globals[1]+source[end.start():]
        module=module[:module_globals.start()]+module[module_globals.end():]
    first=re.search(r'^function ',source,re.M)
    if not first:
        raise ValueError('source functions missing')
    return source[:first.start()]+module+source[first.start():]
