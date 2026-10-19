"""The INPUT route: keys, mouse buttons and the pointer, carried INTO the guest, and the proof
each one landed.

One route, and no host event in it: the session's input port is COM1 as a TCP socket, and the
resident stub in `guest/INJECT.COM` takes one framed command per timer tick off it and carries it
out inside the machine (a scan byte into the 8042, a button into the integration device, the
pointer through INT 33h), so no host event is involved. The stub's own header holds the
protocol.

Two proofs, kept apart. The POINTER is read back: every `send_mouse` asks the stub to report
where the driver's pointer is, before and after, so a move that did not arrive is a miss and not
a success. The PROGRAM's reaction is `expect`, a regex over the guest's E9 log that only the
program writes, waited for from a mark taken before the post (`_post_and_verify`).

`send_keys` and `send_mouse` have their bodies here; their contracts stay with the
registrations in `dosbox_x_server`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from scry_core.reply_contract import Code

import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

# SCAN CODE SET 1 MAKE CODES, by the mapper-style names `send_keys` takes. An extended key
# carries the E0 prefix; the break code of a byte is the byte with bit 7 set, and the stub
# injects whatever it is handed, one byte per tick, so the sequence is composed HERE.
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
MAX_KEYS_PER_CALL = 64    # each scan byte costs a timer tick under the session's lock
SCAN_MODIFIERS: dict[str, tuple[int, ...]] = {
    "shift": (0x2A,), "ctrl": (0x1D,), "control": (0x1D,), "alt": (0x38,), "option": (0x38,),
}


def scan_sequence(keys: list[str], mods: str) -> bytes:
    """The scan bytes a press of `keys` with `mods` held produces: every modifier's make,
    then each key's make and break, then the modifiers' breaks in reverse. An extended key's
    break repeats the E0 prefix. Unknown names are refused with nothing composed; `cmd` has
    no DOS keyboard to land on and is refused by name."""
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



# THE STUB'S PROTOCOL, the opcodes `guest/inject.asm` reads (its header is the contract).
OP_KEY, OP_BUTTON, OP_MOVE, OP_REPORT = b"K", b"B", b"M", b"R"
STUB_PROTOCOL = "2"
STUB_ANNOUNCE = re.compile(r"STUB  \. inject device=(\w+)(?: proto=(\d+))?")
REPORT_LINE = re.compile(
    r"STUB  \. mouse x=(\d+) y=(\d+) buttons=(\d+) max=(\d+),(\d+) mode=(\d+) "
    r"screen=(\d+)x(\d+)")
REPORT_WAIT_S = 5.0     # a report is two ticks away; this bounds a stub that never answers

BUTTONS = {"left": 0, "right": 1, "middle": 2}
MAX_COORD = 0x7FFF      # INT 33h takes a coordinate in a signed 16-bit register
ACTIONS = ("click", "double", "down", "up")
UNITS = ("screen", "mouse")

# THE SCREEN'S OWN UNITS PER BIOS MODE, the ones `screen_view` answers in: character cells for a
# text mode, pixels for a graphics one. The display's drawn size is not it (a 200-line mode is
# drawn scan-doubled to 400, a text mode at 720 wide), so the mode decides, and a mode outside
# this table is refused rather than guessed: `units="mouse"` reaches it in the driver's own
# coordinates. A text mode's columns are its mode's; its rows are the font's (25 or 50 under one
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
    """What the stub says about the driver's pointer: its position and button bits, the range
    the driver maps it into, the BIOS mode and the drawn display."""
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
    """The press and release bytes an action is; a double click is two clicks, a tick apart
    each, which is what a DOS program timing its own double click sees."""
    press, release = bytes([0x80 | BUTTONS[button]]), bytes([BUTTONS[button]])
    one = {"down": [press], "up": [release], "click": [press, release]}
    steps = one["click"] * 2 if action == "double" else one[action]
    return [OP_BUTTON + b for b in steps]


def move_command(x: int, y: int) -> bytes:
    return OP_MOVE + x.to_bytes(2, "little") + y.to_bytes(2, "little")


def require_stub(session: ds.Session) -> None:
    """The stub has to be resident and speak this protocol before anything is sent: an older
    stub reads every byte as a scan code, so a mouse command would arrive as keystrokes. Read
    off the log when the session has one; without a log there is nothing to read it from, and
    the keys go out on the conf's word."""
    if session.launch.logfile is None or session.stub_protocol == STUB_PROTOCOL:
        return
    announce = [STUB_ANNOUNCE.search(line) for line in session.e9_since_mark(0)]
    found = [m for m in announce if m is not None]
    if not found:
        raise ds.Invalid("no_channel",
            "the guest has not announced the input stub (`STUB  . inject` on E9), so nothing "
            "would receive the input: the conf's [autoexec] runs it before the program, "
            f"`mount g \"{dlaunch.GUEST_DIR}\"` then `G:\\INJECT.COM`, or `start(program=...)` "
            "loads it by itself")
    device, proto = found[-1].groups()
    if device != "present":
        raise ds.Invalid("no_channel",
            "the stub found no integration device (`device=absent`), so it left memory: the "
            "session needs `integration device=true`, which `start` sets with an input port")
    if proto != STUB_PROTOCOL:
        raise ds.Invalid("no_channel",
            f"the resident stub speaks protocol {proto or '1'} and this server protocol "
            f"{STUB_PROTOCOL}: the conf mounts an older INJECT.COM. Mount this package's "
            f"`{dlaunch.GUEST_DIR}`")
    session.stub_protocol = proto


