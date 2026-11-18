"""A fresh run of each demo matches its README transcript, its screen.png and, for bricks, the
front door's flow."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from scry_core.demo import load, stale

pytestmark = [pytest.mark.live, pytest.mark.windowed]

ROOT = Path(__file__).resolve().parents[2]
# Above the runner's own per-call bound, so a hang ends as its FAIL.
TIMEOUT_S = 1800
DPAINT = os.environ.get("DELUXE_PAINT_DIR", "")
LINEUP = os.environ.get("LINEUP_MSDOS_DIR", "")
MONKEY = os.environ.get("MONKEY_ISLAND_CD", "")
SPEEDF = os.environ.get("SPEEDF_MSDOS_DIR", "")
RECHIP = os.environ.get("RECHIP_DIR", "")


DEMOS = [
    ("bricks", []),
    ("mines", []),
    *(pytest.param(name, ["--cwd", DPAINT], marks=pytest.mark.skipif(
        not DPAINT, reason="set DELUXE_PAINT_DIR to the directory holding Deluxe Paint II v1.0: "
                           "the repository carries none of the program"))
      for name in ("dpaint", "dpaint_maps")),
    pytest.param("lineup", ["--cwd", LINEUP], marks=pytest.mark.skipif(
        not LINEUP, reason="set LINEUP_MSDOS_DIR to a copy of LineUp's PC port: the repository "
                           "carries none of the game")),
    pytest.param("monkey", ["--cwd", MONKEY], marks=pytest.mark.skipif(
        not MONKEY, reason="set MONKEY_ISLAND_CD to the directory holding the 1992 Enhanced CD's "
                           "monkey.cue and BINs: the repository carries none of the game")),
    pytest.param("speedf", ["--cwd", SPEEDF], marks=pytest.mark.skipif(
        not SPEEDF, reason="set SPEEDF_MSDOS_DIR to a copy of Speed Fight's PC game: the "
                           "repository carries none of the game")),
    pytest.param("rechip", ["--cwd", RECHIP], marks=pytest.mark.skipif(
        not RECHIP, reason="set RECHIP_DIR to a built copy of ReChip!: the repository "
                           "carries none of the program"))]

#: The demos already run in this session: both tests below share one run per demo.
_RUNS: dict[str, subprocess.CompletedProcess[str]] = {}


def _run(name: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    if name not in _RUNS:
        _RUNS[name] = subprocess.run([sys.executable, str(ROOT / "demos" / name / "demo.py"),
                                      *args], cwd=ROOT, capture_output=True, text=True,
                                     timeout=TIMEOUT_S)
    return _RUNS[name]


@pytest.mark.parametrize(("name", "args"), DEMOS)
def test_a_demo_passes(name: str, args: list[str]) -> None:
    ran = _run(name, args)
    verdict = [ln for ln in ran.stdout.splitlines() if ln.startswith(("DEMO", "FAIL", "INVALID"))]
    assert ran.returncode == 0, f"rc {ran.returncode}: {verdict} {ran.stderr.strip()[-300:]}"


@pytest.mark.skipif(sys.platform != "darwin", reason=(
    "the committed READMEs and screen.png are the Mac's run: a transcript carries the byte counts "
    "of the pictures it saved, and a capture's bytes follow the host's display, so another host "
    "cannot reproduce them; `test_a_demo_passes` is what that host judges"))
@pytest.mark.parametrize(("name", "args"), DEMOS)
def test_a_demo_matches_what_is_committed(name: str, args: list[str]) -> None:
    demo = ROOT / "demos" / name
    ran = _run(name, args)
    assert ran.returncode == 0, f"the demo did not pass: rc {ran.returncode}"
    stale_files = stale(load(demo / "demo.py"), ROOT / "tmp" / "demos" / name)
    assert stale_files == [], stale_files
