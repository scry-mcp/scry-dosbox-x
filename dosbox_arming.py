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

import contextlib
import dataclasses
import functools
from collections.abc import Callable
from typing import Any, cast

from scry_core import declaration_rows
from scry_core import value_format as vf

import dosbox_checks as checks
import dosbox_code as code
import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_dump as dumping
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
import dosbox_symbol_file as symbol_file
from dosbox_state import STATE


def declare(kind: str, by: str, ref: str, linear: int | None = None,
            cpu: str | None = None, **watch: Any) -> dec.Declaration:
    """A declaration stamped with this session's origin, the clock, the build of the batch
    that describes `linear`, its place now (`placement.stamp_at`), and for a raw row the mode
    of the stop that placed it (`cpu`; None where no stop did, or the guest runs): the one
    place the declaring tools build one, so none of them can forget the stamp."""
    raw = dec.is_raw_code(kind, by)
    mode = placement.mode_word(cpu) if dec.keeps_mode(kind, by) else None
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
                real = last is not None and dcons.real_segments(last[0])
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

    def mode_here(self, by: str, ref: str) -> str | None:
        """The cpu mode this stop gives a raw row, in the debugger's spelling: its own, but none
        at a real-mode stop that cannot place it (an offset past FFFF) or while the guest runs.
        A protected-mode stop gives its mode whether or not it can read the selector's base:
        the debugger arms by the selector, so the SEG:OFF is read in this mode either way."""
        if not self.session.at_debugger():
            return None
        cpu = self.cpu()
        if self._segs is None:            # this stop's survey was refused: the mode is not its
            return None
        if dcons.real_segments(cpu or "") and self.place(by, ref) is None:
            return None
        return cpu

    def unsurveyed(self) -> bool:
        """At a stop whose survey, once asked for (`mode_here`, `cpu`), was refused: this instant
        cannot say a row's mode, which is the survey's failure and not the row's."""
        return self._segs is None and self.session.at_debugger()

    def cpu(self) -> str | None:
        """This stop's cpu mode as the debugger spells it, off the same survey; the last stop's
        while the guest runs or when the survey is refused, None before any."""
        if self._segs is None and self.session.at_debugger():
            with contextlib.suppress(ds.Invalid):
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


_STALE_WHY = ("no map held now vouches for this raw address (it was stamped under another conf "
              "or map, under none, or where no stop could tell): kept and never re-armed here, "
              "because it re-resolves against nothing. Declare it again to adopt it, or clear "
              "it by this ref")
_ORPHAN_WHY = ("no origin is recorded on it, so it is nobody's: clear it by this ref, or "
               "declare it again to adopt it")
_ORPHAN_WATCH_WHY = _ORPHAN_WHY + ". A show watch is still EVALUATED at every stop while it is here"


def orphan(decl: dec.Declaration) -> bool:
    """A declaration with no origin recorded, in a session that HAS one: written by a store
    from before origins were kept: such a show watch sits in every stop reply with no origin
    and nothing tells it from this session's. With
    no session origin at all (the contract harness never calls `start`) nothing is an
    orphan: there is no "this session's" to tell it from."""
    return decl.origin is None and STATE.session_origin is not None


def decl_row(decl: dec.Declaration) -> dict[str, Any]:
    """The fields every listed declaration carries (`scry_core.declaration_rows`): its ref, how
    it was declared, the cpu, when and in which session (`origin`), whether that session is this
    one (`inherited`) and how old it is."""
    return declaration_rows.row(ref=decl.ref, by=decl.by, cpu=None, cpu_why=ONE_CPU_WHY,
                                created_at=decl.created_at, origin=decl.origin,
                                own_origin=STATE.session_origin, now=st.utc_now())


#: Why no DOSBox-X row names a cpu.
ONE_CPU_WHY = "a DOS machine has one cpu, and every row acts on it"


# The BPLIST kind tokens for a memory watch, told apart from a code breakpoint (`BP`) and
# an interrupt (`BPINT`): protected paged, real, and linear.
_WATCH_KINDS = ("BPPM", "BPMEM", "BPLM")
# The kinds this server arms, at a SEG:OFF. `BPLM` watches a linear address and is never this
# server's: one at the linear address a real-mode SEG:OFF names is still somebody else's row.
_OWN_WATCH_KINDS = ("BPPM", "BPMEM")

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
        if t is not None and t[0] in _OWN_WATCH_KINDS and (t[1], t[2]) == (seg, off):
            return b
    return None


def change_bytes(seg: int, off: int, width: int | None) -> list[tuple[int, int]]:
    """Every byte a change watch of `width` bytes at seg:off arms a row for: the debugger's
    memory breakpoint compares one byte, so a watch over more is a row per byte."""
    return [(seg, off + i) for i in range(max(int(width or 1), 1))]


def reachable_bytes(seg: int, off: int, width: int | None,
                    mode: str) -> list[tuple[int, int]]:
    """`change_bytes`, refused whole when its last byte is past the offset `mode` reaches: judged
    before the first row goes in, so no part of a watch is armed under a reply that says it is
    not."""
    places = change_bytes(seg, off, width)
    last, top = places[-1][1], dcons.offset_ceiling(mode)
    if last > top:
        raise ds.Invalid("bad_argument",
            f"a change watch of {len(places)} bytes at {dcons.canonical_seg_off(seg, off)} ends at "
            f"offset 0x{last:X}, past the 0x{top:X} an offset reaches in {mode} mode: no row was "
            "armed")
    return places


def _mode(session: ds.Session, machine: tuple[str, dict[str, str]] | None) -> str:
    return machine[0] if machine is not None else session.where()["mode"]


def all_held(held: list[dict[str, str]], places: list[tuple[int, int]]) -> bool:
    """Whether the debugger lists a memory watch at every one of `places`."""
    return all(watch_held(held, seg, off) is not None for seg, off in places)


def render_watch(raw: bytes, width: int, fmt: str) -> vf.Value:
    """`width` bytes read as `fmt`, little-endian (x86): one value, a list, a string or a
    struct, as the format grammar says (`value_format`)."""
    return vf.parse(fmt).decode(raw, "little", width)


