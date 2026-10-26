"""The INPUT route: keys, mouse buttons and the pointer, carried INTO the guest, and the proof
each one landed.

The session's input port is COM1 as a TCP socket; the resident stub in `guest/INJECT.COM` takes
each framed command off it as it arrives and carries it out inside the machine (a scan byte into
the 8042, a button into the integration device, the pointer through INT 33h). No host event is
involved.

Two proofs, kept apart: the POINTER is read back from the stub before and after every
`send_mouse`; the PROGRAM's reaction is `expect`, a regex over the guest's E9 log waited for from
a mark taken before the post (`_post_and_verify`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.reply_contract import Code, unavailable

import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

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


def scan_sequence(keys: list[str], mods: str) -> bytes:
    """The scan bytes of pressing `keys` with `mods` held; unknown names are refused."""
    held: list[tuple[int, ...]] = []
    if mods != "-":
        for m in mods.split("+"):
            if m.lower() not in SCAN_MODIFIERS:
                raise ds.Invalid("bad_argument", f"the modifiers are "
                                 f"{sorted(SCAN_MODIFIERS)}; got {m!r} (a DOS keyboard has "
                                 f"no command key)")
            held.append(SCAN_MODIFIERS[m.lower()])
    out = bytearray()
    for code in held:
        out.extend(code)
    for name in keys:
        key_code = SCAN_SET1.get(name.lower())
        if key_code is None:
            raise ds.Invalid("bad_argument",
                f"unknown key name {name!r}; the names "
                             f"are {sorted(SCAN_SET1)}")
        out.extend(key_code)
        out.extend(key_code[:-1] + (key_code[-1] | 0x80,))
    for code in reversed(held):
        out.extend(code[:-1] + (code[-1] | 0x80,))
    return bytes(out)



# The opcodes `guest/inject.asm` reads; its header is the contract.
OP_KEY, OP_BUTTON, OP_MOVE, OP_REPORT = b"K", b"B", b"M", b"R"
STUB_PROTOCOL = "3"
STUB_ANNOUNCE = re.compile(r"STUB  \. inject device=(\w+)(?: proto=(\d+))?")
REPORT_LINE = re.compile(
    r"STUB  \. mouse x=(\d+) y=(\d+) buttons=(\d+) max=(\d+),(\d+) mode=(\d+) "
    r"screen=(\d+)x(\d+)")

BUTTONS = {"left": 0, "right": 1, "middle": 2}
MAX_COORD = 0x7FFF      # INT 33h takes a coordinate in a signed 16-bit register
#: The modifiers as `send_keys` names them, in any case.
MODIFIER_WORDS = tuple(SCAN_MODIFIERS)
#: The buttons as `send_mouse` names them.
BUTTON_WORDS = tuple(BUTTONS)
ACTIONS = ("click", "double", "down", "up")
UNITS = ("screen", "mouse")

# The units `screen_view` answers in per BIOS mode: cells for text, pixels for graphics. The
# drawn size is not it (200 lines are drawn scan-doubled), so the mode decides and a mode outside
# this table is refused; `units="mouse"` reaches it. Text rows are the font's (25 or 50 under one
# mode byte), read off the driver's range, which spans eight units a row.
TEXT_COLUMNS = {0x00: 40, 0x01: 40, 0x02: 80, 0x03: 80, 0x07: 80}
DRIVER_UNITS_PER_ROW = 8
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

    def units(self) -> tuple[int, int] | None:
        if self.mode in TEXT_COLUMNS:
            return TEXT_COLUMNS[self.mode], (self.max_y + 1) // DRIVER_UNITS_PER_ROW
        return SCREEN_UNITS.get(self.mode)


def parse_report(line: str) -> Report:
    m = REPORT_LINE.search(line)
    if m is None:
        raise ds.Invalid("host_failed", f"the stub's report is not in its shape: {line!r}")
    x, y, b, mx, my, mode, w, h = (int(g) for g in m.groups())
    return Report(x, y, b, mx, my, mode, (w, h))


def to_driver(unit: int, size: int, top: int) -> int:
    """A screen unit to the driver's coordinate: the driver spans `0..top` over `size` units."""
    return unit * (top + 1) // size


