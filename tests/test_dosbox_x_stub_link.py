"""The host half of the stub's protocol against a double of the guest's handler
(`guest/scry.asm`). The constants are read off the asm so the double cannot drift from them."""

from __future__ import annotations

import math
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

ASM = (Path(link.__file__).parent / "guest" / "scry.asm").read_text(encoding="utf-8")


def _lengths() -> dict[int, int]:
    """Each opcode's frame length after SYNC, as `parse` decides it."""
    parse = ASM[ASM.index("\nparse:"):]
    block = parse[parse.index("mov     cl,"):parse.index(".len:")]
    lengths, length = {}, 0
    for op in re.finditer(r"mov\s+cl, (\d+)|cmp\s+al, '(.)'", block):
        if op.group(1):
            length = int(op.group(1))
        else:
            lengths[ord(op.group(2))] = length
    return lengths


LENGTHS = _lengths()
STALE_TICKS = int(re.search(r"^STALE_TICKS\s+equ\s+(\d+)", ASM, re.M).group(1))  # type: ignore[union-attr]
TICK_S = 0.005
SPACING_S = link.FRAME_SPACING_S
REPORT = b"STUB  . mouse x=1 y=2 buttons=0 max=639,199 mode=19 screen=320x200\r\n"


class Stub:
    """The stub's two entries and `service`, ported. IRQ 4 enters as bytes arrive unless
    `masked`; the tick enters every `TICK_S` unless `timer_owned` (a program that took INT 08h).
    `dribble` writes a byte at a time; `ack_late` holds the acknowledgement of those frames
    (counted from 0) for `late_s`; `nested` enters IRQ 4 again under each `M`'s INT 33h."""

    def __init__(self, sock: socket.socket, last_seq: int = 0, dribble: bool = False,
                 ack_late: frozenset[int] = frozenset(), late_s: float = 0.0,
                 deaf: bool = False, stale_ticks: int = STALE_TICKS, masked: bool = False,
                 timer_owned: bool = False, nested: bool = False) -> None:
        self.sock, self.dribble, self.ack_late, self.late_s = sock, dribble, ack_late, late_s
        self.stale_ticks, self.nested = stale_ticks, nested
        self.irq4, self.ticks = not (deaf or masked), not (deaf or timer_owned)
        self.last_seq = last_seq
        self.carried: list[bytes] = []
        self.carried_at: list[float] = []
        self.answered = 0
        self.uart: deque[int] = deque()
        self.hunting, self.got, self.have, self.stale = True, 0, 0, 0
        self.busy = self.ticking = False
        self.nested_left = 0
        self.frame = bytearray(8)
        self.most_queued = 0
        self.closed = False
        self._cli = threading.RLock()
        for target in (self._receive, self._clock):
            threading.Thread(target=target, daemon=True).start()

    def _receive(self) -> None:
        try:
            while got := self.sock.recv(4096):
                with self._cli:
                    self.uart.extend(got)
                    self.most_queued = max(self.most_queued, len(self.uart))
                if self.irq4:
                    self.serial()
        except OSError:
            pass
        self.closed = True

    def _clock(self) -> None:
        while not self.closed:
            time.sleep(TICK_S)
            if self.ticks:
                try:
                    self.tick()
                except OSError:
                    return

    def tick(self) -> None:
        self._enter(ticking=True)

    def serial(self) -> None:
        self._enter(ticking=False)

    def _enter(self, ticking: bool) -> None:
        with self._cli:
            if self.busy:
                self.nested_left += 1
                return
            self.ticking = ticking
            self._service()

    def _service(self) -> None:
        self.busy = True
        while self.uart:
            byte = self.uart.popleft()
            if self.hunting:
                if byte == link.SYNC:
                    self.hunting, self.stale = False, 0
                continue
            self.stale = 0
            self.frame[self.got] = byte
            self.got += 1
            self._parse()
        if self.ticking and not self.hunting:
            self.stale += 1
            if self.stale >= self.stale_ticks:
                self.hunting, self.got, self.have = True, 0, 0
        self.busy = False

    def _parse(self) -> None:
        while self.have < self.got:
            self.have += 1
            if self.have < 2:
                continue
            length = LENGTHS.get(self.frame[1])
            if length is None:
                self._resync(0)
                continue
            if self.have < length:
                continue
            whole = bytes(self.frame[:length])
            if link.frame(whole[0], whole[1:-1])[1:] != whole:
                self._resync(0)
                continue
            self._carry(whole[:-1])
            self._resync(length)

    def _resync(self, at: int) -> None:
        rest = bytes(self.frame[at:self.got])
        sync = rest.find(link.SYNC)
        if sync < 0:
            self.hunting, self.got, self.have = True, 0, 0
            return
        rest = rest[sync + 1:]
        self.frame[:len(rest)] = rest
        self.got, self.have, self.stale = len(rest), 0, 0

    def _carry(self, frame: bytes) -> None:
        seq, command = frame[0], frame[1:]
        carried = seq != self.last_seq
        if carried:
            self.last_seq = seq
            self.carried.append(command)
            self.carried_at.append(time.monotonic())
            if self.nested and command[0] == ord("M"):
                self.serial()
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
    monkeypatch.setattr(link, "FRAME_SPACING_S", 0.0)


