"""Freeze watches through the debugger's `FM`, which pins one byte at its value: after every
instruction the heavy debugger finds the byte changed and writes the value back
(`docs/reference/declarations.md`). One `FM` per byte, each a row of the breakpoint list."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scry_core import cancel
from scry_core.reply_contract import Invalid

import dosbox_binary as binaries
import dosbox_declarations as dec
import dosbox_session as ds
import dosbox_taps as taps
from dosbox_state import STATE

FM = "FM"
_SET = re.compile(r"^DEBUG: Set memory freeze at ([0-9A-F]{4}):([0-9A-F]{4,8}) with value: "
                  r"([0-9A-F]{2})$")
#: `BPLIST` prints a freeze by its offset alone, its segment dropped.
_ROW = re.compile(r"^FM ([0-9A-F]{8}) \(([0-9A-F]{2})\)$")
NOT_HELD_WHY = ("the bytes are not the frozen ones at this stop: the emulator writes a frozen byte "
                "back after each instruction the heavy debugger steps, so a dynamic core, or a "
                "write that is no instruction's (DMA), runs past it")


@dataclass
class Freeze:
    """The bytes a freeze watch pinned: where, at which values, and the rows that hold them."""
    seg: int
    off: int
    values: bytes
    entries: list[str]


def _held_rows(held: list[dict[str, str]]) -> list[dict[str, str]]:
    return [b for b in held if _ROW.match(b["entry"])]


def arm(session: ds.Session, decl: dec.Declaration) -> Freeze:
    """Freeze every byte of `decl`'s place at its value now, read back off the list."""
    if not binaries.heavy_debug(session.launch.binary):
        raise Invalid("no_channel", "a freeze watch needs a build with the heavy debugger "
                      "(`build_check`'s `heavy_debug`): only its per-instruction path writes a "
                      "frozen byte back")
    session.require_stopped("a freeze watch")
    seg, off = taps.place(decl, session)
    width = int(decl.width or 1)
    offsets = {off + i for i in range(width)}
    held = {int(m.group(1), 16): b["entry"] for b in _held_rows(session.breakpoints())
            if (m := _ROW.match(b["entry"])) is not None}
    if clash := sorted(offsets & held.keys()):
        owner = next((r for r, f in STATE.freezes.items()
                      if held[clash[0]] in f.entries), None)
        raise Invalid("ambiguous_ref", f"offset 0x{clash[0]:X} is already frozen ("
                      + (f"by the freeze {owner!r}" if owner else
                         f"`{held[clash[0]]}`, which no declaration owns")
                      + "), and the debugger lists a freeze by its offset alone: the two could "
                      "not be told apart. "
                      + ("Clear that freeze first" if owner else
                         "Remove its row with `debug` (`BPLIST`, then `BPDEL <n>`)"))
    session.altered = True
    freeze = Freeze(seg, off, b"", [])
    # Kept as it grows, so a failure half-way removes the rows already armed.
    STATE.freezes[decl.ref] = freeze
    try:
        for i in range(width):
            command = f"{FM} {seg:04X}:{off + i:X}"
            ok, lines = session.exec(command)
            found = next((m for line in lines if (m := _SET.match(line))), None)
            if not ok or found is None:
                raise Invalid("unexpected_answer", f"`{command}` answered "
                              f"{' / '.join(lines) or 'nothing'}, not that it froze the byte; the "
                              "bytes frozen before it were taken out")
            value = int(found.group(3), 16)
            freeze.values += bytes([value])
            freeze.entries.append(f"FM {off + i:08X} ({value:02X})")
        # The value `FM` echoes is uninitialised when a paged protected-mode fault hit the read.
        held_now = session.read_bytes(seg, off, width)
        if held_now != freeze.values:
            raise Invalid("readback_refused",
                          f"`{FM}` echoed {freeze.values.hex()} for the bytes at "
                          f"{seg:04X}:{off:X}, and reading them gives {held_now.hex()}: the "
                          "debugger did not read what it froze, so nothing is armed or stored")
        entries = freeze.entries
        listed = {b["entry"] for b in session.breakpoints()}
        if missing := [e for e in entries if e not in listed]:
            raise Invalid("readback_refused",
                          f"the debugger does not list {', '.join(missing)} after freezing: "
                          "nothing is armed or stored")
    except BaseException:
        with cancel.shielded():
            drop(session, decl.ref)
        raise
    return freeze


def remove(session: ds.Session, ref: str) -> list[str]:
    """Each row of the freeze under `ref` deleted and read back; the rows it removed."""
    freeze = STATE.freezes.get(ref)
    if freeze is None:
        return []
    picks: list[Callable[[str], bool]] = [
        lambda e, want=entry: e == want for entry in freeze.entries]  # type: ignore[misc]
    gone = session.delete_rows(picks)
    kept = [e for e, (row, absent) in zip(freeze.entries, gone, strict=True)
            if row is not None and not absent]
    if kept:
        raise Invalid("unexpected_answer", f"{', '.join(kept)} still listed after `BPDEL`")
    STATE.freezes.pop(ref)
    return [e for e, (row, _a) in zip(freeze.entries, gone, strict=True) if row is not None]


def drop(session: ds.Session, ref: str) -> None:
    """The freeze under `ref` taken out and forgotten whatever the debugger answers."""
    try:
        remove(session, ref)
    except Invalid:
        STATE.freezes.pop(ref, None)


def installed(session: ds.Session, ref: str, held: list[dict[str, str]] | None = None) -> bool:
    freeze = STATE.freezes.get(ref)
    if freeze is None:
        return False
    listed = {b["entry"] for b in (held if held is not None else session.breakpoints())}
    return all(e in listed for e in freeze.entries)


def evaluate(session: ds.Session, decl: dec.Declaration, held: list[dict[str, str]],
             mode: str | None) -> dict[str, Any]:
    """What a stop or a listing says of the freeze under `decl`: whether its rows are listed
    and whether the bytes are still the frozen ones."""
    freeze = STATE.freezes.get(decl.ref)
    if freeze is None:
        return {"state": "unarmed",
                "why": "no freeze is armed for this declaration in this session: a freeze is "
                       "armed when declared on a stopped machine, and never again by itself"}
    item: dict[str, Any] = {"addr": f"{freeze.seg:04X}:{freeze.off:08X}",
                            "frozen_hex": freeze.values.hex(), "entries": list(freeze.entries)}
    if not installed(session, decl.ref, held):
        return {**item, "state": "gone", "why": "the debugger no longer lists every row of this "
                "freeze: something deleted one"}
    now = session.read_bytes(freeze.seg, freeze.off, len(freeze.values), mode=mode)
    item["bytes"] = now.hex()
    if now != freeze.values:
        return {**item, "state": "not_held", "why": NOT_HELD_WHY}
    return {**item, "state": "holding"}
