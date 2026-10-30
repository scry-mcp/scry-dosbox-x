"""The DOS channel, read from the trace `DOSTRACE` wrote over the DOS guest's run
(`tests/fixtures/hardware/dosio.trace`)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import install
from scry_core.reply_contract import Invalid

from scry_dosbox_x import dos_calls as dos
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import server
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

TRACE = Path(__file__).resolve().parent / "fixtures" / "hardware" / "dosio.trace"


def _read(path: Path) -> dos.Trace:
    return dos.read(dos.Trace(path))


def test_each_call_is_paired_with_its_return_and_the_missing_file_carries_error_2() -> None:
    calls = {c.get("file"): c for c in _read(TRACE).calls if c.get("file")}
    found, missing = calls["IN.TXT"], calls["MISSING.TXT"]
    assert found["name"] == "open" and found["out"] == {
        "ax": "0x0005", "bx": "0xFEA5", "cx": "0x00FF", "dx": "0x0198", "cf": 0}, found
    assert "error" not in found and found["caller"] == "08BC:011F" and found["psp"] == "0x08BC"
    assert missing["error"] == {"code": 2, "name": "file not found"}, missing
    assert missing["line"].endswith("MISSING.TXT -> error 2 file not found"), missing["line"]


def test_a_call_is_timed_in_seconds_on_run_for_s_clock() -> None:
    """`T=` is `PIC_FullIndex()`, milliseconds, as `RUNSTATE`'s `ms=` is."""
    missing = next(c for c in _read(TRACE).calls if c.get("file") == "MISSING.TXT")
    assert missing["time_s"] == pytest.approx(0.0013521), missing
    assert missing["time_s"] <= missing["returned_s"] < 0.01, missing


def test_a_call_that_does_not_return_to_its_caller_says_so_and_claims_no_result() -> None:
    shell = next(c for c in _read(TRACE).calls if c["n"] == 1)
    assert shell["switched"] is True and "out" not in shell and "error" not in shell, shell
    assert shell["caller"].startswith("F000:") and shell["file"] == r"Z:\SYSTEM\mount.COM"


def test_a_call_made_inside_another_returns_before_it() -> None:
    by = {c["n"]: c for c in _read(TRACE).calls}
    close = next(c for c in by.values() if c["name"] == "close" and c["psp"] == "0x08BC"
                 and c["n"] > 20)
    inner = [by[close["n"] + 1], by[close["n"] + 2]]
    assert [c["name"] for c in inner] == ["get date", "get time"], inner
    assert close["returned"] and all(c["returned_s"] <= close["returned_s"] for c in inner)


def test_a_read_parses_only_what_the_file_gained_and_holds_a_cut_line(tmp_path: Path) -> None:
    rows = TRACE.read_bytes().splitlines(keepends=True)
    path = tmp_path / "t.trace"
    path.write_bytes(b"".join(rows[:3]) + rows[3][:20])
    trace = _read(path)
    assert [c["n"] for c in trace.calls] == [1, 2] and trace.calls[1]["returned"] is False
    path.write_bytes(b"".join(rows))
    dos.read(trace)
    assert len(trace.calls) == 25 and trace.calls[1]["returned"] is True, len(trace.calls)


def test_a_line_that_is_no_row_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_text("E N=1 nonsense\n")
    with pytest.raises(Invalid) as e:
        _read(path)
    assert e.value.code == "unexpected_answer"


