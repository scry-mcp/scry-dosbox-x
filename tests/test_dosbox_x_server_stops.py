"""The DOSBox-X server: stops, the running guest and the waits."""

from __future__ import annotations

import dataclasses
import inspect
import re
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import fold_calls
import pytest
from dosbox_x_server_support import (  # noqa: E402
    NamesFake,
    _names,
    _ok,
    _protected_table,
    _start_on_a_booted_fake,
    clean_session,  # noqa: E402, F401
    stub_build,
)
from scry_core import (
    log_marks,
)
from scry_core import vocabulary as vocab
from window_double import window_if

from scry_dosbox_x import arming, checks, folds, grammar, sequence, server
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import mcp as dosbox_mcp
from scry_dosbox_x import process as dprocess
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def test_a_log_that_cannot_be_read_at_a_stop_is_the_verify_s_refusal_never_a_check() -> None:
    class Gone:
        def e9_since_mark(self, mark: int) -> list[str]:
            raise ds.Invalid("no_channel", "the log went away")
    got = sequence._verify_at_a_stop(cast(ds.Session, Gone()), "key", 0)
    assert got == {"checked": False, "expected": "key", "why": "the log went away",
                   "code": "no_channel"}, got


def test_run_to_with_a_cold_control_and_an_expired_bound_is_invalid(tmp_path: Path) -> None:
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


