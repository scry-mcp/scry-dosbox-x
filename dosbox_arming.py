"""Arming declarations: what the store says, put into the debugger and read back.

The six declaring tools and `breakpoint_interrupt` have their bodies here; their contracts (the
docstrings the client reads) stay with the registrations in `dosbox_x_server`."""

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
import dosbox_declarations as dec
import dosbox_dump as dumping
import dosbox_grammar as grammar
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
import dosbox_symbol_file as symbol_file
import dosbox_taps as taps
from dosbox_state import STATE


def declare(kind: str, by: str, ref: str, linear: int | None = None,
            cpu: str | None = None, **watch: Any) -> dec.Declaration:
    """A declaration stamped with this session's origin, the clock and its place now; `cpu` is
    the mode of the stop that placed a raw row."""
    raw = dec.is_raw_code(kind, by)
    mode = placement.mode_word(cpu) if dec.keeps_mode(kind, by) else None
    return cast(dec.Declaration,
                placement.to_invalid(lambda: dec.Declaration(kind, by, ref, created_at=st.now(),
                                                    origin=STATE.session_origin,
                                                    fingerprint=placement.stamp_at(linear, raw),
                                                    cpu_mode=mode, **watch)))


class RawPlaces:
    """Where a raw breakpoint lands at this instant, surveying the stop at most once; None where
    this instant cannot say."""

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
                real = last is not None and grammar.real_segments(last[0])
                return dumping.real_linear(seg, off) if real and off <= grammar.offset_ceiling(
                    grammar.REAL_MODE) else None
            if self._segs is None:
                self._segs = code.segments_at_stop(self.session)
            if self._segs.real:
                return (dumping.real_linear(seg, off)
                        if off <= grammar.offset_ceiling(grammar.REAL_MODE) else None)
            base, limit = self._segs.base(seg), self._segs.limit(seg)
        except ds.Invalid:
            return None
        return base + off if off <= limit else None

    def judged(self, decl: dec.Declaration) -> Callable[[], int | None]:
        return lambda: self.linear(decl.by, decl.ref)

    def mode_here(self, by: str, ref: str) -> str | None:
        """The cpu mode this stop gives a raw row, in the debugger's spelling; None at a
        real-mode stop that cannot place it or while the guest runs. A protected-mode stop gives
        its mode even when it cannot read the selector's base."""
        if not self.session.at_debugger():
            return None
        cpu = self.cpu()
        if self._segs is None:            # this stop's survey was refused: the mode is not its
            return None
        if grammar.real_segments(cpu or "") and self.place(by, ref) is None:
            return None
        return cpu

    def unsurveyed(self) -> bool:
        """At a stop whose survey was refused: the failure is the survey's, not the row's."""
        return self._segs is None and self.session.at_debugger()

    def cpu(self) -> str | None:
        """This stop's cpu mode as the debugger spells it; the last stop's while the guest runs
        or the survey is refused."""
        if self._segs is None and self.session.at_debugger():
            with contextlib.suppress(ds.Invalid):
                self._segs = code.segments_at_stop(self.session)
        if self._segs is not None:
            return self._segs.mode
        last = STATE.last_machine()
        return None if last is None else last[0]


def _last_cpu() -> str | None:
    """The last stop's cpu mode, read from the record, with no round trip to the debugger."""
    last = STATE.last_machine()
    return None if last is None else last[0]


def _nowhere() -> None:
    """No place asked: a row it cannot place is taken as described, not armed."""
    return None


def current_store() -> dec.DeclarationStore:
    """The declaration store for the current session's conf, or INVALID with no session."""
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
    """A declaration with no origin recorded, in a session that has one. With no session origin
    (the contract harness never calls `start`) nothing is an orphan."""
    return decl.origin is None and STATE.session_origin is not None


def decl_row(decl: dec.Declaration) -> dict[str, Any]:
    """The fields every listed declaration carries (`scry_core.declaration_rows`)."""
    return declaration_rows.row(kind=decl.kind, ref=decl.ref, by=decl.by, cpu=None,
                                cpu_why=ONE_CPU_WHY, created_at=decl.created_at, origin=decl.origin,
                                own_origin=STATE.session_origin, now=st.utc_now())


#: Why no DOSBox-X row names a cpu.
ONE_CPU_WHY = "a DOS machine has one cpu, and every row acts on it"


# BPLIST kind tokens of a memory watch: protected paged, real, linear.
_WATCH_KINDS = ("BPPM", "BPMEM", "BPLM")
# The kinds this server arms at a SEG:OFF; a `BPLM` row at a real-mode SEG:OFF's linear address is
# somebody else's.
_OWN_WATCH_KINDS = ("BPPM", "BPMEM")

_PR_WATCH_CAVEAT = ("this is a protected-mode watch (BPPM); under a paged DPMI program it "
                    "fires on the paging host, not the program, so a stop "
                    "here is not to be trusted. Break-on-change is reliable in real mode")


def _watch_entry(seg: int, off: int, mode: str) -> str:
    """The debugger's BPLIST spelling for a memory watch, for display only; recognition goes
    through `watch_held`, since the debugger's width varies."""
    kind = grammar.watch_kind(mode)
    return f"{kind} {seg:04X}:{off:08X}" if kind == "BPPM" else f"{kind} {seg:04X}:{off:04X}"


def watch_held(held: list[dict[str, str]], seg: int, off: int) -> dict[str, str] | None:
    """The held BPLIST row that is a memory watch at seg:off, by value, or None; a code
    breakpoint there is not a match."""
    for b in held:
        t = grammar.bp_row_target(b["entry"])
        if t is not None and t[0] in _OWN_WATCH_KINDS and (t[1], t[2]) == (seg, off):
            return b
    return None


def change_bytes(seg: int, off: int, width: int | None) -> list[tuple[int, int]]:
    """Every byte a change watch arms a row for: the debugger's memory breakpoint compares one
    byte."""
    return [(seg, off + i) for i in range(max(int(width or 1), 1))]


def reachable_bytes(seg: int, off: int, width: int | None,
                    mode: str) -> list[tuple[int, int]]:
    """`change_bytes`, refused whole when its last byte is past the offset `mode` reaches,
    before any row goes in."""
    places = change_bytes(seg, off, width)
    last, top = places[-1][1], grammar.offset_ceiling(mode)
    if last > top:
        raise ds.Invalid("bad_argument",
            f"a change watch of {len(places)} bytes at {grammar.canonical_seg_off(seg, off)} "
            f"ends at offset 0x{last:X}, past the 0x{top:X} an offset reaches in {mode} mode: no "
            "row was armed")
    return places


def _mode(session: ds.Session, machine: tuple[str, dict[str, str]] | None) -> str:
    return machine[0] if machine is not None else session.where()["mode"]


