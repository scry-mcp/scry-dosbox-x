"""A number typed into the debugger never starts with a letter.

`GetHexValue` looks a word up as a flag, a register or a loaded symbol before it reads digits, so
an unquoted `AF` or `FACE` is not the number. Each sender is stopped at the command that carries
its number.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, cast

import pytest
from dosbox_x_server_support import FakeSession

from scry_dosbox_x import binary as dbinary
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import driving, find, freezes, hardware
from scry_dosbox_x import session as ds
from scry_dosbox_x import taps as tapping

COLLIDING = (0xAC, 0xAF, 0xCF, 0xDF, 0xAD, 0xFA)
UNCHANGED = (0, 5, 0x10, 0x1AF, 0x1FFFF)
#: A cell letter (`MEMFIND ... B`) is read by the command itself, not as a number.
NOT_NUMBERS = {"B", "W", "D"}


class Stop(Exception):
    """The command under test was recorded; nothing after it matters."""


class Recorder(FakeSession):
    """A stopped session that records the debugger commands it is given and stops at `stop_at`."""

    def __init__(self, cwd: Path, stop_at: str = "") -> None:
        super().__init__()
        self.launch = SimpleNamespace(cwd=cwd, logfile=None, captures_dir=None, watched=False,
                                      input_port=None, binary=None)
        self.stop_at = stop_at
        self.typed: list[str] = []

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        self.typed.append(command)
        if command.startswith("PORTINFO") and self.stop_at != "PORTINFO":
            port = int(command.split()[1], 16)
            return True, [f"DEBUG: PORTINFO {port:04X} R1=1 R2=1 R4=1 W1=1 W2=1 W4=1"]
        raise Stop

    def command(self, text: str, seconds: float | None = None) -> NoReturn:
        self.exec(text, seconds)
        raise AssertionError("unreachable")

    def require_run_state(self, what: str) -> None:
        """A build that reports its run state."""

    def breakpoints(self) -> list[dict[str, str]]:
        return []

    def _memdump_candidates(self) -> list[Path]:
        return ds.Session._memdump_candidates(cast(ds.Session, self))


def shadowed(command: str) -> list[str]:
    """The words of `command` the debugger would look up as a name before reading digits."""
    words = re.findall(r"[0-9A-Za-z_]+", command)
    return [w for w in words if re.fullmatch(r"[A-Fa-f][0-9A-Fa-f]*", w) and w not in NOT_NUMBERS]


@pytest.mark.parametrize("value", COLLIDING)
def test_a_number_starting_with_a_letter_is_typed_with_a_leading_zero(value: int) -> None:
    assert dbg.typed_hex(value) == f"0{value:X}"


@pytest.mark.parametrize("value", UNCHANGED)
def test_every_other_number_is_typed_as_it_always_was(value: int) -> None:
    assert dbg.typed_hex(value) == f"{value:X}"


def test_a_width_pads_first_and_the_letter_is_judged_after_it() -> None:
    assert (dbg.typed_hex(5, 2), dbg.typed_hex(0xAF, 2), dbg.typed_hex(0xAF, 4)) == (
        "05", "0AF", "00AF")


def _freeze(s: Recorder, v: int, d: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(dbinary, "heavy_debug", lambda _binary: True)
    monkeypatch.setattr(tapping, "place", lambda _decl, _session: (0x0814, v))
    return freezes.arm(cast(ds.Session, s), cast(Any, SimpleNamespace(width=1, ref="f")))


#: Each sender, the command of it that carries the number, and the value it types.
SENDERS: dict[str, tuple[str, Any]] = {
    "vgamemdump offset": ("VGAMEMDUMP", lambda s, v, d, mp: ds.Session.vgamemdump(s, v, 4, d)),
    "vgamemdump length": ("VGAMEMDUMP", lambda s, v, d, mp: ds.Session.vgamemdump(s, 0, v, d)),
    "set_register": ("SR", lambda s, v, d, mp: ds.Session.set_register(s, "AX", v)),
    "breakpoint_interrupt number": ("BPINT", lambda s, v, d, mp:
                                    ds.Session.breakpoint_interrupt(s, v)),
    "breakpoint_interrupt ah": ("BPINT", lambda s, v, d, mp:
                                ds.Session.breakpoint_interrupt(s, 0x21, v)),
    "start_scan offset": ("MEMFIND", lambda s, v, d, mp: find.start_scan(s, 0, v, 16, 1)),
    "start_scan length": ("MEMFIND", lambda s, v, d, mp: find.start_scan(s, 0, 0, v, 1)),
    "filter_scan": ("MEMS", lambda s, v, d, mp: find.filter_scan(s, "=", v)),
    "port_read": ("INP", lambda s, v, d, mp: hardware.port_read(s, v)),
    "port_write port": ("OUTB", lambda s, v, d, mp: hardware.port_write(s, v, 0)),
    "port_write value": ("OUTB", lambda s, v, d, mp: hardware.port_write(s, 0x21, v)),
    "log_cpu": ("LOGC", lambda s, v, d, mp: driving.log_cpu(s, "LOGC", v, 0.0, 1.0)),
    "freeze offset": ("FM", _freeze),
}


def _typed_by(sender: str, value: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
              ) -> list[str]:
    word, call = SENDERS[sender]
    s = Recorder(tmp_path, stop_at=word)
    (tmp_path / "sub").mkdir(exist_ok=True)

    def released(session: Any, command: str) -> NoReturn:
        s.typed.append(command)
        raise Stop
    monkeypatch.setattr(driving, "release", released)
    with pytest.raises(Stop):
        call(s, value, tmp_path / "sub" / "out.bin", monkeypatch)
    return [c for c in s.typed if c.split()[0] == word]


@pytest.mark.parametrize("value", COLLIDING)
@pytest.mark.parametrize("sender", SENDERS)
def test_no_sender_types_a_number_the_debugger_would_look_up_as_a_name(
        tmp_path: Path, sender: str, value: int, monkeypatch: pytest.MonkeyPatch) -> None:
    typed = _typed_by(sender, value, tmp_path, monkeypatch)
    assert typed, "the sender stopped before it typed its command"
    assert not shadowed(typed[0]), typed[0]


@pytest.mark.parametrize("sender", SENDERS)
def test_every_row_goes_red_when_the_spelling_is_taken_away(
        tmp_path: Path, sender: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Were a row to stop short of the spelling, it would stay green with the spelling gone."""
    monkeypatch.setattr(dbg, "typed_hex", lambda value, width=0: f"{value:0{width}X}")
    typed = _typed_by(sender, 0xAF, tmp_path, monkeypatch)
    assert shadowed(typed[0]), typed[0]


def test_the_oracle_sees_a_name_in_the_commands_it_was_meant_to_see() -> None:
    assert shadowed("MEMDUMPBIN 0820:5AFE AF MCPDUMP.BIN") == ["AF"]
    assert shadowed("MEMS >FA") == ["FA"]
    assert shadowed("MEMFIND 0000:0 10 B") == []
