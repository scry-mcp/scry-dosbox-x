"""The server's end is the emulator's: however the server goes (its client closes stdin, or a
SIGTERM, SIGHUP or SIGINT ends it), the live session is closed on the way out and the process's
scratch with it. DOSBox-X runs in a process session of its own, so a signal to the server's group
never reaches it: only the server can end it."""

from __future__ import annotations

import signal
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

import dosbox_mcp
import dosbox_state as dstate
import dosbox_x_server as server


class _Live:
    def __init__(self, raises: bool = False) -> None:
        self.closed = 0
        self.raises = raises

    def close(self, *a: Any, **k: Any) -> int:
        self.closed += 1
        if self.raises:
            raise OSError("the emulator would not be reaped")
        return 0


@pytest.fixture
def ending(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """The signalled end, observed: what `_leave` was asked, whether the scratch went first."""
    saved = {s: signal.getsignal(s) for s in server.EXIT_SIGNALS}
    seen: dict[str, Any] = {"exits": [], "scratch": 0, "left": threading.Event()}

    def leave(code: int) -> None:
        seen["exits"].append((code, seen["scratch"]))
        seen["left"].set()

    def remove_scratch() -> None:
        seen["scratch"] += 1
    monkeypatch.setattr(server, "_leave", leave)
    monkeypatch.setattr(dstate, "remove_scratch", remove_scratch)
    yield seen
    for s, handler in saved.items():
        signal.signal(s, handler if handler is not None else signal.SIG_DFL)


def test_a_server_whose_client_left_closes_the_session(monkeypatch: pytest.MonkeyPatch,
                                                       ending: dict[str, Any]) -> None:
    ses = _Live()
    monkeypatch.setattr(dstate.STATE, "session", ses)
    installed: list[Any] = []
    monkeypatch.setattr(server.mcp, "run",
                        lambda: installed.extend(signal.getsignal(s) for s in server.EXIT_SIGNALS))
    server.main()
    assert installed and all(h is server._exit_on for h in installed), installed
    assert ses.closed == 1 and dstate.STATE.session is None
    assert ending["exits"] == []


@pytest.mark.parametrize("name", [n for n in ("SIGTERM", "SIGHUP", "SIGINT") if hasattr(signal, n)])
def test_a_signal_ends_the_session_removes_the_scratch_and_leaves(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any], name: str) -> None:
    ses = _Live()
    monkeypatch.setattr(dstate.STATE, "session", ses)
    sig = getattr(signal, name)
    server._exit_on(sig, None)
    assert ending["left"].wait(5.0), "the signalled end never left"
    assert ending["exits"] == [(128 + sig, 1)], ending["exits"]
    assert ses.closed == 1 and dstate.STATE.session is None
    # A second signal while the end runs must not cut it short.
    assert all(signal.getsignal(s) == signal.SIG_IGN for s in server.EXIT_SIGNALS)


def test_the_signalled_end_waits_for_a_held_lock_only_so_long(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any]) -> None:
    """A tool that holds the lock through a long wait does not keep the emulator alive: the end
    closes it without the lock once its wait for it is over."""
    ses = _Live()
    monkeypatch.setattr(dstate.STATE, "session", ses)
    monkeypatch.setattr(server, "LOCK_WAIT_S", 0.2)
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with dosbox_mcp.LOCK:
            held.set()
            release.wait(10.0)
    holder = threading.Thread(target=hold)
    holder.start()
    held.wait(5.0)
    began = time.monotonic()
    try:
        server._exit_on(signal.SIGTERM, None)
        assert ending["left"].wait(5.0), "the end waited on the lock for ever"
    finally:
        release.set()
        holder.join()
    assert time.monotonic() - began < 3.0 and ses.closed == 1


def test_a_close_that_fails_is_said_and_the_end_still_removes_the_scratch_and_leaves(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any],
        capfd: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(dstate.STATE, "session", _Live(raises=True))
    server._exit_on(signal.SIGTERM, None)
    assert ending["left"].wait(5.0)
    assert ending["exits"] == [(128 + signal.SIGTERM, 1)], ending["exits"]
    assert "could not be closed on the way out" in capfd.readouterr().err


def test_a_signal_while_start_waits_for_its_emulator_ends_that_emulator(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any]) -> None:
    """`start` holds the lock while the emulator it launched comes up, and publishes the session
    only once it has: the end reaches the one still starting too, or it outlives the server."""
    starting = _Live()
    monkeypatch.setattr(dstate.STATE, "session", None)
    monkeypatch.setattr(dstate.STATE, "starting", starting)
    monkeypatch.setattr(server, "LOCK_WAIT_S", 0.2)
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with dosbox_mcp.LOCK:
            held.set()
            release.wait(10.0)
    holder = threading.Thread(target=hold)
    holder.start()
    held.wait(5.0)
    try:
        server._exit_on(signal.SIGTERM, None)
        assert ending["left"].wait(5.0)
    finally:
        release.set()
        holder.join()
    assert starting.closed == 1
