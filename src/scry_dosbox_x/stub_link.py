"""The host half of the stub's serial protocol; the framing contract is `guest/scry.asm`."""

from __future__ import annotations

import contextlib
import socket
import time
from collections.abc import Callable
from typing import Protocol

from scry_core import cancel
from scry_core.reply_contract import Invalid

SYNC, ACK = 0xA5, 0x5A
OP_REPORT, OP_KEY = ord("R"), ord("K")
EXTENDED = 0xE0
#: The release of the fake shift that follows an extended prefix, harmless to a program.
FAKE_SHIFT_BREAK = 0xAA
#: The stub answers the moment a frame is whole; a guest silent this long is refused.
ACK_WAIT_S = 1.0
SENDS = 3
#: Between two frames: the stub carries a frame the moment it is whole, and a program reading its
#: keys once a frame (50 Hz is common) never sees a make whose break came within that frame. One
#: BIOS tick of the guest's own time: the wall clock when a build offers no other.
FRAME_SPACING_S = 0.055
#: Read slice, so a cancel is noticed between reads.
READ_SLICE_S = 0.1
#: A parked machine, run by retraces: the most a frame's acknowledgement may take, the same tick
#: in the guest's clock, and the read after each retrace.
ACK_RETRACES = 8
FRAME_SPACING_MS = FRAME_SPACING_S * 1000
AFTER_RETRACE_S = 0.02
#: A running guest: how often its clock is asked while a frame's spacing is waited out, and the
#: wall time that wait is capped at.
CLOCK_POLL_S = 0.005
SPACING_CEILING_S = 30.0


class Advance(Protocol):
    """One retrace of the parked machine, returning `clock_ms`, its emulated milliseconds."""

    clock_ms: float

    def __call__(self) -> float: ...


def frame(seq: int, command: bytes) -> bytes:
    """SYNC, sequence, command, and a check that XORs every byte after SYNC into FFh."""
    body = bytes((seq,)) + command
    check = 0xFF
    for byte in body:
        check ^= byte
    return bytes((SYNC,)) + body + bytes((check,))


def keys_down(written: list[bytes]) -> tuple[list[tuple[bool, int]], bool]:
    """The keys `written` left down, in press order, and whether it ended on a bare prefix."""
    down: list[tuple[bool, int]] = []
    extended = False
    for command in written:
        if command[0] != OP_KEY:
            continue
        code = command[1]
        if code == EXTENDED:
            extended = True
            continue
        key, extended = (extended, code & 0x7F), False
        if code & 0x80:
            if key in down:
                down.remove(key)
        elif key not in down:
            down.append(key)
    return down, extended


def owed_breaks(written: list[bytes]) -> list[bytes]:
    """The key commands that release every key `written` pressed and did not release, last
    pressed first; an extended key's break repeats its prefix."""
    down, extended = keys_down(written)
    owed: list[bytes] = []
    for prefixed, code in reversed(down):
        if prefixed:
            owed.append(bytes((OP_KEY, EXTENDED)))
        owed.append(bytes((OP_KEY, code | 0x80)))
    if extended:
        owed.append(bytes((OP_KEY, FAKE_SHIFT_BREAK)))
    return owed


class Cut(Invalid):
    """A send refused part-way: `written` of its `total` input commands went out, and `held`
    keys stay down for a later send to release."""

    def __init__(self, cause: Invalid, written: list[bytes], acknowledged: int,
                 commands: list[bytes], held: int) -> None:
        super().__init__(cause.code,
                         f"{cause} ({acknowledged} of {len(commands)} commands acknowledged)")
        self.cause, self.held = cause, held
        self.written, self.total = _inputs(written), _inputs(commands)


def _inputs(commands: list[bytes]) -> int:
    """The commands that act on the guest, reports aside."""
    return sum(1 for c in commands if c[0] != OP_REPORT)


