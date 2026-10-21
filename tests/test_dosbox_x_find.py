"""`find` and the scan family, against the debugger's OWN output tails, captured
(`fixtures/memfind/`), never typed from memory of the source: the pane is a scrollback, so
every fixture carries an earlier command's line above the one under test, which is the
property that made the first parser read the wrong answer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

import dosbox_console as dcons
import dosbox_find as finder
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server  # noqa: F401 -- imports the boundary the shape guard wraps

FIX = Path(__file__).resolve().parent / "fixtures" / "memfind"


def tail(name: str) -> str:
    text = (FIX / f"{name}.txt").read_text(encoding="utf-8")
    assert text.strip(), f"fixture {name} is empty, so this case would examine nothing"
    return text


class Console:
    """A session double whose console answers from a SCRIPT of (command, tail) pairs in
    order, and refuses a command the script did not foresee: a scan driven off the wrong
    command is the defect, not a detail."""

    def __init__(self, script: list[tuple[str, str]], dump: bytes = b"") -> None:
        self.script = list(script)
        self.sent: list[str] = []
        self.dump = dump

    def command(self, text: str, **_: object) -> str:
        assert self.script, f"unscripted console command {text!r}"
        want, answer = self.script.pop(0)
        assert text == want, f"the tool typed {text!r}, the script expected {want!r}"
        self.sent.append(text)
        return tail(answer)

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        assert length == len(self.dump), (length, len(self.dump))
        dest.write_bytes(self.dump)
        self.dumped = dest
        return dest


def session(script: list[tuple[str, str]], dump: bytes = b"") -> Any:
    return Console(script, dump)


# ------------------------------------------------------------------------- find

def test_find_reports_every_offset_the_pattern_starts_at_and_leaves_no_file() -> None:
    dump = b"\x00\x12\x34\x12\x34\x00\x12\x34"
    s = session([], dump)
    got = finder.find(s, 0x00A7, 0x100, len(dump), b"\x12\x34")
    assert got["hits"] == ["00A7:00000101", "00A7:00000103", "00A7:00000106"]
    assert got["hits_total"] == 3 and got["truncated"] is False
    # THE SPAN EXAMINED IS IN THE REPLY: a zero count says over which bytes it was zero.
    # Here the only range source is the caller's own, so `source` is always `ref+length`.
    assert got["span"] == {"from": "00A7:00000100", "length": len(dump), "source": "ref+length"}
    assert not s.dumped.exists() and not s.dumped.parent.exists(), s.dumped


def test_find_counts_overlapping_hits_and_keeps_the_highest_when_truncated(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finder, "HITS_MAX", 2)
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
    """EMPTY HAS ITS OWN SENTENCE: nothing is the matter with an empty string's digits, there are
    none, and empty is what a substitution that matched nothing hands you, which is worth saying
    out loud rather than describing as malformed."""
    with pytest.raises(ds.Invalid, match=says):
        finder.check_pattern(bad)


@pytest.mark.parametrize(("good", "want"), [
    ("1234", b"\x12\x34"),
    ("12 34", b"\x12\x34"),
    ("12 34 ab cd", b"\x12\x34\xab\xcd"),
])
def test_whitespace_between_the_bytes_is_accepted(good: str, want: bytes) -> None:
    """One parser, `bytes.fromhex`, which IGNORES ASCII whitespace by documented design: a line
    pasted out of a dump works wherever hex is taken.
    """
    assert finder.check_pattern(good) == want


# ------------------------------------------------------------------- scan_start

def test_scan_start_reads_the_opened_line_past_an_earlier_refusal() -> None:
    s = session([("MEMFIND 0000:400 100 B", "memfind_opened_0400")])
    got = finder.scan_start(s, 0, 0x400, 0x100, 1)
    assert got == {"seg_off": "0000:00000400", "length": 0x100,
                   "cell_bytes": 1, "addr": "0x00000400", "hits_total": 0x100}


def test_scan_start_refuses_when_the_debugger_already_holds_one() -> None:
    s = session([("MEMFIND 0000:400 100 B", "memfind_already_active")])
    with pytest.raises(ds.Invalid, match="one is open"):
        finder.scan_start(s, 0, 0x400, 0x100, 1)


def test_scan_start_refuses_the_range_the_debugger_refused() -> None:
    s = session([("MEMFIND F000:E000 100 B", "memfind_range_exceeds")])
    with pytest.raises(ds.Invalid, match="past the memory"):
        finder.scan_start(s, 0xF000, 0xE000, 0x100, 1)


@pytest.mark.parametrize("length,cell_bytes", [(0, 1), (0x1000000, 1), (16, 8), (16, True)])
def test_scan_start_refuses_its_own_arguments_before_typing(length: int, cell_bytes: int) -> None:
    s = session([])
    with pytest.raises(ds.Invalid):
        finder.scan_start(s, 0, 0, length, cell_bytes)
    assert s.sent == []


# ------------------------------------------------------------------ scan_filter

def test_scan_filter_refuses_a_listing_whose_rows_do_not_add_up() -> None:
    """The captured page is twenty rows and the captured end two more, against a count
    of 256: fewer rows than the count is a listing that did not all cross the screen."""
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "memfind_list_page"),
                 ("", "memfind_list_last"), ("", "memfind_cancelled")])
    # 0x100 survivors are what the machine said; the two captured pages hold 22 rows, so
    # the whole-listing check must REFUSE rather than hand back a partial table.
    with pytest.raises(ds.Invalid, match="a whole listing"):
        finder.scan_filter(s, "=", 0, finder.HITS_MAX)
    # The last ENTER is the refusal clearing the command line: a refusal that leaves it
    # dirty costs the whole session.
    assert s.sent == ["MEMS =0", "MEMFIND L", "", ""]


def twenty_two() -> Any:
    """The captured page and the captured end carry 22 rows between them, so the count the
    debugger reports is rewritten to 22 in both places it prints it."""
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "memfind_list_page"),
                 ("", "memfind_list_last")])
    orig: Callable[..., str] = s.command

    def command(text: str, **_: object) -> str:
        return orig(text).replace("(000100) matches", "(000016) matches").replace(
            "instance: 000100", "instance: 000016")
    s.command = command
    return s


def test_scan_filter_hands_back_a_whole_listing_when_the_rows_match_the_count() -> None:
    """The captured page and the captured end carry 22 rows between them, so the count
    the debugger reports is rewritten to 22 in both places it prints it and the listing
    is then whole: first row, last row, every row keyed once."""
    s = twenty_two()
    got = finder.scan_filter(s, "=", 0)
    assert got["hits_total"] == 22 and got["closed"] is False and got["iterations"] == 1
    assert len(got["hits"]) == 22
    assert got["hits"][0] == {"seg_off": "0000:00000400", "addr": "0x00000400", "value": 0}
    assert got["hits"][-1]["seg_off"] == "0000:000004FF"


def test_scan_filter_lists_no_more_survivors_than_its_limit_and_says_so() -> None:
    """256 survivors against the default limit: the count comes back, the listing is never
    typed, and `truncated` says the hits are not all of them."""
    s = session([("MEMS =0", "mems_matches")])
    got = finder.scan_filter(s, "=", 0)
    assert got["hits_total"] == 256 > finder.HITS_DEFAULT
    assert got["hits"] == [] and got["truncated"] is True
    assert s.sent == ["MEMS =0"]


@pytest.mark.parametrize("limit", [0, finder.HITS_MAX + 1, True, 2.5])
def test_scan_filter_refuses_a_limit_outside_its_range_before_typing(limit: object) -> None:
    s = session([])
    with pytest.raises(ds.Invalid, match="is outside 1..400"):
        finder.scan_filter(s, "=", 0, cast(int, limit))
    assert s.sent == []


@pytest.mark.parametrize("limit, listed", [(22, True), (21, False)])
def test_scan_filter_lists_exactly_at_its_limit_and_cuts_one_above(limit: int,
                                                                   listed: bool) -> None:
    """22 survivors: a limit of 22 lists them, a limit of 21 types no listing at all."""
    s = twenty_two()
    got = finder.scan_filter(s, "=", 0, limit)
    assert len(got["hits"]) == (22 if listed else 0) and got["truncated"] is not listed
    assert ("MEMFIND L" in s.sent) is listed


def test_scan_filter_reports_a_finished_scan_as_closed_with_no_survivors() -> None:
    s = session([("MEMS !0", "mems_finished")])
    got = finder.scan_filter(s, "!", 0)
    assert {k: got[k] for k in ("operator", "value", "hits_total", "closed", "hits")} == {
        "operator": "!", "value": 0, "hits_total": 0, "closed": True, "hits": []}, got


def test_scan_filter_refuses_a_value_wider_than_the_cells() -> None:
    s = session([("MEMS =FFF", "mems_too_wide")])
    with pytest.raises(ds.Invalid, match="does not fit"):
        finder.scan_filter(s, "=", 0xFFF)


def test_scan_filter_refuses_when_nothing_is_open_and_names_scan_start() -> None:
    s = session([("MEMS =12", "mems_not_active")])
    with pytest.raises(ds.Invalid, match="scan_start"):
        finder.scan_filter(s, "=", 0x12)


def test_scan_filter_sends_no_value_when_none_is_given() -> None:
    s = session([("MEMS >", "mems_finished")])
    finder.scan_filter(s, ">", None)
    assert s.sent == ["MEMS >"]


@pytest.mark.parametrize("op,value", [("==", 1), ("=", -1), ("<>", 0)])
def test_scan_filter_refuses_its_own_arguments_before_typing(op: str, value: int) -> None:
    s = session([])
    with pytest.raises(ds.Invalid):
        finder.scan_filter(s, op, value)
    assert s.sent == []


def test_scan_filter_does_not_list_above_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Above the ceiling the list is cut whole: `hits: []`, `hits_total` beside it and
    `truncated: true`, the words `find` uses for the same idea; `listed` is gone."""
    monkeypatch.setattr(finder, "HITS_MAX", 0xFF)
    s = session([("MEMS =0", "mems_matches")])
    got = finder.scan_filter(s, "=", 0, 0xFF)
    assert got["hits_total"] == 0x100 and got["hits"] == [], got
    assert got["hits_total"] == 0x100 and got["truncated"] is True, got
    assert "listed" not in got, got
    assert s.sent == ["MEMS =0"]


