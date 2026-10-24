"""A watch reached through a POINTER: `[base]+0x28` or `base->field`, resolved when armed
and re-resolved at every stop, because the pointer can move. The pointer's width comes
from the base's type (`ptr32{...}` in `types`)
or from the cpu mode (four bytes protected, two real), read as a NEAR pointer in the
base's own segment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from scry_core import value_format as vf
from test_dosbox_x_server import NamesFake, _names, clean_session  # noqa: F401

import dosbox_arming as arming
import dosbox_declarations as dec
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

DS = 0xAF
ENGINE = 0x1000            # the global pointer `_g_engine`, an offset in DS
HEAP = 0x00200000          # where it points now
HEAP2 = 0x00300000         # where it points after a realloc


def _pointing(tmp_path: Path) -> NamesFake:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_g_engine", ENGINE, kind="D"),
                                     dsym.Symbol("_g_bufsamp", 0x2000, kind="D")])
    dstate.STATE.symbol_types.update({"_G_ENGINE": "ptr32{rate:u32,sync_delta:i16,flags:u8}"})
    fake.mem[(DS, ENGINE)] = HEAP.to_bytes(4, "little")
    fake.mem[(DS, HEAP + 4)] = (-7).to_bytes(2, "little", signed=True)
    fake.mem[(DS, HEAP2 + 4)] = (9).to_bytes(2, "little", signed=True)
    return fake


def test_the_pointer_grammar_is_the_siblings() -> None:
    assert vf.parse_pointer("[_g_engine]+0x28") == vf.PointerRef("_g_engine", 0x28, None)
    assert vf.parse_pointer("[00AF:1000]-4") == vf.PointerRef("00AF:1000", -4, None)
    assert vf.parse_pointer("_g_engine->sync_delta") == vf.PointerRef("_g_engine", 0,
                                                                        "sync_delta")
    assert vf.parse_pointer("00AF:1000") is None and vf.parse_pointer("_g_engine") is None
    assert placement.decide_by("[_g_engine]+0x28") == "pointer"
    assert placement.decide_by("[00AF:1000]") == "pointer"
    assert placement.decide_by("00AF:1000") == "address"
    with pytest.raises(dec.DeclarationError, match="pointer ref"):
        dec.Declaration("watch", "pointer", "[]", width=2, fmt="u16", watch_mode="show")
    with pytest.raises(dec.DeclarationError, match="breakpoint"):
        dec.Declaration("breakpoint", "pointer", "[_g_engine]")


def test_a_pointer_watch_is_resolved_when_armed_and_the_reply_says_through_what(
        tmp_path: Path) -> None:
    _pointing(tmp_path)
    out = server.watch_add(ref="[_g_engine]+0x4", mode="show", length=2, fmt="i16")
    assert out["status"] == "ok" and out["by"] == "pointer" and out["state"] == "evaluated", out
    assert out["pointer"] == {"at": "00AF:00001000", "length": 4, "value": "200000", "offset": 4,
                              "target": f"00AF:{HEAP + 4:08X}"}
    out = server.watch_add(ref="_g_engine->sync_delta", mode="show")
    assert out["status"] == "ok", out
    assert out["fmt"] == "i16" and out["length"] == 2 and out["pointer"]["field"] == "sync_delta"
    listed = {w["ref"]: w for w in server.watch_list()["watches"]}
    assert listed["_g_engine->sync_delta"]["pointer"]["target"] == f"00AF:{HEAP + 4:08X}"
    # An explicit `SEG:OFF` as the base, and a real-mode machine reads a two-byte pointer.
    out = server.watch_add(ref="[00AF:1000]", mode="show", length=4)
    assert out["status"] == "ok" and out["pointer"]["target"] == f"00AF:{HEAP:08X}", out


def test_a_pointer_watch_is_re_resolved_at_every_stop_and_a_change_watch_follows_it(
        tmp_path: Path) -> None:
    fake = _pointing(tmp_path)
    out = server.watch_add(ref="_g_engine->sync_delta", mode="change")
    assert out["status"] == "ok" and out["state"] == "armed", out
    assert fake.rows[-1]["entry"].startswith(f"BPPM 00AF:{HEAP + 4:08X}")
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "armed" and "moved" not in w
    fake.mem[(DS, ENGINE)] = HEAP2.to_bytes(4, "little")       # the pointer moved
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["moved"] == {"from": f"00AF:{HEAP + 4:08X}", "to": f"00AF:{HEAP2 + 4:08X}"}, w
    assert w["pointer"]["value"] == "300000" and w["state"] == "armed"
    assert [r["entry"] for r in fake.rows] == [f"BPPM 00AF:{HEAP2 + 4:08X} (00)"], fake.rows
    rows = dstate.STATE.armed[("watch", "_g_engine->sync_delta")]
    assert [(r["seg"], r["off"]) for r in rows] == [(DS, HEAP2 + 4)]
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert "moved" not in w
    # A SHOW watch through the pointer reads where it points NOW.
    server.watch_clear(ref="_g_engine->sync_delta")
    server.watch_add(ref="_g_engine->sync_delta", mode="show")
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "evaluated" and w["value"] == 9, w


def test_a_base_that_is_not_a_global_is_refused_naming_the_stack(tmp_path: Path) -> None:
    _pointing(tmp_path)
    bad = server.watch_add(ref="[ur_count]+0x0", mode="show", length=2)
    assert bad["status"] == "INVALID" and "stack local" in bad["message"], bad
    bad = server.watch_add(ref="ur_count->x", mode="show")
    assert bad["status"] == "INVALID" and "stack local" in bad["message"], bad
    bad = server.watch_add(ref="_g_bufsamp->x", mode="show")
    assert bad["status"] == "INVALID" and "ptr32" in bad["message"], bad
    bad = server.watch_add(ref="_g_engine->missing", mode="show")
    assert bad["status"] == "INVALID" and "no field" in bad["message"], bad


def test_a_null_pointer_is_a_state_at_the_stop_never_a_watch_at_zero(tmp_path: Path) -> None:
    fake = _pointing(tmp_path)
    fake.mem[(DS, ENGINE)] = bytes(4)
    out = server.watch_add(ref="_g_engine->sync_delta", mode="change")
    assert out["status"] == "ok" and out["state"] == "null_pointer" and not fake.rows, out
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "null_pointer"
    fake.mem[(DS, ENGINE)] = HEAP.to_bytes(4, "little")
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "armed" and w["moved"] == {"from": "null", "to": f"00AF:{HEAP + 4:08X}"}, w
    assert fake.rows[-1]["entry"].startswith(f"BPPM 00AF:{HEAP + 4:08X}")


def test_a_pointer_that_cannot_be_placed_or_read_is_a_state_with_its_reason(
        tmp_path: Path) -> None:
    """Every way the chase can fail is a STATE the reply names, never a traceback and never
    a watch at a guessed place: a base spelt as an address the parser refuses, a base named
    twice in this build, a pointer plus offset past what the mode can address, and a machine
    that cannot be read."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_g_engine", ENGINE, kind="D"),
                                     dsym.Symbol("_twice", 0x10, kind="D"),
                                     dsym.Symbol("_twice", 0x20, kind="D")])
    fake.mem[(DS, ENGINE)] = (0xFFFFFFF0).to_bytes(4, "little")
    bad = server.watch_add(ref="[00AF:ZZ]", mode="show", length=2)
    assert bad["status"] == "ok" and bad["state"] == "unarmable", bad
    bad = server.watch_add(ref="[_twice]", mode="show", length=2)
    assert bad["status"] == "INVALID" and "2 symbols" in bad["message"], bad
    out = server.watch_add(ref="[_g_engine]+0x20", mode="show", length=2)
    assert out["state"] == "unarmable" and "outside" in out["why"], out
    fake.running = True
    by_ref = {w["ref"]: w for w in arming.evaluate_watches(fake, held=[])}  # type: ignore[arg-type]
    w = by_ref["[_g_engine]+0x20"]
    assert w["state"] == "unarmable" and "running" in w["why"], w


