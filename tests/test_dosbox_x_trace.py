"""`trace` against a debugger double that replays what a real one printed and wrote.

Every survey, every `LOG` command's delta and every log file the double hands back is a file
under `fixtures/trace/`, captured from live sessions (its provenance says which): the counter
`cc=`, the prompt a stop announces itself with and the lines of the log are the debugger's,
not an opinion of this file.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from channel_double import NOT_RECOGNIZED, Machine, Stop, protected, session_over
from dosbox_x_server_support import clean_session, install, runnable  # noqa: F401
from scry_core.host_program import MODE_BITS

from scry_dosbox_x import (
    arming,
    checks,
    grammar,
    machine,
    placement,
    run_state,
    server,
    start_symbols,
)
from scry_dosbox_x import binary as binaries
from scry_dosbox_x import collect as dcollect
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as sym
from scry_dosbox_x import trace as tracing

TRACE = Path(__file__).parent / "fixtures" / "trace"
GUEST = Path(__file__).parent / "guest"
MACHINE = Path(__file__).parent / "fixtures" / "machine"


def cap(name: str) -> str:
    return (TRACE / f"{name}.txt").read_text()


@dataclasses.dataclass
class TraceMachine(Machine):
    """The debugger's side of a `LOG` command, over the channel double: each `LOG` takes the next
    scripted `(log, how)`, leaves the captured log in the working directory (None: the file is
    left as it is) and stops where the log's last line is, its cycle count moved by `how`:
    `ran` the instructions the log executed, `int` one more (an interrupt counted and not run),
    `two` two more, `dynamic` none, `close` none and no move, `refused` the debugger refusing the
    file, None no stop at all. `appends` is written to the session's logfile at each `LOG`."""

    logs: list[tuple[str | None, str | None]] = dataclasses.field(default_factory=list)
    logfile: Path | None = None
    appends: str = ""

    def _do_log(self, _: list[str]) -> tuple[bool, list[str]]:
        name, how = self.logs.pop(0) if self.logs else (None, "close")
        if self.logfile is not None and self.appends:
            with self.logfile.open("a", encoding="latin-1") as f:
                f.write(cap(self.appends))
        if how == "refused":
            return False, ["DEBUG: Starting log", tracing.NOT_CREATED_LINE, NOT_RECOGNIZED]
        assert self.cwd is not None
        log = self.cwd / tracing.LOG_FILE
        if name is not None:
            shutil.copyfile(TRACE / f"{name}.trace", log)
        self.stopped, self._polls, self._pending = False, 0, None
        if how is not None:
            lines = log.read_text().splitlines() if log.exists() and name is not None else []
            executed = max(len(lines) - 1, 0)
            moved = {"ran": executed, "int": executed + 1, "two": executed + 2,
                     "dynamic": 0, "close": 0}[how]
            regs: dict[str, int] = {}
            if lines and how != "close":
                cs, eip = lines[-1].split()[0].split(":")
                regs = {"CS": int(cs, 16), "EIP": int(eip, 16)}
            self._pending = Stop(regs, ms=0.1, cycles=moved)
        return True, ["DEBUG: Starting log"]

    _do_logs = _do_logl = _do_logc = _do_log


def heavy_build(where: Path) -> Path:
    """A build that carries the CPU log, whatever is installed on the host running the suite."""
    binary = runnable(where)
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"\x00help\x00" + binaries.HEAVY_DEBUG_MARK + b"\x00")
    binary.chmod(0o755)
    return binary


def tracer(tmp_path: Path, logs: list[tuple[str | None, str | None]], *,
           captures_dir: Path | None = None, running: bool = False,
           binary: Path | None = None, logfile: Path | None = None, cycles: int = 0,
           protected_mode: bool = False, at: tuple[int, int] = (0x814, 0x106)) -> TraceMachine:
    """A live session over a `TraceMachine` stopped at `at`, installed as `start` leaves one."""
    cwd = cwd_of(tmp_path)
    machine = TraceMachine(logs=list(logs), logfile=logfile, stopped=not running, cycles=cycles)
    if protected_mode:
        protected(machine)
    machine.regs.update(CS=at[0], EIP=at[1])
    s = session_over(machine, cwd, logfile=logfile)
    s.launch = dataclasses.replace(
        s.launch, captures_dir=captures_dir,
        binary=str(binary if binary is not None else heavy_build(cwd.parent / "heavy-dosbox-x")))
    install()
    dstate.STATE.session = s
    dstate.STATE.remember_stop(s, {"cs": f"{at[0]:04X}", "eip": f"{at[1]:08X}",
                                   "mode": "Pr32" if protected_mode else "Real"}, {}, [],
                               {"attributed": False})
    return machine


def released(machine: Machine) -> list[str]:
    """The `LOG` family commands the session sent, each a release."""
    return [c.removeprefix("EXEC ") for c in machine.sent
            if c.startswith("EXEC ") and c.split()[1] in ds.LOG_WORDS]


def session_of(machine: Machine) -> ds.Session:
    return cast(ds.Session, dstate.STATE.session)


def test_a_stop_with_no_log_names_its_cause_and_keeps_the_log_open(tmp_path: Path) -> None:
    """With no file at the stop it was removed while open, so the log stays remembered."""
    tracer(tmp_path, [(None, "ran")])
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "m.trace")))
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert "something removed it while the log was open" in got["message"], got["message"]
    assert log_open(), got["message"]


def test_a_build_without_the_cpu_log_is_refused_before_anything_is_sent(
        tmp_path: Path) -> None:
    plain = runnable(tmp_path / "plain")
    plain.write_bytes(b"\x00help\x00LOG? no\x00")
    plain.chmod(0o755)
    machine = settle(tmp_path, binary=plain)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "h.trace")))
    refused_quietly(machine, got, "no_channel", "heavy_debug")


def test_a_build_without_runstate_is_refused_before_anything_is_sent(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    machine.commands = ()
    session_of(machine).commands = frozenset()
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "s.trace")))
    refused_quietly(machine, got, "no_channel", "RUNSTATE")


def test_a_session_build_that_is_gone_is_refused_before_anything_is_sent(
        tmp_path: Path) -> None:
    gone = tmp_path / "gone" / "dosbox-x"
    machine = settle(tmp_path, binary=gone)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "g.trace")))
    refused_quietly(machine, got, "host_failed", "not an executable file")


@pytest.mark.parametrize("shape", ["missing_directory", "free_name", "relative"])
def test_a_dangling_link_where_the_log_opens_is_refused_before_anything_is_sent(
        tmp_path: Path, shape: str) -> None:
    """Three links at the place the log opens, each somebody's file and refused like one:
    without the guard, into a missing directory the debugger is refused its file; to a free name
    elsewhere it writes the log there and `trace.path` comes back a link; a relative one,
    collected at another depth, breaks the reply."""
    machine = settle(tmp_path)
    cwd = cast(Path, machine.cwd)
    link = cwd / tracing.LOG_FILE
    far = {"missing_directory": tmp_path / "nowhere" / "LOG.TXT",
           "free_name": tmp_path / "elsewhere.txt", "relative": Path("rel.txt")}[shape]
    link.symlink_to(far)
    dest = tmp_path / "deeper" / "still" / "l.trace"
    dest.parent.mkdir(parents=True)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(dest)))
    refused_quietly(machine, got, "bad_argument", "already sitting at")
    landed = far if far.is_absolute() else cwd / far
    assert link.is_symlink() and not landed.exists() and not dest.exists()


@MODE_BITS
@pytest.mark.parametrize(("mode", "left_open"), [(0o555, False), (0o555, True), (0o666, False)])
def test_a_working_directory_the_emulator_cannot_write_is_refused_before_anything_is_sent(
        tmp_path: Path, mode: int, left_open: bool) -> None:
    """Neither the trace's command nor the close of a log an earlier trace left open may be sent
    there, and that log stays remembered: nothing here proved it closed. A directory that can be
    written and not searched takes no file either."""
    machine = settle(tmp_path)
    cwd = cast(Path, machine.cwd)
    dstate.STATE.log_open = left_open
    cwd.chmod(mode)
    try:
        got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "u.trace")))
    finally:
        cwd.chmod(0o755)
    refused_quietly(machine, got, "no_channel", f"{cwd} is not writable")
    assert log_open() is left_open


