"""A range of guest memory to a file, in pieces the debugger reads without wrapping.

`MEMDUMPBIN seg:off len` writes byte `x` of the range from the debugger's `GetAddress(seg,
off + x)` (upstream `src/debug/debug.cpp`, `SaveMemoryBin`). Two things in that function make a
long dump wrong while it still answers success with the length asked:

* A 16-bit segment masks the offset to sixteen bits: always in real mode and in v86, and in
  protected mode when the descriptor's D/B bit is clear. A dump that runs past offset 0xFFFF
  reads the start of its own segment again.
* In protected mode a byte past the descriptor's limit has no address, and the dump writes a
  zero for it (the selector in CS excepted: the debugger reads it through its cached base).

So a range that stays inside offsets 0 to 0xFFFF is one command (a 16-bit and a 32-bit segment
address it alike, and its limit is not judged there). A longer one costs something only where
the wrap can happen: in real mode it is cut into windows that each sit inside one segment's 64
KiB, the pieces joined in order; in protected mode the selector's descriptor is read and the
range is refused on a 16-bit segment or past the limit (CS included, judged like the rest).
A v86 stop, which the pane names `VM86`, is a mode `Session.where` refuses, so a range past
0xFFFF there is refused with it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from scry_core import fresh

import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_machine as machine
import dosbox_paths as paths
import dosbox_session as ds

WINDOW_BYTES = 0x10000
SEGMENT_MAX = 0xFFFF
# THE LAST BYTE A REAL-MODE ADDRESS CAN NAME, `FFFF:FFFF` (0xFFFF paragraphs plus 0xFFFF).
# Past it there is no `SEG:OFF` to ask the debugger for, so a range reaching beyond it is
# refused rather than cut short. Written out, not derived from `machine.PARAGRAPH_BYTES`:
# this module is imported while `dosbox_machine` is still loading (through `dosbox_find`),
# so nothing of that module may be read at import time; a test holds the two together.
REAL_REACH_LAST = 0x10FFEF
# Descriptor type bits: S (a code or data segment, not a system one), code, and on a data
# segment expand-down.
_TYPE_S = 0x10
_TYPE_CODE = 0x08
_TYPE_EXPAND_DOWN = 0x04


class Dump(NamedTuple):
    """Where the bytes landed, and whether they were read in real mode past offset 0xFFFF, where
    an address inside them is spelled from its own paragraph (`real_address`)."""
    path: Path
    real_past_ffff: bool


def real_linear(seg: int, off: int) -> int:
    """The linear address of a real-mode `seg:off`, the offset taken whole."""
    return seg * machine.PARAGRAPH_BYTES + off


def real_address(linear: int) -> tuple[int, int]:
    """The real-mode `(segment, offset)` of a linear byte from its own paragraph, the segment
    held to 0xFFFF so the HMA's bytes are `FFFF:` offsets."""
    seg = min(linear // machine.PARAGRAPH_BYTES, SEGMENT_MAX)
    return seg, linear - seg * machine.PARAGRAPH_BYTES


def crosses(off: int, length: int) -> bool:
    """Whether the range runs past offset 0xFFFF, where a 16-bit segment wraps."""
    return off + length > WINDOW_BYTES


def dump_windows(seg: int, off: int, length: int) -> list[tuple[int, int, int]]:
    """The real-mode `(segment, offset, length)` commands that read `length` bytes from
    `seg:off` without wrapping, in order. The range is linear (`seg * 16 + off` onward); a
    range inside one segment's 64 KiB is asked as given, a longer one from each piece's own
    paragraph, so no command crosses its segment's end. Refused when its last byte lies past
    `FFFF:FFFF`, the farthest byte a real-mode address names."""
    start = real_linear(seg, off)
    last = start + length - 1
    if start > REAL_REACH_LAST:
        raise ds.Invalid("bad_argument",
            f"{seg:04X}:{off:04X} is linear {start:X}, which starts past FFFF:FFFF "
            f"({REAL_REACH_LAST:X}), the last byte a real-mode address reaches: no byte from "
            f"there can be asked for")
    if last > REAL_REACH_LAST:
        raise ds.Invalid("bad_argument",
            f"{length} bytes from {seg:04X}:{off:04X} end at linear {last:X}, past "
            f"FFFF:FFFF ({REAL_REACH_LAST:X}), the last byte a real-mode address reaches: "
            f"ask for at most {REAL_REACH_LAST - start + 1} bytes from there")
    if not crosses(off, length):
        return [(seg, off, length)]
    windows: list[tuple[int, int, int]] = []
    at, left = start, length
    while left:
        piece_seg, piece_off = real_address(at)
        n = min(left, WINDOW_BYTES - piece_off)
        windows.append((piece_seg, piece_off, n))
        at, left = at + n, left - n
    return windows


def addressable(found: dict[str, Any], sel: int) -> dict[str, Any] | None:
    """The descriptor `sel` names, or None where upstream gives its bytes no address: a selector
    below 8 (the null one, and the LDT's first slot), no such row, or a row of type 0."""
    if sel < 8:
        return None
    row = machine.descriptor(found, sel)
    return None if row is None or int(row["type"], 16) == 0 else row


def judge_protected(session: ds.Session, sel: int, off: int, length: int,
                    found: dict[str, Any] | None = None) -> None:
    """A protected-mode range past offset 0xFFFF, judged against its descriptor before anything
    is dumped: refused on a 16-bit segment (the debugger wraps it), past the limit (the debugger
    reads zeros there), and for a selector with no descriptor (no address at all). `found`: the
    descriptor listings a caller already read at this stop, so they are not read twice."""
    if session.launch.logfile is None:
        raise ds.Invalid("no_channel",
            f"{length} bytes from {sel:04X}:{off:08X} run past offset 0xFFFF, where the "
            f"selector's descriptor decides whether they wrap or end at its limit, and the "
            f"descriptor tables are read off the session's logfile: `start` with `logfile`")
    notes: list[str] = []
    if found is None:
        reading = machine.read(session, frozenset({"gdt", "ldt"}))
        found, notes = reading.found, reading.notes
    table = machine.table_of(sel)
    if table not in found:
        why = [n for n in notes if f"`{table}`" in n]
        raise ds.Invalid("unexpected_answer",
            f"`{table}` could not be read at this stop, so whether {sel:04X} wraps or ends "
            f"short cannot be said: {'; '.join(why) or 'no reason recorded'}")
    row = addressable(found, sel)
    if row is None:
        raise ds.Invalid("bad_argument",
            f"{sel:04X} names no descriptor in `{table}`, so the debugger gives none of its "
            f"bytes an address and the dump would be zeros: `machine_map` lists the selectors")
    kind = int(row["type"], 16)
    if not row.get("b"):
        raise ds.Invalid("bad_argument",
            f"{sel:04X} is a 16-bit segment (D/B clear), which reaches 64 KiB: the debugger "
            f"reads an offset past 0xFFFF from the segment's start, so {length} bytes from "
            f"offset {off:X} are not the memory there. Ask within offsets 0 to 0xFFFF, or "
            f"read the memory through a 32-bit selector that covers it")
    limit = int(row["limit"], 16)
    last = off + length - 1
    down = kind & _TYPE_S and not kind & _TYPE_CODE and kind & _TYPE_EXPAND_DOWN
    inside = off > limit and last <= 0xFFFFFFFF if down else last <= limit
    if not inside:
        span = (f"above its limit {limit:08X} (expand-down)" if down
                else f"up to its limit {limit:08X}")
        raise ds.Invalid("bad_argument",
            f"{length} bytes from {sel:04X}:{off:08X} end at offset {last:08X}, and "
            f"{sel:04X}'s descriptor covers offsets {span}: past it the debugger writes zeros "
            f"(through the selector in CS, the bytes past the segment), not the segment's memory")


def dump_range(session: ds.Session, seg: int, off: int, length: int, dest: Path,
               found: dict[str, Any] | None = None) -> Dump:
    """`length` bytes from `seg:off` to `dest`, read without a wrap or a zero standing in for
    memory. Within offsets 0 to 0xFFFF: one `Session.memdump`. Past them the stop's mode is read
    (one survey): in real mode the windows of `dump_windows`, each dumped to a scratch file of
    this call's own and joined into `dest`, written once and never over anything; in protected
    mode `judge_protected` (over `found`, listings the caller already read at a stop it knows to
    be protected, so the mode is not surveyed again), then one `Session.memdump`. A v86 stop is
    refused by the survey."""
    ds.check_segment(seg)
    ds.check_dump_length(length)
    if not crosses(off, length):
        return Dump(session.memdump(seg, off, length, dest), False)
    # WHAT NEEDS NO MACHINE BEFORE THE SURVEY that reads the mode, which is a console command:
    # `dest` the way `Session.memdump` judges its own (the pieces go to a scratch directory,
    # so their checks never see it), and a leftover where the debugger writes.
    candidates = session._memdump_candidates()
    dcollect.judge_collection(dest, session.launch.cwd, candidates, "dump")
    dcollect.refuse_leftover(candidates, "dump")
    paths.fresh_dest("dest", dest)
    if found is not None or session.where()["mode"] != dcons.REAL_MODE:
        judge_protected(session, seg, off, length, found)
        return Dump(session.memdump(seg, off, length, dest), False)
    windows = dump_windows(seg, off, length)
    if len(windows) == 1:
        return Dump(session.memdump(*windows[0], dest), True)
    with tempfile.TemporaryDirectory(prefix="dosbox-dump-") as scratch:
        parts = [session.memdump(s, o, n, Path(scratch) / f"{i}.bin").read_bytes()
                 for i, (s, o, n) in enumerate(windows)]
    fresh.create(dest, b"".join(parts), "the dump", named_by_caller=True)
    return Dump(dest, True)
