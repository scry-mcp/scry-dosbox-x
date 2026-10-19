"""`trace`: the machine run a counted number of instructions with the debugger's CPU log on.

The `LOG` family (one word per line shape) opens `LOGCPU.TXT` in the emulator's working
directory, releases the guest, and writes one line per instruction with the state BEFORE it
runs. The count it takes is hex, and the last line it writes is the instruction it stops at,
logged and not executed: so `n` executed instructions are asked as `n + 1` lines. A stop that
comes first (a breakpoint, a watch, an interrupt breakpoint) leaves the log open. The file moves
first, to the caller's `dest` or to the session's captures directory, and `LOGC 0` then closes
the log without executing anything (`_collected` says why in that order).

THE LINE COUNT IS AN INSTRUCTION COUNT ONLY ON THE NORMAL CORE, where the pane's `cc=` moves by
one per instruction; a dynamic core logs at the boundaries of the blocks it translated and its
`cc=` stays put. This server cannot read which core runs, so every trace proves its own count
against `cc=`. A proved log is then joined to the loaded symbols (`join`), and its executed
addresses written beside it, one JSON line each.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import dosbox_binary as binaries
import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_machine as machine
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

T = TypeVar("T")

#: The four shapes, by the debugger's word for each, in its own order.
SHAPES = dict(zip(("normal", "short", "long", "cs_ip"), ds.LOG_WORDS, strict=True))
#: The file the debugger writes, in the emulator's working directory.
LOG_FILE = "LOGCPU.TXT"
#: The most instructions one call executes, chosen from the heaviest shape's measured cost so
#: that one call's file stays under a gibibyte and its wall time under half the wait ceiling.
INSTRUCTIONS_MAX = 3_000_000
#: How long the close of a log is given: it executes nothing.
CLOSE_WAIT_S = 10.0
#: How many characters of a refused line its refusal quotes.
LINE_QUOTED_CHARS = 120
#: How much of a file one read takes: the log and the session's logfile can be long.
READ_CHUNK_BYTES = 1 << 20
#: How much of a line's end its tail pattern is searched in: past the registers' free width.
TAIL_BYTES = 64
#: `cc=` is painted as a 32-bit unsigned number, so a run that crosses its wrap reads lower.
CYCLES_WRAP = 1 << 32
#: How many per-routine rows the reply carries; the rest are counted, and every address is in
#: the set file.
SYMBOLS_SHOWN = 64
#: The set file beside a trace: one JSON line per executed address.
SET_SUFFIX = ".set.jsonl"
#: A code segment's descriptor types as the listing prints them (the S bit and the executable
#: bit set): conforming or not, readable or not, accessed or not.
CODE_TYPES = range(0x18, 0x20)
#: A linear address is 32 bits: a base and an offset that sum past it wrap, as the cpu's do.
LINEAR_MASK = 0xFFFFFFFF
#: The words a note carries when a line was given no linear address.
NO_LINEAR = "no linear address"
#: The line the debugger writes to the session's logfile when the machine closes its log under it
#: (a BIOS power-on self test does); a log that ends at its count or at `LOGC 0` writes
#: `... created` instead.
MACHINE_CLOSED_LINE = f"DEBUG: cpu log {LOG_FILE} stopped"
#: The line the debugger writes to the session's logfile when it cannot create its log. It then
#: runs nothing and answers `command not recognized`, which leaves that command on its input line
#: (REFERENCE.md, The console).
NOT_CREATED_LINE = "DEBUG: Logfile couldn't be created."
E9_BY_LOG = "this tool takes no `e9`: `log(pattern=\".\", channel=\"guest\")` reads the lines"

DYNAMIC_CORE = ("on a dynamic core the debugger logs at block boundaries: trace on the normal "
                "core, `start(flags=[\"-set\", \"cpu core=normal\"])`")
#: Who closes the log under a running machine, in the words every reply that meets it uses.
MACHINE_CLOSES = "a BIOS power-on self test closes the log"
AT_ITS_START = ("the machine stopped where the trace began without executing anything: the log "
                "writes its line before the breakpoints are checked, so a code breakpoint at "
                "that address stops it there again, and so does an interrupt breakpoint, which "
                "stops at its INT before running it; clearing it traces past it")


def check_arguments(instructions: object, shape: object) -> None:
    """The two values only this tool takes, judged before the session is asked for."""
    if isinstance(instructions, bool) or not isinstance(instructions, int) \
            or not 1 <= instructions <= INSTRUCTIONS_MAX:
        raise ds.Invalid("bad_argument",
            f"instructions={instructions!r} is not a whole number from 1 to {INSTRUCTIONS_MAX}: "
            f"how many instructions the trace executes")
    if not isinstance(shape, str) or shape not in SHAPES:
        raise ds.Invalid("bad_argument", f"shape={shape!r} is not one of {', '.join(SHAPES)}")


def set_path(path: Path) -> Path:
    """Where a trace's set file goes: beside it."""
    return path.with_name(path.name + SET_SUFFIX)


