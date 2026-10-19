"""The DEBUG INTERFACE: stepping, running to an address, and watching memory.

WHY THIS IS ONE FILE AND NOT SPLIT ACROSS THE SESSION'S AND THE SERVER'S. It is a
SURFACE rather than a module: three tools, two pure parsers and one shared repaint,
all of which exist to hold each other up. `watch` picks its debugger command from a
mode token that `parse_mode` reads off the same screen `parse_breakpoints` then
confirms the arming against -- so a reader asking "how does the stepping work" wants
those together, and a case split by layer buries the one relationship that matters.
The registration of the three tools stays in the server file with every other tool's,
because that is a fact about the server and not about stepping.

WHAT THESE ARE. Contract tests: none of them launches DOSBox-X. The double stands in
for the DEBUGGER'S SIDE OF THE CONVERSATION -- what comes back for a command -- and the
real methods are driven against it, so what is exercised is this package's logic and
not a reimplementation of it agreeing with itself.

WHAT IS CAPTURED AND WHAT IS NOT, precisely -- because the first version of this
paragraph said "THE SCREENS ARE CAPTURED, NEVER AUTHORED. Every fixture below…", and
that was an over-claim in the file whose whole subject is not believing what you have
not read back.

CAPTURED off a live This debugger session: the three panes
(`REAL_PANE`, `REAL_PANE_TWO_BPS`, `PROT_PANE`) and, separately and more importantly,
the four BREAKPOINT LIST ROWS below. `pane_with` DERIVES a screen from the captured
shape with caller-supplied rows; `after_delete` is written out inline.

THE ROWS ARE THE HALF THAT MATTERS, and they are captured because an AUTHORED one hid a
live bug through an entire review: the code expected `BPPMEM 00AF:6024` and the debugger
prints `BPPM 00AF:00006024`. The test row had been written from the same belief as the
code, so the assertion could not fail, and every protected-mode watch would have armed a
breakpoint and then refused. A fixture an author invents tests the author.

The properties these cases turn on are the ones nobody would think to write: that the
Output pane SCROLLS, so a delta carries an earlier listing above the new one; that the
mode token sits at the END of the `SS=` line and nowhere else; and that an empty
breakpoint listing and a listing that never happened look identical apart from a header.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from scry_core import log_wait as core_wait
from scry_core import progress as mprogress
from test_dosbox_x_server import returned_key_sets

import dosbox_console as dcons
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

# ---------------------------------------------------------------- captured screens

# The RESET screen, at `F000:FFF0`, before anything has switched the CPU out of real
# mode. Trimmed: the data view and the code overview are dropped and the boot log is
# cut, because neither pane is read by anything here. What is KEPT verbatim is every
# property under test -- the `Real` token's position at the end of the `SS=` line, the
# pane headers as the runs of `o` this terminal renders them into, and the Output tail.
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

# THE SAME SESSION AFTER TWO BREAKPOINTS WERE ARMED, and this one is the fixture the
# whole `rfind` design rests on. It carries TWO `Breakpoint list:` headers: the FIRST
# is the repaint of the earlier, EMPTY listing above, and the second is the answer to
# the command just sent. A reader taking the first header answers "nothing is armed"
# for a machine holding two breakpoints -- green, plausible, and wrong.
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

# The DJGPP client under CWSDPMI, 32-bit protected mode, from the same session walked
# forward to `CS=00A7`. The `Pr32` token is what makes `watch` send `BPPM`.
PROT_PANE = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
    "EAX=0000000A  ESI=00400000  DS=00AF   ES=00AF   FS=008F   GS=0000   SS=008F Pr32\r\n"
    "EBX=000000AF  EDI=00238A00  CS=00A7   EIP=00001A27  C0 Z1 S0 O0 A0 P1 D0 I1 T0\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "Breakpoint list:\r\n"
    "-------------------------------------------------------------------------\r\n"
    "I-> _")


# ---------------------------------------------------------- the `resume` deltas
#
# CAPTURED VERBATIM AND WHOLE off a live This debugger, driving
# this package's own `tests/guest/probe.conf`. Not trimmed, because the property under
# test is the ABSENCE of a marker and a slice can only ever lose one.
#
# THEY EXIST BECAUSE THE OBVIOUS FIXTURE WOULD HAVE BEEN A REGISTER PANE, AND THAT IS
# NOT WHAT COMES BACK. `resume`'s delta carries no `Register Overview` banner even when
# the machine stops: this debugger repaints only the cells that CHANGED, and a
# register's LABEL does not change. Scored against `where()` over twelve controlled
# resumes -- three that ran on, nine that stopped:
#
#   `PROMPT` in the delta         agreed with the machine   12/12
#   `PANE_HEADER` in the delta     agreed                    3/12  (never present)
#   `parse_registers` non-empty    agreed                    6/12
#
# A fixture written from the plan's description would have been a pane, the code would
# have been written to parse one, and both would have agreed with each other about a
# screen the emulator does not send.

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
# THE THIRD ONE IS THE ADVERSARIAL FIXTURE AND IT IS WHY THE 6/12 ABOVE IS WORSE THAN
# IT LOOKS. `parse_registers` finds something in it -- but what it finds is
# `CS=081401080100FF91C81440026`, the repainted DIGITS of several fields glued into one
# value no register ever held. So the pane reading is not merely blind here: on the one
# delta where it answers at all, it answers with rubbish of exactly the right shape.


# THE FOUR LIST ROWS, VERBATIM off `BPLIST`. They are constants rather
# than literals at each site so a second opinion about the format cannot be introduced
# one case at a time, and the three memory spellings are NOT uniform -- which is the
# whole point:
#
#   BPM  0040:006C  ->  BPMEM 0040:006C (00)        offset %04X, keyword gains `MEM`
#   BPPM 00AF:6024  ->  BPPM 00AF:00006024 (00)     offset %08X, keyword does NOT
#   BPLM 000B8000   ->  BPLM 000B8000 (00)
BPMEM_ROW = "00. BPMEM 0040:006C (00)"
BPPM_ROW = "00. BPPM 00AF:00006024 (00)"
BP_ROW = "01. BP F000:E05B"


def pane_with(rows: list[str], *, mode: str = "Real", cs: str = "F000",
              eip: str = "0000FFF0") -> str:
    """A repaint carrying a given breakpoint listing, built from the CAPTURED shape.

    It is DERIVED from the fixtures above rather than written afresh: a case that needs
    three breakpoints should differ from the real thing in the rows and in nothing
    else, and a second hand-written screen is a second opinion about what the debugger
    prints.
    """
    return (
        "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
        f"EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 {mode}\r\n"
        f"EBX=00000000  EDI=00000000  CS={cs}   EIP={eip}  C0 Z0 S0 O0\r\n"
        "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
        f"{dcons.BPLIST_HEADER}\r\n"
        "-------------------------------------------------------------------------\r\n"
        + "".join(f"{r}\r\n" for r in rows) + "I-> _")


# ------------------------------------------------------------------- the double

class RealPositionReaders:
    """The three position readers, delegated to the REAL methods rather than reimplemented.

    Shared by every double in this file that stands in for a session's console (the
    scripted `Debugger`, the polling `Wire`): what is worth exercising through them is the
    parsing, the mode refusal and the "read the list back" discipline, and a double that
    reimplemented those would be a second opinion agreeing with itself. The real methods
    reach only for `command` and `alive`, which each double provides. ONE copy, because the
    same three lines in two doubles is the duplication the dup gate caught.
    """

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
        # A scripted console answers, so it is stopped, unless a position read found no pane
        # behind a heard prompt (the real `where` clears the flag then).
        return self._at_debugger

    _at_debugger = True
    stop_count = 1

    def _mark_stopped(self) -> None:
        self._at_debugger = True     # the real one counts transitions; this never leaves


class Debugger(RealPositionReaders):
    """The debugger's SIDE of the conversation: what comes back for what is sent.

    It DISPATCHES by command -- a `NUDGE` takes the next repaint off the queue,
    anything else answers with nothing, which is what the real debugger does for a `BP`:
    it prints an acknowledgement into a pane nobody here reads.

    IT IS STILL ORDER-SENSITIVE, and an earlier version of this paragraph claimed it was
    not ("answers by COMMAND rather than by call order"). `panes.pop(0)` is a queue, so
    a change in how many round trips a method makes shifts every later answer. That is
    not merely untidy: it means a break which REMOVES a round trip can redden a case
    through pane starvation rather than through the property the case is named for --
    measured, one such red was credited to an assertion that never executed.

    THE KEYS ARE RECORDED AS BYTES. `step`'s whole difference between `over` and `into`
    is which escape sequence goes down the terminal, so a double that swallowed them
    would leave the one thing that tool does untested.
    """

    def __init__(self, panes: list[str], *, alive: bool = True,
                 reads: list[str] | None = None,
                 deltas: list[str] | None = None) -> None:
        self.panes = list(panes)
        self.reads = list(reads or [])
        # WHAT `_collect` HANDS BACK, which is a DIFFERENT channel from `panes`. A pane
        # is what a typed command produces; a delta is what a KEY produces, and
        # `resume`'s whole answer is read off one. They are separate queues because a
        # resume that stops the machine consumes one of each -- the delta it reads
        # `halted` from, and then the pane its address read-back asks for -- and a
        # single queue would make the second answer depend on how the first was
        # spelled.
        self.deltas = list(deltas or [])
        self.sent: list[str] = []
        self.keys: list[bytes] = []
        self._alive = alive
        self.altered = False
        # No instrumentation channel: the enriched stop reply's E9 summary delegates to the
        # real `e9`, which refuses a logfile-less session, and reads that refusal as "no log
        # available" rather than letting it blow up the reply.
        self.launch = SimpleNamespace(logfile=None, watched=True)

    def command(self, text: str, **_: object) -> str:
        self.sent.append(text)
        if text == ds.NUDGE:
            return self.panes.pop(0) if self.panes else ""
        return ""

    def _write(self, data: bytes) -> None:
        # The real release hook: a run key drains one `reads` entry, which is the drain
        # `run_to`'s cases below feed ("the first is eaten by the drain").
        ds.Session._release(cast(ds.Session, self), data)
        self.keys.append(data)

    def _collect(self, settle: float = 0.0, timeout: float = 0.0,
                 early: bool = False) -> str:
        return self.deltas.pop(0) if self.deltas else ""

    def _read(self, seconds: float = 0.0) -> str:
        return self.reads.pop(0) if self.reads else ""

    def alive(self) -> bool:
        return self._alive

    def break_in(self, seconds: float = ds.BREAK_IN_WAIT_S) -> float:
        """The channel's `BREAK`, recorded among what was sent: the debugger is back a moment
        later, and the next position read takes the next repaint off the queue."""
        self.sent.append("BREAK")
        self._at_debugger = True
        return 0.1

    # THE POSITION READERS ARE THE REAL ONES (`RealPositionReaders`), the same choice
    # `FakeSession.read_memory` and `.selector` make next door, for the same reason.
    def resume(self) -> dict[str, object]:
        return ds.Session.resume(cast(ds.Session, self))

    def breakpoints(self) -> list[dict[str, str]]:
        return ds.Session.breakpoints(cast(ds.Session, self))

    def registers(self) -> dict[str, str]:
        return ds.Session.registers(cast(ds.Session, self))

    def e9(self, pattern: str, limit: int) -> tuple[list[str], int]:
        # Delegated like the readers: with `launch.logfile` None the real method refuses,
        # which is what the enriched stop reply expects for a session with no log channel.
        return ds.Session.e9(cast(ds.Session, self), pattern, limit)

    def _e9_text(self) -> str:
        return ds.Session._e9_text(cast(ds.Session, self))

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ds.Session.e9_new_since(cast(ds.Session, self), offset)

    # And the three the SERVER calls, for the cases that drive a tool rather than a
    # method. Delegated for the same reason: what the tool layer is being held to is
    # that it adds an envelope and takes nothing away, which is only worth asserting
    # over the answer the real method builds.
    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        return ds.Session.step(cast(ds.Session, self), mode=mode, count=count)

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.run_to(cast(ds.Session, self), seg, off, seconds, control, progress)

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        return ds.Session.watch(cast(ds.Session, self), segment=segment, offset=offset)

    def state(self) -> dict[str, object]:
        return {"alive": self._alive, "altered": self.altered}


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


# ------------------------------------------------------------------ the parsers

def test_the_mode_is_read_as_a_token_and_not_as_the_absence_of_another() -> None:
    """All three modes come back by NAME, which is what stops an absence being one.

    A pane that did not repaint, a running machine and a dead emulator all produce text
    with no `Pr` in it. Read as "not protected" every one of them answers `Real`, and
    `watch` would then send `BPM` where the machine wanted `BPPM` -- which this
    debugger accepts without a word.
    """
    assert dcons.parse_mode(REAL_PANE) == "Real"
    assert dcons.parse_mode(PROT_PANE) == "Pr32"
    assert dcons.parse_mode("SS=008F Pr16\r\n") == "Pr16"


def test_a_screen_that_names_no_mode_is_not_a_mode() -> None:
    assert dcons.parse_mode("") is None
    assert dcons.parse_mode("EAX=00000000  EIP=0000FFF0\r\n") is None


def test_the_mode_is_the_last_one_because_the_pane_scrolls() -> None:
    """A delta can hold a repaint of an EARLIER screen above the current one, and the
    mode being asked about is the one the machine is in now. A program that has just
    entered protected mode leaves both tokens in one delta."""
    assert dcons.parse_mode(REAL_PANE + PROT_PANE) == "Pr32"


def test_the_breakpoint_list_is_read_from_the_last_listing_in_the_delta() -> None:
    """Two `Breakpoint list:` headers in one delta, the rows belonging to the second.

    ON ITS OWN THIS CASE CANNOT TELL `rfind` FROM `find`: serving `find` in place of
    `rfind` leaves it GREEN, which is how the gap was found. Slicing from either header and reading
    to the end of the text picks up the later rows either way, so this asserts that the
    rows are found and parsed, and the case BELOW is the one that holds the position.
    Recorded rather than quietly repaired, because "two headers" reads like a
    discriminating fixture and is not one.
    """
    got = breakpoints(Debugger([REAL_PANE_TWO_BPS]))
    assert [b["entry"] for b in got] == ["BPMEM 0040:006C (00)", "BP F000:E05B"]
    assert [b["index"] for b in got] == ["00", "01"]


def test_a_deleted_breakpoint_does_not_come_back_from_an_earlier_repaint() -> None:
    """THE CASE THE `rfind` REALLY EXISTS FOR: the populated listing comes FIRST.

    This is the `BPDEL` path, and it is the one `run_to` rests its `breakpoint_removed`
    on. After a delete the debugger prints an EMPTY listing -- but the Output pane
    SCROLLS, so the previous, populated listing is still above it. Read from the first
    header, the deleted breakpoint is still there: the tool would report a removal that
    did not happen, or refuse to believe one that did.

    IT IS NOT HYPOTHETICAL. The live case for `run_to` was written with a plain
    substring search over the delta and FAILED against a correct removal for exactly
    this reason, which is how the shape got captured here.
    """
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
    """The two look identical apart from the header, and they mean opposite things:
    one says nothing is armed, the other says nothing was read."""
    assert breakpoints(Debugger([REAL_PANE])) == []
    with pytest.raises(ds.Invalid, match="printed no"):
        breakpoints(Debugger([pane_with([]).replace(dcons.BPLIST_HEADER, "")]))


# --------------------------------------------------------------------- where()

def test_where_answers_with_the_address_and_the_mode_it_is_in() -> None:
    """An address quoted without its mode is not an address: the same sixteen bits are
    a paragraph of physical memory in one and an index into a descriptor table in the
    other."""
    assert where(Debugger([PROT_PANE])) == {"cs": "00A7", "eip": "00001A27",
                                            "mode": "Pr32"}


def test_where_refuses_when_the_machine_is_not_stopped() -> None:
    """The refusal every one of these tools rests on. Each sends something a running
    machine swallows without a word, so this has to be settled by a reading first."""
    with pytest.raises(ds.Invalid, match="stopped at the debugger"):
        where(Debugger([""]))


def test_where_refuses_a_pane_that_repainted_but_named_no_mode() -> None:
    """The half that stops "no token" being silently read as real mode."""
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        where(Debugger(["EAX=00000000  CS=F000   EIP=0000FFF0\r\n"]))


# ---------------------------------------------------------------------- step()

def test_step_sends_f10_for_over_and_f11_for_into() -> None:
    """THE ONE THING THAT DISTINGUISHES THE TWO MODES is which escape goes down the
    terminal, so it is asserted as bytes. The debugger's own help names them: "F10/F11
    - Step over / trace into instruction"."""
    over = Debugger([REAL_PANE, REAL_PANE])
    step(over, mode="over", count=1)
    assert over.keys == [b"\x1b[21~"]

    into = Debugger([REAL_PANE, REAL_PANE])
    step(into, mode="into", count=1)
    assert into.keys == [b"\x1b[23~"]


