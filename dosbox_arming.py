"""The declarations' ARMING: what the store says, put into the debugger and read back.

A declaration is an INTENT kept on disk, keyed by the conf (`dosbox_declarations`); this
module is where an intent meets the machine. It resolves each one through the placement
layer, arms what can be armed (a code breakpoint, an interrupt, a change-watch), reads
the debugger's list back rather than trusting an acknowledgement, evaluates the show
watches at a stop, attributes a stop to the declaration whose address it is at, and
applies, at the next stop, what was declared or cleared while the guest ran.

The six declaring tools (`breakpoint_at/list/clear`, `watch_add/list/clear`) and
`breakpoint_interrupt` have their bodies here; their contracts (the docstrings the client
reads) stay with the registrations in `dosbox_x_server`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any, cast

from scry_core import value_format as vf

import dosbox_checks as checks
import dosbox_code as code
import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_dump as dumping
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE


def declare(kind: str, by: str, ref: str, linear: int | None = None,
            cpu: str | None = None, **watch: Any) -> dec.Declaration:
    """A declaration stamped with this session's origin, the clock, the build of the batch
    that describes `linear`, its place now (`placement.stamp_at`), and for a raw row the mode
    of the stop that placed it (`cpu`; None where no stop did, or the guest runs): the one
    place the declaring tools build one, so none of them can forget the stamp."""
    raw = dec.is_raw_code(kind, by)
    mode = placement.mode_word(cpu) if raw else None
    return cast(dec.Declaration,
                placement.to_invalid(lambda: dec.Declaration(kind, by, ref, created_at=st.now(),
                                                    origin=STATE.session_origin,
                                                    fingerprint=placement.stamp_at(linear, raw),
                                                    cpu_mode=mode, **watch)))


class RawPlaces:
    """Where a raw breakpoint lands at this instant, the stop surveyed at most once and only
    when a batch is held to judge it by: in real mode by arithmetic, in protected mode through
    the selector's base. None where this instant cannot say (a protected-mode guest that runs,
    a base this stop cannot read, an offset past its segment)."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self._segs: code.Segments | None = None

    def linear(self, by: str, ref: str) -> int | None:
        """Its place, asked only with a batch held to judge it by."""
        return self.place(by, ref) if STATE.map_batches else None

    def place(self, by: str, ref: str) -> int | None:
        if by != "address":
            return None
        try:
            seg, off = placement.parse_seg_off(ref)
            if self._segs is None and not self.session.at_debugger():
                last = STATE.last_machine()
                real = last is not None and last[0] == dcons.REAL_MODE
                return dumping.real_linear(seg, off) if real and off <= dcons.offset_ceiling(
                    dcons.REAL_MODE) else None
            if self._segs is None:
                self._segs = code.segments_at_stop(self.session)
            if self._segs.real:
                return (dumping.real_linear(seg, off)
                        if off <= dcons.offset_ceiling(dcons.REAL_MODE) else None)
            base, limit = self._segs.base(seg), self._segs.limit(seg)
        except ds.Invalid:
            return None
        return base + off if off <= limit else None

    def judged(self, decl: dec.Declaration) -> Callable[[], int | None]:
        return lambda: self.linear(decl.by, decl.ref)

    def cpu(self) -> str | None:
        """This stop's cpu mode as the debugger spells it, off the same survey; the last stop's
        while the guest runs, None before any."""
        if self._segs is None and self.session.at_debugger():
            self._segs = code.segments_at_stop(self.session)
        if self._segs is not None:
            return self._segs.mode
        last = STATE.last_machine()
        return None if last is None else last[0]


def _last_cpu() -> str | None:
    """The last stop's cpu mode, for a judgement that must not type at the console."""
    last = STATE.last_machine()
    return None if last is None else last[0]


def _nowhere() -> None:
    """No place asked: before a map there is no batch to judge one by, and a stopper count must
    not type at the console, so a row it cannot place is taken as described: not armed."""
    return None


def current_store() -> dec.DeclarationStore:
    """The declaration store for the current session's conf, or INVALID with no session.
    No conf is known until a session is started, and the conf is what says WHICH guest's
    declarations these are, so there is nothing to answer before then."""
    if STATE.store is None:
        raise ds.Invalid("no_session",
            "no declaration store yet: `start` a session first, so its conf "
                         "identifies which guest's declarations belong here")
    return STATE.store


_STALE_WHY = ("a raw address declared against another build (a different conf or map, or "
              "none recorded): kept and never re-armed here, because it re-resolves against "
              "nothing. Declare it again to adopt it, or clear it by this ref")
_ORPHAN_WHY = ("declared before origins were kept, so it is nobody's: clear it by this "
               "ref, or declare it again to adopt it")
_ORPHAN_WATCH_WHY = _ORPHAN_WHY + ". A show watch is still EVALUATED at every stop while it is here"


def orphan(decl: dec.Declaration) -> bool:
    """A declaration with no origin recorded, in a session that HAS one: written by a store
    from before origins were kept: such a show watch sits in every stop reply with
    `origin: null` and nothing tells it from this session's. With
    no session origin at all (the contract harness never calls `start`) nothing is an
    orphan: there is no "this session's" to tell it from."""
    return decl.origin is None and STATE.session_origin is not None


def decl_row(decl: dec.Declaration) -> dict[str, Any]:
    """The fields every listed declaration carries: its ref, how it was declared, and
    when and by which session (`origin`), so a caller can tell this session's from what
    an earlier one left."""
    return {"ref": decl.ref, "by": decl.by, "created_at": decl.created_at,
            "origin": decl.origin}


# The BPLIST kind tokens for a memory watch, told apart from a code breakpoint (`BP`) and
# an interrupt (`BPINT`): protected paged, real, and linear.
_WATCH_KINDS = ("BPPM", "BPMEM", "BPLM")

# ONE definition of the protected-mode change-watch caveat, shared by the fresh-arm and the
# re-declare paths so the two cannot drift.
_PR_WATCH_CAVEAT = ("this is a protected-mode watch (BPPM); under a paged DPMI program it "
                    "fires on the paging host, not the program, so a stop "
                    "here is not to be trusted. Break-on-change is reliable in real mode")


def _watch_entry(seg: int, off: int, mode: str) -> str:
    """The debugger's own BPLIST spelling for a memory watch at seg:off, for DISPLAY only:
    protected mode lists `BPPM SEL:%08X`, real mode `BPMEM SEG:%04X`. It is NOT used to
    recognise a held row -- the debugger's width varies, so recognition goes through
    `watch_held`, which compares the numbers. This is the expected spelling to show a
    caller, nothing more."""
    if mode.startswith("Pr"):
        return f"BPPM {seg:04X}:{off:08X}"
    return f"BPMEM {seg:04X}:{off:04X}"


