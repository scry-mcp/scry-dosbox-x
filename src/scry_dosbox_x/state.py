"""What the server holds between calls (the one `STATE`) and the shape every reply takes.

Only `stop_named`, `as_of_current` and `list_basis` ask the session anything.
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
from typing import TYPE_CHECKING, Any, cast

from scry_core import cancel, judges, narrowing, regpoint, screen_map
from scry_core import reply_contract as contract

from scry_dosbox_x import declarations as dec
from scry_dosbox_x import grammar
from scry_dosbox_x import program as dprogram
from scry_dosbox_x import session as ds
from scry_dosbox_x import symbols as sym

if TYPE_CHECKING:
    from scry_dosbox_x import start_symbols

NO_STOP_YET_WHY = "this session has not stopped yet"
UNREAD_STOP_WHY = ("the stop the machine is in was not readable yet (its survey failed; the "
                   "next contact retries)")

ROWS_SHOWN = 24


def seg_off(seg: int, off: int) -> str:
    return grammar.seg_off(seg, off)


def flat(linear: int) -> str:
    return f"{linear:#010x}"


def utc_now() -> datetime:
    return datetime.now(UTC)


def now() -> str:
    return utc_now().isoformat(timespec="seconds")


def family(kind: str) -> str:
    """A breakpoint or an interrupt is `bp`, a watch is `watch`: one ref can carry both."""
    return "watch" if kind == "watch" else "bp"


class State:
    def __init__(self) -> None:
        self.session: ds.Session | None = None
        #: Launched by `start`, not yet published: what a signal reaches meanwhile.
        self.starting: ds.Session | None = None

        # Cleared whenever the session changes: a base belongs to ONE loaded process, and a
        # stale one yields a confident wrong address.
        self.table: list[sym.Symbol] = []
        self.table_generation = 0
        self.name_index: sym.NameIndex = {}
        self.symbol_types: dict[str, str] = {}
        self.section_bases: dict[int, int] = {}
        self.base: dict[str, int] = {}
        # None for a caller-given base, which nothing on the machine can contradict.
        self.base_measured_from: str | None = None

        # Persists across sessions, keyed by the conf.
        self.store: dec.DeclarationStore | None = None
        self.session_origin: str | None = None
        self.conf_fingerprint: str | None = None
        self.map_batches: list[dec.Build] = []
        self.start_seq = 0
        # The file layer outlasts sessions; the session layer does not.
        self.maps = screen_map.Maps()
        # `start(symbols=)`'s table until its program is in memory (`start_symbols`).
        self.start_symbols: start_symbols.Held | None = None

        # What the server can still say while the guest runs. Empty: no stop yet.
        self.last_stop: dict[str, Any] = {}
        # Owed to the debugger at the next stop (`apply_pending`); the store holds the intent.
        self.pending: dict[str, Any] = {"arm": [], "disarm": [], "load": None,
                                        "remeasure": False, "dirty": False, "drained_seq": -1}
        # A clear removes THAT row even when the name no longer resolves after a table reload.
        self.armed: dict[tuple[str, str], list[dict[str, Any]]] = {}
        # The count and capture watches' taps this session's debugger holds, by ref
        # (`taps.Tap`); a tap lives as long as the emulator.
        self.taps: dict[str, Any] = {}
        # The freeze watches' pinned bytes this session's debugger holds, by ref
        # (`freezes.Freeze`).
        self.freezes: dict[str, Any] = {}
        # The DOS call trace `start(dos_calls=True)` turned on (`dos_calls.Trace`).
        self.dos_calls: Any = None
        # The files `start(guest_files=)` fingerprinted, kept past `close` for its reply
        # (`guest_files.Print` by path).
        self.guest_files: dict[Path, Any] = {}
        self.applied_last: dict[str, Any] = {}
        self.found_stop_last: dict[str, Any] = {}
        self.cancelled: cancel.Cancelled | None = None
        self.e9_offset = 0
        # Process-lived, so a path handed back still opens after `close`.
        self.scratch: Path | None = None
        self.batches = 0
        self.written: list[tuple[str, str]] = []
        self.session_dir: Path | None = None
        # The closing line of a scan prints no `iterations`: the reply is this plus one.
        self.scan_iterations: int | None = None
        self.scan_cell_bytes: int | None = None
        # An armed `VRT` stops the next release at the next retrace.
        self.retrace_pending = False
        self.log_open = False

    def take_cancelled(self) -> cancel.Cancelled | None:
        record, self.cancelled = self.cancelled, None
        return record

    def session_scratch(self) -> Path:
        if self.session_dir is None:
            self.session_dir = Path(tempfile.mkdtemp(prefix="dosbox-x-session-"))
        return self.session_dir

    def batch_scratch(self) -> Path:
        """Where a batch's files go: never the caller's `cwd`."""
        if self.scratch is None:
            self.scratch = Path(tempfile.mkdtemp(prefix="dosbox-x-batches-"))
        self.scratch.mkdir(parents=True, exist_ok=True)
        return self.scratch

    def remember_stop(self, session: ds.Session, where: dict[str, str],
                      registers: dict[str, str], held: list[dict[str, str]],
                      attribution: dict[str, Any]) -> None:
        # The previous stop's decoded instruction and frame are not this one's
        # (`recorded_stop_reply`); `stop_reply` reads this stop's frame after it.
        self.last_stop.pop("picture", None)
        self.last_stop.pop("frame", None)
        self.last_stop.update(seq=int(self.last_stop.get("seq", 0)) + 1,
                              at=f"{where['cs']}:{where['eip']}", where=dict(where),
                              registers=dict(registers), held=[dict(r) for r in held],
                              attribution=dict(attribution), when=time.monotonic(),
                              clock=now(), stop_count=session.stop_count,
                              paging=session.paging)

    def as_of(self) -> dict[str, Any] | None:
        """The last stop as a dated reference, or None before the first stop."""
        if not self.last_stop:
            return None
        return {"stop_seq": self.last_stop["seq"], "pc": self.last_stop["at"],
                "cause": cause(self.last_stop["attribution"]),
                "since_s": round(time.monotonic() - float(self.last_stop["when"]), 1),
                "wall_at": self.last_stop["clock"]}

    def as_of_current(self, session: ds.Session) -> dict[str, Any] | None:
        """`as_of()` only when the record is of the stop the machine is IN."""
        stop = self.as_of()
        if stop is None or self.last_stop.get("stop_count") != session.stop_count:
            return None
        return stop

    def dated(self) -> dict[str, Any]:
        """`as_of()` as a reply carries it."""
        stop = self.as_of()
        return stop if stop is not None else contract.unavailable(NO_STOP_YET_WHY)

    def current_or_why(self, session: ds.Session) -> dict[str, Any]:
        """`as_of_current()` as a reply carries it."""
        stop = self.as_of_current(session)
        return stop if stop is not None else contract.unavailable(UNREAD_STOP_WHY)

    def stop_named(self, session: ds.Session) -> tuple[dict[str, Any], str]:
        """The current stop and the words for its address and attribution, or the gap."""
        stop = self.as_of_current(session)
        if stop is None:
            return (contract.unavailable(UNREAD_STOP_WHY),
                    ", its position not readable yet (its survey failed; the next contact "
                    "retries)")
        who = self.last_stop.get("attribution") or {}
        by = f" ({who['ref']})" if who.get("attributed") else ""
        return stop, f" at {stop['pc']}{by}"

    def list_basis(self, session: ds.Session) -> tuple[list[dict[str, str]], bool,
                                                       tuple[str, dict[str, str]] | None]:
        """The debugger's list: live when stopped, else the last stop's (flag says which)."""
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
        """The last stop's mode and registers, for resolving names while the machine runs."""
        if not self.last_stop:
            return None
        return str(self.last_stop["where"]["mode"]), dict(self.last_stop["registers"])

    def note_armed(self, ref: str, spec: dict[str, Any]) -> None:
        """Record a row armed for `ref` as a LIST: a reload that moves a symbol arms a second
        row, and the first must not be left behind as `foreign` after a clear."""
        rows = self.armed.setdefault((family(spec["kind"]), ref), [])
        if spec not in rows:
            rows.append(spec)
        self.snapshot_add(str(spec["entry"]))

    def snapshot_add(self, entry: str) -> None:
        held = self.last_stop.get("held")
        if held is not None and not any(r["entry"] == entry for r in held):
            held.append({"index": "?", "entry": entry})

    def snapshot_forget(self, entry: str) -> None:
        """Drop a removed row from the snapshot, matching as the lists do."""
        held = self.last_stop.get("held")
        if held is None:
            return
        want = grammar.bp_row_target(entry)
        held[:] = [r for r in held
                   if not (r["entry"] == entry
                           or (want is not None and grammar.bp_row_target(r["entry"]) == want))]

    def queue_arm(self, ref: str) -> dict[str, Any]:
        """Queue a declaration for the next stop and say so."""
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

    def clear_running_state(self) -> None:
        """What a session's end takes with it."""
        self.last_stop.clear()
        self.pending.update(arm=[], disarm=[], load=None, remeasure=False, dirty=False,
                            drained_seq=-1)
        self.armed.clear()
        self.taps.clear()
        self.freezes.clear()
        self.dos_calls = None
        self.applied_last.clear()
        self.found_stop_last = {}
        self.e9_offset = 0
        self.written.clear()
        self.scan_forget()
        self.retrace_pending = False
        self.log_open = False
        if self.session_dir is not None:
            shutil.rmtree(self.session_dir, ignore_errors=True)
            self.session_dir = None

    def scan_forget(self) -> None:
        """Drop the scan's count and cell together, wherever it ended."""
        self.scan_iterations = None
        self.scan_cell_bytes = None

    def install_table(self, symbols: list[sym.Symbol], accumulate: bool = False) -> None:
        """The one way a table arrives, so the name index never describes another table.

        `accumulate` keeps earlier loads, as the debugger's appending `LV` does; a name loaded
        again takes the new row. The key is the folded name, as in `index_by_name`."""
        fresh = {sym.folded(s.name) for s in symbols}
        kept = ([s for s in self.table if sym.folded(s.name) not in fresh] if accumulate else [])
        self.table[:] = kept + symbols
        self.table_generation += 1
        self.name_index.clear()
        self.name_index.update(sym.index_by_name(self.table))

    def machine_replaced(self) -> None:
        """A state was loaded: the next stop re-measures a base measured off the machine."""
        if self.table and self.base_measured_from is not None:
            self.pending["remeasure"] = self.pending["dirty"] = True

    def forget_symbols(self) -> None:
        """Drop the table and the base; the declaration store stays (re-keyed in `start`)."""
        self.table.clear()
        self.table_generation += 1
        self.name_index.clear()
        self.symbol_types.clear()
        self.section_bases.clear()
        self.base.clear()
        self.base_measured_from = None
        self.map_batches = []
        self.start_symbols = None

    def origin(self) -> str:
        """One stamp per `start`, unique across sessions and processes."""
        self.start_seq += 1
        return f"{now()}#{os.getpid()}.{self.start_seq}"


