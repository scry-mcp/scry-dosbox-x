"""The debugger channel's client (`control`), held to a double that speaks the protocol
the emulator speaks: it dials the session's port and answers one `REQ` per line."""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
from channel_double import Machine, SilentChannel, session_over
from scry_core import cancel
from scry_core.reply_contract import Invalid

from scry_dosbox_x import control
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import session as ds


def _emulator(port: int, answer: Callable[[str], bytes | Iterable[bytes] | None],
              drop_after: int = 0) -> threading.Thread:
    """A double of the emulator's end: dials `port`, then for each request line sends what
    `answer` returns (None sends nothing, which is how a reply that never ends is made; a list
    is sent piece by piece with a pause between, so the reader sees separate reads). With
    `drop_after`, it hangs up after that many requests, unanswered, and dials again, as the
    emulator's I/O thread does."""
    def run() -> None:
        served = 0
        while True:
            with socket.create_connection((control.LOCAL_HOST, port)) as sock:
                buf = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        served += 1
                        if drop_after and served == drop_after:
                            break
                        out = answer(line.decode())
                        if isinstance(out, bytes):
                            sock.sendall(out)
                        elif out is not None:
                            for piece in out:
                                sock.sendall(piece)
                                time.sleep(0.05)
                    else:
                        continue
                    break
            time.sleep(0.2)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _rid(line: str) -> str:
    return line.split()[1]


def test_a_reply_is_read_between_its_begin_and_its_end() -> None:
    assert control.parse_reply(b"BEGIN 3 OK\nPONG\nEND 3", "3") == (True, ["PONG"], b"")
    assert control.parse_reply(b"BEGIN 3 ERR\nunknown\nEND 3\nBEGIN 4", "3") == (
        False, ["unknown"], b"BEGIN 4")
    assert control.parse_reply(b"BEGIN 3 OK\nEND 3", "3") == (True, [], b"")


def test_a_guest_byte_above_ascii_comes_back_as_itself() -> None:
    """A DOS name is code-page bytes: 0x85 is an accented letter, and a listing that carries it
    must give it back as that byte, never as a replacement character."""
    got = control.parse_reply(b"BEGIN 5 OK\n   0814  PR\x85BE\nEND 5", "5")
    assert got == (True, ["   0814  PR\x85BE"], b""), got
    assert control.parse_reply(b"BEGIN 6 OK\n\xff\nEND 6\nBEGIN 7 OK\n\xfe", "6") == (
        True, ["\xff"], b"BEGIN 7 OK\n\xfe")


def test_a_reply_not_yet_whole_is_not_a_reply() -> None:
    assert control.parse_reply(b"BEGIN 3 OK\nPONG\n", "3") is None
    assert control.parse_reply(b"", "3") is None


def test_the_end_of_request_1_is_not_the_end_of_request_10() -> None:
    assert control.parse_reply(b"BEGIN 1 OK\nx\nEND 10", "1") is None
    assert control.parse_reply(b"BEGIN 1 OK\nx\nEND 1\n", "1") == (True, ["x"], b"")


def test_a_stale_reply_before_the_awaited_one_is_dropped() -> None:
    got = control.parse_reply(b"BEGIN 1 OK\nold\nEND 1\nBEGIN 2 OK\nnew\nEND 2", "2")
    assert got == (True, ["new"], b"")


def test_a_verdict_that_is_neither_ok_nor_err_is_refused() -> None:
    with pytest.raises(Invalid, match="neither OK nor ERR"):
        control.parse_reply(b"BEGIN 3 MAYBE\nEND 3", "3")


def test_requests_go_out_numbered_and_come_back_answered() -> None:
    channel = control.ControlChannel(lambda: None)
    seen: list[str] = []

    def answer(line: str) -> bytes:
        seen.append(line)
        rid = _rid(line)
        if line.endswith("BREAK"):
            return f"BEGIN {rid} OK\nEND {rid}\n".encode()
        return f"BEGIN {rid} ERR\nunknown command\nEND {rid}\n".encode()
    _emulator(channel.port, answer)
    try:
        assert channel.request("BREAK") == (True, [])
        assert channel.request("EXEC NOPE") == (False, ["unknown command"])
        assert seen == ["REQ 1 BREAK", "REQ 2 EXEC NOPE"]
    finally:
        channel.close()


