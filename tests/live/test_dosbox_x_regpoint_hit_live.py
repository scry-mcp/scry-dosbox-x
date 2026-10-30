"""A registerpoint's hit says it stays armed, and it does: the next advance stops again."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from scry_core import regpoint
from test_dosbox_x_entry_routes import REAL_PROGRAM, reach_realmode

from scry_dosbox_x import server

pytestmark = pytest.mark.live


@REAL_PROGRAM
def test_a_registerpoint_hit_carries_the_still_armed_note_and_the_next_advance_stops_again(
        tmp_path: Path) -> None:
    _load_seg, cs, _eip = reach_realmode(tmp_path)
    added = cast(dict[str, Any], server.regpoint_add(condition=f"CS=={cs:X}"))
    assert added["status"] == "ok" and added["armed"] is True, added
    first = cast(dict[str, Any], server.resume(seconds=2))
    hit = first.get("regpoint_hit")
    assert first["status"] == "ok" and hit is not None, first
    assert hit["note"] == regpoint.STILL_ARMED and hit["condition"] == hit["ref"], hit
    again = cast(dict[str, Any], server.resume(seconds=2))
    assert again["status"] == "ok" and again["verdict"] == "OTHER_STOP", again
    assert again["stop_seq"] > first["stop_seq"], (first["stop_seq"], again["stop_seq"])
