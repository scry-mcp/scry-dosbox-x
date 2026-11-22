"""One live case per tool, driven through the server as an MCP caller drives it.

A tool with no live case is a tool whose green means nothing: fakes put files and replies
wherever the fake says (a `memdump` collecting from the wrong directory passed every
contract test). The population comes from the MCP registry, gated by
`test_every_tool_has_a_live_case_naming_it`. Each case asserts the tool's own guarantee,
never merely that it returned.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from scry_core import guardian, prose
from scry_core import window as core_window
from test_dosbox_x_live import (  # noqa: E402
    _OWN,
    CONF,
    CWD,
    GUEST_LATE,
    GUEST_MARK,
    GUEST_PROGRAM,
    LIVE_MARKS,
    conf_that_does_not_exit,
)

from scry_dosbox_x import binary as binaries
from scry_dosbox_x import grammar, machine, server
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import mcp as dosbox_mcp
from scry_dosbox_x import process as dprocess
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

pytestmark = LIVE_MARKS

# A ceiling, not a sleep: every wait polls and leaves as soon as its property holds.
GUEST_WAIT = 45.0

# The server's own caps for `_delta`: a case comparing a reply only with itself cannot fail.
DEBUG_CAP = 4000
SMALL_CAP = 2000


def start_ok(**kw: Any) -> dict[str, Any]:
    """`start` with this fixture's conf, REFUSING to continue if it did not come up."""
    reply = cast(dict[str, Any], server.start(conf=CONF or "", cwd=CWD, **kw))
    assert reply["status"] == "ok", reply
    return reply


