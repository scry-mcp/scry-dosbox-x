"""The binary ladder: the argument, then `DOSBOX_X_BINARY`, then the PATH's `dosbox-x`, and the
three fields `start` and `build_check` answer with.

The builds are small shell programs of each case's own, run for real: `-version` and
`-helpdebug` answer the way the case needs, so `shutil.which` and the version call are exercised
as they run in production, not stood in for.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core.reply_contract import Invalid

import dosbox_binary as binaries
import dosbox_x_server as server

# The stub answers as the real build does (`dosbox_binary.version`).
BANNER = "DOSBox-X version 0.0.0 SDL2, a stub build"


def build(where: Path, *, version: str = f'echo "{BANNER}" >&2; exit 1',
          name: str = "dosbox-x") -> Path:
    """An executable at `where/name` answering `-version` with the shell in `version` and
    `-helpdebug` with the line that says the debugger is there."""
    where.mkdir(parents=True, exist_ok=True)
    path = where / name
    path.write_text("#!/bin/sh\n"
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


def test_the_argument_wins_over_the_variable(tmp_path: Path, on_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    mine = build(tmp_path / "arg")
    monkeypatch.setenv(binaries.VARIABLE, str(build(tmp_path / "var")))
    assert binaries.resolve(str(mine)) == binaries.Resolved(str(mine), "argument")


def test_the_variable_wins_over_the_path(tmp_path: Path, on_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    held = build(tmp_path / "var")
    monkeypatch.setenv(binaries.VARIABLE, str(held))
    assert binaries.resolve("") == binaries.Resolved(str(held), "DOSBOX_X_BINARY")


def test_the_path_is_the_last_rung(on_path: Path) -> None:
    assert binaries.resolve("") == binaries.Resolved(str(on_path), "PATH")


def test_nothing_resolvable_is_invalid_naming_all_three_rungs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    for rung in ("`binary` held nothing", "DOSBOX_X_BINARY held nothing", "no `dosbox-x`"):
        assert rung in got["message"], (rung, got["message"])
    assert "binary" not in got, "an INVALID reply may not carry a binary"


def test_a_wrong_first_rung_is_refused_never_passed_over(
        tmp_path: Path, on_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A named build that is not there is refused, though the PATH holds a good one."""
    gone = str(tmp_path / "nope" / "dosbox-x")
    with pytest.raises(Invalid, match="from the argument rung") as refused:
        binaries.resolve(gone)
    assert f"{gone} (no such file)" in str(refused.value) and str(on_path) in str(refused.value)
    monkeypatch.setenv(binaries.VARIABLE, gone)
    with pytest.raises(Invalid, match="from the DOSBOX_X_BINARY rung"):
        binaries.resolve("")


def test_a_dangling_link_is_no_such_file_not_a_missing_exec_bit(
        tmp_path: Path, on_path: Path) -> None:
    link = tmp_path / "dosbox-x"
    link.symlink_to(tmp_path / "gone")
    with pytest.raises(Invalid, match=r"\(no such file\)"):
        binaries.resolve(str(link))


def test_a_wrong_argument_does_not_fall_through_to_the_variable(
        tmp_path: Path, on_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(binaries.VARIABLE, str(build(tmp_path / "var")))
    with pytest.raises(Invalid, match="from the argument rung"):
        binaries.resolve(str(tmp_path / "nope" / "dosbox-x"))


def test_the_path_answered_is_the_file_which_approved(tmp_path: Path, on_path: Path) -> None:
    """Through a symlinked directory, `..` names the target's parent; collapsed by spelling it
    would name a file beside the link, which is not the one checked."""
    target = tmp_path / "real" / "deep"
    target.mkdir(parents=True)
    build(tmp_path / "real")
    (tmp_path / "link").symlink_to(target)
    given = str(tmp_path / "link" / ".." / "dosbox-x")
    assert binaries.resolve(given).path == given


def test_a_directory_or_a_file_without_its_exec_bit_is_refused_saying_which(
        tmp_path: Path, on_path: Path) -> None:
    with pytest.raises(Invalid, match=r"argument rung.*\(a directory\)"):
        binaries.resolve(str(tmp_path))
    unrunnable = build(tmp_path / "plain")
    unrunnable.chmod(0o644)
    with pytest.raises(Invalid, match=r"\(not executable\)"):
        binaries.resolve(str(unrunnable))


@pytest.mark.parametrize("given", ["dosbox-x", "bin/dosbox-x", "./dosbox-x"])
def test_a_relative_path_is_refused_in_the_argument_and_in_the_variable(
        given: str, on_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(Invalid) as refused:
        binaries.resolve(given)
    assert refused.value.code == "bad_argument" and "binary=" in str(refused.value)
    monkeypatch.setenv(binaries.VARIABLE, given)
    with pytest.raises(Invalid) as refused:
        binaries.resolve("")
    assert refused.value.code == "bad_argument" and "DOSBOX_X_BINARY=" in str(refused.value)


def test_the_version_is_the_banner_whatever_the_exit_code(tmp_path: Path) -> None:
    assert binaries.version(str(build(tmp_path))) == BANNER
    on_stdout = build(tmp_path / "out", version='printf "\\n  v 1.2  \\n"')
    assert binaries.version(str(on_stdout)) == "v 1.2"


def test_a_version_call_that_prints_nothing_is_unavailable(tmp_path: Path) -> None:
    got = binaries.version(str(build(tmp_path, version="exit 1")))
    assert got == {"available": False,
                   "why": f"`{tmp_path / 'dosbox-x'} -version` printed nothing (rc=1)"}


def test_a_version_call_that_hangs_is_unavailable_within_its_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(binaries, "VERSION_TIMEOUT_S", 0.2)
    got = binaries.version(str(build(tmp_path, version="exec sleep 5")))
    assert isinstance(got, dict) and got["available"] is False
    assert "did not return in 0.2 s" in got["why"], got


def test_a_version_call_that_cannot_run_is_unavailable(tmp_path: Path) -> None:
    got = binaries.version(str(tmp_path / "gone"))
    assert isinstance(got, dict) and got["available"] is False and "could not run" in got["why"]


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


def test_a_relative_path_entry_through_a_link_names_the_file_which_found(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "real" / "deep"
    target.mkdir(parents=True)
    build(tmp_path / "real" / "bin")
    (tmp_path / "link").symlink_to(target)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "link/../bin")
    got = binaries.resolve("")
    assert Path(got.path).resolve() == (tmp_path / "real" / "bin" / "dosbox-x").resolve(), got


def test_the_path_rung_answers_an_absolute_path(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """A relative PATH entry finds a relative file; the reply names it absolutely."""
    build(tmp_path / "rel")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "rel")
    got = binaries.resolve("")
    assert got == binaries.Resolved(os.path.join(str(tmp_path), "rel", "dosbox-x"), "PATH")
