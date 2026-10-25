"""`run_for` by display retraces, against a double replaying captures from `fixtures/vrt/`."""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar, cast

import pytest
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from test_dosbox_x_debug import RESUME_HALTED, Debugger
from test_dosbox_x_server import clean_session, install  # noqa: F401  (the autouse teardown)

import dosbox_arming as arming
import dosbox_console as dcons
import dosbox_retrace as retrace
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server
from dosbox_sequence import _leaves_running

VRT = Path(__file__).parent / "fixtures" / "vrt"


def cap(name: str) -> str:
    return (VRT / f"{name}.txt").read_text()


class Retraces(Debugger):
    """The debugger's side of a `VRT`: a typed one queues its captured delta after `lag` empty
    polls, taking `delay_s` to arrive. `running` is a machine the console does not answer."""

    def __init__(self, panes: list[str], vrts: list[str], *, lag: int = 0,
                 delay_s: float = 0.0, running: bool = False, survey_s: float = 0.0,
                 deltas: list[str] | None = None) -> None:
        super().__init__(panes, deltas=deltas)
        self.survey_s = survey_s
        self.vrts = list(vrts)
        self.lag = lag
        self.delay_s = delay_s
        self.running = running
        self.launch = SimpleNamespace(logfile=None, watched=True, input_port=None)

    def _write(self, data: bytes) -> None:
        super()._write(data)
        if data == ds.RETRACE_COMMAND and self.vrts:
            self.reads.extend([""] * self.lag + [self.vrts.pop(0)])

    def _read(self, seconds: float = 0.0) -> str:
        chunk = self.reads.pop(0) if self.reads else ""
        time.sleep(self.delay_s if chunk else seconds)
        return chunk

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return not self.running and self._at_debugger

    def command(self, text: str, **k: object) -> str:
        if text == ds.NUDGE:
            time.sleep(self.survey_s)
        return super().command(text, **k)

    def retrace(self, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return ds.Session.retrace(cast(ds.Session, self), began, deadline, progress)


Double = TypeVar("Double", bound=Debugger)


def live(double: Double) -> Double:
    """The double as `start` leaves a session, its park already recorded as the last stop."""
    install()
    dstate.STATE.session = cast(ds.Session, double)
    dstate.STATE.remember_stop(cast(ds.Session, double),
                               {"cs": "0814", "eip": "00000106", "mode": "Real"}, {}, [],
                               {"attributed": False})
    return double


def three_frames() -> Retraces:
    return Retraces([cap("probe-survey-0"), cap("probe-survey-3")],
                    [cap("probe-vrt-1"), cap("probe-vrt-2"), cap("probe-vrt-3")])


def _real_bp(ref: str) -> None:
    """A raw breakpoint at the real-mode stop the probe guest sits at."""
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", ref, cpu=dcons.REAL_MODE))


def test_three_frames_land_three_retraces_with_the_whole_stop_reply() -> None:
    dbg = live(three_frames())
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert got["status"] == "ok", got
    assert got["verdict"] == "ELAPSED" and got["polls"] == 3, got
    assert dbg.keys == [ds.RETRACE_COMMAND] * 3, "one VRT per frame, typed as a release"
    assert got["pc"].endswith(":00000106"), got
    assert got["emulated_before_s"] == pytest.approx(0.005708)
    assert got["emulated_after_s"] == pytest.approx(0.0485122)
    assert got["frame_before"]["available"] is False and got["frame_after"]["available"] is False
    assert "normal core" in got["cycles"]["why"], got
    assert got["regs"] and "cause" in got and "e9" in got and "stop_seq" in got
    assert got["session"]["altered"] is False, "advancing is not writing"
    assert got["summary"].startswith("run_for 3 frames: ELAPSED"), got["summary"]


def test_the_stop_run_for_lands_on_carries_the_e9_block_even_with_no_log() -> None:
    """With no logfile the block is the unavailable shape, naming why."""
    live(three_frames())
    got = cast(dict[str, Any], server.run_for(frames=3))
    assert got["status"] == "ok" and got["e9"]["available"] is False, got["e9"]
    assert "logfile" in got["e9"]["why"], got["e9"]


def test_with_nothing_that_can_cut_it_no_frame_is_surveyed() -> None:
    """Fast path: nothing declared can cut a frame, so only the opening and closing surveys run."""
    dbg = live(three_frames())
    server.run_for(frames=3)
    assert dbg.sent.count(ds.NUDGE) == 2, dbg.sent


def cut_on_the_second_frame() -> Retraces:
    dbg = Retraces([cap("probe-survey-0"), cap("probe-survey-1"),
                    cap("probe-survey-cut-by-bp-0108"), cap("probe-survey-cut-by-bp-0108")],
                   [cap("probe-vrt-1"), cap("probe-vrt-cut-by-bp-0108")])
    live(dbg)
    _real_bp("0814:0108")
    return dbg


def test_a_breakpoint_that_cuts_a_frame_ends_it_other_stop_and_leaves_the_retrace_pending() -> None:
    """A `VRT` a breakpoint stops first stays armed, and the reply and the server say so."""
    cut_on_the_second_frame()
    got = cast(dict[str, Any], server.run_for(frames=5, seconds=2))
    assert got["status"] == "ok", got
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert "breakpoint 0814:0108 " in got["cause"], got["cause"]
    assert got["retrace_pending"] is True and retrace.PENDING_NOTE in got["note"], got
    assert dstate.STATE.retrace_pending is True


def test_the_next_unattributed_stop_is_named_as_the_pending_retrace_and_forgets_it() -> None:
    live(three_frames())
    dstate.STATE.retrace_pending = True
    where = {"cs": "0814", "eip": "00000106", "mode": "Real"}
    kept = arming.attribute_stop(cast(ds.Session, dstate.STATE.session), where=where, held=[])
    assert "retrace_pending" not in kept and dstate.STATE.retrace_pending is True, (
        "a stop the caller made itself (a step, a menu stop, an arrival) is its own, and the "
        "retrace is still pending after it: only a release that ran on may consume it")
    named = arming.attribute_stop(cast(ds.Session, dstate.STATE.session), where=where,
                                  held=[], retrace_may_stop=True)
    assert named["attributed"] is False and named["retrace_pending"] is True, named
    assert "run_for" in named["why"], named["why"]
    assert dstate.STATE.retrace_pending is False


def test_a_bound_that_expires_while_a_retrace_is_out_interrupts_the_run() -> None:
    """A `VRT` still out at the bound is interrupted with `BREAK`; the retrace stays armed."""
    dbg = live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), cap("probe-survey-1")],
                        [cap("probe-vrt-1")], lag=40))
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=0.3))
    assert got["status"] == "ok", got
    assert got["verdict"] == "TIMEOUT" and got["polls"] == 0, got
    assert "BREAK" in dbg.sent, dbg.sent
    assert got["regs"] and "stop_seq" in got, "interrupted, the stop is surveyed"
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_bound_reached_between_frames_is_a_timeout_at_rest() -> None:
    """The check before the third `VRT` finds the bound spent, with the machine at rest."""
    live(Retraces([cap("probe-survey-0"), cap("probe-survey-2")],
                  [cap("probe-vrt-1"), cap("probe-vrt-2")], delay_s=0.15))
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=0.2))
    assert got["status"] == "ok", got
    assert got["verdict"] == "TIMEOUT" and got["polls"] == 2, got
    assert got["regs"], "stopped between frames: the stop reply is there"
    assert "retrace_pending" not in got


