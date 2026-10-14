"""Shared teardown for the live tests that use the DECLARATION STORE.

The name-layer and stop-reply files each start a session AND populate the store, so both
have to clear `_STORE` as well as `_SESSION` between cases -- and both surface a stray
emulator, because `close` reports `reap_failed` when a SIGKILLed child was not reaped and
swallowing it would leave one running with nothing said. Written once here rather than in
each file: it was the same twenty lines twice, which is the duplication this fleet gates.

The store-using files IMPORT `no_session_left_behind` from here, which registers it as their
own autouse fixture. The ENTRY-ROUTE file uses it too now: its walks call
`breakpoint_interrupt`, which stores an interrupt declaration, so it needs the same store
clearing and the same XDG isolation as the others -- keeping its own near-identical teardown
was the duplication this fleet gates (the dup gate caught it). It is a plain module and not a
`conftest.py` on purpose: a second `conftest` in the tree is a duplicate module name to the
type checker, which the shared import sidesteps.
"""
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
    """Close whatever session is installed and clear both globals even if closing threw,
    then make sure of the PROCESS: the fixture holds the handle the session spawned, so
    an emulator that `close` left running is killed here with it, and the case is told.

    The globals are cleared UNCONDITIONALLY. `dosbox_x_server.close()` nulls the session
    only after `Session.close()` returns, and an `OSError` or a `TimeoutExpired` out of
    the teardown would otherwise leave the module pointing at a live emulator and poison
    every later case in both setup and teardown. And a stray is SAID, never swallowed: a
    case that fails must leave no emulator, and one that did is a defect of the tier.
    """
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
    if reply.get("reap_failed"):
        raise AssertionError(f"an emulator may still be running after close: "
                             f"{reply['reap_failed']}")


def _kill_if_still_there(proc: subprocess.Popen[bytes]) -> str:
    """SIGKILL the session's own process group if `close` did not end it, and say what was
    found: empty when nothing was left, else the account the case fails with. The handle
    is the session's, so nothing is searched for on the machine."""
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
    # ISOLATE THE STORE: interrupt breakpoints and every by-name declaration persist to
    # disk keyed by conf, so without this a live run would write into the caller's own state
    # dir and re-arm those declarations at the next real `start` of the same conf -- a stop
    # nobody asked for. The store-using tests also set XDG in their own body; this covers
    # the entry-route walks, which do not.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _drop()
    yield
    _drop()
