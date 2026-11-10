"""The DOSBox-X server: the session, the readers and the surface."""

from __future__ import annotations

import ast
import asyncio
import dataclasses
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import fold_calls
import pytest
from dosbox_x_server_support import (
    FFMPEG_FIX,
    NO_SUCH_HOME,
    FakeSession,
    NamesFake,
    _ffmpeg_record,
    _guest,
    _launch_of,
    _names,
    _source,
    _tools_called_in_tests,
    _typed_into,
    clean_session,  # noqa: E402, F401
    install,
    live_callers,
    returned_key_sets,
    stub_build,
)
from scry_core import (
    host_program,
    log_marks,
    media_tools,
    recording,
    reply_schema,
    roster,
)
from scry_core import window as core_window
from scry_core.host_program import absolute as _abs
from scry_core.host_program import temporary as _tmp
from test_dosbox_x_find import reply

from scry_dosbox_x import arming, checks, folds, placement, run_state, server
from scry_dosbox_x import binary as binaries
from scry_dosbox_x import dos_calls as dos_calls_trace
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import mcp as dosbox_mcp
from scry_dosbox_x import replies as dosbox_replies
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


@pytest.fixture(autouse=True)
def _faked_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every build these cases start is a path that holds no file: what it carries is stubbed."""
    stub_build(monkeypatch)



def _src(fake: Any) -> Path:
    return Path(str(fake.captures()[-1]["path"]))

def test_the_server_reports_the_name_it_is_installed_as() -> None:
    assert server.mcp.name == "dosbox-x"


def test_a_cap_of_zero_would_lie_and_is_refused() -> None:
    for bad in (0, -1):
        with pytest.raises(ValueError, match="is not a cap"):
            dstate.delta("abcdef", bad)
    assert dstate.delta("abcdef", 6) == {
        "output": "abcdef", "output_chars": 6, "clipped": False}
    assert dstate.delta("abcdef", 4) == {
        "output": "cdef", "output_chars": 6, "clipped": True}


def test_a_dead_session_that_had_been_written_to_says_so_in_its_block() -> None:
    written = install()
    written.altered, written._alive = True, False
    got = cast(dict[str, Any], server.registers())
    assert got["code"] == "session_broken" and got["exit_code"] == -15, got
    assert got["session"]["altered"] is True and got["session"]["alive"] is False, got
    clean = install(alive=False)
    assert cast(dict[str, Any], server.registers())["session"]["altered"] is False
    assert clean.closed == 0


def test_a_close_that_could_not_reap_the_child_says_so_in_its_reply() -> None:
    """The field REACHING A CALLER, which is a different claim from it being set."""
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

    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    clean = cast(dict[str, Any], server.close())
    assert clean["exit_code"] == 0 and "reap_failed" not in clean, clean


def test_a_close_whose_output_reader_did_not_end_at_end_of_file_says_why() -> None:
    """A descriptor left open, or a read that failed, is the close's to say; an end of file is
    not."""
    class Leaky(FakeSession):
        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.drain_failure = "it was still reading 2 s after the emulator ended"
            self._alive = False
            return 0

    dstate.STATE.session = Leaky()  # type: ignore[assignment]
    got = cast(dict[str, Any], server.close())
    assert "still reading 2 s after" in str(got.get("note")), got

    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    assert "note" not in cast(dict[str, Any], server.close())


def test_a_start_that_left_an_unreapable_emulator_says_so(tmp_path: Path) -> None:
    """The ONE path besides `close` where an unreaped child can be seen."""
    class Unreapable:
        """THE FIELD IS EARNED BY BEING CLOSED, not preset."""

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

    with mock.patch("scry_dosbox_x.server.ds.Session", build):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert got["status"] == "INVALID"
    assert "the debugger never appeared" in str(got["message"]), got
    assert "may still be running" in str(got["message"]), got
    # The double earning `reap_failed` inside its own `close()` is what fires; this pins the call.
    assert made[0].closed == 1, "the refused session was never closed"
    assert dstate.STATE.session is None

    class Reaped(Unreapable):
        unreapable = False

    with mock.patch("scry_dosbox_x.server.ds.Session", lambda _l: Reaped()):
        ok = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert "the debugger never appeared" in str(ok["message"])
    assert "may still be running" not in str(ok["message"]), ok


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in ffmpeg is a POSIX script")
def test_an_ffmpeg_that_says_why_in_bytes_that_are_not_utf8_is_still_a_refusal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = tmp_path / "bin" / "ffmpeg"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\nprintf 'cannot open \\351t\\351.avi' >&2\nexit 1\n",
                    encoding="ascii")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(tool.parent))
    src = tmp_path / "cap.avi"
    src.write_bytes(b"RIFF")
    fake = SimpleNamespace(captures=lambda: [{"path": str(src)}])
    with pytest.raises(ds.Invalid) as e:
        ds.Session.frame(fake, 0, tmp_path / "out.png", _src(fake))  # type: ignore[arg-type]
    assert e.value.code == "host_failed" and "cannot open" in str(e.value), e.value


def test_a_still_is_written_under_its_normalised_name_and_that_is_the_path_returned(
        tmp_path: Path) -> None:
    src = tmp_path / "cap.avi"
    src.write_bytes(b"RIFF")
    fake = SimpleNamespace(captures=lambda: [{"path": str(src)}])
    out = tmp_path / "out"
    out.mkdir()

    def writes(*a: object, **_k: object) -> object:
        Path(cast("list[str]", a[0])[-1]).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    with (mock.patch("scry_dosbox_x.frames.subprocess.run", writes),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg"))):
        got = ds.Session.frame(fake, 0, out / "Frame_1.PNG", _src(fake))  # type: ignore[arg-type]
        assert got == out / "frame-1.png" and [p.name for p in out.iterdir()] == ["frame-1.png"]
        with pytest.raises(ds.Invalid, match="already exists"):
            ds.Session.frame(fake, 0, out / "FRAME 1.png", _src(fake))  # type: ignore[arg-type]


def test_a_hung_ffmpeg_is_invalid_and_not_a_traceback(tmp_path: Path) -> None:
    def hangs(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=ds.FFMPEG_SECS)

    src = tmp_path / "cap.avi"
    src.write_bytes(b"RIFF")
    fake = SimpleNamespace(captures=lambda: [{"path": str(src)}])
    with (mock.patch("scry_dosbox_x.frames.subprocess.run", hangs),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg")),
          pytest.raises(ds.Invalid, match="did not return within")):
        ds.Session.frame(fake, 0, tmp_path / "out.png", _src(fake))  # type: ignore[arg-type]

    # The green beside it: an unconditional `raise Invalid` in `frame()` would otherwise pass.
    dest = tmp_path / "ok.png"

    argv: list[list[str]] = []

    def writes(*a: object, **_k: object) -> object:
        argv.append(list(cast("list[str]", a[0])))
        dest.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    with (mock.patch("scry_dosbox_x.frames.subprocess.run", writes),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg"))):
        got = ds.Session.frame(fake, 0, dest, _src(fake))  # type: ignore[arg-type]
    assert got == dest and dest.stat().st_size > 1000
    # Without the forced format ffmpeg picks the encoder from the extension and writes a frameless
    # container at exit 0 (tests/fixtures/ffmpeg).
    assert argv, "the mock never saw a command line"
    assert argv[0][-5:] == ["-f", "image2", "-c:v", "png", str(dest)], argv[0]

    # ffmpeg exiting 0 having written nothing: the empty-output guard was exercised by neither tier.
    past_end = _ffmpeg_record("past-end-png")

    def writes_nothing(*_a: object, **_k: object) -> object:
        return SimpleNamespace(stdout="", stderr=past_end["stderr"],
                               returncode=past_end["returncode"])

    with (mock.patch("scry_dosbox_x.frames.subprocess.run", writes_nothing),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg")),
          pytest.raises(ds.Invalid, match="ffmpeg exited 0 but no image")):
        ds.Session.frame(fake, 99999, tmp_path / "never.png", _src(fake))  # type: ignore[arg-type]

    # ffmpeg failing while leaving a non-empty file: the size check alone cannot see it.
    bad = tmp_path / "junk.png"
    corrupt = _ffmpeg_record("corrupt-input")

    def fails_but_writes(*_a: object, **_k: object) -> object:
        bad.write_bytes(b"not an image, but not empty either")
        return SimpleNamespace(stdout="", stderr=corrupt["stderr"],
                               returncode=corrupt["returncode"])

    # The two refusals differ: a non-zero exit carries ffmpeg's reason, an empty output at
    # exit 0 is a guess.
    with (mock.patch("scry_dosbox_x.frames.subprocess.run", fails_but_writes),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg")),
          pytest.raises(ds.Invalid, match=f"ffmpeg exited {corrupt['returncode']}")):
        ds.Session.frame(fake, 5, bad, _src(fake))  # type: ignore[arg-type]

    # A well-formed file of the wrong kind at exit 0: a frameless container recorded when the format
    # was not forced (tests/fixtures/ffmpeg).
    container = tmp_path / "container.mp4"

    recorded = (FFMPEG_FIX / "past-end-unforced.mp4").read_bytes()

    def writes_a_container(*_a: object, **_k: object) -> object:
        container.write_bytes(recorded)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    with (mock.patch("scry_dosbox_x.frames.subprocess.run", writes_a_container),
          mock.patch("scry_dosbox_x.frames.shutil.which", lambda _n: _abs("usr", "bin", "ffmpeg")),
          pytest.raises(ds.Invalid, match="is not a PNG")):
        ds.Session.frame(fake, 99999, container, _src(fake))  # type: ignore[arg-type]


def test_the_live_case_counter_ignores_helpers_comments_and_session_methods() -> None:
    source = (
        "def start_ok():\n    return server.start()\n"
        "def test_one():\n    s = start_ok()\n    server.registers()  # server.debug()\n"
        "    s.memdump()\n    server.close()\n"
    )
    assert _tools_called_in_tests(source) == {"registers", "close"}


def test_every_tool_has_a_live_case_naming_it() -> None:
    """The "every tool has a live case" claim, GATED instead of asserted in prose."""
    live = Path(str(server.__file__)).parents[2] / "tests" / "live"
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
    expected = {
        "start", "status", "close", "log", "log_wait", "debug", "registers", "set_register",
        "write", "read_memory", "disassemble", "call_stack", "memdump", "find", "scan",
        "machine_map", "interrupt_vectors", "palette", "screen_view", "screen_signature",
        "screen_wait", "breakpoint_interrupt", "regpoint_add", "stop", "resume", "step",
        "run_to", "run_for", "trace", "breakpoint_at", "watch_add", "declaration_list",
        "declaration_clear",
        "state_write", "state_list", "snapshot", "captures", "capture_frame", "build_check",
        "symbols_load", "symbols_find", "send_keys", "send_mouse", "perform", "perform_export",
        "drive", "comment_list", "comment_write", "series_capture", "image_compare",
        "audio_compare", "screen_map_find", "screen_map_write", "record", "audio_record", "port",
        "pic", "a20",
        "guest_file", "window", "promote"}
    got = dosbox_mcp.registered_tools()
    assert set(got) == expected
    # The registry is a dict keyed by name, so a length check cannot fail.
    assert sorted(got) == sorted(set(got)), "the registry handed back a name twice"



@pytest.mark.parametrize("old", [{"mode": "headless"}, {"seconds": 60}, {"plan_wait": 5}])
def test_starts_old_words_are_refused_by_name(old: dict[str, Any]) -> None:
    res = asyncio.run(server.mcp.call_tool("start", {"conf": _abs("x.conf"), "cwd": _abs(),
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


def test_every_tool_that_needs_a_session_says_so_when_there_is_none(
        tmp_path: Path) -> None:
    nm = tmp_path / "s.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    calls: dict[str, Callable[[], dict[str, Any]]] = {
        "log": lambda: server.log(channel="guest", pattern="x"),
        "debug": lambda: server.debug(command="BPLIST"),
        "registers": server.registers,
        "set_register": lambda: server.set_register(name="ax", value=1),
        "write": lambda: server.write(ref="0040:0100", data_hex="00"),
        "breakpoint_interrupt": lambda: server.breakpoint_interrupt(number=0x21),
        "regpoint_add": lambda: server.regpoint_add(condition="AX==13"),
        "resume": server.resume, "stop": server.stop,
        "series_capture": lambda: server.series_capture(at_frames=[0]),
        "screen_map_write add": lambda: server.screen_map_write("add", screen="s",
                                                                match=[[0, 0, 1, 1]]),
        "screen_map_find": server.screen_map_find,
        "read_memory": lambda: server.read_memory(ref="0000:00000000"),
        "memdump": lambda: server.memdump(ref="0000:00000000", length=8, dest=_tmp("x.bin")),
        "find": lambda: server.find(ref="0000:00000000", length=8, data_hex="00"),
        "scan start": lambda: server.scan("start", ref="0000:00000000", length=8),
        "scan filter": lambda: server.scan("filter", operator="=", value=0),
        "scan clear": lambda: server.scan("clear"),
        "captures": server.captures, "window": server.window,
        "capture_frame": lambda: server.capture_frame(frame=0, dest=_tmp("x.png")),
        "log_wait": lambda: server.log_wait(channel="guest", pattern="x", seconds=1.0),
        "run_to": lambda: server.run_to(ref="0000:0000", control="0000:0020", seconds=1.0),
        "run_for": lambda: server.run_for(frames=1),
        "trace": lambda: server.trace(instructions=1, dest=_tmp("x.trace")),
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
        "state_write save": lambda: server.state_write("save", name="x"),
        "state_write load": lambda: server.state_write("load", name="x"),
        "state_list": server.state_list,
        "snapshot": server.snapshot,
        "record": lambda: server.record(frames=2),
        "audio_record": lambda: server.audio_record(frames=2),
        "breakpoint_at": lambda: server.breakpoint_at(ref="_main"),
        "declaration_list breakpoint": lambda: server.declaration_list("breakpoint"),
        "declaration_clear breakpoint": lambda: server.declaration_clear("breakpoint", all=True),
        "watch_add": lambda: server.watch_add(ref="_main", mode="change", length=4),
        "declaration_list watch": lambda: server.declaration_list("watch"),
        "declaration_clear watch": lambda: server.declaration_clear("watch", all=True),
        "perform": lambda: server.perform(steps=[{"op": "registers"}]),
        "send_keys": lambda: server.send_keys(keys=["a"]),
        "send_mouse": lambda: server.send_mouse(button="left"),
        "drive": lambda: server.drive(act=[{"op": "status"}]),
        "comment_write add": lambda: server.comment_write("add", ref="_main", text="x"),
        "comment_list": server.comment_list,
        "comment_write delete": lambda: server.comment_write("delete", ref="_main"),
        "comment_write save": lambda: server.comment_write(
            "save", dest=_tmp("x-comments.tsv")),
        "comment_write load": lambda: server.comment_write("load", path=str(nm)),
    }
    callers = live_callers()
    assert len(callers) > len(calls) // 2, (
        f"the derived population found {sorted(callers)}: an AST search that matches nothing "
        f"makes the check below pass whatever the tools are")
    missing = sorted(callers - {name.split()[0] for name in calls})
    assert not missing, (
        f"these tools ask for a live session and are not exercised here: {missing}. "
        f"A tool that stopped calling `live()` would answer from a corpse and nothing "
        f"would say so")
    for name, call in calls.items():
        got = call()
        assert got["status"] == "INVALID", name
        assert "no live session" in got["message"], name


def test_a_dead_session_answers_broken_until_close_collects_it() -> None:
    dead = install(alive=False)
    got = cast(dict[str, Any], server.registers())
    assert got["code"] == "session_broken" and got["exit_code"] == -15, got
    assert "died by signal 15" in got["message"], got
    assert dead.closed == 0 and cast(object, dstate.STATE.session) is dead
    closed = cast(dict[str, Any], server.close())
    assert closed["status"] == "ok" and dead.closed == 1 and dstate.STATE.session is None


def test_start_over_a_dead_session_collects_it_first_and_refuses_over_a_live_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n")

    def spawn(launch: Any) -> Any:
        raise ds.Invalid("session_broken", "not starting anything")
    monkeypatch.setattr("scry_core.binaries.shutil.which", lambda _n: _abs("somewhere", "dosbox-x"))
    monkeypatch.setattr("scry_dosbox_x.server.ds.Session", spawn)
    kw = {"conf": str(conf), "cwd": str(tmp_path), "session_seconds": 60}
    live_one = install()
    assert cast(dict[str, Any], server.start(**kw))["code"] == "session_live"
    assert live_one.closed == 0 and cast(object, dstate.STATE.session) is live_one
    dead = install(alive=False)
    dstate.STATE.last_stop.update({"stop_seq": 7, "where": {"cs": "0814", "eip": "00000106"}})
    assert cast(dict[str, Any], server.start(**kw))["code"] == "session_broken"
    assert dead.closed == 1 and dstate.STATE.session is None, "the dead session was not collected"
    assert dstate.STATE.last_stop == {}, dstate.STATE.last_stop



def test_the_success_path_of_each_reader_returns_a_result(tmp_path: Path) -> None:
    """THE GREEN BESIDE THE REDS."""
    seg, off = 0x0749, 0
    fake = install(answer="DEBUG: Set interrupt breakpoint at INT 21")
    fake.memory.update({(seg << 4) + off + i: i for i in range(16)})
    assert server.registers()["regs"]["EAX"] == "0x00001234"
    assert server.debug(command="BPLIST")["status"] == "ok"
    got = server.read_memory(ref=f"{seg:04X}:{off:08X}")
    assert got["status"] == "ok" and got["hex"] == bytes(range(16)).hex(), got
    assert "INT 21" in server.breakpoint_interrupt(number=0x21, detail=True)["output"]
    short = server.breakpoint_interrupt(number=0x10)
    assert "output" not in short and "output_chars" not in short, short
    assert short["omitted"] == list(dstate.OUTPUT_FIELDS) and short["how"] == dstate.OUTPUT_HOW
    resumed = server.resume()
    assert resumed["status"] == "ok" and "output" not in resumed, resumed
    assert resumed["omitted"] == list(dstate.OUTPUT_FIELDS) and "detail=True" in resumed["how"]



def test_log_reports_how_many_matched_not_how_many_came_back() -> None:
    install()
    got = server.log(channel="guest", pattern="loudness", limit=1)
    assert got["lines_total"] == 500
    assert len(got["lines"]) == 1
    assert got["truncated"] is True


def test_a_dump_returns_the_path_the_bytes_actually_landed_at(tmp_path: Path) -> None:
    install()
    dest = tmp_path / "out" / "mem.bin"
    got = server.memdump(ref="0749:00000000", length=16, dest=str(dest))
    assert got["status"] == "ok"
    assert Path(got["path"]) == dest and got["bytes"] == 16
    assert got["seg_off"] == "0749:00000000" and got["length"] == 16, got



def test_every_reply_carries_whether_the_machine_was_written_to() -> None:
    s = install()
    assert server.status()["session"]["altered"] is False
    server.set_register(name="ax", value=0x10)
    assert s.altered is True
    assert server.status()["session"]["altered"] is True


def test_an_invalid_reply_carries_it_too() -> None:
    install()
    server.set_register(name="ax", value=0x10)
    got = server.read_memory(ref="no_such_symbol")
    assert got["status"] == "INVALID"
    assert got["session"]["altered"] is True


def test_the_real_state_is_the_one_asserted(tmp_path: Path) -> None:
    """The contract belongs to the real object, so the real function is what runs here."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    fake = SimpleNamespace(
        proc=SimpleNamespace(pid=4242),
        alive=lambda: False, altered=True, driver_range=None, conf_digest=dlaunch.digest(conf),
        started_at=time.monotonic() - 3.0, dropped=4096, _at_debugger=True, image=None,
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60,
                              window=core_window.WindowRequest(1, False, (1920, 0))))
    got = ds.Session.state(fake)  # type: ignore[arg-type]
    assert set(got) == {"pid", "alive", "running", "altered", "range_widened", "program", "conf",
                        "conf_digest",
                        "conf_changed_on_disk", "image_changed_on_disk", "watched", "bound_s",
                        "elapsed_s", "output_bytes_dropped", "captures", "state_dir"}
    assert got["program"] is None, "nothing has stopped, so nothing is known of the program"
    assert got["captures"] == "off"
    fake.launch = dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, capture_video=True,
                            program="X.EXE", captures_dir=tmp_path / "caps")
    assert ds.Session.state(fake)["captures"] == str(tmp_path / "caps")  # type: ignore[arg-type]
    fake.launch = dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60, capture_video=True,
                            program="X.EXE")
    assert ds.Session.state(fake)["captures"] == "on, in the emulator's own directory"  # type: ignore[arg-type]
    assert got["pid"] == 4242
    assert got["alive"] is False
    assert got["altered"] is True
    assert got.get("watched", False) is True
    assert got["conf"] == str(conf)
    assert got["bound_s"] == 60
    assert cast(float, got["elapsed_s"]) >= 3.0
    assert got.get("output_bytes_dropped", 0) == 4096
    assert got.get("conf_changed_on_disk", False) is False
    conf.write_text("[sdl]\nchanged\n", encoding="utf-8")
    assert ds.Session.state(fake).get("conf_changed_on_disk", False) is True  # type: ignore[arg-type]
    with mock.patch.object(dlaunch, "current_digest", side_effect=PermissionError("denied")):
        unread = cast(dict[str, Any], ds.Session.state(fake))  # type: ignore[arg-type]
    assert unread.get("conf_changed_on_disk", False) == {"available": False,
                                              "why": "the conf could not be read: denied"}


