"""The bodies of the `resume` and `run_to` tools."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, cast

from scry_core import cancel, screen_map, stop_wait
from scry_core import progress as mprogress
from scry_core import reply_contract as contract

from scry_dosbox_x import arming, folds, grammar, placement, retrace, running
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import run_state as rs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.running import live
from scry_dosbox_x.state import STATE

#: What a `run_for` stop carries that a `run_to` reply has no field for.
RUN_FOR_ONLY = frozenset({"polls", "emulated_before_s", "emulated_after_s", "frame_before",
                          "frame_after", "cycles", "retrace_pending"})


#: What `stop` may go on to, how many short runs that may take, and how long each runs.
STOP_UNTIL = ("", "protected")
PROTECTED_RUNS_MAX = 256
PROTECTED_RUN_S = 0.007
#: The runs grow by one `PROTECTED_RUN_S` each up to this many, then start again: equal runs land
#: at one point of a program's own cycle.
PROTECTED_RUN_STEPS = 11


def _djgpp_held() -> bool:
    return STATE.start_symbols is not None and STATE.start_symbols.dpmi


def in_the_program(mode: str) -> bool:
    """Whether a stop in `mode` ends the walk: protected mode, and with a DJGPP table held, the
    program's own 32-bit code, never the DPMI host's 16-bit code, where it would be placed by
    the host's CS."""
    return mode == grammar.PR32_MODE if _djgpp_held() else mode.startswith("Pr")


def _walk_end() -> str:
    """Where the walk ends, in the words of its progress and its note."""
    return "the program's 32-bit code" if _djgpp_held() else "protected mode"


def to_protected(session: ds.Session,
                 progress: ds.Progress = ds.no_progress) -> tuple[int, bool]:
    """Run a stopped machine in short slices until a stop lands in protected mode
    (`in_the_program`): the runs it took and whether one did. A slice a declared stop ended is
    that stop, and ends the walk: a `BREAK` there would run past it. A `STEPIN` stays inside a
    BIOS handler, so only running leaves one. Its own cancel point is between two runs."""
    # The bound is in runs: `expired` is only the cancel point and the clock read `tick` needs.
    clock = mprogress.Ticker(0.0, progress)
    taken = 0
    while not in_the_program(session.where()["mode"]):
        if taken == PROTECTED_RUNS_MAX:
            return taken, False
        clock.expired()
        clock.tick("stop until protected: run {run} of at most {runs}, not in {end} yet, "
                   "{elapsed:.0f}s", run=taken + 1, runs=PROTECTED_RUNS_MAX, end=_walk_end())
        session.release("RUN")
        time.sleep(PROTECTED_RUN_S * (1 + taken % PROTECTED_RUN_STEPS))
        taken += 1
        if session.at_debugger():
            return taken, False
        session.break_in()
    return taken, True


def run_to_screen(screen: str, control: str, seconds: float,
                  progress: ds.Progress, disarm_watches: bool = False) -> dict[str, Any]:
    """`run_to(screen=)`: a run to the screen's anchor, or a retrace at a time until the map
    names a screen with none, as `run_to` replies."""
    session = live()

    def stop_seq(_reply: dict[str, Any]) -> int | None:
        current = STATE.as_of_current(session)
        return None if current is None else current["stop_seq"]
    return screen_map.run_to_screen(
        STATE.maps, screen, control, seconds,
        step=lambda left: retrace.run_for(session, 1, 0, left, progress,
                                          who="a run to a screen"),
        run_to_anchor=lambda anchor: run_to(anchor, control, seconds, progress),
        read=folds.map_read(session), stop_seq=stop_seq, run_for_only=RUN_FOR_ONLY,
        frame_run=lambda: screen_map.check_frame_flags(
            screen, ["disarm_watches"] if disarm_watches else []))


