"""What a `Session` method hands back, by the values a tool's reply carries: reads and writes
(their bounds, readback and refusals), the facts `state` gives every reply, the stop survey,
the boot wait and `step`, the argument checks a refusal names, a new session and its input
link, what a read of the terminal keeps, the breakpoint rows, the listings read off the log
(`listing`, `intvec`, `memdump`), the wait for a stop, and a frame's source. Each method runs
unbound against a double holding exactly what it reaches for."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from channel_double import Machine, Stop, protected, session_over
from dosbox_x_server_support import CASED_PATHS
from scry_core.host_program import absolute as _abs
from test_dosbox_x_session import _writer

from scry_dosbox_x import collect as dcollect
from scry_dosbox_x import grammar, run_state, stepping
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import session as ds


def _writing(mode: str = "Real") -> tuple[Any, list[str], list[tuple[Any, ...]]]:
    asked: list[tuple[Any, ...]] = []
    s, sent = _writer({"held": bytes(16)}, mode, asked)
    return s, sent, asked


def test_a_write_one_byte_past_the_segment_is_refused_saying_where_it_would_end() -> None:
    s, sent, _ = _writing()
    with pytest.raises(ds.Invalid) as past:
        ds.Session.write_memory(s, 0x40, 0xFFFF, b"\x00\x00")
    assert "last byte" in str(past.value) and "0x10000" in str(past.value) and sent == []


def test_the_rom_guard_is_real_modes_and_judges_the_linear_range() -> None:
    s, sent, asked = _writing("Pr32")
    ds.Session.write_memory(s, 0x00A7, 0xC0000, b"\x01")
    assert sent and sent[0].startswith("SM 00A7:0C0000"), sent
    s, sent, asked = _writing()
    ds.Session.write_memory(s, 0xFFFF, 0x0010, b"\x01")            # linear 0x100000, past ROM
    assert sent and asked == [(0xFFFF, 0x0010, 1, "Real")], (sent, asked)
    for seg, off in ((0xF000, 0xE05B), (0xF000, 0xFFFF)):
        s, sent, _ = _writing()
        with pytest.raises(ds.Invalid) as rom:
            ds.Session.write_memory(s, seg, off, b"\x99")
        said = str(rom.value)
        assert "ENDS the emulator" in said and "0xC0000-0xFFFFF" in said and sent == [], said
        assert f"linear 0x{seg * 16 + off:X}" in said, said
    s, sent, _ = _writing()
    with pytest.raises(ds.Invalid, match="ENDS the emulator"):         # 0xBFFFF..0xC0000
        ds.Session.write_memory(s, 0xBFFF, 0x000F, b"\x01\x02")
    assert sent == []
    s, sent, _ = _writing()
    ds.Session.write_memory(s, 0xBFFF, 0x000E, b"\x01\x02")           # ends at 0xBFFFF
    assert sent, "a write that ends under the ROM was refused"


def _launch(tmp_path: Path, **kw: Any) -> dlaunch.Launch:
    """A launch over a conf written in `tmp_path`, as the doubles here carry one."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    return dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, **kw)


def _stating(tmp_path: Path, **kw: Any) -> Any:
    fake = SimpleNamespace(proc=SimpleNamespace(pid=4242), alive=lambda: True, altered=False,
                           conf_digest="x", started_at=100.0, dropped=0, _at_debugger=False,
                           launch=_launch(tmp_path))
    for k, v in kw.items():
        setattr(fake, k, v)
    return fake


@pytest.mark.parametrize(("alive", "at_debugger", "running"), [
    (True, False, True), (True, True, False), (False, False, False)])
def test_running_is_alive_and_not_at_the_debugger(
        tmp_path: Path, alive: bool, at_debugger: bool, running: bool) -> None:
    fake = _stating(tmp_path, _at_debugger=at_debugger, alive=lambda: alive)
    assert ds.Session.state(fake)["running"] is running


