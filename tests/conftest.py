"""Unit cases never see the developer's DOSBOX_X_BINARY, nor the host's own
build, which a stub on the PATH stands in for; live cases keep them."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from scry_core import window as core_window
from stub_builds import build
from window_double import obeying

LIVE = Path(__file__).resolve().parent / "live"


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
    yield


@pytest.fixture(autouse=True)
def window_host(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if not request.node.path.is_relative_to(LIVE):
        monkeypatch.setattr(core_window, "host", lambda _platform="": obeying())
