"""Searching the guest's memory on DOSBox-X: a byte PATTERN, and a VALUE narrowed by
successive comparisons.

TWO SEARCHES, BECAUSE THE DEBUGGER HAS ONE AND A CALLER NEEDS BOTH. A byte-pattern search
answers every address holding a pattern; the DOSBox-X debugger has no such command. What it
has is `MEMFIND`/`MEMS`, a value SCANNER in the cheat-search tradition: open an instance over
a range in cells of 1, 2 or 4 bytes, then filter it again and again against a value or
against what each cell held when the scan opened, until the cells that survive are the ones
that move the way the program does. For a program with no map, that narrowing is how
anything is found.

So `find` is answered from a BINARY DUMP of the range (the same `MEMDUMPBIN` route `memdump`
takes, its windows past offset 0xFFFF included, into a scratch file this module owns), searched
in Python: exact, console only. And the scanner is exposed as its own family, `scan_start` /
`scan_filter` / `scan_clear`, because the debugger holds ONE instance at a time and the state
is its own: a `scan_start` while one is open is refused in the debugger's own words rather
than silently replacing it.

WHAT THE CONSOLE PRINTS IS THE CONTRACT, read off `src/debug/debug.cpp` (the `MEMFIND` and
`MEMS` branches) and then captured from the live emulator into the tests' doubles. The
scanner's per-cell listing (`MEMFIND L`) is paged content on the ncurses screen, so it is
asked for only when the survivors are few enough to fit one reply.
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

import dosbox_console as dcons
import dosbox_dump as dumping
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

# The lines the debugger prints, verbatim from debug.cpp. `%06X` fields are hex.
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
#: The cells a scan reads, by their size in bytes, and the letter the debugger takes for each.
CELLS = {1: "B", 2: "W", 4: "D"}
#: The cell sizes, as `scan_start` takes them.
CELL_BYTES = tuple(CELLS)
OPERATORS = ("=", "!", ">", ">=", "<", "<=")


def hex_bytes(name: str, value: str, *, verb: str) -> bytes:
    """The bytes a caller wrote as hex, or the refusal. THE ONLY HEX PARSER THIS SERVER HAS.

    `bytes.fromhex`: it IGNORES ASCII WHITESPACE by documented
    design, so a line pasted out of a dump works. `verb` is the one thing the callers differ on --
    what the bytes are FOR.
    """
    try:
        data = bytes.fromhex(value)
    except (ValueError, TypeError):      # a non-string arrives from a hand-written step
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
    """Every offset in `length` bytes from `seg:off` where `pattern` starts. The bytes come
    from `memdump`'s route (`dosbox_dump.dump_range`) into a scratch directory of this call's
    own, never the caller's tree: the same size check, and the same windows past offset
    0xFFFF, so a range longer than a segment is searched in the memory really there."""
    check_find_length(length, pattern)
    with tempfile.TemporaryDirectory(prefix="dosbox-find-") as scratch:
        dumped = dumping.dump_range(session, seg, off, length, Path(scratch) / "range.bin")
        data = dumped.path.read_bytes()
    # COUNTED WHOLE, KEPT AT THE TOP: a pattern that matches everywhere (a range of zeros)
    # would otherwise hold one number per byte to answer with the highest `HITS_MAX`.
    hits: collections.deque[int] = collections.deque(maxlen=judges.HITS_MAX)
    total = 0
    at = data.find(pattern)
    while at != -1:
        hits.append(off + at)
        total += 1
        at = data.find(pattern, at + 1)
    # THE SPAN EXAMINED RIDES ON THE REPLY, so a zero says over which bytes it is a zero.
    # The only range source here is the caller's own, so `source` is always `ref+length`.
    return {"seg_off": st.seg_off(seg, off), "length": length,
            "span": {"from": st.seg_off(seg, off), "length": length, "source": "ref+length"},
            "hits": [_spelled(seg, o, dumped.real_past_ffff) for o in hits],
            "hits_total": total, "truncated": total > judges.HITS_MAX}


def _spelled(seg: int, off: int, real_past_ffff: bool) -> str:
    """A hit as `SEG:OFF`. In real mode an offset past 0xFFFF names nothing (the debugger
    masks it to sixteen bits), so a hit there is spelled from its own paragraph."""
    if real_past_ffff and off >= dumping.WINDOW_BYTES:
        seg, off = dumping.real_address(dumping.real_linear(seg, off))
    return st.seg_off(seg, off)


# THE OUTPUT PANE IS A SCROLLBACK, NOT AN ANSWER. Every `command` delta is a repaint of the
# whole ncurses screen, and its Output pane still shows what EARLIER commands printed (measured:
# a `MEMFIND !` delta carried the previous `MEMS`'s "not active" line above its own). So a
# reply is read off the LAST line the pane holds that belongs to this family, never the first
# match in the text; a family line that is not the last one is somebody else's answer.
SCAN_LINES = (SCAN_OPENED, SCAN_MATCHES, SCAN_FINISHED, SCAN_RANGE,
              re.compile(re.escape(SCAN_ACTIVE)), re.compile(re.escape(SCAN_BAD_SEGMENT)),
              re.compile(re.escape(SCAN_NOT_ACTIVE)), re.compile(re.escape(SCAN_TOO_WIDE)),
              re.compile(re.escape(SCAN_CANCELLED)), re.compile(re.escape(SCAN_NONE_TO_CANCEL)),
              re.compile(re.escape(SCAN_NONE_TO_LIST)))
# The listing is PAGED by the debugger (`dcons.PAGER_MARK`), this many rows and then a prompt that
# any key continues (measured: a command typed while a page waited was eaten character by
# character, one page per keystroke, and the rows in between never crossed the screen). Its
# rows reach only the screen, so the pages are turned with a bare ENTER, one at a time, and
# the rows are read off each delta, where a listing read off the logfile leaves with `Q`.
SCAN_LISTED = re.compile(r"\[MEMFIND\] Matched values during current instance: ([0-9A-F]{6})")
SCAN_PAGE_ROWS = 20


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
                         "`scan_clear` it first, or keep filtering it with `scan_filter`")
    if SCAN_BAD_SEGMENT in line:
        raise ds.Invalid("bad_argument", f"the debugger refused the segment: {SCAN_BAD_SEGMENT}")
    if m := SCAN_RANGE.search(line):
        raise ds.Invalid("bad_argument",
            f"the range runs past the memory the debugger addresses "
                         f"({int(m.group(1), 16)} bytes); nothing was opened")
    if SCAN_NOT_ACTIVE in line:
        STATE.scan_forget()                 # whatever was counted belongs to a scan now gone
        raise ds.Invalid("needs_call",
            f"no search instance is open, so there is nothing to {what}: `scan_start` one")
    if SCAN_TOO_WIDE in line:
        raise ds.Invalid("bad_argument",
            "the value does not fit the instance's width: the debugger refused the filter")


# How many bare ENTERs a recovery will spend. The debugger pages a listing at
# `SCAN_PAGE_ROWS` rows, and a recovery that has to turn more pages than a whole listing
# holds is not recovering: it says so rather than typing for ever.
RECOVER_ENTERS_MAX = 8


def _clear_line(session: ds.Session) -> bool:
    """Leave the debugger's command line EMPTY and its paging finished, and say whether it
    got there.

    WHY THIS EXISTS. The debugger eats a command CHARACTER BY CHARACTER while a paged-content
    prompt waits, one page per keystroke (this module's own measured note, above). So a page
    left unturned swallows the front of the next command and strands its tail on the command
    line (`MEMS ` eaten, `=FF` left typed), and from there every later call
    concatenates onto the same line (`=FFMEMFIND !BPLISTBPLISTBPLIST`) instead of running.
    Nothing but `close` recovered.

    A bare ENTER is the one keystroke that is safe either way: it turns a waiting page, and
    at an IDLE prompt it submits whatever is typed there and clears it. That second half is
    the one this whole recovery rests on, so it was MEASURED against the probe guest rather
    than assumed: several bare ENTERs in a row at an idle prompt produced no output at all
    and did NOT repeat the last command (a convention some interactive debuggers do follow,
    which here would have re-issued a `MEMFIND` or a `MEMS` instead of clearing anything).
    The price of that silence is that the collect waits out its own bound with nothing to
    settle on, which a refusal path can afford and a hot path could not.

    It is spent until the screen stops showing a page mark, under a bound. A tail the ENTER
    submitted and the debugger did not take stays on the line, and a second ENTER would only
    run it again, so that line is emptied with `Session.clear_line`, which runs nothing."""
    for _ in range(RECOVER_ENTERS_MAX):
        try:
            out = session.command("")
            if dcons.PAGER_MARK not in out:
                if dcons.input_line(out):
                    # ESC REPAINTS NO PROMPT, only the cursor, and the line is empty after it
                    # (the next command is taken whole): a delta with no prompt is a clear.
                    out = session.clear_line()
                return not dcons.input_line(out)
        except ds.Invalid:
            return False
    return False


def _unexpected(session: ds.Session, out: str, wanted: str) -> ds.Invalid:
    """The refusal, with the command line LEFT CLEAN. Whatever the debugger showed, the line
    it showed it on is the caller's next command's line, and a refusal that hands back a
    dirty one costs the whole session."""
    recovered = _clear_line(session)
    return ds.Invalid("unexpected_answer",
        f"the debugger did not report {wanted}. What it showed: {out.strip()[-300:]!r}",
        line_recovered=recovered,
        note=("the debugger's command line was empty when checked after this"
              if recovered else
              "the debugger's command line was not confirmed empty: later commands may be "
              "eaten by a pager or typed onto what it holds, so `close` this session"))


def check_scan_range(length: int, cell_bytes: int) -> None:
    """A scan's range as the debugger takes it: a cell of a size it reads, and a length of whole
    cells within the six hex digits the debugger reads."""
    vocab.one_of("cell_bytes", cell_bytes, CELL_BYTES)
    if length <= 0:
        raise ds.Invalid("bad_argument", f"length={length} is not a byte count")
    if length > 0xFFFFFF:
        raise ds.Invalid("bad_argument",
            f"length={length} is more than the six hex digits the debugger takes")
    if length % cell_bytes:
        raise ds.Invalid("bad_argument",
            f"length={length} is not a whole number of {cell_bytes}-byte cells: the last "
            f"{length % cell_bytes} byte(s) would be no cell")


def unlisted_note() -> str:
    """Why a filter past the listing ceiling (`judges.HITS_MAX`) lists none: the debugger pages
    its listing a screen at a time, so listing them costs a console round trip per page, to show
    `limit` of them."""
    return (f"more than {judges.HITS_MAX} survive, and the debugger lists them a page at a "
            f"time: filter again to list them")


#: Why a filter with no `value` answers none: it compared each cell with the scan's opening.
NO_VALUE_WHY = "no `value` was given, so each cell was compared with its value at `scan_start`"


def check_filter(operator: str, value: int | None, limit: int = judges.HITS_DEFAULT) -> None:
    """A filter as the debugger takes it, judged with no machine: one of its operators, a
    value that is absent or a whole number of zero or more (it compares unsigned), and a
    `limit` of survivors to list, 1 to `HITS_MAX`."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= judges.HITS_MAX:
        raise ds.Invalid("bad_argument", f"limit={limit!r} is outside 1..{judges.HITS_MAX}, how "
                         f"many survivors a filter lists; above {judges.HITS_MAX}, filter again")
    vocab.one_of("operator", operator, OPERATORS)
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                              or value < 0):
        raise ds.Invalid("bad_argument",
            f"value={value!r} is not a whole number of zero or more; the debugger compares "
            f"unsigned")