def test_the_session_facts_round_the_elapsed_time_and_name_the_drain_and_state_dir(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 103.46)
    fake = _stating(tmp_path)
    got = ds.Session.state(fake)
    assert got["elapsed_s"] == 3.5 and isinstance(got["elapsed_s"], float), got
    assert got["output_bytes_dropped"] == 0, got
    assert got["state_dir"] == str(fake.launch.cwd / dlaunch.DEFAULT_STATE_SUBDIR), got
    fake.launch = dlaunch.Launch(conf=fake.launch.conf, cwd=tmp_path, seconds=60,
                                 state_dir=tmp_path / "st")
    assert ds.Session.state(fake)["state_dir"] == str(tmp_path / "st")


def _booting(tmp_path: Path, stopped_after_polls: int | None, exits: list[int | None],
             commands: tuple[str, ...] = ("RUNSTATE",)) -> tuple[ds.Session, Machine]:
    """A session whose debugger says stopped at its `stopped_after_polls`th `RUNSTATE` (None:
    never) and whose process answers `exits` one poll at a time."""
    machine = Machine(stopped=False, commands=commands,
                      releases=[], then=None)
    s = session_over(machine, tmp_path)
    polls = {"n": 0}

    def runstate(_c: str) -> tuple[bool, list[str]] | None:
        polls["n"] += 1
        if stopped_after_polls is not None and polls["n"] > stopped_after_polls:
            machine.stopped = True
        return None
    machine.hooks["RUNSTATE"] = runstate
    s.proc = SimpleNamespace(poll=lambda: exits.pop(0) if len(exits) > 1 else exits[0],
                             pid=1)  # type: ignore[assignment]
    s.output_tail = lambda chars: "AAAABBBB"  # type: ignore[method-assign]
    return s, machine


def test_the_wait_for_the_prompt_says_how_long_it_took_and_where_it_is(tmp_path: Path) -> None:
    s, _ = _booting(tmp_path, 3, [None])
    took = s.wait_ready(5)
    assert isinstance(took, float) and took < 1.0 and s.at_debugger() and s.stop_count == 1
    ticks: list[str] = []
    slow, _ = _booting(tmp_path, 25, [None])
    slow.wait_ready(5, lambda *a: ticks.append(str(a[-1])))
    assert ticks == [] or ticks[0].startswith("start: waiting for the debugger, "), ticks


def test_an_emulator_that_exits_or_never_prompts_is_said_with_its_last_words(
        tmp_path: Path) -> None:
    s, _ = _booting(tmp_path, None, [None, 3])
    with pytest.raises(ds.Invalid) as exited:
        s.wait_ready(5)
    assert exited.value.code == "session_broken", exited.value.code
    said = str(exited.value)
    assert "exited with code 3" in said and said.endswith("printed was 'AAAABBBB'"), said
    killed, _ = _booting(tmp_path, None, [None, -11])
    with pytest.raises(ds.Invalid) as signalled:
        killed.wait_ready(5)
    assert "died by signal 11" in str(signalled.value), signalled.value
    silent, _ = _booting(tmp_path, None, [None])
    with pytest.raises(ds.Invalid) as never:
        silent.wait_ready(0.3)
    assert never.value.code == "session_broken", never.value.code
    assert "did not answer stopped within 0.3s" in str(never.value)


def test_a_written_register_hands_back_the_reading_it_was_read_from(tmp_path: Path) -> None:
    s = session_over(Machine(), tmp_path)
    got = s.set_register("cs", 0x50)
    assert got["regs"] == s.registers() and got["regs"]["CS"] == "0050", got


def test_a_start_with_no_runstate_is_held_by_a_break_and_refused_when_the_debugger_cannot(
        tmp_path: Path) -> None:
    s, machine = _booting(tmp_path, None, [None], commands=())
    assert isinstance(s.wait_ready(5), float) and machine.sent == ["BREAK"], machine.sent
    blind, machine = _booting(tmp_path, None, [None], commands=())
    machine.request = lambda command, *a, **k: (True, [  # type: ignore[method-assign]
        "Debugger in Mac OS X is not available unless you start DOSBox-X from a terminal"])
    with pytest.raises(ds.Invalid, match="cannot stop this machine") as caught:
        blind.wait_ready(5)
    assert caught.value.code == "session_broken"