STATE = State()


@atexit.register
def remove_scratch() -> None:
    """A session never closed has nobody else to remove its scratch."""
    for folder in (STATE.session_dir, STATE.scratch):
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)


def reply(status: str = "ok", **fields: Any) -> dict[str, Any]:
    """Every reply's body through the contract's guard; the call boundary adds `session`."""
    out: dict[str, Any] = {"status": status}
    out.update({k: fields.pop(k) for k in ("code", "message") if k in fields})
    out.update(fields)
    if "note" in out and not out["note"]:
        del out["note"]
    if STATE.applied_last and "applied_on_stop" not in out:
        out["applied_on_stop"] = dict(STATE.applied_last)
    STATE.applied_last.clear()
    if STATE.found_stop_last and "stopped_on_its_own" not in out:
        out["stopped_on_its_own"] = dict(STATE.found_stop_last)
    STATE.found_stop_last = {}
    _lead_the_note(out)
    return contract.check_envelope(out)


def _lead_the_note(out: dict[str, Any]) -> None:
    """A wait that expired says what is most likely first (`program.lead`): in its own `note`, or in
    the `note` of the `verify` block an input carries."""
    if out.get("code") == "control_silent" and out.get("message"):
        gone = None if STATE.session is None else dprogram.gone(STATE.session)
        opening = dprogram.lead({}, gone)
        if opening and not str(out["message"]).startswith(opening):
            out["message"] = opening + str(out["message"])
        return
    verify = out.get("verify")
    wait = out if out.get("verdict") == contract.TIMEOUT else (
        verify if isinstance(verify, dict) and verify.get("verdict") == contract.TIMEOUT
        else None)
    if wait is None or not wait.get("note"):
        return
    gone = None if STATE.session is None else dprogram.gone(STATE.session)
    opening = dprogram.lead(wait, gone)
    if opening and not str(wait["note"]).startswith(opening):
        wait["note"] = opening + str(wait["note"])


