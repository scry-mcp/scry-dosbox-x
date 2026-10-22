"""THE MCP BOUNDARY of the DOSBox-X server: the protocol's server object and its `instructions`,
the one lock over the one machine, and this server's part of the call boundary every Scry server
shares (`scry_core.boundary`): how a body is called and which errors are answers, the end of a
cancelled call, the `session` block and the summary every reply opens with.
`dosbox_x_server.py` holds the tools.

THE SCHEMA'S REFUSAL AND THE PICTURE are `scry_core.envelope`'s, the same on every Scry server;
this server's part is `refusal`, the reply a refused call gets under its lock.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from scry_core import boundary, cancel, envelope, presence, recording, roster
from scry_core import strict_arguments as strict

import dosbox_arming as arming
import dosbox_captures as caps
import dosbox_checks as checks
import dosbox_docs as docs
import dosbox_presence as dpresence
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as st
import dosbox_summaries as one_line
import dosbox_trace as trace
from dosbox_state import STATE


def refusal(name: str, arguments: dict[str, Any], cause: ValidationError) -> dict[str, Any]:
    """The refusal's reply, built over the ONE machine like every other reply.

    It is built under the lock (`BOUNDARY.refused`) because `st.reply` is not a read: it hands
    over and CLEARS `applied_last` (what a stop applied of the declarations queued while the
    guest ran) and `found_stop_last` (a stop the guest reached on its own), and unlocked a
    refused call could take either away from the call building the reply meant to carry it.
    No tool here dispatches through `call_tool`, so nothing on this path already holds the
    lock.
    """
    return BOUNDARY.refused(name, arguments, lambda: st.reply(
        status="INVALID", code="bad_argument", message=strict.schema_refusal(cause)))


# THE NAME IT REPORTS MUST BE THE NAME IT IS INSTALLED AS, which is also what
# namespaces its tools. It is `dosbox-x` and not `dosbox`: DOSBox and DOSBox-X are
# different emulators, and the debugger, the config properties and most of this
# surface are the X's, so the short name would promise what this does not do.
# THE SERVER'S OWN `instructions` (below, on `mcp`) are the documented channel for what a
# client should know first, delivered by the protocol rather than pasted by a hook.
#: What a refusal for a running guest names as answering: the sequence's table, and five
#: that answer it outside a list (the last stop's registers, the two that run steps, the
#: export of the session, the session's end).
_ANSWERS_WHILE_RUNNING = roster.answers_while_running(
    sequence.RUNNING_OK_OPS, checks.NOT_STEPS, {"start", "build_check"})


#: THE TOOLS BY FAMILY, in the order the instructions list them (`scry_core.roster`): the
#: roster and the "answers while it runs" sentence are both rendered from it, so a family that
#: answers whole is named once instead of tool by tool.
ROSTER = roster.Roster(families=(
    ("Session", ("build_check", "start", "status", "close")),
    ("Read", ("registers", "read_memory", "disassemble", "call_stack", "memdump", "find",
                  "log", "log_wait", "machine_map", "interrupt_vectors", "palette",
                  "screen_view", "screen_signature", "map_add", "map_find", "debug")),
    ("Scan", ("scan_start", "scan_filter", "scan_clear")),
    ("Write", ("set_register", "write")),
    ("Advance", ("run_to", "run_for", "trace", "screen_wait", "step", "resume", "stop")),
    ("Declarations", ("breakpoint_at", "breakpoint_list", "breakpoint_clear",
                                         "breakpoint_interrupt", "watch_add", "watch_list",
                                         "watch_clear")),
    ("States", ("state_save", "state_load", "state_list")),
    ("Names", ("symbols_load", "symbols_find")),
    ("Comments", ("comment_add", "comment_list", "comment_delete", "comment_save",
                      "comment_load")),
    ("Input", ("send_keys", "send_mouse", "drive")),
    ("Captures", ("captures", "capture_frame", "series_capture", "snapshot")),
    ("Files", ("image_diff", "series_diff", "region_track", "golden_check",
                              "map_load", "map_save")),
    ("Lists", ("perform", "perform_export")),
), answering=tuple(_ANSWERS_WHILE_RUNNING))


mcp = envelope.Envelope(
    "dosbox-x",
    instructions=(
        'A live DOS machine in DOSBox-X.\n\n'
        'TOOLS. ' + ROSTER.text() + '\n\n'
        'A SESSION. `build_check` answers about the BUILD and REFUSES while a session is live.\n'
        '`start` parks it STOPPED at the debugger; `resume` lets it RUN, and readers refuse\n'
        '(`not_stopped`, naming `last_stop`); ' + ROSTER.running_sentence() + '\nIt stops at a '
        'breakpoint armed BEFORE the release '
        'or at `stop`. What you\n'
        'declare while it runs is `pending` until the next stop. After `symbols_load`, a `ref`\n'
        'is a symbol or a `SEG:OFF`. A cancel ends a call as its bound would; the next reply\n'
        'says `cancelled`.\n'
        'FOR A VALUE: `registers`, `read_memory`, `memdump`, `log`; `debug` last.\n\n'
        'EVERY REPLY carries `summary`, `status` (`ok`, or `INVALID` with `code` and `message`)\n'
        "and `session` (`altered` after a write). A wrong TYPE is the schema's `bad_argument`.\n\n"
        'Reference: REFERENCE.md.'
    ),
    refusal=refusal,
)

# ONE machine, one session. The lock serialises the tools rather than letting two
# questions interleave on a terminal that has no notion of them being separate. The
# session itself, and everything held beside it, is `STATE` (`dosbox_state`).
LOCK = boundary.ServerLock()


def registered_tools() -> list[str]:
    """The names the MCP layer will actually serve, ASKED OF THE MCP LAYER.

    It reads the server's own registry rather than a list this module keeps beside
    it. MEASURED: `mcp.tool()` returns the function unchanged, so deleting the
    registration leaves every ordinary test green while the server exposes NOTHING --
    and a parallel list maintained here is populated on the way past whether or not
    the registration happened, so asserting against it caught that defect not at
    all. A second source of truth for "what exists" cannot gate the first.

    It reaches through a private attribute, deliberately: there is no synchronous
    public accessor, and a test pins this so a library change fails loudly here
    instead of silently emptying the surface.
    """
    return sorted(t.name for t in strict.registered(mcp))


def _end_cancelled(name: str, on_cancel: cancel.OnCancel
                   ) -> tuple[cancel.Left, dict[str, Any] | None]:
    """THE END A CANCELLED CALL DECLARED, applied at once: the end its own bound would have given
    it, under the shield so that end's own waits run to completion. `stop` for a tool that comes
    back STOPPED (`BREAK` and the stop recorded, as the `stop` tool does; a guest already at the
    debugger is left so; a CPU log still open closed first), `kill` for one whose failure path
    ends the emulator, `none` for one that leaves the machine as it was. Returned: what it
    left, and its stop's reply, whose accounts go back for the next reply (`_keep_accounts`)."""
    left: cancel.Left | None = None
    stopped: dict[str, Any] | None = None
    ses = STATE.session
    with cancel.shielded():
        try:
            if on_cancel == "kill" and ses is not None:
                ses.close()
                if getattr(ses, "reap_failed", None):
                    left = "unknown"
                STATE.session = None
                STATE.forget_symbols()
                STATE.clear_running_state()
            elif on_cancel == "stop" and ses is not None and ses.alive():
                if STATE.log_open:
                    # CLOSED BEFORE THE STOP IS RECORDED: the close is a release and a return to
                    # the prompt of its own, which recorded after it the next contact would find
                    # as a stop nobody made.
                    if not ses.at_debugger():
                        ses.break_in()
                    trace.close_log_left_open(ses)
                stopped = _stop_of_its_own(ses)
        except (ds.Invalid, OSError):
            left = "unknown"
        if left is None:
            ses = STATE.session
            left = ("closed" if ses is None or not ses.alive()
                    else "stopped" if ses.at_debugger() else "running")
    return left, stopped or None