def test_a_step_that_came_back_says_its_mode_that_it_is_not_running_and_how_it_read(
        tmp_path: Path) -> None:
    machine = Machine(steps=[{"EIP": 0x131}])
    got = cast(dict[str, Any], session_over(machine, tmp_path).step(mode="into", count=1))
    assert got["running"] is False and got["mode"] == "into", got
    assert got["before"]["eip"] == "00000130" and got["after"]["eip"] == "00000131", got


# ------------------------------------------------------------- what a check or a capture says

def test_a_riff_that_is_not_an_avi_and_an_avi_tag_with_no_riff_are_not_avis() -> None:
    assert ds.avi_facts(b"RIFF" + bytes(4) + b"WAVE" + bytes(30))["riff_avi"] is False
    assert ds.avi_facts(b"JUNK" + bytes(4) + b"AVI " + bytes(30))["riff_avi"] is False
    assert ds.avi_facts(b"RIFF" + bytes(4) + b"AVI " + bytes(30))["riff_avi"] is True


def test_the_step_and_register_checks_say_the_value_and_its_bound() -> None:
    with pytest.raises(ds.Invalid) as mode:
        stepping.check_step("sideways", 1)
    assert mode.value.code == "bad_argument", mode.value.code
    said = str(mode.value)
    assert said.startswith("mode is one of ('over', 'into'); got 'sideways'"), said
    assert said.endswith(": `over` runs a CALL to its return, `into` follows it"), said
    for near in ("o", ""):
        with pytest.raises(ds.Invalid):
            stepping.check_step(near, 1)
    with pytest.raises(ds.Invalid) as name:
        ds.check_register_name("bogus")
    assert str(name.value) == ("'bogus' is not a register this debugger sets. One of: "
                               + ", ".join(sorted(grammar.SETTABLE))), name.value
    for key, value, said in (
            ("ax", -1, "value=-1 is negative: ax holds 16 bits, 0 to 0xffff; nothing was sent"),
            ("eax", -1, "0 to 0xffffffff"),
            ("ax", 0x10000,
             "value=0x10000 is wider than ax's 16 bits (at most 0xffff): nothing was sent"),
            ("eax", 1 << 32, "wider than eax's 32 bits (at most 0xffffffff)")):
        with pytest.raises(ds.Invalid) as wrong:
            ds.check_register_value(key, value)
        assert said in str(wrong.value), wrong.value
    ds.check_register_value("ax", 0xFFFF)                     # the widest value each takes
    ds.check_register_value("eax", 0xFFFFFFFF)
    stepping.check_step("over", stepping.STEP_MAX)
    for count in (0, stepping.STEP_MAX + 1):
        with pytest.raises(ds.Invalid, match="a step count is 1 to"):
            stepping.check_step("over", count)
    with pytest.raises(ds.Invalid) as dest:
        ds.check_frame_args(0, Path(_abs("x", "shot%03d.png")))
    assert repr(_abs("x", "shot%03d.png")) in str(dest.value), dest.value


def test_a_gone_emulator_says_how_far_into_which_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    with pytest.raises(ds.Invalid) as gone:
        ds.gone_if_dead(SimpleNamespace(alive=lambda: False), 97.66, 5.04,  # type: ignore[arg-type]
                        "0814:0010")
    assert gone.value.code == "session_broken", gone.value.code
    assert "the emulator is GONE, 2.3s into a 5.0s wait for 0814:0010." in str(gone.value)


# ------------------------------------------------------------- a session as it is born