def test_a_pane_clock_that_did_not_move_is_no_progress() -> None:
    live(Retraces([cap("probe-survey-1"), cap("probe-survey-1")], [cap("probe-vrt-1")]))
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["status"] == "INVALID" and got["code"] == "no_progress", got
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 1 and got["regs"], "the account and the stop ride on it"


def test_a_protected_mode_frame_reads_its_position_off_the_survey() -> None:
    """dos-djgpp32: the DPMI client's selector and 32-bit offset ride on the stop reply."""
    live(Retraces([cap("dos-djgpp32-survey-4"), cap("dos-djgpp32-survey-5")],
                  [cap("dos-djgpp32-vrt-5")]))
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


def test_a_running_guest_is_refused_and_nothing_is_typed() -> None:
    dbg = live(Retraces([], [cap("probe-vrt-1")], running=True))
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["code"] == "not_stopped", got
    assert dbg.keys == [] and dbg.sent == []


def test_a_sequence_reads_whether_run_for_left_the_machine_running() -> None:
    """A release that came back with a stop left the machine stopped; one without, running."""
    assert _leaves_running("run_for", {"verdict": "ELAPSED"}) is True
    assert _leaves_running("run_for", {"verdict": "TIMEOUT", "stop_seq": 3}) is False
    assert _leaves_running("run_for", {"enrichment": {"available": False, "why": "cut"}}) is False
    assert _leaves_running("registers", {}) is False


def test_perform_goes_on_at_once_after_a_run_for_its_bound_interrupted() -> None:
    """A timed-out `run_for` hands the machine back stopped, so the next step runs at once."""
    live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), cap("probe-survey-1"),
                   cap("probe-survey-1")], [cap("probe-vrt-1")], lag=40))
    dbg = cast(Retraces, dstate.STATE.session)
    got = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_for", "frames": 1, "seconds": 0.3}, {"op": "registers"}], settle_seconds=5))
    assert got["status"] == "ok", got
    assert got["steps_completed"] == 2, got
    assert "BREAK" in dbg.sent and dstate.STATE.retrace_pending is True, dbg.sent