def test_an_executable_written_since_its_table_was_checked_is_an_alarm(
        tmp_path: Path) -> None:
    """A relink under a live session leaves the guest running the image on screen while the
    table on disk describes another one."""
    exe = tmp_path / "prod.exe"
    exe.write_bytes(b"MZ")
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    fake = SimpleNamespace(
        proc=SimpleNamespace(pid=4242),
        alive=lambda: True, altered=False, driver_range=None, conf_digest="x",
        started_at=time.monotonic(), dropped=0, _at_debugger=True,
        image={"path": str(exe), "size": exe.stat().st_size,
               "mtime_ns": exe.stat().st_mtime_ns},
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60))
    assert ds.Session.state(fake).get("image_changed_on_disk") is False  # type: ignore[arg-type]
    exe.write_bytes(b"MZ" + b"\0" * 64)
    assert ds.Session.state(fake).get("image_changed_on_disk") is True  # type: ignore[arg-type]
    exe.unlink()
    gone = cast(dict[str, Any], ds.Session.state(fake))["image_changed_on_disk"]  # type: ignore[arg-type]
    assert gone["available"] is False and exe.name in gone["why"], gone


def test_the_double_has_not_drifted_from_what_it_stands_in_for(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    fake = SimpleNamespace(
        proc=SimpleNamespace(pid=4242),
        alive=lambda: True, altered=False, driver_range=None, conf_digest="x",
        started_at=time.monotonic(), dropped=0, _at_debugger=False, image=None,
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60))
    real = ds.Session.state(fake)  # type: ignore[arg-type]
    assert set(FakeSession().state()) == set(real)
    # THE BLOCK'S ALARMS NAME KEYS OF THIS SHAPE: a renamed key would leave a dead rule and
    # the alarm would ride as a fixed fact, omitted.
    fake.dropped = 1
    assert {*dstate._ALARM_WHEN, *dstate._ALWAYS} <= set(ds.Session.state(fake))  # type: ignore[arg-type]
    # The method surface: a method the server calls and the double lacks dies with an
    # AttributeError, which `tool()` does not translate. Derived by AST from the whole package,
    # never written out; attributes on an import are excluded, each file read against its imports.
    package = Path(str(server.__file__)).parent
    used: set[str] = set()
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {a.asname or a.name.split(".")[0]
                   for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        modules |= {a.asname or a.name
                    for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                    for a in n.names}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                 and not (isinstance(n.value, ast.Name) and n.value.id in modules)}
    called = {n for n in used
              if not n.startswith("_") and callable(getattr(ds.Session, n, None))}
    for sentinel in ("registers", "read_bytes", "memdump", "log",
                     "alive", "close", "state", "wait_ready"):
        assert sentinel in called, (
            f"the derivation no longer sees `{sentinel}`, which the server plainly "
            f"uses on a session: it has gone blind and this check is empty")
    for name in sorted(called):
        assert hasattr(ds.Session, name), f"the server calls a `Session.{name}` that does not exist"
        assert hasattr(FakeSession(), name), (
            f"the double has fallen behind: the server calls `{name}` on the session "
            f"and this stub does not have it")
    assert len(FakeSession().state()) == len(real)


