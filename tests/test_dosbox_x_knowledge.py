"""The IBM PC's dictionaries held to the rules every server's base owes (`KnowledgeContract`),
and the names the `dos` channel reads from them."""

from __future__ import annotations

import json
from pathlib import Path

import knowledge_sources as tool
import pytest
import scry_core
from scry_core import conformance, knowledge_tool
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
    sealed,
    shared,
)
from scry_core.knowledge import base as rows

from scry_dosbox_x import dos_calls
from scry_dosbox_x import knowledge as pc
from scry_dosbox_x import server as s
from scry_dosbox_x import state as st
from scry_dosbox_x.knowledge.support import PINS, SUPPORT

ROOT = Path(__file__).resolve().parent.parent
CORE_INDEX = Path(scry_core.__file__).parent / "knowledge_index"
INDEX = ROOT / "tests" / "fixtures" / "knowledge" / "sources.json"
LOCK = ROOT / "src" / "scry_dosbox_x" / "knowledge.lock.json"
SECOND_CHECK = ROOT / "src" / "scry_dosbox_x" / "knowledge.second-check.json"
ROWS_LOCK = ROOT / "src" / "scry_dosbox_x" / "knowledge_index" / "rows-lock.json"
EXAMPLES = ROOT / "docs" / "reference" / "examples.json"
EXAMPLE_CALL = {"kind": "call", "key": "0x21/0x4C"}
EXAMPLE_FROM = ("tests/test_dosbox_x_knowledge.py: the dictionaries of rows read whole, sealed or "
                "not; `PYTHONPATH=tools uv run python tests/test_dosbox_x_knowledge.py` writes it")


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

    def rows_base(self, fts5: bool | None = None) -> rows.Base:
        return pc.rows_base(fts5)

    def rows_sources(self) -> tuple[str, ...]:
        return pc.ROWS_SOURCES

    def rows_lock(self) -> sealed.Lock:
        return pc.rows_lock()


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


def test_the_fixture_serves_exactly_what_it_seals(fixture_base: rows.Base) -> None:
    assert sorted(fixture_base.ids()) == ["ibm-pc:call:0x21/0x4C", "ibm-pc:error:1"]
    assert fixture_base.held_back == 2


@pytest.mark.parametrize(("ah", "name"), [(0x4C, "terminate with code"), (0x3D, "0x3D"),
                                          (0x72, "0x72")])
def test_a_dos_function_is_named_from_the_rows_base_or_stays_its_number(
        served_rows: rows.Base, ah: int, name: str) -> None:
    """0x4C is sealed, 0x3D is held back, 0x72 has no entry."""
    assert dos_calls.function_name(ah) == name


@pytest.mark.parametrize(("code", "name"), [(1, "function invalid"), (2, "2"), (79, "79")])
def test_a_dos_error_is_named_from_the_rows_base_or_stays_its_number(
        served_rows: rows.Base, code: int, name: str) -> None:
    """1 is sealed, 2 is held back, 79 has no entry."""
    assert dos_calls.error_name(code) == name


def test_knowledge_find_and_status_answer_from_the_rows_base() -> None:
    base = pc.base()
    assert isinstance(base, rows.Base)
    reply = s.knowledge_find(kind="call", key="0x21/0x4C")
    assert (reply["served"], reply["held_back"]) == (len(base), base.held_back)
    assert len(base) + base.held_back == len(base.unfiltered())
    assert s.status()["knowledge"] == knowledge_tool.counts(base)


def _lock(id_: str, part: str) -> sealed.Lock:
    return sealed.Lock({id_: {part: sealed.Part("s", "r", "w", {})}})


def test_the_locks_merge_by_part_and_a_part_sealed_twice_is_refused() -> None:
    both = pc.merged(_lock("a", "doc"), _lock("a", "dosbox-x"), _lock("b", "doc"))
    assert {i: sorted(p) for i, p in both.sealed.items()} == {"a": ["doc", "dosbox-x"],
                                                                "b": ["doc"]}
    with pytest.raises(ValueError, match="a: two locks seal its part doc"):
        pc.merged(_lock("a", "doc"), _lock("a", "doc"))


def test_the_server_s_lock_holds_the_shared_seals_beside_its_own(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shared, "rows_lock", lambda: _lock("pic8259:command:0x20", "doc"))
    got = pc.rows_lock().sealed
    assert set(got) == {"pic8259:command:0x20", *sealed.read_lock(ROWS_LOCK).sealed}


def test_the_dictionaries_of_rows_load_whole() -> None:
    base = pc.base().unfiltered()
    assert not (base.file_faults or base.entry_faults or base.load_faults)
    own = {d.dictionary for d in rows.Base.load("scry_dosbox_x", lock=pc.rows_lock()).dictionaries}
    core = {d.dictionary for d in rows.Base.load("scry_core", lock=pc.rows_lock()).dictionaries}
    assert own and core and {d.dictionary for d in base.dictionaries} == own | core


def test_the_old_dictionaries_load_whole() -> None:
    base = pc.names_base()
    assert not (base.file_faults or base.entry_faults or base.load_faults)
    core = Path(scry_core.__file__).parent / "knowledge"
    shared_names = {d.dictionary for d in Base.load(core / "chips", core / "cpus").dictionaries}
    assert shared_names
    assert {d.dictionary for d in base.dictionaries} == shared_names | {
        "int21", "dos-errors", "int10", "int13", "int15", "int16", "int1a", "int2f", "int31",
        "int33", "int67", "xms"}


def test_a_cited_line_that_does_not_hash_to_the_digest_is_not_the_row(
        monkeypatch: pytest.MonkeyPatch) -> None:
    base = pc.names_base()
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


def example() -> dict[str, object]:
    """`knowledge_find`'s example on its reference page: the reply the tool gives over this
    server's dictionaries of rows read whole, so the page shows an entry before any is sealed."""
    fields = knowledge_tool.find(pc.base().unfiltered(), kind=EXAMPLE_CALL["kind"],
                                 key=EXAMPLE_CALL["key"])
    return {"from": EXAMPLE_FROM, "call": EXAMPLE_CALL,
            "reply": {"summary": knowledge_tool.summary(EXAMPLE_CALL, fields),
                      **st.reply(**fields)}}


def test_the_reference_example_is_the_reply_over_the_dictionaries_of_rows() -> None:
    shown = json.loads(EXAMPLES.read_text(encoding="utf-8"))["knowledge_find"]
    assert shown == example(), f"rewrite it as its `from` says: {EXAMPLE_FROM}"


if __name__ == "__main__":
    doc = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    doc["knowledge_find"] = example()
    EXAMPLES.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