def djgpp_tracer(tmp_path: Path, *, refuse: bool = False) -> TraceMachine:
    """The dos-djgpp32 window over the double, answering the descriptor listings from their
    captures, or refusing them when `refuse` is set."""
    machine = tracer(tmp_path, [("dos-djgpp32-engine-cs-ip-200", "ran")], protected_mode=True,
                     at=(0xA7, 0x11734), logfile=tmp_path / "guest.log")
    listings = Listings(None, refuse=refuse)

    def listed(command: str) -> tuple[bool, list[str]]:
        return True, listings.listing(command.split()[0]).split("\n")
    for word in ("CPU", "GDT", "LDT"):
        machine.hooks[word] = listed
    return machine


def test_an_interrupt_that_found_no_stop_names_the_log_left_open(tmp_path: Path) -> None:
    """The bound's `BREAK` that never brought a stop is `not_settled`, and the debugger's log is
    still open: the refusal names its path and what the next trace does about it."""
    machine = tracer(tmp_path, [("probe-int-mid-cs-ip", None)])

    def unsettled(seconds: float | None = None) -> float:
        raise ds.Invalid("not_settled", "`RUNSTATE` did not say stopped")
    session_of(machine).break_in = unsettled  # type: ignore[method-assign]
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "u.trace"), seconds=0.3))
    assert got["code"] == "not_settled" and got["trace"]["closed"] is False, got
    assert "still open" in got["message"] and log_open(), got["message"]


def cwd_of(tmp_path: Path) -> Path:
    cwd = tmp_path / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd


def settle(tmp_path: Path, **kw: Any) -> TraceMachine:
    """`LOGC 11` at the probe's settle loop: sixteen instructions, the cycle count sixteen on."""
    return tracer(tmp_path, [("probe-settle-cs-ip-16", "ran")], **kw)


def no_log_left(cwd: Path) -> bool:
    return not any(p.exists() for p in tracing.log_places(cwd))


# ------------------------------------------------------------------------------- the parse

SHAPE_FILES = [(bench, shape) for bench in ("probe-settle", "dos-real16", "dos-djgpp32")
               for shape in tracing.SHAPES]
#: Where each bench's 64-instruction captures stopped, read off the pane after each (the
#: provenance's run): the last line of the log is that instruction, in the shape's spelling.
STOPPED_AT = {"probe-settle": {s: ("0814", "00000106") for s in tracing.SHAPES} | {
                  "short": ("0814", "0106")},
              "dos-real16": {s: ("15A3", "0000003C") for s in tracing.SHAPES} | {
                  "short": ("15A3", "003C")},
              "dos-djgpp32": {"normal": ("00A7", "0003D451"), "short": ("00A7", "60D71"),
                         "long": ("00A7", "001604C0"), "cs_ip": ("00A7", "00028DCF")}}


def _real_bp(ref: str) -> None:
    """A raw breakpoint declared at the real-mode stop the probe guest sits at."""
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", ref, cpu=grammar.REAL_MODE))


@pytest.mark.parametrize(("bench", "shape"), SHAPE_FILES)
def test_every_captured_shape_parses_whole_with_the_stop_as_its_last_line(
        bench: str, shape: str) -> None:
    got = tracing.parse(TRACE / f"{bench}-{shape.replace('_', '-')}-64.trace", shape)
    assert got.line_count == 65 and sum(got.executed.values()) == 64, got
    assert got.last is not None and got.last[:2] == STOPPED_AT[bench][shape], got.last
    assert tracing.count_lines(TRACE / f"{bench}-{shape.replace('_', '-')}-64.trace") == 65


def test_a_long_line_says_its_own_mode_and_the_others_do_not() -> None:
    real = tracing.parse(TRACE / "probe-settle-long-64.trace", "long")
    paged = tracing.parse(TRACE / "dos-djgpp32-long-64.trace", "long")
    other = tracing.parse(TRACE / "dos-djgpp32-normal-64.trace", "normal")
    assert {flat for _cs, _eip, flat in real.executed} == {True}
    assert {flat for _cs, _eip, flat in paged.executed} == {False}
    assert {flat for _cs, _eip, flat in other.executed} == {None}


@pytest.mark.parametrize("shape", list(tracing.SHAPES))
def test_a_line_another_shape_wrote_is_refused_naming_its_number(
        shape: str, tmp_path: Path) -> None:
    """Read in the wrong shape, a captured file refuses at its first line: the head or the tail
    does not match, and the refusal quotes it rather than reading a column."""
    other = {"normal": "short", "short": "long", "long": "normal", "cs_ip": "normal"}[shape]
    path = tmp_path / "x.trace"
    shutil.copyfile(TRACE / f"dos-djgpp32-{other.replace('_', '-')}-64.trace", path)
    with pytest.raises(ds.Invalid, match=r"line 1 of .* is not a `" + shape):
        tracing.parse(path, shape)


def test_a_line_cut_short_is_refused_where_it_is(tmp_path: Path) -> None:
    lines = (TRACE / "probe-settle-normal-64.trace").read_bytes().splitlines(keepends=True)
    path = tmp_path / "cut.trace"
    path.write_bytes(b"".join(lines[:10]) + lines[10][:40] + b"\n" + b"".join(lines[11:]))
    with pytest.raises(ds.Invalid, match="line 11 of") as got:
        tracing.parse(path, "normal")
    assert got.value.code == "unexpected_answer"


def test_the_counter_is_read_across_its_wrap() -> None:
    """`cc=` is painted as a 32-bit unsigned number: a run that crosses the wrap reads lower."""
    assert tracing.cycles_moved(tracing.CYCLES_WRAP - 5, 11) == 16
    assert tracing.cycles_moved(5, 21) == 16


def test_lines_are_counted_whole_a_last_one_unterminated_included(tmp_path: Path) -> None:
    cases = {b"": 0, b"a\nb": 2, b"a\n": 1, (b"x" * 99 + b"\n") * 11000: 11000}
    for i, (data, lines) in enumerate(cases.items()):
        path = tmp_path / f"{i}.trace"
        path.write_bytes(data)
        assert tracing.count_lines(path) == lines, (len(data), lines)


# ------------------------------------------------------------------------------- the run

def test_sixteen_instructions_ask_seventeen_lines_in_hex_and_come_back_elapsed(
        tmp_path: Path) -> None:
    machine = settle(tmp_path)
    dest = tmp_path / "a.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok", got
    assert released(machine) == ["LOGC 11"], "one command, the count one more than executed"
    assert got["verdict"] == "ELAPSED" and got["pc"].endswith(":00000106"), got
    assert {k: got["trace"][k] for k in ("path", "bytes", "shape", "instructions",
                                         "addresses")} == {
        "path": str(dest), "bytes": dest.stat().st_size, "shape": "cs_ip",
        "instructions": 16, "addresses": 1}, got["trace"]
    assert dest.read_bytes() == (TRACE / "probe-settle-cs-ip-16.trace").read_bytes()
    assert no_log_left(cast(Path, machine.cwd)), "the log stayed in the working directory"
    assert got["regs"] and "cause" in got and "stop_seq" in got and "e9" in got
    assert got["session"]["altered"] is False, "advancing is not writing"
    assert got["summary"].startswith("trace 16 cs_ip: ELAPSED, 16 executed at 1 address")


def test_a_mixed_case_dest_is_written_normalised_with_a_set_file_named_from_its_whole_name(
        tmp_path: Path) -> None:
    settle(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(out / "Run_1.LOG")))
    assert got["status"] == "ok", got
    assert (got["trace"]["path"], got["trace"]["set_path"]) == (
        str(out / "run-1.log"), str(out / "run-1-log-set.jsonl")), got["trace"]
    assert sorted(p.name for p in out.iterdir()) == ["run-1-log-set.jsonl", "run-1.log"]
    assert tracing.set_path(out / "run-1.trace") != tracing.set_path(out / "run-1.log")


def test_the_default_shape_is_the_familys_bare_command(tmp_path: Path) -> None:
    machine = tracer(tmp_path, [("probe-settle-normal-16", "ran")])
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "n.trace")))
    assert got["status"] == "ok" and got["trace"]["shape"] == "normal", got
    assert released(machine) == ["LOG 11"]


