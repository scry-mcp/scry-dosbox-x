"""x86 decoded on the host: bytes, an address and a code size in, one line per instruction out.

The debugger has no disassembly command. Its code pane decodes what it shows (`C seg:off` moves
it), and a pane is one screen of lines with the bytes glued to the text, so a listing of any
length is decoded here, by capstone (the pinned version is `pyproject.toml`'s), from bytes
the server reads off the machine. The pane stays useful as what a decoder nobody here wrote
says about the same bytes: `tests/disasm_control.py` holds the two against each other.

What a line is for comes from the decoder's own instruction groups, never from its text: a call
(an interrupt too: it hands control to a handler the way a call does), a branch, a return, the
next instruction, or `unknown` for a byte no x86 decodes. Capstone files `loop` under relative
branches and not under jumps, so a relative branch that is not a call is a branch too.

And the operands a name can be claimed for, from the decoder's operand details as well: a direct
branch or call target (an immediate), and a direct memory operand (no base, no index register).
A register-relative address is the register's at run time, and nothing here guesses it.

One module imports capstone, this one, and nothing it returns is capstone's: the rest of the
package sees `Insn`.
"""

from __future__ import annotations

import dataclasses

import capstone  # type: ignore[import-untyped]

#: The longest x86 instruction: what is read past a listing's end so the last one completes.
INSN_MAX = 15
#: What names the decoder in a reply's `flow_source`.
SOURCE = "capstone"
#: What a line is for.
CALL, BRANCH, RETURN, SEQUENTIAL, UNKNOWN = "call", "branch", "return", "sequential", "unknown"
#: The bytes column of a line, wide enough for most instructions and never cut.
BYTES_COLUMN = 20

_MODES = {16: capstone.CS_MODE_16, 32: capstone.CS_MODE_32}


@dataclasses.dataclass(frozen=True)
class Target:
    """A direct branch or call target: the operand's text, its offset, and the segment a far
    pointer names (None for a near target, which stays in the line's own segment)."""
    operand: str
    offset: int
    far_segment: int | None


@dataclasses.dataclass(frozen=True)
class Memory:
    """A direct memory operand: its text, its offset in its segment, and the segment register it
    is read through (an override prefix, else DS)."""
    operand: str
    offset: int
    segment_register: str


@dataclasses.dataclass(frozen=True)
class Insn:
    """One decoded instruction, or one byte no instruction starts with (`flow` `unknown`)."""
    offset: int
    data: bytes
    mnemonic: str
    operands: str
    flow: str
    targets: tuple[Target, ...] = ()
    memory: tuple[Memory, ...] = ()

    @property
    def text(self) -> str:
        """The instruction as capstone prints it, mnemonic and operands."""
        return f"{self.mnemonic} {self.operands}".rstrip()

    def line(self, segment: int) -> str:
        """`SSSS:OOOOOOOO BYTES TEXT`, the pane's own address spelling."""
        return (f"{segment:04X}:{self.offset:08X} {self.data.hex().upper():<{BYTES_COLUMN}} "
                f"{self.text}").rstrip()


def _decoder(bits: int) -> capstone.Cs:
    if bits not in _MODES:
        raise ValueError(f"a code size is 16 or 32 bits; got {bits}")
    md = capstone.Cs(capstone.CS_ARCH_X86, _MODES[bits])
    md.detail = True
    md.skipdata = True                     # a byte nothing decodes is a line, then go on
    return md


def _flow(groups: set[int]) -> str:
    if groups & {capstone.CS_GRP_CALL, capstone.CS_GRP_INT}:
        return CALL
    if groups & {capstone.CS_GRP_RET, capstone.CS_GRP_IRET}:
        return RETURN
    if groups & {capstone.CS_GRP_JUMP, capstone.CS_GRP_BRANCH_RELATIVE}:
        return BRANCH
    return SEQUENTIAL


