"""How a summary line says a count: in the number it has (`scry_core.prose`), at one and at more,
and as it came when the reply carried none."""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import dosbox_summaries as one_line  # noqa: E402


@pytest.mark.parametrize("states, said", [(1, "state_list: 1 state in /s"),
                                          (2, "state_list: 2 states in /s")])
def test_a_count_takes_its_noun_in_its_number(states: int, said: str) -> None:
    reply = {"states": [{"name": str(i)} for i in range(states)], "state_dir": "/s"}
    assert one_line.state_list({}, reply) == said


def test_a_read_says_how_many_bytes_it_read_where_and_which() -> None:
    reply = {"seg_off": "00AF:0017A6EC", "length": 4, "hex": "00112233"}
    assert one_line.read_memory({"ref": "g_rate"}, reply) == \
        "read_memory g_rate: 4 bytes at 00AF:0017A6EC: 00112233"


def test_a_long_read_shows_the_first_bytes_and_counts_the_rest() -> None:
    cap = 64
    image = bytes(range(cap + 3))
    reply = {"seg_off": "0040:0000", "length": len(image), "hex": image.hex()}
    assert one_line.read_memory({"ref": "x"}, reply).endswith(
        image[:cap].hex() + "... (3 more bytes in `hex`)")


def test_an_irregular_plural_is_said_as_english_says_it() -> None:
    for n, said in ((1, "at 1 address,"), (2, "at 2 addresses,")):
        reply = {"verdict": "ELAPSED", "trace": {"instructions": 3, "addresses": n}}
        assert said in one_line.trace({"instructions": 3, "shape": "cs_ip"}, reply)


def test_a_count_the_reply_did_not_carry_is_shown_as_it_came() -> None:
    assert one_line.snapshot({}, {"path": "/a.png"}) == "snapshot: None bytes at /a.png"


def test_a_filter_with_no_value_names_no_value_in_its_line() -> None:
    line = one_line.filter_scan({"operator": "="}, {"hits_total": 3, "closed": False})
    assert line == "=, 3 survivors", line


def test_a_cut_scan_filter_says_how_much_of_the_list_it_holds() -> None:
    """`truncated` means more survive than are listed: the line says the first ones are there,
    or that none is when the note says the list was too long to page."""
    some = one_line.filter_scan({"operator": "!"}, {"hits_total": 90, "truncated": True,
                                                    "hits": [{}, {}]})
    none = one_line.filter_scan({"operator": "!"}, {"hits_total": 900, "truncated": True,
                                                    "hits": [], "note": "..."})
    assert some.endswith("the first 2 listed") and "none listed" in none, (some, none)