def evaluate_watches(session: ds.Session, *,
                      machine: tuple[str, dict[str, str]] | None = None,
                      held: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every watch declaration, EVALUATED at this stop: its bytes read and rendered, a show
    watch's state `evaluated`, a break-on-change watch's `armed` or `gone` (whether the
    debugger still holds it). A watch that no longer resolves, or whose bytes cannot be read,
    is listed with why, never a value at a guessed address.
    """
    if STATE.store is None:
        return []
    # `held` is the list the stop already read off its one repaint (`stop_survey`); only a
    # caller with no stop in hand pays a fresh read.
    if held is None:
        held = session.breakpoints()
    places = RawPlaces(session)
    out: list[dict[str, Any]] = []
    for decl in STATE.store.declarations():
        if decl.kind != "watch":
            continue
        item: dict[str, Any] = {"ref": decl.ref, "by": decl.by, "mode": decl.watch_mode,
                                "length": decl.width, "fmt": decl.fmt}
        if orphan(decl):
            item["orphan"] = True       # nobody's: from a store that kept no origin
        if _watch_waits(item, decl, places, machine):
            out.append(item)
            continue
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
            moved = _follow(session, decl, seg, off, _mode(session, machine))
            if moved is not None:
                item["moved"] = moved
                held = session.breakpoints()
                recorded = [r for r in STATE.armed.get(("watch", decl.ref), [])
                            if r["kind"] == "watch"]
                if recorded and all((r["seg"], r["off"]) != (seg, off) for r in recorded):
                    # the new rows were refused: the watch is judged where it is still armed
                    first = min(recorded, key=lambda r: (r["seg"], r["off"]))
                    seg, off = int(first["seg"]), int(first["off"])
        # A CHANGE WATCH IS READ AS A SHOW WATCH IS: the debugger's memory breakpoints write
        # nothing into the memory they watch, so its bytes are the program's; its state says
        # whether the debugger still holds it, and a read that fails leaves that state with why.
        change = decl.watch_mode == "change"
        if change:
            item["state"] = ("armed" if all_held(held, change_bytes(seg, off, decl.width))
                             else "gone")
        try:
            # THE CACHED MODE: a show watch's read_bytes would else
            # re-survey the machine for its offset ceiling -- N watches, N surveys of a
            # screen the stop already read. `machine[0]` is that mode; passed only when the
            # caller cached it, which the stop reply does.
            mode = machine[0] if machine is not None else None
            raw = session.read_bytes(seg, off, cast(int, decl.width), mode=mode)
        except ds.Invalid as e:
            if not change:
                item["state"] = "unreadable"
            item["why"] = str(e)
            out.append(item)
            continue
        if not change:
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
    in real mode, where many spellings alias one byte), other than `but`, whatever their row's
    state: one row is one declaration, armed or not."""
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
                    held: list[dict[str, str]],
                    retrace_may_stop: bool = False) -> dict[str, Any]:
    """WHICH declaration the stop is at, BY ADDRESS COMPARISON, or an honest cannot-say.
    A code breakpoint whose resolved address equals CS:EIP is named. Nothing
    else is claimed: the debugger records no hit flag, and a memory watch stops at the
    instruction that WROTE, not at the watched address, so from a stop there is no
    arithmetic back to a watch declaration. Guessing one would be the confident wrong answer.
    A store from before the one-row rule can hold two declarations at one address: every
    one is named (`refs`), the first stays `ref`, and `note` says so, instead of the first
    in silence.

    `where` and `machine` are read once by the caller: attribution over M
    breakpoints would otherwise re-read the machine M times for a state fixed at this stop.
    `held` is the debugger's list at this stop, off the same repaint: a declaration whose row it
    does not hold there (queued, another build's, waiting for its mode) did not make the stop,
    and is not named.

    `retrace_may_stop` is a stop reached by a release that ran on (`resume`, a `run_to` that did
    not arrive, a stop found on its own): a retrace `run_for` left armed is the likeliest cause
    of such a stop when no declaration explains it, so it is named and forgotten there. Any other
    stop (a step, a `stop`, an arrival) is its caller's own and leaves it armed.
    """
    stop = (int(where["cs"], 16), int(where["eip"], 16))
    mode = where["mode"]
    holders = _bp_holders(session, mode, stop, machine=machine)
    rows = [t[1:] for t in map(dcons.bp_row_target, (b["entry"] for b in held))
            if t is not None and t[0] == "BP"]
    if not any(_same_code_addr(mode, stop, row) for row in rows):
        holders = []
    if holders:
        out: dict[str, Any] = {"attributed": True, "ref": holders[0].ref, "by": holders[0].by,
                               "at": st.seg_off(*stop)}
        if len(holders) > 1:
            out["refs"] = [d.ref for d in holders]
            out["note"] = f"{len(holders)} declarations resolve to this address: all are named"
        return out
    if retrace_may_stop and STATE.retrace_pending:
        STATE.retrace_pending = False
        return {"attributed": False, "retrace_pending": True,
                "at": st.seg_off(*stop),
                "why": "the stop address matches no declared code breakpoint, and a `run_for` "
                       "had left a retrace stop armed, which stops the next release at the next "
                       "retrace: most likely this stop"}
    return {"attributed": False,
            "at": st.seg_off(*stop),
            "why": "the stop address matches no declared code breakpoint. The debugger "
                   "keeps no hit flag, and a memory watch stops at the WRITING instruction "
                   "rather than the watched address, so which declaration fired cannot be "
                   "derived from the stop"}


def _follow(session: ds.Session, decl: dec.Declaration, seg: int, off: int,
            mode: str) -> dict[str, str] | None:
    """A change watch whose pointer now points elsewhere: the rows at the new place, one per byte
    (`change_bytes`), are armed first, and the old rows deleted once the new ones are held.
    `{from, to}` when it moved, None when every byte is where it was. A debugger that refuses a
    new row leaves the old rows armed and `why` beside `from`/`to`; one that keeps an old row
    (its delete refused, or not taken) leaves it in the record, says so in `why`, and the delete
    is tried again at the next stop."""
    rows = STATE.armed.get(("watch", decl.ref), [])
    mine = [r for r in rows if r["kind"] == "watch"]
    try:
        want = reachable_bytes(seg, off, decl.width, mode)
    except ds.Invalid as e:
        return {"from": st.seg_off(mine[0]["seg"], mine[0]["off"]) if mine else "null",
                "to": st.seg_off(seg, off), "why": str(e)}
    stale = [r for r in mine if (r["seg"], r["off"]) not in want]
    have = {(r["seg"], r["off"]) for r in mine}
    missing = [place for place in want if place not in have]
    if not missing:
        _drop_stale(session, rows, stale)
        return None
    old = min(stale, key=lambda r: (r["seg"], r["off"])) if stale else None
    # A watch declared while the pointer was NULL armed nothing: the stop that finds the
    # pointer set arms it, and says it came from null.
    where = {"from": st.seg_off(old["seg"], old["off"]) if old is not None else "null",
             "to": st.seg_off(seg, off)}
    # THE NEW ROWS FIRST, the old ones only once the new are held: a refusal then leaves the
    # watch armed where it was and `why` beside `from`/`to`.
    try:
        for (s_, o_), armed in zip(missing, session.watch_places(missing), strict=True):
            STATE.note_armed(decl.ref, {"kind": "watch", "seg": s_, "off": o_,
                                        "entry": str(armed["armed"])})
    except ds.Invalid as e:
        return {**where, "why": str(e)}
    kept = _drop_stale(session, rows, stale)
    if kept:
        where["why"] = (f"the old row was not deleted ({kept}): the watch is armed at both "
                        "places until the next stop deletes it")
    return where


def delete_watch_rows(session: ds.Session,
                      places: list[tuple[int, int]]) -> tuple[list[str], list[tuple[int, int]]]:
    """The memory-watch rows at `places` deleted: ONE read of the list, a `BPDEL` each from the
    highest index down, and ONE read back. A delete renumbers only the rows below it, so taking
    them highest first keeps every index read from that one list true. The rows the read back
    no longer lists, and the places it still does."""
    listed = session.breakpoints()
    found = [(place, row) for place in dict.fromkeys(places)
             if (row := watch_held(listed, *place)) is not None]
    for _, row in sorted(found, key=lambda pr: int(pr[1]["index"]), reverse=True):
        session.command(f"BPDEL {row['index']}")
    after = session.breakpoints() if found else listed
    gone = [str(row["entry"]) for place, row in found if watch_held(after, *place) is None]
    return gone, [place for place, _ in found if watch_held(after, *place) is not None]


