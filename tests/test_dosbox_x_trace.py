"""`trace` against a debugger double that replays what a real one printed and wrote.

Every survey, every `LOG` command's delta and every log file the double hands back is a file
under `fixtures/trace/`, captured from live sessions (its PROVENANCE says which): the counter
`cc=`, the prompt a stop announces itself with and the lines of the log are the debugger's,
not an opinion of this file.
"""
from __future__ import annotations

import inspect
import json
import os
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_dosbox_x_debug import Debugger
from test_dosbox_x_run_for import live
from test_dosbox_x_server import SELINFO_SCREEN, clean_session, install  # noqa: F401

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_checks as checks
import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_machine as machine
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as sym
import dosbox_trace as tracing
import dosbox_x_server as server

TRACE = Path(__file__).parent / "fixtures" / "trace"
GUEST = Path(__file__).parent / "guest"
MACHINE = Path(__file__).parent / "fixtures" / "machine"


def cap(name: str) -> str:
    return (TRACE / f"{name}.txt").read_text()


class Tracer(Debugger):
    """The debugger's side of a `LOG` command: each one typed takes the next scripted answer,
    the captured log it leaves in the working directory (None: the file is left as it is) and
    the captured delta the terminal offers next (None: the stop never comes). The surveys come
    off `panes` like every nudge. `running` is a machine the console does not answer."""

    def __init__(self, panes: list[str], cwd: Path,
                 logs: list[tuple[str | None, str | None]], *,
                 captures_dir: Path | None = None, running: bool = False,
                 binary: Path | None = None) -> None:
        super().__init__(panes)
        self.logs = list(logs)
        self.running = running
        # THE SESSION'S OWN BUILD is what `trace` reads, so a case's session carries one that
        # has the CPU log, whatever is installed on the host running the suite.
        if binary is None:
            binary = cwd.parent / "heavy-dosbox-x"
            binary.write_bytes(b"\x00help\x00" + binaries.HEAVY_DEBUG_MARK + b"\x00")
            binary.chmod(0o755)
        self.launch = SimpleNamespace(logfile=None, watched=False, input_port=None, cwd=cwd,
                                      captures_dir=captures_dir, binary=str(binary))

    def _write(self, data: bytes) -> None:
        super()._write(data)
        if ds.LOG_COMMAND.fullmatch(data) and self.logs:
            log, delta = self.logs.pop(0)
            if log is not None:
                shutil.copyfile(TRACE / f"{log}.trace", self.launch.cwd / tracing.LOG_FILE)
            if delta is not None:
                self.reads.append(cap(delta))

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return not self.running and self._at_debugger

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        return ds.Session.log_cpu(cast(ds.Session, self), word, count, began, deadline, progress)

    def e9_mark(self) -> int:
        return ds.Session.e9_mark(cast(ds.Session, self))

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        return ds.Session._e9_since(cast(ds.Session, self), offset, channel)


def cwd_of(tmp_path: Path) -> Path:
    cwd = tmp_path / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    return cwd


def settle(tmp_path: Path, **kw: Any) -> Tracer:
    """`LOGC 11` at the probe's settle loop: sixteen instructions, `cc=` sixteen on."""
    return live(Tracer([cap("probe-settle-survey-before"), cap("probe-settle-survey-after")],
                       cwd_of(tmp_path),
                       [("probe-settle-cs_ip-16", "probe-settle-cs_ip-16-delta")], **kw))


def no_log_left(cwd: Path) -> bool:
    return not any(p.exists() for p in tracing.log_places(cwd))


# ------------------------------------------------------------------------------- the parse

SHAPE_FILES = [(bench, shape) for bench in ("probe-settle", "dos-real16", "dos-djgpp32")
               for shape in tracing.SHAPES]
#: Where each bench's 64-instruction captures stopped, read off the pane after each (the
#: PROVENANCE's run): the last line of the log is that instruction, in the shape's spelling.
STOPPED_AT = {"probe-settle": {s: ("0814", "00000106") for s in tracing.SHAPES} | {
                  "short": ("0814", "0106")},
              "dos-real16": {s: ("15A3", "0000003C") for s in tracing.SHAPES} | {
                  "short": ("15A3", "003C")},
              "dos-djgpp32": {"normal": ("00A7", "0003D451"), "short": ("00A7", "60D71"),
                         "long": ("00A7", "001604C0"), "cs_ip": ("00A7", "00028DCF")}}


@pytest.mark.parametrize(("bench", "shape"), SHAPE_FILES)
def test_every_captured_shape_parses_whole_with_the_stop_as_its_last_line(
        bench: str, shape: str) -> None:
    got = tracing.parse(TRACE / f"{bench}-{shape}-64.trace", shape)
    assert got.line_count == 65 and sum(got.executed.values()) == 64, got
    assert got.last is not None and got.last[:2] == STOPPED_AT[bench][shape], got.last
    assert tracing.count_lines(TRACE / f"{bench}-{shape}-64.trace") == 65


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
    shutil.copyfile(TRACE / f"dos-djgpp32-{other}-64.trace", path)
    with pytest.raises(ds.Invalid, match=r"line 1 of .* is not a `" + shape):
        tracing.parse(path, shape)


def test_a_line_cut_short_is_refused_where_it_is(tmp_path: Path) -> None:
    lines = (TRACE / "probe-settle-normal-64.trace").read_bytes().splitlines(keepends=True)
    path = tmp_path / "cut.trace"
    path.write_bytes(b"".join(lines[:10]) + lines[10][:40] + b"\n" + b"".join(lines[11:]))
    with pytest.raises(ds.Invalid, match="line 11 of") as got:
        tracing.parse(path, "normal")
    assert got.value.code == "unexpected_answer"


@pytest.mark.parametrize(("name", "cycles"), [
    ("probe-settle-survey-before", 192333), ("probe-settle-survey-after", 192349),
    ("probe-dynamic-survey-before", 238), ("dos-djgpp32-engine-survey-before", 1963039200),
    ("dos-djgpp32-engine-survey-after", 1963039400)])
