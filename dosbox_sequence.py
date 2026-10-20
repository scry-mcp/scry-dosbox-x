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

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import reply_contract as contract
from scry_core import sequence as executor
from scry_core import sequence_account as account
from scry_core import steps as step_judge

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
#: How long a step waits for a stop by default, in `perform`, `drive` and `start`'s plan.
SETTLE_DEFAULT_S = 30.0

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
                   progress: ds.Progress = ds.no_progress) -> executor.Waited:
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
        refusal, args = step_judge.judge(ops[op], step)
        if refusal is not None:
            refused.append({"step": i, "op": op, **refusal})
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


class _Dosbox(executor.SequenceMachine):
    """This server's half of a list (`scry_core.sequence`): a stop heard by the debugger's
    prompt, a list that begins on a machine taken as stopped, a step's own missed wait, and the
    stop a step that answers on a running guest came to rest at."""

    undeclared = "no breakpoint, no interrupt breakpoint, no change watch"

    def __init__(self, session: ds.Session, summaries: bool) -> None:
        self.session, self.summaries = session, summaries
        self.since = int(STATE.last_stop.get("seq", 0))  # the stops this list numbers follow it

    def answers_running(self, op: str, args: dict[str, Any]) -> bool:
        return answers_running(op, args)

    def running(self) -> bool:
        return not self.session.at_debugger()

    def began_running(self) -> bool:
        # EVERY LIST BEGINS AS ON A STOPPED MACHINE: a step that needs one and finds the guest
        # running answers so itself, and an act of keys sent to a running guest (`drive`'s
        # usual shape) must not wait for a stop it never asked for.
        return False

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
        """THE STOP CAME DURING THE LAST STEP (a `stop`, or a breakpoint that fired while a
        declaration or a key went in): it is the stop the run was heading for. One a step already
        surveyed (the `stop` tool's own reply, a step that found it on its own) is named as
        recorded, never surveyed twice: a second survey numbers it again. Its registers, watches
        and E9 come from the step's reply when the step surveyed it, else off the record."""
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
              prechecked: bool = False) -> dict[str, Any]:
    """Execute steps in order (`scry_core.sequence.run`, its rules), STOPPING at the first
    failure with a full account: `ran` (each step and its reply), `failed` (the step that stopped
    it, absent when none did), `steps_completed`, `held` (the steps whose `recorded` answer this
    run matched), and the machine state. A step is `{"op": <name>, ...args}`. `prechecked` when
    the tool's pre-gate already judged the list whole (`dosbox_checks.steps_whole`), so it is
    judged once a call. With `summaries`, `ran` is the compact account `account_of` builds."""
    validate_summaries(summaries)
    refused = [] if prechecked else preflight(steps, ops)
    if refused:
        first = refused[0]
        return st.reply(status="INVALID", code="bad_argument", ran=[], steps_completed=0,
                        failed_at=first["step"], failed=first, errors=refused,
                        message=refused_text(refused), held=0)
    ended = executor.run(_Dosbox(session, summaries), steps, ops, wait, progress, name)
    if ended.code is not None:
        return st.reply(status="INVALID", code=ended.code, message=ended.message,
                        **ended.fields, held=ended.held)
    return st.reply(**ended.fields, held=ended.held)


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
    """The bound a sequence waits for a stop once it ran: 0 does not wait, and a negative or a
    huge one is not a bound."""
    ds.check_wait_bound(wait, "settle_seconds", from_zero=True)


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
    wait_s = inputs.drive_wait_s(seconds)
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
        # THE ACT'S OWN CODE: a step that failed is `step_failed`, but a list the executor
        # refused (`not_stopped`) or an emulator gone under it (`session_broken`) says so.
        act_code: contract.Code = ran.get("code", "step_failed")
        return st.reply(status="INVALID", code=act_code, act=account,
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
