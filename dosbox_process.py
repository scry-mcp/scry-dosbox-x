from __future__ import annotations

import contextlib
import os
import select
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Any

from scry_core import cancel, guardian, live_host
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress
from scry_core.reply_contract import Invalid

import dosbox_control as control
import dosbox_launch as dlaunch
import dosbox_presence as dpresence
import dosbox_stub_link as stub_link

#: Why no session starts on Windows: the debugger's screen is read through a POSIX terminal.
NO_TERMINAL = ("no DOSBox-X session can start on Windows: this server reads the emulator's "
               "debugger through a POSIX pseudo-terminal, which Windows does not have, and the "
               "channel that would take its place there is not implemented yet")


#: Whether this host gives a session its terminal; the unit suite's doubles stand in for one.
HAS_TERMINAL = sys.platform != "win32"


def refuse_without_a_terminal() -> None:
    """`host_failed` on a host with no pseudo-terminal, before anything is started."""
    if not HAS_TERMINAL:
        raise Invalid("host_failed", NO_TERMINAL)


def _terminal() -> tuple[int, int]:
    """A pseudo-terminal's two ends, the emulator's with its echo off."""
    if sys.platform == "win32":
        raise Invalid("host_failed", NO_TERMINAL)
    else:
        import pty
        import termios

        master, slave = pty.openpty()
        try:
            attrs = termios.tcgetattr(slave)
            attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ECHOE | termios.ECHOK)
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
        except BaseException:
            os.close(master)
            os.close(slave)
            raise
        return master, slave


#: Names in the host's process list.
PROCESS_NAME = "scry-dosbox-x"
GUARDIAN_NAME = guardian.name_of(PROCESS_NAME)
#: Guardian deadline past the bound, on the host's clock (`-time-limit` counts emulated time).
GUARDIAN_GRACE_S = 10.0

# A thread drains the terminal: a full pty buffer blocks the emulator in the kernel, freezing
# the machine between questions. DRAIN_KEEP is a memory ceiling, larger than
# `dosbox_session.SCREEN_KEEP`; reaching it is reported (`_read` refuses the reading).
DRAIN_KEEP = 4 * 1024 * 1024

DRAIN_JOIN_SECS = 2.0

# Small: with the quit warning off a guest answers SIGTERM at once, so what ignores it is deaf.
TERM_GRACE = 2.0

EXIT_POLL_S = 0.1


def wait_exit(proc: subprocess.Popen[Any], seconds: float, progress: Progress,
              what: str) -> int | None:
    """The process's exit code within `seconds`, or None, reporting progress while it waits."""
    t0 = time.monotonic()
    next_tick = t0 + PROGRESS_EVERY_S
    while True:
        cancel.check()
        try:
            return int(proc.wait(timeout=EXIT_POLL_S))
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if now - t0 >= seconds:
            return None
        if now >= next_tick:
            next_tick = now + PROGRESS_EVERY_S
            progress(now - t0, None, f"{what}, {now - t0:.0f}s of {seconds:g}s")