@pytest.fixture(autouse=True)
def no_scan_count() -> Any:
    dstate.STATE.scan_iterations = None
    dstate.STATE.scan_cell_bytes = None
    yield
    dstate.STATE.scan_iterations = None
    dstate.STATE.scan_cell_bytes = None


def _listed_22(s: Any) -> None:
    orig: Callable[..., str] = s.command

    def command(text: str, **_: object) -> str:
        return orig(text).replace("(000100) matches", "(000016) matches").replace(
            "instance: 000100", "instance: 000016")
    s.command = command


def test_a_listed_reply_says_it_is_whole(no_scan_count: None) -> None:
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "memfind_list_page"),
                 ("", "memfind_list_last")])
    _listed_22(s)
    got = finder.scan_filter(s, "=", 0)
    assert got["truncated"] is False and got["hits_total"] == 22, got
    assert len(got["hits"]) == 22 and "listed" not in got, got


def test_the_closing_reply_carries_the_count_one_past_the_last_filter(
        no_scan_count: None) -> None:
    """The debugger's finish line carries no count, so the server counts: the filter that
    closes the scan is the one after the last count the debugger printed."""
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "memfind_list_page"),
                 ("", "memfind_list_last"), ("MEMS !0", "mems_finished")])
    _listed_22(s)
    first = finder.scan_filter(s, "=", 0)
    closing = finder.scan_filter(s, "!", 0)
    assert closing["closed"] is True and closing["iterations"] == first["iterations"] + 1
    assert closing["hits"] == [] and closing["hits_total"] == 0, closing
    assert closing["truncated"] is False, closing


