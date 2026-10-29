"""Count and capture watches against the channel double, whose `TAP` files are what the debugger
wrote on the tap guest (`tests/fixtures/taps/`): its counter written once a tick by `w_inc`, one
more each time, and its polled byte read once a tick by `r_poll`."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, cast

import pytest
from channel_double import REAL_STOP, Machine, protected, session_over
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)

from scry_dosbox_x import arming, server, taps
from scry_dosbox_x import binary as binaries
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as sym

TAPS = Path(__file__).parent / "fixtures" / "taps"
SOURCES = {"W": TAPS / "count-writes.rows", "R": TAPS / "polled-reads.rows",
           "C": TAPS / "count-and-pair.tab"}
#: `tap.asm`'s places, as its listing puts them in the segment DOS loaded it at.
COUNT, POLLED, W_INC, W_PAIR, R_POLL = "0814:0138", "0814:013E", "0814:011D", "0814:0126", \
    "0814:0129"


def live(tmp_path: Path, **over: Any) -> Machine:
    install()
    machine = Machine(regs=dict(REAL_STOP), tap_sources=SOURCES, **over)
    dstate.STATE.session = session_over(machine, tmp_path)
    dstate.STATE.remember_stop(dstate.STATE.session,
                               {"cs": "0814", "eip": "00000100", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return machine


def _ok(reply: object) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def _listed(ref: str) -> dict[str, Any]:
    return next(w for w in _ok(server.declaration_list("watch"))["watches"] if w["ref"] == ref)


def _at_stop(ref: str) -> dict[str, Any]:
    session = cast(Any, dstate.STATE.session)
    return next(w for w in arming.evaluate_watches(session) if w["ref"] == ref)


def test_a_count_tallies_each_write_by_value_and_by_writer(tmp_path: Path) -> None:
    machine = live(tmp_path)
    got = _ok(server.watch_add(ref=COUNT, mode="count", length=8, fmt="u8[8]"))
    assert (got["state"], got["armed"], got["entry"]) == ("armed", True, "TAP 1"), got
    assert got["addr"] == "0814:00000138"
    assert machine.sent[-2].startswith("EXEC TAP C 0814:138 8 ")
    item = _listed(COUNT)
    assert (item["state"], item["installed"], item["total"]) == ("tallied", True, 10), item
    assert item["writers"] == [{"pc": f"0814:0000{W_INC[5:]}", "count": 5},
                               {"pc": f"0814:0000{W_PAIR[5:]}", "count": 5}]
    # Each write of the counter lands one byte in its lane; the word copy two, beyond the range's
    # first byte, so neither covers the 8 bytes whole.
    assert item["values_total"] == 10 and all(v["partial"] for v in item["values"])
    first = [v for v in item["values"] if v["at"] == "0814:00000138"]
    assert sorted(v["raw_hex"] for v in first) == ["01", "02", "03", "04", "05"]


def test_a_count_of_one_byte_decodes_each_value(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=1))
    item = _listed(COUNT)
    assert sorted(v["value"] for v in item["values"] if "value" in v) == [1, 2, 3, 4, 5]


def test_a_write_capture_keeps_each_row_with_the_block_before_the_write(tmp_path: Path) -> None:
    machine = live(tmp_path)
    got = _ok(server.watch_add(ref=COUNT, mode="capture", trigger=COUNT, length=4, fmt="u8[4]"))
    assert got["trigger_addr"] == "0814:00000138" and got["trigger_type"] == "w", got
    assert machine.sent[-2].startswith("EXEC TAP W 0814:138 0814:138 4 ")
    item = _listed(COUNT)
    assert (item["state"], item["rows_kept"], item["rows_max"]) == ("captured", 5, taps.ROWS_MAX)
    rows = item["first_rows"]
    assert [r["n"] for r in rows] == [1, 2, 3, 4, 5]
    for r in rows:
        assert r["pc"] == f"0814:0000{W_INC[5:]}"
        written = int(r["data"], 16)
        assert r["mask"] == "0x000000ff" and written == r["n"]
        assert r["block"] == [written - 1, 0xA5, 0x5A, 0xC3], "the block from before the write"
        assert 0 <= r["line"] < 525
    assert [r["frame"] for r in rows] == [4, 8, 12, 16, 19]
    times = [r["time_s"] for r in rows]
    assert all(0.054 < b - a < 0.056 for a, b in zip(times, times[1:], strict=False)), times


def test_a_read_capture_keeps_the_access_alone(tmp_path: Path) -> None:
    machine = live(tmp_path)
    got = _ok(server.watch_add(ref=POLLED, mode="capture", trigger_type="r"))
    assert (got["length"], got["trigger_type"]) == (1, "r") and "trigger_addr" not in got
    assert machine.sent[-2].startswith("EXEC TAP R 0814:13E ")
    rows = _listed(POLLED)["first_rows"]
    assert len(rows) == 5 and all(r["pc"] == f"0814:0000{R_POLL[5:]}" for r in rows)
    assert all((r["data"], r["mask"]) == ("0x00420000", "0x00ff0000") for r in rows), rows
    assert all("block" not in r for r in rows)


def test_a_stop_survey_says_how_many_since_the_last_stop_and_no_rows(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="capture", trigger=COUNT, length=4))
    first = _at_stop(COUNT)
    assert (first["total"], first["since_last_stop"]) == (5, 5) and "first_rows" not in first
    again = _at_stop(COUNT)
    assert again["since_last_stop"] == 0, "a stop with nothing new counts nothing"
    _listed(COUNT)
    assert _at_stop(COUNT)["since_last_stop"] == 0, "a listing between stops consumes nothing"


def test_a_total_that_fell_is_a_reset(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="capture", trigger=COUNT, length=4))
    _at_stop(COUNT)
    dstate.STATE.taps[COUNT].last_total = 50
    item = _at_stop(COUNT)
    assert (item["since_last_stop"], item["reset"]) == (5, True)


def test_one_taplist_serves_every_tap_of_a_survey(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    _ok(server.watch_add(ref=POLLED, mode="capture", trigger_type="r"))
    machine.sent.clear()
    arming.evaluate_watches(cast(Any, dstate.STATE.session))
    assert machine.sent.count("EXEC TAPLIST") == 1


def test_a_survey_with_no_tap_sends_no_taplist(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="show", length=1))
    arming.evaluate_watches(cast(Any, dstate.STATE.session))
    assert "EXEC TAPLIST" not in machine.sent


def test_clear_removes_the_tap_and_the_declaration(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    got = _ok(server.declaration_clear("watch", ref=COUNT))
    assert got["disarmed"] == ["TAP 1"] and machine.taps == {}
    assert COUNT not in dstate.STATE.taps


def test_declared_again_unchanged_is_a_no_op_and_otherwise_refused(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    again = _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    assert again["already_stored"] is True and len(machine.taps) == 1
    other = cast(dict[str, Any], server.watch_add(ref=COUNT, mode="count", length=4))
    assert other["code"] == "bad_argument" and "already declared" in other["message"], other


def test_a_tap_whose_file_cannot_be_written_stores_nothing(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    live(tmp_path)
    monkeypatch.setattr(dstate.STATE, "session_scratch", lambda: tmp_path / "gone")
    got = cast(dict[str, Any], server.watch_add(ref=COUNT, mode="count", length=8))
    assert got["code"] == "bad_argument" and "cannot write" in got["message"], got
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    assert not [d for d in store.declarations() if d.kind == "watch"]


def test_a_build_without_tap_is_refused_by_the_command_s_name(tmp_path: Path) -> None:
    live(tmp_path, commands=tuple(c for c in binaries.COMMANDS if c != taps.TAP))
    got = cast(dict[str, Any], server.watch_add(ref=COUNT, mode="count", length=8))
    assert got["code"] == "no_channel" and "`TAP`" in got["message"], got


@pytest.mark.parametrize(("args", "said"), [
    ({"mode": "count", "length": 8, "trigger": COUNT}, "trigger and trigger_type"),
    ({"mode": "show", "length": 1, "trigger_type": "r"}, "trigger and trigger_type"),
    ({"mode": "capture", "length": 4}, "names its trigger"),
    ({"mode": "capture", "trigger_type": "r", "length": 2}, "no trigger, length or fmt"),
    ({"mode": "count", "length": 1025}, "at most 1024"),
    ({"mode": "capture", "trigger": COUNT, "length": 129}, "at most 128"),
    ({"mode": "count", "length": 8, "by": "pointer", "ref": "[0814:0138]"}, "by symbol or by"),
    ({"mode": "capture", "trigger_type": "x"}, "trigger_type"),
])
def test_arguments_are_judged_before_the_session_is_asked(args: dict[str, Any],
                                                          said: str) -> None:
    got = cast(dict[str, Any], server.watch_add(**{"ref": COUNT, **args}))
    assert got["code"] == "bad_argument" and said in got["message"], got


def test_a_tap_is_armed_again_where_it_resolves_at_start(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    dstate.STATE.taps.clear()
    machine.taps.clear()
    got = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert [r["ref"] for r in got["rearmed"]] == [COUNT] and len(machine.taps) == 1
    again = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert again["rearmed"] == [] and len(machine.taps) == 1, "one tap where it already is"


# ------------------------------------------------------------- what a listing cannot read

def test_a_tap_the_debugger_did_not_list_or_displaced_says_so(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    machine.hooks["TAPLIST"] = lambda body: (True, [
        "DEBUG: TAP 1 C PHYS=8278 LEN=8 INSTALLED=0 TOTAL=4 ROWS=0 OVERFLOW_ROWS=0 VALUES=4 "
        "OVERFLOW_VALUES=0 PCS=1 OVERFLOW_PCS=0", "DEBUG: TAPLIST 1"])
    displaced = _listed(COUNT)
    assert (displaced["state"], displaced["installed"]) == ("displaced", False)
    assert "replaced" in displaced["why"]
    machine.hooks["TAPLIST"] = lambda body: (True, ["DEBUG: TAPLIST 0"])
    assert _listed(COUNT)["state"] == "unlisted"
    machine.hooks["TAPLIST"] = lambda body: (False, ["*** Debugger command not recognized"])
    item = _listed(COUNT)
    assert item["state"] == "unlisted" and "TAPLIST" in item["why"], item


def test_a_declaration_with_no_tap_in_this_session_is_unarmed(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    dstate.STATE.taps.clear()
    dstate.STATE.taps["0000:0000"] = taps.Tap(9, "C", 0, 1, 0, 0, tmp_path / "x")
    item = _listed(COUNT)
    assert (item["state"], item["installed"]) == ("unarmed", False) and "`start`" in item["why"]


def test_a_rows_file_gone_or_cut_mid_row_lists_the_whole_rows_only(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="capture", trigger=COUNT, length=4, fmt="u8[4]"))
    tap = dstate.STATE.taps[COUNT]
    decl = next(d for d in cast(dec.DeclarationStore, dstate.STATE.store).declarations()
                if d.ref == COUNT)
    whole = SOURCES["W"].read_text().splitlines()
    tap.path.write_text("\n".join(whole[:2]) + "\nr 3 89 165.4803 0814 0000")
    assert [r["n"] for r in taps.first_rows(tap, decl, 24)] == [1, 2]
    tap.path.unlink()
    assert taps.first_rows(tap, decl, 24) == []


def test_a_block_its_format_cannot_decode_says_why(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="capture", trigger=COUNT, length=4, fmt="u8[4]"))
    tap = dstate.STATE.taps[COUNT]
    tap.path.write_text(SOURCES["W"].read_text().splitlines()[0].rsplit(" ", 1)[0] + " 00a55a\n")
    decl = next(d for d in cast(dec.DeclarationStore, dstate.STATE.store).declarations()
                if d.ref == COUNT)
    row = taps.first_rows(tap, decl, 1)[0]
    assert row["block"]["available"] is False and row["raw_hex"] == "00a55a"


def test_a_writer_is_named_by_the_symbol_below_it(tmp_path: Path) -> None:
    live(tmp_path)
    dstate.STATE.install_table(sym.parse_nm("0000011d T w_inc\n00000126 T w_pair\n"))
    dstate.STATE.base = {"base": 0x8140}
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    writers = _listed(COUNT)["writers"]
    assert [w["symbol"] for w in writers] == ["w_inc", "w_pair"]


def test_an_unresolved_symbol_is_refused_and_nothing_stored(tmp_path: Path) -> None:
    live(tmp_path)
    got = cast(dict[str, Any], server.watch_add(ref="_nowhere", mode="count", length=2))
    assert got["code"] == "unknown_ref" and "_nowhere" in got["message"], got
    assert not dstate.STATE.taps


def test_a_tapdel_the_debugger_refused_keeps_the_tap(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    machine.hooks["TAPDEL"] = lambda body: (False, ["DEBUG: TAPDEL no tap 1"])
    with pytest.raises(ds.Invalid, match="TAPDEL 1"):
        taps.remove(cast(Any, dstate.STATE.session), COUNT)
    assert COUNT in dstate.STATE.taps
    assert taps.remove(cast(Any, dstate.STATE.session), "0000:0001") is None


@pytest.mark.parametrize(("fields", "said"), [
    ({"watch_mode": "show", "trigger": COUNT}, "carries no trigger"),
    ({"watch_mode": "count", "trigger_type": "w"}, "count watch carries no trigger"),
    ({"watch_mode": "capture", "trigger_type": "x"}, "one of"),
    ({"watch_mode": "capture", "trigger_type": "w"}, "names its trigger"),
    ({"watch_mode": "capture", "trigger_type": "r", "trigger": COUNT}, "names its trigger"),
])
def test_a_stored_watch_holds_its_trigger_to_its_mode(fields: dict[str, Any], said: str) -> None:
    with pytest.raises(dec.DeclarationError, match=said):
        dec.Declaration("watch", "address", COUNT, width=1, fmt="u8", **fields)
    with pytest.raises(dec.DeclarationError, match="no watch fields"):
        dec.Declaration("breakpoint", "address", COUNT, trigger=COUNT)


def test_a_capture_round_trips_through_the_store_file() -> None:
    made = dec.Declaration("watch", "address", "0814:013C", width=2, fmt="u16",
                           watch_mode="capture", trigger=COUNT, trigger_type="w")
    back = dec.Declaration.from_dict(made.to_dict())
    assert back == made and back.trigger == COUNT and back.trigger_type == "w"
    assert made.adopted_by("o", "t").trigger == COUNT


def test_a_tap_declared_after_one_was_cleared_writes_a_file_of_its_own(tmp_path: Path) -> None:
    """The count by name and the count by address are two declarations of one place: the second,
    numbered after a third was cleared, must not write into the first's file."""
    live(tmp_path)
    dstate.STATE.install_table(sym.parse_nm("00000138 D count\n"))
    dstate.STATE.base = {"base": 0x8140}
    _ok(server.watch_add(ref=POLLED, mode="capture", trigger_type="r"))
    _ok(server.watch_add(ref="count", mode="count", length=1))
    _ok(server.declaration_clear("watch", ref=POLLED))
    _ok(server.watch_add(ref=COUNT, mode="count", length=1))
    paths = [t.path for t in dstate.STATE.taps.values()]
    assert len(set(paths)) == len(paths) == 2, paths


