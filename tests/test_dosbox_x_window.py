"""The window a watched start opens: asked for with `display` and `fullscreen`, proved in the
host's window list, answered by `window`, and never retuned through `flags`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dosbox_x_server_support import _start_on_a_booted_fake
from scry_core import window as core_window
from window_double import Absent, Covered, Dragged, ObeyingHost, Stuck

from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import server
from scry_dosbox_x.state import STATE


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
def test_a_watched_start_asks_the_emulator_for_the_display_and_proves_the_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asked: dict[str, Any],
        flags: list[str]) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, **asked)
    assert got["status"] == "ok", got
    assert _flags() == flags
    window = got["window"]
    assert window["display"] == asked.get("display", 0) and window["onscreen"] is True, window
    assert window["fullscreen"] is bool(asked.get("fullscreen")), window
    server.close()


def test_a_start_nobody_watches_opens_no_window_and_says_nothing_of_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert got["status"] == "ok" and "window" not in got, got
    assert _flags() == []
    server.close()


@pytest.mark.parametrize("asked", [{"display": 0}, {"fullscreen": True},
                                   {"display": 1, "fullscreen": False}])
def test_the_window_arguments_without_shared_are_refused_not_ignored(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asked: dict[str, Any]) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, **asked)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "shared=true" in got["message"], got


def test_a_display_past_the_host_s_count_is_refused_naming_the_count(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, display=5)
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "2 displays (0 to 1)" in got["message"], got
    assert STATE.session is None


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


def test_a_window_the_emulator_never_opened_refuses_the_start_and_leaves_the_session_to_close(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_window, "host", lambda _platform="": Absent())
    monkeypatch.setattr("scry_dosbox_x.lifecycle.WINDOW_WAIT_S", 0.0)
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    assert got["status"] == "INVALID" and got["code"] == "window_not_visible", got
    assert STATE.session is not None, "the caller closes it, as the message says"
    server.close()


def test_window_answers_where_the_window_is_and_with_front_brings_it_forward(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, display=1)
    got = server.window()
    assert got["status"] == "ok" and got["window"]["display"] == 1, got
    forward = server.window(front=True)
    assert forward["status"] == "ok" and forward["window"]["front"] is True, forward
    server.close()


def test_window_answers_a_window_the_owner_dragged_to_another_display(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, display=0)
    monkeypatch.setattr(core_window, "host", lambda _platform="": Dragged())
    got = server.window()
    assert got["status"] == "ok" and got["window"]["display"] == 1, got
    server.close()


def test_window_front_on_a_background_session_says_a_background_app_cannot_come_forward(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_window, "host", lambda _platform="": Stuck())
    monkeypatch.setattr("scry_dosbox_x.lifecycle.WINDOW_WAIT_S", 0.0)
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, background=True)
    got = server.window(front=True)
    assert got["status"] == "INVALID" and got["code"] == "window_not_visible", got
    assert "background=true" in got["message"] and "background=false" in got["message"], got
    server.close()


def test_window_front_on_a_foreground_session_never_blames_the_background(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE CONTROL: the same stuck window, a session that was not launched behind."""
    monkeypatch.setattr(core_window, "host", lambda _platform="": Stuck())
    monkeypatch.setattr("scry_dosbox_x.lifecycle.WINDOW_WAIT_S", 0.0)
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, background=False)
    got = server.window(front=True)
    assert got["code"] == "window_not_visible" and "background" not in got["message"], got
    server.close()


def test_window_refuses_without_a_session_and_for_a_headless_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    none = server.window()
    assert none["status"] == "INVALID" and none["code"] == "no_session", none
    _start_on_a_booted_fake(tmp_path, monkeypatch)
    headless = server.window()
    assert headless["status"] == "INVALID" and headless["code"] == "no_channel", headless
    assert "shared=true" in headless["message"], headless
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


def test_window_front_activates_a_covered_window_and_without_front_only_reports_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = Covered()
    monkeypatch.setattr(core_window, "host", lambda _platform="": host)
    _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, display=1)
    host.activations = 0
    seen = server.window()
    assert seen["window"]["onscreen"] is False and host.activations == 0, seen
    forward = server.window(front=True)
    assert forward["window"]["onscreen"] is True and host.activations == 1, forward
    server.close()


def test_a_fullscreen_that_does_not_fill_the_display_is_refused_not_reported(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Bordered(ObeyingHost):
        def windows(self) -> list[core_window.Seen]:
            return [core_window.Seen(w.pid, w.number, (w.bounds[0], w.bounds[1] + 30,
                                                       w.bounds[2], w.bounds[3] - 30), True)
                    for w in super().windows()]
    monkeypatch.setattr(core_window, "host", lambda _platform="": Bordered())
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True, fullscreen=True)
    assert got["status"] == "INVALID" and got["code"] == "window_not_visible", got
    assert got["seen"]["fullscreen"] is False and "fullscreen" in got["message"], got
    server.close()
