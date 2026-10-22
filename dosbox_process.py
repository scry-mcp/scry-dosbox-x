"""The DOSBox-X PROCESS a session drives: spawned under a pseudo-terminal, its terminal drained by
a thread, its input socket and control channel opened beside it, and ended so that nothing is left
behind. `dosbox_session.Session` is this and the debugger's console on top of it: what is typed,
read back and waited for is the console's; that the emulator exists, is read, and goes away is
this module's.
"""

from __future__ import annotations

import contextlib
import os
import pty
import select
import signal
import socket
import subprocess
import termios
import threading
import time
from dataclasses import replace
from typing import Any

from scry_core import cancel, guardian, live_host
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress

import dosbox_control as control
import dosbox_launch as dlaunch
import dosbox_presence as dpresence
import dosbox_stub_link as stub_link

#: What this server, and after it the guardian beside every emulator, are called in the host's
#: process list.
PROCESS_NAME = "scry-dosbox-x"
GUARDIAN_NAME = guardian.name_of(PROCESS_NAME)
#: How far past the bound, on the host's clock from the spawn, the guardian waits: a guest
#: released at once still ends on its own `-time-limit`, which quits cleanly and finishes the
#: recording. `-time-limit` counts emulated time, so a session that spent its time parked reaches
#: the guardian's kill first, as the bound on the host's clock says it should.
GUARDIAN_GRACE_S = 10.0

# THE TERMINAL IS DRAINED BY A THREAD, AND THAT IS NOT AN OPTIMISATION.
#
# A pty master's buffer is FINITE, and when it fills, the WRITER blocks -- in the
# kernel, not in anybody's code. The writer here is the emulator, so a session whose
# only reader is a tool call FREEZES THE MACHINE between questions.
#
# Seen in a QA round, and it is why this is a thread and not a longer timeout: sessions
# sat at one guest instant for as long as nobody asked, and a single `registers` call
# moved the guest forward. With video capture and without, launched with `-c` and from
# the conf's `[autoexec]`, the stall was the same, so neither is the cause; the same
# program in a batch run played on.
#
# It also explains why the contract tests could not see it: they always have a call
# in flight, which is precisely the condition under which the defect does not exist.
#
# THE NUMBER, which is a different question from the thread and needs its own reason.
# It is a CEILING ON MEMORY, not a working set: about a thousand of this debugger's
# repaints, far more than any reply needs and small enough that a session forgotten for
# an afternoon cannot grow without bound. It is deliberately LARGER than
# `dosbox_session.SCREEN_KEEP`, which is what `_screen` retains
# afterwards: the two bound different things, and reaching this one is an event a
# caller is told about (`_read` refuses the reading) while reaching that one is not.
DRAIN_KEEP = 4 * 1024 * 1024

# How long `close()` waits for the drain thread before it stops trusting it. It is a
# teardown budget, not a guess about the work: the thread's loop wakes every 0.05 s, so
# anything past a few tenths of a second means it is not coming back, and the caller is
# waiting on a session they have already asked to end.
DRAIN_JOIN_SECS = 2.0

# HOW LONG SIGTERM IS BELIEVED IN. Every session is launched with the emulator's quit
# warning OFF, and with it off a guest holding a program answers the TERM at once, running
# or stopped, in a window or headless: so this is a bound and not a wait the ordinary close
# spends. It stays small because what can still ignore the signal (a conf that puts the
# warning back, a build that does not answer under a pty) is not slow but deaf, and the
# SIGKILL behind it cannot be ignored. It is separate from the post-KILL reap budget so a
# close waits in proportion to what the wait can achieve; on a WATCHED session that wait
# sits on somebody's screen. The measured figures belong in the commit that took them.
TERM_GRACE = 2.0


# How often `wait_exit` asks whether the process is gone.
EXIT_POLL_S = 0.1


