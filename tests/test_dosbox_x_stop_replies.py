"""What a stop reply says about the stop, by the keys a caller reads: the cpu mode and why it is
unplaced, a position no survey could read, the guest's block and its mark, a reply built off the
record (its registers, watches, picture and block), the record's own dated reference, the cause
a stop is given (a run_to target, a `stop` call, the retrace), and the state's own defaults and
queued arms."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import NamesFake, _names, clean_session  # noqa: F401
from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_code as code
import dosbox_running as running
import dosbox_state as dstate
import dosbox_x_server as server


def test_the_cpu_mode_says_paged_protected_or_which_mark_left_it_unplaced() -> None:
    assert running.cpu_mode_of("Pr32", True) == "paged"
    assert running.cpu_mode_of("Pr32", False) == "protected"
    none = cast(dict[str, Any], running.cpu_mode_of("Pr32", None))
    assert none["available"] is False and "no PAGE/NOPG mark" in none["why"], none
    marked = cast(dict[str, Any], running.cpu_mode_of("Xyz", False))
    assert "a paging mark" in marked["why"] and "no PAGE" not in marked["why"], marked


def test_a_stop_no_survey_placed_has_neither_pc_nor_mode() -> None:
    cut = contract.unavailable(running.CUT_POSITION_WHY)
    assert running.position(None, None) == {"pc": cut, "cpu_mode": cut}


def test_a_stop_reply_and_a_reply_off_the_record_carry_the_paging_mark(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.paging = True  # type: ignore[attr-defined]
    got = running.stop_reply(fake)  # type: ignore[arg-type]
    assert got["cpu_mode"] == "paged", got
    assert running.recorded_head({})["cpu_mode"] == "paged"
    fake.paging = False  # type: ignore[attr-defined]
    assert running.stop_reply(fake)["cpu_mode"] == "protected"  # type: ignore[arg-type]


def test_the_guest_block_says_what_it_reads_and_keeps_its_mark(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.log = [f"line {n}" for n in range(10)]
    dstate.STATE.e9_offset = 4               # the previous stop's mark, short of the log's end
    block = running.e9_block(fake)  # type: ignore[arg-type]
    assert block["mark"] == 4 and block["lines_total"] == 6, block
    assert dstate.STATE.e9_offset == 10
    fake.log = None
    gone = running.e9_block(fake)  # type: ignore[arg-type]
    assert gone["available"] is False and "logfile" in gone["why"], gone


def test_a_reply_off_the_record_reuses_its_picture_and_carries_regs_watches_and_block(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    running.stop_reply(fake)  # type: ignore[arg-type]
    assert "picture" in dstate.STATE.last_stop
    made: list[Any] = []
    def counted(*a: Any) -> dict[str, Any]:
        made.append(a)
        return {}
    monkeypatch.setattr(code, "stop_instruction", counted)
    dstate.STATE.last_stop["picture"] = {"instruction": {"text": "MINE"}}
    got = running.recorded_stop_reply(fake, {})  # type: ignore[arg-type]
    assert made == [] and got["instruction"] == {"text": "MINE"}, got
    regs = dstate.STATE.last_stop["registers"]
    assert got["regs"] == dstate.shown_regs(regs), got
    assert isinstance(got["watches"], list) and isinstance(got["e9"], dict), got
    got["instruction"]["text"] = "changed"
    assert dstate.STATE.last_stop["picture"]["instruction"]["text"] == "MINE"


def test_a_new_stop_drops_the_last_ones_picture(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    w = fake.where()
    dstate.STATE.remember_stop(fake, w, fake.registers(), [], {"at": "x"})  # type: ignore[arg-type]
    dstate.STATE.last_stop["picture"] = {"instruction": {}}
    dstate.STATE.remember_stop(fake, w, fake.registers(), [], {"at": "x"})  # type: ignore[arg-type]
    assert "picture" not in dstate.STATE.last_stop


def test_the_dated_reference_says_how_long_ago_to_a_tenth(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    running.stop_reply(fake)  # type: ignore[arg-type]
    when = float(dstate.STATE.last_stop["when"])
    monkeypatch.setattr(time, "monotonic", lambda: when + 2.34)
    got = dstate.STATE.as_of()
    assert got is not None and got["since_s"] == 2.3 and isinstance(got["since_s"], float)
    assert got["wall_at"] == dstate.STATE.last_stop["clock"], got


def test_a_fresh_state_answers_before_any_session(tmp_path: Path) -> None:
    fresh = dstate.State()
    assert fresh.pending_summary() == {"arm": [], "disarm": 0, "symbols_load": False,
                                       "base_remeasure": False}, fresh.pending_summary()
    fresh.forget_symbols()
    fresh.clear_running_state()
    assert fresh.take_cancelled() is None
    assert fresh.session is None and fresh.store is None and fresh.starting is None
    assert isinstance(fresh.maps, type(dstate.STATE.maps))
    assert fresh.origin().endswith(".1"), fresh.origin()
    batch = fresh.batch_scratch()
    try:
        assert batch.is_dir() and batch.name.startswith("dosbox-x-batches-"), batch
        assert fresh.batches == 0 and fresh.batch_scratch() == batch
    finally:
        shutil.rmtree(batch)


# ------------------------------------------------------------- what a stop is said to be

def _attributed(monkeypatch: pytest.MonkeyPatch, got: dict[str, Any]) -> None:
    import dosbox_arming as arming
    monkeypatch.setattr(arming, "attribute_stop", lambda *a, **k: dict(got))


def test_a_run_to_stop_names_every_declaration_at_its_target(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    _attributed(monkeypatch, {"attributed": True, "ref": "a", "refs": ["a", "b"],
                              "by": "address", "at": "00A7:00000000"})
    got = running.stop_reply(fake, made_by={"ref": "T", "by": "run_to"})  # type: ignore[arg-type]
    assert got["cause"] == ("run_to's target T at 00A7:00000000, where breakpoint a, b is "
                            "declared too"), got["cause"]
    _attributed(monkeypatch, {"attributed": True, "ref": "a", "by": "address",
                              "at": "00A7:00000000"})
    one = running.stop_reply(fake, made_by={"ref": "T", "by": "run_to"})  # type: ignore[arg-type]
    assert one["cause"].endswith("where breakpoint a is declared too"), one["cause"]


def test_a_stop_call_names_a_declaration_there_before_itself(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    _attributed(monkeypatch, {"attributed": True, "ref": "a", "by": "address",
                              "at": "00A7:00000000"})
    got = running.stop_reply(fake, asked_by="stop")  # type: ignore[arg-type]
    assert got["cause"].startswith("breakpoint a "), got["cause"]
    _attributed(monkeypatch, {"attributed": False, "at": "00A7:00000000"})
    own = running.stop_reply(fake, asked_by="stop")  # type: ignore[arg-type]
    assert own["cause"] == "the `stop` call at 00A7:00000000", own["cause"]
    assert dstate.STATE.last_stop["attribution"] == {
        "attributed": True, "ref": "stop", "by": "stop", "at": "00A7:00000000"}
    _, words = dstate.STATE.stop_named(fake)  # type: ignore[arg-type]
    assert words == " at 00A7:00000000 (stop)", words


def test_only_a_caller_that_may_meet_the_retrace_stop_blames_it(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    dstate.STATE.retrace_pending = True
    plain = running.stop_reply(fake)  # type: ignore[arg-type]
    assert plain["cause"].startswith("no declared code breakpoint"), plain["cause"]
    based = running.stop_or_base(fake, True, {})  # type: ignore[arg-type]
    assert based["cause"].startswith("no declared code breakpoint"), based["cause"]
    assert dstate.STATE.retrace_pending is True
    made = running.stop_reply(fake, retrace_may_stop=True,  # type: ignore[arg-type]
                              made_by={"ref": "T", "by": "run_to"})
    assert made["cause"].startswith("run_to's target T"), made["cause"]
    assert dstate.STATE.retrace_pending is True
    blamed = running.stop_or_base(fake, True, {}, retrace_may_stop=True)  # type: ignore[arg-type]
    assert blamed["cause"].startswith("most likely the retrace stop"), blamed["cause"]
    assert dstate.STATE.retrace_pending is False


def test_an_arm_queued_while_running_says_where_it_will_be_reported(tmp_path: Path) -> None:
    _names(tmp_path)
    dstate.STATE.pending["dirty"] = False
    got = dstate.STATE.queue_arm("_main")
    assert "`applied_on_stop`" in got["note"] and dstate.STATE.pending["dirty"] is True, got


def test_a_running_guest_s_mode_points_at_last_stop(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.running = True
    mode = cast(dict[str, Any], running.stop_cpu_mode(fake))  # type: ignore[arg-type]
    assert "`last_stop`" in mode["why"], mode
    fake.running = False
    mode = cast(dict[str, Any], running.stop_cpu_mode(fake))  # type: ignore[arg-type]
    assert "`last_stop`" in mode["why"] and "not readable" in mode["why"], mode


def test_a_reply_off_the_record_evaluates_its_watches_against_that_stop(tmp_path: Path) -> None:
    import dosbox_symbols as dsym
    fake = _names(tmp_path, symbols=[dsym.Symbol("_v", 0x6024)])
    fake.mem[(0xAF, 0x6024)] = (7).to_bytes(4, "little")
    fake.mem[(0xAF, 0x6028)] = (9).to_bytes(4, "little")
    for ref in ("00AF:00006028", "_v"):
        added = cast(dict[str, Any], server.watch_add(ref=ref, mode="show", length=4))
        assert added["status"] == "ok", added
    running.stop_reply(fake)  # type: ignore[arg-type]
    got = running.recorded_stop_reply(fake, {})  # type: ignore[arg-type]
    by = {w["ref"]: w for w in got["watches"]}

    def got_value(n: int) -> Any:
        return arming.render_watch(n.to_bytes(4, "little"), 4, "u32")
    assert {r: (w["state"], w.get("value")) for r, w in by.items()} == {
        "00AF:00006028": ("evaluated", got_value(9)), "_v": ("evaluated", got_value(7))}, by


def test_a_cut_guest_block_says_how_to_read_the_rest_from_the_guest_channel(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.log = [f"line {n}" for n in range(20)]
    dstate.STATE.e9_offset = 0
    block = running.e9_block(fake)  # type: ignore[arg-type]
    assert block["truncated"] is True and 'channel="guest"' in block["how"], block


def test_a_reply_off_a_record_with_no_picture_decodes_it_from_that_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    running.stop_reply(fake)  # type: ignore[arg-type]
    stop = dstate.STATE.last_stop
    del stop["picture"]
    fake.survey_text = "THE SURVEY"
    asked: list[tuple[Any, ...]] = []

    def decoded(*a: Any) -> dict[str, Any]:
        asked.append(a)
        return {"instruction": {"text": "DECODED"}}
    monkeypatch.setattr(code, "stop_instruction", decoded)
    got = running.recorded_stop_reply(fake, {})  # type: ignore[arg-type]
    assert asked == [(fake, dict(stop["where"]), dict(stop["registers"]), "THE SURVEY")], asked
    assert got["instruction"] == {"text": "DECODED"} and stop["picture"] == {
        "instruction": {"text": "DECODED"}}, (got, stop)


def test_a_stop_the_cancelled_call_had_already_reached_is_named_as_that_call_s(
        tmp_path: Path) -> None:
    """A cancel that lands with the guest at a stop nobody read (the call's own retrace or
    breakpoint) records that stop as the cancelled call's, in the words a cancelled call's stop
    is named with, as the stop it breaks in for is."""
    import dosbox_mcp
    fake = _names(tmp_path)
    fake.stop_count = 1
    got = dosbox_mcp._stop_of_its_own(fake)  # type: ignore[arg-type]
    assert got["cause"].startswith("a cancelled call's stop at "), got["cause"]