def log_places(cwd: Path) -> list[Path]:
    """Where the debugger writes its log: the working directory, either spelling."""
    return [cwd / LOG_FILE, cwd / LOG_FILE.lower()]


def target(session: ds.Session, dest: Path | None) -> Path:
    """Where the file ends: `dest`, judged, or the first `trace-<n>.trace` free in the
    session's captures directory. Refused when there is nowhere to write it."""
    if dest is not None:
        path = paths.fresh_dest("dest", dest)
        cwd = session.launch.cwd
        dcollect.judge_collection(path, cwd, log_places(cwd), "trace")
    else:
        # A NAME PICKED HERE IS NEVER ONE THE DEBUGGER WRITES, so the rule on where a caller's
        # name may point does not bind it: a captures directory that is the working directory
        # still takes the trace.
        captures = session.launch.captures_dir
        if captures is None:
            raise ds.Invalid("bad_argument",
                "no `dest` was given and this session was started with no captures directory "
                "to put the trace in: name a `dest`, or `start(captures_dir=)`")
        if not captures.is_dir():
            raise ds.Invalid("bad_argument",
                f"no `dest` was given and the session's captures directory {captures} is not "
                f"there: name a `dest`, or make that directory")
        n = 1
        while paths.taken(captures / f"trace-{n}.trace") or paths.taken(
                set_path(captures / f"trace-{n}.trace")):
            n += 1
        path = captures / f"trace-{n}.trace"
    paths.fresh_dest("the trace's set file", set_path(path))
    return path


def cycles_moved(before: int, after: int) -> int:
    """How far the pane's counter moved, across its wrap: a trace is far shorter than one."""
    return (after - before) % CYCLES_WRAP


# ------------------------------------------------------------------------------- the parse

Address = tuple[str, str, bool | None]


@dataclass
class Parsed:
    """One file read whole: how many lines, and each EXECUTED line's address counted, which is
    every line but the last (the instruction the trace stopped at). An address is
    `(cs, eip, flat)`, `eip` as the file prints it and `flat` a `long` line's own mode: True in
    real or virtual-8086 mode (CS x 16 + EIP is the address), None where the shape does not say."""

    line_count: int = 0
    executed: Counter[Address] = field(default_factory=Counter)
    last: Address | None = None


# EACH SHAPE IS READ BY ITS HEAD AND ITS TAIL, never by a column: the disassembly between them is
# free text whose width moves with the instruction. `short` prints EIP with at least four digits
# and no padding above that.
_HEAD = {
    "cs_ip": re.compile(rb"([0-9A-F]{4}):([0-9A-F]{8})\Z"),
    "short": re.compile(rb"([0-9A-F]{4}):([0-9A-F]{4,8})  "),
    "normal": re.compile(rb"([0-9A-F]{4}):([0-9A-F]{8})  "),
    "long": re.compile(rb"[0-9]+\.[0-9]{6} ([0-9A-F]{4}):([0-9A-F]{8})  "),
}
_TAIL = {
    "short": re.compile(rb" I[01]\Z"),
    "normal": re.compile(rb" IF:[01]\Z"),
    "long": re.compile(rb" VM:([01]) .*CR0:([0-9A-F]{8})\Z"),
}


def parse(path: Path, shape: str) -> Parsed:
    """The file at `path` read line by line in `shape`; a line no pattern reads is refused
    naming its number, the file left where it is."""
    head, tail = _HEAD[shape], _TAIL.get(shape)
    out = Parsed()
    with path.open("rb") as f:
        for raw in f:
            line = raw.rstrip(b"\r\n")
            out.line_count += 1
            m = head.match(line)
            t = tail.search(line[-TAIL_BYTES:]) if tail is not None else None
            if m is None or (tail is not None and t is None):
                raise ds.Invalid("unexpected_answer",
                    f"line {out.line_count} of {path} is not a `{shape}` line of the debugger's "
                    f"CPU log: {line[:LINE_QUOTED_CHARS].decode('latin-1')!r}",
                    trace={"path": str(path)})
            flat = None
            if shape == "long" and t is not None:
                flat = t.group(1) == b"1" or not int(t.group(2), 16) & 1
            address = (m.group(1).decode(), m.group(2).decode(), flat)
            if out.last is not None:
                out.executed[out.last] += 1
            out.last = address
    return out


