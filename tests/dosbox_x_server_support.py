"""The DOSBox-X server: the helpers its test modules share."""

from __future__ import annotations

import ast
import atexit
import dataclasses
import inspect
import itertools
import json
import re
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest
from scry_core import (
    host_program,
    screen_map,
)
from scry_core import log_wait as core_wait
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab

import dosbox_binary as binaries
import dosbox_declarations as dec
import dosbox_folds as folds
import dosbox_grammar as grammar
import dosbox_inputs as inputs
import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

#: What the DJGPP guest's debugger printed to `SELINFO <reg>` over the channel
#: (`fixtures/channel/scry-dpmi.json`), by register.
SELINFO_CAPTURED = {
    e["request"].split()[-1]: e["lines"]
    for e in json.loads((Path(__file__).parent / "fixtures" / "channel" / "scry-dpmi.json")
                        .read_text(encoding="utf-8"))["exchanges"]
    if e["request"].startswith("EXEC SELINFO ")}

MEASURED_BASE = 0x00400000


def _log_wait_as_guest(self: Any, pattern: str, seconds: float, channel: str, mark: int = 0,
                       progress: ds.Progress = ds.no_progress) -> dict[str, object]:
    got: dict[str, object] = self.e9_wait(pattern, seconds, mark=mark, progress=progress)
    return got


def stub_build(monkeypatch: pytest.MonkeyPatch, debugger_headless: bool = True,
               commands: tuple[str, ...] = binaries.COMMANDS) -> None:
    """What a faked build carries, read at `start` off a path that holds no file."""
    monkeypatch.setattr(binaries, "debugger_headless", lambda _b: debugger_headless)
    monkeypatch.setattr(binaries, "debugger_commands", lambda _b: list(commands))


def stubbed_build() -> Any:
    """`stub_build` for a case with no monkeypatch at hand."""
    return mock.patch.multiple(binaries, debugger_headless=lambda _b: True,
                               debugger_commands=lambda _b: list(binaries.COMMANDS))

class RunStateOnly:
    """A fake's debugger channel: `RUNSTATE` answered from the fake's own `run_state`, else its
    `at_debugger`, which is what the real stop wait polls; any other request is a fake that fell
    behind."""

    def __init__(self, fake: Any) -> None:
        self.fake = fake

    def request(self, command: str, seconds: float = 5.0,
                poll: Any = None) -> tuple[bool, list[str]]:
        assert command == "EXEC RUNSTATE", f"the fake's channel takes only RUNSTATE: {command!r}"
        stopped = getattr(self.fake, "run_state", self.fake.at_debugger)()
        state = "stopped" if stopped else "running"
        return True, [f"DEBUG: RUNSTATE {state} cycles=0 ms=0.000000000"]


class SessionGates:
    """The real session's stop and build gates, run against a fake's own `at_debugger`."""

    @property
    def control(self) -> RunStateOnly:
        return RunStateOnly(self)

    def mark_stopped(self) -> None:
        """A fake is stopped as long as its `at_debugger` says."""

    def forget_stop(self) -> None:
        """A fake is stopped as long as its `at_debugger` says."""

    commands = frozenset(binaries.COMMANDS)
    has = ds.Session.has
    require_stopped = ds.Session.require_stopped
    require_run_state = ds.Session.require_run_state
    delete_rows = ds.Session.delete_rows
    gone_if_dead = ds.Session.gone_if_dead