class Process:
    """The emulator's process, terminal and sockets."""

    #: The guardian beside the emulator (`scry_core.guardian`).
    guard: guardian.Guard | None = None
    launch: dlaunch.Launch
    proc: subprocess.Popen[bytes]

    def __init__(self) -> None:
        # `dropped` is how a caller tells a whole stream from one with a hole in it.
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._eof = threading.Event()
        self.dropped = 0
        # Why it ended: else a transient error reads as a quiet machine while `alive` is true.
        self._drainer: threading.Thread | None = None
        self.drain_ended = ""
        # `quit`, `killed`, `died` (gone before `close`), `none`.
        self.ended_how = "none"
        self._closing = threading.Lock()
        self._closed = False
        # SIGKILL sent, child not reaped; read off the object by the `close` tool.
        self.reap_failed = ""

    def _linked(self, sock: socket.socket) -> stub_link.Link:
        """The stub's link over the input socket, as the session speaks it."""
        raise NotImplementedError

    def _spawn(self, launch: dlaunch.Launch) -> None:
        """Bring up the terminal, emulator, guardian, drain thread and input socket."""
        # Nothing can reach `close()` if this raises, so cleanup is local.
        listener = (dlaunch.listen_input(launch.input_port) if launch.input_port is not None
                    else None)                        # before any process exists
        if listener is not None:
            launch = self.launch = replace(launch, input_port=listener.getsockname()[1])
        try:
            self.control = control.ControlChannel(lambda: self.proc.poll())
            launch = self.launch = replace(launch, control_port=self.control.port)
            self._master, slave = _terminal()
        except BaseException:
            if listener is not None:
                listener.close()
            if getattr(self, "control", None) is not None:
                self.control.close()
            raise
        try:
            self.argv = dlaunch.build_argv(launch)
            self.proc = subprocess.Popen(
                self.argv, cwd=str(launch.cwd), stdin=slave, stdout=slave,
                stderr=slave, env=dlaunch.launch_environment(launch.background),
                start_new_session=True, close_fds=True)
            if (ledger := live_host.EmulatorLedger.from_environment()) is not None:
                ledger.record(self.proc.pid, self.argv[0])
            self.guard = guardian.spawn(self.proc, PROCESS_NAME,
                                        deadline=time.time() + launch.seconds + GUARDIAN_GRACE_S)
            # Not lazy: boot chatter fills the buffer before the first question.
            self._drainer = threading.Thread(target=self._drain, name="dosbox-drain",
                                             daemon=True)
            self._drainer.start()
            # Before the guest runs: it polling a serial port with no peer blocks the emulator.
            self._input: socket.socket | None = None
            self._link: stub_link.Link | None = None
            if listener is not None:
                self._input = dlaunch.accept_input(listener, dlaunch.INPUT_CONNECT_S,
                                                   self.proc.poll)
                self._link = self._linked(self._input)
        except BaseException:
            if listener is not None:
                listener.close()
            self.control.close()
            # Without this kill, a raise after `Popen` leaves an emulator nothing can `close()`.
            with contextlib.suppress(Exception):
                proc = getattr(self, "proc", None)
                if proc is not None and proc.poll() is None:
                    self._signal_group(guardian.KILL)
                    proc.wait(timeout=5)
            self._stop.set()
            drainer = getattr(self, "_drainer", None)
            if drainer is not None:
                drainer.join(timeout=2.0)
            with contextlib.suppress(OSError):
                os.close(self._master)
            raise
        finally:
            with contextlib.suppress(OSError):
                os.close(slave)

    # ------------------------------------------------------------------ reading

    def _drain(self) -> None:
        """Read the terminal while it lives, recording how it ended.

        Overflow drops the oldest bytes, counted; `_read` refuses the reading it lands in.
        """
        ended = "the descriptor reached end of file"
        while not self._stop.is_set():
            try:
                ready, _, _ = select.select([self._master], [], [], 0.05)
            except (OSError, ValueError) as exc:
                ended = f"select on the terminal failed: {exc!r}"
                break
            if not ready:
                continue
            try:
                chunk = os.read(self._master, 65536)
            except OSError as exc:
                ended = f"reading the terminal failed: {exc!r}"
                break
            if not chunk:
                break
            with self._lock:
                self._buf += chunk
                over = len(self._buf) - DRAIN_KEEP
                if over > 0:
                    del self._buf[:over]
                    self.dropped += over
        else:
            ended = "stopped deliberately by close()"
        self.drain_ended = ended
        self._eof.set()

    def _take(self) -> bytes:
        with self._lock:
            got = bytes(self._buf)
            self._buf.clear()
        return got

    # ------------------------------------------------------------------ closing

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self, grace: float = 8.0, progress: Progress = no_progress) -> int | None:
        """End the session; a cancel mid-wait reruns `_close` shielded, then keeps unwinding."""
        with self._closing:
            if self._closed:
                return self.proc.returncode
            try:
                code = self._close(grace, progress)
            except BaseException as e:
                if not cancel.is_cancellation(e):
                    raise
                with cancel.shielded():
                    self._close(grace)
                self._closed = True
                raise
            # An emulator SIGKILLed and not yet reaped can still be reaped by a later close.
            self._closed = not self.reap_failed
            return code

    def _close(self, grace: float = 8.0, progress: Progress = no_progress) -> int | None:
        """End the session; a second call finishes an interrupted one.

        `grace` is the wait after SIGKILL, floored at one second; SIGTERM gets `TERM_GRACE`.
        The whole process group is signalled to catch anything the emulator spawned.
        """
        # The channel the presence writer sends on is about to go.
        dpresence.of(self).close()
        try:
            if self.proc.poll() is not None:
                self.ended_how = "quit" if getattr(self, "_termed", False) else "died"
            else:
                self._signal_group(signal.SIGTERM)
                self._termed = True
                if wait_exit(self.proc, TERM_GRACE, progress,
                             "close: waiting for the emulator to leave on SIGTERM") is not None:
                    self.ended_how = "quit"
                else:
                    self.ended_how = "killed"
                    self._signal_group(guardian.KILL)
                    # Floored: `grace=0` would drop an unreaped child.
                    if wait_exit(self.proc, max(grace, 1.0), progress,
                                 "close: waiting for the SIGKILLed emulator to be reaped") is None:
                        self.reap_failed = (
                            f"SIGKILL was sent and the process had not been reaped "
                            f"{max(grace, 1.0)}s later")
        finally:
            sock = getattr(self, "_input", None)
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
                self._input = None
                self._link = None
            channel = getattr(self, "control", None)
            if channel is not None:
                channel.close()
            # Stop the thread before closing the descriptor; if the join expires, leak the
            # descriptor on purpose rather than let a stale drainer read a recycled one.
            self._stop.set()
            if self._drainer is not None:
                self._drainer.join(timeout=DRAIN_JOIN_SECS)
            if self._drainer is not None and self._drainer.is_alive():
                self.drain_ended = (f"the drain thread did not stop within "
                                    f"{DRAIN_JOIN_SECS} s; the terminal descriptor was "
                                    f"left open on purpose rather than recycled under "
                                    f"a live reader")
            elif not getattr(self, "_master_closed", False):
                self._master_closed = True
                with contextlib.suppress(OSError):
                    os.close(self._master)
            # Only once reaped: stopped earlier, a dying server would leave it unwatched.
            if self.proc.poll() is not None:
                guardian.stop(self.guard)
        # None, not -1: -1 is the genuine code for "killed by SIGHUP".
        return self.proc.returncode

    def _signal_group(self, sig: int) -> None:
        signal_group(self.proc.pid, sig)


def signal_group(pid: int, sig: int) -> None:
    """`sig` to the process group `pid` belongs to, if there still is one."""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        if sys.platform != "win32":
            os.killpg(os.getpgid(pid), sig)