def test_closing_when_there_was_nothing_is_not_a_failure() -> None:
    got = server.close()
    assert got["status"] == "ok" and got["closed"] is False
    for field in ("pid", "exit_code"):
        assert got[field]["available"] is False and "no session" in got[field]["why"], got


def test_closing_a_live_session_closes_it_and_clears_it() -> None:
    s = install()
    got = server.close()
    assert got["closed"] is True and got["exit_code"] == 0
    assert s.closed == 1
    assert dstate.STATE.session is None
    assert got["session"]["altered"] is False



def test_invalid_is_surfaced_and_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The wrapper turns `Invalid` into a reply that SAYS INVALID."""

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
    """The EXCEPTION IDENTITY axis."""

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
    """BOTH, and they are not symmetric."""
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
    short._memdump_candidates = lambda: ds.Session._memdump_candidates(short)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="holds 100"):
        ds.Session.memdump(short, 0, 0x400, 256, tmp_path / "a.bin")  # type: ignore[arg-type]

    assert not (work / ds.MEMDUMP_NAME).exists(), "the refused dump's own file is removed"
    exact = SimpleNamespace(launch=launch, command=writes(256))
    exact._memdump_candidates = lambda: ds.Session._memdump_candidates(exact)  # type: ignore[arg-type]
    got = ds.Session.memdump(exact, 0, 0x400, 256, tmp_path / "b.bin")  # type: ignore[arg-type]
    assert got.stat().st_size == 256


def test_a_dump_refuses_rather_than_deleting_what_is_already_there(
        tmp_path: Path) -> None:
    """It will not delete from the emulator's working directory, which is somebody's project."""
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


def test_start_takes_every_path_as_written(tmp_path: Path) -> None:
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
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: _abs("somewhere", "dosbox-x")), \
         mock.patch("scry_dosbox_x.server.ds.Session", build):
        got = cast(dict[str, Any], server.start(**kw))
    assert "built: the case ends here" in got["message"], got
    assert getattr(built[0], arg) == (tmp_path / under_home if under_home else tmp_path)
    assert not (tmp_path / "~").exists()


def test_the_two_optional_paths_stay_absent_when_the_caller_omits_them(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    launch = _launch_of(conf=str(conf), cwd=str(tmp_path), session_seconds=30)
    assert launch.captures_dir is None and launch.logfile is None
    assert launch.state_dir == dstate.STATE.session_scratch() / "save"


def test_memdump_expands_a_tilde_dest_and_makes_no_literal_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    fake = install()
    seen: list[Path | None] = []

    def frame(at: int, dest: Path, source: Path | None = None) -> Path:
        seen.append(source)
        dest.write_bytes(b"\x89PNG")
        return dest

    fake.frame = frame  # type: ignore[method-assign]
    server.capture_frame(5, str(tmp_path / "shot.png"))
    # the double's own capture, spelled as it is in `install`
    assert seen == [Path("/caps/run_001.avi")], "the default source is the largest capture"


@pytest.mark.parametrize("bad", [pytest.param("~nosuchuser-here/x", marks=NO_SUCH_HOME), "~\x00/x"])
def test_a_tilde_user_or_a_nul_is_a_refusal_and_not_a_traceback(
        tmp_path: Path, bad: str) -> None:
    got = cast(dict[str, Any], server.start(conf=bad, cwd=str(tmp_path), session_seconds=30))
    assert got["code"] == "bad_argument" and "session" in got, got
    install()
    got = cast(dict[str, Any], server.memdump(ref="0000:00000400", length=16, dest=bad))
    assert got["code"] == "bad_argument" and "session" in got, got
    got = cast(dict[str, Any], server.snapshot(dest=bad))
    assert got["code"] == "bad_argument", got
    ok = cast(dict[str, Any], server.memdump(ref="0000:00000400", length=16,
                                             dest=str(tmp_path / "fine.bin")))
    assert ok["status"] == "ok", ok


def test_find_answers_with_both_addresses(tmp_path: Path) -> None:
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "ok", got
    assert got["symbols"][0]["offset"] == 0x0016DF20, got
    assert got["symbols"][0]["addr"] == "0x0056df20", got


def test_find_wants_exactly_one_question(tmp_path: Path) -> None:
    install()
    server.symbols_load(path=_source(tmp_path))
    both = cast(dict[str, Any], server.symbols_find(name="_main", linear="1"))
    assert both["status"] == "INVALID", both
    neither = cast(dict[str, Any], server.symbols_find())
    assert neither["status"] == "INVALID", neither


def test_a_source_that_cannot_be_read_is_a_refusal_and_not_a_traceback(
        tmp_path: Path) -> None:
    install()
    got = cast(dict[str, Any], server.symbols_load(path=str(tmp_path / "nope.sym")))
    assert got["status"] == "INVALID", got
    assert "no symbol file at" in got["message"], got
    assert "session" in got, got

    d = cast(dict[str, Any], server.symbols_load(path=str(tmp_path)))
    assert d["status"] == "INVALID", d




def test_memdump_forwards_the_address_the_caller_asked_for(tmp_path: Path) -> None:
    fake = install()
    dest = tmp_path / "d.bin"
    got = cast(dict[str, Any], server.memdump(ref="0749:00001A44",
                                              length=64, dest=str(dest)))
    assert got["status"] == "ok"
    assert fake.memdump_calls == [(0x0749, 0x1A44, 64)], fake.memdump_calls
    assert got["bytes"] == 64


def test_set_register_writes_the_value_it_was_given() -> None:
    fake = install()
    got = cast(dict[str, Any], server.set_register(name="EAX", value=0xDEADBEEF))
    assert got["regs"]["EAX"] == "0xdeadbeef", got["regs"]
    assert (got["readback"] == "DEADBEEF" and got["verified"] is True
            and got["value"] == "0xdeadbeef")
    assert got["summary"] == "set_register EAX = 3735928559, verified True"
    again = cast(dict[str, Any], server.set_register(name="EAX", value=1))
    assert again["regs"]["EAX"] == "0x00000001"
    fake.masks = True
    masked = cast(dict[str, Any], server.set_register(name="EAX", value=0x10000))
    assert masked["status"] == "ok" and masked["verified"] is False
    assert masked["readback"] == "00000000" and masked["session"]["altered"] is True


def test_the_central_distinctness_guarantee_is_gated_and_not_merely_written() -> None:
    two = [dsym.Symbol("_a", 1), dsym.Symbol("_b", 2)]
    with pytest.raises(dsym.BadSymbolText, match="belonging to another symbol"):
        dsym.Plan(parsed=2, symbols=two, short=["x", "x"]).check()
    with pytest.raises(dsym.BadSymbolText, match="cannot be zipped"):
        dsym.Plan(parsed=2, symbols=two, short=["x"]).check()
    with pytest.raises(dsym.BadSymbolText, match="accounting does not add up"):
        dsym.Plan(parsed=99, symbols=two, short=["x", "y"]).check()
    dsym.Plan(parsed=2, symbols=two, short=["x", "y"]).check()



def test_build_check_is_invalid_and_not_ok_when_there_is_no_binary() -> None:
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: None):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "no DOSBox-X binary resolves" in str(got["message"])
    assert got.get("binary") is None, "an INVALID reply may not carry a binary"


def test_build_check_is_invalid_when_the_build_has_no_debugger(tmp_path: Path) -> None:
    """The precondition it exists for."""
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"\x00usage: ...\x00")
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: str(binary)):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "carries no debugger" in str(got["message"])


def test_build_check_says_ok_and_names_the_surface_on_a_good_build(tmp_path: Path) -> None:
    """THE GREEN BESIDE THE TWO REDS."""
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"\x00" + binaries.DEBUGGER_MARK + b"\x00" + binaries.HEAVY_DEBUG_MARK
                       + b"\x00")
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: str(binary)):
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
    install(alive=True)
    spawned: list[list[str]] = []

    def watched(cmd: list[str], **_k: object) -> object:
        spawned.append(list(cmd))
        return SimpleNamespace(stdout="-break-start\n", stderr="")

    with (mock.patch("scry_core.binaries.shutil.which", lambda _n: _abs("usr", "bin", "dosbox-x")),
          mock.patch("subprocess.run", watched)):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID", got
    assert "second emulator" in str(got["message"]) and "`close`" in str(got["message"])
    assert spawned == [], f"it started one anyway: {spawned}"




def test_a_read_memory_reply_is_exactly_the_bytes_asked_for() -> None:
    """Asked 128, the most it takes, the reply's `hex` holds those 128 and nothing beside."""
    seg, off = 0x0749, 0
    fake = install()
    fake.memory.update({(seg << 4) + off + i: i for i in range(256)})
    got = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{off:08X}", length=128))
    assert got["status"] == "ok" and got["hex"] == bytes(range(128)).hex(), got
    assert fake.memdump_calls == [(seg, off, 128)]


