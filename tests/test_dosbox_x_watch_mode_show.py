"""`read` is refused naming `show`; legacy stores load as `show`; widths treat `show` as `read`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scry_dosbox_x import checks, grammar, server
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import session as ds

CONF = "guest-a.conf"
# Includes a change row, so a migration that rewrote every mode shows.
LEGACY_ROWS: list[dict[str, object]] = [
    {"kind": "watch", "by": "symbol", "ref": "_g_name", "width": 8, "fmt": "char[8]",
     "watch_mode": "read", "created_at": "t", "origin": "s0", "fingerprint": "fp"},
    {"kind": "watch", "by": "symbol", "ref": "_g_pos", "width": 4, "fmt": "i32",
     "watch_mode": "read", "created_at": "t", "origin": "s0", "fingerprint": "fp"},
    {"kind": "watch", "by": "symbol", "ref": "_g_rate", "width": 4, "fmt": "u32",
     "watch_mode": "read"},
    {"kind": "watch", "by": "symbol", "ref": "_g_cue", "width": 1, "fmt": "u8",
     "watch_mode": "read"},
    {"kind": "watch", "by": "address", "ref": "0000:0020", "width": 2, "fmt": "u16",
     "watch_mode": "change", "created_at": "t", "origin": "s0", "fingerprint": "fp"},
]


def test_check_watch_mode_refuses_read_naming_show_and_takes_show() -> None:
    with pytest.raises(dec.DeclarationError, match=r"got 'read'") as refused:
        dec.check_watch_mode("read")
    assert "'show'" in str(refused.value), refused.value
    dec.check_watch_mode("show")


def test_watch_add_refuses_read_before_any_machine_is_asked() -> None:
    reply = server.watch_add(ref="0000:0020", mode="read", length=2)
    assert reply["code"] == "bad_argument", reply
    assert "'show'" in reply["message"] and "'read'" in reply["message"], reply


def test_a_store_written_with_read_rows_loads_them_as_show_and_persists_show(
        tmp_path: Path) -> None:
    path = tmp_path / "declarations.json"
    path.write_text(json.dumps({CONF: LEGACY_ROWS}))
    store = dec.DeclarationStore(CONF, path)
    modes = [d.watch_mode for d in store.declarations()]
    assert modes == ["show"] * 4 + ["change"], modes
    assert json.loads(path.read_text())[CONF] == LEGACY_ROWS
    store.add(dec.Declaration("breakpoint", "address", "0000:0400"))
    stored = [r.get("watch_mode") for r in json.loads(path.read_text())[CONF]]
    assert stored == ["show"] * 4 + ["change", None], stored


def test_a_show_watch_is_bounded_by_the_data_view_and_a_change_watch_by_its_rows() -> None:
    wide = grammar.READ_BYTES_MAX + 1
    with pytest.raises(ds.Invalid, match=f"{wide} is a region"):
        checks.watch_width("show", wide)
    checks.watch_width("show", grammar.READ_BYTES_MAX)
    checks.watch_width("change", checks.CHANGE_WATCH_MAX)
    with pytest.raises(ds.Invalid, match="one debugger row per byte"):
        checks.watch_width("change", checks.CHANGE_WATCH_MAX + 1)

