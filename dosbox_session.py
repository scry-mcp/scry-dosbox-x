"""One live DOSBox-X session, held open, driven through its debugger channel.

Every question is a debugger command sent with the channel's `EXEC` and read from what it PRINTS
(`dosbox_debugger`); nothing reads the debugger's screen. Launch, logs, collection, the process
base and the log/frame/state/symbol bodies are the `dosbox_*` modules `Session` delegates to.
"""

from __future__ import annotations

import contextlib
import re
import socket
import tempfile
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
import dosbox_debugger as dbg
import dosbox_disasm as disasm
import dosbox_launch as dlaunch
import dosbox_paths as paths
import dosbox_process as dprocess
import dosbox_stub_link as stub_link

# WHERE EACH SETTABLE NAME IS READ BACK, and at what width in bits.
READBACK: dict[str, tuple[str, int]] = {
    **{n.lower(): (n, 32) for n in dcons.WIDE_NAMES},
    **{n.lower(): (n, 16) for n in dcons.SEGMENT_NAMES},
    **{n: (f"E{n.upper()}", 16) for n in dcons.LOW_HALVES},
}

#: The ways to step, as `step` takes them.
STEP_MODES = ("over", "into")
# `VRT`: run, and stop at the next vertical retrace.
RETRACE_COMMAND = "VRT"
# THE `LOG` FAMILY, one word per line shape: typed with its hex count.
LOG_WORDS = ("LOG", "LOGS", "LOGL", "LOGC")

# THE CEILING ON ONE `step` CALL, and it is a cost bound rather than a safety one.
STEP_MAX = 64
#: How long one step may take: `STEPIN` answers once its instruction ran, and a step over runs a
#: CALL, an INT, a LOOP or a REP to its next instruction.
STEP_WAIT_S = 6.0
#: How long `resume` watches for a stop the release ran straight into.
RESUME_LOOK_S = 1.0


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

# `SELINFO [segName]` prints `DS: b:00400000 type:13 parbg` and, on the next line,
# `l:0023FFFF dpl : 3 10011`, the five digits under `parbg`'s letters.
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

# How long `ffmpeg` is given to pull one frame out of a capture.
FFMPEG_SECS = 120

SCREENSHOT_COMMAND = b"S"   # the stub's opcode for the device's capture trigger (guest/inject.asm)

BREAK_IN_WAIT_S = 5.0     # from BREAK on the channel to `RUNSTATE` saying stopped
SNAPSHOT_WAIT_S = 10.0
# A STATE IS SAVED AND LOADED BY THE DEBUGGER'S OWN COMMANDS, `SAVESTATE <file>` and `LOADSTATE
# <file>` over the debugger channel.
STATE_WAIT_S = 30.0

#: The line a build without `debugger headless` gives `BREAK` when it has no terminal to draw on:
#: its debugger never stops.
DEBUGGER_UNAVAILABLE = "is not available unless you start DOSBox-X from a terminal"


class NotStopped(Invalid):
    """The machine is running, and the reading needs it stopped."""

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
            f"a step count is 1 to {STEP_MAX}; got {count}. Each step is a command and a "
            f"reading of where it landed, so the ceiling is a cost bound: past it, use `run_to`")


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


def _the_socket_itself(sock: socket.socket) -> socket.socket:
    return sock


#: A TEST'S SEAM, never a caller's: what the input socket is wrapped in before the stub link takes
#: it.
INPUT_LINE: Callable[[socket.socket], Any] = _the_socket_itself


def _entry_is(text: str) -> Callable[[str], bool]:
    """A pick for `Session.delete_rows`: the row whose entry is `text`."""
    return lambda entry: entry == text


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

#: How long `start` waits for the debugger to answer stopped, the `-version` probe's time included.
READY_TIMEOUT_S = 30.0
#: The commands that leave the stopped machine's registers as they were, so a survey taken at the
#: stop still holds after them; any other (a register written, a state loaded, an `INTT`) drops it.
READS_ONLY = frozenset({"EV", "BPLIST", "BP", "BPDEL", "BPINT", "BPM", "BPPM", "MEMDUMPBIN",
                        "SELINFO", "RUNSTATE", "INTVEC", "SM", "SV", "LV", "MEMFIND", "MEMS",
                        "CPU", "GDT", "LDT", "IDT", "PAGING", "DOS", "BIOS", "EMU",
                        "CALLBACKS", "VGA", "PRESENCE"})