def count_lines(path: Path) -> int:
    """Lines in the file, a last one without its newline counted too."""
    lines = 0
    tail = b""
    with path.open("rb") as f:
        while chunk := f.read(READ_CHUNK_BYTES):
            lines += chunk.count(b"\n")
            tail = chunk[-1:]
    return lines + (1 if tail not in (b"", b"\n") else 0)


# ------------------------------------------------------------------------------- the run

def trace(session: ds.Session, instructions: int, shape: str, dest: Path | None, seconds: float,
          progress: ds.Progress) -> dict[str, Any]:
    """`instructions` executed with the `shape` log on, within `seconds`, as the reply `trace`
    publishes. A refusal before the release leaves the machine where it was and no file of its
    own behind."""
    path = target(session, dest)
    ds.console_listening(session, "a trace")
    # THE SESSION'S OWN BUILD, never the PATH's: with the binary ladder they can differ. `which`
    # keeps an absolute one as it is and finds a hand-built `Launch`'s bare name on the PATH.
    binary = shutil.which(session.launch.binary)
    if binary is None:
        raise ds.Invalid("host_failed",
            f"the session's emulator `{session.launch.binary}` is not an executable file any "
            f"more, so its build cannot be read")
    if not binaries.heavy_debug(binary):
        raise ds.Invalid("no_channel",
            f"`{binary}` was built without the debugger's CPU log (only a heavy-debug build "
            f"compiles the `LOG` family), so there is nothing to trace with; `build_check` says "
            f"`heavy_debug`")
    cwd = session.launch.cwd
    # JUDGED BEFORE ANYTHING IS TYPED, the close of a log left open included (NOT_CREATED_LINE).
    if not os.access(cwd, os.W_OK | os.X_OK):
        raise ds.Invalid("no_channel",
            f"{cwd} is not writable, and the debugger opens its log there: nothing was typed. "
            f"`start` with a working directory the emulator can write")
    places = log_places(cwd)
    dcollect.refuse_leftover(places, "trace")
    if STATE.log_open:
        _close_log(session, places, "the log an earlier trace left open")
    armed_at, _ = session.where_and_registers()
    before = session.pane_cycles
    if before is None:
        raise ds.Invalid("unexpected_answer",
            "the pane painted no `cc=` on the survey before the trace, so the count it proves "
            "itself against cannot be read; nothing was run")
    asked = instructions + 1
    logfile = session.launch.logfile
    says = _logfile_reader(session)
    began = time.monotonic()
    # THE LOG IS OPEN FROM THE RELEASE UNTIL SOMETHING PROVES IT CLOSED: its count running out, a
    # close that answered, or the logfile saying the machine closed it. Whatever leaves this call
    # before then leaves the next trace to close it, or that trace's own `LOG` lands on the open
    # stream and what it runs is written nowhere.
    STATE.log_open = True
    expired, saw_at = session.log_cpu(SHAPES[shape], asked, began, began + seconds, progress)
    if expired:
        # No headless stopper calls a log back before its count. The debugger opens its log by
        # the first spelling; the second is only ever somebody's leftover.
        where = places[0]
        if says(MACHINE_CLOSED_LINE):
            STATE.log_open = False
            raise ds.Invalid("wait_expired",
                f"the machine closed the debugger's log before its count ran out (the logfile "
                f"says `{MACHINE_CLOSED_LINE}`; {MACHINE_CLOSES}) and runs on, so the count "
                f"will not stop it: a declared breakpoint still can, `stop` can, and "
                f"`close` ends it. {where} is yours to move, and its lines are not what ran",
                running=True, trace={"path": str(where), "closed": True})
        seen = ("the session's logfile does not say it happened" if logfile is not None else
                "with no `logfile`, where the debugger would say so, the two cannot be told "
                "apart here")
        raise ds.Invalid("wait_expired",
            f"the trace did not stop within {seconds:g} s, so the machine is still running. A "
            f"log that runs to its count stops the machine there (`status` then records the "
            f"stop) and the next trace closes it; one the machine closed first ({MACHINE_CLOSES}, "
            f"so a trace from the reset park meets it) never reaches its count, and {seen}. "
            f"{where} is yours to move",
            running=True, trace={"path": str(where), "closed": False})
    return _collected(session, shape, asked, path, places, before, saw_at,
                      armed_at["mode"] == dcons.REAL_MODE, says)