def test_step_reports_what_happened_and_not_what_was_asked_for() -> None:
    """A STEP OVER A CALL THAT NEVER RETURNS LEAVES THE MACHINE RUNNING, and every
    remaining keystroke then goes to a debugger that is not listening.

    So four were asked for, two panes come back, and the answer is TWO with `running`
    saying why -- not four. A tool that sent the keys and counted them would report a
    fabricated number of exactly the right shape, and the caller would go on to read
    memory at an address the machine left long ago.
    """
    dbg = Debugger([REAL_PANE, REAL_PANE, REAL_PANE])   # where() + two good steps
    got = step(dbg, mode="over", count=4)
    assert got["asked"] == 4
    assert got["completed"] == 2
    assert got["running"] is True
    # IT STOPPED SENDING. Three keys went (the third is the one that lost the machine)
    # and the fourth was never sent, which is the difference between a loop that reads
    # its result back and one that counts.
    assert len(dbg.keys) == 3


def test_a_dead_emulator_is_a_refusal_and_not_a_partial_result() -> None:
    """`running` and `GONE` are not the same answer. The steps that "completed" on a
    machine that no longer exists were measured against nothing, so there is no partial
    result worth handing back -- the refusal is the whole of it."""
    dbg = Debugger([REAL_PANE], alive=False)
    with pytest.raises(ds.Invalid):
        step(dbg, mode="over", count=3)


def test_step_refuses_a_mode_it_does_not_have_and_a_count_it_cannot_afford() -> None:
    dbg = Debugger([REAL_PANE] * 4)
    with pytest.raises(ds.Invalid, match="not a way to step"):
        step(dbg, mode="sideways", count=1)
    with pytest.raises(ds.Invalid, match="step count"):
        step(dbg, mode="over", count=0)
    # A LITERAL, not `ds.STEP_MAX + 1`: derived from the constant, the probe moves WITH
    # it, so the direction that matters -- a ceiling raised until it bounds nothing, the
    # failure this file's own `MAX_SECONDS` comment names -- is the one it cannot see.
    assert ds.STEP_MAX == 64, "the ceiling moved; decide it deliberately and edit here"
    with pytest.raises(ds.Invalid, match="step count"):
        step(dbg, mode="over", count=65)
    # NOTHING WAS SENT. A refusal that had already pressed keys would leave the machine
    # somewhere the reply does not describe.
    assert dbg.keys == []


def test_step_refuses_before_touching_a_machine_that_is_not_stopped() -> None:
    # The wording is `step`'s OWN: handing back the text `registers` prints would describe
    # a tool the caller did not call.
    dbg = Debugger([""])
    with pytest.raises(ds.Invalid, match="a step is a KEYSTROKE"):
        step(dbg, mode="over", count=1)
    assert dbg.keys == []


# --------------------------------------------------------------------- run_to()

ARRIVED = "0000FFF0"


def test_run_to_arrives_and_removes_the_breakpoint_it_created() -> None:
    """A `BP` is PERSISTENT, so a `run_to` that left it behind would silently stop the
    next `resume` at an address the caller had finished with."""
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]),               # is it stopped, and in what mode
                    armed,                       # the arming, read back
                    pane_with([], cs="F000", eip=ARRIVED),   # where it stopped
                    armed,                       # look the index up again
                    pane_with([])])              # gone
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TARGET"
    assert got["breakpoint_removed"] is True
    assert got["note"] == ""
    assert "BP F000:FFF0" in dbg.sent and "BPDEL 00" in dbg.sent


def test_run_to_in_real_mode_arrives_at_an_aliased_seg_off() -> None:
    """MANY SEG:OFF PAIRS NAME ONE BYTE IN REAL MODE. The symbol layer folds a map frame
    onto the load paragraph and arms `BP 1000:0810`; the CPU stops with the program's own
    `CS=1080 EIP=0010`, the same linear address. That IS the arrival: seen red, the string
    compare called it "stopped elsewhere" and left the breakpoint armed to stop the next
    resume. Protected mode keeps the direct compare (the breakpoint is at the live selector)."""
    armed = pane_with(["00. BP 1000:0810"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="1080", eip="00000010"),   # the same byte, spelt by the CPU
                    armed, pane_with([])])
    got = run_to(dbg, 0x1000, 0x0810)
    assert got["verdict"] == "TARGET", got
    assert got["breakpoint_removed"] is True, got
    # THE CONTROL: a different byte is still "elsewhere", whatever its spelling.
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="1080", eip="00000011")])
    got = run_to(dbg, 0x1000, 0x0810)
    assert got["verdict"] == "OTHER_STOP" and "still armed" in str(got["note"]).lower(), got


def test_run_to_looks_the_index_up_again_rather_than_reusing_it() -> None:
    """`BPDEL` RENUMBERS what is left, so an index recorded at arming time is only
    still correct if nothing was deleted in between. Here the breakpoint is at 01 when
    it is armed and at 00 by the time it is removed -- a tool that cached the first
    would delete somebody else's."""
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
    """TWO COMPLETELY DIFFERENT FINDINGS that an unverified arming makes identical.

    The acknowledgement cannot settle it: `DEBUG: Set breakpoint at ...` goes into a
    SCROLLING pane, so it can be a repaint of an earlier one. Resuming on an unarmed
    breakpoint runs the machine with nothing to stop it, and the reply would then blame
    the address.
    """
    dbg = Debugger([pane_with([]), pane_with([])])
    with pytest.raises(ds.Invalid, match="does not list a breakpoint"):
        run_to(dbg, 0xF000, 0xFFF0)
    # AND IT DID NOT RESUME. A refusal that had already let the machine go would leave
    # the caller with a running emulator and a message about arming.
    assert dbg.keys == []


def test_stopping_somewhere_else_is_not_an_arrival() -> None:
    """Another breakpoint getting there first is ordinary, and reporting it as arrival
    would put the caller at an address they did not ask for while telling them they are
    where they wanted to be."""
    dbg = Debugger([pane_with([]),
                    pane_with(["00. BP F000:FFF0"]),
                    pane_with([], cs="F000", eip="0000E05B")])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "OTHER_STOP"
    assert got["breakpoint_removed"] is False
    assert "0000E05B" in str(got["note"]) and "still armed" in str(got["note"])
    assert not any(s.startswith("BPDEL") for s in dbg.sent)


