"""One live DOSBox-X session, held open, and the pseudo-terminal that drives it.

A pseudo-terminal and not a pipe: the debugger is ncurses, which talks to a terminal. Echo is
turned off before the spawn, since a terminal echoes with no child at all; `command()` returns
only the delta a command produced. Launch, console grammar, logs, collection, the process base
and the log/frame/state/symbol bodies are the `dosbox_*` modules `Session` delegates to.
"""

from __future__ import annotations

import contextlib
import os
import re
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import avi, cancel, judges, presence
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.progress import PROGRESS_EVERY_S as PROGRESS_EVERY_S
from scry_core.progress import Progress as Progress
from scry_core.progress import no_progress as no_progress
from scry_core.reply_contract import Invalid as Invalid

import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_launch as dlaunch
import dosbox_paths as paths
import dosbox_process as dprocess
import dosbox_stub_link as stub_link

# The var-list ENCODING lives next door, in a module with no emulator in it, so a golden can exist
# over the bytes without a machine.

# HOW LONG A HELD HEAD MAY GET before it is given up and emitted as text.
PENDING_MAX = 4 * 1024


# HOW LONG A CONSOLE REPLY IS GIVEN (`Session.command`): quiet for `SETTLE_S` once something has
# arrived ends it.
SETTLE_S = 0.6
REPLY_TIMEOUT_S = 6.0
# A reply that ends in the debugger's own last words (`dosbox_console.REPLY_END`) is whole after
# `REPLY_GRACE_S` of quiet.
REPLY_GRACE_S = 0.15
# How the collect slices its wait, and how much raw terminal it keeps to look for that end.
COLLECT_SLICE_S = 0.05
RAW_TAIL_KEEP = 512


# WHERE EACH SETTABLE NAME IS READ BACK, and at what width in bits.
READBACK: dict[str, tuple[str, int]] = {
    **{n.lower(): (n, 32) for n in dcons.WIDE_NAMES},
    **{n.lower(): (n, 16) for n in dcons.SEGMENT_NAMES},
    **{n: (f"E{n.upper()}", 16) for n in dcons.LOW_HALVES},
}

# A command that is guaranteed to REPAINT and changes nothing.
NUDGE = "BPLIST"


# The keys the debugger's own help names: "F5 - Run." and "F10/F11 - Step over / trace into
# instruction." They go as terminal.
STEP_KEYS = {"over": b"\x1b[21~", "into": b"\x1b[23~"}
#: The ways to step, as `step` takes them.
STEP_MODES = tuple(STEP_KEYS)

# F5, "Run.".
RUN_KEY = b"\x1b[15~"
# `VRT`: run, and stop at the next vertical retrace.
RETRACE_COMMAND = b"VRT\r"
# Every key that can leave the machine RUNNING, `run_for`'s typed `VRT` among them.
RELEASE_KEYS = (RUN_KEY, STEP_KEYS["over"], STEP_KEYS["into"], RETRACE_COMMAND)
# THE `LOG` FAMILY, one word per line shape: typed with its hex count.
LOG_WORDS = ("LOG", "LOGS", "LOGL", "LOGC")
LOG_COMMAND = re.compile(rb"(?:" + "|".join(LOG_WORDS).encode() + rb") [0-9A-F]+\r")

# THE CEILING ON ONE `step` CALL, and it is a cost bound rather than a safety one.
STEP_MAX = 64


# `MEMDUMPBIN [s]:[o] [len] [filename]` writes memory to a file in the debugger's working
# directory.
MEMDUMP_NAME = "memdump.bin"
# Passed because a build whose parser reads an optional name and is given none reads that name from
# past the end of the line.
MEMDUMP_FILE = "MCPDUMP.BIN"
# The two lines `SaveMemoryBin` prints (upstream `src/debug/debug.cpp`).
MEMDUMP_OK = "Memory dump binary success"
MEMDUMP_FAIL = "Memory binary dump failed"

# `INTVEC <file>` writes the vector table into the emulator's WORKING DIRECTORY, one line per
# vector (`INT nn: SSSS:OOOO`).
INTVEC_FILE = "MCPIVT.TXT"
INTVEC_OK = "Interrupt vector table written to"

# `SELINFO [segName]` prints `DS: b:00400000 type:13 parbg / l:0023FFFF dpl : 3 10011`, the five
# digits under `parbg`'s letters.
SELINFO_ECHO = "SelectorInfo"
# THE `.*?` BETWEEN `type:` AND `l:` IS BOUNDED, and that bound is the whole of its correctness.
SELINFO_FIELDS = re.compile(
    r"b:([0-9A-Fa-f]{8})\s+type:([0-9A-Fa-f]{2}).{0,64}?l:([0-9A-Fa-f]{8})"
    r"\s+dpl\s*:\s*([0-3])\s+([01])([01])([01])([01])([01])", re.S)


# A descriptor with `type:00` IS NOT PRESENT, and returning its base would be the worst answer this
# module can give: zero.
SELINFO_ABSENT = 0
SELINFO_REGS = ("CS", "DS", "ES", "SS", "FS", "GS")

# `SV`/`LV` acknowledge with `Variable list save (NAME) : ok.` / `: failure.`.
SYM_SAVE_ECHO = "Variable list save"
SYM_LOAD_ECHO = "Variable list load"
SYM_OK = ") : ok."

# A `SV`/`LV` FILENAME IS CUT TO TWELVE CHARACTERS, SILENTLY, AND REPORTED `ok`.
SYM_ARG_MAX = 12
SYM_LOAD_NAME = "SYMS.BIN"
SYM_SAVE_NAME = "SYMSBK.BIN"


# THE CEILING ON EVERY WAIT, its schema halves and its judge are scry-core's (`vocab.WAIT_MAX_S`,
# `vocab.check_wait`).

# A BOUNDED WAIT REPORTS PROGRESS WITH A MESSAGE, through a callback the server hands in.

# `_screen` is trimmed to this.
SCREEN_KEEP = 256 * 1024


# How long `ffmpeg` is given to pull one frame out of a capture.
FFMPEG_SECS = 120



# THE REFUSAL is `scry_core.reply_contract.Invalid` (a code of the table, the prose, the context).


class NotStopped(Invalid):
    """No register pane came back."""

    def __init__(self, message: str, **fields: Any) -> None:
        super().__init__("not_stopped", message, **fields)


def _wait_stopped(pattern: str, arrived: int, waited_s: float,
                  at_bound: bool = False) -> Invalid:
    """The one refusal a wait gives for a machine at the debugger, found by a poll or as the bound
    ran out."""
    when = ("the bound expired and the machine is stopped at the debugger"
            if at_bound else "the machine is stopped at the debugger")
    return E9Stopped(
        f"{when}, so a wait for {pattern!r} cannot end: a stopped guest writes nothing. "
        f"{arrived} line(s) were on disk from the wait's start to this refusal, none "
        f"matching; the emulator flushes its log in its own time, so `e9` may show more. "
        f"Resume it rather than waiting", waited_s=waited_s, arrived=arrived)


class E9Stopped(Invalid):
    """A wait that cannot end because the machine is at the DEBUGGER."""

    def __init__(self, message: str, *, waited_s: float, arrived: int) -> None:
        super().__init__("wait_stopped", message)
        self.waited_s = waited_s
        self.arrived = arrived


def avi_facts(data: bytes) -> dict[str, object]:
    """What is IN a capture, not merely how big it is."""
    return {
        "bytes": len(data),
        "riff_avi": data[:4] == b"RIFF" and data[8:12] == b"AVI ",
        "avi_frames": avi.count(data),   # `scry_core.avi` says which count and why
        # `complete` is INFORMATION, not a usability verdict: ffmpeg extracts a frame from an
        # unindexed capture perfectly well.
        "complete": avi.finished(data),
    }


SCREENSHOT_COMMAND = b"S"   # the stub's opcode for the device's capture trigger (guest/inject.asm)

BREAK_IN_WAIT_S = 5.0     # from BREAK on the channel to the debugger's prompt on the terminal
SNAPSHOT_WAIT_S = 10.0
# A STATE IS SAVED AND LOADED BY THE DEBUGGER'S OWN COMMANDS, `SAVESTATE <file>` and `LOADSTATE
# <file>` over the debugger channel.
STATE_WAIT_S = 30.0


