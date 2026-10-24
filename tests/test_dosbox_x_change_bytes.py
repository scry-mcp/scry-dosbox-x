"""A change watch over several bytes: the debugger's memory breakpoint compares ONE byte
(`CBreakpoint::CheckBreakpoint` reads a `uint8_t` at the row's address), so a watch of `length`
bytes arms one row per byte, is `armed` only while the debugger holds every one, moves every one
when its pointer moves, and is cleared whole."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from test_dosbox_x_server import _names, clean_session  # noqa: F401

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

DS, HERE = 0x00AF, 0x6024


def entries(fake: Any) -> list[str]:
    return sorted(r["entry"] for r in fake.rows)


def test_a_change_watch_arms_a_row_for_every_byte_it_covers(tmp_path: Path) -> None:
    fake = _names(tmp_path, ds_="00AF")
    got = cast(dict[str, Any], server.watch_add(ref="00AF:6024", mode="change", length=4))
    want = [f"BPPM 00AF:{HERE + i:08X} (00)" for i in range(4)]
    assert got["armed"] is True and entries(fake) == want, (got, fake.rows)
    assert got["entries"] == [f"BPPM 00AF:{HERE + i:08X}" for i in range(4)], got
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "armed", w
    fake.rows[:] = [r for r in fake.rows if not r["entry"].startswith("BPPM 00AF:00006026")]
    fake._relist(fake.rows)
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "gone", "a watch the debugger holds three bytes of four of is not armed"


def test_a_change_watch_is_cleared_whole(tmp_path: Path) -> None:
    fake = _names(tmp_path, ds_="00AF")
    server.watch_add(ref="00AF:6024", mode="change", length=2)
    gone = cast(dict[str, Any], server.watch_clear(ref="00AF:6024"))
    assert fake.rows == [] and len(gone["disarmed"]) == 2, (gone, fake.rows)


def test_a_moved_pointer_change_watch_moves_every_byte(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_g_engine", 0x1000, kind="D")], ds_="00AF")
    dstate.STATE.symbol_types["_G_ENGINE"] = "ptr32{a:u16}"
    fake.mem[(DS, 0x1000)] = (0x2000).to_bytes(4, "little")
    server.watch_add(ref="_g_engine->a", mode="change")
    assert entries(fake) == ["BPPM 00AF:00002000 (00)", "BPPM 00AF:00002001 (00)"], fake.rows
    fake.mem[(DS, 0x1000)] = (0x3000).to_bytes(4, "little")
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "armed" and "why" not in w.get("moved", {}), w
    assert entries(fake) == ["BPPM 00AF:00003000 (00)", "BPPM 00AF:00003001 (00)"], fake.rows


def test_a_change_watch_is_at_most_its_ceiling_of_bytes() -> None:
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "change",
                                   "length": checks.CHANGE_WATCH_MAX})
    with pytest.raises(ds.Invalid) as wide:
        checks.preflight("watch_add", {"ref": "0000:0000", "mode": "change",
                                       "length": checks.CHANGE_WATCH_MAX + 1})
    assert f"at most {checks.CHANGE_WATCH_MAX} bytes" in str(wide.value), wide.value
