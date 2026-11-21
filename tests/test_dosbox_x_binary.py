"""The binary ladder as this server climbs it; the ladder's own cases are scry-core's."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import window as core_window
from stub_builds import BANNER, build

from scry_dosbox_x import binary as binaries
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import server
from scry_dosbox_x import session as ds


@pytest.fixture
def on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `dosbox-x` the PATH finds, and nothing else."""
    found = build(tmp_path / "path-bin")
    monkeypatch.setenv("PATH", str(found.parent))
    return found


@pytest.mark.skipif(sys.platform == "win32", reason="`-version` is not run on Windows")
def test_build_check_answers_the_three_fields_and_asks_the_build_it_resolved(
        tmp_path: Path, on_path: Path) -> None:
    mine = build(tmp_path / "arg")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    assert (got["binary"], got["binary_origin"], got["version"]) == (str(mine), "argument",
                                                                     BANNER)
    plain = cast(dict[str, Any], server.build_check())
    # Windows' lookup spells the extension as PATHEXT does, so names are compared by the host's case
    assert (os.path.normcase(plain["binary"]), plain["binary_origin"]) == (
        os.path.normcase(on_path), "PATH"), plain


def test_build_check_on_a_build_with_no_version_still_answers(tmp_path: Path) -> None:
    mine = build(tmp_path, version="sys.exit(1)")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok" and got["version"]["available"] is False, got






@pytest.mark.parametrize("resource", ["2026.10.01", None])
def test_a_build_on_windows_reads_its_version_from_the_file_and_never_runs_the_probe(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resource: str | None) -> None:
    """DOSBox-X's own `-version` opens a console there and waits for a key, so it never returns."""
    seen = tmp_path / "seen"
    mine = build(tmp_path, version=f"open({str(seen)!r}, 'a').write('v'); "
                 f"sys.stderr.write({BANNER!r}); sys.exit(1)")
    monkeypatch.setattr(dlaunch, "VERSION_PROBE_HANGS", True)
    monkeypatch.setattr(dlaunch, "file_version", lambda _path: resource)
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    if resource is None:
        assert got["version"]["available"] is False, got
    else:
        assert resource in got["version"], got
    assert not seen.exists(), "`-version` was spawned on a host where it never returns"


def test_build_check_names_each_missing_command_with_the_tools_it_disables(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mine = build(tmp_path)
    monkeypatch.setattr(binaries, "debugger_commands", lambda _path: ["PIC", "A20"])
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    missing = {row["command"]: row["disables"] for row in got["debugger_commands_missing"]}
    assert list(missing) == [c for c in binaries.COMMANDS if c not in ("PIC", "A20")], got
    assert {"run_to", "run_for", "trace", "screen_wait"} <= set(missing["RUNSTATE"]), got
    assert got["debugger_commands"] == ["PIC", "A20"], got


def test_build_check_omits_the_missing_field_when_the_build_has_every_command(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mine = build(tmp_path)
    monkeypatch.setattr(binaries, "debugger_commands", lambda _path: list(binaries.COMMANDS))
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok" and "debugger_commands_missing" not in got, got


def test_every_optional_command_says_what_it_disables() -> None:
    assert set(binaries.DISABLES) == set(binaries.COMMANDS)
    assert all(binaries.DISABLES[name] for name in binaries.COMMANDS)


def test_the_recordings_need_runstate_since_their_retraces_run_as_run_for_does() -> None:
    """`record` and `audio_record` run their retraces through `retrace.run_for`, which refuses a
    build without `RUNSTATE`, so `build_check` names them among what that build cannot serve."""
    assert {"record", "audio_record"} <= set(binaries.DISABLES["RUNSTATE"])


def test_build_check_judges_the_build_by_its_bytes_and_never_waits_on_helpdebug(
        tmp_path: Path) -> None:
    """Windows' GUI build prints `-helpdebug` to no stream and does not exit: a build whose
    option never returns is answered off its bytes, at once."""
    import time
    mine = build(tmp_path, helpdebug="import time; time.sleep(60)")
    began = time.monotonic()
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok" and got["debugger"] is True, got
    assert time.monotonic() - began < 10, "it waited on `-helpdebug`"


@pytest.mark.skipif(sys.platform == "win32", reason="`-version` is not run on Windows")
def test_the_version_probe_of_a_build_spawns_it_behind_as_a_session_does(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe runs behind, as a session does: an unknown option starts the emulator."""
    monkeypatch.delenv(core_window.BACKGROUND_VAR, raising=False)
    seen = tmp_path / "seen"
    def records(tag: str) -> str:
        return (f"open({str(seen)!r}, 'a').write("
                f"'{tag}=' + os.environ.get({core_window.BACKGROUND_VAR!r}, '') + '\\n')")
    mine = build(tmp_path, version=f"{records('v')}; sys.stderr.write({BANNER!r}); sys.exit(1)",
                 helpdebug=f"{records('h')}; print('-break-start')")
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got["status"] == "ok", got
    assert seen.read_text().split() == ["v=1"], "`-helpdebug` was run: " + seen.read_text()
    seen.unlink()
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    def spawn(launch: Any) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    monkeypatch.setattr("scry_dosbox_x.server.ds.Session", spawn)
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


def test_a_bare_pic_or_a20_word_in_a_build_is_not_the_debuggers_command(tmp_path: Path) -> None:
    other = tmp_path / "other-dosbox-x"
    other.write_bytes(b"\0PIC\0\0A20\0 log groups and a conf word, no debugger command")
    assert not {"PIC", "A20"} & set(binaries.debugger_commands(str(other)))
    carries = tmp_path / "dosbox-x"
    carries.write_bytes(b"\0MASKIRQ\0\0ACKIRQ\0 A20 gate is %s\n")
    assert {"PIC", "A20"} <= set(binaries.debugger_commands(str(carries)))


@pytest.mark.parametrize("marks, layers", [
    (b"\0PRESENCE\0", ["edge", "pointer"]),
    (b"\0PRESENCE\0\0layers\0\0keycap_text_rgb\0", ["edge", "pointer", "keys", "calls", "pause"]),
    (b"\0keycap_text_rgb\0", []),
    (b"a word of a build that has no command", []),
])
def test_the_layers_a_build_draws_are_read_off_the_literal_of_protocol_3(
        tmp_path: Path, marks: bytes, layers: list[str]) -> None:
    mine = tmp_path / "dosbox-x"
    mine.write_bytes(marks)
    assert binaries.presence_layers(str(mine), binaries.debugger_commands(str(mine))) == layers


@pytest.mark.parametrize("commands, layers", [(["PRESENCE"], ["edge", "pointer"]), (["PIC"], None)])
def test_build_check_lists_the_layers_the_build_draws_and_omits_them_without_the_command(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commands: list[str],
        layers: list[str] | None) -> None:
    mine = build(tmp_path)
    monkeypatch.setattr(binaries, "debugger_commands", lambda _path: commands)
    got = cast(dict[str, Any], server.build_check(binary=str(mine)))
    assert got.get("presence_layers") == layers, got
