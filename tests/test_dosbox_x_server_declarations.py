"""The DOSBox-X server: breakpoints, watches and their re-arming."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import (  # noqa: E402
    _Booted,
    _deferred_load_with,
    _loaded_then_restored,
    _names,
    _ok,
    _start_on_a_booted_fake,
    _start_over_a_store,
    build_of,
    clean_session,  # noqa: E402, F401
    install,
    stub_build,
)
from scry_core import declaration_rows
from scry_core import reply_contract as contract

from scry_dosbox_x import arming, placement, running, server, start_symbols
from scry_dosbox_x import code as dcode
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import mcp as dosbox_mcp
from scry_dosbox_x import run_state as rs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def test_the_block_carries_each_alarm_while_it_holds_and_the_process_facts_ride_at_the_top(
        ) -> None:
    fake = install()
    quiet = fake.state()
    loud = {**quiet, "conf_changed_on_disk": True, "output_bytes_dropped": 4096}
    alarms = ("conf_changed_on_disk", "output_bytes_dropped")
    fake.state = lambda: loud  # type: ignore[method-assign]
    short = cast(dict[str, Any], server.registers())["session"]
    assert all(short[k] == loud[k] for k in alarms) and "pid" not in short, short
    status = cast(dict[str, Any], server.status())
    assert status["pid"] == 4242 and status["output_bytes_dropped"] == 4096, status
    fake.state = lambda: quiet  # type: ignore[method-assign]
    short = cast(dict[str, Any], server.registers())["session"]
    assert set(short) == {"alive", "running", "altered"}, short
    closed = cast(dict[str, Any], server.close())
    assert closed["pid"] == 4242 and closed["elapsed_s"] == 1.0, "close says what it ended"


def test_the_server_declares_instructions_and_they_name_what_a_caller_needs() -> None:
    """The `instructions` field is how the PROTOCOL hands a session the server's own contract."""
    text = server.mcp.instructions
    assert text, "the server declares no instructions at all"
    # ABSENCE, not just presence: a phrase that must not be there is not checked by
    # asserting the ones that must.
    for phrase, why in (
        ("ToolSearch", "the deferred-tools rule is the session's own, loaded every session"),
        ("validates the session",
         "build_check answers about the BUILD, never about a reading: a session is not "
         "something it validates"),
        ("console reader", "the pattern belongs to e9; `debug` takes only `command`"),
        ("cycles", "the guest-clock rule is the session's own, and a verbatim second copy here "
                   "is the duplication the deleted SessionStart hook was killed for"),
    ):
        assert phrase not in text, f"the instructions carry {phrase!r}: {why}"
    assert "BUILD" in text and "REFUSES" in text, (
        "build_check must be described as what it is: a precondition check that refuses while a "
        "session is live"
    )
    assert "read_memory" in text, (
        "this server's own docstrings say a VALUE goes through registers/read_memory/memdump; "
        "instructions naming only e9 and debug send a caller to the positional tail"
    )


def test_breakpoint_at_a_symbol_arms_stores_and_says_when_it_is_marked(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T"),
            dsym.Symbol("ATRCT_RUN", 0x599, kind="T", idle=True)]     # one marked public
    fake = _names(tmp_path, symbols=syms)
    fake.launch = dataclasses.replace(fake.launch, core="normal")     # `auto` adds its own note
    got = server.breakpoint_at(ref="_uicue_apply")
    assert got["status"] == "ok" and got["armed"] is True
    assert got["entry"] == "BP 00A7:3D5E0"
    assert "note" not in got, "nothing to say: no note"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["_uicue_apply"]   # type: ignore[union-attr]
    marked = server.breakpoint_at(ref="ATRCT_RUN")
    assert marked["armed"] is True and marked.get("marked", False) is True
    assert "linker's mark" in str(marked["note"])


def test_a_code_breakpoint_on_a_dynamic_core_is_armed_and_says_it_may_be_passed_over(
        tmp_path: Path) -> None:
    """A dynamic core checks breakpoints at block boundaries, so one inside a compiled block can
    be passed over: armed, with the limit and the remedy said, never refused."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T")])
    fake.launch = dataclasses.replace(fake.launch, core="dynamic")
    got = cast(dict[str, Any], server.breakpoint_at(ref="_uicue_apply"))
    assert got["status"] == "ok" and got["armed"] is True, got
    assert "cpu core=normal" in got["note"] and "dynamic" in got["note"], got
    fake.launch = dataclasses.replace(fake.launch, core="auto")
    auto = cast(dict[str, Any], server.breakpoint_at(ref="_uicue_apply"))
    assert auto["armed"] is True, auto
    assert "protected-mode" in auto["note"] and "cpu core=normal" in auto["note"], auto
    fake.launch = dataclasses.replace(fake.launch, core="normal")
    plain = cast(dict[str, Any], server.breakpoint_at(ref="_uicue_apply"))
    assert "dynamic" not in str(plain.get("note")), plain


def test_re_declaring_a_breakpoint_is_a_no_op_that_re_arms_a_lost_row(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T", idle=True)]  # marked, for note
    fake = _names(tmp_path, symbols=syms)
    first = server.breakpoint_at(ref="_uicue_apply")
    assert first.get("already_stored", False) is False and first["armed"] is True
    assert first.get("marked", False) is True and "linker's mark" in str(first["note"])
    again = server.breakpoint_at(ref="_uicue_apply")
    assert again.get("already_stored", False) is True and again["armed"] is True
    assert len([r for r in fake.rows if r["entry"] == "BP 00A7:3D5E0"]) == 1
    # THE NOTE SURVIVES the no-op: dropping it would lose the mark warning on the repeated
    # call a rebuild makes most.
    assert again.get("marked", False) is True and "linker's mark" in str(again["note"])
    # ROW LOST (new session), re-declared -> re-armed, not falsely reported armed.
    fake.rows.clear()
    rearmed = server.breakpoint_at(ref="_uicue_apply")
    assert rearmed.get("already_stored", False) is True and rearmed["armed"] is True
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:3D5E0"]
    assert len(dstate.STATE.store.declarations()) == 1   # type: ignore[union-attr]


def test_re_declaring_a_change_watch_is_a_no_op_and_keeps_the_pr_caveat(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("_g_rate", 0x1234, kind="D")]
    fake = _names(tmp_path, symbols=syms, mode="Pr32")
    first = server.watch_add(ref="_g_rate", mode="change", length=4)
    assert first.get("already_stored", False) is False and first["armed"] is True
    assert "protected-mode watch" in str(first["caveat"])
    again = server.watch_add(ref="_g_rate", mode="change", length=4)
    assert again.get("already_stored", False) is True and again["armed"] is True
    assert "protected-mode watch" in str(again["caveat"])
    assert len([r for r in fake.rows if r["entry"].startswith("BPPM")]) == 4   # a row a byte


def test_a_by_address_declaration_on_a_running_machine_is_kept_unarmed_not_invalid(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, arm_fails=True)
    fake.bp_raises = True                         # the running machine refuses a list read
    bp = server.breakpoint_at(ref="00A7:0100")
    assert bp["status"] == "ok" and bp["stored"] is True and bp["armed"] is False
    # A refusal of the RUNNING kind now queues the declaration for the next stop (the
    # running-guest contract); what this guard pins is unchanged: `ok`,
    # `stored`, and never an INVALID with the declaration already in the store.
    assert bp["state"] == "pending"
    w = server.watch_add(ref="00A7:0100", mode="change", length=4)
    assert w["status"] == "ok" and w["stored"] is True and w["armed"] is False
    assert w["state"] == "pending"


def test_an_interrupt_breakpoint_is_stored_listed_cleared_and_not_double_armed(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    armed = server.breakpoint_interrupt(number=0x21)
    assert armed["stored"] is True and armed.get("already_stored", False) is False
    assert armed["entry"] == "BPINT 21", "the row spelling the docstring promises"
    assert [r["entry"] for r in fake.rows] == ["BPINT 21"]
    listed = server.declaration_list("breakpoint")
    row = next(b for b in listed["breakpoints"] if b["ref"] == "BPINT 21")
    assert row["state"] == "armed" and "foreign" not in listed
    # RE-ARM IS A NO-OP: no second BPINT 21 row, and the reply says already_stored.
    again = server.breakpoint_interrupt(number=0x21)
    assert again.get("already_stored", False) is True and again["armed"] is True
    assert [r["entry"] for r in fake.rows] == ["BPINT 21"]
    # A BPINT the store did not place is FOREIGN, matched by its text.
    fake.rows.append({"index": "09", "entry": "BPINT 10"})
    assert "BPINT 10" in server.declaration_list("breakpoint")["foreign"]["breakpoints"]
    # CLEAR removes the declaration and disarms the row it owns, leaving the foreign one.
    cleared = server.declaration_clear("breakpoint", all=True)
    assert cleared["declarations_cleared"] == 1 and cleared["disarmed"] == ["BPINT 21"]
    assert [r["entry"] for r in fake.rows] == ["BPINT 10"]
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_a_registerpoint_is_stored_listed_cleared_and_not_double_armed(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    armed = server.regpoint_add(condition="ax == 0x13 && bl!=0")
    assert armed["ref"] == "AX==13 && BL!=0" and armed["entry"] == "BPIF AX==13 && BL!=0", armed
    assert [r["entry"] for r in fake.rows] == ["BPIF AX==13 && BL!=0"]
    again = server.regpoint_add(condition="AX==13&&BL!=0")
    assert again["already_stored"] is True and [r["entry"] for r in fake.rows] == [
        "BPIF AX==13 && BL!=0"], "one row a condition, whatever its spelling"
    fake.rows.append({"index": "09", "entry": "BPIF CX==1"})
    listed = server.declaration_list("regpoint")
    assert [(g["ref"], g["state"]) for g in listed["regpoints"]] == [
        ("AX==13 && BL!=0", "armed")] and listed["foreign"] == {"regpoints": ["BPIF CX==1"]}, listed
    cleared = server.declaration_clear("regpoint", all=True)
    assert cleared["declarations_cleared"] == 1 and cleared["disarmed"] == [
        "BPIF AX==13 && BL!=0"], cleared
    assert [r["entry"] for r in fake.rows] == ["BPIF CX==1"]


@pytest.mark.parametrize(("condition", "says"), [
    ("AL==100", "AL holds 8 bits"), ("AX==10000", "AX holds 16 bits"),
    ("CS==10000", "CS holds 16 bits"), ("ES==10000", "ES holds 16 bits"),
    ("AX=13", "not a term"),
    ("AX==1 && BX==2 && CX==3 && DX==4 && SI==5", "at most 4 terms"),
    ("AX==-1", "not a term"), ("", "not a term")])
def test_a_condition_the_debugger_would_never_meet_is_refused_before_anything_is_armed(
        tmp_path: Path, condition: str, says: str) -> None:
    fake = _names(tmp_path)
    got = server.regpoint_add(condition=condition)
    assert got["status"] == "INVALID" and says in str(got["message"]), got
    assert fake.rows == [] and arming.current_store().declarations() == []


@pytest.mark.parametrize("condition", ["AL==FF", "AX==FFFF", "EAX==FFFFFFFF",
                                       "FLAGS==FFFFFFFF", "EIP==0x10000"])
def test_a_value_at_its_registers_width_is_taken(tmp_path: Path, condition: str) -> None:
    _names(tmp_path)
    assert server.regpoint_add(condition=condition)["status"] == "ok"


def test_the_flags_term_is_judged_on_all_32_bits_as_the_debugger_compares_them() -> None:
    from scry_dosbox_x.grammar import condition_holds
    regs = {"EFLAGS": "00020202", "EAX": "00001234"}
    assert condition_holds("FLAGS==20202", regs) is True
    assert condition_holds("FLAGS==202", regs) is False
    assert condition_holds("AH==12 && AL==34", regs) is True


def test_a_holding_registerpoint_is_named_but_never_taken_for_the_stops_maker(
        tmp_path: Path) -> None:
    """On a build whose `RUNSTATE` names no `BPIF` row a condition can hold at a stop something
    else made, so the stop stays unattributed: what reads `attributed` (a retrace cut, `run_to`'s
    arrival) must not see a declared stop, and `cause` names the registerpoint as the likely
    one."""
    fake = _names(tmp_path)
    held = [{"index": "00", "entry": "BPIF DS!=0"}]
    where = {"cs": "0814", "eip": "00000106", "mode": "real"}
    got = arming.attribute_stop(cast(ds.Session, fake), where=where,
                                machine=("real", {"DS": "0814"}), held=held)
    assert got["attributed"] is False and got["regpoints_holding"] == ["DS!=0"], got
    assert "registerpoint DS!=0" in dstate.cause(got), dstate.cause(got)
    dstate.STATE.retrace_pending = True
    got = arming.attribute_stop(cast(ds.Session, fake), where=where,
                                machine=("real", {"DS": "0814"}), held=held,
                                retrace_may_stop=True)
    assert got["retrace_pending"] is True and got["regpoints_holding"] == ["DS!=0"], got
    assert "registerpoint DS!=0" in dstate.cause(got), dstate.cause(got)


def test_a_registerpoint_the_debugger_names_as_the_stops_maker_is_attributed_exactly(
        tmp_path: Path) -> None:
    """`RUNSTATE` ends a stop made by a `BPIF` row with that row's `BPLIST` number: the stop is
    then that registerpoint's, though another one holds too."""
    fake = _names(tmp_path)
    fake.fired_entry = "BPIF AX==1"
    held = [{"index": "00", "entry": "BPIF DS!=0"}, {"index": "0A", "entry": "BPIF AX==1"}]
    where = {"cs": "0814", "eip": "00000106", "mode": "real"}
    got = arming.attribute_stop(cast(ds.Session, fake), where=where,
                                machine=("real", {"DS": "0814", "EAX": "1"}), held=held)
    assert got["attributed"] is True and got["ref"] == "AX==1" and got["by"] == "regpoint", got
    assert "regpoints_holding" not in got
    assert dstate.cause(got) == "registerpoint AX==1, whose condition came true at 0814:00000106"
    held = held[:1]                        # the row left the list since: nothing is claimed
    got = arming.attribute_stop(cast(ds.Session, fake), where=where,
                                machine=("real", {"DS": "0814"}), held=held)
    assert got["attributed"] is False and got["regpoints_holding"] == ["DS!=0"], got


