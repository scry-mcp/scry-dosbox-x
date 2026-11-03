"""A real-mode stop cannot address memory above the first megabyte by SEG:OFF (the debugger wraps
a real-mode offset to 16 bits), and a DPMI program's data lives there: `MEMDUMPLIN` reads it by
linear address, and the program's own pointer is placed that way when no SEG:OFF can reach it."""

from __future__ import annotations

from pathlib import Path

import pytest
from channel_double import EVERY_COMMAND, REAL_STOP, Machine, protected, session_over
from scry_core.screen_map import Pointer

from scry_dosbox_x import grammar, inputs, placement
from scry_dosbox_x import pointer as dpointer
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym

#: The program's flat DS base (linear), and where `_mouse_x` sits from it, as measured on ReChip.
BASE = 0x400000
MOUSE_X = 0x1E367C


def _table(base: int, measured_from: str | None) -> None:
    dstate.STATE.table[:] = [dsym.Symbol("_mouse_x", MOUSE_X, kind="D"),
                             dsym.Symbol("_mouse_y", MOUSE_X - 4, kind="D")]
    dstate.STATE.name_index.clear()
    dstate.STATE.name_index.update(dsym.index_by_name(dstate.STATE.table))
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": base, "limit": -1, "type": -1})
    dstate.STATE.base_measured_from = measured_from


def _real(tmp_path: Path, *, with_command: bool = True) -> tuple[ds.Session, Machine]:
    commands = EVERY_COMMAND if with_command else tuple(c for c in EVERY_COMMAND
                                                         if c != "MEMDUMPLIN")
    machine = Machine(regs=dict(REAL_STOP), commands=commands)
    return session_over(machine, tmp_path), machine


def test_a_linear_read_gives_the_bytes_at_that_address_from_a_real_mode_stop(
        tmp_path: Path) -> None:
    session, machine = _real(tmp_path)
    machine.memory.update({BASE + MOUSE_X + i: v for i, v in enumerate((7, 2, 0, 0))})
    got = session.read_bytes(grammar.LINEAR, BASE + MOUSE_X, 4)
    assert got == bytes((7, 2, 0, 0)), got
    assert any(c.startswith("EXEC MEMDUMPLIN ") for c in machine.sent), machine.sent


def test_a_linear_read_on_a_build_without_the_command_says_so(tmp_path: Path) -> None:
    session, _ = _real(tmp_path, with_command=False)
    with pytest.raises(ds.Invalid, match="MEMDUMPLIN") as refused:
        session.read_bytes(grammar.LINEAR, BASE, 4)
    assert refused.value.code == "no_channel", refused.value.code


def test_the_program_s_pointer_is_placed_by_linear_address_when_no_seg_off_reaches_it(
        tmp_path: Path) -> None:
    session, _ = _real(tmp_path)
    _table(BASE, "DS")
    got = placement.pointer_target("_mouse_x", session)
    assert got == (grammar.LINEAR, BASE + MOUSE_X), got


def test_a_base_that_no_register_measured_is_not_read_by_linear_address(
        tmp_path: Path) -> None:
    """`start(symbols=)` places a table from the program's DOS load segment by passing it as a
    base, so the table records no register: it is the state this test builds, and a DPMI
    program's flat data is not there. A base the caller gave is the same state."""
    session, _ = _real(tmp_path)
    _table(0x8ED00, None)
    with pytest.raises(ds.Invalid, match="protected-mode stop"):
        placement.pointer_target("_mouse_x", session)


def test_a_linear_address_past_thirty_two_bits_keeps_the_refusal(tmp_path: Path) -> None:
    session, _ = _real(tmp_path)
    _table(0xFFFFFF00, "DS")
    with pytest.raises(ds.Invalid, match="past the first megabyte"):
        placement.pointer_target("_mouse_x", session)