def test_the_pane_counter_is_read_off_a_survey(name: str, cycles: int) -> None:
    """`dos-djgpp32-engine-survey-after` is the repaint that glued other text over `ESP=`: the
    counter is anchored on its tail, the run state after it."""
    assert dcons.parse_pane_cycles(cap(name)) == cycles


def test_the_last_pane_on_the_screen_gives_the_counter() -> None:
    both = cap("probe-settle-survey-before") + cap("probe-settle-survey-after")
    assert dcons.parse_pane_cycles(both) == 192349


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


def test_a_screen_with_no_counter_reads_none() -> None:
    assert dcons.parse_pane_cycles(cap("probe-settle-cs_ip-16-delta")[:200]) is None


# ------------------------------------------------------------------------------- the run

def test_sixteen_instructions_ask_seventeen_lines_in_hex_and_come_back_elapsed(
        tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    dest = tmp_path / "a.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok", got
    assert dbg.keys == [b"LOGC 11\r"], "one command, the count one more than executed, in hex"
    assert got["verdict"] == "ELAPSED" and got["pc"].endswith(":00000106"), got
    assert {k: got["trace"][k] for k in ("path", "bytes", "shape", "instructions",
                                         "addresses")} == {
        "path": str(dest), "bytes": dest.stat().st_size, "shape": "cs_ip",
        "instructions": 16, "addresses": 1}, got["trace"]
    assert dest.read_bytes() == (TRACE / "probe-settle-cs_ip-16.trace").read_bytes()
    assert no_log_left(dbg.launch.cwd), "the log stayed in the working directory"
    assert got["regs"] and "attribution" in got and "stop_seq" in got and "e9" in got
    assert got["session"]["altered"] is False, "advancing is not writing"
    assert got["summary"].startswith("trace 16 cs_ip: ELAPSED, 16 executed at 1 address")


def test_the_default_shape_is_the_familys_bare_command(tmp_path: Path) -> None:
    dbg = live(Tracer([cap("probe-settle-survey-after"), cap("probe-settle-normal-survey-after")],
                      cwd_of(tmp_path),
                      [("probe-settle-normal-16", "probe-settle-normal-16-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "n.trace")))
    assert got["status"] == "ok" and got["trace"]["shape"] == "normal", got
    assert dbg.keys == [b"LOG 11\r"]


def test_a_dynamic_core_is_refused_by_its_counter_and_the_file_is_kept(tmp_path: Path) -> None:
    """The negative of the per-call proof: seventeen lines while `cc=` did not move."""
    live(Tracer([cap("probe-dynamic-survey-before"), cap("probe-dynamic-survey-after")],
                cwd_of(tmp_path), [("probe-dynamic-cs_ip-16", "probe-dynamic-cs_ip-16-delta")]))
    dest = tmp_path / "d.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert "moved by 0 while the log says 16" in got["message"], got["message"]
    assert "cpu core=normal" in got["message"], got["message"]
    assert got["trace"]["path"] == str(dest) and dest.exists(), got
    assert got["stop_seq"] and got["pc"].endswith(":00000106"), got


def cut(tmp_path: Path, close: str | None = "probe-cut-close-delta",
        kind: type[Tracer] = Tracer) -> Tracer:
    """A breakpoint at the `dec bx` after the settle loop, and a trace asked past it."""
    dbg = live(kind([cap("probe-cut-survey-before"), cap("probe-cut-survey-after-close")],
                      cwd_of(tmp_path),
                      [("probe-cut-open", "probe-cut-open-delta"), (None, close)]))
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", "0814:0108"))
    return dbg


def test_a_breakpoint_that_cuts_the_trace_is_other_stop_and_the_log_is_closed_first(
        tmp_path: Path) -> None:
    dbg = cut(tmp_path)
    dest = tmp_path / "c.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok", got
    assert dbg.keys == [b"LOGC 186A1\r", b"LOGC 0\r"], "the open log closed before it moved"
    assert got["verdict"] == "OTHER_STOP" and got["attribution"]["ref"] == "0814:0108", got
    assert got["trace"]["instructions"] == 5506 and got["trace"]["addresses"] == 1, got["trace"]
    assert got["pc"].endswith(":00000108") and dest.exists() and no_log_left(
        dbg.launch.cwd)
    assert not log_open(), "a close that answered leaves no log to close"


def test_a_close_that_does_not_answer_names_the_moved_log_as_maybe_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The log moves before the close is typed, so the refusal names it at `dest`."""
    monkeypatch.setattr(tracing, "CLOSE_WAIT_S", 0.2)
    dbg = cut(tmp_path, close=None)
    dest = tmp_path / "c.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert got["trace"] == {"path": str(dest), "closed": False}
    assert dest.exists() and no_log_left(dbg.launch.cwd)
    assert "`close` ends the emulator" in got["message"] and dstate.STATE.log_open is True


def test_a_bound_that_runs_out_interrupts_the_trace_and_collects_what_ran(
        tmp_path: Path) -> None:
    """THE BOUND INTERRUPTS: the stop the count waits for never comes, so at the bound the
    machine is brought back with `BREAK` where it stands, and what the log holds up to there is
    collected as a stop that cut it would be (moved, closed, counted against `cc=`): a TIMEOUT,
    the log closed and nothing left in the working directory."""
    dbg = live(Tracer([cap("probe-int-mid-survey-before"),
                       cap("probe-int-mid-survey-after-close")], cwd_of(tmp_path),
                      [("probe-int-mid-cs_ip", None),
                       (None, "probe-int-mid-close-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "t.trace"), seconds=0.3))
    assert got["status"] == "ok" and got["verdict"] == "TIMEOUT", got
    assert "BREAK" in dbg.sent and got["trace"]["instructions"] == 6, got
    assert dbg.keys == [b"LOGC 186A1\r", b"LOGC 0\r"] and no_log_left(dbg.launch.cwd)
    assert not log_open()


def test_the_running_check_comes_before_the_leftover(tmp_path: Path) -> None:
    """After an expired bound the machine runs with the log open: a trace asked then is told the
    machine runs, not to move a file the debugger is still writing."""
    dbg = settle(tmp_path, running=True)
    (dbg.launch.cwd / tracing.LOG_FILE).write_bytes(b"0814:00000106\n")
    dstate.STATE.log_open = True
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "o.trace")))
    refused_quietly(dbg, got, "not_stopped", "running")


def log_open() -> bool:
    """Read through a call, so a type checker does not carry an earlier assertion's value past
    the tool calls that change it."""
    return dstate.STATE.log_open


@pytest.mark.parametrize(("typed", "released"), [
    (b"LOGC 11\r", True), (b"LOG 186A1\r", True), (b"LOGL C9\r", True), (b"LOGS 0\r", True),
    (b"BPLIST\r", False), (b"HEAVYLOG\r", False), (b"LOGC\r", False)])
def test_a_log_command_is_a_release_and_clears_the_stopped_flag(
        typed: bytes, released: bool) -> None:
    """A typed command that lets the guest run has to clear the flag a run key clears, or the
    next contact reads a running machine as parked and types into a console that is not
    listening."""
    s = SimpleNamespace(_at_debugger=True, _peek_carry="I->", _read=lambda _s=0.0: "")
    ds.Session._release(cast(ds.Session, s), typed)
    assert s._at_debugger is (not released) and (s._peek_carry == "") is released


def test_close_forgets_a_log_left_open() -> None:
    install()
    dstate.STATE.log_open = True
    assert cast(dict[str, Any], server.close())["closed"] is True
    assert not log_open()


# ------------------------------------------------------- stops the trace did not ask for

def cut_by(tmp_path: Path, scenario: str) -> Tracer:
    """A capture of the probe's DOS boot with `BPINT 21` armed: the log moved out, then
    `LOGC 0`, then the survey after the close."""
    return live(Tracer([cap(f"probe-{scenario}-survey-before"),
                        cap(f"probe-{scenario}-survey-after-close")], cwd_of(tmp_path),
                       [(f"probe-{scenario}-cs_ip", f"probe-{scenario}-cs_ip-delta"),
                        (None if scenario != "post" else "probe-post-close",
                         f"probe-{scenario}-close-delta")]))


def test_an_interrupt_breakpoint_counts_its_int_without_running_it(tmp_path: Path) -> None:
    """The counter takes the INT and the machine stops before running it, so `cc=` moved one
    more than the six instructions that executed; the trace is whole, not a dynamic core."""
    dbg = cut_by(tmp_path, "int-mid")
    dest = tmp_path / "i.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["trace"]["instructions"] == 6, got["trace"]
    assert tracing.AT_ITS_START not in got["trace"]["note"], got["trace"]
    assert got["pc"] == "0814:00000108" and got["cpu_mode"] == "real", got
    assert dbg.keys == [b"LOGC 186A1\r", b"LOGC 0\r"] and no_log_left(dbg.launch.cwd)


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
    live(Tracer([cap("probe-int-mid-survey-before"), cap("probe-int-mid-survey-after-close")],
                cwd_of(tmp_path), [("probe-int-mid-cs_ip", "probe-int-mid-cs_ip-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=6, shape="cs_ip",
                                            dest=str(tmp_path / "e.trace")))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got


def test_a_log_the_bios_closed_before_the_stop_is_refused_and_kept(tmp_path: Path) -> None:
    """The power-on self test closes the log while the machine runs on: the close then writes a
    fresh empty file, which is how it shows, and that file is removed; the three lines are
    kept, moved before the close could write over them."""
    dbg = cut_by(tmp_path, "post")
    dest = tmp_path / "p.trace"
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert "closed the debugger's log" in got["message"], got["message"]
    assert dest.read_bytes() == (TRACE / "probe-post-cs_ip.trace").read_bytes()
    assert no_log_left(dbg.launch.cwd) and got["stop_seq"], got


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
    assert got["attribution"].get("retrace_pending") is True, got["attribution"]
    assert not dstate.STATE.retrace_pending


def test_addresses_count_the_distinct_executed_places(tmp_path: Path) -> None:
    live(Tracer([cap("dos-djgpp32-engine-survey-before"), cap("dos-djgpp32-engine-survey-after")],
                cwd_of(tmp_path),
                [("dos-djgpp32-engine-cs_ip-200", "dos-djgpp32-engine-cs_ip-200-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=200, shape="cs_ip",
                                            dest=str(tmp_path / "x.trace")))
    lines = (TRACE / "dos-djgpp32-engine-cs_ip-200.trace").read_bytes().splitlines()
    assert got["status"] == "ok" and got["trace"]["instructions"] == 200, got
    assert got["trace"]["addresses"] == len(set(lines[:-1])) > 1, got["trace"]


@pytest.mark.parametrize("shape", list(tracing.SHAPES))
def test_every_shape_types_its_own_word(shape: str, tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    server.trace(instructions=16, shape=shape, dest=str(tmp_path / "w.trace"))
    word = {"normal": b"LOG", "short": b"LOGS", "long": b"LOGL", "cs_ip": b"LOGC"}[shape]
    assert dbg.keys == [word + b" 11\r"]


def test_more_lines_than_asked_is_not_this_log(tmp_path: Path) -> None:
    live(Tracer([cap("probe-settle-survey-before"), cap("probe-settle-survey-after")],
                cwd_of(tmp_path), [("probe-settle-cs_ip-64", "probe-settle-cs_ip-16-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "m.trace")))
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert "65 lines for 17 asked" in got["message"] and log_open()


def test_an_empty_log_is_refused_and_kept(tmp_path: Path) -> None:
    live(Tracer([cap("probe-settle-survey-before"), cap("probe-settle-survey-after")],
                cwd_of(tmp_path), [("probe-post-close", "probe-settle-cs_ip-16-delta"),
                                   (None, "probe-cut-close-delta")]))
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
    under the call): the prompt comes back with no log, and the session's logfile says why."""
    dbg = live(LogfileTracer([cap("probe-settle-survey-before")], cwd_of(tmp_path),
                             [(None, "probe-unwritable-cs_ip-16-delta")]))
    dbg.appends = "probe-unwritable-logfile"
    dbg.launch.logfile = tmp_path / "guest.log"
    dbg.launch.logfile.write_text("an earlier line\n")
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "n.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "could not create LOGCPU.TXT" in got["message"], got["message"]
    assert "Logfile couldn't be created." in got["message"], got["message"]
    assert "`close`" in got["message"], got["message"]
    assert not log_open() and dbg.keys == [b"LOGC 11\r"]


@pytest.mark.parametrize(("earlier", "words"), [
    (None, "cannot be told apart"),
    ("", "does not say it was refused"),
    (cap("probe-unwritable-logfile"), "does not say it was refused")],
    ids=["no logfile", "logfile", "an earlier refusal before the mark"])
def test_a_stop_with_no_log_and_no_word_why_names_both_causes_and_keeps_the_log_open(
        tmp_path: Path, earlier: str | None, words: str) -> None:
    """Without the debugger's own words since the release the file may have been refused or
    removed while open, so the log stays remembered: a refusal written before the trace began is
    another call's. The logfile gains a count's own lines, which are not a refusal either."""
    panes = [cap("probe-settle-survey-before")]
    logs: list[tuple[str | None, str | None]] = [(None, "probe-settle-cs_ip-16-delta")]
    if earlier is None:
        live(Tracer(panes, cwd_of(tmp_path), logs))
    else:
        dbg = live(LogfileTracer(panes, cwd_of(tmp_path), logs))
        dbg.appends = "probe-count-logfile"
        dbg.launch.logfile = tmp_path / "guest.log"
        dbg.launch.logfile.write_text(earlier)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "m.trace")))
    assert got["status"] == "INVALID" and got["code"] == "unexpected_answer", got
    assert "was refused the file, or something removed it" in got["message"], got["message"]
    assert words in got["message"] and log_open(), got["message"]


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
    assert f"1 to {tracing.INSTRUCTIONS_MAX}." in str(server.trace.__doc__)


@pytest.mark.parametrize("where", ["description", "REFERENCE.md"])
def test_the_texts_say_the_bound_interrupts_the_trace(where: str) -> None:
    """A trace whose stop never comes is interrupted at its bound, so the texts may not
    promise a count that runs on, nor a log left open for the next trace."""
    package = Path(__file__).parents[1]
    text = str(server.trace.__doc__) if where == "description" else (package / where).read_text()
    flat = " ".join(text.split())
    assert "interrupted where it stood" in flat
    for promise in ("runs to its count and stops there", "so the log runs on to its count",
                    "leaves a log running to its count", "no such close was seen"):
        assert promise not in flat, promise


def test_the_bound_itself_is_accepted() -> None:
    checks.check("trace", instructions=tracing.INSTRUCTIONS_MAX, seconds=600)


def refused_quietly(dbg: Tracer, got: dict[str, Any], code: str, words: str) -> None:
    assert got["status"] == "INVALID" and got["code"] == code, got
    assert words in got["message"], got["message"]
    assert dbg.keys == [] and dbg.sent == [], "a refusal reached the terminal"


def test_a_dest_already_there_is_refused_and_kept(tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    mine = tmp_path / "mine.trace"
    mine.write_bytes(b"the caller's")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(mine)))
    refused_quietly(dbg, got, "bad_argument", "already exists")
    assert mine.read_bytes() == b"the caller's"


def test_a_dest_in_the_working_directory_is_refused(tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(
        instructions=16, dest=str(dbg.launch.cwd / "x.trace")))
    refused_quietly(dbg, got, "bad_argument", "working directory")


def test_a_dest_whose_directory_is_missing_is_refused(tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16,
                                            dest=str(tmp_path / "nowhere" / "x.trace")))
    refused_quietly(dbg, got, "bad_argument", "not a directory")