def test_a_declared_code_breakpoint_carries_the_dynamic_core_limit() -> None:
    """On a dynamic core a late code breakpoint can miss, so `ELAPSED` does not prove unreached."""
    live(Retraces([cap("probe-survey-0"), cap("probe-survey-1")], [cap("probe-vrt-1")]))
    _real_bp("0000:0002")
    got = cast(dict[str, Any], server.run_for(frames=1))
    assert got["verdict"] == "ELAPSED", got
    assert "dynamic core" in got["note"] and "run_to" in got["note"], got["note"]
    live(three_frames())                    # the control: a fresh store, nothing declared
    plain = cast(dict[str, Any], server.run_for(frames=3))
    assert "dynamic core" not in str(plain.get("note")), plain


def test_a_resume_that_stops_where_nothing_is_declared_names_the_pending_retrace() -> None:
    """The release that ran on is the one the pending retrace stops: `resume`'s own stop."""
    live(Retraces([cap("probe-survey-1")] * 3, [], deltas=[RESUME_HALTED]))
    dstate.STATE.retrace_pending = True
    got = cast(dict[str, Any], server.resume())
    assert "stop_seq" in got, got
    assert got["cause"].startswith("most likely the retrace stop"), got["cause"]
    assert dstate.STATE.retrace_pending is False


def test_the_opening_survey_is_not_charged_to_the_frames() -> None:
    """The deadline starts once the machine is placed; the pending retrace is forgotten only
    when a `VRT` has gone out."""
    dbg = live(Retraces([cap("probe-survey-0"), cap("probe-survey-1")], [cap("probe-vrt-1")],
                        survey_s=0.4))
    dstate.STATE.retrace_pending = True
    got = cast(dict[str, Any], server.run_for(frames=1, seconds=0.3))
    assert got["verdict"] == "ELAPSED" and got["polls"] == 1, got
    assert dbg.keys == [ds.RETRACE_COMMAND]
    assert dstate.STATE.retrace_pending is False


def test_a_cut_is_remembered_even_when_the_final_survey_is_cut() -> None:
    """The cut is known once the frame's survey names the breakpoint."""
    cut_on_the_second_frame()
    dbg = cast(Retraces, dstate.STATE.session)
    dbg.panes[-1] = ""                           # the stop reply's survey comes back empty
    got = cast(dict[str, Any], server.run_for(frames=5))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["polls"] == 2 and got["enrichment"]["available"] is False, got
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_retrace_is_a_release_the_session_follows() -> None:
    """Sending `VRT` clears the stopped flag, as a run key does."""
    dbg = live(three_frames())
    dbg._at_debugger = True
    ds.Session._release(cast(ds.Session, dbg), ds.RETRACE_COMMAND)
    assert dbg._at_debugger is False


def test_a_cut_on_the_last_frame_is_named_by_the_stop_reply() -> None:
    dbg = Retraces([cap("probe-survey-0"), cap("probe-survey-1"),
                    cap("probe-survey-cut-by-bp-0108")],
                   [cap("probe-vrt-1"), cap("probe-vrt-cut-by-bp-0108")])
    live(dbg)
    _real_bp("0814:0108")
    got = cast(dict[str, Any], server.run_for(frames=2, seconds=2))
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_stop_a_declaration_explains_keeps_the_retrace_pending() -> None:
    live(three_frames())
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


def test_an_interrupt_breakpoint_says_its_stop_counts_as_a_frame() -> None:
    live(three_frames())
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("interrupt", "address", dcons.interrupt_row(0x21, None)))
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=2))
    assert retrace.UNTOLD_NOTE in got["note"], got


def test_perform_refuses_a_bad_run_for_step_before_anything_is_typed() -> None:
    dbg = live(three_frames())
    got = cast(dict[str, Any], server.perform(steps=[
        {"op": "status"}, {"op": "run_for", "frames": 0}]))
    assert got["code"] == "bad_argument", got
    assert dbg.keys == [] and dbg.sent == []


