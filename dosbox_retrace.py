"""`run_for` and `screen_wait`: the machine advanced by display retraces.

A frame is one vertical retrace, the debugger's `VRT` (run, then stop at the next retrace), sent
as a release and heard by the prompt the way `run_to` hears its stop. The register pane's own
clock (`pfi=`, emulated milliseconds) says how far the machine went. A `VRT` that a breakpoint
stops first stays armed in the debugger, so `STATE.retrace_pending` follows it frame by frame and
the first stop a later release makes is named for it (`dosbox_arming.attribute_stop`).
"""
from __future__ import annotations

import time
from typing import Any

from scry_core import cancel
from scry_core import progress as mprogress

import dosbox_arming as arming
import dosbox_running as running
import dosbox_screen as screen
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

CYCLES_WHY = ("the pane's `cc=` counts cycles only on the normal core, and which core runs is not "
              "something this server can read, so no count is given")
PENDING_NOTE = "a retrace stop is still armed: the next release stops at the next retrace"
UNCUT_NOTE = ("a code breakpoint is declared, and on a dynamic core one can fail to cut a frame: "
              "`ELAPSED` does not prove its address was not reached; `run_to` and `resume` "
              "honour it")
UNTOLD_NOTE = ("a change-watch or an interrupt breakpoint is declared, and its stop cannot be told "
               "from a retrace, so it is taken for one")
#: The pane prints `pfi=` to this many decimals: a difference is compared at that resolution, so
#: a clock that lands exactly on the mark is not a float's rounding short of it.
PANE_CLOCK_DECIMALS = 9


def run_for(session: ds.Session, frames: int, milliseconds: int, seconds: float,
            progress: ds.Progress, e9: str, e9_filter: str,
            e9_stamp: str | None) -> dict[str, Any]:
    """`frames` retraces, or as many as cover `milliseconds` of the pane's clock, within
    `seconds`, as the reply `run_for` publishes. The bound starts once the opening survey has
    read the clock, so a short one still reaches the first frame. By milliseconds every frame
    is surveyed, because its clock is what says whether to go on."""
    session.where_and_registers()
    before = session.pane_clock_ms
    if milliseconds and before is None:
        raise ds.Invalid("unexpected_answer",
            "the pane painted no `pfi=` on the survey before the first frame, so there is no "
            "clock to count milliseconds from; nothing was run")
    timed = milliseconds > 0
    began = time.monotonic()
    deadline = began + seconds
    # THE LINE IS THE RUN'S, frames or emulated milliseconds done of those asked; each retrace's
    # own wait reports nothing and still polls for the call's cancellation.
    clock = mprogress.Ticker(seconds, progress)
    asked = f"{milliseconds} ms" if timed else f"{frames} frame{'s' * (frames != 1)}"
    cuttable = arming.declares_code_breakpoint()
    polls = 0
    verdict = "ELAPSED"
    last = before                             # the clock at the last stop that painted one
    stalled_at: float | None = None
    while not (frames and polls >= frames):
        clock.expired()                       # the call's cancellation, and the line's clock
        if time.monotonic() >= deadline:
            verdict = "TIMEOUT"
            break
        if _advance(session, began, deadline, ds.no_progress):
            return st.reply(verdict="TIMEOUT", running=True, polls=polls,
                            **_clock(before, None), **_counts(), retrace_pending=True,
                            note=f"the bound expired with a `VRT` out, so the machine is still "
                                 f"running; {PENDING_NOTE}",
                            waited_s=round(time.monotonic() - began, 1))
        polls += 1
        if frames:
            clock.report(polls, frames, "run_for {asked}: frame {done} of {frames}, "
                         "{elapsed:.0f}s of {bound:g}s", asked=asked, done=polls, frames=frames,
                         bound=seconds)
        if not (timed or (cuttable and polls < frames)):
            continue                          # the stop reply surveys the last frame
        try:
            where, registers = session.where_and_registers()
        except ds.Invalid:
            continue                          # a cut repaint: the next frame's survey reads it
        if cuttable and _cut(session, where, registers) is not None:
            verdict = "OTHER_STOP"
            break
        now = session.pane_clock_ms
        if not timed or now is None or last is None or before is None:
            continue                          # no clock on this repaint: read at the next
        if now <= last:
            stalled_at = now
            break
        last = now
        clock.report(now - before, milliseconds, "run_for {asked}: {done:.0f} ms of {asked} "
                     "emulated, {elapsed:.0f}s of {bound:g}s", asked=asked, done=now - before,
                     bound=seconds)
        if round(now - before, PANE_CLOCK_DECIMALS) >= milliseconds:
            break
    fields: dict[str, Any] = {"verdict": verdict, "polls": polls, "running": False}
    try:
        reply = running.stop_reply(session, e9, e9_filter, e9_stamp, **fields)
        stopped_at: dict[str, str] | None = dict(STATE.last_stop["where"])
    except ds.Invalid as exc:                 # a cut pane: the account stands without the stop
        reply = st.reply(enrichment={"available": False, "why": str(exc)}, **fields)
        stopped_at = None
    if verdict == "ELAPSED" and (reply.get("attribution") or {}).get("attributed"):
        STATE.retrace_pending = True          # the last frame, cut: named by its own survey
        verdict = "OTHER_STOP"
    after = session.pane_clock_ms if stopped_at else (last if timed else None)
    extra: dict[str, Any] = {**_clock(before, after), **_counts(), "stopped_at": stopped_at,
                             "waited_s": round(time.monotonic() - began, 1)}
    unread = before is None or (stopped_at is not None and after is None)
    notes = [note for note, holds in ((PENDING_NOTE, verdict == "OTHER_STOP"),
                                      (UNCUT_NOTE, cuttable),
                                      (UNTOLD_NOTE, arming.declares_untold_stopper()),
                                      ("the pane painted no `pfi=`, so the clock is null", unread))
             if holds]
    if verdict == "OTHER_STOP":
        extra["retrace_pending"] = True
    if notes:
        extra["note"] = "; ".join(notes)
    if stalled_at is not None:
        stuck = (f"retrace stop {polls} left the pane's clock at {stalled_at} ms, where the stop "
                 f"before it had put it: the machine stopped advancing")
    elif polls and before is not None and after is not None and after <= before:
        stuck = (f"the pane's clock read {before} ms before and {after} ms after {polls} retrace "
                 f"stop(s): nothing was emulated")
    else:
        stuck = ""
    if stuck:
        kept = {k: v for k, v in reply.items() if k not in ("status", "verdict", "session")}
        return st.reply(status="INVALID", code="no_progress", message=stuck, **kept, **extra)
    return st.extend(reply, verdict=verdict, **extra)


