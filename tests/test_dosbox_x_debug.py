"""Contract tests of the debug interface over the debugger channel: the stop survey, `step`,
`run_to`, `watch`, `resume`, a build without `RUNSTATE`, and what each hot path costs.

None launches DOSBox-X. `channel_double.Machine` answers each request in the shape the debugger
printed it live, and the real `Session` methods run against it; a count is the requests it was
sent, never a time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import fold_calls
import pytest
from channel_double import (
    NOT_RECOGNIZED,
    REAL_STOP,
    Machine,
    Stop,
    protected,
    session_over,
)
from dosbox_x_server_support import returned_key_sets
from scry_core import vocabulary as vocab
from test_dosbox_x_e9_wait import E9_BOOT, LogSession

import dosbox_arming as arming
import dosbox_debugger as dbg
import dosbox_grammar as grammar
import dosbox_run_state as run_state
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_stepping as stepping
import dosbox_x_server as server

#: The step guest's bytes at 0814:0100 (`tests/guest/step.asm`, assembled by nasm).
STEP_COM = bytes.fromhex("CD03B83412E81700B430CD21BE2200BF2600B90400FCF3A4B90300E2FEEB01C3EBFE")


def _step_guest(**over: Any) -> Machine:
    """The step guest stopped at 0814:0102, its code in memory."""
    regs = dict(REAL_STOP, CS=0x814, EIP=0x102)
    memory = {0x8140 + 0x100 + i: b for i, b in enumerate(STEP_COM)}
    return Machine(regs=regs, memory=memory, **over)


def exec_sent(machine: Machine) -> list[str]:
    return [c for c in machine.sent if c.startswith("EXEC ")]


# ------------------------------------------------------------------ the stop survey


def test_where_reads_the_position_and_the_mode_off_one_ev(tmp_path: Path) -> None:
    machine = Machine()
    s = session_over(machine, tmp_path)
    assert s.where() == {"cs": "0814", "eip": "00000130", "mode": "Real"}
    assert machine.sent == ["EXEC EV " + " ".join(dbg.SURVEY_NAMES)], machine.sent


def test_a_protected_stop_takes_its_code_size_from_cs_s_descriptor(tmp_path: Path) -> None:
    machine = protected(Machine())
    s = session_over(machine, tmp_path)
    where, regs, paging = s._survey()
    assert where == {"cs": "00A7", "eip": "00011734", "mode": "Pr32"}, where
    assert paging is True and regs["ESP"] == "0009CF9C", (paging, regs)
    machine.selinfo["CS"] = ("CS: b:00400000 type:1B parbg", "    l:0009FFFF dpl : 3 10000")
    s._surveyed = None
    assert s.where()["mode"] == "Pr16"


def test_a_virtual_8086_stop_is_its_own_mode_with_real_mode_segments(tmp_path: Path) -> None:
    machine = Machine()
    machine.regs.update(CR0=0x11, EFLAGS=0x23202)
    s = session_over(machine, tmp_path)
    assert s.where()["mode"] == "VM86"
    assert not any("SELINFO" in c for c in machine.sent), "a VM86 stop needs no descriptor"


def test_registers_are_given_at_the_widths_a_stop_reply_always_had(tmp_path: Path) -> None:
    s = session_over(Machine(), tmp_path)
    regs = s.registers()
    assert regs["EAX"] == "00000000" and regs["CS"] == "0814" and regs["EIP"] == "00000130"
    assert set(regs) == set(grammar.REGISTER_NAMES)


def test_an_ev_that_answers_short_is_refused_rather_than_misread(tmp_path: Path) -> None:
    machine = Machine()
    machine.hooks["EV"] = lambda c: (True, [f"EV of '{c[3:]}' is:", "814 130"])
    s = session_over(machine, tmp_path)
    with pytest.raises(ds.Invalid, match="not one value for each"):
        s.where()


def test_a_running_machine_is_refused_a_survey_and_nothing_else_is_sent(tmp_path: Path) -> None:
    machine = Machine(stopped=False)
    s = session_over(machine, tmp_path)
    with pytest.raises(ds.NotStopped, match="the guest is running"):
        s.where()
    assert machine.sent == ["EXEC RUNSTATE"], machine.sent


def test_a_stop_the_machine_ran_into_is_found_by_the_next_contact(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x200})])
    s = session_over(machine, tmp_path)
    s.resume()
    assert s.at_debugger() and s.where()["eip"] == "00000200"


# ------------------------------------------------------------------ breakpoints


def test_the_breakpoint_list_is_read_as_the_debugger_printed_it(tmp_path: Path) -> None:
    machine = Machine(breakpoints=["BPMEM 0040:006C (00)", "BPINT 21 AH=4C", "BP 0814:0130"])
    s = session_over(machine, tmp_path)
    assert [b["entry"] for b in s.breakpoints()] == machine.breakpoints
    assert [b["index"] for b in s.breakpoints()] == ["00", "01", "02"]


def test_an_empty_list_is_an_answer_and_a_missing_header_is_not(tmp_path: Path) -> None:
    machine = Machine()
    s = session_over(machine, tmp_path)
    assert s.breakpoints() == []
    machine.hooks["BPLIST"] = lambda _c: (True, ["-------"])
    with pytest.raises(ds.Invalid, match="printed no 'Breakpoint list:'"):
        s.breakpoints()


def test_an_interrupt_breakpoint_is_confirmed_from_the_list_not_from_the_word(
        tmp_path: Path) -> None:
    machine = Machine()
    s = session_over(machine, tmp_path)
    assert "INT 21 AH=4C" in s.breakpoint_interrupt(0x21, 0x4C)
    machine.hooks["BPINT"] = lambda c: (True, ["DEBUG: Set interrupt breakpoint at INT 13"])
    with pytest.raises(ds.Invalid, match="not in the debugger's breakpoint list"):
        s.breakpoint_interrupt(0x13)


def test_arming_reads_the_row_back_and_leaves_the_session_unaltered(tmp_path: Path) -> None:
    machine = Machine()
    s = session_over(machine, tmp_path)
    got = s.arm_code_breakpoint(0x814, 0x130)
    assert got["entry"] == "BP 0814:0130" and s.altered is False
    machine.hooks["BP"] = lambda c: (True, ["DEBUG: Set breakpoint at 0814:0140"])
    with pytest.raises(ds.Invalid, match="NOT armed"):
        s.arm_code_breakpoint(0x814, 0x140)


def test_a_build_without_the_heavy_debugger_alters_the_guest_by_arming(tmp_path: Path) -> None:
    """Such a build plants a code breakpoint as an `INT 3` byte in guest memory; the heavy one
    checks each instruction against its list and writes nothing."""
    s = session_over(Machine(), tmp_path)
    s.plants_int3 = True
    s.arm_code_breakpoint(0x814, 0x130)
    assert s.altered is True
    again = session_over(Machine(), tmp_path)
    again.plants_int3 = True
    again.watch_places([(0x814, 0x200)])
    assert again.altered is False, "a memory watch plants nothing"


def test_a_clear_finds_its_row_by_value_and_reads_the_removal_back(tmp_path: Path) -> None:
    machine = Machine(breakpoints=["BP 0814:0130", "BPINT 21"])
    s = session_over(machine, tmp_path)
    assert s.clear_code_breakpoint(0x814, 0x130) == {"entry": "BP 0814:0130", "removed": True}
    assert s.clear_interrupt_breakpoint(0x21) == {"entry": "BPINT 21", "removed": True}
    assert machine.breakpoints == []
    absent = s.clear_code_breakpoint(0x814, 0x130)
    assert absent["removed"] is False and "no such breakpoint" in str(absent["note"])


def test_a_breakpoint_bpdel_did_not_remove_is_said_to_be_there(tmp_path: Path) -> None:
    machine = Machine(breakpoints=["BP 0814:0130"])
    machine.hooks["BPDEL"] = lambda _c: (True, ["DEBUG: Breakpoint deletion failure."])
    s = session_over(machine, tmp_path)
    assert s.clear_code_breakpoint(0x814, 0x130)["removed"] is False


# ------------------------------------------------------------------ step


def test_a_step_into_is_stepin_and_reads_where_it_landed(tmp_path: Path) -> None:
    machine = _step_guest(steps=[{"EIP": 0x105, "EAX": 0x1234}])
    s = session_over(machine, tmp_path)
    got = s.step(count=1, mode="into")
    assert got["after"] == {"cs": "0814", "eip": "00000105", "mode": "Real"}, got
    assert got["moved"] is True and got["completed"] == 1 and got["running"] is False
    assert "EXEC STEPIN" in machine.sent


def test_a_step_over_a_call_composes_a_breakpoint_at_the_next_instruction(
        tmp_path: Path) -> None:
    """At 0814:0105 `call leaf` (E8 17 00), three bytes: the next instruction is 0814:0108."""
    machine = _step_guest(releases=[Stop({"EIP": 0x108})])
    machine.regs["EIP"] = 0x105
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.step(count=1, mode="over"))
    assert got["after"]["eip"] == "00000108", got
    assert "EXEC BP 0814:0108" in machine.sent and "EXEC RUN" in machine.sent
    assert "EXEC STEPIN" not in machine.sent
    assert machine.breakpoints == [], "the step's own breakpoint was left armed"


@pytest.mark.parametrize(("eip", "after"), [(0x10A, 0x10C), (0x116, 0x118), (0x11B, 0x11D)],
                         ids=["int-21h", "rep-movsb", "loop"])
def test_a_step_over_runs_an_int_a_rep_and_a_loop_to_their_next_instruction(
        tmp_path: Path, eip: int, after: int) -> None:
    machine = _step_guest(releases=[Stop({"EIP": after})])
    machine.regs["EIP"] = eip
    s = session_over(machine, tmp_path)
    assert cast(dict[str, Any], s.step(count=1, mode="over"))["after"]["eip"] == f"{after:08X}"
    assert f"EXEC BP 0814:{after:04X}" in machine.sent


def test_a_step_over_a_plain_instruction_is_a_step_into(tmp_path: Path) -> None:
    machine = _step_guest(steps=[{"EIP": 0x105}])
    s = session_over(machine, tmp_path)
    s.step(count=1, mode="over")
    assert "EXEC STEPIN" in machine.sent and "EXEC RUN" not in machine.sent


def test_a_step_over_keeps_a_breakpoint_the_caller_had_at_the_next_instruction(
        tmp_path: Path) -> None:
    machine = _step_guest(releases=[Stop({"EIP": 0x108})], breakpoints=["BP 0814:0108"])
    machine.regs["EIP"] = 0x105
    s = session_over(machine, tmp_path)
    s.step(count=1, mode="over")
    assert machine.breakpoints == ["BP 0814:0108"], "the caller's breakpoint was removed"
    assert "EXEC BP 0814:0108" not in machine.sent


def test_a_step_over_that_cannot_be_stopped_at_its_bound_says_its_breakpoint_is_armed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`BREAK` taken and `RUNSTATE` never stopped: the refusal carries the row left behind."""
    monkeypatch.setattr(stepping, "STEP_WAIT_S", 0.05)
    monkeypatch.setattr(run_state, "BREAK_IN_WAIT_S", 0.05)
    machine = _step_guest(releases=[None])
    machine.regs["EIP"] = 0x105
    s = session_over(machine, tmp_path)
    original = machine.request

    def deaf_break(command: str, *a: Any, **k: Any) -> tuple[bool, list[str]]:
        return (True, []) if command == "BREAK" else original(command, *a, **k)
    machine.request = deaf_break  # type: ignore[method-assign]
    with pytest.raises(ds.Invalid) as e:
        s.step(count=1, mode="over")
    assert e.value.code == "not_settled" and "0814:0108 is STILL ARMED" in str(e.value), e.value