def test_a_bound_that_expires_interrupts_the_run_and_keeps_the_target_armed() -> None:
    """THE BOUND INTERRUPTS: a run still going when its bound runs out is brought back with
    `BREAK` and surveyed where it stands, a TIMEOUT, so the caller never inherits a machine
    no reader can answer for. The target stays armed, deliberately: the caller has not
    reached it, and the reply says so rather than claiming a cleanup."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), "",
                    pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TIMEOUT", got
    assert "BREAK" in dbg.sent, dbg.sent
    assert got["stopped_at"] == {"cs": "0837", "eip": "0000004C", "mode": "Real"}, got
    assert got["breakpoint_removed"] is False
    assert "interrupted" in str(got["note"]) and "still armed" in str(got["note"]), got


CONTROL_HIT = "0000E05B"


def test_run_to_with_a_control_counts_its_hits_and_releases_the_machine_again() -> None:
    """The control is armed BESIDE the target; each time it fires the machine is let go and
    the hit counted, and on arrival BOTH breakpoints are removed. The pane queue spells the
    round trips out: two control stops, then the target, then two cleanups."""
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    prompt = dcons.PROMPT + " _"
    dbg = Debugger([pane_with([]),                                  # stopped, and the mode
                    both,                                           # the arming, read back
                    pane_with([], cs="F000", eip=CONTROL_HIT),      # stop 1: the control
                    pane_with([], cs="F000", eip=CONTROL_HIT),      # stop 2: the control
                    pane_with([], cs="F000", eip=ARRIVED),          # stop 3: the target
                    both, control_only,                             # target BPDEL, read back
                    control_only, pane_with([])],                   # control BPDEL, read back
                   # each release eats one read (the drain), then the wait hears the prompt
                   reads=["", prompt, "", prompt, "", prompt])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TARGET", got
    assert got["control"] == {"at": "F000:E05B", "hits": 2, "removed": True}, got
    assert got["breakpoint_removed"] is True
    assert dbg.keys.count(ds.RUN_KEY) == 3, "released once per control hit, plus the first"
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent   # one per breakpoint, each renumbered to 00


def test_run_to_with_a_control_that_never_fires_reports_zero_hits_and_both_armed() -> None:
    """The silence decision 12 exists for: neither fired within the bound. The session
    interrupts the run and reports the account (`hits: 0`, the control removed, the target
    armed) and the server turns it into INVALID; a single reply saying "it did not arrive"
    would be the wrong verdict."""
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both, "", pane_with([], cs="0837", eip="0000004C"),
                    both, pane_with(["00. BP F000:FFF0"])])
    got = run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT", got
    assert got["control"] == {"at": "F000:E05B", "hits": 0, "removed": True}, got
    assert "F000:FFF0 is still armed" in str(got["note"]), got["note"]


def test_run_to_whose_control_eats_the_whole_bound_is_a_timeout(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The control fires, the clock is spent by the time the position is read, and the
    machine sits at rest ON the control: the target did not fire, the control is counted and
    removed, and the verdict is TIMEOUT, because the bound ran out whatever the last wait saw,
    and nothing was interrupted.
    The clock is a counter, one second per call, so the deadline passes between the stop
    being heard and the position being read."""
    import itertools
    import time
    tick = itertools.count(0.0, 1.0)
    monkeypatch.setattr(time, "monotonic", lambda: next(tick))   # the module `run_to` reads
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only_at_01 = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both,
                    pane_with([], cs="F000", eip=CONTROL_HIT),   # the one stop: the control
                    control_only_at_01, pane_with(["00. BP F000:FFF0"])],   # control BPDEL
                   reads=["", dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=2.5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT", got
    assert "BREAK" not in dbg.sent, "at rest on the control: nothing to interrupt"
    assert got["control"] == {"at": "F000:E05B", "hits": 1, "removed": True}, got
    assert "BPDEL 01" in dbg.sent and dbg.keys.count(ds.RUN_KEY) == 1, dbg.sent
    assert "still armed" in str(got["note"]), got["note"]   # the TARGET stays, on purpose
    assert "ON the control F000:E05B (its hit number 1)" in str(got["note"]), got["note"]
    assert "something else" not in str(got["note"]), "a rest on the control is not a stranger"


def test_run_to_refuses_a_control_the_debugger_did_not_arm() -> None:
    """The read-back covers BOTH breakpoints: a control that is not in the list would make
    every hit count a fiction, so it is refused before the machine is released."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"])])
    with pytest.raises(ds.Invalid, match="F000:E05B"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xE05B))
    assert dbg.keys == []


def test_run_to_reports_a_control_it_could_not_remove_beside_a_sound_arrival() -> None:
    """The arrival stands; the control's cleanup is its own account: `removed: false` with
    the failure text appended to the note, never an INVALID over a cleanup."""
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    control_only = pane_with(["00. BP F000:E05B"])
    dbg = Debugger([pane_with([]), both,
                    pane_with([], cs="F000", eip=ARRIVED),
                    both, control_only,                    # target: BPDEL 00, read back: gone
                    control_only, control_only],           # control: BPDEL 00, STILL there
                   reads=["", dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TARGET" and got["breakpoint_removed"] is True, got
    assert got["control"] == {"at": "F000:E05B", "hits": 0, "removed": False}, got
    assert "F000:E05B is STILL in the" in str(got["note"]), got["note"]


def test_run_to_without_a_control_says_so_with_one_key_and_not_by_omission() -> None:
    """`control` is on EVERY reply, `null` when none was given, so the shape never has to
    be discovered first; and the reply is otherwise what it always was."""
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed, pane_with([], cs="F000", eip=ARRIVED), armed,
                    pane_with([])])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["control"] is None and got["verdict"] == "TARGET"


def test_run_to_refuses_a_control_on_the_target_itself() -> None:
    """By PLACE and not by spelling: in real mode `F000:FFF0` and `FFFF:0000` are one byte,
    and a control there would count every arrival as a control hit and run past it."""
    dbg = Debugger([pane_with([])] * 4)
    with pytest.raises(ds.Invalid, match="same address"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xF000, 0xFFF0))
    with pytest.raises(ds.Invalid, match="same address"):
        run_to(dbg, 0xF000, 0xFFF0, control=(0xFFFF, 0x0000))     # the alias
    assert not any(s.startswith("BP ") for s in dbg.sent), "refused before arming anything"
    # and in PROTECTED mode a different selector IS a different place
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
    """THE DEFECT THE MODE-WIDTH RULE WAS WRITTEN TO FIX, and it was in the first
    version of this module.

    A flat 16-bit clamp refuses essentially every interesting protected-mode address:
    `_main` in the DJGPP binary this package was built against sits at offset 0x16DF20.
    MEASURED against the real debugger, it takes a 32-bit offset and lists it back --
    `BP 0087:00012345` was accepted and printed as `BP 0087:12345`, which is also why
    the `:04X` this compares with still matches: the list prints a MINIMUM of four hex
    digits rather than exactly four.

    Its mirror is in the refusal case below: in REAL mode the same offset addresses
    nothing, and the debugger would accept it and then never fire.
    """
    # THE EXPECTED SPELLING IS WRITTEN OUT, not built with the same format spec the
    # production code uses -- that compared the code with itself and could not fail. The
    # measured claim is that the list prints a MINIMUM of four hex digits, so a
    # six-digit offset appears unpadded, and this is what that looks like.
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
        run_to(dbg, 0, 0x10000)          # Real mode: past 0xFFFF addresses nothing
    with pytest.raises(ds.Invalid, match="not a bound"):
        run_to(dbg, 0, 0, seconds=0)
    assert ds.RUN_TO_MAX == 600, "the ceiling moved; decide it deliberately and edit here"
    with pytest.raises(ds.Invalid, match="not a bound"):
        run_to(dbg, 0, 0, seconds=601)
    # IT LOOKED AT THE MACHINE (that is how it knows the mode) AND ARMED NOTHING. The
    # assertion is about the `BP`, not about silence: a refusal that had already armed
    # a breakpoint would leave one behind for the next caller to trip over.
    assert not any(s.startswith("BP ") for s in dbg.sent), dbg.sent
    assert dbg.keys == []


# ---------------------------------------------------------------------- watch()

def test_watch_eats_the_selector_choice_by_reading_the_machines_mode() -> None:
    """THE WHOLE REASON THIS IS A TOOL and not a spelling of three debugger commands.

    The same sixteen bits are a paragraph of physical memory in real mode and an index
    into a descriptor table in protected mode. The debugger accepts either command
    without comment, and the mode changes underneath a caller as their program boots --
    so the choice is made from a reading of the machine, on every call.

    THE TWO LIST ROWS ARE CAPTURED, and the protected one is here because an AUTHORED
    version of it hid a live bug through a whole review. The code expected
    `BPPMEM 00AF:6024`; the debugger prints `BPPM 00AF:00006024` -- a different keyword
    AND a different offset width -- so every protected-mode watch armed the breakpoint
    and then refused, blaming the one cause that was not it. The old fixture could not
    fail, because its row was written from the same belief as the code.
    """
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
    """A watch that was never armed and one that never fires are the same silence, and
    only one of them is a finding about the program."""
    dbg = Debugger([REAL_PANE, pane_with([])])
    with pytest.raises(ds.Invalid, match="does not list a watch"):
        watch(dbg, segment=0x0040, offset=0x006C)


def test_watch_refuses_an_address_outside_what_the_command_can_carry() -> None:
    with pytest.raises(ds.Invalid, match="segment"):
        watch(Debugger([REAL_PANE]), segment=0x10000, offset=0)
    with pytest.raises(ds.Invalid, match="offset"):
        watch(Debugger([REAL_PANE]), segment=0, offset=0x10000)


# ------------------------------------------------------------------ the tools

@pytest.fixture(autouse=True)
def clean_session() -> Any:
    dstate.STATE.session = None
    dstate.STATE.clear_running_state()      # a previous case's last stop must not skip the park
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
    """A reply from a dead session would be a reading of nothing -- and the envelope is
    asserted because an INVALID is the reply a caller reasons hardest about, and the
    one an earlier version of this server dropped the session block from."""
    reply = cast(dict[str, Any], call())
    assert reply["status"] == "INVALID"
    assert "no live session" in reply["message"]
    assert reply["session"] == {"alive": False, "running": False, "altered": False}


# What each tool PROMISES to hand back. Spelled out here so the assertion below is
# against a contract and not against whatever the code happens to return today.
# WHAT EACH TOOL MUST HAND BACK WHOLE, DERIVED FROM THE METHOD rather than listed.
#
# It was a hand-written dict, and it had already fallen behind: `step` gained `stalled`
# and `run_to` gained `bound_expired`, and neither reached this set. Since this is the
# ONLY thing asserting the server's envelope passes a session answer through without
# taking anything away (`_answer` is a straight splat), a filter dropping either field
# on the way out would have left both tiers green and no MCP caller would ever have
# seen them.
#
# `returned_key_sets` reads EACH return separately and `test_each_double_returns_...`
# holds every branch of a method to one set, so taking the first is safe and is checked
# next door rather than assumed here.
TOOL_FIELDS = {"step": set(returned_key_sets(ds.Session.step)[0]),
               # the wait's TARGET, the branch this case drives: its TIMEOUT carries no line
               "log_wait": next(set(keys) for keys in returned_key_sets(ds.Session.log_wait)
                                if "line" in keys)}
# `run_to` SPEAKS THE SHARED WORDS, so its session's account is mapped and not handed on: the
# set is the tool's own, every one of which comes from that account.
TOOL_FIELDS["run_to"] = {"verdict", "target", "ref", "stopped_at", "waited_s",
                         "target_disarmed", "control_hits", "controls", "note"}


@pytest.mark.parametrize("tool", sorted(TOOL_FIELDS))
def test_the_tools_hand_the_sessions_own_answer_back_whole(
        tool: str, tmp_path: Path) -> None:
    """The server layer adds an envelope and takes NOTHING away.

    IT IS PARAMETRISED OVER ALL THREE, because covering `step` alone leaves a gap:
    wrapping `run_to` and `watch` so they return only `{status, session}` -- every
    promised field gone -- leaves the whole contract suite green while their field sets
    are asserted in the live tier alone, which skips by default without a real
    emulator.

    Each set only means anything WHOLE: `completed` beside `running`, `arrived` beside
    `breakpoint_removed`. A tool that dropped one would leave the caller reading `ok`
    over a machine that stopped stepping three instructions ago.
    """
    # step and run_to STOP, so their reply is the enriched one (Phase 4): after the tool's
    # own reads, `_stop_reply` reads `where` and `registers` from ONE survey now
    # (`stop_survey`, decision 35), so it needs ONE more pane, not two. The store is
    # empty here (no `start`), so no watch read and no attribution survey follow. Exactly one
    # enrich pane is deliberate: a regression to two separate surveys starves the second pop
    # and reddens this, so this provisioning is itself the guard on the fold.
    enrich = [pane_with([], cs="F000", eip="0000FFF0")]
    # THE FIRST CONTACT RECORDS THE PARK: every tool's `live()` surveys a machine found at
    # the debugger once, for `last_stop` (the running-guest contract), so the three console
    # tools pay ONE pane before their own reads. Exact on purpose, like the enrich pane.
    park = [pane_with([])]
    panes = {"step": [*park, REAL_PANE, REAL_PANE, *enrich],
             # With the CONTROL `run_to` requires: two `BP`s, one list holding both,
             # the arrival, then each row looked up and deleted.
             "run_to": [*park, pane_with([]),
                        pane_with(["00. BP F000:FFF0", "01. BP F000:FFE0"]),
                        pane_with([], cs="F000", eip="0000FFF0"),
                        pane_with(["00. BP F000:FFF0", "01. BP F000:FFE0"]), pane_with([]),
                        pane_with(["00. BP F000:FFE0"]), pane_with([]), *enrich],
             "log_wait": []}[tool]
    args: dict[str, Any] = cast(dict[str, Any], {"step": {"mode": "over", "count": 1},
                            # A SHORT bound: the double's `_read` never yields, so the
                            # wait runs to the deadline. At the default 30 s this one
                            # case took 30 s -- which is also the evidence that the
                            # pre-release drain works, because before it a stale pane
                            # in the buffer ended the wait instantly.
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
    reply = cast(dict[str, Any], getattr(server, tool)(**args))
    assert reply["status"] == "ok", reply
    missing = TOOL_FIELDS[tool] - set(reply)
    assert not missing, f"{tool} dropped {sorted(missing)} on the way through _answer"


def test_where_and_registers_surveys_once_and_matches_the_two_calls() -> None:
    """Decision 35: `where_and_registers` reads where AND registers off ONE survey. This
    pins the AXIS the fold exists on -- the number of console round trips -- not just the
    values: a regression to two surveys keeps the values right and only this `sent` count
    moves. Value-equivalence is checked beside it, against the same fixture read the old
    way (a separate `where()` then `registers()`)."""
    pane = pane_with(["00. BP F000:FFF0"], cs="F000", eip="0000FFF0")
    folded = Debugger([pane])
    where, regs = ds.Session.where_and_registers(cast(ds.Session, folded))
    assert folded.sent.count(ds.NUDGE) == 1, folded.sent   # ONE round trip, the whole point

    # the same fixture read the OLD way costs two surveys, and yields the same values.
    two = Debugger([pane, pane])
    old_where = ds.Session.where(cast(ds.Session, two))
    old_regs = ds.Session.registers(cast(ds.Session, two))
    assert two.sent.count(ds.NUDGE) == 2, two.sent
    assert where == old_where and regs == old_regs


def test_where_and_registers_refuses_a_cut_pane_like_where_does() -> None:
    """It shares `where_from`, so a pane with no CPU mode is refused on THIS call site too,
    not only through `where()` -- a regression that stopped routing it through `where_from`
    would be caught here rather than sailing through with a half-read position."""
    no_mode = "ooooRegister OverviewooooEAX=00000001  ESI=00000000\r\nI-> _"
    with pytest.raises(ds.Invalid, match="no CPU mode"):
        ds.Session.where_and_registers(cast(ds.Session, Debugger([no_mode])))


def test_a_virtual_8086_pane_is_no_mode_a_position_is_read_in() -> None:
    """The debugger names a virtual-8086 stop `VM86`, and no reader here addresses through it:
    both surveys refuse the pane rather than read it as real mode or as a selector, which is
    what a trace from such a stop, or ending at one, meets."""
    vm86 = REAL_PANE.replace(" Real\r\n", " VM86\r\n")
    assert vm86 != REAL_PANE
    with pytest.raises(ds.Invalid, match="no CPU mode") as e:
        ds.Session.where(cast(ds.Session, Debugger([vm86])))
    assert e.value.code == "unexpected_answer"
    with pytest.raises(ds.Invalid, match="no CPU mode") as e:
        ds.Session.where_and_registers(cast(ds.Session, Debugger([vm86])))
    assert e.value.code == "unexpected_answer"


def test_a_protected_mode_watch_may_be_wider_than_sixteen_bits() -> None:
    """THE SAME WIDTH DEFECT AS `run_to`, ON THE SIBLING CALL SITE, which had no case.

    The clamp was corrected on one and left standing on the other, so a watch on a DJGPP
    static past 0xFFFF was refused outright while a breakpoint on one was not. Both go
    through `offset_ceiling` now, and this is what stops the copy coming back.
    """
    dbg = Debugger([PROT_PANE, pane_with(["00. BPPM 00AF:00236024 (00)"], mode="Pr32")])
    got = watch(dbg, segment=0x00AF, offset=0x236024)
    assert got["command"] == "BPPM 00AF:236024", got
    assert got["armed"] == "BPPM 00AF:00236024", got


def test_a_step_that_moves_the_machine_reports_that_it_moved() -> None:
    """THE CONTRACT TIER NEVER SAW THE MACHINE MOVE, and that was the gap.

    Every other step case reuses one pane, so `after` was indistinguishable from
    `before` and returning `before` for both passed the whole suite -- the only
    assertion on their content anywhere was in the live tier. `moved` is a separate
    field from `completed` on purpose: `completed` counts keys sent to a machine that
    was still there afterwards, which is NOT proof the instruction executed, and an
    instruction can legitimately leave EIP where it was.
    """
    dbg = Debugger([pane_with([], cs="F000", eip="0000FFF0"),
                    pane_with([], cs="F000", eip="0000E05B")])
    got = step(dbg, mode="over", count=1)
    assert cast(dict[str, str], got["before"])["eip"] == "0000FFF0"
    assert cast(dict[str, str], got["after"])["eip"] == "0000E05B", got
    assert got["moved"] is True and got["completed"] == 1


def test_a_step_that_did_not_move_says_so_instead_of_claiming_success() -> None:
    """The mirror, and the reason `moved` exists: a key the debugger ignored leaves a
    pane that parses perfectly, so `completed` alone cannot tell it from a real step."""
    dbg = Debugger([REAL_PANE, REAL_PANE])
    got = step(dbg, mode="over", count=1)
    assert got["completed"] == 1 and got["moved"] is False


def test_the_mode_token_is_read_off_the_register_pane_and_not_out_of_the_log() -> None:
    """`Real` IS AN ORDINARY ENGLISH WORD, and the Output pane is a scrolling LOG.

    That pane carries DOSBox-X's own messages and the guest's E9 lines, and it is
    painted BELOW the register pane -- so an unanchored `\\b(Real|Pr16|Pr32)\\b` taking
    the LAST match deliberately preferred the one region of the screen that can say
    anything at all. A `Pr32` machine whose log mentions the word answered `Real`, and
    `watch` then sent `BPM` where the machine wanted `BPPM`.
    """
    noisy = PROT_PANE + "DEBUG: CPU switched to Real mode\r\nI-> _"
    assert dcons.parse_mode(noisy) == "Pr32"
    assert where(Debugger([noisy]))["mode"] == "Pr32"


def test_where_refuses_a_pane_that_carries_no_position() -> None:
    """AN EMPTY STRING IS NOT AN ADDRESS. `_survey` asks whether the pane came back at
    all, which any single register satisfies, so a cut delta carrying `EAX=` and a mode
    token produced `{'cs': 'F000', 'eip': '', ...}` -- and `run_to` then died on
    `int('', 16)`, a ValueError escaping as a traceback from the method whose entire job
    is saying where the machine is."""
    partial = ("EAX=00000000  SS=0000 Real\r\n"
               "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    with pytest.raises(ds.Invalid, match="no CS and no EIP"):
        where(Debugger([partial]))


def test_a_partial_pane_is_refused_rather_than_called_a_running_machine() -> None:
    """`where()` REFUSES FOR THREE REASONS AND ONLY ONE MEANS "RUNNING".

    A machine that is stopped, whose pane came back but named no CPU mode, was reported
    by `run_to` as a machine still running, its breakpoint armed and unremovable. Every
    clause of that was false. Catching the base class widened one observed cause into
    three unobserved ones, in the reply a caller reasons hardest about.
    """
    modeless = ("EAX=00000000  CS=F000   EIP=0000FFF0\r\n"
                "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), modeless])
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        run_to(dbg, 0xF000, 0xFFF0)

    stepper = Debugger([pane_with([]), modeless])
    with pytest.raises(ds.Invalid, match="names no CPU mode"):
        step(stepper, mode="over", count=2)


def test_an_arrival_reports_the_time_it_actually_waited() -> None:
    """`waited_s` SAYS WHAT HAPPENED, never what it was asked for: an arrival after a
    fraction of a second under a 30-second bound reporting `waited_s: 30.0` is a
    fabricated number of the right shape, which no reader can tell from a measured one.

    The bound here is deliberately large so that echoing it would be unmistakable.
    """
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="F000", eip="0000FFF0"),
                    armed, pane_with([])],
                   # TWO chunks: the FIRST is eaten by the pre-release drain, which is
                   # the point of that drain -- the read-back leaves a whole register
                   # pane in the buffer and without the flush it ended the wait
                   # instantly. The second is what arrives after F5.
                   reads=["", pane_with([], cs="F000", eip="0000FFF0")])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=30)
    assert got["verdict"] == "TARGET", got
    assert cast(float, got["waited_s"]) < 5.0, got


def test_the_right_offset_in_the_wrong_segment_is_not_an_arrival() -> None:
    """THE OTHER HALF OF THE CONJUNCTION. The existing fixture stops at the right
    segment and the wrong offset, so dropping the offset test goes red and dropping the
    SEGMENT test did not. In a DPMI guest the same offset under a different selector is
    an ordinary event, and this reported it as arrival."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]),
                    pane_with([], cs="0087", eip="0000FFF0")])
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "OTHER_STOP", got
    assert "0087" in str(got["note"]), got