def _drop_stale(session: ds.Session, rows: list[dict[str, Any]],
                stale: list[dict[str, Any]]) -> str:
    """The rows of a moved watch at a place it no longer points to deleted from the debugger and
    then from the record; one the debugger still lists after its `BPDEL` stays in both. What
    kept one, or an empty string."""
    if not stale:
        return ""
    # THE LIST IS READ WHEN THE DELETES ARE MADE, never handed in: the debugger lists a row just
    # armed first, so a list read before an arm gives every older row the wrong index.
    try:
        _, kept = delete_watch_rows(session, [(int(r["seg"]), int(r["off"])) for r in stale])
    except ds.Invalid as e:
        return str(e)
    rows[:] = [r for r in rows if r not in stale or (int(r["seg"]), int(r["off"])) in kept]
    return "the debugger still lists it" if kept else ""


#: The buckets of a re-arm's account, each a list of `decl_row`s, `why` on the last three.
REARM_BUCKETS = ("rearmed", "stale", "unresolved", "ambiguous", "unarmable")


def rearm_declarations(session: ds.Session) -> dict[str, Any]:
    """Re-resolve every stored declaration against the just-loaded table and arm the code
    ones that resolve and are not already held; a held one stays as it is and is in no bucket.
    The re-arm: a breakpoint declared
    by name is meant to survive a rebuild and re-place itself. It arms nothing for an
    unresolved or ambiguous name -- those are listed, never guessed at. The account is one
    list of rows per bucket (`REARM_BUCKETS`), each row `decl_row`'s, so a row another session
    left says whose it is and how old as it re-arms.
    """
    out: dict[str, Any] = {key: [] for key in REARM_BUCKETS}
    if STATE.store is None:
        return out
    held = {dcons.bp_row_target(b["entry"]) for b in session.breakpoints()}
    places = RawPlaces(session)
    for decl in STATE.store.declarations():
        if decl.kind != "breakpoint":
            continue
        row = decl_row(decl)
        res = placement.resolve_ref(decl, "CS", session)
        state = res["state"]
        if state in ("unresolved", "ambiguous", "unarmable"):
            out[state].append({**row, **({"why": res["why"]} if "why" in res else {})})
        elif ("BP", res["seg"], res["off"]) in held:
            continue              # already armed, by this session or by a symbol's re-arm
        # A RAW ADDRESS PLACED IN THE OTHER MODE, OR BY NO STOP, waits for a stop of its own:
        # read here, its SEG:OFF may be another byte. `start` parks in real mode, so a
        # protected-mode row is re-armed by a `symbols_load` at a protected-mode stop, never at
        # the park, and a row no stop placed is re-armed nowhere until one does.
        elif (mode := placement.waits(decl, places.cpu)) is not None:
            if mode == dec.UNPLACED and _stored_before_modes(decl):
                # ONE ROW THAT CANNOT BE ADOPTED IS THAT ROW'S ANSWER, never the whole re-arm's.
                try:
                    adopted = _adopted(session, decl, res, places)
                except ds.Invalid as e:
                    out["unarmable"].append({**row, "why": str(e)})
                    continue
                if adopted is not None:
                    out["rearmed"].append({**row, **adopted})
                    continue
            out["unarmable"].append({**row, "why": placement.waits_why(mode, "Declare it again")})
        # A RAW ADDRESS FROM ANOTHER BUILD IS NOT RE-ARMED (decided per build): it re-resolves
        # against nothing, and armed blind on a relinked program it lands wherever the linker
        # put something else. It stays in the store, is NAMED here
        # and listed `stale`, and declaring it again adopts it. Tested AFTER `held`, so a
        # row the debugger holds anyway is never called stale here and `armed` in the list.
        elif placement.is_stale(decl, places.judged(decl)):
            out["stale"].append(row)
        else:
            try:
                session.arm_code_breakpoint(res["seg"], res["off"])
                STATE.note_armed(decl.ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                                       "entry": f"BP {res['seg']:04X}:{res['off']:04X}"})
                out["rearmed"].append(row)
            except ds.Invalid as e:
                # the machine moved under us; the intent is kept
                out["unarmable"].append({**row, "why": str(e)})
    return out


def arm_at_start(session: ds.Session) -> dict[str, Any]:
    """At `start`, the machine parked: arm again the raw addresses an earlier session declared
    over THIS build, which is what the per-build rule promises and what nothing else does
    before the first `symbols_load`. Another build's stay `stale`. The reply's part is
    `declarations.rearm`, the account `rearm_declarations` gives; with no breakpoint to arm,
    the debugger's list is not read, so a start with nothing declared costs no round trip, and
    each stored breakpoint is listed where the park leaves it.

    The session is already installed when this runs, so a refusal here is handed back for
    `start`'s reply (`rearm_refused`) rather than raised: raised, it would answer INVALID over
    a live emulator. The declarations stay stored either way."""
    if STATE.store is None or not any(
            d.kind == "breakpoint" and d.by == "address"
            and not placement.is_stale(d, _nowhere)
            for d in STATE.store.declarations()):
        return {"declarations": {"rearm": _unarmed_at_start()}}
    try:
        return {"declarations": {"rearm": rearm_declarations(session)}}
    except ds.Invalid as e:
        return {"declarations": {"rearm": _unarmed_at_start(str(e))}, "rearm_refused": str(e)}


def _unarmed_at_start(refused: str = "") -> dict[str, Any]:
    """The account of a park that armed nothing, every stored breakpoint by its state there,
    read without the console: a name waits for the table; a raw address of another build is
    stale, and one of this build is unarmable with the re-arm's `refused` reason."""
    out: dict[str, Any] = {key: [] for key in REARM_BUCKETS}
    for decl in STATE.store.declarations() if STATE.store is not None else []:
        if decl.kind != "breakpoint":
            continue
        row = decl_row(decl)
        if decl.by != "address":
            out["unresolved"].append({**row, "why": NO_TABLE_WHY})
        elif refused and not placement.is_stale(decl, _nowhere):
            out["unarmable"].append({**row, "why": refused})
        else:
            out["stale"].append(row)
    return out


#: Why a name is not re-armed at the park: the table it resolves in is loaded later.
NO_TABLE_WHY = "no symbol table is loaded yet: `symbols_load` re-arms it"