def test_a_tap_the_debugger_took_but_does_not_list_installed_is_not_armed(
        tmp_path: Path) -> None:
    """Every arming is read back off the debugger's list, never its acknowledgement."""
    machine = live(tmp_path)
    machine.hooks["TAPLIST"] = lambda body: (True, [
        "DEBUG: TAP 1 C PHYS=8278 LEN=8 INSTALLED=0 TOTAL=0 ROWS=0 OVERFLOW_ROWS=0 VALUES=0 "
        "OVERFLOW_VALUES=0 PCS=0 OVERFLOW_PCS=0", "DEBUG: TAPLIST 1"])
    got = cast(dict[str, Any], server.watch_add(ref=COUNT, mode="count", length=8))
    assert got["code"] == "readback_refused" and "TAPLIST" in got["message"], got
    assert machine.taps == {} and not dstate.STATE.taps, "the tap the list denied is removed"
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    assert not [d for d in store.declarations() if d.kind == "watch"]


def test_the_tally_id_is_the_debugger_s_id_as_text(tmp_path: Path) -> None:
    live(tmp_path)
    got = _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    assert got["tally_id"] == "1" and _listed(COUNT)["tally_id"] == "1"
    assert got["summary"] == f"watch_add {COUNT}: count watch armed as TAP 1, 8 bytes"


