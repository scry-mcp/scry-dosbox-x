"""The video a session recorded, listed, and a still taken out of it with `ffmpeg`. Its own
module because the capture format and the extractor change for reasons of their own; each
function is a session method's body, and `Session` delegates to it."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from scry_core.reply_contract import Invalid

import dosbox_paths as paths
import dosbox_session as ds


def folder(ses: ds.Session) -> Path:
    """Where the emulator writes a capture: `captures_dir`, else `capture/` under its working
    directory, which is DOSBox-X's own default."""
    given = ses.launch.captures_dir
    return given if given is not None else ses.launch.cwd / "capture"


def videos(ses: ds.Session) -> list[dict[str, object]]:
    """The video this session recorded, largest last, each with what is IN it: its frame count
    and its index, not just its size, because a capture that recorded nothing and one that
    recorded the whole session are both files of plausible sizes. None when it records nothing.

    TWO FILES IS THE NORMAL CASE, not a fault: DX-CAPTURE restarts its recording when the guest
    changes video mode, so a program that boots in DOS text and then goes graphical leaves a
    small first file and the real one after it."""
    where = folder(ses)
    if not ses.launch.capture_video or not where.is_dir():
        return []
    out: list[dict[str, object]] = []
    # THE FACTS OF A FILE THAT HAS NOT CHANGED ARE THE FACTS READ LAST TIME: `captures` is
    # polled while a recording runs, and reading every capture whole at each poll to count its
    # frames is the cost. One entry per file, keyed by its size AND its modification time, so a
    # file replaced by another of the same size is read again; the entries of files no longer
    # listed leave with this rebuild. A file the emulator removed between the listing and the
    # read is not listed.
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
    """The video a still is taken out of, refused when there is none: `videos`, largest last."""
    if not ses.launch.capture_video:
        raise Invalid("no_channel", "this session was not started with capture_video, so "
                      "nothing was recording. That is not an empty capture, it "
                      "is no capture")
    out = videos(ses)
    if not out:
        raise Invalid("unexpected_answer",
            f"no capture appeared in {folder(ses)}. Two causes, and "
            f"they need different answers: the recording stops when the captured "
            f"PROGRAM exits, so a session still running may not have written one "
            f"yet; OR the program never started, because `program` is passed with "
            f"`-c`, which runs AFTER the conf's [autoexec] section -- a conf whose "
            f"autoexec ends in `exit` quits before it is reached")
    return out


