"""A bricks session exports, replays twice with no model, and an edited copy diverges.

The export cuts at `resume`: the released run ends wherever a stop finds it, which no replayed
advance reaches."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import live_private  # isort: skip -- first: a pooled job's working copies
import pytest

import dosbox_x_server as server

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
BRICKS = live_private.bricks_dir()
REPLAY_WITHIN_S = 600


def _replay(document: Path, transcript: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "scry_core.replay", str(document),
                           "--transcript", str(transcript)], cwd=ROOT, capture_output=True,
                          text=True, timeout=REPLAY_WITHIN_S)


def test_a_bricks_session_replays_twice_and_an_edited_one_diverges(tmp_path: Path) -> None:
    started = cast(dict[str, Any], server.start(conf=str(BRICKS / "bricks.conf"),
                                                cwd=str(BRICKS), session_seconds=300,
                                                logfile=str(tmp_path / "bricks-e9.log")))
    assert started["status"] == "ok", started.get("summary")
    try:
        ran = server.run_for(frames=30)
        assert ran["status"] == "ok", ran
        sig = server.screen_signature()
        regs = server.registers()
        assert sig["status"] == "ok" and regs["status"] == "ok", (sig, regs)
        assert server.resume()["status"] == "ok"
        server.send_keys(keys=["right"])
        document = tmp_path / "bricks-session.json"
        exported = server.perform_export(dest=str(document))
    finally:
        server.close()
    assert exported["status"] == "ok", exported.get("summary")
    assert exported["steps"] >= 1 and exported["checks"] == 2, exported
    assert "op" in exported["cut"] and exported["cut"]["op"] == "resume", exported["cut"]
    for n in (1, 2):
        played = _replay(document, tmp_path / f"replay-{n}" / "t.md")
        assert played.returncode == 0, (n, played.stdout[-600:], played.stderr[-300:])
    doc = json.loads(document.read_text())
    at = next(i for i, step in enumerate(doc["steps"]) if "recorded" in step)
    field = next(iter(doc["steps"][at]["recorded"]))
    doc["steps"][at]["recorded"][field] = "edited"
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(doc))
    played = _replay(edited, tmp_path / "edited" / "t.md")
    assert played.returncode == 1, played.stdout[-600:]
    assert f"diverged at step {at + 1} of " in played.stdout
    assert f": {field} recorded 'edited'" in played.stdout
