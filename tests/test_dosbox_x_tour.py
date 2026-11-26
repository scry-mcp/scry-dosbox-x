"""The reference tour's own tail, without an emulator: when a run's transcript replaces the
committed copy the reference pages read their examples from."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from scry_core.demo import StepFailed

TOUR = Path(__file__).resolve().parents[1] / "docs" / "reference" / "tour" / "tour.py"


@pytest.fixture(scope="module")
def tour() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reference_tour", TOUR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code, argv, copies", [
    (0, ["--display", "1"], 1),
    (0, [], 1),
    (1, [], 0),
    (0, ["--transcript", "/elsewhere/t.md"], 0),
    (0, ["--display", "1", "--transcript=/elsewhere/t.md"], 0),
])
def test_only_a_run_that_passed_at_its_own_place_replaces_the_committed_transcript(
        tour: ModuleType, monkeypatch: pytest.MonkeyPatch, code: int, argv: list[str],
        copies: int) -> None:
    copied: list[tuple[Any, Any]] = []
    monkeypatch.setattr(tour.shutil, "copyfile", lambda src, dst: copied.append((src, dst)))
    assert tour.keep_transcript(code, argv) == code
    assert len(copied) == copies
    assert all(dst == tour.TRANSCRIPT for _, dst in copied)


# ------------------------------------------------ the steps that name something, on real replies

BRICKS = Path(__file__).resolve().parents[1] / "demos" / "bricks"
DOCS = Path(__file__).resolve().parents[1] / "docs"
ID = re.compile(r"ibm-pc:[a-z]+:[0-9A-Za-z/=.]+")


@pytest.fixture
def exit_stop() -> Any:
    """Bricks' own bytes, stopped on the `int 21h` of its exit with AX 4C00h."""
    from dosbox_x_server_support import install
    from test_dosbox_x_code import CodeMachine

    from scry_dosbox_x import session as ds
    from scry_dosbox_x import state as dstate
    from scry_dosbox_x import symbols as sym
    image = (BRICKS / "BRICKS.COM").read_bytes()
    exit = b"\xb8\x00\x4c\xcd\x21"
    assert image.count(exit) == 1, "BRICKS.COM no longer holds exactly one exit sequence"
    exit_at = image.find(exit)
    regs = {"EAX": "00004C00", "EBX": "0", "ECX": "0", "EDX": "0", "ESI": "0", "EDI": "0",
            "EBP": "0", "ESP": "0000FFFE", "EIP": f"{0x100 + exit_at + 3:08X}", "CS": "08DF",
            "DS": "08DF", "ES": "08DF", "FS": "0", "GS": "0", "SS": "08DF"}
    machine = CodeMachine(regs)
    start = 0x8DF * 16 + 0x100
    machine.mem[start:start + len(image)] = image
    install()
    dstate.STATE.session = cast(ds.Session, machine)
    table = "\n".join(f"{o} {k} {n}" for o, k, n in (
        line.split() for line in (BRICKS / "bricks.sym").read_text(encoding="ascii").splitlines()))
    dstate.STATE.install_table(sym.parse_nm(table))
    dstate.STATE.base.update({"base": 0x8DF0})
    return machine


def test_the_exit_listing_is_judged_on_the_game_s_own_bytes(tour: ModuleType,
                                                            exit_stop: Any) -> None:
    from scry_dosbox_x import code
    from scry_dosbox_x import session as ds
    reply = code.disassemble(cast(ds.Session, exit_stop), "main_loop", 32)
    assert "named from the registers" in tour.exit_listing(reply, None)
    reply["line_notes"] = []
    with pytest.raises(StepFailed):
        tour.exit_listing(reply, None)


def test_the_exit_listing_is_the_last_line_and_the_one_the_note_names(
        tour: ModuleType) -> None:
    """The step reads the exit from the listing's end; a note on an earlier `int 0x21`, or an
    `int 0x21` that is not the end, is not the exit this step is about."""
    note = {"line": 2, "note": "terminate with code (0x4C)", "live": True}
    lines = ["mov ax, 0x4c00", "int 0x21", "int 0x21"]
    assert "exit call's line" in tour.exit_listing({"lines": lines, "line_notes": [note]}, None)
    with pytest.raises(StepFailed):
        tour.exit_listing({"lines": lines, "line_notes": [{**note, "line": 1}]}, None)
    with pytest.raises(StepFailed):
        tour.exit_listing({"lines": ["mov ax, 0x4c00", "int 0x21", "nop"],
                           "line_notes": [note]}, None)


def test_the_stop_at_the_exit_is_judged_with_its_note(tour: ModuleType, exit_stop: Any) -> None:
    from scry_dosbox_x import code
    from scry_dosbox_x import session as ds
    where, regs, _held = exit_stop.stop_survey()
    row = code.stop_instruction(cast(ds.Session, exit_stop), where, regs)["instruction"]
    reply = {"verdict": "OTHER_STOP", "instruction": row, "regs": {"EAX": "0x00004C00"}}
    assert "names terminate with code" in tour.leaving(reply, None)
    bare = {**reply, "instruction": {k: v for k, v in row.items() if k != "note"}}
    with pytest.raises(StepFailed):
        tour.leaving(bare, None)


def test_the_tour_s_row_pens_are_the_game_s_own(tour: ModuleType) -> None:
    """The tour reads the colours `bricks.asm` writes, so a row added or dropped there reddens
    the palette and the port steps instead of failing the next live run."""
    source = (BRICKS / "bricks.asm").read_text(encoding="ascii")
    block = source.split("row_colours:", 1)[1].split("row_colours_end:", 1)[0]
    rows = [[int(value, 16) for value in line.split("db", 1)[1].split(",")]
            for line in block.splitlines() if "db" in line]
    assert [bytes(row).hex() for row in rows] == tour.ROW_RGB
    assert tour.ROW_PEN + len(rows) - 1 == tour.ROW_LAST_PEN


def test_the_base_step_is_judged_on_the_reply_the_reference_shows(tour: ModuleType) -> None:
    shown = json.loads((DOCS / "reference" / "examples.json").read_text(encoding="utf-8"))
    reply = shown["knowledge_find"]["reply"]
    entry = reply["entries"][0]
    assert tour.base_exit(reply, None).endswith(
        f"{entry['name']}, read in {entry['sources'][0]['where']}")
    with pytest.raises(StepFailed):
        tour.base_exit({**reply, "entries_total": 2}, None)


def _not_held(text: str) -> list[str]:
    """The entry ids `text` cites that the base's dictionaries do not hold, served or not."""
    from scry_dosbox_x import knowledge
    held = knowledge.base().unfiltered()
    return [cited for cited in ID.findall(text) if held.by_id(cited) is None]


def test_the_tour_and_the_reference_cite_entries_the_base_holds_only() -> None:
    seen = 0
    for path in [TOUR, *sorted(DOCS.rglob("*.json")), *sorted(DOCS.rglob("*.md")),
                 DOCS.parent / "REFERENCE.md"]:
        text = path.read_text(encoding="utf-8")
        seen += len(ID.findall(text))
        assert _not_held(text) == [], f"{path.name} cites an entry the base does not hold"
    assert seen, "INVALID: no entry id was cited, so nothing was judged"


def test_a_cited_entry_that_is_absent_fails_the_case() -> None:
    absent = "ibm-pc:call:0x21/0xFE"
    assert _not_held(f"`{absent}`, but `ibm-pc:call:0x21/0x4C` is held") == [absent]
