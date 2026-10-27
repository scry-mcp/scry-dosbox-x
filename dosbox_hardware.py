"""`port`, `pic` and `a20`: the machine's I/O ports, its interrupt controllers and its A20 gate,
typed over the debugger's own `IN*`/`OUT*`, `PIC` and `A20`, with `PORTINFO` telling a port no
device answers from a device that answered 0xFF (`docs/reference/hardware.md`)."""

from __future__ import annotations

import re
from typing import Any

from scry_core import judges
from scry_core import vocabulary as vocab
from scry_core.reply_contract import Invalid, unavailable

import dosbox_debugger as dbg
import dosbox_session as ds
import dosbox_state as st

PORTINFO = "PORTINFO"
PORT_MAX = 0xFFFF
#: Each access's size in bits, with the debugger's read and write words for it.
BITS = {8: ("INP", "OUTB"), 16: ("INW", "OUTW"), 32: ("IND", "OUTD")}
PORTINFO_LINE = re.compile(r"^DEBUG: PORTINFO ([0-9A-F]{4}) R1=([01]) R2=([01]) R4=([01]) "
                           r"W1=([01]) W2=([01]) W4=([01])$")
RESULT_LINE = re.compile(r"^Result: ([0-9a-f]+)$")

IRQ_MAX = 15
#: The `PIC` subcommand each action sends.
PIC_ACTIONS = {"mask": "MASKIRQ", "unmask": "UNMASKIRQ", "ack": "ACKIRQ", "raise": "RAISEIRQ",
               "lower": "LOWERIRQ"}
PIC_HEADER = re.compile(r"^(Master|Slave) interrupt controller state$")
PIC_ICW = re.compile(r"^ICW (\d+)/(\d+) special=([01]) auto-eoi=([01]) rotate-eoi=([01]) "
                     r"single=([01]) request_issr=([01]) vectorbase=0x([0-9a-f]{2}) "
                     r"active_irq=(\d+) isr=([0-9a-f]{2}) isrr=([0-9a-f]{2}) "
                     r"isrignore=([0-9a-f]{2})$")
PIC_ROW = re.compile(r"^\s*(\d+) 0x([0-9A-F]{2})   ([R ])    ([M ])    ([S ])   ?(CASCADE)?\s*$")
A20_LINE = re.compile(r"^A20 gate is (ON|OFF)$")


#: What `pic.cpp` writes as the active line when its in-service register is empty.
NONE_IN_SERVICE = 8


def _in_service(line: int) -> int | dict[str, Any]:
    return unavailable("no line is in service") if line == NONE_IN_SERVICE else line


def _hex(value: int, bits: int) -> str:
    return f"0x{value:0{bits // 4}X}"


def _number(name: str, given: object) -> int:
    """An integer or its `0x` spelling, as `set_register` takes one."""
    if given == "" or given is None:
        raise Invalid("bad_argument", f"{name} is required: an integer or `0x` hex")
    return judges.number(name, given, 32, "a port")


def check_port(port: object = None, bits: object = 8, value: object = None, *,
               write: bool = False, **_: Any) -> tuple[int, int | None]:
    """The port, size and value a caller gave, before the session is asked."""
    vocab.one_of("bits", bits, tuple(BITS))
    at = _number("port", port)
    if not 0 <= at <= PORT_MAX:
        raise Invalid("bad_argument", f"port={port!r} is not an I/O port: 0 to 0x{PORT_MAX:X}")
    size = int(bits)      # type: ignore[call-overload]
    if at + size // 8 - 1 > PORT_MAX:
        raise Invalid("bad_argument",
                      f"a {size}-bit access at 0x{at:X} reaches past port 0x{PORT_MAX:X}")
    if not write and value is None:
        return at, None
    number = _number("value", value)
    if not 0 <= number < 1 << size:
        raise Invalid("bad_argument", f"value={value!r} does not fit a {size}-bit port: 0 to "
                      f"0x{(1 << size) - 1:X}")
    return at, number


def check_port_write(**given: Any) -> None:
    check_port(write=True, **given)