def test_a_dynamic_core_is_refused_by_its_counter_and_the_file_is_kept(tmp_path: Path) -> None:
    """The negative of the per-call proof: seventeen lines while the cycle count did not move."""
    tracer(tmp_path, [("probe-dynamic-cs-ip-16", "dynamic")])
    dest = tmp_path / "d.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert "moved by 0 while the log holds 16 entries" in got["message"], got["message"]
    assert "cpu core=normal" in got["message"], got["message"]
    assert got["trace"]["path"] == str(dest) and dest.exists(), got
    assert got["stop_seq"] and got["pc"].endswith(":00000106"), got


def test_a_placement_said_at_the_trace_stop_survives_the_counter_refusing_the_trace(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    said = {"placed": True, "path": "/x/APP.MAP", "load_segment": "025C", "base": "0x000025c0",
            "loaded": 3}
    monkeypatch.setattr(start_symbols, "place_if_due", lambda session: said)
    tracer(tmp_path, [("probe-dynamic-cs-ip-16", "dynamic")])
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "d.trace")))
    assert got["code"] == "no_channel" and got["symbols_placed"] == said, got


def cut(tmp_path: Path, close: str | None = "close") -> TraceMachine:
    """A breakpoint at the `dec bx` after the settle loop, and a trace asked past it."""
    machine = tracer(tmp_path, [("probe-cut-open", "ran"), (None, close)])
    _real_bp("0814:0108")
    machine.breakpoints.insert(0, "BP 0814:0108")
    return machine


def test_a_breakpoint_that_cuts_the_trace_is_other_stop_and_the_log_is_closed_first(
        tmp_path: Path) -> None:
    machine = cut(tmp_path)
    dest = tmp_path / "c.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok", got
    assert released(machine) == ["LOGC 186A1", "LOGC 0"], "the open log closed before it moved"
    assert got["verdict"] == "OTHER_STOP" and "breakpoint 0814:0108 " in got["cause"], got
    assert got["trace"]["instructions"] == 5506 and got["trace"]["addresses"] == 1, got["trace"]
    assert got["pc"].endswith(":00000108") and dest.exists() and no_log_left(
        cast(Path, machine.cwd))
    assert not log_open(), "a close that answered leaves no log to close"


def test_a_close_that_does_not_answer_names_the_moved_log_as_maybe_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The log moves before the close is sent, so the refusal names it at `dest`."""
    monkeypatch.setattr(tracing, "CLOSE_WAIT_S", 0.2)
    machine = cut(tmp_path, close=None)
    dest = tmp_path / "c.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert got["trace"] == {"path": str(dest), "closed": False}
    assert dest.exists() and no_log_left(cast(Path, machine.cwd))
    assert "`close` ends the emulator" in got["message"] and dstate.STATE.log_open is True


def test_a_cut_log_the_host_holds_while_open_is_closed_then_collected(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows will neither move nor delete a file the debugger holds open; a copy it allows.
    So the log is copied, closed (it was open, so the machine had not closed it) and removed."""
    machine = cut(tmp_path)
    cwd = cast(Path, machine.cwd)
    real_replace, real_unlink = Path.replace, Path.unlink

    def held(path: Path) -> bool:
        return path.parent == cwd and path.name.upper() == tracing.LOG_FILE \
            and "EXEC LOGC 0" not in machine.sent

    def replace(self: Path, target: Any) -> Path:
        if held(self):
            raise PermissionError(13, "The process cannot access the file")
        return real_replace(self, target)

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if held(self):
            raise PermissionError(13, "The process cannot access the file")
        real_unlink(self, missing_ok=missing_ok)
    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(Path, "unlink", unlink)
    dest = tmp_path / "w.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["trace"]["instructions"] == 5506 and dest.exists(), got["trace"]
    assert released(machine) == ["LOGC 186A1", "LOGC 0"] and no_log_left(cwd)
    assert not log_open()


def test_a_bound_that_runs_out_interrupts_the_trace_and_collects_what_ran(
        tmp_path: Path) -> None:
    """THE BOUND INTERRUPTS: the stop the count waits for never comes, so at the bound the
    machine is brought back with `BREAK` where it stands, and what the log holds up to there is
    collected as a stop that cut it would be (moved, closed, counted against the cycles): a
    TIMEOUT, the log closed and nothing left in the working directory."""
    machine = tracer(tmp_path, [("probe-int-mid-cs-ip", None), (None, "close")])
    machine.hooks["BREAK"] = None  # type: ignore[assignment]
    original = machine.request

    def at_the_break(command: str, *a: Any, **k: Any) -> tuple[bool, list[str]]:
        if command == "BREAK":
            machine.cycles += 6               # what ran before the interrupt
        return original(command, *a, **k)
    machine.request = at_the_break  # type: ignore[method-assign]
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "t.trace"), seconds=0.3))
    assert got["status"] == "ok" and got["verdict"] == "TIMEOUT", got
    assert "BREAK" in machine.sent and got["trace"]["instructions"] == 6, got
    assert released(machine) == ["LOGC 186A1", "LOGC 0"] and no_log_left(cast(Path, machine.cwd))
    assert not log_open()


def test_the_running_check_comes_before_the_leftover(tmp_path: Path) -> None:
    """After an expired bound the machine runs with the log open: a trace asked then is told the
    machine runs, not to move a file the debugger is still writing."""
    machine = settle(tmp_path, running=True)
    (cast(Path, machine.cwd) / tracing.LOG_FILE).write_bytes(b"0814:00000106\n")
    dstate.STATE.log_open = True
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "o.trace")))
    refused_quietly(machine, got, "not_stopped", "running")


def log_open() -> bool:
    """Read through a call, so a type checker does not carry an earlier assertion's value past
    the tool calls that change it."""
    return dstate.STATE.log_open


@pytest.mark.parametrize("command", ["LOGC 11", "LOG 186A1", "LOGL C9", "LOGS 0"])
def test_a_log_command_is_a_release_and_clears_the_stopped_flag(
        tmp_path: Path, command: str) -> None:
    """A command that lets the guest run clears the stopped flag, or the next contact reads a
    running machine as parked; a `LOG` the debugger refused released nothing."""
    machine = TraceMachine(logs=[(None, None)])
    s = session_over(machine, cwd_of(tmp_path))
    s.release(command)
    assert s.parked is False
    refused = TraceMachine(logs=[(None, "refused")])
    kept = session_over(refused, cwd_of(tmp_path))
    with pytest.raises(ds.Invalid, match="refused"):
        kept.release(command)
    assert kept.parked is True


def test_close_forgets_a_log_left_open() -> None:
    install()
    dstate.STATE.log_open = True
    assert cast(dict[str, Any], server.close())["closed"] is True
    assert not log_open()


# ------------------------------------------------------- stops the trace did not ask for

def cut_by(tmp_path: Path, scenario: str) -> TraceMachine:
    """A capture of the probe's DOS boot with `BPINT 21` armed: the log moved out, then
    `LOGC 0`, then the stop after the close."""
    return tracer(tmp_path, [(f"probe-{scenario}-cs-ip", "int"),
                             (None if scenario != "post" else "probe-post-close", "close")])


def test_an_interrupt_breakpoint_counts_its_int_without_running_it(tmp_path: Path) -> None:
    """The counter takes the INT and the machine stops before running it, so the cycle count
    moved one more than the six instructions that executed; the trace is whole."""
    machine = cut_by(tmp_path, "int-mid")
    dest = tmp_path / "i.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["trace"]["instructions"] == 6, got["trace"]
    assert tracing.AT_ITS_START not in got["trace"]["note"], got["trace"]
    assert got["pc"] == "0814:00000108" and got["cpu_mode"] == "real", got
    assert released(machine) == ["LOGC 186A1", "LOGC 0"] and no_log_left(cast(Path, machine.cwd))


def test_a_trace_started_on_an_interrupt_breakpoint_stops_there_again_and_says_so(
        tmp_path: Path) -> None:
    cut_by(tmp_path, "int-at")
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "a.trace")))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["trace"]["instructions"] == 0 and got["trace"]["addresses"] == 0, got["trace"]
    assert got["trace"]["note"].startswith(tracing.AT_ITS_START), got["trace"]
    assert "an interrupt breakpoint, which stops at its INT" in got["trace"]["note"], got["trace"]