KEYS = [b"K\x1e", b"K\x9e", b"M\x10\x00\x20\x00", b"B\x80"]


def test_the_protocol_constants_are_the_stubs_own() -> None:
    for name, value in (("SYNC", link.SYNC), ("ACK", link.ACK)):
        found = re.search(rf"^{name}\s+equ\s+0?([0-9A-Fa-f]+)h", ASM, re.M)
        assert found and int(found.group(1), 16) == value, name
    assert f"proto={inputs.STUB_PROTOCOL} motion=$'" in ASM
    assert f"'SCRY-INJECT-{inputs.STUB_PROTOCOL}'" in ASM


def test_the_frame_lengths_are_read_off_the_stubs_parser() -> None:
    assert {ord("K"): 4, ord("B"): 4, ord("M"): 7, ord("R"): 3, ord("S"): 3} == LENGTHS


@pytest.mark.parametrize("entry", [{"timer_owned": True}, {"masked": True}],
                         ids=["IRQ 4 alone: the program owns the timer",
                              "the tick alone: the program masked IRQ 4"])
def test_either_entry_alone_carries_every_command(pair: Any, entry: dict[str, bool]) -> None:
    host, guest = pair
    stub = Stub(guest, masked=entry.get("masked", False),
                timer_owned=entry.get("timer_owned", False))
    assert link.Link(host).send(KEYS) == []
    assert stub.carried == KEYS


def test_an_entry_under_the_stubs_own_driver_call_leaves_the_bytes_to_the_next(
        pair: Any) -> None:
    """IRQ 4 raised inside `M`'s INT 33h finds `service` busy and reads nothing."""
    host, guest = pair
    stub = Stub(guest, nested=True)
    assert link.Link(host).send(KEYS) == []
    assert stub.carried == KEYS and stub.nested_left == 1


def test_under_irq_4_alone_a_short_frame_is_resynced_by_its_resend(pair: Any) -> None:
    """With no tick, nothing ages the short frame out: the resend's bytes are what resync it."""
    host, guest = pair
    stub = Stub(guest, timer_owned=True)
    link.Link(Lossy(host, {0: slice(0, -1)})).send([b"K\x1e"])  # type: ignore[arg-type]
    assert stub.carried == [b"K\x1e"] and stub.stale == 0


def test_an_unknown_opcode_is_read_past_and_the_frame_behind_it_carried(pair: Any) -> None:
    """A SYNC and a sequence byte with nothing after: the next frame's SYNC is read as their
    opcode, unknown, and read again it is the frame it starts."""
    host, guest = pair
    stub = Stub(guest, timer_owned=True)
    host.sendall(bytes((link.SYNC, 7)))
    line = Lossy(host, {})
    assert link.Link(line).send([b"K\x1e"]) == []  # type: ignore[arg-type]
    assert stub.carried == [b"K\x1e"] and line.frames == 1, "it took a resend to be found"


def test_each_command_waits_for_its_acknowledgement_and_is_carried_out_once(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest)
    assert link.Link(host).send(KEYS) == []
    assert stub.carried == KEYS and stub.most_queued <= 1 + max(LENGTHS.values()), (
        "a frame went before its ack")


