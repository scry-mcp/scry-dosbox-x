"""What the session guarantees, held to fixtures; each refusal has a green beside it."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from channel_double import Machine, protected, session_over
from dosbox_x_server_support import CASED_PATHS
from scry_core import guardian
from scry_core import vocabulary as vocab
from scry_core import window as core_window
from scry_core.host_program import MODE_BITS
from scry_core.host_program import absolute as _abs
from test_dosbox_x_spawn import Child
from test_dosbox_x_stub_link import REPORT, Stub

from scry_dosbox_x import conf as dconf
from scry_dosbox_x import grammar, inputs, lifecycle, stepping, stub_link
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import process as dprocess
from scry_dosbox_x import session as ds
from scry_dosbox_x import symbols as dsym


def _free_port() -> int:
    """A port nothing holds right now, for a case that names one."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def conf(tmp_path: Path) -> Path:
    p = tmp_path / "guest.conf"
    p.write_text("[sdl]\n[autoexec]\nGAME.EXE\n", encoding="utf-8")
    return p


def launch(conf: Path, **over: object) -> dlaunch.Launch:
    base: dict[str, object] = {"conf": conf, "cwd": conf.parent, "seconds": 60}
    base.update(over)
    return dlaunch.Launch(**base)  # type: ignore[arg-type]


def pair_at(argv: list[str], value: str) -> bool:
    """Is `value` immediately after a `-set`?"""
    return any(argv[i] == "-set" and argv[i + 1] == value
               for i in range(len(argv) - 1))


def test_the_launch_is_the_binary_the_conf_and_a_stop_at_the_debugger(conf: Path) -> None:
    """The three tokens the whole design rests on, asserted by POSITION."""
    argv = dlaunch.build_argv(launch(conf))
    assert argv[0] == "dosbox-x"
    assert argv[argv.index("-conf") + 1] == str(conf)
    assert "-break-start" in argv
    assert "-fastlaunch" in argv
    assert "-nopromptfolder" in argv, "a build prompting for its folder never stops at the debugger"


def test_headless_uses_the_emulators_own_video_property(conf: Path) -> None:
    """Not SDL_VIDEODRIVER, and not -silent."""
    argv = dlaunch.build_argv(launch(conf))
    assert pair_at(argv, "sdl videodriver=dummy")
    assert "-silent" not in argv


@pytest.mark.parametrize(("asked", "tail"), [
    (core_window.WindowRequest(0, False, (0, 0)), ["-set", "sdl display=0",
                                           "-set", "sdl windowposition=40,40"]),
    (core_window.WindowRequest(1, False, (2048, 0)), ["-set", "sdl display=1",
                                                      "-set", "sdl windowposition=2088,40"]),
    (core_window.WindowRequest(0, True, (0, 0)), ["-set", "sdl display=0", "-fullscreen"]),
])
def test_a_watched_session_gets_no_dummy_driver_and_the_window_it_asked_for(
        conf: Path, asked: core_window.WindowRequest, tail: list[str]) -> None:
    """The IDENTITY axis: the window request is the one fact, and argv is computed from it."""
    argv = dlaunch.build_argv(launch(conf, window=asked))
    assert not pair_at(argv, "sdl videodriver=dummy")
    assert argv[-len(tail):] == tail
    assert launch(conf, window=asked).watched is True


def test_a_launch_with_no_window_is_unwatched_and_headless(conf: Path) -> None:
    unwatched = launch(conf)
    assert unwatched.watched is False
    assert pair_at(dlaunch.build_argv(unwatched), "sdl videodriver=dummy")


def test_every_launch_carries_its_bound(conf: Path) -> None:
    """DOSBox-X does not refuse an unknown option, it HANGS."""
    argv = dlaunch.build_argv(launch(conf, seconds=45))
    assert argv[argv.index("-time-limit") + 1] == "45"


def test_the_logfile_and_the_captures_directory_go_to_their_own_settings(conf: Path,
                                                                        tmp_path: Path) -> None:
    """The IDENTITY axis again, and it is not cosmetic"""
    log, cap = tmp_path / "g.log", tmp_path / "caps"
    argv = dlaunch.build_argv(launch(conf, logfile=log, captures_dir=cap))
    assert pair_at(argv, f"log logfile={log}")
    assert pair_at(argv, f"dosbox captures={cap}")


def test_neither_setting_appears_when_it_was_not_asked_for(conf: Path) -> None:
    """The green beside the red above"""
    argv = dlaunch.build_argv(launch(conf))
    assert not any(a.startswith(("log logfile=", "dosbox captures=")) for a in argv)


def test_capture_wraps_the_program_and_plain_does_not(conf: Path) -> None:
    """DX-CAPTURE is the ONLY screen capture with nobody at the keyboard"""
    plain = dlaunch.build_argv(launch(conf, program="GAME.EXE"))
    assert plain[plain.index("-c") + 1] == "GAME.EXE"
    shot = dlaunch.build_argv(launch(conf, program="GAME.EXE", capture_video=True))
    assert shot[shot.index("-c") + 1] == "DX-CAPTURE /V GAME.EXE"


def test_the_serial_route_is_two_set_overrides_and_a_port_in_range(conf: Path) -> None:
    """`input_port` puts the two switches the route needs on the argv as `-set` overrides."""
    argv = dlaunch.build_argv(launch(conf, input_port=5555))
    assert argv[argv.index("cpu integration device=true") - 1] == "-set"
    assert argv[argv.index("serial serial1=nullmodem server:127.0.0.1 port:5555 transparent:1")
                - 1] == "-set"
    plain = dlaunch.build_argv(launch(conf))
    assert not any("integration device" in a or "nullmodem" in a for a in plain)
    dlaunch.validate(launch(conf, input_port=5555))
    for bad in (80, 70000, -1):
        with pytest.raises(ds.Invalid, match="between 1024 and 65535"):
            dlaunch.validate(launch(conf, input_port=bad))


def test_the_serial_socket_is_the_emulators_dial_and_a_dial_that_never_comes_is_refused(
        ) -> None:
    """`accept_input` takes the emulator's dial on the session's listener."""
    listener = dlaunch.listen_input(_free_port())
    port = listener.getsockname()[1]
    emulator = socket.socket()
    emulator.connect(("127.0.0.1", port))       # the listener's backlog holds the dial
    try:
        client = dlaunch.accept_input(listener, 3.0, lambda: None)
        peer = emulator
        with pytest.raises(OSError):
            listener.accept()
        try:
            fake = SimpleNamespace(_link=stub_link.Link(client))
            stub = Stub(peer)
            commands = [b"K\x1e", b"M\x10\x00\x20\x00", b"R"]
            got = ds.Session.send_commands(fake, commands)  # type: ignore[arg-type]
            assert got == [REPORT[:-2].decode()] and stub.carried == commands
            with pytest.raises(ds.Invalid, match="nothing to send"):
                ds.Session.send_commands(fake, [])  # type: ignore[arg-type]
            peer.close()
            client.close()
            with pytest.raises(ds.Invalid, match="socket is gone"):
                ds.Session.send_commands(fake, [b"K\x1e"])  # type: ignore[arg-type]
        finally:
            peer.close()
    finally:
        listener.close()
    silent = dlaunch.listen_input(_free_port())
    quiet = silent.getsockname()[1]
    with pytest.raises(ds.Invalid, match=f"never dialled the serial input port {quiet} within"):
        dlaunch.accept_input(silent, 0.5, lambda: None)
    no_route = SimpleNamespace(_link=None)
    with pytest.raises(ds.Invalid, match="no input route"):
        ds.Session.send_commands(no_route, [b"K\x1e"])  # type: ignore[arg-type]


def test_a_port_something_else_holds_is_refused_before_the_emulator_exists() -> None:
    """A port another process listens on cannot be the session's"""
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        with pytest.raises(ds.Invalid, match=f"input_port {port} is already in use"):
            dlaunch.listen_input(port)
    finally:
        holder.close()
    held = dlaunch.listen_input(port)
    try:
        with pytest.raises(OSError):
            socket.socket().bind(("127.0.0.1", port))
    finally:
        held.close()


