"""Keep injected function locals separate from the legacy global namespace.

Warcraft 1.27 rejected the combined script when injected locals shadowed the
original single-letter sound globals. Namespace parameters and indented locals
without changing string literals, rawcodes, comments or legacy functions.
"""
import re
from tools.patching import functions

TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\x27[^\x27\n]*\x27|//[^\n]*|\b\w+\b')


def namespace_new_locals(raw: bytes) -> bytes:
    source = raw.decode('utf8')
    for name, match in reversed(list(functions(source).items())):
        if not name.startswith(('MJ_', 'MJ5_')):
            continue
        body = match[0]
        args = body.splitlines()[0].split(' takes ')[1].split(' returns ')[0]
        names = re.findall(r'(?:^|,)\s*\w+\s+(\w+)', args)
        names += re.findall(r'^\s*local \w+(?: array)? (\w+)', body, re.M)
        rename = {n: 'mjlocal_' + n for n in names if not n.startswith('mjlocal_')}
        if any(new in names for new in rename.values()):
            raise ValueError('local namespace collision in ' + name)
        body = TOKENS.sub(lambda token: rename.get(token[0], token[0]), body)
        source = source[:match.start()] + body + source[match.end():]
    return source.encode('utf8')