class Delivered(ds.Invalid):
    """A failure AFTER the commands went into the guest: what went in rides with it, so the
    reply says so and a caller does not send them twice."""

    def __init__(self, code: Code, message: str, fields: dict[str, Any]) -> None:
        super().__init__(code, message)
        self.fields = fields


# THE STUB WRITES ON THE SAME CHANNEL THE PROGRAM DOES, and its read-back lands after the mark a
# reaction is waited from: a pattern its line matches would be served as the program reacting.
# Spelled without a space and under its own flags, so a caller's verbose or case-blind pattern
# cannot change what it excludes.
STUB_LINE = r"(?-i:STUB[ ]{2}\.[ ])"
_GLOBAL_FLAGS = re.compile(r"^(?:\(\?[aiLmsux]+\))+")


def program_reaction(expect: str) -> str:
    """`expect`, matched on the program's lines only, never on one the stub wrote. The leading
    global flag groups stay in front, where Python requires them; under verbose mode the
    caller's pattern ends on a line of its own, so a trailing comment closes there."""
    flags = _GLOBAL_FLAGS.match(expect)
    head = flags.group(0) if flags else ""
    body = expect[len(head):] + ("\n" if "x" in head else "")
    return rf"{head}^(?!.*{STUB_LINE})(?=.*?(?:{body}))"


def _refuse_stopped(session: ds.Session, what: str) -> None:
    # A STOPPED MACHINE CANNOT TAKE INPUT: the bytes would sit in the emulator's buffer and
    # land, unannounced, at the next resume. Refused before posting, naming the stop. PASSIVE,
    # and not `where()`: on a running guest the nudge is swallowed and its collect stays open
    # for its whole timeout, and that window is exactly where a stop's prompt was consumed
    # unrecorded.
    if session.at_debugger():
        running.observe_stop(session)
        _, where = STATE.stop_named(session)
        # A PLAIN `Invalid`, not `NotStopped`: that class names a machine that is NOT stopped,
        # and its envelope would list the tools that answer while the guest runs.
        raise ds.Invalid("not_running",
            f"the machine is STOPPED at the debugger{where}, so {what} sent now would sit in "
            f"the serial buffer and land at the next resume. `resume` first, then send")


def _report(session: ds.Session) -> Report:
    mark = session.e9_mark()
    session.send_commands([OP_REPORT])
    try:
        got = session.e9_wait(REPORT_LINE.pattern, REPORT_WAIT_S, mark=mark)
    except ds.E9Expired:
        raise ds.Invalid("host_failed",
            f"the stub did not report the pointer within {REPORT_WAIT_S}s: it is not reading "
            "the port (a guest that masked the timer, or a stub that is gone)") from None
    return parse_report(str(got["line"]))

