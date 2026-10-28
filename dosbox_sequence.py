"""The SEQUENCE executor: a list of the server's own operations, run in order, in one call."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import frame_window, roster
from scry_core import reply_contract as contract
from scry_core import sequence as executor
from scry_core import sequence_account as account
from scry_core import steps as step_judge
from scry_core import vocabulary as vocab

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_debugger as dbg
import dosbox_inputs as inputs
import dosbox_logs as dlogs
import dosbox_media as media
import dosbox_running as guest
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

Ops = dict[str, Callable[..., dict[str, Any]]]

#: The most calls one recording keeps (`scry_core.recording.Recorder`).
RECORD_MAX = 5000
#: Default wait for a stop, per step.
SETTLE_DEFAULT_S = 30.0

#: Tools that answer on a running guest (none needs the debugger to hold it); any other waits
#: for the next stop. Membership is proven per tool against a live session; `symbols_load` is
#: out because without a `base` it measures one off the machine.
RUNNING_OK_OPS = frozenset({
    "status", "log", "log_wait", "symbols_find", "comment_list", "comment_write",
    "breakpoint_at", "breakpoint_interrupt", "regpoint_add", "declaration_list",
    "declaration_clear",
    "watch_add", "captures", "capture_frame", "series_capture", "send_keys", "send_mouse",
    "state_write", "state_list", "snapshot", "stop", "screen_map_write", "guest_file",
    *media.MEDIA_TOOLS})
#: Methods of a folded tool that answer on a running guest; its others need a stop. Both state
#: methods go down the debugger channel, breaking in on a running guest and releasing it after.
RUNNING_METHODS: dict[str, tuple[str, ...]] = {"comment_write": ("save",),
                                                "screen_map_write": ("load", "save"),
                                                "state_write": ("save", "load")}
GATE = roster.RunningGate(ops=RUNNING_OK_OPS, methods=RUNNING_METHODS)


def answers_running(op: str, args: dict[str, Any]) -> bool:
    return GATE.answers(op, args)


_RELEASES = frozenset({"resume", "run_to", "run_for", "step"})


#: Waits for something to see: their TIMEOUT fails the list's premise, unlike a run's TIMEOUT,
#: which hands back a stopped machine and the list goes on.
_WAITS_TO_SEE = frozenset({"log_wait", "screen_wait"})


def _missed(op: str, reply: dict[str, Any]) -> bool:
    """Whether a step's own wait for what it was to see ran out."""
    checked = reply.get("verify")
    return ((op in _WAITS_TO_SEE and reply.get("verdict") == contract.TIMEOUT)
            or (isinstance(checked, dict) and checked.get("verdict") == contract.TIMEOUT))


def _leaves_running(op: str, reply: dict[str, Any]) -> bool:
    """Whether a release came back with no stop, read from its own reply."""
    return op in _RELEASES and "stop_seq" not in reply and "enrichment" not in reply


def _wait_for_stop(session: ds.Session, seconds: float,
                   progress: ds.Progress = ds.no_progress) -> executor.Waited:
    """`stopped` | `running` | `gone`, asked of the debugger's run state (`Session.await_stop`)."""
    began = time.monotonic()
    try:
        expired, _saw_at = ds.Session.await_stop(
            session, began, began + seconds, "the next step", progress,
            label="waiting for the machine to stop", look_once=True)
    except ds.Invalid:
        if session.alive():
            raise
        return "gone"
    except OSError:
        # a channel to a dead emulator
        if not session.alive():
            return "gone"
        raise
    if expired:
        return "gone" if not session.alive() else "running"
    return "stopped"


