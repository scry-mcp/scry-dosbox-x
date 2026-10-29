"""`find` and the scan family, against what the debugger printed to each scan command over its
channel (`fixtures/memfind/scry-scan.json`, one live run of the probe guest)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import scan_vocabulary as words

import dosbox_find as finder
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server  # noqa: F401 -- imports the boundary the shape guard wraps

CAPTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "memfind" / "scry-scan.json")
                     .read_text(encoding="utf-8"))["exchanges"]
#: Each reply by what it shows, as its place in the capture.
REPLY = {"list_none": 3, "cancel_none": 4, "not_active": 5, "opened_whole": 6, "cancelled": 7,
         "opened_short": 8, "opened_0400": 10, "already_active": 11, "too_wide": 12,
         "matches": 13, "listing": 14, "finished": 15, "cancel_after_finished": 17,
         "opened_0400_80": 18, "matches_previous": 19, "finished_previous": 20,
         "opened_f000": 22, "range_exceeds": 24}
#: The survivors `MEMS =0` left and `MEMFIND L` listed, the closing count among its lines.
SURVIVORS = 0xD2


def reply(name: str) -> str:
    """What the debugger printed for the capture's reply `name`, as `Session.command` gives it."""
    lines = CAPTURE[REPLY[name]]["lines"]
    assert lines, f"the reply {name} is empty, so this case would examine nothing"
    return "\n".join(lines)


class Console:
    """A session double answering from a script of (command, reply) pairs, refusing any other."""

    def __init__(self, script: list[tuple[str, str]], dump: bytes = b"") -> None:
        self.script = list(script)
        self.sent: list[str] = []
        self.dump = dump

    def command(self, text: str, seconds: float | None = None) -> str:
        assert self.script, f"unscripted debugger command {text!r}"
        want, answer = self.script.pop(0)
        assert text == want, f"the tool sent {text!r}, the script expected {want!r}"
        self.sent.append(text)
        return reply(answer) if answer in REPLY else answer

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        assert length == len(self.dump), (length, len(self.dump))
        dest.write_bytes(self.dump)
        self.dumped = dest
        return dest


def session(script: list[tuple[str, str]], dump: bytes = b"") -> Any:
    return Console(script, dump)


def listed(drop: int = 0) -> list[tuple[str, str]]:
    """`MEMS =0` and its whole listing; `drop` rows taken out of the listing (an edit)."""
    lines = reply("listing").splitlines()
    cut = "\n".join(lines[:-1 - drop] + lines[-1:]) if drop else reply("listing")
    return [("MEMS =0", "matches"), ("MEMFIND L", cut)]


def test_find_reports_every_offset_the_pattern_starts_at_and_leaves_no_file() -> None:
    dump = b"\x00\x12\x34\x12\x34\x00\x12\x34"
    s = session([], dump)
    got = finder.find(s, 0x00A7, 0x100, len(dump), b"\x12\x34")
    assert got["hits"] == ["00A7:00000101", "00A7:00000103", "00A7:00000106"]
    assert got["hits_total"] == 3 and got["truncated"] is False
    assert got["span"] == {"from": "00A7:00000100", "length": len(dump), "source": "ref+length"}
    assert not s.dumped.exists() and not s.dumped.parent.exists(), s.dumped


