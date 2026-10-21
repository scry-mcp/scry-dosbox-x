"""The tools that let the guest run and say where it came back: `resume` and `run_to`. The bodies
of the two tools, which the server registers; its own module because how a run is released,
waited on and judged changes for reasons the tool registrations do not."""

from __future__ import annotations

import time
from typing import Any, cast

from scry_core import reply_contract as contract

import dosbox_placement as placement
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_running import live


def resume(seconds: float, detail: bool,
           progress: ds.Progress) -> dict[str, Any]:
    """The body of the `resume` tool. With a bound it waits for a stop: `OTHER_STOP` with the
    stop's survey, or `TIMEOUT` with the machine LEFT RUNNING; with none it waits for nothing
    and carries no verdict, though an F5 that never left the debugger is still a stop."""
    session = live()
    # A GUEST ALREADY RUNNING IS REFUSED BEFORE ANY CHECK THAT NEEDS THE MACHINE: an F5 there
    # does nothing, and an `ok` for it reads exactly like the release of a stopped machine.
    if not session.at_debugger():
        raise ds.NotStopped("the guest is already running, so there is nothing to resume")
    out = session.resume()
    halted = bool(out["halted"])
    stopped_at = cast(dict[str, str] | None, out["stopped_at"])
    base: dict[str, Any] = st.delta_if_asked(cast(str, out["screen"]), st.DETAIL_TEXT_KEEP, detail)
    if seconds > 0:
        began = time.monotonic()
        while not halted:
            expired, _saw_at = ds.Session.await_stop(session, began, began + seconds,
                                                      "resume", progress, label="resume")
            if expired:
                break
            # AN ANNOUNCED STOP IS READ BACK: a machine not at rest when asked still runs, so
            # the wait listens on for the rest of its bound. A pane cut another way is a stop
            # whose position could not be read, said by the stop reply's own enrichment.
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
                            "the console tools refuse until it stops")
        base = {"verdict": contract.OTHER_STOP if halted else contract.TIMEOUT, **base}
    if halted:
        # NO PAGE/NOPG MARK HERE: `where()` reads none, and the one the session holds is the stop
        # before's; the stop's own survey (`stop_reply`) replaces this with the mark it read.
        base.update(running.position(stopped_at, None))
    # A HALT IS A STOP, so it carries the full stop reply: registers, the
    # watches evaluated, its `cause` and the E9 block. A machine still running has
    # nothing to read, so it comes back with just the base.
    return running.stop_or_base(session, halted, base, retrace_may_stop=True)


def run_to(ref: str, control: str, seconds: float, progress: ds.Progress) -> dict[str, Any]:
    """The body of the `run_to` tool."""
    session = live()
    # ONE SURVEY for the resolution: a symbol needs the mode and the CS
    # selector, and reading them as two round trips before the run's own third was two
    # avoidable console trips per `run_to` by name. A raw SEG:OFF reads nothing here.
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
    # `target` is the session's own spelling of the place, `ref` the caller's.
    fields: dict[str, Any] = {
        "verdict": verdict, "target": out["target"], "ref": ref,
        **running.position(out["stopped_at"], None),      # the survey's mark replaces it
        "target_disarmed": out["breakpoint_removed"], "control_hits": hits,
        "controls": [{"ref": control, "at": armed["at"], "hits_in_run": hits,
                      "removed": armed["removed"]}],
        "note": out["note"]}
    # A RUN THAT MEASURED NOTHING ABOUT ITS CONTROL proves nothing about its target: the bound
    # ran out with the control never fired, or another stop ended the run before it could
    # fire. Both are refused, with the stop the run left surveyed beside the refusal.
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
    # AN ARRIVAL IS THE STOP `run_to` MADE, attributed to its target although the breakpoint
    # that made it is removed by now; a stop elsewhere may be a retrace `run_for` left.
    arrived = verdict == contract.TARGET
    return running.stop_or_base(session, True, fields, retrace_may_stop=not arrived,
                                made_by={"ref": ref, "by": "run_to"} if arrived else None)