def test_no_dest_and_no_captures_directory_is_refused_naming_both(tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16))
    refused_quietly(dbg, got, "bad_argument", "start(captures_dir=)")


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
    dbg = settle(tmp_path, captures_dir=tmp_path / "missing")
    got = cast(dict[str, Any], server.trace(instructions=16))
    refused_quietly(dbg, got, "bad_argument", "is not there")


def test_a_dest_from_the_home_directory_is_written_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest="~/h.trace"))
    assert got["status"] == "ok" and got["trace"]["path"] == str(tmp_path / "h.trace"), got
    assert not (tmp_path / "~").exists()


def test_a_set_file_already_there_is_refused_and_the_counter_skips_one(tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    (tmp_path / "s.trace.set.jsonl").write_text("the caller's")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "s.trace")))
    refused_quietly(dbg, got, "bad_argument", "already exists")
    caps = tmp_path / "caps"
    caps.mkdir()
    (caps / "trace-1.trace.set.jsonl").write_text("an earlier set")
    settle(tmp_path / "again", captures_dir=caps)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["trace"]["path"] == str(caps / "trace-2.trace"), got


def test_the_log_is_looked_for_under_both_spellings(tmp_path: Path) -> None:
    assert [p.name for p in tracing.log_places(tmp_path)] == ["LOGCPU.TXT", "logcpu.txt"]


