"""What a `Session` method hands back, by the values a tool's reply carries: reads and writes
(their bounds, readback and refusals), the facts `state` gives every reply, the stop survey,
the boot wait and `step`, the argument checks a refusal names, a new session and its input
link, what a read of the terminal keeps, the breakpoint rows, the listings read off the log
(`listing`, `intvec`, `memdump`), the wait for a stop, and a frame's source. Each method runs
unbound against a double holding exactly what it reaches for."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scry_core.host_program import absolute as _abs
from test_dosbox_x_debug import REAL_PANE, Debugger
from test_dosbox_x_session import _writer

import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_launch as dlaunch
import dosbox_session as ds


def _row(seg: int, off: int, first: int = 0) -> str:
    return f"{seg:04X}:{off:08X} " + " ".join(f"{(first + i) & 0xFF:02X}" for i in range(16))


def _viewing(rows: list[str], sent: list[str] | None = None, alive: bool = True) -> Any:
    def command(text: str, settle: float = 0.6, timeout: float = 6.0) -> str:
        if sent is not None:
            sent.append(text)
        return "\n".join(rows)
    return SimpleNamespace(command=command, alive=lambda: alive,
                           where=lambda: {"mode": "Real"})


def test_a_read_is_of_the_address_asked_and_names_what_came_back_otherwise() -> None:
    sent: list[str] = []
    got = ds.Session.read_memory(_viewing([_row(0xF000, 0xE040)], sent), 0xF000, 0xE040)
    assert sent == ["D F000:E040"] and got[0].startswith("F000:0000E040"), (sent, got)
    with pytest.raises(ds.Invalid) as elsewhere:
        ds.Session.read_memory(_viewing([_row(0xF000, 0xE040)]), 0xF000, 0x0100)
    assert "F000:0000E040" in str(elsewhere.value), elsewhere.value
    for alive, said in ((True, "emulator running"), (False, "emulator GONE")):
        with pytest.raises(ds.Invalid) as nothing:
            ds.Session.read_memory(_viewing([], alive=alive), 0xF000, 0xE040)
        assert said in str(nothing.value), nothing.value


def test_a_row_painted_twice_is_kept_once_at_its_last_paint() -> None:
    a, b = _row(0x40, 0x00, 0x00), _row(0x40, 0x10, 0x00)       # both rows open with 00
    got = ds.Session.read_memory(_viewing([a, b, b, a]), 0x40, 0x00)
    assert [r.split()[0] for r in got] == ["0040:00000010", "0040:00000000"], got
    many = [_row(0x40, 16 * i, 0) for i in range(8)]
    assert len(ds.Session.read_memory(_viewing(many), 0x40, 0x00)) == 8


def test_a_value_the_view_does_not_cover_is_refused_and_the_view_bounds_a_read() -> None:
    one = SimpleNamespace(read_memory=lambda _s, _o, mode=None: [_row(0x749, 0)])
    with pytest.raises(ds.Invalid) as short:
        ds.Session.read_bytes(one, 0x749, 0, 32)  # type: ignore[arg-type]
    assert short.value.code == "unexpected_answer", short.value.code
    assert "did not cover all 32 bytes" in str(short.value) and "painted 16" in str(short.value)
    eight = SimpleNamespace(read_memory=lambda _s, _o, mode=None: [
        _row(0x749, 16 * i, 16 * i) for i in range(8)])
    assert len(ds.Session.read_bytes(eight, 0x749, 0, 128)) == 128  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="region"):
        ds.Session.read_bytes(eight, 0x749, 0, 129)  # type: ignore[arg-type]


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
    assert sent and sent[0].startswith("SM 00A7:C0000"), sent
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
                           _drainer=None, drain_ended="",
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
    hold = threading.Event()
    live = threading.Thread(target=hold.wait, daemon=True)
    live.start()
    fake = _stating(tmp_path, _drainer=live)
    got = ds.Session.state(fake)
    assert got["elapsed_s"] == 3.5 and isinstance(got["elapsed_s"], float), got
    assert got["drain_alive"] is True and "drain_ended" not in got, got
    assert got["state_dir"] == "the emulator's own save/ under its working directory", got
    fake.launch = dlaunch.Launch(conf=fake.launch.conf, cwd=tmp_path, seconds=60,
                                 state_dir=tmp_path / "st")
    assert ds.Session.state(fake)["state_dir"] == str(tmp_path / "st")
    hold.set()
    live.join(1)
    assert ds.Session.state(fake)["drain_alive"] is False


SURVEY = (Path(__file__).parent / "fixtures" / "trace" / "probe-settle-survey-before.txt"
          ).read_text(encoding="utf-8")


def test_a_stop_survey_keeps_its_own_screen_clock_and_cycles() -> None:
    s = SimpleNamespace(_survey=lambda: (SURVEY, dcons.parse_registers(SURVEY)),
                        breakpoints=lambda: [])
    where, _regs, _held = ds.Session.stop_survey(s)  # type: ignore[arg-type]
    assert where == dcons.where_from(SURVEY), where
    assert s.survey_text == SURVEY
    assert (s.pane_clock_ms, s.pane_cycles) == (dcons.parse_pane_clock(SURVEY),
                                                dcons.parse_pane_cycles(SURVEY))
    assert s.pane_clock_ms is not None and s.pane_cycles is not None


def _booting(prompt_after_s: float | None, said: list[str], exits: list[int | None]) -> Any:
    """A session whose debugger answers after `prompt_after_s` (None: never), whose terminal
    says `said` one chunk a read, and whose process answers `exits` one poll at a time."""
    began = time.monotonic()
    s = SimpleNamespace(_screen="", dropped=0, stopped=[])

    def read(_t: float) -> str:
        if prompt_after_s is not None and time.monotonic() - began >= prompt_after_s:
            s._screen = "\n" + dcons.PROMPT
        return said.pop(0) if said else ""
    s._read = read
    s._mark_stopped = lambda: s.stopped.append(True)
    s.proc = SimpleNamespace(poll=lambda: exits.pop(0) if len(exits) > 1 else exits[0])
    return s


def test_the_wait_for_the_prompt_says_how_long_it_took_and_where_it_is() -> None:
    took = ds.Session.wait_ready(_booting(0.45, [], [None]), 5)
    assert isinstance(took, float) and 0.4 < took < 1.5, took
    ticks: list[str] = []
    ds.Session.wait_ready(_booting(0.5, [], [None]), 5,
                          lambda *a: ticks.append(str(a[-1])))
    assert ticks == [], ticks
    ds.Session.wait_ready(_booting(2.6, [], [None]), 5,
                          lambda *a: ticks.append(str(a[-1])))
    assert 1 <= len(ticks) <= 3 and ticks[0].startswith(
        "start: waiting for the debugger prompt, 1s of 5s"), ticks


def test_an_emulator_that_exits_or_never_prompts_is_said_with_its_last_words() -> None:
    with pytest.raises(ds.Invalid) as exited:
        ds.Session.wait_ready(_booting(None, ["AAAA", "BBBB"], [None, 3]), 5)
    assert exited.value.code == "session_broken", exited.value.code
    said = str(exited.value)
    assert "exited with code 3" in said and said.endswith("said was 'AAAABBBB'"), said
    with pytest.raises(ds.Invalid) as silent:
        ds.Session.wait_ready(_booting(None, ["AAAA"], [None]), 0.3)
    assert silent.value.code == "session_broken", silent.value.code
    assert "did not appear within 0.3s" in str(silent.value)
    assert str(silent.value).endswith("'AAAA'"), silent.value


def test_a_written_register_hands_back_the_pane_it_was_read_from() -> None:
    pane = {"EAX": "00000000", "CS": "0050", "DS": "0040"}
    fake = SimpleNamespace(altered=False, command=lambda _text: "", registers=lambda: pane)
    assert ds.Session.set_register(fake, "cs", 0x50)["regs"] == pane  # type: ignore[arg-type]


def test_a_step_that_came_back_says_its_mode_that_it_is_not_running_and_how_it_read() -> None:
    dbg = Debugger([REAL_PANE, REAL_PANE])
    asked: list[dict[str, Any]] = []
    collect = dbg._collect

    def recorded(*a: Any, **k: Any) -> Any:
        asked.append(k)
        return collect(*a, **k)
    dbg._collect = recorded  # type: ignore[method-assign]
    got = ds.Session.step(dbg, mode="over", count=1)  # type: ignore[arg-type]
    assert got["running"] is False and got["mode"] == "over", got
    assert asked and all(k == {"settle": 0.4, "timeout": 6.0} for k in asked), asked


# ------------------------------------------------------------- what a check or a capture says

def test_a_riff_that_is_not_an_avi_and_an_avi_tag_with_no_riff_are_not_avis() -> None:
    assert ds.avi_facts(b"RIFF" + bytes(4) + b"WAVE" + bytes(30))["riff_avi"] is False
    assert ds.avi_facts(b"JUNK" + bytes(4) + b"AVI " + bytes(30))["riff_avi"] is False
    assert ds.avi_facts(b"RIFF" + bytes(4) + b"AVI " + bytes(30))["riff_avi"] is True


def test_the_step_and_register_checks_say_the_value_and_its_bound() -> None:
    with pytest.raises(ds.Invalid) as mode:
        ds.check_step("sideways", 1)
    assert mode.value.code == "bad_argument", mode.value.code
    said = str(mode.value)
    assert said.startswith("mode is one of ('over', 'into'); got 'sideways'"), said
    assert said.endswith(": `over` runs a CALL to its return, `into` follows it"), said
    for near in ("o", ""):
        with pytest.raises(ds.Invalid):
            ds.check_step(near, 1)
    with pytest.raises(ds.Invalid) as name:
        ds.check_register_name("bogus")
    assert str(name.value) == ("'bogus' is not a register this debugger sets. One of: "
                               + ", ".join(sorted(dcons.SETTABLE))), name.value
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
    ds.check_step("over", ds.STEP_MAX)
    for count in (0, ds.STEP_MAX + 1):
        with pytest.raises(ds.Invalid, match="a step count is 1 to"):
            ds.check_step("over", count)
    with pytest.raises(ds.Invalid) as dest:
        ds.check_frame_args(0, Path(_abs("x", "shot%03d.png")))
    assert "'/x/shot%03d.png'" in str(dest.value), dest.value


def test_a_gone_emulator_says_how_far_into_which_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    with pytest.raises(ds.Invalid) as gone:
        ds.gone_if_dead(SimpleNamespace(alive=lambda: False), 97.66, 5.04,  # type: ignore[arg-type]
                        "0814:0010")
    assert gone.value.code == "session_broken", gone.value.code
    assert "the emulator is GONE, 2.3s into a 5.0s wait for 0814:0010." in str(gone.value)


def test_a_survey_nudges_with_bplist_and_says_whether_the_emulator_lives() -> None:
    sent: list[str] = []

    def command(text: str, settle: float = 0.6, timeout: float = 6.0) -> str:
        sent.append(text)
        return ""
    for poll, said in ((lambda: 1, "(emulator GONE)"), (lambda: None, "(emulator running)")):
        s = ds.Session.__new__(ds.Session)
        s.command = command  # type: ignore[method-assign]
        s.proc = SimpleNamespace(poll=poll)  # type: ignore[assignment]
        s._drainer = None
        with pytest.raises(ds.NotStopped) as nothing:
            ds.Session._survey(s)
        assert said in str(nothing.value), nothing.value
    assert sent == ["BPLIST", "BPLIST"], sent


# ------------------------------------------------------------- a session as it is born

def test_a_new_session_starts_unaltered_unread_and_at_no_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import dosbox_process as dprocess
    monkeypatch.setattr(dprocess.Process, "_spawn", lambda self, launch: None)
    launch = _launch(tmp_path)
    ses = ds.Session(launch)
    # A pid no process holds, so nothing reached through it can signal a real one.
    ses.proc = SimpleNamespace(pid=999999, poll=lambda: None)  # type: ignore[assignment]
    assert ses.launch is launch and ses.conf_digest == dlaunch.digest(launch.conf)
    assert ses.altered is False and ses.stop_count == 0
    assert (ses.paging, ses.pane_clock_ms, ses.pane_cycles) == (None, None, None)
    assert ses.survey_text == "" and ses._screen == ses._pending == "" == ses._peek_carry
    assert ses._raw_tail == "" and ses._raw_reads == 0 and ses._avi_facts == {}
    facts = ses.state()
    assert isinstance(facts["elapsed_s"], float) and facts["altered"] is False, facts
    ses._mark_stopped()
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

def _drain(chunks: list[bytes]) -> Any:
    from test_dosbox_x_session import FakeDrain
    d = FakeDrain([])
    left = list(chunks)
    d._take = lambda: left.pop(0) if left else b""
    return d


def test_a_read_takes_what_the_drain_offers_and_keeps_its_screen(
        monkeypatch: pytest.MonkeyPatch) -> None:
    d = _drain([b"abc", b"def"])
    d.dropped = 5                                          # earlier losses are not this read's
    assert ds.Session._read(d, 0.0) == "abc"
    assert (d._raw_tail, d._raw_reads) == ("abc", 1)
    assert ds.Session._read(d, 0.0) == "def" and d._screen == "abcdef"
    d = _drain([b"ab\xffcd"])
    assert ds.Session._read(d, 0.0) == "ab�cd"
    d = _drain([b"EAX=1"])
    d._eof.set()
    began = time.monotonic()
    assert ds.Session._read(d, 0.3) == "EAX=1"
    assert time.monotonic() - began < 0.2, "a read at the end of the stream waited its slice out"
    monkeypatch.setattr(ds, "SCREEN_KEEP", 5)
    d = _drain([b"abcdefgh"])
    ds.Session._read(d, 0.0)
    assert d._screen == "defgh"


def test_an_unfinished_escape_is_held_up_to_its_bound_wherever_it_starts() -> None:
    d = _drain([b"x" * 5000 + b"\x1b[1;2"])
    assert ds.Session._read(d, 0.0) == "x" * 5000 and d._pending == "\x1b[1;2"
    whole = "\x1b]" + "x" * (ds.PENDING_MAX - 2)
    d = _drain([whole.encode()])
    ds.Session._read(d, 0.0)
    assert d._pending == whole
    d = _drain([(whole + "x").encode()])
    ds.Session._read(d, 0.0)
    assert d._pending == ""


def test_a_reply_gathers_every_chunk_and_an_escape_alone_keeps_it_open() -> None:
    from test_dosbox_x_session import _collected, _replaying
    got, _ = _collected([(0, "abc"), (0.1, "def")], settle=0.3)
    assert got == "abcdef", got
    ses = _replaying([(0, "abc"), (0.2, "\x1b[1m"), (0.4, "\x1b[2m"), (0.55, "def")])
    assert ses._collect(0.3, 3.0) == "abcdef"


def test_a_key_written_releases_the_machine(tmp_path: Path) -> None:
    import os
    r, w = os.pipe()
    try:
        s = ds.Session.__new__(ds.Session)
        s._master = w
        seen: list[bytes] = []
        s._release = seen.append  # type: ignore[method-assign,assignment]
        ds.Session._write(s, b"x\r")
        assert seen == [b"x\r"] and os.read(r, 8) == b"x\r"
    finally:
        os.close(r)
        os.close(w)


# ------------------------------------------------------------- the breakpoint rows

def _listing(tmp_path: Path, lists: list[list[dict[str, str]]], mode: str = "Pr32") -> Any:
    sent: list[str] = []

    def command(text: str, **_: Any) -> str:
        sent.append(text)
        return ""
    return SimpleNamespace(launch=_launch(tmp_path),
                           where=lambda: {"cs": "00A7", "eip": "0", "mode": mode},
                           command=command, sent=sent, alive=lambda: True, altered=False,
                           breakpoints=lambda: list(lists.pop(0) if len(lists) > 1
                                                    else lists[0]))


def test_an_armed_code_row_is_sent_read_back_and_handed_back_with_the_list(
        tmp_path: Path) -> None:
    held = [{"index": "00", "entry": "BP 00A7:0100"}]
    s = _listing(tmp_path, [held])
    got = ds.Session.arm_code_breakpoint(s, 0x00A7, 0x100)
    assert s.sent == ["BP 00A7:0100"], s.sent
    assert (got["target"], got["breakpoints"]) == ("00A7:0100", held), got
    other = [{"index": "00", "entry": "BP 00A7:0200"}]
    with pytest.raises(ds.Invalid) as missing:
        ds.Session.arm_code_breakpoint(_listing(tmp_path, [other]), 0x00A7, 0x100)
    assert "['BP 00A7:0200']" in str(missing.value), missing.value


def test_a_clear_deletes_by_index_and_says_removed_only_when_the_row_is_gone(
        tmp_path: Path) -> None:
    absent = ds.Session.clear_code_breakpoint(_listing(tmp_path, [[]]), 0x00A7, 0x16DD80)
    assert absent["entry"] == "BP 00A7:16DD80" and absent["removed"] is False, absent
    row = {"index": "03", "entry": "BP 00A7:0100"}
    other = {"index": "00", "entry": "BP 00A7:0200"}
    s = _listing(tmp_path, [[other, row], [other]])
    gone = ds.Session.clear_code_breakpoint(s, 0x00A7, 0x100)
    assert s.sent == ["BPDEL 03"] and gone["removed"] is True, (s.sent, gone)
    stays = ds.Session.clear_code_breakpoint(_listing(tmp_path, [[row], [row]]), 0x00A7, 0x100)
    assert stays["removed"] is False, stays
    no_int = ds.Session.clear_interrupt_breakpoint(_listing(tmp_path, [[]]), 0x31, 0x05)
    assert no_int["entry"] == "BPINT 31 AH=05", no_int


# ------------------------------------------------------------- a listing off the logfile

def _lister(tmp_path: Path, write: bytes | None, reply: str = "I-> _",
            truncate_to: int | None = None) -> Any:
    log = tmp_path / "e9.log"

    def command(text: str, **_: Any) -> str:
        if write is not None:
            with log.open("ab") as f:
                f.write(write)
        if truncate_to is not None:
            log.write_bytes(log.read_bytes()[:truncate_to])
        return reply
    return SimpleNamespace(launch=_launch(tmp_path, logfile=log), command=command)


def test_a_listing_is_what_the_command_appended_to_the_log(tmp_path: Path) -> None:
    assert ds.Session.listing(_lister(tmp_path, b"ROWS\n"), "GDT") == "ROWS\n"
    (tmp_path / "e9.log").write_bytes(b"0123456789")
    assert ds.Session.listing(_lister(tmp_path, None), "GDT") == ""
    with pytest.raises(ds.Invalid) as shrank:
        ds.Session.listing(_lister(tmp_path, None, truncate_to=9), "GDT")
    assert "shrank from 10 to 9" in str(shrank.value), shrank.value
    (tmp_path / "e9.log").unlink()
    with pytest.raises(ds.Invalid) as nothing:
        ds.Session.listing(_lister(tmp_path, None), "GDT")
    assert nothing.value.code == "no_channel" and "left nothing to read" in str(nothing.value)
    tail = "y" * 300
    with pytest.raises(ds.Invalid) as no_prompt:
        ds.Session.listing(_lister(tmp_path, b"", reply=tail), "GDT")
    assert repr(tail[-200:]) in str(no_prompt.value), no_prompt.value


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

class _Clocked:
    """A session `await_stop` listens on, with a clock its reads advance: each read takes its
    slice (or a twentieth of a second for a look), hands back the next text, and a hundred
    reads end the test rather than hang it."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, texts: list[str],
                 alive: bool = True) -> None:
        self.now = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: self.now)
        self.texts, self._alive = list(texts), alive
        self._peek_carry = ""
        self.slices: list[float] = []
        self.stopped = 0

    def _read(self, seconds: float) -> str:
        self.slices.append(seconds)
        assert len(self.slices) < 100, "the wait never ended"
        self.now += seconds or 0.05
        return self.texts.pop(0) if self.texts else ""

    def alive(self) -> bool:
        return self._alive

    def _mark_stopped(self) -> None:
        self.stopped += 1


