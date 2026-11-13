"""One live DOSBox-X session, held open, driven through its debugger channel.

Every question is a debugger command sent with the channel's `EXEC` and read from what it PRINTS
(`debugger`); nothing reads the debugger's screen. Launch, logs, runs, stepping, frames and
states are the modules beside it that `Session` delegates to.
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

from scry_core import avi, cancel, judges, log_wait, presence
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.progress import PROGRESS_EVERY_S as PROGRESS_EVERY_S
from scry_core.progress import Progress as Progress
from scry_core.progress import no_progress as no_progress
from scry_core.reply_contract import Invalid as Invalid

from scry_dosbox_x import binary as dbinary
from scry_dosbox_x import collect as dcollect
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import grammar, paths, stub_link
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import process as dprocess
from scry_dosbox_x import program as dprogram

# WHERE EACH SETTABLE NAME IS READ BACK, and at what width in bits.
READBACK: dict[str, tuple[str, int]] = {
    **{n.lower(): (n, 32) for n in grammar.WIDE_NAMES},
    **{n.lower(): (n, 16) for n in grammar.SEGMENT_NAMES},
    **{n: (f"E{n.upper()}", 16) for n in grammar.LOW_HALVES},
}

# `VRT`: run, and stop at the next vertical retrace.
RETRACE_COMMAND = "VRT"
# THE `LOG` FAMILY, one word per line shape: typed with its hex count.
LOG_WORDS = ("LOG", "LOGS", "LOGL", "LOGC")

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
#: `VGAMEMDUMP`'s every answer opens with this; its success line ends `success`.
VGAMEMDUMP_SAID = "DEBUG: VGAMEMDUMP"
VGAMEMDUMP_OK = "success"

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
#: A selector named by its number, which `SELINFO` answers in any CPU mode, unlike a register.
SELECTOR_NUMBER = re.compile(r"[0-9A-Fa-f]{4}")
#: `symbols_load`'s `base_from` as a schema pattern: a register in any case, or a selector number.
BASE_FROM_PATTERN = "^({})$".format("|".join(
    ["".join(f"[{c.lower()}{c.upper()}]" for c in reg) for reg in SELINFO_REGS]
    + [SELECTOR_NUMBER.pattern]))

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

SCREENSHOT_COMMAND = b"S"   # the stub's opcode for the device's capture trigger (guest/scry.asm)

SNAPSHOT_WAIT_S = 10.0
# A STATE IS SAVED AND LOADED BY THE DEBUGGER'S OWN COMMANDS, `SAVESTATE <file>` and `LOADSTATE
# <file>` over the debugger channel.
STATE_WAIT_S = 30.0


class NotStopped(Invalid):
    """The machine is running, and the reading needs it stopped."""

    def __init__(self, message: str, **fields: Any) -> None:
        super().__init__("not_stopped", message, **fields)


def wait_stopped(pattern: str, arrived: int, waited_s: float, *, parked: bool,
                  at_bound: bool) -> Invalid:
    """The refusal a wait gives for a machine at the debugger."""
    return E9Stopped(
        log_wait.stopped_message(pattern, arrived, waited_s, parked=parked, at_bound=at_bound)
        + ". The emulator flushes its log in its own time, so `log` may show more",
        waited_s=waited_s, arrived=arrived)


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


def entry_is(text: str) -> Callable[[str], bool]:
    """A pick for `Session.delete_rows`: the row whose entry is `text`."""
    return lambda entry: entry == text


def check_register_name(name: str) -> str:
    """The lower-case register `SR` takes, or the refusal naming the ones it does."""
    key = name.strip().lower()
    if key not in grammar.SETTABLE:
        raise Invalid("bad_argument", f"{name!r} is not a register this debugger sets. One of: "
                      f"{', '.join(sorted(grammar.SETTABLE))}")
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
from scry_dosbox_x import (  # noqa: E402
    driving,
    frames,
    log_reader,
    run_state,
    saved_states,
    stepping,
    symbol_file,
)

#: The commands after which a survey taken at the stop still holds: they leave the registers, the
#: flags and CR0 as they were (memory and breakpoints they may write); any other drops it.
KEEPS_SURVEY = frozenset({"EV", "BPLIST", "BP", "BPDEL", "BPINT", "BPM", "BPPM", "BPIF",
                        "MEMDUMPBIN", "MEMDUMPLIN", "VGAMEMDUMP", "SELINFO", "RUNSTATE", "INTVEC",
                        "SM", "SV", "LV", "MEMFIND", "MEMS",
                        "CPU", "GDT", "LDT", "IDT", "PAGING", "DOS", "BIOS", "EMU",
                        "CALLBACKS", "VGA", "PRESENCE"})



def refuse_parked_snapshot(session: Any) -> None:
    """A screenshot is of a frame drawn after it is asked, which only a run draws."""
    if session.at_debugger():
        raise Invalid("not_running",
            "a screenshot is the emulator's own capture of the next frame it draws, and a "
            "machine stopped at the debugger draws none: taking one would run it. "
            "`screen_view` reads the screen at this stop without moving it; or `resume`, "
            "then snapshot")

class Session(dprocess.Process):
    """A DOSBox-X process that stays put between questions."""

    # WHETHER A CODE BREAKPOINT IS A WRITE: a build without the heavy debugger plants it as an
    # `INT 3` byte in guest memory on release (`CBreakpoint::Activate`); the heavy one checks each
    # instruction against its list and leaves memory alone. A memory watch plants nothing. Read
    # off the build at the first arming; None until then.
    plants_int3: bool | None = None
    # The range `send_mouse` widened; kept, because restoring it would jump the program's pointer.
    driver_range: dict[str, int] | None = None
    # What the driver's report said right after, to tell that range from a reset to the default.
    driver_range_seen: tuple[int, int] | None = None

    def __init__(self, launch: dlaunch.Launch) -> None:
        dlaunch.validate(launch)
        self.launch = launch
        self.conf_digest = dlaunch.digest(launch.conf)
        self.altered = False
        # THE STUB'S PROTOCOL once the guest announced it (`inputs.require_stub`).
        self.stub_protocol = ""
        self.stub_motion: bool | None = None    # whether a move carries motion; None: unread
        self.vars_held = 0          # the names the debugger's list held at the last read-back
        # THE EXECUTABLE A LOADED TABLE WAS CHECKED AGAINST, as the disk held it then.
        self.image: dict[str, Any] | None = None
        self.started_at = time.monotonic()
        # WHICH OF THE DEBUGGER'S OPTIONAL COMMANDS THIS BUILD PARSES, as `start` read them.
        self.commands = launch.debugger_commands
        self._at_debugger = False   # set by a stop seen, cleared by a release
        #: Whether a release's outcome is not confirmed: the command was sent and no answer said
        #: it was taken, so the guest may be running or stopped and nobody knows yet.
        self._run_unknown = False
        self.stop_count = 0         # how many times the flag went False -> True: each is a
        # stop the server may not have observed through a tool
        self.keys_posted = 0        # how many `send_keys` posted: the first can be swallowed
        self.log_seen_bytes = 0     # the logfile's high-water mark: a smaller file lost lines
        self.paging: bool | None = None     # the last stop survey's paging bit, None unread
        # THIS STOP'S SURVEY, kept until the machine moves or a register is written.
        self._surveyed: tuple[dict[str, str], dict[str, str], bool] | None = None
        self.clock_ms: float | None = None  # `RUNSTATE`'s emulated milliseconds, last read
        self.cycles: int | None = None      # `RUNSTATE`'s cycle count, last read
        self.frames: int | None = None      # `RUNSTATE`'s display frames since power-on
        self.fired_entry: str | None = None   # the `BPIF` row `RUNSTATE` said made this stop

        self._avi_facts: dict[tuple[str, int, int], dict[str, object]] = {}
        self.state_sent = False   # whether the last state command went down the channel
        self.machine_replaced = False   # whether the last state load replaced the machine
        self.state_answered = False   # whether the emulator answered it ok
        # The presence of this session (`presence`), set by `start`.
        self.presence = presence.Shown()
        # THE PROCESS COMES UP LAST, its own fields first.
        dprocess.Process.__init__(self)
        self._spawn(launch)

    def arming_writes(self) -> bool:
        if self.plants_int3 is None:
            self.plants_int3 = not dbinary.heavy_debug(self.launch.binary)
        return self.plants_int3

    def stub_replaced(self) -> None:
        """The guest's memory was replaced (a loaded state), the stub's last sequence with it."""
        if self._link is not None:
            self._link.unprove()

    def _linked(self, sock: socket.socket) -> stub_link.Link:
        return stub_link.Link(INPUT_LINE(sock), self.at_debugger, self._guest_ms)

    def _guest_ms(self) -> float | None:
        """The running guest's emulated ms from `RUNSTATE`; None without one."""
        if not self.has(dbg.RUNSTATE):
            return None
        try:
            run_state.read_run_state(self)
        except Invalid:
            return None
        return self.clock_ms

    # ------------------------------------------------------------------ the channel

    def has(self, command: str) -> bool:
        """Whether this build's debugger parses `command`."""
        return command in self.commands

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        """One debugger command: whether it was taken and every line it printed."""
        if command.split()[:1] and command.split()[0].upper() not in KEEPS_SURVEY:
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
        self._run_unknown = False

    def forget_stop(self) -> None:
        """The machine was released, or was seen running."""
        self.fired_entry = None
        self._at_debugger = False
        self._surveyed = None
        self._run_unknown = False

    @property
    def parked(self) -> bool:
        """Whether the machine was at the debugger when it was last seen."""
        return self._at_debugger

    def at_debugger(self) -> bool:
        """Whether the machine is parked at the debugger; a running one is asked of `RUNSTATE`."""
        if self._at_debugger:
            return True
        if not self.has(dbg.RUNSTATE):
            return False
        return run_state.read_run_state(self)

    def require_stopped(self, what: str) -> None:
        """Refuse `what` unless the machine is stopped at the debugger."""
        run_state.require_stopped(self, what)

    def require_run_state(self, what: str) -> None:
        """Refuse, before anything acts, a tool that waits for a stop this build cannot see."""
        run_state.require_run_state(self, what)

    def wait_ready(self, timeout: float | None = None,
                   progress: Progress = no_progress) -> float:
        """Seconds until the debugger answers that the machine stopped at its first instruction."""
        return run_state.wait_ready(
            self, run_state.READY_TIMEOUT_S if timeout is None else timeout, progress)

    def _first_stop(self) -> bool:
        """Whether the debugger holds the machine now."""
        return run_state.first_stop(self)

    # ------------------------------------------------------------------ driving

    def release(self, command: str) -> list[str]:
        """Let the machine run with `command`."""
        return driving.release(self, command)

    def _survey(self) -> tuple[dict[str, str], dict[str, str], bool]:
        """Where, the registers and the paging bit, read once per stop."""
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

    def watch_program(self) -> None:
        """Fold this stop's DOS process into the program watch, once per reply that reports a
        stop (never per frame of a run). A reading that fails adds nothing: the reply has its own
        refusal for a channel that is gone."""
        try:
            dprogram.observe(dprogram.watch_of(self), dbg.psp(self),
                             lambda: self.listing("DOS MCBS"), self._text_rows,
                             self._expected(), self._ran)
        except Invalid:
            return

    def _expected(self) -> str | None:
        """The program `start` ran, by the name its memory blocks carry."""
        words = (self.launch.program or "").split(maxsplit=1)
        return Path(words[0].replace("\\", "/")).stem.upper() if words else None

    def _ran(self) -> bool:
        """Whether the log holds a line of the program's own, not the stub's."""
        if self.launch.logfile is None:
            return False
        return any(not re.search(dprogram.STUB_LINE, line) for line in self.e9_since(0)[0])

    def _text_rows(self) -> list[str] | None:
        """The text screen's rows at this stop, or None when it is not in a text mode."""
        from scry_dosbox_x import screen, vga  # both import this module
        try:
            if vga.source_of(vga.listed(self, vga.COMMAND_OF["mode"])) != vga.TEXT:
                return None
            with tempfile.TemporaryDirectory(prefix="dosbox-x-fault-") as scratch:
                shown = screen.screen_view(self, None, 0, None, Path(scratch))
        except Invalid:
            return None
        text = shown.get("text")
        return [str(row) for row in text] if isinstance(text, list) else None

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        """Both readings off ONE survey."""
        where, regs, self.paging = self._survey()
        return where, regs

    def breakpoints(self) -> list[dict[str, str]]:
        """What the debugger currently holds, READ OFF IT rather than remembered."""
        text = self.command("BPLIST")
        if grammar.BPLIST_HEADER not in text:
            raise Invalid("unexpected_answer",
                f"`BPLIST` printed no {grammar.BPLIST_HEADER!r}: {text.strip()[-200:]!r}. An empty "
                f"list and a listing that never happened both come back as no rows, and only one "
                f"of them means nothing is armed")
        return grammar.parse_breakpoints(text)

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """Exactly `n` bytes at seg:off, through `MEMDUMPBIN`, in either CPU mode."""
        if n <= 0:
            raise Invalid("bad_argument", f"a read needs a positive length; got {n}")
        if n > grammar.READ_BYTES_MAX:
            raise Invalid("bad_argument",
                f"read_bytes reads up to {grammar.READ_BYTES_MAX} bytes; {n} is a region -- use "
                f"memdump")
        self.require_stopped("a memory read")
        if seg == grammar.LINEAR:
            return self._read_linear(off, n)
        check_segment(seg)
        grammar.check_offset(off, mode if mode is not None else self.where()["mode"])
        with tempfile.TemporaryDirectory(prefix="dosbox-read-") as scratch:
            return self.memdump(seg, off, n, Path(scratch) / "read.bin").read_bytes()

    def _read_linear(self, linear: int, n: int) -> bytes:
        """`n` bytes at a LINEAR address through the page tables of CR3, in any CPU mode."""
        if not self.has("MEMDUMPLIN"):
            raise dbg.missing("MEMDUMPLIN", "a read by linear address")
        if not 0 <= linear <= 0xFFFFFFFF:
            raise Invalid("bad_argument", f"a linear address is 0 to 0xFFFFFFFF; got {linear:#x}")
        command = f"MEMDUMPLIN {dbg.typed_hex(linear)} {dbg.typed_hex(n)} {MEMDUMP_FILE}"
        with tempfile.TemporaryDirectory(prefix="dosbox-read-") as scratch:
            return _dumped(self, command, n, Path(scratch) / "read.bin", (MEMDUMP_OK, MEMDUMP_FAIL),
                           MEMDUMP_OK).read_bytes()

    # How many bytes one `SM` carries: the debugger takes a list of values after the address on one
    # input line.
    WRITE_CHUNK = 8

    # THE ROM OF A REAL-MODE MACHINE, by linear address: the option ROMs and the BIOS.
    ROM_LINEAR = (0xC0000, 0xFFFFF)

    def write_memory(self, seg: int, off: int, data: bytes,
                     mode: str | None = None) -> dict[str, object]:
        """Write `data` at seg:off through `SM`, read it back, and mark the session altered."""
        if not data:
            raise Invalid("bad_argument", "a write needs at least one byte")
        check_segment(seg)
        mode = mode if mode is not None else self.where()["mode"]
        top = grammar.check_offset(off, mode)
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
                    f"{grammar.canonical_seg_off(seg, off)} is in the ROM range (linear 0x{lo:X}, "
                    f"0x{self.ROM_LINEAR[0]:X}-0x{self.ROM_LINEAR[1]:X}): measured on this "
                    f"build, the debugger's `SM` into it does not write and does not "
                    f"refuse, it ENDS the emulator. Nothing was sent")
        self.altered = True
        for i in range(0, len(data), self.WRITE_CHUNK):
            chunk = data[i:i + self.WRITE_CHUNK]
            # EVERY VALUE LEADS WITH A ZERO.
            values = " ".join(f"0{b:02X}" for b in chunk)
            self.command(f"SM {dbg.typed_addr(seg, off + i)} {values}")
        back = self.read_bytes(seg, off, len(data), mode=mode)
        return {"bytes_written": len(data), "readback": back.hex(), "verified": back == data}

    def set_register(self, name: str, value: int) -> dict[str, object]:
        """Write a register, READ IT BACK, and mark the session altered for good."""
        key = check_register_name(name)
        check_register_value(key, value)
        self.require_stopped("a register write")
        self.altered = True
        out = self.command(f"SR {key} {dbg.typed_hex(value)}")
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
        arg = f"BPINT {dbg.typed_hex(number, 2)}"
        if ah is not None:
            arg += f" {dbg.typed_hex(ah, 2)}"
        out = self.command(arg)
        # READ THE LIST BACK, exactly as `run_to` and `watch` do, and for the reason this module
        # states everywhere else.
        armed = grammar.interrupt_row(number, ah)
        if not any(row["entry"] == armed for row in self.breakpoints()):
            raise Invalid("readback_refused",
                f"`{arg}` is not in the debugger's breakpoint list, so it "
                          f"was not armed. Resuming now would run with nothing to "
                          f"stop the machine. What it printed: {out.strip()[-300:]!r}")
        return out

    def retrace(self, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """Run to the next vertical retrace."""
        return driving.retrace(self, began, deadline, progress)

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """A `LOG` word with its hex `count`, and the stop it ends at."""
        return driving.log_cpu(self, word, count, began, deadline, progress)

    def resume(self, look: bool = True) -> dict[str, object]:
        """Let the machine run; `look` says whether it stopped again."""
        return driving.resume(self, look)

    # --------------------------------------------------------------- the debugging

    def step(self, count: int = 1, mode: str = "into") -> dict[str, object]:
        """Advance the machine one instruction at a time, reading where each one landed."""
        return stepping.step(self, count, mode)

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: Progress = no_progress) -> dict[str, object]:
        """Run to an address and say where it stopped."""
        return driving.run_to(self, seg, off, seconds, control, progress)

    def await_stop(self, began: float, deadline: float, target: str,
                   progress: Progress = no_progress, label: str = "",
                   look_once: bool = False) -> tuple[bool, float]:
        """Ask the debugger whether the machine stopped, until `deadline`."""
        return run_state.await_stop(self, began, deadline, target, progress, label, look_once)

    def delete_rows(self, picks: list[Callable[[str], bool]]
                    ) -> list[tuple[dict[str, str] | None, bool]]:
        """The first row each of `picks` takes, deleted from the highest index down (a delete
        renumbers the rows below), one read back: per pick, its row (None) and whether none is
        listed after."""
        listed = self.breakpoints()
        found = [next((b for b in listed if pick(b["entry"])), None) for pick in picks]
        rows = {b["index"]: b for b in found if b is not None}
        for index in sorted(rows, key=lambda i: int(i, 16), reverse=True):
            self.command(f"BPDEL {dbg.typed_hex(int(index, 16), 2)}")
        after = self.breakpoints() if rows else listed
        return [(row, not any(pick(b["entry"]) for b in after))
                for row, pick in zip(found, picks, strict=True)]

    def watch_places(self, places: list[tuple[int, int]]) -> list[dict[str, object]]:
        """Break when memory CHANGES at every one of `places`, the command chosen for the caller:
        a row each (a memory breakpoint compares one byte), in one reading of the mode, a command
        per row and ONE read of the list back."""
        # THE MACHINE IS READ FIRST: a command sent to a running guest is a refusal with a side
        # effect.
        cpu = self.where()["mode"]
        for segment, offset in places:
            check_segment(segment)
            grammar.check_offset(offset, cpu)
        # THE THREE LIST SPELLINGS ARE CAPTURED, NOT DERIVED.
        sent: list[tuple[str, str]] = []
        for segment, offset in places:
            if grammar.watch_kind(cpu) == "BPPM":
                sent.append((f"BPPM {dbg.typed_addr(segment, offset)}",
                             f"BPPM {segment:04X}:{offset:08X}"))
            else:
                sent.append((f"BPM {dbg.typed_addr(segment, offset)}",
                             f"BPMEM {segment:04X}:{offset:04X}"))
        # A watch is NEVER removed by this method.
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
        grammar.check_offset(off, stopped["mode"])
        target = f"{seg:04X}:{off:04X}"
        self.altered |= self.arming_writes()
        self.command(f"BP {dbg.typed_addr(seg, off)}")
        held = self.breakpoints()
        want = ("BP", seg, off)
        listed = next((b for b in held if grammar.bp_row_target(b["entry"]) == want), None)
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
        grammar.check_offset(off, stopped["mode"])
        want = ("BP", seg, off)
        [(row, removed)] = self.delete_rows([lambda e: grammar.bp_row_target(e) == want])
        if row is None:
            return {"entry": f"BP {seg:04X}:{off:04X}", "removed": False,
                    "note": "no such breakpoint to remove"}
        return {"entry": row["entry"], "removed": removed}

    def condition_breakpoint(self, row: str) -> str:
        """Arm `BPIF row` and read the list back: a row it does not hold armed nothing."""
        out = self.command(f"{grammar.CONDITION_ROW}{row}")
        want = f"{grammar.CONDITION_ROW}{row}"
        if not any(b["entry"] == want for b in self.breakpoints()):
            raise Invalid("readback_refused",
                f"`{want}` is not in the debugger's breakpoint list, so it was not armed. What it "
                f"printed: {out.strip()[-300:]!r}")
        return out

    def clear_condition_breakpoint(self, row: str) -> dict[str, object]:
        """Remove a condition breakpoint by its own ROW TEXT, and READ THE LIST BACK."""
        self.where()                      # refuses a running machine before the command
        want = f"{grammar.CONDITION_ROW}{row}"
        [(held, removed)] = self.delete_rows([entry_is(want)])
        if held is None:
            return {"entry": want, "removed": False, "note": "no such breakpoint to remove"}
        return {"entry": want, "removed": removed}

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        """Remove an interrupt breakpoint by its own ROW TEXT, and READ THE LIST BACK."""
        check_interrupt(number, ah)
        self.where()                      # refuses a running machine before the command
        want = grammar.interrupt_row(number, ah)
        [(row, removed)] = self.delete_rows([entry_is(want)])
        if row is None:
            return {"entry": want, "removed": False, "note": "no such breakpoint to remove"}
        return {"entry": want, "removed": removed}

    # ------------------------------------------------------------------ the log

    def e9(self, pattern: str, limit: int = 40) -> tuple[list[str], int]:
        return log_reader.e9(self, pattern, limit)

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        return log_reader.log(self, pattern, limit, channel, since_mark)

    def log_text(self) -> str:
        return log_reader.log_text(self)

    def e9_text(self) -> str:
        return log_reader.e9_text(self)

    def e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        return log_reader.e9_since(self, offset, channel)

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return log_reader.e9_new_since(self, offset)

    def e9_since_mark(self, mark: int) -> list[str]:
        return log_reader.e9_since_mark(self, mark)

    def e9_mark(self) -> int:
        return log_reader.e9_mark(self)

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: Progress = no_progress,
                advance: stub_link.Advance | None = None) -> dict[str, object]:
        return log_reader.e9_wait(self, pattern, seconds, mark, progress, advance)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: Progress = no_progress) -> dict[str, object]:
        return log_reader.log_wait(self, pattern, seconds, channel, mark, progress)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        """Memory to a FILE, returning the path it ended up at."""
        check_segment(seg)
        check_dump_length(length)
        command = f"MEMDUMPBIN {dbg.typed_addr(seg, off)} {dbg.typed_hex(length)} {MEMDUMP_FILE}"
        return _dumped(self, command, length, dest, (MEMDUMP_OK, MEMDUMP_FAIL), MEMDUMP_OK)

    def vgamemdump(self, offset: int, length: int, dest: Path) -> Path:
        """Video memory, planes interleaved, to a file through `VGAMEMDUMP`; its path."""
        check_dump_length(length)
        command = f"VGAMEMDUMP {dbg.typed_hex(offset)} {dbg.typed_hex(length)} {MEMDUMP_FILE}"
        return _dumped(self, command, length, dest, (VGAMEMDUMP_SAID,), VGAMEMDUMP_OK)

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
        numbered = reg.isascii() and SELECTOR_NUMBER.fullmatch(reg) is not None
        if not numbered and not (reg.isascii() and reg.upper() in SELINFO_REGS):
            vocab.one_of("base_from", reg, SELINFO_REGS,
                         ", any case taken, or a selector as four hex digits. The debugger "
                         "answers any other register with a ZEROED descriptor rather than an "
                         "error, which reads as a real selector based at 0")
        name = reg.upper()
        label = "  " if numbered else name      # a number leaves the line's own name blank
        out = self.command(f"SELINFO {name}")
        marker = f"{SELINFO_ECHO} {name}:"
        at = out.rfind(marker)
        if at < 0:
            raise Invalid("unexpected_answer",
                f"the debugger did not echo `{marker}` (emulator "
                f"{'running' if self.alive() else 'GONE'}). What it printed: "
                f"{out.strip()[-300:]!r}")
        # ANCHORED ON THE ANSWER'S OWN LINE, which begins with the register's name.
        line = out.find(f"{label}: b:", at)
        m = SELINFO_FIELDS.match(out, line + len(label) + 2) if line >= 0 else None
        if m is None:
            raise Invalid("unexpected_answer",
                f"`{marker}` came back with no complete base/type/limit on a "
                          f"`{name}:` line of its own. A descriptor read that has to "
                          f"take a field from somewhere else is not a reading. What it "
                          f"printed: {out[at:at + 300]!r}")
        base, kind, limit = (int(m.group(1), 16), int(m.group(2), 16),
                             int(m.group(3), 16))
        # AN ABSENT DESCRIPTOR IS REFUSED RATHER THAN REPORTED AS BASE 0.
        if kind == SELINFO_ABSENT and numbered:
            raise Invalid("bad_argument",
                f"selector {name} has no present descriptor (type:00, base 0, limit 0): "
                f"nothing has set it up in this machine's tables, so check the number "
                f"against a protected-mode stop's `CS` and `DS`")
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
    def acked(out: str, echo: str, name: str) -> None:
        return symbol_file.acked(out, echo, name)

    # ------------------------------------------------------------------ capture

    def captures(self) -> list[dict[str, object]]:
        return frames.captures(self)

    def frame(self, at: int, dest: Path, source: Path) -> Path:
        return frames.frame(self, at, dest, source)

    # ------------------------------------------------------------------ input to the guest

    def stop_at_bound(self) -> bool:
        """A run whose bound ran out, handed back STOPPED; whether this call had to stop it."""
        return run_state.stop_at_bound(self)

    def break_in(self, seconds: float | None = None) -> float:
        """Bring a running guest back to the debugger; the seconds until it said so."""
        return run_state.break_in(
            self, run_state.BREAK_IN_WAIT_S if seconds is None else seconds)

    def state_dir(self) -> Path:
        return saved_states.state_dir(self)

    def state_command(self, verb: str, path: Path, seconds: float) -> dict[str, object]:
        return saved_states.state_command(self, verb, path, seconds)

    def save_state(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        return saved_states.save_state(self, name, seconds)

    def load_state(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        return saved_states.load_state(self, name, seconds)

    def snapshot(self, dest: Path | None = None, seconds: float = SNAPSHOT_WAIT_S,
                 progress: Progress = no_progress) -> dict[str, object]:
        """One still of the RUNNING screen, taken INSIDE the guest."""
        vocab.check_wait(seconds)
        folder = frames.folder(self)
        target = None if dest is None else paths.fresh_named_dest("dest", dest)
        refuse_parked_snapshot(self)
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
            if paths.taken(target):
                raise Invalid("readback_refused", f"{target} appeared while the screenshot was "
                              f"taken, and is somebody's: the screenshot stays at {path}",
                              path=str(path))
            path = dcollect.collect(path, target, "screenshot")
        return {"route": "guest", **judges.file_facts(path)}

    def state_list(self) -> dict[str, object]:
        return saved_states.state_list(self)

    def send_commands(self, commands: list[bytes],
                      advance: stub_link.Advance | None = None) -> list[str]:
        """The input route's post; `advance` runs a parked machine until each is taken."""
        if self._link is None:
            raise Invalid("no_channel", "this session has no input route: its socket was "
                          "never connected")
        if not commands:
            raise Invalid("bad_argument", "nothing to send")
        return self._link.send(commands, advance)

    # ------------------------------------------------------------------ closing

    @property
    def pid(self) -> int:
        return self.proc.pid

    def state(self) -> dict[str, object]:
        """Everything the server says about the session."""
        changed: bool | dict[str, Any]
        try:
            changed = (self.launch.conf.is_file()
                       and dlaunch.current_digest(self.launch.conf) != self.conf_digest)
        except OSError as e:
            changed = contract.unavailable(f"the conf could not be read: {e}")
        # A RELINK UNDER A LIVE SESSION leaves the guest running the image on screen while the
        # table was checked against another one: the stamp the load took says whether it moved.
        image: bool | dict[str, Any] = False
        if self.image is not None:
            try:
                held = Path(str(self.image["path"])).stat()
            except OSError as e:
                image = contract.unavailable(f"the executable could not be read: {e}")
            else:
                image = ((held.st_size, held.st_mtime_ns)
                         != (self.image["size"], self.image["mtime_ns"]))
        # WHETHER THE GUEST RUNS, off the session's own flag: no channel round trip on every
        # reply, except past a release whose outcome no answer confirmed, which is re-read.
        running: bool | dict[str, Any] = self.alive() and not self._at_debugger
        if getattr(self, "_run_unknown", False):
            if not self.has(dbg.RUNSTATE):
                running = contract.unavailable(
                    "the machine was released and this build has no `RUNSTATE` to re-read whether "
                    "it stopped, so whether it runs is unknown: `stop` brings it back")
            else:
                try:
                    running = not self.at_debugger()
                except Invalid as e:
                    running = contract.unavailable(
                        f"the machine was released and its state could not be read back ({e}), "
                        "so whether it runs is unknown")
        return {
            "pid": self.proc.pid,
            "alive": self.alive(),
            "running": running,
            "altered": self.altered,
            "range_widened": self.driver_range,
            # WHAT THE STOPS FOUND OF THE PROGRAM: a block once it is gone, else None.
            "program": dprogram.gone(self),
            "conf": str(self.launch.conf),
            **({"bundle": self.launch.bundle} if self.launch.bundle else {}),
            "conf_digest": self.conf_digest,
            "conf_changed_on_disk": changed,
            "image_changed_on_disk": image,
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
            "state_dir": str(dlaunch.state_dir_of(self.launch)),
        }


def _dumped(session: Session, command: str, length: int, dest: Path,
            said_by: tuple[str, ...], ok: str) -> Path:
    """The file a dump `command` wrote, collected to `dest`: `said_by` picks the lines that report
    it, the last of which must hold `ok`, and the file must be `length` bytes."""
    candidates = session._memdump_candidates()
    # Judged before the debugger writes anything, so a refusal leaves no dump behind to poison
    # the next call.
    dcollect.judge_collection(dest, session.launch.cwd, candidates, "dump")
    dcollect.refuse_leftover(candidates, "dump")
    dest = paths.fresh_named_dest("dest", dest)
    # EVERY REFUSAL FROM THE COMMAND ON TAKES THIS CALL'S FILE AWAY.
    try:
        out = session.command(command)
        said = [ln for ln in out.splitlines() if any(m in ln for m in said_by)]
        if not said or ok not in said[-1]:
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