class Link:
    """One session's serial link to the stub. `parked` says whether the machine is at the
    debugger, where the guest runs nothing and so no acknowledgement comes unless a send's
    `advance` runs it."""

    def __init__(self, sock: socket.socket, parked: Callable[[], bool] = lambda: False,
                 clock: Callable[[], float | None] = lambda: None) -> None:
        self.sock = sock
        self.parked = parked
        self.clock = clock
        self.seq = 0
        self._pending = bytearray()
        self._acked_at = -FRAME_SPACING_S
        # False after a state load: the stub's sequence is unknown, so a report proves it first.
        self.proved = True
        self._advance: Advance | None = None
        self._clock_ms = 0.0
        self._acked_ms: float | None = None
        self._acked_running_ms: float | None = None
        self._written: list[bytes] = []
        #: Releases a cut send owes, paid ahead of the next send, and the keys they release.
        self.owed: list[bytes] = []
        self.held = 0
        #: Since the link opened, so a caller can tell what one call put in.
        self.inputs_written = 0
        self.releases_sent = 0

    def unprove(self) -> None:
        """The stub's memory was replaced (a state loaded)."""
        self.proved = False
        # The held key was the replaced machine's.
        self.owed, self.held = [], 0

    def send(self, commands: list[bytes], advance: Advance | None = None) -> list[str]:
        """Send in order; return the `R` report lines. A refusal says how many were acked.
        `advance` runs a parked machine until each is acknowledged."""
        self._advance = advance
        if advance is not None:
            # The guest's clock alone, so a replay takes these retraces; one behind the last
            # frame's was put back by a load, with nothing to wait out.
            self._clock_ms = advance.clock_ms
            if self._acked_ms is not None and self._clock_ms < self._acked_ms:
                self._acked_ms = None
        try:
            return self._send(commands)
        finally:
            self._advance = None

    def _send(self, commands: list[bytes]) -> list[str]:
        reports: list[str] = []
        acknowledged = 0
        self._written = []
        base: int | None = None
        try:
            if not self.proved:
                self._deliver(bytes((OP_REPORT,)))
                self._line()
                self.proved = True
            self._pay_owed()
            base = len(self._written)
            for command in commands:
                self._deliver(command)
                acknowledged += 1
                if command[0] == OP_REPORT:
                    reports.append(self._line())
        except Invalid as e:
            written = self._written[base:] if base is not None else []
            # A call that holds keys on purpose (`action="down"`) owes no release.
            if not owed_breaks(commands):
                self._owe(written)
            raise Cut(e, written, acknowledged, commands, self.held) from None
        except BaseException as e:
            if cancel.is_cancellation(e):
                self._owe(self._written[base:] if base is not None else [])
                self._release_keys()
            raise
        finally:
            if base is not None:
                self.inputs_written += _inputs(self._written[base:])
        return reports

    def _owe(self, written: list[bytes]) -> None:
        self.owed += owed_breaks(written)
        self.held += len(keys_down(written)[0])

    def _pay_owed(self) -> None:
        """The releases owed, each dropped once taken: a key left down repeats in the guest."""
        while self.owed:
            self._deliver(self.owed[0])
            del self.owed[0]
            self.releases_sent += 1
        self.held = 0

    def _release_keys(self) -> None:
        """A cancelled send's releases, best effort: what the stub does not take stays owed."""
        with cancel.shielded(), contextlib.suppress(Invalid):
            self._pay_owed()

    def _deliver(self, command: bytes) -> None:
        """Return once the command has run (by this send or an earlier one); else refuse."""
        seq = self._next()
        self._space()
        for sent in range(SENDS):
            self._write(frame(seq, command))
            if not sent:
                self._written.append(command)
            carried = self._acknowledged(seq, command[0])
            if carried is None:
                continue
            if carried or sent:
                self._acked_at = time.monotonic()
                self._acked_ms = self._clock_ms if self._advance is not None else None
                self._acked_running_ms = self.clock() if self._advance is None else None
                return
            # First send answered as a repeat (state loaded from another session): resend.
            seq = self._next()
        each = (f"{ACK_RETRACES} retraces" if self._advance is not None else f"{ACK_WAIT_S}s")
        raise Invalid("host_failed",
            f"no acknowledgement of a {chr(command[0])!r} command after {SENDS} sends, "
            f"{each} each: a guest that masked IRQ 4 and its timer, a stub "
            f"that dropped every frame, or one that is gone, which this cannot tell apart")

    def _space(self) -> None:
        """A frame's distance from the last one."""
        if self._advance is not None:
            while self._acked_ms is not None and self._clock_ms - self._acked_ms < FRAME_SPACING_MS:
                self._clock_ms = self._advance()
            return
        if self._acked_running_ms is not None:
            self._space_by_guest_clock(self._acked_running_ms)
            return
        while (left := self._acked_at + FRAME_SPACING_S - time.monotonic()) > 0:
            cancel.check()
            time.sleep(min(left, READ_SLICE_S))

    def _space_by_guest_clock(self, acked_ms: float) -> None:
        """A running guest's frame is its own milliseconds, which lag the wall's when starved."""
        ceiling = time.monotonic() + SPACING_CEILING_S
        while time.monotonic() < ceiling:
            cancel.check()
            now_ms = self.clock()
            # a parked guest's clock is frozen, and a loaded state puts it behind the last ack
            if (now_ms is None or self.parked() or now_ms < acked_ms
                    or now_ms - acked_ms >= FRAME_SPACING_MS):
                return
            time.sleep(CLOCK_POLL_S)

    def _next(self) -> int:
        """1 to 255: the stub starts at 0, which no frame carries."""
        self.seq = self.seq % 255 + 1
        return self.seq

    def _write(self, data: bytes) -> None:
        try:
            self.sock.settimeout(None)
            self.sock.sendall(data)
        except OSError as e:
            raise Invalid("session_broken", f"the input socket is gone ({e}): the rest of the "
                          f"commands were not sent") from None

    def _acknowledged(self, seq: int, op: int) -> bool | None:
        """Whether the frame was carried out, None if no acknowledgement came in time."""
        deadline = time.monotonic() + ACK_WAIT_S
        retraces = 0
        while True:
            at = self._pending.find(ACK)
            if at >= 0 and len(self._pending) >= at + 4:
                got = bytes(self._pending[at:at + 4])
                if got[1] == seq and got[2] == op:
                    del self._pending[:at + 4]
                    return bool(got[3])
                del self._pending[:at + 1]               # a late twin of an earlier ack
                continue
            if self._advance is not None:
                if retraces == ACK_RETRACES:
                    return None
                self._clock_ms = self._advance()
                retraces += 1
                self._read(time.monotonic() + AFTER_RETRACE_S, parked_ok=True)
                continue
            if not self._read(deadline):
                return None

    def _line(self) -> str:
        """The report line after an acknowledgement; a parked stop can fall mid-line."""
        deadline = time.monotonic() + ACK_WAIT_S
        retraces = 0
        while (end := self._pending.find(b"\r\n")) < 0:
            if self._advance is not None:
                if self._read(time.monotonic() + AFTER_RETRACE_S, parked_ok=True):
                    continue
                if retraces < ACK_RETRACES:
                    self._clock_ms = self._advance()
                    retraces += 1
                    continue
            elif self._read(deadline):
                continue
            raise Invalid("host_failed", "the stub acknowledged a report and sent no line "
                          "within " + (f"{ACK_RETRACES} retraces" if self._advance is not None
                                       else f"{ACK_WAIT_S}s"))
        line = bytes(self._pending[:end]).decode("ascii", "replace")
        del self._pending[:end + 2]
        return line

    def _read(self, deadline: float, parked_ok: bool = False) -> bool:
        """Append what the stub sent; False once `deadline` passed with nothing new.
        `parked_ok`: the caller advances the parked machine itself."""
        while (left := deadline - time.monotonic()) > 0:
            cancel.check()
            self.sock.settimeout(min(left, READ_SLICE_S))
            try:
                got = self.sock.recv(4096)
            except TimeoutError:
                # Park is named only once the line is empty: an ack sent just before the park
                # is read first, or its command would be resent.
                if not parked_ok and self.parked():
                    raise Invalid("wait_stopped", "the machine stopped at the debugger while "
                                  "the stub's answer was awaited: the stub runs inside the "
                                  "machine, and a stopped machine runs nothing") from None
                continue
            except OSError as e:
                raise Invalid("session_broken", f"the input socket is gone ({e})") from None
            if not got:
                raise Invalid("session_broken", "the emulator closed the input socket")
            self._pending += got
            return True
        return False
