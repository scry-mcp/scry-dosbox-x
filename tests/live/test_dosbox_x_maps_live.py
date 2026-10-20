"""Screen maps on a real screen: bricks' own map (`demos/bricks/bricks.scry-map.json`, written by
a session through `map_add` and `map_save`) recognises the play screen off one read, and a
control named on it is clicked by name, the game logging that its paddle followed the pointer.

The map knows the play screen by the two words of its header, `SCORE` and `LIVES` without their
digits: the border and the court change colour from one stop to the next, so they would match
no later stop."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_x_server as server

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
BRICKS = ROOT / "demos" / "bricks"
MAP = BRICKS / "bricks.scry-map.json"
#: The control the map names on the play screen, and its centre: where the paddle goes.
COURT_CENTRE = [240, 100]


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r.get("summary")
    return r


def test_bricks_map_finds_the_play_screen_and_a_control_is_clicked_by_name(
        tmp_path: Path) -> None:
    _ok(server.start(conf=str(BRICKS / "bricks.conf"), cwd=str(BRICKS), session_seconds=300,
                     logfile=str(tmp_path / "bricks-e9.log")))
    try:
        loaded = _ok(server.map_load(path=str(MAP)))
        assert (loaded["application"], loaded["screens"], loaded["controls"]) == ("bricks", 1, 1)
        # Parked before anything set a video mode there is no screen to read: the find fails,
        # and a failed find identifies nothing a control could be clicked on.
        unread = cast(dict[str, Any], server.map_find())
        assert unread["code"] == "no_channel", unread
        unaimed = cast(dict[str, Any], server.send_mouse(target="court"))
        assert unaimed["code"] == "needs_call", unaimed
        _ok(server.resume())
        _ok(server.log_wait(pattern="BRICKS ready", channel="guest", seconds=30))
        _ok(server.stop())
        at = _ok(server.status())["last_stop"]["stop_seq"]
        found = _ok(server.map_find())
        assert (found["matched"], found["screen"], found["layer"]) == (True, "play", "file")
        assert found["controls"][0]["centre"] == COURT_CENTRE
        # The session layer: the screen in front, saved beside the loaded one as one map.
        added = _ok(server.map_add(screen="header", match=[[0, 0, 52, 8]]))
        assert added["shadows_file"] is False
        saved = _ok(server.map_save(dest=str(tmp_path / "bricks.scry-map.json")))
        assert saved["screens"] == 2 and saved["promoted"] == ["header"]
        _ok(server.resume())
        _ok(server.send_keys(keys=["m"], expect="MOUSE ON$", seconds=10))
        clicked = _ok(server.send_mouse(target="court", expect="MOUSE$", seconds=10))
        assert (clicked["target"], clicked["screen"]) == ("court", "play")
        assert clicked["identified_at_stop"] == at
        pointer = clicked["pointer"]["screen"]
        assert [pointer["x"], pointer["y"]] == COURT_CENTRE and clicked["arrived"] is True
        assert clicked["verify"]["seen"] is True, clicked["verify"]
        # THE NEGATIVE, with its control first: stopped, the play screen still matches; one
        # pixel of the header's `S` changed in video memory (mode 13h, A000:0000, a byte a pixel,
        # 320 a row), and nothing the map holds is that screen any more.
        _ok(server.stop())
        assert _ok(server.map_find())["screen"] == "play"
        # White on the default palette, or black where it was white: two pens that are two
        # colours (the top eight of the default palette are all black, so a flipped index is
        # not always a changed pixel).
        pixel = int(_ok(server.read_memory(ref="A000:0141", length=1))["hex"][:2], 16)
        _ok(server.write(ref="A000:0141", data_hex="00" if pixel == 0x0F else "0f"))
        changed = _ok(server.map_find())
        assert changed["matched"] is False and changed["screens_tried"] == 2, changed
    finally:
        server.close()