def test_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    dbg = settle(tmp_path, running=True)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "r.trace")))
    refused_quietly(dbg, got, "not_stopped", "running")


def test_a_build_without_the_cpu_log_is_refused_before_anything_is_typed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "plain"
    plain.write_bytes(b"\x00help\x00LOG? no\x00")
    plain.chmod(0o755)
    dbg = settle(tmp_path, binary=plain)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "h.trace")))
    refused_quietly(dbg, got, "no_channel", "heavy_debug")


def test_a_hand_built_launch_s_bare_name_is_found_on_the_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `Launch` built without `start` carries the bare name; `trace` reads the build the PATH
    gives it, as the session itself was spawned."""
    heavy = tmp_path / "bin" / "dosbox-x"
    heavy.parent.mkdir()
    heavy.write_bytes(b"\x00help\x00" + binaries.HEAVY_DEBUG_MARK + b"\x00")
    heavy.chmod(0o755)
    monkeypatch.setenv("PATH", str(heavy.parent))
    dbg = settle(tmp_path, binary=Path("dosbox-x"))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "b.trace")))
    assert got["status"] == "ok", got
    assert dbg.launch.binary == "dosbox-x"


def test_a_session_build_that_is_gone_is_refused_before_anything_is_typed(
        tmp_path: Path) -> None:
    gone = tmp_path / "gone" / "dosbox-x"
    dbg = settle(tmp_path, binary=gone)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "g.trace")))
    refused_quietly(dbg, got, "host_failed", "not an executable file")


def test_a_log_already_in_the_working_directory_is_refused_never_read_or_deleted(
        tmp_path: Path) -> None:
    dbg = settle(tmp_path)
    theirs = dbg.launch.cwd / tracing.LOG_FILE.lower()
    theirs.write_bytes(b"somebody's log")
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "l.trace")))
    refused_quietly(dbg, got, "bad_argument", "already sitting at")
    assert theirs.read_bytes() == b"somebody's log"


@pytest.mark.parametrize("shape", ["missing_directory", "free_name", "relative"])
def test_a_dangling_link_where_the_log_opens_is_refused_before_anything_is_typed(
        tmp_path: Path, shape: str) -> None:
    """Three links at the place the log opens, each somebody's file and refused like one:
    without the guard, into a missing directory the debugger is refused its file and the
    console spoiled; to a free name elsewhere it writes the log there and `trace.path` comes
    back a link; a relative one, collected at another depth, breaks the reply."""
    dbg = settle(tmp_path)
    link = dbg.launch.cwd / tracing.LOG_FILE
    far = {"missing_directory": tmp_path / "nowhere" / "LOG.TXT",
           "free_name": tmp_path / "elsewhere.txt", "relative": Path("rel.txt")}[shape]
    link.symlink_to(far)
    dest = tmp_path / "deeper" / "still" / "l.trace"
    dest.parent.mkdir(parents=True)
    got = cast(dict[str, Any], server.trace(instructions=16, dest=str(dest)))
    refused_quietly(dbg, got, "bad_argument", "already sitting at")
    landed = far if far.is_absolute() else dbg.launch.cwd / far
    assert link.is_symlink() and not landed.exists() and not dest.exists()


@pytest.mark.parametrize(("mode", "left_open"), [(0o555, False), (0o555, True), (0o666, False)])
def test_a_working_directory_the_emulator_cannot_write_is_refused_before_anything_is_typed(
        tmp_path: Path, mode: int, left_open: bool) -> None:
    """Neither the trace's command nor the close of a log an earlier trace left open may be
    typed there (PROVENANCE, `probe-unwritable-*`), and that log stays remembered: nothing here
    proved it closed. A directory that can be written and not searched takes no file either."""
    dbg = settle(tmp_path)
    dstate.STATE.log_open = left_open
    dbg.launch.cwd.chmod(mode)
    try:
        got = cast(dict[str, Any], server.trace(instructions=16, dest=str(tmp_path / "u.trace")))
    finally:
        dbg.launch.cwd.chmod(0o755)
    refused_quietly(dbg, got, "no_channel", f"{dbg.launch.cwd} is not writable")
    assert log_open() is left_open


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
    dbg = settle(tmp_path)
    bad = cast(dict[str, Any], server.perform(steps=[{"op": "trace", "instructions": 0}]))
    assert bad["status"] == "INVALID" and bad["errors"][0]["op"] == "trace", bad
    assert dbg.keys == []
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

    def __init__(self, logfile: Path | None, cpu: str = "dos-djgpp32-CPU",
                 refuse: bool = False) -> None:
        self.launch = SimpleNamespace(logfile=logfile)
        self.asked: list[str] = []
        self.cpu = cpu
        self.refuse = refuse

    def listing(self, command: str) -> str:
        self.asked.append(command)
        if self.refuse:
            raise ds.Invalid("unexpected_answer", f"`{command}` brought no prompt back")
        return {"CPU": (MACHINE / f"{self.cpu}.log.txt").read_text(encoding="latin-1"),
                "GDT": cap("dos-djgpp32-gdt-listing"),
                "LDT": cap("dos-djgpp32-ldt-listing")}[command]


def stopped_in(mode: str) -> None:
    dstate.STATE.last_stop["where"] = {"cs": "00A7", "eip": "00000000", "mode": mode}


def per_routine(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {r["symbol"]: r["instructions"] for r in rows}


def test_the_probe_start_window_joins_to_its_three_routines(tmp_path: Path) -> None:
    """The known answer is the guest's own: 200 instructions from `start` split 51, 144, 5."""
    live(Tracer([cap("probe-start-survey-before"), cap("probe-start-survey-after")],
                cwd_of(tmp_path), [("probe-start-normal-200", "probe-start-normal-200-delta")]))
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
    assert found["set_path"] == str(dest) + ".set.jsonl" and len(rows) == found["addresses"]
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


