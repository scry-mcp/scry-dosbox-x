"""Unit cases never see the developer's DOSBOX_X_BINARY, nor the host's own
build, which a stub on the PATH stands in for; live cases keep them."""

import os
from collections.abc import Iterator
from pathlib import Path

import dosbox_x_server_support as support
import pytest
from scry_core import file_names
from scry_core import window as core_window
from stub_builds import build
from window_double import obeying

from scry_dosbox_x import state as dstate

LIVE = Path(__file__).resolve().parent / "live"
#: The debugger's own names.
FIXED_NAMES = frozenset({"MCPDUMP.BIN", "MCPIVT.TXT", "SYMS.BIN", "SYMSBK.BIN", "LOGCPU.TXT"})
_JUDGED: set[Path] = set()
_RAN: list[str] = []


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Each unit case's new files in the server's own directories, judged by their names before
    its fixtures clear them."""
    yield
    if item.path.is_relative_to(LIVE):
        return
    _RAN.append(item.nodeid)
    folders = {str(f) for f in (dstate.STATE.session_dir, dstate.STATE.scratch,
                                support._STORE_TMP) if f is not None}
    outside: list[Path] = []
    for folder in map(Path, folders):
        new = {Path(root, f) for root, _, files in os.walk(folder) for f in files} - _JUDGED
        if new:
            _JUDGED.update(new)
            outside += [f for f in file_names.outside(folder)
                        if f in new and f.name not in FIXED_NAMES]
    if outside:
        pytest.fail("the server wrote files named outside the rule of a file name: "
                    + ", ".join(sorted(str(f) for f in outside)), pytrace=False)


@pytest.fixture(scope="session", autouse=True)
def names_were_judged(request: pytest.FixtureRequest) -> Iterator[None]:
    yield
    config = request.config
    narrowed = config.option.keyword or config.args != config.getini("testpaths")
    if _RAN and not _JUDGED and not narrowed:
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