def test_a_breakpoint_that_survives_bpdel_is_reported_as_still_there() -> None:
    """THE MODULE'S ONE RULE, on the one field that makes a claim: never believe an ok.

    `BPDEL` is sent and the listing afterwards still holds the breakpoint. Claiming
    `breakpoint_removed: True` here would leave the caller certain a persistent
    breakpoint is gone when it will stop their next `resume`.
    """
    armed = pane_with(["00. BP F000:FFF0"])
    dbg = Debugger([pane_with([]), armed,
                    pane_with([], cs="F000", eip="0000FFF0"),
                    armed, armed])          # still listed after BPDEL
    got = run_to(dbg, 0xF000, 0xFFF0)
    assert got["verdict"] == "TARGET", got
    assert got["breakpoint_removed"] is False, got
    assert "STILL in the debugger's list" in str(got["note"]), got


# ------------------------------------------------------------------------ e9_wait

# TWO INSTRUMENTATION LINES, verbatim from a real guest run. The prefix is
# what `E9_LINE` matches on, and a line that merely QUOTES one does not count -- which
# is why the third string below is here.
E9_BOOT = ("Bochs port E9h: [+   0.000] BOOT  . start version=1.0 gfx=1024x768x8 "
           "rate=44100 buf=2048")
E9_HELP = "Bochs port E9h: [+  19.715] UI    . info_open base=HELP"
E9_QUOTED = "make: src/loudness.c: info_open base=HELP is not an E9 line"


