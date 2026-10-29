"""`record` and `audio_record`: a capture kind turned on at a stop through the debugger's
`CAPTURE`, `frames` retraces run as `run_for` runs them, the kind turned off at the stop that ends
the run, and the file checked before its path is answered (`docs/reference/captures.md`)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scry_core import cancel, prose, wav
from scry_core.reply_contract import Invalid, unavailable

import dosbox_capture_files as files
import dosbox_collect as dcollect
import dosbox_debugger as dbg
import dosbox_paths as paths
import dosbox_retrace as retrace
import dosbox_session as ds
import dosbox_state as st

CAPTURE = "CAPTURE"
LINE = re.compile(r"^DEBUG: CAPTURE (WAV|OPL|MIDI|VIDEO) (on|off) path=(.+)$")
VIDEO = "VIDEO"
#: Each `CAPTURE` word's file extension, which is the reply's `kind`.
EXTENSION = {**{word: ext for ext, word in files.AUDIO_KINDS.items()}, VIDEO: "avi"}
#: The debugger formats a message into 512 bytes, one of them the NUL: a line this long was cut.
LINE_CUT = 511
NO_FILE_WHY = {
    "OPL": "the guest keyed no OPL note on during the run, and the writer opens its file at the "
           "first one",
    "MIDI": "the guest sent no MIDI byte during the run, and the writer opens its file at the "
            "first one",
}


def _states(lines: list[str]) -> dict[str, tuple[bool, str | None]]:
    """Each kind's line as `(on, path)`, a path of `-` being none."""
    out: dict[str, tuple[bool, str | None]] = {}
    for line in lines:
        found = LINE.match(line)
        if found is not None:
            path = found.group(3)
            out[found.group(1)] = (found.group(2) == "on", None if path == "-" else path)
    return out


def _cut_line(kind: str, word: str, lines: list[str]) -> Invalid | None:
    """The refusal for a `CAPTURE` line the debugger's message buffer cut, its path with it."""
    cut = next((ln for ln in lines
                if ln.startswith("DEBUG: CAPTURE") and len(ln) >= LINE_CUT), None)
    if cut is None:
        return None
    return Invalid("readback_refused",
                   f"the debugger's message buffer cut its `{CAPTURE} {kind} {word}` line at "
                   f"{len(cut)} characters, so the path in it cannot be trusted (the capture is "
                   "off, and its file is where the emulator wrote it): record with a shorter "
                   "`captures_dir` (or working directory)")


def _toggle(session: ds.Session, kind: str, on: bool) -> tuple[str | None, Invalid | None]:
    """`CAPTURE kind ON|OFF`, read back; the file it names, if any, and the refusal for a path
    the debugger's buffer cut (raised at once for ON, which has no path to give)."""
    word = "ON" if on else "OFF"
    ok, lines = session.exec(f"{CAPTURE} {kind} {word}")
    said = _states(lines).get(kind)
    if not ok or said is None or said[0] != on:
        raise Invalid("unexpected_answer",
                      f"`{CAPTURE} {kind} {word}` answered {' / '.join(lines) or 'nothing'}, "
                      f"not its line saying the {kind} capture is {word.lower()}")
    cut = _cut_line(kind, word, lines)
    if cut is not None and on:
        raise cut
    return said[1], cut


def _wav_fields(path: Path, ran: dict[str, Any]) -> dict[str, Any]:
    """The WAV checked against itself and the run's emulated span."""
    head = wav.header(path)
    if head is None:
        raise Invalid("readback_refused", f"{path} is not a finished WAV: its header disagrees "
                      "with the file", path=str(path))
    if head.samples == 0:
        raise Invalid("readback_refused", f"{path} holds no sample: the mixer wrote nothing over "
                      "the run; check that the guest makes sound on a device this conf enables",
                      path=str(path))
    before, after = ran.get("emulated_before_s"), ran.get("emulated_after_s")
    fields: dict[str, Any] = {}
    if isinstance(before, float) and isinstance(after, float):
        span = after - before
        tick = head.sample_rate / 1000
        if abs(head.samples - span * head.sample_rate) > files.SPAN_TICKS * tick:
            lost = (" A short file is the usual sign of a host that did not hold the guest's "
                    "clock in real time, so the mixer dropped whole blocks: lower the guest's "
                    "fixed `cycles` and record again."
                    if head.samples < span * head.sample_rate else "")
            raise Invalid("readback_refused",
                          f"{path} does not hold the run it was bounded by: "
                          f"{prose.counted(head.samples, 'sample')} where {span:.7f} s at "
                          f"{head.sample_rate} Hz is {span * head.sample_rate:.0f}.{lost}",
                          path=str(path))
        fields["emulated_s"] = round(span, 7)
    else:
        fields["emulated_s"] = unavailable("`RUNSTATE` gave no clock at one end of the run")
    lo, hi = wav.levels(path)
    return {"channels": head.channels, "sample_rate_hz": head.sample_rate,
            "samples": head.samples, **fields, "sample_min": lo, "sample_max": hi}


