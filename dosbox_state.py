"""What the server HOLDS between calls, and the shape every reply takes.

One session, one machine: the live `Session`, the symbol table the last `symbols_load`
placed, the declaration store keyed by the conf, the last stop as its survey saw it, and
what was asked while the guest ran and still waits for the next stop. Every module of
this package reads and writes it through the one `STATE` instance below, so a test that
installs a fake session or a table does it in ONE place and every tool sees it.

The envelope lives here too (`reply`, `answer`), because it is built FROM this state:
every reply, INVALID ones included, carries the session block and the account of a queue
drained on the way to it. `delta` is the one screen-shaped helper, kept beside them
because it decides how a repaint crosses into a reply.

Nothing here talks to the emulator, with one exception: `stop_named`, `as_of_current` and
`list_basis` ASK the session whether the record describes the stop it is in, because a
record's date is only honest against the machine it dates.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from scry_core import cancel, judges, narrowing, screen_map
from scry_core import reply_contract as contract

import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_session as ds
import dosbox_symbols as sym

#: `last_stop` before the session's first stop, and the stop the machine is in while its survey
#: is not readable yet (a cut pane: the record still holds the stop before it).
NO_STOP_YET_WHY = "this session has not stopped yet"
UNREAD_STOP_WHY = ("the stop the machine is in was not readable yet (a cut pane; the next "
                   "contact retries)")

# ROWS OF ONE TABLE A REPLY SHOWS: a batch with `summaries` shows this many of
# its compact rows and names the files that hold every one.
ROWS_SHOWN = 24


def seg_off(seg: int, off: int) -> str:
    """ONE SPELLING FOR A SEGMENTED ADDRESS in every reply: `SSSS:OOOOOOOO`, the form every
    DOS ref takes and the debugger itself prints."""
    return dcons.seg_off(seg, off)


def flat(linear: int) -> str:
    """ONE SPELLING FOR A LINEAR ADDRESS in every reply: `0x` and eight digits, so the same
    place is one string and compares as one."""
    return f"{linear:#010x}"


def utc_now() -> datetime:
    """The one clock a declaration is stamped and aged by."""
    return datetime.now(UTC)


def now() -> str:
    return utc_now().isoformat(timespec="seconds")


def family(kind: str) -> str:
    """The two families an armed row belongs to: a breakpoint or an interrupt on one side,
    a watch on the other, since one ref can carry both."""
    return "watch" if kind == "watch" else "bp"


class State:
    """The one live session and everything the server remembers about it."""

    def __init__(self) -> None:
        self.session: ds.Session | None = None
        #: The session `start` launched and has not published yet (it waits for it, holding the
        #: lock): what an end by signal reaches when the lock is not let go of in time.
        self.starting: ds.Session | None = None

        # The symbol table the last `symbols_load` parsed, and the descriptor it was placed
        # against. They are held HERE rather than in the session because the full
        # untruncated names never go near the emulator: the debugger gets fifteen
        # characters and this keeps what the toolchain actually printed, which is what
        # `symbols_find` answers from.
        #
        # THEY ARE CLEARED WHENEVER THE SESSION CHANGES, and that is the load-bearing half.
        # A base is a property of ONE loaded process: keep the table across a `start` and
        # `symbols_find` goes on adding the old base to its offsets and hands back a linear
        # address for a program that is no longer running -- a confident wrong answer,
        # which this package treats as worse than a refusal.
        self.table: list[sym.Symbol] = []
        # BUMPED WHENEVER THE TABLE CHANGES, which is in place (`install_table` replaces the
        # list's contents): what a structure built over the table checks before reusing itself.
        self.table_generation = 0
        self.name_index: sym.NameIndex = {}      # the table by name, rebuilt with it
        # THE TYPE OF A SYMBOL, when a `types` file says: what `watch_add` reads with when
        # the caller names no format. Dropped with the table.
        self.symbol_types: dict[str, str] = {}
        # THE PER-SECTION BASES OF A SECTIONED LOAD, empty for a flat one. Cleared with the
        # table and for the same reason: a base belongs to ONE loaded process.
        self.section_bases: dict[int, int] = {}
        self.base: dict[str, int] = {}
        # THE REGISTER WHOSE SELECTOR THE TABLE'S BASE WAS MEASURED FROM (`symbols_load` with no
        # `base`), so a state load can have the next stop measure it again; None for a base
        # the caller gave, which nothing on the machine can contradict.
        self.base_measured_from: str | None = None

        # THE DECLARATION STORE for the conf the current session was started from, or None
        # before a session exists. Unlike the symbol table, it PERSISTS ACROSS SESSIONS
        # keyed by the conf's identity, so it is re-KEYED on `start` rather
        # than forgotten: a breakpoint declared by name is meant to survive a close/start
        # and re-resolve itself.
        self.store: dec.DeclarationStore | None = None
        # THE SESSION'S OWN STAMP, set by `start`, written into every declaration this
        # session makes as its `origin`: it tells a caller which session declared or last
        # adopted a row. Whether a raw address is re-armed is the build's to say, below.
        self.session_origin: str | None = None
        # THE CONF ALONE, the build before any map: what a raw row no batch describes is
        # stamped with, and how this session's comments of that kind are found when a batch
        # that describes them arrives.
        self.conf_fingerprint: str | None = None
        # EVERY BATCH LOADED SINCE THE LAST REPLACE, in load order
        # (`dosbox_placement.take_the_batch`): what a raw row is stamped with and judged by
        # (`dosbox_declarations.raw_staleness`). Dropped with the table.
        self.map_batches: list[dec.Build] = []
        self.start_seq = 0     # starts in this process, so two within one second differ
        # THE SCREEN MAPS, for the life of the server: the file layer a `map_load` read stays
        # across sessions, the session layer and the last identification go with a `start`.
        self.maps = screen_map.Maps()

        # THE LAST STOP, as its one survey saw it: position, registers, the debugger's
        # list, the attribution, and when. It is what the server can still say about the
        # machine while the guest runs and the console answers nothing (the running-guest
        # contract). Filled by every stop reply, cleared by
        # `start` and `close`. Empty means no stop yet in this session.
        self.last_stop: dict[str, Any] = {}
        # WHAT WAS ASKED WHILE THE GUEST RAN, to be applied at the next stop: the refs to arm
        # (a breakpoint or a change-watch declared while running), the debugger rows to remove
        # (a clear made while running), and the symbol bytes to load. The STORE already holds
        # the intent; this holds only what the console still owes. Drained by `apply_pending`
        # at the head of every stop reply, and cleared by `start`.
        self.pending: dict[str, Any] = {"arm": [], "disarm": [], "load": None,
                                        "remeasure": False, "dirty": False, "drained_seq": -1}
        # WHAT THIS SESSION ARMED, per ref: the debugger row it produced (`kind`
        # bp/int/watch, its seg:off or number, its `entry`). A clear made later removes
        # THAT row, whether or not the name still resolves: a symbol table reloaded in
        # between no longer knows the old name, and re-resolving it would leave the row
        # armed forever. Cleared by `start`.
        self.armed: dict[tuple[str, str], list[dict[str, Any]]] = {}
        # THE ACCOUNT OF A QUEUE DRAINED BY `live()`, handed to the next reply built and
        # then forgotten: the tool that found the machine stopped is the one whose reply
        # says what was applied, whatever that tool was.
        self.applied_last: dict[str, Any] = {}
        # The stop the guest reached on its own that the latest contact found, handed to
        # that contact's reply as `stopped_on_its_own` and then forgotten.
        self.found_stop_last: dict[str, Any] = {}
        # A CALL THE CLIENT CANCELLED has no reply of its own, so what it left rides on the next
        # reply that closes, whatever tool that is, and is then forgotten (`take_cancelled`).
        self.cancelled: cancel.Cancelled | None = None
        # Where the log ended at the LAST stop, so a stop's E9 block holds only what the
        # guest logged between then and now. Session-lived, reset on `start`.
        self.e9_offset = 0
        # WHERE A BATCH WITH `summaries` WRITES ITS TWO FILES, made on first use and kept for
        # the life of the process, so a path a reply handed back still opens after `close`;
        # the files are numbered per call by `batches`, so two calls never share one.
        self.scratch: Path | None = None
        self.batches = 0
        #: Every file a call of this session wrote and handed back, `(kind, path)` in order:
        #: what `captures` lists, re-read when it is asked.
        self.written: list[tuple[str, str]] = []
        # THE SESSION'S SCRATCH: where a picture or a series goes when the call names no
        # `dest`, made on first use and removed with the session (`clear_running_state`). A
        # path a reply places there is gone at `close`; a `dest` is what outlives the session.
        self.session_dir: Path | None = None
        # THE OPEN SCAN'S LAST `iterations`, as the debugger printed it: its closing line
        # prints none, so the closing reply is this plus one. None when no scan this server
        # opened or filtered is open.
        self.scan_iterations: int | None = None
        # THE OPEN SCAN'S CELL, in bytes, recorded when `scan_start` opens it: a filter value
        # wider than the cell is refused before `MEMS` is typed. None when no scan this server
        # opened is open.
        self.scan_cell_bytes: int | None = None
        # A RETRACE STOP STILL ARMED IN THE DEBUGGER: a `VRT` that a breakpoint stopped first
        # (or one still out when `run_for`'s bound interrupted it) stops the next release at the
        # next retrace. Kept by `run_for` frame by frame; consumed by the first stop a release that
        # ran on makes that no declaration explains (`dosbox_arming.attribute_stop`).
        self.retrace_pending = False
        # A CPU LOG A `trace` LEFT OPEN: an interrupt at its bound found no prompt, or a cancel
        # left it, so the next trace closes it before opening its own (`dosbox_trace`).
        self.log_open = False

    def take_cancelled(self) -> cancel.Cancelled | None:
        """The record a cancelled call left, handed once to the next reply that closes."""
        record, self.cancelled = self.cancelled, None
        return record

    def session_scratch(self) -> Path:
        """The session's scratch, made on first use (`session_dir` says when it goes)."""
        if self.session_dir is None:
            self.session_dir = Path(tempfile.mkdtemp(prefix="dosbox-x-session-"))
        return self.session_dir

    def batch_scratch(self) -> Path:
        """The directory a batch's files go to: this server's own, never the caller's `cwd`,
        which is the project."""
        if self.scratch is None:
            self.scratch = Path(tempfile.mkdtemp(prefix="dosbox-x-batches-"))
        # A long-lived process outlives what the OS temp cleaner leaves alone.
        self.scratch.mkdir(parents=True, exist_ok=True)
        return self.scratch

    # ------------------------------------------------------------------ the last stop

    def remember_stop(self, session: ds.Session, where: dict[str, str],
                      registers: dict[str, str], held: list[dict[str, str]],
                      attribution: dict[str, Any]) -> None:
        # The instruction decoded for the stop before is not this one's: a stop found on its
        # own decodes its own when a reply first names it (`recorded_stop_reply`).
        self.last_stop.pop("picture", None)
        self.last_stop.update(seq=int(self.last_stop.get("seq", 0)) + 1,
                              at=f"{where['cs']}:{where['eip']}", where=dict(where),
                              registers=dict(registers), held=[dict(r) for r in held],
                              attribution=dict(attribution), when=time.monotonic(),
                              clock=now(), stop_count=getattr(session, "stop_count", None),
                              paging=getattr(session, "paging", None))

    def as_of(self) -> dict[str, Any] | None:
        """The last stop as a dated reference for an answer given while the guest runs, or
        None when this session has not stopped yet."""
        if not self.last_stop:
            return None
        return {"stop_seq": self.last_stop["seq"], "pc": self.last_stop["at"],
                "cause": cause(self.last_stop["attribution"]),
                "since_s": round(time.monotonic() - float(self.last_stop["when"]), 1),
                "wall_at": self.last_stop["clock"]}

    def as_of_current(self, session: ds.Session) -> dict[str, Any] | None:
        """`as_of()` only when the record describes the stop the machine is IN. After a
        survey that refused (a cut pane) the record is still the PREVIOUS stop's, and naming
        its address as this one's would be a confident wrong answer of the right shape
        (an auditor's finding)."""
        stop = self.as_of()
        if stop is None or self.last_stop.get("stop_count") != getattr(session,
                                                                        "stop_count", None):
            return None
        return stop

    def dated(self) -> dict[str, Any]:
        """`as_of()` as a reply carries it: unavailable before the session's first stop."""
        stop = self.as_of()
        return stop if stop is not None else contract.unavailable(NO_STOP_YET_WHY)

    def current_or_why(self, session: ds.Session) -> dict[str, Any]:
        """`as_of_current()` as a reply carries it: unavailable when the stop the machine is
        in was not readable yet."""
        stop = self.as_of_current(session)
        return stop if stop is not None else contract.unavailable(UNREAD_STOP_WHY)

    def stop_named(self, session: ds.Session) -> tuple[dict[str, Any], str]:
        """The stop the machine is in, for a reply that names it: the current record and
        the words for its address and attribution, or the honest gap when it could not be
        read."""
        stop = self.as_of_current(session)
        if stop is None:
            return (contract.unavailable(UNREAD_STOP_WHY),
                    ", its position not readable yet (a cut pane; the next contact retries)")
        who = self.last_stop.get("attribution") or {}
        by = f" ({who['ref']})" if who.get("attributed") else ""
        return stop, f" at {stop['pc']}{by}"

    def list_basis(self, session: ds.Session) -> tuple[list[dict[str, str]], bool,
                                                       tuple[str, dict[str, str]] | None]:
        """What a listing reads the debugger's side from: the live list when the machine is
        stopped, else the last stop's, with the flag that says which and the machine reading
        to resolve symbols against (the last stop's, or nothing when there has been none). A
        running guest is known without asking its console, which would take the list unread."""
        try:
            if not session.at_debugger():
                raise ds.NotStopped("the guest is running")
            return session.breakpoints(), True, None
        except ds.NotStopped:      # a running guest; a cut listing on a STOPPED one refuses
            if not self.last_stop:
                return [], False, None
            return (list(self.last_stop["held"]), False,
                    (str(self.last_stop["where"]["mode"]), dict(self.last_stop["registers"])))

    def last_machine(self) -> tuple[str, dict[str, str]] | None:
        """The last stop's mode and registers, for resolving a name while the console cannot
        be asked; None when this session has not stopped yet."""
        if not self.last_stop:
            return None
        return str(self.last_stop["where"]["mode"]), dict(self.last_stop["registers"])

    # ------------------------------------------------------ what was armed, and pending

    def note_armed(self, ref: str, spec: dict[str, Any]) -> None:
        """Record a row this session armed for `ref`, under its family (a breakpoint or an
        interrupt on one side, a watch on the other, since one ref can carry both), as a
        LIST: a reload that moves a symbol arms a second row and the first must be
        remembered too, or a later clear leaves it behind as `foreign` forever. The last
        stop's snapshot of the debugger's list learns the row too, so a listing given while
        the guest runs is what the server did after that stop and not only what it saw at
        it."""
        rows = self.armed.setdefault((family(spec["kind"]), ref), [])
        if spec not in rows:
            rows.append(spec)
        self.snapshot_add(str(spec["entry"]))

    def snapshot_add(self, entry: str) -> None:
        held = self.last_stop.get("held")
        if held is not None and not any(r["entry"] == entry for r in held):
            held.append({"index": "?", "entry": entry})

    def snapshot_forget(self, entry: str) -> None:
        """Drop a row the server removed from the debugger from the last stop's snapshot, by
        the same match the lists use (target for a BP or a watch, text for an interrupt)."""
        held = self.last_stop.get("held")
        if held is None:
            return
        want = dcons.bp_row_target(entry)
        held[:] = [r for r in held
                   if not (r["entry"] == entry
                           or (want is not None and dcons.bp_row_target(r["entry"]) == want))]

    def queue_arm(self, ref: str) -> dict[str, Any]:
        """Put a declaration on the arm queue and say so: the guest runs, the console cannot
        take it now, the next stop will."""
        if ref not in self.pending["arm"]:
            self.pending["arm"].append(ref)
        self.pending["dirty"] = True
        return {"note": "the guest is running, so nothing can be armed now: it is stored "
                        "and will be armed at the next stop, whose reply says so in "
                        "`applied_on_stop`"}

    def pending_summary(self) -> dict[str, Any]:
        return {"arm": list(self.pending["arm"]), "disarm": len(self.pending["disarm"]),
                "symbols_load": self.pending["load"] is not None,
                "base_remeasure": bool(self.pending["remeasure"])}

    # ----------------------------------------------------------- the session's turnover

    def clear_running_state(self) -> None:
        """What a session's end takes with it: the last stop, the queue, the armed rows, any
        account not yet handed to a reply, and the session's scratch with its files. Called by
        `start`, `close` and a cancelled call that killed the session, so `status` never dates
        an answer by a stop of a session that is gone."""
        self.last_stop.clear()
        self.pending.update(arm=[], disarm=[], load=None, remeasure=False, dirty=False,
                            drained_seq=-1)
        self.armed.clear()
        self.applied_last.clear()
        self.found_stop_last = {}
        self.e9_offset = 0    # the next session's log starts empty
        self.written.clear()                      # its files are the next session's to list
        self.scan_forget()                        # the debugger's scan dies with it
        self.retrace_pending = False              # and so does its armed retrace
        self.log_open = False                     # and its CPU log
        if self.session_dir is not None:          # and the pictures and series it made
            shutil.rmtree(self.session_dir, ignore_errors=True)
            self.session_dir = None

    def scan_forget(self) -> None:
        """No scan this server can speak for is open: what it counted and the cell it opened are
        dropped together, wherever the scan ended or was taken out of its hands."""
        self.scan_iterations = None
        self.scan_cell_bytes = None

    def install_table(self, symbols: list[sym.Symbol], accumulate: bool = False) -> None:
        """THE ONE WAY A TABLE ARRIVES, so the index by name can never describe a
        different table: both are replaced here, together, and nowhere else.

        `accumulate` KEEPS WHAT AN EARLIER LOAD PLACED, which is what the debugger's own
        `LV` does (it appends, and `loaded` counts its whole holding). The two halves have
        to agree: with `LV` appending while this table is replaced, a second load with a
        narrower `pattern` drops an earlier symbol out of `symbols_find` and orphans the
        breakpoint armed on it. A name loaded AGAIN takes the new row: a
        relinked program moves, and the freshest placement is the one the debugger holds.

        THE KEY IS THE EXACT NAME, because that is what the index and every lookup use
        (`index_by_name` buckets on `s.name` and keeps duplicates as a LIST, and a real
        population carries hundreds of names shared by several symbols). Folding case here
        would collapse two symbols the rest of the package treats as different, and dropping
        a whole same-named family for one reloaded member would shrink the very table this
        accumulation exists to protect."""
        fresh = {s.name for s in symbols}
        kept = ([s for s in self.table if s.name not in fresh] if accumulate else [])
        self.table[:] = kept + symbols
        self.table_generation += 1
        self.name_index.clear()
        self.name_index.update(sym.index_by_name(self.table))

    def machine_replaced(self) -> None:
        """A state was loaded: the program's selectors are the restored machine's, so the next
        stop measures the table's base again (`dosbox_arming.apply_pending`) when the load
        measured it off the machine. The table itself is kept: the program is the same."""
        if self.table and self.base_measured_from is not None:
            self.pending["remeasure"] = self.pending["dirty"] = True

    def forget_symbols(self) -> None:
        """Drop the table and the base. Called wherever the session stops being the one
        they were measured against. The declaration STORE is NOT dropped here: it is keyed
        by the conf and persists, and is re-keyed in `start`."""
        self.table.clear()
        self.table_generation += 1
        self.name_index.clear()
        self.symbol_types.clear()
        self.section_bases.clear()
        self.base.clear()
        self.base_measured_from = None
        self.map_batches = []

    def origin(self) -> str:
        """One stamp per `start`: the clock, this process, and a counter, so two sessions of
        one process inside the same second, and two processes over one conf, never share
        one (a shared origin would make the previous session's raw addresses look like this
        one's)."""
        self.start_seq += 1
        return f"{now()}#{os.getpid()}.{self.start_seq}"


