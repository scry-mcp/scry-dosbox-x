"""The symbols a DJGPP executable carries in its COFF table, checked against a loaded text table.

A text table goes stale when the program is relinked without it: every name still resolves, a
few bytes off. The linker wrote the image's symbols in the same run as the code, so they are
exact. Real-mode executables carry none, and then nothing here can check.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from scry_core import reply_contract as contract

from scry_dosbox_x import session as ds
from scry_dosbox_x import symbols as sym

I386_MAGIC = 0x14C
ENTRY_BYTES = 18
C_EXT = 2
TEXT_SECTION = 1
NAMED_MAX = 3


class CutImage(Exception):
    """A COFF image whose header or tables run past the end of the file."""


class Stripped(Exception):
    """A COFF image whose header names no symbol table: `strip` ran on it."""


def _coff_start(data: bytes) -> int:
    """Where the COFF file starts: after the go32 stub, if the image opens with one."""
    if data[:2] != b"MZ":
        return 0
    if len(data) < 6:
        raise CutImage("the MZ header is cut")
    last, pages = struct.unpack_from("<HH", data, 2)
    return int(pages) * 512 - ((512 - int(last)) % 512 if last else 0)


def global_code_symbols(exe: Path) -> dict[str, int] | None:
    """The image's global `.text` symbols, name to value; None when it is not a COFF image;
    `CutImage` when cut short, `Stripped` when it has no symbol table."""
    try:
        return _symbols(exe.read_bytes())
    except (struct.error, ValueError, IndexError) as e:
        raise CutImage(str(e)) from None


def _symbols(data: bytes) -> dict[str, int] | None:
    start = _coff_start(data)
    if len(data) < start:
        raise CutImage(f"the file is {len(data)} bytes, shorter than its MZ header says "
                       f"({start})")
    if len(data) < start + 20:
        return None
    magic, _sections, _stamp, table, count = struct.unpack_from("<HHIII", data, start)
    if magic != I386_MAGIC:
        return None
    if table == 0:
        raise Stripped
    strings = start + table + count * ENTRY_BYTES
    out: dict[str, int] = {}
    i = 0
    while i < count:
        at = start + table + ENTRY_BYTES * i
        if at + ENTRY_BYTES > len(data):
            raise CutImage("the symbol table runs past the end of the file")
        raw = data[at:at + 8]
        if raw[:4] == b"\0\0\0\0":
            name_at = strings + struct.unpack_from("<I", raw, 4)[0]
            name = data[name_at:data.index(b"\0", name_at)].decode("latin-1")
        else:
            name = raw.rstrip(b"\0").decode("latin-1")
        value, section, _type, storage, aux = struct.unpack_from("<IhHBB", data, at + 8)
        if section == TEXT_SECTION and storage == C_EXT:
            out[name] = value
        i += 1 + aux
    return out


def executable_beside(table: Path) -> Path | None:
    """The executable beside a table under its stem, matched in any case as DOS does."""
    want = f"{table.stem}.exe".lower()
    try:
        return next((c for c in sorted(table.parent.iterdir())
                     if c.name.lower() == want and c.is_file()), None)
    except OSError:
        return None


def stamp(path: Path) -> dict[str, Any] | None:
    """A file's identity as the disk holds it now, or None when it cannot be read: what tells a
    later reply that the executable moved under the running session."""
    try:
        held = path.stat()
    except OSError:
        return None
    return {"path": str(path), "size": held.st_size, "mtime_ns": held.st_mtime_ns}


def check(table: Path, symbols: list[sym.Symbol]) -> dict[str, Any]:
    """The table's global code symbols against the executable beside it: `against` and `agree`
    when all match, unavailable when nothing can be compared, a refusal when any differs."""
    exe = executable_beside(table)
    if exe is None:
        return contract.unavailable(f"no executable named {table.stem}.exe beside the table, "
                                    "so it could not be checked against its build")
    if not any(s.kind != "?" for s in symbols):
        return contract.unavailable("the table carries no symbol kinds (a link map lists none), "
                                    "so its code symbols cannot be told from the rest")
    try:
        image = global_code_symbols(exe)
    except CutImage as e:
        return contract.unavailable(f"{exe.name}'s COFF image is cut ({e}), so the table could "
                                    "not be checked against it")
    except Stripped:
        return contract.unavailable(f"{exe.name} is a COFF image stripped of its symbol table, "
                                    "so the table could not be checked against it")
    except OSError as e:
        return contract.unavailable(f"{exe.name} could not be read ({e})")
    if image is None:
        return contract.unavailable(f"{exe.name} carries no COFF symbol table (a real-mode "
                                    "executable carries none), so the table could not be "
                                    "checked against it")
    shared = [s for s in symbols if s.kind == "T" and s.name in image]
    if not shared:
        return contract.unavailable(f"{exe.name}'s own symbols share no global code symbol "
                                    "with the table, so nothing could be compared")
    off = [s for s in shared if s.offset != image[s.name]]
    if off:
        named = ", ".join(f"{s.name} at 0x{s.offset:X} in the table and 0x{image[s.name]:X} "
                          f"in {exe.name}" for s in off[:NAMED_MAX])
        more = f", and {len(off) - NAMED_MAX} more" if len(off) > NAMED_MAX else ""
        raise ds.Invalid("bad_argument",
            f"the table and {exe.name} beside it disagree on {len(off)} of the {len(shared)} "
            f"global code symbols they share ({named}{more}), so one of the two is another "
            f"build's. Nothing was loaded; regenerate the table from the executable the "
            f"guest runs, or move a stale {exe.name} away from it")
    return {"against": str(exe), "agree": len(shared)}