def effect_seen(expect: str, reaction: dict[str, object]) -> dict[str, Any]:
    """The verified-and-seen block a post or an act hands back, ONE shape for `send_keys`,
    `send_mouse` and `drive`. `seen_before_waiting` is what `e9_wait`'s `already` means from
    a mark: the reaction was in the log when the wait first looked -- which, with the mark
    taken BEFORE the post, includes a reaction the guest wrote WHILE the key was going in.
    It is not named `already`: that reads as "it had happened before the post", and a run
    whose every reaction is stamped after its post would carry it on each.
    `lines_before` is how many lines the guest wrote between the mark and the reaction."""
    return {"checked": True, "seen": True, "expected": expect, "line": reaction["line"],
            "seen_before_waiting": reaction["already"],
            "lines_before": reaction["lines_before"],
            "waited_s": reaction["waited_s"], "lines_total": reaction["lines_total"]}


EFFECT_WAIT_DEFAULT_S = 10.0    # how long a verified post waits for the guest's reaction



def _post_and_verify(session: ds.Session, kind: str, post: Any, expect: str | None,
                     seconds: float | None, *, progress: ds.Progress = ds.no_progress,
                     **fields: Any) -> dict[str, Any]:
    """Post one input and say whether the PROGRAM REACTED, the half `send_keys` and
    `send_mouse` share. `post()` sends the commands and returns the reply's own fields.

    A COMMAND THAT WENT DOWN THE SOCKET IS NOT AN INPUT THE PROGRAM TOOK: a modal popup can
    capture a key while the post reads as a success. So with `expect` (a regex over the
    guest's E9 log) the sequence is: MARK the log, post, then wait for a NEW line matching it.
    A line already on disk before the mark is history and is never served as the reaction,
    and neither is a line the stub wrote (`program_reaction`). A miss is INVALID, saying the
    program did not react, and it still carries what was posted, because a swallowed key is a
    different fact from a key never sent. A line the guest writes between the mark and the post
    (a key still being digested, a timer it logs on) is after the mark and is served;
    `seen_before_waiting` and `waited_s` show that shape.

    ONLY THE EXPIRED BOUND IS THE PROGRAM'S MISS. `E9Expired` is the observation that nothing
    matched; `E9Stopped` is the machine reaching the debugger while the wait looked (a
    breakpoint armed before the post fired after it), reported with `last_stop` and never as
    "the program swallowed it"; a gone emulator or a shrunk log is the instrument breaking, and
    comes back `effect.checked: False` with the wait's own words leading the reason.

    WITHOUT `expect` NOTHING ABOUT THE PROGRAM IS VERIFIED, and the reply says so in `effect`.
    Everything that would make the verification impossible is refused BEFORE the post, because
    a post cannot be taken back.
    """
    try:
        return _verify(session, kind, post, expect, seconds, progress, fields)
    except Delivered as e:
        return st.reply(status="INVALID", code=e.code, **fields, **e.fields, delivered=True,
                        effect={"checked": False, "why": "the read-back failed after the "
                                                      "commands went in"},
                        message=f"the {kind} went into the guest, and then {e}")


def _verify(session: ds.Session, kind: str, post: Any, expect: str | None,
            seconds: float | None, progress: ds.Progress,
            fields: dict[str, Any]) -> dict[str, Any]:
    if expect is None:
        return st.reply(**fields, **post(), effect={
            "checked": False,
            "why": "no `expect` was given, so the reply says what went into the guest and NOT "
                   "that the program took it; pass expect=<E9 pattern> to confirm its reaction"})
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    try:
        mark = session.e9_mark()          # refuses a session with no logfile: no channel
    except ds.Invalid as e:
        raise ds.Invalid("bad_argument", f"`expect` cannot be checked: {e}. Refused before posting "
                         f"anything, because a post cannot be taken back") from None
    host = dict(fields, **post())
    try:
        reaction = session.e9_wait(program_reaction(expect), wait_s, mark=mark,
                                   progress=progress)
    except ds.E9Stopped as e:
        running.observe_stop(session)
        stop, where = STATE.stop_named(session)
        effect = {"checked": True, "seen": False, "expected": expect,
                  "stopped_during_wait": True, "waited_s": e.waited_s,
                  "lines_on_disk": e.arrived, "why": str(e)}
        # WHETHER THE INPUT LANDED BEFORE THE STOP IS THE GUEST'S LOG'S TO SAY: a key can go
        # in, its own reaction produce the wrap that fires the stopper, and the log carry the
        # lines. What is known is where an undelivered command waits.
        return st.reply(status="INVALID", code="wait_stopped", **host, last_stop=stop,
                      effect=effect,
                      message=f"the {kind} went into the guest and the machine STOPPED at the "
                             f"debugger during the wait{where}, so no line matching {expect!r} "
                             f"could arrive: a stopped guest writes nothing. This MISS is the "
                             f"stop's, not the program's; whether the stub delivered it before "
                             f"the stop is the guest's log's to say (`e9` since the post), and "
                             f"a command not delivered waits in the serial buffer for the next "
                             f"resume")
    except ds.E9Expired as e:
        return st.reply(status="INVALID", code="wait_expired", **host,
                      effect={"checked": True, "seen": False, "expected": expect,
                              "why": str(e)},
                      message=f"the {kind} went into the guest but the program did not react: "
                             f"no new line matching {expect!r} within {wait_s}s of the post. "
                             f"It may have swallowed it (a modal, a loading state); either way "
                             f"this is a MISS, not a delivery. {e}")
    except ds.Invalid as e:
        return st.reply(status="INVALID", code=e.code, **host,
                      effect={"checked": False, "expected": expect, "why": str(e)},
                      message=f"the {kind} went into the guest and its effect could NOT be "
                             f"verified: {e}")
    return st.reply(**host, effect=effect_seen(expect, reaction))