def _operand_texts(insn: capstone.CsInsn) -> list[str]:
    """Each operand's own text, capstone's operand string split at its commas (no x86 operand
    holds one), or the whole string for each when the split does not give one text per operand
    (a far pointer prints its two immediates as one `seg:off`)."""
    texts = [t.strip() for t in insn.op_str.split(",")] if insn.op_str else []
    return texts if len(texts) == len(insn.operands) else [insn.op_str] * len(insn.operands)


def _width(size: int) -> int:
    """The mask of a value `size` bytes wide."""
    return (1 << (8 * size)) - 1


def _facts(insn: capstone.CsInsn, flow: str) -> tuple[tuple[Target, ...], tuple[Memory, ...]]:
    """A target is as wide as its operand (an IP of 16 bits wraps inside its segment, 66h widens
    it); a displacement as wide as the address (capstone hands a 16-bit one back sign-extended,
    and offset 8004 is not -7FFC)."""
    texts = _operand_texts(insn)
    ops = list(insn.operands)
    targets: list[Target] = []
    memory: list[Memory] = []
    if flow in (CALL, BRANCH) and not insn.group(capstone.CS_GRP_INT):
        imms = [o for o in ops if o.type == capstone.x86.X86_OP_IMM]
        if len(imms) == 2:                 # ptr16:16 or ptr16:32, segment first
            targets.append(Target(insn.op_str, imms[1].imm & _width(imms[1].size),
                                  imms[0].imm & 0xFFFF))
        elif len(imms) == 1:
            targets.append(Target(texts[ops.index(imms[0])], imms[0].imm & _width(imms[0].size),
                                  None))
    for text, o in zip(texts, ops, strict=True):
        if o.type == capstone.x86.X86_OP_MEM and o.mem.base == 0 and o.mem.index == 0:
            register = insn.reg_name(o.mem.segment) if o.mem.segment else "ds"
            memory.append(Memory(text, o.mem.disp & _width(insn.addr_size), register.upper()))
    return tuple(targets), tuple(memory)


def _masked_branch_text(insn: capstone.CsInsn) -> str:
    """Capstone adds a relative branch to the address without wrapping it, and a 16-bit IP
    does wrap: the target is printed inside the segment, as the CPU goes there."""
    if not insn.group(capstone.CS_GRP_BRANCH_RELATIVE):
        return str(insn.op_str)
    imm, mask = insn.operands[0].imm, _width(insn.operands[0].size)
    return str(insn.op_str).replace(hex(imm), hex(imm & mask)) if imm != imm & mask else \
        str(insn.op_str)


def decode(code: bytes, offset: int, bits: int, length: int | None = None) -> list[Insn]:
    """The instructions in `code`, which starts at `offset`, decoded `bits` wide. With `length`,
    only those that start inside the first `length` bytes: the last may run past them, into
    the extra the caller read for it. A byte nothing decodes is a line of its own, `unknown`,
    and decoding resumes at the next byte."""
    end = offset + (len(code) if length is None else length)
    out: list[Insn] = []
    for insn in _decoder(bits).disasm(code, offset):
        if insn.address >= end:
            break
        if insn.id == 0:                   # skipdata: no instruction starts here
            out.append(Insn(insn.address, bytes(insn.bytes), insn.mnemonic, insn.op_str,
                            UNKNOWN))
            continue
        flow = _flow(set(insn.groups))
        targets, memory = _facts(insn, flow)
        out.append(Insn(insn.address, bytes(insn.bytes), insn.mnemonic,
                        _masked_branch_text(insn), flow, targets, memory))
    return out


def one(code: bytes, offset: int, bits: int) -> Insn | None:
    """The single instruction `code` is, or None when it is not exactly one decodable
    instruction: shorter, longer, or a byte nothing decodes."""
    got = decode(code, offset, bits)
    if len(got) != 1 or got[0].flow == UNKNOWN or len(got[0].data) != len(code):
        return None
    return got[0]
