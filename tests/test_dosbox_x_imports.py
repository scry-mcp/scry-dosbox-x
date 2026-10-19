"""Every module of the server imports on its own, in a fresh interpreter: the modules import each
other in a cycle that only works while no module reads another's names at import time, and the
suite always enters through the server, so an order that breaks is seen only here."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = sorted(p.stem for p in ROOT.glob("dosbox_*.py"))


def test_the_modules_were_found() -> None:
    assert len(MODULES) > 20, MODULES


@pytest.mark.parametrize("module", MODULES)
def test_a_module_imports_first(module: str) -> None:
    got = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT,
                         capture_output=True, text=True, timeout=60, check=False)
    assert got.returncode == 0, got.stderr[-600:]
