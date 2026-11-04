from __future__ import annotations

import contextlib
import errno
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Any

from scry_core import cancel, guardian, live_host
from scry_core import reply_contract as contract
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress
from scry_core.reply_contract import Invalid

from scry_dosbox_x import control, stub_link
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import presence as dpresence


def _streams(debugger_headless: bool) -> tuple[int, int] | None:
    """The read and write ends the emulator's output goes to; None for a console of its own.

    A debugger with a screen never stops unless all three streams are a terminal (POSIX) or it
    has a console (Windows): it gets a terminal nobody reads, or the hidden console's streams.
    A headless debugger's output is a pipe."""
    if debugger_headless:
        return os.pipe()
    if sys.platform == "win32":
        return None
    else:
        import pty

        return pty.openpty()


def _console() -> dict[str, Any]:
    """Windows: the emulator in a console of its own, hidden. Without one it dies at start."""
    if sys.platform == "win32":
        shown = subprocess.STARTUPINFO()
        shown.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        shown.wShowWindow = 0                                  # SW_HIDE
        return {"creationflags": subprocess.CREATE_NEW_CONSOLE, "startupinfo": shown}
    else:
        return {"start_new_session": True}


NO_OUTPUT_WHY = ("the emulator wrote to a console of its own, which this server does not read "
                 "(Windows, a build whose debugger draws a screen)")
#: Names in the host's process list.
PROCESS_NAME = "scry-dosbox-x"
GUARDIAN_NAME = guardian.name_of(PROCESS_NAME)
#: Guardian deadline past the bound, on the host's clock (`-time-limit` counts emulated time).
GUARDIAN_GRACE_S = 10.0

# A full pipe or terminal blocks the emulator in the kernel, so a thread drains it; past
# DRAIN_KEEP the oldest bytes go, counted in `dropped`.
DRAIN_KEEP = 4 * 1024 * 1024

