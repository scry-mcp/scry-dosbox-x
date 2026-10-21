"""Arguments at their edges, each judge at its maximum and one past it, and the small seams a
tool hands its arguments through: the counts a caller can reach, said exactly."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import dosbox_captures as captures
import dosbox_inputs as inputs
import dosbox_session as ds
import dosbox_state as dstate


def test_a_key_list_takes_its_maximum_and_refuses_one_more() -> None:
    inputs.check_keys(["a"] * inputs.MAX_KEYS_PER_CALL, None)
    with pytest.raises(ds.Invalid) as e:
        inputs.check_keys(["a"] * (inputs.MAX_KEYS_PER_CALL + 1), None)
    assert e.value.code == "bad_argument"


def test_a_directory_where_a_capture_was_is_listed_as_not_present(tmp_path: Path) -> None:
    (tmp_path / "shot.png").mkdir()
    assert captures._row("png", tmp_path / "shot.png") == {
        "kind": "png", "path": str(tmp_path / "shot.png"), "present": False}


def test_capture_frame_hands_its_frame_number_to_the_session(tmp_path: Path) -> None:
    asked: list[Any] = []
    out = tmp_path / "f.png"
    out.write_bytes(b"\x89PNG\r\n\x1a\n")

    def frame(at: int, dest: Path, source: Path | None = None) -> Path:
        asked.append((at, dest, source))
        return out

    session = cast(ds.Session, SimpleNamespace(
        frame=frame, state=lambda: {"alive": True, "running": False, "altered": False}))
    dstate.STATE.session = session
    try:
        got = captures.capture_frame(session, 7, out, tmp_path / "v.avi")
    finally:
        dstate.STATE.session = None
    assert asked == [(7, out, tmp_path / "v.avi")] and got["frame"] == 7, got