def watch_held(held: list[dict[str, str]], seg: int, off: int) -> dict[str, str] | None:
    """The held BPLIST row that is a memory watch at seg:off, by VALUE, or None. A code
    breakpoint at the same address (`BP`) is deliberately not a match: the two are different
    kinds and `watch_clear` must not delete a code breakpoint."""
    for b in held:
        t = dcons.bp_row_target(b["entry"])
        if t is not None and t[0] in _WATCH_KINDS and (t[1], t[2]) == (seg, off):
            return b
    return None


def render_watch(raw: bytes, width: int, fmt: str) -> vf.Value:
    """`width` bytes read as `fmt`, little-endian (x86): one value, a list, a string or a
    struct, as the format grammar says (`value_format`)."""
    return vf.parse(fmt).decode(raw, "little", width)


def evaluate_watches(session: ds.Session, *,
                      machine: tuple[str, dict[str, str]] | None = None,
                      held: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every watch declaration, EVALUATED at this stop (decision 13). A show watch
    is read and rendered -- it arms nothing, so its bytes are the program's (decision 29).
    A break-on-change watch is NOT read: it armed a trap byte in that memory, and reading
    it would hand back the trap as the value it exists to report, so it is listed with its
    state and that reason instead. A watch that no longer resolves is listed with why, never
    a value at a guessed address.
    """
    if STATE.store is None:
        return []
    # `held` is the list the stop already read off its one repaint (`stop_survey`); only a
    # caller with no stop in hand pays a fresh read.
    if held is None:
        held = session.breakpoints()
    out: list[dict[str, Any]] = []
    for decl in STATE.store.declarations():
        if decl.kind != "watch":
            continue
        item: dict[str, Any] = {"ref": decl.ref, "by": decl.by, "mode": decl.watch_mode,
                                "length": decl.width, "fmt": decl.fmt}
        if orphan(decl):
            item["orphan"] = True       # nobody's: from a store that kept no origin
        res = placement.resolve_ref(decl, "DS", session, machine=machine)
        if "pointer" in res:
            item["pointer"] = res["pointer"]
        if res["state"] != "armable":
            item["state"] = res["state"]
            if "why" in res:
                item["why"] = res["why"]
            out.append(item)
            continue
        seg, off = res["seg"], res["off"]
        if decl.by == "pointer" and decl.watch_mode == "change":
            # RE-RESOLVED AT EVERY STOP, because the pointer can move: a change watch armed
            # at the old struct is moved to the new one, and the reply says from where. A
            # move the debugger refused leaves it armed where it was, and the state below
            # is judged THERE.
            moved = _follow(session, decl, seg, off, held)
            if moved is not None:
                item["moved"] = moved
                held = session.breakpoints()
                if "why" in moved:
                    still = next((r for r in STATE.armed.get(("watch", decl.ref), [])
                                  if r["kind"] == "watch"), None)
                    if still is not None:
                        seg, off = int(still["seg"]), int(still["off"])
        if decl.watch_mode == "change":
            item["state"] = "armed" if watch_held(held, seg, off) else "gone"
            item["note"] = ("a break-on-change watch arms a trap byte in this memory, so "
                            "its value is not read here -- the read would return the trap. "
                            "Clear it to read the value")
            out.append(item)
            continue
        # A show watch whose address is CURRENTLY armed as a memory watch (a change watch on
        # the same bytes, however it was declared -- decision 29 forbids the pair by ref, but
        # two refs can alias one address) would read that watch's trap byte. Checked against
        # the live BPLIST, not the store, so it holds whatever the declaration said.
        if watch_held(held, seg, off) is not None:
            item["state"] = "shadowed"
            item["note"] = ("a break-on-change watch is armed at this same address, so its "
                            "bytes are the trap, not the value -- this read is skipped. Clear "
                            "the change watch to read here")
            out.append(item)
            continue
        try:
            # THE CACHED MODE (decision 35, part 2): a show watch's read_bytes would else
            # re-survey the machine for its offset ceiling -- N watches, N surveys of a
            # screen the stop already read. `machine[0]` is that mode; passed only when the
            # caller cached it, which the stop reply does.
            mode = machine[0] if machine is not None else None
            raw = session.read_bytes(seg, off, cast(int, decl.width), mode=mode)
        except ds.Invalid as e:
            item["state"] = "unreadable"
            item["why"] = str(e)
            out.append(item)
            continue
        item["state"] = "evaluated"
        item["value"] = render_watch(raw, cast(int, decl.width), cast(str, decl.fmt))
        item["bytes"] = raw.hex()
        out.append(item)
    return out


def _same_code_addr(mode: str, a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Whether two code addresses are the same place. Protected mode compares the selector
    and offset directly (the breakpoint was armed at the live selector). Real mode compares
    the LINEAR address, because many seg:off pairs alias one physical byte and the stop's
    CS:EIP need not use the same paragraph the breakpoint was placed against."""
    if mode.startswith("Pr"):
        return a == b
    return a[0] * 16 + a[1] == b[0] * 16 + b[1]


def _bp_holders(session: ds.Session, mode: str, at: tuple[int, int], *, but: str = "",
                machine: tuple[str, dict[str, str]] | None = None) -> list[dec.Declaration]:
    """The breakpoint declarations that resolve to the code address `at` (by linear address
    in real mode, where many spellings alias one byte), other than `but`."""
    if STATE.store is None:
        return []
    out: list[dec.Declaration] = []
    skip = dec.canonical_ref(but, placement.decide_by(but)) if but else ""
    for decl in STATE.store.declarations():
        if decl.kind != "breakpoint" \
                or (but and dec.canonical_ref(decl.ref, decl.by) == skip):
            continue
        res = placement.resolve_ref(decl, "CS", session, machine=machine)
        if res["state"] != "armable":
            continue
        there = (res["seg"], res["off"])
        # With no mode to hand (no stop recorded yet) the spellings are compared as they
        # are: a real-mode alias of one byte under two paragraphs is then not seen, which
        # errs towards accepting, never towards refusing a declaration wrongly.
        if _same_code_addr(mode, at, there) if mode else at == there:
            out.append(decl)
    return out


def attribute_stop(session: ds.Session, *, where: dict[str, str],
                    machine: tuple[str, dict[str, str]] | None = None,
                    retrace_may_stop: bool = False) -> dict[str, Any]:
    """WHICH declaration the stop is at, BY ADDRESS COMPARISON, or an honest cannot-say
    (decision 13). A code breakpoint whose resolved address equals CS:EIP is named. Nothing
    else is claimed: the debugger records no hit flag, and a memory watch stops at the
    instruction that WROTE, not at the watched address, so from a stop there is no
    arithmetic back to a watch declaration. Guessing one would be the confident wrong answer.
    A store from before the one-row rule can hold two declarations at one address: every
    one is named (`refs`), the first stays `ref`, and `note` says so, instead of the first
    in silence.

    `where` and `machine` are read once by the caller (decision 35): attribution over M
    breakpoints would otherwise re-read the machine M times for a state fixed at this stop.

    `retrace_may_stop` is a stop reached by a release that ran on (`resume`, a `run_to` that did
    not arrive, a stop found on its own): a retrace `run_for` left armed is the likeliest cause
    of such a stop when no declaration explains it, so it is named and forgotten there. Any other
    stop (a step, a `stop`, an arrival) is its caller's own and leaves it armed.
    """
    stop = (int(where["cs"], 16), int(where["eip"], 16))
    mode = where["mode"]
    holders = _bp_holders(session, mode, stop, machine=machine)
    if holders:
        out: dict[str, Any] = {"attributed": True, "ref": holders[0].ref, "by": holders[0].by,
                               "at": f"{stop[0]:04X}:{stop[1]:04X}"}
        if len(holders) > 1:
            out["refs"] = [d.ref for d in holders]
            out["note"] = (f"{len(holders)} declarations resolve to this address (a store "
                           f"from before one row was one declaration): all are named")
        return out
    if retrace_may_stop and STATE.retrace_pending:
        STATE.retrace_pending = False
        return {"attributed": False, "retrace_pending": True,
                "at": f"{stop[0]:04X}:{stop[1]:04X}",
                "why": "the stop address matches no declared code breakpoint, and a `run_for` "
                       "had left a retrace stop armed, which stops the next release at the next "
                       "retrace: most likely this stop"}
    return {"attributed": False,
            "at": f"{stop[0]:04X}:{stop[1]:04X}",
            "why": "the stop address matches no declared code breakpoint. The debugger "
                   "keeps no hit flag, and a memory watch stops at the WRITING instruction "
                   "rather than the watched address, so which declaration fired cannot be "
                   "derived from the stop"}


def _follow(session: ds.Session, decl: dec.Declaration, seg: int, off: int,
            held: list[dict[str, str]]) -> dict[str, str] | None:
    """A change watch whose pointer now points elsewhere: the old row is deleted, a row at
    the new place armed, the record moved. `{from, to}` when it moved, None when it is
    where it was; a debugger that refuses the new row leaves `why` beside them and the
    record as it was."""
    rows = STATE.armed.get(("watch", decl.ref), [])
    old = next((r for r in rows if r["kind"] == "watch"), None)
    if old is not None and (old["seg"], old["off"]) == (seg, off):
        return None
    # A watch declared while the pointer was NULL armed nothing: the stop that finds the
    # pointer set arms it, and says it came from null.
    where = {"from": f"{old['seg']:04X}:{old['off']:04X}" if old is not None else "null",
             "to": f"{seg:04X}:{off:04X}"}
    # THE NEW ROW FIRST, the old one only once the new is held: a refusal then leaves the
    # watch armed where it was, the record true, and `why` beside `from`/`to`.
    try:
        armed = session.watch(segment=seg, offset=off)
    except ds.Invalid as e:
        return {**where, "why": str(e)}
    row = watch_held(held, int(old["seg"]), int(old["off"])) if old is not None else None
    if row is not None:
        session.command(f"BPDEL {row['index']}")
    rows[:] = [r for r in rows if r is not old]
    STATE.note_armed(decl.ref, {"kind": "watch", "seg": seg, "off": off,
                                "entry": str(armed["armed"])})
    return where


def rearm_declarations(session: ds.Session) -> dict[str, Any]:
    """Re-resolve every stored declaration against the just-loaded table and arm the code
    ones that resolve and are not already held. Decision 7's re-arm: a breakpoint declared
    by name is meant to survive a rebuild and re-place itself. It arms nothing for an
    unresolved or ambiguous name -- those are counted and reported, never guessed at.
    """
    empty: dict[str, Any] = {"rearmed": 0, "rearmed_refs": [], "stale": [],
                             "unresolved": 0, "ambiguous": 0, "unarmable": 0}
    if STATE.store is None:
        return empty
    held = {dcons.bp_row_target(b["entry"]) for b in session.breakpoints()}
    out = dict(empty)
    places = RawPlaces(session)
    for decl in STATE.store.declarations():
        if decl.kind != "breakpoint":
            continue
        res = placement.resolve_ref(decl, "CS", session)
        state = res["state"]
        if state in ("unresolved", "ambiguous", "unarmable"):
            out[state] += 1
        elif ("BP", res["seg"], res["off"]) in held:
            continue              # already armed, by this session or by a symbol's re-arm
        # A RAW ADDRESS PLACED IN THE OTHER MODE waits for a stop of its own: read here, its
        # SEG:OFF is another byte. `start` parks in real mode, so a protected-mode row is
        # re-armed by a `symbols_load` at a protected-mode stop, never at the park.
        elif placement.waits(decl, places.cpu) is not None:
            out["unarmable"] += 1
        # A RAW ADDRESS FROM ANOTHER BUILD IS NOT RE-ARMED (the owner's decision, per
        # build): it re-resolves against nothing, and armed blind on a relinked program it
        # lands wherever the linker put something else. It stays in the store, is NAMED here
        # and listed `stale`, and declaring it again adopts it. Tested AFTER `held`, so a
        # row the debugger holds anyway is never called stale here and `armed` in the list.
        elif placement.is_stale(decl, places.judged(decl)):
            out["stale"].append(decl.ref)
        else:
            try:
                session.arm_code_breakpoint(res["seg"], res["off"])
                STATE.note_armed(decl.ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                                       "entry": f"BP {res['seg']:04X}:{res['off']:04X}"})
                out["rearmed"] += 1
                out["rearmed_refs"].append(decl.ref)
            except ds.Invalid:
                out["unarmable"] += 1   # the machine moved under us; the intent is kept
    return out


