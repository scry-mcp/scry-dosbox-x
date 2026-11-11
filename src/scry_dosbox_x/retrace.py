"""`run_for` and `screen_wait`: the machine advanced by display retraces (the debugger's `VRT`).

A `VRT` that a breakpoint stops first stays armed in the debugger, so `STATE.retrace_pending`
follows it and the first stop a later release makes is named for it.
"""
from __future__ import annotations

import time
from typing import Any

from scry_core import cancel, stop_wait
from scry_core import progress as mprogress
from scry_core import reply_contract as contract
from scry_core.prose import counted

from scry_dosbox_x import arming, at_stop, machine, running, screen, vga
from scry_dosbox_x import dac as vgadac
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import run_state as rs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

COUNTED_CORE = "normal"
PENDING_NOTE = "a retrace stop is still armed: the next release stops at the next retrace"
UNCUT_NOTE = ("a code breakpoint is declared, and on a dynamic core one can fail to cut a frame: "
              "`ELAPSED` does not prove its address was not reached; `run_to` and `resume` "
              "honour it")
UNTOLD_NOTE = ("a change-watch or an interrupt breakpoint is declared, and its stop cannot be told "
               "from a retrace, so it is taken for one")
#: `RUNSTATE` prints its clock to this many decimals; compare at that resolution, not at float
#: noise.
CLOCK_DECIMALS = 9


def cycles_why(core: str) -> str:
    """Why a run on `core` gives no cycle count."""
    return (f"{dbg.NORMAL_CORE_CYCLES}, and this session started on the {core} core: "
            f"start on `flags=[\"-set\", \"cpu core={COUNTED_CORE}\"]` for a count")


def _cycles(session: ds.Session, before: int | None) -> Any:
    """The run's cycles, counted only on a session that started on the normal core, whose
    `RUNSTATE` cycle count then means what it says."""
    core = session.launch.core
    if core != COUNTED_CORE:
        return contract.unavailable(cycles_why(core))
    if before is None or session.cycles is None:
        return contract.unavailable("`RUNSTATE` gave no cycle count at one end of the run")
    if session.cycles < before:
        return contract.unavailable("the cycle counter wrapped during the run, so there is no "
                                    "count")
    return session.cycles - before


