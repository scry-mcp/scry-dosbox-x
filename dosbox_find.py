"""Memory search on DOSBox-X: `find` for a byte pattern, `scan` for a value narrowed by filters.

The debugger has no byte-pattern search, so `find` searches a `MEMDUMPBIN` dump of the range in
Python. `scan` wraps its `MEMFIND`/`MEMS` value scanner, which holds one instance at a time.
The debugger's printed lines are the contract (read off `src/debug/debug.cpp`); its per-cell
listing is paged, so it is asked for only when the survivors fit one reply.
"""

from __future__ import annotations

import collections
import contextlib
import re
import tempfile
from pathlib import Path
from typing import Any

from scry_core import judges
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.prose import counted

import dosbox_dump as dumping
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

# Verbatim from debug.cpp; `%06X` fields are hex.
SCAN_CREATED = "Created memory search instance."
SCAN_ACTIVE = "Memory search instance is already active."
SCAN_BAD_SEGMENT = "Invalid selector/segment, cancelling."
SCAN_RANGE = re.compile(r"Range exceeds configured memory \(([0-9A-Fa-f]+) bytes\)")
SCAN_OPENED = re.compile(
    r"RAM search from ([0-9A-F]{4}):([0-9A-F]{4,8}) \(lin ([0-9A-F]{8})\) "
    r"with range: ([0-9A-F]{6})")
SCAN_NOT_ACTIVE = "MEMFIND Memory search is not active."
SCAN_TOO_WIDE = "Value is larger than specified size range."
SCAN_FINISHED = re.compile(r"No more matches found .*Memory search instance finished\.")
SCAN_MATCHES = re.compile(
    r"\(([0-9A-F]{6})\) (?:matches found with value|addresses matching) .*"
    r"Iterations: ([0-9A-F]{6})")
SCAN_ROW = re.compile(
    r"\[MEMFIND\] Address: ([0-9A-F]{4}):([0-9A-F]{6}) \(lin ([0-9A-F]{8})\) "
    r"Current Value: ([0-9A-F]+)")
SCAN_CANCELLED = "Memory search instance cancelled."
SCAN_NONE_TO_CANCEL = "No active search instances to cancel."
SCAN_NONE_TO_LIST = "No active search instances to list from."
#: Cell size in bytes to the letter the debugger takes.
CELLS = {1: "B", 2: "W", 4: "D"}
CELL_BYTES = judges.SCAN_CELL_BYTES
OPERATORS = judges.SCAN_OPERATORS


def hex_bytes(name: str, value: str, *, verb: str) -> bytes:
    """The bytes a caller wrote as hex, or the refusal. The only hex parser this server has."""
    try:
        data = bytes.fromhex(value)
    except (ValueError, TypeError):      # non-string from a hand-written step
        raise ds.Invalid("bad_argument", f"{name}={value!r} is not a whole number of hex "
                                         "bytes (two digits per byte)") from None
    if not data:
        raise ds.Invalid("bad_argument", f"{name} is empty: nothing to {verb}")
    return data


def check_pattern(data_hex: str) -> bytes:
    return hex_bytes("data_hex", data_hex, verb="search for")


def check_find_length(length: int, pattern: bytes) -> None:
    """A search's range holds the pattern at least once, which also refuses no range at all."""
    if length < len(pattern):
        raise ds.Invalid("bad_argument",
            f"length={length} is shorter than the {len(pattern)}-byte pattern: nothing "
                         f"could match")


def find(session: ds.Session, seg: int, off: int, length: int, pattern: bytes) -> dict[str, Any]:
    """Every offset in `length` bytes from `seg:off` where `pattern` starts, searched in a
    `dump_range` dump (windows past 0xFFFF included) kept in a scratch directory."""
    check_find_length(length, pattern)
    with tempfile.TemporaryDirectory(prefix="dosbox-find-") as scratch:
        dumped = dumping.dump_range(session, seg, off, length, Path(scratch) / "range.bin")
        data = dumped.path.read_bytes()
    # a pattern matching everywhere would otherwise hold one number per byte
    hits: collections.deque[int] = collections.deque(maxlen=judges.HITS_MAX)
    total = 0
    at = data.find(pattern)
    while at != -1:
        hits.append(off + at)
        total += 1
        at = data.find(pattern, at + 1)
    # the span rides on the reply so a zero says over which bytes it is a zero
    return {"seg_off": st.seg_off(seg, off), "length": length,
            "span": {"from": st.seg_off(seg, off), "length": length, "source": "ref+length"},
            "hits": [_spelled(seg, o, dumped.real_past_ffff) for o in hits],
            "hits_total": total, "truncated": total > judges.HITS_MAX}


def _spelled(seg: int, off: int, real_past_ffff: bool) -> str:
    """A hit as `SEG:OFF`; in real mode an offset past 0xFFFF is respelled from its paragraph."""
    if real_past_ffff and off >= dumping.WINDOW_BYTES:
        seg, off = dumping.real_address(dumping.real_linear(seg, off))
    return st.seg_off(seg, off)


