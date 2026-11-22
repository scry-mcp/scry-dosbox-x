"""The note a disassembled line carries from the base, apart from a person's comments. What an
instruction states outright is named on any line; what a register holds (`in al, dx`, the AH of an
`int 21h`) only for the instruction at the stop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scry_core import notes

from scry_dosbox_x import disasm, knowledge, naming
from scry_dosbox_x.state import STATE

#: The registers a call's function and a port are read from, by the debugger's names for them.
WORDS = ("AX", "BX", "CX", "DX", "SI", "DI")


def _hex(text: str | None) -> int | None:
    """A register as the debugger prints it, bare hex digits."""
    try:
        return None if text is None else int(text, 16)
    except ValueError:
        return None


def live_registers(regs: Mapping[str, str]) -> dict[str, int]:
    """The stop's word registers by upper-case name, from its `E` registers."""
    out: dict[str, int] = {}
    for word in WORDS:
        value = _hex(regs.get(f"E{word}"))
        if value is not None:
            out[word] = value & 0xFFFF
    return out


def operands(insn: disasm.Insn, registers: Mapping[str, int] | None) -> list[notes.Operand]:
    """What `insn` refers to; `registers` are the stop's, given only for the instruction there."""
    parts = [p.strip() for p in insn.operands.split(",")]
    if insn.mnemonic == "int" and len(parts) == 1 and (n := naming.number_of(parts[0])) is not None:
        if registers is None or n == naming.XMS_KEY:
            return [notes.Operand("interrupt", n)]
        return [notes.Operand("interrupt", n, live=True, registers=registers)]
    if insn.mnemonic in ("in", "out") and len(parts) == 2:
        access: notes.Access = "read" if insn.mnemonic == "in" else "write"
        text = parts[1] if insn.mnemonic == "in" else parts[0]
        if (port := naming.number_of(text)) is not None:
            return [notes.Operand("port", port, access)]
        if text == "dx" and registers is not None and "DX" in registers:
            return [notes.Operand("port", registers["DX"], access, live=True)]
    return []


def of_insn(insn: disasm.Insn, registers: Mapping[str, int] | None = None) -> notes.Note | None:
    """The base's note for `insn`, or None when it names nothing or the `names` switch is off."""
    return notes.note(knowledge.base(), knowledge.SCOPE, operands(insn, registers),
                      names_on=STATE.names)


def on_instruction(row: dict[str, Any], insn: disasm.Insn, regs: Mapping[str, str]) -> None:
    """The stop's `instruction` row gains its `note`, and `note_live` when registers named it."""
    if (found := of_insn(insn, live_registers(regs))) is not None:
        row["note"] = found.text
        if found.live:
            row["note_live"] = True


def of_listing(insns: Sequence[disasm.Insn], seg: int,
               regs: Mapping[str, str]) -> list[dict[str, Any]]:
    """`{line, note}` for each line of a listing the base names; `live` where registers did."""
    at = (_hex(regs.get("CS")), _hex(regs.get("EIP")))
    held = live_registers(regs)
    out: list[dict[str, Any]] = []
    for i, insn in enumerate(insns):
        if (found := of_insn(insn, held if (seg, insn.offset) == at else None)) is not None:
            out.append({"line": i, "note": found.text, **({"live": True} if found.live else {})})
    return out
