"""The MCP boundary of the DOSBox-X server: server object, `instructions`, the one lock and this
server's hooks into `scry_core.boundary`. `server.py` holds the tools.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from scry_core import boundary, cancel, envelope, presence, recording, roster
from scry_core import strict_arguments as strict

from scry_dosbox_x import arming, checks, docs, folds, running, sequence, trace
from scry_dosbox_x import captures as caps
from scry_dosbox_x import presence as dpresence
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x import summaries as one_line
from scry_dosbox_x.state import STATE


def refusal(name: str, arguments: dict[str, Any], cause: ValidationError) -> dict[str, Any]:
    """The refusal reply, built under the lock because `st.reply` clears `applied_last` and
    `found_stop_last`, which a concurrent call building its own reply must still carry.
    """
    return BOUNDARY.refused(name, arguments, lambda: st.reply(
        status="INVALID", code="bad_argument", message=strict.schema_refusal(cause)))


#: What a refusal for a running guest names as answering.
_ANSWERS_WHILE_RUNNING = roster.answers_while_running(
    sequence.GATE.listed(folds.METHODS), checks.NOT_STEPS,
    {"start", "build_check"})


#: The tools by family, in the order the instructions list them.
ROSTER = roster.Roster(families=(
    ("Session", ("build_check", "start", "status", "window", "close")),
    ("Machine", ("machine_map", "interrupt_vectors", "log", "log_wait")),
    ("Read", ("registers", "read_memory", "disassemble", "call_stack", "memdump", "find",
              "screen_map_find", "screen_map_write")),
    ("Screen", ("palette", "screen_view", "screen_signature")),
    ("Scan", ("scan",)),
    ("Write", ("set_register", "write", "debug")),
    ("Hardware", ("port", "pic", "a20")),
    ("Advance", ("run_to", "run_for", "trace", "screen_wait", "step", "resume", "wait",
                 "stop")),
    ("Declarations", ("breakpoint_at", "breakpoint_interrupt", "regpoint_add", "watch_add",
                      "declaration_list", "declaration_clear")),
    ("States", ("state_list", "state_write")),
    ("Names", ("symbols_load", "symbols_find")),
    ("Comments", ("comment_list", "comment_write")),
    ("Input", ("send_keys", "send_mouse")),
    ("Captures", ("captures", "capture_frame", "series_capture", "snapshot", "record",
                  "audio_record")),
    ("Files", ("image_compare", "audio_compare", "guest_file")),
    ("Lists", ("perform", "perform_export", "drive")),
    ("Store", ("promote",)),
), answering=tuple(_ANSWERS_WHILE_RUNNING))


# `dosbox-x`, not `dosbox`: a different emulator, and the name namespaces the tools.
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
        'declare while it runs is `pending` until the next stop (a count, capture or freeze is\n'
        'declared at a stop, and acts as it runs). After `symbols_load`, a `ref`\n'
        'is a symbol or a `SEG:OFF`. A cancel ends a call as its bound would; the next reply\n'
        'says `cancelled`.\n'
        'FOR A VALUE: `registers`, `read_memory`, `memdump`, `log`; `debug` last.\n\n'
        'EVERY REPLY carries `summary`, `status` (`ok`, or `INVALID` with `code` and `message`)\n'
        "and `session` (`altered` after a write); a diagnostic left out is empty, and\n"
        "`omitted` names what was not sent.\n"
        "A wrong TYPE is the schema's `bad_argument`.\n\n"
        'Reference: REFERENCE.md.'
    ),
    refusal=refusal,
)

# One machine: the lock keeps two questions from interleaving on its debugger.
LOCK = boundary.ServerLock()


def registered_tools() -> list[str]:
    """The names the MCP layer serves, read from its registry.

    Reaches a private attribute on purpose (no public synchronous accessor); a test pins it.
    """
    return sorted(t.name for t in strict.registered(mcp))


def _end_cancelled(name: str, on_cancel: cancel.OnCancel
                   ) -> tuple[cancel.Left, dict[str, Any] | None]:
    """Apply at once the end a cancelled call declared, under the shield: `stop` brings the
    guest back STOPPED, `kill` ends the emulator, `none` leaves it. Returns what it left and
    its stop's reply, whose accounts go back for the next reply."""
    left: cancel.Left | None = None
    stopped: dict[str, Any] | None = None
    ses = STATE.session
    with cancel.shielded():
        try:
            if on_cancel == "kill" and ses is not None:
                ses.close()
                if ses.reap_failed:
                    left = "unknown"
                STATE.session = None
                STATE.forget_symbols()
                STATE.clear_running_state()
            elif on_cancel == "stop" and ses is not None and ses.alive():
                broke_in = False
                if STATE.log_open:
                    # Closed before the stop is recorded: the close is itself a release and a
                    # stop, which would read as a stop nobody made.
                    if not ses.at_debugger():
                        ses.break_in()
                        broke_in = True
                    trace.close_log_left_open(ses)
                stopped = _stop_of_its_own(ses, broke_in)
        except (ds.Invalid, OSError):
            left = "unknown"
        if left is None:
            ses = STATE.session
            left = ("closed" if ses is None or not ses.alive()
                    else "stopped" if ses.at_debugger() else "running")
    return left, stopped or None