def test_milliseconds_run_retrace_by_retrace_until_the_pane_clock_has_risen_that_far() -> None:
    """The captured clock is under 30 ms after the second retrace and over it after the third."""
    dbg = live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), cap("probe-survey-2"),
                         cap("probe-survey-3"), cap("probe-survey-3")],
                        [cap("probe-vrt-1"), cap("probe-vrt-2"), cap("probe-vrt-3")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert got["status"] == "ok", got
    assert got["verdict"] == "ELAPSED" and got["polls"] == 3, got
    assert dbg.keys == [ds.RETRACE_COMMAND] * 3
    assert got["emulated_before_s"] == pytest.approx(0.005708)
    assert got["emulated_after_s"] == pytest.approx(0.0485122)
    assert got["summary"].startswith("run_for 30 ms: ELAPSED"), got["summary"]


def test_a_retrace_that_did_not_move_the_clock_ends_a_timed_run_no_progress() -> None:
    live(Retraces([cap("probe-survey-1"), cap("probe-survey-1"), cap("probe-survey-1")],
                  [cap("probe-vrt-1"), cap("probe-vrt-2")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert got["status"] == "INVALID" and got["code"] == "no_progress", got
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 1, "the first frame that did not move ends it"


def test_a_timed_run_needs_a_clock_to_start_from() -> None:
    """With no `pfi=` to count from, the run is refused before any retrace goes out."""
    no_clock = cap("probe-survey-0").replace("pfi=", "pfx=")
    dbg = live(Retraces([no_clock], [cap("probe-vrt-1")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    contract.check_refusal("run_for", got, "unexpected_answer")
    assert dbg.keys == []


def test_a_timed_run_that_stalls_after_moving_says_where_the_clock_stopped() -> None:
    """The refusal names the frame that did not move the clock, not "nothing was emulated"."""
    live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), cap("probe-survey-1"),
                   cap("probe-survey-1")], [cap("probe-vrt-1"), cap("probe-vrt-2")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=100, seconds=2))
    contract.check_refusal("run_for", got, "no_progress")
    assert got["polls"] == 2, got
    assert "nothing was emulated" not in got["message"], got["message"]
    assert "19.9761" in got["message"], got["message"]


def test_a_frame_whose_survey_painted_no_clock_is_read_at_the_next() -> None:
    """One repaint without `pfi=` mid-run does not end it."""
    no_clock = cap("probe-survey-2").replace("pfi=", "pfx=")
    live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), no_clock,
                   cap("probe-survey-3"), cap("probe-survey-3")],
                  [cap("probe-vrt-1"), cap("probe-vrt-2"), cap("probe-vrt-3")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert got["status"] == "ok" and got["verdict"] == "ELAPSED" and got["polls"] == 3, got


def test_a_breakpoint_cuts_a_timed_run_too() -> None:
    dbg = Retraces([cap("probe-survey-0"), cap("probe-survey-1"),
                    cap("probe-survey-cut-by-bp-0108"), cap("probe-survey-cut-by-bp-0108")],
                   [cap("probe-vrt-1"), cap("probe-vrt-cut-by-bp-0108")])
    live(dbg)
    _real_bp("0814:0108")
    got = cast(dict[str, Any], server.run_for(milliseconds=100, seconds=2))
    assert got["verdict"] == "OTHER_STOP" and got["polls"] == 2, got
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True


def test_a_timed_run_surveys_each_frame_once_and_the_stop_once() -> None:
    dbg = live(Retraces([cap("probe-survey-0"), cap("probe-survey-1"), cap("probe-survey-2"),
                         cap("probe-survey-3"), cap("probe-survey-3")],
                        [cap("probe-vrt-1"), cap("probe-vrt-2"), cap("probe-vrt-3")]))
    got = cast(dict[str, Any], server.run_for(milliseconds=30, seconds=2))
    assert dbg.sent.count(ds.NUDGE) == 1 + got["polls"] + 1, dbg.sent


class LandsAtTheBound(Retraces):
    """The wait gives up with the `VRT` out, but its stop lands before the interrupt looks."""

    def retrace(self, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        self._at_debugger = True
        return True, 0.0


def test_a_retrace_that_lands_as_the_bound_expires_is_spent_not_pending() -> None:
    dbg = live(LandsAtTheBound([cap("probe-survey-0"), cap("probe-survey-1")], []))
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=5))
    assert got["verdict"] == "TIMEOUT" and "BREAK" not in dbg.sent, (got, dbg.sent)
    assert "retrace_pending" not in got and dstate.STATE.retrace_pending is False, got


class CutAtTheBound(Retraces):
    """A declared breakpoint stops the machine after the wait gave up, so the `VRT` stays armed."""

    def retrace(self, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        super().retrace(began, deadline, progress)
        return True, 0.0


def test_a_breakpoint_that_lands_as_the_bound_expires_leaves_the_retrace_pending() -> None:
    dbg = live(CutAtTheBound([cap("probe-survey-0"), cap("probe-survey-cut-by-bp-0108"),
                              cap("probe-survey-cut-by-bp-0108")],
                             [cap("probe-vrt-cut-by-bp-0108")]))
    _real_bp("0814:0108")
    got = cast(dict[str, Any], server.run_for(frames=3, seconds=5))
    assert "BREAK" not in dbg.sent and got["verdict"] == "OTHER_STOP", (got, dbg.sent)
    assert got["retrace_pending"] is True and dstate.STATE.retrace_pending is True, got