def test_find_counts_overlapping_hits_and_keeps_the_highest_when_truncated(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(words, "HITS_MAX", 2)
    got = finder.find(session([], b"\xaa" * 5), 0, 0, 5, b"\xaa\xaa")
    assert got["hits_total"] == 4 and got["truncated"] is True
    assert got["hits"] == ["0000:00000002", "0000:00000003"]


def test_find_refuses_a_pattern_longer_than_the_range_before_dumping() -> None:
    with pytest.raises(ds.Invalid, match="shorter than"):
        finder.find(session([]), 0, 0, 1, b"\x12\x34")


@pytest.mark.parametrize(("bad", "says"), [
    ("", "is empty"),
    ("abc", "whole number of hex bytes"),
    ("zz", "whole number of hex bytes"),
])
def test_check_pattern_refuses_what_is_not_whole_hex_bytes(bad: str, says: str) -> None:
    """Empty has its own sentence: it is what a substitution that matched nothing hands you."""
    with pytest.raises(ds.Invalid, match=says):
        finder.check_pattern(bad)


@pytest.mark.parametrize(("good", "want"), [
    ("1234", b"\x12\x34"),
    ("12 34", b"\x12\x34"),
    ("12 34 ab cd", b"\x12\x34\xab\xcd"),
])
def test_whitespace_between_the_bytes_is_accepted(good: str, want: bytes) -> None:
    """`bytes.fromhex` ignores ASCII whitespace, so a line pasted out of a dump works."""
    assert finder.check_pattern(good) == want


def test_scan_start_reads_the_opened_line() -> None:
    s = session([("MEMFIND 0000:400 100 B", "opened_0400")])
    got = finder.start_scan(s, 0, 0x400, 0x100, 1)
    assert got == {"seg_off": "0000:00000400", "length": 0x100,
                   "cell_bytes": 1, "addr": "0x00000400", "hits_total": 0x100}


def test_scan_start_refuses_when_the_debugger_already_holds_one() -> None:
    s = session([("MEMFIND 0000:400 100 B", "already_active")])
    with pytest.raises(ds.Invalid, match="one is open"):
        finder.start_scan(s, 0, 0x400, 0x100, 1)


def test_scan_start_refuses_the_range_the_debugger_refused() -> None:
    s = session([("MEMFIND 0000:0 FFFFFF B", "range_exceeds")])
    with pytest.raises(ds.Invalid, match="past the memory"):
        finder.start_scan(s, 0, 0, 0xFFFFFF, 1)


@pytest.mark.parametrize("length,cell_bytes", [(0, 1), (0x1000000, 1), (16, 8), (16, True)])
def test_scan_start_refuses_its_own_arguments_before_sending(length: int, cell_bytes: int) -> None:
    s = session([])
    with pytest.raises(ds.Invalid):
        finder.start_scan(s, 0, 0, length, cell_bytes)
    assert s.sent == []


def test_scan_filter_refuses_a_listing_whose_rows_do_not_add_up() -> None:
    """The captured listing with one row taken out (an edit) against its own closing count."""
    s = session(listed(drop=1))
    with pytest.raises(ds.Invalid, match="a whole listing"):
        finder.filter_scan(s, "=", 0, words.HITS_MAX)
    assert s.sent == ["MEMS =0", "MEMFIND L"]


def test_scan_filter_hands_back_a_whole_listing_when_the_rows_match_the_count() -> None:
    """Rows matching the count make a whole listing: first row, last row, every row keyed once."""
    got = finder.filter_scan(session(listed()), "=", 0, words.HITS_MAX)
    assert got["hits_total"] == SURVIVORS and got["closed"] is False and got["iterations"] == 1
    assert len(got["hits"]) == SURVIVORS
    assert got["hits"][0] == {"seg_off": "0000:00000404", "addr": "0x00000404", "value": "0x00"}
    assert got["hits"][-1]["seg_off"] == "0000:000004FF"


def test_scan_filter_shows_the_first_limit_survivors_and_says_more_survive() -> None:
    got = finder.filter_scan(session(listed()), "=", 0, 5)
    assert got["hits_total"] == SURVIVORS and len(got["hits"]) == 5 and got["truncated"], got
    assert got["hits"][0]["seg_off"] == "0000:00000404", got


@pytest.mark.parametrize("limit", [0, words.HITS_MAX + 1, True, 2.5])
def test_scan_filter_refuses_a_limit_outside_its_range_before_sending(limit: object) -> None:
    s = session([])
    with pytest.raises(ds.Invalid, match="is outside 1..400"):
        finder.filter_scan(s, "=", 0, cast(int, limit))
    assert s.sent == []


@pytest.mark.parametrize("limit, whole", [(SURVIVORS, True), (SURVIVORS - 1, False)])
def test_scan_filter_lists_exactly_at_its_limit_and_cuts_one_above(limit: int,
                                                                   whole: bool) -> None:
    got = finder.filter_scan(session(listed()), "=", 0, limit)
    assert len(got["hits"]) == limit and got["truncated"] is not whole, got


def test_scan_filter_reports_a_finished_scan_as_closed_with_no_survivors() -> None:
    got = finder.filter_scan(session([("MEMS !0", "finished")]), "!", 0)
    assert {k: got[k] for k in ("operator", "value", "hits_total", "closed", "hits")} == {
        "operator": "!", "value": "0x00", "hits_total": 0, "closed": True, "hits": []}, got


def test_scan_filter_refuses_a_value_wider_than_the_cells() -> None:
    with pytest.raises(ds.Invalid, match="does not fit"):
        finder.filter_scan(session([("MEMS =FFF", "too_wide")]), "=", 0xFFF)


def test_a_filter_refuses_when_nothing_is_open_and_names_the_start() -> None:
    with pytest.raises(ds.Invalid, match=r'scan\(method="start"\)'):
        finder.filter_scan(session([("MEMS =12", "not_active")]), "=", 0x12)


def test_scan_filter_sends_no_value_when_none_is_given() -> None:
    """With no value the debugger compares each cell with its previous one, and says so."""
    s = session([("MEMS >", "finished_previous")])
    assert finder.filter_scan(s, ">", None)["closed"] is True
    assert s.sent == ["MEMS >"]


@pytest.mark.parametrize("op,value", [("==", 1), ("=", -1), ("<>", 0)])
def test_scan_filter_refuses_its_own_arguments_before_sending(op: str, value: int) -> None:
    s = session([])
    with pytest.raises(ds.Invalid):
        finder.filter_scan(s, op, value)
    assert s.sent == []


def test_scan_filter_does_not_list_above_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Above the ceiling the list is cut whole: `hits: []` with `hits_total` and `truncated`."""
    monkeypatch.setattr(words, "HITS_MAX", SURVIVORS - 1)
    s = session([("MEMS =0", "matches")])
    got = finder.filter_scan(s, "=", 0, SURVIVORS - 1)
    assert got["hits_total"] == SURVIVORS and got["hits"] == [] and got["truncated"], got
    assert "listed" not in got and "filter again" in got["note"], got
    assert s.sent == ["MEMS =0"]


@pytest.fixture(autouse=True)
def no_scan_count() -> Any:
    dstate.STATE.scan_iterations = None
    dstate.STATE.scan_cell_bytes = None
    yield
    dstate.STATE.scan_iterations = None
    dstate.STATE.scan_cell_bytes = None


def test_the_closing_reply_carries_the_count_one_past_the_last_filter(
        no_scan_count: None) -> None:
    """The debugger's finish line has no count, so the server counts one past the last."""
    s = session([*listed(), ("MEMS !0", "finished")])
    first = finder.filter_scan(s, "=", 0, words.HITS_MAX)
    closing = finder.filter_scan(s, "!", 0)
    assert closing["closed"] is True and closing["iterations"] == first["iterations"] + 1
    assert closing["hits"] == [] and closing["hits_total"] == 0, closing
    assert closing["truncated"] is False, closing


def test_a_close_with_no_count_held_says_so_rather_than_guessing(no_scan_count: None) -> None:
    """A scan opened through `debug` leaves no count: the reply says why, never a made-up number."""
    got = finder.filter_scan(session([("MEMS !0", "finished")]), "!", 0)
    assert got["iterations"]["available"] is False, got


def test_scan_start_and_scan_clear_reset_the_count(no_scan_count: None) -> None:
    dstate.STATE.scan_iterations = 7
    finder.start_scan(session([("MEMFIND 0000:400 100 B", "opened_0400")]), 0, 0x400, 0x100, 1)
    got = finder.filter_scan(session([("MEMS !0", "finished")]), "!", 0)
    assert got["iterations"] == 1, got
    dstate.STATE.scan_iterations = 7
    finder.clear_scan(session([("MEMFIND !", "cancelled")]))
    assert dstate.STATE.scan_iterations is None


def test_scan_clear_says_a_scan_was_cancelled() -> None:
    assert finder.clear_scan(session([("MEMFIND !", "cancelled")])) == {"cleared": True}


@pytest.mark.parametrize("name", ["cancel_none", "cancel_after_finished"])
def test_scan_clear_says_nothing_was_open_without_refusing(name: str) -> None:
    got = finder.clear_scan(session([("MEMFIND !", name)]))
    assert got["cleared"] is False and "no search instance" in got["note"]


def test_scan_clear_refuses_an_answer_it_cannot_read() -> None:
    s = session([("MEMFIND !", "list_none")])
    with pytest.raises(ds.Invalid, match="did not report") as caught:
        finder.clear_scan(s)
    assert caught.value.code == "unexpected_answer" and s.sent == ["MEMFIND !"]


def test_scan_start_checks_the_echoed_range_and_closes_a_wrong_one() -> None:
    s = session([("MEMFIND 0000:0 FFFFFF B", "opened_whole")])
    got = finder.start_scan(s, 0, 0, 0xFFFFFF, 1)
    assert got["hits_total"] == 0xFFFFFF and got["addr"] == "0x00000000"
    short = session([("MEMFIND 0000:0 FFFFFE B", "opened_whole"), ("MEMFIND !", "cancelled")])
    with pytest.raises(ds.Invalid, match="the range asked for"):
        finder.start_scan(short, 0, 0, 0xFFFFFE, 1)
    assert short.sent == ["MEMFIND 0000:0 FFFFFE B", "MEMFIND !"]


def test_scan_start_accepts_an_offset_wider_than_sixteen_bits() -> None:
    """The debugger echoes the offset as `%04X`, which grows past 16 bits (an edited capture)."""
    opened = reply("opened_0400").replace("0000:0400 (lin 00000400) with range: 000100",
                                          "0023:16DF20 (lin 0016DF20) with range: 000100")
    got = finder.start_scan(session([("MEMFIND 0023:16DF20 100 B", opened)]),
                            0x23, 0x16DF20, 0x100, 1)
    assert got["addr"] == "0x0016df20" and got["hits_total"] == 0x100


def test_a_scan_the_debugger_says_is_gone_leaves_no_count_to_add_to(no_scan_count: None) -> None:
    """A scan the debugger says is gone leaves no stale sum for the next close."""
    dstate.STATE.scan_iterations = 2
    with pytest.raises(ds.Invalid, match=r'scan\(method="start"\)'):
        finder.filter_scan(session([("MEMS =12", "not_active")]), "=", 0x12)
    got = finder.filter_scan(session([("MEMS !0", "finished")]), "!", 0)
    assert got["iterations"]["available"] is False, got


@pytest.mark.parametrize("command", ["MEMS =0", "memfind 0000:400 10 B", "MEMFIND !"])
def test_a_raw_scan_command_drops_the_count(command: str) -> None:
    """A raw `MEMS` or `MEMFIND` moves the debugger's count past ours, so ours is dropped."""
    from dosbox_x_server_support import install
    install()
    dstate.STATE.scan_iterations = 4
    try:
        assert dosbox_x_server.debug(command=command)["status"] == "ok"
        assert dstate.STATE.scan_iterations is None
    finally:
        dstate.STATE.session = None
        dstate.STATE.scan_iterations = None


def test_clear_running_state_drops_the_count() -> None:
    dstate.STATE.scan_iterations = 5
    dstate.STATE.clear_running_state()
    assert dstate.STATE.scan_iterations is None


@pytest.mark.parametrize("name", ["cancel_none", "cancel_after_finished"])
def test_a_clear_with_nothing_open_drops_the_count_too(no_scan_count: None, name: str) -> None:
    dstate.STATE.scan_iterations = 3
    finder.clear_scan(session([("MEMFIND !", name)]))
    assert dstate.STATE.scan_iterations is None


@pytest.mark.parametrize(("size", "letter", "top"), [
    (1, "B", 0xFF), (2, "W", 0xFFFF), (4, "D", 0xFFFFFFFF)])
def test_a_scan_opened_at_a_width_takes_a_value_of_exactly_that_many_bytes(
        size: int, letter: str, top: int) -> None:
    """The opening line names its cell width; the captured byte opening is edited to it."""
    said = "1 byte" if size == 1 else f"{size} bytes"
    opened = reply("opened_0400").replace("1 byte specified", f"{said} specified")
    s = session([(f"MEMFIND 0000:400 100 {letter}", opened), (f"MEMS ={top:X}", "finished")])
    assert finder.start_scan(s, 0, 0x400, 0x100, size)["cell_bytes"] == size
    with pytest.raises(ds.Invalid, match="wider than"):
        finder.filter_scan(s, "=", top + 1)
    assert finder.filter_scan(s, "=", top)["closed"] is True
    assert s.sent == [f"MEMFIND 0000:400 100 {letter}", f"MEMS ={top:X}"]


@pytest.mark.parametrize("line", [finder.SCAN_ACTIVE, finder.SCAN_NOT_ACTIVE],
                         ids=["one already open", "none open"])
def test_a_scan_that_needs_another_call_first_says_needs_call(line: str) -> None:
    """`needs_call`, not `bad_argument`: another call has to come first, named in the message."""
    with pytest.raises(ds.Invalid) as e:
        finder._refuse(line, "filter")
    assert e.value.code == "needs_call" and "`scan(method=" in str(e.value)


def test_a_filter_with_no_value_says_what_it_compared_with_instead_of_a_null(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """No `value`: cells compare with their previous value, and the reply says so, not null."""
    monkeypatch.setattr(words, "HITS_MAX", 0x7F)      # the 128 survivors are not listed
    got = finder.filter_scan(session([("MEMS =", "matches_previous")]), "=", None)
    assert got["value"] == {"available": False, "why": finder.NO_VALUE_WHY}, got["value"]
    assert got["hits_total"] == 0x80 and got["note"] == finder.unlisted_note(), got
    assert "more than 127 survive" in got["note"]


def test_find_keeps_no_more_hits_than_it_answers() -> None:
    """A pattern matching everywhere counts every hit but keeps only `HITS_MAX` of them."""
    import tracemalloc
    dump = bytes(0xFFFF)
    s = session([], dump)
    tracemalloc.start()
    got = finder.find(s, 0, 0, len(dump), b"\x00")
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert got["hits_total"] == len(dump) and len(got["hits"]) == words.HITS_MAX, got["hits_total"]
    assert peak < 3 * len(dump), f"{peak} bytes traced for a {len(dump)}-byte range"


def test_a_scan_opened_over_another_range_is_cancelled_before_it_is_refused() -> None:
    """An instance of another range is closed before the refusal, so no scan is held by nobody."""
    s = session([("MEMFIND 0000:400 80 B", "opened_0400"), ("MEMFIND !", "cancelled")])
    with pytest.raises(ds.Invalid, match="the range asked for"):
        finder.start_scan(s, 0, 0x400, 0x80, 1)
    assert s.sent == ["MEMFIND 0000:400 80 B", "MEMFIND !"], s.sent
    assert dstate.STATE.scan_cell_bytes is None


def test_the_scan_judges_take_their_edges_and_refuse_one_past() -> None:
    """The edges of `limit`, a bool value, a one-cell range, and `find` at exactly `HITS_MAX`."""
    op = finder.OPERATORS[0]
    for limit in (1, words.HITS_MAX):
        finder.check_filter(op, None, limit)
    for limit in (0, words.HITS_MAX + 1):
        with pytest.raises(ds.Invalid):
            finder.check_filter(op, None, limit)
    with pytest.raises(ds.Invalid):
        finder.check_filter(op, True)
    finder.check_scan_range(1, 1)
    with pytest.raises(ds.Invalid):
        finder.check_scan_range(0, 1)
    got = finder.find(session([], b"\xaa" * words.HITS_MAX), 0, 0, words.HITS_MAX, b"\xaa")
    assert got["hits_total"] == words.HITS_MAX and got["truncated"] is False, got["truncated"]


def test_every_cell_width_a_scan_takes_has_the_letter_the_debugger_takes() -> None:
    assert set(finder.CELLS) == set(finder.CELL_BYTES)