def test_a_dial_that_never_comes_kills_the_child_it_spawned(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE ARM THAT MATTERS"""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    child = Child()
    signalled: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: child)
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: signalled.append(sig))
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)
    port = _free_port()
    with pytest.raises(ds.Invalid, match="never dialled"):
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    dlaunch.listen_input(port).close()
    assert signalled == [guardian.KILL] and len(child.waits) == 1, (signalled, child.waits)


def test_the_program_reaches_the_emulator_as_one_argv_element(conf: Path) -> None:
    """The vocabulary is ours; the values are the caller's."""
    nasty = "X.EXE; -loadstate 1"
    argv = dlaunch.build_argv(launch(conf, program=nasty))
    assert argv[argv.index("-c") + 1] == nasty
    assert argv.count("-c") == 1


def test_a_valid_launch_passes_validation_without_starting_anything(conf: Path) -> None:
    """The green beside every red below."""
    dlaunch.validate(launch(conf))
    dlaunch.validate(launch(conf, window=core_window.WindowRequest(0, False, (0, 0))))
    dlaunch.validate(launch(conf, program="G.EXE", capture_video=True))


def test_a_session_that_cannot_be_reproduced_is_refused_before_it_exists(tmp_path: Path) -> None:
    with pytest.raises(ds.Invalid, match="no conf"):
        dlaunch.validate(dlaunch.Launch(conf=tmp_path / "gone.conf", cwd=tmp_path, seconds=30))


def test_a_missing_working_directory_is_refused_too(conf: Path, tmp_path: Path) -> None:
    """It is guarded for the same reason the conf is, and for one more"""
    with pytest.raises(ds.Invalid, match="working directory"):
        dlaunch.validate(launch(conf, cwd=tmp_path / "nowhere"))


def test_an_unbounded_session_is_refused(conf: Path) -> None:
    """Zero is the DANGEROUS value, not merely an invalid one"""
    for bad in (0, -1):
        with pytest.raises(ds.Invalid, match="without a bound"):
            dlaunch.validate(launch(conf, seconds=bad))


def test_a_bound_too_large_to_bound_anything_is_refused(conf: Path) -> None:
    """The ceiling, at its boundary"""
    dlaunch.validate(launch(conf, seconds=dlaunch.MAX_SECONDS))
    with pytest.raises(ds.Invalid, match="not a bound"):
        dlaunch.validate(launch(conf, seconds=dlaunch.MAX_SECONDS + 1))


def test_capture_without_a_program_to_capture_is_refused(conf: Path) -> None:
    """DX-CAPTURE wraps a PROGRAM."""
    with pytest.raises(ds.Invalid, match="needs a program"):
        dlaunch.validate(launch(conf, capture_video=True))


LIVE = "Bochs port E9h: [+   9.122] AUDIO . loudness: A=-19.1 B=-29.6\n"
LIVE2 = "Bochs port E9h: [+  12.000] AUDIO . loudness: A=-18.0 B=-28.0\n"
REPLAY = "dosbox-run: | LOG: Bochs port E9h: [+   9.122] AUDIO . loudness: A=-19.1\n"
NOISE = "gcc -o build/GAME.EXE src/audio.c src/loudness.c\n"


def test_only_an_instrumentation_line_can_match() -> None:
    """The defect this guard exists for, reproduced as a fixture."""
    lines, total = dlogs.filter_e9(NOISE + LIVE + REPLAY, "loudness", 10)
    assert total == 1
    assert lines == [LIVE.rstrip("\n")]


def test_a_pattern_that_matches_nothing_is_an_answer() -> None:
    """Empty is an answer; INVALID is what "there was no channel" gets."""
    assert dlogs.filter_e9(LIVE, "no-such-thing", 10) == ([], 0)


def test_the_total_is_what_matched_and_not_what_came_back() -> None:
    """The COUNT axis."""
    text = "".join(f"Bochs port E9h: [+ {i}.0] TICK n={i}\n" for i in range(10))
    lines, total = dlogs.filter_e9(text, "TICK", 3)
    assert total == 10
    assert len(lines) == 3


def test_the_limit_keeps_the_tail_and_not_the_head() -> None:
    """The ORDER axis, not the presence one."""
    text = "".join(f"Bochs port E9h: [+ {i}.0] TICK n={i}\n" for i in range(10))
    lines, _ = dlogs.filter_e9(text, "TICK", 3)
    assert [ln.split("n=")[1] for ln in lines] == ["7", "8", "9"]


def test_a_limit_of_zero_or_less_is_refused() -> None:
    """`limit=0` reads naturally as "no cap" and `limit=-1` as "all"."""
    for bad in (0, -1):
        with pytest.raises(ds.Invalid, match="haystack"):
            dlogs.filter_e9(LIVE, "loudness", bad)
    dlogs.filter_e9(LIVE, "loudness", dlogs.LOG_LIMIT_MAX)
    with pytest.raises(ds.Invalid, match=f"1..{dlogs.LOG_LIMIT_MAX}"):
        dlogs.filter_e9(LIVE, "loudness", dlogs.LOG_LIMIT_MAX + 1)


def test_an_unusable_pattern_is_invalid_and_does_not_escape() -> None:
    """`pattern` is the caller's regular expression."""
    with pytest.raises(ds.Invalid, match="not a usable pattern"):
        dlogs.filter_e9(LIVE, "[", 10)


def test_the_two_nothings_are_counted_apart() -> None:
    """A log with instrumentation and no match is an answer."""
    assert dlogs.count_e9(NOISE + LIVE + REPLAY + LIVE2) == 2
    assert dlogs.count_e9(NOISE + REPLAY) == 0


def test_a_child_that_could_not_be_reaped_is_recorded_and_not_reported_as_clean(
) -> None:
    """SIGKILL cannot be ignored."""
    class NeverDies:
        returncode: int | None = None

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="dosbox-x", timeout=timeout or 0)

    sent: list[int] = []
    fake = SimpleNamespace(
        proc=NeverDies(), reap_failed="", drain_failure="", _drainer=None,
        _out=None, _signal_group=sent.append)
    fake._ask_to_leave = lambda: ds.Session._ask_to_leave(fake)  # type: ignore[arg-type]
    rc = ds.Session._close(fake, grace=0)  # type: ignore[arg-type]
    assert rc is None, "a child that was never reaped has no exit code"
    assert fake.reap_failed.startswith("SIGKILL was sent"), (
        f"the session reported nothing about a child it could not reap: "
        f"{fake.reap_failed!r}")
    assert sent == [signal.SIGTERM, guardian.KILL], sent

    class IgnoresTermDiesOnKill:
        returncode = -9

        def __init__(self) -> None:
            self.first = 0.0
            self.stretches = 0

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            now = time.monotonic()
            self.first = self.first or now
            if now - self.first < dprocess.TERM_GRACE:
                self.stretches = 1
                time.sleep(timeout or 0)
                raise subprocess.TimeoutExpired(cmd="dosbox-x", timeout=timeout or 0)
            self.stretches = 2
            return -9

    proc = IgnoresTermDiesOnKill()
    ok_sent: list[int] = []
    ok = SimpleNamespace(
        proc=proc, reap_failed="", drain_failure="", _drainer=None,
        _out=None, _signal_group=ok_sent.append)
    ok._ask_to_leave = lambda: ds.Session._ask_to_leave(ok)  # type: ignore[arg-type]
    assert ds.Session._close(ok) == -9  # type: ignore[arg-type]
    assert ok_sent == [signal.SIGTERM, guardian.KILL], ok_sent
    assert proc.stretches == 2, "the control never reached the SIGKILL wait"
    assert ok.reap_failed == "", (
        "a child that WAS reaped after SIGKILL was reported as unreapable, which is "
        "the ordinary close of a running session")


def _src(fake: Any) -> Path:
    return Path(str(fake.captures()[-1]["path"]))


def test_a_still_whose_destination_already_exists_is_refused_before_ffmpeg_runs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The caller's file is NEVER deleted."""
    mine = tmp_path / "README.md"
    mine.write_bytes(b"the caller's own file, nothing to do with a frame")
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    ran: list[list[str]] = []

    def record_run(argv: list[str], **_k: object) -> SimpleNamespace:
        ran.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shutil, "which", lambda name: _abs("usr", "bin", "ffmpeg"))
    monkeypatch.setattr(subprocess, "run", record_run)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.frame(fake, 9999, mine, _src(fake))  # type: ignore[arg-type]
    assert mine.read_bytes() == b"the caller's own file, nothing to do with a frame", (
        "it deleted or overwrote the caller's file")
    assert ran == [], "ffmpeg was asked for a frame before the destination was judged"
    (tmp_path / "elsewhere").mkdir()
    link = tmp_path / "shot.png"
    link.symlink_to(tmp_path / "elsewhere" / "victim.png")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.frame(fake, 7, link, _src(fake))  # type: ignore[arg-type]
    assert ran == [] and not (tmp_path / "elsewhere" / "victim.png").exists()


def test_a_destination_that_is_a_numbering_template_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`-f image2` reads the path as a printf TEMPLATE."""
    monkeypatch.setattr("shutil.which", lambda name: name)   # an ffmpeg, never run
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    with pytest.raises(ds.Invalid, match="containing `%` is refused"):
        ds.Session.frame(fake, 7, tmp_path / "shot%03d.png", _src(fake))  # type: ignore[arg-type]

    with pytest.raises(ds.Invalid, match="containing `%` is refused"):
        ds.Session.frame(fake, 7, tmp_path / "run%d" / "shot.png", _src(fake))  # type: ignore[arg-type]


def test_a_destination_with_no_directory_is_a_refusal_not_a_traceback(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`tool()` translates only `Invalid`."""
    monkeypatch.setattr("shutil.which", lambda name: name)   # an ffmpeg, never run
    missing = tmp_path / "missing"
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    with pytest.raises(ds.Invalid, match="is not a directory"):
        ds.Session.frame(fake, 7, missing / "shot.png", _src(fake))  # type: ignore[arg-type]
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    asked: list[str] = []

    def writes_the_dump(text: str, **_k: object) -> str:
        asked.append(text)
        (tmp_path / ds.MEMDUMP_NAME).write_bytes(b"\xAB" * 16)
        return f"DEBUG: {ds.MEMDUMP_OK}."

    dumper = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=writes_the_dump,
        _memdump_candidates=lambda: [tmp_path / ds.MEMDUMP_NAME])
    with pytest.raises(ds.Invalid, match="is not a directory"):
        ds.Session.memdump(dumper, 0, 0, 16, missing / "d.bin")  # type: ignore[arg-type]
    assert asked == [] and not (tmp_path / ds.MEMDUMP_NAME).exists()
    assert not missing.exists()


@CASED_PATHS
def test_the_dump_is_looked_for_in_the_working_directory_first(tmp_path: Path) -> None:
    """The one property the whole `memdump` defect was about, asserted by name."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    caps = tmp_path / "caps"
    fake = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=work, seconds=60,
                                            captures_dir=caps))
    got = ds.Session._memdump_candidates(fake)  # type: ignore[arg-type]
    assert got[0] == work / ds.MEMDUMP_FILE, (
        f"the name `memdump` passes is not looked for first; the list starts {got[:1]}")
    assert {p.name for p in got if p.parent == work} == {
        ds.MEMDUMP_FILE, ds.MEMDUMP_NAME, ds.MEMDUMP_NAME.upper()}, got
    assert any(p.parent == caps for p in got), got

    bare = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=work, seconds=60))
    assert ds.Session._memdump_candidates(bare)  # type: ignore[arg-type]


def test_read_memory_with_a_cached_mode_does_not_survey_for_it(tmp_path: Path) -> None:
    """A passed `mode` is the offset ceiling's source: no survey goes out for it."""
    machine = protected(Machine(memory={0x16DF20 + i: 0x8D for i in range(4)}))
    s = session_over(machine, tmp_path)
    assert s.read_bytes(0x00A7, 0x16DF20, 4, mode="Pr32") == bytes([0x8D] * 4)
    assert [c for c in machine.sent if c.startswith("EXEC EV")] == [], machine.sent


