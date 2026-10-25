"""The stub's recovery paths, each provoked through a faulty line put in at the session's seam.
`STUB_FAULTS_GUEST_DIR` points at a scratch stub with a recovery removed, to see a case red."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, cast

import pytest
import stub_faults
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_launch as dlaunch
import dosbox_session as ds
import dosbox_x_server as server

pytestmark = pytest.mark.live

GUEST = Path(__file__).resolve().parent.parent / "guest"
WAIT_S = 20
KEY_A = r"MOUSE \. key=97$"


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str) -> list[Any]:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    scratch = os.environ.get("STUB_FAULTS_GUEST_DIR")
    if scratch:
        monkeypatch.setattr(dlaunch, "GUEST_DIR", Path(scratch))
    made: list[Any] = []

    def line(sock: Any) -> Any:
        made.append(stub_faults.FaultyLine(sock, fault))
        return made[-1]

    monkeypatch.setattr(ds, "INPUT_LINE", line)
    r = cast(dict[str, Any], server.start(
        conf=str(GUEST / "mouse.conf"), cwd=str(GUEST), session_seconds=180,
        logfile=str(tmp_path / "guest.log"), program="MOUSE.COM"))
    assert r["status"] == "ok", r
    server.resume()
    reset = cast(dict[str, Any], server.log_wait(channel="guest", pattern=r"MOUSE \. reset",
                                                 seconds=WAIT_S))
    assert reset["status"] == "ok", reset
    return made


def _keys_logged(tmp_path: Path) -> int:
    text = (tmp_path / "guest.log").read_text(encoding="utf-8", errors="replace")
    return len([ln for ln in text.splitlines() if re.search(KEY_A, ln)])


def test_a_lost_acknowledgement_is_answered_by_a_repeat_that_runs_nothing_twice(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    [line] = _start(tmp_path, monkeypatch, "lose_ack")
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_A, seconds=WAIT_S))
    assert got["status"] == "ok", got
    assert line.acks_dropped == 1, "the fault was not provoked"
    server.log_wait(channel="guest", pattern=r"MOUSE \. key=", seconds=2)
    assert _keys_logged(tmp_path) == 1, "the key the lost acknowledgement left was run twice"


def test_a_frame_dribbled_across_ticks_is_assembled_and_carried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    [line] = _start(tmp_path, monkeypatch, "dribble")
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_A, seconds=WAIT_S))
    assert got["status"] == "ok", got
    assert line.frames_sent >= 2 and line.writes > line.frames_sent, "nothing was dribbled"
    assert _keys_logged(tmp_path) == 1


def test_a_short_frame_ages_out_and_the_next_send_is_carried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stub drops the cut first frame; the host's unacknowledged resend is the one run."""
    [line] = _start(tmp_path, monkeypatch, "short")
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_A, seconds=WAIT_S))
    assert got["status"] == "ok", got
    assert line.frames_sent == 3, f"{line.frames_sent} sends for two frames, one cut once"
    assert _keys_logged(tmp_path) == 1


def test_a_line_closed_mid_send_ends_the_call_at_once_as_a_broken_session(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _start(tmp_path, monkeypatch, "close")
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "INVALID" and got["code"] == "session_broken", got
    assert _keys_logged(tmp_path) == 0, "half a frame ran"