def _advance(session: ds.Session, began: float, deadline: float, tick: ds.Progress) -> bool:
    """One retrace, the step both waits take each frame: `VRT` released and its stop heard by the
    prompt. True when the bound expired with it out: the debugger still holds it, and the next
    release meets it (`STATE.retrace_pending`); a stop that answered it spends any earlier one."""
    try:
        expired, _ = session.retrace(began, deadline, tick)
    except BaseException as e:
        # A CANCELLED WAIT leaves its `VRT` out, as an expired one does, unless its stop was
        # already heard: the next release meets it.
        if cancel.is_cancellation(e):
            STATE.retrace_pending = not _heard(session)
        raise
    STATE.retrace_pending = expired
    return expired


def _cut(session: ds.Session, where: dict[str, str] | None = None,
         registers: dict[str, str] | None = None) -> dict[str, Any] | None:
    """The attribution when a declared code breakpoint made this stop rather than the retrace,
    whose `VRT` then stays armed; None for a retrace, or a repaint too cut to place. Surveys the
    stop unless the caller already has."""
    if where is None or registers is None:
        try:
            where, registers = session.where_and_registers()
        except ds.Invalid:
            return None
    attribution = arming.attribute_stop(session, where=where, machine=(where["mode"], registers))
    if not attribution["attributed"]:
        return None
    STATE.retrace_pending = True
    return attribution


def _clock(before: float | None, after: float | None) -> dict[str, Any]:
    """The pane's emulated milliseconds as seconds; null where no survey painted `pfi=`."""
    return {"emulated_before_s": None if before is None else before / 1000,
            "emulated_after_s": None if after is None else after / 1000}


def _counts() -> dict[str, Any]:
    return {"frame_before": None, "frame_after": None, "cycles": None, "cycles_why": CYCLES_WHY}


