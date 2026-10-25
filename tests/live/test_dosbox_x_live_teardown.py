"""The live teardown without an emulator (a `sleep`): no `live` marker, runs in the default tier."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any

import pytest
from _live_teardown import _drop

import dosbox_state as dstate


class _ClosesWithoutEnding:
    """A close that reports a clean quit while its process runs on."""

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self.proc = proc
        self.reap_failed = ""
        self.ended_how = "none"
        self.launch = SimpleNamespace(logfile=None)

    def state(self) -> dict[str, object]:
        return {"alive": True, "pid": self.proc.pid}

    def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
        self.ended_how = "quit"
        return 0

    def console_tail(self, chars: int) -> str:
        return ""


def test_a_process_close_left_running_is_killed_and_the_case_is_told() -> None:
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        dstate.STATE.session = _ClosesWithoutEnding(proc)  # type: ignore[assignment]
        with pytest.raises(AssertionError, match="still running after close"):
            _drop()
        assert proc.poll() is not None, "the stray was not killed"
        assert dstate.STATE.session is None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_a_close_that_ended_its_process_raises_nothing() -> None:
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    session = _ClosesWithoutEnding(proc)

    def close_for_real(grace: float = 8.0, progress: Any = None) -> int | None:
        proc.kill()
        proc.wait(timeout=5)
        return _ClosesWithoutEnding.close(session, grace)

    session.close = close_for_real  # type: ignore[method-assign]
    dstate.STATE.session = session  # type: ignore[assignment]
    _drop()
    assert proc.poll() is not None and dstate.STATE.session is None