def test_a_reply_split_across_reads_is_assembled() -> None:
    channel = control.ControlChannel(lambda: None)
    _emulator(channel.port, lambda line: [b"BEGIN 1 OK\nPO", b"NG\nEN", b"D 1\n"])
    try:
        assert channel.request("PING") == (True, ["PONG"])
    finally:
        channel.close()


def test_a_reply_that_never_ends_is_host_failed_not_a_guess() -> None:
    channel = control.ControlChannel(lambda: None)
    _emulator(channel.port, lambda line: f"BEGIN {_rid(line)} OK\nhalf".encode())
    try:
        with pytest.raises(Invalid) as e:
            channel.request("BREAK", seconds=0.3)
        assert e.value.code == "host_failed" and "unknown" in str(e.value)
    finally:
        channel.close()


def test_a_running_guest_whose_channel_is_silent_is_said_silent_through_the_session(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The input tools tell "nothing was sent" from the silence's own type, so it has to come
    through the session's run-state question whole."""
    monkeypatch.setattr(control, "REPLY_S", 0.2)
    silent = SilentChannel(0.2)
    session = session_over(Machine(stopped=False), tmp_path)
    session.control = silent.channel
    try:
        with pytest.raises(control.ChannelSilent) as e:
            session.at_debugger()
    finally:
        silent.close()
    assert "RUNSTATE" in e.value.silence and e.value.code == "host_failed", e.value.silence


def test_a_channel_is_known_silent_from_a_request_it_left_unanswered_until_one_answers() -> None:
    """What the presence writer reads before it asks: during a host call, asking again only
    holds the channel for its whole bound in front of the next call's own request."""
    channel = control.ControlChannel(lambda: None)
    _emulator(channel.port,
              lambda line: b"" if line.endswith("1 PING") else f"BEGIN {_rid(line)} OK\nEND "
                                                              f"{_rid(line)}\n".encode())
    try:
        seen = [channel.silent]
        with pytest.raises(control.ChannelSilent):
            channel.request("PING", seconds=0.2)
        seen.append(channel.silent)
        assert channel.request("PING") == (True, [])
        seen.append(channel.silent)
        assert seen == [False, True, False], seen
    finally:
        channel.close()


def test_an_emulator_that_never_dials_is_no_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control, "CONTROL_ACCEPT_S", 0.3)
    channel = control.ControlChannel(lambda: None)
    try:
        with pytest.raises(Invalid) as e:
            channel.request("BREAK")
        assert e.value.code == "no_channel" and "mcp_server" in str(e.value)
    finally:
        channel.close()


def test_an_emulator_that_exits_before_dialling_is_said_at_once() -> None:
    channel = control.ControlChannel(lambda: 3)
    try:
        with pytest.raises(Invalid) as e:
            channel.request("BREAK")
        assert e.value.code == "session_broken" and "code 3" in str(e.value)
    finally:
        channel.close()


def test_a_closed_channel_refuses_rather_than_listening_again() -> None:
    channel = control.ControlChannel(lambda: None)
    channel.close()
    with pytest.raises(Invalid) as e:
        channel.request("PING")
    assert e.value.code == "session_broken"


def test_the_launch_points_the_emulator_at_the_session_s_channel(tmp_path: object) -> None:
    from pathlib import Path
    root = Path(str(tmp_path))
    launch = dlaunch.Launch(conf=root / "g.conf", cwd=root, seconds=30, control_port=40123)
    argv = dlaunch.build_argv(launch)
    i = argv.index("dosbox mcp_server=40123")
    assert argv[i - 1] == "-set"
    assert "dosbox mcp_server=40123" not in dlaunch.build_argv(
        dlaunch.Launch(conf=root / "g.conf", cwd=root, seconds=30))


