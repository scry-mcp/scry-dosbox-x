"""What a session learned goes into a store only when the call approves it, and reads back."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

import live_private  # isort: skip -- first: a pooled job's working copies
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

from scry_dosbox_x import server

pytestmark = pytest.mark.live

BRICKS = live_private.bricks_dir()


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r.get("summary")
    return r


def test_a_map_learned_in_a_session_is_promoted_and_read_back(tmp_path: Path) -> None:
    game = tmp_path / "game"
    shutil.copytree(BRICKS, game / "bricks")
    started = _ok(server.start(conf=str(game / "bricks" / "bricks.conf"),
                               cwd=str(game / "bricks"), session_seconds=300,
                               logfile=str(tmp_path / "bricks-e9.log")))
    try:
        assert started["kept"].startswith("1 saved for `promote`"), started
        _ok(server.resume())
        _ok(server.log_wait(pattern="BRICKS ready", channel="guest", seconds=30))
        _ok(server.stop())
        added = _ok(server.screen_map_write("add", screen="header", match=[[0, 0, 52, 8]]))
        assert added["kept"].startswith("2 saved for `promote`"), added
        review = _ok(server.promote(dry_run=True, root=str(game)))
        entries = [c["entry"] for c in review["candidates"]]
        assert entries == ["maps/bricks", "start/bricks"], review
        assert not (game / ".scry").exists(), "a review wrote the store"
        assert review["would_create"] == [".scry/", ".scry/about.json", ".scry/README.md"]
        written = _ok(server.promote(entries=entries, root=str(game)))
        assert sorted(w["file"] for w in written["written"]) == [
            ".scry/maps/bricks-screen-map.json", ".scry/start/bricks.json"], written
        assert written["draft"] == [], written
        assert written["created"] == review["would_create"], written
        read = _ok(server.screen_map_write(
            "load", path=str(game / ".scry" / "maps" / "bricks-screen-map.json")))
        assert (read["application"], read["screens"]) == ("bricks", 1), read
        recipe = json.loads((game / ".scry" / "start" / "bricks.json").read_text())
        assert recipe["conf"].startswith("${root}/") and recipe["cwd"].startswith("${root}"), (
            recipe)
    finally:
        closed = cast(dict[str, Any], server.close())
    assert "draft" not in closed, closed
