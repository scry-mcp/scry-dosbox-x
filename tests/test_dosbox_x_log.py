"""`log` and `log_wait`: ONE pair of tools over every channel the emulator writes.

DOSBox-X writes one file (`log logfile=`): the guest's own 0xE9 instrumentation, one
line per write with the `Bochs port E9h: ` prefix, and the emulator's own log lines around
it (the categories its `log` section lists). A reader of the E9 lines alone leaves the
second unreachable. The reader takes a `channel`: `guest` (the E9 lines), `emulator`
(every other line of the file) or `all` (the file in order, each line tagged with its
source); `process` names a stdout which here is the debugger's own terminal and not a log,
so it is refused by name. The stop survey's `e9` block, `expect` and `drive`'s look are
the guest channel by definition.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)
from test_dosbox_x_e9_wait import E9_BOOT, E9_HELP, LogSession

from scry_dosbox_x import log_reader, server
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import session as ds

EMU_LINE = "LOG: DOSBox-X version 2025.05.03"           # an emulator line, no E9 prefix
EMU_LINE_2 = "LOG: CONFIG: Loading primary settings"


def test_the_old_tool_names_are_gone_and_the_pair_is_registered() -> None:
    names = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert {"log", "log_wait"} <= names
    assert not {"e9", "e9_wait"} & names


def test_filter_log_selects_by_channel_and_tags_all() -> None:
    text = f"{EMU_LINE}\n{E9_BOOT}\n{EMU_LINE_2}\n{E9_HELP}\n"
    assert dlogs.filter_log(text, ".", 40, "guest") == ([E9_BOOT, E9_HELP], 2)
    assert dlogs.filter_log(text, ".", 40, "emulator") == ([EMU_LINE, EMU_LINE_2], 2)
    assert dlogs.filter_log(text, ".", 40, "all") == (
        [f"[emulator] {EMU_LINE}", f"[guest] {E9_BOOT}", f"[emulator] {EMU_LINE_2}",
         f"[guest] {E9_HELP}"], 4)
    assert dlogs.filter_log(text, "CONFIG", 40, "all") == ([f"[emulator] {EMU_LINE_2}"], 1)
    assert dlogs.filter_e9(text, ".", 40) == dlogs.filter_log(text, ".", 40, "guest")
    with pytest.raises(ds.Invalid, match="channel"):
        dlogs.filter_log(text, ".", 40, "process")


def test_label_counts_are_the_first_word_after_the_e9_prefix() -> None:
    lines = [E9_BOOT, E9_HELP, E9_BOOT]
    counts = dlogs.label_counts(lines)
    assert counts == {"BOOT": 2, "UI": 1}, "the label is the word after the stamp"
    assert dlogs.label_counts([EMU_LINE]) == {"LOG:": 1}


def test_a_session_log_reads_each_channel_off_the_one_file(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{EMU_LINE}\n{E9_BOOT}\n", encoding="utf-8")
    ses = LogSession(log)
    assert ses.log(".", 40, "guest") == ([E9_BOOT], 1)
    assert ses.log(".", 40, "emulator") == ([EMU_LINE], 1)
    assert ses.log(".", 40, "all") == ([f"[emulator] {EMU_LINE}", f"[guest] {E9_BOOT}"], 2)
    with pytest.raises(ds.Invalid, match="process"):
        ses.log(".", 40, "process")
    # The guest channel keeps its guard: a log with no instrumentation is no channel.
    log.write_text(f"{EMU_LINE}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="no instrumentation"):
        ses.log(".", 40, "guest")
    assert ses.log(".", 40, "emulator") == ([EMU_LINE], 1)


def test_log_wait_on_the_emulator_channel_finds_an_emulator_line(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{EMU_LINE_2}\n", encoding="utf-8")
    got = LogSession(log).log_wait("CONFIG", seconds=2, channel="emulator")
    assert got["line"] == EMU_LINE_2 and got["already"] is True and got["lines_before"] == 0
    got = LogSession(log).log_wait("CONFIG", seconds=2, channel="all")
    assert got["line"] == f"[emulator] {EMU_LINE_2}" and got["lines_before"] == 1
    missed = LogSession(log).log_wait("CONFIG", seconds=0.2, channel="guest")
    assert missed["verdict"] == "TIMEOUT" and missed["arrived_during"] == 0, missed
    # `e9_wait` is the guest channel's wait, the one `expect` and `drive` rest on.
    assert LogSession(log).e9_wait("BOOT", seconds=1)["line"] == E9_BOOT


def test_the_log_tool_passes_channel_and_labels_through() -> None:
    s = install()
    got = server.log(pattern="PERF", channel="guest", limit=7)
    assert got["status"] == "ok" and got["channel"] == "guest"
    assert s.log_calls == [("PERF", 7, "guest")]
    assert got["lines_total"] == 500 and len(got["lines"]) == 1 and got["truncated"] is True
    assert got["summary"] == "log guest /PERF/: 1 of 500 lines"
    assert "labels" not in got
    got = server.log(pattern="PERF", channel="guest", labels=True)
    assert got["labels"] == {"one": 1}
    bad = server.log(pattern="PERF", channel="serial")
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument"


def test_log_notes_lines_may_be_in_flight_on_a_running_machine() -> None:
    from types import SimpleNamespace
    from typing import cast
    running = cast(ds.Session, SimpleNamespace(parked=False))
    assert "not be in the file yet" in log_reader.in_flight_note(running)
    parked = cast(ds.Session, SimpleNamespace(parked=True))
    assert log_reader.in_flight_note(parked) == ""


def test_the_log_tool_carries_the_in_flight_note_on_a_running_machine(
        monkeypatch: pytest.MonkeyPatch) -> None:
    s = install()
    monkeypatch.setattr(s, "at_debugger", lambda: False)      # running, so lines are in flight
    got = server.log(pattern="PERF", channel="guest", limit=7)
    assert got["status"] == "ok" and "not be in the file yet" in got.get("note", ""), got


def test_perform_knows_the_pair_under_its_new_names() -> None:
    from scry_dosbox_x import checks
    assert {"log", "log_wait"} <= set(checks.BY_OP)
    assert not {"e9", "e9_wait"} & set(checks.BY_OP)


def test_a_log_wait_whose_call_is_cancelled_stops_waiting(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import time

    from scry_core import cancel

    def check() -> None:
        raise asyncio.CancelledError
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(cancel, "check", check)
    began = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        LogSession(log).log_wait("NEVER_THERE", seconds=5, channel="guest")
    assert time.monotonic() - began < 1.0


def test_since_mark_reads_only_what_came_after_it_on_every_channel(tmp_path: Path) -> None:
    """One file holds the three channels, so one position serves each: after the mark only
    what was written after it, whatever the channel; a mark at the end reads nothing."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{EMU_LINE}\n", encoding="utf-8")
    mark = log.stat().st_size
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{E9_BOOT}\n{EMU_LINE_2}\n")      # the replayed timeline writes BOOT again
    ses = LogSession(log)
    assert ses.log("BOOT", 40, "guest", mark) == ([E9_BOOT], 1)
    assert ses.log("BOOT", 40, "guest") == ([E9_BOOT, E9_BOOT], 2), "0 reads the whole log"
    assert ses.log(".", 40, "emulator", mark) == ([EMU_LINE_2], 1)
    assert ses.log(".", 40, "all", mark) == (
        [f"[guest] {E9_BOOT}", f"[emulator] {EMU_LINE_2}"], 2)
    assert ses.log(".", 40, "guest", log.stat().st_size) == ([], 0), "a window, not the channel"
    with pytest.raises(ds.Invalid, match=r"past where the guest log ends now") as e:
        ses.log(".", 40, "guest", log.stat().st_size + 1)
    assert e.value.code == "bad_argument"