def test_a_move_the_debugger_refuses_keeps_the_record_and_says_why(tmp_path: Path) -> None:
    fake = _pointing(tmp_path)
    server.watch_add(ref="_g_engine->sync_delta", mode="change")
    fake.mem[(DS, ENGINE)] = HEAP2.to_bytes(4, "little")

    def refuse(**_k: object) -> dict[str, object]:
        raise ds.Invalid("not_stopped", "the machine is running; nothing was armed")

    setattr(fake, "watch", refuse)  # noqa: B010
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["moved"]["why"] and w["moved"]["to"] == f"00AF:{HEAP2 + 4:08X}", w
    rows = dstate.STATE.armed[("watch", "_g_engine->sync_delta")]
    assert [(r["seg"], r["off"]) for r in rows] == [(DS, HEAP + 4)], "the record stayed"
    # AND THE OLD ROW IS STILL HELD BY THE DEBUGGER, and the state is judged there (the
    # audit found the old row deleted before the new was tried, and the state read at the
    # refused place).
    assert [r["entry"] for r in fake.rows] == [f"BPPM 00AF:{HEAP + 4:08X} (00)"], fake.rows
    assert w["state"] == "armed", w


def test_a_bare_deref_of_a_typed_pointer_reads_as_the_struct_it_points_at(tmp_path: Path) -> None:
    fake = _pointing(tmp_path)
    fake.mem[(DS, HEAP)] = ((0xAC44).to_bytes(4, "little")
                            + (-7).to_bytes(2, "little", signed=True) + b"\x81")
    out = server.watch_add(ref="[_g_engine]", mode="show")
    assert out["status"] == "ok", out
    assert out["fmt"] == "{rate:u32,sync_delta:i16,flags:u8}" and out["length"] == 7
    (w,) = [x for x in arming.evaluate_watches(fake) if x["ref"] == "[_g_engine]"]  # type: ignore[arg-type]
    assert w["value"] == {"rate": 0xAC44, "sync_delta": -7, "flags": 0x81}
    import struct
    fake.mem[(DS, HEAP + 8)] = struct.pack("<d", 5.17)
    out = server.watch_add(ref="[_g_engine]+0x8", mode="show", fmt="f64")
    assert out["status"] == "ok" and out["length"] == 8, out
    (w,) = [x for x in arming.evaluate_watches(fake) if x["ref"] == "[_g_engine]+0x8"]  # type: ignore[arg-type]
    assert abs(w["value"] - 5.17) < 1e-9


