"""What a number is called on this machine: the namer `scry_core.naming` asks. It reads only the
loaded base and the symbol table, never the emulator, because it runs under the call's lock."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scry_core import naming
from scry_core.knowledge import Base, KeyFault
from scry_core.knowledge import keys as keyspelling
from scry_core.naming import Field, Named

from scry_dosbox_x import declarations as dec
from scry_dosbox_x import knowledge
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

#: The XMS driver's key borrows its multiplex number, and it is called far: INT 43h is no call.
XMS_KEY = 0x43
#: The tools whose `ref` may be a symbol.
ADDRESS_TOOLS = frozenset({"read_memory", "memdump", "write", "disassemble", "find", "scan",
                           "breakpoint_at", "watch_add", "run_to", "comment_write"})
#: Numbers the replies of a tool show, by the path of their field, and how a reply spells them.
NUMBER_FIELDS: dict[str, tuple[Field, ...]] = {
    "port": (Field("port", "port"),),
    "interrupt_vectors": (Field("vectors[].number", "vector"),),
}
_WIDTH = {"port": 4, "vector": 2}


def number_of(value: object) -> int | None:
    """`value` as a whole number when it is one: an integer, or `0x` hex as a reply prints it."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def interrupt_call(base: Base, interrupt: int, registers: Mapping[str, int]) -> Named | None:
    if interrupt == XMS_KEY:
        return None
    try:
        return naming.named_call(base, knowledge.SCOPE, interrupt, registers)
    except KeyFault:
        return None


def _symbol(ref: str) -> Named | None:
    """A symbol typed as a ref, with the address the loaded table places it at; a table of
    sections, a name the table gives twice and one it lacks name nothing."""
    if not ref.strip() or not STATE.table or STATE.section_bases or STATE.base.get("base", -1) < 0:
        return None
    found = dec.DeclarationStore.resolve_name(dec.Declaration("breakpoint", "symbol", ref),
                                              STATE.table, STATE.name_index)
    if found.state == "unresolved" or found.matches != 1 or found.offset is None:
        return None
    return Named("symbol", ref.strip(), st.flat(STATE.base["base"] + found.offset))


class DosboxNamer:
    """Per argument and per reply field, what a number is called in the confirmed base."""

    def __init__(self, base: Base) -> None:
        self._base = base

    def _entry(self, kind: str, value: int, access: str = "") -> Named | None:
        try:
            key = keyspelling.canonical(kind, f"0x{value:X}")
        except KeyFault:
            return None
        found = (self._base.get(kind, key, knowledge.SCOPE, access) if access else None) \
            or self._base.get(kind, key, knowledge.SCOPE)
        if found is None:
            return None
        return Named(kind, found.name, f"0x{value:0{_WIDTH.get(kind, 2)}X}", id=found.id)

    def arguments(self, tool: str, given: Mapping[str, Any]) -> Mapping[str, Named]:
        out: dict[str, Named] = {}
        if tool == "breakpoint_interrupt":
            number, ah = number_of(given.get("number")), number_of(given.get("ah"))
            if number is not None and ah is not None and (
                    call := interrupt_call(self._base, number, {"AH": ah})) is not None:
                out["number"] = call
        elif tool == "port":
            port = number_of(given.get("port"))
            access = {"read": "read", "write": "write"}.get(str(given.get("method")), "")
            if port is not None and (named := self._entry("port", port, access)) is not None:
                out["port"] = named
        ref = given.get("ref")
        if tool in ADDRESS_TOOLS and isinstance(ref, str) and (named := _symbol(ref)) is not None:
            out["ref"] = named
        return out

    def reply(self, tool: str, reply: Mapping[str, Any]) -> Sequence[tuple[str, Named]]:
        out: list[tuple[str, Named]] = []
        access = ("write" if "readback" in reply else "read") if tool == "port" else ""
        for seen in naming.walk(reply, NUMBER_FIELDS.get(tool, ())):
            value = number_of(seen.value)
            if value is not None and (
                    named := self._entry(seen.field.kind, value, access)) is not None:
                out.append((seen.path, named))
        return out


NAMER = DosboxNamer(knowledge.base())
#: The namer as the boundary holds it: a failure gives no names and is counted for `status`.
GUARD = naming.Guarded(NAMER)
