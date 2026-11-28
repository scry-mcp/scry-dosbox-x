"""The note a disassembled line and a stop's instruction carry from the base."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _names, clean_session, install  # noqa: F401
from scry_core.knowledge.base import Base
from test_dosbox_x_code import COM_START, LOAD, StoppedCode, picture

from scry_dosbox_x import code, disasm, knowledge, line_notes, server
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
    assert line_notes.of_listing(_insns(EXIT), LOAD, {}) == [
        {"line": 1, "note": "DOS function calls (0x21)"}]
    at_int = line_notes.of_listing(_insns(EXIT), LOAD, REGS)
    assert at_int == [{"line": 1,
                       "note": "DOS function calls (0x21); terminate with code (0x4C)",
                       "live": True}]


def test_the_registers_name_only_the_instruction_at_the_stop() -> None:
    elsewhere = {**REGS, "EIP": "00000100"}
    assert line_notes.of_listing(_insns(EXIT), LOAD, elsewhere) == [
        {"line": 1, "note": "DOS function calls (0x21)"}]
    assert line_notes.of_listing(_insns(EXIT), LOAD + 1, REGS) == [
        {"line": 1, "note": "DOS function calls (0x21)"}]


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
    assert (got["note"] == "DOS function calls (0x21); terminate with code (0x4C)"
            and got["note_live"] is True), got


def test_a_stop_with_nothing_to_name_has_no_note_field() -> None:
    got = picture(_stopped_at(bytes.fromhex("90"), 0))["instruction"]
    assert "note" not in got and "note_live" not in got, got


def test_a_live_note_reaches_the_stop_model_through_the_reply_guard(tmp_path: Path) -> None:
    """`stop` builds this reply through the boundary, so `reply_shapes_guard` judges it against
    the published `stop` model: dropping `note_live` from the shared instruction leaves an extra
    key the model refuses, where a hand-built picture would stay green."""
    fake: Any = _names(tmp_path)
    fake.cs, fake.eip = "0814", "00000102"
    fake.mem[(0x0814, 0x102)] = bytes.fromhex("CD21")
    fake.registers = lambda: {"CS": fake.cs, "DS": fake.ds, "EIP": fake.eip,
                              "EAX": "00004C00"}
    fake.running = True
    got = server.stop()
    assert got["instruction"]["note"] == ("DOS function calls (0x21); terminate with code "
                                          "(0x4C)"), got["instruction"]
    assert got["instruction"]["note_live"] is True, got["instruction"]


def test_disassemble_lists_its_notes_apart_from_its_lines() -> None:
    s = _stopped_at(bytes.fromhex("CD21"), 0x4C00)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    got = code.disassemble(cast(ds.Session, s), "0814:0100", 2)
    assert got["line_notes"] == [{"line": 0,
                                  "note": "DOS function calls (0x21); terminate with code (0x4C)",
                                  "live": True}], got
    s2 = _stopped_at(bytes.fromhex("90CD21"), 0x4C00)
    dstate.STATE.session = cast(ds.Session, s2)
    plain = code.disassemble(cast(ds.Session, s2), "0814:0100", 3)
    assert plain["line_notes"] == [{"line": 1, "note": "DOS function calls (0x21)"}], plain


def test_the_three_calls_answer_the_shape_a_line_note_carries() -> None:
    """`disassemble`, a stop and a trace answer the note shape both servers share: `line` and
    `note`, `live`/`note_live` only when a register named it, and no entry id."""
    live = _stopped_at(bytes.fromhex("CD21"), 0x4C00)
    install()
    dstate.STATE.session = cast(ds.Session, live)
    listed = code.disassemble(cast(ds.Session, live), "0814:0100", 2)["line_notes"]
    assert [set(entry) for entry in listed] == [{"line", "note", "live"}]
    assert listed[0]["live"] is True and isinstance(listed[0]["line"], int)
    plain = _stopped_at(bytes.fromhex("90CD21"), 0x4C00)
    dstate.STATE.session = cast(ds.Session, plain)
    stated = code.disassemble(cast(ds.Session, plain), "0814:0100", 3)["line_notes"]
    assert [set(entry) for entry in stated] == [{"line", "note"}]
    stopped = picture(live)["instruction"]
    assert set(stopped) & {"note", "note_live", "live", "id"} == {"note", "note_live"}
    assert picture(_stopped_at(bytes.fromhex("90"), 0))["instruction"].keys() & {
        "note", "note_live", "live", "id"} == set()
    from typing import get_type_hints

    from scry_dosbox_x import replies
    assert (get_type_hints(replies.TraceReply)["instruction"]
            is get_type_hints(replies.StopReply)["instruction"])


def _strings(value: Any) -> list[str]:
    """Every string `value` holds, its keys included."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in [key, *_strings(item)]]
    if isinstance(value, list | tuple):
        return [text for item in value for text in _strings(item)]
    return []


def test_no_reply_cuts_the_bases_text() -> None:
    """No `…` on a row, a note or a description, and a cut list says how many it holds."""
    from scry_dosbox_x import server

    base = knowledge.base()
    held = next((whole for whole in map(base.whole, base.entries()) if "rows_total" in whole),
                None)
    assert held is not None, "no entry answered with rows cut: this case examines nothing"
    shown = server.knowledge_find(id=held["id"])
    assert shown["status"] == "ok", shown
    rows = shown["entries"][0]
    assert (len(rows["rows"]) < rows["rows_total"] == held["rows_total"]), rows
    cut = server.knowledge_find(text="the", limit=1)
    assert cut["truncated"] is True and cut["entries_total"] > len(cut["entries"]), cut
    live = _stopped_at(bytes.fromhex("CD21"), 0x4C00)
    install()
    dstate.STATE.session = cast(ds.Session, live)
    listing = code.disassemble(cast(ds.Session, live), "0814:0100", 2)
    texts = [*_strings(shown), *_strings(cut), *_strings(listing), *_strings(picture(live))]
    assert len(texts) > 20, "the replies carried almost no text, so this case examined nothing"
    assert [text for text in texts if "…" in text] == []


def test_a_register_the_debugger_did_not_print_as_hex_is_left_out() -> None:
    assert line_notes.live_registers({"EAX": "zz", "EDX": "000003C8"}) == {"DX": 0x3C8}
    assert line_notes.of_listing(_insns(EXIT), LOAD, {"CS": "0814", "EIP": "?"}) == [
        {"line": 1, "note": "DOS function calls (0x21)"}]