@pytest.mark.parametrize("token", ["dosbox mcp_server=9", "dosbox mcp_server 9",
                                   "DOSBOX  MCP_SERVER=9", "mcp_server 9",
                                   "debugger headless=false"])
def test_a_caller_s_flags_cannot_repoint_the_channel(token: str) -> None:
    """Every spelling DOSBox-X's `-set` takes, the value after `=` or after a space."""
    with pytest.raises(Invalid) as e:
        dlaunch.check_flags(["-set", token])
    assert e.value.code == "bad_argument" and "debugger channel" in str(e.value)


def test_an_owned_key_is_found_with_its_value_after_a_space() -> None:
    with pytest.raises(Invalid) as e:
        dlaunch.check_flags(["-set", "dos break on int3 true"])
    assert e.value.code == "bad_argument" and "break_on_int3" in str(e.value)


class _Channel:
    """`BREAK` answered `ok`, and `RUNSTATE` stopped once `parks`."""

    def __init__(self, ok: bool, parks: bool) -> None:
        self.ok, self.parks = ok, parks
        self.sent: list[str] = []

    def request(self, command: str, seconds: float = control.REPLY_S,
                poll: Any = None) -> tuple[bool, list[str]]:
        self.sent.append(command)
        if command == "EXEC RUNSTATE":
            state = "stopped" if self.parks else "running"
            return True, [f"DEBUG: RUNSTATE {state} cycles=0 ms=0.000000000"]
        return self.ok, [] if self.ok else ["not now"]


def _session(ok: bool, parks: bool, alive: bool = True) -> ds.Session:
    s = ds.Session.__new__(ds.Session)
    s.control = _Channel(ok, parks)  # type: ignore[assignment]
    s.commands = frozenset({"RUNSTATE"})
    s._at_debugger, s._surveyed, s.stop_count = False, None, 0
    s.alive = lambda: alive  # type: ignore[method-assign]
    return s


def test_break_in_sends_break_and_waits_for_the_debugger_to_say_stopped() -> None:
    parked = _session(ok=True, parks=True)
    assert ds.Session.break_in(parked, seconds=1.0) >= 0
    assert parked.control.sent == ["BREAK", "EXEC RUNSTATE"]  # type: ignore[attr-defined]
    assert parked.at_debugger()


def test_break_in_says_when_the_stop_never_comes() -> None:
    with pytest.raises(Invalid) as e:
        ds.Session.break_in(_session(ok=True, parks=False), seconds=0.1)
    assert e.value.code == "not_settled" and "still be running" in str(e.value)


def test_break_in_on_an_emulator_that_died_says_so_at_once() -> None:
    """A dead emulator never parks: the wait refuses it as gone at its first poll rather than
    sitting out its bound to call the guest still running."""
    began = time.monotonic()
    with pytest.raises(Invalid) as e:
        ds.Session.break_in(_session(ok=True, parks=False, alive=False), seconds=5.0)
    assert e.value.code == "session_broken" and "GONE" in str(e.value), e.value
    assert time.monotonic() - began < 1.0, "the dead emulator's wait sat out its bound"


def test_break_in_says_when_the_channel_refuses() -> None:
    with pytest.raises(Invalid) as e:
        ds.Session.break_in(_session(ok=False, parks=True), seconds=1.0)
    assert e.value.code == "unexpected_answer" and "not now" in str(e.value)


def test_a_dropped_connection_is_taken_again_from_the_emulator_s_redial() -> None:
    """The emulator redials a second after it loses the channel; the listener stays open for
    the session's life, so the request after the drop reaches the new connection."""
    channel = control.ControlChannel(lambda: None)
    _emulator(channel.port, lambda line: f"BEGIN {_rid(line)} OK\nEND {_rid(line)}\n".encode(),
              drop_after=1)
    try:
        with pytest.raises(Invalid) as e:
            channel.request("BREAK")
        assert e.value.code == "session_broken" and "redials" in str(e.value)
        assert channel.request("BREAK") == (True, [])
    finally:
        channel.close()