def arm_at_start(session: ds.Session) -> dict[str, str]:
    """At `start`, the machine parked: arm again the raw addresses an earlier session declared
    over THIS build, which is what the per-build rule promises and what nothing else does
    before the first `symbols_load`. Another build's stay `stale`. With none to arm, the
    debugger's list is not read, so a start with nothing declared costs no round trip.

    The session is already installed when this runs, so a refusal here is handed back for
    `start`'s reply (`rearm_refused`) rather than raised: raised, it would answer INVALID over
    a live emulator. The declarations stay stored either way."""
    if STATE.store is None or not any(
            d.kind == "breakpoint" and d.by == "address"
            and not placement.is_stale(d, _nowhere)
            for d in STATE.store.declarations()):
        return {}
    try:
        rearm_declarations(session)
    except ds.Invalid as e:
        return {"rearm_refused": str(e)}
    return {}


def apply_pending(session: ds.Session) -> dict[str, Any]:
    """At a stop, do what the guest's running kept the console from doing: load the symbols
    that were parsed and held, remove the rows a clear left behind, arm what was declared.
    Returns the account, empty when nothing was pending. Each half is attempted on its own:
    a refusal on one (a symbol that no longer resolves) is reported, not allowed to hold the
    others back, and what could not be applied stays pending for the next stop."""
    if not (STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["load"] is not None):
        return {}
    STATE.pending["dirty"] = False
    STATE.pending["drained_seq"] = STATE.last_stop.get("seq", 0)
    out: dict[str, Any] = {"symbols_loaded": False, "disarmed": [], "armed": [],
                           "still_pending": []}
    if STATE.pending["load"] is not None:
        try:
            session.load_symbols(cast(bytes, STATE.pending["load"]))
            STATE.pending["load"] = None
            out["symbols_loaded"] = True
            # THE RE-ARM THAT FOLLOWS EVERY LOAD, which the pending reply promised.
            out["armed"].extend(rearm_declarations(session)["rearmed_refs"])
        except ds.Invalid as e:
            out["still_pending"].append(f"symbols_load: {e}")
    kept_disarm: list[dict[str, Any]] = []
    for spec in STATE.pending["disarm"]:
        try:
            if spec["kind"] == "bp":
                gone = session.clear_code_breakpoint(spec["seg"], spec["off"])
            elif spec["kind"] == "int":
                gone = session.clear_interrupt_breakpoint(spec["num"], spec["ah"])
            else:
                row = watch_held(session.breakpoints(), spec["seg"], spec["off"])
                if row is not None:
                    session.command(f"BPDEL {row['index']}")
                gone = {"entry": spec["entry"], "removed": row is not None}
            if gone["removed"]:
                out["disarmed"].append(str(gone["entry"]))
                STATE.snapshot_forget(str(gone["entry"]))
        except ds.Invalid as e:
            kept_disarm.append(spec)
            out["still_pending"].append(f"disarm {spec['entry']}: {e}")
    STATE.pending["disarm"][:] = kept_disarm
    kept_arm: list[str] = []
    if STATE.store is not None and STATE.pending["arm"]:
        # ONE machine reading and ONE list read for every ref (decision 35), not one per
        # ref: at a console round trip apiece, three refs cost seconds otherwise.
        try:
            where, regs = session.where_and_registers()
            machine: tuple[str, dict[str, str]] | None = (where["mode"], regs)
            held = session.breakpoints()
        except ds.Invalid:
            machine, held = None, []
        for ref in STATE.pending["arm"]:
            decl = next((d for d in STATE.store.declarations() if d.ref == ref), None)
            if decl is None or ref in out["armed"]:
                continue                     # cleared before the stop came, or re-armed by the load
            try:
                if decl.kind == "interrupt":
                    num, ah = dcons.parse_interrupt_row(decl.ref)
                    if not any(b["entry"] == decl.ref for b in held):
                        session.breakpoint_interrupt(num, ah)
                    STATE.note_armed(ref, {"kind": "int", "num": num, "ah": ah, "entry": decl.ref})
                elif decl.kind == "watch":
                    res = placement.resolve_ref(decl, "DS", session, machine=machine)
                    if res["state"] != "armable":
                        raise ds.Invalid("unknown_ref", str(res.get("why", res["state"])))
                    aliased = _aliased(ref, res["seg"], res["off"])
                    if aliased is not None:
                        raise ds.Invalid("ambiguous_ref", aliased)
                    row = watch_held(held, res["seg"], res["off"])
                    entry = (row["entry"] if row is not None else
                             str(session.watch(segment=res["seg"], offset=res["off"])["armed"]))
                    if row is None:
                        held.append({"index": "?", "entry": entry})   # the list learns the row
                    STATE.note_armed(ref, {"kind": "watch", "seg": res["seg"], "off": res["off"],
                                      "entry": entry})
                else:
                    res = placement.resolve_ref(decl, "CS", session, machine=machine)
                    if res["state"] != "armable":
                        raise ds.Invalid("unknown_ref", str(res.get("why", res["state"])))
                    want = ("BP", res["seg"], res["off"])
                    entry = f"BP {res['seg']:04X}:{res['off']:04X}"
                    if not any(dcons.bp_row_target(b["entry"]) == want for b in held):
                        session.arm_code_breakpoint(res["seg"], res["off"])
                        # THE LIST LEARNS THE ROW: read once before the loop, it never saw
                        # what the loop armed, and a second ref on the same address stacked
                        # a second row.
                        held.append({"index": "?", "entry": entry})
                    STATE.note_armed(ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                                      "entry": entry})
                out["armed"].append(ref)
            except ds.Invalid as e:
                kept_arm.append(ref)
                out["still_pending"].append(f"arm {ref}: {e}")
    STATE.pending["arm"][:] = kept_arm
    if not out["still_pending"]:
        del out["still_pending"]
    if not (out["symbols_loaded"] or out["disarmed"] or out["armed"]
            or out.get("still_pending")):
        return {}
    # ACCUMULATED, NOT REPLACED: `live()` may have drained part of the queue a moment
    # before a stop tool drains the rest, and the reply must carry BOTH accounts as one
    # (measured: a drain in `live()` followed by the stop's own lost the first's disarms).
    merged = STATE.applied_last
    for key in ("disarmed", "armed"):
        merged[key] = list(merged.get(key, [])) + list(out[key])
    merged["symbols_loaded"] = bool(merged.get("symbols_loaded")) or bool(out["symbols_loaded"])
    if "still_pending" in out:
        merged["still_pending"] = list(out["still_pending"])
    else:
        merged.pop("still_pending", None)
    return out


