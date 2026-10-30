"""`run_for` by display retraces (the debugger's `VRT`), against the channel double: each `VRT`
stops at the next scripted retrace, and `RUNSTATE` gives the emulated clock it reached."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from channel_double import REAL_STOP, Machine, Stop, protected, session_over
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab

from scry_dosbox_x import arming, grammar, retrace, server
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x.sequence import _leaves_running

#: The probe guest at rest in its tick loop, where a retrace stop finds it.
PARK = {"CS": 0x814, "EIP": 0x106}
#: One retrace of the probe's 70 Hz text mode, in emulated milliseconds.
FRAME_MS = 14.27


def live(machine: Machine, tmp_path: Path) -> Machine:
    """The double as `start` leaves a session, its park already recorded as the last stop."""
    install()
    machine.regs.update(PARK)
    dstate.STATE.session = session_over(machine, tmp_path)
    dstate.STATE.remember_stop(dstate.STATE.session,
                               {"cs": "0814", "eip": "00000106", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return machine


def frames(n: int, **over: Any) -> Machine:
    return Machine(regs=dict(REAL_STOP), releases=[Stop(ms=FRAME_MS)] * n, **over)


def vrts(machine: Machine) -> list[str]:
    return [c for c in machine.sent if c == "EXEC VRT"]


def _real_bp(ref: str) -> None:
    """A raw breakpoint at the real-mode stop the probe guest sits at."""
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", ref, cpu=grammar.REAL_MODE))


def test_three_frames_land_three_retraces_with_the_whole_stop_reply(tmp_path: Path) -> None:
    machine = live(frames(3), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert got["status"] == "ok", got
    assert got["verdict"] == "ELAPSED" and got["polls"] == 3, got
    assert vrts(machine) == ["EXEC VRT"] * 3, "one VRT per frame, sent as a release"
    assert got["pc"].endswith(":00000106"), got
    assert got["emulated_before_s"] == pytest.approx(0.0007)
    assert got["emulated_after_s"] == pytest.approx(0.0007 + 3 * FRAME_MS / 1000)
    assert got["frame_before"]["available"] is False and got["frame_after"]["available"] is False
    assert "prints no `frames=`" in got["frame"]["why"], got["frame"]
    assert "normal core" in got["cycles"]["why"], got
    assert got["regs"] and "cause" in got and "e9" in got and "stop_seq" in got
    assert got["session"]["altered"] is False, "advancing is not writing"
    assert got["summary"].startswith("run_for 3 frames: ELAPSED"), got["summary"]
    assert "cannot be told" in got["cause"], "with no frame counted, no retrace is proved"


def test_cycles_are_counted_when_the_session_started_on_the_normal_core(tmp_path: Path) -> None:
    machine = live(frames(3), tmp_path)
    dstate.STATE.session.launch.core = "normal"      # type: ignore[union-attr]
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert got["cycles"] == 3 * 1000, got["cycles"]
    assert vrts(machine) == ["EXEC VRT"] * 3


def test_a_cycle_counter_that_wrapped_in_the_run_gives_no_count() -> None:
    from types import SimpleNamespace
    session = SimpleNamespace(launch=SimpleNamespace(core="normal"), cycles=3)
    got = retrace._cycles(cast(ds.Session, session), 10)
    assert got["available"] is False and "wrapped" in got["why"], got
    session.cycles = 13
    assert retrace._cycles(cast(ds.Session, session), 10) == 3


def test_cycles_name_the_core_that_keeps_them_from_being_counted(tmp_path: Path) -> None:
    live(frames(1), tmp_path)
    dstate.STATE.session.launch.core = "dynamic_x86"  # type: ignore[union-attr]
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["cycles"]["available"] is False and "dynamic_x86" in got["cycles"]["why"], got


def test_a_build_that_counts_frames_places_the_run_and_its_stop_by_frame(tmp_path: Path) -> None:
    machine = frames(3)
    machine.frames = 100
    live(machine, tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert (got["frame_before"], got["frame_after"], got["frame"]) == (100, 103, 103), got
    assert got["cause"] == "the retrace run_for ran to, at 0814:00000106", got["cause"]


def test_the_stop_run_for_lands_on_carries_the_e9_block_even_with_no_log(tmp_path: Path) -> None:
    live(frames(3), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert got["status"] == "ok" and got["e9"]["available"] is False, got["e9"]
    assert "logfile" in got["e9"]["why"], got["e9"]


def test_with_nothing_that_can_cut_it_no_frame_is_surveyed(tmp_path: Path) -> None:
    """Fast path: nothing declared can cut a frame, so only the opening and closing surveys run."""
    machine = live(frames(3), tmp_path)
    server.run_for(frames=3)
    assert sum(c.startswith("EXEC EV ") for c in machine.sent) == 2, machine.sent


def cut_on_the_second_frame(tmp_path: Path) -> Machine:
    machine = live(Machine(regs=dict(REAL_STOP), releases=[
        Stop(ms=FRAME_MS), Stop({"EIP": 0x108}, ms=3.0)]), tmp_path)
    _real_bp("0814:0108")
    machine.breakpoints.insert(0, "BP 0814:0108")
    return machine


def test_a_breakpoint_that_cuts_a_frame_ends_it_other_stop_and_leaves_the_retrace_pending(
        tmp_path: Path) -> None:
    """A `VRT` a breakpoint stops first stays armed, and the reply and the server say so."""
    cut_on_the_second_frame(tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=5, seconds=2))
    assert got["status"] == "ok", got
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert "breakpoint 0814:0108 " in got["cause"], got["cause"]
    assert got["retrace_pending"] is True and retrace.PENDING_NOTE in got["note"], got
    assert dstate.STATE.retrace_pending is True


def test_the_next_unattributed_stop_is_named_as_the_pending_retrace_and_forgets_it(
        tmp_path: Path) -> None:
    live(frames(3), tmp_path)
    dstate.STATE.retrace_pending = True
    where = {"cs": "0814", "eip": "00000106", "mode": "Real"}
    session = cast(ds.Session, dstate.STATE.session)
    kept = arming.attribute_stop(session, where=where, held=[])
    assert "retrace_pending" not in kept and dstate.STATE.retrace_pending is True
    named = arming.attribute_stop(session, where=where, held=[], retrace_may_stop=True)
    assert named["attributed"] is False and named["retrace_pending"] is True, named
    assert "run_for" in named["why"], named["why"]
    assert dstate.STATE.retrace_pending is False


def test_a_bound_that_expires_while_a_retrace_is_out_interrupts_the_run(tmp_path: Path) -> None:
    """A `VRT` still out at the bound is interrupted with `BREAK`; the retrace stays armed."""
    machine = live(Machine(regs=dict(REAL_STOP), releases=[None]), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=0.3))
    assert got["status"] == "ok", got
    assert got["verdict"] == "TIMEOUT" and got["polls"] == 0, got
    assert "BREAK" in machine.sent, machine.sent
    assert got["regs"] and "stop_seq" in got, "interrupted, the stop is surveyed"
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True
    assert got["cause"].startswith("run_for's 0.3 s bound ran out"), got["cause"]


def test_a_bound_reached_between_frames_is_a_timeout_at_rest(tmp_path: Path) -> None:
    """The check before the next `VRT` finds the bound spent, with the machine at rest."""
    machine = live(frames(100), tmp_path)
    machine.polls_before_stop = 2000
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=0.2))
    assert got["status"] == "ok" and got["verdict"] == "TIMEOUT", got
    assert got["regs"], "the stop reply is there"


def test_a_clock_that_did_not_move_is_no_progress(tmp_path: Path) -> None:
    live(Machine(regs=dict(REAL_STOP), releases=[Stop(ms=0.0)]), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["status"] == "INVALID" and got["code"] == "no_progress", got
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 1 and got["regs"], "the account and the stop ride on it"


def test_a_protected_mode_frame_reads_its_position_off_the_survey(tmp_path: Path) -> None:
    """The DPMI client's selector and 32-bit offset ride on the stop reply."""
    machine = protected(Machine(releases=[Stop({"EIP": 0xBAA28}, ms=FRAME_MS)]))
    install()
    dstate.STATE.session = session_over(machine, tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["status"] == "ok", got
    assert got["pc"] == "00A7:000BAA28", got


@pytest.mark.parametrize("args", [
    {}, {"frames": 0, "milliseconds": 0}, {"frames": 2, "milliseconds": 50}, {"frames": -1},
    {"frames": True}, {"milliseconds": -5}, {"milliseconds": 2.5}, {"milliseconds": True},
    {"milliseconds": 10 ** 400}, {"frames": 3, "seconds": 0},
    {"frames": 3, "seconds": vocab.WAIT_MAX_S + 1}])
def test_a_bad_argument_is_refused_before_the_session_gate(args: dict[str, Any]) -> None:
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.run_for(**args))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got