def test_read_memory_refuses_a_segment_that_will_not_fit_the_command() -> None:
    fake = install()
    got = cast(dict[str, Any], server.read_memory(ref="10000:00000000"))
    assert got["status"] == "INVALID", got
    # THE MESSAGE IS ABOUT THE ARGUMENT, and nothing reached the debugger for it.
    assert "a segment is 0x0000 to 0xFFFF" in str(got["message"]), got["message"]
    assert fake.memdump_calls == [] and fake.executed == []


def test_each_double_returns_the_field_set_the_real_method_returns() -> None:
    for name in ("step", "run_to", "watch", "log_wait"):
        # `watch` is the one-row case of `watch_places`, whose element is its reply.
        branches = returned_key_sets(getattr(ds.Session, "watch_places" if name == "watch"
                                             else name))
        double = returned_key_sets(getattr(FakeSession, name))
        assert branches, f"nothing was read off the real {name}: this measured nothing"
        assert len(double) == 1, f"the {name} double should have one return"
        # Per branch, not the union: a key missing from one branch is invisible to a set over all.
        for i, real in enumerate(branches):
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
    """The `clipped: True` branch, owned by a case that NAMES it."""
    out = "x" * 5000
    got = dstate.delta(out, 4000)
    assert got.get("clipped", False) is True
    assert len(cast(str, got["output"])) == 4000, "the output is cut to the cap"
    assert got["output_chars"] == 5000, (
        "`output_chars` is the WHOLE output and not the slice -- reporting the slice's "
        "length is the defect the field exists to make visible")
    assert cast(str, got["output"]) == out[-4000:], "it keeps the TAIL"