class LogSession:
    """A session whose only job is to own a growing logfile.

    It drives the REAL `e9_wait` -- the method reaches for `launch.logfile`, `alive()`
    and nothing else -- so what is exercised is the polling, the already/waited split
    and the three refusals, not a reimplementation of them.
    """

    def __init__(self, log: Path, *, alive: bool = True) -> None:
        self.launch = SimpleNamespace(logfile=log, watched=False)
        self._alive = alive

    def alive(self) -> bool:
        return self._alive

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return False            # a guest that is running, the wait's ordinary case

    def state(self) -> dict[str, object]:
        return {"alive": self._alive, "altered": False}

    def _e9_text(self) -> str:
        return ds.Session._e9_text(cast(ds.Session, self))

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ds.Session.e9_new_since(cast(ds.Session, self), offset)

    def _log_text(self) -> str:
        return ds.Session._log_text(cast(ds.Session, self))

    def log(self, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
        return ds.Session.log(cast(ds.Session, self), pattern, limit, channel)

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
    """THE MARK IS WHAT MAKES "DID THE GUEST REACT" ANSWERABLE. A line matching the pattern
    is ALREADY in the log; a wait taken from a mark set after it must NOT report it -- that
    stale line is history, and reading it as the reaction to an event posted after the mark
    is the false success `send_keys` verification exists to refuse. The control beside it:
    the same wait from mark 0 finds it at once, so the mark is what made the difference."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    assert mark == log.stat().st_size          # a BYTE position, not a line index
    # THE EXPIRY IS A TIMEOUT, and its count names the region it examined: with a mark it
    # is "since the mark", never "in the log altogether", which would be false by exactly
    # the lines before it.
    expired = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert expired["verdict"] == "TIMEOUT", expired
    assert re.search(r"0 since the mark at byte \d+", str(expired["note"])), expired
    assert "altogether" not in str(expired["note"])
    assert s.e9_wait("info_open", seconds=0.3)["already"] is True    # the control
    # A line written AFTER the mark is the answer, and it is the first one after the mark,
    # not the earlier one: the stale line stays invisible to a marked wait.
    later = "Bochs port E9h: [+  40.000] UI    . info_open base=ABOUT"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{later}\n")
    got = s.e9_wait("info_open", seconds=0.3, mark=mark)
    assert got["line"] == later and got["lines_total"] == 1, got
    assert got["lines_examined"] == 1 and got["since_mark"] == mark, got
    # A mark on a log that does not exist yet is 0: the whole future log is "after" it.
    assert LogSession(tmp_path / "absent.log").e9_mark() == 0


def test_a_mark_inside_a_half_written_line_does_not_serve_that_line_as_new(
        tmp_path: Path) -> None:
    """THE MARK IS THE FILE'S SIZE, and a writer flushes mid-line, so the mark can land
    inside a line begun BEFORE it. That line belongs to before the mark: its tail must not
    be served as a new match (it is a fragment, not an instrumentation line), and the first
    WHOLE line after it is the answer. Both directions: with only the tail appended the wait
    expires; with a real line after it, that line and only that line is found."""
    log = tmp_path / "guest.log"
    half = "Bochs port E9h: [+   1.000] ACT   . key_cue"        # begun, not finished
    log.write_text(f"{E9_BOOT}\n{half}", encoding="utf-8")
    s = LogSession(log)
    mark = s.e9_mark()
    with log.open("a", encoding="utf-8") as fh:
        fh.write("_a=0 b=-1 on=0\n")                             # the tail of the old line
    assert s.e9_wait("key_cue_a", seconds=0.3, mark=mark)["verdict"] == "TIMEOUT"
    whole = "Bochs port E9h: [+   2.000] ACT   . key_cue_a=1 b=-1 on=1"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{whole}\n")
    got = s.e9_wait("key_cue_a", seconds=0.3, mark=mark)
    assert got["line"] == whole and got["lines_total"] == 1, got


def test_a_line_that_already_happened_is_answered_at_once(tmp_path: Path) -> None:
    """THE HALF A WAITING TOOL CANNOT DO. Between launching the emulator and asking, the
    event may already have gone past; a tool that only waited would sit out its whole
    bound and then report that it never happened -- false, and expensive by exactly the
    length of the bound."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["already"] is True
    assert got["line"] == E9_HELP
    assert got["waited_s"] == 0.0, "it waited for something it already had"


def test_the_first_occurrence_is_the_answer_and_the_count_says_there_were_more(
        tmp_path: Path) -> None:
    """"When did it happen" is answered by the FIRST time, not the most recent one --
    and `lines_total` is what tells a caller who wanted the latest that there is one."""
    log = tmp_path / "guest.log"
    first = "Bochs port E9h: [+   1.000] UI    . info_open base=HELP"
    log.write_text(f"{first}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == first and got["lines_total"] == 2


def test_a_line_that_arrives_during_the_wait_is_the_other_answer(
        tmp_path: Path) -> None:
    """THE WAIT REALLY WAITS. The log holds instrumentation but not the pattern, a
    writer appends the match a moment later, and the reply must say `already: False`
    with a measured `waited_s` -- otherwise "it was already there" and "I saw it
    arrive" are the same reply and the tool has only one semantic."""
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
    # BOTH SIDES. A lower bound alone is satisfied by `round(seconds, 3)` -- the bound
    # ASKED FOR, which is the exact defect `run_to` shipped and has a row for -- and by
    # seconds-since-boot. The upper bound is what tells a measurement from an echo.
    assert 0.3 <= cast(float, got["waited_s"]) < 5.0, got
    assert cast(int, got["lines_examined"]) >= 2, got


def test_a_bound_that_expires_is_invalid_and_says_what_it_examined(
        tmp_path: Path) -> None:
    """NOT AN EMPTY ANSWER. A caller who asked "wait for X" and got "no lines" cannot
    tell "X did not happen in this window" from "there was nothing to match against",
    and this package refuses to print the same thing for both. The TIMEOUT's note names the
    channel, the count and the duration, so the reader can see it really watched."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("never_going_to_appear", seconds=0.4)
    assert got["verdict"] == "TIMEOUT" and "a bound that expired" in str(got["note"]), got
    assert got["lines_examined"] == 1 and got["arrived_during"] == 0, got


def test_only_a_session_with_no_channel_at_all_is_refused_outright() -> None:
    """ONE of `e9`'s three refusals survives a WAIT, and the other two must not.

    A session with no logfile has no channel and waiting cannot create one. But a log
    that does not EXIST yet, and a log with no instrumentation IN it, are the ordinary
    state of a guest that has just been resumed -- and lifting `e9`'s guards wholesale
    made this tool unable to wait for the guest's FIRST trace. MEASURED before the fix:
    `start`, `resume`, `e9_wait("BOOT")` refused in 0.000s against a five-second bound,
    for a line that arrived 0.3s later. The canonical flow could not work.
    """
    with pytest.raises(ds.Invalid, match="without a logfile"):
        LogSession(cast(Path, None)).e9_wait("x", seconds=1)


def test_it_waits_for_the_guests_very_first_trace(tmp_path: Path) -> None:
    """THE CASE THAT COULD NOT PASS BEFORE. The log does not exist when the wait begins
    -- no file, no instrumentation, nothing -- and the trace arrives afterwards. That is
    `start` then `resume` then "wait for the boot line", which is the flow this tool
    exists for."""
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
    """THE WORST DEFECT THIS TOOL HAD, and it produced BOTH failures at once.

    A log written through ordinary stdio ends MID-LINE between flushes -- the steady
    state while a writer is producing, not a rare race. The old reader split the file by
    lines and indexed by line NUMBER, so a fragment consumed an index and matched
    `E9_LINE`, which only anchors the prefix. Two consequences, both measured against
    the shipped code: the fragment was returned AS the guest's trace with its payload
    missing, and when the rest arrived the line count did not grow, so the completed
    line was NEVER TESTED -- the caller got "a bound that expired" for a line sitting in
    the file that `e9` could find.
    """
    log = tmp_path / "guest.log"
    partial = "Bochs port E9h: [+  19.715] UI    . info_open"
    log.write_text(f"{E9_BOOT}\n{partial}", encoding="utf-8")   # NO trailing newline

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
    # NOT the fragment, and NOT a timeout: the whole line, once.
    assert got["line"] == f"{partial} base=HELP", got
    assert got["already"] is False, got


def test_a_log_rewritten_underneath_the_wait_is_read_from_its_start(tmp_path: Path) -> None:
    """A log rewritten SHORTER than the wait's offset describes a file that no longer exists,
    so the wait reads the new one from its start: a line written to it after the rewrite is
    found, where keeping the offset would see nothing more for the rest of the bound."""
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
    """`alive()` consulted ONCE, while composing the refusal at the end, lets a session
    that died two tenths of a second in burn the whole bound (up to ten minutes, with
    the server's lock held) before saying so, and then advise asking again with a longer
    bound, which is the one thing that cannot help a dead emulator."""
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
    """An expiry reporting the log's TOTAL under the words "went past" makes a wait in
    which NOTHING happened, on a log carrying earlier traces, say "40 instrumentation
    line(s) went past" -- read by anyone diagnosing a silent guest as a live channel.
    They are different facts and both are given."""
    log = tmp_path / "guest.log"
    # FORTY-ONE, and the `\b`, because `match=` is an unanchored `re.search`: with 40
    # lines and no word boundary, the broken message "40 instrumentation line(s)
    # arrived DURING" CONTAINS "0 instrumentation line(s) arrived DURING", so the case
    # written to stop a fabricated count could not tell 0 from 40. Demonstrated across
    # 0/10/20/30/40/100/500 -- every one matched. A non-multiple of ten also shows a
    # truncation bug that a round number would hide.
    log.write_text(f"{E9_BOOT}\n" * 41, encoding="utf-8")
    began = time.monotonic()
    got = LogSession(log).e9_wait("never_appears", seconds=0.4)
    assert re.search(r"\b0 instrumentation line\(s\) arrived DURING", str(got["note"])), got
    # AND THE BOUND IS HONOURED, which nothing checked: `deadline = began + seconds * 2`
    # left the whole tier green, in a method whose own refusal justifies its ceiling by
    # "this would sit on a line that is never going to arrive, holding the lock".
    assert 0.35 <= time.monotonic() - began < 2.0, "the bound was not the bound"


def test_the_match_count_of_a_waited_answer_is_not_hardcoded(tmp_path: Path) -> None:
    """`lines_total` was the literal 1 in the waited branch while meaning "how many matched"
    in the other -- a fabricated count of exactly the right shape, in the field the
    docstring uses to justify the design ("so a caller who wanted the latest knows there
    is one"). Seven matching lines in one burst reported 1."""
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
    """The guard is on the CHANNEL, not the content: a build log naming a source file,
    or a tool echoing a trace back, carries the words without being the thing. Here the
    quoting line contains the pattern and must not be the answer."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_QUOTED}\n{E9_BOOT}\n{E9_HELP}\n", encoding="utf-8")
    got = LogSession(log).e9_wait("info_open", seconds=2)
    assert got["line"] == E9_HELP, got


def test_e9_wait_refuses_a_wait_that_is_not_a_bound(tmp_path: Path) -> None:
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    assert ds.RUN_TO_MAX == 600, "the ceiling moved; decide it deliberately and edit here"
    for bad in (0, -1, 601):
        with pytest.raises(ds.Invalid, match="not a bound"):
            LogSession(log).e9_wait("x", seconds=bad)


def test_e9_wait_refuses_a_pattern_that_is_not_a_pattern(tmp_path: Path) -> None:
    """The caller's mistake, not the guest's, and it is named as such."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="not a usable pattern"):
        LogSession(log).e9_wait("(unclosed", seconds=1)


# ----------------------------------- the four the FIRST adversarial review found
#
# Each was LIVE and the suite above was green over it. Three share one shape: a guard
# whose MESSAGE described a defence the guard did not implement.


def test_an_interrupt_breakpoint_is_confirmed_from_the_list_not_from_the_word() -> None:
    """The acknowledgement was `"reakpoint" not in out`, and `BPLIST_HEADER` is
    `"Breakpoint list:"`, which CONTAINS it -- while `NUDGE` IS `BPLIST`, so every
    register read in this class puts that header on the scrolling Output pane. After
    any other tool had run, the check could not fail. MEASURED in a live session:
    the delta for this very call carried seven of those headers.

    The rows are CAPTURED, both forms, from This debugger:
        00. BPINT 21
        01. BPINT 31 AH=00
    """
    # The pane the old check would have accepted: the header is there (so `reakpoint`
    # is in the text) and the list holds NOTHING.
    dbg = Debugger([pane_with([])])
    with pytest.raises(ds.Invalid, match="not in the debugger's breakpoint list"):
        ds.Session.breakpoint_interrupt(cast(ds.Session, dbg), 0x31, 0x00)
    # THE CONTROL, so this is not a guard that refuses everything: the real row is
    # accepted, in both of the forms the debugger prints.
    ds.Session.breakpoint_interrupt(
        cast(ds.Session, Debugger([pane_with(["00. BPINT 31 AH=00"])])), 0x31, 0x00)
    ds.Session.breakpoint_interrupt(
        cast(ds.Session, Debugger([pane_with(["00. BPINT 21"])])), 0x21)
    # AND THE AH IS PART OF THE IDENTITY, not decoration: an arming on a DIFFERENT AH
    # is not the one that was asked for, which a prefix match would have accepted.
    with pytest.raises(ds.Invalid, match="not in the debugger's breakpoint list"):
        ds.Session.breakpoint_interrupt(
            cast(ds.Session, Debugger([pane_with(["00. BPINT 31 AH=05"])])), 0x31, 0x00)


def test_arming_a_breakpoint_marks_the_session_altered() -> None:
    """`altered` said false on a session holding breakpoints. The debugger arms a code
    breakpoint by writing a trap byte into memory -- `run_to`'s own non-arrival note
    says so -- and `watch` never removes its own. Only `set_register` set the flag, so
    a `read_memory` over a watched address could return the trap as program bytes under
    a header stating the session had not been written to."""
    dbg = Debugger([pane_with(["00. BP F000:FFF0"]), pane_with(["00. BP F000:FFF0"]),
                    pane_with([])])
    # READ INTO LOCALS RATHER THAN ASSERTING ON THE ATTRIBUTE. mypy narrows a member
    # expression and does not re-widen it across a call, so `assert dbg.altered is
    # False` makes every later check on it unreachable -- and an unreachable assertion
    # is a test that cannot fail, which is the thing this whole review is about.
    before = dbg.altered
    run_to(dbg, 0xF000, 0xFFF0)
    assert (before, dbg.altered) == (False, True), "run_to armed and did not say so"

    # TWO PANES, and the first version of this gave one and died on pane starvation:
    # `watch` reads the CPU MODE before it arms and the LIST after, which is two round
    # trips. The double is a queue, so a case that miscounts them fails for a reason
    # that has nothing to do with the property it names -- the hazard its own docstring
    # spells out. Built the way the neighbouring watch cases build theirs.
    w = Debugger([REAL_PANE, pane_with([BPMEM_ROW])])
    w_before = w.altered
    watch(w, segment=0x0040, offset=0x006C)
    assert (w_before, w.altered) == (False, True), "watch armed and did not say so"


def test_a_breakpoint_row_glued_to_the_text_before_it_is_still_a_row() -> None:
    """`BREAKPOINT_ROW` was the last of the three pane patterns anchored to the start
    of a line, and this debugger's repaints glue content with no newline. The bad
    direction is not the refusal: `run_to`'s cleanup reads `removed = not any(...)`,
    so an unreadable row is reported as `breakpoint_removed: true` for a breakpoint
    still sitting in the machine."""
    glued = ("ooooOutputoooooooooooooo" + dcons.BPLIST_HEADER + "\r\n"
             "----------------00. BP F000:E05B\r\nI-> _")
    got = dcons.parse_breakpoints(glued)
    assert [b["entry"] for b in got] == ["BP F000:E05B"]
    assert [b["index"] for b in got] == ["00"]
    # AND IT STILL DOES NOT EAT THE REGISTER PANE'S OWN NUMBERS, which is what the
    # `^` was doing the work of: these two appear in every real repaint.
    assert dcons.parse_breakpoints("pfi=0.992628993\r\n92.464754300\r\ncc=0RUN\r\n") == []


def test_moved_is_asked_per_step_and_not_of_the_endpoints() -> None:
    """A two-instruction loop returns to where it started, so comparing only the ends
    reported `moved: false` -- which this method's docstring says means a key the
    debugger IGNORED -- for two steps that both moved. `stalled` is the number that
    actually names a swallowed keystroke."""
    dbg = Debugger([pane_with([], eip="0000FFF0"), pane_with([], eip="0000FFF2"),
                    pane_with([], eip="0000FFF0")])
    got = step(dbg, mode="over", count=2)
    assert got["completed"] == 2
    assert got["moved"] is True, "both steps moved; only the endpoints agreed"
    assert got["stalled"] == 0
    # THE MIRROR, and it is the case `moved` exists for: the debugger ignores the keys
    # and every position is the same one.
    idle = Debugger([pane_with([], eip="0000FFF0"), pane_with([], eip="0000FFF0"),
                     pane_with([], eip="0000FFF0")])
    still = step(idle, mode="over", count=2)
    assert still["moved"] is False and still["stalled"] == 2


# ------------------------------------------------- the verification pass
#
# Six defects in this surface that the review above CLAIMED and this pass
# MEASURED. Each case below reproduces the measurement that confirmed one of them,
# against a double rather than against an emulator, so it can go red on every commit.


class Dies(Debugger):
    """A debugger whose emulator dies after a given number of `alive()` questions.

    IT IS A PROGRAM AND NOT A CONSTANT, deliberately. `Debugger`'s `alive` is a fixed
    flag, and a fixed flag cannot express the state these two defects live in: a
    session that was up when the machine was released and gone by the next poll. A
    double that cannot change over a run cannot exercise a bug whose cause is that
    something changed.
    """

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
    """`run_to` must not poll a corpse for its entire bound with the server's lock held.

    Against a session dead from the moment the machine is released, `alive()` consulted
    only once the loop is over spends the whole bound before saying anything -- on a
    `RUN_TO_MAX` of 600s that is ten minutes in which `status` cannot even be asked, for
    a session that has already gone.

    `e9_wait` carries the same check and says so in a comment; the two are one shape.
    """
    # Two panes: the `where()` before arming, and the read-back of the breakpoint list.
    # `alive()` is asked twice by then; the third question is the loop's first.
    # IT DIES PART-WAY THROUGH, which is the state the defect lives in. With
    # `dies_after=0` the session is a CONSTANT dead one -- nothing before the loop calls
    # `alive()` at all (`_survey` only evaluates it inside the f-string of a
    # `NotStopped` it does not raise on the success path), so the very first question is
    # the loop's, and hoisting the check OUT of the loop entirely keeps such a case
    # GREEN while restoring the whole defect.
    dbg = Dies([pane_with([]), pane_with(["00. BP F000:E05B"])], dies_after=3)
    with pytest.raises(ds.Invalid, match="the emulator is GONE"):
        run_to(dbg, 0xF000, 0xE05B, seconds=30.0)
    # THE READ COUNT IS THE ASSERTION, not the wall clock. A timing threshold on a
    # shared machine is a flake; "it did not sit through its bound" is a fact about the
    # loop, and at 0.25s a poll a 30s bound is 120 of them. One read is the pre-release
    # drain and three are the loop's, so five is a ceiling with room and nowhere near
    # a bound that was sat through.
    assert dbg.polls <= 5, (
        f"it read {dbg.polls} times on a session that died three questions in; the "
        f"death is meant to be noticed in the loop, not when the bound runs out")
    assert dbg.alive_calls >= 3, (
        f"`alive()` was asked {dbg.alive_calls} times: the check is not in the loop")


def test_an_announced_stop_that_is_not_one_keeps_the_run_going_to_its_bound() -> None:
    """A repaint arrives at once and the nudge after it finds no register pane: the
    machine still runs, so the wait LISTENS ON for the rest of its bound, sending nothing
    (no second release), and only the bound interrupts it. Ending there instead would
    hand back a TIMEOUT for a run given no time at all."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "", "",
                    pane_with([], cs="0837", eip="0000004C")],
                   # THE FIRST ENTRY IS EATEN BY THE DRAIN: `run_to` calls `_read(0.0)`
                   # before releasing the machine.
                   reads=["", "EAX=00000001 EIP=0000FFF0\r\n"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.5)
    assert got["verdict"] == "TIMEOUT", got
    assert dbg.keys.count(ds.RUN_KEY) == 1, "released once: the announcement sent nothing"
    assert cast(float, got["waited_s"]) >= 0.5, got


def test_a_stop_announced_only_by_the_prompt_is_seen_by_the_wait() -> None:
    """THE REGISTER LABELS ARE NOT RESENT ON A STOP, and the wait was reading them.

    `resume` measured it and says so in its docstring: this debugger repaints only the
    cells that changed, so a machine that stops again redraws its code pane while `EAX=`
    and the rest stay where they were and are never sent -- the prompt agreed with the
    machine 12/12, the pane 6/12. `run_to`'s wait was the pane reading. MEASURED over the
    MCP transport on a real-mode guest with an INT 21 breakpoint armed beside the
    target: the machine stopped within milliseconds and the reply came back after the
    FULL 60 s bound: a timeout for a machine that had been sitting at the debugger the whole
    time.
    """
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")],
                   # The first read is eaten by the drain before the machine is released;
                   # the second is what a stop actually sends: a redrawn code pane and
                   # the prompt, with no register label anywhere in it.
                   reads=["", "0837:004C  CD21  int 21  " + dcons.PROMPT + " _"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=2.0)
    assert got["verdict"] == "OTHER_STOP", got
    assert cast(float, got["waited_s"]) < 1.0, (
        f"waited_s is {got['waited_s']}: the wait sat out its bound over a stop that "
        f"was announced on its first read")
    assert "something else got there first" in str(got["note"]), got["note"]


def test_a_prompt_split_across_two_reads_is_still_heard() -> None:
    """The carry's prompt term, which nothing else exercises: `EIP_CARRY` alone is wider
    than the prompt today, so the `len(PROMPT)` half of `STOP_CARRY` is a passenger until
    a register name shrinks -- and a passenger with no test is a term that can be deleted
    green. The split falls INSIDE the prompt, the only split that can lose it."""
    noise = "the code pane, redrawn, and nothing that looks like a register label "
    assert len(noise) > dcons.STOP_CARRY, "the fixture must be wider than the carry"
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")],
                   reads=["", noise + dcons.PROMPT[:-1], dcons.PROMPT[-1:] + " _"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=2.0)
    assert got["verdict"] == "OTHER_STOP", got
    assert cast(float, got["waited_s"]) < 1.0, got


def test_a_stop_elsewhere_read_after_the_bound_is_another_stop_not_a_timeout() -> None:
    """A stop the wait never heard is still found at rest afterwards: the bound ran out,
    the machine did not, and nobody here stopped it, so it is OTHER_STOP and nothing was
    interrupted."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "OTHER_STOP", got
    assert "BREAK" not in dbg.sent, dbg.sent
    assert "something else got there first" in str(got["note"]), got["note"]


def test_a_bound_that_really_expired_is_a_timeout() -> None:
    """THE GREEN BESIDE THE RED: the same bound with the machine still running is the
    TIMEOUT, so the case above cannot pass over a verdict that never changes."""
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "",
                    pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "TIMEOUT", got
    assert "the 0.05 s bound ran out and the run was interrupted" in str(got["note"])


def test_the_wait_scans_the_new_text_and_not_the_whole_terminal_again() -> None:
    """`parse_registers(seen)` over an accumulating `seen` is quadratic in the wait.

    MEASURED on the same regex before the fix: 100 polls cost 115 ms, 200 cost 458,
    400 cost 1,917 and 800 cost 7,983 -- four times the cost for twice the polls --
    against 15 ms for the fresh-only form, all of it inside the server's lock. It is
    the defect `e9_wait` measured on its side at 12.7 ms a poll and fixed.

    THE ASSERTION IS THE SCANNED LENGTH AND NOT THE CLOCK. A timing threshold on a
    shared machine is a flake, and the property is not "it is fast": it is that what
    the loop looks at does NOT GROW with how long it has been waiting.
    """
    chunk = "EAX=00000000 EBX=00000000\r\n" * 20
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]), "", pane_with([])],
                   reads=[""] + [chunk] * 200)      # the first is eaten by the drain
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
    # `STOP_CARRY` is what the loop slices by; `EIP_CARRY` is only one of its terms. And
    # `watched` records nothing on a poll whose text carries the prompt: that check comes
    # first and short-circuits the parse, so a prompt-bearing `chunk` would leave
    # `seen_lengths` empty and the first assertion above would fire, not this one.
    assert max(seen_lengths) <= len(chunk) + dcons.STOP_CARRY, (
        f"the loop scanned up to {max(seen_lengths)} characters for a "
        f"{len(chunk)}-character read: it is re-reading what it already read")