def all_held(held: list[dict[str, str]], places: list[tuple[int, int]]) -> bool:
    """Whether the debugger lists a memory watch at every one of `places`."""
    return all(watch_held(held, seg, off) is not None for seg, off in places)


def render_watch(raw: bytes, width: int, fmt: str) -> vf.Value:
    """`width` bytes read as `fmt`, little-endian (x86)."""
    return vf.parse(fmt).decode(raw, "little", width)


def evaluate_watches(session: ds.Session, *,
                      machine: tuple[str, dict[str, str]] | None = None,
                      held: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every watch declaration evaluated at this stop; one that no longer resolves or cannot be
    read is listed with why, never a value at a guessed address."""
    if STATE.store is None:
        return []
    # `held` is the stop's own read; only a caller with no stop in hand pays a fresh one.
    if held is None:
        held = session.breakpoints()
    places = RawPlaces(session)
    out: list[dict[str, Any]] = []
    counts = _tap_counts(session)
    for decl in STATE.store.declarations():
        if decl.kind != "watch":
            continue
        item: dict[str, Any] = {"ref": decl.ref, "by": decl.by, "mode": decl.watch_mode,
                                "length": decl.width, "fmt": decl.fmt}
        if orphan(decl):
            item["orphan"] = True       # nobody's: from a store that kept no origin
        if decl.watch_mode in dec.TAP_MODES:
            out.append({**item, **_tap_item(decl, counts, at_stop=True)})
            continue
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
            # Re-resolved at every stop, since the pointer can move; a refused move leaves the watch
            # armed where it was and the state is judged there.
            moved = _follow(session, decl, seg, off, _mode(session, machine))
            if moved is not None:
                item["moved"] = moved
                held = session.breakpoints()
                recorded = [r for r in STATE.armed.get(("watch", decl.ref), [])
                            if r["kind"] == "watch"]
                if recorded and all((r["seg"], r["off"]) != (seg, off) for r in recorded):
                    first = min(recorded, key=lambda r: (r["seg"], r["off"]))
                    seg, off = int(first["seg"]), int(first["off"])
        # A change watch is read as a show watch is: the debugger's memory breakpoints write nothing
        # into the memory they watch.
        change = decl.watch_mode == "change"
        if change:
            item["state"] = ("armed" if all_held(held, change_bytes(seg, off, decl.width))
                             else "gone")
        try:
            # `machine[0]` is the mode the stop reply cached: a show watch's read would else
            # re-survey per watch.
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
    """Whether two code addresses are the same place: by selector and offset in protected mode,
    by linear address in real mode, where many seg:off pairs alias one byte."""
    if mode.startswith("Pr"):
        return a == b
    return a[0] * 16 + a[1] == b[0] * 16 + b[1]


def _bp_holders(session: ds.Session, mode: str, at: tuple[int, int], *, but: str = "",
                machine: tuple[str, dict[str, str]] | None = None) -> list[dec.Declaration]:
    """The breakpoint declarations that resolve to code address `at` (by linear address in real
    mode), other than `but`, whatever their row's state."""
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
        # With no mode to hand, spellings compare as they are: errs towards accepting, never towards
        # refusing wrongly.
        if _same_code_addr(mode, at, there) if mode else at == there:
            out.append(decl)
    return out


def _conditions_met(registers: dict[str, str], held: list[dict[str, str]]) -> list[str]:
    """The held registerpoints whose condition holds for a stop's registers."""
    rows = [b["entry"][len(grammar.CONDITION_ROW):] for b in held
            if b["entry"].startswith(grammar.CONDITION_ROW)]
    return [r for r in rows if grammar.condition_holds(r, registers)]


def attribute_stop(session: ds.Session, *, where: dict[str, str],
                    machine: tuple[str, dict[str, str]] | None = None,
                    held: list[dict[str, str]],
                    retrace_may_stop: bool = False) -> dict[str, Any]:
    """Which declaration the stop is at, by address comparison, or an honest cannot-say.

    A memory watch stops at the writing instruction, not the watched address, so only a code
    breakpoint whose address equals CS:EIP is named; several at one address are all named
    (`refs`). `held` is the debugger's list at this stop: a row it does not hold did not make
    the stop. `retrace_may_stop` (a release that ran on) names and forgets a retrace `run_for`
    left armed when no declaration explains the stop."""
    stop = (int(where["cs"], 16), int(where["eip"], 16))
    mode = where["mode"]
    holders = _bp_holders(session, mode, stop, machine=machine)
    rows = [t[1:] for t in map(grammar.bp_row_target, (b["entry"] for b in held))
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
    # `BPIF` keeps no hit flag, and a condition can hold at a stop something else made: one
    # that holds is named as the likely maker, never taken for it.
    met = _conditions_met(machine[1], held) if machine is not None else []
    holding = {"regpoints_holding": met} if met else {}
    if retrace_may_stop and STATE.retrace_pending:
        STATE.retrace_pending = False
        return {"attributed": False, "retrace_pending": True, **holding,
                "at": st.seg_off(*stop),
                "why": "the stop address matches no declared code breakpoint, and a `run_for` "
                       "had left a retrace stop armed, which stops the next release at the next "
                       "retrace: most likely this stop"}
    return {"attributed": False, **holding,
            "at": st.seg_off(*stop),
            "why": "the stop address matches no declared code breakpoint. The debugger "
                   "keeps no hit flag, and a memory watch stops at the WRITING instruction "
                   "rather than the watched address, so which declaration fired cannot be "
                   "derived from the stop"}


#: A pointer watch's `moved.why` when only the CPU mode changed: the debugger compares a row in
#: the terms of the mode that armed it.
OTHER_MODE_ROW = ("armed again in this CPU mode: the old row was the other mode's, and the "
                  "debugger reads a row in the mode that armed it")


def _follow(session: ds.Session, decl: dec.Declaration, seg: int, off: int,
            mode: str) -> dict[str, str] | None:
    """A change watch whose pointer now points elsewhere: new rows armed first, old ones deleted
    once those are held. `{from, to}` when it moved, None otherwise; `why` when a row was
    refused or kept (retried at the next stop), or armed again at the same place because the
    old one was the other CPU mode's."""
    rows = STATE.armed.get(("watch", decl.ref), [])
    mine = [r for r in rows if r["kind"] == "watch"]
    try:
        want = reachable_bytes(seg, off, decl.width, mode)
    except ds.Invalid as e:
        return {"from": st.seg_off(mine[0]["seg"], mine[0]["off"]) if mine else "null",
                "to": st.seg_off(seg, off), "why": str(e)}
    # A row of the other mode is not this watch's here, at the same numbers or not: the debugger
    # compares it in this mode's terms.
    kind = grammar.watch_kind(mode)
    stale = [r for r in mine if (r["seg"], r["off"]) not in want or _row_kind(r) != kind]
    have = {(r["seg"], r["off"]) for r in mine if r not in stale}
    missing = [place for place in want if place not in have]
    if not missing:
        _drop_stale(session, rows, stale)
        return None
    old = min(stale, key=lambda r: (r["seg"], r["off"])) if stale else None
    # A watch declared while the pointer was NULL armed nothing; it came from null.
    where = {"from": st.seg_off(old["seg"], old["off"]) if old is not None else "null",
             "to": st.seg_off(seg, off)}
    if where["from"] == where["to"]:
        where["why"] = OTHER_MODE_ROW
    # New rows first, so a refusal leaves the watch armed where it was.
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


def _row_kind(row: dict[str, Any]) -> str | None:
    target = grammar.bp_row_target(str(row.get("entry", "")))
    return target[0] if target is not None else None


def _watch_row_at(place: tuple[int, int], kind: str | None = None) -> Callable[[str], bool]:
    """A pick for `Session.delete_rows`: the memory-watch row at `place`, of `kind` if named."""
    def pick(entry: str) -> bool:
        held = watch_held([{"entry": entry, "index": "00"}], *place)
        return held is not None and kind in (None, _row_kind(held))
    return pick


def delete_watch_rows(session: ds.Session, places: list[tuple[int, int]],
                      kinds: list[str | None] | None = None,
                      ) -> tuple[list[str], list[tuple[int, int]]]:
    """The memory-watch rows at `places` deleted, each of its `kinds` entry when given: one list
    read, a `BPDEL` each from the highest index down (a delete renumbers only the rows below),
    one read back. Returns the rows gone and the places still listed."""
    pairs = list(dict.fromkeys(zip(places, kinds or [None] * len(places), strict=True)))
    wanted = [place for place, _ in pairs]
    deleted = session.delete_rows([_watch_row_at(p, k) for p, k in pairs])
    gone = [str(row["entry"]) for row, absent in deleted if row is not None and absent]
    kept = [p for p, (row, absent) in zip(wanted, deleted, strict=True)
            if row is not None and not absent]
    return gone, kept


def _drop_stale(session: ds.Session, rows: list[dict[str, Any]],
                stale: list[dict[str, Any]]) -> str:
    """The rows of a moved watch at a place it no longer points to deleted from the debugger and
    the record; one the debugger still lists stays in both. What kept one, or empty."""
    if not stale:
        return ""
    # The list is read when the deletes are made: the debugger lists a row just armed first, so an
    # older list gives every older row the wrong index.
    try:
        _, kept = delete_watch_rows(session, [(int(r["seg"]), int(r["off"])) for r in stale],
                                    [_row_kind(r) for r in stale])
    except ds.Invalid as e:
        return str(e)
    rows[:] = [r for r in rows if r not in stale or (int(r["seg"]), int(r["off"])) in kept]
    return "the debugger still lists it" if kept else ""


#: The buckets of a re-arm's account, each a list of `decl_row`s, `why` on the last three.
REARM_BUCKETS = ("rearmed", "stale", "unresolved", "ambiguous", "unarmable")


def _rearm_condition(session: ds.Session, decl: dec.Declaration, out: dict[str, Any]) -> None:
    """A stored registerpoint armed again, unless held; one a build cannot arm is `unarmable`."""
    row, entry = decl_row(decl), f"{grammar.CONDITION_ROW}{decl.ref}"
    if not session.has("BPIF"):
        out["unarmable"].append({**row, "why": "this build's debugger has no `BPIF` command"})
        return
    if any(b["entry"] == entry for b in session.breakpoints()):
        return
    try:
        session.condition_breakpoint(decl.ref)
    except ds.Invalid as e:
        out["unarmable"].append({**row, "why": str(e)})
        return
    STATE.note_armed(decl.ref, {"kind": "cond", "row": decl.ref, "entry": entry})
    out["rearmed"].append(row)


def _rearm_tap(session: ds.Session, decl: dec.Declaration, out: dict[str, Any]) -> None:
    """A stored count or capture tapped again where it resolves now; one already tapped where it
    resolves stays."""
    row = decl_row(decl)
    held = STATE.taps.get(decl.ref)
    waits = placement.waits(decl, RawPlaces(session).cpu)
    if waits is not None:
        out["unarmable"].append({**row, "why": placement.waits_why(waits, "Declare it again")})
        return
    try:
        if held is not None:
            if (held.seg, held.off) == taps.place(decl, session) and taps.installed(
                    session, decl.ref):
                return
            taps.drop(session, decl.ref)
        taps.arm(session, decl)
    except ds.Invalid as e:
        state = "unresolved" if e.code == "unknown_ref" else "unarmable"
        out[state].append({**row, "why": str(e)})
        return
    out["rearmed"].append(row)


def rearm_declarations(session: ds.Session) -> dict[str, Any]:
    """Re-resolve every stored declaration against the just-loaded table and arm the code ones
    that resolve and are not already held. Unresolved or ambiguous names are listed, never
    guessed at. The account is one list of `decl_row`s per bucket (`REARM_BUCKETS`)."""
    out: dict[str, Any] = {key: [] for key in REARM_BUCKETS}
    if STATE.store is None:
        return out
    held = {grammar.bp_row_target(b["entry"]) for b in session.breakpoints()}
    places = RawPlaces(session)
    for decl in STATE.store.declarations():
        if decl.kind == "regpoint":
            _rearm_condition(session, decl, out)
            continue
        if decl.kind == "watch" and decl.watch_mode in dec.TAP_MODES:
            _rearm_tap(session, decl, out)
            continue
        if decl.kind != "breakpoint":
            continue
        row = decl_row(decl)
        res = placement.resolve_ref(decl, "CS", session)
        state = res["state"]
        if state in ("unresolved", "ambiguous", "unarmable"):
            out[state].append({**row, **({"why": res["why"]} if "why" in res else {})})
        elif ("BP", res["seg"], res["off"]) in held:
            continue              # already armed, by this session or by a symbol's re-arm
        # A raw address placed in the other mode, or by no stop, waits for a stop of its own:
        # `start` parks in real mode, so a protected-mode row is re-armed at a protected-mode stop,
        # not at the park.
        elif (mode := placement.waits(decl, places.cpu)) is not None:
            if mode == dec.UNPLACED and _stored_before_modes(decl):
                # A row that cannot be adopted answers for itself, not for the whole re-arm.
                try:
                    adopted = _adopted(session, decl, res, places)
                except ds.Invalid as e:
                    out["unarmable"].append({**row, "why": str(e)})
                    continue
                if adopted is not None:
                    out["rearmed"].append({**row, **adopted})
                    continue
            out["unarmable"].append({**row, "why": placement.waits_why(mode, "Declare it again")})
        # A raw address from another build re-resolves against nothing, and armed blind lands
        # wherever the linker put something else: it stays stored, listed `stale`, and declaring it
        # again adopts it. Tested after `held`, so a row the debugger holds is never called stale.
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
    """At `start`, arm again the raw addresses an earlier session declared over this build, and
    every registerpoint, which names no address; another build's addresses stay `stale`. With
    nothing to arm the debugger's list is not read.

    The session is already installed, so a refusal is handed back as `rearm_refused`, not
    raised."""
    if STATE.store is None or not any(
            d.kind == "regpoint" or (d.kind == "watch" and d.watch_mode in dec.TAP_MODES)
            or (d.kind == "breakpoint" and d.by == "address"
                and not placement.is_stale(d, _nowhere))
            for d in STATE.store.declarations()):
        return {"declarations": {"rearm": _unarmed_at_start()}}
    try:
        return {"declarations": {"rearm": rearm_declarations(session)}}
    except ds.Invalid as e:
        return {"declarations": {"rearm": _unarmed_at_start(str(e))}, "rearm_refused": str(e)}


def _unarmed_at_start(refused: str = "") -> dict[str, Any]:
    """The account of a park that armed nothing, read without asking the debugger: a name waits
    for the table, a raw address of another build is stale, one of this build is unarmable with
    `refused`."""
    out: dict[str, Any] = {key: [] for key in REARM_BUCKETS}
    for decl in STATE.store.declarations() if STATE.store is not None else []:
        if decl.kind == "regpoint" and refused:
            out["unarmable"].append({**decl_row(decl), "why": refused})
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
    """At a stop, do what the guest's running kept the debugger from doing: load held symbols,
    remove rows a clear left, arm what was declared. Each half is attempted on its own; what
    could not be applied stays pending. Empty when nothing was pending."""
    if not (STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["load"] is not None
            or STATE.pending["remeasure"]):
        return {}
    STATE.pending["dirty"] = False
    STATE.pending["drained_seq"] = STATE.last_stop.get("seq", 0)
    out: dict[str, Any] = {"symbols_loaded": False, "disarmed": [], "armed": [],
                           "still_pending": []}
    # Clears first, so a breakpoint declared again after its clear is armed again, not counted armed
    # over a row this stop deletes.
    kept_disarm: list[dict[str, Any]] = []
    for spec in STATE.pending["disarm"]:
        try:
            if spec["kind"] == "bp":
                gone = session.clear_code_breakpoint(spec["seg"], spec["off"])
            elif spec["kind"] == "int":
                gone = session.clear_interrupt_breakpoint(spec["num"], spec["ah"])
            elif spec["kind"] == "cond":
                gone = session.clear_condition_breakpoint(spec["row"])
            elif spec["kind"] == "tap":
                gone = {"entry": spec["entry"],
                        "removed": taps.remove(session, spec["ref"], spec["id"]) is not None}
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
        # A load no stop of this session can take is dropped, said once.
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
            # The map is taken here, as a load at a stop takes it, before the re-arm judges the
            # rows. Imported at the call: the comments module is built on this one.
            import dosbox_comments
            unwritten = dosbox_comments.park_rows_take_the_map(session)
            if unwritten is not None:
                out["still_pending"].append(
                    f"taking the map: {unwritten}; the rows this session placed before any map "
                    "keep their place as it was, and a later load takes them")
            # The load is done whatever the re-arm answers: a failure queues the breakpoints it
            # would have armed for the loop below.
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
        # One machine reading and one list read for every ref.
        try:
            where, regs = session.where_and_registers()
            machine: tuple[str, dict[str, str]] | None = (where["mode"], regs)
            held = session.breakpoints()
        except ds.Invalid:
            machine, held = None, []
        for ref in STATE.pending["arm"]:
            rearmed = ref in out["armed"]    # by the load, which re-arms breakpoints only
            # Every declaration under the ref: the queue holds a ref once, and a breakpoint and a
            # watch may share it. Each arm checks the list first, so nothing is doubled.
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
    # Accumulated, not replaced: `live()` may have drained part of the queue before a stop tool
    # drains the rest.
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
            num, ah = grammar.parse_interrupt_row(decl.ref)
            if not any(b["entry"] == decl.ref for b in held):
                session.breakpoint_interrupt(num, ah)
            STATE.note_armed(ref, {"kind": "int", "num": num, "ah": ah, "entry": decl.ref})
        elif decl.kind == "regpoint":
            entry = f"{grammar.CONDITION_ROW}{decl.ref}"
            if not any(b["entry"] == entry for b in held):
                session.condition_breakpoint(decl.ref)
            STATE.note_armed(ref, {"kind": "cond", "row": decl.ref, "entry": entry})
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
            if not any(grammar.bp_row_target(b["entry"]) == want for b in held):
                session.arm_code_breakpoint(res["seg"], res["off"])
                # The list learns the row: read once before the loop, it would stack a second row on
                # the same address.
                held.append({"index": "?", "entry": entry})
            STATE.note_armed(ref, {"kind": "bp", "seg": res["seg"], "off": res["off"],
                              "entry": entry})
            _placed_here(decl, places, cpu)
    except ds.Invalid as e:
        out["still_pending"].append(f"arm {ref} ({decl.kind}): {e}")
        return False
    return True


# #: How far past the table's last symbol a stop still counts as the program's code (the last
# routine's body, which no symbol bounds).
PROGRAM_TAIL = 0x10000


def _remeasure(session: ds.Session, out: dict[str, Any]) -> None:
    """The first protected-mode stop whose `EIP` is within the table's span (`PROGRAM_TAIL` past
    its last symbol) measures the table's base and the program's selectors again: a restored
    machine may hold the program elsewhere. A moved base moves the table and re-arms what is
    declared by name."""
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
    # The base has moved whatever the re-arm answers: a failure queues what it would have armed.
    try:
        out["armed"].extend(r["ref"] for r in rearm_declarations(session)["rearmed"])
    except ds.Invalid as e:
        out["still_pending"].append(f"the re-arm after the base was measured again: {e}")
        for decl in _armable_declarations():
            if decl.kind == "breakpoint" and decl.ref not in STATE.pending["arm"]:
                STATE.pending["arm"].append(decl.ref)


def _disarm_by_name(session: ds.Session, out: dict[str, Any]) -> None:
    """The code breakpoints armed by name before the base moved, cleared from the debugger: on a
    restored machine their old places are someone else's bytes. One that cannot be cleared stays
    queued."""
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
    """One drain's account joined into `STATE.applied_last`: lists accumulate, a symbols load is
    kept once made, still-pending is the latest word."""
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
    """The mode this stop gives a queued raw row (None for a symbol); refused, so it stays
    queued, when the row waits here."""
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
    """Whether a raw watch waits at this stop for the mode that placed it, `item` then carrying
    that state and why. One no stop placed is placed by the first stop that can."""
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
    """`RawPlaces.mode_here`, off the stop's own survey when the caller holds it, which needs no
    second survey."""
    if machine is None:
        return places.mode_here(decl.by, decl.ref)
    cpu = machine[0]
    if grammar.real_segments(cpu):
        _, off = placement.parse_seg_off(decl.ref)
        return cpu if off <= grammar.offset_ceiling(grammar.REAL_MODE) else None
    return cpu


def _stored_before_modes(decl: dec.Declaration) -> bool:
    """A raw row a store wrote before modes were kept: stamped with a batch, with no mode, which
    no row of today can be."""
    return decl.cpu_mode is None and decl.fingerprint not in (
        None, dec.PENDING_STAMP, decl.conf_fingerprint, STATE.conf_fingerprint)


def _adopted(session: ds.Session, decl: dec.Declaration, res: dict[str, Any],
             places: RawPlaces) -> dict[str, str] | None:
    """A raw breakpoint no stop placed, armed and placed at this stop when it can, else queued
    (None). Armed, it answers `why` when its place could not be written."""
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
        # Armed, its place not written: queued, since the re-arm skips a row the debugger holds.
        if decl.ref not in STATE.pending["arm"]:
            STATE.pending["arm"].append(decl.ref)
        return {"why": f"{e}; the next stop writes it again"}
    return {}


def _placed_here(decl: dec.Declaration, places: RawPlaces, cpu: str | None) -> None:
    """A raw row armed or read at this stop is placed by it: the stop's mode is written, and for
    a code row its place's stamp. A watch's place is its mode alone."""
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
    """The declarations armable in this build and session: not a stale raw address, an earlier
    session's interrupt, or an undefined symbol."""
    if STATE.store is None:
        return []
    return [d for d in STATE.store.declarations()
            if not placement.is_stale(d, _nowhere)
            # A raw watch no stop placed is placed by the first stop that reads it; a raw breakpoint
            # no stop placed is armed nowhere until declared again.
            and placement.waits(d, _last_cpu) in ((None, dec.UNPLACED) if d.kind == "watch"
                                                  else (None,))
            and not (d.kind == "interrupt" and d.origin != STATE.session_origin)
            and not (d.by == "symbol" and dec.DeclarationStore.resolve_name(
                d, STATE.table, STATE.name_index).state == "unresolved")]


def declares_code_breakpoint() -> bool:
    """Whether an armable code breakpoint is declared: the one stopper a stop's address is
    attributed to."""
    return any(d.kind == "breakpoint" for d in _armable_declarations())


def declares_untold_stopper() -> bool:
    """Whether an armable stopper is declared whose stop no address names: a change-watch, an
    interrupt breakpoint or a registerpoint."""
    return any(d.kind in ("interrupt", "regpoint")
               or (d.kind == "watch" and d.watch_mode == "change")
               for d in _armable_declarations())


def something_can_stop_it() -> bool:
    """Whether anything can bring the running machine back to the debugger, without asking it:
    the debugger's list at the last stop (it holds a row whoever armed it) and the store minus
    what is known not to be armed. Doubt errs on the side of waiting."""
    held = STATE.last_stop.get("held") or []
    if any(str(r.get("entry", "")).startswith(("BP ", "BPINT ", "BPMEM ", "BPPM ", "BPLM ",
                                                grammar.CONDITION_ROW))
           for r in held):
        return True
    # A declaration still on the arm queue is armed only AT a stop, so it cannot produce one.
    queued = set(STATE.pending["arm"])
    return any(not (d.kind == "watch" and d.watch_mode != "change") and d.ref not in queued
               for d in _armable_declarations())


def breakpoint_interrupt(session: ds.Session, number: int, ah: int | None,
                         detail: bool = False) -> dict[str, Any]:
    """The body of the `breakpoint_interrupt` tool."""
    want = grammar.interrupt_row(number, ah)
    decl = declare("interrupt", "address", want)
    if not session.at_debugger():
        is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
        return st.reply(ref=want, stored=True, already_stored=not is_new, armed=False,
                      state="pending", **STATE.queue_arm(want))
    if any(b["entry"] == want for b in session.breakpoints()):
        is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
        return st.reply(ref=want, stored=True, already_stored=not is_new, armed=True,
                      entry=want, note="this interrupt breakpoint was already armed")
    # Stored first, as its twins are: a store that cannot be written leaves nothing armed
    # unaccounted for.
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    try:
        delta = st.delta_if_asked(session.breakpoint_interrupt(number, ah), st.DETAIL_TEXT_KEEP,
                                   detail)
    except ds.Invalid:
        # Not armed, so not kept: a stored row would list as one that can stop the guest.
        if is_new:
            placement.to_invalid(lambda: current_store().remove(ref=want, kind="interrupt"))
        raise
    num, ah = grammar.parse_interrupt_row(want)
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
        # An address declared again in another spelling is the same declaration, handled under its
        # stored spelling.
        ref, decl = stored, dataclasses.replace(decl, ref=stored)
    # Resolve before storing, so an ambiguous name is refused leaving nothing; an unresolved one is
    # kept (it may resolve next build).
    res = placement.resolve_ref(decl, "CS", session)
    if res["state"] == "ambiguous":
        raise ds.Invalid("unknown_ref", res["why"])   # refuse, and store nothing
    # One row is one declaration: a second ref resolving to a held row's address would leave the
    # other declared over a row the debugger no longer has after a clear.
    if res["state"] == "armable":
        # The mode is the last stop's, from the record: a channel round trip per declaration is not
        # worth a fact the survey holds.
        last = STATE.last_machine()
        others = _bp_holders(session, last[0] if last else "", (res["seg"], res["off"]),
                             but=ref)
        if others:
            raise ds.Invalid("ambiguous_ref",
                f"{grammar.canonical_seg_off(res['seg'], res['off'])} is already declared under "
                             f"{others[0].ref!r}: one breakpoint row is one declaration, so "
                             f"clear that ref or use it")
    # Declared again in the other mode: the row's address was fixed in that stop's mode, so the same
    # text is another byte now.
    moved = _moved(next((d for d in current_store().declarations()
                         if d.kind == "breakpoint" and d.ref == ref), None), decl)
    is_new = cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # A re-declaration is a no-op, not a refusal; the arming below still runs, so a lost debugger
    # entry is re-armed.
    already = not is_new

    def pending() -> dict[str, Any]:
        # Stored, armed at the next stop: the guest runs.
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                        armed=False, state="pending", **STATE.queue_arm(ref))

    if res["state"] == "unresolved":
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unresolved",
                      note=f"{ref} {placement.NOT_IN_TABLE}; the declaration is kept and "
                           f"arms nothing until a table defines it")
    if res["state"] == "unarmable":
        # Stored but not armable now: the guest runs (armed at the next stop) or a real-mode table
        # has no base yet.
        if not session.at_debugger():
            return pending()
        return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                      armed=False, state="unarmable", why=res["why"])
    # The row as stored waits at this stop when no stop placed it, or one of the other mode did and
    # this one cannot place it again.
    if session.at_debugger():
        stored_row = next(d for d in current_store().declarations()
                          if d.kind == "breakpoint" and d.ref == ref)
        if (mode := placement.waits(stored_row, places.cpu)) is not None:
            return st.reply(ref=ref, by=chosen, stored=True, already_stored=already,
                            armed=False, state="unarmable",
                            why=placement.waits_why(
                                mode, "Declare it again",
                                places.mode_here(chosen, ref) is not None))
    # Already armed? A re-declaration must not stack a second entry. Check and arm are both inside
    # the try: `session.breakpoints()` refuses a running machine as `arm` does, and a by-address ref
    # has not touched it yet.
    want = ("BP", res["seg"], res["off"])
    try:
        placement._listening(session)     # a placement reads a stopped machine's registers
        existing = next((b for b in session.breakpoints()
                         if grammar.bp_row_target(b["entry"]) == want), None)
        if existing is not None and moved:
            session.clear_code_breakpoint(res["seg"], res["off"])
            existing = None
        held = existing or session.arm_code_breakpoint(res["seg"], res["off"])
    except ds.Invalid as e:
        # The machine is running (kept, armed at the next stop) or moved between resolving and
        # arming (kept, said as unarmed). A running-kind refusal queues even if the peek says
        # stopped: the stop came between, and the next contact drains the queue.
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