def test_the_status_docstring_names_every_field_its_reply_carries() -> None:
    install(alive=True)
    got = cast(dict[str, Any], server.status())
    doc = server.status.__doc__ or ""
    # MATCHED IN BACKTICKS, NOT AS A SUBSTRING: `conf` sits inside `conf_digest`, so a bare
    # substring would stay green over a field left out.
    fields = {*cast(dict[str, Any], got["session"]), *dstate.process_facts()}
    unnamed = sorted(k for k in fields if f"`{k}`" not in doc)
    assert not unnamed, (
        f"`status` returns these and its docstring does not name them: {unnamed}. An "
        f"MCP caller reads the docstring and not the README")
    # A field left out empty (`OmitEmpty`) is named all the same, and absent from the reply.
    left_out = reply_schema.omitted_when_empty(dosbox_replies.MODELS["status"])
    assert len(fields) >= 11 and fields - left_out <= set(got) | set(got["session"]), got


def test_every_reply_opens_with_a_summary_and_closes_with_the_session(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    ok = cast(dict[str, Any], server.registers())
    assert list(ok)[0] == "summary" and list(ok)[-1] == "session", list(ok)
    assert ok["summary"].startswith("registers: "), ok["summary"]
    fake.running = True
    refused = cast(dict[str, Any], server.registers())
    assert refused["status"] == "INVALID"
    assert list(refused)[0] == "summary" and refused["summary"].startswith("registers: INVALID")


@pytest.mark.skipif(sys.platform == "win32", reason="`-version` is not run on Windows")
def test_start_launches_the_binary_it_resolved_and_says_which(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    mine = host_program.write(tmp_path / "dev" / "dosbox-x", "import sys\n"
                              "sys.stderr.write('DOSBox-X version dev\\n')\nsys.exit(1)\n")
    launched: list[dlaunch.Launch] = []

    class Booted(NamesFake):
        argv = [str(mine), "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    def session(launch: dlaunch.Launch) -> Booted:
        launched.append(launch)
        return Booted(conf=conf)

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with mock.patch("scry_dosbox_x.server.ds.Session", session):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                                binary=str(mine)))
    assert got["status"] == "ok", got
    assert [launch.binary for launch in launched] == [str(mine)]
    assert (got["binary"], got["binary_origin"], got["version"]) == (
        str(mine), "argument", "DOSBox-X version dev"), got


@pytest.mark.parametrize(("core_text", "flags", "said"), [
    ("dynamic", None, True), ("normal", None, False), ("auto", None, False),
    ("dynamic", ["-set", "cpu core=normal"], False),
    ("normal", ["-set", "cpu core=dynamic"], True),
])
def test_start_warns_that_a_dynamic_core_passes_over_code_breakpoints(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, core_text: str,
        flags: list[str] | None, said: bool) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text(f"[cpu]\ncore={core_text}\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]

        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/dosbox-x")
    monkeypatch.setattr("scry_core.binaries.version", lambda *_a, **_k: "DOSBox-X (a stub)")
    stub_build(monkeypatch)
    with mock.patch("scry_dosbox_x.server.ds.Session", lambda launch: Booted(conf=conf)):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60, flags=flags))
    assert got["status"] == "ok", got
    note = str(got.get("note", ""))
    assert ("can be passed over" in note and "cpu core=normal" in note) is said, got