def preflight(steps: list[dict[str, Any]], ops: Ops) -> list[dict[str, Any]]:
    """Check every step's op, argument names and values before any runs; collect all refusals.

    Returns the refusals, each `step`, `op`, `code`, `message`."""
    refused: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        op = executor.step_op(step)
        if op is None or op not in ops:
            refused.append(executor.not_a_step(i, step, "the step names no `op`"))
            continue
        refusal, args = step_judge.judge(ops[op], step)
        if refusal is not None:
            refused.append({"step": i, "op": op, **refusal})
            continue
        try:
            checks.preflight(op, args)
        except ds.Invalid as e:
            refused.append({"step": i, "op": op, "code": e.code, "message": str(e)})
        except (TypeError, AttributeError, ValueError) as e:
            # a list's members are untyped, so a check can meet a value of the wrong type
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": f"its value is not one the tool's argument check "
                                       f"could judge: {e}"})
    return refused


def _cause_key(stop: dict[str, Any]) -> str:
    """A stop's `cause` without the address, so one declaration is one key."""
    return st.cause_key(str(stop.get("cause")))


#: This server's half of `scry_core.sequence_account`: a compact stop row keeps its number and
#: cause; registers, watches and log stay in the full reply.
SHAPE = account.Shape(kept=("stop_seq", "cause"), cause_key=_cause_key)


def _batch_stem() -> Path:
    """Where a batch's two files go: the server's scratch, never the caller's `cwd`."""
    scratch = STATE.batch_scratch()
    STATE.batches += 1
    return scratch / f"batch-{STATE.batches}"


