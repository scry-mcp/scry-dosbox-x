"""`series_capture` out of a video capture: on a real AVI made here with the real ffmpeg, each frame
of the series is held against the one `capture_frame` extracts by itself; on a stubbed ffmpeg, each
refusal. The capture is DOSBox-X's codec (ZMBV), so the path is the one a session records."""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import png, raster

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dosbox_media as media  # noqa: E402
import dosbox_session as ds  # noqa: E402
import dosbox_state as dstate  # noqa: E402
import dosbox_x_server as server  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                  reason="series_capture's real path needs ffmpeg on PATH")
W, H, FRAMES = 64, 48, 12


class _Captures:
    """The one thing the tool asks of a session: what it captured."""

    def __init__(self, avi: Path, frames: int) -> None:
        self.avi, self.frames = avi, frames

    def captures(self) -> list[dict[str, object]]:
        return [{"path": str(self.avi), "frames": self.frames}]


def _avi(tmp_path: Path) -> Path:
    """A ZMBV capture of `FRAMES` frames of ffmpeg's test pattern, every frame unlike the last
    (its counter moves)."""
    avi = tmp_path / "cap.avi"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    f"testsrc=size={W}x{H}:rate=10", "-frames:v", str(FRAMES), "-c:v", "zmbv",
                    str(avi)], check=True, timeout=60)
    return avi


def _alone(avi: Path, frame: int, dest: Path) -> png.Raster:
    """Frame `frame` extracted by itself, as `capture_frame` extracts it, decoded to RGB."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(avi), "-vf",
                    f"select='eq(n\\,{frame})'", "-fps_mode", "passthrough", "-frames:v", "1",
                    "-f", "image2", "-c:v", "png", "-pix_fmt", "rgb24", str(dest)],
                   check=True, timeout=60)
    return png.decode(dest.read_bytes())


@needs_ffmpeg
def test_each_frame_of_a_series_is_the_frame_the_avi_holds_at_that_number(tmp_path: Path) -> None:
    avi = _avi(tmp_path)
    scratch = tmp_path / "scratch"
    out = media.series_capture(_Captures(avi, FRAMES), scratch, [2, 5, 9], None, None,  # type: ignore[arg-type]
                               1, None, "", None)
    manifest = Path(out["manifest"])
    assert manifest.parent == scratch / "series" / "series-1" and out["kept_after_close"] is False
    assert (out["count"], out["first"], out["last"], out["distinct"]) == (3, 2, 9, 3)
    assert out["frame_source"] == "avi" and out["source"] == str(avi)
    assert out["crop"] == [0, 0, W, H]
    for frame in (2, 5, 9):
        kept = png.decode((manifest.parent / f"f{frame:06d}.png").read_bytes())
        assert kept.pixels == raster.rgb(_alone(avi, frame, tmp_path / f"alone-{frame}.png")), frame
    assert sorted(p.name for p in manifest.parent.iterdir()) == [
        "f000002.png", "f000005.png", "f000009.png", "manifest.json"]
    assert json.loads(manifest.read_text())["source"] == "avi"


@needs_ffmpeg
def test_a_cropped_range_series_kept_in_its_dest(tmp_path: Path) -> None:
    avi = _avi(tmp_path)
    dest = tmp_path / "kept"
    out = media.series_capture(_Captures(avi, FRAMES), tmp_path / "s", None, 0, 10, 5,  # type: ignore[arg-type]
                               [8, 4, 16, 12], str(dest), str(avi))
    assert out["kept_after_close"] is True and Path(out["manifest"]).parent == dest
    assert out["first"] == 0 and out["last"] == 10 and out["count"] == 3
    whole = _alone(avi, 5, tmp_path / "whole.png")
    kept = png.decode((dest / "f000005.png").read_bytes())
    assert (kept.width, kept.height) == (16, 12)
    assert kept.pixels == raster.rgb(raster.cropped(whole, [8, 4, 16, 12]))


def _header(tmp_path: Path, width: int = W, height: int = H) -> Path:
    """An AVI's first chunks as far as the main header: all `avi_size` reads."""
    avih = struct.pack("<14I", 100000, 0, 0, 0, FRAMES, 0, 1, 0, width, height, 0, 0, 0, 0)
    avi = tmp_path / "head.avi"
    avi.write_bytes(b"RIFF" + bytes(4) + b"AVI LIST" + bytes(4) + b"hdrlavih"
                    + struct.pack("<I", len(avih)) + avih)
    return avi


