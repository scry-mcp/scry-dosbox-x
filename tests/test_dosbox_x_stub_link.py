"""The host half of protocol 3 against a double of the guest's tick handler (`guest/inject.asm`).
The constants are read off the asm so the double cannot drift from them."""

from __future__ import annotations

import re
import socket
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core.reply_contract import Invalid

import dosbox_inputs as inputs
import dosbox_stub_link as link

ASM = (Path(link.__file__).parent / "guest" / "inject.asm").read_text(encoding="utf-8")
#: Each opcode's frame length after SYNC (sequence, opcode, payload, check).
LENGTHS = {ord("K"): 4, ord("B"): 4, ord("M"): 7, ord("R"): 3, ord("S"): 3}
STALE_TICKS = int(re.search(r"^STALE_TICKS\s+equ\s+(\d+)", ASM, re.M).group(1))  # type: ignore[union-attr]
TICK_S = 0.005
REPORT = b"STUB  . mouse x=1 y=2 buttons=0 max=639,199 mode=19 screen=320x200\r\n"


class Stub:
    """The tick handler, ported. `dribble` writes a byte at a time; `ack_late` holds the
    acknowledgement of those frames (counted from 0) for `late_s`."""

    def __init__(self, sock: socket.socket, last_seq: int = 0, dribble: bool = False,
                 ack_late: frozenset[int] = frozenset(), late_s: float = 0.0,
                 deaf: bool = False, stale_ticks: int = STALE_TICKS) -> None:
        self.sock, self.dribble, self.ack_late, self.late_s = sock, dribble, ack_late, late_s
        self.deaf, self.stale_ticks = deaf, stale_ticks
        self.last_seq = last_seq
        self.carried: list[bytes] = []
        self.answered = 0
        self.uart: deque[int] = deque()
        self.hunting, self.have, self.stale = True, 0, 0
        self.frame = bytearray(8)
        self.most_queued = 0
        self.closed = False
        for target in (self._receive, self._ticks):
            threading.Thread(target=target, daemon=True).start()

    def _receive(self) -> None:
        try:
            while got := self.sock.recv(4096):
                self.uart.extend(got)
                self.most_queued = max(self.most_queued, len(self.uart))
        except OSError:
            pass
        self.closed = True

    def _ticks(self) -> None:
        while not self.closed:
            time.sleep(TICK_S)
            if not self.deaf:
                try:
                    self.tick()
                except OSError:
                    return

    def tick(self) -> None:
        while self.uart:
            byte = self.uart.popleft()
            if self.hunting:
                if byte == link.SYNC:
                    self.hunting, self.have, self.stale = False, 0, 0
                continue
            self.stale = 0
            self.frame[self.have] = byte
            self.have += 1
            if self.have < 2:
                continue
            length = LENGTHS.get(self.frame[1])
            if length is None:
                self.hunting = True
                continue
            if self.have < length:
                continue
            self.hunting = True
            whole = bytes(self.frame[:length])
            if link.frame(whole[0], whole[1:-1])[1:] != whole:
                continue
            self._carry(whole[:-1])
            return
        if not self.hunting:
            self.stale += 1
            if self.stale >= self.stale_ticks:
                self.hunting = True

    def _carry(self, frame: bytes) -> None:
        seq, command = frame[0], frame[1:]
        carried = seq != self.last_seq
        if carried:
            self.last_seq = seq
            self.carried.append(command)
        n = self.answered
        self.answered += 1
        out = bytes((link.ACK, seq, command[0], int(carried)))
        out += REPORT if command[0] == ord("R") else b""
        if n in self.ack_late:
            threading.Timer(self.late_s, self._send, (out,)).start()
        else:
            self._send(out)

    def _send(self, data: bytes) -> None:
        if self.closed:
            return
        try:
            for part in ([data[i:i + 1] for i in range(len(data))] if self.dribble else [data]):
                self.sock.sendall(part)
        except OSError:
            pass


