"""The host half of the stub's serial protocol 3; the framing contract is `guest/inject.asm`."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable

from scry_core import cancel
from scry_core.reply_contract import Invalid

SYNC, ACK = 0xA5, 0x5A
OP_REPORT = ord("R")
#: The stub answers the moment a frame is whole; a guest silent this long is refused.
ACK_WAIT_S = 1.0
SENDS = 3
#: Between two frames: the stub carries a frame the moment it is whole, and a program reading its
#: keys once a frame (50 Hz is common) never sees a make whose break came within that frame. One
#: BIOS tick, so the guest's clock, which follows the host's while it runs, spaces them so too.
FRAME_SPACING_S = 0.055
#: Read slice, so a cancel is noticed between reads.
READ_SLICE_S = 0.1


def frame(seq: int, command: bytes) -> bytes:
    """SYNC, sequence, command, and a check that XORs every byte after SYNC into FFh."""
    body = bytes((seq,)) + command
    check = 0xFF
    for byte in body:
        check ^= byte
    return bytes((SYNC,)) + body + bytes((check,))


class Link:
    """One session's serial link to the stub. `parked` says whether the machine is at the
    debugger, where the guest runs nothing and so no acknowledgement can come."""

    def __init__(self, sock: socket.socket, parked: Callable[[], bool] = lambda: False) -> None:
        self.sock = sock
        self.parked = parked
        self.seq = 0
        self._pending = bytearray()
        self._acked_at = -FRAME_SPACING_S
        # False after a state load: the stub's sequence is unknown, so a report proves it first.
        self.proved = True

    def unprove(self) -> None:
        """The stub's memory was replaced (a state loaded)."""
        self.proved = False

    def send(self, commands: list[bytes]) -> list[str]:
        """Send in order; return the `R` report lines. A refusal says how many were acked."""
        reports: list[str] = []
        acknowledged = 0
        if not self.proved:
            self._deliver(bytes((OP_REPORT,)))
            self._line()
            self.proved = True
        for command in commands:
            try:
                self._deliver(command)
                acknowledged += 1
                if command[0] == OP_REPORT:
                    reports.append(self._line())
            except Invalid as e:
                raise Invalid(e.code, f"{e} ({acknowledged} of {len(commands)} commands "
                              f"acknowledged)") from None
        return reports

    def _deliver(self, command: bytes) -> None:
        """Return once the command has run (by this send or an earlier one); else refuse."""
        seq = self._next()
        while (left := self._acked_at + FRAME_SPACING_S - time.monotonic()) > 0:
            cancel.check()
            time.sleep(min(left, READ_SLICE_S))
        for sent in range(SENDS):
            self._write(frame(seq, command))
            carried = self._acknowledged(seq, command[0])
            if carried is None:
                continue
            if carried or sent:
                self._acked_at = time.monotonic()
                return
            # First send answered as a repeat (state loaded from another session): resend.
            seq = self._next()
        raise Invalid("host_failed",
            f"no acknowledgement of a {chr(command[0])!r} command after {SENDS} sends, "
            f"{ACK_WAIT_S}s each: a guest that masked IRQ 4 and its timer, a stub "
            f"that dropped every frame, or one that is gone, which this cannot tell apart")

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
        while True:
            at = self._pending.find(ACK)
            if at >= 0 and len(self._pending) >= at + 4:
                got = bytes(self._pending[at:at + 4])
                if got[1] == seq and got[2] == op:
                    del self._pending[:at + 4]
                    return bool(got[3])
                del self._pending[:at + 1]               # a late twin of an earlier ack
                continue
            if not self._read(deadline):
                return None

    def _line(self) -> str:
        """The report line that follows an acknowledgement."""
        deadline = time.monotonic() + ACK_WAIT_S
        while (end := self._pending.find(b"\r\n")) < 0:
            if not self._read(deadline):
                raise Invalid("host_failed",
                    f"the stub acknowledged a report and sent no line within {ACK_WAIT_S}s")
        line = bytes(self._pending[:end]).decode("ascii", "replace")
        del self._pending[:end + 2]
        return line

    def _read(self, deadline: float) -> bool:
        """Append what the stub sent; False once `deadline` passed with nothing new."""
        while (left := deadline - time.monotonic()) > 0:
            cancel.check()
            self.sock.settimeout(min(left, READ_SLICE_S))
            try:
                got = self.sock.recv(4096)
            except TimeoutError:
                # Park is named only once the line is empty: an ack sent just before the park
                # is read first, or its command would be resent.
                if self.parked():
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
