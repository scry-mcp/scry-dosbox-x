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
from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_machine as machine
import dosbox_running as running
import dosbox_screen as screen
import dosbox_session as ds
import dosbox_state as st
import dosbox_vga as vga
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
    # THE LINE IS THE RUN'S, frames or emulated milliseconds done of those asked. A retrace's own
    # wait reports only when that retrace is slow to come, on wall time, through the same line,
    # so a frame that never comes still says the run is alive; it polls for the cancel either way.
    clock = mprogress.Ticker(seconds, progress)
    asked = f"{milliseconds} ms" if timed else f"{frames} frame{'s' * (frames != 1)}"
    polls = 0

    def report_slow_retrace(_elapsed: float, _total: float | None, _message: str) -> None:
        clock.expired()                       # the run's clock read now, not at the frame's start
        done = "" if timed else f"frame {polls} of {frames}, "
        clock.tick("run_for {asked}: {done}waiting for its retrace, {elapsed:.0f}s of {bound:g}s",
                   asked=asked, done=done, bound=seconds)

    cuttable = arming.declares_code_breakpoint()
    verdict = contract.ELAPSED
    last = before                             # the clock at the last stop that painted one
    stalled_at: float | None = None
    while not (frames and polls >= frames):
        clock.expired()                       # the call's cancellation, and the line's clock
        if time.monotonic() >= deadline:
            verdict = contract.TIMEOUT
            break
        if _advance(session, began, deadline, report_slow_retrace):
            # THE BOUND INTERRUPTS: a `VRT` still out leaves the machine running, so it is
            # brought back where it stands and surveyed there, as every bounded run hands the
            # machine back stopped. The `VRT` stays armed, and the next release meets it. A stop
            # that landed before the interrupt looked is the retrace's, which spends it, unless a
            # declared breakpoint made it (`_cut`), which ends the run as inside the loop.
            STATE.retrace_pending = ds.Session.stop_at_bound(session)
            verdict = contract.TIMEOUT
            if not STATE.retrace_pending and cuttable and _cut(session) is not None:
                verdict = contract.OTHER_STOP
            break
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
            verdict = contract.OTHER_STOP
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
    fields: dict[str, Any] = {"verdict": verdict, "polls": polls}
    try:
        reply = running.stop_reply(session, e9, e9_filter, e9_stamp,
                                   e9_how=running.E9_BY_ARGUMENT, **fields)
        stopped_at: dict[str, str] | None = dict(STATE.last_stop["where"])
    except ds.Invalid as exc:                 # a cut pane: the account stands without the stop
        reply = st.reply(enrichment={"available": False, "why": str(exc)}, **fields)
        stopped_at = None
    if verdict == contract.ELAPSED and (reply.get("attribution") or {}).get("attributed"):
        STATE.retrace_pending = True          # the last frame, cut: named by its own survey
        verdict = contract.OTHER_STOP
    after = session.pane_clock_ms if stopped_at else (last if timed else None)
    extra: dict[str, Any] = {**_clock(before, after), **_counts(),
                             # A cut survey's reply has no position of its own to carry.
                             **({} if stopped_at else running.position(None, None)),
                             "waited_s": round(time.monotonic() - began, 1)}
    pending = STATE.retrace_pending           # every cut and every interrupt leaves it armed
    notes = [note for note, holds in ((PENDING_NOTE, pending),
                                      (UNCUT_NOTE, cuttable),
                                      (UNTOLD_NOTE, arming.declares_untold_stopper()))
             if holds]
    if pending:
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


#: Why a clock reading is not there, and why a DOS machine has no frame reading at all.
NO_CLOCK_WHY = "the pane painted no `pfi=` on that survey"
NO_FRAME_WHY = ("a DOS machine keeps no frame counter a server could read: `polls` counts the "
                "retraces")


def _clock(before: float | None, after: float | None) -> dict[str, Any]:
    """The pane's emulated milliseconds as seconds, unavailable where no survey painted
    `pfi=`."""
    return {"emulated_before_s": contract.or_unavailable(
                None if before is None else before / 1000, NO_CLOCK_WHY),
            "emulated_after_s": contract.or_unavailable(
                None if after is None else after / 1000, NO_CLOCK_WHY)}


def _counts() -> dict[str, Any]:
    return {"frame_before": contract.unavailable(NO_FRAME_WHY),
            "frame_after": contract.unavailable(NO_FRAME_WHY),
            "cycles": contract.unavailable(CYCLES_WHY)}


