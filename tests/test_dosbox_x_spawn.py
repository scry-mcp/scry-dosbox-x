"""What `_spawn` brings up, against an emulator double that dials the port the argv names: the
terminal with its echo off and nothing else changed, the process in a group of its own with the
terminal on its three streams, the guardian over that process, the drain thread, the input
route and its link, and a failed start that takes everything down in order."""

from __future__ import annotations

import contextlib
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import guardian

import dosbox_control as control
import dosbox_launch as dlaunch
import dosbox_session as ds

if sys.platform != "win32":
    import termios

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="a session spawns on a pseudo-terminal, which Windows lacks")


class Child:
    pid = 4242

    def __init__(self, code: int | None = None) -> None:
        self.code = code
        self.waits: list[float | None] = []

    @property
    def returncode(self) -> int | None:
        return self.code

    def poll(self) -> int | None:
        return self.code

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        return 0


class Emulator:
    """`subprocess.Popen` as the session calls it: it records the argv and the keywords, and
    dials the serial port the argv names, as the emulator does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, child: Child | None = None,
                 dial: bool = True) -> None:
        self.child = child or Child()
        self.argv: list[str] = []
        self.kw: dict[str, Any] = {}
        self.dialled: list[socket.socket] = []
        self.dial = dial
        self.guarded: list[Any] = []
        self.real = subprocess.Popen
        monkeypatch.setattr(subprocess, "Popen", self)
        monkeypatch.setattr(guardian, "spawn", self.guard)
        monkeypatch.setattr(guardian, "stop", lambda guard: None)
        monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: None)

    def guard(self, child: Any, *_: Any, **__: Any) -> Any:
        self.guarded.append(child)
        return "guard"

    def __call__(self, argv: list[str], **kw: Any) -> Any:
        if "-conf" not in argv:                 # not the emulator: the ledger's `ps`, say
            return self.real(argv, **kw)
        self.argv, self.kw = list(argv), kw
        port = re.search(r"port:(\d+)", " ".join(argv))
        if port and self.dial:
            s = socket.socket()
            s.connect(("127.0.0.1", int(port.group(1))))
            self.dialled.append(s)
        return self.child

    def close(self) -> None:
        for s in self.dialled:
            s.close()


@pytest.fixture
def conf(tmp_path: Path) -> Path:
    path = tmp_path / "g.conf"
    path.write_text("[sdl]\n", encoding="utf-8")
    return path


def _done(ses: ds.Session) -> None:
    ses._stop.set()
    if ses._drainer is not None:
        ses._drainer.join(1)
    for s in (ses._input, ses.control):
        if s is not None:
            s.close()
    with contextlib.suppress(OSError):
        os.close(ses._master)
    ses._master_closed = True                 # so a later `_close` does not close it again


def test_a_spawn_runs_the_emulator_in_its_own_group_on_the_terminal(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":  # the module is skipped there; this is what mypy reads
        emu = Emulator(monkeypatch)
        seen: list[list[Any]] = []
        real = termios.tcsetattr

        def recorded(fd: int, when: int, attrs: list[Any]) -> None:
            seen.append([list(termios.tcgetattr(fd)), list(attrs)])
            real(fd, when, attrs)
        monkeypatch.setattr(termios, "tcsetattr", recorded)
        ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=0))
        try:
            port = ses.launch.input_port
            assert port and f"port:{port}" in " ".join(emu.argv), emu.argv
            kw = emu.kw
            assert kw["cwd"] == str(tmp_path) and kw["start_new_session"] is True
            assert kw["close_fds"] is True and kw["stdin"] == kw["stdout"] == kw["stderr"]
            assert isinstance(kw["stdin"], int)
            (before, after), = seen
            mask = termios.ECHO | termios.ECHONL | termios.ECHOE | termios.ECHOK
            assert after[3] == before[3] & ~mask, (before, after)
            assert after[:3] + after[4:] == before[:3] + before[4:], (before, after)
            assert emu.guarded == [emu.child] and cast(Any, ses.guard) == "guard"
            assert ses._drainer is not None and ses._drainer.is_alive()
            assert ses._drainer.daemon is True and ses._drainer.name == "dosbox-drain"
            assert ses._input is not None and ses._link is not None and ses._link.sock is ses._input
            assert ses._input.getpeername() == emu.dialled[0].getsockname()
        finally:
            _done(ses)
            emu.close()


def test_a_fixed_port_is_kept_and_no_port_means_no_route(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    emu = Emulator(monkeypatch)
    ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    try:
        assert ses.launch.input_port == port
    finally:
        _done(ses)
        emu.close()
    emu = Emulator(monkeypatch)
    ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30))
    try:
        assert ses._input is None and ses._link is None
        with pytest.raises(ds.Invalid, match="no input route"):
            ses.send_commands([b"R"])
    finally:
        _done(ses)
    ses.proc = Child(0)  # type: ignore[assignment]
    ses._close()


def test_a_start_whose_control_channel_fails_raises_that_and_frees_the_port(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Emulator(monkeypatch)

    def refused(*_: Any) -> None:
        raise OSError("no port")
    monkeypatch.setattr(control, "ControlChannel", refused)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(OSError, match="no port"):
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    dlaunch.listen_input(port).close()


def test_a_failed_start_stops_the_drain_before_closing_its_terminal(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":  # the module is skipped there; this is what mypy reads
        emu = Emulator(monkeypatch, dial=False)
        monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
        ended = threading.Event()

        def drain(self: ds.Session) -> None:
            self._stop.wait()
            time.sleep(0.3)
            ended.set()
        monkeypatch.setattr(ds.Session, "_drain", drain)
        master_closed_after_drain: list[bool] = []
        real_close = os.close
        fds: dict[str, int] = {}
        real_openpty = os.openpty

        def openpty() -> tuple[int, int]:
            m, s = real_openpty()
            fds["master"] = m
            return m, s
        monkeypatch.setattr("pty.openpty", openpty)

        def closing(fd: int) -> None:
            if fd == fds.get("master"):
                master_closed_after_drain.append(ended.is_set())
            real_close(fd)
        monkeypatch.setattr(os, "close", closing)
        with pytest.raises(ds.Invalid):
            ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=0))
        assert master_closed_after_drain == [True], master_closed_after_drain
        assert emu.child.waits == [5], emu.child.waits


def test_a_failed_start_of_an_emulator_already_gone_sends_no_kill(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emu = Emulator(monkeypatch, child=Child(3), dial=False)
    sent: list[int] = []
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: sent.append(sig))
    began = time.monotonic()
    with pytest.raises(ds.Invalid):
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=0))
    assert sent == [] and emu.child.waits == []
    assert time.monotonic() - began < 2.0, "it waited out the dial bound for a dead emulator"


def test_an_emulator_gone_before_it_dialled_the_debugger_channel_is_said_at_once(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child()
    Emulator(monkeypatch, child=child)
    ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30))
    try:
        child.code = 3
        began = time.monotonic()
        with pytest.raises(ds.Invalid, match=r"exited \(code 3\) without dialling"):
            ses.control._connected()
        assert time.monotonic() - began < 2.0, "it waited out the dial bound for a dead emulator"
    finally:
        _done(ses)


def test_a_failed_start_whose_drain_will_not_stop_still_returns(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    Emulator(monkeypatch, dial=False)
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
    stuck = threading.Event()
    monkeypatch.setattr(ds.Session, "_drain", lambda self: stuck.wait())
    began = time.monotonic()
    try:
        with pytest.raises(ds.Invalid):
            ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=0))
        assert time.monotonic() - began < 4.0, "a stuck drain held the failed start"
    finally:
        stuck.set()


def test_a_terminal_that_will_not_close_neither_masks_a_failure_nor_fails_a_start(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":  # the module is skipped there; this is what mypy reads
        real_close = os.close
        opened: list[int] = []
        real_openpty = os.openpty

        def openpty() -> tuple[int, int]:
            m, s = real_openpty()
            opened[:] = [m, s]
            return m, s
        monkeypatch.setattr("pty.openpty", openpty)

        def refusing(fd: int) -> None:
            real_close(fd)
            if fd in opened:
                raise OSError(9, "EBADF")
        monkeypatch.setattr(os, "close", refusing)
        emu = Emulator(monkeypatch)
        ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30))
        _done(ses)
        emu.close()
        Emulator(monkeypatch, dial=False)
        monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
        with pytest.raises(ds.Invalid, match="never dialled the serial input port"):
            ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=0))