def apply_pending(session: ds.Session) -> dict[str, Any]:
    """At a stop, do what the guest's running kept the console from doing: load the symbols
    that were parsed and held, remove the rows a clear left behind, arm what was declared.
    Returns the account, empty when nothing was pending. Each half is attempted on its own:
    a refusal on one (a symbol that no longer resolves) is reported, not allowed to hold the
    others back, and what could not be applied stays pending for the next stop."""
    if not (STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["load"] is not None
            or STATE.pending["remeasure"]):
        return {}
    STATE.pending["dirty"] = False
    STATE.pending["drained_seq"] = STATE.last_stop.get("seq", 0)
    out: dict[str, Any] = {"symbols_loaded": False, "disarmed": [], "armed": [],
                           "still_pending": []}
    # THE CLEARS FIRST: a row a clear queued is gone before the load's re-arm reads the list, so a
    # breakpoint declared again after its clear is armed again, never counted armed over a row
    # this same stop deletes.
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
    if STATE.pending["load"] is not None and (full := symbol_file.vars_overflow(
            session, cast(bytes, STATE.pending["load"]))) is not None:
        # A LOAD NO STOP OF THIS SESSION CAN TAKE is dropped, said once, never retried at each.
        STATE.pending["load"] = None
        out["still_pending"].append(f"symbols_load, dropped: {full}")
    if STATE.pending["load"] is not None:
        try:
            session.load_symbols(cast(bytes, STATE.pending["load"]))
            STATE.pending["load"] = None
            out["symbols_loaded"] = True
        except ds.Invalid as e:
            out["still_pending"].append(f"symbols_load: {e}")
        if out["symbols_loaded"]:
            # THE MAP IS TAKEN HERE, as a load at a stop takes it: this session's rows no stop
            # had placed are stamped with the batch that now describes them, before the re-arm
            # judges them. Imported at the call: the comments module is built on this one.
            import dosbox_comments
            unwritten = dosbox_comments.park_rows_take_the_map(session)
            if unwritten is not None:
                out["still_pending"].append(
                    f"taking the map: {unwritten}; the rows this session placed before any map "
                    "keep their place as it was, and a later load takes them")
            # THE RE-ARM THAT FOLLOWS EVERY LOAD, which the pending reply promised. The load is
            # done whatever this answers, so a re-arm that fails puts the breakpoints it would
            # have armed (never a raw address of another build) on the queue the loop below
            # works through now, and what that cannot arm stays queued for the next stop.
            try:
                out["armed"].extend(r["ref"] for r in rearm_declarations(session)["rearmed"])
            except ds.Invalid as e:
                out["still_pending"].append(f"the re-arm after the load: {e}")
                for decl in _armable_declarations():
                    if decl.kind == "breakpoint" and decl.ref not in STATE.pending["arm"]:
                        STATE.pending["arm"].append(decl.ref)
    if STATE.pending["remeasure"]:
        _remeasure(session, out)
    kept_arm: list[str] = []
    places = RawPlaces(session)
    if STATE.store is not None and STATE.pending["arm"]:
        # ONE machine reading and ONE list read for every ref, not one per
        # ref: at a console round trip apiece, three refs cost seconds otherwise.
        try:
            where, regs = session.where_and_registers()
            machine: tuple[str, dict[str, str]] | None = (where["mode"], regs)
            held = session.breakpoints()
        except ds.Invalid:
            machine, held = None, []
        for ref in STATE.pending["arm"]:
            rearmed = ref in out["armed"]    # by the load, which re-arms breakpoints only
            # EVERY DECLARATION UNDER THE REF: the queue holds a ref once, and a breakpoint and
            # a watch declared at one address while the guest ran are both waiting on it. Each
            # family's arm checks the list first, so one armed at an earlier stop is not doubled.
            for decl in [d for d in STATE.store.declarations()
                         if d.ref == ref and not (d.kind == "watch" and d.watch_mode != "change")]:
                if rearmed and decl.kind == "breakpoint":
                    continue
                if _arm_queued(session, decl, machine, held, places, out):
                    continue
                if ref not in kept_arm:
                    kept_arm.append(ref)
            if ref not in kept_arm and not rearmed \
                    and any(d.ref == ref for d in STATE.store.declarations()):
                out["armed"].append(ref)
    STATE.pending["arm"][:] = kept_arm
    if not out["still_pending"]:
        del out["still_pending"]
    if not (out["symbols_loaded"] or out["disarmed"] or out["armed"]
            or out.get("still_pending") or "base_remeasured" in out):
        return {}
    # ACCUMULATED, NOT REPLACED: `live()` may have drained part of the queue a moment
    # before a stop tool drains the rest, and the reply must carry BOTH accounts as one
    # (measured: a drain in `live()` followed by the stop's own lost the first's disarms).
    merge_applied(out)
    return out


def _arm_queued(session: ds.Session, decl: dec.Declaration,
                machine: tuple[str, dict[str, str]] | None, held: list[dict[str, Any]],
                places: RawPlaces, out: dict[str, Any]) -> bool:
    """Arm one queued declaration at the stop, noting the row; False, with why in
    `out["still_pending"]`, when it cannot be armed yet."""
    ref = decl.ref
    try:
        if decl.kind == "interrupt":
            num, ah = dcons.parse_interrupt_row(decl.ref)
            if not any(b["entry"] == decl.ref for b in held):
                session.breakpoint_interrupt(num, ah)
            STATE.note_armed(ref, {"kind": "int", "num": num, "ah": ah, "entry": decl.ref})
        elif decl.kind == "watch":
            cpu = _waits_at(decl, places)
            res = placement.resolve_ref(decl, "DS", session, machine=machine)
            if res["state"] != "armable":
                raise ds.Invalid("unknown_ref", str(res.get("why", res["state"])))
            covered = reachable_bytes(res["seg"], res["off"], decl.width,
                                      _mode(session, machine))
            aliased = _aliased(ref, covered)
            if aliased is not None:
                raise ds.Invalid("ambiguous_ref", aliased)
            missing = [place for place in covered if watch_held(held, *place) is None]
            made = dict(zip(missing, session.watch_places(missing), strict=True)) if missing else {}
            for place in covered:
                row = watch_held(held, *place)
                entry = row["entry"] if row is not None else str(made[place]["armed"])
                if row is None:
                    held.append({"index": "?", "entry": entry})   # the list learns the row
                STATE.note_armed(ref, {"kind": "watch", "seg": place[0], "off": place[1],
                                       "entry": entry})
            _placed_here(decl, places, cpu)
        else:
            cpu = _waits_at(decl, places)
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
            _placed_here(decl, places, cpu)
    except ds.Invalid as e:
        out["still_pending"].append(f"arm {ref} ({decl.kind}): {e}")
        return False
    return True


#: How far past the table's last symbol a stop still counts as the program's code: the last
#: routine's body, which no symbol bounds. A stop in a DPMI host or another program lies outside
#: the program's span by far more.
PROGRAM_TAIL = 0x10000


def _remeasure(session: ds.Session, out: dict[str, Any]) -> None:
    """The first stop IN THE PROGRAM'S CODE after a state load measures the table's base again,
    through the register the load measured it from, and the program's selectors with it: the
    restored machine may hold the program elsewhere, under other selectors, and a symbol placed
    through the old base or armed through the old selector would name another byte. The program's
    code is a protected-mode stop whose `EIP` falls within the table's span (`PROGRAM_TAIL`
    past its last symbol): a real-mode handler, a DPMI host's code or another program waits for
    the next stop, as one that cannot be measured does. A base that moved moves the table and
    re-arms what is declared by name."""
    reg = STATE.base_measured_from
    if reg is None or not STATE.table:
        STATE.pending["remeasure"] = False
        return
    try:
        where, regs = session.where_and_registers()
        offsets = [s.offset for s in STATE.table]
        eip = int(where.get("eip", "-1"), 16)
        if (not where["mode"].startswith("Pr") or not {"CS", "DS"} <= set(regs)
                or not min(offsets) <= eip <= max(offsets) + PROGRAM_TAIL):
            out["still_pending"].append(
                "measuring the table's base again after the load: this stop is not in the "
                "program's protected-mode code, so the next one that is measures it")
            return
        desc = session.selector(reg)
    except (ds.Invalid, ValueError) as e:
        out["still_pending"].append(f"measuring the table's base again after the load: {e}")
        return
    selectors = {f"selector_{r}": int(regs[r], 16) for r in ("CS", "DS")}
    STATE.pending["remeasure"] = False
    old = STATE.base.get("base", -1)
    moved = {**{k: desc[k] for k in placement.PLACE_KEYS}, **selectors}
    if all(STATE.base.get(k) == v for k, v in moved.items()):
        return
    STATE.base.update(moved)
    if old != desc["base"]:
        out["base_remeasured"] = {"register": reg, "from": f"{old:#010x}",
                                  "to": f"{desc['base']:#010x}"}
    _disarm_by_name(session, out)
    # THE BASE HAS MOVED WHATEVER THE RE-ARM ANSWERS: one that fails queues what it would have
    # armed, as the re-arm after a load does.
    try:
        out["armed"].extend(r["ref"] for r in rearm_declarations(session)["rearmed"])
    except ds.Invalid as e:
        out["still_pending"].append(f"the re-arm after the base was measured again: {e}")
        for decl in _armable_declarations():
            if decl.kind == "breakpoint" and decl.ref not in STATE.pending["arm"]:
                STATE.pending["arm"].append(decl.ref)