def test_log_wait_since_mark_takes_a_line_before_the_mark_for_history(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    mark = log.stat().st_size
    missed = LogSession(log).log_wait("BOOT", seconds=0.2, channel="guest", mark=mark)
    assert missed["verdict"] == "TIMEOUT" and "since_mark" not in missed, missed
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{E9_BOOT}\n")
    got = LogSession(log).log_wait("BOOT", seconds=1, channel="guest", mark=mark)
    assert got["verdict"] == "TARGET" and got["already"] is True and got["lines_before"] == 0


def test_the_tools_refuse_a_mark_that_names_no_position_before_reading(tmp_path: Path) -> None:
    """A negative mark is refused by the judge every list runs too; one past the end by the
    tool, against the file as it stands."""
    from scry_dosbox_x import checks
    with pytest.raises(ds.Invalid, match="0 or more"):
        checks.BY_OP["log"](pattern=".", channel="guest", since_mark=-1)
    with pytest.raises(ds.Invalid, match="0 or more"):
        checks.BY_OP["log_wait"](pattern=".", channel="guest", since_mark=-1)
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    s = install()
    s.launch.logfile = log
    got = server.log_wait(pattern=".", channel="guest", seconds=1, since_mark=10**6)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "past where the guest log ends now" in got["message"], got


def test_the_log_tool_hands_its_mark_to_the_session() -> None:
    s = install()
    server.log(pattern="PERF", channel="guest", limit=7, since_mark=12)
    assert s.since_marks == [12], s.since_marks


def test_the_log_wait_tool_waits_from_its_mark(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    s = install()
    s.launch.logfile = log
    s.log_wait = LogSession(log).log_wait  # type: ignore[method-assign]
    got = server.log_wait(pattern="BOOT", channel="guest", seconds=0.3,
                          since_mark=log.stat().st_size)
    assert got["status"] == "ok" and got["verdict"] == "TIMEOUT", got


def test_a_mark_does_not_flatten_the_two_nothings_on_the_guest_channel(tmp_path: Path) -> None:
    """A file with no instrumentation at all is no channel with a mark too, never an empty
    window: the guard is on the file, the mark only narrows what is read of it."""
    log = tmp_path / "guest.log"
    log.write_text(f"{EMU_LINE}\n", encoding="utf-8")
    mark = log.stat().st_size
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{EMU_LINE_2}\n")
    with pytest.raises(ds.Invalid) as e:
        LogSession(log).log(".", 40, "guest", mark)
    assert e.value.code == "no_channel", e.value
    assert LogSession(log).log(".", 40, "emulator", mark) == ([EMU_LINE_2], 1)