STATE = State()


@atexit.register
def remove_scratch() -> None:
    """THE PROCESS'S SCRATCH GOES WITH THE PROCESS: the batches' directory lives as long as the
    server does, and a session never closed (its client gone) has nobody else to take its
    pictures away."""
    for folder in (STATE.session_dir, STATE.scratch):
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)


# ------------------------------------------------------------------------- the envelope


def reply(status: str = "ok", **fields: Any) -> dict[str, Any]:
    """Every reply's body, including an INVALID one's, passed through the contract's guard: an
    INVALID with no `code` of the table, no `message`, or a retired spelling (`reason`) is a
    programmer's error here and never a reply. The `session` block is added once, by the call
    boundary after the body (`session_block`)."""
    out: dict[str, Any] = {"status": status}
    # A REFUSAL READS ITS CODE AND ITS MESSAGE FIRST, whatever account it carries after them.
    out.update({k: fields.pop(k) for k in ("code", "message") if k in fields})
    out.update(fields)
    # A NOTE APPEARS ONLY WHEN SOMETHING IS SAID: a body that had nothing to say passes None or
    # an empty one.
    if "note" in out and not out["note"]:
        del out["note"]
    if STATE.applied_last and "applied_on_stop" not in out:
        out["applied_on_stop"] = dict(STATE.applied_last)
    STATE.applied_last.clear()
    # A STOP THE GUEST REACHED ON ITS OWN is said by the contact that found it and then
    # forgotten, so a caller driving a run with `status` alone learns of it from that reply.
    if STATE.found_stop_last and "stopped_on_its_own" not in out:
        out["stopped_on_its_own"] = dict(STATE.found_stop_last)
    STATE.found_stop_last = {}
    return contract.check_envelope(out)