# ------------------------------------------------------------------ argument checks
# THE CHECKS THAT NEED NOTHING FROM THE MACHINE LIVE HERE AS FUNCTIONS, one per argument
# family, and the session methods call them first. They are also what `perform` runs over a
# WHOLE list before its first step: a batch enters through the same checks the synchronous
# call makes, so a value that would be refused mid-list is refused before anything ran.


def check_register_name(name: str) -> str:
    """The lower-case register `SR` takes, or the refusal naming the ones it does."""
    key = name.strip().lower()
    if key not in dcons.SETTABLE:
        raise Invalid("bad_argument", f"{name!r} is not a register this debugger sets. One of: "
                      f"{', '.join(sorted(dcons.SETTABLE))}")
    return key


def check_register_value(key: str, value: int) -> None:
    """A value `SR` can put in register `key`."""
    bits = READBACK[key][1]
    if value < 0:
        raise Invalid("bad_argument",
            f"value={value} is negative: {key} holds {bits} bits, 0 to {(1 << bits) - 1:#x}; "
            f"nothing was sent")
    if value >= 1 << bits:
        raise Invalid("bad_argument",
            f"value={value:#x} is wider than {key}'s {bits} bits (at most "
            f"{(1 << bits) - 1:#x}): nothing was sent")


#: An interrupt number and AH are one byte each.
BYTE_MAX = 0xFF


def check_interrupt(number: int, ah: int | None) -> None:
    if not 0 <= number <= BYTE_MAX:
        raise Invalid("bad_argument", f"an interrupt number is 0x00 to 0xFF; got {number}")
    if ah is not None and not 0 <= ah <= BYTE_MAX:
        raise Invalid("bad_argument", f"AH is 0x00 to 0xFF; got {ah}")


def check_step(mode: str, count: int) -> None:
    vocab.one_of("mode", mode, STEP_MODES,
                 ": `over` runs a CALL to its return, `into` follows it")
    if not 1 <= count <= STEP_MAX:
        raise Invalid("bad_argument",
            f"a step count is 1 to {STEP_MAX}; got {count}. Each step is "
                      f"a keystroke AND a repaint read back to prove it landed, so "
                      f"the ceiling is a cost bound: past it, use `run_to`")


def check_dump_length(length: int) -> None:
    if length <= 0:
        raise Invalid("bad_argument", f"a dump of {length} bytes is not a dump")


def check_frame_args(at: int, dest: Path) -> None:
    """A frame index and a destination ffmpeg will not misread."""
    if at < 0:
        raise Invalid("bad_argument", f"frame {at} is not a frame")
    if "%" in str(dest):
        raise Invalid("bad_argument",
            f"a destination containing `%` is refused: {str(dest)!r}. "
                      f"The still is written through ffmpeg's image2 muxer, which "
                      f"reads the whole path as a numbering template and writes "
                      f"somewhere else")


def _still_armed(exc: Invalid, target: str, began: float, ctl: str | None = None) -> Invalid:
    """The refusal that CARRIES the irreversible part."""
    also = f" (and so is the control at {ctl})" if ctl else ""
    return Invalid(exc.code,
                   f"{exc} -- and the breakpoint at {target}{also} is STILL ARMED after "
                   f"{round(time.monotonic() - began, 1)}s: this call wrote a trap byte "
                    f"into the guest and could not read the machine back to remove it, so "
                    f"it will stop the next `resume`")


def console_listening(session: Session, what: str) -> None:
    """Refuse, before anything is typed, a command for a console that is not listening."""
    if not session.at_debugger():
        raise NotStopped(f"the guest is running, so the console cannot take {what}: a "
                         "command typed now is dropped, never run at the next stop")


def forget_stop(session: Session) -> None:
    """The stopped flag, the passive peek's carry and what the terminal holds, all gone."""
    session._at_debugger = False
    session._peek_carry = ""
    with contextlib.suppress(Invalid):     # a dropped-bytes reading: text the release discards
        session._read(0.0)


def reader_dead(session: Session) -> bool:
    """The terminal reader thread ended."""
    drainer = getattr(session, "_drainer", None)
    return drainer is not None and not drainer.is_alive()


def _the_socket_itself(sock: socket.socket) -> socket.socket:
    return sock


#: A TEST'S SEAM, never a caller's: what the input socket is wrapped in before the stub link takes
#: it.
INPUT_LINE: Callable[[socket.socket], Any] = _the_socket_itself


def gone_if_dead(session: Session, began: float, bound_s: float, what: str) -> None:
    """Refuse a wait whose emulator has gone, at once."""
    if not session.alive():
        raise Invalid("session_broken",
            f"the emulator is GONE, {round(time.monotonic() - began, 1)}s into a "
            f"{round(bound_s, 1)}s wait for {what}. Nothing will arrive, so a longer bound "
            f"would not help: this needs a new session, not a bigger number")


def check_segment(seg: int) -> None:
    """A real-mode segment, held to sixteen bits."""
    if not 0 <= seg <= 0xFFFF:
        raise Invalid("bad_argument", f"a segment is 0x0000 to 0xFFFF; got {seg}")


# THE SESSION'S SEAMS, each its own module of the methods' bodies, which `Session` delegates to.
import dosbox_frames as frames  # noqa: E402
import dosbox_log_reader as log_reader  # noqa: E402
import dosbox_saved_states as saved_states  # noqa: E402
import dosbox_symbol_file as symbol_file  # noqa: E402

#: How long `start` waits for the debugger's prompt, the `-version` probe's time included.
READY_TIMEOUT_S = 30.0


