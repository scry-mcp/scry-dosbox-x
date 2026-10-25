"""Every way the server ends closes the live session; DOSBox-X has its own process session."""

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
from dosbox_mcp import LOCK


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
    # a second signal must not cut the end short
    assert all(signal.getsignal(s) == signal.SIG_IGN for s in server.EXIT_SIGNALS)


def test_the_signalled_end_waits_for_a_held_lock_only_so_long(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any]) -> None:
    """A tool holding the lock does not keep the emulator alive past `LOCK_WAIT_S`."""
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
    """`start` publishes the session only once up, so the end must reach the starting one too."""
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


def test_the_servers_end_and_a_signalled_one_close_the_session_once(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any]) -> None:
    """Two threads reach one session; its close body runs once (a second would re-signal)."""
    import dosbox_session as ds

    bodies: list[float] = []

    def slow_close(self: ds.Session, grace: float = 8.0, progress: Any = None) -> int:
        bodies.append(time.monotonic())
        time.sleep(0.5)
        return 0

    ses = ds.Session.__new__(ds.Session)
    ses._closing, ses._closed, ses.reap_failed = threading.Lock(), False, ""
    ses.proc = type("Proc", (), {"returncode": 0})()
    monkeypatch.setattr(ds.Session, "_close", slow_close)
    monkeypatch.setattr(dstate.STATE, "session", ses)
    monkeypatch.setattr(server, "LOCK_WAIT_S", 0.2)
    # the signal must land while `main`'s end holds the lock, else it closes first
    later = threading.Timer(0.1, server._end_signalled, args=(128 + signal.SIGTERM,))
    monkeypatch.setattr(server.mcp, "run", later.start)
    try:
        server.main()
    finally:
        # a signalled end still running at teardown would reach the real `_leave`
        later.join()
        ending["left"].wait(5.0)
    assert ending["left"].wait(5.0), "the signalled end never left"
    assert len(bodies) == 1, f"{len(bodies)} closes of one session"


def test_a_close_whose_reap_failed_is_finished_by_the_next_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A close whose emulator was not reaped (`reap_failed`) is retried by the next one."""
    import dosbox_session as ds

    bodies: list[int] = []

    def close_once_unreaped(self: ds.Session, grace: float = 8.0, progress: Any = None) -> int:
        bodies.append(1)
        self.reap_failed = "not reaped" if len(bodies) == 1 else ""
        return 0

    ses = ds.Session.__new__(ds.Session)
    ses._closing, ses._closed, ses.reap_failed = threading.Lock(), False, ""
    ses.proc = type("Proc", (), {"returncode": 0})()
    monkeypatch.setattr(ds.Session, "_close", close_once_unreaped)
    ses.close()
    ses.close()
    ses.close()
    assert len(bodies) == 2, bodies


def test_a_signalled_end_waits_for_the_tool_holding_the_lock_before_closing(
        monkeypatch: pytest.MonkeyPatch, ending: dict[str, Any]) -> None:
    """A tool holding the lock finishes before the emulator is closed under it."""
    closed: list[float] = []
    ses = type("Held", (), {"close": lambda self: closed.append(time.monotonic())})()
    monkeypatch.setattr(dstate.STATE, "session", ses)
    monkeypatch.setattr(server, "LOCK_WAIT_S", 5.0)
    released: list[float] = []
    held = threading.Event()

    def a_tool() -> None:              # another thread's tool: the lock is re-entrant
        with LOCK:
            held.set()
            time.sleep(0.3)
            released.append(time.monotonic())
    tool = threading.Thread(target=a_tool)
    tool.start()
    held.wait(5.0)
    try:
        server._end_signalled(128 + signal.SIGTERM)
    finally:
        tool.join()
    assert closed and released and closed[0] >= released[0], (closed, released)
