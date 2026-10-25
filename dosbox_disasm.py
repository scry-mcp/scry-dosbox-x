"""x86 decoded on the host with capstone: bytes, an address and a code size in, `Insn` out.

Flow comes from the decoder's instruction groups, never its text. Targets and memory operands
are claimed only when direct: a register-relative address is not guessed. The only module that
imports capstone.
"""

from __future__ import annotations

import dataclasses

import capstone  # type: ignore[import-untyped]

#: Read past a listing's end so the last instruction completes.
INSN_MAX = 15
SOURCE = "capstone"
CALL, BRANCH, RETURN, SEQUENTIAL, UNKNOWN = "call", "branch", "return", "sequential", "unknown"
BYTES_COLUMN = 20

_MODES = {16: capstone.CS_MODE_16, 32: capstone.CS_MODE_32}


@dataclasses.dataclass(frozen=True)
class Target:
    """A direct branch or call target; `far_segment` is None for a near one."""
    operand: str
    offset: int
    far_segment: int | None


@dataclasses.dataclass(frozen=True)
class Memory:
    """A direct memory operand and the segment register it goes through (override, else DS)."""
    operand: str
    offset: int
    segment_register: str


@dataclasses.dataclass(frozen=True)
class Insn:
    """One decoded instruction, or a byte nothing decodes (`flow` `unknown`)."""
    offset: int
    data: bytes
    mnemonic: str
    operands: str
    flow: str
    targets: tuple[Target, ...] = ()
    memory: tuple[Memory, ...] = ()

    @property
    def text(self) -> str:
        """Mnemonic and operands as capstone prints them."""
        return f"{self.mnemonic} {self.operands}".rstrip()

    def line(self, segment: int) -> str:
        """`SSSS:OOOOOOOO BYTES TEXT`, the debugger's own address spelling."""
        return (f"{segment:04X}:{self.offset:08X} {self.data.hex().upper():<{BYTES_COLUMN}} "
                f"{self.text}").rstrip()


def _decoder(bits: int) -> capstone.Cs:
    if bits not in _MODES:
        raise ValueError(f"a code size is 16 or 32 bits; got {bits}")
    md = capstone.Cs(capstone.CS_ARCH_X86, _MODES[bits])
    md.detail = True
    md.skipdata = True
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
    """Each operand's text; a far pointer is one `seg:off` string for its two immediates."""
    texts = [t.strip() for t in insn.op_str.split(",")] if insn.op_str else []
    return texts if len(texts) == len(insn.operands) else [insn.op_str] * len(insn.operands)


def _width(size: int) -> int:
    return (1 << (8 * size)) - 1


def _facts(insn: capstone.CsInsn, flow: str) -> tuple[tuple[Target, ...], tuple[Memory, ...]]:
    """Capstone hands a 16-bit displacement back sign-extended, so it is masked."""
    texts = _operand_texts(insn)
    ops = list(insn.operands)
    targets: list[Target] = []
    memory: list[Memory] = []
    if flow in (CALL, BRANCH) and not insn.group(capstone.CS_GRP_INT):
        imms = [o for o in ops if o.type == capstone.x86.X86_OP_IMM]
        if len(imms) == 2:                 # far pointer, segment first
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
    """Capstone does not wrap a relative target at 16 bits; the CPU does."""
    if not insn.group(capstone.CS_GRP_BRANCH_RELATIVE):
        return str(insn.op_str)
    imm, mask = insn.operands[0].imm, _width(insn.operands[0].size)
    return str(insn.op_str).replace(hex(imm), hex(imm & mask)) if imm != imm & mask else \
        str(insn.op_str)


def decode(code: bytes, offset: int, bits: int, length: int | None = None) -> list[Insn]:
    """Decode `code`; with `length`, keep only instructions starting inside it."""
    end = offset + (len(code) if length is None else length)
    out: list[Insn] = []
    for insn in _decoder(bits).disasm(code, offset):
        if insn.address >= end:
            break
        if insn.id == 0:                   # skipdata
            out.append(Insn(insn.address, bytes(insn.bytes), insn.mnemonic, insn.op_str,
                            UNKNOWN))
            continue
        flow = _flow(set(insn.groups))
        targets, memory = _facts(insn, flow)
        out.append(Insn(insn.address, bytes(insn.bytes), insn.mnemonic,
                        _masked_branch_text(insn), flow, targets, memory))
    return out


def one(code: bytes, offset: int, bits: int) -> Insn | None:
    """The one instruction `code` is, or None if it is not exactly one decodable instruction."""
    got = decode(code, offset, bits)
    if len(got) != 1 or got[0].flow == UNKNOWN or len(got[0].data) != len(code):
        return None
    return got[0]
