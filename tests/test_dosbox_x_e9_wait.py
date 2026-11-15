"""`e9_wait` and `log_wait` over a growing logfile: what a wait answers, refuses and reports.

None launches DOSBox-X: a double owns a real logfile and drives the real waits on it.
"""

from __future__ import annotations

import math
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from channel_double import SilentChannel
from scry_core import log_wait as core_wait
from scry_core import progress as mprogress
from scry_core import vocabulary as vocab

from scry_dosbox_x import log_reader
from scry_dosbox_x import session as ds

# Two instrumentation lines verbatim from a real guest; the third string only quotes one.
E9_BOOT = ("Bochs port E9h: [+   0.000] BOOT  . start version=1.0 gfx=1024x768x8 "
           "rate=44100 buf=2048")


E9_HELP = "Bochs port E9h: [+  19.715] UI    . info_open base=HELP"


E9_QUOTED = "make: src/loudness.c: info_open base=HELP is not an E9 line"


class LogSession:
    """A session that owns a growing logfile and drives the real `e9_wait`."""

    def __init__(self, log: Path, *, alive: bool = True) -> None:
        self.launch = SimpleNamespace(logfile=log, watched=False)
        self._alive = alive
        self.log_seen_bytes = 0

    def alive(self) -> bool:
        return self._alive

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return False

    def state(self, *, unless_silent: bool = False) -> dict[str, object]:
        return {"alive": self._alive, "running": False, "altered": False}

    def e9_text(self) -> str:
        return ds.Session.e9_text(cast(ds.Session, self))

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ds.Session.e9_new_since(cast(ds.Session, self), offset)

    def log_text(self) -> str:
        return ds.Session.log_text(cast(ds.Session, self))

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        return ds.Session.log(cast(ds.Session, self), pattern, limit, channel, since_mark)

    def e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        return ds.Session.e9_since(cast(ds.Session, self), offset, channel)

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.e9_wait(cast(ds.Session, self), pattern, seconds, mark=mark,
                                  progress=progress)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.log_wait(cast(ds.Session, self), pattern, seconds, channel,
                                   mark=mark, progress=progress)

    def e9_mark(self) -> int:
        return ds.Session.e9_mark(cast(ds.Session, self))


