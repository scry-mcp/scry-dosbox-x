"""Unit cases never see the developer's DOSBOX_X_BINARY, nor the host's own
build, which a stub on the PATH stands in for; live cases keep them."""

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import dosbox_x_server_support as support
import pytest
from scry_core import names_written
from scry_core import window as core_window
from scry_core.knowledge import base as rows
from scry_core.knowledge import rows as rows_file
from scry_core.knowledge import sealed
from stub_builds import build
from window_double import obeying

from scry_dosbox_x import knowledge
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


ROWS = Path(__file__).resolve().parent / "fixtures" / "knowledge" / "rows"


@pytest.fixture
def fixture_base(tmp_path: Path) -> rows.Base:
    """The dictionaries of rows of `fixtures/knowledge/rows` with INT 21h AH=4Ch and DOS error 1
    sealed in every part, AH=3Dh and error 2 left unsealed."""
    folder = tmp_path / "rows"
    shutil.copytree(ROWS, folder)
    lock = tmp_path / "rows-lock.json"
    lock.write_text(json.dumps({"format": sealed.LOCK_FORMAT, "sealed": {}}) + "\n",
                    encoding="utf-8")
    for name, id_ in (("int21", "ibm-pc:call:0x21/0x4C"), ("dos-errors", "ibm-pc:error:1")):
        file = folder / f"{name}.json"
        dictionary, faults = rows_file.parse(file.read_text(encoding="utf-8"), name)
        assert dictionary is not None and not faults, faults
        for part in sealed.parts(dictionary):
            assert sealed.seal(file, [id_], lock, part, "reader", "writer") == []
    return rows.Base.load(folder, lock=sealed.read_lock(lock))


@pytest.fixture
def served_rows(fixture_base: rows.Base, monkeypatch: pytest.MonkeyPatch) -> rows.Base:
    """`fixture_base` as the base the server answers from."""
    monkeypatch.setattr(knowledge, "base", lambda: fixture_base)
    return fixture_base
