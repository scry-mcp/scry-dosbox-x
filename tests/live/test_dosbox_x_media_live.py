"""The media tools through the server against a real DOSBox-X: the screen guest
(`tests/guest/screen.asm`) recorded with `capture_video`, its 13h screen attached, a series cut
out of its capture and every file tool asked about that series, headless."""
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
#: The screen guest's steps up to its 13h picture, each ending in `int 3`.
TO_13H = ("text", "start80", "dac01", "13h")


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="series_capture needs ffmpeg")
def test_the_screen_guests_capture_becomes_a_series_every_file_tool_reads(
        tmp_path: Path) -> None:
    _ok(server.start(conf=str(GUEST / "screen.conf"), cwd=str(GUEST), seconds=120,
                     program="SCREEN.COM", break_on_int3=True, capture_video=True,
                     captures_dir=str(tmp_path / "cap"), logfile=str(tmp_path / "x.log")))
    for _ in TO_13H:
        assert _ok(server.resume(seconds=30)).get("halted") is True
    view = _ok(server.screen_view())
    image = view["image"]
    assert image["inline"] is True and (image["width"], image["height"]) == (1280, 800)
    sig = _ok(server.screen_signature(crop=[0, 0, 32, 32]))
    assert len(sig["signature"]) == 16 and sig["kind"] == "pixel"
    assert _ok(server.resume(seconds=30)).get("halted") is True      # the display start moves
    newest = max(_ok(server.captures())["captures"], key=lambda c: str(c["path"]))
    count = min(int(newest["frames"]), 10)
    assert count >= 2, newest
    series = _ok(server.series_capture(first=0, last=count - 1, source=newest["path"],
                                       dest=str(tmp_path / "series")))
    assert series["count"] == count and series["frame_source"] == "avi"
    manifest = series["manifest"]
    frames = sorted((tmp_path / "series").glob("f*.png"))
    same = _ok(server.image_diff(a=str(frames[0]), b=str(frames[0])))
    assert same["differing_pixels"] == 0 and same["bbox"] is None
    pair = cast(dict[str, Any], server.series_diff(a=manifest, b=manifest))
    moving = series["distinct"] > 1
    assert (pair.get("identical") == count) if moving else pair["code"] == "control_silent"
    track = cast(dict[str, Any], server.region_track(manifest=manifest))
    assert (track.get("transitions_total", 0) >= 1) if moving else (
        track["code"] == "control_silent")
    sums = tmp_path / "goldens.sha256"
    sums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                            for p in frames))
    gold = _ok(server.golden_check(manifest=manifest, checksums=str(sums)))
    assert gold["matched"] == count and gold["differing"] == []
    _ok(server.close())
