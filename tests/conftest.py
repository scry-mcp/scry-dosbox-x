"""Unit cases never see the developer's DOSBOX_X_BINARY, nor the host's own
build, which a stub on the PATH stands in for; live cases keep them."""

import os
from collections.abc import Iterator
from pathlib import Path

import dosbox_x_server_support as support
import pytest
from scry_core import names_written
from scry_core import window as core_window
from stub_builds import build
from window_double import obeying

from scry_dosbox_x import state as dstate

LIVE = Path(__file__).resolve().parent / "live"
#: The debugger's own names.
NAMES = names_written.Names(fixed={"MCPDUMP.BIN", "MCPIVT.TXT", "SYMS.BIN", "SYMSBK.BIN",
                                   "LOGCPU.TXT"})


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Each unit case's new files in the server's own directories, judged by their names before
    its fixtures clear them."""
    yield
    if item.path.is_relative_to(LIVE):
        return
    outside = NAMES.outside([dstate.STATE.session_dir, dstate.STATE.scratch, support._STORE_TMP])
    if outside:
        pytest.fail("the server wrote files named outside the rule of a file name: "
                    + ", ".join(map(str, outside)), pytrace=False)


@pytest.fixture(scope="session", autouse=True)
def names_were_judged(request: pytest.FixtureRequest) -> Iterator[None]:
    yield
    if NAMES.judged_nothing(request.config):
        pytest.fail("INVALID: no file the server wrote was judged by its name", pytrace=False)


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

