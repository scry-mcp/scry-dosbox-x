"""Watches read as the SHAPE the value has: arrays, strings, structs, and a symbol's own type.

The grammar (`value_format`) names the shape, a sized format
implies its width, and a symbol typed by the `types` file given to `symbols_load` reads as
that type with no format named at all.
"""

from __future__ import annotations

from pathlib import Path

from dosbox_x_server_support import _names, clean_session, install  # noqa: F401

from scry_dosbox_x import server
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def test_a_sized_format_needs_no_width_and_a_typed_symbol_needs_no_format(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_pos", 0x100, kind="D"),
                                     dsym.Symbol("_name", 0x200, kind="D"),
                                     dsym.Symbol("_rate", 0x400, kind="D")])
    dstate.STATE.symbol_types.update({"_POS": "{x:i16,y:i16}", "_NAME": "char[8]",
                                      "_RATE": "u32"})
    out = server.watch_add(ref="_pos", mode="show")
    assert out["status"] == "ok" and out["mode"] == "show", out
    decl = next(d for d in dstate.STATE.store.declarations() if d.ref == "_pos")  # type: ignore[union-attr]
    assert decl.fmt == "{x:i16,y:i16}" and decl.width == 4
    out = server.watch_add(ref="00A7:0300", mode="show", fmt="u16[4]")
    assert out["status"] == "ok"
    decl = next(d for d in dstate.STATE.store.declarations() if d.ref == "00A7:0300")  # type: ignore[union-attr]
    assert decl.fmt == "u16[4]" and decl.width == 8
    out = server.watch_add(ref="_rate", mode="show")
    assert out["status"] == "ok", out
    assert out["fmt"] == "u32" and out["length"] == 4, "the reply names what was declared"
    decl = next(d for d in dstate.STATE.store.declarations() if d.ref == "_rate")  # type: ignore[union-attr]
    assert decl.fmt == "u32" and decl.width == 4, "a typed scalar with no width: one value"
    out = server.watch_add(ref="00A7:0500", mode="show", fmt="i16")
    assert out["status"] == "ok", out
    decl = next(d for d in dstate.STATE.store.declarations() if d.ref == "00A7:0500")  # type: ignore[union-attr]
    assert decl.width == 2
    bad = server.watch_add(ref="00A7:0400", mode="show", fmt="u16[4]", length=6)
    assert bad["status"] == "INVALID" and "does not agree" in bad["message"]
    bad = server.watch_add(ref="00A7:0400", mode="show")
    assert bad["status"] == "INVALID" and "needs a length" in bad["message"]
    assert fake.rows == [], "show watches arm nothing"


def test_symbols_load_takes_a_types_file_and_refuses_a_name_the_table_lacks(
        tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n0016e000 D _hero\n", encoding="utf-8")
    types = tmp_path / "types.txt"
    types.write_text("# shapes\n_hero: {x:i16,y:i16,hp:u8}\n", encoding="utf-8")
    _names(tmp_path)
    got = server.symbols_load(path=str(nm), base="400000", types=str(types))
    assert got["status"] == "ok", got
    assert dstate.STATE.symbol_types == {"_HERO": "{x:i16,y:i16,hp:u8}"}
    assert got["symbols_typed"] == 1, "the load reply counts the types it installed"
    types.write_text("_villain: u8\n", encoding="utf-8")
    got = server.symbols_load(path=str(nm), base="400000", types=str(types))
    assert got["status"] == "INVALID" and "_VILLAIN" in got["message"]
    types.write_text("_hero: u64\n", encoding="utf-8")
    got = server.symbols_load(path=str(nm), base="400000", types=str(types))
    assert got["status"] == "INVALID" and "types.txt:1" in got["message"]
    dstate.STATE.forget_symbols()
    assert dstate.STATE.symbol_types == {}, "dropped with the table"


def test_a_types_file_that_cannot_be_read_is_refused_naming_it(tmp_path: Path) -> None:
    import pytest

    from scry_dosbox_x import placement
    from scry_dosbox_x import session as ds
    with pytest.raises(ds.Invalid, match="no types file at"):
        placement.read_types(str(tmp_path / "missing.txt"))
