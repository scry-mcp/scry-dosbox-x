"""A watch at a raw SEG:OFF across the cpu's two modes.

A SEG:OFF names one byte in real mode and another in protected mode, where its segment is a
selector, and the debugger's memory breakpoint computes its address in the mode of the moment
it compares. So a raw watch keeps the mode of the stop that placed it, as a raw breakpoint and a
raw comment do, and is read and armed only at a stop of that mode; at a stop of the other it is
`unarmable`, saying the mode it waits for, never a value read off the other byte."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _start_over_a_store, clean_session  # noqa: F401
from test_dosbox_x_comments import _ParkedInRealMode, ok

from scry_dosbox_x import arming, code, grammar, server
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import state as dstate

AT = "0000:0600"


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    booted.mem[(0, 0x600)] = bytes.fromhex("0000c07f")
    return booted


def _stored(ref: str) -> dec.Declaration:
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    return next(d for d in store.declarations() if d.kind == "watch" and d.ref == ref)


def _listed(ref: str) -> dict[str, Any]:
    return next(w for w in ok(server.declaration_list("watch"))["watches"] if w["ref"] == ref)


def _at_stop(booted: Any, ref: str) -> dict[str, Any]:
    session = cast(Any, dstate.STATE.session)
    return next(w for w in arming.evaluate_watches(session, machine=(booted.mode, {}))
                if w["ref"] == ref)


def test_a_raw_watch_placed_in_real_mode_waits_at_a_protected_mode_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    booted = _start(tmp_path, monkeypatch)
    ok(server.watch_add(ref=AT, mode="show", fmt="f32"))
    assert _stored(AT).cpu_mode == "real"
    booted.mode = "Pr32"
    for item in (_listed(AT), _at_stop(booted, AT)):
        assert item["state"] == "unarmable", item
        assert "placed at a real-mode stop" in item["why"], item
        assert "value" not in item and "bytes" not in item, item
    booted.mode = grammar.REAL_MODE
    back = _at_stop(booted, AT)
    assert (back["state"], back["value"]) == ("evaluated", "nan"), back


def test_a_change_watch_declared_again_in_the_other_mode_is_armed_again_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its rows were made in the real-mode stop's terms, so at a protected-mode stop they are
    the watch's and not judged held; declared again there, they are deleted and the watch is
    armed in this mode's."""
    booted = _start(tmp_path, monkeypatch)
    assert ok(server.watch_add(ref=AT, mode="change", length=2))["entries"] == [
        "BPMEM 0000:0600", "BPMEM 0000:0601"]
    booted.mode = "Pr32"
    listed = ok(server.declaration_list("watch"))
    assert listed["watches"][0]["state"] == "unarmable", listed
    assert "foreign" not in listed, listed
    again = ok(server.watch_add(ref=AT, mode="change", length=2))
    assert again["entries"] == ["BPPM 0000:00000600", "BPPM 0000:00000601"], again
    held = [r["entry"] for r in booted.rows]
    assert not any(e.startswith("BPMEM") for e in held), held
    assert _stored(AT).cpu_mode == "protected"


def test_a_raw_watch_declared_while_the_guest_ran_is_placed_by_the_first_stop_that_reads_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    booted = _start(tmp_path, monkeypatch)
    booted.running = True
    ok(server.watch_add(ref=AT, mode="show", fmt="f32"))
    assert _stored(AT).cpu_mode is None
    booted.running = False
    assert _at_stop(booted, AT)["state"] == "evaluated"
    assert _stored(AT).cpu_mode == "real"


def test_a_change_watch_queued_while_the_guest_ran_is_placed_by_the_stop_that_arms_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    booted = _start(tmp_path, monkeypatch)
    booted.running = True
    assert ok(server.watch_add(ref=AT, mode="change", length=2))["state"] == "pending"
    booted.running = False
    applied = arming.apply_pending(cast(Any, dstate.STATE.session))
    assert applied["armed"] == [AT], applied
    assert _stored(AT).cpu_mode == "real"


def test_a_raw_watchs_mode_round_trips_and_a_named_watch_carries_none() -> None:
    held = dec.Declaration("watch", "address", AT, width=4, fmt="f32", watch_mode="show",
                           cpu_mode="real")
    assert dec.Declaration.from_dict(held.to_dict()).cpu_mode == "real"
    with pytest.raises(dec.DeclarationError, match="cpu mode"):
        dec.Declaration("watch", "symbol", "_x", width=4, fmt="u32", watch_mode="show",
                        cpu_mode="real")


def test_a_change_watch_moved_to_the_other_mode_keeps_one_record_per_byte_and_clears_alone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The record names the rows of the mode it is armed in only: a record of the other mode's
    rows too would send a clear's delete twice at one index, which takes the row below it."""
    booted = _start(tmp_path, monkeypatch)
    ok(server.breakpoint_at(ref="0814:0100"))
    ok(server.watch_add(ref=AT, mode="change", length=2))
    booted.mode = "Pr32"
    ok(server.watch_add(ref=AT, mode="change", length=2))
    assert len(dstate.STATE.armed[("watch", AT)]) == 2, dstate.STATE.armed
    ok(server.declaration_clear("watch", ref=AT))
    assert [r["entry"] for r in booted.rows] == ["BP 0814:0100"], booted.rows


def test_a_moved_change_watch_whose_old_rows_stay_is_not_called_armed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    booted = _start(tmp_path, monkeypatch)
    ok(server.watch_add(ref=AT, mode="change", length=2))
    booted.mode = "Pr32"
    monkeypatch.setattr(arming, "delete_watch_rows",
                        lambda _s, places: ([], list(places)))
    again = ok(server.watch_add(ref=AT, mode="change", length=2))
    assert (again["armed"], again["state"]) == (False, "unarmable"), again


def test_a_stop_judges_a_raw_watchs_mode_off_its_own_survey(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stop's one survey (`machine`) says the mode; a watch that waits costs no second one."""
    booted = _start(tmp_path, monkeypatch)
    ok(server.watch_add(ref=AT, mode="show", fmt="f32"))
    booted.mode = "Pr32"

    def surveyed(_session: Any) -> Any:
        raise AssertionError("a second survey of this stop")
    monkeypatch.setattr(code, "segments_at_stop", surveyed)
    item = _at_stop(booted, AT)
    assert item["state"] == "unarmable" and "to place it in this mode" in item["why"], item


def test_placing_a_raw_watch_writes_its_mode_and_nothing_else(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A watch is judged by no build, so the stop that places it writes no stamp and takes no
    other session's row for its own."""
    booted = _start(tmp_path, monkeypatch)
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.add(dec.Declaration("watch", "address", AT, width=4, fmt="f32", watch_mode="show",
                              created_at="t0", origin="another session", fingerprint="other"))
    assert _at_stop(booted, AT)["state"] == "evaluated"
    placed = _stored(AT)
    assert (placed.cpu_mode, placed.fingerprint, placed.origin) == (
        "real", "other", "another session"), placed
