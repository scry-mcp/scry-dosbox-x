"""The INPUT route: keys, mouse buttons and the pointer, carried INTO the guest, and the proof
each one landed.

The session's input port is COM1 as a TCP socket; the resident stub in `guest/SCRY.COM` takes
each framed command off it as it arrives and carries it out inside the machine (a scan byte into
the 8042, a button into the integration device, the pointer through INT 33h). No host event is
involved.

Two proofs, kept apart: the POINTER is read back from the stub before and after every
`send_mouse`; the PROGRAM's reaction is `expect`, a regex over the guest's E9 log waited for from
a mark taken before the post (`_post_and_verify`).
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from scry_core import cancel
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.reply_contract import Code, unavailable
from scry_core.screen_map import Pointer

from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import placement, retrace, running, taps
from scry_dosbox_x import pointer as dpointer
from scry_dosbox_x import program as dprogram
from scry_dosbox_x import run_state as rs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

# Scan set 1 make codes by the mapper-style names `send_keys` takes. The stub injects whatever
# bytes it is handed, so the E0 prefixes and break codes are composed here.
SCAN_SET1: dict[str, tuple[int, ...]] = {
    "escape": (0x01,), "esc": (0x01,),
    "1": (0x02,), "2": (0x03,), "3": (0x04,), "4": (0x05,), "5": (0x06,), "6": (0x07,),
    "7": (0x08,), "8": (0x09,), "9": (0x0A,), "0": (0x0B,),
    "minus": (0x0C,), "equals": (0x0D,), "backspace": (0x0E,), "tab": (0x0F,),
    "q": (0x10,), "w": (0x11,), "e": (0x12,), "r": (0x13,), "t": (0x14,), "y": (0x15,),
    "u": (0x16,), "i": (0x17,), "o": (0x18,), "p": (0x19,),
    "leftbracket": (0x1A,), "rightbracket": (0x1B,),
    "return": (0x1C,), "enter": (0x1C,),
    "a": (0x1E,), "s": (0x1F,), "d": (0x20,), "f": (0x21,), "g": (0x22,), "h": (0x23,),
    "j": (0x24,), "k": (0x25,), "l": (0x26,),
    "semicolon": (0x27,), "quote": (0x28,), "grave": (0x29,), "backslash": (0x2B,),
    "z": (0x2C,), "x": (0x2D,), "c": (0x2E,), "v": (0x2F,), "b": (0x30,), "n": (0x31,),
    "m": (0x32,), "comma": (0x33,), "period": (0x34,), "slash": (0x35,),
    "space": (0x39,), "capslock": (0x3A,),
    "f1": (0x3B,), "f2": (0x3C,), "f3": (0x3D,), "f4": (0x3E,), "f5": (0x3F,), "f6": (0x40,),
    "f7": (0x41,), "f8": (0x42,), "f9": (0x43,), "f10": (0x44,), "f11": (0x57,), "f12": (0x58,),
    "home": (0xE0, 0x47), "up": (0xE0, 0x48), "pageup": (0xE0, 0x49),
    "left": (0xE0, 0x4B), "right": (0xE0, 0x4D), "end": (0xE0, 0x4F),
    "down": (0xE0, 0x50), "pagedown": (0xE0, 0x51), "insert": (0xE0, 0x52),
    "delete": (0xE0, 0x53),
}
MAX_KEYS_PER_CALL = 64    # each scan byte is a frame, a BIOS tick apart, under the session's lock
SCAN_MODIFIERS: dict[str, tuple[int, ...]] = {
    "shift": (0x2A,), "ctrl": (0x1D,), "control": (0x1D,), "alt": (0x38,), "option": (0x38,),
}


def scan_sequence(keys: list[str], mods: str, action: str = "press") -> bytes:
    """The scan bytes of pressing `keys` with `mods` held; unknown names are refused. `down`
    holds the modifiers and presses the keys and nothing more; `up` releases them."""
    if action not in KEY_ACTIONS:
        raise ds.Invalid("bad_argument", f"action is one of {list(KEY_ACTIONS)}; got {action!r}")
    held: list[tuple[int, ...]] = []
    if mods != "-":
        for m in mods.split("+"):
            if m.lower() not in SCAN_MODIFIERS:
                raise ds.Invalid("bad_argument", f"the modifiers are "
                                 f"{sorted(SCAN_MODIFIERS)}; got {m!r} (a DOS keyboard has "
                                 f"no command key)")
            held.append(SCAN_MODIFIERS[m.lower()])
    out = bytearray()
    if action != "up":
        for code in held:
            out.extend(code)
    for name in keys:
        key_code = SCAN_SET1.get(name.lower())
        if key_code is None:
            raise ds.Invalid("bad_argument",
                f"unknown key name {name!r}; the names "
                             f"are {sorted(SCAN_SET1)}")
        if action != "up":
            out.extend(key_code)
        if action != "down":
            out.extend(key_code[:-1] + (key_code[-1] | 0x80,))
    if action != "down":
        for code in reversed(held):
            out.extend(code[:-1] + (code[-1] | 0x80,))
    return bytes(out)



# The opcodes `guest/scry.asm` reads; its header is the contract.
OP_KEY, OP_BUTTON, OP_MOVE, OP_REPORT, OP_RANGE = b"K", b"B", b"M", b"R", b"W"
STUB_PROTOCOL = "7"
# `inject` is the stub's former name: matching it lets its announce read as another protocol,
# not as none.
STUB_ANNOUNCE = re.compile(r"STUB  \. (?:scry|inject) device=(\w+)(?: proto=(\d+))?"
                           r"(?: motion=([01]))?")
REPORT_LINE = re.compile(
    r"STUB  \. mouse x=(\d+) y=(\d+) buttons=(\d+) max=(\d+),(\d+) mode=(\d+) "
    r"screen=(\d+)x(\d+) vbe=(\d+) attr=(\d+) res=(\d+)x(\d+)(?=\s|$)")

BUTTONS = {"left": 0, "right": 1, "middle": 2}
MAX_COORD = 0x7FFF      # INT 33h takes a coordinate in a signed 16-bit register
#: The modifiers as `send_keys` names them, in any case.
MODIFIER_WORDS = tuple(SCAN_MODIFIERS)
#: The buttons as `send_mouse` names them.
BUTTON_WORDS = tuple(BUTTONS)
ACTIONS = ("click", "double", "triple", "down", "up", "drag")
#: What `send_keys` does with the keys: tap them, only press them, only release them.
KEY_ACTIONS = ("press", "down", "up")
UNITS = ("screen", "mouse")

# The units `screen_view` answers in per BIOS mode: cells for text, pixels for graphics. The
# drawn size is not it (200 lines are drawn scan-doubled), so the mode decides and a mode outside
# this table is refused; `units="mouse"` reaches it. Text rows are the font's (25 or 50 under one
# mode byte), read off the driver's range, which spans eight units a row. Under a VBE mode the
# BIOS byte is the emulated card's own number, so the stub asks VBE (4F03h, 4F01h) instead.
TEXT_COLUMNS = {0x00: 40, 0x01: 40, 0x02: 80, 0x03: 80, 0x07: 80}
DRIVER_UNITS_PER_ROW = 8
FIRST_VBE_MODE = 0x100
VBE_GRAPHICS = 0x10       # ModeAttributes bit 4: a graphics mode, else text
SCREEN_UNITS: dict[int, tuple[int, int]] = {
    0x04: (320, 200), 0x05: (320, 200), 0x0D: (320, 200), 0x13: (320, 200),
    0x06: (640, 200), 0x0E: (640, 200),
    0x0F: (640, 350), 0x10: (640, 350),
    0x11: (640, 480), 0x12: (640, 480),
}


@dataclass(frozen=True)
class Report:
    """What the stub reports of the driver's pointer, its range, the BIOS mode and the display."""
    x: int
    y: int
    buttons: int
    max_x: int
    max_y: int
    mode: int
    drawn: tuple[int, int]
    vbe: int = 0
    vbe_attributes: int = 0
    resolution: tuple[int, int] = (0, 0)

    def is_vbe(self) -> bool:
        return self.vbe >= FIRST_VBE_MODE

    def units(self) -> tuple[int, int] | None:
        if self.is_vbe():
            # 4F01h failing leaves 0x0, and the BIOS byte is then no mode a table can read.
            return self.resolution if min(self.resolution) > 0 else None
        if self.mode in TEXT_COLUMNS:
            return TEXT_COLUMNS[self.mode], self.text_rows()
        return SCREEN_UNITS.get(self.mode)

    def text_rows(self) -> int:
        """Rows from a range set as `rows * 8 - 1` (the driver's own) or `(rows - 1) * 8` (a
        program that multiplies its last row); never both of the two fit one range."""
        if (self.max_y + 1) % DRIVER_UNITS_PER_ROW == 0:
            return (self.max_y + 1) // DRIVER_UNITS_PER_ROW
        if self.max_y % DRIVER_UNITS_PER_ROW == 0:
            return self.max_y // DRIVER_UNITS_PER_ROW + 1
        return (self.max_y + 1) // DRIVER_UNITS_PER_ROW

    def kind(self) -> str:
        if self.is_vbe():
            return "pixel" if self.vbe_attributes & VBE_GRAPHICS else "text"
        return "text" if self.mode in TEXT_COLUMNS else "pixel"


