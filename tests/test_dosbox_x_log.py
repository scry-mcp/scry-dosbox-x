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
from test_dosbox_x_debug import E9_BOOT, E9_HELP, LogSession
from test_dosbox_x_server import clean_session, install  # noqa: F401  (the autouse teardown)

import dosbox_logs as dlogs
import dosbox_session as ds
import dosbox_x_server as server

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


def test_perform_knows_the_pair_under_its_new_names() -> None:
    import dosbox_checks as checks
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