def test_a_class_on_the_pointer_type_is_the_siblings_and_changes_nothing_here(
        tmp_path: Path) -> None:
    """`ptr32@DATA{...}` annotates the pointer type with a class, for a board whose data is
    relocated by class; a DOS machine has no classes, so the grammar parses it here and the
    watch resolves
    exactly as the un-annotated type does, with no stray key in the reply."""
    fake = _pointing(tmp_path)
    plain = server.watch_add(ref="_g_engine->sync_delta", mode="show")
    assert plain["status"] == "ok", plain
    server.watch_clear(all=True)
    dstate.STATE.symbol_types.update(
        {"_G_ENGINE": "ptr32@DATA{rate:u32,sync_delta:i16,flags:u8}"})
    typed = server.watch_add(ref="_g_engine->sync_delta", mode="show")
    assert typed["status"] == "ok", typed
    for key in ("fmt", "length", "pointer", "state", "by"):
        assert typed[key] == plain[key], (key, typed[key], plain[key])
    assert "relocated" not in typed["pointer"] and "class_from" not in typed["pointer"]
    (w,) = [x for x in arming.evaluate_watches(fake) if x["ref"] == "_g_engine->sync_delta"]  # type: ignore[arg-type]
    assert w["value"] == -7


def test_an_address_inside_a_pointer_ref_matches_in_any_spelling_too(tmp_path: Path) -> None:
    """The spelling rule one layer down: `[00AF:1000]` and `[00af:1000]` name one pointer,
    so the second is adopted and a clear in either spelling reaches it."""
    _pointing(tmp_path)
    first = server.watch_add(ref="[00AF:1000]", mode="show", length=4)
    assert first["status"] == "ok", first
    again = server.watch_add(ref="[00af:1000]", mode="show", length=4)
    assert again["already_stored"] is True and again["ref"] == "[00AF:1000]", again
    assert server.watch_clear(ref="[ 0af:1000 ]")["declarations_cleared"] == 1
    assert dec.canonical_ref("_g_engine->sync_delta", "pointer") == "_g_engine->sync_delta"