def check_expectation(expect: str | None, seconds: float | None) -> None:
    """The reaction half's arguments: a non-empty pattern that compiles, and a bound only
    beside it. TYPES ARE CHECKED because a `perform` step hands its arguments over untyped
    (JSON, no signature check on values), and a TypeError out of `re.compile` or `0 < "3"`
    is a traceback the tool wrapper deliberately does not translate."""
    if expect is None:
        if seconds is not None:
            raise ds.Invalid("bad_argument",
                "`seconds` bounds the wait for the guest's reaction, and without "
                             "`expect` there is no reaction to wait for: it would be "
                             "silently ignored. Give an `expect` pattern, or drop `seconds`")
        return
    if not isinstance(cast(object, expect), str) or not expect:
        raise ds.Invalid("bad_argument",
            f"`expect` is a non-empty regular expression over the E9 log; got "
                         f"{expect!r}. An empty pattern matches every line, so it would "
                         f"take the first unrelated trace as the reaction")
    dlogs.compiled(expect)
    dlogs.compiled(program_reaction(expect))
    wait_s = EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    if isinstance(cast(object, wait_s), bool) or not isinstance(cast(object, wait_s),
                                                                  int | float):
        raise ds.Invalid("bad_argument", f"`seconds` is a number; got {seconds!r}")
    if not 0 < wait_s <= ds.RUN_TO_MAX:
        raise ds.Invalid("bad_argument",
            f"a wait of {wait_s}s for the effect is not a bound: it is more "
                         f"than zero and at most {ds.RUN_TO_MAX}s. Refused before posting")


def check_keys(keys: list[str], modifiers: list[str] | None, expect: str | None = None,
               seconds: float | None = None) -> None:
    """Everything `send_keys` refuses before anything is sent."""
    # A STRING IS NOT A LIST OF NAMES. Over the transport `keys` arrives as raw JSON, so
    # `"keys": "enter"` reaches here as a str; `*keys` would then splat it into e,n,t,e,r --
    # five wrong keys. `cast(object, ...)` lets the honest runtime guard past the type checker.
    if isinstance(cast(object, keys), str):
        raise ds.Invalid("bad_argument",
            "keys is a LIST of names (['enter']), not a string ('enter'): a "
                         "bare string would be sent as its individual characters")
    if not keys:
        raise ds.Invalid("bad_argument", "send_keys needs at least one key name")
    if len(keys) > MAX_KEYS_PER_CALL:
        # THE COST IS WALL TIME UNDER THE SERVER'S LOCK: every scan byte waits a timer tick, so
        # a long text is many seconds during which `status` and `e9` cannot be asked.
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
                seconds: float | None = None) -> None:
    """Everything `send_mouse` refuses before anything is sent: a move, a button or both,
    whole non-negative numbers (a `perform` step hands values over untyped), the vocabularies."""
    if x is None and y is None and button is None:
        raise ds.Invalid("bad_argument",
            "name a move (`x` and `y`), a `button`, or both (the move goes first)")
    if (x is None) != (y is None):
        raise ds.Invalid("bad_argument", "a move needs BOTH `x` and `y`")
    for name, value in (("x", x), ("y", y)):
        if value is not None and (isinstance(cast(object, value), bool)
                                  or not isinstance(cast(object, value), int)
                                  or not 0 <= value <= MAX_COORD):
            raise ds.Invalid("bad_argument",
                f"`{name}` is a whole number from 0 to {MAX_COORD}, in `units`; got {value!r}")
    if button is not None and button not in BUTTONS:
        raise ds.Invalid("bad_argument",
            f"a mouse button is one of {sorted(BUTTONS)}; got {button!r}")
    if action not in ACTIONS:
        raise ds.Invalid("bad_argument", f"`action` is one of {list(ACTIONS)}; got {action!r}")
    if action != "click" and button is None:
        raise ds.Invalid("bad_argument", f"`action={action!r}` acts on a `button`; name one")
    if units not in UNITS:
        raise ds.Invalid("bad_argument",
            f"`units` is 'screen' (cells in a text mode, pixels in a graphics one, as "
            f"`screen_view` counts them) or 'mouse' (the driver's own coordinates); got {units!r}")
    check_expectation(expect, seconds)