def wait_for(predicate: Any, seconds: float = GUEST_WAIT) -> bool:
    """Poll until it holds or the ceiling is reached."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return False


def a_running_guest_that_has_logged(tmp_path: Path, seconds: int = 120,
                                    lines: int = 6) -> None:
    """Start with a log, release the guest until close (headless, nothing armed:"""
    log = tmp_path / "guest.log"
    start_ok(session_seconds=seconds, logfile=str(log))
    server.resume()
    assert wait_for(lambda: log.exists() and dlogs.count_e9(
        log.read_text(encoding="utf-8", errors="replace")) >= lines), \
        "the guest emitted no instrumentation: this window measured nothing, INVALID"


def test_build_check_answers_about_this_build_and_names_the_whole_surface() -> None:
    """The one tool whose job is examining preconditions, asked of the real binary."""
    reply = cast(dict[str, Any], server.build_check())
    assert reply["status"] == "ok", reply
    assert reply["debugger"] is True
    assert Path(str(reply["binary"])).is_file()
    assert set(reply["tools"]) == set(dosbox_mcp.registered_tools())
    assert reply["session"] == {"alive": False, "running": False, "altered": False}


def test_start_headless_reaches_the_debugger_and_declares_what_it_launched() -> None:
    """A run that cannot say which run it was is not attributable to anything."""
    reply = start_ok(session_seconds=60)
    argv = cast(list[str], reply["argv"])
    assert reply.get("shared", False) is False
    assert "-break-start" in argv
    assert argv[argv.index("-time-limit") + 1] == "60"
    assert argv[argv.index("sdl videodriver=dummy") - 1] == "-set"
    assert cast(float, reply["ready_after_s"]) > 0
    assert reply["session"]["alive"] is True and reply.get("watched", False) is False, reply


@pytest.mark.windowed
def test_start_shared_asks_for_the_display_and_adds_no_dummy_driver() -> None:
    """The WATCHED path, on the real emulator, bounded to seconds."""
    reply = start_ok(session_seconds=30, shared=True, display=0)
    argv = cast(list[str], reply["argv"])
    assert reply.get("shared", False) is True
    assert "sdl videodriver=dummy" not in argv, "a watched session was forced headless"
    assert "sdl display=0" in argv, f"the display did not reach the emulator: {argv}"
    assert cast(dict[str, Any], reply["window"])["onscreen"] is True, reply
    assert reply.get("watched", False) is True, reply
    regs = cast(dict[str, Any], server.registers())
    assert regs["status"] == "ok", regs
    assert regs["regs"]["CS"] == "0xf000"


@pytest.mark.windowed
def test_window_answers_what_the_os_lists_and_a_headless_session_has_none() -> None:
    """The reply is checked against the host's own window list, read here and not through the
    server; the control is the headless session, which the list must show no window for."""
    host = core_window.host()
    reply = start_ok(session_seconds=30, shared=True, display=0, background=True)
    pid = cast(int, reply["pid"])
    listed = [w for w in host.windows() if w.pid == pid]
    said = cast(dict[str, Any], server.window())["window"]
    assert listed and said["display"] == 0 and said["onscreen"] is True, (said, listed)
    main = core_window.main_window(pid, listed)
    assert main is not None and main.bounds == tuple(said["bounds"].values()), (said, listed)
    server.close()
    reply = start_ok(session_seconds=30, background=True)
    assert not [w for w in host.windows() if w.pid == reply["pid"]], "a headless run drew a window"
    refused = cast(dict[str, Any], server.window())
    assert refused["code"] == "no_channel", refused


def test_stop_brings_a_running_headless_guest_back_through_the_debugger_channel() -> None:
    """`stop` sends BREAK down the emulator's own debugger channel:"""
    start_ok(session_seconds=60)
    released = cast(dict[str, Any], server.resume())
    assert released["status"] == "ok" and "pc" not in released, released
    assert released["session"]["running"] is True, released
    back = cast(dict[str, Any], server.stop())
    assert back["status"] == "ok" and back["interrupted"] is True and back["via"] == "break", back
    assert "regs" in back and "waited_s" not in back, back
    again = cast(dict[str, Any], server.stop())
    assert again["interrupted"] is False


def test_status_reports_the_live_session_and_not_a_remembered_one() -> None:
    """The fields a caller reasons with, read off a machine that really exists."""
    start_ok(session_seconds=60)
    first = cast(dict[str, Any], server.status())
    assert first["status"] == "ok"
    assert wait_for(lambda: cast(dict[str, Any], server.status())[
        "elapsed_s"] > first["elapsed_s"], seconds=10), \
        "the elapsed time did not move: this is not a reading of a live session"
    later = cast(dict[str, Any], server.status())
    assert later["session"]["alive"] is True
    assert later["session"]["altered"] is False, "nothing wrote to this machine"
    assert later.get("output_bytes_dropped", 0) == 0, (
        "the emulator's output overflowed on an idle session: the drain is not keeping up")
    assert first["pc"] == "F000:0000FFF0" and first["cpu_mode"] == "real", first
    assert first["declarations"] == {"breakpoints": 0, "watches": 0, "regpoints": 0}, first


def test_a_registerpoint_stops_the_guest_as_its_condition_comes_true() -> None:
    """`regpoint_add` arms the debugger's `BPIF`: the stop comes with the register at the value
    and its cause names the registerpoint; the clear takes the row out of the debugger."""
    start_ok(session_seconds=120)
    armed = cast(dict[str, Any], server.regpoint_add(condition="bx == 0x100"))
    assert armed["status"] == "ok" and armed["ref"] == "BX==100", armed
    stop = cast(dict[str, Any], server.resume(seconds=60))
    assert stop.get("verdict") == "OTHER_STOP", stop
    assert int(stop["regs"]["EBX"], 16) & 0xFFFF == 0x100 and "BX==100" in str(stop["cause"])
    cleared = cast(dict[str, Any], server.declaration_clear("regpoint", all=True))
    assert cleared["declarations_cleared"] == 1 and cleared["disarmed"] == ["BPIF BX==100"]


def test_a_registerpoint_at_the_most_terms_and_digits_is_listed_back_whole() -> None:
    """Four terms of eight digits, the longest condition `BPIF` takes: its `BPLIST` row must
    come back as sent, or the arm is refused and the debugger keeps a row nothing declared."""
    start_ok(session_seconds=60)
    widest = "EAX==FFFFFFFF && EBX==FFFFFFFF && ECX==FFFFFFFF && EDX==FFFFFFFF"
    armed = cast(dict[str, Any], server.regpoint_add(condition=widest))
    assert armed["status"] == "ok" and armed["entry"] == f"BPIF {widest}", armed
    listed = cast(dict[str, Any], server.declaration_list("regpoint"))
    assert [g["state"] for g in listed["regpoints"]] == ["armed"] and not listed.get(
        "foreign"), listed
    assert cast(dict[str, Any], server.declaration_clear("regpoint", all=True))[
        "disarmed"] == [f"BPIF {widest}"]


_TRAP_AT = "0050:00F0"
_TRAP = "90CCEBFE"


@pytest.mark.parametrize("key", [True, False], ids=["key_on", "key_off"])
def test_break_on_int3_stops_the_guests_own_int3_and_only_with_the_key(key: bool) -> None:
    """`start(break_on_int3=True)` stops the machine at the guest's own `int 3`, at the trap."""
    start_ok(session_seconds=120, break_on_int3=key)
    server.breakpoint_interrupt(number=0x21)
    booted = cast(dict[str, Any], server.resume(seconds=30))
    assert booted.get("verdict") == "OTHER_STOP", (
        "DOS never called INT 21h: nothing here was measured")
    server.declaration_clear("breakpoint", ref="BPINT 21")
    assert server.write(ref=_TRAP_AT, data_hex=_TRAP)["verified"] is True
    seg, off = (int(x, 16) for x in _TRAP_AT.split(":"))
    server.set_register(name="cs", value=seg)
    server.set_register(name="eip", value=off)
    here = cast(dict[str, Any], server.registers())["regs"]
    assert (int(here["CS"], 16), int(here["EIP"], 16)) == (seg, off), here
    ran = cast(dict[str, Any], server.resume(seconds=10))
    if key:
        assert ran.get("verdict") == "OTHER_STOP", ran
        stop_cs, stop_eip = ran["pc"].split(":")
        assert stop_cs == f"{seg:04X}", ran
        assert int(stop_eip, 16) == off + 1, ran
    else:
        assert ran["verdict"] == "TIMEOUT" and "pc" not in ran, ran
        assert ran["session"]["running"] is True, ran


def test_registers_returns_a_value_the_caller_did_not_supply() -> None:
    """The reply a terminal echo cannot fabricate."""
    start_ok(session_seconds=60)
    reply = cast(dict[str, Any], server.registers())
    assert reply["status"] == "ok", reply
    regs = cast(dict[str, str], reply["regs"])
    assert regs["CS"] == "0xf000" and regs["EIP"] == "0x0000fff0"
    assert "EAX" in regs


def test_set_register_takes_and_its_mark_survives_into_every_later_reply() -> None:
    """Two guarantees, and the second is the one a caller cannot recover for itself."""
    start_ok(session_seconds=60)
    assert cast(dict[str, Any], server.status())["session"]["altered"] is False
    reply = cast(dict[str, Any], server.set_register(name="ax", value=0x1234))
    assert reply["status"] == "ok", reply
    assert reply["regs"]["EAX"] == "0x00001234"
    assert reply["readback"] == "0x1234" and reply["verified"] is True
    assert reply["session"]["altered"] is True
    assert cast(dict[str, Any], server.status())["session"]["altered"] is True
    invalid = cast(dict[str, Any], server.step(count=0))
    assert invalid["status"] == "INVALID"
    assert invalid["session"]["altered"] is True, (
        "an INVALID reply stopped saying the machine had been written to")


def test_read_memory_answers_about_the_address_that_was_asked_for() -> None:
    """The answer is IN the answer:"""
    start_ok(session_seconds=60)
    seg, off = 0xF000, 0xE000
    reply = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{off:08X}", length=128))
    assert reply["status"] == "ok", reply
    assert reply["seg_off"] == f"{seg:04X}:{off:08X}" and reply["length"] == 128
    body = bytes.fromhex(str(reply["hex"])).decode("latin-1")
    assert len(body) == 128, f"asked 128 bytes, the reply holds {len(body)}"
    assert "DOSBox-X BIOS" in body or "COMPATIBLE BIO" in body, body
    bad = cast(dict[str, Any], server.read_memory(ref="10000:00000000"))
    assert bad["status"] == "INVALID" and "segment" in str(bad["message"])


def test_debug_hands_back_its_output_and_says_whether_it_kept_all_of_it() -> None:
    """The one tool with no server-side guardrail, so its honesty IS its contract."""
    start_ok(session_seconds=60)
    reply = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert reply["status"] == "ok", reply
    assert reply["command"] == "BPLIST"
    assert "Breakpoint list" in str(reply["output"])
    output = str(reply["output"])
    assert reply["clipped"] is False and len(output) <= DEBUG_CAP, reply
    assert "output_chars" not in reply and "output_path" not in reply, (
        f"an unclipped output carries the clip's fields: {reply}")
    long = cast(dict[str, Any], server.debug(command="HELP"))
    assert long["clipped"] is True and len(str(long["output"])) <= DEBUG_CAP, long
    assert cast(int, long["output_chars"]) > DEBUG_CAP, long
    assert len(Path(str(long["output_path"])).read_text()) == long["output_chars"], long
    resumed = cast(dict[str, Any], server.resume(detail=True))
    assert resumed.get("clipped", False) is (
        cast(int, resumed["output_chars"]) > SMALL_CAP), resumed["output_chars"]


def test_memdump_lands_the_exact_bytes_and_leaves_nothing_behind(
        tmp_path: Path) -> None:
    """Through the tool, the layer that runs it against a machine."""
    start_ok(session_seconds=90)
    dest = tmp_path / "dump.bin"
    reply = cast(dict[str, Any], server.memdump(
        ref="F000:0000E000", length=256, dest=str(dest)))
    assert reply["status"] == "ok", reply
    assert reply["path"] == str(dest), "it reported a path it did not write to"
    assert reply["bytes"] == 256 and dest.stat().st_size == 256
    body = dest.read_bytes()
    assert len(set(body)) > 1, ("every byte is identical, which is what a wrong "
                                "segment and a truncated write both look like")
    left = [p for p in cast(ds.Session, dstate.STATE.session)._memdump_candidates()
            if p.exists()]
    assert not left, f"the dump was left behind at {left}"


def test_breakpoint_interrupt_arms_the_interrupt_it_was_given_and_not_another() -> None:
    """The hex-for-decimal trap, asserted against the debugger's own acknowledgement."""
    start_ok(session_seconds=60)
    reply = cast(dict[str, Any], server.breakpoint_interrupt(number=0x21, ah=0x4C, detail=True))
    assert reply["status"] == "ok", reply
    assert "INT 21 AH=4C" in str(reply["output"]), reply["output"][-400:]


def test_resume_lets_the_guest_advance() -> None:
    """The guest genuinely RUNS, evidenced by a stop away from the reset vector it parked at."""
    start_ok(session_seconds=90)
    reply = cast(dict[str, Any], server.resume(detail=True))
    assert reply["status"] == "ok" and reply["output"] == "OK", reply
    assert "pc" not in reply, reply
    assert reply["session"]["running"] is True, reply
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True
    assert wait_for(lambda: cast(dict[str, Any], server.status())["elapsed_s"] > 1.0, seconds=10)
    stopped = cast(dict[str, Any], server.stop())
    assert stopped["status"] == "ok" and stopped["pc"] != "F000:0000FFF0", stopped


def test_wait_holds_a_running_guest_for_its_bound_and_refuses_a_stopped_one(
        tmp_path: Path) -> None:
    """`wait` lets a running guest play without touching it, and a stopped machine refuses."""
    log = tmp_path / "guest.log"
    start_ok(session_seconds=90, logfile=str(log))
    server.resume()
    assert wait_for(lambda: log.exists() and dlogs.count_e9(
        log.read_text(encoding="utf-8", errors="replace")) >= 1), "the guest never logged"
    waited = cast(dict[str, Any], server.wait(seconds=1.0))
    assert waited["status"] == "ok" and waited["waited_s"] >= 0.9, waited
    assert waited["session"]["running"] is True, waited
    server.stop()
    refused = cast(dict[str, Any], server.wait(seconds=1.0))
    assert refused["status"] == "INVALID" and refused["code"] == "not_running", refused


def test_e9_returns_matching_lines_and_counts_all_of_them(tmp_path: Path) -> None:
    """THE POSITIVE PATH, which no live case had ever exercised."""
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log(channel="guest", pattern="Bochs port E9h", limit=2))
    assert reply["status"] == "ok", reply
    lines = cast(list[str], reply["lines"])
    assert len(lines) == 2 and len(reply["lines"]) == 2
    assert cast(int, reply["lines_total"]) > 2, (
        f"lines_total ({reply['lines_total']}) is not more than what came back, so this "
        f"case cannot tell the total from the slice")
    assert reply["truncated"] is True
    assert all(ln.startswith("Bochs port E9h:") for ln in lines), lines
    empty = cast(dict[str, Any], server.log(channel="guest", pattern="zzz-no-guest-emits-this",
                                            limit=5))
    assert empty["status"] == "ok", empty
    assert empty["lines"] == [] and empty["lines_total"] == 0


