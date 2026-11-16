"""A debugger behind its channel, for the unit suite: what it answers is the shape the debugger
printed to the same requests live (`tests/fixtures/channel/`, held to it by
`test_dosbox_x_channel_double.py`), from a small machine the case sets up.

`Machine` is stopped or running, holds registers, memory and a breakpoint list, and answers one
`EXEC` at a time; a release (`RUN`, `VRT`, the `LOG` family) runs until the next scripted stop,
which `RUNSTATE` then reports. `session_over` builds a `Session` on it with no process behind.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from scry_dosbox_x import binary as dosbox_binary
from scry_dosbox_x import control, grammar
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import session as ds

FIXTURES = Path(__file__).parent / "fixtures" / "channel"
#: The longest line the debugger's message buffer holds: 512 bytes, one of them the NUL.
DEBUGGER_LINE_MAX = 511
EVERY_COMMAND = dosbox_binary.COMMANDS
NOT_RECOGNIZED = "*** Debugger command not recognized"
RULE = "-" * 73
#: The real-mode stop the probe guest was broken into at, as the capture read it.
REAL_STOP = {"EAX": 0, "EBX": 0xDF, "ECX": 0x4E39, "EDX": 0x814, "ESI": 0x173, "EDI": 0x15D,
             "EBP": 0x91C, "ESP": 0xFFFE, "EIP": 0x130, "CS": 0x814, "DS": 0x814, "ES": 0x814,
             "FS": 0, "GS": 0, "SS": 0x814, "EFLAGS": 0x7213, "CR0": 0x10}
#: The protected-mode stop of the DJGPP guest, at its INT 31h AH=02h.
PROTECTED_STOP = {"EAX": 0x90205, "EBX": 0x9CF24, "ECX": 0xA7, "EDX": 0x992C, "ESI": 0x54,
                  "EDI": 0x1D048, "EBP": 0x9CFA0, "ESP": 0x9CF9C, "EIP": 0x11734, "CS": 0xA7,
                  "DS": 0xAF, "ES": 0xAF, "FS": 0x8F, "GS": 0xBF, "SS": 0xAF, "EFLAGS": 0x3206,
                  "CR0": 0x80000011}
SELINFO_CODE32 = ("CS: b:00400000 type:1B parbg", "    l:0009FFFF dpl : 3 10010")
SELINFO_DATA32 = ("{r}: b:00400000 type:13 parbg", "    l:0009FFFF dpl : 3 10010")
SELINFO_REAL = ("                                  ", "                                  ")
CAPTURE_KINDS = ("WAV", "OPL", "MIDI", "VIDEO")
#: What the emulator itself prints as a kind turns on, ahead of `CAPTURE`'s line.
CAPTURE_SAYS = {"OPL": "Preparing to capture Raw OPL, will start with first note played.",
                "MIDI": "Preparing for raw midi capture, will start with first data."}
#: ...and as it turns off, by whether its writer had opened a file.
CAPTURE_CLOSES = {("WAV", True): "Stopped capturing wave output.",
                  ("OPL", True): "Stopped Raw OPL capturing.",
                  ("OPL", False): "Stopped Raw OPL capturing.",
                  ("MIDI", True): "Stopping raw midi saving and finalizing file.",
                  ("MIDI", False): "Stopped capturing raw midi before any data arrived.",
                  ("VIDEO", True): "Stopped capturing video."}


@dataclass
class Stop:
    """Where a release ends: the registers it changes, and how far the emulated clock and the
    cycle count move to get there; `None` in its place keeps the machine running."""
    regs: dict[str, int] = field(default_factory=dict)
    ms: float = 1.0
    cycles: int = 1000
    frames: int = 1


@dataclass
class Machine:
    """The debugger's side of the channel, answered as the capture shows it answers."""

    regs: dict[str, int] = field(default_factory=lambda: dict(REAL_STOP))
    commands: tuple[str, ...] = EVERY_COMMAND
    stopped: bool = True
    cwd: Path | None = None
    memory: dict[int, int] = field(default_factory=dict)
    #: What each release meets, in order, then `then`: a `Stop`, or None for no stop at all.
    releases: list[Stop | None] = field(default_factory=list)
    then: Stop | None = None
    #: Where each `STEPIN` lands, in order.
    steps: list[dict[str, int]] = field(default_factory=list)
    breakpoints: list[str] = field(default_factory=list)
    #: Requests a running machine answers `running` to before its scripted stop is reached.
    polls_before_stop: int = 0
    selinfo: dict[str, tuple[str, str]] = field(default_factory=dict)
    sent: list[str] = field(default_factory=list)
    cycles: int = 0
    clock_ms: float = 0.7
    #: The display frames since power-on `RUNSTATE` prints; None, a build that prints none.
    frames: int | None = None
    alive: bool = True
    _pending: Stop | None = None
    _polls: int = 0
    #: Per `CAPTURE` kind, the file its writer opens at its first data (copied into the capture
    #: folder at the first release with the kind on), or absent for a kind that gets none.
    capture_sources: dict[str, Path] = field(default_factory=dict)
    capture_rollovers: int = 0
    capture_first: int = 0
    #: The kinds on, each with the file it writes, None until its first data.
    capturing: dict[str, Path | None] = field(default_factory=dict)
    #: Per `TAP` kind (`W`, `R`, `C`), the file the debugger has written for such a tap by the
    #: time `TAPLIST` flushes it; a kind absent records nothing.
    tap_sources: dict[str, Path] = field(default_factory=dict)
    #: The taps installed: id -> kind, physical address, length, file.
    taps: dict[int, tuple[str, int, int, Path]] = field(default_factory=dict)
    tap_next: int = 1
    #: A hook the case puts on one command word: called with the command, it may answer instead.
    hooks: dict[str, Callable[[str], tuple[bool, list[str]] | None]] = field(default_factory=dict)

    # ------------------------------------------------------------------ the channel

    def request(self, command: str, seconds: float = 5.0,
                poll: Callable[[], None] = lambda: None, *,
                unless_silent: bool = False) -> tuple[bool, list[str]]:
        self.sent.append(command)
        if not self.alive:
            raise ds.Invalid("session_broken", "the debugger channel dropped (the emulator "
                             "closed it)")
        if command == "BREAK":
            self._stop_here(Stop(ms=0.0, cycles=0, frames=0))
            return True, []
        if command == "PING":
            return True, ["PONG"]
        body = command.removeprefix("EXEC ")
        word = body.split()[0].upper()
        hook = self.hooks.get(word)
        if hook is not None and (got := hook(body)) is not None:
            return got
        if word in EVERY_COMMAND and word not in self.commands:
            return False, [NOT_RECOGNIZED]
        handler = getattr(self, f"_do_{word.lower()}", None)
        if handler is None:
            return False, [NOT_RECOGNIZED]
        result: tuple[bool, list[str]] = handler(body.split()[1:])
        return result

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------ the run state

    def _stop_here(self, stop: Stop | None = None) -> None:
        stop = stop or Stop()
        self.regs.update(stop.regs)
        self.stopped, self._pending = True, None
        self.cycles += stop.cycles
        self.clock_ms += stop.ms
        if self.frames is not None:
            self.frames += stop.frames

    def _release(self) -> None:
        self.stopped, self._polls = False, 0
        self._pending = self.releases.pop(0) if self.releases else self.then
        for kind, path in self.capturing.items():
            source = self.capture_sources.get(kind)
            if path is None and source is not None and self.cwd is not None:
                folder = self.cwd / "capture"
                folder.mkdir(exist_ok=True)
                for n in range(self.capture_first, self.capture_first + self.capture_rollovers + 1):
                    made = folder / f"sound_{n:03d}{source.suffix}"
                    made.write_bytes(source.read_bytes())
                self.capturing[kind] = made

    def _do_runstate(self, _: list[str]) -> tuple[bool, list[str]]:
        if not self.stopped and self._pending is not None:
            if self._polls >= self.polls_before_stop:
                self._stop_here(self._pending)
            self._polls += 1
        state = "stopped" if self.stopped else "running"
        frames = "" if self.frames is None else f" frames={self.frames}"
        return True, [f"DEBUG: RUNSTATE {state} cycles={self.cycles} "
                      f"ms={self.clock_ms:.9f}{frames}"]

    def _do_run(self, _: list[str]) -> tuple[bool, list[str]]:
        self._release()
        return True, ["OK"]

    _do_vrt = _do_run

    def _do_log(self, _: list[str]) -> tuple[bool, list[str]]:
        self._release()
        return True, ["DEBUG: Starting log"]

    _do_logs = _do_logl = _do_logc = _do_log

    def _do_stepin(self, _: list[str]) -> tuple[bool, list[str]]:
        if not self.stopped:
            return False, ["DEBUG: STEPIN requires the debugger to be stopped"]
        if self.steps:
            self.regs.update(self.steps.pop(0))
        r = self.regs
        return True, [f"DEBUG: STEPIN CS:IP={r['CS']:04X}:{r['EIP'] & 0xFFFF:04X} "
                      f"AX={r['EAX'] & 0xFFFF:04X} BX={r['EBX'] & 0xFFFF:04X} "
                      f"CX={r['ECX'] & 0xFFFF:04X} DX={r['EDX'] & 0xFFFF:04X}"]

    # ------------------------------------------------------------------ captures

    def _capture_line(self, kind: str, on: bool, path: Path | None) -> str:
        line = f"DEBUG: CAPTURE {kind} {'on' if on else 'off'} path={path or '-'}"
        return line[:DEBUGGER_LINE_MAX]      # `DEBUG_ShowMsg` formats into `char buf[512]`

    def _do_capture(self, args: list[str]) -> tuple[bool, list[str]]:
        if not args:
            return True, [self._capture_line(k, k in self.capturing, self.capturing.get(k))
                          for k in CAPTURE_KINDS]
        kind, word = args[0].upper(), args[1].upper() if len(args) > 1 else ""
        if kind not in CAPTURE_KINDS or word not in ("ON", "OFF") or len(args) != 2:
            return False, ["DEBUG: CAPTURE usage: CAPTURE [WAV|OPL|MIDI|VIDEO ON|OFF]"]
        said = [CAPTURE_SAYS[kind]] if word == "ON" and kind in CAPTURE_SAYS else []
        if word == "ON":
            self.capturing.setdefault(kind, None)
            return True, [*said, self._capture_line(kind, True, self.capturing[kind])]
        on = kind in self.capturing
        path = self.capturing.pop(kind, None)
        said = [CAPTURE_CLOSES[kind, path is not None]] if on and (
            kind, path is not None) in CAPTURE_CLOSES else []
        return True, [*said, self._capture_line(kind, False, path)]

    # ------------------------------------------------------------------ taps

    def _do_tap(self, args: list[str]) -> tuple[bool, list[str]]:
        usage = (False, ["DEBUG: TAP usage: TAP W seg:off [bseg:boff blen] file | TAP R seg:off "
                         "file | TAP C seg:off len file (hex; len at most 400, blen at most 80)"])
        if len(args) < 3 or args[0] not in ("W", "R", "C"):
            return usage
        if not self.stopped:
            return False, ["DEBUG: TAP requires the debugger to be stopped"]
        seg, off = (int(x, 16) for x in args[1].split(":"))
        length = int(args[2], 16) if args[0] == "C" else 1
        path = Path(args[-1])
        if not path.parent.is_dir():
            return False, [f"DEBUG: TAP cannot write {path}"]
        path.write_text("")
        tap = self.tap_next
        self.tap_next += 1
        self.taps[tap] = (args[0], seg * 16 + off, length, path)
        return True, [f"DEBUG: TAP {tap} {args[0]} PHYS={seg * 16 + off:X} LEN={length:X} "
                      f"success FILE={path}"]

    def _do_taplist(self, _: list[str]) -> tuple[bool, list[str]]:
        lines = []
        for tap, (kind, phys, length, path) in self.taps.items():
            source = self.tap_sources.get(kind)
            text = source.read_text() if source is not None else ""
            path.write_text(text)
            rows = text.count("\nr ") + text.startswith("r ")
            values = [ln for ln in text.splitlines() if ln.startswith("v ")]
            pcs = [ln for ln in text.splitlines() if ln.startswith("p ")]
            total = sum(int(v.split()[-1]) for v in values) if kind == "C" else rows
            lines.append(f"DEBUG: TAP {tap} {kind} PHYS={phys:X} LEN={length:X} INSTALLED=1 "
                         f"TOTAL={total} ROWS={0 if kind == 'C' else rows} OVERFLOW_ROWS=0 "
                         f"VALUES={len(values)} OVERFLOW_VALUES=0 PCS={len(pcs)} "
                         f"OVERFLOW_PCS=0")
        return True, [*lines, f"DEBUG: TAPLIST {len(self.taps)}"]

    def _do_tapdel(self, args: list[str]) -> tuple[bool, list[str]]:
        every = args == ["*"]
        gone = list(self.taps) if every else [int(args[0])] if int(args[0]) in self.taps else []
        if not gone and not every:
            return False, [f"DEBUG: TAPDEL no tap {args[0]}"]
        for tap in gone:
            del self.taps[tap]
        return True, [f"DEBUG: TAPDEL {len(gone)} removed"]

    # ------------------------------------------------------------------ readings

    def _do_ev(self, names: list[str]) -> tuple[bool, list[str]]:
        values = [f"{self.regs.get(n.upper(), 0):x}" for n in names]
        return True, [f"EV of '{' '.join(names)}' is:", " ".join(values)]

    def _do_selinfo(self, args: list[str]) -> tuple[bool, list[str]]:
        reg = args[0].upper() if args else ""
        lines = self.selinfo.get(reg, SELINFO_REAL)
        return True, [f"SelectorInfo {reg}:", *(line.format(r=reg) for line in lines)]

    def _do_memdumpbin(self, args: list[str]) -> tuple[bool, list[str]]:
        seg, off = (int(x, 16) for x in args[0].split(":"))
        length = int(args[1], 16)
        assert self.cwd is not None, "a dump needs the machine's cwd"
        base = seg * 16 + off if not self.regs["CR0"] & 1 else off
        data = bytes(self.memory.get(base + i, 0) for i in range(length))
        (self.cwd / args[2]).write_bytes(data)
        return True, ["DEBUG: Memory dump binary success."]

    def _do_memdumplin(self, args: list[str]) -> tuple[bool, list[str]]:
        linear, length = int(args[0], 16), int(args[1], 16)
        assert self.cwd is not None, "a dump needs the machine's cwd"
        data = bytes(self.memory.get(linear + i, 0) for i in range(length))
        (self.cwd / args[2]).write_bytes(data)
        return True, ["DEBUG: Memory dump binary success."]

    def _do_sm(self, args: list[str]) -> tuple[bool, list[str]]:
        seg, off = (int(x, 16) for x in args[0].split(":"))
        base = seg * 16 + off if not self.regs["CR0"] & 1 else off
        for i, value in enumerate(args[1:]):
            self.memory[base + i] = int(value, 16) & 0xFF
        return True, [f"DEBUG: Memory changed ({len(args) - 1} bytes)"]

    def _do_sr(self, args: list[str]) -> tuple[bool, list[str]]:
        name = args[0].upper() if args else ""
        wide = name if name in grammar.WIDE_NAMES or name in grammar.SEGMENT_NAMES else f"E{name}"
        if wide not in self.regs or len(args) < 2:
            return True, ["DEBUG: Set Register failure."]
        self.regs[wide] = int(args[1], 16)
        return True, ["DEBUG: Set Register success."]

    # ------------------------------------------------------------------ breakpoints

    def _listing(self) -> list[str]:
        return ["Breakpoint list:", RULE,
                *(f"{i:02X}. {entry}" for i, entry in enumerate(self.breakpoints))]

    def _do_bplist(self, _: list[str]) -> tuple[bool, list[str]]:
        return True, self._listing()

    # The debugger puts every new breakpoint at the head of its list, whatever its kind.
    def _do_bp(self, args: list[str]) -> tuple[bool, list[str]]:
        self.breakpoints.insert(0, f"BP {args[0]}")
        return True, [f"DEBUG: Set breakpoint at {args[0]}"]

    def _do_bpint(self, args: list[str]) -> tuple[bool, list[str]]:
        ah = f" AH={args[1]}" if len(args) > 1 else ""
        self.breakpoints.insert(0, f"BPINT {args[0]}{ah}")
        return True, [f"DEBUG: Set interrupt breakpoint at INT {args[0]}{ah}"]

    def _do_bpm(self, args: list[str]) -> tuple[bool, list[str]]:
        self.breakpoints.insert(0, f"BPMEM {args[0]} (00)")
        return True, [f"DEBUG: Set memory breakpoint at {args[0]}"]

    def _do_bppm(self, args: list[str]) -> tuple[bool, list[str]]:
        seg, off = args[0].split(":")
        self.breakpoints.insert(0, f"BPPM {seg}:{int(off, 16):08X} (00)")
        return True, [f"DEBUG: Set prot-mode memory breakpoint at {seg}:{int(off, 16):08X}"]

    # A freeze is listed by its offset alone, its segment dropped, as the debugger lists it.
    def _do_fm(self, args: list[str]) -> tuple[bool, list[str]]:
        seg, off = (int(x, 16) for x in args[0].split(":"))
        value = self.memory.get(seg * 16 + off, 0)
        self.breakpoints.insert(0, f"FM {off:08X} ({value:02X})")
        return True, [f"DEBUG: Set memory freeze at {seg:04X}:{off:04X} with value: {value:02X}"]

    def _do_bpdel(self, args: list[str]) -> tuple[bool, list[str]]:
        if args and args[0] == "*":
            self.breakpoints.clear()
            return True, ["DEBUG: Breakpoints deleted."]
        index = int(args[0], 16) if args else -1
        if not 0 <= index < len(self.breakpoints):
            return True, ["DEBUG: Breakpoint deletion failure."]
        del self.breakpoints[index]
        return True, ["DEBUG: Breakpoint deletion success."]


