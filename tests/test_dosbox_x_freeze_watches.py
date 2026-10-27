"""Freeze watches against the channel double, which answers `FM` as the debugger does: the byte's
value now, and a list row with its offset alone (`dosbox_freezes`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from channel_double import REAL_STOP, Machine, session_over
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_state as dstate
import dosbox_x_server as server

#: `dosio.asm`'s timer counter, in the segment DOS loaded it at.
TICKS = "08BC:018F"
LINEAR = 0x8BC * 16 + 0x18F


@pytest.fixture(autouse=True)
def heavy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(binaries, "heavy_debug", lambda _b: True)


def live(tmp_path: Path) -> Machine:
    install()
    machine = Machine(regs=dict(REAL_STOP), memory={LINEAR: 0x49, LINEAR + 1: 0x00})
    dstate.STATE.session = session_over(machine, tmp_path)
    dstate.STATE.remember_stop(dstate.STATE.session,
                               {"cs": "08BC", "eip": "00000179", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return machine


def _reply(r: object) -> dict[str, Any]:
    return cast(dict[str, Any], r)


def _at_stop(ref: str) -> dict[str, Any]:
    session = cast(Any, dstate.STATE.session)
    return next(w for w in arming.evaluate_watches(session) if w["ref"] == ref)


def test_a_freeze_pins_each_byte_at_its_value_and_reads_its_rows_back(tmp_path: Path) -> None:
    machine = live(tmp_path)
    got = _reply(server.watch_add(ref=TICKS, mode="freeze", length=2))
    assert got["status"] == "ok" and got["state"] == "armed" and got["frozen_hex"] == "4900", got
    assert got["entries"] == ["FM 0000018F (49)", "FM 00000190 (00)"]
    assert [c for c in machine.sent if " FM " in f" {c} "] == [
        "EXEC FM 08BC:18F", "EXEC FM 08BC:190"], machine.sent
    assert cast(Any, dstate.STATE.session).altered is True


def test_a_stop_says_whether_the_bytes_are_still_the_frozen_ones(tmp_path: Path) -> None:
    machine = live(tmp_path)
    server.watch_add(ref=TICKS, mode="freeze", length=1)
    assert _at_stop(TICKS)["state"] == "holding"
    machine.memory[LINEAR] = 0x4A
    moved = _at_stop(TICKS)
    assert moved["state"] == "not_held" and moved["bytes"] == "4a" and "dynamic core" in \
        moved["why"], moved


def test_a_freeze_whose_row_was_deleted_is_gone(tmp_path: Path) -> None:
    machine = live(tmp_path)
    server.watch_add(ref=TICKS, mode="freeze", length=1)
    machine.breakpoints.clear()
    assert _at_stop(TICKS)["state"] == "gone"


def test_a_clear_deletes_every_row_and_reads_the_list_back(tmp_path: Path) -> None:
    machine = live(tmp_path)
    server.watch_add(ref=TICKS, mode="freeze", length=2)
    got = _reply(server.declaration_clear(kind="watch", ref=TICKS))
    assert got["status"] == "ok" and sorted(got["disarmed"]) == [
        "FM 0000018F (49)", "FM 00000190 (00)"], got
    assert machine.breakpoints == []


def test_a_freeze_nobody_declared_at_the_same_offset_is_refused(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.breakpoints.append("FM 0000018F (11)")
    got = _reply(server.watch_add(ref=TICKS, mode="freeze", length=1))
    assert got["code"] == "ambiguous_ref" and "offset alone" in got["message"], got


def test_a_build_with_no_heavy_debugger_refuses_a_freeze(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    live(tmp_path)
    monkeypatch.setattr(binaries, "heavy_debug", lambda _b: False)
    got = _reply(server.watch_add(ref=TICKS, mode="freeze", length=1))
    assert got["code"] == "no_channel" and "heavy" in got["message"], got


@pytest.mark.parametrize(("kw", "said"), [({"length": 17}, "at most 16"),
                                          ({"ref": "[0814:0100]+2"}, "symbol or by address")])
def test_a_freeze_too_long_or_through_a_pointer_is_refused(tmp_path: Path, kw: dict[str, Any],
                                                           said: str) -> None:
    live(tmp_path)
    got = _reply(server.watch_add(**{"ref": TICKS, "mode": "freeze", "length": 1, **kw}))
    assert got["status"] == "INVALID" and said in got["message"], got


def test_a_second_freeze_on_an_offset_one_already_holds_is_refused(tmp_path: Path) -> None:
    live(tmp_path)
    assert _reply(server.watch_add(ref=TICKS, mode="freeze", length=2))["status"] == "ok"
    got = _reply(server.watch_add(ref="08BC:0190", mode="freeze", length=1))
    assert got["code"] == "ambiguous_ref", got


def test_a_freeze_that_fails_half_way_leaves_no_row_armed(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["FM"] = lambda c: (True, ["garbled"]) if c.endswith("190") else None
    got = _reply(server.watch_add(ref=TICKS, mode="freeze", length=2))
    assert got["code"] == "unexpected_answer" and machine.breakpoints == [], (got,
                                                                           machine.breakpoints)


def test_a_stored_freeze_is_not_armed_again_at_start(tmp_path: Path) -> None:
    machine = live(tmp_path)
    server.watch_add(ref=TICKS, mode="freeze", length=1)
    dstate.STATE.freezes.clear()
    machine.breakpoints.clear()
    session = cast(Any, dstate.STATE.session)
    rearm = arming.arm_at_start(session)["declarations"]["rearm"]
    assert machine.breakpoints == [] and any(r["ref"] == TICKS for r in rearm["unarmable"]), rearm


def test_a_freeze_through_a_pointer_is_refused_before_the_session() -> None:
    install()
    dstate.STATE.session = None
    got = _reply(server.watch_add(ref="[0040:0010]+2", mode="freeze", length=1))
    assert got["code"] == "bad_argument" and "symbol or by address" in got["message"], got
