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
  directory, a watched session with no placement helper, a session with no bound or
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
    log_marks,
    media_tools,
    methods,
    narrowing,
    process_name,
    recording,
    reference,
    reply_schema,  # noqa: E402
    )
from scry_core import placement as window  # noqa: E402
from scry_core import presence as scry_presence  # noqa: E402
from scry_core import sequence_account as account  # noqa: E402
from scry_core import steps as core_steps  # noqa: E402
from scry_core import strict_arguments as strict  # noqa: E402
from scry_core import vocabulary as vocab
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
import dosbox_declarations as dec  # noqa: E402
import dosbox_dump as dumping  # noqa: E402
import dosbox_find as finder  # noqa: E402
import dosbox_folds as folds  # noqa: E402
import dosbox_inputs as inputs  # noqa: E402
import dosbox_launch as dlaunch  # noqa: E402
import dosbox_lifecycle as lifecycle  # noqa: E402
import dosbox_log_reader as log_reader  # noqa: E402
import dosbox_logs as dlogs  # noqa: E402
import dosbox_machine as machine  # noqa: E402
import dosbox_media as media  # noqa: E402
import dosbox_paths as paths  # noqa: E402
import dosbox_placement as placement  # noqa: E402
import dosbox_presence as dpresence  # noqa: E402
import dosbox_process as dprocess
import dosbox_replies  # noqa: E402
import dosbox_retrace as retrace  # noqa: E402
import dosbox_running as running  # noqa: E402
import dosbox_screen as screen  # noqa: E402
import dosbox_sequence as sequence  # noqa: E402
import dosbox_session as ds  # noqa: E402
import dosbox_state as st  # noqa: E402
import dosbox_summaries as one_line  # noqa: E402
import dosbox_trace as tracing  # noqa: E402
import dosbox_vga as vga  # noqa: E402
from dosbox_mcp import LOCK, RECORDER, ROSTER, registered_tools, tool  # noqa: E402
from dosbox_mcp import mcp as mcp  # noqa: E402  (the probe and the clients read `server.mcp`)
from dosbox_running import live  # noqa: E402
from dosbox_state import STATE  # noqa: E402

# ------------------------------------------------------------------- session: the build

@tool("Check the build", summary=one_line.build_check, read_only=True)
def build_check(binary: str = "") -> dict[str, Any]:
    """Whether a DOSBox-X binary resolves and carries the debugger. Run before `start`; it
    refuses while a session is live. `binary`: omitted, `DOSBOX_X_BINARY`, else the PATH's
    `dosbox-x`; a named build that fails is refused.

    Reply: `binary`, `binary_origin`, `version`, `debugger`, `heavy_debug` (`trace` needs it).
    """
    if binary:          # the shape first, as every path's, whatever the session is
        paths.absolute("binary", binary)
    dprocess.refuse_without_a_terminal()
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
            # LAUNCHED BEHIND, as a session is, and BOUNDED: this build does not refuse an
            # option it does not know, it starts, so a probe that opened a window would
            # otherwise take the front, and only the bound would end it.
            env=dlaunch.launch_environment(True), timeout=20)
    except subprocess.TimeoutExpired:
        raise ds.Invalid("host_failed",
            f"`{resolved.path} -helpdebug` did not return in 20 s: a build that does not "
            f"know the option hangs on it rather than failing, and a slow or wedged start "
            f"looks the same") from None
    except OSError as e:
        raise ds.Invalid("host_failed",
            f"`{resolved.path} -helpdebug` could not be run: {e}") from None
    text = got.stdout + got.stderr
    has_debugger = "-break-start" in text
    if not has_debugger:
        raise ds.Invalid("host_failed",
            f"`{resolved.path} -helpdebug` does not list `-break-start`, which a build with the "
            f"debugger does. The readers of the machine (`registers`, `read_memory`, "
            f"`memdump`, `step`, `debug`), the breakpoints, the watches and the symbol "
            f"placement all need it; the guest's log (`log`, `log_wait`), the captures and the "
            f"in-guest input do not")
    if not binaries.debugger(resolved.path):
        raise ds.Invalid("host_failed",
            f"{resolved.path} carries no debugger: `-helpdebug` lists `-break-start`, which a "
            f"build configured without the debugger lists too, and the binary holds none of the "
            f"debugger's own text. The readers of the machine, the breakpoints, the watches "
            f"and the symbol placement all need it; the guest's log, the captures and the "
            f"in-guest input do not")
    return st.reply(**dlaunch.binary_facts(resolved, binaries.VERSION_TIMEOUT_S), debugger=True,
                    heavy_debug=binaries.heavy_debug(resolved.path), tools=registered_tools())


# ---------------------------------------------------------- session: start, status, close