def test_the_frame_size_is_the_avis_own_header(tmp_path: Path) -> None:
    assert media.avi_size(_header(tmp_path, 320, 200)) == (320, 200)
    (tmp_path / "x.avi").write_bytes(b"not an avi at all")
    with pytest.raises(ds.Invalid, match="no AVI main header"):
        media.avi_size(tmp_path / "x.avi")
    with pytest.raises(ds.Invalid, match="cannot be read"):
        media.avi_size(tmp_path / "absent.avi")
    # A writer that leaves the size to the stream header: a 0x0 frame would judge every crop
    # off it and echo `[0, 0, 0, 0]` beside frames of the real size.
    with pytest.raises(ds.Invalid, match="declares a 0x200 frame"):
        media.avi_size(_header(tmp_path, 0, 200))


def _stub(monkeypatch: pytest.MonkeyPatch, writes: int, rc: int = 0,
          hang: bool = False) -> list[list[str]]:
    """ffmpeg stubbed: it writes `writes` PNGs where it was told, exits `rc`, or hangs."""
    ran: list[list[str]] = []

    def run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        ran.append(argv)
        if hang:
            raise subprocess.TimeoutExpired(argv, 1)
        pattern = Path(argv[-1])
        for n in range(1, writes + 1):
            Path(str(pattern).replace("%06d", f"{n:06d}")).write_bytes(
                png.encode(png.Raster(W, H, bytes(W * H * 3))))
        return subprocess.CompletedProcess(argv, rc, "", "boom" if rc else "")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", run)
    return ran


@pytest.mark.parametrize("writes, rc, hang, said, code", [
    (2, 0, False, "holds 2 of the 3 frames asked: frame 3 is past its end", "bad_argument"),
    (3, 1, False, "ffmpeg exited 1", "host_failed"),
    (0, 0, True, "did not return within", "host_failed"),
])
def test_an_ffmpeg_that_failed_or_wrote_short_is_refused_and_leaves_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, writes: int, rc: int, hang: bool,
        said: str, code: str) -> None:
    ran = _stub(monkeypatch, writes, rc, hang)
    dest = tmp_path / "kept"
    with pytest.raises(ds.Invalid, match=said) as e:
        media.series_capture(_Captures(_header(tmp_path), FRAMES), tmp_path / "s",  # type: ignore[arg-type]
                             [1, 2, 3], None, None, 1, None, str(dest), None)
    assert e.value.code == code and not dest.exists()
    assert ran[0][ran[0].index("-frames:v"):ran[0].index("-frames:v") + 2] == ["-frames:v", "3"]
    graph = ran[0][ran[0].index("-vf") + 1]
    assert graph == "select='eq(n\\,1)+eq(n\\,2)+eq(n\\,3)'"
    assert ran[0][ran[0].index("-pred"):ran[0].index("-pred") + 2] == ["-pred", "none"]


def test_what_ffmpeg_is_never_asked_about(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _stub(monkeypatch, 3)
    head = _header(tmp_path)
    session = _Captures(head, FRAMES)
    with pytest.raises(ds.Invalid, match="leaves the capture's 64x48 frames"):
        media.series_capture(session, tmp_path / "s", [1], None, None, 1, [60, 0, 8, 8], "",  # type: ignore[arg-type]
                             None)
    with pytest.raises(ds.Invalid, match="containing `%`"):
        media.check_series_capture(frames=[1], dest=str(tmp_path / "run%d"))
    assert ran == [], "every refusal above came before ffmpeg was run"
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ds.Invalid, match="there is none on PATH") as e:
        media.series_capture(session, tmp_path / "s", [1], None, None, 1, None, "", None)  # type: ignore[arg-type]
    assert e.value.code == "host_failed"


def test_a_second_series_in_the_scratch_takes_the_next_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, 1)
    session = _Captures(_header(tmp_path), FRAMES)
    names = [Path(media.series_capture(session, tmp_path / "s", [1], None, None, 1, None, "",  # type: ignore[arg-type]
                                       None)["manifest"]).parent.name for _ in range(2)]
    assert names == ["series-1", "series-2"]
    (tmp_path / "there").mkdir()
    with pytest.raises(ds.Invalid, match="already exists"):
        media.series_capture(session, tmp_path / "s", [1], None, None, 1, None,  # type: ignore[arg-type]
                             str(tmp_path / "there"), None)