def test_a_count_that_ran_out_is_held_exact(tmp_path: Path) -> None:
    """The INT allowance is for a cut run only: the same seven lines asked as six instructions
    ran out at their count, and a counter one past them is refused."""
    tracer(tmp_path, [("probe-int-mid-cs-ip", "int")])
    got = cast(dict[str, Any], server.trace(instructions=6, shape="cs_ip",
                                            dest=str(tmp_path / "e.trace")))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got


def test_a_log_the_bios_closed_before_the_stop_is_refused_and_kept(tmp_path: Path) -> None:
    """The power-on self test closes the log while the machine runs on: the close then writes a
    fresh empty file, which is how it shows, and that file is removed; the three lines are
    kept, moved before the close could write over them."""
    machine = cut_by(tmp_path, "post")
    dest = tmp_path / "p.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert "closed the debugger's log" in got["message"], got["message"]
    assert dest.read_bytes() == (TRACE / "probe-post-cs-ip.trace").read_bytes()
    assert no_log_left(cast(Path, machine.cwd)) and got["stop_seq"], got


def test_a_pending_retrace_is_left_by_a_count_and_taken_by_an_unexplained_stop(
        tmp_path: Path) -> None:
    settle(tmp_path / "a")
    dstate.STATE.retrace_pending = True
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "r1.trace")))
    assert got["status"] == "ok" and dstate.STATE.retrace_pending is True, got
    cut_by(tmp_path / "b", "int-mid")
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "r2.trace")))
    assert got["cause"].startswith("most likely the retrace stop"), got["cause"]
    assert not dstate.STATE.retrace_pending


def test_addresses_count_the_distinct_executed_places(tmp_path: Path) -> None:
    tracer(tmp_path, [("dos-djgpp32-engine-cs-ip-200", "ran")], protected_mode=True,
           at=(0xA7, 0x11734))
    got = cast(dict[str, Any], server.trace(instructions=200, shape="cs_ip",
                                            dest=str(tmp_path / "x.trace")))
    lines = (TRACE / "dos-djgpp32-engine-cs-ip-200.trace").read_bytes().splitlines()
    assert got["status"] == "ok" and got["trace"]["instructions"] == 200, got
    assert got["trace"]["addresses"] == len(set(lines[:-1])) > 1, got["trace"]


@pytest.mark.parametrize("shape", list(tracing.SHAPES))
def test_every_shape_types_its_own_word(shape: str, tmp_path: Path) -> None:
    machine = settle(tmp_path)
    server.trace(instructions=16, shape=shape, dest=str(tmp_path / "w.trace"))
    word = {"normal": "LOG", "short": "LOGS", "long": "LOGL", "cs_ip": "LOGC"}[shape]
    assert released(machine) == [f"{word} 11"]


def test_more_lines_than_asked_is_not_this_log(tmp_path: Path) -> None:
    tracer(tmp_path, [("probe-settle-cs-ip-64", "ran")])
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "m.trace")))
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert "65 lines for 17 asked" in got["message"] and log_open()


def test_an_empty_log_is_refused_and_kept(tmp_path: Path) -> None:
    tracer(tmp_path, [("probe-post-close", "ran"), (None, "close")])
    dest = tmp_path / "z.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert "holds no line" in got["message"] and dest.exists()


def test_a_read_the_host_refuses_is_named_not_raised(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(_path: Path) -> int:
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(tracing, "count_lines", denied)
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "d.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert got["trace"]["path"].endswith(tracing.LOG_FILE), got


def test_a_log_the_debugger_could_not_create_is_named_and_not_remembered_open(
        tmp_path: Path) -> None:
    """The working directory judged writable and the file refused all the same (it changed
    under the call): the debugger's own answer to the `LOG` says so, and nothing ran."""
    machine = tracer(tmp_path, [(None, "refused")])
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "n.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "could not create LOGCPU.TXT" in got["message"], got["message"]
    assert "Logfile couldn't be created." in got["message"], got["message"]
    assert not log_open() and released(machine) == ["LOGC 11"], machine.sent
    assert session_of(machine).parked is True, "a refused `LOG` released nothing"


# ------------------------------------------------------------- refusals that arm nothing

@pytest.mark.parametrize(("kw", "words"), [
    ({"instructions": 0}, "from 1 to"), ({"instructions": tracing.INSTRUCTIONS_MAX + 1}, "from 1"),
    ({"instructions": True}, "whole number"), ({"instructions": 16, "shape": "wide"}, "cs_ip"),
    ({"instructions": 16, "dest": "rel/x.trace"}, "relative"),
    ({"instructions": 16, "seconds": 0}, "not a bound"),
    ({"instructions": 16, "seconds": 601}, "not a bound")])
def test_a_wrong_argument_is_refused_before_the_session_is_asked(
        kw: dict[str, Any], words: str) -> None:
    got = cast(dict[str, Any], server.trace(**kw))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert words in got["message"] and not got["session"]["alive"], got


def test_the_description_states_the_bound_the_check_holds() -> None:
    assert f"(1 to {tracing.INSTRUCTIONS_MAX})" in str(server.trace.__doc__)


@pytest.mark.parametrize("where", ["docs/reference/advance.md", "REFERENCE.md"])
def test_the_texts_say_the_bound_interrupts_the_trace(where: str) -> None:
    """A trace whose stop never comes is interrupted at its bound, so the texts may not
    promise a count that runs on, nor a log left open for the next trace."""
    text = (Path(__file__).parents[1] / where).read_text()
    flat = " ".join(text.split())
    assert "interrupted where it stood" in flat
    for promise in ("runs to its count and stops there", "so the log runs on to its count",
                    "leaves a log running to its count", "no such close was seen"):
        assert promise not in flat, promise


def test_the_bound_itself_is_accepted() -> None:
    checks.check("trace", instructions=tracing.INSTRUCTIONS_MAX, seconds=600)


def refused_quietly(machine: Machine, got: dict[str, Any], code: str, words: str) -> None:
    assert got["status"] == "INVALID" and got["code"] == code, got
    assert words in got["message"], got["message"]
    assert set(machine.sent) <= {"EXEC RUNSTATE"}, "a refusal sent the debugger a command"


def test_a_dest_already_there_is_refused_and_kept(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    mine = tmp_path / "mine.trace"
    mine.write_bytes(b"the caller's")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(mine)))
    refused_quietly(machine, got, "bad_argument", "already exists")
    assert mine.read_bytes() == b"the caller's"


def test_a_dest_in_the_working_directory_is_refused(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(
        instructions=16, dest=str(cast(Path, machine.cwd) / "x.trace")))
    refused_quietly(machine, got, "bad_argument", "working directory")


def test_a_dest_whose_directory_is_missing_is_refused(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16,
                                            dest=str(tmp_path / "nowhere" / "x.trace")))
    refused_quietly(machine, got, "bad_argument", "not a directory")


def test_no_dest_and_no_captures_directory_is_refused_naming_both(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16))
    refused_quietly(machine, got, "bad_argument", "start(captures_dir=)")


def test_no_dest_takes_the_next_free_number_in_the_captures_directory(tmp_path: Path) -> None:
    """A dangling link is a taken name: a move onto it would write wherever it points."""
    caps = tmp_path / "caps"
    caps.mkdir()
    (caps / "trace-1.trace").write_bytes(b"an earlier one")
    (caps / "trace-2.trace").symlink_to(tmp_path / "nowhere")
    settle(tmp_path, captures_dir=caps)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["status"] == "ok" and got["trace"]["path"] == str(caps / "trace-3.trace"), got
    settle(tmp_path / "first", captures_dir=tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["trace"]["path"] == str(tmp_path / "empty" / "trace-1.trace"), got


def test_a_captures_directory_that_is_not_there_is_named(tmp_path: Path) -> None:
    machine = settle(tmp_path, captures_dir=tmp_path / "missing")
    got = cast(dict[str, Any], server.trace(instructions=16))
    refused_quietly(machine, got, "bad_argument", "is not there")


def test_a_dest_from_the_home_directory_is_written_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest="~/h.trace"))
    assert got["status"] == "ok" and got["trace"]["path"] == str(tmp_path / "h.trace"), got
    assert not (tmp_path / "~").exists()


def test_a_set_file_already_there_is_refused_and_the_counter_skips_one(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    (tmp_path / "s-trace-set.jsonl").write_text("the caller's")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "s.trace")))
    refused_quietly(machine, got, "bad_argument", "already exists")
    caps = tmp_path / "caps"
    caps.mkdir()
    (caps / "trace-1-trace-set.jsonl").write_text("an earlier set")
    settle(tmp_path / "again", captures_dir=caps)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["trace"]["path"] == str(caps / "trace-2.trace"), got


