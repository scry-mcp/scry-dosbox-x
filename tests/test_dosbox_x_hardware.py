"""`port`, `pic` and `a20` against the debugger's captured answers (`tests/fixtures/hardware`)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import FakeSession, install
from scry_core.reply_contract import Invalid

import dosbox_hardware as hardware
import dosbox_state as dstate
import dosbox_x_server as server

FIX = Path(__file__).resolve().parent / "fixtures" / "hardware"
PORTINFO = {int(line.split()[2], 16): line
            for line in (FIX / "portinfo.txt").read_text().splitlines()}
PIC_LISTING = (FIX / "pic-irq0-masked.txt").read_text().rstrip("\n").splitlines()


class Machine(FakeSession):
    """A stopped machine answering each command as the debugger did: `PORTINFO` by port, `PIC`
    from the captured listing with the masks this run set, `A20` from a gate it holds."""

    def __init__(self, reads: dict[str, str] | None = None, a20_sticks: bool = True) -> None:
        super().__init__()
        self.reads = reads or {}
        self.pic_rows = list(PIC_LISTING)
        self.gate, self.a20_sticks = False, a20_sticks

    def at_debugger(self) -> bool:
        return True

    def _row(self, irq: int, masked: bool) -> None:
        at = next(i for i, line in enumerate(self.pic_rows)
                  if line.startswith(f"{irq:3d} 0x"))
        line = self.pic_rows[at]
        self.pic_rows[at] = line[:16] + ("M" if masked else " ") + line[17:]

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        self.executed.append(command)
        words = command.split()
        if words[0] == "PORTINFO":
            return True, [PORTINFO[int(words[1], 16)]]
        if words[0] in ("INP", "INW", "IND"):
            return True, [f"Result: {self.reads.get(command, 'ff')}"]
        if words[0].startswith("OUT"):
            return True, []
        if command == "PIC":
            return True, list(self.pic_rows)
        if words[0] == "PIC":
            if words[1] in ("MASKIRQ", "UNMASKIRQ"):
                self._row(int(words[2]), words[1] == "MASKIRQ")
            return True, []
        if command == "A20":
            return True, [f"A20 gate is {'ON' if self.gate else 'OFF'}"]
        if words[0] == "A20":
            self.gate = (words[1] == "ON") if self.a20_sticks else self.gate
            return True, []
        return False, ["*** Debugger command not recognized"]


def _call(fn: Callable[..., Any], **kw: Any) -> dict[str, Any]:
    return cast(dict[str, Any], fn(**kw))


def _on(machine: Machine) -> Machine:
    fake = install()
    machine.altered = False
    dstate.STATE.session = machine  # type: ignore[assignment]
    del fake
    return machine


def test_a_port_read_answers_the_value_and_marks_the_session_altered() -> None:
    m = _on(Machine({"INP 3DA": "4"}))
    got = _call(server.port, method="read", port=0x3DA)
    assert got["status"] == "ok" and got["value"] == "0x04" and got["port"] == "0x03DA", got
    assert m.altered is True and m.executed == ["PORTINFO 3DA", "INP 3DA"], m.executed


@pytest.mark.parametrize(("port", "bits", "write"), [(0x2E8, 8, False), (0x3DA, 16, False),
                                                       (0x3DA, 8, True), (0x21, 32, True)])
def test_an_access_no_device_answers_is_refused_before_it_is_made(port: int, bits: int,
                                                                  write: bool) -> None:
    m = _on(Machine())
    kw = {"method": "write", "value": 0} if write else {"method": "read"}
    got = _call(server.port, port=port, bits=bits, **kw)
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert "no device" in got["message"] and m.executed == [f"PORTINFO {port:X}"], m.executed
    assert m.altered is False


def test_a_write_says_a_port_has_nothing_to_read_back() -> None:
    m = _on(Machine())
    got = _call(server.port, method="write", port=0x3C8, value="0x15", bits=16)
    assert got["status"] == "ok" and got["value"] == "0x0015", got
    assert got["readback"]["available"] is False and m.executed[-1] == "OUTW 3C8 15", m.executed


@pytest.mark.parametrize(("kw", "said"), [
    ({"port": 0x10000}, "0xFFFF"), ({"port": 0xFFFF, "bits": 16}, "reaches past"),
    ({"port": 0x21, "bits": 12}, "bits"), ({"port": 0x21, "value": 0x100, "method": "write"},
                                            "does not fit"),
    ({"method": "write", "port": 0x21}, "value is required"), ({"port": "0x1g"}, "port")])
def test_a_port_value_or_size_out_of_range_is_refused_unsent(kw: dict[str, Any],
                                                              said: str) -> None:
    m = _on(Machine())
    got = _call(server.port, **{"method": "read", **kw})
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert said in got["message"] and m.executed == [], (got, m.executed)


def test_a_build_without_portinfo_is_refused_by_name() -> None:
    m = _on(Machine())
    m.commands = frozenset()
    got = _call(server.port, method="read", port=0x21)
    assert got["code"] == "no_channel" and "`PORTINFO`" in got["message"], got
    assert m.executed == []


def test_the_listing_is_read_into_both_controllers_and_sixteen_lines() -> None:
    read = hardware.parse_pic(PIC_LISTING)
    assert [c["controller"] for c in read["controllers"]] == ["master", "slave"]
    assert read["controllers"][1]["vector_base"] == "0x70"
    # `pic.cpp` writes 8 when its in-service register is empty: no line, never a ninth one, and
    # no reply carries a null.
    assert all(c["active_irq"]["available"] is False for c in read["controllers"]), read
    by = {r["irq"]: r for r in read["irqs"]}
    assert len(by) == 16 and by[0]["requested"] and by[0]["masked"] and by[2]["cascade"]
    assert [i for i, r in by.items() if r["masked"]] == [0, 3, 5, 6, 7, 10, 11]


@pytest.mark.parametrize("cut", [slice(0, 5), slice(0, 13)])
def test_a_listing_that_is_not_the_controllers_is_refused(cut: slice) -> None:
    with pytest.raises(Invalid) as e:
        hardware.parse_pic(PIC_LISTING[cut])
    assert e.value.code == "unexpected_answer"


def test_a_mask_is_read_back_and_marks_the_session_altered() -> None:
    m = _on(Machine())
    got = _call(server.pic, method="unmask", irq=3)
    assert got["status"] == "ok" and got["line"]["masked"] is False and m.altered, got
    assert "PIC UNMASKIRQ 3" in m.executed


def test_a_mask_the_listing_does_not_show_is_refused() -> None:
    m = _on(Machine())
    m._row = lambda irq, masked: None  # type: ignore[method-assign]
    got = _call(server.pic, method="unmask", irq=3)
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got


def test_an_irq_past_fifteen_is_refused_unsent_though_the_debugger_takes_it() -> None:
    m = _on(Machine())
    got = _call(server.pic, method="mask", irq=99)
    assert got["code"] == "bad_argument" and m.executed == [], got


def test_the_a20_gate_set_is_read_back() -> None:
    _on(Machine())
    assert _call(server.a20, method="on")["enabled"] is True
    assert _call(server.a20, method="read")["enabled"] is True
    _on(Machine(a20_sticks=False))
    got = _call(server.a20, method="on")
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