def test_a_dest_that_cannot_be_made_is_refused(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, 1)

    def denied(self: Path, *_: Any, **__: Any) -> None:
        raise PermissionError("read-only")
    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(ds.Invalid, match="cannot be created: read-only") as e:
        media.series_capture(_Captures(_header(tmp_path), FRAMES), tmp_path / "s", [1], None,  # type: ignore[arg-type]
                             None, 1, None, str(tmp_path / "kept"), None)
    assert e.value.code == "bad_argument"


@needs_ffmpeg
def test_a_frame_past_the_real_end_is_refused_by_name(tmp_path: Path) -> None:
    """The capture holds 12 frames, whatever a count of its `00dc` tags says (its index carries
    one per frame again): frame 13 is past its end."""
    avi = _avi(tmp_path)
    assert avi.read_bytes().count(b"00dc") > FRAMES, "the tag count overstates, the control"
    with pytest.raises(ds.Invalid, match="holds 2 of the 3 frames asked: frame 13 is past") as e:
        media.series_capture(_Captures(avi, 2 * FRAMES), tmp_path / "s", [10, 11, 13], None,  # type: ignore[arg-type]
                             None, 1, None, "", None)
    assert e.value.code == "bad_argument"


@needs_ffmpeg
def test_the_avi_s_frames_are_numbered_from_zero(tmp_path: Path) -> None:
    """Frame 0 is the capture's first, the one ffmpeg extracts with no selection at all; frame
    11 its last of 12, and frame 12 one past the end."""
    avi = _avi(tmp_path)
    out = media.series_capture(_Captures(avi, FRAMES), tmp_path / "s", [0, 11], None, None,  # type: ignore[arg-type]
                               1, None, "", None)
    first = tmp_path / "first.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(avi), "-frames:v", "1", "-f",
                    "image2", "-c:v", "png", "-pix_fmt", "rgb24", str(first)],
                   check=True, timeout=60)
    kept = png.decode((Path(out["manifest"]).parent / "f000000.png").read_bytes())
    assert kept.pixels == raster.rgb(png.decode(first.read_bytes()))
    with pytest.raises(ds.Invalid, match="holds 1 of the 2 frames asked: frame 12 is past"):
        media.series_capture(_Captures(avi, FRAMES), tmp_path / "t", [11, 12], None, None,  # type: ignore[arg-type]
                             1, None, "", None)


@needs_ffmpeg
def test_series_capture_answers_through_this_server_with_its_paths_where_they_were_named(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The registered tool, not the module function: `dest` keeps the series past `close`,
    `source` names the capture read, and the reply wears this server's envelope."""
    avi = _avi(tmp_path)
    other = tmp_path / "other.avi"
    shutil.copy(avi, other)
    session = _Captures(avi, FRAMES)
    session.captures = lambda: [{"path": str(avi), "frames": FRAMES},  # type: ignore[method-assign]
                                {"path": str(other), "frames": FRAMES}]
    monkeypatch.setattr(server, "live", lambda: session)
    monkeypatch.setattr(dstate.STATE, "session_scratch", lambda: tmp_path / "scratch")
    dest = tmp_path / "kept"
    r = cast(dict[str, Any], server.series_capture(first=0, last=1, crop=[0, 0, 8, 4],
                                                   dest=str(dest), source=str(avi)))
    assert r["status"] == "ok" and "session" in r, r
    assert r["kept_after_close"] is True and Path(r["manifest"]).parent == dest, r
    assert r["source"] == str(avi) and r["crop"] == [0, 0, 8, 4] and r["count"] == 2, r


def test_a_media_file_tool_answers_in_this_server_s_envelope(tmp_path: Path) -> None:
    """The file tools' bodies are scry-core's and answer bare fields; through this server each
    wears the envelope every other reply wears: `status`, `session` and its own summary."""
    pic = tmp_path / "a.png"
    pic.write_bytes(png.encode(png.Raster(2, 2, bytes(12))))
    r = cast(dict[str, Any], server.image_diff(a=str(pic), b=str(pic)))
    assert r["status"] == "ok" and "session" in r, r
    assert r["summary"].startswith("image_diff: no pixel differs"), r["summary"]
