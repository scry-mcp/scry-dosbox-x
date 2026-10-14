"""The SEQUENCE executor: a list of the server's own operations, run in order, in one call.

start(plan=[...]) and perform([...]) run a LIST of the server's own operations, addressed
by NAME (decision 2, 4): the caller says the high-level steps, the server does the seg:off
and mode work. Two moments, one executor: `start(plan=)` runs a plan on a fresh session,
`perform` runs one against a session already open.

The executor takes the operation table (`ops`) from the server, which owns the
registrations, so this module names no tool: it dispatches what it is handed, waits for
the machine to stop before a console step (decision 37), and hands back the enriched stop
the list was heading for. `drive` is the loop built on it: mark the log, act, verify,
look.
"""

from __future__ import annotations

import inspect
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_inputs as inputs
import dosbox_running as guest
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

Ops = dict[str, Callable[..., dict[str, Any]]]

# The ops a step may name: the server's OWN tool names, exactly (decision 34). NOT the
# lifecycle (`start`/`close`/`build_check`) and NOT `perform` itself.
#
# NOTHING IS DEFERRED TODAY: `send_keys` sat here (KNOWN-BUT-UNBUILT) until its route was
# agreed, and it is now built. The set stays because the mechanism is the honest way to
# name a step whose tool is planned but not yet real -- a clear refusal, not a KeyError.
DEFERRED_OPS: set[str] = set()


#: THE TOOLS THAT ANSWER ON A RUNNING GUEST, the one table of them: they read a file or the
#: log, post host input, work the window's menu, or queue a declaration as `pending` for the
#: next stop, and none types at the debugger's console. Everything else needs a stopped
#: machine, so a sequence WAITS for the next stop before dispatching one. The membership is
#: proven tool by tool against a running session, not trusted to this list; `symbols_load` is
#: out because without a `base` it measures one off the machine.
RUNNING_OK_OPS = frozenset({
    "status", "log", "log_wait", "symbols_find", "comment_list", "comment_save",
    "breakpoint_at", "breakpoint_interrupt", "breakpoint_list", "breakpoint_clear",
    "watch_add", "watch_list", "watch_clear",
    "captures", "capture_frame", "send_keys", "send_mouse",
    "state_save", "state_load", "state_list", "snapshot", "stop"})


def _leaves_running(op: str, reply: dict[str, Any]) -> bool:
    """Whether a step left the machine running, read from its OWN reply, not assumed:
    `resume` that did not halt, `run_to`, `run_for` or `step` that came back running. A console
    step and a reader leave the machine as they found it (stopped), so they answer False."""
    if op == "resume":
        return not bool(reply.get("halted"))
    if op in ("run_to", "run_for", "step"):
        return bool(reply.get("running"))
    return False


def _wait_for_stop(session: ds.Session, seconds: float,
                   progress: ds.Progress = ds.no_progress) -> str:
    """`stopped` | `running` | `gone`: LISTENING for the debugger's prompt on the terminal
    until the machine is back at the debugger, the bound expires, or the emulator has died,
    the same passive wait `run_to` and a bounded `resume` make (`Session._await_stop`).

    IT USED TO POLL by typing a `BPLIST` and reading the position, and that cost two things
    the passive form does not: the keystrokes queued and were consumed at the stop, and on a
    quiet running machine each poll spun to the console's timeout, so the progress tick came
    several seconds apart instead of every PROGRESS_EVERY_S, which is exactly the distance at
    which a hung server and a long wait look the same again. A stop hands the keyboard back
    to the debugger, which prints its prompt: the arrival announces itself, and nothing has
    to be typed to hear it. A GONE emulator is told apart in the loop (the wait raises
    `session_broken` the moment `alive()` says so) rather than read as "still running"."""
    began = time.monotonic()
    try:
        expired, _saw_at = ds.Session._await_stop(
            session, began, began + seconds, "the next console step", progress,
            label="waiting for the machine to stop")
    except ds.Invalid:
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