@pytest.mark.parametrize(("line", "fired"), [
    ("DEBUG: RUNSTATE stopped cycles=5 ms=0.5 frames=3 bpif=0A", "BPIF AX==1"),
    ("DEBUG: RUNSTATE stopped cycles=5 ms=0.5 frames=3 bpif=0B", None),
    ("DEBUG: RUNSTATE stopped cycles=5 ms=0.5 frames=3", None),
    ("DEBUG: RUNSTATE running cycles=5 ms=0.5 frames=3", None)])
def test_runstate_says_which_bpif_row_stopped_the_machine_only_when_it_did(
        tmp_path: Path, line: str, fired: str | None) -> None:
    fake = _names(tmp_path)
    fake.fired_entry = "BPIF stale"
    fake.rows = [{"index": "0A", "entry": "BPIF AX==1"}]
    rs.take_run_state(cast(ds.Session, fake), True, [line])
    assert fake.fired_entry == fired and cast(Any, fake).frames == 3


def test_a_registerpoint_declared_while_running_is_armed_at_the_next_stop_and_cleared_queued(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = True
    server.resume()
    fake.running, fake.halted = True, False
    queued = server.regpoint_add(condition="DX==3DA")
    assert queued["state"] == "pending" and fake.rows == [], queued
    fake.running, fake.halted = False, True
    stop = server.resume()
    assert stop["applied_on_stop"]["armed"] == ["DX==3DA"], stop["applied_on_stop"]
    assert [r["entry"] for r in fake.rows] == ["BPIF DX==3DA"]
    server.resume()
    fake.running, fake.halted = True, False
    cleared = server.declaration_clear("regpoint", ref="DX==3DA")
    assert cleared["pending_disarm"] == ["DX==3DA"], cleared
    fake.running, fake.halted = False, True
    stop = server.resume()
    assert stop["applied_on_stop"]["disarmed"] == ["BPIF DX==3DA"] and fake.rows == [], stop


def test_a_registerpoint_is_cleared_by_any_spelling_regpoint_add_takes(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    server.regpoint_add(condition="AX==13")
    unknown = server.declaration_clear("regpoint", ref="AX==14")
    assert unknown["status"] == "INVALID" and "regpoint" in str(unknown["message"]) \
        and "watch" not in str(unknown["message"]), unknown
    cleared = server.declaration_clear("regpoint", ref="ax == 0x13")
    assert cleared["declarations_cleared"] == 1 and fake.rows == [], cleared


def test_a_registerpoint_the_debugger_refused_is_not_kept(tmp_path: Path) -> None:
    fake = _names(tmp_path)

    def refuse(row: str) -> str:
        raise ds.Invalid("unexpected_answer", "no BPIF row came back")

    fake.condition_breakpoint = refuse  # type: ignore[method-assign]
    assert server.regpoint_add(condition="AX==1")["status"] == "INVALID"
    assert server.declaration_list("regpoint")["regpoints"] == []


def test_a_build_without_bpif_refuses_a_registerpoint_naming_it(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.commands = frozenset(c for c in fake.commands if c != "BPIF")
    got = server.regpoint_add(condition="AX==1")
    assert got["status"] == "INVALID" and got["code"] == "no_channel" and "BPIF" in str(
        got["message"]), got


def test_every_tool_declares_a_title_and_the_readers_a_read_only_hint() -> None:
    """`title` is what the client shows; `readOnlyHint` is what lets it run readers in parallel."""
    tools = {t.name: t for t in server.mcp._tool_manager.list_tools()}
    untitled = sorted(n for n, t in tools.items() if not t.title)
    assert not untitled, f"tools with no title: {untitled}"
    read_only = {n for n, t in tools.items()
                 if t.annotations is not None and t.annotations.read_only_hint}
    # EQUALITY, not containment: a new tool wrongly marked read-only must break this line,
    # and a hand-kept list of writers would not see a tool absent from both lists. The
    # readers keep the hint although the first contact after a stop applies pending
    # declarations: that write is the declaring call's, not the reader's (owner's call).
    assert read_only == {"status", "log", "log_wait", "registers", "read_memory", "find",
                         "disassemble", "call_stack",
                         "symbols_find",
                         "declaration_list", "captures", "build_check", "state_list",
                         "comment_list", "screen_signature", "screen_map_find", "guest_file",
                         "audio_compare"}, read_only


def test_breakpoint_clear_by_ref_takes_the_family_without_touching_watches(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T")]
    fake = _names(tmp_path, symbols=syms)
    server.breakpoint_at(ref="_uicue_apply")
    server.breakpoint_interrupt(number=0x21)
    server.watch_add(ref="00AF:0100", mode="change", length=4)
    cleared = server.declaration_clear("breakpoint", all=True)
    assert cleared["declarations_cleared"] == 2                  # bp + interrupt, not watch
    kinds = sorted(d.kind for d in dstate.STATE.store.declarations())  # type: ignore[union-attr]
    assert kinds == ["watch"], kinds
    assert any(r["entry"].startswith("BPPM") or r["entry"].startswith("BPMEM")
               for r in fake.rows), fake.rows


def test_breakpoint_at_an_ambiguous_name_is_refused_and_stores_nothing(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("dup", 0x1000, kind="t"), dsym.Symbol("dup", 0x2000, kind="t")]
    _names(tmp_path, symbols=syms)
    got = server.breakpoint_at(ref="dup")
    assert got["status"] == "INVALID" and "names 2 symbols" in str(got["message"])
    assert got["code"] == "ambiguous_ref", "the code the other server gives the same refusal"
    assert "(0x1000, 0x2000)" in str(got["message"]), "each candidate's address, the file's order"
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_a_watch_through_a_pointer_whose_base_name_is_ambiguous_is_refused_as_ambiguous(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("dup", 0x1000, kind="d"), dsym.Symbol("dup", 0x2000, kind="d")]
    _names(tmp_path, symbols=syms)
    got = server.watch_add(ref="[dup]+0x4", mode="change", length=2)
    assert got["status"] == "INVALID" and got["code"] == "ambiguous_ref", got
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_breakpoint_at_an_unresolved_name_is_kept_not_armed(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")])
    got = server.breakpoint_at(ref="ensure_soundfont")
    assert got["status"] == "ok" and got["armed"] is False
    assert got["state"] == "unresolved"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["ensure_soundfont"]  # type: ignore[union-attr]


def test_breakpoint_list_shows_armed_unresolved_and_foreign(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")            # armed
    server.breakpoint_at(ref="gone_symbol")      # unresolved
    fake.rows.append({"index": "09", "entry": "BP F000:E05B"})   # a foreign leftover
    got = server.declaration_list("breakpoint")
    states = {b["ref"]: b["state"] for b in got["breakpoints"]}
    assert states == {"_main": "armed", "gone_symbol": "unresolved"}
    assert got["foreign"] == {"breakpoints": ["BP F000:E05B"]}


def test_breakpoint_clear_disarms_only_its_own_and_leaves_the_foreign(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")
    fake.rows.append({"index": "09", "entry": "BP F000:E05B"})    # foreign
    got = server.declaration_clear("breakpoint", all=True)
    assert got["declarations_cleared"] == 1
    assert got["disarmed"] == ["BP 00A7:16DD80"]
    assert {r["entry"] for r in fake.rows} == {"BP F000:E05B"}    # the foreign one stays
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_symbols_load_rearms_a_declaration_at_its_new_address(tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    # declare while unresolved (no table yet loaded through symbols_load)
    server.breakpoint_at(ref="_main")
    assert fake.rows == [], "nothing to arm against before a table is loaded"
    got = server.symbols_load(path=str(nm), base="400000")
    assert got["status"] == "ok"
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"]
    assert any(r["entry"] == "BP 00A7:16DD80" for r in fake.rows)


def test_watch_add_refuses_show_and_change_on_one_address(tmp_path: Path) -> None:
    """One address may not be both a show and a change watch."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    r = server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    assert r["status"] == "ok" and r["armed"] is False
    clash = server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    assert clash["status"] == "INVALID" and "both a show AND a change watch" in str(
        clash["message"])


def test_a_protected_mode_change_watch_carries_the_paging_caveat(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], mode="Pr32")
    got = server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is True
    assert "paging host" in str(got["caveat"])


def test_watch_list_matches_a_watch_despite_its_trailing_hit_count(tmp_path: Path) -> None:
    """A memory-watch BPLIST row carries a `(00)` hit count a code breakpoint's does not."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], mode="Pr32")
    server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    got = server.declaration_list("watch")
    row = next(w for w in got["watches"] if w["ref"] == "g_rate")
    assert row["state"] == "armed", got
    assert row["length"] == 4 and "width" not in row, "the list speaks watch_add's word"
    assert "foreign" not in got, got


def test_breakpoint_at_by_address_parses_the_seg_off(tmp_path: Path) -> None:
    _names(tmp_path)
    got = server.breakpoint_at(ref="00A7:16DD80")
    assert got["status"] == "ok" and got["by"] == "address" and got["armed"] is True
    assert got["entry"] == "BP 00A7:16DD80"


def test_breakpoint_at_stores_but_reports_unarmed_when_arming_fails(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    fake.arm_fails = True
    got = server.breakpoint_at(ref="_main")
    assert got["status"] == "ok" and got["armed"] is False and got["state"] == "unarmable"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["_main"]  # type: ignore[union-attr]


def test_breakpoint_list_reports_gone_when_the_debugger_no_longer_holds_it(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")
    fake.rows.clear()          # the debugger lost it (a close, or a hand BPDEL)
    got = server.declaration_list("breakpoint")
    assert got["breakpoints"][0]["state"] == "gone"


def test_breakpoint_list_reports_an_ambiguous_declaration_without_crashing(
        tmp_path: Path) -> None:
    _names(tmp_path)
    dstate.STATE.store.add(dec.Declaration("breakpoint", "symbol", "dup"))   # type: ignore[union-attr]
    dstate.STATE.install_table([dsym.Symbol("dup", 0x1000, kind="t"),
                        dsym.Symbol("dup", 0x2000, kind="t")])
    got = server.declaration_list("breakpoint")
    assert got["breakpoints"][0]["state"] == "ambiguous"


def test_watch_add_read_mode_stores_and_arms_nothing(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    got = server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is False and got["mode"] == "show"
    assert fake.rows == [], "a show watch must arm nothing"
    # dec 12, one word per concept: the state `watch_add` gives a placed show watch is
    # the SAME word `declaration_list(kind="watch")` and a stop's `watches` give it: a word per tool
    # would make
    # the identical watch report two different states.
    assert got["state"] == "evaluated"
    lst = server.declaration_list("watch")
    assert lst["watches"][0]["state"] == "evaluated"


def test_watch_add_an_unresolved_change_is_kept_not_refused(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("other", 0x1000, kind="d")])
    got = server.watch_add(ref="g_gone", mode="change", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is False and got["state"] == "unresolved"
    assert "g_gone" in [d.ref for d in dstate.STATE.store.declarations()]  # type: ignore[union-attr]


def test_watch_clear_disarms_change_and_leaves_read_alone(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")     # arms nothing
    server.watch_add(ref="0040:006C", mode="change", length=4)          # arms a BPPM row
    got = server.declaration_clear("watch", all=True)
    assert got["declarations_cleared"] == 2
    assert got["disarmed"], "the change-watch's entry should have been removed"
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_rearm_counts_unresolved_and_ambiguous(tmp_path: Path) -> None:
    nm = tmp_path / "s.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    _names(tmp_path)
    server.breakpoint_at(ref="_main")          # will resolve once loaded
    server.breakpoint_at(ref="_gone")          # stays unresolved
    got = server.symbols_load(path=str(nm), base="400000")
    assert [r["ref"] for r in got["declarations"]["unresolved"]] == ["_gone"]
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"]


def test_breakpoint_list_tells_unarmable_from_ambiguous_from_unresolved(
        tmp_path: Path) -> None:
    """The three non-armed states are DISTINCT and must not collapse."""
    dup = [dsym.Symbol("twice", 0x100, kind="T"), dsym.Symbol("twice", 0x200, kind="T")]
    one = dsym.Symbol("once", 0x300, kind="T")
    _names(tmp_path, symbols=[*dup, one], mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})   # sectioned: no flat base
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "symbol", "once"))
    st.add(dec.Declaration("breakpoint", "symbol", "twice"))
    st.add(dec.Declaration("breakpoint", "symbol", "absent"))
    listed = server.declaration_list("breakpoint")
    states = {b["ref"]: b["state"] for b in listed["breakpoints"]}
    assert states == {"once": "unarmable", "twice": "ambiguous", "absent": "unresolved"}


def test_watch_held_matches_by_value_across_widths_and_never_a_code_bp() -> None:
    rows = [{"index": "00", "entry": "BPPM 00AF:6024 (00)"},        # narrow width
            {"index": "01", "entry": "BP 00AF:00006024"}]           # a code BP, same addr
    hit = arming.watch_held(rows, 0xAF, 0x6024)
    assert hit is not None and hit["index"] == "00"                 # the watch, not the BP
    assert arming.watch_held(rows, 0xAF, 0x9999) is None


def test_watch_clear_reports_disarmed_only_after_reading_the_removal_back(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`disarmed` is the machine's answer read back, not a claim that a BPDEL must have taken."""
    fake = _names(tmp_path)
    server.watch_add(ref="0040:006C", mode="change", length=4)     # arms a BPPM row
    monkeypatch.setattr(fake, "command", lambda *_a, **_k: "")    # BPDEL is a no-op now
    got = server.declaration_clear("watch", all=True)
    assert got["declarations_cleared"] == 1
    assert got["disarmed"] == [], "the watch was NOT gone from the list, so not disarmed"


def test_start_refuses_a_corrupt_declaration_file_before_launching(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "state"
    (state / "dosbox-x-debug").mkdir(parents=True)
    (state / "dosbox-x-debug" / "declarations.json").write_text(
        '["not a mapping"]', encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    stub_build(monkeypatch)

    def no_session(*_a: object, **_k: object) -> object:
        raise AssertionError("ds.Session must not be built when the store is corrupt")
    monkeypatch.setattr(ds, "Session", no_session)
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=1))
    assert got["status"] == "INVALID" and "not a mapping" in got["message"]
    assert dstate.STATE.session is None, "no session may be left behind by a refused start"


def test_breakpoint_at_a_symbol_with_no_flat_base_is_stored_unarmed(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_x", 0x100, kind="T")], mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})
    got = cast(dict[str, Any], server.breakpoint_at(ref="_x"))
    assert got["stored"] is True and got["armed"] is False and got["state"] == "unarmable"
    assert "FLAT base" in got["why"]


def test_rearm_counts_ambiguous_and_unarmable_apart(tmp_path: Path) -> None:
    dup = [dsym.Symbol("dup", 0x1, kind="T"), dsym.Symbol("dup", 0x2, kind="T")]
    _names(tmp_path, symbols=[*dup, dsym.Symbol("one", 0x3, kind="T")], mode="Real")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "symbol", "one"))
    st.add(dec.Declaration("breakpoint", "symbol", "dup"))
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})
    got = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert {k: [r["ref"] for r in v] for k, v in got.items()} == {
        "rearmed": [], "stale": [], "unresolved": [], "ambiguous": ["dup"], "unarmable": ["one"]}
    assert all(r["why"] for r in (*got["ambiguous"], *got["unarmable"])), got


def test_watch_flows_in_real_mode_arm_list_and_clear(tmp_path: Path) -> None:
    _names(tmp_path, mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0x7DF0, "limit": -1, "type": -1})
    w = cast(dict[str, Any], server.watch_add(ref="0100:0200", mode="change", length=4))
    assert w["armed"] is True
    lst = cast(dict[str, Any], server.declaration_list("watch"))
    assert lst["watches"][0]["state"] == "armed"
    assert str(lst["watches"][0]["entry"]).startswith("BPMEM ")
    cl = cast(dict[str, Any], server.declaration_clear("watch", all=True))
    assert cl["disarmed"]
    assert cast(dict[str, Any], server.declaration_list("watch"))["watches"] == []


def test_watch_list_reports_gone_and_foreign(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0, "limit": -1, "type": -1})
    server.watch_add(ref="0100:0200", mode="change", length=4)          # armed
    fake.rows.append({"index": "09", "entry": "BPMEM 0300:0400 (00)"})  # foreign
    fake.rows = [r for r in fake.rows if not r["entry"].startswith("BPMEM 0100")]  # gone
    lst = cast(dict[str, Any], server.declaration_list("watch"))
    states = {w["ref"]: w["state"] for w in lst["watches"]}
    assert states["0100:0200"] == "gone"
    assert "BPMEM 0300:0400 (00)" in lst["foreign"]["watches"]


def test_watch_list_states_unresolved_and_ambiguous(tmp_path: Path) -> None:
    dup = [dsym.Symbol("two", 0x1, kind="d"), dsym.Symbol("two", 0x2, kind="d")]
    _names(tmp_path, symbols=dup)
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "two", width=4, fmt="u32", watch_mode="change"))
    st.add(dec.Declaration("watch", "symbol", "gone", width=4, fmt="u32", watch_mode="show"))
    lst = cast(dict[str, Any], server.declaration_list("watch"))
    states = {w["ref"]: w["state"] for w in lst["watches"]}
    assert states["two"] == "ambiguous" and states["gone"] == "unresolved"


def test_watch_add_change_that_cannot_arm_is_kept_unarmed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_x", 0x1000, kind="d")])

    def boom(**_k: object) -> dict[str, object]:
        raise ds.Invalid("not_stopped", "the machine is running; nothing was armed")
    monkeypatch.setattr(fake, "watch", boom)
    got = cast(dict[str, Any], server.watch_add(ref="g_x", mode="change", length=4))
    assert got["armed"] is False and got["state"] == "unarmable"


def test_watch_clear_skips_an_unresolvable_change_and_still_clears_the_store(
        tmp_path: Path) -> None:
    _names(tmp_path, symbols=[])          # empty table: the name will not resolve
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "gone", width=4, fmt="u32",
                           watch_mode="change"))
    got = cast(dict[str, Any], server.declaration_clear("watch", all=True))
    assert got["declarations_cleared"] == 1 and got["disarmed"] == []


def test_render_watch_reads_the_bytes_as_little_endian_values() -> None:
    import struct as _s
    assert arming.render_watch(bytes([0x78, 0x56, 0x34, 0x12]), 4, "u32") == 0x12345678
    assert arming.render_watch(bytes([0xFF, 0xFF, 0xFF, 0xFF]), 4, "i32") == -1
    assert arming.render_watch(_s.pack("<f", 1.5), 4, "f32") == 1.5
    assert arming.render_watch(bytes([1, 0, 2, 0]), 4, "u16") == [1, 2]     # two of them
    assert arming.render_watch(bytes([1, 2, 3, 4]), 4, "u8") == [1, 2, 3, 4]
    assert arming.render_watch(bytes([0x2A]), 1, "u8") == 0x2A
    assert arming.render_watch(bytes([1, 0, 2, 0]), 0, "u16[2]") == [1, 2]
    assert arming.render_watch(b"RE\0\0\xfe\xff", 0, "{name:char[4],x:i16}") == {
        "name": "RE", "x": -2}


def test_evaluate_watches_reads_read_mode_together_and_bytes_for_a_struct(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[
        dsym.Symbol("g_eng_rate", 0x1000, kind="d"),
        dsym.Symbol("g_eng_samples_tick", 0x1004, kind="d"),
        dsym.Symbol("g_bufsamp", 0x1008, kind="d"),
        dsym.Symbol("g_cue", 0x2000, kind="d"),
    ], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (44100).to_bytes(4, "little")
    fake.mem[(0xAF, 0x1004)] = (735).to_bytes(4, "little")
    fake.mem[(0xAF, 0x1008)] = (512).to_bytes(4, "little")
    fake.mem[(0xAF, 0x2000)] = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    st = dstate.STATE.store
    assert st is not None
    for name in ("g_eng_rate", "g_eng_samples_tick", "g_bufsamp"):
        st.add(dec.Declaration("watch", "symbol", name, width=4, fmt="u32",
                               watch_mode="show"))
    st.add(dec.Declaration("watch", "symbol", "g_cue", width=8, fmt="u8",
                           watch_mode="show"))
    out = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    by = {w["ref"]: w for w in out}
    assert by["g_eng_rate"]["value"] == 44100 and by["g_eng_rate"]["state"] == "evaluated"
    assert by["g_eng_samples_tick"]["value"] == 735
    assert by["g_bufsamp"]["value"] == 512
    assert by["g_cue"]["value"] == [1, 2, 3, 4, 5, 6, 7, 8]   # bytes, no fields (R5)
    assert by["g_cue"]["bytes"] == "0102030405060708"


def test_evaluate_watches_reads_a_change_watch_s_value_beside_its_state(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_x", 0x1000, kind="d")], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (7).to_bytes(4, "little")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "g_x", width=4, fmt="u32",
                           watch_mode="change"))
    st.add(dec.Declaration("watch", "symbol", "g_absent", width=4, fmt="u32",
                           watch_mode="show"))
    by = {w["ref"]: w for w in arming.evaluate_watches(fake)}  # type: ignore[arg-type]
    assert by["g_x"]["value"] == arming.render_watch((7).to_bytes(4, "little"), 4, "u32"), by
    assert by["g_x"]["bytes"] == "07000000" and "note" not in by["g_x"], by
    assert by["g_absent"]["state"] == "unresolved" and "value" not in by["g_absent"]


def test_stop_reply_carries_registers_watches_cause_and_the_e9_block(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x1000, kind="d")], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (48000).to_bytes(4, "little")
    fake.log = ["boot", "rate=48000", "tick"]
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32",
                           watch_mode="show"))
    out = running.stop_reply(fake, halted=True)  # type: ignore[arg-type]
    assert out["status"] == "ok" and out["halted"] is True
    assert out["regs"]["CS"] == "0x00a7" and out["regs"]["DS"] == "0x00af"
    assert out["watches"][0]["value"] == 48000 and out["watches"][0]["state"] == "evaluated"
    assert out["cause"].startswith("no declared code breakpoint")  # nothing declared at CS:EIP
    assert out["e9"]["lines_total"] == 3 and out["e9"]["truncated"] is False, out["e9"]


