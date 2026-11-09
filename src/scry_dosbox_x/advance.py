"""The bodies of the `resume` and `run_to` tools."""

from __future__ import annotations

import time
from typing import Any, cast

from scry_core import reply_contract as contract
from scry_core import screen_map

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import folds, placement, retrace, running
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
PROTECTED_RUNS_MAX = 64
PROTECTED_RUN_S = 0.02


def to_protected(session: ds.Session) -> tuple[int, bool]:
    """Run a stopped machine in short slices until a stop lands in protected mode: the runs it
    took and whether one did. A slice a declared stop ended is that stop, and ends the walk: a
    `BREAK` there would run past it. A `STEPIN` stays inside a BIOS handler, so only running
    leaves one."""
    taken = 0
    while not session.where()["mode"].startswith("Pr"):
        if taken == PROTECTED_RUNS_MAX:
            return taken, False
        session.release("RUN")
        time.sleep(PROTECTED_RUN_S)
        taken += 1
        if session.at_debugger():
            return taken, False
        session.break_in()
    return taken, True


def run_to_screen(screen: str, control: str, seconds: float,
                  progress: ds.Progress) -> dict[str, Any]:
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
        read=folds.map_read(session), stop_seq=stop_seq, run_for_only=RUN_FOR_ONLY)


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
    out = cast(dict[str, Any], session.run_to(seg, off, seconds, ctl, progress))
    armed = out.pop("control")
    hits = int(armed["hits"])
    verdict = out.pop("verdict")
    fields: dict[str, Any] = {
        "verdict": verdict, "target": out["target"], "ref": ref,
        **running.position(out["stopped_at"], None),      # the survey's mark replaces it
        "target_disarmed": out["breakpoint_removed"], "control_hits": hits,
        "controls": [{"ref": control, "at": armed["at"], "hits_in_run": hits,
                      "removed": armed["removed"]}],
        "note": out["note"]}
    # A run that never saw its control proves nothing about its target.
    if verdict != contract.TARGET and not hits:
        code: contract.Code = ("control_silent" if verdict == contract.TIMEOUT
                               else "cut_by_other_stop")
        message = (f"the control {control} never fired within {seconds:g} s, so {ref} not "
                   f"firing means nothing. Check that the control really is hot on this "
                   f"screen" if code == "control_silent" else
                   f"another stop ended the run before the control {control} fired, so "
                   f"nothing was measured about {ref}")
        refused = {k: v for k, v in fields.items() if k != "verdict"}
        return running.stop_or_base(session, True,
                                    {"status": "INVALID", "code": code, "message": message,
                                     **refused}, retrace_may_stop=True)
    # An arrival is attributed to its target though that breakpoint is removed by now.
    arrived = verdict == contract.TARGET
    return running.stop_or_base(session, True, fields, retrace_may_stop=not arrived,
                                made_by={"ref": ref, "by": "run_to"} if arrived else None)


def stop_in_protected_mode(session: ds.Session) -> dict[str, Any]:
    """`stop(until="protected")`: the stop this walk ended at, and what it took."""
    interrupted = not session.at_debugger()
    if interrupted:
        session.break_in()
    else:
        running.observe_stop(session)
        where = session.where()
        if where["mode"].startswith("Pr"):
            last = STATE.current_or_why(session)
            return st.reply(interrupted=False, runs_to_protected=0, last_stop=last,
                            cpu_mode=running.cpu_mode_of(where["mode"], session.paging),
                            pc=f"{where['cs']}:{where['eip']}",
                            note="the machine was already stopped in protected mode")
    runs, arrived = to_protected(session)
    extra: dict[str, Any] = {} if arrived else {"note": (
        f"did not reach protected mode in {runs} short runs: `cause` says where it stopped, "
        "ask again")}
    if interrupted:
        extra["via"] = "break"
    return running.stop_reply(session, asked_by="stop", interrupted=interrupted,
                              runs_to_protected=runs, **extra)