def test_a_step_over_whose_own_breakpoint_will_not_go_says_it_is_still_armed(
        tmp_path: Path) -> None:
    """A `BPDEL` the debugger takes and leaves the row: the reply says the next run stops there."""
    machine = _step_guest(releases=[Stop({"EIP": 0x108})])
    machine.regs["EIP"] = 0x105
    machine.hooks["BPDEL"] = lambda body: (True, [])
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.step(count=1, mode="over"))
    assert machine.breakpoints == ["BP 0814:0108"]
    assert "0814:0108 is STILL in the debugger's list" in str(got.get("note")), got


def test_a_step_over_that_runs_past_its_bound_is_brought_back_and_says_where(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bound's `BREAK` stops the machine inside the callee: the reply says it is stopped
    there, and the steps after it are not sent."""
    monkeypatch.setattr(stepping, "STEP_WAIT_S", 0.05)
    machine = _step_guest(releases=[None])
    machine.regs["EIP"] = 0x105
    s = session_over(machine, tmp_path)
    original = machine.request

    def inside_the_callee(command: str, *a: Any, **k: Any) -> tuple[bool, list[str]]:
        if command == "BREAK":
            machine.regs["EIP"] = 0x11F
        return original(command, *a, **k)
    machine.request = inside_the_callee  # type: ignore[method-assign]
    got = cast(dict[str, Any], s.step(count=3, mode="over"))
    assert got["running"] is False and got["completed"] == 1, got
    assert got["after"]["eip"] == "0000011F" and s.parked, got
    assert "BREAK" in machine.sent and machine.breakpoints == []
    assert machine.sent.count("EXEC RUN") == 1, "a step was sent after the interrupted one"


def test_a_release_whose_reply_fails_is_not_believed_stopped(tmp_path: Path) -> None:
    """The release went out; a reply that broke off cannot say it stayed at the debugger."""
    machine = Machine(regs=dict(REAL_STOP))
    s = session_over(machine, tmp_path)

    def dropped(command: str) -> tuple[bool, list[str]] | None:
        raise ds.Invalid("session_broken", "the debugger channel dropped")
    machine.hooks["RUN"] = dropped
    with pytest.raises(ds.Invalid):
        s._release("RUN")
    assert not s.parked


def test_a_rep_ret_is_stepped_into_as_the_return_it_is(tmp_path: Path) -> None:
    """`F3 C3` returns: a breakpoint after it would never be reached."""
    machine = _step_guest(steps=[{"EIP": 0x200}])
    base = (0x814 << 4) + 0x105
    machine.memory.update({base: 0xF3, base + 1: 0xC3})
    machine.regs["EIP"] = 0x105
    s = session_over(machine, tmp_path)
    s.step(count=1, mode="over")
    assert "EXEC STEPIN" in machine.sent and "EXEC RUN" not in machine.sent, machine.sent


def test_a_loaded_state_is_read_afresh(tmp_path: Path) -> None:
    """A load replaces the machine: the survey of the stop before it is no reading of it."""
    machine = Machine(regs=dict(REAL_STOP))
    s = session_over(machine, tmp_path)
    assert s.where()["eip"] == "00000130"

    def loaded(command: str) -> tuple[bool, list[str]]:
        machine.regs["EIP"] = 0x777
        return True, ["DEBUG: LOADSTATE ok"]
    machine.hooks["LOADSTATE"] = loaded
    state = tmp_path / "a.sav"
    state.write_bytes(b"state")
    s._state_command("LOADSTATE", state, 5.0)
    assert s.where()["eip"] == "00000777"


def test_moved_is_asked_per_step_and_not_of_the_endpoints(tmp_path: Path) -> None:
    machine = _step_guest(steps=[{"EIP": 0x105}, {"EIP": 0x105}, {"EIP": 0x108}])
    s = session_over(machine, tmp_path)
    got = s.step(count=3, mode="into")
    assert got["stalled"] == 1 and got["moved"] is True and got["completed"] == 3, got


def test_a_step_refuses_a_mode_it_does_not_have_and_a_count_it_cannot_afford(
        tmp_path: Path) -> None:
    s = session_over(Machine(), tmp_path)
    with pytest.raises(ds.Invalid, match="mode"):
        s.step(count=1, mode="out")
    for bad in (0, stepping.STEP_MAX + 1):
        with pytest.raises(ds.Invalid, match="cost bound"):
            s.step(count=bad, mode="into")


def test_steps_already_taken_are_named_when_the_landing_cannot_be_read(tmp_path: Path) -> None:
    machine = _step_guest(steps=[{"EIP": 0x105}])
    s = session_over(machine, tmp_path)
    reads = {"n": 0}

    def ev(c: str) -> tuple[bool, list[str]] | None:
        reads["n"] += 1
        return (True, ["EV of '?' is:", "1 2"]) if reads["n"] > 2 else None
    machine.hooks["EV"] = ev
    with pytest.raises(ds.Invalid, match=r"ALREADY gone to the machine .* 1 were CONFIRMED"):
        s.step(count=3, mode="into")


# ------------------------------------------------------------------ run_to


def test_run_to_arrives_and_removes_the_breakpoint_it_created(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x140})])
    s = session_over(machine, tmp_path)
    got = s.run_to(0x814, 0x140, 1.0)
    assert got["verdict"] == "TARGET" and got["breakpoint_removed"] is True, got
    assert machine.breakpoints == []
    assert s.altered is False, "a debugger breakpoint changes neither memory nor registers"


def test_run_to_in_real_mode_arrives_at_an_aliased_seg_off(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"CS": 0x815, "EIP": 0x130})])
    s = session_over(machine, tmp_path)
    assert s.run_to(0x814, 0x140, 1.0)["verdict"] == "TARGET"


def test_never_armed_is_refused_rather_than_reported_as_never_arrived(tmp_path: Path) -> None:
    machine = Machine()
    machine.hooks["BP"] = lambda c: (True, ["DEBUG: Set breakpoint at nowhere"])
    s = session_over(machine, tmp_path)
    with pytest.raises(ds.Invalid, match="does not list a breakpoint at 0814:0140"):
        s.run_to(0x814, 0x140, 1.0)
    assert "EXEC RUN" not in machine.sent


def test_stopping_somewhere_else_is_another_stop_and_not_an_arrival(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x200})])
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.run_to(0x814, 0x140, 1.0))
    assert got["verdict"] == "OTHER_STOP" and "something else got there first" in got["note"]


def test_a_bound_that_expires_interrupts_the_run_and_disarms_the_target(tmp_path: Path) -> None:
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.run_to(0x814, 0x140, 0.1))
    assert got["verdict"] == "TIMEOUT" and "interrupted" in got["note"], got
    assert "BREAK" in machine.sent and machine.breakpoints == []


def test_run_to_with_a_control_counts_its_hits_and_lets_the_machine_go_again(
        tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x150}), Stop({"EIP": 0x150}), Stop({"EIP": 0x140})])
    s = session_over(machine, tmp_path)
    got = s.run_to(0x814, 0x140, 1.0, control=(0x814, 0x150))
    assert got["verdict"] == "TARGET", got
    control = cast(dict[str, Any], got["control"])
    assert control == {"at": "0814:0150", "hits": 2, "removed": True}, control
    assert machine.breakpoints == []


def test_a_control_that_eats_the_whole_bound_is_a_timeout(tmp_path: Path) -> None:
    machine = Machine(then=Stop({"EIP": 0x150}))
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.run_to(0x814, 0x140, 0.05, control=(0x814, 0x150)))
    assert got["verdict"] == "TIMEOUT" and "ON the control" in got["note"], got


def test_run_to_refuses_a_control_on_the_target_and_arguments_it_cannot_honour(
        tmp_path: Path) -> None:
    s = session_over(Machine(), tmp_path)
    with pytest.raises(ds.Invalid, match="same address as the target"):
        s.run_to(0x814, 0x140, 1.0, control=(0x815, 0x130))
    with pytest.raises(ds.Invalid, match="a segment is"):
        s.run_to(0x10000, 0, 1.0)
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        s.run_to(0x814, 0x10000, 1.0)
    with pytest.raises(ds.Invalid):
        s.run_to(0x814, 0x140, vocab.WAIT_MAX_S + 1)


def test_a_protected_mode_target_may_be_wider_than_sixteen_bits(tmp_path: Path) -> None:
    machine = protected(Machine(releases=[Stop({"EIP": 0x16DF20})]))
    s = session_over(machine, tmp_path)
    assert s.run_to(0xA7, 0x16DF20, 1.0)["verdict"] == "TARGET"


def test_a_cleanup_that_could_not_be_confirmed_is_said_beside_a_sound_arrival(
        tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x140})])
    machine.hooks["BPDEL"] = lambda _c: (True, ["DEBUG: Breakpoint deletion failure."])
    s = session_over(machine, tmp_path)
    got = cast(dict[str, Any], s.run_to(0x814, 0x140, 1.0))
    assert got["verdict"] == "TARGET" and got["breakpoint_removed"] is False
    assert "STILL in the debugger's list" in got["note"], got


def test_the_stop_wait_reports_its_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                             ) -> None:
    monkeypatch.setattr(dbg, "PROGRESS_EVERY_S", 0.0)
    said: list[str] = []
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path)
    s.run_to(0x814, 0x140, 0.05, progress=lambda _e, _t, m: said.append(m))
    assert said and all(m.startswith("run_to 0814:0140: running") for m in said), said[:3]


def test_a_run_cancelled_in_flight_is_brought_back_and_takes_its_breakpoints_with_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from scry_core import cancel
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path)
    calls = {"n": 0}

    def check() -> None:
        calls["n"] += 1
        if calls["n"] > 3 and not cancel.shielding():
            raise asyncio.CancelledError
    monkeypatch.setattr(cancel, "check", check)
    with pytest.raises(asyncio.CancelledError):
        s.run_to(0x814, 0x140, 5.0)
    assert "BREAK" in machine.sent and machine.breakpoints == [], machine.sent


# ------------------------------------------------------------------ watches


def test_a_watch_chooses_its_command_by_the_machines_mode(tmp_path: Path) -> None:
    real = Machine()
    armed = session_over(real, tmp_path)
    got = armed.watch_places([(0x40, 0x6C)])[0]
    assert armed.altered is False
    assert (got["command"], got["armed"]) == ("BPM 0040:006C", "BPMEM 0040:006C")
    pr32 = protected(Machine())
    got = session_over(pr32, tmp_path).watch_places([(0xAF, 0x16DF20)])[0]
    assert (got["command"], got["armed"]) == ("BPPM 00AF:16DF20", "BPPM 00AF:0016DF20")


def test_a_watch_the_debugger_does_not_hold_is_refused(tmp_path: Path) -> None:
    machine = Machine()
    machine.hooks["BPM"] = lambda c: (True, ["DEBUG: Set memory breakpoint at 0040:006C"])
    with pytest.raises(ds.Invalid, match="never fires are the same silence"):
        session_over(machine, tmp_path).watch_places([(0x40, 0x6C)])[0]


def test_a_watch_refuses_an_address_its_mode_cannot_carry(tmp_path: Path) -> None:
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        session_over(Machine(), tmp_path).watch_places([(0x40, 0x10000)])[0]


# ------------------------------------------------------------------ resume and BREAK


def test_a_resume_that_stopped_straight_away_says_where(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x200})])
    got = session_over(machine, tmp_path).resume()
    assert got["halted"] is True and cast(dict[str, str], got["stopped_at"])["eip"] == "00000200"
    assert got["output"] == "OK"


def test_a_resume_without_a_look_returns_straight_after_the_release(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x200})])
    got = session_over(machine, tmp_path).resume(look=False)
    assert got["halted"] is False and got["stopped_at"] is None and got["output"] == "OK", got
    assert "EXEC RUN" in machine.sent and "EXEC RUNSTATE" not in machine.sent, machine.sent


def test_a_resume_without_a_look_still_says_when_the_build_cannot_tell(tmp_path: Path) -> None:
    _, official = _official(tmp_path)
    got = official.resume(look=False)
    assert isinstance(got["halted"], dict) and "RUNSTATE" in got["halted"]["why"], got


def test_a_resume_that_let_the_machine_go_says_that_instead(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            ) -> None:
    monkeypatch.setattr(ds, "RESUME_LOOK_S", 0.05)
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path)
    got = s.resume()
    assert got["halted"] is False and got["stopped_at"] is None
    assert s.state()["running"] is True


def test_status_on_a_running_guest_asks_runstate_once(tmp_path: Path) -> None:
    machine = Machine(stopped=False)
    dstate.STATE.session = session_over(machine, tmp_path)
    try:
        got = cast(dict[str, Any], fold_calls.of(server, "status")())
    finally:
        dstate.STATE.session = None
    assert got["status"] == "ok" and got["session"]["running"] is True, got
    assert machine.sent == ["EXEC RUNSTATE"], machine.sent


def test_what_was_queued_is_applied_only_at_a_stop_the_contact_recorded(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The machine stops between the contact's first `RUNSTATE` and a second: applying the queue
    there would answer `applied_on_stop` for a stop no reply has named."""
    machine = Machine(stopped=False, polls_before_stop=1)
    machine._pending = Stop({"EIP": 0x200})
    session = session_over(machine, tmp_path)
    applied: list[bool] = []
    monkeypatch.setattr(arming, "apply_pending", lambda _s: applied.append(True))
    dstate.STATE.pending["arm"].append("0000:0009")
    dstate.STATE.pending["dirty"] = True
    try:
        running.drain_if_stopped(session)
        assert applied == [] or dstate.STATE.last_stop.get("stop_count") == session.stop_count
        running.drain_if_stopped(session)
        assert applied == [True] and dstate.STATE.found_stop_last, dstate.STATE.found_stop_last
    finally:
        dstate.STATE.pending["arm"].clear()
        dstate.STATE.pending["dirty"] = False


def test_break_in_waits_for_runstate_to_say_stopped(tmp_path: Path) -> None:
    machine = Machine(stopped=False)
    s = session_over(machine, tmp_path)
    s.break_in()
    assert s.at_debugger() and machine.sent[:2] == ["BREAK", "EXEC RUNSTATE"], machine.sent


def test_break_in_on_a_build_without_a_debugger_screen_says_why(tmp_path: Path) -> None:
    machine = Machine(stopped=False)
    machine.request = lambda command, *a, **k: (True, [  # type: ignore[method-assign]
        "Debugger in Mac OS X is not available unless you start DOSBox-X from a terminal or "
        "from the Terminal application"])
    with pytest.raises(ds.Invalid, match="refused BREAK"):
        session_over(machine, tmp_path).break_in()


# ------------------------------------------------------------------ a build without RUNSTATE


def _official(tmp_path: Path, **over: Any) -> tuple[Machine, ds.Session]:
    machine = Machine(commands=(), **over)
    return machine, session_over(machine, tmp_path)


@pytest.mark.parametrize("call", [
    pytest.param(lambda s: s.run_to(0x814, 0x140, 1.0), id="run_to"),
    pytest.param(lambda s: s.step(count=1, mode="into"), id="step-into"),
    pytest.param(lambda s: s.retrace(0.0, 1.0), id="retrace"),
    pytest.param(lambda s: s.log_cpu("LOG", 2, 0.0, 1.0), id="log"),
])
def test_a_tool_that_waits_for_a_stop_is_refused_naming_the_command_it_needs(
        tmp_path: Path, call: Any) -> None:
    machine, s = _official(tmp_path)
    with pytest.raises(ds.Invalid) as caught:
        call(s)
    assert caught.value.code == "no_channel" and dbg.COMMANDS_SECTION in str(caught.value)
    assert {"EXEC RUN", "EXEC VRT", "EXEC STEPIN"}.isdisjoint(machine.sent), machine.sent
    assert not any(c.startswith("EXEC BP ") for c in machine.sent), machine.sent


def test_a_step_over_needs_runstate_and_into_needs_stepin(tmp_path: Path) -> None:
    machine = Machine(commands=("STEPIN",))
    s = session_over(machine, tmp_path)
    with pytest.raises(ds.Invalid, match="`RUNSTATE`"):
        s.step(count=1, mode="over")
    _, official = _official(tmp_path)
    with pytest.raises(ds.Invalid, match="`STEPIN`"):
        official.step(count=1, mode="into")


def test_readings_keep_working_until_a_release_and_after_a_stop(tmp_path: Path) -> None:
    machine, s = _official(tmp_path)
    assert s.where()["eip"] == "00000130"
    out = s.resume()
    assert isinstance(out["halted"], dict) and "RUNSTATE" in out["halted"]["why"]
    with pytest.raises(ds.Invalid, match="`stop` brings it back") as caught:
        s.where()
    assert caught.value.code == "no_channel"
    s.break_in()
    assert s.where()["eip"] == "00000130" and "EXEC RUNSTATE" not in machine.sent


def test_a_binary_that_names_runstate_and_a_debugger_that_lacks_it_starts_without_it(
        tmp_path: Path) -> None:
    machine = Machine(commands=())
    s = session_over(machine, tmp_path)
    s.commands = frozenset({"RUNSTATE"})
    assert s._first_stop() is True
    assert "RUNSTATE" not in s.commands and machine.sent == ["EXEC RUNSTATE", "BREAK"]


# ------------------------------------------------------------------ the capture cap


def test_a_reply_cut_at_the_channels_cap_is_refused_and_never_read_as_whole(
        tmp_path: Path) -> None:
    machine = Machine()
    machine.hooks["GDT"] = lambda _c: (True, ["GDT Base:00000000 Limit:0000FFFF",
                                             "[1 debug output lines discarded]"])
    s = session_over(machine, tmp_path)
    with pytest.raises(ds.Invalid, match=f"more than the {dbg.CAPTURE_LINES} lines"):
        s.listing("GDT")


def test_an_unknown_command_comes_back_not_taken_with_the_debuggers_words(
        tmp_path: Path) -> None:
    assert session_over(Machine(), tmp_path).exec("NOSUCH") == (False, [NOT_RECOGNIZED])


# ------------------------------------------------------------------ what a hot path costs


def test_a_step_into_costs_one_reading_before_and_two_requests_per_step(tmp_path: Path) -> None:
    machine = _step_guest(steps=[{"EIP": 0x105}, {"EIP": 0x11F}, {"EIP": 0x108}])
    s = session_over(machine, tmp_path)
    s.step(count=3, mode="into")
    assert exec_sent(machine) == ["EXEC EV " + " ".join(dbg.SURVEY_NAMES)] + [
        "EXEC STEPIN", "EXEC EV " + " ".join(dbg.SURVEY_NAMES)] * 3, exec_sent(machine)


def test_a_control_hit_costs_a_release_a_run_state_and_one_reading(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x150}), Stop({"EIP": 0x140})])
    s = session_over(machine, tmp_path)
    s.run_to(0x814, 0x140, 1.0, control=(0x814, 0x150))
    first_run = machine.sent.index("EXEC RUN")
    second_run = machine.sent.index("EXEC RUN", first_run + 1)
    assert machine.sent[first_run:second_run] == [
        "EXEC RUN", "EXEC RUNSTATE", "EXEC EV " + " ".join(dbg.SURVEY_NAMES)], machine.sent