def test_the_stop_a_cancelled_calls_end_made_is_last_stops_cause(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.cs, fake.eip = "00A7", "00001A27"
    fake.running = True
    dosbox_mcp._stop_of_its_own(fake)  # type: ignore[arg-type]
    got = cast(dict[str, Any], server.status())
    assert got["last_stop"]["cause"] == "a cancelled call's stop at 00A7:00001A27", got


def test_resume_enriches_a_halt_and_leaves_a_running_machine_bare(tmp_path: Path) -> None:
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


def test_resume_takes_a_look_for_a_stop_only_with_a_bound(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    server.resume()
    server.resume(seconds=0.1)
    assert fake.looks == [False, True]


def test_a_halt_whose_position_is_unreadable_keeps_the_halt(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A halt is a real observation."""
    fake = _names(tmp_path)
    fake.halted = True

    def cut() -> dict[str, str]:
        raise ds.Invalid("unexpected_answer", "the register pane came back cut")
    monkeypatch.setattr(fake, "where", cut)
    out = cast(dict[str, Any], server.resume())
    assert out["status"] == "ok" and "stop_seq" not in out
    assert out["enrichment"]["available"] is False and "cut" in out["enrichment"]["why"]
    assert "regs" not in out


def test_every_stop_shows_its_guest_lines_since_the_previous_one_bounded(
        tmp_path: Path) -> None:
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
        params = inspect.signature(fold_calls.of(server, tool)).parameters
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


# --------------------------------------- the pending queue, applied at the stop (T2)

def test_what_is_asked_while_the_guest_runs_is_applied_at_the_next_stop(
        tmp_path: Path) -> None:
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
    cleared = server.declaration_clear("breakpoint", ref="_old")
    assert cleared["status"] == "ok" and cleared.get("pending_disarm",
                                                     []) == ["BP 00A7:2000"], cleared
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
    fake = _names(tmp_path, watched=True)
    server.status()
    fake.running = True
    got = server.stop()
    assert got["cause"] == "the `stop` call at 00A7:00000000", got


def test_stop_keeps_the_envelope_on_both_branches(tmp_path: Path) -> None:
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
    # one before (it must not stay on the previous stop while `registers` reads the new
    # address).
    assert st["last_stop"]["stop_seq"] == 1 and st["last_stop"]["pc"] == "00A7:00000000", st
    fake.running = True
    fake.eip = "00001234"
    fake.running = False                                 # a second stop on its own
    assert server.status()["last_stop"]["stop_seq"] == 2
    assert server.status()["last_stop"]["pc"] == "00A7:00001234"
    assert server.status()["last_stop"]["stop_seq"] == 2      # observed once, not per call
    assert server.registers(from_last_stop=True)["regs"]["EIP"] == "0x00001234"


def test_the_running_guest_contract_holds_at_its_edges(tmp_path: Path) -> None:
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
    assert server.declaration_clear("breakpoint", ref="00A7:0100").get("pending_disarm",
                                                                       []) == []   # never armed
    assert server.breakpoint_interrupt(number=0x21)["state"] == "pending"
    assert server.breakpoint_at(ref="00A7:0200")["state"] == "pending"
    lst = server.declaration_list("breakpoint")
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
    cleared = server.declaration_clear("breakpoint", ref="_main")
    assert sorted(cleared["disarmed"]) == ["BP 00A7:1000", "BP 00A7:1200"], cleared
    assert "foreign" not in server.declaration_list("breakpoint")
    # A QUEUED DISARM'S ROW IS NOT FOREIGN while it waits.
    fake.running = True
    assert server.declaration_clear("breakpoint", ref="00A7:0200").get("pending_disarm",
                                                                       []) == ["BP 00A7:0200"]
    assert "foreign" not in server.declaration_list("breakpoint")
    fake.running = False
    # CLOSE TAKES THE STATE WITH IT.
    server.close()
    assert server.status()["last_stop"]["available"] is False
    assert server.status()["pending"] == {"arm": [], "disarm": 0, "symbols_load": False,
                                          "base_remeasure": False}


def test_a_stop_whose_survey_refused_is_not_named_with_the_previous_stops_address(
        tmp_path: Path) -> None:
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


# ------------------------------------------------------- the progress line on a bounded wait


def test_the_sdk_injects_the_context_into_the_waiting_tools_and_hides_it(
        tmp_path: Path) -> None:
    for name in ("run_to", "log_wait", "perform", "drive", "send_keys", "send_mouse", "resume",
                 "start", "close"):
        tool = server.mcp._tool_manager.get_tool(name)
        assert tool is not None and tool.context_kwarg == "ctx", name
        assert "ctx" not in tool.parameters.get("properties", {}), name
    for name in ("step", "registers", "status"):
        tool = server.mcp._tool_manager.get_tool(name)
        assert tool is not None and tool.context_kwarg is None, name


def test_a_stop_reads_only_what_the_guest_wrote_since_the_previous_stop(tmp_path: Path) -> None:
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
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    with mock.patch("scry_dosbox_x.server.ds.Session", lambda _l: Booted(conf=conf)):
        out = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert out["status"] == "ok", out
    recorded = dstate.STATE.as_of()
    assert recorded is not None and recorded["stop_seq"] == 1, recorded
    assert dstate.STATE.last_machine() is not None


@pytest.mark.parametrize("watched", [False, True])
def test_stop_brings_a_running_guest_back_headless_or_windowed(tmp_path: Path,
                                                               watched: bool) -> None:
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


def test_wait_ready_and_close_report_their_progress() -> None:
    """The boot and the close are the waits the owner watches longest, and they painted nothing."""

    class _Booting:
        """A debugger that answers stopped `stops_after` seconds into the boot."""

        def __init__(self, stops_after: float) -> None:
            self.at = time.monotonic() + stops_after
            self.proc = SimpleNamespace(poll=lambda: None)

        def _first_stop(self) -> bool:
            return time.monotonic() >= self.at

        def mark_stopped(self) -> None:
            pass

    ticks: list[str] = []
    numbers: list[tuple[float, float | None]] = []

    def record(p: float, t: float | None, m: str) -> None:
        ticks.append(m)
        numbers.append((p, t))

    ds.Session.wait_ready(_Booting(2.2), 5.0, record)  # type: ignore[arg-type]
    assert ticks and "start: waiting for the debugger" in ticks[0], ticks
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
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], ds_="00AF")
    for bad in (0, grammar.READ_BYTES_MAX + 1):
        out = cast(dict[str, Any], server.read_memory(ref="g_rate", length=bad))
        assert out["status"] == "INVALID" and "memdump" in out["message"], out
    out = cast(dict[str, Any], server.resume(seconds=-1))
    assert out["status"] == "INVALID" and "is not a bound" in out["message"], out
    past = cast(dict[str, Any], server.resume(seconds=vocab.WAIT_MAX_S + 1))
    assert past["code"] == "bad_argument" and f"at most {vocab.WAIT_MAX_S:g}," in past["message"]
    fake.launch.window = window_if(True)         # a windowed session needs no stopper
    fake.where_raises = True                     # it runs, and nothing stops it
    monkeypatch = pytest.MonkeyPatch()
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


def test_resume_with_a_bound_comes_back_with_the_stop_when_the_run_state_says_stopped(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    fake.launch.window = window_if(True)
    monkeypatch.setattr(fake, "alive", lambda: True)
    out = cast(dict[str, Any], server.resume(seconds=2.0))
    assert out["status"] == "ok" and out["verdict"] == "OTHER_STOP" and "pc" in out, out
    # A RUN STATE THAT SAYS RUNNING is no stop: the wait asks on to its bound.
    fake.where_raises = True
    out = cast(dict[str, Any], server.resume(seconds=0.5))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["waited_s"] >= 0.5 and "STILL RUNNING" in out["note"], out


def test_run_to_summary_spells_a_control_that_never_counted_as_a_count_not_a_prefix(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.launch = dataclasses.replace(fake.launch, core="normal")   # `auto` adds a note
    fake.runto_running = False
    fake.control_hits = 0
    got = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020", seconds=1))
    assert got["status"] == "ok" and got["verdict"] == "TARGET", got
    assert got["summary"] == "run_to 0000:0010: TARGET at 00A7:00000000, control counted 0", (
        got["summary"])
    assert "note" not in got, "a clean arrival says nothing more: no note"


def test_start_hands_the_callers_flags_to_a_headless_launch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    stub_build(monkeypatch)
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


def test_a_stop_reply_carries_its_own_number(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.step(mode="over"))
    assert got["stop_seq"] == dstate.STATE.last_stop["seq"], got
    again = cast(dict[str, Any], server.step(mode="over"))
    assert again["stop_seq"] == got["stop_seq"] + 1, again


@pytest.mark.parametrize(("mode", "paging", "want"), [
    ("Real", False, "real"), ("Real", None, "real"), ("Pr32", True, "paged"),
    ("Pr16", False, "protected"), ("Pr32", False, "protected"), ("Pr32", None, None)])
def test_status_names_the_cpu_mode_of_the_stop_it_is_in(
        tmp_path: Path, mode: str, paging: bool | None, want: str | None) -> None:
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


def test_status_does_not_name_a_stop_it_could_not_read_as_the_one_it_is_in(
        tmp_path: Path) -> None:
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


def test_a_recorded_stop_keeps_the_paging_mark_its_survey_read(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.paging = True   # what a paged stop survey leaves
    server.step(mode="over")
    assert dstate.STATE.last_stop["paging"] is True


def test_a_boot_whose_call_is_cancelled_stops_waiting_for_the_prompt(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

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


def test_a_log_rewritten_between_two_stops_is_counted_from_its_start(tmp_path: Path) -> None:
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
    fake = _names(tmp_path)
    fake.halted = True
    got = cast(dict[str, Any], server.resume(seconds=5))
    assert got["verdict"] == "OTHER_STOP" and "stop_seq" in got, got


def test_a_stop_whose_survey_came_back_cut_names_no_mode_off_the_stop_before(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Pr32")
    fake.paging = True   # the previous stop's mark
    fake.halted = True
    fake.registers_raises = True
    got = cast(dict[str, Any], server.resume())
    assert got["pc"] == f"{fake.cs}:{fake.eip}", got
    assert got["cpu_mode"]["available"] is False, got



def test_start_names_no_stop_of_its_own_beside_the_park(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The park after `start` is stop 1, the session's own: no stop "on its own" rides beside it."""
    got = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert got["status"] == "ok" and "stopped_on_its_own" not in got, sorted(got)


def test_the_instructions_families_are_the_registered_tools_and_the_running_ones_answer() -> None:
    assert dosbox_mcp.ROSTER.unlisted(dosbox_mcp.registered_tools()) == []
    answering = (sequence.GATE.listed(folds.METHODS)
                 | (checks.NOT_STEPS - {"start", "build_check"}))
    named = dosbox_mcp.ROSTER.answering_named() - {"registers(from_last_stop=True)"}
    assert named <= answering, sorted(named - answering)
    assert dosbox_mcp.ROSTER.running_sentence() in (server.mcp.instructions or "")


def test_an_arrival_is_attributed_to_run_tos_own_target_and_recorded_so(tmp_path: Path) -> None:
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


def test_a_protected_stop_in_another_selector_places_by_the_programs_own(
        tmp_path: Path) -> None:
    fake = _protected_table(tmp_path)
    fake.cs, fake.ds = "0018", "0020"
    bp = _ok(server.breakpoint_at(ref="_main"))
    assert bp["entry"].startswith("BP 00A7:"), bp


def test_a_stop_already_parked_is_heard_by_a_wait_of_no_seconds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_raises = True

    def parked() -> bool:
        fake.where_raises = False       # it had stopped before the first look
        return True

    monkeypatch.setattr(fake, "run_state", parked)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0))
    assert out["status"] == "ok" and out["steps_completed"] == 2, out


def test_a_stop_tool_s_drain_is_not_repeated_by_the_next_contact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import running
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
