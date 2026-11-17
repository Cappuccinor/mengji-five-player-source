"""Update a copied MPQ with StormLib; independently verify opaque resources."""
from __future__ import annotations
import ctypes as C
import hashlib
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor'))
import mpyq

BASELINE = 'f5aa029c5d43f49ee9d6bf3d710d54714528450cecf9b27ae2dc539bde765853'
DLL = ROOT / 'vendor/stormlib/x64/StormLib.dll'


def _library():
    lib = C.WinDLL(str(DLL), use_last_error=True)
    H, D, B = C.c_void_p, C.c_uint32, C.c_bool
    definitions = {
        'SFileOpenArchive': ([C.c_wchar_p, D, D, C.POINTER(H)], B),
        'SFileCloseArchive': ([H], B),
        'SFileOpenFileEx': ([H, C.c_char_p, D, C.POINTER(H)], B),
        'SFileGetFileSize': ([H, C.POINTER(D)], D),
        'SFileReadFile': ([H, H, D, C.POINTER(D), H], B),
        'SFileCloseFile': ([H], B),
        'SFileCreateFile': ([H, C.c_char_p, C.c_uint64, D, D, D, C.POINTER(H)], B),
        'SFileWriteFile': ([H, H, D, D], B),
        'SFileFinishFile': ([H], B),
    }
    for name, (args, result) in definitions.items():
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = args, result
    return lib


def _check(ok, action):
    if not ok:
        raise OSError(C.get_last_error(), action)


def read_member(path: Path, name: str) -> bytes:
    lib, archive, member = _library(), C.c_void_p(), C.c_void_p()
    _check(lib.SFileOpenArchive(str(Path(path).resolve()), 0, 0x30100, C.byref(archive)), 'open archive')
    try:
        _check(lib.SFileOpenFileEx(archive, name.encode('utf-8'), 0, C.byref(member)), 'open ' + name)
        try:
            high = C.c_uint32()
            size = lib.SFileGetFileSize(member, C.byref(high))
            if high.value or size > 128 * 1024 * 1024:
                raise ValueError('member exceeds 128 MiB limit')
            if not size:
                return b''
            buf, got = C.create_string_buffer(size), C.c_uint32()
            _check(lib.SFileReadFile(member, buf, size, C.byref(got), None), 'read ' + name)
            if got.value != size:
                raise ValueError('short member read')
            return buf.raw
        finally:
            lib.SFileCloseFile(member)
    finally:
        lib.SFileCloseArchive(archive)


def _inventory(data: bytes):
    base = data.find(b'MPQ\x1a')
    if base < 0:
        raise ValueError('missing MPQ header')
    mpq = mpyq.MPQArchive(io.BytesIO(data[base:]), listfile=False)
    rows = {}
    for entry in mpq.hash_table:
        idx = entry.block_table_index
        if idx in (0xFFFFFFFF, 0xFFFFFFFE):
            continue
        if idx >= len(mpq.block_table):
            raise ValueError('invalid MPQ block reference')
        block = mpq.block_table[idx]
        start, end = base + block.offset, base + block.offset + block.archived_size
        if not (base <= start <= end <= len(data)):
            raise ValueError('invalid MPQ block extent')
        identity = (entry.hash_a, entry.hash_b, entry.locale, entry.platform)
        if identity in rows:
            raise ValueError('ambiguous hash entry')
        rows[identity] = (idx, block, hashlib.sha256(data[start:end]).hexdigest())
    return mpq, rows


def verify_preservation(before: bytes, after: bytes, replacements: dict[str, bytes]) -> dict:
    old, old_rows = _inventory(before)
    _, new_rows = _inventory(after)
    replaced = {(old._hash(n, 'HASH_A'), old._hash(n, 'HASH_B')) for n in replacements}
    preserved = set()
    for identity, (idx, block, digest) in old_rows.items():
        if identity[:2] in replaced:
            continue
        if identity not in new_rows:
            raise ValueError(f'unknown member lost: {identity}')
        _, new_block, new_digest = new_rows[identity]
        if (block.size, block.flags, digest) != (new_block.size, new_block.flags, new_digest):
            raise ValueError(f'original member changed: {identity}')
        if block.flags & 0x20000 and block.offset != new_block.offset:
            raise ValueError('encrypted fixed-key block moved')
        preserved.add(idx)
    return {'preserved_blocks': len(preserved), 'unknown_members_preserved': True}


def update_archive(source: Path, destination: Path, replacements: dict[str, bytes], *, map_title=None) -> dict:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('source and destination must differ')
    if destination.exists():
        raise FileExistsError(destination)
    before = source.read_bytes()
    if hashlib.sha256(before).hexdigest() != BASELINE:
        raise ValueError('source baseline hash mismatch')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Staging and all temporary files remain beside the F: output.
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='mpq-') as temporary:
        stage = Path(temporary) / 'stage.w3x'
        stage.write_bytes(before)
        if replacements:
            lib, archive = _library(), C.c_void_p()
            # NO_LISTFILE / NO_ATTRIBUTES also force read-only in StormLib.
            _check(lib.SFileOpenArchive(str(stage), 0, 0, C.byref(archive)), 'open writable copy')
            try:
                for name, content in sorted(replacements.items()):
                    member = C.c_void_p()
                    _check(lib.SFileCreateFile(archive, name.encode('utf-8'), 0, len(content), 0,
                                              0x80000200, C.byref(member)), 'create ' + name)
                    try:
                        buf = C.create_string_buffer(content)
                        _check(lib.SFileWriteFile(member, buf, len(content), 2), 'write ' + name)
                    finally:
                        _check(lib.SFileFinishFile(member), 'finish ' + name)
            finally:
                _check(lib.SFileCloseArchive(archive), 'close writable copy')
        after = stage.read_bytes()
        if map_title is not None:
            from tools.map_identity import rename_header
            after=rename_header(after,map_title)
            stage.write_bytes(after)
        report = verify_preservation(before, after, replacements)
        for name, content in replacements.items():
            if read_member(stage, name) != content:
                raise ValueError('replacement readback mismatch: ' + name)
        report.update(sha256=hashlib.sha256(after).hexdigest(), replacements=list(replacements))
        # Exclusive final creation; never replace an existing deliverable.
        with destination.open('xb') as stream:
            stream.write(after)
        return report