def screen_wait(session: ds.Session, text: str, seconds: float,
                progress: ds.Progress) -> dict[str, Any]:
    """Retrace by retrace until `text` is inside one row of the text screen. `seconds` counts
    from once the opening read has looked at the screen, so a short bound still reaches the
    first frame, and is read before each retrace, so a frame's read and the stop reply under
    way when it passes are finished. Already there: answered at once, the machine not moved.
    Found: the stop reply, the find kept when its survey comes back cut. A frame in a mode that
    is not text is examined as no match. A declared code breakpoint that cuts a frame ends the
    wait `wait_stopped`; the bound, `wait_expired` (`_expired`); a frame laid out in a way the
    reader refuses, that `no_channel`. Each that ends at a stop of its own records it, as every
    stop tool does."""
    watch = screen.TextWatch(session)
    rows = watch.rows()
    examined, not_text = 1, int(rows is None)
    hit = None if rows is None else screen.find_text(rows, text)
    if hit is not None:
        return st.reply(already=True, waited_s=0.0, polls=0, point=hit[0], line=hit[1])
    last = rows
    began = time.monotonic()
    deadline = began + seconds
    clock = mprogress.Ticker(seconds, progress)
    cuttable = arming.declares_code_breakpoint()
    polls = 0
    while hit is None:
        seen = {} if last is None else {"text": last}
        clock.expired()                       # the call's cancellation, and the line's clock
        if time.monotonic() >= deadline:
            raise _expired(session, text, seconds, polls, f"{not_text} of {examined}", seen,
                           out=False)
        if _advance(session, began, deadline, ds.no_progress):
            raise _expired(session, text, seconds, polls, f"{not_text} of {examined}", seen,
                           out=True)
        polls += 1
        cut = _cut(session) if cuttable else None
        if cut is not None:
            raise ds.Invalid("wait_stopped",
                f"a declared breakpoint stopped the machine before retrace {polls}, so the "
                f"wait for `{text}` cannot go on; {PENDING_NOTE}",
                polls=polls, attribution=cut, **_ended_at(session), retrace_pending=True,
                **seen)
        try:
            rows = watch.rows()
        except ds.Invalid as e:
            # A screen laid out in a way this does not read is a verdict on a console that
            # answered; any other refusal is about the console itself, which is not asked more.
            if e.code != "no_channel":
                raise
            raise ds.Invalid(e.code, f"{e}; the wait had stopped the machine at retrace {polls}",
                             **{**e.fields, "polls": polls, **_ended_at(session)}) from None
        examined += 1
        clock.tick("screen_wait {text!r}: retrace {polls}, {mode}, {elapsed:.0f}s of {bound:g}s",
                   text=text, polls=polls, mode="a text mode" if rows is not None else
                   "not a text mode", bound=seconds)
        if rows is None:
            not_text += 1
            continue
        last = rows
        hit = screen.find_text(rows, text)
    found: dict[str, Any] = {"already": False, "waited_s": round(time.monotonic() - began, 1),
                             "polls": polls, "point": hit[0], "line": hit[1]}
    if arming.declares_untold_stopper():
        found["note"] = UNTOLD_NOTE
    return _stop_reply(session, found)


def _stop_reply(session: ds.Session, base: dict[str, Any]) -> dict[str, Any]:
    """The stop reply with `base` in it; a survey that comes back cut keeps `base`, its
    enrichment marked unavailable, and records no stop."""
    return running.stop_or_base(session, True, "none", ".", None, base)


#: What a refused wait carries of the stop reply that recorded its stop: the stop's number, or
#: the enrichment marked unavailable when its survey came back cut, and the accounts that reply
#: delivered (a stop the guest reached on its own, declarations applied on it), which would
#: otherwise be spent on a reply nobody sees.
ENDED_KEYS = ("stop_seq", "enrichment", "stopped_on_its_own", "applied_on_stop")


def _heard(session: ds.Session) -> bool:
    """Whether the guest is at the debugger, read under the shield while a cancel unwinds; a
    terminal that cannot answer is taken as not heard, which leaves the retrace pending."""
    with cancel.shielded():
        try:
            return session.at_debugger()
        except (ds.Invalid, OSError):
            return False


def _ended_at(session: ds.Session) -> dict[str, Any]:
    """The stop a refused wait ends at, recorded by the stop reply, as the fields of
    `ENDED_KEYS` the refusal carries."""
    stop = _stop_reply(session, {})
    return {key: stop[key] for key in ENDED_KEYS if key in stop}


def _expired(session: ds.Session, text: str, seconds: float, polls: int, not_text: str,
             seen: dict[str, Any], *, out: bool) -> ds.Invalid:
    """`screen_wait`'s bound, as the refusal it raises. With a `VRT` still `out` the machine runs
    and nothing can be read. Stopped at a retrace of its own, that stop is recorded so the next
    call does not take it for one the guest reached on its own; stopped before any, nothing was
    typed, and the record and a pending retrace stay as they were."""
    fields: dict[str, Any] = {"polls": polls, **seen, "running": out}
    if polls and not out:
        fields.update(_ended_at(session))
    fields["retrace_pending"] = STATE.retrace_pending
    skipped = "" if not_text.startswith("0 ") else (
        f"; {not_text} frames examined were not in a text mode")
    return ds.Invalid("wait_expired",
        f"`{text}` was not on the text screen in {polls} retrace(s) within {seconds:g} s{skipped}"
        + (f"; {PENDING_NOTE}, so the machine is still running" if out else ""), **fields)