def list_breakpoints(session: ds.Session) -> dict[str, Any]:
    """The body of the `declaration_list(kind="breakpoint")` tool."""
    store = current_store()
    held, read, machine = STATE.list_basis(session)
    places = RawPlaces(session)
    out: list[dict[str, Any]] = []
    mine: set[tuple[str, int, int]] = set()
    mine_int: set[str] = set()
    for decl in store.declarations():
        if decl.kind == "interrupt":
            # An interrupt has no address to resolve: its declaration is its row text, matched by
            # equality against the held rows.
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
        # A stale raw address is listed as such unless this session has it armed anyway. An orphan
        # takes `orphan` as its state only where it would otherwise be `gone` or `stale`: facts that
        # decide what a caller does next (armed, unresolved) are not replaced.
        if orphan(decl):
            item["orphan"] = True
        if state in ("unresolved", "ambiguous", "unarmable"):
            # Said as such whatever build it was declared against.
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
                and any(grammar.bp_row_target(b["entry"]) == ("BP", res["seg"], res["off"])
                        for b in held)):
            item["state"] = "orphan" if orphan(decl) else "stale"
            item["why"] = _ORPHAN_WHY if orphan(decl) else _STALE_WHY
        else:
            want = ("BP", res["seg"], res["off"])
            item["entry"] = f"BP {res['seg']:04X}:{res['off']:04X}"
            item["marked"] = res["marked"]
            listed = any(grammar.bp_row_target(b["entry"]) == want for b in held)
            if listed:
                mine.add(want)
            _held_state(item, decl, listed)
        out.append(item)
    pending_states(out)
    # A row a clear has queued for removal is not foreign.
    queued = {str(sp["entry"]) for sp in STATE.pending["disarm"]}
    foreign = [b["entry"] for b in held
               if (t := grammar.bp_row_target(b["entry"])) is not None
               and t[0] == "BP" and t not in mine and b["entry"] not in queued]
    # A BPINT row the store did not place is foreign too, matched by whole text.
    foreign += [b["entry"] for b in held
                if b["entry"].startswith("BPINT ") and b["entry"] not in mine_int
                and b["entry"] not in queued]
    dated: dict[str, Any] = {} if read else {"last_stop": STATE.dated()}
    return st.reply(breakpoints=out, foreign=foreign, debugger_read=read, **dated)


