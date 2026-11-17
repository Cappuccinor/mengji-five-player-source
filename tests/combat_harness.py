"""Native-boundary logic harness. No engine, timing, rendering or synchronization claim."""
import re
from tests.jass_subset import execute


def run_functions(source):
    # Python keeps numeric values regardless of these JASS declaration types.
    source=re.sub(r'\breturns real\b','returns integer',source)
    source=re.sub(r'local (real|player|unit|group|timer) ', 'local integer ',source)
    source=re.sub(r'local integer (\w+)\n',r'local integer \1=0\n',source)
    source=re.sub(r'\$([0-9A-F]+)',r'0x\1',source)
    source=re.sub(r'\bfunction (\w+)(?=[,)])',r'\1',source)
    source=source.replace('else\nendif','endif')
    source=re.sub(r'(^if [^\n]+ then\n)(?=else\n|endif\n)',r'\1call MJ_TestNoop()\n',source,flags=re.M)
    env=execute(source)
    env['MJ_TestNoop']=lambda:None
    return env
