"""The screen guest recorded with `capture_video`, cut into a series every file tool reads."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from live_private import guest_dir

import dosbox_x_server as server

pytestmark = pytest.mark.live

GUEST = guest_dir()
TO_13H = ("text", "start80", "dac01", "13h")


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="series_capture needs ffmpeg")
def test_the_screen_guests_capture_becomes_a_series_every_file_tool_reads(
        tmp_path: Path) -> None:
    _ok(server.start(conf=str(GUEST / "screen.conf"), cwd=str(GUEST), session_seconds=120,
                     program="SCREEN.COM", break_on_int3=True, capture_video=True,
                     captures_dir=str(tmp_path / "cap"), logfile=str(tmp_path / "x.log")))
    for _ in TO_13H:
        assert _ok(server.resume(seconds=30)).get("verdict") == "OTHER_STOP"
    view = _ok(server.screen_view())
    image = view["image"]
    assert image["inline"] is True and (image["width"], image["height"]) == (1280, 800)
    sig = _ok(server.screen_signature(crop=[0, 0, 32, 32]))
    assert len(sig["signature"]) == 16 and sig["kind"] == "pixel"
    assert _ok(server.resume(seconds=30)).get("verdict") == "OTHER_STOP"   # the display start moves
    listed = _ok(server.captures())["captures"]
    videos = [c for c in listed if c["kind"] == "avi"]
    assert videos, listed
    newest = max(videos, key=lambda c: str(c["path"]))
    count = min(int(newest["avi_frames"]), 10)
    assert count >= 2, newest
    series = _ok(server.series_capture(first=0, last=count - 1, capture_path=newest["path"],
                                       dest=str(tmp_path / "series")))
    assert series["count"] == count and series["frame_source"] == "avi"
    manifest = series["manifest"]
    frames = sorted((tmp_path / "series").glob("f*.png"))
    same = _ok(server.image_compare("image", a=str(frames[0]), b=str(frames[0])))
    assert same["differing_pixels"] == 0 and same["bbox"]["available"] is False
    # The guest moves the display start while it records, so the series changes: a series that
    # came out uniform is a capture that missed it, never a pass by the other branch.
    assert series["distinct"] > 1, series
    pair = _ok(server.image_compare("series", a=manifest, b=manifest))
    assert pair["identical"] == count, pair
    track = _ok(server.image_compare("region", manifest=manifest))
    assert track["transitions_total"] >= 1, track
    sums = tmp_path / "goldens.sha256"
    sums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                            for p in frames))
    gold = _ok(server.image_compare("golden", manifest=manifest, checksums=str(sums)))
    assert gold["matched"] == count and gold["differing"] == []
    _ok(server.close())
