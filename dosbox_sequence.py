"""The SEQUENCE executor: a list of the server's own operations, run in order, in one call.

start(plan=[...]) and perform([...]) run a LIST of the server's own operations, addressed
by NAME: the caller says the high-level steps, the server does the seg:off
and mode work. Two moments, one executor: `start(plan=)` runs a plan on a fresh session,
`perform` runs one against a session already open.

The executor takes the operation table (`ops`) from the server, which owns the
registrations, so this module names no tool: it dispatches what it is handed, waits for
the machine to stop before a console step, and hands back the enriched stop
the list was heading for. `drive` is the loop built on it: mark the log, act, verify,
look.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from scry_core import progress as mprogress
from scry_core import recording
from scry_core import reply_contract as contract
from scry_core import sequence_account as account

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_inputs as inputs
import dosbox_logs as dlogs
import dosbox_media as media
import dosbox_running as guest
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

Ops = dict[str, Callable[..., dict[str, Any]]]

# The ops a step may name: the server's OWN tool names, exactly. NOT the
# lifecycle (`start`/`close`/`build_check`) and NOT `perform` itself.


#: The most calls one recording keeps, this server's bound (`scry_core.recording.Recorder`):
#: `perform` takes a list of any length, so the bound is the recording's own.
RECORD_MAX = 5000

#: THE TOOLS THAT ANSWER ON A RUNNING GUEST, the one table of them: they read a file or the
#: log, post input into the guest, go down the debugger channel, or queue a declaration as
#: `pending` for the next stop, and none types at the debugger's console. Everything else
#: needs a stopped machine, so a sequence WAITS for the next stop before dispatching one. The
#: membership is proven tool by tool against a running session, not trusted to this list;
#: `symbols_load` is out because without a `base` it measures one off the machine.
RUNNING_OK_OPS = frozenset({
    "status", "log", "log_wait", "symbols_find", "comment_list", "comment_save",
    "breakpoint_at", "breakpoint_interrupt", "breakpoint_list", "breakpoint_clear",
    "watch_add", "watch_list", "watch_clear",
    "captures", "capture_frame", "series_capture", "send_keys", "send_mouse",
    "state_save", "state_load", "state_list", "snapshot", "stop", "map_load", "map_save",
    # the media file tools read files, never the machine
    *media.MEDIA_TOOLS})


def answers_running(op: str, args: dict[str, Any]) -> bool:
    """Whether this step answers on a running guest: a `RUNNING_OK_OPS` tool, or the registers
    as the last stop surveyed them, which type nothing at the console."""
    return op in RUNNING_OK_OPS or (op == "registers" and args.get("from_last_stop") is True)


#: The steps that release the machine, each of which comes back with the stop it ended on, or
#: running when it ended on none.
_RELEASES = frozenset({"resume", "run_to", "run_for", "step"})


#: The steps whose wait is for something to SEE, a line or a text: their TIMEOUT is the list's
#: premise failing. A run's TIMEOUT hands the machine back stopped and surveyed, and the list
#: goes on from there.
_WAITS_TO_SEE = frozenset({"log_wait", "screen_wait"})


def _missed(op: str, reply: dict[str, Any]) -> bool:
    """Whether a step's own wait for what it was to see ran out: a `log_wait` or `screen_wait`
    TIMEOUT, or the `expect` of an input step."""
    checked = reply.get("verify")
    return ((op in _WAITS_TO_SEE and reply.get("verdict") == contract.TIMEOUT)
            or (isinstance(checked, dict) and checked.get("verdict") == contract.TIMEOUT))


def _leaves_running(op: str, reply: dict[str, Any]) -> bool:
    """Whether a step left the machine running, read from its OWN reply, not assumed: a
    release that came back with no stop, surveyed (`stop_seq`) or cut (`enrichment`). A
    console step and a reader leave the machine as they found it (stopped), so they answer
    False."""
    return op in _RELEASES and "stop_seq" not in reply and "enrichment" not in reply


def _wait_for_stop(session: ds.Session, seconds: float,
                   progress: ds.Progress = ds.no_progress) -> str:
    """`stopped` | `running` | `gone`: LISTENING for the debugger's prompt on the terminal
    until the machine is back at the debugger, the bound expires, or the emulator has died,
    the same passive wait `run_to` and a bounded `resume` make (`Session.await_stop`).

    NOTHING IS TYPED TO HEAR A STOP. A stop hands the keyboard back to the debugger, which
    prints its prompt, so the arrival announces itself; a command typed at a running guest
    would queue for the stop and, on a quiet machine, spin to the console's timeout, the
    progress tick then coming seconds apart, where a hung server and a long wait look the
    same. A GONE emulator is told apart in the loop (the wait raises `session_broken` the
    moment `alive()` says so); any other refusal of a live one is its own answer, never
    "gone"."""
    began = time.monotonic()
    try:
        expired, _saw_at = ds.Session.await_stop(
            session, began, began + seconds, "the next console step", progress,
            label="waiting for the machine to stop")
    except ds.Invalid:
        if session.alive():
            raise
        return "gone"
    except OSError:
        # a read from a dead pty; confirm and report gone rather than escaping as a
        # traceback the tool wrapper cannot turn into a reply with a session block.
        if not session.alive():
            return "gone"
        raise
    if expired:
        return "gone" if not session.alive() else "running"
    return "stopped"



_TYPED: dict[str, tuple[type | tuple[type, ...], str]] = {
    "int": (int, "an integer"), "float": ((int, float), "a number"),
    "str": (str, "a string"), "bool": (bool, "a boolean"),
}


def _wrong_type(fn: Any, args: dict[str, Any]) -> str | None:
    """The first argument whose value is not what the tool's own signature declares, as the
    refusal names it, or None. A bool is never an integer here: `True` for a count is a
    mistake, not a 1. The scalar annotations are judged, and a scalar `| None` too (a
    `None` passes it, anything else is judged as the scalar); a step's remaining shapes are
    the check's business."""
    for name, param in inspect.signature(fn).parameters.items():
        if name not in args:
            continue
        ann = param.annotation if isinstance(param.annotation, str) else getattr(
            param.annotation, "__name__", "")
        parts = [part.strip() for part in ann.split("|")]
        value = args[name]
        if "None" in parts and len(parts) == 2:
            if value is None:
                continue
            parts.remove("None")
        typed = _TYPED.get(parts[0]) if len(parts) == 1 else None
        if typed is None:
            continue
        want, word = typed
        if (isinstance(value, bool) and want is not bool) or not isinstance(value, want):
            return f"{name} is {word}; got {value!r}"
    return None