NO_SESSION_BLOCK: dict[str, Any] = {"alive": False, "running": False, "altered": False}


_ALARM_WHEN: dict[str, Callable[[Any], bool]] = {
    "program": lambda v: bool(v),
    "conf_changed_on_disk": lambda v: v is not False,
    "output_bytes_dropped": lambda v: bool(v),
}
_ALWAYS = ("alive", "running", "altered")


def session_block(whole: bool = False) -> dict[str, Any]:
    """The `session` block every reply closes with. `whole` changes nothing."""
    if STATE.session is None:
        return dict(NO_SESSION_BLOCK)
    return {key: value for key, value in STATE.session.state().items()
            if key in _ALWAYS or (key in _ALARM_WHEN and _ALARM_WHEN[key](value))}


def process_facts() -> dict[str, Any]:
    """The process facts for the top of `start`, `status` and `close`; empty with no session."""
    if STATE.session is None:
        return {}
    return {key: value for key, value in STATE.session.state().items()
            if key not in _ALWAYS and key != "program"}


def extend(built: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """Add fields to a built body, keeping `close`'s `session` last."""
    tail = built.pop("session", None)
    built.update(fields)
    _lead_the_note(built)
    if tail is not None:
        built["session"] = tail
    return built


def answer(fields: dict[str, object]) -> dict[str, Any]:
    """A session method's own answer, whole under the envelope: its fields only mean
    something together, so no tool re-picks them."""
    return reply(**cast(dict[str, Any], fields))


#: Tail kept of the text `debug` returns, and of the one `detail=True` adds.
DEBUG_TEXT_KEEP = 4000
DETAIL_TEXT_KEEP = 2000


def delta(out: str, keep: int) -> dict[str, Any]:
    """The tail of what the debugger printed for a command, saying it is a slice (`clipped`)."""
    # `out[-0:]` is the whole string. Not `Invalid`: `keep` is never a caller's, so a bad one
    # is a bug here.
    if keep <= 0:
        raise ValueError(f"a cap of {keep} is not a cap: it would return the whole "
                         f"text while reporting itself clipped")
    return {"output": out[-keep:], "output_chars": len(out), "clipped": len(out) > keep}


OUTPUT_FIELDS = ("output", "output_chars", "clipped")
OUTPUT_HOW = "detail=True adds what the debugger printed for this command"


def delta_if_asked(out: str, keep: int, detail: bool) -> dict[str, Any]:
    """`delta` with `detail`; without it, the note that the output was left out."""
    return delta(out, keep) if detail else narrowing.omission(list(OUTPUT_FIELDS), OUTPUT_HOW)


def interrupt_stop(attribution: dict[str, Any], instruction: dict[str, Any],
                   registers: dict[str, str], held: list[dict[str, str]]) -> dict[str, Any]:
    """`attribution` with an `own` cause when no declaration explains the stop, the instruction
    there is an `int`, and a held `BPINT` row watches that interrupt (and that `AH`, if it names
    one): `break_on_int3` is such a row."""
    if (attribution.get("attributed") or attribution.get("own")
            or attribution.get("retrace_pending") or attribution.get("regpoints_holding")):
        return attribution
    raw = bytes.fromhex(str(instruction.get("bytes", "")))
    if raw[:1] == b"\xCC":
        number = 3
    elif raw[:1] == b"\xCD" and len(raw) >= 2:
        number = raw[1]
    else:
        return attribution
    eax = registers.get("EAX")
    ah = (int(eax, 16) >> 8) & 0xFF if eax else None
    rows = [entry for b in held if b["entry"].startswith("BPINT ")
            for entry, (num, row_ah) in [(b["entry"], grammar.parse_interrupt_row(b["entry"]))]
            if num == number and (row_ah is None or row_ah == ah)]
    if not rows:
        return attribution
    named = " and ".join(f"`{row}`" for row in rows)
    return {**attribution, "own": f"most likely the held {named}: the guest is at `int "
                                  f"{number:02X}`"}


_CAUSE_AT = re.compile(r" at [0-9A-Fa-f]{4}:[0-9A-Fa-f]{4,8}")


def regpoint_hit(attribution: dict[str, Any]) -> dict[str, Any]:
    """The `regpoint_hit` object of a stop a registerpoint made, or met beside a `run_to`'s
    target."""
    ref = attribution["ref"] if attribution.get("by") == "regpoint" else attribution.get("regpoint")
    if not ref:
        return {}
    return {"regpoint_hit": regpoint.hit(ref, ref, attribution["at"])}


def cause(attribution: dict[str, Any]) -> str:
    """What stopped the machine, as every stop reply's `cause`."""
    at = attribution.get("at", "an address the record lacks")
    if not attribution.get("attributed"):
        if attribution.get("own"):
            return f"{attribution['own']}, at {at}"
        holding = attribution.get("regpoints_holding")
        held_too = (f"; registerpoint {', '.join(holding)} holds here, and `BPIF` stops as "
                    f"its condition comes true" if holding else "")
        if attribution.get("retrace_pending"):
            return (f"most likely the retrace stop a `run_for` left armed: no declared code "
                    f"breakpoint at {at}{held_too}")
        if holding:
            return (f"most likely registerpoint {', '.join(holding)}, whose condition holds at "
                    f"{at}: `BPIF` stops as it comes true, and this build's `RUNSTATE` did not "
                    f"name the row that stopped the machine, so it cannot be proved")
        return (f"no declared code breakpoint at {at}: the debugger keeps no hit flag and a memory "
                f"watch stops at the instruction that wrote, so which declaration fired cannot "
                f"be told")
    if attribution.get("by") == "regpoint":
        return f"registerpoint {attribution['ref']}, whose condition came true at {at}"
    if attribution.get("by") == "stop":
        return f"the `stop` call at {at}"
    if attribution.get("by") == "cancel":
        return f"a cancelled call's stop at {at}"
    if attribution.get("by") == "run_to":
        also = list(attribution.get("refs", []))
        return (f"run_to's target {attribution['ref']} at {at}"
                + (f", where breakpoint {', '.join(also)} is declared too" if also else "")
                + (f", where registerpoint {attribution['regpoint']} came true too"
                   if attribution.get("regpoint") else ""))
    refs = attribution.get("refs")
    if refs:
        return f"breakpoints {', '.join(refs)} at {at}, every declaration at that address named"
    return f"breakpoint {attribution['ref']} (by {attribution['by']}) at {at}"


def cause_key(text: str) -> str:
    """`cause` without its address: the key for counting stops by declaration."""
    return _CAUSE_AT.sub("", text)


def shown_regs(registers: dict[str, str]) -> dict[str, str]:
    """Register values as `0x` at their width, the spelling `judges.number` takes back."""
    return {name: judges.hex_at_width(int(digits, 16), 4 * len(digits))
            for name, digits in registers.items()}