def run_for(session: ds.Session, frames: int, milliseconds: int, seconds: float,
            progress: ds.Progress, who: str = "run_for") -> dict[str, Any]:
    """`frames` retraces, or as many as cover `milliseconds` of emulated time, within `seconds`.

    The bound starts once the opening read has taken the clock, so a short one still reaches the
    first frame. `who` names the run in the cause of a stop it made itself.
    """
    session.require_run_state("run_for")
    session.where_and_registers()
    rs.read_run_state(session)
    before = session.clock_ms
    cycles_before = session.cycles
    first_frame = session.frames
    if milliseconds and before is None:
        raise ds.Invalid("unexpected_answer",
            "`RUNSTATE` gave no clock before the first frame, so there is no clock to count "
            "milliseconds from; nothing was run")
    timed = milliseconds > 0
    began = time.monotonic()
    deadline = began + seconds
    # A retrace's own wait reports through the same line, so a frame that never comes still
    # says the run is alive.
    clock = mprogress.Ticker(seconds, progress)
    asked = f"{milliseconds} ms" if timed else f"{frames} frame{'s' * (frames != 1)}"
    polls = 0

    def report_slow_retrace(_elapsed: float, _total: float | None, _message: str) -> None:
        clock.expired()
        done = "" if timed else f"frame {polls} of {frames}, "
        clock.tick("run_for {asked}: {done}waiting for its retrace, {elapsed:.0f}s of {bound:g}s",
                   asked=asked, done=done, bound=seconds)

    cuttable = arming.declares_code_breakpoint()
    alone = not arming.something_can_stop_it()
    verdict = contract.ELAPSED
    last = before
    stalled_at: float | None = None
    frame_at_release: int | None = None
    while not (frames and polls >= frames):
        clock.expired()
        if time.monotonic() >= deadline:
            verdict = contract.TIMEOUT
            break
        frame_at_release = session.frames
        if _advance(session, began, deadline, report_slow_retrace):
            # A `VRT` still out leaves the machine running: stop it where it stands. A stop that
            # landed before the interrupt is the retrace's and spends it, unless a declared
            # breakpoint made it.
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
        # The clock comes with the stop's `RUNSTATE`; only a frame something declared can cut
        # is surveyed, to tell its stop from a retrace.
        if cuttable and (timed or polls < frames):
            try:
                where, registers, held = session.stop_survey()
            except ds.Invalid:
                continue                      # a reading the stop could not give
            if _cut(session, (where, registers, held)) is not None:
                verdict = contract.OTHER_STOP
                break
        now = session.clock_ms
        if not timed or now is None or last is None or before is None:
            continue
        if now <= last:
            stalled_at = now
            break
        last = now
        clock.report(now - before, milliseconds, "run_for {asked}: {done:.0f} ms of {asked} "
                     "emulated, {elapsed:.0f}s of {bound:g}s", asked=asked, done=now - before,
                     bound=seconds)
        if round(now - before, CLOCK_DECIMALS) >= milliseconds:
            break
    fields: dict[str, Any] = {"verdict": verdict, "polls": polls}
    # Only a frame that moved proves a retrace: an INT 3 the conf breaks on, or a row typed
    # through `debug`, stops it too and is nothing declared.
    crossed = (session.frames is not None and frame_at_release is not None
               and session.frames > frame_at_release)
    own = "" if not alone else (
        (f"the retrace {who} ran to" if crossed else "")
        if verdict == contract.ELAPSED
        else f"{who}'s {seconds:g} s bound ran out where the machine stood")
    try:
        reply = running.stop_reply(session, own=own, **fields)
        stopped_at: dict[str, str] | None = dict(STATE.last_stop["where"])
    except ds.Invalid as exc:
        reply = st.reply(**running.unavailable_enrichment(exc), **fields)
        stopped_at = None
    if verdict == contract.ELAPSED and STATE.last_stop.get("attribution", {}).get("attributed") \
            and stopped_at is not None:
        STATE.retrace_pending = True
        verdict = contract.OTHER_STOP
    after = session.clock_ms if stopped_at else (last if timed else None)
    extra: dict[str, Any] = {**_clock(before, after),
                             **_counts(first_frame, reply.get("frame") if stopped_at else None,
                                      _cycles(session, cycles_before)),
                             **({} if stopped_at else running.position(None, None))}
    pending = STATE.retrace_pending
    notes = [note for note, holds in ((PENDING_NOTE, pending),
                                      (UNCUT_NOTE, cuttable),
                                      (UNTOLD_NOTE, arming.declares_untold_stopper()))
             if holds]
    if pending:
        extra["retrace_pending"] = True
    if notes:
        extra["note"] = "; ".join(notes)
    if stalled_at is not None:
        stuck = (f"retrace stop {polls} left the emulated clock at {stalled_at} ms, where the stop "
                 f"before it had put it: the machine stopped advancing")
    elif polls and before is not None and after is not None and after <= before:
        stuck = (f"the emulated clock read {before} ms before and {after} ms after "
                 f"{counted(polls, 'retrace stop')}: nothing was emulated")
    else:
        stuck = ""
    if stuck:
        kept = {k: v for k, v in reply.items() if k not in ("status", "verdict", "session")}
        return st.reply(status="INVALID", code="no_progress", message=stuck, **kept, **extra)
    return st.extend(reply, verdict=verdict, **extra)


def _advance(session: ds.Session, began: float, deadline: float, tick: ds.Progress) -> bool:
    """One retrace. True when the bound expired with the `VRT` still out."""
    try:
        expired, _ = session.retrace(began, deadline, tick)
    except BaseException as e:
        # A cancelled wait leaves its `VRT` out unless its stop was already heard.
        if cancel.is_cancellation(e):
            STATE.retrace_pending = not _heard(session)
        raise
    STATE.retrace_pending = expired
    return expired


def _cut(session: ds.Session,
         survey: tuple[dict[str, str], dict[str, str], list[dict[str, str]]] | None = None,
         ) -> dict[str, Any] | None:
    """The attribution when a declared code breakpoint made this stop, leaving the `VRT` armed;
    None for a retrace or a stop that could not be read."""
    if survey is None:
        try:
            survey = session.stop_survey()
        except ds.Invalid:
            return None
    where, registers, held = survey
    attribution = arming.attribute_stop(session, where=where, machine=(where["mode"], registers),
                                        held=held)
    if not attribution["attributed"]:
        return None
    STATE.retrace_pending = True
    return attribution


NO_CLOCK_WHY = "`RUNSTATE` gave no clock at that stop"
NO_STOP_FRAME_WHY = "the run ended at no stop the server could read"


