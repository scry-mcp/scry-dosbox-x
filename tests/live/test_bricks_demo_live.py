"""The bricks demo, run whole, still passes and its README still shows what the server answers:
the transcript a fresh run writes is compared line for line with the block `--update-readme`
wrote, and the picture with `screen.png`.

The demo opens a WINDOW (the mouse and the saved states need one) and asks the placement helper
named by `WINDOW_APP` where it goes, so this SKIPS without one, as the tier's other window cases
skip without their flags: where a window goes is not this package's decision. It takes the focus
for a moment at each key, mouse event and menu click.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from scry_core.demo import readme_drift

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demos" / "bricks"
RUN = ROOT / "tmp" / "demos" / "bricks"
#: The whole demo, above the runner's own bound on one call, so a hung call ends as its FAIL.
TIMEOUT_S = 1800


@pytest.mark.windowed
@pytest.mark.skipif(not os.environ.get("WINDOW_APP"),
                    reason="set WINDOW_APP to a placement helper: the demo opens a window")
def test_the_bricks_demo_passes_and_matches_its_readme() -> None:
    ran = subprocess.run([sys.executable, str(DEMO / "demo.py")], cwd=ROOT, capture_output=True,
                         text=True, timeout=TIMEOUT_S)
    verdict = [ln for ln in ran.stdout.splitlines() if ln.startswith(("DEMO", "FAIL", "INVALID"))]
    assert ran.returncode == 0, f"rc {ran.returncode}: {verdict} {ran.stderr.strip()[-300:]}"
    drift = readme_drift(DEMO / "README.md", RUN / "transcript.normalised.md")
    assert drift == "", drift
    assert (DEMO / "screen.png").read_bytes() == (RUN / "screen.png").read_bytes(), \
        "the committed screen.png is not this run's capture"
