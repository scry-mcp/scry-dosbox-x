"""Bricks' own map recognises the play screen off one read and a control is clicked by name."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import live_private  # isort: skip -- first: a pooled job's working copies
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

from scry_dosbox_x import server

pytestmark = pytest.mark.live

BRICKS = live_private.bricks_dir()
MAP = BRICKS / "bricks-screen-map.json"
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
        loaded = _ok(server.screen_map_write("load", path=str(MAP)))
        assert (loaded["application"], loaded["screens"], loaded["controls"]) == ("bricks", 1, 1)
        # Parked before any video mode is set there is no screen to read.
        unread = cast(dict[str, Any], server.screen_map_find())
        assert unread["code"] == "no_channel", unread
        unaimed = cast(dict[str, Any], server.send_mouse(target="court"))
        assert unaimed["code"] == "needs_call", unaimed
        _ok(server.resume())
        _ok(server.log_wait(pattern="BRICKS ready", channel="guest", seconds=30))
        _ok(server.stop())
        at = _ok(server.status())["last_stop"]["stop_seq"]
        found = _ok(server.screen_map_find())
        assert (found["matched"], found["screen"], found["layer"]) == (True, "play", "file")
        assert found["controls"][0]["centre"] == COURT_CENTRE
        added = _ok(server.screen_map_write("add", screen="header", match=[[0, 0, 52, 8]]))
        assert added["shadows_file"] is False
        saved = _ok(server.screen_map_write("save", dest=str(tmp_path / "bricks-screen-map.json")))
        assert saved["screens"] == 2 and saved["promoted"] == ["header"]
        _ok(server.resume())
        _ok(server.send_keys(keys=["m"], expect="MOUSE ON$", seconds=10))
        clicked = _ok(server.send_mouse(target="court", expect="MOUSE$", seconds=10))
        assert (clicked["target"], clicked["screen"]) == ("court", "play")
        assert clicked["identified_at_stop"] == at
        pointer = clicked["pointer"]["screen"]
        assert [pointer["x"], pointer["y"]] == COURT_CENTRE
        assert clicked.get("arrived", clicked.get("driver_arrived")) is True
        assert clicked["verify"]["seen"] is True, clicked["verify"]
        # Negative: the control match first, then one pixel of the header `S` flipped
        # (mode 13h: A000:0000, a byte a pixel, 320 a row).
        _ok(server.stop())
        assert _ok(server.screen_map_find())["screen"] == "play"
        # Flip between white and black: a flipped index is not always a changed colour.
        pixel = int(_ok(server.read_memory(ref="A000:0141", length=1))["hex"][:2], 16)
        _ok(server.write(ref="A000:0141", data_hex="00" if pixel == 0x0F else "0f"))
        changed = _ok(server.screen_map_find())
        assert changed["matched"] is False and changed["screens_tried"] == 2, changed
    finally:
        server.close()


def _anchored(tmp_path: Path, mode: str) -> str:
    """Bricks' map with its play screen anchored at `main_loop`, after which it is whole."""
    doc = json.loads(MAP.read_text())
    doc["mode"] = mode
    doc["screens"][0]["anchor"] = "main_loop"
    folder = tmp_path / mode
    folder.mkdir()
    path = folder / "bricks-screen-map.json"
    path.write_text(json.dumps(doc))
    return str(path)


def test_the_symbols_start_holds_are_placed_and_a_run_reaches_a_screen_by_name(
        tmp_path: Path) -> None:
    started = _ok(server.start(conf=str(BRICKS / "bricks.conf"), cwd=str(BRICKS),
                               session_seconds=300, break_on_int3=True,
                               logfile=str(tmp_path / "bricks-e9.log"),
                               symbols=str(BRICKS / "bricks.sym")))
    assert started["symbols"]["held"].endswith("bricks.sym")
    try:
        ready = _ok(server.resume(seconds=30))
        placed = ready["symbols_placed"]
        assert placed["placed"] is True, placed
        assert placed["load_segment"] == str(ready["pc"]).split(":")[0], (placed, ready["pc"])
        assert _ok(server.symbols_find(name="MAIN_LOOP"))["symbols"][0]["name"] == "main_loop"
        _ok(server.screen_map_write("load", path=_anchored(tmp_path, "verified")))
        judged = _ok(server.run_to(screen="play", control="move_ball"))
        assert judged["screen"] == {"screen": "play", "layer": "file", "mode": "verified",
                                    "judged": True}, judged
        _ok(server.screen_map_write("load", path=_anchored(tmp_path, "consolidated")))
        shown = _ok(server.run_to(screen="play", control="move_ball"))
        assert shown["screen"]["judged"] is False and shown["verdict"] == "TARGET"
        # Negative: one pixel of the header `S` flipped, and the verified screen is stale.
        (tmp_path / "again").mkdir()
        _ok(server.screen_map_write("load", path=_anchored(tmp_path / "again", "verified")))
        pixel = int(_ok(server.read_memory(ref="A000:0141", length=1))["hex"][:2], 16)
        _ok(server.write(ref="A000:0141", data_hex="00" if pixel == 0x0F else "0f"))
        stale = cast(dict[str, Any], server.run_to(screen="play", control="move_ball"))
        assert stale["status"] == "INVALID" and stale["code"] == "stale_map", stale
    finally:
        server.close()