def _disarm_by_name(session: ds.Session, out: dict[str, Any]) -> None:
    """The code breakpoints armed by NAME before the base moved, cleared from the debugger: its
    rows outlive a state load, and on the restored machine their old places are someone else's
    bytes. A reload keeps them (the same machine, see `STATE.note_armed`); a replaced machine
    does not. One that cannot be cleared stays queued to disarm."""
    by_name = {d.ref for d in current_store().declarations()
               if d.kind == "breakpoint" and d.by == "symbol"}
    for (fam, ref), rows in list(STATE.armed.items()):
        if fam != "bp" or ref not in by_name:
            continue
        for spec in [r for r in rows if r.get("kind") == "bp"]:
            try:
                session.clear_code_breakpoint(spec["seg"], spec["off"])
            except ds.Invalid as e:
                out["still_pending"].append(f"clearing {spec['entry']} after the base moved: {e}")
                STATE.pending["disarm"].append(spec)
            rows.remove(spec)
        if not rows:
            del STATE.armed[(fam, ref)]


def merge_applied(account: dict[str, Any]) -> None:
    """One drain's account joined into `STATE.applied_last`: the lists accumulate, a load of
    symbols is kept once any drain made one, and what is still pending is the latest word."""
    merged = STATE.applied_last
    for key in ("disarmed", "armed"):
        if key in account:
            merged[key] = list(merged.get(key, [])) + list(account[key])
    if "base_remeasured" in account:
        merged["base_remeasured"] = account["base_remeasured"]
    if "symbols_loaded" in account:
        merged["symbols_loaded"] = (bool(merged.get("symbols_loaded"))
                                    or bool(account["symbols_loaded"]))
    if "still_pending" in account:
        merged["still_pending"] = list(account["still_pending"])
    else:
        merged.pop("still_pending", None)


def _waits_at(decl: dec.Declaration, places: RawPlaces) -> str | None:
    """The mode this stop gives a queued raw row (None for a symbol), refused when the row waits
    here: placed in the other mode, or this stop cannot place it. It stays queued."""
    if not dec.keeps_mode(decl.kind, decl.by):
        return None
    cpu = places.mode_here(decl.by, decl.ref)
    if cpu is None and places.unsurveyed():
        raise ds.Invalid("unexpected_answer", "this stop's survey could not be read, so the mode "
                         "that places the row is not known here: it waits for the next stop")
    if cpu is None or placement.waits(decl, lambda: cpu) not in (None, dec.UNPLACED):
        raise ds.Invalid("unknown_ref", placement.waits_why(decl.cpu_mode or dec.UNPLACED,
                                                          "Declare it again", cpu is not None))
    return cpu


def _moved(before: dec.Declaration | None, decl: dec.Declaration) -> bool:
    """Whether `decl` places again, in the other mode, a raw row a stop of one mode placed."""
    return (before is not None and None not in (before.cpu_mode, decl.cpu_mode)
            and before.cpu_mode != decl.cpu_mode)


def _watch_waits(item: dict[str, Any], decl: dec.Declaration, places: RawPlaces,
                 machine: tuple[str, dict[str, str]] | None) -> bool:
    """Whether a raw watch waits at this stop for one of the mode that placed it, its `item`
    then given that state and why, as a raw breakpoint's: read here, its SEG:OFF is another byte.
    One no stop placed is placed by the first stop that can, so a watch declared while the guest
    ran is read in that stop's mode; a placement the store cannot write is tried again at the
    next stop, and the watch is read here all the same."""
    cpu = (lambda: machine[0]) if machine is not None else places.cpu
    mode = placement.waits(decl, cpu)
    if mode is None:
        return False
    here = _mode_here(decl, places, machine)
    if mode == dec.UNPLACED and here is not None:
        with contextlib.suppress(ds.Invalid):
            _placed_here(decl, places, here)
        return False
    item["state"] = "unarmable"
    item["why"] = placement.waits_why(mode, "Declare it again", here is not None)
    return True


def _mode_here(decl: dec.Declaration, places: RawPlaces,
               machine: tuple[str, dict[str, str]] | None) -> str | None:
    """`RawPlaces.mode_here`, off the stop's own survey when the caller holds it: a protected-mode
    stop places any SEG:OFF in its mode, a real-mode one an offset within FFFF, which needs no
    second survey to tell."""
    if machine is None:
        return places.mode_here(decl.by, decl.ref)
    cpu = machine[0]
    if dcons.real_segments(cpu):
        _, off = placement.parse_seg_off(decl.ref)
        return cpu if off <= dcons.offset_ceiling(dcons.REAL_MODE) else None
    return cpu


def _stored_before_modes(decl: dec.Declaration) -> bool:
    """A raw row a store wrote before modes were kept: stamped with the batch that described its
    place, with no mode, which no row of today can be (one placed takes its stop's mode, one
    whose place was not known takes the pending stamp, or the conf's with no batch held, and
    waits for a stop of its own session). A legacy row stamped with the conf alone cannot be
    told from those, and waits as they do."""
    return decl.cpu_mode is None and decl.fingerprint not in (
        None, dec.PENDING_STAMP, decl.conf_fingerprint, STATE.conf_fingerprint)


def _adopted(session: ds.Session, decl: dec.Declaration, res: dict[str, Any],
             places: RawPlaces) -> dict[str, str] | None:
    """A raw breakpoint no stop placed, armed at this one when it can place it, and placed by
    it; queued for a later stop when this one cannot (None). A row stored before modes were
    kept was never placed under any map, so the stop that places it makes it this session's
    (`_placed_here`). Armed, it answers what its row adds: a `why` when the place could not be
    written, since the breakpoint is armed all the same."""
    cpu = places.mode_here(decl.by, decl.ref)
    if cpu is None or "seg" not in res:
        if decl.ref not in STATE.pending["arm"]:
            STATE.pending["arm"].append(decl.ref)
        return None
    session.arm_code_breakpoint(res["seg"], res["off"])
    STATE.note_armed(decl.ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                                "entry": f"BP {res['seg']:04X}:{res['off']:04X}"})
    try:
        _placed_here(decl, places, cpu)
    except ds.Invalid as e:
        # ARMED, ITS PLACE NOT WRITTEN: queued, so the next stop writes it (the re-arm skips a
        # row the debugger already holds, and would never come back to it).
        if decl.ref not in STATE.pending["arm"]:
            STATE.pending["arm"].append(decl.ref)
        return {"why": f"{e}; the next stop writes it again"}
    return {}