def test_a_new_session_starts_unaltered_unread_and_at_no_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import process as dprocess
    monkeypatch.setattr(dprocess.Process, "_spawn", lambda self, launch: None)
    launch = _launch(tmp_path)
    ses = ds.Session(launch)
    # A pid no process holds, so nothing reached through it can signal a real one.
    ses.proc = SimpleNamespace(pid=999999, poll=lambda: None)  # type: ignore[assignment]
    assert ses.launch is launch and ses.conf_digest == dlaunch.digest(launch.conf)
    assert ses.altered is False and ses.stop_count == 0 and ses.commands == frozenset()
    assert (ses.paging, ses.clock_ms, ses.cycles) == (None, None, None)
    assert ses._surveyed is None and ses._avi_facts == {}
    facts = ses.state()
    assert isinstance(facts["elapsed_s"], float) and facts["altered"] is False, facts
    ses.mark_stopped()
    assert ses.stop_count == 1


def test_a_link_writes_to_the_input_socket_and_asks_the_session_whether_it_is_parked(
        tmp_path: Path) -> None:
    import socket as sock
    a, b = sock.socketpair()
    try:
        ses = ds.Session.__new__(ds.Session)
        parked = [True]
        ses.at_debugger = lambda: parked[0]  # type: ignore[method-assign]
        link = ds.Session._linked(ses, a)
        assert link.sock is a and link.parked() is True
        parked[0] = False
        assert link.parked() is False
    finally:
        a.close()
        b.close()


# ------------------------------------------------------------- what a read gives back


# ------------------------------------------------------------- the breakpoint rows


def test_an_armed_code_row_is_sent_read_back_and_handed_back_with_the_list(
        tmp_path: Path) -> None:
    machine = protected(Machine())
    got = session_over(machine, tmp_path).arm_code_breakpoint(0x00A7, 0x100)
    assert "EXEC BP 00A7:0100" in machine.sent, machine.sent
    assert (got["target"], got["breakpoints"]) == (
        "00A7:0100", [{"index": "00", "entry": "BP 00A7:0100"}]), got
    other = protected(Machine(breakpoints=["BP 00A7:0200"]))
    other.hooks["BP"] = lambda _c: (True, ["DEBUG: Set breakpoint at 00A7:0100"])
    with pytest.raises(ds.Invalid) as missing:
        session_over(other, tmp_path).arm_code_breakpoint(0x00A7, 0x100)
    assert "['BP 00A7:0200']" in str(missing.value), missing.value


def test_a_clear_deletes_by_index_and_says_removed_only_when_the_row_is_gone(
        tmp_path: Path) -> None:
    absent = session_over(protected(Machine()), tmp_path).clear_code_breakpoint(0x00A7,
                                                                                0x16DD80)
    assert absent["entry"] == "BP 00A7:16DD80" and absent["removed"] is False, absent
    machine = protected(Machine(breakpoints=["BP 00A7:0200", "BP 00A7:0100"]))
    gone = session_over(machine, tmp_path).clear_code_breakpoint(0x00A7, 0x100)
    assert "EXEC BPDEL 01" in machine.sent and gone["removed"] is True, (machine.sent, gone)
    assert machine.breakpoints == ["BP 00A7:0200"]
    stays = protected(Machine(breakpoints=["BP 00A7:0100"]))
    stays.hooks["BPDEL"] = lambda _c: (True, ["DEBUG: Breakpoint deletion failure."])
    assert session_over(stays, tmp_path).clear_code_breakpoint(0x00A7, 0x100)["removed"] \
        is False
    no_int = session_over(Machine(), tmp_path).clear_interrupt_breakpoint(0x31, 0x05)
    assert no_int["entry"] == "BPINT 31 AH=05", no_int


def test_a_listing_is_what_the_command_printed_whole(tmp_path: Path) -> None:
    machine = Machine()
    machine.hooks["GDT"] = lambda _c: (True, ["GDT Base:000D16FE Limit:00000087", "0000: b"])
    s = session_over(machine, tmp_path)
    assert s.listing("GDT") == "GDT Base:000D16FE Limit:00000087\n0000: b"
    machine.hooks["PAGING"] = lambda _c: (True, [])
    assert s.listing("PAGING") == ""


# ------------------------------------------------------------- a listing off the logfile


def _vectoring(tmp_path: Path, writes: bool, said: str) -> Any:
    def command(text: str, **_: Any) -> str:
        if writes:
            (tmp_path / ds.INTVEC_FILE).write_bytes(b"\x00" * 4)
        return said
    return SimpleNamespace(launch=SimpleNamespace(cwd=tmp_path), command=command)