def test_the_log_is_looked_for_under_both_spellings(tmp_path: Path) -> None:
    assert [p.name for p in tracing.log_places(tmp_path)] == ["LOGCPU.TXT", "logcpu.txt"]


def test_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    machine = settle(tmp_path, running=True)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "r.trace")))
    refused_quietly(machine, got, "not_stopped", "running")


def test_a_hand_built_launch_s_bare_name_is_found_on_the_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `Launch` built without `start` carries the bare name; `trace` reads the build the PATH
    gives it, as the session itself was spawned."""
    heavy = heavy_build(tmp_path / "bin" / "dosbox-x")
    monkeypatch.setenv("PATH", str(heavy.parent))
    machine = settle(tmp_path, binary=Path("dosbox-x"))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "b.trace")))
    assert got["status"] == "ok", got
    assert session_of(machine).launch.binary == "dosbox-x"


def test_a_log_already_in_the_working_directory_is_refused_never_read_or_deleted(
        tmp_path: Path) -> None:
    machine = settle(tmp_path)
    theirs = cast(Path, machine.cwd) / tracing.LOG_FILE.lower()
    theirs.write_bytes(b"somebody's log")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "l.trace")))
    refused_quietly(machine, got, "bad_argument", "already sitting at")
    assert theirs.read_bytes() == b"somebody's log"


# ------------------------------------------------------------------- the build, the console

def test_heavy_debug_reads_the_help_line_off_the_binary(tmp_path: Path) -> None:
    with_log = tmp_path / "a"
    with_log.write_bytes(b"xx" + binaries.HEAVY_DEBUG_MARK + b"yy")
    without = tmp_path / "b"
    without.write_bytes(b"xx LOGS yy")
    assert binaries.heavy_debug(str(with_log)) is True
    assert binaries.heavy_debug(str(without)) is False


@pytest.mark.parametrize("command", ["LOG 10", "logs 10", "LOGL 1", "LOGC 0", " LOG"])
def test_debug_refuses_the_log_family_naming_trace(command: str) -> None:
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "`trace`" in got["message"], got["message"]


def test_perform_checks_a_trace_step_with_the_list_and_runs_one(tmp_path: Path) -> None:
    machine = settle(tmp_path)
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "trace", "instructions": 0}]))
    assert bad["status"] == "INVALID" and bad["errors"][0]["op"] == "trace", bad
    assert released(machine) == []
    dest = tmp_path / "p.trace"
    got = cast(dict[str, Any], server.perform(steps=[
        {"op": "trace", "instructions": 16, "shape": "cs_ip", "dest": str(dest)}]))
    assert got["status"] == "ok" and got["steps_completed"] == 1, got
    assert got["ran"][0]["reply"]["trace"]["instructions"] == 16 and dest.exists()


# ------------------------------------------------------------------------------ the join

#: Where the probe guest was loaded in every capture: its CS, as a real-mode base.
PROBE_BASE = 0x814 * 16
#: The probe's own arithmetic over 200 instructions from `start` on a tick whose last digit does
#: not carry: one `emit` of the 28-character tick string, five of `bump`, the rest in `start`.
PROBE_START_200 = {"start": 51, "emit": 144, "bump": 5}
#: The dos-djgpp32 client's code selector: its LDT descriptor's base is where `DJGPP32.SYM` is
#: placed.
DOS_DJGPP32_BASE = 0x400000


def load(table: str, base: int) -> None:
    """A flat table at `base`, as `symbols_load` installs one: no section bases."""
    dstate.STATE.section_bases.clear()
    dstate.STATE.install_table(sym.parse_nm(Path(table).read_text(encoding="ascii")))
    dstate.STATE.base.update(base=base)


def table_walk(linear: int) -> dict[str, Any] | None:
    """The nearest-symbol rule by `find_by_offset`'s walk of the table per address: the
    reference the bisection is held to."""
    found = sym.find_by_offset(dstate.STATE.table, linear - dstate.STATE.base["base"])
    if found is None:
        return None
    best, delta = found
    return {"query": f"0x{linear - dstate.STATE.base['base']:X}", **placement._placed(best),
            "delta": delta}


class Listings:
    """A session that answers the debugger's listings from captures: `GDT` and `LDT` read at
    the dos-djgpp32 window's stop, and the `CPU` listing of the same program in the same mode from
    the machine fixtures; with no logfile it has none to read."""

    def __init__(self, logfile: Path | None, cpu: str = "dos-djgpp32-cpu",
                 refuse: bool = False) -> None:
        self.launch = SimpleNamespace(logfile=logfile)
        self.asked: list[str] = []
        self.cpu = cpu
        self.refuse = refuse

    def listing(self, command: str) -> str:
        self.asked.append(command)
        if self.refuse:
            raise ds.Invalid("unexpected_answer", f"`{command}` brought no prompt back")
        return {"CPU": (MACHINE / f"{self.cpu}-log.txt").read_text(encoding="latin-1"),
                "GDT": cap("dos-djgpp32-gdt-listing"),
                "LDT": cap("dos-djgpp32-ldt-listing")}[command]


def stopped_in(mode: str) -> None:
    dstate.STATE.last_stop["where"] = {"cs": "00A7", "eip": "00000000", "mode": mode}


def per_routine(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {r["symbol"]: r["instructions"] for r in rows}


def test_the_probe_start_window_joins_to_its_three_routines(tmp_path: Path) -> None:
    """The known answer is the guest's own: 200 instructions from `start` split 51, 144, 5."""
    tracer(tmp_path, [("probe-start-normal-200", "ran")])
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    dest = tmp_path / "start.trace"
    got = cast(dict[str, Any], server.trace(instructions=200, dest=str(dest)))
    assert got["status"] == "ok", got
    found = got["trace"]
    assert per_routine(found["symbols"]) == PROBE_START_200, found["symbols"]
    assert [r["addr"] for r in found["symbols"]] == ["0x0000824b", "0x00008277", "0x00008281"]
    assert found["symbols"][0]["first"] == "0x0000824b", "the routine's first address is its own"
    assert found["unplaced"] == 0 and found["symbols_total"] == 3, found
    assert found["truncated"] is False and "note" not in found, found
    rows = [json.loads(x) for x in Path(found["set_path"]).read_text().splitlines()]
    assert found["set_path"] == str(tmp_path / "start-trace-set.jsonl")
    assert len(rows) == found["addresses"]
    assert sum(r["count"] for r in rows) == 200
    assert [r["addr"] for r in rows] == sorted(r["addr"] for r in rows)
    assert all(re.fullmatch(r"0x[0-9a-f]{8}", r["addr"]) for r in rows), rows[:2]
    assert {r["symbol"] for r in rows} == set(PROBE_START_200)


def test_a_long_line_is_placed_by_its_own_mode_whatever_the_window_ends_say() -> None:
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Pr32")
    notes: list[str] = []
    got = tracing.join(cast(ds.Session, Listings(None)),
                       tracing.parse(TRACE / "probe-start-long-200.trace", "long"), False, notes)
    assert per_routine(got.symbols) == PROBE_START_200 and notes == [], (got.symbols, notes)


def test_without_a_logfile_the_protected_lines_are_placed_off_the_listings() -> None:
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Pr32")
    notes: list[str] = []
    tracing.join(cast(ds.Session, Listings(None)),
                 tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), True, notes)
    assert not any("logfile" in n for n in notes), notes


def test_a_cs_that_names_no_code_descriptor_of_its_privilege_gets_no_linear() -> None:
    """The probe's real-mode segment read as a selector against dos-djgpp32's tables: no LDT row
    0814 qualifies, so no line is given an address it might not have."""
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Pr32")
    notes: list[str] = []
    session = Listings(Path("guest.log"))
    got = tracing.join(cast(ds.Session, session),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), False,
                       notes)
    assert session.asked == ["CPU", "GDT", "LDT"], session.asked
    assert got.symbols == [] and all("addr" not in r for r in got.rows)
    assert any("no present code descriptor" in n for n in notes), notes