def test_captures_and_a_still_come_out_of_a_real_recording(tmp_path: Path) -> None:
    """Both halves, on one recording, because a still is an EXTRACTION from the video."""
    caps = tmp_path / "caps"
    caps.mkdir()
    conf = conf_that_does_not_exit(tmp_path)
    reply = cast(dict[str, Any], server.start(
        conf=str(conf), cwd=CWD, session_seconds=120,
        program=GUEST_PROGRAM,
        capture_video=True, captures_dir=str(caps)))
    assert reply["status"] == "ok", reply
    server.resume()

    def enough() -> bool:
        files = sorted(caps.glob("*.avi"), key=lambda f: f.stat().st_size)
        return bool(files) and cast(
            int, ds.avi_facts(files[-1].read_bytes())["avi_frames"]) > 200

    assert wait_for(enough, seconds=90), "no capture reached 200 frames: INVALID"

    got = cast(dict[str, Any], server.captures())
    assert got["status"] == "ok", got
    files = [c for c in cast(list[dict[str, Any]], got["captures"]) if c["kind"] == "avi"]
    biggest = files[-1]
    assert biggest["riff_avi"] is True, files
    assert cast(int, biggest["avi_frames"]) > 100, files
    assert [f["bytes"] for f in files] == sorted(f["bytes"] for f in files), files

    shot = tmp_path / "shot.png"
    frame = cast(dict[str, Any], server.capture_frame(frame=60, dest=str(shot)))
    assert frame["status"] == "ok", frame
    assert frame["path"] == str(shot)
    assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "that is not a PNG"
    assert frame["bytes"] == shot.stat().st_size > 1000
    other = tmp_path / "shot2.png"
    second = cast(dict[str, Any], server.capture_frame(frame=180, dest=str(other)))
    assert second["status"] == "ok", second
    assert other.read_bytes() != shot.read_bytes(), (
        "frames 60 and 180 came out byte-identical, so `frame` is reaching nothing and "
        "any frame number would return this same image")


def test_a_close_after_the_emulator_died_carries_the_last_words_of_both_channels(
        tmp_path: Path) -> None:
    """Why it ended, in the reply that ends it, on the real emulator:"""
    log = tmp_path / "s.log"
    started = start_ok(session_seconds=60, logfile=str(log))
    dprocess.signal_group(int(started["pid"]), guardian.KILL)
    assert wait_for(lambda: not server.status()["session"]["alive"], seconds=10)
    gone = cast(dict[str, Any], server.close())
    assert gone["ended_by"] == "died", gone
    assert gone["stdout_tail"].strip() and gone["errorlog_tail"].strip(), gone
    start_ok(session_seconds=60, logfile=str(log))
    clean = cast(dict[str, Any], server.close())
    assert clean["ended_by"] == "quit", clean
    assert set(clean["omitted"]) == {"stdout_tail", "errorlog_tail"}, clean
    start_ok(session_seconds=60, logfile=str(log))
    asked = cast(dict[str, Any], server.close(detail=True))
    assert asked["stdout_tail"].strip() and asked["errorlog_tail"].strip(), asked


def test_close_clears_the_session_so_the_next_tool_says_there_is_none() -> None:
    """Closing is TWO things, and the second is the one that had no live case."""
    start_ok(session_seconds=60)
    reply = cast(dict[str, Any], server.close())
    assert reply["status"] == "ok" and reply["closed"] is True
    assert "pid" in reply, "it did not say what it had just closed"
    assert dstate.STATE.session is None, "the server is still pointing at a dead session"
    after = cast(dict[str, Any], server.registers())
    assert after["status"] == "INVALID" and "no live session" in str(after["message"])
    gone = cast(dict[str, Any], server.status())
    assert gone["session"]["alive"] is False and "alive" not in gone, gone
    again = cast(dict[str, Any], server.close())
    assert again["status"] == "ok" and again["closed"] is False


