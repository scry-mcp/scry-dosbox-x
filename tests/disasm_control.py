"""The control `disassemble` is held to: the debugger's own code pane, line by line.

Two decoders print one instruction in two syntaxes, so text equality proves nothing. A line
agrees when both start an instruction at the same address, of the same length (where the pane
printed all its bytes), with the same bytes as far as the pane printed them, the same mnemonic,
and operand by operand in order the same signed numbers and register names, with no size word on
the pane's side that capstone's lacks (the pane leaves one out where a register already fixes the
size; capstone always prints it). The pane's own annotations are dropped first: `($+n)`,
`($-n)`, `(no jmp)`, `(down)`, `(up)` and the `ds:[015A]=3030` note of what an operand holds now.

The synonyms and the exceptions were captured, not authored: each is a disagreement met on a real
pane (the package's guests, dos-real16, dos-djgpp32), kept with the opcode it was met on and judged
against the Intel SDM. A synonym is one instruction spelled two ways; an exception is a line the
pane gets wrong about x86 and is not compared.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import dosbox_code as code
import dosbox_disasm as disasm

_ANNOTATION = re.compile(r"\s*(?:\(\$[+-][0-9a-f]+\)|\(no jmp\)|\(down\)|\(up\))")
_VALUE_NOTE = re.compile(r"[a-z]s:\[[0-9A-F]+\]=[0-9A-F]+$")
SIZES = frozenset({"byte", "word", "dword", "qword", "fword", "tbyte"})
REGISTERS = frozenset({"al", "ah", "ax", "eax", "bl", "bh", "bx", "ebx", "cl", "ch", "cx", "ecx",
                       "dl", "dh", "dx", "edx", "si", "esi", "di", "edi", "bp", "ebp", "sp", "esp",
                       "cs", "ds", "es", "ss", "fs", "gs"})


@dataclass(frozen=True)
class Synonym:
    """One instruction the two decoders spell differently, keyed by its opcode: `pane` and
    `capstone` are the mnemonics each prints; `implicit` says capstone also prints the operands
    the opcode implies, which the pane leaves out, so operands are not compared; `registers`
    pairs a register name each side prints for the same operand; `sizes` says the pane's size
    word names half of the operand, so sizes are not compared; `pointer` says one side prints a
    far pointer as `seg:off` and the other as two operands, so its numbers are compared whole."""
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
    """The instruction's bytes from its opcode on, its legacy prefixes skipped."""
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
    """A line the pane decodes wrongly for x86, with the reason; its bytes are not compared."""
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
    """The numbers among one operand's tokens, each negative when a `-` stands before it."""
    out = []
    for sign, tok in tokens:
        value = read(tok)
        if value is not None:
            out.append(-value if sign else value)
    return sorted(out)


_PANE_PART = re.compile(r"(-?)\s*([A-Za-z_$.@?][\w$.@?~]*|[0-9A-Fa-f]+)")
_CAPSTONE_PART = re.compile(r"(-?)\s*(0x[0-9a-f]+|[A-Za-z_]\w*|\d+)")

#: One operand as compared: its numbers (signed), its register names, its size words.
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
    """What a comparison examined and what it found: `compared` lines agreed or not,
    `disagreements` one sentence each, `excepted` the lines an exception took out."""
    compared: int
    disagreements: list[str]
    excepted: list[str]


def compare(pane: list[code.PaneLine], segment: str, insns: list[disasm.Insn],
            names: dict[str, int] | None = None) -> Verdict:
    """Every pane line of `segment` against the capstone line that starts at its address.
    `insns` is capstone's own listing over the bytes, decoded from a known instruction
    boundary, so a line capstone never starts is a disagreement and not a fresh decode.
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


def _differences(p: code.PaneLine, raw: bytes, ins: disasm.Insn,
                 names: dict[str, int]) -> list[str]:
    """Why a pane line and capstone's line at its address are not one instruction, operand by
    operand in order; empty when they agree."""
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