def test_the_dos_djgpp32_window_is_placed_through_the_ldt_base_not_the_raw_offset() -> None:
    load(str(TRACE / "dos-djgpp32-engine.sym"), DOS_DJGPP32_BASE)
    stopped_in("Pr32")
    notes: list[str] = []
    parsed = tracing.parse(TRACE / "dos-djgpp32-engine-cs-ip-200.trace", "cs_ip")
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, False, notes)
    engine = next(r for r in got.symbols if r["symbol"] == "_engine_pos")
    assert engine["first"] == engine["addr"] == f"{DOS_DJGPP32_BASE + 0x5E9C0:#010x}", engine
    for row in got.rows:
        linear = int(row["addr"], 16)
        assert linear == DOS_DJGPP32_BASE + int(row["seg_off"].split(":")[1], 16)
        expected = table_walk(linear)
        span = placement.symbol_span()
        if span is not None and span[0] <= linear <= span[1] and expected is not None:
            assert (row["symbol"], row["delta"]) == (expected["name"], expected["delta"])
        else:
            assert "symbol" not in row, row
    assert sum(r["instructions"] for r in got.symbols) + sum(
        r["count"] for r in got.rows if "symbol" not in r) == 200


def test_no_table_loaded_names_no_routine_and_says_so() -> None:
    dstate.STATE.forget_symbols()
    dstate.STATE.section_bases.clear()
    stopped_in("Real")
    notes: list[str] = []
    got = tracing.join(cast(ds.Session, Listings(None)),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), True,
                       notes)
    assert got.symbols == [] and all("symbol" not in r and "addr" in r for r in got.rows)
    assert any("no symbol table" in n for n in notes), notes


def test_the_reply_shows_sixty_four_routines_and_counts_the_rest(tmp_path: Path) -> None:
    """A table with a symbol at every address the dos-djgpp32 window executed: one routine each,
    the first sixty-four in the reply and every address in the set file."""
    djgpp_tracer(tmp_path)
    lines = (TRACE / "dos-djgpp32-engine-cs-ip-200.trace").read_text().splitlines()
    offsets = sorted({int(x.split(":")[1], 16) for x in lines[:-1]})
    dstate.STATE.section_bases.clear()
    dstate.STATE.install_table([sym.Symbol(f"_at_{o:x}", o) for o in offsets])
    dstate.STATE.base.update(base=DOS_DJGPP32_BASE)
    got = cast(dict[str, Any], server.trace(instructions=200, shape="cs_ip",
                                            dest=str(tmp_path / "t.trace")))
    found = got["trace"]
    assert got["status"] == "ok" and found["symbols_total"] == len(offsets), got
    assert len(found["symbols"]) == tracing.SYMBOLS_SHOWN < len(offsets), found["symbols_total"]
    assert found["truncated"] is True and found["unplaced"] == 0, found
    assert len(Path(found["set_path"]).read_text().splitlines()) == len(offsets)


def test_the_bisection_answers_what_the_table_walk_answers(tmp_path: Path) -> None:
    """Every address of the captured windows and every byte across the probe's table, against
    the rule `symbols_find` states; a tie answers the first symbol in the table, and a table
    replaced in place is not answered from the one before."""
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    for linear in range(PROBE_BASE + 0xF0, PROBE_BASE + 0x160):
        assert placement.nearest_symbol(linear) == table_walk(linear), hex(linear)
    load(str(TRACE / "dos-djgpp32-engine.sym"), DOS_DJGPP32_BASE)
    for line in (TRACE / "dos-djgpp32-engine-cs-ip-200.trace").read_text().splitlines():
        linear = DOS_DJGPP32_BASE + int(line.split(":")[1], 16)
        assert placement.nearest_symbol(linear) == table_walk(linear), line
    tie = tmp_path / "tie.sym"
    tie.write_text("0000010b T start\n0000010b T alias\n00000137 T emit\n")
    load(str(tie), PROBE_BASE)
    tied, walked = placement.nearest_symbol(PROBE_BASE + 0x110), table_walk(PROBE_BASE + 0x110)
    assert tied is not None and walked is not None and tied["name"] == "start" == walked["name"]
    tie.write_text("0000010b T other\n0000010b T alias\n00000137 T emit\n")
    load(str(tie), PROBE_BASE)
    replaced = placement.nearest_symbol(PROBE_BASE + 0x110)
    assert replaced is not None and replaced["name"] == "other"


def test_a_selector_qualifies_only_as_present_code_of_its_own_privilege() -> None:
    """dos-djgpp32's LDT at the window's stop: 00A7 is code at privilege 3, asked at 3; 00A4 is the
    same descriptor asked at privilege 0; 00AF is the client's data segment at 3. Only the first
    is an address."""
    load(str(TRACE / "dos-djgpp32-engine.sym"), DOS_DJGPP32_BASE)
    stopped_in("Pr32")
    parsed = tracing.Parsed(executed=Counter({("00A7", "0005E9C0", None): 1,
                                              ("00A4", "0005E9C0", None): 1,
                                              ("00AF", "0005E9C0", None): 1}))
    notes: list[str] = []
    session = Listings(Path("guest.log"))
    got = tracing.join(cast(ds.Session, session), parsed, False, notes)
    placed = {r["seg_off"]: r.get("addr") for r in got.rows}
    assert placed == {"00A7:0005E9C0": f"{DOS_DJGPP32_BASE + 0x5E9C0:#010x}", "00A4:0005E9C0": None,
                      "00AF:0005E9C0": None}, placed
    assert session.asked == ["CPU", "GDT", "LDT"], "one read of the tables per window"
    assert any(tracing.NO_LINEAR in n for n in notes), notes


def test_past_the_highest_symbol_nothing_is_named(tmp_path: Path) -> None:
    """Without the probe's data rows the table ends at `bump`'s own address: the four
    instructions of its body above it are past what the table describes, so they stay
    unplaced rather than credited to the last routine."""
    code_only = tmp_path / "code.sym"
    code_only.write_text("".join(x + "\n" for x in (GUEST / "probe.sym").read_text().splitlines()
                                 if " T " in x))
    load(str(code_only), PROBE_BASE)
    stopped_in("Real")
    got = tracing.join(cast(ds.Session, Listings(None)),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), True, [])
    assert per_routine(got.symbols) == {"start": 51, "emit": 144, "bump": 1}, got.symbols
    assert sum(r["count"] for r in got.rows if "symbol" not in r) == 4


def test_a_routine_spans_from_its_lowest_to_its_highest_address_whatever_ran_first() -> None:
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Real")
    parsed = tracing.Parsed(executed=Counter({("0814", "00000120", None): 2,
                                              ("0814", "0000010B", None): 1}))
    got = tracing.join(cast(ds.Session, Listings(None)), parsed, True, [])
    assert got.symbols == [{"symbol": "start", "addr": "0x0000824b", "addresses": 2,
                            "instructions": 3, "first": "0x0000824b", "last": "0x00008260"}]


def test_a_gdt_selector_is_placed_through_the_gdt_at_its_own_privilege() -> None:
    """The DPMI host's code selectors in dos-djgpp32's GDT: 0018 at privilege 0, and 002B, which
    names 0028 asked at privilege 3; 0008 is a data descriptor."""
    stopped_in("Pr32")
    parsed = tracing.Parsed(executed=Counter({("0018", "00000010", None): 1,
                                              ("002B", "00000020", None): 1,
                                              ("0008", "00000030", None): 1}))
    dstate.STATE.forget_symbols()
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, False, [])
    placed = {r["seg_off"]: r.get("addr") for r in got.rows}
    assert placed == {"0018:00000010": "0x000cc5c0", "002B:00000020": "0x000cc5d0",
                      "0008:00000030": None}, placed


def test_a_window_armed_protected_and_stopped_real_reads_no_selector() -> None:
    """Its ends disagree, so its lines are read through selectors, and a real-mode stop has no
    descriptor tables: nothing is placed, and nothing raises."""
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Real")
    notes: list[str] = []
    session = Listings(Path("guest.log"), cpu="probe-booted-cpu")
    got = tracing.join(cast(ds.Session, session),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), False,
                       notes)
    assert session.asked == ["CPU"] and all("addr" not in r for r in got.rows), got.rows[:2]
    assert any(tracing.NO_LINEAR in n for n in notes), notes


