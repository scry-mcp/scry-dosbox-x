"""`start(symbols=)`: a table judged at `start`, placed at the first stop DOS holds its program.

The load segment is read off the memory chain (`DOS MCBS`), never a stop's `CS`, which a stop in
DOS or a second code segment would make wrong. The program's own block is the one at its own PSP;
an EXE's table counts from one PSP past it, a COM's (`ORG 100h`) from the PSP itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scry_core import judges

from scry_dosbox_x import arming, coff, comments, grammar, machine, placement
from scry_dosbox_x import session as ds
from scry_dosbox_x import symbols as sym
from scry_dosbox_x.state import STATE

PROGRAM = "program"
BASE_FROM = (PROGRAM, *ds.SELINFO_REGS)
PSP_PARAGRAPHS = 0x10      # an EXE's image starts one 256-byte PSP past it


@dataclass(frozen=True)
class Held:
    path: str
    base_from: str
    com: bool = False
    #: The table's comparison with the executable beside it, as `coff.check` answered it.
    checked: dict[str, Any] = field(default_factory=dict)


def check(symbols: str, base_from: str) -> Held | None:
    """`start`'s `symbols` and `base_from`, judged before the boot."""
    word = PROGRAM if base_from.lower() == PROGRAM else base_from.upper()
    if not symbols:
        if word != PROGRAM:
            raise ds.Invalid("bad_argument", "`base_from` places a `symbols` table, and none "
                             "was given")
        return None
    if word not in BASE_FROM:
        raise ds.Invalid("bad_argument", f"`base_from` is `program` or one of "
                         f"{', '.join(ds.SELINFO_REGS)}, got {base_from!r}")
    path = judges.existing_file("symbols", symbols, "symbol file")
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        parsed, _ = sym.parse(text)
        sym.check_folded(parsed, text)
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", f"symbols: {e}") from None
    checked = coff.check(path, parsed)
    com = any(p.suffix.lower() == ".com" and p.stem.upper() == path.stem.upper()
              for p in path.parent.iterdir())
    return Held(str(path), word, com, checked)


def load_segment(rows: list[dict[str, Any]], program: str, com: bool = False) -> int | None:
    """The segment `program`'s table counts from, or None while it is not loaded."""
    for row in rows:
        mcb, psp = int(row["mcb_seg"], 16), int(row["psp_seg"], 16)
        if psp == mcb + 1 and str(row.get("filename", "")).strip().upper() == program.upper():
            return psp if com else psp + PSP_PARAGRAPHS
    return None


def place_if_due(session: ds.Session) -> dict[str, Any] | None:
    """At a stop: the held table placed once its program is loaded, said once; else None."""
    held = STATE.start_symbols
    if held is None:
        return None
    try:
        rows = machine.parse_mcbs(session.listing("DOS MCBS"))
    except (ds.Invalid, machine.Unreadable):
        return None                     # caught mid-change: the next stop reads again
    segment = load_segment(rows, Path(held.path).stem, held.com)
    program = held.base_from == PROGRAM
    if segment is None or (not program and grammar.real_segments(session.where()["mode"])):
        return None             # a register base needs a descriptor, which real mode lacks
    STATE.start_symbols = None
    try:
        loaded = placement.load(session, held.path, Path(held.path),
                                segment * 16 if program else None,
                                "CS" if program else held.base_from, None, False, None,
                                rearm_declarations=arming.rearm_declarations,
                                take_the_map=comments.park_rows_take_the_map)
    except ds.Invalid as e:
        return {"placed": False, "path": held.path, "code": e.code, "why": str(e)}
    return {"placed": True, "path": held.path, "load_segment": f"{segment:04X}",
            "base": loaded["base"], "loaded": loaded["loaded"]}
