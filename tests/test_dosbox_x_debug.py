"""Contract tests of the debug interface: `step`, `run_to` and `watch`, with `e9_wait`.

None launches DOSBox-X. The doubles stand in for the debugger's side of the conversation and
the real methods run against them. The screens and breakpoint list rows are captured from a
live debugger, because a row authored from the code's own belief hid a live bug: the code
expected `BPPMEM 00AF:6024` and the debugger prints `BPPM 00AF:00006024`.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import fold_calls
import pytest
from dosbox_x_server_support import returned_key_sets
from scry_core import log_wait as core_wait
from scry_core import progress as mprogress
from scry_core import vocabulary as vocab

import dosbox_console as dcons
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

# The RESET screen at `F000:FFF0`, trimmed to what is read: the `Real` token at the end of
# the `SS=` line, the pane headers as runs of `o`, and the Output tail.
REAL_PANE = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
    "EAX=00000000  ESI=00000000  DS=0000   ES=0000   FS=0000   GS=0000   SS=0000 Real\r\n"
    "EBX=00000000  EDI=00000000  CS=F000   EIP=0000FFF0  C0 Z0 S0 O0 A0 P0 D0 I0 T0\r\n"
    "ECX=00000000  EBP=00000000NOPG  IOPL0  CPL0\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "***| TYPE HELP (+ENTER) TO GET AN OVERVIEW OF ALL COMMANDS |***\r\n"
    "Breakpoint list:\r\n"
    "-------------------------------------------------------------------------\r\n"
    "I-> _")

# Two `Breakpoint list:` headers: the first repaints the earlier empty listing, the second
# answers the command just sent. The `rfind` design rests on this.
REAL_PANE_TWO_BPS = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
    "EAX=00000000  ESI=00000000  DS=0000   ES=0000   FS=0000   GS=0000   SS=0000 Real\r\n"
    "EBX=00000000  EDI=00000000  CS=F000   EIP=0000FFF0  C0 Z0 S0 O0 A0 P0 D0 I0 T0\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "Breakpoint list:\r\n"
    "-------------------------------------------------------------------------\r\n"
    "DEBUG: Set breakpoint at F000:E05B\r\n"
    "DEBUG: Set memory breakpoint at 0040:006C\r\n"
    "Breakpoint list:\r\n"
    "-------------------------------------------------------------------------\r\n"
    "00. BPMEM 0040:006C (00)\r\n"
    "01. BP F000:E05B\r\n"
    "I-> _")

# DJGPP under CWSDPMI, 32-bit protected mode: `Pr32` makes `watch` send `BPPM`.
PROT_PANE = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
    "EAX=0000000A  ESI=00400000  DS=00AF   ES=00AF   FS=008F   GS=0000   SS=008F Pr32\r\n"
    "EBX=000000AF  EDI=00238A00  CS=00A7   EIP=00001A27  C0 Z1 S0 O0 A0 P1 D0 I1 T0\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "Breakpoint list:\r\n"
    "-------------------------------------------------------------------------\r\n"
    "I-> _")


# Captured verbatim and whole from a live debugger: the property is the absence of a marker,
# which a slice can only lose. The delta carries no `Register Overview` banner even on a stop
# (only changed cells repaint), so `PROMPT` is the discriminator.

RESUME_RAN = (
    "\r(Running)monopal: green,\r\nActive save slot: 1 [Empty]\r\nUSING AVI+ZMBV\r\nPentium C"
    "MPXCHG8B emulation is enabled\r\nMax 1073741824 sz 16384\n16384\r\nFinal arrangement: Be"
    "low 4GB = 16384KB, Above 4GB = 0KB\r\nMIDI:Opened device:coreaudio\r\nVOODOO LFB now at "
    "d0000000\n13\r\nSerial2: BASE 2f8h\r\nParallel1: BASE 378h\r\nMPU-401 Registering I/O po"
    "rts as if IBM PC MPU-401 at base 330h\r\nMemory I/O complexity optimization enabled aka "
    "option 'memory io optimization 1'. If the game or demo is unable to draw to the sc...The"
    " 'scanline render on demand' option is available and may provide a modest boost in video"
    " render performance if set to true.\r\nAllocated APM BIOS pm entry point at f000:ce404\r"
    "\nWriting code to fce60\r\n***| TYPE HELP (+ENTER) TO GET AN OVERVIEW OF ALL COMMANDS |*"
    "**\r\nISA Plug & Play BIOS enabled\x1b7\x1b8\r\nVGA ROM BIOS init callback\x1b7\x1b8\r\n"
    "WARNING: No translation support (to host) for code page 0\x1b7\x1b8\r\nDOS keyboard layo"
    "ut loaded with main language code US for layout us\x1b7\x1b8\r\nXMS: 50 handles allocate"
    "d for use by the DOS environment\x1b7\x1b8\r\nEMS page frame at 0xe000-0xefff\x1b7\x1b8"
    "\r\nCOMMAND.COM env size:720 bytes\x1b7\x1b8\r\nCOMMAND.COM environment block:    0x0701"
    " sz=0x002d\x1b7\x1b8\r\nCOMMAND.COM main body (PSP):0x072f sz=0x009a\x1b7\x1b8\r\nCOMMAN"
    "D.COM stack:0x0749\x1b7\x1b8\r\npixratio 1.350, dw false, dh false\x1b7\x1b8\r\nAspect r"
    "atio: 720 x 540  xToY=1.333 yToX=0.750\x1b7\x1b8\r\nsurface consider=720x400 final=720x4"
    "00"
)

RESUME_HALTED = (
    '\r(Running)\r\n\n0814:00000108 CD21int  21\r\n\n\n\n0814:00000112 CD21int  21\rI-> _C121'
    '1944\n7947'
)

RESUME_HALTED_GLUED = (
    '\r(Running)\r\n\n0814:00000108\r\n0814:0000010A 30C0    xor  al,al\r\n0814:0000010C FE38'
    '0600callback 0006  (internal program)\r\n0814:00000110 B44C    mov  ah,4C\r\n0814:000001'
    '12 CD211\r\n0814:00000114 050000  add  ax,0000\r\n0814:00000117 0000add  [bx+si],alds:[0'
    '140]=0000\r\n0814:00000119 0000    add  [bx+si],al      ds:[0140]=0000\r\n0814:0000011B '
    '0000add  [bx+si],alds:[0140]=0000\r\n0814:0000011D 0000    add  [bx+si],al      ds:[0140'
    ']=0000\r\n0814:0000011F 0000add  [bx+si],alds:[0140]=0000\rI-> _A1814814814040FFFE  CS=0'
    '81401080100FF91C81440026\n7328'
)
# The third is adversarial: `parse_registers` answers `CS=081401080100FF91C81440026`, the
# digits of several fields glued into a value no register held.


# The four list rows, verbatim off `BPLIST`; the memory spellings are not uniform:
#
#   BPM  0040:006C  ->  BPMEM 0040:006C (00)        offset %04X, keyword gains `MEM`
#   BPPM 00AF:6024  ->  BPPM 00AF:00006024 (00)     offset %08X, keyword does NOT
#   BPLM 000B8000   ->  BPLM 000B8000 (00)
BPMEM_ROW = "00. BPMEM 0040:006C (00)"
BPPM_ROW = "00. BPPM 00AF:00006024 (00)"
BP_ROW = "01. BP F000:E05B"


def pane_with(rows: list[str], *, mode: str = "Real", cs: str = "F000",
              eip: str = "0000FFF0") -> str:
    """A repaint with a given breakpoint listing, derived from the captured shape."""
    return (
        "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
        f"EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 {mode}\r\n"
        f"EBX=00000000  EDI=00000000  CS={cs}   EIP={eip}  C0 Z0 S0 O0\r\n"
        "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
        f"{dcons.BPLIST_HEADER}\r\n"
        "-------------------------------------------------------------------------\r\n"
        + "".join(f"{r}\r\n" for r in rows) + "I-> _")



class RealPositionReaders:
    """The three position readers, delegated to the real methods."""

    def _survey(self) -> tuple[str, dict[str, str]]:
        return ds.Session._survey(cast(ds.Session, self))

    def where(self) -> dict[str, str]:
        return ds.Session.where(cast(ds.Session, self))

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return ds.Session.where_and_registers(cast(ds.Session, self))

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        return ds.Session.stop_survey(cast(ds.Session, self))

    def read_memory(self, seg: int, off: int, mode: str | None = None) -> list[str]:
        return ds.Session.read_memory(cast(ds.Session, self), seg, off, mode)

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        return ds.Session.read_bytes(cast(ds.Session, self), seg, off, n, mode)

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        # Stopped unless a position read found no pane behind a heard prompt (the real `where`
        # clears the flag then).
        return self._at_debugger

    _at_debugger = True
    stop_count = 1

    def _mark_stopped(self) -> None:
        self._at_debugger = True


class Debugger(RealPositionReaders):
    """The debugger's side of the conversation, answered from a queue, so it is order-sensitive."""

    def __init__(self, panes: list[str], *, alive: bool = True,
                 reads: list[str] | None = None,
                 deltas: list[str] | None = None) -> None:
        self.panes = list(panes)
        self.reads = list(reads or [])
        # What `_collect` hands back: a separate queue from `panes`, since a stopping resume
        # consumes one of each.
        self.deltas = list(deltas or [])
        self.sent: list[str] = []
        self.keys: list[bytes] = []
        self._alive = alive
        self.altered = False
        # No instrumentation channel: the real session refuses a logfile-less one and the stop
        # reply reads that as no log.
        self.launch = SimpleNamespace(logfile=None, watched=True)

    def command(self, text: str, **_: object) -> str:
        self.sent.append(text)
        if text == ds.NUDGE:
            return self.panes.pop(0) if self.panes else ""
        return ""

    def _write(self, data: bytes) -> None:
        # The real release hook: a run key drains one `reads` entry.
        ds.Session._release(cast(ds.Session, self), data)
        self.keys.append(data)

    def _collect(self, settle: float = 0.0, timeout: float = 0.0,
                 early: bool = False) -> str:
        return self.deltas.pop(0) if self.deltas else ""

    def clear_line(self) -> str:
        self._write(dcons.CLEAR_LINE_KEY)
        return ""

    def _read(self, seconds: float = 0.0) -> str:
        return self.reads.pop(0) if self.reads else ""

    def alive(self) -> bool:
        return self._alive

    def break_in(self, seconds: float = ds.BREAK_IN_WAIT_S) -> float:
        self.sent.append("BREAK")
        self._at_debugger = True
        return 0.1

    def resume(self) -> dict[str, object]:
        return ds.Session.resume(cast(ds.Session, self))

    def breakpoints(self) -> list[dict[str, str]]:
        return ds.Session.breakpoints(cast(ds.Session, self))

    def registers(self) -> dict[str, str]:
        return ds.Session.registers(cast(ds.Session, self))

    def e9(self, pattern: str, limit: int) -> tuple[list[str], int]:
        return ds.Session.e9(cast(ds.Session, self), pattern, limit)

    def _e9_text(self) -> str:
        return ds.Session._e9_text(cast(ds.Session, self))

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ds.Session.e9_new_since(cast(ds.Session, self), offset)

    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        return ds.Session.step(cast(ds.Session, self), mode=mode, count=count)

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.run_to(cast(ds.Session, self), seg, off, seconds, control, progress)

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        return ds.Session.watch(cast(ds.Session, self), segment=segment, offset=offset)

    def state(self) -> dict[str, object]:
        return {"alive": self._alive, "running": False, "altered": self.altered}


