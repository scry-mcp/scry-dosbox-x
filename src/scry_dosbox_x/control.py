"""The emulator's two local TCP routes, and the debugger channel that is one of them.

The session listens before the emulator exists and the emulator dials it, so no other process
can take the port between a check and the bind.

The debugger channel is upstream's (`[dosbox] mcp_server=<port>`): the emulator dials the
session and serves one request per line,

    REQ <id> PING | BREAK | EXEC <debugger command>

answered by

    BEGIN <id> OK|ERR
    <the lines the debugger printed while it ran>
    END <id>

It answers while the guest RUNS, so `BREAK` is the way into a running guest. The dial is accepted
lazily, at the first request, and the listener stays open for the session's life because the
emulator redials a second after losing the connection.
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from collections.abc import Callable

from scry_core.reply_contract import Invalid

LOCAL_HOST = "127.0.0.1"
ACCEPT_SLICE_S = 0.1
CONTROL_ACCEPT_S = 5.0
REPLY_S = 5.0
RECV_SLICE_S = 0.1


def listen_local(port: int) -> socket.socket:
    """A loopback socket listening on `port` (0: the kernel's pick). OSError if unavailable."""
    sock = socket.socket()
    try:
        # POSIX: REUSEADDR so a TIME_WAIT port is not "in use".
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        sock.setsockopt(socket.SOL_SOCKET, exclusive or socket.SO_REUSEADDR, 1)
        sock.bind((LOCAL_HOST, port))
        sock.listen(1)
    except OSError:
        sock.close()
        raise
    return sock


def await_dial(listener: socket.socket, seconds: float,
               exited: Callable[[], int | None]) -> socket.socket | int | None:
    """The emulator's dial within `seconds`: the socket, its exit code if it died first, or None."""
    deadline = time.monotonic() + seconds
    listener.settimeout(ACCEPT_SLICE_S)
    while True:
        try:
            sock, _ = listener.accept()
            return sock
        except TimeoutError:
            if (code := exited()) is not None:
                return code
            if time.monotonic() >= deadline:
                return None


def parse_reply(buf: bytes, rid: str) -> tuple[bool, list[str], bytes] | None:
    """`(ok, lines, rest)` once `buf` holds the whole reply to `rid`, else None.

    Anything before its `BEGIN` is an abandoned earlier reply (dropped); after `END` is `rest`.
    Read a byte to a character: a listing carries the guest's own code-page bytes."""
    text = buf.decode("latin-1")
    begin = f"BEGIN {rid} "
    start = text.find(begin)
    if start < 0:
        return None
    end_mark = f"\nEND {rid}"
    end = text.find(end_mark, start)
    if end < 0:
        return None
    after = end + len(end_mark)
    if after < len(text) and text[after] not in "\r\n":
        return None              # `END 1` is not the end of request 10
    head, *lines = text[start:end].split("\n")
    verdict = head[len(begin):].strip()
    if verdict not in ("OK", "ERR"):
        raise Invalid("unexpected_answer",
                      f"the debugger channel answered request {rid} with {head!r}, which is "
                      f"neither OK nor ERR")
    rest = text[after:].lstrip("\r\n").encode("latin-1")
    return verdict == "OK", lines, rest


def _no_poll() -> None:
    """No-op poll."""


HOST_CALL = "a long host call (a DOS file or device operation the emulator waits on)"
#: How a caller learns the host call ended: `status` fails while it lasts.
UNTIL_IT_ENDS = "`status` answers again at once when the host call ends"


class ChannelSilent(Invalid):
    """`host_failed` for a request the emulator never finished answering. `silence` says why
    without the request's own doubt, for a caller that knows what it did before asking."""

    def __init__(self, command: str, seconds: float) -> None:
        verb, *rest = command.split()
        asked = rest[0] if verb == "EXEC" and rest else verb
        self.silence = (f"the debugger channel did not answer {asked} within {seconds:g} s, as "
                        f"it does not while the emulator is inside {HOST_CALL}")
        super().__init__("host_failed",
            f"the debugger channel did not finish its reply to {verb} within {seconds:g} s; "
            f"whether it acted is unknown. A guest stuck in {HOST_CALL} is a likely cause")


class ControlChannel:
    """One session's end of the debugger channel; a lock keeps one request in flight."""

    def __init__(self, exited: Callable[[], int | None]) -> None:
        try:
            self._listener: socket.socket | None = listen_local(0)
        except OSError as e:
            raise Invalid("host_failed", f"the kernel would not hand out a free port for the "
                          f"debugger channel ({e})") from None
        self._conn: socket.socket | None = None
        self._exited = exited
        self._buf = b""
        self._next = 1
        self._in_flight = threading.Lock()
        self.port: int = self._listener.getsockname()[1]
        #: The last request went unanswered and none has been answered since.
        self.silent = False

    def _connected(self) -> socket.socket:
        if self._conn is not None:
            return self._conn
        if self._listener is None:
            raise Invalid("session_broken", "the debugger channel is closed")
        got = await_dial(self._listener, CONTROL_ACCEPT_S, self._exited)
        if isinstance(got, int):
            raise Invalid("session_broken",
                          f"the emulator exited (code {got}) without dialling its debugger channel")
        if got is None:
            raise Invalid("no_channel",
                f"the emulator never dialled the debugger channel on port {self.port}: this "
                f"build has no `mcp_server` (a DOSBox-X that predates it upstream, or one built "
                f"without the debugger), so a running guest cannot be reached")
        got.settimeout(RECV_SLICE_S)
        self._conn, self._buf = got, b""
        return got

    def _dropped(self, why: str) -> Invalid:
        """The connection is gone; the next request accepts the redial."""
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()
        return Invalid("session_broken", f"the debugger channel dropped ({why}); the emulator "
                       f"redials within a second, and the next request takes that connection")

    def request(self, command: str, seconds: float = REPLY_S,
                poll: Callable[[], None] = _no_poll) -> tuple[bool, list[str]]:
        """Send `PING`, `BREAK` or `EXEC <cmd>`; return `(ok, lines)`.

        No reply within `seconds` is `host_failed`, and whether the request acted is unknown.
        `poll` runs at each slice of the wait."""
        if not command.strip() or "\n" in command or "\r" in command:
            raise Invalid("bad_argument", f"a channel request is one non-empty line; got "
                          f"{command!r}")
        with self._in_flight:
            return self._request(command, seconds, poll)

    def _request(self, command: str, seconds: float,
                 poll: Callable[[], None]) -> tuple[bool, list[str]]:
        conn = self._connected()
        rid = str(self._next)
        self._next += 1
        try:
            conn.sendall(f"REQ {rid} {command}\n".encode())
        except OSError as e:
            raise self._dropped(str(e)) from None
        deadline = time.monotonic() + seconds
        while (got := parse_reply(self._buf, rid)) is None:
            poll()
            if time.monotonic() >= deadline:
                self.silent = True
                raise ChannelSilent(command, seconds)
            try:
                chunk = conn.recv(65536)
            except TimeoutError:
                continue
            except OSError as e:
                raise self._dropped(str(e)) from None
            if not chunk:
                raise self._dropped("the emulator closed it")
            self._buf += chunk
        ok, lines, self._buf = got
        self.silent = False
        return ok, lines

    def close(self) -> None:
        """Close both sockets; the emulator's end is already dying."""
        for sock in (self._conn, self._listener):
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
        self._conn = self._listener = None
