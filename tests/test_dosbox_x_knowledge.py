"""The IBM PC's dictionaries held to the rules every server's base owes (`KnowledgeContract`),
and the names the `dos` channel reads from them."""

from __future__ import annotations

import json
from pathlib import Path

import knowledge_sources as tool
import pytest
import scry_core
from scry_core import conformance
from scry_core.knowledge import (
    Base,
    Lock,
    Row,
    SecondCheck,
    SourceIndex,
    Support,
    read_index,
    read_lock,
    read_second_check,
    shared,
)

from scry_dosbox_x import dos_calls
from scry_dosbox_x import knowledge as pc
from scry_dosbox_x.knowledge.support import PINS, SUPPORT

ROOT = Path(__file__).resolve().parent.parent
CORE_INDEX = Path(scry_core.__file__).parent / "knowledge_index"
INDEX = ROOT / "tests" / "fixtures" / "knowledge" / "sources.json"
LOCK = ROOT / "src" / "scry_dosbox_x" / "knowledge.lock.json"
SECOND_CHECK = ROOT / "src" / "scry_dosbox_x" / "knowledge.second-check.json"


def committed_index(base: Base) -> SourceIndex:
    """The committed index as the contract reads it. A row of Ralf Brown's list holds a digest
    and no text, so its line is the entry's own `cites` when that hashes to the digest, and a
    marker no entry can quote when it does not: the contract's "quotes it character for
    character" then judges the digest."""
    doc = json.loads(INDEX.read_text(encoding="utf-8"))
    cited = {src.ref: src.cites for entry in base.unfiltered().entries()
             for src in entry.sources}
    rows: dict[str, Row] = {}
    for ref, raw in doc["rows"].items():
        line = raw.get("line")
        if line is None:
            held = cited.get(ref, "")
            line = held if tool.digest(held) == raw["digest"] else f"<digest {raw['digest']}>"
        rows[ref] = Row(line, raw.get("key", ""), raw.get("marks", ""))
    return SourceIndex(rows, {name: tuple(keys) for name, keys in doc["lists"].items()},
                       doc["pins"])


class PcKnowledge:
    """This server's base as the contract asks for it."""

    def support(self) -> Support:
        return SUPPORT

    def base(self, fts5: bool | None = None) -> Base:
        return pc.load(fts5)

    def sources(self) -> SourceIndex:
        own, core = committed_index(self.base()), read_index(CORE_INDEX / "shared.json")
        return SourceIndex({**core.rows, **own.rows}, {**core.lists, **own.lists},
                           {**core.pins, **own.pins})

    def lock(self) -> Lock:
        held = {id_: locked for lock in shared.locks() for id_, locked in lock.checked.items()}
        return Lock({**held, **read_lock(LOCK).checked})

    def second_check(self) -> SecondCheck:
        return SecondCheck({**shared.second_check().confirmed,
                            **read_second_check(SECOND_CHECK).confirmed})

    def code_scopes(self) -> tuple[str, ...]:
        return (pc.SCOPE,)


class TestPcKnowledge(conformance.KnowledgeContract):
    @pytest.fixture
    def subject(self) -> PcKnowledge:
        return PcKnowledge()


def test_the_second_check_names_only_entries_still_sealed_at_the_digest_it_confirmed() -> None:
    rows = read_second_check(SECOND_CHECK).confirmed
    sealed = {entry.id: entry.checked for entry in PcKnowledge().base().unfiltered().entries()}
    assert rows
    for entry_id, row in rows.items():
        check = sealed.get(entry_id)
        assert check is not None and check.digest == row.digest, entry_id


def test_the_pins_of_the_index_are_the_ones_the_server_declares() -> None:
    assert dict(PcKnowledge().sources().pins) == PINS


@pytest.mark.parametrize(("ah", "name"), [(0x4C, "exit"), (0x2C, "get time"),
                                          (0x71, "long filename fns"), (0xEF, "ancient art cga")])
def test_a_dos_function_is_named_from_the_base(ah: int, name: str) -> None:
    assert dos_calls.function_name(ah) == name


@pytest.mark.parametrize(("ah", "number"), [(0x3D, "0x3D"), (0x72, "0x72")])
def test_a_function_the_base_does_not_serve_is_its_number(ah: int, number: str) -> None:
    """0x3D has an entry the second check has not confirmed; 0x72 has none."""
    assert dos_calls.function_name(ah) == number


@pytest.mark.parametrize(("code", "name"), [(0, "no error"), (100, "open semaphore limit")])
def test_a_dos_error_is_named_from_the_base(code: int, name: str) -> None:
    assert dos_calls.error_name(code) == name


@pytest.mark.parametrize("code", [2, 79])
def test_an_error_the_base_does_not_serve_is_its_number(code: int) -> None:
    """2 has an entry the second check has not confirmed; 79 has none."""
    assert dos_calls.error_name(code) == str(code)


def test_the_dictionaries_load_whole() -> None:
    base = pc.base()
    assert not (base.file_faults or base.entry_faults or base.load_faults)
    core = Path(scry_core.__file__).parent / "knowledge"
    shared_names = {d.dictionary for d in Base.load(core / "chips", core / "cpus").dictionaries}
    assert shared_names
    assert {d.dictionary for d in base.dictionaries} == shared_names | {
        "int21", "dos-errors", "int10", "int13", "int15", "int16", "int1a", "int2f", "int31",
        "int33", "int67", "xms"}


def test_a_cited_line_that_does_not_hash_to_the_digest_is_not_the_row(
        monkeypatch: pytest.MonkeyPatch) -> None:
    base = pc.base()
    ref = next(r for r in json.loads(INDEX.read_text(encoding="utf-8"))["rows"]
               if r.startswith("rbil61:"))
    assert not committed_index(base).rows[ref].line.startswith("<digest ")
    monkeypatch.setattr(tool, "digest", lambda line: "0" * 64)
    assert committed_index(base).rows[ref].line.startswith("<digest ")


def test_the_list_lines_the_repository_holds_are_the_places_of_the_list_the_index_digests() -> None:
    doc = json.loads(INDEX.read_text(encoding="utf-8"))
    held = tool.list_lines_held(tool._dictionaries(ROOT / "src" / "scry_dosbox_x" / "knowledge"))
    assert held > 0, "INVALID: no dictionary cites the list"
    assert held == sum(ref.startswith("rbil61:") for ref in doc["rows"])
