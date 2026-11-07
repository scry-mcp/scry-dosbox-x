"""MCP server owning one live DOSBox-X session, so a question costs milliseconds.

WHY AN MCP AND NOT A SCRIPT.  The expensive part is never the question, it is the state:
each shell command is a fresh process, so the emulator dies between one question and the
next and every follow-up pays another boot.  Held open here, the state is reached once, a
question to the debugger costs its round trip on the debugger channel, and one that never
asks it (`log`, `status`) costs nearly nothing.  What a question costs is measured when a
decision needs it, and the measure lives in the commit that took it: a tool's cost is the
number of requests it sends, each answered whole before the next goes.

WHAT IT DELIBERATELY DOES NOT DO.  A golden, or any byte-for-byte comparison, stays
in a batch run: a batch replays from power-on, so its frames are the same in every
run, and a live session's frame depends on every question asked before it.  That is
not a gap to be closed later, it is the reason both exist.

SAVE STATES.  The state tools (`state_write(method="save")`, `state_write(method="load")`) are the
debugger's own SAVESTATE
and LOADSTATE, sent down the debugger channel to a build that carries both; `state_list`
reads the directory.  The other ways in are no tools, each for its reason: a config's
`autosave=<interval> <slot>` writes on a timer the caller does not choose; loading through
the emulator is a MAPPER action, a HOST key to a window in front, and this server posts no
host keys; `-loadstate` is not an option the build has (an unknown option starts the
emulator, so it seems to hang); `forceloadstate` overrides a version or program mismatch on
load, it triggers nothing.

`RUNWATCH` SHIPS NO TOOL.  The debugger has it (`debug_running = true; DEBUG_DrawScreen();`
-- resume the machine while going on painting its state), and it is the obvious way to watch
a program move, but it is a HOSE: it resumes and repaints without pause, far past a settle
window, and sending `RUNWATCH` a second time does NOT turn it off, so the session is lost.
A tool with no way back leaves the caller holding a wedged session, which is worse than not
having it.  Anyone picking this up again needs to find the OFF
switch FIRST.  The tools that do ship stop the machine deliberately (`run_to`), step it
one instruction at a time (`step`), or arm a watch and leave it stopped (`watch`). `run_to`,
`run_for`, `trace` and `screen_wait` interrupt at their bound and always hand the debugger back;
`resume`'s bound leaves the machine running, and its reply says so.  The difference from
`RUNWATCH` is that the state is REPORTED and the session is still usable.

HONESTY, wired into the contract rather than into a prompt:

- `start` refuses a session it cannot reproduce -- an unreadable config or working
  directory, `flags` DOSBox-X would hang on, a session with no bound or
  with one so large it bounds nothing -- and refuses it BEFORE the process exists.
  When a session comes up but never reaches its debugger, it is CLOSED before the
  refusal is returned: a guarantee that leaves alive what it just declared invalid is
  not a guarantee.
- A read that found nothing says WHICH nothing.  "No line matched" is an answer;
  "there is no instrumentation to match against" is INVALID, and a caller that cannot
  tell them apart reports a broken instrument as a clean result.
- EVERY reply carries the session's state, `altered` included -- the INVALID ones
  too (whole on `start`, `status` and `close`, its alarms on the rest).  An INVALID
  answer is the one a caller reasons hardest about, and it is the worst one to hand over
  with no trace that the machine had been written to.
- A PATH A CALLER GIVES IT IS ABSOLUTE OR `~`-LED, judged by scry-core's one judge
  (through `paths`): `~` is expanded, a relative path is refused, and the refusal
  names the argument.

The server knows no project: the conf, the working directory, the program and the
flags all come from the caller (the window, from `display`, `fullscreen` and `size`), so the same
server serves every DOS project.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

from mcp.server.mcpserver import Context
from pydantic import Field
from scry_core import (  # noqa: E402
    fresh,
    given,
    judges,
    log_marks,
    media_tools,
    methods,
    narrowing,
    process_name,
    recording,
    reference,
    reply_schema,
    screen_map,
    signalled_end,
)
from scry_core import presence as scry_presence  # noqa: E402
from scry_core import (
    scan_vocabulary as words,
)
from scry_core import sequence_account as account  # noqa: E402
from scry_core import steps as core_steps  # noqa: E402
from scry_core import strict_arguments as strict  # noqa: E402
from scry_core import vocabulary as vocab
from scry_core import window as core_window  # noqa: E402
from scry_core.progress import bridge  # noqa: E402

from scry_dosbox_x import (
    advance,  # noqa: E402
    arming,  # noqa: E402
    capture_files,  # noqa: E402
    checks,  # noqa: E402
    code,  # noqa: E402
    comments,  # noqa: E402
    folds,  # noqa: E402
    grammar,  # noqa: E402
    hardware,  # noqa: E402
    inputs,  # noqa: E402
    lifecycle,  # noqa: E402
    log_reader,  # noqa: E402
    machine,  # noqa: E402
    media,  # noqa: E402
    paths,  # noqa: E402
    placement,
    recordings,  # noqa: E402
    regpoints,  # noqa: E402
    retrace,  # noqa: E402
    running,  # noqa: E402
    screen,  # noqa: E402
    sequence,  # noqa: E402
    start_symbols,  # noqa: E402
    stepping,  # noqa: E402
    vga,  # noqa: E402
)
from scry_dosbox_x import binary as binaries  # noqa: E402
from scry_dosbox_x import captures as caps  # noqa: E402
from scry_dosbox_x import dac as vgadac  # noqa: E402
from scry_dosbox_x import declarations as dec  # noqa: E402
from scry_dosbox_x import dos_calls as dos_calls_trace  # noqa: E402
from scry_dosbox_x import dump as dumping  # noqa: E402
from scry_dosbox_x import find as finder  # noqa: E402
from scry_dosbox_x import guest_files as guest  # noqa: E402
from scry_dosbox_x import launch as dlaunch  # noqa: E402
from scry_dosbox_x import logs as dlogs  # noqa: E402
from scry_dosbox_x import presence as dpresence  # noqa: E402
from scry_dosbox_x import process as dprocess
from scry_dosbox_x import promote as mpromote  # noqa: E402
from scry_dosbox_x import replies as dosbox_replies  # noqa: E402
from scry_dosbox_x import screen_pens as by_pens  # noqa: E402
from scry_dosbox_x import session as ds  # noqa: E402
from scry_dosbox_x import state as st  # noqa: E402
from scry_dosbox_x import summaries as one_line  # noqa: E402
from scry_dosbox_x import trace as tracing  # noqa: E402
from scry_dosbox_x.mcp import LOCK, RECORDER, ROSTER, registered_tools, tool  # noqa: E402
from scry_dosbox_x.mcp import mcp as mcp  # noqa: E402  (the probe and the clients read `server.mcp`)
from scry_dosbox_x.running import live  # noqa: E402
from scry_dosbox_x.state import STATE  # noqa: E402

# ------------------------------------------------------------------- session: the build

@tool("Check the build", summary=one_line.build_check, read_only=True)
def build_check(binary: str = "") -> dict[str, Any]:
    """Whether a DOSBox-X binary resolves and carries the debugger. Run before `start`; it
    refuses `session_live` while a session is live. `binary`: omitted, `DOSBOX_X_BINARY`, else
    the PATH's `dosbox-x`; a named build that fails is refused.

    Reply: `binary`, `binary_origin`, `version`, `debugger`, `heavy_debug` (`trace` and a freeze
    watch need it), `debugger_commands` (which of {DEBUGGER_COMMANDS} the build's debugger has;
    omitted when none), `debugger_commands_missing` (each one it lacks, with the tools that
    command disables; omitted when none is missing).
    """
    if binary:          # the shape first, as every path's, whatever the session is
        paths.absolute("binary", binary)
    if STATE.session is not None and STATE.session.alive():
        # ANSWERING MEANS A SECOND EMULATOR from the same binary, which `start` refuses for
        # the same reason: two emulators on one machine make every timing on it a measurement
        # of the neighbour. The build does not change while a session is up.
        raise ds.Invalid("session_live",
            "a session is live, and this would start a second emulator: `close` first, or "
            "use the answer this build already gave")
    resolved = binaries.resolve(binary)
    # Judged by the binary's bytes alone: `-helpdebug` lists `-break-start` on a build without the
    # debugger too, and Windows' GUI build prints it to no stream and never exits.
    if not binaries.debugger(resolved.path):
        raise ds.Invalid("host_failed",
            f"{resolved.path} carries no debugger: the binary holds none of the debugger's own "
            f"text. The readers of the machine, the breakpoints, the watches and the symbol "
            f"placement all need it; the guest's log, the captures and the in-guest input do "
            f"not")
    found = binaries.debugger_commands(resolved.path)
    commands: dict[str, Any] = {"debugger_commands": found} if found else {}
    if absent := binaries.debugger_commands_missing(found):
        commands["debugger_commands_missing"] = absent
    return st.reply(**dlaunch.binary_facts(resolved, binaries.VERSION_TIMEOUT_S), debugger=True,
                    heavy_debug=binaries.heavy_debug(resolved.path), **commands,
                    tools=registered_tools())


# ---------------------------------------------------------- session: start, status, close

@tool("Start a DOSBox-X session", summary=one_line.start, on_cancel="kill")
def start(conf: str = "", cwd: str = "",
          session_seconds: Annotated[int, vocab.bounds(1, dlaunch.MAX_SECONDS)] | None = None,
          shared: bool = False, display: int | None = None, fullscreen: bool | None = None,
          size: str | None = None,
          flags: list[str] | None = None,
          break_on_int3: Annotated[bool, Field(description=(
              "Also stop at the guest's own `int 3`, where a program marks a break; the "
              "debugger's first prompt still comes first."))] = False,
          program: str = "",
          logfile: str = "", capture_video: bool = False,
          captures_dir: Annotated[str, Field(description=(
              "Where the emulator writes a capture it takes itself; empty, `capture` under "
              "the working directory."))] = "",
          plan: list[dict[str, Any]] | None = None,
          settle_seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] | None = None,
          input_port: Annotated[int, vocab.bounds(0, dlaunch.INPUT_PORT_MAX)] = 0,
          state_dir: str = "",
          binary: str = "",
          background: Annotated[bool | None, Field(description=(
              "Launch behind, keeping the caller's focus, or in front; omitted it is behind "
              "unless `shared`."))] = None,
          presence: Annotated[bool, Field(description=scry_presence.ARGUMENT)] = True,
          dos_calls: bool = False,
          log_categories: dict[Annotated[str, vocab.enum(dlaunch.LOG_CATEGORIES)],
                               Annotated[str, vocab.enum(dlaunch.LOG_LEVELS)]] | None = None,
          guest_files: list[str] | None = None, symbols: str = "",
          base_from: Annotated[str, vocab.folded(start_symbols.BASE_FROM)] = start_symbols.PROGRAM,
          profile: str = "",
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Open one live DOSBox-X session from your conf, parked at the debugger. Somebody watching
    through a stream (Moonlight) needs `shared=true` and `fullscreen=true`: a pointer does not
    map inside a window.

    Paths are absolute or `~`-led. `cwd`: where the conf's relative paths resolve. `binary`:
    an executable or a `.app` carrying one, which `open` launches (macOS alone): that route
    keeps `cwd` through DOSBox-X's own `sdl working directory` setting, names the bundle in
    `bundle`, and leaves the exit status to launchd, so `close` answers `unavailable` for it.
    `session_seconds`: the lifetime.
    `shared`: watched, in a window; false, headless.
    `profile`: a repository's run recipe (`.scry/start/<name>.json`) or a path to one. Its keys
    are this tool's arguments and fill only what the call does not give; the reply's `profile`
    block names it and what it filled. The store is looked for from the server's directory, then
    `cwd`.
    `display`: the OS's display index for the window, 0 (the main display) when omitted;
    `fullscreen`: the window fills it; `size`: `WIDTHxHEIGHT` of the window in the host's unit,
    else the largest 4:3 window the display's usable area holds. All three need `shared=true` and
    are refused otherwise; `size` is also refused beside `fullscreen`, beyond the usable area
    (naming it) and under an `sdl output` that ignores it; a `display` past the host's count is
    refused naming the count. The server waits for the window to be listed on that display and
    answers `window`; `window` judges the size once the guest runs.
    `flags`: argv tokens, a `-set` value one token. `logfile`: the guest's E9 channel, for `log`,
    `log_wait`, `drive`. `program` runs after autoexec; `capture_video` records it. `plan` runs
    as `perform` does, each wait bounded by `settle_seconds` (default {SETTLE_S}). `input_port`:
    COM1's TCP port, 0 a free one.
    `state_dir`: where `state_write` saves; empty, the session's scratch (gone at `close`).
    `dos_calls`: record every INT 21h for `log(channel="dos")`, up to the build's row cap; the
    server holds the newest {DOS_CALLS_KEPT} calls it has read, `n` staying the file's number.
    `log_categories`: `[log]` category to level, into `logfile`. `guest_files`: host files the
    guest should leave, read by `guest_file` and `close`. `symbols`: a table `symbols_load`
    reads, judged here and placed at the first stop where DOS holds the program its stem names
    (`<stem>.exe`); `base_from` `program` (its load segment) or a register, as `symbols_load`
    measures one, at a protected-mode stop. That stop's reply says `symbols_placed` once
    (`placed`, `path`, `load_segment`, `base`, `loaded`; a placement refused: `placed: false`,
    `code`, `why`); a later `symbols_load` replaces it.

    Refused: a live session, a window that never appears on the asked display
    (`window_not_visible`, the session left live to `window` or `close`), `flags` setting what
    `display`, `fullscreen` or `size` own, `fullscreen` on `sdl output=surface` (it switches the
    video mode and leaves the window off screen), `fullscreen` on a display other than 0
    on macOS (a halted start never reaches full screen there), a bad path or `symbols` table,
    `session_seconds` out of range, `capture_video` without `program`, an `input_port` other than
    0 outside {INPUT_PORT_MIN}-{INPUT_PORT_MAX}, `log_categories` without `logfile`, `dos_calls`
    on a build with no `DOSTRACE`, `guest_files` naming a directory, one file twice or more than
    {GUEST_FILES_MAX}, or a session already live (`session_live`).

    Reply: `pid`, `stub`, `window` (`display`, `bounds`, `onscreen`, `front`, `fullscreen`, with
    `shared`), `input_port`, `declarations` (`rearm`), `dos_calls`, `log_categories`,
    `guest_files` (each when asked for: the trace's path, the categories set, each file as it was
    before the boot), `symbols` (`held`, `base_from`, `checked`), and with a profile `profile`
    (`name`, `file`, `supplied`); with `plan`, these facts sit
    under `start` beside the plan's account. `note` when the conf or `flags` select a dynamic
    cpu core, which
    can pass over code breakpoints: start on `flags=["-set", "cpu core=normal"]`.

    Reference: REFERENCE.md, The session.
    """
    params = dict(locals())
    params.pop("ctx")
    block: dict[str, Any] | None = None
    if profile:
        params, block = lifecycle.with_profile(profile, keys=_PROFILE_KEYS, arguments=params,
                                               given=given.names() or ())
    params.pop("profile")
    # Before the launch: a `plan` runs inside it, and one of its `add` steps names a map by the
    # guest this call starts.
    mpromote.note_start(params)
    reply = lifecycle.start(**params, progress=bridge(ctx), ops=_step_ops)
    if block is not None:
        STATE.drafts.loaded_entry("start", Path(str(block["file"])).stem)
    else:
        STATE.drafts.forget("start")
    if mpromote.keep_start(params, defaults=_START_DEFAULTS):
        reply["kept"] = mpromote.kept_line(STATE.drafts)
    if block is not None:
        reply["profile"] = block
    return reply


