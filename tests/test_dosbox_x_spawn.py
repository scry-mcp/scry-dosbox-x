"""What `_spawn` brings up, against an emulator double that dials the port the argv names: the
process in a group of its own (a hidden console of its own on Windows), its output on a pipe
when the debugger is headless and on a terminal nobody reads when it is not, the guardian over
that process, the drain thread, the input route and its link, and a failed start that takes
everything down in order."""

from __future__ import annotations

import os
import plistlib
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import app_launch, guardian

from scry_dosbox_x import control
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import session as ds

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="Windows gives a console, not a tty")


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
        out = kw.get("stdout")
        self.tty = isinstance(out, int) and os.isatty(out)
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
    if ses._drainer is not None:
        ses._drainer.join(1)
    for s in (ses._input, ses.control):
        if s is not None:
            s.close()
    if ses._out is not None:
        os.close(ses._out)
        ses._out = None                        # so a later `_close` does not close it again


def launch(conf: Path, tmp_path: Path, **kw: Any) -> dlaunch.Launch:
    return dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, **{"debugger_headless": True, **kw})


def test_a_headless_spawn_puts_the_output_on_a_pipe_and_the_emulator_on_its_own(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path, input_port=0))
    try:
        port = ses.launch.input_port
        assert port and f"port:{port}" in " ".join(emu.argv), emu.argv
        kw = emu.kw
        assert kw["cwd"] == str(tmp_path) and kw["close_fds"] is True
        assert kw["stdin"] is subprocess.DEVNULL and kw["stdout"] == kw["stderr"]
        assert isinstance(kw["stdout"], int) and emu.tty is False
        if sys.platform == "win32":
            assert kw["creationflags"] == subprocess.CREATE_NEW_CONSOLE
            assert kw["startupinfo"].wShowWindow == 0
        else:
            assert kw["start_new_session"] is True
        assert emu.guarded == [emu.child] and cast(Any, ses.guard) == "guard"
        assert ses._drainer is not None and ses._drainer.daemon is True
        assert ses._drainer.name == "dosbox-drain"
        assert ses._input is not None and ses._link is not None and ses._link.sock is ses._input
        assert ses._input.getpeername() == emu.dialled[0].getsockname()
    finally:
        _done(ses)
        emu.close()