def test_without_a_logfile_the_protected_lines_get_no_linear_and_the_note_says_why() -> None:
    load(str(GUEST / "probe.sym"), PROBE_BASE)
    stopped_in("Pr32")
    notes: list[str] = []
    got = tracing.join(cast(ds.Session, Listings(None)),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), True,
                       notes)
    assert got.symbols == [] and all("addr" not in r for r in got.rows), got.rows[:2]
    assert any("`logfile`" in n for n in notes), notes


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
    parsed = tracing.parse(TRACE / "dos-djgpp32-engine-cs_ip-200.trace", "cs_ip")
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


class ListingTracer(Tracer):
    """The dos-djgpp32 window's double, answering the descriptor listings as `Listings` does, or
    refusing them when `refuse` is set."""

    refuse = False

    def listing(self, command: str) -> str:
        return Listings(None, refuse=self.refuse).listing(command)

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        raise ds.Invalid("no_channel", "the guest's log is not what this case reads")

    def selector(self, reg: str) -> dict[str, int]:
        """The real reader over the captured dos-djgpp32 `SELINFO` screen."""
        screen = SimpleNamespace(command=lambda _text: SELINFO_SCREEN, alive=lambda: True)
        return ds.Session.selector(cast(ds.Session, screen), reg)


def test_the_reply_shows_sixty_four_routines_and_counts_the_rest(tmp_path: Path) -> None:
    """A table with a symbol at every address the dos-djgpp32 window executed: one routine each,
    the first sixty-four in the reply and every address in the set file."""
    dbg = live(ListingTracer([cap("dos-djgpp32-engine-survey-before"),
                              cap("dos-djgpp32-engine-survey-after")], cwd_of(tmp_path),
                             [("dos-djgpp32-engine-cs_ip-200",
                               "dos-djgpp32-engine-cs_ip-200-delta")]))
    dbg.launch.logfile = tmp_path / "guest.log"
    lines = (TRACE / "dos-djgpp32-engine-cs_ip-200.trace").read_text().splitlines()
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
    for line in (TRACE / "dos-djgpp32-engine-cs_ip-200.trace").read_text().splitlines():
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
    session = Listings(Path("guest.log"), cpu="probe-booted-CPU")
    got = tracing.join(cast(ds.Session, session),
                       tracing.parse(TRACE / "probe-start-normal-200.trace", "normal"), False,
                       notes)
    assert session.asked == ["CPU"] and all("addr" not in r for r in got.rows), got.rows[:2]
    assert any(tracing.NO_LINEAR in n for n in notes), notes