def _stop_of_its_own(ses: ds.Session) -> dict[str, Any]:
    """The `stop` end's stop, its reply: a running guest is brought back with `BREAK`, as the
    `stop` tool does, and one already at a stop nobody has read (the call's own retrace or
    breakpoint) has that stop recorded as the call's, as its bound's refusal records it."""
    if not ses.at_debugger():
        ses.break_in()
        return running.stop_reply(ses, interrupted=True, via="break")
    if getattr(ses, "stop_count", None) != STATE.last_stop.get("stop_count"):
        return running.stop_or_base(ses, True, {})
    return {}


def _keep_accounts(reply: dict[str, Any]) -> None:
    """THE ACCOUNTS A REPLY CARRIED GO BACK FOR THE NEXT ONE: the reply goes to nobody (the
    `stop` end's stop, or a call cancelled as its body returned), and what it applied or found
    is said once, by whichever reply comes next."""
    if reply.get("applied_on_stop"):
        arming.merge_applied(reply["applied_on_stop"])
    if reply.get("stopped_on_its_own"):
        STATE.found_stop_last = dict(reply["stopped_on_its_own"])


def _invoke(fn: Callable[..., Any], called: inspect.BoundArguments) -> dict[str, Any]:
    """The body called once what needs no machine is judged, and only `NotStopped` and
    `Invalid` translated into replies. Widening this to `Exception` would turn every genuine
    bug (an `AttributeError`, a bad regex, a timeout) into "I examined nothing", a broken
    instrument reporting itself as a clean one; the escapes are handled where they happen."""
    given = dict(called.arguments)
    given.pop("ctx", None)
    try:
        # WHAT THE MACHINE IS NOT NEEDED FOR IS JUDGED FIRST: a refusal a caller can see
        # without a session.
        checks.check(fn.__name__, **given)
        reply: dict[str, Any] = fn(*called.args, **called.kwargs)
        caps.note_written(fn.__name__, reply)
        return reply
    except ds.NotStopped as e:
        # THE GUEST RUNS AND THIS READER CANNOT ANSWER: say where the machine was last seen and
        # which readers do answer now, so the caller can decide without provoking a stop (the
        # running-guest contract).
        return st.reply(**e.reply(last_stop=STATE.dated(),
                                  answers_while_running=_ANSWERS_WHILE_RUNNING))
    except ds.Invalid as e:
        return st.reply(**e.reply())


