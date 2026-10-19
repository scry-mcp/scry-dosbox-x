"""A step's `recorded`: what a session's reply said, which the replay's `perform` holds the step's
own reply to. A mismatch stops the list there as INVALID `diverged`, naming the field, what was
recorded and what came back (`failed_at`, as any step failure); a match is an ordinary step."""

from __future__ import annotations

import pathlib
import sys
from typing import Any

from scry_core import demo, replay

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from test_dosbox_x_server import clean_session, install  # noqa: E402,F401

import dosbox_x_server as server  # noqa: E402


def _regs(recorded: Any) -> dict[str, Any]:
    return {"op": "registers", "recorded": recorded}


def test_a_step_that_holds_to_what_was_recorded_runs_as_any_step() -> None:
    install()
    regs = server.registers()["registers"]
    out = server.perform(steps=[_regs({"registers": regs}), _regs({"registers": regs})])
    assert out["status"] == "ok" and out["completed"] == 2, out
    assert out["held"] == 2, "each step held to its recorded answer is counted"


def test_a_step_that_does_not_hold_stops_the_list_as_diverged() -> None:
    install()
    regs = server.registers()["registers"]
    out = server.perform(steps=[_regs({"registers": regs}),
                                _regs({"registers": {**regs, "EAX": "DEADBEEF"}}),
                                _regs({"registers": regs})])
    assert out["status"] == "INVALID" and out["code"] == "diverged", out
    assert out["failed_at"] == 1 and out["completed"] == 1
    assert out["field"] == "registers" and out["got"] == regs
    assert out["failed"]["op"] == "registers" and out["failed"]["reply"]["registers"] == regs
    assert "step 1 ('registers') diverged" in out["message"]
    assert out["held"] == 1, "the step before the divergence held, the diverged one did not"


def test_the_replay_runner_reads_this_servers_own_diverged_reply(tmp_path: pathlib.Path) -> None:
    """The contract between this server's `perform` and the runner (`scry_core.replay`): the
    reply a diverged step gives is the one the runner names the step and the field from, never
    an exit 3 for a reply it cannot read."""
    install()
    regs = server.registers()["registers"]
    steps = [_regs({"registers": regs}), _regs({"registers": {**regs, "EAX": "DEADBEEF"}})]
    out = server.perform(steps=steps)
    said = replay._failed(steps)(out, demo.Run(dir=tmp_path))
    assert said.startswith("diverged at step 2 of 2 (registers): registers recorded "), said


def test_recorded_never_reaches_the_tool() -> None:
    install()
    out = server.perform(steps=[_regs({})])
    assert out["status"] == "ok" and out["held"] == 0, "an empty `recorded` holds to nothing"


def test_a_recorded_that_is_not_a_mapping_is_refused_before_any_step_runs() -> None:
    install()
    out = server.perform(steps=[{"op": "registers"}, _regs(["registers"])])
    assert out["code"] == "bad_argument" and out.get("completed", 0) == 0, out
    assert "recorded" in out["message"]