def test_read_memory_takes_a_32_bit_offset_in_protected_mode(tmp_path: Path) -> None:
    """A flat clamp of the offset to 0xFFFF would refuse every 32-bit DJGPP address."""
    pr32 = session_over(protected(Machine(memory={0x16DF20: 0x8D})), tmp_path)
    assert pr32.read_bytes(0x00A7, 0x16DF20, 1) == b"\x8d"
    real = session_over(Machine(), tmp_path)
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        real.read_bytes(0x00A7, 0x16DF20, 1)


def test_a_dump_destination_inside_the_debuggers_own_place_is_refused(
        tmp_path: Path) -> None:
    """A `dest` naming a CANDIDATE as a directory component would pollute the dump place."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    candidate = cwd / ds.MEMDUMP_NAME

    def writes(_t: str, **_k: object) -> str:
        candidate.write_bytes(b"\xAB" * 16)
        return f"DEBUG: {ds.MEMDUMP_OK}."

    d = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=cwd, seconds=60),
                        command=writes,
                        _memdump_candidates=lambda: [candidate])
    with pytest.raises(ds.Invalid, match="where the debugger writes its own file"):
        ds.Session.memdump(d, 0, 0, 16, candidate / "sub" / "d.bin")  # type: ignore[arg-type]
    assert not candidate.is_dir(), "the candidate path was turned into a directory"

    with pytest.raises(ds.Invalid, match="where the debugger writes"):
        ds.Session.memdump(d, 0, 0, 16,  # type: ignore[arg-type]
                           cwd / ds.MEMDUMP_NAME.upper() / "sub" / "d.bin")
    link = tmp_path / "link"
    link.symlink_to(cwd)
    d2 = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=link, seconds=60),
                         command=writes,
                         _memdump_candidates=lambda: [link / ds.MEMDUMP_NAME])
    with pytest.raises(ds.Invalid, match="where the debugger writes"):
        ds.Session.memdump(d2, 0, 0, 16, candidate / "sub" / "d.bin")  # type: ignore[arg-type]
    old = os.getcwd()
    os.chdir(cwd)
    try:
        with pytest.raises(ds.Invalid, match="where the debugger writes"):
            ds.Session.memdump(d, 0, 0, 16, Path(ds.MEMDUMP_NAME))  # type: ignore[arg-type]
    finally:
        os.chdir(old)

    got = ds.Session.memdump(d, 0, 0, 16, tmp_path / "fine.bin")  # type: ignore[arg-type]
    assert got.read_bytes() == b"\xAB" * 16
    caps = tmp_path / "caps"
    caps.mkdir()
    elsewhere = caps / ds.MEMDUMP_NAME

    def writes_elsewhere(_t: str, **_k: object) -> str:
        elsewhere.write_bytes(b"\xAB" * 16)
        return f"DEBUG: {ds.MEMDUMP_OK}."

    d3 = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=cwd, seconds=60),
                         command=writes_elsewhere,
                         _memdump_candidates=lambda: [elsewhere])
    near = ds.Session.memdump(d3, 0, 0, 16, caps / (ds.MEMDUMP_NAME + "2"))  # type: ignore[arg-type]
    assert near.read_bytes() == b"\xAB" * 16


def test_a_dump_destination_in_the_working_directory_is_refused_and_a_subdirectory_is_not(
        tmp_path: Path) -> None:
    """The debugger writes its own dump file into the emulator's working directory."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    candidate = cwd / ds.MEMDUMP_NAME
    asked: list[str] = []

    def writes(text: str, **_k: object) -> str:
        asked.append(text)
        candidate.write_bytes(b"\xCD" * 16)
        return f"DEBUG: {ds.MEMDUMP_OK}."

    d = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=cwd, seconds=60),
                        command=writes, _memdump_candidates=lambda: [candidate])
    folded = Path(str(cwd).upper()) if (Path(str(cwd).upper())).exists() else cwd
    for dest in (cwd / "x.bin", folded / "y.bin"):
        with pytest.raises(ds.Invalid, match="working directory"):
            ds.Session.memdump(d, 0, 0, 16, dest)  # type: ignore[arg-type]
    old = os.getcwd()
    os.chdir(cwd)
    try:
        with pytest.raises(ds.Invalid, match="working directory"):
            ds.Session.memdump(d, 0, 0, 16, Path("z.bin"))  # type: ignore[arg-type]
    finally:
        os.chdir(old)
    assert asked == [], "the debugger was asked for a dump that was then refused"
    assert not any((cwd / n).exists() for n in ("x.bin", "y.bin", "z.bin"))
    (cwd / "TMP").mkdir()
    got = ds.Session.memdump(d, 0, 0, 16, cwd / "TMP" / "d.bin")  # type: ignore[arg-type]
    assert got.read_bytes() == b"\xCD" * 16


def test_a_dump_destination_that_already_exists_is_refused_before_the_debugger_is_asked(
        tmp_path: Path) -> None:
    """`source.replace(dest)` overwrites in silence"""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    candidate = cwd / ds.MEMDUMP_NAME
    asked: list[str] = []

    def writes(text: str, **_k: object) -> str:
        asked.append(text)
        candidate.write_bytes(b"\xAB" * 16)
        return f"DEBUG: {ds.MEMDUMP_OK}."

    d = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=cwd, seconds=60),
                        command=writes, _memdump_candidates=lambda: [candidate])
    mine = tmp_path / "data.bin"
    mine.write_bytes(b"the caller's data, not guest memory")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.memdump(d, 0, 0, 16, mine)  # type: ignore[arg-type]
    assert mine.read_bytes() == b"the caller's data, not guest memory", "it overwrote it"
    assert asked == [], "the debugger was asked to dump before the destination was judged"
    assert not candidate.exists(), "a dump was written and abandoned where the debugger writes"
    (tmp_path / "elsewhere").mkdir()
    link = tmp_path / "d.bin"
    link.symlink_to(tmp_path / "elsewhere" / "victim.bin")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.memdump(d, 0, 0, 16, link)  # type: ignore[arg-type]
    assert asked == [] and not (tmp_path / "elsewhere" / "victim.bin").exists()
    got = ds.Session.memdump(d, 0, 0, 16, tmp_path / "fresh.bin")  # type: ignore[arg-type]
    assert got.read_bytes() == b"\xAB" * 16


def test_only_the_names_this_debugger_sets_are_accepted() -> None:
    """`SR` takes MULTIPLE pairs and a carriage return is appended."""
    assert "ax" in grammar.SETTABLE and "eax" in grammar.SETTABLE
    assert "ax 1\rBPINT 21" not in grammar.SETTABLE
    assert "eex" not in grammar.SETTABLE


AVI = Path(__file__).parent / "fixtures" / "avi"


def fake_avi(frames: int, complete: bool = True) -> bytes:
    """The SHAPE of a capture, as the two real ones under `fixtures/avi` hold it."""
    avih = b"avih" + struct.pack("<I", 56) + struct.pack(
        "<14I", 0, 0, 0, 0, frames if complete else 0, 0, 1, 0, 720, 400, 0, 0, 0, 0)
    body = b"RIFF" + b"\x00" * 4 + b"AVI " + b"LIST" + b"\x00" * 8 + avih + b"00dc" * frames
    return body + (b"idx1" + b"00dc" * frames if complete else b"")


def test_a_finished_capture_counts_its_frames_from_its_header() -> None:
    """The real 12-frame capture"""
    data = (AVI / "dosbox-x-zmbv-12.avi").read_bytes()
    assert data.count(b"00dc") == 26
    assert ds.avi_facts(data) == {"bytes": len(data), "riff_avi": True, "avi_frames": 12,
                                  "complete": True}


def test_a_capture_still_recording_counts_its_frame_chunks() -> None:
    data = (AVI / "dosbox-x-zmbv-running.avi").read_bytes()
    assert ds.avi_facts(data) == {"bytes": len(data), "riff_avi": True, "avi_frames": 9,
                                  "complete": False}


def test_a_capture_is_judged_by_what_is_in_it_and_not_by_its_size() -> None:
    """A recording that captured nothing and one that captured everything are both plausible."""
    facts = ds.avi_facts(fake_avi(frames=5428))
    assert facts["riff_avi"] is True
    assert facts["avi_frames"] == 5428
    assert facts["complete"] is True


def test_a_capture_still_in_progress_is_marked_incomplete_and_not_corrupt() -> None:
    """The index is written when the recording STOPS, so its absence is a state and not damage."""
    facts = ds.avi_facts(fake_avi(frames=40, complete=False))
    assert facts["complete"] is False and facts["avi_frames"] == 40


def test_something_that_is_not_a_capture_is_not_called_one() -> None:
    """The green's red"""
    facts = ds.avi_facts(b"this is not a video at all")
    assert facts["riff_avi"] is False
    assert facts["avi_frames"] == 0


def stopped(**over: object) -> Any:
    """A stand-in carrying only what `captures`/`frame` READ."""
    base: dict[str, object] = {"captures_dir": None, "capture_video": False}
    base.update(over)
    return SimpleNamespace(launch=SimpleNamespace(**base), _avi_facts={})


def test_a_session_that_was_not_recording_is_not_an_empty_capture(tmp_path: Path) -> None:
    """"Nothing was recording" and "the recording is empty" are different answers."""
    with pytest.raises(ds.Invalid, match="nothing was recording"):
        ds.Session.captures(
            stopped(captures_dir=tmp_path, capture_video=False))


def test_a_recording_session_with_no_file_yet_says_why(tmp_path: Path) -> None:
    """The green's other half"""
    with pytest.raises(ds.Invalid, match="no .avi file in"):
        ds.Session.captures(
            stopped(captures_dir=tmp_path, capture_video=True))


def test_the_captures_come_back_largest_last(tmp_path: Path) -> None:
    """The ORDER axis, and it is load-bearing"""
    (tmp_path / "a_000.avi").write_bytes(fake_avi(frames=40))
    (tmp_path / "a_001.avi").write_bytes(fake_avi(frames=5428))
    got = ds.Session.captures(
        stopped(captures_dir=tmp_path, capture_video=True))
    assert [c["avi_frames"] for c in got] == [40, 5428]