def test_a_wait_from_a_mark_does_not_answer_with_what_was_written_before_it(
        tmp_path: Path) -> None:
    """The control: the same wait from mark 0 finds the line at once."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    assert mark == log.stat().st_size
    # With a mark the count names the region since the mark, not the whole log.
    expired = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert expired["verdict"] == "TIMEOUT", expired
    assert re.search(r"0 since the mark at byte \d+", str(expired["note"])), expired
    assert "altogether" not in str(expired["note"])
    assert s.e9_wait("info_open", seconds=0.3)["already"] is True
    later = "Bochs port E9h: [+  40.000] UI    . info_open base=ABOUT"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{later}\n")
    got = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert got["line"] == later and got["lines_total"] == 1, got
    assert got["lines_examined"] == 1 and "since_mark" not in got, got
    assert LogSession(tmp_path / "absent.log").e9_mark() == 0


def test_a_mark_inside_a_half_written_line_does_not_serve_that_line_as_new(
        tmp_path: Path) -> None:
    """The mark is the file size, so it can land inside a line begun before it."""
    log = tmp_path / "guest.log"
    half = "Bochs port E9h: [+   1.000] ACT   . key_cue"
    log.write_text(f"{E9_BOOT}\n{half}", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    with log.open("a", encoding="utf-8") as fh:
        fh.write("_a=0 b=-1 on=0\n")
    assert s.e9_wait("key_cue_a", seconds=0.3, mark=mark)["verdict"] == "TIMEOUT"
    whole = "Bochs port E9h: [+   2.000] ACT   . key_cue_a=1 b=-1 on=1"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{whole}\n")
    got = s.e9_wait("key_cue_a", seconds=0.3, mark=mark)
    assert got["line"] == whole and got["lines_total"] == 1, got


def test_a_line_that_already_happened_is_answered_at_once(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["already"] is True
    assert got["line"] == E9_HELP
    assert got["waited_s"] == 0.0, "it waited for something it already had"


def test_the_first_occurrence_is_the_answer_and_the_count_says_there_were_more(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    first = "Bochs port E9h: [+   1.000] UI    . info_open base=HELP"
    log.write_text(f"{first}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == first and got["lines_total"] == 2


def test_a_line_that_arrives_during_the_wait_is_the_other_answer(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    def append_later() -> None:
        time.sleep(0.4)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{E9_HELP}\n")

    writer = threading.Thread(target=append_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["already"] is False, got
    assert got["line"] == E9_HELP
    # Both bounds: a lower one alone is satisfied by echoing the bound asked for.
    assert 0.3 <= cast(float, got["waited_s"]) < 5.0, got
    assert cast(int, got["lines_examined"]) >= 2, got


def test_a_bound_that_expires_is_invalid_and_says_what_it_examined(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("never_going_to_appear", seconds=0.4)
    assert got["verdict"] == "TIMEOUT" and "a bound that expired" in str(got["note"]), got
    assert got["lines_examined"] == 1 and got["arrived_during"] == 0, got


def test_only_a_session_with_no_channel_at_all_is_refused_outright() -> None:
    """A missing log, or one with no instrumentation yet, is normal for a just-resumed guest."""
    with pytest.raises(ds.Invalid, match="without a logfile"):
        LogSession(cast(Path, None)).e9_wait("x", seconds=1)


def test_it_waits_for_the_guests_very_first_trace(tmp_path: Path) -> None:
    log = tmp_path / "not-yet.log"

    def write_later() -> None:
        time.sleep(0.3)
        log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    writer = threading.Thread(target=write_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("start version", seconds=30)
    finally:
        writer.join()
    assert got["already"] is False, got
    assert got["line"] == E9_BOOT


def test_a_line_still_being_written_is_not_reported_and_is_not_lost(
        tmp_path: Path) -> None:
    """A fragment must neither be returned as the trace nor consume a line index."""
    log = tmp_path / "guest.log"
    partial = "Bochs port E9h: [+  19.715] UI    . info_open"
    log.write_text(f"{E9_BOOT}\n{partial}", encoding="utf-8")

    def finish_the_line() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(" base=HELP\n")

    writer = threading.Thread(target=finish_the_line)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["line"] == f"{partial} base=HELP", got
    assert got["already"] is False, got


def test_a_log_rewritten_underneath_the_wait_is_read_from_its_start(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n" * 40, encoding="utf-8")
    fresh = "Bochs port E9h: [+   1.000] UI    . info_open base=FRESH"

    def rewrite_later() -> None:
        time.sleep(0.3)
        log.write_text(f"{fresh}\n", encoding="utf-8")

    writer = threading.Thread(target=rewrite_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=5)
    finally:
        writer.join()
    assert got["verdict"] == "TARGET" and got["line"] == fresh, got


def test_a_session_that_dies_mid_wait_says_so_without_burning_the_bound(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    session = LogSession(log)

    def die_later() -> None:
        time.sleep(0.3)
        session._alive = False

    writer = threading.Thread(target=die_later)
    writer.start()
    began = time.monotonic()
    try:
        with pytest.raises(ds.Invalid, match="GONE"):
            session.e9_wait("never_appears", seconds=30)
    finally:
        writer.join()
    assert time.monotonic() - began < 5.0, "it waited out the bound for a dead session"


def test_the_count_of_what_arrived_during_the_wait_is_not_the_logs_total(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    # Forty-one and the `\b`: `match=` is an unanchored search, and "40 ... arrived DURING"
    # contains the "0 ..." form.
    log.write_text(f"{E9_BOOT}\n" * 41, encoding="utf-8")
    began = time.monotonic()
    got = LogSession(log).e9_wait("never_appears", seconds=0.4)
    assert re.search(r"\b0 lines arrived DURING", str(got["note"])), got
    # The bound is honoured: `deadline = began + seconds * 2` would stay green otherwise.
    assert 0.35 <= time.monotonic() - began < 2.0, "the bound was not the bound"


def test_the_match_count_of_a_waited_answer_is_not_hardcoded(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    def burst() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            for i in range(7):
                fh.write(f"Bochs port E9h: [+ {i}.000] UI    . info_open base=HELP\n")

    writer = threading.Thread(target=burst)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["lines_total"] == 7, got
    assert got["arrived_during"] == 7, got


def test_a_line_that_only_quotes_an_e9_trace_is_not_one(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_QUOTED}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == E9_HELP, got


def test_e9_wait_refuses_a_wait_that_is_not_a_bound(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    assert vocab.WAIT_MAX_S == 600, "the ceiling moved; decide it deliberately and edit here"
    for bad in (0, -1, 601):
        with pytest.raises(ds.Invalid, match="not a bound"):
            LogSession(log).e9_wait("x", seconds=bad)


def test_e9_wait_refuses_a_pattern_that_is_not_a_pattern(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="not a usable pattern"):
        LogSession(log).e9_wait("(unclosed", seconds=1)


class DyingLog(LogSession):
    """Writes its exit trace on its way out; `e9_wait` asks `alive()` first and reads last."""

    def __init__(self, log: Path, *, write_after: int, line: str) -> None:
        super().__init__(log)
        self.polls = 0
        self.write_after = write_after
        self.line = line
        self.log_path = log
        self.gone = False

    def alive(self) -> bool:
        return not self.gone

    def e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        # The read answers first, and only then does the guest write and die; otherwise the
        # ordinary match path answers and the death path never runs.
        got = super().e9_since(offset, channel)
        if self.polls == self.write_after:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            self.gone = True
        return got


def test_the_guests_last_line_is_read_before_a_death_is_reported(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    exit_line = "Bochs port E9h: [+   9.000] PERF  . exit code=0"
    got = DyingLog(log, write_after=2, line=exit_line).e9_wait("exit", seconds=5)
    assert got["line"] == exit_line, got
    assert got["already"] is False


def test_a_death_with_nothing_in_the_log_is_still_a_refusal(tmp_path: Path) -> None:
    """The red beside the case above."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="the emulator is GONE"):
        DyingLog(log, write_after=2, line="nothing to match here").e9_wait(
            "exit", seconds=5)