def _placed_here(decl: dec.Declaration, places: RawPlaces, cpu: str | None) -> None:
    """A raw row armed or read at this stop is placed by it: the stop's mode is written. A code
    row takes the stamp of its place too, as `breakpoint_at` writes it, and one no stop placed
    before becomes this session's, since nothing says another map placed it; a watch is judged
    by no build, so its place is its mode alone."""
    if cpu is None:
        return
    new = dataclasses.replace(decl, cpu_mode=placement.mode_word(cpu))
    if dec.is_raw_code(decl.kind, decl.by):
        new = dataclasses.replace(
            new, fingerprint=placement.stamp_at(places.linear(decl.by, decl.ref), raw=True),
            origin=STATE.session_origin if _stored_before_modes(decl) else decl.origin)
    if (new.fingerprint, new.cpu_mode, new.origin) != (decl.fingerprint, decl.cpu_mode,
                                                       decl.origin):
        try:
            placement.to_invalid(lambda: current_store().apply(replaces=[(decl, new)]))
        except dec.StoreWriteError as e:
            raise ds.Invalid("host_failed", f"armed, but its place could not be written: {e}; "
                             "the stored row keeps its old place") from None


def _armable_declarations() -> list[dec.Declaration]:
    """The declarations that can be armed in this build and this session: not a raw address
    kept from another build, not an interrupt of an earlier session, not a symbol this build
    does not define."""
    if STATE.store is None:
        return []
    return [d for d in STATE.store.declarations()
            if not placement.is_stale(d, _nowhere)
            # A RAW WATCH NO STOP PLACED is placed by the first stop that reads it, and armed
            # there; a raw breakpoint no stop placed is armed nowhere until one is declared again.
            and placement.waits(d, _last_cpu) in ((None, dec.UNPLACED) if d.kind == "watch"
                                                  else (None,))
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
    stop, which holds a row whoever armed it (a `run_to` target whose removal could not be
    confirmed has no declaration behind it), and the store, leaving out what is known NOT
    to be armed (a stale raw address, a symbol this build does not define). The remaining
    doubt errs on the side of waiting."""
    held = STATE.last_stop.get("held") or []
    if any(str(r.get("entry", "")).startswith(("BP ", "BPINT ", "BPMEM ", "BPPM ", "BPLM "))
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
    # STORED FIRST, as its twins are: a store that cannot be written leaves nothing armed that
    # no declaration accounts for.
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    try:
        delta = st.delta_if_asked(session.breakpoint_interrupt(number, ah), st.DETAIL_TEXT_KEEP,
                                   detail)
    except ds.Invalid:
        # NOT ARMED, so not kept: a row this call stored would list as one that can stop the
        # guest while nothing can.
        if is_new:
            placement.to_invalid(lambda: current_store().remove(ref=want, kind="interrupt"))
        raise
    num, ah = dcons.parse_interrupt_row(want)
    STATE.note_armed(want, {"kind": "int", "num": num, "ah": ah, "entry": want})
    return st.reply(ref=want, stored=True, already_stored=not is_new, entry=want, **delta)


def breakpoint_at(session: ds.Session, ref: str, by: str) -> dict[str, Any]:
    """The body of the `breakpoint_at` tool."""
    # `by` was judged before the session gate (`dosbox_checks.by_choice`), its family's words.
    chosen = placement.decide_by(ref) if by == "auto" else by
    placement.address_shape(ref, chosen)
    places = RawPlaces(session)
    decl = declare("breakpoint", chosen, ref, places.linear(chosen, ref),
                   cpu=places.mode_here(chosen, ref) if chosen == "address" else None)
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
                f"{dcons.canonical_seg_off(res['seg'], res['off'])} is already declared under "
                             f"{others[0].ref!r}: one breakpoint row is one declaration, so "
                             f"clear that ref or use it")
    # DECLARED AGAIN IN THE OTHER MODE: the debugger fixed the row's address when it was made,
    # in that stop's mode, so the row that reads the same text is another byte now.
    moved = _moved(next((d for d in current_store().declarations()
                         if d.kind == "breakpoint" and d.ref == ref), None), decl)
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # A RE-DECLARATION IS A NO-OP, NOT A REFUSAL: the store keeps one
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
                      note=f"{ref} {placement.NOT_IN_TABLE}; the declaration is kept and "
                           f"arms nothing until a table defines it")
    if res["state"] == "unarmable":
        # STORED BUT NOT ARMABLE NOW: the machine is running (kept, armed at the next stop
        # and said so), or a real-mode table has no base yet (kept, said as unarmed).
        if not session.at_debugger():
            return pending()
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unarmable", why=res["why"])
    # THE ROW AS STORED WAITS at this stop when no stop placed it, or one of the other mode did
    # and this one could not place it again: armed only at a stop of its own mode.
    if session.at_debugger():
        stored_row = next(d for d in current_store().declarations()
                          if d.kind == "breakpoint" and d.ref == ref)
        if (mode := placement.waits(stored_row, places.cpu)) is not None:
            return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                            armed=False, state="unarmable",
                            why=placement.waits_why(
                                mode, "Declare it again",
                                places.mode_here(chosen, ref) is not None))
    # ALREADY ARMED? A re-declaration must not stack a second debugger entry: if the row
    # is already held, this is a no-op arm. BOTH the check and the arm are inside the try,
    # because `session.breakpoints()` refuses a running machine exactly as `arm` does, and
    # a by-address ref reaches here without the machine having been touched yet -- so the
    # running case must answer `unarmed`, not escape as INVALID (which it did once).
    want = ("BP", res["seg"], res["off"])
    try:
        placement._listening(session)     # a running console drops what is typed at it
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
            item["why"] = placement.waits_why(
                mode, "Declare it again",
                session.at_debugger() and places.mode_here(decl.by, decl.ref) is not None)
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
            listed = any(dcons.bp_row_target(b["entry"]) == want for b in held)
            if listed:
                mine.add(want)
            _held_state(item, decl, listed)
        out.append(item)
    _pending_states(out)
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
    dated: dict[str, Any] = {} if read else {"last_stop": STATE.dated()}
    return st.reply(breakpoints=out, foreign=foreign, debugger_read=read, **dated)


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
    return ("removing these rows now failed (`pending_disarm`), so they are retried "
            "on the next call (`applied_on_stop.disarmed`); the declarations are cleared now")


def breakpoint_clear(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `breakpoint_clear` tool. Both families are cleared here: a `ref` alone (or
    nothing) takes breakpoints AND interrupts, and a caller wanting only one family clears by
    ref. Watches are a different tool, cleared without touching these."""
    store = current_store()
    ref = _require_a_match(store, ref, ("breakpoint", "interrupt"))
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    # THE GUEST RUNS: the rows cannot be removed now, so they are queued for the next stop
    # and the declarations are dropped at once; a name resolves against the last stop's
    # machine, since the console cannot say what mode it is in.
    running = not session.at_debugger()
    # WHAT EACH DECLARATION ARMED is worked out before anything changes: this session's record
    # of its rows (a reload can have armed a second), or with none the live resolution while
    # stopped, and nothing while running, since a row this session never armed does not exist
    # in an emulator this session started.
    plan: list[tuple[dec.Declaration, list[dict[str, Any]], Callable[..., dict[str, object]]]]
    plan = []
    for decl in store.declarations():
        if ref is not None and decl.ref != ref:
            continue
        rows = list(STATE.armed.get(("bp", decl.ref), []))
        if decl.kind == "breakpoint":
            if not rows and not running:
                res = placement.resolve_ref(decl, "CS", session)
                if res["state"] == "armable":
                    rows = [{"kind": "bp", "seg": res["seg"], "off": res["off"],
                             "entry": f"BP {res['seg']:04X}:{res['off']:04X}"}]
            plan.append((decl, rows, session.clear_code_breakpoint))
        elif decl.kind == "interrupt":
            num, ah = dcons.parse_interrupt_row(decl.ref)
            if not rows and not running:
                rows = [{"kind": "int", "num": num, "ah": ah, "entry": decl.ref}]
            plan.append((decl, rows, functools.partial(session.clear_interrupt_breakpoint,
                                                        num, ah)))
    # THEN THE STORE, in one write: a write that fails changes nothing (the store rolls back)
    # and leaves every row armed, so the refusal is the whole story.
    removed = cast(int, placement.to_invalid(
        lambda: store.remove(ref=ref, kind=("breakpoint", "interrupt"))))
    for decl, rows, clear in plan:
        STATE.armed.pop(("bp", decl.ref), None)
        for spec in rows:
            named = str(spec["entry"]) if decl.kind == "breakpoint" else decl.ref
            one = (functools.partial(clear, spec["seg"], spec["off"])
                   if decl.kind == "breakpoint" else clear)
            _disarm_one(spec, named, running, disarmed, pending_disarm, one)
    _unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=_pending_note(running, pending_disarm))