def _devices(session: ds.Session, port: int) -> dict[str, bool]:
    """Which accesses of `port` reach a device, by one `PORTINFO`: `r8` .. `w32`."""
    ok, lines = session.exec(f"{PORTINFO} {port:X}")
    found = next((m for m in map(PORTINFO_LINE.match, lines) if m is not None), None)
    if not ok or found is None or int(found.group(1), 16) != port:
        raise Invalid("unexpected_answer", f"`{PORTINFO} {port:X}` answered "
                      f"{' / '.join(lines) or 'nothing'}, not its line for port 0x{port:X}")
    flags = [g == "1" for g in found.groups()[1:]]
    return dict(zip(("r8", "r16", "r32", "w8", "w16", "w32"), flags, strict=True))


def _reached(session: ds.Session, port: int, bits: int, write: bool, tool: str) -> None:
    """Refuse an access no device answers, before it is made."""
    if not session.has(PORTINFO):
        raise dbg.missing(PORTINFO, f"`{tool}`, which tells a port with no device from one "
                          "answering 0xFF,")
    session.require_stopped(tool)
    side = "w" if write else "r"
    if not _devices(session, port)[f"{side}{bits}"]:
        raise Invalid("no_channel",
                      f"no device answers a {bits}-bit {'write' if write else 'read'} of port "
                      f"0x{port:X} on this machine: the emulator would "
                      + ("swallow the value with nothing said" if write else
                         "answer all ones where no device is, which reads as a value")
                      + ". Check the port, the size, and the conf's hardware")


def port_read(session: ds.Session, port: judges.NumberArg, bits: int = 8) -> dict[str, Any]:
    """The body of `port(method="read")`."""
    at, _none = check_port(port, bits)
    _reached(session, at, bits, False, 'port(method="read")')
    # A read can change the device (3DAh resets the attribute flip-flop, 60h takes the key).
    session.altered = True
    word = BITS[bits][0]
    ok, lines = session.exec(f"{word} {at:X}")
    found = next((m for m in map(RESULT_LINE.match, lines) if m is not None), None)
    if not ok or found is None:
        raise Invalid("unexpected_answer", f"`{word} {at:X}` answered "
                      f"{' / '.join(lines) or 'nothing'}, not a `Result:` line")
    value = int(found.group(1), 16)
    if value >> bits:
        raise Invalid("unexpected_answer", f"`{word} {at:X}` answered {value:#x}, wider than "
                      f"the {bits} bits it reads")
    return st.reply(port=_hex(at, 16), bits=bits, value=_hex(value, bits))


def port_write(session: ds.Session, port: judges.NumberArg, value: judges.NumberArg,
               bits: int = 8) -> dict[str, Any]:
    """The body of `port(method="write")`."""
    at, number = check_port(port, bits, value, write=True)
    assert number is not None
    _reached(session, at, bits, True, 'port(method="write")')
    session.altered = True
    word = BITS[bits][1]
    ok, lines = session.exec(f"{word} {at:X} {number:X}")
    if not ok:
        raise Invalid("unexpected_answer", f"`{word} {at:X} {number:X}` was not taken: "
                      f"{' / '.join(lines) or 'nothing'}")
    return st.reply(port=_hex(at, 16), bits=bits, value=_hex(number, bits),
                    readback=unavailable("a port holds no value to read back: what a read of it "
                                         "answers is the device's, not the write's"))


def parse_pic(lines: list[str]) -> dict[str, Any]:
    """The `PIC` listing: each controller's state and its eight lines."""
    controllers: list[dict[str, Any]] = []
    irqs: list[dict[str, Any]] = []
    for line in lines:
        if (head := PIC_HEADER.match(line)) is not None:
            controllers.append({"controller": head.group(1).lower()})
        elif (icw := PIC_ICW.match(line)) is not None and controllers:
            g = icw.groups()
            controllers[-1].update(
                icw_index=int(g[0]), icw_words=int(g[1]), special=g[2] == "1",
                auto_eoi=g[3] == "1", rotate_eoi=g[4] == "1", single=g[5] == "1",
                request_issr=g[6] == "1", vector_base=f"0x{g[7].upper()}",
                active_irq=_in_service(int(g[8])), isr=f"0x{g[9].upper()}",
                isrr=f"0x{g[10].upper()}", isr_ignore=f"0x{g[11].upper()}")
        elif (row := PIC_ROW.match(line)) is not None:
            irqs.append({"irq": int(row.group(1)), "vector": f"0x{row.group(2)}",
                         "requested": row.group(3) == "R", "masked": row.group(4) == "M",
                         "in_service": row.group(5) == "S",
                         **({"cascade": True} if row.group(6) else {})})
    if [c["controller"] for c in controllers] not in (["master"], ["master", "slave"]) \
            or [r["irq"] for r in irqs] != list(range(8 * len(controllers))) \
            or any("vector_base" not in c for c in controllers):
        raise Invalid("unexpected_answer", "`PIC` listed something that is not one or two "
                      f"controllers with their lines: {' / '.join(lines) or 'nothing'}")
    return {"controllers": controllers, "irqs": irqs}