def preflight(steps: list[dict[str, Any]], ops: Ops, *, serial: bool) -> list[dict[str, Any]]:
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
        if op is None or (op not in ops and op not in DEFERRED_OPS):
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": f"is not a step ({step!r}): the vocabulary is the "
                                       f"server's own operation names, {sorted(ops)}"})
            continue
        if op in DEFERRED_OPS:
            continue
        args = {k: v for k, v in step.items() if k != "op"}
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
            checks.preflight(op, args, serial=serial)
        except ds.Invalid as e:
            refused.append({"step": i, "op": op, "code": e.code, "message": str(e)})
        except (TypeError, AttributeError, ValueError) as e:
            # A step's value the schema never saw (a list's members are not typed) reaching a
            # check that assumes its type: the caller's mistake, refused, never a traceback.
            refused.append({"step": i, "op": op, "code": "bad_argument",
                            "message": f"carries a value its tool cannot take: {e}"})
    return refused


# ------------------------------------------------------------ a batch with `summaries`

#: What a compact row keeps of a STOP besides its summary line: its number and what stopped
#: it, spelled as the full reply spells them.
_STOP_KEPT = ("stop_seq", "attribution")


def validate_summaries(summaries: object) -> None:
    """`summaries` is a yes or a no, in the one sentence both batch tools use."""
    if not isinstance(summaries, bool):
        raise ds.Invalid("bad_argument", f"summaries is true or false; got {summaries!r}")


def _is_stop(reply: dict[str, Any]) -> bool:
    """Whether `reply` is a stop's: every one carries the number `stop_reply` gave it."""
    return isinstance(reply.get("stop_seq"), int)


def _stops_in(reply: dict[str, Any]) -> list[dict[str, Any]]:
    """Every stop `reply` surveys: its own, and the one the guest reached on its own that
    this contact found and recorded (`stopped_on_its_own`), which carries its number too."""
    found = reply.get("stopped_on_its_own")
    return [r for r in (reply, found) if isinstance(r, dict) and _is_stop(r)]


def _how(stop: dict[str, Any]) -> str:
    """The key a stop is counted under: the declaration it was attributed to, or
    `unattributed` (the debugger keeps no hit flag, so an address match is all a stop can say
    about its cause)."""
    attribution = stop.get("attribution")
    if isinstance(attribution, dict) and attribution.get("attributed"):
        return str(attribution.get("ref"))
    return "unattributed"


def _brief(entry: dict[str, Any], step: int) -> dict[str, Any]:
    """A step's COMPACT ROW: its index in the list, its op, and its reply cut to the line the
    client paints and the verdict (`summary`, every tool's first field; `status`). A STOP
    keeps what makes it one, `_STOP_KEPT`; its registers, watches and log stay in the full
    reply."""
    reply = entry["reply"]
    cut = {"summary": reply.get("summary"), "status": reply.get("status")}
    if _is_stop(reply):
        cut.update({k: reply.get(k) for k in _STOP_KEPT})
    if "stopped_on_its_own" in reply:
        cut["stopped_on_its_own"] = reply["stopped_on_its_own"]
    return {"step": step, "op": entry["op"], "reply": cut}


def _stops(replies: list[dict[str, Any]], first: int, last: int) -> dict[str, Any]:
    """THE MACHINE'S COUNT OF THE STOPS it numbered from `first` to `last`, so no reader has to
    assemble one: the range, the stops the replies surveyed in it, a count per `_how`, and
    `unaccounted`, the stops numbered in the range that no reply surveyed (a stop a refusing
    reader took is real, so it is reported and never refused). No stop numbered is `null` for
    both ends."""
    seen: dict[int, str] = {}
    for reply in replies:
        for stop in _stops_in(reply):
            seq = int(stop["stop_seq"])
            if first <= seq <= last:
                seen[seq] = _how(stop)
    by_how: dict[str, int] = {}
    for how in seen.values():
        by_how[how] = by_how.get(how, 0) + 1
    numbered = last >= first
    return {"stop_seq_first": first if numbered else None,
            "stop_seq_last": last if numbered else None, "surveyed": len(seen),
            "by_how": by_how, "unaccounted": last - first + 1 - len(seen) if numbered else 0}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    """`rows` as JSON Lines at `path`, one a line, ASCII by JSON's own escapes."""
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="ascii")
    return str(path)