def _unqueue_cleared(store: dec.DeclarationStore) -> None:
    """The arm queue holds REFS, and a breakpoint and a watch may share one: after a clear, a
    queued ref stays while any family still declares it, and goes once none does."""
    held = {d.ref for d in store.declarations()}
    STATE.pending["arm"][:] = [r for r in STATE.pending["arm"] if r in held]


def _aliased(ref: str, places: list[tuple[int, int]]) -> str | None:
    """The refusal when ANOTHER ref of this store already armed a watch at one of `places`: two
    declarations sharing one debugger row would be disarmed together by a clear of either,
    in silence. One watchpoint is one declaration."""
    for (family, other), rows in STATE.armed.items():
        if family != "watch" or other == ref:
            continue
        for seg, off in places:
            if any(r["kind"] == "watch" and (r["seg"], r["off"]) == (seg, off) for r in rows):
                return (f"{dcons.canonical_seg_off(seg, off)} is already armed under {other!r}: "
                        "one watchpoint is one declaration, so clear that ref or use it")
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
    checks.watch_width(mode, width)
    places = RawPlaces(session)
    decl = declare("watch", chosen, ref,
                   cpu=places.mode_here(chosen, ref) if chosen == "address" else None,
                   width=width, fmt=fmt, watch_mode=mode)
    stored = current_store().held_ref(ref, ("watch",))
    if stored is not None and stored != ref:
        # AN ADDRESS DECLARED AGAIN IN ANOTHER SPELLING IS THE SAME DECLARATION, and
        # it is handled under its stored spelling, the string a clear takes.
        ref, decl = stored, dataclasses.replace(decl, ref=stored)
    # DECLARED AGAIN IN THE OTHER MODE: its rows compare their SEG:OFF in the mode of the moment,
    # so the ones the other mode made watch another byte here, and are made again.
    moved = _moved(_stored_watch(ref), decl)
    res = placement.resolve_ref(decl, "DS", session)
    # A NAME THAT MATCHES SEVERAL SYMBOLS IS REFUSED BEFORE STORING, as `breakpoint_at`
    # does: stored, the change path then read `seg` off a resolution that has none, and
    # the KeyError escaped with no session block.
    if res["state"] == "ambiguous":
        raise ds.Invalid("unknown_ref", res["why"])
    if mode == "change" and res["state"] == "armable":
        aliased = _aliased(ref, change_bytes(res["seg"], res["off"], width))
        if aliased is not None:
            raise ds.Invalid("ambiguous_ref", aliased)
    already = not cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # THE ROW AS STORED WAITS at this stop when one of the other mode placed it and this one could
    # not place it again: read and armed only at a stop of its own mode.
    waiting: dict[str, Any] = {}
    if session.at_debugger() and _watch_waits(waiting, cast(dec.Declaration, _stored_watch(ref)),
                                              places, None):
        return st.reply(ref=ref, by=chosen, mode=mode, fmt=fmt, length=width, stored=True,
                        already_stored=already, armed=False, **waiting)
    # THROUGH A POINTER the reply says through what: where the pointer sits, its width,
    # what it holds, and the offset past it; a null pointer is a state the stop re-resolves.
    extra: dict[str, Any] = {"pointer": res["pointer"]} if "pointer" in res else {}
    if chosen == "pointer" and res["state"] in ("null_pointer", "unarmable"):
        return st.reply(ref=ref, by=chosen, mode=mode, fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=res["state"],
                      why=res["why"], **extra)
    if mode == "show":
        # A SHOW WATCH ARMS NOTHING: a plain memory read at every stop. The declaration is
        # stored; whether the symbol resolves yet only
        # decides whether it can be READ, not whether it is kept. The state is its
        # resolution, spelled the same way `watch_list` and a stop's `watches` spell it (one
        # word per concept) -- `evaluated` when it has an address, else the reason it
        # has none.
        state = "evaluated" if res["state"] == "armable" else res["state"]
        return st.reply(ref=ref, by=chosen, mode="show", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=state, **extra)
    # NOT PLACEABLE NOW: kept, and answered with the resolution's own reason (a pointer that
    # cannot be followed, a real-mode table with no base) or, for a name, the table's; a
    # running guest queues it for the stop that can place it.
    if res["state"] != "armable":
        if res["state"] == "unarmable" and not session.at_debugger():
            return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width,
                            stored=True, already_stored=already, armed=False, state="pending",
                            **STATE.queue_arm(ref))
        said = ({"why": res["why"]} if "why" in res else
                {"note": f"{ref} {placement.NOT_IN_TABLE}; kept, arms nothing yet"})
        return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                        already_stored=already, armed=False, state=res["state"], **said,
                        **extra)
    # ALREADY ARMED? A change-watch re-declared after a rebuild would otherwise stack a
    # second BPPM/BPM at the same address; if the row is held, this is a no-op arm. The
    # check is INSIDE the try for the same reason as breakpoint_at: `breakpoints()` and
    # `where()` refuse a running machine, and a by-address ref has not touched it yet.
    try:
        placement._listening(session)     # a running console drops what is typed at it
        mode = session.where()["mode"]
        covered = reachable_bytes(res["seg"], res["off"], width, mode)
        if moved:
            _unarm_moved(session, ref, covered)
        listed = session.breakpoints()
        missing = [place for place in covered if watch_held(listed, *place) is None]
        made = dict(zip(missing, session.watch_places(missing), strict=True)) if missing else {}
    except ds.Invalid as e:
        if isinstance(e, ds.NotStopped) or not session.at_debugger():
            return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                          already_stored=already, armed=False, state="pending",
                          **STATE.queue_arm(ref))
        return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state="unarmable", why=str(e))
    # EVERY ROW IS THE WATCH'S, the ones the debugger already held as much as the ones just
    # armed: the record names them all, so a clear deletes them all. A re-declaration that found
    # every row held is a no-op, and still carries the Pr caveat, because a re-declared change
    # watch is as untrustworthy under paging as a fresh one.
    entries = [str(made[p]["armed"]) if p in made else _watch_entry(*p, mode) for p in covered]
    for (s_, o_), entry in zip(covered, entries, strict=True):
        STATE.note_armed(ref, {"kind": "watch", "seg": s_, "off": o_, "entry": entry})
    caveat = {"caveat": _PR_WATCH_CAVEAT} if mode.startswith("Pr") else {}
    sent = {"command": str(made[missing[0]]["command"])} if missing else {}
    return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                    already_stored=already, armed=True, state="armed", entry=entries[0],
                    entries=entries, **sent, **caveat, **extra)