class LateLog(LogSession):
    """Burns the rest of the bound inside the read, so the expiry path certainly runs."""

    def __init__(self, log: Path, *, line: str, burn: float) -> None:
        super().__init__(log)
        self.polls = 0
        self.line = line
        self.log_path = log
        self.burn = burn
        self.wrote = False

    def e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super().e9_since(offset, channel)
        if self.polls >= 2 and not self.wrote:
            # Written after this read answered, then the bound is spent.
            self.wrote = True
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            time.sleep(self.burn)
        return got


def test_a_line_written_in_the_tail_of_the_window_is_not_lost_to_the_clock(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    late = "Bochs port E9h: [+   3.000] PERF  . audio play=1"
    sess = LateLog(log, line=late, burn=0.4)
    got = sess.e9_wait("audio", seconds=0.25)
    assert got["line"] == late, got
    assert got["already"] is False


def test_an_expired_bound_with_nothing_matching_is_still_a_refusal(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LateLog(log, line="Bochs port E9h: [+   3.000] UI    . nothing",
                  burn=0.4).e9_wait("audio", seconds=0.25)
    assert got["verdict"] == "TIMEOUT" and "nothing matched" in str(got["note"]), got


class StoppedLogSession(LogSession):
    """A `LogSession` that can say it is parked at the debugger."""

    def __init__(self, log: Path, *, at_debugger: bool) -> None:
        super().__init__(log)
        self._parked = at_debugger

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return self._parked


def test_a_wait_on_a_machine_stopped_at_the_debugger_refuses_at_once(tmp_path: Path) -> None:
    """A stopped guest writes nothing; what the log already holds is still answered first."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    parked = StoppedLogSession(log, at_debugger=True)
    began = time.monotonic()
    with pytest.raises(ds.Invalid, match="a stopped machine logs nothing"):
        parked.e9_wait("never_going_to_appear", seconds=30)
    assert time.monotonic() - began < 1.0, "it sat out the bound on a stopped machine"
    assert parked.e9_wait("BOOT", seconds=30)["already"] is True
    running = StoppedLogSession(log, at_debugger=False)
    assert running.e9_wait("never_going_to_appear", seconds=0.3)["verdict"] == "TIMEOUT"


class BusyChannelLogSession(LogSession):
    """A session whose debugger channel is busy: `at_debugger` raises `host_failed`."""

    def at_debugger(self) -> bool:
        raise ds.Invalid("host_failed",
                         "the debugger channel did not finish its reply to EXEC within 5 s")


def test_a_wait_reads_the_logfile_while_the_debugger_channel_is_busy(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A guest stuck in a long host call does not stop the file read: the wait answers from the
    logfile, treating the busy channel as "still running", and never raises `host_failed`."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(core_wait, "POLL_S", 0.05)
    busy = BusyChannelLogSession(log)
    assert busy.e9_wait("BOOT", seconds=0.3)["already"] is True
    expired = busy.e9_wait("never_going_to_appear", seconds=0.2)
    assert expired["verdict"] == "TIMEOUT", expired


def test_a_wait_on_a_silent_channel_keeps_its_bound_and_claims_no_run_state(
        tmp_path: Path) -> None:
    """Each question to a silent channel costs the channel's whole bound: the wait asks it once,
    so it ends within its own bound and that one question, `waited_s` is the time it took, and
    the note does not claim a run state nothing answered."""
    log = tmp_path / "guest.log"
    log.write_text("Bochs port E9h: OPEN BEGIN T=000D6087\n", encoding="utf-8")
    silent = SilentChannel(0.5)               # a question that costs most of the bound
    busy = LogSession(log)
    busy.at_debugger = silent.ask  # type: ignore[method-assign]
    try:
        began = time.monotonic()
        got = busy.log_wait("OPEN END", seconds=0.8, channel="guest")
        took = time.monotonic() - began
    finally:
        silent.close()
    assert got["verdict"] == "TIMEOUT", got
    assert took <= 0.8 + silent.seconds + 0.1 and silent.asked == 1, (took, silent.asked)
    assert abs(float(cast(float, got["waited_s"])) - round(took, 1)) <= 0.3, (got["waited_s"], took)
    note = str(got["note"])
    assert "still running" not in note and "not known" in note, note


def test_a_log_that_shrank_says_it_lost_lines(tmp_path: Path) -> None:
    """A logfile that grows back is read from its start; a smaller one lost lines, said once."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    ses = cast(ds.Session, SimpleNamespace(launch=SimpleNamespace(logfile=log),
                                           log_seen_bytes=0))
    assert log_reader.lost_lines_note(ses) == ""
    assert ses.log_seen_bytes == log.stat().st_size
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")       # a dump rewrote it shorter
    note = log_reader.lost_lines_note(ses)
    assert "lost lines" in note, note
    assert log_reader.lost_lines_note(ses) == "", "the loss is said once, then re-baselined"