def test_closing_a_running_session_does_not_wait_out_a_signal_it_ignores() -> None:
    """The cost of ending a session that was actually USED, which is every real one, and the."""
    start_ok(session_seconds=90)
    resumed = cast(dict[str, Any], server.resume(detail=True))
    assert resumed["status"] == "ok" and resumed["output"] == "OK", resumed
    assert "pc" not in resumed and resumed["session"]["running"] is True, resumed
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True

    proc = cast(ds.Session, dstate.STATE.session).proc
    t0 = time.monotonic()
    reply = cast(dict[str, Any], server.close())
    took = time.monotonic() - t0
    assert reply["closed"] is True
    assert proc.poll() is not None, (
        "the emulator is STILL RUNNING after close returned. `closed: true` says a "
        "session was there, not that it ended")
    assert reply["ended_by"] == "quit", (
        f"close ended a running session by {reply['ended_by']!r}, not a clean quit: the "
        f"emulator ignored the TERM, so the quit warning is back on")
    assert cast(int, reply["exit_code"]) == 0, (
        f"exit code {reply['exit_code']}: a clean quit exits 0")
    assert took < 5.0, (
        f"closing a running session took {took:.2f}s. With the quit warning off the "
        f"emulator answers the TERM at once; a wait this long means it is sitting behind "
        f"a dialog nobody will answer, the failure forcing the warning off exists to "
        f"prevent. The honest ceiling is TERM_GRACE ({dprocess.TERM_GRACE}s) plus the drain "
        f"join ({dprocess.DRAIN_JOIN_SECS}s)")


def test_a_real_mode_session_refuses_rather_than_placing_at_base_zero(
        tmp_path: Path) -> None:
    """The guard, against the machine that really produces the trap."""
    start_ok(session_seconds=60)
    regs = cast(dict[str, Any], server.registers())["regs"]
    assert regs["CS"] == "0xf000", (
        f"expected a session stopped at the reset vector, got CS={regs['CS']}")
    src = tmp_path / "probe.sym"
    src.write_text("0000fff0 T _reset_vector\n", encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src)))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "real mode" in got["message"] and "`base`" in got["message"], got


def test_symbols_load_places_a_real_list_through_the_whole_chain(
        tmp_path: Path) -> None:
    """Descriptor refused, base supplied, file written, `LV`, `SV`, decode, lookup."""
    start_ok(session_seconds=90)
    src = tmp_path / "probe.sym"
    src.write_text("00000000 T _rom_start\n"
                   "0000fff0 T _reset_vector\n"
                   "0000abcd t _somewhere_in_rom\n", encoding="utf-8")

    got = cast(dict[str, Any], server.symbols_load(path=str(src), base="0xF0000"))
    assert got["status"] == "ok", got
    assert got["parsed"] == 3 and got["kept"] == 3, got
    assert got["loaded"] == 3, (
        f"the debugger reported ok and holds {got['loaded']} records. Those disagree, "
        f"so nothing here is a reading of what it loaded")

    found = cast(dict[str, Any], server.symbols_find(name="_reset_vector"))
    assert found["status"] == "ok", found
    assert found["symbols"][0]["addr"] == "0x000ffff0", found

    where = cast(dict[str, Any], server.symbols_find(linear="0x000FFFF2"))
    assert (where["name"], where["delta"]) == ("_reset_vector", 2), where


def test_symbols_load_leaves_no_file_behind_in_the_working_directory(
        tmp_path: Path) -> None:
    """The two files live in the emulator's WORKING DIRECTORY, which is somebody's project."""
    start_ok(session_seconds=60)
    cwd = Path(CWD)
    src = tmp_path / "probe.sym"
    src.write_text("00001000 T _x\n", encoding="utf-8")
    try:
        got = cast(dict[str, Any], server.symbols_load(path=str(src),
                                                       base="0xF0000"))
        assert got["status"] == "ok", got
    finally:
        src.unlink(missing_ok=True)
    left = [n for n in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME) if (cwd / n).exists()]
    for name in left:
        (cwd / name).unlink()
    assert not left, f"{left} was left in {cwd}, which is somebody's project"


@pytest.mark.parametrize("which", ["load", "save"])
def test_a_file_already_sitting_at_either_name_is_refused_not_overwritten(
        which: str, tmp_path: Path) -> None:
    """The mirror of the case above, and the one that stops "delete on the way in" passing it:"""
    start_ok(session_seconds=60)
    cwd = Path(CWD)
    intruder = cwd / (ds.SYM_LOAD_NAME if which == "load" else ds.SYM_SAVE_NAME)
    src = tmp_path / "probe.sym"
    src.write_text("00001000 T _x\n", encoding="utf-8")
    intruder.write_bytes(b"not mine")
    try:
        got = cast(dict[str, Any], server.symbols_load(path=str(src),
                                                       base="0xF0000"))
        assert got["status"] == "INVALID", got
        assert "will not overwrite" in got["message"], got
        assert intruder.read_bytes() == b"not mine", "it overwrote the caller's file"
    finally:
        intruder.unlink(missing_ok=True)


RESET_CS, RESET_EIP = "F000", "0000FFF0"
AFTER_ONE_STEP = "0000E05B"


BIOS_CALLS_TO_SKIP = 40


def test_step_advances_by_exactly_one_instruction_and_says_where_it_landed() -> None:
    """A step is only a step if the machine MOVED, and moved to the right place."""
    start_ok(session_seconds=60)
    reply = cast(dict[str, Any], server.step(mode="over", count=1))
    assert reply["status"] == "ok", reply
    assert reply["before"] == f"{RESET_CS}:{RESET_EIP}" and reply["cpu_mode"] == "real"
    assert reply["after"] == f"{RESET_CS}:{AFTER_ONE_STEP}"
    assert reply["instructions_completed"] == 1 and reply["session"]["running"] is False


def test_stepping_a_running_machine_refuses_instead_of_pressing_keys_at_nobody(
        ) -> None:
    """THE REFUSAL, against a machine that is really running."""
    start_ok(session_seconds=60)
    server.resume()
    reply = cast(dict[str, Any], server.step(mode="over", count=1))
    assert reply["status"] == "INVALID", reply
    assert reply["code"] == "not_stopped", reply
    assert "needs the machine STOPPED" in reply["message"], reply


def a_return_address_in_ram() -> tuple[int, int]:
    """Stop the guest at one of its own `INT 21` calls, and give back where that call RETURNS to."""
    reply = cast(dict[str, Any], server.breakpoint_interrupt(number=0x21))
    assert reply["status"] == "ok", reply
    seg = eip = 0
    for _ in range(BIOS_CALLS_TO_SKIP):
        server.resume()
        regs = cast(dict[str, Any], server.registers())
        assert regs["status"] == "ok", regs
        seg = int(regs["regs"]["CS"], 16)
        eip = int(regs["regs"]["EIP"], 16)
        if seg != 0xF000:
            break
    else:
        pytest.fail(
            f"every one of {BIOS_CALLS_TO_SKIP} INT 21 calls was made from the BIOS "
            f"ROM segment (last: {seg:04X}:{eip:08X}). A code breakpoint there is "
            f"acknowledged and never fires, so this case cannot measure what it is "
            f"named for: INVALID, not a pass")
    read = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{eip:08X}", length=2))
    assert read["status"] == "ok", read
    opcode = [read["hex"][:2].upper(), read["hex"][2:4].upper()]
    assert opcode == ["CD", "21"], (
        f"the stop at {seg:04X}:{eip:08X} is not a two-byte `CD 21` (it reads "
        f"{opcode}), so eip+2 is not the return address and this case would be "
        f"measuring an address the machine never reaches: INVALID, not a pass")
    server.debug(command="BPDEL *")
    return seg, eip + 2


def a_hot_address() -> str:
    """The timer interrupt's handler, read off the guest's own vector table (INT 8 at."""
    vec = cast(dict[str, Any], server.read_memory(ref="0000:0020", length=4))
    assert vec["status"] == "ok", vec
    raw = bytes.fromhex(vec["hex"])
    off, seg = int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:], "little")
    return f"{seg:04X}:{off:04X}"


