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
AVI's own header (`avih`, `scry_core.avi`) declares, before ffmpeg runs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from scry_core import avi, fresh, judges, media_tools, raster, series

import dosbox_paths as paths
import dosbox_session as ds

#: How long the one ffmpeg pass may take: a thousand frames of a DOS screen, with room.
SERIES_FFMPEG_SECS = 300
#: The media file tools this server publishes, named once for its registration, its sequences and
#: its pre-gate: the image layer's; the sound layer's join the day a session records a WAV.
MEDIA_TOOLS = media_tools.IMAGE_TOOLS
#: What a series' frame numbers count here: the capture file's own frames, from 0.
FRAME_SOURCE = "avi"

def check_series_capture(frames: list[int] | None = None, first: int | None = None,
                         last: int | None = None, step: int = 1, crop: list[int] | None = None,
                         dest: str = "", capture_path: str = "", **_: Any) -> None:
    """`series_capture`'s machine-independent half: the frames, the crop's shape, and the two
    paths absolute, with no `%` (ffmpeg's image2 muxer reads one as a numbering template)."""
    series.frame_list(frames, first, last, step)
    if crop is not None:
        judges.rect("crop", crop)
    if capture_path:
        paths.absolute("capture_path", capture_path)
    if dest:
        path = paths.absolute("dest", dest)
        if "%" in str(path):
            raise ds.Invalid("bad_argument", f"dest: a path containing `%` is refused: "
                             f"{str(path)!r}. ffmpeg's image2 muxer reads it as a numbering "
                             "template and writes somewhere else")


def select_expression(wanted: list[int]) -> str:
    """ffmpeg's `select` expression keeping exactly the frames `wanted`, its commas escaped
    as a filter graph needs them."""
    return "+".join(f"eq(n\\,{f})" for f in wanted)


def series_capture(session: ds.Session, scratch: Path, frames: list[int] | None,
                   first: int | None, last: int | None, step: int, crop: list[int] | None,
                   dest: str, capture_path: str) -> dict[str, Any]:
    """The body of the `series_capture` tool."""
    check_series_capture(frames, first, last, step, crop, dest, capture_path)
    if shutil.which("ffmpeg") is None:
        raise ds.Invalid("host_failed", "a series is extracted from the capture with `ffmpeg`, "
                         "and there is none on PATH")
    wanted = series.frame_list(frames, first, last, step)
    # A FRAME PAST THE END is told by ffmpeg, which reads the file's frames.
    src = (paths.input_file("capture_path", capture_path, "capture") if capture_path
           else Path(str(session.captures()[-1]["path"])))
    width, height = avi.size("capture_path", src)
    area = raster.inside(crop, width, height, f"the capture's {width}x{height} frames")
    folder = fresh.directory(paths.fresh_dest("dest", dest) if dest else None,
                             scratch / "series", lambda n: f"series-{n}", "the series")
    with fresh.taken_back(folder):
        _extract(src, folder, wanted, area if crop is not None else None)
        reply = series.write_manifest(folder, "dosbox-x", FRAME_SOURCE, crop, wanted)
    return {**reply, **series.tail(len(wanted), bool(dest), FRAME_SOURCE), "capture_path": str(src),
            "crop": list(area)}


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
