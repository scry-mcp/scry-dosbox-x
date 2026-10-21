"""A faulty line between the server and the guest's stub, put in at the session's own seam
(`dosbox_session.INPUT_LINE`): it holds the real input socket and, on its first frame or its
first acknowledgement, does ONE thing to it, so each of the stub's recovery paths can be
provoked live. It counts what crossed it, which is what the cells judge."""

from __future__ import annotations

import socket
import time

#: A timer tick of the guest's, the pace the stub reads at.
TICK_S = 1 / 18.2


class FaultyLine:
    """`fault` is one of `lose_ack` (the stub's first acknowledgement never reaches the host),
    `dribble` (every frame sent a byte at a time, a tick and a half apart), `short` (the first
    frame cut after its sequence byte, the rest never sent) or `close` (the first frame cut
    half-way and the socket closed)."""

    def __init__(self, sock: socket.socket, fault: str) -> None:
        self.sock, self.fault = sock, fault
        self.frames_sent = 0
        self.writes = 0
        self.acks_dropped = 0
        self._dropping = fault == "lose_ack"

    def settimeout(self, value: float | None) -> None:
        self.sock.settimeout(value)

    def sendall(self, data: bytes) -> None:
        self.frames_sent += 1
        first = self.frames_sent == 1
        if self.fault == "dribble":
            for byte in data:
                self.sock.sendall(bytes((byte,)))
                self.writes += 1
                time.sleep(TICK_S * 1.5)
            return
        if self.fault == "short" and first:
            self.sock.sendall(data[:2])          # SYNC and the sequence byte, then nothing
            return
        if self.fault == "close" and first:
            self.sock.sendall(data[:len(data) // 2])
            self.sock.close()
            raise OSError("the line closed mid-send")
        self.sock.sendall(data)

    def recv(self, size: int) -> bytes:
        got = self.sock.recv(size)
        if self._dropping and got:
            at = got.find(0x5A)
            if at >= 0 and len(got) >= at + 4:
                self._dropping = False
                self.acks_dropped += 1
                got = got[:at] + got[at + 4:]
                if not got:              # nothing else came with it: wait for what does
                    got = self.sock.recv(size)
        return got
