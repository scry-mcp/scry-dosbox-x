"""The window tier of DOSBox-X: a cover over the emulator's window, and `window(front=True)`
bringing it back, launched in front or behind. It moves the owner's desk: `-m window`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from scry_core import window_stand_ins as stand_ins
from test_dosbox_x_live import CONF, CWD, LIVE_MARKS

from scry_dosbox_x import server

pytestmark = LIVE_MARKS


def _window(**arguments: Any) -> dict[str, Any]:
    return cast(dict[str, Any], server.window(**arguments))


def _started(background: bool) -> int:
    started = cast(dict[str, Any], server.start(conf=CONF or "", cwd=CWD, session_seconds=60,
                                                shared=True, display=0, background=background))
    assert started["status"] == "ok" and started["background"] is background, started
    return cast(int, started["pid"])


@stand_ins.on_the_desk
def test_window_front_brings_the_emulator_back_from_behind_a_full_screen_application(
        tmp_path: Path) -> None:
    try:
        with stand_ins.under_a_cover(_started(background=False), tmp_path):
            stand_ins.comes_forward(_window)
    finally:
        server.close()


@stand_ins.on_the_desk
def test_window_front_brings_a_background_session_back_too(tmp_path: Path) -> None:
    try:
        with stand_ins.under_a_cover(_started(background=True), tmp_path):
            stand_ins.comes_forward(_window)
    finally:
        server.close()