def send_keys(session: ds.Session, keys: list[str], modifiers: list[str] | None,
              expect: str | None, seconds: float | None,
              progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The body of the `send_keys` tool."""
    check_keys(keys, modifiers, expect, seconds)
    _refuse_stopped(session, "a key")
    require_stub(session)
    seq = scan_sequence(keys, "+".join(modifiers) if modifiers else "-")

    def post() -> dict[str, Any]:
        session.send_commands(key_commands(seq))
        return {"route": "guest", "posted": len(keys), "bytes": len(seq), "ticks": len(seq)}
    return _post_and_verify(session, "key", post, expect, seconds, progress=progress,
                            keys=keys, modifiers=modifiers or [])


def _target(report: Report, x: int, y: int, units: str) -> tuple[int, int]:
    """Where the driver's pointer has to go for (`x`, `y`) in `units`, refused off the screen."""
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
    screen = None if size is None else {
        "x": to_screen(report.x, size[0], report.max_x),
        "y": to_screen(report.y, size[1], report.max_y),
        "width": size[0], "height": size[1]}
    return {"screen": screen, "mouse": {"x": report.x, "y": report.y,
                                        "max_x": report.max_x, "max_y": report.max_y},
            "buttons": [name for name, bit in BUTTONS.items() if report.buttons >> bit & 1],
            "mode": f"{report.mode:#04x}"}


def send_mouse(session: ds.Session, x: int | None, y: int | None, button: str | None,
               action: str, units: str, expect: str | None, seconds: float | None,
               progress: ds.Progress = ds.no_progress) -> dict[str, Any]:
    """The body of the `send_mouse` tool: read where the pointer is, move it, press, read it
    back. The read-back needs the log, so a session without one is refused before anything."""
    check_mouse(x, y, button, action, units, expect, seconds)
    if session.launch.logfile is None:
        raise ds.Invalid("no_channel",
            "send_mouse reads the pointer back off the guest's E9 log, and this session was "
            "started without a logfile: start it with logfile= to use the mouse")
    _refuse_stopped(session, "a mouse event")
    require_stub(session)
    before = _report(session)
    target = None if x is None or y is None else _target(before, x, y, units)

    def post() -> dict[str, Any]:
        commands = [] if target is None else [move_command(*target)]
        commands += [] if button is None else button_commands(button, action)
        try:
            session.send_commands(commands)
            after = _report(session)
        except ds.E9Stopped as e:
            running.observe_stop(session)
            raise Delivered(e.code, str(e), {"route": "guest"}) from None
        except ds.Invalid as e:
            # SOME OF IT MAY HAVE GONE IN: the socket can die between two commands, and the
            # read-back runs after all of them.
            raise Delivered(e.code, str(e), {"route": "guest"}) from None
        landed = target is None or (after.x, after.y) == target
        fields: dict[str, Any] = {"route": "guest", "pointer": _pointer(after),
                                  "arrived": landed}
        if target is not None and not landed:
            # THE DRIVER PLACED IT ELSEWHERE: a text mode snaps to its cell, a program's own
            # range (INT 33h AX=07h/08h) clamps. Said, never rounded away.
            fields["asked"] = {"x": target[0], "y": target[1]}
        return fields
    return _post_and_verify(session, "mouse event", post, expect, seconds, progress=progress,
                            x=x, y=y, units=units, button=button,
                            action=action if button is not None else None)