def _files(rows: list[dict[str, Any]], replies: list[dict[str, Any]]) -> dict[str, Any]:
    """The two files of a batch with summaries, numbered per call. They are written after every
    step ran, so the machine has already moved: a scratch that refuses them costs the files,
    said in `files_why`, and never the account beside them."""
    try:
        scratch = STATE.batch_scratch()
    except OSError as e:
        return {"ran_path": None, "replies_path": None, "files_why": str(e)}
    STATE.batches += 1
    stem = scratch / f"batch-{STATE.batches}"
    pair = (stem.with_suffix(".ran.jsonl"), stem.with_suffix(".replies.jsonl"))
    try:
        return {"ran_path": _write_jsonl(pair[0], rows),
                "replies_path": _write_jsonl(pair[1], replies)}
    except OSError as e:
        # THE PAIR OR NEITHER: a file the reply does not name is one nobody finds.
        for path in pair:
            path.unlink(missing_ok=True)
        return {"ran_path": None, "replies_path": None, "files_why": str(e)}


def account_of(ran: list[dict[str, Any]], summaries: bool, keep_last: bool, since: int,
               also: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`ran` as the reply carries it, and with `summaries` what the machine counted. Without
    `summaries`, `ran` as it is, each step's full reply.

    With `summaries`, every step is cut to its compact row (`_brief`) except, with
    `keep_last`, the last one that ran, kept whole. A list that failed at a step keeps that
    step whole under `failed`. `ran` shows the FIRST `ROWS_SHOWN` compact
    rows and the kept step, with `steps_total` and `truncated`; every compact row goes to
    `ran_path` and every full reply to `replies_path`. `stops` counts the stops the session
    numbered since `since`, read off the steps' replies and `also`'s (the step that failed,
    the stop the tail waited for). Why a batch needs it is REFERENCE's, Sequences in one
    call."""
    if not summaries:
        return {"ran": ran}
    rows = [_brief(r, i) for i, r in enumerate(ran)]
    briefed = len(ran) - 1 if keep_last and ran else len(ran)
    shown = rows[:min(briefed, st.ROWS_SHOWN)] + [{"step": i, **ran[i]}
                                                   for i in range(briefed, len(ran))]
    replies = [r["reply"] for r in ran] + (also or [])
    # THE RANGE ENDS AT THE NEWEST STOP ANY REPLY CARRIES, or at the record's if that is newer:
    # a session buried mid-list clears the record, and a range read off it alone would then
    # hide the stops the rows above still show.
    last = max([int(STATE.last_stop.get("seq", 0))]
               + [int(s["stop_seq"]) for r in replies for s in _stops_in(r)])
    return {"ran": shown, "steps_total": len(ran), "truncated": briefed > st.ROWS_SHOWN,
            **_files(rows, [{"step": i, **r} for i, r in enumerate(ran)]),
            "stops": _stops(replies, since + 1, last)}


def run_steps(session: ds.Session, steps: list[dict[str, Any]], wait: float,
              ops: Ops, progress: ds.Progress = ds.no_progress,
              summaries: bool = False) -> dict[str, Any]:
    """Execute steps in order, STOPPING at the first failure with a full account (decision
    3). Returns `ran` (each step and its reply), `failed` (the step that stopped it, or
    None), `completed`, and the machine state. A step is `{"op": <name>, ...args}`.

    DECISION 37, the resume boundary: after a step that leaves the machine RUNNING, only a
    running-OK op may follow immediately; before any CONSOLE op the sequence WAITS for the
    next stop (bounded by `wait`), because a console op sent to a running guest is swallowed.
    A console op reached with the machine still running after that wait is a FAILURE naming
    the boundary, not a call dispatched into the void. The caller owns the `_live()` call and
    hands the session in, so the "needs a session" gate sees the TOOL, not this helper.

    With `summaries`, `ran` is the compact account `account_of` builds.
    """
    validate_summaries(summaries)
    since = int(STATE.last_stop.get("seq", 0))     # the stops this call numbers come after it
    refused = preflight(steps, ops, serial=session.launch.input_port is not None)
    if refused:
        first = refused[0]
        return st.reply(status="INVALID", code="bad_argument", ran=[], completed=0,
                        failed_at=first["step"], failed=first, errors=refused,
                        message=f"{len(refused)} step(s) refused before anything ran: "
                                + "; ".join(f"step {e['step']} ({e['op']!r}) {e['message']}"
                                            for e in refused)
                                + ". Nothing was run")
    ran: list[dict[str, Any]] = []
    running = False
    released_last = False     # the LAST step is the one that let the machine run
    trap_of_run_to = False    # a `run_to` that ran off leaves its own breakpoint armed
    came_to_rest = False      # the LAST step found the released machine stopped
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or "op" not in step:
            return st.reply(status="INVALID", code="bad_argument",
                          **account_of(ran, summaries, keep_last=False, since=since),
                          completed=len(ran), failed_at=i,
                          message=f"step {i} is not a {{'op': <name>, ...}} object: {step!r}")
        op = str(step["op"])
        args = {k: v for k, v in step.items() if k != "op"}
        if op in DEFERRED_OPS:
            return st.reply(status="INVALID", code="bad_argument",
                          **account_of(ran, summaries, keep_last=False, since=since),
                          completed=len(ran), failed_at=i,
                          message=f"the step {op!r} is not built yet: its route is under "
                                 f"design, so a sequence cannot use it. See the driver "
                                 f"design plan")
        if op not in ops:
            return st.reply(status="INVALID", code="bad_argument",
                          **account_of(ran, summaries, keep_last=False, since=since),
                          completed=len(ran), failed_at=i,
                          message=f"{op!r} is not a step: the vocabulary is the server's own "
                                 f"operation names, {sorted(ops)}")
        # DECISION 37: a console op needs a stopped machine. If the previous step left it
        # running, wait for the stop a breakpoint or the guest will produce -- or find the
        # emulator gone, which is a DIFFERENT answer from "still running".
        if running and op not in RUNNING_OK_OPS:
            state = _wait_for_stop(session, wait, progress)
            if state == "gone":
                return st.reply(status="INVALID", code="session_broken",
                              **account_of(ran, summaries, keep_last=True, since=since),
                              completed=len(ran), failed_at=i,
                              message=f"the emulator is GONE (its bound expired or it "
                                     f"crashed) before the console step {op!r} could run")
            if state == "running":
                return st.reply(status="INVALID", code="not_stopped",
                              **account_of(ran, summaries, keep_last=True, since=since),
                              completed=len(ran), failed_at=i,
                              message=f"the machine was still running {wait}s after the "
                                     f"previous step, so the console step {op!r} cannot be "
                                     f"sent (it would be swallowed). A breakpoint or watch "
                                     f"has to stop it first")
            running = False
        reply = ops[op](**args)      # its arguments were bound up front, before any step ran
        if reply.get("status") != "ok":
            # DECISION 3: stop here. `ran` holds only the steps that SUCCEEDED; the one that
            # stopped the sequence is `failed`, and the machine state rides in `session` --
            # deliberate from inertial is exactly what this keeps separable.
            return st.reply(status="INVALID", code="step_failed",
                          **account_of(ran, summaries, keep_last=False, since=since,
                                       also=[reply]),
                          completed=len(ran), failed_at=i, failed={"op": op, "reply": reply},
                          message=f"step {i} ({op!r}) failed: {reply.get('message')}")
        ran.append({"op": op, "reply": reply})
        # A RUNNING-OK OP DOES NOT RELEASE THE MACHINE, and whether it stopped it is the
        # SESSION's to say, never the op's name: `_leaves_running` would answer False for a
        # `send_keys` after a `resume` and send the next console step into a running guest,
        # while a `stop`, or a breakpoint that fired during a key's `expect`, did stop it.
        if op not in RUNNING_OK_OPS:
            came_to_rest = False
            running = _leaves_running(op, reply)
            released_last = running
            trap_of_run_to = running and op == "run_to"
        else:
            came_to_rest = running and session.at_debugger()
            running = running and not came_to_rest
            released_last = False
    # THE TAIL: if the sequence ends with the machine running, wait for the stop it was
    # heading for and hand back the ENRICHED reply at that stop (decision 13) -- that is the
    # value R1/R3 want, the state AT the breakpoint. If it does not stop in time, say so
    # rather than pretending the run finished at a stop.
    final: dict[str, Any] = {}
    if running and wait == 0:
        final = {"still_running": True,
                 "note": "wait=0: the sequence ended with the machine running and no stop "
                         "was waited for"}
    elif (running and not released_last and not trap_of_run_to
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
        elif last.get("stop_seq") == recorded["stop_seq"] and "registers" in last:
            final = {"stopped": {**recorded, **{k: last[k] for k in _ENRICHED if k in last}}}
        else:
            final = {"stopped": _recorded_stop(session, recorded)}
    elif running:
        state = _wait_for_stop(session, wait, progress)
        if state == "stopped":
            final = {"stopped": _final_stop(session)}
        elif state == "gone":
            final = {"gone": True,
                     "note": "the sequence ended with the machine running and the emulator "
                             "is now GONE (its bound expired or it crashed)"}
        else:
            final = {"still_running": True,
                     "note": f"the sequence ended with the machine running and it did not "
                             f"stop within {wait}s"}
    stopped = final.get("stopped")
    return st.reply(**account_of(ran, summaries, keep_last=True, since=since,
                                 also=[stopped] if isinstance(stopped, dict) else None),
                    completed=len(ran), failed_at=None, **final)


#: What a stop's enriched reply adds to the record of it.
_ENRICHED = ("registers", "watches", "e9", "instruction", "instruction_why")


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
    unavailable while `ran`/`completed` stand. It takes the tool's own fields as **base; the
    tail adds none, so it is called with none: `base={}` would land a literal `base` field."""
    try:
        return guest.stop_reply(session)
    except ds.Invalid as e:
        return {"enrichment": {"available": False, "why": str(e)}}


def _is_stopped(session: ds.Session) -> bool:
    """Whether the machine sits at the debugger: `where()` answers only then and refuses on
    a running guest (the NUDGE it sends is swallowed), which is the discrimination every
    reader here rests on. A gone emulator refuses too, and is not stopped either."""
    try:
        session.where()
    except ds.Invalid:
        return False
    return True


def validate_wait(wait: float) -> None:
    """The bound a sequence waits for a stop, refused when it is not a bound: zero or a
    negative one makes the decision-37 wait give up at once and report a machine that was
    never given the time, and a huge one is not a bound."""
    if isinstance(cast(object, wait), bool) or not isinstance(cast(object, wait), int | float) \
            or not 0 <= wait <= ds.RUN_TO_MAX:
        raise ds.Invalid("bad_argument",
            f"wait is a bound from 0 (never wait) to {ds.RUN_TO_MAX} seconds; "
                         f"got {wait!r}")


def _verify_after_wait(session: ds.Session, expect: str, wait_s: float, mark: int,
                       progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The VERIFY on a running guest: wait up to `wait_s` for a new line since the mark."""
    try:
        reaction = session.e9_wait(expect, wait_s, mark=mark, progress=progress)
    except ds.E9Stopped as e:
        guest.observe_stop(session)
        return {"checked": True, "seen": False, "expected": expect,
                "stopped_during_wait": True, "waited_s": e.waited_s,
                "lines_on_disk": e.arrived, "why": str(e)}
    except ds.E9Expired as e:
        return {"checked": True, "seen": False, "expected": expect,
                "why": f"no new line matching {expect!r} within {wait_s}s. {e}"}
    except ds.Invalid as e:
        return {"checked": False, "expected": expect, "why": str(e), "code": e.code}
    return inputs.effect_seen(expect, reaction)


def _verify_at_a_stop(session: ds.Session, expect: str, mark: int) -> dict[str, Any]:
    """The VERIFY on a guest stopped at the debugger: one read since the mark, no wait,
    because nothing more will be written until the machine is resumed."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"checked": False, "expected": expect, "why": str(e), "code": e.code}
    hits = [ln for ln in since if ds.compiled(expect).search(ln)]
    if not hits:
        return {"checked": True, "seen": False, "expected": expect,
                "why": f"no line matching {expect!r} since the mark, and the machine is "
                       f"STOPPED at the debugger, so nothing more will be written until it "
                       f"is resumed: waiting would not change the answer"}
    return inputs.effect_seen(expect, {"line": hits[0], "already": True,
                                 "lines_before": since.index(hits[0]), "waited_s": 0.0,
                                 "lines_total": len(hits)})


def _look(session: ds.Session, mark: int, pattern: str, limit: int) -> dict[str, Any]:
    """The LOOK after an act: the guest's lines since the mark matching `pattern`, cut to the
    last `limit`, with the counts that say what was cut, in `log`'s own words. Unavailable is
    said, not hidden."""
    try:
        since = session.e9_since_mark(mark)
    except ds.Invalid as e:
        return {"e9": {"available": False, "why": str(e)}}
    rx = ds.compiled(pattern)
    kept = [ln for ln in since if rx.search(ln)]
    return {"e9": {"available": True, "since_mark": mark, "written": len(since),
                   "lines_total": len(kept), "truncated": len(kept) > limit,
                   "lines": kept[-limit:], "pattern": pattern}}


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
    ran = run_steps(session, act, wait, ops, progress, summaries)
    account = {k: v for k, v in ran.items() if k not in ("status", "session")}
    account.setdefault("failed", None)     # always there, so a reader need not probe for it
    if ran.get("status") != "ok":
        return st.reply(status="INVALID", code="step_failed", act=account,
                      message=f"the act stopped at step {ran.get('failed_at')}: "
                              f"{ran.get('message')}",
                      looked=_look(session, mark, pattern, limit))
    checked: dict[str, Any] = {"checked": False,
                                "why": "no `expect` given; the act's own steps carried "
                                       "whatever verification they asked for"}
    if expect is not None:
        # A GUEST STOPPED AT THE DEBUGGER CANNOT WRITE A LINE. When the act ended at a stop
        # (its tail found one, or no step ever let the machine run), waiting `seconds` for
        # the expectation would burn the bound on a machine that cannot act and then blame
        # the program. So the log is read ONCE from the mark and the verdict says why.
        # WHICH IT IS comes from the act's own tail when it had one, and from the machine
        # otherwise: an act of running-guest steps alone (the usual shape) says nothing
        # about the state, because the executor starts every sequence assuming a stopped
        # machine; asking the position is one console round trip and refuses on a running
        # guest, which is the same stop-detector every reader here trusts.
        if "still_running" in ran or "gone" in ran:
            ended_running = True
        elif "stopped" in ran:
            ended_running = False
        else:
            ended_running = not _is_stopped(session)
        checked = (_verify_after_wait(session, expect, wait_s, mark, progress)
                   if ended_running else _verify_at_a_stop(session, expect, mark))
        if checked.get("seen") is False:
            if checked.get("stopped_during_wait"):
                stop, where = STATE.stop_named(session)
                return st.reply(status="INVALID", code="wait_stopped", act=account,
                              verify=checked, last_stop=stop,
                              looked=_look(session, mark, pattern, limit),
                              message=f"the act ran and the machine STOPPED at the debugger "
                                     f"during the wait{where}, so the guest could not do what "
                                     f"was expected: {checked['why']}")
            return st.reply(status="INVALID", code="wait_expired", act=account, verify=checked,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran but the guest did not do what was expected: "
                                 f"{checked['why']}")
        if not checked.get("checked"):
            # The verify's own refusal names the cause; the act ran, so the reply keeps it.
            code: contract.Code = checked.get("code", "unexpected_answer")
            return st.reply(status="INVALID", code=code, act=account, verify=checked,
                          looked=_look(session, mark, pattern, limit),
                          message=f"the act ran and its effect could NOT be verified: "
                                 f"{checked['why']}")
    return st.reply(act=account, verify=checked, looked=_look(session, mark, pattern, limit))
