"""MCP server owning one live DOSBox-X session, so a question costs milliseconds.

WHY AN MCP AND NOT A SCRIPT.  The expensive part is never the question, it is the state:
each shell command is a fresh process, so the emulator dies between one question and the
next and every follow-up pays another boot.  Held open here, the state is reached once, a
question through the debugger console costs its round trip, and one that never touches the
terminal (`log`, `status`) costs nearly nothing.  What a question costs is measured when a
decision needs it, and the measure lives in the commit that took it: every tool going
through the console waits for the end of its reply by construction, which is why a bare
pseudo-terminal round trip under-prices a real question.

WHAT IT DELIBERATELY DOES NOT DO.  A golden, or any byte-for-byte comparison, stays
in a batch run: a batch reaches an EXACT frame, identical across runs, and a live
session sits wherever the last question left it.  That is not a gap to be closed
later, it is the reason both exist.

SAVE STATES.  The state tools (`state_save`, `state_load`) are the debugger's own SAVESTATE
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
window, and writing `RUNWATCH` a second time does NOT turn it off, so the session is lost.
A tool with no way back leaves the caller holding a wedged session and a terminal nobody can
read, which is worse than not having it.  Anyone picking this up again needs to find the OFF
switch FIRST.  The tools that do ship stop the machine deliberately (`run_to`), step it
one instruction at a time (`step`), or arm a watch and leave it stopped (`watch`). `run_to`,
`run_for`, `trace` and `screen_wait` interrupt at their bound and always hand the debugger back;
`resume`'s bound leaves the machine running, and its reply says so.  The difference from
`RUNWATCH` is that the state is REPORTED and the session is still usable.

HONESTY, wired into the contract rather than into a prompt:

- `start` refuses a session it cannot reproduce -- an unreadable config or working
  directory, a watched session with no placement flags, a session with no bound or
  with one so large it bounds nothing -- and refuses it BEFORE the process exists.
  When a session comes up but never reaches its debugger, it is CLOSED before the
  refusal is returned: a guarantee that leaves alive what it just declared invalid is
  not a guarantee.
- A read that found nothing says WHICH nothing.  "No line matched" is an answer;
  "there is no instrumentation to match against" is INVALID, and a caller that cannot
  tell them apart reports a broken instrument as a clean result.
- EVERY reply carries the session's state, `altered` included -- the INVALID ones
  too.  An INVALID answer is the one a caller reasons hardest about, and it is the worst
  one to hand over with no trace that the machine had been written to.
- A PATH A CALLER GIVES IT IS ABSOLUTE OR `~`-LED, judged by scry-core's one judge
  (through `dosbox_paths`): `~` is expanded, a relative path is refused, and the refusal
  names the argument.

The server knows no project: the conf, the working directory, the program and the
window flags all come from the caller, so the same server serves every DOS project.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

from mcp.server.mcpserver import Context
from pydantic import Field

# THE FILE IS NOT CALLED `server.py`, and that is not fussiness. Another server may install
# a top-level `server` module, and in an environment that holds both packages (or one
# pytest process that imports both) `import server` binds to whichever was imported
# first, silently, and a suite starts testing the wrong program while every case still
# passes for the other one.
#
# The session module lives next door, and this file starts in two ways: as a script
# (which puts its directory on sys.path) and as the package's installed entry point
# (which does not). It is APPENDED and not inserted at position 0: at the front it
# would shadow the standard library for the whole process, so a file landing beside
# this one named `select.py` or `signal.py` would replace the module this session
# depends on -- the same silent-wrong-import hazard, installed by the fix for it.
sys.path.append(str(Path(__file__).resolve().parent))

from scry_core import (  # noqa: E402
    fresh,
    judges,
    media_tools,
    narrowing,
    process_name,
    recording,
    screen_map,
)
from scry_core import presence as scry_presence  # noqa: E402
from scry_core import strict_arguments as strict  # noqa: E402
from scry_core.progress import bridge  # noqa: E402

import dosbox_advance as advance  # noqa: E402
import dosbox_arming as arming  # noqa: E402
import dosbox_binary as binaries  # noqa: E402
import dosbox_captures as caps  # noqa: E402
import dosbox_checks as checks  # noqa: E402
import dosbox_code as code  # noqa: E402
import dosbox_comments as comments  # noqa: E402
import dosbox_console as dcons  # noqa: E402
import dosbox_dac as vgadac  # noqa: E402
import dosbox_dump as dumping  # noqa: E402
import dosbox_find as finder  # noqa: E402
import dosbox_inputs as inputs  # noqa: E402
import dosbox_lifecycle as lifecycle  # noqa: E402
import dosbox_logs as dlogs  # noqa: E402
import dosbox_machine as machine  # noqa: E402
import dosbox_media as media  # noqa: E402
import dosbox_paths as paths  # noqa: E402
import dosbox_placement as placement  # noqa: E402
import dosbox_presence as dpresence  # noqa: E402
import dosbox_retrace as retrace  # noqa: E402
import dosbox_running as running  # noqa: E402
import dosbox_screen as screen  # noqa: E402
import dosbox_sequence as sequence  # noqa: E402
import dosbox_session as ds  # noqa: E402
import dosbox_state as st  # noqa: E402
import dosbox_summaries as one_line  # noqa: E402
import dosbox_trace as tracing  # noqa: E402
import dosbox_vga as vga  # noqa: E402
from dosbox_mcp import LOCK, RECORDER, registered_tools, tool  # noqa: E402
from dosbox_mcp import mcp as mcp  # noqa: E402  (the probe and the clients read `server.mcp`)
from dosbox_running import live  # noqa: E402
from dosbox_state import STATE  # noqa: E402

# ------------------------------------------------------------------- session: the build

@tool("Check the build", summary=one_line.build_check, read_only=True)
def build_check(binary: str = "") -> dict[str, Any]:
    """Whether this server's PRECONDITIONS hold: a DOSBox-X binary resolves and that build
    carries the DEBUGGER. Run it BEFORE `start`; it REFUSES while a session is live
    (answering means starting a second emulator). `binary`: the absolute path of the build to
    ask about; omitted, the `DOSBOX_X_BINARY` variable, else the PATH's `dosbox-x`, as `start`
    resolves it; a named build that does not resolve is refused, never replaced. Reply:
    `binary` (the absolute path), `binary_origin` (`argument`, `DOSBOX_X_BINARY` or `PATH`),
    `version` (the build's first line, or `{available: false, why}`), `debugger`,
    `heavy_debug` (the build carries the debugger's CPU log, which `trace` needs), and INVALID
    naming the precondition that fails; `heavy_debug: false` is an answer, and it is `trace`
    that refuses such a build. It is about the build, never about a reading.
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
    try:
        got = subprocess.run(
            [resolved.path, "-helpdebug"], capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL,
            # WHAT PROTECTS THIS CALL IS THE TIMEOUT, AND NOTHING ELSE. No headless
            # setting is passed (`-set "sdl videodriver=dummy"` is a session's, and
            # headless is the application's setting, never an environment variable), and
            # `env=None` is `subprocess`'s DEFAULT, inherit the parent environment: it
            # sets nothing at all. The risk is real (this build does not refuse an
            # option it does not know, it starts), so the bound below is what stands in
            # front of it.
            timeout=20)
    except subprocess.TimeoutExpired:
        raise ds.Invalid("host_failed",
            f"`{resolved.path} -helpdebug` did not return in 20 s. On this emulator an "
            f"option it does not recognise does not fail, it hangs, so that is what "
            f"a build without this option looks like") from None
    text = got.stdout + got.stderr
    has_debugger = "-break-start" in text
    if not has_debugger:
        raise ds.Invalid("host_failed",
            f"`{resolved.path}` does not list `-break-start`, so it was built without the "
            f"debugger. The readers of the machine (`registers`, `read_memory`, `memdump`, "
            f"`step`, `debug`), the breakpoints, the watches and the symbol placement all "
            f"need it; the guest's log (`log`, `log_wait`), the captures and the "
            f"in-guest input do not")
    return st.reply(**binaries.facts(resolved), debugger=True,
                    heavy_debug=binaries.heavy_debug(resolved.path), tools=registered_tools())


# ---------------------------------------------------------- session: start, status, close

@tool("Start a DOSBox-X session", summary=one_line.start, on_cancel="kill")
def start(conf: str, cwd: str, session_seconds: int, shared: bool = False,
          window_flags: list[str] | None = None, flags: list[str] | None = None,
          break_on_int3: bool = False, program: str = "", logfile: str = "",
          capture_video: bool = False, captures_dir: str = "",
          plan: list[dict[str, Any]] | None = None, settle_seconds: float | None = None,
          input_port: int = 0, state_dir: str = "", binary: str = "",
          background: bool | None = None,
          presence: Annotated[bool, Field(description=scry_presence.ARGUMENT)] = True,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Open ONE live DOSBox-X session from your conf, parked at the debugger, stopped and
    ready. Refuses while a session is live.

    Every path is absolute or `~`-led: `cwd`, the emulator's working directory, there; `conf`;
    `logfile`, its directory there; `captures_dir` and `state_dir`, created with their parents.
    `session_seconds`: the session's REQUIRED lifetime, at most {SESSION_MAX_S} s; `close` is
    the act. `shared`: watched, in a window `window_flags` places; false, headless.
    `window_flags` and `flags` (the emulator's own options, after this server's defaults) are
    argv tokens, a `-set` value ONE token with its spaces: `["-set", "sdl display=1"]`.
    `break_on_int3`: the guest's `int 3` stops at the debugger. `logfile`: the guest's E9
    channel, without which `log`, `log_wait`, `expect` and `drive` have none. `program` runs
    with `-c` AFTER the conf's autoexec (which must not `exit`); `capture_video` records it.
    `plan`: operations run on the fresh session with `perform`'s rules, `settle_seconds`
    (default {SETTLE_S}, and only with a plan) bounding each wait. `input_port`: COM1's TCP port
    for the input (`0`: a free one); the conf's autoexec runs the reply's `stub` first, or
    `program` loads it. `state_dir`: what `state_save` writes to (`save` under `cwd`). `binary`:
    the build to run; omitted, `DOSBOX_X_BINARY`, else the PATH's `dosbox-x`. `background`:
    `true` behind, your focus kept; `false` in front; omitted, by `shared`.

    Reply: `shared`, `ready_after_s`, `argv`, `binary`, `binary_origin`, `version`, `stub`,
    `input_port`, `background`, `presence`, and `rearm_refused` (why) when stored raw
    breakpoints could not be re-armed; with `plan`, the sequence account, the start facts
    under `start`.

    Refused before anything starts: a path not absolute, an unresolved binary, a missing
    conf, `cwd` or `logfile` directory, `session_seconds` out of range, `shared` without
    `window_flags` or headless with them, a glued or shredded `-set`, `capture_video`
    without `program`, an `input_port` outside {INPUT_PORT_MIN}-{INPUT_PORT_MAX} or busy.

    Reference: REFERENCE.md, The session.
    """
    return lifecycle.start(conf, cwd, session_seconds, shared, window_flags, flags,
                           break_on_int3, program, logfile, capture_video, captures_dir, plan,
                           settle_seconds, input_port, state_dir, binary, background,
                           presence, bridge(ctx), _step_ops)


@tool("Session status", summary=one_line.status, read_only=True)
def status() -> dict[str, Any]:
    """What the session is right now. Safe on a running guest. It records a stop no tool has
    reported (`stopped_on_its_own`) and applies what was queued while the guest ran
    (`applied_on_stop`).

    Reply: `session`, `alive: false` when there is none (under `status: "ok"`: nothing
    running is an answer). The same block rides on EVERY reply of every tool:

      pid                     the emulator process's pid.
      alive                   the emulator process is up.
      running                 the guest runs; false parked at the debugger.
      altered                 something here WROTE to the guest: a later measurement is of a
                              forced state.
      conf                    the config the session was started from.
      conf_digest             a digest of that file's content AT START.
      conf_changed_on_disk    the file changed since (`false` when GONE, unavailable unreadable).
      watched                 it was started to be looked at, so a window was placed.
      bound_s                 the ceiling the session was given.
      elapsed_s               how much of that is spent.
      terminal_bytes_dropped  nonzero: a screen delta had a hole in it.
      drain_alive             the terminal reader runs; dead, reads return nothing.
      drain_ended             why that reader stopped, present once it has.
      captures                `off`, or where a `capture_video` session records.
      state_dir               where `state_save` writes and `state_list` reads.

    At the top: `alive` and `running` again, `last_stop` (`stop_seq`, `pc`, `attribution`,
    `since_s`, `wall_at`; the park after `start` is stop 1; unavailable with no session or a cut
    survey), `pending` (asked while the guest ran: `arm` refs, a `disarm` count,
    `symbols_load`), `presence` (`true` drawn, `false` asked off, or why not), and with a
    session its stop's `pc` (absent while it runs) and `cpu_mode` (`real`, `protected`,
    `paged`; unavailable while it runs), and `declarations`, this server's own counted
    (`breakpoints`, `watches`).

    Reference: REFERENCE.md, What every reply carries.
    """
    if STATE.session is not None and STATE.session.alive():
        running.drain_if_stopped(STATE.session)   # `status` asks for no session, but uses one
    block = st.session_block()
    return st.reply(alive=block["alive"], running=block["running"], last_stop=STATE.dated(),
                    pending=STATE.pending_summary(), **running.status_facts(STATE.session),
                    presence=lifecycle.presence_shown(STATE.session))


@tool("Close the session", summary=one_line.close, session_before=True, on_cancel="kill")
def close(ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """End the session deliberately rather than waiting for its bound. Reports its progress
    while the emulator takes its time to leave.

    Reply: `closed`, `ended_by` (`quit`: the emulator left on the first signal, which is what
    a session launched here does, program loaded or not, because `start` turns the quit
    warning off; `killed`: it ignored the signal, a conf that puts the warning back or a
    guest wedged, and SIGKILL ended it; `died`: it had already exited when this was called;
    `none`: nothing to close), `exit_code` (an integer, or unavailable with its `why`:
    SIGKILLed and still not reaped, an emulator may still be on the machine, or not read).
    `session` describes the state as it was BEFORE closing, so its `pid` is the process this
    call ended.
    """
    return lifecycle.close(bridge(ctx))


# ------------------------------------------------------------------ the guest's own log

@tool("Read the log", summary=one_line.log, read_only=True)
def log(pattern: str, channel: str, limit: int = 40, labels: bool = False) -> dict[str, Any]:
    """The session's log, one `channel` of it, filtered in the server by a regex.

    `channel` is `guest` (the program's own 0xE9 instrumentation, one line per write),
    `emulator` (DOSBox-X's own lines, the categories its `log` section names) or `all` (the
    file in order, each line tagged `[guest] ` or `[emulator] `); `process` names the
    emulator's stdout, which here is the debugger's terminal, and is refused by name.
    `pattern` is a Python regular expression; `limit` keeps the NEWEST
    matching lines; `labels=True` adds `labels`, how many returned lines carry each first
    word (the guest's own `BOOT`, `PERF`, `UI`...), one glance at who is talking. Needs a
    session started with `logfile`. Works on a running guest (and, like every tool, applies
    what was queued while the guest ran if it finds the machine stopped, saying so in
    `applied_on_stop`).

    Reply: `channel`, `lines` (the newest `limit` matches, in order), `lines_total` (how many
    matched IN ALL, not how many came back), `truncated`, and `labels` when asked. An empty `lines`
    is an answer: the channel is there and nothing matched.

    INVALID, with `code` and `message` saying which: no `logfile` on this session; the log
    does not exist yet; the guest channel holds no instrumentation at all; `limit` outside
    1..{LOG_LIMIT_MAX} (above that, narrow the pattern); a
    pattern that does not compile; a channel that is not one of the three; the session is
    gone. For "when did X happen, and wait if it has not" use `log_wait`.
    """
    lines, total = live().log(pattern, limit, channel)
    reply: dict[str, Any] = dict(pattern=pattern, channel=channel, lines_total=total,
                                 truncated=total > len(lines), lines=lines)
    if labels:
        reply["labels"] = dlogs.label_counts(lines)
    return st.reply(**reply)


@tool("Wait for a log line", summary=one_line.log_wait, read_only=True, on_cancel="none")
def log_wait(pattern: str, channel: str, seconds: float = 30.0,
             ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """WHEN a line of `channel` matching `pattern` was logged: at once if it already was,
    else wait for it. Reports its progress while it waits.

    `channel` as in `log` (`guest`, `emulator`, `all`); `pattern` is a regex over that
    channel; `seconds` bounds the wait. It reads what the log ALREADY holds first, so a line
    that went past before you asked is still found. Works on a running guest (the usual
    case: a guest writing traces is a guest that runs).

    Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the FIRST match; `log` is the tool
    for the newest), `already` (it was in the log before this call: history, not something you
    were present for), `waited_s` (0.0 when already), `lines_before`, `lines_total`,
    `arrived_during`, `lines_examined`, `since_mark`; when the bound ran out, `verdict`
    `TIMEOUT` with `pattern`, `channel`, `arrived_during`, `lines_examined`, `waited_s`,
    `since_mark` and a `note` (the guest still runs). `status: INVALID`: `wait_stopped` when the
    machine is STOPPED and the log does not already hold the line (a stopped guest writes
    nothing; the refusal names `pattern` and `last_stop`, and a stop that lands DURING the wait
    is reported the same way after one last read of the log), `session_broken` when the emulator
    went away. No `logfile`, a bad `seconds` (outside (0, {WAIT_MAX_S}]), an unusable regex or
    an unknown channel is refused. A log that does not exist YET is not refused: that is the
    ordinary state right after `resume`.

    The moment it hands back is for choosing an address to `run_to` or `watch` on the NEXT
    run: the guest is usually still running when this returns, and the console tools refuse
    then. `expect` on `send_keys`/`drive` is this same wait on the guest channel, from a
    mark taken before the act.
    """
    session = live()
    try:
        got = session.log_wait(pattern, seconds, channel, progress=bridge(ctx))
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
    """The register pane as a mapping (`EAX`, `EIP`, `CS`, `DS`, ... as hex strings).
    Needs the machine stopped at the debugger; INVALID when no pane came back, and that
    refusal carries `last_stop` and the tools that do answer while the guest runs.
    `from_last_stop=True` hands back the registers AS THEY WERE at the last stop, marked
    `superseded: true` with `last_stop`, never as the current value; INVALID before any stop.
    """
    if from_last_stop:
        live()
        if not STATE.last_stop:
            raise ds.Invalid("no_stop", "no stop yet in this session, so there are no last-stop "
                             "registers to hand back")
        return st.reply(regs=dict(STATE.last_stop["registers"]), superseded=True,
                        last_stop=STATE.dated())
    return st.reply(regs=live().registers())


@tool("Read memory", summary=one_line.read_memory, read_only=True, replay=("hex",))
def read_memory(ref: str, length: int = 16) -> dict[str, Any]:
    """`length` bytes at `ref`, a symbol or a `SEG:OFF` (the colon is the tell: a bare
    number is read as a symbol name), as `hex`;
    beside them the data-view ROWS the debugger's `D` printed, which is where the bytes come
    from. Needs the machine stopped.

    Reply: `hex` (`length` bytes from the address), `length`, `rows` (the data view's rows
    of sixteen bytes, as many as the debugger's window showed), and `seg_off`, where the
    ref resolved to. `length` is 1 to {READ_MAX}, and the rows have to hold it from the
    address: a view that showed fewer bytes than asked is refused (`readback_refused`)
    naming what it held, and above the view the answer is `memdump`. INVALID unless the
    address asked for is among the rows returned, so a cut repaint is refused rather than
    handed back shifted. An absent or ambiguous symbol is refused.
    """
    session = live()                 # `length` is judged by the registry, before the call
    seg, off = placement.read_target(ref, "DS", session)
    rows = session.read_memory(seg, off)
    return st.reply(ref=ref, seg_off=st.seg_off(seg, off), length=length,
                    hex=dcons.bytes_of_rows(rows, off, length), rows=rows)


@tool("Disassemble code", summary=one_line.disassemble, read_only=True)
def disassemble(ref: str, length: int = 16) -> dict[str, Any]:
    """Decode `length` bytes (1..{DISASM_MAX}) from `ref`, a symbol or a `SEG:OFF`, one x86
    instruction a line, on the host (capstone): the debugger has no disassembly command. The
    listing completes the instruction that straddles the end, so it may run a little past
    `length`, unless the segment ends first. Needs the machine stopped.

    The width is the segment's own D bit: real mode 16-bit; in protected mode the pane's
    `Pr32`/`Pr16` for CS, `SELINFO` for a selector another segment register holds, the
    descriptor listings (which need `logfile`) for one no register holds.

    Reply: `seg_off`, `length`, `code_bits` (16 or 32) and `code_bits_from` (where
    the width was read), `lines` (`SSSS:OOOOOOOO BYTES TEXT`; a byte no instruction starts
    with is `.byte 0x..`), `flow` (per line: `call`, an interrupt included; `branch`; `return`;
    `sequential`; `unknown` for such a byte), `flow_source` (`capstone`), and with a symbol
    table loaded `resolved`: every direct call or branch target (`kind` `target`, its segment
    the line's own or the far pointer's) and direct memory operand (`kind` `memory`,
    `register` the segment register it is read through, at its value at this stop), each with
    `line`, `operand`, `seg_off`, `addr` (the linear address), and the nearest `symbol` with
    `delta`, unavailable outside the table's span; a row that could not be placed has `addr`
    unavailable too. A register-relative operand is not resolved.

    Refused: `length` outside 1..{DISASM_MAX}, and one that runs past the end of a 16-bit segment
    (IP wraps there), naming the most bytes from there; `memdump`'s refusals apply to the
    bytes read (a leftover dump file, a protected-mode range past offset 0xFFFF without
    `logfile`).

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(ref=ref, **code.disassemble(live(), ref, length))


@tool("Guess the call stack", summary=one_line.call_stack, read_only=True)
def call_stack() -> dict[str, Any]:
    """A heuristic chain of the callers of the routine the stop is in, never a verdict: the
    frame pointers walked (C's `push bp`/`mov bp, sp` and the `enter` frame), each return
    address kept only when a call instruction ends exactly there. Needs the machine stopped.

    Row 0 is the stop. Outside its routine's frame (a `push bp` or `enter` at the routine's own
    address, the `mov bp, sp` right after the push, the `ret` that leaves it) the caller is read
    off the stack pointer (`via` `entry`); then the chain from BP (`bp_chain`): the return
    beside each frame, near or far as the call before it says. A return is named by the
    routine its call is in. The walk ends at a zero
    or non-rising saved frame pointer, a frame past the stack segment's end, a return no call
    precedes (not listed), a return outside the loaded table (listed), or its bound.

    Reply: `heuristic` (always true), `code_bits`, `calls` (innermost first: `seg_off`,
    `addr` (linear), `symbol` and `delta`, unavailable outside the table's span,
    `via`, `call` (the call instruction at the call site, unavailable on row 0), `bp` (the
    frame it was read beside, unavailable on rows 0 and `entry`)), `truncated` (the bound was
    reached), `ended_why` (a read that failed says so here). Refused when the register pane
    shows no SS, ESP or EBP. A routine that keeps no frame pointer is invisible to it: its
    caller's caller is listed in its place, or nothing.

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(**code.call_stack(live()))


@tool("Dump memory to a file", summary=one_line.memdump, replay="drop")
def memdump(ref: str, length: int, dest: str) -> dict[str, Any]:
    """`length` bytes of memory to a FILE at `dest`, returning `ref`, `seg_off`, `length`,
    `path` and `bytes`.

    `ref` is a symbol or a `SEG:OFF` (colon required); `dest` is an absolute path, its
    directory there. Needs the machine stopped. The size
    handed back is checked for EQUALITY against `length`. Refused rather than overwriting: a
    dump file already sitting where the debugger writes (the emulator's working directory),
    a dangling link there included, or at `dest`, and a `dest` directly in that directory (a
    subdirectory of it is fine). An absent or ambiguous symbol is refused.

    Past offset 0xFFFF the debugger would wrap a 16-bit segment or read zeros past a limit: in
    real mode the range is read in 64 KiB windows, so it holds the bytes really there, up to
    `FFFF:FFFF`; in protected mode the selector's descriptor is read (which needs `logfile`)
    and a 16-bit segment, a range past its limit, or a selector with no descriptor is refused.
    Inside 0 to 0xFFFF the limit is not judged and the debugger reads zeros past it.
    """
    session = live()
    ds.console_listening(session, "a dump")
    seg, off = placement.read_target(ref, "DS", session)
    dumped = dumping.dump_range(session, seg, off, length, paths.absolute("dest", dest))
    return st.reply(ref=ref, seg_off=st.seg_off(seg, off), length=length, path=str(dumped.path),
                    bytes=dumped.path.stat().st_size)


@tool("Find bytes in memory", summary=one_line.find, read_only=True)
def find(data_hex: str, ref: str, length: int) -> dict[str, Any]:
    """Every address holding the bytes `data_hex` (whole hex bytes, two digits each) in
    `length` bytes from `ref`. `ref` and `length` are required: there is no default range.

    The debugger has no pattern search of its own, so the range is dumped (the `memdump`
    route, its windows past offset 0xFFFF included, into a scratch file of this call's own
    that is gone before the reply) and searched exactly. Needs the machine
    stopped; `memdump`'s refusals apply (a leftover dump file where the debugger writes). In
    real mode a hit past offset 0xFFFF is named from its own paragraph. For a VALUE narrowed
    by what it does over time, the debugger's own scanner is `scan_start` / `scan_filter` /
    `scan_clear`.

    Reply: `seg_off`, `length`, `span` (what was examined:
    `from`, `length`, `source`, here always `ref+length` since the range is the caller's
    own), `hits` (`SEG:OFF` in address order, at most {HITS_MAX}: when truncated, the HIGHEST
    addresses are kept), `hits_total` (every hit), `truncated`.
    """
    # THE HEX BEFORE THE MACHINE, which is where `write` already asked it and where this did
    # not: the same argument of the same server answered `bad_argument` through one tool and
    # `no_session` through the other. Whether the bytes are hex is as true with no machine as
    # with one; where `ref` POINTS is not, and that still waits below.
    pattern = finder.check_pattern(data_hex)
    session = live()
    ds.console_listening(session, "a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.find(session, seg, off, length, pattern))


@tool("Start a value scan", summary=one_line.scan_start, replay="drop")
def scan_start(ref: str, length: int, cell_bytes: int = 1) -> dict[str, Any]:
    """Open the debugger's value scanner (`MEMFIND`) over `length` bytes from `ref`, in cells
    of `cell_bytes` (1, 2 or 4, little-endian): every cell is a candidate
    until `scan_filter` narrows them. The debugger holds ONE scan at a time, so a scan
    already open is refused in its words: `scan_clear` it, or keep filtering it.

    This is the cheat-search loop for a program with no map: open the scan, play, filter
    by what the value must have done (`=` a known value, `!` with no value for "changed
    since the scan opened"), until the survivors are the cells that move the way the
    program does. `length` is a whole number of cells.
    Needs the machine stopped. Reply: `seg_off`, `length`, `cell_bytes`, `addr` (the linear
    address the scan opened at), `hits_total` (every cell is a candidate).
    """
    session = live()
    ds.console_listening(session, "a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.scan_start(session, seg, off, length, cell_bytes))


@tool("Filter the value scan", summary=one_line.scan_filter, replay="drop")
def scan_filter(operator: str = "=", value: judges.NumberArg | None = None,
                limit: int = finder.HITS_DEFAULT) -> dict[str, Any]:
    """Keep the scan's cells whose current content satisfies `operator` (`=`, `!`, `>`,
    `>=`, `<`, `<=`) against `value`; with no `value`, against what each cell held when
    `scan_start` opened the scan: `!` alone keeps the cells that CHANGED since then, `=`
    alone those that did not, `>` alone those that grew. The debugger's `MEMS`.

    `value` is an integer or a `0x` hex string; one wider than the cell of a scan `scan_start`
    opened is refused before `MEMS` is typed. Needs the machine stopped and a scan open. Reply:
    `operator`, `value`, `iterations` (the filters so far, this one included; on the closing
    reply the server's own count, unavailable for a scan `debug` touched), `closed` (a step that
    leaves NO survivor closes the scan, which is what the debugger does), `hits` (each
    survivor's `seg_off`, `addr` and current `value`), `hits_total` and `truncated`: above
    `limit` survivors (1 to {HITS_MAX}, default {HITS_DEFAULT}) `hits` is empty and `truncated`
    true, so filter again, with a larger `limit` if need be.

    THE COMMAND LINE IS LEFT CLEAN even when the answer cannot be read. The debugger eats a
    command character by character while a paged-content prompt waits, one page per
    keystroke, so a listing that ends with a page unturned swallows the front of the next
    command and strands its tail on the line, and from there every later call concatenates
    instead of running until `close`. So a listing turns its last page, and an
    `unexpected_answer` clears the line before it refuses, saying so in `line_recovered`.
    """
    session = live()
    ds.console_listening(session, "a search")
    number = None if value is None else checks.number("value", value)
    return st.reply(**finder.scan_filter(session, operator, number, limit))


@tool("Clear the value scan", summary=one_line.scan_clear, replay="drop")
def scan_clear() -> dict[str, Any]:
    """Cancel the debugger's open scan (`MEMFIND !`). Nothing open is a no-op that says so.
    Needs the machine stopped. Reply: `cleared`. An answer this cannot read clears the
    debugger's command line before refusing (`line_recovered`): see `scan_filter`.
    """
    session = live()
    ds.console_listening(session, "a search")
    return st.reply(**finder.scan_clear(session))


@tool("Debugger console command", summary=one_line.debug)
def debug(command: str) -> dict[str, Any]:
    """One raw `command` to the debugger console; the LAST resort, not the first.

    Needs the machine STOPPED at the debugger (a running guest's console takes nothing). Reply:
    `screen_delta`, the delta the screen produced for the command, capped at its last
    {DEBUG_TEXT_KEEP} characters with `screen_chars` (how much the screen produced) and
    `clipped` (whether what came back is all of it). It is a repaint of an ncurses screen,
    interleaved with the rest of the panes, not a parsed answer. For a VALUE use `registers`,
    `read_memory` or `memdump`; for the log use `log`; for a breakpoint or a watch use the tools
    that read the debugger's list back, which this does not. Refused `bad_argument` before
    anything is typed: a command that lets the guest run (`VRT`, `RUNWATCH`, `INT`, the `LOG`
    family), naming the tool that does it and reports the stop, and a command carrying a control
    character.
    """
    session = live()
    ds.console_listening(session, repr(command))
    # A SCAN COMMAND TYPED HERE moves the debugger's own count past the one `scan_filter` keeps,
    # and may open a scan at another width, so both are dropped rather than answered stale.
    if command.strip().upper().startswith(("MEMS", "MEMFIND")):
        STATE.scan_iterations = None
        STATE.scan_cell_bytes = None
    out = session.command(command)
    if not out.strip():
        raise ds.Invalid("unexpected_answer",
            f"the debugger produced nothing for {command!r}: an empty "
                         f"screen delta is not an empty answer, it is no answer")
    return st.reply(command=command, **st.delta(out, st.DEBUG_TEXT_KEEP))


@tool("Force a register", summary=one_line.set_register)
def set_register(name: str, value: judges.NumberArg) -> dict[str, Any]:
    """Write one register, READ IT BACK off the pane, and mark the session `altered` for
    good: every later reading is of a forced state, and the flag on every reply is how a reader
    three questions later knows. `name` is a register the debugger's `SR` takes (`eax`, `ax`,
    `ip`, ...); `value` is an integer or a `0x` hex string within the register's width, refused
    before anything is sent when negative or wider. Needs the machine stopped.

    Reply: `register` (the name as `SR` takes it), `regs` (the pane after the write), `value`
    (what was sent), `readback` (the register asked for as the pane shows it now, at its own
    width: eight hex digits for a 32-bit name, four for a segment register, read under its own
    name, and four for a 16-bit name, read as the low half of its 32-bit register, `ax` in
    `EAX`), `verified` (readback equals what was sent; false is not always a failure: a register
    the debugger masks is doing its job). INVALID when no pane, or a pane without that register,
    came back to read.
    """
    number = checks.number("value", value)
    out = live().set_register(name, number)
    return st.answer({"value": number, **out})


@tool("Write memory", summary=one_line.write)
def write(ref: str, data_hex: str) -> dict[str, Any]:
    """Write bytes at a SYMBOL or a `SEG:OFF` and READ THEM BACK. MODIFIES the machine:
    every later reply says so in `altered`.

    `data_hex` is whole hex bytes, two digits each, up to {READ_MAX} (the data view's reach for the
    readback; a region is not a write). The bytes go through the debugger's `SM` and the
    range is read back off the data view. Needs the machine stopped; an absent or ambiguous
    symbol is refused.

    Reply: `ref`, `seg_off`, `bytes_written` (sent), `readback` (hex read back from
    the same range), `verified` (readback equals what was sent). `verified: false` is not
    always a failure: a memory-mapped register answers what it answers; for RAM it means the
    write went nowhere. A real-mode address in the ROM range is REFUSED with nothing sent:
    measured on this build, `SM` into ROM ends the emulator instead of writing.
    """
    data = checks.write_data(data_hex)        # parsed once; the bytes travel, not the text
    session = live()
    seg, off = placement.read_target(ref, "DS", session)
    out = session.write_memory(seg, off, data)
    return st.answer({"ref": ref, "seg_off": st.seg_off(seg, off), **out})


# ------------------------------------------------------------- advancing the machine

@tool("Resume the machine", summary=one_line.resume, on_cancel="none", replay="wall")
def resume(e9: str = "none", e9_filter: str = ".",
           e9_stamp: str = "", seconds: float = 0.0, detail: bool = False,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Let the machine run (F5, sent once). With `seconds` at zero (the default) it comes back
    at once, no verdict; with a bound it waits up to `seconds` for a stop, listening for the
    debugger's prompt as `run_to` does and reporting its progress: `verdict` `OTHER_STOP` with
    the full stop when one lands, or `TIMEOUT` with `waited_s` and a `note`, LEAVING IT RUNNING
    (unlike `run_to`, which interrupts at its bound); `seconds` is 0 or a bound up to
    {WAIT_MAX_S}. Needs the machine stopped: a guest already running is refused `not_stopped`,
    since an F5 there does nothing and an `ok` would read like a release.

    Nothing has to be declared first: `stop` brings a running guest back, headless or windowed.

    Reply: a reply that stopped (an F5 that never left the debugger is a stop too) carries
    {STOP_FIELDS}. `e9` is OFF by default: `"all"`, `"lines:N"`, `"since"` (since the previous
    stop) or `"seconds:N"` (needs `e9_stamp`, a regex with ONE group capturing each line's own
    time), filtered by `e9_filter`. With `detail=True`, `screen_delta`: the debugger's repaint
    for the F5, a POSITIONAL tail capped at its last {DETAIL_TEXT_KEEP} characters (`clipped`),
    never a value; without it `omitted` names it.

    Reference: REFERENCE.md, Advancing the machine.
    """
    return advance.resume(e9, e9_filter, e9_stamp or None, seconds, detail, bridge(ctx))


@tool("Stop a running machine", summary=one_line.stop, on_cancel="stop", replay="wall")
def stop(ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Bring a RUNNING guest back to the debugger and survey the stop, headless or windowed
    alike: the session sends `BREAK` down the emulator's own debugger channel (upstream's
    `mcp_server`), which reaches the debugger while the guest runs, with no window, no menu and
    nothing taken from whoever is using the screen.

    THE MACHINE STOPS WHEREVER IT IS, and that is not always in the program: a DJGPP guest
    spends part of every frame in real-mode BIOS handlers (`F000:xxxx`), and a stop landing
    there has no protected-mode selector to place a symbol against, so a watch on a
    protected symbol reads `unarmable` at that stop, and a stop lands there often.
    `run_to` a symbol of the program, or `step` a few times, to get back to its code.

    `unarmable` AND `unresolved` ARE DIFFERENT ANSWERS and the difference is worth holding:
    `unarmable` means the symbol IS in the table and its address cannot be worked out at
    this instant (this case), while `unresolved` means the table does not carry the name at
    all. A session that met `unresolved` here was being told the truth about its TABLE, not
    about the stop: `symbols_load` accumulates its batches, so a name missing after several
    loads is one none of them carried.

    Reply: `interrupted` (`true` with the full stop reply, `via: "break"` and `waited_s`, the
    seconds from the request to the debugger's prompt; `false` when the machine was already
    stopped, with `last_stop` and a `note`). A `BREAK` whose prompt never comes is
    `not_settled`: asking again is allowed, and if `stop` fails as well, `close` then
    `start`.
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
                            "(a cut pane; the next contact retries)"))
    waited = session.break_in()
    return running.stop_reply(session, interrupted=True, via="break", waited_s=waited)


@tool("Step instructions", summary=one_line.step)
def step(count: int = 1, mode: str = "into",
         e9: str = "none", e9_filter: str = ".",
         e9_stamp: str = "") -> dict[str, Any]:
    """`count` instructions, one at a time, `mode` `into` (F11, the default) or
    `over` (F10), each step READ BACK. Needs the machine stopped.

    Reply: `mode`, `asked`, `before` and `after` (each `SSSS:OOOOOOOO`),
    `instructions_completed` (how many steps actually landed, not how many were asked; fewer
    when the machine left the debugger, e.g. an `over` across a call that never returns, which
    `session.running` says, so the remaining steps were not sent), `moved`, `stalled` (steps
    that did not change position: a swallowed keystroke), and when it stopped {STOP_FIELDS}.
    `e9` is `none`
    (default), `all` (the whole log), `lines:N` (the last N), `since` (every line since the
    previous stop) or `seconds:N` (needs `e9_stamp`), filtered by `e9_filter`. A settle per
    step; for a longer run use `run_to`.
    """
    session = live()
    out = cast(dict[str, Any], session.step(mode=mode, count=count))
    ran_away = bool(out.pop("running"))
    out["instructions_completed"] = out.pop("completed")
    out["before"], out["after"] = (f"{w['cs']}:{w['eip']}" for w in (out["before"], out["after"]))
    # A step that STOPPED carries the full stop reply; one that ran away (a CALL that never
    # returned) left the machine running, which `session.running` says, and a running machine
    # has nothing to read.
    return running.stop_or_base(session, not ran_away, e9, e9_filter, e9_stamp or None, out)


@tool("Run to a place, with a control", summary=one_line.run_to, on_cancel="stop")
def run_to(ref: str, control: str, seconds: float = 30.0,
           e9: str = "none", e9_filter: str = ".",
           e9_stamp: str = "",
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run until a SYMBOL or a `SEG:OFF`, and say where it really stopped. Reports its
    progress while it waits.

    `ref` is a symbol name from the loaded table or a raw `SEG:OFF` in hex (the colon is the
    tell); the server derives the debugger's address from the machine's own mode, arms a
    `BP`, verifies it by reading the list back, releases the machine and waits up to
    `seconds`, INTERRUPTING the run at its bound. `control` is REQUIRED, this run's own (the
    session keeps no declared control): a second `ref` known to be HOT, armed
    beside the target and counted every time it fires, so a bound that expires with ZERO
    control hits is INVALID rather than "it did not arrive". Pick one that fires a few times a
    run: each hit costs a round trip.

    Refused before the machine moves: no control (the schema requires one, and an empty one is
    none), an absent or ambiguous name, a machine not stopped.

    Reply: `verdict` (`TARGET`; `OTHER_STOP`, another breakpoint got there first; `TIMEOUT`,
    the bound ran out and the run was interrupted where it stood), `target_disarmed` (the
    breakpoint it armed, removed on every outcome; false when that could not be confirmed),
    `waited_s`, `target`, `control_hits`, `controls` (`ref`, `at`, `hits_in_run`, `removed`), a
    `note` explaining a non-arrival, and {STOP_FIELDS} (same `e9`/`e9_filter`/`e9_stamp` as
    `resume`). INVALID
    carries no `verdict`: `control_silent` (a TIMEOUT with no control hit) or
    `cut_by_other_stop` (another stop before the control fired), each with the stop surveyed;
    `not_settled` when the interrupt found no prompt.

    Reference: REFERENCE.md, Advancing the machine.
    """
    return advance.run_to(ref, control, seconds, e9, e9_filter, e9_stamp or None, bridge(ctx))


@tool("Run for frames or emulated time", summary=one_line.run_for, on_cancel="stop")
def run_for(milliseconds: int = 0, frames: int = 0, seconds: float = 30.0,
            e9: str = "none", e9_filter: str = ".", e9_stamp: str = "",
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run the machine for `frames` frames of the display, one vertical retrace each (the
    debugger's `VRT`), or for `milliseconds` of its emulated time, and come back STOPPED with
    the full stop reply. Reports its progress while it waits.

    Arguments: exactly one of `frames` and `milliseconds` above zero. By `milliseconds` it runs
    retrace by retrace until the register pane's emulated clock has risen at least that far, so
    it stops at the first retrace at or past the mark, surveying every frame to read it.
    `seconds`: the wall-clock bound, (0, {WAIT_MAX_S}]. `e9`, `e9_filter`, `e9_stamp` as in
    `resume`. Needs the machine stopped. A DOS machine keeps no frame counter, so `frames` counts
    retraces from where the call starts.

    Reply: `verdict`, `ELAPSED` (the run ran its course: every frame, or the clock at the mark),
    `OTHER_STOP` (a declared code breakpoint stopped it first, named by `attribution`) or
    `TIMEOUT` (the bound expired); `polls`, the `VRT`s answered by a stop; `emulated_before_s`
    and `emulated_after_s`, the register pane's emulated clock; `frame_before`, `frame_after`
    and `cycles`, unavailable with why; `waited_s`, and {STOP_FIELDS}. `retrace_pending: true`:
    the debugger still holds a retrace stop, which the next release meets. `note`: what the
    reply cannot prove (a declared breakpoint or watch, an unread clock). A `TIMEOUT` with a
    `VRT` still out is interrupted where it stands, its retrace left pending. INVALID
    `no_progress` when the clock did not move (over the run by frames, at any frame by
    milliseconds); `unexpected_answer` when a timed run finds no clock to start from, before
    anything runs. Advancing is not altering.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    ds.console_listening(session, "a `VRT`")
    return retrace.run_for(session, frames, milliseconds, seconds, bridge(ctx), e9, e9_filter,
                           e9_stamp or None)


@tool("Trace what a run executes", summary=one_line.trace, on_cancel="stop")
def trace(instructions: int, shape: str = "normal", dest: str = "", seconds: float = 60.0,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run the machine `instructions` instructions with the debugger's CPU log on (its `LOG`
    family), come back STOPPED with the log in a file and the full stop reply, and say which
    loaded symbols the executed addresses fall in.

    Arguments: `instructions`, how many to EXECUTE, 1 to {INSTRUCTIONS_MAX}. `shape`: `normal`
    (`LOG`: disassembly and registers), `short` (`LOGS`), `long` (`LOGL`: adds emulated time, VM and
    CR0) or `cs_ip` (`LOGC`: the address alone). `dest`: absolute, its directory there, the
    file not, not directly in the emulator's working directory; empty,
    the next free `trace-<n>.trace` in the session's captures directory. `seconds`: the
    wall-clock bound, (0, {WAIT_MAX_S}]. Needs the machine stopped, a writable working directory and
    `build_check`'s `heavy_debug`.

    The count is proved against the pane's `cc=` counter, which on the normal core moves one
    per instruction: a mismatch is `no_channel`, the file kept (a dynamic core logs at block
    boundaries: `start(flags=["-set", "cpu core=normal"])` to trace).

    Reply: `verdict`, `ELAPSED` (all ran; the file holds one line more, the stop), `OTHER_STOP`
    (a declared stopper or pending retrace first, `attribution`) or `TIMEOUT` (the bound ran
    out: the run interrupted where it stood, and what ran up to there collected); `waited_s`,
    {STOP_FIELDS}; `trace`: `path`, `bytes`, `shape`, `instructions` (executed), `addresses`
    (distinct), `unplaced` (no symbol places them), `set_path` (a JSON line per address;
    unavailable when it could not be written, said in `note`), `symbols` (per routine, the first
    {SYMBOLS_SHOWN}), `symbols_total`, `truncated`, `note` for what it cannot prove.
    `readback_refused`: the log closed early (the machine closed it before the trace stopped, so
    its lines are not what ran), is empty, or would not close; `host_failed`: the debugger was
    refused its file (`close`). Advancing is not altering.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    return tracing.trace(session, instructions, shape,
                         paths.absolute("dest", dest) if dest else None, seconds, bridge(ctx))


@tool("Run until text is on screen", summary=one_line.screen_wait, on_cancel="stop", replay="wall")
def screen_wait(text: str, seconds: float = 30.0,
                ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run the machine retrace by retrace until `text` is on the TEXT screen, and stop there.
    `text` (1 to {SCREEN_TEXT_MAX} characters code page 437 draws, not ending in a blank) is matched
    literally, case-sensitive, inside ONE row of the screen as `screen_view` reads it, trailing
    blanks dropped: a string that wraps across rows is not found. `seconds`, the wall-clock
    bound, (0, {WAIT_MAX_S}], counted from after the first read of the screen, so a short one still
    reaches the first frame; a frame's read under way when it passes is finished. Needs the
    machine stopped and a session started with `logfile`; reports its progress while it waits.

    Already on screen at the call: answered at once, the machine not moved. Otherwise each
    retrace costs a stop and five console round trips, so for a string far ahead `run_for`
    first. A frame not in a text mode is no match.

    Reply: `verdict` `TARGET` with `already`, `waited_s`, `polls` (the retraces run), `point`
    (`[column, row]` where the text begins), `line` (that row); when it ran, {STOP_FIELDS} (or
    `enrichment` unavailable, its survey cut), and a `note` when a declared watch or interrupt
    breakpoint could have made a stop it took for a retrace. The bound: `verdict` `TIMEOUT` with
    `polls`, `text` (the rows of the last text page read, absent when none was),
    `retrace_pending`, a `note` and the stop it ended at (a `VRT` still out is interrupted where
    it stands).

    Refused: a bad `text` or `seconds` (`bad_argument`, before anything is typed); a declared
    code breakpoint stopping the machine first (`wait_stopped`, with its `attribution`,
    `stop_seq`, `polls`, `retrace_pending`, `text`); a screen it cannot read, as `screen_view`
    refuses it, with `polls` and `stop_seq` after a retrace; where `stop_seq` is due and the
    stop's survey came back cut, `enrichment` unavailable instead; no `logfile`
    (`no_channel`); a running guest (`not_stopped`).

    Reference: REFERENCE.md, Input and the screen.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return retrace.screen_wait(session, text, seconds, bridge(ctx))


@tool("Save the machine state", summary=one_line.state_save)
def state_save(name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, Any]:
    """Save the machine under `name` as `<state_dir>/<name>.sav`, by the debugger's own
    `SAVESTATE` sent down the debugger channel: no window, no menu, no focus taken, headless
    or windowed. Needs a DOSBox-X that carries the command; any other build is refused
    `no_channel`, naming the command it lacks. The command needs the debugger stopped, so
    a RUNNING guest is stopped for it and released again (`paused: true`); a parked one stays
    parked. The file is read back for what it says about itself. Never overwrites. Saving
    alters nothing. `seconds` bounds the command's reply. `name`: letters, digits, `_`, `-`, a
    letter or digit first, at most {STATE_NAME_MAX}, not digits only (the emulator's slot files).

    Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`, `memory_mb`, `saved_at`
    (the state's own members, the local time it was saved), `paused`, `waited_s` (the command
    alone); `session.running` says whether the guest runs after the call.
    """
    return st.answer(live().state_save(name, seconds))


@tool("Load a machine state", summary=one_line.state_load)
def state_load(name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, Any]:
    """Load the state `name` from `<state_dir>/<name>.sav`, by the debugger's own `LOADSTATE`
    sent down the debugger channel, as `state_save` saves (same build, no window). A RUNNING
    guest is stopped for it and released again (`paused: true`), now running the loaded
    machine; a parked one stays parked, at the loaded machine's position. A state of another
    DOSBox-X version, program, memory size or machine type is refused, never asked about. It
    REPLACES the machine, so the session is altered from here on.

    Reply: `name`, `path`, the state's own members, `paused`, `waited_s`; `session.running`
    says whether the guest runs after the call.
    """
    return st.answer(live().state_load(name, seconds))


@tool("Snapshot the screen to a PNG", summary=one_line.snapshot, on_cancel="none", replay="drop")
def snapshot(dest: str = "", seconds: float = ds.SNAPSHOT_WAIT_S,
             ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """One still of the RUNNING screen, taken inside the guest through the input stub (no
    window, no menu, any session), confirmed by the new `.png` under the captures directory
    (`captures_dir`, or `capture/` under `cwd`) within `seconds`, and moved to `dest` when
    given (absolute, its directory there, not there yet).
    REFUSED with the machine parked at the debugger (the stub takes commands on the timer
    tick), on a session with no `logfile` (the command is the Delete key's scan code to an
    older stub, and only the log says which is resident), and on a guest whose log shows no
    stub, as `send_keys` is.

    Reply: `route: "guest"`, `path`, `bytes`, `sha256` (of the file), `waited_s`.
    """
    session = live()
    if session.launch.logfile is None:
        # `S` IS ALSO THE DELETE KEY'S SCAN CODE: an older stub would press it, and with no log
        # there is no announce to tell the two apart.
        raise ds.Invalid("no_channel",
            "snapshot needs the guest's E9 log to see which stub is resident (its command is "
            "a scan code to an older one): start the session with logfile=")
    inputs.require_stub(session)
    return st.answer(session.snapshot(paths.absolute("dest", dest) if dest else None, seconds,
                                      bridge(ctx)))


@tool("List the saved states", summary=one_line.state_list, read_only=True)
def state_list() -> dict[str, Any]:
    """Every state under the session's state directory, each with what it says about
    itself (`version`, `program`, `machine`, `memory_mb`, `saved_at`, `bytes`), read
    off the file without loading it. A file there that is not a state carries a `note`.
    The emulator's own numbered slot file is NOT a named state and is reported apart, as
    `working_slot`. Works on a running guest and needs no window.

    Reply: `state_dir`, `states`, `working_slot`.
    """
    return st.answer(live().state_list())


@tool("Arm an interrupt breakpoint", summary=one_line.breakpoint_interrupt)
def breakpoint_interrupt(number: int, ah: int | None = None,
                         detail: bool = False) -> dict[str, Any]:
    """Break on an interrupt, optionally on one `ah` function: `BPINT <number> [<ah>]`.

    `number` and `ah` are the debugger's HEX values given as integers: pass `0x21` (33) for
    DOS, not `21`, which would arm INT 0x15. This is how control comes BACK from a running
    guest on this platform (a host keypress cannot break in): arm it BEFORE `resume`. While the
    guest runs it is queued `pending`, as below. The declaration is STORED under its
    `BPINT ..` spelling, so `breakpoint_list` shows it and `breakpoint_clear(ref="BPINT 21")`
    removes it; arming the same interrupt again is a no-op that says `already_stored`.

    Reply: `ref`, the exact string `breakpoint_clear` takes for it (`BPINT 21`,
    `BPINT 21 AH=4B`: the debugger's own row spelling, hex, `AH=` included when `ah` was
    given), `stored`, `already_stored`, `entry`; with `detail=True` the acknowledgement's
    `screen_delta` (capped, with `screen_chars`/`clipped`), else `omitted` names them: a
    fresh arm only, since a pending or already armed one typed nothing. While the
    guest runs it is stored `pending` and armed at the next stop.
    """
    return arming.breakpoint_interrupt(live(), number, ah, detail)


# --------------------------------------------------------------- names for addresses

@tool("Load a symbol table", summary=one_line.symbols_load)
def symbols_load(path: str, base: str = "", base_from: str = "CS",
                 pattern: str = "", keep_noise: bool = False,
                 section_bases: dict[str, str] | None = None, types: str = "",
                 ) -> dict[str, Any]:
    """Load a toolchain's TEXT symbol list into the debugger and the server, so every other tool
    takes NAMES. Wants the machine stopped INSIDE the program whose symbols these are (a breakpoint
    on INT 0x21, or INT 0x31 with ah=2 for a DJGPP program). With an explicit `base` it also works
    while the guest RUNS: the table answers at once and the debugger's list loads at the next stop
    (`pending: true`).

    Arguments: `path`, a file (an absolute path): `nm` output, a GNU `ld` map, a
    Borland TLINK/TASM map, or an Open Watcom map. A FLAT list (`nm`, GNU, real-mode Borland) takes
    `base`: measured by default off the selector named by `base_from` (default `CS`, right under
    DPMI), REQUIRED in real mode as HEX TEXT, `load_segment * 16` (segment 0x0800 is `"0x8000"`).
    A SECTIONED map (32-bit Borland, Watcom) takes `section_bases`, hex per section index.
    `types`: a UTF-8 file typing symbols in the value grammar. `pattern`: a regex SEARCHED in the
    full name (`^_snd` keeps a prefix); `keep_noise` keeps section and compiler-label symbols.

    Refused (INVALID): both `base` and `section_bases`; a sectioned map with no `section_bases`; a
    real-mode map with no `base`; a running machine with no explicit base; a file whose symbol rows
    were mostly unreadable.

    A second load ADDS to the first, on both sides; a load with a different base REPLACES the
    table here (`table_mode` says which), while the debugger keeps every row it was given until
    `close`.

    Reply: `parsed`, `kept`, `loaded` (the debugger's own count), `table_mode`,
    `table_total`, `truncated_names`, `renamed` (names the debugger shortened with `~n`),
    `disambiguated`, `unreadable`, `excluded_sections`, `excluded_pattern`,
    `excluded_unplaceable`, `overlay_idle`, `unencodable`, `unencodable_total`, `symbols_typed`,
    `bytes`, `descriptor`, `pending`, `base_from`, `base`, `limit`, and `declarations` (the
    stored breakpoints re-armed: `rearmed_refs`, `stale`, and counts for `unresolved`,
    `ambiguous`, `unarmable`).

    Reference: REFERENCE.md, Names for addresses.
    """
    session = live()
    src = paths.input_file("path", path, "symbol file")
    typed = placement.read_types(types) if types else {}
    return placement.load(session, path, src,
                          placement.hex_arg("base", base) if base else None,
                          base_from, pattern or None, keep_noise,
                          None if section_bases is None else placement.hex_bases(section_bases),
                          rearm_declarations=arming.rearm_declarations,
                          take_the_map=comments.park_rows_take_the_map, types=typed)


@tool("Look a symbol up", summary=one_line.symbols_find, read_only=True)
def symbols_find(name: str = "", offset: int | None = None,
                 section: int | None = None,
                 linear: str = "", limit: int = 10) -> dict[str, Any]:
    """Look a symbol up in the FULL table `symbols_load` parsed (untruncated names).

    `name`: exact match, else prefix matches, up to `limit` (`truncated` says if it
    bit). `offset` (a toolchain offset) or `linear` (a linear address as hex text, `0x1000`;
    a `SEG:OFF` is `read_memory`'s, not this one's),
    optionally with `section`: what am I inside? -- the nearest symbol AT OR BELOW and the
    distance above it (this table carries no sizes). One question per call.

    Reply: by name, `query`, `symbols_total` (how many) and `symbols`, a list with `name`, `offset`,
    `addr` (linear), `section`, `idle` (Borland's own mark on that row, always false for `nm`/GNU);
    by offset or linear, the nearest symbol's own fields and `delta`. INVALID with no table
    loaded, or `limit` outside 1..{SYMBOLS_LIMIT_MAX} on the `name` question (a prefix matching
    more is a listing, not a lookup).
    """
    # THE SESSION IS ASKED FOR FIRST, as every read tool asks. The table is forgotten when
    # the session OBJECT changes, and the burial of a session that died on its bound happens
    # inside `live()`: without the call a table would outlive the program it was measured on,
    # and answer `ok` with a linear address for a process that is gone.
    live()
    return placement.find(name or None, offset, section, linear or None, limit)


# ------------------------------------------------------------------------------- comments

@tool("Add a comment", summary=one_line.comment_add, replay="drop")
def comment_add(ref: str, text: str) -> dict[str, Any]:
    """A comment on a place in the program, kept with this conf's declarations: by symbol it
    follows the symbol through a rebuild, by raw `SEG:OFF` it is `stale` once the build changes.
    One comment per place: a second at the same linear address, in any spelling, replaces the
    text and keeps the held row's `ref`. Nothing is written to the machine.

    Arguments: `ref`, a symbol or a `SEG:OFF` (read in the mode the machine is in); `text`, one
    printable line, no edge blanks, at most {COMMENT_BYTES_MAX} UTF-8 bytes. Needs the machine
    STOPPED. Refused `bad_argument` before anything is stored: an empty, blank or `#` ref, a pointer
    (`[g]+2`), `symbol+offset`, a `0x` number, a malformed `SEG:OFF`, an offset past its
    segment's limit, a bad text; `ambiguous_ref`, a name this table defines twice.

    Reply: `comment` (the row: `ref`, `by`, `created_at`, `origin`, `text`, `addr` once
    placed, `state`, `why`), `replaced_comments` (the rows replaced, whole), `declarations`
    (`persistent`, true: the store is a file, and `path`, that file), `note` (why the place is
    not `resolved`).
    A store that cannot be written is `host_failed` with `held_in_memory: true`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_add(live(), ref, text)


@tool("List the comments", summary=one_line.comment_list, read_only=True)
def comment_list() -> dict[str, Any]:
    """Every comment of this conf, in the order the store holds them, each placed now. Answers
    on a RUNNING guest too, typing nothing: then a protected-mode `SEG:OFF` is `unarmable` until
    a stop reads its selector's base.

    Reply: `comments`, each row with `ref`, `by`, `created_at`, `origin`, `text`, `addr`
    (the linear address, once placed), `state` (`resolved`, `unresolved` no such symbol now,
    `ambiguous`, `stale` a raw address not known to be this build's, `unarmable` its place cannot be
    worked out now), `why`, and `orphan` on a row from a store that kept no origin;
    `comments_total`, `truncated`, `declarations` (`persistent`, `path`); running, also
    `last_stop`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_list(live())


@tool("Delete a comment", summary=one_line.comment_delete, replay="drop")
def comment_delete(ref: str) -> dict[str, Any]:
    """Delete one comment: the one whose own `ref` this spells, else the one at the place it
    names. There is no delete-all. Needs the machine STOPPED. Refused `bad_argument` on a ref
    no comment could have (empty, a pointer, `+`, `0x`); `unknown_ref` when nothing matches,
    naming the refs held.

    Reply: `deleted` (the row), `declarations` (`persistent`, `path`), `note`. A store that
    cannot be written is `host_failed` with `held_in_memory: true`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_delete(live(), ref)


@tool("Save the comments to a file", summary=one_line.comment_save, replay="drop")
def comment_save(dest: str) -> dict[str, Any]:
    """Write every comment of this conf to `dest`, an absolute path, as a comment file (`# comments
    v1:` header, one sorted tab-separated row each; convention `<symbol file stem>.comments.tsv`
    beside the symbol file), whole or not at all. Answers on a running guest too.

    Refused `bad_argument`, the path left as it is: relative, a link, a directory or any
    other non-regular file, a missing directory, an existing file that is not a comment file,
    the declaration store's own file; two comments at one place, which a file names once (named,
    so one can be deleted). A file the host will not let it write is `host_failed`.

    Reply: `path` (the file written), `comments_total`, `dropped_comments` (each `ref` of the
    replaced file that the store does not hold), `dropped_total`, `truncated`, `note`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_save(live(), dest)


@tool("Load comments from a file", summary=one_line.comment_load, replay="drop")
def comment_load(path: str) -> dict[str, Any]:
    """Read a comment file (an absolute `path`) into this conf's comments, all or nothing: the
    file is parsed and every row placed first, and a row the format refuses or one address in
    two spellings refuses the whole file (`bad_argument`). Then the file wins: a place the store
    does not comment is added, one with another text replaced, one with the same text unchanged
    (a raw one taken into this session's build, ref and stamp kept); rows only the store holds stay.
    Two rows this stop places at one byte are both kept, and `note` names them; so is a raw row
    this stop's mode cannot place (past FFFF in real mode, the null selector in protected mode),
    kept `unarmable` and placed at a stop whose mode holds it. Needs the machine STOPPED.

    Reply: `path` (the file read), `parsed`, `added`, `replaced_comments` (the store's old rows,
    whole), `replaced_total`, `truncated`, `unchanged`, `comments_total`, `declarations`
    (`persistent`, `path`), `note`. A store that cannot be written is `host_failed` with
    `held_in_memory: true`.

    Reference: REFERENCE.md, Declarations.
    """
    return comments.comment_load(live(), path)


# ---------------------------------------------------------------------- the DOS machine

@tool("Map the machine", summary=one_line.machine_map, replay="drop")
def machine_map(sections: list[str] | None = None, dest: str = "") -> dict[str, Any]:
    """WHAT THE DOS MACHINE IS AT THIS STOP, one section per debugger listing, read live off the
    session's logfile: it needs the machine STOPPED and a session started with `logfile`, and
    costs a console round trip per listing.

    `sections` names the ones to read; left out, the DOS machine and the cpu: `mcbs`, `devs`,
    `kern`, `xms`, `ems`, `ems_pages`, `emu_mem`, `machine`, `cpu`, and in protected mode `gdt`
    and `ldt`. The rest are read only when named: `bios_mem`, `callbacks`, `vga`, `paging`.
    `dest` (absolute, not there yet) writes every section read WHOLE as JSON (`path`).

    Refused: an empty or unknown `sections`, or a `dest` already there (`bad_argument`, before
    anything is typed); no `logfile` (`no_channel`); a running guest (`not_stopped`); no prompt
    after a listing (`unexpected_answer`: `close` the session); a logfile that shrank
    (`session_broken`).

    Reply: `cpu_mode` (`real`, `protected`, `paged`; unavailable when the `CPU` listing is
    unreadable), then each section read: `mcbs` (`memory`, `mcb_seg`, `size_bytes`, `psp_seg`,
    `notes`, `filename`), `devs` (`header`, `attr`, `strat`, `intr`, `name`), `kern` (`seg`,
    `size_bytes`, `what`), `xms` (`handle`, `status`, `location`, `size_bytes`), `ems`
    (`handle`, `addr`, `size_bytes`, `name`), `ems_pages` (`handle`, `page`, `start`, `end`),
    `bios_mem` (`start`, `end`, `status`, `what`), `callbacks` (`number`, `desc`), `emu_mem`,
    `machine`, `cpu` (control registers, flags, `gdt`, `idt`, `tr`, `ldt`); `gdt`/`ldt`
    (`selector`, `base`, `limit`, `type`, `dpl`, `p`, `a`, `r`, `b`, `g`); `paging` (runs:
    `start`, `end`, `phy`, `flags`, `d`, `a`); `vga` (`mode`, `crtc`, `seq`, `gc`, `ac`, `dac`,
    `draw`). A section the debugger refused or printed nothing known for is ABSENT and
    `coverage_note` says why. `counts` (full lengths), `truncated` (a list cut at
    {LOG_LIMIT_MAX} rows), `sources`; `omitted` (sections this mode has that were not read) with
    `how`. Writes nothing to the guest.

    Reference: REFERENCE.md, Reading and writing.
    """
    chosen = narrowing.sections(sections, machine.SECTION_NAMES, machine.DEFAULT_SECTIONS)
    target = paths.fresh_dest("dest", dest) if dest else None
    session = live()
    ds.console_listening(session, "a listing")
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
def interrupt_vectors(number: int | None = None) -> dict[str, Any]:
    """WHICH HANDLER EVERY INTERRUPT VECTOR POINTS AT, AND WHAT HOLDS IT: the debugger's
    `INTVEC` table, each handler placed in the block of the MCB chain, the kernel's blocks or
    the BIOS's that holds it, and named by the loaded symbol table where that table reaches.
    `number`, an integer 0 to 255 (INT 0x21 is 33), narrows the reply to one vector; the whole
    table is read either way. Needs the machine STOPPED. In protected mode the table is the IDT,
    placed through the GDT or LDT and, with paging on, the page runs. The debugger writes
    `MCPIVT.TXT` into the emulator's working directory, which this reads and removes; with
    `logfile` it then reads the listings `machine_map` reads, a console round trip each.
    Without `logfile` no vector has a holder, nor in protected mode an `addr` or a `symbol`.

    Refused: `number` outside 0 to 255 (`bad_argument`, before anything is typed); a
    `MCPIVT.TXT` already there (`bad_argument`: somebody else's, left in place); a running
    guest (`not_stopped`); no table reported written, or a file that is not the whole table
    (`unexpected_answer`); and the listings' refusals, as `machine_map` gives them.

    Reply: `cpu_mode` (without `logfile`, as `status` reports it), `vectors` (each `number`,
    `seg_off` as the table holds it, `addr` the linear address before any paging, the row that
    holds the handler under its own section's name, `mcbs`, `kern` or `bios_mem`, first match in
    that order, absent when none does or it was not placed, and `symbol` as
    `symbols_find(linear=)` answers it, given only between the table's lowest and highest
    symbol), `counts` (`vectors`, `held`, `named`, over the whole table), `sources`,
    `coverage_note` (what could not be placed, and why). Before DOS has filled the table every
    vector is 0000:0000, as read.

    Reference: REFERENCE.md, Reading and writing.
    """
    session = live()
    ds.console_listening(session, "`INTVEC`")
    return st.reply(**machine.interrupt_vectors(session, number))


# ------------------------------------------------------------------------ the screen

@tool("Read the palette", summary=one_line.palette, replay="drop")
def palette(first: judges.NumberArg = 0, count: int = 0, scale: int = 0,
            dest: str = "") -> dict[str, Any]:
    """THE 256 COLOURS OF THE VGA'S DAC AS THEY ARE AT THIS STOP, read off the debugger's
    `VGA DAC` and `VGA DACPAL` listings in the session's logfile, with their swatch attached:
    it needs the machine STOPPED and a session started with `logfile`, and costs a console
    round trip per listing and one more for `VGA DACPAL`'s pager.

    The DAC holds entries 0 to 255 and nothing past them: an entry past 255 does not exist.
    `first` (0 to 255; an integer or a `0x` hex string) and `count` (1 to
    256, 0 for every entry from `first`) choose the entries returned, `first + count` at most
    256. The swatch is one square per entry, sixteen a row, an indexed PNG whose every pixel is
    the entry's index into the DAC. {PICTURE}. {PICTURE_ARGS}.

    Reply: `entries` (256), `first`, `count` (how many came back), `colors` (`#rrggbb`, each
    six-bit component widened as the emulator renders it, its two top bits repeated below),
    `rgb` (each entry as `VGA DACPAL` printed it, three six-bit components in hex), `bits` (6),
    `pel_mask` as `VGA DAC` printed it, and `image`.

    Refused: an entry the DAC does not have (`first` 256 or more, `first + count` past 256), a
    `scale` out of range or a relative `dest` (`bad_argument`, before anything is typed); a
    `dest` already there or with no directory (`bad_argument`); no `logfile` (`no_channel`); a
    running guest (`not_stopped`); a DAC not in its six-bit mode, or a listing in a shape this
    was not written against (`unexpected_answer`); a picture the disk could not take whole
    (`host_failed`, leaving no file).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**vgadac.palette(session, checks.number("first", first), count, scale,
                                     paths.absolute("dest", dest) if dest else None,
                                     STATE.session_scratch()))


@tool("Read the screen", summary=one_line.screen_view, replay="drop")
def screen_view(crop: list[int] | None = None, scale: int = 0,
                dest: str = "", attach: bool = True) -> dict[str, Any]:
    """WHAT THE SCREEN SHOWS AT THIS STOP, read from video memory where the VGA listings say it
    lies: needs the machine STOPPED and a session started with `logfile`. A text mode comes back
    as text; the chained 256-colour mode (13h's) as the picture: an indexed PNG of
    the indices the guest wrote, the PLTE the DAC. {PICTURE}.
    {PICTURE_ARGS}; {PICTURE_ATTACH}; a text mode takes none of these. `crop`
    `[x, y, width, height]`,
    in characters or pixels. Protected mode reads through a covering GDT or LDT segment.

    Reply: `vga_mode` (`VGA MODE`'s word), `kind` (`text` or `pixel`), `width` and `height` (in
    characters or pixels), `crop` (the rectangle read), `display_start` (as `VGA MODE` printed
    it); in text, `text` (one string a row of the crop, as code page 437 draws it, trailing
    spaces dropped) and `cursor` (`[column, row]` in the crop, unavailable when hidden or
    outside it); in 256 colours, `image`.

    Refused: a relative `dest`, a `scale` out of range or a misshapen `crop` (`bad_argument`,
    before anything is typed); `dest`, `scale` or `attach` in a text mode, a `crop` off the
    screen, a `dest` already there or with no directory, or a dump file left in the emulator's
    working directory (`bad_argument`); any other mode, planar, linear-frame-buffer or none set,
    naming it and `capture_frame`; a layout this does not decode (split, panning, a row wider
    than the screen), a screen past its window, or one no segment or page reaches as itself; no
    `logfile` (each `no_channel`); a running guest (`not_stopped`); a DAC not six-bit, or a
    listing in another shape (`unexpected_answer`); a picture the disk could not take whole
    (`host_failed`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**screen.screen_view(session, crop, scale,
                                         paths.absolute("dest", dest) if dest else None,
                                         STATE.session_scratch(), attach))


@tool("Signature of the screen", summary=one_line.screen_signature, read_only=True,
      replay=("signature",))
def screen_signature(crop: list[int] | None = None) -> dict[str, Any]:
    """One hex string for what is on screen, or on `crop` of it, so "is it the same screen" is
    answered by comparing two strings and no picture crosses the conversation. It is the
    `scry-sig/1` signature a series row carries over the same crop: in a text mode each cell is
    its code page 437 byte and the colours its attribute resolves to through the Attribute
    Controller and the DAC; in 256 colours each pixel is its DAC colour. So a palette change is
    a new signature, and the cursor is not part of it. `crop` `[x, y, width, height]`, in
    characters or pixels. It reads what `screen_view` reads, in the same modes; needs the
    machine STOPPED and a session started with `logfile`.

    Reply: `signature` (16 hex characters), `kind` (`text` or `pixel`), `width` and `height`
    (the screen's), `crop` (the rectangle hashed), `vga_mode`.

    Refused as `screen_view` is, `dest` and `scale` aside: a `crop` off the screen
    (`bad_argument`); another mode, naming it and `capture_frame`, or a screen it cannot place
    (`no_channel`); no `logfile` (`no_channel`); a running guest (`not_stopped`); a DAC not in
    its six-bit mode or a listing in another shape (`unexpected_answer`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**screen.screen_signature(session, crop))


# ------------------------------------------------------------------- the screen maps

def _map_read(session: ds.Session) -> screen_map.Read:
    """The one screen read a map is matched against, `screen_signature`'s."""
    return lambda: screen.grid(session)[0]


@tool("Load a screen map", summary=one_line.map_load)
def map_load(path: str) -> dict[str, Any]:
    """{MAP_LOAD}.

    Reference: REFERENCE.md, Screen maps.
    """
    return st.reply(**STATE.maps.load(path))


@tool("Map the screen in front of you", summary=one_line.map_add)
def map_add(screen: str, match: list[list[int]],
            controls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Map the screen the machine shows NOW as `screen` in the SESSION layer: one read signs each
    `match` crop (`[x, y, width, height]`, 1..16, regions that stay still on that screen, never
    a cursor or a moving sprite), and `controls` (`[{"name", "rect"}]`, a `rect` shaped as a
    crop) name its controls, all in the screen's own units (cells in a text mode, pixels in 256
    colours, as `screen_view` counts). A screen of the same name in the file is shadowed
    (`shadows_file`). Needs the machine STOPPED and a session started with `logfile`; a `start`
    empties the session layer.

    Reply: `screen`, `kind`, `size`, `match` (each crop with its `signature`), `controls`,
    `replaced`, `shadows_file`. Refused: a misshapen name, crop or control, a rectangle off the
    screen (`bad_argument`); the modes `screen_view` refuses.

    Reference: REFERENCE.md, Screen maps.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**STATE.maps.add(screen, match, controls, _map_read(session)))


@tool("Which mapped screen is this", summary=one_line.map_find, read_only=True,
      replay=("matched", "screen"))
def map_find() -> dict[str, Any]:
    """WHICH MAPPED SCREEN the machine shows, from ONE screen read and no picture: the session
    layer first, then the file's; a screen matches when its kind and size are the screen's and
    every region's signature is. Needs the machine STOPPED and a session with `logfile`.

    Reply: `matched`; matched, `screen`, `layer` (`session` or `file`), `kind`, `size`,
    `controls` (each `name`, `rect`, `centre`), and `send_mouse(target=)` then acts on them; not
    matched, `kind`, `size`, `screens_mapped`, `screens_tried` (of that kind and size). Refused:
    no screen mapped (`needs_call`); the modes `screen_view` refuses.

    Reference: REFERENCE.md, Screen maps.
    """
    session = live()
    ds.console_listening(session, "a listing")
    # The stop the read is of, or None when that stop's own record could not be made (a cut
    # pane): a previous stop's number would date the identification wrong.
    current = STATE.as_of_current(session)
    return st.reply(**STATE.maps.find(_map_read(session),
                                      None if current is None else current["stop_seq"]))


@tool("Save the screen map", summary=one_line.map_save, replay="drop")
def map_save(path: str, overwrite: bool = False) -> dict[str, Any]:
    """{MAP_SAVE}.

    Reference: REFERENCE.md, Screen maps.
    """
    return st.reply(**STATE.maps.save(path, overwrite))


@tool("Capture a series of frames", summary=one_line.series_capture, replay="drop")
def series_capture(frames: list[int] | None = None, first: int | None = None,
                   last: int | None = None, step: int = 1, crop: list[int] | None = None,
                   dest: str = "", capture_path: str = "") -> dict[str, Any]:
    """FRAMES OUT OF THE SESSION'S VIDEO CAPTURE, as PNGs and one manifest: the series
    `series_diff`, `region_track` and `golden_check` read, with no picture in the reply. Needs
    `ffmpeg` (named when missing) and a session started with `capture_video`.

    The frames are the AVI's own, numbered from 0, NOT emulated frames: `frames` (a list,
    ascending) or `first`, `last` and `step`, at most {SERIES_MAX}. `capture_path`: an absolute
    path of a capture, default the largest. `crop` `[x, y, width, height]` in the capture's pixels,
    default the whole frame. `dest`: a new absolute directory, kept after `close`; else one in
    the session's scratch, gone at `close` (`kept_after_close` says which). A `%` in `dest` is
    refused (ffmpeg would read it as a template).

    Reply: `manifest` (its path), `count`, `first`, `last`, `distinct` (signatures over the
    crop), `frames_asked`, `kept_after_close`, `frame_source` (`avi`), `capture_path`, `crop`.
    It answers on a running guest too: it reads the file. Refused: a frame past the capture's
    end, a crop off its frames, a `dest` already there (`bad_argument`); a session with no
    `captures_dir` or no `capture_video` (`no_channel`), or no capture written yet
    (`unexpected_answer`); no `ffmpeg`, or ffmpeg failing (`host_failed`).

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    return st.reply(**media.series_capture(session, STATE.session_scratch(), frames, first,
                                           last, step, crop, dest, capture_path))


# THE MEDIA FILE TOOLS are scry-core's, body and description, each registered through this
# server's own `tool`, its bare fields made a reply (`status` and `session`) as this server's own
# bodies make theirs; bound here by name so a step and a direct call find them as they find
# every other tool.
_MEDIA = media_tools.register(tool, media.MEDIA_TOOLS, lambda body: st.reply(**body))
image_diff = _MEDIA["image_diff"]
series_diff = _MEDIA["series_diff"]
region_track = _MEDIA["region_track"]
golden_check = _MEDIA["golden_check"]


# --------------------------------------------------- declarations: breakpoints, watches

@tool("Declare a breakpoint", summary=one_line.breakpoint_at)
def breakpoint_at(ref: str, by: str = "auto") -> dict[str, Any]:
    """Declare a code breakpoint at a SYMBOL or a `SEG:OFF`, and arm it if it can be.

    The declaration is STORED on disk keyed by the conf, stamped with this session as its
    `origin`, so it survives a rebuild: on every `symbols_load` a symbol re-resolves and
    re-arms, while a raw `SEG:OFF` re-arms per BUILD, whoever declared it: at `start` when it
    was declared before any map was loaded, after a `symbols_load` of the same map when it was
    declared over that map, and `stale` over another build (declaring it again adopts it). A
    symbol absent from THIS
    build is stored `unresolved`, not refused (it may be inlined this time). A name matching
    several symbols is refused, nothing stored; so is an address another declaration of
    this store already holds, naming that ref (one breakpoint row is one declaration:
    clear that ref or use it). `by` is `auto` (symbol or address by shape)
    unless you must force `symbol` or `address`. Arming needs the machine stopped and the
    debugger to take the `BP`; the entry is read back from its list.

    Reply: `ref` (the string that clears it), `by`, `stored`, `already_stored` (a no-op
    re-declaration, adopted by this session), `armed`, `entry` (the debugger's row, e.g.
    `BP 00AF:0017A6EC`), `state` (`armed`, `unresolved`, `unarmable`, `pending` when the
    guest is running: stored now, armed at the next stop and said so in `applied_on_stop`
    with `why`), `marked` and `note` when the symbol carries the linker's mark (a fact, not a
    refusal: whether such an address fires is an open question).
    """
    return arming.breakpoint_at(live(), ref, by)


@tool("List the breakpoint declarations", summary=one_line.breakpoint_list, read_only=True)
def breakpoint_list() -> dict[str, Any]:
    """Every breakpoint DECLARATION with its state, cross-referenced with the debugger's
    own list. Answers on a RUNNING guest too: then the debugger cannot be asked, so the
    states are those of the last stop's survey, `debugger_read` is false and `last_stop` dates
    the answer by that stop (`stop_seq`, `pc`, `attribution`, `since_s`, `wall_at`); with no
    stop yet, `last_stop` is unavailable and a symbol's state is `unarmable`. Stopped: read
    live, `debugger_read` true.

    Reply: `breakpoints`, each with `ref` (the string that clears it), `by`, `created_at`,
    `origin` (the session that declared or last adopted it), `entry`, `state` -- `armed` (its
    entry is in the debugger's list), `unresolved` (no such symbol in this build), `gone`
    (armable but no longer in the list), `unarmable` (machine running or no symbols loaded),
    `ambiguous` (a name this build defines more than once: nothing is armed for it), `pending`
    (declared while the guest ran, applied at the next stop), `stale` (a raw address declared
    over another build: kept, never re-armed here; declare it again to adopt it), `orphan` (from
    a store that kept no origin, where it would otherwise say `gone`; every such row also
    carries `orphan: true` whatever its state: nobody's, clear it by its `ref` or declare it
    again) -- plus `marked` for symbols; and `foreign`, entries the debugger holds that this
    store never declared (a `run_to` whose cleanup could not be confirmed leaves one), listed
    and never deleted. `breakpoint_clear` is this family's broom and never touches a watch;
    `watch_clear` is the other, and the two together empty the store.
    """
    return arming.breakpoint_list(live())


@tool("Clear breakpoint declarations", summary=one_line.breakpoint_clear)
def breakpoint_clear(ref: str = "", all: bool = False) -> dict[str, Any]:
    """Clear breakpoint declarations: all of them with `all=True`, or the one named by the
    exact `ref` its declaring reply carried (a symbol, a `SEG:OFF`, or a `BPINT NN` /
    `BPINT NN AH=NN` row). Removes from the debugger ONLY what this store armed, and only
    while the machine is stopped; the declarations themselves are dropped either way. A
    `foreign` entry is never deleted, only reported as left.

    Reply: `declarations_cleared`, `disarmed` (the debugger rows removed), `pending_disarm`
    (rows queued for removal at the next stop because the guest is running: the
    declarations are gone now, the rows go then), `note`. A `ref` that matches no
    breakpoint declaration is INVALID, naming the refs the store holds; `all=True` on an empty
    store is `ok` with 0; neither `ref` nor `all`, or both, is `bad_argument`.
    """
    checks.clear_scope(ref, all)                  # here too: no path reaches the body unjudged
    return arming.breakpoint_clear(live(), None if all else ref)


@tool("Declare a watch", summary=one_line.watch_add)
def watch_add(ref: str, mode: str, length: int = 0, fmt: str = "auto",
              by: str = "auto") -> dict[str, Any]:
    """Declare a WATCH by symbol, by `SEG:OFF`, or at a place reached THROUGH a pointer, read as
    `fmt` (little-endian), in one of two modes. The declaration persists like a breakpoint's and
    re-resolves on `symbols_load`.

    Arguments:
    - `mode`: `show` (read at each stop: nothing is armed, the value rides in `watches`)
      or `change` (a trap is armed and the machine stops when the bytes change; trusted in REAL
      mode, while under a DJGPP program's paging the reply says its firing is not to be trusted).
    - `ref`: a symbol, a `SEG:OFF`, or `[base]`, `[base]+0x28`, `[base]-0x4`, `base->field`, with
      `base` a symbol or address holding a POINTER (read at its type's width, else four bytes in
      protected mode and two in real), re-resolved at every stop.
    - `fmt`: the value grammar: a scalar (`u8` .. `f64`), an array (`u16[8]`), a string
      (`char[16]`) or a struct (`{x:i16,y:i16}`). With no `fmt` a typed symbol reads as its type,
      else the widest unsigned scalar `length` divides.
    - `length`: TOTAL bytes, a whole number of `fmt` values; a sized format needs none. A show
      watch is at most {READ_MAX} bytes.
    - `by`: `auto` (by shape) unless you must force `symbol`, `address` or `pointer`.

    Refused: one address as both show and change; a length over the ceiling; a pointer base the
    table lacks (most likely a stack local).  Reply: `ref` (the string `watch_clear` takes),
    `by`, `mode`, `stored`, `already_stored`, `state` (`evaluated` for a placed show watch,
    `unresolved`, `unarmable`, `null_pointer`; a change watch adds `armed`, or `pending` while
    the guest runs, armed at the next stop and said in `applied_on_stop`), `pointer` through a
    pointer (`at`, `length`, `value`, `offset`, `field`), and `entry`/`command` for a change
    watch.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.watch_add(live(), ref, mode, length, fmt, by)


@tool("List the watch declarations", summary=one_line.watch_list, read_only=True)
def watch_list() -> dict[str, Any]:
    """Every watch DECLARATION and its state, on a stopped OR a running guest (running:
    states as of the last stop's survey, `debugger_read` false, `last_stop` dating the answer;
    see `breakpoint_list`). Reply: `watches`, each with `ref`, `by`,
    `created_at`, `origin` (the session that declared or last adopted it), `mode`,
    `length`, `fmt`, `state` (a show watch: `evaluated`/`unresolved`/`ambiguous`/
    `unarmable`, it arms nothing but IS EVALUATED at every stop; a change watch additionally
    `armed` or `gone`; either `orphan` when it comes from a store that kept no origin: it is
    nobody's, clear it by its `ref` or declare it again to adopt it), and `foreign`, memory
    breakpoints the debugger holds that this store never declared. No watch is re-armed
    across sessions, so none is ever `stale`; the origin says whose it is. `watch_clear` is
    this family's broom; `breakpoint_clear` never touches a watch, and the two together
    empty the store.
    """
    return arming.watch_list(live())


@tool("Clear watch declarations", summary=one_line.watch_clear)
def watch_clear(ref: str = "", all: bool = False) -> dict[str, Any]:
    """Clear watch declarations: all with `all=True`, or the one named by the exact `ref`
    its `watch_add` reply carried. Disarms from the debugger only the change-watches this
    store armed (show watches armed nothing), and only while the machine is stopped;
    declarations are dropped either way. A foreign memory breakpoint is never deleted, only
    reported as left.

    Reply: `declarations_cleared`, `disarmed`, `pending_disarm` (rows queued for removal
    at the next stop because the guest is running), `note`. A `ref` that matches no watch
    declaration is INVALID, naming the refs the store holds; `all=True` on an empty store is
    `ok` with 0; neither `ref` nor `all`, or both, is `bad_argument`.
    """
    checks.clear_scope(ref, all)
    return arming.watch_clear(live(), None if all else ref)


# ------------------------------------------------------------ input to a running guest

@tool("Send keystrokes", summary=one_line.send_keys, on_cancel="none")
def send_keys(keys: list[str], modifiers: list[str] | None = None,
              expect: str = "", seconds: float | None = None,
              ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Send KEYSTROKES into the RUNNING guest, inside the machine, and, with `expect`, PROVE
    the program took them. The wait for the reaction reports its progress.

    Arguments: `keys`, key names (`a`, `1`, `enter`, `esc`, `space`, `up`, `f1`..`f12`,
    punctuation names), at most {KEYS_MAX} per call; `modifiers` (`shift`, `ctrl`, `alt`), held
    across them; `expect`, a regex over the guest's E9 log that only the program's REACTION
    writes, waited for up to `seconds` (default {EFFECT_WAIT_S}).

    Refused before anything is sent: an unknown key or modifier name; `seconds` without
    `expect`; a machine stopped at the debugger (the keys would land at the next resume); a
    guest whose log shows no stub announce, or an older stub (`no_channel`, naming the conf
    line); with no `logfile` there is no announce to read and the keys go out.

    Reply: `route: "guest"`, `posted`, `bytes`, `ticks`, and `verify`: `verdict` `TARGET`
    with `seen`, `line`, `waited_s`, `seen_before_waiting`, `lines_before`, `lines_total`, or
    `TIMEOUT` (a miss, the program did not react) with `arrived_during` and a `note`; or
    `checked: false` with no `expect`. A stop that lands DURING the wait is INVALID
    (`wait_stopped`) with `last_stop`. Timing is "now": for a precise guest instant, `run_to`
    it, send, then `resume`.

    Reference: REFERENCE.md, Input and the screen.
    """
    return inputs.send_keys(live(), keys, modifiers, expect or None, seconds, bridge(ctx))


@tool("Send mouse input", summary=one_line.send_mouse, on_cancel="none")
def send_mouse(x: int | None = None, y: int | None = None, button: str = "",
               action: str = "click", units: str = "screen", expect: str = "",
               seconds: float | None = None, target: str = "",
               ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Move the guest's MOUSE POINTER and press its buttons, inside the machine, and read the
    pointer back. With `expect`, PROVE the program reacted, as `send_keys` does.

    `x`, `y`: where the pointer goes, both or neither, in `units`: `screen` (default), the
    screen's own units as `screen_view` counts them (character cells in a text mode, pixels in
    a graphics one; the standard BIOS modes), or `mouse`, the DOS driver's own coordinates (for
    a VESA or custom mode). `target`: instead of `x`, `y`, a control of the screen the latest
    `map_find` matched, its centre in `screen` units. `button`: `left`, `right` or `middle`;
    `action`: `click` (default), `double` (two clicks a tick apart), `down` or `up` (a drag is
    `down`, a move, `up`). A move and a button in one call: the move goes first.

    Refused before anything is sent: no move and no button, half a move, a negative or
    non-integer coordinate, a place off the screen or outside the driver's range, `screen`
    units in a mode this server does not map, an unknown button, action or units, a session
    with no `logfile` (the read-back goes through it), a stopped machine, no stub. A `target`
    beside `x`, `y` or `units="mouse"` (`bad_argument`); no `map_find` match since the start,
    or a guest no longer showing that screen's kind and size (`needs_call`); a control that
    screen lacks (`unknown_ref`).

    Reply: `route: "guest"`, `pointer` read back after the call (`screen` with `x`, `y`,
    `width`, `height`, or unavailable in an unmapped mode; `mouse` with the driver's `x`, `y`,
    `max_x`, `max_y`; `buttons` held; `bios_mode`), `arrived` (the read-back is where it was
    asked; when it is not, `asked` says where in the driver's coordinates: a text mode snaps to
    its cell, a program's own range clamps), the arguments, `verify` as `send_keys`'; with a
    `target`, `target`, `screen` and `identified_at_stop`, the stop that `map_find` read. A
    read-back that fails after the commands went in is INVALID with `delivered: true`, so
    nothing is sent twice.

    Reference: REFERENCE.md, Input and the screen.
    """
    if not target:
        moved = inputs.send_mouse(live(), x, y, button or None, action, units, expect or None,
                                  seconds, bridge(ctx))
    else:
        inputs.check_mouse(x, y, button or None, action, units, expect or None, seconds, target)
        aimed = STATE.maps.target(target)
        moved = inputs.send_mouse_at(live(), aimed, button or None, action, expect or None,
                                     seconds, bridge(ctx))
    # Read off the state, not `live()`: a session that died after the move went in must not
    # cost the caller the reply that says it was delivered.
    dpresence.of(STATE.session).pointer_moved()
    return moved


# ----------------------------------------------------------------------- the captures

@tool("List this session's captures", summary=one_line.captures, read_only=True)
def captures() -> dict[str, Any]:
    """The video captures this session recorded, with what is in them.

    Needs `start(capture_video=True, program=..., captures_dir=...)`. Reply: `captures`, a
    list of `path`, `bytes`, `avi_frames`, `complete` (the recording was finalised; `false` is
    information, not damage: a frame extracts from an unindexed capture fine), largest last.
    Two files is the normal case: the recording restarts when the guest changes video mode.
    An empty list on a conf whose autoexec exits before `program` runs is explained in the
    reply. Works on a running guest.
    """
    return caps.captures(live())


@tool("Extract a frame to a file", summary=one_line.capture_frame, replay="drop")
def capture_frame(frame: int, dest: str, capture_path: str = "") -> dict[str, Any]:
    """ONE still image out of a capture, frame `frame`, written to `dest` as PNG whatever
    the name says; `capture_path` defaults to the largest capture; both are absolute paths. Needs
    `ffmpeg` (named when missing) and a session started with `capture_video`. Reply: `path`,
    `bytes`, `sha256`, `capture_path` (the capture read), `frame`. A `%` anywhere in `dest` is
    refused (ffmpeg would read the path as a template), and so is a `dest` already there: it is
    never deleted or overwritten; a frame past the end is refused rather than a frameless file
    handed back.
    """
    session = live()
    return caps.capture_frame(session, frame, paths.absolute("dest", dest),
                              paths.input_file("capture_path", capture_path, "capture")
                              if capture_path else None)


# ---------------------------------------------------------------------- the sequence

def _step_ops() -> dict[str, Callable[..., dict[str, Any]]]:
    """Op name -> the wrapped tool it dispatches to: every tool the MCP layer serves but
    `checks.NOT_STEPS`, read off the registry at call time, so a step is a tool by construction and
    a new tool is a step without a second list to forget."""
    # The module's own binding first, so a step dispatches to whatever this module calls the tool
    # now; the registration's function for a tool registered elsewhere.
    here = globals()
    return {t.name: here.get(t.name, t.fn) for t in strict.registered(mcp)
            if t.name not in checks.NOT_STEPS}


checks.take_step_ops(_step_ops)


@tool("Export the session as a replay", summary=recording.export_summary)
def perform_export(path: str, overwrite: bool = False) -> dict[str, Any]:
    """{EXPORTS}

    Kept: what moved the machine, as steps, and the reads that are checks (`read_memory`,
    `registers`, `screen_signature`, `golden_check`), each holding to what its reply said
    (`recorded`). Dropped, each named with why: a refused call, any other read, a call that
    changes nothing in the emulated machine. Cut, named: the first call no replay can place (a
    release, a `stop` or `screen_wait` that ran the guest and came back stopped, or a wall-clock
    bound that ended a run, whose run ends where no replay reaches; no reply; a refusal after the
    guest moved; a guest found elsewhere than the call before left it; a step that wrote a file
    the session named; past {RECORD_MAX} calls kept).

    {EXPORT_REPLY}

    Reference: REFERENCE.md, From an investigation to a bench.
    """
    return st.reply(**recording.export(RECORDER, path, overwrite))


@tool("Run a sequence of steps", summary=one_line.perform, on_cancel="stop")
def perform(steps: list[dict[str, Any]], settle_seconds: float = 30.0, summaries: bool = False,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run a LIST of the server's own operations in order on the open session, in ONE round
    trip, stopping at the first failure with the whole account.

    Arguments: `steps`, each `{"op": <tool name>, ...its arguments}`; every tool but
    `build_check`, `start`, `close`, `perform`, `drive` and `perform_export` is a step, `debug`
    included. A `resume` (or a `step` that comes back running) ends the console-driven part:
    after it the steps `answers_while_running` lists run at once (a `stop` ends the run), and
    before any other the sequence WAITS up to `settle_seconds` for the machine to stop (0 never
    waits). A `send_keys`/`send_mouse` step whose own `expect` misses ends the list, `verdict`
    `TIMEOUT`. `summaries=True`, an argument of the call and never of a step, keeps a long list
    readable: each step but the last that ran becomes a compact row; `ran` shows the first
    {ROWS_SHOWN}, `ran_path` and `replies_path` hold all, and `stops` counts the stops.

    A step's `recorded`, `{field: value}`, is what its reply must hold (a replay,
    `perform_export`): else INVALID `diverged` there, with `field`, `recorded` and `got`; `held`
    counts the steps that held.

    Refused before the first step runs: the WHOLE list is checked (ops, argument names and
    VALUES, through each tool's own checks), and the reply is INVALID with `errors` listing EVERY
    refused step (`step`, `op`, `code`, `message`), nothing run. What only its step can judge (a
    symbol against the table loaded by then, a file an earlier step writes, the machine's mode)
    refuses at that step.

    Reply: `ran` (each step's `op` and full `reply`), `steps_completed`, `held`; a step's refusal is
    INVALID (`step_failed`) with `failed_at` and `failed`; once it waited, `verdict`: `TARGET`
    (a list ending running adds `stopped`, the stop it was heading for) or `TIMEOUT` (the steps
    after the wait unsent, a `note`); with no wait, `not_stopped` before a console step, or
    `still_running`; a gone emulator is `session_broken`. `start(plan=...)` runs one too.

    Reference: REFERENCE.md, Sequences in one call.
    """
    return sequence.run_steps(live(), steps, settle_seconds, _step_ops(), bridge(ctx), summaries,
                              prechecked=True)


@tool("Drive an input and verify it", summary=one_line.drive, on_cancel="none")
def drive(act: list[dict[str, Any]], expect: str = "",
          seconds: float | None = None, pattern: str = ".", limit: int = 40,
          settle_seconds: float = 30.0, summaries: bool = False,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """LOOK, ACT, VERIFY in one call: the way a browser is driven, for a DOS program. The
    waits inside (for a stop between steps, for `expect`) report their progress.

    The E9 log is MARKED first; `act` (a list of steps in `perform`'s vocabulary, typically
    `send_keys`/`send_mouse` each with its own `expect`) runs with `perform`'s rules; with
    `expect` (a regex; empty for none) the call then waits up to `seconds` (default
    {EXPECT_WAIT_S}, at most {WAIT_MAX_S}) for a NEW matching line from that mark, the act's
    overall effect; and `looked.guest` is what the guest wrote since the mark, filtered by
    `pattern` (a regex) and cut to the LAST `limit` (1..{LOG_LIMIT_MAX}, default 40): `pattern`
    only filters what is SHOWN and proves nothing, so it is never the `expect`. An act that
    ended stopped at the debugger has the log read once, not waited on: a stopped guest cannot
    write. `settle_seconds` and `summaries` are `perform`'s. `seconds` with no `expect` is
    refused. Needs a session with `logfile`.

    Reply: `act` (`ran`, `steps_completed`, `failed_at`, `failed` when a step did, `perform`'s
    tail), `verify` (`checked`; `verdict` `TARGET` with `seen`, `line`, `seen_before_waiting`,
    `lines_before`, `waited_s`, `lines_total`, or `TIMEOUT`, the expectation not met, with
    `arrived_during` and a `note`; `checked: false` with `why` when no `expect` was given;
    `available: false` when `act.verdict` is `TIMEOUT`), and `looked.guest` (`lines_written`,
    `lines_total`, `truncated`, `lines`, `since_mark`, `pattern`). INVALID with the same `act`,
    `verify` and `looked` when a step failed (`step_failed`), when the act itself was refused or
    its emulator went (its own code: `not_stopped`, `session_broken`, `diverged`...), when a
    stopped machine lacks the line (`wait_stopped`), or when the verify itself refused (its
    `code`). No screen in the look: a still is `capture_frame`.

    `checked` is whether a check ran at all, `seen` whether the line arrived; neither is
    `verified`, which everywhere else means a readback equal to what was sent.
    """
    return sequence.drive(live(), _step_ops(), act, expect or None, seconds, pattern, limit,
                          settle_seconds, bridge(ctx), summaries)


strict.strict_arguments(mcp)


#: The signals that end a server whose client went away abruptly (a SIGTERM, the SIGHUP of a
#: terminal that closed, a Ctrl-C). Their default action would end the server with its `finally`
#: unrun, and DOSBox-X, in a process session of its own, would outlive it.
EXIT_SIGNALS: tuple[signal.Signals, ...] = tuple(
    getattr(signal, name) for name in ("SIGTERM", "SIGHUP", "SIGINT") if hasattr(signal, name))
#: How long a signalled end waits for a tool to let go of the machine before it closes the
#: emulator without it: the process is going either way, and the emulator must not outlive it.
LOCK_WAIT_S = 10.0
#: How the signalled end leaves once the session and the scratch are gone: at once, because the
#: transport's reader thread is still blocked on a stdin nobody closed, and the interpreter would
#: wait for it for ever.
_leave = os._exit


def _exit_on(signum: int, _frame: object) -> None:
    """A signal from `EXIT_SIGNALS`: the end runs on a thread of its own, never as an exception
    in whatever frame the event loop was in (a task group would wrap it, and the end would be
    missed), and the signals after it are ignored, so a second one cannot cut it short."""
    for sig in EXIT_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)
    threading.Thread(target=_end_signalled, args=(128 + signum,), name="signalled-end",
                     daemon=True).start()


def _end_signalled(code: int) -> None:
    """The session closed (under the lock, or past `LOCK_WAIT_S` without it), the process's
    scratch removed as the normal exit's `atexit` would, and the process left, whatever failed
    on the way."""
    try:
        took = LOCK.acquire(timeout=LOCK_WAIT_S)
        try:
            _close_held_session()
        except Exception as e:  # noqa: BLE001 -- said, then the end goes on: it must leave
            print(f"dosbox-x server: the session could not be closed on the way out ({e!r})",
                  file=sys.stderr, flush=True)
        finally:
            if took:
                LOCK.release()
        st.remove_scratch()
    finally:
        _leave(code)


def _close_held_session() -> None:
    """The emulator this server holds, ended: the published session, and one `start` is still
    waiting for (an end by signal that could not take the lock reaches it)."""
    for held in (STATE.session, STATE.starting):
        if held is not None:
            held.close()
    STATE.session = STATE.starting = None


def main() -> None:
    process_name.set_title(ds.PROCESS_NAME)
    for sig in EXIT_SIGNALS:
        signal.signal(sig, _exit_on)
    try:
        mcp.run()
    finally:
        # UNDER THE LOCK, because a worker thread may still be inside a tool holding
        # the terminal this is about to close.
        with LOCK:
            _close_held_session()


if __name__ == "__main__":
    main()
