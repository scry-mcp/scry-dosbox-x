"""The IBM PC's dictionaries held to the rules every server's base owes (`KnowledgeContract`),
and the names the `dos` channel reads from them."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core import conformance
from scry_core.knowledge import Base, Lock, SourceIndex, Support, read_index, read_lock

from scry_dosbox_x import dos_calls
from scry_dosbox_x import knowledge as pc
from scry_dosbox_x.knowledge.support import PINS, SUPPORT

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "tests" / "fixtures" / "knowledge" / "sources.json"
LOCK = ROOT / "src" / "scry_dosbox_x" / "knowledge.lock.json"


class PcKnowledge:
    """This server's base as the contract asks for it."""

    def support(self) -> Support:
        return SUPPORT

    def base(self, fts5: bool | None = None) -> Base:
        return Base.load("scry_dosbox_x", fts5=fts5, pins=PINS)

    def sources(self) -> SourceIndex:
        return read_index(INDEX)

    def lock(self) -> Lock:
        return read_lock(LOCK)

    def code_scopes(self) -> tuple[str, ...]:
        return (pc.SCOPE,)


class TestPcKnowledge(conformance.KnowledgeContract):
    @pytest.fixture
    def subject(self) -> PcKnowledge:
        return PcKnowledge()


def test_the_pins_of_the_index_are_the_ones_the_server_declares() -> None:
    assert dict(PcKnowledge().sources().pins) == PINS


@pytest.mark.parametrize(("ah", "name"), [(0x4C, "exit"), (0x3D, "open file"), (0x2C, "get time"),
                                          (0x71, "long filename fns"), (0xEF, "ancient art cga")])
def test_a_dos_function_is_named_from_the_base(ah: int, name: str) -> None:
    assert dos_calls.function_name(ah) == name


def test_a_function_the_base_does_not_hold_stays_unnamed() -> None:
    assert dos_calls.function_name(0x72) == "unnamed"


@pytest.mark.parametrize(("code", "name"), [(2, "file not found"), (5, "access denied"),
                                            (80, "file exists"), (95, "interrupted")])
def test_a_dos_error_is_named_from_the_base(code: int, name: str) -> None:
    assert dos_calls.error_name(code) == name


def test_an_error_the_base_does_not_hold_stays_unnamed() -> None:
    assert dos_calls.error_name(79) == "unnamed"


def test_the_two_dictionaries_load_whole() -> None:
    base = pc.base()
    assert not (base.file_faults or base.entry_faults or base.load_faults)
    assert {d.dictionary for d in base.dictionaries} == {"int21", "dos-errors"}