def test_tables_that_cannot_be_read_leave_a_note_and_the_trace_whole(tmp_path: Path) -> None:
    """A descriptor listing that fails after the log has moved costs the join, never the
    proved trace or where its file went."""
    djgpp_tracer(tmp_path, refuse=True)
    dest = tmp_path / "r.trace"
    got = cast(dict[str, Any], server.trace(instructions=200, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["trace"]["path"] == str(dest), got
    assert "could not be read" in got["trace"]["note"], got["trace"]["note"]


def test_a_set_file_the_host_refuses_part_way_is_removed_and_said(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = iter(range(1000))

    def full(_row: object) -> str:
        if next(rows) == 1:
            raise OSError(28, "No space left on device")
        return "{}"
    # The trace's own writer alone: the rest of the process (the session block's cost) keeps json.
    monkeypatch.setattr(tracing, "json", SimpleNamespace(dumps=full))
    tracer(tmp_path, [("probe-start-normal-200", "ran")])
    dest = tmp_path / "f.trace"
    got = cast(dict[str, Any], server.trace(instructions=200, dest=str(dest)))
    assert got["status"] == "ok" and got["trace"]["set_path"]["available"] is False, got["trace"]
    assert not (tmp_path / "f-trace-set.jsonl").exists() and dest.exists()
    assert "could not be written" in got["trace"]["note"], got["trace"]["note"]


def test_a_linear_address_wraps_at_thirty_two_bits() -> None:
    stopped_in("Pr32")
    dstate.STATE.forget_symbols()
    parsed = tracing.Parsed(executed=Counter({("00A7", "FFC00010", None): 1}))
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, False, [])
    assert got.rows[0]["addr"] == "0x00000010", got.rows


def test_two_routines_of_one_name_are_two_rows() -> None:
    dstate.STATE.section_bases.clear()
    dstate.STATE.install_table([sym.Symbol("_dup", 0x10B), sym.Symbol("_mid", 0x120),
                                sym.Symbol("_dup", 0x137), sym.Symbol("_end", 0x200)])
    dstate.STATE.base.update(base=PROBE_BASE)
    stopped_in("Real")
    parsed = tracing.Parsed(executed=Counter({("0814", "0000010B", None): 1,
                                              ("0814", "00000137", None): 2}))
    got = tracing.join(cast(ds.Session, Listings(None)), parsed, True, [])
    assert [(r["symbol"], r["instructions"]) for r in got.symbols] == [("_dup", 1), ("_dup", 2)]


def test_set_rows_without_a_linear_come_last() -> None:
    rows = [{"seg_off": "00A7:00000002"}, {"seg_off": "0814:00000001", "addr": "0x00008141"},
            {"seg_off": "00A7:00000001"}, {"seg_off": "0814:00000000", "addr": "0x00008140"}]
    assert [r["seg_off"] for r in sorted(rows, key=tracing._set_order)] == [
        "0814:00000000", "0814:00000001", "00A7:00000001", "00A7:00000002"]


def test_a_sectioned_table_is_answered_as_the_walk_answers_it() -> None:
    """Two sections with overlapping offsets, each at its own base: the bisection answers every
    address the way `find_by_offset` does for that address's section."""
    dstate.STATE.install_table([
        sym.Symbol("_a1", 0x10, section=1), sym.Symbol("_b1", 0x40, section=1),
        sym.Symbol("_a2", 0x08, section=2), sym.Symbol("_b2", 0x40, section=2)])
    dstate.STATE.section_bases.clear()
    dstate.STATE.section_bases.update({1: 0x10000, 2: 0x20000})
    for linear in list(range(0x10000, 0x10060)) + list(range(0x20000, 0x20060)) + [0x500]:
        section = 1 if linear < 0x20000 else 2
        found = sym.find_by_offset(dstate.STATE.table, linear - dstate.STATE.section_bases.get(
            section, 0), section) if linear >= 0x10000 else None
        got = placement.nearest_symbol(linear)
        if found is None:
            assert got is None, hex(linear)
        else:
            assert got is not None and (got["name"], got["delta"]) == (found[0].name, found[1])
    dstate.STATE.section_bases.clear()


# --------------------------------------------------------- the open log, remembered until closed

def test_a_cut_run_whose_read_fails_remembers_the_log_it_left_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A breakpoint cut the log, so the debugger still holds it open when the host refuses the
    read: the next trace has to close it before opening its own."""
    def denied(_path: Path) -> int:
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(tracing, "count_lines", denied)
    machine = cut(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert released(machine) == ["LOGC 186A1"] and log_open()


def test_a_cut_run_whose_move_fails_remembers_the_log_it_left_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(source: Path, dest: Path, what: str, release: Any = None) -> Path:
        raise ds.Invalid("host_failed", f"the {what} at {source} could not be moved to {dest}")
    monkeypatch.setattr(dcollect, "collect", refused)
    machine = cut(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert released(machine) == ["LOGC 186A1"] and log_open()


def test_a_wait_that_breaks_off_remembers_the_log_it_released(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The log opens with the release: a wait that leaves by an exception (a client that went
    away, a read that failed) leaves it open, and the next trace has to know."""
    monkeypatch.setattr(run_state, "PROGRESS_EVERY_S", 0.0)
    machine = tracer(tmp_path, [("probe-settle-cs-ip-16", None)])

    def gone(*_args: object) -> None:
        raise RuntimeError("the client went away")
    with pytest.raises(RuntimeError):
        tracing.trace(session_of(machine), 16, "cs_ip", tmp_path / "g.trace", 5.0, gone)
    assert released(machine) == ["LOGC 11"] and log_open()


def test_a_count_that_ran_out_closed_its_own_log(tmp_path: Path) -> None:
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "s.trace")))
    assert got["status"] == "ok" and not log_open(), got


def test_a_log_left_open_is_closed_and_its_empty_file_removed_before_anything_else(
        tmp_path: Path) -> None:
    """A refusal that comes after the close of a log an expired trace left leaves no file of this
    call's behind, or the next trace would be refused over it."""
    machine = tracer(tmp_path, [("probe-post-close", "close")])
    session = session_of(machine)

    def cut_survey() -> Any:
        raise ds.Invalid("unexpected_answer", "the survey came back cut")
    session.where_and_registers = cut_survey  # type: ignore[method-assign]
    dstate.STATE.log_open = True
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "o.trace")))
    assert got["code"] == "unexpected_answer" and released(machine) == ["LOGC 0"], got
    assert no_log_left(cast(Path, machine.cwd)) and not log_open()


# --------------------------------------------------------------------- the bound expiring


def test_a_log_the_machine_closed_before_the_bound_is_not_what_ran(tmp_path: Path) -> None:
    """From the reset park the BIOS closes the debugger's log before its count: the bound
    interrupts the run, and the collect finds the log already closed, so its lines are not what
    ran and the trace is refused, with the stop it ended at."""
    machine = tracer(tmp_path, [("probe-post-cs-ip", None), ("probe-post-close", "close")])
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "p.trace"), seconds=0.3))
    assert got["code"] == "readback_refused" and "BREAK" in machine.sent, got
    assert "are not what ran" in got["message"] and "stop_seq" in got, got


class ReadSizes(type(Path())):  # type: ignore[misc]
    """A path whose file says how much each read asked for."""

    asked: list[int] = []

    def open(self, *args: Any, **kwargs: Any) -> Any:
        f = super().open(*args, **kwargs)
        real = f.read

        def read(n: int = -1) -> bytes:
            ReadSizes.asked.append(n)
            return cast(bytes, real(n))
        f.read = read
        return f


# ------------------------------------------------------------------- the reply's other keys

def test_a_set_file_that_appeared_during_the_wait_is_left_alone(tmp_path: Path) -> None:
    """Judged absent before the run, then made by somebody else while it ran."""
    path = tmp_path / "a-trace-set.jsonl"
    path.write_text("theirs\n")
    notes: list[str] = []
    assert tracing._write_set(path, [{"addr": "0814:00000106", "count": 1}], notes) is None
    assert path.read_text() == "theirs\n" and "could not be written" in notes[0], notes


def test_the_e9_block_names_the_tool_that_reads_the_lines_not_an_argument_trace_lacks(
        tmp_path: Path) -> None:
    logfile = tmp_path / "guest.log"
    logfile.write_text("")
    machine = tracer(tmp_path, [("probe-settle-cs-ip-16", "ran")], logfile=logfile)
    machine.appends = "probe-count-logfile"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "e.trace")))
    assert got["status"] == "ok" and got["e9"] == {"lines_total": 0, "truncated": False,
                                                    "lines": [], "mark": 0}, got["e9"]