def step(dbg: Debugger, **kw: Any) -> dict[str, object]:
    return ds.Session.step(cast(ds.Session, dbg), **kw)


def run_to(dbg: Debugger, seg: int, off: int, seconds: float = 0.05,
           control: tuple[int, int] | None = None,
           progress: ds.Progress = ds.no_progress) -> dict[str, object]:
    return ds.Session.run_to(cast(ds.Session, dbg), seg, off, seconds, control, progress)


def watch(dbg: Debugger, **kw: Any) -> dict[str, object]:
    return ds.Session.watch(cast(ds.Session, dbg), **kw)


def where(dbg: Debugger) -> dict[str, str]:
    return ds.Session.where(cast(ds.Session, dbg))


def resume(dbg: Debugger) -> dict[str, object]:
    return ds.Session.resume(cast(ds.Session, dbg))


def breakpoints(dbg: Debugger) -> list[dict[str, str]]:
    return ds.Session.breakpoints(cast(ds.Session, dbg))



def test_the_mode_is_read_as_a_token_and_not_as_the_absence_of_another() -> None:
    """Named tokens, so an absent `Pr` is not read as real mode."""
    assert dcons.parse_mode(REAL_PANE) == "Real"
    assert dcons.parse_mode(PROT_PANE) == "Pr32"
    assert dcons.parse_mode("SS=008F Pr16\r\n") == "Pr16"


def test_a_screen_that_names_no_mode_is_not_a_mode() -> None:
    assert dcons.parse_mode("") is None
    assert dcons.parse_mode("EAX=00000000  EIP=0000FFF0\r\n") is None


def test_the_mode_is_the_last_one_because_the_pane_scrolls() -> None:
    """A delta can hold an earlier repaint above the current one."""
    assert dcons.parse_mode(REAL_PANE + PROT_PANE) == "Pr32"


def test_the_breakpoint_list_is_read_from_the_last_listing_in_the_delta() -> None:
    """`find` would pass here too; the case below pins `rfind`."""
    got = breakpoints(Debugger([REAL_PANE_TWO_BPS]))
    assert [b["entry"] for b in got] == ["BPMEM 0040:006C (00)", "BP F000:E05B"]
    assert [b["index"] for b in got] == ["00", "01"]


def test_a_deleted_breakpoint_does_not_come_back_from_an_earlier_repaint() -> None:
    """The populated listing comes first and an empty one follows it."""
    after_delete = (
        "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
        f"{dcons.BPLIST_HEADER}\r\n"
        "-------------------------------------------------------------------------\r\n"
        "00. BP 0814:010A\r\n"
        "DEBUG: Breakpoints deleted.\r\n"
        "EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 Real\r\n"
        "EBX=00000000  EDI=00000000  CS=0814   EIP=0000010A  C0 Z0 S0 O0\r\n"
        f"{dcons.BPLIST_HEADER}\r\n"
        "-------------------------------------------------------------------------\r\n"
        "I-> _")
    assert breakpoints(Debugger([after_delete])) == []


def test_an_empty_listing_is_an_answer_and_a_missing_one_is_not() -> None:
    """An empty listing says nothing is armed; a missing one says nothing was read."""
    assert breakpoints(Debugger([REAL_PANE])) == []
    with pytest.raises(ds.Invalid, match="printed no"):
        breakpoints(Debugger([pane_with([]).replace(dcons.BPLIST_HEADER, "")]))



def test_where_answers_with_the_address_and_the_mode_it_is_in() -> None:
    assert where(Debugger([PROT_PANE])) == {"cs": "00A7", "eip": "00001A27",
                                            "mode": "Pr32"}


def test_where_refuses_when_the_machine_is_not_stopped() -> None:
    with pytest.raises(ds.Invalid, match="stopped at the debugger"):
        where(Debugger([""]))


def test_where_refuses_a_pane_that_repainted_but_named_no_mode() -> None:
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        where(Debugger(["EAX=00000000  CS=F000   EIP=0000FFF0\r\n"]))



def test_step_sends_f10_for_over_and_f11_for_into() -> None:
    over = Debugger([REAL_PANE, REAL_PANE])
    step(over, mode="over", count=1)
    assert over.keys == [b"\x1b[21~"]

    into = Debugger([REAL_PANE, REAL_PANE])
    step(into, mode="into", count=1)
    assert into.keys == [b"\x1b[23~"]


def test_step_reports_what_happened_and_not_what_was_asked_for() -> None:
    """A step over a call that never returns leaves the machine running."""
    dbg = Debugger([REAL_PANE, REAL_PANE, REAL_PANE])
    got = step(dbg, mode="over", count=4)
    assert got["asked"] == 4
    assert got["completed"] == 2
    assert got["running"] is True
    assert len(dbg.keys) == 3


def test_a_dead_emulator_is_a_refusal_and_not_a_partial_result() -> None:
    dbg = Debugger([REAL_PANE], alive=False)
    with pytest.raises(ds.Invalid):
        step(dbg, mode="over", count=3)


def test_step_refuses_a_mode_it_does_not_have_and_a_count_it_cannot_afford() -> None:
    dbg = Debugger([REAL_PANE] * 4)
    with pytest.raises(ds.Invalid, match="mode is one of"):
        step(dbg, mode="sideways", count=1)
    with pytest.raises(ds.Invalid, match="step count"):
        step(dbg, mode="over", count=0)
    # A literal, not `ds.STEP_MAX + 1`: derived, the probe would move with a ceiling raised
    # until it bounds nothing.
    assert ds.STEP_MAX == 64, "the ceiling moved; decide it deliberately and edit here"
    with pytest.raises(ds.Invalid, match="step count"):
        step(dbg, mode="over", count=65)
    assert dbg.keys == []


def test_step_refuses_before_touching_a_machine_that_is_not_stopped() -> None:
    dbg = Debugger([""])
    with pytest.raises(ds.Invalid, match="a step is a KEYSTROKE"):
        step(dbg, mode="over", count=1)
    assert dbg.keys == []



ARRIVED = "0000FFF0"


def test_run_to_arrives_and_removes_the_breakpoint_it_created() -> None:
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]),
                    armed,
                    pane_with([], cs="F000", eip=ARRIVED),
                    armed,
                    pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TARGET"
    assert got["breakpoint_removed"] is True
    assert got["note"] == ""
    assert "BP F000:FFF0" in dbg.sent and "BPDEL 00" in dbg.sent


def test_run_to_in_real_mode_arrives_at_an_aliased_seg_off() -> None:
    """Many SEG:OFF pairs name one real-mode byte, so arrival compares linear addresses."""
    armed = pane_with(["00. BP 1000:0810"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="1080", eip="00000010"),
                    armed, pane_with([])])
    got = run_to(dbg, 0x1000, 0x0810)
    assert got["verdict"] == "TARGET", got
    assert got["breakpoint_removed"] is True, got
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="1080", eip="00000011"), armed, pane_with([])])
    got = run_to(dbg, 0x1000, 0x0810)
    assert got["verdict"] == "OTHER_STOP" and got["breakpoint_removed"] is True, got


