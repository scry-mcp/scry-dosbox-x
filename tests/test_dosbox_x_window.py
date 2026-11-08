"""The window a watched start opens in DOSBox-X: the argv it asks the emulator for, the flags that
cannot retune it, and the `surface` output; the contract every server meets is core's."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import _start_on_a_booted_fake
from scry_core import conformance, window_size
from scry_core import window as core_window
from scry_core.window_stand_ins import hosts
from window_double import asked as session_window

from scry_dosbox_x import conf as dconf
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import lifecycle, server
from scry_dosbox_x.state import STATE


class _Subject:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path, self.monkeypatch = tmp_path, monkeypatch
        self.asked = session_window
        self.shows_fullscreen = sys.platform != window_size.DOSBOX_X_HALTED_MAIN_ONLY_ON
        self.takes_fullscreen = True

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
    """The display, position and full-screen tokens of the live session's argv."""
    assert STATE.session is not None
    argv = dlaunch.build_argv(STATE.session.launch)
    at = next((i for i, t in enumerate(argv) if t.startswith("sdl display=")), None)
    if at is None:
        return []
    end = at + 3 if argv[at + 2].startswith("sdl windowposition=") else at + 1
    return [*argv[at - 1:end], *(["-fullscreen"] if "-fullscreen" in argv else [])]


#: Where a window's top goes: Windows places its frame above the client area.
TOP = 51 if sys.platform == "win32" else 40


@pytest.mark.parametrize(("asked", "flags"), [
    ({}, ["-set", "sdl display=0", "-set", f"sdl windowposition=40,{TOP}"]),
    ({"display": 1}, ["-set", "sdl display=1", "-set", f"sdl windowposition=1960,{TOP}"]),
    ({"display": 0, "fullscreen": True},
     ["-set", "sdl display=0", "-fullscreen"]),
    ({"fullscreen": False}, ["-set", "sdl display=0", "-set", f"sdl windowposition=40,{TOP}"]),
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
    (["-set", "sdl windowresolution=640x480"], "size"),
])
def test_flags_cannot_retune_the_window_the_start_arguments_own(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: list[str], owner: str) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, flags=flag)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert f"through `{owner}`" in got["message"], got