def session_over(machine: Machine, cwd: Path, *, logfile: Path | None = None,
                 alive: Callable[[], bool] | None = None) -> ds.Session:
    """A `Session` whose debugger is `machine`, with no process behind it."""
    machine.cwd = cwd
    s = ds.Session.__new__(ds.Session)
    s.launch = dlaunch.Launch(binary="/stub/dosbox-x", conf=cwd / "g.conf", cwd=cwd, seconds=60,
                              logfile=logfile)
    s.commands = frozenset(machine.commands)
    s.control = machine  # type: ignore[assignment]
    s.altered, s.stop_count, s._at_debugger = False, 0, False
    s._run_unknown = False
    s.plants_int3 = False       # the heavy debugger, as every build this suite stands in for
    s.conf_digest, s.started_at, s.dropped = "", time.monotonic(), 0
    s.paging, s.clock_ms, s.cycles = None, None, None
    s.fired_entry = None
    s.vars_held, s.stub_protocol = 0, ""
    s.image = None          # no table loaded, so no executable to watch
    s._link, s._input = None, None
    s.proc = SimpleNamespace(poll=lambda: None if machine.alive else -9, pid=4242)
    if alive is not None:
        s.alive = alive  # type: ignore[method-assign]
    if machine.stopped:
        s.mark_stopped()
    return s


def protected(machine: Machine) -> Machine:
    """`machine` stopped in the DJGPP guest's protected mode, CS a 32-bit code segment."""
    machine.regs = dict(PROTECTED_STOP)
    machine.selinfo = {"CS": SELINFO_CODE32, **{r: SELINFO_DATA32 for r in ("DS", "ES", "SS")}}
    return machine



class SilentChannel:
    """The channel of an emulator inside a long host call: connected, answering nothing, so
    `ask` (`RUNSTATE`) ends `host_failed` at the bound `seconds`."""

    def __init__(self, seconds: float) -> None:
        self.channel = control.ControlChannel(lambda: None)
        self.seconds = seconds
        self.asked = 0
        self._emulator = socket.create_connection((control.LOCAL_HOST, self.channel.port))

    def ask(self) -> bool:
        self.asked += 1
        ok, _ = self.channel.request(f"EXEC {dbg.RUNSTATE}", self.seconds)
        raise AssertionError(f"a silent channel answered ({ok})")

    def close(self) -> None:
        self._emulator.close()
        self.channel.close()