def require_a_match(store: dec.DeclarationStore, ref: str | None,
                     kinds: tuple[str, ...]) -> str | None:
    """A `ref` that matches no declaration of these kinds is refused, naming the refs the store
    holds: a zero in green is indistinguishable from "nothing to clear" for a caller who
    misspelt the ref. No `ref` clears everything."""
    if ref is None:
        return None
    # An address matches in any spelling: `held_ref` gives the stored one.
    mine = [d.ref for d in store.declarations() if d.kind in kinds]
    held = store.held_ref(ref, kinds)
    if held is not None:
        return held
    have = ", ".join(repr(r) for r in mine) if mine else "none at all"
    if kinds == ("regpoint",):
        raise ds.Invalid("unknown_ref",
            f"{ref!r} matches no regpoint declaration, so nothing was cleared. The regpoint "
            f"declarations this conf holds: {have}. A condition matches in any spelling "
            f"`regpoint_add` takes")
    family = "breakpoint" if "breakpoint" in kinds else "watch"
    raise ds.Invalid("unknown_ref",
        f"{ref!r} matches no {family} declaration, so nothing was cleared. "
                     f"The {family} declarations this conf holds: {have}. A SEG:OFF "
                     f"matches in any spelling; a symbol or a `BPINT NN` / `BPINT NN "
                     f"AH=NN` row is the exact string the declaring reply carried")