def test_a_register_split_across_two_reads_is_still_found() -> None:
    """THE MIRROR of the case above, and the reason the fix is a CARRY rather than a
    plain "scan only the new part".

    A read is cut wherever the pipe happened to be, so `EIP=00001` can arrive in one
    poll and `000` in the next. Scanning each chunk alone would miss a match the
    accumulating version found -- trading a cost defect for a correctness one, which
    is a worse trade in the direction this package refuses.
    """
    # THE FIRST READ IS LONGER THAN THE CARRY, and the split is deep inside the token.
    # The first version read `"some noise EI"` -- THIRTEEN characters against a carry of
    # 36 -- so `fresh[-EIP_CARRY:]`, `fresh[:EIP_CARRY]` and `fresh` were all the same
    # string, and the case could not tell a TAIL carry from a HEAD one nor notice the
    # width shrinking. MEASURED: `carry = fresh[:EIP_CARRY]` and `EIP_CARRY = 2` were
    # both green over it, and the constant's own comment says a stale value would fail
    # by "a match silently missed rather than anything red".
    #
    # AND THE SPLIT FALLS INSIDE `EIP=` ITSELF, which is the ONLY split that can lose a
    # match. `REGISTER`'s value group is `+`, so `EIP=0000E05` already matches on its
    # own and the tail arriving next poll costs nothing -- a fixture split in the VALUE
    # therefore pins neither the carry's width nor its direction, which is how the
    # first repair of this case stayed green on both breaks.
    noise = "some entirely unremarkable terminal noise that goes on a while "
    assert len(noise) > dcons.EIP_CARRY, "the fixture must be wider than the carry"
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:E05B"]),
                    pane_with([], eip="0000E05B")],
                   reads=["", noise + "EIP=", "0000E05B more\r\n"])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=5.0)
    assert got["verdict"] == "TARGET", got
    # `waited_s` IS THE DISCRIMINATING ASSERTION, not the verdict. With no carry the loop
    # sits out its bound and `where()` then pops a pane showing the machine AT the target,
    # so the verdict comes out TARGET either way. Deleting this line as redundant would
    # turn the row that names this case into a blind spot.
    assert cast(float, got["waited_s"]) < 1.0, got


def test_an_address_is_never_composed_out_of_two_repaints() -> None:
    """`parse_registers` is last-wins PER REGISTER, so a delta holding an old whole
    pane above a CUT one yields a `CS`/`EIP` pair that neither repaint holds.

    MEASURED before the fix: `where()` answered `{'cs': '0087', 'eip': '00012345'}`
    for a machine no repaint ever showed there, the `missing` check could not see it
    because both keys were present, and `run_to` turned it into `arrived: True`.
    """
    whole = ("ooooRegister Overviewoooo"
             "EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 Pr32\r\n"
             "EBX=00000000  EDI=00000000  CS=0087   EIP=00099999  C0 Z0\r\n")
    cut = "EAX=00000005  EIP=00012345\r\n"
    dbg = Debugger([whole + cut + "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _"])
    with pytest.raises(ds.Invalid, match="carries no CS"):
        where(dbg)
    # THE GREEN BESIDE IT: one whole pane still answers, or this passes over a `where()`
    # that refuses everything.
    ok = Debugger([pane_with([], mode="Pr32", cs="0087", eip="00012345")])
    assert where(ok) == {"cs": "0087", "eip": "00012345", "mode": "Pr32"}


def test_the_last_pane_is_the_answer_when_a_delta_carries_two_whole_ones() -> None:
    """AND THE OTHER HALF, which the refusal above does not cover: when BOTH repaints
    are whole, the newest is the position -- the pane scrolls, so the older one is
    history and answering with it would be a stale address of the right shape."""
    old = pane_with([], mode="Pr32", cs="0087", eip="00001000")
    new = pane_with([], mode="Pr32", cs="0087", eip="00002000")
    assert dcons.parse_last_pane(old + new)["EIP"] == "00002000"
    assert dcons.parse_last_pane(old)["EIP"] == "00001000"


def test_steps_already_taken_are_named_when_the_position_cannot_be_read() -> None:
    """`step` caught `NotStopped` only, so a pane naming no CPU mode -- a PLAIN
    `Invalid` -- escaped whole and said nothing about what had already happened.

    MEASURED before the fix, against a double that steps four times and then hands
    back a partial pane: five keystrokes had reached the machine and the caller was
    told about none of them. A step is IRREVERSIBLE (this debugger has no un-step), so
    that leaves the machine in a position neither side can name.

    IT STILL REFUSES. A reading that could not be made is not an answer, and turning
    this into a reply would have `step` claiming a position it just failed to read.
    What is asserted is that the refusal CARRIES the irreversible part.
    """
    modeless = ("EAX=00000000  CS=F000   EIP=0000FFF4\r\n"
                "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _")
    dbg = Debugger([pane_with([], eip="0000FFF0"),      # the `before`
                    pane_with([], eip="0000FFF1"),      # step 1
                    pane_with([], eip="0000FFF2"),      # step 2
                    modeless])                          # step 3: unreadable
    with pytest.raises(ds.Invalid) as caught:
        step(dbg, mode="over", count=10)
    said = str(caught.value)
    assert "names no CPU mode" in said, said
    # THE COUNT IS THE KEYSTROKES SENT, and it must equal what really went out. An
    # adversarial pass caught this reporting `completed` instead -- one FEWER, because
    # `completed` only rises after the position is confirmed -- which under-states the
    # irreversible damage, the one direction this message may not err in.
    assert f"{len(dbg.keys)} `over` keystroke(s) of 10 had ALREADY gone" in said, said
    assert "of which 2 were CONFIRMED landed" in said, said
    assert "F000:0000FFF0" in said, said
    # AND THE KEYSTROKES REALLY WENT OUT: three were sent and the third is the one whose
    # result could not be read.
    assert len(dbg.keys) == 3, dbg.keys


class DyingLog(LogSession):
    """A guest that writes its exit trace ON ITS WAY OUT and is gone by the next poll.

    THE ORDER IS THE WHOLE POINT, so this is a program and not a flag. `e9_wait`'s loop
    asks `alive()` FIRST and reads LAST, so the window that loses a line is exactly the
    one between the final read and the death -- which cannot be expressed by a session
    that is either alive or dead for the whole run.
    """

    def __init__(self, log: Path, *, write_after: int, line: str) -> None:
        super().__init__(log)
        self.polls = 0
        self.write_after = write_after
        self.line = line
        self.log_path = log       # `log` is the session's reader, not a file
        self.gone = False

    def alive(self) -> bool:
        return not self.gone

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        # THE READ ANSWERS FIRST, and only then does the guest write and die. Getting
        # this backwards is what made the first version of this double useless: it
        # wrote the line and the SAME read handed it back, so the case returned through
        # the ordinary match path and the death path -- the thing it is named for --
        # never ran. MEASURED: with the fix's final read deleted, the case stayed GREEN.
        got = super()._e9_since(offset, channel)
        if self.polls == self.write_after:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            self.gone = True
        return got


def test_the_guests_last_line_is_read_before_a_death_is_reported(
        tmp_path: Path) -> None:
    """The canonical wait -- for a guest's EXIT trace -- failed exactly on the line it
    was waiting for.

    MEASURED before the fix: the line was sitting unread in the log at the instant
    `e9_wait` refused, `e9` on the same log found it, and the refusal's own sentence
    ("Nothing more will be written to this log") is precisely why the missing read
    mattered -- that was the last chance to read what already was.
    """
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    exit_line = "Bochs port E9h: [+   9.000] PERF  . exit code=0"
    got = DyingLog(log, write_after=2, line=exit_line).e9_wait("exit", seconds=5)
    assert got["line"] == exit_line, got
    assert got["already"] is False


def test_a_death_with_nothing_in_the_log_is_still_a_refusal(tmp_path: Path) -> None:
    """THE GREEN'S RED. Without it the case above passes over an `e9_wait` that never
    refuses on a dead emulator at all, which would replace a missed line with a wait
    that hangs on a corpse."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match="the emulator is GONE"):
        DyingLog(log, write_after=2, line="nothing to match here").e9_wait(
            "exit", seconds=5)


class LateLog(LogSession):
    """A guest that writes AFTER the last poll of the bound but before the deadline.

    IT BURNS THE REST OF THE BOUND ITSELF rather than trusting the arithmetic of
    `E9_POLL` against `seconds`. The first version wrote the line and let the loop go
    round again, so the ORDINARY match path answered and the expiry path -- the thing
    this exists to exercise -- never ran; MEASURED, deleting the fix's final read left
    the case GREEN. Sleeping past the deadline inside the read makes the next loop
    check certainly fail, which is a property of the double rather than of how fast the
    machine happens to be.
    """

    def __init__(self, log: Path, *, line: str, burn: float) -> None:
        super().__init__(log)
        self.polls = 0
        self.line = line
        self.log_path = log       # `log` is the session's reader, not a file
        self.burn = burn
        self.wrote = False

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super()._e9_since(offset, channel)
        if self.polls >= 2 and not self.wrote:
            # Written after this read handed its answer back, and then the bound is
            # spent: the loop leaves on the clock without ever having looked for it.
            self.wrote = True
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(self.line + "\n")
            time.sleep(self.burn)
        return got


def test_a_line_written_in_the_tail_of_the_window_is_not_lost_to_the_clock(
        tmp_path: Path) -> None:
    """The loop leaves on the DEADLINE, so up to a whole `E9_POLL` of the guest's
    output had never been looked at when the refusal was composed. The window is
    small and what it holds is exactly the line being waited for."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    late = "Bochs port E9h: [+   3.000] PERF  . audio play=1"
    sess = LateLog(log, line=late, burn=0.4)
    got = sess.e9_wait("audio", seconds=0.25)
    assert got["line"] == late, got
    assert got["already"] is False


