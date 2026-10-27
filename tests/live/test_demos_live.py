"""A fresh run of each demo matches its README transcript, its screen.png and, for bricks, the
front door's flow."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from scry_core.demo import load, stale

pytestmark = [pytest.mark.live, pytest.mark.windowed,
              pytest.mark.skipif(not os.environ.get("WINDOW_APP"),
                                 reason="set WINDOW_APP to a placement helper: a demo opens a "
                                        "window")]

ROOT = Path(__file__).resolve().parents[2]
# Above the runner's own per-call bound, so a hang ends as its FAIL.
TIMEOUT_S = 1800
DPAINT = os.environ.get("DELUXE_PAINT_DIR", "")


@pytest.mark.parametrize(("name", "args"), [
    ("bricks", []),
    pytest.param("dpaint", ["--cwd", DPAINT], marks=pytest.mark.skipif(
        not DPAINT, reason="set DELUXE_PAINT_DIR to your own copy of Deluxe Paint II v1.0: "
                           "the repository carries none of the program"))])
def test_a_demo_passes_and_matches_what_is_committed(name: str, args: list[str]) -> None:
    demo = ROOT / "demos" / name
    ran = subprocess.run([sys.executable, str(demo / "demo.py"), *args], cwd=ROOT,
                         capture_output=True, text=True, timeout=TIMEOUT_S)
    verdict = [ln for ln in ran.stdout.splitlines() if ln.startswith(("DEMO", "FAIL", "INVALID"))]
    assert ran.returncode == 0, f"rc {ran.returncode}: {verdict} {ran.stderr.strip()[-300:]}"
    stale_files = stale(load(demo / "demo.py"), ROOT / "tmp" / "demos" / name)
    assert stale_files == [], stale_files