#: What a profile may set: `start`'s own arguments, read off its signature so the two cannot
#: drift apart. `profile` is not one of them, and `ctx` is the protocol's.
_PROFILE_KEYS = tuple(name for name in inspect.signature(start).parameters
                      if name not in ("ctx", "profile"))
#: The same, with each argument's default: a recipe keeps what the call decided, not what the
#: tool would have answered on its own.
_START_DEFAULTS = {name: parameter.default
                   for name, parameter in inspect.signature(start).parameters.items()}


@tool("The session's window", summary=core_window.summary)
def window(front: bool = False) -> dict[str, Any]:
    """Where the watched window is on the host, at any time, a running guest included. `front`
    brings it in front of whatever covers it and reads that back.

    Reply: `window` (`display`, the OS's index; `bounds`; `onscreen`; `front`, no other
    application's window covering its centre; `fullscreen`); `size` when the session was started
    with a stated `size`: `asked`, `seen`, which rectangle was `compared` (`client` or
    `outer`), `tolerance_px`, `height_free` and `matches`.

    Refused: no session (`no_session`), a session started without `shared` (`no_channel`), a
    window that never appears or, with `front`, is still covered after the activation
    (`window_not_visible`, naming what was seen; on a `background=true` session it names that as
    what may keep it behind). Without `front` the window is answered wherever the owner put it.

    Reference: REFERENCE.md, The session.
    """
    return lifecycle.window(live(), front)


@tool("Session status", summary=one_line.status, read_only=True)
def status() -> dict[str, Any]:
    """What the session is right now. It records a stop no tool has reported
    (`stopped_on_its_own`) and applies what was queued while the guest ran
    (`applied_on_stop`).

    Reply: `last_stop` (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`) and `pending` (`arm`
    refs, a `disarm` count, `symbols_load`, `base_remeasure`), both unavailable or empty once a
    session has ended; with a session also `presence`, `pid`,
    `conf`, `conf_digest`, `conf_changed_on_disk`, `image_changed_on_disk`, `watched`, `bound_s`,
    `elapsed_s`, `output_bytes_dropped`, `captures`, `state_dir`, `declarations`, `pc` and
    `cpu_mode`;
    `symbols_held` (`path`, `base_from`, `waiting_for`) while a `start` table waits for its
    program, which costs a memory-chain read at every stop. `session` carries `alive`,
    `running`, `altered` and each alarm while it holds.

    Reference: REFERENCE.md, What every reply carries.
    """
    stopped = False
    if STATE.session is not None and STATE.session.alive():
        running.drain_if_stopped(STATE.session)   # `status` asks for no session, but uses one
        stopped = STATE.session.parked            # what the drain's own reading left
    shown: dict[str, Any] = ({} if STATE.session is None
                             else {"presence": lifecycle.presence_shown(STATE.session)})
    return st.reply(**st.process_facts(), last_stop=STATE.dated(),
                    pending=STATE.pending_summary(),
                    **running.status_facts(STATE.session, stopped), **shown)


