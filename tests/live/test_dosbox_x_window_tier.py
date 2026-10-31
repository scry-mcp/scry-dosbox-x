"""The window tier of DOSBox-X: a full-screen application takes the Space the emulator's window is
on, and `window(front=True)` brings it back. It switches the owner's desk, so it is out of every
default run (`-m window`, with `SCRY_FOCUS_CONTROL=1` on a Mac)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from scry_core import window as core_window
from scry_core import window_stand_ins as stand_ins
from test_dosbox_x_live import CONF, CWD, LIVE_MARKS

from scry_dosbox_x import server

pytestmark = LIVE_MARKS


@stand_ins.on_the_desk
def test_window_front_brings_the_emulator_back_from_behind_a_full_screen_application(
        tmp_path: Path) -> None:
    started = cast(dict[str, Any], server.start(conf=CONF or "", cwd=CWD, session_seconds=60,
                                                shared=True, display=0, background=False))
    assert started["status"] == "ok", started
    host = core_window.host()
    cover = subprocess.Popen([str(stand_ins.built(tmp_path, "cover"))])
    try:
        pid = cast(int, started["pid"])
        stand_ins.until("the full-screen application taking the Space",
                        lambda: (s := core_window.state_of(pid, host.windows(), host.displays(),
                                                           host.above)) is not None
                        and not s.onscreen)
        behind = cast(dict[str, Any], server.window())["window"]
        assert behind["onscreen"] is False, behind
        front = cast(dict[str, Any], server.window(front=True))
        assert front["status"] == "ok", front
        assert front["window"]["onscreen"] is True and front["window"]["front"] is True, front
    finally:
        cover.terminate()
        cover.wait(timeout=10)
        server.close()
