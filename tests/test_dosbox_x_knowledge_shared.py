"""What this server serves of the shared base (the chips scry-core holds once): what the shared
lock seals, merged with this server's own seals."""

from __future__ import annotations

from importlib import resources

from scry_core.knowledge import base as rows
from scry_core.knowledge import sealed, shared

from scry_dosbox_x import knowledge as pc
from scry_dosbox_x import server as s


def _shared(base: rows.Base) -> set[str]:
    return {e.id for e in base.entries() if e.scope != pc.SCOPE}


def test_the_base_serves_the_shared_entries_the_shared_lock_seals_and_no_others() -> None:
    assert _shared(pc.base().unfiltered()), "no shared entry was loaded"
    alone = rows.Base.load("scry_core", lock=shared.rows_lock())
    assert _shared(pc.base()) == {e.id for e in alone.entries()}


def test_the_own_entries_are_served_by_the_own_lock_alone() -> None:
    own = resources.files("scry_dosbox_x") / pc.ROWS_LOCK
    alone = rows.Base.load("scry_dosbox_x", lock=sealed.parse_lock(own.read_text(encoding="utf-8")))
    assert {e.id for e in pc.base().entries() if e.scope == pc.SCOPE} == set(alone.ids())


def test_knowledge_find_answers_a_shared_chip_command_or_says_it_is_held_back() -> None:
    reply = s.knowledge_find(kind="command", key="0x20", scope="pic8259")
    answered = [e["id"] for e in reply["entries"]] + reply.get("unconfirmed", [])
    assert answered == ["pic8259:command:0x20..0x27"], reply