class Session(dprocess.Process):
    """A DOSBox-X process that stays put between questions."""

    def __init__(self, launch: dlaunch.Launch) -> None:
        dlaunch.validate(launch)
        self.launch = launch
        self.conf_digest = dlaunch.digest(launch.conf)
        self.altered = False
        # THE STUB'S PROTOCOL once the guest announced it (`dosbox_inputs.require_stub`).
        self.stub_protocol = ""
        self.vars_held = 0          # the names the debugger's list held at the last read-back
        self.started_at = time.monotonic()
        self._screen = ""
        self._at_debugger = False   # set by the prompt, cleared by a run key
        self.stop_count = 0         # how many times the flag went False -> True: each is a
        # stop the server may not have observed through a tool
        self.paging: bool | None = None   # the last stop survey's PAGE/NOPG, None unread
        self.survey_text = ""                 # the last stop survey's screen, its code pane
        self.pane_clock_ms: float | None = None   # `pfi=` of the last stop or placing survey
        self.pane_cycles: int | None = None       # `cc=` of the same survey
        self._peek_carry = ""       # the tail of the last passive peek, for a split prompt
        self._pending = ""      # an escape or character split across two reads
        self._raw_tail = ""     # the last raw terminal bytes read, escapes kept (`REPLY_END`)
        self._raw_reads = 0     # how many reads brought raw bytes, escapes alone included

        self._avi_facts: dict[tuple[str, int, int], dict[str, object]] = {}
        self.state_sent = False   # whether the last state command went down the channel
        self.machine_replaced = False   # whether the last state load replaced the machine
        self.state_answered = False   # whether the emulator answered it ok
        # The presence of this session (`dosbox_presence`), set by `start`.
        self.presence = presence.Shown()
        # THE PROCESS COMES UP LAST, its own fields first.
        dprocess.Process.__init__(self)
        self._spawn(launch)


    def stub_replaced(self) -> None:
        """The guest's memory was replaced (a loaded state), the stub's last sequence with it."""
        if self._link is not None:
            self._link.unprove()

    def _linked(self, sock: socket.socket) -> stub_link.Link:
        return stub_link.Link(INPUT_LINE(sock), self.at_debugger)

    # ------------------------------------------------------------------ reading

    def _read(self, seconds: float) -> str:
        """Whatever the terminal offered within `seconds`, with the escapes stripped."""
        end = time.monotonic() + seconds
        dropped_before = self.dropped
        out = b""
        while time.monotonic() < end:
            out += self._take()
            if self._eof.is_set():
                break
            time.sleep(0.02)
        out += self._take()     # whatever landed during the final slice
        lost = self.dropped - dropped_before
        if lost:
            # The held escape head belongs to a stream that no longer exists.
            self._pending = ""
            raise Invalid("unexpected_answer",
                f"the terminal buffer overflowed and {lost} bytes were discarded "
                f"during this read, so what came back has a hole in it and is not a "
                f"reading. The buffer is drained now: ask again")
        raw = self._pending + out.decode("utf-8", errors="replace")
        held = dcons.PARTIAL_TAIL.search(raw)
        if held and len(raw) - held.start() <= PENDING_MAX:
            self._pending = raw[held.start():]
            raw = raw[:held.start()]
        else:
            # No head, or one that has grown past PENDING_MAX and is not an escape this debugger is
            # going to finish.
            self._pending = ""
        if raw:
            self._raw_tail = (self._raw_tail + raw)[-RAW_TAIL_KEEP:]
            self._raw_reads += 1
        text = dcons.ANSI.sub("", raw)
        if text:
            self._screen = (self._screen + text)[-SCREEN_KEEP:]
        return text

    def _mark_stopped(self) -> None:
        """The machine is at the debugger."""
        if not self._at_debugger:
            self.stop_count += 1
        self._at_debugger = True

    @property
    def parked(self) -> bool:
        """Whether the machine was parked at the debugger at the last terminal read."""
        return self._at_debugger

    def at_debugger(self) -> bool:
        """Whether the machine is parked at the debugger, answered WITHOUT a console round trip."""
        if not self._at_debugger:
            try:
                seen = self._peek_carry + self._read(0.0)
                if dcons.PROMPT in seen:
                    self._mark_stopped()
                self._peek_carry = seen[-dcons.STOP_CARRY:]   # a prompt split across two peeks
            except Invalid:
                pass          # a dropped-bytes reading; the flag stands as it was
        return self._at_debugger

    def console_tail(self, chars: int) -> str:
        """The last `chars` of what the emulator's console printed (the debugger's terminal,
        escapes stripped)."""
        rest = self._pending + self._take().decode("utf-8", errors="replace")
        self._pending = ""
        if rest:
            self._screen = (self._screen + dcons.ANSI.sub("", rest))[-SCREEN_KEEP:]
        return self._screen[-chars:]

    def wait_ready(self, timeout: float = READY_TIMEOUT_S,
                   progress: Progress = no_progress) -> float:
        """Seconds until the debugger prompt appears."""
        t0 = time.monotonic()
        seen = ""
        next_tick = t0 + PROGRESS_EVERY_S
        while time.monotonic() - t0 < timeout:
            cancel.check()
            seen += self._read(0.2)
            if dcons.PROMPT in self._screen:
                self._mark_stopped()    # born stopped: the prompt answered
                return round(time.monotonic() - t0, 3)
            now = time.monotonic()
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - t0, None, f"start: waiting for the debugger prompt, "
                                         f"{now - t0:.0f}s of {timeout:g}s")
            rc = self.proc.poll()
            if rc is not None:
                raise Invalid("session_broken",
                    f"the emulator exited with code {rc} before the debugger came "
                    f"up. That is not a slow start: the last thing it said was "
                    f"{seen.strip()[-400:]!r}")
            time.sleep(0.05)
        # IT NAMES WHAT WAS SEEN AND NOT A CAUSE.
        raise Invalid("session_broken",
            f"the debugger prompt did not appear within {timeout}s and the emulator "
            f"is still running (terminal bytes discarded so far: {self.dropped}). "
            f"A build with no debugger looks like this, and so does a prompt that "
            f"arrived and was lost. The last thing seen was {seen.strip()[-400:]!r}")

    # ------------------------------------------------------------------ driving

    def _release(self, data: bytes) -> None:
        """What a RUN KEY means for this session's own state, decided ONCE for `resume`, `step` and
        `run_to`."""
        if data not in RELEASE_KEYS and LOG_COMMAND.fullmatch(data) is None:
            return
        forget_stop(self)

    def _write(self, data: bytes) -> None:
        """Write it ALL."""
        self._release(data)
        try:
            while data:
                data = data[os.write(self._master, data):]
        except OSError as e:
            # A DEAD EMULATOR CLOSES ITS END OF THE PTY.
            if not self.alive():
                raise Invalid("session_broken",
                    f"the emulator is GONE (exit code {self.proc.poll()}): the "
                              f"terminal refused the write ({e.strerror}). Nothing more "
                              f"can be asked of this session; `close` it and `start` "
                              f"again") from None
            raise

    def command(self, text: str, settle: float = SETTLE_S,
                timeout: float = REPLY_TIMEOUT_S) -> str:
        """Send one debugger command and return what the screen produced FOR IT."""
        return self._keys(text.encode() + b"\r", settle, timeout)

    def _keys(self, data: bytes, settle: float = SETTLE_S,
              timeout: float = REPLY_TIMEOUT_S) -> str:
        """`data` typed as it is, and what the screen produced for it."""
        # WHAT THE TERMINAL STILL HOLDS IS NOT THIS COMMAND'S REPLY.
        with contextlib.suppress(Invalid):        # a dropped-bytes reading: nothing to keep
            stale = self._peek_carry + self._read(0.0)
            if dcons.PROMPT in stale:
                self._mark_stopped()
            self._peek_carry = stale[-dcons.STOP_CARRY:]
        self._write(data)
        reply = self._collect(settle, timeout, early=True)
        # THE PROMPT IS COUNTED WHEREVER IT IS READ.
        seen = self._peek_carry + reply
        if dcons.PROMPT in seen:
            self._mark_stopped()
        self._peek_carry = seen[-dcons.STOP_CARRY:]
        return reply

    def listing(self, command: str) -> str:
        """A debugger LISTING (`DOS MCBS`, `GDT`, `PAGING`...), whole, read off the session's
        logfile."""
        logfile = self.launch.logfile
        if logfile is None:
            raise Invalid("no_channel",
                f"`{command}` is read off the session's logfile and this session was "
                f"started without one, which the screen cannot stand in for: it loses "
                f"the listing's columns. `start` with `logfile`")
        begin = logfile.stat().st_size if logfile.exists() else 0
        reply = self.command(command)
        if dcons.at_pager(reply):
            reply = self._keys(dcons.PAGER_EXIT)
        held = dcons.input_line(reply)
        if held is None:
            raise Invalid("unexpected_answer",
                f"no prompt came back for `{command}`, so what the logfile holds is not "
                f"known to be the whole listing, and the console may still be paging it: "
                f"`close` this session. What the screen showed: {reply.strip()[-200:]!r}")
        if held:
            raise Invalid("unexpected_answer",
                f"after `{command}` the debugger's input line holds {held!r}: the next "
                f"command would be appended to it rather than run. `close` this session")
        try:
            with logfile.open("rb") as f:
                size = f.seek(0, os.SEEK_END)
                if size < begin:
                    raise Invalid("session_broken",
                        f"{logfile} shrank from {begin} to {size} bytes while `{command}` "
                        f"ran: it was truncated or replaced, so what it holds now is not "
                        f"this listing")
                f.seek(begin)
                return f.read().decode("latin-1")
        except FileNotFoundError:
            raise Invalid("no_channel", f"no log at {logfile}: the emulator has not "
                          f"written it, so `{command}` left nothing to read") from None

    def end_pager(self) -> str:
        """`PAGER_EXIT` at a pager, and what the screen produced for it."""
        return self._keys(dcons.PAGER_EXIT)

    def clear_line(self) -> str:
        """`CLEAR_LINE_KEY` at the prompt, and what the screen produced for it."""
        return self._keys(dcons.CLEAR_LINE_KEY)

    def _collect(self, settle: float, timeout: float, early: bool = False) -> str:
        """What arrives until it has been quiet for `settle`, once something has arrived."""
        got = ""
        deadline = time.monotonic() + timeout
        last_s, reads = 0.0, self._raw_reads
        while time.monotonic() < deadline:
            chunk = self._read(COLLECT_SLICE_S)
            if chunk or self._raw_reads != reads:
                reads, last_s = self._raw_reads, time.monotonic()
            if chunk:
                got += chunk
            elif got:                      # only ONCE something has arrived
                ended = early and dcons.REPLY_END.search(self._raw_tail) is not None
                if time.monotonic() - last_s >= (min(settle, REPLY_GRACE_S) if ended
                                                 else settle):
                    break
        return got

    def _survey(self) -> tuple[str, dict[str, str]]:
        """ONE repaint, and everything that can be read off it."""
        text = self.command(NUDGE)
        found = dcons.parse_registers(text)
        if not found:
            # THE MESSAGE NAMES WHAT WAS SEEN, not a cause.
            if reader_dead(self):
                raise NotStopped(
                    f"no register pane came back from `{NUDGE}`, and the terminal reader "
                    f"has DIED ({self.drain_ended or 'no reason recorded'}): nothing can "
                    f"come back from this session whatever the machine does. `close` it "
                    f"and `start` again")
            raise NotStopped(
                f"no register pane came back from `{NUDGE}` (emulator "
                f"{'running' if self.alive() else 'GONE'}). A register read is only "
                f"a reading when the machine is stopped at the debugger")
        return text, found

    def registers(self) -> dict[str, str]:
        """The register pane, as a mapping."""
        return self._survey()[1]

    def where(self) -> dict[str, str]:
        """WHERE THE MACHINE IS STOPPED."""
        at = dcons.where_from(self._survey()[0])
        self._mark_stopped()       # a position was read: the prompt answered
        return at

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        """Everything a STOP REPLY reads, off ONE repaint."""
        text, regs = self._survey()
        where = dcons.where_from(text)
        # THE PAGING MARK AND THE CLOCK ARE THIS REPAINT'S, like the position: set here, so a later
        # survey (the list read below.
        self.paging = dcons.parse_paging(text)
        self.survey_text = text
        self.pane_clock_ms = dcons.parse_pane_clock(text)
        self.pane_cycles = dcons.parse_pane_cycles(text)
        if dcons.BPLIST_HEADER not in text:
            # The pane came back whole and the listing did not (a cut repaint): one fresh read of
            # the list.
            return where, regs, self.breakpoints()
        return where, regs, dcons.parse_breakpoints(text)

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        """Both readings off ONE survey, so a stop reply pays a single console round trip for where
        AND registers instead of two of the same screen (a console round trip costs most of a
        second)."""
        text, regs = self._survey()
        self.pane_clock_ms = dcons.parse_pane_clock(text)
        self.pane_cycles = dcons.parse_pane_cycles(text)
        return dcons.where_from(text), regs

    def breakpoints(self) -> list[dict[str, str]]:
        """What the debugger currently holds, READ OFF IT rather than remembered."""
        text, _ = self._survey()
        if dcons.BPLIST_HEADER not in text:
            raise Invalid("unexpected_answer",
                f"`{NUDGE}` repainted a register pane but printed no {dcons.BPLIST_HEADER!r}. "
                f"An empty list and a listing that never happened both come back as no "
                f"rows, and only one of them means nothing is armed")
        return dcons.parse_breakpoints(text)

    def read_memory(self, seg: int, off: int, mode: str | None = None) -> list[str]:
        """The data-view rows at an address, and INVALID unless THAT address is among them."""
        check_segment(seg)
        # THE OFFSET'S WIDTH IS THE CPU MODE'S (`check_offset`): a flat 0xFFFF would refuse every
        # 32-bit protected-mode address.
        dcons.check_offset(off, mode if mode is not None else self.where()["mode"])
        rows = dcons.parse_data_view(self.command(f"D {seg:04X}:{off:04X}"))
        if not rows:
            # NO CAUSE IS NAMED, per this class's own rule.
            raise Invalid("unexpected_answer",
                f"no data view came back for D {seg:04X}:{off:04X} (emulator "
                f"{'running' if self.alive() else 'GONE'}). Several things produce "
                f"this and none of them is picked here: the machine is running, the "
                f"pane did not repaint, the emulator is gone")
        # TWO REPAINTS OF ONE VIEW ARE ONE VIEW.
        newest: dict[str, str] = {}
        for r in rows:
            addr = r.split()[0]
            newest.pop(addr, None)
            newest[addr] = r
        rows = list(newest.values())
        want = f"{seg:04X}:{off:08X}"
        if not any(r.startswith(want) for r in rows):
            # THE ROWS ARE IN PAINT ORDER, which is not address order, so this says what it HAS
            # rather than describing where they "start".
            raise Invalid("unexpected_answer",
                f"the screen came back with {len(rows)} data row(s) and none of them "
                f"is {want}, the address that was asked for. What came back: "
                f"{[r.split()[0] for r in rows[:4]]}. That is a reading of somewhere "
                f"else")
        return rows

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """Exactly `n` bytes at seg:off, for a watch to render as a value."""
        if n <= 0:
            raise Invalid("bad_argument", f"a read needs a positive length; got {n}")
        if n > dcons.DATA_VIEW_BYTES:
            raise Invalid("bad_argument",
                f"read_bytes reads up to {dcons.DATA_VIEW_BYTES} bytes (the data view's reach); "
                          f"{n} is a region -- use memdump")
        by_off: dict[int, int] = {}
        for r in self.read_memory(seg, off, mode=mode):
            m = dcons.DATA_ROW.search(r)
            if m is None:
                continue
            base = int(m.group(2), 16)
            for i, pair in enumerate(m.group(3).split()):
                by_off[base + i] = int(pair, 16)
        try:
            return bytes(by_off[off + i] for i in range(n))
        except KeyError:
            raise Invalid("unexpected_answer",
                f"the data view for {dcons.canonical_seg_off(seg, off)} did not cover all {n} "
                f"bytes asked for; it painted {len(by_off)} from the start address") from None

    # How many bytes one `SM` carries: the debugger takes a list of values after the address on one
    # input line.
    WRITE_CHUNK = 8

    # THE ROM OF A REAL-MODE MACHINE, by linear address: the option ROMs and the BIOS.
    ROM_LINEAR = (0xC0000, 0xFFFFF)

    def write_memory(self, seg: int, off: int, data: bytes,
                     mode: str | None = None) -> dict[str, object]:
        """Write `data` at seg:off through the debugger's `SM`, READ IT BACK, and mark the session
        altered for good."""
        if not data:
            raise Invalid("bad_argument", "a write needs at least one byte")
        check_segment(seg)
        mode = mode if mode is not None else self.where()["mode"]
        top = dcons.check_offset(off, mode)
        # THE LAST BYTE IS BOUNDED TOO.
        if off + len(data) - 1 > top:
            raise Invalid("bad_argument",
                f"the write's last byte would be at 0x{off + len(data) - 1:X}, past "
                          f"the 0x{top:X} an offset can reach in this CPU mode: "
                          f"{len(data)} bytes from 0x{off:X} do not fit in the segment")
        if not mode.startswith("Pr"):
            lo, hi = seg * 16 + off, seg * 16 + off + len(data) - 1
            if hi >= self.ROM_LINEAR[0] and lo <= self.ROM_LINEAR[1]:
                raise Invalid("bad_argument",
                    f"{dcons.canonical_seg_off(seg, off)} is in the ROM range (linear 0x{lo:X}, "
                    f"0x{self.ROM_LINEAR[0]:X}-0x{self.ROM_LINEAR[1]:X}): measured on this "
                    f"build, the debugger's `SM` into it does not write and does not "
                    f"refuse, it ENDS the emulator. Nothing was sent")
        self.altered = True
        for i in range(0, len(data), self.WRITE_CHUNK):
            chunk = data[i:i + self.WRITE_CHUNK]
            # EVERY VALUE LEADS WITH A ZERO.
            values = " ".join(f"0{b:02X}" for b in chunk)
            self.command(f"SM {seg:04X}:{off + i:04X} {values}")
        back = self.read_bytes(seg, off, len(data), mode=mode)
        return {"bytes_written": len(data), "readback": back.hex(), "verified": back == data}

    def set_register(self, name: str, value: int) -> dict[str, object]:
        """Write a register, READ IT BACK, and mark the session altered for good."""
        key = check_register_name(name)
        check_register_value(key, value)
        self.altered = True
        self.command(f"SR {key} {value:x}")
        regs = self.registers()
        pane, bits = READBACK[key]
        got = regs.get(pane)
        if got is None:
            raise Invalid("readback_refused",
                f"the pane came back without {pane} after `SR`, so the "
                          f"write could not be read back. The session is marked altered "
                          f"anyway, because the attempt reached the machine")
        held = int(got, 16) & ((1 << bits) - 1)
        return {"register": key, "regs": regs, "readback": judges.hex_at_width(held, bits),
                "verified": held == value}

    def breakpoint_interrupt(self, number: int, ah: int | None = None) -> str:
        """Break on an interrupt."""
        check_interrupt(number, ah)
        arg = f"BPINT {number:02X}" + (f" {ah:02X}" if ah is not None else "")
        out = self.command(arg)
        # READ THE LIST BACK, exactly as `run_to` and `watch` do, and for the reason this module
        # states everywhere else.
        armed = dcons.interrupt_row(number, ah)
        if not any(row["entry"] == armed for row in self.breakpoints()):
            raise Invalid("readback_refused",
                f"`{arg}` is not in the debugger's breakpoint list, so it "
                          f"was not armed. Resuming now would run with nothing to "
                          f"stop the machine. What it showed: {out.strip()[-300:]!r}")
        return out

    def retrace(self, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """Run to the next vertical retrace."""
        self._write(RETRACE_COMMAND)
        return Session.await_stop(self, began, deadline, "the next retrace", progress,
                                   label="run_for: the next retrace")

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """`word` of the `LOG` family with its `count` in hex (`LOGC 41`), typed as the release it
        is, and the stop it ends at heard by the prompt until `deadline`."""
        if word not in LOG_WORDS:
            raise ValueError(f"{word!r} is not a word of the LOG family")
        command = f"{word} {count:X}"
        self._write(command.encode() + b"\r")
        return Session.await_stop(self, began, deadline, f"`{command}`", progress,
                                   label=f"trace: `{command}`")

    def resume(self) -> dict[str, object]:
        """Let the machine run, and SAY whether it actually left the debugger."""
        self._write(RUN_KEY)
        text = self._collect(settle=1.0, timeout=8.0)
        halted = dcons.PROMPT in text
        if halted:
            self._mark_stopped()
        stopped_at: dict[str, str] | None = None
        if halted:
            try:
                stopped_at = self.where()
            except Invalid:
                # NOT re-raised.
                stopped_at = None
        return {"screen": text, "halted": halted, "stopped_at": stopped_at}

    def resume_after_command(self) -> dict[str, object]:
        """`resume` after a command that ran at a stop the server made for it (a saved state's),
        with the halt it reports confirmed."""
        before = self.stop_count
        out = self.resume()
        if out["halted"] and out["stopped_at"] is None:
            forget_stop(self)
            self.stop_count = before
            with contextlib.suppress(Invalid):
                out["stopped_at"] = self.where()
            out["halted"] = self._at_debugger
        return out

    # --------------------------------------------------------------- the debugging

    def step(self, count: int = 1, mode: str = "into") -> dict[str, object]:
        """Advance the machine one instruction at a time, VERIFYING each one landed."""
        check_step(mode, count)
        # THE REFUSAL IS THIS TOOL'S, not the position reader's.
        try:
            before = self.where()
        except NotStopped:
            # A dead emulator is not a running one.
            if not self.alive() or reader_dead(self):
                raise
            raise NotStopped(
                "a step needs the machine STOPPED at the debugger, and it is running: a "
                "step is a KEYSTROKE (F10/F11) to the debugger's window, and a keystroke to "
                "a running guest is swallowed with no error anywhere, so stepping now would "
                "report a machine it never touched. No step key was sent. Bring it back with "
                "`stop` or a breakpoint armed before it ran (the "
                "position could not be read, which is how a running machine is known here)"
            ) from None
        after, completed, running = before, 0, False
        # COUNTED PER STEP, because comparing only the ENDPOINTS answers a different question than
        # the one `moved` is asked.
        stalled, sent = 0, 0
        for _ in range(count):
            position_before = after
            # `_write` AND `_collect` ARE INSIDE THE TRY.
            try:
                sent += 1
                self._write(STEP_KEYS[mode])
                self._collect(settle=0.4, timeout=6.0)
                after = self.where()
            except NotStopped:
                # THE MACHINE IS GONE OR IT IS RUNNING, AND THOSE ARE NOT THE SAME ANSWER.
                if not self.alive():
                    raise
                running = True
                break
            except Invalid as exc:
                # EVERY OTHER `Invalid` FROM `where()` MUST REPORT THE STEPS ALREADY TAKEN.
                if isinstance(exc, NotStopped):
                    raise
                # IT REPORTS THE KEYSTROKES SENT, NOT THE ONES READ BACK.
                raise Invalid(exc.code,
                    f"{exc} -- and {sent} `{mode}` keystroke(s) of {count} had ALREADY "
                    f"gone to the machine when this happened, of which {completed} were "
                    f"CONFIRMED landed. They are irreversible: this debugger has no "
                    f"un-step, so the machine is at least {completed} step(s) past "
                    f"{before['cs']}:{before['eip']} and this call could not read where "
                    f"that is") from None
            if after == position_before:
                stalled += 1
            completed += 1
        return {"mode": mode, "asked": count, "completed": completed,
                "running": running, "moved": stalled < completed,
                "stalled": stalled,
                "before": before, "after": after}

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: Progress = no_progress) -> dict[str, object]:
        """Run until the machine reaches an address, and say where it really stopped."""
        # THE ARGUMENT CHECKS THAT NEED NOTHING FROM THE MACHINE GO FIRST.
        check_segment(seg)
        vocab.check_wait(seconds)
        stopped = self.where()      # refuses a running machine BEFORE arming anything
        # THE OFFSET'S WIDTH IS THE CPU MODE'S.
        top = dcons.check_offset(off, stopped["mode"])
        target = f"{seg:04X}:{off:04X}"
        ctl = None
        if control is not None:
            cseg, coff = control
            if not 0 <= cseg <= 0xFFFF or not 0 <= coff <= top:
                raise Invalid("bad_argument", f"the control {cseg:04X}:{coff:X} is outside what "
                              f"{stopped['mode']} mode can address")
            ctl = f"{cseg:04X}:{coff:04X}"
            # THE SAME PLACE, NOT THE SAME SPELLING: in real mode `1234:0010` and `1235:0000` are
            # one byte.
            same = (ctl == target if str(stopped["mode"]).startswith("Pr")
                    else cseg * 16 + coff == seg * 16 + off)
            if same:
                raise Invalid("bad_argument",
                    f"the control {ctl} is the same address as the target {target}: "
                              "a control proves the target COULD have fired, and the target "
                              "cannot prove that about itself")
        # ARMING IS A WRITE TO THE MACHINE, so the session is marked BEFORE the command goes out
        # and stays marked whatever happens next.
        self.altered = True
        self.command(f"BP {target}")
        if ctl is not None:
            self.command(f"BP {ctl}")
        armed = self.breakpoints()
        for spelled in [target] + ([ctl] if ctl is not None else []):
            if not any(f"BP {spelled}" == b["entry"] for b in armed):
                raise Invalid("readback_refused",
                    f"the debugger does not list a breakpoint at {spelled} after being "
                    f"told to set one. What it holds: {[b['entry'] for b in armed]}. "
                    f"Resuming now would run the machine with nothing to stop it, and the "
                    f"reply would blame the address rather than the arming")
        # THE TERMINAL IS DRAINED BEFORE THE MACHINE IS RELEASED -- by `_write` itself, for every
        # run key (`_release`).
        began = time.monotonic()
        deadline = began + seconds
        control_hits = 0
        at: dict[str, str] | None = None
        expired, interrupted = True, False
        release = True
        # THE CONTROL LOOP: released, waited for, read; a stop AT the control is counted and the
        # machine let go again.
        try:
            while True:
                if release:
                    self._write(RUN_KEY)
                release = True
                expired, _saw_at = Session.await_stop(self, began, deadline, target, progress)
                if expired:
                    break
                try:
                    at = self.where()
                except NotStopped:
                    if not self.alive():
                        raise
                    # THE ANNOUNCED STOP THAT IS NOT ONE: the machine still runs, so the wait
                    # listens on for the rest of its bound, sending nothing.
                    release = False
                    continue
                except Invalid as exc:
                    # THE OTHER TWO WAYS `where()` REFUSES, caught with something attached.
                    raise _still_armed(exc, target, began, ctl) from None
                # THE TARGET IS ASKED FIRST.
                if control is None or Session._stopped_at(at, seg, off):
                    break
                if not Session._stopped_at(at, control[0], control[1]):
                    break
                control_hits += 1
                if time.monotonic() >= deadline:
                    # AT REST ON THE CONTROL WITH NO BOUND LEFT: reported as a stop elsewhere, and
                    # the bound DID run out, whatever the last wait saw.
                    expired = True
                    break
                at = None
            read_after_bound = at is None
            if at is None:
                # THE BOUND RAN OUT: the position is read AFTER the loop, because the machine can
                # be found at rest however the loop ended.
                try:
                    try:
                        at = self.where()
                    except NotStopped:
                        if not self.alive():
                            raise
                        interrupted = Session.stop_at_bound(self)
                        at = self.where()
                except Invalid as exc:
                    raise _still_armed(exc, target, began, ctl) from None
        except BaseException as e:
            if cancel.is_cancellation(e):
                Session._abandon_run(self, [target] + ([ctl] if ctl is not None else []))
            raise
        # ARRIVAL IS THE SAME PLACE, NOT THE SAME SPELLING.
        arrived = Session._stopped_at(at, seg, off)
        on_control = control is not None and Session._stopped_at(at, control[0], control[1])
        if on_control and read_after_bound and not interrupted:
            control_hits += 1          # found resting on the control after the bound: it fired
        # THE TARGET IS OURS ON EVERY STOPPED OUTCOME, like the control: a `BP` is persistent.
        removed, cleanup = Session._remove_own_breakpoint(self, target)
        control_removed = False
        if ctl is not None:
            # THE CONTROL IS OURS ON EVERY STOPPED OUTCOME: nobody asked to keep it.
            control_removed, control_cleanup = Session._remove_own_breakpoint(self, ctl)
            cleanup += control_cleanup
        # THE VERDICT IS WHAT ENDED THE RUN, read off the stop and not off the wait.
        if arrived:
            verdict, why = contract.TARGET, ""
        elif interrupted or (expired and on_control):
            verdict = contract.TIMEOUT
            why = (f"the {seconds:g} s bound ran out and the run was interrupted at "
                   f"{at['cs']}:{at['eip']}" if interrupted else
                   f"it came to rest ON the control {ctl} (its hit number {control_hits}) when "
                   f"the bound ran out")
        else:
            verdict = contract.OTHER_STOP
            why = f"it stopped at {at['cs']}:{at['eip']}: something else got there first"
        rom = (f" If {target} is in ROM (a BIOS or option-ROM segment such as F000), that is "
               f"why: a code breakpoint in ROM is acknowledged, appears in BPLIST, and never "
               f"fires" if interrupted else "")
        return {"verdict": verdict, "target": target,
                "stopped_at": at, "waited_s": round(time.monotonic() - began, 3),
                "breakpoint_removed": removed,
                "control": Session._control_block(ctl, control_hits,
                                                  removed=control_removed),
                "note": cleanup.strip() if arrived else
                        f"{why}, and not at {target}{rom}." + (
                            cleanup if not removed else
                            f" The breakpoint at {target} was removed.{cleanup}")}

    def await_stop(self, began: float, deadline: float, target: str,
                    progress: Progress = no_progress, label: str = "",
                    look_once: bool = False) -> tuple[bool, float]:
        """Listen for the debugger to announce a stop, until `deadline`."""
        # THE CARRY STARTS WHERE THE LAST PASSIVE PEEK LEFT IT (`at_debugger`).
        carry = self._peek_carry
        next_tick = began + PROGRESS_EVERY_S
        # `look_once`: THE TERMINAL IS READ AT LEAST ONCE, a bound of 0 included.
        looked = not look_once
        while not looked or time.monotonic() < deadline:
            now = time.monotonic()
            cancel.check()
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - began, None, f"{label or f'run_to {target}'}: running "
                                            f"{now - began:.0f}s of {deadline - began:g}s")
            # THE DEATH IS CHECKED IN THE LOOP, as `e9_wait` does.
            gone_if_dead(self, began, deadline - began, target)
            # ONLY THE FRESH TEXT IS SCANNED, PLUS A BOUNDED CARRY.
            fresh = carry + self._read(0.25 if now < deadline else 0.0)
            looked = True
            # EITHER ANNOUNCEMENT ENDS THE WAIT.
            if dcons.PROMPT in fresh or dcons.parse_registers(fresh).get("EIP"):
                if dcons.PROMPT in fresh:
                    self._mark_stopped()   # heard here, before any reader consumes it
                # THE MOMENT IS STAMPED HERE, where it happened, and not after `where()` has run (a
                # NUDGE plus a collect, up to its own timeout).
                return False, round(time.monotonic() - began, 1)
            carry = fresh[-dcons.STOP_CARRY:]
        # WHAT THE WAIT READ LAST IS THE NEXT LOOK'S START, as a peek's is.
        self._peek_carry = carry
        return True, 0.0

    @staticmethod
    def _stopped_at(at: dict[str, str], seg: int, off: int) -> bool:
        """Whether a stop position IS `seg:off`."""
        if str(at["mode"]).startswith("Pr"):
            return at["cs"] == f"{seg:04X}" and int(at["eip"], 16) == off
        return int(at["cs"], 16) * 16 + int(at["eip"], 16) == seg * 16 + off

    @staticmethod
    def _control_block(ctl: str | None, hits: int, *, removed: bool) -> dict[str, object]:
        """The `control` field of a `run_to` reply."""
        if ctl is None:
            return contract.unavailable("no control was named")
        return {"at": ctl, "hits": hits, "removed": removed}

    def _abandon_run(self, own: list[str]) -> None:
        """A RUN CANCELLED IN FLIGHT LEAVES NOTHING ARMED."""
        with cancel.shielded(), contextlib.suppress(Invalid, OSError):
            if not self.at_debugger():
                self.break_in()
            for spelled in own:
                Session._remove_own_breakpoint(self, spelled)

    def _remove_own_breakpoint(self, spelled: str) -> tuple[bool, str]:
        """Remove a breakpoint THIS call armed, on a stopped machine."""
        try:
            here = self.breakpoints()
            mine = [b for b in here if f"BP {spelled}" == b["entry"]]
            if not mine:
                return False, (f" The breakpoint at {spelled} was not in the list at "
                               f"cleanup time, so nothing was removed and something "
                               f"else took it away.")
            self.command(f"BPDEL {mine[0]['index']}")
            removed = not any(f"BP {spelled}" == b["entry"] for b in self.breakpoints())
            if not removed:
                return False, (f" `BPDEL` was sent and {spelled} is STILL in the "
                               f"debugger's list: it will stop the next `resume`.")
            return True, ""
        except Invalid as exc:
            return False, (f" The stop is sound; the cleanup could not be confirmed "
                           f"({exc}). Assume the breakpoint at {spelled} is still armed.")

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        """Break when a piece of memory CHANGES, choosing the command for the caller."""
        return Session.watch_places(self, [(segment, offset)])[0]

    def watch_places(self, places: list[tuple[int, int]]) -> list[dict[str, object]]:
        """`watch` at every one of `places`, a row each (a memory breakpoint compares one byte), in
        one reading of the mode, a command per row and ONE read of the list back."""
        # THE MACHINE IS READ FIRST: a command typed at a running guest is a refusal with a side
        # effect.
        cpu = self.where()["mode"]
        for segment, offset in places:
            check_segment(segment)
            dcons.check_offset(offset, cpu)
        # THE THREE LIST SPELLINGS ARE CAPTURED, NOT DERIVED.
        sent: list[tuple[str, str]] = []
        for segment, offset in places:
            if cpu.startswith("Pr"):
                sent.append((f"BPPM {segment:04X}:{offset:04X}",
                             f"BPPM {segment:04X}:{offset:08X}"))
            else:
                sent.append((f"BPM {segment:04X}:{offset:04X}",
                             f"BPMEM {segment:04X}:{offset:04X}"))
        # SAME AS `run_to`: arming is a write, and a watch is NEVER removed by this method.
        self.altered = True
        for command, _ in sent:
            self.command(command)
        # READ BACK, for the same reason `run_to` does.
        held = self.breakpoints()
        missing = [(command, entry) for command, entry in sent
                   if not any(b["entry"].startswith(entry) for b in held)]
        if missing:
            raise Invalid("readback_refused",
                f"the debugger does not list a watch matching "
                f"{', '.join(f'`{e}`' for _, e in missing)} after "
                f"{', '.join(f'`{c}`' for c, _ in missing)}. What it holds: "
                f"{[b['entry'] for b in held]}. A watch that was never armed and one that "
                f"never fires are the same silence")
        # `mode` IS THE MACHINE'S CPU MODE, the reading the command was chosen from.
        return [{"command": command, "mode": cpu, "armed": entry, "breakpoints": held,
                 "fires_on": "a CHANGE to the value, never a read and never a write of the "
                             "value already there"} for command, entry in sent]

    # -------------------------------------------------------- staged code breakpoints

    def arm_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        """Arm a CODE breakpoint at `seg:off` and LEAVE THE MACHINE STOPPED."""
        stopped = self.where()      # refuses a running machine BEFORE arming
        check_segment(seg)
        dcons.check_offset(off, stopped["mode"])
        target = f"{seg:04X}:{off:04X}"
        self.altered = True
        self.command(f"BP {target}")
        held = self.breakpoints()
        want = ("BP", seg, off)
        listed = next((b for b in held if dcons.bp_row_target(b["entry"]) == want), None)
        if listed is None:
            raise Invalid("readback_refused",
                f"the debugger does not list a breakpoint at {target} after being told to "
                f"set one. What it holds: {[b['entry'] for b in held]}. It was NOT armed, "
                f"so a caller releasing the machine now would run with nothing to stop it")
        return {"target": target, "entry": listed["entry"], "breakpoints": held}

    def clear_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        """Remove a code breakpoint at `seg:off`, by its own text, and READ THE LIST BACK."""
        stopped = self.where()
        check_segment(seg)
        dcons.check_offset(off, stopped["mode"])
        want = ("BP", seg, off)
        target = f"BP {seg:04X}:{off:04X}"
        mine = [b for b in self.breakpoints() if dcons.bp_row_target(b["entry"]) == want]
        if not mine:
            return {"entry": target, "removed": False, "note": "no such breakpoint to remove"}
        self.command(f"BPDEL {mine[0]['index']}")
        removed = not any(dcons.bp_row_target(b["entry"]) == want for b in self.breakpoints())
        return {"entry": mine[0]["entry"], "removed": removed}

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        """Remove an interrupt breakpoint by its own ROW TEXT, and READ THE LIST BACK."""
        check_interrupt(number, ah)
        self.where()                      # refuses a running machine before the console
        want = dcons.interrupt_row(number, ah)
        mine = [b for b in self.breakpoints() if b["entry"] == want]
        if not mine:
            return {"entry": want, "removed": False, "note": "no such breakpoint to remove"}
        self.command(f"BPDEL {mine[0]['index']}")
        removed = not any(b["entry"] == want for b in self.breakpoints())
        return {"entry": want, "removed": removed}

    # ------------------------------------------------------------------ the log

    def e9(self, pattern: str, limit: int = 40) -> tuple[list[str], int]:
        return log_reader.e9(self, pattern, limit)

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        return log_reader.log(self, pattern, limit, channel, since_mark)

    def _log_text(self) -> str:
        return log_reader._log_text(self)

    def _e9_text(self) -> str:
        return log_reader._e9_text(self)

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        return log_reader._e9_since(self, offset, channel)

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return log_reader.e9_new_since(self, offset)

    def e9_since_mark(self, mark: int) -> list[str]:
        return log_reader.e9_since_mark(self, mark)

    def e9_mark(self) -> int:
        return log_reader.e9_mark(self)

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: Progress = no_progress) -> dict[str, object]:
        return log_reader.e9_wait(self, pattern, seconds, mark, progress)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: Progress = no_progress) -> dict[str, object]:
        return log_reader.log_wait(self, pattern, seconds, channel, mark, progress)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        """Memory to a FILE, returning the path it ended up at."""
        check_segment(seg)
        check_dump_length(length)
        candidates = self._memdump_candidates()
        # Judged before the debugger writes anything, so a refusal leaves no dump behind to poison
        # the next call.
        dcollect.judge_collection(dest, self.launch.cwd, candidates, "dump")
        dcollect.refuse_leftover(candidates, "dump")
        paths.fresh_dest("dest", dest)
        # EVERY REFUSAL FROM THE COMMAND ON TAKES THIS CALL'S FILE AWAY.
        try:
            out = self.command(f"MEMDUMPBIN {seg:04X}:{off:04X} {length:X} {MEMDUMP_FILE}")
            said = [ln for ln in out.splitlines() if MEMDUMP_OK in ln or MEMDUMP_FAIL in ln]
            if not said or MEMDUMP_OK not in said[-1]:
                raise Invalid("unexpected_answer",
                    f"the debugger did not report a successful dump. What it "
                              f"showed: {out.strip()[-300:]!r}")
            source = next((c for c in candidates if c.exists()), None)
            if source is None:
                raise Invalid("unexpected_answer", f"the debugger reported success and none of "
                              f"{[str(c) for c in candidates]} exists. Those disagree, so "
                              f"this is not a reading")
            # THE SIZE IS THE ONE THING TYING THESE BYTES TO THIS REQUEST, so it is checked for
            # EQUALITY and not for being non-empty.
            got = source.stat().st_size
            if got != length:
                raise Invalid("readback_refused",
                    f"asked the debugger for {length} bytes and {source} holds "
                              f"{got}. That is not the dump that was asked for")
            return dcollect.collect(source, dest, "dump")
        except BaseException as exc:
            # A HOST ERROR TOO (the terminal broke after the debugger wrote): whatever escapes, the
            # file is this call's.
            kept: dict[Path, str] = {}
            for c in candidates:
                try:
                    c.unlink()
                except FileNotFoundError:
                    pass
                except OSError as gone:
                    # One file under both spellings, where the filesystem folds case: named once.
                    try:
                        again = any(c.samefile(k) for k in kept)
                    except OSError:
                        again = False
                    if not again:
                        kept[c] = f"{c} ({gone.strerror})"
            if isinstance(exc, Invalid) and exc.code == "host_failed":
                after = (f"That file could not be removed: {', '.join(kept.values())}, so the "
                         f"next dump is refused over it until it is moved aside" if kept else
                         "That file was removed, so the next dump is not refused over it")
                raise Invalid(exc.code, f"{exc}. {after}") from None
            raise

    def intvec(self) -> str:
        """The interrupt vector table as the debugger's `INTVEC` writes it."""
        names = [self.launch.cwd / INTVEC_FILE, self.launch.cwd / INTVEC_FILE.lower()]
        dcollect.refuse_leftover(names, "vector table")
        try:
            out = self.command(f"INTVEC {INTVEC_FILE}")
            written = next((p for p in names if p.exists()), None)
            if written is None:
                raise Invalid("unexpected_answer",
                    f"no {INTVEC_FILE} appeared in {self.launch.cwd} after `INTVEC`. What "
                    f"the debugger showed: {out.strip()[-300:]!r}")
            if INTVEC_OK not in out:
                raise Invalid("unexpected_answer",
                    f"the debugger did not report the table written, so {written} is not "
                    f"known to be whole. What it showed: {out.strip()[-300:]!r}")
            return written.read_bytes().decode("latin-1")
        finally:
            for p in names:
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()

    def _memdump_candidates(self) -> list[Path]:
        """Every place the dump could land, as observed rather than read off the help."""
        names = (MEMDUMP_NAME, MEMDUMP_NAME.upper())
        places = [self.launch.cwd]
        if self.launch.captures_dir is not None:
            places.append(self.launch.captures_dir)
        seen: list[Path] = [self.launch.cwd / MEMDUMP_FILE]
        for place in places:
            for name in names:
                path = place / name
                if path not in seen:
                    seen.append(path)
        return seen

    # ------------------------------------------------------------------ symbols

    def selector(self, reg: str) -> dict[str, int]:
        """A segment register's descriptor BASE and LIMIT, as numbers, its type, and `big`, its D/B
        bit."""
        # ASCII ONLY BEFORE THE CASE IS FOLDED: `upper()` turns `ſs` into `SS`, which the published
        # pattern refuses.
        if not (reg.isascii() and reg.upper() in SELINFO_REGS):
            vocab.one_of("base_from", reg, SELINFO_REGS,
                         ", any case taken. The debugger answers any other register with a "
                         "ZEROED descriptor rather than an error, which reads as a real "
                         "selector based at 0")
        name = reg.upper()
        out = self.command(f"SELINFO {name}")
        marker = f"{SELINFO_ECHO} {name}:"
        at = out.rfind(marker)
        if at < 0:
            raise Invalid("unexpected_answer",
                f"the debugger did not echo `{marker}` (emulator "
                f"{'running' if self.alive() else 'GONE'}). A descriptor read is only "
                f"a reading when the machine is stopped at the debugger. What it "
                f"showed: {out.strip()[-300:]!r}")
        # ANCHORED ON THE ANSWER'S OWN LINE, which begins with the register's name.
        line = out.find(f"{name}: b:", at)
        m = SELINFO_FIELDS.match(out, line + len(name) + 2) if line >= 0 else None
        if m is None:
            raise Invalid("unexpected_answer",
                f"`{marker}` came back with no complete base/type/limit on a "
                          f"`{name}:` line of its own. A descriptor read that has to "
                          f"take a field from somewhere else is not a reading. What it "
                          f"showed: {out[at:at + 300]!r}")
        base, kind, limit = (int(m.group(1), 16), int(m.group(2), 16),
                             int(m.group(3), 16))
        # AN ABSENT DESCRIPTOR IS REFUSED RATHER THAN REPORTED AS BASE 0.
        if kind == SELINFO_ABSENT:
            raise Invalid("bad_argument",
                f"{name} has no present descriptor (type:00, base 0, limit 0). Either "
                f"this machine is in REAL MODE, where there are none and a base of 0 "
                f"would place every symbol at its raw offset, or {name} holds a "
                f"selector nothing has set up. Reach the point where your program is "
                f"actually running, or pass the base explicitly")
        return {"base": base, "limit": limit, "type": kind, "big": int(m.group(8))}

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        return symbol_file.load_symbols(self, data)

    @staticmethod
    def _acked(out: str, echo: str, name: str) -> None:
        return symbol_file._acked(out, echo, name)

    # ------------------------------------------------------------------ capture

    def captures(self) -> list[dict[str, object]]:
        return frames.captures(self)

    def frame(self, at: int, dest: Path, source: Path | None = None) -> Path:
        return frames.frame(self, at, dest, source)

    # ------------------------------------------------------------------ input to the guest

    def stop_at_bound(self) -> bool:
        """A run whose bound ran out, handed back STOPPED."""
        if self.at_debugger():
            return False
        self.break_in()
        return True

    def break_in(self, seconds: float = BREAK_IN_WAIT_S) -> float:
        """Bring a RUNNING guest back to the debugger through its control channel's `BREAK`
        (`dosbox_control`), headless or windowed alike, and wait for its prompt."""
        ok, lines = self.control.request("BREAK")
        if not ok:
            raise Invalid("unexpected_answer",
                f"the debugger channel refused BREAK: {' / '.join(lines) or 'no reason given'}")
        began = time.monotonic()
        while time.monotonic() - began < seconds:
            cancel.check()
            if self.at_debugger():
                return round(time.monotonic() - began, 2)
            gone_if_dead(self, began, seconds, "the debugger's prompt")
            time.sleep(0.05)
        raise Invalid("not_settled",
            f"the debugger channel accepted BREAK and the debugger's prompt did not "
                      f"appear within {seconds} s: the guest may still be running. Asking "
                      f"`stop` again is allowed; if it fails as well, `close` then `start`")

    def _state_dir(self) -> Path:
        return saved_states._state_dir(self)

    def _state_command(self, verb: str, path: Path, seconds: float) -> dict[str, object]:
        return saved_states._state_command(self, verb, path, seconds)

    def save_state(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        return saved_states.save_state(self, name, seconds)

    def load_state(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        return saved_states.load_state(self, name, seconds)

    def snapshot(self, dest: Path | None = None, seconds: float = SNAPSHOT_WAIT_S,
                 progress: Progress = no_progress) -> dict[str, object]:
        """One still of the RUNNING screen, taken INSIDE the guest."""
        vocab.check_wait(seconds)
        folder = frames.folder(self)
        target = None if dest is None else paths.fresh_dest("dest", dest)
        if self.at_debugger():
            raise Invalid("not_running",
                "a screenshot is taken of a RUNNING machine only: the stub takes its commands "
                          "on the timer tick, which a machine parked at the debugger never "
                          "reaches. `resume`, then snapshot")
        before = set(folder.glob("*.png")) if folder.is_dir() else set()
        self.send_commands([SCREENSHOT_COMMAND])
        began = time.monotonic()
        while True:
            cancel.check()
            new = sorted((set(folder.glob("*.png")) if folder.is_dir() else set()) - before)
            if new:
                path = new[-1]
                size = path.stat().st_size
                time.sleep(0.2)
                if size and path.stat().st_size == size:     # the writer is done with it
                    break
            gone_if_dead(self, began, seconds, "the screenshot")
            if time.monotonic() - began >= seconds:
                raise Invalid("wait_expired",
                    f"no new PNG appeared under {folder} within {seconds:g} s of the command")
            time.sleep(0.1)
        if target is not None:
            path = dcollect.collect(path, target, "screenshot")
        return {"route": "guest", **judges.file_facts(path)}

    def state_list(self) -> dict[str, object]:
        return saved_states.state_list(self)

    def send_commands(self, commands: list[bytes]) -> list[str]:
        """The input route's post."""
        if self._link is None:
            raise Invalid("no_channel", "this session has no input route: its socket was "
                          "never connected")
        if not commands:
            raise Invalid("bad_argument", "nothing to send")
        return self._link.send(commands)

    # ------------------------------------------------------------------ closing

    def state(self) -> dict[str, object]:
        """Everything the server says about the session."""
        changed: bool | dict[str, Any]
        try:
            changed = (self.launch.conf.is_file()
                       and dlaunch.current_digest(self.launch.conf) != self.conf_digest)
        except OSError as e:
            changed = contract.unavailable(f"the conf could not be read: {e}")
        return {
            "pid": self.proc.pid,
            "alive": self.alive(),
            # WHETHER THE GUEST RUNS, off the session's own flag: no console round trip on every
            # reply.
            "running": self.alive() and not self._at_debugger,
            "altered": self.altered,
            "conf": str(self.launch.conf),
            "conf_digest": self.conf_digest,
            "conf_changed_on_disk": changed,
            "watched": self.launch.watched,
            "bound_s": self.launch.seconds,
            "elapsed_s": round(time.monotonic() - self.started_at, 1),
            # THE EMULATOR'S TERMINAL is what overflows -- ncurses repaints, SDL banners, and the
            # log when no `logfile` is set.
            "terminal_bytes_dropped": self.dropped,
            # WHETHER THE READER IS STILL ALIVE, which no other field answers.
            "drain_alive": self._drainer is not None and self._drainer.is_alive(),
            # WHY THE READER STOPPED, present only once it has: an empty reason is no datum.
            **({"drain_ended": self.drain_ended} if self.drain_ended else {}),
            # WHETHER THIS SESSION RECORDS, and where, so a caller need not infer it from a
            # `captures` with no `avi` row.
            "captures": (str(self.launch.captures_dir) if self.launch.captures_dir is not None
                         else "on, in the emulator's own directory")
                        if self.launch.capture_video else "off",
            # WHERE `state_write(method="save")` writes and `state_list` reads.
            "state_dir": str(self.launch.state_dir) if self.launch.state_dir is not None
                         else "the emulator's own save/ under its working directory",
        }