def _armable_declarations() -> list[dec.Declaration]:
    """The declarations that can be armed in this build and this session: not a raw address
    kept from another build, not an interrupt of an earlier session, not a symbol this build
    does not define."""
    if STATE.store is None:
        return []
    return [d for d in STATE.store.declarations()
            if not placement.is_stale(d, _nowhere)
            and placement.waits(d, _last_cpu) is None
            and not (d.kind == "interrupt" and d.origin != STATE.session_origin)
            and not (d.by == "symbol" and dec.DeclarationStore.resolve_name(
                d, STATE.table, STATE.name_index).state == "unresolved")]


def declares_code_breakpoint() -> bool:
    """Whether an armable code breakpoint is declared: the one stopper a stop's address can be
    attributed to, and so the one a retrace run surveys each frame for."""
    return any(d.kind == "breakpoint" for d in _armable_declarations())


def declares_untold_stopper() -> bool:
    """Whether an armable stopper is declared whose stop no address names: a change-watch or an
    interrupt breakpoint."""
    return any(d.kind == "interrupt" or (d.kind == "watch" and d.watch_mode == "change")
               for d in _armable_declarations())


def something_can_stop_it() -> bool:
    """Whether anything can bring the running machine back to the debugger: a code or
    interrupt breakpoint, or a change-watch. Two sources, neither the console (which a
    running machine does not answer): the debugger's own list as it stood at the last
    stop, which holds a row whoever armed it (a `run_to` target left armed after a stop
    elsewhere has no declaration behind it), and the store, leaving out what is known NOT
    to be armed (a stale raw address, a symbol this build does not define). The remaining
    doubt errs on the side of waiting."""
    held = STATE.last_stop.get("held") or []
    if any(str(r.get("entry", "")).startswith(("BP ", "BPINT ", "BPMEM ", "BPPM "))
           for r in held):
        return True
    # A declaration still on the arm queue is armed only AT a stop, so it cannot produce one.
    queued = set(STATE.pending["arm"])
    return any(not (d.kind == "watch" and d.watch_mode != "change") and d.ref not in queued
               for d in _armable_declarations())