def resume(seconds: float, detail: bool,
           progress: ds.Progress) -> dict[str, Any]:
    """Release the guest; with a bound, wait for a stop or leave it running."""
    session = live()
    # Refused first: a `RUN` on a running guest does nothing, yet an `ok` would read as a release.
    if not session.at_debugger():
        if not session.has(dbg.RUNSTATE):
            raise rs.unknown_after_release("a resume")
        raise ds.NotStopped("the guest is already running, so there is nothing to resume")
    if seconds > 0:
        session.require_run_state("a resume with a bound")
    out = session.resume(look=seconds > 0)
    halted = out["halted"] is True
    stopped_at = cast(dict[str, str] | None, out["stopped_at"])
    base: dict[str, Any] = st.delta_if_asked(cast(str, out["output"]), st.DETAIL_TEXT_KEEP, detail)
    if isinstance(out["halted"], dict):
        base["note"] = (f"the machine was released; {out['halted']['why']}, so `stop` is how it "
                        f"comes back")
    if seconds > 0:
        began = time.monotonic()
        while not halted:
            expired, _saw_at = ds.Session.await_stop(session, began, began + seconds,
                                                      "resume", progress, label="resume")
            if expired:
                break
            # A machine not at rest when asked still runs, so keep listening.
            try:
                stopped_at = session.where()
                halted = True
            except ds.NotStopped:
                continue
            except ds.Invalid:
                stopped_at, halted = None, True
        base["waited_s"] = round(time.monotonic() - began, 3)
        if not halted:
            base["note"] = (f"no stop within {seconds:g} s; the machine is STILL RUNNING, and "
                            "the debugger's tools refuse until it stops")
        base = {"verdict": contract.OTHER_STOP if halted else contract.TIMEOUT, **base}
    if halted:
        # `where()` reads no page mark; the held one is stale until `stop_reply` replaces it.
        base.update(running.position(stopped_at, None))
    return running.stop_or_base(session, halted, base, retrace_may_stop=True)


def wait(session: ds.Session, seconds: float, progress: ds.Progress) -> dict[str, Any]:
    """Let a running guest play `seconds` and report where it ended, as `resume`'s wait does
    without the release. A stopped machine is refused, and a deliberate wait that expires is the
    answer, never a failure."""
    if session.at_debugger():
        raise ds.Invalid("not_running",
                         "the machine is stopped at the debugger: `wait` lets a running guest "
                         "play, so `resume` it first")
    session.require_run_state("a wait")
    began = time.monotonic()
    halted = False
    stopped_at: dict[str, str] | None = None
    while not halted:
        expired, _ = ds.Session.await_stop(session, began, began + seconds, "wait",
                                            progress, label="wait")
        if expired:
            break
        try:
            stopped_at = session.where()
            halted = True
        except ds.NotStopped:
            continue
        except ds.Invalid:
            stopped_at, halted = None, True
    base: dict[str, Any] = {"waited_s": round(time.monotonic() - began, 3)}
    if halted:
        base.update(running.position(stopped_at, None))
        return running.stop_or_base(session, halted, {"verdict": contract.OTHER_STOP, **base},
                                    retrace_may_stop=True)
    base["note"] = (f"the machine is still running after {seconds:g} s; a deliberate wait that "
                    f"expires is this answer, not a failure")
    return running.stop_or_base(session, halted, base)


