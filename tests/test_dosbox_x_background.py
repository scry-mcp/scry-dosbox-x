"""Whether a launch takes the owner's focus: the SDL hint `start` sets or removes in the spawned
environment, decided by `background` and, omitted, by whether somebody watches."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import dosbox_launch as dlaunch
import dosbox_session as ds
import dosbox_x_server as server


@pytest.mark.parametrize(("background", "watched", "behind"), [
    (None, False, True), (None, True, False), (True, True, True), (False, False, False)])
def test_omitted_a_headless_start_goes_behind_and_a_shared_one_in_front(
        background: bool | None, watched: bool, behind: bool) -> None:
    assert dlaunch.judge_background(background, watched) is behind


def test_the_hint_is_set_or_removed_never_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(dlaunch.BACKGROUND_VAR, "1")
    assert dlaunch.BACKGROUND_VAR not in dlaunch.launch_environment(False)
    monkeypatch.delenv(dlaunch.BACKGROUND_VAR)
    assert dlaunch.launch_environment(True)[dlaunch.BACKGROUND_VAR] == "1"
    assert dlaunch.launch_environment(True)["TERM"] == "xterm-256color"


def test_the_session_spawns_the_emulator_with_the_launch_s_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read at the one place the process is made, so no start can bypass it."""
    seen: list[dict[str, str]] = []

    def spawn(*_a: Any, **kw: Any) -> None:
        seen.append(dict(kw["env"]))
        raise OSError("not spawned in a unit test")
    monkeypatch.setattr(subprocess, "Popen", spawn)
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    for behind in (True, False):
        launch = dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, background=behind)
        with pytest.raises(OSError, match="not spawned"):
            ds.Session(launch)
        assert (seen[-1].get(dlaunch.BACKGROUND_VAR) == "1") is behind, seen[-1]


def test_start_says_what_the_process_was_told(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake
    got = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert got["status"] == "ok" and got["background"] is True, got
    server.close()
    shown = _start_on_a_booted_fake(tmp_path, monkeypatch, background=False)
    assert shown["status"] == "ok" and shown["background"] is False, shown
    server.close()


def test_a_shared_start_goes_in_front_unless_told_otherwise(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake, placed_by
    placed_by(tmp_path, monkeypatch, "-set\nsdl display=1\n")
    shared = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    assert shared["status"] == "ok" and shared["background"] is False, shared
    server.close()
    behind = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, background=True)
    assert behind["status"] == "ok" and behind["background"] is True, behind
    server.close()


def test_a_live_runs_ledger_learns_the_emulator_the_session_spawned(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The run's proof that no emulator outlived it reads this ledger, written at the one place
    the process is made, before anything after it can fail; outside a live run nothing is."""
    from scry_core import live_host

    class Spawned:
        pid = 4321

        def poll(self) -> int:
            return 0

    def no_thread(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: Spawned())
    monkeypatch.setattr("threading.Thread", no_thread)
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    ledger = tmp_path / "emulators.tsv"
    for named in (True, False):
        if named:
            monkeypatch.setenv(live_host.LEDGER_VAR, str(ledger))
        else:
            monkeypatch.delenv(live_host.LEDGER_VAR)
            ledger.unlink()
        with pytest.raises(RuntimeError, match="new thread"):
            ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60))
        assert (live_host.EmulatorLedger(ledger).recorded() == {4321: "dosbox-x"}) is named