def test_attribution_names_a_breakpoint_at_the_stop_or_says_it_cannot(tmp_path: Path) -> None:
    """Attribution is by ADDRESS COMPARISON."""
    fake = _names(tmp_path)
    fake.cs, fake.eip = "00A7", "00001A27"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "00A7:00001A27"))
    st.add(dec.Declaration("breakpoint", "address", "00A7:00009999"))
    held = [{"index": "0", "entry": "BP 00A7:00001A27"}, {"index": "1", "entry": "BP 00A7:9999"}]
    hit = arming.attribute_stop(fake, where=fake.where(), held=held)  # type: ignore[arg-type]
    assert hit["attributed"] is True and hit["ref"] == "00A7:00001A27"
    fake.eip = "00005555"
    miss = arming.attribute_stop(fake, where=fake.where(), held=held)  # type: ignore[arg-type]
    assert miss["attributed"] is False and "no hit flag" in miss["why"]


def test_a_stop_names_no_declaration_the_debugger_holds_no_row_for(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.cs, fake.eip = "00A7", "00001A27"
    store = dstate.STATE.store
    assert store is not None
    store.add(dec.Declaration("breakpoint", "address", "00A7:00001A27"))
    unheld = running.stop_reply(fake)  # type: ignore[arg-type]
    assert not unheld["cause"].startswith("breakpoint"), unheld["cause"]
    fake.rows.append({"index": "0", "entry": "BPPM 00A7:00001A27 (00)"})   # a watch row there
    watched = running.stop_reply(fake)  # type: ignore[arg-type]
    assert not watched["cause"].startswith("breakpoint"), watched["cause"]
    fake.rows.clear()
    fake.rows.append({"index": "0", "entry": "BP 00A7:00001A27"})
    held = running.stop_reply(fake)  # type: ignore[arg-type]
    assert held["cause"].startswith("breakpoint 00A7:00001A27"), held["cause"]


def test_a_cancelled_calls_stop_names_the_cancel_unless_a_declaration_is_there(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.cs, fake.eip = "00A7", "00001A27"
    got = running.stop_reply(fake, asked_by="cancel")  # type: ignore[arg-type]
    assert got["cause"] == "a cancelled call's stop at 00A7:00001A27", got["cause"]
    assert dstate.cause_key(got["cause"]) == "a cancelled call's stop"
    store = dstate.STATE.store
    assert store is not None
    store.add(dec.Declaration("breakpoint", "address", "00A7:00001A27"))
    fake.rows.append({"index": "0", "entry": "BP 00A7:00001A27"})
    named = running.stop_reply(fake, asked_by="cancel")  # type: ignore[arg-type]
    assert named["cause"].startswith("breakpoint 00A7:00001A27"), named["cause"]


def test_evaluate_watches_skips_a_breakpoint_and_reports_why_and_unreadable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dup = [dsym.Symbol("two", 0x1, kind="d"), dsym.Symbol("two", 0x2, kind="d")]
    fake = _names(tmp_path, symbols=[*dup, dsym.Symbol("ok", 0x1000, kind="d")], ds_="00AF")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "00A7:0010"))          # skipped
    st.add(dec.Declaration("watch", "symbol", "two", width=4, fmt="u32",
                           watch_mode="show"))                             # ambiguous + why
    st.add(dec.Declaration("watch", "symbol", "ok", width=4, fmt="u32",
                           watch_mode="show"))                             # unreadable

    def boom(_s: int, _o: int, _n: int, mode: str | None = None) -> bytes:
        raise ds.Invalid("unexpected_answer", "the data view did not come back")
    monkeypatch.setattr(fake, "read_bytes", boom)
    by = {w["ref"]: w for w in arming.evaluate_watches(fake)}  # type: ignore[arg-type]
    assert set(by) == {"two", "ok"}                            # the breakpoint is not listed
    assert by["two"]["state"] == "ambiguous" and "why" in by["two"]
    assert by["ok"]["state"] == "unreadable" and "did not come back" in by["ok"]["why"]