def test_a_capture_that_has_not_grown_is_not_read_again(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """`captures` is polled."""
    reads: list[str] = []
    real = ds.avi_facts

    def counting(data: bytes) -> dict[str, object]:
        reads.append("read")
        return real(data)

    monkeypatch.setattr(ds, "avi_facts", counting)
    f = tmp_path / "a_000.avi"
    f.write_bytes(fake_avi(frames=40))
    fake = stopped(captures_dir=tmp_path, capture_video=True)
    assert ds.Session.captures(fake)[0]["avi_frames"] == 40 and len(reads) == 1
    assert ds.Session.captures(fake)[0]["avi_frames"] == 40 and len(reads) == 1
    f.write_bytes(fake_avi(frames=41))
    assert ds.Session.captures(fake)[0]["avi_frames"] == 41 and len(reads) == 2


def test_the_capture_cache_keeps_one_entry_per_file(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Two captures is the normal case, and the cache is per FILE"""
    reads: list[str] = []
    real = ds.avi_facts

    def counting(data: bytes) -> dict[str, object]:
        reads.append("read")
        return real(data)

    monkeypatch.setattr(ds, "avi_facts", counting)
    small, big = tmp_path / "a_000.avi", tmp_path / "a_001.avi"
    small.write_bytes(fake_avi(frames=40))
    big.write_bytes(fake_avi(frames=99))
    fake = stopped(captures_dir=tmp_path, capture_video=True)
    assert [c["avi_frames"] for c in ds.Session.captures(fake)] == [40, 99] and len(reads) == 2
    assert [c["avi_frames"] for c in ds.Session.captures(fake)] == [40, 99] and len(reads) == 2
    same_size = fake_avi(frames=40)
    assert len(same_size) == small.stat().st_size
    small.write_bytes(same_size)
    os.utime(small, ns=(small.stat().st_atime_ns, small.stat().st_mtime_ns + 1_000_000))
    ds.Session.captures(fake)
    assert len(reads) == 3, "a file replaced at the same size was served from the cache"


def test_a_negative_frame_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: name)   # an ffmpeg, never run
    with pytest.raises(ds.Invalid, match="not a frame"):
        ds.Session.frame(
            stopped(captures_dir=tmp_path, capture_video=True), -1, tmp_path / "x.png",
            tmp_path / "cap.avi")


MID_ROW = (
    "F000:0000E000 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49 42  ..............IB")
SPLIT_AT = 20


def test_a_name_that_is_not_a_register_never_reaches_the_debugger() -> None:
    """THE GUARD IS EXERCISED, not just its frozenset read back."""
    sent: list[str] = []
    fake = SimpleNamespace(altered=False, command=sent.append)
    for bad in ("eax 0 ; RUN", "cr3", "", "e a x"):
        with pytest.raises(ds.Invalid, match="not a register this debugger sets"):
            ds.Session.set_register(fake, bad, 1)   # type: ignore[arg-type]
    assert sent == [], f"a rejected name still reached the debugger: {sent}"
    assert fake.altered is False, (
        "a name that never reached the machine marked the session altered")


def test_set_register_refuses_a_value_its_register_cannot_hold_before_sending() -> None:
    """`SR` takes a hex word and the debugger keeps what fits."""
    sent: list[str] = []
    fake = SimpleNamespace(altered=False, command=sent.append)
    for name, value in (("ax", 0x10000), ("eax", 1 << 32), ("cs", -1)):
        with pytest.raises(ds.Invalid, match="nothing was sent"):
            ds.Session.set_register(fake, name, value)   # type: ignore[arg-type]
    assert sent == [] and fake.altered is False, sent


def test_set_register_whose_pane_lacks_the_register_is_refused_and_still_altered(
        tmp_path: Path) -> None:
    """The readback is a reading of the register, after the `SR`."""
    machine = Machine()
    s = session_over(machine, tmp_path)
    s.registers = lambda: {"EBX": "0"}  # type: ignore[method-assign]
    with pytest.raises(ds.Invalid, match="without EAX after `SR`"):
        s.set_register("eax", 1)
    assert machine.sent == ["EXEC SR eax 1"], machine.sent
    assert s.altered is True
    del s.registers
    ok = s.set_register("eax", 1)
    assert ok["readback"] == "0x00000001" and ok["verified"] is True
    machine.hooks["SR"] = lambda _c: (True, ["DEBUG: Set Register success."])
    assert s.set_register("eax", 2)["verified"] is False


def _pane_after_sr(pane: dict[str, str]) -> SimpleNamespace:
    """A session double whose pane, after the `SR`, is `pane`"""
    return SimpleNamespace(altered=False, command=lambda _text: "", registers=lambda: pane)


def test_a_segment_register_reads_back_under_its_own_name(tmp_path: Path) -> None:
    """A segment register has no 32-bit form."""
    s = session_over(Machine(), tmp_path)
    got = s.set_register("cs", 0x50)
    assert got["readback"] == "0x0050" and got["verified"] is True, got
    assert s.altered is True


def test_a_16_bit_name_is_read_back_as_the_low_half_of_its_register(tmp_path: Path) -> None:
    """`ax` is the low half of `EAX`, which is what the reading carries."""
    machine = Machine()
    machine.regs["EAX"] = 0xABCD0000
    s = session_over(machine, tmp_path)
    def low_half(command: str) -> tuple[bool, list[str]] | None:
        _, name, value = command.split()
        if name != "ax":
            return None
        machine.regs["EAX"] = (machine.regs["EAX"] & 0xFFFF0000) | int(value, 16)
        return True, ["DEBUG: Set Register success."]
    machine.hooks["SR"] = low_half
    got = s.set_register(" AX", 0x1234)
    assert got["readback"] == "0x1234" and got["verified"] is True, got
    assert got["register"] == "ax", got
    assert machine.regs["EAX"] == 0xABCD1234
    ip = s.set_register("ip", 0x0100)
    assert ip["readback"] == "0x0100" and ip["verified"] is True, ip


def test_every_settable_name_has_the_pane_register_and_width_it_is_read_back_at() -> None:
    """ONE TABLE says where each name `SR` takes is read back, and it covers `SETTABLE` exactly"""
    assert set(ds.READBACK) == set(grammar.SETTABLE)
    for name, (pane, bits) in ds.READBACK.items():
        assert pane in grammar.REGISTER_NAMES, (name, pane)
        assert bits in (16, 32), (name, bits)
    assert ds.READBACK["cs"] == ("CS", 16) and ds.READBACK["es"] == ("ES", 16)
    assert ds.READBACK["ax"] == ("EAX", 16) and ds.READBACK["ip"] == ("EIP", 16)
    assert ds.READBACK["esp"] == ("ESP", 32)


def test_an_ack_naming_a_truncated_filename_is_not_an_ack() -> None:
    """THE SILENT HAZARD IN THIS COMMAND."""
    ok = f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"
    ds.Session.acked(ok, ds.SYM_SAVE_ECHO, ds.SYM_SAVE_NAME)

    ok_load = f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
    ds.Session.acked(ok_load, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    with pytest.raises(ds.Invalid, match="did not acknowledge"):
        ds.Session.acked(ok_load, ds.SYM_SAVE_ECHO, ds.SYM_SAVE_NAME)

    truncated = "DEBUG: Variable list save (ABCDEFGHIJKL) : ok.\n"
    with pytest.raises(ds.Invalid, match="truncates a filename"):
        ds.Session.acked(truncated, ds.SYM_SAVE_ECHO, "ABCDEFGHIJKLMNOPQRST.BIN")

    failed = "DEBUG: Variable list save (/PRIVATE/TMP) : failure.\n"
    with pytest.raises(ds.Invalid, match="did not acknowledge"):
        ds.Session.acked(failed, ds.SYM_SAVE_ECHO, _abs("private", "tmp", "x.bin"))


def test_an_ok_from_an_earlier_call_does_not_acknowledge_this_one() -> None:
    """THE SECOND AXIS"""
    delta = (f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
             f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"
             f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}) : failure.\n")
    with pytest.raises(ds.Invalid, match="OLDER ok"):
        ds.Session.acked(delta, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)


def test_both_filenames_this_module_uses_fit_inside_what_the_debugger_keeps() -> None:
    """A constant checked against the debugger's limit."""
    assert ds.SYM_ARG_MAX == 12
    for name in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME):
        assert len(name) <= ds.SYM_ARG_MAX, name
        assert name == name.upper(), (
            f"{name!r} is not upper case, and the debugger uppercases the filename it "
            f"echoes back, so `acked` would never match its own request")


def _loader(tmp_path: Path, reply: Callable[[str], str] | None = None) -> Any:
    """A stand-in with exactly what `load_symbols` reaches for."""
    def default(text: str) -> str:
        if text.startswith("LV"):
            return f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
        (tmp_path / ds.SYM_SAVE_NAME).write_bytes(GOOD_LIST)
        return f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"

    return SimpleNamespace(launch=SimpleNamespace(cwd=tmp_path),
                           command=reply or default,
                           alive=lambda: True, vars_held=0,
                           acked=ds.Session.acked)


GOOD_LIST = (b"\x01\x00" + b"_x" + b"\0" * 14 + b"\x10\x00\x00\x00")

GUARD_MARK = "No file was written"


def _running() -> tuple[str, dict[str, str]]:
    """What `_survey` does when the console is not listening"""
    raise ds.NotStopped("no register pane came back from `BPLIST` (emulator running). "
                        "A register read is only a reading when the machine is "
                        "stopped at the debugger")


def test_a_symbol_file_round_trips_and_leaves_nothing_behind(tmp_path: Path) -> None:
    """The control for every refusal below"""
    got = ds.Session.load_symbols(_loader(tmp_path), GOOD_LIST)
    assert got == [("_x", 0x10)]
    for name in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME):
        assert not (tmp_path / name).exists(), f"{name} was left behind"