DRAIN_JOIN_SECS = 2.0
#: Windows has no SIGTERM to ask with: `signal_group` terminates, so a quit is asked on the channel.
TERMINATES = sys.platform == "win32"

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
    """The emulator's process, its output and its sockets."""

    guard: guardian.Guard | None = None
    launch: dlaunch.Launch
    proc: subprocess.Popen[bytes]

    def __init__(self) -> None:
        # `dropped` is how a caller tells a whole stream from one with a hole in it.
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.dropped = 0
        self._out: int | None = None
        # False when the emulator writes to a console of its own, which nothing here reads
        self.captures_output = False
        # Why the reader stopped short; empty at a clean end of output.
        self._drainer: threading.Thread | None = None
        self.drain_failure = ""
        # `quit`, `killed`, `died` (gone before `close`), `none`.
        self.ended_how = "none"
        self._closing = threading.Lock()
        self._closed = False
        # SIGKILL sent, child not reaped; read off the object by the `close` tool.
        self.reap_failed = ""

    def _linked(self, sock: socket.socket) -> stub_link.Link:
        raise NotImplementedError

    def _spawn(self, launch: dlaunch.Launch) -> None:
        """Bring up the emulator, its guardian, the output drain and the input socket."""
        # Nothing can reach `close()` if this raises, so cleanup is local.
        listener = (dlaunch.listen_input(launch.input_port) if launch.input_port is not None
                    else None)                        # before any process exists
        if listener is not None:
            launch = self.launch = replace(launch, input_port=listener.getsockname()[1])
        ends: tuple[int, int] | None = None
        try:
            self.control = control.ControlChannel(lambda: self.proc.poll())
            launch = self.launch = replace(launch, control_port=self.control.port)
            ends = _streams(launch.debugger_headless)
        except BaseException:
            if listener is not None:
                listener.close()
            if getattr(self, "control", None) is not None:
                self.control.close()
            raise
        streams: dict[str, Any] = {}
        terminal = False
        if ends is not None:
            self._out = ends[0]
            self.captures_output = True
            terminal = os.isatty(ends[1])
            streams = {"stdin": ends[1] if terminal else subprocess.DEVNULL,
                       "stdout": ends[1], "stderr": ends[1]}
        try:
            self.argv = dlaunch.build_argv(launch)
            try:
                self.proc = subprocess.Popen(
                    self.argv, cwd=str(launch.cwd),
                    env=dlaunch.launch_environment(launch.background, terminal=terminal),
                    close_fds=True,
                    **streams, **_console())
            finally:
                # The child holds its own copy: closed here, the drain reads end of file the
                # moment nobody writes any more.
                if ends is not None:
                    with contextlib.suppress(OSError):
                        os.close(ends[1])
            if (ledger := live_host.EmulatorLedger.from_environment()) is not None:
                ledger.record(self.proc.pid, self.argv[0])
            self.guard = guardian.spawn(self.proc, PROCESS_NAME,
                                        deadline=time.time() + launch.seconds + GUARDIAN_GRACE_S)
            if self._out is not None:
                # Not lazy: boot chatter fills the pipe before the first question.
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
            if self._drainer is not None:
                self._drainer.join(timeout=DRAIN_JOIN_SECS)
            if self._out is not None:
                with contextlib.suppress(OSError):
                    os.close(self._out)
            raise

    # ------------------------------------------------------------------ reading

    def _drain(self) -> None:
        """Read the emulator's output while it lives, recording why it stopped short, if it did.

        It ends at end of file, which is the emulator gone (on a pty Linux reports that as
        `EIO`); overflow drops the oldest bytes, counted.
        """
        assert self._out is not None
        while True:
            try:
                chunk = os.read(self._out, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO and os.isatty(self._out):
                    break
                self.drain_failure = f"a read failed ({exc!r}), so the tails may be short"
                break
            if not chunk:
                break
            with self._lock:
                self._buf += chunk
                over = len(self._buf) - DRAIN_KEEP
                if over > 0:
                    del self._buf[:over]
                    self.dropped += over

    def output_tail(self, chars: int) -> str:
        """The last `chars` of what the emulator printed; empty when its console kept it."""
        with self._lock:
            got = bytes(self._buf[-4 * chars:])
        return got.decode("utf-8", errors="replace")[-chars:]

    def stdout_tail(self, chars: int) -> str | dict[str, Any]:
        """`output_tail`, or unavailable with why when no stream carried the output."""
        if not (self.captures_output or self._out is not None):
            return contract.unavailable(NO_OUTPUT_WHY)
        return self.output_tail(chars)

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
                asked = getattr(self, "_asked_to_leave", None)
                self.ended_how = "died" if asked is None else "quit" if asked else "killed"
            else:
                self._asked_to_leave = self._ask_to_leave()
                if self._asked_to_leave and wait_exit(
                        self.proc, TERM_GRACE, progress,
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
            # The drain ends at the emulator's end of file; if the join expires, the descriptor
            # is leaked on purpose rather than recycled under a live reader.
            if self._drainer is not None:
                self._drainer.join(timeout=DRAIN_JOIN_SECS)
            if self._drainer is not None and self._drainer.is_alive():
                self.drain_failure = (f"it was still reading {DRAIN_JOIN_SECS} s after the "
                                    f"emulator ended, so the tails may be short")
            elif self._out is not None:
                with contextlib.suppress(OSError):
                    os.close(self._out)
                self._out = None
            # Only once reaped: stopped earlier, a dying server would leave it unwatched.
            if self.proc.poll() is not None:
                guardian.stop(self.guard)
        # None, not -1: -1 is the genuine code for "killed by SIGHUP".
        return self.proc.returncode

    def _signal_group(self, sig: int) -> None:
        signal_group(self.proc.pid, sig)

    def _ask_to_leave(self) -> bool:
        """SIGTERM, or on Windows the debugger's `QUIT`; False when nothing was asked."""
        if not TERMINATES:
            self._signal_group(signal.SIGTERM)
            return True
        channel = getattr(self, "control", None)
        if channel is None:
            return False
        try:
            channel.request("EXEC QUIT", TERM_GRACE)
        except Invalid as e:
            return e.code == "session_broken"
        return True


def signal_group(pid: int, sig: int) -> None:
    """`sig` to the process group `pid` belongs to, if there still is one; on Windows, where
    there are no signals to send, the process is terminated (its job object takes the rest)."""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        if sys.platform == "win32":
            os.kill(pid, signal.SIGTERM)
        else:
            os.killpg(os.getpgid(pid), sig)