def test_with_the_captures_directory_the_working_directory_the_default_lands_there(
        tmp_path: Path) -> None:
    machine = settle(tmp_path, captures_dir=cwd_of(tmp_path))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["status"] == "ok", got
    assert got["trace"]["path"] == str(cast(Path, machine.cwd) / "trace-1.trace"), got["trace"]
    assert no_log_left(cast(Path, machine.cwd))


def test_a_trace_started_on_a_code_breakpoint_stops_there_again_and_says_so(
        tmp_path: Path) -> None:
    """The log is the live run's (provenance), at 0814:0108 with a breakpoint there."""
    machine = tracer(tmp_path, [("probe-on-bp-cs-ip", "ran"), (None, "close")], at=(0x814, 0x108))
    _real_bp("0814:0108")
    machine.breakpoints.insert(0, "BP 0814:0108")
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "b.trace")))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert "breakpoint 0814:0108 " in got["cause"] and got["trace"]["instructions"] == 0, got
    assert "code breakpoint" in got["trace"]["note"], got["trace"]["note"]


def test_unplaced_counts_the_executed_addresses_no_symbol_places(tmp_path: Path) -> None:
    """Without the probe's data rows the table ends at `bump`'s own address, so the addresses of
    its body above it are executed and unplaced, beside the placed ones."""
    code_only = tmp_path / "code.sym"
    code_only.write_text("".join(x + "\n" for x in (GUEST / "probe.sym").read_text().splitlines()
                                 if " T " in x))
    tracer(tmp_path, [("probe-start-normal-200", "ran")])
    load(str(code_only), PROBE_BASE)
    got = cast(dict[str, Any], server.trace(instructions=200, dest=str(tmp_path / "u.trace")))
    rows = [json.loads(x) for x in Path(got["trace"]["set_path"]).read_text().splitlines()]
    unplaced = sum(1 for r in rows if "symbol" not in r)
    assert 0 < got["trace"]["unplaced"] == unplaced < got["trace"]["addresses"], got["trace"]


def test_no_table_leaves_every_executed_address_unplaced(tmp_path: Path) -> None:
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "u.trace")))
    assert got["trace"]["addresses"] == got["trace"]["unplaced"] == 1, got["trace"]


# --------------------------------------------------------------------- the counter's proof


def test_the_counter_is_read_across_its_wrap_by_the_call(tmp_path: Path) -> None:
    settle(tmp_path, cycles=tracing.CYCLES_WRAP - 5)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "w.trace")))
    assert got["status"] == "ok" and got["trace"]["instructions"] == 16, got


def test_a_cut_run_that_counted_two_more_is_refused(tmp_path: Path) -> None:
    """The allowance is one, the INT an interrupt breakpoint counted and did not run: two more
    is a counter that does not follow the log."""
    executed = tracing.count_lines(TRACE / "probe-cut-open.trace") - 1
    machine = tracer(tmp_path, [("probe-cut-open", "two"), (None, "close")])
    _real_bp("0814:0108")
    machine.breakpoints.insert(0, "BP 0814:0108")
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert f"moved by {executed + 2} while the log holds {executed} entries" in got["message"]
    assert released(machine) == ["LOGC 186A1", "LOGC 0"]


# ------------------------------------------------------------------ the modes of the join

def test_a_long_line_in_virtual_8086_mode_is_flat_under_protection(tmp_path: Path) -> None:
    """CR0's protection bit stays set in virtual-8086 mode, so `VM:1` alone makes the line's
    address its paragraph: a captured protected line with that one flag turned on, since no
    capture ran in that mode."""
    lines = (TRACE / "dos-djgpp32-long-64.trace").read_bytes().splitlines(keepends=True)
    v86, n = re.subn(rb" VM:0 ", b" VM:1 ", lines[0])
    assert n == 1
    path = tmp_path / "v.trace"
    path.write_bytes(v86 + lines[1])
    got = tracing.parse(path, "long")
    assert [flat for _cs, _eip, flat in got.executed] == [True], got.executed


def test_a_window_mixing_flat_and_protected_lines_reads_the_selectors_for_the_protected() -> None:
    load(str(TRACE / "dos-djgpp32-engine.sym"), DOS_DJGPP32_BASE)
    stopped_in("Pr32")
    parsed = tracing.Parsed(executed=Counter({("0814", "0000010B", True): 1,
                                              ("00A7", "0005E9C0", False): 1}))
    notes: list[str] = []
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, False, notes)
    placed = {r["seg_off"]: r.get("addr") for r in got.rows}
    assert placed == {"0814:0000010B": "0x0000824b",
                      "00A7:0005E9C0": f"{DOS_DJGPP32_BASE + 0x5E9C0:#010x}"}, placed
    assert not any(tracing.NO_LINEAR in n for n in notes), "a flat line was looked up as a selector"


def test_a_long_line_that_says_protected_wins_over_real_window_ends() -> None:
    load(str(TRACE / "dos-djgpp32-engine.sym"), DOS_DJGPP32_BASE)
    stopped_in("Real")
    parsed = tracing.Parsed(executed=Counter({("00A7", "0005E9C0", False): 1}))
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, True, [])
    assert got.rows[0].get("addr") == f"{DOS_DJGPP32_BASE + 0x5E9C0:#010x}", got.rows


def patch_ldt(monkeypatch: pytest.MonkeyPatch, **changed: Any) -> None:
    """dos-djgpp32's captured LDT, read as `machine.read` would, with the client's code descriptor
    (00A4) changed in the named fields: no capture holds a conforming or a not-present code
    segment."""
    rows = machine.parse_descriptors(cap("dos-djgpp32-ldt-listing"), "LDT")
    code = next(r for r in rows if r["selector"] == "00A4")
    code.update(changed)
    monkeypatch.setattr(machine, "read", lambda _session, _what: SimpleNamespace(
        found={"gdt": [], "ldt": rows}))


def linear_of_00a7() -> str | None:
    """The client's code selector at privilege 3, joined at a protected stop with no table."""
    stopped_in("Pr32")
    dstate.STATE.forget_symbols()
    parsed = tracing.Parsed(executed=Counter({("00A7", "0005E9C0", None): 1}))
    got = tracing.join(cast(ds.Session, Listings(Path("guest.log"))), parsed, False, [])
    return cast("str | None", got.rows[0].get("addr"))


@pytest.mark.parametrize("code_type", ["18", "19", "1A", "1C", "1F"])
def test_every_code_type_at_its_own_privilege_qualifies(
        code_type: str, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_ldt(monkeypatch, type=code_type)
    assert linear_of_00a7() == f"{DOS_DJGPP32_BASE + 0x5E9C0:#010x}"


@pytest.mark.parametrize("data_type", ["10", "17"])
def test_a_data_type_does_not_qualify(data_type: str, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_ldt(monkeypatch, type=data_type)
    assert linear_of_00a7() is None


def test_a_code_segment_not_present_does_not_qualify(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_ldt(monkeypatch, p=0)
    assert linear_of_00a7() is None


def test_a_binary_rebuilt_at_the_same_size_is_read_again(tmp_path: Path) -> None:
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"xx" + binaries.HEAVY_DEBUG_MARK + b"yy")
    assert binaries.heavy_debug(str(binary)) is True
    first = binary.stat().st_mtime_ns
    binary.write_bytes(b"xx" + b"-" * len(binaries.HEAVY_DEBUG_MARK) + b"yy")
    os.utime(binary, ns=(first, first + 1_000_000_000))
    assert binaries.heavy_debug(str(binary)) is False


def test_a_trace_cut_as_the_bound_expires_is_another_stop_not_a_timeout(tmp_path: Path) -> None:
    """The race the bound can lose: a stop cuts the count after the wait gave up and before the
    interrupt looks, so nothing is interrupted and the run ended at another's stop."""
    machine = cut(tmp_path)
    session = session_of(machine)
    real = session.log_cpu

    def gave_up(word: str, count: int, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        expired, saw = real(word, count, began, deadline, progress)
        return (True if count else expired), saw     # the close (`LOGC 0`) answers as it does
    session.log_cpu = gave_up  # type: ignore[method-assign]
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "t.trace")))
    assert "BREAK" not in machine.sent and got["verdict"] == "OTHER_STOP", (got, machine.sent)