#: The `session` block of a reply given with no session: nothing runs, nothing was written.
NO_SESSION_BLOCK: dict[str, Any] = {"alive": False, "running": False, "altered": False}


#: The facts of the block that are alarms while they hold, each with the test that says so: a conf
#: changed under the session (or unreadable), terminal bytes dropped, a reader that died.
_ALARM_WHEN: dict[str, Callable[[Any], bool]] = {
    "conf_changed_on_disk": lambda v: v is not False,
    "terminal_bytes_dropped": lambda v: bool(v),
    "drain_alive": lambda v: v is False,
    "drain_ended": lambda v: True,
}
#: What every reply carries whatever it holds.
_ALWAYS = ("alive", "running", "altered")


def session_block(whole: bool = False) -> dict[str, Any]:
    """The `session` block every reply closes with, read off the session as it is now: alive,
    running, altered and each alarm while it holds, and the same three keys saying nothing runs
    when there is none. Nothing in it is fixed for the session, so `whole` changes nothing: the
    process's facts ride at the top of `start`, `status` and `close` (`process_facts`)."""
    if STATE.session is None:
        return dict(NO_SESSION_BLOCK)
    return {key: value for key, value in STATE.session.state().items()
            if key in _ALWAYS or (key in _ALARM_WHEN and _ALARM_WHEN[key](value))}