def test_a_linear_read_past_thirty_two_bits_is_refused_before_anything_is_sent(
        tmp_path: Path) -> None:
    session, machine = _real(tmp_path)
    with pytest.raises(ds.Invalid, match="0xFFFFFFFF"):
        session.read_bytes(grammar.LINEAR, 1 << 32, 4)
    assert not any(c.startswith("EXEC MEMDUMPLIN") for c in machine.sent), machine.sent


def test_a_running_guest_is_refused_not_given_a_place_it_cannot_read(tmp_path: Path) -> None:
    session, machine = _real(tmp_path)
    _table(BASE, "DS")
    machine.stopped = False
    session.forget_stop()
    with pytest.raises(ds.Invalid):
        placement.pointer_target("_mouse_x", session)


def test_a_build_without_the_command_keeps_the_refusal(tmp_path: Path) -> None:
    session, _ = _real(tmp_path, with_command=False)
    _table(BASE, "DS")
    with pytest.raises(ds.Invalid, match="protected-mode stop"):
        placement.pointer_target("_mouse_x", session)


def test_a_protected_mode_stop_keeps_the_selector_and_never_goes_linear(tmp_path: Path) -> None:
    machine = protected(Machine())
    session = session_over(machine, tmp_path)
    _table(BASE, "DS")
    dstate.STATE.base.update({"selector_DS": 0xAF})
    got = placement.pointer_target("_mouse_x", session)
    assert got == (0xAF, MOUSE_X), got


def test_a_protected_mode_stop_with_no_stored_selector_reads_by_linear_address(
        tmp_path: Path) -> None:
    """A table measured at a real-mode stop (`base_from` a selector number) stores no selector,
    and a later protected-mode stop (a mouse callback, a DPMI host) holds a DS that is not the
    program's: the register's base would read another variable."""
    machine = protected(Machine())
    session = session_over(machine, tmp_path)
    _table(BASE, "00AF")
    got = placement.pointer_target("_mouse_x", session)
    assert got == (grammar.LINEAR, BASE + MOUSE_X), got


def test_an_explicit_seg_off_is_read_as_given_and_a_malformed_one_is_not_made_linear(
        tmp_path: Path) -> None:
    session, _ = _real(tmp_path)
    _table(BASE, "DS")
    assert placement.pointer_target("0814:0010", session) == (0x814, 0x10)
    with pytest.raises(ds.Invalid):
        placement.pointer_target("10000:0000", session)


def test_the_pointer_is_read_through_the_linear_place(tmp_path: Path) -> None:
    session, machine = _real(tmp_path)
    _table(BASE, "DS")
    machine.memory.update({BASE + MOUSE_X + i: v for i, v in enumerate((7, 2, 0, 0))})
    machine.memory.update({BASE + MOUSE_X - 4 + i: v for i, v in enumerate((130, 0, 0, 0))})
    declared = Pointer("_mouse_x", "_mouse_y", 4)
    places = dpointer.locate(declared, lambda ref: placement.pointer_target(ref, session))
    assert dpointer.program_at(session.read_bytes, declared, places) == (519, 130)


def test_the_pointer_is_placed_again_at_each_stop_the_steering_reads_from(tmp_path: Path) -> None:
    """A retrace stop after a nudge can be in a BIOS handler in real mode while the first stop was
    the program's: the selector placed at the first one is not an address there."""
    machine = protected(Machine())
    session = session_over(machine, tmp_path)
    _table(BASE, "DS")
    dstate.STATE.base.update({"selector_DS": 0xAF})
    machine.selinfo["DS"] = machine.selinfo["DS"]
    machine.memory.update({BASE + MOUSE_X + i: v for i, v in enumerate((7, 2, 0, 0))})
    machine.memory.update({BASE + MOUSE_X - 4 + i: v for i, v in enumerate((130, 0, 0, 0))})
    declared = Pointer("_mouse_x", "_mouse_y", 4)
    seen = inputs.program_reader(session, declared)
    machine.regs.update(REAL_STOP)
    session.forget_stop()
    assert seen() == (519, 130)
