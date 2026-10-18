"""The emulator's two local TCP routes, and the debugger channel that is one of them.

Both routes have the same shape: the SESSION listens before the emulator exists, and the
emulator dials it. The other way round, with the emulator listening, was measured losing: a
process that took the port between the server's check and the emulator's bind was left listening
beside it, and the session's connect reached THAT process. A port the kernel picks and the
session holds from that moment cannot be taken in between. `listen_local` and `await_dial` are
that shape, once; the serial input route (`dosbox_session.listen_input`) and the debugger channel
word their own refusals around them.

THE DEBUGGER CHANNEL is upstream's (`[dosbox] mcp_server=<port>`, off at 0): at start the emulator
dials 127.0.0.1:<port> and serves one request per line,

    REQ <id> PING | BREAK | EXEC <debugger command>

answered by

    BEGIN <id> OK|ERR
    <the lines the debugger printed while it ran>
    END <id>

polled from a timer tick as well as from the debugger's own loop, so it answers while the guest
RUNS. That is what makes it the way back into a running guest: `BREAK` is the debugger hotkey
without a window, a key nobody has to press on a screen nobody has to own. The dial is accepted
LAZILY, at the first request: the emulator dials from its init and the kernel's backlog keeps the
connection until then, so a session that never breaks in pays nothing for the channel. The
listener stays open for the session's life, because the emulator redials a second after it loses
the connection, and a closed port would make that loss permanent.
"""

from __future__ import annotations

import contextlib
import socket
import time
from collections.abc import Callable

from scry_core.reply_contract import Invalid

LOCAL_HOST = "127.0.0.1"
ACCEPT_SLICE_S = 0.1      # how often a wait for a dial looks up to see whether the emulator runs
# The dial happens at the emulator's init, long before anyone asks, so by the first request it
# is in the backlog: the bound only has to cover a request sent in the first second of a start,
# or the redial a second after a dropped connection.
CONTROL_ACCEPT_S = 5.0
REPLY_S = 5.0             # one request's reply; every command it carries is short
RECV_SLICE_S = 0.1


def listen_local(port: int) -> socket.socket:
    """A socket listening on `port` of the loopback (0: the kernel's pick, held from the moment
    it is picked). OSError when the port cannot be had; the caller says what for."""
    sock = socket.socket()
    try:
        # EXCLUSIVE where the platform has the word for it (Windows), and on POSIX the
        # TIME_WAIT of a port an earlier session used is not "in use".
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
    """The emulator's dial on `listener` within `seconds`: the connected socket, or the
    emulator's exit code if it died first (said at once, not after the whole bound), or None
    when the bound passed. The first connection is taken as the emulator's: the port is the
    kernel's pick, so a stranger would have to dial it inside the emulator's start."""
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

    A reply starts at its `BEGIN <id>` line and ends at `END <id>`; anything before the
    `BEGIN` is a reply to an earlier request nobody waited for (dropped), and anything after
    the `END` stays in `rest` for the next read."""
    text = buf.decode("utf-8", errors="replace")
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
    rest = text[after:].lstrip("\r\n").encode("utf-8")
    return verdict == "OK", lines, rest


def _no_poll() -> None:
    """A request with nothing to poll while it waits."""


class ControlChannel:
    """One session's end of the debugger channel: a listener for the session's life, a
    connection from the first request on, one request in flight at a time."""

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
        self.port: int = self._listener.getsockname()[1]

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
        """The connection is gone; the next request accepts the emulator's redial."""
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()
        return Invalid("session_broken", f"the debugger channel dropped ({why}); the emulator "
                       f"redials within a second, and the next request takes that connection")

    def request(self, command: str, seconds: float = REPLY_S,
                poll: Callable[[], None] = _no_poll) -> tuple[bool, list[str]]:
        """Send `PING`, `BREAK` or `EXEC <cmd>` and return `(ok, lines)` as the debugger
        answered them. A reply that does not end within `seconds` is `host_failed`: the
        request may or may not have acted, and saying which would be a guess. `poll` runs at
        each slice of the wait (a long command's caller passes `cancel.check`); a reply left
        unread by it is dropped by the next request's (`parse_reply`)."""
        if not command.strip() or "\n" in command or "\r" in command:
            raise Invalid("bad_argument", f"a channel request is one non-empty line; got "
                          f"{command!r}")
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
                raise Invalid("host_failed",
                    f"the debugger channel did not finish its reply to {command.split()[0]} "
                    f"within {seconds:g} s; whether it acted is unknown")
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
        return ok, lines

    def close(self) -> None:
        """Both sockets, quietly: the emulator's end is dying or dead by the time this runs."""
        for sock in (self._conn, self._listener):
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
        self._conn = self._listener = None
