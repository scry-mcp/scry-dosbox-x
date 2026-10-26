"""The debugger's printed grammar: register names, CPU modes, offsets and breakpoint rows."""

from __future__ import annotations

import re

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


def real_segments(mode: str) -> bool:
    return mode in (REAL_MODE, V86_MODE)


# Not line-anchored: a row is matched wherever it starts on its line (`00. BP F000:FFF0`).
BREAKPOINT_ROW = re.compile(r"\s*([0-9A-F]{2})\.\s+(\S.*?)\s*$", re.M)


BPLIST_HEADER = "Breakpoint list:"


#: How many bytes one read takes (`read_memory`, a watch's value); a region is a `memdump`.
READ_BYTES_MAX = 128


def offset_ceiling(mode: str) -> int:
    return 0xFFFFFFFF if mode.startswith("Pr") else 0xFFFF


def check_offset(off: int, mode: str) -> int:
    """The ceiling for `mode`, or the refusal."""
    top = offset_ceiling(mode)
    if not 0 <= off <= top:
        raise Invalid("bad_argument",
            f"an offset is 0x0 to 0x{top:X} in {mode} mode; got 0x{off:X}: in real mode an "
            "offset past 0xFFFF addresses nothing")
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


def bp_row_target(entry: str) -> tuple[str, int, int] | None:
    """A BPLIST row as `(kind, seg, off)`, by value: one offset prints at several widths."""
    m = _BP_ROW_ADDR.match(entry.strip())
    if m is not None:
        return m.group(1), int(m.group(2), 16), int(m.group(3), 16)
    lin = _BP_ROW_LINEAR.match(entry.strip())
    if lin is None:
        return None
    return lin.group(1), 0, int(lin.group(2), 16)