def parse_report(line: str) -> Report:
    m = REPORT_LINE.search(line)
    if m is None:
        raise ds.Invalid("host_failed", f"the stub's report is not in its shape: {line!r}")
    x, y, b, mx, my, mode, w, h, vbe, attr, rw, rh = (int(g) for g in m.groups())
    return Report(x, y, b, mx, my, mode, (w, h), vbe, attr, (rw, rh))


def per_unit(size: int, top: int) -> int | None:
    """How many driver coordinates make one screen unit, when the range is a whole number of
    them: set as `size * k - 1` (the driver's own) or as `(size - 1) * k` (a program that
    multiplies its last unit, as Deluxe Paint does). None when neither divides."""
    if (top + 1) % size == 0:
        return (top + 1) // size
    if size > 1 and top % (size - 1) == 0 and top >= size - 1:
        return top // (size - 1)
    return None


def to_driver(unit: int, size: int, top: int) -> int:
    """A screen unit to the driver's coordinate, at the middle of the unit's span: the driver
    snaps to its granularity, and a span's first coordinate can snap into the unit before."""
    k = per_unit(size, top)
    if k is not None:
        return min(unit * k + k // 2, top)
    first = -(-unit * (top + 1) // size)
    last = max(first, -(-(unit + 1) * (top + 1) // size) - 1)
    return min((first + last) // 2, top)


def to_screen(coord: int, size: int, top: int) -> int:
    k = per_unit(size, top)
    if k is not None:
        return min(coord // k, size - 1)
    return coord * size // (top + 1)


def key_commands(seq: bytes) -> list[bytes]:
    return [OP_KEY + bytes([b]) for b in seq]


CLICKS = {"click": 1, "double": 2, "triple": 3}


def button_commands(button: str, action: str) -> list[bytes]:
    """The press and release bytes of an action; a double click is two clicks, frames apart."""
    press, release = bytes([0x80 | BUTTONS[button]]), bytes([BUTTONS[button]])
    one = {"down": [press], "up": [release], "click": [press, release]}
    steps = one["click"] * CLICKS.get(action, 1) if action in CLICKS else one[action]
    return [OP_BUTTON + b for b in steps]


def move_command(x: int, y: int) -> bytes:
    return OP_MOVE + x.to_bytes(2, "little") + y.to_bytes(2, "little")


def range_command(max_x: int, max_y: int) -> bytes:
    """The driver's range becomes 0..`max_x` and 0..`max_y` (INT 33h AX=07h and AX=08h)."""
    return OP_RANGE + max_x.to_bytes(2, "little") + max_y.to_bytes(2, "little")


def require_stub(session: ds.Session) -> None:
    """Refuse unless the resident stub speaks this protocol (an older one would misread the
    frames). Without a log there is nothing to read it from and the input goes out on trust."""
    if session.launch.logfile is None or session.stub_protocol == STUB_PROTOCOL:
        return
    announce = [STUB_ANNOUNCE.search(line) for line in session.e9_since_mark(0)]
    found = [m for m in announce if m is not None]
    if not found:
        if session.parked and session.stop_count <= 1:
            raise ds.Invalid("no_channel",
                "the guest has not run yet: `start` parked it before its first instruction, so "
                "the input stub has not announced itself (`STUB  . scry` on E9); `run_for` or "
                "`resume` lets the autoexec run it, then send again")
        loaded = (f"`start(program=...)` mounted it on {session.launch.stub_drive}: and ran it "
                  f"after the conf's [autoexec], which may have exited or run the program first"
                  if session.launch.stub_drive else "or `start(program=...)` loads it by itself")
        raise ds.Invalid("no_channel",
            "the guest has not announced the input stub (`STUB  . scry` on E9), so nothing "
            "would receive the input: the conf's [autoexec] runs it before the program, "
            f"`mount g \"{dlaunch.GUEST_DIR}\"` then `G:\\{dlaunch.STUB_FILE}`; {loaded}")
    device, proto, motion = found[-1].groups()
    if device != "present":
        raise ds.Invalid("no_channel",
            f"the stub's device probe did not answer the expected identification "
            f"(`device={device}`), so it left memory: the session needs `integration "
            f"device=true`, which `start` sets with an input port, and a build whose device "
            f"answers otherwise reads the same")
    if proto != STUB_PROTOCOL:
        raise ds.Invalid("no_channel",
            f"the resident stub announces protocol {proto or 'none'} and this server speaks "
            f"{STUB_PROTOCOL}: the conf mounts another stub. Mount this package's "
            f"`{dlaunch.GUEST_DIR}`")
    session.stub_protocol, session.stub_motion = proto, motion == "1"


class Delivered(ds.Invalid):
    """A failure after the commands went into the guest; `fields` ride into the reply."""

    def __init__(self, code: Code, message: str, fields: dict[str, Any]) -> None:
        super().__init__(code, message)
        self.fields = fields


def _delivered(e: ds.Invalid, parked: Retraces | None = None) -> Delivered:
    """A send that failed part-way: some of it may have gone in, so it is not to be resent."""
    return Delivered(e.code, str(e), {"route": "guest", **_parked_fields(parked)})


def _parked_fields(parked: Retraces | None) -> dict[str, Any]:
    return {} if parked is None else parked.fields()


class Retraces:
    """A parked machine run one retrace at a time while the stub takes the commands; its last
    stop becomes the reply's."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self.run = 0
        self.last: dict[str, Any] = {}
        rs.read_run_state(session)
        self.clock_ms = session.clock_ms or 0.0
        self.e9_mark = STATE.e9_offset
        self.baseline = {str(tap.id): tap.last_total for tap in STATE.taps.values()}
        if STATE.taps:
            # The stop the post begins at may be one no tool reported, so the totals are read here.
            with contextlib.suppress(ds.Invalid):
                self.baseline.update({str(i): int(c["total"])
                                      for i, c in taps.listed(session).items()})

    def __call__(self) -> float:
        try:
            reply = retrace.run_for(self.session, 1, 0, RETRACE_BOUND_S, ds.no_progress,
                                    who="the input's post")
        except BaseException as e:
            # The machine was stopped when the post began: a cancel leaves it stopped too.
            if cancel.is_cancellation(e):
                with cancel.shielded():
                    ds.Session.stop_at_bound(self.session)
            raise
        self.run += 1
        self.last = reply
        if reply.get("verdict") == contract.OTHER_STOP:
            raise ds.Invalid("wait_stopped",
                f"a declared breakpoint stopped the machine short of retrace {self.run} of the "
                f"post: {reply.get('cause')}. Clear it, or `resume` past it, and send the rest")
        if reply.get("status") != "ok" or reply.get("verdict") != contract.ELAPSED:
            raise ds.Invalid("unexpected_answer",
                f"retrace {self.run} of the post did not come "
                f"({reply.get('code') or reply.get('verdict')}): "
                f"{reply.get('message') or reply.get('note')}")
        self.clock_ms = self.session.clock_ms or 0.0
        return self.clock_ms

    def fields(self) -> dict[str, Any]:
        """What the post ran, and the stop it left the machine at, with the guest's lines of
        every retrace; the watches are as the last one read them."""
        out = {"polls": self.run, **{k: self.last[k] for k in STOP_KEYS if k in self.last}}
        if "watches" in out:
            out["watches"] = taps.since_post(out["watches"], self.baseline)
        if "e9" in out:
            out["e9"] = running.e9_block(self.session, self.e9_mark)
        return out


#: A retrace normally comes in a frame's time; this bounds one that does not.
RETRACE_BOUND_S = 5.0
#: The stop a parked post leaves, as `run_for` reads it.
STOP_KEYS = ("pc", "cpu_mode", "stop_seq", "frame", "instruction", "regs", "watches", "cause",
             "regpoint_hit", "e9")


def _send(session: ds.Session, commands: list[bytes],
          advance: Retraces | None = None) -> list[str]:
    """The commands down the stub's link, its report lines back."""
    try:
        return (session.send_commands(commands) if advance is None
                else session.send_commands(commands, advance))
    except ds.Invalid as e:
        if e.code == "wait_stopped":
            running.observe_stop(session)
        raise


# The stub's announce shares the program's channel, so a pattern it matches would be served as
# the program reacting.
STUB_LINE = dprogram.STUB_LINE
_GLOBAL_FLAGS = re.compile(r"^(?:\(\?[aiLmsux]+\))+")


def program_reaction(expect: str) -> str:
    """`expect`, matched on the program's lines only. Global flag groups stay in front, where
    Python requires them; under verbose mode a trailing comment closes on its own line."""
    flags = _GLOBAL_FLAGS.match(expect)
    head = flags.group(0) if flags else ""
    body = expect[len(head):] + ("\n" if "x" in head else "")
    return rf"{head}^(?!.*{STUB_LINE})(?=.*?(?:{body}))"


def _ready(session: ds.Session, what: str, expect: str | None) -> Retraces | None:
    """A log for `expect`, a stub of this protocol; on a parked machine, the retraces the post
    will run it by, which needs `RUNSTATE`."""
    parked = session.at_debugger()
    if parked:
        running.observe_stop(session)
        session.require_run_state(what)
    if expect is not None:
        _expect_mark(session)
    require_stub(session)
    return Retraces(session) if parked else None


def _expect_mark(session: ds.Session) -> int:
    """Where the log ends; no log to wait on is refused before posting, which cannot be undone."""
    try:
        return session.e9_mark()
    except ds.Invalid as e:
        raise ds.Invalid("bad_argument", f"`expect` cannot be checked: {e}. Refused before posting "
                         f"anything, because a post cannot be taken back") from None


def _report(session: ds.Session, advance: Retraces | None = None) -> Report:
    # On the stub's own line: on E9 it could land inside one of the program's lines.
    return parse_report(_send(session, [OP_REPORT], advance)[0])

def verify_block(expect: str, reaction: dict[str, object]) -> dict[str, Any]:
    """The `verify` block shared by `send_keys`, `send_mouse` and `drive`. `seen_before_waiting`
    is `e9_wait`'s `already`, renamed because with the mark taken before the post it includes a
    reaction written while the key was going in, not only one from before the post."""
    if reaction["verdict"] != contract.TARGET:
        return {"checked": True, "seen": False, "expected": expect,
                "verdict": reaction["verdict"], "waited_s": reaction["waited_s"],
                "arrived_during": reaction["arrived_during"],
                "lines_examined": reaction["lines_examined"],
                "note": f"no new line matching the pattern: {reaction['note']}. The input "
                        f"was delivered and this is a miss on the pattern: the program "
                        f"swallowed it (a modal, a loading state), reacted without writing "
                        f"that line, or the pattern does not match what it writes"}
    return {"checked": True, "seen": True, "expected": expect, "verdict": contract.TARGET,
            "line": reaction["line"], "seen_before_waiting": reaction["already"],
            "lines_before": reaction["lines_before"],
            "waited_s": reaction["waited_s"], "lines_total": reaction["lines_total"]}


EFFECT_WAIT_DEFAULT_S = 10.0    # how long a verified post waits for the guest's reaction
DRIVE_EXPECT_WAIT_S = 5.0       # the default bound on `drive`'s wait for `expect`


def drive_wait_s(seconds: float | None) -> float:
    """`seconds`, or the default bound of `drive`'s wait for `expect`."""
    return DRIVE_EXPECT_WAIT_S if seconds is None else seconds



def _post_and_verify(session: ds.Session, kind: str, post: Any, expect: str | None,
                     seconds: float | None, *, progress: ds.Progress = ds.no_progress,
                     parked: Retraces | None = None, **fields: Any) -> dict[str, Any]:
    """Post one input and say whether the PROGRAM REACTED. `post()` sends the commands and
    returns the reply's own fields.

    A command down the socket is not an input the program took (a modal can capture a key). With
    `expect` the log is marked, the input posted, and a NEW line matching it waited for; history
    and the stub's own lines never count. A miss is the wait's `TIMEOUT`, beside what was posted.
    `E9Stopped` (a breakpoint fired during the wait) is reported with `last_stop`, never as a
    swallowed key; a gone emulator comes back `verify.checked: False`.

    Without `expect` nothing about the program is verified, and `verify` says so. Whatever makes
    verification impossible is refused before the post, which cannot be taken back.
    """
    try:
        return _verify(session, kind, post, expect, seconds, progress, fields, parked)
    except Delivered as e:
        return st.reply(status="INVALID", code=e.code, **fields, **e.fields, delivered=True,
                        verify={"checked": False, "why": "the send failed part-way"},
                        message=f"the {kind} was sent, and some of it may have gone in: {e}")


def _verify(session: ds.Session, kind: str, post: Any, expect: str | None,
            seconds: float | None, progress: ds.Progress,
            fields: dict[str, Any], parked: Retraces | None = None) -> dict[str, Any]:
    if expect is None:
        return st.reply(**fields, **post(), verify={
            "checked": False,
            "why": "no `expect` was given, so the reply says what went into the guest and NOT "
                   "that the program took it; pass expect=<E9 pattern> to confirm its reaction"})
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    mark = _expect_mark(session)
    host = dict(fields, **post())
    try:
        if parked is None:
            reaction = session.e9_wait(program_reaction(expect), wait_s, mark=mark,
                                       progress=progress)
        else:
            reaction = session.e9_wait(program_reaction(expect), wait_s, mark=mark,
                                       progress=progress, advance=parked)
            host.update(parked.fields())
    except ds.E9Stopped as e:
        running.observe_stop(session)
        stop, where = STATE.stop_named(session)
        checked = {"checked": True, "seen": False, "expected": expect,
                   "stopped_during_wait": True, "waited_s": e.waited_s,
                   "lines_on_disk": e.arrived, "why": str(e)}
        # Whether the input landed before the stop is the guest's log's to say.
        return st.reply(status="INVALID", code="wait_stopped", **host, last_stop=stop,
                      verify=checked,
                      message=f"the {kind} went into the guest and the machine STOPPED at the "
                             f"debugger during the wait{where}, so no line matching {expect!r} "
                             f"could arrive: a stopped guest writes nothing. This MISS is the "
                             f"stop's, not the program's; whether the stub delivered it before "
                             f"the stop is the guest's log's to say (`e9` since the post), and "
                             f"a command not delivered waits in the serial buffer for the next "
                             f"resume")
    except ds.Invalid as e:
        return st.reply(status="INVALID", code=e.code, **host,
                      verify={"checked": False, "expected": expect, "why": str(e)},
                      message=f"the {kind} went into the guest and its effect could NOT be "
                             f"verified: {e}")
    return st.reply(**host, verify=verify_block(expect, reaction))


def check_expectation(expect: str | None, seconds: float | None) -> None:
    """The one judge of an expectation, an input's and `drive`'s: a pattern that compiles, and
    a bound only beside it. Types are checked because a `perform` step passes values untyped and
    a TypeError would surface as a traceback."""
    if expect is None:
        if seconds is not None:
            raise ds.Invalid("bad_argument",
                "`seconds` bounds the wait for the guest's reaction, and without "
                             "`expect` there is no reaction to wait for: it would be "
                             "silently ignored. Give an `expect` pattern, or drop `seconds`")
        return
    dlogs.compiled(expect)
    dlogs.compiled(program_reaction(expect))
    if seconds is not None:
        vocab.check_wait(seconds)


def check_keys(keys: list[str], modifiers: list[str] | None, expect: str | None = None,
               seconds: float | None = None) -> None:
    """Everything `send_keys` refuses before anything is sent."""
    # Raw JSON can hand a str, which would be sent as its characters; `cast(object, ...)` lets
    # the runtime guard past the type checker.
    if isinstance(cast(object, keys), str):
        raise ds.Invalid("bad_argument",
            "keys is a LIST of names (['enter']), not a string ('enter'): a "
                         "bare string would be sent as its individual characters")
    if not keys:
        raise ds.Invalid("bad_argument", "send_keys needs at least one key name")
    if len(keys) > MAX_KEYS_PER_CALL:
        raise ds.Invalid("bad_argument",
            f"at most {MAX_KEYS_PER_CALL} key names per call (got {len(keys)}): "
                         f"each key costs wall time under the session's lock; send a longer "
                         f"text in several calls")
    for name in keys:
        if not isinstance(cast(object, name), str) or name.lower() not in SCAN_SET1:
            raise ds.Invalid("bad_argument",
                f"unknown key name {name!r}; the names are {sorted(SCAN_SET1)}")
    for m in modifiers or []:
        if not isinstance(cast(object, m), str) or m.lower() not in SCAN_MODIFIERS:
            raise ds.Invalid("bad_argument",
                f"unknown modifier {m!r}; the modifiers are {sorted(SCAN_MODIFIERS)} (a DOS "
                f"keyboard has no command key)")
    check_expectation(expect, seconds)


def check_mouse(x: int | None, y: int | None, button: str | None, action: str = "click",
                units: str = "screen", expect: str | None = None,
                seconds: float | None = None, target: str | None = None,
                to_x: int | None = None, to_y: int | None = None) -> None:
    """Everything `send_mouse` refuses before anything is sent."""
    if target is not None:
        if not isinstance(cast(object, target), str) or not target:
            raise ds.Invalid("bad_argument", f"target is a control's name on the screen "
                             f"`screen_map_find` matched; got {target!r}")
        if x is not None or y is not None:
            raise ds.Invalid("bad_argument", "`target` names where the pointer goes: give it, "
                             "or `x` and `y`, not both")
        if units != "screen":
            raise ds.Invalid("bad_argument", "a control's place is in the screen's units: "
                             "`target` goes with units 'screen'")
    if x is None and y is None and button is None and target is None and not action:
        raise ds.Invalid("bad_argument",
            "name a move (`x` and `y`, or a `target`), a `button`, or both (the move goes first)")
    if (x is None) != (y is None):
        raise ds.Invalid("bad_argument", "a move needs BOTH `x` and `y`")
    for name, value in (("x", x), ("y", y), ("to_x", to_x), ("to_y", to_y)):
        if value is not None and (isinstance(cast(object, value), bool)
                                  or not isinstance(cast(object, value), int)
                                  or not 0 <= value <= MAX_COORD):
            raise ds.Invalid("bad_argument",
                f"`{name}` is a whole number from 0 to {MAX_COORD}, in `units`; got {value!r}")
    if button is not None:
        vocab.one_of("button", button, BUTTON_WORDS)
    vocab.one_of("action", action, ("", *ACTIONS))
    if (to_x is None) != (to_y is None):
        raise ds.Invalid("bad_argument", "a drag's end needs BOTH `to_x` and `to_y`")
    if action == "drag":
        if x is None and target is None:
            raise ds.Invalid("bad_argument", "a drag starts at a place: give `x` and `y`, or a "
                             "`target`")
        if to_x is None:
            raise ds.Invalid("bad_argument", "a drag ends at a place: give `to_x` and `to_y`")
    elif to_x is not None:
        raise ds.Invalid("bad_argument", "`to_x` and `to_y` are where a drag ends: use them "
                         "with action='drag'")
    vocab.one_of("units", units, UNITS, ": `screen` counts cells in a text mode and pixels in "
                 "a graphics one, as `screen_view` does; `mouse` the driver's own coordinates")
    check_expectation(expect, seconds)


def send_keys(session: ds.Session, keys: list[str], modifiers: list[str] | None,
              expect: str | None, seconds: float | None,
              progress: ds.Progress = ds.no_progress, action: str = "press") -> dict[str, Any]:
    """The body of the `send_keys` tool."""
    check_keys(keys, modifiers, expect, seconds)
    parked = _ready(session, "a key", expect)
    seq = scan_sequence(keys, "+".join(modifiers) if modifiers else "-", action)

    def post() -> dict[str, Any]:
        try:
            _send(session, key_commands(seq), parked)
        except ds.Invalid as e:
            raise _delivered(e, parked) from None
        return {"route": "guest", "posted": len(keys), "bytes": len(seq), "frames": len(seq),
                **_parked_fields(parked)}
    return _post_and_verify(session, "key", post, expect, seconds, progress=progress,
                            parked=parked, keys=keys, modifiers=modifiers or [])


def _target(report: Report, x: int, y: int, units: str) -> tuple[int, int]:
    """Where the driver's pointer goes for (`x`, `y`) in `units`; off the screen is refused."""
    if units == "mouse":
        if x > report.max_x or y > report.max_y:
            raise ds.Invalid("bad_argument",
                f"({x}, {y}) is outside the driver's range 0..{report.max_x}, "
                f"0..{report.max_y}; nothing was sent")
        return x, y
    size = report.units()
    if size is None:
        raise ds.Invalid("bad_argument",
            f"the guest is in {_mode_name(report)}, whose size "
            f"{'VBE did not report' if report.is_vbe() else UNMAPPED}, so the screen's units "
            f"are unknown; pass "
            f"`units='mouse'` with the driver's own coordinates (range 0..{report.max_x}, "
            f"0..{report.max_y}). Nothing was sent")
    if x >= size[0] or y >= size[1]:
        raise ds.Invalid("bad_argument",
            f"({x}, {y}) is outside the screen, {size[0]} x {size[1]} in {_mode_name(report)}; "
            f"nothing was sent")
    return to_driver(x, size[0], report.max_x), to_driver(y, size[1], report.max_y)


NO_MOTION_WHY = ("this build's integration device takes no relative motion, so the pointer was "
                 "placed without any: a program that reads the motion counters (INT 33h AX=0Bh), "
                 "takes movement events (AX=0Ch) or drives a PS/2 mouse saw nothing move")
UNREAD_MOTION_WHY = ("the session has no log, where the stub says whether the build takes "
                     "relative motion")


def _motion(session: ds.Session) -> bool | dict[str, Any]:
    """Whether the move reached the motion counters as well as the pointer."""
    motion = getattr(session, "stub_motion", None)
    if motion is None:
        return unavailable(UNREAD_MOTION_WHY)
    return True if motion else unavailable(NO_MOTION_WHY)


UNMAPPED = "this server does not map (a custom mode)"


def _mode_name(report: Report) -> str:
    return f"VBE mode {report.vbe:#05x}" if report.is_vbe() else f"BIOS mode {report.mode:#04x}"


def _pointer(report: Report) -> dict[str, Any]:
    size = report.units()
    screen = unavailable("an unmapped mode: the screen's size in its own units is not known") \
        if size is None else {
        "x": to_screen(report.x, size[0], report.max_x),
        "y": to_screen(report.y, size[1], report.max_y),
        "width": size[0], "height": size[1]}
    return {"screen": screen, "mouse": {"x": report.x, "y": report.y,
                                        "max_x": report.max_x, "max_y": report.max_y},
            "buttons": [name for name, bit in BUTTONS.items() if report.buttons >> bit & 1],
            "bios_mode": f"{report.mode:#04x}",
            **({"vbe_mode": f"{report.vbe:#05x}"} if report.is_vbe() else {})}


def program_reader(session: ds.Session, program: Pointer) -> Callable[[], tuple[int, int]]:
    """The program's pointer read where the machine is stopped now: each retrace stop after a
    nudge can be in another mode, so the refs are placed again, not once for the first stop."""
    def seen() -> tuple[int, int]:
        places = dpointer.locate(program, lambda ref: placement.pointer_target(ref, session))
        return dpointer.program_at(session.read_bytes, program, places)
    return seen


def _steer(session: ds.Session, parked: Retraces, program: Pointer,
           places: tuple[tuple[int, int], tuple[int, int]], aim: tuple[int, int],
           after: Report) -> tuple[Report, dpointer.Steered | None]:
    """The driver nudged until the program's own pointer is on `aim`; the report after the last
    nudge. A mode with no known size has no ratio to nudge by, and is left as it is."""
    size = after.units()
    if size is None:
        return after, None
    latest = [after]

    def nudge(dx: int, dy: int) -> None:
        here = latest[0]
        _send(session, [move_command(min(max(here.x + dx, 0), here.max_x),
                                     min(max(here.y + dy, 0), here.max_y))], parked)
        latest[0] = _report(session, parked)
    seen_now = program_reader(session, program)

    def resync() -> tuple[tuple[int, int], tuple[int, int]]:
        here = latest[0]
        _send(session, [move_command(0, 0)], parked)
        low = seen_now()
        _send(session, [move_command(here.max_x, here.max_y)], parked)
        latest[0] = _report(session, parked)
        return low, seen_now()
    def interior_reach(reach: tuple[tuple[int, int], tuple[int, int]]
                       ) -> tuple[tuple[int, int], tuple[int, int]]:
        """Per axis, a driver distance and the program units it moved the pointer. A sweep end
        pinned at the program's last unit measures a span that is too short, so that distance is
        halved until the pointer is off the edge; a pointer that never leaves it keeps the first."""
        here = latest[0]
        driver = [here.max_x, here.max_y]
        low, high = list(reach[0]), list(reach[1])
        for _ in range(CLAMP_HALVINGS):
            pinned = [axis for axis in (0, 1) if high[axis] >= size[axis] - 1 and driver[axis] > 1]
            if not pinned:
                break
            for axis in pinned:
                driver[axis] //= 2
            _send(session, [move_command(*driver)], parked)
            high = list(seen_now())
        return ((driver[0], abs(high[0] - low[0])), (driver[1], abs(high[1] - low[1])))

    def widen(reach: tuple[tuple[int, int], tuple[int, int]]) -> tuple[float, float] | None:
        """The aim is past what the driver's range lets the program's pointer reach: widen the
        range to the program's whole screen, at the ratio the sweep just measured."""
        here = latest[0]
        if session.driver_range is not None:
            if (here.max_x, here.max_y) == session.driver_range_seen:
                return None
            session.driver_range = None       # the program reset the driver: its range is back
        (reach_x, reach_y) = interior_reach(reach)
        wanted = (max(_range_for(size[0], reach_x[0], reach_x[1]), here.max_x),
                  max(_range_for(size[1], reach_y[0], reach_y[1]), here.max_y))
        if wanted == (here.max_x, here.max_y):
            return None
        _send(session, [range_command(*wanted)], parked)
        latest[0] = _report(session, parked)
        session.driver_range = {"x": wanted[0], "y": wanted[1]}
        session.driver_range_seen = (latest[0].max_x, latest[0].max_y)
        session.altered = True
        return (latest[0].max_x + 1) / size[0], (latest[0].max_y + 1) / size[1]
    steered = dpointer.steer(
        aim,
        seen_now,
        nudge, ((after.max_x + 1) / size[0], (after.max_y + 1) / size[1]), resync, widen)
    return latest[0], steered


#: How many times a pinned sweep's far end is moved back toward the origin.
CLAMP_HALVINGS = 6


def _range_for(screen: int, max_: int, span: int) -> int:
    """The driver range that spans a `screen` of program units, given that `max_` moved the
    program's pointer `span` units; unchanged when the sweep measured nothing."""
    if span <= 0:
        return max_
    return min(MAX_COORD, -(-(screen - 1) * max_ // span))


def send_mouse_at(session: ds.Session, aimed: dict[str, Any], button: str | None, action: str,
                  expect: str | None, seconds: float | None,
                  progress: ds.Progress = ds.no_progress, *, to_x: int | None = None,
                  to_y: int | None = None, program: Pointer | None = None) -> dict[str, Any]:
    """`send_mouse(target=)`: the pointer to the centre of the control `aimed` names."""
    x, y = aimed["centre"]
    reply = send_mouse(session, x, y, button, action, "screen", expect, seconds, progress, aimed,
                       to_x=to_x, to_y=to_y, program=program)
    return {**reply, "target": aimed["target"], "screen": aimed["screen"],
            "identified_at_stop": aimed["identified_at_stop"]}


def _still_the_screen(report: Report, aimed: dict[str, Any]) -> None:
    """Refuse when the guest's mode changed since `screen_map_find`: the same numbers would read a
    text cell as a pixel. Only kind and size are visible while it runs; a changed screen of the
    same mode is the caller's to catch with `screen_map_find` at a stop."""
    kind, (width, height) = aimed["kind"], aimed["size"]
    units = report.units()
    now = None if units is None else (report.kind(), units)
    if now != (kind, (width, height)):
        said = ("a mode this server does not map" if now is None
                else f"a {now[0]} {now[1][0]}x{now[1][1]} screen")
        raise ds.Invalid("needs_call", f"target={aimed['target']!r} is a control of "
                         f"{aimed['screen']!r}, a {kind} {width}x{height} screen, and the guest "
                         f"shows {said} now: `screen_map_find` again at a stop")


def _landed(after: Report, target: tuple[int, int], x: int | None, y: int | None,
            units: str) -> bool:
    """Whether the pointer is where it was asked to be, in the units it was asked in: a screen
    unit is a span of driver coordinates, any of which is that unit."""
    if units == "mouse":
        return (after.x, after.y) == target
    size = after.units()
    return size is not None and (to_screen(after.x, size[0], after.max_x),
                                 to_screen(after.y, size[1], after.max_y)) == (x, y)


def send_mouse(session: ds.Session, x: int | None, y: int | None, button: str | None,
               action: str, units: str, expect: str | None, seconds: float | None,
               progress: ds.Progress = ds.no_progress,
               aimed: dict[str, Any] | None = None, *, to_x: int | None = None,
               to_y: int | None = None, program: Pointer | None = None) -> dict[str, Any]:
    """The body of the `send_mouse` tool. `aimed` is the control a `target` named
    (`screen_map.Maps.target`); a drag presses at `x`, `y` and releases at `to_x`, `to_y`."""
    check_mouse(x, y, button, action, units, expect, seconds, None, to_x, to_y)
    parked = _ready(session, "a mouse event", expect)
    before = _report(session, parked)
    if aimed is not None:
        _still_the_screen(before, aimed)
    target = None if x is None or y is None else _target(before, x, y, units)
    end = None if to_x is None or to_y is None else _target(before, to_x, to_y, units)
    sized = before.units() is not None
    why_not = (None if program is None else
               dpointer.unsteered(parked is not None, target is not None, units, sized))
    places = (dpointer.locate(program, lambda ref: placement.pointer_target(ref, session))
              if program is not None and target is not None and why_not is None else None)

    def pressing(end_at: tuple[int, int] | None) -> list[bytes]:
        if button is None:
            return []
        if action != "drag":
            return button_commands(button, action)
        assert end_at is not None
        return [*button_commands(button, "down"), move_command(*end_at),
                *button_commands(button, "up")]

    def post() -> dict[str, Any]:
        moves = [] if target is None else [move_command(*target)]
        end_at = end
        steered: dpointer.Steered | None = None
        range_before = session.driver_range is not None
        try:
            if program is not None and places is not None and parked is not None:
                assert x is not None and y is not None
                _send(session, moves, parked)
                after = _report(session, parked)
                after, steered = _steer(session, parked, program, places, (x, y), after)
                if to_x is not None and to_y is not None:
                    end_at = _target(after, to_x, to_y, units)    # the range may have grown
                if buttons := pressing(end_at):
                    _send(session, buttons, parked)
                    after = _report(session, parked)
            else:
                _send(session, moves + pressing(end_at), parked)
                after = _report(session, parked)
        except ds.Invalid as e:
            raise _delivered(e, parked) from None
        arrival = end_at or target
        landed = dpointer.arrived(
            steered, arrival is None or _landed(after, arrival, to_x if end_at else x,
                                                to_y if end_at else y, units), end_at is not None)
        shown = _pointer(after)
        if steered is not None:
            shown["program"] = dpointer.shown(steered)
            if session.driver_range is not None and not range_before:
                shown["program"]["range_widened"] = dict(session.driver_range)
        elif why_not is not None:
            shown["program"] = unavailable(why_not)
        # A screen-unit move that no program pointer judged proves only where the DRIVER is, which
        # a program with its own pointer tracking can disagree with.
        judged = steered is not None or arrival is None or units == "mouse"
        fields: dict[str, Any] = {"route": "guest", "pointer": shown,
                                  "arrived" if judged else "driver_arrived": landed,
                                  **_parked_fields(parked)}
        if target is not None:
            fields["motion"] = _motion(session)
        if arrival is not None and not landed:
            # The driver's granularity or a program's own range (INT 33h AX=07h/08h) moved it out.
            fields["asked"] = {"x": arrival[0], "y": arrival[1]}
        return fields
    asked = {**({"x": x, "y": y} if x is not None and y is not None else {}), "units": units,
             **({"button": button, "action": action} if button is not None else {})}
    return _post_and_verify(session, "mouse event", post, expect, seconds, progress=progress,
                            parked=parked, **asked)