def _displaced(machine: Machine) -> None:
    """The next `TAPLIST` lists tap 1 displaced, as a mode set or a loaded state leaves it."""
    def once(_: str) -> tuple[bool, list[str]]:
        del machine.hooks["TAPLIST"]
        return True, ["DEBUG: TAP 1 C PHYS=8278 LEN=8 INSTALLED=0 TOTAL=3 ROWS=0 "
                      "OVERFLOW_ROWS=0 VALUES=3 OVERFLOW_VALUES=0 PCS=1 OVERFLOW_PCS=0",
                      "DEBUG: TAPLIST 1"]
    machine.hooks["TAPLIST"] = once


def test_a_displaced_tap_declared_again_is_tapped_again(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    _displaced(machine)
    again = _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    assert again["tally_id"] == "2" and list(machine.taps) == [2], again


def test_a_displaced_tap_is_tapped_again_by_the_rearm(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    _displaced(machine)
    got = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert [r["ref"] for r in got["rearmed"]] == [COUNT] and list(machine.taps) == [2]


def test_a_tap_whose_read_back_failed_is_taken_out(tmp_path: Path) -> None:
    machine = live(tmp_path)
    machine.hooks["TAPLIST"] = lambda body: (False, ["*** Debugger command not recognized"])
    got = cast(dict[str, Any], server.watch_add(ref=COUNT, mode="count", length=8))
    assert got["code"] == "readback_refused", got
    assert machine.taps == {} and not dstate.STATE.taps


def test_a_queued_removal_never_takes_a_newer_tap_of_the_same_ref(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    session = cast(Any, dstate.STATE.session)
    assert taps.remove(session, COUNT, tap_id=9) is None and COUNT in dstate.STATE.taps
    assert taps.remove(session, COUNT, tap_id=1) == "TAP 1"


def test_a_raw_tap_placed_in_real_mode_waits_at_a_protected_mode_stop(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    dstate.STATE.taps.clear()
    machine.taps.clear()
    protected(machine)
    got = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert [r["ref"] for r in got["unarmable"]] == [COUNT] and machine.taps == {}, got
    assert "real-mode stop" in got["unarmable"][0]["why"]


def test_a_trigger_is_stored_in_one_spelling_and_never_through_a_pointer(tmp_path: Path) -> None:
    live(tmp_path)
    _ok(server.watch_add(ref="0814:013C", mode="capture", trigger="0814:138", length=2))
    again = _ok(server.watch_add(ref="0814:013C", mode="capture", trigger="814:0138", length=2))
    assert again["already_stored"] is True, again
    pointer = cast(dict[str, Any], server.watch_add(ref="0814:013C", mode="capture",
                                                   trigger="[0814:0138]", length=2))
    assert pointer["code"] == "bad_argument" and "pointer" in pointer["message"], pointer


def test_a_row_of_a_build_that_writes_no_frame_is_read_with_the_frame_unavailable() -> None:
    old = "r 1 224 55.629400000 0814 0000011D 00000001 000000FF 00a55ac3"
    new = "r 1 4 224 55.629400000 0814 0000011D 00000001 000000FF 00a55ac3"
    assert taps._ROW.match(old).groups()[:3] == ("1", None, "224")  # type: ignore[union-attr]
    assert taps._ROW.match(new).groups()[:3] == ("1", "4", "224")  # type: ignore[union-attr]


_LOADED = {"path": "/s/x.sav", "paused": True, "machine": "svga_s3", "memory_mb": 16,
           "program": "TAP", "saved_at": "2026-10-29 12:00:00", "version": "2026.10.01",
           "mark": {}}


def test_a_state_load_taps_the_declared_watches_again_and_says_so(tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    session = cast(Any, dstate.STATE.session)

    def loaded(name: str, seconds: float) -> dict[str, object]:
        session.machine_replaced = True
        _displaced(machine)          # the fork's load resets the page handlers
        return {"name": name, **_LOADED}

    session.machine_replaced = False
    session.load_state = loaded
    got = _ok(server.state_write("load", name="x"))
    assert got["taps"] == {"rearmed": [COUNT], "unarmed": []}, got
    assert list(machine.taps) == [2], "the displaced tap was replaced by a new one"
    assert _listed(COUNT)["tally_id"] == "2"


def test_a_state_load_with_no_watch_declared_adds_nothing(tmp_path: Path) -> None:
    live(tmp_path)
    session = cast(Any, dstate.STATE.session)
    session.machine_replaced = False
    session.load_state = lambda name, seconds: {"name": name, **_LOADED}
    assert "taps" not in _ok(server.state_write("load", name="x"))


def test_a_tap_on_an_auto_core_session_says_protected_mode_may_leave_it_blind(
        tmp_path: Path) -> None:
    live(tmp_path)
    session = cast(Any, dstate.STATE.session)
    assert session.launch.core == "auto"
    got = _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    assert "auto" in got["note"] and "cpu core=normal" in got["note"], got
    session.launch = dataclasses.replace(session.launch, core="normal")
    again = _ok(server.watch_add(ref=POLLED, mode="capture", trigger_type="r"))
    assert "note" not in again, again


def test_a_load_that_released_a_running_guest_says_its_taps_wait_for_a_stop(
        tmp_path: Path) -> None:
    machine = live(tmp_path)
    _ok(server.watch_add(ref=COUNT, mode="count", length=8))
    session = cast(Any, dstate.STATE.session)

    def loaded(name: str, seconds: float) -> dict[str, object]:
        session.machine_replaced = True
        machine.stopped = False        # the load stopped the guest and released it again
        session._at_debugger = False
        return {"name": name, **_LOADED}

    session.machine_replaced = False
    session.load_state = loaded
    got = _ok(server.state_write("load", name="x"))
    assert got["taps"]["rearmed"] == [] and got["taps"]["unarmed"][0]["ref"] == COUNT, got
    assert "running" in got["taps"]["unarmed"][0]["why"], got
    assert machine.taps == {} or list(machine.taps) == [1], "nothing was tapped on a running guest"