def run_to(ref: str, control: str, seconds: float, progress: ds.Progress) -> dict[str, Any]:
    """Run to `ref`, with `control` as the place that proves the run was hot."""
    session = live()
    # One survey resolves both refs; a raw SEG:OFF reads nothing.
    by_address = (placement.decide_by(ref) == "address"
                  and placement.decide_by(control) == "address")
    machine = None if by_address else session.where_and_registers()
    mode_regs = None if machine is None else (machine[0]["mode"], machine[1])
    seg, off = placement.read_target(ref, "CS", session, machine=mode_regs)
    ctl = placement.read_target(control, "CS", session, machine=mode_regs)
    counted, left = _declared_controls(session, (seg, off), ctl, mode_regs)
    out = cast(dict[str, Any], session.run_to(seg, off, seconds, ctl, progress,
                                              declared=[place for _, place in counted]))
    armed = [out.pop("control"), *out.pop("declared")]
    refs = [control, *(name for name, _ in counted)]
    hits = sum(int(block["hits"]) for block in armed)
    verdict = out.pop("verdict")
    fields: dict[str, Any] = {
        "verdict": verdict, "target": out["target"], "ref": ref,
        **running.position(out["stopped_at"], None),      # the survey's mark replaces it
        "target_disarmed": out["breakpoint_removed"], "control_hits": hits,
        "controls": [{"ref": name, "at": block["at"], "hits_in_run": block["hits"],
                      "removed": block["removed"]}
                     for name, block in zip(refs, armed, strict=True)],
        "note": " ".join(filter(None, (out["note"], (
            f"declared controls not counted in this run: {'; '.join(left)}" if left else ""))))}
    # A run that never saw its control proves nothing about its target.
    if verdict != contract.TARGET and not hits:
        code: contract.Code = ("control_silent" if verdict == contract.TIMEOUT
                               else "cut_by_other_stop")
        message = (f"the control {control} never fired within {seconds:g} s, so {ref} not "
                   f"firing means nothing. Check that the control really is hot on this "
                   f"screen" if code == "control_silent" else
                   f"another stop ended the run before the control {control} fired, so "
                   f"nothing was measured about {ref}. {stop_wait.CUT_WAY_OUT}")
        refused = {k: v for k, v in fields.items() if k != "verdict"}
        return running.stop_or_base(session, True,
                                    {"status": "INVALID", "code": code, "message": message,
                                     **refused}, retrace_may_stop=True)
    # An arrival is attributed to its target though that breakpoint is removed by now.
    arrived = verdict == contract.TARGET
    return running.stop_or_base(session, True, fields, retrace_may_stop=not arrived,
                                made_by={"ref": ref, "by": "run_to"} if arrived else None)


def _declared_controls(session: ds.Session, target: tuple[int, int], own: tuple[int, int],
                       machine: tuple[str, dict[str, str]] | None
                       ) -> tuple[list[tuple[str, tuple[int, int]]], list[str]]:
    """Each control `breakpoint_at(role="control")` declared that is `counted` here, by ref and
    place, but one at the target or at the run's own control, which already counts; and each
    left out, with why."""
    if STATE.store is None:
        return [], []
    mode = machine[0] if machine is not None else session.where()["mode"]
    places = arming.RawPlaces(session)

    def same(a: tuple[int, int], b: tuple[int, int]) -> bool:
        return a == b if mode.startswith("Pr") else a[0] * 16 + a[1] == b[0] * 16 + b[1]
    out: list[tuple[str, tuple[int, int]]] = []
    left: list[str] = []
    for decl in STATE.store.declarations():
        if decl.kind != "breakpoint" or decl.role != "control":
            continue
        state, why, res = arming.control_state(session, decl, places, machine)
        if state != "counted":
            left.append(f"{decl.ref} ({state}{f': {why}' if why else ''})")
            continue
        place = (int(res["seg"]), int(res["off"]))
        if not any(same(place, p) for p in (target, own, *(q for _, q in out))):
            out.append((decl.ref, place))
    return out, left


def stop_in_protected_mode(session: ds.Session, progress: ds.Progress) -> dict[str, Any]:
    """`stop(until="protected")`: the stop this walk ended at, and what it took."""
    interrupted = not session.at_debugger()
    if interrupted:
        session.break_in()
    else:
        running.observe_stop(session)
        where = session.where()
        if in_the_program(where["mode"]):
            last = STATE.current_or_why(session)
            return st.reply(interrupted=False, runs_to_protected=0, last_stop=last,
                            cpu_mode=running.cpu_mode_of(where["mode"], session.paging),
                            pc=f"{where['cs']}:{where['eip']}",
                            note=f"the machine was already stopped in {_walk_end()}")
    runs, arrived = to_protected(session, progress)
    extra: dict[str, Any] = {} if arrived else {"note": (
        f"did not reach {_walk_end()} in {runs} short runs: `cause` says where it stopped, "
        "ask again")}
    if interrupted:
        extra["via"] = "break"
    return running.stop_reply(session, asked_by="stop", interrupted=interrupted,
                              runs_to_protected=runs, **extra)