@tool("Start a DOSBox-X session", summary=one_line.start, on_cancel="kill")
def start(conf: str, cwd: str,
          session_seconds: Annotated[int, vocab.bounds(1, dlaunch.MAX_SECONDS)],
          shared: bool = False,
          display: Annotated[str, vocab.enum(window.DISPLAY_OPTIONS),
                             Field(description=window.DISPLAY_ARGUMENT)] = "",
          flags: list[str] | None = None, break_on_int3: bool = False, program: str = "",
          logfile: str = "", capture_video: bool = False, captures_dir: str = "",
          plan: list[dict[str, Any]] | None = None,
          settle_seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] | None = None,
          input_port: Annotated[int, vocab.bounds(0, dlaunch.INPUT_PORT_MAX)] = 0,
          state_dir: str = "",
          binary: str = "", background: bool | None = None,
          presence: Annotated[bool, Field(description=scry_presence.ARGUMENT)] = True,
          ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Open one live DOSBox-X session from your conf, parked at the debugger.

    Paths are absolute or `~`-led. `session_seconds`: the lifetime. `shared`: watched on
    `display`; false, headless. `flags`: argv tokens, a `-set` value one token. `logfile`: the
    guest's E9 channel, for `log`, `log_wait`, `drive`. `program` runs after autoexec;
    `capture_video` records it. `plan` runs as `perform` does, each wait bounded by
    `settle_seconds` (default {SETTLE_S}). `input_port`: COM1's TCP port, 0 a free one.
    `state_dir`: where `state_write` saves; empty, under `cwd`.

    Refused: a live session, a bad path, `session_seconds` out of range, `capture_video`
    without `program`, an `input_port` other than 0 outside {INPUT_PORT_MIN}-{INPUT_PORT_MAX}, or
    busy.

    Reply: `pid`, `stub`, `input_port`, `declarations` (`rearm`); with `plan`, its account.

    Reference: REFERENCE.md, The session.
    """
    return lifecycle.start(conf, cwd, session_seconds, shared, display, flags,
                           break_on_int3, program, logfile, capture_video, captures_dir, plan,
                           settle_seconds, input_port, state_dir, binary, background,
                           presence, bridge(ctx), _step_ops)


@tool("Session status", summary=one_line.status, read_only=True)
def status() -> dict[str, Any]:
    """What the session is right now. It records a stop no tool has reported
    (`stopped_on_its_own`) and applies what was queued while the guest ran
    (`applied_on_stop`).

    Reply: `pid`, `conf`, `conf_digest`, `conf_changed_on_disk`, `watched`, `bound_s`,
    `elapsed_s`, `terminal_bytes_dropped`, `drain_alive`, `drain_ended`, `captures`,
    `state_dir`, `pending` (`arm` refs, a `disarm` count, `symbols_load`, `base_remeasure`),
    `presence`, `declarations`, and with a session `pc` and `cpu_mode`. Also `last_stop`
    (`stop_seq`, `pc`, `cause`, `since_s`, `wall_at`). `session` carries `alive`, `running`,
    `altered` and each alarm while it holds.

    Reference: REFERENCE.md, What every reply carries.
    """
    if STATE.session is not None and STATE.session.alive():
        running.drain_if_stopped(STATE.session)   # `status` asks for no session, but uses one
    return st.reply(**st.process_facts(), last_stop=STATE.dated(),
                    pending=STATE.pending_summary(), **running.status_facts(STATE.session),
                    presence=lifecycle.presence_shown(STATE.session))


@tool("Close the session", summary=one_line.close, session_before=True, on_cancel="kill")
def close(detail: bool = False, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """End the session deliberately rather than waiting for its bound.

    Reply: `closed`, `ended_by` (`quit`, `killed`, `died`, `none`), `pid`, `stdout_tail` and
    `errorlog_tail` when the end was not a clean `quit`, or with `detail=True`. `exit_code` is
    an integer or unavailable with its `why`. `session` is the block before closing.
    """
    return lifecycle.close(bridge(ctx), detail)


# ------------------------------------------------------------------ the guest's own log

@tool("Read the log", summary=one_line.log, read_only=True)
def log(pattern: str, channel: Annotated[str, vocab.enum(dlogs.LOG_CHANNELS)],
        limit: Annotated[int, vocab.bounds(1, dlogs.LOG_LIMIT_MAX)] = 40,
        labels: bool = False,
        since_mark: Annotated[int, log_marks.SINCE_MARK_BOUND] = 0) -> dict[str, Any]:
    """The session's log, one `channel` (`guest`, `emulator`, `all`) filtered by the Python regex
    `pattern`; `limit` keeps the newest matches; `labels=True` adds `labels`. `since_mark` (a
    byte position, from a `mark`) reads only what follows. Needs a session with `logfile`; works
    on a running guest.

    Reply: `channel`, `lines`, `lines_total`, `truncated`, `labels`, `pattern`. INVALID with
    `code`: no `logfile`, no log yet, no guest instrumentation, `limit` out of range, a bad
    pattern, an unknown channel (`process` is refused by name), a `since_mark` naming no
    position. To wait for a line use `log_wait`.

    Reference: REFERENCE.md, The log.
    """
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

    Reply: `verdict` `TARGET`, `pattern`, `channel`, `line` (the first match), `already`,
    `waited_s`, `lines_before`, `lines_total`, `arrived_during`, `lines_examined`; on timeout
    `verdict` `TIMEOUT` with `note`, `arrived_during`, `lines_examined`, `waited_s`. `status:
    INVALID`: `wait_stopped` on a stopped machine whose log lacks the line, `session_broken`
    when the emulator went away; no `logfile`, a bad `seconds`, regex, channel or `since_mark`
    are refused.

    Reference: REFERENCE.md, The log.
    """
    session = live()
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
    """The register pane. `from_last_stop=True` returns the registers of the last stop, never the
    current value; refused before any stop.

    Reply: `regs` (hex strings), `superseded`. CR0, CR3 and descriptor tables:
    `machine_map(sections=["control"])`.
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
                length: Annotated[int, vocab.bounds(1, dcons.DATA_VIEW_BYTES)] = 16,
                ) -> dict[str, Any]:
    """`length` bytes (1..{READ_MAX}) at `ref`, a symbol or `SEG:OFF` (a bare number is read as a
    symbol).

    Reply: `hex`, `length`, `rows` (the data view's), `seg_off`, `ref`. A view holding fewer
    bytes than asked is `readback_refused`; above it use `memdump`. An absent or ambiguous
    symbol is refused.
    """
    session = live()                 # `length` is judged by the registry, before the call
    seg, off = placement.read_target(ref, "DS", session)
    rows = session.read_memory(seg, off)
    return st.reply(ref=ref, seg_off=st.seg_off(seg, off), length=length,
                    hex=dcons.bytes_of_rows(rows, off, length), rows=rows)


@tool("Disassemble code", summary=one_line.disassemble, read_only=True)
def disassemble(ref: str, length: Annotated[int, vocab.bounds(1, code.LENGTH_MAX)] = 16,
                ) -> dict[str, Any]:
    """Decode `length` bytes from `ref` (a symbol or `SEG:OFF`) as x86, one instruction a line. The
    last is completed unless the segment ends first.

    Reply: `seg_off`, `length`, `code_bits`, `code_bits_from`, `lines`, `flow` (per line:
    `call`, `branch`, `return`, `sequential`, `unknown`), `flow_source`, and with symbols loaded
    `resolved` (direct call/branch targets and memory operands: `line`, `operand`, `seg_off`,
    `addr`, `symbol`, `delta`).

    Refused: `length` out of range or past the end of a 16-bit segment; `memdump`'s refusals
    apply.

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(ref=ref, **code.disassemble(live(), ref, length))


@tool("Guess the call stack", summary=one_line.call_stack, read_only=True)
def call_stack() -> dict[str, Any]:
    """A heuristic chain of the stop's callers, never a verdict: frame pointers walked (`push
    bp`/`mov bp, sp`, `enter`), each return kept only when a call instruction ends there. Row 0
    is the stop.

    Reply: `heuristic`, `code_bits`, `calls` (innermost first: `seg_off`, `addr`, `symbol`,
    `delta`, `via`, `call`, `bp`), `truncated`, `ended_why`. Refused when the register pane
    shows no SS, ESP or EBP. A routine with no frame pointer is invisible.

    Reference: REFERENCE.md, Reading and writing.
    """
    return st.reply(**code.call_stack(live()))


@tool("Dump memory to a file", summary=one_line.memdump, replay="drop")
def memdump(ref: str, length: int, dest: str) -> dict[str, Any]:
    """`length` bytes from `ref` (a symbol or `SEG:OFF`) to the new file `dest` (absolute).

    Reply: `ref`, `seg_off`, `length`, `path`, `bytes`. Refused: a dump file already where the
    debugger writes or at `dest`, a `dest` directly in that directory, an absent or ambiguous
    symbol; in protected mode a 16-bit segment, a range past its limit, or no descriptor (needs
    `logfile`).
    """
    session = live()
    ds.console_listening(session, "a dump")
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
    ds.console_listening(session, "a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.find(session, seg, off, length, pattern))


@tool("Value scan", summary=methods.fold_line("scan", folds.SCAN), replay="drop")
def scan(method: Annotated[str, vocab.enum(tuple(folds.SCAN))], ref: str = "",
         length: int | None = None,
         cell_bytes: Annotated[int, vocab.enum(finder.CELL_BYTES)] | None = None,
         operator: Annotated[str, vocab.enum(finder.OPERATORS)] | None = None,
         value: judges.NumberArg | None = None,
         limit: Annotated[int, vocab.bounds(1, judges.HITS_MAX)] | None = None,
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
    words; a `value` wider than the cell. An answer this cannot read clears the debugger's
    command line before refusing (`line_recovered`).

    Reference: REFERENCE.md, Reading and writing.
    """
    return methods.dispatch(folds.SCAN, locals())




#: The debugger's commands that write the guest, read in upstream's command parser: memory
#: (`SM`, `SMV`), registers (`SR`), an interrupt taken (`INTT`), a timer IRQ raised at the PIC
#: (`TIMERIRQ`), a state loaded (`LOADSTATE`), a port written (`OUTB`/`OUTP`/`OUTW`/`OUTD`), and
#: the BIOS clock (`TIME`, `DATE`: both reset its midnight flag, set or not). Breakpoints and
#: listings write no guest state.
DEBUG_WRITES = frozenset({"SM", "SMV", "SR", "INTT", "TIMERIRQ", "LOADSTATE", "OUTB", "OUTP",
                          "OUTW", "OUTD", "TIME", "DATE"})


@tool("Debugger console command", summary=one_line.debug)
def debug(command: str) -> dict[str, Any]:
    """One raw `command` to the debugger console; the last resort. For a value use `registers`,
    `read_memory` or `memdump`; for the log `log`.

    Reply: `screen_delta` (the last {DEBUG_TEXT_KEEP} characters of the screen's repaint),
    `screen_chars`, `clipped`, `command`, `note`.

    Refused `bad_argument`: a command that lets the guest run (`VRT`, `RUNWATCH`, `INT`, the
    `LOG` family) and a control character.
    """
    session = live()
    ds.console_listening(session, repr(command))
    # A SCAN COMMAND TYPED HERE moves the debugger's own count past the one `scan(method="filter")`
    # keeps,
    # and may open a scan at another width, so both are dropped rather than answered stale.
    if command.strip().upper().startswith(("MEMS", "MEMFIND")):
        STATE.scan_forget()
    # A COMMAND THAT WRITES THE GUEST (`DEBUG_WRITES`) marks the session as `write` and
    # `set_register` do, before it is typed: what reaches the machine has been written.
    if command.split()[:1] and command.split()[0].upper() in DEBUG_WRITES:
        session.altered = True
    out = session.command(command)
    if not out.strip():
        raise ds.Invalid("unexpected_answer",
            f"the debugger produced nothing for {command!r}: an empty "
                         f"screen delta is not an empty answer, it is no answer")
    # THE CONSOLE IS LEFT CLEAN, whatever the command did to it: a listing that paged is paged
    # out, and a line the debugger did not take is emptied, so no later tool types onto it.
    notes = []
    if dcons.at_pager(out):
        out += session.end_pager()
        notes.append(PAGED_NOTE)
    if held := dcons.input_line(out):
        session.clear_line()
        notes.append(f"the debugger did not take {held!r} (still on its input line after the "
                     f"prompt came back), so the line was emptied and the next command runs "
                     f"on its own")
    return st.reply(command=command, **st.delta(out, st.DEBUG_TEXT_KEEP),
                    **({"note": "; ".join(notes)} if notes else {}))


#: What `debug` says of a command whose listing paged.
PAGED_NOTE = "the listing paged: `Q` ended the pager and the rest of it is in `screen_delta`"


@tool("Force a register", summary=one_line.set_register)
def set_register(name: str, value: judges.NumberArg) -> dict[str, Any]:
    """Write one register and read it back off the pane; marks the session `altered`. Needs the
    machine stopped.

    `name` is a register the debugger's `SR` takes (`eax`, `ax`, `ip`); a negative or too wide
    `value` is refused unsent.

    Reply: `register`, `regs`, `value`, `readback` (both `0x` at the register's width),
    `verified`. INVALID when no pane came back.
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

@tool("Resume the machine", summary=one_line.resume, on_cancel="none", replay="wall")
def resume(seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] = 0.0, detail: bool = False,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Let the machine run. `seconds` 0 (the default) returns at once; a bound up to {WAIT_MAX_S}
    waits for a stop and, if none comes, leaves it running. Needs a stopped machine.

    Reply: with a bound, `verdict` (`OTHER_STOP` with the stop reply of `run_to`; `TIMEOUT`,
    `waited_s`, `note`). `screen_delta` (with `detail=True`: the repaint's last
    {DETAIL_TEXT_KEEP} characters; else `omitted`).

    Reference: REFERENCE.md, Advancing the machine.
    """
    return advance.resume(seconds, detail, bridge(ctx))


@tool("Stop a running machine", summary=one_line.stop, on_cancel="stop", replay="wall")
def stop(ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Bring a running guest back to the debugger and survey the stop, headless or windowed.

    Reply: `interrupted` (`true` with the stop reply and `via: "break"`; `false` when already
    stopped, with a `note`). INVALID `not_settled`: the `BREAK` got no prompt; ask again.

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
                            "(a cut pane; the next contact retries)"))
    session.break_in()
    return running.stop_reply(session, asked_by="stop", interrupted=True, via="break")


@tool("Step instructions", summary=one_line.step)
def step(count: Annotated[int, vocab.bounds(1, ds.STEP_MAX)] = 1,
         mode: Annotated[str, vocab.enum(ds.STEP_MODES)] = "into") -> dict[str, Any]:
    """`count` instructions, each read back; `mode` `into` (F11) or `over` (F10). Needs the machine
    stopped.

    Reply: `mode`, `asked`, `before`, `after`, `instructions_completed`, `moved`, `stalled`
    (CS:EIP unchanged after a step), and the stop reply; an `over` whose call never returns
    leaves the guest running, with no stop reply. For longer runs `run_to`.
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


@tool("Run to a place, with a control", summary=one_line.run_to, on_cancel="stop")
def run_to(ref: str, control: str, seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run until a symbol or a `SEG:OFF` and say where it stopped.

    `ref`: a loaded symbol or hex `SEG:OFF`. `control` is required: a second ref known to be
    hot, counted when it fires, so a bound that expires with no control hit is INVALID, not "it
    did not arrive". Needs a stopped machine. Refused: an absent or ambiguous name.

    Reply: `verdict` (`TARGET`, `OTHER_STOP`, `TIMEOUT`), `target_disarmed`, `control_hits`,
    `controls` (`ref`, `at`, `hits_in_run`), `note`, the stop (`pc`, `regs`, `cause`). INVALID:
    `control_silent`, `cut_by_other_stop`, `not_settled`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    return advance.run_to(ref, control, seconds, bridge(ctx))


@tool("Run for frames or emulated time", summary=one_line.run_for, on_cancel="stop")
def run_for(milliseconds: int = 0, frames: int = 0,
            seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run for `frames` display frames (one `VRT` each) or `milliseconds` of emulated time (exactly
    one) and come back STOPPED. Reports progress while it waits. Needs the machine stopped.

    Reply: `verdict` (`ELAPSED`, `OTHER_STOP`, `TIMEOUT`), `polls`, `emulated_before_s`,
    `emulated_after_s`, `frame_before`, `frame_after`, `cycles` (unavailable with why),
    `retrace_pending`, `note`, {STOP_FIELDS}. INVALID: `no_progress`, `unexpected_answer`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    ds.console_listening(session, "a `VRT`")
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
    captures. Needs a stopped machine, a writable working directory and `build_check`'s
    `heavy_debug`; a dynamic core needs `start(flags=["-set", "cpu core=normal"])`.

    Reply: `verdict`, the stop reply of `run_to`, `trace` (`path`, `instructions`, `addresses`,
    `unplaced`, `set_path`, `symbols` (first {SYMBOLS_SHOWN})). Refused: `no_channel`,
    `readback_refused`, `host_failed`.

    Reference: REFERENCE.md, Advancing the machine.
    """
    session = live()
    return tracing.trace(session, instructions, shape,
                         paths.absolute("dest", dest) if dest else None, seconds, bridge(ctx))


@tool("Run until text is on screen", summary=one_line.screen_wait, on_cancel="stop", replay="wall")
def screen_wait(text: str, seconds: Annotated[float, vocab.WAIT_BOUNDS] = 30.0,
                ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run the machine retrace by retrace until `text` is on the TEXT screen, and stop there.
    `text` (1 to {SCREEN_TEXT_MAX} code page 437 characters) is matched literally,
    case-sensitive, inside one row as `screen_view` reads it. Needs a stopped machine and a
    session started with `logfile`. Already on screen: answered at once. Each retrace costs a
    stop and five round trips, so `run_for` first for a distant string.

    Reply: `verdict` `TARGET` (`already`, `waited_s`, `polls`, `point` `[column, row]`, `line`)
    or `TIMEOUT` (`waited_s`, `polls`, `text`, `retrace_pending`), `note`, the stop reply of
    `run_to`. Refused: `bad_argument`, `wait_stopped` (a declared breakpoint stopped it),
    `no_channel` (no `logfile`).

    Reference: REFERENCE.md, Input and the screen.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return retrace.screen_wait(session, text, seconds, bridge(ctx))




@tool("Snapshot the screen to a PNG", summary=one_line.snapshot, on_cancel="none", replay="drop")
def snapshot(dest: str = "", seconds: Annotated[float, vocab.WAIT_BOUNDS] = ds.SNAPSHOT_WAIT_S,
             ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """A still of the running screen, taken in the guest into the captures directory within
    `seconds`, moved to `dest` if given (absolute, new). Refused: parked at the debugger, no
    `logfile`, no stub in the log.

    Reply: `route`, `path`, `bytes`, `sha256`.
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
    `LOADSTATE`; no window or focus needed. A running guest is stopped for it and released
    again. `name`: letters, digits, `_`, `-`, a letter or digit first, at most {STATE_NAME_MAX},
    not digits only. `seconds` bounds the command's reply.

    `save`: never overwrites. Reply: `name`, `path`, `bytes`, `version`, `program`, `machine`,
    `memory_mb`, `saved_at`, `paused`.

    `load`: replaces the machine, altering the session. Reply: `name`, `path`, the state's own
    members, `paused`, `mark`.

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
    `already_stored`, `armed`, `state`, `entry`; with `detail=True` also `screen_delta`.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.breakpoint_interrupt(live(), number, ah, detail)


# --------------------------------------------------------------- names for addresses

@tool("Load a symbol table", summary=one_line.symbols_load)
def symbols_load(path: str, base: str = "",
                 base_from: Annotated[str, vocab.folded(ds.SELINFO_REGS)] = "CS",
                 pattern: str = "", keep_noise: bool = False,
                 section_bases: dict[str, str] | None = None, types: str = "",
                 ) -> dict[str, Any]:
    """Load a toolchain's symbol list so other tools take names. Stop inside the program first;
    with an explicit `base` a running guest works too (`pending: true`).

    `path`: `nm` output or a GNU `ld`, Borland or Watcom map. Flat lists take `base` (hex text,
    required in real mode); sectioned maps take `section_bases`. `types`, `pattern`,
    `keep_noise` filter and type rows.

    Refused (INVALID): both `base` and `section_bases`; a sectioned map without
    `section_bases`; real mode or a running machine without `base`; a mostly unreadable file;
    a table the `<stem>.exe` contradicts.

    Reply: `parsed`, `kept`, `loaded`, `table_mode`, `table_total`, `renamed`, `pending`,
    `base`, `checked`, `declarations`.

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
                 linear: str = "",
                 limit: Annotated[int, vocab.bounds(1, placement.SYMBOLS_LIMIT_MAX)] = 10,
                 ) -> dict[str, Any]:
    """Look a symbol up in the table `symbols_load` kept. `name`: exact, else prefixes up to
    `limit`. `offset` (an integer) or `linear` (hex text), with `section`: the nearest symbol at
    or below.

    Reply: `query`, `symbols_total`, `symbols` (`name`, `offset`, `addr`),
    `truncated`; by address, the symbol's fields and `delta`. INVALID: no table.
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

    `add`: `text` (one printable line, at most {COMMENT_BYTES_MAX} UTF-8 bytes) on `ref`,
    a symbol or a `SEG:OFF`; a second there replaces it. Reply: `comment`, `replaced_comments`,
    `declarations`, `note`.

    `delete`: the comment `ref` names. Reply: `deleted`, `declarations`, `note`.

    `save`: every comment to `dest`, an absolute path, replacing a comment file there (rows
    only it held in `dropped_comments`); any other file is refused; answers on a running guest.
    Reply: `path`, `comments_total`, `dropped_comments`, `dropped_total`, `truncated`, `note`.

    `load`: the comment file at `path`, all or nothing, the file winning. Reply: `path`,
    `parsed`, `added`, `replaced_comments`, `replaced_total`, `truncated`, `unchanged`,
    `comments_total`, `declarations`, `note`.

    `add`, `delete` and `load` need the machine stopped. Refused: an argument the method
    does not take, a misshapen `ref` or `text` (`bad_argument`), a name defined twice
    (`ambiguous_ref`), an unknown `ref` (`unknown_ref`), an unwritable store (`host_failed`).

    Reference: REFERENCE.md, Declarations.
    """
    return methods.dispatch(folds.COMMENT, locals())





# ---------------------------------------------------------------------- the DOS machine

@tool("Map the machine", summary=one_line.machine_map, replay="drop")
def machine_map(sections: list[Annotated[str, vocab.enum(machine.SECTION_NAMES)]] | None = None,
                dest: str = "") -> dict[str, Any]:
    """What the DOS machine is at this stop: one section per debugger listing, read off the logfile
    (needs `logfile`). `sections` left out reads the DOS machine and `control`; `bios_mem`,
    `callbacks`, `vga`, `paging` only when named. `dest` (absolute, new) writes all sections
    whole as JSON. Writes nothing to the guest.

    Reply: `cpu_mode`, one key per section read as rows, `counts`, `truncated` (cut at
    {LOG_LIMIT_MAX} rows), `sources`, `coverage_note` (why a section is absent), `path`.
    Refused: bad `sections` or an existing `dest` (`bad_argument`); no `logfile` (`no_channel`);
    a running guest (`not_stopped`); no prompt after a listing (`unexpected_answer`: `close`).

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
    ds.console_listening(session, "`INTVEC`")
    return st.reply(**machine.interrupt_vectors(session, number))


# ------------------------------------------------------------------------ the screen

@tool("Read the palette", summary=one_line.palette, replay="drop")
def palette(first: Annotated[int, vocab.bounds(0, vgadac.DAC_ENTRIES - 1)] | str = 0,
            count: Annotated[int, vocab.bounds(0, vgadac.DAC_ENTRIES)] = 0, scale: int = 0,
            dest: str = "") -> dict[str, Any]:
    """The VGA DAC's 256 colours at this stop, read off the `VGA DAC` listings in the logfile
    (needs `logfile`), with an indexed PNG swatch. `first` and `count` (0 for all from `first`)
    choose entries, `first + count` at most 256. `scale` 0 fits the largest enlargement up to 8;
    `dest` a new path, else a scratch gone at `close`.

    Reply: `entries`, `first`, `count`, `colors` (`#rrggbb`), `rgb`, `bits`, `pel_mask`,
    `image`.

    Refused: an entry past 255, a bad `scale`, a relative or existing `dest` (`bad_argument`);
    no `logfile` (`no_channel`); a running guest (`not_stopped`); a DAC not six-bit
    (`unexpected_answer`); a picture not taken whole (`host_failed`).

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
    """What the screen shows at this stop, read from video memory (needs `logfile`): text as text,
    the chained 256-colour mode (13h) as a PNG. `crop` is `[x, y, width, height]` in characters
    or pixels. `scale` 0 fits the largest up to 8x; `dest` a new path (else a scratch); `attach`
    false leaves it unattached.

    Reply: `vga_mode`, `kind`, `width`, `height`, `crop`, `display_start`; in text `text`,
    `cursor`; in 256 colours `image`.

    Refused: a relative or existing `dest`, a bad `scale` or `crop`, `dest`/`scale`/`attach` in
    text (`bad_argument`); another mode (naming `capture_frame`), an undecodable layout or no
    `logfile` (`no_channel`); a running guest (`not_stopped`); a DAC not six-bit
    (`unexpected_answer`).

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
    """One hex string for what is on screen or on `crop` `[x, y, width, height]`: the `scry-sig/1`
    signature of a series row (text cells by byte and colours, 256-colour pixels by DAC colour;
    no cursor). Reads what `screen_view` reads (needs `logfile`).

    Reply: `signature`, `kind`, `width`, `height`, `crop`, `vga_mode`. Refusals as
    `screen_view`, `dest` and `scale` aside.

    Reference: REFERENCE.md, Media files.
    """
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**screen.screen_signature(session, crop))


# ------------------------------------------------------------------- the screen maps



@tool("Which mapped screen is this", summary=one_line.map_find, read_only=True,
      replay=("matched", "screen"))
def map_find() -> dict[str, Any]:
    """Which mapped screen the machine shows. Reply: `matched`; matched, `screen`, `layer`, `kind`,
    `size`, `controls` (`name`, `rect`, `centre`); else `screens_mapped`, `screens_tried`. None
    mapped: `needs_call`.

    Reference: REFERENCE.md, Screen maps.
    """
    session = live()
    ds.console_listening(session, "a listing")
    # The stop the read is of, or None when that stop's own record could not be made (a cut
    # pane): a previous stop's number would date the identification wrong.
    current = STATE.as_of_current(session)
    return st.reply(**STATE.maps.find(folds.map_read(session),
                                      None if current is None else current["stop_seq"]))


@tool("Write the screen map", summary=methods.fold_line("map_write", folds.MAP),
      replay={"add": "step", "load": "step", "save": "drop"})
def map_write(method: Annotated[str, vocab.enum(tuple(folds.MAP))], screen: str = "",
              match: list[list[int]] | None = None, controls: list[dict[str, Any]] | None = None,
              path: str = "", dest: str = "", overwrite: bool | None = None) -> dict[str, Any]:
    """The screen map: an application's screens, each known by the signatures of its stable
    regions, and their controls, in a session layer and a file layer.

    `add`: the screen shown now as `screen` in the session layer, one read signing each `match`
    crop ([x, y, width, height], 1..16), `controls` ([{"name", "rect"}]) in the screen's own
    units; needs `logfile`. Reply: `screen`, `kind`, `size`, `match`, `controls`, `replaced`,
    `shadows_file`.

    `load`: `path` (`<application>{MAP_SUFFIX}`, absolute or `~`-led) as the file layer. Reply:
    `path`, `application`, `screens`, `controls`.

    `save`: both layers as one map to `dest`, refused there without `overwrite`, made the file
    layer. Reply: `path`, `application`, `screens`, `controls`, `promoted`.

    Refused: an argument the method does not take; a misshapen name, crop, control or file
    (`bad_argument`); nothing mapped to save (`needs_call`); the modes `screen_view` refuses.

    Reference: REFERENCE.md, Screen maps.
    """
    return methods.dispatch(folds.MAP, locals())



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


# --------------------------------------------------- declarations: breakpoints, watches

@tool("Declare a breakpoint", summary=one_line.breakpoint_at)
def breakpoint_at(ref: str, by: Annotated[str, vocab.enum(checks.BREAKPOINT_BY)] = "auto",
                  ) -> dict[str, Any]:
    """Declare a code breakpoint at a symbol or `SEG:OFF`, and arm it if it can be. Stored, and
    re-armed on `symbols_load`; a raw `SEG:OFF` goes `stale` over another build.

    Refused: a name matching several symbols; an address another declaration holds, naming it.
    A symbol absent from this build is stored `unresolved`.

    Reply: `ref`, `stored`, `already_stored`, `armed`, `entry`, `state` (`armed`,
    `unresolved`, `unarmable`, `pending` while the guest runs), `why`, `marked` and `note` for
    a linker-marked symbol.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.breakpoint_at(live(), ref, by)


@tool("List the declarations", summary=one_line.declaration_list, read_only=True)
def declaration_list(kind: Annotated[str, vocab.enum(("", *folds.KINDS))] = "",
                     ) -> dict[str, Any]:
    """List the declarations of `kind` (empty: every kind) with their state, cross-referenced
    with the debugger's own list. On a running guest the states are the last stop's survey
    (`debugger_read` false).

    Reply: `breakpoints`, `watches` (each kind asked; each row `ref`, `by`, `cpu`,
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
              ) -> dict[str, Any]:
    """Declare a watch by symbol, `SEG:OFF` or through a pointer, read as `fmt`. Persists and
    re-resolves on `symbols_load`.

    `mode`: `show` (read at each stop) or `change` (stops when the bytes change). `ref`: a
    symbol, `SEG:OFF`, or `[base]+0x28`, `base->field`. `fmt`: a scalar (`u8` .. `f64`), an
    array (`u16[8]`), a string (`char[16]`) or a struct (`{x:i16,y:i16}`). `length`: total
    bytes; at most {READ_MAX} for show, {CHANGE_WATCH_MAX} for change (a debugger row per byte,
    `entries`).

    Refused: one ref as both modes; a length over the ceiling; a pointer base the table lacks.

    Reply: `ref`, `stored`, `already_stored`, `state` (`evaluated`, `unresolved`, `unarmable`,
    `null_pointer`, `pending`), `armed`, `pointer`, `entry`, `caveat`.

    Reference: REFERENCE.md, Declarations.
    """
    return arming.watch_add(live(), ref, mode, length, fmt, by)




# ------------------------------------------------------------ input to a running guest

@tool("Send keystrokes", summary=one_line.send_keys, on_cancel="none")
def send_keys(keys: list[str],
              modifiers: list[Annotated[str, vocab.folded(inputs.MODIFIER_WORDS)]] | None = None,
              expect: str = "", seconds: Annotated[float, vocab.WAIT_BOUNDS] | None = None,
              ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Send keystrokes to the running guest; with `expect`, prove the program took them.

    `keys`: at most {KEYS_MAX}. `expect`: a regex over the E9 log the program's
    reaction writes, waited up to `seconds` (default {EFFECT_WAIT_S}).

    Refused: an unknown key or modifier, `seconds` without `expect`, a stopped machine, no
    stub (`no_channel`).

    Reply: `route`, `posted`, `bytes`, `ticks`, `verify` (`verdict` `TARGET` or `TIMEOUT`,
    `seen`).

    Reference: REFERENCE.md, Input and the screen.
    """
    return inputs.send_keys(live(), keys, modifiers, expect or None, seconds, bridge(ctx))


@tool("Send mouse input", summary=one_line.send_mouse, on_cancel="none")
def send_mouse(x: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               y: Annotated[int, vocab.bounds(0, inputs.MAX_COORD)] | None = None,
               button: Annotated[str, vocab.enum(("", *inputs.BUTTON_WORDS))] = "",
               action: Annotated[str, vocab.enum(inputs.ACTIONS)] = "click",
               units: Annotated[str, vocab.enum(inputs.UNITS)] = "screen", expect: str = "",
               seconds: Annotated[float, vocab.WAIT_BOUNDS] | None = None, target: str = "",
               ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Move the guest's mouse pointer, press buttons, and read the pointer back; `expect`
    proves the program reacted, as in `send_keys`.

    `x`, `y`: both or neither, in `units`. `target`: a control of the latest `map_find` screen,
    instead of `x`, `y`. A drag is `down`, a move, `up`.

    Refused: no move and no button, half a move, a place off the screen, a stopped machine, no
    stub; `target` beside `x`, `y` or `units="mouse"` (`bad_argument`); no `map_find` match
    (`needs_call`); an unknown control (`unknown_ref`).

    Reply: `route`, `pointer`, `arrived` (else `asked`), `verify`; with `target`: `target`,
    `screen`, `identified_at_stop`.

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
    dpresence.pointer_moved(dpresence.of(STATE.session))
    return moved


# ----------------------------------------------------------------------- the captures

@tool("List this session's captures", summary=one_line.captures, read_only=True)
def captures() -> dict[str, Any]:
    """Lists the files the session's tools wrote, in write order, re-read now, then the
    `capture_video` AVIs, largest last. Works on a running guest.

    Reply: `captures` (each `kind`, `path`, `present`, `bytes`; an AVI also `riff_avi`,
    `avi_frames`, `complete`). A file gone has `present: false`, no `bytes`.
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
                              paths.input_file("capture_path", capture_path, "capture")
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

    Kept: moving calls and checks (`read_memory`, `registers`, `screen_signature`, `map_find`,
    `image_compare(method="golden")`), each held to its `recorded` reply. Other calls drop;
    the first no replay can place, or past {RECORD_MAX}, cuts the rest.

    `dest` (`.json`) is refused if present unless `overwrite`. Reply: `path`, `steps`,
    `checks`, `dropped`, `dropped_total`, `cut`, `replay`; `no_recording` if empty.

    Reference: REFERENCE.md, From an investigation to a bench.
    """
    return st.reply(**recording.export(RECORDER, dest, overwrite))


#: `summaries`' own description, `perform`'s and `drive`'s, as scry-core words it.
SUMMARIES_ARGUMENT = account.summaries_argument(st.ROWS_SHOWN)


@tool("Run a sequence of steps", summary=one_line.perform, on_cancel="stop")
def perform(steps: list[dict[str, Any]],
            settle_seconds: Annotated[float, vocab.WAIT_FROM_ZERO_BOUNDS] = 30.0,
            summaries: Annotated[bool, Field(description=SUMMARIES_ARGUMENT)] = False,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """Run this server's operations in order on the open session, stopping at the first
    failure.

    `steps`: `{"op": <tool>, ...arguments}`, any tool but `build_check`, `start`, `close`,
    `perform`, `drive`, `perform_export`. A `send_keys` or `send_mouse` whose `expect`
    misses ends the list `TIMEOUT`. A step's `recorded` must hold, else INVALID `diverged`.
    The whole list is checked first: INVALID `errors` (`step`, `op`, `code`, `message`),
    nothing run. `settle_seconds` bounds each wait for a stop before a step that needs one (0:
    never wait).

    Reply: `ran`, `steps_completed`, `held`, `failed_at`, `failed` (INVALID `step_failed`),
    `verdict` (`TARGET` adds `stopped`, `TIMEOUT` `note`), else `still_running`.

    Reference: REFERENCE.md, Sequences in one call.
    """
    return sequence.run_steps(live(), steps, settle_seconds, _step_ops(), bridge(ctx), summaries)


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

#: What the reference pages are generated from
#: (`python -m scry_core.reference dosbox_x_server:REFERENCE`) and held to
#: (`tests/test_dosbox_x_reference_pages.py`).
REFERENCE = reference.Registry(server=mcp, models=dosbox_replies.MODELS, roster=ROSTER,
                               envelope=dosbox_replies.DosboxEnvelope,
                               root=Path(__file__).resolve().parent)


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
    process_name.set_title(dprocess.PROCESS_NAME)
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
