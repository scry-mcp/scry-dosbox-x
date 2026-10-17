"""`series_capture`: frames out of the session's video capture, written as a `scry-series/1`
series (`scry_core.series`): PNGs and one manifest, no picture in the reply.

WHY FROM THE AVI. DOS has no frame counter a stop can read, and a stop per retrace has no measured
route, so the one headless record of frames is the capture `start(capture_video=True)` writes. Its
frames are numbered by the file's own index from 0: what the series calls frame N is the AVI's
N-th frame, not an emulated frame number, and the reply's `frame_source` says so.

ONE FFMPEG PASS. A `select` over the frame numbers keeps the frames asked for, a `crop` filter
cuts the region, and ffmpeg writes the PNGs itself (`-f image2`), each read back here through
`scry_core.png` for its signature and its hash. The pixels are written RGB with no row
prediction (`-pix_fmt rgb24 -pred none`), so a palette AVI and a direct-colour one come out
alike and every frame decodes at the cost of a copy. The crop is judged against the size the
AVI's own header (`avih`) declares, before ffmpeg runs.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

from scry_core import fresh, judges, raster, series

import dosbox_paths as paths
import dosbox_session as ds

#: How long the one ffmpeg pass may take: a thousand frames of a DOS screen, with room.
SERIES_FFMPEG_SECS = 300
#: The AVI main header: its tag, and where its width and height lie among its fourteen DWORDs.
AVIH = b"avih"
AVIH_WIDTH_DWORD = 8
#: How far into an AVI its main header is looked for: it is the first chunk of `hdrl`.
AVIH_WITHIN = 4096


def check_series_capture(frames: list[int] | None = None, first: int | None = None,
                         last: int | None = None, step: int = 1, crop: list[int] | None = None,
                         dest: str = "", source: str | None = None, **_: Any) -> None:
    """`series_capture`'s machine-independent half: the frames, the crop's shape, and the two
    paths absolute, with no `%` (ffmpeg's image2 muxer reads one as a numbering template)."""
    series.frame_list(frames, first, last, step)
    if crop is not None:
        judges.rect("crop", crop)
    if source:
        paths.absolute("source", source)
    if dest:
        path = paths.absolute("dest", dest)
        if "%" in str(path):
            raise ds.Invalid("bad_argument", f"dest: a path containing `%` is refused: "
                             f"{str(path)!r}. ffmpeg's image2 muxer reads it as a numbering "
                             "template and writes somewhere else")


def avi_size(path: Path) -> tuple[int, int]:
    """The frame size an AVI's main header declares, or the refusal naming what is missing."""
    try:
        with path.open("rb") as f:
            head = f.read(AVIH_WITHIN)
    except OSError as e:
        raise ds.Invalid("bad_argument", f"source: {path} cannot be read: {e}") from None
    at = head.find(AVIH)
    body = head[at + 8:at + 8 + 14 * 4] if at >= 0 else b""
    if not head.startswith(b"RIFF") or len(body) < 14 * 4:
        raise ds.Invalid("bad_argument", f"source: {path} has no AVI main header (`avih`) in "
                         f"its first {AVIH_WITHIN} bytes, so its frame size is unknown")
    width, height = struct.unpack_from("<II", body, AVIH_WIDTH_DWORD * 4)
    if not (width and height):
        raise ds.Invalid("bad_argument", f"source: {path}'s main header (`avih`) declares a "
                         f"{width}x{height} frame, so its frame size is unknown")
    return width, height


def _folder(scratch: Path, dest: str) -> tuple[Path, bool]:
    """The series' directory: `dest`, created now, or a numbered one in the session's scratch,
    gone at `close`; and whether it outlives the session."""
    if dest:
        path = paths.fresh_dest("dest", dest)
        try:
            path.mkdir()
        except OSError as e:
            raise ds.Invalid("bad_argument", f"dest: {path} cannot be created: {e}") from None
        return path, True
    return fresh.numbered_dir(scratch / "series", lambda n: f"series-{n}", "the series"), False


def select_expression(wanted: list[int]) -> str:
    """ffmpeg's `select` expression keeping exactly the frames `wanted`, its commas escaped
    as a filter graph needs them."""
    return "+".join(f"eq(n\\,{f})" for f in wanted)


def series_capture(session: ds.Session, scratch: Path, frames: list[int] | None,
                   first: int | None, last: int | None, step: int, crop: list[int] | None,
                   dest: str, source: str | None) -> dict[str, Any]:
    """The body of the `series_capture` tool."""
    check_series_capture(frames, first, last, step, crop, dest, source)
    if shutil.which("ffmpeg") is None:
        raise ds.Invalid("host_failed", "a series is extracted from the capture with `ffmpeg`, "
                         "and there is none on PATH")
    wanted = series.frame_list(frames, first, last, step)
    # A FRAME PAST THE END is told by ffmpeg, which reads the file's frames, and not by the
    # count `captures` gives: that count reads the `00dc` tag, which a finished AVI's index
    # carries again for every frame.
    src = (paths.input_file("source", source, "capture") if source
           else Path(str(session.captures()[-1]["path"])))
    width, height = avi_size(src)
    area = raster.inside(crop, width, height, f"the capture's {width}x{height} frames")
    folder, kept = _folder(scratch, dest)
    try:
        _extract(src, folder, wanted, area if crop is not None else None)
        reply = series.write_manifest(folder, "dosbox-x", "avi", crop, wanted)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {**reply, "frames_asked": len(wanted), "kept_after_close": kept,
            "frame_source": "avi", "source": str(src), "crop": list(area)}


def _extract(src: Path, folder: Path, wanted: list[int],
             area: tuple[int, int, int, int] | None) -> None:
    """The one ffmpeg pass, its PNGs renamed by the frame each one is; a pass that wrote fewer
    than asked is refused naming how many came out."""
    graph = f"select='{select_expression(wanted)}'"
    if area is not None:
        x, y, w, h = area
        graph += f",crop={w}:{h}:{x}:{y}"
    try:
        got = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", graph,
             "-fps_mode", "passthrough", "-frames:v", str(len(wanted)), "-f", "image2",
             "-c:v", "png", "-pred", "none", "-pix_fmt", "rgb24",
             str(folder / "raw-%06d.png")],
            capture_output=True, text=True, errors="replace", check=False,
            timeout=SERIES_FFMPEG_SECS)
    except subprocess.TimeoutExpired:
        raise ds.Invalid("host_failed", f"`ffmpeg` did not return within {SERIES_FFMPEG_SECS}s "
                         f"extracting {len(wanted)} frames from {src}") from None
    out = sorted(folder.glob("raw-*.png"))
    said = (got.stdout + got.stderr).strip()[-300:]
    if got.returncode != 0:
        raise ds.Invalid("host_failed", f"ffmpeg exited {got.returncode} extracting frames "
                         f"from {src} and said: {said!r}")
    if len(out) != len(wanted):
        missing = wanted[len(out)]
        raise ds.Invalid("bad_argument", f"{src} holds {len(out)} of the {len(wanted)} frames "
                         f"asked: frame {missing} is past its end (frames are numbered from 0)")
    for raw, frame in zip(out, wanted, strict=True):
        raw.rename(folder / series.frame_name(frame))
