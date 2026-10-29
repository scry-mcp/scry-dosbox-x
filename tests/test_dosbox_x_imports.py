"""Each module imports first in a fresh interpreter: the import cycle breaks by order."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = sorted(f"scry_dosbox_x.{p.stem}" for p in (ROOT / "src" / "scry_dosbox_x").glob("*.py")
                 if p.stem != "__init__")


def test_the_modules_were_found() -> None:
    assert len(MODULES) > 20, MODULES


@pytest.mark.parametrize("module", MODULES)
def test_a_module_imports_first(module: str) -> None:
    got = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT,
                         capture_output=True, text=True, timeout=60, check=False)
    assert got.returncode == 0, got.stderr[-600:]