@pytest.mark.parametrize("command", ["", "  ", "BREAK\nREQ 9 EXEC RUN", "PING\r"])
def test_a_request_is_one_non_empty_line(command: str) -> None:
    channel = control.ControlChannel(lambda: None)
    try:
        with pytest.raises(Invalid) as e:
            channel.request(command)
        assert e.value.code == "bad_argument"
    finally:
        channel.close()


class _Recording:
    """A stand-in for the channel that says whether it was closed."""
    made: list[_Recording] = []

    def __init__(self, exited: Callable[[], int | None]) -> None:
        self.port, self.closed = 40999, False
        _Recording.made.append(self)

    def close(self) -> None:
        self.closed = True


def test_a_spawn_that_fails_closes_the_channel_and_the_argv_named_its_port(
        tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    from pathlib import Path
    root = Path(str(tmp_path))
    (root / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    _Recording.made.clear()
    seen: list[list[str]] = []

    def spawn(argv: list[str], **_k: object) -> None:
        seen.append(argv)
        raise OSError("not spawned in a unit test")
    monkeypatch.setattr(control, "ControlChannel", _Recording)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    with pytest.raises(OSError, match="not spawned"):
        ds.Session(dlaunch.Launch(conf=root / "g.conf", cwd=root, seconds=30))
    assert [r.closed for r in _Recording.made] == [True]
    assert "dosbox mcp_server=40999" in seen[0]


def test_an_output_pipe_that_cannot_be_opened_closes_the_channel(
        tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from pathlib import Path
    root = Path(str(tmp_path))
    (root / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    _Recording.made.clear()

    def no_pipe() -> tuple[int, int]:
        raise OSError("out of descriptors")
    monkeypatch.setattr(control, "ControlChannel", _Recording)
    monkeypatch.setattr(os, "pipe", no_pipe)
    with pytest.raises(OSError, match="out of descriptors"):
        ds.Session(dlaunch.Launch(conf=root / "g.conf", cwd=root, seconds=30,
                                  debugger_headless=True))
    assert [r.closed for r in _Recording.made] == [True]


def test_close_closes_the_channel() -> None:
    import threading
    from types import SimpleNamespace
    s = ds.Session.__new__(ds.Session)
    s._closing, s._closed = threading.Lock(), False   # what `__init__` gives a close
    s.proc = SimpleNamespace(poll=lambda: 0, wait=lambda timeout=None: 0,
                             pid=1, returncode=0)
    s._signal_group = lambda sig: None  # type: ignore[method-assign]
    s._drainer = None
    s._out = None
    s.drain_failure = s.reap_failed = ""
    s.ended_how = "none"
    channel = _Recording(lambda: None)
    s.control = channel  # type: ignore[assignment]
    s.close()
    assert channel.closed and s.ended_how == "died"


def test_break_in_polls_for_the_cancel_while_it_waits_for_the_prompt(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def cancelled() -> None:
        raise asyncio.CancelledError
    monkeypatch.setattr(cancel, "check", cancelled)
    began = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        ds.Session.break_in(_session(ok=True, parks=False), seconds=5.0)
    assert time.monotonic() - began < 1.0


def test_the_channel_takes_one_request_at_a_time_from_any_thread(
        monkeypatch: pytest.MonkeyPatch) -> None:
    channel = control.ControlChannel(lambda: None)
    inside: list[int] = []
    overlaps: list[int] = []

    def slow(command: str, seconds: float, poll: Any) -> tuple[bool, list[str]]:
        inside.append(1)
        if len(inside) > 1:
            overlaps.append(1)
        time.sleep(0.05)
        inside.pop()
        return True, [command]
    monkeypatch.setattr(channel, "_request", slow)
    threads = [threading.Thread(target=channel.request, args=(f"PING {n}",)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    channel.close()
    assert overlaps == []
