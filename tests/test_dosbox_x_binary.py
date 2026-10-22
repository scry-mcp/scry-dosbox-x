"""The binary ladder as this server climbs it: the rungs it names (`DOSBOX_X_BINARY`, the PATH's
`dosbox-x`) and what `start` and `build_check` do with the build they land on. The ladder's own
cases, each rung and the version probe, are scry-core's (`tests/test_binaries.py`).

The builds are small shell programs of each case's own, run for real.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

import dosbox_binary as binaries
import dosbox_launch as dlaunch
import dosbox_session as ds
import dosbox_x_server as server

# The stub answers as the real build does (`dosbox_binary.version`).
BANNER = "DOSBox-X version 0.0.0 SDL2, a stub build"


def build(where: Path, *, version: str = f'echo "{BANNER}" >&2; exit 1',
          name: str = "dosbox-x") -> Path:
    """An executable at `where/name` answering `-version` with the shell in `version` and
    `-helpdebug` with the line a debugger build lists, carrying the debugger's own text as a
    debugger build does."""
    where.mkdir(parents=True, exist_ok=True)
    path = where / name
    path.write_text("#!/bin/sh\n"
                    f"# {binaries.DEBUGGER_MARK.decode()}\n"
                    f'case "$1" in -version) {version} ;; -helpdebug) echo "-break-start" ;; '
                    "esac\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `dosbox-x` the PATH finds, and nothing else on the PATH."""
    found = build(tmp_path / "path-bin")
    monkeypatch.setenv("PATH", str(found.parent))
    return found






























def test_build_check_answers_the_three_fields_and_asks_the_build_it_resolved(
        tmp_path: Path, on_path: Path) -> None:
    mine = build(tmp_path / "arg")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    assert (got["binary"], got["binary_origin"], got["version"]) == (str(mine), "argument",
                                                                     BANNER)
    plain = cast(dict[str, Any], server.build_check())
    assert (plain["binary"], plain["binary_origin"]) == (str(on_path), "PATH"), plain


def test_build_check_on_a_build_with_no_version_still_answers(tmp_path: Path) -> None:
    mine = build(tmp_path, version="exit 1")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok" and got["version"]["available"] is False, got






def test_both_probes_of_a_build_spawn_it_behind_as_a_session_does(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An option this build does not know starts the emulator, so its `-version` and
    `-helpdebug` probes are launched as a session is, behind, whatever the server's own
    environment holds."""
    monkeypatch.delenv(dlaunch.BACKGROUND_VAR, raising=False)
    seen = tmp_path / "seen"
    mine = build(tmp_path, version=f'echo "v=${dlaunch.BACKGROUND_VAR}" >> {seen}; '
                                    f'echo "{BANNER}" >&2; exit 1')
    text = mine.read_text().replace(
        '-helpdebug) echo "-break-start"',
        f'-helpdebug) echo "h=${dlaunch.BACKGROUND_VAR}" >> {seen}; echo "-break-start"')
    assert text != mine.read_text(), "the -helpdebug arm was not found to record its env"
    mine.write_text(text)
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    assert sorted(seen.read_text().split()) == ["h=1", "v=1"], seen.read_text()
    # AND `start`'s own probe, before it spawns the session.
    seen.unlink()
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    def spawn(launch: Any) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    monkeypatch.setattr("dosbox_x_server.ds.Session", spawn)
    server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=60, binary=str(mine))
    assert seen.read_text().split() == ["v=1"], seen.read_text()