def test_the_teardown_of_two_breakpoints_reads_the_list_twice_and_deletes_twice(
        tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x140})])
    s = session_over(machine, tmp_path)
    s.run_to(0x814, 0x140, 1.0, control=(0x814, 0x150))
    arrived = len(machine.sent) - 1 - machine.sent[::-1].index(
        "EXEC EV " + " ".join(dbg.SURVEY_NAMES))
    assert machine.sent[arrived + 1:] == ["EXEC BPLIST", "EXEC BPDEL 01", "EXEC BPDEL 00",
                                          "EXEC BPLIST"], machine.sent[arrived + 1:]


def test_a_reading_at_a_surveyed_stop_costs_one_request(tmp_path: Path) -> None:
    machine = Machine(memory={0x8270: 0xAB})
    s = session_over(machine, tmp_path)
    s.where()
    before = len(machine.sent)
    assert s.read_bytes(0x814, 0x130, 1) == b"\xab"
    assert machine.sent[before:] == ["EXEC MEMDUMPBIN 0814:0130 1 MCPDUMP.BIN"], machine.sent


def test_a_write_or_a_release_makes_the_next_reading_survey_again(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop({"EIP": 0x200})])
    s = session_over(machine, tmp_path)
    s.where()
    s.set_register("eax", 5)
    assert s.registers()["EAX"] == "00000005"
    s.resume()
    assert s.where()["eip"] == "00000200"


