"""What both servers answer alike, on the real build: a repeated name, a tie, a status with no
session."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import REAL_PROGRAM, reach_realmode

from scry_dosbox_x import server

pytestmark = pytest.mark.live


@REAL_PROGRAM
def test_a_repeated_name_is_refused_with_its_addresses_and_a_tie_goes_to_the_first_row(
        tmp_path: Path) -> None:
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    table = tmp_path / "parity.sym"
    table.write_text("00000010 T dup\n00000020 T dup\n00000030 T first\n00000030 T second\n",
                     encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(table), base=f"{load_seg:04X}"))
    assert loaded["status"] == "ok", loaded
    twice = cast(dict[str, Any], server.read_memory(ref="dup", length=2))
    assert twice["status"] == "INVALID" and "(0x10, 0x20)" in twice["message"], twice
    found = cast(dict[str, Any], server.symbols_find(name="dup"))
    assert found["status"] == "ok" and len(found["symbols"]) == 2, found
    where = cast(dict[str, Any], server.symbols_find(name="second"))["symbols"][0]["addr"]
    at = cast(dict[str, Any], server.symbols_find(linear=where))
    assert at["name"] == "first", at


@REAL_PROGRAM
def test_status_after_close_names_no_overlay_and_still_answers_the_stop_and_the_queue(
        tmp_path: Path) -> None:
    reach_realmode(tmp_path)
    assert cast(dict[str, Any], server.close())["status"] == "ok"
    said = cast(dict[str, Any], server.status())
    assert said["session"]["alive"] is False and "presence" not in said, said
    assert {"last_stop", "pending"} <= set(said), said