def refused_text(refused: list[dict[str, Any]]) -> str:
    """The message of a list refused before anything ran: every refusal, each by its step and
    its op (a step that is no mapping has none to name, and its own message quotes it)."""
    def one(e: dict[str, Any]) -> str:
        op = f" ({e['op']!r})" if isinstance(e["op"], str) else ""
        return f"step {e['step']}{op} {e['message']}"
    return (f"{len(refused)} step(s) refused before anything ran: "
            + "; ".join(one(e) for e in refused) + ". Nothing was run")


def preflight(steps: list[dict[str, Any]], ops: Ops) -> list[dict[str, Any]]:
    """EVERY STEP IS CHECKED BEFORE ANY STEP RUNS, its op, its argument NAMES and its argument
    VALUES, and every refusal is collected rather than the first one returned: a list whose
    third step is not a step, names an argument its tool does not take, or carries a value
    the tool would refuse, must not have executed its first two (a key sent, a machine
    released) before refusing, and a caller told about all of them fixes the batch once.
    The values go through the SAME functions the tools run first when called on their own
    (`dosbox_checks`). Returns the refusals, each `step`, `op`, `code`, `message`."""
    refused: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        op = str(step.get("op")) if isinstance(step, dict) else None
        if op is None or op not in ops:
            refused.append({"step": i,
                            "op": contract.or_unavailable(op, "the step is no mapping"),
                            "code": "bad_argument",
                            "message": f"is not a step ({step!r}): the vocabulary is the "
                                       f"server's own operation names, {sorted(ops)}"})
            continue
        args = recording.step_arguments(step)
        if (why := recording.refuse_recorded(step)) is not None:
            refused.append({"step": i, "op": op, "code": "bad_argument", "message": why})
            continue
        # `ctx` is the SDK's, injected when the client calls a tool, never an argument a
        # step may carry: a stray value would reach the progress bridge as a context.
        if "ctx" in args:
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": "carries `ctx`, which is not a step argument: the "
                                       "client's context is not something a step names"})
            continue
        try:
            # BIND against the REAL tool signature (functools.wraps exposes it via
            # __wrapped__, which inspect.signature follows), so a bad ARGUMENT NAME is the
            # sequence's fault to report, and a genuine TypeError raised INSIDE a tool later
            # is NOT swallowed as "bad arguments" but escapes as the bug it is.
            inspect.signature(ops[op]).bind(**args)
        except TypeError as e:
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": f"has bad arguments: {e}"})
            continue
        wrong = _wrong_type(ops[op], args)
        if wrong is not None:
            refused.append({"step": i, "op": op, "code": "bad_argument", "message": wrong})
            continue
        try:
            checks.preflight(op, args)
        except ds.Invalid as e:
            refused.append({"step": i, "op": op, "code": e.code, "message": str(e)})
        except (TypeError, AttributeError, ValueError) as e:
            # A step's value the schema never saw (a list's members are not typed) reaching a
            # check that assumes its type: the caller's mistake, refused, never a traceback.
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": f"carries a value its tool cannot take: {e}"})
    return refused


