"""THE MCP BOUNDARY of the DOSBox-X server: the protocol's server object and its `instructions`,
the one lock over the one machine, the summary every reply opens with, the decorator that
registers a tool, and the end of a cancelled call. `dosbox_x_server.py` holds the tools;
what a tool is wrapped in, which is the same for every one of them, is here.

THE SCHEMA'S REFUSAL AND THE PICTURE are `scry_core.envelope`'s, the same on every Scry server;
this server's part is `refusal`, the reply a refused call gets under its lock.
"""

from __future__ import annotations

import functools
import inspect
import threading
import time
from collections.abc import Callable
from typing import Any

from mcp.types import ToolAnnotations
from pydantic import ValidationError
from scry_core import cancel, envelope
from scry_core import strict_arguments as strict

import dosbox_checks as checks
import dosbox_docs as docs
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as st
import dosbox_summaries as one_line
from dosbox_state import STATE


def refusal(name: str, arguments: dict[str, Any], cause: ValidationError) -> dict[str, Any]:
    """The refusal's reply, built over the ONE machine like every other reply.

    THE SEAM SITS OUTSIDE `tool()`'s WRAPPER and so outside the `LOCK` that wrapper
    holds, and `st.reply` is not a read: it hands over and CLEARS `applied_last` (what a
    stop applied of the declarations queued while the guest ran) and `found_stop_last`
    (a stop the guest reached on its own). Unlocked, a call the schema refused could take
    either account away from the call that was building the reply meant to carry it,
    and that stop would be reported to nobody.

    NOTHING ON THIS PATH CAN ALREADY HOLD THE LOCK: the schema refuses BEFORE the tool
    body runs, so this call never reached the wrapper that takes it, and no tool here
    dispatches through `call_tool`. `LOCK` being an `RLock` is not what makes this safe.
    """
    with LOCK:
        reply = st.reply(status="INVALID", code="bad_argument",
                         message=strict.schema_refusal(cause))
        body = _finished(name, arguments, reply)
    return body


# THE NAME IT REPORTS MUST BE THE NAME IT IS INSTALLED AS, which is also what
# namespaces its tools. It is `dosbox-x` and not `dosbox`: DOSBox and DOSBox-X are
# different emulators, and the debugger, the config properties and most of this
# surface are the X's, so the short name would promise what this does not do.
# THE SERVER'S OWN `instructions` (below, on `mcp`) are the documented channel for what a
# client should know first, delivered by the protocol rather than pasted by a hook.
mcp = envelope.Envelope(
    "dosbox-x",
    instructions=(
        'A live DOS machine in DOSBox-X.\n\n'
        'TOOLS. Session: `build_check`, `start`, `status`, `close`. Read: `registers`,\n'
        '`read_memory`, `disassemble`, `call_stack`, `memdump`, `find`, `log`, `log_wait`,\n'
        '`machine_map`, `interrupt_vectors`, `palette`, `screen_view`, `screen_signature`,\n'
        '`debug`. Scan (by value, with no map): `scan_start`, `scan_filter`, `scan_clear`.\n'
        'Write: `set_register`, `write`. Advance: `run_to`, `run_for`, `trace`, `screen_wait`,\n'
        '`step`, `resume`, `stop`. Declarations, kept per conf: `breakpoint_at`,\n'
        '`breakpoint_list`, `breakpoint_clear`, `breakpoint_interrupt`, `watch_add`,\n'
        '`watch_list`, `watch_clear`. States: `state_save`, `state_load`, `state_list`.\n'
        'Names: `symbols_load`,\n'
        '`symbols_find`. Comments: `comment_add`, `comment_list`, `comment_delete`,\n'
        '`comment_save`, `comment_load`. Input, in-guest:\n'
        '`send_keys`, `send_mouse`, `drive`. Captures: `captures`, `capture_frame`,\n'
        '`series_capture`, `snapshot`. Files, any state: `image_diff`, `series_diff`,\n'
        '`region_track`, `golden_check`. Sequences: `perform`.\n\n'
        'A SESSION. `build_check` answers about the BUILD, never a reading, and REFUSES while a\n'
        'session is live. `start` parks the guest STOPPED at the debugger; `resume` lets it\n'
        'run. The readers need it STOPPED and refuse otherwise, naming `last_stop` and what\n'
        'answers; a running guest is reached through `log`, `log_wait`, `send_keys` and\n'
        '`send_mouse`, and stops at a breakpoint armed BEFORE the release\n'
        '(`breakpoint_interrupt` 0x21 real mode, 0x31 ah=2 DJGPP) or at `stop`, headless or\n'
        'windowed. What you declare while\n'
        'it runs is `pending` until the next stop. After `symbols_load`, a `ref` is a symbol or\n'
        'a `SEG:OFF`. A cancel ends a call as its bound would; the next reply says `cancelled`.\n'
        'FOR A VALUE use `registers`, `read_memory`, `memdump` or `log`; `debug` is the last\n'
        'resort.\n\n'
        'EVERY REPLY carries `summary`, `status` (`ok`, or `INVALID` with `code` and `message`)\n'
        'and `session` (`altered`: has anything here written to the machine?). An argument of\n'
        "the wrong TYPE is the schema's `bad_argument`.\n\n"
        'Reference: REFERENCE.md.'
    ),
    refusal=refusal,
)