class FakeSession(SessionGates):
    """The narrowest faithful stand-in for a session: it does what the contract says."""

    def __init__(self, *, alive: bool = True, answer: str = "some output", took: bool = True,
                 mode: str = "Real") -> None:
        self.altered = False
        # the data-view screens are real-mode; a case on the protected-mode `SELINFO` capture says
        # `Pr32`
        self.mode = mode
        self._alive = alive
        # what every debugger command prints, and whether the debugger took it
        self.answer, self.took = answer, took
        self.executed: list[str] = []
        self.memory: dict[int, int] = {}
        self.closed = 0
        self.proc = SimpleNamespace(poll=lambda: None if self._alive else -15, pid=4242)
        self.launch = SimpleNamespace(cwd=Path("/"), logfile=None, watched=False)
        self._avi_facts: dict[tuple[str, int, int], dict[str, object]] = {}
        self.e9_calls: list[tuple[str, int]] = []
        self.log_calls: list[tuple[str, int, str]] = []
        self.since_marks: list[int] = []
        self.loaded: list[tuple[str, int]] = []
        # what the address-taking tools were handed: tells a forwarded address from a forwarded zero
        self.memdump_calls: list[tuple[int, int, int]] = []
        self.conditions: list[str] = []

    reap_failed = ""
    drain_ended = "the descriptor reached end of file"
    survey_text = ""
    ended_how = "none"

    def alive(self) -> bool:
        return self._alive

    def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
        return 0.0

    def break_in(self, seconds: float = 5.0) -> float:
        raise ds.Invalid("no_channel", "the emulator never dialled the debugger channel")

    def save_state(self, name: str, seconds: float = 20.0) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this DOSBox-X has no `SAVESTATE` debugger command")

    def stub_replaced(self) -> None:
        """No input link here to prove again."""

    def load_state(self, name: str, seconds: float = 20.0) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this DOSBox-X has no `LOADSTATE` debugger command")

    def state_list(self) -> dict[str, object]:
        return {"state_dir": "/x/save", "states": [],
                "working_slot": {"available": False, "why": "no working slot"}}

    def snapshot(self, dest: Path | None = None, seconds: float = 10.0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        raise ds.Invalid("no_channel", "this session is headless: there is no window")

    def state(self) -> dict[str, object]:
        # the real shape: a two-key stub let the `altered` guarantee be deleted with the suite green
        return {"pid": 4242, "alive": self._alive,
                "running": self._alive and bool(getattr(self, "running", False)),
                "altered": self.altered,
                "conf": "/x/g.conf", "conf_digest": "abc123", "conf_changed_on_disk": False,
                "watched": False, "bound_s": 60, "elapsed_s": 1.0,
                "output_bytes_dropped": 0, "captures": "off",
                "state_dir": "the emulator's own save/ under its working directory"}

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        self.executed.append(command)
        if command.upper().startswith("SELINFO "):
            return True, SELINFO_CAPTURED[command.split()[-1].upper()]
        return self.took, self.answer.splitlines()

    def command(self, text: str, seconds: float | None = None) -> str:
        return "\n".join(self.exec(text, seconds)[1])

    def await_stop(self, began: float, deadline: float, target: str,
                   progress: ds.Progress = ds.no_progress, label: str = "") -> tuple[bool, float]:
        return ds.Session.await_stop(cast(ds.Session, self), began, deadline, target, progress,
                                     label)

    def retrace(self, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return False, 0.0

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return False, 0.0

    def registers(self) -> dict[str, str]:
        return {"EAX": "00001234"}

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return True

    def where(self) -> dict[str, str]:
        return {"cs": "F000", "eip": "0000FFF0", "mode": self.mode}

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.where(), self.registers()

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        return self.where(), self.registers(), self.breakpoints()

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """THE REAL METHOD, over this double's `memdump`."""
        return ds.Session.read_bytes(self, seg, off, n, mode)  # type: ignore[arg-type]

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
        return {"entry": grammar.interrupt_row(number, ah), "removed": True}

    masks = False
    rom = False

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
        return False

    def resume(self) -> dict[str, object]:
        # a constant: what `halted` is read off is exercised against captured deltas
        return {"output": "", "halted": False, "stopped_at": None}

    # contracts, not behaviour (driven against a debugger double in `test_dosbox_x_debug.py`);
    # each returns its tool's field set, so a tool dropping `running` or `arrived` shows
    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        return {"mode": mode, "asked": count, "completed": count, "running": False,
                "moved": True, "stalled": 0,
                "before": {"cs": "F000", "eip": "0000FFF0", "mode": "Real"},
                "after": {"cs": "F000", "eip": "0000FFF5", "mode": "Real"}}

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        # a constant, not the echoed bound: an echoed `seconds` would pass as a measurement
        return {"verdict": "TARGET", "target": f"{seg:04X}:{off:04X}",
                "stopped_at": {"cs": f"{seg:04X}", "eip": f"{off:08X}",
                               "mode": "Real"},
                "waited_s": 0.25, "breakpoint_removed": True, "note": "",
                "control": contract.unavailable("no control was named") if control is None else
                {"at": f"{control[0]:04X}:{control[1]:04X}", "hits": 0, "removed": True}}

    def watch_places(self, places: list[tuple[int, int]]) -> list[dict[str, object]]:
        return [self.watch(seg, off) for seg, off in places]

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        return {"command": "BPM 0040:006C", "mode": "Real",
                "armed": "BPMEM 0040:006C", "breakpoints": [],
                "fires_on": "a CHANGE to the value"}

    def e9_mark(self) -> int:
        return 0

    stub_protocol = inputs.STUB_PROTOCOL

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
        dlogs.check_channel(channel)
        return {"verdict": "TARGET", "pattern": pattern, "channel": channel,
                "line": "Bochs port E9h: [+ 0.000] BOOT  . start", "already": True,
                "lines_total": 1, "lines_before": 0, "arrived_during": 0, "waited_s": 0.0,
                "lines_examined": 1}

    def e9(self, pattern: str, limit: int) -> tuple[list[str], int]:
        self.e9_calls.append((pattern, limit))
        return ["one line"], 500

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        dlogs.check_channel(channel)
        self.log_calls.append((pattern, limit, channel))
        self.since_marks.append(since_mark)
        return ["one line"], 500

    def condition_breakpoint(self, row: str) -> str:
        """`BPIF`, which this stand-in records and lists nothing for."""
        self.conditions.append(row)
        return f"DEBUG: Set conditional breakpoint: {row}"

    def clear_condition_breakpoint(self, row: str) -> dict[str, object]:
        return {"entry": f"BPIF {row}", "removed": False, "note": "no such breakpoint to remove"}

    def vgamemdump(self, offset: int, length: int, dest: Path) -> Path:
        """Video memory, which this stand-in holds none of: zeros."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(length))
        return dest

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        """`memory` by real-mode linear address, zeros where it holds nothing."""
        self.memdump_calls.append((seg, off, length))
        dest.parent.mkdir(parents=True, exist_ok=True)
        base = (seg << 4) + off
        dest.write_bytes(bytes(self.memory.get(base + i, 0) for i in range(length)))
        return dest

    def captures(self) -> list[dict[str, object]]:
        # largest LAST: the text-mode boot, then the real one; `capture_frame`'s default rests on it
        return [{"path": "/caps/run_000.avi", "bytes": 107194, "riff_avi": True,
                 "avi_frames": 40, "complete": True},
                {"path": "/caps/run_001.avi", "bytes": 19296742, "riff_avi": True,
                 "avi_frames": 5428, "complete": True}]

    def frame(self, at: int, dest: Path, source: Path | None = None) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG" + b"\x00" * 2000)
        return dest

    def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
        self.closed += 1
        self._alive = False
        self.ended_how = "quit"
        return 0

    def stdout_tail(self, chars: int) -> str:
        return ""

    def output_tail(self, chars: int) -> str:
        return ""

    def selector(self, reg: str) -> dict[str, int]:
        """THE REAL METHOD, over the CAPTURED descriptor replies."""
        return ds.Session.selector(self, reg)      # type: ignore[arg-type]

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        """What the debugger would hold afterwards, INCLUDING what it already held."""
        self.loaded += dsym.decode(data)
        return list(self.loaded)


@pytest.fixture(autouse=True)
def clean_session() -> Any:
    """No live session before a case, and NONE LEFT BEHIND after one."""
    dstate.STATE.session = None
    dstate.STATE.store = None
    dstate.STATE.session_origin = None
    dstate.STATE.conf_fingerprint = None
    dstate.STATE.last_stop.clear()
    dstate.STATE.clear_running_state()
    dstate.STATE.forget_symbols()
    dstate.STATE.cancelled = None
    dstate.STATE.maps = screen_map.Maps()
    yield
    dstate.STATE.session = None
    dstate.STATE.store = None
    dstate.STATE.session_origin = None
    dstate.STATE.conf_fingerprint = None
    dstate.STATE.last_stop.clear()
    dstate.STATE.clear_running_state()
    dstate.STATE.forget_symbols()
    dstate.STATE.cancelled = None
    dstate.STATE.maps = screen_map.Maps()


_STORE_TMP = tempfile.mkdtemp(prefix="dosbox-x-server-test-")
atexit.register(shutil.rmtree, _STORE_TMP, ignore_errors=True)
_INSTALL_SEQ = itertools.count()


def install(**kw: Any) -> FakeSession:
    s = FakeSession(**kw)
    dstate.STATE.session = s  # type: ignore[assignment]
    # a session and its store come together; the conf key is a counter, as CPython reuses
    # `id()` of freed objects and the stores share one file
    dstate.STATE.store = dec.DeclarationStore(
        f"install-{next(_INSTALL_SEQ)}", path=Path(_STORE_TMP) / "declarations.json")
    return s


FFMPEG_FIX = Path(__file__).resolve().parent / "fixtures" / "ffmpeg"


def _ffmpeg_record(case: str) -> dict[str, Any]:
    """What ffmpeg answered in one recorded case (exit code, bytes written, stderr)."""
    return cast(dict[str, Any], json.loads((FFMPEG_FIX / f"{case}.json").read_text("utf-8")))


def _tools_called_in_tests(source: str) -> set[str]:
    """The tools a test file CALLS THROUGH THE SERVER from inside its `test_*` functions."""
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


def live_callers() -> set[str]:
    """The tools that CALL `live()`, asked of the source rather than remembered."""
    def asks(node: ast.AST) -> bool:
        return any(isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                   and sub.func.id == "live" for sub in ast.walk(node))

    tree = ast.parse(Path(str(server.__file__)).read_text(encoding="utf-8"))
    direct = {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and asks(node)}
    # a fold's methods ask in `dosbox_folds`, each in its own body
    folded = {tool for tool, table in (("comment_write", folds.COMMENT), ("map_write", folds.MAP),
                                       ("scan", folds.SCAN), ("state_write", folds.STATE_METHODS))
              if any(asks(ast.parse(inspect.getsource(m.body))) for m in table.values())}
    return direct | folded



def _launch_of(**kw: Any) -> dlaunch.Launch:
    """Run `start` far enough to capture the `Launch` it built, and no further."""
    seen: list[dlaunch.Launch] = []

    def build(launch: dlaunch.Launch) -> Any:
        seen.append(launch)
        raise ds.Invalid("session_broken", "not starting anything: this case wants the Launch only")

    with mock.patch("scry_core.binaries.shutil.which", lambda _n: "/somewhere/dosbox-x"), \
         mock.patch("dosbox_x_server.ds.Session", build), stubbed_build():
        server.start(**kw)
    assert seen, "`start` never reached the Launch"
    return seen[0]



NM_TEXT = ("0016df20 T _main\n"
           "0005c830 T _engine_load_midi\n"
           "0005aa20 T _engine_create\n"
           "0013a020 t .text\n")


def _source(tmp_path: Path, text: str = NM_TEXT) -> str:
    p = tmp_path / "djgpp32.sym"
    p.write_text(text, encoding="utf-8")
    return str(p)


# minimal, not the symbols suite's fixture: the assertion is that the flag survives the seam
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


# a real ILINK32 map (tests/fixtures/borland-ilink32/PROVENANCE.txt): `Start` reads ZERO and the
# bases are distinct, so ignoring the section index would misplace every symbol
ILINK32_MAP = Path(__file__).parent / "fixtures" / "borland-ilink32" / "sections32.map"
ILINK32_BASES = {"1": "0x401000", "2": "0x423000", "3": "0x4289B8"}


#: A descriptor that is not present, as the probe guest's real-mode stop printed it for FS
#: (`fixtures/channel/scry-real.json`), respelled for CS: the type field is what decides.
SELINFO_ZEROED = ["SelectorInfo CS:", "CS: b:000EF000 type:00 parbg",
                  "    l:0000CA60 dpl : 0 01110"]


def returned_key_sets(fn: object) -> list[frozenset[str]]:
    """The literal keys of EACH dict a function returns, one set per `return`."""
    src = textwrap.dedent(inspect.getsource(cast(Any, fn)))
    # a delegating method is read at the body it hands the call to
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
    def returned(node: ast.AST) -> ast.Dict | None:
        if not isinstance(node, ast.Return):
            return None
        value = node.value.elt if isinstance(node.value, ast.ListComp) else node.value
        return value if isinstance(value, ast.Dict) else None
    return [keys(d) for node in ast.walk(ast.parse(src)) if (d := returned(node)) is not None]

def documented(tool: str) -> str:
    import dosbox_mcp
    root = Path(__file__).resolve().parent.parent
    family = next(f for f, tools in dosbox_mcp.ROSTER.families if tool in tools)
    pages = (root / "docs" / "reference" / f"{family.lower()}.md", root / "REFERENCE.md")
    return " ".join(" ".join(p.read_text(encoding="utf-8").split()) for p in pages)


# every bucket a different number: with two at zero, swapping them is invisible.
# `nm` shape: a long name (truncated_names), two statics sharing fifteen chars (disambiguated),
# three placeable section labels (noise), one N and one A (unplaceable), a pattern dropping two.
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



class NamesFake(SessionGates):

    survey_text = ""

    def __init__(self, *, mode: str = "Pr32", cs: str = "00A7", ds_: str = "00AF",
                 conf: Path | None = None, arm_fails: bool = False,
                 watched: bool = True, input_port: int | None = None) -> None:
        self.mode, self.cs, self.ds = mode, cs, ds_
        self._peek_carry = ""
        self.vars_held = 0
        self.arm_fails = arm_fails
        # the guest runs: every console method refuses as the real ones do, `at_debugger()` says so
        self._running = False
        self.stop_count = 0
        self.stop_unread = False
        self.reap_failed = ""
        self.drain_ended = ""
        self.ended_how = "none"
        self.mem: dict[tuple[int, int], bytes] = {}
        self.log: list[str] | None = []
        self.eip = "00000000"
        self.halted = False
        self.step_running = False
        self.runto_running = False
        self.runto_elsewhere = False
        self.control_hits = 0
        self.rows: list[dict[str, str]] = []
        self.bp_calls = 0
        self.survey_calls = 0
        self.bp_raises = False
        self.where_raises = False
        self.where_refusals = 0
        self.alive_flag = True
        self.registers_raises = False
        self.altered = False
        self.dies_on_resume = False
        self.commands_sent: list[list[bytes]] = []
        self.break_ins = 0
        # the stub's view of the driver: pointer, buttons, mapped range, BIOS mode
        self.stub_protocol = inputs.STUB_PROTOCOL
        self.pointer = (320, 96)
        self.buttons = 0
        self.mouse_max = (639, 199)
        self.video_mode = 3
        self.pointer_snaps = 1
        self.reports_lost: set[int] = set()
        self.reports = 0
        self.input_effect: str | None = None
        self.after_effect: list[str] = []
        self.resume_effect: list[str] = []
        self.scancodes_sent: list[bytes] = []
        self.wait_calls: list[tuple[str, float, int]] = []
        self.full_reads = 0
        self.incremental_reads = 0
        self.wait_raises: Exception | None = None
        self.stops_during_wait = False
        self.runto_calls: list[tuple[int, int, float]] = []
        self.launch = dlaunch.Launch(conf=conf or Path("/x.conf"), cwd=Path("/"), seconds=60,
                                watched=watched, input_port=input_port)

    def listing(self, command: str) -> str:
        """A debugger whose listings print nothing a parser takes."""
        return ""

    def alive(self) -> bool:
        return self.alive_flag

    def run_state(self) -> bool:
        """What `RUNSTATE` says, off the state `where()` answers from."""
        if self.where_refusals > 0:
            self.where_refusals -= 1
            return False
        return not (self.where_raises or self.running)

    def state(self) -> dict[str, object]:
        return {"alive": self.alive_flag, "running": self._running, "altered": False}

    def report_line(self) -> str:
        x, y = self.pointer
        return (f"STUB  . mouse x={x} y={y} buttons={self.buttons} "
                f"max={self.mouse_max[0]},{self.mouse_max[1]} mode={self.video_mode} "
                f"screen=720x400")

    def send_commands(self, commands: list[bytes]) -> list[str]:
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
            offset = 0
        return list(self.log[offset:]), len(self.log)

    log_wait = _log_wait_as_guest

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        self.wait_calls.append((pattern, seconds, mark))
        if self.wait_raises is not None:
            raise self.wait_raises
        if self.stops_during_wait:
            self.running = False
            raise ds._wait_stopped(pattern, 0, 0.4, parked=False, at_bound=False)
        # the real method's answers: bad pattern or bound is `Invalid`, expiry the `TIMEOUT` verdict
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
        # the effect line was appended before the wait began, so it was ALREADY there
        return {"verdict": "TARGET", "line": hits[0], "already": True, "lines_total": len(hits),
                "lines_before": self.log[mark:].index(hits[0]), "arrived_during": 0,
                "waited_s": 0.0, "lines_examined": len(self.log) - mark}

    def where(self) -> dict[str, str]:
        if self.where_refusals > 0:
            self.where_refusals -= 1
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
            self.stop_count += 1
        self._running = value

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        # a stop nobody has read: the real peek counts the transition inside this call
        if self.stop_unread:
            self.stop_unread = False
            self.running = False
        return not self.running

    def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
        self.alive_flag = False
        self.ended_how = "killed"
        return 0


    def stdout_tail(self, chars: int) -> str:
        return ""
    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.where(), self.registers()

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
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
            self.alive_flag = False
        if self.log is not None:
            self.log.extend(self.resume_effect)
        return {"halted": self.halted,
                "stopped_at": {"cs": self.cs, "eip": self.eip, "mode": self.mode},
                "output": "OK"}

    def step(self, mode: str = "over", count: int = 1) -> dict[str, object]:
        self.running = self.step_running
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
        # `runto_running`: the bound ran out (TIMEOUT); `runto_elsewhere`: another's stop
        verdict = ("TIMEOUT" if self.runto_running else
                   "OTHER_STOP" if self.runto_elsewhere else "TARGET")
        return {"verdict": verdict, "target": f"{segment:04X}:{offset:04X}",
                "stopped_at": {"cs": self.cs, "eip": self.eip, "mode": self.mode},
                "waited_s": 0.0, "breakpoint_removed": True, "control": ctl,
                "note": "" if verdict == "TARGET" else f"{verdict.lower()}: not at the target"}

    def command(self, text: str, **_k: object) -> str:
        if text.startswith("BPDEL "):
            idx = text.split()[1]
            self._relist([r for r in self.rows if r.get("index") != idx])
        return ""

    def _relist(self, rows: list[dict[str, str]]) -> None:
        self.rows[:] = [{**r, "index": f"{i:02d}"} for i, r in enumerate(rows)]

    def _listed(self, entry: str) -> None:
        self._relist([{"index": "", "entry": entry}, *self.rows])

    def arm_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        if self.running:
            raise ds.NotStopped("the machine is running; nothing was armed")
        if self.arm_fails:
            raise ds.Invalid("not_stopped", "the machine is running; nothing was armed")
        entry = f"BP {seg:04X}:{off:04X}"
        self._listed(entry)
        return {"target": f"{seg:04X}:{off:04X}", "entry": entry, "breakpoints": self.rows}

    def _console(self) -> None:
        if self.running:
            raise ds.NotStopped("the machine is running; the console takes no command")

    def clear_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        self._console()
        entry = f"BP {seg:04X}:{off:04X}"
        before = len(self.rows)
        self._relist([r for r in self.rows if r["entry"] != entry])
        return {"entry": entry, "removed": len(self.rows) < before}

    def breakpoint_interrupt(self, number: int, ah: int | None = None) -> str:
        self._console()
        entry = grammar.interrupt_row(number, ah)
        self._listed(entry)
        return f"DEBUG: Set interrupt breakpoint at INT {number:02X}"

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        self._console()
        entry = grammar.interrupt_row(number, ah)
        before = len(self.rows)
        self._relist([r for r in self.rows if r["entry"] != entry])
        return {"entry": entry, "removed": len(self.rows) < before}

    def condition_breakpoint(self, row: str) -> str:
        self._console()
        self._listed(f"BPIF {row}")
        return f"DEBUG: Set conditional breakpoint: {row}"

    def clear_condition_breakpoint(self, row: str) -> dict[str, object]:
        self._console()
        before = len(self.rows)
        self._relist([r for r in self.rows if r["entry"] != f"BPIF {row}"])
        return {"entry": f"BPIF {row}", "removed": len(self.rows) < before}

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        if self.running:
            raise ds.Invalid("unexpected_answer",
                "no register pane came back, so this console is not taking "
                             "commands")
        self.loads = getattr(self, "loads", 0) + 1
        self.held_vars = [*getattr(self, "held_vars", []), *dsym.decode(data)]
        return list(self.held_vars)

    def selector(self, reg: str) -> dict[str, int]:
        if self.running:
            raise ds.Invalid("unexpected_answer", "no register pane came back")
        return {"base": 0x00400000, "limit": 0x0023FFFF, "type": 0x1B, "big": 1}

    def watch_places(self, places: list[tuple[int, int]]) -> list[dict[str, object]]:
        return [self.watch(segment=seg, offset=off) for seg, off in places]

    def watch(self, segment: int | None = None, offset: int | None = None,
              linear: int | None = None) -> dict[str, object]:
        self._console()
        seg, off = int(segment or 0), int(offset or 0)
        armed = f"BPPM {seg:04X}:{off:08X}" if self.mode.startswith("Pr") \
            else f"BPMEM {seg:04X}:{off:04X}"
        # the real row carries a trailing hit count `(00)` that a code breakpoint's does not
        self._listed(f"{armed} (00)")
        sent = (f"BPPM {seg:04X}:{off:04X}" if self.mode.startswith("Pr")
                else f"BPM {seg:04X}:{off:04X}")
        return {"command": sent, "mode": self.mode,
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


def _guest(tmp_path: Path) -> Any:
    fake = _names(tmp_path, watched=False)
    fake.launch = dataclasses.replace(fake.launch, logfile=Path("/e9.log"))
    fake.running = True
    return fake


E9_KEY_ACT = "Bochs port E9h: [+  66.628] ACT   . key_cue_a=0 b=-1 on=0"


def _start_on_a_booted_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                            which: bool = True, **kw: Any) -> dict[str, Any]:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    if which:
        monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
        # and its version, or the host's own `-version` would run
        monkeypatch.setattr("scry_core.binaries.version", lambda *_a, **_k: "DOSBox-X (a stub)")
        stub_build(monkeypatch)

    def booted(launch: dlaunch.Launch) -> Booted:
        fake = Booted(conf=conf)
        fake.launch.input_port = launch.input_port
        return fake

    with mock.patch("dosbox_x_server.ds.Session", booted):
        return cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                                 **kw))


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
                        conf_text: str = "[sdl]\n",
                        regpoints: tuple[str, ...] = ()) -> tuple[dict[str, Any], NamesFake]:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    conf = tmp_path / "g.conf"
    conf.write_text(conf_text, encoding="utf-8")
    booted = double(conf=conf)
    mode = "real" if booted.mode == grammar.REAL_MODE else "protected"
    store = dec.DeclarationStore(str(conf.resolve()))
    for ref, fp in stamped.items():
        store.add(dec.Declaration("breakpoint", "address", ref, created_at="t0", origin="s1",
                                  fingerprint=fp or dlaunch.fingerprint(conf.resolve()),
                                  cpu_mode=mode))
    for row in regpoints:
        store.add(dec.Declaration("regpoint", "expr", row, created_at="t0", origin="s1"))
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    stub_build(monkeypatch)
    with mock.patch("dosbox_x_server.ds.Session", lambda _l: booted):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60))
    return got, booted



def _typed_into(s: FakeSession, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What reaches the debugger through `exec`, recorded; each prints nothing."""
    typed: list[str] = []

    def exec_(text: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        typed.append(text)
        return True, []

    monkeypatch.setattr(s, "exec", exec_)
    return typed






#: Cases about a dump's two spellings, which Windows compares as one path.
CASED_PATHS = pytest.mark.skipif(sys.platform == "win32",
                                 reason="Windows compares paths without their case")
#: Cases about a `~user` naming no account, which Windows expands to a profile path regardless.
NO_SUCH_HOME = pytest.mark.skipif(sys.platform == "win32",
                                  reason="Windows expands any `~user` without asking for it")

def runnable(path: Path) -> Path:
    """`path` named as this host finds a program by name: with `.exe` on Windows."""
    return path.with_name(path.name + ".exe") if sys.platform == "win32" else path

def placed_by(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, said: str) -> Path:
    """A placement helper at `WINDOW_APP` that prints `said` and records how it was asked."""
    asked = tmp_path / "helper-asked.txt"
    exe = host_program.write(tmp_path / "place-window", "import sys\n"
                             f"open({str(asked)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                             f"sys.stdout.buffer.write({said.encode()!r})\n")
    monkeypatch.setenv("WINDOW_APP", str(exe))
    monkeypatch.delenv("WINDOW_SHARED_DISPLAY", raising=False)
    return asked


def _ok(reply: dict[str, Any]) -> dict[str, Any]:
    assert reply["status"] == "ok", reply
    return reply


def _deferred_load_with(tmp_path: Path, declare: Any) -> tuple[NamesFake, Path]:
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


def _protected_table(tmp_path: Path) -> NamesFake:
    """A table loaded at a protected-mode stop, its base measured off CS (00A7)."""
    nm = tmp_path / "prog.nm"
    nm.write_text("0016dd80 T _main\n00200000 D _g_eng_rate\n", encoding="utf-8")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(nm), base_from="CS"))
    return fake


def _loaded_then_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *,
                          cs: str = "00B7") -> NamesFake:
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf)))
    assert loaded["status"] == "ok" and dstate.STATE.base["selector_CS"] == 0xA7, loaded
    monkeypatch.setattr(type(fake), "selector",
                        lambda self, reg: {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B})
    fake.cs, fake.eip = cs, "00001004"
    dstate.STATE.machine_replaced()
    return fake