def _stop_of_its_own(ses: ds.Session, broke_in: bool = False) -> dict[str, Any]:
    """The `stop` end's reply: `BREAK` a running guest; record an unread stop as the call's."""
    if broke_in or not ses.at_debugger():
        if not broke_in:
            ses.break_in()
        try:
            return running.stop_reply(ses, interrupted=True, via="break", asked_by="cancel")
        except ds.Invalid as e:
            # A survey cut after the placement was made: the stop stands and says it.
            if not running.placement_of(e):
                raise
            return running.unavailable_enrichment(e)
    if ses.stop_count != STATE.last_stop.get("stop_count"):
        return running.stop_or_base(ses, True, {}, asked_by="cancel")
    return {}


def _keep_accounts(reply: dict[str, Any]) -> None:
    """Return a dropped reply's accounts to the next reply."""
    if reply.get("applied_on_stop"):
        arming.merge_applied(reply["applied_on_stop"])
    if reply.get("stopped_on_its_own"):
        STATE.found_stop_last = dict(reply["stopped_on_its_own"])


def _invoke(fn: Callable[..., Any], called: inspect.BoundArguments) -> dict[str, Any]:
    """Call the body, translating only `NotStopped` and `Invalid`: widening to `Exception`
    would report a genuine bug as "I examined nothing"."""
    given = dict(called.arguments)
    given.pop("ctx", None)
    try:
        checks.check(fn.__name__, **given)
        reply: dict[str, Any] = fn(*called.args, **called.kwargs)
        caps.note_written(fn.__name__, reply)
        return reply
    except ds.NotStopped as e:
        return st.reply(**e.reply(last_stop=STATE.dated(),
                                  answers_while_running=_ANSWERS_WHILE_RUNNING))
    except ds.Invalid as e:
        return st.reply(**e.reply())


def _keep_cancelled(record: cancel.Cancelled) -> None:
    STATE.cancelled = record


def _machine() -> recording.Machine:
    """Whether the guest runs and how many times the session has come back to the debugger."""
    ses = STATE.session
    if ses is None:
        return recording.Machine(running=False, seq=None)
    if not ses.alive():
        return recording.UNREAD
    # The flag, never a question to the debugger: recording a call must not cost a round trip.
    # A parked machine's last `RUNSTATE` is its stop's, so its frame is that stop's.
    return recording.Machine(running=not ses.parked, seq=ses.stop_count,
                             frame=getattr(ses, "frames", None) if ses.parked else None)


#: Each declaration kind a `start` re-arms: the tool that lists it and the field of its rows.
_LISTS = {"breakpoint": ("declaration_list", "breakpoints"),
          "interrupt": ("declaration_list", "breakpoints"),
          "regpoint": ("declaration_list", "regpoints"),
          "watch": ("declaration_list", "watches")}


RECORDER = recording.Recorder("dosbox-x", "scry_dosbox_x.server", sequence.RECORD_MAX, _machine,
                              lambda: STATE.session is not None and STATE.session.alive(),
                              declarations=lambda: arming.current_store().declarations(),
                              kinds=_LISTS,
                              stop_fields=("regs", "frame"),
                              outside=checks.NOT_STEPS - checks.SEQUENCES - {"start"},
                              sequences=checks.SEQUENCES, start_tool="start",
                              states=recording.States("state_write", "save", "load", "name"),
                              plan="plan",
                              plan_with=("settle_seconds",))

def _session_presence() -> presence.Presence | None:
    """The live session's presence writer, if it has one."""
    return dpresence.of(STATE.session).held


# Bound once at import: tests patch the names the hooks call through, never the hooks.
BOUNDARY = boundary.Boundary(
    mcp, LOCK, invoke=_invoke, end=_end_cancelled, refusal_line=one_line.refusal,
    session_block=st.session_block, take_cancelled=STATE.take_cancelled,
    keep_cancelled=_keep_cancelled, doc=docs.filled, give_back=_keep_accounts,
    recorder=RECORDER,
    listener=presence.Slot(_session_presence))


def tool(
    title: str, *, summary: one_line.Summary, read_only: bool = False, idempotent: bool = False,
    body_session: bool = False, on_cancel: cancel.OnCancel | None = None,
    replay: recording.Replay | None = None, names_file: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an MCP tool on this server's boundary (`scry_core.boundary.Boundary.tool`).

    A reader that changes what the server holds is declared not read-only. The first contact
    after a stop applies declarations queued while the guest ran, so a reader can deliver that
    write; its reply says so in `applied_on_stop`. No tool here is idempotent.
    """

    return BOUNDARY.tool(title, summary=summary, read_only=read_only, idempotent=idempotent,
                         body_session=body_session, on_cancel=on_cancel, replay=replay,
                         names_file=names_file)