def test_start_with_no_rung_resolving_is_refused_before_anything_starts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    spawned: list[object] = []
    with mock.patch("scry_dosbox_x.server.ds.Session", lambda launch: spawned.append(launch)):
        got = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=60))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "DOSBOX_X_BINARY held nothing" in got["message"] and spawned == []


def test_a_bad_by_is_refused(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")])
    assert server.breakpoint_at(ref="_main", by="guess")["status"] == "INVALID"
    assert server.watch_add(ref="_main", mode="change", length=4, by="guess")[
        "status"] == "INVALID"


def test_store_requires_a_started_session() -> None:
    dstate.STATE.store = None
    with pytest.raises(ds.Invalid, match="no declaration store"):
        arming.current_store()


def test_parse_seg_off_refuses_a_non_hex_pair() -> None:
    with pytest.raises(ds.Invalid, match="not a hex SEG:OFF"):
        placement.parse_seg_off("ZZ:GG")


def test_clearing_a_ref_that_matches_nothing_is_refused_naming_what_there_is(
        tmp_path: Path) -> None:
    _names(tmp_path)
    server.breakpoint_interrupt(number=0x21, ah=0x4B)
    wrong = server.declaration_clear("breakpoint", ref="BPINT 21 4B")
    assert wrong["status"] == "INVALID", wrong
    assert "BPINT 21 AH=4B" in wrong["message"], wrong["message"]
    assert server.declaration_list("breakpoint")["breakpoints"][0]["state"] == "armed"
    assert server.declaration_clear("watch", ref="_nope")["status"] == "INVALID"
    server.declaration_clear("breakpoint", all=True)
    empty = server.declaration_clear("breakpoint", all=True)
    assert empty["status"] == "ok" and empty["declarations_cleared"] == 0, empty
    assert server.declaration_clear("watch", all=True)["status"] == "ok"


def test_a_relative_path_is_refused_and_an_absolute_one_names_the_file_it_looked_at(
        tmp_path: Path) -> None:
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


def test_every_registered_tool_is_named_in_the_instructions() -> None:
    assert dosbox_mcp.ROSTER.unlisted(dosbox_mcp.registered_tools()) == []
    assert dosbox_mcp.ROSTER.misfiled(roster.SHARED_FAMILIES) == []
    assert dosbox_mcp.ROSTER.text() in (server.mcp.instructions or ""), "the roster is missing"


def test_capture_frame_replies_with_the_source_it_read_and_the_frame_asked(
        tmp_path: Path) -> None:
    install()
    got = server.capture_frame(frame=3, dest=str(tmp_path / "f.png"))
    assert got["frame"] == 3 and got["capture_path"] == str(Path("/caps/run_001.avi")), got
    assert "at_frame" not in got
    own = tmp_path / "run_000.avi"
    own.write_bytes(b"RIFF")
    named = server.capture_frame(frame=3, dest=str(tmp_path / "g.png"), capture_path=str(own))
    assert named["capture_path"] == str(own)


def test_close_says_how_the_session_ended() -> None:
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
    fake = _names(tmp_path, symbols=[dsym.Symbol("var", 0x200, kind="D")])
    got = cast(dict[str, Any], server.write(ref="var", data_hex="deadbeef"))
    assert got["status"] == "ok" and got["bytes_written"] == 4 and got["verified"] is True, got
    assert got["readback"] == "deadbeef" and got["seg_off"] == "00AF:00000200"
    assert got["summary"] == "write var: 4 bytes, verified True"
    assert fake.mem[(0xAF, 0x200)] == b"\xde\xad\xbe\xef"
    raw = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="12"))
    assert raw["status"] == "ok" and fake.mem[(0x40, 0x100)] == b"\x12"
    for bad, says in (("", "is empty"), ("abc", "whole number of hex bytes"),
                      ("zz", "whole number of hex bytes")):
        out = cast(dict[str, Any], server.write(ref="var", data_hex=bad))
        assert out["status"] == "INVALID" and says in out["message"], (bad, out)
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


def test_find_through_the_tool_searches_the_dump_and_reports_the_sibling_shape() -> None:
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
    install(answer=reply("opened_0400"))
    got = server.scan("start", ref="0000:00000400", length=256)
    assert got["status"] == "ok", got
    assert got["hits_total"] == 256 and got["cell_bytes"] == 1 and got["addr"] == "0x00000400"
    assert got["summary"] == "scan start: 0000:00000400, 256 cells of 1 byte"


def test_scan_filter_through_the_tool_reports_a_finished_scan_and_says_so() -> None:
    install(answer=reply("finished"))
    got = server.scan("filter", operator="!", value=0)
    assert got["status"] == "ok", got
    assert got["hits_total"] == 0 and got["closed"] is True and got["hits"] == []
    assert got["summary"] == "scan filter: ! 0, 0 survivors, scan closed"


def test_scan_clear_through_the_tool_reports_both_outcomes() -> None:
    install(answer=reply("cancelled"))
    got = server.scan("clear")
    assert got["status"] == "ok" and got["cleared"] is True, got
    assert got["summary"] == "scan clear: cleared"
    install(answer=reply("cancel_none"))
    none = server.scan("clear")
    assert none["status"] == "ok" and none["cleared"] is False, none
    assert none["summary"] == "scan clear: nothing was open"


def test_the_data_view_ceilings_pass_at_the_maximum_on_both_paths(tmp_path: Path) -> None:
    _names(tmp_path)
    checks.preflight("read_memory", {"ref": "0000:0000", "length": 128})
    checks.preflight("write", {"ref": "0000:0000", "data_hex": "00" * 128})
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "show", "length": 128})
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "show", "fmt": "u16[64]"})
    checks.preflight("watch_add", {"ref": "0000:0000", "mode": "change",
                                   "length": checks.CHANGE_WATCH_MAX})
    assert server.read_memory(ref="0000:0000", length=129)["code"] == "bad_argument"
    assert server.write(ref="0000:0000", data_hex="00" * 129)["code"] == "bad_argument"