# ------------------------------------------------------------ a batch with `summaries`

def validate_summaries(summaries: object) -> None:
    """`summaries` is a yes or a no, in the one sentence both batch tools use."""
    if not isinstance(summaries, bool):
        raise ds.Invalid("bad_argument", f"summaries is true or false; got {summaries!r}")


def _how(stop: dict[str, Any]) -> str:
    """The key a stop is counted under: the declaration it was attributed to, or
    `unattributed` (the debugger keeps no hit flag, so an address match is all a stop can say
    about its cause)."""
    attribution = stop.get("attribution")
    if isinstance(attribution, dict) and attribution.get("attributed"):
        return str(attribution.get("ref"))
    return "unattributed"


#: THIS SERVER'S HALF OF THE ACCOUNT (`scry_core.sequence_account`): a stop's compact row keeps
#: its number and what stopped it, spelled as the full reply spells them; its registers,
#: watches and log stay in the full reply.
SHAPE = account.Shape(kept=("stop_seq", "attribution"), how=_how)


def _batch_stem() -> Path:
    """Where a batch's two files go: this server's own scratch, numbered per call, never the
    caller's `cwd`, which is the project."""
    scratch = STATE.batch_scratch()
    STATE.batches += 1
    return scratch / f"batch-{STATE.batches}"