def test_a_load_past_what_the_debuggers_save_can_hold_is_refused_before_lv(
        tmp_path: Path) -> None:
    """`LV` appends and nothing clears the debugger's list."""
    sent: list[str] = []
    fake = _loader(tmp_path)
    plain = fake.command

    def recorded(text: str) -> str:
        sent.append(text)
        return str(plain(text))
    fake.command = recorded
    fake.vars_held = dsym.COUNT_MAX
    with pytest.raises(ds.Invalid, match="65535") as refused:
        ds.Session.load_symbols(fake, GOOD_LIST)
    assert sent == [] and "nothing clears" in str(refused.value), sent
    fake.vars_held = dsym.COUNT_MAX - 1
    assert ds.Session.load_symbols(fake, GOOD_LIST) == [("_x", 0x10)]
    assert fake.vars_held == 1, "the holding is what the read-back says"


def test_a_load_whose_save_fails_after_lv_counts_what_lv_took(tmp_path: Path) -> None:
    """`LV` acknowledged has appended its names whatever the read-back does next."""
    def reply(text: str) -> str:
        if text.startswith("LV"):
            return f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
        return f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}) : failure.\n"
    fake = _loader(tmp_path, reply)
    with pytest.raises(ds.Invalid):
        ds.Session.load_symbols(fake, GOOD_LIST)
    assert fake.vars_held == 1


def test_the_ceiling_is_judged_before_the_file_is_written(tmp_path: Path) -> None:
    fake = _loader(tmp_path)
    fake.vars_held = dsym.COUNT_MAX
    tmp_path.chmod(0o555)
    try:
        with pytest.raises(ds.Invalid, match="past 65535"):
            ds.Session.load_symbols(fake, GOOD_LIST)
    finally:
        tmp_path.chmod(0o755)


def test_a_file_already_there_is_named_before_the_machine_is_read(
        tmp_path: Path) -> None:
    """THE OTHER DIRECTION OF THE SAME ORDER, and it was not gated at all."""
    (tmp_path / ds.SYM_LOAD_NAME).write_bytes(b"somebody else's file")
    fake = _loader(tmp_path)
    fake._survey = _running
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.load_symbols(fake, GOOD_LIST)


def test_the_acknowledgement_refusal_keeps_the_tail_and_not_the_head() -> None:
    """WHAT SURVIVES THE 300-CHARACTER BOUND IS THE NEWEST EVIDENCE, not the oldest."""
    out = "HEADMARK " + "x" * 400 + " TAILMARK"
    with pytest.raises(ds.Invalid) as caught:
        ds.Session.acked(out, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    said = str(caught.value)
    assert "TAILMARK" in said, said
    assert "HEADMARK" not in said, "it quoted the head, so the newest evidence is gone"


def test_a_missing_acknowledgement_names_every_cause_that_has_been_seen() -> None:
    """The refusal enumerates, so what it LEAVES OUT reads as excluded."""
    running = ("\x1b7\x1b8\r\nBochs port E9h: [+ 00000.000] PROBE . tick"
               "\x1b7\x1b8\r\nBochs port E9h: [+ 00001.000] PROBE . tick")
    with pytest.raises(ds.Invalid) as caught:
        ds.Session.acked(running, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    said = str(caught.value)
    for clause in ("truncates a filename", "OLDER ok", "EMPTY", "RUNNING",
                   "not a closed list"):
        assert clause in said, f"the refusal no longer says {clause!r}: {said}"
    assert "PROBE . tick" in said


def test_a_dangling_symlink_at_either_name_is_refused(tmp_path: Path) -> None:
    """`exists()` FOLLOWS symlinks."""
    victim = tmp_path / "elsewhere" / "victim.bin"
    victim.parent.mkdir()
    (tmp_path / ds.SYM_LOAD_NAME).symlink_to(victim)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.load_symbols(_loader(tmp_path), GOOD_LIST)
    assert not victim.exists(), "it wrote through the link, outside the directory"


@MODE_BITS
def test_an_unwritable_working_directory_is_a_refusal_and_not_a_traceback(
        tmp_path: Path) -> None:
    """`tool()` translates only `Invalid`."""
    cwd = tmp_path / "ro"
    cwd.mkdir()
    cwd.chmod(0o555)
    try:
        with pytest.raises(ds.Invalid, match="could not write"):
            ds.Session.load_symbols(_loader(cwd), GOOD_LIST)
    finally:
        cwd.chmod(0o755)


def test_a_file_the_debugger_saved_that_cannot_be_read_back_is_a_refusal(
        tmp_path: Path) -> None:
    """`BadSymbolText` is NOT an `Invalid`."""
    def bad(text: str) -> str:
        if text.startswith("LV"):
            return f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
        (tmp_path / ds.SYM_SAVE_NAME).write_bytes(b"\x02\x00" + b"\0" * 10)
        return f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"

    with pytest.raises(ds.Invalid, match="cannot be read back"):
        ds.Session.load_symbols(_loader(tmp_path, bad), GOOD_LIST)


def test_the_descriptor_read_does_not_stitch_two_descriptors_together(
        tmp_path: Path) -> None:
    """The base from one descriptor and the limit from ANOTHER is a wrong answer."""
    screen = ("SelectorInfo CS:\r\n"
              "CS: b:00400000 type:1B parbg\r\n"
              + "x" * 400 + "\r\n"
              "DS: b:00008240 type:12 parbg\nl:0000FFFF dpl : 3 10010\r\n")
    fake = SimpleNamespace(command=lambda text: screen, alive=lambda: True)
    with pytest.raises(ds.Invalid, match="line of its own"):
        ds.Session.selector(fake, "CS")   # type: ignore[arg-type]

    whole = ("SelectorInfo CS:\r\n"
             "CS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 10011\r\n"
             "DS: b:00008240 type:12 parbg\nl:0000FFFF dpl : 3 10010\r\n")
    ok = SimpleNamespace(command=lambda text: whole, alive=lambda: True)
    got = ds.Session.selector(ok, "CS")    # type: ignore[arg-type]
    assert got == {"base": 0x00400000, "limit": 0x0023FFFF, "type": 0x1B, "big": 1}


def test_the_descriptor_read_takes_the_big_bit_from_the_fourth_digit() -> None:
    """`SELINFO`'s five digits under `parbg` are present, available, reserved, big, granularity."""
    line = "SelectorInfo CS:\r\nCS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 {}\r\n"
    narrow = SimpleNamespace(command=lambda text: line.format("10001"), alive=lambda: True)
    assert ds.Session.selector(narrow, "CS")["big"] == 0    # type: ignore[arg-type]
    wide = SimpleNamespace(command=lambda text: line.format("10011"), alive=lambda: True)
    assert ds.Session.selector(wide, "CS")["big"] == 1    # type: ignore[arg-type]
    bare = SimpleNamespace(command=lambda text: line.format(""), alive=lambda: True)
    with pytest.raises(ds.Invalid, match="line of its own"):
        ds.Session.selector(bare, "CS")   # type: ignore[arg-type]


def test_the_descriptor_read_takes_the_answer_to_this_question(tmp_path: Path) -> None:
    """The OCCURRENCE axis, the sibling of `acked`'s."""
    screen = ("SelectorInfo CS:\r\n"
              "CS: b:00010000 type:1B parbg\nl:0000FFFF dpl : 3 10011\r\n"
              "SelectorInfo CS:\r\n"
              "CS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 10011\r\n")
    fake = SimpleNamespace(command=lambda text: screen, alive=lambda: True)
    got = ds.Session.selector(fake, "CS")   # type: ignore[arg-type]
    assert got["base"] == 0x00400000, (
        f"it answered 0x{got['base']:08X}, which is the base the machine had when the "
        f"question was asked the FIRST time")


def _bp_fake(tmp_path: Path, *, mode: str = "Pr32",
             held: list[dict[str, str]] | None = None) -> SimpleNamespace:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    fake = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        where=lambda: {"cs": "00A7", "eip": "0", "mode": mode},
        command=lambda _t, **_k: "",
        breakpoints=lambda: list(held or []),
        alive=lambda: True, altered=False, arming_writes=lambda: False)
    fake.delete_rows = lambda picks: ds.Session.delete_rows(fake, picks)  # type: ignore[arg-type]
    return fake


def test_arm_code_breakpoint_reads_the_list_back_and_refuses_a_wrong_mode(
        tmp_path: Path) -> None:
    """It stages a breakpoint WITHOUT releasing the machine."""
    ok = _bp_fake(tmp_path, held=[{"index": "00", "entry": "BP 00A7:16DD80"}])
    got = ds.Session.arm_code_breakpoint(ok, 0x00A7, 0x16DD80)  # type: ignore[arg-type]
    assert got["entry"] == "BP 00A7:16DD80" and ok.altered is False

    real = _bp_fake(tmp_path, mode="Real")
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        ds.Session.arm_code_breakpoint(real, 0x00A7, 0x16DD80)  # type: ignore[arg-type]

    unlisted = _bp_fake(tmp_path, held=[])
    with pytest.raises(ds.Invalid, match="does not list a breakpoint"):
        ds.Session.arm_code_breakpoint(unlisted, 0x00A7, 0x100)  # type: ignore[arg-type]

    with pytest.raises(ds.Invalid, match="segment is 0x0000"):
        ds.Session.arm_code_breakpoint(ok, 0x1_0000, 0)  # type: ignore[arg-type]


def test_clear_code_breakpoint_reads_removal_back_and_is_honest_when_absent(
        tmp_path: Path) -> None:
    """`removed` is the machine's answer read AFTER the delete."""
    present = _bp_fake(tmp_path, held=[{"index": "03", "entry": "BP 00A7:16DD80"}])
    calls = {"n": 0}

    def bps() -> list[dict[str, str]]:
        calls["n"] += 1
        return [{"index": "03", "entry": "BP 00A7:16DD80"}] if calls["n"] == 1 else []
    present.breakpoints = bps
    got = ds.Session.clear_code_breakpoint(present, 0x00A7, 0x16DD80)  # type: ignore[arg-type]
    assert got["removed"] is True

    absent = _bp_fake(tmp_path, held=[])
    gone = ds.Session.clear_code_breakpoint(absent, 0x00A7, 0x16DD80)  # type: ignore[arg-type]
    assert gone["removed"] is False and "no such breakpoint" in str(gone["note"])


def test_clear_interrupt_breakpoint_finds_the_row_by_text_and_reads_removal_back(
        tmp_path: Path) -> None:
    """BPLIST numbers code breakpoints before interrupts whatever the arming order."""
    held = [{"index": "00", "entry": "BP 00A7:16DD80"},
            {"index": "01", "entry": "BP 00A7:3D5E0"},
            {"index": "02", "entry": "BPINT 31 AH=00"}]
    fake = _bp_fake(tmp_path, held=held)
    sent: list[str] = []
    fake.command = lambda text, **_k: sent.append(text)
    calls = {"n": 0}

    def bps() -> list[dict[str, str]]:
        calls["n"] += 1
        return held if calls["n"] == 1 else held[:2]
    fake.breakpoints = bps
    got = ds.Session.clear_interrupt_breakpoint(fake, 0x31, 0x00)  # type: ignore[arg-type]
    assert got["removed"] is True and got["entry"] == "BPINT 31 AH=00"
    assert sent == ["BPDEL 02"], sent

    other_ah = _bp_fake(tmp_path, held=held)
    other_sent: list[str] = []
    other_ah.command = lambda text, **_k: other_sent.append(text)
    gone = ds.Session.clear_interrupt_breakpoint(other_ah, 0x31, 0x05)  # type: ignore[arg-type]
    assert gone["removed"] is False and "no such breakpoint" in str(gone["note"])
    assert other_sent == [], other_sent
    assert grammar.interrupt_row(0x21, None) == "BPINT 21"
    assert grammar.interrupt_row(0x31, 0) == "BPINT 31 AH=00"


def test_clear_interrupt_breakpoint_removed_is_read_back_not_assumed(
        tmp_path: Path) -> None:
    """`removed` is what the list says AFTER the BPDEL, never that the delete was sent."""
    held = [{"index": "00", "entry": "BPINT 21"}]
    fake = _bp_fake(tmp_path, held=held)
    sent: list[str] = []
    fake.command = lambda text, **_k: sent.append(text)
    fake.breakpoints = lambda: [dict(r) for r in held]
    got = ds.Session.clear_interrupt_breakpoint(fake, 0x21)  # type: ignore[arg-type]
    assert sent == ["BPDEL 00"], sent
    assert got["removed"] is False, got
    for bad in (0x100, -1):
        with pytest.raises(ds.Invalid, match="interrupt number"):
            ds.Session.clear_interrupt_breakpoint(fake, bad)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="AH"):
        ds.Session.clear_interrupt_breakpoint(fake, 0x21, 0x100)  # type: ignore[arg-type]