def test_run_to_arrives_at_a_real_address_and_takes_its_breakpoint_away() -> None:
    """The whole chain against a real debugger:"""
    start_ok(session_seconds=120)
    seg, off = a_return_address_in_ram()
    reply = cast(dict[str, Any], server.run_to(ref=f"{seg:04X}:{off:04X}", seconds=30,
                                               control="0000:0001"))
    assert reply["status"] == "ok", reply
    assert reply["verdict"] == "TARGET", reply
    assert reply["pc"] == f"{seg:04X}:{off:08X}", reply
    assert reply["target_disarmed"] is True, reply
    server.debug(command="BP F000:E05B")
    left = cast(dict[str, Any], server.debug(command="BPLIST"))
    held = [b["entry"] for b in grammar.parse_breakpoints(str(left["output"]))]
    assert "BP F000:E05B" in held, (
        f"the sentinel is not in the listing, so this read examined nothing and its "
        f"verdict about the removal is worth nothing: {held}")
    assert f"BP {seg:04X}:{off:04X}" not in held, held


BOOT_SLICE_FRAMES = 10
BOOT_SLICES_MAX = 6


def test_machine_map_is_honest_before_dos_and_finds_the_guest_after(tmp_path: Path) -> None:
    """At the park `start` leaves, DOS has not booted, so the chain is ABSENT with the."""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.machine_map(sections=list(machine.SECTION_NAMES)))
    assert park["status"] == "ok" and "mcbs" not in park, park
    assert "DOS kernel is inactive" in park["coverage_note"], park["coverage_note"]
    assert park["control"]["cr0"] and park["bios_mem"], park
    program = Path(GUEST_PROGRAM).stem.upper()
    for _ in range(BOOT_SLICES_MAX):
        assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
        booted = cast(dict[str, Any], server.machine_map(sections=list(machine.SECTION_NAMES)))
        assert booted["status"] == "ok", booted
        if program in {b["filename"] for b in booted.get("mcbs", [])}:
            break
    assert program in {b["filename"] for b in booted["mcbs"]}, booted["mcbs"]
    assert ("gdt" in booted) == (booted["cpu_mode"] != "real"), booted["coverage_note"]
    assert booted["counts"]["mcbs"] == len(booted["mcbs"]) and booted["sources"]["mcbs"]
    after = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert grammar.BPLIST_HEADER in after["output"] \
        and "not recognized" not in after["output"], after["output"][-200:]


def test_palette_reads_the_dac_before_and_after_the_bios_sets_it(tmp_path: Path) -> None:
    """At the park no video mode is set and the DAC is all zero; once the guest runs in a text."""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.palette())
    assert park["status"] == "ok" and park["entries"] == 256, park
    assert set(park["rgb"]) == {"000000"}, park["rgb"][:4]
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    dest = tmp_path / "dac.png"
    one = cast(dict[str, Any], server.palette(first=1, count=1, dest=str(dest)))
    assert one["status"] == "ok", one
    assert one["rgb"] == ["00002a"] and one["colors"] == ["#0000aa"], one
    assert one["image"]["path"] == str(dest) and dest.stat().st_size > 0
    after = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert grammar.BPLIST_HEADER in after["output"] \
        and "not recognized" not in after["output"], after["output"][-200:]
    bad = cast(dict[str, Any], server.palette(first=256))
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", bad


def test_screen_view_reads_the_text_the_guest_was_launched_from(tmp_path: Path) -> None:
    """Before the BIOS sets a mode there is no screen to read, and the refusal names the mode."""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.screen_view())
    assert park["status"] == "INVALID" and park["code"] == "no_channel", park
    assert "`M_ERROR`" in park["message"] and "capture_frame" in park["message"]
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    view = cast(dict[str, Any], server.screen_view())
    assert view["status"] == "ok" and view["kind"] == "text", view
    assert (view["width"], view["height"]) == (80, 25)
    program = Path(GUEST_PROGRAM).name.upper()
    assert program and any(row.upper().endswith(program) for row in view["text"]), view["text"]
    launched = next(i for i, row in enumerate(view["text"]) if row.upper().endswith(program))
    assert view["cursor"] == [0, launched + 1], (view["cursor"], view["text"])
    one = cast(dict[str, Any], server.screen_signature())
    two = cast(dict[str, Any], server.screen_signature())
    assert one["status"] == two["status"] == "ok", (one, two)
    assert one["signature"] == two["signature"] and one["kind"] == "text"
    bad = cast(dict[str, Any], server.screen_view(dest=str(tmp_path / "text.png")))
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", bad


def test_screen_wait_runs_until_the_launch_line_is_on_screen(tmp_path: Path) -> None:
    """From the park, where no mode is set, the wait runs retrace by retrace until DOS has."""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    program = Path(GUEST_PROGRAM).name.upper()
    found = cast(dict[str, Any], server.screen_wait(text=program, seconds=120))
    assert found["status"] == "ok" and found["already"] is False, found
    assert found["polls"] >= 1 and found["line"].upper().endswith(program), found
    assert found["regs"] and "stop_seq" in found
    again = cast(dict[str, Any], server.screen_wait(text=program, seconds=5))
    assert again["status"] == "ok" and again["already"] is True and again["polls"] == 0, again
    gone = cast(dict[str, Any], server.screen_wait(text="NO GUEST PRINTS THIS", seconds=3))
    assert gone["status"] == "ok" and gone["verdict"] == "TIMEOUT", gone
    assert gone["polls"] >= 1 and any(program in row.upper() for row in gone["text"]), gone


def test_interrupt_vectors_places_the_dos_handler_and_leaves_no_file(tmp_path: Path) -> None:
    """Once DOS runs, INT 21h points into a block one of the listings holds and the table is."""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    one = cast(dict[str, Any], server.interrupt_vectors(number=0x21))
    assert one["status"] == "ok" and len(one["vectors"]) == 1, one
    row = one["vectors"][0]
    assert row["number"] == "0x21" and row["seg_off"] != "0000:00000000", row
    assert any(k in row for k in ("mcbs", "kern", "bios_mem")), one["coverage_note"]
    whole = cast(dict[str, Any], server.interrupt_vectors())
    assert whole["status"] == "ok" and len(whole["vectors"]) == 256
    left = Path(CWD) / ds.INTVEC_FILE
    assert not left.exists(), "the server's own file is removed"
    left.write_text("planted by the live case")
    try:
        refused = cast(dict[str, Any], server.interrupt_vectors())
        assert refused["code"] == "bad_argument" and left.read_text() == "planted by the live case"
    finally:
        left.unlink()
    server.close()
    start_ok(session_seconds=120)
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    bare = cast(dict[str, Any], server.interrupt_vectors(number=0x21))
    mode = status_mode()
    assert bare["status"] == "ok" and isinstance(mode, str) and bare["cpu_mode"] == mode, bare
    assert ("addr" in bare["vectors"][0]) == (mode == "real"), bare
    assert "logfile" not in bare["coverage_note"] and any(
        k in bare["vectors"][0] for k in ("mcbs", "kern", "bios_mem")), bare


def status_mode() -> Any:
    return cast(dict[str, Any], server.status()).get("cpu_mode")