def test_a_trace_cut_at_its_bound_says_so(tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(TRACE.read_bytes() + b"X ROWS_MAX=1000000\n")
    install()
    dstate.STATE.dos_calls = dos.Trace(path)
    got = cast(dict[str, Any], server.log(pattern="open", channel="dos"))
    assert got["status"] == "ok" and "stopped at its" in got["note"], got


def _call_rows(first: int, last: int, name: str | None = None) -> str:
    """Paired rows in the shapes `DOSTRACE` writes for calls `first` to `last`."""
    regs = " ".join(f"{r}=0000" for r in ("AX", "BX", "CX", "DX", "SI", "DI", "DS", "ES"))
    return "".join(
        f"E N={n} T={n}.0 M=R CS=08BC IP=011F PSP=08BC {regs} NAME={name or f'F{n}.TXT'}\n"
        f"R N={n} T={n}.5 AX=0005 BX=0000 CX=0000 DX=0000 CF=0 SWITCHED=0\n"
        for n in range(first, last + 1))


def test_a_trace_past_its_window_keeps_the_newest_calls_and_counts_the_dropped(
        tmp_path: Path) -> None:
    path = tmp_path / "long.trace"
    path.write_text(_call_rows(1, dos.CALLS_KEPT + 7))
    trace = _read(path)
    assert (len(trace.calls), trace.dropped) == (dos.CALLS_KEPT, 7)
    assert trace.calls[0]["n"] == 8 and trace.calls[-1]["n"] == dos.CALLS_KEPT + 7
    assert 7 not in trace.by_n and 8 in trace.by_n and len(trace.by_n) == dos.CALLS_KEPT
    install()
    dstate.STATE.dos_calls = trace
    got = cast(dict[str, Any], server.log(pattern="F", channel="dos", limit=2))
    assert got["calls_dropped"] == 7 and got["lines_total"] == dos.CALLS_KEPT, got


def test_a_read_trims_as_it_goes_so_a_long_unread_file_never_sits_whole_in_memory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "long.trace"
    path.write_text(_call_rows(1, dos.CALLS_KEPT * 3))
    monkeypatch.setattr(dos, "CHUNK_BYTES", 1 << 20)
    held: list[int] = []
    trim = dos._trim

    def watching(trace: dos.Trace) -> None:
        held.append(len(trace.calls))
        trim(trace)
    monkeypatch.setattr(dos, "_trim", watching)
    trace = _read(path)
    assert trace.dropped == dos.CALLS_KEPT * 2 and trace.calls[-1]["n"] == dos.CALLS_KEPT * 3
    assert len(held) > 1 and max(held) < dos.CALLS_KEPT * 2, held


def test_a_pattern_cached_before_the_window_moved_answers_only_with_held_calls(
        tmp_path: Path) -> None:
    path = tmp_path / "long.trace"
    path.write_text(_call_rows(1, dos.CALLS_KEPT))
    trace = _read(path)
    assert len(dos._matching(trace, r"F(1|2)\.TXT")) == 2
    with path.open("a") as f:
        f.write(_call_rows(dos.CALLS_KEPT + 1, dos.CALLS_KEPT + 1, name="F1.TXT"))
    dos.read(trace)
    assert [c["n"] for c in dos._matching(trace, r"F(1|2)\.TXT")] == [2, dos.CALLS_KEPT + 1]


def test_log_on_the_dos_channel_filters_and_keeps_the_newest() -> None:
    install()
    dstate.STATE.dos_calls = dos.Trace(TRACE)
    got = cast(dict[str, Any], server.log(pattern="open", channel="dos", limit=1))
    assert got["status"] == "ok" and got["lines_total"] == 2 and got["truncated"] is True, got
    assert [c["file"] for c in got["calls"]] == ["MISSING.TXT"], got["calls"]


def test_a_session_with_no_trace_answers_no_channel_naming_dos_calls() -> None:
    install()
    dstate.STATE.dos_calls = None
    got = cast(dict[str, Any], server.log(pattern=".", channel="dos"))
    assert got["code"] == "no_channel" and "dos_calls" in got["message"], got


def test_since_mark_is_refused_on_the_dos_channel() -> None:
    install()
    dstate.STATE.dos_calls = dos.Trace(TRACE)
    got = cast(dict[str, Any], server.log(pattern=".", channel="dos", since_mark=10))
    assert got["code"] == "bad_argument" and "since_mark" in got["message"], got


def test_log_wait_answers_at_once_for_a_traced_call() -> None:
    install()
    dstate.STATE.dos_calls = dos.Trace(TRACE)
    got = cast(dict[str, Any], server.log_wait(pattern="MISSING", channel="dos", seconds=1))
    assert got["verdict"] == "TARGET" and got["already"] is True, got
    assert got["call"]["file"] == "MISSING.TXT"


class _Stopping:
    """A session the wait sees running, until `RUNSTATE` answers stopped on its second poll."""

    parked = False

    def __init__(self) -> None:
        self.asked = 0

    def alive(self) -> bool:
        return True

    def at_debugger(self) -> bool:
        self.asked += 1
        return self.asked >= 2


def test_a_wait_ends_when_the_machine_stops_during_it() -> None:
    install()
    dstate.STATE.dos_calls = dos.Trace(TRACE)
    session = _Stopping()
    with pytest.raises(ds.E9Stopped):
        dos.log_wait(cast(Any, session), "NEVER_CALLED", 5.0, 0, lambda *_a: None)
    assert session.asked == 2


def test_a_wait_that_times_out_on_a_cut_trace_says_both(tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(TRACE.read_bytes() + b"X ROWS_MAX=1000000\n")
    install()
    dstate.STATE.dos_calls = dos.Trace(path)
    session = _Stopping()
    session.at_debugger = lambda: False  # type: ignore[method-assign]
    got = dos.log_wait(cast(Any, session), "NEVER_CALLED", 0.1, 0, lambda *_a: None)
    assert got["verdict"] == "TIMEOUT" and "in 0.1 s" in got["note"], got
    assert "stopped at its" in got["note"]


def test_a_trace_written_with_crlf_reads_as_the_same_rows(tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(TRACE.read_bytes().replace(b"\n", b"\r\n"))
    calls = {c.get("file"): c for c in _read(path).calls if c.get("file")}
    assert calls["MISSING.TXT"]["error"]["code"] == 2 and calls["IN.TXT"]["file"] == "IN.TXT"


def test_a_trace_row_of_no_known_shape_breaks_every_later_read_not_only_the_first(
        tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(b"not a row of DOSTRACE\n")
    trace = dos.Trace(path)
    for _ in range(2):
        with pytest.raises(Invalid) as seen:
            dos.read(trace)
        assert seen.value.code == "unexpected_answer", seen.value


def test_a_match_the_trace_gained_just_before_the_emulator_died_is_still_found(
        tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(b"")
    install()
    dstate.STATE.dos_calls = dos.Trace(path)

    class Dying:
        parked = False
        polls = 0

        def alive(self) -> bool:
            self.polls += 1
            if self.polls == 1:
                return True
            path.write_bytes(TRACE.read_bytes())
            return False

        def at_debugger(self) -> bool:
            return False

    got = dos.log_wait(cast(Any, Dying()), "MISSING", 5.0, 0, lambda *_a: None)
    assert got["verdict"] == "TARGET" and got["already"] is False, got


def test_a_repeated_pattern_searches_only_the_calls_that_can_still_change(
        monkeypatch: pytest.MonkeyPatch) -> None:
    trace = _read(TRACE)
    searched: list[str] = []

    class Counting:
        def search(self, line: str) -> object:
            searched.append(line)
            return None

    monkeypatch.setattr(dlogs, "compiled", lambda _pattern: Counting())
    dos._matching(trace, "ANY")
    first = len(searched)
    dos._matching(trace, "ANY")
    assert first == len(trace.calls) and len(searched) - first < first // 2, (first, searched)


def test_a_match_written_as_the_emulator_died_is_found_though_the_peek_at_the_debugger_fails(
        tmp_path: Path) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(b"")
    install()
    dstate.STATE.dos_calls = dos.Trace(path)

    class Gone:
        parked = False
        peeks = 0

        def alive(self) -> bool:
            return self.peeks < 2

        def at_debugger(self) -> bool:
            self.peeks += 1
            if self.peeks >= 2:
                path.write_bytes(TRACE.read_bytes())
                raise ds.Invalid("session_broken", "the debugger channel dropped")
            return False

    got = dos.log_wait(cast(Any, Gone()), "MISSING", 5.0, 0, lambda *_a: None)
    assert got["verdict"] == "TARGET", got


def test_a_call_that_arrives_in_the_last_poll_interval_is_found_not_timed_out(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "t.trace"
    path.write_bytes(b"")
    install()
    dstate.STATE.dos_calls = dos.Trace(path)
    sleep = time.sleep

    def arrives_while_asleep(seconds: float) -> None:
        path.write_bytes(TRACE.read_bytes())
        sleep(0.03)
    monkeypatch.setattr(time, "sleep", arrives_while_asleep)

    class Running:
        parked = False

        def alive(self) -> bool:
            return True

        def at_debugger(self) -> bool:
            return False

    got = dos.log_wait(cast(Any, Running()), "MISSING", 0.01, 0, lambda *_a: None)
    assert got["verdict"] == "TARGET", got


def test_a_read_renders_only_the_calls_it_gained(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = TRACE.read_bytes().splitlines(keepends=True)
    trace = dos.Trace(TRACE)
    seen: list[int] = []
    real = dos._render

    def counted(call: dict[str, Any]) -> str:
        seen.append(call["n"])
        return real(call)
    monkeypatch.setattr(dos, "_render", counted)
    dos.read(trace)
    first = len(seen)
    dos.read(trace)
    assert first >= len(trace.calls) and len(seen) == first, (first, len(seen), len(rows))