def screen_wait(session: ds.Session, text: str, seconds: float,
                progress: ds.Progress) -> dict[str, Any]:
    """Retrace by retrace until `text` is inside one row of the text screen. `seconds` counts
    from once the opening read has looked at the screen, so a short bound still reaches the
    first frame, and is read before each retrace, so a frame's read and the stop reply under
    way when it passes are finished. Already there: answered at once, the machine not moved.
    Found: the stop reply, the find kept when its survey comes back cut. A frame in a mode that
    is not text is examined as no match. A declared code breakpoint that cuts a frame ends the
    wait `wait_stopped`; the bound, a `TIMEOUT` at a stop (`_expired`); a frame laid out in a way
    the reader refuses, that `no_channel`. Each that ends at a stop of its own records it, as every
    stop tool does."""
    watch = TextWatch(session)
    rows = watch.rows()
    examined, not_text = 1, int(rows is None)
    hit = None if rows is None else find_text(rows, text)
    if hit is not None:
        return st.reply(verdict=contract.TARGET, already=True, waited_s=0.0, polls=0,
                        point=hit[0], line=hit[1])
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
            return _expired(session, text, seconds, polls, f"{not_text} of {examined}", seen,
                            out=False, began=began)
        if _advance(session, began, deadline, ds.no_progress):
            return _expired(session, text, seconds, polls, f"{not_text} of {examined}", seen,
                            out=True, began=began, cuttable=cuttable)
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
        hit = find_text(rows, text)
    found: dict[str, Any] = {"verdict": contract.TARGET, "already": False,
                             "waited_s": round(time.monotonic() - began, 1),
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
             seen: dict[str, Any], *, out: bool, began: float,
             cuttable: bool = False) -> dict[str, Any]:
    """`screen_wait`'s bound, a `TIMEOUT` at a stop: with a `VRT` still `out` the machine is
    interrupted where it stands, and the retrace stays armed for the next release; stopped at a
    retrace of its own, that stop is surveyed. Stopped before any, nothing was typed and the
    reply carries no stop."""
    # A `VRT` typed and still out is interrupted; one whose stop landed first is spent, and
    # that stop is surveyed like any other, unless a declared breakpoint made it: then the wait
    # ends as a cut inside it does.
    pending = out and ds.Session.stop_at_bound(session)
    if out and not pending and cuttable and (cut := _cut(session)) is not None:
        raise ds.Invalid("wait_stopped",
            f"a declared breakpoint stopped the machine as the {seconds:g} s bound ran out, so "
            f"the wait for `{text}` ends there; {PENDING_NOTE}",
            polls=polls, attribution=cut, **_ended_at(session), retrace_pending=True, **seen)
    if out:
        STATE.retrace_pending = pending
    skipped = "" if not_text.startswith("0 ") else (
        f"; {not_text} frames examined were not in a text mode")
    base: dict[str, Any] = {
        "verdict": contract.TIMEOUT, "polls": polls, **seen,
        "retrace_pending": STATE.retrace_pending,
        "waited_s": round(time.monotonic() - began, 1),
        "note": f"`{text}` was not on the text screen in {polls} retrace(s) within "
                f"{seconds:g} s{skipped}" + (f"; {PENDING_NOTE}" if pending else "")}
    if not (polls or out):
        return st.reply(**base)
    return _stop_reply(session, base)


class TextWatch:
    """The text screen read stop after stop, at the cost a wait can pay each frame: `VGA MODE`
    (the mode word and the display start), `VGA DRAW` (the size the screen renders), `VGA GC`
    (where the page lies: the switch to the monochrome mode moves it to B0000 and leaves the
    other two as they were), `CPU` (how it is reached), and one dump. `VGA CRTC` is read once,
    as it places only the cursor, which a wait does not return; the descriptor tables are
    re-read only when the cpu mode, or whether a virtual-8086 task runs, changes: a guest can
    enter protected mode under an unchanged text screen."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self.crtc: dict[str, Any] | None = None
        self.cpu: tuple[str, bool] | None = None
        self.tables: vga.Tables | None = None

    def rows(self) -> list[str] | None:
        """The rows the text screen shows now, or None when the screen is not in a text mode."""
        mode = vga.listed(self.session, vga.COMMAND_OF["mode"])
        if mode.get("mode") != "M_TEXT":
            return None
        draw, gc = (vga.listed(self.session, vga.COMMAND_OF[key]) for key in ("draw", "gc"))
        if self.crtc is None:
            self.crtc = vga.listed(self.session, vga.COMMAND_OF["crtc"])
        shape = vga.geometry({"mode": mode, "crtc": self.crtc, "gc": gc, "draw": draw})
        reading = machine.read(self.session, frozenset())
        cpu = (str(reading.mode), vga.in_v86(reading))
        if cpu != self.cpu or self.tables is None:
            self.cpu = cpu
            self.tables = vga.tables_from(reading) if reading.mode == "real" \
                else vga.read_tables(self.session)
        seg, off = vga.selector_for(shape.linear, shape.length, self.tables)
        page = vga.dump(self.session, seg, off, shape.length)
        return screen.text_rows(page, shape.width, shape.height)


def find_text(rows: list[str], text: str) -> tuple[list[int], str] | None:
    """Where `text` first appears inside one row: `[column, row]` and that row."""
    for r, row in enumerate(rows):
        c = row.find(text)
        if c >= 0:
            return [c, r], row
    return None