def test_a_wait_reports_its_progress_on_its_tick_in_its_own_words(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.4)
    s = _Clocked(monkeypatch, [])
    said: list[tuple[float, Any, str]] = []
    expired, _ = ds.Session.await_stop(s, 100.0, 101.25, "T",  # type: ignore[arg-type]
                                       lambda *a: said.append(a))
    assert expired is True
    assert said == [(0.5, None, "run_to T: running 0s of 1.25s"),
                    (1.0, None, "run_to T: running 1s of 1.25s")], said
    assert all(x == 0.25 for x in s.slices), s.slices


def test_a_spent_bound_looks_once_only_when_asked_and_without_blocking(
        monkeypatch: pytest.MonkeyPatch) -> None:
    s = _Clocked(monkeypatch, ["\n" + dcons.PROMPT])
    assert ds.Session.await_stop(s, 100.0, 100.0, "T") == (True, 0.0)  # type: ignore[arg-type]
    assert s.slices == [] and s.stopped == 0
    expired, _ = ds.Session.await_stop(s, 100.0, 100.0, "T",  # type: ignore[arg-type]
                                       look_once=True)
    assert expired is False and s.slices == [0.0] and s.stopped == 1


def test_a_stop_is_heard_from_a_repaint_or_a_prompt_split_across_reads(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from test_dosbox_x_debug import REAL_PANE
    pane = "\n".join(ln for ln in REAL_PANE.splitlines() if dcons.PROMPT not in ln)
    s = _Clocked(monkeypatch, ["", pane])
    expired, _ = ds.Session.await_stop(s, 100.0, 110.0, "T")  # type: ignore[arg-type]
    assert expired is False and s.stopped == 0 and len(s.slices) == 2
    half = len(dcons.PROMPT) // 2
    s = _Clocked(monkeypatch, ["..." + dcons.PROMPT[:half], dcons.PROMPT[half:]])
    expired, _ = ds.Session.await_stop(s, 100.0, 110.0, "T")  # type: ignore[arg-type]
    assert expired is False and s.stopped == 1 and len(s.slices) == 2


def test_a_wait_on_a_dead_emulator_names_its_bound_and_target(
        monkeypatch: pytest.MonkeyPatch) -> None:
    s = _Clocked(monkeypatch, [], alive=False)
    with pytest.raises(ds.Invalid) as gone:
        ds.Session.await_stop(s, 100.0, 105.04, "0814:0010")  # type: ignore[arg-type]
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
    emulator, _ = ds.Session._e9_since(s, 0, "emulator")  # type: ignore[arg-type]
    assert any("CONFIG" in ln for ln in emulator), emulator
    guest, _ = ds.Session._e9_since(s, 0)  # type: ignore[arg-type]
    assert not any("CONFIG" in ln for ln in guest), guest