class Lossy:
    """The host's socket; `keep` maps a frame index (resends counted) to the slice that arrives."""

    def __init__(self, sock: socket.socket, keep: dict[int, slice]) -> None:
        self.sock, self.keep, self.frames = sock, keep, 0

    def sendall(self, data: bytes) -> None:
        n = self.frames
        self.frames += 1
        self.sock.sendall(data[self.keep[n]] if n in self.keep else data)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.sock, name)


def _acks_with_no_line(guest: socket.socket) -> None:
    """Acknowledge the first frame read, send nothing after."""
    def ack_only() -> None:
        frame = guest.recv(16)
        guest.sendall(bytes((link.ACK, frame[1], frame[2], 1)))
    threading.Thread(target=ack_only, daemon=True).start()


@pytest.fixture
def pair() -> Any:
    host, guest = socket.socketpair()
    yield host, guest
    host.close()
    guest.close()


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(link, "ACK_WAIT_S", 0.2)


KEYS = [b"K\x1e", b"K\x9e", b"M\x10\x00\x20\x00", b"B\x80"]


def test_the_protocol_constants_are_the_stubs_own() -> None:
    for name, value in (("SYNC", link.SYNC), ("ACK", link.ACK)):
        found = re.search(rf"^{name}\s+equ\s+0?([0-9A-Fa-f]+)h", ASM, re.M)
        assert found and int(found.group(1), 16) == value, name
    assert f"proto={inputs.STUB_PROTOCOL}'" in ASM
    assert f"'SCRY-INJECT-{inputs.STUB_PROTOCOL}'" in ASM


def test_each_command_waits_for_its_acknowledgement_and_is_carried_out_once(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest)
    assert link.Link(host).send(KEYS) == []
    assert stub.carried == KEYS and stub.most_queued <= 1 + max(LENGTHS.values()), (
        "a frame went before its ack")


def test_a_report_comes_back_after_its_acknowledgement_even_a_byte_at_a_time(
        pair: Any) -> None:
    host, guest = pair
    Stub(guest, dribble=True)
    assert link.Link(host).send([b"K\x1e", b"R"]) == [REPORT[:-2].decode()]


@pytest.mark.parametrize("arrives", [slice(0, 0), slice(0, 1), slice(0, 2), slice(0, 3)],
                         ids=["nothing", "its SYNC alone", "SYNC and sequence", "short"])
def test_a_frame_cut_on_the_way_is_sent_again_and_runs_nothing_else(
        pair: Any, arrives: slice) -> None:
    """The resend is read as itself, never its SYNC as a sequence byte; frame 75 is cut because
    that misreading would run a key."""
    host, guest = pair
    stub = Stub(guest)
    keys = [bytes((ord("K"), n)) for n in range(80)]
    link.Link(Lossy(host, {ord("K") - 1: arrives})).send(keys)  # type: ignore[arg-type]
    assert stub.carried == keys


def test_a_frame_short_its_tail_on_a_slow_guest_is_never_completed_by_the_resend(
        pair: Any) -> None:
    """The resend's first bytes complete the short frame, which fails its check and runs nothing."""
    host, guest = pair
    stub = Stub(guest, stale_ticks=10_000)
    link.Link(Lossy(host, {1: slice(0, -1)})).send(KEYS)  # type: ignore[arg-type]
    assert stub.carried == KEYS, "the short frame ran with the resend's bytes as its tail"


def test_a_lost_acknowledgement_is_answered_by_the_repeat_and_never_carried_out_twice(
        pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest, ack_late=frozenset({0}), late_s=10.0)
    link.Link(host).send(KEYS)
    assert stub.carried == KEYS, "the repeat of a frame already carried out ran again"


def test_a_late_twin_acknowledgement_is_passed_over(pair: Any) -> None:
    """The next command waits for its own acknowledgement, not the late twin's."""
    host, guest = pair
    stub = Stub(guest, ack_late=frozenset({0}), late_s=link.ACK_WAIT_S * 1.5)
    link.Link(host).send(KEYS)
    assert stub.carried == KEYS