def test_a_vector_table_the_debugger_did_not_write_whole_quotes_what_it_showed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    said = "z" * 400
    with pytest.raises(ds.Invalid) as unwritten:
        ds.Session.intvec(_vectoring(tmp_path, False, said))
    assert repr(said[-300:]) in str(unwritten.value), unwritten.value
    with pytest.raises(ds.Invalid) as unsaid:
        ds.Session.intvec(_vectoring(tmp_path, True, said))
    assert repr(said[-300:]) in str(unsaid.value), unsaid.value
    asked: list[list[Path]] = []

    def refused(names: list[Path], what: str) -> None:
        asked.append(list(names))
        raise ds.Invalid("bad_argument", "left over")
    monkeypatch.setattr(dcollect, "refuse_leftover", refused)
    with pytest.raises(ds.Invalid):
        ds.Session.intvec(_vectoring(tmp_path, False, said))
    assert asked == [[tmp_path / ds.INTVEC_FILE, tmp_path / ds.INTVEC_FILE.lower()]], asked


# ------------------------------------------------------------- a dump and what it leaves

def _dumper(tmp_path: Path, said: str, writes: bool, sub: str = "out") -> Any:
    (tmp_path / sub).mkdir(exist_ok=True)
    cands = [tmp_path / ds.MEMDUMP_NAME, tmp_path / ds.MEMDUMP_NAME.upper()]

    def command(text: str, **_: Any) -> str:
        if writes:
            cands[0].write_bytes(b"\xAB" * 16)
        return said
    return SimpleNamespace(launch=_launch(tmp_path),
                           command=command, _memdump_candidates=lambda: list(cands))


@CASED_PATHS
def test_a_dump_refusal_names_dest_and_quotes_what_the_debugger_showed(
        tmp_path: Path) -> None:
    there = tmp_path / "out" / "d.bin"
    s = _dumper(tmp_path, f"DEBUG: {ds.MEMDUMP_OK}.", True)
    there.write_bytes(b"mine")
    with pytest.raises(ds.Invalid) as taken:
        ds.Session.memdump(s, 0, 0, 16, there)
    assert str(taken.value).startswith("dest:"), taken.value
    there.unlink()
    said = "q" * 400
    with pytest.raises(ds.Invalid) as unsaid:
        ds.Session.memdump(_dumper(tmp_path, said, False), 0, 0, 16, there)
    assert repr(said[-300:]) in str(unsaid.value), unsaid.value
    with pytest.raises(ds.Invalid) as nowhere:
        ds.Session.memdump(_dumper(tmp_path, f"DEBUG: {ds.MEMDUMP_OK}.", False), 0, 0, 16,
                           there)
    assert nowhere.value.code == "unexpected_answer" and "none of" in str(nowhere.value)
    assert str(tmp_path / ds.MEMDUMP_NAME) in str(nowhere.value), nowhere.value


@CASED_PATHS
def test_a_dump_the_host_could_not_place_says_whether_its_file_was_removed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(*_: Any) -> Path:
        raise ds.Invalid("host_failed", "could not move it")
    monkeypatch.setattr(dcollect, "collect", failed)
    dest = tmp_path / "out" / "d.bin"
    s = _dumper(tmp_path, f"DEBUG: {ds.MEMDUMP_OK}.", True)
    with pytest.raises(ds.Invalid) as removed:
        ds.Session.memdump(s, 0, 0, 16, dest)
    assert str(removed.value).endswith(
        "That file was removed, so the next dump is not refused over it"), removed.value
    real_unlink = Path.unlink

    def stuck(self: Path, missing_ok: bool = False) -> None:
        if self.name.lower() == ds.MEMDUMP_NAME.lower():
            raise PermissionError(13, "Permission denied")
        real_unlink(self, missing_ok)

    def unknown(self: Path, other: Any) -> bool:
        raise OSError("cannot tell")
    s = _dumper(tmp_path, f"DEBUG: {ds.MEMDUMP_OK}.", True)
    with monkeypatch.context() as stuck_here:
        stuck_here.setattr(Path, "unlink", stuck)
        stuck_here.setattr(Path, "samefile", unknown)
        with pytest.raises(ds.Invalid) as kept:
            ds.Session.memdump(s, 0, 0, 16, dest)
    for c in (tmp_path / ds.MEMDUMP_NAME, tmp_path / ds.MEMDUMP_NAME.upper()):
        assert str(c) in str(kept.value), kept.value
    assert "could not be removed" in str(kept.value)
    (tmp_path / ds.MEMDUMP_NAME).unlink(missing_ok=True)


