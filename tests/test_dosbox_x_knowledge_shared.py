"""What this server serves of the shared base (the chips and cpus scry-core holds once): only what
the shared locks and second check confirm, merged with this server's own confirmation."""

from __future__ import annotations

from scry_core import knowledge_tool
from scry_core.knowledge import shared

from scry_dosbox_x import knowledge as pc
from scry_dosbox_x import server as s


def test_the_base_serves_the_shared_entries_the_shared_check_confirms_and_no_others() -> None:
    whole = pc.load().unfiltered()
    sure = shared.confirmation()
    taken = {e.id for e in whole.entries() if e.scope != pc.SCOPE}
    assert taken, "no shared entry was loaded"
    served = {e.id for e in pc.base().entries()}
    assert taken & served == {e.id for e in whole.entries()
                              if e.scope != pc.SCOPE and sure.confirms(e)}
    assert served & taken


def test_the_own_entries_keep_their_own_confirmation() -> None:
    own = {e.id for e in pc.base().entries() if e.scope == pc.SCOPE}
    assert len(own) == 630


def test_knowledge_find_answers_a_shared_chip_register() -> None:
    reply = s.knowledge_find(kind="register", key="0x00", scope="am9517a")
    assert [e["id"] for e in reply["entries"]] == ["am9517a:register:0x00"]


def test_knowledge_find_on_a_held_back_shared_key_says_it_is_not_confirmed() -> None:
    held = next(e.id for e in pc.load().unfiltered().entries()
                if e.scope not in {pc.SCOPE} and pc.base().by_id(e.id) is None)
    scope, kind, key = held.split(":", 2)
    reply = s.knowledge_find(kind=kind, key=key, scope=scope)
    assert reply["entries"] == [] and reply["unconfirmed"] == [held]


def test_status_carries_the_counts_of_the_whole_served_base() -> None:
    counts = knowledge_tool.counts(pc.base())
    assert counts["served"] > 630 and counts["held_back"] > 235