def _a_build_without_runstate() -> str:
    """A release binary of this machine: `DOSBOX_X_RELEASE_BINARY`, else the PATH's, and only
    one that lacks `RUNSTATE`, since a build that has it cannot answer the negative."""
    held = os.environ.get("DOSBOX_X_RELEASE_BINARY") or shutil.which("dosbox-x") or ""
    if not held or not binaries.debugger(held) or "RUNSTATE" in binaries.debugger_commands(held):
        pytest.skip("no DOSBox-X release without RUNSTATE here: set DOSBOX_X_RELEASE_BINARY")
    return held


def test_a_tool_that_waits_is_refused_by_name_on_a_build_without_runstate() -> None:
    """The negative of the cell above: the same call on a release is `no_channel` naming the
    command, and `build_check` of that binary says what it lacks and what that disables."""
    release = _a_build_without_runstate()
    checked = cast(dict[str, Any], server.build_check(binary=release))
    absent = {row["command"]: row["disables"] for row in checked["debugger_commands_missing"]}
    assert "run_for" in absent["RUNSTATE"], checked
    start_ok(session_seconds=60, binary=release)
    refused = cast(dict[str, Any], server.run_for(frames=1))
    assert refused["code"] == "no_channel" and "RUNSTATE" in refused["message"], refused
    assert refused["session"]["running"] is False, "a refused wait must not release the machine"


def test_run_for_lands_its_retraces_and_the_pane_clock_says_how_far() -> None:
    """Frames are the debugger's retraces, and the known answer is the display's own rate:"""
    start_ok(session_seconds=120)
    first = cast(dict[str, Any], server.run_for(frames=3))
    assert first["status"] == "ok", first
    assert first["verdict"] == "ELAPSED" and first["polls"] == 3
    assert first["session"]["running"] is False
    assert first["emulated_after_s"] > first["emulated_before_s"], first
    second = cast(dict[str, Any], server.run_for(frames=2))
    assert second["status"] == "ok" and second["verdict"] == "ELAPSED", second
    moved = second["emulated_after_s"] - second["emulated_before_s"]
    assert moved == pytest.approx(2 / 70, rel=0.2), f"two retraces moved the clock {moved} s"
    assert server.status()["pc"] == second["pc"], "status names this stop"
    asked_ms = 50
    timed = cast(dict[str, Any], server.run_for(milliseconds=asked_ms))
    assert timed["status"] == "ok" and timed["verdict"] == "ELAPSED", timed
    covered = timed["emulated_after_s"] - timed["emulated_before_s"]
    assert asked_ms / 1000 <= covered < asked_ms / 1000 + 1 / 70, f"{covered} s landed"
    refused = cast(dict[str, Any], server.debug(command="VRT"))
    assert refused["code"] == "bad_argument" and "run_for" in refused["message"], refused