def pending_note(running: bool, pending: list[str]) -> str | None:
    """Why a row is still on the debugger after a clear: a running guest takes the command at
    the next stop, but a stopped one whose debugger refused it is not "running", which would
    send a caller to wait for a stop that already happened."""
    if not pending:
        return None
    if running:
        return ("the guest is running, so the debugger's rows for these are removed at the next "
                "stop (`applied_on_stop.disarmed`); the declarations are cleared now")
    return ("removing these rows now failed (`pending_disarm`), so they are retried "
            "on the next call (`applied_on_stop.disarmed`); the declarations are cleared now")


def clear_breakpoints(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `declaration_clear(kind="breakpoint")` tool: a `ref` alone (or nothing)
    takes breakpoints and interrupts; watches are a different tool."""
    store = current_store()
    ref = require_a_match(store, ref, ("breakpoint", "interrupt"))
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    # The guest runs: rows are queued for the next stop and the declarations dropped at once; a name
    # resolves against the last stop's machine.
    running = not session.at_debugger()
    # What each declaration armed is worked out before anything changes: this session's record (a
    # reload can have armed a second), or the live resolution while stopped, nothing while running.
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
            num, ah = grammar.parse_interrupt_row(decl.ref)
            if not rows and not running:
                rows = [{"kind": "int", "num": num, "ah": ah, "entry": decl.ref}]
            plan.append((decl, rows, functools.partial(session.clear_interrupt_breakpoint,
                                                        num, ah)))
    # Then the store, in one write: a failed write changes nothing and leaves every row armed.
    removed = cast(int, placement.to_invalid(
        lambda: store.remove(ref=ref, kind=("breakpoint", "interrupt"))))
    for decl, rows, clear in plan:
        STATE.armed.pop(("bp", decl.ref), None)
        for spec in rows:
            named = str(spec["entry"]) if decl.kind == "breakpoint" else decl.ref
            one = (functools.partial(clear, spec["seg"], spec["off"])
                   if decl.kind == "breakpoint" else clear)
            disarm_one(spec, named, running, disarmed, pending_disarm, one)
    unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=pending_note(running, pending_disarm))


def unqueue_cleared(store: dec.DeclarationStore) -> None:
    """The arm queue holds refs a breakpoint and a watch may share: a queued ref stays while any
    family declares it."""
    held = {d.ref for d in store.declarations()}
    STATE.pending["arm"][:] = [r for r in STATE.pending["arm"] if r in held]


def _aliased(ref: str, places: list[tuple[int, int]]) -> str | None:
    """The refusal when another ref already armed a watch at one of `places`: a clear of either
    would disarm both in silence."""
    for (family, other), rows in STATE.armed.items():
        if family != "watch" or other == ref:
            continue
        for seg, off in places:
            if any(r["kind"] == "watch" and (r["seg"], r["off"]) == (seg, off) for r in rows):
                return (f"{grammar.canonical_seg_off(seg, off)} is already armed under {other!r}: "
                        "one watchpoint is one declaration, so clear that ref or use it")
    return None


def watch_add(session: ds.Session, ref: str, mode: str, width: int, fmt: str,
              by: str, trigger: str = "", trigger_type: str = "w") -> dict[str, Any]:
    """The body of the `watch_add` tool."""
    placement.to_invalid(lambda: dec.check_watch_mode(mode))
    chosen = placement.decide_by(ref) if by == "auto" else by
    placement.address_shape(ref, chosen)
    trig, side = checks.tap_fields(mode, trigger, trigger_type, width, fmt)
    if side == "r":
        width, fmt = 1, "u8"
    if chosen == "pointer":
        # The base is judged first, so a ref with no pointer to start from is refused for that and
        # not for the format.
        probe = placement.resolve_ref(
            placement.to_invalid(lambda: dec.Declaration("watch", "pointer", ref, width=1,
                                                         fmt="u8", watch_mode="show")),
            "DS", session)
        if probe["state"] in ("unresolved", "ambiguous") and "why" in probe:
            raise ds.Invalid("unknown_ref", probe["why"])
    if fmt == "auto":
        # The type comes from the symbol table when the caller gave none; through a pointer, the
        # field's own format; else the default scalar of the given width.
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
    if mode in dec.TAP_MODES:
        return _tap_add(session, chosen, ref, mode, width, fmt, trig, side)
    places = RawPlaces(session)
    decl = declare("watch", chosen, ref,
                   cpu=places.mode_here(chosen, ref) if chosen == "address" else None,
                   width=width, fmt=fmt, watch_mode=mode)
    stored = current_store().held_ref(ref, ("watch",))
    if stored is not None and stored != ref:
        # An address declared again in another spelling is the same declaration, under its stored
        # spelling.
        ref, decl = stored, dataclasses.replace(decl, ref=stored)
    # Declared again in the other mode: its rows compare SEG:OFF in the mode of the moment, so the
    # other mode's rows watch another byte and are made again.
    moved = _moved(_stored_watch(ref), decl)
    res = placement.resolve_ref(decl, "DS", session)
    # A name matching several symbols is refused before storing, as in `breakpoint_at`: stored, the
    # change path read `seg` off a resolution that has none.
    if res["state"] == "ambiguous":
        raise ds.Invalid("unknown_ref", res["why"])
    if mode == "change" and res["state"] == "armable":
        aliased = _aliased(ref, change_bytes(res["seg"], res["off"], width))
        if aliased is not None:
            raise ds.Invalid("ambiguous_ref", aliased)
    already = not cast(bool, placement.to_invalid(lambda: current_store().add(decl)))
    # The row as stored waits at this stop when one of the other mode placed it and this one cannot
    # place it again.
    waiting: dict[str, Any] = {}
    if session.at_debugger() and _watch_waits(waiting, cast(dec.Declaration, _stored_watch(ref)),
                                              places, None):
        return st.reply(ref=ref, by=chosen, mode=mode, fmt=fmt, length=width, stored=True,
                        already_stored=already, armed=False, **waiting)
    # Through a pointer the reply says through what; a null pointer is a state the stop re-resolves.
    extra: dict[str, Any] = {"pointer": res["pointer"]} if "pointer" in res else {}
    if chosen == "pointer" and res["state"] in ("null_pointer", "unarmable"):
        return st.reply(ref=ref, by=chosen, mode=mode, fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=res["state"],
                      why=res["why"], **extra)
    if mode == "show":
        # A show watch arms nothing: a plain read at every stop. Its state is the resolution,
        # spelled as `declaration_list(kind="watch")` and a stop's `watches` spell it.
        state = "evaluated" if res["state"] == "armable" else res["state"]
        return st.reply(ref=ref, by=chosen, mode="show", fmt=fmt, length=width, stored=True,
                      already_stored=already, armed=False, state=state, **extra)
    # Not placeable now: kept, answered with the resolution's own reason or the table's; a running
    # guest queues it.
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
    # Already armed? A re-declared change watch must not stack a second BPPM/BPM; check and arm are
    # inside the try as in `breakpoint_at`.
    try:
        placement._listening(session)     # a placement reads a stopped machine's registers
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
    # Every row is the watch's, held or just armed, so a clear deletes them all. A re-declaration
    # that found every row held still carries the Pr caveat.
    entries = [str(made[p]["armed"]) if p in made else _watch_entry(*p, mode) for p in covered]
    for (s_, o_), entry in zip(covered, entries, strict=True):
        STATE.note_armed(ref, {"kind": "watch", "seg": s_, "off": o_, "entry": entry})
    caveat = {"caveat": _PR_WATCH_CAVEAT} if mode.startswith("Pr") else {}
    sent = {"command": str(made[missing[0]]["command"])} if missing else {}
    return st.reply(ref=ref, by=chosen, mode="change", fmt=fmt, length=width, stored=True,
                    already_stored=already, armed=True, state="armed", entry=entries[0],
                    entries=entries, **sent, **caveat, **extra)


def _tap_add(session: ds.Session, chosen: str, ref: str, mode: str, width: int, fmt: str,
             trigger: str | None, side: str | None) -> dict[str, Any]:
    """A count or capture watch: stored once its tap is installed, which needs the machine
    stopped. Declared again unchanged, a tap still installed is a no-op."""
    places = RawPlaces(session)
    decl = declare("watch", chosen, ref,
                   cpu=places.mode_here(chosen, ref) if chosen == "address" else None,
                   width=width, fmt=fmt, watch_mode=mode, trigger=trigger, trigger_type=side)
    store = current_store()
    held = store.held_ref(ref, ("watch",))
    stored = _stored_watch(held) if held is not None else None
    if stored is not None and not dec.same_place(stored, decl):
        raise ds.Invalid("bad_argument",
                         f"{ref} is already declared as a {stored.watch_mode} watch: one ref is "
                         "one declaration, so clear it before declaring it another way")
    reply: dict[str, Any] = {"ref": ref, "by": chosen, "mode": mode, "fmt": fmt, "length": width,
                             "stored": True}
    if side is not None:
        reply.update(trigger_type=side, **({"trigger": trigger} if trigger else {}))
    if stored is not None and stored.ref in STATE.taps and taps.installed(session, stored.ref):
        tap = STATE.taps[stored.ref]
        return st.reply(**{**reply, "ref": stored.ref}, already_stored=True, armed=True,
                        state="armed", tally_id=str(tap.id), entry=f"TAP {tap.id}")
    if stored is not None and stored.ref in STATE.taps:
        taps.drop(session, stored.ref)       # displaced: tapped again as the page is now
    tap = taps.arm(session, stored or decl)
    try:
        already = not cast(bool, placement.to_invalid(lambda: store.add(stored or decl)))
    except ds.Invalid:
        taps.drop(session, (stored or decl).ref)
        raise
    return st.reply(**reply, already_stored=already, armed=True, state="armed",
                    tally_id=str(tap.id), entry=f"TAP {tap.id}",
                    addr=f"{tap.seg:04X}:{tap.off:08X}",
                    **({"trigger_addr": f"{tap.trigger[0]:04X}:{tap.trigger[1]:08X}"}
                       if tap.trigger else {}))


def _unarm_moved(session: ds.Session, ref: str, covered: list[tuple[int, int]]) -> None:
    """A change watch's rows of the other mode deleted and forgotten; a row still listed refuses
    the arm, since it would be counted as this mode's."""
    gone, kept = delete_watch_rows(session, covered)
    for entry in gone:
        STATE.snapshot_forget(entry)
    STATE.armed.pop(("watch", ref), None)
    if kept:
        raise ds.Invalid("unexpected_answer", f"the rows the other mode armed at "
                         f"{', '.join(grammar.canonical_seg_off(*p) for p in kept)} are still "
                         "listed after their delete: nothing was armed in this mode")


def _stored_watch(ref: str) -> dec.Declaration | None:
    return next((d for d in current_store().declarations() if d.kind == "watch" and d.ref == ref),
                None)


def _tap_counts(session: ds.Session) -> dict[int, dict[str, int]] | str:
    """One `TAPLIST` for every tap of a survey, or why it could not be read."""
    try:
        return taps.listed(session)
    except ds.Invalid as e:
        return str(e)


def _tap_item(decl: dec.Declaration, counts: dict[int, dict[str, int]] | str,
              at_stop: bool) -> dict[str, Any]:
    """A count or capture's own fields in a survey or a listing."""
    if isinstance(counts, str):
        return {"state": "unlisted", "why": counts}
    item = taps.evaluate(decl, counts, at_stop)
    return {**({"trigger": decl.trigger} if decl.trigger else {}), **item}


def list_watches(session: ds.Session) -> dict[str, Any]:
    """The body of the `declaration_list(kind="watch")` tool."""
    store = current_store()
    held, read, machine = STATE.list_basis(session)
    places = RawPlaces(session)
    out: list[dict[str, Any]] = []
    mine: set[tuple[int, int]] = set()
    counts = _tap_counts(session)
    for decl in store.declarations():
        if decl.kind != "watch":
            continue
        item: dict[str, Any] = decl_row(decl)
        item.update(mode=decl.watch_mode, length=decl.width, fmt=decl.fmt)
        if decl.watch_mode in dec.TAP_MODES:
            out.append({**item, **_tap_item(decl, counts, at_stop=False)})
            continue
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
            # Arms nothing; resolution is the state unless it is nobody's.
            if orphan(decl):
                item["state"] = "orphan"
                item["why"] = _ORPHAN_WATCH_WHY
            else:
                item["state"] = "evaluated"
        else:
            seg, off = res["seg"], res["off"]
            item["entry"] = _watch_entry(seg, off, machine[0] if machine is not None
                                         else session.where()["mode"])
            # Match by the numbers, never by spelling: the debugger's offset width varies (`BPPM
            # 00AF:6024` and `BPPM 00AF:00006024`).
            covered = change_bytes(seg, off, decl.width)
            listed = all_held(held, covered)
            mine.update(place for place in covered if watch_held(held, *place) is not None)
            _held_state(item, decl, listed)
        out.append(item)
    pending_states(out)
    queued = {(sp["seg"], sp["off"]) for sp in STATE.pending["disarm"] if sp["kind"] == "watch"}
    foreign = [b["entry"] for b in held
               if (t := grammar.bp_row_target(b["entry"])) is not None
               and t[0] in _WATCH_KINDS
               and (t[0] not in _OWN_WATCH_KINDS
                    or ((t[1], t[2]) not in mine and (t[1], t[2]) not in queued))]
    dated: dict[str, Any] = {} if read else {"last_stop": STATE.dated()}
    return st.reply(watches=out, foreign=foreign, debugger_read=read, **dated)


def clear_watches(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `declaration_clear(kind="watch")` tool."""
    store = current_store()
    ref = require_a_match(store, ref, ("watch",))
    to_go = [d for d in store.declarations()
             if d.kind == "watch" and (ref is None or d.ref == ref)]
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    running = not session.at_debugger()
    # The rows first, then the store, as in `declaration_clear(kind="breakpoint")`.
    plan: list[list[dict[str, Any]]] = []
    for decl in to_go:
        if decl.watch_mode in dec.TAP_MODES:
            tapped = STATE.taps.get(decl.ref)
            plan.append([] if tapped is None else
                        [{"kind": "tap", "ref": decl.ref, "id": tapped.id,
                          "entry": f"TAP {tapped.id}"}])
            continue
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
            if rows[0]["kind"] == "tap":
                removed_tap = taps.remove(session, decl.ref)
                if removed_tap is not None:
                    disarmed.append(removed_tap)
                continue
            # Read the list back: `disarmed` is the machine's answer, not a claim that a BPDEL must
            # have taken.
            gone, _ = delete_watch_rows(session, [(int(r["seg"]), int(r["off"])) for r in rows])
            for entry in gone:
                disarmed.append(entry)
                STATE.snapshot_forget(entry)
        except ds.Invalid:
            for spec in rows:
                STATE.pending["disarm"].append(spec)
                pending_disarm.append(str(spec["entry"]))
            STATE.pending["dirty"] = True
    unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                  pending_disarm=pending_disarm,
                  note=pending_note(running, pending_disarm))


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


def pending_states(rows: list[dict[str, Any]]) -> None:
    """A row asked to arm while the guest ran is `pending` whatever the list says now."""
    for item in rows:
        if item["ref"] in STATE.pending["arm"]:
            item["state"] = "pending"
            item.pop("why", None)


def disarm_one(spec: dict[str, Any], named: str, running: bool, disarmed: list[str],
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