def scan_start(session: ds.Session, seg: int, off: int, length: int,
               cell_bytes: int) -> dict[str, Any]:
    """Open the debugger's search instance over `length` bytes from `seg:off`, in cells of
    `cell_bytes` (1, 2 or 4). Every cell starts as a candidate."""
    check_scan_range(length, cell_bytes)
    letter, size = CELLS[cell_bytes], cell_bytes
    out = session.command(f"MEMFIND {seg:04X}:{off:X} {length:X} {letter}")
    last = _last_scan_line(out)
    _refuse(last, "open")
    opened = SCAN_OPENED.search(last)
    if opened is None:
        raise _unexpected(session, out, "a search instance")
    if int(opened.group(4), 16) != length:
        # IT OPENED ONE, just not this one: closed before the refusal, or the next `scan_start`
        # would be told a scan is open that this server does not hold.
        with contextlib.suppress(ds.Invalid):
            session.command("MEMFIND !")
        raise _unexpected(session, out,
            f"the range asked for: {length:#x} bytes were asked and it opened a search over "
            f"{int(opened.group(4), 16):#x}")
    STATE.scan_iterations = 0           # a scan this server opened: no filter yet
    STATE.scan_cell_bytes = size
    return {"seg_off": st.seg_off(seg, off), "length": length, "cell_bytes": size,
            "addr": st.flat(int(opened.group(3), 16)), "hits_total": length // size}


def _listing(session: ds.Session, survivors: int) -> list[dict[str, Any]]:
    """`MEMFIND L`, page by page, until the debugger's closing count; the rows are keyed by
    address so a line the terminal repainted twice counts once."""
    rows: dict[str, dict[str, Any]] = {}
    out = session.command("MEMFIND L")
    # THE FIRST PAGE STILL SHOWS THE PREVIOUS LISTING ABOVE IT when the scan was listed
    # before (the pane is a scrollback): only what comes after the filter's own summary
    # line, the newest non-row line, belongs to this listing.
    summaries = list(SCAN_MATCHES.finditer(out))
    if summaries:
        out = out[summaries[-1].end():]
    for _ in range(survivors // SCAN_PAGE_ROWS + 2):
        for s, o, lin, v in SCAN_ROW.findall(out):
            at = st.seg_off(int(s, 16), int(o, 16))
            rows[at] = {"seg_off": at, "addr": st.flat(int(lin, 16)), "value": int(v, 16)}
        closings = list(SCAN_LISTED.finditer(out))
        last_row = max((m.end() for m in SCAN_ROW.finditer(out)), default=-1)
        if closings and closings[-1].end() > last_row:
            listed = closings[-1]
            if int(listed.group(1), 16) != survivors or len(rows) != survivors:
                raise _unexpected(session, out,
                    f"a whole listing: it counted {survivors} survivors, closed the listing "
                    f"at {int(listed.group(1), 16)} and {len(rows)} rows crossed the screen")
            # THE CLOSING COUNT IS NOT THE END OF THE PAGING. A delta can carry the count
            # AND a paged-content prompt still waiting behind it, and returning there leaves
            # that prompt to eat the front of the caller's next command.
            if dcons.PAGER_MARK in out[listed.end():] and not _clear_line(session):
                # A CLEAR THAT DID NOT CLEAR IS NOT A SUCCESS. Handing the rows back with
                # the prompt still armed is the same defect, on the success path and silent:
                # the caller's next command would be eaten and the session lost.
                raise ds.Invalid("unexpected_answer",
                    "the listing ended with a paged-content prompt this could not turn in "
                    f"{RECOVER_ENTERS_MAX} ENTERs, so the debugger's command line is still "
                    "waiting: every later command would be eaten by it rather than run. "
                    "`close` this session",
                    line_recovered=False, survivors=survivors, rows=len(rows))
            return list(rows.values())
        if dcons.PAGER_MARK not in out:
            raise _unexpected(session, out, "the listing's next page nor its end")
        out = session.command("")
    raise _unexpected(session, out,
        f"the end of the listing within {survivors // SCAN_PAGE_ROWS + 2} pages")


def scan_filter(session: ds.Session, operator: str, value: int | None,
                limit: int = judges.HITS_DEFAULT) -> dict[str, Any]:
    """Keep the cells whose current content satisfies `operator` against `value`, or, with
    no value, against what each cell held when the scan was opened (measured: a cell changed
    once and then left alone keeps passing `!` filter after filter, and written back to its
    opening value it stops). The first `limit` survivors are listed with their current values
    (`truncated` when more survive), up to `HITS_MAX` survivors, past which the listing would
    cost a console page per screenful and none is listed; a step that leaves none CLOSES the
    instance, which is what the debugger does, and the reply says so.

    `iterations` is the debugger's own count, printed on every filter but the closing one,
    whose line carries none: the server keeps the last one it read (`STATE.scan_iterations`)
    and answers it plus one there, or unavailable with why when no count it can stand behind is
    held (the scan was opened, filtered or ended through `debug`, or the debugger said none
    was open)."""
    check_filter(operator, value, limit)
    cell = STATE.scan_cell_bytes
    if value is not None and cell is not None and value >= 1 << (8 * cell):
        raise ds.Invalid("bad_argument",
            f"value={value:#x} is wider than the open scan's {cell}-byte cell (at most "
            f"{(1 << (8 * cell)) - 1:#x}): nothing was typed")
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
        raise _unexpected(session, out, "survivors or a finished search")
    survivors = int(summary.group(1), 16)
    iterations = int(summary.group(2), 16)
    STATE.scan_iterations = iterations
    listable = survivors <= judges.HITS_MAX
    hits = [_shown(row, cell) for row in _listing(session, survivors)[:limit]] if listable else []
    return {"operator": operator, "value": _asked(value, cell), "iterations": iterations,
            "closed": False, "hits": hits, "hits_total": survivors,
            "truncated": survivors > len(hits),
            **({} if listable else {"note": unlisted_note()})}


def scan_clear(session: ds.Session) -> dict[str, Any]:
    """Cancel the debugger's search instance. Nothing open is a no-op that says so."""
    out = session.command("MEMFIND !")
    last = _last_scan_line(out)
    if SCAN_CANCELLED in last or SCAN_NONE_TO_CANCEL in last:
        STATE.scan_forget()
    if SCAN_CANCELLED in last:
        return {"cleared": True}
    if SCAN_NONE_TO_CANCEL in last:
        return {"cleared": False, "note": "no search instance was open"}
    raise _unexpected(session, out, "a cancelled instance nor that none was open")


def _cell_bits(cell: int | None) -> int:
    """The bits a value of the open scan's cell is shown at; a byte when the cell is unknown (a
    scan opened through `debug`), the narrowest a value of any cell takes."""
    return 8 * (cell or 1)


def _asked(value: int | None, cell: int | None) -> str | dict[str, Any]:
    """The `value` a filter compared with, `0x` at the cell's width, or why there is none."""
    return (contract.unavailable(NO_VALUE_WHY) if value is None
            else judges.hex_at_width(value, _cell_bits(cell)))


def _shown(row: dict[str, Any], cell: int | None) -> dict[str, Any]:
    """A survivor's row with its value `0x` at the cell's width."""
    return {**row, "value": judges.hex_at_width(int(row["value"]), _cell_bits(cell))}