def test_an_expired_bound_with_nothing_matching_is_still_a_refusal(
        tmp_path: Path) -> None:
    """THE OTHER GREEN'S RED, for the expiry path: a final read that ANSWERED whatever
    it found would turn every expired bound into a match."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    got = LateLog(log, line="Bochs port E9h: [+   3.000] UI    . nothing",
                  burn=0.4).e9_wait("audio", seconds=0.25)
    assert got["verdict"] == "TIMEOUT" and "nothing matched" in str(got["note"]), got


# ------------------------- what the LATER adversarial review found in the fix
#
# The first `parse_last_pane` ruled that "a pane cannot name the same register twice",
# so a REPEAT was where the next repaint began. An auditor broke it in BOTH directions
# in one reading, and both are below. The rule is now anchored on the pane's own banner,
# which is a MEASURED marker rather than an inference from names.

# The banner every repaint carries, rendered the way this terminal draws it.
BANNER = "oooo" + dcons.PANE_HEADER + "oooooooooooooooooooo"


def pane_fragment(names: list[str], mode: str = "", **values: str) -> str:
    """A piece of a register pane, DERIVED from `REGISTER_NAMES` rather than written.

    The order is the one MEASURED off a real debugger (three consecutive surveys, 15
    hits each, all distinct, same order). It is derived because the hand-written double
    in this file emits NINE registers ending at `EIP`, so every cut it can express lands
    BEFORE `EIP` -- exactly the region where the old rule behaved correctly, which is
    why a green suite could not see either defect below.
    """
    out = []
    for n in names:
        out.append(f"{n}={values.get(n, '00000000')}")
        # THE MODE TOKEN SITS AT THE END OF THE `SS=` LINE and nowhere else -- `CPU_MODE`
        # anchors on `SS=[0-9A-F]{4}` followed by it. A fragment that put it anywhere
        # else parsed as no mode at all, so the case meant to exercise the CS/EIP
        # refusal tripped the mode refusal instead and asserted the wrong thing.
        if n == "SS" and mode:
            out.append(f"{mode}\r\n")
    return "  ".join(out) + "\r\n"


REAL_ORDER = ["EAX", "ESI", "DS", "ES", "FS", "GS", "SS", "EBX", "EDI", "CS", "EIP",
              "ECX", "EBP", "EDX", "ESP"]


def test_two_disjoint_fragments_never_compose_one_address() -> None:
    """A stale TAIL and a fresh HEAD that share no register name.

    The old rule saw no repeat, merged them, and returned all fifteen with `EIP` from
    one repaint and `CS` from the other -- MEASURED `{'CS': '0087', 'EIP': '00012345'}`
    with `missing == []`, which is verbatim the wrong answer `parse_last_pane` was
    written to prevent. `parse_mode` answered from the fresh half, so `where()` handed
    back a complete, well-formed position that no repaint ever showed.
    """
    tail = REAL_ORDER[REAL_ORDER.index("EIP"):]          # EIP ECX EBP EDX ESP
    head = REAL_ORDER[:REAL_ORDER.index("EIP")]          # EAX ... CS
    stale = pane_fragment(tail, EIP="00012345")
    fresh = BANNER + pane_fragment(head, mode="Pr32", CS="0087", SS="008F")
    got = dcons.parse_last_pane(stale + fresh)
    assert got.get("CS") == "0087", got
    assert "EIP" not in got, (
        f"an EIP survived from a repaint the fresh banner is below: {got}. That is the "
        f"composed address this function exists to refuse")
    # AND THE CALLER REFUSES, which is the point: a short pane beats a false one.
    dbg = Debugger([stale + fresh + "ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\nI-> _"])
    with pytest.raises(ds.Invalid, match="carries no EIP"):
        where(dbg)


def test_a_whole_repaint_behind_a_stale_tail_is_still_read() -> None:
    """THE MIRROR, and the half a refusal-only fix would have hidden.

    The old rule reset at the fresh `EIP`, throwing away the fresh `CS` it had read
    moments earlier from the SAME repaint -- so `where()` refused a delta whose last
    repaint was complete and unambiguous. That is a regression against `parse_registers`
    and it fires on the LAST FIVE of the fifteen cut positions, which is exactly where
    the pane is most likely to be cut.
    """
    stale = pane_fragment(REAL_ORDER[REAL_ORDER.index("EIP"):], EIP="00099999")
    fresh = BANNER + pane_fragment(REAL_ORDER, mode="Pr32", CS="0087",
                                   EIP="00012345", SS="008F")
    got = dcons.parse_last_pane(stale + fresh)
    assert len(got) == len(REAL_ORDER), got
    assert (got["CS"], got["EIP"]) == ("0087", "00012345"), got


def test_a_headerless_fragment_above_the_last_repaint_is_refused() -> None:
    """The third case, and the reason the rule is header-PLUS-no-repeat rather than the
    header alone: a newer fragment carrying no banner sits on top of the last whole
    pane, and nothing can say which repaint each value came from."""
    whole = BANNER + pane_fragment(REAL_ORDER, CS="0087", EIP="00012345", SS="008F")
    newer = pane_fragment(["EAX", "EIP"], EIP="0000DEAD")
    assert dcons.parse_last_pane(whole + newer) == {}


def test_a_delta_with_no_banner_at_all_is_not_a_repaint() -> None:
    """No banner means no complete repaint arrived, and assembling one from fragments is
    the composition this refuses. `{}` rather than a plausible mapping."""
    assert dcons.parse_last_pane(pane_fragment(REAL_ORDER, CS="0087")) == {}


def test_a_refusal_mid_run_says_the_breakpoint_is_still_armed() -> None:
    """`run_to` guarded `where()` with `except NotStopped` alone, so a pane naming no
    CPU mode -- a PLAIN `Invalid` -- escaped the method whole.

    The caller then got an exception with none of `waited_s`, `bound_expired`, or the
    sentence saying a trap byte is sitting in the guest. MEASURED before the fix:
    `Invalid` out of `run_to` with `altered` True and a `BP` left where it will stop the
    next `resume` at an address nobody recorded.

    IT STILL REFUSES. A pane naming no CPU mode is NOT a running machine, and reporting
    it as one is the defect the case above this one pins. What is asserted is that the
    refusal CARRIES the irreversible part.
    """
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
    """`_write` and `_collect` sat OUTSIDE `step`'s try, so an `Invalid` from `_read`
    (the drain thread dropped bytes) escaped with no step count -- the same defect the
    new handler exists to close, reached by another door, and MORE likely over a long
    step run than a modeless pane."""
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


# ------------------------------------------------------- resume(): the `ok`
#                                                          that examined nothing
#
# A `resume` that sends the key and answers `{"status": "ok"}` has looked at NOTHING,
# with its own delta in front of it. An `ok` for a machine still sitting at the debugger
# is byte for byte the `ok` for one that ran, and what that produces downstream is a
# guest that appears hung: a working session gets closed over exactly that reading.
#
# WHAT THESE CASES REST ON. The tempting reading is that the delta "carries the
# debugger's register pane"; it does not -- see the fixtures at the top of this file. So
# the discriminator is the PROMPT, and the two directions below are what hold it there.

def test_a_resume_that_left_the_machine_at_the_debugger_says_so() -> None:
    """The HALTED direction, and the fixture is the one that kills the pane reading.

    `RESUME_HALTED` is a real delta off a machine that stopped again, and
    `parse_registers` finds NOTHING in it. A `resume` built on the register pane
    answers `halted: False` here -- which is the defect this card is about, rebuilt
    inside its own fix.
    """
    dbg = Debugger([pane_with([], cs="0814", eip="00000112")],
                   deltas=[RESUME_HALTED])
    got = resume(dbg)
    assert got["halted"] is True, got
    assert got["stopped_at"] == {"cs": "0814", "eip": "00000112", "mode": "Real"}
    assert not dcons.parse_registers(RESUME_HALTED), (
        "the fixture stopped being the one that discriminates: a delta the pane "
        "reading can answer cannot show that the pane reading is wrong")


def test_a_resume_that_let_the_machine_go_says_that_instead() -> None:
    """The RUNNING direction. Same tool, opposite answer, off a captured delta.

    THE SECOND ASSERTION IS THE COST PROPERTY AND ALSO A CORRECTNESS ONE: nothing is
    sent to a machine that is running. This debugger's console swallows a command then
    with no error anywhere, so a read-back on this path would buy a settle for an
    answer it could not get.
    """
    dbg = Debugger([], deltas=[RESUME_RAN])
    got = resume(dbg)
    assert got["halted"] is False, got
    assert got["stopped_at"] is None, got
    assert dbg.sent == [], (
        f"a running machine was asked {dbg.sent}: the console swallows it")


def test_the_two_outcomes_differ_in_the_field_that_answers_the_question() -> None:
    """THE CASE THE WHOLE CARD REDUCES TO. Before the fix these two replies were equal
    in every field a caller could read, which is why `ok` meant nothing."""
    halted = resume(Debugger([pane_with([], cs="0814", eip="00000112")],
                             deltas=[RESUME_HALTED]))
    ran = resume(Debugger([], deltas=[RESUME_RAN]))
    assert halted["halted"] != ran["halted"], (halted, ran)


def test_the_address_is_read_back_and_is_not_scavenged_off_the_delta() -> None:
    """THE IDENTITY AXIS ON THE ADDRESS, and its fixture is the adversarial one.

    `RESUME_HALTED_GLUED` is the delta where `parse_registers` DOES answer -- with
    `CS=081401080100FF91C81440026`, the repainted digits of several fields run
    together. So a `stopped_at` scavenged out of the delta would not be empty here, it
    would be confidently wrong, and of exactly the right shape to be passed on.

    The address must be the one the READ-BACK produced, and it is a different value
    from anything in that delta.
    """
    glued = dcons.parse_registers(RESUME_HALTED_GLUED)
    assert glued.get("CS") == "081401080100FF91C81440026", (
        f"the fixture no longer glues: {glued}")
    dbg = Debugger([pane_with([], cs="F000", eip="0000DAC6")],
                   deltas=[RESUME_HALTED_GLUED])
    got = resume(dbg)
    assert got["stopped_at"] == {"cs": "F000", "eip": "0000DAC6", "mode": "Real"}
    assert dbg.sent == [ds.NUDGE], dbg.sent


def test_a_prompt_that_came_back_over_an_unreadable_pane_is_still_halted() -> None:
    """`halted` and `stopped_at` answer DIFFERENT questions, so one survives the other.

    The prompt came back, so the machine IS at the debugger; the repaint that followed
    was cut, so `where()` refuses rather than composing an address out of two panes.
    Reporting `halted: False` here would be the card's defect again, and REFUSING would
    invent a verdict: stopping again is what breakpoints are for.
    """
    got = resume(Debugger(["EAX=00000000  SS=0000 Real\r\n"], deltas=[RESUME_HALTED]))
    assert got["halted"] is True, got
    assert got["stopped_at"] is None, got


def test_the_key_goes_once_and_this_tool_never_sends_it_again() -> None:
    """NO RETRIES, in both directions, asserted rather than promised in prose.

    A tool that resumed until something worked would be guessing how many stops a
    configuration has, and that number is not a thing it can know.
    """
    ran = Debugger([], deltas=[RESUME_RAN])
    resume(ran)
    halted = Debugger([pane_with([], cs="0814", eip="00000112")],
                      deltas=[RESUME_HALTED])
    resume(halted)
    assert ran.keys == [ds.RUN_KEY], ran.keys
    assert halted.keys == [ds.RUN_KEY], halted.keys


class Wire(RealPositionReaders):
    """A debugger whose ONLY fake is `_read`, so the REAL `_collect` runs.

    `Debugger` stubs `_collect`, which is right for every case above: those are about
    what `resume` DOES with a delta, and scripting the delta is how they stay
    deterministic. What it leaves unexecuted is `_collect` ITSELF -- and that function
    decides what `halted` MEANS. `halted` is a marker found in whatever `_collect` handed
    back, so the window `_collect` collects over IS the window the marker has to arrive
    in, and `settle=1.0, timeout=8.0` are not two cosmetic literals.

    Without this class the whole body of `_collect` is executed by NO contract test: the
    tool every session begins with rests on a function the contract tier never runs.

    THE SCRIPT IS ONE ENTRY PER POLL, and `""` is a poll that found nothing. An empty
    poll SLEEPS for the slice it was given, because the settle is measured in wall
    clock: a poll that returned instantly would make the loop spin and measure nothing,
    which is the double getting wrong precisely the property it exists to reproduce.
    """

    def __init__(self, script: list[str], panes: list[str] | None = None) -> None:
        self.script = list(script)
        self.panes = list(panes or [])
        self.polls = 0
        self.keys: list[bytes] = []
        self.sent: list[str] = []
        self._peek_carry = ""     # `command()` folds the drained leftover into it
        self._raw_tail, self._raw_reads = "", 0    # what the real `_read` keeps for `_collect`

    # THE REAL KEY ROUND TRIP, which the real `command` types through.
    _keys = ds.Session._keys

    def _read(self, seconds: float = 0.0) -> str:
        self.polls += 1
        chunk = self.script.pop(0) if self.script else ""
        if not chunk:
            time.sleep(seconds)
        return chunk

    def _write(self, data: bytes) -> None:
        # THE REAL RELEASE HOOK, because a run key DRAINS the terminal before it
        # goes out, and `resume`'s `screen` is defined by that drain: a double that skipped
        # it would hand the residue of the previous op to `_collect` and read a `halted` off
        # it, which is the defect and not the contract.
        ds.Session._release(cast(ds.Session, self), data)
        self.keys.append(data)

    def command(self, text: str, **_: object) -> str:
        self.sent.append(text)
        return self.panes.pop(0) if self.panes else ""

    # THE POINT OF THIS CLASS: the real one, not a stub. Everything else here exists to
    # give it something to poll.
    def _collect(self, settle: float, timeout: float, early: bool = False) -> str:
        return ds.Session._collect(cast(ds.Session, self), settle, timeout, early)


def wired(script: list[str], panes: list[str] | None = None,
          residue: str = "") -> dict[str, object]:
    """`residue` is what the terminal still held from BEFORE the F5 -- the repaint of the
    console op that ran just before it in the same call -- and the drain a release performs
    pops it first, so `script` is one entry per poll AFTER the key, as before."""
    return ds.Session.resume(cast(ds.Session, Wire([residue, *script], panes)))


def test_a_leftover_of_the_previous_command_is_not_read_as_this_ones_reply() -> None:
    """MEASURED on a real guest (a DJGPP program): `run_to` removed its target
    and then its control with two `BPDEL` in a row, and the list read back after the second
    still showed the control, while `BPLIST` typed by hand right after showed it gone. The
    reply had been decided by a LEFTOVER: bytes the previous command's repaint delivered
    after its own collect had gone quiet were sitting in the drain, `_collect` took them as
    this command's first bytes, the settle timer started on them, and the real listing
    arrived after the loop had already stopped. So `command()` drains what the terminal
    still holds BEFORE it types, and only what arrives after the keystroke is the reply.
    The script models exactly that: a stale listing already waiting, two empty polls while
    the debugger works, then the real (empty) listing."""
    stale = ("ooooOutputoooo" + dcons.BPLIST_HEADER + "\r\n-----\r\n00. BP 00A7:5D730\r\n"
             + dcons.PROMPT + " _")
    fresh = dcons.BPLIST_HEADER + "\r\n-----\r\n" + dcons.PROMPT + " _"
    wire = Wire([stale, "", "", fresh])
    delta = ds.Session.command(cast(ds.Session, wire), "BPLIST", settle=0.05, timeout=2.0)
    assert "00A7:5D730" not in delta, delta
    assert dcons.parse_breakpoints(delta) == [], delta
    assert wire.keys == [b"BPLIST\r"], "the drain never types anything"


# What `Session.resume` waits for the stop's repaint, as it passes `_collect`.
RESUME_SETTLE_S = 1.0


def test_a_prompt_that_arrives_after_the_settle_is_not_seen_and_halted_reads_false() -> None:
    """THE LIMIT `halted` INHERITS FROM `_collect`, executed rather than described.

    `_collect` returns at the FIRST settle-long silence after the first byte, not at
    the end of its timeout. So a guest that prints something and goes quiet closes the
    window, and a breakpoint that fires afterwards repaints a prompt nobody is reading:
    `resume` answers `halted: False` for a machine that IS at the debugger.

    This is a LIMIT PINNED, not a property wanted. It is here because it was invisible:
    the reply is `ok`, `alive` is true, every later tool works, and the only symptom is
    a caller who believes the machine is running. Whoever changes the window will turn
    this red, and that is the point -- the message says what moved.
    """
    # One byte, then silence for longer than `resume`'s settle, and the prompt after it: the
    # settle closes on the poll that fills it, so five polls past that is a machine that
    # stopped too late to be seen, whatever the collect's slice.
    script = ["COMMAND.COM\r\n"] + [""] * (round(RESUME_SETTLE_S / ds.COLLECT_SLICE_S) + 5) + [
        dcons.PROMPT + " _"]
    got = wired(script, panes=[pane_with([], cs="0814", eip="00000112")])
    assert got["halted"] is False, got
    assert got["stopped_at"] is None, got
    assert dcons.PROMPT not in cast(str, got["screen"]), (
        "the prompt reached the delta after all, so this case is no longer about the "
        f"window closing early: {got['screen']!r}")


def test_the_same_prompt_inside_the_window_is_seen() -> None:
    """THE CONTROL BESIDE IT, and the ONLY difference is when the prompt arrives.

    Without this, the case above proves nothing: `halted: False` and "this harness
    never reads a prompt at all" are the same output. Same script shape, same double,
    prompt at the third poll instead of the sixteenth.
    """
    script = ["COMMAND.COM\r\n", "", dcons.PROMPT + " _"]
    got = wired(script, panes=[pane_with([], cs="0814", eip="00000112")])
    assert got["halted"] is True, got
    assert got["stopped_at"] == {"cs": "0814", "eip": "00000112", "mode": "Real"}


def test_a_terminal_that_never_said_anything_costs_the_whole_timeout() -> None:
    """THE OTHER HALF OF THE WINDOW: the settle timer starts at the FIRST byte.

    `_collect`'s quiet branch is `elif got:`, so with nothing ever arriving there is no
    silence to measure and the loop runs to its deadline. That is the cost the docstring
    calls "none at all on the ordinary one": the read-back is free there, the collect is
    not, and a guest that says nothing pays the full bound.
    """
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
    """Through the SERVER, because the envelope is where a field gets dropped."""
    # A HALT is a stop, so resume returns the enriched reply: after the halt delta it reads
    # `where` and `registers`, hence the two extra register panes here.
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
    assert got["stopped_at"] == {"cs": "0814", "eip": "00000112", "mode": "Real"}
    assert got["screen_delta"] == RESUME_HALTED, got
    assert "omitted" not in got and "how" not in got
    # decision 13: the halt now also carries the registers, the (empty) watch list, the
    # attribution and the E9 summary -- none of which displaced the base fields above.
    assert got["registers"] and got["watches"] == [] and "attributed" in got["attribution"]
    assert got["e9"]["available"] is False    # this fake owns no logfile


# ------------------------------------- a wait on a stopped machine ends at once

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
    """MEASURED on a real guest: a breakpoint left by another session stopped the
    guest while a `start(plan=)` was running, and `e9_wait("PERF  . audio", 40)` sat out the
    whole 40 s to answer "bound expired ... the emulator is still running" -- about a
    machine that had been parked at the debugger throughout. A stopped guest writes
    nothing, so the wait refuses at once and says the machine is stopped. What the log
    already holds is still answered first (`already`), stopped or not."""
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
    """`lines_before`: the count of lines between the start of the window (the mark) and the
    match, so a reaction that arrived after a post can be told from one that was there
    first. Both branches: found at once, and found after a wait."""
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


# ------------------------------------------------------------ the console
#
# Both are about text the terminal offered at a moment nobody was reading it FOR that
# purpose: a stop's prompt consumed as part of a typed command's reply, and a
# console op's repaint left behind for the next release to read as its own.


class Console(Wire):
    """A `Wire` whose `command`, `at_debugger` and stopped flag are the REAL ones.

    `Wire` fakes `command` as a queue of panes, which is right for the resume cases above
    and blind to the race: there the repaint a stop paints has to pass through `command`'s own
    `_collect`, because that is where it was lost. Born running, like a guest a key is
    being sent to.
    """

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
    """THE RACE ITSELF (measured). A key was posted by serial while a
    breakpoint was about to fire. The pre-check typed a NUDGE at the running guest; the
    stop landed while that command was collecting its reply, so the prompt the stop prints
    was consumed AS the NUDGE's reply -- which carried no register pane, hence `NotStopped`
    -- and nothing marked the machine stopped. Every passive peek afterwards found an empty
    terminal, the wait sat out its bound and said "the emulator is still running", and the
    NEXT `send_keys` refused for a machine that had been parked throughout. The prompt is
    the debugger saying it has the keyboard, wherever it is read."""
    con = Console([RESUME_HALTED])          # the stop's repaint: a prompt, no register pane
    with pytest.raises(ds.NotStopped):
        con.where()
    assert con.at_debugger() is True, "the prompt went past inside `command` and was not counted"
    assert con.stop_count == 1, con.stop_count
    assert not dcons.parse_registers(RESUME_HALTED), (
        "the fixture stopped discriminating: with a register pane `where()` would answer")


def test_a_release_forgets_the_prompt_a_passive_peek_carried() -> None:
    """The carried tail of a passive peek is the last `STOP_CARRY` characters it saw, kept
    so a prompt split across two peeks is still found. A chunk that ENDS with the prompt
    leaves the whole prompt in the carry, and after a release the next peek reassembled it
    out of the carry alone and reported a running machine as stopped. A run key forgets the
    carry along with the flag: whatever was offered before it is about the stop being left.
    """
    seen_stop = "0814:00000112 CD21int  21\r\n" + dcons.PROMPT     # a chunk ending at the prompt
    assert dcons.PROMPT in seen_stop[-dcons.STOP_CARRY:], "the fixture must fit the carry"
    # After the F5 one line of guest output, then silence: the collect closes on its settle
    # instead of running to its whole timeout for a case that is about the carry.
    con = Console([seen_stop, "COMMAND.COM\r\n", "", "", ""])
    assert con.at_debugger() is True
    got = ds.Session.resume(cast(ds.Session, con))       # F5; no prompt after it
    assert got["halted"] is False, got
    assert con.at_debugger() is False, "the carry from before the release resurrected the prompt"


class LateStopLogSession(LogSession):
    """Says "running" to the first `running_answers` questions and "stopped" from then on:
    the stop that lands between the loop's last look and the clock running out."""

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
    """THE EXPIRY'S OWN WORDS. The loop asks at every poll, so a stop the loop sees
    refuses at once; a stop that lands AFTER the last poll and before the clock reached the
    expiry, which said "The emulator is still running" -- about the PROCESS -- while the
    debugger had the machine. One poll per wait here (`E9_POLL` longer than the bound), so
    the first answer is the loop's and the second is the expiry's. The control beside it is
    the same shape with the machine really still running, which keeps the old words."""
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
    """Measured: a plan of `breakpoint_clear` + `breakpoint_at` + `resume`
    brought "Breakpoint list:" seven times in the resume's `screen`, because the delta began
    where the last READ left the terminal and the console ops before it had left their
    repaints unconsumed. The worse half: a console op's repaint ENDS with the debugger's
    prompt, so a machine the F5 let run read as `halted: true` off text painted before the
    key. The terminal is drained before the key goes out, as `run_to` always did."""
    residue = "Breakpoint list:\r\n0814:0100 BP\r\n" + dcons.PROMPT + " _"
    ran = wired(["COMMAND.COM\r\n", "", ""], residue=residue)
    assert ran["halted"] is False, ran
    assert "Breakpoint list:" not in cast(str, ran["screen"]), ran["screen"]
    # THE CONTROL: the same prompt arriving AFTER the key is still a halt, so the drain
    # took the residue and not the answer.
    halted = wired(["", dcons.PROMPT + " _"], panes=[pane_with([], cs="0814", eip="00000112")],
                   residue=residue)
    assert halted["halted"] is True, halted
    assert "Breakpoint list:" not in cast(str, halted["screen"]), halted["screen"]