def test_a_close_with_no_count_held_says_so_rather_than_guessing(no_scan_count: None) -> None:
    """A scan opened past the server (`debug("MEMFIND ...")`) leaves no count here: the
    closing reply says `iterations: null` and why, never a number made up."""
    got = finder.scan_filter(session([("MEMS !0", "mems_finished")]), "!", 0)
    assert got["iterations"]["available"] is False, got


def test_scan_start_and_scan_clear_reset_the_count(no_scan_count: None) -> None:
    dstate.STATE.scan_iterations = 7                    # an earlier scan's count
    finder.scan_start(session([("MEMFIND 0000:400 100 B", "memfind_opened_0400")]),
                      0, 0x400, 0x100, 1)
    got = finder.scan_filter(session([("MEMS !0", "mems_finished")]), "!", 0)
    assert got["iterations"] == 1, got                  # the first filter closed it
    dstate.STATE.scan_iterations = 7
    finder.scan_clear(session([("MEMFIND !", "memfind_cancelled")]))
    assert dstate.STATE.scan_iterations is None


# ------------------------------------------------------------------- scan_clear

def test_scan_clear_reads_the_last_line_not_the_stale_one_above_it() -> None:
    s = session([("MEMFIND !", "memfind_cancelled")])
    assert finder.scan_clear(s) == {"cleared": True}