def account_of(ran: list[dict[str, Any]], summaries: bool, keep_last: bool, since: int,
               also: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`ran` as the reply carries it (`scry_core.sequence_account.account`)."""
    return account.account(ran, summaries, keep_last, since,
                           int(STATE.last_stop.get("seq", 0)), SHAPE, _batch_stem, also,
                           rows_shown=st.ROWS_SHOWN)


class _Dosbox(executor.SequenceMachine):
    """This server's half of a list (`scry_core.sequence`)."""

    undeclared = "no breakpoint, no interrupt breakpoint, no change watch"

    def __init__(self, session: ds.Session, summaries: bool) -> None:
        self.session, self.summaries = session, summaries
        self.since = int(STATE.last_stop.get("seq", 0))  # stops this list numbers follow it

    def answers_running(self, op: str, args: dict[str, Any]) -> bool:
        return answers_running(op, args)

    def running(self) -> bool:
        return not self.session.at_debugger()

    def leaves_running(self, op: str, reply: dict[str, Any]) -> bool:
        return _leaves_running(op, reply)

    def wait_for_stop(self, seconds: float, progress: ds.Progress,
                      tail: bool = False) -> executor.Waited:
        return _wait_for_stop(self.session, seconds, progress)

    def can_be_stopped(self) -> bool:
        return arming.something_can_stop_it()

    def tail_stop(self) -> dict[str, Any]:
        return _final_stop(self.session)

    def account(self, ran: list[dict[str, Any]], keep_last: bool,
                also: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return account_of(ran, self.summaries, keep_last, self.since, also)

    def missed(self, op: str, reply: dict[str, Any]) -> bool:
        return _missed(op, reply)

    def rested(self, ran: list[dict[str, Any]]) -> dict[str, Any] | None:
        """The stop that came during the last step, if any.

    A stop a step already surveyed is named as recorded, never surveyed again: a second
    survey numbers it twice."""
        recorded = STATE.as_of_current(self.session)
        last = ran[-1]["reply"] if ran else {}
        if recorded is None:
            return _final_stop(self.session)
        if last.get("stop_seq") == recorded["stop_seq"] and "regs" in last:
            return {**guest.recorded_head(recorded),
                    **{k: last[k] for k in _ENRICHED if k in last}}
        return _recorded_stop(self.session, recorded)


def run_steps(session: ds.Session, steps: list[dict[str, Any]], wait: float,
              ops: Ops, progress: ds.Progress = ds.no_progress,
              summaries: bool = False, name: str = "perform",
              tail_wait: bool = True, until_frame: int = 0) -> dict[str, Any]:
    """Execute steps in order (`scry_core.sequence.run`), stopping at the first failure.

    A step is `{"op": <name>, ...args}`; the list arrives judged whole by
    `dosbox_checks.steps_whole`. `tail_wait` is False when the caller waits for the list's
    effect its own way (`drive` with an `expect`); with `until_frame` the list repeats
    (`frame_window.Window`)."""
    account.check_summaries(summaries)
    frame_window.check_arguments(until_frame, summaries)
    window = None
    if until_frame:
        here = _until_from(session)
        frame_window.check_until(steps, until_frame, here, here is None)
        window = frame_window.Window(until_frame, here, here is None, progress)
    ended = executor.run(_Dosbox(session, summaries), steps, ops, wait, progress, name,
                         tail_wait=tail_wait, cycle=window)
    if window is not None:
        window.last_line()
    if ended.code is not None:
        return st.reply(status="INVALID", code=ended.code, message=ended.message,
                        **ended.fields, held=ended.held)
    return st.reply(**ended.fields, held=ended.held)


_ENRICHED = ("regs", "watches", "e9", "instruction")


def _until_from(session: ds.Session) -> int | None:
    """The frame a stopped machine stands in, None on a running one; a build whose `RUNSTATE`
    counts no frames is refused."""
    session.require_run_state("until_frame")
    stopped = dbg.read_run_state(session)
    if session.frames is None:
        raise ds.Invalid("no_channel", f"until_frame needs a frame counter: {dbg.NO_FRAMES_WHY}; "
                         f"`run_for(frames=)` counts retraces from where the machine stands")
    return session.frames if stopped else None


def _recorded_stop(session: ds.Session, recorded: dict[str, Any]) -> dict[str, Any]:
    """`guest.recorded_stop_reply`, keeping the record when a read refuses."""
    try:
        return guest.recorded_stop_reply(session, recorded)
    except ds.Invalid as e:
        return {**recorded, "enrichment": {"available": False, "why": str(e)}}


def _final_stop(session: ds.Session) -> dict[str, Any]:
    """The enriched reply at the stop a sequence ends on.

    Guarded: an unreadable stop can make `guest.stop_reply` refuse, which must not lose the
    account. The tail adds no fields, so no `base` is passed (`base={}` would land a literal
    `base` field). A retrace a `run_for` left armed may be this stop."""
    try:
        return guest.stop_reply(session, retrace_may_stop=True)
    except ds.Invalid as e:
        return {"enrichment": {"available": False, "why": str(e)}}


def validate_wait(wait: float) -> None:
    """Refuse a negative or huge bound; 0 does not wait."""
    vocab.check_wait(wait, "settle_seconds", zero_means="never wait")


def _verify_after_wait(session: ds.Session, expect: str, wait_s: float, mark: int,
                       progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """Wait up to `wait_s` for a new line since the mark."""
    try:
        reaction = session.e9_wait(inputs.program_reaction(expect), wait_s, mark=mark,
                                   progress=progress)
    except ds.E9Stopped as e:
        guest.observe_stop(session)
        return {"checked": True, "seen": False, "expected": expect,
                "stopped_during_wait": True, "waited_s": e.waited_s,
                "lines_on_disk": e.arrived, "why": str(e)}
    except ds.Invalid as e:
        return {"checked": False, "expected": expect, "why": str(e), "code": e.code}
    return inputs.verify_block(expect, reaction)


def _verify_at_a_stop(session: ds.Session, expect: str, mark: int) -> dict[str, Any]:
    """One read since the mark, no wait: a stopped machine writes nothing more."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"checked": False, "expected": expect, "why": str(e), "code": e.code}
    reaction = dlogs.compiled(inputs.program_reaction(expect))
    hits = [ln for ln in since if reaction.search(ln)]
    if not hits:
        return {"checked": True, "seen": False, "expected": expect,
                "waited_s": 0.0, "lines_on_disk": len(since),
                "why": f"no line matching {expect!r} since the mark, and the act left the "
                       f"machine STOPPED at the debugger, where it writes nothing: this look "
                       f"is one read. `send_keys` or `send_mouse` with `expect` waits on a "
                       f"stopped machine retrace by retrace"}
    return inputs.verify_block(expect, {"verdict": contract.TARGET, "line": hits[0],
                                    "already": True, "lines_before": since.index(hits[0]),
                                    "waited_s": 0.0, "lines_total": len(hits)})


def _look(session: ds.Session, mark: int, pattern: str, limit: int) -> dict[str, Any]:
    """The guest's lines since the mark (`account.looked`)."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"guest": {"available": False, "why": str(e)}}
    return account.looked("guest", since, mark, dlogs.compiled(pattern), limit)


def drive_refused(e: ds.Invalid) -> ds.Invalid:
    """`drive`'s refusal before anything ran, in the one shape every `drive` reply has."""
    judged = {k: e.fields.pop(k) for k in ("ran", "steps_completed", "failed_at", "failed",
                                          "errors") if k in e.fields}
    act = judged or {"ran": [], "steps_completed": 0, "failed": executor.none_failed(),
                      "failed_at": executor.none_failed()}
    return ds.Invalid(e.code, str(e), **e.fields, act=act,
                      verify={"checked": False, "why": "the act was refused before anything ran"},
                      looked=contract.unavailable("the act was refused before anything ran, so "
                                                  "nothing was looked at"))


def drive(session: ds.Session, ops: Ops, act: list[dict[str, Any]], expect: str | None,
          seconds: float | None, pattern: str, limit: int, wait: float,
          progress: ds.Progress = ds.no_progress, summaries: bool = False) -> dict[str, Any]:
    """The body of the `drive` tool: arguments judged before the session gate
    (`dosbox_checks._drive`), the key input route when the act runs."""
    wait_s = inputs.drive_wait_s(seconds)
    # without a logfile there is no LOOK or VERIFY: refuse before the act
    try:
        mark = session.e9_mark()
    except ds.Invalid as e:
        raise drive_refused(ds.Invalid("no_channel",
            f"drive needs a session started with a logfile: {e}")) from None
    # with an `expect` the verify is the wait, or a running guest's act would first sit out
    # `settle_seconds`
    ran = run_steps(session, act, wait, ops, progress, summaries, name="drive",
                    tail_wait=expect is None)
    told = executor.act_told(ran)
    if ran.get("status") != "ok":
        # `step_failed`, or the executor's own `not_stopped` / `session_broken`
        act_code, said = executor.act_stopped(ran)
        return st.reply(status="INVALID", code=act_code, act=told, message=said,
                        looked=_look(session, mark, pattern, limit))
    checked: dict[str, Any] = dict(executor.NO_EXPECT)
    if told.get("verdict") == contract.TIMEOUT:
        # the act did not do what it was asked, so nothing it did is checked
        checked = executor.act_ran_out()
    elif expect is not None:
        # A stopped guest cannot write a line: read the log once rather than burn the bound.
        # The act's own tail says which it is; else the session flag.
        if "still_running" in ran:
            ended_running = True
        elif "stopped" in ran:
            ended_running = False
        else:
            ended_running = not session.at_debugger()
        checked = (_verify_after_wait(session, expect, wait_s, mark, progress)
                   if ended_running else _verify_at_a_stop(session, expect, mark))
        if checked.get("seen") is False and "verdict" not in checked:
            # the stop's miss, never the program's
            stop, where = STATE.stop_named(session)
            when = " during the wait" if checked.get("stopped_during_wait") else ""
            return st.reply(status="INVALID", code="wait_stopped", act=told,
                          verify=checked, last_stop=stop,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran, the machine is STOPPED at the debugger"
                                 f"{when}{where}, and no line matching `expect` was in the "
                                 f"log since the act: {checked['why']}")
        if not checked.get("checked"):
            code: contract.Code = checked.get("code", "unexpected_answer")
            return st.reply(status="INVALID", code=code, act=told, verify=checked,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran and its effect could NOT be verified: "
                                 f"{checked['why']}")
    return st.reply(act=told, verify=checked, looked=_look(session, mark, pattern, limit))