def _file_fields(kind: str, path: Path, ran: dict[str, Any]) -> dict[str, Any]:
    """The kind's own check and counts; a file that fails it is refused with its path."""
    if kind == "WAV":
        return _wav_fields(path, ran)
    if kind == VIDEO:
        facts = ds.avi_facts(path.read_bytes())
        if not facts["complete"] or not facts["avi_frames"]:
            raise Invalid("readback_refused",
                          f"{path} is not a finished AVI with a frame in it "
                          f"({facts['avi_frames']} frames, index "
                          f"{'present' if facts['complete'] else 'missing'})", path=str(path))
        return {"avi_frames": facts["avi_frames"]}
    found = files.facts("dro" if kind == "OPL" else "mid", path)
    if not found.get("complete"):
        raise Invalid("readback_refused", f"{path} is not a finished "
                      f"{'DRO 2.0 stream' if kind == 'OPL' else 'MIDI file'}: its header "
                      "disagrees with the file", path=str(path))
    found.pop("complete")
    return found


def recording(session: ds.Session, tool: str, kind: str, frames: int, dest: Path | None,
              seconds: float, progress: ds.Progress) -> dict[str, Any]:
    """The body of `record` (`kind` `VIDEO`) and `audio_record`."""
    if not session.has(CAPTURE):
        raise dbg.missing(CAPTURE, f"`{tool}`")
    session.require_stopped(tool)
    if dest is not None:
        dest = paths.fresh_dest("dest", dest)
    _ok, listed = session.exec(CAPTURE)
    held = _states(listed).get(kind)
    if held is None:
        raise Invalid("unexpected_answer", f"`{CAPTURE}` listed no {kind} line: "
                      f"{' / '.join(listed) or 'nothing'}")
    if held[0]:
        raise Invalid("no_channel",
                      f"the {kind} capture is already on"
                      + (" (this session was started with `capture_video`)"
                         if kind == VIDEO and session.launch.capture_video else "")
                      + ": a recording here would end that one. A stretch is recorded with the "
                      "capture off")
    ended, closed, why, cut = True, None, "", None
    try:
        _toggle(session, kind, True)
        ran = retrace.run_for(session, frames, 0, seconds, progress)
    finally:
        # Shielded: after a cancel the turn-off's own poll would raise and abandon its answer.
        with cancel.shielded():
            try:
                closed, cut = _toggle(session, kind, False)
            except Invalid as e:
                ended, why = False, str(e)
    own: dict[str, Any] = {"kind": EXTENSION[kind], "frames": frames,
                           "began": True, "ended": ended}
    if not ended:
        left_on = (f"the capture could not be turned off ({why}): it records until `close`, "
                   "which ends the emulator and its files")
        # A video reply requires its file facts, so each says it has none; the rest leave them out.
        gone = {name: unavailable(f"the capture is still on: {why}")
                for name in ("path", "bytes", "avi_frames")} if kind == VIDEO else {}
        return st.extend(ran, **own, **gone,
                         note="; ".join(n for n in (ran.get("note"), left_on) if n))
    if cut is not None:
        raise cut
    if closed is None:
        if kind in NO_FILE_WHY:
            return st.extend(ran, **own, path=unavailable(NO_FILE_WHY[kind]))
        raise Invalid("readback_refused", f"the {kind} capture was on over the run and its "
                      "writer opened no file")
    path = Path(closed)
    fields = _file_fields(kind, path, ran)
    if dest is not None:
        if paths.taken(dest):
            raise Invalid("readback_refused", f"{dest} appeared while the run went on, and is "
                          f"somebody's: the recording stays at {path}", path=str(path))
        path = dcollect.collect(path, dest, f"{kind} capture")
    own.update(path=str(path), bytes=path.stat().st_size)
    if ran.get("status") == "INVALID":
        return {**ran, **own, **fields}
    return st.extend(ran, **own, **fields)