def to_screen(coord: int, size: int, top: int) -> int:
    return coord * size // (top + 1)


def key_commands(seq: bytes) -> list[bytes]:
    return [OP_KEY + bytes([b]) for b in seq]


def button_commands(button: str, action: str) -> list[bytes]:
    """The press and release bytes of an action; a double click is two clicks, frames apart."""
    press, release = bytes([0x80 | BUTTONS[button]]), bytes([BUTTONS[button]])
    one = {"down": [press], "up": [release], "click": [press, release]}
    steps = one["click"] * 2 if action == "double" else one[action]
    return [OP_BUTTON + b for b in steps]


def move_command(x: int, y: int) -> bytes:
    return OP_MOVE + x.to_bytes(2, "little") + y.to_bytes(2, "little")


def require_stub(session: ds.Session) -> None:
    """Refuse unless the resident stub speaks this protocol (an older one would misread the
    frames). Without a log there is nothing to read it from and the input goes out on trust."""
    if session.launch.logfile is None or session.stub_protocol == STUB_PROTOCOL:
        return
    announce = [STUB_ANNOUNCE.search(line) for line in session.e9_since_mark(0)]
    found = [m for m in announce if m is not None]
    if not found:
        loaded = (f"`start(program=...)` mounted it on {session.launch.stub_drive}: and ran it "
                  f"after the conf's [autoexec], which may have exited or run the program first"
                  if session.launch.stub_drive else "or `start(program=...)` loads it by itself")
        raise ds.Invalid("no_channel",
            "the guest has not announced the input stub (`STUB  . inject` on E9), so nothing "
            "would receive the input: the conf's [autoexec] runs it before the program, "
            f"`mount g \"{dlaunch.GUEST_DIR}\"` then `G:\\INJECT.COM`; {loaded}")
    device, proto = found[-1].groups()
    if device != "present":
        raise ds.Invalid("no_channel",
            f"the stub's device probe did not answer the expected identification "
            f"(`device={device}`), so it left memory: the session needs `integration "
            f"device=true`, which `start` sets with an input port, and a build whose device "
            f"answers otherwise reads the same")
    if proto != STUB_PROTOCOL:
        raise ds.Invalid("no_channel",
            f"the resident stub announces protocol {proto or 'none'} and this server speaks "
            f"{STUB_PROTOCOL}: the conf mounts another INJECT.COM. Mount this package's "
            f"`{dlaunch.GUEST_DIR}`")
    session.stub_protocol = proto


class Delivered(ds.Invalid):
    """A failure after the commands went into the guest; `fields` ride into the reply."""

    def __init__(self, code: Code, message: str, fields: dict[str, Any]) -> None:
        super().__init__(code, message)
        self.fields = fields


def _delivered(e: ds.Invalid) -> Delivered:
    """A send that failed part-way: some of it may have gone in, so it is not to be resent."""
    return Delivered(e.code, str(e), {"route": "guest"})


def _send(session: ds.Session, commands: list[bytes]) -> list[str]:
    """The commands down the stub's link, its report lines back."""
    try:
        return session.send_commands(commands)
    except ds.Invalid as e:
        if e.code == "wait_stopped":
            running.observe_stop(session)
        raise


# The stub's announce shares the program's channel, so a pattern it matches would be served as
# the program reacting. Spelled without a space and under its own flags, so a caller's verbose
# or case-blind pattern cannot change what it excludes.
STUB_LINE = r"(?-i:STUB[ ]{2}\.[ ])"
_GLOBAL_FLAGS = re.compile(r"^(?:\(\?[aiLmsux]+\))+")


def program_reaction(expect: str) -> str:
    """`expect`, matched on the program's lines only. Global flag groups stay in front, where
    Python requires them; under verbose mode a trailing comment closes on its own line."""
    flags = _GLOBAL_FLAGS.match(expect)
    head = flags.group(0) if flags else ""
    body = expect[len(head):] + ("\n" if "x" in head else "")
    return rf"{head}^(?!.*{STUB_LINE})(?=.*?(?:{body}))"


def _ready(session: ds.Session, what: str, expect: str | None) -> None:
    """A running machine, a log for `expect`, a stub of this protocol."""
    _refuse_stopped(session, what)
    if expect is not None:
        _expect_mark(session)
    require_stub(session)