# ------------------------------------------------------------- listening for a stop


def test_a_wait_reports_its_progress_on_its_tick_in_its_own_words(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_state, "PROGRESS_EVERY_S", 0.04)
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path)
    s.release("RUN")
    said: list[tuple[float, Any, str]] = []
    began = time.monotonic()
    expired, _ = s.await_stop(began, began + 0.13, "T", lambda *a: said.append(a))
    assert expired is True and said, said
    assert all(m.startswith("run_to T: running ") and m.endswith("s of 0.13s")
               for _, _, m in said), said


def test_a_spent_bound_looks_once_only_when_asked_and_without_blocking(tmp_path: Path) -> None:
    machine = Machine(releases=[Stop()])
    s = session_over(machine, tmp_path)
    s.release("RUN")
    asked = len(machine.sent)
    assert s.await_stop(100.0, 100.0, "T") == (True, 0.0)
    assert len(machine.sent) == asked, "a spent bound asked the debugger"
    expired, _ = s.await_stop(time.monotonic(), time.monotonic(), "T", look_once=True)
    assert expired is False and machine.sent[asked:] == ["EXEC RUNSTATE"]


def test_a_wait_on_a_dead_emulator_names_its_bound_and_target(tmp_path: Path) -> None:
    machine = Machine(releases=[None])
    s = session_over(machine, tmp_path, alive=lambda: False)
    s.release("RUN")
    began = time.monotonic()
    with pytest.raises(ds.Invalid) as gone:
        s.await_stop(began, began + 5.04, "0814:0010")
    assert "a 5.0s wait for 0814:0010" in str(gone.value), gone.value


def test_a_frame_is_taken_from_the_capture_the_caller_named(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    import subprocess
    ran: list[list[str]] = []

    def record_run(argv: list[str], **_k: object) -> SimpleNamespace:
        ran.append(argv)
        return SimpleNamespace(returncode=1, stdout="", stderr="no")
    monkeypatch.setattr(shutil, "which", lambda name: _abs("usr", "bin", "ffmpeg"))
    monkeypatch.setattr(subprocess, "run", record_run)
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    other = tmp_path / "other.avi"
    with pytest.raises(ds.Invalid):
        ds.Session.frame(fake, 0, tmp_path / "o.png", source=other)  # type: ignore[arg-type]
    assert ran and ran[0][ran[0].index("-i") + 1] == str(other), ran


def test_a_register_the_selector_cannot_read_is_refused_naming_it() -> None:
    s = ds.Session.__new__(ds.Session)
    with pytest.raises(ds.Invalid) as wrong:
        ds.Session.selector(s, "XX")
    assert "got 'XX'" in str(wrong.value), wrong.value


def test_the_emulator_channel_is_read_as_asked_and_not_as_the_guest(tmp_path: Path) -> None:
    log = tmp_path / "e9.log"
    log.write_text("CONFIG:Loading primary settings\n"
                   "Bochs port E9h: [+   0.000] BOOT  . start\n", encoding="utf-8")
    s = SimpleNamespace(launch=SimpleNamespace(logfile=log))
    emulator, _ = ds.Session.e9_since(s, 0, "emulator")  # type: ignore[arg-type]
    assert any("CONFIG" in ln for ln in emulator), emulator
    guest, _ = ds.Session.e9_since(s, 0)  # type: ignore[arg-type]
    assert not any("CONFIG" in ln for ln in guest), guest
