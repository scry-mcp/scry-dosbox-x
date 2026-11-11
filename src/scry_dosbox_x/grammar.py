"""The debugger's printed grammar: register names, CPU modes, offsets and breakpoint rows."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from scry_core.reply_contract import Invalid

WIDE_NAMES = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP")


SEGMENT_NAMES = ("CS", "DS", "ES", "FS", "GS", "SS")


REGISTER_NAMES = WIDE_NAMES + SEGMENT_NAMES


# `SR` takes multiple pairs, so an unchecked name could run commands the caller never named.
LOW_HALVES = frozenset({"ax", "bx", "cx", "dx", "si", "di", "bp", "sp", "ip"})


SETTABLE = frozenset(n.lower() for n in REGISTER_NAMES) | LOW_HALVES


# A positive token, never the absence of `Pr`: a stale reading would pass for real mode.
REAL_MODE = "Real"
V86_MODE = "VM86"


CPU_MODES = (REAL_MODE, "Pr16", "Pr32", V86_MODE)


def watch_kind(mode: str) -> str:
    """A change watch's row kind in `mode`; VM86 is real mode's."""
    return "BPPM" if mode.startswith("Pr") else "BPMEM"


def real_segments(mode: str) -> bool:
    return mode in (REAL_MODE, V86_MODE)


# Not line-anchored: a row is matched wherever it starts on its line (`00. BP F000:FFF0`).
BREAKPOINT_ROW = re.compile(r"\s*([0-9A-F]{2})\.\s+(\S.*?)\s*$", re.M)


BPLIST_HEADER = "Breakpoint list:"


#: How many bytes one read takes (`read_memory`, a watch's value); a region is a `memdump`.
READ_BYTES_MAX = 128


#: A segment that says its offset is a LINEAR address, read by `MEMDUMPLIN`: a real-mode stop
#: reaches no further than seg:off16 can.
LINEAR = -1


def offset_ceiling(mode: str) -> int:
    return 0xFFFFFFFF if mode.startswith("Pr") else 0xFFFF


def check_offset(off: int, mode: str) -> int:
    """The ceiling for `mode`, or the refusal."""
    top = offset_ceiling(mode)
    if not 0 <= off <= top:
        raise Invalid("bad_argument",
            f"an offset is 0x0 to 0x{top:X} in {mode} mode; got 0x{off:X}: in real mode an "
            "offset past 0xFFFF addresses nothing; a DPMI guest reaches a protected-mode "
            "stop with `stop(until=\"protected\")`")
    return top


def parse_breakpoints(text: str) -> list[dict[str, str]]:
    """The breakpoint list from the LAST listing; no header also returns empty."""
    at = text.rfind(BPLIST_HEADER)
    if at < 0:
        return []
    return [{"index": i, "entry": e}
            for i, e in BREAKPOINT_ROW.findall(text[at + len(BPLIST_HEADER):])]


def seg_off(seg: int, off: int, digits: int = 8) -> str:
    return f"{seg:04X}:{off:0{digits}X}"


def canonical_seg_off(seg: int, off: int) -> str:
    """One spelling per place: four offset digits up to FFFF, eight past it."""
    return seg_off(seg, off, 8 if off > 0xFFFF else 4)


_BP_ROW_ADDR = re.compile(r"^(BP[A-Z]*)\s+([0-9A-Fa-f]+):([0-9A-Fa-f]+)")
_BP_ROW_LINEAR = re.compile(r"^(BPLM)\s+([0-9A-Fa-f]+)\b")


def interrupt_row(number: int, ah: int | None) -> str:
    """The BPLIST row of an interrupt breakpoint."""
    return f"BPINT {number:02X}" + (f" AH={ah:02X}" if ah is not None else "")


_INT_ROW = re.compile(r"^BPINT ([0-9A-Fa-f]{2})(?: AH=([0-9A-Fa-f]{2}))?$")


def parse_interrupt_row(row: str) -> tuple[int, int | None]:
    """The inverse of `interrupt_row`; INVALID otherwise."""
    m = _INT_ROW.match(row.strip())
    if m is None:
        raise Invalid("unexpected_answer",
            f"{row!r} is not an interrupt breakpoint row (BPINT NN [AH=NN])")
    return int(m.group(1), 16), (int(m.group(2), 16) if m.group(2) is not None else None)


#: The registers `BPIF` compares, as the debugger spells them, and its comparisons.
CONDITION_REGISTERS = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP",
                       "AX", "BX", "CX", "DX", "SI", "DI", "BP", "SP", "IP",
                       "AL", "BL", "CL", "DL", "AH", "BH", "CH", "DH",
                       "CS", "DS", "ES", "FS", "GS", "SS", "FLAGS")
CONDITION_OPS = ("==", "!=", "<=", ">=", "<", ">")
CONDITION_TERMS_MAX = 4
#: A `BPLIST` row of a condition breakpoint opens with this.
CONDITION_ROW = "BPIF "


def check_wait_condition(terms: Sequence[Any]) -> None:
    """A `screen_wait` condition's registers, judged before anything runs: a name this machine
    reads at a stop, and a value its width can hold. `FLAGS` is `BPIF`'s, not a stop's."""
    for t in terms:
        if t.size:
            continue
        if t.operand not in CONDITION_REGISTERS or t.operand == "FLAGS":
            raise Invalid("bad_argument", f"the condition names {t.operand!r}, which is no "
                          "register a stop reads here: "
                          + ", ".join(r for r in CONDITION_REGISTERS if r != "FLAGS"))
        if t.value >= 1 << condition_bits(t.operand):
            raise Invalid("bad_argument", f"{t.operand} is {condition_bits(t.operand)} bits wide "
                          f"and never holds {t.value:#x}")


def condition_bits(register: str) -> int:
    """How wide `BPIF` reads a register: the flags are `reg_flags` whole."""
    if register == "FLAGS" or (len(register) == 3 and register[0] == "E"):
        return 32
    return 8 if register[1] in "LH" and register[0] in "ABCD" else 16


_TERM = re.compile(r"\s*([A-Za-z]+)\s*(==|!=|<=|>=|<|>)\s*(?:0[xX])?([0-9A-Fa-f]{1,8})\s*$")


def condition_row(text: str) -> str:
    """`text` as `BPIF` prints it back (`AX==13 && BX!=0`: registers upper-cased, values bare
    hex), or a refusal saying what it takes."""
    terms = text.split("&&")
    shown: list[str] = []
    for term in terms:
        m = _TERM.fullmatch(term)
        if m is None or m.group(1).upper() not in CONDITION_REGISTERS:
            raise Invalid("bad_argument",
                f"{term.strip()!r} is not a term `BPIF` takes: a register "
                f"({', '.join(CONDITION_REGISTERS)}), a comparison "
                f"({' '.join(CONDITION_OPS)}) and a hex value, terms joined by `&&`")
        register, value = m.group(1).upper(), int(m.group(3), 16)
        if value >> (bits := condition_bits(register)):
            raise Invalid("bad_argument", f"{term.strip()!r} can never hold: {register} holds "
                          f"{bits} bits, and {value:X} is wider")
        shown.append(f"{register}{m.group(2)}{value:X}")
    if len(shown) > CONDITION_TERMS_MAX:
        raise Invalid("bad_argument", f"a condition holds at most {CONDITION_TERMS_MAX} terms; "
                      f"got {len(shown)}")
    return " && ".join(shown)


def register_value(regs: dict[str, str], name: str) -> int | None:
    """`name`'s value from a stop's 32-bit registers, its 16- or 8-bit part named; None when the
    stop carries no such register."""
    if name in regs:
        return int(regs[name], 16)
    if name == "FLAGS":
        flags = regs.get("EFLAGS")
        return None if flags is None else int(flags, 16)
    if len(name) == 2 and name[0] in "ABCD" and name[1] in "LH":
        wide = regs.get(f"E{name[0]}X")
        if wide is None:
            return None
        return int(wide, 16) >> (8 if name[1] == "H" else 0) & 0xFF
    wide = regs.get(f"E{name}")
    return None if wide is None else int(wide, 16) & 0xFFFF


def condition_holds(row: str, regs: dict[str, str]) -> bool | None:
    """Whether a canonical condition holds for a stop's registers; None when one it names is
    not among them."""
    for term in row.split(" && "):
        m = _TERM.fullmatch(term)
        if m is None:
            return None
        value = register_value(regs, m.group(1))
        if value is None:
            return None
        want, op = int(m.group(3), 16), m.group(2)
        if not {"==": value == want, "!=": value != want, "<=": value <= want,
                ">=": value >= want, "<": value < want, ">": value > want}[op]:
            return False
    return True


def bp_row_target(entry: str) -> tuple[str, int, int] | None:
    """A BPLIST row as `(kind, seg, off)`, by value: one offset prints at several widths."""
    m = _BP_ROW_ADDR.match(entry.strip())
    if m is not None:
        return m.group(1), int(m.group(2), 16), int(m.group(3), 16)
    lin = _BP_ROW_LINEAR.match(entry.strip())
    if lin is None:
        return None
    return lin.group(1), 0, int(lin.group(2), 16)