def test_interrupt_row_round_trips_through_parse_and_parse_refuses_junk() -> None:
    """`interrupt_row` and `parse_interrupt_row` are exact inverses over every printed value."""
    for n in (0, 0x21, 0xFF):
        for ah in (None, 0, 0x4C, 0xFF):
            assert grammar.parse_interrupt_row(grammar.interrupt_row(n, ah)) == (n, ah)
    for junk in ("INT 21", "BPINT 211", "BPINT 21 AH=", "BP 00A7:0100", "BPINT ZZ", ""):
        with pytest.raises(ds.Invalid, match="interrupt breakpoint row"):
            grammar.parse_interrupt_row(junk)


def test_bp_row_target_reads_seg_off_by_value_across_widths_and_kinds() -> None:
    """A row is recognised by the NUMBERS it carries, whatever width the debugger printed."""
    assert grammar.bp_row_target("BP 0087:12345") == ("BP", 0x87, 0x12345)
    assert grammar.bp_row_target("BP 00A7:0100") == ("BP", 0xA7, 0x100)
    assert grammar.bp_row_target("BP 00A7:100") == ("BP", 0xA7, 0x100)
    assert grammar.bp_row_target("BPMEM 0040:006C (00)") == ("BPMEM", 0x40, 0x6C)
    assert grammar.bp_row_target("BPPM 00AF:00006024 (00)") == ("BPPM", 0xAF, 0x6024)
    assert grammar.bp_row_target("BPPM 00AF:6024") == ("BPPM", 0xAF, 0x6024)
    assert grammar.bp_row_target("BPINT 21") is None
    assert grammar.bp_row_target("BPINT 31 AH=00") is None


def test_arm_and_clear_recognise_a_breakpoint_by_value_not_by_printed_width(
        tmp_path: Path) -> None:
    """THE SHIPPED-BUG CLASS"""
    listed = [{"index": "00", "entry": "BP 00A7:100"}]
    ok = _bp_fake(tmp_path, held=listed)
    got = ds.Session.arm_code_breakpoint(ok, 0x00A7, 0x100)  # type: ignore[arg-type]
    assert got["entry"] == "BP 00A7:100"

    calls = {"n": 0}

    def bps() -> list[dict[str, str]]:
        calls["n"] += 1
        return listed if calls["n"] == 1 else []
    ok.breakpoints = bps
    gone = ds.Session.clear_code_breakpoint(ok, 0x00A7, 0x100)  # type: ignore[arg-type]
    assert gone["removed"] is True and gone["entry"] == "BP 00A7:100"


def test_read_bytes_returns_the_exact_n_bytes_at_the_address(tmp_path: Path) -> None:
    """A watch needs the bytes themselves, from the dump of exactly that span."""
    machine = Machine(memory={0x7490 + i: i for i in range(32)})
    s = session_over(machine, tmp_path)
    assert s.read_bytes(0x749, 0, 4) == bytes([0, 1, 2, 3])
    assert s.read_bytes(0x749, 0x0E, 4) == bytes([0x0E, 0x0F, 0x10, 0x11])
    assert machine.sent[-1] == "EXEC MEMDUMPBIN 0749:000E 4 MCPDUMP.BIN", machine.sent
    with pytest.raises(ds.Invalid, match="region"):
        s.read_bytes(0x749, 0, 200)
    with pytest.raises(ds.Invalid, match="positive length"):
        s.read_bytes(0x749, 0, 0)
    assert not list(tmp_path.glob("*.BIN")), "a read left its dump in the working directory"


def test_close_records_which_ending_it_got() -> None:
    """Three endings, told apart on the object the server reads after the close"""
    import subprocess
    from types import SimpleNamespace

    def bare(poll_answers: list[int | None], wait_raises: int) -> ds.Session:
        s = ds.Session.__new__(ds.Session)
        s._closing, s._closed = threading.Lock(), False
        polls: list[int | None] = list(poll_answers)
        first = [0.0]

        def poll() -> int | None:
            return polls.pop(0) if len(polls) > 1 else polls[0]

        def wait(timeout: float | None = None) -> int:
            now = time.monotonic()
            first[0] = first[0] or now
            if now - first[0] < wait_raises * dprocess.TERM_GRACE:
                time.sleep(timeout or 0)
                raise subprocess.TimeoutExpired("dosbox-x", timeout or 0)
            polls[:] = [0]
            return 0

        s.proc = SimpleNamespace(poll=poll, wait=wait, pid=1, returncode=0)  # type: ignore[assignment]
        s._signal_group = lambda sig: None  # type: ignore[method-assign]
        s._drainer = None
        s._out = None
        s.drain_failure = ""
        s.reap_failed = ""
        s.ended_how = "none"
        return s

    s = bare([0], 0)
    s.close()
    assert s.ended_how == "died"
    s = bare([None, 0], 0)
    s.close()
    assert s.ended_how == ("killed" if dprocess.TERMINATES else "quit")
    s = bare([None, 0], 1)
    s.close()
    assert s.ended_how == "killed" and s.reap_failed == ""

    import asyncio

    from scry_core import cancel
    closed: list[int] = []
    raised = [False]

    def check() -> None:
        if not cancel.shielding() and not raised[0]:
            raised[0] = True
            raise asyncio.CancelledError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cancel, "check", check)
        mp.setattr(os, "close", closed.append)
        s = bare([None, 0], 0)
        s._out = 99
        with pytest.raises(asyncio.CancelledError):
            s.close()
    assert raised == [True] and closed == [99], closed
    assert s.ended_how == ("killed" if dprocess.TERMINATES else "quit"), s.ended_how


