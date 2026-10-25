from __future__ import annotations

import re

from scry_core.reply_contract import Invalid

ANSI = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[()][A-Z0-9]"
    r"|\x1b[=>]")


PARTIAL_TAIL = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*|\][^\x07\x1b]*|[()])?$")


# `resume` tells a stop from a run-on by it: the register pane is not repainted.
PROMPT = "I->"


PAGER_MARK = "Paged content: Hit ENTER to continue"


PAGER_EXIT = b"Q"


# An unrecognised command stays on the input line; ESC empties it, a bare CR would rerun it.
CLEAR_LINE_KEY = b"\x1b"


# A paging listing redraws the input line still holding the command; only the empty one ends.
_ATTRS = r"(?:\x1b\[[0-9;]*m)*"


REPLY_END = re.compile(
    r"(?:I-> _?\x1b\[K(?:\x1b\[\d+;\d+H|\r\x1b\[\d+d)\x1b\(B\x1b\[m" + _ATTRS
    + r"|Paged content: Hit ENTER to continue, Q to exit paging\x1b\[K(?:\x1b\[\d+;\d+H)?"
    r"\x1b\(B\x1b\[m" + _ATTRS + r"(?:\x1b\[\d+;\d+H)?)\Z")


# No `\b`: frame characters arrive as letters (`...ooooEAX=00001234`) and EAX would never match.
WIDE_NAMES = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP")


SEGMENT_NAMES = ("CS", "DS", "ES", "FS", "GS", "SS")


REGISTER_NAMES = WIDE_NAMES + SEGMENT_NAMES


REGISTER = re.compile(f"({'|'.join(REGISTER_NAMES)})=([0-9A-F]+)")


EIP_CARRY = max(len(n) for n in REGISTER_NAMES) + 1


STOP_CARRY = max(EIP_CARRY, len(PROMPT))


# `SR` takes multiple pairs, so an unchecked name could run commands the caller never named.
LOW_HALVES = frozenset({"ax", "bx", "cx", "dx", "si", "di", "bp", "sp", "ip"})


SETTABLE = frozenset(n.lower() for n in REGISTER_NAMES) | LOW_HALVES


# A positive token, never the absence of `Pr`: a stale pane would read as real mode.
REAL_MODE = "Real"
V86_MODE = "VM86"


CPU_MODES = (REAL_MODE, "Pr16", "Pr32", V86_MODE)


def real_segments(mode: str) -> bool:
    return mode in (REAL_MODE, V86_MODE)


# Anchored on the `SS=` line: the Output log below the pane can carry the word `Real`.
CPU_MODE = re.compile(rf"SS=[0-9A-F]{{4}}\s+({'|'.join(CPU_MODES)})\b")


PAGING = re.compile(r"EBP=[0-9A-F]{8}(PAGE|NOPG)")


# Only a full repaint labels it; a stop's delta carries bare digits.
PANE_CLOCK = re.compile(r"pfi=([0-9]+\.[0-9]+)")


# Anchored on the tail: a repaint can glue other text over the label.
PANE_CYCLES = re.compile(r"cc=([0-9]+) *[A-Z]+\r?$", re.M)


# Not line-anchored: repaints glue rows to the text before them (`----00. BP F000:FFF0`).
BREAKPOINT_ROW = re.compile(r"\s*([0-9A-F]{2})\.\s+(\S.*?)\s*$", re.M)


BPLIST_HEADER = "Breakpoint list:"


PANE_HEADER = "Register Overview"


# No `^`: the pane header abuts the first row. The lookahead sits inside the gutter repetition,
# else gutter lengths 1 to 15 swallow the next row's address.
DATA_VIEW_BYTES = 128


_ROW_BYTES = re.compile(r"([0-9A-F]{4}):([0-9A-F]{4,8})((?: [0-9A-F]{2})+)")


