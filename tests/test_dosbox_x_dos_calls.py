"""The DOS channel, read from the trace `DOSTRACE` wrote over the DOS guest's run
(`tests/fixtures/hardware/dosio.trace`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import install
from scry_core.reply_contract import Invalid

import dosbox_dos_calls as dos
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

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