def _expect_mark(session: ds.Session) -> int:
    """Where the log ends; no log to wait on is refused before posting, which cannot be undone."""
    try:
        return session.e9_mark()
    except ds.Invalid as e:
        raise ds.Invalid("bad_argument", f"`expect` cannot be checked: {e}. Refused before posting "
                         f"anything, because a post cannot be taken back") from None


def _refuse_stopped(session: ds.Session, what: str) -> None:
    # A stopped machine would hold the bytes until the next resume. Passive check, not
    # `where()`: on a running guest its nudge is swallowed and the collect stays open for its
    # whole timeout, a window where a stop's prompt was consumed unrecorded.
    if session.at_debugger():
        running.observe_stop(session)
        _, where = STATE.stop_named(session)
        # Not `NotStopped`: that class names a machine that is not stopped.
        raise ds.Invalid("not_running",
            f"the machine is STOPPED at the debugger{where}, so {what} sent now would sit in "
            f"the serial buffer and land at the next resume. `resume` first, then send")


def _report(session: ds.Session) -> Report:
    # On the stub's own line: on E9 it could land inside one of the program's lines.
    return parse_report(_send(session, [OP_REPORT])[0])

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
                     **fields: Any) -> dict[str, Any]:
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
        return _verify(session, kind, post, expect, seconds, progress, fields)
    except Delivered as e:
        return st.reply(status="INVALID", code=e.code, **fields, **e.fields, delivered=True,
                        verify={"checked": False, "why": "the send failed part-way"},
                        message=f"the {kind} was sent, and some of it may have gone in: {e}")


def _verify(session: ds.Session, kind: str, post: Any, expect: str | None,
            seconds: float | None, progress: ds.Progress,
            fields: dict[str, Any]) -> dict[str, Any]:
    if expect is None:
        return st.reply(**fields, **post(), verify={
            "checked": False,
            "why": "no `expect` was given, so the reply says what went into the guest and NOT "
                   "that the program took it; pass expect=<E9 pattern> to confirm its reaction"})
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    mark = _expect_mark(session)
    host = dict(fields, **post())
    try:
        reaction = session.e9_wait(program_reaction(expect), wait_s, mark=mark,
                                   progress=progress)
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
                seconds: float | None = None, target: str | None = None) -> None:
    """Everything `send_mouse` refuses before anything is sent."""
    if target is not None:
        if not isinstance(cast(object, target), str) or not target:
            raise ds.Invalid("bad_argument", f"target is a control's name on the screen "
                             f"`map_find` matched; got {target!r}")
        if x is not None or y is not None:
            raise ds.Invalid("bad_argument", "`target` names where the pointer goes: give it, "
                             "or `x` and `y`, not both")
        if units != "screen":
            raise ds.Invalid("bad_argument", "a control's place is in the screen's units: "
                             "`target` goes with units 'screen'")
    if x is None and y is None and button is None and target is None:
        raise ds.Invalid("bad_argument",
            "name a move (`x` and `y`, or a `target`), a `button`, or both (the move goes first)")
    if (x is None) != (y is None):
        raise ds.Invalid("bad_argument", "a move needs BOTH `x` and `y`")
    for name, value in (("x", x), ("y", y)):
        if value is not None and (isinstance(cast(object, value), bool)
                                  or not isinstance(cast(object, value), int)
                                  or not 0 <= value <= MAX_COORD):
            raise ds.Invalid("bad_argument",
                f"`{name}` is a whole number from 0 to {MAX_COORD}, in `units`; got {value!r}")
    if button is not None:
        vocab.one_of("button", button, BUTTON_WORDS)
    vocab.one_of("action", action, ACTIONS)
    if action != "click" and button is None:
        raise ds.Invalid("bad_argument", f"`action={action!r}` acts on a `button`; name one")
    vocab.one_of("units", units, UNITS, ": `screen` counts cells in a text mode and pixels in "
                 "a graphics one, as `screen_view` does; `mouse` the driver's own coordinates")
    check_expectation(expect, seconds)