@POSIX
def test_a_spawn_without_headless_gets_a_terminal_nobody_reads(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A debugger with a screen stops only on a terminal: all three streams are one."""
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path, debugger_headless=False))
    try:
        kw = emu.kw
        assert kw["stdin"] == kw["stdout"] == kw["stderr"] and emu.tty is True, kw
    finally:
        _done(ses)


@pytest.mark.skipif(sys.platform != "win32", reason="the console is Windows'")
def test_a_spawn_without_headless_on_windows_keeps_the_hidden_console_s_streams(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path, debugger_headless=False))
    try:
        assert not {"stdin", "stdout", "stderr"} & set(emu.kw), emu.kw
        assert emu.kw["startupinfo"].wShowWindow == 0 and ses._drainer is None
    finally:
        _done(ses)


def test_a_fixed_port_is_kept_and_no_port_means_no_route(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path, input_port=port))
    try:
        assert ses.launch.input_port == port
    finally:
        _done(ses)
        emu.close()
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path))
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
        ds.Session(launch(conf, tmp_path, input_port=port))
    dlaunch.listen_input(port).close()


def test_a_failed_start_stops_the_drain_before_closing_its_read_end(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emu = Emulator(monkeypatch, dial=False)
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
    ended = threading.Event()

    def drain(self: ds.Session) -> None:
        time.sleep(0.3)
        ended.set()
    monkeypatch.setattr(ds.Session, "_drain", drain)
    closed_after_drain: list[bool] = []
    real_close, real_pipe = os.close, os.pipe
    fds: dict[str, int] = {}

    def pipe() -> tuple[int, int]:
        r, w = real_pipe()
        fds.setdefault("read", r)          # the output's; a later pipe is a subprocess's own
        return r, w
    monkeypatch.setattr(os, "pipe", pipe)

    def closing(fd: int) -> None:
        if fd == fds.get("read"):
            closed_after_drain.append(ended.is_set())
        real_close(fd)
    monkeypatch.setattr(os, "close", closing)
    with pytest.raises(ds.Invalid):
        ds.Session(launch(conf, tmp_path, input_port=0))
    assert closed_after_drain == [True], closed_after_drain
    assert emu.child.waits == [5], emu.child.waits


def test_a_failed_start_of_an_emulator_already_gone_sends_no_kill(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emu = Emulator(monkeypatch, child=Child(3), dial=False)
    sent: list[int] = []
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: sent.append(sig))
    began = time.monotonic()
    with pytest.raises(ds.Invalid):
        ds.Session(launch(conf, tmp_path, input_port=0))
    assert sent == [] and emu.child.waits == []
    assert time.monotonic() - began < 2.0, "it waited out the dial bound for a dead emulator"


def test_an_emulator_gone_before_it_dialled_the_debugger_channel_is_said_at_once(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child = Child()
    Emulator(monkeypatch, child=child)
    ses = ds.Session(launch(conf, tmp_path))
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
            ds.Session(launch(conf, tmp_path, input_port=0))
        assert time.monotonic() - began < 4.0, "a stuck drain held the failed start"
    finally:
        stuck.set()


def test_a_write_end_that_will_not_close_neither_masks_a_failure_nor_fails_a_start(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_close, real_pipe = os.close, os.pipe
    opened: list[int] = []

    def pipe() -> tuple[int, int]:
        r, w = real_pipe()
        opened[:] = [w]
        return r, w
    monkeypatch.setattr(os, "pipe", pipe)

    def refusing(fd: int) -> None:
        real_close(fd)
        if fd in opened:
            raise OSError(9, "EBADF")
    monkeypatch.setattr(os, "close", refusing)
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path))
    _done(ses)
    emu.close()
    Emulator(monkeypatch, dial=False)
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
    with pytest.raises(ds.Invalid, match="never dialled the serial input port"):
        ds.Session(launch(conf, tmp_path, input_port=0))


def _app_bundle(tmp_path: Path) -> Path:
    """A `.app` whose plist names an emulator; nothing is spawned from what it holds."""
    contents = tmp_path / "Probe.app" / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "MacOS" / "dosbox-x").write_text("#!/bin/sh\n")
    (contents / "Info.plist").write_bytes(plistlib.dumps(
        {"CFBundleExecutable": "dosbox-x", "CFBundlePackageType": "APPL"}))
    return tmp_path / "Probe.app"


@pytest.mark.skipif(sys.platform != "darwin", reason="an app bundle is macOS's")
def test_a_bundle_launches_through_open_into_the_session_s_own_cwd(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`open` starts the app, two `-set`s put it in `cwd`, and the pid is the app's own."""
    children: list[Any] = []
    monkeypatch.setattr(guardian, "spawn", lambda child, *a, **k: children.append(child))
    monkeypatch.setattr(guardian, "stop", lambda guard: None)
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: None)

    def no_popen(*a: Any, **k: Any) -> Any:
        raise AssertionError("Popen was used for the app route")

    monkeypatch.setattr(subprocess, "Popen", no_popen)
    seen: dict[str, Any] = {}

    def run_open(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(app_launch, "run_open", run_open)
    monkeypatch.setattr(app_launch, "find_pid", lambda token, timeout: 4242)
    bundle = _app_bundle(tmp_path)
    ses = ds.Session(launch(conf, tmp_path, bundle=str(bundle),
                            binary=str(bundle / "Contents" / "MacOS" / "dosbox-x")))
    try:
        assert isinstance(ses.proc, app_launch.AppProcess), ses.proc
        assert ses.proc.pid == 4242
        cmd = seen["cmd"]
        assert cmd[:4] == ["/usr/bin/open", "-n", "-a", str(bundle)], cmd
        assert "-i" not in cmd and "-o" not in cmd, "the app route carries no channel of ours"
        argv = cmd[cmd.index("--args") + 1:]
        overlay = Path(argv[argv.index("-conf", argv.index("-conf") + 1) + 1])
        assert overlay.read_text(encoding="utf-8") == (
            f"[dosbox]\nworking directory option=force\nworking directory default={tmp_path}\n")
        assert not any("working directory" in word for word in argv), argv
        assert ses._drainer is None and ses.captures_output is False
        assert children == [ses.proc], "the guardian watches the app's pid"
        assert ses.state()["bundle"] == str(bundle)
    finally:
        _done(ses)


def test_a_plain_binary_goes_through_popen_and_never_through_open(
        conf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: the route is taken only by a session that asked for it."""

    def boom(cmd: list[str]) -> Any:
        raise AssertionError("open was called for a plain binary")

    monkeypatch.setattr(app_launch, "run_open", boom)
    emu = Emulator(monkeypatch)
    ses = ds.Session(launch(conf, tmp_path))
    try:
        assert emu.argv and "-conf" in emu.argv
        assert not isinstance(ses.proc, app_launch.AppProcess)
        assert "bundle" not in ses.state()
    finally:
        _done(ses)
        emu.close()