def test_disassemble_decodes_what_memory_holds_and_names_the_probes_calls(
        tmp_path: Path) -> None:
    """The probe's `start` decoded on the host:"""
    start_ok(session_seconds=180, logfile=str(tmp_path / "guest.log"))
    parked = cast(dict[str, Any], server.run_for(frames=1))
    assert parked["status"] == "ok" and parked["pc"].endswith(":00000106"), parked
    loaded = cast(dict[str, Any], server.symbols_load(path=str(_OWN / "probe.sym"),
                                                      base="0x8140"))
    assert loaded["status"] == "ok", loaded
    got = cast(dict[str, Any], server.disassemble(ref="start", length=16))
    assert got["status"] == "ok" and got["code_bits"] == 16, got
    listed = [(ln.split()[0], ln.split()[1]) for ln in got["lines"]]
    listed_bytes = "".join(b for _a, b in listed)
    raw = cast(dict[str, Any], server.read_memory(ref="0814:010B",
                                                  length=len(listed_bytes) // 2))["hex"]
    assert listed_bytes.upper() == raw.upper(), (listed, raw)
    named = {(r["line"], r["kind"]): (r["symbol"], r["delta"]) for r in got["resolved"]}
    assert named[(1, "target")] == ("emit", 0) and named[(2, "target")] == ("bump", 0)
    assert named[(3, "memory")] == ("cnt", 1), named
    refused = cast(dict[str, Any], server.disassemble(ref="start", length=0))
    assert refused["code"] == "bad_argument", refused


def test_comments_follow_the_symbol_one_per_place_and_round_trip_through_a_file(
        tmp_path: Path) -> None:
    """On the probe with `probe.sym` at 8140:"""
    start_ok(session_seconds=120, logfile=str(tmp_path / "guest.log"))
    assert cast(dict[str, Any], server.run_for(frames=1))["status"] == "ok"
    assert cast(dict[str, Any], server.symbols_load(path=str(_OWN / "probe.sym"),
                                                    base="0x8140"))["status"] == "ok"
    held = {c["ref"] for c in cast(dict[str, Any], server.comment_list())["comments"]}
    assert not held & {"start", "0814:0106"}, f"the store already comments these: {held}"
    counted = cast(dict[str, Any], server.status())["declarations"]
    linear = cast(dict[str, Any], server.symbols_find(name="start"))["symbols"][0]["addr"]
    added = cast(dict[str, Any], server.comment_write("add", ref="start", text="entry"))
    assert added["status"] == "ok" and added["comment"]["addr"] == linear, added
    aliased = cast(dict[str, Any], server.comment_write("add", ref="0824:000B",
                                                        text="entry, aliased"))
    assert aliased["comment"]["ref"] == "start", aliased
    assert [r["text"] for r in aliased["replaced_comments"]] == ["entry"], aliased
    assert cast(dict[str, Any], server.status())["declarations"] == counted
    first, second = tmp_path / "a-comments.tsv", tmp_path / "b-comments.tsv"
    try:
        saved = cast(dict[str, Any], server.comment_write("save", dest=str(first)))
        assert saved["status"] == "ok", saved
        assert "start\t\t" in first.read_text(encoding="utf-8")
        assert cast(dict[str, Any], server.comment_write("delete", ref="start"))["status"] == "ok"
        loaded = cast(dict[str, Any], server.comment_write("load", path=str(first)))
        assert loaded["status"] == "ok" and loaded["added"] == 1, loaded
        assert cast(dict[str, Any], server.comment_write("save",
                                                         dest=str(second)))["status"] == "ok"
        assert first.read_bytes() == second.read_bytes()
    finally:
        for ref in {c["ref"] for c in cast(dict[str, Any], server.comment_list())["comments"]} \
                - held:
            server.comment_write("delete", ref=ref)


def test_call_stack_at_the_probes_settle_loop_lists_the_stop_and_why_it_ended(
        tmp_path: Path) -> None:
    """The probe keeps no frame pointer, so the walk at its settle `loop` has the stop as its."""
    start_ok(session_seconds=120, logfile=str(tmp_path / "guest.log"))
    parked = cast(dict[str, Any], server.run_for(frames=1))
    assert parked["status"] == "ok", parked
    got = cast(dict[str, Any], server.call_stack())
    assert got["status"] == "ok" and got["heuristic"] is True, got
    assert got["calls"][0]["seg_off"] == parked["pc"] and got["ended_why"], got


def test_trace_executes_the_count_it_was_asked_and_hands_the_log_over(tmp_path: Path) -> None:
    """At the probe guest's settle loop `loop` takes one off ECX per instruction it executes, so."""
    start_ok(session_seconds=180)
    parked = cast(dict[str, Any], server.run_for(frames=2))
    assert parked["status"] == "ok" and parked["pc"].endswith(":00000106"), parked
    ecx = int(parked["regs"]["ECX"], 16)
    assert ecx > 16, "the settle loop has room for the whole trace"
    dest = tmp_path / "settle.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["verdict"] == "ELAPSED", got
    assert got["trace"]["instructions"] == 16 and got["trace"]["addresses"] == 1, got["trace"]
    assert int(got["regs"]["ECX"], 16) == ecx - 16, (ecx, got["regs"])
    assert len(dest.read_bytes().splitlines()) == 17
    assert not any((Path(CWD) / n).exists() for n in ("LOGCPU.TXT", "logcpu.txt"))
    refused = cast(dict[str, Any], server.debug(command="LOG 10"))
    assert refused["code"] == "bad_argument" and "`trace`" in refused["message"], refused


def test_run_to_arrives_at_an_aliased_real_mode_spelling_of_the_same_byte() -> None:
    """MANY SEG:OFF PAIRS NAME ONE BYTE IN REAL MODE, and the symbol layer arms through the load."""
    start_ok(session_seconds=120)
    seg, off = a_return_address_in_ram()
    alias = f"{seg - 1:04X}:{off + 16:04X}"
    reply = cast(dict[str, Any], server.run_to(ref=alias, seconds=30, control="0000:0001"))
    assert reply["status"] == "ok" and reply["target"] == alias, reply
    assert reply["verdict"] == "TARGET", reply
    assert reply["pc"] == f"{seg:04X}:{off:08X}", reply
    assert reply["target_disarmed"] is True, reply


def test_a_bound_that_expires_reports_a_machine_at_rest_and_its_breakpoint_gone(
        ) -> None:
    """THE NEGATIVE, on the same tool, in the same session shape."""
    start_ok(session_seconds=90)
    seg, off = a_return_address_in_ram()
    into = cast(dict[str, Any], server.run_to(ref=f"{seg:04X}:{off:04X}", seconds=30,
                                              control="0000:0001"))
    assert into["verdict"] == "TARGET", into
    hot = a_hot_address()
    assert hot != "0000:0000", "the vector table is filled once the BIOS ran"
    reply = cast(dict[str, Any], server.run_to(ref="0000:0001", seconds=3, control=hot))
    assert reply["status"] == "ok", reply
    assert reply["control_hits"] > 0, "the timer handler fired: the silence is a measurement"
    assert reply["verdict"] == "TIMEOUT", reply
    # Stopped where it stands: in the handler or out of it, as the bound found the guest.
    assert reply["session"]["running"] is False and ":" in str(reply["pc"]), reply
    assert reply["target_disarmed"] is True, reply
    assert "was removed" in str(reply["note"]), reply

def test_a_second_resume_after_run_to_does_not_stop_where_run_to_arrived() -> None:
    """The timer handler runs every few milliseconds, so a breakpoint `run_to` left behind would
    stop the next release at once; the same address armed by hand is the control that does."""
    start_ok(session_seconds=90)
    seg, off = a_return_address_in_ram()
    into = cast(dict[str, Any], server.run_to(ref=f"{seg:04X}:{off:04X}", seconds=30,
                                              control="0000:0001"))
    assert into["verdict"] == "TARGET", into
    hot = a_hot_address()
    assert hot != "0000:0000", "the vector table is filled once the BIOS ran"
    arrived = cast(dict[str, Any], server.run_to(ref=hot, seconds=10, control="0000:0001"))
    assert arrived["verdict"] == "TARGET" and arrived["target_disarmed"] is True, arrived
    again = cast(dict[str, Any], server.resume(seconds=2))
    assert again["status"] == "ok" and again["verdict"] == "TIMEOUT", again
    assert server.stop()["status"] == "ok"
    server.debug(command=f"BP {hot}")
    armed = cast(dict[str, Any], server.resume(seconds=10))
    assert armed["verdict"] == "OTHER_STOP" and armed["pc"] == arrived["pc"], (
        f"the control did not stop at the handler by hand, so the silence above measured "
        f"nothing: {armed}")


def test_e9_wait_answers_a_line_that_had_already_gone_past(tmp_path: Path) -> None:
    """THE QUERY HALF, against a real guest."""
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log_wait(channel="guest", pattern=GUEST_MARK, seconds=30))
    assert reply["status"] == "ok", reply
    assert reply["already"] is True, reply
    assert reply["waited_s"] == 0.0, reply
    assert GUEST_MARK in str(reply["line"]), reply
    assert cast(int, reply["lines_examined"]) > 5, reply


def test_e9_wait_really_waits_for_a_line_that_has_not_happened_yet(
        tmp_path: Path) -> None:
    """THE WAIT HALF, and it must REQUIRE the wait, not accept either outcome."""
    a_running_guest_that_has_logged(tmp_path, seconds=180, lines=1)
    late = GUEST_LATE
    before = cast(dict[str, Any], server.log(channel="guest", pattern=late, limit=1))
    assert before["status"] == "ok", before
    assert before["lines_total"] == 0, (
        f"{late!r} had ALREADY been logged {prose.counted(before['lines_total'], 'time')} before "
        f"this was asked, so this window cannot demonstrate a wait at all: INVALID, not a pass")

    reply = cast(dict[str, Any], server.log_wait(channel="guest", pattern=late, seconds=120))
    assert reply["status"] == "ok", reply
    assert reply["already"] is False, reply
    assert 0.0 < cast(float, reply["waited_s"]) < 120.0, reply
    assert cast(int, reply["arrived_during"]) > 0, reply


def test_e9_wait_says_a_bound_expired_rather_than_answering_nothing(
        tmp_path: Path) -> None:
    """A TIMEOUT verdict, not an empty answer, and the note names what it examined -- against a."""
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log_wait(
        channel="guest", pattern="a_string_this_guest_will_never_log", seconds=3))
    assert reply["status"] == "ok" and reply["verdict"] == "TIMEOUT", reply
    assert "arrived DURING the wait" in reply["note"], reply
    assert "in the log altogether" in reply["note"], reply


def test_write_lands_in_ram_and_is_read_back_and_a_write_into_rom_is_refused() -> None:
    """The readback on the real debugger:"""
    start_ok(session_seconds=60)
    ram = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="1234abcd"))
    assert ram["status"] == "ok" and ram["verified"] is True, ram
    assert ram["readback"] == "1234abcd" and ram["bytes_written"] == 4
    assert ram["session"]["altered"] is True
    back = cast(dict[str, Any], server.read_memory(ref="0040:0100", length=4))["hex"]
    assert back == "1234abcd", back
    rom = cast(dict[str, Any], server.write(ref="F000:E05B", data_hex="99"))
    assert rom["status"] == "INVALID" and "ENDS the emulator" in rom["message"], rom
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True


_MARK_AT = "0000:000004F0"


def _byte_at(ref: str) -> str:
    reply = cast(dict[str, Any], server.read_memory(ref=ref, length=1))
    assert reply["status"] == "ok", reply
    return str(reply["hex"]).upper()