def test_a_show_watch_on_bytes_a_change_watch_covers_is_read_as_any_other(tmp_path: Path) -> None:
    fake = _names(tmp_path, ds_="00AF")
    fake.rows.append({"index": "00", "entry": "BPPM 00AF:00006024 (00)"})   # armed elsewhere
    fake.mem[(0xAF, 0x6024)] = (999).to_bytes(4, "little")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "address", "00AF:00006024", width=4, fmt="u32",
                           watch_mode="show"))
    w = arming.evaluate_watches(fake)[0]  # type: ignore[arg-type]
    assert w["state"] == "evaluated" and w["bytes"] == (999).to_bytes(4, "little").hex(), w


def test_a_read_watch_wider_than_128_bytes_is_refused_at_declaration(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.watch_add(ref="0040:0000", mode="show", length=256,
                                                fmt="u8"))
    assert got["status"] == "INVALID" and "region" in got["message"]


# ----------------------------------------------------- the ref you clear with

def test_every_declaration_reply_carries_the_ref_that_clears_it(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    armed = server.breakpoint_interrupt(number=0x21, ah=0x4B)
    assert armed["ref"] == "BPINT 21 AH=4B", armed
    assert [r["entry"] for r in fake.rows] == ["BPINT 21 AH=4B"]
    cleared = server.declaration_clear("breakpoint", ref=armed["ref"])
    assert cleared["status"] == "ok" and cleared["declarations_cleared"] == 1, cleared
    assert fake.rows == []
    watched = server.watch_add(ref="_g_state", mode="show", length=4)
    assert watched["ref"] == "_g_state", watched
    assert server.declaration_clear("watch", ref=watched["ref"])["declarations_cleared"] == 1


# ------------------------------------------- stale raw addresses across sessions

def test_symbols_load_leaves_another_builds_raw_address_stale_and_names_what_it_rearmed(
        tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s1"
    dstate.STATE.conf_fingerprint = "conf-of-an-older-build"
    server.breakpoint_at(ref="00A7:5C6F0")
    server.breakpoint_at(ref="_main")
    # A NEW SESSION over a REBUILT program: the emulator's own list starts empty, the origin
    # changes, and the map loaded below fingerprints a different build.
    fake.rows.clear()
    dstate.STATE.session_origin = "s2"
    dstate.STATE.conf_fingerprint = dlaunch.fingerprint(fake.launch.conf)
    got = server.symbols_load(path=str(nm), base="400000")
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"], got["declarations"]
    assert [r["ref"] for r in got["declarations"]["stale"]] == ["00A7:5C6F0"], \
        got["declarations"]
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:16DD80"], fake.rows
    listed = {b["ref"]: b for b in server.declaration_list("breakpoint")["breakpoints"]}
    assert listed["00A7:5C6F0"]["state"] == "stale", listed
    assert listed["00A7:5C6F0"]["origin"] == "s1" and listed["00A7:5C6F0"]["created_at"]
    assert listed["_main"]["state"] == "armed" and listed["_main"]["origin"] == "s1"
    # ADOPTION: declaring the same raw address in s2 arms it and moves its origin here.
    adopted = server.breakpoint_at(ref="00A7:5C6F0")
    assert adopted.get("already_stored", False) is True and adopted["armed"] is True, adopted
    row = next(b for b in server.declaration_list("breakpoint")["breakpoints"]
               if b["ref"] == "00A7:5C6F0")
    assert row["state"] == "armed" and row["origin"] == "s2", row


def test_start_re_arms_a_raw_address_left_over_the_same_build_and_not_another_builds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapf = tmp_path / "prog.map"
    mapf.write_text("0016dd80 T _main\n", encoding="utf-8")
    (tmp_path / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    over_map = build_of((tmp_path / "g.conf").resolve(), mapf.read_text(encoding="utf-8"))
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {
        "00A7:0100": None, "00A7:0200": "fp-of-another-build", "00A7:0300": over_map})
    assert got["status"] == "ok", got
    assert [r["entry"] for r in booted.rows] == ["BP 00A7:0100"], booted.rows
    listed = server.declaration_list("breakpoint")
    assert listed["debugger_read"] is True, listed
    rows = {b["ref"]: b for b in listed["breakpoints"]}
    assert rows["00A7:0100"]["state"] == "armed", rows
    assert rows["00A7:0200"]["state"] == "stale", rows
    assert rows["00A7:0300"]["state"] == "stale", rows


def test_a_re_arm_at_start_that_cannot_read_the_list_is_said_not_fatal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class CutList(_Booted):
        def breakpoints(self) -> list[dict[str, str]]:
            raise ds.Invalid("unexpected_answer", "no BPLIST header came back")

    got, _ = _start_over_a_store(tmp_path, monkeypatch, {"00A7:0100": None}, CutList,
                                 regpoints=("AX==13",))
    assert got["status"] == "ok", got
    assert "no BPLIST header" in got["rearm_refused"], got
    rearm = got["declarations"]["rearm"]
    assert rearm["stale"] == [] and [r["ref"] for r in rearm["unarmable"]] == [
        "00A7:0100", "AX==13"], rearm
    assert "no BPLIST header" in rearm["unarmable"][0]["why"], rearm
    assert dstate.STATE.session is not None
    assert [d.ref for d in dstate.STATE.store.declarations()] == [  # type: ignore[union-attr]
        "00A7:0100", "AX==13"]


def test_start_arms_a_stored_registerpoint_again(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A condition names no address, so no build makes it stale: `start` arms it as it parks."""
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, regpoints=("AX==13",))
    assert got["status"] == "ok", got
    assert [r["entry"] for r in booted.rows] == ["BPIF AX==13"], booted.rows
    listed = server.declaration_list("regpoint")["regpoints"]
    assert [(g["ref"], g["state"]) for g in listed] == [("AX==13", "armed")], listed


def test_start_with_nothing_to_re_arm_does_not_read_the_list(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got, booted = _start_over_a_store(tmp_path, monkeypatch,
                                      {"00A7:0200": "fp-of-another-build"})
    assert got["status"] == "ok" and "rearm_refused" not in got, got
    assert booted.bp_calls == 0, booted.bp_calls


def test_a_start_lists_an_unresolved_name_with_what_would_place_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A name no table loaded in this session resolves is kept for the next build; the row has
    to say so, or `unresolved` reads as this build having lost the symbol."""
    got, _ = _start_over_a_store(tmp_path, monkeypatch, {}, regpoints=("AX==13",),
                                 symbols=("_engine_pos",))
    rows = got["declarations"]["rearm"]["unresolved"]
    assert [r["ref"] for r in rows] == ["_engine_pos"], got["declarations"]
    assert "symbols_load" in rows[0]["why"], rows[0]
    assert rows[0]["inherited"] is True, rows[0]


def test_start_answers_each_stored_breakpoint_as_a_row_saying_whose_and_how_old(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got, _ = _start_over_a_store(tmp_path, monkeypatch, {
        "00A7:0100": None, "00A7:0200": "fp-of-another-build"})
    rearm = got["declarations"]["rearm"]
    assert {k: [r["ref"] for r in v] for k, v in rearm.items()} == {
        "rearmed": ["00A7:0100"], "stale": ["00A7:0200"], "unresolved": [], "ambiguous": [],
        "unarmable": []}, rearm
    for row in (*rearm["rearmed"], *rearm["stale"]):
        assert row["origin"] == "s1" and row["inherited"] is True, row
        assert row["cpu"] == contract.unavailable(arming.ONE_CPU_WHY), row
        assert row["age_s"] == contract.unavailable(declaration_rows.UNDATED_WHY), "t0 is no date"
    dstate.STATE.session = None
    (tmp_path / "again").mkdir()
    got, booted = _start_over_a_store(tmp_path / "again", monkeypatch,
                                      {"00A7:0200": "fp-of-another-build"})
    assert [r["ref"] for r in got["declarations"]["rearm"]["stale"]] == ["00A7:0200"], got
    assert booted.bp_calls == 0, booted.bp_calls



# --------------------------------------------------------- an orphan says so

def test_a_declaration_from_a_store_that_kept_no_origin_is_listed_as_an_orphan(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    dstate.STATE.session_origin = "s2"
    store = dstate.STATE.store
    assert store is not None
    store.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32", watch_mode="show"))
    store.add(dec.Declaration("breakpoint", "address", "00A7:0100", cpu_mode="protected"))
    store.add(dec.Declaration("interrupt", "address", "BPINT 21"))
    watches = server.declaration_list("watch")["watches"]
    assert watches[0]["state"] == "orphan" and "EVALUATED" in watches[0]["why"], watches
    bps = {b["ref"]: b for b in server.declaration_list("breakpoint")["breakpoints"]}
    assert bps["00A7:0100"]["state"] == "orphan" and bps["BPINT 21"]["state"] == "orphan", bps
    assert bps["00A7:0100"]["orphan"] is True and "EVALUATED" not in bps["00A7:0100"]["why"]
    # THE STOP REPLY SAYS IT TOO: the orphan show watch is evaluated, flagged as nobody's.
    fake.halted = True
    stop = server.resume()
    assert stop["watches"][0]["state"] == "evaluated" and stop["watches"][0]["orphan"] is True, stop
    # HELD WINS, AND AN UNRESOLVED NAME STAYS UNRESOLVED: an orphan the debugger holds is
    # `armed` (and its row is NOT foreign), an orphan symbol this build lacks is `unresolved`
    # -- the facts a caller acts on, with `orphan: true` beside them.
    store.add(dec.Declaration("breakpoint", "symbol", "g_rate"))
    store.add(dec.Declaration("breakpoint", "symbol", "nope"))
    fake.rows.append({"index": "00", "entry": "BP 00A7:0017A6EC"})
    listed = server.declaration_list("breakpoint")
    bps = {b["ref"]: b for b in listed["breakpoints"]}
    assert bps["g_rate"]["state"] == "armed" and bps["g_rate"]["orphan"] is True, bps
    assert bps["nope"]["state"] == "unresolved" and bps["nope"]["orphan"] is True, bps
    assert "foreign" not in listed, listed
    store.add(dec.Declaration("watch", "address", "00A7:0200", width=4, fmt="u32",
                              watch_mode="change"))
    fake.rows.extend({"index": f"{1 + i:02d}", "entry": f"BPPM 00A7:{0x200 + i:08X} (00)"}
                     for i in range(4))                  # a row for each of its four bytes
    wl = server.declaration_list("watch")
    armed = next(w for w in wl["watches"] if w["ref"] == "00A7:0200")
    assert armed["state"] == "armed" and armed["orphan"] is True and "foreign" not in wl, wl
    fake.rows.clear()
    assert server.declaration_clear("breakpoint",
                                    all=True)["declarations_cleared"] == 4      # the watches stay
    assert sorted(w["ref"] for w in server.declaration_list("watch")["watches"]) == ["00A7:0200",
                                                                                     "g_rate"]
    assert server.declaration_clear("watch", all=True)["declarations_cleared"] == 2
    assert fake.rows == []


# ------------------------------------------- a stop reads the list once

def test_a_stop_reads_the_breakpoint_list_once_and_shares_it(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    fake.halted = True                   # the resume stops again at once
    fake.bp_calls = fake.survey_calls = 0
    got = server.resume()
    assert "stop_seq" in got and got["watches"][0]["state"] == "evaluated", got
    assert fake.survey_calls == 1, fake.survey_calls
    assert fake.bp_calls == 0, f"the stop re-read the list {fake.bp_calls} times"


def test_the_queue_covers_interrupts_and_change_watches_and_says_what_it_could_not_apply(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d"),
                                     dsym.Symbol("_gone", 0x3000, kind="T"),
                                     dsym.Symbol("_late", 0x4000, kind="T")])
    server.breakpoint_interrupt(number=0x21, ah=0x4B)
    server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    fake.halted = True
    server.resume()
    fake.running = True
    fake.halted = False
    bc = server.declaration_clear("breakpoint", ref="BPINT 21 AH=4B")
    assert bc.get("pending_disarm", []) == ["BPINT 21 AH=4B"]
    wc = server.declaration_clear("watch", ref="g_rate")
    assert wc.get("pending_disarm", []) and wc.get("pending_disarm",
                                                   [])[0].startswith("BPPM 00AF:0017A6EC"), wc
    assert server.breakpoint_at(ref="_gone")["state"] == "pending"
    assert server.breakpoint_at(ref="_late")["state"] == "pending"
    assert server.declaration_clear("breakpoint",
                                    ref="_gone")["declarations_cleared"] == 1   # before the stop
    dstate.STATE.install_table([dsym.Symbol("g_rate", 0x17A6EC, kind="d")])   # `_late` vanished
    fake.running = False
    fake.halted = True
    stop = server.resume()
    applied = stop["applied_on_stop"]
    assert applied["disarmed"][0] == "BPINT 21 AH=4B", applied
    assert applied["disarmed"][1].startswith("BPPM 00AF:0017A6EC"), applied
    assert applied["armed"] == [] and any("arm _late" in s for s in applied["still_pending"])
    assert fake.rows == [], fake.rows
    assert server.status()["pending"]["arm"] == ["_late"]


def test_two_refs_on_one_address_do_not_share_a_change_watch_in_silence(
        tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    first = server.watch_add(ref="g_rate", mode="change", length=4)
    assert first["status"] == "ok" and first["armed"] is True
    second = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert second["status"] == "INVALID" and "already armed under 'g_rate'" in str(
        second["message"])
    assert [d.ref for d in arming.current_store().declarations()] == ["g_rate"]


def test_an_aliased_change_watch_declared_while_running_stays_pending_and_says_why(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    first = server.watch_add(ref="g_rate", mode="change", length=4)
    assert first["armed"] is True
    fake.running = True
    fake.halted = False
    second = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert second["status"] == "INVALID" and "already armed under 'g_rate'" in str(
        second["message"])
    # Queued BEFORE the alias existed, aliased by the time the stop drains the queue.
    server.declaration_clear("watch", ref="g_rate")
    dstate.STATE.armed.clear()
    queued = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert queued["status"] == "ok" and queued["state"] == "pending", queued
    dstate.STATE.armed[("watch", "g_rate")] = [
        {"kind": "watch", "seg": 0xAF, "off": 0x17A6EC, "entry": "BPPM 00AF:0017A6EC"}]
    fake.running = False
    fake.halted = True
    stop = server.resume()
    still = stop["applied_on_stop"]["still_pending"]
    assert len(still) == 1 and "already armed under 'g_rate'" in still[0], still


def test_two_pending_declarations_on_one_address_arm_one_row_at_the_stop(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("bar", 0x100, kind="T")])
    fake.halted = True
    server.resume()                                   # stop 1, recorded
    store = dstate.STATE.store
    assert store is not None
    for name in ("foo", "bar"):
        store.add(dec.Declaration("breakpoint", "symbol", name, origin=dstate.STATE.session_origin))
        dstate.STATE.queue_arm(name)
    fake.running = True
    fake.running = False                              # the machine ran and stopped again
    fake.halted = True
    stop = server.resume()
    assert stop["applied_on_stop"]["armed"] == ["foo", "bar"]
    assert [r["entry"] for r in fake.rows].count("BP 00A7:0100") == 1, fake.rows


def test_one_breakpoint_row_is_one_declaration_and_an_old_store_is_attributed_whole(
        tmp_path: Path) -> None:
    """ONE ROW, ONE DECLARATION."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("bar", 0x100, kind="T")])
    assert server.breakpoint_at(ref="foo")["armed"] is True
    second = server.breakpoint_at(ref="00A7:0100")
    assert second["status"] == "INVALID" and "'foo'" in second["message"], second
    third = server.breakpoint_at(ref="bar")
    assert third["status"] == "INVALID" and "'foo'" in third["message"], third
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["foo"]  # type: ignore[union-attr]
    assert server.breakpoint_at(ref="foo").get("already_stored",
                                               False) is True, "a re-declaration adopts"
    # THE OLD STORE: both declarations already there, the stop at their address.
    dstate.STATE.store.add(dec.Declaration("breakpoint", "symbol", "bar",  # type: ignore[union-attr]
                                           origin=dstate.STATE.session_origin))
    fake.eip = "00000100"
    fake.halted = True
    stop = server.resume()
    assert stop["cause"].startswith("breakpoints foo, bar at ") and "every declaration" in \
        stop["cause"], stop["cause"]


def test_watch_add_refuses_an_ambiguous_name_and_stores_nothing(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("dup", 0x100, kind="T"),
                              dsym.Symbol("dup", 0x200, kind="T")])
    for mode in ("change", "show"):
        out = server.watch_add(ref="dup", mode=mode, length=4)
        assert out["status"] == "INVALID" and "names 2 symbols" in out["message"], out
    assert dstate.STATE.store.declarations() == []  # type: ignore[union-attr]


def test_a_declaring_reply_names_its_state_in_the_lists_own_words(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("var", 0x200, kind="D")])
    assert server.breakpoint_at(ref="foo")["state"] == "armed"
    assert server.watch_add(ref="var", mode="change", length=4)["state"] == "armed"
    assert server.watch_add(ref="var", mode="change", length=4)["state"] == "armed"
    failing = _names(tmp_path, symbols=[dsym.Symbol("bar", 0x300, kind="T")], arm_fails=True)
    got = server.breakpoint_at(ref="bar")
    assert got["armed"] is False and got["state"] == "unarmable", got
    del failing, fake


def test_a_headless_resume_with_nothing_declared_is_released(tmp_path: Path) -> None:
    _names(tmp_path, watched=False)
    released = cast(dict[str, Any], server.resume())
    assert released["status"] == "ok" and "stop_seq" not in released, released


def test_an_interrupt_breakpoint_from_another_session_does_not_count_as_a_stopper(
        tmp_path: Path) -> None:
    _names(tmp_path, watched=False)
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("interrupt", "address", "BPINT 21", origin="an-earlier-session"))
    assert arming.something_can_stop_it() is False
    server.breakpoint_interrupt(number=0x21)          # this session's own: armed
    assert arming.something_can_stop_it() is True


def test_watch_add_judges_the_mode_before_the_size(tmp_path: Path) -> None:
    _names(tmp_path)
    got = server.watch_add(ref="00AF:0100", mode="bogus")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "mode is one of" in got["message"], got["message"]
    step = server.perform(steps=[{"op": "watch_add", "ref": "00AF:0100", "mode": "bogus"}])
    assert step["code"] == "bad_argument" and "mode is one of" in step["message"], step


def test_a_breakpoint_left_armed_by_run_to_counts_as_a_stopper(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False)
    assert arming.something_can_stop_it() is False
    # THE ROW IS THE DEBUGGER'S: it sits in the list the next stop's survey reads, and in
    # the last stop's snapshot the server keeps for a running machine.
    fake.rows.append({"index": "00", "entry": "BP 00A7:5EA30"})
    dstate.STATE.last_stop["held"] = list(fake.rows)
    assert arming.something_can_stop_it() is True
    resumed = cast(dict[str, Any], server.resume())
    assert resumed["status"] == "ok", resumed


def test_every_tool_names_its_summary_and_declares_both_hints() -> None:
    served = dosbox_mcp.registered_tools()
    assert served and set(served) <= set(dosbox_mcp.BOUNDARY.summaries), sorted(
        set(served) - set(dosbox_mcp.BOUNDARY.summaries))
    for t in server.mcp._tool_manager.list_tools():
        hints = t.annotations
        assert hints is not None, t.name
        assert isinstance(hints.read_only_hint, bool), t.name
        assert hints.idempotent_hint is False, t.name


def test_status_counts_the_declarations_as_the_lists_list_them(tmp_path: Path) -> None:
    _names(tmp_path, mode="Real", cs="0749", ds_="0749")
    assert server.status()["declarations"] == {"breakpoints": 0, "watches": 0, "regpoints": 0}
    server.breakpoint_at(ref="0749:0010")
    server.breakpoint_interrupt(number=0x21)
    server.watch_add(ref="0749:0020", mode="show", length=2)
    got = cast(dict[str, Any], server.status())["declarations"]
    assert got == {"breakpoints": len(server.declaration_list("breakpoint")["breakpoints"]),
                   "watches": len(server.declaration_list("watch")["watches"]),
                   "regpoints": len(server.declaration_list("regpoint")["regpoints"])} == {
                       "breakpoints": 2, "watches": 1, "regpoints": 0}, got


def test_status_counts_the_declarations_on_a_running_machine_too(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real", cs="0749", ds_="0749")
    server.breakpoint_at(ref="0749:0010")
    fake.running = True
    got = cast(dict[str, Any], server.status())
    assert got["pc"]["available"] is False, got
    assert got["declarations"] == {"breakpoints": 1, "watches": 0, "regpoints": 0}, got


@pytest.mark.parametrize(("com", "waits_for"), [(False, "LINEUP.EXE"), (True, "LINEUP.COM")])
def test_status_says_which_program_a_held_start_table_waits_for(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, com: bool, waits_for: str) -> None:
    """A table that never matches costs a memory-chain read at every stop, silently otherwise."""
    _names(tmp_path, mode="Real", cs="0749", ds_="0749")
    assert "symbols_held" not in server.status()
    monkeypatch.setattr(dstate.STATE, "start_symbols",
                        start_symbols.Held(str(tmp_path / "lineup.map"), "program", com))
    got = cast(dict[str, Any], server.status())
    assert got["symbols_held"] == {"path": str(tmp_path / "lineup.map"), "base_from": "program",
                                   "waiting_for": waits_for}, got


def test_a_start_table_nothing_could_check_says_so_in_its_reply(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start(symbols=)` refuses a table its executable contradicts; a table with no executable
    beside it must not then read like one that was compared."""
    table = tmp_path / "LINEUP.SYM"
    table.write_text("00000100 T start\n", encoding="utf-8")
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, symbols=str(table))
    assert got["status"] == "ok", got
    checked = got["symbols"]["checked"]
    assert checked["available"] is False and "LINEUP.exe" in checked["why"], got["symbols"]


def test_a_start_table_with_its_executable_says_what_it_was_checked_against(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    guest = Path(__file__).resolve().parent / "guest"
    for name in ("dpmi.exe", "dpmi.sym"):
        (tmp_path / name).write_bytes((guest / name).read_bytes())
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, symbols=str(tmp_path / "dpmi.sym"))
    assert got["status"] == "ok", got
    assert str(got["symbols"]["checked"].get("against", "")).endswith("dpmi.exe"), got["symbols"]


@pytest.mark.parametrize(("shared", "said"), [(False, "headless"), (True, "shared")])
def test_starts_line_names_how_the_session_is_watched(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shared: bool, said: str) -> None:
    kw: dict[str, Any] = {"shared": True} if shared else {}
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, **kw)
    assert got["status"] == "ok" and got["summary"].startswith(f"start g.conf: {said} on "), got


def test_two_loads_queued_while_the_guest_runs_reach_the_debugger_together(
        tmp_path: Path) -> None:
    one, two = tmp_path / "one.nm", tmp_path / "two.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    two.write_text("00002000 T _second\n", encoding="utf-8")
    fake = _names(tmp_path)
    taken: list[str] = []

    def load(data: bytes) -> list[tuple[str, int]]:
        held = dsym.decode(data)
        taken.extend(name for name, _ in held)
        return held
    fake.load_symbols = load  # type: ignore[method-assign]
    fake.running, fake.halted = True, False
    for nm in (one, two):
        assert server.symbols_load(path=str(nm), base="400000")["pending"] is True
    assert {s.name for s in dstate.STATE.table} == {"_main", "_second"}
    fake.running, fake.halted = False, True
    assert server.resume()["applied_on_stop"]["symbols_loaded"] is True
    assert sorted(taken) == ["_main", "_second"], taken


def test_a_refused_load_leaves_the_batch_still_queued(tmp_path: Path) -> None:
    one, two = tmp_path / "one.nm", tmp_path / "two.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    two.write_text("00002000 T _second\n", encoding="utf-8")
    fake = _names(tmp_path)
    fake.running, fake.halted = True, False
    server.symbols_load(path=str(one), base="400000")
    queued = dstate.STATE.pending["load"]
    assert queued, "nothing was queued"
    fake.running, fake.halted = False, True

    def refused(data: bytes) -> list[tuple[str, int]]:
        raise ds.Invalid("unexpected_answer", "LV was not acknowledged")
    fake.load_symbols = refused  # type: ignore[method-assign]
    got = cast(dict[str, Any], server.symbols_load(path=str(two), base="400000"))
    assert got["status"] == "INVALID" and dstate.STATE.pending["load"] == queued, got


def test_a_load_at_a_stop_replaces_a_queued_batch_the_debugger_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    one = tmp_path / "one.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    fake.running, fake.halted = True, False
    server.symbols_load(path=str(one), base="500000")
    assert dstate.STATE.pending["load"], "nothing was queued"
    fake.running, fake.halted = False, True
    real = fake.load_symbols

    def refuses(data: bytes) -> Any:
        raise ds.Invalid("unexpected_answer", "the debugger refused the batch")
    monkeypatch.setattr(fake, "load_symbols", refuses)
    server.status()                                # the stop's drain: refused, kept queued
    assert dstate.STATE.pending["load"], "the refused batch was not kept"
    monkeypatch.setattr(fake, "load_symbols", real)
    got = cast(dict[str, Any], server.symbols_load(path=str(one), base="400000"))
    assert got["status"] == "ok" and dstate.STATE.pending["load"] is None, got


def test_a_breakpoint_and_a_change_watch_queued_at_one_ref_are_both_armed_at_the_stop(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True, mode="Real")
    server.status()
    fake.running = True
    w = server.watch_add(ref="0814:0100", mode="change", length=2)
    b = server.breakpoint_at(ref="0814:0100")
    assert w["state"] == "pending" and b["state"] == "pending", (w, b)
    fake.running = False
    st = server.status()
    assert st["applied_on_stop"]["armed"] == ["0814:0100"], st
    assert set(dstate.STATE.armed) == {("watch", "0814:0100"), ("bp", "0814:0100")}, \
        dstate.STATE.armed


def test_a_stored_declaration_follows_its_names_into_a_rebuilt_map(tmp_path: Path) -> None:
    old, new = tmp_path / "old.nm", tmp_path / "new.nm"
    old.write_text("0016dd80 T _main\n00200000 D g_rate\n", encoding="utf-8")
    new.write_text("0017ee90 T _main\n00210040 D g_rate\n", encoding="utf-8")
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s1"
    _ok(server.symbols_load(path=str(old), base="400000"))
    _ok(server.breakpoint_at(ref="_main"))
    _ok(server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32"))
    assert "BP 00A7:16DD80" in [r["entry"] for r in fake.rows], fake.rows
    fake.rows.clear()
    dstate.STATE.session_origin = "s2"
    got = _ok(server.symbols_load(path=str(new), base="400000"))
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"], got["declarations"]
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:17EE90"], fake.rows
    (bp,) = server.declaration_list("breakpoint")["breakpoints"]
    assert (bp["state"], bp["entry"]) == ("armed", "BP 00A7:17EE90"), bp
    store = dstate.STATE.store
    assert store is not None
    (watch,) = [d for d in store.declarations() if d.kind == "watch"]
    placed = placement.resolve_ref(watch, "DS", cast(ds.Session, fake))
    assert (placed["state"], placed["off"]) == ("armable", 0x210040), placed


def test_a_change_watch_that_cannot_be_placed_says_why_and_is_stored(tmp_path: Path) -> None:
    real = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x1000, kind="D")], mode="Real",
                  base=-1)
    got = server.watch_add(ref="g_rate", mode="change", length=2)
    assert got["status"] == "ok" and got["state"] == "unarmable", got
    assert "FLAT base" in got["why"] and real.rows == [], got
    none = server.watch_add(ref="g_absent", mode="change", length=2)
    assert none["state"] == "unresolved" and "build" not in none.get("note", ""), none


def test_a_load_leaves_a_breakpoint_the_debugger_holds_armed_and_out_of_its_account(
        tmp_path: Path) -> None:
    nm = tmp_path / "foo.nm"
    nm.write_text("00001000 T foo\n", encoding="utf-8")
    fake = _names(tmp_path, mode="Real")
    _ok(server.breakpoint_at(ref="0814:0100"))
    rows = list(fake.rows)
    assert rows, "the raw breakpoint was not armed"
    got = _ok(server.symbols_load(path=str(nm), base="400000"))
    assert not any(got["declarations"][b] for b in arming.REARM_BUCKETS), got["declarations"]
    assert fake.rows == rows, "the held row was touched"


def test_a_breakpoint_cleared_and_declared_again_while_a_load_waits_is_armed_at_the_stop(
        tmp_path: Path) -> None:
    fake, _ = _deferred_load_with(tmp_path, lambda: None)
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows
    fake.running = True
    _ok(server.symbols_load(path=str(tmp_path / "foo.nm"), base="400000"))
    _ok(server.declaration_clear("breakpoint", ref="foo"))
    _ok(server.breakpoint_at(ref="foo"))
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


def test_a_deferred_load_the_debuggers_list_cannot_hold_is_dropped_once(tmp_path: Path) -> None:
    fake, _ = _deferred_load_with(tmp_path, lambda: None)
    fake.vars_held = dsym.COUNT_MAX
    loads = getattr(fake, "loads", 0)
    fake.running = False
    applied = _ok(server.status())["applied_on_stop"]
    assert getattr(fake, "loads", 0) == loads, "the load was sent to the debugger"
    assert any(p.startswith("symbols_load, dropped:") for p in applied["still_pending"]), applied
    assert dstate.STATE.pending["load"] is None


def test_a_watch_queued_under_a_ref_the_load_re_arms_is_armed_too(tmp_path: Path) -> None:
    fake, _ = _deferred_load_with(
        tmp_path, lambda: server.watch_add(ref="foo", mode="change", length=2))
    fake.running = False
    server.status()
    kinds = sorted(r["entry"].split()[0] for r in fake.rows)
    assert kinds == ["BP", "BPPM", "BPPM"], fake.rows            # the watch's two bytes


def test_a_re_arm_that_fails_after_a_deferred_load_is_armed_from_the_queue(
        tmp_path: Path) -> None:
    fake, _ = _deferred_load_with(tmp_path, lambda: None)
    fake.running = False
    fake.bp_raises = True                       # the list read after the load refuses, once
    first = server.status()
    assert any("re-arm after the load" in s
               for s in first["applied_on_stop"].get("still_pending", [])), first
    fake.bp_raises = False
    fake.running = True
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


@pytest.mark.parametrize("family", ["breakpoint", "watch"])
def test_a_clear_the_store_cannot_write_disarms_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str) -> None:
    fake = _names(tmp_path, mode="Real")
    ref = "0814:0100" if family == "breakpoint" else "0814:0200"
    if family == "breakpoint":
        _ok(server.breakpoint_at(ref=ref))
    else:
        _ok(server.watch_add(ref=ref, mode="change", length=2))
    armed = [r["entry"] for r in fake.rows]
    assert armed, fake.rows
    store = dstate.STATE.store
    assert store is not None

    def fails() -> None:
        raise OSError("read-only")
    monkeypatch.setattr(store, "_persist", fails)
    got = server.declaration_clear(family, ref=ref)
    assert got["status"] == "INVALID" and "could not be written" in got["message"], got
    assert [r["entry"] for r in fake.rows] == armed, "a refused clear disarmed a row"
    assert len(store.declarations()) == 1, store.declarations()
    key = ("bp" if family == "breakpoint" else "watch", ref)
    assert key in dstate.STATE.armed, "a refused clear dropped the record of its row"
    fake.running = True
    assert server.declaration_clear(family, ref=ref)["status"] == "INVALID"
    assert dstate.STATE.pending["disarm"] == [], "a refused clear queued a disarm"


def test_a_watch_clear_that_cannot_read_the_mode_changes_nothing(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    _ok(server.watch_add(ref="0814:0200", mode="change", length=2))
    dstate.STATE.armed.clear()
    fake.where_raises = True
    assert server.declaration_clear("watch", ref="0814:0200")["status"] == "INVALID"
    store = dstate.STATE.store
    assert store is not None and len(store.declarations()) == 1, "the declaration was dropped"


def test_an_interrupt_breakpoint_the_store_cannot_keep_is_not_armed(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    store = dstate.STATE.store
    assert store is not None
    path = tmp_path / "decl.json"
    path.unlink(missing_ok=True)
    path.mkdir()                                  # the store's next write fails
    got = server.breakpoint_interrupt(number=0x21)
    assert got["status"] == "INVALID", got
    assert not [r for r in fake.rows if r["entry"].startswith("BPINT")], fake.rows


def test_a_queued_raw_breakpoint_a_stop_cannot_survey_blames_the_survey_not_the_row(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, mode="Real")
    server.status()
    fake.running = True
    _ok(server.breakpoint_at(ref="0814:0100"))
    fake.running = False

    def refused(_session: object) -> object:
        raise ds.Invalid("unexpected_answer", "a cut pane")
    with monkeypatch.context() as cut:
        cut.setattr(dcode, "segments_at_stop", refused)
        applied = server.status()["applied_on_stop"]
    (why,) = applied["still_pending"]
    assert "no stop has placed it" not in why and "survey" in why, why
    assert dstate.STATE.pending["arm"] == ["0814:0100"], dstate.STATE.pending
    fake.running = True
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


def test_a_show_watch_under_a_queued_ref_arms_nothing(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    _ok(server.watch_add(ref="0814:0100", mode="show", length=2))
    server.status()
    fake.running = True
    _ok(server.breakpoint_at(ref="0814:0100"))
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


def test_a_failed_re_arm_after_a_load_queues_only_what_the_re_arm_would_arm(
        tmp_path: Path) -> None:
    def stale() -> None:
        store, session = dstate.STATE.store, dstate.STATE.session
        assert store is not None and session is not None
        dstate.STATE.conf_fingerprint = dlaunch.fingerprint(session.launch.conf)
        store.add(dec.Declaration("breakpoint", "address", "00A7:5C6F0", origin="s0",
                                  fingerprint="another-build", cpu_mode="protected"))
    fake, _ = _deferred_load_with(tmp_path, stale)
    fake.running = False
    fake.bp_raises = True
    server.status()
    assert "00A7:5C6F0" not in dstate.STATE.pending["arm"], dstate.STATE.pending
    assert not [r for r in fake.rows if "5C6F0" in r["entry"]], fake.rows


def test_an_interrupt_breakpoint_the_debugger_refused_is_not_kept(tmp_path: Path) -> None:
    fake = _names(tmp_path)

    def refuse(number: int, ah: int | None = None) -> str:
        raise ds.Invalid("unexpected_answer", "no BPINT row came back")

    fake.breakpoint_interrupt = refuse  # type: ignore[method-assign]
    got = server.breakpoint_interrupt(number=0x21)
    assert got["status"] == "INVALID", got
    listed = server.declaration_list("breakpoint")
    assert listed["breakpoints"] == [], listed


def test_an_arrival_on_a_declared_breakpoint_names_both(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x1000, kind="T")])
    _ok(server.breakpoint_at(ref="foo"))
    fake.cs, fake.eip = "00A7", "00001000"
    got = cast(dict[str, Any], server.run_to(ref="foo", control="0000:0020", seconds=5))
    assert (got["cause"].startswith("run_to's target ")
            and "breakpoint foo is declared" in got["cause"]), got


def test_a_queued_raw_breakpoint_whose_place_cannot_be_written_is_said_at_the_stop(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    server.status()
    fake.running = True
    _ok(server.breakpoint_at(ref="0814:0100"))
    path = tmp_path / "decl.json"
    path.unlink(missing_ok=True)
    path.mkdir()                                  # the stop's write of its place fails
    fake.running = False
    got = server.status()
    assert got["status"] == "ok", got
    assert any("could not be written" in s
               for s in got["applied_on_stop"].get("still_pending", [])), got["applied_on_stop"]


@pytest.mark.parametrize(("decl", "can"), [
    (dec.Declaration("watch", "address", "0814:0100", width=2, fmt="u16", watch_mode="show"),
     False),
    (dec.Declaration("watch", "address", "0814:0100", width=2, fmt="u16", watch_mode="change"),
     True),
    (dec.Declaration("interrupt", "address", "BPINT 21", origin="an earlier session"), False),
    (dec.Declaration("interrupt", "address", "BPINT 21", origin="s-now"), True),
    (dec.Declaration("breakpoint", "symbol", "_absent", origin="s-now"), False),
    (dec.Declaration("breakpoint", "symbol", "_main", origin="s-now"), True),
], ids=["show", "change", "old-interrupt", "interrupt", "unresolved", "resolved"])
def test_what_can_stop_the_guest_is_what_would_be_armed(tmp_path: Path,
                                                        decl: dec.Declaration,
                                                        can: bool) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")], mode="Real")
    dstate.STATE.session_origin = "s-now"
    dstate.STATE.last_stop["held"] = []
    store = dstate.STATE.store
    assert store is not None
    store.add(decl)
    assert arming.something_can_stop_it() is can


def test_a_stop_named_while_the_machine_is_in_it_names_its_declaration_too() -> None:
    state = dstate.State()
    session = SimpleNamespace(stop_count=3, paging=None)
    state.remember_stop(cast(ds.Session, session), {"cs": "0814", "eip": "00001A27"}, {}, [],
                        {"attributed": True, "ref": "_tick", "by": "symbol",
                         "at": "0814:00001A27"})
    stop, words = state.stop_named(cast(ds.Session, session))
    assert stop["pc"] == "0814:00001A27" and words == " at 0814:00001A27 (_tick)", words


def test_a_raw_breakpoint_stored_before_modes_were_kept_is_adopted_by_the_stop_that_places_it(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0814:010B", cpu_mode=None, origin="old",
                           fingerprint="0123456789abcdef"))
    got = arming.rearm_declarations(cast(Any, fake))
    assert [r["ref"] for r in got["rearmed"]] == ["0814:010B"], got
    (row,) = st.declarations()
    assert row.cpu_mode == "real" and row.origin == "this-session", row
    assert row.fingerprint != dec.PENDING_STAMP, row


def test_a_re_arm_that_fails_after_the_base_moved_queues_what_it_would_arm(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)

    def cut(_session: Any) -> dict[str, Any]:
        raise ds.Invalid("unexpected_answer", "the pane was cut")

    monkeypatch.setattr(arming, "rearm_declarations", cut)
    out = arming.apply_pending(cast(Any, fake))
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert any("the pane was cut" in w for w in out["still_pending"]), out


def test_a_numbered_selector_is_remeasured_only_where_it_shares_the_programs_base(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    dstate.STATE.base_measured_from = "00AF"
    asked: list[str] = []

    def selector(_self: Any, reg: str) -> dict[str, int]:
        asked.append(reg)
        return {"base": 0x00500000 if reg == "00AF" else 0x00600000,
                "limit": 0x0023FFFF, "type": 0x1B}

    monkeypatch.setattr(type(fake), "selector", selector)
    out = arming.apply_pending(cast(Any, fake))
    assert "base_remeasured" not in out, out
    assert any("00AF" in w and "CS" in w for w in out["still_pending"]), out
    assert dstate.STATE.pending["remeasure"], "a refused re-measure must stay pending"
    monkeypatch.setattr(type(fake), "selector",
                        lambda _self, _reg: {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B})
    moved = arming.apply_pending(cast(Any, fake))
    assert moved["base_remeasured"]["to"] == "0x00500000", moved


def test_one_row_that_cannot_be_adopted_is_that_row_s_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    for ref in ("0814:010B", "0814:0200"):
        st.add(dec.Declaration("breakpoint", "address", ref, cpu_mode=None, origin="old",
                               fingerprint="0123456789abcdef"))
    armed = type(fake).arm_code_breakpoint

    def first_refuses(self: Any, seg: int, off: int) -> dict[str, object]:
        if off == 0x010B:
            raise ds.Invalid("unexpected_answer", "the debugger refused it")
        return armed(self, seg, off)

    monkeypatch.setattr(fake, "arm_code_breakpoint", first_refuses.__get__(fake))
    got = arming.rearm_declarations(cast(Any, fake))
    assert [r["ref"] for r in got["rearmed"]] == ["0814:0200"], got
    assert [r["ref"] for r in got["unarmable"]] == ["0814:010B"], got


def test_a_row_armed_whose_place_could_not_be_written_is_queued_for_the_next_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0814:010B", cpu_mode=None, origin="old",
                           fingerprint="0123456789abcdef"))

    def refuses(*_a: Any, **_k: Any) -> None:
        raise dec.StoreWriteError("the disk is full")

    monkeypatch.setattr(st, "apply", refuses)
    got = arming.rearm_declarations(cast(Any, fake))
    (row,) = got["rearmed"]
    assert "next stop writes it again" in row["why"], row
    assert "0814:010B" in dstate.STATE.pending["arm"]


def test_a_base_that_moved_clears_the_rows_armed_by_name_at_the_old_place(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    fake.cs = "00A7"                                   # declared before the load, at the old place
    dstate.STATE.pending["remeasure"] = False
    declared = cast(dict[str, Any], server.breakpoint_at(ref="_tick"))
    assert declared["status"] == "ok", declared
    cleared: list[tuple[int, int]] = []
    def clear(self: Any, seg: int, off: int) -> dict[str, object]:
        cleared.append((seg, off))
        return {"removed": True}

    monkeypatch.setattr(type(fake), "clear_code_breakpoint", clear)
    fake.cs = "00B7"
    dstate.STATE.machine_replaced()
    out = arming.apply_pending(cast(Any, fake))
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert cleared == [(0xA7, 0x1000)], cleared
    assert [r["entry"] for r in dstate.STATE.armed[("bp", "_tick")]] == ["BP 00B7:1000"]


def test_the_stop_a_list_ends_on_may_be_the_retrace_a_run_for_left_armed(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    declared = cast(dict[str, Any], server.breakpoint_at(ref="0814:0100"))
    assert declared["status"] == "ok", declared
    fake.halted = False
    dstate.STATE.retrace_pending = True
    out = cast(dict[str, Any], server.perform(steps=[{"op": "resume"}], settle_seconds=2.0))
    assert "retrace" in str(out["stopped"].get("cause")), out["stopped"]
    assert dstate.STATE.retrace_pending is False


def test_a_registerpoint_on_a_build_without_bpif_is_refused_once_by_name_and_never_queued(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.commands = frozenset(c for c in fake.commands if c != "BPIF")
    refused = server.regpoint_add(condition="AX==13")
    assert refused["code"] == "no_channel" and "`BPIF`" in str(refused["message"]), refused
    arming.current_store().add(arming.declare("regpoint", "expr", "AX==13"))
    unarmed = arming.rearm_declarations(cast(ds.Session, fake))["unarmable"]
    assert [r["why"] for r in unarmed] == ["this build's debugger has no `BPIF` command"]
    assert dstate.STATE.pending["arm"] == [], "nothing waits for a stop that cannot arm it"


def test_a_registerpoint_cleared_while_still_queued_promises_no_row_to_remove(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = True
    server.resume()
    fake.running, fake.halted = True, False
    queued = server.regpoint_add(condition="DX==3DA")
    assert queued["state"] == "pending", queued
    cleared = server.declaration_clear("regpoint", ref="DX==3DA")
    assert not cleared.get("pending_disarm") and not cleared.get("note"), cleared
    assert dstate.STATE.pending["arm"] == [] and dstate.STATE.pending["disarm"] == [], cleared
    fake.running, fake.halted = False, True
    stop = server.resume()
    assert "disarmed" not in stop.get("applied_on_stop", {}) and fake.rows == [], stop


def _clear_like_the_session(rows: int, refuses: bool = False) -> Any:
    """`Session.clear_*_breakpoint`'s shape: one row taken out per call, `removed` only when none
    is listed after, a `note` when no row was there at all."""
    left = [rows]

    def clear() -> dict[str, object]:
        if refuses:
            raise ds.Invalid("unexpected_answer", "BPDEL was refused")
        if left[0] == 0:
            return {"entry": "BPIF X", "removed": False, "note": "no such breakpoint to remove"}
        left[0] -= 1
        return {"entry": "BPIF X", "removed": left[0] == 0}
    return clear


@pytest.mark.parametrize(("rows", "refuses", "disarmed", "pending"), [
    (1, False, ["BPIF X"], []), (2, False, ["BPIF X"], []), (5, False, ["BPIF X"], []),
    (0, False, [], []), (2, True, [], ["X"]), (arming.DUPLICATE_ROWS_MAX + 1, False, [], ["X"])])
def test_a_clear_takes_out_every_duplicate_row_and_queues_what_it_could_not(
        rows: int, refuses: bool, disarmed: list[str], pending: list[str]) -> None:
    got_disarmed: list[str] = []
    got_pending: list[str] = []
    dstate.STATE.pending["disarm"].clear()
    arming.disarm_one({"kind": "cond", "entry": "BPIF X"}, "X", False, got_disarmed, got_pending,
                      _clear_like_the_session(rows, refuses))
    assert (got_disarmed, got_pending) == (disarmed, pending)
    assert bool(dstate.STATE.pending["disarm"]) == bool(pending)
    dstate.STATE.pending["disarm"].clear()


def test_a_queued_clear_takes_out_every_identical_row_at_the_stop() -> None:
    install()
    dstate.STATE.pending["disarm"][:] = [{"kind": "cond", "row": "X", "entry": "BPIF X"}]
    clear = _clear_like_the_session(3)
    session = cast(ds.Session, SimpleNamespace(clear_condition_breakpoint=lambda row: clear()))
    got = arming.apply_pending(session)
    assert got["disarmed"] == ["BPIF X"] and not got.get("still_pending"), got
    assert dstate.STATE.pending["disarm"] == []


@pytest.mark.parametrize(("state", "code"), [("ambiguous", "ambiguous_ref"),
                                              ("unresolved", "unknown_ref"),
                                              ("armable", "unknown_ref")])
def test_a_placement_that_cannot_be_used_is_refused_by_the_one_seam(state: str, code: str) -> None:
    refused = placement.refusal({"state": state, "why": "N is in the table twice"})
    assert (refused.code, str(refused)) == (code, "N is in the table twice")
    assert placement.refusal({"state": state}, "no place").args[-1] == "no place"

