"""The recorded video, listed, and a still extracted from it with `ffmpeg`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from scry_core.reply_contract import Invalid

from scry_dosbox_x import paths
from scry_dosbox_x import session as ds


def folder(ses: ds.Session) -> Path:
    """Where the emulator writes a capture."""
    given = ses.launch.captures_dir
    return given if given is not None else ses.launch.cwd / "capture"


def videos(ses: ds.Session) -> list[dict[str, object]]:
    """The video this session recorded, largest last, with frame count and index.

    Two files is normal: DX-CAPTURE restarts when the guest changes video mode."""
    where = folder(ses)
    if not ses.launch.capture_video or not where.is_dir():
        return []
    out: list[dict[str, object]] = []
    # Keyed by size and mtime: `captures` is polled, and re-reading every file per poll is the cost.
    fresh: dict[tuple[str, int, int], dict[str, object]] = {}
    for f in where.glob("*.avi"):
        try:
            stat = f.stat()
            key = (str(f), stat.st_size, stat.st_mtime_ns)
            facts = ses._avi_facts.get(key)
            if facts is None:
                facts = ds.avi_facts(f.read_bytes())
        except FileNotFoundError:
            continue
        fresh[key] = facts
        out.append({"path": str(f), **facts})
    ses._avi_facts = fresh
    return sorted(out, key=lambda row: int(str(row["bytes"])))


def captures(ses: ds.Session) -> list[dict[str, object]]:
    """The video a still is taken out of, refused when there is none."""
    if not ses.launch.capture_video:
        raise Invalid("no_channel", "this session was not started with capture_video, so "
                      "nothing was recording. That is not an empty capture, it "
                      "is no capture")
    out = videos(ses)
    if not out:
        raise Invalid("unexpected_answer",
            f"no .avi file in {folder(ses)}, and that absence is all this saw. The causes "
            f"known: the recording stops when the captured PROGRAM exits, so a session "
            f"still running may not have written one yet; the program was never reached, "
            f"because `program` is passed with `-c`, which runs AFTER the conf's [autoexec] "
            f"section (a conf whose autoexec ends in `exit` quits before it); or the "
            f"emulator wrote it somewhere else")
    return out


def frame(ses: ds.Session, at: int, dest: Path, source: Path) -> Path:
    """One still out of the capture at frame `at`; always a PNG, whatever `dest` is named.

    From the video because DOSBox-X's screenshot needs a keypress."""
    if shutil.which("ffmpeg") is None:
        raise Invalid("host_failed", "a still is extracted from the capture with `ffmpeg`, and "
                      "there is none on PATH. The video itself does not need it; "
                      "only this does")
    ds.check_frame_args(at, dest)
    paths.fresh_dest("dest", dest)
    # A `%` anywhere in `dest` is refused: `-f image2` treats the whole path as a printf
    # template, so the PNG can land at a path the caller never named. Broader than the hazard
    # on purpose: a false refusal is loud, the other failure is silent.
    try:
        got = subprocess.run(
            # Format forced: else a frame past the end with an `.mp4` dest writes a frameless
            # container at rc=0.
            ["ffmpeg", "-v", "error", "-y", "-i", str(source),
             "-vf", f"select='eq(n\\,{at})'", "-fps_mode", "passthrough",
             "-frames:v", "1", "-f", "image2", "-c:v", "png", str(dest)],
            capture_output=True, text=True, errors="replace", check=False,
            timeout=ds.FFMPEG_SECS)
    except subprocess.TimeoutExpired:
        # Not a raw traceback: `tool()` translates only `Invalid`.
        raise Invalid("host_failed", f"`ffmpeg` did not return within {ds.FFMPEG_SECS}s pulling "
                      f"frame {at} from {source}. That is the tool hanging, not an "
                      f"answer about the capture") from None
    if got.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        # rc!=0 is ffmpeg's own failure; rc=0 with no output leaves the cause a guess.
        said = (got.stdout + got.stderr).strip()[-300:]
        if got.returncode != 0:
            raise Invalid("host_failed",
                f"ffmpeg exited {got.returncode} extracting frame {at} "
                          f"from {source} and said: {said!r}. Any file it left behind "
                          f"is not a frame")
        raise Invalid("host_failed",
            f"ffmpeg exited 0 but no image came out of {source} at frame {at}. It "
            f"said: {said!r}. The commonest cause is a frame past the end: "
            f"`captures` reports how many there are; an unindexed capture is not the "
            f"cause, a frame comes out of one fine")
    # Cheap guard against a well-formed file of the wrong kind.
    if dest.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise Invalid("host_failed",
            f"what ffmpeg left at {dest} is not a PNG, so it is not the "
                      f"still that was asked for")
    return dest
