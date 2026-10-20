"""THE STUB'S SERIAL LINK, the host half of protocol 3: each command goes down COM1 as a frame,
comes back acknowledged on the same link, and a report comes back after its acknowledgement. The
framing, the check, the ageing of a short frame and the repeat are the stub's header's
(`guest/inject.asm`), which is the contract; this module sends one frame at a time, waits for its
acknowledgement, and sends it again when none comes. Its own module because the framing and the
recovery change together and for reasons of their own; `Session` holds one and knows nothing of
frames.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable

from scry_core import cancel
from scry_core.reply_contract import Invalid

SYNC, ACK = 0xA5, 0x5A
OP_REPORT = ord("R")
#: How long one acknowledgement may take: the stub answers on the tick after the frame lands; this
#: bounds a stub that never answers, and a guest whose ticks come further apart than it is
#: refused as one.
ACK_WAIT_S = 1.0
#: How many times one frame is sent before the line is declared not answering.
SENDS = 3
#: The slice a wait reads in, so a cancelled call is noticed between reads.
READ_SLICE_S = 0.1


def frame(seq: int, command: bytes) -> bytes:
    """SYNC, the sequence byte, the command, and its check: every byte after SYNC XORed into
    FFh, so a frame completed with another's bytes does not add up and runs nothing."""
    body = bytes((seq,)) + command
    check = 0xFF
    for byte in body:
        check ^= byte
    return bytes((SYNC,)) + body + bytes((check,))


class Link:
    """One session's serial link to the stub: the socket the emulator's COM1 dialled, the
    sequence it is at, and what the stub sent that was not read yet. `parked` says whether the
    machine is at the debugger, where no tick runs and so no acknowledgement can come."""

    def __init__(self, sock: socket.socket, parked: Callable[[], bool] = lambda: False) -> None:
        self.sock = sock
        self.parked = parked
        self.seq = 0
        self._pending = bytearray()

    def send(self, commands: list[bytes]) -> list[str]:
        """Each command framed, sent and acknowledged in order; the report lines the `R`
        commands brought back, in order. A command none of whose sends was acknowledged is
        refused naming how many were acknowledged before it; it may have been carried out
        itself (its acknowledgements lost, or the machine stopped with it written)."""
        reports: list[str] = []
        for done, command in enumerate(commands):
            try:
                self._deliver(command)
                if command[0] == OP_REPORT:
                    reports.append(self._line())
            except Invalid as e:
                raise Invalid(e.code, f"{e} (after {done} of {len(commands)} commands "
                              f"acknowledged)") from None
        return reports

    def _deliver(self, command: bytes) -> None:
        """One command carried out, by this send or, its acknowledgement lost, by an earlier
        one; or the refusal."""
        seq = self._next()
        for sent in range(SENDS):
            self._write(frame(seq, command))
            carried = self._acknowledged(seq, command[0])
            if carried is None:
                continue                                # lost: the same frame again
            if carried or sent:
                return
            # A FIRST SEND ANSWERED AS A REPEAT: the stub's last sequence is this one (a state
            # loaded from another session), so it is sent again under the next.
            seq = self._next()
        raise Invalid("host_failed",
            f"the stub acknowledged none of {SENDS} sends of a {chr(command[0])!r} command "
            f"within {ACK_WAIT_S}s each: it is not reading the port (a guest that masked the "
            f"timer, or a stub that is gone)")

    def _next(self) -> int:
        """The next sequence byte, 1 to 255: the stub starts at 0, which no frame carries."""
        self.seq = self.seq % 255 + 1
        return self.seq

    def _write(self, data: bytes) -> None:
        try:
            self.sock.settimeout(None)      # a read's slice is not the send's bound
            self.sock.sendall(data)
        except OSError as e:
            raise Invalid("session_broken", f"the input socket is gone ({e}): the emulator "
                          f"closed its end, so nothing more was delivered") from None

    def _acknowledged(self, seq: int, op: int) -> bool | None:
        """This frame's acknowledgement: whether it was carried out, None when none came within
        `ACK_WAIT_S`. Whatever is not this frame's (a late twin of an earlier acknowledgement) is
        passed over."""
        deadline = time.monotonic() + ACK_WAIT_S
        while True:
            at = self._pending.find(ACK)
            if at >= 0 and len(self._pending) >= at + 4:
                got = bytes(self._pending[at:at + 4])
                if got[1] == seq and got[2] == op:
                    del self._pending[:at + 4]
                    return bool(got[3])
                del self._pending[:at + 1]               # not this frame's: look past it
                continue
            if not self._read(deadline):
                return None

    def _line(self) -> str:
        """The report that follows its acknowledgement, to its CR LF."""
        deadline = time.monotonic() + ACK_WAIT_S
        while (end := self._pending.find(b"\r\n")) < 0:
            if not self._read(deadline):
                raise Invalid("host_failed",
                    f"the stub acknowledged a report and sent no line within {ACK_WAIT_S}s")
        line = bytes(self._pending[:end]).decode("ascii", "replace")
        del self._pending[:end + 2]
        return line

    def _read(self, deadline: float) -> bool:
        """What the stub sent, appended; False once `deadline` passed with nothing new."""
        while (left := deadline - time.monotonic()) > 0:
            cancel.check()
            if self.parked():
                raise Invalid("wait_stopped", "the machine stopped at the debugger while the "
                              "stub's answer was awaited: the stub runs on the timer tick, "
                              "which a stopped machine never reaches")
            self.sock.settimeout(min(left, READ_SLICE_S))
            try:
                got = self.sock.recv(4096)
            except TimeoutError:
                continue
            except OSError as e:
                raise Invalid("session_broken", f"the input socket is gone ({e})") from None
            if not got:
                raise Invalid("session_broken", "the emulator closed the input socket")
            self._pending += got
            return True
        return False
