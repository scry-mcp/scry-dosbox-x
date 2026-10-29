"""A step's `recorded` is held to the replay reply; a mismatch is INVALID `diverged`."""

from __future__ import annotations

import pathlib
import sys
from typing import Any

from scry_core import demo, replay

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dosbox_x_server_support import clean_session, install  # noqa: E402,F401

from scry_dosbox_x import server  # noqa: E402


def _regs(recorded: Any) -> dict[str, Any]:
    return {"op": "registers", "recorded": recorded}


def test_a_step_that_holds_to_what_was_recorded_runs_as_any_step() -> None:
    install()
    regs = server.registers()["regs"]
    out = server.perform(steps=[_regs({"regs": regs}), _regs({"regs": regs})])
    assert out["status"] == "ok" and out["steps_completed"] == 2, out
    assert out["held"] == 2, "each step held to its recorded answer is counted"


def test_a_step_that_does_not_hold_stops_the_list_as_diverged() -> None:
    install()
    regs = server.registers()["regs"]
    out = server.perform(steps=[_regs({"regs": regs}),
                                _regs({"regs": {**regs, "EAX": "DEADBEEF"}}),
                                _regs({"regs": regs})])
    assert out["status"] == "INVALID" and out["code"] == "diverged", out
    assert out["failed_at"] == 1 and out["steps_completed"] == 1
    assert out["field"] == "regs" and out["got"] == regs
    assert out["failed"]["op"] == "registers" and out["failed"]["reply"]["regs"] == regs
    assert "step 2 ('registers') diverged" in out["message"]
    assert out["held"] == 1, "the step before the divergence held, the diverged one did not"


def test_the_replay_runner_reads_this_servers_own_diverged_reply(tmp_path: pathlib.Path) -> None:
    """The replay runner names the step and field from this server's diverged reply."""
    install()
    regs = server.registers()["regs"]
    steps = [_regs({"regs": regs}), _regs({"regs": {**regs, "EAX": "DEADBEEF"}})]
    out = server.perform(steps=steps)
    said = replay._failed(steps)(out, demo.Run(dir=tmp_path))
    assert said.startswith("diverged at step 2 of 2 (registers): regs recorded "), said


def test_recorded_never_reaches_the_tool() -> None:
    install()
    out = server.perform(steps=[_regs({})])
    assert out["status"] == "ok" and out["held"] == 0, "an empty `recorded` holds to nothing"


def test_a_recorded_that_is_not_a_mapping_is_refused_before_any_step_runs() -> None:
    install()
    out = server.perform(steps=[{"op": "registers"}, _regs(["regs"])])
    assert out["code"] == "bad_argument" and out["steps_completed"] == 0, out
    assert "recorded" in out["message"]