@pytest.mark.parametrize("fixture", ["memfind_cancel_none", "memfind_cancel_after_finished"])
def test_scan_clear_says_nothing_was_open_without_refusing(fixture: str) -> None:
    s = session([("MEMFIND !", fixture)])
    got = finder.scan_clear(s)
    assert got["cleared"] is False and "no search instance" in got["note"]


def test_scan_clear_refuses_an_answer_it_cannot_read() -> None:
    s = session([("MEMFIND !", "memfind_list_none"), ("", "memfind_cancelled")])
    with pytest.raises(ds.Invalid, match="did not report") as caught:
        finder.scan_clear(s)
    assert caught.value.fields["line_recovered"] is True, caught.value.fields
    assert s.sent == ["MEMFIND !", ""], "the refusal cleared the line before returning"


def test_scan_start_reads_past_two_stacked_stale_lines_and_checks_the_echoed_range() -> None:
    s = session([("MEMFIND 0000:0 FFFFFF B", "memfind_opened")])
    got = finder.scan_start(s, 0, 0, 0xFFFFFF, 1)
    assert got["hits_total"] == 0xFFFFFF and got["addr"] == "0x00000000"
    short = session([("MEMFIND 0000:0 FFFFFE B", "memfind_opened"),
                     ("", "memfind_cancelled")])
    with pytest.raises(ds.Invalid, match="the range asked for"):
        finder.scan_start(short, 0, 0, 0xFFFFFE, 1)
    assert short.sent == ["MEMFIND 0000:0 FFFFFE B", ""]


def test_scan_start_accepts_an_offset_wider_than_sixteen_bits() -> None:
    """The debugger echoes the offset as `%04X`, so past 16 bits it simply grows; a
    protected-mode global is exactly that address, and a four-digit pattern would have
    read a successful open as no open at all."""
    s = session([("MEMFIND 0023:16DF20 100 B", "memfind_opened_0400")])
    orig: Callable[..., str] = s.command

    def command(text: str, **_: object) -> str:
        return orig(text).replace("0000:0400 (lin 00000400) with range: 000100",
                                  "0023:16DF20 (lin 0016DF20) with range: 000100")
    s.command = command
    got = finder.scan_start(s, 0x23, 0x16DF20, 0x100, 1)
    assert got["addr"] == "0x0016df20" and got["hits_total"] == 0x100


def test_listing_rows_are_read_across_a_page_with_another_pane_spliced_in() -> None:
    """The captured second page carries a torn row, two whole rows, a repaint of the
    register pane, then more rows: the torn line is not a row, the rest are."""
    rows = finder.SCAN_ROW.findall(tail("memfind_list_next_page"))
    assert [r[1] for r in rows] == ["000422", "000423", "000428", "000429", "00042A"]


def test_listing_ignores_the_previous_listings_closing_line_and_rows_above_the_summary() -> None:
    """A scan listed once and filtered again: the first page of the new listing still
    shows the OLD closing count and old rows above the filter's own summary line, and
    only what follows that summary belongs to the new listing."""
    stale = tail("memfind_list_last")            # old rows 4FE, 4FF and "Matched ... 000100"
    fresh_summary = tail("mems_matches").replace("(000100) matches", "(000002) matches")
    page = stale + fresh_summary + tail("memfind_list_last").replace(
        "instance: 000100", "instance: 000002")
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "mems_matches")])
    answers = iter([fresh_summary, page])
    s.command = lambda text, **_: next(answers)
    got = finder.scan_filter(s, "=", 0)
    assert got["hits_total"] == 2 and [h["seg_off"] for h in got["hits"]] == [
        "0000:000004FE", "0000:000004FF"]