def process_facts() -> dict[str, Any]:
    """What the process a session runs is (`pid`, the conf and its digest, the bound and what is
    spent, the terminal's reader, the captures, the state directory), at the top of `start`,
    `status` and `close`: asked for, so never on every reply. Nothing with no session."""
    if STATE.session is None:
        return {}
    return {key: value for key, value in STATE.session.state().items() if key not in _ALWAYS}


def extend(built: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """Fields added to a reply body already built. A body carries no `session` (the boundary
    closes every reply with it) but `close`'s, the state before the close, which stays last."""
    tail = built.pop("session", None)
    built.update(fields)
    if tail is not None:
        built["session"] = tail
    return built


def answer(fields: dict[str, object]) -> dict[str, Any]:
    """A session method's OWN answer, handed back whole under the standard envelope.

    It exists so the three debugging tools cannot quietly reshape what the session
    concluded. Each of those answers is a set of fields that only mean anything
    together -- `completed` beside `running`, a `verdict` beside `breakpoint_removed` --
    and a tool that picked fields out by hand is a second place for that set to be
    decided, which is where one of them goes missing.

    The `cast` is the price of `dosbox_session` using no `Any` anywhere: its methods
    answer `dict[str, object]`, and `reply` takes a `status` that must be a string. It
    is confined to this one line rather than repeated at three call sites.
    """
    return reply(**cast(dict[str, Any], fields))


#: The tail of the console text `debug` hands back, and the shorter one `detail=True` adds to an
#: advance or an interrupt arming, whose parsed fields are the answer.
DEBUG_TEXT_KEEP = 4000
DETAIL_TEXT_KEEP = 2000


def delta(out: str, keep: int) -> dict[str, Any]:
    """A screen slice that SAYS it is one.

    A repaint of a full ncurses screen is unbounded and the conversation is not, so
    the tools that hand back raw screen text keep only the tail of it. That is a slice
    by POSITION, a sample rather than a result, and undeclared a caller could not tell a
    whole delta from a clipped one: both would arrive as `screen_delta` under `status: ok`.

    THE CAPS ARE HEADROOM ON A STOPPED MACHINE, measured per tool: `HELP` is the longest
    listing this debugger prints and it fits under `debug`'s cap, and a quiet guest's F5
    repaint fits under `resume`'s. On a RUNNING guest the F5 delta is bounded by the
    collect's settle over a scrolling Output pane rather than by a repaint's size, so a
    chatty guest reaches that cap and `clipped` says so. Each figure belongs to the tool
    and the machine STATE it was taken in: a `BPLIST` repaint's size says nothing about
    what `resume` sees, and a delta read on a running machine, whose console swallows
    the command, is the guest's own chatter and not the listing at all.

    The narrow readers (`registers`, `read_memory`, `memdump`) reduce by MEANING and
    do not come through here; this is for the tools whose answer the server cannot
    know the shape of.
    """
    # A CAP OF ZERO OR LESS WOULD DECLARE A CLIP THAT DID NOT HAPPEN: `out[-0:]` is the
    # WHOLE string, so the reply would hand back everything while saying it is a tail.
    #
    # IT IS A `ValueError` AND NOT AN `Invalid`. `keep` is never a caller's: the three
    # call sites pass literals, so a bad one is a bug in THIS module. `Invalid` is the
    # category reserved for "the question could not be answered", and `tool()` turns it
    # into a caller-facing INVALID -- so
    # raising it here would dress a server bug as a statement about the caller's
    # request, which is verbatim what the rule "a real bug dressed up as
    # INVALID" exists to forbid. A bug escapes as a bug.
    if keep <= 0:
        raise ValueError(f"a cap of {keep} is not a cap: it would return the whole "
                         f"screen while reporting itself clipped")
    return {"screen_delta": out[-keep:], "screen_chars": len(out),
            "clipped": len(out) > keep}


#: What `delta` adds to a reply, which a reply without the repaint names as left out.
REPAINT_FIELDS = ("screen_delta", "screen_chars", "clipped")
#: How a reply without the debugger's repaint asks for it.
REPAINT_HOW = "detail=True adds the debugger's repaint for this command"


def delta_if_asked(out: str, keep: int, detail: bool) -> dict[str, Any]:
    """`delta` with `detail`; without it, the note that the repaint was left out. A tool whose
    answer is parsed off the screen gives the raw text only when asked: the parsed fields are
    the answer, and the repaint is most of the reply's size."""
    return delta(out, keep) if detail else narrowing.omission(list(REPAINT_FIELDS), REPAINT_HOW)


#: A stop's address inside its `cause`, the part that varies from one stop to the next.
_CAUSE_AT = re.compile(r" at [0-9A-Fa-f]{4}:[0-9A-Fa-f]{4,8}")


def cause(attribution: dict[str, Any]) -> str:
    """What stopped the machine, in the words every stop reply carries as `cause`: the
    declaration a stop is at, with how it was named and where, or why none can be named."""
    # A stop whose address the record lacks is still named; only its place is left out.
    at = attribution.get("at", "an address the record lacks")
    if not attribution.get("attributed"):
        if attribution.get("retrace_pending"):
            return (f"most likely the retrace stop a `run_for` left armed: no declared code "
                    f"breakpoint at {at}")
        return (f"no declared code breakpoint at {at}: the debugger keeps no hit flag and a memory "
                f"watch stops at the instruction that wrote, so which declaration fired cannot "
                f"be told")
    if attribution.get("by") == "stop":
        return f"the `stop` call at {at}"
    if attribution.get("by") == "cancel":
        return f"a cancelled call's stop at {at}"
    if attribution.get("by") == "run_to":
        also = list(attribution.get("refs", []))
        return (f"run_to's target {attribution['ref']} at {at}"
                + (f", where breakpoint {', '.join(also)} is declared too" if also else ""))
    refs = attribution.get("refs")
    if refs:
        return f"breakpoints {', '.join(refs)} at {at}, every declaration at that address named"
    return f"breakpoint {attribution['ref']} (by {attribution['by']}) at {at}"


def cause_key(text: str) -> str:
    """`cause` with its address taken off: the key a count of stops by declaration uses."""
    return _CAUSE_AT.sub("", text)


def shown_regs(registers: dict[str, str]) -> dict[str, str]:
    """The register pane as a reply shows it: each value `0x` and its digits at the width the
    pane prints it, the spelling a value argument takes back (`judges.number`)."""
    return {name: judges.hex_at_width(int(digits, 16), 4 * len(digits))
            for name, digits in registers.items()}