def _pic_listing(session: ds.Session) -> dict[str, Any]:
    ok, lines = session.exec("PIC")
    if not ok:
        raise Invalid("unexpected_answer", f"`PIC` was not taken: {' / '.join(lines)}")
    return parse_pic(lines)


def check_pic(irq: object = None, **_: Any) -> None:
    if not isinstance(irq, int) or isinstance(irq, bool) or not 0 <= irq <= IRQ_MAX:
        raise Invalid("bad_argument", f"irq={irq!r} is not an interrupt line: 0 to {IRQ_MAX} "
                      "(8 to 15 on the slave controller)")


def pic_read(session: ds.Session) -> dict[str, Any]:
    """The body of `pic(method="read")`."""
    session.require_stopped('pic(method="read")')
    return st.reply(**_pic_listing(session))


def pic_action(session: ds.Session, action: str, irq: int) -> dict[str, Any]:
    """The body of `pic`'s actions: one line masked, unmasked, acknowledged, raised or lowered,
    and the line read back. Only a mask is a state the listing must show; the rest say what the
    line holds after."""
    check_pic(irq)
    session.require_stopped(f'pic(method="{action}")')
    listed = _pic_listing(session)
    if irq >= 8 * len(listed["controllers"]):
        raise Invalid("bad_argument", f"irq={irq} is on a slave controller this machine does "
                      "not have")
    session.altered = True
    command = f"PIC {PIC_ACTIONS[action]} {irq}"
    ok, lines = session.exec(command)
    if not ok:
        raise Invalid("unexpected_answer", f"`{command}` was not taken: {' / '.join(lines)}")
    after = next(r for r in _pic_listing(session)["irqs"] if r["irq"] == irq)
    if action in ("mask", "unmask") and after["masked"] != (action == "mask"):
        raise Invalid("readback_refused", f"`{command}` was taken and the listing still shows "
                      f"IRQ {irq} {'un' if action == 'mask' else ''}masked", line=after)
    return st.reply(method=action, irq=irq, line=after)


def a20_read(session: ds.Session) -> dict[str, Any]:
    """The body of `a20(method="read")`."""
    session.require_stopped('a20(method="read")')
    return st.reply(enabled=_a20(session))


def _a20(session: ds.Session) -> bool:
    ok, lines = session.exec("A20")
    found = next((m for m in map(A20_LINE.match, lines) if m is not None), None)
    if not ok or found is None:
        raise Invalid("unexpected_answer", f"`A20` answered {' / '.join(lines) or 'nothing'}, "
                      "not `A20 gate is ON` or `OFF`")
    return found.group(1) == "ON"


def a20_set(session: ds.Session, on: bool) -> dict[str, Any]:
    """The body of `a20(method="on")` and `a20(method="off")`, read back."""
    word = "ON" if on else "OFF"
    session.require_stopped(f'a20(method="{word.lower()}")')
    session.altered = True
    ok, lines = session.exec(f"A20 {word}")
    if not ok:
        raise Invalid("unexpected_answer", f"`A20 {word}` was not taken: {' / '.join(lines)}")
    if _a20(session) != on:
        raise Invalid("readback_refused", f"`A20 {word}` was taken and the gate still reads "
                      f"{'OFF' if on else 'ON'}")
    return st.reply(enabled=on)