# ------------------------------------------------ a page left unturned corrupts the line

def test_a_listing_that_ends_with_a_page_still_waiting_turns_it_before_returning() -> None:
    """THE DEFECT. A listing that returns the moment it sees its closing count can leave the
    debugger STILL holding a paged-content prompt. That prompt then eats the next command
    character by character, one page per keystroke: `MEMS ` is swallowed and `=FF` is left
    typed on the command line, so the debugger answers "command not recognized" and every
    later call concatenates onto the same line (`=FFMEMFIND !BPLISTBPLISTBPLIST`). Only
    `close` recovers from that."""
    # Two captured rows and a closing count of two, so the whole-listing check passes and
    # the case is about the PAGE alone; the page mark is the captured one, appended.
    closing = "\n".join(tail("memfind_list_last").splitlines()[-4:]).replace(
        "instance: 000100", "instance: 000002")
    still_paged = closing + "\n" + tail("memfind_list_page").splitlines()[-1]
    s = session([("MEMS =0", "mems_matches"), ("MEMFIND L", "mems_matches")])
    answers = iter([tail("mems_matches").replace("(000100) matches", "(000002) matches"),
                    still_paged, tail("memfind_cancelled")])
    typed: list[str] = []

    def command(text: str, **_: object) -> str:
        typed.append(text)
        return next(answers)

    s.command = command
    got = finder.scan_filter(s, "=", 0)
    assert got["hits_total"] == 2, got
    assert typed[-1] == "", (
        f"the listing returned on {typed[-1]!r} with a page still waiting: the next command "
        "is what pays for it")


def test_an_unreadable_answer_clears_the_command_line_before_it_refuses() -> None:
    """THE NET, whatever leaves the line dirty. An `unexpected_answer` returning with
    whatever the debugger half-typed still on its command line makes every later call
    concatenate instead of run. So the line is cleared before the refusal goes back, and
    the refusal says the session is still usable."""
    typed: list[str] = []

    class Dirty:
        def command(self, text: str, **_: object) -> str:
            typed.append(text)
            return tail("memfind_list_none") if text else tail("memfind_cancelled")

    with pytest.raises(ds.Invalid) as caught:
        finder.scan_clear(cast(Any, Dirty()))
    assert caught.value.code == "unexpected_answer", caught.value
    assert "" in typed[1:], (
        f"the refusal went back without clearing the line; what it typed was {typed!r}")


def test_an_idle_prompt_answers_a_bare_enter_with_nothing_and_that_counts_as_cleared() -> None:
    """The measured idle behaviour, pinned. A bare ENTER at an idle prompt produces NO
    output at all (measured against the probe guest, three in a row, and the last command
    was not repeated), so an empty delta is what a successful clear looks like. A recovery
    reading emptiness as failure would spend its whole bound and then declare a healthy
    session unusable."""
    typed: list[str] = []

    def command(text: str, **_: object) -> str:
        typed.append(text)
        return ""

    assert finder._clear_line(cast(Any, type("Idle", (), {"command": staticmethod(command)})()))
    assert typed == [""], f"one ENTER should have been enough; it typed {typed!r}"


def test_a_tail_the_debugger_did_not_take_is_emptied_with_escape_not_run_again() -> None:
    """A page turned can leave a stranded tail on the line, which an ENTER submits and the
    debugger does not take: a second ENTER would run it again, so ESC empties it."""
    typed: list[str] = []

    class Stranded:
        def command(self, text: str, **_: object) -> str:
            typed.append(text)
            return "*** Debugger command not recognized\r\n" + dcons.PROMPT + " =FF _"

        def clear_line(self) -> str:
            typed.append("ESC")
            return dcons.PROMPT + " _"

    assert finder._clear_line(cast(Any, Stranded()))
    assert typed == ["", "ESC"], typed


def test_a_scan_the_debugger_says_is_gone_leaves_no_count_to_add_to(no_scan_count: None) -> None:
    """The debugger said no scan is open, so whatever this server counted belongs to a scan
    that ended past it: the next close answers null with why, never the stale sum."""
    dstate.STATE.scan_iterations = 2
    with pytest.raises(ds.Invalid, match="scan_start"):
        finder.scan_filter(session([("MEMS =12", "mems_not_active")]), "=", 0x12)
    got = finder.scan_filter(session([("MEMS !0", "mems_finished")]), "!", 0)
    assert got["iterations"]["available"] is False, got


