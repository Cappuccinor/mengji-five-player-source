"""Execute the pure selection core's restricted JASS subset for logic tests.

This is not a Warcraft VM: no handles, timers, network, strings, overflow or
gameplay natives. Unsupported syntax is rejected. Runtime tests remain required.
"""
from collections import defaultdict
import re


def expression(text):
    for a,b in [('true','True'),('false','False'),('null','None')]:
        text=re.sub(r'\b'+a+r'\b',b,text)
    return text


def execute(source):
    names=[]
    output=[]
    indent=0
    in_globals=False
    for raw in source.splitlines():
        line=raw.split('//',1)[0].strip()
        if not line:
            continue
        if line=='globals':
            in_globals=True
            continue
        if line=='endglobals':
            in_globals=False
            continue
        if in_globals:
            match=re.fullmatch(r'(integer|boolean)( array)? (\w+)(?:=(.*))?',line)
            if not match:
                raise ValueError('unsupported global: '+line)
            kind,arr,name,value=match.groups()
            names.append(name)
            default='False' if kind=='boolean' else '0'
            output.append(name+'='+(('defaultdict('+('bool' if kind=='boolean' else 'int')+')') if arr else expression(value or default)))
            continue
        if line.startswith('function '):
            match=re.fullmatch(r'function (\w+) takes (.*?) returns (integer|boolean|nothing)',line)
            if not match:
                raise ValueError('unsupported function: '+line)
            name,params,_=match.groups()
            args=[] if params=='nothing' else [p.strip().split()[1] for p in params.split(',')]
            output.append('def '+name+'('+','.join(args)+'):')
            indent=1
            if names:
                output.append('    global '+','.join(names))
            continue
        if line=='endfunction':
            indent=0
            continue
        if line in ('endif','endloop'):
            indent-=1
            continue
        if line.startswith('elseif '):
            indent-=1
            output.append('    '*indent+'elif '+expression(line[7:-5])+':')
            indent+=1
            continue
        if line=='else':
            indent-=1
            output.append('    '*indent+'else:')
            indent+=1
            continue
        if line.startswith('if ') and line.endswith(' then'):
            output.append('    '*indent+'if '+expression(line[3:-5])+':')
            indent+=1
        elif line=='loop':
            output.append('    '*indent+'while True:')
            indent+=1
        elif line.startswith('exitwhen '):
            output.append('    '*indent+'if '+expression(line[9:])+': break')
        elif line.startswith('local '):
            match=re.fullmatch(r'local (integer|boolean) (\w+)=(.*)',line)
            if not match:
                raise ValueError('unsupported local: '+line)
            output.append('    '*indent+match[2]+'='+expression(match[3]))
        elif line.startswith('set '):
            output.append('    '*indent+expression(line[4:]))
        elif line.startswith('call '):
            output.append('    '*indent+expression(line[5:]))
        elif line.startswith('return'):
            output.append('    '*indent+expression(line))
        else:
            raise ValueError('unsupported statement: '+line)
    environment={'defaultdict':defaultdict}
    exec(compile('\n'.join(output),'<restricted JASS core>','exec'),environment)
    return environment