def test_run_to_looks_the_index_up_again_rather_than_reusing_it() -> None:
    """`BPDEL` renumbers what is left."""
    dbg = Debugger([pane_with(["00. BPMEM 0040:006C (00)"]),
                    pane_with(["00. BPMEM 0040:006C (00)", "01. BP F000:FFF0"]),
                    pane_with([], cs="F000", eip=ARRIVED),
                    pane_with(["00. BP F000:FFF0"]),
                    pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["breakpoint_removed"] is True
    assert "BPDEL 00" in dbg.sent, dbg.sent
    assert "BPDEL 01" not in dbg.sent


def test_it_was_never_armed_is_refused_rather_than_reported_as_never_arrived() -> None:
    """The acknowledgement goes into a scrolling pane, so it cannot prove the arming."""
    dbg = Debugger([pane_with([]), pane_with([])])
    with pytest.raises(ds.Invalid, match="does not list a breakpoint"):
        run_to(dbg, 0xF000, 0xFFF0)
    assert dbg.keys == []


def test_stopping_somewhere_else_is_not_an_arrival() -> None:
    dbg = Debugger([pane_with([]),
                    pane_with(["00. BP F000:FFF0"]),
                    pane_with([], cs="F000", eip="0000E05B"),
                    pane_with(["00. BP F000:FFF0"]), pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "OTHER_STOP"
    assert got["breakpoint_removed"] is True
    assert "0000E05B" in str(got["note"]) and "was removed" in str(got["note"]), got["note"]
    assert "BPDEL 00" in dbg.sent, dbg.sent


def test_a_bound_that_expires_interrupts_the_run_and_disarms_the_target() -> None:
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), "",
                    pane_with([], cs="0837", eip="0000004C"),
                    pane_with(["00. BP F000:FFF0"]), pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TIMEOUT", got
    assert "BREAK" in dbg.sent, dbg.sent
    assert got["stopped_at"] == {"cs": "0837", "eip": "0000004C", "mode": "Real"}, got
    assert got["breakpoint_removed"] is True
    assert "interrupted" in str(got["note"]) and "was removed" in str(got["note"]), got


CONTROL_HIT = "0000E05B"


def test_run_to_with_a_control_counts_its_hits_and_releases_the_machine_again() -> None:
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    prompt = dcons.PROMPT + " _"
    dbg = Debugger([pane_with([]),
                    both,
                    pane_with([], cs="F000", eip=CONTROL_HIT),
                    pane_with([], cs="F000", eip=CONTROL_HIT),
                    pane_with([], cs="F000", eip=ARRIVED),
                    both, control_only,
                    control_only, pane_with([])],
                   # each release eats one read (the drain), then the wait hears the prompt
                   reads=["", prompt, "", prompt, "", prompt])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TARGET", got
    assert got["control"] == {"at": "F000:E05B", "hits": 2, "removed": True}, got
    assert got["breakpoint_removed"] is True
    assert dbg.keys.count(ds.RUN_KEY) == 3, "released once per control hit, plus the first"
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent


def test_run_to_with_a_control_that_never_fires_reports_zero_hits_and_neither_armed() -> None:
    """The session reports `hits: 0` and the server turns it into INVALID."""
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both, "", pane_with([], cs="0837", eip="0000004C"),
                    both, control_only, control_only, pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT", got
    assert got["control"] == {"at": "F000:E05B", "hits": 0, "removed": True}, got
    assert got["breakpoint_removed"] is True, got
    assert "F000:FFF0 was removed" in str(got["note"]), got["note"]


def test_run_to_whose_control_eats_the_whole_bound_is_a_timeout(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The clock ticks one second per call, so the deadline passes between the stop and the read."""
    import itertools
    import time
    tick = itertools.count(0.0, 1.0)
    monkeypatch.setattr(time, "monotonic", lambda: next(tick))
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both,
                    pane_with([], cs="F000", eip=CONTROL_HIT),
                    both, control_only,
                    control_only, pane_with([])],
                   reads=["", dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=2.5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT", got
    assert "BREAK" not in dbg.sent, "at rest on the control: nothing to interrupt"
    assert got["control"] == {"at": "F000:E05B", "hits": 1, "removed": True}, got
    assert dbg.sent.count("BPDEL 00") == 2 and dbg.keys.count(ds.RUN_KEY) == 1, dbg.sent
    assert got["breakpoint_removed"] is True, got
    assert "ON the control F000:E05B (its hit number 1)" in str(got["note"]), got["note"]
    assert "something else" not in str(got["note"]), "a rest on the control is not a stranger"


def test_run_to_refuses_a_control_the_debugger_did_not_arm() -> None:
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"])])
    with pytest.raises(ds.Invalid, match="F000:E05B"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xE05B))
    assert dbg.keys == []


def test_run_to_reports_a_control_it_could_not_remove_beside_a_sound_arrival() -> None:
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both,
                    pane_with([], cs="F000", eip=ARRIVED),
                    both, control_only,
                    control_only, control_only],
                   reads=["", dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TARGET" and got["breakpoint_removed"] is True, got
    assert got["control"] == {"at": "F000:E05B", "hits": 0, "removed": False}, got
    assert "F000:E05B is STILL in the" in str(got["note"]), got["note"]


def test_run_to_without_a_control_says_so_with_one_key_and_not_by_omission() -> None:
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed, pane_with([], cs="F000", eip=ARRIVED), armed,
                    pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["control"] == {"available": False, "why": "no control was named"}, got
    assert got["verdict"] == "TARGET", got


def test_run_to_refuses_a_control_on_the_target_itself() -> None:
    """By place, not spelling: `F000:FFF0` and `FFFF:0000` are one byte."""
    dbg = Debugger([pane_with([])] * 4)
    with pytest.raises(ds.Invalid, match="same address"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xFFF0))
    with pytest.raises(ds.Invalid, match="same address"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xFFFF, 0x0000))
    assert not any(s.startswith("BP ") for s in dbg.sent), "refused before arming anything"
    pr = Debugger([PROT_PANE, pane_with(["00. BP 00A7:0010", "01. BP 00A8:0010"], mode="Pr32"),
                   pane_with([], mode="Pr32", cs="00A7", eip="00000010"),
                   pane_with(["00. BP 00A7:0010", "01. BP 00A8:0010"], mode="Pr32"),
                   pane_with(["00. BP 00A8:0010"], mode="Pr32"),
                   pane_with(["00. BP 00A8:0010"], mode="Pr32"), pane_with([], mode="Pr32")],
                  reads=["", dcons.PROMPT + " _"])
    got = run_to(pr, 0x00A7, 0x0010, seconds=5, control=(0x00A8, 0x0010))
    assert got["verdict"] == "TARGET", got
    assert got["control"] == {"at": "00A8:0010", "hits": 0, "removed": True}, got


def test_a_protected_mode_target_may_be_wider_than_sixteen_bits() -> None:
    """A flat 16-bit clamp refuses real protected-mode offsets; the list prints 4+ hex digits."""
    # Written out, not built with the production format spec: the list prints a minimum of
    # four hex digits.
    wide = "16DF20"
    dbg = Debugger([PROT_PANE,
                    pane_with([f"00. BP 00A7:{wide}"], mode="Pr32"),
                    pane_with([], mode="Pr32", cs="00A7", eip=f"{0x16DF20:08X}"),
                    pane_with([f"00. BP 00A7:{wide}"], mode="Pr32"),
                    pane_with([], mode="Pr32")])
    got = run_to(dbg, 0x00A7, 0x16DF20)
    assert got["verdict"] == "TARGET", got
    assert f"BP 00A7:{wide}" in dbg.sent, dbg.sent


def test_run_to_refuses_an_address_and_a_wait_it_cannot_honour() -> None:
    dbg = Debugger([pane_with([])] * 4)
    with pytest.raises(ds.Invalid, match="segment"):
        run_to(dbg, 0x10000, 0)
    with pytest.raises(ds.Invalid, match="offset"):
        run_to(dbg, 0, 0x10000)
    with pytest.raises(ds.Invalid, match="not a bound"):
        run_to(dbg, 0, 0, seconds=0)
    assert vocab.WAIT_MAX_S == 600, "the ceiling moved; decide it deliberately and edit here"
    with pytest.raises(ds.Invalid, match="not a bound"):
        run_to(dbg, 0, 0, seconds=601)
    assert not any(s.startswith("BP ") for s in dbg.sent), dbg.sent
    assert dbg.keys == []



def test_watch_eats_the_selector_choice_by_reading_the_machines_mode() -> None:
    """The protected row is captured: the debugger prints `BPPM 00AF:00006024`, not `BPPMEM`."""
    real = Debugger([REAL_PANE, pane_with([BPMEM_ROW])])
    got = watch(real, segment=0x0040, offset=0x006C)
    assert got["command"] == "BPM 0040:006C"
    assert got["mode"] == "Real"

    prot = Debugger([PROT_PANE, pane_with([BPPM_ROW], mode="Pr32")])
    got = watch(prot, segment=0x00AF, offset=0x6024)
    assert got["command"] == "BPPM 00AF:6024"
    assert got["armed"] == "BPPM 00AF:00006024", got
    assert got["mode"] == "Pr32"


def test_a_watch_the_debugger_does_not_hold_is_refused() -> None:
    dbg = Debugger([REAL_PANE, pane_with([])])
    with pytest.raises(ds.Invalid, match="does not list a watch"):
        watch(dbg, segment=0x0040, offset=0x006C)


def test_watch_refuses_an_address_outside_what_the_command_can_carry() -> None:
    with pytest.raises(ds.Invalid, match="segment"):
        watch(Debugger([REAL_PANE]), segment=0x10000, offset=0)
    with pytest.raises(ds.Invalid, match="offset"):
        watch(Debugger([REAL_PANE]), segment=0, offset=0x10000)



@pytest.fixture(autouse=True)
def clean_session() -> Any:
    dstate.STATE.session = None
    dstate.STATE.clear_running_state()
    yield
    dstate.STATE.session = None
    dstate.STATE.clear_running_state()


@pytest.mark.parametrize("call", [
    pytest.param(lambda: server.step(mode="over"), id="step"),
    pytest.param(lambda: server.run_to(ref="0000:0000", control="0000:0020"), id="run_to"),
    pytest.param(lambda: server.log_wait(channel="guest", pattern="x", seconds=1), id="log_wait"),
])
def test_each_tool_refuses_with_no_session_and_still_carries_the_envelope(
        call: Any) -> None:
    reply = cast(dict[str, Any], call())
    assert reply["status"] == "INVALID"
    assert "no live session" in reply["message"]
    assert reply["session"] == {"alive": False, "running": False, "altered": False}


# Derived from the method, not listed: a hand-written dict fell behind when `step` and
# `run_to` gained fields, and this is the only check that the envelope drops nothing.
# `step` names the session's count in the shared word; the rest of its account is handed on.
TOOL_FIELDS = {"step": set(returned_key_sets(ds.Session.step)[0]) - {"completed", "running"}
               | {"instructions_completed"},
               "log_wait": next(set(keys) for keys in returned_key_sets(ds.Session.log_wait)
                                if "line" in keys)}
# `run_to` speaks the shared words, so its account is mapped and not handed on.
TOOL_FIELDS["run_to"] = {"verdict", "target", "ref", "pc", "cpu_mode",
                         "target_disarmed", "control_hits", "controls"}


@pytest.mark.parametrize("tool", sorted(TOOL_FIELDS))
def test_the_tools_hand_the_sessions_own_answer_back_whole(
        tool: str, tmp_path: Path) -> None:
    """Parametrised over all three, so a tool wrapped to return only the envelope goes red."""
    # step and run_to stop, so their reply is the enriched one: ONE survey (`stop_survey`)
    # needs one more pane, and a regression to two surveys starves the second pop.
    enrich = [pane_with([], cs="F000", eip="0000FFF0")]
    # The first contact records the park: every tool's `live()` surveys a machine found at the
    # debugger once, so the console tools pay one pane before their own reads.
    park = [pane_with([])]
    panes = {"step": [*park, REAL_PANE, REAL_PANE, *enrich],
             "run_to": [*park, pane_with([]),
                        pane_with(["00. BP F000:FFF0", "01. BP F000:FFE0"]),
                        pane_with([], cs="F000", eip="0000FFF0"),
                        pane_with(["00. BP F000:FFF0", "01. BP F000:FFE0"]), pane_with([]),
                        pane_with(["00. BP F000:FFE0"]), pane_with([]), *enrich],
             "log_wait": []}[tool]
    args: dict[str, Any] = cast(dict[str, Any], {"step": {"mode": "over", "count": 1},
                            # A short bound: the double's `_read` never yields,
                            # so the wait runs to the deadline.
                            "run_to": {"ref": "F000:FFF0", "control": "F000:FFE0",
                                       "seconds": 0.05},
                            "log_wait": {"pattern": "x", "channel": "guest", "seconds": 1}}[tool])
    if tool == "log_wait":
        log = tmp_path / "guest.log"
        log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
        dstate.STATE.session = cast(ds.Session, LogSession(log))
        args["pattern"] = "start version"
    else:
        dstate.STATE.session = cast(ds.Session, Debugger(panes))
    reply = cast(dict[str, Any], fold_calls.of(server, tool)(**args))
    assert reply["status"] == "ok", reply
    missing = TOOL_FIELDS[tool] - set(reply)
    assert not missing, f"{tool} dropped {sorted(missing)} on the way through _answer"


def test_where_and_registers_surveys_once_and_matches_the_two_calls() -> None:
    """Pins the console round-trip count, which a two-survey regression leaves with right values."""
    pane = pane_with(["00. BP F000:FFF0"], cs="F000", eip="0000FFF0")
    folded = Debugger([pane])
    where, regs = ds.Session.where_and_registers(cast(ds.Session, folded))
    assert folded.sent.count(ds.NUDGE) == 1, folded.sent

    two = Debugger([pane, pane])
    old_where = ds.Session.where(cast(ds.Session, two))
    old_regs = ds.Session.registers(cast(ds.Session, two))
    assert two.sent.count(ds.NUDGE) == 2, two.sent
    assert where == old_where and regs == old_regs


def test_where_and_registers_refuses_a_cut_pane_like_where_does() -> None:
    no_mode = "ooooRegister OverviewooooEAX=00000001  ESI=00000000\r\nI-> _"
    with pytest.raises(ds.Invalid, match="no CPU mode"):
        ds.Session.where_and_registers(cast(ds.Session, Debugger([no_mode])))


def test_a_virtual_8086_pane_is_read_as_its_own_mode_with_real_mode_segments() -> None:
    vm86 = REAL_PANE.replace(" Real\r\n", " VM86\r\n")
    assert vm86 != REAL_PANE
    at = ds.Session.where(cast(ds.Session, Debugger([vm86])))
    assert at["mode"] == "VM86", at
    where, regs = ds.Session.where_and_registers(cast(ds.Session, Debugger([vm86])))
    assert where["mode"] == "VM86" and regs, where
    assert dcons.real_segments("VM86") and dcons.real_segments("Real")
    assert not any(dcons.real_segments(m) for m in ("Pr16", "Pr32"))


def test_a_protected_mode_watch_may_be_wider_than_sixteen_bits() -> None:
    dbg = Debugger([PROT_PANE, pane_with(["00. BPPM 00AF:00236024 (00)"], mode="Pr32")])
    got = watch(dbg, segment=0x00AF, offset=0x236024)
    assert got["command"] == "BPPM 00AF:236024", got
    assert got["armed"] == "BPPM 00AF:00236024", got


def test_a_step_that_moves_the_machine_reports_that_it_moved() -> None:
    """Other step cases reuse one pane; `moved` is separate from `completed` on purpose."""
    dbg = Debugger([pane_with([], cs="F000", eip="0000FFF0"),
                    pane_with([], cs="F000", eip="0000E05B")])
    got = step(dbg, mode="over", count=1)
    assert cast(dict[str, str], got["before"])["eip"] == "0000FFF0"
    assert cast(dict[str, str], got["after"])["eip"] == "0000E05B", got
    assert got["moved"] is True and got["completed"] == 1


def test_a_step_that_did_not_move_says_so_instead_of_claiming_success() -> None:
    dbg = Debugger([REAL_PANE, REAL_PANE])
    got = step(dbg, mode="over", count=1)
    assert got["completed"] == 1 and got["moved"] is False


def test_the_mode_token_is_read_off_the_register_pane_and_not_out_of_the_log() -> None:
    """`Real` is an English word and the Output log below the register pane can carry it."""
    noisy = PROT_PANE + "DEBUG: CPU switched to Real mode\r\nI-> _"
    assert dcons.parse_mode(noisy) == "Pr32"
    assert where(Debugger([noisy]))["mode"] == "Pr32"


def test_where_refuses_a_pane_that_carries_no_position() -> None:
    """An empty string is not an address: `int('', 16)` must not escape."""
    partial = ("EAX=00000000  SS=0000 Real\r\n"
               "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    with pytest.raises(ds.Invalid, match="no CS and no EIP"):
        where(Debugger([partial]))


def test_a_partial_pane_is_refused_rather_than_called_a_running_machine() -> None:
    """`where()` refuses for three reasons and only one means running."""
    modeless = ("EAX=00000000  CS=F000   EIP=0000FFF0\r\n"
                "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), modeless])
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        run_to(dbg, 0xF000, 0xFFF0)

    stepper = Debugger([pane_with([]), modeless])
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        step(stepper, mode="over", count=2)


def test_an_arrival_reports_the_time_it_actually_waited() -> None:
    """The bound is large so that echoing it would be unmistakable."""
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="F000", eip="0000FFF0"),
                    armed, pane_with([])],
                   # The first chunk is eaten by the pre-release drain; the second arrives after F5.
                   reads=["", pane_with([], cs="F000", eip="0000FFF0")])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=30)
    assert got["verdict"] == "TARGET", got
    assert cast(float, got["waited_s"]) < 5.0, got


def test_the_right_offset_in_the_wrong_segment_is_not_an_arrival() -> None:
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]),
                    pane_with([], cs="0087", eip="0000FFF0")])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "OTHER_STOP", got
    assert "0087" in str(got["note"]), got


def test_a_breakpoint_that_survives_bpdel_is_reported_as_still_there() -> None:
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="F000", eip="0000FFF0"),
                    armed, armed])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TARGET", got
    assert got["breakpoint_removed"] is False, got
    assert "STILL in the debugger's list" in str(got["note"]), got



# Two instrumentation lines verbatim from a real guest; the third string only quotes one.
E9_BOOT = ("Bochs port E9h: [+   0.000] BOOT  . start version=1.0 gfx=1024x768x8 "
           "rate=44100 buf=2048")
E9_HELP = "Bochs port E9h: [+  19.715] UI    . info_open base=HELP"
E9_QUOTED = "make: src/loudness.c: info_open base=HELP is not an E9 line"


class LogSession:
    """A session that owns a growing logfile and drives the real `e9_wait`."""

    def __init__(self, log: Path, *, alive: bool = True) -> None:
        self.launch = SimpleNamespace(logfile=log, watched=False)
        self._alive = alive

    def alive(self) -> bool:
        return self._alive

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return False

    def state(self) -> dict[str, object]:
        return {"alive": self._alive, "running": False, "altered": False}

    def _e9_text(self) -> str:
        return ds.Session._e9_text(cast(ds.Session, self))

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ds.Session.e9_new_since(cast(ds.Session, self), offset)

    def _log_text(self) -> str:
        return ds.Session._log_text(cast(ds.Session, self))

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        return ds.Session.log(cast(ds.Session, self), pattern, limit, channel, since_mark)

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        return ds.Session._e9_since(cast(ds.Session, self), offset, channel)

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.e9_wait(cast(ds.Session, self), pattern, seconds, mark=mark,
                                  progress=progress)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.log_wait(cast(ds.Session, self), pattern, seconds, channel,
                                   mark=mark, progress=progress)

    def e9_mark(self) -> int:
        return ds.Session.e9_mark(cast(ds.Session, self))


def test_a_wait_from_a_mark_does_not_answer_with_what_was_written_before_it(
        tmp_path: Path) -> None:
    """The control: the same wait from mark 0 finds the line at once."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    assert mark == log.stat().st_size
    # With a mark the count names the region since the mark, not the whole log.
    expired = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert expired["verdict"] == "TIMEOUT", expired
    assert re.search(r"0 since the mark at byte \d+", str(expired["note"])), expired
    assert "altogether" not in str(expired["note"])
    assert s.e9_wait("info_open", seconds=0.3)["already"] is True
    later = "Bochs port E9h: [+  40.000] UI    . info_open base=ABOUT"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{later}\n")
    got = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert got["line"] == later and got["lines_total"] == 1, got
    assert got["lines_examined"] == 1 and "since_mark" not in got, got
    assert LogSession(tmp_path / "absent.log").e9_mark() == 0


def test_a_mark_inside_a_half_written_line_does_not_serve_that_line_as_new(
        tmp_path: Path) -> None:
    """The mark is the file size, so it can land inside a line begun before it."""
    log = tmp_path / "guest.log"
    half = "Bochs port E9h: [+   1.000] ACT   . key_cue"
    log.write_text(f"{E9_BOOT}\n{half}", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    with log.open("a", encoding="utf-8") as fh:
        fh.write("_a=0 b=-1 on=0\n")
    assert s.e9_wait("key_cue_a", seconds=0.3, mark=mark)["verdict"] == "TIMEOUT"
    whole = "Bochs port E9h: [+   2.000] ACT   . key_cue_a=1 b=-1 on=1"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{whole}\n")
    got = s.e9_wait("key_cue_a", seconds=0.3, mark=mark)
    assert got["line"] == whole and got["lines_total"] == 1, got


def test_a_line_that_already_happened_is_answered_at_once(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["already"] is True
    assert got["line"] == E9_HELP
    assert got["waited_s"] == 0.0, "it waited for something it already had"


def test_the_first_occurrence_is_the_answer_and_the_count_says_there_were_more(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    first = "Bochs port E9h: [+   1.000] UI    . info_open base=HELP"
    log.write_text(f"{first}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == first and got["lines_total"] == 2


def test_a_line_that_arrives_during_the_wait_is_the_other_answer(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    def append_later() -> None:
        time.sleep(0.4)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{E9_HELP}\n")

    writer = threading.Thread(target=append_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["already"] is False, got
    assert got["line"] == E9_HELP
    # Both bounds: a lower one alone is satisfied by echoing the bound asked for.
    assert 0.3 <= cast(float, got["waited_s"]) < 5.0, got
    assert cast(int, got["lines_examined"]) >= 2, got


def test_a_bound_that_expires_is_invalid_and_says_what_it_examined(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("never_going_to_appear", seconds=0.4)
    assert got["verdict"] == "TIMEOUT" and "a bound that expired" in str(got["note"]), got
    assert got["lines_examined"] == 1 and got["arrived_during"] == 0, got


def test_only_a_session_with_no_channel_at_all_is_refused_outright() -> None:
    """A missing log, or one with no instrumentation yet, is normal for a just-resumed guest."""
    with pytest.raises(ds.Invalid, match="without a logfile"):
        LogSession(cast(Path, None)).e9_wait("x", seconds=1)


def test_it_waits_for_the_guests_very_first_trace(tmp_path: Path) -> None:
    log = tmp_path / "not-yet.log"

    def write_later() -> None:
        time.sleep(0.3)
        log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    writer = threading.Thread(target=write_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("start version", seconds=30)
    finally:
        writer.join()
    assert got["already"] is False, got
    assert got["line"] == E9_BOOT


def test_a_line_still_being_written_is_not_reported_and_is_not_lost(
        tmp_path: Path) -> None:
    """A fragment must neither be returned as the trace nor consume a line index."""
    log = tmp_path / "guest.log"
    partial = "Bochs port E9h: [+  19.715] UI    . info_open"
    log.write_text(f"{E9_BOOT}\n{partial}", encoding="utf-8")

    def finish_the_line() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(" base=HELP\n")

    writer = threading.Thread(target=finish_the_line)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["line"] == f"{partial} base=HELP", got
    assert got["already"] is False, got


def test_a_log_rewritten_underneath_the_wait_is_read_from_its_start(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n" * 40, encoding="utf-8")
    fresh = "Bochs port E9h: [+   1.000] UI    . info_open base=FRESH"

    def rewrite_later() -> None:
        time.sleep(0.3)
        log.write_text(f"{fresh}\n", encoding="utf-8")

    writer = threading.Thread(target=rewrite_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=5)
    finally:
        writer.join()
    assert got["verdict"] == "TARGET" and got["line"] == fresh, got


def test_a_session_that_dies_mid_wait_says_so_without_burning_the_bound(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    session = LogSession(log)

    def die_later() -> None:
        time.sleep(0.3)
        session._alive = False

    writer = threading.Thread(target=die_later)
    writer.start()
    began = time.monotonic()
    try:
        with pytest.raises(ds.Invalid, match="GONE"):
            session.e9_wait("never_appears", seconds=30)
    finally:
        writer.join()
    assert time.monotonic() - began < 5.0, "it waited out the bound for a dead session"


def test_the_count_of_what_arrived_during_the_wait_is_not_the_logs_total(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    # Forty-one and the `\b`: `match=` is an unanchored search, and "40 ... arrived DURING"
    # contains the "0 ..." form.
    log.write_text(f"{E9_BOOT}\n" * 41, encoding="utf-8")
    began = time.monotonic()
    got = LogSession(log).e9_wait("never_appears", seconds=0.4)
    assert re.search(r"\b0 lines arrived DURING", str(got["note"])), got
    # The bound is honoured: `deadline = began + seconds * 2` would stay green otherwise.
    assert 0.35 <= time.monotonic() - began < 2.0, "the bound was not the bound"


def test_the_match_count_of_a_waited_answer_is_not_hardcoded(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")

    def burst() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            for i in range(7):
                fh.write(f"Bochs port E9h: [+ {i}.000] UI    . info_open base=HELP\n")

    writer = threading.Thread(target=burst)
    writer.start()
    try:
        got = LogSession(log).e9_wait("info_open", seconds=30)
    finally:
        writer.join()
    assert got["lines_total"] == 7, got
    assert got["arrived_during"] == 7, got


def test_a_line_that_only_quotes_an_e9_trace_is_not_one(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_QUOTED}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == E9_HELP, got


def test_e9_wait_refuses_a_wait_that_is_not_a_bound(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    assert vocab.WAIT_MAX_S == 600, "the ceiling moved; decide it deliberately and edit here"
    for bad in (0, -1, 601):
        with pytest.raises(ds.Invalid, match="not a bound"):
            LogSession(log).e9_wait("x", seconds=bad)


def test_e9_wait_refuses_a_pattern_that_is_not_a_pattern(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="not a usable pattern"):
        LogSession(log).e9_wait("(unclosed", seconds=1)




def test_an_interrupt_breakpoint_is_confirmed_from_the_list_not_from_the_word() -> None:
    """`Breakpoint list:` contains "reakpoint" and every NUDGE paints it. Rows: `BPINT 31 AH=00`."""
    # Header present, list empty: what a text-only check would accept.
    dbg = Debugger([pane_with([])])
    with pytest.raises(ds.Invalid, match="not in the debugger's breakpoint list"):
        ds.Session.breakpoint_interrupt(cast(ds.Session, dbg), 0x31, 0x00)
    # The control: the real row is accepted, in both forms.
    ds.Session.breakpoint_interrupt(
        cast(ds.Session, Debugger([pane_with(["00. BPINT 31 AH=00"])])), 0x31, 0x00)
    ds.Session.breakpoint_interrupt(
        cast(ds.Session, Debugger([pane_with(["00. BPINT 21"])])), 0x21)
    with pytest.raises(ds.Invalid, match="not in the debugger's breakpoint list"):
        ds.Session.breakpoint_interrupt(
            cast(ds.Session, Debugger([pane_with(["00. BPINT 31 AH=05"])])), 0x31, 0x00)


def test_arming_a_breakpoint_marks_the_session_altered() -> None:
    """The debugger arms a breakpoint by writing a trap byte into memory."""
    dbg = Debugger([pane_with(["00. BP F000:FFF0"]), pane_with(["00. BP F000:FFF0"]),
                    pane_with([])])
    # Read into locals: mypy narrows `dbg.altered` and would make later assertions unreachable.
    before = dbg.altered
    run_to(dbg, 0xF000, 0xFFF0)
    assert (before, dbg.altered) == (False, True), "run_to armed and did not say so"

    # Two panes: `watch` reads the mode before arming and the list after; the double is a queue.
    w = Debugger([REAL_PANE, pane_with([BPMEM_ROW])])
    w_before = w.altered
    watch(w, segment=0x0040, offset=0x006C)
    assert (w_before, w.altered) == (False, True), "watch armed and did not say so"


def test_a_breakpoint_row_glued_to_the_text_before_it_is_still_a_row() -> None:
    """Repaints glue content with no newline; an unread row would report a removal."""
    glued = ("ooooOutputoooooooooooooo" + dcons.BPLIST_HEADER + "\r\n"
             "----------------00. BP F000:E05B\r\nI-> _")
    got = dcons.parse_breakpoints(glued)
    assert [b["entry"] for b in got] == ["BP F000:E05B"]
    assert [b["index"] for b in got] == ["00"]
    # The `^` anchor keeps these out: they appear in every real repaint.
    assert dcons.parse_breakpoints("pfi=0.992628993\r\n92.464754300\r\ncc=0RUN\r\n") == []


def test_moved_is_asked_per_step_and_not_of_the_endpoints() -> None:
    """A two-instruction loop returns to its start."""
    dbg = Debugger([pane_with([], eip="0000FFF0"), pane_with([], eip="0000FFF2"),
                    pane_with([], eip="0000FFF0")])
    got = step(dbg, mode="over", count=2)
    assert got["completed"] == 2
    assert got["moved"] is True, "both steps moved; only the endpoints agreed"
    assert got["stalled"] == 0
    idle = Debugger([pane_with([], eip="0000FFF0"), pane_with([], eip="0000FFF0"),
                     pane_with([], eip="0000FFF0")])
    still = step(idle, mode="over", count=2)
    assert still["moved"] is False and still["stalled"] == 2




class Dies(Debugger):
    """Its emulator dies after a given number of `alive()` questions."""

    def __init__(self, panes: list[str], *, dies_after: int) -> None:
        super().__init__(panes)
        self.dies_after = dies_after
        self.alive_calls = 0
        self.polls = 0

    def alive(self) -> bool:
        self.alive_calls += 1
        return self.alive_calls <= self.dies_after

    def _read(self, seconds: float = 0.0) -> str:
        self.polls += 1
        return ""


def test_a_dead_session_is_noticed_in_the_wait_and_not_after_the_whole_bound() -> None:
    # Two panes: `where()` before arming and the list read-back. The session dies part-way:
    # a constant corpse would let hoisting the check out of the loop stay green.
    dbg = Dies([pane_with([]), pane_with(["00. BP F000:E05B"])], dies_after=3)
    with pytest.raises(ds.Invalid, match="the emulator is GONE"):
        run_to(dbg, 0xF000, 0xE05B, seconds=30.0)
    # The read count is the assertion, not the clock: one read is the drain and three the
    # loop's, so five is a ceiling.
    assert dbg.polls <= 5, (
        f"it read {dbg.polls} times on a session that died three questions in; the "
        f"death is meant to be noticed in the loop, not when the bound runs out")
    assert dbg.alive_calls >= 3, (
        f"`alive()` was asked {dbg.alive_calls} times: the check is not in the loop")


def test_an_announced_stop_that_is_not_one_keeps_the_run_going_to_its_bound() -> None:
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "", "",
                    pane_with([], cs="0837", eip="0000004C")],
                   # The first entry is eaten by the drain.
                   reads=["", "EAX=00000001 EIP=0000FFF0\r\n"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.5)
    assert got["verdict"] == "TIMEOUT", got
    assert dbg.keys.count(ds.RUN_KEY) == 1, "released once: the announcement sent nothing"
    assert cast(float, got["waited_s"]) >= 0.5, got


def test_a_stop_announced_only_by_the_prompt_is_seen_by_the_wait() -> None:
    """The register labels are not resent on a stop, so the wait has to read the prompt."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")],
                   # The first read is eaten by the drain; the second is what a stop sends:
                   # a code pane and the prompt, with no register label.
                   reads=["", "0837:004C  CD21  int 21  " + dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=2.0)
    assert got["verdict"] == "OTHER_STOP", got
    assert cast(float, got["waited_s"]) < 1.0, (
        f"waited_s is {got['waited_s']}: the wait sat out its bound over a stop that "
        f"was announced on its first read")
    assert "something else got there first" in str(got["note"]), got["note"]


def test_a_prompt_split_across_two_reads_is_still_heard() -> None:
    """The split falls inside the prompt, the only one that can lose that carry term."""
    noise = "the code pane, redrawn, and nothing that looks like a register label "
    assert len(noise) > dcons.STOP_CARRY, "the fixture must be wider than the carry"
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")],
                   reads=["", noise + dcons.PROMPT[:-1], dcons.PROMPT[-1:] + " _"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=2.0)
    assert got["verdict"] == "OTHER_STOP", got
    assert cast(float, got["waited_s"]) < 1.0, got


def test_a_stop_elsewhere_read_after_the_bound_is_another_stop_not_a_timeout() -> None:
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "OTHER_STOP", got
    assert "BREAK" not in dbg.sent, dbg.sent
    assert "something else got there first" in str(got["note"]), got["note"]


def test_a_bound_that_really_expired_is_a_timeout() -> None:
    """The control beside the case above."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "",
                    pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "TIMEOUT", got
    assert "the 0.05 s bound ran out and the run was interrupted" in str(got["note"])


def test_the_wait_scans_the_new_text_and_not_the_whole_terminal_again() -> None:
    """The assertion is the scanned length, not the clock."""
    chunk = "EAX=00000000 EBX=00000000\r\n" * 20
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "", pane_with([])],
                   reads=[""] + [chunk] * 200)
    seen_lengths: list[int] = []
    real = dcons.parse_registers

    def watched(text: str) -> dict[str, str]:
        seen_lengths.append(len(text))
        return real(text)

    dcons.parse_registers = watched
    try:
        run_to(dbg, 0xF000, 0xE05B, seconds=0.3)
    finally:
        dcons.parse_registers = real
    assert len(seen_lengths) > 3, f"only {len(seen_lengths)} polls: nothing was measured"
    # A prompt-bearing chunk would short-circuit the parse and leave `seen_lengths` empty.
    assert max(seen_lengths) <= len(chunk) + dcons.STOP_CARRY, (
        f"the loop scanned up to {max(seen_lengths)} characters for a "
        f"{len(chunk)}-character read: it is re-reading what it already read")


def test_a_register_split_across_two_reads_is_still_found() -> None:
    """The carry, not a plain scan of the new part, keeps a register cut by the pipe."""
    # The first read is shorter than the carry and the split falls inside `EIP=` itself, the
    # only split that can lose a match and tell a tail carry from a head one.
    noise = "some entirely unremarkable terminal noise that goes on a while "
    assert len(noise) > dcons.EIP_CARRY, "the fixture must be wider than the carry"
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], eip="0000E05B")],
                   reads=["", noise + "EIP=", "0000E05B more\r\n"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=5.0)
    assert got["verdict"] == "TARGET", got
    # `waited_s` discriminates: without the carry the verdict is TARGET anyway, via the pane
    # `where()` pops.
    assert cast(float, got["waited_s"]) < 1.0, got


def test_an_address_is_never_composed_out_of_two_repaints() -> None:
    """`parse_registers` is last-wins per register, so two repaints could compose one."""
    whole = ("ooooRegister Overviewoooo"
             "EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 Pr32\r\n"
             "EBX=00000000  EDI=00000000  CS=0087   EIP=00099999  C0 Z0\r\n")
    cut = "EAX=00000005  EIP=00012345\r\n"
    dbg = Debugger([whole + cut + "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _"])
    with pytest.raises(ds.Invalid, match="carries no CS"):
        where(dbg)
    ok = Debugger([pane_with([], mode="Pr32", cs="0087", eip="00012345")])
    assert where(ok) == {"cs": "0087", "eip": "00012345", "mode": "Pr32"}


def test_the_last_pane_is_the_answer_when_a_delta_carries_two_whole_ones() -> None:
    old = pane_with([], mode="Pr32", cs="0087", eip="00001000")
    new = pane_with([], mode="Pr32", cs="0087", eip="00002000")
    assert dcons.parse_last_pane(old + new)["EIP"] == "00002000"
    assert dcons.parse_last_pane(old)["EIP"] == "00001000"


def test_steps_already_taken_are_named_when_the_position_cannot_be_read() -> None:
    """A step is irreversible, so the refusal carries the steps taken."""
    modeless = ("EAX=00000000  CS=F000   EIP=0000FFF4\r\n"
                "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    dbg = Debugger([pane_with([], eip="0000FFF0"),
                    pane_with([], eip="0000FFF1"),
                    pane_with([], eip="0000FFF2"),
                    modeless])
    with pytest.raises(ds.Invalid) as caught:
        step(dbg, mode="over", count=10)
    said = str(caught.value)
    assert "names no CPU mode" in said, said
    # The count is the keystrokes sent; `completed` would be one fewer and understate the
    # irreversible part.
    assert f"{len(dbg.keys)} `over` keystroke(s) of 10 had ALREADY gone" in said, said
    assert "of which 2 were CONFIRMED landed" in said, said
    assert "F000:0000FFF0" in said, said
    assert len(dbg.keys) == 3, dbg.keys


class DyingLog(LogSession):
    """Writes its exit trace on its way out; `e9_wait` asks `alive()` first and reads last."""

    def __init__(self, log: Path, *, write_after: int, line: str) -> None:
        super().__init__(log)
        self.polls = 0
        self.write_after = write_after
        self.line = line
        self.log_path = log
        self.gone = False

    def alive(self) -> bool:
        return not self.gone

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        # The read answers first, and only then does the guest write and die; otherwise the
        # ordinary match path answers and the death path never runs.
        got = super()._e9_since(offset, channel)
        if self.polls == self.write_after:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            self.gone = True
        return got


def test_the_guests_last_line_is_read_before_a_death_is_reported(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    exit_line = "Bochs port E9h: [+   9.000] PERF  . exit code=0"
    got = DyingLog(log, write_after=2, line=exit_line).e9_wait("exit", seconds=5)
    assert got["line"] == exit_line, got
    assert got["already"] is False


def test_a_death_with_nothing_in_the_log_is_still_a_refusal(tmp_path: Path) -> None:
    """The red beside the case above."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="the emulator is GONE"):
        DyingLog(log, write_after=2, line="nothing to match here").e9_wait(
            "exit", seconds=5)


class LateLog(LogSession):
    """Burns the rest of the bound inside the read, so the expiry path certainly runs."""

    def __init__(self, log: Path, *, line: str, burn: float) -> None:
        super().__init__(log)
        self.polls = 0
        self.line = line
        self.log_path = log
        self.burn = burn
        self.wrote = False

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super()._e9_since(offset, channel)
        if self.polls >= 2 and not self.wrote:
            # Written after this read answered, then the bound is spent.
            self.wrote = True
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            time.sleep(self.burn)
        return got


def test_a_line_written_in_the_tail_of_the_window_is_not_lost_to_the_clock(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    late = "Bochs port E9h: [+   3.000] PERF  . audio play=1"
    sess = LateLog(log, line=late, burn=0.4)
    got = sess.e9_wait("audio", seconds=0.25)
    assert got["line"] == late, got
    assert got["already"] is False


def test_an_expired_bound_with_nothing_matching_is_still_a_refusal(
        tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LateLog(log, line="Bochs port E9h: [+   3.000] UI    . nothing",
                  burn=0.4).e9_wait("audio", seconds=0.25)
    assert got["verdict"] == "TIMEOUT" and "nothing matched" in str(got["note"]), got


# A pane cannot name a register twice, so a repeat is where the next repaint begins,
# anchored on the pane's banner.

BANNER = "oooo" + dcons.PANE_HEADER + "oooooooooooooooooooo"


def pane_fragment(names: list[str], mode: str = "", **values: str) -> str:
    """A piece of a register pane derived from `REGISTER_NAMES`, in the real painting order."""
    out = []
    for n in names:
        out.append(f"{n}={values.get(n, '00000000')}")
        # The mode token sits at the end of the `SS=` line and nowhere else.
        if n == "SS" and mode:
            out.append(f"{mode}\r\n")
    return "  ".join(out) + "\r\n"


REAL_ORDER = ["EAX", "ESI", "DS", "ES", "FS", "GS", "SS", "EBX", "EDI", "CS", "EIP",
              "ECX", "EBP", "EDX", "ESP"]


def test_two_disjoint_fragments_never_compose_one_address() -> None:
    tail = REAL_ORDER[REAL_ORDER.index("EIP"):]
    head = REAL_ORDER[:REAL_ORDER.index("EIP")]
    stale = pane_fragment(tail, EIP="00012345")
    fresh = BANNER + pane_fragment(head, mode="Pr32", CS="0087", SS="008F")
    got = dcons.parse_last_pane(stale + fresh)
    assert got.get("CS") == "0087", got
    assert "EIP" not in got, (
        f"an EIP survived from a repaint the fresh banner is below: {got}. That is the "
        f"composed address this function exists to refuse")
    dbg = Debugger([stale + fresh + "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _"])
    with pytest.raises(ds.Invalid, match="carries no EIP"):
        where(dbg)


def test_a_whole_repaint_behind_a_stale_tail_is_still_read() -> None:
    """A rule that reset at the fresh `EIP` would lose the same repaint's `CS`."""
    stale = pane_fragment(REAL_ORDER[REAL_ORDER.index("EIP"):], EIP="00099999")
    fresh = BANNER + pane_fragment(REAL_ORDER, mode="Pr32", CS="0087",
                                   EIP="00012345", SS="008F")
    got = dcons.parse_last_pane(stale + fresh)
    assert len(got) == len(REAL_ORDER), got
    assert (got["CS"], got["EIP"]) == ("0087", "00012345"), got


def test_a_headerless_fragment_above_the_last_repaint_is_refused() -> None:
    whole = BANNER + pane_fragment(REAL_ORDER, CS="0087", EIP="00012345", SS="008F")
    newer = pane_fragment(["EAX", "EIP"], EIP="0000DEAD")
    assert dcons.parse_last_pane(whole + newer) == {}


def test_a_delta_with_no_banner_at_all_is_not_a_repaint() -> None:
    assert dcons.parse_last_pane(pane_fragment(REAL_ORDER, CS="0087")) == {}


def test_a_refusal_mid_run_says_the_breakpoint_is_still_armed() -> None:
    """A plain `Invalid` must not escape without the note about the armed trap byte."""
    modeless = ("EAX=00000000  CS=F000   EIP=0000FFF4\r\n"
                "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), modeless],
                   reads=["", "EAX=1 EIP=0000E05B\r\n"])
    with pytest.raises(ds.Invalid) as caught:
        run_to(dbg, 0xF000, 0xE05B, seconds=5.0)
    said = str(caught.value)
    assert "names no CPU mode" in said, said
    assert "STILL ARMED" in said, said
    assert "F000:E05B" in said, said
    assert dbg.altered is True, "the trap byte went in; the session must say so"


def test_a_dropped_read_mid_run_still_names_the_steps_taken() -> None:
    dbg = Debugger([pane_with([], eip="0000FFF0"), pane_with([], eip="0000FFF1"),
                    pane_with([], eip="0000FFF2")])
    calls = {"n": 0}
    real_collect = dbg._collect

    def flaky(settle: float = 0.0, timeout: float = 0.0, early: bool = False) -> str:
        calls["n"] += 1
        if calls["n"] == 3:
            raise ds.Invalid("unexpected_answer",
                "the terminal buffer overflowed and 4096 bytes were lost")
        return real_collect(settle, timeout, early)

    dbg._collect = flaky                                  # type: ignore[method-assign]
    with pytest.raises(ds.Invalid) as caught:
        step(dbg, mode="over", count=10)
    said = str(caught.value)
    assert "terminal buffer overflowed" in said, said
    assert f"{len(dbg.keys)} `over` keystroke(s) of 10 had ALREADY gone" in said, said


# A `resume` answering `ok` without reading its delta looks at nothing. The delta carries
# no register pane, so the PROMPT is the discriminator.

def test_a_resume_that_left_the_machine_at_the_debugger_says_so() -> None:
    """`RESUME_HALTED` is a real delta in which `parse_registers` finds nothing."""
    dbg = Debugger([pane_with([], cs="0814", eip="00000112")],
                   deltas=[RESUME_HALTED])
    got = resume(dbg)
    assert got["halted"] is True, got
    assert got["stopped_at"] == {"cs": "0814", "eip": "00000112", "mode": "Real"}
    assert not dcons.parse_registers(RESUME_HALTED), (
        "the fixture stopped being the one that discriminates: a delta the pane "
        "reading can answer cannot show that the pane reading is wrong")


def test_a_resume_that_let_the_machine_go_says_that_instead() -> None:
    """Nothing is sent to a running machine: the console swallows it without an error."""
    dbg = Debugger([], deltas=[RESUME_RAN])
    got = resume(dbg)
    assert got["halted"] is False, got
    assert got["stopped_at"] is None, got
    assert dbg.sent == [], (
        f"a running machine was asked {dbg.sent}: the console swallows it")


def test_the_two_outcomes_differ_in_the_field_that_answers_the_question() -> None:
    halted = resume(Debugger([pane_with([], cs="0814", eip="00000112")],
                             deltas=[RESUME_HALTED]))
    ran = resume(Debugger([], deltas=[RESUME_RAN]))
    assert halted["halted"] != ran["halted"], (halted, ran)


def test_the_address_is_read_back_and_is_not_scavenged_off_the_delta() -> None:
    """`RESUME_HALTED_GLUED` parses to wrong digits; the address must come from the read-back."""
    glued = dcons.parse_registers(RESUME_HALTED_GLUED)
    assert glued.get("CS") == "081401080100FF91C81440026", (
        f"the fixture no longer glues: {glued}")
    dbg = Debugger([pane_with([], cs="F000", eip="0000DAC6")],
                   deltas=[RESUME_HALTED_GLUED])
    got = resume(dbg)
    assert got["stopped_at"] == {"cs": "F000", "eip": "0000DAC6", "mode": "Real"}
    assert dbg.sent == [ds.NUDGE], dbg.sent


def test_a_prompt_that_came_back_over_an_unreadable_pane_is_still_halted() -> None:
    got = resume(Debugger(["EAX=00000000  SS=0000 Real\r\n"], deltas=[RESUME_HALTED]))
    assert got["halted"] is True, got
    assert got["stopped_at"] is None, got


def test_the_key_goes_once_and_this_tool_never_sends_it_again() -> None:
    ran = Debugger([], deltas=[RESUME_RAN])
    resume(ran)
    halted = Debugger([pane_with([], cs="0814", eip="00000112")],
                      deltas=[RESUME_HALTED])
    resume(halted)
    assert ran.keys == [ds.RUN_KEY], ran.keys
    assert halted.keys == [ds.RUN_KEY], halted.keys


class Wire(RealPositionReaders):
    """Only `_read` is fake, so the real `_collect` runs; an empty poll sleeps its slice."""

    def __init__(self, script: list[str], panes: list[str] | None = None) -> None:
        self.script = list(script)
        self.panes = list(panes or [])
        self.polls = 0
        self.keys: list[bytes] = []
        self.sent: list[str] = []
        self._peek_carry = ""
        self._raw_tail, self._raw_reads = "", 0

    _keys = ds.Session._keys

    def _read(self, seconds: float = 0.0) -> str:
        self.polls += 1
        chunk = self.script.pop(0) if self.script else ""
        if not chunk:
            time.sleep(seconds)
        return chunk

    def _write(self, data: bytes) -> None:
        # The real release hook: a run key drains the terminal first, and `resume`'s `screen`
        # is defined by that drain.
        ds.Session._release(cast(ds.Session, self), data)
        self.keys.append(data)

    def command(self, text: str, **_: object) -> str:
        self.sent.append(text)
        return self.panes.pop(0) if self.panes else ""

    def _collect(self, settle: float, timeout: float, early: bool = False) -> str:
        return ds.Session._collect(cast(ds.Session, self), settle, timeout, early)


def wired(script: list[str], panes: list[str] | None = None,
          residue: str = "") -> dict[str, object]:
    """`residue` is what the terminal held before the F5; the release drains it first."""
    return ds.Session.resume(cast(ds.Session, Wire([residue, *script], panes)))


def test_a_leftover_of_the_previous_command_is_not_read_as_this_ones_reply() -> None:
    """A stale listing left in the drain must not be taken as this command's reply."""
    stale = ("ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\n-----\r\n00. BP 00A7:5D730\r\n"
             + dcons.PROMPT + " _")
    fresh = dcons.BPLIST_HEADER + "\r\n-----\r\n" + dcons.PROMPT + " _"
    wire = Wire([stale, "", "", fresh])
    delta = ds.Session.command(cast(ds.Session, wire), "BPLIST", settle=0.05, timeout=2.0)
    assert "00A7:5D730" not in delta, delta
    assert dcons.parse_breakpoints(delta) == [], delta
    assert wire.keys == [b"BPLIST\r"], "the drain never types anything"


class Released(Wire):
    """The wire after a state command, with the stop flag and count of the real session."""

    def __init__(self, script: list[str], panes: list[str] | None = None) -> None:
        super().__init__(script, panes)
        self._at_debugger, self.stop_count = True, 1

    _mark_stopped = ds.Session._mark_stopped
    resume = ds.Session.resume
    where = ds.Session.where
    _survey = ds.Session._survey

    def alive(self) -> bool:
        return True


def test_a_late_repaint_read_as_the_releases_halt_is_taken_back_when_no_pane_comes() -> None:
    """A state command's repaint can land after the release's drain; its prompt reads as a halt."""
    late = "DEBUG: Saved /x/a.sav\r\n" + dcons.PROMPT + " _"
    wire = Released(["", late], panes=[])
    got = ds.Session.resume_after_command(cast(ds.Session, wire))
    assert got["halted"] is False and got["stopped_at"] is None, got
    assert wire._at_debugger is False and wire.stop_count == 1, "the false stop stayed counted"


def test_a_real_halt_after_the_release_is_kept_with_its_position() -> None:
    late = dcons.PROMPT + " _"
    wire = Released(["", late], panes=["", pane_with([], cs="0814", eip="00000112")])
    got = ds.Session.resume_after_command(cast(ds.Session, wire))
    assert got["halted"] is True and got["stopped_at"] == {"cs": "0814", "eip": "00000112",
                                                           "mode": "Real"}, got
    assert wire._at_debugger is True and wire.stop_count == 2


class PromptInTheLook(Released):
    """A breakpoint fires inside the second look: its prompt marks the stop, with no pane."""

    def where(self) -> dict[str, str]:
        ds.Session._mark_stopped(cast(ds.Session, self))
        raise ds.NotStopped("no register pane came back from `BPLIST` (emulator running)")


def test_a_stop_the_second_look_saw_is_kept_without_its_position() -> None:
    wire = PromptInTheLook(["", dcons.PROMPT + " _"], panes=[])
    got = ds.Session.resume_after_command(cast(ds.Session, wire))
    assert got["halted"] is True and got["stopped_at"] is None, got
    assert wire._at_debugger is True and wire.stop_count == 2, (wire._at_debugger,
                                                               wire.stop_count)


class UnreadablePane(Released):
    def where(self) -> dict[str, str]:
        ds.Session._mark_stopped(cast(ds.Session, self))
        raise ds.Invalid("unexpected_answer", "the register pane came back but names no CPU mode")


def test_a_second_look_that_cannot_read_the_pane_does_not_raise() -> None:
    wire = UnreadablePane(["", dcons.PROMPT + " _"], panes=[])
    got = ds.Session.resume_after_command(cast(ds.Session, wire))
    assert got["halted"] is True and got["stopped_at"] is None, got


RESUME_SETTLE_S = 1.0


def test_a_prompt_that_arrives_after_the_settle_is_not_seen_and_halted_reads_false() -> None:
    """Pins a limit: `_collect` closes at the first settle-long silence, missing a later prompt."""
    # One byte, silence past `resume`'s settle, then the prompt: a stop too late to be seen.
    script = ["COMMAND.COM\r\n"] + [""] * (round(RESUME_SETTLE_S / ds.COLLECT_SLICE_S) + 5) + [
        dcons.PROMPT + " _"]
    got = wired(script, panes=[pane_with([], cs="0814", eip="00000112")])
    assert got["halted"] is False, got
    assert got["stopped_at"] is None, got
    assert dcons.PROMPT not in cast(str, got["screen"]), (
        "the prompt reached the delta after all, so this case is no longer about the "
        f"window closing early: {got['screen']!r}")


def test_the_same_prompt_inside_the_window_is_seen() -> None:
    """The control: only the prompt's arrival time differs."""
    script = ["COMMAND.COM\r\n", "", dcons.PROMPT + " _"]
    got = wired(script, panes=[pane_with([], cs="0814", eip="00000112")])
    assert got["halted"] is True, got
    assert got["stopped_at"] == {"cs": "0814", "eip": "00000112", "mode": "Real"}


def test_a_terminal_that_never_said_anything_costs_the_whole_timeout() -> None:
    wire = Wire([])
    began = time.monotonic()
    got = ds.Session._collect(cast(ds.Session, wire), settle=0.05, timeout=0.4)
    elapsed = time.monotonic() - began
    assert got == "", got
    assert elapsed >= 0.4, (
        f"the collect returned after {elapsed:.2f} s of a 0.4 s bound having read "
        f"nothing: the quiet timer started before any byte arrived, so a silent "
        f"terminal now closes the window instead of waiting it out")


def test_the_tool_hands_both_fields_on_and_takes_nothing_away() -> None:
    # A halt returns the enriched reply: two extra register panes after the halt delta.
    dbg = Debugger([pane_with([], cs="0814", eip="00000112"),
                    pane_with([], cs="0814", eip="00000112"),
                    pane_with([], cs="0814", eip="00000112")],
                   deltas=[RESUME_HALTED])
    dstate.STATE.session = cast(ds.Session, dbg)
    try:
        got = cast(dict[str, Any], server.resume(detail=True))
    finally:
        dstate.STATE.session = None
    assert got["status"] == "ok", got
    assert "verdict" not in got, "a resume that waited for nothing carries none"
    assert got["stop_seq"] >= 1, got
    assert got["pc"] == "0814:00000112" and got["cpu_mode"] == "real"
    assert got["screen_delta"] == RESUME_HALTED, got
    assert "omitted" not in got and "how" not in got
    assert got["regs"] and got["watches"] == [] and isinstance(got["cause"], str)
    assert got["e9"]["available"] is False



class StoppedLogSession(LogSession):
    """A `LogSession` that can say it is parked at the debugger."""

    def __init__(self, log: Path, *, at_debugger: bool) -> None:
        super().__init__(log)
        self._parked = at_debugger

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return self._parked


def test_a_wait_on_a_machine_stopped_at_the_debugger_refuses_at_once(tmp_path: Path) -> None:
    """A stopped guest writes nothing; what the log already holds is still answered first."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    parked = StoppedLogSession(log, at_debugger=True)
    began = time.monotonic()
    with pytest.raises(ds.Invalid, match="stopped at the debugger"):
        parked.e9_wait("never_going_to_appear", seconds=30)
    assert time.monotonic() - began < 1.0, "it sat out the bound on a stopped machine"
    assert parked.e9_wait("BOOT", seconds=30)["already"] is True
    running = StoppedLogSession(log, at_debugger=False)
    assert running.e9_wait("never_going_to_appear", seconds=0.3)["verdict"] == "TIMEOUT"


def test_a_waited_answer_says_how_many_lines_sat_before_the_match(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    assert LogSession(log).e9_wait("info_open", seconds=1)["lines_before"] == 1

    def append_later() -> None:
        time.sleep(0.3)
        with log.open("a", encoding="utf-8") as fh:
            fh.write("Bochs port E9h: [+ 1.000] MISC  . filler\n")
            fh.write("Bochs port E9h: [+ 1.100] ACT   . key down SPACE mods=0\n")

    writer = threading.Thread(target=append_later)
    writer.start()
    try:
        got = LogSession(log).e9_wait("key down SPACE", seconds=10)
    finally:
        writer.join()
    assert got["already"] is False and got["lines_before"] == 3, got




class Console(Wire):
    """A `Wire` whose `command`, `at_debugger` and stopped flag are the real ones, born running."""

    _at_debugger = False
    _peek_carry = ""
    stop_count = 0

    def command(self, text: str, **_: object) -> str:
        self.sent.append(text)
        return ds.Session.command(cast(ds.Session, self), text)

    def alive(self) -> bool:
        return True

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return ds.Session.at_debugger(cast(ds.Session, self))

    def _mark_stopped(self) -> None:
        ds.Session._mark_stopped(cast(ds.Session, self))


def test_a_stop_that_lands_inside_a_typed_commands_own_read_is_not_lost() -> None:
    """The stop's prompt is consumed as the NUDGE's reply, so nothing marks the machine stopped."""
    con = Console([RESUME_HALTED])
    with pytest.raises(ds.NotStopped):
        con.where()
    assert con.at_debugger() is True, "the prompt went past inside `command` and was not counted"
    assert con.stop_count == 1, con.stop_count
    assert not dcons.parse_registers(RESUME_HALTED), (
        "the fixture stopped discriminating: with a register pane `where()` would answer")


def test_a_release_forgets_the_prompt_a_passive_peek_carried() -> None:
    """A run key forgets the passive peek's carry along with the flag."""
    seen_stop = "0814:00000112 CD21int  21\r\n" + dcons.PROMPT
    assert dcons.PROMPT in seen_stop[-dcons.STOP_CARRY:], "the fixture must fit the carry"
    # After F5 one line of output, then silence, so the collect closes on its settle.
    con = Console([seen_stop, "COMMAND.COM\r\n", "", "", ""])
    assert con.at_debugger() is True
    got = ds.Session.resume(cast(ds.Session, con))
    assert got["halted"] is False, got
    assert con.at_debugger() is False, "the carry from before the release resurrected the prompt"


class LateStopLogSession(LogSession):
    """Says running to the first `running_answers` questions and stopped from then on."""

    def __init__(self, log: Path, *, running_answers: int) -> None:
        super().__init__(log)
        self.asked = 0
        self.running_answers = running_answers

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        self.asked += 1
        return self.asked > self.running_answers


def test_an_expiry_consults_the_debugger_before_saying_still_running(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop landing after the last poll must not read as the process still running."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(core_wait, "POLL_S", 0.3)
    late = LateStopLogSession(log, running_answers=1)
    with pytest.raises(ds.E9Stopped, match="stopped at the debugger"):
        late.e9_wait("never_going_to_appear", seconds=0.2)
    assert late.asked == 2, late.asked
    still = LateStopLogSession(log, running_answers=99)
    got = still.e9_wait("never_going_to_appear", seconds=0.2)
    assert got["verdict"] == "TIMEOUT" and "still running" in str(got["note"]), got
    assert still.asked == 2, still.asked


def test_a_resume_reads_only_what_the_f5_produced_not_the_previous_ops_repaint() -> None:
    """The delta starts where the last read ended, and a console op's repaint ends in the prompt."""
    residue = "Breakpoint list:\r\n0814:0100 BP\r\n" + dcons.PROMPT + " _"
    ran = wired(["COMMAND.COM\r\n", "", ""], residue=residue)
    assert ran["halted"] is False, ran
    assert "Breakpoint list:" not in cast(str, ran["screen"]), ran["screen"]
    halted = wired(["", dcons.PROMPT + " _"], panes=[pane_with([], cs="0814", eip="00000112")],
                   residue=residue)
    assert halted["halted"] is True, halted
    assert "Breakpoint list:" not in cast(str, halted["screen"]), halted["screen"]


class StopsAfterWriting(LogSession):
    """Writes the awaited line and parks at the debugger inside one poll interval."""

    def __init__(self, log: Path, *, line: str) -> None:
        super().__init__(log)
        self.line, self.polls, self.parks = line, 0, False

    def at_debugger(self) -> bool:
        return self.parks

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super()._e9_since(offset, channel)
        if self.polls == 2:
            with self.launch.logfile.open("a", encoding="utf-8") as f:
                f.write(self.line + "\n")
            self.parks = True
        return got


def test_a_reaction_written_just_before_the_stop_is_found_not_refused(tmp_path: Path) -> None:
    """The loop checks the debugger first and reads the log last, so a last read is due."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    line = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1"
    got = StopsAfterWriting(log, line=line).e9_wait("key_cue_a", seconds=5)
    assert got["line"] == line and got["already"] is False, got
    with pytest.raises(ds.E9Stopped, match="stopped at the debugger"):
        StopsAfterWriting(log, line="Bochs port E9h: [+   9.000] UI    . other").e9_wait(
            "key_cue_b", seconds=5)




def test_e9_wait_reports_its_progress_while_it_waits(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(mprogress, "PROGRESS_EVERY_S", 0.0)
    ticks: list[tuple[float, float | None, str]] = []
    LogSession(log).e9_wait("never", seconds=0.25,
                            progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks, "the wait reported nothing"
    # A wait measured in time has no total: a bar towards the bound reads as progress to failure.
    assert all(t is None and m.startswith("log_wait guest /never/") for _p, t, m in ticks)
    assert ticks[-1][0] > 0 and "0 lines arrived" in ticks[-1][2]
    ticks.clear()
    LogSession(log).e9_wait("BOOT", seconds=0.25, progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks == []


class _Listening:
    """What `await_stop` reaches for on a machine that never announces a stop."""

    _peek_carry = ""

    def alive(self) -> bool:
        return True

    def _read(self, timeout: float) -> str:
        time.sleep(timeout)
        return ""


def test_the_stop_wait_of_run_to_reports_its_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    began = time.monotonic()
    expired, _saw = ds.Session.await_stop(cast(ds.Session, _Listening()), began, began + 0.3,
                                           "0087:0234", lambda p, t, m: ticks.append(m))
    assert expired is True and ticks and ticks[0].startswith("run_to 0087:0234: ")


def test_a_wait_that_runs_out_leaves_what_it_read_last_for_the_next_look() -> None:
    class _Split(_Listening):
        def _read(self, timeout: float) -> str:
            return "DS=0008 I-"

    listening = _Split()
    began = time.monotonic()
    expired, _ = ds.Session.await_stop(cast(ds.Session, listening), began, began + 0.3,
                                       "0087:0234", lambda p, t, m: None)
    assert expired is True and listening._peek_carry.endswith("I-"), listening._peek_carry


def test_run_to_hands_its_progress_to_the_stop_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), "",
                    pane_with([], cs="0837", eip="0000004C")])
    out = run_to(dbg, 0xF000, 0xFFF0, seconds=0.3,
                 progress=lambda p, t, m: ticks.append(m))
    assert out.get("verdict") == "TIMEOUT" and ticks and ticks[0].startswith("run_to F000:FFF0")


def test_run_to_cancelled_in_flight_is_brought_back_and_takes_its_breakpoints_with_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from scry_core import cancel

    class Cancelled(Debugger):
        stopped = False
        breaks = 0

        @property
        def parked(self) -> bool:
            return self.at_debugger()

        def at_debugger(self) -> bool:
            return self.stopped

        def break_in(self, seconds: float = 5.0) -> float:
            self.breaks += 1
            self.stopped = True
            return 0.0

    def check() -> None:
        if not cancel.shielding():
            raise asyncio.CancelledError
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Cancelled([pane_with([]), both,
                     both, control_only,
                     control_only, pane_with([])])
    monkeypatch.setattr(cancel, "check", check)
    with pytest.raises(asyncio.CancelledError):
        run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert dbg.breaks == 1, "the run was left in flight"
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent


class PromptInTheNudge(Debugger):
    """The first nudge after the bound reads the prompt and no pane, the next reads the pane."""

    def command(self, text: str, **k: object) -> str:
        out = super().command(text, **k)
        if text == ds.NUDGE and out == "" and not self._at_debugger:
            self._at_debugger = True
        return out


def test_a_run_that_came_to_rest_after_the_bound_is_not_interrupted() -> None:
    dbg = PromptInTheNudge([pane_with([]), pane_with(["00. BP F000:E05B"]), "",
                            pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "OTHER_STOP" and "BREAK" not in dbg.sent, (got, dbg.sent)


def test_a_rest_on_the_control_found_after_the_bound_counts_as_its_hit() -> None:
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    dbg = PromptInTheNudge([pane_with([]), both, "",
                            pane_with([], cs="F000", eip=CONTROL_HIT),
                            both, pane_with(["00. BP F000:E05B"]),
                            pane_with(["00. BP F000:E05B"]), pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=0.05, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT" and got["control"] == {
        "at": "F000:E05B", "hits": 1, "removed": True}, got


def test_a_cancel_during_the_interrupt_at_the_bound_takes_the_breakpoints_with_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    class CancelledAtTheBound(Debugger):
        breaks = 0

        def break_in(self, seconds: float = 5.0) -> float:
            self.breaks += 1
            if self.breaks == 1:
                raise asyncio.CancelledError
            self._at_debugger = True
            return 0.0

    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = CancelledAtTheBound([pane_with([]), both, "",
                               both, control_only, control_only, pane_with([])])
    from scry_core import cancel
    monkeypatch.setattr(cancel, "is_cancellation",
                        lambda e: isinstance(e, asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        run_to(dbg, 0xF000, 0xFFF0, seconds=0.05, control=(0xF000, 0xE05B))
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent


def test_a_non_arrival_whose_control_cleanup_failed_says_both_in_sentences() -> None:
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both, "", pane_with([], cs="0837", eip="0000004C"),
                    both, control_only, control_only, control_only])
    got = run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xE05B))
    assert "F000:FFF0 was removed. `BPDEL` was sent and F000:E05B is STILL" in str(got["note"]), (
        got["note"])


class _SplitPrompt(_Listening):
    """A parked guest whose last passive peek read `I` and left `->` for the next read."""

    _peek_carry = "I"

    def __init__(self) -> None:
        self.reads = ["->"]
        self.stopped = False

    def _read(self, timeout: float) -> str:
        return self.reads.pop(0) if self.reads else super()._read(timeout)

    def _mark_stopped(self) -> None:
        self.stopped = True


def test_a_prompt_split_between_the_last_peek_and_the_stop_wait_is_heard() -> None:
    s = _SplitPrompt()
    began = time.monotonic()
    expired, _saw = ds.Session.await_stop(cast(ds.Session, s), began, began + 0.5, "x")
    assert expired is False and s.stopped, "the split prompt was never matched"