def _keep_cancelled(record: cancel.Cancelled) -> None:
    STATE.cancelled = record


def _machine() -> recording.Machine:
    """The machine around a recorded call: whether the guest runs, and how many times the
    session has come back to the prompt, which every stop moves the moment the prompt shows (a
    parked `state_load` included, before any survey records it), so a call is judged by what it
    did and not by a record that catches up later. A session that died is unreadable."""
    ses = STATE.session
    if ses is None:
        return recording.Machine(running=False, seq=None)
    if not ses.alive():
        return recording.UNREAD
    # THE FLAG, NEVER THE PEEK: a peek after a releasing step of a sequence would consume the
    # prompt the step's own wait listens for (`Session.parked`).
    return recording.Machine(running=not ses.parked, seq=getattr(ses, "stop_count", None))


#: The session's recording: what `perform_export` writes (REFERENCE.md, From an investigation to
#: a bench). `start`'s `plan` runs steps of a sequence, recorded after the start.
# `live` is what `start` refuses over: a start refused there touched nothing.
#: Each kind of declaration a `start` re-arms, by the tool that lists it and the field its rows
#: are under (an interrupt is a breakpoint's row).
_LISTS = {"breakpoint": ("breakpoint_list", "breakpoints"),
          "interrupt": ("breakpoint_list", "breakpoints"), "watch": ("watch_list", "watches")}


RECORDER = recording.Recorder("dosbox-x", "dosbox_x_server.py", sequence.RECORD_MAX, _machine,
                              lambda: STATE.session is not None and STATE.session.alive(),
                              declarations=lambda: arming.current_store().declarations(),
                              kinds=_LISTS,
                              stop_fields=("regs",),
                              outside=checks.NOT_STEPS - checks.SEQUENCES - {"start"},
                              sequences=checks.SEQUENCES, start_tool="start",
                              states=("state_save", "state_load", "name"), plan="plan",
                              plan_with=("settle_seconds",))

def _session_presence() -> presence.Presence | None:
    """The live session's presence writer, if it has one."""
    return dpresence.of(STATE.session).held


# THE HOOKS ARE BOUND HERE, ONCE, AT IMPORT: a test that replaces one patches the name the hook
# calls through (`STATE`, `running`), never the hook itself, which the boundary already holds.
BOUNDARY = boundary.Boundary(
    mcp, LOCK, invoke=_invoke, end=_end_cancelled, refusal_line=one_line.refusal,
    session_block=st.session_block, take_cancelled=STATE.take_cancelled,
    keep_cancelled=_keep_cancelled, doc=docs.filled, give_back=_keep_accounts,
    recorder=RECORDER,
    # PRESENCE hears every outermost call, so the window lights while one drives the machine.
    listener=presence.Slot(_session_presence))


def tool(
    title: str, *, summary: one_line.Summary, read_only: bool = False, idempotent: bool = False,
    session_before: bool = False, on_cancel: cancel.OnCancel | None = None,
    replay: recording.ExportAs | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an MCP tool on this server's boundary (`scry_core.boundary.Boundary.tool`, the
    contract), `summary` its line in `dosbox_summaries`; `on_cancel` ends at `_end_cancelled`,
    and which errors become replies is `_invoke`'s.

    A reader here also declares what changes what the server holds (`symbols_load`, a
    declaration) as not read-only. ONE CAVEAT, decided by the owner: the first contact after a
    stop applies what was DECLARED while the guest ran (`running.drain_if_stopped`), so a reader
    can be the call that arms a breakpoint. That write belongs to the declaring call, which was
    not read-only and said `pending`; the reader only delivers it, and its reply says so in
    `applied_on_stop`. No tool here is idempotent: each reads a machine that moves or a file that
    may change.
    """

    return BOUNDARY.tool(title, summary=summary, read_only=read_only, idempotent=idempotent,
                         session_before=session_before, on_cancel=on_cancel, replay=replay)
