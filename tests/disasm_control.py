"""The control `disassemble` is held to: the debugger's own code pane, line by line, off screens
a terminal session captured (`fixtures/code/`), which the channel no longer carries.

Two decoders print one instruction in two syntaxes, so text equality proves nothing. A line
agrees when both decode the same address to the same length, bytes and mnemonic, and per operand
the same signed numbers and register names. A size word on the pane's side must appear on
capstone's too (the pane omits it where a register fixes the size).

Synonyms (one instruction spelled two ways) and exceptions (lines the pane gets wrong, not
compared) were captured on real panes and judged against the Intel SDM.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

import dosbox_disasm as disasm


class PaneLine(NamedTuple):
    """One code pane line; `data` is None when the pane cut the bytes (`..`) or printed pf/na."""
    segment: str
    offset: int
    data: bytes | None
    text: str


_PANE_HEADER = re.compile(r"Code Overview(?:o+)")
_PANE_END = re.compile(r"o{4}(?:Output|Variable)")
_PANE_LINE = re.compile(
    r"^([0-9A-F]{4}):([0-9A-F]{8}) ((?:[0-9A-F]{2}|pf|na)*)(\.\.)?\s*(.*?)\s*$")


def pane_lines(screen: str) -> list[PaneLine]:
    """The code pane's lines, off the last pane painted (an earlier repaint may be partial); the
    first line follows the header rule with no line break."""
    blocks = list(_PANE_HEADER.finditer(screen))
    if not blocks:
        return []
    rest = screen[blocks[-1].end():]
    end = _PANE_END.search(rest)
    out: list[PaneLine] = []
    for raw in (rest[:end.start()] if end else rest).splitlines():
        m = _PANE_LINE.match(raw)
        if m is None:
            continue
        pairs, cut = m.group(3), m.group(4)
        whole = not cut and "pf" not in pairs and "na" not in pairs and bool(pairs)
        out.append(PaneLine(m.group(1), int(m.group(2), 16),
                            bytes.fromhex(pairs) if whole else None, m.group(5)))
    return out


_ANNOTATION = re.compile(r"\s*(?:\(\$[+-][0-9a-f]+\)|\(no jmp\)|\(down\)|\(up\))")
_VALUE_NOTE = re.compile(r"[a-z]s:\[[0-9A-F]+\]=[0-9A-F]+$")
SIZES = frozenset({"byte", "word", "dword", "qword", "fword", "tbyte"})
REGISTERS = frozenset({"al", "ah", "ax", "eax", "bl", "bh", "bx", "ebx", "cl", "ch", "cx", "ecx",
                       "dl", "dh", "dx", "edx", "si", "esi", "di", "edi", "bp", "ebp", "sp", "esp",
                       "cs", "ds", "es", "ss", "fs", "gs"})


@dataclass(frozen=True)
class Synonym:
    """One instruction spelled two ways, keyed by opcode. `implicit`: capstone prints operands
    the pane omits. `registers`: name pairs for one operand. `sizes` False: the pane's size
    word names half the operand. `pointer`: far pointer as `seg:off` vs two operands."""
    opcode: Callable[[bytes], bool]
    pane: str
    capstone: str
    met: str
    implicit: bool = False
    registers: tuple[tuple[str, str], ...] = ()
    sizes: bool = True
    pointer: bool = False


_PREFIXES = frozenset(b"\x26\x2e\x36\x3e\x64\x65\x66\x67\xf0\xf2\xf3")


def _opcode(data: bytes) -> bytes:
    """The bytes from the opcode on, legacy prefixes skipped."""
    at = 0
    while at < len(data) and data[at] in _PREFIXES:
        at += 1
    return data[at:]


def _first(byte: int) -> Callable[[bytes], bool]:
    return lambda data: _opcode(data)[:1] == bytes([byte])


def _group(byte: int, reg: int) -> Callable[[bytes], bool]:
    def match(data: bytes) -> bool:
        op = _opcode(data)
        return len(op) > 1 and op[0] == byte and (op[1] >> 3) & 7 == reg
    return match


SYNONYMS = (
    Synonym(_first(0x72), "jc", "jb", "72 20 in the code guest's data, read as code"),
    Synonym(_first(0x73), "jnc", "jae", "73 0D in dos-djgpp32's INT 31h wrapper"),
    Synonym(_first(0xAC), "lodsb", "lodsb", "AC in the code guest's and the probe's emit",
            implicit=True),
    Synonym(_first(0x6E), "outsb", "outsb", "6E in the code guest's strings", implicit=True),
    Synonym(_first(0x6F), "outsw", "outsw", "6F in the code guest's strings", implicit=True),
    Synonym(_first(0x6D), "insw", "insw", "6D in the code guest's strings", implicit=True),
    Synonym(_first(0x9A), "call", "lcall", "9A 06 00 95 08 in dos-real16's _START: the pane "
            "prints `call 0895:0006`, capstone `lcall 0x895, 6`", pointer=True),
    Synonym(_group(0xFF, 3), "call", "lcall", "FF 1E, the code guest's far call through a "
            "pointer: the pane prints `call far word`, the word being the pointer's offset half",
            sizes=False),
    Synonym(_first(0x8E), "mov", "mov", "8E C0 in dos-djgpp32's 32-bit code: MOV Sreg, r/m16, the "
            "pane naming the 16-bit register and capstone its 32-bit name",
            registers=(("ax", "eax"), ("bx", "ebx"), ("cx", "ecx"), ("dx", "edx"),
                       ("si", "esi"), ("di", "edi"), ("bp", "ebp"), ("sp", "esp"))),
    Synonym(_first(0x61), "popad", "popal", "61 in the DPMI guest's _tick (00A7:2081), 32-bit "
            "code: POPAD in the Intel SDM, capstone's AT&T-style suffix"),
)


@dataclass(frozen=True)
class PaneWrong:
    """A line the pane decodes wrongly for x86, with the reason."""
    opcode: Callable[[bytes], bool]
    why: str


EXCEPTIONS = (
    PaneWrong(_group(0xFE, 7), "FE /7 is no x86 instruction (Intel SDM, opcode map group 4); "
               "DOSBox enters its own code through FE 38 nn nn, so its pane reads any FE /7 as "
               "`callback` with a word after it"),
)


def _operands(text: str) -> list[str]:
    return [t.strip() for t in text.split(",")] if text.strip() else []


def _signed(tokens: list[tuple[str, str]], read: Callable[[str], int | None]) -> list[int]:
    """Numbers among an operand's tokens, negative after a `-`."""
    out = []
    for sign, tok in tokens:
        value = read(tok)
        if value is not None:
            out.append(-value if sign else value)
    return sorted(out)