def test_tables_that_cannot_be_read_leave_a_note_and_the_trace_whole(tmp_path: Path) -> None:
    """A descriptor listing that fails after the log has moved costs the join, never the
    proved trace or where its file went."""
    dbg = live(ListingTracer([cap("dos-djgpp32-engine-survey-before"),
                              cap("dos-djgpp32-engine-survey-after")], cwd_of(tmp_path),
                             [("dos-djgpp32-engine-cs_ip-200",
                               "dos-djgpp32-engine-cs_ip-200-delta")]))
    dbg.launch.logfile = tmp_path / "guest.log"
    dbg.refuse = True
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
    monkeypatch.setattr(json, "dumps", full)
    live(Tracer([cap("probe-start-survey-before"), cap("probe-start-survey-after")],
                cwd_of(tmp_path), [("probe-start-normal-200", "probe-start-normal-200-delta")]))
    dest = tmp_path / "f.trace"
    got = cast(dict[str, Any], server.trace(instructions=200, dest=str(dest)))
    assert got["status"] == "ok" and got["trace"]["set_path"]["available"] is False, got["trace"]
    assert not Path(str(dest) + ".set.jsonl").exists() and dest.exists()
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
    dbg = cut(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert dbg.keys == [b"LOGC 186A1\r"] and log_open()


def test_a_cut_run_whose_move_fails_remembers_the_log_it_left_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(source: Path, dest: Path, what: str) -> Path:
        raise ds.Invalid("host_failed", f"the {what} at {source} could not be moved to {dest}")
    monkeypatch.setattr(dcollect, "collect", refused)
    dbg = cut(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert dbg.keys == [b"LOGC 186A1\r"] and log_open()


def test_a_wait_that_breaks_off_remembers_the_log_it_released(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The log opens with the release: a wait that leaves by an exception (a client that went
    away, a read that failed) leaves it open, and the next trace has to know."""
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.0)
    dbg = live(Tracer([cap("probe-settle-survey-before")], cwd_of(tmp_path),
                      [("probe-settle-cs_ip-16", None)]))

    def gone(*_args: object) -> None:
        raise RuntimeError("the client went away")
    with pytest.raises(RuntimeError):
        tracing.trace(cast(ds.Session, dbg), 16, "cs_ip", tmp_path / "g.trace", 5.0, gone)
    assert dbg.keys == [b"LOGC 11\r"] and log_open()


def test_a_count_that_ran_out_closed_its_own_log(tmp_path: Path) -> None:
    settle(tmp_path)
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "s.trace")))
    assert got["status"] == "ok" and not log_open(), got


def test_a_log_left_open_is_closed_and_its_empty_file_removed_before_anything_else(
        tmp_path: Path) -> None:
    """A refusal that comes after the close of a log an expired trace left leaves no file of this
    call's behind, or the next trace would be refused over it."""
    dbg = live(Tracer([], cwd_of(tmp_path), [("probe-post-close", "probe-post-close-delta")]))

    def cut_survey() -> Any:
        raise ds.Invalid("unexpected_answer", "the survey came back cut")
    dbg.where_and_registers = cut_survey  # type: ignore[method-assign]
    dstate.STATE.log_open = True
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "o.trace")))
    assert got["code"] == "unexpected_answer" and dbg.keys == [b"LOGC 0\r"], got
    assert no_log_left(dbg.launch.cwd) and not log_open()


# --------------------------------------------------------------------- the bound expiring

class LogfileTracer(Tracer):
    """A capture of the session's logfile, appended as the emulator wrote it when the `LOG`
    command was typed: the lines the reset park's run wrote, or a count's."""

    appends = "probe-post-logfile"

    def _write(self, data: bytes) -> None:
        super()._write(data)
        if ds.LOG_COMMAND.fullmatch(data):
            with self.launch.logfile.open("a", encoding="latin-1") as f:
                f.write(cap(self.appends))


