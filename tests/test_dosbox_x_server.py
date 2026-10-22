"""What the MCP surface refuses, what it always says, and that it exists at all.

These are CONTRACT tests, not emulator tests: none of them launches DOSBox-X. What
they hold is the part that has to be true before one is involved.

THE STUB REPRODUCES THE CONTRACT, NOT THE CODE.  An earlier version's stub returned a
path it had not written, which is exactly what the real `memdump` wrongly did -- so
the test AGREED WITH THE BUG and the suite could not tell "the guard fired" from
"this tool never works". A double is built from what the thing PROMISES.
"""

from __future__ import annotations

import ast
import asyncio
import atexit
import dataclasses
import inspect
import itertools
import json
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest
from scry_core import declaration_rows, log_marks, media_tools, recording, screen_map
from scry_core import log_wait as core_wait
from scry_core import reply_contract as contract
from scry_core import sequence_account as account
from scry_core import steps as step_judge
from scry_core import vocabulary as vocab

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_checks as checks
import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_docs
import dosbox_inputs as inputs
import dosbox_launch as dlaunch
import dosbox_lifecycle
import dosbox_logs as dlogs
import dosbox_machine as machine
import dosbox_mcp
import dosbox_placement as placement
import dosbox_process as dprocess
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

# A `SELINFO CS` reply in the shape a DJGPP program under CWSDPMI gets, AUTHORED: no capture
# of it is kept, so it is the assumed screen, not a record. It is whole rather than reduced,
# because the property it exists to exercise is the NOISE: the debugger overlays a descriptor
# line into the REGISTER pane (`ss: b:00008240`) as well as printing the one that was asked
# for, so a
# reader that searches the screen for the first `b:` returns the STACK selector's base
# for a question about the code selector -- a wrong answer of exactly the right shape.
SELINFO_SCREEN = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo\r\n"
    "EAX=0000000A  ESI=00400000  DS=00AF   ES=00AF   FS=008F   SS=008F Pr32\r\n"
    "ECX=00000001  EBP=0000091C  ss: b:00008240 type:12 parbg    PAGEPSE IOPL3\r\n"
    "EDX=001798A6  ESP=00000760l:0000FFFF dpl : 3 10010    cc=237868    RUN\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "SelectorInfo CS:\r\n"
    "CS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 10011\r\n"
    "SelectorInfo DS:\r\n"
    "DS: b:00400000 type:13 parbg\nl:0023FFFF dpl : 3 10011\r\n"
    "I-> _")

# The same three records DOSBox-X itself wrote, reused here so a contract case and the
# converter's golden cannot drift apart about what the format is.
MEASURED_BASE = 0x00400000


def _log_wait_as_guest(self: Any, pattern: str, seconds: float, channel: str, mark: int = 0,
                       progress: ds.Progress = ds.no_progress) -> dict[str, object]:
    """A double's `log_wait`: the guest channel through its own `e9_wait`, once for the
    three doubles that only ever answer the guest."""
    got: dict[str, object] = self.e9_wait(pattern, seconds, mark=mark, progress=progress)
    return got


class FakeSession:
    """The narrowest faithful stand-in for a session: it does what the contract says.

    Deliberately NOT a stand-in for the emulator. Nothing here tests what DOSBox-X
    does; it exists so the server's own promises can be exercised without one.
    """

    def __init__(self, *, alive: bool = True, screen: str = "some screen",
                 mode: str = "Real") -> None:
        self.altered = False
        # THE MODE THE PANE NAMES, declared: the data-view screens here are real-mode, and a
        # case that measures a base off the protected-mode `SELINFO` capture says `Pr32`, or
        # the double would be two machines at once.
        self.mode = mode
        self._alive = alive
        self._screen = screen
        self.closed = 0
        # The process, as the server reads its exit off it: -15 once the double is dead.
        self.proc = SimpleNamespace(poll=lambda: None if self._alive else -15, pid=4242)
        # The launch a tool reads relative paths from (`cwd`) and the E9 channel from
        # (`logfile`); the real one is a `Launch`, and these are the two fields reached.
        self.launch = SimpleNamespace(cwd=Path("/"), logfile=None, watched=False)
        self._avi_facts: dict[tuple[str, int, int], dict[str, object]] = {}
        self.e9_calls: list[tuple[str, int]] = []
        self.log_calls: list[tuple[str, int, str]] = []
        self.console_keys: list[str] = []
        self.after_pager = "I-> _"
        self.since_marks: list[int] = []
        self.loaded: list[tuple[str, int]] = []
        # WHAT THE ADDRESS-TAKING TOOLS WERE ACTUALLY HANDED. Without this the double
        # could not tell a tool that forwards its caller's address from one that
        # forwards zero, and MEASURED, that break came back GREEN:
        # `memdump(0, 0, length, ...)` passed the whole contract tier.
        self.memdump_calls: list[tuple[int, int, int]] = []

    reap_failed = ""      # read by the `close` tool and by `start`'s failure arm
    survey_text = ""      # the last stop survey's screen: no code pane on these fixed screens
    ended_how = "none"    # how `close` ended it, read by the `close` tool beside the code

    def alive(self) -> bool:
        return self._alive

    def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
        """Found MISSING the moment the drift check stopped looking only for the
        literal spelling `live().name`. `start` calls it, and no contract case had
        ever reached it against this double because every `start` case tests a refusal
        that fires before a process exists."""
        return 0.0

    def break_in(self, seconds: float = 5.0) -> float:
        raise ds.Invalid("no_channel", "the emulator never dialled the debugger channel")

    def state_save(self, name: str, seconds: float = 20.0) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this DOSBox-X has no `SAVESTATE` debugger command")

    def stub_replaced(self) -> None:
        """No input link here to prove again."""

    def state_load(self, name: str, seconds: float = 20.0) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this DOSBox-X has no `LOADSTATE` debugger command")

    def state_list(self) -> dict[str, object]:
        return {"state_dir": "/x/save", "states": [],
                "working_slot": {"available": False, "why": "no working slot"}}

    def snapshot(self, dest: Path | None = None, seconds: float = 10.0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this session is headless: there is no window")

    def state(self) -> dict[str, object]:
        # The REAL shape. A two-key stub let the whole `altered` guarantee be
        # deleted from the real `state()` with the suite still green. The COUNT is
        # deliberately not written here: a number in a comment goes false at the
        # next field, and the test derives it from the real `state()` instead.
        return {"pid": 4242, "alive": self._alive,
                "running": self._alive and bool(getattr(self, "running", False)),
                "altered": self.altered,
                "conf": "/x/g.conf", "conf_digest": "abc123", "conf_changed_on_disk": False,
                "watched": False, "bound_s": 60, "elapsed_s": 1.0,
                "terminal_bytes_dropped": 0, "drain_alive": True, "captures": "off",
                "state_dir": "the emulator's own save/ under its working directory"}

    def command(self, text: str, **_: object) -> str:
        return self._screen

    def end_pager(self) -> str:
        self.console_keys.append("end_pager")
        return self.after_pager

    def clear_line(self) -> str:
        self.console_keys.append("clear_line")
        return ""

    def await_stop(self, began: float, deadline: float, target: str,
                   progress: ds.Progress = ds.no_progress, label: str = "") -> tuple[bool, float]:
        # The server calls it on the class with the session (`ds.Session.await_stop`), so the
        # real body runs over this double, as it does for every caller.
        return ds.Session.await_stop(cast(ds.Session, self), began, deadline, target, progress,
                                     label)

    def retrace(self, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return False, 0.0     # lands at once; run_for's own cases replay captured retraces

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return False, 0.0     # stops at once; trace's own cases replay captured logs

    def registers(self) -> dict[str, str]:
        return {"EAX": "00001234"}

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return True

    def where(self) -> dict[str, str]:
        """The real `read_memory` needs the CPU mode now (decision 38, to take the
        offset ceiling from it); this stands in with a real-mode reading, which is what
        these fixed screens are. A case needing protected mode passes `mode`."""
        return {"cs": "F000", "eip": "0000FFF0", "mode": self.mode}

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.where(), self.registers()

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        return self.where(), self.registers(), self.breakpoints()

    def read_memory(self, seg: int, off: int, mode: str | None = None) -> list[str]:
        """THE REAL METHOD, run against this double's screen.

        It is delegated rather than reimplemented because the thing worth exercising
        here is the parsing and the "is the address I asked for actually in this"
        check, and a double that reimplemented them would be agreeing with itself. It
        works because the real method reaches only for `command`, `where` and `alive`,
        all of which this stands in for.
        """
        return ds.Session.read_memory(self, seg, off, mode)  # type: ignore[arg-type]

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """THE REAL METHOD too, over this double's screen: it reaches only `read_memory`."""
        return ds.Session.read_bytes(self, seg, off, n, mode)  # type: ignore[arg-type]

    # The name-layer tools reach these on a session; the double carries them so the
    # drift check sees the surface. Cases that exercise the tools for real install a
    # richer stand-in; here they only need to EXIST and answer plausibly.
    def breakpoints(self) -> list[dict[str, str]]:
        return []

    def listing(self, command: str) -> str:
        return ""

    def intvec(self) -> str:
        return ""

    def arm_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        return {"target": f"{seg:04X}:{off:04X}", "entry": f"BP {seg:04X}:{off:04X}",
                "breakpoints": []}

    def clear_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        return {"entry": f"BP {seg:04X}:{off:04X}", "removed": True}

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        return {"entry": dcons.interrupt_row(number, ah), "removed": True}

    masks = False       # a register the debugger masks: the pane answers something else
    rom = False         # memory the write cannot change: the readback says so

    def write_memory(self, seg: int, off: int, data: bytes,
                     mode: str | None = None) -> dict[str, object]:
        self.altered = True
        self.writes = getattr(self, "writes", []) + [(seg, off, data)]
        back = bytes(len(data)) if self.rom else data
        return {"bytes_written": len(data), "readback": back.hex(), "verified": back == data}

    def set_register(self, name: str, value: int) -> dict[str, object]:
        self.altered = True
        got = "00000000" if self.masks else f"{value:08X}"
        return {"register": name.strip().lower(), "regs": {"EAX": got}, "readback": got,
                "verified": got == f"{value:08X}"}

    def breakpoint_interrupt(self, number: int, ah: int | None = None) -> str:
        return f"DEBUG: Set interrupt breakpoint at INT {number:02X}"

    def stop_at_bound(self) -> bool:
        return False             # this stub never runs, so a bound finds it at rest

    def resume(self) -> dict[str, object]:
        # THE REAL FIELD SET, and a CONSTANT rather than a reading, which is honest
        # here in a way a computed answer would not be: this double stands in for the
        # session so the SERVER's cases have something to call. What `halted` is really
        # read off is exercised next door, against captured deltas.
        return {"screen": "", "halted": False, "stopped_at": None}

    def resume_after_command(self) -> dict[str, object]:
        return self.resume()       # its confirmation is the session's, tested on the wire

    # THE DEBUGGING TRIO, as CONTRACTS rather than as behaviour. What they really do is
    # driven against a debugger double in `test_dosbox_x_debug.py`, which is where the
    # stepping loop and the read-the-list-back discipline are held to account. Here
    # they exist so the SERVER's cases -- the envelope, the lock, the refusals -- have
    # something to call, and each returns the field set its tool promises: a stub that
    # returned a bare `{}` would let a tool drop `running` or `arrived` with nothing to
    # say so.
    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        return {"mode": mode, "asked": count, "completed": count, "running": False,
                "moved": True, "stalled": 0,
                "before": {"cs": "F000", "eip": "0000FFF0", "mode": "Real"},
                "after": {"cs": "F000", "eip": "0000FFF5", "mode": "Real"}}

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        # `waited_s` IS A MEASUREMENT AND NOT THE BOUND. Echoing `seconds` straight back
        # would answer the caller with the caller's own argument under the name of an
        # elapsed time -- which is the shape of the
        # `length` defect `read_memory` was built to remove, reproduced in the stand-in
        # for a tool that got it right. A constant is honest here where the argument is
        # not: it is visibly not a measurement.
        return {"verdict": "TARGET", "target": f"{seg:04X}:{off:04X}",
                "stopped_at": {"cs": f"{seg:04X}", "eip": f"{off:08X}",
                               "mode": "Real"},
                "waited_s": 0.25, "breakpoint_removed": True, "note": "",
                "control": contract.unavailable("no control was named") if control is None else
                {"at": f"{control[0]:04X}:{control[1]:04X}", "hits": 0, "removed": True}}

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        return {"command": "BPM 0040:006C", "mode": "Real",
                "armed": "BPMEM 0040:006C", "breakpoints": [],
                "fires_on": "a CHANGE to the value"}

    def e9_mark(self) -> int:
        return 0

    stub_protocol = inputs.STUB_PROTOCOL   # announced: `require_stub` reads no log

    def send_commands(self, commands: list[bytes]) -> list[str]:
        return []

    def e9_since_mark(self, mark: int) -> list[str]:
        return ["Bochs port E9h: [+ 0.000] BOOT  . start"]

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return ["Bochs port E9h: [+ 0.000] BOOT  . start"][offset:], 1

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return self.log_wait(pattern, seconds, "guest", mark=mark, progress=progress)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        # `arrived_during` AND `lines_examined`, WHICH THE REAL METHOD RETURNS. This used
        # to drop both and invent `lines_scanned`, a name that has never existed --
        # under a comment claiming each of these "returns the field set its tool
        # promises".
        dlogs.check_channel(channel)
        return {"verdict": "TARGET", "pattern": pattern, "channel": channel,
                "line": "Bochs port E9h: [+ 0.000] BOOT  . start", "already": True,
                "lines_total": 1, "lines_before": 0, "arrived_during": 0, "waited_s": 0.0,
                "lines_examined": 1}

    def e9(self, pattern: str, limit: int) -> tuple[list[str], int]:
        self.e9_calls.append((pattern, limit))
        return ["one line"], 500          # MANY matched, ONE returned

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        dlogs.check_channel(channel)
        self.log_calls.append((pattern, limit, channel))
        self.since_marks.append(since_mark)
        return ["one line"], 500

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        self.memdump_calls.append((seg, off, length))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00" * length)   # the contract: bytes actually land
        return dest

    def captures(self) -> list[dict[str, object]]:
        # Two files, largest LAST: the text-mode boot and then the real one. That
        # ordering is the contract `capture_frame`'s default rests on.
        return [{"path": "/caps/run_000.avi", "bytes": 107194, "riff_avi": True,
                 "avi_frames": 40, "complete": True},
                {"path": "/caps/run_001.avi", "bytes": 19296742, "riff_avi": True,
                 "avi_frames": 5428, "complete": True}]

    def frame(self, at: int, dest: Path, source: Path | None = None) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG" + b"\x00" * 2000)   # the contract: an image lands
        return dest

    def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
        self.closed += 1
        self._alive = False
        self.ended_how = "quit"
        return 0

    def console_tail(self, chars: int) -> str:
        return ""

    def selector(self, reg: str) -> dict[str, int]:
        """THE REAL METHOD, run against a CAPTURED descriptor screen.

        Delegated for the same reason `read_memory` is: what is worth exercising here
        is the anchoring on this command's own echo, and a double that reimplemented it
        would be agreeing with itself. `SELINFO_SCREEN` carries the register-pane
        overlay that makes the anchoring necessary in the first place.
        """
        # SAVED AND RESTORED. `command()` returns `self._screen` for EVERY command, so
        # replacing it outright left any case that read a screen AFTER `symbols_load`
        # parsing the descriptor capture instead of its own fixture. No case does that
        # today, which makes it a trap rather than a failure -- and the kind that is
        # found by the case somebody writes next.
        was = self._screen
        try:
            self._screen = SELINFO_SCREEN
            return ds.Session.selector(self, reg)      # type: ignore[arg-type]
        finally:
            self._screen = was

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        """What the debugger would hold afterwards, INCLUDING what it already held.

        `LV` APPENDS (tests/fixtures/symbols-lv: a second load leaves both), so the
        double accumulates. A stub that returned only the last load would let the
        server claim `loaded` is the size of this load, which is the one property the
        real command does not have.
        """
        self.loaded += dsym.decode(data)
        return list(self.loaded)


@pytest.fixture(autouse=True)
def clean_session() -> Any:
    """No live session before a case, and NONE LEFT BEHIND after one.

    The teardown half was missing and its docstring claimed it anyway. It matters
    because the whole suite shares ONE process: a stub left in a module global outlives the
    file that set it.

    THE SYMBOL TABLE IS A MODULE GLOBAL TOO, and leaving it was measured doing exactly
    what this warns about: `test_find_refuses_before_anything_is_loaded` came back `ok`
    with zero matches, because an earlier case in this file had left a table installed.
    It is only ever cleared in production by `start`, `close` and a cancel that kills the
    session -- and `install()` reaches past all three.
    """
    dstate.STATE.session = None
    dstate.STATE.store = None
    dstate.STATE.session_origin = None
    dstate.STATE.conf_fingerprint = None
    dstate.STATE.last_stop.clear()
    dstate.STATE.clear_running_state()
    dstate.STATE.forget_symbols()
    dstate.STATE.cancelled = None
    dstate.STATE.maps = screen_map.Maps()   # the server's, surviving a close by design
    yield
    dstate.STATE.session = None
    dstate.STATE.store = None
    dstate.STATE.session_origin = None      # a case that set it must not stale the next one's
    dstate.STATE.conf_fingerprint = None
    dstate.STATE.last_stop.clear()          # nor date the next one's answers by its stops
    dstate.STATE.clear_running_state()      # nor leave it a queue to drain
    dstate.STATE.forget_symbols()
    dstate.STATE.cancelled = None           # nor a cancelled call's record for its first reply
    dstate.STATE.maps = screen_map.Maps()   # nor a map the next case did not load


_STORE_TMP = tempfile.mkdtemp(prefix="dosbox-x-server-test-")
atexit.register(shutil.rmtree, _STORE_TMP, ignore_errors=True)
_INSTALL_SEQ = itertools.count()


def install(**kw: Any) -> FakeSession:
    s = FakeSession(**kw)
    dstate.STATE.session = s  # type: ignore[assignment]
    # A SESSION AND ITS STORE COME TOGETHER: `start` sets both, and three breakpoint
    # tools read the store, so a double with a session and no store is a state
    # production never has. The conf key is a MONOTONIC counter, never `id(s)`: CPython
    # reuses the address of a freed object, so `id`-keyed stores over one shared file
    # made a later install inherit an earlier test's declarations.
    dstate.STATE.store = dec.DeclarationStore(
        f"install-{next(_INSTALL_SEQ)}", path=Path(_STORE_TMP) / "declarations.json")
    return s


# ------------------------------------------------------------------- the surface

def test_the_server_reports_the_name_it_is_installed_as() -> None:
    """The name it declares must equal the name it is registered as, which is also
    what namespaces its tools. That exact mismatch has happened on this fleet before:
    a server declared one name, was installed as another, and the first was by then
    the name of a different thing entirely."""
    assert server.mcp.name == "dosbox-x"


def test_a_cap_of_zero_would_lie_and_is_refused() -> None:
    """`out[-0:]` is the WHOLE string, so a cap of zero returns everything while
    declaring itself a tail. It is a `ValueError` rather than an `Invalid`: `keep` is
    never a caller's (three call sites, all literals), so a bad one is a bug in this
    module, and `Invalid` would dress it as a statement about the caller's request.

    This guard shipped with no test at all, in the commit whose own headline finding
    was that a guard nothing can turn red is not a guard."""
    for bad in (0, -1):
        with pytest.raises(ValueError, match="is not a cap"):
            dstate.delta("abcdef", bad)
    # The control: a real cap behaves, at and either side of the boundary.
    assert dstate.delta("abcdef", 6) == {
        "screen_delta": "abcdef", "screen_chars": 6, "clipped": False}
    assert dstate.delta("abcdef", 4) == {
        "screen_delta": "cdef", "screen_chars": 6, "clipped": True}


def test_a_dead_session_that_had_been_written_to_says_so_in_its_block() -> None:
    """A session whose emulator died is kept until `close`, so its `session` block still
    says it was written to, as a field: a caller who forced a register and whose emulator
    then hit its bound is never left with a refusal that hides it."""
    written = install()
    written.altered, written._alive = True, False
    got = cast(dict[str, Any], server.registers())
    assert got["code"] == "session_broken" and got["exit_code"] == -15, got
    assert got["session"]["altered"] is True and got["session"]["alive"] is False, got
    # AND THE CONTROL: the field follows the session, not the refusal.
    clean = install(alive=False)
    assert cast(dict[str, Any], server.registers())["session"]["altered"] is False
    assert clean.closed == 0


def test_a_close_that_could_not_reap_the_child_says_so_in_its_reply() -> None:
    """The field REACHING A CALLER, which is a different claim from it being set.

    `close`'s reply captures the session state BEFORE closing, and every call site
    discards the session immediately afterwards, so the reap failure is read after the
    close and said where the exit code would be: unavailable, with why. So this asserts
    the REPLY, not the object.
    """
    class Unreapable(FakeSession):
        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.reap_failed = "SIGKILL was sent and the process had not been reaped"
            self._alive = False
            return None

    dstate.STATE.session = Unreapable()  # type: ignore[assignment]
    got = cast(dict[str, Any], server.close())
    assert got["exit_code"]["available"] is False, got
    assert "SIGKILL was sent" in got["exit_code"]["why"], got
    assert "may still be on the machine" in got["summary"], got["summary"]

    # THE CONTROL: an ordinary close reports its exit code, so the assertion above is
    # about an unreaped child and not about the field's shape.
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    clean = cast(dict[str, Any], server.close())
    assert clean["exit_code"] == 0 and "reap_failed" not in clean, clean


def test_a_start_that_left_an_unreapable_emulator_says_so(tmp_path: Path) -> None:
    """The ONE path besides `close` where an unreaped child can be seen.

    `reap_failed` is set inside `close()`'s `if self.proc.poll() is None:` block, so it
    exists only when a LIVE session is closed. Two consumers were added for it in
    earlier rounds and BOTH sat on the dead branch, where `poll()` is non-None and the
    signals never run: MEASURED, closing an already-exited session leaves the field
    empty, so neither could ever fire. They are deleted.

    This arm is where it matters. `wait_ready` raising with the child still running is
    exactly the case where SIGKILL can fail to reap, and the reply is a refusal that
    would otherwise say nothing about the emulator it left behind.
    """
    class Unreapable:
        """THE FIELD IS EARNED BY BEING CLOSED, not preset.

        Its first version set `reap_failed` as a class attribute, so `if
        session.reap_failed:` fired whether or not `close()` had run -- and
        MEASURED, deleting the `session.close()` above it left the whole battery
        green, restoring the very defect the comment there names. A real `Session`
        cannot present a non-empty `reap_failed` before `close()` has run, so a
        double that does is the "state the real class cannot occupy" this commit
        convicted three earlier rounds of building.
        """

        argv = ["dosbox-x"]
        unreapable = True

        def __init__(self) -> None:
            self.reap_failed = ""
            self.closed = 0

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            raise ds.Invalid("session_broken", "the debugger never appeared")

        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.closed += 1
            if self.unreapable:
                self.reap_failed = ("SIGKILL was sent and the process had not been "
                                    "reaped 1.0s later")
            return None

    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    made: list[Unreapable] = []

    def build(_l: object) -> Unreapable:
        made.append(Unreapable())
        return made[-1]

    with mock.patch("dosbox_x_server.ds.Session", build):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert got["status"] == "INVALID"
    assert "the debugger never appeared" in str(got["message"]), got
    assert "may still be running" in str(got["message"]), got
    # THE SESSION WAS ACTUALLY CLOSED. What makes deleting that `close()` go red is
    # the DOUBLE earning `reap_failed` inside its own `close()` -- measured, this
    # assertion alone is not what fires. It is here so the call is pinned directly
    # rather than only through its side effect, and the distinction is written down
    # because a later pass reading a vaguer comment could remove the earning and keep
    # this line, which would reopen the hole.
    assert made[0].closed == 1, "the refused session was never closed"
    assert dstate.STATE.session is None

    # THE CONTROL: the same refusal from a session that WAS reaped says nothing about
    # a stray emulator, so the assertion above is about the reaping.
    class Reaped(Unreapable):
        unreapable = False

    with mock.patch("dosbox_x_server.ds.Session", lambda _l: Reaped()):
        ok = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert "the debugger never appeared" in str(ok["message"])
    assert "may still be running" not in str(ok["message"]), ok


def test_a_hung_ffmpeg_is_invalid_and_not_a_traceback(tmp_path: Path) -> None:
    """`tool()` translates only `Invalid`, so a `TimeoutExpired` out of `frame()`
    escaped raw -- losing BOTH of this module's contracts at once: the reply stops
    saying which nothing it found, and stops carrying the session's state.

    `build_check` catches the same exception twelve lines of comment deep, for the same
    reason. This one shipped without a test.

    A LIMIT SAID OUT LOUD: `dosbox_frames.subprocess` IS the stdlib module, so these
    patches are process-wide for the duration of the block. That is safe here because
    the blocks are two statements long, but this suite runs in ONE pytest process,
    which is the same hazard `clean_session`'s
    docstring is about. Keep them short."""
    def hangs(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=ds.FFMPEG_SECS)

    src = tmp_path / "cap.avi"
    src.write_bytes(b"RIFF")
    fake = SimpleNamespace(captures=lambda: [{"path": str(src)}])
    with (mock.patch("dosbox_frames.subprocess.run", hangs),
          mock.patch("dosbox_frames.shutil.which", lambda _n: "/usr/bin/ffmpeg"),
          pytest.raises(ds.Invalid, match="did not return within")):
        ds.Session.frame(fake, 0, tmp_path / "out.png")  # type: ignore[arg-type]

    # THE GREEN BESIDE IT, without which an unconditional `raise Invalid` at the top of
    # `frame()` passes -- MEASURED, it did. There is no other contract case in which
    # the real `frame()` SUCCEEDS: the double's `frame` is a stub and the only other
    # case is a second refusal.
    dest = tmp_path / "ok.png"

    argv: list[list[str]] = []

    def writes(*a: object, **_k: object) -> object:
        argv.append(list(cast("list[str]", a[0])))
        dest.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    with (mock.patch("dosbox_frames.subprocess.run", writes),
          mock.patch("dosbox_frames.shutil.which", lambda _n: "/usr/bin/ffmpeg")):
        got = ds.Session.frame(fake, 0, dest)  # type: ignore[arg-type]
    assert got == dest and dest.stat().st_size > 1000
    # THE FORMAT IS FORCED IN THE ARGV, which no test could see while every one of
    # them mocked `subprocess.run` without looking at what it was handed. Without
    # these flags ffmpeg picks the encoder from `dest`'s EXTENSION, and a frame past the end
    # then writes a frameless container at exit 0 (tests/fixtures/ffmpeg) -- a file that
    # passes every other check in the guard.
    assert argv, "the mock never saw a command line"
    assert argv[0][-5:] == ["-f", "image2", "-c:v", "png", str(dest)], argv[0]

    # AND ffmpeg EXITING 0 HAVING WRITTEN NOTHING, which is the commonest real failure
    # (a frame past the end of the capture) and was exercised by NEITHER tier: the
    # empty-output guard could be deleted with the whole battery green, and `frame()`
    # would then return a path it had not written -- the defect this file's own header
    # says the double was rebuilt to stop agreeing with.
    past_end = _ffmpeg_record("past-end-png")

    def writes_nothing(*_a: object, **_k: object) -> object:
        return SimpleNamespace(stdout="", stderr=past_end["stderr"],
                               returncode=past_end["returncode"])

    with (mock.patch("dosbox_frames.subprocess.run", writes_nothing),
          mock.patch("dosbox_frames.shutil.which", lambda _n: "/usr/bin/ffmpeg"),
          pytest.raises(ds.Invalid, match="ffmpeg exited 0 but no image")):
        ds.Session.frame(fake, 99999, tmp_path / "never.png")  # type: ignore[arg-type]

    # AND ffmpeg FAILING WHILE LEAVING A NON-EMPTY FILE, which the size check alone
    # cannot see. The exit code and stderr are a corrupt input's (tests/fixtures/ffmpeg); the
    # file it leaves is AUTHORED, since that recorded failure writes nothing: "a file exists
    # and is not empty" and "ffmpeg succeeded" are different questions either way.
    bad = tmp_path / "junk.png"
    corrupt = _ffmpeg_record("corrupt-input")

    def fails_but_writes(*_a: object, **_k: object) -> object:
        bad.write_bytes(b"not an image, but not empty either")
        return SimpleNamespace(stdout="", stderr=corrupt["stderr"],
                               returncode=corrupt["returncode"])

    # AND THE TWO REFUSALS SAY DIFFERENT THINGS, which is the point: a non-zero exit
    # is ffmpeg reporting its own failure with the reason in hand, while an empty
    # output at exit 0 is the frame-past-the-end shape where the cause is a guess.
    # Merged, the message blamed "a frame past the end" for a conversion error.
    with (mock.patch("dosbox_frames.subprocess.run", fails_but_writes),
          mock.patch("dosbox_frames.shutil.which", lambda _n: "/usr/bin/ffmpeg"),
          pytest.raises(ds.Invalid, match=f"ffmpeg exited {corrupt['returncode']}")):
        ds.Session.frame(fake, 5, bad)  # type: ignore[arg-type]

    # AND A WELL-FORMED FILE OF THE WRONG KIND at exit 0, which neither the code nor
    # the size can see. Recorded (tests/fixtures/ffmpeg): a frame past the end of a capture,
    # with `dest` named `.mp4` and the format not forced, gives a FRAMELESS CONTAINER at exit
    # 0 -- every term of the guard false, and `frame()` would return it as a still.
    # The format is forced now, so this should be unreachable through the real ffmpeg;
    # it is asserted anyway because the defect was a file that passed every test but
    # the one nobody was making.
    container = tmp_path / "container.mp4"

    recorded = (FFMPEG_FIX / "past-end-unforced.mp4").read_bytes()

    def writes_a_container(*_a: object, **_k: object) -> object:
        container.write_bytes(recorded)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    with (mock.patch("dosbox_frames.subprocess.run", writes_a_container),
          mock.patch("dosbox_frames.shutil.which", lambda _n: "/usr/bin/ffmpeg"),
          pytest.raises(ds.Invalid, match="is not a PNG")):
        ds.Session.frame(fake, 99999, container)  # type: ignore[arg-type]


FFMPEG_FIX = Path(__file__).resolve().parent / "fixtures" / "ffmpeg"


def _ffmpeg_record(case: str) -> dict[str, Any]:
    """What ffmpeg answered in one recorded case (exit code, bytes written, stderr)."""
    return cast(dict[str, Any], json.loads((FFMPEG_FIX / f"{case}.json").read_text("utf-8")))


def _tools_called_in_tests(source: str) -> set[str]:
    """The tools a test file CALLS THROUGH THE SERVER from inside its `test_*` functions.

    Only a call inside a test function is a case. A helper that starts or closes the
    session for every case calls `server.start` and `server.close` too, and counting
    those made both tools "covered" by plumbing that asserts nothing about them. And
    only `server.<tool>(...)` counts: not a Session method that shares the name, and
    not the words in a comment."""
    called: set[str] = set()
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test_"):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "server"):
                called.add(node.func.attr)
    return called


def test_the_live_case_counter_ignores_helpers_comments_and_session_methods() -> None:
    """The control for the contract below: a tool called only from a helper, only in a
    comment, or only as a Session method is NOT a live case, and one called inside a
    `test_*` function is. Without this the contract could go green on plumbing."""
    source = (
        "def start_ok():\n    return server.start()\n"
        "def test_one():\n    s = start_ok()\n    server.registers()  # server.debug()\n"
        "    s.memdump()\n    server.close()\n"
    )
    assert _tools_called_in_tests(source) == {"registers", "close"}


def test_every_tool_has_a_live_case_naming_it() -> None:
    """The "every tool has a live case" claim, GATED instead of asserted in prose.

    It was a sentence in a file header, and a sentence cannot notice a case being
    skipped: the watched-mode case skips when its placement flags are absent, so on a
    host whose display topology cannot be read the live file reports "22 passed" and a
    reader takes the whole surface as covered. A skip and a pass print the same
    thing without `-rs`.

    NO COUNT IS WRITTEN DOWN HERE. A docstring that names a number of tools, or a number
    of contract tests, is stale prose inside the gate that exists to stop prose going
    stale, which is the sharpest form the defect takes. A number in a durable text expires
    by itself and nobody re-reads it to notice; the INVARIANT (every registered tool has a
    live case) does not.

    IT RUNS AT CONTRACT TIER ON PURPOSE. This is the one assertion about live coverage
    that must not itself depend on an emulator, a display or an environment variable --
    otherwise the check meant to catch a silent skip can be silently skipped.

    THE POPULATION COMES FROM THE MCP REGISTRY, not from a list here, so a tool added
    tomorrow turns this red until it has a live case, and a list nobody maintains
    cannot quietly fall behind the surface.

    IT PARSES THE SOURCE, it does not search it, and the first version searched. That
    version's condition ended in `f".{t}(" not in text`, which subsumed its own two
    earlier clauses and made them dead -- so a tool counted as covered if ANY dotted
    call of that name appeared anywhere, including inside a COMMENT, and including
    `s.memdump(...)` on a `Session` object, which is not the tool at all. Both were
    demonstrated: deleting the only real call to the `debug` tool and leaving the words
    in a comment kept the gate green. An AST cannot be satisfied by prose.
    """
    live = Path(str(server.__file__)).parent / "tests" / "live"
    called: set[str] = set()
    for path in sorted(live.glob("test_*.py")):
        called |= _tools_called_in_tests(path.read_text(encoding="utf-8"))
    missing = sorted(set(dosbox_mcp.registered_tools()) - called)
    assert not missing, (
        f"these tools have no live case that CALLS them through the server: "
        f"{missing}. A tool with no live case is a tool whose green means nothing -- "
        f"`memdump` shipped having never once worked, with the whole contract tier "
        f"green over it")


def test_every_tool_this_server_promises_is_actually_registered() -> None:
    """MEASURED: `mcp.tool()` returns the function unchanged, so dropping the
    registration leaves every other test green while the server exposes NOTHING.
    Nothing asserted the surface existed, only that individual functions behaved."""
    expected = {"start", "status", "close", "log", "debug", "registers",
                "set_register", "write", "breakpoint_interrupt", "resume", "read_memory",
                "disassemble", "call_stack", "memdump", "find", "scan_start", "scan_filter",
                "scan_clear",
                "captures", "capture_frame", "build_check",
                "symbols_load", "symbols_find", "step", "run_to", "run_for", "log_wait",
                "breakpoint_at", "breakpoint_list", "breakpoint_clear",
                "watch_add", "watch_list", "watch_clear", "perform", "perform_export",
                "state_save", "state_load", "state_list", "snapshot",
                "send_keys", "send_mouse", "drive", "stop", "machine_map",
                "interrupt_vectors", "palette", "screen_view", "screen_signature",
                "screen_wait", "trace", "comment_add", "comment_list", "comment_delete",
                "comment_save", "comment_load", "series_capture",
                "image_diff", "series_diff", "region_track", "golden_check",
                "map_load", "map_add", "map_find", "map_save"}
    got = dosbox_mcp.registered_tools()
    assert set(got) == expected
    # NOT a length check against `expected`: `registered_tools()` reads a dict keyed
    # by name, so a duplicate cannot exist and that assertion described a state the
    # data structure cannot hold. What CAN go wrong is the registry disagreeing with
    # the module's own function list, so that is what is asked.
    assert sorted(got) == sorted(set(got)), "the registry handed back a name twice"


# ------------------------------------------------------------------- the refusals

@pytest.mark.parametrize("old", [{"mode": "headless"}, {"seconds": 60}, {"plan_wait": 5}])
def test_starts_old_words_are_refused_by_name(old: dict[str, Any]) -> None:
    """`mode`, `seconds` and `plan_wait` are `shared`, `session_seconds` and `settle_seconds`:
    the old word is the schema's refusal naming it, never a call that ran on a default (and
    never a launch: the refusal comes before the binary is looked for)."""
    res = asyncio.run(server.mcp.call_tool("start", {"conf": "/x.conf", "cwd": "/",
                                                    "session_seconds": 60, **old}))
    reply = json.loads("".join(c.text for c in res.content if getattr(c, "text", None)))
    assert reply["code"] == "bad_argument" and next(iter(old)) in reply["message"], reply


def test_a_second_session_is_refused_while_the_first_is_alive(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    install(alive=True)
    got = server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30)
    assert got["status"] == "INVALID"
    assert "already live" in got["message"]


def live_callers() -> set[str]:
    """The tools that CALL `live()`, asked of the source rather than remembered.

    A list here is a list that falls behind the surface, which is what happened: it
    named ten of the sixteen, under a docstring reading "THE POPULATION, not a sample
    of three". What a hand-written population misses is the NEWEST tools, which is
    exactly the direction that kind of list fails in.

    IT PARSES, it does not search, for the same reason
    `test_every_tool_has_a_live_case_naming_it` does: `"live()" in text` is satisfied
    by a comment.
    """
    tree = ast.parse(Path(str(server.__file__)).read_text(encoding="utf-8"))
    return {node.name for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and any(isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "live" for sub in ast.walk(node))}


def test_every_tool_that_needs_a_session_says_so_when_there_is_none(
        tmp_path: Path) -> None:
    """THE POPULATION, DERIVED. Each of these calls `live()`, and a tool that stopped
    doing so would answer from a corpse.

    THE ARGUMENTS CANNOT BE DERIVED -- a parser cannot invent a valid `segment` -- so
    they stay written here, and the check that they COVER the population is what is
    derived. A tool added tomorrow turns this red until it has a row, which is the one
    thing the old hand-written dict could not do.
    """
    nm = tmp_path / "s.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    calls: dict[str, Callable[[], dict[str, Any]]] = {
        "log": lambda: server.log(channel="guest", pattern="x"),
        "debug": lambda: server.debug(command="BPLIST"),
        "registers": server.registers,
        "set_register": lambda: server.set_register(name="ax", value=1),
        "write": lambda: server.write(ref="0040:0100", data_hex="00"),
        "breakpoint_interrupt": lambda: server.breakpoint_interrupt(number=0x21),
        "resume": server.resume, "stop": server.stop,
        "series_capture": lambda: server.series_capture(at_frames=[0]),
        "map_add": lambda: server.map_add(screen="s", match=[[0, 0, 1, 1]]),
        "map_find": server.map_find,
        "read_memory": lambda: server.read_memory(ref="0000:00000000"),
        "memdump": lambda: server.memdump(ref="0000:00000000", length=8, dest="/tmp/x"),
        "find": lambda: server.find(ref="0000:00000000", length=8, data_hex="00"),
        "scan_start": lambda: server.scan_start(ref="0000:00000000", length=8),
        "scan_filter": lambda: server.scan_filter(operator="=", value=0),
        "scan_clear": server.scan_clear,
        "captures": server.captures,
        "capture_frame": lambda: server.capture_frame(frame=0, dest="/tmp/x.png"),
        "log_wait": lambda: server.log_wait(channel="guest", pattern="x", seconds=1.0),
        "run_to": lambda: server.run_to(ref="0000:0000", control="0000:0020", seconds=1.0),
        "run_for": lambda: server.run_for(frames=1),
        "trace": lambda: server.trace(instructions=1, dest="/tmp/x.trace"),
        "step": lambda: server.step(mode="over", count=1),
        "symbols_find": lambda: server.symbols_find(name="_main"),
        "disassemble": lambda: server.disassemble(ref="0814:0100"),
        "call_stack": server.call_stack,
        "machine_map": server.machine_map,
        "interrupt_vectors": server.interrupt_vectors,
        "palette": server.palette,
        "screen_view": server.screen_view,
        "screen_signature": server.screen_signature,
        "screen_wait": lambda: server.screen_wait(text="C:"),
        "symbols_load": lambda: server.symbols_load(path=str(nm), base="10000"),
        "state_save": lambda: server.state_save(name="x"),
        "state_load": lambda: server.state_load(name="x"),
        "state_list": server.state_list,
        "snapshot": server.snapshot,
        "breakpoint_at": lambda: server.breakpoint_at(ref="_main"),
        "breakpoint_list": server.breakpoint_list,
        "breakpoint_clear": lambda: server.breakpoint_clear(all=True),
        "watch_add": lambda: server.watch_add(ref="_main", mode="change", length=4),
        "watch_list": server.watch_list,
        "watch_clear": lambda: server.watch_clear(all=True),
        "perform": lambda: server.perform(steps=[{"op": "registers"}]),
        "send_keys": lambda: server.send_keys(keys=["a"]),
        "send_mouse": lambda: server.send_mouse(button="left"),
        "drive": lambda: server.drive(act=[{"op": "status"}]),
        "comment_add": lambda: server.comment_add(ref="_main", text="x"),
        "comment_list": server.comment_list,
        "comment_delete": lambda: server.comment_delete(ref="_main"),
        "comment_save": lambda: server.comment_save(dest="/tmp/x.comments.tsv"),
        "comment_load": lambda: server.comment_load(path=str(nm)),
    }
    callers = live_callers()
    assert len(callers) > len(calls) // 2, (
        f"the derived population found {sorted(callers)}: an AST search that matches nothing "
        f"makes the check below pass whatever the tools are")
    missing = sorted(callers - set(calls))
    assert not missing, (
        f"these tools ask for a live session and are not exercised here: {missing}. "
        f"A tool that stopped calling `live()` would answer from a corpse and nothing "
        f"would say so")
    for name, call in calls.items():
        got = call()
        assert got["status"] == "INVALID", name
        assert "no live session" in got["message"], name


def test_the_block_carries_each_alarm_while_it_holds_and_the_process_facts_ride_at_the_top(
        ) -> None:
    """Every reply's block carries `alive`, `running`, `altered` and each alarm WHILE IT HOLDS;
    what the process is rides at the top of `start`, `status` and `close` and nowhere else. Read
    on a session whose alarms all hold, then on its quiet twin."""
    fake = install()
    quiet = fake.state()
    loud = {**quiet, "conf_changed_on_disk": True, "terminal_bytes_dropped": 4096,
            "drain_alive": False, "drain_ended": "EIO"}
    alarms = ("conf_changed_on_disk", "terminal_bytes_dropped", "drain_alive", "drain_ended")
    fake.state = lambda: loud  # type: ignore[method-assign]
    short = cast(dict[str, Any], server.registers())["session"]
    assert all(short[k] == loud[k] for k in alarms) and "pid" not in short, short
    status = cast(dict[str, Any], server.status())
    assert status["pid"] == 4242 and status["drain_ended"] == "EIO", status
    fake.state = lambda: quiet  # type: ignore[method-assign]
    short = cast(dict[str, Any], server.registers())["session"]
    assert set(short) == {"alive", "running", "altered"}, short
    closed = cast(dict[str, Any], server.close())
    assert closed["pid"] == 4242 and closed["elapsed_s"] == 1.0, "close says what it ended"


def test_a_dead_session_answers_broken_until_close_collects_it() -> None:
    """A machine that died under the session is `session_broken` with its `exit_code`, the
    session kept (its block, its `altered`) until `close`, which collects it."""
    dead = install(alive=False)
    got = cast(dict[str, Any], server.registers())
    assert got["code"] == "session_broken" and got["exit_code"] == -15, got
    assert dead.closed == 0 and cast(object, dstate.STATE.session) is dead
    closed = cast(dict[str, Any], server.close())
    assert closed["status"] == "ok" and dead.closed == 1 and dstate.STATE.session is None


def test_start_over_a_dead_session_collects_it_first_and_refuses_over_a_live_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n")

    def spawn(launch: Any) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    monkeypatch.setattr("scry_core.binaries.shutil.which", lambda _n: "/somewhere/dosbox-x")
    monkeypatch.setattr("dosbox_x_server.ds.Session", spawn)
    kw = {"conf": str(conf), "cwd": str(tmp_path), "session_seconds": 60}
    live_one = install()
    assert cast(dict[str, Any], server.start(**kw))["code"] == "session_live"
    assert live_one.closed == 0 and cast(object, dstate.STATE.session) is live_one
    dead = install(alive=False)
    dstate.STATE.last_stop.update({"stop_seq": 7, "where": {"cs": "0814", "eip": "00000106"}})
    assert cast(dict[str, Any], server.start(**kw))["code"] == "session_broken"
    assert dead.closed == 1 and dstate.STATE.session is None, "the dead session was not collected"
    # ITS ACCOUNT GOES WITH IT, even when the start that collected it is refused after.
    assert dstate.STATE.last_stop == {}, dstate.STATE.last_stop


# ------------------------------------------------------------------- the answers

def test_the_success_path_of_each_reader_returns_a_result(tmp_path: Path) -> None:
    """THE GREEN BESIDE THE REDS. Without it a reader could raise INVALID
    unconditionally and every refusal test above would still pass."""
    # THE SCREEN IS BUILT FROM THE ADDRESS BEING ASKED FOR, not pasted: `read_memory`
    # refuses a reply that does not contain the row it asked about, so a hand-written
    # row would have to be edited in step with the arguments below and would go stale
    # silently the day they change.
    seg, off = 0x0749, 0
    row = f"{seg:04X}:{off:08X} " + " ".join(["00"] * 16) + "  " + "." * 16
    install(screen=f"some screen\r\n{row}\r\n")
    assert server.registers()["regs"]["EAX"] == "0x00001234"
    assert server.debug(command="BPLIST")["status"] == "ok"
    got = server.read_memory(ref=f"{seg:04X}:{off:08X}")
    assert got["status"] == "ok"
    assert got["rows"] == [row], got
    assert "INT 21" in server.breakpoint_interrupt(number=0x21, detail=True)["screen_delta"]
    short = server.breakpoint_interrupt(number=0x10)
    assert "screen_delta" not in short and "screen_chars" not in short, short
    assert short["omitted"] == list(dstate.REPAINT_FIELDS) and short["how"] == dstate.REPAINT_HOW
    resumed = server.resume()
    assert resumed["status"] == "ok" and "screen_delta" not in resumed, resumed
    assert resumed["omitted"] == list(dstate.REPAINT_FIELDS) and "detail=True" in resumed["how"]


def test_a_reader_that_got_an_empty_screen_says_so(tmp_path: Path) -> None:
    install(screen="   \n")
    assert server.debug(command="BPLIST")["status"] == "INVALID"
    assert server.read_memory(ref="0000:00000000")["status"] == "INVALID"


def test_log_reports_how_many_matched_not_how_many_came_back() -> None:
    """Different answers. Reporting the slice's length under the name `matched` meant
    a caller asking "how many times did this fire" got the limit back."""
    install()
    got = server.log(channel="guest", pattern="loudness", limit=1)
    assert got["lines_total"] == 500
    assert len(got["lines"]) == 1
    assert got["truncated"] is True


def test_log_passes_the_callers_pattern_limit_and_channel_through() -> None:
    s = install()
    server.log(channel="guest", pattern="PERF", limit=7)
    assert s.log_calls == [("PERF", 7, "guest")]


def test_a_dump_returns_the_path_the_bytes_actually_landed_at(tmp_path: Path) -> None:
    """The success path, which had NO test: the only case was one where the file was
    absent, so the size half of the guard could be deleted and stay green."""
    install()
    dest = tmp_path / "out" / "mem.bin"
    got = server.memdump(ref="0749:00000000", length=16, dest=str(dest))
    assert got["status"] == "ok"
    assert Path(got["path"]) == dest and got["bytes"] == 16
    assert got["seg_off"] == "0749:00000000" and got["length"] == 16, got


# --------------------------------------------------------------- the reply shape

def test_every_reply_carries_whether_the_machine_was_written_to() -> None:
    s = install()
    assert server.status()["session"]["altered"] is False
    server.set_register(name="ax", value=0x10)
    assert s.altered is True
    assert server.status()["session"]["altered"] is True


def test_an_invalid_reply_carries_it_too() -> None:
    """The one a caller reasons hardest about, and the one an earlier version handed
    back with no trace that the machine had been forced."""
    install(screen="   \n")                 # nothing but whitespace comes back
    server.set_register(name="ax", value=0x10)
    got = server.debug(command="BPLIST")
    assert got["status"] == "INVALID"
    assert got["session"]["altered"] is True


def test_the_real_state_is_the_one_asserted(tmp_path: Path) -> None:
    """The contract belongs to the real object, so the real function is what runs here.

    `Session.state` is called UNBOUND against a minimal object carrying only the four
    attributes it reads, which exercises the actual code without a process existing.
    With only a hand-written stub in play, `altered` could be deleted from the real
    `state()` and the whole suite stayed green -- the headline guarantee gated by a
    double that had been written to agree with it.

    EVERY VALUE IS ASSERTED, not just the key set. An adversarial pass proved the
    earlier version toothless: breaking `"alive": self.alive()` to a hardcoded `True`,
    and `"terminal_bytes_dropped"` to a hardcoded `0`, each left all 56 green. Five of
    the nine values were checked by nothing, including the counter the whole drain
    change is about.
    """
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    dead = threading.Thread(target=lambda: None)
    fake = SimpleNamespace(
        proc=SimpleNamespace(pid=4242),
        alive=lambda: False, altered=True, conf_digest=dlaunch.digest(conf),
        started_at=time.monotonic() - 3.0, dropped=4096, _at_debugger=True,
        _drainer=dead, drain_ended="reading the terminal failed: OSError()",
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, watched=True,
                         window_flags=["-set", "sdl display=1"]))
    got = ds.Session.state(fake)  # type: ignore[arg-type]
    assert set(got) == {"pid", "alive", "running", "altered", "conf", "conf_digest",
                        "conf_changed_on_disk", "watched", "bound_s",
                        "elapsed_s", "terminal_bytes_dropped",
                        "drain_alive", "drain_ended", "captures", "state_dir"}
    # WHETHER CAPTURES ARE ON is said here, at `start` and at `close`, so a caller need not
    # infer it from a `captures` listing with no `avi` row.
    assert got["captures"] == "off"
    fake.launch = dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, capture_video=True,
                            program="X.EXE", captures_dir=tmp_path / "caps")
    assert ds.Session.state(fake)["captures"] == str(tmp_path / "caps")  # type: ignore[arg-type]
    fake.launch = dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, capture_video=True,
                            program="X.EXE")
    assert ds.Session.state(fake)["captures"] == "on, in the emulator's own directory"  # type: ignore[arg-type]
    # The pid is the emulator's OWN handle, so a caller ending a run by pid (or checking
    # the one it thinks is the session's) reads it here instead of hunting it with `ps`.
    assert got["pid"] == 4242
    # Each of these PASSES THROUGH a distinct attribute, so a value hardcoded in
    # `state()` fails here instead of being absorbed.
    assert got["alive"] is False
    assert got["altered"] is True
    assert got["watched"] is True
    assert got["conf"] == str(conf)
    assert got["bound_s"] == 60
    assert cast(float, got["elapsed_s"]) >= 3.0
    # Reported rather than inferred: the terminal buffer is bounded, so a caller has
    # no other way to tell a screen it saw whole from one missing its oldest bytes.
    assert got["terminal_bytes_dropped"] == 4096
    # A drainer that died takes every later read with it while `alive` still says the
    # emulator is up. Both halves are carried: whether it is running, and how it ended.
    assert got["drain_alive"] is False
    assert got["drain_ended"] == "reading the terminal failed: OSError()"
    assert got["conf_changed_on_disk"] is False
    # And it NOTICES when the conf moves under a live session, which is the only
    # reason the digest is carried at all.
    conf.write_text("[sdl]\nchanged\n", encoding="utf-8")
    assert ds.Session.state(fake)["conf_changed_on_disk"] is True  # type: ignore[arg-type]
    # A conf that cannot be read is said, never left a null nobody can tell from "unchanged".
    with mock.patch.object(dlaunch, "current_digest", side_effect=PermissionError("denied")):
        unread = cast(dict[str, Any], ds.Session.state(fake))  # type: ignore[arg-type]
    assert unread["conf_changed_on_disk"] == {"available": False,
                                              "why": "the conf could not be read: denied"}


def test_the_double_has_not_drifted_from_what_it_stands_in_for(tmp_path: Path) -> None:
    """A stub that has fallen behind the real shape is how a test starts agreeing with
    a bug instead of with a contract."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    fake = SimpleNamespace(
        proc=SimpleNamespace(pid=4242),
        alive=lambda: True, altered=False, conf_digest="x",
        started_at=time.monotonic(), dropped=0, _at_debugger=False,
        _drainer=None, drain_ended="",
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60))
    real = ds.Session.state(fake)  # type: ignore[arg-type]
    assert set(FakeSession().state()) == set(real)
    # THE BLOCK'S ALARMS NAME KEYS OF THIS SHAPE: a renamed key would leave a dead rule and
    # the alarm would ride as a fixed fact, omitted.
    fake.drain_ended = "EIO"
    assert {*dstate._ALARM_WHEN, *dstate._ALWAYS} <= set(ds.Session.state(fake))  # type: ignore[arg-type]
    # AND THE METHOD SURFACE, which this case's own name promised and did not check.
    # MEASURED: adding `read_memory` to the server left this green and made two other
    # cases die with an `AttributeError` -- a crash, not a contract failure, and one
    # the `tool()` wrapper deliberately does NOT translate, so on the real path it
    # would have escaped as a traceback rather than as INVALID.
    #
    # THE LIST IS DERIVED FROM THE SERVER'S OWN SOURCE, never written out here: a
    # parallel list is populated by whoever remembers, which is the same defect one
    # level up.
    #
    #
    # EVERY ATTRIBUTE THE SERVER USES THAT IS NOT ON AN IMPORTED MODULE, intersected
    # with what `Session` actually has. Three derivations have now been tried and the
    # first two each failed in one direction:
    #
    #   `live()\.(\w+)` by TEXT      -- saw 10, missed 5, and any `sess = live()`
    #                                    refactor blinded it completely.
    #   any `.name` by TEXT           -- read comments and docstrings, and made
    #                                    `subprocess.run` into a phantom requirement.
    #   `live()` usage by AST        -- precise about the source of the call and
    #                                    therefore NARROWER than the regex it replaced:
    #                                    MEASURED, it covered 10 where the regex had
    #                                    covered 14, so deleting `wait_ready` from the
    #                                    double went green. A guard against going blind
    #                                    that itself went blind.
    #
    # This one is by AST (so prose cannot contribute) and excludes attributes reached
    # on an IMPORT (so `subprocess.run` cannot), which is the pair of properties the
    # three attempts each had one of.
    #
    # THE POPULATION IS THE PACKAGE, not the server file: the tool bodies live in the
    # modules beside it (`dosbox_arming`, `dosbox_inputs`, ...), so a derivation that read
    # one file would have gone blind a fourth way, on the day the server was carved.
    #
    # AND EACH FILE IS READ AGAINST ITS OWN IMPORTS. Pooling every module's import
    # aliases into one set before deciding which attribute reads to keep would let a
    # local variable in one file, named like an import alias of ANOTHER file, hide its
    # attribute reads from the derivation: a hole no case fell through yet, closed
    # before one does.
    package = Path(str(server.__file__)).parent
    used: set[str] = set()
    for path in sorted(package.glob("dosbox_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {a.asname or a.name.split(".")[0]
                   for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        modules |= {a.asname or a.name
                    for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                    for a in n.names}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                 and not (isinstance(n.value, ast.Name) and n.value.id in modules)}
    # CALLABLE ONLY, said out loud because the comment above says "what `Session`
    # actually has" and this is narrower: every non-callable instance attribute is
    # dropped, `altered`, `argv` and `reap_failed` among them. The first and last are
    # read by the server and covered by their own cases; `argv` is not on the double at
    # all and is harmless only because `start` always builds a real `Session`.
    called = {n for n in used
              if not n.startswith("_") and callable(getattr(ds.Session, n, None))}
    # THE FLOOR IS NAMED, NOT COUNTED. Its first version was `>= 10`, which is exactly
    # what the broken derivation produced, so it was green on the very regression it
    # was added to stop. These are used on a session in plain sight, and the last four
    # are the ones the AST-only version silently dropped.
    for sentinel in ("registers", "read_memory", "memdump", "log",
                     "alive", "close", "state", "wait_ready"):
        assert sentinel in called, (
            f"the derivation no longer sees `{sentinel}`, which the server plainly "
            f"uses on a session: it has gone blind and this check is empty")
    for name in sorted(called):
        assert hasattr(ds.Session, name), f"the server calls a `Session.{name}` that does not exist"
        assert hasattr(FakeSession(), name), (
            f"the double has fallen behind: the server calls `{name}` on the session "
            f"and this stub does not have it")
    # THE COUNT IS DERIVED FROM THE REAL SHAPE, never written in prose. A comment on
    # `FakeSession` naming how many keys it holds has to be hand-edited by whoever adds
    # one -- a number in a comment that nothing checks is false at the next field and
    # nobody notices.
    assert len(FakeSession().state()) == len(real)


def test_closing_when_there_was_nothing_is_not_a_failure() -> None:
    got = server.close()
    assert got["status"] == "ok" and got["closed"] is False


def test_closing_a_live_session_closes_it_and_clears_it() -> None:
    """The real path, which had no test: removing `_SESSION = None` left the session
    installed and every later `start` refusing "a session is already live"."""
    s = install()
    got = server.close()
    assert got["closed"] is True and got["exit_code"] == 0
    assert s.closed == 1
    assert dstate.STATE.session is None
    # And the reply still carries the state it HAD, because a caller reading a close
    # is entitled to know whether what it just ended had been written to.
    assert got["session"]["altered"] is False


# ------------------------------------------------------------------ the wrapper

def test_invalid_is_surfaced_and_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper turns `Invalid` into a reply that SAYS INVALID. Letting it escape
    as an exception, or flattening it to an empty result, are the two ways an
    instrument that examined nothing gets read as one that found nothing."""

    # A throwaway tool the pre-gate registry has never heard of: named as machine-judged
    # for the test, since an unknown name there is a programmer's error by design.
    monkeypatch.setattr(checks, "MACHINE_JUDGES", checks.MACHINE_JUDGES | {"boom_invalid"})

    @dosbox_mcp.tool("Boom invalid", summary=lambda args, reply: "boom_invalid: ok")
    def boom_invalid() -> dict[str, object]:
        raise ds.Invalid("unexpected_answer", "I examined nothing")

    try:
        got = boom_invalid()
        assert got["status"] == "INVALID" and got["message"] == "I examined nothing"
    finally:
        # The throwaway registration LEAVES the live surface, or every later assertion
        # about that surface (the roster in the instructions) is order-dependent.
        server.mcp._tool_manager._tools.pop("boom_invalid", None)
        dosbox_mcp.BOUNDARY.summaries.pop("boom_invalid", None)


def test_a_real_bug_is_not_dressed_up_as_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """The EXCEPTION IDENTITY axis. Widening the wrapper to `except Exception` leaves
    the case above green while every genuine defect -- an AttributeError, a timeout --
    starts reporting itself as "I examined nothing", which is a broken instrument
    calling itself clean."""

    # A throwaway tool the pre-gate registry has never heard of: named as machine-judged
    # for the test, since an unknown name there is a programmer's error by design.
    monkeypatch.setattr(checks, "MACHINE_JUDGES", checks.MACHINE_JUDGES | {"boom_bug"})

    @dosbox_mcp.tool("Boom bug", summary=lambda args, reply: "boom_bug: ok")
    def boom_bug() -> dict[str, object]:
        raise AttributeError("a real defect")

    try:
        with pytest.raises(AttributeError):
            boom_bug()
    finally:
        server.mcp._tool_manager._tools.pop("boom_bug", None)
        dosbox_mcp.BOUNDARY.summaries.pop("boom_bug", None)


def test_both_halves_of_the_capture_come_back(tmp_path: Path) -> None:
    """BOTH, and they are not symmetric. The VIDEO is the emulator's own doing and
    needs no keypress; the STILL is an EXTRACTION from it, because the emulator's own
    screenshot is a mapper action with no non-interactive trigger at all.

    The bug this closes: `capture_video=True` started a recording and NO tool handed
    back the file. It recorded and did not say so.
    """
    fake = install()
    caps_dir = tmp_path / "caps"
    caps_dir.mkdir()
    fixtures = Path(__file__).parent / "fixtures" / "avi"
    for name in ("dosbox-x-zmbv-12.avi", "dosbox-x-zmbv-running.avi"):
        shutil.copyfile(fixtures / name, caps_dir / name)
    fake.launch.capture_video, fake.launch.captures_dir = True, caps_dir
    got = server.captures()
    assert got["status"] == "ok" and [c["kind"] for c in got["captures"]] == ["avi", "avi"], got
    sizes = [c["bytes"] for c in got["captures"]]
    assert sizes == sorted(sizes), "largest last: the default source for a still"
    assert all(c["present"] is True and c["avi_frames"] > 0 for c in got["captures"]), got

    dest = tmp_path / "shot" / "frame.png"
    shot = server.capture_frame(frame=1400, dest=str(dest))
    assert shot["status"] == "ok"
    assert Path(shot["path"]) == dest and shot["bytes"] > 0
    assert shot["frame"] == 1400 and len(shot["sha256"]) == 64, shot
    listed = server.captures()["captures"]
    assert listed[0] == {"kind": "png", "path": str(dest), "present": True,
                         "bytes": dest.stat().st_size}, "the still the session wrote, first"
    dest.unlink()
    assert server.captures()["captures"][0] == {"kind": "png", "path": str(dest),
                                                "present": False}, "gone, and said so"


def test_a_dump_of_the_wrong_size_is_not_the_dump_that_was_asked_for(
        tmp_path: Path) -> None:
    """The size is the ONLY thing tying those bytes to this request, so it is checked
    for EQUALITY.

    The first version asked only `> 0`, which accepts a truncated write, a wrong
    segment that landed short, and any leftover file with a byte in it. `length` was
    in hand the whole time. `Session.memdump` runs UNBOUND here against a stand-in
    whose `command` writes the file the debugger would have written -- the real method,
    the real check, no emulator.
    """
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    launch = dlaunch.Launch(conf=conf, cwd=work, seconds=60)

    def writes(nbytes: int) -> Callable[..., str]:
        def command(_text: str, **_k: object) -> str:
            (work / ds.MEMDUMP_NAME).write_bytes(b"\xAB" * nbytes)
            return f"DEBUG: {ds.MEMDUMP_OK}."
        return command

    short = SimpleNamespace(launch=launch, command=writes(100))
    # The REAL candidate list, asked of the real method: a hand-written one here
    # would stop covering a location the module adds later.
    short._memdump_candidates = lambda: ds.Session._memdump_candidates(short)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="holds 100"):
        ds.Session.memdump(short, 0, 0x400, 256, tmp_path / "a.bin")  # type: ignore[arg-type]

    assert not (work / ds.MEMDUMP_NAME).exists(), "the refused dump's own file is removed"
    # And the control: the RIGHT size goes through, so the refusal above is about the
    # length and not about this path being broken.
    exact = SimpleNamespace(launch=launch, command=writes(256))
    exact._memdump_candidates = lambda: ds.Session._memdump_candidates(exact)  # type: ignore[arg-type]
    got = ds.Session.memdump(exact, 0, 0x400, 256, tmp_path / "b.bin")  # type: ignore[arg-type]
    assert got.stat().st_size == 256


def test_a_dump_refuses_rather_than_deleting_what_is_already_there(
        tmp_path: Path) -> None:
    """It will not delete from the emulator's working directory, which is somebody's
    project. The earlier version unlinked every candidate with the error SUPPRESSED,
    so the staleness guarantee rested on an error nobody read."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    mine = work / ds.MEMDUMP_NAME
    mine.write_bytes(b"a file the caller cares about")
    fake = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=work, seconds=60),
        command=lambda *_a, **_k: "this should never be reached")
    fake._memdump_candidates = lambda: ds.Session._memdump_candidates(fake)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="already sitting at"):
        ds.Session.memdump(fake, 0, 0x400, 256, tmp_path / "out.bin")  # type: ignore[arg-type]
    assert mine.read_bytes() == b"a file the caller cares about"


# ------------------------------------ a caller's path is absolute or `~`-led, `~` expanded

def _launch_of(**kw: Any) -> dlaunch.Launch:
    """Run `start` far enough to capture the `Launch` it built, and no further.

    `ds.Session` is replaced by a builder that records its argument and then refuses,
    so nothing is spawned and `start` returns INVALID. `shutil.which` is stubbed, so these
    cases need no DOSBox-X installed."""
    seen: list[dlaunch.Launch] = []

    def build(launch: dlaunch.Launch) -> Any:
        seen.append(launch)
        raise ds.Invalid("session_broken", "not starting anything: this case wants the Launch only")

    with mock.patch("scry_core.binaries.shutil.which", lambda _n: "/somewhere/dosbox-x"), \
         mock.patch("dosbox_x_server.ds.Session", build):
        server.start(**kw)
    assert seen, "`start` never reached the Launch"
    return seen[0]


def test_start_takes_every_path_as_written(tmp_path: Path) -> None:
    """Each of `start`'s paths asserted SEPARATELY: they are separate arguments, so one
    assertion over one of them would leave the others free to regress."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    launch = _launch_of(conf=str(conf), cwd=str(tmp_path), session_seconds=30,
                        captures_dir=str(tmp_path / "caps"), logfile=str(tmp_path / "e9.log"),
                        state_dir=str(tmp_path / "states"))
    assert launch.conf == conf and launch.cwd == tmp_path.resolve()
    assert launch.captures_dir == tmp_path / "caps" and launch.logfile == tmp_path / "e9.log"
    assert launch.state_dir == tmp_path / "states"


@pytest.mark.parametrize(("arg", "under_home"), [
    ("conf", "g.conf"), ("cwd", ""), ("captures_dir", "caps"), ("logfile", "e9.log"),
    ("state_dir", "states")])
def test_start_expands_a_tilde_in_every_path_and_makes_nothing_at_a_literal_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arg: str, under_home: str) -> None:
    """`Path("~/g.conf")` is a RELATIVE path whose first component is `~`: the judge expands
    it, so the session is built on the home directory's path and nothing is made at a
    literal `~`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    kw: dict[str, Any] = {"conf": str(conf), "cwd": str(tmp_path), "session_seconds": 30,
                          arg: f"~/{under_home}" if under_home else "~"}
    built: list[dlaunch.Launch] = []

    def build(launch: dlaunch.Launch) -> None:
        built.append(launch)
        raise ds.Invalid("host_failed", "built: the case ends here")
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: "/somewhere/dosbox-x"), \
         mock.patch("dosbox_x_server.ds.Session", build):
        got = cast(dict[str, Any], server.start(**kw))
    assert "built: the case ends here" in got["message"], got
    assert getattr(built[0], arg) == (tmp_path / under_home if under_home else tmp_path)
    assert not (tmp_path / "~").exists()


def test_the_two_optional_paths_stay_absent_when_the_caller_omits_them(tmp_path: Path) -> None:
    """`captures_dir` and `logfile` are absent unless given: "the caller said nothing" never
    turns into a path (a captures directory at the working directory, an `e9` channel
    reading a directory, both `ok`)."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    launch = _launch_of(conf=str(conf), cwd=str(tmp_path), session_seconds=30)
    assert launch.captures_dir is None and launch.logfile is None
    assert launch.state_dir == tmp_path.resolve() / "save"


def test_memdump_expands_a_tilde_dest_and_makes_no_literal_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`~/dump.bin` taken as written would put the bytes in a directory literally named `~`:
    the judge expands it, so the bytes land in the home directory and no `~` is made."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install()
    got = cast(dict[str, Any],
               server.memdump(ref="0000:00000400", length=16, dest="~/dump.bin"))
    assert got["status"] == "ok", got
    assert (tmp_path / "dump.bin").stat().st_size == 16 and not (tmp_path / "~").exists()


def test_capture_frame_expands_a_tilde_in_either_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`dest` AND `source`, separately, because they are two arguments."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "run.avi").write_bytes(b"RIFF")
    fake = install()
    seen: list[Any] = []

    def frame(at: int, dest: Path, source: Path) -> Path:
        seen.append((at, dest, source))
        dest.write_bytes(b"png")
        return dest
    fake.frame = frame  # type: ignore[method-assign,assignment]
    for kw in ({"dest": "~/shot.png"},
               {"dest": str(tmp_path / "shot2.png"), "capture_path": "~/run.avi"}):
        assert cast(dict[str, Any], server.capture_frame(5, **kw))["status"] == "ok"
    assert [a[1] for a in seen] == [tmp_path / "shot.png", tmp_path / "shot2.png"], seen
    assert seen[1][2] == tmp_path / "run.avi" and not (tmp_path / "~").exists()


def test_an_omitted_capture_source_stays_absent_rather_than_becoming_a_path(
        tmp_path: Path) -> None:
    """The source defaults to "the largest capture", decided inside the session; an omitted
    one is handed down as absent, never as a path."""
    fake = install()
    seen: list[Path | None] = []

    def frame(at: int, dest: Path, source: Path | None = None) -> Path:
        seen.append(source)
        dest.write_bytes(b"\x89PNG")
        return dest

    fake.frame = frame  # type: ignore[method-assign]
    server.capture_frame(5, str(tmp_path / "shot.png"))
    assert seen == [Path("/caps/run_001.avi")], "the default source is the largest capture"


@pytest.mark.parametrize("bad", ["~nosuchuser-here/x", "~\x00/x"])
def test_a_tilde_user_or_a_nul_is_a_refusal_and_not_a_traceback(
        tmp_path: Path, bad: str) -> None:
    """`tool()` translates only `Invalid`, so both spellings are refused cleanly, through three
    tools, each reply carrying its session block."""
    got = cast(dict[str, Any], server.start(conf=bad, cwd=str(tmp_path), session_seconds=30))
    assert got["code"] == "bad_argument" and "session" in got, got
    install()
    got = cast(dict[str, Any], server.memdump(ref="0000:00000400", length=16, dest=bad))
    assert got["code"] == "bad_argument" and "session" in got, got
    got = cast(dict[str, Any], server.snapshot(dest=bad))
    assert got["code"] == "bad_argument", got
    # The control: an absolute path in a directory that is there goes through.
    ok = cast(dict[str, Any], server.memdump(ref="0000:00000400", length=16,
                                             dest=str(tmp_path / "fine.bin")))
    assert ok["status"] == "ok", ok


# ------------------------------------------------------------------------- symbols

NM_TEXT = ("0016df20 T _main\n"
           "0005c830 T _engine_load_midi\n"
           "0005aa20 T _engine_create\n"
           "0013a020 t .text\n")


def _source(tmp_path: Path, text: str = NM_TEXT) -> str:
    p = tmp_path / "djgpp32.sym"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_the_base_is_measured_off_the_machine_and_not_assumed(tmp_path: Path) -> None:
    """The one fact a symbol file cannot be built without, and the one place it lives.

    A toolchain emits OFFSETS; this debugger's var list stores LINEAR addresses. Under
    a DPMI host the difference is decided at load time, so it is read from the running
    machine -- and the LIMIT comes back beside it because that is the independent thing
    a caller can check the base against.
    """
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "ok", got
    assert got["base"] == MEASURED_BASE, got
    assert got["limit"] == 0x0023FFFF, got
    assert got["base_from"] == "CS", got


def test_the_base_is_read_from_this_commands_echo_and_not_the_first_on_screen(
        tmp_path: Path) -> None:
    """The debugger overlays `ss: b:00008240` into the register pane, so a reader that
    takes the first `b:` on the screen answers about the STACK selector.

    This is the case that makes the anchoring load-bearing rather than tidy: the stack
    base is in the captured screen, above the answer, and it is a perfectly plausible
    number.
    """
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base_from="DS"))
    assert got["base"] == MEASURED_BASE, got
    assert got["base"] != 0x00008240, "it answered with the stack selector's base"


def test_an_explicit_base_reports_no_limit_rather_than_inventing_one(
        tmp_path: Path) -> None:
    """The limit is what lets a caller check the base is really this program's, so a
    fabricated one would hand their own assumption back as evidence for itself."""
    install()
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base="100000"))
    assert got["base"] == 0x00100000, got
    assert got["limit"] == -1, got
    assert got["base_from"] == "caller", got


def test_every_parsed_symbol_is_accounted_for_in_the_reply(tmp_path: Path) -> None:
    """The counts are what a caller reads INSTEAD of the names, so they must sum."""
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["parsed"] == 4, got
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["unencodable_total"]) == got["parsed"], got
    assert got["excluded_sections"] == 1, got
    assert got["truncated_names"] == 1, got    # `_engine_load_midi` is 17 characters


def test_the_accounting_still_sums_when_the_unencodable_list_is_truncated(
        tmp_path: Path) -> None:
    """`unencodable` is a POSITIONAL SLICE, so it needs a count beside it or the
    reply's own arithmetic stops adding up -- and the caller's conservation check fails
    silently, over a reply whose whole purpose is that the counts are what you read
    instead of the names.

    THE FIXTURE HAS TO EXCEED THE CAP. The other case has four symbols and at most one
    unencodable, so it could never reach it: the sum held there while it was broken,
    and the assertion was written against `len(...)`, which encoded the break.
    """
    install(mode="Pr32")
    text = "".join(f"0000{i:04x} T _caf\u00e9{i}\n" for i in range(12)) + "00009999 T _ok\n"
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path, text)))
    assert got["parsed"] == 13, got
    assert got["unencodable_total"] == 12, got
    assert len(got["unencodable"]) == 8, "the list is capped, which is the point"
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["unencodable_total"]) == got["parsed"], got


def test_loaded_is_read_back_out_of_the_debugger_and_lv_appends(
        tmp_path: Path) -> None:
    """`ok` is not evidence: this emulator prints it for a filename it truncated.

    And `LV` appends (tests/fixtures/symbols-lv), so a second load leaves BOTH lists --
    `loaded` is the debugger's whole holding, not the size of this call. A tool reporting the latter
    would be describing something the real command does not do.
    """
    install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src))
    assert first["loaded"] == first["kept"] == 3, first
    second = cast(dict[str, Any], server.symbols_load(path=src))
    assert second["kept"] == 3, second
    assert second["loaded"] == 6, second


def test_the_bytes_that_went_in_carry_the_measured_linear_address(
        tmp_path: Path) -> None:
    """End to end through the server: `nm`'s 0x16DF20 plus the machine's 0x400000 is
    the 0x56DF20 the live debugger was measured holding for `_main`."""
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert ("_main", 0x0056DF20) in s.loaded, s.loaded


def test_a_source_that_is_not_a_symbol_list_is_refused_by_name(tmp_path: Path) -> None:
    install()
    src = _source(tmp_path, "make: *** No rule to make target 'all'.  Stop.\n")
    got = cast(dict[str, Any], server.symbols_load(path=src))
    assert got["status"] == "INVALID", got
    assert "djgpp32.sym" in got["message"], got
    assert "session" in got, got


def test_a_register_this_debugger_does_not_report_is_refused_not_sent(
        tmp_path: Path) -> None:
    """`SELINFO` answers an argument it does not know with an EMPTY name and an all-zero
    descriptor rather than an error (tests/fixtures/selinfo/break-start-af.txt), which
    reads exactly like a real selector based at 0."""
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base_from="AX"))
    assert got["status"] == "INVALID", got
    assert "ZEROED" in got["message"], got


def test_a_pattern_narrows_by_the_full_name(tmp_path: Path) -> None:
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   pattern="^_engine"))
    assert got["kept"] == 2, got
    assert got["excluded_pattern"] == 1, got   # `_main`; `.text` is a section


# A BORLAND MAP WITH AN OVERLAY, minimal and NOT the symbols suite's captured fixture:
# what is being asserted here is the SEAM -- that the flag survives the tool boundary --
# and the parsing of it is that suite's, next to the real file it was captured from.
TLINK_TEXT = (
    " Start  Stop   Length Name               Class\r\n"
    "\r\n"
    " 00000H 0ACD7H 0ACD8H _TEXT              CODE\r\n"
    "\r\n"
    "  Address         Publics by Name\r\n"
    "\r\n"
    " 0D74:00E21 idle  ACTIVEIMAN\r\n"
    " 0459:00123       ACTIVE_CLS\r\n"
    "\r\n"
    "Program entry point at 0000:0000\r\n")


def test_an_overlay_symbol_reaches_the_caller_flagged_and_counted(tmp_path: Path)\
        -> None:
    """CONDITIONALITY AT THE BOUNDARY, which is the only place it is worth anything.

    TLINK writes `idle` beside a public in an overlay it has not made resident, so that
    address holds whatever is swapped in when you look. The reader carries the flag now;
    this is the case that says an MCP caller SEES it -- both as a count of how much of
    the table is like that, and per symbol, because a total cannot answer about the one
    name you asked for.

    THE BASE IS PASSED. A Borland map is real-mode `SEG:OFFS` and `base_from` measures a
    DPMI selector that does not exist there, which is the tool's own documented refusal.
    """
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base="1000"))
    assert got["status"] == "ok", got
    assert got["kept"] == 2, got
    assert got["overlay_idle"] == 1, got
    # A SUBSET AND NOT A BUCKET: the counts above still partition `parsed`, so a caller
    # checking the accounting is not told a symbol went missing.
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["excluded_unplaceable"] + got["unencodable_total"]
            == got["parsed"] == 2), got

    flagged = cast(dict[str, Any], server.symbols_find(name="ACTIVEIMAN"))
    assert flagged["symbols"][0]["idle"] is True, flagged
    # THE CONTROL, without which `idle: True` hardcoded satisfies the line above.
    plain = cast(dict[str, Any], server.symbols_find(name="ACTIVE_CLS"))
    assert plain["symbols"][0]["idle"] is False, plain
    # AND THE OTHER BRANCH of the same tool, which builds its reply separately.
    linear = f"{0x1000 + 0x0D74 * 16 + 0x00E21:X}"
    by_addr = cast(dict[str, Any], server.symbols_find(linear=linear))
    assert by_addr["name"] == "ACTIVEIMAN" and by_addr["idle"] is True, by_addr


def test_an_nm_table_is_reported_with_no_overlay_symbols(tmp_path: Path) -> None:
    """THE CONTROL FOR THE FORMAT: `nm` has no such concept, so anything but zero here
    would be this server inventing one. Without it, a hardcoded 1 passes the case
    above."""
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["overlay_idle"] == 0, got
    found = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert found["symbols"][0]["idle"] is False, found


# TWO SECTIONS AT THE SAME OFFSET, and the `Start` column reading ZERO -- both of them
# copied from the real artefact (`HELLO32.MAP`) rather than from the vendor's
# documentation, which is where the previous version of this came from and where it was
# wrong. Two sections because with one, a reply that ignored the section index and one
# that used it are the same reply.
TLINK32_TEXT = (
    " Start         Length     Name               Class\r\n"
    "\r\n"
    " 0001:00000000 0000214D4H _TEXT              CODE\r\n"
    " 0002:00000000 0000059B8H _DATA              DATA\r\n"
    "\r\n"
    "  Address         Publics by Name\r\n"
    "\r\n"
    " 0001:000000E4       _main\r\n"
    " 0002:000000E4       _table\r\n"
    "\r\n"
    "Program entry point at 0001:000000E4\r\n")


def test_a_32_bit_map_reaches_the_caller_through_the_tool(tmp_path: Path) -> None:
    """THE WHOLE SEAM, which nothing exercised: every 32-bit assertion lived one layer
    down, against `sym.parse` directly.

    `symbols_load` -> `parse` -> the 32-bit path -> `plan` -> `encode` -> the debugger ->
    `_placed` is where the arithmetic a caller actually sees is decided.

    `section_bases` IS THE POINT OF THE CASE NOW, and it replaced `base=0`. That old
    argument rested on the belief that the map's `Start` column is a full address, so
    the offsets coming out were already complete; the real artefact prints zeros there,
    which makes `base=0` mean "put everything at its raw offset". A sectioned map is
    placed from a table the CALLER supplies, because the bases are not in the file.

    THE TWO BASES ARE DISTINCT AND THE TWO SYMBOLS SHARE AN OFFSET, which is what lets
    this fail at all: with one base, or with the section index ignored, `_main` and
    `_table` come back at the same address and the reply reads exactly as right.
    """
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x401000", "2": "0x423000"}))
    assert got["status"] == "ok", got
    assert got["kept"] == 2 and got["unreadable"] == 0, got
    assert got["overlay_idle"] == 0, got

    at = {}
    for name in ("_main", "_table"):
        found = cast(dict[str, Any], server.symbols_find(name=name))
        one = found["symbols"][0]
        assert one["offset"] == 0x000000E4, one
        assert one["idle"] is False, one
        at[name] = (one["section"], int(one["addr"], 16))
    assert at == {"_main": (1, 0x004010E4), "_table": (2, 0x004230E4)}, at


def test_a_sectioned_map_refuses_a_section_the_caller_did_not_position(
        tmp_path: Path) -> None:
    """The refusal a caller most needs, through the layer they meet it at: it NAMES the
    section nobody positioned rather than reporting a row as lost."""
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    # THE TOOL DECORATOR TRANSLATES A REFUSAL INTO A REPLY rather than letting it
    # escape, which is the whole reason `Invalid` exists as its own type -- so the
    # assertion is on the reply, not on an exception.
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x401000"}))
    assert got["status"] != "ok", got
    assert "section 2" in str(got["message"]), got["message"]
    assert "_table" in str(got["message"]), got["message"]


def test_section_bases_keys_arrive_as_json_strings_and_are_read_as_numbers(
        tmp_path: Path) -> None:
    """JSON HAS NO INTEGER KEYS, so the table reaches this tool keyed on `"1"`.

    Accepted as it comes, it would match NO symbol -- every one of them carries an `int`
    section -- while looking exactly like a table that does, and the caller would be told
    their sections are unpositioned about a table naming all of them.
    """
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"0x1": "0x401000", "2": "0x423000"}))
    assert got["kept"] == 2, got
    # AND A KEY THAT IS NOT A NUMBER IS REFUSED rather than silently dropped, because a
    # dropped key is a section that then reads as unpositioned.
    bad = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"_TEXT": "0x401000"}))
    assert bad["status"] != "ok", bad
    assert "section indices" in str(bad["message"]), bad["message"]


# ------------------------------------------------------------- finding one again

def test_find_refuses_before_anything_is_loaded() -> None:
    install()
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "INVALID", got
    assert "no symbol table" in got["message"], got


def test_find_answers_with_both_addresses(tmp_path: Path) -> None:
    """The offset is what the toolchain printed and the linear is what the debugger
    shows; quoting one makes the reader do the arithmetic this tool got right once."""
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "ok", got
    assert got["symbols"][0]["offset"] == 0x0016DF20, got
    assert got["symbols"][0]["addr"] == "0x0056df20", got


def test_find_by_linear_takes_the_base_back_off(tmp_path: Path) -> None:
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(linear="0056DF24"))
    assert got["name"] == "_main", got
    assert got["delta"] == 4, got


def test_find_by_linear_takes_hex_text_and_refuses_a_number(tmp_path: Path) -> None:
    """`linear` is hex TEXT, so no caller converts hex to decimal: a number is
    refused naming the argument, never read as hex digits or coerced, and so is text that is
    not a hex address."""
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    prefixed = cast(dict[str, Any], server.symbols_find(linear="0x56DF24"))
    assert prefixed["name"] == "_main" and prefixed["delta"] == 4, prefixed
    for bad in (0x0056DF24, "56DFZZ", "-56DF24"):
        got = cast(dict[str, Any], server.symbols_find(linear=bad))
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "linear is" in got["message"], got["message"]


def test_find_wants_exactly_one_question(tmp_path: Path) -> None:
    install()
    server.symbols_load(path=_source(tmp_path))
    both = cast(dict[str, Any], server.symbols_find(name="_main", linear="1"))
    assert both["status"] == "INVALID", both
    neither = cast(dict[str, Any], server.symbols_find())
    assert neither["status"] == "INVALID", neither


def test_the_table_is_forgotten_when_the_session_goes(tmp_path: Path) -> None:
    """THE STALE-BASE GUARD, and it is the reason the table is cleared at all.

    A base belongs to ONE loaded process. Kept across a close, `symbols_find` goes on
    adding the old base to its offsets and hands back a confident linear address for a
    program that is no longer running -- which this package treats as worse than a
    refusal, because a refusal is visible.
    """
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert cast(dict[str, Any], server.symbols_find(name="_main"))["status"] == "ok"
    server.close()
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "INVALID", got
    assert dstate.STATE.table == [], "the table outlived the session it was measured on"


def test_a_session_that_died_on_its_bound_takes_the_table_with_it(
        tmp_path: Path) -> None:
    """THE MOST DANGEROUS OF THE THREE CLEARING SITES, and the one no test reached.

    `_forget_symbols` runs when the session OBJECT changes. A session that expires on
    its own bound changes no object until `close` collects it, so `symbols_find` asks
    `live()` first and is `session_broken` meanwhile: without the call it would answer `ok`
    with a linear address for a program that is gone.
    """
    s = install()
    server.symbols_load(path=_source(tmp_path))
    s._alive = False                      # what a bound expiring looks like from here
    got = cast(dict[str, Any], server.symbols_find(linear="0056DF24"))
    assert got["code"] == "session_broken", got
    server.close()
    assert dstate.STATE.table == [], "the table outlived the process it was measured on"


def test_a_new_session_does_not_inherit_the_previous_ones_table(
        tmp_path: Path) -> None:
    """The second untested site. `start` clears ABOVE every validation, so it is
    reached with no previous session and on every failure path -- but nothing asserted
    it, and deleting that one call left the whole suite green.

    IT CLEARS EVEN WHEN `start` GOES ON TO REFUSE, which is the direction that matters:
    the clear sits above every validation, so a `start` that fails for any reason still
    does not leave the previous program's base behind.
    """
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert dstate.STATE.table, "precondition: a table is installed"
    s._alive = False                    # the previous session's bound has expired
    server.start(conf=str(tmp_path / "nope.conf"), cwd=str(tmp_path), session_seconds=30)
    assert dstate.STATE.table == [], (
        "a new session inherited the previous one's table, so `symbols_find` would add "
        "a dead program's base to its offsets")


def test_a_start_refused_because_a_session_is_live_keeps_the_table(
        tmp_path: Path) -> None:
    """The mirror, and it is what stops "clear on every start" being the whole answer:
    a `start` refused because the machine is still up has changed nothing, and the
    table still describes the program that is still running."""
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.start(conf=str(tmp_path / "x.conf"),
                                            cwd=str(tmp_path), session_seconds=30))
    assert got["status"] == "INVALID" and "already live" in got["message"], got
    assert cast(dict[str, Any],
                server.symbols_find(name="_main"))["status"] == "ok"


# A `SELINFO CS` reply at `-break-start` (real mode, at the reset vector), AUTHORED. The
# descriptor is all zeroes and it is INDISTINGUISHABLE from the reply for a selector nothing
# has set up -- which is why the type field is what decides, not the base.
SELINFO_ZEROED = (
    "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo\r\n"
    "EAX=00000000  ESI=00000000  DS=0000   ES=0000   SS=0000 Real\r\n"
    "EBX=00000000  EDI=00000000  CS=F000   EIP=0000FFF0  C0 Z0 S0 O0\r\n"
    "ooooOutputoooooooooooooooooooooooooooooooooooooooooooooooooooooo"
    "SelectorInfo CS:\r\n"
    "CS: b:00000000 type:00 parbg\nl:00000000 dpl : 0 00000\r\n"
    "I-> _")


# `SELINFO CS` at a real-mode stop INSIDE a program (the probe guest at 0814:012A),
# captured through the MCP client: the echo and nothing else, no descriptor line at all.
SELINFO_REAL_MODE_IN_A_PROGRAM = "SelectorInfo CS:\r\n\n\nI-> _"


def test_a_real_mode_map_with_no_base_is_refused_before_selinfo_is_asked(
        tmp_path: Path) -> None:
    """In real mode there are no descriptors to measure a base from, and this build's
    `SELINFO` there prints no descriptor line at all inside a program, so asking it could only
    give the parser's refusal, which names the wrong cause. The register pane already says the
    mode, so the refusal comes first and names the cause and the remedy: `base` as hex text,
    the load segment times 16. A 16-bit protected-mode pane has descriptors and is measured."""
    class RealModeProgram(FakeSession):
        asked: list[str] = []

        def selector(self, reg: str) -> dict[str, int]:
            self.asked.append(reg)
            self._screen = SELINFO_REAL_MODE_IN_A_PROGRAM
            return ds.Session.selector(self, reg)      # type: ignore[arg-type]

    s = RealModeProgram()
    s.asked = []
    dstate.STATE.session = s                                # type: ignore[assignment]
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "real mode" in got["message"].lower() and "`base`" in got["message"], got
    assert "* 16" in got["message"], got
    assert s.asked == [], "SELINFO was asked in real mode"
    pr16 = FakeSession(mode="Pr16")
    dstate.STATE.session = pr16                             # type: ignore[assignment]
    measured = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert measured["status"] == "ok" and measured["base"] == MEASURED_BASE, measured


def test_an_absent_descriptor_is_refused_rather_than_placed_at_base_zero(
        tmp_path: Path) -> None:
    """THE GUARD THAT MATTERS MOST, because its failure mode is silent and plausible.

    A zeroed descriptor (the shape `SELINFO` gives at the reset vector, and for a selector
    nothing has set up) taken at face value is `base = 0`, which places every symbol at its
    raw offset -- a table that loads without complaint, reports `ok`, and names whatever
    occupies low memory. Real mode is refused before it is asked; this is the guard that is
    left, for a protected-mode selector with no present descriptor.

    The type field is what separates it from a real descriptor, and it separates it from
    NOTHING ELSE: base 0 alone is not the signal, because a base of 0 is a legal thing
    for a descriptor to have.
    """
    class Unset(FakeSession):
        """The double with the zeroed descriptor, on a protected-mode pane."""

        def where(self) -> dict[str, str]:
            return {"cs": "00A7", "eip": "00000000", "mode": "Pr32"}

        def selector(self, reg: str) -> dict[str, int]:
            self._screen = SELINFO_ZEROED
            return ds.Session.selector(self, reg)      # type: ignore[arg-type]

    s = Unset()
    dstate.STATE.session = s                                # type: ignore[assignment]
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "INVALID", got
    assert "no present descriptor" in got["message"], got
    assert "raw offset" in got["message"], got

    # AND THE CONTROL: an explicit base still goes through on that same machine, so the
    # refusal is about the DESCRIPTOR and not a helper that refuses everything.
    ok = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                  base="F0000"))
    assert ok["status"] == "ok", ok
    assert ("_main", 0x000F0000 + 0x0016DF20) in s.loaded, s.loaded


def test_an_empty_name_is_a_listing_and_not_a_lookup(tmp_path: Path) -> None:
    """`startswith("")` is true of every symbol, so an empty name matched all of them
    under `status: ok` -- honest arithmetic, and not the question anybody asked."""
    install()
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(name=""))
    assert got["status"] == "INVALID", got


def test_a_failed_load_does_not_replace_a_table_that_was_working(
        tmp_path: Path) -> None:
    """A REFUSAL THAT ALSO CORRUPTS STATE inverts this module's one rule.

    `load_symbols` refuses on many paths -- seven at the time of writing, and the count
    is not the point, which is why this no longer quotes one: it said FOUR while the
    method already had six. Installing the table before calling it meant a refused load
    still replaced a good one: the caller got INVALID from `symbols_load` and `ok` from
    `symbols_find`, answering out of a table the debugger does not hold.
    """
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    good = cast(dict[str, Any], server.symbols_find(name="_main"))["symbols"][0]

    def refuse(data: bytes) -> list[tuple[str, int]]:
        raise ds.Invalid("unexpected_answer", "the debugger did not acknowledge it")

    s.load_symbols = refuse                     # type: ignore[method-assign]
    other = _source(tmp_path, "00001000 T _somebody_elses_main\n")
    bad = cast(dict[str, Any], server.symbols_load(path=other))
    assert bad["status"] == "INVALID", bad
    still = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert still["status"] == "ok", still
    assert still["symbols"][0] == good, "a refused load replaced a working table"


def test_the_descriptor_type_is_reported_so_a_caller_can_see_what_was_read(
        tmp_path: Path) -> None:
    """`1B` is a 32-bit code segment and `13` is data; an explicit base reports `-1`
    because there was no descriptor to read at all."""
    install(mode="Pr32")
    measured = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert measured["descriptor"] == 0x1B, measured
    given = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                     base="1000"))
    assert given["descriptor"] == -1, given


def test_a_source_that_cannot_be_read_is_a_refusal_and_not_a_traceback(
        tmp_path: Path) -> None:
    """`tool()` translates only `Invalid`, and a mistyped path is this tool's likeliest first
    call: it is refused naming the file it did not find, with the session block."""
    install()
    got = cast(dict[str, Any], server.symbols_load(path=str(tmp_path / "nope.sym")))
    assert got["status"] == "INVALID", got
    assert "no symbol file at" in got["message"], got
    assert "session" in got, got

    # A DIRECTORY is the other spelling of the same mistake, and it raises a different
    # OSError subclass -- so it is here rather than assumed to be covered.
    d = cast(dict[str, Any], server.symbols_load(path=str(tmp_path)))
    assert d["status"] == "INVALID", d


# ---------------------------------- the three blind spots that were MEASURED
#
# Each of these breaks came back GREEN over the whole contract tier. They are the
# same shape as the defect `read_memory`'s own docstring convicts -- accept a number,
# never use it, echo it back -- and that one was fixed while its two neighbours were
# not.


def test_memdump_forwards_the_address_the_caller_asked_for(tmp_path: Path) -> None:
    """`live().memdump(0, 0, length, ...)` passed every case: the double ignored the
    segment and the offset, so nothing could tell a tool that forwards its caller's
    address from one that dumps low memory and reports `ok`."""
    fake = install()
    dest = tmp_path / "d.bin"
    # Inside one segment's 64 KiB, so it is one command whatever the mode; a range past offset
    # 0xFFFF is `test_dosbox_x_dump.py`'s, where the windows and the descriptor are judged.
    got = cast(dict[str, Any], server.memdump(ref="0749:00001A44",
                                              length=64, dest=str(dest)))
    assert got["status"] == "ok"
    assert fake.memdump_calls == [(0x0749, 0x1A44, 64)], fake.memdump_calls
    # AND THE LENGTH IS NOT 16, which is what both pre-existing dump cases happened to
    # request -- so a break pinning the literal 16 was green as well.
    assert got["bytes"] == 64


def test_set_register_writes_the_value_it_was_given() -> None:
    """`live().set_register(name, 0)` was green: the only case asserted `altered` and
    the session block, never the mapping that comes back, so the VALUE was unwatched."""
    fake = install()
    got = cast(dict[str, Any], server.set_register(name="EAX", value=0xDEADBEEF))
    assert got["regs"]["EAX"] == "0xdeadbeef", got["regs"]
    # READ BACK: `readback` is what the pane says and `verified` whether it equals what
    # was sent; a register the debugger masks answers false under `status: ok` and
    # `altered` either way, rather than being refused.
    assert (got["readback"] == "DEADBEEF" and got["verified"] is True
            and got["value"] == "0xdeadbeef")
    assert got["summary"] == "set_register EAX = 3735928559, verified True"
    # THE CONTROL: a different value has to produce a different answer, or this is
    # asserting a constant.
    again = cast(dict[str, Any], server.set_register(name="EAX", value=1))
    assert again["regs"]["EAX"] == "0x00000001"
    fake.masks = True
    masked = cast(dict[str, Any], server.set_register(name="EAX", value=0x10000))
    assert masked["status"] == "ok" and masked["verified"] is False
    assert masked["readback"] == "00000000" and masked["session"]["altered"] is True


def test_the_central_distinctness_guarantee_is_gated_and_not_merely_written() -> None:
    """`Plan.check()`'s own docstring says the guarantee "was measurably FALSE for a
    while, and a guarantee that lives only in a test is one that holds until somebody
    edits the function without running that test" -- and then NOTHING tested the check
    itself. Removing its uniqueness raise passed the whole tier.

    All three of its refusals are exercised here, each built by hand rather than by
    `plan()`, because `plan()` cannot produce an invalid one and a check that can only
    be fed valid input is not being checked.
    """
    two = [dsym.Symbol("_a", 1), dsym.Symbol("_b", 2)]
    with pytest.raises(dsym.BadSymbolText, match="belonging to another symbol"):
        dsym.Plan(parsed=2, symbols=two, short=["x", "x"]).check()
    with pytest.raises(dsym.BadSymbolText, match="cannot be zipped"):
        dsym.Plan(parsed=2, symbols=two, short=["x"]).check()
    with pytest.raises(dsym.BadSymbolText, match="accounting does not add up"):
        dsym.Plan(parsed=99, symbols=two, short=["x", "y"]).check()
    # THE CONTROL: a well-formed plan passes all three, so this is not a check that
    # refuses everything.
    dsym.Plan(parsed=2, symbols=two, short=["x", "y"]).check()


# ------------------------------------------------ the verification pass

def test_build_check_is_invalid_and_not_ok_when_there_is_no_binary() -> None:
    """`build_check` had NO contract case at all -- not one, which is what the finding
    said, but none.

    MEASURED: `grep build_check tests/` matched a comment, a string inside another
    test's expected set, and ONE case in the LIVE tier; `pytest -k build_check` selected
    zero of 288. So the defect its own docstring records -- "An earlier version
    returned `ok` with `binary: None`, the one tool whose purpose is examining
    preconditions reporting a clean result for a missing tool" -- was pinned by nothing
    that runs on a commit, and by nothing else either.

    THE PATH IS PATCHED, NOT THE ANSWER: `shutil.which` is what decides, so that is
    what the double stands in for, and the real body runs.
    """
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: None):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "no DOSBox-X binary resolves" in str(got["message"])
    assert got.get("binary") is None, "an INVALID reply may not carry a binary"


def test_build_check_is_invalid_when_the_build_has_no_debugger() -> None:
    """The precondition it exists for. A build without the debugger starts fine and
    then hangs `start` until its timeout, so a `build_check` that could not tell them
    apart would send a caller looking at their config."""
    with (mock.patch("scry_core.binaries.shutil.which", lambda _n: "/usr/bin/dosbox-x"),
          mock.patch("dosbox_x_server.subprocess.run",
                     lambda *_a, **_k: SimpleNamespace(stdout="usage: ...", stderr=""))):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "which a build with the debugger does" in str(got["message"])


def test_a_build_that_lists_the_option_but_carries_no_debugger_is_refused(
        tmp_path: Path) -> None:
    """MEASURED (tests/fixtures/build_check): a build configured with `--disable-debug` still
    lists `-break-start` in `-helpdebug`, because the option parser is there either way. What
    tells the two apart is the debugger's own text in the binary."""
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"\x00a build with the option and no debugger\x00")
    with (mock.patch("scry_core.binaries.shutil.which", lambda _n: str(binary)),
          mock.patch("dosbox_x_server.subprocess.run",
                     lambda *_a, **_k: SimpleNamespace(stdout="-break-start\n", stderr=""))):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID" and "carries no debugger" in str(got["message"]), got


def test_build_check_says_ok_and_names_the_surface_on_a_good_build(tmp_path: Path) -> None:
    """THE GREEN BESIDE THE TWO REDS. Without it both cases above pass over a
    `build_check` that raises unconditionally. The binary is a file of this case's own,
    carrying the help line a heavy-debug build compiles, and one without it says false."""
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"\x00" + binaries.DEBUGGER_MARK + b"\x00" + binaries.HEAVY_DEBUG_MARK
                       + b"\x00")
    with (mock.patch("scry_core.binaries.shutil.which", lambda _n: str(binary)),
          mock.patch("dosbox_x_server.subprocess.run",
                     lambda *_a, **_k: SimpleNamespace(stdout="-break-start\n",
                                                       stderr=""))):
        got = cast(dict[str, Any], server.build_check())
        binary.write_bytes(b"\x00" + binaries.DEBUGGER_MARK + b"\x00LOGS only\x00")
        plain = cast(dict[str, Any], server.build_check())
    assert got["status"] == "ok", got
    assert got["binary"] == str(binary)
    assert got["debugger"] is True
    assert got["heavy_debug"] is True and plain["heavy_debug"] is False, (got, plain)
    # NOT COMPARED AGAINST `registered_tools()`, which is what `build_check` itself
    # returns: both sides move together, so `registered_tools() -> []` made the
    # assertion `set() == set()`. It is held to a FLOOR and to tools named here.
    tools = set(cast("list[str]", got["tools"]))
    assert {"start", "close", "status", "build_check"} <= tools, tools
    assert len(tools) >= 20, f"the surface shrank to {len(tools)}: {sorted(tools)}"


def test_build_check_refuses_to_start_a_second_emulator_beside_a_live_one() -> None:
    """It answers by running `dosbox-x -helpdebug`, which is a SECOND process of the
    same binary -- and on a build without the debugger that is not a help listing, it
    is a full emulator for the whole 20 s bound, because this build does not refuse an
    option it does not know: it starts.

    `start` refuses exactly this, in as many words. MEASURED before the fix: with a
    live session installed, `build_check` spawned
    `['/opt/homebrew/bin/dosbox-x', '-helpdebug']` with a 20 s timeout and returned
    `ok`, while `start` in the identical state refused.

    THE SPAWN IS WATCHED, not merely the status: asserting INVALID alone would pass
    over a refusal raised AFTER the process had already been started.
    """
    install(alive=True)
    spawned: list[list[str]] = []

    def watched(cmd: list[str], **_k: object) -> object:
        spawned.append(list(cmd))
        return SimpleNamespace(stdout="-break-start\n", stderr="")

    with (mock.patch("scry_core.binaries.shutil.which", lambda _n: "/usr/bin/dosbox-x"),
          mock.patch("dosbox_x_server.subprocess.run", watched)):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "second emulator" in str(got["message"]) and "`close`" in str(got["message"])
    assert spawned == [], f"it started one anyway: {spawned}"


def test_a_limit_means_nothing_where_one_symbol_comes_back_and_is_not_refused_there(
) -> None:
    """`limit <= 0` was refused ABOVE the branch split, so it fired for `offset` and
    `linear` -- which answer with exactly one symbol and never slice.

    MEASURED before the fix: on the offset branch `limit=1` and `limit=10` returned
    byte-identical replies (the proof it is not read) while `limit=0` was refused.
    """
    install(alive=True)
    dstate.STATE.install_table([dsym.Symbol(name="_main", offset=0x1000, kind="T"),
                                dsym.Symbol(name="_next", offset=0x2000, kind="T")])
    dstate.STATE.base.update(base=0x10000)
    try:
        zero = cast(dict[str, Any], server.symbols_find(offset=0x1004, limit=0))
        assert zero["status"] == "ok", zero
        assert zero["name"] == "_main"
        # AND IT IS STILL REFUSED WHERE IT MEANS SOMETHING, or this would have moved
        # the defect rather than fixed it.
        bad = cast(dict[str, Any], server.symbols_find(name="_ma", limit=0))
        assert bad["status"] == "INVALID", bad
        assert "would return nothing" in str(bad["message"])
        # AND A CEILING, because a `limit` with no top hands a whole table back under the
        # name of a lookup. The ceiling itself is taken, one past it refused,
        # and the offset branch, which never reads `limit`, is still not corrected about it.
        top = cast(dict[str, Any], server.symbols_find(name="_", limit=placement.SYMBOLS_LIMIT_MAX))
        assert top["status"] == "ok" and top["symbols_total"] == 2, top
        over = cast(dict[str, Any],
                    server.symbols_find(name="_", limit=placement.SYMBOLS_LIMIT_MAX + 1))
        assert over["status"] == "INVALID", over
        assert f"1..{placement.SYMBOLS_LIMIT_MAX}" in str(over["message"]), over
        fine = cast(dict[str, Any], server.symbols_find(offset=0x1004, limit=10 ** 6))
        assert fine["status"] == "ok", fine
    finally:
        dstate.STATE.forget_symbols()


def test_a_bad_pattern_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    """`dosbox_symbols.plan` compiled the caller's regex bare, and `symbols_load`'s
    only guard is `except BadSymbolText`.

    End to end through the tool, that lets
    `re.PatternError: missing ), unterminated subpattern at position 0` come OUT of
    `symbols_load` -- no `status`, no `reason`, no session block. The reader that takes a
    pattern is the layer that owes the guard, and `dosbox_logs.compiled` carries it.
    """
    install(alive=True)
    src = tmp_path / "s.nm"
    src.write_text("00001000 T _main\n00002000 T _next\n", encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base="10000",
                                                   pattern="(unclosed"))
    assert got["status"] == "INVALID", got
    assert "not a usable pattern" in str(got["message"])
    assert "session" in got, "an INVALID reply must still carry the session block"
    # AND IT DOES NOT BLAME THE FILE. `BadSymbolText`'s translation prefixes the
    # caller's path, which is right for text that would not parse and wrong for an
    # argument typed at the tool: a refusal reading
    # `INVALID: /path/to/s.nm: that is not a usable pattern` names a file that is
    # perfectly readable and was read.
    assert str(src) not in str(got["message"]), (
        f"the refusal names the source file for a defect in the PATTERN: "
        f"{got['message']}")
    # THE GREEN BESIDE IT: a pattern that compiles still works, or this passes over a
    # `plan` that refuses every pattern.
    ok = cast(dict[str, Any], server.symbols_load(path=str(src), base="10000",
                                                  pattern="^_ma"))
    assert ok["status"] == "ok", ok


def test_a_read_memory_reply_carries_the_whole_data_view_and_not_just_the_row_asked_for(
) -> None:
    """The fixture held ONE row, and the reply's whole value is that EIGHT come back.

    This tool returns rows instead of a screen precisely because the debugger's data
    view holds eight of them and a positional cut fell inside them -- so the answer
    began at E040 for a caller who had asked about E000. MEASURED before this case:
    reducing `read_memory` to return only the row asked for left the ENTIRE contract
    tier green (252 passed), over the exact defect the tool exists to prevent.
    """
    seg, off = 0x0749, 0
    rows = [f"{seg:04X}:{off + 16 * i:08X} " + " ".join([f"{i:02X}"] * 16)
            + "  " + "." * 16 for i in range(8)]
    install(screen="some screen\r\n" + "\r\n".join(rows) + "\r\n")
    got = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{off:08X}"))
    assert got["status"] == "ok", got
    assert got["rows"] == rows, got
    assert len(got["rows"]) == 8, (
        f"the data view paints eight rows and {len(got['rows'])} came back: a reply "
        f"holding only the row asked for is the defect this tool was built against")


def test_read_memory_refuses_a_segment_that_will_not_fit_the_command() -> None:
    """The range check had no contract case at all: removing it left the
    whole contract tier green (252 passed, measured), and its only cover was one
    assertion in the LIVE tier -- the tier that skips itself on a machine with no
    conf."""
    seg, off = 0x0749, 0
    row = f"{seg:04X}:{off:08X} " + " ".join(["00"] * 16) + "  " + "." * 16
    install(screen=f"some screen\r\n{row}\r\n")
    got = cast(dict[str, Any], server.read_memory(ref="10000:00000000"))
    assert got["status"] == "INVALID", got
    # THE MESSAGE IS ABOUT THE ARGUMENT, not about the screen. Without the check the
    # call falls through to the row-match refusal, whose text blames the reply -- so
    # asserting only INVALID would pass over the defect.
    assert "a segment is 0x0000 to 0xFFFF" in str(got["message"]), got["message"]


def test_each_double_returns_the_field_set_the_real_method_returns() -> None:
    """The comment above the four debugging doubles claims exactly this, and it was
    FALSE for two of them.

    MEASURED by AST before the fix: `step`'s double was missing `moved` and `stalled`
    -- and `stalled` was added by the fix pass, so the double had never been
    brought forward with the fix it stands in for -- while `e9_wait`'s was missing
    `arrived_during` and `lines_examined` and INVENTED `lines_scanned`, a field the real
    method has never returned.

    A DOUBLE IS CAPTURED FROM THE REAL THING, NEVER AUTHORED FROM WHAT SOMEBODY
    BELIEVES IT LOOKS LIKE, and these four were authored. A comment saying they agree
    is a reminder, and reminders are what fail; this reads BOTH sides and compares
    them, so the claim cannot go stale again in either direction. It compares NAMES and
    not values: a stub's values are its own business, and its field set is a contract.
    """
    for name in ("step", "run_to", "watch", "log_wait"):
        branches = returned_key_sets(getattr(ds.Session, name))
        double = returned_key_sets(getattr(FakeSession, name))
        assert branches, f"nothing was read off the real {name}: this measured nothing"
        assert len(double) == 1, f"the {name} double should have one return"
        # PER BRANCH, NOT THE UNION, which is how the first version of this gate could
        # be fooled. `e9_wait` has FOUR dict returns and `run_to` two; a set
        # comprehension over all of them unions the keys, so a field present on three
        # branches and missing from the fourth was invisible -- and that is the exact
        # defect `run_to`'s own comment names ("a field that appears on one branch is a
        # field a caller must first discover the shape of the reply to read").
        # MEASURED: all four methods return an IDENTICAL key set on every branch today,
        # so this is a real invariant and not a convenience.
        for i, real in enumerate(branches):
            # A VERDICT IS WHAT TELLS TWO SHAPES APART: a wait's `TIMEOUT` carries what arrived
            # while it waited and no line, and its `verdict` says so, so the caller reads the
            # word rather than discovering the shape.
            if "verdict" in real and "verdict" in branches[0]:
                continue
            assert real == branches[0], (
                f"`{name}` return #{i} carries a different field set from its first: "
                f"missing {sorted(branches[0] - real)}, extra {sorted(real - branches[0])}"
                f". A caller cannot be asked to discover the reply's shape per branch")
        # A wait's double answers its TARGET: one of the real branches, named by the verdict.
        assert double[0] in branches if "verdict" in double[0] else double[0] == branches[0], (
            f"the `{name}` double and the real method disagree. Missing from the "
            f"double: {sorted(branches[0] - double[0])}. Invented by it: "
            f"{sorted(double[0] - branches[0])}")


def test_a_delta_longer_than_the_cap_is_cut_and_says_so() -> None:
    """The `clipped: True` branch, owned by a case that NAMES it.

    It was a tail-end assertion inside `test_a_cap_of_zero_would_lie_and_is_refused`,
    which is a case about a different guard -- so the live tier, looking for somewhere
    to delegate this branch to, delegated it to a TOOL instead and got it wrong.

    MEASURED against a real emulator: on a STOPPED machine no ordinary
    command on this build reaches a cap -- `debug("BPLIST")` is 2973 and
    `debug("HELP")`, the longest listing the debugger prints, is 3083, both under the
    4000 `debug` passes. So on a STOPPED machine this branch is not reachable live (a
    running guest's `resume` reaches its own cap, its Output pane scrolling through the
    settle, and the tool's contract says so), and it is covered HERE, on a screen built to
    exceed the cap.
    """
    out = "x" * 5000
    got = dstate.delta(out, 4000)
    assert got["clipped"] is True
    assert len(cast(str, got["screen_delta"])) == 4000, "the delta is cut to the cap"
    assert got["screen_chars"] == 5000, (
        "`screen_chars` is the WHOLE screen and not the slice -- reporting the slice's "
        "length is the defect the field exists to make visible")
    assert cast(str, got["screen_delta"]) == out[-4000:], "it keeps the TAIL"


def returned_key_sets(fn: object) -> list[frozenset[str]]:
    """The literal keys of EACH dict a function returns, one set per `return`.

    PER BRANCH and never unioned: a union cannot see a field dropped from one return of
    several, which is the shape `run_to` and `e9_wait` are most exposed to (two and four
    dict returns respectively).

    A LIMIT, said out loud: it reads dict LITERALS. A reply assembled into a variable
    and returned by name, or built with `**`, comes back short or empty -- which the
    callers guard against by asserting the result is non-empty rather than trusting it.
    """
    src = textwrap.dedent(inspect.getsource(cast(Any, fn)))
    # A METHOD THAT DELEGATES (`return frames.frame(self, ...)`, a seam of the session) is read
    # at the body it hands the call to, which is where its returns are.
    body = ast.parse(src).body[0]
    if (isinstance(body, ast.FunctionDef)
            and isinstance(last := body.body[-1], ast.Return) and isinstance(last.value, ast.Call)
            and isinstance(f := last.value.func, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.value.id in getattr(fn, "__globals__", {})
            and inspect.ismodule(fn.__globals__[f.value.id])):  # type: ignore[attr-defined]
        return returned_key_sets(getattr(fn.__globals__[f.value.id], f.attr))  # type: ignore[attr-defined]
    # A WAIT'S `**got.fields()` is the core wait's `Found`, spread whole: its fields are the keys.
    found = frozenset(f.name for f in dataclasses.fields(core_wait.Found))

    def keys(d: ast.Dict) -> frozenset[str]:
        named = {k.value for k in d.keys
                 if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        spread = any(k is None and isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                     and v.func.attr == "fields" for k, v in zip(d.keys, d.values, strict=True))
        return frozenset(named | (found if spread else set()))
    return [keys(node.value) for node in ast.walk(ast.parse(src))
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)]

def test_the_status_docstring_names_every_field_its_reply_carries() -> None:
    """An MCP caller reads this docstring and NOT the README, which `status`'s own
    docstring says -- and it then described five of eleven fields.

    The six it left out included `conf_changed_on_disk`, the one field that says the
    session no longer reproduces the config it was started from. MEASURED before the
    fix: only `alive` and `terminal_bytes_dropped` appeared by name at all.

    IT IS DERIVED AND NOT REMEMBERED, which is the point: a docstring brought up to
    date once falls behind at the next field, and nothing notices. This reads the
    REPLY and requires each key to appear in the text, so the next field added turns it
    red until it is described.
    """
    install(alive=True)
    got = cast(dict[str, Any], server.status())
    doc = server.status.__doc__ or ""
    # MATCHED AS A ROW, NOT AS A SUBSTRING. `k not in doc` is shadowed by longer
    # names: `alive` sits inside `drain_alive`, and `conf` inside `conf_digest`,
    # `conf_changed_on_disk` and the word `config`. MEASURED, both rows could be
    # deleted from the docstring and this stayed green -- over the one defect it is
    # here to catch.
    fields = {*cast(dict[str, Any], got["session"]), *dstate.process_facts()}
    unnamed = sorted(k for k in fields if not re.search(rf"^\s+{re.escape(k)}\s", doc, re.M))
    assert not unnamed, (
        f"`status` returns these and its docstring does not name them: {unnamed}. An "
        f"MCP caller reads the docstring and not the README")
    # AND IT MEASURED SOMETHING: without this, a reply that lost its session block
    # would pass by having nothing to check.
    assert len(fields) >= 11 and fields <= set(got) | set(got["session"]), got
    # A LIMIT, SAID OUT LOUD: this asks whether the field has a ROW, not whether what is
    # written beside it is true. It catches a field going UNDESCRIBED, which is what
    # happened to six of the eleven; it cannot catch one being described wrongly.


def test_read_memory_refuses_an_offset_that_will_not_fit_the_command() -> None:
    """The guard immediately below the segment one, and it was in the state the segment
    guard was FOUND in: no contract case at all, so removing it left the
    whole tier green.

    Without it the call formats `D 0000:10000` and falls through to the row-match
    refusal, whose message blames the SCREEN -- so a caller is told the debugger
    answered about somewhere else when what was wrong was their own argument.
    """
    seg, off = 0x0749, 0
    row = f"{seg:04X}:{off:08X} " + " ".join(["00"] * 16) + "  " + "." * 16
    install(screen=f"some screen\r\n{row}\r\n")
    got = cast(dict[str, Any], server.read_memory(ref="0000:00010000"))
    assert got["status"] == "INVALID", got
    # Decision 38 made the ceiling mode-aware; in the real mode this double reports,
    # 0x10000 still addresses nothing, and the refusal says so rather than blaming the
    # screen.
    assert "past 0xFFFF addresses nothing" in str(got["message"]), got["message"]


# ------------------------------------------ every bucket the plan carries, at the seam
#
# `nm` OUTPUT WITH SEVERAL BUCKETS NON-EMPTY, captured from a real listing: a long name
# (truncated_names), two statics that shorten to the same fifteen (disambiguated), a section
# label (noise) and an absolute (unplaceable). A reply full of zeroes cannot tell a
# counter that travelled from one that was defaulted, so the fixture has to make several
# of them move at once.
#
# EVERY BUCKET A DIFFERENT NUMBER, and that is the load-bearing property rather than
# tidiness: with two buckets both at zero, SWAPPING them in the reply is invisible.
# MEASURED -- the first version had `excluded_noise` and `excluded_pattern` both 0
# (`.comment` is type `N`, so it leaves as UNPLACEABLE before the noise filter ever sees
# it, and no pattern was passed), and exchanging those two fields came back GREEN.
# So: THREE section labels of a PLACEABLE type for the noise bucket, ONE `N` and ONE `A`
# for the unplaceable one, and a `pattern` that drops exactly two more.
NM_FRAGMENT = (
    "0001c2b0 T _map_demo_a_very_long_symbol_name\n"
    "0001c300 t _map_demo_helper_alpha\n"
    "0001c310 t _map_demo_helper_alphb\n"
    "0001c340 D _keepme_table\n"
    "0001c350 T _keepme_main\n"
    "0001c360 T _dropme_one\n"
    "0001c370 T _dropme_two\n"
    "0001c380 T .text\n"
    "0001c390 T .data\n"
    "0001c3a0 T .bss\n"
    "00000000 N .comment\n"
    "000003f8 A _port\n")

def test_the_caller_is_told_about_every_bucket_the_plan_carries(tmp_path: Path) -> None:
    """CONSERVATION AT THE BOUNDARY, which is the only place it is worth anything.

    `Plan.check()`'s sum grew a term and `symbols_load`'s reply did not, so an MCP
    caller got a report whose buckets do not add up to `parsed` and no field explaining
    the gap -- the exact failure `Plan`'s docstring says cannot happen.

    IT IS DERIVED FROM THE DATACLASS AND IT USED TO SAY SO WHILE LISTING SEVEN NAMES BY
    HAND, which is the same false claim one level up: a future bucket was NOT caught,
    the test simply had to be edited when one arrived -- and `overlay_idle` is the one
    that arrived and proved it.

    IT IS DERIVED BY EXCLUSION AND NOT BY TYPE, which is the correction after that. The
    first version kept the fields typed `int`, with a floor of eight against a population
    of nine -- so retyping ONE counter `int | None` dropped it out of the set (`f.type` is
    a STRING here, `"int | None"`), left eight, passed the floor, and stopped requiring
    that counter to reach the caller at all. A filter on the SHAPE of a field standing in
    for a claim about the POPULATION is exactly the wrong way round. Now every field must
    be reported unless it is named below, so a retyped counter forces a red or an
    explicit exception rather than vanishing.
    """
    import dataclasses
    # THE THREE THAT TRAVEL BY ANOTHER ROUTE, each named with its reason: `unencodable`
    # goes out truncated to eight PLUS its own length, and `symbols`/`short` are the
    # table itself rather than a number about it.
    carried_otherwise = {"unencodable", "symbols", "short"}
    fields = {f.name for f in dataclasses.fields(dsym.Plan)}
    assert carried_otherwise < fields, f"an exception names no field: {fields}"
    counters = fields - carried_otherwise
    assert "overlay_idle" in counters, counters
    # THE REPLY, NOT THE SOURCE TEXT. Grepping `inspect.getsource(symbols_load)` for
    # `plan.<counter>` is a LEXICAL test of the axis "does the counter reach the caller":
    # `getsource` returns comments and the docstring too, so a counter named in one of
    # this function's (long) comments satisfies it while the key is gone from the returned
    # dict -- and so does `_unused = plan.truncated_names`. The caller then gets a
    # reply whose buckets do not sum to `parsed`, which is the property the docstring
    # says cannot happen.
    #
    # THE FIXTURE IS CHOSEN SO SEVERAL COUNTERS ARE NON-ZERO, because a reply full of
    # zeroes cannot tell a counter that travelled from one that was defaulted.
    install()
    src = tmp_path / "prog.sym"
    src.write_text(NM_FRAGMENT, encoding="utf-8")
    reply = cast(dict[str, Any], server.symbols_load(
        path=str(src), base="0", pattern="^_(keepme|map_demo)"))
    assert reply["status"] == "ok", reply
    plan = dsym.plan(dsym.parse(NM_FRAGMENT)[0], pattern="^_(keepme|map_demo)",
                     unreadable=0)
    # WHICH REPLY KEY CARRIES WHICH BUCKET, declared. Two weaker forms were tried and
    # both are recorded because each looked right:
    #
    #   `f"plan.{c}" in inspect.getsource(symbols_load)` -- LEXICAL. `getsource` returns
    #       comments and the docstring, so a counter named in a comment satisfied it with
    #       the key gone from the reply, and so did `_unused = plan.truncated_names`.
    #   `getattr(plan, c) in reply.values()` -- VALUE MEMBERSHIP, which is identity's
    #       opposite: it asks whether that NUMBER appears anywhere, and on a real fixture
    #       several buckets share a value. MEASURED: deleting the count from the reply
    #       entirely left this case GREEN, because some other field happened to hold the
    #       same number.
    #
    # The mapping is a second statement of the reply's shape and could drift, which is
    # why `counters` is derived from the dataclass and the mapping must cover it EXACTLY:
    # a bucket added to `Plan` fails here until somebody says where it goes.
    carries = {
        "parsed": "parsed", "excluded_noise": "excluded_sections",
        "excluded_pattern": "excluded_pattern",
        "excluded_unplaceable": "excluded_unplaceable",
        "truncated_names": "truncated_names",
        "disambiguated": "disambiguated", "renamed": "renamed",
        "unreadable": "unreadable", "overlay_idle": "overlay_idle",
    }
    assert set(carries) == counters, (
        f"the mapping and the dataclass disagree: {set(carries) ^ counters}")
    for field_name, key in carries.items():
        assert key in reply, f"symbols_load's reply has no `{key}`"
        # THE TYPE BEFORE THE VALUE, because `True == 1` and `False == 0`: every counter
        # here is a COUNT, and a bucket that turned into a flag would satisfy the equality
        # below against the 0 or 1 it happens to hold, which is the one drift this loop
        # could not see.
        assert type(reply[key]) is int, (
            f"reply[{key!r}] is {type(reply[key]).__name__}, and a count is an int")
        assert reply[key] == getattr(plan, field_name), (
            f"reply[{key!r}] is {reply[key]!r}, plan.{field_name} is "
            f"{getattr(plan, field_name)!r}")
    # AND THE FIXTURE HAS TO MAKE SEVERAL OF THEM MOVE, or every comparison above is
    # 0 == 0 and a reply of all zeroes would satisfy it.
    non_zero = [c for c in counters if getattr(plan, c)]
    assert len(non_zero) >= 4, f"this fixture leaves too much at zero to tell: {non_zero}"
    # A SECOND READ WITH A DIFFERENT FILTER, and this is the identity axis rather than
    # the presence one. The loop above catches a SWAP between two reply keys only when
    # their values differ, and on any one fixture some buckets coincide -- MEASURED,
    # `excluded_noise` and `excluded_pattern` were both 0 on the first version of this
    # fixture and exchanging those two fields in the reply came back GREEN.
    #
    # Reading the SAME file twice under different `pattern`s moves the buckets by
    # different amounts, so a fixed swap has to survive BOTH vectors to stay invisible.
    other = cast(dict[str, Any], server.symbols_load(
        path=str(src), base="0", pattern="^_dropme"))
    plan2 = dsym.plan(dsym.parse(NM_FRAGMENT)[0], pattern="^_dropme", unreadable=0)
    for field_name, key in carries.items():
        assert other[key] == getattr(plan2, field_name), (
            f"second read: reply[{key!r}] is {other[key]!r}, plan.{field_name} is "
            f"{getattr(plan2, field_name)!r}")
    moved = [k for k in carries.values() if reply[k] != other[k]]
    assert len(moved) >= 3, f"the two reads barely differ, so a swap could hide: {moved}"
    # THE LIMIT, said out loud: two buckets equal in BOTH reads could still be exchanged
    # unseen. What closes that is a third fixture, not a stronger assertion here.
    # AND `unencodable` REACHES THE CALLER ANYWAY, so the exception list cannot become a
    # hiding place: it goes out truncated to eight PLUS its own length.
    assert "unencodable_total" in reply, sorted(reply)


# ------------------------------------- asking a SECTIONED table where you have stopped

def test_a_sectioned_table_answers_a_linear_address_without_being_told_the_section(
        tmp_path: Path) -> None:
    """THE BRANCH A CALLER WHO HAS STOPPED SOMEWHERE ACTUALLY USES.

    A linear address answers the section question itself: it falls inside exactly one
    section's base, and picking the greatest base at or below it is the encoder's own
    arithmetic run backwards. Making the caller work the section out first would hand
    back the sum they came here to have computed.
    """
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    server.symbols_load(path=str(src),
                        section_bases={"1": "0x401000", "2": "0x423000"})
    # 0x4010F0 is 12 bytes past `_main`, which is section 1 offset 0xE4.
    got = cast(dict[str, Any], server.symbols_find(linear="4010F0"))
    assert got["name"] == "_main" and got["section"] == 1, got
    assert got["delta"] == 0xC, got
    # AND THE OTHER SECTION, at the SAME distance past its own symbol -- which a table
    # that ignored the section index would answer with `_main` too, because 0x4230F0 is
    # also above section 1's base.
    other = cast(dict[str, Any], server.symbols_find(linear="4230F0"))
    assert other["name"] == "_table" and other["section"] == 2, other
    assert other["delta"] == 0xC, other


def test_an_offset_alone_is_refused_on_a_sectioned_table(tmp_path: Path) -> None:
    """The sections OVERLAP, so a bare offset exists in every one of them. Answering it
    would mean picking one silently -- which is exactly the confident wrong answer this
    package treats as worse than a refusal."""
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    server.symbols_load(path=str(src),
                        section_bases={"1": "0x401000", "2": "0x423000"})
    got = cast(dict[str, Any], server.symbols_find(offset=0xE4))
    assert got["status"] != "ok", got
    assert "SECTIONED" in str(got["message"]), got["message"]
    # WITH THE SECTION NAMED it answers, and the two sections give DIFFERENT symbols for
    # the same offset -- which is the whole reason the bare form is refused.
    one = cast(dict[str, Any], server.symbols_find(offset=0xE4, section=1))
    two = cast(dict[str, Any], server.symbols_find(offset=0xE4, section=2))
    assert (one["name"], two["name"]) == ("_main", "_table"), (one, two)


def test_an_address_below_every_section_is_refused_rather_than_folded(
        tmp_path: Path) -> None:
    """Below every base there is no section to subtract, and choosing one anyway would
    produce a negative offset and then the nearest symbol of whatever section that was."""
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    server.symbols_load(path=str(src),
                        section_bases={"1": "0x401000", "2": "0x423000"})
    got = cast(dict[str, Any], server.symbols_find(linear="0x1000"))
    assert got["status"] != "ok", got
    assert "below every section" in str(got["message"]), got["message"]


def test_a_flat_table_refuses_a_question_about_a_section_it_does_not_have(
        tmp_path: Path) -> None:
    """A flat table has exactly one section, so naming a different one is a question
    about something that is not there -- and answering it with the flat symbols would be
    agreeing with a mistaken premise."""
    install()
    src = tmp_path / "prog.sym"
    src.write_text(NM_FRAGMENT, encoding="utf-8")
    server.symbols_load(path=str(src), base="0")
    got = cast(dict[str, Any], server.symbols_find(offset=0x1c350, section=2))
    assert got["status"] != "ok", got
    assert "loaded FLAT" in str(got["message"]), got["message"]
    # AND WITHOUT IT, the same question answers.
    ok = cast(dict[str, Any], server.symbols_find(offset=0x1c350))
    assert ok["name"] == "_keepme_main", ok


def test_nothing_below_the_asked_offset_names_the_section_it_looked_in(
        tmp_path: Path) -> None:
    """"Nothing in the table" is a statement about the TABLE, and on a sectioned load it
    has to say WHICH section it examined -- otherwise a caller reads it as a statement
    about the whole program."""
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    server.symbols_load(path=str(src),
                        section_bases={"1": "0x401000", "2": "0x423000"})
    got = cast(dict[str, Any], server.symbols_find(offset=0x10, section=1))
    assert got["status"] != "ok", got
    assert "section 1" in str(got["message"]), got["message"]


def test_the_server_declares_instructions_and_they_name_what_a_caller_needs() -> None:
    """The `instructions` field is how the PROTOCOL hands a session the server's own contract.

    Nothing else asserts it: deleting the `instructions=` argument, or truncating it to "",
    leaves the suite green while every session loses the text. The failure direction is silence,
    which is what a compliant server looks like.

    It asserts the CLAIMS, not the wording, and the claims it pins are the ones easiest to get
    FALSE: `build_check` described as validating a reading, which it does not, and the console
    reader described as taking a `pattern`, which it does not have.
    """
    text = server.mcp.instructions
    assert text, "the server declares no instructions at all"
    # ABSENCE, not just presence: a phrase that must not be there is not checked by
    # asserting the ones that must.
    for phrase, why in (
        ("ToolSearch", "the deferred-tools rule is the session's own, loaded every session"),
        ("validates the session",
         "build_check answers about the BUILD, never about a reading: a session is not "
         "something it validates"),
        ("console reader", "the pattern belongs to e9; `debug` takes only `command`"),
        ("cycles", "the guest-clock rule is the session's own, and a verbatim second copy here "
                   "is the duplication the deleted SessionStart hook was killed for"),
    ):
        assert phrase not in text, f"the instructions carry {phrase!r}: {why}"
    assert "BUILD" in text and "REFUSES" in text, (
        "build_check must be described as what it is: a precondition check that refuses while a "
        "session is live"
    )
    assert "read_memory" in text, (
        "this server's own docstrings say a VALUE goes through registers/read_memory/memdump; "
        "instructions naming only e9 and debug send a caller to the positional tail"
    )


# ============================ the name layer: breakpoints and watches ============

class NamesFake:
    """A session double for the name-layer tools: it holds a mutable BPLIST so arming and
    clearing are visible to `breakpoint_list`, and answers `where`/`registers` so the
    server can derive a seg:off. Real vs protected mode and the CS/DS selectors are set by
    the test, since they are exactly what the derivation turns on."""

    survey_text = ""      # its stop survey paints no screen, so no code pane

    def __init__(self, *, mode: str = "Pr32", cs: str = "00A7", ds_: str = "00AF",
                 conf: Path | None = None, arm_fails: bool = False,
                 watched: bool = True, input_port: int | None = None) -> None:
        self.mode, self.cs, self.ds = mode, cs, ds_
        self._peek_carry = ""                # `Session.await_stop` runs on this double
        self.arm_fails = arm_fails
        # THE GUEST RUNS: one switch that makes every console method refuse the way the
        # real ones do (where, registers, the list, arming, clearing, a watch, a load), and
        # `at_debugger()` say so passively -- the shape the running-guest contract is
        # written against.
        self._running = False
        self.stop_count = 0                  # bumped when `running` goes True -> False
        self.stop_unread = False             # the guest stopped and no contact has seen it yet
        self.reap_failed = ""                # what `close` reports beside the exit code
        self.ended_how = "none"              # and how it ended, in `close`'s own words
        self.mem: dict[tuple[int, int], bytes] = {}
        self.log: list[str] | None = []      # None models a session with no logfile
        self.eip = "00000000"
        self.halted = False
        self.step_running = False
        self.runto_running = False
        self.runto_elsewhere = False         # a stop of another's ends the run first
        self.control_hits = 0
        self.rows: list[dict[str, str]] = []
        self.bp_calls = 0                    # how many times the list was READ (a round trip each)
        self.survey_calls = 0                # how many one-repaint stop surveys were taken
        self.bp_raises = False               # True models a running machine: a list read refuses
        self.where_raises = False            # True models a running machine: where() refuses
        self.where_refusals = 0              # >0: refuse where() this many times, then stop
        self.alive_flag = True               # False models an emulator that has died
        self.registers_raises = False        # True models a cut pane: registers() refuses
        self.altered = False                 # live() reads this when burying a dead session
        self.dies_on_resume = False          # True: alive at perform start, dead after resume
        self.commands_sent: list[list[bytes]] = []   # every send_commands call, whole
        self.break_ins = 0                       # how many times the menu route was taken
        # THE STUB'S VIEW OF THE DRIVER, as the real one reports it: a pointer, its buttons,
        # the range the driver maps it into and the BIOS mode (text 80x25 by default).
        self.stub_protocol = inputs.STUB_PROTOCOL
        self.pointer = (320, 96)
        self.buttons = 0
        self.mouse_max = (639, 199)
        self.video_mode = 3
        self.pointer_snaps = 1                   # a text mode places the pointer on its cell
        self.reports_lost: set[int] = set()       # the reports (counted from 1) that never come
        self.reports = 0
        self.input_effect: str | None = None      # a log line the guest writes on a post
        self.after_effect: list[str] = []         # what it writes after that, for a LOOK
        self.resume_effect: list[str] = []        # what it writes during a resume
        self.scancodes_sent: list[bytes] = []     # what the serial route was handed
        self.wait_calls: list[tuple[str, float, int]] = []  # what e9_wait was asked, with the mark
        self.full_reads = 0                  # whole-log reads (`e9`), which a stop must not pay
        self.incremental_reads = 0           # reads of what is new since the last stop
        self.wait_raises: Exception | None = None  # e9_wait refuses with THIS (a gone emulator)
        self.stops_during_wait = False       # a breakpoint fires while e9_wait is looking
        self.runto_calls: list[tuple[int, int, float]] = []   # the seg:off run_to was given
        self.launch = dlaunch.Launch(conf=conf or Path("/x.conf"), cwd=Path("/"), seconds=60,
                                watched=watched, input_port=input_port)

    def alive(self) -> bool:
        return self.alive_flag

    # THE TERMINAL, derived from the same state `where()` answers from: the sequence
    # executor's wait LISTENS for the prompt instead of typing a poll, so a fake with no
    # terminal is a fake the wait cannot hear a stop on. A machine that stops after a few
    # polls (`where_refusals`) is heard after that many reads, as it was polled before.
    _screen = ""

    def _read(self, timeout: float) -> str:
        if self.where_refusals > 0:
            self.where_refusals -= 1
            return ""
        if self.where_raises or self.running:
            time.sleep(min(timeout, 0.05))
            return ""
        return dcons.PROMPT

    def _mark_stopped(self) -> None:
        pass

    def state(self) -> dict[str, object]:
        return {"alive": self.alive_flag, "running": self._running, "altered": False}

    def report_line(self) -> str:
        x, y = self.pointer
        return (f"STUB  . mouse x={x} y={y} buttons={self.buttons} "
                f"max={self.mouse_max[0]},{self.mouse_max[1]} mode={self.video_mode} "
                f"screen=720x400")

    def send_commands(self, commands: list[bytes]) -> list[str]:
        """The stub of the real guest, carried out on this double's own state: `K` is a scan
        byte, `B` a button, `M` the pointer placed (snapped to `pointer_snaps`, as a text
        mode does), `R` the report line, handed back. THE GUEST REACTS to a post that is not
        only a report, when the test says so, by writing `input_effect` and then
        `after_effect`."""
        self.commands_sent.append(list(commands))
        reports: list[str] = []
        keys = b"".join(c[1:] for c in commands if c[:1] == b"K")
        if keys:
            self.scancodes_sent.append(keys)
        for c in commands:
            if c[:1] == b"B":
                bit = 1 << (c[1] & 0x7F)
                self.buttons = self.buttons | bit if c[1] & 0x80 else self.buttons & ~bit
            elif c[:1] == b"M":
                snap = self.pointer_snaps
                x, y = int.from_bytes(c[1:3], "little"), int.from_bytes(c[3:5], "little")
                self.pointer = (min(x, self.mouse_max[0]) // snap * snap,
                                min(y, self.mouse_max[1]) // snap * snap)
            elif c[:1] == b"R":
                self.reports += 1
                if self.reports in self.reports_lost:
                    raise ds.Invalid("host_failed", "no acknowledgement of a 'R' command "
                                     "after 3 sends")
                reports.append(self.report_line())
        acted = any(c[:1] != b"R" for c in commands)
        if acted and self.input_effect is not None and self.log is not None:
            self.log.append(self.input_effect)
            self.log.extend(self.after_effect)
        return reports

    def break_in(self, seconds: float = 5.0) -> float:
        """The channel route of the real one, headless or windowed: the machine is at the
        debugger a moment later, which the running flag's setter counts as a stop."""
        self.break_ins += 1
        self.running = False
        return 0.12

    def stop_at_bound(self) -> bool:
        return ds.Session.stop_at_bound(cast(ds.Session, self))

    def e9_mark(self) -> int:
        if self.log is None:
            raise ds.Invalid("no_channel", "this session was started without a logfile")
        return len(self.log)

    def e9_since_mark(self, mark: int) -> list[str]:
        if self.log is None:
            raise ds.Invalid("no_channel", "this session was started without a logfile")
        return list(self.log[mark:])

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        if self.log is None:
            raise ds.Invalid("no_channel", "this session was started without a logfile")
        self.incremental_reads += 1
        if offset > len(self.log):
            offset = 0                       # rewritten shorter: read from its start, as the real
        return list(self.log[offset:]), len(self.log)

    log_wait = _log_wait_as_guest

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        self.wait_calls.append((pattern, seconds, mark))
        if self.wait_raises is not None:
            raise self.wait_raises
        if self.stops_during_wait:
            self.running = False             # the stop is counted, as the real flag counts it
            raise ds.E9Stopped(f"the machine is stopped at the debugger, so a wait for "
                               f"{pattern!r} cannot end: a stopped guest writes nothing",
                               waited_s=0.4, arrived=0)
        # THE REAL METHOD'S OWN ANSWERS: a bad pattern and a bad bound are `Invalid` (not a
        # raw re.error), and an expired bound is the `TIMEOUT` verdict, which is the one
        # answer the server may read as a miss.
        rx = dlogs.compiled(pattern)
        if not 0 < seconds <= vocab.WAIT_MAX_S:
            raise ds.Invalid("bad_argument", f"a wait of {seconds} is not a bound")
        if self.log is None:
            raise ds.Invalid("no_channel", "this session was started without a logfile")
        hits = [ln for ln in self.log[mark:] if rx.search(ln)]
        if not hits:
            return {"verdict": "TIMEOUT", "arrived_during": 0,
                    "lines_examined": len(self.log) - mark, "waited_s": seconds,
                    "note": f"nothing matched {pattern!r} in {seconds}s"}
        # The effect line was appended by `send_input` BEFORE this wait began, so the
        # honest answer is the real method's: it was ALREADY there on the first read.
        return {"verdict": "TARGET", "line": hits[0], "already": True, "lines_total": len(hits),
                "lines_before": self.log[mark:].index(hits[0]), "arrived_during": 0,
                "waited_s": 0.0, "lines_examined": len(self.log) - mark}

    def where(self) -> dict[str, str]:
        if self.where_refusals > 0:
            self.where_refusals -= 1         # a machine that stops after a few polls
            raise ds.NotStopped("the machine is running; where() refuses")
        if self.where_raises or self.running:
            raise ds.NotStopped("the machine is running; where() refuses")
        return {"cs": self.cs, "eip": self.eip, "mode": self.mode}

    @property
    def running(self) -> bool:
        return self._running

    @running.setter
    def running(self, value: bool) -> None:
        if self._running and not value:
            self.stop_count += 1            # the machine came to rest: a stop, like the real one
        self._running = value

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        # A STOP NOBODY HAS READ YET: the real peek finds the prompt in the drain and counts
        # the transition then and there, so the count moves INSIDE this call and not before.
        if self.stop_unread:
            self.stop_unread = False
            self.running = False
        return not self.running

    def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
        self.alive_flag = False
        self.ended_how = "killed"
        return 0


    def console_tail(self, chars: int) -> str:
        return ""
    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.where(), self.registers()

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        """ONE repaint's worth, like the real one: the list comes with the pane, so this
        counts as a survey and NOT as a `breakpoints()` read (`bp_calls` stays)."""
        self.survey_calls += 1
        return self.where(), self.registers(), [dict(r) for r in self.rows]

    def registers(self) -> dict[str, str]:
        if self.registers_raises:
            raise ds.NotStopped("a cut pane: no register pane came back")
        if self.running:
            raise ds.NotStopped("no register pane came back from `BPLIST` (emulator running)")
        return {"CS": self.cs, "DS": self.ds, "EIP": self.eip}

    def e9(self, pattern: str, limit: int) -> tuple[list[str], int]:
        if self.log is None:
            raise ds.Invalid("no_channel", "this session was started without a logfile")
        self.full_reads += 1
        hit = [ln for ln in self.log if re.search(pattern, ln)]
        return hit[-limit:], len(hit)

    def breakpoints(self) -> list[dict[str, str]]:
        self.bp_calls += 1
        if self.bp_raises or self.running:
            raise ds.NotStopped("the machine is running; the debugger took no list")
        return [dict(r) for r in self.rows]

    def read_memory(self, seg: int, off: int, mode: str | None = None) -> list[str]:
        return [f"{seg:04X}:{off:04X} 00 11 22 33"]

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        return self.mem.get((seg, off), bytes(n))[:n]

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        """What was asked, recorded BEFORE the console check, so a case can tell a dump
        refused by the tool from one the session was handed and turned down."""
        self.memdump_calls = getattr(self, "memdump_calls", []) + [(seg, off, length)]
        self._console()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(length))
        return dest

    def write_memory(self, seg: int, off: int, data: bytes,
                     mode: str | None = None) -> dict[str, object]:
        self._console()
        self.mem[(seg, off)] = data
        return {"bytes_written": len(data), "readback": data.hex(), "verified": True}

    def resume(self) -> dict[str, object]:
        if self.dies_on_resume:
            self.alive_flag = False          # the guest's bound expired during the run
        if self.log is not None:
            self.log.extend(self.resume_effect)   # what the guest wrote while it ran
        return {"halted": self.halted,
                "stopped_at": {"cs": self.cs, "eip": self.eip, "mode": self.mode},
                "screen": "ooooOutputoooo\r\nI-> _"}

    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        self.running = self.step_running          # a step that ran away leaves it running
        return {"running": self.step_running, "completed": count, "moved": True,
                "stalled": 0, "before": {"cs": self.cs, "eip": self.eip, "mode": self.mode},
                "after": {"cs": self.cs, "eip": self.eip, "mode": self.mode}}

    def run_to(self, segment: int, offset: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        self.runto_calls.append((segment, offset, seconds))
        self.last_control = control
        ctl = (contract.unavailable("no control was named") if control is None else
               {"at": f"{control[0]:04X}:{control[1]:04X}", "hits": self.control_hits,
                "removed": True})
        # `runto_running` models a bound that ran out: the real one interrupts the run there,
        # so the machine comes back stopped with a TIMEOUT; `runto_elsewhere` a stop of another's.
        verdict = ("TIMEOUT" if self.runto_running else
                   "OTHER_STOP" if self.runto_elsewhere else "TARGET")
        return {"verdict": verdict, "target": f"{segment:04X}:{offset:04X}",
                "stopped_at": {"cs": self.cs, "eip": self.eip, "mode": self.mode},
                "waited_s": 0.0, "breakpoint_removed": True, "control": ctl,
                "note": "" if verdict == "TARGET" else f"{verdict.lower()}: not at the target"}

    def command(self, text: str, **_k: object) -> str:
        if text.startswith("BPDEL "):
            idx = text.split()[1]
            self.rows = [r for r in self.rows if r.get("index") != idx]
        return ""

    def arm_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        if self.running:
            raise ds.NotStopped("the machine is running; nothing was armed")
        if self.arm_fails:
            raise ds.Invalid("not_stopped", "the machine is running; nothing was armed")
        entry = f"BP {seg:04X}:{off:04X}"
        self.rows.append({"index": f"{len(self.rows):02d}", "entry": entry})
        return {"target": f"{seg:04X}:{off:04X}", "entry": entry, "breakpoints": self.rows}

    def _console(self) -> None:
        if self.running:
            raise ds.NotStopped("the machine is running; the console takes no command")

    def clear_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        self._console()
        entry = f"BP {seg:04X}:{off:04X}"
        before = len(self.rows)
        self.rows = [r for r in self.rows if r["entry"] != entry]
        return {"entry": entry, "removed": len(self.rows) < before}

    def breakpoint_interrupt(self, number: int, ah: int | None = None) -> str:
        self._console()
        entry = dcons.interrupt_row(number, ah)
        self.rows.append({"index": f"{len(self.rows):02d}", "entry": entry})
        return f"DEBUG: Set interrupt breakpoint at INT {number:02X}"

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        self._console()
        entry = dcons.interrupt_row(number, ah)
        before = len(self.rows)
        self.rows = [r for r in self.rows if r["entry"] != entry]
        return {"entry": entry, "removed": len(self.rows) < before}

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        if self.running:      # the REAL one wraps its NotStopped into a plain Invalid
            raise ds.Invalid("unexpected_answer",
                "no register pane came back, so this console is not taking "
                             "commands")
        self.loads = getattr(self, "loads", 0) + 1
        return [("loaded", 0)]

    def selector(self, reg: str) -> dict[str, int]:
        if self.running:      # likewise: a plain Invalid in the real session
            raise ds.Invalid("unexpected_answer", "no register pane came back")
        return {"base": 0x00400000, "limit": 0x0023FFFF, "type": 0x1B}

    def watch(self, segment: int | None = None, offset: int | None = None,
              linear: int | None = None) -> dict[str, object]:
        self._console()
        seg, off = int(segment or 0), int(offset or 0)
        armed = f"BPPM {seg:04X}:{off:08X}" if self.mode.startswith("Pr") \
            else f"BPMEM {seg:04X}:{off:04X}"
        # THE REAL DEBUGGER APPENDS A TRAILING HIT COUNT to a memory-watch row that a code
        # breakpoint's does not carry -- captured, not invented, because a clean double hid
        # exactly this and a live run caught it.
        self.rows.append({"index": f"{len(self.rows):02d}", "entry": f"{armed} (00)"})
        return {"command": f"BP.. {seg:04X}:{off:04X}", "mode": self.mode,
                "addressing": "segment", "armed": armed, "breakpoints": self.rows,
                "fires_on": "a change"}


def _names(tmp_path: Path, *, symbols: list[dsym.Symbol] | None = None,
           base: int = 0x00400000, **kw: Any) -> NamesFake:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    dstate.STATE.store = dec.DeclarationStore(str(conf), path=tmp_path / "decl.json")
    dstate.STATE.install_table(symbols or [])
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": base, "limit": -1, "type": -1})
    fake = NamesFake(conf=conf, **kw)
    dstate.STATE.session = fake  # type: ignore[assignment]
    return fake


def test_decide_by_reads_the_shape_of_the_ref() -> None:
    assert placement.decide_by("_uicue_apply") == "symbol"
    assert placement.decide_by("00A7:0016DD80") == "address"


def test_a_bare_linear_address_is_refused_it_has_no_segment() -> None:
    with pytest.raises(ds.Invalid, match="no segment to arm at"):
        placement.parse_seg_off("0x400000")
    assert placement.parse_seg_off("00A7:16DD80") == (0xA7, 0x16DD80)


def test_target_for_takes_the_selector_in_protected_mode_and_the_paragraph_in_real() -> None:
    """The heart of decision 17: the caller gives an offset, the server gives the seg:off,
    and which it is turns on the mode. Protected: the selector CS, offset unchanged. Real:
    the load paragraph, and a high offset split so it still fits 16 bits."""
    prot = NamesFake(mode="Pr32", cs="00A7")
    assert placement.target_for(0x16DD80, "CS", prot) == (0xA7, 0x16DD80)  # type: ignore[arg-type]
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0x7DF0, "limit": -1, "type": -1})
    real = NamesFake(mode="Real")
    assert placement.target_for(0x599, "CS", real) == (0x7DF, 0x599)   # type: ignore[arg-type]
    # a high real-mode offset (a data segment) is split so off <= 0xFFFF and folds back.
    seg, off = placement.target_for(0x140E0, "DS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0x7DF0 + 0x140E0 and off <= 0xFFFF


def test_breakpoint_at_a_symbol_arms_stores_and_says_when_it_is_marked(
        tmp_path: Path) -> None:
    """S3: arming on a linker-marked public SAYS so (a fact, not a refusal), and the
    declaration is stored so it survives a rebuild."""
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T"),
            dsym.Symbol("ATRCT_RUN", 0x599, kind="T", idle=True)]     # one marked public
    _names(tmp_path, symbols=syms)
    got = server.breakpoint_at(ref="_uicue_apply")
    assert got["status"] == "ok" and got["armed"] is True
    assert got["entry"] == "BP 00A7:3D5E0"
    assert "note" not in got, "nothing to say: no note"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["_uicue_apply"]   # type: ignore[union-attr]
    marked = server.breakpoint_at(ref="ATRCT_RUN")
    assert marked["armed"] is True and marked["marked"] is True
    assert "linker's mark" in str(marked["note"])


def test_re_declaring_a_breakpoint_is_a_no_op_that_re_arms_a_lost_row(
        tmp_path: Path) -> None:
    """The owner's QA call: re-declaring is a no-op, not a refusal, so a declaration script
    survives a re-run after a rebuild. `already_stored` says which. AND the arm still runs,
    so a declaration whose debugger row was LOST (a new session cleared BPLIST) is re-armed
    rather than reported armed while absent -- the gone-then-rearm path no live case reaches
    because the live one re-declares a still-armed row."""
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T", idle=True)]  # marked, for note
    fake = _names(tmp_path, symbols=syms)
    first = server.breakpoint_at(ref="_uicue_apply")
    assert first["already_stored"] is False and first["armed"] is True
    assert first["marked"] is True and "linker's mark" in str(first["note"])
    again = server.breakpoint_at(ref="_uicue_apply")
    assert again["already_stored"] is True and again["armed"] is True
    assert len([r for r in fake.rows if r["entry"] == "BP 00A7:3D5E0"]) == 1
    # THE NOTE SURVIVES the no-op: dropping it would lose the mark warning on the repeated
    # call a rebuild makes most.
    assert again["marked"] is True and "linker's mark" in str(again["note"])
    # ROW LOST (new session), re-declared -> re-armed, not falsely reported armed.
    fake.rows.clear()
    rearmed = server.breakpoint_at(ref="_uicue_apply")
    assert rearmed["already_stored"] is True and rearmed["armed"] is True
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:3D5E0"]
    assert len(dstate.STATE.store.declarations()) == 1   # type: ignore[union-attr]


def test_re_declaring_a_change_watch_is_a_no_op_and_keeps_the_pr_caveat(
        tmp_path: Path) -> None:
    """A change-watch re-declared after a rebuild must not stack a second BPPM, and the
    protected-mode caveat rides the no-op reply too."""
    syms = [dsym.Symbol("_g_rate", 0x1234, kind="D")]
    fake = _names(tmp_path, symbols=syms, mode="Pr32")
    first = server.watch_add(ref="_g_rate", mode="change", length=4)
    assert first["already_stored"] is False and first["armed"] is True
    assert "protected-mode watch" in str(first["caveat"])
    again = server.watch_add(ref="_g_rate", mode="change", length=4)
    assert again["already_stored"] is True and again["armed"] is True
    assert "protected-mode watch" in str(again["caveat"])
    assert len([r for r in fake.rows if r["entry"].startswith("BPPM")]) == 1


def test_a_by_address_declaration_on_a_running_machine_is_kept_unarmed_not_invalid(
        tmp_path: Path) -> None:
    """REGRESSION GUARD: the already-armed check reads the live list, which refuses a
    running machine -- so it must sit inside the try that answers `unarmed`, or a
    by-address ref (which reaches arming without touching the machine) escapes as INVALID
    with the declaration already stored and no `stored` in the reply."""
    fake = _names(tmp_path, arm_fails=True)
    fake.bp_raises = True                         # the running machine refuses a list read
    bp = server.breakpoint_at(ref="00A7:0100")
    assert bp["status"] == "ok" and bp["stored"] is True and bp["armed"] is False
    # A refusal of the RUNNING kind now queues the declaration for the next stop (the
    # running-guest contract); what this guard pins is unchanged: `ok`,
    # `stored`, and never an INVALID with the declaration already in the store.
    assert bp["state"] == "pending"
    w = server.watch_add(ref="00A7:0100", mode="change", length=4)
    assert w["status"] == "ok" and w["stored"] is True and w["armed"] is False
    assert w["state"] == "pending"


def test_an_interrupt_breakpoint_is_stored_listed_cleared_and_not_double_armed(
        tmp_path: Path) -> None:
    """The whole interrupt-in-store path at the SERVER level, which the live tier alone
    covered (and it is env-gated): stored on arm, shown armed in the list, a foreign BPINT
    surfaced, re-arm is a no-op that does not stack a row, and clear removes it and disarms
    the debugger row -- by text, since the row carries no seg:off."""
    fake = _names(tmp_path)
    armed = server.breakpoint_interrupt(number=0x21)
    assert armed["stored"] is True and armed["already_stored"] is False
    assert armed["entry"] == "BPINT 21", "the row spelling the docstring promises"
    assert [r["entry"] for r in fake.rows] == ["BPINT 21"]
    listed = server.breakpoint_list()
    row = next(b for b in listed["breakpoints"] if b["ref"] == "BPINT 21")
    assert row["state"] == "armed" and listed["foreign"] == []
    # RE-ARM IS A NO-OP: no second BPINT 21 row, and the reply says already_stored.
    again = server.breakpoint_interrupt(number=0x21)
    assert again["already_stored"] is True and again["armed"] is True
    assert [r["entry"] for r in fake.rows] == ["BPINT 21"]
    # A BPINT the store did not place is FOREIGN, matched by its text.
    fake.rows.append({"index": "09", "entry": "BPINT 10"})
    assert "BPINT 10" in server.breakpoint_list()["foreign"]
    # CLEAR removes the declaration and disarms the row it owns, leaving the foreign one.
    cleared = server.breakpoint_clear(all=True)
    assert cleared["declarations_cleared"] == 1 and cleared["disarmed"] == ["BPINT 21"]
    assert [r["entry"] for r in fake.rows] == ["BPINT 10"]
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_perform_runs_steps_in_order_and_stops_at_the_first_failure(
        tmp_path: Path) -> None:
    """Decisions 2 and 3: a list of the server's own ops runs in order, and a failing step
    STOPS the sequence with a full account -- the steps that ran, which failed and why, and
    nothing after it. Here an ambiguous name fails the second step; the third never runs."""
    syms = [dsym.Symbol("_main", 0x1000, kind="T"),
            dsym.Symbol("dup", 0x2000, kind="t"), dsym.Symbol("dup", 0x3000, kind="t")]
    _names(tmp_path, symbols=syms)
    out = server.perform(steps=[
        {"op": "breakpoint_at", "ref": "_main"},
        {"op": "breakpoint_at", "ref": "dup"},          # ambiguous -> fails here
        {"op": "breakpoint_at", "ref": "_main"},        # must NOT run
    ])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert out["steps_completed"] == 1, out
    assert [r["op"] for r in out["ran"]] == ["breakpoint_at"], out   # only the first SUCCEEDED
    assert out["failed"]["op"] == "breakpoint_at", out               # the second is here
    assert "names 2 symbols" in out["message"], out


def test_perform_refuses_an_unknown_op(tmp_path: Path) -> None:
    """The vocabulary is the server's own op names. An unknown op is refused naming the
    vocabulary."""
    _names(tmp_path)
    unknown = server.perform(steps=[{"op": "warp_core"}])
    assert unknown["status"] == "INVALID" and "not a step" in unknown["message"]
    # THE REFUSAL NAMES THE VOCABULARY, not just "not a step": dropping the op list from the
    # message would leave the weaker assertion green.
    assert "resume" in unknown["message"], unknown
    # A malformed step carries failed_at like every other failure, not a missing key.
    shapeless = server.perform(steps=["registers"])   # not an {op: ...} object
    assert shapeless["status"] == "INVALID" and "not a" in shapeless["message"]
    assert shapeless["failed_at"] == 0, shapeless
    assert "available" not in shapeless["message"], "a reason, never a dict's repr"


def _guest(tmp_path: Path) -> Any:
    """A running guest whose session has a logfile, as the mouse reads its pointer back
    through it and the stub's announce is read off it."""
    fake = _names(tmp_path, watched=False)
    fake.launch = dataclasses.replace(fake.launch, logfile=Path("/e9.log"))
    fake.running = True
    return fake


def test_input_reaches_a_headless_session_and_the_mouse_needs_no_log(tmp_path: Path) -> None:
    """Every input goes into the guest, so a headless session takes keys and clicks like a
    windowed one; the mouse reads its pointer back off the stub's own line, so a session with
    no log takes it too."""
    fake = _guest(tmp_path)
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["route"] == "guest"
    assert cast(dict[str, Any], server.send_mouse(button="left"))["route"] == "guest"
    fake.launch = dlaunch.Launch(conf=Path("/x.conf"), cwd=Path("/"), seconds=60, logfile=None)
    nolog = cast(dict[str, Any], server.send_mouse(button="left"))
    assert nolog["status"] == "ok" and nolog["pointer"], nolog


def test_send_keys_composes_the_scan_bytes_as_key_commands(tmp_path: Path) -> None:
    """The keys go down as one `K` command per scan byte, the modifiers' makes first and their
    breaks last; the reply counts what went and names the route, and a list given as a bare
    string is refused rather than splatted into characters."""
    fake = _names(tmp_path, watched=False)
    fake.running = True
    got = cast(dict[str, Any], server.send_keys(keys=["a", "enter"],
                                                modifiers=["ctrl", "shift"]))
    assert got["status"] == "ok" and got["keys"] == ["a", "enter"], got
    assert got["modifiers"] == ["ctrl", "shift"]
    want = bytes([0x1D, 0x2A, 0x1E, 0x9E, 0x1C, 0x9C, 0xAA, 0x9D])
    assert fake.commands_sent == [[b"K" + bytes([b]) for b in want]], fake.commands_sent
    assert (got["route"], got["posted"], got["bytes"], got["ticks"]) == ("guest", 2, 8, 8)
    assert "activated" not in got and "restored" not in got and "focus" not in got, got
    empty = cast(dict[str, Any], server.send_keys(keys=[]))
    assert empty["status"] == "INVALID" and "at least one key" in empty["message"]
    astr = cast(dict[str, Any], server.send_keys(keys=cast(Any, "enter")))
    assert astr["status"] == "INVALID" and "not a string" in astr["message"]
    assert len(fake.commands_sent) == 1, "a refused call must not have sent anything"


def test_send_mouse_moves_presses_and_reads_the_pointer_back(tmp_path: Path) -> None:
    """A move (`x`, `y`), a button, or a move then a button, in one call: the pointer is read
    before (to map the screen's units onto the driver's range) and after (to prove where it
    went), and the reply carries the read-back in both units."""
    fake = _guest(tmp_path)
    fake.video_mode, fake.mouse_max = 0x13, (639, 199)
    moved = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert moved["status"] == "ok" and moved["route"] == "guest", moved
    # 320 x 200 pixels over a 640 x 200 driver range: x doubles, y stays.
    assert fake.commands_sent == [[b"R"], [b"M" + (200).to_bytes(2, "little")
                                          + (50).to_bytes(2, "little")], [b"R"]]
    assert moved["arrived"] is True and "asked" not in moved
    assert moved["pointer"]["screen"] == {"x": 100, "y": 50, "width": 320, "height": 200}
    assert moved["pointer"]["mouse"] == {"x": 200, "y": 50, "max_x": 639, "max_y": 199}
    assert moved["pointer"]["bios_mode"] == "0x13" and moved["pointer"]["buttons"] == []
    fake.commands_sent.clear()
    both = cast(dict[str, Any], server.send_mouse(x=0, y=0, button="right"))
    assert fake.commands_sent[1] == [b"M\x00\x00\x00\x00", b"B\x81", b"B\x01"], fake.commands_sent
    assert both["button"] == "right" and both["action"] == "click"
    fake.commands_sent.clear()
    held = cast(dict[str, Any], server.send_mouse(button="left", action="down"))
    assert fake.commands_sent[1] == [b"B\x80"] and held["pointer"]["buttons"] == ["left"]
    server.send_mouse(button="left", action="up")
    assert fake.commands_sent[-2] == [b"B\x00"] and fake.buttons == 0
    server.send_mouse(button="middle", action="double")
    assert fake.commands_sent[-2] == [b"B\x82", b"B\x02", b"B\x82", b"B\x02"]
    raw = cast(dict[str, Any], server.send_mouse(x=639, y=199, units="mouse"))
    assert raw["status"] == "ok" and raw["pointer"]["mouse"]["x"] == 639, raw
    assert raw["pointer"]["screen"]["x"] == 319


def test_a_move_the_driver_placed_elsewhere_is_said_never_rounded_away(tmp_path: Path) -> None:
    """A text mode puts the pointer on its cell and a program's own range clamps it: the
    read-back is what the reply reports, `arrived` false and `asked` beside it."""
    fake = _guest(tmp_path)
    fake.pointer_snaps = 8
    exact = cast(dict[str, Any], server.send_mouse(x=10, y=3))         # cell (10, 3)
    assert exact["arrived"] is True and exact["pointer"]["screen"]["x"] == 10, exact
    off = cast(dict[str, Any], server.send_mouse(x=21, y=3, units="mouse"))
    assert off["status"] == "ok" and off["arrived"] is False, off
    assert off["asked"] == {"x": 21, "y": 3} and off["pointer"]["mouse"]["x"] == 16, off


def test_send_mouse_refuses_before_anything_is_sent(tmp_path: Path) -> None:
    """Every refusal arrives before a byte goes down: the shape, the numbers, the vocabularies,
    a target off the screen, a mode whose units this server does not map."""
    fake = _guest(tmp_path)
    cases: list[tuple[Callable[[], dict[str, Any]], str]] = [
        (lambda: server.send_mouse(), "name a move"),
        (lambda: server.send_mouse(x=1), "BOTH `x` and `y`"),
        (lambda: server.send_mouse(x=cast(Any, 1.5), y=0), "whole number"),
        (lambda: server.send_mouse(x=cast(Any, True), y=0), "whole number"),
        (lambda: server.send_mouse(x=-1, y=0), "whole number"),
        (lambda: server.send_mouse(x=inputs.MAX_COORD + 1, y=0, units="mouse"), "to 32767"),
        (lambda: server.send_mouse(x=0, y=2**31, units="mouse"), "to 32767"),
        (lambda: server.send_mouse(button="wheel"), "button is one of"),
        (lambda: server.send_mouse(button="left", action="triple"), "action is one of"),
        (lambda: server.send_mouse(x=1, y=1, action="down"), "acts on a `button`"),
        (lambda: server.send_mouse(x=1, y=1, units="pixels"), "units is one of"),
    ]
    for call, words in cases:
        got = call()
        assert got["status"] == "INVALID" and words in got["message"], (words, got)
    assert fake.commands_sent == [], "a refused call must not have sent anything"
    # the screen's own bounds, read from the stub: refused after the report, before the move
    off = cast(dict[str, Any], server.send_mouse(x=80, y=0))            # text 80 x 25
    assert off["status"] == "INVALID" and "outside the screen, 80 x 25" in off["message"], off
    raw = cast(dict[str, Any], server.send_mouse(x=640, y=0, units="mouse"))
    assert raw["status"] == "INVALID" and "outside the driver's range" in raw["message"], raw
    fake.video_mode = 0x101                                            # a VESA mode
    vesa = cast(dict[str, Any], server.send_mouse(x=1, y=1))
    assert vesa["status"] == "INVALID" and "units='mouse'" in vesa["message"], vesa
    assert all(cmds == [b"R"] for cmds in fake.commands_sent), fake.commands_sent
    ok = cast(dict[str, Any], server.send_mouse(x=1, y=1, units="mouse"))
    assert ok["status"] == "ok" and ok["pointer"]["screen"]["available"] is False, ok
    # THE TOP of the argument passes it and meets the driver's own range instead.
    top = cast(dict[str, Any], server.send_mouse(x=inputs.MAX_COORD, y=0, units="mouse"))
    assert "outside the driver's range" in top["message"], top


def test_a_stub_that_never_reports_is_named_and_a_malformed_report_refused(
        tmp_path: Path) -> None:
    """The pointer's read-back is the stub's line: a stub that stopped reading the port is the
    instrument broken (`host_failed`), never a pointer that did not move; and a report in
    another shape is refused rather than half-read."""
    fake = _guest(tmp_path)
    fake.reports_lost = {1}
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "no acknowledgement" in got["message"], got
    with pytest.raises(ds.Invalid, match="not in its shape"):
        inputs.parse_report("STUB  . mouse x=1 y=2")


def test_the_stub_must_have_announced_its_protocol_before_anything_is_sent(
        tmp_path: Path) -> None:
    """An older stub reads every byte as a scan code, so a mouse command would type
    keystrokes: the announce is read off the log once, and an absent, deviceless or older
    stub is refused naming the fix. Found once, it is not searched for again."""
    fake = _guest(tmp_path)
    fake.stub_protocol = ""
    fake.log = ["Bochs port E9h: BOOT  . start"]
    none = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert none["status"] == "INVALID" and "INJECT.COM" in none["message"], none
    fake.log.append("Bochs port E9h: STUB  . inject device=absent")
    absent = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert "integration device=true" in absent["message"], absent
    fake.log.append("Bochs port E9h: STUB  . inject device=present")
    old = cast(dict[str, Any], server.send_mouse(button="left"))
    assert "protocol none" in old["message"] and "another INJECT.COM" in old["message"], old
    assert fake.commands_sent == []
    fake.log.append("Bochs port E9h: STUB  . inject device=present proto=2")
    stale = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert "protocol 2" in stale["message"] and fake.commands_sent == [], stale
    fake.log.append(f"Bochs port E9h: STUB  . inject device=present proto={inputs.STUB_PROTOCOL}")
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["status"] == "ok"
    assert fake.stub_protocol == inputs.STUB_PROTOCOL
    fake.log.clear()
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["status"] == "ok"


E9_KEY_ACT = "Bochs port E9h: [+  66.628] ACT   . key_cue_a=0 b=-1 on=0"


def test_send_keys_with_an_expectation_confirms_the_guest_reacted(tmp_path: Path) -> None:
    """THE TWO-CHANNEL HALF: a key is not delivered because it was posted, it is delivered
    because the GUEST reacted. With `expect` the tool marks the log BEFORE the post, posts,
    and waits for a NEW line matching it; the reply then says the effect was SEEN and quotes
    the line. The mark is asserted to be the pre-post position, because a mark taken after
    the post would hide a reaction that landed at once."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    fake.input_effect = E9_KEY_ACT
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=5))
    assert got["status"] == "ok" and got["posted"] == 1, got
    # `seen_before_waiting`, not `already`: the reaction was written AFTER the post (the
    # fake appends it on send) and was there when the wait first looked from the mark, and
    # `lines_before` says nothing sat between the mark and it (measured).
    assert got["verify"] == {"checked": True, "seen": True, "expected": "key_cue_a",
                             "verdict": "TARGET", "line": E9_KEY_ACT,
                             "seen_before_waiting": True, "lines_before": 0, "waited_s": 0.0,
                             "lines_total": 1}, got["verify"]
    assert "already" not in got["verify"] and "effect" not in got
    # the mark is 1 line, taken before the post
    assert fake.wait_calls == [(inputs.program_reaction("key_cue_a"), 5, 1)], fake.wait_calls
    # THE DEFAULT BOUND is a named constant, passed through when `seconds` is omitted.
    server.send_keys(keys=["a"], expect="key_cue_a")
    assert fake.wait_calls[-1][1] == inputs.EFFECT_WAIT_DEFAULT_S


def test_send_keys_reports_a_swallowed_key_as_a_miss_not_a_success(tmp_path: Path) -> None:
    """THE FALSE SUCCESS THIS EXISTS TO REFUSE. The guest swallows the key (a modal had the
    focus) and writes nothing, AND an earlier line already matches the pattern -- the cue
    fired at some point before this post. The wait's verdict is TIMEOUT, its note says the
    guest did not react, the reply still reports the post that happened (a miss is not
    'nothing was sent'), and the stale line is NOT served as the reaction: the wait was asked
    from the mark, past it."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start", E9_KEY_ACT]   # a STALE match
    fake.input_effect = None                                              # the guest is silent
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=2))
    assert got["status"] == "ok" and got["verify"]["verdict"] == "TIMEOUT", got
    assert "miss on the pattern" in got["verify"]["note"], got["verify"]
    assert got["posted"] == 1 and got["route"] == "guest", got     # the post is still reported
    assert got["verify"]["checked"] is True and got["verify"]["seen"] is False, got["verify"]
    # from PAST the stale line
    assert fake.wait_calls == [(inputs.program_reaction("key_cue_a"), 2, 2)], fake.wait_calls
    assert fake.scancodes_sent == [bytes([0x1E, 0x9E])]


def test_send_keys_an_instrument_that_broke_is_not_reported_as_a_miss(
        tmp_path: Path) -> None:
    """ONLY AN EXPIRED BOUND IS A MISS. The wait also refuses when the emulator is GONE or
    the log SHRUNK, and those are the instrument breaking, not the guest ignoring the key:
    the reply says the effect could NOT be verified, leads with the wait's own words, and
    never claims the program swallowed anything. Seen red: catching the base class turned a
    dead emulator into "the guest did not react ... the emulator is GONE"."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.wait_raises = ds.Invalid("session_broken", "the emulator is GONE, 0.2s into a 10.0s wait")
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert got["status"] == "INVALID" and got["posted"] == 1, got
    assert got["verify"] == {"checked": False, "expected": "key_cue_a",
                             "why": "the emulator is GONE, 0.2s into a 10.0s wait"}, got
    assert "could NOT be verified" in got["message"] and "GONE" in got["message"], got["message"]
    assert "miss on the pattern" not in got["message"], got["message"]


def test_send_keys_without_an_expectation_says_it_did_not_verify(tmp_path: Path) -> None:
    """No `expect`, no verification -- and the reply SAYS so instead of letting `posted`
    read as delivered. `verify.checked` is False with the reason, so a caller cannot take
    the ok for a landing. And `seconds` with nothing to bound is REFUSED, not ignored."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "ok" and got["posted"] == 1, got
    assert got["verify"]["checked"] is False and "expect" in got["verify"]["why"], got
    assert fake.wait_calls == []
    orphan = cast(dict[str, Any], server.send_keys(keys=["a"], seconds=5))
    assert orphan["status"] == "INVALID" and "silently ignored" in orphan["message"], orphan
    assert len(fake.commands_sent) == 1, "the refused call must not have posted"


def test_send_keys_expectation_that_cannot_be_checked_is_refused_before_the_post(
        tmp_path: Path) -> None:
    """A post cannot be taken back, so everything that would make the verification
    impossible is refused BEFORE it: no logfile (no channel to see a reaction in), a
    pattern that is empty or not a regex, a wait that is not a bound or not a number (a
    `perform` step hands values over untyped). `commands_sent` stays empty -- the key was NOT
    sent and then reported unverifiable."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.log = None                                   # a session with no logfile
    nolog = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert nolog["status"] == "INVALID" and "logfile" in nolog["message"], nolog
    fake.log = []
    badrx = cast(dict[str, Any], server.send_keys(keys=["a"], expect="(unclosed"))
    assert badrx["status"] == "INVALID" and "pattern" in badrx["message"].lower(), badrx
    nobound = cast(dict[str, Any], server.send_keys(keys=["a"], expect="x", seconds=0))
    assert nobound["status"] == "INVALID" and "bound" in nobound["message"], nobound
    # UNTYPED VALUES, as a perform step delivers them: a TypeError out of the comparison or
    # the regex compiler is a traceback the tool wrapper does not translate.
    astr = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": "x", "seconds": "3"}]))
    assert astr["status"] == "INVALID" and "is a number" in astr["message"], astr
    nonstr = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": 5}]))
    assert nonstr["status"] == "INVALID" and "expect is a string" in nonstr["message"], nonstr
    assert fake.commands_sent == [], "a refused verification must not have posted anything"
    empty = cast(dict[str, Any], server.send_keys(keys=["a"], expect=""))
    assert empty["status"] == "ok" and "unverified" in empty["summary"], "empty is not given"


def test_send_mouse_takes_the_same_expectation(tmp_path: Path) -> None:
    """The mouse half verifies through the same path: a click OR a move with `expect` is
    confirmed or reported missed exactly as a key is, and a miss still carries the
    pointer's read-back."""
    fake = _guest(tmp_path)
    fake.input_effect = "Bochs port E9h: [+   1.000] UI    . ask via CLICK on button 0"
    hit = cast(dict[str, Any], server.send_mouse(button="left", expect="via CLICK"))
    assert hit["status"] == "ok" and hit["verify"]["seen"] is True, hit
    moved = cast(dict[str, Any], server.send_mouse(x=10, y=20, expect="via CLICK"))
    assert moved["status"] == "ok" and moved["verify"]["seen"] is True, moved
    assert fake.commands_sent[-2] == [b"M" + (80).to_bytes(2, "little")
                                      + (160).to_bytes(2, "little")]
    fake.input_effect = None
    miss = cast(dict[str, Any], server.send_mouse(button="left", expect="via CLICK",
                                                  seconds=1))
    assert miss["status"] == "ok" and miss["verify"]["verdict"] == "TIMEOUT", miss
    assert miss["pointer"]["mouse"]["x"] == 80 and miss["route"] == "guest", miss


def test_perform_stops_at_a_send_keys_step_whose_expectation_missed(tmp_path: Path) -> None:
    """Decision 3 meets the driver: a sequence whose key was swallowed ENDS there with the
    wait's TIMEOUT, naming the step, rather than carrying on as if the program had taken the
    key; the step is in `ran`, with its post and its miss."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": "key_cue_a", "seconds": 1},
        {"op": "status"}]))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 1 and "step 1 ('send_keys')" in out["note"], out
    assert out["ran"][0]["reply"]["posted"] == 1, out["ran"][0]
    assert "status" not in [r["op"] for r in out["ran"]], "the steps after it were not sent"


def test_run_to_takes_a_symbol_or_an_address_like_the_readers_do(tmp_path: Path) -> None:
    """Decision 11 reaches `run_to`: a symbol resolves through the same path the breakpoint
    and reader tools use (the code selector in protected mode, the paragraph in real mode),
    a raw SEG:OFF is taken as written, and a name absent from this build is refused before
    anything runs. The reply names the ref and the target it resolved to."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T"),
                                     dsym.Symbol("twice", 0x10, kind="t"),
                                     dsym.Symbol("twice", 0x20, kind="t")])
    by_name = cast(dict[str, Any],
                   server.run_to(ref="_uicue_apply", control="0000:0020", seconds=5))
    assert by_name["status"] == "ok" and by_name["verdict"] == "TARGET", by_name
    assert fake.runto_calls == [(0xA7, 0x3D5E0, 5)], fake.runto_calls   # CS, the symbol's offset
    # `target` is the SESSION'S spelling, handed back untouched (a second spelling beside
    # the note that quotes the first is two names for one address).
    assert by_name["ref"] == "_uicue_apply" and by_name["target"] == "00A7:3D5E0"
    by_addr = cast(dict[str, Any], server.run_to(ref="F000:0E05", control="0000:0020"))
    assert fake.runto_calls[-1] == (0xF000, 0xE05, 30.0)
    assert by_addr["target"] == "F000:0E05", by_addr
    absent = cast(dict[str, Any], server.run_to(ref="_nobody", control="0000:0020"))
    assert absent["status"] == "INVALID" and "not in the symbol table" in absent["message"], absent
    twice = cast(dict[str, Any], server.run_to(ref="twice", control="0000:0020"))
    assert twice["status"] == "INVALID" and "names 2 symbols" in twice["message"], twice
    empty = cast(dict[str, Any], server.run_to(ref="", control="0000:0020"))
    assert empty["status"] == "INVALID", empty            # not a DeclarationError traceback
    assert len(fake.runto_calls) == 2, "a refused ref must not have run anything"
    # THE OLD SPELLING IS GONE: the numeric pair is not a parameter any more.
    old = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_to", "segment": 0, "offset": 0x10, "control": "0000:0020"}]))
    assert old["status"] == "INVALID" and "bad arguments" in old["message"], old


def test_scan_sequence_composes_set1_makes_and_breaks_in_order() -> None:
    """The serial route's bytes: modifiers' makes, each key's make and break, the
    modifiers' breaks in reverse; an extended key repeats its E0 prefix on the break; an
    unknown name or a modifier a DOS keyboard lacks is refused with nothing composed."""
    assert inputs.scan_sequence(["a"], "-") == bytes([0x1E, 0x9E])
    assert inputs.scan_sequence(["a", "enter"], "-") == bytes([0x1E, 0x9E, 0x1C, 0x9C])
    assert inputs.scan_sequence(["a"], "shift") == bytes([0x2A, 0x1E, 0x9E, 0xAA])
    assert inputs.scan_sequence(["up"], "ctrl+alt") == bytes(
        [0x1D, 0x38, 0xE0, 0x48, 0xE0, 0xC8, 0xB8, 0x9D])
    assert inputs.scan_sequence(["F11"], "-") == bytes([0x57, 0xD7])   # names are case-free
    with pytest.raises(ds.Invalid, match="unknown key name"):
        inputs.scan_sequence(["a", "bogus"], "-")
    with pytest.raises(ds.Invalid, match="no command key"):
        inputs.scan_sequence(["a"], "cmd")


def test_send_keys_refuses_a_stopped_machine_and_the_cap_and_a_miss_blames_no_window(
        tmp_path: Path) -> None:
    """A stopped machine is refused, not fed bytes that would land at the next resume; a long
    text goes in several calls; and a miss names the program, not a focus it never needed."""
    fake = _names(tmp_path, watched=False)
    fake.running = True
    fake.input_effect = E9_KEY_ACT
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert got["status"] == "ok" and got["verify"]["seen"] is True, got
    shifted = cast(dict[str, Any], server.send_keys(keys=["b"], modifiers=["shift"]))
    assert fake.scancodes_sent[-1] == bytes([0x2A, 0x30, 0xB0, 0xAA]) and shifted["ticks"] == 4
    fake.running = False
    stopped = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert stopped["status"] == "INVALID" and "STOPPED at the debugger" in stopped["message"]
    fake.running = True
    capped = cast(dict[str, Any], server.send_keys(keys=["a"] * 65))
    assert capped["status"] == "INVALID" and "at most 64" in capped["message"], capped
    assert len(fake.scancodes_sent) == 2
    fake.input_effect = None
    miss = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=1))
    assert miss["verify"]["verdict"] == "TIMEOUT", miss
    assert "focus" not in miss["verify"]["note"], miss["verify"]["note"]


def test_the_key_vocabulary_is_the_scan_table_s() -> None:
    """One table names every key the route can send, and every entry composes a make and a
    break: an extended key carries its E0 prefix on both."""
    for name, code in inputs.SCAN_SET1.items():
        seq = inputs.scan_sequence([name], "-")
        assert seq == bytes(code) + bytes(code[:-1]) + bytes([code[-1] | 0x80]), name


def test_the_shipped_stub_matches_its_source(tmp_path: Path) -> None:
    """`guest/INJECT.COM` is the assembled `guest/inject.asm`, byte for byte: a COM edited by
    hand, or a source edited without reassembling, is what this turns red on. It needs NASM
    to reassemble and SKIPS without it, saying so, rather than reporting a match it never
    checked."""
    nasm = shutil.which("nasm")
    if nasm is None:
        pytest.skip("nasm is not on PATH, so the stub cannot be reassembled to compare")
    guest = Path(str(server.__file__)).parent / "guest"
    out = tmp_path / "INJECT.COM"
    subprocess.run([nasm, "-f", "bin", str(guest / "inject.asm"), "-o", str(out)], check=True)
    assert out.read_bytes() == (guest / "INJECT.COM").read_bytes(), (
        "guest/INJECT.COM is not the assembled guest/inject.asm: reassemble it")
    assert out.stat().st_size < 1024, "the stub is meant to be tiny"


def test_drive_marks_acts_verifies_and_looks_from_the_mark(tmp_path: Path) -> None:
    """The Chrome-driver shape for a DOS program: the log is marked BEFORE the act, the act
    runs as `perform` runs it, the overall `expect` is waited for from that mark, and the
    LOOK is what the guest wrote since it (filtered, last N). A stale line before the mark
    is neither the verification nor part of the look."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.where_raises = True              # a RUNNING guest, as a key is sent to
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start", E9_KEY_ACT]   # a STALE cue
    fake.input_effect = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1 b=-1 on=1"
    asked: list[bool] = []
    where = fake.where

    def counted() -> Any:
        asked.append(True)
        return where()
    fake.where = counted  # type: ignore[method-assign]
    out = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect="key_cue_a", seconds=7,
        pattern="ACT", limit=10))
    assert out["status"] == "ok", out
    assert asked == [], "whether the guest runs is the session's flag, never a console command"
    act = out["act"]
    assert act["steps_completed"] == 1 and act["failed_at"]["available"] is False, act
    assert out["verify"]["seen"] is True and "on=1" in out["verify"]["line"], out["verify"]
    # from the mark
    assert fake.wait_calls[-1] == (inputs.program_reaction("key_cue_a"), 7.0, 2), fake.wait_calls
    e9 = out["looked"]["guest"]
    assert e9["available"] is True and e9["since_mark"] == 2, e9
    assert e9["lines_written"] == e9["lines_total"] == 1, e9
    assert e9["lines"] == [fake.input_effect], e9
    # THE CUT, THE FILTER AND THE COUNTS, each pinned by a fixture that separates them:
    # three lines land after the mark, one of which does not match `pattern`; `limit=1`
    # keeps the LAST matching one, `written` counts all three, `lines_total` the two.
    fake.log = [f"Bochs port E9h: [+   {i}.000] PERF  . tick={i}" for i in range(6)]
    mark_before = len(fake.log)
    fake.input_effect = "Bochs port E9h: [+   7.000] PERF  . tick=7"
    fake.after_effect = ["Bochs port E9h: [+   7.100] VU    . ball play=0",
                         "Bochs port E9h: [+   7.200] PERF  . tick=8"]
    out = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["b"]}],
                                             pattern="tick", limit=1))
    e9 = out["looked"]["guest"]
    assert e9["since_mark"] == mark_before, e9
    assert (e9["lines_written"], e9["lines_total"], len(e9["lines"])) == (3, 2, 1), e9
    assert e9["lines"] == [fake.after_effect[1]] and e9["pattern"] == "tick", e9
    assert out["verify"]["checked"] is False and "no `expect`" in out["verify"]["why"]
    assert "failed" not in out["act"], out["act"]


def test_drive_reports_a_miss_a_failed_act_and_refuses_what_it_cannot_do(
        tmp_path: Path) -> None:
    """A guest that did not do what was expected is the verify's TIMEOUT, with the account of
    what ran and the look beside it; a step whose own expect missed ends the act, and the
    overall expect is then not waited for (`verify` unavailable); and
    everything the call cannot honour -- no logfile, an empty act, a bad look or bound,
    seconds with no expect -- is refused before the act moves anything."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # input goes to a RUNNING guest
    fake.where_raises = True              # a RUNNING guest, as a key is sent to
    fake.input_effect = None
    miss = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                              expect="key_cue_a", seconds=1))
    assert miss["status"] == "ok" and miss["verify"]["verdict"] == "TIMEOUT", miss
    assert miss["act"]["steps_completed"] == 1 and miss["verify"]["seen"] is False, miss
    assert miss["looked"]["guest"]["lines_written"] == 0
    cut = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"], "expect": "never", "seconds": 1},
             {"op": "status"}], expect="key_cue_a"))
    assert cut["status"] == "ok" and cut["act"]["verdict"] == "TIMEOUT", cut
    assert cut["act"]["steps_completed"] == 1 and cut["verify"]["available"] is False, cut
    assert len(fake.wait_calls) == 2, "the overall expect must not be waited for after a cut act"
    # EVERY REFUSAL COMES BEFORE THE ACT MOVES ANYTHING: each of these carries a step that
    # would post a key, and none of them posts. An unknown op among the steps is refused up
    # front too, where `perform` would have run the steps before it.
    posted, waited = len(fake.commands_sent), len(fake.wait_calls)
    key = {"op": "send_keys", "keys": ["a"]}
    refusals: list[Callable[[], dict[str, Any]]] = [
        lambda: server.drive(act=[]),
        lambda: server.drive(act=[key], pattern="("),
        lambda: server.drive(act=[key], limit=0),
        lambda: server.drive(act=[key], seconds=3),
        lambda: server.drive(act=[key], settle_seconds=-1),   # 0 never waits; below is no bound
        lambda: server.drive(act=[key, {"op": "warp_core"}]),
        lambda: server.drive(act=[key, "not a step"])]
    for refusal in refusals:
        got = refusal()
        assert got["status"] == "INVALID", got
        # ONE SHAPE, whichever check refused it: the act's account, a verify and a look.
        assert {"act", "verify", "looked"} <= set(got) and "errors" not in got, got
        assert got["act"]["steps_completed"] == 0, got
    fake.log = None
    nolog = cast(dict[str, Any], server.drive(act=[key]))
    assert nolog["status"] == "INVALID" and "logfile" in nolog["message"]
    assert {"act", "verify", "looked"} <= set(nolog), nolog
    assert (len(fake.commands_sent), len(fake.wait_calls)) == (posted, waited), (
        "a refused drive must not have acted or waited")
    # `perform` refuses the same non-bound `wait`.
    assert cast(dict[str, Any], server.perform(steps=[{"op": "status"}],
                                               settle_seconds=-1))["status"] \
        == "INVALID"
    # AN EMPTY `expect` IS NO EXPECT, as everywhere an optional text is empty: the act runs and
    # nothing is verified, which the reply says.
    fake.log = []
    unchecked = cast(dict[str, Any], server.drive(act=[key], expect=""))
    assert unchecked["status"] == "ok" and unchecked["verify"]["checked"] is False, unchecked


def test_drive_carries_the_verify_refusals_own_code_when_the_instrument_broke(
        tmp_path: Path) -> None:
    """The act ran and the VERIFY could not be made because the wait's instrument broke (the
    emulator GONE, the log SHRUNK): the reply's `code` is the wait's own, not a word invented
    here, and `verify` carries it too, so a caller can tell a broken instrument from a miss
    without parsing prose."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.where_raises = True
    fake.input_effect = None
    fake.wait_raises = ds.Invalid("session_broken", "the emulator is GONE, 0.2s into a 1s wait")
    out = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                             expect="key_cue_a", seconds=1))
    assert out["status"] == "INVALID" and out["code"] == "session_broken", out
    assert "could NOT be verified" in out["message"] and "GONE" in out["message"], out
    assert out["verify"]["checked"] is False and out["verify"]["code"] == "session_broken"


def test_drive_verifies_a_stopped_guest_with_one_read_and_no_wait(tmp_path: Path) -> None:
    """A guest stopped at the debugger cannot write a line, so an act that ended at a stop is
    verified with ONE read since the mark: seen if the line is already there, a miss that
    SAYS the machine is stopped otherwise -- never a wait that burns the bound on a machine
    that could not act and then blames the program. Seen red: the wait ran its whole bound."""
    fake = _names(tmp_path, watched=True)
    fake.halted = True                    # a resume that halts at once: the act ends stopped
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    miss = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], expect="key_cue_a",
                                              seconds=5))
    assert miss["status"] == "INVALID" and miss["verify"]["seen"] is False, miss
    assert "STOPPED at the debugger" in miss["verify"]["why"], miss["verify"]
    assert fake.wait_calls == [], "a stopped guest is read, not waited for"
    # the line the guest wrote BEFORE stopping (during the act) is the verification.
    fake.resume_effect = [E9_KEY_ACT]
    seen = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], expect="key_cue_a"))
    assert seen["status"] == "ok" and seen["verify"]["seen"] is True, seen
    assert seen["verify"]["waited_s"] == 0.0 and fake.wait_calls == []


def test_drive_takes_the_act_s_own_ending_over_the_session_flag(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An act that says it ended running is waited on even when the flag reads stopped, and one
    that says it ended at a stop is read once even when the flag reads running: the act's tail
    saw the machine last."""
    fake = _names(tmp_path, watched=True)
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]

    def ended(how: str) -> Any:
        account = {"status": "ok", "ran": [], "steps_completed": 1,
                   how: True if how == "still_running" else {"stop_seq": 2}}
        return lambda *_a, **_k: account
    for how, flag_running, waits in (("still_running", False, 1), ("stopped", True, 0)):
        fake.running = flag_running
        fake.wait_calls.clear()
        monkeypatch.setattr(sequence, "run_steps", ended(how))
        server.drive(act=[{"op": "status"}], expect="key_cue_a", seconds=1)
        assert len(fake.wait_calls) == waits, (how, fake.wait_calls)


def test_a_log_that_cannot_be_read_at_a_stop_is_the_verify_s_refusal_never_a_check() -> None:
    class Gone:
        def e9_since_mark(self, mark: int) -> list[str]:
            raise ds.Invalid("no_channel", "the log went away")
    got = sequence._verify_at_a_stop(cast(ds.Session, Gone()), "key", 0)
    assert got == {"checked": False, "expected": "key", "why": "the log went away",
                   "code": "no_channel"}, got


def test_perform_a_running_ok_step_leaves_the_machine_as_it_found_it(tmp_path: Path) -> None:
    """R1's shape, `resume` then `send_keys`: the key step runs on the RUNNING guest and
    must not make the executor believe the machine stopped. Two consequences, both seen red
    when a running-OK op overwrote `running`: the TAIL still waits for the stop the resume was
    heading for and hands back the enriched reply; and a CONSOLE step after `[resume, status]`
    is held at the decision-37 boundary ("still running") rather than dispatched into a
    running machine and failing on a cut pane."""
    fake = _names(tmp_path, watched=True)
    fake.input_effect = E9_KEY_ACT
    fake.halted = False              # the resume leaves the machine running...
    server.breakpoint_at(ref="00A7:0100")   # R1 ARMS before it resumes: the stop is coming
    fake.where_refusals = 2          # ...and it stops after two polls of the tail
    # THE RESUME LETS IT RUN, and only the resume: the machine is at rest until the F5, which
    # `resume` itself checks, and away from the debugger from then on.
    released: list[bool] = []
    real_resume = fake.resume

    def resume_and_run() -> dict[str, object]:
        released.append(True)
        return real_resume()

    fake.resume = resume_and_run  # type: ignore[method-assign]
    fake.at_debugger = lambda: not released  # type: ignore[method-assign]
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "resume"},
        {"op": "send_keys", "keys": ["a"], "expect": "key_cue_a"},
        {"op": "status"}], settle_seconds=5.0))
    assert out["status"] == "ok" and out["steps_completed"] == 3, out
    assert out["ran"][1]["reply"]["verify"]["seen"] is True, out["ran"][1]
    assert "stopped" in out and "regs" in out["stopped"], out
    # the boundary half: a console op after a running-OK op still waits, and says so.
    fake.where_refusals = 0
    fake.where_raises = True
    fake.registers_raises = True
    released.clear()                  # at rest again for the next list's resume
    held = cast(dict[str, Any], server.perform(steps=[
        {"op": "resume"}, {"op": "status"}, {"op": "registers"}], settle_seconds=0.5))
    assert held["status"] == "ok" and held["verdict"] == "TIMEOUT", held
    assert held["steps_completed"] == 2 and "still running" in held["note"], held


def test_perform_waits_for_a_stop_before_a_console_step_after_a_resume(
        tmp_path: Path) -> None:
    """Decision 37: a `resume` that leaves the machine running ends the console-driven part.
    A running-OK op (`status`) may follow at once; a CONSOLE op (`registers`) makes the
    sequence WAIT for the next stop first. The fake stays running, so the wait runs out: the
    list ends there with a TIMEOUT naming the boundary, the console step never dispatched into
    the void; with no wait asked the step is refused `not_stopped`."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_raises = True            # ...and the running machine refuses where()
    # a running-OK op after resume is fine (it does not touch the console)
    ok = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0.5)
    assert ok["status"] == "ok", ok
    # a console op after resume, with the machine never stopping, ends the list (decision 37)
    blocked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0.5)
    assert blocked["status"] == "ok" and blocked["verdict"] == "TIMEOUT", blocked
    assert "still running" in blocked["note"] and blocked["steps_completed"] == 1, blocked
    unasked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0)
    assert unasked["status"] == "INVALID" and unasked["code"] == "not_stopped", unasked
    assert unasked["failed_at"] == 1, unasked


def test_perform_tail_waits_for_the_stop_and_returns_the_enriched_reply(
        tmp_path: Path) -> None:
    """When the sequence ends with the machine RUNNING, perform waits for the stop it was
    heading for and hands back the ENRICHED reply at it (registers, watches, attribution) --
    the value R1/R3 want. Here resume leaves it running and `where()` refuses twice then
    succeeds, modelling a breakpoint that fires a moment later. The reply carries `stopped`
    and NOT a stray `base` field (the tail called `_stop_reply` with no base fields)."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_refusals = 2             # ...then the machine stops (a breakpoint fires)
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=2.0)
    assert out["status"] == "ok", out
    assert "stopped" in out and "base" not in out["stopped"], out
    stop = out["stopped"]
    assert "regs" in stop and "watches" in stop and "cause" in stop, stop


def test_perform_tail_says_so_if_the_machine_never_stops(tmp_path: Path) -> None:
    """The honest other half: a sequence that ends running and does NOT stop within `wait`
    reports still_running rather than pretending it reached a stop."""
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True            # never stops
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=0.5)
    assert out["status"] == "ok", out
    assert out["verdict"] == "TIMEOUT" and "did not stop" in out["note"], out
    assert "still_running" not in out, "no boolean restates the verdict"


def test_perform_console_step_after_resume_runs_once_the_machine_stops(
        tmp_path: Path) -> None:
    """Decision 37's WIN, mid-sequence: resume leaves the machine running, and a CONSOLE op
    that follows waits for the stop and THEN runs. `where()` refuses twice (running) then
    succeeds (a breakpoint fired), so the wait bridges the resume and `registers` dispatches.
    Without the wait clearing `running`, the console op would be refused or sent into the
    void; this proves it is neither."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_refusals = 2             # ...then the machine stops
    out = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=2.0)
    assert out["status"] == "ok", out
    assert [r["op"] for r in out["ran"]] == ["resume", "registers"], out


def test_run_to_with_a_cold_control_and_an_expired_bound_is_invalid(tmp_path: Path) -> None:
    """Decision 12 of the emulator roadmap: with a control armed, a bound that ran out and a
    control that NEVER fired proves nothing about the target, so the reply is INVALID
    (`control_silent`) with the account and the interrupted stop's survey attached, and no
    verdict. A control that DID fire keeps the TIMEOUT, because then the silence is a
    measurement. A stop of another's before the control fired is `cut_by_other_stop`."""
    fake = _names(tmp_path)
    fake.runto_running = True
    cold = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020", seconds=1))
    assert cold["status"] == "INVALID" and cold["code"] == "control_silent", cold
    assert "verdict" not in cold, cold
    assert "never fired" in cold["message"] and "0000:0020" in cold["message"], cold
    assert cold["control_hits"] == 0 and cold["controls"] == [
        {"ref": "0000:0020", "at": "0000:0020", "hits_in_run": 0, "removed": True}], cold
    assert "stop_seq" in cold, "the interrupted stop is surveyed beside the refusal"
    assert cold["summary"].startswith("run_to: INVALID"), cold["summary"]
    assert fake.runto_calls[-1][:2] == (0, 0x10), fake.runto_calls
    fake.control_hits = 7
    hot = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020", seconds=1))
    assert hot["status"] == "ok" and hot["verdict"] == "TIMEOUT", hot
    assert hot["summary"] == "run_to 0000:0010: TIMEOUT at 00A7:00000000, control counted 7", (
        hot["summary"])
    fake.runto_running, fake.runto_elsewhere, fake.control_hits = False, True, 0
    cut = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020", seconds=1))
    assert cut["status"] == "INVALID" and cut["code"] == "cut_by_other_stop", cut
    fake.control_hits = 2
    elsewhere = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020"))
    assert elsewhere["status"] == "ok" and elsewhere["verdict"] == "OTHER_STOP", elsewhere
    # And WITHOUT a control the run is refused before the machine moves: one row per
    # address means a stop at the target could not be told from the target itself.
    calls = len(fake.runto_calls)
    plain = cast(dict[str, Any], server.run_to(ref="0000:0010", seconds=1))
    assert plain["status"] == "INVALID" and "no control" in plain["message"], plain
    assert len(fake.runto_calls) == calls, "nothing was sent"


def test_run_to_resolves_a_symbolic_control_and_perform_passes_one_through(
        tmp_path: Path) -> None:
    """A symbol as the control resolves through the same layer as a symbol as the target,
    even beside a raw-address target (which alone would skip the survey); and a `perform`
    step carries `control` to `run_to` like any other argument, since the step is bound
    against the live signature."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_hot", 0x3D5E0, kind="T")])
    fake.control_hits = 2
    got = cast(dict[str, Any], server.run_to(ref="00A7:00000010", control="_hot", seconds=1))
    assert got["status"] == "ok", got
    assert fake.last_control == (0xA7, 0x3D5E0), fake.last_control   # CS, the symbol's offset
    assert got["control_hits"] == 2 and got["controls"] == [
        {"ref": "_hot", "at": "00A7:3D5E0", "hits_in_run": 2, "removed": True}], got
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "run_to", "ref": "00A7:00000010", "control": "_hot", "seconds": 1}]))
    assert out["status"] == "ok" and out["steps_completed"] == 1, out
    assert out["ran"][0]["reply"]["control_hits"] == 2, out["ran"][0]


def test_every_reply_opens_with_a_summary_and_closes_with_the_session(tmp_path: Path) -> None:
    """The line the client paints is the tool's name, its arguments and its reply, so the
    reply's FIRST field is the one-line summary, on an ok reply and on an INVALID one alike,
    and the `session` block stays last. Read from a live-shaped double through the wrapper,
    which is the only place the order is decided."""
    fake = _names(tmp_path)
    ok = cast(dict[str, Any], server.registers())
    assert list(ok)[0] == "summary" and list(ok)[-1] == "session", list(ok)
    assert ok["summary"].startswith("registers: "), ok["summary"]
    fake.running = True
    refused = cast(dict[str, Any], server.registers())
    assert refused["status"] == "INVALID"
    assert list(refused)[0] == "summary" and refused["summary"].startswith("registers: INVALID")


def test_every_tool_declares_a_title_and_the_readers_a_read_only_hint() -> None:
    """`title` is what the client shows; `readOnlyHint` is what lets it run readers in
    parallel. A reader without the hint is merely slower; a WRITER with it is a lie a client
    would act on, so the writers are pinned as not read-only by name."""
    tools = {t.name: t for t in server.mcp._tool_manager.list_tools()}
    untitled = sorted(n for n, t in tools.items() if not t.title)
    assert not untitled, f"tools with no title: {untitled}"
    read_only = {n for n, t in tools.items()
                 if t.annotations is not None and t.annotations.read_only_hint}
    # EQUALITY, not containment: a new tool wrongly marked read-only must break this line,
    # and a hand-kept list of writers would not see a tool absent from both lists. The
    # readers keep the hint although the first contact after a stop applies pending
    # declarations: that write is the declaring call's, not the reader's (owner's call).
    assert read_only == {"status", "log", "log_wait", "registers", "read_memory", "find",
                         "disassemble", "call_stack",
                         "symbols_find",
                         "breakpoint_list", "watch_list", "captures", "build_check",
                         "state_list", "comment_list",
                         "screen_signature", "map_find",
                         "image_diff", "series_diff", "golden_check"}, read_only


def test_perform_after_a_run_to_that_timed_out_needs_no_tail(tmp_path: Path) -> None:
    """A `run_to` whose bound ran out hands the machine back STOPPED, interrupted where it
    stood, so the list neither waits at its tail nor at the boundary before the next console
    step: the release steps that leave the machine running are `resume`, a `step` that ran
    away and a `run_for` cut short of its stop."""
    fake = _names(tmp_path)
    fake.runto_running = True           # run_to bound expired: interrupted, stopped
    fake.control_hits = 1          # the control fired: the TIMEOUT is a measurement
    out = server.perform(steps=[{"op": "run_to", "ref": "0000:0000", "control": "0000:0020"},
                                {"op": "registers"}], settle_seconds=2.0)
    assert out["status"] == "ok" and out["steps_completed"] == 2, out
    assert "stopped" not in out and "still_running" not in out, out


def test_perform_reports_a_gone_emulator_as_gone_not_still_running(
        tmp_path: Path) -> None:
    """A dead emulator makes where() refuse exactly as a running one does, so `_wait_for_stop`
    checks alive() and the sequence says GONE, not 'still running' -- the confident wrong
    answer that would otherwise contradict the session.alive:False in the same reply. Both
    the boundary and the tail are covered."""
    # TAIL: resume leaves running, the emulator dies during the run, the wait finds it gone.
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True
    fake.dies_on_resume = True          # alive when perform starts, dead after the resume
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=0.5)
    assert out["status"] == "INVALID" and out["code"] == "session_broken", out
    assert "GONE" in out["message"], out
    # BOUNDARY: a console op after a running step, emulator gone -> refused naming GONE.
    fake2 = _names(tmp_path)
    fake2.halted = False
    fake2.where_raises = True
    fake2.dies_on_resume = True
    blocked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0.5)
    assert blocked["status"] == "INVALID" and "GONE" in blocked["message"], blocked


def test_perform_a_deep_type_error_in_a_tool_is_not_masked_as_bad_arguments(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine TypeError raised INSIDE a tool must escape as the bug it is, not be relabeled
    'bad arguments' -- the anti-pattern tool() forbids. Args are bound against the real
    signature first (a true bad-arg name IS reported), and only then is the tool called."""
    _names(tmp_path)
    # a real bad-argument name is still reported as such (bound before dispatch)
    bad = server.perform(steps=[{"op": "registers", "nope": 1}])
    assert bad["status"] == "INVALID" and "bad arguments" in bad["message"], bad
    # a TypeError from inside the tool body escapes rather than being masked
    monkeypatch.setattr(server, "registers", lambda: (_ for _ in ()).throw(TypeError("boom")))
    with pytest.raises(TypeError, match="boom"):
        server.perform(steps=[{"op": "registers"}])


def test_perform_tail_keeps_the_account_when_the_final_enrichment_refuses(
        tmp_path: Path) -> None:
    """A cut pane at the final stop must not throw away the whole sequence: `_stop_reply` is
    guarded, so a refusal there marks the enrichment unavailable while `ran`/`completed`
    stand. Here where() succeeds for the wait then registers() refuses inside `_stop_reply`."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves running
    fake.where_refusals = 1             # the wait succeeds on the next poll
    fake.registers_raises = True        # _stop_reply reads registers and it refuses (cut pane)
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=2.0)
    assert out["status"] == "ok", out   # the sequence account survives
    assert out["steps_completed"] == 1 and [r["op"] for r in out["ran"]] == ["resume"], out
    assert out["stopped"]["enrichment"]["available"] is False, out


def test_start_with_a_plan_runs_it_on_the_fresh_session_and_folds_the_boot_in(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start(plan=...)` runs the plan on the fresh session through the SAME executor, and
    folds the boot reply in under `start` (stripped of status/session). A failing plan leaves
    the session OPEN. Driven with ds.Session mocked, since start itself boots an emulator."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]
        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    made: list[Booted] = []
    def build(_l: object) -> Booted:
        b = Booted(conf=conf)
        made.append(b)
        return b

    with mock.patch("dosbox_x_server.ds.Session", build):
        out = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30,
            plan=[{"op": "registers"}]))
    assert out["status"] == "ok", out
    assert [r["op"] for r in out["ran"]] == ["registers"], out
    # THE BOOT IS FOLDED IN under `start`, stripped of status/session.
    assert out["start"]["shared"] is False and "argv" in out["start"], out
    assert "status" not in out["start"] and "session" not in out["start"], out

    # A plan that FAILS AT A STEP leaves the session OPEN (start does not close it): a symbol
    # watch with no size passes the list's check and is refused by its step. Clear the
    # session the first start installed, or this start refuses "already live" before the plan.
    dstate.STATE.session = None
    with mock.patch("dosbox_x_server.ds.Session", build):
        failed = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30,
            plan=[{"op": "watch_add", "ref": "no_such", "mode": "show"}]))
    assert failed["status"] == "INVALID" and failed["failed_at"] == 0, failed
    # annotated `object` so mypy does not narrow `dstate.STATE.session` here and then call the
    # reassignment below unreachable (ruff rewrites getattr, so the annotation is the seam).
    still_open: object = dstate.STATE.session
    assert still_open is not None, "a failed plan closed the session"
    # AND no plan short-circuits to the plain boot reply.
    dstate.STATE.session = None
    with mock.patch("dosbox_x_server.ds.Session", build):
        plain = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert plain["status"] == "ok" and "ran" not in plain and "start" not in plain, plain


def test_perform_bad_arguments_for_a_step_are_reported_not_crashed(tmp_path: Path) -> None:
    """A wrong argument name for an op is the sequence's to report -- the tool never sees the
    call, so it cannot translate it -- rather than a TypeError escaping."""
    _names(tmp_path)
    out = server.perform(steps=[{"op": "registers", "bogus": 1}])
    assert out["status"] == "INVALID" and "bad arguments" in out["message"], out


def test_start_with_a_plan_runs_it_on_the_fresh_session(tmp_path: Path) -> None:
    """Decision 2's other moment: `start(plan=...)` runs the plan through the SAME executor,
    and folds the started-reply in under `start` so a caller sees both the boot and the plan.
    Driven with a FakeSession installed by hand, since `start` itself boots an emulator."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    dstate.STATE.store = dec.DeclarationStore(str(conf), path=tmp_path / "decl.json")
    fake = NamesFake(conf=conf)
    dstate.STATE.session = fake  # type: ignore[assignment]
    # exercise the executor path start(plan=) uses, without re-booting: call _run_steps the
    # way start does, then assert the fold-in shape start applies.
    ran = sequence.run_steps(fake, [{"op": "registers"}], 1.0, server._step_ops())  # type: ignore[arg-type]
    assert ran["status"] == "ok" and ran["steps_completed"] == 1
    assert ran["ran"][0]["op"] == "registers"


def _start_on_a_booted_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                            which: bool = True, **kw: Any) -> dict[str, Any]:
    """`start` driven whole without an emulator: the session is faked at the seam `start`
    builds it through, and the boot is answered as ready at once."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    if which:
        monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
        # AND ITS VERSION, or the host's own `/usr/bin/dosbox-x -version` would run, if it has one.
        monkeypatch.setattr("scry_core.binaries.version", lambda *_a, **_k: "DOSBox-X (a stub)")
    def booted(launch: dlaunch.Launch) -> Booted:
        fake = Booted(conf=conf)
        fake.launch.input_port = launch.input_port    # the session's own, as a real one keeps
        return fake

    with mock.patch("dosbox_x_server.ds.Session", booted):
        return cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                                 **kw))


def test_start_launches_the_binary_it_resolved_and_says_which(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ladder's answer is the emulator the session runs, and the reply names it: the path,
    the rung it came from and the build's own version line, never a choice made in silence."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    mine = tmp_path / "dev" / "dosbox-x"
    mine.parent.mkdir()
    mine.write_text('#!/bin/sh\necho "DOSBox-X version dev" >&2; exit 1\n', encoding="utf-8")
    mine.chmod(0o755)
    launched: list[dlaunch.Launch] = []

    class Booted(NamesFake):
        argv = [str(mine), "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    def session(launch: dlaunch.Launch) -> Booted:
        launched.append(launch)
        return Booted(conf=conf)

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with mock.patch("dosbox_x_server.ds.Session", session):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                                binary=str(mine)))
    assert got["status"] == "ok", got
    assert [launch.binary for launch in launched] == [str(mine)]
    assert (got["binary"], got["binary_origin"], got["version"]) == (
        str(mine), "argument", "DOSBox-X version dev"), got


def test_start_with_no_rung_resolving_is_refused_before_anything_starts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    spawned: list[object] = []
    with mock.patch("dosbox_x_server.ds.Session", lambda launch: spawned.append(launch)):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "DOSBOX_X_BINARY held nothing" in got["message"] and spawned == []


def test_start_from_the_path_with_a_plan_says_which_build_under_start(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The PATH rung through the tool itself, and the plan's account carrying the three fields
    under `start` with the rest of the start facts."""
    on_path = tmp_path / "bin" / "dosbox-x"
    on_path.parent.mkdir()
    on_path.write_text('#!/bin/sh\necho "DOSBox-X version path" >&2; exit 1\n', encoding="utf-8")
    on_path.chmod(0o755)
    monkeypatch.setenv("PATH", str(on_path.parent))
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, plan=[{"op": "status"}], settle_seconds=0,
                                  which=False)
    assert got["status"] == "ok", got
    assert (got["start"]["binary"], got["start"]["binary_origin"], got["start"]["version"]) == (
        str(on_path), "PATH", "DOSBox-X version path"), got


def test_start_with_a_plan_keeps_session_as_the_last_key(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """THE ENVELOPE CLOSES WITH `session` on every reply, and the one reply with a plan did
    not: the start facts were appended AFTER it, so a reader taking the last key as the
    session block read the start facts instead. Found by a repository's session driving
    the server. The session is faked at the seam `start` builds it through, so the plan
    path runs whole without an emulator."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, plan=[{"op": "status"}], settle_seconds=0)
    assert got["status"] == "ok" and "start" in got, got
    assert list(got)[-1] == "session", f"the reply ends in {list(got)[-1]!r}, not `session`"


def test_breakpoint_clear_by_ref_takes_the_family_without_touching_watches(
        tmp_path: Path) -> None:
    """`breakpoint_clear` clears breakpoints AND interrupts (decision 10's family), and a
    watch of the same session is left alone -- that is `watch_clear`'s job."""
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T")]
    fake = _names(tmp_path, symbols=syms)
    server.breakpoint_at(ref="_uicue_apply")
    server.breakpoint_interrupt(number=0x21)
    server.watch_add(ref="00AF:0100", mode="change", length=4)
    cleared = server.breakpoint_clear(all=True)
    assert cleared["declarations_cleared"] == 2                  # bp + interrupt, not watch
    kinds = sorted(d.kind for d in dstate.STATE.store.declarations())  # type: ignore[union-attr]
    assert kinds == ["watch"], kinds
    assert any(r["entry"].startswith("BPPM") or r["entry"].startswith("BPMEM")
               for r in fake.rows), fake.rows


def test_breakpoint_at_an_ambiguous_name_is_refused_and_stores_nothing(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("dup", 0x1000, kind="t"), dsym.Symbol("dup", 0x2000, kind="t")]
    _names(tmp_path, symbols=syms)
    got = server.breakpoint_at(ref="dup")
    assert got["status"] == "INVALID" and "names 2 symbols" in str(got["message"])
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_breakpoint_at_an_unresolved_name_is_kept_not_armed(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")])
    got = server.breakpoint_at(ref="ensure_soundfont")
    assert got["status"] == "ok" and got["armed"] is False
    assert got["state"] == "unresolved"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["ensure_soundfont"]  # type: ignore[union-attr]


def test_breakpoint_list_shows_armed_unresolved_and_foreign(tmp_path: Path) -> None:
    """Decision 33: a declaration is armed/unresolved/gone, and a BP the store did not put
    there is foreign, listed and never deleted."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")            # armed
    server.breakpoint_at(ref="gone_symbol")      # unresolved
    fake.rows.append({"index": "09", "entry": "BP F000:E05B"})   # a foreign leftover
    got = server.breakpoint_list()
    states = {b["ref"]: b["state"] for b in got["breakpoints"]}
    assert states == {"_main": "armed", "gone_symbol": "unresolved"}
    assert got["foreign"] == ["BP F000:E05B"]


def test_breakpoint_clear_disarms_only_its_own_and_leaves_the_foreign(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")
    fake.rows.append({"index": "09", "entry": "BP F000:E05B"})    # foreign
    got = server.breakpoint_clear(all=True)
    assert got["declarations_cleared"] == 1
    assert got["disarmed"] == ["BP 00A7:16DD80"]
    assert {r["entry"] for r in fake.rows} == {"BP F000:E05B"}    # the foreign one stays
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_symbols_load_rearms_a_declaration_at_its_new_address(tmp_path: Path) -> None:
    """Decision 7 / example R4: a breakpoint declared by name, then a rebuild moves the
    symbol; symbols_load re-resolves and re-arms it at the new address by itself."""
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    # declare while unresolved (no table yet loaded through symbols_load)
    server.breakpoint_at(ref="_main")
    assert fake.rows == [], "nothing to arm against before a table is loaded"
    got = server.symbols_load(path=str(nm), base="400000")
    assert got["status"] == "ok"
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"]
    assert any(r["entry"] == "BP 00A7:16DD80" for r in fake.rows)


def test_watch_add_refuses_show_and_change_on_one_address(tmp_path: Path) -> None:
    """Decision 29 at the tool: one address may not be both a show and a
    change watch."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    r = server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    assert r["status"] == "ok" and r["armed"] is False
    clash = server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    assert clash["status"] == "INVALID" and "both a show AND a change watch" in str(
        clash["message"])


def test_a_protected_mode_change_watch_carries_the_paging_caveat(tmp_path: Path) -> None:
    """Phase 1's BPPM finding, surfaced: a change-watch in protected mode is armed but its
    reply says the firing is not to be trusted under paging."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], mode="Pr32")
    got = server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is True
    assert "paging host" in str(got["caveat"])


def test_watch_list_matches_a_watch_despite_its_trailing_hit_count(tmp_path: Path) -> None:
    """A memory-watch BPLIST row carries a `(00)` hit count a code breakpoint's does not.
    watch_list must match by PREFIX or the armed watch reads as `gone` AND its own entry
    reappears as `foreign` -- which a live run caught before this case existed."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], mode="Pr32")
    server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    got = server.watch_list()
    row = next(w for w in got["watches"] if w["ref"] == "g_rate")
    assert row["state"] == "armed", got
    assert row["length"] == 4 and "width" not in row, "the list speaks watch_add's word"
    assert got["foreign"] == [], got


def test_breakpoint_at_by_address_parses_the_seg_off(tmp_path: Path) -> None:
    _names(tmp_path)
    got = server.breakpoint_at(ref="00A7:16DD80")
    assert got["status"] == "ok" and got["by"] == "address" and got["armed"] is True
    assert got["entry"] == "BP 00A7:16DD80"


def test_breakpoint_at_stores_but_reports_unarmed_when_arming_fails(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    fake.arm_fails = True
    got = server.breakpoint_at(ref="_main")
    assert got["status"] == "ok" and got["armed"] is False and got["state"] == "unarmable"
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["_main"]  # type: ignore[union-attr]


def test_a_bad_by_is_refused(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")])
    assert server.breakpoint_at(ref="_main", by="guess")["status"] == "INVALID"
    assert server.watch_add(ref="_main", mode="change", length=4, by="guess")[
        "status"] == "INVALID"


def test_breakpoint_list_reports_gone_when_the_debugger_no_longer_holds_it(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x16DD80, kind="T")])
    server.breakpoint_at(ref="_main")
    fake.rows.clear()          # the debugger lost it (a close, or a hand BPDEL)
    got = server.breakpoint_list()
    assert got["breakpoints"][0]["state"] == "gone"


def test_breakpoint_list_reports_an_ambiguous_declaration_without_crashing(
        tmp_path: Path) -> None:
    _names(tmp_path)
    dstate.STATE.store.add(dec.Declaration("breakpoint", "symbol", "dup"))   # type: ignore[union-attr]
    dstate.STATE.install_table([dsym.Symbol("dup", 0x1000, kind="t"),
                        dsym.Symbol("dup", 0x2000, kind="t")])
    got = server.breakpoint_list()
    assert got["breakpoints"][0]["state"] == "ambiguous"


def test_watch_add_read_mode_stores_and_arms_nothing(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    got = server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is False and got["mode"] == "show"
    assert fake.rows == [], "a show watch must arm nothing"
    # dec 12, one word per concept: the state `watch_add` gives a placed show watch is
    # the SAME word `watch_list` and a stop's `watches` give it: a word per tool would make
    # the identical watch report two different states.
    assert got["state"] == "evaluated"
    lst = server.watch_list()
    assert lst["watches"][0]["state"] == "evaluated"


def test_watch_add_an_unresolved_change_is_kept_not_refused(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("other", 0x1000, kind="d")])
    got = server.watch_add(ref="g_gone", mode="change", length=4, fmt="u32")
    assert got["status"] == "ok" and got["armed"] is False and got["state"] == "unresolved"
    assert "g_gone" in [d.ref for d in dstate.STATE.store.declarations()]  # type: ignore[union-attr]


def test_watch_clear_disarms_change_and_leaves_read_alone(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")     # arms nothing
    server.watch_add(ref="0040:006C", mode="change", length=4)          # arms a BPPM row
    got = server.watch_clear(all=True)
    assert got["declarations_cleared"] == 2
    assert got["disarmed"], "the change-watch's entry should have been removed"
    assert dstate.STATE.store.declarations() == []   # type: ignore[union-attr]


def test_rearm_counts_unresolved_and_ambiguous(tmp_path: Path) -> None:
    nm = tmp_path / "s.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    _names(tmp_path)
    server.breakpoint_at(ref="_main")          # will resolve once loaded
    server.breakpoint_at(ref="_gone")          # stays unresolved
    got = server.symbols_load(path=str(nm), base="400000")
    assert [r["ref"] for r in got["declarations"]["unresolved"]] == ["_gone"]
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"]


def test_real_mode_placement_at_its_exact_edges() -> None:
    """Linear 0x100000 is the first address past real mode's reach and is refused; 0xFFFFF is
    the last and is taken; an offset of exactly 0x10000 is folded to a seg:off whose offset
    fits, never handed on as a 17-bit offset."""
    real = NamesFake(mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0xF0000, "limit": -1, "type": -1})
    with pytest.raises(ds.Invalid, match="past the 0xFFFFF"):
        placement.target_for(0x10000, "CS", real)   # type: ignore[arg-type]
    seg, off = placement.target_for(0xFFFF, "CS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0xFFFFF and off <= 0xFFFF, (hex(seg), hex(off))
    dstate.STATE.base.update({"base": 0x10000})
    seg, off = placement.target_for(0x10000, "CS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0x20000 and off <= 0xFFFF, (hex(seg), hex(off))


def test_a_sectioned_table_places_by_base_says_it_has_no_flat_one_and_counts_what_it_skipped(
        tmp_path: Path) -> None:
    """The section a linear address is in is the one with the greatest base below it, whatever
    the sections' numbers; a sectioned load answers the flat base's sentinel and a real-mode
    target refuses it."""
    fake = install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x423000", "2": "0x401000"}))
    assert got["status"] == "ok" and got["base"] == -1, got
    found = cast(dict[str, Any], server.symbols_find(linear="004230E4"))
    assert found["name"] == "_main" and found["delta"] == 0, found
    real = NamesFake(mode="Real")
    with pytest.raises(ds.Invalid, match="FLAT base"):
        placement.target_for(0x10, "CS", real)   # type: ignore[arg-type]
    del fake


def test_a_load_somewhere_else_replaces_the_table_and_its_types(tmp_path: Path) -> None:
    """A line the parser could not read is counted; a load at another base replaces the table
    and drops the types the earlier one carried."""
    one = tmp_path / "one.nm"
    one.write_text("00001000 D _rate\n         U _undefined\n", encoding="utf-8")
    _names(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=str(one), base="400000"))
    assert first["status"] == "ok" and first["unreadable"] == 1, first
    dstate.STATE.symbol_types["_RATE"] = "u16"           # as a types file would have set it
    again = cast(dict[str, Any], server.symbols_load(path=str(one), base="500000"))
    assert again["table_mode"] == "replaced" and dstate.STATE.symbol_types == {}, again


def test_target_for_refuses_a_real_mode_symbol_that_folds_past_1mb() -> None:
    """A real-mode offset high enough that base+offset crosses 0x100000 cannot be split to
    seg:off without dropping bit 20, so it is REFUSED rather than armed at a wrong
    paragraph. base 0xF0000 + offset 0x20000 = linear 0x110000 -> the split would return
    seg 0x1000, off 0, which folds back to 0x10000, not 0x110000."""
    real = NamesFake(mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0xF0000, "limit": -1, "type": -1})
    with pytest.raises(ds.Invalid, match="past the 0xFFFFF"):
        placement.target_for(0x20000, "CS", real)   # type: ignore[arg-type]


def test_breakpoint_list_tells_unarmable_from_ambiguous_from_unresolved(
        tmp_path: Path) -> None:
    """The three non-armed states are DISTINCT and must not collapse. A real-mode table
    with no flat base makes a resolvable symbol `unarmable` (the address cannot be worked
    out now), NEVER `ambiguous` (which would lie that the name is defined twice). A name
    defined twice is `ambiguous`; a name absent is `unresolved`. Before the fix a single
    `except Invalid` labelled the no-base case `ambiguous` too."""
    dup = [dsym.Symbol("twice", 0x100, kind="T"), dsym.Symbol("twice", 0x200, kind="T")]
    one = dsym.Symbol("once", 0x300, kind="T")
    _names(tmp_path, symbols=[*dup, one], mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})   # sectioned: no flat base
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "symbol", "once"))
    st.add(dec.Declaration("breakpoint", "symbol", "twice"))
    st.add(dec.Declaration("breakpoint", "symbol", "absent"))
    listed = server.breakpoint_list()
    states = {b["ref"]: b["state"] for b in listed["breakpoints"]}
    assert states == {"once": "unarmable", "twice": "ambiguous", "absent": "unresolved"}


def test_watch_held_matches_by_value_across_widths_and_never_a_code_bp() -> None:
    """A watch is recognised by its numbers, so the debugger's varying offset width does
    not make an armed watch read as gone. A code breakpoint at the same address is NOT a
    match: clearing a watch must never delete a code breakpoint."""
    rows = [{"index": "00", "entry": "BPPM 00AF:6024 (00)"},        # narrow width
            {"index": "01", "entry": "BP 00AF:00006024"}]           # a code BP, same addr
    hit = arming.watch_held(rows, 0xAF, 0x6024)
    assert hit is not None and hit["index"] == "00"                 # the watch, not the BP
    assert arming.watch_held(rows, 0xAF, 0x9999) is None


def test_watch_clear_reports_disarmed_only_after_reading_the_removal_back(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`disarmed` is the machine's answer read back, not a claim that a BPDEL must have
    taken. If the debugger still lists the watch after the delete, the tool does not say it
    was disarmed."""
    fake = _names(tmp_path)
    server.watch_add(ref="0040:006C", mode="change", length=4)     # arms a BPPM row
    monkeypatch.setattr(fake, "command", lambda *_a, **_k: "")    # BPDEL is a no-op now
    got = server.watch_clear(all=True)
    assert got["declarations_cleared"] == 1
    assert got["disarmed"] == [], "the watch was NOT gone from the list, so not disarmed"


def test_start_refuses_a_corrupt_declaration_file_before_launching(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corrupt or hand-edited declarations file fails as a clean INVALID BEFORE the
    emulator boots, never a traceback after it is already up. The store is built and
    validated before the session, so `ds.Session` is never even constructed here."""
    state = tmp_path / "state"
    (state / "dosbox-x-debug").mkdir(parents=True)
    (state / "dosbox-x-debug" / "declarations.json").write_text(
        '["not a mapping"]', encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")

    def no_session(*_a: object, **_k: object) -> object:
        raise AssertionError("ds.Session must not be built when the store is corrupt")
    monkeypatch.setattr(ds, "Session", no_session)
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=1))
    assert got["status"] == "INVALID" and "not a mapping" in got["message"]
    assert dstate.STATE.session is None, "no session may be left behind by a refused start"


def test_store_requires_a_started_session() -> None:
    """Every tool that reaches the store gets a named refusal, not an AttributeError, when
    no session has keyed one yet."""
    dstate.STATE.store = None
    with pytest.raises(ds.Invalid, match="no declaration store"):
        arming.current_store()


def test_parse_seg_off_refuses_a_non_hex_pair() -> None:
    with pytest.raises(ds.Invalid, match="not a hex SEG:OFF"):
        placement.parse_seg_off("ZZ:GG")


def test_breakpoint_at_a_symbol_with_no_flat_base_is_stored_unarmed(tmp_path: Path) -> None:
    """A real-mode symbol whose table has no flat base cannot be placed right now, so it is
    STORED and reported `unarmed` with the reason -- not refused, not armed at a guess."""
    _names(tmp_path, symbols=[dsym.Symbol("_x", 0x100, kind="T")], mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})
    got = cast(dict[str, Any], server.breakpoint_at(ref="_x"))
    assert got["stored"] is True and got["armed"] is False and got["state"] == "unarmable"
    assert "FLAT base" in got["why"]


def test_rearm_counts_ambiguous_and_unarmable_apart(tmp_path: Path) -> None:
    """`symbols_load`'s re-arm reports each non-armed reason under its OWN name: a duplicate
    name is `ambiguous`, a resolvable name with no base yet is `unarmable`, and neither is
    counted as the other."""
    dup = [dsym.Symbol("dup", 0x1, kind="T"), dsym.Symbol("dup", 0x2, kind="T")]
    _names(tmp_path, symbols=[*dup, dsym.Symbol("one", 0x3, kind="T")], mode="Real")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "symbol", "one"))
    st.add(dec.Declaration("breakpoint", "symbol", "dup"))
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": -1, "limit": -1, "type": -1})
    got = arming.rearm_declarations(cast(Any, dstate.STATE.session))
    assert {k: [r["ref"] for r in v] for k, v in got.items()} == {
        "rearmed": [], "stale": [], "unresolved": [], "ambiguous": ["dup"], "unarmable": ["one"]}
    assert all(r["why"] for r in (*got["ambiguous"], *got["unarmable"])), got


def test_watch_flows_in_real_mode_arm_list_and_clear(tmp_path: Path) -> None:
    """The real-mode watch path: a change watch lists as a `BPMEM` row (the display spelling
    `_watch_entry` gives real mode), reads back `armed`, and clears."""
    _names(tmp_path, mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0x7DF0, "limit": -1, "type": -1})
    w = cast(dict[str, Any], server.watch_add(ref="0100:0200", mode="change", length=4))
    assert w["armed"] is True
    lst = cast(dict[str, Any], server.watch_list())
    assert lst["watches"][0]["state"] == "armed"
    assert str(lst["watches"][0]["entry"]).startswith("BPMEM ")
    cl = cast(dict[str, Any], server.watch_clear(all=True))
    assert cl["disarmed"]
    assert cast(dict[str, Any], server.watch_list())["watches"] == []


def test_watch_list_reports_gone_and_foreign(tmp_path: Path) -> None:
    """A declared change watch the debugger no longer holds is `gone`; a memory-watch row
    the store never placed is `foreign` and listed, never silently taken as one of ours."""
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0, "limit": -1, "type": -1})
    server.watch_add(ref="0100:0200", mode="change", length=4)          # armed
    fake.rows.append({"index": "09", "entry": "BPMEM 0300:0400 (00)"})  # foreign
    fake.rows = [r for r in fake.rows if not r["entry"].startswith("BPMEM 0100")]  # gone
    lst = cast(dict[str, Any], server.watch_list())
    states = {w["ref"]: w["state"] for w in lst["watches"]}
    assert states["0100:0200"] == "gone"
    assert "BPMEM 0300:0400 (00)" in lst["foreign"]


def test_watch_list_states_unresolved_and_ambiguous(tmp_path: Path) -> None:
    """A watch on a name absent this build is `unresolved`; a name defined twice is
    `ambiguous` with its reason -- the same vocabulary the breakpoint list uses."""
    dup = [dsym.Symbol("two", 0x1, kind="d"), dsym.Symbol("two", 0x2, kind="d")]
    _names(tmp_path, symbols=dup)
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "two", width=4, fmt="u32", watch_mode="change"))
    st.add(dec.Declaration("watch", "symbol", "gone", width=4, fmt="u32", watch_mode="show"))
    lst = cast(dict[str, Any], server.watch_list())
    states = {w["ref"]: w["state"] for w in lst["watches"]}
    assert states["two"] == "ambiguous" and states["gone"] == "unresolved"


def test_watch_add_change_that_cannot_arm_is_kept_unarmed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A change watch that resolves but cannot arm (the machine moved) is STORED and
    reported `unarmed`, its intent kept for a later stop."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_x", 0x1000, kind="d")])

    def boom(**_k: object) -> dict[str, object]:
        raise ds.Invalid("not_stopped", "the machine is running; nothing was armed")
    monkeypatch.setattr(fake, "watch", boom)
    got = cast(dict[str, Any], server.watch_add(ref="g_x", mode="change", length=4))
    assert got["armed"] is False and got["state"] == "unarmable"


def test_watch_clear_skips_an_unresolvable_change_and_still_clears_the_store(
        tmp_path: Path) -> None:
    """A change watch that no longer resolves armed nothing to remove, so `watch_clear`
    skips the debugger for it but still drops the declaration (it is the store's)."""
    _names(tmp_path, symbols=[])          # empty table: the name will not resolve
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "gone", width=4, fmt="u32",
                           watch_mode="change"))
    got = cast(dict[str, Any], server.watch_clear(all=True))
    assert got["declarations_cleared"] == 1 and got["disarmed"] == []


def test_read_memory_takes_a_symbol_or_a_seg_off_ref(tmp_path: Path) -> None:
    """Decision 11 reaches the readers as ONE spelling (owner's QA call): `read_memory`
    locates its address from a symbol OR a raw SEG:OFF `ref`, and both read the same place.
    The numeric segment/offset pair a reader once also took is gone -- one way to say one
    address. A protected-mode data symbol resolves against the live DS selector."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], ds_="00AF")
    by_name = cast(dict[str, Any], server.read_memory(ref="g_rate", length=4))
    assert by_name["status"] == "ok" and by_name["seg_off"].startswith("00AF:")
    assert by_name["hex"] == "00112233" and by_name["length"] == 4, by_name
    assert by_name["seg_off"] == "00AF:0017A6EC", by_name
    by_addr = cast(dict[str, Any], server.read_memory(ref="00AF:0017A6EC", length=4))
    assert by_addr["seg_off"] == "00AF:0017A6EC", by_addr


def test_read_memory_refuses_an_unlocatable_or_ambiguous_target(tmp_path: Path) -> None:
    """A read needs a concrete address, so an absent name or a doubly-defined name is a
    named refusal -- never a read at a guessed address."""
    _names(tmp_path, symbols=[dsym.Symbol("dup", 0x1, kind="d"),
                              dsym.Symbol("dup", 0x2, kind="d")])
    absent = cast(dict[str, Any], server.read_memory(ref="nope"))
    assert absent["status"] == "INVALID" and "not in the symbol table" in absent["message"]
    ambig = cast(dict[str, Any], server.read_memory(ref="dup"))
    assert ambig["status"] == "INVALID" and "names 2 symbols" in ambig["message"]
    # A BARE NUMBER (no colon) is a symbol lookup, not a linear address -- `_decide_by` keys
    # on the colon. Pinned directly so a regression that read bare hex as an address (the
    # confusion _decide_by's own docstring warns of) would redden here.
    numeric = cast(dict[str, Any], server.read_memory(ref="400000"))
    assert numeric["status"] == "INVALID" and "not in the symbol table" in numeric["message"]


def test_render_watch_reads_the_bytes_as_little_endian_values() -> None:
    """N bytes read as the declared format, x86 little-endian: one scalar is one value, a
    width of several is a list, and the grammar's shapes decode to theirs."""
    import struct as _s
    assert arming.render_watch(bytes([0x78, 0x56, 0x34, 0x12]), 4, "u32") == 0x12345678
    assert arming.render_watch(bytes([0xFF, 0xFF, 0xFF, 0xFF]), 4, "i32") == -1
    assert arming.render_watch(_s.pack("<f", 1.5), 4, "f32") == 1.5
    assert arming.render_watch(bytes([1, 0, 2, 0]), 4, "u16") == [1, 2]     # two of them
    assert arming.render_watch(bytes([1, 2, 3, 4]), 4, "u8") == [1, 2, 3, 4]
    assert arming.render_watch(bytes([0x2A]), 1, "u8") == 0x2A
    assert arming.render_watch(bytes([1, 0, 2, 0]), 0, "u16[2]") == [1, 2]
    assert arming.render_watch(b"RE\0\0\xfe\xff", 0, "{name:char[4],x:i16}") == {
        "name": "RE", "x": -2}


def test_evaluate_watches_reads_read_mode_together_and_bytes_for_a_struct(
        tmp_path: Path) -> None:
    """R2 and R5: the three rate globals come back TOGETHER in one evaluation, each rendered
    as its declared u32, and a struct declared as u8 comes back as its bytes with no fields
    invented. A protected-mode data symbol resolves against the live DS selector."""
    fake = _names(tmp_path, symbols=[
        dsym.Symbol("g_eng_rate", 0x1000, kind="d"),
        dsym.Symbol("g_eng_samples_tick", 0x1004, kind="d"),
        dsym.Symbol("g_bufsamp", 0x1008, kind="d"),
        dsym.Symbol("g_cue", 0x2000, kind="d"),
    ], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (44100).to_bytes(4, "little")
    fake.mem[(0xAF, 0x1004)] = (735).to_bytes(4, "little")
    fake.mem[(0xAF, 0x1008)] = (512).to_bytes(4, "little")
    fake.mem[(0xAF, 0x2000)] = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    st = dstate.STATE.store
    assert st is not None
    for name in ("g_eng_rate", "g_eng_samples_tick", "g_bufsamp"):
        st.add(dec.Declaration("watch", "symbol", name, width=4, fmt="u32",
                               watch_mode="show"))
    st.add(dec.Declaration("watch", "symbol", "g_cue", width=8, fmt="u8",
                           watch_mode="show"))
    out = arming.evaluate_watches(fake)  # type: ignore[arg-type]
    by = {w["ref"]: w for w in out}
    assert by["g_eng_rate"]["value"] == 44100 and by["g_eng_rate"]["state"] == "evaluated"
    assert by["g_eng_samples_tick"]["value"] == 735
    assert by["g_bufsamp"]["value"] == 512
    assert by["g_cue"]["value"] == [1, 2, 3, 4, 5, 6, 7, 8]   # bytes, no fields (R5)
    assert by["g_cue"]["bytes"] == "0102030405060708"


def test_evaluate_watches_will_not_read_a_change_watch_off_its_trap(tmp_path: Path) -> None:
    """A break-on-change watch armed a trap byte in its memory (decision 29), so its value
    is NOT read here -- the reply carries the reason instead of a value that would be the
    trap. Unresolved and unreadable watches carry why, never a guessed value."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_x", 0x1000, kind="d")], ds_="00AF")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "g_x", width=4, fmt="u32",
                           watch_mode="change"))
    st.add(dec.Declaration("watch", "symbol", "g_absent", width=4, fmt="u32",
                           watch_mode="show"))
    by = {w["ref"]: w for w in arming.evaluate_watches(fake)}  # type: ignore[arg-type]
    assert "value" not in by["g_x"] and "trap" in by["g_x"]["note"]
    assert by["g_absent"]["state"] == "unresolved" and "value" not in by["g_absent"]


def test_stop_reply_carries_registers_watches_cause_and_the_e9_block(tmp_path: Path) -> None:
    """A stop reply always carries the registers, the watches evaluated, its `cause`, and the
    E9 block: the guest's lines since the previous stop, whole when they fit."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x1000, kind="d")], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (48000).to_bytes(4, "little")
    fake.log = ["boot", "rate=48000", "tick"]
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32",
                           watch_mode="show"))
    out = running.stop_reply(fake, halted=True)  # type: ignore[arg-type]
    assert out["status"] == "ok" and out["halted"] is True
    assert out["regs"]["CS"] == "0x00a7" and out["regs"]["DS"] == "0x00af"
    assert out["watches"][0]["value"] == 48000 and out["watches"][0]["state"] == "evaluated"
    assert out["cause"].startswith("no declared code breakpoint")  # nothing declared at CS:EIP
    assert out["e9"]["lines_total"] == 3 and out["e9"]["truncated"] is False, out["e9"]


def test_attribution_names_a_breakpoint_at_the_stop_or_says_it_cannot(tmp_path: Path) -> None:
    """Attribution is by ADDRESS COMPARISON. A code breakpoint declared at CS:EIP is named;
    a stop elsewhere is an honest cannot-say, naming the reason (no hit flag)."""
    fake = _names(tmp_path)
    fake.cs, fake.eip = "00A7", "00001A27"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "00A7:00001A27"))
    st.add(dec.Declaration("breakpoint", "address", "00A7:00009999"))
    hit = arming.attribute_stop(fake, where=fake.where())  # type: ignore[arg-type]
    assert hit["attributed"] is True and hit["ref"] == "00A7:00001A27"
    fake.eip = "00005555"
    miss = arming.attribute_stop(fake, where=fake.where())  # type: ignore[arg-type]
    assert miss["attributed"] is False and "no hit flag" in miss["why"]


def test_resume_enriches_a_halt_and_leaves_a_running_machine_bare(tmp_path: Path) -> None:
    """The wiring: a resume that HALTED carries the full stop reply (watches, E9, ...); one
    that left the machine running carries only its base, because a running machine has
    nothing to read and `where` would refuse it."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x1000, kind="d")], ds_="00AF")
    fake.mem[(0xAF, 0x1000)] = (60).to_bytes(4, "little")
    fake.log = ["a", "b"]
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32",
                           watch_mode="show"))
    fake.halted = True
    out = cast(dict[str, Any], server.resume())
    assert "stop_seq" in out and out["watches"][0]["value"] == 60
    assert out["e9"]["lines_total"] == 2
    fake.halted = False
    bare = cast(dict[str, Any], server.resume())
    assert "stop_seq" not in bare and "watches" not in bare and "e9" not in bare
    assert "verdict" not in bare, "a resume that waited for nothing carries none"


def test_step_and_run_to_enrich_a_stop_but_not_a_still_running_machine(
        tmp_path: Path) -> None:
    """step carries the full stop reply when it STOPPED, and only the base answer when the
    machine ran on (a CALL that never returned) -- a running machine has nothing to read; a
    `run_to` always stops, its bound interrupting the run, so it always carries one."""
    fake = _names(tmp_path)
    stopped_step = cast(dict[str, Any], server.step(mode="over"))
    assert "regs" in stopped_step and "e9" in stopped_step
    fake.step_running = True
    ran = cast(dict[str, Any], server.step(mode="over"))
    assert ran["session"]["running"] is True and "running" not in ran, ran
    assert "regs" not in ran and "e9" not in ran and "pc" not in ran, ran
    fake.step_running, fake.running = False, False           # stopped again for the run
    stopped_run = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020"))
    assert stopped_run["verdict"] == "TARGET" and "watches" in stopped_run
    fake.runto_running, fake.control_hits = True, 1
    timed = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020"))
    assert timed["verdict"] == "TIMEOUT" and "watches" in timed


def test_evaluate_watches_skips_a_breakpoint_and_reports_why_and_unreadable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The evaluator walks only watch declarations (a breakpoint in the store is skipped), an
    ambiguous watch carries its why, and a read whose bytes cannot be fetched is `unreadable`
    with the reason -- never a value at a guessed address."""
    dup = [dsym.Symbol("two", 0x1, kind="d"), dsym.Symbol("two", 0x2, kind="d")]
    fake = _names(tmp_path, symbols=[*dup, dsym.Symbol("ok", 0x1000, kind="d")], ds_="00AF")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "00A7:0010"))          # skipped
    st.add(dec.Declaration("watch", "symbol", "two", width=4, fmt="u32",
                           watch_mode="show"))                             # ambiguous + why
    st.add(dec.Declaration("watch", "symbol", "ok", width=4, fmt="u32",
                           watch_mode="show"))                             # unreadable

    def boom(_s: int, _o: int, _n: int, mode: str | None = None) -> bytes:
        raise ds.Invalid("unexpected_answer", "the data view did not come back")
    monkeypatch.setattr(fake, "read_bytes", boom)
    by = {w["ref"]: w for w in arming.evaluate_watches(fake)}  # type: ignore[arg-type]
    assert set(by) == {"two", "ok"}                            # the breakpoint is not listed
    assert by["two"]["state"] == "ambiguous" and "why" in by["two"]
    assert by["ok"]["state"] == "unreadable" and "did not come back" in by["ok"]["why"]


def test_attribution_in_real_mode_compares_the_linear_address(tmp_path: Path) -> None:
    """Real-mode attribution compares LINEAR addresses, so a breakpoint declared at one
    seg:off matches a stop the debugger reports through a different aliasing paragraph."""
    fake = _names(tmp_path, mode="Real")
    fake.cs, fake.eip = "1000", "00000010"        # linear 0x10010
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0FFF:00000110"))   # 0xFFF0+0x110=0x10100? no
    st.add(dec.Declaration("breakpoint", "address", "1001:00000000"))   # linear 0x10010 -- same
    hit = arming.attribute_stop(fake, where=fake.where())  # type: ignore[arg-type]
    assert hit["attributed"] is True and hit["ref"] == "1001:00000000"


def test_a_halt_whose_position_is_unreadable_keeps_the_halt(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A halt is a real observation. If the position cannot be read (a cut pane, where()
    refusing), the halt and its base fields stand and the enrichment is marked unavailable --
    the whole reply is NOT thrown away for a read that could not be made."""
    fake = _names(tmp_path)
    fake.halted = True

    def cut() -> dict[str, str]:
        raise ds.Invalid("unexpected_answer", "the register pane came back cut")
    monkeypatch.setattr(fake, "where", cut)
    out = cast(dict[str, Any], server.resume())
    assert out["status"] == "ok" and "stop_seq" not in out
    assert out["enrichment"]["available"] is False and "cut" in out["enrichment"]["why"]
    assert "regs" not in out


def test_a_read_watch_is_not_read_off_a_change_watchs_armed_trap(tmp_path: Path) -> None:
    """decision 29 airtight against aliasing: a show watch whose address is CURRENTLY armed as
    a memory watch (however declared) is `shadowed`, not read -- its bytes would be the trap."""
    fake = _names(tmp_path, ds_="00AF")
    fake.rows.append({"index": "00", "entry": "BPPM 00AF:00006024 (00)"})   # armed elsewhere
    fake.mem[(0xAF, 0x6024)] = (999).to_bytes(4, "little")
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("watch", "address", "00AF:00006024", width=4, fmt="u32",
                           watch_mode="show"))
    w = arming.evaluate_watches(fake)[0]  # type: ignore[arg-type]
    assert w["state"] == "shadowed" and "value" not in w and "trap" in w["note"]


def test_a_stop_a_sequence_found_moves_the_mark_its_block_starts_from(tmp_path: Path) -> None:
    """A stop recorded by the contact that found it (`recorded_stop_reply`) shows the lines since
    the previous stop and moves the mark, so the next stop shows only what came after it."""
    fake = _names(tmp_path)
    fake.log = ["L1", "L2"]
    dstate.STATE.e9_offset = 0
    dstate.STATE.remember_stop(cast(ds.Session, fake), {"cs": "F000", "eip": "0000FFF0",
                                                        "mode": "Real"}, {}, [],
                               {"attributed": False})
    dstate.STATE.last_stop["picture"] = {}
    found = running.recorded_stop_reply(fake, {})  # type: ignore[arg-type]
    assert found["e9"]["lines"] == ["L1", "L2"] and found["e9"]["mark"] == 0, found["e9"]
    assert fake.log is not None
    fake.log += ["L3"]
    nxt = running.e9_block(fake)  # type: ignore[arg-type]
    assert nxt["lines"] == ["L3"] and nxt["mark"] > 0, nxt


def test_every_stop_shows_its_guest_lines_since_the_previous_one_bounded(
        tmp_path: Path) -> None:
    """ON AND BOUNDED: whole up to `STOP_LINES_SHOWN`, one past it the newest ones with
    `truncated` and a `how` naming `log` from the block's own mark, arguments `log` takes; the
    tools that stop take no display argument; no log is unavailable with why."""
    fake = _names(tmp_path)
    fake.halted = True
    shown = log_marks.STOP_LINES_SHOWN
    fake.log = [f"line{i}" for i in range(shown)]
    whole = server.resume()["e9"]
    assert (whole["lines_total"], whole["truncated"], whole["mark"]) == (shown, False, 0), whole
    assert "how" not in whole, whole
    fake.log += [f"more{i}" for i in range(shown + 1)]
    cut = server.resume()["e9"]
    assert cut["truncated"] and cut["lines_total"] == shown + 1 and cut["mark"] > 0, cut
    assert cut["lines"] == [f"more{i}" for i in range(1, shown + 1)], cut
    named = set(re.findall(r"(\w+)=", cut["how"]))
    params = inspect.signature(server.log).parameters
    required = {k for k, v in params.items() if v.default is inspect.Parameter.empty}
    assert f"since_mark={cut['mark']}" in cut["how"] and required <= named <= set(params), (
        cut["how"])
    for tool in ("resume", "step", "run_to", "run_for"):
        params = inspect.signature(getattr(server, tool)).parameters
        assert not {"e9", "e9_filter", "e9_stamp"} & set(params), tool
    fake.log = None
    assert server.resume()["e9"]["available"] is False


def test_stop_on_a_parked_machine_never_names_a_previous_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    dstate.STATE.remember_stop(cast(ds.Session, fake), {"cs": "F000", "eip": "0000FFF0",
                                                        "mode": "Real"}, {}, [],
                               {"attributed": False})
    fake.stop_count = 99                          # a stop the record is not of

    def cut(*_a: Any) -> Any:
        raise ds.Invalid("host_failed", "the pane was cut")
    monkeypatch.setattr(fake, "stop_survey", cut)
    got = cast(dict[str, Any], server.stop())
    assert got["interrupted"] is False and got["last_stop"]["available"] is False, got
    assert "not readable yet" in got["note"]


def test_a_read_watch_wider_than_128_bytes_is_refused_at_declaration(tmp_path: Path) -> None:
    """A width no stop could ever serve is refused up front, pointing at memdump, rather than
    stored only to report `unreadable` at every stop."""
    _names(tmp_path)
    got = cast(dict[str, Any], server.watch_add(ref="0040:0000", mode="show", length=256,
                                                fmt="u8"))
    assert got["status"] == "INVALID" and "region" in got["message"]


# ----------------------------------------------------- the ref you clear with

def test_every_declaration_reply_carries_the_ref_that_clears_it(tmp_path: Path) -> None:
    """MEASURED on a real guest: `breakpoint_interrupt(0x21, ah=0x4B)` answered with
    an `entry` and no `ref`, and the spelling that clears it -- the debugger's own
    `BPINT 21 AH=4B` -- was in no description and no reply, so the caller's
    `breakpoint_clear(ref="BPINT 21 4B")` cleared nothing. The reply of every tool that
    creates a declaration carries `ref`, and that string clears it."""
    fake = _names(tmp_path)
    armed = server.breakpoint_interrupt(number=0x21, ah=0x4B)
    assert armed["ref"] == "BPINT 21 AH=4B", armed
    assert [r["entry"] for r in fake.rows] == ["BPINT 21 AH=4B"]
    cleared = server.breakpoint_clear(ref=armed["ref"])
    assert cleared["status"] == "ok" and cleared["declarations_cleared"] == 1, cleared
    assert fake.rows == []
    watched = server.watch_add(ref="_g_state", mode="show", length=4)
    assert watched["ref"] == "_g_state", watched
    assert server.watch_clear(ref=watched["ref"])["declarations_cleared"] == 1


def test_clearing_a_ref_that_matches_nothing_is_refused_naming_what_there_is(
        tmp_path: Path) -> None:
    """A zero in green is indistinguishable from "nothing to clear" for a caller who spelt
    the ref wrong, and that caller left a breakpoint armed (measured). A `ref`
    that matches no declaration is INVALID and names the refs the store holds; clearing
    ALL of an empty store stays `ok` with 0, because there the zero is the answer."""
    _names(tmp_path)
    server.breakpoint_interrupt(number=0x21, ah=0x4B)
    wrong = server.breakpoint_clear(ref="BPINT 21 4B")
    assert wrong["status"] == "INVALID", wrong
    assert "BPINT 21 AH=4B" in wrong["message"], wrong["message"]
    assert server.breakpoint_list()["breakpoints"][0]["state"] == "armed"
    assert server.watch_clear(ref="_nope")["status"] == "INVALID"
    server.breakpoint_clear(all=True)
    empty = server.breakpoint_clear(all=True)
    assert empty["status"] == "ok" and empty["declarations_cleared"] == 0, empty
    assert server.watch_clear(all=True)["status"] == "ok"


# ------------------------------------------- stale raw addresses across sessions

def test_symbols_load_leaves_another_builds_raw_address_stale_and_names_what_it_rearmed(
        tmp_path: Path) -> None:
    """The same defect at the server: a raw-address breakpoint from session s1 over an OLDER
    build must NOT re-arm itself in session s2 (per build: kept, listed `stale`, not armed,
    because it re-resolves against nothing), a
    by-symbol one must, and `symbols_load` names WHICH refs it re-armed and which it left
    stale rather than handing back a count. Re-declaring the raw address in s2 adopts it."""
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s1"
    dstate.STATE.conf_fingerprint = "conf-of-an-older-build"
    server.breakpoint_at(ref="00A7:5C6F0")
    server.breakpoint_at(ref="_main")
    # A NEW SESSION over a REBUILT program: the emulator's own list starts empty, the origin
    # changes, and the map loaded below fingerprints a different build.
    fake.rows.clear()
    dstate.STATE.session_origin = "s2"
    dstate.STATE.conf_fingerprint = dlaunch.fingerprint(fake.launch.conf)
    got = server.symbols_load(path=str(nm), base="400000")
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"], got["declarations"]
    assert [r["ref"] for r in got["declarations"]["stale"]] == ["00A7:5C6F0"], \
        got["declarations"]
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:16DD80"], fake.rows
    listed = {b["ref"]: b for b in server.breakpoint_list()["breakpoints"]}
    assert listed["00A7:5C6F0"]["state"] == "stale", listed
    assert listed["00A7:5C6F0"]["origin"] == "s1" and listed["00A7:5C6F0"]["created_at"]
    assert listed["_main"]["state"] == "armed" and listed["_main"]["origin"] == "s1"
    # ADOPTION: declaring the same raw address in s2 arms it and moves its origin here.
    adopted = server.breakpoint_at(ref="00A7:5C6F0")
    assert adopted["already_stored"] is True and adopted["armed"] is True, adopted
    row = next(b for b in server.breakpoint_list()["breakpoints"] if b["ref"] == "00A7:5C6F0")
    assert row["state"] == "armed" and row["origin"] == "s2", row


class _Booted(NamesFake):
    """A double `start` builds through its seam and finds ready at once."""
    argv = ["dosbox-x", "-conf", "g.conf"]

    def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
        return 0.5


def build_of(conf: Path, nm_text: str, base: int = 0x400000) -> str:
    """The stamp of the batch an `nm` map loaded at `base` makes over `conf`."""
    return dec.Build.of(dlaunch.fingerprint(conf), [(s.name, dsym.place(s, {dsym.FLAT: base}))
                                               for s in dsym.parse_nm(nm_text)]).stamp


def _start_over_a_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                        stamped: dict[str, str | None], double: type[NamesFake] = _Booted,
                        conf_text: str = "[sdl]\n") -> tuple[dict[str, Any], NamesFake]:
    """`start` driven whole over a store an earlier session left: each raw address in
    `stamped` declared as a breakpoint with that build fingerprint (None: this start's own,
    the conf alone), placed at a stop of the mode the double parks in. The store lives under a
    state directory of the case's own; the conf holds `conf_text`, so a case can edit the conf
    between two sessions."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    conf = tmp_path / "g.conf"
    conf.write_text(conf_text, encoding="utf-8")
    booted = double(conf=conf)
    mode = "real" if booted.mode == dcons.REAL_MODE else "protected"
    store = dec.DeclarationStore(str(conf.resolve()))
    for ref, fp in stamped.items():
        store.add(dec.Declaration("breakpoint", "address", ref, created_at="t0", origin="s1",
                                  fingerprint=fp or dlaunch.fingerprint(conf.resolve()),
                                  cpu_mode=mode))
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    with mock.patch("dosbox_x_server.ds.Session", lambda _l: booted):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60))
    return got, booted


def test_start_re_arms_a_raw_address_left_over_the_same_build_and_not_another_builds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PER BUILD: a raw-address breakpoint an earlier session declared over the build a start
    has (the conf, no map loaded yet) is re-armed at `start` and listed `armed`, because over
    an unchanged program it still names the same instruction. One declared over another
    build, and one declared over a map (which waits for that map's `symbols_load`), stay
    `stale` and are not armed."""
    mapf = tmp_path / "prog.map"
    mapf.write_text("0016dd80 T _main\n", encoding="utf-8")
    (tmp_path / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    over_map = build_of((tmp_path / "g.conf").resolve(), mapf.read_text(encoding="utf-8"))
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {
        "00A7:0100": None, "00A7:0200": "fp-of-another-build", "00A7:0300": over_map})
    assert got["status"] == "ok", got
    assert [r["entry"] for r in booted.rows] == ["BP 00A7:0100"], booted.rows
    listed = server.breakpoint_list()
    assert listed["debugger_read"] is True, listed
    rows = {b["ref"]: b for b in listed["breakpoints"]}
    assert rows["00A7:0100"]["state"] == "armed", rows
    assert rows["00A7:0200"]["state"] == "stale", rows
    assert rows["00A7:0300"]["state"] == "stale", rows


def test_a_re_arm_at_start_that_cannot_read_the_list_is_said_not_fatal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The re-arm at `start` runs once the session is installed, so a refusal there must not
    turn the whole `start` INVALID over a live emulator (the next `start` would then be
    refused as already live). The session comes up, and the reply says the re-arm was
    refused and why; the declaration stays stored."""
    class CutList(_Booted):
        def breakpoints(self) -> list[dict[str, str]]:
            raise ds.Invalid("unexpected_answer", "no BPLIST header came back")

    got, _ = _start_over_a_store(tmp_path, monkeypatch, {"00A7:0100": None}, CutList)
    assert got["status"] == "ok", got
    assert "no BPLIST header" in got["rearm_refused"], got
    rearm = got["declarations"]["rearm"]
    assert rearm["stale"] == [] and [r["ref"] for r in rearm["unarmable"]] == ["00A7:0100"], rearm
    assert "no BPLIST header" in rearm["unarmable"][0]["why"], rearm
    assert dstate.STATE.session is not None
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["00A7:0100"]  # type: ignore[union-attr]


def test_start_with_nothing_to_re_arm_does_not_read_the_list(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no raw address of this build stored (only another build's), the re-arm at `start`
    reads no list: a start costs no console round trip for declarations it would not arm."""
    got, booted = _start_over_a_store(tmp_path, monkeypatch,
                                      {"00A7:0200": "fp-of-another-build"})
    assert got["status"] == "ok" and "rearm_refused" not in got, got
    assert booted.bp_calls == 0, booted.bp_calls


def test_start_answers_each_stored_breakpoint_as_a_row_saying_whose_and_how_old(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start`'s re-arm account is a list of rows per bucket, each the row the lists give, so a
    declaration an earlier session left says whose it is as it re-arms, and one of another build
    says it is stale. Both paths: the park that reads the list and arms, and the
    one that has nothing to arm and reads nothing."""
    got, _ = _start_over_a_store(tmp_path, monkeypatch, {
        "00A7:0100": None, "00A7:0200": "fp-of-another-build"})
    rearm = got["declarations"]["rearm"]
    assert {k: [r["ref"] for r in v] for k, v in rearm.items()} == {
        "rearmed": ["00A7:0100"], "stale": ["00A7:0200"], "unresolved": [], "ambiguous": [],
        "unarmable": []}, rearm
    for row in (*rearm["rearmed"], *rearm["stale"]):
        assert row["origin"] == "s1" and row["inherited"] is True, row
        assert row["cpu"] == contract.unavailable(arming.ONE_CPU_WHY), row
        assert row["age_s"] == contract.unavailable(declaration_rows.UNDATED_WHY), "t0 is no date"
    dstate.STATE.session = None
    (tmp_path / "again").mkdir()
    got, booted = _start_over_a_store(tmp_path / "again", monkeypatch,
                                      {"00A7:0200": "fp-of-another-build"})
    assert [r["ref"] for r in got["declarations"]["rearm"]["stale"]] == ["00A7:0200"], got
    assert booted.bp_calls == 0, booted.bp_calls


def test_a_listed_row_carries_its_age_from_the_servers_clock_and_whose_it_is(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`age_s` is whole seconds since `created_at` on this server's clock, and this session's own
    row is not `inherited`: the half of a row a caller cannot read off `origin`."""
    then = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(dstate, "utc_now", lambda: then)
    _names(tmp_path)
    server.breakpoint_at(ref="_main")
    monkeypatch.setattr(dstate, "utc_now", lambda: then + timedelta(seconds=90))
    row = server.breakpoint_list()["breakpoints"][0]
    assert (row["ref"], row["age_s"], row["inherited"]) == ("_main", 90, False), row
    assert row["created_at"] == then.isoformat(timespec="seconds"), row


def test_a_file_where_the_default_state_directory_goes_is_refused_naming_the_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no `state_dir` the session's saves go to `<cwd>/save`; a FILE there refuses `start`
    `host_failed` (the host's filesystem refused), naming the default and the argument that
    moves it, never `state_dir` as if the caller had given one."""
    (tmp_path / "save").write_text("a file, not a directory", encoding="utf-8")
    (tmp_path / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    got = server.start(conf=str(tmp_path / "g.conf"), cwd=str(tmp_path), session_seconds=60)
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert got["message"].startswith(
        "the default state directory (`<cwd>/save`; `state_dir` names another): "), got
    assert dstate.STATE.session is None


def test_a_stored_address_the_parser_refuses_is_listed_and_clearable(tmp_path: Path) -> None:
    """A hand-edited or older declaration file is the one input the tools do not get to
    validate, and one unreadable address in it would make `breakpoint_list` and every
    `breakpoint_clear` die on that row, so nothing could list or remove it. It is
    `unarmable` with the parser's words, and its own ref clears it."""
    _names(tmp_path)
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "0x1234"))  # type: ignore[union-attr]
    rows = server.breakpoint_list()["breakpoints"]
    assert rows[0]["state"] == "unarmable" and "cannot be read" in rows[0]["why"], rows
    assert server.breakpoint_clear(ref="0x1234")["declarations_cleared"] == 1


# ------------------------------ a relative path refused, an absolute one named

def test_a_relative_path_is_refused_and_an_absolute_one_names_the_file_it_looked_at(
        tmp_path: Path) -> None:
    """A relative path is judged against one directory and used in another (the server's
    own, the emulator's `cwd`), so it is refused before anything reads it, `cwd` included;
    an absolute path stands, and a refusal names the absolute path it looked at."""
    nm = tmp_path / "one.nm"
    nm.write_text("0016dd80 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    fake.launch = dataclasses.replace(fake.launch, cwd=tmp_path)
    rel = server.symbols_load(path="one.nm", base="400000")
    assert rel["code"] == "bad_argument" and "relative" in rel["message"], rel
    got = server.symbols_load(path=str(nm), base="400000")
    assert got["status"] == "ok", got
    missing = server.symbols_load(path=str(tmp_path / "nope.nm"), base="400000")
    assert missing["status"] == "INVALID" and str(tmp_path / "nope.nm") in missing["message"], (
        missing)
    dstate.STATE.session = None
    rel = server.start(conf="x.conf", cwd="rel/dir", session_seconds=30)
    assert rel["status"] == "INVALID", rel
    assert "cwd='rel/dir' must be an absolute path" in rel["message"], rel


# ------------------------------- no wait at the end for a running-guest tail

def test_perform_does_not_wait_for_a_stop_when_the_last_step_was_a_running_guest_op(
        tmp_path: Path) -> None:
    """MEASURED on a real guest: `perform([..., resume, e9_wait, send_keys, e9])`
    came back after the FULL 30 s `wait` with "did not stop within 30.0s" -- a stop nobody
    asked for, because the list ended in `e9`. The tail waits only when the LAST step is
    the one that released the machine, or something declared can still produce a stop (a
    breakpoint, an interrupt, a change-watch: R1 arms one before it resumes and wants the
    stop). With nothing declared, the sequence returns at once, still running, and says why
    no stop was waited for. Two controls beside it: a list ending in `resume` still waits,
    and the same list with a breakpoint declared waits too."""
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True            # never stops
    # A RELEASE THE DOUBLE ITSELF RECORDS: after a running-guest step the sequence asks the
    # session whether the machine stopped, so the F5 (or a `run_to` that ran off) has to leave
    # it running there too, and each case parks it again before its own `resume`.
    released, ran_to = fake.resume, fake.run_to

    def _resume() -> dict[str, object]:
        fake.running = True
        return released()

    def _run_to(*a: Any, **k: Any) -> dict[str, object]:
        fake.running = fake.runto_running
        return ran_to(*a, **k)

    fake.resume, fake.run_to = _resume, _run_to  # type: ignore[method-assign]
    began = time.monotonic()
    out = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=5.0)
    assert out["status"] == "ok" and out.get("still_running") is True, out
    assert time.monotonic() - began < 2.0, "the tail waited for a stop nobody asked for"
    assert "no stop was waited for" in out["note"], out
    fake.running = False
    began = time.monotonic()
    tail = server.perform(steps=[{"op": "resume"}], settle_seconds=0.6)
    assert tail.get("verdict") == "TIMEOUT" and time.monotonic() - began >= 0.5, tail
    fake.running = False
    # Declared at a stop whose mode the survey reads, so it is placed there and armed.
    fake.where_raises = False
    server.breakpoint_at(ref="00A7:0100")
    fake.where_raises = True
    began = time.monotonic()
    armed = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0.6)
    assert armed.get("verdict") == "TIMEOUT" and time.monotonic() - began >= 0.5, armed
    # `settle_seconds=0` NEVER waits, breakpoint or not, and says so.
    fake.running = False
    began = time.monotonic()
    zero = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0)
    assert zero.get("still_running") is True and time.monotonic() - began < 0.5, zero
    assert "settle_seconds=0" in zero["note"], zero
    # A STALE raw address (another build's, never re-armed) cannot stop it: no wait.
    fake.running = False
    server.breakpoint_clear(all=True)
    dstate.STATE.session_origin = "s2"
    dstate.STATE.conf_fingerprint = "fp-now"
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "00A7:0200",  # type: ignore[union-attr]
                                      origin="s1", fingerprint="fp-old"))
    fake.running = False
    began = time.monotonic()
    stale = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=5.0)
    assert stale.get("still_running") is True and time.monotonic() - began < 2.0, stale



# --------------------------------------------------------- an orphan says so

def test_a_declaration_from_a_store_that_kept_no_origin_is_listed_as_an_orphan(
        tmp_path: Path) -> None:
    """MEASURED on a real guest: a show watch from an older store sat in every stop
    reply with no origin and nothing to tell it from this session's, and the breakpoint
    broom left it. Both families list such a row as `orphan` with the ref that clears it,
    and each broom sweeps only its own family."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    dstate.STATE.session_origin = "s2"
    store = dstate.STATE.store
    assert store is not None
    store.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32", watch_mode="show"))
    store.add(dec.Declaration("breakpoint", "address", "00A7:0100", cpu_mode="protected"))
    store.add(dec.Declaration("interrupt", "address", "BPINT 21"))
    watches = server.watch_list()["watches"]
    assert watches[0]["state"] == "orphan" and "EVALUATED" in watches[0]["why"], watches
    bps = {b["ref"]: b for b in server.breakpoint_list()["breakpoints"]}
    assert bps["00A7:0100"]["state"] == "orphan" and bps["BPINT 21"]["state"] == "orphan", bps
    assert bps["00A7:0100"]["orphan"] is True and "EVALUATED" not in bps["00A7:0100"]["why"]
    # THE STOP REPLY SAYS IT TOO: the orphan show watch is evaluated, flagged as nobody's.
    fake.halted = True
    stop = server.resume()
    assert stop["watches"][0]["state"] == "evaluated" and stop["watches"][0]["orphan"] is True, stop
    # HELD WINS, AND AN UNRESOLVED NAME STAYS UNRESOLVED: an orphan the debugger holds is
    # `armed` (and its row is NOT foreign), an orphan symbol this build lacks is `unresolved`
    # -- the facts a caller acts on, with `orphan: true` beside them.
    store.add(dec.Declaration("breakpoint", "symbol", "g_rate"))
    store.add(dec.Declaration("breakpoint", "symbol", "nope"))
    fake.rows.append({"index": "00", "entry": "BP 00A7:0017A6EC"})
    listed = server.breakpoint_list()
    bps = {b["ref"]: b for b in listed["breakpoints"]}
    assert bps["g_rate"]["state"] == "armed" and bps["g_rate"]["orphan"] is True, bps
    assert bps["nope"]["state"] == "unresolved" and bps["nope"]["orphan"] is True, bps
    assert listed["foreign"] == [], listed
    store.add(dec.Declaration("watch", "address", "00A7:0200", width=4, fmt="u32",
                              watch_mode="change"))
    fake.rows.append({"index": "01", "entry": "BPPM 00A7:00000200 (00)"})
    wl = server.watch_list()
    armed = next(w for w in wl["watches"] if w["ref"] == "00A7:0200")
    assert armed["state"] == "armed" and armed["orphan"] is True and wl["foreign"] == [], wl
    fake.rows.clear()
    assert server.breakpoint_clear(all=True)["declarations_cleared"] == 4      # the watches stay
    assert sorted(w["ref"] for w in server.watch_list()["watches"]) == ["00A7:0200", "g_rate"]
    assert server.watch_clear(all=True)["declarations_cleared"] == 2
    assert fake.rows == []


# ------------------------------------------- a stop reads the list once

def test_a_stop_reads_the_breakpoint_list_once_and_shares_it(tmp_path: Path) -> None:
    """MEASURED on a real guest: a `resume` that stopped cost four `BPLIST` round
    trips, two of them for the same screen -- the watches re-read the list the stop's own
    repaint already carried. A stop takes ONE survey (where, registers, list) and evaluates
    the watches against it; `breakpoints()` is not read again on the way."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    fake.halted = True                   # the resume stops again at once
    fake.bp_calls = fake.survey_calls = 0
    got = server.resume()
    assert "stop_seq" in got and got["watches"][0]["state"] == "evaluated", got
    assert fake.survey_calls == 1, fake.survey_calls
    assert fake.bp_calls == 0, f"the stop re-read the list {fake.bp_calls} time(s)"


# ------------------------------------- lists answer while the guest runs (T1)

def test_the_lists_answer_from_the_store_and_the_last_stop_while_the_guest_runs(
        tmp_path: Path) -> None:
    """MEASURED on a real guest: `breakpoint_list` with the guest running answered
    INVALID with `registers`' own text, while its description promised rows from the store.
    The server HOLDS the answer: the declarations, and the debugger's list as the last stop's
    survey saw it. Running, the lists answer from those two, say `debugger_read: false` and
    `last_stop` the last stop; stopped, they read the debugger and say `debugger_read: true`."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T"),
                                     dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.breakpoint_at(ref="_main")
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    fake.halted = True
    stop = server.resume()                       # the survey of this stop is remembered
    assert "stop_seq" in stop
    stopped = server.breakpoint_list()
    assert stopped["debugger_read"] is True and stopped["breakpoints"][0]["state"] == "armed"
    # THE GUEST RUNS: the console refuses, the lists do not.
    fake.halted = False
    fake.bp_raises = True
    fake.where_raises = True
    running = server.breakpoint_list()
    assert running["status"] == "ok", running
    assert running["debugger_read"] is False, running
    # stop 1 is the park the machine was found in at the first contact; the resume's halt
    # is stop 2, and that is what dates the answer.
    assert running["last_stop"]["stop_seq"] == 2, running
    assert running["last_stop"]["pc"] == "00A7:00000000", running
    assert running["breakpoints"][0]["ref"] == "_main"
    assert running["breakpoints"][0]["state"] == "armed", running      # as of the last stop
    watches = server.watch_list()
    assert watches["status"] == "ok" and watches["debugger_read"] is False, watches
    assert watches["watches"][0]["state"] == "evaluated", watches
    # NEVER STOPPED: nothing to date the answer by, and the rows still come.
    dstate.STATE.last_stop.clear()
    fresh = server.breakpoint_list()
    assert fresh["status"] == "ok" and fresh["last_stop"]["available"] is False, fresh
    assert fresh["breakpoints"][0]["state"] == "unarmable", fresh


# --------------------------------------- the pending queue, applied at the stop (T2)

def test_what_is_asked_while_the_guest_runs_is_applied_at_the_next_stop(
        tmp_path: Path) -> None:
    """The running-guest contract (the owner's decision): a declaration, a clear or a symbol
    load asked while the guest runs answers `pending`, and the next stop applies it before
    evaluating anything and says so in `applied_on_stop`. Before this, `unarmable` and "the
    debugger's list was left as it was" were the answers, and nobody applied them later."""
    nm = tmp_path / "one.nm"
    nm.write_text("00001000 T _main\n0017a6ec d g_rate\n", encoding="utf-8")
    fake = _names(tmp_path, symbols=[dsym.Symbol("_old", 0x2000, kind="T")])
    server.breakpoint_at(ref="_old")                     # armed while stopped, to be cleared
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:2000"]
    fake.running = True
    fake.halted = False
    loaded = server.symbols_load(path=str(nm), base="400000")
    assert loaded["status"] == "ok" and loaded["pending"] is True, loaded
    # the table is held at once
    assert server.symbols_find(name="_main")["symbols_total"] == 1
    armed = server.breakpoint_at(ref="_main")
    assert armed["status"] == "ok" and armed["state"] == "pending", armed
    watched = server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    assert watched["status"] == "ok" and watched["state"] == "pending", watched
    cleared = server.breakpoint_clear(ref="_old")
    assert cleared["status"] == "ok" and cleared["pending_disarm"] == ["BP 00A7:2000"], cleared
    st = server.status()
    assert st["pending"] == {"arm": ["_main", "g_rate"], "disarm": 1,
                             "symbols_load": True, "base_remeasure": False}, st
    assert fake.rows == [{"index": "00", "entry": "BP 00A7:2000"}], (
        "nothing touched the debugger yet")
    # THE STOP: everything pending is applied first, then the stop is read.
    fake.running = False
    fake.halted = True
    stop = server.resume()
    assert "stop_seq" in stop, stop
    applied = stop["applied_on_stop"]
    assert applied["symbols_loaded"] is True and fake.loads == 1, applied
    assert applied["armed"] == ["_main", "g_rate"], applied
    assert applied["disarmed"] == ["BP 00A7:2000"], applied
    entries = [r["entry"] for r in fake.rows]
    assert "BP 00A7:1000" in entries and "BP 00A7:2000" not in entries, entries
    assert any(e.startswith("BPPM 00AF:0017A6EC") for e in entries), entries
    assert server.status()["pending"] == {"arm": [], "disarm": 0, "symbols_load": False,
                                          "base_remeasure": False}
    # NOTHING PENDING: the next stop says nothing about it.
    assert "applied_on_stop" not in server.resume()


# ---------------------------------------------- last_stop where it helps (T3)

def test_status_and_a_running_refusal_carry_the_last_stop(tmp_path: Path) -> None:
    """A reader refused because the guest runs, and saying only that, leaves the caller not
    knowing where the machine is or since when. `status` carries `last_stop` (null before any
    stop), every such refusal carries it too and names the readers that DO answer while
    running, and `registers(from_last_stop=True)` hands the last stop's registers marked
    stale, never by default."""
    fake = _names(tmp_path)
    park = server.status()["last_stop"]          # the machine is found at the debugger
    assert park["stop_seq"] == 1 and park["pc"] == "00A7:00000000", park
    fake.halted = True
    server.resume()
    fake.running = True
    st = server.status()
    assert st["last_stop"]["stop_seq"] == 2 and st["last_stop"]["pc"] == "00A7:00000000", st
    refused = server.registers()
    assert refused["status"] == "INVALID", refused
    assert refused["last_stop"]["stop_seq"] == 2, refused
    assert "log" in refused["answers_while_running"], refused
    old = server.registers(from_last_stop=True)
    assert (old["status"] == "ok" and old["superseded"] is True
            and old["regs"]["CS"] == "0x00a7"), old
    assert old["last_stop"]["stop_seq"] == 2
    dstate.STATE.last_stop.clear()
    assert server.registers(from_last_stop=True)["status"] == "INVALID"


def test_memdump_on_a_running_guest_is_refused_before_the_session_is_asked(
        tmp_path: Path) -> None:
    """`memdump` is one of the readers the running-guest contract refuses: a dump command
    typed at a console that is not listening is dropped. So it refuses
    `not_stopped` with `last_stop`, the way `find` does, before the session is handed
    anything."""
    fake = _names(tmp_path)
    server.status()                              # the park, on record
    fake.running = True
    got = server.memdump(ref="0000:0400", length=16, dest=str(tmp_path / "d.bin"))
    assert got["status"] == "INVALID" and got["code"] == "not_stopped", got
    assert got["last_stop"]["stop_seq"] == 1, got
    assert "log" in got["answers_while_running"], got
    assert getattr(fake, "memdump_calls", []) == [], "the session was asked to dump"
    assert not (tmp_path / "d.bin").exists()


def test_resume_on_a_running_guest_is_refused_before_any_other_check(
        tmp_path: Path) -> None:
    """An `ok` from a `resume` that found the guest already running cannot be told from one
    that released it, so it is refused `not_stopped` like every other tool that needs the
    machine stopped. A value wrong with no machine at all, a negative `seconds`, is refused
    before the gate."""
    # Without the gate this is where an F5 would go out and answer `ok` with `halted: false`.
    fake = _names(tmp_path, watched=True)
    server.status()                              # the park, on record
    fake.running = True
    with mock.patch.object(fake, "resume", side_effect=AssertionError("F5 was sent")):
        got = server.resume()
    assert got["status"] == "INVALID" and got["code"] == "not_stopped", got
    assert got["last_stop"]["stop_seq"] == 1, got
    assert "log" in got["answers_while_running"], got
    # AND THE ORDER: headless and nothing armed is still `not_stopped`; a negative bound is
    # wrong whatever the machine does, so it is refused first.
    fake = _names(tmp_path, watched=False)
    fake.running = True
    with mock.patch.object(fake, "resume", side_effect=AssertionError("F5 was sent")):
        got = server.resume()
        bound = server.resume(seconds=-1)
    assert got["status"] == "INVALID" and got["code"] == "not_stopped", got
    assert bound["code"] == "bad_argument" and "is not a bound" in bound["message"], bound


def test_a_stop_the_caller_asked_for_is_named_as_its_cause(tmp_path: Path) -> None:
    """`stop`'s own stop names the call as its cause, never "which declaration fired cannot be
    told": nothing is at that address to tell apart, and the caller knows what stopped it."""
    fake = _names(tmp_path, watched=True)
    server.status()
    fake.running = True
    got = server.stop()
    assert got["cause"] == "the `stop` call at 00A7:00000000", got


def test_stop_keeps_the_envelope_on_both_branches(tmp_path: Path) -> None:
    """Every reply opens with `summary` and closes with `session`, on both branches of `stop`:
    the one that interrupts a windowed guest, which adds `stopped_at` to a reply already
    built, and the one that finds the machine at rest."""
    fake = _names(tmp_path, watched=True)
    server.status()                              # the park, on record
    fake.running = True
    got = server.stop()
    assert got["status"] == "ok" and got["interrupted"] is True, got
    assert got["pc"] == "00A7:00000000", got
    keys = list(got)
    assert keys[0] == "summary" and keys[-1] == "session", keys
    again = server.stop()                        # the machine is at rest now
    assert again["interrupted"] is False, again
    keys = list(again)
    assert keys[0] == "summary" and keys[-1] == "session", keys


def test_a_stop_nobody_read_is_counted_by_status_alone_and_said_once(
        tmp_path: Path) -> None:
    """A caller driving an unwatched run with `status` and `captures` only must learn
    that the guest has stopped: the first contact finds the prompt in the drain, counts
    the stop THEN, records it, and its reply says `stopped_on_its_own`; the next reply does
    not repeat it. Measured on a real guest: with the count read before the peek, `status`
    kept naming the previous stop and only `registers` moved it."""
    fake = _names(tmp_path)
    before = server.status()["last_stop"]["stop_seq"]    # the park, on record
    fake.running = True                                  # released
    fake.eip = "00000146"
    fake.stop_unread = True                              # the breakpoint fired, unread
    st = server.status()
    assert st["last_stop"]["stop_seq"] == before + 1, st
    assert st["last_stop"]["pc"] == "00A7:00000146", st
    assert st["stopped_on_its_own"]["stop_seq"] == before + 1, st
    assert "stopped_on_its_own" not in server.status()   # said once, by the contact that found it


def test_a_stop_that_came_on_its_own_still_applies_the_queue_at_the_next_contact(
        tmp_path: Path) -> None:
    """A breakpoint fires while the caller is waiting on the log or sending a key, so the
    stop is nobody's reply. The next tool that finds the machine at the debugger (here
    `status`, passively) applies what was pending and says so, so a declaration made while
    the guest ran is never left waiting for a stop TOOL to be called."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")])
    fake.running = True
    assert server.breakpoint_at(ref="_main")["state"] == "pending"
    assert server.status()["pending"]["arm"] == ["_main"]
    fake.running = False                                 # a breakpoint fired meanwhile
    st = server.status()
    assert st["applied_on_stop"]["armed"] == ["_main"], st
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:1000"]
    assert "applied_on_stop" not in server.status()      # said once, by the reply that did it
    # AND THE STOP ITSELF IS ON RECORD: `last_stop` is the stop the machine is in, not the
    # one before (measured: it stayed on the previous stop while `registers`
    # read the new address).
    assert st["last_stop"]["stop_seq"] == 1 and st["last_stop"]["pc"] == "00A7:00000000", st
    fake.running = True
    fake.eip = "00001234"
    fake.running = False                                 # a second stop on its own
    assert server.status()["last_stop"]["stop_seq"] == 2
    assert server.status()["last_stop"]["pc"] == "00A7:00001234"
    assert server.status()["last_stop"]["stop_seq"] == 2      # observed once, not per call
    assert server.registers(from_last_stop=True)["regs"]["EIP"] == "0x00001234"


def test_the_queue_covers_interrupts_and_change_watches_and_says_what_it_could_not_apply(
        tmp_path: Path) -> None:
    """The other kinds the queue carries: an interrupt and a change-watch cleared while the
    guest runs are removed at the stop; a declaration cleared before the stop is simply not
    armed; and an arm the stop cannot resolve (the table changed meanwhile) is reported
    under `still_pending` and stays queued rather than vanishing."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d"),
                                     dsym.Symbol("_gone", 0x3000, kind="T"),
                                     dsym.Symbol("_late", 0x4000, kind="T")])
    server.breakpoint_interrupt(number=0x21, ah=0x4B)
    server.watch_add(ref="g_rate", mode="change", length=4, fmt="u32")
    fake.halted = True
    server.resume()
    fake.running = True
    fake.halted = False
    assert server.breakpoint_clear(ref="BPINT 21 AH=4B")["pending_disarm"] == ["BPINT 21 AH=4B"]
    wc = server.watch_clear(ref="g_rate")
    assert wc["pending_disarm"] and wc["pending_disarm"][0].startswith("BPPM 00AF:0017A6EC"), wc
    assert server.breakpoint_at(ref="_gone")["state"] == "pending"
    assert server.breakpoint_at(ref="_late")["state"] == "pending"
    assert server.breakpoint_clear(ref="_gone")["declarations_cleared"] == 1   # before the stop
    dstate.STATE.install_table([dsym.Symbol("g_rate", 0x17A6EC, kind="d")])   # `_late` vanished
    fake.running = False
    fake.halted = True
    stop = server.resume()
    applied = stop["applied_on_stop"]
    assert applied["disarmed"][0] == "BPINT 21 AH=4B", applied
    assert applied["disarmed"][1].startswith("BPPM 00AF:0017A6EC"), applied
    assert applied["armed"] == [] and any("arm _late" in s for s in applied["still_pending"])
    assert fake.rows == [], fake.rows
    assert server.status()["pending"]["arm"] == ["_late"]


def test_the_states_a_listing_still_gives_when_nothing_is_held(tmp_path: Path) -> None:
    """The branches a live list reaches when the debugger holds nothing: an interrupt
    declaration whose row is gone, an orphan raw breakpoint that is not held, and a
    breakpoint that cannot be armed for a reason that is NOT the guest running (a
    real-mode table with no flat base), which stays `unarmed` with the reason."""
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s2"
    server.breakpoint_interrupt(number=0x21)         # this session's: gone once its row is
    fake.rows.clear()
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "00A7:0300",  # type: ignore[union-attr]
                                            cpu_mode="protected"))
    rows = {b["ref"]: b for b in server.breakpoint_list()["breakpoints"]}
    assert rows["BPINT 21"]["state"] == "gone" and rows["00A7:0300"]["state"] == "orphan", rows
    real = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")], mode="Real",
                  base=-1)
    got = server.breakpoint_at(ref="_main")
    assert got["state"] == "unarmable" and "FLAT base" in got["why"], got
    assert real.rows == []


def test_the_running_guest_contract_holds_at_its_edges(tmp_path: Path) -> None:
    """The fresh-eyes findings on the contract, each pinned: a pending load re-arms the
    declarations it resolves; a clear of a ref that was itself pending queues no phantom
    disarm; a reload that armed a symbol twice clears BOTH rows; the lists show a queued
    ref as `pending` and do not call a queued row `foreign`; an interrupt declared while
    running is pending too; a reader refused by symbol carries `last_stop`; and `close`
    takes the running state with it."""
    nm = tmp_path / "one.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    server.breakpoint_at(ref="_main")                    # unresolved: no table yet
    fake.halted = True
    server.resume()
    fake.running = True
    fake.halted = False
    assert server.symbols_load(path=str(nm), base="400000")["pending"] is True
    assert server.breakpoint_at(ref="00A7:0100")["state"] == "pending"
    assert server.breakpoint_clear(ref="00A7:0100")["pending_disarm"] == []   # never armed
    assert server.breakpoint_interrupt(number=0x21)["state"] == "pending"
    assert server.breakpoint_at(ref="00A7:0200")["state"] == "pending"
    lst = server.breakpoint_list()
    states = {b["ref"]: b["state"] for b in lst["breakpoints"]}
    assert states["00A7:0200"] == "pending" and states["BPINT 21"] == "pending", states
    refused = server.read_memory(ref="_main")
    assert refused["status"] == "INVALID" and refused["last_stop"]["stop_seq"] == 2, refused
    fake.running = False
    fake.halted = True
    stop = server.resume()
    applied = stop["applied_on_stop"]
    assert applied["symbols_loaded"] is True and "_main" in applied["armed"], applied
    assert "BPINT 21" in applied["armed"] and "00A7:0200" in applied["armed"], applied
    entries = [r["entry"] for r in fake.rows]
    assert "BP 00A7:1000" in entries and "BPINT 21" in entries and "BP 00A7:0200" in entries
    # A RELOAD MOVES `_main`: two rows armed for one ref, and a clear takes both.
    nm.write_text("00001200 T _main\n", encoding="utf-8")
    server.symbols_load(path=str(nm), base="400000")
    entries = [r["entry"] for r in fake.rows]
    assert "BP 00A7:1000" in entries and "BP 00A7:1200" in entries, entries
    cleared = server.breakpoint_clear(ref="_main")
    assert sorted(cleared["disarmed"]) == ["BP 00A7:1000", "BP 00A7:1200"], cleared
    assert server.breakpoint_list()["foreign"] == []
    # A QUEUED DISARM'S ROW IS NOT FOREIGN while it waits.
    fake.running = True
    assert server.breakpoint_clear(ref="00A7:0200")["pending_disarm"] == ["BP 00A7:0200"]
    assert server.breakpoint_list()["foreign"] == []
    fake.running = False
    # CLOSE TAKES THE STATE WITH IT.
    server.close()
    assert server.status()["last_stop"]["available"] is False
    assert server.status()["pending"] == {"arm": [], "disarm": 0, "symbols_load": False,
                                          "base_remeasure": False}


def test_perform_checks_every_op_before_running_any(tmp_path: Path) -> None:
    """MEASURED on a real guest: `[send_keys, close, status]` SENT the key and then
    refused at step 1 because `close` is not a step. A refusal for the vocabulary comes
    before anything runs."""
    fake = _names(tmp_path, watched=True)
    out = server.perform(steps=[{"op": "send_keys", "keys": ["a"]}, {"op": "close"},
                                {"op": "status"}])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert out["steps_completed"] == 0 and out["ran"] == [], out
    assert fake.keys_sent == [] if hasattr(fake, "keys_sent") else True


def test_send_keys_names_a_stop_that_landed_during_the_wait_not_still_running(
        tmp_path: Path) -> None:
    """Measured: A key posted by serial just before a breakpoint fired: the
    wait's expiry said "the guest wrote NOTHING ... The emulator is still running" -- the
    PROCESS -- and blamed the program, while the debugger had held the machine for seconds
    and the next `send_keys` refused for exactly that. The miss names the stop the machine
    is in, says where the key went, and carries `last_stop` so the caller can act on it."""
    fake = _names(tmp_path, watched=False, input_port=5555)
    fake.running = True                      # a RUNNING guest, as a key is sent to
    fake.input_effect = None
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=5))
    assert got["status"] == "INVALID" and got["route"] == "guest", got
    assert got["posted"] == 1 and fake.scancodes_sent == [bytes([0x1E, 0x9E])], got
    assert got["verify"]["checked"] is True and got["verify"]["seen"] is False, got["verify"]
    assert got["verify"]["stopped_during_wait"] is True, got["verify"]
    assert "STOPPED at the debugger during the wait at 00A7:00000000" in got["message"], got
    assert "next resume" in got["message"] and "still running" not in got["message"], got["message"]
    assert "guest's log's to say" in got["message"], got["message"]   # never "the key sits in..."
    assert got["verify"]["waited_s"] == 0.4 and got["verify"]["lines_on_disk"] == 0, got["verify"]
    assert got["last_stop"]["pc"] == "00A7:00000000", got["last_stop"]
    assert fake.survey_calls == 1, "the stop is surveyed ONCE, by this reply"
    # THE NEXT KEY IS REFUSED AS STOPPED, in the same words: the two replies agree.
    nxt = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert nxt["status"] == "INVALID" and "STOPPED at the debugger" in nxt["message"], nxt
    assert len(fake.scancodes_sent) == 1, "a refused key must not have sent bytes"


def test_input_to_a_machine_stopped_at_the_debugger_is_refused_before_the_post(
        tmp_path: Path) -> None:
    """A key or a click to a machine parked at the debugger is never a delivery: the
    bytes would sit in the serial buffer and land at the next resume. Keys and clicks are
    refused before posting, with or without `expect`, naming the stop and `resume` as the
    way forward."""
    fake = _guest(tmp_path)
    fake.running = False                           # stopped, as a fresh session is
    fake.input_effect = None
    calls: list[Callable[[], dict[str, Any]]] = [
        lambda: server.send_keys(keys=["a"]),
        lambda: server.send_keys(keys=["a"], expect="key_cue_a", seconds=2),
        lambda: server.send_mouse(button="left")]
    for call in calls:
        got = call()
        assert got["status"] == "INVALID" and "STOPPED at the debugger" in got["message"], got
        assert "`resume` first" in got["message"] and "00A7:0000" in got["message"]
        # A STOPPED machine is the opposite of the running one `NotStopped` names, so the
        # refusal is a plain INVALID: the running-guest envelope's `answers_while_running`
        # would tell a caller which tools answer while the guest RUNS, about a guest that
        # is stopped.
        assert "answers_while_running" not in got, got
    assert fake.commands_sent == [], "nothing was posted to a stopped machine"
    assert "posted" not in got


def test_a_stop_whose_survey_refused_is_not_named_with_the_previous_stops_address(
        tmp_path: Path) -> None:
    """A cut pane at survey time leaves the record on the PREVIOUS stop, and the reply used to
    print that stop's address and attribution as this wait's (an audit found it): a
    confident wrong answer of the right shape. The reply says the position could not be read
    yet, and carries no `last_stop`, rather than the stale one."""
    fake = _names(tmp_path, watched=False, input_port=5555)
    assert cast(dict[str, Any], server.status())["last_stop"]["pc"] == "00A7:00000000"
    fake.running = True
    fake.input_effect = None
    fake.stops_during_wait = True
    fake.registers_raises = True                   # the survey of the NEW stop refuses
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=2))
    assert got["status"] == "INVALID" and got["verify"]["stopped_during_wait"] is True, got
    assert "00A7:00000000" not in got["message"], got["message"]
    assert "position not readable yet" in got["message"], got["message"]
    assert got["last_stop"]["available"] is False, got["last_stop"]


def test_drive_names_a_stop_that_landed_during_its_verify(tmp_path: Path) -> None:
    """`drive`'s VERIFY on a running guest is the same wait; a stop during it is the stop's
    miss, named with `last_stop`, and not "the guest did not do what was expected" (auditor,
    the wording removed from `send_keys` survived here)."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                            # the act is sent to a RUNNING guest
    fake.input_effect = None
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                            expect="key_cue_a", seconds=1))
    assert got["status"] == "INVALID", got
    assert got["verify"]["stopped_during_wait"] is True, got["verify"]
    assert "STOPPED at the debugger during the wait at 00A7:00000000" in got["message"], got
    assert "no line matching `expect`" in got["message"], got["message"]
    assert got["last_stop"]["pc"] == "00A7:00000000", got["last_stop"]


# ------------------------------------------------------- the progress line on a bounded wait


def test_the_sdk_injects_the_context_into_the_waiting_tools_and_hides_it(
        tmp_path: Path) -> None:
    """`ctx` is found by its type through the wrapper, is not an argument the client can
    pass, and stays out of the summary; the tools with no wait take none."""
    for name in ("run_to", "log_wait", "perform", "drive", "send_keys", "send_mouse", "resume",
                 "start", "close"):
        tool = server.mcp._tool_manager.get_tool(name)
        assert tool is not None and tool.context_kwarg == "ctx", name
        assert "ctx" not in tool.parameters.get("properties", {}), name
    for name in ("step", "registers", "status"):
        tool = server.mcp._tool_manager.get_tool(name)
        assert tool is not None and tool.context_kwarg is None, name


def test_the_sequences_wait_for_a_stop_reports_its_progress(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tail of `perform` waits for a stop after a step left the machine running; that
    wait is bounded and says where it is, like every other."""
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True                    # running, and it stays running
    monkeypatch.setattr(fake, "_read", lambda timeout: "", raising=False)
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    out = sequence.run_steps(fake, [{"op": "resume"}], 0.3, server._step_ops(),  # type: ignore[arg-type]
                             lambda p, t, m: ticks.append(m))
    assert out.get("verdict") == "TIMEOUT", out
    assert ticks and ticks[0].startswith("waiting for the machine to stop: ")


def test_the_sequences_wait_for_a_stop_listens_for_the_prompt_and_types_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The wait between a step that left the machine running and the next console step
    must not POLL by typing `BPLIST` and reading the position: that queues keystrokes for
    the stop, and paces a progress tick by the console's timeout on a quiet machine (up to
    six seconds instead of the one every other wait keeps). It listens for the debugger's
    prompt on the terminal the way `run_to` does. The proof is a `where()` that REFUSES
    throughout (a typed poll would read the machine as running) beside a prompt on the
    terminal: the passive wait hears it and answers `stopped`; with nothing on the terminal
    it answers `running` at the bound (the control), ticking every PROGRESS_EVERY_S."""
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True
    monkeypatch.setattr(fake, "_read", lambda timeout: dcons.PROMPT, raising=False)
    monkeypatch.setattr(fake, "_screen", "", raising=False)
    monkeypatch.setattr(fake, "alive", lambda: True)
    marked: list[bool] = []
    monkeypatch.setattr(fake, "_mark_stopped", lambda: marked.append(True), raising=False)
    assert sequence._wait_for_stop(fake, 1.0) == "stopped"  # type: ignore[arg-type]
    assert marked == [True], "the stop heard on the terminal is marked before a reader consumes it"

    def read_nothing(timeout: float) -> str:
        time.sleep(timeout)
        return ""

    monkeypatch.setattr(fake, "_read", read_nothing, raising=False)
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    assert sequence._wait_for_stop(fake, 0.6, lambda p, t, m: ticks.append(m)) == "running"  # type: ignore[arg-type]
    assert ticks and ticks[0].startswith("waiting for the machine to stop: "), ticks
    # A GONE emulator is still told apart from a running one.
    monkeypatch.setattr(fake, "alive", lambda: False)
    assert sequence._wait_for_stop(fake, 0.3) == "gone"  # type: ignore[arg-type]


def test_a_step_carrying_ctx_is_refused_before_it_runs(tmp_path: Path) -> None:
    """`ctx` is the SDK's; a step that names it would hand a stray value to the progress bridge,
    which would blow up at the first tick, an escape the wrapper does not translate."""
    _names(tmp_path)
    out = server.perform(steps=[{"op": "status"}, {"op": "resume", "ctx": "bogus"}])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert "ctx" in out["message"] and out["steps_completed"] == 0, "seen up front: nothing ran"


def test_the_verify_of_drive_forwards_the_progress_to_the_wait() -> None:
    class _Waits:
        log_wait = _log_wait_as_guest

        def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                    progress: ds.Progress = ds.no_progress) -> dict[str, object]:
            progress(1.0, seconds, "tick")
            return {"verdict": "TARGET", "line": "x", "already": False, "lines_total": 1,
                    "lines_before": 0,
                    "arrived_during": 1, "waited_s": 1.0, "lines_examined": 1}

    ticks: list[str] = []
    out = sequence._verify_after_wait(_Waits(), "x", 3.0, 0,  # type: ignore[arg-type]
                                      lambda p, t, m: ticks.append(m))
    assert ticks == ["tick"] and out["seen"] is True


def test_perform_carries_the_clients_context_to_its_wait(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end through the registered tool, from the worker thread the SDK uses."""
    import anyio

    got: list[str] = []

    class _Ctx:
        async def report_progress(self, progress: float, total: float | None = None,
                                  message: str | None = None) -> None:
            got.append(str(message))

    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)

    async def main() -> None:
        await anyio.to_thread.run_sync(
            lambda: server.perform(steps=[{"op": "resume"}], settle_seconds=0.3, ctx=_Ctx()))

    anyio.run(main)
    assert got and got[0].startswith("waiting for the machine to stop")


def test_send_keys_hands_its_progress_to_the_wait_for_the_reaction() -> None:
    """The wait for `expect` after a posted key is the longest wait this server makes in
    ordinary use, and it reports like every other bounded wait."""
    class _Route:
        launch = SimpleNamespace(watched=False, input_port=5555, logfile=None)
        stub_protocol = inputs.STUB_PROTOCOL

        def e9_mark(self) -> int:
            return 0

        @property
        def parked(self) -> bool:
            return self.at_debugger()

        def at_debugger(self) -> bool:
            return False

        def send_commands(self, commands: list[bytes]) -> list[str]:
            return []

        log_wait = _log_wait_as_guest

        def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                    progress: ds.Progress = ds.no_progress) -> dict[str, object]:
            progress(1.0, seconds, "tick")
            return {"verdict": "TARGET", "line": "READY", "already": False, "lines_total": 1,
                    "lines_before": 0,
                    "arrived_during": 1, "waited_s": 1.0, "lines_examined": 1}

    ticks: list[str] = []
    out = inputs.send_keys(_Route(), ["enter"], None, "READY", 2.0,  # type: ignore[arg-type]
                           lambda p, t, m: ticks.append(m))
    assert ticks == ["tick"] and out["verify"]["seen"] is True


def test_two_refs_on_one_address_do_not_share_a_change_watch_in_silence(
        tmp_path: Path) -> None:
    """Two declarations resolving to one seg:off would share ONE BPPM row, and clearing
    either would disarm the other without a word. One watchpoint is one declaration: the
    second is refused naming the first."""
    _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    first = server.watch_add(ref="g_rate", mode="change", length=4)
    assert first["status"] == "ok" and first["armed"] is True
    second = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert second["status"] == "INVALID" and "already armed under 'g_rate'" in str(
        second["message"])
    assert [d.ref for d in arming.current_store().declarations()] == ["g_rate"]


def test_an_aliased_change_watch_declared_while_running_stays_pending_and_says_why(
        tmp_path: Path) -> None:
    """The alias refusal holds while the guest runs (the last stop's machine resolves the
    range) and on the pending path: a change watch queued for a range that ANOTHER ref
    armed before the stop came is not armed at the stop, and the account names the ref."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    first = server.watch_add(ref="g_rate", mode="change", length=4)
    assert first["armed"] is True
    fake.running = True
    fake.halted = False
    second = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert second["status"] == "INVALID" and "already armed under 'g_rate'" in str(
        second["message"])
    # Queued BEFORE the alias existed, aliased by the time the stop drains the queue.
    server.watch_clear(ref="g_rate")
    dstate.STATE.armed.clear()
    queued = server.watch_add(ref="00AF:0017A6EC", mode="change", length=4)
    assert queued["status"] == "ok" and queued["state"] == "pending", queued
    dstate.STATE.armed[("watch", "g_rate")] = [
        {"kind": "watch", "seg": 0xAF, "off": 0x17A6EC, "entry": "BPPM 00AF:0017A6EC"}]
    fake.running = False
    fake.halted = True
    stop = server.resume()
    still = stop["applied_on_stop"]["still_pending"]
    assert len(still) == 1 and "already armed under 'g_rate'" in still[0], still


def test_the_front_door_table_names_exactly_the_tools_the_server_registers() -> None:
    """The README's tool table is the one copy of the roster a stranger reads, and it is
    kept by hand: a tool added to the server and left out of it, or a row kept after a
    tool was retired, is silent either way. The table is read as the set of backticked
    names in its first column and compared with the MCP layer's own registry, so the gate
    goes red when a name is missing AND when one is extra; a name listed twice is a row
    the reader meets twice and is refused too."""
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    head = "| tool | what it does |"
    assert head in readme, "the front door has no tool table headed by tool/what it does"
    rows = readme.split(head, 1)[1].split("\n\n", 1)[0].splitlines()[1:]
    listed: list[str] = []
    for row in rows:
        cells = row.split("|")
        assert len(cells) >= 3, f"not a table row: {row!r}"
        listed += re.findall(r"`([a-z_]+)`", cells[1])
    assert listed, "the table names no tool at all, so this is not a verdict"
    twice = sorted({name for name in listed if listed.count(name) > 1})
    assert not twice, f"named in more than one row: {twice}"
    registered = set(dosbox_mcp.registered_tools())
    assert set(listed) == registered, (
        f"missing from the table: {sorted(registered - set(listed))}; "
        f"in the table but not registered: {sorted(set(listed) - registered)}"
    )


def test_every_registered_tool_is_named_in_the_instructions() -> None:
    """The `instructions` string is the one channel a session receives at connection, and a
    tool registered but not named there is one the session never learns exists. Asked of
    the MCP layer, never of a list kept beside it."""
    assert dosbox_mcp.ROSTER.unlisted(dosbox_mcp.registered_tools()) == []
    assert dosbox_mcp.ROSTER.text() in (server.mcp.instructions or ""), "the roster is missing"


def test_perform_checks_every_steps_arguments_before_any_step_runs(tmp_path: Path) -> None:
    """The contract says a bad step refuses before anything runs, and the up-front pass
    checked the op NAMES only: a `resume` ran, an irreversible act, before the next
    step's misspelt argument was seen. Every step is bound against its tool's signature
    first, and `ctx` is refused there too."""
    fake = _names(tmp_path)
    fake.halted = False
    out = server.perform(steps=[{"op": "resume"}, {"op": "status", "bogus": 1}], settle_seconds=1.0)
    assert out["status"] == "INVALID" and "bad arguments" in out["message"], out
    assert out["steps_completed"] == 0 and out["ran"] == [] and out["failed_at"] == 1
    assert fake.stop_count == 0, "the resume never went out"
    out = server.perform(steps=[{"op": "resume"}, {"op": "status", "ctx": 1}], settle_seconds=1.0)
    assert out["status"] == "INVALID" and "`ctx`" in out["message"] and out["steps_completed"] == 0


def test_two_pending_declarations_on_one_address_arm_one_row_at_the_stop(tmp_path: Path) -> None:
    """The drain read the debugger's list ONCE before its loop and never refreshed it, so
    two refs resolving to one address (a store from before the one-row rule holds them)
    both passed the 'already held' check and the second `BP` stacked a second row. The
    list learns each row as it is armed."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("bar", 0x100, kind="T")])
    fake.halted = True
    server.resume()                                   # stop 1, recorded
    store = dstate.STATE.store
    assert store is not None
    for name in ("foo", "bar"):
        store.add(dec.Declaration("breakpoint", "symbol", name, origin=dstate.STATE.session_origin))
        dstate.STATE.queue_arm(name)
    fake.running = True
    fake.running = False                              # the machine ran and stopped again
    fake.halted = True
    stop = server.resume()
    assert stop["applied_on_stop"]["armed"] == ["foo", "bar"]
    assert [r["entry"] for r in fake.rows].count("BP 00A7:0100") == 1, fake.rows


def test_one_breakpoint_row_is_one_declaration_and_an_old_store_is_attributed_whole(
        tmp_path: Path) -> None:
    """ONE ROW, ONE DECLARATION. A second declaration resolving to an address another
    breakpoint declaration already holds (a name and the SEG:OFF it sits at, or two names
    on one address) would be stored over the same row, so clearing either would send the
    removal and leave the other declared over a row the debugger no longer has. It is
    refused naming the holder. A store from before the rule can still hold two: the
    stop's attribution then names every declaration at the address instead of the first
    in silence."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("bar", 0x100, kind="T")])
    assert server.breakpoint_at(ref="foo")["armed"] is True
    second = server.breakpoint_at(ref="00A7:0100")
    assert second["status"] == "INVALID" and "'foo'" in second["message"], second
    third = server.breakpoint_at(ref="bar")
    assert third["status"] == "INVALID" and "'foo'" in third["message"], third
    assert [d.ref for d in dstate.STATE.store.declarations()] == ["foo"]  # type: ignore[union-attr]
    assert server.breakpoint_at(ref="foo")["already_stored"] is True, "a re-declaration adopts"
    # THE OLD STORE: both declarations already there, the stop at their address.
    dstate.STATE.store.add(dec.Declaration("breakpoint", "symbol", "bar",  # type: ignore[union-attr]
                                           origin=dstate.STATE.session_origin))
    fake.eip = "00000100"
    fake.halted = True
    stop = server.resume()
    assert stop["cause"].startswith("breakpoints foo, bar at ") and "every declaration" in \
        stop["cause"], stop["cause"]


def test_watch_add_refuses_an_ambiguous_name_and_stores_nothing(tmp_path: Path) -> None:
    """`breakpoint_at` refuses a name that matches several symbols before storing it;
    `watch_add` stored it and then, in change mode, read `seg` off a resolution that has
    none, escaping as a KeyError with no session block. Both modes refuse naming the
    count, with nothing stored, as the breakpoint does."""
    _names(tmp_path, symbols=[dsym.Symbol("dup", 0x100, kind="T"),
                              dsym.Symbol("dup", 0x200, kind="T")])
    for mode in ("change", "show"):
        out = server.watch_add(ref="dup", mode=mode, length=4)
        assert out["status"] == "INVALID" and "names 2 symbols" in out["message"], out
    assert dstate.STATE.store.declarations() == []  # type: ignore[union-attr]


def test_a_declaring_reply_names_its_state_in_the_lists_own_words(tmp_path: Path) -> None:
    """An armed `breakpoint_at`/`watch_add` carried no `state` at all, and the state a
    declaration could not arm in was spelt `unarmed` here and `unarmable` in the lists:
    one word per concept, and a caller reading `state` finds one on every reply."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x100, kind="T"),
                                     dsym.Symbol("var", 0x200, kind="D")])
    assert server.breakpoint_at(ref="foo")["state"] == "armed"
    assert server.watch_add(ref="var", mode="change", length=4)["state"] == "armed"
    assert server.watch_add(ref="var", mode="change", length=4)["state"] == "armed"
    failing = _names(tmp_path, symbols=[dsym.Symbol("bar", 0x300, kind="T")], arm_fails=True)
    got = server.breakpoint_at(ref="bar")
    assert got["armed"] is False and got["state"] == "unarmable", got
    del failing, fake


def test_capture_frame_replies_with_the_source_it_read_and_the_frame_asked(
        tmp_path: Path) -> None:
    """The docstring promised `source` and `at`; the reply carried `at_frame` and no
    source, so a caller could not tell which capture the still came out of when the
    default (the largest) was taken."""
    install()
    got = server.capture_frame(frame=3, dest=str(tmp_path / "f.png"))
    assert got["frame"] == 3 and got["capture_path"] == "/caps/run_001.avi", got
    assert "at_frame" not in got
    own = tmp_path / "run_000.avi"
    own.write_bytes(b"RIFF")
    named = server.capture_frame(frame=3, dest=str(tmp_path / "g.png"), capture_path=str(own))
    assert named["capture_path"] == str(own)


def test_close_says_how_the_session_ended() -> None:
    """An exit code is not a word for the ENDING, and the reply names it in `ended_by`:
    `quit` (the emulator took the signal and left on its own), `killed`
    (SIGKILL after it ignored the first signal, which every session under a pty does),
    `died` (it had already exited when `close` was called), `none`. Read off the session
    after the close."""
    class Ended(FakeSession):
        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.ended_how = "killed"
            self._alive = False
            return -9

    dstate.STATE.session = Ended()  # type: ignore[assignment]
    got = cast(dict[str, Any], server.close())
    assert got["ended_by"] == "killed" and got["exit_code"] == -9 and "how" not in got
    assert got["summary"] == "close: killed, exit code -9"
    assert cast(dict[str, Any], server.close())["ended_by"] == "none"

    class Died(FakeSession):
        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.ended_how = "died"
            self._alive = False
            return 1

    dstate.STATE.session = Died()  # type: ignore[assignment]
    died = cast(dict[str, Any], server.close())
    assert died["ended_by"] == "died" and died["exit_code"] == 1
    assert died["summary"] == "close: died, exit code 1"


def test_write_puts_bytes_at_a_name_or_an_address_and_reads_them_back(tmp_path: Path) -> None:
    """`write`: bytes to a symbol or a `SEG:OFF`, read back off the data view, `verified`
    saying whether what memory holds is what was sent, and the
    session altered from then on. A write into ROM is taken and changes nothing, which the
    readback says under `ok`; a running machine, an odd or empty hex string and an unknown
    name are refused with nothing sent."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("var", 0x200, kind="D")])
    got = cast(dict[str, Any], server.write(ref="var", data_hex="deadbeef"))
    assert got["status"] == "ok" and got["bytes_written"] == 4 and got["verified"] is True, got
    assert got["readback"] == "deadbeef" and got["seg_off"] == "00AF:00000200"
    assert got["summary"] == "write var: 4 bytes, verified True"
    assert fake.mem[(0xAF, 0x200)] == b"\xde\xad\xbe\xef"
    raw = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="12"))
    assert raw["status"] == "ok" and fake.mem[(0x40, 0x100)] == b"\x12"
    # EMPTY SAYS "is empty" AND MALFORMED SAYS "whole number of hex bytes": two different mistakes
    # with two sentences, since this server grew ONE hex parser instead of two. Paired, not
    # either-or: an `or` here would stay green if the two sentences were folded into one.
    for bad, says in (("", "is empty"), ("abc", "whole number of hex bytes"),
                      ("zz", "whole number of hex bytes")):
        out = cast(dict[str, Any], server.write(ref="var", data_hex=bad))
        assert out["status"] == "INVALID" and says in out["message"], (bad, out)
    # AND WHITESPACE BETWEEN THE BYTES IS ACCEPTED, which it always was here (`bytes.fromhex`
    # ignores it by documented design) while the scanner's own copy of the rule refused it.
    spaced = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="34 56"))
    assert spaced["status"] == "ok" and fake.mem[(0x40, 0x100)] == b"\x34\x56", spaced
    unknown = cast(dict[str, Any], server.write(ref="nope", data_hex="00"))
    assert unknown["status"] == "INVALID" and "not in the symbol table" in unknown["message"]
    fake.running = True
    running = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="12"))
    assert running["status"] == "INVALID" and "running" in running["message"], running
    assert list(fake.mem) == [(0xAF, 0x200), (0x40, 0x100)], "nothing more was written"
    plain = install()
    plain.rom = True                              # a memory-mapped register answering 0
    port = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="99"))
    assert port["status"] == "ok" and port["verified"] is False and port["readback"] == "00"
    assert port["session"]["altered"] is True


def test_a_stop_reads_only_what_the_guest_wrote_since_the_previous_stop(tmp_path: Path) -> None:
    """Every stop carries the E9 block, so it reads only what is new since the previous stop,
    never the whole log: a session's cost per stop does not grow with its log."""
    fake = _names(tmp_path)
    fake.halted = True
    fake.log = [f"line{i}" for i in range(10)]
    first = server.resume()
    assert first["e9"]["lines_total"] == 10 and first["e9"]["mark"] == 0
    assert fake.full_reads == 0 and fake.incremental_reads == 1
    fake.log += ["line10", "line11"]
    second = server.resume()
    assert second["e9"]["lines"] == ["line10", "line11"] and second["e9"]["lines_total"] == 2
    assert fake.full_reads == 0 and fake.incremental_reads == 2
    third = server.resume()
    assert third["e9"]["lines_total"] == 0 and fake.incremental_reads == 3
    fake.log = None
    assert server.resume()["e9"]["available"] is False


def test_start_leaves_the_park_at_the_debugger_recorded_as_stop_one(tmp_path: Path) -> None:
    """`start` records the park at the debugger as the session's first stop and THEN cleared
    the running state, which took the record it had just made: right after `start` the
    server held no last stop, so a `breakpoint_at` declared before any other contact read
    no machine mode and compared addresses without their real-mode aliases. The clearing
    comes first; the record survives it."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    with mock.patch("dosbox_x_server.ds.Session", lambda _l: Booted(conf=conf)):
        out = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert out["status"] == "ok", out
    recorded = dstate.STATE.as_of()
    assert recorded is not None and recorded["stop_seq"] == 1, recorded
    assert dstate.STATE.last_machine() is not None


@pytest.mark.parametrize("watched", [False, True])
def test_stop_brings_a_running_guest_back_headless_or_windowed(tmp_path: Path,
                                                               watched: bool) -> None:
    """`stop` breaks in through the debugger channel, which every session has: a running
    guest comes back with the full stop reply, `via: break` and the seconds it took, headless
    or windowed; an already-stopped one says so with `last_stop`."""
    fake = _names(tmp_path, watched=watched)
    fake.running = True
    out = cast(dict[str, Any], server.stop())
    assert out["status"] == "ok" and out["interrupted"] is True and out["via"] == "break", out
    assert "how" not in out and "running" not in out, out
    assert "focus" not in out, "nothing is clicked, so there is no focus to report"
    assert fake.break_ins == 1 and fake.running is False
    assert "regs" in out and out["pc"] == "00A7:00000000"
    assert out["summary"] == "stop: break, at 00A7:00000000"
    again = cast(dict[str, Any], server.stop())
    assert again["interrupted"] is False and again["last_stop"]["stop_seq"] >= 1
    assert fake.break_ins == 1


def test_a_headless_resume_with_nothing_declared_is_released(tmp_path: Path) -> None:
    """With `stop` reaching a headless guest there is always a way back, so a `resume` needs
    no stopper declared first: it goes out and leaves the machine running."""
    _names(tmp_path, watched=False)
    released = cast(dict[str, Any], server.resume())
    assert released["status"] == "ok" and "stop_seq" not in released, released


def test_an_interrupt_breakpoint_from_another_session_does_not_count_as_a_stopper(
        tmp_path: Path) -> None:
    """An interrupt breakpoint is never re-armed across sessions and lists as `gone`, yet
    the stopper check (which decides whether a `perform` ending on a running step waits for
    a stop) counted it. Only an interrupt this session declared can stop the machine."""
    _names(tmp_path, watched=False)
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("interrupt", "address", "BPINT 21", origin="an-earlier-session"))
    assert arming.something_can_stop_it() is False
    server.breakpoint_interrupt(number=0x21)          # this session's own: armed
    assert arming.something_can_stop_it() is True


# ------------------------------------------------- the pre-flight: values, not only shapes

def test_a_bad_value_in_a_later_step_runs_nothing_and_every_refusal_is_listed(
        tmp_path: Path) -> None:
    """A batch is checked WHOLE before its first step runs, with the same checks each tool
    runs on its own: a key name no route knows, a pattern that does not compile. Nothing
    is posted, and the reply lists every refused step so a caller fixes the batch once.
    Measured on a real guest: the first key went in and the program reacted before the
    second step's unknown name was seen."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["b"]},
        {"op": "send_keys", "keys": ["not_a_real_key_xyz"]},
        {"op": "log", "pattern": "(", "channel": "guest"}], settle_seconds=0.5))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert out["ran"] == [] and out["steps_completed"] == 0 and out["failed_at"] == 1, out
    assert fake.commands_sent == [], "a key was posted before the batch was checked"
    refused = cast(list[dict[str, Any]], out["errors"])
    assert [e["step"] for e in refused] == [1, 2], refused
    assert "not_a_real_key_xyz" in refused[0]["message"], refused[0]
    assert "pattern" in refused[1]["message"], refused[1]


def test_send_keys_refuses_an_unknown_name_before_the_window_is_touched(
        tmp_path: Path) -> None:
    """The same check, on the tool itself: an unknown key name is refused by the server
    before the helper is asked to take the focus and post, so the refusal costs no focus
    switch and reads the same whichever route would have answered."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.send_keys(keys=["a", "not_a_real_key_xyz"]))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "not_a_real_key_xyz" in out["message"], out
    assert fake.commands_sent == [], "an unknown name was sent"


def test_the_modifier_vocabulary_is_the_dos_keyboard_s() -> None:
    """The modifiers are the ones a DOS keyboard has, judged before anything is sent: the
    command key is refused by name, an unknown one with the list."""
    inputs.check_keys(["a"], ["shift", "CTRL", "alt", "option", "control"])
    with pytest.raises(ds.Invalid, match="no command key"):
        inputs.check_keys(["a"], ["cmd"])
    with pytest.raises(ds.Invalid, match="unknown modifier 'hyper'"):
        inputs.check_keys(["a"], ["hyper"])
    with pytest.raises(ds.Invalid, match="unknown key name 'bogus'"):
        inputs.check_keys(["bogus"], None)


@pytest.mark.parametrize(("op", "bad", "good"), [
    ("breakpoint_interrupt", {"number": 0x21, "ah": 0x100}, {"number": 0x21, "ah": 0x4C}),
    ("machine_map", {"sections": ["bogus"]}, {"sections": [machine.SECTION_NAMES[0]]}),
    ("scan_filter", {"operator": "=", "value": 1, "limit": 401},
     {"operator": "=", "value": 1, "limit": 400}),
    ("send_keys", {"keys": ["a"], "seconds": 5.0}, {"keys": ["a"], "expect": "R", "seconds": 5.0}),
    ("send_keys", {"keys": ["a"], "expect": "R", "seconds": -1.0}, {"keys": ["a"], "expect": "R"}),
    ("send_keys", {"keys": ["a"], "modifiers": ["cmd"]}, {"keys": ["a"], "modifiers": ["shift"]}),
    ("send_mouse", {"x": 1, "y": 1, "seconds": 5.0},
     {"x": 1, "y": 1, "expect": "R", "seconds": 5.0}),
    ("send_mouse", {"x": 1, "y": 1, "expect": "R", "seconds": -1.0},
     {"x": 1, "y": 1, "expect": "R"}),
    ("send_mouse", {"button": "wheel"}, {"button": "middle"}),
    ("send_mouse", {"x": 3}, {"x": 3, "y": 4}),
    ("send_mouse", {"button": "left", "action": "hold"}, {"button": "left", "action": "down"}),
    ("send_mouse", {"x": 3, "y": 4, "units": "px"}, {"x": 3, "y": 4, "units": "mouse"}),
    ("log", {"pattern": "(", "channel": "guest", "limit": 5}, {"pattern": "x", "channel": "guest"}),
    ("log", {"pattern": "x", "channel": "guest", "limit": 0},
     {"pattern": "x", "channel": "guest", "limit": 1}),
    ("log", {"pattern": "x", "channel": "process"}, {"pattern": "x", "channel": "all"}),
    ("log_wait", {"pattern": "x", "channel": "guest", "seconds": 0},
     {"pattern": "x", "channel": "emulator", "seconds": 3}),
    ("resume", {"seconds": -1}, {"seconds": 0}),
    ("step", {"mode": "sideways"}, {"mode": "into", "count": 2}),
    ("run_to", {"ref": "ZZZZ:", "seconds": 5}, {"ref": "00A7:0100", "control": "00A7:0200"}),
    ("breakpoint_at", {"ref": "_main", "by": "guess"}, {"ref": "_main"}),
    ("breakpoint_interrupt", {"number": 0x100}, {"number": 0x21, "ah": 0x4C}),
    ("watch_add", {"ref": "_g", "mode": "show", "length": 2, "fmt": "u32"},
     {"ref": "_g", "mode": "change", "length": 4}),
    ("read_memory", {"ref": "00A7:zz"}, {"ref": "00A7:0100"}),
    ("memdump", {"ref": "_g", "length": 0, "dest": "/x/d.bin"},
     {"ref": "_g", "length": 8, "dest": "/x/d.bin"}),
    ("memdump", {"ref": "_g", "length": 8, "dest": "d.bin"},
     {"ref": "_g", "length": 8, "dest": "/x/d.bin"}),
    ("write", {"ref": "_g", "data_hex": "abc"}, {"ref": "_g", "data_hex": "abcd"}),
    ("set_register", {"name": "xyz", "value": 1}, {"name": "ax", "value": 1}),
    ("set_register", {"name": "ax", "value": "1"}, {"name": "ax", "value": 0x1234}),
    ("symbols_load", {"path": "/x/m.map", "base": "1", "section_bases": {"1": "1"}},
     {"path": "/x/m.map", "base": "1"}),
    ("symbols_load", {"path": "/x/m.map", "base": 4096},
     {"path": "/x/m.map", "base": "0x1000"}),
    ("symbols_load", {"path": "m.map"}, {"path": "/x/m.map"}),
    ("symbols_load", {"path": "/x/m.map", "types": "t"},
     {"path": "/x/m.map", "types": "/x/t"}),
    ("capture_frame", {"frame": -1, "dest": "/x/s.png"}, {"frame": 3, "dest": "/x/s.png"}),
    ("capture_frame", {"frame": 3, "dest": "/x/s.png", "capture_path": "c.avi"},
     {"frame": 3, "dest": "/x/s.png", "capture_path": "/x/c.avi"}),
])
def test_every_registry_entry_refuses_its_bad_value_and_passes_its_good_one(
        op: str, bad: dict[str, Any], good: dict[str, Any]) -> None:
    """One bad value and one good one per registry entry, so a check that stopped judging
    (an entry pointing at a function that accepts everything) is seen: the bad value must
    raise the tool's own refusal and the good one must pass in silence."""
    with pytest.raises(ds.Invalid):
        checks.preflight(op, bad)
    checks.preflight(op, good)
    checks.preflight("status", {})        # no entry: nothing to judge


def test_wait_ready_and_close_report_their_progress() -> None:
    """The boot and the close are the waits the owner watches longest, and they painted
    nothing. The control: a prompt that is already there, and a process already gone, report
    nothing."""
    import time

    class _Booting:
        def __init__(self, prompt_after: float) -> None:
            self.at = time.monotonic() + prompt_after
            self._screen = ""
            self.proc = SimpleNamespace(poll=lambda: None)

        def _read(self, timeout: float) -> str:
            time.sleep(timeout)
            if time.monotonic() >= self.at:
                self._screen += dcons.PROMPT
            return ""

        def _mark_stopped(self) -> None:
            pass

    ticks: list[str] = []
    numbers: list[tuple[float, float | None]] = []

    def record(p: float, t: float | None, m: str) -> None:
        ticks.append(m)
        numbers.append((p, t))

    ds.Session.wait_ready(_Booting(2.2), 5.0, record)  # type: ignore[arg-type]
    assert ticks and "waiting for the debugger prompt" in ticks[0], ticks
    # Measured in time, so no total: a bar filling towards the bound reads as progress towards
    # failure.
    assert all(t is None and 0 < p < 5.0 for p, t in numbers), numbers
    control: list[str] = []
    ds.Session.wait_ready(_Booting(0.0), 5.0, lambda p, t, m: control.append(m))  # type: ignore[arg-type]
    assert control == []

    class _SlowExit:
        def __init__(self, after: float) -> None:
            self.gone_at = time.monotonic() + after

        def wait(self, timeout: float | None = None) -> int:
            time.sleep(min(timeout or 0.0, 0.1))
            if time.monotonic() < self.gone_at:
                raise subprocess.TimeoutExpired("dosbox-x", timeout or 0)
            return 0

    ticks = []
    assert dprocess.wait_exit(_SlowExit(2.2), 5.0, lambda p, t, m: ticks.append(m), "close: x") == 0  # type: ignore[arg-type]
    assert ticks and ticks[0].startswith("close: x, 1s of 5"), ticks
    assert dprocess.wait_exit(_SlowExit(9.0), 0.3, lambda p, t, m: None, "close: x") is None  # type: ignore[arg-type]


def test_read_memory_length_is_bounded_and_resume_takes_the_siblings_bound(
        tmp_path: Path) -> None:
    """Two rows of the symmetry audit: `read_memory(length)` answers `hex` and refuses a
    length the data view cannot hold; `resume(seconds)` waits for a stop the way
    `run_to` listens, and leaves the machine running when the bound expires."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], ds_="00AF")
    for bad in (0, dcons.DATA_VIEW_BYTES + 1):
        out = cast(dict[str, Any], server.read_memory(ref="g_rate", length=bad))
        assert out["status"] == "INVALID" and "memdump" in out["message"], out
    out = cast(dict[str, Any], server.resume(seconds=-1))
    assert out["status"] == "INVALID" and "is not a bound" in out["message"], out
    past = cast(dict[str, Any], server.resume(seconds=vocab.WAIT_MAX_S + 1))
    assert past["code"] == "bad_argument" and f"at most {vocab.WAIT_MAX_S:g}," in past["message"]
    fake.launch.watched = True                   # a windowed session needs no stopper
    def read_nothing(timeout: float) -> str:
        time.sleep(timeout)
        return ""

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(fake, "_read", read_nothing, raising=False)
    monkeypatch.setattr(fake, "_screen", "", raising=False)
    monkeypatch.setattr(fake, "alive", lambda: True)
    ticks: list[str] = []
    monkeypatch.setattr(server, "bridge", lambda ctx: (lambda p, t, m: ticks.append(m)))
    try:
        out = cast(dict[str, Any], server.resume(seconds=1.3))
    finally:
        monkeypatch.undo()
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["waited_s"] >= 1.2 and "STILL RUNNING" in out["note"], out
    assert ticks and ticks[0].startswith("resume: running "), ticks


def test_resume_with_a_bound_comes_back_with_the_stop_when_the_prompt_lands(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The prompt arrives inside the bound: the reply is the full stop; and a prompt seen
    with the machine not at rest when asked is said as such, the machine still running."""
    fake = _names(tmp_path)
    fake.launch.watched = True
    monkeypatch.setattr(fake, "_read", lambda timeout: dcons.PROMPT, raising=False)
    monkeypatch.setattr(fake, "_screen", "", raising=False)
    monkeypatch.setattr(fake, "alive", lambda: True)
    monkeypatch.setattr(fake, "_mark_stopped", lambda: None, raising=False)
    out = cast(dict[str, Any], server.resume(seconds=2.0))
    assert out["status"] == "ok" and out["verdict"] == "OTHER_STOP" and "pc" in out, out
    # A PROMPT SEEN WITH THE MACHINE NOT AT REST is no stop: the wait listens on to its bound.
    fake.where_raises = True
    out = cast(dict[str, Any], server.resume(seconds=0.5))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["waited_s"] >= 0.5 and "STILL RUNNING" in out["note"], out


def test_perform_refuses_a_run_to_step_without_a_control_before_the_list_runs(
        tmp_path: Path) -> None:
    """A list is checked WHOLE before its first step: a `run_to` with no control (required by
    its signature) or an empty one is found here, not five steps in, and nothing was sent."""
    fake = _names(tmp_path)
    out = cast(dict[str, Any], server.perform(steps=[{"op": "status"},
                                                     {"op": "run_to", "ref": "0000:0000"}]))
    assert out["status"] == "INVALID" and "'control'" in str(out.get("errors")), out
    empty = cast(dict[str, Any], server.perform(steps=[
        {"op": "status"}, {"op": "run_to", "ref": "0000:0000", "control": ""}]))
    assert empty["status"] == "INVALID" and "no control" in str(empty.get("errors")), empty
    assert out.get("ran") in (None, []) and fake.runto_calls == [], out


# ------------------------------------------------------ find and the scan family

_MEMFIND = Path(__file__).resolve().parent / "fixtures" / "memfind"


def _tail(name: str) -> str:
    text = (_MEMFIND / f"{name}.txt").read_text(encoding="utf-8")
    assert text.strip(), f"fixture {name} is empty, so this case would examine nothing"
    return text


def test_find_through_the_tool_searches_the_dump_and_reports_the_sibling_shape() -> None:
    """The double's dump is all zeros, so a zero pattern hits at every offset and a
    non-zero one nowhere: both counts are known from the double, not reasoned."""
    s = install()
    got = server.find(ref="0749:00000010", length=4, data_hex="0000")
    assert got["status"] == "ok", got
    assert got["hits"] == ["0749:00000010", "0749:00000011", "0749:00000012"]
    assert got["hits_total"] == 3 and got["truncated"] is False
    assert s.memdump_calls == [(0x0749, 0x10, 4)]
    assert got["summary"] == "find 0749:00000010: 3 hits of 0000 in 4 bytes"
    none = server.find(ref="0749:00000010", length=4, data_hex="ff")
    assert none["status"] == "ok" and none["hits_total"] == 0 and none["hits"] == []
    bad = server.find(ref="0749:00000010", length=4, data_hex="abc")
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", bad


def test_scan_start_through_the_tool_reports_the_opened_instance() -> None:
    install(screen=_tail("memfind_opened_0400"))
    got = server.scan_start(ref="0000:00000400", length=256)
    assert got["status"] == "ok", got
    assert got["hits_total"] == 256 and got["cell_bytes"] == 1 and got["addr"] == "0x00000400"
    assert got["summary"] == "scan_start 0000:00000400: 256 cells of 1 byte"


def test_scan_filter_through_the_tool_reports_a_finished_scan_and_says_so() -> None:
    install(screen=_tail("mems_finished"))
    got = server.scan_filter(operator="!", value=0)
    assert got["status"] == "ok", got
    assert got["hits_total"] == 0 and got["closed"] is True and got["hits"] == []
    assert got["summary"] == "scan_filter ! 0: 0 survivors, scan closed"


def test_scan_clear_through_the_tool_reports_both_outcomes() -> None:
    install(screen=_tail("memfind_cancelled"))
    got = server.scan_clear()
    assert got["status"] == "ok" and got["cleared"] is True, got
    assert got["summary"] == "scan_clear: cleared"
    install(screen=_tail("memfind_cancel_none"))
    none = server.scan_clear()
    assert none["status"] == "ok" and none["cleared"] is False, none
    assert none["summary"] == "scan_clear: nothing was open"


def test_run_to_summary_spells_a_control_that_never_counted_as_a_count_not_a_prefix(
        tmp_path: Path) -> None:
    """`control fired 0x` reads as a hex prefix with nothing after it, which is what a
    target reached before the control's first frame produces: the count is a number, so
    the summary spells it as one."""
    fake = _names(tmp_path)
    fake.runto_running = False
    fake.control_hits = 0
    got = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020", seconds=1))
    assert got["status"] == "ok" and got["verdict"] == "TARGET", got
    assert got["summary"] == "run_to 0000:0010: TARGET at 00A7:00000000, control counted 0", (
        got["summary"])
    assert "note" not in got, "a clean arrival says nothing more: no note"


def test_perform_checks_a_symbols_find_step_before_any_step_runs(tmp_path: Path) -> None:
    """`symbols_find` had no entry in the preflight registry, so a list carrying one with a
    `limit` past the ceiling, or with no question at all, pressed the keys of the steps
    before it and refused only when its own step ran (the audit of the pointer watches
    found it). The checks the tool runs on its own arguments run over the list first, so
    `ran` is empty and nothing was posted."""
    fake = _names(tmp_path, watched=True, symbols=[dsym.Symbol("_main", 0x100, kind="T")])
    fake.running = True
    fake.where_raises = True
    fake.input_effect = None
    for bad in ({"op": "symbols_find", "name": "_m", "limit": 51},
                {"op": "symbols_find", "name": "_m", "limit": 0},
                {"op": "symbols_find", "name": "", "limit": 5},
                {"op": "symbols_find"},
                {"op": "symbols_find", "name": "_m", "linear": "100"},
                # UNTYPED VALUES, as a step delivers them: a string limit is a refusal,
                # never a TypeError out of the comparison (the auditor's input).
                {"op": "symbols_find", "name": "_m", "limit": "5"},
                {"op": "symbols_find", "name": "_m", "limit": True}):
        out = server.perform(steps=[{"op": "send_keys", "keys": ["a"]}, bad], settle_seconds=1.0)
        assert out["status"] == "INVALID" and out["ran"] == [], (bad, out)
        assert out["errors"][0]["step"] == 1 and out["errors"][0]["op"] == "symbols_find", out
    assert fake.commands_sent == [], "a refused list must not have posted a key"
    # What only its step can judge still refuses THERE: a name absent from the table is
    # not a preflight refusal, and the step before it runs.
    fake.running = False
    fake.halted = True
    out = server.perform(steps=[{"op": "status"}, {"op": "symbols_find", "name": "_m", "limit": 5}])
    assert out["status"] == "ok" and out["steps_completed"] == 2, out


@pytest.mark.parametrize("bad", [
    {"op": "read_memory", "ref": "0000:0000", "length": 129},
    {"op": "read_memory", "ref": "0000:0000", "length": 0},
    {"op": "write", "ref": "0000:0000", "data_hex": "00" * 129},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "length": 129},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "fmt": "u8[129]"},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "fmt": "u16[65]"},
])
def test_perform_checks_the_data_view_ceilings_before_any_step_runs(
        tmp_path: Path, bad: dict[str, Any]) -> None:
    """`read_memory`'s length, `write`'s bytes and a show watch's width are each bounded by
    the data view, and the bounds live in the registry the whole-list check reads, so a list
    with the bad value at step 1 is refused whole with `ran` empty, like any other value."""
    _names(tmp_path)
    out = server.perform(steps=[{"op": "status"}, bad])
    assert out["status"] == "INVALID" and out["ran"] == [], (bad, out)
    assert out["errors"][0]["step"] == 1 and out["errors"][0]["op"] == bad["op"], out


def test_the_data_view_ceilings_pass_at_the_maximum_on_both_paths(tmp_path: Path) -> None:
    """THE BOUNDARY, on the registry itself: the maximum passes, one past it does not, and
    so does the synchronous call, which reads the same registry."""
    _names(tmp_path)
    checks.preflight("read_memory", {"ref": "0000:0000", "length": 128})
    checks.preflight("write", {"ref": "0000:0000", "data_hex": "00" * 128})
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "show", "length": 128})
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "show", "fmt": "u16[64]"})
    # A change watch arms a trap and reads nothing at a stop: the view's reach is not its bound.
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "change", "length": 129})
    assert server.read_memory(ref="0000:0000", length=129)["code"] == "bad_argument"
    assert server.write(ref="0000:0000", data_hex="00" * 129)["code"] == "bad_argument"


def test_drives_lines_ceiling_is_logs_ceiling_and_not_a_second_constant(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`drive` capped `lines` with a constant of its own that happened to equal `log`'s
    `LOG_LIMIT_MAX` (the audit of #69 found the copy): two numbers for one ceiling drift.
    With the one ceiling moved, `drive` follows it, refusing one past it and taking it."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.where_raises = True
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 7)
    key = {"op": "send_keys", "keys": ["a"]}
    over = cast(dict[str, Any], server.drive(act=[key], limit=8))
    assert over["status"] == "INVALID" and "outside 1..7" in over["message"], over
    assert fake.commands_sent == [], "a refused drive must not have acted"
    at = cast(dict[str, Any], server.drive(act=[key], limit=7))
    assert at["status"] == "ok", at


def test_an_address_ref_has_one_spelling_and_a_clear_takes_any_of_them(tmp_path: Path) -> None:
    """A `SEG:OFF` is one address in many spellings (case, padding), so it is stored in
    ONE, the reply carries it, a
    re-declaration in another is adopted, and a clear matches any of them."""
    fake = _names(tmp_path)
    out = server.breakpoint_at(ref="00a7:100")
    assert out["status"] == "ok" and out["ref"] == "00a7:100", out
    assert server.breakpoint_at(ref="00A7:0100")["already_stored"] is True
    cleared = server.breakpoint_clear(ref="0A7:00000100")
    assert cleared["declarations_cleared"] == 1, cleared
    assert not any(r["entry"].startswith("BP ") for r in fake.rows), fake.rows
    assert server.watch_add(ref="00AF:0100", mode="change", length=4)["ref"] == "00AF:0100"
    assert server.watch_clear(ref="00af:100")["declarations_cleared"] == 1


def test_a_second_load_with_a_narrower_pattern_keeps_what_the_first_one_placed(
        tmp_path: Path) -> None:
    """The debugger's `LV` APPENDS, and `loaded` says so, so a server table REPLACED by
    every load contradicts it: after a second `symbols_load` with a disjoint `pattern`,
    `symbols_find` answers 0 matches for a symbol of the first load, `run_to` on it is
    `unknown_ref`, and a breakpoint armed on it is listed `unresolved` with the debugger's
    real row stranded in `foreign`, impossible to clear by name.

    Loading in narrow batches is the reasonable thing to do with thousands of symbols, so
    the two halves are aligned the way the debugger already behaves: the table ACCUMULATES.
    """
    install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src, pattern="_engine_create"))
    assert first["kept"] == 1, first
    second = cast(dict[str, Any], server.symbols_load(path=src, pattern="_main"))
    assert second["kept"] == 1, second
    assert second["table_mode"] == "accumulated", second
    assert second["table_total"] == 2, second
    got = cast(dict[str, Any], server.symbols_find(name="_engine_create"))
    assert got["status"] == "ok", got
    assert got["symbols_total"] == 1, (
        "the first load's symbol is gone from the table the second load left behind")


def test_a_types_name_the_table_lacks_is_refused_before_anything_is_written(
        tmp_path: Path) -> None:
    """A REFUSAL MAY NOT ALSO CORRUPT STATE, which is this module's one rule and the reason
    the debugger is written to before the table is. The `types` check sat AFTER both, so a
    single typo refused the call with the debugger's list already grown by `LV` and this
    side's table already replaced: the caller was told it failed and the session had moved.
    """
    s = install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src, pattern="_engine_create"))
    assert first["table_total"] == 1, first
    loaded_before = list(s.loaded)
    types_file = tmp_path / "dos-djgpp32.types"
    types_file.write_text("_no_such_symbol: u32\n", encoding="utf-8")
    bad = cast(dict[str, Any], server.symbols_load(path=src, pattern="_main",
                                                   types=str(types_file)))
    assert bad["status"] == "INVALID", bad
    assert "types are named for symbols the table lacks" in bad["message"], bad
    assert s.loaded == loaded_before, "the debugger's list grew on a call that refused"
    still = cast(dict[str, Any], server.symbols_find(name="_engine_create"))
    assert still["symbols_total"] == 1, still
    gone = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert gone["symbols_total"] == 0, "the refused load's symbols landed in the table anyway"


def test_perform_a_step_missing_a_value_or_carrying_the_wrong_type_is_refused_not_crashed(
        tmp_path: Path) -> None:
    """The whole list is judged before its first step runs, and that judgement covers a
    value left out (`watch_add` without `length`) and a value of the wrong type (`length`
    as a string) the same way it covers a bad name: a refusal naming the argument, never
    a TypeError out of the checker."""
    _names(tmp_path)
    out = server.perform(steps=[{"op": "step", "count": 1, "mode": "over"},
                                {"op": "watch_add", "ref": "F000:C9B0", "mode": "show"}])
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "length" in out["message"], out["message"]
    typed = server.perform(steps=[{"op": "step", "count": 1, "mode": "over"},
                                  {"op": "read_memory", "ref": "F000:C9B0", "length": "8"}])
    assert typed["status"] == "INVALID" and typed["code"] == "bad_argument", typed
    assert "step 2 ('read_memory') length is an integer; got '8'" in typed["message"], typed
    assert "not supported" not in typed["message"]


def test_an_invalid_summary_is_cut_at_a_word_and_says_so() -> None:
    """The summary is one line a person reads without the JSON, so a long refusal is cut
    there: at a word, with a mark that says the rest is in `message`, never mid-word."""
    message = "a RELATIVE path is not a place: " + "give the dump an absolute path " * 6
    line = dosbox_mcp.BOUNDARY.line("memdump", {}, {"status": "INVALID", "code": "bad_argument",
                                           "message": message})
    head = "memdump: INVALID (bad_argument), "
    assert line.startswith(head), line
    shown = line.removeprefix(head)
    assert shown.endswith("...") and len(shown) <= 124, shown
    kept = shown.removesuffix("...")
    assert message.startswith(kept) and message[len(kept)] == " ", "cut at a word, never inside one"
    short = dosbox_mcp.BOUNDARY.line("x", {},
                                     {"status": "INVALID", "code": "c", "message": "short"})
    assert short == "x: INVALID (c), short"


def test_every_step_check_takes_what_its_tool_takes_with_the_same_defaults() -> None:
    """A check is called with a STEP's arguments, which are the tool's: a value the tool
    defaults and the check requires is a TypeError out of the checker, and a default the
    two spell differently judges a call the tool would never make."""
    ops = server._step_ops()
    for op, check in checks.BY_OP.items():
        fn = ops.get(op) or getattr(server, op)      # a tool that is not a batch step
        tool = {n: p for n, p in inspect.signature(fn).parameters.items() if n != "ctx"}
        for name, param in inspect.signature(check).parameters.items():
            if param.kind is param.VAR_KEYWORD or name == "serial":
                continue
            assert name in tool, f"{op}: the check takes `{name}`, which the tool does not"
            if param.default is param.empty:
                assert tool[name].default is param.empty, (
                    f"{op}: the tool defaults `{name}` and the check requires it")
            elif tool[name].default is not param.empty:
                assert tool[name].default == param.default, (
                    f"{op}: `{name}` defaults to {tool[name].default!r} in the tool and "
                    f"{param.default!r} in the check")


def test_watch_add_judges_the_mode_before_the_size(tmp_path: Path) -> None:
    """A bogus `mode` with no `fmt` and no `length` was refused for the size, and the mode
    surfaced only on the second call: the mode is a word of the vocabulary and is judged
    first, in the tool and in a batch step alike."""
    _names(tmp_path)
    got = server.watch_add(ref="00AF:0100", mode="bogus")
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "mode is one of" in got["message"], got["message"]
    step = server.perform(steps=[{"op": "watch_add", "ref": "00AF:0100", "mode": "bogus"}])
    assert step["code"] == "bad_argument" and "mode is one of" in step["message"], step


def test_a_breakpoint_left_armed_by_run_to_counts_as_a_stopper(tmp_path: Path) -> None:
    """A `run_to` target whose removal could not be confirmed stays in the debugger with no
    declaration behind it, and `resume` must not refuse to run a machine that row could
    stop: the debugger's own list at the last stop is what says what is armed."""
    fake = _names(tmp_path, watched=False)
    assert arming.something_can_stop_it() is False
    # THE ROW IS THE DEBUGGER'S: it sits in the list the next stop's survey reads, and in
    # the last stop's snapshot the server keeps for a running machine.
    fake.rows.append({"index": "00", "entry": "BP 00A7:5EA30"})
    dstate.STATE.last_stop["held"] = list(fake.rows)
    assert arming.something_can_stop_it() is True
    resumed = cast(dict[str, Any], server.resume())
    assert resumed["status"] == "ok", resumed


def test_start_with_an_input_port_keeps_session_as_the_last_key(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stub's whereabouts were appended after the envelope was built, so a reader
    taking the last key as the session block read `input_port` instead."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, input_port=5555)
    assert got["status"] == "ok" and got["input_port"] == 5555 and "stub" in got, got
    assert list(got)[-1] == "session", f"the reply ends in {list(got)[-1]!r}, not `session`"


def test_a_machine_independent_argument_is_refused_before_the_session_gate() -> None:
    """A segment past sixteen bits, a channel outside the vocabulary and a hex pattern that
    is not hex are as wrong with no session as with one, so they are refused cold as
    `bad_argument`; a ref the table has to resolve still answers `no_session` (the control)."""
    dstate.STATE.session = None
    calls: tuple[Callable[[], Any], ...] = (
                 lambda: server.breakpoint_at(ref="12345:0010"),
                 lambda: server.log(channel="bogus", pattern="x"),
                 lambda: server.find(ref="12345:0010", length=4, data_hex="00"),
                 lambda: server.watch_add(ref="F000:0000", mode="bogus", length=2),
                 lambda: server.scan_start(ref="12345:0010", length=4))
    for call in calls:
        got = cast(dict[str, Any], call())
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    control = cast(dict[str, Any], server.read_memory(ref="F000:0000", length=8))
    assert control["code"] == "no_session", control
    keys = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert keys["code"] == "no_session", "the key route is the session's own fact"


def _typed_into(s: FakeSession, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What reaches the terminal through `command`, recorded; each answer is a bare prompt."""
    typed: list[str] = []

    def command(text: str, **_: object) -> str:
        typed.append(text)
        return "I-> _"

    monkeypatch.setattr(s, "command", command)
    return typed


@pytest.mark.parametrize(("command", "tool"), [
    ("VRT", "`run_for(frames=1)`"), ("vrt", "`run_for(frames=1)`"), (" RUNWATCH", "`resume`"),
    ("INT 21", "`resume`"), ("int 10", "`resume`")])
def test_debug_refuses_a_typed_command_that_lets_the_guest_run(
        command: str, tool: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refused before anything reaches the terminal, naming the tool that releases the machine
    and reports the stop."""
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert tool in got["message"], got["message"]
    assert typed == [], "a refused command reached the terminal"


@pytest.mark.parametrize("command", ["BPLIST", "INTT 21", "TIMERIRQ", "INTVEC x.txt", "VRTX",
                                     "BPINT 21", "BPLIST INT", "HEAVYLOG", "LOGX"])
def test_debug_passes_a_command_that_keeps_the_machine_at_the_debugger(
        command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: the classifier reads the FIRST WORD, anchored, so `INTT` (which enters the
    handler and stays at the debugger), a longer word starting with a releasing one, and a
    releasing word further along the line all go through; so does `HEAVYLOG`, which toggles a
    ring of the CPU log and does not release the guest."""
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "ok", got
    assert typed == [command]


@pytest.mark.parametrize("command", ["BPLIST\rVRT", "BPLIST\nVRT", "\x1b[15~", "BPLIST\x1b[15~",
                                     "BPLIST\tx"])
def test_debug_refuses_a_command_carrying_a_control_character(
        command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The classifier reads the first word, and the whole string reaches the terminal: a line
    break would type a second command after it, and an escape is a key (`\x1b[15~` is the run
    key itself). `debug` is one command of printable text."""
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert typed == [], "a refused command reached the terminal"


def test_debug_refuses_a_command_that_is_not_text() -> None:
    """The schema refuses it from a client; a direct call or a probe's replayed arguments
    reach the check, which answers `bad_argument` rather than raising."""
    install()
    got = cast(dict[str, Any], server.debug(command=cast(Any, 5)))
    assert got["code"] == "bad_argument", got


def test_debug_refuses_a_typed_release_with_no_session() -> None:
    """The command's text alone decides, so the refusal comes before the session gate."""
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.debug(command="VRT"))
    assert got["code"] == "bad_argument", got
    control = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert control["code"] == "no_session", control


def test_every_tool_has_a_pre_gate_check_or_is_named_as_judged_by_the_machine() -> None:
    """An absent entry and a forgotten one look identical, so the tools deliberately without
    a check are named, and the two sets together are the registry: no more, no less."""
    registered = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert registered == set(checks.BY_OP) | checks.MACHINE_JUDGES, (
        sorted(registered ^ (set(checks.BY_OP) | checks.MACHINE_JUDGES)))


def test_the_instructions_say_a_wrong_type_is_the_schemas_refusal() -> None:
    assert "wrong TYPE" in (server.mcp.instructions or ""), "the sentence is missing"


@pytest.mark.parametrize(("ah", "refusal"), [
    (None, None),                                  # an explicit null is the `| None` it declares
    (2, None),
    ("2", "ah is "),                               # anything else is judged as the scalar
    (True, "ah is "),                              # and a bool is never a number
])
def test_a_step_takes_null_for_an_optional_scalar_and_judges_anything_else(
    ah: Any, refusal: str | None,
) -> None:
    """`breakpoint_interrupt`'s `ah` is `int | None`: a step may pass it null explicitly,
    which the schema of the tool itself accepts, and any other value is judged as an int."""
    said = step_judge.wrong_type(server.breakpoint_interrupt, {"number": 0x21, "ah": ah})
    assert (said is None) if refusal is None else (said or "").startswith(refusal), said


def test_start_hands_the_callers_flags_to_a_headless_launch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """At the tool: `flags` and `break_on_int3` reach the launch of a HEADLESS session, where
    there is no window for `window_flags` to place."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    seen: list[dlaunch.Launch] = []

    class Recorder:
        def __init__(self, launch: dlaunch.Launch) -> None:
            seen.append(launch)
            self.reap_failed = ""

        def wait_ready(self, **_: Any) -> float:
            raise ds.Invalid("session_broken", "recorded, not started")

        def close(self, **_: Any) -> None:
            pass

    monkeypatch.setattr(shutil, "which", lambda _: "/bin/true")
    monkeypatch.setattr(ds, "Session", Recorder)
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30,
                                            flags=["-set", "cpu cycles=fixed 3000"],
                                            break_on_int3=True))
    assert got["code"] == "session_broken", got
    argv = dlaunch.build_argv(seen[0])
    assert argv[argv.index("cpu cycles=fixed 3000") - 1] == "-set", argv
    assert argv[argv.index("dos break on int3=true") - 1] == "-set", argv


@pytest.mark.parametrize("spelled", ["0x1000", "1000", "0X1000"])
def test_symbols_load_takes_its_base_as_hex_text(tmp_path: Path, spelled: str) -> None:
    """A caller holds a load address in hex, so the base is hex text and no conversion is left
    to the caller."""
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base=spelled))
    assert got["status"] == "ok", got
    assert got["base"] == 0x1000, got


@pytest.mark.parametrize("bad", [4096, "-1000", "10_00", "0xZZ", ""])
def test_symbols_load_refuses_a_base_that_is_not_hex_text(tmp_path: Path, bad: object) -> None:
    """An integer is refused, not coerced: a caller passing one has done the conversion this
    argument exists to take away."""
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base=bad))
    assert got["code"] == "bad_argument" and "base" in got["message"], got


def test_section_bases_are_hex_text_too(tmp_path: Path) -> None:
    """The sectioned form: a base per section index, each hex text; an integer
    value is refused naming the section."""
    install()
    src = tmp_path / "flat.map"
    src.write_text(TLINK32_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x401000", "2": "423000"}))
    assert got["status"] == "ok" and got["kept"] == 2, got
    bad = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": 0x401000}))
    assert bad["code"] == "bad_argument" and "section_bases" in bad["message"], bad


def test_every_tool_names_its_summary_and_declares_both_hints() -> None:
    """`tool()` takes `summary=` (required) and `idempotent=`: every tool
    the MCP layer serves has its own line in `dosbox_summaries`, and its annotations carry
    BOTH hints as booleans, so a client never reads an absent hint as a guess."""
    served = dosbox_mcp.registered_tools()
    assert served and set(served) <= set(dosbox_mcp.BOUNDARY.summaries), sorted(
        set(served) - set(dosbox_mcp.BOUNDARY.summaries))
    for t in server.mcp._tool_manager.list_tools():
        hints = t.annotations
        assert hints is not None, t.name
        assert isinstance(hints.read_only_hint, bool), t.name
        assert hints.idempotent_hint is False, t.name


def test_a_stop_reply_carries_its_own_number(tmp_path: Path) -> None:
    """Every stop names the number the server gave it, `stop_seq`: what a batch with
    `summaries` counts by, and the same number `last_stop.stop_seq` names afterwards."""
    _names(tmp_path)
    got = cast(dict[str, Any], server.step(mode="over"))
    assert got["stop_seq"] == dstate.STATE.last_stop["seq"], got
    again = cast(dict[str, Any], server.step(mode="over"))
    assert again["stop_seq"] == got["stop_seq"] + 1, again


def test_perform_with_summaries_cuts_every_step_but_the_last_and_counts_the_stops(
        tmp_path: Path) -> None:
    """`summaries=True`: compact rows for every step but the one
    that matters, both files holding all of them, and the stops counted by the server."""
    _names(tmp_path)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "step", "count": 1, "mode": "over"},
               {"op": "step", "count": 1, "mode": "over"}, {"op": "registers"}],
        summaries=True))
    assert out["status"] == "ok" and out["steps_total"] == 3 and out["truncated"] is False, out
    first, second, last = out["ran"]
    assert {"summary", "status", "stop_seq", "cause"} <= set(first["reply"]), first
    assert set(first["reply"]) <= {"summary", "status", "stop_seq", "cause",
                                   "stopped_on_its_own"}, first
    assert "regs" not in second["reply"] and "regs" in last["reply"], out["ran"]
    assert out["summary"] == "perform: 3 of 3 steps", out["summary"]
    rows = Path(out["ran_path"]).read_text(encoding="ascii").splitlines()
    replies = Path(out["replies_path"]).read_text(encoding="ascii").splitlines()
    assert len(rows) == len(replies) == 3, (rows, replies)
    assert json.loads(replies[0])["reply"]["regs"], replies[0]
    stops = out["stops"]
    assert stops["stop_seq_last"] == dstate.STATE.last_stop["seq"], stops
    assert stops["unaccounted"] == 0 and stops["surveyed"] >= 2, stops
    assert stops["surveyed"] == stops["stop_seq_last"] - stops["stop_seq_first"] + 1, stops
    assert list(stops["by_cause"].values()) == [stops["surveyed"]], stops
    assert next(iter(stops["by_cause"])).startswith("no declared code breakpoint"), stops
    plain = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}]))
    assert "steps_total" not in plain and "regs" in plain["ran"][0]["reply"], plain


def test_perform_with_summaries_shows_the_first_rows_and_says_it_cut(tmp_path: Path) -> None:
    """Past `ROWS_SHOWN` the reply shows the first rows and the kept step, `truncated` says so,
    and the files still hold every step."""
    _names(tmp_path)
    n = dstate.ROWS_SHOWN + 3
    out = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}] * n, summaries=True))
    assert out["steps_total"] == n and out["truncated"] is True, out
    assert len(out["ran"]) == dstate.ROWS_SHOWN + 1 and out["ran"][-1]["step"] == n - 1, out
    assert len(Path(out["ran_path"]).read_text(encoding="ascii").splitlines()) == n


def test_summaries_is_a_yes_or_a_no(tmp_path: Path) -> None:
    _names(tmp_path)
    calls: list[Callable[[], Any]] = [
        lambda: server.perform(steps=[{"op": "registers"}], summaries="yes"),
        lambda: server.drive(act=[{"op": "registers"}], summaries=1)]
    for call in calls:
        got = cast(dict[str, Any], call())
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "summaries is true or false" in got["message"], got["message"]


# The register pane's paging mark, as the debugger paints it straight after EBP's value.
# Real mode is the reset screen (`test_dosbox_x_debug.REAL_PANE`); the PAGE line is dos-djgpp32's,
# a DJGPP client stopped by `BPINT 31 AH=02`, copied from that run's `debug("CPU")` screen.
_NOPG_LINE = "ECX=00000000  EBP=00000000NOPG  IOPL0  CPL0\r\n"
_PAGE_LINE = "ECX=000000A7  EBP=002B8690PAGEPSE IOPL3  CPL3\r\n"


def test_the_paging_mark_is_read_off_the_pane_and_absent_is_not_off() -> None:
    assert dcons.parse_paging(_NOPG_LINE) is False
    assert dcons.parse_paging(_PAGE_LINE) is True
    assert dcons.parse_paging(_NOPG_LINE + _PAGE_LINE) is True       # the newest pane wins
    assert dcons.parse_paging("Output: PAGE fault, NOPG here too") is None


@pytest.mark.parametrize(("mode", "paging", "want"), [
    ("Real", False, "real"), ("Real", None, "real"), ("Pr32", True, "paged"),
    ("Pr16", False, "protected"), ("Pr32", False, "protected"), ("Pr32", None, None)])
def test_status_names_the_cpu_mode_of_the_stop_it_is_in(
        tmp_path: Path, mode: str, paging: bool | None, want: str | None) -> None:
    """`real`, `protected` or `paged`, from the pane's mode word and its PAGE/NOPG mark; a
    protected pane with no mark is not guessed: unavailable, with why."""
    fake = _names(tmp_path, mode=mode)
    server.registers()                          # a contact that finds the park and records it
    dstate.STATE.last_stop["paging"] = paging
    got = cast(dict[str, Any], server.status())
    assert got["cpu_mode"] == want if want is not None else got["cpu_mode"]["available"] is False
    assert "cpu_mode_why" not in got, got
    assert got["pc"] == dstate.STATE.last_stop["at"], got
    fake.running = True
    running_now = cast(dict[str, Any], server.status())
    assert running_now["pc"]["available"] is False and "running" in running_now["pc"]["why"]
    assert running_now["cpu_mode"]["available"] is False, running_now
    assert "running" in running_now["cpu_mode"]["why"], running_now


def test_status_counts_the_declarations_as_the_lists_list_them(tmp_path: Path) -> None:
    """`declarations` counts this server's own declarations per family, in any state, and each
    count equals the rows its `_list` tool returns: interrupts are breakpoints there too."""
    _names(tmp_path, mode="Real", cs="0749", ds_="0749")
    assert server.status()["declarations"] == {"breakpoints": 0, "watches": 0}
    server.breakpoint_at(ref="0749:0010")
    server.breakpoint_interrupt(number=0x21)
    server.watch_add(ref="0749:0020", mode="show", length=2)
    got = cast(dict[str, Any], server.status())["declarations"]
    assert got == {"breakpoints": len(server.breakpoint_list()["breakpoints"]),
                   "watches": len(server.watch_list()["watches"])} == {
                       "breakpoints": 2, "watches": 1}, got


def test_status_with_no_session_adds_no_machine_facts() -> None:
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.status())
    assert not got["session"]["alive"] and not {"pc", "cpu_mode", "declarations"} & set(got), got
    assert got["summary"] == "status: no session", got["summary"]


def test_status_summarises_the_session_it_answers_about() -> None:
    """The summary is built from the body's reply, whose block is the short one: it reads the
    reply's own facts, so a live session is never summarised as none."""
    install()
    got = cast(dict[str, Any], server.status())
    assert got["session"]["alive"] and got["summary"] == "status: alive, stopped", got["summary"]
    install(alive=False)
    got = cast(dict[str, Any], server.status())
    assert got["summary"] == "status: DOSBox-X has exited, `close` it", got["summary"]


def test_status_does_not_name_a_stop_it_could_not_read_as_the_one_it_is_in(
        tmp_path: Path) -> None:
    """The guest stopped again and the survey of that stop was cut: the record still holds the
    PREVIOUS stop, so `pc` and `cpu_mode` are unavailable with why, never the old stop's values
    given as the current one's."""
    fake = _names(tmp_path, mode="Real")
    server.registers()                              # the park, recorded
    before = dict(dstate.STATE.last_stop)
    fake._running = True                            # it ran on...
    fake.stop_unread = True                         # ...and stopped where nobody has looked
    fake.registers_raises = True                    # ...and that stop's pane comes back cut
    fake.where_raises = True                        # ...to every reader of it
    got = cast(dict[str, Any], server.status())
    assert dstate.STATE.last_stop["seq"] == before["seq"], "the cut stop was recorded"
    assert got["pc"]["available"] is False and "not readable" in got["pc"]["why"], got
    assert got["cpu_mode"]["available"] is False, got
    assert "not readable" in got["cpu_mode"]["why"], got


def test_status_pc_is_where_the_machine_is_now_after_a_command_moved_it(tmp_path: Path) -> None:
    """A command that moves CS:IP inside a stop (`INTT`, `set_register`) makes no new stop:
    `status.pc` reads the pane now, and the stop's own pc stays in `last_stop`."""
    fake = _names(tmp_path, mode="Real", cs="0814", ds_="0814")
    server.registers()                              # the park, recorded
    stop_pc = dstate.STATE.last_stop["at"]
    fake.cs = "F000"                                # `INTT 21` took the machine into the handler
    got = cast(dict[str, Any], server.status())
    assert got["pc"].startswith("F000:") and got["pc"] != stop_pc, got
    assert dstate.STATE.last_stop["at"] == stop_pc, "the stop's record moved with it"


def test_status_counts_the_declarations_on_a_running_machine_too(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real", cs="0749", ds_="0749")
    server.breakpoint_at(ref="0749:0010")
    fake.running = True
    got = cast(dict[str, Any], server.status())
    assert got["pc"]["available"] is False, got
    assert got["declarations"] == {"breakpoints": 1, "watches": 0}, got


def test_the_stop_count_survives_a_session_closed_mid_batch() -> None:
    """A session closed mid-list clears the stop record, so the
    server's counter reads 0 afterwards: the count still covers every stop the replies carry,
    rather than coming back empty beside rows that show them."""
    dstate.STATE.last_stop.clear()
    ran = [{"op": "resume", "reply": {"summary": "s", "status": "ok", "stop_seq": n,
                                      "cause": dstate.cause({"attributed": False,
                                                             "at": f"0814:000001{n:02X}"})}}
           for n in (6, 7, 8)]
    got = sequence.account_of(ran, True, keep_last=False, since=5)["stops"]
    assert got == {"stop_seq_first": 6, "stop_seq_last": 8, "surveyed": 3,
                   "by_cause": {dstate.cause_key(dstate.cause({"attributed": False,
                                                                  "at": "0814:00000100"})): 3},
                   "unaccounted": 0}, got


def test_a_batch_writes_both_files_or_neither_and_remakes_a_vanished_scratch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = [{"step": 0, "op": "status", "reply": {"summary": "s", "status": "ok"}}]
    monkeypatch.setattr(dstate.STATE, "scratch", tmp_path / "gone")   # the OS cleaned it away
    made = account.files(sequence._batch_stem, rows, rows)
    assert made["ran_path"] and Path(made["replies_path"]).exists(), made
    real = account.write_jsonl
    calls: list[Path] = []

    def second_fails(path: Path, r: list[dict[str, Any]]) -> str:
        calls.append(path)
        out = real(path, r)
        if len(calls) == 2:
            raise OSError("disk full half way")
        return out

    monkeypatch.setattr(account, "write_jsonl", second_fails)
    failed = account.files(sequence._batch_stem, rows, rows)
    assert failed["ran_path"]["available"] is False and "disk full" in failed["ran_path"]["why"]
    assert not any(p.exists() for p in calls), [p for p in calls if p.exists()]


def test_a_bare_step_is_one_step_into_and_find_takes_the_pattern_first(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default and the order are the contract a caller relies on without naming them: a
    bare `step()` reaches the session as ONE step INTO, and `find` and `step` take their
    arguments in the published order."""
    fake = _names(tmp_path)
    asked: list[dict[str, Any]] = []
    real = fake.step

    def recording(**kw: Any) -> dict[str, object]:
        asked.append(kw)
        return real(**kw)

    monkeypatch.setattr(fake, "step", recording)
    server.step()
    assert asked == [{"mode": "into", "count": 1}], asked

    def order(fn: Callable[..., Any]) -> list[str]:
        return [p for p in inspect.signature(fn).parameters if p != "ctx"]

    assert order(server.find)[:3] == ["data_hex", "ref", "length"], order(server.find)
    assert order(server.step)[:2] == ["count", "mode"], order(server.step)


def test_drive_hands_summaries_to_its_act(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.drive(act=[{"op": "registers"}, {"op": "registers"}],
                                             summaries=True))
    act = got["act"]
    assert act["steps_total"] == 2 and act["ran_path"] and "stops" in act, act
    assert set(act["ran"][0]["reply"]) <= {"summary", "status", "stop_seq", "cause",
                                           "stopped_on_its_own"}, act["ran"][0]


@pytest.mark.parametrize("bad_step", [
    {"op": "symbols_find", "linear": "56DFZZ"},
    {"op": "symbols_load", "path": "x.map", "section_bases": {"1": 4096}}])
def test_a_list_refuses_a_bad_hex_address_before_its_first_step_runs(
        tmp_path: Path, bad_step: dict[str, Any]) -> None:
    """The hex text of `linear` and of `section_bases` is judged with the rest of the list,
    before anything runs, like every other value a step carries."""
    _names(tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}, bad_step]))
    assert got["status"] == "INVALID" and got["ran"] == [], got
    assert [e["step"] for e in got["errors"]] == [1], got["errors"]


def test_every_tool_is_summarised_by_its_own_line() -> None:
    """Each line is the tool's own: this server's function of its name, or, for a media file
    tool or a screen map tool, scry-core's line of that tool."""
    from scry_core import screen_map
    lines = dosbox_mcp.BOUNDARY.summaries
    for name in dosbox_mcp.registered_tools():
        if name in media_tools.TOOLS:
            assert lines[name] is media_tools.TOOLS[name].summary, name
        elif name.startswith("map_"):
            assert lines[name] is getattr(screen_map, name.removeprefix("map_") + "_line"), name
        elif name == "perform_export":
            assert lines[name] is recording.export_summary, name
        else:
            assert lines[name].__name__ == name, (name, lines[name])


def test_a_recorded_stop_keeps_the_paging_mark_its_survey_read(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.paging = True  # type: ignore[attr-defined]   # what a paged stop survey leaves
    server.step(mode="over")
    assert dstate.STATE.last_stop["paging"] is True


def test_a_boot_whose_call_is_cancelled_stops_waiting_for_the_prompt(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import time

    from scry_core import cancel

    class _Never:
        _screen = ""
        proc = SimpleNamespace(poll=lambda: None)

        def _read(self, timeout: float) -> str:
            return ""

    def check() -> None:
        raise asyncio.CancelledError
    monkeypatch.setattr(cancel, "check", check)
    began = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        ds.Session.wait_ready(_Never(), 5.0)  # type: ignore[arg-type]
    assert time.monotonic() - began < 1.0


def test_a_wait_step_that_ran_out_ends_the_list_and_a_run_that_did_goes_on(
        tmp_path: Path) -> None:
    """A `log_wait` whose line never came is the list's premise failing: the list ends there,
    TIMEOUT, the steps after it unsent. A run whose bound ran out hands the machine back
    stopped and surveyed, so the list goes on from there."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "log_wait", "pattern": "NEVER", "channel": "guest", "seconds": 1},
        {"op": "status"}]))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 1 and "step 1 ('log_wait')" in out["note"], out
    fake.running = False
    fake.runto_running, fake.control_hits = True, 1
    ran = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_to", "ref": "0000:0010", "control": "0000:0020"}, {"op": "status"}]))
    assert ran["status"] == "ok" and ran["steps_completed"] == 2 and "verdict" not in ran, ran


def test_a_list_that_waited_mid_way_and_ends_running_carries_no_target(
        tmp_path: Path) -> None:
    """`TARGET` says every wait ended at a stop; a list that waited mid-way and then ended
    with the machine running, with nothing to wait for, is `still_running` and no verdict."""
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_refusals = 2                     # the first resume's stop lands a moment later
    released, calls = fake.resume, [0]

    def resume() -> dict[str, object]:
        calls[0] += 1
        fake.running = calls[0] == 2            # the second one runs on, nothing to stop it
        return released()

    fake.resume = resume  # type: ignore[method-assign]
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "resume"}, {"op": "registers"}, {"op": "resume"}, {"op": "status"}],
        settle_seconds=2.0))
    assert out["status"] == "ok" and out.get("still_running") is True, out
    assert "verdict" not in out, out


def test_a_log_rewritten_between_two_stops_is_counted_from_its_start(tmp_path: Path) -> None:
    """A log rewritten shorter between two stops is read from its start, and the block says so
    with its mark at zero, rather than counting from a place in a file that no longer exists."""
    fake = _names(tmp_path)
    fake.halted = True
    fake.log = [f"line{i}" for i in range(10)]
    assert server.resume()["e9"]["lines_total"] == 10
    fake.log = ["fresh0", "fresh1"]
    again = server.resume()["e9"]
    assert (again["lines_total"], again["lines"], again["mark"]) == (
        2, ["fresh0", "fresh1"], 0), again


def test_a_bounded_resume_whose_f5_never_left_is_a_stop_with_its_verdict(
        tmp_path: Path) -> None:
    """A caller who gave `seconds` reads a verdict whatever came: an F5 that never left the
    debugger is that stop, OTHER_STOP, not a stop with no word."""
    fake = _names(tmp_path)
    fake.halted = True
    got = cast(dict[str, Any], server.resume(seconds=5))
    assert got["verdict"] == "OTHER_STOP" and "stop_seq" in got, got


def test_drive_says_its_check_was_not_made_when_the_act_ran_out(tmp_path: Path) -> None:
    """An act whose own expect missed ends there and the overall `expect` is not checked: the
    summary says so, never "no expectation" for a call that passed one."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.input_effect = None
    got = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"], "expect": "never", "seconds": 1}],
        expect="key_cue_a"))
    assert got["verify"]["available"] is False, got
    assert got["summary"] == "drive: effect not checked", got["summary"]


def test_drive_says_its_act_ended_after_its_last_step_when_the_emulator_went(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An act that ran every step and left the machine running, whose emulator was gone by the
    tail's wait, failed at no step: the refusal says after which, never a dict's repr."""
    _names(tmp_path, watched=True)
    server.breakpoint_interrupt(number=0x21)            # something declared: the tail waits
    monkeypatch.setattr(sequence, "_wait_for_stop", lambda *a, **k: "gone")
    got = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], settle_seconds=1))
    assert got.get("code") == "session_broken", {k: got[k] for k in ("summary", "status")}
    assert "GONE" in got["message"] and "available" not in got["message"], got
    assert "after its last step" in got["message"], got["message"]


def test_a_step_whose_survey_came_back_cut_is_not_said_to_be_running(tmp_path: Path) -> None:
    """A step that stopped but whose stop survey came back cut has no `pc` to name: its summary
    says the position was not read, never that a parked machine runs."""
    fake = _names(tmp_path)
    fake.registers_raises = True
    got = cast(dict[str, Any], server.step())
    assert got["session"]["running"] is False and "enrichment" in got, got
    assert "running" not in got["summary"], got["summary"]


def test_a_stop_whose_survey_came_back_cut_names_no_mode_off_the_stop_before(
        tmp_path: Path) -> None:
    """The PAGE/NOPG mark is read off a stop's own survey: when that survey comes back cut, the
    mark the session holds is the stop before's, and a mode built on it would be a guess."""
    fake = _names(tmp_path, mode="Pr32")
    fake.paging = True  # type: ignore[attr-defined]   # the previous stop's mark
    fake.halted = True
    fake.registers_raises = True
    got = cast(dict[str, Any], server.resume())
    assert got["pc"] == f"{fake.cs}:{fake.eip}", got
    assert got["cpu_mode"]["available"] is False, got


def placed_by(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, said: str) -> Path:
    """A placement helper at `WINDOW_APP` that prints `said` and records how it was asked."""
    asked = tmp_path / "helper-asked.txt"
    exe = tmp_path / "place-window"
    exe.write_text(f'#!/bin/sh\necho "$@" >> "{asked}"\nprintf %s "{said}"\n', encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("WINDOW_APP", str(exe))
    monkeypatch.delenv("WINDOW_SHARED_DISPLAY", raising=False)
    return asked


@pytest.mark.parametrize(("shared", "said"), [(False, "headless"), (True, "shared")])
def test_starts_line_names_how_the_session_is_watched(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shared: bool, said: str) -> None:
    placed_by(tmp_path, monkeypatch, "-set\nsdl display=1\n")
    kw: dict[str, Any] = {"shared": True} if shared else {}
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, **kw)
    assert got["status"] == "ok" and got["summary"].startswith(f"start g.conf: {said} on "), got


@pytest.mark.parametrize("tool", ["breakpoint_clear", "watch_clear"])
@pytest.mark.parametrize("kw", [{}, {"ref": ""}, {"ref": "x", "all": True}])
def test_a_clear_names_what_it_clears_even_past_the_pre_gate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, kw: dict[str, Any]) -> None:
    """Neither a `ref` nor `all`, or both, is refused: by the pre-gate, and by the tool itself,
    so no path to the body can take an empty `ref` for "every declaration"."""
    _names(tmp_path)
    server.watch_add(ref="00AF:0100", mode="change", length=4)
    server.breakpoint_interrupt(number=0x21)
    refused = cast(dict[str, Any], getattr(server, tool)(**kw))
    assert refused["code"] == "bad_argument", refused
    monkeypatch.setattr(checks, "check", lambda *a, **k: None)          # no pre-gate
    past = cast(dict[str, Any], getattr(server, tool)(**kw))
    assert past["code"] == "bad_argument", past
    assert dstate.STATE.store is not None and len(dstate.STATE.store.declarations()) == 2


def test_a_number_a_caller_spells_in_hex_reaches_the_tool_as_the_integer(tmp_path: Path) -> None:
    fake = install()
    got = cast(dict[str, Any], server.set_register(name="EAX", value="0xDEADBEEF"))
    assert got["value"] == "0xdeadbeef" and got["regs"]["EAX"] == "0xdeadbeef", got
    assert cast(dict[str, Any], server.set_register(name="EAX", value=""))["code"] == \
        "bad_argument"
    del fake


def test_drive_carries_its_acts_own_code_when_no_step_failed(tmp_path: Path) -> None:
    """A list the executor refused (a console step after a release with `settle_seconds` 0) is
    `not_stopped`, not a failed step: `drive` answers the act's own code."""
    fake = _names(tmp_path, watched=True)
    fake.halted = False                         # the resume leaves the guest running
    fake.where_raises = True                    # ...and it stays running: no prompt to hear
    got = cast(dict[str, Any], server.drive(act=[{"op": "resume"}, {"op": "registers"}],
                                            settle_seconds=0))
    assert got["code"] == "not_stopped", {k: got.get(k) for k in ("code", "message")}



def test_start_names_no_stop_of_its_own_beside_the_park(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The park after `start` is stop 1, the session's own: no stop "on its own" rides beside it."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert got["status"] == "ok" and "stopped_on_its_own" not in got, sorted(got)


def test_start_refuses_a_settle_bound_with_no_plan_to_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`settle_seconds` bounds a plan's waits: with no plan it would be silently ignored. The
    launch is replaced, so a regression of the refusal fails here and never starts an emulator."""
    def launched(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("the start was not refused: it reached the launch")
    monkeypatch.setattr(dosbox_lifecycle, "start", launched)
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    got = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                            settle_seconds=5))
    assert got["code"] == "bad_argument" and "plan" in got["message"], got


def test_a_refused_list_answers_the_contracts_shape(tmp_path: Path) -> None:
    """A list refused part-way is a refusal like any other: `summary`, `status`, `code`,
    `message` first."""
    _names(tmp_path)
    contract.check_refusal("perform", cast(dict[str, Any], server.perform(
        steps=[{"op": "registers"}, {"op": "write", "ref": "nowhere", "data_hex": "00"}])))


def test_the_pointer_names_the_bios_mode_and_the_screen_its_vga_mode(tmp_path: Path) -> None:
    """`vga_mode` is the VGA listing's word wherever it is spelled; the mouse driver's video mode
    is the BIOS mode number, its own word."""
    fake = _guest(tmp_path)
    moved = cast(dict[str, Any], server.send_mouse(x=1, y=1, units="mouse"))
    assert moved["pointer"]["bios_mode"].startswith("0x") and "vga_mode" not in moved["pointer"]
    del fake


def test_drive_waits_for_its_expect_five_seconds_by_default(tmp_path: Path) -> None:
    """The default bound on `drive`'s wait for `expect` is the one both servers name, and it is
    the bound the wait is handed when `seconds` is left out."""
    assert inputs.DRIVE_EXPECT_WAIT_S == 5.0
    assert dosbox_docs.DOC_VALUES["EXPECT_WAIT_S"] == "5"
    fake = _names(tmp_path, watched=True)
    fake.running = True
    server.drive(act=[{"op": "send_keys", "keys": ["a"]}], expect="key_cue_a")
    assert fake.wait_calls and fake.wait_calls[-1][1] == 5.0, fake.wait_calls


def test_log_waits_stop_refusal_names_the_pattern_and_the_stop(tmp_path: Path) -> None:
    """`wait_stopped` from `log_wait` carries what was waited for and the stop it met."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.log_wait(channel="guest", pattern="never", seconds=1))
    assert got["code"] == "wait_stopped" and got["pattern"] == "never", got
    assert got["last_stop"]["pc"] == "00A7:00000000", got


def test_the_instructions_families_are_the_registered_tools_and_the_running_ones_answer() -> None:
    """The roster's families name every registered tool once and nothing else (a misspelt name
    would be a tool the session looks for and never finds), and every tool the running sentence
    names, a whole family's included, is one a running guest is answered by."""
    assert dosbox_mcp.ROSTER.unlisted(dosbox_mcp.registered_tools()) == []
    answering = sequence.RUNNING_OK_OPS | (checks.NOT_STEPS - {"start", "build_check"})
    named = dosbox_mcp.ROSTER.answering_named() - {"registers(from_last_stop=True)"}
    assert named <= answering, sorted(named - answering)
    assert dosbox_mcp.ROSTER.running_sentence() in (server.mcp.instructions or "")


def test_a_plans_wait_is_held_to_the_one_wait_bound_before_anything_is_spawned(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start(plan=..., settle_seconds=...)` is a wait like every other: one past `WAIT_MAX_S`
    is refused before the emulator exists, in the one wait judge's sentence."""
    spawned: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a))
    conf = tmp_path / "x.conf"
    conf.write_text("[autoexec]\n")
    out = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path),
                                            session_seconds=60,
                                            plan=[{"op": "registers"}],
                                            settle_seconds=vocab.WAIT_MAX_S + 1))
    assert out["code"] == "bad_argument", out
    assert out["message"].startswith(f"settle_seconds={vocab.WAIT_MAX_S + 1} is not a bound"), out
    assert spawned == [], "refused before anything was spawned"


def test_a_raw_command_that_writes_the_guest_marks_the_session_altered() -> None:
    """A command that writes the guest's memory, registers, ports, PIC or
    DOS clock marks the session as `write` and `set_register` do, so every later reply says the
    machine was written to; a breakpoint or a listing writes no guest state and does not."""
    fake = install()
    for command in ("BPLIST", "BP 0000:0009", "BPDEL *", "MEMDUMPBIN 0:0 10", "IV 0:0 X"):
        server.debug(command=command)
        assert fake.altered is False, f"{command} writes nothing and marked the session"
    for command in ("SM 0000:0400 0FF", "sr eax 1", "SMV 400 0FF", "INTT 21", "TIMERIRQ",
                    "LOADSTATE /x/a.sav", "OUTB E9 51", "OUTP E9 51", "OUTW 80 0", "OUTD 80 0",
                    "TIME", "date 01-02-2026"):
        fake.altered = False
        got = cast(dict[str, Any], server.debug(command=command))
        assert fake.altered is True and got["session"]["altered"] is True, command


def test_debug_empties_a_line_the_debugger_did_not_take_and_says_so() -> None:
    """A command the debugger does not recognise stays on its input line, and every later
    command would be appended to it: `debug` empties the line and names what it held."""
    fake = install()
    fake._screen = "*** Debugger command not recognized\nI-> VGA_"
    got = cast(dict[str, Any], server.debug(command="VGA"))
    assert fake.console_keys == ["clear_line"], fake.console_keys
    assert "did not take 'VGA'" in got["note"], got
    fake.console_keys.clear()
    fake._screen = "Breakpoint list:\nI-> _"
    got = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert fake.console_keys == [] and "note" not in got, got


def test_debug_pages_a_listing_out_and_returns_the_rest_of_it() -> None:
    """A listing that pages leaves the pager waiting; `debug` ends it with `Q` alone and the
    rest of the listing is in the delta it returns."""
    fake = install()
    fake._screen = "page one\nI-> HELP_\n^ Paged content: Hit ENTER to continue, Q to exit paging"
    fake.after_pager = "page two\nI-> _"
    got = cast(dict[str, Any], server.debug(command="HELP"))
    assert fake.console_keys == ["end_pager"], fake.console_keys
    assert got["screen_delta"].endswith("page two\nI-> _") and got["note"] == server.PAGED_NOTE


def test_two_loads_queued_while_the_guest_runs_reach_the_debugger_together(
        tmp_path: Path) -> None:
    """Two batches loaded at one place while the guest runs accumulate in the table, so the
    debugger takes both at the next stop: a queue of one would leave the first batch named here
    and unknown there."""
    one, two = tmp_path / "one.nm", tmp_path / "two.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    two.write_text("00002000 T _second\n", encoding="utf-8")
    fake = _names(tmp_path)
    taken: list[str] = []

    def load(data: bytes) -> list[tuple[str, int]]:
        taken.extend(name for name, _ in dsym.decode(data))
        return [("loaded", len(taken))]
    fake.load_symbols = load  # type: ignore[method-assign]
    fake.running, fake.halted = True, False
    for nm in (one, two):
        assert server.symbols_load(path=str(nm), base="400000")["pending"] is True
    assert {s.name for s in dstate.STATE.table} == {"_main", "_second"}
    fake.running, fake.halted = False, True
    assert server.resume()["applied_on_stop"]["symbols_loaded"] is True
    assert sorted(taken) == ["_main", "_second"], taken


def test_a_refused_load_leaves_the_batch_still_queued(tmp_path: Path) -> None:
    one, two = tmp_path / "one.nm", tmp_path / "two.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    two.write_text("00002000 T _second\n", encoding="utf-8")
    fake = _names(tmp_path)
    fake.running, fake.halted = True, False
    server.symbols_load(path=str(one), base="400000")
    queued = dstate.STATE.pending["load"]
    assert queued, "nothing was queued"
    fake.running, fake.halted = False, True

    def refused(data: bytes) -> list[tuple[str, int]]:
        raise ds.Invalid("unexpected_answer", "LV was not acknowledged")
    fake.load_symbols = refused  # type: ignore[method-assign]
    got = cast(dict[str, Any], server.symbols_load(path=str(two), base="400000"))
    assert got["status"] == "INVALID" and dstate.STATE.pending["load"] == queued, got


def test_one_map_loaded_again_is_held_once_and_a_forgotten_table_takes_its_bases(
        tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    _names(tmp_path)
    dstate.STATE.conf_fingerprint = "conf"
    for _ in range(3):
        assert server.symbols_load(path=str(nm), base="400000")["status"] == "ok"
    assert len(dstate.STATE.map_batches) == 1, "one map loaded again is not another batch"
    dstate.STATE.section_bases[1] = 0x1000
    dstate.STATE.forget_symbols()
    assert dstate.STATE.section_bases == {}, "a forgotten table kept its section bases"


def test_a_load_at_a_stop_replaces_a_queued_batch_the_debugger_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A batch queued while the guest ran and refused at the stop stays queued for the next
    one; a load made at the stop supersedes it, so it is never applied over the new table."""
    one = tmp_path / "one.nm"
    one.write_text("00001000 T _main\n", encoding="utf-8")
    fake = _names(tmp_path)
    fake.running, fake.halted = True, False
    server.symbols_load(path=str(one), base="500000")
    assert dstate.STATE.pending["load"], "nothing was queued"
    fake.running, fake.halted = False, True
    real = fake.load_symbols

    def refuses(data: bytes) -> Any:
        raise ds.Invalid("unexpected_answer", "the debugger refused the batch")
    monkeypatch.setattr(fake, "load_symbols", refuses)
    server.status()                                # the stop's drain: refused, kept queued
    assert dstate.STATE.pending["load"], "the refused batch was not kept"
    monkeypatch.setattr(fake, "load_symbols", real)
    got = cast(dict[str, Any], server.symbols_load(path=str(one), base="400000"))
    assert got["status"] == "ok" and dstate.STATE.pending["load"] is None, got


def test_a_state_dir_the_caller_gave_is_named_as_theirs_when_a_file_holds_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "mine").write_text("a file", encoding="utf-8")
    (tmp_path / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    got = server.start(conf=str(tmp_path / "g.conf"), cwd=str(tmp_path), session_seconds=60,
                       state_dir=str(tmp_path / "mine"))
    assert got["status"] == "INVALID" and got["message"].startswith("state_dir: "), got


def test_a_breakpoint_and_a_change_watch_queued_at_one_ref_are_both_armed_at_the_stop(
        tmp_path: Path) -> None:
    """The queue holds a ref once, and both families declared under it while the guest ran
    are armed at the next stop: the account names the ref, and the debugger holds both rows."""
    fake = _names(tmp_path, watched=True, mode="Real")
    server.status()
    fake.running = True
    w = server.watch_add(ref="0814:0100", mode="change", length=2)
    b = server.breakpoint_at(ref="0814:0100")
    assert w["state"] == "pending" and b["state"] == "pending", (w, b)
    fake.running = False
    st = server.status()
    assert st["applied_on_stop"]["armed"] == ["0814:0100"], st
    assert set(dstate.STATE.armed) == {("watch", "0814:0100"), ("bp", "0814:0100")}, \
        dstate.STATE.armed


def test_an_arrival_is_attributed_to_run_tos_own_target_and_recorded_so(tmp_path: Path) -> None:
    """The breakpoint `run_to` armed is removed before the stop is surveyed, and no declaration
    sits there: the reply that says TARGET names the target as what made the stop, and so does
    `last_stop`, instead of saying no declared breakpoint did. A stop elsewhere is still looked
    for among the declarations."""
    fake = _names(tmp_path, symbols=[dsym.Symbol("_engine_load_midi", 0x3D5E0, kind="T")])
    got = cast(dict[str, Any],
               server.run_to(ref="_engine_load_midi", control="0000:0020", seconds=5))
    assert got["verdict"] == "TARGET", got
    assert got["cause"].startswith("run_to's target _engine_load_midi at "), got["cause"]
    assert server.status()["last_stop"]["cause"].startswith("run_to's target ")
    fake.runto_elsewhere = True
    fake.control_hits = 1
    other = cast(dict[str, Any], server.run_to(ref="_engine_load_midi", control="0000:0020"))
    assert other["verdict"] == "OTHER_STOP" and not other["cause"].startswith("run_to"), other


def _ok(reply: dict[str, Any]) -> dict[str, Any]:
    assert reply["status"] == "ok", reply
    return reply


def test_a_stored_declaration_follows_its_names_into_a_rebuilt_map(tmp_path: Path) -> None:
    """Nothing a declaration keeps was resolved when it was made: a name is stored as typed and
    placed again against the map loaded now, so over a rebuild that moved `_main` and `g_rate`
    the breakpoint is armed and the watch listed at the new places, never the old."""
    old, new = tmp_path / "old.nm", tmp_path / "new.nm"
    old.write_text("0016dd80 T _main\n00200000 D g_rate\n", encoding="utf-8")
    new.write_text("0017ee90 T _main\n00210040 D g_rate\n", encoding="utf-8")
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s1"
    _ok(server.symbols_load(path=str(old), base="400000"))
    _ok(server.breakpoint_at(ref="_main"))
    _ok(server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32"))
    assert "BP 00A7:16DD80" in [r["entry"] for r in fake.rows], fake.rows
    fake.rows.clear()
    dstate.STATE.session_origin = "s2"
    got = _ok(server.symbols_load(path=str(new), base="400000"))
    assert [r["ref"] for r in got["declarations"]["rearmed"]] == ["_main"], got["declarations"]
    assert [r["entry"] for r in fake.rows] == ["BP 00A7:17EE90"], fake.rows
    (bp,) = server.breakpoint_list()["breakpoints"]
    assert (bp["state"], bp["entry"]) == ("armed", "BP 00A7:17EE90"), bp
    store = dstate.STATE.store
    assert store is not None
    (watch,) = [d for d in store.declarations() if d.kind == "watch"]
    placed = placement.resolve_ref(watch, "DS", cast(ds.Session, fake))
    assert (placed["state"], placed["off"]) == ("armable", 0x210040), placed


def test_a_change_watch_that_cannot_be_placed_says_why_and_is_stored(tmp_path: Path) -> None:
    """A real-mode table with no flat base places no symbol: the change watch is kept and
    answered `unarmable` with the resolution's own reason, never a traceback; a name the loaded
    table does not define says the table, not the build."""
    real = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x1000, kind="D")], mode="Real",
                  base=-1)
    got = server.watch_add(ref="g_rate", mode="change", length=2)
    assert got["status"] == "ok" and got["state"] == "unarmable", got
    assert "FLAT base" in got["why"] and real.rows == [], got
    none = server.watch_add(ref="g_absent", mode="change", length=2)
    assert none["state"] == "unresolved" and "build" not in none.get("note", ""), none


def _deferred_load_with(tmp_path: Path, declare: Any) -> tuple[NamesFake, Path]:
    """A table with `foo`, a breakpoint on it, the guest released, `declare` run while it runs,
    and a second load of the same map queued for the stop."""
    nm = tmp_path / "foo.nm"
    nm.write_text("00001000 T foo\n", encoding="utf-8")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(nm), base="400000"))
    _ok(server.breakpoint_at(ref="foo"))
    fake.rows.clear()
    fake.running = True
    declare()
    assert server.symbols_load(path=str(nm), base="400000")["status"] == "ok"
    return fake, nm


def test_a_watch_queued_under_a_ref_the_load_re_arms_is_armed_too(tmp_path: Path) -> None:
    """The load's re-arm covers breakpoints only: a change watch queued under the same ref is
    armed at the stop on its own, not dropped from the queue with the breakpoint's ref."""
    fake, _ = _deferred_load_with(
        tmp_path, lambda: server.watch_add(ref="foo", mode="change", length=2))
    fake.running = False
    server.status()
    kinds = sorted(r["entry"].split()[0] for r in fake.rows)
    assert kinds == ["BP", "BPPM"], fake.rows


def test_a_re_arm_that_fails_after_a_deferred_load_is_armed_from_the_queue(
        tmp_path: Path) -> None:
    fake, _ = _deferred_load_with(tmp_path, lambda: None)
    fake.running = False
    fake.bp_raises = True                       # the list read after the load refuses, once
    first = server.status()
    assert any("re-arm after the load" in s
               for s in first["applied_on_stop"].get("still_pending", [])), first
    fake.bp_raises = False
    fake.running = True
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


def test_an_interrupt_breakpoint_the_store_cannot_keep_is_not_armed(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    store = dstate.STATE.store
    assert store is not None
    path = tmp_path / "decl.json"
    path.unlink(missing_ok=True)
    path.mkdir()                                  # the store's next write fails
    got = server.breakpoint_interrupt(number=0x21)
    assert got["status"] == "INVALID", got
    assert not [r for r in fake.rows if r["entry"].startswith("BPINT")], fake.rows


def test_a_show_watch_under_a_queued_ref_arms_nothing(tmp_path: Path) -> None:
    """A show watch arms nothing ever: a breakpoint queued under its ref while the guest runs
    arms the breakpoint alone at the stop, never a memory trap the watch would then read."""
    fake = _names(tmp_path, mode="Real")
    _ok(server.watch_add(ref="0814:0100", mode="show", length=2))
    server.status()
    fake.running = True
    _ok(server.breakpoint_at(ref="0814:0100"))
    fake.running = False
    server.status()
    assert [r["entry"].split()[0] for r in fake.rows] == ["BP"], fake.rows


def test_a_failed_re_arm_after_a_load_queues_only_what_the_re_arm_would_arm(
        tmp_path: Path) -> None:
    """A raw address another build left is never re-armed: the re-arm a deferred load owes
    queues this build's breakpoints, not every stored one."""
    def stale() -> None:
        store, session = dstate.STATE.store, dstate.STATE.session
        assert store is not None and session is not None
        dstate.STATE.conf_fingerprint = dlaunch.fingerprint(session.launch.conf)
        store.add(dec.Declaration("breakpoint", "address", "00A7:5C6F0", origin="s0",
                                  fingerprint="another-build", cpu_mode="protected"))
    fake, _ = _deferred_load_with(tmp_path, stale)
    fake.running = False
    fake.bp_raises = True
    server.status()
    assert "00A7:5C6F0" not in dstate.STATE.pending["arm"], dstate.STATE.pending
    assert not [r for r in fake.rows if "5C6F0" in r["entry"]], fake.rows


def test_an_interrupt_breakpoint_the_debugger_refused_is_not_kept(tmp_path: Path) -> None:
    fake = _names(tmp_path)

    def refuse(number: int, ah: int | None = None) -> str:
        raise ds.Invalid("unexpected_answer", "no BPINT row came back")

    fake.breakpoint_interrupt = refuse  # type: ignore[method-assign]
    got = server.breakpoint_interrupt(number=0x21)
    assert got["status"] == "INVALID", got
    assert server.breakpoint_list()["breakpoints"] == [], server.breakpoint_list()


def test_an_arrival_on_a_declared_breakpoint_names_both(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("foo", 0x1000, kind="T")])
    _ok(server.breakpoint_at(ref="foo"))
    fake.cs, fake.eip = "00A7", "00001000"
    got = cast(dict[str, Any], server.run_to(ref="foo", control="0000:0020", seconds=5))
    assert (got["cause"].startswith("run_to's target ")
            and "breakpoint foo is declared" in got["cause"]), got


def test_a_queued_raw_breakpoint_whose_place_cannot_be_written_is_said_at_the_stop(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    server.status()
    fake.running = True
    _ok(server.breakpoint_at(ref="0814:0100"))
    path = tmp_path / "decl.json"
    path.unlink(missing_ok=True)
    path.mkdir()                                  # the stop's write of its place fails
    fake.running = False
    got = server.status()
    assert got["status"] == "ok", got
    assert any("could not be written" in s
               for s in got["applied_on_stop"].get("still_pending", [])), got["applied_on_stop"]


@pytest.mark.parametrize(("decl", "can"), [
    (dec.Declaration("watch", "address", "0814:0100", width=2, fmt="u16", watch_mode="show"),
     False),
    (dec.Declaration("watch", "address", "0814:0100", width=2, fmt="u16", watch_mode="change"),
     True),
    (dec.Declaration("interrupt", "address", "BPINT 21", origin="an earlier session"), False),
    (dec.Declaration("interrupt", "address", "BPINT 21", origin="s-now"), True),
    (dec.Declaration("breakpoint", "symbol", "_absent", origin="s-now"), False),
    (dec.Declaration("breakpoint", "symbol", "_main", origin="s-now"), True),
], ids=["show", "change", "old-interrupt", "interrupt", "unresolved", "resolved"])
def test_what_can_stop_the_guest_is_what_would_be_armed(tmp_path: Path,
                                                        decl: dec.Declaration,
                                                        can: bool) -> None:
    """A show watch arms nothing, an interrupt of an earlier session is not re-armed, a name the
    table does not define arms nothing: none of them can bring a running guest back."""
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")], mode="Real")
    dstate.STATE.session_origin = "s-now"
    dstate.STATE.last_stop["held"] = []
    store = dstate.STATE.store
    assert store is not None
    store.add(decl)
    assert arming.something_can_stop_it() is can


def _protected_table(tmp_path: Path) -> NamesFake:
    """A table loaded at a protected-mode stop, its base measured off CS (00A7)."""
    nm = tmp_path / "prog.nm"
    nm.write_text("0016dd80 T _main\n00200000 D _g_eng_rate\n", encoding="utf-8")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(nm), base_from="CS"))
    return fake


def test_a_stop_outside_the_program_says_so_for_every_symbol(tmp_path: Path) -> None:
    """A stop in a real-mode BIOS handler the program called into has no selector to place a
    protected-mode symbol through: readers, a breakpoint and a scan answer that the machine
    stopped outside the program, never the segment check's own number."""
    fake = _protected_table(tmp_path)
    fake.mode, fake.cs, fake.ds = "Real", "F000", "0040"
    read = server.read_memory(ref="_g_eng_rate", length=4)
    assert read["status"] == "INVALID" and "outside the program" in read["message"], read
    assert "0x0000 to 0xFFFF" not in read["message"], read
    bp = server.breakpoint_at(ref="_main")
    assert bp["state"] == "unarmable" and "outside the program" in bp["why"], bp


def test_a_protected_stop_in_another_selector_places_by_the_programs_own(
        tmp_path: Path) -> None:
    """A stop in a DPMI host's 16-bit code holds the host's selectors: a symbol is placed
    through the selector its table was measured against, not the one the stop holds."""
    fake = _protected_table(tmp_path)
    fake.cs, fake.ds = "0018", "0020"
    bp = _ok(server.breakpoint_at(ref="_main"))
    assert bp["entry"].startswith("BP 00A7:"), bp


def test_a_table_of_another_build_is_refused_and_the_loaded_one_stays(tmp_path: Path) -> None:
    """The executable beside a table is the build's own record: a table that disagrees with it
    is refused before the debugger takes anything, and the table loaded before stays."""
    guest = Path(__file__).resolve().parent / "guest"
    fake = _names(tmp_path)
    good = tmp_path / "good" / "dpmi.sym"
    good.parent.mkdir()
    shutil.copy(guest / "dpmi.sym", good)
    shutil.copy(guest / "dpmi.exe", good.parent / "dpmi.exe")
    loaded = _ok(server.symbols_load(path=str(good), base_from="CS"))
    assert loaded["checked"]["agree"] > 100, loaded["checked"]
    stale = tmp_path / "stale" / "dpmi.sym"
    stale.parent.mkdir()
    shutil.copy(guest / "dpmi.exe", stale.parent / "dpmi.exe")
    stale.write_text("".join(
        f"{int(p[0], 16) + 0xD0:08x} {p[1]} {p[2]}\n" if len(p) == 3 and p[1] == "T" else ln + "\n"
        for ln in good.read_text(encoding="utf-8").splitlines() for p in [ln.split()]),
        encoding="utf-8")
    before, base, loads = list(dstate.STATE.table), dict(dstate.STATE.base), fake.loads
    refused = server.symbols_load(path=str(stale), base_from="CS")
    assert refused["status"] == "INVALID" and "another build's" in refused["message"], refused
    assert dstate.STATE.table == before and dict(dstate.STATE.base) == base, "state moved"
    assert fake.loads == loads, "the debugger was handed the refused table"


def test_a_second_batch_at_the_same_base_accumulates_whatever_stop_it_is_loaded_at(
        tmp_path: Path) -> None:
    """The program's selectors are a fact about the table, not about where it sits: a second
    batch at the same base, loaded at a real-mode stop, adds to the first."""
    first, second = tmp_path / "a.nm", tmp_path / "b.nm"
    first.write_text("0016dd80 T _main\n", encoding="utf-8")
    second.write_text("0017ee90 T _other\n", encoding="utf-8")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(first), base="400000"))
    fake.mode = "Real"
    got = _ok(server.symbols_load(path=str(second), base="400000"))
    assert got["table_mode"] == "accumulated", got
    assert {s.name for s in dstate.STATE.table} >= {"_main", "_other"}


def test_a_table_loaded_while_the_guest_runs_takes_no_selectors_from_the_last_stop(
        tmp_path: Path) -> None:
    """The last stop may be another program's: a real-mode table loaded while the guest runs
    keeps no selectors, and is placed by its paragraph at the real-mode stop that follows."""
    nm = tmp_path / "rm.nm"
    nm.write_text("00000100 T _start\n", encoding="utf-8")
    fake = _names(tmp_path)
    server.status()                                  # a protected-mode stop recorded
    fake.running = True
    assert server.symbols_load(path=str(nm), base="8000")["status"] == "ok"
    fake.running, fake.mode = False, "Real"
    got = server.breakpoint_at(ref="_start")
    assert got["state"] == "armed", got


def test_symbols_load_hands_keep_noise_on_and_reads_a_map_with_a_byte_no_utf8_reads(
        tmp_path: Path) -> None:
    """`keep_noise` reaches the plan (a section label kept or excluded by it), and the map is
    read leniently: a code-page byte in a line counts that line unread, never a refusal."""
    nm = tmp_path / "prog.nm"
    nm.write_bytes(b"00001000 t .text\n0016dd80 T _main\n\xb0 not a row\n")
    _names(tmp_path)
    plain = _ok(server.symbols_load(path=str(nm), base="400000"))
    _names(tmp_path)
    noisy = _ok(server.symbols_load(path=str(nm), base="400000", keep_noise=True))
    assert plain["excluded_sections"] == 1 and noisy["excluded_sections"] == 0, (plain, noisy)
    assert noisy["kept"] == plain["kept"] + 1 and plain["unreadable"] == 1, (plain, noisy)


def test_a_stop_named_while_the_machine_is_in_it_names_its_declaration_too() -> None:
    """The words a `wait_stopped` refusal names the stop with carry the declaration it is at,
    read off the record, not only its address."""
    state = dstate.State()
    session = SimpleNamespace(stop_count=3)
    state.remember_stop(cast(ds.Session, session), {"cs": "0814", "eip": "00001A27"}, {}, [],
                        {"attributed": True, "ref": "_tick", "by": "symbol",
                         "at": "0814:00001A27"})
    stop, words = state.stop_named(cast(ds.Session, session))
    assert stop["pc"] == "0814:00001A27" and words == " at 0814:00001A27 (_tick)", words


def test_start_takes_the_version_probe_out_of_the_ready_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The `-version` probe is part of the start: what it spends comes off the wait for the
    debugger's prompt, so a build that hangs on it costs no more than the start's own bound."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    waited: list[float] = []

    class Recorder:
        def __init__(self, launch: dlaunch.Launch) -> None:
            self.reap_failed = ""

        def wait_ready(self, timeout: float, **_: Any) -> float:
            waited.append(timeout)
            raise ds.Invalid("session_broken", "recorded, not started")

        def close(self, **_: Any) -> None:
            pass

    def slow_facts(resolved: Any, seconds: float) -> dict[str, Any]:
        waited.append(seconds)
        time.sleep(0.3)
        return {"binary": resolved.path, "binary_origin": resolved.origin, "version": "v"}

    monkeypatch.setattr(shutil, "which", lambda _: "/bin/true")
    monkeypatch.setattr(dlaunch, "binary_facts", slow_facts)
    monkeypatch.setattr(ds, "Session", Recorder)
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path),
                                            session_seconds=30))
    assert got["code"] == "session_broken", got
    asked, ready = waited
    assert asked == binaries.VERSION_TIMEOUT_S, waited
    assert ready <= ds.READY_TIMEOUT_S - 0.3, waited


def test_close_carries_the_last_words_of_both_channels_when_the_end_was_not_clean(
        tmp_path: Path) -> None:
    """Why it ended, in the reply that ends it: the console's last words (the debugger's
    terminal, escapes stripped) and the logfile's, each the newest `TAIL_CHARS`, on an end
    that was not a clean quit, or when `detail` asks; a clean quit names them in `omitted`.
    With no logfile the log's tail is unavailable, saying why."""
    log = tmp_path / "s.log"
    log.write_text("x" * 2000 + "LOG: the end\n", encoding="utf-8")

    class Ended(FakeSession):
        def __init__(self, how: str, code: int, logfile: Path | None) -> None:
            super().__init__()
            self._how, self._code = how, code
            self.launch = SimpleNamespace(cwd=Path("/"), logfile=logfile, watched=False)

        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.ended_how, self._alive = self._how, False
            return self._code

        def console_tail(self, chars: int) -> str:
            return ("y" * 3000 + "Exit to error: the console's own words")[-chars:]

    dstate.STATE.session = Ended("killed", -9, log)  # type: ignore[assignment]
    got = cast(dict[str, Any], server.close())
    assert got["stdout_tail"].endswith("the console's own words"), got
    assert len(got["stdout_tail"]) == log_marks.TAIL_CHARS, len(got["stdout_tail"])
    assert got["errorlog_tail"].endswith("LOG: the end\n"), got
    dstate.STATE.session = Ended("quit", 0, None)  # type: ignore[assignment]
    clean = cast(dict[str, Any], server.close())
    assert "stdout_tail" not in clean and {"stdout_tail", "errorlog_tail"} <= set(
        clean["omitted"]) and "detail=True" in clean["how"], clean
    dstate.STATE.session = Ended("quit", 0, None)  # type: ignore[assignment]
    asked = cast(dict[str, Any], server.close(detail=True))
    assert asked["stdout_tail"] and asked["errorlog_tail"]["available"] is False, asked
    assert "logfile" in asked["errorlog_tail"]["why"], asked


def test_the_process_facts_ride_at_the_top_of_status_and_close_and_the_block_keeps_the_rest(
        ) -> None:
    """What the process is (`pid`, the conf and its digest, the bound) is asked for: it rides at
    the top of `status`, `start` and `close`. The block keeps what every reply
    must carry: alive, running, altered and each alarm while it holds."""
    install()
    st = cast(dict[str, Any], server.status())
    assert st["pid"] == 4242 and "conf_digest" in st and "bound_s" in st, st
    assert set(st["session"]) == {"alive", "running", "altered"}, st["session"]
    read = cast(dict[str, Any], server.registers())
    assert "pid" not in read and set(read["session"]) == {"alive", "running", "altered"}, read
    closed = cast(dict[str, Any], server.close())
    assert closed["pid"] == 4242 and set(closed["session"]) == {"alive", "running", "altered"}, (
        closed)


def test_a_watched_window_is_placed_by_the_host_s_helper_on_the_display_asked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A watched session's window goes where `WINDOW_APP` says, asked as `dosbox --shared` and
    the display; its flags reach the command line one token per line, a `-set` pair included,
    and the reply says which display it went to."""
    asked = placed_by(tmp_path, monkeypatch, "-set\nsdl display=1\n")
    seen: list[dlaunch.Launch] = []

    def booted(launch: dlaunch.Launch) -> Any:
        seen.append(launch)
        raise ds.Invalid("session_broken", "recorded, not started")

    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    monkeypatch.setattr("scry_core.binaries.version", lambda *_a, **_k: "DOSBox-X (a stub)")
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    with mock.patch("dosbox_x_server.ds.Session", booted):
        server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=60, shared=True,
                     display="main")
    assert seen and seen[0].window_flags == ["-set", "sdl display=1"], seen
    assert asked.read_text().split() == ["dosbox", "--shared", "--display", "main"]
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    assert got["status"] == "ok" and got["display"] == "secondary", got


def test_a_watched_start_with_no_helper_is_refused_and_a_display_needs_a_watched_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No helper, no window placed: a watched start is the host's to fix, never given a geometry
    invented here. A `display` on a headless run is refused: nobody looks at a display there."""
    monkeypatch.delenv("WINDOW_APP", raising=False)
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    assert got["code"] == "host_failed" and "WINDOW_APP" in got["message"], got
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, display="main")
    assert got["code"] == "bad_argument" and "nobody watches" in got["message"], got
    placed_by(tmp_path, monkeypatch, "")
    quiet = _start_on_a_booted_fake(tmp_path, monkeypatch, shared=True)
    assert quiet["status"] == "ok", "one display, no flags: an answer, and the window opens"


def test_a_list_begun_on_a_running_guest_waits_for_its_stop_before_a_console_step(
        tmp_path: Path) -> None:
    """The executor's rule on both servers: a list begun on a running machine waits for its
    stop before its first step that needs one, as one that released the machine itself does,
    never sending the step to be refused at once."""
    fake = _names(tmp_path)
    fake._running = True
    out = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}], settle_seconds=0.3))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 0 and "still running" in out["note"], out


def test_a_terminal_that_overflows_while_the_list_waits_ends_it_with_what_ran(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The keys were posted and the machine released before the wait's read found a hole in
    the terminal: the reply carries those steps, the overflow as the list's end."""
    fake = _names(tmp_path)
    fake._running = True

    def overflowed(*_a: Any, **_k: Any) -> tuple[bool, float]:
        raise ds.Invalid("unexpected_answer", "the terminal buffer overflowed and 4096 bytes "
                         "were discarded during this read")

    monkeypatch.setattr(ds.Session, "await_stop", overflowed)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "send_keys", "keys": ["a"]}, {"op": "registers"}], settle_seconds=0.5))
    assert out["code"] == "unexpected_answer" and "overflowed" in out["message"], out
    assert [s["op"] for s in out["ran"]] == ["send_keys"] and out["steps_completed"] == 1, out


def test_a_raw_breakpoint_stored_before_modes_were_kept_is_adopted_by_the_stop_that_places_it(
        tmp_path: Path) -> None:
    """A raw row with no cpu mode (a store written before modes were kept) was never placed
    under any map, so the first stop that can place it arms it, writes its place and its mode,
    and makes it this session's (the owner's decision)."""
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0814:010B", cpu_mode=None, origin="old",
                           fingerprint="0123456789abcdef"))
    got = arming.rearm_declarations(cast(Any, fake))
    assert [r["ref"] for r in got["rearmed"]] == ["0814:010B"], got
    (row,) = st.declarations()
    assert row.cpu_mode == "real" and row.origin == "this-session", row
    assert row.fingerprint != dec.PENDING_STAMP, row


def test_a_state_load_keeps_the_table_and_its_base_is_measured_again_at_the_next_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The restored machine may hold the program at another base: the table is kept (no load
    again), and the first stop after the load measures the base the load measured, through the
    same register, moving the symbols' places and the breakpoints armed by name with it."""
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf)))
    assert loaded["status"] == "ok" and dstate.STATE.base["base"] == 0x00400000, loaded
    monkeypatch.setattr(type(fake), "selector",
                        lambda self, reg: {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B})
    fake.eip = "00001004"                           # stopped in `_tick`, the program's code
    dstate.STATE.pending["remeasure"] = True        # what a state load leaves
    out = arming.apply_pending(cast(Any, fake))
    assert dstate.STATE.table and dstate.STATE.base["base"] == 0x00500000, dstate.STATE.base
    assert out["base_remeasured"] == {"register": "CS", "from": "0x00400000",
                                      "to": "0x00500000"}, out
    assert dstate.STATE.pending["remeasure"] is False


def test_a_state_load_asks_the_next_stop_to_measure_a_measured_base_again(
        tmp_path: Path) -> None:
    """Only a base the load measured off the machine is measured again: one the caller gave is
    the caller's, and no table means nothing to place."""
    _names(tmp_path, symbols=[dsym.Symbol("_tick", 0x1000, kind="T")])
    dstate.STATE.base_measured_from = "CS"
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is True
    dstate.STATE.pending["remeasure"] = False
    dstate.STATE.base_measured_from = None
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is False


def _loaded_then_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *,
                          cs: str = "00B7") -> NamesFake:
    """A table loaded off CS at a program stop, then a state load: the restored machine holds the
    program at another base under the selector `cs`."""
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf)))
    assert loaded["status"] == "ok" and dstate.STATE.base["selector_CS"] == 0xA7, loaded
    monkeypatch.setattr(type(fake), "selector",
                        lambda self, reg: {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B})
    fake.cs, fake.eip = cs, "00001004"      # stopped in `_tick`, the program's own code
    dstate.STATE.machine_replaced()
    return fake


def test_the_base_measured_again_takes_the_program_s_selectors_with_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The restored run's host gave the program other selectors: a breakpoint armed by name
    goes through the new one, never the selector of the run the table was loaded in."""
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    out = arming.apply_pending(cast(Any, fake))
    assert dstate.STATE.base["selector_CS"] == 0xB7, dstate.STATE.base
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert placement.target_for(0x1000, "CS", cast(Any, fake))[0] == 0xB7


def test_a_stop_outside_the_program_s_code_leaves_the_base_to_measure_at_the_next(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real-mode stop (a BIOS or DOS handler the program called into) holds no selector of the
    program's: measured there, the table would move to whatever CS holds."""
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    asked: list[str] = []

    def selector(self: Any, reg: str) -> dict[str, int]:
        asked.append(reg)
        return {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B}

    monkeypatch.setattr(type(fake), "selector", selector)
    for mode, eip in (("Real", "00001004"), ("Pr32", "00F00000")):   # a handler; a host's code
        fake.mode, fake.eip = mode, eip
        out = arming.apply_pending(cast(Any, fake))
        assert dstate.STATE.base["base"] == 0x00400000 and "base_remeasured" not in out, out
        assert dstate.STATE.pending["remeasure"] is True
        assert any("not in the program's protected-mode code" in w
                   for w in out["still_pending"]), out
    assert asked == [], "a stop outside the program asks no descriptor"


def test_a_re_arm_that_fails_after_the_base_moved_queues_what_it_would_arm(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The base has moved whatever the re-arm answers: the account says so, the failure is
    pending, and the drain goes on to the queues it was there for."""
    fake = _loaded_then_restored(tmp_path, monkeypatch)

    def cut(_session: Any) -> dict[str, Any]:
        raise ds.Invalid("unexpected_answer", "the pane was cut")

    monkeypatch.setattr(arming, "rearm_declarations", cut)
    out = arming.apply_pending(cast(Any, fake))
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert any("the pane was cut" in w for w in out["still_pending"]), out


def test_a_pending_measure_is_said_by_status_and_drained_by_the_next_contact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A parked load leaves the machine at the loaded position: the next reader measures there,
    not the next stop tool wherever it lands."""
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    assert dstate.STATE.pending_summary()["base_remeasure"] is True
    import dosbox_running as running
    running.drain_if_stopped(cast(Any, fake))
    assert dstate.STATE.base["base"] == 0x00500000, dstate.STATE.base
    assert dstate.STATE.pending_summary()["base_remeasure"] is False


def test_a_load_refused_before_it_was_sent_replaced_nothing(tmp_path: Path) -> None:
    """`machine_replaced` is the last load's: a refusal before anything went down the channel
    leaves it False whatever an earlier state command left behind."""
    import dosbox_saved_states as saved
    ses = SimpleNamespace(machine_replaced=True, state_sent=True,
                          _state_dir=lambda: tmp_path)
    with pytest.raises(ds.Invalid) as refusal:
        saved.state_load(cast(Any, ses), "nope")
    assert refusal.value.code == "unknown_ref" and ses.machine_replaced is False


def test_one_row_that_cannot_be_adopted_is_that_row_s_answer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two rows stored before modes were kept: the first refuses to arm, the second is adopted
    all the same, and the re-arm answers both."""
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    for ref in ("0814:010B", "0814:0200"):
        st.add(dec.Declaration("breakpoint", "address", ref, cpu_mode=None, origin="old",
                               fingerprint="0123456789abcdef"))
    armed = type(fake).arm_code_breakpoint

    def first_refuses(self: Any, seg: int, off: int) -> dict[str, object]:
        if off == 0x010B:
            raise ds.Invalid("unexpected_answer", "the debugger refused it")
        return armed(self, seg, off)

    monkeypatch.setattr(fake, "arm_code_breakpoint", first_refuses.__get__(fake))
    got = arming.rearm_declarations(cast(Any, fake))
    assert [r["ref"] for r in got["rearmed"]] == ["0814:0200"], got
    assert [r["ref"] for r in got["unarmable"]] == ["0814:010B"], got


def test_a_row_armed_whose_place_could_not_be_written_is_queued_for_the_next_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The breakpoint is armed, so the re-arm would skip it as held and never write its place:
    the row is queued, and its account says so."""
    fake = _names(tmp_path, mode="Real")
    dstate.STATE.session_origin = "this-session"
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0814:010B", cpu_mode=None, origin="old",
                           fingerprint="0123456789abcdef"))

    def refuses(*_a: Any, **_k: Any) -> None:
        raise dec.StoreWriteError("the disk is full")

    monkeypatch.setattr(st, "apply", refuses)
    got = arming.rearm_declarations(cast(Any, fake))
    (row,) = got["rearmed"]
    assert "next stop writes it again" in row["why"], row
    assert "0814:010B" in dstate.STATE.pending["arm"]


def test_a_base_that_moved_clears_the_rows_armed_by_name_at_the_old_place(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The debugger's rows outlive a state load, and on the restored machine the old place is
    someone else's bytes: the breakpoint declared by name is cleared there and armed anew."""
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    fake.cs = "00A7"                                   # declared before the load, at the old place
    dstate.STATE.pending["remeasure"] = False
    declared = cast(dict[str, Any], server.breakpoint_at(ref="_tick"))
    assert declared["status"] == "ok", declared
    cleared: list[tuple[int, int]] = []
    def clear(self: Any, seg: int, off: int) -> dict[str, object]:
        cleared.append((seg, off))
        return {"removed": True}

    monkeypatch.setattr(type(fake), "clear_code_breakpoint", clear)
    fake.cs = "00B7"
    dstate.STATE.machine_replaced()
    out = arming.apply_pending(cast(Any, fake))
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert cleared == [(0xA7, 0x1000)], cleared
    assert [r["entry"] for r in dstate.STATE.armed[("bp", "_tick")]] == ["BP 00B7:1000"]


def test_a_state_load_through_the_server_asks_the_next_stop_for_the_base(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end through `state_load`: a load the session says replaced the machine queues the
    base's measure; one it says did not (refused before it was sent) queues nothing."""
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    assert cast(dict[str, Any], server.symbols_load(path=str(mapf)))["status"] == "ok"
    dstate.STATE.pending["remeasure"] = False

    def loads(self: Any, name: str, seconds: float = 20.0) -> dict[str, object]:
        self.machine_replaced = name == "here"
        if name != "here":
            raise ds.Invalid("unknown_ref", f"no state named {name!r}")
        return {"name": name, "paused": True}

    monkeypatch.setattr(type(fake), "state_load", loads, raising=False)
    assert cast(dict[str, Any], server.state_load(name="gone"))["code"] == "unknown_ref"
    assert dstate.STATE.pending_summary()["base_remeasure"] is False
    assert cast(dict[str, Any], server.state_load(name="here"))["status"] == "ok"
    assert dstate.STATE.pending_summary()["base_remeasure"] is True
    assert dict(dstate.STATE.pending)["dirty"] is True


def test_a_base_the_caller_gave_is_never_measured_again(tmp_path: Path) -> None:
    """A base `symbols_load` was handed is the caller's: a state load leaves it as it is."""
    _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf), base="400000"))
    assert loaded["status"] == "ok", loaded
    assert dstate.STATE.base_measured_from is None
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is False


def test_drive_with_an_expect_leaves_the_wait_to_it_on_a_running_guest(tmp_path: Path) -> None:
    """The verify is the wait: an act on a running guest does not first sit out
    `settle_seconds` for a stop at its tail, or its effect would be judged after the wait ran
    out and never looked for."""
    fake = _names(tmp_path, watched=True, mode="Real")
    declared = cast(dict[str, Any], server.breakpoint_at(ref="0814:0100"))
    assert declared["status"] == "ok", declared        # something that can stop the guest
    fake.running = True
    fake.where_raises = True
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    out = cast(dict[str, Any], server.drive(act=[{"op": "status"}], expect="NEVER_LOGGED",
                                            seconds=0.2, settle_seconds=1.0))
    assert out["act"].get("verdict") != "TIMEOUT", out["act"]
    assert out["verify"].get("available") is not False, out["verify"]


def test_a_stop_already_parked_is_heard_by_a_wait_of_no_seconds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`settle_seconds=0` waits for nothing, but a stop that already came is a stop: the one look
    at the terminal after the bound hears it, and the console step runs."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_raises = True

    def parked(timeout: float) -> str:
        fake.where_raises = False       # the prompt already sits in the drain
        return dcons.PROMPT

    monkeypatch.setattr(fake, "_read", parked, raising=False)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0))
    assert out["status"] == "ok" and out["steps_completed"] == 2, out


def test_the_stop_a_list_ends_on_may_be_the_retrace_a_run_for_left_armed(
        tmp_path: Path) -> None:
    """A stop no tool made is one a release reached: a retrace `run_for` left armed is named as
    its likeliest cause, and the flag is spent, as for a bounded `resume`."""
    fake = _names(tmp_path)
    declared = cast(dict[str, Any], server.breakpoint_at(ref="0814:0100"))
    assert declared["status"] == "ok", declared
    fake.halted = False
    dstate.STATE.retrace_pending = True
    out = cast(dict[str, Any], server.perform(steps=[{"op": "resume"}], settle_seconds=2.0))
    assert "retrace" in str(out["stopped"].get("cause")), out["stopped"]
    assert dstate.STATE.retrace_pending is False


def test_a_stop_tool_s_drain_is_not_repeated_by_the_next_contact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stop reply drains what was pending before it reads; the next contact finds the same
    stop and nothing new asked, so it drains nothing again (a console round trip a stop)."""
    import dosbox_running as running
    fake = _names(tmp_path)
    running.stop_reply(cast(Any, fake))
    dstate.STATE.pending["arm"] = ["9999:9999"]       # still waiting for a stop that places it
    dstate.STATE.pending["dirty"] = False
    drains: list[int] = []

    def counted(_session: Any) -> dict[str, Any]:
        drains.append(1)
        return {"armed": [], "disarmed": []}

    monkeypatch.setattr(arming, "apply_pending", counted)
    running.drain_if_stopped(cast(Any, fake))
    assert drains == [], "the stop's own drain was taken for none"