# ------------------------------------------------------------------ the tools


@pytest.mark.parametrize("call", [
    pytest.param(lambda: server.step(mode="over"), id="step"),
    pytest.param(lambda: server.run_to(ref="0000:0000", control="0000:0020"), id="run_to"),
    pytest.param(lambda: server.log_wait(channel="guest", pattern="x", seconds=1), id="log_wait"),
])
def test_each_tool_refuses_with_no_session_and_still_carries_the_envelope(
        call: Any) -> None:
    reply = cast(dict[str, Any], call())
    assert reply["status"] == "INVALID"
    assert "no live session" in reply["message"]
    assert reply["session"] == {"alive": False, "running": False, "altered": False}


# Derived from the method, not listed: a hand-written dict fell behind when `step` and
# `run_to` gained fields, and this is the only check that the envelope drops nothing.
# `step` names the session's count in the shared word; the rest of its account is handed on.
TOOL_FIELDS = {"step": set(returned_key_sets(ds.Session.step)[0]) - {"completed", "running"}
               | {"instructions_completed"},
               "log_wait": next(set(keys) for keys in returned_key_sets(ds.Session.log_wait)
                                if "line" in keys)}


@pytest.mark.parametrize("tool", sorted(TOOL_FIELDS))
def test_the_tools_hand_the_sessions_own_answer_back_whole(tool: str, tmp_path: Path) -> None:
    """A tool wrapped to return only the envelope goes red."""
    args: dict[str, Any] = {"step": {"mode": "into", "count": 1},
                            "log_wait": {"pattern": "start version", "channel": "guest",
                                         "seconds": 1}}[tool]
    if tool == "log_wait":
        log = tmp_path / "guest.log"
        log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
        dstate.STATE.session = cast(ds.Session, LogSession(log))
    else:
        dstate.STATE.session = session_over(_step_guest(steps=[{"EIP": 0x105}]), tmp_path)
    reply = cast(dict[str, Any], fold_calls.of(server, tool)(**args))
    assert reply["status"] == "ok", reply
    missing = TOOL_FIELDS[tool] - set(reply)
    assert not missing, f"{tool} dropped {sorted(missing)} on the way through _answer"


