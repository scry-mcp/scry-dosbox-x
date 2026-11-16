"""A range of guest memory to a file, in pieces the debugger reads without wrapping.

Upstream `SaveMemoryBin` reads byte `x` through `GetAddress(seg, off + x)`, which makes a long
dump wrong while it still answers success with the length asked:

* A 16-bit segment (real mode, `VM86`, or protected with D/B clear) masks the offset to sixteen
  bits, so a dump past 0xFFFF rereads the start of its own segment.
* In protected mode a byte past the descriptor's limit is written as zero.

A range inside offsets 0 to 0xFFFF is one command; a longer one is cut into per-segment
windows in real mode and `VM86`, and refused in protected mode on a 16-bit segment or past
the limit.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from scry_core import fresh

from scry_dosbox_x import collect as dcollect
from scry_dosbox_x import grammar, machine, paths
from scry_dosbox_x import session as ds

WINDOW_BYTES = 0x10000
SEGMENT_MAX = 0xFFFF
# `FFFF:FFFF`, the last byte a real-mode address names. Written out, not derived from
# `machine.PARAGRAPH_BYTES`: this module is imported while `machine` is still loading.
REAL_REACH_LAST = 0x10FFEF
_TYPE_S = 0x10
_TYPE_CODE = 0x08
_TYPE_EXPAND_DOWN = 0x04


class Dump(NamedTuple):
    """Where the bytes landed, and whether real mode read them past offset 0xFFFF."""
    path: Path
    real_past_ffff: bool


def real_linear(seg: int, off: int) -> int:
    """The linear address of a real-mode `seg:off`, the offset taken whole."""
    return seg * machine.PARAGRAPH_BYTES + off


def real_address(linear: int) -> tuple[int, int]:
    """The real-mode `(segment, offset)` of a linear byte, the segment capped at 0xFFFF."""
    seg = min(linear // machine.PARAGRAPH_BYTES, SEGMENT_MAX)
    return seg, linear - seg * machine.PARAGRAPH_BYTES


def crosses(off: int, length: int) -> bool:
    """Whether the range runs past offset 0xFFFF."""
    return off + length > WINDOW_BYTES


def dump_windows(seg: int, off: int, length: int) -> list[tuple[int, int, int]]:
    """The real-mode `(segment, offset, length)` commands reading the range without wrapping."""
    start = real_linear(seg, off)
    last = start + length - 1
    if start > REAL_REACH_LAST:
        raise ds.Invalid("bad_argument",
            f"{grammar.canonical_seg_off(seg, off)} is linear {start:X}, which starts past "
            f"FFFF:FFFF ({REAL_REACH_LAST:X}), the last byte a real-mode address reaches: no byte "
            f"from there can be asked for")
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
    """The descriptor `sel` names, or None where its bytes have no address."""
    if sel < 8:
        return None
    row = machine.descriptor(found, sel)
    return None if row is None or int(row["type"], 16) == 0 else row


def judge_protected(session: ds.Session, sel: int, off: int, length: int,
                    found: dict[str, Any] | None = None) -> None:
    """Refuse a protected-mode range past 0xFFFF on a 16-bit segment, past the limit, or with
    no descriptor. `found`: listings already read at this stop."""
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
            f"{length} bytes from {grammar.canonical_seg_off(sel, off)} end at offset {last:08X}, "
            f"and {sel:04X}'s descriptor covers offsets {span}: past it the debugger writes zeros "
            f"(through the selector in CS, the bytes past the segment), not the segment's memory")


def dump_range(session: ds.Session, seg: int, off: int, length: int, dest: Path,
               found: dict[str, Any] | None = None) -> Dump:
    """`length` bytes from `seg:off` to `dest` with no wrap or stand-in zeros.

    `found`: listings read at a stop known to be protected, so the mode is not surveyed again."""
    ds.check_segment(seg)
    ds.check_dump_length(length)
    if not crosses(off, length):
        return Dump(session.memdump(seg, off, length, dest), False)
    # Before the mode survey: the pieces go to a scratch directory, so their checks miss `dest`.
    candidates = session._memdump_candidates()
    dcollect.judge_collection(dest, session.launch.cwd, candidates, "dump")
    dcollect.refuse_leftover(candidates, "dump")
    dest = paths.fresh_dest("dest", dest)
    if found is not None or not grammar.real_segments(session.where()["mode"]):
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