class StopsAfterWriting(LogSession):
    """Writes the awaited line and parks itself at the debugger inside ONE poll interval:
    the reaction logged by the key's handler, and the breakpoint on that handler firing
    right after -- both between two looks at the log."""

    def __init__(self, log: Path, *, line: str) -> None:
        super().__init__(log)
        self.line, self.polls, self.parks = line, 0, False

    def at_debugger(self) -> bool:
        return self.parks

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        self.polls += 1
        got = super()._e9_since(offset, channel)
        if self.polls == 2:                 # the first is the "already" look; this is the loop's
            with self.launch.logfile.open("a", encoding="utf-8") as f:
                f.write(self.line + "\n")
            self.parks = True
        return got


def test_a_reaction_written_just_before_the_stop_is_found_not_refused(tmp_path: Path) -> None:
    """THE LAST LOOK BEFORE A STOPPED REFUSAL (an audit found it). The loop checks the
    debugger FIRST and reads the log LAST, so a guest that logs the reaction and then hits
    the breakpoint on its handler, inside one poll, was refused as "no line could arrive: a
    stopped guest writes nothing" while `e9` on the same log found the line. The GONE and
    expiry paths took that last read already; the stopped path takes it too."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    line = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1"
    got = StopsAfterWriting(log, line=line).e9_wait("key_cue_a", seconds=5)
    assert got["line"] == line and got["already"] is False, got
    # THE CONTROL: the same session with nothing written before the stop still refuses.
    with pytest.raises(ds.E9Stopped, match="stopped at the debugger"):
        StopsAfterWriting(log, line="Bochs port E9h: [+   9.000] UI    . other").e9_wait(
            "key_cue_b", seconds=5)


# ------------------------------------------------------- the progress line on a bounded wait


def test_e9_wait_reports_its_progress_while_it_waits(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """A wait that says nothing and a hung server look the same from the terminal; the
    client paints a progress message live (measured by the owner's eye), so every bounded
    wait reports one: the seconds spent of the bound and what is being waited for."""
    log = tmp_path / "guest.log"
    log.write_text(f"{E9_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(mprogress, "PROGRESS_EVERY_S", 0.0)
    ticks: list[tuple[float, float | None, str]] = []
    LogSession(log).e9_wait("never", seconds=0.25,
                            progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks, "the wait reported nothing"
    # A wait measured in time has no total: a bar filling towards the bound reads as progress
    # towards failure.
    assert all(t is None and m.startswith("log_wait guest /never/") for _p, t, m in ticks)
    assert ticks[-1][0] > 0 and "0 lines arrived" in ticks[-1][2]
    # A wait answered from what the log already holds reports nothing: there was no wait.
    ticks.clear()
    LogSession(log).e9_wait("BOOT", seconds=0.25, progress=lambda p, t, m: ticks.append((p, t, m)))
    assert ticks == []


class _Listening:
    """What `await_stop` reaches for on a machine that never announces a stop."""

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


def test_run_to_hands_its_progress_to_the_stop_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the real `run_to`, not `await_stop` alone: the forwarding at the one call site
    inside `run_to` is what this pins."""
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    dbg = Debugger([pane_with([]), pane_with(["00. BP F000:FFF0"]), "",
                    pane_with([], cs="0837", eip="0000004C")])
    out = run_to(dbg, 0xF000, 0xFFF0, seconds=0.3,
                 progress=lambda p, t, m: ticks.append(m))
    assert out.get("verdict") == "TIMEOUT" and ticks and ticks[0].startswith("run_to F000:FFF0")


def test_run_to_cancelled_in_flight_is_brought_back_and_takes_its_breakpoints_with_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancelled while it waits, the run has no reply to say what it left armed, so it leaves
    nothing: the guest is brought back with `BREAK` and both breakpoints it armed are removed,
    or the caller's next `resume` stops at a place nobody named."""
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
    dbg = Cancelled([pane_with([]), both,                 # the mode, the arming read back
                     both, control_only,                  # target BPDEL, read back
                     control_only, pane_with([])])        # control BPDEL, read back
    monkeypatch.setattr(cancel, "check", check)
    with pytest.raises(asyncio.CancelledError):
        run_to(dbg, 0xF000, 0xFFF0, seconds=5, control=(0xF000, 0xE05B))
    assert dbg.breaks == 1, "the run was left in flight"
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent


class PromptInTheNudge(Debugger):
    """A machine that comes to rest between the wait giving up and the position read: the
    first nudge after the bound reads the stop's prompt and no pane, as a stop landing inside
    a typed command's own read does, and the next nudge reads the pane."""

    def command(self, text: str, **k: object) -> str:
        out = super().command(text, **k)
        if text == ds.NUDGE and out == "" and not self._at_debugger:
            self._at_debugger = True             # the prompt went past inside the read
        return out


def test_a_run_that_came_to_rest_after_the_bound_is_not_interrupted() -> None:
    """THE INTERRUPT IS GUARDED: a run found at rest after its bound is another's stop, so no
    `BREAK` reaches an idle debugger and the verdict is OTHER_STOP, never a TIMEOUT claimed for a
    stop nobody here made."""
    dbg = PromptInTheNudge([pane_with([]), pane_with(["00. BP F000:E05B"]), "",
                            pane_with([], cs="0837", eip="0000004C")])
    got = run_to(dbg, 0xF000, 0xE05B, seconds=0.05)
    assert got["verdict"] == "OTHER_STOP" and "BREAK" not in dbg.sent, (got, dbg.sent)


def test_a_rest_on_the_control_found_after_the_bound_counts_as_its_hit() -> None:
    """A control the machine is found resting on after the bound FIRED, so the run is a
    TIMEOUT with one hit, never `control_silent` with the stop sitting on the control."""
    both = pane_with(["00. BP F000:FFF0", "01. BP F000:E05B"])
    dbg = PromptInTheNudge([pane_with([]), both, "",
                            pane_with([], cs="F000", eip=CONTROL_HIT),
                            both, pane_with(["00. BP F000:FFF0"])])
    got = run_to(dbg, 0xF000, 0xFFF0, seconds=0.05, control=(0xF000, 0xE05B))
    assert got["verdict"] == "TIMEOUT" and got["control"] == {
        "at": "F000:E05B", "hits": 1, "removed": True}, got


def test_a_cancel_during_the_interrupt_at_the_bound_takes_the_breakpoints_with_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The interrupt at the bound is inside the run's cancel handling: a cancel arriving while
    `BREAK` waits for its prompt removes the breakpoints the run armed, as a cancel in flight
    does."""
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
    dbg = CancelledAtTheBound([pane_with([]), both, "",          # running at the bound
                               both, control_only, control_only, pane_with([])])
    from scry_core import cancel
    monkeypatch.setattr(cancel, "is_cancellation",
                        lambda e: isinstance(e, asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        run_to(dbg, 0xF000, 0xFFF0, seconds=0.05, control=(0xF000, 0xE05B))
    assert dbg.sent.count("BPDEL 00") == 2, dbg.sent