def _writer(memory: dict[str, bytes], mode: str = "Real",
            asked: list[tuple[Any, ...]] | None = None) -> tuple[ds.Session, list[str]]:
    """A session stopped in `mode` that records what `write_memory` sends."""
    sent: list[str] = []
    s = ds.Session.__new__(ds.Session)
    s.altered = False

    def command(text: str, seconds: float | None = None) -> str:
        sent.append(text)
        return ""

    def read_bytes(seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        if asked is not None:
            asked.append((seg, off, n, mode))
        return memory["held"][:n]
    s.command = command  # type: ignore[method-assign]
    s.where = lambda: {"cs": "F000", "eip": "0", "mode": mode}  # type: ignore[method-assign]
    s.read_bytes = read_bytes  # type: ignore[method-assign]
    return s, sent


def test_write_memory_sends_short_sm_lines_and_reads_the_range_back() -> None:
    """`SM seg:off v1 v2 ...` takes a list of values on one input line."""
    memory = {"held": bytes(range(20))}
    s, sent = _writer(memory)
    out = ds.Session.write_memory(s, 0x40, 0x100, bytes(range(20)))
    assert sent == ["SM 0040:0100 000 001 002 003 004 005 006 007",
                    "SM 0040:0108 008 009 00A 00B 00C 00D 00E 00F",
                    "SM 0040:0110 010 011 012 013"], sent
    assert out == {"bytes_written": 20, "readback": bytes(range(20)).hex(), "verified": True}
    assert s.altered is True
    memory["held"] = bytes(20)
    out = ds.Session.write_memory(s, 0x40, 0x100, bytes(range(20)))
    assert out["verified"] is False and out["readback"] == bytes(20).hex()
    with pytest.raises(ds.Invalid, match="at least one byte"):
        ds.Session.write_memory(s, 0x40, 0x100, b"")
    with pytest.raises(ds.Invalid, match="offset"):
        ds.Session.write_memory(s, 0x40, 0x10000, b"\x00")


def test_write_memory_refuses_the_rom_range_and_a_dead_pty_is_named() -> None:
    """On this build `SM` into the BIOS ROM ends the emulator."""
    s, sent = _writer({"held": b""})
    for seg, off in ((0xF000, 0xE05B), (0xC000, 0x0000), (0xBFFF, 0x0010)):
        with pytest.raises(ds.Invalid, match="ENDS the emulator"):
            ds.Session.write_memory(s, seg, off, b"\x99")
    assert sent == [] and s.altered is False
    s.read_bytes = lambda seg, off, n, mode=None: b"\x99"  # type: ignore[method-assign]
    assert ds.Session.write_memory(s, 0xBFFF, 0x000F, b"\x99")["verified"] is True
    sent.clear()
    with pytest.raises(ds.Invalid, match="last byte"):
        ds.Session.write_memory(s, 0x0040, 0xFFF8, bytes(20))
    assert sent == []
    s.read_bytes = lambda seg, off, n, mode=None: bytes(n)  # type: ignore[method-assign]
    assert ds.Session.write_memory(s, 0x0040, 0xFF80, bytes(128))["verified"] is True
    with pytest.raises(ds.Invalid, match="a segment is 0x0000 to 0xFFFF"):
        ds.Session.write_memory(s, 0x10000, 0x0000, b"\x99")


def test_the_stop_surveys_e9_reader_refuses_a_log_that_is_not_there_yet(tmp_path: Path) -> None:
    """`e9_new_since` is the stop survey's reader and answers as `e9` does"""
    s = ds.Session.__new__(ds.Session)
    s.launch = SimpleNamespace(logfile=tmp_path / "not-yet.log")  # type: ignore[assignment]
    with pytest.raises(ds.Invalid, match="has not written anything yet"):
        ds.Session.e9_new_since(s, 0)
    assert ds.Session.e9_since(s, 0) == ([], 0)
    (tmp_path / "not-yet.log").write_text("Bochs port E9h: [+ 0.000] BOOT  . start\n")
    lines, offset = ds.Session.e9_new_since(s, 0)
    assert len(lines) == 1 and offset > 0


def test_the_launch_turns_the_quit_warning_off_so_close_is_a_quit(conf: Path) -> None:
    """With a program loaded, the emulator answers a SIGTERM by asking whether to quit anyway."""
    argv = dlaunch.build_argv(launch(conf))
    assert argv[argv.index("dosbox quit warning=false") - 1] == "-set"
    asked = core_window.WindowRequest(1, False, (2048, 0))
    watched = dlaunch.build_argv(launch(conf, window=asked))
    assert watched.index("dosbox quit warning=false") < watched.index("sdl display=1")


def test_a_byte_that_spells_a_flag_name_is_sent_as_a_number() -> None:
    """On the real debugger `SM 9000:0040 AC` writes 00, `SM 9000:0060 0AC` writes AC."""
    s, sent = _writer({"held": bytes.fromhex("11AC0000")})
    out = ds.Session.write_memory(s, 0x9000, 0x0000, bytes.fromhex("11AC0000"))
    assert sent == ["SM 9000:0000 011 0AC 000 000"], sent
    assert out["verified"] is True


def test_step_refuses_a_running_machine_in_its_own_words_not_a_register_reads(
        tmp_path: Path) -> None:
    """`step`'s first act is to read the position, and a running machine refuses it as a step."""
    machine = Machine(stopped=False)
    session = session_over(machine, tmp_path)
    with pytest.raises(ds.NotStopped) as caught:
        session.step(mode="over", count=1)
    said = str(caught.value)
    assert "register read" not in said, f"step is still using `registers`' words: {said!r}"
    assert "step" in said.lower(), said
    assert not {"EXEC STEPIN", "EXEC RUN"} & set(machine.sent), machine.sent


def test_step_on_a_dead_emulator_escapes_as_itself_not_as_a_running_machine(
        tmp_path: Path) -> None:
    """THE OTHER HALF OF `step`'s OWN REFUSAL: a channel to a dead emulator is not a run."""
    machine = Machine(stopped=False)
    session = session_over(machine, tmp_path)
    machine.alive = False
    with pytest.raises(ds.Invalid) as caught:
        session.step(mode="over", count=1)
    assert caught.value.code == "session_broken", caught.value


def test_a_headless_caller_flag_reaches_argv(conf: Path) -> None:
    """A caller's `-set` is an EMULATOR flag, so it reaches argv headless too."""
    clock = ["-set", "cpu cycles=fixed 3000"]
    headless = dlaunch.build_argv(launch(conf, flags=clock))
    assert pair_at(headless, "cpu cycles=fixed 3000"), headless
    watched = dlaunch.build_argv(launch(conf, window=core_window.WindowRequest(1, False, (2048, 0)),
                                        flags=clock))
    assert pair_at(watched, "cpu cycles=fixed 3000"), watched
    assert headless.index("cpu cycles=fixed 3000") > headless.index("dosbox quit warning=false")


@pytest.mark.parametrize("flags", [["-set", "sdl autolock=false", ""], [""]])
def test_an_empty_token_is_refused_before_any_rule_about_its_neighbours(
        conf: Path, flags: list[str]) -> None:
    with pytest.raises(ds.Invalid, match="separate non-empty strings"):
        dlaunch.validate(launch(conf, flags=flags))


@pytest.mark.parametrize("flags", [["-set", "cpu", "cycles=fixed 3000"],
                                   ["-set cpu cycles=fixed 3000"], ["-set", ""],
                                   ["-set", "sdl"], ["-set", "cpu cycles 3000"]])
def test_a_shredded_or_glued_set_is_refused(conf: Path, flags: list[str]) -> None:
    """A `-set` with no `=` is ignored by DOSBox-X at rc 0, whether shredded or the value after a
    space."""
    with pytest.raises(ds.Invalid, match="bad_argument|-set"):
        dlaunch.validate(launch(conf, flags=flags))


@pytest.mark.parametrize("flags", [
    ["-time-limit", "0"], ["-conf", "other.conf"], ["-break-start"],
    ["-set", "sdl videodriver=cocoa"], ["-set", "log logfile=elsewhere.log"],
    ["-set", "dos  break on int3=false"], ["-set", "serial serial1=disabled"],
    ["-set", "cpu integration device=false"], ["-set", "dosbox captures=/tmp/x"],
    ["-set", "break on int3=false"], ["-set", "integration device=false"],
    ["-set", "windowresolution=800x600"], ["-set", "display=1"],
    ["-savedir", _abs("tmp", "states")], ["-c", "GAME.EXE"]])
def test_flags_may_not_retune_what_a_named_argument_owns(conf: Path, flags: list[str]) -> None:
    """`flags` carries the emulator's options, never one a named argument owns."""
    with pytest.raises(ds.Invalid, match="owns"):
        dlaunch.validate(launch(conf, flags=flags))


def test_flags_may_still_retune_the_defaults_no_argument_owns(conf: Path) -> None:
    """The quit warning and the clock are the caller's to set, with or without a section: the
    emulator takes `key=value` alone."""
    dlaunch.validate(launch(conf, flags=["-set", "dosbox quit warning=true",
                                    "-set", "cpu cycles=fixed 3000", "-set", "cycles=max"]))


def test_the_paging_mark_is_the_stop_surveys_and_a_later_survey_does_not_move_it(
        tmp_path: Path) -> None:
    """The paging bit a stop is recorded with is read by the same survey as its position."""
    machine = protected(Machine())
    session = session_over(machine, tmp_path)
    session.stop_survey()
    assert session.paging is True
    machine.regs["CR0"] = 0x11
    session.registers()
    session.stop_survey()
    assert session.paging is True, "a later reading at the same stop moved its paging bit"
    session.forget_stop()
    session.mark_stopped()
    session.stop_survey()
    assert session.paging is False, "the next stop kept the previous one's paging bit"


def test_a_stranger_that_takes_the_port_after_the_check_never_receives_the_input(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A port taken by another process after the check must never receive the input."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    port = _free_port()
    stranger: list[socket.socket] = []
    dialled: list[socket.socket] = []

    def spawn(*_a: object, **_k: object) -> Child:
        s = socket.socket()
        with contextlib.suppress(OSError):
            s.bind(("127.0.0.1", port))
            s.listen(1)
            s.settimeout(0.5)
            stranger.append(s)
        emulator = socket.socket()
        with contextlib.suppress(OSError):
            emulator.connect(("127.0.0.1", port))
        dialled.append(emulator)
        return Child()

    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: None)
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 2.0)
    try:
        ses = ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    except ds.Invalid:
        ses = None
    try:
        for s in stranger:
            with pytest.raises(OSError):
                s.accept()
        assert ses is not None and ses._input is not None
        assert ses._input.getpeername() == dialled[0].getsockname(), "not the emulator's socket"
    finally:
        for s in stranger + dialled:
            s.close()
        if ses is not None and ses._input is not None:
            ses._input.close()


def test_an_emulator_that_exits_before_it_dials_is_said_at_once() -> None:
    listener = dlaunch.listen_input(0)
    began = time.monotonic()
    with pytest.raises(ds.Invalid, match=r"exited \(code 3\) before it dialled"):
        dlaunch.accept_input(listener, 30.0, lambda: 3)
    assert time.monotonic() - began < 2.0, "it waited out the bound for a dead emulator"


def test_port_0_is_the_kernels_pick_held_from_the_moment_it_is_picked(conf: Path) -> None:
    listener = dlaunch.listen_input(0)
    try:
        port = listener.getsockname()[1]
        assert 1024 <= port <= 65535
        with pytest.raises(OSError):
            socket.socket().bind(("127.0.0.1", port))
    finally:
        listener.close()
    dlaunch.validate(launch(conf, input_port=0))


