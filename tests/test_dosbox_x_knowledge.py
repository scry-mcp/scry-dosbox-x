"""The IBM PC's dictionaries of rows held to the rules every server's base owes
(`KnowledgeContract`), and the names the `dos` channel reads from them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scry_core import conformance, knowledge_tool
from scry_core.knowledge import Support, sealed, shared
from scry_core.knowledge import base as rows

from scry_dosbox_x import dos_calls
from scry_dosbox_x import knowledge as pc
from scry_dosbox_x import server as s
from scry_dosbox_x import state as st
from scry_dosbox_x.knowledge.support import SUPPORT

ROOT = Path(__file__).resolve().parent.parent
ROWS_LOCK = ROOT / "src" / "scry_dosbox_x" / "knowledge_index" / "rows-lock.json"
EXAMPLES = ROOT / "docs" / "reference" / "examples.json"
EXAMPLE_CALL = {"kind": "call", "key": "0x21/0x4C"}
EXAMPLE_FROM = ("tests/test_dosbox_x_knowledge.py: the dictionaries of rows read whole, sealed or "
                "not; `PYTHONPATH=tools uv run python tests/test_dosbox_x_knowledge.py` writes it")


class PcKnowledge:
    """This server's base of rows as the contract asks for it."""

    def support(self) -> Support:
        return SUPPORT

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