# ONE machine, one session. The lock serialises the tools rather than letting two
# questions interleave on a terminal that has no notion of them being separate. The
# session itself, and everything held beside it, is `STATE` (`dosbox_state`).
LOCK = threading.RLock()
# HOW DEEP THE CALLS INSIDE THE LOCK ARE NESTED, read and written only while holding it: a
# `perform` calls its steps through their tools, and only the outermost reply is the caller's.
_nested = [0]

#: What a refusal for a running guest names as answering: the sequence's table, and four
#: that answer it outside a list (the last stop's registers, the two that run steps, the
#: session's end).
_ANSWERS_WHILE_RUNNING = [*sorted(sequence.RUNNING_OK_OPS), "registers(from_last_stop=True)",
                          "perform", "drive", "close"]


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
    return sorted(t.name for t in mcp._tool_manager.list_tools())


#: Each registered tool's summary, filled by `tool` as it registers them.
_SUMMARIES: dict[str, one_line.Summary] = {}


def _summary(name: str, args: dict[str, Any], reply: dict[str, Any]) -> str:
    """The one line the MCP client shows for a call (`dosbox_summaries`): the envelope's for a
    reply that is not `ok`, the tool's own otherwise."""
    if reply.get("status") != "ok":
        return one_line.refusal(name, reply)
    return _SUMMARIES[name](args, reply)


def _finished(name: str, args: dict[str, Any], reply: dict[str, Any],
              session_before: bool = False, outer: bool = True) -> dict[str, Any]:
    """The reply a caller reads, closed in ONE place for every path (the decorator's and the
    schema's refusal): `summary` first, the tool's own fields, `session` last.

    THE `session` BLOCK IS COMPOSED HERE, AFTER THE BODY, from the state the server holds, so a
    body that wrote to the machine or released it once its envelope was built cannot hand back a
    block describing the machine before it did. A tool registered with `session_before` keeps
    the block its body built: `close`'s, the state BEFORE the close."""
    body = {k: v for k, v in reply.items() if k != "session"}
    kept = reply.get("session") if session_before else None
    session = kept if kept is not None else st.session_block()
    summary = _summary(name, args, reply)
    # Only the OUTER call's reply carries it: a step of a `perform` is not the reply a caller reads.
    if outer and (record := STATE.take_cancelled()) is not None:
        # WHAT A CANCELLED CALL LEFT, said first by the next reply: the cancelled call had none.
        return {"summary": record.summary(summary), **body, "cancelled": record.note(),
                "session": session}
    return {"summary": summary, **body, "session": session}


def _end_cancelled(name: str, on_cancel: cancel.OnCancel, began: float) -> None:
    """THE END A CANCELLED CALL DECLARED, applied at once: the end its own bound would have given
    it, under the shield so that end's own waits run to completion. `stop` for a tool that comes
    back STOPPED (`BREAK` and the stop recorded, as the `stop` tool does; a guest already at the
    debugger is left so), `kill` for one whose failure path ends the emulator, `none` for one that
    leaves the machine as it was. What it left is recorded for the next reply."""
    left: cancel.Left | None = None
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
                _keep_accounts(_stop_of_its_own(ses))
        except (ds.Invalid, OSError):
            left = "unknown"
        if left is None:
            ses = STATE.session
            left = ("closed" if ses is None or not ses.alive()
                    else "stopped" if ses.at_debugger() else "running")
    STATE.cancelled = cancel.recorded(STATE.cancelled, name, time.monotonic() - began, left)


def _stop_of_its_own(ses: ds.Session) -> dict[str, Any]:
    """The `stop` end's stop, its reply: a running guest is brought back with `BREAK`, as the
    `stop` tool does, and one already at a stop nobody has read (the call's own retrace or
    breakpoint) has that stop recorded as the call's, as its bound's refusal records it."""
    if not ses.at_debugger():
        ses.break_in()
        return running.stop_reply(ses, interrupted=True, how="break")
    if getattr(ses, "stop_count", None) != STATE.last_stop.get("stop_count"):
        return running.stop_or_base(ses, True, "none", ".", None, {})
    return {}


def _keep_accounts(stopped: dict[str, Any]) -> None:
    """THE ACCOUNTS A STOP DELIVERED GO BACK FOR THE NEXT REPLY: the stop's own reply goes to
    nobody, and what it applied or found is said once, by whichever reply comes next."""
    STATE.applied_last.update(stopped.get("applied_on_stop") or {})
    if stopped.get("stopped_on_its_own"):
        STATE.found_stop_last = dict(stopped["stopped_on_its_own"])