def breakpoint_interrupt(session: ds.Session, number: int, ah: int | None,
                         detail: bool = False) -> dict[str, Any]:
    """The body of the `breakpoint_interrupt` tool."""
    want = dcons.interrupt_row(number, ah)
    decl = declare("interrupt", "address", want)
    if not session.at_debugger():
        is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
        return st.reply(ref=want, stored=True, already_stored=not is_new, armed=False,
                      state="pending", **STATE.queue_arm(want))
    if any(b["entry"] == want for b in session.breakpoints()):
        is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
        return st.reply(ref=want, stored=True, already_stored=not is_new, armed=True,
                      entry=want, note="this interrupt breakpoint was already armed")
    delta = st.delta_if_asked(session.breakpoint_interrupt(number, ah), 2000, detail)
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    num, ah = dcons.parse_interrupt_row(want)
    STATE.note_armed(want, {"kind": "int", "num": num, "ah": ah, "entry": want})
    return st.reply(ref=want, stored=True, already_stored=not is_new, entry=want, **delta)


def breakpoint_at(session: ds.Session, ref: str, by: str) -> dict[str, Any]:
    """The body of the `breakpoint_at` tool."""
    # `by` was judged before the session gate (`dosbox_checks.by_choice`), its family's words.
    chosen = placement.decide_by(ref) if by == "auto" else by
    placement.address_shape(ref, chosen)
    places = RawPlaces(session)
    placed = session.at_debugger() and places.place(chosen, ref) is not None
    decl = declare("breakpoint", chosen, ref, places.linear(chosen, ref),
                   cpu=places.cpu() if placed else None)
    stored = current_store().held_ref(ref, ("breakpoint",))
    if stored is not None and stored != ref:
        # AN ADDRESS DECLARED AGAIN IN ANOTHER SPELLING IS THE SAME DECLARATION, and
        # it is handled under its stored spelling, the string a clear takes.
        ref, decl = stored, dataclasses.replace(decl, ref=stored)
    # RESOLVE BEFORE STORING so an ambiguous name is refused without leaving a declaration
    # that can never arm; an unresolved one is fine to store (it may resolve next build).
    res = placement.resolve_ref(decl, "CS", session)
    if res["state"] == "ambiguous":
        raise ds.Invalid("unknown_ref", res["why"])   # refuse, and store nothing
    # ONE ROW IS ONE DECLARATION: a second ref resolving to an address
    # another breakpoint declaration holds was stored over the same row, and clearing
    # either left the other declared over a row the debugger no longer had.
    if res["state"] == "armable":
        # The mode is the last stop's (the machine is stopped, and its mode changed last
        # when it ran), read from the record and not the console: a round trip per
        # declaration would be paid for a fact the survey already holds.
        last = STATE.last_machine()
        others = _bp_holders(session, last[0] if last else "", (res["seg"], res["off"]),
                             but=ref)
        if others:
            raise ds.Invalid("ambiguous_ref",
                f"{res['seg']:04X}:{res['off']:04X} is already declared under "
                             f"{others[0].ref!r}: one breakpoint row is one declaration, so "
                             f"clear that ref or use it")
    # DECLARED AGAIN IN THE OTHER MODE: the debugger fixed the row's address when it was made,
    # in that stop's mode, so the row that reads the same text is another byte now.
    before = next((d for d in current_store().declarations()
                   if d.kind == "breakpoint" and d.ref == ref), None)
    moved = (before is not None and None not in (before.cpu_mode, decl.cpu_mode)
             and before.cpu_mode != decl.cpu_mode)
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # A RE-DECLARATION IS A NO-OP, NOT A REFUSAL (owner's call at QA): the store keeps one
    # copy and says whether this call added it. The arming below still runs, so a
    # re-declared breakpoint whose debugger entry was lost (a new session) is re-armed.
    already = not is_new

    def pending() -> dict[str, Any]:
        # STORED, ARMED AT THE NEXT STOP: the guest runs. Said from two places (a refusal
        # before the arm, and one during it) in one shape.
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                        armed=False, state="pending", **STATE.queue_arm(ref))

    if res["state"] == "unresolved":
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unresolved",
                      note=f"{ref} is not a symbol in this build; the declaration is kept "
                           f"and arms nothing until a build defines it")
    if res["state"] == "unarmable":
        # STORED BUT NOT ARMABLE NOW: the machine is running (kept, armed at the next stop
        # and said so), or a real-mode table has no base yet (kept, said as unarmed).
        if not session.at_debugger():
            return pending()
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unarmable", why=res["why"])
    # ALREADY ARMED? A re-declaration must not stack a second debugger entry: if the row
    # is already held, this is a no-op arm. BOTH the check and the arm are inside the try,
    # because `session.breakpoints()` refuses a running machine exactly as `arm` does, and
    # a by-address ref reaches here without the machine having been touched yet -- so the
    # running case must answer `unarmed`, not escape as INVALID (which it did once).
    want = ("BP", res["seg"], res["off"])
    try:
        placement._listening(session)     # a running console would take the list unread
        existing = next((b for b in session.breakpoints()
                         if dcons.bp_row_target(b["entry"]) == want), None)
        if existing is not None and moved:
            session.clear_code_breakpoint(res["seg"], res["off"])
            existing = None
        held = existing or session.arm_code_breakpoint(res["seg"], res["off"])
    except ds.Invalid as e:
        # The machine is running (the intent is kept and armed at the next stop) or it
        # moved between resolving and arming (the intent is kept, said as unarmed). A
        # refusal of the running kind queues even if the peek says stopped by now: the
        # stop came between the two, and the next contact drains the queue at once.
        if isinstance(e, ds.NotStopped) or not session.at_debugger():
            return pending()
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unarmable", why=str(e))
    note = None
    if res["marked"]:
        note = (f"{ref} carries the linker's mark; a breakpoint on a marked address is one "
                f"whose firing is an open question, so this is said rather than assumed")
    STATE.note_armed(ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                      "entry": str(held["entry"])})
    return st.reply(ref=ref, by=chosen, stored=True, already_stored=already, armed=True,
                  state="armed", entry=held["entry"], marked=res["marked"], note=note)