# A reply is the LAST family line, never the first: one command can print several.
SCAN_LINES = (SCAN_OPENED, SCAN_MATCHES, SCAN_FINISHED, SCAN_RANGE,
              re.compile(re.escape(SCAN_ACTIVE)), re.compile(re.escape(SCAN_BAD_SEGMENT)),
              re.compile(re.escape(SCAN_NOT_ACTIVE)), re.compile(re.escape(SCAN_TOO_WIDE)),
              re.compile(re.escape(SCAN_CANCELLED)), re.compile(re.escape(SCAN_NONE_TO_CANCEL)),
              re.compile(re.escape(SCAN_NONE_TO_LIST)))
SCAN_LISTED = re.compile(r"\[MEMFIND\] Matched values during current instance: ([0-9A-F]{6})")


def _last_scan_line(out: str) -> str:
    last = ""
    for line in out.splitlines():
        if any(p.search(line) for p in SCAN_LINES):
            last = line
    return last


def _refuse(line: str, what: str) -> None:
    if SCAN_ACTIVE in line:
        raise ds.Invalid("needs_call",
            "the debugger holds one search instance at a time and one is open: "
                         "`scan(method=\"clear\")` it first, or keep filtering it with "
                         "`scan(method=\"filter\")`")
    if SCAN_BAD_SEGMENT in line:
        raise ds.Invalid("bad_argument", f"the debugger refused the segment: {SCAN_BAD_SEGMENT}")
    if m := SCAN_RANGE.search(line):
        raise ds.Invalid("bad_argument",
            f"the range runs past the memory the debugger addresses "
                         f"({int(m.group(1), 16)} bytes); nothing was opened")
    if SCAN_NOT_ACTIVE in line:
        STATE.scan_forget()                 # whatever was counted belongs to a scan now gone
        raise ds.Invalid("needs_call",
            f"no search instance is open, so there is nothing to {what}: `scan(method=\"start\")` "
            "one")
    if SCAN_TOO_WIDE in line:
        raise ds.Invalid("bad_argument",
            "the value does not fit the instance's width: the debugger refused the filter")


def _unexpected(out: str, wanted: str) -> ds.Invalid:
    """The refusal naming what the debugger printed instead."""
    return ds.Invalid("unexpected_answer",
        f"the debugger did not report {wanted}. What it printed: {out.strip()[-300:]!r}")


def check_scan_range(length: int, cell_bytes: int) -> None:
    """A scan's range as the debugger takes it: a known cell size, whole cells, six hex digits."""
    vocab.one_of("cell_bytes", cell_bytes, CELL_BYTES)
    if not isinstance(length, int) or isinstance(length, bool):
        raise ds.Invalid("bad_argument", f"length is a byte count; got {length!r}")
    if length <= 0:
        raise ds.Invalid("bad_argument", f"length={length} is not a byte count")
    if length > 0xFFFFFF:
        raise ds.Invalid("bad_argument",
            f"length={length} is more than the six hex digits the debugger takes")
    if length % cell_bytes:
        raise ds.Invalid("bad_argument",
            f"length={length} is not a whole number of {cell_bytes}-byte cells: the last "
            f"{counted(length % cell_bytes, 'byte')} would be no cell")


def unlisted_note() -> str:
    """Why a filter past `judges.HITS_MAX` lists none."""
    return (f"more than {judges.HITS_MAX} survive, more than a reply lists: filter again to list "
            f"them")


NO_VALUE_WHY = ("no `value` was given, so each cell was compared with its value at "
                "`scan(method=\"start\")`")