def test_a_running_guest_is_refused_and_nothing_is_sent_but_the_question(
        tmp_path: Path) -> None:
    machine = live(Machine(regs=dict(REAL_STOP), stopped=False), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["code"] == "not_stopped", got
    assert set(machine.sent) == {"EXEC RUNSTATE"}, machine.sent


def test_a_build_without_runstate_is_refused_before_a_retrace_goes_out(tmp_path: Path) -> None:
    machine = live(Machine(regs=dict(REAL_STOP), commands=()), tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["code"] == "no_channel" and "RUNSTATE" in got["message"], got
    assert "EXEC VRT" not in machine.sent


def test_a_sequence_reads_whether_run_for_left_the_machine_running() -> None:
    """A release that came back with a stop left the machine stopped; one without, running."""
    assert _leaves_running("run_for", {"verdict": "ELAPSED"}) is True
    assert _leaves_running("run_for", {"verdict": "TIMEOUT", "stop_seq": 3}) is False
    assert _leaves_running("run_for", {"enrichment": {"available": False, "why": "cut"}}) is False
    assert _leaves_running("registers", {}) is False


def _counting(n: int, at: int, tmp_path: Path) -> Machine:
    machine = frames(n)
    machine.frames = at
    return live(machine, tmp_path)


def test_a_stop_that_crossed_no_frame_is_not_named_the_retrace(tmp_path: Path) -> None:
    """An INT 3 under `break_on_int3`, or a raw `BP`, stops it short of the frame: no
    declaration explains it, and the frame that did not move says it was no retrace."""
    machine = frames(0)
    machine.releases = [Stop(ms=FRAME_MS, frames=0)]
    machine.frames = 100
    live(machine, tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["frame"] == 100 and "ran to" not in got["cause"], got["cause"]


def test_a_stop_recorded_without_its_reply_carries_no_earlier_stop_s_frame(
        tmp_path: Path) -> None:
    _counting(3, 100, tmp_path)
    assert server.run_for(frames=1)["frame"] == 101
    session = dstate.STATE.session
    assert session is not None
    dstate.STATE.remember_stop(session, {"cs": "0814", "eip": "00000108", "mode": "Real"}, {},
                               [], {"attributed": False})
    assert "frame" not in dstate.STATE.last_stop, dstate.STATE.last_stop["frame"]


def test_until_frame_repeats_the_list_until_a_stop_reads_the_frame(tmp_path: Path) -> None:
    _counting(10, 100, tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[{"op": "run_for", "frames": 1}],
                                              summaries=True, until_frame=104))
    assert got["status"] == "ok", got
    assert (got["until_frame"], got["frame_reached"], got["steps_completed"]) == (104, 104, 4)
    assert "frame 104 of 104" in got["summary"], got["summary"]


def test_until_frame_refuses_a_frame_behind_and_a_build_that_counts_none(tmp_path: Path) -> None:
    _counting(3, 100, tmp_path)
    behind = cast(dict[str, Any], server.perform(steps=[{"op": "run_for", "frames": 1}],
                                                 summaries=True, until_frame=100))
    assert behind["code"] == "bad_argument" and "stands at frame 100" in behind["message"]
    live(frames(3), tmp_path)
    blind = cast(dict[str, Any], server.perform(steps=[{"op": "run_for", "frames": 1}],
                                                summaries=True, until_frame=5))
    assert blind["code"] == "no_channel" and "frames=" in blind["message"], blind


def test_perform_goes_on_at_once_after_a_run_for_its_bound_interrupted(tmp_path: Path) -> None:
    """A timed-out `run_for` hands the machine back stopped, so the next step runs at once."""
    machine = live(Machine(regs=dict(REAL_STOP), releases=[None]), tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_for", "frames": 1, "seconds": 0.3}, {"op": "registers"}], settle_seconds=5))
    assert got["status"] == "ok", got
    assert got["steps_completed"] == 2, got
    assert "BREAK" in machine.sent and dstate.STATE.retrace_pending is True, machine.sent


def test_a_declared_code_breakpoint_carries_the_dynamic_core_limit(tmp_path: Path) -> None:
    """On a dynamic core a late code breakpoint can miss, so `ELAPSED` does not prove unreached."""
    live(frames(1), tmp_path)
    _real_bp("0000:0002")
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["verdict"] == "ELAPSED", got
    assert "dynamic core" in got["note"] and "run_to" in got["note"], got["note"]
    live(frames(3), tmp_path)               # the control: a fresh store, nothing declared
    plain = cast(dict[str, Any], server.run_for(frames=3))
    assert "dynamic core" not in str(plain.get("note")), plain


def test_a_resume_that_stops_where_nothing_is_declared_names_the_pending_retrace(
        tmp_path: Path) -> None:
    """The release that ran on is the one the pending retrace stops: `resume`'s own stop."""
    live(frames(1), tmp_path)
    dstate.STATE.retrace_pending = True
    got = cast(dict[str, Any], server.resume(seconds=1.0))
    assert "stop_seq" in got, got
    assert got["cause"].startswith("most likely the retrace stop"), got["cause"]
    assert dstate.STATE.retrace_pending is False


def test_the_opening_read_forgets_the_pending_retrace_only_once_a_vrt_has_gone_out(
        tmp_path: Path) -> None:
    machine = live(frames(1), tmp_path)
    dstate.STATE.retrace_pending = True
    got = cast(dict[str, Any], server.run_for(frames=1, seconds=0.3))
    assert got["verdict"] == "ELAPSED" and got["polls"] == 1, got
    assert vrts(machine) == ["EXEC VRT"]
    assert dstate.STATE.retrace_pending is False


def test_a_retrace_is_a_release_the_session_follows(tmp_path: Path) -> None:
    """Sending `VRT` clears the stopped flag, as `RUN` does."""
    live(frames(1), tmp_path)
    session = cast(ds.Session, dstate.STATE.session)
    session.release(ds.RETRACE_COMMAND)
    assert session.parked is False


def test_a_cut_on_the_last_frame_is_named_by_the_stop_reply(tmp_path: Path) -> None:
    cut_on_the_second_frame(tmp_path)
    got = cast(dict[str, Any], server.run_for(frames=2, seconds=2))
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_stop_a_declaration_explains_keeps_the_retrace_pending(tmp_path: Path) -> None:
    live(frames(3), tmp_path)
    _real_bp("0814:0108")
    dstate.STATE.retrace_pending = True
    got = arming.attribute_stop(cast(ds.Session, dstate.STATE.session),
                                where={"cs": "0814", "eip": "00000108", "mode": "Real"},
                                held=[{"index": "0", "entry": "BP 0814:0108"}],
                                retrace_may_stop=True)
    assert got["attributed"] is True and dstate.STATE.retrace_pending is True, got


def test_a_session_s_end_forgets_its_armed_retrace() -> None:
    dstate.STATE.retrace_pending = True
    dstate.STATE.clear_running_state()
    assert dstate.STATE.retrace_pending is False


def test_an_interrupt_breakpoint_says_its_stop_counts_as_a_frame(tmp_path: Path) -> None:
    live(frames(3), tmp_path)
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(
        arming.declare("interrupt", "address", grammar.interrupt_row(0x21, None)))
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=2))
    assert retrace.UNTOLD_NOTE in got["note"], got
    assert "which declaration fired cannot be told" in got["cause"], "something could stop it"


def test_perform_refuses_a_bad_run_for_step_before_anything_is_sent(tmp_path: Path) -> None:
    machine = live(frames(3), tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[
        {"op": "status"}, {"op": "run_for", "frames": 0}]))
    assert got["code"] == "bad_argument", got
    assert machine.sent == [], machine.sent