@tool("Close the session", summary=one_line.close, body_session=True, on_cancel="kill")
def close(detail: bool = False, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """End the session deliberately rather than waiting for its bound.

    Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid` and
    `exit_code`, each an integer, or unavailable with its `why` when no session was running;
    `stdout_tail` and `errorlog_tail` when the end was not a clean `quit`, or with `detail=True`;
    `note` when the output was not read to its end. `guest_files`: each file `start` named, with
    `guest_file`'s `state`. `session` is the block as it is after the close (`alive` and
    `running` false), and `draft` names the candidates the session left waiting for `promote`.
    """
    return mpromote.after_close(STATE.drafts, lifecycle.close(bridge(ctx), detail))


# ------------------------------------------------------------------ the guest's own log

@tool("Read the log", summary=one_line.log, read_only=True)
def log(pattern: str, channel: Annotated[str, vocab.enum(dlogs.LOG_CHANNELS)],
        limit: Annotated[int, vocab.bounds(1, dlogs.LOG_LIMIT_MAX)] = 40,
        labels: bool = False,
        since_mark: Annotated[int, log_marks.SINCE_MARK_BOUND] = 0) -> dict[str, Any]:
    """The session's log, one `channel` (`guest`, `emulator`, `all`, `dos`) filtered by the
    Python regex `pattern`; `limit` keeps the newest matches; `labels=True` adds `labels`, the
    matching lines counted by first word.
    `since_mark` (a byte position, from a `mark`) reads only what follows. Needs a session with
    `logfile`. `dos`, the guest's INT 21h calls and no other interrupt, instead needs a session
    started with `dos_calls`, matches `pattern` against each call's `line` (`#20 08BC:0139 psp
    0x08BC 0x3D open MISSING.TXT -> error 2 file not found`), counts calls where the others count
    lines (the matches among the calls the server holds), and takes no `since_mark` or `labels`;
    past those, `calls_dropped` says how many of the oldest went. Works on a running guest.

    Reply: `channel`, `lines` (not on `dos`), `lines_total`, `truncated`, `labels`, `pattern`,
    `note`; on the DOS channel `calls` instead of `lines` (each `n`, `time_s`, `cpu_mode`,
    `caller`, `psp`, `function`, `name`, `file`, `in`, `out`, `error`, `returned`, `returned_s`,
    `switched`, `line`), and `calls_dropped` (on `dos`, past the calls held). INVALID with `code`:
    no `logfile`, no log yet, no guest instrumentation, `limit` out of range,
    a bad pattern, an unknown channel (`process` is refused by name), a `since_mark` naming no
    position. To wait for a line use `log_wait`.

    Reference: REFERENCE.md, The log.
    """
    if channel == dos_calls_trace.CHANNEL:
        live()
        return dos_calls_trace.log(pattern, limit, since_mark, labels)
    lines, total = live().log(pattern, limit, channel, since_mark)
    reply: dict[str, Any] = dict(pattern=pattern, channel=channel, lines_total=total,
                                 truncated=total > len(lines), lines=lines)
    if labels:
        reply["labels"] = dlogs.label_counts(lines)
    return st.reply(**reply)


@tool("Wait for a log line", summary=one_line.log_wait, read_only=True, on_cancel="none")
def log_wait(pattern: str, channel: Annotated[str, vocab.enum(dlogs.LOG_CHANNELS)],
             seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
             since_mark: Annotated[int, log_marks.SINCE_MARK_BOUND] = 0,
             ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """When a line of `channel` matching `pattern` was logged: at once if the log already holds it,
    else wait up to `seconds`. `channel` and `since_mark` as in `log`. Works on a running guest.

    Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the first match, not on `dos`),
    `call` (on `dos`), `already`, `waited_s`, `lines_before`, `lines_total`, `arrived_during`,
    `lines_examined` (the calls held on `dos`), `calls_dropped` (on `dos`, past the calls held);
    on timeout `verdict` `TIMEOUT`
    with `note`, `arrived_during`, `lines_examined`, `waited_s`. `status: INVALID`: `wait_stopped`
    on a stopped machine whose
    log lacks the line, `session_broken` when the emulator went away; no `logfile`, a bad
    `seconds`, regex, channel or `since_mark` are refused.

    Reference: REFERENCE.md, The log.
    """
    session = live()
    if channel == dos_calls_trace.CHANNEL:
        try:
            return dos_calls_trace.log_wait(session, pattern, seconds, since_mark, bridge(ctx))
        except ds.E9Stopped as e:
            running.observe_stop(session)      # the stop the wait found is recorded and named
            stop, where = STATE.stop_named(session)
            return st.reply(status="INVALID", code=e.code,
                            message=f"{e}. The machine is stopped{where}", pattern=pattern,
                            last_stop=stop)
    if since_mark:
        log_reader.log_file_from(session, since_mark, channel)
    try:
        got = session.log_wait(pattern, seconds, channel, mark=since_mark, progress=bridge(ctx))
        return st.answer({**got, "channel": channel})
    except ds.E9Stopped as e:
        running.observe_stop(session)          # the stop the wait found is recorded and named
        stop, where = STATE.stop_named(session)
        return st.reply(status="INVALID", code=e.code,
                        message=f"{e}. The machine is stopped{where}", pattern=pattern,
                        last_stop=stop)


# --------------------------------------------- readers of a STOPPED machine, and a write



@tool("Read the registers", summary=one_line.registers, read_only=True, replay=("regs",))
def registers(from_last_stop: bool = False) -> dict[str, Any]:
    """The registers at this stop. `from_last_stop=True` returns the registers of the last stop,
    never the current value; refused (`no_stop`) before any stop.

    Reply: `regs` (hex strings), `superseded` (with `from_last_stop`). CR0, CR3 and descriptor
    tables: `machine_map(sections=["control"])`.
    """
    if from_last_stop:
        live()
        if not STATE.last_stop:
            raise ds.Invalid("no_stop", "no stop yet in this session, so there are no last-stop "
                             "registers to hand back")
        return st.reply(regs=st.shown_regs(STATE.last_stop["registers"]), superseded=True,
                        last_stop=STATE.dated())
    return st.reply(regs=st.shown_regs(live().registers()))


@tool("Read memory", summary=one_line.read_memory, read_only=True, replay=("hex",))
def read_memory(ref: str,
                length: Annotated[int, vocab.bounds(1, grammar.READ_BYTES_MAX)] = 16,
                ) -> dict[str, Any]:
    """`length` bytes (1..{READ_MAX}) at `ref`, a symbol or `SEG:OFF` (a bare number is read as a
    symbol).

    Reply: `hex`, `length`, `seg_off`, `ref`; above {READ_MAX} bytes use `memdump`. Needs the
    machine stopped. An absent or ambiguous symbol is refused.
    """
    session = live()                 # `length` is judged by the registry, before the call
    seg, off = placement.read_target(ref, "DS", session)
    data = session.read_bytes(seg, off, length)
    return st.reply(ref=ref, seg_off=st.seg_off(seg, off), length=length, hex=data.hex())


@tool("Disassemble code", summary=one_line.disassemble, read_only=True)
def disassemble(ref: str, length: Annotated[int, vocab.bounds(1, code.LENGTH_MAX)] = 16,
                ) -> dict[str, Any]:
    """Decode `length` bytes from `ref` (a symbol or `SEG:OFF`) as x86, one instruction a line. The
    last is completed unless the segment ends first. A line a comment is placed on ends
    ` // <text>`.

    Reply: `seg_off`, `length`, `code_bits`, `code_bits_from`, `lines`, `flow` (per line:
    `call`, `branch`, `return`, `sequential`, `unknown`), `flow_source`, and with symbols loaded
    `resolved` (direct call/branch targets and memory operands: `line`, `operand`, `seg_off`,
    `addr`, `symbol`, `delta`).

    Refused: `length` out of range or past the end of a 16-bit segment; `memdump`'s refusals
    apply.

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(ref=ref, **code.disassemble(live(), ref, length, comments.notes))


@tool("Guess the call stack", summary=one_line.call_stack, read_only=True)
def call_stack() -> dict[str, Any]:
    """A heuristic chain of the stop's callers, never a verdict: frame pointers walked (`push
    bp`/`mov bp, sp`, `enter`), each return kept only when a call instruction ends there. Row 0
    is the stop.

    Reply: `heuristic`, `code_bits`, `calls` (innermost first: `seg_off`, `addr`, `symbol`,
    `delta`, `via`, `call`, `bp`), `truncated`, `ended_why`. Refused when the registers come
    back without SS, ESP or EBP. A routine with no frame pointer is invisible.

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(**code.call_stack(live()))


@tool("Dump memory to a file", summary=one_line.memdump, replay="drop")
def memdump(ref: str, length: int, dest: str) -> dict[str, Any]:
    """`length` bytes from `ref` (a symbol or `SEG:OFF`) to the new file `dest` (absolute).

    Reply: `ref`, `seg_off`, `length`, `path`, `bytes`. Refused: a dump file already where the
    debugger writes or at `dest`, a `dest` directly in that directory, an absent or ambiguous
    symbol; in protected mode a 16-bit segment, a range past its limit, or no descriptor.
    """
    session = live()
    session.require_stopped("a dump")
    seg, off = placement.read_target(ref, "DS", session)
    dumped = dumping.dump_range(session, seg, off, length, paths.absolute("dest", dest))
    return st.reply(ref=ref, seg_off=st.seg_off(seg, off), length=length, path=str(dumped.path),
                    bytes=dumped.path.stat().st_size)


@tool("Find bytes in memory", summary=one_line.find, read_only=True)
def find(data_hex: str, ref: str, length: int) -> dict[str, Any]:
    """Every address holding `data_hex` (whole hex bytes) in `length` bytes from `ref`; both
    required. `memdump`'s refusals apply. For a value narrowed over time use `scan`.

    Reply: `seg_off`, `length`, `span`, `hits` (`SEG:OFF`, at most {HITS_MAX}, highest kept),
    `hits_total`, `truncated`.
    """
    # THE HEX BEFORE THE MACHINE, which is where `write` already asked it and where this did
    # not: the same argument of the same server answered `bad_argument` through one tool and
    # `no_session` through the other. Whether the bytes are hex is as true with no machine as
    # with one; where `ref` POINTS is not, and that still waits below.
    pattern = finder.check_pattern(data_hex)
    session = live()
    session.require_stopped("a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.find(session, seg, off, length, pattern))


@tool("Value scan", summary=methods.fold_line("scan", folds.SCAN), replay="drop")
def scan(method: Annotated[str, vocab.enum(tuple(folds.SCAN))], ref: str = "",
         length: int | None = None,
         cell_bytes: Annotated[int, vocab.enum(finder.CELL_BYTES)] | None = None,
         operator: Annotated[str, vocab.enum(finder.OPERATORS)] | None = None,
         value: judges.NumberArg | None = None,
         limit: Annotated[int, vocab.bounds(1, words.HITS_MAX)] | None = None,
         ) -> dict[str, Any]:
    """Value scan: find a variable no map names (the debugger's `MEMFIND`). One scan at a time.

    `start`: every cell of `cell_bytes` (little-endian) over `length` bytes from `ref` is a
    candidate. Reply: `seg_off`, `length`, `cell_bytes`, `addr`, `hits_total`.

    `filter`: keep the cells whose content satisfies `operator` (`=` default) against `value`
    (an integer or a `0x` string), or with no `value` against what each held at `start`; none
    left closes the scan. Reply: `operator`, `value`, `iterations`, `closed`, `hits` (the first
    `limit`, default {HITS_DEFAULT}), `hits_total`, `truncated`, `note`.

    `clear`: cancel the open scan. Reply: `cleared`.

    Refused: an argument the method does not take; a scan already open, in the debugger's
    words; a `value` wider than the cell.

    Reference: REFERENCE.md, Reading and writing.
    """
    return methods.dispatch(folds.SCAN, locals())




#: The debugger's commands that write the guest, read in upstream's command parser: memory
#: (`SM`, `SMV`), registers (`SR`), an interrupt taken (`INTT`), a timer IRQ raised at the PIC
#: (`TIMERIRQ`), a state loaded (`LOADSTATE`), a port read or written (`IN*`, `OUT*`: a read can
#: change the device, as reading 3DAh resets the attribute flip-flop), a byte frozen (`FM`), and
#: the BIOS clock (`TIME`, `DATE`: both reset its midnight flag, set or not). Breakpoints and
#: listings write no guest state.
DEBUG_WRITES = frozenset({"SM", "SMV", "SR", "INTT", "TIMERIRQ", "LOADSTATE", "INP", "INB", "INW",
                          "IND", "OUTB", "OUTP", "OUTW", "OUTD", "FM", "TIME", "DATE"})
#: Commands that list with no argument and write with one: the PIC's actions, the A20 gate set.
DEBUG_WRITES_WITH_ARGUMENT = frozenset({"PIC", "A20"})


def debug_writes(command: str) -> bool:
    """Whether `command` writes the guest (`DEBUG_WRITES`, `DEBUG_WRITES_WITH_ARGUMENT`)."""
    words = command.upper().split()
    return bool(words) and (words[0] in DEBUG_WRITES
                            or (words[0] in DEBUG_WRITES_WITH_ARGUMENT and len(words) > 1))


@tool("Raw debugger command", summary=one_line.debug)
def debug(command: str) -> dict[str, Any]:
    """One raw `command` to the debugger; the last resort. For a value use `registers`,
    `read_memory` or `memdump`; for the log `log`.

    Reply: `output` (the last {DEBUG_TEXT_KEEP} characters of what the debugger printed),
    `output_chars`, `clipped`, `command`, `note` (when the debugger did not take the command).

    Refused `bad_argument`: a command that lets the guest run (`RUN`, `VRT`, `RUNWATCH`, `INT`,
    `STEPIN`, the `LOG` family) and a control character.
    """
    session = live()
    session.require_stopped(repr(command))
    # A SCAN COMMAND SENT HERE moves the debugger's own count past the one `scan(method="filter")`
    # keeps, and may open a scan at another width, so both are dropped rather than answered stale.
    if command.strip().upper().startswith(("MEMS", "MEMFIND")):
        STATE.scan_forget()
    # A COMMAND THAT WRITES THE GUEST (`debug_writes`) marks the session as `write` and
    # `set_register` do, before it is sent: what reaches the machine has been written.
    if debug_writes(command):
        session.altered = True
    ok, lines = session.exec(command)
    out = "\n".join(lines)
    note = "" if ok else ("the debugger did not take it: an unknown command, or one it refused "
                          "with the reason it printed")
    return st.reply(command=command, **st.delta(out, st.DEBUG_TEXT_KEEP),
                    **({"note": note} if note else {}))


@tool("Force a register", summary=one_line.set_register)
def set_register(name: str, value: judges.NumberArg) -> dict[str, Any]:
    """Write one register and read it back; marks the session `altered`. Needs the machine
    stopped.

    `name` is a register the debugger's `SR` takes (`eax`, `ax`, `ip`); a negative or too wide
    `value` is refused unsent.

    Reply: `register`, `regs`, `value`, `readback` (both `0x` at the register's width),
    `verified`. INVALID when the registers did not come back.
    """
    number = checks.number("value", value)
    out = live().set_register(name, number)
    bits = ds.READBACK[str(out["register"])][1]
    return st.answer({"value": judges.hex_at_width(number, bits), **out,
                      "regs": st.shown_regs(cast(dict[str, str], out["regs"]))})


@tool("Write memory", summary=one_line.write)
def write(ref: str, data_hex: str) -> dict[str, Any]:
    """Write bytes at a symbol or `SEG:OFF` and read them back. Modifies the machine; needs it
    stopped.

    `data_hex` is whole hex bytes, up to {READ_MAX}. An absent or ambiguous symbol, and a
    real-mode ROM address, are refused unsent.

    Reply: `ref`, `seg_off`, `bytes_written`, `readback`, `verified`.
    """
    data = checks.write_data(data_hex)        # parsed once; the bytes travel, not the text
    session = live()
    seg, off = placement.read_target(ref, "DS", session)
    out = session.write_memory(seg, off, data)
    return st.answer({"ref": ref, "seg_off": st.seg_off(seg, off), **out})


# ------------------------------------------------------------- advancing the machine

# ---------------------------------------------------------------- the machine's hardware

@tool("Read or write an I/O port", summary=methods.fold_line("port", folds.PORT))
def port(method: Annotated[str, vocab.enum(tuple(folds.PORT))],
         port: judges.NumberArg | None = None,
         bits: Annotated[int, vocab.enum(tuple(hardware.BITS))] = 8,
         value: judges.NumberArg | None = None) -> dict[str, Any]:
    """One access of an I/O port, the one kind a memory write cannot make. Marks the session
    `altered`, a read too: reading a port can change its device (3DAh resets the attribute
    flip-flop, 60h takes the key). Needs the machine stopped and a build whose debugger has
    `PORTINFO`. `port` and `value` are integers or `0x` hex, as the reply spells them.

    `read`: `port`, `bits` (8, 16 or 32). Reply: `port`, `bits`, `value`.

    `write`: `port`, `value`, `bits`. Reply: `port`, `bits`, `value`, `readback` (unavailable:
    a port holds no value to read back).

    Refused (`bad_argument`): a port past 0xFFFF, a value wider than `bits`, an argument the
    method does not take. `no_channel`: a port no device answers at that size and side (the
    emulator would answer all ones, or swallow the write, in silence), or no `PORTINFO`.
    `not_stopped`: a running guest. `unexpected_answer`: the debugger answered another shape.

    Reference: REFERENCE.md, The machine's hardware.
    """
    return methods.dispatch(folds.PORT, locals())


@tool("Read or drive the interrupt controllers", summary=methods.fold_line("pic", folds.PIC))
def pic(method: Annotated[str, vocab.enum(tuple(folds.PIC))],
        irq: Annotated[int, vocab.bounds(0, hardware.IRQ_MAX)] | None = None) -> dict[str, Any]:
    """The 8259 interrupt controllers, which decide which hardware interrupt reaches the CPU.
    Needs the machine stopped.

    `read`: Reply: `controllers` (each `controller`, `vector_base`, `active_irq` (unavailable
    with none in service), `isr`, `isrr`, `auto_eoi`, ...), `irqs` (each `irq`, `vector`,
    `requested`, `masked`, `in_service`, `cascade`).

    `mask`, `unmask`, `acknowledge` (clear its in-service bit), `raise`, `lower` (its request line):
    `irq` 0 to 15. Marks the session `altered`. The timer is IRQ 0: `raise` it to run its
    handler on demand. Reply: `method`, `irq`, `line` (its row after).

    Refused (`bad_argument`): an `irq` out of range or on a slave this machine lacks, an
    argument the method does not take. `no_channel`: a build with no `PIC` command.
    `readback_refused`: a mask or unmask the listing does not show after. `not_stopped`: a
    running guest. `unexpected_answer`: a listing of another shape.

    Reference: REFERENCE.md, The machine's hardware.
    """
    return methods.dispatch(folds.PIC, locals())


@tool("Read or set the A20 gate", summary=methods.fold_line("a20", folds.A20))
def a20(method: Annotated[str, vocab.enum(tuple(folds.A20))]) -> dict[str, Any]:
    """The A20 gate, which decides whether memory past 1 MB wraps to 0. Needs the machine
    stopped.

    `method`: one of `read`, `on`, `off`. The last two mark the session `altered` and read the
    gate back.
    Reply: `enabled`.

    Refused: a build with no `A20` command (`no_channel`); a gate that does not read back as set
    (`readback_refused`); a running guest
    (`not_stopped`); an answer of another shape (`unexpected_answer`).

    Reference: REFERENCE.md, The machine's hardware.
    """
    return methods.dispatch(folds.A20, locals())


@tool("Resume the machine", summary=one_line.resume, on_cancel="none", replay="wall")
def resume(seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] = 0.0, detail: bool = False,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Let the machine run. `seconds` 0 (the default) returns at once with no deadline; a bound
    up to {WAIT_MAX_S} waits for a stop and, if none comes, leaves it running. Needs a stopped
    machine.

    Reply: with a bound, `waited_s` and `verdict` (`OTHER_STOP` with the stop reply of `run_to`;
    `TIMEOUT`, left running, with a `note`). `output` (with `detail=True`: the last
    {DETAIL_TEXT_KEEP} characters the debugger printed for `RUN`; else `omitted`).

    Reference: REFERENCE.md, Advancing the machine.
    """
    return advance.resume(seconds, detail, bridge(ctx))


@tool("Stop a running machine", summary=one_line.stop, on_cancel="stop", replay="wall")
def stop(ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Bring a running guest back to the debugger and survey the stop, headless or windowed.

    Reply: `interrupted` (`true` with the stop reply and `via: "break"`; `false` when already
    stopped, with a `note`). INVALID `not_settled`: after the `BREAK`, `RUNSTATE` did not say
    stopped; ask again.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    if session.at_debugger():
        running.observe_stop(session)
        # THE STOP IT IS IN, or none: after a survey that could not be read the record is the
        # previous stop's, and naming it would be a confident wrong answer.
        current = STATE.as_of_current(session)
        return st.reply(interrupted=False, last_stop=STATE.current_or_why(session),
                        note="the machine was already stopped" + (
                            "" if current is not None else ", its position not readable yet "
                            "(its survey failed; the next contact retries)"))
    session.break_in()
    return running.stop_reply(session, asked_by="stop", interrupted=True, via="break")


@tool("Step instructions", summary=one_line.step)
def step(count: Annotated[int, vocab.bounds(1, stepping.STEP_MAX)] = 1,
         mode: Annotated[str, vocab.enum(stepping.STEP_MODES)] = "into") -> dict[str, Any]:
    """`count` instructions, each read back; `mode` `into` (the debugger's `STEPIN`) or `over` (a
    CALL, INT, LOOP or REP run to the next instruction, which needs `RUNSTATE`). Needs the machine
    stopped.

    Reply: `mode`, `asked`, `before`, `after`, `instructions_completed`, `moved`, `stalled`
    (CS:EIP unchanged after a step), `note` (a step over's own breakpoint not confirmed removed),
    and the stop reply; an `over` that does not come back within its bound is stopped where it
    stands, and no later step is sent. For longer runs `run_to`.
    """
    session = live()
    out = cast(dict[str, Any], session.step(mode=mode, count=count))
    ran_away = bool(out.pop("running"))
    out["instructions_completed"] = out.pop("completed")
    out["before"], out["after"] = (f"{w['cs']}:{w['eip']}" for w in (out["before"], out["after"]))
    # A step that STOPPED carries the full stop reply; one that ran away (a CALL that never
    # returned) left the machine running, which `session.running` says, and a running machine
    # has nothing to read.
    return running.stop_or_base(session, not ran_away, out)


@tool("Run to a place or a mapped screen", summary=one_line.run_to, on_cancel="stop")
def run_to(ref: str = "", *, control: str = "", screen: str = "",
           seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run until a symbol or a `SEG:OFF` and say where it stopped.

    `ref`: a loaded symbol or hex `SEG:OFF`. `control` is required with a `ref` or an anchored
    screen: a second ref known to be hot, counted when it fires, so a bound that expires with no
    control hit is INVALID, not "it did not arrive". Needs a stopped machine. Refused: an absent
    or ambiguous name. On a dynamic cpu core, or `auto` (protected-mode code runs dynamic),
    which can pass over a breakpoint inside a compiled block, `note` says so.

    {MAP_RUN_TO}

    Reply: `verdict` (`TARGET`, `OTHER_STOP`, `TIMEOUT`), `target_disarmed`, `control_hits`,
    `controls` (`ref`, `at`, `hits_in_run`; a run to a ref or an anchor), `frames` (a screen with
    no anchor), `note`, the stop (`pc`, `frame`, `regs`, `cause`). INVALID: `control_silent`,
    `cut_by_other_stop`, `not_settled`, `stale_map`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    if screen:
        reply = advance.run_to_screen(screen, control, seconds, bridge(ctx))
        # A run by frames names no breakpoint, so the dynamic core's limit is not its to carry.
        return (dlaunch.with_dynamic_core_note(reply, session.launch)
                if STATE.maps.is_anchored(screen) else reply)
    if not control:
        raise screen_map.no_control()
    return dlaunch.with_dynamic_core_note(
        advance.run_to(ref, control, seconds, bridge(ctx)), session.launch)


@tool("Run for frames or emulated time", summary=one_line.run_for, on_cancel="stop")
def run_for(milliseconds: int = 0, frames: int = 0,
            seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run for `frames` display frames (one `VRT` each) or `milliseconds` of emulated time (exactly
    one) and come back STOPPED. `milliseconds` runs whole frames, so it ends at the first
    retrace at or past the time asked, up to one frame later. Reports progress while it waits.
    Needs the machine stopped.

    Reply: `verdict` (`ELAPSED`, `OTHER_STOP`, `TIMEOUT`), `polls`, `emulated_before_s`,
    `emulated_after_s`, `frame_before`, `frame_after`, `cycles` (a count on the normal core, else
    unavailable with why), `retrace_pending` (a retrace stop is left armed), `note`,
    {STOP_FIELDS}. INVALID: `no_progress`, `unexpected_answer`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    session.require_stopped("a `VRT`")
    return retrace.run_for(session, frames, milliseconds, seconds, bridge(ctx))


@tool("Trace what a run executes", summary=one_line.trace, on_cancel="stop")
def trace(instructions: Annotated[int, vocab.bounds(1, tracing.INSTRUCTIONS_MAX)],
          shape: Annotated[str, vocab.enum(tracing.SHAPE_WORDS)] = "normal", dest: str = "",
          seconds: Annotated[float, vocab.WAIT_BOUNDS] = 60.0,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run `instructions` (1 to {INSTRUCTIONS_MAX}) with the debugger's CPU log on and come back
    STOPPED with the log in a file, joined to symbols.

    `shape`: `normal` (`LOG`), `short` (`LOGS`), `long` (`LOGL`) or `cs_ip` (`LOGC`). `dest`:
    absolute, its directory there, the file not; empty is the next `trace-<n>.trace` in
    captures. `seconds` bounds the wait for the log. Needs a stopped machine, a writable working
    directory and `build_check`'s
    `heavy_debug`; a dynamic core needs `start(flags=["-set", "cpu core=normal"])`.

    Reply: `verdict`, the stop reply of `run_to`, `trace` (`path`, `instructions`, `addresses`,
    `unplaced`, `set_path`, `symbols` (first {SYMBOLS_SHOWN})). Refused: `no_channel`,
    `readback_refused`, `host_failed`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    return tracing.trace(session, instructions, shape,
                         paths.absolute("dest", dest) if dest else None, seconds, bridge(ctx))


@tool("Wait for a screen, its text or its palette", summary=one_line.screen_wait,
      on_cancel="stop", replay=recording.Counted("run_for", "frames", "polls"))
def screen_wait(text: str = "", screen: str = "", palette: str = "",
                every: Annotated[int, vocab.bounds(0, checks.SAMPLED_EVERY_MAX)] = 0,
                seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
                ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run the machine retrace by retrace until ONE predicate holds, and stop there.

    Exactly one of: `text` (1 to {SCREEN_TEXT_MAX} code page 437 characters, matched literally and
    case-sensitive inside one row as `screen_view` reads it), `screen` (a name of the loaded
    screen map, `screen_map_write`; the frame it names), `palette` ({PALETTES}: every DAC entry
    black, which is how a fade ends). None or several is `bad_argument`.

    `every`: 0 judges every retrace; N judges every Nth, for a predicate whose read is a full
    frame, and a screen that lasts fewer than N retraces is passed over. `seconds` bounds the
    polls, counted from the opening read; the stop at the bound comes after it. Needs a stopped
    machine and `RUNSTATE`. Already true: answered at once, the machine not moved. Each poll
    costs a stop and a read, so `run_for` first for a distant screen.

    Reply: `verdict` `TARGET` (`predicate`, `already`, `waited_s`, `polls`, `sampled_every`;
    text adds `point` `[column, row]` and `line`, screen adds `screen`, palette adds `entries`) or
    `TIMEOUT` (the same, with `retrace_pending`), `note`, the stop reply of `run_to` with its
    `frame` (unless the predicate was already true). Refused: `bad_argument`, `unknown_ref` (no
    such mapped screen), `wait_stopped` (a declared breakpoint stopped it), `no_channel` (a
    screen it cannot read, or a build with no `RUNSTATE`).

    Reference: REFERENCE.md, Input and the screen.
    """
    session = live()
    session.require_stopped("screen_wait")
    if palette:
        vocab.one_of("palette", palette, checks.PALETTES)
    return retrace.screen_wait(session, text, screen, palette, every, seconds, bridge(ctx))




@tool("Snapshot the screen to a PNG", summary=one_line.snapshot, on_cancel="none", replay="drop")
def snapshot(dest: str = "", seconds: Annotated[float, vocab.WAIT_BOUNDS] = ds.SNAPSHOT_WAIT_S,
             ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """A still of the screen as a PNG, at `dest` if given (absolute, new). Running: taken in the
    guest into the captures directory within `seconds` (`route` `guest`; `wait_expired` when none
    appears); refused with no `logfile` or no stub in the log. At a stop: written from video
    memory through `screen_view`'s decoder (`route` `video_memory`), unscaled, without running the
    machine; a text mode is refused (`no_channel`), and `seconds` is not used.

    Reply: `route`, `path`, `bytes`, `sha256`.
    """
    session = live()
    if session.at_debugger():
        vocab.check_wait(seconds)
        return st.answer(screen.still(session, paths.absolute("dest", dest) if dest else None))
    if session.launch.logfile is None:
        # `S` IS ALSO THE DELETE KEY'S SCAN CODE: an older stub would press it, and with no log
        # there is no announce to tell the two apart.
        raise ds.Invalid("no_channel",
            "snapshot needs the guest's E9 log to see which stub is resident (its command is "
            "a scan code to an older one): start the session with logfile=")
    inputs.require_stub(session)
    return st.answer(session.snapshot(paths.absolute("dest", dest) if dest else None, seconds,
                                      bridge(ctx)))


@tool("Record frames to an AVI", summary=one_line.record, on_cancel="stop")
def record(frames: int, dest: str = "", seconds: Annotated[float, vocab.WAIT_BOUNDS] = 60.0,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Record exactly `frames` retraces of the screen to an AVI, then stop. Needs the machine
    STOPPED and a build whose debugger has `CAPTURE`; headless or windowed.

    `dest`: an absolute path not there yet; empty leaves the file where the emulator wrote it.
    `seconds` bounds the wait for the recording. The AVI is checked before its path is given;
    zero frames is INVALID.

    One frame is written per retrace, but none for the first from the stop `start` leaves. A run
    cut short (`verdict` `TIMEOUT`, `OTHER_STOP`) is checked for what it holds. A capture that
    could not be turned off is `ended: false`, no `path`, and records until `close`.

    Refused: `frames` under 1, a video capture already on (`capture_video`), a build with no
    `CAPTURE`, a running machine.

    Reply: `verdict`, `kind`, `frames`, `began`, `ended`, `path`, `bytes`, `avi_frames`,
    `note`, the run's fields as `run_for` gives them, {STOP_FIELDS}.

    Reference: REFERENCE.md, Input and the screen.
    """
    session = live()
    return recordings.recording(session, "record", recordings.VIDEO, frames,
                                paths.absolute("dest", dest) if dest else None, seconds,
                                bridge(ctx))


@tool("Record the sound to a file", summary=one_line.audio_record, on_cancel="stop")
def audio_record(frames: int, dest: str = "",
                 seconds: Annotated[float, vocab.WAIT_BOUNDS] = 60.0,
                 kind: Annotated[str, vocab.enum(tuple(capture_files.AUDIO_KINDS))] = "wav",
                 ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Record exactly `frames` retraces of sound, then stop: the mixer to a WAV (`kind`
    `wav`), the OPL register writes to a DRO (`dro`) or the MIDI bytes to a MIDI file
    (`mid`). Needs the machine STOPPED and a build whose debugger has `CAPTURE`.

    `dest`: an absolute path not there yet; empty leaves the file where the emulator wrote it.
    `seconds` bounds the wait for the recording. The file is checked before its path is given
    (a rolled-over OPL run: the last); a WAV whose
    samples miss the run's emulated span by more than {SPAN_TICKS} mixer ticks is INVALID.
    Silence is reported, never refused; a run with no OPL note or MIDI byte has no file (`path`
    unavailable). A run cut short is checked for what it holds; a capture that could not be turned
    off is `ended: false`, no `path`, and records until `close`.

    Refused: `frames` under 1, that kind already on, a build with no `CAPTURE`, a running
    machine.

    Reply: `verdict`, `kind`, `frames`, `began`, `ended`, `path` (none if the capture could not be
    turned off), `bytes` (a file was written); a WAV's `channels`, `sample_rate_hz`, `samples`,
    `emulated_s`, `sample_min`, `sample_max`; a DRO's `opl_pairs`, `opl_ms` (the last file's);
    `files` (each `path`, `bytes`) when the OPL writer rolled over to a new file, `path` then the
    last; a MIDI file's `midi_bytes`; `note`, the run's fields, {STOP_FIELDS}.

    Reference: REFERENCE.md, Input and the screen.
    """
    session = live()
    return recordings.recording(session, "audio_record", capture_files.AUDIO_KINDS[kind],
                                frames, paths.absolute("dest", dest) if dest else None, seconds,
                                bridge(ctx))


@tool("List the saved states", summary=one_line.state_list, read_only=True)
def state_list() -> dict[str, Any]:
    """List the session's saved states, read off each file without loading it.

    Reply: `state_dir`, `states` (`version`, `program`, `machine`, `memory_mb`, `saved_at`,
    `bytes`, `note`), `working_slot`.

    Reference: REFERENCE.md, Saved states.
    """
    return st.answer(live().state_list())


@tool("Save or load a machine state", summary=methods.fold_line("state_write",
                                                             folds.STATE_METHODS))
def state_write(method: Annotated[str, vocab.enum(tuple(folds.STATE_METHODS))], name: str,
                seconds: Annotated[float, vocab.WAIT_BOUNDS] = ds.STATE_WAIT_S
                ) -> dict[str, Any]:
    """Save or load the machine as `<state_dir>/<name>.sav` through the debugger's `SAVESTATE` and
    `LOADSTATE`; no window or focus needed. `method`: `save` or `load`. A running guest is
    stopped for it and released again. `name`: letters, digits, `_`, `-`, never `-` first, at
    most {STATE_NAME_MAX}, not digits only. `seconds` bounds the command's reply.

    `save`: never overwrites. Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`,
    `memory_mb`, `saved_at`, `paused`.

    `load`: replaces the machine, altering the session, and taps the declared count and capture
    watches again (the load resets the page handlers). Reply: `name`, `path`, the state's own
    members, `paused`, `mark`, `taps` (`rearmed` refs and `unarmed` rows with `why`) when
    a declared tap was tapped again or could not be (a guest released running again waits for
    a stop).

    Refused: a DOSBox-X without the commands (`no_channel`); a state of another version,
    program, memory size or machine type; a `.sav` that is no regular file (`unknown_ref`).

    Reference: REFERENCE.md, Saved states.
    """
    return methods.dispatch(folds.STATE_METHODS, locals())


@tool("Arm an interrupt breakpoint", summary=one_line.breakpoint_interrupt)
def breakpoint_interrupt(number: Annotated[int, vocab.bounds(0, ds.BYTE_MAX)],
                         ah: Annotated[int, vocab.bounds(0, ds.BYTE_MAX)] | None = None,
                         detail: bool = False) -> dict[str, Any]:
    """Break on an interrupt, optionally one `ah` function. Arm it before `resume`. `number` and
    `ah` are hex given as integers: `0x21` for DOS, not `21`. Pending while the guest runs.

    Reply: `ref` (e.g. `BPINT 21 AH=4B`, what `declaration_clear` takes), `stored`,
    `already_stored`, `armed`, `state` (while the guest runs), `entry` (once armed);
    with `detail=True` also `output`.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.breakpoint_interrupt(live(), number, ah, detail)


@tool("Declare a registerpoint", summary=one_line.regpoint_add)
def regpoint_add(condition: str) -> dict[str, Any]:
    """Declare a registerpoint: the machine stops when `condition` comes true, wherever in the
    program ("who puts this value in this register"). Stored, re-armed at `start`; pending while
    the guest runs. Needs the debugger's `BPIF`.

    `condition`: up to four terms joined by `&&`, each a register (`AX`, `EAX`, `AL`, `CS`, ...,
    `FLAGS`), a comparison (`==`, `!=`, `<`, `<=`, `>`, `>=`) and a hex value (`AX==3B`,
    `0x` allowed); compares, never assigns.

    Refused: a term not in that shape (`bad_argument`); a build without `BPIF` (`no_channel`).

    Reply: `ref` (the condition as the debugger prints it back, what `declaration_clear` takes),
    `stored`, `already_stored`, `armed`, `state`, `while_running`, `entry` (once armed),
    `note`.

    Reference: REFERENCE.md, Declarations.
    """
    return regpoints.regpoint_add(live(), condition)


# --------------------------------------------------------------- names for addresses

@tool("Load a symbol table", summary=one_line.symbols_load)
def symbols_load(path: str, base: str = "",
                 base_from: Annotated[str, Field(json_schema_extra={
                     "pattern": ds.BASE_FROM_PATTERN})] = "CS",
                 pattern: str = "", keep_noise: bool = False,
                 section_bases: dict[str, str] | None = None, types: str = "",
                 ) -> dict[str, Any]:
    """Load a toolchain's symbol list so other tools take names. Stop inside the program first;
    with an explicit `base` a running guest works too (`pending: true`).

    `path`: `nm` output or a GNU `ld`, Borland or Watcom map. Flat lists take `base` (hex text) or
    `base_from`, a register or a selector as four hex digits (`00AF`), whose descriptor the
    debugger reads in any CPU mode, so a real-mode stop can load a protected-mode program's table;
    sectioned maps take `section_bases`. `types`, `pattern`, `keep_noise` filter and type rows.

    Refused (INVALID): both `base` and `section_bases`; a sectioned map without
    `section_bases`; real mode or a running machine without `base` or a selector number; a
    mostly unreadable file;
    a table the `<stem>.exe` contradicts; a table in which two names differ only in case, naming
    both lines.

    Reply: `parsed`, `kept`, `loaded`, `table_mode`, `table_total`, `renamed`, `pending`,
    `base`, `checked`, `declarations`, and `debugger_holds` when an earlier load's rows are
    still in the debugger.

    Reference: REFERENCE.md, Names for addresses.
    """
    session = live()
    src = judges.existing_file("path", path, "symbol file")
    typed = placement.read_types(types) if types else {}
    STATE.start_symbols = None      # a table loaded by hand is the one the session keeps
    return placement.load(session, path, src,
                          placement.hex_arg("base", base) if base else None,
                          base_from, pattern or None, keep_noise,
                          None if section_bases is None else placement.hex_bases(section_bases),
                          rearm_declarations=arming.rearm_declarations,
                          take_the_map=comments.park_rows_take_the_map, types=typed)


@tool("Look a symbol up", summary=one_line.symbols_find, read_only=True)
def symbols_find(name: str = "", offset: int | None = None,
                 section: int | None = None,
                 linear: str = "",
                 limit: Annotated[int, vocab.bounds(1, placement.SYMBOLS_LIMIT_MAX)] = 10,
                 ) -> dict[str, Any]:
    """Look a symbol up in the table `symbols_load` kept. `name`: exact, else prefix matches by
    section and offset, case ignored, each in the spelling the map gave, up to `limit`. `offset` (an
    integer) or `linear` (hex text), with `section`: the nearest symbol at or below.

    Reply: `query`; by name, `symbols_total`, `symbols` (`name`, `offset`, `addr`), `truncated`;
    by address, the symbol's fields and `delta`. INVALID: no table.
    """
    # THE SESSION IS ASKED FOR FIRST, as every read tool asks: a session whose emulator died is
    # `session_broken` there, and the table is forgotten when the session OBJECT changes, so it
    # never answers `ok` with a linear address for a process that is gone.
    live()
    return placement.find(name or None, offset, section, linear or None, limit)


# ------------------------------------------------------------------------------- comments


@tool("List the comments", summary=one_line.comment_list, read_only=True)
def comment_list() -> dict[str, Any]:
    """Every comment of this conf, in store order. Answers on a running guest too.

    Reply: `comments` (each `ref`, `text`, `addr`, `state`, `why`),
    `comments_total`, `truncated`, `declarations`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_list(live())


@tool("Write the comments", summary=methods.fold_line("comment_write", folds.COMMENT),
      replay="drop")
def comment_write(method: Annotated[str, vocab.enum(tuple(folds.COMMENT))], ref: str = "",
                  text: str = "", dest: str = "", path: str = "") -> dict[str, Any]:
    """Change this conf's comments.

    `add`: `text` (one printable line, at most {COMMENT_TEXT_MAX} UTF-8 bytes) on `ref`,
    a symbol or a `SEG:OFF`; a second there replaces it. Reply: `comment`, `replaced_comments`,
    `declarations`, `note`.

    `delete`: the comment `ref` names. Reply: `deleted`, `declarations`, `note`.

    {COMMENT_SAVE}

    {COMMENT_LOAD}

    `add`, `delete` and `load` need the machine stopped. Refused: an argument the method
    does not take, a misshapen `ref` or `text`, a `save` `dest` that is the declaration store's
    file, compared without regard to case on any volume (`bad_argument`), a name defined twice
    (`ambiguous_ref`), an unknown `ref` (`unknown_ref`), an unwritable store (`host_failed`).

    Reference: REFERENCE.md, Declarations.
    """
    return methods.dispatch(folds.COMMENT, locals())





# ---------------------------------------------------------------------- the DOS machine

@tool("Map the machine", summary=one_line.machine_map, replay="drop")
def machine_map(sections: list[Annotated[str, vocab.enum(machine.SECTION_NAMES)]] | None = None,
                dest: str = "") -> dict[str, Any]:
    """What the DOS machine is at this stop: one section per debugger listing. `sections` left
    out reads the DOS machine and `control`; `bios_mem`, `callbacks`, `vga`, `paging` only when
    named. `dest` (absolute, new) writes all sections whole as JSON. Writes nothing to the guest.

    Reply: `cpu_mode`, one key per section read as rows, `counts`, `truncated` (cut at
    {LOG_LIMIT_MAX} rows), `sources`, `coverage_note` (why a section is absent), `path` (with
    `dest`). Refused: bad `sections` or an existing `dest` (`bad_argument`); a running guest
    (`not_stopped`).

    Reference: REFERENCE.md, Reading and writing.
    """
    chosen = narrowing.sections(sections, machine.SECTION_NAMES, machine.DEFAULT_SECTIONS)
    target = paths.fresh_dest("dest", dest) if dest else None
    session = live()
    session.require_stopped("a listing")
    whole = machine.machine_map(session, chosen)
    if "vga" in chosen:
        machine.add_section(whole, "vga", *vga.vga_section(session))
    reply = machine.cut_lists(whole)
    if target is not None:
        text = json.dumps(whole, indent=1).encode()
        fresh.create(target, text, "the map", named_by_caller=True)
        reply["path"] = str(target)
    mode = whole["cpu_mode"]
    left = [n for n in machine.sections_of(mode if isinstance(mode, str) else None)
            if n not in chosen]
    if left:
        reply.update(narrowing.omission(left, machine.MAP_HOW))
    elif reply["truncated"] and target is None:
        reply["how"] = machine.MAP_CUT_HOW
    return st.reply(**reply)


@tool("Read the interrupt vectors", summary=one_line.interrupt_vectors, replay="drop")
def interrupt_vectors(number: Annotated[int, vocab.bounds(0, ds.BYTE_MAX)] | None = None,
                      ) -> dict[str, Any]:
    """Which handler every interrupt vector points at and what holds it, from the debugger's
    `INTVEC` table: a handler is placed in the MCB, kernel or BIOS block holding it and named by
    loaded symbols. `number` (0 to 255) narrows the reply to one vector. In protected mode the
    table is the IDT.

    Reply: `cpu_mode`, `vectors` (each `number`, `seg_off`, `addr`, a holder row, `symbol`),
    `counts`, `sources`, `coverage_note`.

    Refused: `number` out of range or a `MCPIVT.TXT` already there (`bad_argument`); a running
    guest (`not_stopped`); an incomplete table (`unexpected_answer`); `machine_map`'s listing
    refusals.

    Reference: REFERENCE.md, Reading and writing.
    """
    session = live()
    session.require_stopped("`INTVEC`")
    return st.reply(**machine.interrupt_vectors(session, number))


# ------------------------------------------------------------------------ the screen

@tool("Read the palette", summary=one_line.palette, replay="drop")
def palette(first: Annotated[int, vocab.bounds(0, vgadac.DAC_ENTRIES - 1)] | str = 0,
            count: Annotated[int, vocab.bounds(0, vgadac.DAC_ENTRIES)] = 0, scale: int = 0,
            dest: str = "") -> dict[str, Any]:
    """The VGA DAC's 256 colours at this stop, read off the `VGA DAC` listings, with an indexed
    PNG swatch. `first` and `count` (0 for all from `first`)
    choose entries, `first + count` at most 256. `scale` 0 fits the largest enlargement up to 8;
    `dest` a new path, else a scratch gone at `close`.

    Reply: `entries`, `first`, `count`, `colors` (`#rrggbb`), `rgb`, `bits`, `pel_mask`,
    `image`.

    Refused: an entry past 255, a bad `scale`, a relative or existing `dest` (`bad_argument`);
    a running guest (`not_stopped`); a DAC not six-bit (`unexpected_answer`); a picture not
    taken whole (`host_failed`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    session.require_stopped("a listing")
    return st.reply(**vgadac.palette(session, checks.number("first", first), count, scale,
                                     paths.absolute("dest", dest) if dest else None,
                                     STATE.session_scratch()))


@tool("Read the screen", summary=one_line.screen_view, replay="drop")
def screen_view(mode: Annotated[str, vocab.enum(by_pens.MODES)] = "render",
                pens: list[int] | None = None, point: list[int] | None = None,
                crop: list[int] | None = None, scale: int = 0,
                dest: str = "", attach: bool = True) -> dict[str, Any]:
    """What the screen shows at this stop, read from video memory: text as text, a graphics mode
    as a PNG (256 colours chained or not, 16-colour planar, 8-, 15-, 16- or 32-bit linear; all
    but chained through `VGAMEMDUMP`). `mode`: `render`, `isolate` (`pens`, 1..{SCREEN_PENS_MAX},
    in `isolate_color` over grey), `histogram` (pens used, no picture), `pixel` (`point`
    `[x, y]`); the last three read a palette-indexed graphics mode, where a pen is the DAC entry
    a pixel holds, and no `set_by` is answered. `crop` is `[x, y, width, height]` in characters
    or pixels and narrows all but `pixel`. `scale` 0 fits the largest up to 8x; `dest` a new
    path (else a scratch); `attach` false leaves it unattached.

    Reply: `mode`, `vga_mode`, `kind`, `width`, `height`, `crop`, `display_start`; in text `text`,
    `cursor`; in graphics `screen_indexed`, `entries` (indexed) and `image` (not for mode
    histogram); `isolate`: `pixels`, `bbox`, `pens`, `isolate_color`; mode histogram: `histogram`,
    `pens_used`, `unused`; `pixel`: `x`, `y`, `pen`, `color`, `point_in_crop`.

    Refused: a relative or existing `dest`, a bad `scale`, `crop`, `mode`, `pens` or `point`, an
    argument the mode ignores, `dest`/`scale`/`attach` in text or `histogram`, a `point` off the
    screen (`bad_argument`); another mode or a build without `VGAMEMDUMP` (naming
    `capture_frame`), an undecodable layout, or `isolate`/`histogram`/`pixel` on a text or
    direct-colour mode (`no_channel`); a running guest (`not_stopped`); a DAC not six-bit
    (`unexpected_answer`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    session.require_stopped("a listing")
    return st.reply(**screen.screen_view(session, crop, scale,
                                         paths.absolute("dest", dest) if dest else None,
                                         STATE.session_scratch(), attach, mode, pens, point))


@tool("Signature of the screen", summary=one_line.screen_signature, read_only=True,
      replay=("signature",))
def screen_signature(crop: list[int] | None = None) -> dict[str, Any]:
    """One hex string for what is on screen or on `crop` `[x, y, width, height]`: the `scry-sig/1`
    signature of a series row (text cells by byte and colours, 256-colour pixels by DAC colour;
    no cursor). Reads what `screen_view` reads.

    Reply: `signature`, `kind`, `width`, `height`, `crop`, `vga_mode`. Refusals as
    `screen_view`, `dest` and `scale` aside.

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    session.require_stopped("a listing")
    return st.reply(**screen.screen_signature(session, crop))


# ------------------------------------------------------------------- the screen maps



@tool("Which mapped screen is this", summary=one_line.screen_map_find, read_only=True,
      replay=("matched", "screen"))
def screen_map_find() -> dict[str, Any]:
    """{MAP_FIND}

    Reference: REFERENCE.md, Screen maps.
    """
    session = live()
    session.require_stopped("a listing")
    # The stop the read is of, or None when that stop's own record could not be made (its survey
    # failed): a previous stop's number would date the identification wrong.
    current = STATE.as_of_current(session)
    return st.reply(**STATE.maps.find(folds.map_read(session),
                                      None if current is None else current["stop_seq"]))


@tool("Write the screen map", summary=methods.fold_line("screen_map_write", folds.MAP),
      replay={"add": "step", "load": "step", "pointer": "step", "save": "drop"})
def screen_map_write(method: Annotated[str, vocab.enum(tuple(folds.MAP))], screen: str = "",
              match: list[list[int]] | None = None, controls: list[dict[str, Any]] | None = None,
              cells: Annotated[str, vocab.enum(screen_map.CELLS_WORDS)] = "",
              anchor: str = "", path: str = "", scale: int | None = None,
              margin: list[int] | None = None, dest: str = "",
              overwrite: bool | None = None,
              pointer: dict[str, Any] | None = None) -> dict[str, Any]:
    """{MAP_WRITE}

    {MAP_ADD}

    {MAP_POINTER}

    {MAP_CELLS}

    {MAP_ANCHOR}

    {MAP_LOAD}

    {MAP_SAVE}

    {MAP_REFUSED}; the modes `screen_view` refuses.

    Reference: REFERENCE.md, Screen maps.
    """
    reply = methods.dispatch(folds.MAP, locals())
    return mpromote.after_map(method, reply)



@tool("Capture a series of frames", summary=one_line.series_capture, replay="drop")
def series_capture(at_frames: list[int] | None = None, first: int | None = None,
                   last: int | None = None, step: int = 1, crop: list[int] | None = None,
                   dest: str = "", capture_path: str = "") -> dict[str, Any]:
    """Capture frames as PNGs plus a manifest (read by `image_compare`).

    AVI frames from 0: `at_frames`, or `first`, `last`, `step`; max {SERIES_MAX}. `crop`:
    `[x, y, w, h]`. `dest`: new directory, kept after `close`.

    Reply: `manifest`, `count`, `first`, `last`, `distinct`, `kept_after_close`, `capture_path`,
    `crop`. Refused: `bad_argument` (frame, crop, `dest`), `no_channel` (no `capture_video`),
    `unexpected_answer` (no capture), `host_failed` (no `ffmpeg`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    return st.reply(**media.series_capture(session, STATE.session_scratch(), at_frames, first,
                                           last, step, crop, dest, capture_path))


# THE MEDIA FILE TOOLS are scry-core's, body and description, each registered through this
# server's own `tool`, its bare fields made a reply (`status` and `session`) as this server's own
# bodies make theirs; bound here by name so a step and a direct call find them as they find
# every other tool.
_MEDIA = media_tools.register(tool, media.MEDIA_TOOLS, lambda body: st.reply(**body))
image_compare = _MEDIA["image_compare"]
audio_compare = _MEDIA["audio_compare"]


# --------------------------------------------------- declarations: breakpoints, watches

@tool("Declare a breakpoint", summary=one_line.breakpoint_at)
def breakpoint_at(ref: str, by: Annotated[str, vocab.enum(checks.BREAKPOINT_BY)] = "auto",
                  ) -> dict[str, Any]:
    """Declare a code breakpoint at a symbol or `SEG:OFF`, and arm it if it can be. Stored, and
    re-armed on `symbols_load`; a raw `SEG:OFF` goes `stale` over another build. `by`: `auto`
    (this server's choice), `symbol` or `address`, which is how the ref is read.

    Refused: a name matching several symbols; an address another declaration holds, naming it. On
    a dynamic cpu core, or `auto` (protected-mode code runs dynamic), which can pass over it
    inside a compiled block, `note` says so. A symbol
    absent from this build is stored `unresolved`.

    Reply: `ref`, `stored`, `already_stored`, `armed`, `entry` (once armed), `state` (`armed`,
    `unresolved`, `unarmable`, `pending` while the guest runs), `why`, `marked` and `note` for
    a linker-marked symbol.

    Reference: REFERENCE.md, Declarations.
    """
    session = live()
    return dlaunch.with_dynamic_core_note(arming.breakpoint_at(session, ref, by), session.launch)


@tool("List the declarations", summary=one_line.declaration_list, read_only=True)
def declaration_list(kind: Annotated[str, vocab.enum(("", *folds.KINDS))] = "",
                     ) -> dict[str, Any]:
    """List the declarations of `kind` (empty: every kind) with their state, cross-referenced
    with the debugger's own list. On a running guest the states are the last stop's survey
    (`debugger_read` false).

    Reply: `breakpoints`, `regpoints`, `watches` (each kind asked; each row `ref`, `by`, `cpu`,
    `created_at`, `origin`, `inherited`, `age_s`, `state`, plus its kind's fields), `foreign`
    (debugger entries no declaration resolves to), `debugger_read`.

    Reference: REFERENCE.md, Declarations.
    """
    return folds.list_declarations(kind)


@tool("Clear declarations", summary=one_line.declaration_clear)
def declaration_clear(kind: Annotated[str, vocab.enum(folds.KINDS)], ref: str = "",
                      all: bool = False) -> dict[str, Any]:
    """Clear the declarations of `kind`: all with `all=True`, or the one named by the exact `ref`
    its declaring reply carried; `breakpoint` takes `breakpoint_interrupt` rows too. Removes only
    what this store armed, the declarations at once and, on a running guest, their debugger
    rows at the next stop (`pending_disarm`); a `foreign` entry is never deleted.

    Refused: a `ref` matching none, naming the refs held; neither `ref` nor `all`, or both
    (`bad_argument`).

    Reply: `declarations_cleared`, `disarmed`, `pending_disarm` (removed at the next stop),
    `note`.

    Reference: REFERENCE.md, Declarations.
    """
    return folds.clear_declarations(kind, ref, all)




@tool("Declare a watch", summary=one_line.watch_add)
def watch_add(ref: str, mode: Annotated[str, vocab.enum(dec.WATCH_MODES)], length: int = 0,
              fmt: str = "auto", by: Annotated[str, vocab.enum(checks.WATCH_BY)] = "auto",
              trigger: str = "",
              trigger_type: Annotated[str, vocab.enum(dec.TRIGGER_TYPES)] = "w",
              ) -> dict[str, Any]:
    """Declare a watch by symbol, `SEG:OFF` or through a pointer, read as `fmt`. Persists and
    re-resolves on `symbols_load`.

    `mode`: `show` (read at each stop), `change` (stops when the bytes change), `count` (tallies
    every write and its writer), `capture` (a row per access of `trigger`, with the beam line
    and the time), `freeze` (pins the bytes at their value: the guest's writes are undone, and
    the session is `altered`);
    count, capture and freeze never stop the machine. `ref`: a symbol, `SEG:OFF`, or
    `[base]+0x28`, `base->field`. `fmt`: a scalar (`u8` .. `f64`), an array (`u16[8]`), a string
    (`char[16]`) or a struct (`{x:i16,y:i16}`). `length`: total bytes; at most {READ_MAX} for
    show, {CHANGE_WATCH_MAX} for change and {FREEZE_MAX} for freeze (a debugger row per byte,
    `entries`), {TAP_COUNT_MAX} for count, {TAP_BLOCK_MAX} for capture. `trigger`,
    `trigger_type`: capture only; a capture of reads (`r`) is of `ref` itself, with no
    `trigger`, `length` or `fmt`. A count or capture is declared at a stop, by symbol or
    `SEG:OFF`, on a build whose debugger has `TAP`; from then on it records while the guest
    runs. A freeze likewise, on a heavy-debug build, pinning the values of that stop; each stop
    reads its bytes back (`holding`, or `not_held` when something ran past it), and a stored
    freeze is not armed again at `start` or `symbols_load`, where its bytes hold other values.

    Refused: one ref declared two ways; a length over the ceiling; a pointer base the table
    lacks; a count, capture or freeze through a pointer or on a running machine (`not_stopped`);
    a count or capture with no `TAP`, a freeze with no heavy debugger (`no_channel`); a freeze
    on an offset already frozen (`ambiguous_ref`); a write capture with no `trigger`; `trigger`
    or `trigger_type` on another mode.

    Reply: `ref`, `by`, `mode`, `fmt`, `length`, `stored`, `already_stored`, `state` (`evaluated`,
    `unresolved`, `unarmable`, `null_pointer`, `pending`, `armed`), `armed`, `pointer` (a pointer
    `ref`), `entry` (once armed), `caveat` (protected mode); a count or capture's `tally_id`,
    `addr`, `trigger`, `trigger_addr`, `trigger_type`; a freeze's `addr`, `entries`, `frozen_hex`;
    its account is `declaration_list`'s.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.watch_add(live(), ref, mode, length, fmt, by, trigger, trigger_type)




# ------------------------------------------------------------ input into the guest

@tool("Send keystrokes", summary=one_line.send_keys, on_cancel="none")
def send_keys(keys: list[str],
              modifiers: list[Annotated[str, vocab.folded(inputs.MODIFIER_WORDS)]] | None = None,
              expect: str = "", seconds: Annotated[float, vocab.WAIT_BOUNDS] | None = None,
              action: Annotated[str, vocab.enum(inputs.KEY_ACTIONS)] = "press",
              ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Send keystrokes to the guest; with `expect`, prove the program took them.

    `keys`: at most {KEYS_MAX}. `action`: `press` taps them; `down` holds the modifiers and
    presses the keys, `up` releases them, so a held key spans the calls between; a held key
    makes no repeats of its own, each repeat is a further `down`. `expect`: a regex over the
    E9 log the program's reaction writes, waited up to `seconds` (default {EFFECT_WAIT_S}).
    A stopped machine is
    run retrace by retrace until the stub takes each key, and left stopped at a retrace; its
    `expect` waits `seconds` of the guest's own time.

    Refused: an unknown key or modifier, `seconds` without `expect`, no stub, a stopped
    machine on a build with no `RUNSTATE` (`no_channel`).

    Reply: `route`, `posted`, `bytes`, `frames` (stub commands, a BIOS tick apart), `verify`
    (`verdict` `TARGET` or `TIMEOUT`, `seen`); from a stopped machine `polls` and the stop
    it was left at ({STOP_FIELDS}).

    Reference: REFERENCE.md, Input and the screen.
    """
    return inputs.send_keys(live(), keys, modifiers, expect or None, seconds, bridge(ctx), action)


@tool("Send mouse input", summary=one_line.send_mouse, on_cancel="none")
def send_mouse(x: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               y: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               button: Annotated[str, vocab.enum(("", *inputs.BUTTON_WORDS))] = "",
               action: Annotated[str, vocab.enum(("", *inputs.ACTIONS))] = "",
               units: Annotated[str, vocab.enum(inputs.UNITS)] = "screen", expect: str = "",
               seconds: Annotated[float, vocab.WAIT_BOUNDS] | None = None, target: str = "",
               to_x: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               to_y: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Move the guest's mouse pointer, press buttons, and read the pointer back; `expect`
    proves the program reacted, as in `send_keys`, and is waited up to `seconds`.

    `x`, `y`: both or neither, in `units`. `action` names what the button does; with an `action`
    and no `button` the left one is used, and with neither only the pointer moves. `target`: a
    control of the latest `screen_map_find`
    screen, instead of `x`, `y`. `action="drag"` presses at that place and releases at `to_x`,
    `to_y`, with the move between. A stopped machine is run as for `send_keys`; under a map that
    declares the program's own pointer, a move there nudges the driver until that pointer is on
    the place and `arrived` judges it (`pointer.program`, unavailable with its reason on a running
    guest, `units="mouse"` or a mode of unknown size). A drag's end is not steered.

    Refused: no move and no button, half a move, a place off the screen, no stub, a stopped
    machine with no `RUNSTATE`; `target` beside `x`, `y` or `units="mouse"`, a drag without
    both ends, `to_x` and `to_y` without a drag (`bad_argument`);
    no `screen_map_find` match (`needs_call`); an unknown control (`unknown_ref`).

    Reply: `route`, `pointer`, `arrived` (the program's pointer read, or `units="mouse"`; else
    `driver_arrived` and `asked`: only the driver is known), `motion` (a move reached the motion
    counters too), `verify`; with `target`: `target`, `screen`, `identified_at_stop`; from a
    stopped machine, `send_keys`' `polls` and stop.

    Reference: REFERENCE.md, Input and the screen.
    """
    button = button or ("left" if action else "")      # naming an action presses the left button
    action = action or "click"
    if not target:
        moved = inputs.send_mouse(live(), x, y, button or None, action, units, expect or None,
                                  seconds, bridge(ctx), to_x=to_x, to_y=to_y,
                                  program=STATE.maps.pointer)
    else:
        inputs.check_mouse(x, y, button or None, action, units, expect or None, seconds, target,
                           to_x, to_y)
        aimed = STATE.maps.target(target)
        moved = inputs.send_mouse_at(live(), aimed, button or None, action, expect or None,
                                     seconds, bridge(ctx), to_x=to_x, to_y=to_y,
                                     program=STATE.maps.pointer)
    # Read off the state, not `live()`: a session that died after the move went in must not
    # cost the caller the reply that says it was delivered.
    dpresence.pointer_moved(dpresence.of(STATE.session))
    return moved


# ----------------------------------------------------------------------- the captures

@tool("What the guest left in a file", summary=one_line.guest_file, read_only=True,
      replay=("state",))
def guest_file(path: str) -> dict[str, Any]:
    """What the guest left at `path`, a host file `start(guest_files=)` fingerprinted before
    the emulator booted: `absent`, `empty`, `unchanged` (the bytes and time from before the
    run) or `written`. Reads the host's file, so it answers with the guest running or after
    `close`.

    Reply: `path`, `state`, `bytes`, `sha256`, `before` (`exists`, `bytes`, `sha256`),
    `same_bytes` (written again with the bytes it held). INVALID `readback_refused` on the
    first three, which hand nothing back; a path `start` did not name is refused.

    Reference: REFERENCE.md, The guest's files.
    """
    return guest.guest_file(path)


@tool("List this session's captures", summary=one_line.captures, read_only=True)
def captures() -> dict[str, Any]:
    """Lists the files the session's tools wrote (`record` and `audio_record` among them), in
    write order, re-read when changed, then the `capture_video` AVIs, largest last. Works on a
    running guest.

    Reply: `captures` (each `kind`, `path`, `present`, `bytes`; a recording also `complete`, and
    an AVI `riff_avi`, `avi_frames`, a WAV `samples`, `channels`, `sample_rate_hz`, a DRO
    `opl_pairs`, `opl_ms`, a MIDI file `midi_bytes`). A file gone has `present: false`, no
    `bytes`.
    """
    return caps.captures(live())


@tool("Extract a frame to a file", summary=one_line.capture_frame, replay="drop")
def capture_frame(frame: int, dest: str, capture_path: str = "") -> dict[str, Any]:
    """Frame `frame` of a capture written to `dest` as PNG; `capture_path` defaults to the
    largest. Needs `ffmpeg`, `capture_video`. Refused: `%` in or existing `dest`, a frame
    past the end.

    Reply: `path`, `bytes`, `sha256`, `capture_path`, `frame`.
    """
    session = live()
    return caps.capture_frame(session, frame, paths.absolute("dest", dest),
                              judges.existing_file("capture_path", capture_path, "capture")
                              if capture_path else None)


# ---------------------------------------------------------------------- the sequence

def _step_ops() -> dict[str, Callable[..., dict[str, Any]]]:
    """Op name -> the wrapped tool it dispatches to: every tool the MCP layer serves but
    `checks.NOT_STEPS`, read off the registry at call time, so a step is a tool by construction and
    a new tool is a step without a second list to forget."""
    return core_steps.step_ops(mcp, globals(), checks.NOT_STEPS)


checks.take_step_ops(_step_ops)


@tool("Export the session as a replay", summary=recording.export_summary)
def perform_export(dest: str, overwrite: bool = False) -> dict[str, Any]:
    """Write the session's calls since `start` to `dest` as a `perform` document.

    Kept: moving calls and checks (`read_memory`, `registers`, `screen_signature`,
    `screen_map_find`, `guest_file`, `image_compare(method="golden")`), each held to its
    `recorded` reply. Other calls drop; the first no replay can place, or past {RECORD_MAX}, cuts
    the rest.

    `dest` (`.json`) is refused if present unless `overwrite`. Reply: `path`, `steps`,
    `checks`, `dropped`, `dropped_total`, `cut`, `replay`, and `kept` when the document is kept
    for `promote`; `no_recording` if empty.

    Reference: REFERENCE.md, From an investigation to a bench.
    """
    return mpromote.after_export(STATE.drafts, st.reply(**recording.export(
        RECORDER, dest, overwrite)), mpromote.PROMOTE_PATHS)


#: `summaries`' own description, `perform`'s and `drive`'s, as scry-core words it.
SUMMARIES_ARGUMENT = account.summaries_argument(st.ROWS_SHOWN)


@tool("Promote what the session learned", summary=one_line.promote, replay="drop")
def promote(dry_run: bool = False, entries: list[str] | None = None,
            names: dict[str, str] | None = None, root: str = "") -> dict[str, Any]:
    """{PROMOTE}

    Reference: REFERENCE.md, The store.
    """
    return st.reply(**mpromote.promote(dry_run, entries, names, root))


@tool("Run a sequence of steps", summary=one_line.perform, on_cancel="stop")
def perform(steps: list[dict[str, Any]] | None = None, path: str = "",
            settle_seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] = 30.0,
            summaries: Annotated[bool, Field(description=SUMMARIES_ARGUMENT)] = False,
            until_frame: int = 0,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run this server's operations in order on the open session, stopping at the first
    failure.

    `steps`: `{"op": <tool>, ...arguments}`, any tool but `build_check`, `start`, `close`,
    `perform`, `drive`, `perform_export`. `path`: a `perform` document (absolute or `~`-led:
    `.scry/perform/<name>.json`, or a file `perform_export` wrote) whose steps are replayed; give
    `steps` or `path`, never both.
    A `send_keys` or `send_mouse` whose `expect`
    misses ends the list `TIMEOUT`. A step's `recorded` must hold, else INVALID `diverged`.
    The whole list is checked first: INVALID `errors` (`step`, `op`, `code`, `message`),
    nothing run. `settle_seconds` bounds each wait for a stop before a step that needs one (0:
    never wait). {UNTIL_FRAME} Frames count since power-on. A `screen_view` step inlines its
    text; its picture is written to its `path` and answers `not_inlined: nested`.

    Reply: `ran`, `steps_completed`, `held`, `failed_at`, `failed` (INVALID `step_failed`),
    `verdict` (once the list waited; `TARGET` adds `stopped`, `TIMEOUT` `note`), else
    `still_running`; `frame_reached` (with `until_frame`).

    Reference: REFERENCE.md, Sequences in one call.
    """
    from_document = bool(path)
    steps = recording.steps_to_replay(steps, path)
    if from_document:      # the pre-gate judges a caller's own list; a document's is read here
        checks.steps_whole("steps", steps)
        STATE.drafts.loaded_entry("perform", Path(path).expanduser().stem)
    return sequence.run_steps(live(), steps, settle_seconds, _step_ops(), bridge(ctx), summaries,
                              until_frame=until_frame)


@tool("Drive an input and verify it", summary=one_line.drive, on_cancel="none")
def drive(act: list[dict[str, Any]], expect: str = "",
          seconds: Annotated[float, vocab.WAIT_BOUNDS] | None = None, pattern: str = ".",
          limit: Annotated[int, vocab.bounds(1, dlogs.LOG_LIMIT_MAX)] = 40,
          settle_seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] = 30.0,
          summaries: Annotated[bool, Field(description=SUMMARIES_ARGUMENT)] = False,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Look, act and verify in one call. Marks the E9 log, runs `act` (steps in `perform`'s
    vocabulary), then with `expect` waits up to `seconds` (default {EXPECT_WAIT_S}, at most
    {WAIT_MAX_S}) for a new matching line. Needs a `logfile`.

    `pattern` and `limit` only filter the lines shown; `settle_seconds` is the call's, as in
    `perform`. Refused: `seconds` without `expect`.

    Reply: `act` (`ran`, `steps_completed`, `failed_at`), `verify` (`verdict` `TARGET` or
    `TIMEOUT`, `seen`, `line`; `checked: false`), `looked.guest` (`lines`, `truncated`).
    INVALID with the same fields on `step_failed`, `wait_stopped`, or the act's own refusal.
    No screen: use `capture_frame`.

    Reference: REFERENCE.md, Input and the screen.
    """
    return sequence.drive(live(), _step_ops(), act, expect or None, seconds, pattern, limit,
                          settle_seconds, bridge(ctx), summaries)


strict.strict_arguments(mcp)
reply_schema.declare(mcp, dosbox_replies.MODELS)
sequence.GATE.check_folds(folds.METHODS)

#: What the reference pages are generated from
#: (`python -m scry_core.reference scry_dosbox_x.server:REFERENCE`) and held to
#: (`tests/test_dosbox_x_reference_pages.py`).
REFERENCE = reference.Registry(server=mcp, models=dosbox_replies.MODELS, roster=ROSTER,
                               envelope=dosbox_replies.DosboxEnvelope,
                               root=Path(__file__).resolve().parents[2])


def _close_held_session() -> None:
    """The emulator this server holds, ended: the published session, and one `start` is still
    waiting for (an end by signal that could not take the lock reaches it)."""
    for held in (STATE.session, STATE.starting):
        if held is not None:
            held.close()
    STATE.session = STATE.starting = None


#: The end on a signal: the emulator closed, the process's scratch removed, the process left.
END = signalled_end.SignalledEnd(LOCK, _close_held_session, lambda: st.remove_scratch(),
                                 "dosbox-x server")


def main() -> None:
    process_name.set_title(dprocess.PROCESS_NAME)
    END.install()
    try:
        mcp.run()
    finally:
        # UNDER THE LOCK, because a worker thread may still be inside a tool holding
        # the terminal this is about to close.
        with LOCK:
            _close_held_session()


if __name__ == "__main__":
    main()
