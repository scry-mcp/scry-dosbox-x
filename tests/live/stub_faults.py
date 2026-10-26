"""A faulty line at the session's `INPUT_LINE` seam: one fault on the first frame or ack."""

from __future__ import annotations

import socket
import time

#: One guest timer tick: the pace the stub drops a short frame at.
TICK_S = 1 / 18.2


class FaultyLine:
    """`fault`: `lose_ack`, `dribble`, `short`, `tail_sync` (the first frame whose payload is a
    SYNC arrives short its check) or `close`."""

    def __init__(self, sock: socket.socket, fault: str) -> None:
        self.sock, self.fault = sock, fault
        self.frames_sent = 0
        self.writes = 0
        self.acks_dropped = 0
        self.cut = False
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
            self.sock.sendall(data[:2])
            return
        if self.fault == "tail_sync" and not self.cut and data[3] == 0xA5:
            self.cut = True
            self.sock.sendall(data[:-1])
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
                if not got:
                    got = self.sock.recv(size)
        return got
