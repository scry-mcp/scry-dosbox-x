"""`trace`: the machine run a counted number of instructions with the debugger's CPU log on.

The log writes one line per instruction with the state BEFORE it runs, and its last line is the
instruction it stops at, logged and not executed: `n` executed are asked as `n + 1` lines.

The line count is an instruction count only on an interpreting core; a dynamic core writes one
entry per translated block. The server cannot read which core runs, so every trace proves its
count against the cycle count `RUNSTATE` prints before the release and at the stop.
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

from scry_core import file_names
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab

from scry_dosbox_x import binary as binaries
from scry_dosbox_x import collect as dcollect
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import grammar, machine, paths, placement, running
from scry_dosbox_x import run_state as rs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

T = TypeVar("T")

SHAPE_WORDS = ("normal", "short", "long", "cs_ip")
SHAPES = dict(zip(SHAPE_WORDS, ds.LOG_WORDS, strict=True))
LOG_FILE = "LOGCPU.TXT"
#: Sized from the heaviest shape: a file under a gibibyte, wall time under half the wait ceiling.
INSTRUCTIONS_MAX = 3_000_000
CLOSE_WAIT_S = 10.0
LINE_QUOTED_CHARS = 120
READ_CHUNK_BYTES = 1 << 20
TAIL_BYTES = 64
#: `RUNSTATE` prints the core's `cycle_count`, a `Bitu`: 64 bits on a 64-bit build.
CYCLES_WRAP = 1 << 64
SYMBOLS_SHOWN = 64
#: Descriptor types with the S and executable bits set.
CODE_TYPES = range(0x18, 0x20)
LINEAR_MASK = 0xFFFFFFFF
NO_LINEAR = "no linear address"
#: What the debugger prints, refusing the `LOG`, when it cannot create its log.
NOT_CREATED_LINE = "DEBUG: Logfile couldn't be created."

DYNAMIC_CORE = (f"a dynamic core writes one entry per translated block, and "
                f"{dbg.NORMAL_CORE_CYCLES}; trace on the normal core, "
                f"`start(flags=[\"-set\", \"cpu core=normal\"])`")
MACHINE_CLOSES = "a BIOS power-on self test closes the log"
AT_ITS_START = ("the machine stopped where the trace began without executing anything: the log "
                "writes its line before the breakpoints are checked, so a code breakpoint at "
                "that address stops it there again, and so does an interrupt breakpoint, which "
                "stops at its INT before running it; clearing it traces past it")


def check_arguments(instructions: object, shape: object) -> None:
    """Judge `instructions` and `shape` before the session is asked for."""
    if isinstance(instructions, bool) or not isinstance(instructions, int) \
            or not 1 <= instructions <= INSTRUCTIONS_MAX:
        raise ds.Invalid("bad_argument",
            f"instructions={instructions!r} is not a whole number from 1 to {INSTRUCTIONS_MAX}: "
            f"how many instructions the trace executes")
    vocab.one_of("shape", shape, SHAPE_WORDS)


def set_path(path: Path) -> Path:
    """Where a trace's set file goes: beside it, named from the whole trace file name, so two
    traces that differ only by extension keep two set files. The set file is a name the server
    makes up, so the file-name rule normalises it even when `path` is a `dest` the caller wrote
    with capitals and underscores."""
    parts = (path.stem, path.suffix[1:]) if path.suffix else (path.name,)
    return path.with_name(file_names.name(*(file_names.word(part, "dest") for part in parts),
                                          "set", extension="jsonl"))


def log_places(cwd: Path) -> list[Path]:
    """Where the debugger writes its log: the working directory, either spelling."""
    return [cwd / LOG_FILE, cwd / LOG_FILE.lower()]


def target(session: ds.Session, dest: Path | None) -> Path:
    """`dest`, judged, or the first free `trace-<n>.trace` in the captures directory."""
    if dest is not None:
        path = paths.fresh_named_dest("dest", dest)
        cwd = session.launch.cwd
        dcollect.judge_collection(path, cwd, log_places(cwd), "trace")
    else:
        # A name picked here is never one the debugger writes, so a captures directory that is
        # the working directory still takes the trace.
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
    """How far the cycle count moved, across its wrap."""
    return (after - before) % CYCLES_WRAP


# ------------------------------------------------------------------------------- the parse

Address = tuple[str, str, bool | None]


@dataclass
class Parsed:
    """Line count and the count per executed address (every line but the last). An address is
    `(cs, eip, flat)`; `flat` is True in real or virtual-8086 mode, None where the shape does
    not say."""

    line_count: int = 0
    executed: Counter[Address] = field(default_factory=Counter)
    last: Address | None = None


# Read by head and tail, never by column: the disassembly between them is free-width text.
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
    """Read `path` in `shape`; a line no pattern reads is refused naming its number."""
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
    """Lines in the file, an unterminated last one included."""
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
    """`instructions` executed with the `shape` log on, within `seconds`. A refusal before the
    release leaves the machine and the filesystem as they were."""
    path = target(session, dest)
    session.require_stopped("a trace")
    # The session's own build, never the PATH's: with the binary ladder they can differ.
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
    # Judged before anything is sent, the close of a left-open log included.
    if not os.access(cwd, os.W_OK | os.X_OK):
        raise ds.Invalid("no_channel",
            f"{cwd} is not writable, and the debugger opens its log there: nothing was sent. "
            f"`start` with a working directory the emulator can write")
    places = log_places(cwd)
    dcollect.refuse_leftover(places, "trace")
    if STATE.log_open:
        _close_log(session, places, "the log an earlier trace left open")
    session.require_run_state("a trace")
    armed_at, _ = session.where_and_registers()
    rs.read_run_state(session)              # the cycle count the trace proves itself against
    before = session.cycles
    if before is None:
        raise ds.Invalid("unexpected_answer",
            "`RUNSTATE` gave no cycle count before the trace, so the count it proves itself "
            "against cannot be read; nothing was run")
    asked = instructions + 1
    began = time.monotonic()
    # Open from the release until something proves it closed; else the next trace's own `LOG`
    # lands on the open stream and what it runs is written nowhere.
    STATE.log_open = True
    try:
        expired, _ = session.log_cpu(SHAPES[shape], asked, began, began + seconds, progress)
    except ds.Invalid as e:
        if NOT_CREATED_LINE not in str(e):
            raise
        STATE.log_open = False
        raise ds.Invalid("host_failed",
            f"the debugger could not create {LOG_FILE} in {cwd} (it answered "
            f"`{NOT_CREATED_LINE}`), so nothing ran; to trace, `start` with a working directory "
            f"the emulator can write") from None
    if expired:
        # The bound interrupts; what the log holds is collected as a cut stop, a TIMEOUT.
        try:
            expired = ds.Session.stop_at_bound(session)   # False: it came to rest on its own
        except ds.Invalid as e:
            raise ds.Invalid(e.code,
                f"{e}. The debugger's log is still open at {places[0]}: the next trace refuses "
                f"while that file sits there, and once it is moved closes the log before "
                f"opening its own", trace={"path": str(places[0]), "closed": False}) from None
    return _collected(session, shape, asked, path, places, before,
                      grammar.real_segments(armed_at["mode"]), interrupted=expired)


def _collected(session: ds.Session, shape: str, asked: int, path: Path, places: list[Path],
               before: int, armed_real: bool,
               *, interrupted: bool = False) -> dict[str, Any]:
    """With the machine stopped: move the log, close it if a stop cut it, prove its count."""
    source = _written(places)
    if source is None:
        raise _no_log(session)
    lines = _host(lambda: count_lines(source), source)
    if lines > asked:
        raise ds.Invalid("unexpected_answer",
            f"{source} holds {lines} lines for {asked} asked: it is not this log",
            trace={"path": str(source)})
    ran_out = lines == asked
    if ran_out:
        STATE.log_open = False
    # Moved before the close, which cannot tell an open log from a closed one: on a log the
    # machine already closed, `LOGC 0` opens a fresh file, and that file is how it shows.
    cut_what = f"a stop cut the trace, and its log (moved to {path})"
    cut_extra = {"trace": {"path": str(path), "closed": False}}
    released: list[bool] = []

    def release() -> None:
        # Held open, so the machine had not closed it: no fresh file to judge.
        _send_close(session, cut_what, **cut_extra)
        released.append(True)
    collected = dcollect.collect(source, path, "trace", release=None if ran_out else release)
    closed_early = False
    if not ran_out and not released:
        closed_early = _close_log(session, places, cut_what, **cut_extra)
    kept = {"path": str(collected), "bytes": collected.stat().st_size, "shape": shape}
    try:
        reply = running.stop_reply(session, retrace_may_stop=not ran_out)
    except ds.Invalid as exc:
        raise ds.Invalid("unexpected_answer",
            f"the stop the trace ended at could not be surveyed ({exc}), so its count cannot be "
            f"proved; the log is at {collected}", trace=kept,
            **running.placement_of(exc)) from None
    stop = {"stop_seq": reply.get("stop_seq"), "pc": reply["pc"], "cpu_mode": reply["cpu_mode"],
            **({"symbols_placed": reply["symbols_placed"]} if "symbols_placed" in reply else {})}
    if closed_early:
        raise ds.Invalid("readback_refused",
            f"the machine closed the debugger's log before the trace stopped ({MACHINE_CLOSES}), "
            f"so the {lines} lines at {collected} are not what ran",
            trace=kept, **stop)
    if lines == 0:
        raise ds.Invalid("readback_refused",
            f"the log at {collected} holds no line: nothing was traced", trace=kept, **stop)
    executed = lines - 1
    after = session.cycles
    if after is None:
        raise ds.Invalid("unexpected_answer",
            f"`RUNSTATE` gave no cycle count at the stop, so the {executed} instructions the log "
            f"says executed cannot be proved; the log is at {collected}", trace=kept, **stop)
    moved = cycles_moved(before, after)
    # An interrupt breakpoint stops inside its INT, counted but not run: a cut run may read one
    # more than executed.
    if moved != executed and (ran_out or moved != executed + 1):
        raise ds.Invalid("no_channel",
            f"the cycle count moved by {moved} while the log holds {executed} entries, so the "
            f"log is not a count of executed instructions ({DYNAMIC_CORE}). The log is at "
            f"{collected}", trace=kept, **stop)
    parsed = _host(lambda: parse(collected, shape), collected)
    notes = [AT_ITS_START] if executed == 0 else []
    coverage = join(session, parsed, armed_real, notes)
    rows = sorted(coverage.rows, key=_set_order)
    written = _write_set(set_path(collected), rows, notes)
    found: dict[str, Any] = {
        **kept, "instructions": executed, "addresses": len(parsed.executed),
        "unplaced": sum(1 for r in rows if "symbol" not in r),
        "set_path": contract.or_unavailable(written, "the set file could not be written: "
                                                     "`note` says why"),
        "symbols": coverage.symbols[:SYMBOLS_SHOWN],
        "symbols_total": len(coverage.symbols),
        "truncated": len(coverage.symbols) > SYMBOLS_SHOWN}
    if notes:
        found["note"] = "; ".join(notes)
    verdict = (contract.ELAPSED if ran_out else
               contract.TIMEOUT if interrupted else contract.OTHER_STOP)
    return st.extend(reply, verdict=verdict, trace=found)


# --------------------------------------------------------------------------------- the join

@dataclass
class Coverage:
    """One set-file row per address, one row per routine."""

    rows: list[dict[str, Any]]
    symbols: list[dict[str, Any]]


def join(session: ds.Session, parsed: Parsed, armed_real: bool, notes: list[str]) -> Coverage:
    """Each executed address as a linear one where its mode allows, plus the nearest symbol
    (REFERENCE.md, Advancing the machine, has the rule)."""
    stop_real = grammar.real_segments(STATE.last_stop["where"]["mode"])
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
        row: dict[str, Any] = {"seg_off": st.seg_off(int(cs, 16), offset)}
        if base is not None:
            linear = (base + offset) & LINEAR_MASK
            row["addr"] = st.flat(linear)
            symbol = (placement.nearest_symbol(linear)
                      if span is not None and span[0] <= linear <= span[1] else None)
            if symbol is not None:
                row.update(symbol=symbol["name"], delta=symbol["delta"])
                _count(routines, symbol, linear, count)
        row["count"] = count
        rows.append(row)
    symbols = sorted(routines.values(), key=lambda r: (r["addr"], r["symbol"]))
    for r in symbols:
        r["first"], r["last"] = st.flat(r["first"]), st.flat(r["last"])
    return Coverage(rows, symbols)


def _count(routines: dict[tuple[str, int], dict[str, Any]], symbol: dict[str, Any],
           linear: int, count: int) -> None:
    key = (str(symbol["name"]), int(symbol["addr"], 16))
    row = routines.setdefault(key, {"symbol": key[0], "addr": st.flat(key[1]), "addresses": 0,
                                    "instructions": 0, "first": linear, "last": linear})
    row["addresses"] += 1
    row["instructions"] += count
    row["first"], row["last"] = min(row["first"], linear), max(row["last"], linear)


def _set_order(row: dict[str, Any]) -> tuple[bool, str, str]:
    return ("addr" not in row, str(row.get("addr", "")), str(row["seg_off"]))


def _selector_bases(session: ds.Session, selectors: set[str],
                    notes: list[str]) -> dict[str, int | None]:
    """Base of each qualifying selector from one `GDT`/`LDT` listing; None for the rest."""
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
    """Write the set file; one failed part-way is removed, one that already existed is left
    alone. The trace stands without it."""
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
    """`read()`, with a host failure refused naming the file."""
    try:
        return read()
    except OSError as exc:
        raise ds.Invalid("host_failed", f"{path} could not be read: {exc!r}",
                         trace={"path": str(path)}) from None


def _no_log(session: ds.Session) -> ds.Invalid:
    """The refusal for a stop with no log: the log may still be open."""
    return ds.Invalid("unexpected_answer",
        f"the trace stopped and no {LOG_FILE} is in {session.launch.cwd}: something removed it "
        f"while the log was open, so the log is still open and the next trace closes it before "
        f"its own")


def _written(places: list[Path]) -> Path | None:
    return next((p for p in places if p.exists()), None)


def _close_log(session: ds.Session, places: list[Path], what: str, **extra: Any) -> bool:
    """`LOGC 0` on a log that may be open, executing nothing. Returns whether the machine had
    already closed it (the empty file the close then makes is removed). Refused naming `what`
    when the close does not answer."""
    _send_close(session, what, **extra)
    return _remove_fresh(places)


def _send_close(session: ds.Session, what: str, **extra: Any) -> None:
    began = time.monotonic()
    expired, _ = session.log_cpu("LOGC", 0, began, began + CLOSE_WAIT_S)
    if expired:
        raise ds.Invalid("readback_refused",
            f"{what} did not answer its close within {CLOSE_WAIT_S:g} s, so the log may still be "
            f"open and the machine may be running. `close` ends the emulator and the log with it",
            **extra)
    STATE.log_open = False


def close_log_left_open(session: ds.Session) -> None:
    """Close a CPU log a cancelled call left open. What it wrote is first moved to the first
    free `trace-cancelled-<n>.trace` in the captures directory (else the working directory)."""
    cwd = session.launch.cwd
    captures = session.launch.captures_dir
    home = captures if captures is not None and captures.is_dir() else cwd
    places = log_places(cwd)
    source = _written(places)
    what = "the CPU log a cancelled call left open"
    released: list[bool] = []

    def release() -> None:
        _send_close(session, what)
        released.append(True)
    if source is not None:
        aside = next(home / f"trace-cancelled-{n}.trace" for n in itertools.count(1)
                     if not paths.taken(home / f"trace-cancelled-{n}.trace"))
        dcollect.collect(source, aside, "trace", release=release)
    if not released:
        _close_log(session, places, what)


def _remove_fresh(places: list[Path]) -> bool:
    fresh = _written(places)
    if fresh is None:
        return False
    if fresh.stat().st_size == 0:
        fresh.unlink()
    return True