def _collected(session: ds.Session, shape: str, asked: int, path: Path, places: list[Path],
               before: int, saw_at: float, armed_real: bool,
               says: Callable[[str], bool]) -> dict[str, Any]:
    """The machine is stopped: the log moved, closed if a stop cut it, and its count proved."""
    source = _written(places)
    if source is None:
        raise _no_log(session, says)
    lines = _host(lambda: count_lines(source), source)
    if lines > asked:
        raise ds.Invalid("unexpected_answer",
            f"{source} holds {lines} lines for {asked} asked: it is not this log",
            trace={"path": str(source)})
    ran_out = lines == asked
    if ran_out:
        STATE.log_open = False
    # MOVED BEFORE THE CLOSE, because the close cannot tell an open log from a closed one: on a
    # log the machine already closed (a BIOS power-on self test closes it) `LOGC 0` opens a fresh
    # file over this name, and a file it creates in the working directory is how that shows.
    collected = dcollect.collect(source, path, "trace")
    closed_early = False
    if not ran_out:
        closed_early = _close_log(session, places,
                                  f"a stop cut the trace, and its log (moved to {collected})",
                                  trace={"path": str(collected), "closed": False})
    kept = {"path": str(collected), "bytes": collected.stat().st_size, "shape": shape}
    try:
        reply = running.stop_reply(session, retrace_may_stop=not ran_out, e9_how=E9_BY_LOG)
    except ds.Invalid as exc:
        raise ds.Invalid("unexpected_answer",
            f"the stop the trace ended at could not be surveyed ({exc}), so its count cannot be "
            f"proved; the log is at {collected}", trace=kept) from None
    stop = {"stop_seq": reply.get("stop_seq"), "stopped_at": dict(STATE.last_stop["where"])}
    if closed_early:
        raise ds.Invalid("readback_refused",
            f"the machine closed the debugger's log before the trace stopped ({MACHINE_CLOSES}), "
            f"so the {lines} lines at {collected} are not what ran",
            trace=kept, **stop)
    if lines == 0:
        raise ds.Invalid("readback_refused",
            f"the log at {collected} holds no line: nothing was traced", trace=kept, **stop)
    executed = lines - 1
    after = session.pane_cycles
    if after is None:
        raise ds.Invalid("unexpected_answer",
            f"the pane painted no `cc=` at the stop, so the {executed} instructions the log says "
            f"executed cannot be proved; the log is at {collected}", trace=kept, **stop)
    moved = cycles_moved(before, after)
    # AN INTERRUPT BREAKPOINT STOPS INSIDE ITS INT, after the counter took it and before it ran,
    # so a cut run may count one instruction more than it executed; a count that ran out may not.
    if moved != executed and (ran_out or moved != executed + 1):
        raise ds.Invalid("no_channel",
            f"the pane's `cc=` moved by {moved} while the log says {executed} instructions "
            f"executed: {DYNAMIC_CORE}. The log is at {collected}", trace=kept, **stop)
    parsed = _host(lambda: parse(collected, shape), collected)
    notes = [AT_ITS_START] if executed == 0 else []
    coverage = join(session, parsed, armed_real, notes)
    rows = sorted(coverage.rows, key=_set_order)
    written = _write_set(set_path(collected), rows, notes)
    found: dict[str, Any] = {
        **kept, "instructions": executed, "addresses": len(parsed.executed),
        "unplaced": sum(1 for r in rows if "symbol" not in r),
        "set_path": written, "symbols": coverage.symbols[:SYMBOLS_SHOWN],
        "symbols_total": len(coverage.symbols),
        "symbols_truncated": len(coverage.symbols) > SYMBOLS_SHOWN}
    if notes:
        found["note"] = "; ".join(notes)
    return st.extend(reply, verdict="ELAPSED" if ran_out else "OTHER_STOP",
                     stopped_at=stop["stopped_at"],
                     waited_s=saw_at, trace=found)


# --------------------------------------------------------------------------------- the join

@dataclass
class Coverage:
    """The executed addresses placed: one set-file row per address, one row per routine."""

    rows: list[dict[str, Any]]
    symbols: list[dict[str, Any]]


