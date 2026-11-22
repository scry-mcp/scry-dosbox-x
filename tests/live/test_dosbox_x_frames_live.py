"""Frame k of a session's video is the emulator frame the decorator takes it for."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from live_private import guest_dir

from scry_dosbox_x import server

pytestmark = pytest.mark.live

GUEST = guest_dir()
TAIL = 30
#: Distinct, so a miscount cannot cancel out.
RUNS = (3, 4, 5, 6)
STOPS = 6


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="series_capture needs ffmpeg")
def test_a_picture_written_at_a_counted_stop_first_shows_in_the_video_frame_the_count_names(
        tmp_path: Path) -> None:
    """The decorator counts a place back from the end of the video, whose last frame is the last
    one a reply counted: a byte written at counted frame `c` shows first in video frame
    `c - (counter - held)`."""
    _ok(server.start(conf=str(GUEST / "screen.conf"), cwd=str(GUEST), session_seconds=120,
                     program="SCREEN.COM", break_on_int3=True, capture_video=True,
                     captures_dir=str(tmp_path / "cap"), logfile=str(tmp_path / "x.log")))
    for _ in range(STOPS):
        assert _ok(server.resume(seconds=30)).get("verdict") == "OTHER_STOP"
    assert _ok(server.resume(seconds=2))["verdict"] == "TIMEOUT"
    _ok(server.stop())
    placed: list[int] = []
    counter = _ok(server.run_for(frames=1))["frame_after"]
    for offset, frames in enumerate(RUNS):
        _ok(server.write(ref=f"A000:{offset:04X}", data_hex="FF"))
        placed.append(counter)
        counter = _ok(server.run_for(frames=frames))["frame_after"]
    videos = [c for c in _ok(server.captures())["captures"] if c["kind"] == "avi"]
    newest = max(videos, key=lambda c: str(c["path"]))
    held = int(newest["avi_frames"])
    first = held - TAIL
    series = _ok(server.series_capture(first=first, last=held - 1, capture_path=newest["path"],
                                       dest=str(tmp_path / "series")))
    digests = [hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((tmp_path / "series").glob("f*.png"))]
    assert len(digests) == series["count"] == TAIL, series
    changed = [first + i for i in range(1, TAIL) if digests[i] != digests[i - 1]]
    expected = [c - (counter - held) for c in placed]
    assert changed == expected, (
        f"a byte written at counted frames {placed} first shows in video frames {changed}, "
        f"where the counter's last frame {counter} against the video's {held} says {expected}")
    _ok(server.close())