def test_a_first_send_answered_as_a_repeat_goes_again_under_the_next_sequence(
        pair: Any) -> None:
    """A stub holding the host's first sequence takes it for a repeat: sent again, renumbered."""
    host, guest = pair
    stub = Stub(guest, last_seq=1)
    link.Link(host).send([b"K\x1e"])
    assert stub.carried == [b"K\x1e"]


def test_the_sequence_wraps_past_255_and_never_carries_0(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest)
    sent = link.Link(host)
    commands = [bytes((ord("K"), n % 128)) for n in range(300)]
    sent.send(commands)
    assert stub.carried == commands and sent.seq == 300 % 255


def test_a_stub_that_never_answers_is_refused_naming_what_went_in_before(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest)
    lossy = Lossy(host, {n: slice(0, 0) for n in range(1, 99)})
    with pytest.raises(Invalid, match=r"no acknowledgement of a .K. command.*\(1 of 4 commands"):
        link.Link(lossy).send(KEYS)  # type: ignore[arg-type]
    assert stub.carried == KEYS[:1]


def test_an_acknowledged_report_with_no_line_is_refused(pair: Any) -> None:
    host, guest = pair
    _acks_with_no_line(guest)
    with pytest.raises(Invalid, match="sent no line"):
        link.Link(host).send([b"R"])


def test_a_machine_that_stops_under_the_wait_is_said_at_once(pair: Any) -> None:
    host, guest = pair
    Stub(guest, deaf=True)
    began = time.monotonic()
    with pytest.raises(Invalid) as e:
        link.Link(host, parked=lambda: True).send([b"K\x1e"])
    assert e.value.code == "wait_stopped" and time.monotonic() - began < link.ACK_WAIT_S


@pytest.mark.parametrize("closed", ["before the send", "under the wait"])
def test_a_closed_line_is_the_route_gone(pair: Any, closed: str) -> None:
    host, guest = pair
    if closed == "before the send":
        guest.close()
    else:
        threading.Timer(0.05, guest.close).start()
    with pytest.raises(Invalid) as e:
        link.Link(host).send([b"K\x1e"])
    assert e.value.code == "session_broken", e.value


def test_a_report_acknowledged_with_no_line_counts_its_command_as_acknowledged(
        pair: Any) -> None:
    host, guest = pair
    _acks_with_no_line(guest)
    with pytest.raises(Invalid, match=r"\(1 of 1 commands acknowledged\)"):
        link.Link(host).send([b"R"])


def test_an_acknowledgement_already_on_the_line_is_read_before_a_stop_is_named(
        pair: Any) -> None:
    """An ack already on the line means carried, not refused as stopped (a caller would resend)."""
    host, guest = pair

    def ack_then_park() -> None:
        frame = guest.recv(16)
        guest.sendall(bytes((link.ACK, frame[1], frame[2], 1)))
    threading.Thread(target=ack_then_park, daemon=True).start()
    time.sleep(0.05)
    parked = {"yes": False}
    sent = link.Link(host, parked=lambda: parked["yes"])

    def write_then_park(data: bytes) -> None:
        host.sendall(data)
        time.sleep(0.05)
        parked["yes"] = True
    sent._write = write_then_park  # type: ignore[method-assign]
    assert sent.send([b"K\x1e"]) == []


def test_a_dropped_first_frame_to_a_stub_whose_last_sequence_is_its_own_is_still_carried(
        pair: Any) -> None:
    """After a loss a repeat answer cannot say whether the command ran; the link proves the
    sequence first, so the command is carried out once."""
    host, guest = pair
    stub = Stub(guest, last_seq=1)
    loaded = link.Link(cast(Any, Lossy(host, {0: slice(0, 0)})))
    loaded.unprove()
    loaded.send([b"K\x1e"])
    assert stub.carried[-1:] == [b"K\x1e"] and b"K\x1e" not in stub.carried[:-1], stub.carried