#: The mnemonics a step over runs past with a breakpoint, beside every CALL and INT (`disasm.CALL`):
#: a REP repeats its string instruction and a LOOP its body, each before the next instruction.
STEP_OVER_WORDS = ("rep", "loop")


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
        # WHICH OF THE DEBUGGER'S OPTIONAL COMMANDS THIS BUILD PARSES, as `start` read them.
        self.commands = launch.debugger_commands
        self._at_debugger = False   # set by a stop seen, cleared by a release
        self.stop_count = 0         # how many times the flag went False -> True: each is a
        # stop the server may not have observed through a tool
        self.paging: bool | None = None     # the last stop survey's paging bit, None unread
        # THIS STOP'S SURVEY, kept until the machine moves or a register is written.
        self._surveyed: tuple[dict[str, str], dict[str, str], bool] | None = None
        self.clock_ms: float | None = None  # `RUNSTATE`'s emulated milliseconds, last read
        self.cycles: int | None = None      # `RUNSTATE`'s cycle count, last read

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

    # ------------------------------------------------------------------ the channel

    def has(self, command: str) -> bool:
        """Whether this build's debugger parses `command`."""
        return command in self.commands

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        """One debugger command: whether it was taken and every line it printed."""
        if command.split()[:1] and command.split()[0].upper() not in READS_ONLY:
            self._surveyed = None
        return dbg.exec_lines(self, command, seconds)

    def command(self, text: str, seconds: float | None = None) -> str:
        """One debugger command and what it printed, as one text."""
        return "\n".join(self.exec(text, seconds)[1])

    def listing(self, command: str) -> str:
        """A debugger LISTING (`DOS MCBS`, `GDT`, `PAGING`...), whole, as it was printed."""
        return self.command(command)

    def gone_if_dead(self, began: float, bound_s: float, what: str) -> None:
        gone_if_dead(self, began, bound_s, what)

    # ------------------------------------------------------------------ the run state

    def mark_stopped(self) -> None:
        """The machine is at the debugger."""
        if not self._at_debugger:
            self.stop_count += 1
            self._surveyed = None
        self._at_debugger = True

    def forget_stop(self) -> None:
        """The machine was released, or was seen running."""
        self._at_debugger = False
        self._surveyed = None

    @property
    def parked(self) -> bool:
        """Whether the machine was at the debugger when it was last seen."""
        return self._at_debugger

    def at_debugger(self) -> bool:
        """Whether the machine is parked at the debugger: known at once while it is, and asked
        of `RUNSTATE` while it runs, which is how a stop it ran into is found."""
        if self._at_debugger:
            return True
        if not self.has(dbg.RUNSTATE):
            return False
        return dbg.read_run_state(self)

    def require_stopped(self, what: str) -> None:
        """Refuse `what` unless the machine is stopped at the debugger."""
        if self.at_debugger():
            return
        if not self.has(dbg.RUNSTATE):
            raise dbg.unknown_after_release(what)
        raise NotStopped(f"the guest is running, so the debugger cannot take {what}: it needs "
                         "the machine stopped. `stop` brings it back, or a breakpoint armed "
                         "before it was released")

    def require_run_state(self, what: str) -> None:
        """Refuse, before anything acts, a tool that waits for a stop this build cannot see."""
        if not self.has(dbg.RUNSTATE):
            raise dbg.no_run_state(what)

    def wait_ready(self, timeout: float = READY_TIMEOUT_S,
                   progress: Progress = no_progress) -> float:
        """Seconds until the debugger answers that the machine stopped at its first
        instruction (`-break-start`)."""
        t0 = time.monotonic()
        next_tick = t0 + PROGRESS_EVERY_S
        while True:
            cancel.check()
            rc = self.proc.poll()
            if rc is not None:
                raise Invalid("session_broken",
                    f"the emulator exited with code {rc} before its debugger answered. That is "
                    f"not a slow start: the last thing it printed was "
                    f"{self.output_tail(400).strip()!r}")
            try:
                if self._first_stop():
                    self.mark_stopped()
                    return round(time.monotonic() - t0, 3)
            except Invalid as exc:
                if exc.code != "no_channel" or time.monotonic() - t0 >= timeout:
                    raise
            now = time.monotonic()
            if now - t0 >= timeout:
                raise Invalid("session_broken",
                    f"the debugger did not answer stopped within {timeout}s and the emulator is "
                    f"still running. The last thing it printed was "
                    f"{self.output_tail(400).strip()!r}")
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - t0, None, f"start: waiting for the debugger, "
                                         f"{now - t0:.0f}s of {timeout:g}s")
            time.sleep(0.05)

    def _first_stop(self) -> bool:
        """Whether the debugger holds the machine now. With no `RUNSTATE` a `BREAK` makes sure of
        it: the debugger answers it once it holds the machine, and says when it cannot. A build
        whose binary names `RUNSTATE` and whose debugger does not take it is read as one without."""
        if self.has(dbg.RUNSTATE):
            ok, lines = self.exec(dbg.RUNSTATE)
            if ok or dbg.NOT_RECOGNIZED not in lines:
                return dbg.take_run_state(self, ok, lines)
            self.commands = self.commands - {dbg.RUNSTATE}
        ok, lines = self.control.request("BREAK")
        said = " / ".join(lines)
        if not ok or DEBUGGER_UNAVAILABLE in said:
            raise Invalid("session_broken",
                f"the debugger cannot stop this machine: `BREAK` answered "
                f"{said or 'ERR with no reason'}")
        return True

    # ------------------------------------------------------------------ driving

    def _release(self, command: str) -> list[str]:
        """Let the machine run with `command` (`RUN`, `VRT`, the `LOG` family, `STEPIN`); a
        command the debugger refused released nothing."""
        ok, lines = self.exec(command)
        if not ok:
            raise Invalid("unexpected_answer",
                f"the debugger refused `{command}`: {' / '.join(lines) or 'no reason given'}")
        self.forget_stop()
        return lines

    def _survey(self) -> tuple[dict[str, str], dict[str, str], bool]:
        """ONE reading of the stopped machine: where, its registers, and its paging bit, read once
        per stop and kept until the machine moves."""
        self.require_stopped("a register read")
        if self._surveyed is None:
            self._surveyed = dbg.survey(self)
        where, regs, paging = self._surveyed
        return dict(where), dict(regs), paging

    def registers(self) -> dict[str, str]:
        """The registers, as a mapping."""
        return self._survey()[1]

    def where(self) -> dict[str, str]:
        """WHERE THE MACHINE IS STOPPED."""
        return self._survey()[0]

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        """Everything a STOP REPLY reads: where, registers and the breakpoints."""
        where, regs, self.paging = self._survey()
        return where, regs, self.breakpoints()

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        """Both readings off ONE survey."""
        where, regs, self.paging = self._survey()
        return where, regs

    def breakpoints(self) -> list[dict[str, str]]:
        """What the debugger currently holds, READ OFF IT rather than remembered."""
        text = self.command("BPLIST")
        if dcons.BPLIST_HEADER not in text:
            raise Invalid("unexpected_answer",
                f"`BPLIST` printed no {dcons.BPLIST_HEADER!r}: {text.strip()[-200:]!r}. An empty "
                f"list and a listing that never happened both come back as no rows, and only one "
                f"of them means nothing is armed")
        return dcons.parse_breakpoints(text)

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """Exactly `n` bytes at seg:off, through `MEMDUMPBIN`, in either CPU mode."""
        if n <= 0:
            raise Invalid("bad_argument", f"a read needs a positive length; got {n}")
        if n > dcons.READ_BYTES_MAX:
            raise Invalid("bad_argument",
                f"read_bytes reads up to {dcons.READ_BYTES_MAX} bytes; {n} is a region -- use "
                f"memdump")
        check_segment(seg)
        self.require_stopped("a memory read")
        dcons.check_offset(off, mode if mode is not None else self.where()["mode"])
        with tempfile.TemporaryDirectory(prefix="dosbox-read-") as scratch:
            return self.memdump(seg, off, n, Path(scratch) / "read.bin").read_bytes()

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
        self.require_stopped("a register write")
        self.altered = True
        out = self.command(f"SR {key} {value:x}")
        regs = self.registers()
        reg, bits = READBACK[key]
        got = regs.get(reg)
        if got is None:
            raise Invalid("readback_refused",
                f"the registers came back without {reg} after `SR` ({out.strip()!r}), so the "
                f"write could not be read back. The session is marked altered anyway, because "
                f"the attempt reached the machine")
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
                          f"stop the machine. What it printed: {out.strip()[-300:]!r}")
        return out

    def retrace(self, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """Run to the next vertical retrace."""
        self.require_run_state("a retrace")
        self._release(RETRACE_COMMAND)
        return Session.await_stop(self, began, deadline, "the next retrace", progress,
                                  label="run_for: the next retrace")

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """`word` of the `LOG` family with its `count` in hex (`LOGC 41`), sent as the release it
        is, and the stop it ends at asked of `RUNSTATE` until `deadline`."""
        if word not in LOG_WORDS:
            raise ValueError(f"{word!r} is not a word of the LOG family")
        self.require_run_state("trace")
        command = f"{word} {count:X}"
        self._release(command)
        return Session.await_stop(self, began, deadline, f"`{command}`", progress,
                                  label=f"trace: `{command}`")

    def resume(self) -> dict[str, object]:
        """Let the machine run, and SAY whether it stopped again straight away."""
        output = "\n".join(self._release("RUN"))
        if not self.has(dbg.RUNSTATE):
            return {"halted": contract.unavailable(
                        f"this build's debugger has no `{dbg.RUNSTATE}` command to say whether "
                        f"the machine stopped again ({dbg.COMMANDS_SECTION})"),
                    "stopped_at": None, "output": output}
        began = time.monotonic()
        expired, _ = Session.await_stop(self, began, began + RESUME_LOOK_S, "a stop",
                                        label="resume")
        stopped_at: dict[str, str] | None = None
        if not expired:
            with contextlib.suppress(Invalid):
                stopped_at = self.where()
        return {"halted": not expired, "stopped_at": stopped_at, "output": output}

    def resume_after_command(self) -> dict[str, object]:
        """`resume` after a command that ran at a stop the server made for it (a saved state's)."""
        return self.resume()

    # --------------------------------------------------------------- the debugging

    def step(self, count: int = 1, mode: str = "into") -> dict[str, object]:
        """Advance the machine one instruction at a time, reading where each one landed."""
        check_step(mode, count)
        if not self.has("STEPIN"):
            raise dbg.missing("STEPIN", "a step")
        if mode == "over":
            # `STEPIN` answers once its instruction ran; a step over may RUN past a CALL.
            self.require_run_state("a step over")
        # THE REFUSAL IS THIS TOOL'S, not the position reader's.
        try:
            before = self.where()
        except NotStopped:
            if not self.alive():
                raise
            raise NotStopped(
                "a step needs the machine STOPPED at the debugger, and it is running: no step "
                "was sent. Bring it back with `stop` or a breakpoint armed before it ran") from None
        after, completed, running = before, 0, False
        # COUNTED PER STEP, because comparing only the ENDPOINTS answers a different question than
        # the one `moved` is asked.
        stalled, sent = 0, 0
        for _ in range(count):
            position_before = after
            try:
                sent += 1
                landed = self._one_step(after, mode)
                if landed is None:
                    running = True
                    break
                after = landed
            except NotStopped:
                if not self.alive():
                    raise
                running = True
                break
            except Invalid as exc:
                # IT REPORTS THE STEPS SENT, NOT THE ONES READ BACK.
                raise Invalid(exc.code,
                    f"{exc} -- and {sent} `{mode}` step(s) of {count} had ALREADY gone to the "
                    f"machine when this happened, of which {completed} were CONFIRMED landed. "
                    f"They are irreversible: this debugger has no un-step, so the machine is at "
                    f"least {completed} step(s) past {before['cs']}:{before['eip']} and this "
                    f"call could not read where that is") from None
            if after == position_before:
                stalled += 1
            completed += 1
        return {"mode": mode, "asked": count, "completed": completed,
                "running": running, "moved": stalled < completed,
                "stalled": stalled,
                "before": before, "after": after}

    def _one_step(self, at: dict[str, str], mode: str) -> dict[str, str] | None:
        """One step from `at`; where it landed, or None when the machine ran on past the bound.

        Into is `STEPIN`. Over is composed: an instruction that would run on past the next one (a
        CALL, an INT, a LOOP, a REP) gets a breakpoint at the next instruction and a `RUN`, and
        any other is a step into."""
        nxt = self._step_over_target(at) if mode == "over" else None
        if nxt is None:
            self._release("STEPIN")
            self.mark_stopped()     # `STEPIN` answers once its instruction ran, stopped
            return self.where()
        target = f"{int(at['cs'], 16):04X}:{nxt:04X}"
        armed = any(dcons.bp_row_target(b["entry"]) == ("BP", int(at["cs"], 16), nxt)
                    for b in self.breakpoints())
        if not armed:
            self.command(f"BP {target}")
        began = time.monotonic()
        try:
            self._release("RUN")
            expired, _ = Session.await_stop(self, began, began + STEP_WAIT_S, target,
                                            label="step over")
            if expired:
                self.stop_at_bound()
                return None
        finally:
            if not armed and self.at_debugger():
                Session._remove_own(self, [target])
        return self.where()

    def _step_over_target(self, at: dict[str, str]) -> int | None:
        """The offset after the instruction at `at` when a step over must run past it, else None."""
        bits = 32 if at["mode"] == "Pr32" else 16
        cs, eip = int(at["cs"], 16), int(at["eip"], 16)
        n = disasm.INSN_MAX if bits == 32 else min(disasm.INSN_MAX, 0x10000 - eip)
        raw = self.read_bytes(cs, eip, n, mode=at["mode"])
        first = disasm.decode(raw, eip, bits)[:1]
        if not first:
            return None
        insn = first[0]
        runs_on = insn.flow == disasm.CALL or insn.mnemonic.startswith(STEP_OVER_WORDS)
        return eip + len(insn.data) if runs_on else None

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: Progress = no_progress) -> dict[str, object]:
        """Run until the machine reaches an address, and say where it really stopped."""
        # THE ARGUMENT CHECKS THAT NEED NOTHING FROM THE MACHINE GO FIRST.
        check_segment(seg)
        vocab.check_wait(seconds)
        self.require_run_state("run_to")
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
        began = time.monotonic()
        deadline = began + seconds
        control_hits = 0
        at: dict[str, str] | None = None
        expired, interrupted = True, False
        # THE CONTROL LOOP: released, waited for, read; a stop AT the control is counted and the
        # machine let go again.
        try:
            while True:
                self._release("RUN")
                expired, _saw_at = Session.await_stop(self, began, deadline, target, progress)
                if expired:
                    break
                try:
                    at = self.where()
                except Invalid as exc:
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
                # THE BOUND RAN OUT: the machine is stopped where it stands and read after the
                # loop, because it can be found at rest however the loop ended.
                try:
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
        # THE TARGET AND THE CONTROL ARE OURS ON EVERY STOPPED OUTCOME: a `BP` is persistent, and
        # nobody asked to keep either.
        removals = Session._remove_own(self, [target] + ([ctl] if ctl is not None else []))
        removed, cleanup = removals[0]
        control_removed = False
        if ctl is not None:
            control_removed, control_cleanup = removals[1]
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
        """Ask the debugger whether the machine stopped, until `deadline`."""
        return dbg.await_stop(self, began, deadline, target, progress, label, look_once)

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
            Session._remove_own(self, own)

    def delete_rows(self, picks: list[Callable[[str], bool]]
                    ) -> list[tuple[dict[str, str] | None, bool]]:
        """The first row each of `picks` takes, deleted: one list read, a `BPDEL` each from the
        highest index down (a delete renumbers only the rows below), one read back. For each
        pick, the row it found (None) and whether no row it takes is listed after."""
        listed = self.breakpoints()
        found = [next((b for b in listed if pick(b["entry"])), None) for pick in picks]
        rows = {b["index"]: b for b in found if b is not None}
        for index in sorted(rows, key=lambda i: int(i, 16), reverse=True):
            self.command(f"BPDEL {index}")
        after = self.breakpoints() if rows else listed
        return [(row, not any(pick(b["entry"]) for b in after))
                for row, pick in zip(found, picks, strict=True)]

    def _remove_own(self, spelled: list[str]) -> list[tuple[bool, str]]:
        """Remove the breakpoints THIS call armed, on a stopped machine; for each, whether it
        went and the sentence a reply carries when it did not."""
        try:
            gone = Session.delete_rows(self, [_entry_is(f"BP {s}") for s in spelled])
        except Invalid as exc:
            return [(False, f" The stop is sound; the cleanup could not be confirmed ({exc}). "
                            f"Assume the breakpoint at {s} is still armed.") for s in spelled]
        out: list[tuple[bool, str]] = []
        for s, (row, absent) in zip(spelled, gone, strict=True):
            if row is None:
                out.append((False, f" The breakpoint at {s} was not in the list at cleanup "
                                   f"time, so nothing was removed and something else took it "
                                   f"away."))
            elif not absent:
                out.append((False, f" `BPDEL` was sent and {s} is STILL in the debugger's "
                                   f"list: it will stop the next `resume`."))
            else:
                out.append((True, ""))
        return out

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        """Break when a piece of memory CHANGES, choosing the command for the caller."""
        return Session.watch_places(self, [(segment, offset)])[0]

    def watch_places(self, places: list[tuple[int, int]]) -> list[dict[str, object]]:
        """`watch` at every one of `places`, a row each (a memory breakpoint compares one byte), in
        one reading of the mode, a command per row and ONE read of the list back."""
        # THE MACHINE IS READ FIRST: a command sent to a running guest is a refusal with a side
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
        [(row, removed)] = self.delete_rows([lambda e: dcons.bp_row_target(e) == want])
        if row is None:
            return {"entry": f"BP {seg:04X}:{off:04X}", "removed": False,
                    "note": "no such breakpoint to remove"}
        return {"entry": row["entry"], "removed": removed}

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        """Remove an interrupt breakpoint by its own ROW TEXT, and READ THE LIST BACK."""
        check_interrupt(number, ah)
        self.where()                      # refuses a running machine before the command
        want = dcons.interrupt_row(number, ah)
        [(row, removed)] = self.delete_rows([lambda e: e == want])
        if row is None:
            return {"entry": want, "removed": False, "note": "no such breakpoint to remove"}
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
                              f"printed: {out.strip()[-300:]!r}")
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
            # A HOST ERROR TOO: whatever escapes, the file is this call's.
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
                    f"the debugger printed: {out.strip()[-300:]!r}")
            if INTVEC_OK not in out:
                raise Invalid("unexpected_answer",
                    f"the debugger did not report the table written, so {written} is not "
                    f"known to be whole. What it printed: {out.strip()[-300:]!r}")
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
                f"{'running' if self.alive() else 'GONE'}). What it printed: "
                f"{out.strip()[-300:]!r}")
        # ANCHORED ON THE ANSWER'S OWN LINE, which begins with the register's name.
        line = out.find(f"{name}: b:", at)
        m = SELINFO_FIELDS.match(out, line + len(name) + 2) if line >= 0 else None
        if m is None:
            raise Invalid("unexpected_answer",
                f"`{marker}` came back with no complete base/type/limit on a "
                          f"`{name}:` line of its own. A descriptor read that has to "
                          f"take a field from somewhere else is not a reading. What it "
                          f"printed: {out[at:at + 300]!r}")
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
        """A run whose bound ran out, handed back STOPPED; whether this call had to stop it."""
        if self.at_debugger():
            return False
        self.break_in()
        return True

    def break_in(self, seconds: float = BREAK_IN_WAIT_S) -> float:
        """Bring a RUNNING guest back to the debugger through its channel's `BREAK`, and wait
        for `RUNSTATE` to say so; with no `RUNSTATE`, `BREAK`'s own answer says it."""
        ok, lines = self.control.request("BREAK")
        said = " / ".join(lines)
        if not ok or DEBUGGER_UNAVAILABLE in said:
            raise Invalid("unexpected_answer",
                f"the debugger channel refused BREAK: {said or 'no reason given'}")
        began = time.monotonic()
        if not self.has(dbg.RUNSTATE):
            self.mark_stopped()
            return 0.0
        while time.monotonic() - began < seconds:
            cancel.check()
            if dbg.read_run_state(self):
                return round(time.monotonic() - began, 2)
            gone_if_dead(self, began, seconds, "the debugger to stop")
            time.sleep(dbg.POLL_PAUSE_S)
        raise Invalid("not_settled",
            f"the debugger channel accepted BREAK and `RUNSTATE` did not say stopped within "
            f"{seconds} s: the guest may still be running. Asking `stop` again is allowed; if it "
            f"fails as well, `close` then `start`")

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

    def console_tail(self, chars: int) -> str:
        """The last `chars` of what the emulator printed on its output."""
        return self.output_tail(chars)

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
            # WHETHER THE GUEST RUNS, off the session's own flag: no channel round trip on every
            # reply.
            "running": self.alive() and not self._at_debugger,
            "altered": self.altered,
            "conf": str(self.launch.conf),
            "conf_digest": self.conf_digest,
            "conf_changed_on_disk": changed,
            "watched": self.launch.watched,
            "bound_s": self.launch.seconds,
            "elapsed_s": round(time.monotonic() - self.started_at, 1),
            # THE EMULATOR'S OUTPUT is what overflows: SDL banners, and the log when no
            # `logfile` is set.
            "output_bytes_dropped": self.dropped,
            # WHETHER THIS SESSION RECORDS, and where, so a caller need not infer it from a
            # `captures` with no `avi` row.
            "captures": (str(self.launch.captures_dir) if self.launch.captures_dir is not None
                         else "on, in the emulator's own directory")
                        if self.launch.capture_video else "off",
            # WHERE `state_write(method="save")` writes and `state_list` reads.
            "state_dir": str(self.launch.state_dir) if self.launch.state_dir is not None
                         else "the emulator's own save/ under its working directory",
        }
