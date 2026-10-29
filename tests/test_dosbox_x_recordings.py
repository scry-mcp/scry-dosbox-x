"""`record` and `audio_record` against the channel double: `CAPTURE` turns a kind on at the stop,
`run_for` runs the retraces, `CAPTURE` turns it off at the stop it reached, and the file the
emulator wrote (a capture of the sound guest, `tests/fixtures/captures/`) is checked before its
path is answered."""

from __future__ import annotations

import asyncio
import os
import struct
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from channel_double import REAL_STOP, Machine, Stop, session_over
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)
from scry_core import cancel

from scry_dosbox_x import binary as binaries
from scry_dosbox_x import capture_files, recordings, retrace, server, summaries
from scry_dosbox_x import captures as caps
from scry_dosbox_x import state as dstate

CAPTURES = Path(__file__).parent / "fixtures" / "captures"
#: One retrace of the sound guest's text mode, in emulated milliseconds: the two the WAV holds
#: are 28.5 ms of the run that wrote it.
FRAME_MS = 14.27
SOURCES = {"WAV": CAPTURES / "two-frames.wav", "VIDEO": CAPTURES / "two-frames.avi",
           "OPL": CAPTURES / "eight-frames.dro", "MIDI": CAPTURES / "eight-frames.mid"}


def live(tmp_path: Path, *, frames: int = 2, sources: dict[str, Path] | None = None,
         **over: Any) -> Machine:
    install()
    machine = Machine(regs=dict(REAL_STOP), releases=[Stop(ms=FRAME_MS)] * frames,
                      capture_sources=SOURCES if sources is None else sources, **over)
    dstate.STATE.session = session_over(machine, tmp_path)
    dstate.STATE.remember_stop(dstate.STATE.session,
                               {"cs": "0814", "eip": "00000148", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return machine


def _ok(reply: object) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def _capture_commands(machine: Machine) -> list[str]:
    return [c.removeprefix("EXEC ") for c in machine.sent if c.startswith("EXEC CAPTURE")]


# ------------------------------------------------------------------------------- the WAV

def test_a_wav_over_two_retraces_is_checked_against_the_span_and_moved_to_dest(
        tmp_path: Path) -> None:
    machine = live(tmp_path)
    dest = tmp_path / "out" / "tone.wav"
    dest.parent.mkdir()
    got = _ok(server.audio_record(frames=2, dest=str(dest)))
    assert _capture_commands(machine) == ["CAPTURE", "CAPTURE WAV ON", "CAPTURE WAV OFF"]
    assert (got["kind"], got["frames"], got["began"], got["ended"]) == ("wav", 2, True, True)
    assert got["verdict"] == "ELAPSED" and got["polls"] == 2
    assert got["path"] == str(dest) and dest.read_bytes() == SOURCES["WAV"].read_bytes()
    assert not (tmp_path / "capture" / "sound_000.wav").exists(), "moved, not copied"
    assert (got["channels"], got["sample_rate_hz"], got["samples"]) == (2, 48000, 1344)
    assert got["emulated_s"] == pytest.approx(2 * FRAME_MS / 1000)
    assert got["sample_min"] < got["sample_max"], "the guest's tone is not silence"
    assert got["bytes"] == dest.stat().st_size


def test_with_no_dest_the_file_stays_where_the_emulator_wrote_it(tmp_path: Path) -> None:
    live(tmp_path)
    got = _ok(server.audio_record(frames=2))
    assert got["path"] == str(tmp_path / "capture" / "sound_000.wav")


@pytest.mark.parametrize(("frame_ms", "held"), [
    # 1344 samples at 48000 Hz are 28.0 ms: two ticks either side of that is the bound
    (14.0 + 0.999, True), (14.0 + 1.001, False), (14.0 - 0.999, True), (14.0 - 1.001, False)])
def test_a_wav_that_misses_its_span_by_more_than_two_ticks_is_refused_and_kept(
        tmp_path: Path, frame_ms: float, held: bool) -> None:
    install()
    machine = Machine(regs=dict(REAL_STOP), releases=[Stop(ms=frame_ms)] * 2,
                      capture_sources=SOURCES)
    dstate.STATE.session = session_over(machine, tmp_path)
    got = cast(dict[str, Any], server.audio_record(frames=2))
    if held:
        assert got["status"] == "ok", got
        return
    assert got["code"] == "readback_refused" and "does not hold the run" in got["message"], got
    assert got["path"] == str(tmp_path / "capture" / "sound_000.wav")
    assert Path(got["path"]).is_file(), "a refused recording is kept, never deleted"
    short = frame_ms > 14.0
    assert ("lower the guest's fixed `cycles`" in got["message"]) is short, got["message"]


def _edited(tmp_path: Path, at: int, value: int) -> Path:
    out = bytearray(SOURCES["WAV"].read_bytes())
    struct.pack_into("<I", out, at, value)
    path = tmp_path / "edited.wav"
    path.write_bytes(bytes(out))
    return path


@pytest.mark.parametrize(("why", "at", "value"), [("still open", 4, 0), ("data size", 40, 8)])
def test_a_wav_whose_header_disagrees_with_its_file_is_refused(
        tmp_path: Path, why: str, at: int, value: int) -> None:
    live(tmp_path, sources={**SOURCES, "WAV": _edited(tmp_path, at, value)})
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "readback_refused" and "not a finished WAV" in got["message"], (why, got)


def test_a_wav_with_no_sample_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.wav"
    head = bytearray(SOURCES["WAV"].read_bytes()[:44])
    struct.pack_into("<I", head, 4, 36)
    struct.pack_into("<I", head, 40, 0)
    empty.write_bytes(bytes(head))
    live(tmp_path, sources={**SOURCES, "WAV": empty})
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "readback_refused" and "holds no sample" in got["message"], got


# ----------------------------------------------------------------------- OPL, MIDI, video

@pytest.mark.parametrize(("kind", "word", "fields"), [
    ("dro", "OPL", {"opl_pairs": 11, "opl_ms": 0}),
    ("mid", "MIDI", {"midi_bytes": 12})])
def test_the_opl_and_midi_files_are_checked_and_counted(
        tmp_path: Path, kind: str, word: str, fields: dict[str, int]) -> None:
    machine = live(tmp_path)
    got = _ok(server.audio_record(frames=2, kind=kind))
    assert _capture_commands(machine)[1:] == [f"CAPTURE {word} ON", f"CAPTURE {word} OFF"]
    assert got["kind"] == kind and {k: got[k] for k in fields} == fields, got
    assert "samples" not in got


def test_an_opl_run_that_rolled_over_names_every_file_it_wrote(tmp_path: Path) -> None:
    """The OPL writer closes its file after 30 s of emulated silence and opens the next at the
    next note: the run's files are the siblings written since it began, not the last alone."""
    live(tmp_path, capture_rollovers=2)
    got = _ok(server.audio_record(frames=2, kind="dro"))
    folder = tmp_path / "capture"
    assert got["path"] == str(folder / "sound_002.dro"), got
    assert [f["path"] for f in got["files"]] == [str(folder / f"sound_00{n}.dro") for n in range(3)]
    assert all(f["bytes"] == got["bytes"] for f in got["files"]), got["files"]
    assert "3 files" in got["note"] and "30 s" in got["note"], got["note"]


def test_a_rolled_over_run_moved_to_dest_still_names_all_its_files(tmp_path: Path) -> None:
    """`dest` takes the last file out of the capture folder; the run's files are listed as they
    stood when it ended, the last one at `dest`."""
    live(tmp_path, capture_rollovers=2)
    dest = tmp_path / "out.dro"
    got = _ok(server.audio_record(frames=2, kind="dro", dest=str(dest)))
    folder = tmp_path / "capture"
    assert got["path"] == str(dest), got
    assert [f["path"] for f in got["files"]] == [str(folder / "sound_000.dro"),
                                                 str(folder / "sound_001.dro"), str(dest)]
    assert "3 files" in got["note"], got["note"]


def test_a_file_a_coarse_file_system_clock_dates_just_before_the_call_is_this_runs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows stamps a file from a clock that ticks about every 16 ms, so the first file of a run
    can carry a time a few milliseconds before the `time.time()` read that began it."""
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 0.012)
    live(tmp_path, capture_rollovers=1)
    got = _ok(server.audio_record(frames=2, kind="dro"))
    assert [f["path"].rsplit("_", 1)[1] for f in got["files"]] == ["000.dro", "001.dro"], got


def test_the_file_the_previous_recording_closed_a_moment_ago_is_not_this_runs(
        tmp_path: Path) -> None:
    older = tmp_path / "capture" / "sound_000.dro"
    older.parent.mkdir()
    older.write_bytes(SOURCES["OPL"].read_bytes())
    ago = time.time() - 1
    os.utime(older, (ago, ago))
    live(tmp_path, capture_first=1)
    got = _ok(server.audio_record(frames=2, kind="dro"))
    assert got["path"].endswith("sound_001.dro") and "files" not in got, got


def test_a_capture_folder_entry_that_is_no_file_or_vanished_is_not_a_run_file(
        tmp_path: Path) -> None:
    folder = tmp_path / "capture"
    folder.mkdir()
    (folder / "sound_000.dro").mkdir()
    (folder / "sound_001.DRO").write_bytes(b"x")
    (folder / "sound_002.dro").symlink_to(folder / "nowhere")
    live(tmp_path, capture_first=3)
    got = _ok(server.audio_record(frames=2, kind="dro"))
    assert got["path"].endswith("sound_003.dro") and "files" not in got, got


def test_a_file_an_earlier_run_left_beside_the_new_one_is_not_this_runs(tmp_path: Path) -> None:
    older = tmp_path / "capture" / "sound_000.dro"
    older.parent.mkdir()
    older.write_bytes(SOURCES["OPL"].read_bytes())
    os.utime(older, (1_000_000, 1_000_000))
    live(tmp_path, capture_first=1)
    got = _ok(server.audio_record(frames=2, kind="dro"))
    assert got["path"].endswith("sound_001.dro") and "files" not in got, got


@pytest.mark.parametrize("kind", ["dro", "mid"])
def test_a_run_with_no_event_of_the_kind_has_no_file_and_says_why(
        tmp_path: Path, kind: str) -> None:
    live(tmp_path, sources={})
    got = _ok(server.audio_record(frames=2, kind=kind))
    assert got["path"]["available"] is False and "first one" in got["path"]["why"], got
    assert summaries.audio_record({"frames": 2, "kind": kind}, got).endswith("no file")


def test_a_truncated_dro_is_refused(tmp_path: Path) -> None:
    cut = tmp_path / "cut.dro"
    cut.write_bytes(SOURCES["OPL"].read_bytes()[:-2])
    live(tmp_path, sources={**SOURCES, "OPL": cut})
    got = cast(dict[str, Any], server.audio_record(frames=2, kind="dro"))
    assert got["code"] == "readback_refused" and "DRO 2.0" in got["message"], got


def test_record_checks_the_avi_and_counts_its_frames(tmp_path: Path) -> None:
    machine = live(tmp_path)
    got = _ok(server.record(frames=2))
    assert _capture_commands(machine)[1:] == ["CAPTURE VIDEO ON", "CAPTURE VIDEO OFF"]
    assert (got["kind"], got["avi_frames"]) == ("avi", 2), got


def test_a_wav_or_avi_writer_that_opened_nothing_is_refused(tmp_path: Path) -> None:
    live(tmp_path, sources={})
    got = cast(dict[str, Any], server.record(frames=2))
    assert got["code"] == "readback_refused" and "opened no file" in got["message"], got


# -------------------------------------------------------------------------- refusals

def test_a_kind_already_on_is_refused_before_anything_runs(tmp_path: Path) -> None:
    machine = live(tmp_path, capturing={"VIDEO": None})
    got = cast(dict[str, Any], server.record(frames=2))
    assert got["code"] == "no_channel" and "already on" in got["message"], got
    assert _capture_commands(machine) == ["CAPTURE"]
    assert not any(c == "EXEC VRT" for c in machine.sent), "nothing ran"


def test_a_build_without_capture_is_refused_by_the_command_s_name(tmp_path: Path) -> None:
    live(tmp_path, commands=tuple(c for c in binaries.COMMANDS if c != recordings.CAPTURE))
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "no_channel" and "`CAPTURE`" in got["message"], got


def test_a_running_machine_is_refused(tmp_path: Path) -> None:
    machine = live(tmp_path, stopped=False, then=None)
    dstate.STATE.session.forget_stop()  # type: ignore[union-attr]
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "not_stopped", got
    assert not _capture_commands(machine)


@pytest.mark.parametrize(("args", "said"), [
    ({"frames": 0}, "frames=0"), ({"frames": 2, "kind": "ogg"}, "kind="),
    ({"frames": 2, "dest": "rel.wav"}, "dest="), ({"frames": 2, "seconds": 0}, "seconds")])
def test_arguments_are_judged_before_the_session_is_asked(
        args: dict[str, Any], said: str) -> None:
    got = cast(dict[str, Any], server.audio_record(**args))
    assert got["code"] == "bad_argument" and said in got["message"], got


def test_an_answer_that_is_not_capture_s_line_is_refused(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: ((True, ["DEBUG: CAPTURE WAV off path=-"])
                                             if body == "CAPTURE WAV ON" else None)
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "unexpected_answer" and "CAPTURE WAV ON" in got["message"], got


# ----------------------------------------------------------- a run that does not end well

def test_a_capture_that_cannot_be_turned_off_is_said_and_never_checked(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: ((False, ["*** Debugger command not recognized"])
                                             if body.endswith(" OFF") else None)
    got = _ok(server.audio_record(frames=2))
    assert got["ended"] is False and "`close`" in got["note"], got
    assert "path" not in got


def test_a_video_capture_that_cannot_be_turned_off_says_why_it_has_no_file(
        tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: ((False, ["*** Debugger command not recognized"])
                                             if body.endswith(" OFF") else None)
    got = _ok(server.record(frames=2))
    assert got["ended"] is False, got
    for field in ("path", "bytes", "avi_frames"):
        assert got[field]["available"] is False and "still on" in got[field]["why"], (field, got)


def test_a_run_that_raised_still_turns_the_capture_off(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    machine = live(tmp_path)

    def broken(*_: object) -> dict[str, Any]:
        raise RuntimeError("the channel went away mid-run")
    monkeypatch.setattr(retrace, "run_for", broken)
    with pytest.raises(RuntimeError):
        recordings.recording(cast(Any, dstate.STATE.session), "audio_record", "WAV", 2, None,
                             10.0, lambda *_: None)
    assert _capture_commands(machine)[-1] == "CAPTURE WAV OFF"


def test_a_run_that_made_no_progress_keeps_its_refusal_and_names_the_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    live(tmp_path)
    real = retrace.run_for

    def stuck(*a: Any) -> dict[str, Any]:
        reply = real(*a)
        return {**reply, "status": "INVALID", "code": "no_progress", "message": "stuck",
                "emulated_after_s": reply["emulated_before_s"] + 2 * FRAME_MS / 1000}
    monkeypatch.setattr(retrace, "run_for", stuck)
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["status"] == "INVALID" and got["code"] == "no_progress", got
    assert got["samples"] == 1344 and Path(got["path"]).is_file()


# ------------------------------------------------------------------- captures and one line

def test_captures_lists_each_recording_with_what_it_holds(tmp_path: Path) -> None:
    live(tmp_path, frames=4)
    _ok(server.audio_record(frames=2))
    dstate.STATE.session.control.releases = [Stop(ms=FRAME_MS)] * 4  # type: ignore[union-attr]
    _ok(server.audio_record(frames=2, kind="mid"))
    rows = _ok(server.captures())["captures"]
    assert [(r["kind"], r["complete"]) for r in rows] == [("wav", True), ("mid", True)]
    assert rows[0]["samples"] == 1344 and rows[1]["midi_bytes"] == 12


def test_a_file_a_writer_left_open_is_listed_as_not_complete(tmp_path: Path) -> None:
    path = tmp_path / "open.wav"
    head = bytearray(SOURCES["WAV"].read_bytes())
    struct.pack_into("<I", head, 4, 0)
    path.write_bytes(bytes(head))
    dstate.STATE.written[:] = [("wav", str(path))]
    row = caps._row("wav", path)
    assert row["complete"] is False and row["samples"]["available"] is False
    assert capture_files.facts("trace", path) == {}


def test_the_one_lines_say_what_was_recorded() -> None:
    reply = {"verdict": "ELAPSED", "kind": "wav", "samples": 1344, "sample_rate_hz": 48000,
             "sample_min": -3, "sample_max": 9, "path": "/c/a.wav"}
    assert summaries.audio_record({"frames": 2}, reply) == (
        "audio_record wav 2 frames: ELAPSED, 1344 samples at 48000 Hz at /c/a.wav")
    assert summaries.audio_record({"frames": 2}, {**reply, "sample_max": -3}).endswith(
        "48000 Hz, silent at /c/a.wav")
    assert summaries.record({"frames": 1}, {"verdict": "ELAPSED", "avi_frames": 1,
                                            "path": "/c/r.avi"}) == (
        "record 1 frame: ELAPSED, 1 frame at /c/r.avi")


def test_a_run_with_no_clock_still_answers_the_wav_with_its_span_unavailable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    live(tmp_path)
    real = retrace.run_for

    def clockless(*a: Any) -> dict[str, Any]:
        return {**real(*a), "emulated_after_s": {"available": False, "why": "no clock"}}
    monkeypatch.setattr(retrace, "run_for", clockless)
    got = _ok(server.audio_record(frames=2))
    assert got["emulated_s"]["available"] is False and got["samples"] == 1344


def test_an_avi_the_writer_left_unfinished_is_refused(tmp_path: Path) -> None:
    running = Path(__file__).parent / "fixtures" / "avi" / "dosbox-x-zmbv-running.avi"
    live(tmp_path, sources={**SOURCES, "VIDEO": running})
    got = cast(dict[str, Any], server.record(frames=2))
    assert got["code"] == "readback_refused" and "index missing" in got["message"], got


def test_a_listing_that_names_no_line_for_the_kind_is_refused(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: (True, []) if body == "CAPTURE" else None
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "unexpected_answer" and "no WAV line" in got["message"], got


def test_an_avi_that_cannot_be_read_is_listed_by_its_size(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "r.avi"
    path.write_bytes(SOURCES["VIDEO"].read_bytes())

    def unreadable(self: Path) -> bytes:
        raise PermissionError(self)
    monkeypatch.setattr(Path, "read_bytes", unreadable)
    row = caps._row("avi", path)
    assert row == {"kind": "avi", "path": str(path), "present": True, "bytes": path.stat().st_size}


def test_a_recording_is_listed_under_its_own_kind_whatever_dest_is_called(
        tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.audio_record(frames=2, kind="dro", dest=str(tmp_path / "opl.wav")))
    row = _ok(server.captures())["captures"][0]
    assert (row["kind"], row["complete"], row["opl_pairs"]) == ("dro", True, 11), row


def test_a_capture_left_on_says_so_in_its_one_line(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: ((False, ["*** Debugger command not recognized"])
                                             if body.endswith(" OFF") else None)
    got = _ok(server.audio_record(frames=2))
    assert got["summary"].endswith("still recording until `close`"), got["summary"]


def test_a_build_without_capture_is_told_so_before_the_running_machine_is(
        tmp_path: Path) -> None:
    live(tmp_path, stopped=False, then=None,
         commands=tuple(c for c in binaries.COMMANDS if c != recordings.CAPTURE))
    dstate.STATE.session.forget_stop()  # type: ignore[union-attr]
    got = cast(dict[str, Any], server.record(frames=2))
    assert got["code"] == "no_channel", got


def test_a_cancelled_run_still_turns_the_capture_off_and_reads_it_back(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cancel is still pending when the turn-off is sent: shielded, its poll does not raise."""
    machine = live(tmp_path)

    def pending() -> None:
        if not cancel.shielding():
            raise asyncio.CancelledError
    machine.hooks["CAPTURE"] = lambda body: (pending() if body.endswith(" OFF") else None)

    def cancelled(*_: object) -> dict[str, Any]:
        raise asyncio.CancelledError
    monkeypatch.setattr(retrace, "run_for", cancelled)
    with pytest.raises(asyncio.CancelledError):
        recordings.recording(cast(Any, dstate.STATE.session), "audio_record", "WAV", 2, None,
                             10.0, lambda *_: None)
    assert machine.capturing == {} and _capture_commands(machine)[-1] == "CAPTURE WAV OFF"


def test_a_capture_left_on_keeps_the_run_s_own_note(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    machine = live(tmp_path)
    machine.hooks["CAPTURE"] = lambda body: ((False, ["*** Debugger command not recognized"])
                                             if body.endswith(" OFF") else None)
    real = retrace.run_for
    monkeypatch.setattr(retrace, "run_for", lambda *a: {**real(*a), "note": "the run's own"})
    got = _ok(server.audio_record(frames=2))
    assert got["note"].startswith("the run's own; ") and "`close`" in got["note"], got


def test_a_dest_taken_during_the_run_is_never_overwritten(tmp_path: Path) -> None:
    machine = live(tmp_path)
    dest = tmp_path / "late.wav"

    def taken(body: str) -> None:
        if body.endswith(" OFF"):
            dest.write_bytes(b"somebody's")
    machine.hooks["CAPTURE"] = taken
    got = cast(dict[str, Any], server.audio_record(frames=2, dest=str(dest)))
    assert got["code"] == "readback_refused" and str(dest) in got["message"], got
    assert dest.read_bytes() == b"somebody's" and Path(got["path"]).is_file()


@pytest.mark.skipif(sys.platform == "win32",
                    reason="a 480-character directory cannot be made under MAX_PATH")
def test_a_capture_path_the_debuggers_message_buffer_cut_is_refused_not_misread(
        tmp_path: Path) -> None:
    deep = tmp_path.joinpath(*["d" * 60] * 8)
    deep.mkdir(parents=True)
    machine = live(deep)
    got = cast(dict[str, Any], server.audio_record(frames=2))
    assert got["code"] == "readback_refused" and "cut" in got["message"], got
    assert "shorter" in got["message"], got
    assert _capture_commands(machine)[-1] == "CAPTURE WAV OFF", "the capture was still turned off"
