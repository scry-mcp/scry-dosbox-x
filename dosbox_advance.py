"""The tools that let the guest run and say where it came back: `resume` and `run_to`. The bodies
of the two tools, which the server registers; its own module because how a run is released,
waited on and judged changes for reasons the tool registrations do not."""

from __future__ import annotations

import time
from typing import Any, cast

import dosbox_placement as placement
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_running import live


def resume(e9: str, e9_filter: str, e9_stamp: str | None, seconds: float, detail: bool,
           progress: ds.Progress) -> dict[str, Any]:
    """The body of the `resume` tool."""
    session = live()
    # A GUEST ALREADY RUNNING IS REFUSED BEFORE ANY CHECK THAT NEEDS THE MACHINE: an F5 there
    # does nothing, and an `ok` for it reads exactly like the release of a stopped machine.
    if not session.at_debugger():
        raise ds.NotStopped("the guest is already running, so there is nothing to resume")
    out = session.resume()
    base = dict(halted=out["halted"], stopped_at=out["stopped_at"],
                **st.delta_if_asked(cast(str, out["screen"]), 2000, detail))
    if not out["halted"] and seconds > 0:
        began = time.monotonic()
        expired, _saw_at = ds.Session.await_stop(session, began, began + seconds, "resume",
                                                  progress, label="resume")
        base["waited_s"] = round(time.monotonic() - began, 3)
        if not expired:
            try:
                base["stopped_at"] = session.where()
                base["halted"] = True
            except ds.NotStopped:
                base["note"] = ("the debugger announced a stop and the machine was not at rest "
                                "when asked: it is RUNNING")
        else:
            base["note"] = (f"no stop within {seconds:g} s; the machine is STILL RUNNING, and "
                            "the console tools refuse until it stops")
    # A HALT IS A STOP, so it carries the full stop reply: registers, the
    # watches evaluated, the attribution and the E9 summary. A machine still running has
    # nothing to read, so it comes back with just the base.
    return running.stop_or_base(session, bool(base["halted"]), e9, e9_filter, e9_stamp, base,
                                retrace_may_stop=True)


def run_to(ref: str, control: str, seconds: float, e9: str, e9_filter: str,
           e9_stamp: str | None, progress: ds.Progress) -> dict[str, Any]:
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
    out = session.run_to(seg, off, seconds, ctl, progress)
    out["ref"] = ref            # `target` is the session's own spelling, kept as it came
    # THE CONTROL'S VERDICT: a bound that ran out with
    # the control armed and NEVER fired is not a non-arrival, it is a run that proved
    # nothing, and it says so as INVALID with the account attached.
    hits = out.get("control")
    if out.get("running") and isinstance(hits, dict) and not hits["hits"]:
        return st.reply(status="INVALID", code="control_silent",
                      message=f"the control {control} never fired within {seconds}s, so {ref} "
                             f"not firing means nothing. Check that the control really is hot "
                             f"on this screen; both breakpoints are still armed",
                      **cast(dict[str, Any], out))
    # ARRIVED or stopped ELSEWHERE both mean the machine is stopped, so both carry the full
    # stop reply; a bound that expired left it running and there is nothing to read.
    # An arrival is the stop `run_to` made; a stop elsewhere may be a retrace `run_for` left.
    return running.stop_or_base(session, not out.get("running"), e9, e9_filter, e9_stamp,
                         cast(dict[str, Any], out), retrace_may_stop=not out.get("arrived"))