def _unarm_moved(session: ds.Session, ref: str, covered: list[tuple[int, int]]) -> None:
    """A change watch's rows of the other mode deleted and forgotten, so the record names only
    the rows armed in this one; a row the debugger still lists refuses the arm, since a held row
    of the other mode would be counted as this one's."""
    gone, kept = delete_watch_rows(session, covered)
    for entry in gone:
        STATE.snapshot_forget(entry)
    STATE.armed.pop(("watch", ref), None)
    if kept:
        raise ds.Invalid("unexpected_answer", f"the rows the other mode armed at "
                         f"{', '.join(dcons.canonical_seg_off(*p) for p in kept)} are still listed "
                         "after their delete: nothing was armed in this mode")


def _stored_watch(ref: str) -> dec.Declaration | None:
    return next((d for d in current_store().declarations() if d.kind == "watch" and d.ref == ref),
                None)


def watch_list(session: ds.Session) -> dict[str, Any]:
    """The body of the `watch_list` tool."""
    store = current_store()
    held, read, machine = STATE.list_basis(session)
    places = RawPlaces(session)
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
        elif _watch_waits(item, decl, places, machine):
            # ITS ROWS ARE STILL ITS OWN, never foreign: made in the other mode's terms.
            mine.update(place for place in change_bytes(res["seg"], res["off"], decl.width)
                        if watch_held(held, *place) is not None)
        elif decl.watch_mode == "show":
            # arms nothing; resolution is the whole state, unless it is nobody's, which is
            # the one thing a reader of every stop reply needs to know about it
            if orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WATCH_WHY
            else:
                item["state"] = "evaluated"
        else:
            seg, off = res["seg"], res["off"]
            item["entry"] = _watch_entry(seg, off, machine[0] if machine is not None
                                         else session.where()["mode"])
            # Match by the NUMBERS (a watch family kind at this seg:off), never by a
            # reconstructed spelling: the debugger's offset width is not fixed (one address
            # was listed as both `BPPM 00AF:6024` and `BPPM 00AF:00006024`), so an equality
            # or prefix test on the spelling reports an armed watch as gone.
            covered = change_bytes(seg, off, decl.width)
            listed = all_held(held, covered)
            mine.update(place for place in covered if watch_held(held, *place) is not None)
            _held_state(item, decl, listed)
        out.append(item)
    _pending_states(out)
    queued = {(sp["seg"], sp["off"]) for sp in STATE.pending["disarm"] if sp["kind"] == "watch"}
    foreign = [b["entry"] for b in held
               if (t := dcons.bp_row_target(b["entry"])) is not None
               and t[0] in _WATCH_KINDS
               and (t[0] not in _OWN_WATCH_KINDS
                    or ((t[1], t[2]) not in mine and (t[1], t[2]) not in queued))]
    dated: dict[str, Any] = {} if read else {"last_stop": STATE.dated()}
    return st.reply(watches=out, foreign=foreign, debugger_read=read, **dated)


def watch_clear(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `watch_clear` tool."""
    store = current_store()
    ref = _require_a_match(store, ref, ("watch",))
    to_go = [d for d in store.declarations()
             if d.kind == "watch" and (ref is None or d.ref == ref)]
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    running = not session.at_debugger()
    # THE ROWS FIRST, THEN THE STORE, as `breakpoint_clear`: nothing changes before the rows are
    # known, and a write that fails changes nothing and disarms nothing.
    plan: list[list[dict[str, Any]]] = []
    for decl in to_go:
        rows = [] if decl.watch_mode == "show" else list(STATE.armed.get(("watch", decl.ref), []))
        if decl.watch_mode == "change" and not rows and not running:
            res = placement.resolve_ref(decl, "DS", session)
            if res["state"] == "armable":
                mode = session.where()["mode"]
                rows = [{"kind": "watch", "seg": s_, "off": o_,
                         "entry": _watch_entry(s_, o_, mode)}
                        for s_, o_ in change_bytes(res["seg"], res["off"], decl.width)]
        plan.append(rows)             # a show watch armed nothing
    removed = cast(int, placement.to_invalid(lambda: store.remove(ref=ref, kind="watch")))
    for decl, rows in zip(to_go, plan, strict=True):
        STATE.armed.pop(("watch", decl.ref), None)
        if not rows:
            continue
        try:
            if running:
                raise ds.NotStopped("the guest is running")
            # READ THE LIST BACK, as `clear_code_breakpoint` does: `disarmed` is the machine's
            # answer, not this tool's claim that a BPDEL it sent must have taken.
            gone, _ = delete_watch_rows(session, [(int(r["seg"]), int(r["off"])) for r in rows])
            for entry in gone:
                disarmed.append(entry)
                STATE.snapshot_forget(entry)
        except ds.Invalid:
            for spec in rows:
                STATE.pending["disarm"].append(spec)
                pending_disarm.append(str(spec["entry"]))
            STATE.pending["dirty"] = True
    _unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=_pending_note(running, pending_disarm))


def _held_state(item: dict[str, Any], decl: dec.Declaration, held: bool) -> None:
    """A placed row's state against the debugger's list: `armed` when it holds the row, else
    `orphan` for a declaration nobody owns, else `gone`."""
    if held:
        item["state"] = "armed"
    elif orphan(decl):
        item["state"] = "orphan"
        item["why"] = _ORPHAN_WHY
    else:
        item["state"] = "gone"


def _pending_states(rows: list[dict[str, Any]]) -> None:
    """A row asked to arm while the guest ran is `pending` whatever the list says now."""
    for item in rows:
        if item["ref"] in STATE.pending["arm"]:
            item["state"] = "pending"
            item.pop("why", None)


def _disarm_one(spec: dict[str, Any], named: str, running: bool, disarmed: list[str],
                pending_disarm: list[str], clear: Callable[[], dict[str, object]]) -> None:
    """One armed row taken out of the debugger, or queued for the next stop: while the guest
    runs, and when the removal refuses, since a row left in is one the next release meets."""
    if not running:
        try:
            gone = clear()
        except ds.Invalid:
            pass
        else:
            if gone["removed"]:
                disarmed.append(str(gone["entry"]))
                STATE.snapshot_forget(str(gone["entry"]))
            return
    STATE.pending["disarm"].append(spec)
    STATE.pending["dirty"] = True
    pending_disarm.append(named)
