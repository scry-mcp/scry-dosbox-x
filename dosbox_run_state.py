"""Whether the machine is at the debugger, and how it is brought there; `Session` delegates here.

The session's own flag answers while the machine is parked. Past a release only the debugger knows,
and `RUNSTATE` is how it is asked; a build without it is told stopped by `BREAK`'s own answer.
"""

from __future__ import annotations

import time

from scry_core import cancel, prose
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress
from scry_core.reply_contract import Code, Invalid

import dosbox_debugger as dbg
import dosbox_session as ds

#: How long `start` waits for the debugger to answer stopped, the `-version` probe's time included.
READY_TIMEOUT_S = 30.0
#: From `BREAK` on the channel to `RUNSTATE` saying stopped.
BREAK_IN_WAIT_S = 5.0
#: The line a build without `debugger headless` gives `BREAK` when it has no terminal to draw on:
#: its debugger never stops.
DEBUGGER_UNAVAILABLE = "is not available unless you start DOSBox-X from a terminal"


def require_stopped(ses: ds.Session, what: str) -> None:
    if ses.at_debugger():
        return
    if not ses.has(dbg.RUNSTATE):
        raise dbg.unknown_after_release(what)
    raise ds.NotStopped(f"the guest is running, so the debugger cannot take {what}: it needs "
                        "the machine stopped. `stop` brings it back, or a breakpoint armed "
                        "before it was released")


def require_run_state(ses: ds.Session, what: str) -> None:
    if not ses.has(dbg.RUNSTATE):
        raise dbg.no_run_state(what)


def wait_ready(ses: ds.Session, timeout: float, progress: Progress = no_progress) -> float:
    t0 = time.monotonic()
    next_tick = t0 + PROGRESS_EVERY_S
    while True:
        cancel.check()
        rc = ses.proc.poll()
        if rc is not None:
            raise Invalid("session_broken",
                f"the emulator {prose.ended_by(rc)} before its debugger answered. That is "
                f"not a slow start: the last thing it printed was "
                f"{ses.output_tail(400).strip()!r}")
        try:
            if ses._first_stop():
                ses.mark_stopped()
                return round(time.monotonic() - t0, 3)
        except Invalid as exc:
            if exc.code != "no_channel" or time.monotonic() - t0 >= timeout:
                raise
        now = time.monotonic()
        if now - t0 >= timeout:
            raise Invalid("session_broken",
                f"the debugger did not answer stopped within {timeout}s and the emulator is "
                f"still running. The last thing it printed was "
                f"{ses.output_tail(400).strip()!r}")
        if now >= next_tick:
            next_tick = now + PROGRESS_EVERY_S
            progress(now - t0, None, f"start: waiting for the debugger, "
                                     f"{now - t0:.0f}s of {timeout:g}s")
        time.sleep(0.05)


def first_stop(ses: ds.Session) -> bool:
    """With no `RUNSTATE` a `BREAK` makes sure of it: the debugger answers it once it holds the
    machine, and says when it cannot. A build whose binary names `RUNSTATE` and whose debugger
    does not take it is read as one without."""
    if ses.has(dbg.RUNSTATE):
        ok, lines = ses.exec(dbg.RUNSTATE)
        if ok or dbg.NOT_RECOGNIZED not in lines:
            return dbg.take_run_state(ses, ok, lines)
        ses.commands = ses.commands - {dbg.RUNSTATE}
    send_break(ses, "session_broken", "the debugger cannot stop this machine: `BREAK` was refused")
    return True


def send_break(ses: ds.Session, code: Code, refused: str) -> None:
    """`BREAK` on the channel, refused as `code` when the debugger did not take it."""
    ok, lines = ses.control.request("BREAK")
    said = " / ".join(lines)
    if not ok or DEBUGGER_UNAVAILABLE in said:
        raise Invalid(code, f"{refused}: {said or 'no reason given'}")


def stop_at_bound(ses: ds.Session) -> bool:
    if ses.at_debugger():
        return False
    ses.break_in()
    return True


def break_in(ses: ds.Session, seconds: float) -> float:
    """Wait for `RUNSTATE` to say stopped; with no `RUNSTATE`, `BREAK`'s own answer says it."""
    send_break(ses, "unexpected_answer", "the debugger channel refused BREAK")
    began = time.monotonic()
    if not ses.has(dbg.RUNSTATE):
        ses.mark_stopped()
        return 0.0
    while time.monotonic() - began < seconds:
        cancel.check()
        if dbg.read_run_state(ses):
            return round(time.monotonic() - began, 2)
        ds.gone_if_dead(ses, began, seconds, "the debugger to stop")
        time.sleep(dbg.POLL_PAUSE_S)
    raise Invalid("not_settled",
        f"the debugger channel accepted BREAK and `RUNSTATE` did not say stopped within "
        f"{seconds} s: the guest may still be running. Asking `stop` again is allowed; if it "
        f"fails as well, `close` then `start`")