def breakpoint_list(session: ds.Session) -> dict[str, Any]:
    """The body of the `breakpoint_list` tool."""
    store = current_store()
    held, read, machine = STATE.list_basis(session)
    places = RawPlaces(session)
    out: list[dict[str, Any]] = []
    mine: set[tuple[str, int, int]] = set()
    mine_int: set[str] = set()
    for decl in store.declarations():
        if decl.kind == "interrupt":
            # AN INTERRUPT HAS NO ADDRESS TO RESOLVE: its declaration IS its row text (the
            # debugger's `BPINT 21 ..` spelling), and its state is whether the debugger
            # still holds that row, matched by equality since the row has no seg:off.
            item = decl_row(decl)
            item["entry"] = decl.ref
            if orphan(decl):
                item["orphan"] = True
            if any(b["entry"] == decl.ref for b in held):
                item["state"] = "armed"
                mine_int.add(decl.ref)
            elif orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WHY
            else:
                item["state"] = "gone"
            out.append(item)
            continue
        if decl.kind != "breakpoint":
            continue
        item = decl_row(decl)
        res = placement.resolve_ref(decl, "CS", session, machine=machine)
        state = res["state"]
        # A STALE RAW ADDRESS IS LISTED AS SUCH, unless this session has it armed anyway
        # (then it is simply armed, and declaring it here has adopted it already). An
        # ORPHAN (no origin on file) carries the flag on every row and takes `orphan` as its
        # STATE only where the state would otherwise be `gone` or `stale`: a held row is
        # `armed`, an unresolved name is `unresolved`, because those facts decide what a
        # caller does next and "nobody's" does not replace them.
        if orphan(decl):
            item["orphan"] = True
        if state in ("unresolved", "ambiguous", "unarmable"):
            # An address the parser cannot read, or a name with no or two homes, is said
            # as such whatever build it was declared against: that is what decides what a
            # caller does next.
            item["state"] = state
            if "why" in res:
                item["why"] = res["why"]
        elif (mode := placement.waits(decl, places.cpu)) is not None:
            # Neither judged nor called armed here, the debugger's row included: in this mode
            # its SEG:OFF is another byte. That row is the declaration's, not foreign.
            item["state"] = "unarmable"
            item["why"] = placement.waits_why(mode, "Declare it again")
            mine.add(("BP", res["seg"], res["off"]))
        elif placement.is_stale(decl, places.judged(decl)) and not (
                state == "armable"
                and any(dcons.bp_row_target(b["entry"]) == ("BP", res["seg"], res["off"])
                        for b in held)):
            item["state"] = "orphan" if orphan(decl) else "stale"
            item["why"] = _ORPHAN_WHY if orphan(decl) else _STALE_WHY
        else:
            want = ("BP", res["seg"], res["off"])
            item["entry"] = f"BP {res['seg']:04X}:{res['off']:04X}"
            item["marked"] = res["marked"]
            if any(dcons.bp_row_target(b["entry"]) == want for b in held):
                item["state"] = "armed"
                mine.add(want)
            elif orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WHY
            else:
                item["state"] = "gone"
        out.append(item)
    for item in out:
        if item["ref"] in STATE.pending["arm"]:
            item["state"] = "pending"
            item.pop("why", None)
    # A ROW A CLEAR HAS QUEUED FOR REMOVAL is not foreign while it waits for the stop.
    queued = {str(sp["entry"]) for sp in STATE.pending["disarm"]}
    foreign = [b["entry"] for b in held
               if (t := dcons.bp_row_target(b["entry"])) is not None
               and t[0] == "BP" and t not in mine and b["entry"] not in queued]
    # A BPINT row the store did not place is foreign too, matched by its whole text since
    # an interrupt row carries no seg:off for `bp_row_target` to read.
    foreign += [b["entry"] for b in held
                if b["entry"].startswith("BPINT ") and b["entry"] not in mine_int
                and b["entry"] not in queued]
    return st.reply(breakpoints=out, foreign=foreign, debugger_read=read,
                  last_stop=None if read else STATE.as_of())


def _require_a_match(store: dec.DeclarationStore, ref: str | None,
                     kinds: tuple[str, ...]) -> str | None:
    """A `ref` that matches NO declaration of these kinds is refused, naming the refs the
    store holds. A zero in green is indistinguishable from "nothing to clear" for a caller
    who spelt the ref wrong, and that caller leaves the breakpoint armed (a `BPINT 21 4B`
    that cleared nothing where `BPINT 21 AH=4B` was the row).
    No `ref` means clear everything, and there an empty store's zero is the answer."""
    if ref is None:
        return None
    # AN ADDRESS MATCHES IN ANY SPELLING: the
    # stored spelling is what the caller's ref maps to, and what the loops then compare.
    mine = [d.ref for d in store.declarations() if d.kind in kinds]
    held = store.held_ref(ref, kinds)
    if held is not None:
        return held
    family = "breakpoint" if "breakpoint" in kinds else "watch"
    have = ", ".join(repr(r) for r in mine) if mine else "none at all"
    raise ds.Invalid("unknown_ref",
        f"{ref!r} matches no {family} declaration, so nothing was cleared. "
                     f"The {family} declarations this conf holds: {have}. A SEG:OFF "
                     f"matches in any spelling; a symbol or a `BPINT NN` / `BPINT NN "
                     f"AH=NN` row is the exact string the declaring reply carried")



def _pending_note(running: bool, pending: list[str]) -> str | None:
    """Why a row is still on the debugger after a clear, said truthfully: a running guest cannot
    take the command now and the row goes at the next stop; a STOPPED guest whose debugger refused
    the command is a different thing, and calling it "running" sends a caller to wait for a stop
    that has already happened. Either way the declarations are cleared now."""
    if not pending:
        return None
    if running:
        return ("the guest is running, so the debugger's rows for these are removed at the next "
                "stop (`applied_on_stop.disarmed`); the declarations are cleared now")
    return ("the debugger refused to remove these rows now (`pending_disarm`), so they are retried "
            "on the next call (`applied_on_stop.disarmed`); the declarations are cleared now")


