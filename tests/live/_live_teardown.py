"""Autouse teardown for live tests that use the declaration store."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

import dosbox_state as dstate
import dosbox_x_server as server


def _drop() -> None:
    """Close the session, clear the globals even if close threw, fail on a stray."""
    session = dstate.STATE.session
    if session is None:
        dstate.STATE.store = None
        return
    proc = session.proc
    reply: dict[str, Any] = {}
    try:
        reply = cast(dict[str, Any], server.close())
    finally:
        dstate.STATE.session = None
        dstate.STATE.store = None
        stray = _kill_if_still_there(proc)
    if stray:
        raise AssertionError(stray)
    code = reply.get("exit_code")
    if isinstance(code, dict):
        raise AssertionError(f"an emulator may still be running after close: {code.get('why')}")


def _kill_if_still_there(proc: subprocess.Popen[bytes]) -> str:
    """SIGKILL the process group if close left it; return the failure text."""
    if proc.poll() is not None:
        return ""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return (f"the emulator (pid {proc.pid}) was still running after close and did "
                f"not die within 5 s of SIGKILL: it is still on the machine")
    return (f"the emulator (pid {proc.pid}) was still running after close returned; "
            f"the teardown killed it, and the case that left it is the defect")


@pytest.fixture(autouse=True)
def no_session_left_behind(tmp_path: Path,
                           monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Declarations persist to disk keyed by conf and would re-arm at the next start.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _drop()
    yield
    _drop()