def join(session: ds.Session, parsed: Parsed, armed_real: bool, notes: list[str]) -> Coverage:
    """Each executed address as a linear one where its mode allows, and inside the loaded
    table's span the nearest symbol: a `long` line by its own mode, any other by the mode of the
    window's two ends (REFERENCE.md, Advancing the machine, says the rule and its limits)."""
    stop_real = STATE.last_stop["where"]["mode"] == dcons.REAL_MODE
    window_flat = armed_real and stop_real
    flat_of = {a: (a[2] if a[2] is not None else window_flat) for a in parsed.executed}
    bases: dict[str, int | None] = {}
    if not all(flat_of.values()):
        bases = _selector_bases(session, {a[0] for a, flat in flat_of.items() if not flat},
                                notes)
    span = placement.symbol_span()
    if span is None:
        notes.append("no symbol table is loaded: `symbols_load` names the routines")
    rows: list[dict[str, Any]] = []
    routines: dict[tuple[str, int], dict[str, Any]] = {}
    for (cs, eip, line_flat), count in parsed.executed.items():
        offset = int(eip, 16)
        base = int(cs, 16) * machine.PARAGRAPH_BYTES if flat_of[(cs, eip, line_flat)] \
            else bases.get(cs)
        row: dict[str, Any] = {"addr": f"{cs}:{eip}"}
        if base is not None:
            linear = (base + offset) & LINEAR_MASK
            row["linear"] = f"{linear:08X}"
            symbol = (placement.nearest_symbol(linear)
                      if span is not None and span[0] <= linear <= span[1] else None)
            if symbol is not None:
                row.update(symbol=symbol["name"], delta=symbol["delta"])
                _count(routines, symbol, linear, count)
        row["count"] = count
        rows.append(row)
    symbols = sorted(routines.values(), key=lambda r: (r["linear"], r["symbol"]))
    for r in symbols:
        r["first"], r["last"] = f"{r['first']:08X}", f"{r['last']:08X}"
    return Coverage(rows, symbols)


def _count(routines: dict[tuple[str, int], dict[str, Any]], symbol: dict[str, Any],
           linear: int, count: int) -> None:
    key = (str(symbol["name"]), int(symbol["linear"]))
    row = routines.setdefault(key, {"symbol": key[0], "linear": f"{key[1]:08X}", "addresses": 0,
                                    "instructions": 0, "first": linear, "last": linear})
    row["addresses"] += 1
    row["instructions"] += count
    row["first"], row["last"] = min(row["first"], linear), max(row["last"], linear)


def _set_order(row: dict[str, Any]) -> tuple[bool, str, str]:
    return ("linear" not in row, str(row.get("linear", "")), str(row["addr"]))


def _selector_bases(session: ds.Session, selectors: set[str],
                    notes: list[str]) -> dict[str, int | None]:
    """The base of each selector that qualifies, read off one `GDT` and `LDT` listing at the
    stop; None for one that does not."""
    if session.launch.logfile is None:
        notes.append(f"the protected-mode lines have {NO_LINEAR}: the descriptor tables are "
                     f"read off the session's logfile, so `start` with `logfile`")
        return {}
    try:
        found = machine.read(session, frozenset({"gdt", "ldt"})).found
    except ds.Invalid as exc:
        notes.append(f"the protected-mode lines have {NO_LINEAR}: the descriptor tables could "
                     f"not be read ({exc})")
        return {}
    out: dict[str, int | None] = {}
    for cs in selectors:
        sel = int(cs, 16)
        row = machine.descriptor(found, sel)
        ours = (row is not None and row.get("p") == 1 and int(row["type"], 16) in CODE_TYPES
                and row.get("dpl") == sel & machine.SELECTOR_RPL_MASK)
        out[cs] = int(row["base"], 16) if ours and row is not None else None
    if any(base is None for base in out.values()):
        notes.append(f"some lines have {NO_LINEAR}: their CS names no present code "
                     f"descriptor of its own privilege at the stop, as a stretch outside "
                     f"protected mode would")
    return out


def _write_set(path: Path, rows: list[dict[str, Any]], notes: list[str]) -> str | None:
    """The set file, line by line; one the host refuses part-way is removed, never left looking
    whole, and one somebody made while the trace ran is theirs and left alone. Either way the
    trace stands without it."""
    refused = f"the set file {path} could not be written"
    try:
        f = path.open("x", encoding="utf-8")
    except OSError as exc:
        notes.append(f"{refused}: {exc!r}")
        return None
    try:
        with f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
    except OSError as exc:
        path.unlink(missing_ok=True)
        notes.append(f"{refused}: {exc!r}")
        return None
    return str(path)