_PANE_PART = re.compile(r"(-?)\s*([A-Za-z_$.@?][\w$.@?~]*|[0-9A-Fa-f]+)")
_CAPSTONE_PART = re.compile(r"(-?)\s*(0x[0-9a-f]+|[A-Za-z_]\w*|\d+)")

Operand = tuple[list[int], list[str], set[str]]


def _pane_view(text: str, names: dict[str, int]) -> tuple[str, list[Operand]]:
    text = _ANNOTATION.sub("", text).strip()
    text = _VALUE_NOTE.sub("", text).strip()
    mnemonic, _, operands = text.partition(" ")

    def number(tok: str) -> int | None:
        if tok in names:
            return names[tok]
        return int(tok, 16) if re.fullmatch(r"[0-9A-F]+", tok) else None

    out: list[Operand] = []
    for op in _operands(operands):
        parts = _PANE_PART.findall(op)
        out.append((_signed(parts, number), sorted(t for _s, t in parts if t in REGISTERS),
                    {t for _s, t in parts if t in SIZES}))
    return mnemonic, out


def _capstone_view(insn: disasm.Insn) -> tuple[str, list[Operand]]:
    def number(tok: str) -> int | None:
        if tok.startswith("0x"):
            return int(tok, 16)
        return int(tok) if tok.isdigit() else None

    out: list[Operand] = []
    for op in _operands(insn.operands):
        parts = _CAPSTONE_PART.findall(op)
        out.append((_signed(parts, number), sorted(t for _s, t in parts if t in REGISTERS),
                    {t for _s, t in parts if t in SIZES}))
    return insn.mnemonic, out


@dataclass
class Verdict:
    compared: int
    disagreements: list[str]
    excepted: list[str]


def compare(pane: list[PaneLine], segment: str, insns: list[disasm.Insn],
            names: dict[str, int] | None = None) -> Verdict:
    """Every pane line of `segment` against the capstone line at its address.
    `insns` is decoded from a known boundary, so a line capstone never starts disagrees.
    `names` maps a name the pane prints in an operand to its value."""
    names = names or {}
    at = {i.offset: i for i in insns}
    first, last = (insns[0].offset, insns[-1].offset) if insns else (0, -1)
    verdict = Verdict(0, [], [])
    for p in pane:
        if p.segment != segment or not first <= p.offset <= last:
            continue
        where = f"{p.segment}:{p.offset:08X}"
        raw = p.data or b""
        ins = at.get(p.offset)
        if p.data is not None and any(e.opcode(p.data) for e in EXCEPTIONS):
            verdict.excepted.append(where)
            continue
        verdict.compared += 1
        if ins is None:
            verdict.disagreements.append(f"{where}: the pane starts an instruction where "
                                         f"capstone does not ({p.text!r})")
            continue
        why = _differences(p, raw, ins, names)
        if why:
            verdict.disagreements.append(f"{where}: {'; '.join(why)} (pane {p.text!r}, "
                                         f"capstone {ins.text!r})")
    return verdict


def _differences(p: PaneLine, raw: bytes, ins: disasm.Insn,
                 names: dict[str, int]) -> list[str]:
    """Why the two lines differ; empty when they agree."""
    why = []
    if p.data is not None and len(p.data) != len(ins.data):
        why.append(f"length {len(p.data)} against {len(ins.data)}")
    if not ins.data.startswith(raw):
        why.append(f"bytes {raw.hex().upper()} against {ins.data.hex().upper()}")
    pm, pane_ops = _pane_view(p.text, names)
    cm, cap_ops = _capstone_view(ins)
    syn = next((s for s in SYNONYMS if s.opcode(ins.data) and s.pane == pm
                and s.capstone == cm), None)
    if pm != cm and syn is None:
        why.append(f"mnemonic {pm!r} against {cm!r}")
    if syn is not None and syn.implicit:
        return why
    if syn is not None and syn.pointer:
        pane_ops = [(sorted(n for o in pane_ops for n in o[0]), [], set())]
        cap_ops = [(sorted(n for o in cap_ops for n in o[0]), [], set())]
    if len(pane_ops) != len(cap_ops):
        return [*why, f"{len(pane_ops)} operands against {len(cap_ops)}"]
    swap = dict(syn.registers) if syn is not None else {}
    for n, ((pn, pr, ps), (cn, cr, cs)) in enumerate(zip(pane_ops, cap_ops, strict=True)):
        pr = sorted(swap[r] if r in swap and swap[r] in cr else r for r in pr)
        if pn != cn:
            why.append(f"operand {n + 1}: numbers {pn} against {cn}")
        if pr != cr:
            why.append(f"operand {n + 1}: registers {pr} against {cr}")
        if (syn is None or syn.sizes) and not ps <= cs:
            why.append(f"operand {n + 1}: size words {sorted(ps)} against {sorted(cs)}")
    return why
