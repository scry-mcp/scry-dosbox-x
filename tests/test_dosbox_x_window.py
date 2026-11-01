"""The window a watched start opens in DOSBox-X: the argv it asks the emulator for, the flags that
cannot retune it, and the `surface` output; the contract every server meets is core's."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import _start_on_a_booted_fake
from scry_core import conformance
from window_double import asked as session_window

from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import server
from scry_dosbox_x.state import STATE


class _Subject:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path, self.monkeypatch = tmp_path, monkeypatch
        self.asked = session_window
        self.shows_fullscreen = True

    def start(self, **arguments: Any) -> dict[str, Any]:
        return _start_on_a_booted_fake(self.tmp_path, self.monkeypatch, **arguments)

    def window(self, front: bool = False) -> dict[str, Any]:
        return cast(dict[str, Any], server.window(front=front))

    def close(self) -> dict[str, Any]:
        return cast(dict[str, Any], server.close())

    def status(self) -> dict[str, Any]:
        return cast(dict[str, Any], server.status())

    def has_session(self) -> bool:
        return STATE.session is not None


class TestDosboxXWindow(conformance.SessionContract):
    @pytest.fixture
    def subject(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Subject:
        return _Subject(tmp_path, monkeypatch)


def _flags() -> list[str]:
    assert STATE.session is not None
    argv = dlaunch.build_argv(STATE.session.launch)
    at = next((i for i, t in enumerate(argv) if t.startswith("sdl display=")), None)
    return [] if at is None else [*argv[at - 1:at + 1], *(["-fullscreen"] if "-fullscreen" in argv
                                                          else [])]


@pytest.mark.parametrize(("asked", "flags"), [
    ({}, ["-set", "sdl display=0"]),
    ({"display": 1}, ["-set", "sdl display=1"]),
    ({"display": 1, "fullscreen": True}, ["-set", "sdl display=1", "-fullscreen"]),
    ({"fullscreen": False}, ["-set", "sdl display=0"]),
])
def test_a_watched_start_asks_the_emulator_for_the_display(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asked: dict[str, Any],
        flags: list[str]) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, **asked)
    assert got["status"] == "ok", got
    assert _flags() == flags
    server.close()


def test_a_start_nobody_watches_opens_no_window_and_says_nothing_of_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert got["status"] == "ok" and "window" not in got, got
    assert _flags() == []
    server.close()


@pytest.mark.parametrize(("flag", "owner"), [
    (["-set", "sdl display=1"], "display"),
    (["-set", "sdl windowposition=0,0"], "display"),
    (["-set", "sdl fullscreen=true"], "fullscreen"),
    (["-fullscreen"], "fullscreen"),
])
def test_flags_cannot_retune_the_window_the_start_arguments_own(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: list[str], owner: str) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, flags=flag)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert f"through `{owner}`" in got["message"], got


def test_the_window_size_is_the_confs_and_the_refusal_says_so_not_fullscreen(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True,
                                  flags=["-set", "sdl windowresolution=640x480"])
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    message = got["message"]
    assert "the conf decides" in message and "[sdl]" in message and "windowresolution" in message
    assert "fullscreen" not in message, "`fullscreen` cannot set a size"


def test_the_other_sdl_sets_still_pass_flags(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """THE CONTROL: the refusal is of the window's keys, not of every `sdl` set."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True,
                                  flags=["-set", "sdl autolock=false"])
    assert got["status"] == "ok", got
    server.close()


def test_a_session_whose_emulator_has_died_is_session_broken_not_a_missing_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    try:
        assert STATE.session is not None
        STATE.session.alive_flag = False  # type: ignore[attr-defined]
        STATE.session.proc = SimpleNamespace(poll=lambda: 3)  # type: ignore[assignment]
        got = server.window()
        assert got["status"] == "INVALID" and got["code"] == "session_broken", got
    finally:
        server.close()


def test_the_background_hint_and_the_judge_are_core_s_not_a_copy() -> None:
    assert not hasattr(dlaunch, "judge_background") and not hasattr(dlaunch, "BACKGROUND_VAR")


@pytest.mark.parametrize(("conf_text", "flags", "refused"), [
    ("[sdl]\noutput=surface\n", None, True),
    ("[sdl]\noutput=opengl\n", ["-set", "sdl output=surface"], True),
    ("[sdl]\noutput=surface\n", ["-set", "sdl output=opengl"], False),
    ("[sdl]\n", None, False),
    ("[sdl]\noutput=openglnb\n", None, False),
])
def test_fullscreen_on_the_surface_output_is_refused_by_name_and_no_other_is(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conf_text: str,
        flags: list[str] | None, refused: bool) -> None:
    """`surface` switches the display's video mode and leaves the window off screen; the other
    outputs scale to the display and show."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, conf_text=conf_text, shared=True,
                                  fullscreen=True, flags=flags)
    if refused:
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "output=surface" in got["message"] and "fullscreen" in got["message"], got
    else:
        assert got["status"] == "ok", got
        server.close()


def test_a_windowed_start_on_the_surface_output_is_not_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE CONTROL: only the full-screen combination cannot show."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, conf_text="[sdl]\noutput=surface\n",
                                  shared=True)
    assert got["status"] == "ok", got
    server.close()