def test_the_other_sdl_sets_still_pass_flags(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """THE CONTROL: the refusal is of the window's keys, not of every `sdl` set."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True,
                                  flags=["-set", "sdl autolock=false"])
    assert got["status"] == "ok", got
    server.close()


def test_a_start_refused_for_its_window_keeps_the_presence_it_was_asked_for(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_window, "WAIT_S", 0.0)
    monkeypatch.setattr(core_window, "host", lambda _platform="": hosts.Dragged(session_window))
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, display=0, presence=True)
    assert got["status"] == "INVALID" and got["code"] == "window_not_visible", got
    assert STATE.session is not None, "the refusal leaves the session live"
    opened = getattr(STATE.session, "presence", None)
    assert opened is not None and opened.reply() is not False, "presence never opened"
    server.close()


def test_a_session_whose_emulator_has_died_is_session_broken_not_a_missing_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    try:
        assert STATE.session is not None
        STATE.session.alive_flag = False  # type: ignore[attr-defined]
        STATE.session.proc = SimpleNamespace(poll=lambda: 3)
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


@pytest.mark.parametrize(("platform", "display", "refused"), [
    ("darwin", 1, True), ("darwin", 0, False), ("win32", 1, False)])
def test_fullscreen_off_the_main_display_is_refused_where_a_halted_start_cannot_reach_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, display: int,
        refused: bool) -> None:
    """The scry build on macOS goes full screen on another display only once the emulator runs,
    and a start is halted at its first instruction: the window would stay windowed."""
    monkeypatch.setattr("sys.platform", platform)
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, fullscreen=True,
                                  display=display)
    if refused:
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "display" in got["message"] and "fullscreen" in got["message"], got
        assert STATE.session is None
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




def test_a_stated_size_reaches_the_command_line_as_windowresolution_and_the_window_judges_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, size="1280x960")
    try:
        assert got["status"] == "ok", got
        seen = server.window()
        assert seen["size"]["asked"] == {"width": 1280, "height": 960}, seen
        assert seen["size"]["matches"] is True, seen
    finally:
        server.close()


@pytest.mark.parametrize(("matches", "stop_count", "parked", "noted"), [
    (False, 1, True, True), (False, 2, True, False), (False, 1, False, False),
    (True, 1, True, False)])
def test_a_window_without_its_size_says_why_only_while_the_guest_has_never_run(
        monkeypatch: pytest.MonkeyPatch, matches: bool, stop_count: int, parked: bool,
        noted: bool) -> None:
    reply = {"window": {"display": 0}, "size": {"matches": matches}}
    monkeypatch.setattr(core_window, "answer", lambda *a, **k: dict(reply))
    session = SimpleNamespace(pid=1, launch=SimpleNamespace(window=None, background=False),
                              parked=parked, stop_count=stop_count)
    got = lifecycle.window(cast(Any, session), False)
    assert ("first video mode" in str(got.get("note", ""))) is noted, got


@pytest.mark.parametrize("arguments", [{"size": "1280x960"}, {"shared": True, "size": "wide"},
                                       {"shared": True, "size": "99999x99999"},
                                       {"shared": True, "size": "640x480", "fullscreen": True}])
def test_a_size_that_cannot_act_is_refused_before_the_emulator_starts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: dict[str, Any]) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")      # on Linux the host check answers first
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, **arguments)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert STATE.session is None


@pytest.mark.parametrize(("output", "platform", "taken"), [
    ("opengl", "darwin", True), ("openglnb", "win32", True), ("openglhq", "win32", True),
    ("openglpp", "darwin", True), ("direct3d", "win32", True), ("default", "darwin", True),
    ("default", "win32", True), ("surface", "darwin", False), ("ttf", "darwin", False)])
def test_a_size_under_an_output_that_ignores_it_is_refused_naming_the_output(
        output: str, platform: str, taken: bool) -> None:
    assert dconf.honours_window_size(output, platform) is taken


@pytest.mark.parametrize(("conf_text", "flags", "aware"), [
    ("[dosbox]\ndpi aware=true\n", [], True), ("[dosbox]\ndpi aware=1\n", [], True),
    ("[dosbox]\ndpi aware=false\n", [], False), ("[dosbox]\ndpi aware=0\n", [], False),
    ("[dosbox]\ndpi aware=auto\n", [], None), ("[dosbox]\n", [], None), ("", [], None),
    ("[dosbox]\ndpi aware=true\n", ["-set", "dosbox dpi aware=false"], False),
    ("[sdl]\ndpi aware=true\n", [], None),
    ("[dosbox]\ndpi aware=true\n", ["-nodpiaware"], False),     # the flag ignores the setting
    ("[dosbox]\ndpi aware=true\n", ["-set", "dpi aware=false"], False),   # no section named
    ("[dosbox]\ndpi aware=false\n", ["-set", "dpi aware=true"], True),
])
def test_the_dpi_awareness_a_conf_or_a_set_states_is_read_as_true_false_or_auto(
        tmp_path: Path, conf_text: str, flags: list[str], aware: bool | None) -> None:
    conf = tmp_path / "t.conf"
    conf.write_text(conf_text)
    assert dconf.dpi_awareness(conf, flags) is aware


def test_the_request_carries_the_dpi_awareness_the_size_words_need(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    conf = tmp_path / "t.conf"
    conf.write_text("[dosbox]\ndpi aware=true\n")
    wanted = core_window.WindowRequest(0, False, (0, 0), size=(1280, 960))
    judged = lifecycle._judge_window(wanted, conf, [])
    assert judged is not None and judged.dpi_aware is True


class _WithUsable(hosts.Obeying):
    """Displays that report a usable area 30 short at the top, as a macOS menu bar does."""

    def displays(self) -> list[core_window.Display]:
        return [replace(d, usable=(d.bounds[0], d.bounds[1] + 30, d.bounds[2], d.bounds[3] - 30))
                for d in hosts.DISPLAYS]


def _argv_window_words(**start: Any) -> list[str]:
    assert STATE.session is not None
    return [t for t in dlaunch.build_argv(STATE.session.launch) if t.startswith("sdl window")]


def _started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conf_text: str = "[sdl]\n",
             **arguments: Any) -> dict[str, Any]:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(core_window, "host", lambda _platform="": _WithUsable(session_window))
    return _start_on_a_booted_fake(tmp_path, monkeypatch, conf_text=conf_text, shared=True,
                                   **arguments)


def test_a_stated_size_is_the_windowresolution_the_emulator_is_told(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _started(tmp_path, monkeypatch, size="1280x960")
    try:
        assert got["status"] == "ok", got
        assert "sdl windowresolution=1280x960" in _argv_window_words()
    finally:
        server.close()


def test_a_watched_window_with_no_size_gets_the_largest_4_3_one_the_usable_area_holds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _started(tmp_path, monkeypatch)
    try:
        assert got["status"] == "ok", got
        fitted = window_size.aspect_fit((4, 3), (0, 30, 1920, 1050), 1.0, "darwin")
        assert f"sdl windowresolution={fitted[0]}x{fitted[1]}" in _argv_window_words()
        assert "size" not in server.window(), "the server's own choice is not judged"
    finally:
        server.close()


@pytest.mark.parametrize("size", ["800x600", "desktop", "original"])
def test_a_size_the_conf_states_is_not_overridden_by_the_fit(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: str) -> None:
    got = _started(tmp_path, monkeypatch, conf_text=f"[sdl]\nwindowresolution={size}\n")
    try:
        assert got["status"] == "ok", got
        assert not [t for t in _argv_window_words() if "windowresolution" in t]
    finally:
        server.close()


def test_under_an_output_that_ignores_a_size_it_is_refused_and_no_fit_is_made(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = "[sdl]\noutput=surface\n"
    refused = _started(tmp_path, monkeypatch, conf_text=conf, size="1280x960")
    assert refused["status"] == "INVALID" and refused["code"] == "bad_argument", refused
    assert "output=surface" in refused["message"] and STATE.session is None
    got = _started(tmp_path, monkeypatch, conf_text=conf)
    try:
        assert got["status"] == "ok", got
        assert not [t for t in _argv_window_words() if "windowresolution" in t]
    finally:
        server.close()