def account_of(ran: list[dict[str, Any]], summaries: bool, keep_last: bool, since: int,
               also: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`ran` as the reply carries it, and with `summaries` what the machine counted
    (`scry_core.sequence_account.account`); why a batch needs it is REFERENCE's, Sequences in
    one call."""
    return account.account(ran, summaries, keep_last, since,
                           int(STATE.last_stop.get("seq", 0)), SHAPE, _batch_stem, also,
                           rows_shown=st.ROWS_SHOWN)


def run_steps(session: ds.Session, steps: list[dict[str, Any]], wait: float,
              ops: Ops, progress: ds.Progress = ds.no_progress,
              summaries: bool = False, name: str = "perform",
              prechecked: bool = False) -> dict[str, Any]:
    """Execute steps in order, STOPPING at the first failure with a full account. Returns
    `ran` (each step and its reply), `failed` (the step that stopped it, absent when none did),
    `steps_completed`, `held` (the steps whose `recorded` answer this run matched), and the machine
    state. A step is `{"op": <name>, ...args}`. `prechecked` when the tool's pre-gate already
    judged the list whole (`dosbox_checks.steps_whole`), so it is judged once a call.
    """
    held = [0]
    reply = _run_steps(session, steps, wait, ops, progress, summaries, name, held, prechecked)
    return {**reply, "held": held[0]}


def _run_steps(session: ds.Session, steps: list[dict[str, Any]], wait: float, ops: Ops,
               progress: ds.Progress, summaries: bool, name: str, held: list[int],
               prechecked: bool = False) -> dict[str, Any]:
    """`run_steps`' body, counting into `held`.

    THE RESUME BOUNDARY: after a step that leaves the machine RUNNING, only a
    running-OK op may follow immediately; before any CONSOLE op the sequence WAITS for the
    next stop (bounded by `wait`), because a console op sent to a running guest is swallowed.
    A console op reached with the machine still running after that wait is a FAILURE naming
    the boundary, not a call dispatched into the void. The caller owns the `live()` call and
    hands the session in, so the "needs a session" gate sees the TOOL, not this helper.

    With `summaries`, `ran` is the compact account `account_of` builds.
    """
    validate_summaries(summaries)
    since = int(STATE.last_stop.get("seq", 0))     # the stops this call numbers come after it
    refused = [] if prechecked else preflight(steps, ops)
    if refused:
        first = refused[0]
        return st.reply(status="INVALID", code="bad_argument", ran=[], steps_completed=0,
                        failed_at=first["step"], failed=first, errors=refused,
                        message=refused_text(refused))
    ran: list[dict[str, Any]] = []
    running = False
    released_last = False     # the LAST step is the one that let the machine run
    came_to_rest = False      # the LAST step found the released machine stopped
    waited = False            # a wait for a stop was asked for and made: the list earns a verdict
    began = time.monotonic()           # the line of the list rises from here
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or "op" not in step:
            return st.reply(status="INVALID", code="bad_argument",
                          **account_of(ran, summaries, keep_last=False, since=since),
                          steps_completed=len(ran), failed_at=i,
                          message=f"step {i} is not a {{'op': <name>, ...}} object: {step!r}")
        op = str(step["op"])
        args = recording.step_arguments(step)
        if op not in ops:
            return st.reply(status="INVALID", code="bad_argument",
                          **account_of(ran, summaries, keep_last=False, since=since),
                          steps_completed=len(ran), failed_at=i,
                          message=f"{op!r} is not a step: the vocabulary is the server's own "
                                 f"operation names, {sorted(ops)}")
        # A CONSOLE OP NEEDS A STOPPED MACHINE. If the previous step left it
        # running, wait for the stop a breakpoint or the guest will produce -- or find the
        # emulator gone, which is a DIFFERENT answer from "still running".
        if running and not answers_running(op, args):
            state = _wait_for_stop(session, wait, progress)
            if state == "gone":
                return st.reply(status="INVALID", code="session_broken",
                              **account_of(ran, summaries, keep_last=True, since=since),
                              steps_completed=len(ran), failed_at=i,
                              message=f"the emulator is GONE (its bound expired or it "
                                     f"crashed) before the console step {op!r} could run")
            if state == "running":
                why = (f"the machine was still running {wait:g}s after the previous step, so "
                       f"the console step {op!r} cannot be sent (it would be swallowed). A "
                       f"breakpoint or watch has to stop it first")
                if not wait:
                    # NO WAIT WAS ASKED, so nothing ran out: the step could not be sent at all.
                    return st.reply(status="INVALID", code="not_stopped",
                                  **account_of(ran, summaries, keep_last=True, since=since),
                                  steps_completed=len(ran), failed_at=i, message=why)
                # THE WAIT RAN OUT: a verdict, and the list ends here with what it completed.
                return st.reply(**account_of(ran, summaries, keep_last=True, since=since),
                                steps_completed=len(ran), failed_at=_none_failed(),
                                verdict=contract.TIMEOUT,
                                note=f"{why}; it and the steps after it were not sent")
            waited = waited or wait > 0
            running = False
        # A STEP HAS NO REQUEST OF ITS OWN: its progress goes out on the list's line.
        with mprogress.within(progress, f"{name} step {i + 1} of {len(steps)} ({op})", began):
            reply = ops[op](**args)  # its arguments were bound up front, before any step ran
        if reply.get("status") != "ok":
            # STOP HERE. `ran` holds only the steps that SUCCEEDED; the one that
            # stopped the sequence is `failed`, and the machine state rides in `session` --
            # deliberate from inertial is exactly what this keeps separable.
            return st.reply(status="INVALID", code="step_failed",
                          **account_of(ran, summaries, keep_last=False, since=since,
                                       also=[reply]),
                          steps_completed=len(ran), failed_at=i, failed={"op": op, "reply": reply},
                          message=f"step {i} ({op!r}) failed: {reply.get('message')}")
        if (apart := recording.diverged(step.get(recording.RECORDED) or {}, reply)) is not None:
            # A REPLAY THAT LEFT THE SESSION IT REPLAYS stops where it left, where a desync is
            # cheapest to read: every step after it would only compound it.
            message, fields = recording.divergence(i, op, reply, apart)
            return st.reply(status="INVALID", code="diverged",
                          **account_of(ran, summaries, keep_last=False, since=since,
                                       also=[reply]),
                          steps_completed=len(ran), **fields, message=message)
        held[0] += bool(step.get(recording.RECORDED))
        ran.append({"op": op, "reply": reply})
        if _missed(op, reply):
            # A STEP'S OWN WAIT FOR WHAT IT WAS TO SEE RAN OUT: what the rest of the list was
            # built on did not happen, so it ends here with the verdict, as a wait of the
            # list's own does.
            return st.reply(**account_of(ran, summaries, keep_last=True, since=since),
                            steps_completed=len(ran), failed_at=_none_failed(),
                            verdict=contract.TIMEOUT,
                            note=f"step {i} ({op!r}) waited for what it was to see and it did "
                                 f"not come; the steps after it were not sent")
        # A RUNNING-OK OP DOES NOT RELEASE THE MACHINE, and whether it stopped it is the
        # SESSION's to say, never the op's name: `_leaves_running` would answer False for a
        # `send_keys` after a `resume` and send the next console step into a running guest,
        # while a `stop`, or a breakpoint that fired during a key's `expect`, did stop it.
        if not answers_running(op, args):
            came_to_rest = False
            running = _leaves_running(op, reply)
            released_last = running
        else:
            came_to_rest = running and session.at_debugger()
            running = running and not came_to_rest
            released_last = False
    # THE TAIL: if the sequence ends with the machine running, wait for the stop it was
    # heading for and hand back the ENRICHED reply at that stop -- that is the
    # value R1/R3 want, the state AT the breakpoint. If it does not stop in time, say so
    # rather than pretending the run finished at a stop.
    final: dict[str, Any] = {}
    if running and wait == 0:
        final = {"still_running": True,
                 "note": "settle_seconds=0: the sequence ended with the machine running and "
                         "no stop was waited for"}
    elif (running and not released_last
          and not arming.something_can_stop_it()):
        # THE LAST STEP WAS A RUNNING-GUEST OP AND NOTHING DECLARED CAN STOP THE MACHINE,
        # so a wait cannot end: a list that ends in `e9` after a `resume`, with the
        # breakpoints cleared and only show watches declared, wants the guest left
        # running: otherwise the tail sits out its whole bound for a stop nothing can
        # produce. With a breakpoint or change-watch declared the
        # tail still waits (R1's shape: arm, resume, send the key, hand back the stop).
        final = {"still_running": True,
                 "note": "the sequence ended with the machine running after a "
                         "running-guest step and nothing declared can stop it (no "
                         "breakpoint, interrupt or change-watch), so no stop was waited "
                         "for; declare one, or end the list with the resume/run_to/step "
                         "to wait for its stop"}
    elif came_to_rest:
        # THE STOP CAME DURING THE LAST STEP (a `stop`, or a breakpoint that fired while a
        # declaration or a key went in): it is the stop the run was heading for. One a step
        # already surveyed (the `stop` tool's own reply, a step that found it on its own) is
        # named as recorded, never surveyed twice: a second survey numbers it again. Its
        # registers, watches and E9 come from the step's reply when the step surveyed it (the
        # `stop` tool), else off the record.
        recorded = STATE.as_of_current(session)
        last = ran[-1]["reply"] if ran else {}
        if recorded is None:
            final = {"stopped": _final_stop(session)}
        elif last.get("stop_seq") == recorded["stop_seq"] and "regs" in last:
            final = {"stopped": {**recorded, **guest.recorded_position(),
                                 **{k: last[k] for k in _ENRICHED if k in last}}}
        else:
            final = {"stopped": _recorded_stop(session, recorded)}
    elif running:
        state = _wait_for_stop(session, wait, progress)
        if state == "gone":
            return st.reply(status="INVALID", code="session_broken",
                            **account_of(ran, summaries, keep_last=True, since=since),
                            steps_completed=len(ran), failed_at=_none_failed(),
                            message="the sequence ended with the machine running and the "
                                    "emulator is now GONE (its bound expired or it crashed)")
        waited = True
        if state == "stopped":
            final = {"stopped": _final_stop(session)}
        else:
            final = {"verdict": contract.TIMEOUT,
                     "note": f"the sequence ended with the machine running and it did not "
                             f"stop within {wait:g}s"}
    # A LIST THAT WAITED FOR A STOP EARNS A VERDICT, `TARGET` when every wait it made ended at
    # one; a list that waited for none carries none.
    if waited and "verdict" not in final and "still_running" not in final:
        final = {"verdict": contract.TARGET, **final}
    stopped = final.get("stopped")
    return st.reply(**account_of(ran, summaries, keep_last=True, since=since,
                                 also=[stopped] if isinstance(stopped, dict) else None),
                    steps_completed=len(ran), failed_at=_none_failed(), **final)


def _none_failed() -> dict[str, Any]:
    """`failed_at` of a list no step of which failed."""
    return contract.unavailable("no step failed")


#: What a stop's enriched reply adds to the record of it.
_ENRICHED = ("regs", "watches", "e9", "instruction")


def _recorded_stop(session: ds.Session, recorded: dict[str, Any]) -> dict[str, Any]:
    """`guest.recorded_stop_reply`, guarded as `_final_stop` guards the survey: a read that
    refuses at this stop marks the enrichment unavailable and keeps the record."""
    try:
        return guest.recorded_stop_reply(session, recorded)
    except ds.Invalid as e:
        return {**recorded, "enrichment": {"available": False, "why": str(e)}}


def _final_stop(session: ds.Session) -> dict[str, Any]:
    """The enriched reply at the stop a sequence ends on. THE ENRICHMENT IS GUARDED, as
    `guest.stop_or_base` guards the same call: a cut pane at this final stop must not throw
    away the whole sequence account. `guest.stop_reply` reads `where`/`registers` AGAIN and
    either can refuse on a partial repaint, so a failure there marks the enrichment
    unavailable while `ran`/`steps_completed` stand. It takes the tool's own fields as **base; the
    tail adds none, so it is called with none: `base={}` would land a literal `base` field."""
    try:
        return guest.stop_reply(session)
    except ds.Invalid as e:
        return {"enrichment": {"available": False, "why": str(e)}}


def validate_wait(wait: float) -> None:
    """The bound a sequence waits for a stop, refused when it is not a bound: zero or a
    negative one makes the decision-37 wait give up at once and report a machine that was
    never given the time, and a huge one is not a bound."""
    if isinstance(cast(object, wait), bool) or not isinstance(cast(object, wait), int | float) \
            or not 0 <= wait <= ds.RUN_TO_MAX:
        raise ds.Invalid("bad_argument",
            f"settle_seconds is a bound from 0 (never wait) to {ds.RUN_TO_MAX} seconds; "
                         f"got {wait!r}")


def _verify_after_wait(session: ds.Session, expect: str, wait_s: float, mark: int,
                       progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The VERIFY on a running guest: wait up to `wait_s` for a new line since the mark."""
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
    """The VERIFY on a guest stopped at the debugger: one read since the mark, no wait,
    because nothing more will be written until the machine is resumed."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"checked": False, "expected": expect, "why": str(e), "code": e.code}
    reaction = dlogs.compiled(inputs.program_reaction(expect))
    hits = [ln for ln in since if reaction.search(ln)]
    if not hits:
        return {"checked": True, "seen": False, "expected": expect,
                "waited_s": 0.0, "lines_on_disk": len(since),
                "why": f"no line matching {expect!r} since the mark, and the machine is "
                       f"STOPPED at the debugger, so nothing more will be written until it "
                       f"is resumed: waiting would not change the answer"}
    return inputs.verify_block(expect, {"verdict": contract.TARGET, "line": hits[0],
                                    "already": True, "lines_before": since.index(hits[0]),
                                    "waited_s": 0.0, "lines_total": len(hits)})


def _look(session: ds.Session, mark: int, pattern: str, limit: int) -> dict[str, Any]:
    """The LOOK after an act: the guest's lines since the mark matching `pattern`, cut to the
    last `limit`, with the counts that say what was cut, in `log`'s own words. Unavailable is
    said, not hidden."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"guest": {"available": False, "why": str(e)}}
    rx = dlogs.compiled(pattern)
    kept = [ln for ln in since if rx.search(ln)]
    return {"guest": {"available": True, "since_mark": mark, "lines_written": len(since),
                   "lines_total": len(kept), "truncated": len(kept) > limit,
                   "lines": kept[-limit:], "pattern": pattern}}


def _where_stopped(failed_at: object) -> str:
    """Where a refused act stopped: at its failing step, or after its last step when every step
    ran and the tail's wait found the emulator gone (`failed_at` unavailable)."""
    return f"at step {failed_at}" if isinstance(failed_at, int) else "after its last step"


def drive(session: ds.Session, ops: Ops, act: list[dict[str, Any]], expect: str | None,
          seconds: float | None, pattern: str, limit: int, wait: float,
          progress: ds.Progress = ds.no_progress, summaries: bool = False) -> dict[str, Any]:
    """The body of the `drive` tool. Its arguments are judged before the session gate
    (`dosbox_checks._drive`, the act whole); what needs the session, the input route of a key
    step, is judged when the act runs."""
    wait_s = inputs.EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    # THE MARK, before anything moves. A session with no logfile has no LOOK and no VERIFY,
    # and that is refused before the act rather than discovered after it.
    try:
        mark = session.e9_mark()
    except ds.Invalid as e:
        raise ds.Invalid("no_channel",
            f"drive needs a session started with a logfile: {e}") from None
    ran = run_steps(session, act, wait, ops, progress, summaries, name="drive",
                    prechecked=True)
    account = {k: v for k, v in ran.items() if k not in ("status", "session")}
    if ran.get("status") != "ok":
        return st.reply(status="INVALID", code="step_failed", act=account,
                      message=f"the act stopped {_where_stopped(ran.get('failed_at'))}: "
                              f"{ran.get('message')}",
                      looked=_look(session, mark, pattern, limit))
    checked: dict[str, Any] = {"checked": False,
                                "why": "no `expect` given; the act's own steps carried "
                                       "whatever verification they asked for"}
    if expect is not None and account.get("verdict") == contract.TIMEOUT:
        # THE ACT DID NOT COME TO REST: its own wait ran out, so what it was meant to cause
        # cannot be asked of the guest yet.
        checked = contract.unavailable("the act's own wait ran out (`act.verdict` TIMEOUT), so "
                                       "its effect was not checked")
    elif expect is not None:
        # A GUEST STOPPED AT THE DEBUGGER CANNOT WRITE A LINE. When the act ended at a stop
        # (its tail found one, or no step ever let the machine run), waiting `seconds` for
        # the expectation would burn the bound on a machine that cannot act and then blame
        # the program. So the log is read ONCE from the mark and the verdict says why.
        # WHICH IT IS comes from the act's own tail when it had one, and from the machine
        # otherwise: an act of running-guest steps alone (the usual shape) says nothing
        # about the state, because the executor starts every sequence assuming a stopped
        # machine; the session's own flag answers with no console round trip (a command typed
        # at a running guest's console waits out its whole timeout and lands at the next stop).
        if "still_running" in ran:
            ended_running = True
        elif "stopped" in ran:
            ended_running = False
        else:
            ended_running = not session.at_debugger()
        checked = (_verify_after_wait(session, expect, wait_s, mark, progress)
                   if ended_running else _verify_at_a_stop(session, expect, mark))
        if checked.get("seen") is False and "verdict" not in checked:
            # A STOPPED MACHINE LACKS THE LINE, found during the wait or before it: the guest
            # could not write it, so this is the stop's, never the program's miss.
            stop, where = STATE.stop_named(session)
            when = " during the wait" if checked.get("stopped_during_wait") else ""
            return st.reply(status="INVALID", code="wait_stopped", act=account,
                          verify=checked, last_stop=stop,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran and the machine is STOPPED at the debugger"
                                 f"{when}{where}, so the guest could not do what was "
                                 f"expected: {checked['why']}")
        if not checked.get("checked"):
            # The verify's own refusal names the cause; the act ran, so the reply keeps it.
            code: contract.Code = checked.get("code", "unexpected_answer")
            return st.reply(status="INVALID", code=code, act=account, verify=checked,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran and its effect could NOT be verified: "
                                 f"{checked['why']}")
    return st.reply(act=account, verify=checked, looked=_look(session, mark, pattern, limit))
