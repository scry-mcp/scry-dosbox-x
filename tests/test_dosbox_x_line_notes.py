"""The note a disassembled line and a stop's instruction carry from the base."""

from __future__ import annotations

from typing import cast

import pytest
from dosbox_x_server_support import clean_session, install  # noqa: F401
from scry_core.knowledge.base import Base
from test_dosbox_x_code import COM_START, LOAD, StoppedCode, picture

from scry_dosbox_x import code, disasm, knowledge, line_notes
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

#: `mov ah, 4Ch` then `int 21h`, which DOS reads as EXIT.
EXIT = bytes.fromhex("B44CCD21")
REGS = {"CS": "0814", "EIP": "00000102", "EAX": "00004C00", "EDX": "000003C8"}


def _insns(raw: bytes) -> list[disasm.Insn]:
    return disasm.decode(raw, 0x100, 16)


@pytest.fixture
def ports(named_base: Base, monkeypatch: pytest.MonkeyPatch) -> None:
    """A base that holds the VGA DAC's port, which the confirmed base does not yet."""
    monkeypatch.setattr(knowledge, "base", lambda: named_base)


def test_an_interrupt_is_named_only_at_the_stop_that_holds_its_function() -> None:
    assert line_notes.of_listing(_insns(EXIT), LOAD, {}) == []
    at_int = line_notes.of_listing(_insns(EXIT), LOAD, REGS)
    assert at_int == [{"line": 1, "note": "terminate with code (0x4C)", "live": True}]


def test_the_registers_name_only_the_instruction_at_the_stop() -> None:
    elsewhere = {**REGS, "EIP": "00000100"}
    assert line_notes.of_listing(_insns(EXIT), LOAD, elsewhere) == []
    assert line_notes.of_listing(_insns(EXIT), LOAD + 1, REGS) == []


def test_with_the_names_off_no_line_has_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dstate.STATE, "names", False)
    assert line_notes.of_listing(_insns(EXIT), LOAD, REGS) == []


def test_int_43h_is_not_the_xms_driver_at_a_stop() -> None:
    insns = disasm.decode(bytes.fromhex("CD43"), 0x102, 16)
    assert line_notes.of_listing(insns, LOAD, {**REGS, "EAX": "00000800"}) == []


@pytest.mark.usefixtures("ports")
def test_a_port_an_instruction_states_is_named_on_any_line() -> None:
    out = line_notes.of_listing(_insns(bytes.fromhex("E460")), LOAD, {})
    assert out == [{"line": 0, "note": "keyboard data (0x60)"}]
    assert line_notes.of_listing(_insns(bytes.fromhex("BAC803EE")), LOAD, {}) == []


@pytest.mark.usefixtures("ports")
def test_a_port_in_dx_is_named_at_the_stop_by_direction() -> None:
    out = line_notes.of_listing(_insns(bytes.fromhex("BAC803EE")), LOAD, {**REGS,
                                                                          "EIP": "00000103"})
    assert out == [{"line": 1, "note": "dac write index (0x3C8)", "live": True}]
    read = line_notes.of_listing(_insns(bytes.fromhex("BAC803EC")), LOAD, {**REGS,
                                                                           "EIP": "00000103"})
    assert [r["note"] for r in read] == ["dac read index (0x3C8)"]


def _stopped_at(raw: bytes, eax: int) -> StoppedCode:
    s = StoppedCode("code-stop1")
    s.mem[LOAD * 16 + COM_START:LOAD * 16 + COM_START + len(raw)] = raw
    s.regs["EAX"] = f"{eax:08X}"
    s.regs["EIP"] = f"{COM_START:08X}"
    return s


def test_a_stop_at_an_interrupt_carries_its_note_and_says_a_register_named_it() -> None:
    s = _stopped_at(bytes.fromhex("CD21"), 0x4C00)
    got = picture(s)["instruction"]
    assert got["text"] == "int 0x21"
    assert got["note"] == "terminate with code (0x4C)" and got["note_live"] is True, got


def test_a_stop_with_nothing_to_name_has_no_note_field() -> None:
    got = picture(_stopped_at(bytes.fromhex("90"), 0))["instruction"]
    assert "note" not in got and "note_live" not in got, got


def test_disassemble_lists_its_notes_apart_from_its_lines() -> None:
    s = _stopped_at(bytes.fromhex("CD21"), 0x4C00)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    got = code.disassemble(cast(ds.Session, s), "0814:0100", 2)
    assert got["line_notes"] == [{"line": 0, "note": "terminate with code (0x4C)",
                                  "live": True}], got
    s2 = _stopped_at(bytes.fromhex("90CD21"), 0x4C00)
    dstate.STATE.session = cast(ds.Session, s2)
    plain = code.disassemble(cast(ds.Session, s2), "0814:0100", 3)
    assert "line_notes" not in plain, plain


def test_a_register_the_debugger_did_not_print_as_hex_is_left_out() -> None:
    assert line_notes.live_registers({"EAX": "zz", "EDX": "000003C8"}) == {"DX": 0x3C8}
    assert line_notes.of_listing(_insns(EXIT), LOAD, {"CS": "0814", "EIP": "?"}) == []