def _host(read: Callable[[], T], path: Path) -> T:
    """A read of the log the host may fail, refused naming the file rather than escaping."""
    try:
        return read()
    except OSError as exc:
        raise ds.Invalid("host_failed", f"{path} could not be read: {exc!r}",
                         trace={"path": str(path)}) from None


def _no_log(session: ds.Session, says: Callable[[str], bool]) -> ds.Invalid:
    """The refusal for a stop with no log in the working directory. It clears `STATE.log_open`
    only when the logfile says the debugger was refused the file, so no log opened; otherwise
    something may have removed the file while the log was open, and the log stays remembered."""
    cwd = session.launch.cwd
    if says(NOT_CREATED_LINE):
        STATE.log_open = False
        return ds.Invalid("host_failed",
            f"the debugger could not create {LOG_FILE} in {cwd} (the logfile says "
            f"`{NOT_CREATED_LINE}`), so nothing ran. It answered `command not recognized`, and "
            f"every command typed after that fails as well: `close`, then `start` with a working "
            f"directory the emulator can write")
    seen = ("the session's logfile does not say it was refused" if session.launch.logfile
            is not None else "with no `logfile`, where the debugger says when it is refused the "
            "file, the two cannot be told apart")
    return ds.Invalid("unexpected_answer",
        f"the trace stopped and no {LOG_FILE} is in {cwd}: the debugger was refused the file, "
        f"or something removed it while the log was open, and {seen}. Refused, its console "
        f"fails every command after it and `close` is the way out; removed, the log is still "
        f"open and the next trace closes it before its own")


def _logfile_reader(session: ds.Session) -> Callable[[str], bool]:
    """A reader of whether the session's logfile holds a line of the debugger's written from now
    on; it answers False without a logfile, where nothing can be read."""
    logfile = session.launch.logfile
    if logfile is None:
        return lambda _line: False
    mark = session.e9_mark()
    return lambda line: _logfile_says(logfile, mark, line)


def _logfile_says(logfile: Path, mark: int, line: str) -> bool:
    """Whether the session's logfile, past byte `mark`, holds the debugger's `line` at the start
    of a line (a guest's own lines carry their channel's prefix). One the host cannot read says
    nothing, which the caller reports as not seen."""
    needle = b"\n" + line.encode()
    carry = b"\n"
    try:
        with logfile.open("rb") as f:
            f.seek(mark)
            while chunk := f.read(READ_CHUNK_BYTES):
                seen = carry + chunk
                if needle in seen:
                    return True
                carry = seen[-(len(needle) - 1):]
    except OSError:
        return False
    return False


def _written(places: list[Path]) -> Path | None:
    return next((p for p in places if p.exists()), None)


def _close_log(session: ds.Session, places: list[Path], what: str, **extra: Any) -> bool:
    """`LOGC 0` on a log that may still be open: it closes it, executing nothing, and the flag
    clears. Whether the machine had already closed it: the close then writes an empty file,
    which this call made and removes. Refused naming `what` when the close does not answer."""
    began = time.monotonic()
    expired, _ = session.log_cpu("LOGC", 0, began, began + CLOSE_WAIT_S)
    if expired:
        raise ds.Invalid("readback_refused",
            f"{what} did not answer its close within {CLOSE_WAIT_S:g} s, so the log may still be "
            f"open and the machine may be running. `close` ends the emulator and the log with it",
            **extra)
    STATE.log_open = False
    return _remove_fresh(places)


def close_log_left_open(session: ds.Session) -> None:
    """A CPU log a cancelled call left open, closed by its `stop` end with the guest at the
    debugger, so the next trace starts on a closed log. What it wrote is moved aside first, to
    the first free `trace-cancelled-<n>.trace` in the working directory: on a log the machine
    already closed, `LOGC 0` opens a fresh file over its name."""
    cwd = session.launch.cwd
    places = log_places(cwd)
    source = _written(places)
    if source is not None:
        aside = next(cwd / f"trace-cancelled-{n}.trace" for n in itertools.count(1)
                     if not paths.taken(cwd / f"trace-cancelled-{n}.trace"))
        dcollect.collect(source, aside, "trace")
    _close_log(session, places, "the CPU log a cancelled call left open")


def _remove_fresh(places: list[Path]) -> bool:
    fresh = _written(places)
    if fresh is None:
        return False
    if fresh.stat().st_size == 0:
        fresh.unlink()
    return True