def _clock(before: float | None, after: float | None) -> dict[str, Any]:
    """`RUNSTATE`'s emulated milliseconds as seconds."""
    return {"emulated_before_s": contract.or_unavailable(
                None if before is None else before / 1000, NO_CLOCK_WHY),
            "emulated_after_s": contract.or_unavailable(
                None if after is None else after / 1000, NO_CLOCK_WHY)}


def _counts(before: int | None, after: Any, cycles: Any) -> dict[str, Any]:
    """The frames the run began and ended in, as each stop reply's `frame` reads them."""
    return {"frame_before": contract.or_unavailable(before, dbg.NO_FRAMES_WHY),
            "frame_after": after if after is not None
            else contract.unavailable(NO_STOP_FRAME_WHY),
            "cycles": cycles}


#: The least a retrace is given when a bound is all but spent.
MIN_STEP_S = 0.001


class Watched:
    """One of `screen_wait`'s predicates: what a poll reads, and what a hit answers.

    Cheap predicates only: the cost of a poll is the read, and `every` is the caller's lever.
    """

    name: str
    said: str
    examined: int = 1

    def hit(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def state(self) -> dict[str, Any]:
        """What the reply carries of the last frame examined, on a timeout as on a hit."""
        return {}

    def why(self) -> str:
        """What a timeout adds about what it examined, after the count of retraces."""
        return ""


class TextWatched(Watched):
    name = "text"

    def __init__(self, session: ds.Session, text: str) -> None:
        self.watch = TextWatch(session)
        self.text = text
        self.said = f"`{text}`"
        self.examined = 1
        self.not_text = 0
        self.last: list[str] | None = None

    def hit(self) -> dict[str, Any] | None:
        rows = self.watch.rows()
        if rows is None:
            self.not_text += 1
            return None
        self.last = rows
        found = find_text(rows, self.text)
        return None if found is None else {"point": found[0], "line": found[1]}

    def state(self) -> dict[str, Any]:
        return {} if self.last is None else {"text": self.last}

    def why(self) -> str:
        return ("" if not self.not_text else
                f"; {self.not_text} of {self.examined} frames examined were not in a text mode")


class ScreenWatched(Watched):
    name = "screen"

    def __init__(self, session: ds.Session, screen: str) -> None:
        self.session = session
        self.screen = screen
        self.said = f"screen {screen!r}"
        STATE.maps.check_known(screen)      # an unmapped name is refused before a frame runs

    def hit(self) -> dict[str, Any] | None:
        # Imported here: `folds` reaches `checks`, and `checks` reaches this module through
        # `inputs`, so the top of this file cannot hold it.
        from scry_dosbox_x import folds as dosbox_folds

        try:
            shown = STATE.maps.find(dosbox_folds.map_read(self.session), None)
        except ds.Invalid as e:
            # A frame with no video mode yet is no match, like a non-text frame to a text wait.
            if e.code != "no_channel":
                raise
            return None
        if shown.get("matched") and shown["screen"] == self.screen:
            return {"screen": {"name": shown["screen"], "layer": shown["layer"]}}
        return None

    def state(self) -> dict[str, Any]:
        return {}

    def why(self) -> str:
        found = STATE.maps.found
        return "" if found is not None else "; no mapped screen matched the frames examined"


class ChangedWatched(Watched):
    """A screen the map names other than the one it named at the call's start
    (`scry_core.stop_wait.Changed`)."""

    name = "changed"
    said = "a changed screen"

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self.judge = stop_wait.Changed(self._found())

    def _found(self) -> dict[str, Any]:
        # Imported here for the reason `ScreenWatched.hit` gives.
        from scry_dosbox_x import folds as dosbox_folds

        try:
            return STATE.maps.find(dosbox_folds.map_read(self.session), None)
        except ds.Invalid as e:
            # A frame with no video mode yet names no screen: a transition, as for `screen`.
            if e.code != "no_channel":
                raise
            return {"matched": False, "screens_tried": 0, "screens_unjudged": 0}

    def hit(self) -> dict[str, Any] | None:
        found = self._found()
        if not self.judge.judge(found):
            return None
        return {"screen": {"name": found["screen"], "layer": found["layer"]},
                "started_on": self.judge.started_on or contract.unavailable(
                    "the map named no screen when the wait began")}


class PaletteWatched(Watched):
    name = "palette"

    def __init__(self, session: ds.Session, palette: str) -> None:
        self.session = session
        self.palette = palette
        self.said = f"a {palette} palette"

    def hit(self) -> dict[str, Any] | None:
        _, entries = vgadac.read_dac(self.session)
        if all(entry == "000000" for entry in entries):
            return {"palette": self.palette, "entries": len(entries)}
        return None


def _watched(session: ds.Session, text: str, screen: str, palette: str,
             changed: bool = False) -> Watched:
    """The one predicate the caller named; none or several is refused before a frame runs."""
    named = [(name, value) for name, value in
             (("text", text), ("screen", screen), ("palette", palette), ("changed", changed))
             if value]
    if len(named) != 1:
        raise ds.Invalid("bad_argument",
                         "screen_wait runs on exactly one of `text`, `screen`, `palette` or "
                         f"`changed`; got {len(named)} of them. Each is a different read of the "
                         "screen, and a frame has the budget of one")
    name, value = named[0]
    if name == "changed":
        return ChangedWatched(session)
    value = str(value)
    if name == "text":
        return TextWatched(session, value)
    if name == "screen":
        return ScreenWatched(session, value)
    return PaletteWatched(session, value)


def screen_wait(session: ds.Session, text: str, screen: str, palette: str, every: int,
                seconds: float, progress: ds.Progress, on_breakpoint: str = "",
                on_watch: str = "", condition: str = "",
                changed: bool = False) -> dict[str, Any]:
    """Retrace by retrace until the one predicate holds.

    `text`: inside one row of the text screen. `screen`: the loaded screen map names the frame.
    `palette`: every DAC entry is black. `every`: 0 judges every retrace, N judges every Nth,
    which can pass over a screen that lasts fewer than N and is what the reply's `sampled_every`
    says. `seconds` counts from once the opening read has looked. Already there: answered at
    once, the machine not moved. A declared code breakpoint that cuts a frame ends the wait
    `wait_stopped`; the bound, a `TIMEOUT` (`_expired`).
    """
    session.require_run_state("screen_wait")
    spec = stop_wait.check(on_breakpoint, on_watch, every, condition)
    if spec is not None:
        at_stop.declared_row(spec)          # refused before the screen is read
    watched = _watched(session, text, screen, palette, changed)
    if spec is not None:
        return at_stop.screen_wait_at(
            session, spec, watched, seconds, progress, _advance, _cut, _stop_reply, _bound,
            _ended_at, "" if session.launch.core == COUNTED_CORE else UNCUT_NOTE)
    step = every or 1
    hit = watched.hit()
    if hit is not None:
        return st.reply(verdict=contract.TARGET, predicate=watched.name, already=True,
                        waited_s=0.0, polls=0, sampled_every=every, **watched.state(), **hit)
    began = time.monotonic()
    deadline = began + seconds
    clock = mprogress.Ticker(seconds, progress)
    cuttable = arming.declares_code_breakpoint()
    polls = 0
    while hit is None:
        clock.expired()
        if time.monotonic() >= deadline:
            return _expired(session, watched, every, seconds, polls, out=False, began=began)
        early = _advance_by(session, step, began, deadline, clock)
        if early is None:
            polls += step
        elif early.get("status") != "ok":
            return early
        else:
            return _expired(session, watched, every, seconds, polls, out=True, began=began,
                            cuttable=cuttable)
        if cuttable and (cut := _cut(session)) is not None:
            raise ds.Invalid("wait_stopped",
                f"a declared breakpoint stopped the machine before retrace {polls}, so the "
                f"wait for {watched.said} cannot go on; {PENDING_NOTE}",
                polls=polls, predicate=watched.name,
                **{**_ended_at(session), "cause": st.cause(cut)}, retrace_pending=True,
                **watched.state())
        try:
            hit = watched.hit()
        except ds.Invalid as e:
            # Any other refusal is about the debugger itself, which is not asked more.
            if e.code != "no_channel":
                raise
            raise ds.Invalid(e.code, f"{e}; the wait had stopped the machine at retrace {polls}",
                             **{**e.fields, "polls": polls, "predicate": watched.name,
                                **_ended_at(session)}) from None
        watched.examined += 1
        clock.tick("screen_wait {said}: retrace {polls}, {elapsed:.0f}s of {bound:g}s",
                   said=watched.said, polls=polls, bound=seconds)
    found: dict[str, Any] = {"verdict": contract.TARGET, "predicate": watched.name,
                             "already": False,
                             "waited_s": round(time.monotonic() - began, 1), "polls": polls,
                             "sampled_every": every, **watched.state(), **hit}
    if arming.declares_untold_stopper():
        found["note"] = UNTOLD_NOTE
    return _stop_reply(session, found)


def _bound(session: ds.Session, out: bool) -> bool:
    """Stop a run whose bound ran out with a `VRT` still `out`, as `_expired` does; whether a
    `VRT` is still armed after it."""
    if out:
        STATE.retrace_pending = ds.Session.stop_at_bound(session)
    return STATE.retrace_pending


def _advance_by(session: ds.Session, frames: int, began: float, deadline: float,
                tick: mprogress.Ticker) -> dict[str, Any] | None:
    """`frames` retraces; None when they all came, else the run's end (a `TIMEOUT` or a stop)."""
    if frames == 1:
        return {"verdict": contract.TIMEOUT, "status": "ok"} \
            if _advance(session, began, deadline, ds.no_progress) else None
    left = max(deadline - time.monotonic(), MIN_STEP_S)

    def said(progress: float, total: float | None, message: str) -> None:
        tick.tick("screen_wait {message}", message=message)

    out = run_for(session, frames, 0, left, said, who="a sampled screen wait")
    if out.get("status") == "ok" and out.get("verdict") == contract.ELAPSED:
        return None
    return out


def _stop_reply(session: ds.Session, base: dict[str, Any]) -> dict[str, Any]:
    """The stop reply with `base` in it; a cut survey keeps `base` and records no stop."""
    return running.stop_or_base(session, True, base)


#: What a refused wait carries of the stop reply that recorded its stop; otherwise those accounts
#: would be spent on a reply nobody sees.
ENDED_KEYS = ("stop_seq", "cause", "regpoint_hit", "enrichment", "symbols_placed",
              "stopped_on_its_own", "applied_on_stop")


def _heard(session: ds.Session) -> bool:
    """Whether the guest is at the debugger; a channel that cannot answer is not heard."""
    with cancel.shielded():
        try:
            return session.at_debugger()
        except (ds.Invalid, OSError):
            return False


def _ended_at(session: ds.Session) -> dict[str, Any]:
    """The stop a refused wait ends at, as the `ENDED_KEYS` fields."""
    stop = _stop_reply(session, {})
    return {key: stop[key] for key in ENDED_KEYS if key in stop}


def _expired(session: ds.Session, watched: Watched, every: int, seconds: float, polls: int,
             *, out: bool, began: float, cuttable: bool = False) -> dict[str, Any]:
    """`screen_wait`'s bound, a `TIMEOUT` at a stop; stopped before any retrace, no stop."""
    pending = out and ds.Session.stop_at_bound(session)
    if out and not pending and cuttable and (cut := _cut(session)) is not None:
        raise ds.Invalid("wait_stopped",
            f"a declared breakpoint stopped the machine as the {seconds:g} s bound ran out, so "
            f"the wait for {watched.said} ends there; {PENDING_NOTE}",
            polls=polls, predicate=watched.name,
            **{**_ended_at(session), "cause": st.cause(cut)}, retrace_pending=True,
            **watched.state())
    if out:
        STATE.retrace_pending = pending
    sampled = ("" if not every else
               f", judged every {every} retraces, so a screen shorter than that is passed over")
    # THE SAME FIELDS AS A FOUND WAIT, `already` included and false: a bound that ran out is
    # a wait nothing answered before a frame ran, and the MAME twin says so the same way.
    base: dict[str, Any] = {
        "verdict": contract.TIMEOUT, "predicate": watched.name, "already": False, "polls": polls,
        "sampled_every": every, **watched.state(),
        "retrace_pending": STATE.retrace_pending,
        "waited_s": round(time.monotonic() - began, 1),
        "note": f"{watched.said} was not found in {counted(polls, 'retrace')} within "
                f"{seconds:g} s{sampled}{watched.why()}"
                + (f"; {PENDING_NOTE}" if pending else "")}
    if not (polls or out):
        return st.reply(**base)
    return _stop_reply(session, base)


class TextWatch:
    """The text screen read stop after stop at the least cost per frame.

    `VGA CRTC` is read once, as it places only the cursor. The descriptor tables are re-read only
    when the cpu mode or the virtual-8086 state changes: a guest can enter protected mode under
    an unchanged text screen. `VGA GC` is read each time because the monochrome switch moves the
    page to B0000.
    """

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
