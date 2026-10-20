"""`captures` lists every file the session wrote: each writer's file is kept under its kind, and
nothing else is."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_dosbox_x_session import fake_avi

import dosbox_captures as caps
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server


def test_each_writer_is_kept_under_its_kind_once_and_a_refusal_or_a_reader_never(
) -> None:
    dstate.STATE.written.clear()
    caps.note_written("series_capture", {"status": "ok", "manifest": "/s/manifest.json"})
    caps.note_written("trace", {"status": "ok", "trace": {"path": "/t/run.trace"}})
    caps.note_written("map_save", {"status": "ok", "path": "/m/game.scry-map.json"})
    caps.note_written("memdump", {"status": "ok", "path": "/d/ram.bin"})
    caps.note_written("memdump", {"status": "ok", "path": "/d/ram.bin"})       # once
    caps.note_written("memdump", {"status": "INVALID", "path": "/d/no.bin"})   # refused
    caps.note_written("read_memory", {"status": "ok", "path": "/r/x"})          # no writer
    caps.note_written("machine_map", {"status": "ok"})                          # wrote nothing
    assert dstate.STATE.written == [("series", "/s/manifest.json"), ("trace", "/t/run.trace"),
                                    ("json", "/m/game.scry-map.json"), ("bin", "/d/ram.bin")]
    dstate.STATE.clear_running_state()
    assert dstate.STATE.written == [], "a session's files are not the next one's"


def _recording(cwd: Path, captures_dir: Path | None = None) -> Any:
    return SimpleNamespace(launch=SimpleNamespace(cwd=cwd, captures_dir=captures_dir,
                                                  capture_video=True), _avi_facts={})


def test_a_recording_without_a_captures_dir_is_listed_from_the_emulators_own_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no `captures_dir` the emulator records under `capture/` in its working directory,
    and `captures` lists it there, read once while it has not grown, with what is IN it."""
    dstate.STATE.written.clear()
    (tmp_path / "capture").mkdir()
    (tmp_path / "capture" / "g_000.avi").write_bytes(fake_avi(frames=7))
    reads: list[bytes] = []
    real = ds.avi_facts

    def counted(data: bytes) -> dict[str, object]:
        reads.append(data)
        return real(data)
    monkeypatch.setattr(ds, "avi_facts", counted)
    session = _recording(tmp_path)
    for _ in range(2):
        rows = caps.captures(session)["captures"]
        assert [(r["kind"], r["avi_frames"], r["riff_avi"]) for r in rows] == [("avi", 7, True)]
    assert len(reads) == 1, "an unchanged capture was read whole again"


def test_a_capture_gone_between_the_listing_and_its_read_is_not_a_traceback(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dstate.STATE.written.clear()
    (tmp_path / "g_000.avi").write_bytes(fake_avi(frames=3))

    def vanished(self: Path) -> bytes:
        raise FileNotFoundError(self)
    monkeypatch.setattr(Path, "read_bytes", vanished)
    assert caps.captures(_recording(tmp_path, tmp_path))["captures"] == []


def test_every_tool_that_writes_to_a_dest_is_a_writer_captures_lists() -> None:
    """A tool that takes `dest` writes a file; one missing from `WRITERS` is a file `captures`
    never lists, and nothing else would say so."""
    takes_dest = {t.name for t in asyncio.run(server.mcp.list_tools())
                  if "dest" in t.input_schema["properties"]}
    assert takes_dest, "no tool takes a dest: the read examined nothing"
    assert takes_dest <= set(caps.WRITERS), sorted(takes_dest - set(caps.WRITERS))
    caps.note_written("screen_view", {"status": "ok", "image": {"path": "/g/screen.png"}})
    assert dstate.STATE.written[-1] == ("png", "/g/screen.png")