def expired_with_logfile(tmp_path: Path, earlier: str, appends: str) -> dict[str, Any]:
    """A trace from the reset park bounded short, its logfile holding `earlier` before the
    trace and gaining the capture `appends` while it waits."""
    dbg = live(LogfileTracer([cap("probe-post-survey-before")], cwd_of(tmp_path),
                             [("probe-post-cs_ip", None)]))
    dbg.appends = appends
    logfile = tmp_path / "guest.log"
    logfile.write_text(earlier, encoding="latin-1")
    dbg.launch.logfile = logfile
    return cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                             dest=str(tmp_path / "p.trace"), seconds=0.3))


def test_a_log_the_machine_closed_before_the_bound_is_not_what_ran(tmp_path: Path) -> None:
    """From the reset park the BIOS closes the debugger's log before its count: the bound
    interrupts the run, and the collect finds the log already closed, so its lines are not what
    ran and the trace is refused, with the stop it ended at."""
    dbg = live(Tracer([cap("probe-post-survey-before"), cap("probe-post-survey-after-close")],
                      cwd_of(tmp_path),
                      [("probe-post-cs_ip", None),
                       ("probe-post-close", "probe-post-close-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "p.trace"), seconds=0.3))
    assert got["code"] == "readback_refused" and "BREAK" in dbg.sent, got
    assert "are not what ran" in got["message"] and "stop_seq" in got, got


def test_the_logfile_is_read_in_chunks_and_a_line_across_two_is_found(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A guest's own line carrying the words is not the debugger's: only a line that starts
    with them is."""
    monkeypatch.setattr(tracing, "READ_CHUNK_BYTES", 7)
    logfile = tmp_path / "guest.log"
    logfile.write_text("x\nBochs port E9h: " + tracing.NOT_CREATED_LINE + "\n")
    assert not tracing._logfile_says(logfile, 2, tracing.NOT_CREATED_LINE)
    logfile.write_text("x\n" + tracing.NOT_CREATED_LINE + "\n")
    assert tracing._logfile_says(logfile, 2, tracing.NOT_CREATED_LINE)


def test_a_logfile_the_host_cannot_read_says_nothing(tmp_path: Path) -> None:
    assert not tracing._logfile_says(tmp_path, 0, tracing.NOT_CREATED_LINE), \
        "a directory read as a logfile"


def test_the_line_is_found_across_every_split_of_a_chunk(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Down to a chunk of one byte, so the carry has to hold all but the line's last byte."""
    logfile = tmp_path / "guest.log"
    logfile.write_text("x\n" + tracing.NOT_CREATED_LINE + "\n")
    for size in range(1, len(tracing.NOT_CREATED_LINE) + 3):
        monkeypatch.setattr(tracing, "READ_CHUNK_BYTES", size)
        assert tracing._logfile_says(logfile, 0, tracing.NOT_CREATED_LINE), size


def test_a_line_that_begins_at_the_mark_is_at_a_line_start(tmp_path: Path) -> None:
    """The mark is where the logfile ended at the release, which is a line's start."""
    earlier = "an earlier line\n"
    logfile = tmp_path / "guest.log"
    logfile.write_text(earlier + tracing.NOT_CREATED_LINE + "\n")
    assert tracing._logfile_says(logfile, len(earlier), tracing.NOT_CREATED_LINE)


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


def test_the_logfile_is_read_a_chunk_at_a_time(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The logfile grows for the whole session, so it is never read whole into memory."""
    monkeypatch.setattr(tracing, "READ_CHUNK_BYTES", 5)
    logfile = ReadSizes(tmp_path / "guest.log")
    logfile.write_text("x\n" * 40)
    ReadSizes.asked = []
    assert not tracing._logfile_says(logfile, 0, tracing.NOT_CREATED_LINE)
    assert ReadSizes.asked and set(ReadSizes.asked) == {5}, ReadSizes.asked


# ------------------------------------------------------------------- the reply's other keys

def test_a_set_file_that_appeared_during_the_wait_is_left_alone(tmp_path: Path) -> None:
    """Judged absent before the run, then made by somebody else while it ran."""
    path = tmp_path / "a.trace.set.jsonl"
    path.write_text("theirs\n")
    notes: list[str] = []
    assert tracing._write_set(path, [{"addr": "0814:00000106", "count": 1}], notes) is None
    assert path.read_text() == "theirs\n" and "could not be written" in notes[0], notes


class LateTracer(Tracer):
    """The stop heard a while after the command: the wait's reads come back empty until then."""

    late_s = 0.3
    typed_at: float | None = None

    def _write(self, data: bytes) -> None:
        if ds.LOG_COMMAND.fullmatch(data):
            self.typed_at = time.monotonic()
        super()._write(data)

    def _read(self, seconds: float = 0.0) -> str:
        if self.typed_at is not None and time.monotonic() < self.typed_at + self.late_s:
            time.sleep(0.02)
            return ""
        return super()._read(seconds)


def test_waited_s_is_when_the_stop_was_heard_not_the_work_after_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_join = tracing.join

    def slow(*args: Any) -> tracing.Coverage:
        time.sleep(0.6)
        return real_join(*args)
    monkeypatch.setattr(tracing, "join", slow)
    live(LateTracer([cap("probe-settle-survey-before"), cap("probe-settle-survey-after")],
                    cwd_of(tmp_path), [("probe-settle-cs_ip-16", "probe-settle-cs_ip-16-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "w.trace")))
    assert got["status"] == "ok" and LateTracer.late_s <= got["waited_s"] < 0.6, got["waited_s"]


def test_the_e9_block_names_the_tool_that_reads_the_lines_not_an_argument_trace_lacks(
        tmp_path: Path) -> None:
    dbg = live(LogfileTracer([cap("probe-settle-survey-before"),
                              cap("probe-settle-survey-after")], cwd_of(tmp_path),
                             [("probe-settle-cs_ip-16", "probe-settle-cs_ip-16-delta")]))
    dbg.appends = "probe-count-logfile"
    dbg.launch.logfile = tmp_path / "guest.log"
    dbg.launch.logfile.write_text("")
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "e.trace")))
    assert got["status"] == "ok" and got["e9"]["shown"] == 0, got["e9"]
    how = got["e9"]["how"]
    assert "e9=" not in how and "`log(" in how, how
    named = set(re.findall(r"(\w+)=", how))
    params = inspect.signature(server.log).parameters
    required = {n for n, p in params.items() if p.default is inspect.Parameter.empty}
    assert named <= set(params) and required <= named, (named, required)


def test_with_the_captures_directory_the_working_directory_the_default_lands_there(
        tmp_path: Path) -> None:
    dbg = settle(tmp_path, captures_dir=cwd_of(tmp_path))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip"))
    assert got["status"] == "ok", got
    assert got["trace"]["path"] == str(dbg.launch.cwd / "trace-1.trace"), got["trace"]
    assert no_log_left(dbg.launch.cwd)


def test_a_trace_started_on_a_code_breakpoint_stops_there_again_and_says_so(
        tmp_path: Path) -> None:
    """The log is the live run's (PROVENANCE); the surveys and deltas around it are the cut
    scenario's at the same stop, 0814:0108 with the log open, then closed, which is the state
    that run was in: no capture of its own surveys was kept."""
    live(Tracer([cap("probe-cut-survey-after-close"), cap("probe-cut-survey-after-close")],
                cwd_of(tmp_path), [("probe-on-bp-cs_ip", "probe-cut-open-delta"),
                                   (None, "probe-cut-close-delta")]))
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", "0814:0108"))
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "b.trace")))
    assert got["status"] == "ok" and got["verdict"] == "OTHER_STOP", got
    assert got["attribution"]["ref"] == "0814:0108" and got["trace"]["instructions"] == 0, got
    assert "code breakpoint" in got["trace"]["note"], got["trace"]["note"]


def test_unplaced_counts_the_executed_addresses_no_symbol_places(tmp_path: Path) -> None:
    """Without the probe's data rows the table ends at `bump`'s own address, so the addresses of
    its body above it are executed and unplaced, beside the placed ones."""
    code_only = tmp_path / "code.sym"
    code_only.write_text("".join(x + "\n" for x in (GUEST / "probe.sym").read_text().splitlines()
                                 if " T " in x))
    live(Tracer([cap("probe-start-survey-before"), cap("probe-start-survey-after")],
                cwd_of(tmp_path), [("probe-start-normal-200", "probe-start-normal-200-delta")]))
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

def survey_with_counter(name: str, cycles: int) -> str:
    """A captured survey with its `cc=` value replaced, the one field changed: no capture
    crosses the counter's 32-bit wrap or shows a core that overcounts a cut run."""
    text, n = re.subn(r"cc=[0-9]+", f"cc={cycles}", cap(name))
    assert n == 1, f"{name}: {n} counters"
    return text


def test_the_counter_is_read_across_its_wrap_by_the_call(tmp_path: Path) -> None:
    live(Tracer([survey_with_counter("probe-settle-survey-before", tracing.CYCLES_WRAP - 5),
                 survey_with_counter("probe-settle-survey-after", 11)], cwd_of(tmp_path),
                [("probe-settle-cs_ip-16", "probe-settle-cs_ip-16-delta")]))
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip",
                                            dest=str(tmp_path / "w.trace")))
    assert got["status"] == "ok" and got["trace"]["instructions"] == 16, got


def test_a_cut_run_that_counted_two_more_is_refused(tmp_path: Path) -> None:
    """The allowance is one, the INT an interrupt breakpoint counted and did not run: two more
    is a counter that does not follow the log."""
    before = dcons.parse_pane_cycles(cap("probe-cut-survey-before"))
    executed = tracing.count_lines(TRACE / "probe-cut-open.trace") - 1
    assert before is not None
    dbg = live(Tracer([cap("probe-cut-survey-before"),
                       survey_with_counter("probe-cut-survey-after-close", before + executed + 2)],
                      cwd_of(tmp_path),
                      [("probe-cut-open", "probe-cut-open-delta"),
                       (None, "probe-cut-close-delta")]))
    assert dstate.STATE.store is not None
    dstate.STATE.store.add(arming.declare("breakpoint", "address", "0814:0108"))
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "c.trace")))
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert f"moved by {executed + 2} while the log says {executed}" in got["message"]
    assert dbg.keys == [b"LOGC 186A1\r", b"LOGC 0\r"]


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