def wait_exit(proc: subprocess.Popen[Any], seconds: float, progress: Progress,
              what: str) -> int | None:
    """The process's exit code within `seconds`, or None: a `proc.wait(timeout)` that reports
    its progress, because `close` is a wait the owner watches and a quit that takes seconds
    looks exactly like a hung server without the line."""
    t0 = time.monotonic()
    next_tick = t0 + PROGRESS_EVERY_S
    while True:
        cancel.check()
        # SLICES OF THE REAL `wait`, not a `poll` loop: `wait` is what reaps the child, and
        # what the doubles of `close` speak.
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
    """The emulator's process, its terminal and its sockets: `_spawn` brings them up, `close`
    takes them down whatever state they are in."""

    #: The guardian beside the emulator (`scry_core.guardian`), set once it is spawned; why, in
    #: REFERENCE.md, The session.
    guard: subprocess.Popen[bytes] | None = None
    launch: dlaunch.Launch
    proc: subprocess.Popen[bytes]

    def __init__(self) -> None:
        # What the drain thread fills and `_read` empties. `dropped` is not
        # bookkeeping: the buffer is bounded, so a session left alone for long enough
        # discards its OLDEST bytes, and a caller has no other way to tell a stream it
        # saw whole from one with a hole in it.
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._eof = threading.Event()
        self.dropped = 0
        # WHY THE DRAINER ENDED, and never just THAT it ended. `_eof` is set by four
        # different endings -- a real EOF, `_stop` from `close()`, and an error out of
        # either `select` or `os.read` -- and a drainer killed by a transient error
        # makes every later read return "" forever while `alive` still says true. A
        # session that is a broken instrument reporting itself as a quiet machine is
        # the one failure this module exists to prevent.
        self._drainer: threading.Thread | None = None
        self.drain_ended = ""
        # HOW THE SESSION ENDED, set by `close` and read by the server beside `exit_code`,
        # one word each: `quit` (it left on the first signal), `killed` (SIGKILL,
        # which a session under a pty always needs), `died` (already gone when `close` was
        # called), `none` (not closed yet).
        self.ended_how = "none"
        # ONE CLOSE AT A TIME, AND ONE THAT FINISHED WHOLE IS NOT RUN AGAIN: the server's own
        # end and a signalled one that waited out the tool lock can both reach this session from
        # two threads, and a second `_close` would signal the group and close the master again.
        self._closing = threading.Lock()
        self._closed = False
        # Set only when SIGKILL was sent and the child had still not been reaped.
        #
        # IT IS NOT IN `state()`, because a copy there would be inert. It can
        # only be set DURING `close()`, and every caller discards the session straight
        # afterwards -- so a copy in `state()` is unreachable by construction. The
        # `close` tool reads it off the object after closing and reports it beside
        # `exit_code`, which is the reply that would otherwise be a bare null.
        self.reap_failed = ""

    def _linked(self, sock: socket.socket) -> stub_link.Link:
        """The stub's link over the input socket, as the session speaks it."""
        raise NotImplementedError

    def _spawn(self, launch: dlaunch.Launch) -> None:
        """Bring the emulator up for `launch`: its terminal (echo off), its process in a group of
        its own, the guardian beside it, the drain thread, and the input socket accepted before
        the guest runs."""
        # THE WHOLE SETUP IS UNDER `finally`, because three calls between opening the
        # terminal and handing it to the child can raise, and on any of them the
        # object is never bound to anything: nothing could ever reach `close()` to
        # reclaim the descriptors.
        listener = (dlaunch.listen_input(launch.input_port) if launch.input_port is not None
                    else None)                        # before any process exists
        if listener is not None:
            launch = self.launch = replace(launch, input_port=listener.getsockname()[1])
        try:
            self.control = control.ControlChannel(lambda: self.proc.poll())
            launch = self.launch = replace(launch, control_port=self.control.port)
            self._master, slave = pty.openpty()
        except BaseException:
            if listener is not None:
                listener.close()
            if getattr(self, "control", None) is not None:
                self.control.close()
            raise
        try:
            attrs = termios.tcgetattr(slave)
            attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ECHOE | termios.ECHOK)
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
            self.argv = dlaunch.build_argv(launch)
            self.proc = subprocess.Popen(
                self.argv, cwd=str(launch.cwd), stdin=slave, stdout=slave,
                stderr=slave, env=dlaunch.launch_environment(launch.background),
                start_new_session=True, close_fds=True)
            if (ledger := live_host.EmulatorLedger.from_environment()) is not None:
                ledger.record(self.proc.pid, self.argv[0])
            self.guard = guardian.spawn(self.proc, PROCESS_NAME,
                                        deadline=time.time() + launch.seconds + GUARDIAN_GRACE_S)
            # STARTED HERE AND NOT LAZILY ON THE FIRST READ: the window this closes
            # is the one between the child being born and the first question, which
            # is exactly when the boot chatter fills the buffer.
            self._drainer = threading.Thread(target=self._drain, name="dosbox-drain",
                                             daemon=True)
            self._drainer.start()
            # THE INPUT SOCKET IS ACCEPTED NOW, before the guest runs a single instruction
            # (`-break-start` holds it at reset): the nullmodem dials from the emulator's
            # init, and a guest polling a serial port with no peer BLOCKS the emulator
            # ("Nullmodem: block on polling", its own log line).
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
            # THE CHILD IS KILLED HERE, and this arm is why. Before the drain thread
            # existed, `Popen` was the LAST statement in this block, so nothing could
            # raise once a process existed. Now two statements follow it, and both can
            # raise for real: `Thread.start()` with `RuntimeError("can't start new
            # thread")`, or the `KeyboardInterrupt`/`SystemExit` that `except
            # BaseException` is written for. Closing the master and re-raising without
            # touching `self.proc` would leave an emulator running under a bound of up
            # to `dosbox_launch.MAX_SECONDS` with NO object anywhere able to reach `close()`
            # -- which is exactly the six-left-running disaster `dosbox_launch.validate`'s
            # docstring is about, arriving by a different door.
            with contextlib.suppress(Exception):
                proc = getattr(self, "proc", None)
                if proc is not None and proc.poll() is None:
                    self._signal_group(signal.SIGKILL)
                    proc.wait(timeout=5)
            self._stop.set()
            # THE DRAIN THREAD IS JOINED BEFORE THE DESCRIPTOR IS CLOSED, as `close()` does
            # and for its reason: besides an interrupt, a dial that never came arrives
            # here seconds later with the thread selecting on `_master`. Closing under it
            # leaves it reading a number the kernel is free to hand to the next session's
            # pty.
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
        """Read the terminal for as long as it lives. See `DRAIN_KEEP` for why.

        It runs whether or not anybody is asking anything, because the thing it is
        preventing is the emulator BLOCKING on a full buffer, and that happens
        precisely when nobody is asking.

        It drops the OLDEST bytes on overflow rather than the newest: what a caller
        wants from a terminal is the current screen, and the repaint that carries it
        is the most recent thing in there. The drop is COUNTED, and `_read` REFUSES
        the reading it lands in rather than handing back a stream with a hole.

        HOW IT ENDED IS RECORDED, because `_eof` alone cannot say. Four endings reach
        it and only one of them is normal; a drainer killed by a transient error makes
        every later read return "" forever while `state()` still reports `alive`.
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
        """End the session and leave nothing behind (`_close`), EVEN WHEN THE CALL IS CANCELLED
        HALF-WAY: the cancel lands in the wait for the exit, and an emulator signalled but never
        waited on is the one thing a cancel must not leave, so the close runs again, shielded and
        silent, and the cancellation goes on unwinding once it has."""
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
            # FINAL ONLY WHEN NOTHING WAS LEFT BEHIND: an emulator SIGKILLed and not yet reaped
            # is one a later close can still reap.
            self._closed = not self.reap_failed
            return code

    def _close(self, grace: float = 8.0, progress: Progress = no_progress) -> int | None:
        """End the session and leave nothing behind; a second call finishes what an interrupted
        one began, and never closes the terminal twice.

        A live session outlives the turn, which is the one hazard a batch launcher
        does not have. The bound is the backstop and this is the deliberate act; both
        exist because either alone leaves a case uncovered -- and the backstop, kept by
        the guardian, is the one that survives this process being killed, since a
        `finally` does not run on SIGKILL.

        `grace` IS THE WAIT AFTER SIGKILL, FLOORED AT ONE SECOND, and SIGTERM gets
        `TERM_GRACE` of its own: with the quit warning off on every argv the ordinary session
        answers the TERM at once, so that budget is a bound on a signal that is expected to
        land, and what still ignores it is deaf rather than slow (see that constant). One
        budget for both would spend the post-KILL reap budget on every close of a used
        session. The floor exists because `grace=0` is a
        reasonable reading of "do not wait" and SIGKILL still needs reaping.

        THE DESCRIPTOR IS CLOSED UNDER `finally`. Without it, a second `wait` that
        times out takes the exception out of here with the master still open and the
        caller's session state still pointing at a half-closed object.

        The process GROUP is signalled, not just the child: `start_new_session` put
        it in its own, so anything it spawned would otherwise be missed.
        """
        # The presence's writer stops first: the channel it sends on is about to go.
        dpresence.of(self).close()
        try:
            if self.proc.poll() is not None:
                # A process that left on this close's own SIGTERM quit; one found gone, died.
                self.ended_how = "quit" if getattr(self, "_termed", False) else "died"
            else:
                self._signal_group(signal.SIGTERM)
                self._termed = True
                if wait_exit(self.proc, TERM_GRACE, progress,
                             "close: waiting for the emulator to leave on SIGTERM") is not None:
                    self.ended_how = "quit"
                else:
                    self.ended_how = "killed"
                    self._signal_group(signal.SIGKILL)
                    # THE SIGKILL WAIT IS FLOORED, and a caller cannot ask for none.
                    # `close(grace=0)` is a reasonable reading of "do not wait" and it
                    # produced the state this class forbids: the child SIGKILLed, the
                    # TimeoutExpired suppressed, `None` returned as the exit code, and
                    # the server then dropping its reference -- an un-reaped process
                    # nothing can reach. SIGKILL cannot be ignored, so the only
                    # question is how long reaping takes, and a second is far past it.
                    # AND AN EXPIRY HERE IS RECORDED, not merely survived. Suppressing
                    # it and returning `self.proc.returncode` hands back None for a
                    # child that was SIGKILLed and not yet reaped, and the server then
                    # drops its reference: an un-reaped process nothing can reach, with
                    # `exit_code: null` as the only trace. The drain-thread join eleven
                    # lines below already does the right thing with its own expiry;
                    # this is the same treatment for this one.
                    if wait_exit(self.proc, max(grace, 1.0), progress,
                                 "close: waiting for the SIGKILLed emulator to be reaped") is None:
                        # THE MESSAGE STATES THE FACT AND NOTHING ABOUT A REPLY.
                        # Both earlier wordings named an `exit_code` "below" or "in
                        # this reply", and both dangled: the field is consumed by two
                        # different tools and only one of them has an exit code.
                        self.reap_failed = (
                            f"SIGKILL was sent and the process had not been reaped "
                            f"{max(grace, 1.0)}s later")
        finally:
            # THE INPUT SOCKET GOES FIRST, and quietly: the emulator's end is dying or dead
            # by now, and a socket left open is a descriptor leaked per session.
            sock = getattr(self, "_input", None)
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
                self._input = None
                self._link = None
            channel = getattr(self, "control", None)
            if channel is not None:
                channel.close()
            # THE THREAD IS STOPPED BEFORE THE DESCRIPTOR IS CLOSED, and the order is
            # the whole point: closing first leaves it selecting on a number the
            # kernel is free to hand to the next file this process opens.
            #
            # AND THE JOIN IS CHECKED, because a `join(timeout=...)` that EXPIRES
            # produces exactly the state this ordering exists to prevent, silently:
            # `join` returns None either way. If the thread outlives the wait, the
            # descriptor is DELIBERATELY LEAKED rather than closed. One leaked fd in a
            # process that is ending a session is cheap; a recycled fd being read by a
            # stale drainer -- into the next session's buffer -- is not, and in a
            # long-lived MCP server the next fd is the next session's own terminal.
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
            # The guardian stops only once the emulator is reaped: stopped earlier, a server
            # dying in between would leave it unwatched.
            if self.proc.poll() is not None:
                guardian.stop(self.guard)
        # None, not -1: `subprocess` encodes a signal death as a NEGATIVE number, so
        # -1 is the genuine code for "killed by SIGHUP" and cannot double as "unknown".
        return self.proc.returncode

    def _signal_group(self, sig: int) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(os.getpgid(self.proc.pid), sig)

