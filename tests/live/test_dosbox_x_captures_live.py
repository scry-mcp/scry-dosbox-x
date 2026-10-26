"""The sound guest recorded at a stop, through the server: a WAV, a DRO, a MIDI file and an AVI,
each checked against what the guest plays (`tests/guest/sound.asm`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from live_private import guest_dir

import dosbox_capture_files as capture_files
import dosbox_x_server as server

pytestmark = pytest.mark.live

GUEST = guest_dir()


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def test_the_sound_guest_is_recorded_in_every_kind(tmp_path: Path) -> None:
    _ok(server.start(conf=str(GUEST / "sound.conf"), cwd=str(GUEST), session_seconds=120,
                     captures_dir=str(tmp_path / "cap"), presence=False))
    _ok(server.run_for(frames=20))
    wav = _ok(server.audio_record(frames=35, dest=str(tmp_path / "a.wav")))
    assert wav["sample_min"] < wav["sample_max"] and wav["channels"] == 2, wav
    dro = _ok(server.audio_record(frames=35, kind="dro", dest=str(tmp_path / "a.dro")))
    stream = capture_files.dro(Path(dro["path"]))
    assert stream is not None and dro["opl_pairs"] == stream.pairs >= 2, dro
    mid = _ok(server.audio_record(frames=35, kind="mid", dest=str(tmp_path / "a.mid")))
    assert b"\x90\x3c" in Path(mid["path"]).read_bytes(), mid
    avi = _ok(server.record(frames=5, dest=str(tmp_path / "a.avi")))
    assert avi["avi_frames"] == 5, avi
    _ok(server.close())