def bytes_of_rows(rows: list[str], off: int, length: int) -> str:
    """`length` bytes from `off` of the data-view `rows` as hex; INVALID if they hold fewer."""
    held: dict[int, int] = {}
    for row in rows:
        m = _ROW_BYTES.search(row)
        if m is None:
            continue
        start = int(m.group(2), 16)
        for i, byte in enumerate(m.group(3).split()):
            held[start + i] = int(byte, 16)
    out: list[str] = []
    for a in range(off, off + length):
        if a not in held:
            raise Invalid("readback_refused",
                f"the data view holds {len(out)} bytes from offset {off:#x}, not the "
                f"{length} asked for: ask for fewer, or `memdump` the range")
        out.append(f"{held[a]:02x}")
    return "".join(out)


DATA_ROW = re.compile(
    r"([0-9A-F]{4}):([0-9A-F]{8})((?: [0-9A-F]{2}){16})"
    r"(?:  ((?:(?![0-9A-F]{4}:[0-9A-F]{8})[^\r\n]){0,16}))?")


def parse_registers(text: str) -> dict[str, str]:
    return dict(REGISTER.findall(text))


def where_from(text: str) -> dict[str, str]:
    """The position (cs, eip, mode) of an already-surveyed screen."""
    regs = parse_last_pane(text)
    cpu = parse_mode(text)
    if cpu is None:
        raise Invalid("unexpected_answer",
            f"the register pane came back but names no CPU mode (expected one of "
            f"{', '.join(CPU_MODES)}). Without it an address is ambiguous: the same "
            f"sixteen bits are a paragraph in real mode and a selector in protected mode")
    missing = [n for n in ("CS", "EIP") if not regs.get(n)]
    if missing:
        raise Invalid("unexpected_answer",
            f"the register pane came back but carries no {' and no '.join(missing)}"
            f" (it had: {sorted(regs)}). That is a partial repaint, not a position: an "
            f"empty address would be passed on as if it were one")
    return {"cs": regs["CS"], "eip": regs["EIP"], "mode": cpu}


def parse_last_pane(text: str) -> dict[str, str]:
    """The registers of the LAST repaint only; `{}` when it is not whole."""
    head = text.rfind(PANE_HEADER)
    if head < 0:
        return {}
    pane: dict[str, str] = {}
    for name, value in REGISTER.findall(text[head:]):
        if name in pane:
            return {}
        pane[name] = value
    return pane


def offset_ceiling(mode: str) -> int:
    """The widest offset in `mode`."""
    return 0xFFFFFFFF if mode.startswith("Pr") else 0xFFFF


def check_offset(off: int, mode: str) -> int:
    """The ceiling for `mode`, or the refusal."""
    top = offset_ceiling(mode)
    if not 0 <= off <= top:
        raise Invalid("bad_argument",
            f"an offset is 0x0 to 0x{top:X} in {mode} mode; got 0x{off:X}: in real mode an "
            "offset past 0xFFFF addresses nothing")
    return top


def parse_pane_clock(text: str) -> float | None:
    found = PANE_CLOCK.findall(text)
    return float(found[-1]) if found else None


def parse_pane_cycles(text: str) -> int | None:
    found = PANE_CYCLES.findall(text)
    return int(found[-1]) if found else None


def parse_paging(text: str) -> bool | None:
    """Paging on (`PAGE`) or off (`NOPG`); None when no pane says, which is not "off"."""
    found = PAGING.findall(text)
    return None if not found else found[-1] == "PAGE"


def parse_mode(text: str) -> str | None:
    """The last CPU mode a screen reports, None if it names none."""
    found = CPU_MODE.findall(text)
    return found[-1] if found else None


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


def parse_data_view(text: str) -> list[str]:
    """The data-view rows, every match on a line."""
    return [m.group(0) for raw in text.splitlines()
            for m in DATA_ROW.finditer(raw)]


def input_line(reply: str) -> str | None:
    """The input line at the LAST prompt; None when no prompt came back."""
    at = reply.rfind(PROMPT)
    if at < 0:
        return None
    return reply[at + len(PROMPT):].strip().removesuffix("_").strip()


def at_pager(reply: str) -> bool:
    """Whether the pager marker sits under the LAST prompt."""
    at = reply.rfind(PROMPT)
    return at >= 0 and PAGER_MARK in reply[at:]