def test_an_interrupt_that_found_no_prompt_names_the_log_left_open(tmp_path: Path) -> None:
    """The bound's `BREAK` whose prompt never came is `not_settled`, and the debugger's log is
    still open: the refusal names its path and what the next trace does about it."""
    class Unsettled(Tracer):
        def break_in(self, seconds: float = 5.0) -> float:
            raise ds.Invalid("not_settled", "the prompt did not appear")

    live(Unsettled([cap("probe-int-mid-survey-before")], cwd_of(tmp_path),
                   [("probe-int-mid-cs_ip", None)]))
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "u.trace"), seconds=0.3))
    assert got["code"] == "not_settled" and got["trace"]["closed"] is False, got
    assert "still open" in got["message"] and log_open(), got["message"]



class StopsAsTheBoundExpires(Tracer):
    """The race the bound can lose: a stop cuts the count after the wait gave up and before the
    interrupt looks, so nothing is interrupted and the run ended at another's stop."""

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: ds.Progress = ds.no_progress) -> tuple[bool, float]:
        expired, saw = super().log_cpu(word, count, began, deadline, progress)
        return (True if count else expired), saw     # the close (`LOGC 0`) answers as it does


def test_a_trace_cut_as_the_bound_expires_is_another_stop_not_a_timeout(tmp_path: Path) -> None:
    dbg = cut(tmp_path, kind=StopsAsTheBoundExpires)
    got = cast(dict[str, Any], server.trace(instructions=100000, shape="cs_ip",
                                            dest=str(tmp_path / "t.trace")))
    assert "BREAK" not in dbg.sent and got["verdict"] == "OTHER_STOP", (got, dbg.sent)
