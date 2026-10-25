"""A fresh run of the bricks demo matches the README transcript and screen.png."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from scry_core.demo import load, stale

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demos" / "bricks"
RUN = ROOT / "tmp" / "demos" / "bricks"
# Above the runner's own per-call bound, so a hang ends as its FAIL.
TIMEOUT_S = 1800


@pytest.mark.windowed
@pytest.mark.skipif(not os.environ.get("WINDOW_APP"),
                    reason="set WINDOW_APP to a placement helper: the demo opens a window")
def test_the_bricks_demo_passes_and_matches_its_readme_and_the_front_door() -> None:
    ran = subprocess.run([sys.executable, str(DEMO / "demo.py")], cwd=ROOT, capture_output=True,
                         text=True, timeout=TIMEOUT_S)
    verdict = [ln for ln in ran.stdout.splitlines() if ln.startswith(("DEMO", "FAIL", "INVALID"))]
    assert ran.returncode == 0, f"rc {ran.returncode}: {verdict} {ran.stderr.strip()[-300:]}"
    stale_files = stale(load(DEMO / "demo.py"), RUN)
    assert stale_files == [], stale_files