def test_frames_go_a_spacing_apart_and_the_spacing_outlasts_a_50_hz_frame(
        pair: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stub carries a frame the moment it is whole, so the host keeps a make and its break
    apart long enough for a program that reads its keys once a frame to see the make."""
    monkeypatch.setattr(link, "FRAME_SPACING_S", SPACING_S)
    host, guest = pair
    stub = Stub(guest)
    link.Link(host).send(KEYS)
    gaps = [b - a for a, b in zip(stub.carried_at, stub.carried_at[1:], strict=False)]
    assert len(gaps) == len(KEYS) - 1 and min(gaps) >= link.FRAME_SPACING_S, gaps
    assert link.FRAME_SPACING_S > 1 / 50


class Retraces:
    """A parked machine: the stub runs only when the host advances it, once per retrace."""

    FRAME_MS = 14.27

    def __init__(self, stub: Stub) -> None:
        self.stub, self.clock_ms, self.carried_ms, self.run = stub, 0.0, list[float](), 0

    def __call__(self) -> float:
        time.sleep(0.01)                  # the bytes reach the emulated UART before it runs
        before = len(self.stub.carried)
        self.stub.serial()
        self.clock_ms += self.FRAME_MS
        self.run += 1
        self.carried_ms += [self.clock_ms] * (len(self.stub.carried) - before)
        return self.clock_ms


def test_a_parked_machine_takes_each_frame_by_retraces_a_guest_tick_apart(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest, deaf=True)
    run = Retraces(stub)
    assert link.Link(host).send(KEYS + [b"R"], run) == [REPORT[:-2].decode()]
    assert stub.carried == KEYS + [b"R"], stub.carried
    gaps = [b - a for a, b in zip(run.carried_ms, run.carried_ms[1:], strict=False)]
    assert min(gaps) >= link.FRAME_SPACING_MS, gaps


@pytest.mark.parametrize("gap_s", [0.0, 0.1], ids=["back to back", "a client's pause apart"])
def test_two_parked_posts_take_the_retraces_their_guest_time_needs_whatever_the_wall_clock(
        pair: Any, gap_s: float) -> None:
    """A replay sends the two posts back to back; the session that recorded them did not."""
    host, guest = pair
    run = Retraces(Stub(guest, deaf=True))
    line = link.Link(host)
    line.send([b"K\x1e"], run)
    first = run.run
    time.sleep(gap_s)
    line.send([b"K\x9e"], run)
    spacing = math.ceil(link.FRAME_SPACING_MS / Retraces.FRAME_MS)
    assert (first, run.run - first) == (1, spacing + 1), (first, run.run)


def test_a_clock_that_went_back_is_no_frame_to_wait_after(pair: Any) -> None:
    """A state load puts the guest's clock behind the last frame's: nothing is waited out."""
    host, guest = pair
    run = Retraces(Stub(guest, deaf=True))
    line = link.Link(host)
    line.send([b"K\x1e"], run)
    run.clock_ms -= 1000
    before = run.run
    line.send([b"K\x9e"], run)
    assert run.run - before == 1, run.run - before


def test_a_parked_stub_that_never_answers_is_refused_in_retraces(pair: Any) -> None:
    host, guest = pair
    stub = Stub(guest, deaf=True)
    stub.serial = lambda: None  # type: ignore[method-assign]
    run = Retraces(stub)
    with pytest.raises(Invalid, match=f"{link.ACK_RETRACES} retraces each"):
        link.Link(host).send([b"K\x1e"], run)
    assert run.run == link.SENDS * link.ACK_RETRACES


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


@pytest.mark.parametrize("command", [b"K\xa5", b"M\xa5\x00\xa5\x00"],
                         ids=["a SYNC as the payload", "two SYNCs in the payload"])
def test_a_short_frame_holding_a_sync_is_found_again_in_its_own_bytes(
        pair: Any, command: bytes) -> None:
    """With no tick to age it, the resend completes the short frame wrongly; the stub reads the
    failed frame's bytes again from the one after its SYNC and finds the resend there."""
    host, guest = pair
    stub = Stub(guest, stale_ticks=10_000)
    link.Link(Lossy(host, {0: slice(0, -1)})).send([command])  # type: ignore[arg-type]
    assert stub.carried == [command]


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