def send_keys(session: ds.Session, keys: list[str], modifiers: list[str] | None,
              expect: str | None, seconds: float | None,
              progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The body of the `send_keys` tool."""
    check_keys(keys, modifiers, expect, seconds)
    _ready(session, "a key", expect)
    seq = scan_sequence(keys, "+".join(modifiers) if modifiers else "-")

    def post() -> dict[str, Any]:
        try:
            _send(session, key_commands(seq))
        except ds.Invalid as e:
            raise _delivered(e) from None
        return {"route": "guest", "posted": len(keys), "bytes": len(seq), "ticks": len(seq)}
    return _post_and_verify(session, "key", post, expect, seconds, progress=progress,
                            keys=keys, modifiers=modifiers or [])


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
            f"the guest is in BIOS mode {report.mode:#04x}, whose screen units this server does "
            f"not map (a VESA or custom mode); pass `units='mouse'` with the driver's own "
            f"coordinates (range 0..{report.max_x}, 0..{report.max_y}). Nothing was sent")
    if x >= size[0] or y >= size[1]:
        raise ds.Invalid("bad_argument",
            f"({x}, {y}) is outside the screen, {size[0]} x {size[1]} in mode "
            f"{report.mode:#04x}; nothing was sent")
    return to_driver(x, size[0], report.max_x), to_driver(y, size[1], report.max_y)


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
            "bios_mode": f"{report.mode:#04x}"}


def send_mouse_at(session: ds.Session, aimed: dict[str, Any], button: str | None, action: str,
                  expect: str | None, seconds: float | None,
                  progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """`send_mouse(target=)`: the pointer to the centre of the control `aimed` names."""
    x, y = aimed["centre"]
    reply = send_mouse(session, x, y, button, action, "screen", expect, seconds, progress, aimed)
    return {**reply, "target": aimed["target"], "screen": aimed["screen"],
            "identified_at_stop": aimed["identified_at_stop"]}


def _still_the_screen(report: Report, aimed: dict[str, Any]) -> None:
    """Refuse when the guest's mode changed since `map_find`: the same numbers would read a text
    cell as a pixel. Only kind and size are visible while it runs; a changed screen of the same
    mode is the caller's to catch with `map_find` at a stop."""
    kind, (width, height) = aimed["kind"], aimed["size"]
    units = report.units()
    now = (None if units is None
           else ("text" if report.mode in TEXT_COLUMNS else "pixel", units))
    if now != (kind, (width, height)):
        said = ("a mode this server does not map" if now is None
                else f"a {now[0]} {now[1][0]}x{now[1][1]} screen")
        raise ds.Invalid("needs_call", f"target={aimed['target']!r} is a control of "
                         f"{aimed['screen']!r}, a {kind} {width}x{height} screen, and the guest "
                         f"shows {said} now: `map_find` again at a stop")


def send_mouse(session: ds.Session, x: int | None, y: int | None, button: str | None,
               action: str, units: str, expect: str | None, seconds: float | None,
               progress: ds.Progress = ds.no_progress,
               aimed: dict[str, Any] | None = None) -> dict[str, Any]:
    """The body of the `send_mouse` tool. `aimed` is the control a `target` named
    (`screen_map.Maps.target`)."""
    check_mouse(x, y, button, action, units, expect, seconds)
    _ready(session, "a mouse event", expect)
    before = _report(session)
    if aimed is not None:
        _still_the_screen(before, aimed)
    target = None if x is None or y is None else _target(before, x, y, units)

    def post() -> dict[str, Any]:
        commands = [] if target is None else [move_command(*target)]
        commands += [] if button is None else button_commands(button, action)
        try:
            _send(session, commands)
            after = _report(session)
        except ds.Invalid as e:
            raise _delivered(e) from None
        landed = target is None or (after.x, after.y) == target
        fields: dict[str, Any] = {"route": "guest", "pointer": _pointer(after),
                                  "arrived": landed}
        if target is not None and not landed:
            # A text mode snaps to its cell, a program's own range (INT 33h AX=07h/08h) clamps.
            fields["asked"] = {"x": target[0], "y": target[1]}
        return fields
    asked = {**({"x": x, "y": y} if x is not None and y is not None else {}), "units": units,
             **({"button": button, "action": action} if button is not None else {})}
    return _post_and_verify(session, "mouse event", post, expect, seconds, progress=progress,
                            **asked)
