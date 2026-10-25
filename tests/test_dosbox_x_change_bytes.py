"""A change watch over several bytes: the debugger's memory breakpoint compares ONE byte
(`CBreakpoint::CheckBreakpoint` reads a `uint8_t` at the row's address), so a watch of `length`
bytes arms one row per byte, is `armed` only while the debugger holds every one, moves every one
when its pointer moves, and is cleared whole."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _names, clean_session  # noqa: F401

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
    gone = cast(dict[str, Any], server.declaration_clear("watch", ref="00AF:6024"))
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


def test_a_change_watch_whose_bytes_cross_the_offset_ceiling_arms_none_of_them(
        tmp_path: Path) -> None:
    """Its last byte would be at an offset the mode cannot address: refused before the first row
    goes in, so no half of it is left armed under a reply that says it is not."""
    fake = _names(tmp_path, mode="Real", cs="0000", ds_="0000")
    got = cast(dict[str, Any], server.watch_add(ref="0000:FFFF", mode="change", length=2))
    assert got["armed"] is False and fake.rows == [], (got, fake.rows)
    assert "FFFF" in str(got.get("why", "")), got
    assert dstate.STATE.armed.get(("watch", "0000:FFFF")) in (None, []), dstate.STATE.armed


def _counting(rows: list[dict[str, str]]) -> Any:
    from types import SimpleNamespace
    calls: dict[str, int] = {"where": 0, "breakpoints": 0}
    sent: list[str] = []

    def where() -> dict[str, str]:
        calls["where"] += 1
        return {"cs": "0000", "eip": "0", "mode": "Real"}

    def breakpoints() -> list[dict[str, str]]:
        calls["breakpoints"] += 1
        return [dict(r) for r in rows]

    def command(text: str, **_: Any) -> str:
        sent.append(text)
        if text.startswith("BPM "):
            seg, off = text.split()[1].split(":")
            rows.insert(0, {"index": "", "entry": f"BPMEM {seg}:{off} (00)"})
        elif text.startswith("BPDEL "):
            del rows[int(text.split()[1])]
        rows[:] = [{**r, "index": f"{i:02d}"} for i, r in enumerate(rows)]
        return ""
    return SimpleNamespace(where=where, breakpoints=breakpoints, command=command, calls=calls,
                           sent=sent, rows=rows, altered=False)


def test_a_watch_of_several_bytes_costs_its_commands_and_one_read_back() -> None:
    s = _counting([])
    got = ds.Session.watch_places(s, [(0, 0x500 + i) for i in range(4)])
    assert [g["armed"] for g in got] == [f"BPMEM 0000:{0x500 + i:04X}" for i in range(4)], got
    assert s.calls == {"where": 1, "breakpoints": 1} and len(s.sent) == 4, (s.calls, s.sent)


def test_rows_are_deleted_highest_index_first_from_one_list() -> None:
    s = _counting([])
    ds.Session.watch_places(s, [(0, 0x500 + i) for i in range(3)])
    s.calls.update(breakpoints=0)
    gone, kept = arming.delete_watch_rows(s, [(0, 0x500), (0, 0x502)])
    assert s.sent[-2:] == ["BPDEL 02", "BPDEL 00"] and kept == [], s.sent
    assert sorted(gone) == ["BPMEM 0000:0500 (00)", "BPMEM 0000:0502 (00)"], gone
    assert [r["entry"] for r in s.rows] == ["BPMEM 0000:0501 (00)"] and s.calls["breakpoints"] == 2
