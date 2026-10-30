"""A number the server types is read as a number, whatever the loaded symbols are named."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import REAL_PROGRAM, reach_realmode

from scry_dosbox_x import server

pytestmark = pytest.mark.live

#: A name made only of hex digits, so a bare `ABCD` typed to the debugger is this symbol.
SHADOW = "ABCD"


@REAL_PROGRAM
def test_a_symbol_named_like_an_offset_does_not_shadow_the_offset_read(tmp_path: Path) -> None:
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    window = cast(dict[str, Any], server.read_memory(ref=f"{load_seg:04X}:ABC0", length=32))
    assert window["status"] == "ok", window
    table = tmp_path / "shadow.sym"
    table.write_text(f"00000010 T {SHADOW}\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(table), base=f"{load_seg:04X}"))
    assert loaded["status"] == "ok", loaded
    at_symbol = cast(dict[str, Any], server.read_memory(ref=f"{load_seg:04X}:0010", length=4))
    wanted = window["hex"][2 * 0xD:2 * 0xD + 8]
    assert at_symbol["hex"] != wanted, "the control: the symbol's bytes differ from the offset's"
    got = cast(dict[str, Any], server.read_memory(ref=f"{load_seg:04X}:{SHADOW}", length=4))
    assert got["status"] == "ok", got
    assert got["hex"] == wanted, (got, window)


@REAL_PROGRAM
def test_a_segment_typed_with_a_leading_zero_is_taken_by_the_debugger(tmp_path: Path) -> None:
    reach_realmode(tmp_path)
    got = cast(dict[str, Any], server.read_memory(ref="B800:0000", length=4))
    assert got["status"] == "ok" and len(got["hex"]) == 8, got
