"""`start(symbols=)`: the table judged at `start` and placed at the program's load segment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import dosbox_machine
import dosbox_placement
import dosbox_session as ds
import dosbox_start_symbols as ss
import dosbox_x_server as server
from dosbox_state import STATE

ROWS = [
    {"memory": "conventional", "mcb_seg": "0158", "size_bytes": 640, "psp_seg": "0008",
     "filename": "SC"},
    {"memory": "conventional", "mcb_seg": "0199", "size_bytes": 2048, "psp_seg": "019A",
     "filename": "COMMAND"},
    {"memory": "conventional", "mcb_seg": "0240", "size_bytes": 160, "psp_seg": "024C",
     "filename": "LINEUP"},     # its environment: owned by LINEUP's PSP, past it
    {"memory": "conventional", "mcb_seg": "024B", "size_bytes": 300000, "psp_seg": "024C",
     "filename": "LINEUP"},
]


def test_the_load_segment_is_the_programs_own_block_past_its_psp() -> None:
    assert ss.load_segment(ROWS, "lineup") == 0x024C + 0x10
    assert ss.load_segment(ROWS, "lineup", com=True) == 0x024C, "a COM's offsets count from it"
    assert ss.load_segment(ROWS, "MINES") is None, "not loaded yet: the next stop tries again"


def test_a_free_block_with_the_programs_stale_name_is_no_program() -> None:
    free = [{**ROWS[-1], "psp_seg": "0000"}]
    assert ss.load_segment(free, "LINEUP") is None


def test_start_judges_the_table_and_its_base_before_the_boot(tmp_path: Path) -> None:
    table = tmp_path / "LINEUP.SYM"
    table.write_text("00000100 T start\n")
    assert ss.check(str(table), "program") == ss.Held(str(table), "program")
    assert ss.check(str(table), "ds") == ss.Held(str(table), "DS")
    assert ss.check(str(table), "Program") == ss.Held(str(table), "program")
    (tmp_path / "LINEUP.COM").write_bytes(b"\xc3")
    assert ss.check(str(table), "program") == ss.Held(str(table), "program", com=True)
    assert ss.check("", "program") is None
    folded = tmp_path / "GAME.SYM"
    folded.write_text("00000100 T ShowCredits\n00000200 T SHOWCREDITS\n")
    with pytest.raises(ds.Invalid, match="once case is ignored") as e:
        ss.check(str(folded), "program")
    assert e.value.code == "bad_argument", "a table its load would refuse is refused at start"
    for symbols, base_from, said in [("", "CS", "`base_from` places a `symbols` table"),
                                     (str(table), "IP", "`base_from` is `program` or"),
                                     (str(tmp_path / "none.map"), "program", "no symbol file")]:
        with pytest.raises(ds.Invalid, match=said) as e:
            ss.check(symbols, base_from)
        assert e.value.code == "bad_argument"


class _Session:
    def __init__(self, listing: str | Exception, mode: str = "Real") -> None:
        self.listing_text, self.mode = listing, mode

    def where(self) -> dict[str, str]:
        return {"mode": self.mode}

    def listing(self, command: str) -> str:
        assert command == "DOS MCBS"
        if isinstance(self.listing_text, Exception):
            raise self.listing_text
        return self.listing_text


def test_nothing_is_placed_while_no_table_is_held_or_the_listing_cannot_be_read(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(STATE, "start_symbols", None)
    assert ss.place_if_due(_Session("unused")) is None  # type: ignore[arg-type]
    monkeypatch.setattr(STATE, "start_symbols", ss.Held("/x/LINEUP.MAP", "program"))
    assert ss.place_if_due(_Session(ds.Invalid("unexpected_answer", "x"))) is None  # type: ignore[arg-type]
    assert STATE.start_symbols is not None, "held for the next stop"


def test_the_table_is_placed_once_at_the_load_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(STATE, "start_symbols", ss.Held("/x/LINEUP.MAP", "program"))
    monkeypatch.setattr(dosbox_machine, "parse_mcbs", lambda text: ROWS)
    loads: list[Any] = []

    def load(session: Any, source: str, src: Path, base: int | None, base_from: str,
             *rest: Any, **kw: Any) -> dict[str, Any]:
        loads.append((source, base, base_from))
        return {"status": "ok", "base": base, "loaded": 385, "kept": 385}
    monkeypatch.setattr(dosbox_placement, "load", load)
    got = ss.place_if_due(_Session("listing"))  # type: ignore[arg-type]
    assert got == {"placed": True, "path": "/x/LINEUP.MAP", "load_segment": "025C",
                   "base": 0x25C0, "loaded": 385}
    assert loads == [("/x/LINEUP.MAP", 0x25C0, "CS")]
    assert STATE.start_symbols is None
    assert ss.place_if_due(_Session("listing")) is None  # type: ignore[arg-type]


def test_a_register_base_waits_for_a_stop_with_a_descriptor_to_read(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A DOS extender's program is in the chain before it switches to protected mode: the stops
    in real mode before it have no descriptor, so the table is held through them."""
    monkeypatch.setattr(STATE, "start_symbols", ss.Held("/x/LINEUP.MAP", "DS"))
    monkeypatch.setattr(dosbox_machine, "parse_mcbs", lambda text: ROWS)
    loads: list[Any] = []

    def load(session: Any, source: str, src: Path, base: int | None, base_from: str,
             *rest: Any, **kw: Any) -> dict[str, Any]:
        loads.append((base, base_from))
        return {"base": 0x1000, "loaded": 1}
    monkeypatch.setattr(dosbox_placement, "load", load)
    assert ss.place_if_due(_Session("listing", "Real")) is None  # type: ignore[arg-type]
    assert STATE.start_symbols is not None and loads == []
    got = ss.place_if_due(_Session("listing", "Pr32"))  # type: ignore[arg-type]
    assert got is not None and got["placed"] is True and loads == [(None, "DS")]


def test_a_placement_the_table_refuses_is_said_once_and_dropped(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(STATE, "start_symbols", ss.Held("/x/LINEUP.MAP", "program"))
    monkeypatch.setattr(dosbox_machine, "parse_mcbs", lambda text: ROWS)

    def load(*a: Any, **kw: Any) -> dict[str, Any]:
        raise ds.Invalid("bad_argument", "a table the LINEUP.EXE contradicts")
    monkeypatch.setattr(dosbox_placement, "load", load)
    got = ss.place_if_due(_Session("listing"))  # type: ignore[arg-type]
    assert got == {"placed": False, "path": "/x/LINEUP.MAP", "code": "bad_argument",
                   "why": "a table the LINEUP.EXE contradicts"}
    assert STATE.start_symbols is None


def test_a_table_loaded_by_hand_supersedes_the_one_start_holds(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(STATE, "start_symbols", ss.Held("/x/LINEUP.MAP", "program"))
    monkeypatch.setattr(server, "live", lambda: object())
    monkeypatch.setattr(dosbox_placement, "load", lambda *a, **k: {"status": "ok"})
    table = tmp_path / "OTHER.SYM"
    table.write_text("00000100 T start\n")
    server.symbols_load(path=str(table), base="1000")
    assert STATE.start_symbols is None