@pytest.mark.parametrize("command", ["MEMS =0", "memfind 0000:400 10 B", "MEMFIND !"])
def test_a_raw_scan_command_drops_the_count(tmp_path: Any, command: str) -> None:
    """A `MEMS` or `MEMFIND` typed through `debug` moves the debugger's own count past this
    server's, so the server stops claiming one."""
    import dosbox_x_server as server

    class Raw:
        def alive(self) -> bool:
            return True

        @property
        def parked(self) -> bool:
            return self.at_debugger()

        def at_debugger(self) -> bool:
            return True

        def command(self, text: str, **_: object) -> str:
            return "screen"

        def state(self) -> dict[str, object]:
            return {"alive": True, "running": False, "altered": False}

    dstate.STATE.session = Raw()  # type: ignore[assignment]
    dstate.STATE.scan_iterations = 4
    try:
        assert server.debug(command=command)["status"] == "ok"
        assert dstate.STATE.scan_iterations is None
    finally:
        dstate.STATE.session = None
        dstate.STATE.scan_iterations = None


def test_clear_running_state_drops_the_count() -> None:
    dstate.STATE.scan_iterations = 5
    dstate.STATE.clear_running_state()
    assert dstate.STATE.scan_iterations is None


@pytest.mark.parametrize("fixture", ["memfind_cancel_none", "memfind_cancel_after_finished"])
def test_a_clear_with_nothing_open_drops_the_count_too(no_scan_count: None, fixture: str) -> None:
    dstate.STATE.scan_iterations = 3
    finder.scan_clear(session([("MEMFIND !", fixture)]))
    assert dstate.STATE.scan_iterations is None


@pytest.mark.parametrize(("size", "letter", "top"), [
    (1, "B", 0xFF), (2, "W", 0xFFFF), (4, "D", 0xFFFFFFFF)])
def test_a_scan_opened_at_a_width_takes_a_value_of_exactly_that_many_bytes(
        size: int, letter: str, top: int) -> None:
    """The opening line names its cell (upstream `debug.cpp` at the pinned tag prints `1 byte`,
    `2 bytes` or `4 bytes specified.`); the captured byte opening is rewritten to the width."""
    said = "1 byte" if size == 1 else f"{size} bytes"
    s = session([(f"MEMFIND 0000:400 100 {letter}", "memfind_opened_0400"),
                 (f"MEMS ={top:X}", "mems_finished")])
    orig: Callable[..., str] = s.command

    def command(text: str, **_: object) -> str:
        return orig(text).replace("1 byte specified", f"{said} specified")
    s.command = command
    assert finder.scan_start(s, 0, 0x400, 0x100, size)["cell_bytes"] == size
    with pytest.raises(ds.Invalid, match="wider than"):
        finder.scan_filter(s, "=", top + 1)
    assert finder.scan_filter(s, "=", top)["closed"] is True
    assert s.sent == [f"MEMFIND 0000:400 100 {letter}", f"MEMS ={top:X}"]


@pytest.mark.parametrize("line", [finder.SCAN_ACTIVE, finder.SCAN_NOT_ACTIVE],
                         ids=["one already open", "none open"])
def test_a_scan_that_needs_another_call_first_says_needs_call(line: str) -> None:
    """The shared table's `needs_call`: another call has to come first (`scan_clear`, or
    `scan_start`), named in the message, where `bad_argument` would ask for another value."""
    with pytest.raises(ds.Invalid) as e:
        finder._refuse(line, "filter")
    assert e.value.code == "needs_call" and "`scan_" in str(e.value)


def test_a_filter_with_no_value_says_what_it_compared_with_instead_of_a_null() -> None:
    """No `value`: each cell is compared with its value when the scan opened, and the reply's
    `value` says so as the unavailable datum, never a null."""
    s = session([("MEMS =", "mems_matches")])
    got = finder.scan_filter(s, "=", None)
    assert got["value"] == {"available": False, "why": finder.NO_VALUE_WHY}, got["value"]
