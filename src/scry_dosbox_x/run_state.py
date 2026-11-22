"""Whether the machine is at the debugger, and how it is brought there; `Session` delegates here.

The session's own flag answers while the machine is parked. Past a release only the debugger knows,
and `RUNSTATE` is how it is asked; a build without it is told stopped by `BREAK`'s own answer.
"""

from __future__ import annotations

import time
from typing import Any

from scry_core import cancel, prose
from scry_core import reply_contract as contract
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress
from scry_core.reply_contract import Code, Invalid

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import session as ds

#: How long `start` waits for the debugger to answer stopped, the `-version` probe's time included.
READY_TIMEOUT_S = 30.0
#: From `BREAK` on the channel to `RUNSTATE` saying stopped.
BREAK_IN_WAIT_S = 5.0
#: The pause between two `RUNSTATE`s of a wait: shorter than a frame takes the emulator, or a
#: run by retraces waits on the pause rather than on the guest.
POLL_PAUSE_S = 0.002
#: The line a build without `debugger headless` gives `BREAK` when it has no terminal to draw on:
#: its debugger never stops.
DEBUGGER_UNAVAILABLE = "is not available unless you start DOSBox-X from a terminal"


def require_stopped(ses: ds.Session, what: str) -> None:
    if ses.at_debugger():
        return
    if not ses.has(dbg.RUNSTATE):
        raise unknown_after_release(what)
    raise ds.NotStopped(f"the guest is running, so the debugger cannot take {what}: it needs "
                        "the machine stopped. `stop` brings it back, or a breakpoint armed "
                        "before it was released")


def require_run_state(ses: ds.Session, what: str) -> None:
    if not ses.has(dbg.RUNSTATE):
        raise no_run_state(what)


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
            return take_run_state(ses, ok, lines)
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
        if read_run_state(ses):
            return round(time.monotonic() - began, 2)
        ds.gone_if_dead(ses, began, seconds, "the debugger to stop")
        time.sleep(POLL_PAUSE_S)
    raise Invalid("not_settled",
        f"the debugger channel accepted BREAK and `RUNSTATE` did not say stopped within "
        f"{seconds} s: the guest may still be running. Asking `stop` again is allowed; if it "
        f"fails as well, `close` then `start`")


def no_run_state(what: str) -> Invalid:
    """A tool that waits for, or reads, a stop this build cannot see."""
    return dbg.missing(dbg.RUNSTATE, f"{what} waits for the machine to stop, which")


def unknown_after_release(what: str) -> Invalid:
    """A reading of a machine released on a build that cannot say whether it stopped since."""
    return Invalid("no_channel",
        f"the machine was let run, and this build's debugger has no `{dbg.RUNSTATE}` command to "
        f"say whether it has stopped since ({dbg.COMMANDS_SECTION}), so {what} could read a moving "
        f"machine. `stop` brings it back to the debugger, wherever it is")


def read_run_state(session: ds.Session, *, unless_silent: bool = False) -> bool:
    """One `RUNSTATE`: whether the machine is stopped, with the cycles and the clock it gives;
    `unless_silent` sends nothing on a channel whose last request went unanswered."""
    return take_run_state(session, *dbg.exec_lines(session, dbg.RUNSTATE,
                                                   unless_silent=unless_silent))


def _fired_entry(session: ds.Session, number: str | None) -> str | None:
    """The text of the `BPIF` row `RUNSTATE` numbered, read now: a row's number shifts when
    another row goes in or out, its text does not."""
    if number is None:
        return None
    return next((b["entry"] for b in session.breakpoints()
                 if int(b["index"], 16) == int(number, 16)), None)


def take_run_state(session: ds.Session, ok: bool, lines: list[str]) -> bool:
    """`RUNSTATE`'s answer read into the session: stopped, its cycles and its clock."""
    found = dbg.RUNSTATE_LINE.match(lines[-1]) if ok and lines else None
    if found is None:
        raise Invalid("unexpected_answer",
            f"`{dbg.RUNSTATE}` answered {' / '.join(lines) or 'nothing'}, not its one line "
            f"`DEBUG: RUNSTATE stopped|running cycles=<n> ms=<t> frames=<n> [bpif=<n>]`")
    session.cycles, session.clock_ms = int(found.group(2)), float(found.group(3))
    session.frames = None if found.group(4) is None else int(found.group(4))
    if found.group(1) == "stopped":
        session.fired_entry = _fired_entry(session, found.group(5))
        session.mark_stopped()
        return True
    session.fired_entry = None
    session.forget_stop()
    return False


def frame_at_stop(session: ds.Session) -> int | dict[str, Any]:
    """The display frame a stopped machine is in, asked of `RUNSTATE`, or why there is none."""
    return frame_now(session)


def frame_now(session: ds.Session, *, unless_silent: bool = False) -> int | dict[str, Any]:
    """The display frame the machine is in, running or stopped, asked of `RUNSTATE`, which
    answers while the guest runs and does not stop it; or why there is none. `unless_silent`
    sends nothing on a channel whose last request went unanswered."""
    if not session.has(dbg.RUNSTATE):
        return contract.unavailable(f"this build's debugger has no `{dbg.RUNSTATE}`")
    take_run_state(session, *dbg.exec_lines(session, dbg.RUNSTATE, unless_silent=unless_silent))
    return contract.or_unavailable(session.frames, dbg.NO_FRAMES_WHY)


def await_stop(session: ds.Session, began: float, deadline: float, target: str,
               progress: Progress = no_progress, label: str = "",
               look_once: bool = False) -> tuple[bool, float]:
    """Ask `RUNSTATE` until the machine stops or `deadline` passes: `(expired, seconds)`;
    `look_once` asks at least once, a bound of 0 included."""
    if not session.has(dbg.RUNSTATE):
        raise no_run_state(label or f"run_to {target}")
    next_tick = began + PROGRESS_EVERY_S
    looked = not look_once
    while not looked or time.monotonic() < deadline:
        now = time.monotonic()
        cancel.check()
        if now >= next_tick:
            next_tick = now + PROGRESS_EVERY_S
            progress(now - began, None, f"{label or f'run_to {target}'}: running "
                                        f"{now - began:.0f}s of {deadline - began:g}s")
        session.gone_if_dead(began, deadline - began, target)
        looked = True
        if read_run_state(session):
            return False, round(time.monotonic() - began, 1)
        time.sleep(POLL_PAUSE_S)
    return True, 0.0
