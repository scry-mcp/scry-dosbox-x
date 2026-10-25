"""The binary ladder as this server climbs it; the ladder's own cases are scry-core's."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest
from stub_builds import BANNER, build

import dosbox_binary as binaries
import dosbox_launch as dlaunch
import dosbox_session as ds
import dosbox_x_server as server


@pytest.fixture
def on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `dosbox-x` the PATH finds, and nothing else."""
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
    mine = build(tmp_path, version="sys.exit(1)")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok" and got["version"]["available"] is False, got






def test_both_probes_of_a_build_spawn_it_behind_as_a_session_does(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both probes run behind, as a session does: an unknown option starts the emulator."""
    monkeypatch.delenv(dlaunch.BACKGROUND_VAR, raising=False)
    seen = tmp_path / "seen"
    def records(tag: str) -> str:
        return (f"open({str(seen)!r}, 'a').write("
                f"'{tag}=' + os.environ.get({dlaunch.BACKGROUND_VAR!r}, '') + '\\n')")
    mine = build(tmp_path, version=f"{records('v')}; sys.stderr.write({BANNER!r}); sys.exit(1)",
                 helpdebug=f"{records('h')}; print('-break-start')")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    assert sorted(seen.read_text().split()) == ["h=1", "v=1"], seen.read_text()
    seen.unlink()
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    def spawn(launch: Any) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    monkeypatch.setattr("dosbox_x_server.ds.Session", spawn)
    server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=60, binary=str(mine))
    assert seen.read_text().split() == ["v=1"], seen.read_text()


def test_build_check_with_nothing_resolvable_is_host_failed_and_names_no_binary(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An INVALID reply carries no `binary`, which would read as a build found."""
    monkeypatch.delenv(binaries.VARIABLE, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    got = cast(dict[str, Any], server.build_check())
    assert got["code"] == "host_failed" and "binary" not in got, got
    assert "no DOSBox-X binary resolves from the PATH rung" in got["message"], got


@pytest.mark.skipif(sys.platform == "win32", reason="Windows runs no file by a mode bit")
def test_build_check_on_an_executable_the_host_cannot_run_is_host_failed(
        tmp_path: Path) -> None:
    empty = tmp_path / "dosbox-x"
    empty.write_bytes(b"")
    empty.chmod(0o755)
    got = cast(dict[str, Any], server.build_check(binary=str(empty)))
    assert got["code"] == "host_failed", got
    assert str(empty) in got["message"], got