def test_a_base_typed_ptr16_is_read_two_bytes_wide_whatever_the_cpu_mode(tmp_path: Path) -> None:
    """The base's own type sets the pointer's width: a `ptr16` in a protected-mode program
    reads two bytes, and the bytes past them are no part of the address."""
    fake = _pointing(tmp_path)
    dstate.STATE.symbol_types["_G_ENGINE"] = "ptr16{rate:u32,sync_delta:i16,flags:u8}"
    fake.mem[(DS, ENGINE)] = bytes([0x34, 0x12, 0xFF, 0x00])
    out = server.watch_add(ref="[_g_engine]+0x4", mode="show", length=2, fmt="i16")
    assert out["status"] == "ok", out
    assert out["pointer"]["length"] == 2 and out["pointer"]["target"] == "00AF:00001238", out


def test_a_cached_machine_places_an_untyped_pointer_without_asking_the_machine(
        tmp_path: Path) -> None:
    fake = _pointing(tmp_path)
    asked: list[bool] = []
    where = fake.where

    def counted() -> Any:
        asked.append(True)
        return where()
    fake.where = counted  # type: ignore[method-assign]
    decl = dec.Declaration("watch", "pointer", "[00AF:1000]", width=2, fmt="u16",
                           watch_mode="show")
    res = placement.resolve_ref(decl, "DS", fake,  # type: ignore[arg-type]
                                machine=("Pr32", fake.registers()))
    assert res["state"] == "armable", res
    assert asked == [], "a cached machine was asked again"


def test_a_move_whose_old_row_the_debugger_will_not_delete_keeps_both_and_says_so(
        tmp_path: Path) -> None:
    """The new row is held when the old one's `BPDEL` is refused: the stop's reply still comes,
    the watch is judged where it now points, and the record keeps the old row too, since the
    debugger still holds it, with `why` saying it was not deleted."""
    fake = _pointing(tmp_path)
    server.watch_add(ref="_g_engine->sync_delta", mode="change")
    fake.mem[(DS, ENGINE)] = HEAP2.to_bytes(4, "little")
    sent = fake.command

    def refuse_bpdel(text: str, *a: Any, **k: Any) -> Any:
        if text.startswith("BPDEL"):
            raise ds.Invalid("unexpected_answer", "BPDEL was not acknowledged")
        return sent(text, *a, **k)

    setattr(fake, "command", refuse_bpdel)  # noqa: B010
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert w["state"] == "armed" and w["moved"]["to"] == f"00AF:{HEAP2 + 4:08X}", w
    assert "not deleted" in w["moved"]["why"], w
    rows = dstate.STATE.armed[("watch", "_g_engine->sync_delta")]
    assert sorted((r["seg"], r["off"]) for r in rows) == [(DS, HEAP + 4), (DS, HEAP2 + 4)], rows
    # THE NEXT STOP, the pointer unmoved: no second row at the new place, no move said again,
    # and once the debugger takes the delete the old row leaves the record.
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert "moved" not in w and len(fake.rows) == 2, (w, fake.rows)
    setattr(fake, "command", sent)  # noqa: B010
    (w,) = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    assert "moved" not in w and [r["entry"] for r in fake.rows] == [
        f"BPPM 00AF:{HEAP2 + 4:08X} (00)"], fake.rows
    assert [(r["seg"], r["off"]) for r in rows] == [(DS, HEAP2 + 4)], rows