def check_filter(operator: str, value: int | None, limit: int = judges.HITS_DEFAULT) -> None:
    """A filter as the debugger takes it, judged with no machine (it compares unsigned)."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= judges.HITS_MAX:
        raise ds.Invalid("bad_argument", f"limit={limit!r} is outside 1..{judges.HITS_MAX}, how "
                         f"many survivors a filter lists; above {judges.HITS_MAX}, filter again")
    vocab.one_of("operator", operator, OPERATORS)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                              or value < 0):
        raise ds.Invalid("bad_argument",
            f"value={value!r} is not a whole number of zero or more; the debugger compares "
            f"unsigned")


def start_scan(session: ds.Session, seg: int, off: int, length: int,
               cell_bytes: int) -> dict[str, Any]:
    """Open the debugger's search instance over `length` bytes from `seg:off`."""
    check_scan_range(length, cell_bytes)
    letter, size = CELLS[cell_bytes], cell_bytes
    out = session.command(f"MEMFIND {seg:04X}:{off:X} {length:X} {letter}")
    last = _last_scan_line(out)
    _refuse(last, "open")
    opened = SCAN_OPENED.search(last)
    if opened is None:
        raise _unexpected(out, "a search instance")
    if int(opened.group(4), 16) != length:
        # close the stray instance, or the next start is told one is open that we do not hold
        with contextlib.suppress(ds.Invalid):
            session.command("MEMFIND !")
        raise _unexpected(out,
            f"the range asked for: {length:#x} bytes were asked and it opened a search over "
            f"{int(opened.group(4), 16):#x}")
    STATE.scan_iterations = 0           # a scan this server opened: no filter yet
    STATE.scan_cell_bytes = size
    return {"seg_off": st.seg_off(seg, off), "length": length, "cell_bytes": size,
            "addr": st.flat(int(opened.group(3), 16)), "hits_total": length // size}


def _listing(session: ds.Session, survivors: int) -> list[dict[str, Any]]:
    """`MEMFIND L`, whole in one reply, rows keyed by address and held to the closing count."""
    out = session.command("MEMFIND L")
    rows: dict[str, dict[str, Any]] = {}
    for s, o, lin, v in SCAN_ROW.findall(out):
        at = st.seg_off(int(s, 16), int(o, 16))
        rows[at] = {"seg_off": at, "addr": st.flat(int(lin, 16)), "value": int(v, 16)}
    listed = SCAN_LISTED.search(out)
    if listed is None or int(listed.group(1), 16) != survivors or len(rows) != survivors:
        raise _unexpected(out,
            f"a whole listing: it counted {survivors} survivors, and the listing closed at "
            f"{int(listed.group(1), 16) if listed else 'no count'} with {len(rows)} rows")
    return list(rows.values())


def filter_scan(session: ds.Session, operator: str, value: int | None,
                limit: int = judges.HITS_DEFAULT) -> dict[str, Any]:
    """Keep the cells satisfying `operator` against `value`, or against their value at the scan's
    opening when there is none. Lists the first `limit` survivors, none past `HITS_MAX`; a step
    leaving none closes the instance, as the debugger does.

    `iterations` is the debugger's count, absent from its closing line: the server answers the
    last one it read plus one, or unavailable when it holds none it can stand behind."""
    check_filter(operator, value, limit)
    cell = STATE.scan_cell_bytes
    if value is not None and cell is not None and value >= 1 << (8 * cell):
        raise ds.Invalid("bad_argument",
            f"value={value:#x} is wider than the open scan's {cell}-byte cell (at most "
            f"{(1 << (8 * cell)) - 1:#x}): nothing was sent")
    arg = "" if value is None else f"{value:X}"
    out = session.command(f"MEMS {operator}{arg}")
    last = _last_scan_line(out)
    _refuse(last, "filter")
    if SCAN_FINISHED.search(last):
        held = STATE.scan_iterations
        STATE.scan_forget()
        closing: dict[str, Any] = {
            "operator": operator, "value": _asked(value, cell),
            "iterations": contract.unavailable(
                "the debugger's closing line carries no count, and this server holds none it "
                "can stand behind: the scan was opened, filtered or ended through `debug`")
            if held is None else held + 1, "closed": True,
            "hits": [], "hits_total": 0, "truncated": False}
        return closing
    summary = SCAN_MATCHES.search(last)
    if summary is None:
        raise _unexpected(out, "survivors or a finished search")
    survivors = int(summary.group(1), 16)
    iterations = int(summary.group(2), 16)
    STATE.scan_iterations = iterations
    listable = survivors <= judges.HITS_MAX
    hits = [_shown(row, cell) for row in _listing(session, survivors)[:limit]] if listable else []
    return {"operator": operator, "value": _asked(value, cell), "iterations": iterations,
            "closed": False, "hits": hits, "hits_total": survivors,
            "truncated": survivors > len(hits),
            **({} if listable else {"note": unlisted_note()})}


def clear_scan(session: ds.Session) -> dict[str, Any]:
    """Cancel the debugger's search instance. Nothing open is a no-op that says so."""
    out = session.command("MEMFIND !")
    last = _last_scan_line(out)
    if SCAN_CANCELLED in last or SCAN_NONE_TO_CANCEL in last:
        STATE.scan_forget()
    if SCAN_CANCELLED in last:
        return {"cleared": True}
    if SCAN_NONE_TO_CANCEL in last:
        return {"cleared": False, "note": "no search instance was open"}
    raise _unexpected(out, "a cancelled instance nor that none was open")


def _cell_bits(cell: int | None) -> int:
    """Display width in bits; a byte when the cell is unknown (a scan opened through `debug`)."""
    return 8 * (cell or 1)


def _asked(value: int | None, cell: int | None) -> str | dict[str, Any]:
    """The value a filter compared with, or why there is none."""
    return (contract.unavailable(NO_VALUE_WHY) if value is None
            else judges.hex_at_width(value, _cell_bits(cell)))


def _shown(row: dict[str, Any], cell: int | None) -> dict[str, Any]:
    """A survivor's row with its value at the cell's width."""
    return {**row, "value": judges.hex_at_width(int(row["value"]), _cell_bits(cell))}