def test_a_spawn_that_fails_lets_the_port_go(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    port = _free_port()

    def refuse(*_a: object, **_k: object) -> None:
        raise OSError("no such emulator")
    monkeypatch.setattr(subprocess, "Popen", refuse)
    with pytest.raises(OSError) as held:
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    dlaunch.listen_input(port).close()
    assert held.value is not None


RECORDED = json.loads((Path(__file__).parent / "fixtures" / "console_replies" / "recorded.json")
                      .read_text(encoding="utf-8"))


def test_the_conf_is_hashed_again_only_when_it_moves(tmp_path: Path) -> None:
    """Every reply says whether the conf changed."""
    import os

    from scry_dosbox_x import launch as dl
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n")
    first = dl.current_digest(conf)
    calls: list[Path] = []
    real = dl.digest

    def counted(path: Path) -> str:
        calls.append(path)
        return real(path)
    dl_digest = dl.digest
    try:
        dl.digest = counted
        assert [dl.current_digest(conf) for _ in range(3)] == [first] * 3 and calls == []
        conf.write_text("[sdl]\nfullscreen=false\n")
        os.utime(conf, ns=(1, 1))
        assert dl.current_digest(conf) != first and calls == [conf]
    finally:
        dl.digest = dl_digest


def test_the_session_spawns_a_named_guardian_with_its_wall_clock_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_core import guardian
    seen: list[tuple[str, float]] = []

    class Spawned:
        pid = 12345

        def poll(self) -> int | None:
            return None

    def spawn(*_a: Any, **_k: Any) -> Spawned:
        return Spawned()

    def guard(child: object, name: str, deadline: float = 0.0) -> None:
        seen.append((name, deadline))
        raise OSError("stop here")
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr(ds.Session, "_signal_group", lambda *_a: None)
    monkeypatch.setattr(guardian, "spawn", guard)
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    before = time.time()
    with pytest.raises(OSError, match="stop here"):
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=90))
    assert seen and seen[0][0] == dprocess.PROCESS_NAME
    assert dprocess.GUARDIAN_NAME == "scry-dosbox-x-guardian"
    grace = dprocess.GUARDIAN_GRACE_S
    assert before + 90 + grace <= seen[0][1] <= time.time() + 90 + grace


def test_the_stub_takes_the_first_drive_from_y_down_that_the_conf_does_not_mount(
        tmp_path: Path) -> None:
    """`program` mounts the stub with `-c` after the conf's `[autoexec]`."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\nfullscreen=false\n[autoexec]\nmount c .\n@MOUNT y /tmp\n"
                    "imgmount x disk.img -t hdd\nsubst W: C:\\TOOLS\n", encoding="utf-8")
    argv = dlaunch.build_argv(launch(conf, program="APP.EXE", input_port=5555))
    assert f'mount V "{dlaunch.GUEST_DIR}"' in argv and "V:\\SCRY.COM" in argv, argv
    every = "\n".join(f"mount {d} ." for d in "DEFGHIJKLMNOPQRSTUVWXY")
    conf.write_text(f"[autoexec]\n{every}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match=r"no drive from Y: to D: is free.*mounts D:, E:"):
        dlaunch.validate(launch(conf, program="APP.EXE", input_port=5555))
    dlaunch.validate(launch(conf, program="", input_port=5555))
    dlaunch.validate(launch(conf, program="APP.EXE", input_port=None))


@pytest.mark.parametrize(("autoexec", "taken"), [
    ("mount -t cdrom d /cd", "D"), ("[AUTOEXEC]\nMOUNT y .", "Y"),
    ("imgmount -t floppy a a.img", "A"), ("subst x: c:\\tools", "X"),
    ("[autoexec] # the program starts here\nmount y .", "Y"),
])
def test_a_conf_s_mounts_are_read_past_options_case_and_a_bom(tmp_path: Path, autoexec: str,
                                                            taken: str) -> None:
    conf = tmp_path / "g.conf"
    head = "" if autoexec.startswith("[") else "[autoexec]\n"
    conf.write_text(f"{head}{autoexec}\n[sdl]\nmount q .\n", encoding="utf-8-sig")
    assert dconf.conf_mounts(conf) == [taken], "a mount outside [autoexec] counted, or missed"


def test_a_stub_the_conf_runs_is_judged_by_the_protocol_it_carries(tmp_path: Path) -> None:
    for name, proto in (("old", 6), ("new", 7), ("stale build", 6)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "SCRY.COM").write_bytes(b"\x90SCRY-INJECT-%d\x00" % proto)
    conf = tmp_path / "g.conf"
    conf.write_text('[autoexec]\nmount g "old" -ro\ng:\\SCRY.COM\nmount H new\n@h:\\scry.com\n'
                    'mount i missing\ni:\\SCRY.COM\nmount k "stale build"\nk:\\SCRY.COM\n'
                    '[sdl]\nj:\\SCRY.COM\n', encoding="utf-8")
    assert dconf.stub_protocols(conf, tmp_path) == [("g:\\SCRY.COM", "6"),
                                                    ("@h:\\scry.com", "7"),
                                                    ("k:\\SCRY.COM", "6")]


def test_start_says_when_the_conf_runs_a_stub_of_another_protocol(tmp_path: Path) -> None:
    for name, proto in (("old", 6), ("new", int(inputs.STUB_PROTOCOL))):
        (tmp_path / name).mkdir()
        (tmp_path / name / "SCRY.COM").write_bytes(b"SCRY-INJECT-%d" % proto)
    conf = tmp_path / "g.conf"
    conf.write_text('[cpu]\ncore=normal\n[autoexec]\nmount g old\ng:\\SCRY.COM\n', encoding="utf-8")
    note = lifecycle._notes(launch(conf))["note"]
    assert "stub of protocol 6" in note and f"speaks {inputs.STUB_PROTOCOL}" in note, note
    conf.write_text('[cpu]\ncore=normal\n[autoexec]\nmount g new\ng:\\SCRY.COM\n', encoding="utf-8")
    assert lifecycle._notes(launch(conf)) == {}, "a stub of this protocol is nothing to say"


@pytest.mark.parametrize(("conf_text", "flags", "core"), [
    ("[cpu]\ncore=dynamic\n", [], "dynamic"),
    ("[cpu]\nCore = Dynamic_x86\n", [], "dynamic_x86"),
    ("[cpu]\ncore=normal\n", [], "normal"),
    ("[cpu]\ncore=auto\n", [], "auto"),
    ("[sdl]\ncore=dynamic\n", [], "auto"),
    ("[cpu]\ncore=dynamic\n", ["-set", "cpu core=normal"], "normal"),
    ("[cpu]\ncore=normal\n", ["-set", "cpu core=dynamic"], "dynamic"),
    ("[cpu]\ncore=normal\n", ["-set", "cpu core=dynamic", "-set", "cpu core=auto"], "auto"),
    ("[cpu]\ncore=dynamic\n", ["-set", "sdl fullscreen=true"], "dynamic"),
    ("\ufeff[CPU]\ncore=dynamic\n", [], "dynamic"),
    ("[cpu] # the processor\ncore=dynamic\n", [], "dynamic"),
    ("[cpu]\ncore=normal\n", ["-set", "CPU CORE=dynamic"], "dynamic"),
    ("[cpu]\ncore=normal\n", ["-set", "cpu", "core", "dynamic"], "normal"),
    ("[cpu]\ncore= # use the default\n", [], "auto"),
    ("[cpu]\ncore=normal\ncore= # nothing\n", [], "normal"),
])
def test_the_core_a_session_boots_with_is_the_flags_last_word_over_the_confs(
        tmp_path: Path, conf_text: str, flags: list[str], core: str) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text(conf_text, encoding="utf-8")
    assert dconf.cpu_core(conf, flags) == core


@pytest.mark.parametrize(("token", "key", "value"), [
    ("cpu core=dynamic", ["cpu", "core"], "dynamic"),
    ("CPU CORE = Dynamic ", ["cpu", "core"], "dynamic"),
    ("core=auto", ["core"], "auto"),
    ("sdl windowresolution=1280x720", ["sdl", "windowresolution"], "1280x720"),
    ("cpu", ["cpu"], ""),
])
def test_a_set_token_is_read_once_into_its_key_words_and_its_value(
        token: str, key: list[str], value: str) -> None:
    assert dconf.split_set(token) == (key, value)


@pytest.mark.parametrize("from_zero", [False, True])
def test_a_wait_bound_takes_its_maximum_and_refuses_one_past_it(from_zero: bool) -> None:
    zero_means = "no wait" if from_zero else ""
    vocab.check_wait(vocab.WAIT_MAX_S, zero_means=zero_means)
    with pytest.raises(ds.Invalid, match="seconds"):
        vocab.check_wait(vocab.WAIT_MAX_S + 0.5, zero_means=zero_means)
    if from_zero:
        vocab.check_wait(0, zero_means="no wait")
    else:
        with pytest.raises(ds.Invalid, match="seconds"):
            vocab.check_wait(0)


def test_the_argument_judges_take_their_edges_and_refuse_one_past(
) -> None:
    """Each judge at its maximum and its minimum, one past each refused `bad_argument`."""
    for count in (1, stepping.STEP_MAX):
        stepping.check_step("into", count)
    for count in (0, stepping.STEP_MAX + 1):
        with pytest.raises(ds.Invalid) as e:
            stepping.check_step("into", count)
        assert e.value.code == "bad_argument"
    for number, ah in ((0, None), (ds.BYTE_MAX, None), (0x21, 0), (0x21, ds.BYTE_MAX)):
        ds.check_interrupt(number, ah)
    for number, ah in ((-1, None), (ds.BYTE_MAX + 1, None), (0x21, ds.BYTE_MAX + 1)):
        with pytest.raises(ds.Invalid):
            ds.check_interrupt(number, ah)
    ds.check_dump_length(1)
    with pytest.raises(ds.Invalid):
        ds.check_dump_length(0)


def test_two_programs_under_one_conf_keep_their_own_declarations(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"

    def identity(program: str | None) -> str:
        return dlaunch.store_identity(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60,
                                                     program=program))

    assert identity("A.EXE") != identity("B.EXE")
    assert identity("A.EXE") == identity("a.exe /x") == identity("A.EXE one two")
    assert identity(None) == identity("") == str(conf.resolve())