def test_states_round_trip_headless_through_the_debugger_commands(tmp_path: Path) -> None:
    """A state saved and loaded with no window, by the debugger's own SAVESTATE and LOADSTATE (a."""
    state_dir = tmp_path / "states"
    started = cast(dict[str, Any], server.start(
        conf=str(conf_that_does_not_exit(tmp_path)), cwd=CWD, session_seconds=120,
        program=GUEST_PROGRAM, logfile=str(tmp_path / "e9.log"), state_dir=str(state_dir)))
    assert started["status"] == "ok", started
    empty = cast(dict[str, Any], server.state_list())
    assert empty["status"] == "ok" and empty["states"] == [], empty
    missing = cast(dict[str, Any], server.state_write("load", name="live"))
    assert missing["status"] == "INVALID" and missing["code"] == "unknown_ref", missing
    assert server.write(ref=_MARK_AT, data_hex="AA")["verified"] is True
    saved = cast(dict[str, Any], server.state_write("save", name="live"))
    if saved.get("code") == "no_channel":
        pytest.skip(f"this DOSBox-X carries no SAVESTATE: {saved['message']}")
    assert saved["status"] == "ok" and saved["paused"] is False, saved
    assert Path(str(saved["path"])) == state_dir / "live.sav"
    assert saved["program"] and saved["saved_at"] and saved["version"].startswith("DOSBox-X")
    assert server.write(ref=_MARK_AT, data_hex="55")["verified"] is True
    assert _byte_at(_MARK_AT) == "55", "the control: the byte changed after the save"
    loaded = cast(dict[str, Any], server.state_write("load", name="live"))
    assert loaded["status"] == "ok" and loaded["paused"] is False, loaded
    assert loaded["session"]["altered"] is True
    assert _byte_at(_MARK_AT) == "AA", "the load brought the saved machine back"
    released = cast(dict[str, Any], server.resume())
    assert "pc" not in released, released
    running = cast(dict[str, Any], server.state_write("save", name="running"))
    assert running["status"] == "ok" and running["paused"] is True, running
    again = cast(dict[str, Any], server.state_write("load", name="running"))
    assert again["status"] == "ok" and again["paused"] is True, again
    shot = cast(dict[str, Any], server.snapshot(dest=str(tmp_path / "shot.png")))
    assert shot["status"] == "ok" and (tmp_path / "shot.png").stat().st_size > 0, shot
    listed = cast(dict[str, Any], server.state_list())
    names = sorted(str(s["name"]) for s in cast(list[dict[str, Any]], listed["states"]))
    assert names == ["live", "running"], listed
    back = cast(dict[str, Any], server.stop())
    assert back["status"] == "ok" and back["interrupted"] is True, back


def test_find_locates_the_bytes_a_dump_of_the_same_range_starts_with(tmp_path: Path) -> None:
    """Through the tool, against the range `memdump`'s case uses, which holds many distinct."""
    start_ok(session_seconds=90)
    dest = tmp_path / "range.bin"
    dump = cast(dict[str, Any], server.memdump(ref="F000:0000E000", length=256, dest=str(dest)))
    assert dump["status"] == "ok", dump
    head = dest.read_bytes()[:4].hex()
    reply = cast(dict[str, Any], server.find(ref="F000:0000E000", length=256, data_hex=head))
    assert reply["status"] == "ok", reply
    assert reply["hits"][0] == "F000:0000E000" and reply["hits_total"] >= 1, reply
    assert reply["truncated"] is False
    left = [p for p in cast(ds.Session, dstate.STATE.session)._memdump_candidates()
            if p.exists()]
    assert not left, f"the search left its dump behind at {left}"
    short = cast(dict[str, Any], server.find(ref="F000:0000E000", length=2, data_hex=head))
    assert short["status"] == "INVALID" and short["code"] == "bad_argument", short


def test_scan_narrows_to_every_zero_cell_and_closes_once() -> None:
    """The debugger's own scanner, driven end to end over the range that holds ONE value at the."""
    start_ok(session_seconds=90)
    opened = cast(dict[str, Any], server.scan("start", ref="0000:00000400", length=256))
    assert opened["status"] == "ok", opened
    assert opened["hits_total"] == 256 and opened["cell_bytes"] == 1, opened
    again = cast(dict[str, Any], server.scan("start", ref="0000:00000400", length=16))
    assert again["status"] == "INVALID" and "one is open" in again["message"], again
    kept = cast(dict[str, Any], server.scan("filter", operator="=", value=0, limit=400))
    assert kept["status"] == "ok", kept
    assert kept["hits_total"] == 256 and kept["closed"] is False, kept
    assert len(kept["hits"]) == 256, kept["summary"]
    assert kept["hits_total"] == 256 and kept["truncated"] is False, kept["summary"]
    assert kept["hits"][0] == {"seg_off": "0000:00000400", "addr": "0x00000400", "value": "0x00"}
    assert kept["hits"][-1]["seg_off"] == "0000:000004FF"
    wide = cast(dict[str, Any], server.scan("filter", operator="=", value=0x1FF))
    assert wide["status"] == "INVALID" and "is wider than the open scan's" in wide["message"], wide
    again = cast(dict[str, Any], server.scan("filter", operator="=", value=0))
    assert again["iterations"] == kept["iterations"] + 1, (kept["iterations"], again)
    gone = cast(dict[str, Any], server.scan("filter", operator="!", value=0))
    assert gone["status"] == "ok" and gone["closed"] is True and gone["hits_total"] == 0, gone
    assert gone["iterations"] == again["iterations"] + 1, (again["iterations"], gone)
    nothing = cast(dict[str, Any], server.scan("clear"))
    assert nothing["status"] == "ok" and nothing["cleared"] is False, nothing
    orphan = cast(dict[str, Any], server.scan("filter", operator="=", value=0))
    assert orphan["status"] == "INVALID" and 'scan(method="start")' in orphan["message"], orphan
    reopened = cast(dict[str, Any], server.scan("start", ref="0000:00000400", length=16))
    assert reopened["status"] == "ok", reopened
    cleared = cast(dict[str, Any], server.scan("clear"))
    assert cleared["status"] == "ok" and cleared["cleared"] is True, cleared


def test_a_filter_with_no_value_compares_with_the_scan_as_it_opened() -> None:
    """`!` with no value is "changed since the scan OPENED", not since the previous filter:"""
    start_ok(session_seconds=90)
    assert server.write(ref="0050:0200", data_hex="1111111122222222")["verified"] is True
    opened = cast(dict[str, Any], server.scan("start", ref="0050:0200", length=8, cell_bytes=4))
    assert opened["hits_total"] == 2, opened
    server.write(ref="0050:0200", data_hex="33333333")
    once = cast(dict[str, Any], server.scan("filter", operator="!"))
    assert once["hits_total"] == 1 and once["hits"][0]["seg_off"] == "0050:00000200", once
    still = cast(dict[str, Any], server.scan("filter", operator="!"))
    assert still["hits_total"] == 1 and still["iterations"] == once["iterations"] + 1, still
    server.write(ref="0050:0200", data_hex="11111111")
    back = cast(dict[str, Any], server.scan("filter", operator="!"))
    assert back["closed"] is True and back["hits_total"] == 0, back
    assert back["iterations"] == still["iterations"] + 1, back
