"""Unit cases never see the developer's DOSBOX_X_BINARY nor the host's own build, which a stub on
the PATH stands in for, and their session doubles stand in for the terminal on every host; live
cases keep all three as the host has them."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import dosbox_process as dprocess

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from stub_builds import build  # noqa: E402

LIVE = Path(__file__).resolve().parent / "tests" / "live"


@pytest.fixture(scope="session")
def stub_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("path-build"),
                 version="print('DOSBox-X version 0.0.0, a stub on PATH')")


@pytest.fixture(autouse=True)
def unit_case_host(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch,
                   stub_build: Path) -> Iterator[None]:
    if not request.node.path.is_relative_to(LIVE):
        monkeypatch.delenv("DOSBOX_X_BINARY", raising=False)
        monkeypatch.setenv("PATH", f"{stub_build.parent}{os.pathsep}{os.environ.get('PATH', '')}")
        monkeypatch.setattr(dprocess, "HAS_TERMINAL", True)
    yield