def with_watches_disarmed(session: ds.Session, disarm: bool,
                          run: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """`run` with every armed change watch's rows deleted from the debugger when `disarm`, armed
    again afterwards whatever it answered: the reply names the watches disarmed, those that did
    not come back (queued for the next stop, with why), and any row the debugger kept."""
    if not disarm:
        return run()
    session.where()     # a running machine is refused before any row is touched
    disarmed, kept = _disarm_change_watches(session)
    back: dict[str, str] = {}
    try:
        reply = run()
    finally:
        # Shielded, as a cancelled run's own cleanup is: a watch left disarmed would go silent.
        with cancel.shielded():
            back = _rearm_change_watches(session, disarmed)
    for row in reply.get("watches") or []:
        if back.get(row.get("ref", "?")) == "" and row.get("state") == "gone":
            row["state"] = "armed"
    reply["disarmed_watches"] = [{"ref": ref} for ref in disarmed]
    lost = [{"ref": ref, "why": why} for ref, why in back.items() if why]
    if lost:
        reply["not_rearmed"] = lost
    if kept:
        reply["note"] = " ".join(filter(None, (reply.get("note"), (
            f"the debugger kept a row of {', '.join(kept)} after `BPDEL`, so that watch could "
            "still cut this pass"))))
    return reply


def _disarm_change_watches(session: ds.Session) -> tuple[list[str], list[str]]:
    """The change watches whose rows are now all deleted, and those the debugger kept a row of."""
    specs = [(ref, spec) for (family, ref), rows in STATE.armed.items() if family == "watch"
             for spec in rows if spec.get("kind") == "watch"]
    if not specs:
        return [], []
    picks = [arming.watch_row_pick((int(spec["seg"]), int(spec["off"])), spec)
             for _ref, spec in specs]
    gone: dict[str, bool] = {}
    for (ref, _spec), (row, absent) in zip(specs, session.delete_rows(picks), strict=True):
        gone[ref] = gone.get(ref, True) and (row is None or absent)
    for ref, all_gone in gone.items():
        if all_gone:
            # Its rows are no longer the debugger's: the re-arm records the ones it makes.
            STATE.armed.pop(("watch", ref), None)
    return [r for r, ok in gone.items() if ok], [r for r, ok in gone.items() if not ok]


def _rearm_change_watches(session: ds.Session, disarmed: list[str]) -> dict[str, str]:
    """Each disarmed watch resolved and armed again as a queued declaration is, at this stop and
    in its mode (a pointer that moved is followed): empty when it came back, else why, and then
    it stays queued for the next stop."""
    if not disarmed:
        return {}
    decls = {d.ref: d for d in (STATE.store.declarations() if STATE.store is not None else [])
             if d.kind == "watch" and d.watch_mode == "change"}
    try:
        where, regs = session.where_and_registers()
        held = session.breakpoints()
    except ds.Invalid as e:
        return {ref: _queued(ref, f"the machine could not be read after the pass: {e}")
                for ref in disarmed}
    places = arming.RawPlaces(session)
    back: dict[str, str] = {}
    for ref in disarmed:
        decl = decls.get(ref)
        if decl is None:
            back[ref] = ""          # cleared during the pass: nothing is owed
            continue
        out: dict[str, Any] = {"still_pending": []}
        armed = arming.arm_queued(session, decl, (where["mode"], regs), held, places, out)
        back[ref] = "" if armed else _queued(ref, out["still_pending"][-1])
    return back


def _queued(ref: str, why: str) -> str:
    """`why`, the watch put on the arm queue so the next stop arms it."""
    if ref not in STATE.pending["arm"]:
        STATE.pending["arm"].append(ref)
    return f"{why}; queued: the next stop arms it"
