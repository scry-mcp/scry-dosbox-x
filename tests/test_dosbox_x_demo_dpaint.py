"""The Deluxe Paint demo's checks, without an emulator."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed

from demos.dpaint import demo


def test_the_word_passes_only_when_every_step_of_it_ran() -> None:
    run = Run(dir=Path("."))
    assert demo.WORD in demo.typed(Reply({"steps_completed": 4, "failed_at": None}), run)
    with pytest.raises(StepFailed):
        demo.typed(Reply({"steps_completed": 2, "failed_at": 2}), run)