def test_a_waited_answer_says_how_many_lines_sat_before_the_match(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    assert LogSession(log).e9_wait("info_open", seconds=1)["lines_before"] == 1

    def append_later() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            fh.write("Bochs port E9h: [+ 1.000] MISC  . filler\n")
            fh.write("Bochs port E9h: [+ 1.100] ACT   . key down SPACE mods=0\n")

    writer = threading.Thread(target=append_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("key down SPACE", seconds=10)
    finally:
        writer.join()
    assert got["already"] is False and got["lines_before"] == 3, got


class LateStopLogSession(LogSession):
    """Says running to the first `running_answers` questions and stopped from then on."""

    def __init__(self, log: Path, *, running_answers: int) -> None:
        super().__init__(log)
        self.asked = 0
        self.running_answers = running_answers

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        self.asked += 1
        return self.asked > self.running_answers


def test_an_expiry_consults_the_debugger_before_saying_still_running(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop landing after the last poll must not read as the process still running."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(core_wait, "POLL_S", 0.3)
    late = LateStopLogSession(log, running_answers=1)
    with pytest.raises(ds.E9Stopped, match="a stopped machine logs nothing"):
        late.e9_wait("never_going_to_appear", seconds=0.2)
    assert late.asked == 2, late.asked
    still = LateStopLogSession(log, running_answers=99)
    got = still.e9_wait("never_going_to_appear", seconds=0.2)
    assert got["verdict"] == "TIMEOUT" and "still running" in str(got["note"]), got
    assert still.asked == 2, still.asked


def test_a_stop_met_during_the_wait_is_said_as_one_and_a_parked_machine_as_parked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(core_wait, "POLL_S", 0.05)
    with pytest.raises(ds.E9Stopped, match="STOPPED during the wait"):
        LateStopLogSession(log, running_answers=1).e9_wait("never_going_to_appear", seconds=5)
    with pytest.raises(ds.E9Stopped, match="STOPPED at the debugger"):
        StoppedLogSession(log, at_debugger=True).e9_wait("never_going_to_appear", seconds=5)


class StopsAfterWriting(LogSession):
    """Writes the awaited line and parks at the debugger inside one poll interval."""

    def __init__(self, log: Path, *, line: str) -> None:
        super().__init__(log)
        self.line, self.polls, self.parks = line, 0, False

    def at_debugger(self) -> bool:
        return self.parks

    def e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super().e9_since(offset, channel)
        if self.polls == 2:
            with self.launch.logfile.open("a", encoding="utf-8") as f:
                f.write(self.line + "\n")
            self.parks = True
        return got


def test_a_reaction_written_just_before_the_stop_is_found_not_refused(tmp_path: Path) -> None:
    """The loop checks the debugger first and reads the log last, so a last read is due."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    line = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1"
    got = StopsAfterWriting(log, line=line).e9_wait("key_cue_a", seconds=5)
    assert got["line"] == line and got["already"] is False, got
    with pytest.raises(ds.E9Stopped, match="a stopped machine logs nothing"):
        StopsAfterWriting(log, line="Bochs port E9h: [+   9.000] UI    . other").e9_wait(
            "key_cue_b", seconds=5)


def test_e9_wait_reports_its_progress_while_it_waits(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(mprogress, "PROGRESS_EVERY_S", 0.0)
    ticks: list[tuple[float, float | None, str]] = []
    LogSession(log).e9_wait("never", seconds=0.25,
                            progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks, "the wait reported nothing"
    # A wait measured in time has no total: a bar towards the bound reads as progress to failure.
    assert all(t is None and m.startswith("log_wait guest /never/") for _p, t, m in ticks)
    assert ticks[-1][0] > 0 and "0 lines arrived" in ticks[-1][2]
    ticks.clear()
    LogSession(log).e9_wait("BOOT", seconds=0.25, progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks == []


class _Clock:
    """A parked machine one retrace a call; its clock in the guest's milliseconds."""

    FRAME_MS = 14.27

    def __init__(self) -> None:
        self.clock_ms, self.run = 0.0, 0

    def __call__(self) -> float:
        self.run += 1
        self.clock_ms += self.FRAME_MS
        return self.clock_ms


def test_a_parked_miss_runs_the_retraces_the_guest_s_seconds_need_and_no_more() -> None:
    clock = _Clock()
    got = log_reader._parked_wait(re.compile("NEVER"), "NEVER", "guest", 1.0, lambda: ["x"],
                                  clock)
    assert got["verdict"] == "TIMEOUT" and clock.run == math.ceil(1000 / _Clock.FRAME_MS), got
    assert "of the guest's time" in str(got["note"])


def test_a_parked_hit_ends_the_wait_at_the_retrace_that_wrote_it() -> None:
    clock = _Clock()
    looks = iter([["a"], ["b"], ["key=97"], ["c"]])
    got = log_reader._parked_wait(re.compile("key="), "key=", "guest", 5.0,
                                  lambda: next(looks), clock)
    assert (got["verdict"], got["line"], clock.run, got["already"]) == (
        "TARGET", "key=97", 2, False), got