def test_milliseconds_run_retrace_by_retrace_until_the_clock_has_risen_that_far(
        tmp_path: Path) -> None:
    """Two frames are under 30 ms of emulated time and three are over it."""
    machine = live(frames(5), tmp_path)
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert got["status"] == "ok", got
    assert got["verdict"] == "ELAPSED" and got["polls"] == 3, got
    assert vrts(machine) == ["EXEC VRT"] * 3
    assert got["summary"].startswith("run_for 30 ms: ELAPSED"), got["summary"]


def test_a_retrace_that_did_not_move_the_clock_ends_a_timed_run_no_progress(
        tmp_path: Path) -> None:
    live(Machine(regs=dict(REAL_STOP), releases=[Stop(ms=0.0), Stop(ms=FRAME_MS)]), tmp_path)
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert got["status"] == "INVALID" and got["code"] == "no_progress", got
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 1, "the first frame that did not move ends it"


def test_a_timed_run_that_stalls_after_moving_says_where_the_clock_stopped(
        tmp_path: Path) -> None:
    """The refusal names the frame that did not move the clock, not "nothing was emulated"."""
    live(Machine(regs=dict(REAL_STOP), releases=[Stop(ms=FRAME_MS), Stop(ms=0.0)]), tmp_path)
    got = cast(dict[str, Any], server.run_for(milliseconds=100, seconds=2))
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 2, got
    assert "nothing was emulated" not in got["message"], got["message"]
    assert f"{0.7 + FRAME_MS:.2f}"[:4] in got["message"], got["message"]


def test_a_breakpoint_cuts_a_timed_run_too(tmp_path: Path) -> None:
    cut_on_the_second_frame(tmp_path)
    got = cast(dict[str, Any], server.run_for(milliseconds=100, seconds=2))
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_timed_run_reads_each_frame_s_clock_from_the_stop_it_waited_for(
        tmp_path: Path) -> None:
    """The clock comes with the stop: a frame costs its `VRT` and its `RUNSTATE`, no survey."""
    machine = live(frames(5), tmp_path)
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert sum(c.startswith("EXEC EV ") for c in machine.sent) == 2, machine.sent
    assert got["polls"] == 3


def test_a_snapshot_of_a_stopped_machine_reads_this_stop_and_never_runs_it(
        tmp_path: Path) -> None:
    """The guest route would have to run the machine to draw a frame; a stop is read from video
    memory (the decoder's cases are `test_dosbox_x_screen.py`'s)."""
    machine = live(frames(1), tmp_path)
    got = cast(dict[str, Any], server.snapshot())
    assert got["code"] != "not_running", got
    assert any(c.startswith("EXEC VGA MODE") for c in machine.sent), machine.sent
    assert vrts(machine) == [] and "EXEC RUN" not in machine.sent, "nothing ran"
