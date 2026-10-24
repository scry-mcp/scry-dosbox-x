"""The emulator's process as `close` meets it: the wait for its exit and what that wait reports, a
real `Process` from its defaults, the terminal's drain over a pipe, and what a close takes down
(the presence writer, the guardian, the input socket, a drainer that will not stop)."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import threading
import time
from typing import Any

import pytest
from scry_core import guardian

import dosbox_process as dprocess
import dosbox_session as ds


class _Clock:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.now = 1000.0
        monkeypatch.setattr(time, "monotonic", lambda: self.now)


class _Deaf:
    """A child whose `wait` spends its timeout on the clock and answers only once it has lived
    `term_s` past SIGTERM or `kill_s` past SIGKILL; `None` never."""

    def __init__(self, clock: _Clock, term_s: float | None, kill_s: float | None) -> None:
        self.clock, self.term_s, self.kill_s = clock, term_s, kill_s
        self.returncode: int | None = None
        self.sent: list[int] = []
        self.at = clock.now
        self.timeouts: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def signal(self, sig: int) -> None:
        self.sent.append(sig)
        if sig == 9 or len(self.sent) == 1:
            self.at = self.clock.now

    def wait(self, timeout: float | None = None) -> int:
        self.timeouts.append(timeout)
        assert timeout is not None, "an unbounded wait on a child that may never leave"
        self.clock.now += timeout
        killed = 9 in self.sent
        due = self.kill_s if killed else self.term_s
        if due is not None and self.clock.now - self.at >= due:
            self.returncode = -9 if killed else 0
            return self.returncode
        raise subprocess.TimeoutExpired(cmd="dosbox-x", timeout=timeout)


def _process(proc: Any, **fields: Any) -> dprocess.Process:
    p = dprocess.Process()
    p.proc = proc
    p._master = -1
    p._signal_group = proc.signal  # type: ignore[method-assign]
    for k, v in fields.items():
        setattr(p, k, v)
    return p


def test_a_wait_for_the_exit_ticks_once_a_second_in_bounded_slices(
        monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(monkeypatch)
    child = _Deaf(clock, 3.5, None)
    child.signal(15)
    said: list[tuple[float, Any, str]] = []
    assert dprocess.wait_exit(child, 5.0, lambda *a: said.append(a),  # type: ignore[arg-type]
                              "w") == 0
    assert 1 <= len(said) <= 4 and all(t is None for _, t, _ in said), said
    assert all(0 < p < 5.0 for p, _, _ in said) and said[0][0] == pytest.approx(1.0), said
    assert said[0][2] == "w, 1s of 5s", said
    assert all(t is not None and t <= dprocess.EXIT_POLL_S for t in child.timeouts)
    never = _Deaf(clock, None, None)
    assert dprocess.wait_exit(never, 0.5, lambda *a: None, "w") is None  # type: ignore[arg-type]


def test_a_new_process_holds_nothing_and_closes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(monkeypatch)
    child = _Deaf(clock, 0.0, None)
    p = _process(child)
    assert (p.dropped, p.drain_ended, p.reap_failed, p._closed) == (0, "", "", False)
    assert p._take() == b"" and p.ended_how == "none"
    p.close()
    assert p.ended_how == "quit" and child.sent == [15], child.sent
    p.close()
    assert child.sent == [15], "a closed session was signalled again"


@pytest.mark.parametrize(("grace", "said"), [
    (None, "SIGKILL was sent and the process had not been reaped 8.0s later"),
    (0, "SIGKILL was sent and the process had not been reaped 1.0s later")])
def test_an_unreaped_child_is_reported_with_the_wait_it_had(
        monkeypatch: pytest.MonkeyPatch, grace: float | None, said: str) -> None:
    clock = _Clock(monkeypatch)
    p = _process(_Deaf(clock, None, None))
    if grace is None:
        p.close()
    else:
        p.close(grace)
    assert p.reap_failed == said, p.reap_failed


def test_a_close_reports_both_waits_in_its_own_words(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(monkeypatch)
    p = _process(_Deaf(clock, None, 1.5))
    said: list[str] = []
    p.close(progress=lambda *a: said.append(str(a[-1])))
    assert said[0] == "close: waiting for the emulator to leave on SIGTERM, 1s of 2s", said
    assert "close: waiting for the SIGKILLed emulator to be reaped, 1s of 8s" in said, said
    assert p.ended_how == "killed" and p.reap_failed == ""


def test_a_cancelled_close_still_reaps_and_is_not_run_again(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_core import cancel
    clock = _Clock(monkeypatch)
    child = _Deaf(clock, None, 0.5)
    p = _process(child)

    def cancelled(*_: Any) -> None:
        raise asyncio.CancelledError()
    with pytest.raises(BaseException) as gone:
        p.close(progress=cancelled)
    assert cancel.is_cancellation(gone.value), gone.value
    assert p.ended_how == "killed" and child.returncode == -9
    sent = list(child.sent)
    p.close()
    assert child.sent == sent, "a cancelled close that reaped was run again"
    assert p.ended_how == "killed", "a cancelled close that reaped was run again"


def test_a_close_stops_the_presence_and_the_guardian_and_drops_the_input_route(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_core import presence
    clock = _Clock(monkeypatch)
    order: list[str] = []

    class Seen(presence.Shown):
        def close(self) -> None:
            order.append("presence")
    child = _Deaf(clock, 0.0, None)
    signal = child.signal

    def signalled(sig: int) -> None:
        order.append("signal")
        signal(sig)
    child.signal = signalled  # type: ignore[method-assign]
    stopped: list[Any] = []
    monkeypatch.setattr(guardian, "stop", stopped.append)
    a, b = socket.socketpair()
    p = _process(child, presence=Seen(), guard="G", _input=a, _link=object())
    try:
        p._close()
        assert order[:2] == ["presence", "signal"], order
        assert stopped == ["G"] and a.fileno() == -1
        assert p._input is None and p._link is None
        p._close()
        with pytest.raises(ds.Invalid, match="no input route"):
            ds.Session.send_commands(p, [b"R"])  # type: ignore[arg-type]
    finally:
        b.close()
    deaf = _Deaf(clock, None, None)
    stopped.clear()
    _process(deaf)._close()
    assert stopped == [], "the guardian was stopped while the emulator was not reaped"


def test_a_socket_that_will_not_close_does_not_stop_the_close(
        monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(monkeypatch)

    class Stuck:
        def close(self) -> None:
            raise OSError("busy")
    r, w = os.pipe()
    os.close(w)
    p = _process(_Deaf(clock, 0.0, None), _input=Stuck())
    p._master = r
    p._close()
    with pytest.raises(OSError):
        os.fstat(r)


def test_a_drainer_that_will_not_stop_leaves_the_descriptor_open_and_says_so(
        monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(monkeypatch)
    monkeypatch.setattr(dprocess, "DRAIN_JOIN_SECS", 0.2)
    hold = threading.Event()
    stuck = threading.Thread(target=hold.wait, daemon=True)
    stuck.start()
    r, w = os.pipe()
    try:
        p = _process(_Deaf(clock, 0.0, None), _drainer=stuck)
        p._master = r
        worker = threading.Thread(target=p._close, daemon=True)
        began = time.perf_counter()
        worker.start()
        worker.join(5)
        assert not worker.is_alive() and time.perf_counter() - began < 1.0
        assert p.drain_ended.startswith("the drain thread did not stop within 0.2 s")
        os.fstat(r)                                    # still open, on purpose
    finally:
        hold.set()
        os.close(r)
        os.close(w)


# ------------------------------------------------------------- the drain over a pipe

def _draining() -> tuple[dprocess.Process, int, threading.Thread]:
    p = dprocess.Process()
    r, w = os.pipe()
    p._master = r
    t = threading.Thread(target=p._drain, daemon=True)
    t.start()
    return p, w, t


def _until(cond: Any) -> None:
    end = time.perf_counter() + 3
    while not cond() and time.perf_counter() < end:
        time.sleep(0.01)


def test_the_drain_gathers_while_idle_and_says_how_it_ended() -> None:
    p, w, t = _draining()
    try:
        os.write(w, b"ab")
        _until(lambda: bytes(p._buf) == b"ab")
        time.sleep(0.2)                               # idle, longer than a select slice
        os.write(w, b"cd")
        _until(lambda: bytes(p._buf) == b"abcd")
        assert p._take() == b"abcd" and t.is_alive() and not p._eof.is_set()
        p._stop.set()
        t.join(0.5)
        assert not t.is_alive() and p.drain_ended == "stopped deliberately by close()"
        assert p._eof.is_set()
    finally:
        os.close(w)
        os.close(p._master)
    p, w, t = _draining()
    os.close(w)
    t.join(1)
    assert p.drain_ended == "the descriptor reached end of file" and p._eof.is_set()
    os.close(p._master)


def test_the_drain_names_a_select_or_a_read_that_failed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    p = dprocess.Process()
    p._master = -1
    p._drain()
    assert p.drain_ended.startswith("select on the terminal failed") and p._eof.is_set()

    def broken(fd: int, n: int) -> bytes:
        raise OSError(5, "EIO")
    p, w, t = _draining()
    with monkeypatch.context() as failing:
        failing.setattr(os, "read", broken)
        os.write(w, b"x")
        t.join(1)
    assert p.drain_ended.startswith("reading the terminal failed") and p._eof.is_set()
    os.close(w)
    os.close(p._master)


def test_the_drain_keeps_the_newest_bytes_and_counts_what_it_dropped(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dprocess, "DRAIN_KEEP", 8)
    p, w, t = _draining()
    try:
        os.write(w, b"12345678")
        _until(lambda: len(p._buf) == 8)
        assert p.dropped == 0
        os.write(w, b"9")
        _until(lambda: p.dropped == 1)
        assert p.dropped == 1
        os.write(w, b"ABCDE")
        _until(lambda: p.dropped == 6)
        assert p.dropped == 6 and p._take() == b"789ABCDE"
    finally:
        p._stop.set()
        t.join(1)
        os.close(w)
        os.close(p._master)