def frame(ses: ds.Session, at: int, dest: Path, source: Path | None = None) -> Path:
    """ONE still image out of the capture, at frame `at`.

    WHY IT COMES FROM THE VIDEO AND NOT FROM THE EMULATOR. DOSBox-X's own
    screenshot is a MAPPER action and needs a keypress, so there is no
    non-interactive trigger for it; the video does have one. The still is
    therefore an extraction, and it requires the capture to have been recording.

    `ffmpeg` is an OPTIONAL dependency and its absence is said out loud rather
    than worked around: a tool that quietly produces nothing is worse than one
    that names what is missing.

    IT ALWAYS WRITES A PNG, whatever `dest` is called, and the caller is told so
    here because nothing in the reply says it. The encoder is forced rather than
    inferred from the extension: see the argv below for what inferring it was
    measured doing.
    """
    if shutil.which("ffmpeg") is None:
        raise Invalid("host_failed", "a still is extracted from the capture with `ffmpeg`, and "
                      "there is none on PATH. The video itself does not need it; "
                      "only this does")
    ds.check_frame_args(at, dest)
    paths.fresh_dest("dest", dest)
    src = source or Path(str(ses.captures()[-1]["path"]))
    # A `%` ANYWHERE IN THE DESTINATION IS REFUSED. `-f image2` treats the WHOLE
    # PATH as a printf template, so `shot%03d.png` makes ffmpeg write `shot001.png`
    # and leave `dest` untouched -- after which this method refuses, blaming "a
    # frame past the end" for an extraction that worked perfectly.
    #
    # IT IS `str(dest)` AND NOT `dest.name`: what ffmpeg opens is the EXPANDED
    # path, so a `%` in a parent misplaces the still exactly as one in the name
    # does, and the name alone covers the half a caller is least likely to write.
    #
    # THE OUTCOME DEPENDS ON WHETHER THE EXPANSION ALREADY EXISTS, and both halves
    # were observed: with a literal `run%d/` directory there and `run1/` absent,
    # ffmpeg fails with nothing written anywhere, and with
    # it present it writes a perfectly good PNG there, at a path the caller never
    # named and with no error. The second is the one worth refusing for, and it
    # cannot be told from the first in advance.
    #
    # It is deliberately broader than the hazard: ffmpeg leaves a `%` with no valid
    # conversion alone (`fifty%.png` is written as itself), so those are refused
    # unnecessarily. That direction fails loudly and the other fails silently.
    #
    # `dest` is judged absent by `paths.fresh_dest` above, so whatever sits there
    # after ffmpeg is this extraction and not a stale image: nothing is deleted to
    # make that true.
    try:
        got = subprocess.run(
            # THE FORMAT IS FORCED, and this is not tidiness: without it ffmpeg
            # picks the encoder from `dest`'s EXTENSION, which is the caller's.
            # MEASURED on ffmpeg 9.0.1 with this exact argv: asking for a frame
            # PAST THE END of a real capture writes nothing for a `.png`
            # destination but a 1307-byte FRAMELESS CONTAINER for an `.mp4` one,
            # at exit code ZERO -- so every term of the guard below was false and
            # `frame()` handed that container back as a still. With the format
            # forced, the same request writes NO FILE and the guard fires.
            #
            # It also means this tool's promise ("ONE still image") no longer
            # depends on the caller spelling the extension the way it meant.
            ["ffmpeg", "-v", "error", "-y", "-i", str(src),
             "-vf", f"select='eq(n\\,{at})'", "-fps_mode", "passthrough",
             "-frames:v", "1", "-f", "image2", "-c:v", "png", str(dest)],
            capture_output=True, text=True, check=False, timeout=ds.FFMPEG_SECS)
    except subprocess.TimeoutExpired:
        # AS `Invalid`, NOT AS A TRACEBACK. `tool()` translates only `Invalid`, so
        # this escaped raw while `build_check` catches the same exception twelve
        # lines of comment deep for the same reason. Two of this module's contracts
        # break at once when it escapes: the reply stops saying WHICH nothing it
        # found, and it stops carrying the session's state at all.
        raise Invalid("host_failed", f"`ffmpeg` did not return within {ds.FFMPEG_SECS}s pulling "
                      f"frame {at} from {src}. That is the tool hanging, not an "
                      f"answer about the capture") from None
    # THE EXIT CODE IS READ, and it was not. MEASURED on ffmpeg 7.x: a frame past
    # the end of a capture writes NO file for a `.png` destination but a 261-byte
    # frameless container for an `.mp4` one, so "a file exists and is non-empty" is
    # not the same question as "ffmpeg succeeded". Only the size was asked.
    if got.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        # THE TWO ARMS SAY DIFFERENT THINGS, because they ARE different things and
        # merging them picks a cause. A non-zero exit code is ffmpeg reporting its
        # own failure and the reason is in hand; an empty or absent output with a
        # ZERO code is the frame-past-the-end shape, where the cause is a guess.
        # This module's rule, stated in `wait_ready`: INVALID names what was seen.
        said = (got.stdout + got.stderr).strip()[-300:]
        if got.returncode != 0:
            raise Invalid("host_failed",
                f"ffmpeg exited {got.returncode} extracting frame {at} "
                          f"from {src} and said: {said!r}. Any file it left behind "
                          f"is not a frame")
        raise Invalid("host_failed",
            f"ffmpeg exited 0 but no image came out of {src} at frame {at}. It "
            f"said: {said!r}. The commonest cause is a frame past the end: "
            f"`captures` reports how many there are; an unindexed capture is not the "
            f"cause, a frame comes out of one fine")
    # AND THE BYTES ARE AN IMAGE. Forcing the format above should make this
    # unreachable, which is exactly why it is cheap to assert: the failure it
    # guards against was a well-formed file of the wrong KIND, and "a file exists
    # and is not empty" could not tell the difference.
    if dest.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise Invalid("host_failed",
            f"what ffmpeg left at {dest} is not a PNG, so it is not the "
                      f"still that was asked for")
    return dest