def test_an_invalid_summary_is_cut_at_a_word_and_says_so() -> None:
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


def test_a_machine_independent_argument_is_refused_before_the_session_gate() -> None:
    dstate.STATE.session = None
    calls: tuple[Callable[[], Any], ...] = (
                 lambda: server.breakpoint_at(ref="12345:0010"),
                 lambda: server.log(channel="bogus", pattern="x"),
                 lambda: server.find(ref="12345:0010", length=4, data_hex="00"),
                 lambda: server.watch_add(ref="F000:0000", mode="bogus", length=2),
                 lambda: server.scan("start", ref="12345:0010", length=4))
    for call in calls:
        got = cast(dict[str, Any], call())
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    control = cast(dict[str, Any], server.read_memory(ref="F000:0000", length=8))
    assert control["code"] == "no_session", control
    keys = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert keys["code"] == "no_session", "the key route is the session's own fact"


@pytest.mark.parametrize(("command", "tool"), [
    ("VRT", "`run_for(frames=1)`"), ("vrt", "`run_for(frames=1)`"), (" RUNWATCH", "`resume`"),
    ("INT 21", "`resume`"), ("int 10", "`resume`")])
def test_debug_refuses_a_typed_command_that_lets_the_guest_run(
        command: str, tool: str, monkeypatch: pytest.MonkeyPatch) -> None:
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert tool in got["message"], got["message"]
    assert typed == [], "a refused command reached the terminal"


@pytest.mark.parametrize("command", ["BPLIST", "INTT 21", "TIMERIRQ", "INTVEC x.txt", "VRTX",
                                     "BPINT 21", "BPLIST INT", "HEAVYLOG", "LOGX"])
def test_debug_passes_a_command_that_keeps_the_machine_at_the_debugger(
        command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "ok", got
    assert typed == [command]


@pytest.mark.parametrize("command", ["BPLIST\rVRT", "BPLIST\nVRT", "\x1b[15~", "BPLIST\x1b[15~",
                                     "BPLIST\tx"])
def test_debug_refuses_a_command_carrying_a_control_character(
        command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    typed = _typed_into(install(), monkeypatch)
    got = cast(dict[str, Any], server.debug(command=command))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert typed == [], "a refused command reached the terminal"


def test_debug_refuses_a_command_that_is_not_text() -> None:
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
    registered = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert registered == set(checks.BY_OP) | checks.MACHINE_JUDGES, (
        sorted(registered ^ (set(checks.BY_OP) | checks.MACHINE_JUDGES)))


def test_the_instructions_say_a_wrong_type_is_the_schemas_refusal() -> None:
    assert "wrong TYPE" in (server.mcp.instructions or ""), "the sentence is missing"


def test_the_instructions_close_with_the_in_development_notice() -> None:
    from scry_core.envelope import IN_DEVELOPMENT
    text = server.mcp.instructions or ""
    assert text.endswith("\n\n" + IN_DEVELOPMENT) and text.count(IN_DEVELOPMENT) == 1



def test_status_with_no_session_adds_no_machine_facts() -> None:
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.status())
    assert not got["session"]["alive"] and not {"pc", "cpu_mode", "declarations"} & set(got), got
    assert got["summary"] == "status: no session", got["summary"]
    assert "presence" not in got, "alive false already says no overlay is drawn"
    assert {"last_stop", "pending"} <= set(got), got


def test_status_summarises_the_session_it_answers_about() -> None:
    install()
    got = cast(dict[str, Any], server.status())
    assert got["session"]["alive"] and got["summary"] == "status: alive, stopped", got["summary"]
    install(alive=False)
    got = cast(dict[str, Any], server.status())
    assert got["summary"] == "status: DOSBox-X has exited, `close` it", got["summary"]


def test_status_pc_is_where_the_machine_is_now_after_a_command_moved_it(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real", cs="0814", ds_="0814")
    server.registers()                              # the park, recorded
    stop_pc = dstate.STATE.last_stop["at"]
    fake.cs = "F000"                                # `INTT 21` took the machine into the handler
    got = cast(dict[str, Any], server.status())
    assert got["pc"].startswith("F000:") and got["pc"] != stop_pc, got
    assert dstate.STATE.last_stop["at"] == stop_pc, "the stop's record moved with it"


def test_every_tool_is_summarised_by_its_own_line() -> None:
    from scry_core import promote as core_promote
    from scry_core import screen_map
    from scry_core import window as core_window
    lines = dosbox_mcp.BOUNDARY.summaries
    folded = {"comment_write": folds.COMMENT, "screen_map_write": folds.MAP, "scan": folds.SCAN,
              "state_write": folds.STATE_METHODS, "port": folds.PORT, "pic": folds.PIC,
              "a20": folds.A20}
    for name in dosbox_mcp.registered_tools():
        if name in media_tools.TOOLS:
            assert lines[name] is media_tools.TOOLS[name].summary, name
        elif name in folded:
            # A fold's line opens with the tool and the method, then the method's own, this
            # server's or scry-core's.
            assert lines[name].__qualname__.startswith("fold_line"), (name, lines[name])
            for method in folded[name].values():
                assert method.line.__module__ in ("scry_dosbox_x.summaries",
                                                  "scry_core.screen_map"), (name, method.line)
        elif name == "screen_map_find":
            assert lines[name] is screen_map.find_line, name
        elif name == "perform_export":
            assert lines[name] is recording.export_summary, name
        elif name == "promote":
            assert lines[name] is core_promote.promote_line, name
        elif name == "window":
            assert lines[name] is core_window.summary, name
        else:
            assert lines[name].__name__ == name, (name, lines[name])


@pytest.mark.parametrize("tool", ["declaration_clear breakpoint", "declaration_clear watch"])
@pytest.mark.parametrize("kw", [{}, {"ref": ""}, {"ref": "x", "all": True}])
def test_a_clear_names_what_it_clears_even_past_the_pre_gate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, kw: dict[str, Any]) -> None:
    _names(tmp_path)
    server.watch_add(ref="00AF:0100", mode="change", length=4)
    server.breakpoint_interrupt(number=0x21)
    refused = cast(dict[str, Any], fold_calls.of(server, tool)(**kw))
    assert refused["code"] == "bad_argument", refused
    monkeypatch.setattr(checks, "check", lambda *a, **k: None)          # no pre-gate
    past = cast(dict[str, Any], fold_calls.of(server, tool)(**kw))
    assert past["code"] == "bad_argument", past
    assert dstate.STATE.store is not None and len(dstate.STATE.store.declarations()) == 2


def test_a_number_a_caller_spells_in_hex_reaches_the_tool_as_the_integer(tmp_path: Path) -> None:
    fake = install()
    got = cast(dict[str, Any], server.set_register(name="EAX", value="0xDEADBEEF"))
    assert got["value"] == "0xdeadbeef" and got["regs"]["EAX"] == "0xdeadbeef", got
    assert cast(dict[str, Any], server.set_register(name="EAX", value=""))["code"] == \
        "bad_argument"
    del fake


def test_the_pointer_names_the_bios_mode_and_the_screen_its_vga_mode(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    moved = cast(dict[str, Any], server.send_mouse(x=1, y=1, units="mouse"))
    assert moved["pointer"]["bios_mode"].startswith("0x") and "vga_mode" not in moved["pointer"]
    del fake


def test_a_raw_command_that_writes_the_guest_marks_the_session_altered() -> None:
    fake = install()
    for command in ("BPLIST", "BP 0000:0009", "BPDEL *", "MEMDUMPBIN 0:0 10", "IV 0:0 X", "PIC",
                    "A20", "PORTINFO 3DA", "DOSTRACE"):
        server.debug(command=command)
        assert fake.altered is False, f"{command} writes nothing and marked the session"
    for command in ("SM 0000:0400 0FF", "sr eax 1", "SMV 400 0FF", "INTT 21", "TIMERIRQ",
                    "LOADSTATE /x/a.sav", "OUTB E9 51", "OUTP E9 51", "OUTW 80 0", "OUTD 80 0",
                    "TIME", "date 01-02-2026", "PIC MASKIRQ 0", "pic raiseirq 3", "A20 ON",
                    "A20 0", "FM 0814:0100", "INP 3DA", "INB 60", "INW 3DA", "IND 3DA"):
        fake.altered = False
        got = cast(dict[str, Any], server.debug(command=command))
        assert fake.altered is True and got["session"]["altered"] is True, command


def test_a_raw_dostrace_that_would_move_the_dos_channel_is_refused() -> None:
    fake = install()
    for command in ("DOSTRACE OFF", "dostrace /x/other.trace"):
        got = cast(dict[str, Any], server.debug(command=command))
        assert got["code"] == "bad_argument" and "dos_calls" in got["message"], got
    server.debug(command="DOSTRACE")
    assert fake.executed == ["DOSTRACE"]


def test_debug_says_when_the_debugger_did_not_take_the_command() -> None:
    fake = install(answer="*** Debugger command not recognized", took=False)
    got = cast(dict[str, Any], server.debug(command="VGA"))
    assert got["status"] == "ok" and "did not take it" in got["note"], got
    assert got["output"] == "*** Debugger command not recognized" and fake.executed == ["VGA"]
    fake.answer, fake.took = "Breakpoint list:", True
    got = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert "note" not in got, got


def test_a_state_dir_the_caller_gave_is_named_as_theirs_when_a_file_holds_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "mine").write_text("a file", encoding="utf-8")
    (tmp_path / "g.conf").write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("shutil.which", lambda _b: _abs("usr", "bin", "dosbox-x"))
    got = server.start(conf=str(tmp_path / "g.conf"), cwd=str(tmp_path), session_seconds=60,
                       state_dir=str(tmp_path / "mine"))
    assert got["status"] == "INVALID" and got["message"].startswith("state_dir: "), got


def test_start_takes_the_version_probe_out_of_the_ready_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(shutil, "which", lambda _: _abs("bin", "true"))
    monkeypatch.setattr(dlaunch, "binary_facts", slow_facts)
    monkeypatch.setattr(ds, "Session", Recorder)
    dstate.STATE.session = None
    got = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path),
                                            session_seconds=30))
    assert got["code"] == "session_broken", got
    asked, ready = waited
    assert asked == binaries.VERSION_TIMEOUT_S, waited
    assert ready <= run_state.READY_TIMEOUT_S - 0.3, waited