def tool(
    title: str, *, summary: one_line.Summary, read_only: bool = False, idempotent: bool = False,
    session_before: bool = False, on_cancel: cancel.OnCancel | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an MCP tool, serialise it over the one machine, and put the one-line
    `summary` first in its reply: `summary` is the tool's own line (`dosbox_summaries`),
    REQUIRED, so a tool registered without one fails at import.

    `title` is what the client shows for the tool, and `read_only` becomes the protocol's
    `readOnlyHint`: a reader declares it so a client may run readers in parallel, which is
    honest here because every tool takes the lock anyway. Anything that advances the
    machine, writes to it, changes what the server holds (`symbols_load`, a declaration)
    or writes a FILE (`memdump`, `capture_frame`) is not read-only. ONE CAVEAT, decided
    by the owner: the first contact after a stop applies what was DECLARED while the
    guest ran (`running.drain_if_stopped`), so a reader can be the call that arms a breakpoint.
    That write belongs to the declaring call, which was not read-only and said
    `pending`; the reader only delivers it, and its reply says so in `applied_on_stop`.

    `idempotent` becomes `idempotentHint`, a STRONGER claim than read-only: calling it again
    changes nothing AND answers the same. Every tool here reads a machine that moves or a file
    that may change, so none declares it; declared wrongly it would invite a
    client to repeat a call whose answer had moved underneath it, so it stays false unless
    the tool's own data cannot change.

    `session_before` keeps the `session` block the body built instead of composing it after
    (`_finished`): only `close`, whose block is the state BEFORE the kill.

    `on_cancel` is how the tool ends when the client cancels its call (`_end_cancelled`), and a
    tool that takes a `ctx`, which is every tool that waits and reports its progress, must
    declare it or fails at import. Any other tool can still meet a cancel in a wait of its own,
    and ends `none`, the machine left as it was.

    A tool that takes a `ctx` (the protocol's `Context`, for the progress line of a bounded
    wait) gets it from the SDK, and it is kept out of the summary's arguments. The summary
    reads the arguments the call RAN with, defaults applied.

    ONLY `Invalid` is translated. Widening this to `Exception` would turn every
    genuine bug -- an `AttributeError`, a bad regex, a timeout -- into "I examined
    nothing", which is a broken instrument reporting itself as a clean one: exactly
    the failure this module is written against. The escapes are handled where they
    happen instead.
    """

    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(fn)
        if "ctx" in signature.parameters and on_cancel is None:
            raise TypeError(f"{fn.__name__} waits and reports its progress, so it declares "
                            "how a cancel ends it (`on_cancel`)")
        _SUMMARIES[fn.__name__] = summary

        @functools.wraps(fn)
        def wrapped(*a: Any, **k: Any) -> Any:
            given = dict(signature.bind_partial(*a, **k).arguments)
            given.pop("ctx", None)
            with LOCK:
                # A CALL CANCELLED WHILE IT WAITED FOR THE LOCK did nothing, so it has no end
                # to apply and nothing to record.
                cancel.check()
                began = time.monotonic()
                _nested[0] += 1
                try:
                    # WHAT THE MACHINE IS NOT NEEDED FOR IS JUDGED FIRST: a refusal a caller
                    # can see without a session.
                    checks.check(fn.__name__, **given)
                    reply = fn(*a, **k)
                except ds.NotStopped as e:
                    # THE GUEST RUNS AND THIS READER CANNOT ANSWER: say where the machine
                    # was last seen and which readers do answer now, so the caller can
                    # decide without provoking a stop (the running-guest contract).
                    reply = st.reply(**e.reply(last_stop=STATE.as_of(),
                                               answers_while_running=_ANSWERS_WHILE_RUNNING))
                except ds.Invalid as e:
                    reply = st.reply(**e.reply())
                except BaseException as e:
                    # A CANCELLED CALL ends as it declared and answers nothing: the request is
                    # gone, so the record waits for the next reply. Anything else is not ours.
                    if cancel.is_cancellation(e):
                        _end_cancelled(fn.__name__, on_cancel or "none", began)
                    raise
                finally:
                    _nested[0] -= 1
                bound = signature.bind_partial(*a, **k)
                bound.apply_defaults()               # a summary reads what the call RAN with
                args = dict(bound.arguments)
                args.pop("ctx", None)
                # Under the lock: the `session` block is read off the one machine's state.
                return _finished(fn.__name__, args, reply, session_before,
                                 outer=_nested[0] == 0)

        wrapped.__doc__ = docs.filled(fn.__name__, fn.__doc__ or "")
        return mcp.tool(title=title,
                        annotations=ToolAnnotations(read_only_hint=read_only,
                                                    idempotent_hint=idempotent))(wrapped)

    return register