def breakpoint_clear(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `breakpoint_clear` tool."""
    store = current_store()
    ref = _require_a_match(store, ref, ("breakpoint", "interrupt"))
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    # THE GUEST RUNS: the rows cannot be removed now, so they are queued for the next stop
    # and the declarations are dropped at once; a name resolves against the last stop's
    # machine, since the console cannot say what mode it is in.
    running = not session.at_debugger()
    for decl in store.declarations():
        if ref is not None and decl.ref != ref:
            continue
        if decl.kind == "breakpoint":
            # WHAT THIS SESSION ARMED for the ref is what gets removed, every row of it (a
            # reload can have armed a second); with no record, the live resolution is the
            # fallback while stopped, and NOTHING is queued while running: a row this
            # session never armed does not exist in an emulator this session started.
            rows = STATE.armed.pop(("bp", decl.ref), [])
            if not rows and not running:
                res = placement.resolve_ref(decl, "CS", session)
                if res["state"] == "armable":
                    rows = [{"kind": "bp", "seg": res["seg"], "off": res["off"],
                             "entry": f"BP {res['seg']:04X}:{res['off']:04X}"}]
            for spec in rows:
                if running:
                    STATE.pending["disarm"].append(spec)
                    STATE.pending["dirty"] = True
                    pending_disarm.append(str(spec["entry"]))
                    continue
                try:
                    gone = session.clear_code_breakpoint(spec["seg"], spec["off"])
                    if gone["removed"]:
                        disarmed.append(str(gone["entry"]))
                        STATE.snapshot_forget(str(gone["entry"]))
                except ds.Invalid:
                    STATE.pending["disarm"].append(spec)
                    STATE.pending["dirty"] = True
                    pending_disarm.append(str(spec["entry"]))
        elif decl.kind == "interrupt":
            rows = STATE.armed.pop(("bp", decl.ref), [])
            num, ah = dcons.parse_interrupt_row(decl.ref)
            if not rows and not running:
                rows = [{"kind": "int", "num": num, "ah": ah, "entry": decl.ref}]
            for spec in rows:
                if running:
                    STATE.pending["disarm"].append(spec)
                    STATE.pending["dirty"] = True
                    pending_disarm.append(decl.ref)
                    continue
                try:
                    gone = session.clear_interrupt_breakpoint(num, ah)
                    if gone["removed"]:
                        disarmed.append(str(gone["entry"]))
                        STATE.snapshot_forget(str(gone["entry"]))
                except ds.Invalid:
                    STATE.pending["disarm"].append(spec)
                    STATE.pending["dirty"] = True
                    pending_disarm.append(decl.ref)
    # Both families cleared here, so `kind` is not passed: a `ref` alone (or nothing)
    # takes breakpoints AND interrupts, and a caller wanting only one family clears by
    # ref. Watches are a different tool (decision 10's "without touching watches").
    removed = (store.remove(ref=ref, kind="breakpoint")
               + store.remove(ref=ref, kind="interrupt"))
    _unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=_pending_note(running, pending_disarm))


def _unqueue_cleared(store: dec.DeclarationStore) -> None:
    """The arm queue holds REFS, and a breakpoint and a watch may share one: after a clear, a
    queued ref stays while any family still declares it, and goes once none does."""
    held = {d.ref for d in store.declarations()}
    STATE.pending["arm"][:] = [r for r in STATE.pending["arm"] if r in held]


def _aliased(ref: str, seg: int, off: int) -> str | None:
    """The refusal when ANOTHER ref of this store already armed a watch at seg:off: two
    declarations sharing one debugger row would be disarmed together by a clear of either,
    in silence. One watchpoint is one declaration."""
    for (family, other), rows in STATE.armed.items():
        if family != "watch" or other == ref:
            continue
        if any(r["kind"] == "watch" and (r["seg"], r["off"]) == (seg, off) for r in rows):
            return (f"{seg:04X}:{off:04X} is already armed under {other!r}: one watchpoint is "
                    "one declaration, so clear that ref or use it")
    return None


def watch_add(session: ds.Session, ref: str, mode: str, width: int, fmt: str,
              by: str) -> dict[str, Any]:
    """The body of the `watch_add` tool."""
    placement.to_invalid(lambda: dec.check_watch_mode(mode))
    chosen = placement.decide_by(ref) if by == "auto" else by
    placement.address_shape(ref, chosen)
    if chosen == "pointer":
        # THE BASE IS JUDGED FIRST, so a ref with no pointer to start from (a stack local,
        # an untyped base under `->`) is refused for that and not for the format it could
        # not have named.
        probe = placement.resolve_ref(
            placement.to_invalid(lambda: dec.Declaration("watch", "pointer", ref, width=1,
                                                         fmt="u8", watch_mode="show")),
            "DS", session)
        if probe["state"] in ("unresolved", "ambiguous") and "why" in probe:
            raise ds.Invalid("unknown_ref", probe["why"])
    if fmt == "auto":
        # THE TYPE COMES FROM THE SYMBOL TABLE when the caller gave none (a `types` file
        # given to `symbols_load`); through a pointer, the named FIELD's own format; else
        # the default scalar, with the width the caller gave.
        typed = STATE.symbol_types.get(ref.strip().upper()) if chosen == "symbol" else None
        if chosen == "pointer":
            typed = vf.pointer_field_fmt(ref, STATE.symbol_types)
        if typed is not None and width == 0:
            fmt = typed
        elif width > 0:
            fmt = "u32" if width % 4 == 0 else "u16" if width % 2 == 0 else "u8"
        else:
            raise ds.Invalid("bad_argument",
                             f"a {mode} watch needs a length in bytes, or a fmt that names "
                             f"its size (u16[8], char[16], {{x:i16,y:i16}}), or a symbol "
                             f"the table types; {ref} has none of the three")
    try:
        width = vf.parse(fmt).width_for(width)
    except vf.FormatError as e:
        raise ds.Invalid("bad_argument", str(e)) from None
    checks.show_watch_width(mode, width)
    decl = declare("watch", chosen, ref, width=width, fmt=fmt, watch_mode=mode)
    stored = current_store().held_ref(ref, ("watch",))
    if stored is not None and stored != ref:
        # AN ADDRESS DECLARED AGAIN IN ANOTHER SPELLING IS THE SAME DECLARATION, and
        # it is handled under its stored spelling, the string a clear takes.
        ref, decl = stored, dataclasses.replace(decl, ref=stored)
    res = placement.resolve_ref(decl, "DS", session)
    # A NAME THAT MATCHES SEVERAL SYMBOLS IS REFUSED BEFORE STORING, as `breakpoint_at`
    # does: stored, the change path then read `seg` off a resolution that has none, and
    # the KeyError escaped with no session block.
    if res["state"] == "ambiguous":
        raise ds.Invalid("unknown_ref", res["why"])
    if mode == "change" and res["state"] == "armable":
        aliased = _aliased(ref, res["seg"], res["off"])
        if aliased is not None:
            raise ds.Invalid("ambiguous_ref", aliased)
    already = not cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # THROUGH A POINTER the reply says through what: where the pointer sits, its width,
    # what it holds, and the offset past it; a null pointer is a state the stop re-resolves.
    extra: dict[str, Any] = {"pointer": res["pointer"]} if "pointer" in res else {}
    if chosen == "pointer" and res["state"] in ("null_pointer", "unarmable"):
        return st.reply(ref=ref, by=chosen, mode=mode, fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=res["state"],
                      why=res["why"], **extra)
    if mode == "show":
        # A SHOW WATCH ARMS NOTHING (decision 29): a plain memory read at every stop, which
        # Phase 4 delivers. The declaration is stored; whether the symbol resolves yet only
        # decides whether it can be READ, not whether it is kept. The state is its
        # resolution, spelled the same way `watch_list` spells it (dec 12: one word per
        # concept) -- `resolved` when it has an address, else the reason it has none.
        state = "resolved" if res["state"] == "armable" else res["state"]
        return st.reply(ref=ref, by=chosen, mode="show", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=state, **extra)
    if res["state"] == "unresolved":
        return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state="unresolved",
                      note=f"{ref} is not a symbol in this build; kept, arms nothing yet")
    # ALREADY ARMED? A change-watch re-declared after a rebuild would otherwise stack a
    # second BPPM/BPM at the same address; if the row is held, this is a no-op arm. The
    # check is INSIDE the try for the same reason as breakpoint_at: `breakpoints()` and
    # `where()` refuse a running machine, and a by-address ref has not touched it yet.
    try:
        placement._listening(session)     # a running console would take the list unread
        if watch_held(session.breakpoints(), res["seg"], res["off"]) is not None:
            # ALREADY ARMED: a no-op re-declaration. It still carries the Pr caveat, because
            # a re-declared change-watch is as untrustworthy under paging as a fresh one --
            # returning None would drop the warning on exactly the repeated call a rebuild
            # workflow makes most.
            mode = session.where()["mode"]
            return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                          already_stored=already, armed=True, state="armed",
                          entry=_watch_entry(res["seg"], res["off"], mode),
                          caveat=_PR_WATCH_CAVEAT if mode.startswith("Pr") else None)
        armed = session.watch(segment=res["seg"], offset=res["off"])
    except ds.Invalid as e:
        if isinstance(e, ds.NotStopped) or not session.at_debugger():
            return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                          already_stored=already, armed=False, state="pending",
                          **STATE.queue_arm(ref))
        return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state="unarmable", why=str(e))
    caveat = _PR_WATCH_CAVEAT if str(armed["mode"]).startswith("Pr") else None
    STATE.note_armed(ref, {"kind": "watch", "seg": res["seg"], "off": res["off"],
                      "entry": str(armed["armed"])})
    return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                    already_stored=already, armed=True, state="armed", command=armed["command"],
                    entry=armed["armed"], caveat=caveat, **extra)


def watch_list(session: ds.Session) -> dict[str, Any]:
    """The body of the `watch_list` tool."""
    store = current_store()
    held, read, machine = STATE.list_basis(session)
    out: list[dict[str, Any]] = []
    mine: set[tuple[int, int]] = set()
    for decl in store.declarations():
        if decl.kind != "watch":
            continue
        item: dict[str, Any] = decl_row(decl)
        item.update(mode=decl.watch_mode, length=decl.width, fmt=decl.fmt)
        res = placement.resolve_ref(decl, "DS", session, machine=machine)
        state = res["state"]
        if "pointer" in res:
            item["pointer"] = res["pointer"]
        if orphan(decl):
            item["orphan"] = True
        if state in ("unresolved", "ambiguous", "unarmable", "null_pointer"):
            item["state"] = state
            if "why" in res:
                item["why"] = res["why"]
        elif decl.watch_mode == "show":
            # arms nothing; resolution is the whole state, unless it is nobody's, which is
            # the one thing a reader of every stop reply needs to know about it
            if orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WATCH_WHY
            else:
                item["state"] = "resolved"
        else:
            seg, off = res["seg"], res["off"]
            item["entry"] = _watch_entry(seg, off, machine[0] if machine is not None
                                         else session.where()["mode"])
            # Match by the NUMBERS (a watch family kind at this seg:off), never by a
            # reconstructed spelling: the debugger's offset width is not fixed (one address
            # was listed as both `BPPM 00AF:6024` and `BPPM 00AF:00006024`), so an equality
            # or prefix test on the spelling reports an armed watch as gone.
            if watch_held(held, seg, off):
                item["state"] = "armed"
                mine.add((seg, off))
            elif orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WHY
            else:
                item["state"] = "gone"
        out.append(item)
    for item in out:
        if item["ref"] in STATE.pending["arm"]:
            item["state"] = "pending"
            item.pop("why", None)
    queued = {(sp["seg"], sp["off"]) for sp in STATE.pending["disarm"] if sp["kind"] == "watch"}
    foreign = [b["entry"] for b in held
               if (t := dcons.bp_row_target(b["entry"])) is not None
               and t[0] in _WATCH_KINDS and (t[1], t[2]) not in mine
               and (t[1], t[2]) not in queued]
    return st.reply(watches=out, foreign=foreign, debugger_read=read,
                  last_stop=None if read else STATE.as_of())


def watch_clear(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `watch_clear` tool."""
    store = current_store()
    ref = _require_a_match(store, ref, ("watch",))
    to_go = [d for d in store.declarations()
             if d.kind == "watch" and (ref is None or d.ref == ref)]
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    running = not session.at_debugger()
    for decl in to_go:
        if decl.watch_mode == "show":
            STATE.armed.pop(("watch", decl.ref), None)
            continue                 # armed nothing
        rows = STATE.armed.pop(("watch", decl.ref), [])
        if not rows and not running:
            res = placement.resolve_ref(decl, "DS", session)
            if res["state"] == "armable":
                rows = [{"kind": "watch", "seg": res["seg"], "off": res["off"],
                         "entry": _watch_entry(res["seg"], res["off"],
                                               session.where()["mode"])}]
        for spec in rows:
            seg, off, entry = spec["seg"], spec["off"], str(spec["entry"])
            if running:
                STATE.pending["disarm"].append(spec)
                STATE.pending["dirty"] = True
                pending_disarm.append(entry)
                continue
            try:
                row = watch_held(session.breakpoints(), seg, off)
                if row is None:
                    continue
                session.command(f"BPDEL {row['index']}")
                # READ THE LIST BACK, as `clear_code_breakpoint` does: `disarmed` is the
                # machine's answer, not this tool's claim that a BPDEL it sent must have taken.
                if watch_held(session.breakpoints(), seg, off) is None:
                    disarmed.append(row["entry"])
                    STATE.snapshot_forget(str(row["entry"]))
            except ds.Invalid:
                STATE.pending["disarm"].append(spec)
                STATE.pending["dirty"] = True
                pending_disarm.append(entry)
    removed = store.remove(ref=ref, kind="watch")
    _unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=_pending_note(running, pending_disarm))