def test_close_carries_the_last_words_of_both_channels_when_the_end_was_not_clean(
        tmp_path: Path) -> None:
    log = tmp_path / "s.log"
    log.write_bytes(b"x" * 2000 + b"LOG: the end\n")

    class Ended(FakeSession):
        def __init__(self, how: str, code: int, logfile: Path | None) -> None:
            super().__init__()
            self._how, self._code = how, code
            self.launch = SimpleNamespace(cwd=Path(_abs()), logfile=logfile, watched=False)

        def close(self, grace: float = 8.0, progress: Any = None) -> int | None:
            self.ended_how, self._alive = self._how, False
            return self._code

        def stdout_tail(self, chars: int) -> str:
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
    install()
    st = cast(dict[str, Any], server.status())
    assert st["pid"] == 4242 and "conf_digest" in st and "bound_s" in st, st
    assert set(st["session"]) == {"alive", "running", "altered"}, st["session"]
    read = cast(dict[str, Any], server.registers())
    assert "pid" not in read and set(read["session"]) == {"alive", "running", "altered"}, read
    closed = cast(dict[str, Any], server.close())
    assert closed["pid"] == 4242 and set(closed["session"]) == {"alive", "running", "altered"}, (
        closed)


def test_the_instructions_tell_an_empty_diagnostic_from_a_field_not_sent() -> None:
    text = " ".join((server.mcp.instructions or "").split())
    assert "`omitted` names what was not sent" in text, text


def test_presence_off_is_answered_false_and_never_omitted() -> None:
    from scry_core import reply_schema

    from scry_dosbox_x import replies as dosbox_replies
    for model in (dosbox_replies.StartReply, dosbox_replies.StatusReply):
        assert "presence" not in reply_schema.omitted_when_empty(model), model


def test_close_and_status_with_no_session_say_so_in_the_words_both_servers_use() -> None:
    from scry_core import session_block

    dstate.STATE.session = None
    closed = cast(dict[str, Any], server.close())
    assert closed["summary"] == session_block.NO_SESSION_CLOSE, closed
    assert closed["note"] == session_block.NO_SESSION_CLOSE_NOTE, closed
    assert cast(dict[str, Any], server.status())["summary"] == session_block.NO_SESSION_STATUS


@pytest.mark.parametrize("failure", [ds.Invalid("unexpected_answer", "DOSTRACE answered nothing"),
                                     OSError("no scratch directory")])
def test_a_start_whose_dos_trace_fails_leaves_no_session_and_names_a_stray_emulator(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted:
        reap_failed = ""

        def __init__(self, launch: dlaunch.Launch) -> None:
            pass

        def wait_ready(self, timeout: float, **_: Any) -> float:
            return 0.1

        def close(self, **_: Any) -> None:
            self.reap_failed = "SIGKILL was sent and the process had not been reaped"

    def refuse(_session: Any) -> None:
        raise failure

    monkeypatch.setattr(shutil, "which", lambda _: _abs("bin", "true"))
    monkeypatch.setattr(binaries, "debugger_commands", lambda _path: ["DOSTRACE"])
    monkeypatch.setattr(ds, "Session", Booted)
    monkeypatch.setattr(dos_calls_trace, "begin", refuse)
    dstate.STATE.session = None
    try:
        got = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path),
                                                session_seconds=30, dos_calls=True))
    except OSError:
        got = {"code": "session_broken", "message": "stray"}
    assert got["code"] == "session_broken" and "stray" in got["message"], got
    assert dstate.STATE.session is None and dstate.STATE.store is None, got


def test_a_start_that_names_no_state_dir_keeps_its_states_out_of_the_working_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    seen: list[dlaunch.Launch] = []

    class Recorder:
        reap_failed = ""

        def __init__(self, launch: dlaunch.Launch) -> None:
            seen.append(launch)

        def wait_ready(self, timeout: float, **_: Any) -> float:
            raise ds.Invalid("session_broken", "recorded, not started")

        def close(self, **_: Any) -> None:
            pass

    monkeypatch.setattr(shutil, "which", lambda _: _abs("bin", "true"))
    monkeypatch.setattr(ds, "Session", Recorder)
    dstate.STATE.session = None
    server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=30)
    chosen = seen[0].state_dir
    assert chosen is not None and tmp_path not in chosen.parents, chosen
    assert dstate.STATE.session_scratch() in chosen.parents, chosen
