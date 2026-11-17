"""Run pjass with a declared API set; this does not execute the map."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check_jass(script: Path, api_dir: Path) -> dict:
    # pjass accepts most C0 bytes inside strings. Never ship binary object text
    # as JASS source; this gate is stricter than its syntax-only lexer.
    raw=Path(script).read_bytes()
    for offset,value in enumerate(raw):
        if (value<32 and value not in (9,10,13)) or value==127:
            return {'passed':False,'exit_code':1,'command':[],
                    'output':f'Forbidden control byte 0x{value:02x} at byte {offset}',
                    'runtime_verified':False}
    command = [str(ROOT / 'vendor/pjass.exe'), str(api_dir / 'common.j'),
               str(api_dir / 'Blizzard.j'), str(script)]
    result = subprocess.run(command, capture_output=True, timeout=30)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    return {'passed': result.returncode == 0, 'exit_code': result.returncode,
            'command': command, 'output': output, 'runtime_verified': False}


if __name__ == '__main__':
    result = check_jass(Path(sys.argv[1]), ROOT / 'vendor/jass-1.27.1')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result['exit_code'])
