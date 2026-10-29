"""The Deluxe Paint screen-map demo's checks, without an emulator."""

from __future__ import annotations

import pytest
from scry_core.demo import Reply, StepFailed

from demos.dpaint_maps import demo


def test_a_call_that_completed_every_step_passes() -> None:
    demo.completed(Reply({"failed_at": {"available": False, "why": "no step failed"},
                          "steps_completed": 3}))


@pytest.mark.parametrize("failed_at", [2, {"step": 2, "op": "send_mouse"}])
def test_a_call_that_failed_a_step_fails_the_demo_whatever_shape_it_says_so_in(
        failed_at: object) -> None:
    with pytest.raises(StepFailed):
        demo.completed(Reply({"failed_at": failed_at, "steps_completed": 2}))
