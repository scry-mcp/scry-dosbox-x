"""What the session guarantees, held to fixtures rather than to a live emulator.

EVERY CASE HERE EXISTS BECAUSE SOMETHING WENT WRONG ONCE.  The channel guard, the
tail slice, the refusals and the argv adjacency are not hypotheticals: each was a
defect measured while this server was built, and each is written as the NEGATIVE that
would have caught it.

AND EVERY RED HAS A GREEN BESIDE IT.  A refusal test on its own passes just as well
when the guard refuses EVERYTHING, so each one is paired with a case that must get
through.  That pairing is the difference between "the guard fires" and "the guard
fires on the right thing".
"""

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
from typing import Any, cast

import pytest
from scry_core import vocabulary as vocab
from test_dosbox_x_stub_link import REPORT, Stub

import dosbox_console as dcons
import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_process as dprocess
import dosbox_session as ds
import dosbox_stub_link as stub_link
import dosbox_symbols as dsym

# --------------------------------------------------------------------- fixtures



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
    """Is `value` immediately after a `-set`?

    ADJACENCY, not membership. A `-set` and its value present but APART is the
    shredded-pair failure this fleet has measured: DOSBox-X accepts the stray tokens
    and silently ignores the setting, so two independent `in` checks pass while the
    option never takes effect.
    """
    return any(argv[i] == "-set" and argv[i + 1] == value
               for i in range(len(argv) - 1))


# ------------------------------------------------------- the command line's shape

def test_the_launch_is_the_binary_the_conf_and_a_stop_at_the_debugger(conf: Path) -> None:
    """The three tokens the whole design rests on, asserted by POSITION.

    `-break-start` is what makes a session start stopped and askable; without it the
    guest runs away and every later tool is INVALID. It was asserted by nothing.
    """
    argv = dlaunch.build_argv(launch(conf))
    assert argv[0] == "dosbox-x"
    assert argv[argv.index("-conf") + 1] == str(conf)
    assert "-break-start" in argv
    assert "-fastlaunch" in argv


def test_headless_uses_the_emulators_own_video_property(conf: Path) -> None:
    """Not SDL_VIDEODRIVER, and not -silent.

    `videodriver` is DOSBox-X's own `[sdl]` property and names `dummy` in its own
    description, so headless is the application agreeing rather than us going around
    it. `-silent` also hides the window but EXITS after AUTOEXEC.BAT, which cannot
    host a session at all.
    """
    argv = dlaunch.build_argv(launch(conf))
    assert pair_at(argv, "sdl videodriver=dummy")
    assert "-silent" not in argv


def test_a_watched_session_gets_no_dummy_driver_and_keeps_the_callers_flags(conf: Path) -> None:
    """The IDENTITY axis: the two branches must not be interchangeable.

    A test that only checked "the flags appear" would pass with the branches swapped,
    which is the failure that puts a window on the display nobody is looking at while
    reporting headless. And the ORDER of the caller's flags is preserved, so a
    reversal is caught too: `-set` and its value are a pair, not a set.
    """
    flags = ["-set", "sdl display=1", "-set", "sdl windowposition=0,0"]
    argv = dlaunch.build_argv(launch(conf, watched=True, window_flags=flags))
    assert not pair_at(argv, "sdl videodriver=dummy")
    assert argv[-len(flags):] == flags


def test_every_launch_carries_its_bound(conf: Path) -> None:
    """DOSBox-X does not refuse an unknown option, it HANGS (measured). The bound is
    the only thing that ends an abandoned session."""
    argv = dlaunch.build_argv(launch(conf, seconds=45))
    assert argv[argv.index("-time-limit") + 1] == "45"


def test_the_logfile_and_the_captures_directory_go_to_their_own_settings(conf: Path,
                                                                        tmp_path: Path) -> None:
    """The IDENTITY axis again, and it is not cosmetic: swapped, `e9` reads a file
    nothing writes and `memdump` collects from a directory nothing fills, both
    silently."""
    log, cap = tmp_path / "g.log", tmp_path / "caps"
    argv = dlaunch.build_argv(launch(conf, logfile=log, captures_dir=cap))
    assert pair_at(argv, f"log logfile={log}")
    assert pair_at(argv, f"dosbox captures={cap}")


def test_neither_setting_appears_when_it_was_not_asked_for(conf: Path) -> None:
    """The green beside the red above: the branches are conditional, not unconditional."""
    argv = dlaunch.build_argv(launch(conf))
    assert not any(a.startswith(("log logfile=", "dosbox captures=")) for a in argv)


def test_capture_wraps_the_program_and_plain_does_not(conf: Path) -> None:
    """DX-CAPTURE is the ONLY screen capture with nobody at the keyboard: the still
    screenshot is a mapper action and needs a key."""
    plain = dlaunch.build_argv(launch(conf, program="GAME.EXE"))
    assert plain[plain.index("-c") + 1] == "GAME.EXE"
    shot = dlaunch.build_argv(launch(conf, program="GAME.EXE", capture_video=True))
    assert shot[shot.index("-c") + 1] == "DX-CAPTURE /V GAME.EXE"


def test_the_serial_route_is_two_set_overrides_and_a_port_in_range(conf: Path) -> None:
    """`input_port` puts the two switches the route needs on the argv as `-set` overrides --
    the integration device in the `[cpu]` section, where it is honoured, and COM1 as a
    nullmodem dialling the session on that port -- and a port outside the unprivileged range is
    refused before any process exists. Without a port the argv carries neither."""
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
    """`accept_input` takes the emulator's dial on the session's listener, so a dial that
    comes a moment after the emulator starts is reached, and closes the listener; no dial
    within the bound is a refusal naming the port, never a session with a route that does not
    exist. And `send_commands` sends what it is given through the session's link, refuses an
    empty send, and reports a socket the other end closed as the route being GONE rather than
    as a delivery."""
    listener = dlaunch.listen_input(_free_port())
    port = listener.getsockname()[1]
    emulator = socket.socket()
    threading.Timer(0.2, lambda: emulator.connect(("127.0.0.1", port))).start()
    try:
        client = dlaunch.accept_input(listener, 3.0, lambda: None)
        peer = emulator
        with pytest.raises(OSError):
            listener.accept()            # closed once the dial was taken
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
    """A port another process listens on cannot be the session's: refused naming it, and once
    free it is listened on, and held, so nothing else can take it."""
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        with pytest.raises(ds.Invalid, match=f"input_port {port} is already in use"):
            dlaunch.listen_input(port)
    finally:
        holder.close()
    held = dlaunch.listen_input(port)      # free again: listened on
    try:
        with pytest.raises(OSError):
            socket.socket().bind(("127.0.0.1", port))
    finally:
        held.close()


def test_a_dial_that_never_comes_kills_the_child_it_spawned(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE ARM THAT MATTERS: the emulator's dial is accepted inside the constructor's `try`,
    so one that never comes must kill that emulator and re-raise, never leave one running
    behind a refusal, and let the port go. The child and the signal are doubled; the drain
    thread is real and is joined before the pty is closed."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Child:
        pid = 4242

        def __init__(self) -> None:
            self.waited = 0

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            self.waited += 1
            return -9

    child = Child()
    signalled: list[int] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: child)
    monkeypatch.setattr(ds.Session, "_signal_group", lambda self, sig: signalled.append(sig))
    monkeypatch.setattr(dlaunch, "INPUT_CONNECT_S", 0.3)    # the double never dials
    port = _free_port()
    with pytest.raises(ds.Invalid, match="never dialled"):
        ds.Session(dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=30, input_port=port))
    dlaunch.listen_input(port).close()      # the session let its listener go
    assert signalled == [signal.SIGKILL] and child.waited == 1, (signalled, child.waited)


def test_the_program_reaches_the_emulator_as_one_argv_element(conf: Path) -> None:
    """The vocabulary is ours; the values are the caller's.

    An earlier version of this case asserted `"-loadstate" not in argv`, which cannot
    fail: `in` on a list is element equality, so a program string containing that word
    is never an element whatever `build_argv` does. What has to hold is that the
    program stays ONE token -- split, its tail arrives in FLAG position, and by this
    emulator's own measurement an unrecognised flag does not fail, it hangs.
    """
    nasty = "X.EXE; -loadstate 1"
    argv = dlaunch.build_argv(launch(conf, program=nasty))
    assert argv[argv.index("-c") + 1] == nasty
    assert argv.count("-c") == 1


# ---------------------------------------------------------------- the refusals
#
# THESE CALL `validate` AND NEVER `Session`, and that is not a stylistic choice.
# While the guards lived inside the constructor, testing them meant CONSTRUCTING a
# session, so the break that deletes a guard did not make a test fail -- it made
# the test START A REAL EMULATOR that nothing then closed. MEASURED: six left running
# on the machine, and the one from the missing-bound case carried `-time-limit 0`,
# which is no bound at all. A pure decision cannot spawn anything, broken or not.

def test_a_valid_launch_passes_validation_without_starting_anything(conf: Path) -> None:
    """The green beside every red below. Without it, `validate` could refuse
    EVERYTHING and the whole group would still pass."""
    dlaunch.validate(launch(conf))
    dlaunch.validate(launch(conf, watched=True, window_flags=["-set", "sdl x=1"]))
    dlaunch.validate(launch(conf, program="G.EXE", capture_video=True))


def test_a_session_that_cannot_be_reproduced_is_refused_before_it_exists(tmp_path: Path) -> None:
    with pytest.raises(ds.Invalid, match="no conf"):
        dlaunch.validate(dlaunch.Launch(conf=tmp_path / "gone.conf", cwd=tmp_path, seconds=30))


def test_a_missing_working_directory_is_refused_too(conf: Path, tmp_path: Path) -> None:
    """It is guarded for the same reason the conf is, and for one more: a bad cwd makes
    `Popen` raise AFTER the pseudo-terminal is open, leaking two descriptors on an
    object nothing can reach to close."""
    with pytest.raises(ds.Invalid, match="working directory"):
        dlaunch.validate(launch(conf, cwd=tmp_path / "nowhere"))


def test_a_glued_placement_pair_is_refused(conf: Path) -> None:
    """`-set` and its value are two tokens. Arriving as one, DOSBox-X does not refuse
    it, it hangs on it.

    THIS TEST PASSED FOR THE WRONG REASON FOR ITS WHOLE LIFE. Its fixture carried TWO
    malformations -- the glued pair AND a trailing `""` -- and the guard only ever
    tested the type and the emptiness, so it was the empty string that raised. MEASURED:
    the glued pair ALONE validated clean. The fixture is now one
    malformation per case, each asserting the message that belongs to it, which is the
    only arrangement in which either can fail for its own reason.
    """
    with pytest.raises(ds.Invalid, match="GLUED into one token"):
        dlaunch.validate(launch(conf, watched=True, window_flags=['-set "sdl display=1"']))
    with pytest.raises(ds.Invalid, match="GLUED into one token"):
        dlaunch.validate(launch(conf, watched=True, window_flags=["-set sdl display=1"]))


def test_an_empty_placement_flag_is_refused(conf: Path) -> None:
    """The OTHER malformation, which a single case would fold into its neighbour's."""
    with pytest.raises(ds.Invalid, match="separate non-empty strings"):
        dlaunch.validate(launch(conf, watched=True, window_flags=["-fullscreen", ""]))


def test_a_value_holding_a_space_is_the_normal_case_and_passes(conf: Path) -> None:
    """THE CONTROL, and the reason the rule is "an option is one word" rather than
    anything about quotes: `place-window` emits `-set` and `sdl display=1` as two argv
    tokens, and the second one HAS to be allowed to hold a space. A guard that refused
    every token with a space in it would reject the correct call."""
    dlaunch.validate(launch(conf, watched=True,
                       window_flags=["-set", "sdl display=1", "-fullscreen"]))


def test_an_unbounded_session_is_refused(conf: Path) -> None:
    """Zero is the DANGEROUS value, not merely an invalid one: DOSBox-X reads
    `-time-limit 0` as no limit."""
    for bad in (0, -1):
        with pytest.raises(ds.Invalid, match="without a bound"):
            dlaunch.validate(launch(conf, seconds=bad))


def test_a_bound_too_large_to_bound_anything_is_refused(conf: Path) -> None:
    """The ceiling, at its boundary: the value AT the limit passes and one past it
    does not. A test using a far-away number leaves the threshold free to move."""
    dlaunch.validate(launch(conf, seconds=dlaunch.MAX_SECONDS))
    with pytest.raises(ds.Invalid, match="not a bound"):
        dlaunch.validate(launch(conf, seconds=dlaunch.MAX_SECONDS + 1))


def test_capture_without_a_program_to_capture_is_refused(conf: Path) -> None:
    """DX-CAPTURE wraps a PROGRAM. Without one the flag was accepted and quietly did
    nothing, and the reply said ok."""
    with pytest.raises(ds.Invalid, match="needs a program"):
        dlaunch.validate(launch(conf, capture_video=True))


# ------------------------------------------------------------- the E9 channel

LIVE = "Bochs port E9h: [+   9.122] AUDIO . loudness: A=-19.1 B=-29.6\n"
LIVE2 = "Bochs port E9h: [+  12.000] AUDIO . loudness: A=-18.0 B=-28.0\n"
REPLAY = "dosbox-run: | LOG: Bochs port E9h: [+   9.122] AUDIO . loudness: A=-19.1\n"
NOISE = "gcc -o build/GAME.EXE src/audio.c src/loudness.c\n"


def test_only_an_instrumentation_line_can_match() -> None:
    """The defect this guard exists for, reproduced as a fixture.

    Both other lines CONTAIN the pattern: one is a build log naming a source file, the
    other is a tool's report quoting a trace back. A filter matching on content alone
    returns three; the channel guard returns one.
    """
    lines, total = dlogs.filter_e9(NOISE + LIVE + REPLAY, "loudness", 10)
    assert total == 1
    assert lines == [LIVE.rstrip("\n")]


def test_a_pattern_that_matches_nothing_is_an_answer() -> None:
    """Empty is an answer; INVALID is what "there was no channel" gets. A caller that
    cannot tell them apart reports a broken instrument as a clean result."""
    assert dlogs.filter_e9(LIVE, "no-such-thing", 10) == ([], 0)


def test_the_total_is_what_matched_and_not_what_came_back() -> None:
    """The COUNT axis. Reporting the slice's length under the name `matched` meant a
    caller asking "how many times did this fire" got the limit back."""
    text = "".join(f"Bochs port E9h: [+ {i}.0] TICK n={i}\n" for i in range(10))
    lines, total = dlogs.filter_e9(text, "TICK", 3)
    assert total == 10
    assert len(lines) == 3


def test_the_limit_keeps_the_tail_and_not_the_head() -> None:
    """The ORDER axis, not the presence one.

    A test asserting only "limit lines came back" passes with a head slice, and a head
    slice answers every question with the boot.
    """
    text = "".join(f"Bochs port E9h: [+ {i}.0] TICK n={i}\n" for i in range(10))
    lines, _ = dlogs.filter_e9(text, "TICK", 3)
    assert [ln.split("n=")[1] for ln in lines] == ["7", "8", "9"]


def test_a_limit_of_zero_or_less_is_refused() -> None:
    """`limit=0` reads naturally as "no cap" and `limit=-1` as "all", and both would
    return the entire log: the haystack this exists to stop carrying."""
    for bad in (0, -1):
        with pytest.raises(ds.Invalid, match="haystack"):
            dlogs.filter_e9(LIVE, "loudness", bad)
    # AND A CEILING, because a guard whose own words call the whole log "the haystack
    # this exists to stop carrying" still lets `limit=1000000` carry it. The boundary:
    # the ceiling itself is taken, one past it is refused.
    dlogs.filter_e9(LIVE, "loudness", dlogs.LOG_LIMIT_MAX)
    with pytest.raises(ds.Invalid, match=f"1..{dlogs.LOG_LIMIT_MAX}"):
        dlogs.filter_e9(LIVE, "loudness", dlogs.LOG_LIMIT_MAX + 1)


def test_an_unusable_pattern_is_invalid_and_does_not_escape() -> None:
    """`pattern` is the caller's regular expression. A malformed one raises `re.error`,
    which is not `Invalid`, so uncaught it reaches the caller as a traceback instead of
    the clean refusal this contract is built on."""
    with pytest.raises(ds.Invalid, match="not a usable pattern"):
        dlogs.filter_e9(LIVE, "[", 10)


def test_the_two_nothings_are_counted_apart() -> None:
    """A log with instrumentation and no match is an answer; a log with none at all is
    a statement about the build, and the caller has to be able to tell which it got.

    The COUNT axis: the fixture holds TWO instrumentation lines, so a counter that
    only ever looks at the first line is caught. With one, it is not.
    """
    assert dlogs.count_e9(NOISE + LIVE + REPLAY + LIVE2) == 2
    assert dlogs.count_e9(NOISE + REPLAY) == 0


# -------------------------------------------------------------- the register pane

# CAPTURED FROM A LIVE EMULATOR, not written from what a register pane is imagined to
# look like. An ncurses pane is painted as runs of cells and the debugger draws its
# frames with the alternate character set, which arrives as ordinary letters -- so a
# register name abuts the run in front of it. A tidy hand-written fixture with a
# newline before `EAX` is exactly what hid the bug: `\b` finds no boundary between `o`
# and `E`, so EAX (the register a caller SETS to prove the machine answered) was the
# one name that never matched, while every register following a space read fine.
REAL_PANE = ("ooooooooooooooooooooooooooooooooooooooo"
             "EAX=00001234  ESI=00000000  DS=0000   ES=0000   FS=0000   GS=0000\n"
             "EBX=00004321  EDI=00000000  CS=F000   EIP=0000DAC6\n")


def test_a_register_name_that_abuts_the_pane_fill_is_still_read() -> None:
    regs = dcons.parse_registers(REAL_PANE)
    assert regs["EAX"] == "00001234"
    assert regs["EBX"] == "00004321"
    assert regs["EIP"] == "0000DAC6"


def test_the_newest_repaint_wins() -> None:
    """The RECENCY axis, which no assertion on values can reach.

    A delta can carry several repaints of the same pane, and the staleness the nudge
    exists to prevent comes back if the FIRST one wins. Both are valid panes with
    valid values, so every content assertion passes either way.
    """
    older = "EAX=00000001  EIP=00000010\n"
    newer = "EAX=000000FF  EIP=000000F0\n"
    regs = dcons.parse_registers(older + newer)
    assert regs["EAX"] == "000000FF"
    assert regs["EIP"] == "000000F0"


def test_a_screen_with_no_pane_parses_to_nothing() -> None:
    """So `registers()` can raise INVALID rather than hand back an empty mapping that
    reads like a machine with empty registers."""
    assert dcons.parse_registers("DEBUG: Set Register success.\nI-> _") == {}


def test_a_child_that_could_not_be_reaped_is_recorded_and_not_reported_as_clean(
) -> None:
    """SIGKILL cannot be ignored, so a wait that still expires means the child was not
    REAPED -- and `close` then returns `self.proc.returncode`, which is None. The
    server drops its reference straight afterwards, so the only trace of a process
    nothing can reach any more would be `exit_code: null`, indistinguishable from a
    clean end.

    THE FIRST VERSION OF THIS FIX WAS `max(grace, 1.0)` AND NOTHING ELSE, which makes
    the case unlikely rather than reportable. A round of review neutralised the
    recording and the whole battery stayed green, because the only case naming it covers a test
    that covers `state()`'s pass-through of the field, never `close()` setting it.
    This exercises the assignment.
    """
    class NeverDies:
        returncode: int | None = None

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="dosbox-x", timeout=timeout or 0)

    sent: list[int] = []
    fake = SimpleNamespace(
        proc=NeverDies(), reap_failed="", drain_ended="", _drainer=None,
        _master=-1, _stop=threading.Event(), _signal_group=sent.append)
    rc = ds.Session._close(fake, grace=0)  # type: ignore[arg-type]
    assert rc is None, "a child that was never reaped has no exit code"
    assert fake.reap_failed.startswith("SIGKILL was sent"), (
        f"the session reported nothing about a child it could not reap: "
        f"{fake.reap_failed!r}")
    # THE SIGNALS THEMSELVES, in order. Nothing asserted their IDENTITY, so replacing
    # SIGKILL with a second SIGTERM left the whole contract battery green -- and the
    # message above, which says "SIGKILL was sent", became a lie its own assertion
    # accepted.
    assert sent == [signal.SIGTERM, signal.SIGKILL], sent

    # THE CONTROL IGNORES SIGTERM AND THEN DIES ON SIGKILL, which is the ORDINARY
    # close of a running session on this build. Its first version returned at the
    # SIGTERM wait, so it never reached SIGKILL at all -- and with that control,
    # recording on EVERY SIGKILL rather than only on the expiry was green. Since
    # SIGTERM is measured to be ignored while the guest runs, that break would have
    # stamped "the exit code is not a reading of how it died" on essentially every real
    # close.
    class IgnoresTermDiesOnKill:
        returncode = -9

        def __init__(self) -> None:
            self.first = 0.0
            self.stretches = 0                       # the SIGTERM budget, then the SIGKILL's

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            # The SIGTERM budget, ignored for its whole stretch (the wait comes in slices
            # so the line can be painted); reaped after SIGKILL.
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
        proc=proc, reap_failed="", drain_ended="", _drainer=None,
        _master=-1, _stop=threading.Event(), _signal_group=ok_sent.append)
    assert ds.Session._close(ok) == -9  # type: ignore[arg-type]
    assert ok_sent == [signal.SIGTERM, signal.SIGKILL], ok_sent
    assert proc.stretches == 2, "the control never reached the SIGKILL wait"
    assert ok.reap_failed == "", (
        "a child that WAS reaped after SIGKILL was reported as unreapable, which is "
        "the ordinary close of a running session")


def test_a_still_whose_destination_already_exists_is_refused_before_ffmpeg_runs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The caller's file is NEVER deleted. Unlinking `dest` before asking ffmpeg for the
    frame turns a frame past the end of the capture (ffmpeg writes nothing, exit code
    zero) into a lost file with the reply INVALID about the frame:
    `capture_frame(frame=9999, dest="README.md")` would be a delete. A `dest` that is
    already there is refused, saying so, before ffmpeg is asked anything, and the bytes
    at `dest` are the caller's afterwards, whatever they were.
    """
    mine = tmp_path / "README.md"
    mine.write_bytes(b"the caller's own file, nothing to do with a frame")
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    ran: list[list[str]] = []

    def record_run(argv: list[str], **_k: object) -> SimpleNamespace:
        ran.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", record_run)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.frame(fake, 9999, mine)  # type: ignore[arg-type]
    assert mine.read_bytes() == b"the caller's own file, nothing to do with a frame", (
        "it deleted or overwrote the caller's file")
    assert ran == [], "ffmpeg was asked for a frame before the destination was judged"
    # A DANGLING SYMLINK AT `dest` IS "THERE" TOO. `exists()` follows the link and reads
    # False, and an `open()` through it creates the file at the link's TARGET, anywhere
    # on the filesystem: the family `load_symbols`'s guard already names.
    (tmp_path / "elsewhere").mkdir()
    link = tmp_path / "shot.png"
    link.symlink_to(tmp_path / "elsewhere" / "victim.png")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.frame(fake, 7, link)  # type: ignore[arg-type]
    assert ran == [] and not (tmp_path / "elsewhere" / "victim.png").exists()


def test_a_destination_that_is_a_numbering_template_is_refused(
        tmp_path: Path) -> None:
    """`-f image2` reads the path as a printf TEMPLATE.

    MEASURED: a `dest` of `shot%03d.png` makes ffmpeg write `shot001.png` and leave
    `dest` untouched, after which the refusal blames "a frame past the end" for an
    extraction that worked. The format is forced for every extension now, so this
    reaches any caller rather than only one who named a `.png`.
    """
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    with pytest.raises(ds.Invalid, match="containing `%` is refused"):
        ds.Session.frame(fake, 7, tmp_path / "shot%03d.png")  # type: ignore[arg-type]

    # AND ONE COMPONENT UP, which is the half a check on `dest.name` misses and the
    # half a caller is likelier to write: with a literal `run%d/` there, ffmpeg writes a
    # perfectly good PNG into an expanded sibling `run1/`, and the caller is told a frame
    # past the end.
    with pytest.raises(ds.Invalid, match="containing `%` is refused"):
        ds.Session.frame(fake, 7, tmp_path / "run%d" / "shot.png")  # type: ignore[arg-type]


def test_a_destination_with_no_directory_is_a_refusal_not_a_traceback(
        tmp_path: Path) -> None:
    """`tool()` translates only `Invalid`, so a bare `PermissionError` out of a write reaches an
    MCP caller as a traceback, losing the reply's account of what it found and the session's
    state. A `dest` whose directory is not there is refused by name, before either writer asks
    the emulator for anything; nothing creates it."""
    missing = tmp_path / "missing"
    fake = SimpleNamespace(captures=lambda: [{"path": str(tmp_path / "cap.avi")}])
    with pytest.raises(ds.Invalid, match="is not a directory"):
        ds.Session.frame(fake, 7, missing / "shot.png")  # type: ignore[arg-type]
    # The same judge on the other writer, before the debugger is asked: nothing is written
    # to be abandoned in the working directory.
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


# ------------------------------------------------------------- where a dump lands

def test_the_dump_is_looked_for_in_the_working_directory_first(tmp_path: Path) -> None:
    """The one property the whole `memdump` defect was about, asserted by name.

    A tool collecting the debugger's file from the CAPTURES directory, on the strength of
    a line in the debugger's own help, never works once: the file lands in the emulator's
    WORKING directory, and every dump returns INVALID.

    That is caught by two other cases, but INCIDENTALLY -- one is about the
    dump's SIZE and the other about refusing to delete somebody's file, and both
    happen to go red when the candidate list empties. A break whose only accuser is
    a test named for something else is a break with no attribution: if either of
    those is ever narrowed, this property loses its cover in silence and nothing says
    so. So it is asked here, by its own name.

    BOTH SPELLINGS ARE CHECKED because a case-folding filesystem hides which of the
    two is really on disk, and the working directory comes FIRST because that is where
    the file was measured. The name `memdump` passes is first, the default after it.
    """
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
    # THE CAPTURES DIRECTORY IS STILL CHECKED, and after: that was one build on one
    # platform, so neither place is dropped on the strength of a single measurement.
    assert any(p.parent == caps for p in got), got

    # AND WITH NO CAPTURES DIRECTORY the working directory is still there, which is
    # the configuration `memdump` is normally called in: it needs neither that
    # argument nor a capture, and a list that came back empty would make every dump
    # INVALID again.
    bare = SimpleNamespace(launch=dlaunch.Launch(conf=conf, cwd=work, seconds=60))
    assert ds.Session._memdump_candidates(bare)  # type: ignore[arg-type]


# ----------------------------------------------------------------- the data view

# CAPTURED FROM A LIVE EMULATOR, and it is the SAME lesson as REAL_PANE above rather
# than a second copy of it: the pane header abuts the first data row with no newline,
# because an ncurses screen is painted as runs of cells. A tidy hand-written fixture
# with a newline before `F000:0000E000` is exactly what would hide the defect this
# was written after.
#
# THE CODE OVERVIEW IS IN IT ON PURPOSE. It sits on the same screen, shows the same
# segment, and its rows begin identically -- so a fixture holding only the data view
# could not tell "it reads the data view" from "it reads any address-looking row",
# which is the discrimination the whole pattern rests on.
REAL_DATA_VIEW = (
    "ooooData view (segmented)oooooooooooooooooooooooooo"
    "F000:0000E000 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49 42  ..............IB\r\n"
    "F000:0000E010 4D 20 43 4F 4D 50 41 54 49 42 4C 45 20 42 49 4F  M COMPATIBLE BIO\r\n"
    "ooooCode Overviewoooooooooooooooooooooooooooooooooo"
    "F000:0000FFF0 EA5BE000F0          jmp  F000:E05B\r\n"
    "F000:0000FFF5 3031xor  [bx+di],dhds:[0000]=0000\r\n"
    "ooooOutputooooooooooooooooooooooooooooooooooooooooo"
    "DEBUG: Set data overview to F000:E000\r\nI-> _")


def test_a_data_row_that_abuts_the_pane_header_is_still_read() -> None:
    """THE ROW THE CALLER ASKED ABOUT IS THE FIRST ONE, and the first one is the one
    that abuts. MEASURED against a live emulator with the pattern anchored at line
    start: eight rows on screen, SEVEN parsed, and the missing one was E000 for a
    caller who had asked for E000. Losing any other row would be a degradation;
    losing this one makes the tool answer about somewhere else."""
    rows = dcons.parse_data_view(REAL_DATA_VIEW)
    assert rows[0].startswith("F000:0000E000"), rows
    assert rows[0].endswith("..............IB"), "the ASCII gutter was cut off"
    assert len(rows) == 2, rows


def test_a_code_row_is_not_a_data_row() -> None:
    """The discrimination the shape rests on, asserted rather than assumed.

    A code row carries the same segment and the same address shape; what it does NOT
    carry is sixteen SPACE-SEPARATED byte pairs, because its bytes are run together.
    Without this, `read_memory` would happily return the disassembly sitting two panes
    below and call it memory.

    IT ASSERTS THE ADDRESSES, NOT THE MNEMONIC TEXT, and the difference is a measured
    blind spot rather than a refinement. Loosening the pattern's `{16}` to `{1,16}` --
    the natural way to break this -- makes code rows parse as `'F000:0000FFF0 EA'`,
    which stops BEFORE the `jmp`, so a test asking "is `jmp` absent" stays green while
    two disassembly rows enter a `read_memory` reply. Naming the addresses that may
    come back cannot be satisfied that way.
    """
    rows = dcons.parse_data_view(REAL_DATA_VIEW)
    assert [r.split()[0] for r in rows] == ["F000:0000E000", "F000:0000E010"], rows
    assert not any("jmp" in r or "xor" in r for r in rows), rows


def test_two_rows_on_one_line_both_come_back() -> None:
    """The rows are glued to each other, not only to the pane header.

    The header/row abutment that `DATA_ROW` exists to survive is produced by ncurses
    painting runs of cells; nothing makes that mechanism stop at the boundary between
    two DATA rows. MEASURED on `.search`, which returns one match per line: two
    complete rows parsed to ONE, and `read_memory` then reported "that is a reading of
    somewhere else" about a row present in the very string it had parsed.
    """
    glued = ("F000:0000E000" + " 00" * 16 + "  ................"
             "F000:0000E010" + " 11" * 16 + "  xxxxxxxxxxxxxxxx")
    rows = dcons.parse_data_view(glued)
    assert [r.split()[0] for r in rows] == ["F000:0000E000", "F000:0000E010"], rows


@pytest.mark.parametrize("gutter", range(17))
def test_a_gutter_cannot_swallow_the_address_of_the_row_behind_it(gutter: int) -> None:
    """The case for the lookahead, and it is the one `[^\\r\\n]` cannot cover.

    When a row's ASCII gutter is short or absent and the next row follows on the same
    line, an unguarded `{0,16}` gutter captured the next row's own address, so the scan
    resumed mid-token and that row was lost. The line endings are irrelevant here:
    `splitlines()` has already removed them, and the two rows were never on separate
    lines to begin with.

    EVERY LENGTH FROM 0 TO 16 IS EXERCISED, and that is the whole point of this case
    rather than a flourish. Its first version tested length 0 ONLY, and the fix it was
    written for guarded only the gutter's first character -- so this case passed while
    the defect survived, and lengths 1 to 15 lost the second row exactly as before.
    A parametrised range makes the defect inexpressible instead of merely absent: the
    axis being moved is the gutter's LENGTH, which is what one hand-picked value cannot
    move.
    """
    line = ("F000:0000E000" + " 00" * 16 + "  " + "." * gutter
            + "F000:0000E010" + " 11" * 16 + "  " + "." * 16)
    rows = dcons.parse_data_view(line)
    assert [r.split()[0] for r in rows] == ["F000:0000E000", "F000:0000E010"], (
        f"gutter of {gutter}: {rows}")
    assert "F000:0000E010" not in rows[0], f"the gutter ate the next address: {rows[0]}"


def test_a_gutter_cannot_reach_into_the_row_below() -> None:
    """The ASCII gutter is bounded and excludes the line endings.

    A row whose gutter is SHORT is the case that matters: an unbounded one would run
    past the end of its own line and swallow the head of the next, so two rows would
    come back as one and the second address would vanish from a reply that still
    looked well formed.
    """
    short = ("F000:0000E000" + " 00" * 16 + "  ab\r\n"
             "F000:0000E010" + " 11" * 16 + "  cd\r\n")
    rows = dcons.parse_data_view(short)
    assert len(rows) == 2, rows
    assert "\n" not in rows[0] and "\r" not in rows[0], rows[0]
    assert rows[1].startswith("F000:0000E010")


def test_a_reading_of_somewhere_else_is_refused(tmp_path: Path) -> None:
    """THE CASE WHOSE ABSENCE MADE THE FIX UNGATED, which is the whole point of it.

    `read_memory`'s headline claim is that the address asked for is the assertion, not
    merely that some rows came back. MEASURED during this block's own review:
    replacing that guard with `if False:` left ALL 63 contract tests and ALL 22 live
    tests green. The only negative that existed drove the OTHER guard (an empty
    screen), and the live case asserts `rows[0]` on what a real emulator returned,
    which is true with the guard gone.

    So the exact defect this method was written to fix -- a reply that is `ok` and
    about somewhere else -- was one deleted line away, with nothing anywhere to say
    so. A green that cannot turn red is not a gate.

    THE SCREEN HOLDS A NEIGHBOURING ADDRESS, not junk: a wrong-address reply is
    plausible, well formed and full of real hex, which is what makes it dangerous.
    """
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    elsewhere = "F000:0000E040" + " 00" * 16 + "  ................"
    fake = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=lambda _t, **_k: elsewhere,
        where=lambda: {"cs": "F000", "eip": "0000E000", "mode": "Real"},
        alive=lambda: True)
    with pytest.raises(ds.Invalid, match="none of them is F000:0000E000"):
        ds.Session.read_memory(fake, 0xF000, 0xE000)  # type: ignore[arg-type]

    # THE CONTROL, so the refusal above is about the ADDRESS and not about this path
    # being broken: the same screen, asked about the address it really holds.
    got = ds.Session.read_memory(fake, 0xF000, 0xE040)  # type: ignore[arg-type]
    assert got == [elsewhere]


def test_read_memory_with_a_cached_mode_does_not_survey_for_it(tmp_path: Path) -> None:
    """Decision 35 part 2: a passed `mode` is the offset ceiling's source, so `read_memory`
    must NOT call `where()` for it -- that is the per-watch re-survey the fold removes. Pinned
    by a double whose `where()` RAISES: with `mode` given the rows come back (where was not
    consulted); the control with `mode=None` raises (where WAS consulted). A regression that
    dropped the cache and always surveyed would redden the first half."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    row = "00A7:0016DF20" + " 8D" * 16 + "  ................"

    def where_boom() -> dict[str, str]:
        raise ds.NotStopped("where() must not be called when the mode is cached")
    fake = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=lambda _t, **_k: row, where=where_boom, alive=lambda: True)
    # read_bytes reaches self.read_memory; delegate it to the real method bound to this fake,
    # so the mode threads through the same path a show watch takes.
    fake.read_memory = lambda seg, off, mode=None: ds.Session.read_memory(
        fake, seg, off, mode)  # type: ignore[arg-type]
    # WITH the cached mode: no survey, rows come back.
    got = ds.Session.read_memory(fake, 0x00A7, 0x16DF20, mode="Pr32")  # type: ignore[arg-type]
    assert got == [row]
    # bytes too, through read_bytes -> read_memory, the path a show watch takes.
    b = ds.Session.read_bytes(fake, 0x00A7, 0x16DF20, 4, mode="Pr32")  # type: ignore[arg-type]
    assert b == bytes([0x8D] * 4)
    # CONTROL: with no cached mode, where() is consulted and this double refuses.
    with pytest.raises(ds.Invalid, match="must not be called"):
        ds.Session.read_memory(fake, 0x00A7, 0x16DF20)  # type: ignore[arg-type]


def test_read_memory_takes_a_32_bit_offset_in_protected_mode(tmp_path: Path) -> None:
    """Decision 38: the shipped `read_memory` clamped the offset flat to 0xFFFF, so it
    refused every 32-bit DJGPP address while `run_to` and `watch` took one. Seen RED: at
    0x16DF20 on a Pr32 machine it must be REFUSED before the fix and read after, and in
    real mode the same offset must still be refused (there it addresses nothing).
    """
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    row = "00A7:0016DF20" + " 8D" * 16 + "  ................"

    pr32 = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=lambda _t, **_k: row,
        where=lambda: {"cs": "00A7", "eip": "0016DF20", "mode": "Pr32"},
        alive=lambda: True)
    # In protected mode the 32-bit offset is accepted and the row comes back.
    assert ds.Session.read_memory(pr32, 0x00A7, 0x16DF20) == [row]  # type: ignore[arg-type]

    real = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=lambda _t, **_k: row,
        where=lambda: {"cs": "F000", "eip": "0000FFF0", "mode": "Real"},
        alive=lambda: True)
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        ds.Session.read_memory(real, 0x00A7, 0x16DF20)  # type: ignore[arg-type]


def test_read_memory_hands_back_one_view_when_the_pane_repainted_twice(
        tmp_path: Path) -> None:
    """MEASURED LIVE through the MCP transport on a stopped Pr32 machine: `D 00AF:179784`
    answered with the eight data rows TWICE -- the view is painted once with the
    `Set data overview` acknowledgement and again on the settle -- and `read_memory`
    handed back sixteen rows for an eight-row pane. A caller counting rows, or reading
    "the row after" one, was reading a repaint. The reply is ONE view: each address once,
    at the place it was LAST painted, because the last repaint is the newest reading.
    Seen RED: sixteen rows came back before the fix.
    """
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    seg, off = 0x00AF, 0x179784
    rows = [f"{seg:04X}:{off + 16 * i:08X} " + " ".join([f"{i:02X}"] * 16)
            + "  " + "." * 16 for i in range(8)]
    twice = "DEBUG: Set data overview to 00AF:179784\r\n" + "\r\n".join(rows) \
        + "\r\n" + "\r\n".join(rows) + "\r\nI-> _"
    fake = SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        command=lambda _t, **_k: twice,
        where=lambda: {"cs": "00A7", "eip": "0016DF20", "mode": "Pr32"},
        alive=lambda: True)
    got = ds.Session.read_memory(fake, seg, off)  # type: ignore[arg-type]
    assert got == rows, f"{len(got)} rows for an eight-row pane: {got}"


def test_the_gutter_stops_at_sixteen_characters() -> None:
    """The bound itself, which nothing asserted once the lookahead subsumed it.

    MEASURED: widening `{0,16}` to `{0,64}` left the whole battery green, and a glued
    screen then returned fifty characters of pane decoration INSIDE what a caller reads
    as a memory row. The lookahead stops an ADDRESS; only the bound stops everything
    else, and the gutter of this debugger's data view is sixteen characters because
    that is how many bytes the row holds.
    """
    long_gutter = "F000:0000E000" + " 00" * 16 + "  " + "x" * 40
    rows = dcons.parse_data_view(long_gutter)
    assert len(rows) == 1, rows
    assert rows[0].endswith("x" * 16), rows[0]
    assert "x" * 17 not in rows[0], (
        f"the gutter ran past sixteen characters: {rows[0]!r}")


def test_a_dump_destination_inside_the_debuggers_own_place_is_refused(
        tmp_path: Path) -> None:
    """A `dest` naming a CANDIDATE as a directory component would collect the dump into the
    place the debugger writes, where it cannot be told from a leftover: refused before the
    debugger is asked, and an ordinary destination after it still works."""
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

    # THE THREE SPELLINGS THAT ARE THE SAME FILE TO THE KERNEL AND UNEQUAL TO `==`.
    # The first version of this guard compared path STRINGS, and all three escaped it,
    # each reproducing the poisoning it exists to prevent. The relative one is the
    # worst: it SUCCEEDS, depositing the dump onto the candidate, so it is the NEXT
    # call that is refused.
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

    # THE CONTROLS, and they are what make this about poisoning rather than about
    # refusing. An ordinary destination still works on the same session afterwards --
    # including one whose name merely SHARES A PREFIX with a candidate, which a
    # startswith comparison with no separator would have swallowed. That one sits beside
    # a candidate OUTSIDE the working directory (a captures directory), because a `dest`
    # directly in the working directory is refused on its own account.
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
    """The debugger writes its own dump file into the emulator's working directory, so a
    `dest` there, whatever its name, is a dump collected into the directory it is collected
    FROM: refused before the debugger is asked, compared on the filesystem (a relative
    spelling and a case-folded one are the same directory). A SUBDIRECTORY is a project's
    own `TMP/` and carries no such hazard, so it is allowed."""
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
    """`source.replace(dest)` overwrites in silence: a `dest` the caller already had comes
    back overwritten with guest memory under `status: ok`, however firmly a docstring
    promises such a file is refused. The refusal is real, it names the path, it happens
    before the debugger writes anything (so there is no leftover to poison the next
    dump), and the caller's bytes are untouched.
    """
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
    # A DANGLING SYMLINK AT `dest` IS "THERE" TOO (see the still's test above): the
    # cross-device copy fallback opens through it and writes at the link's target.
    (tmp_path / "elsewhere").mkdir()
    link = tmp_path / "d.bin"
    link.symlink_to(tmp_path / "elsewhere" / "victim.bin")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.memdump(d, 0, 0, 16, link)  # type: ignore[arg-type]
    assert asked == [] and not (tmp_path / "elsewhere" / "victim.bin").exists()
    # THE CONTROL: the same session dumps to a fresh destination on the next call.
    got = ds.Session.memdump(d, 0, 0, 16, tmp_path / "fresh.bin")  # type: ignore[arg-type]
    assert got.read_bytes() == b"\xAB" * 16


def test_a_screen_with_no_data_view_parses_to_nothing() -> None:
    """So `read_memory` can raise INVALID rather than hand back an empty list, which
    reads like an address holding nothing."""
    assert dcons.parse_data_view("DEBUG: Set Register success.\nI-> _") == []
    assert dcons.parse_data_view(REAL_PANE) == []


def test_only_the_names_this_debugger_sets_are_accepted() -> None:
    """`SR` takes MULTIPLE pairs and a carriage return is appended, so an unchecked
    name is a way to run debugger commands the caller never named."""
    assert "ax" in dcons.SETTABLE and "eax" in dcons.SETTABLE
    assert "ax 1\rBPINT 21" not in dcons.SETTABLE
    assert "eex" not in dcons.SETTABLE


# ---------------------------------------------------------------- the capture

AVI = Path(__file__).parent / "fixtures" / "avi"


def fake_avi(frames: int, complete: bool = True) -> bytes:
    """The SHAPE of a capture, as the two real ones under `fixtures/avi` hold it.

    It is not a playable file and does not pretend to be: what `avi_facts` reads is
    the RIFF header, the main header's total (0 while recording, as measured), the `00dc`
    frame chunks, and the `idx1` index, which names every frame again once it is written.
    """
    avih = b"avih" + struct.pack("<I", 56) + struct.pack(
        "<14I", 0, 0, 0, 0, frames if complete else 0, 0, 1, 0, 720, 400, 0, 0, 0, 0)
    body = b"RIFF" + b"\x00" * 4 + b"AVI " + b"LIST" + b"\x00" * 8 + avih + b"00dc" * frames
    return body + (b"idx1" + b"00dc" * frames if complete else b"")


def test_a_finished_capture_counts_its_frames_from_its_header() -> None:
    """The real 12-frame capture: its index names every frame again, so a count of the tag
    would read 26."""
    data = (AVI / "dosbox-x-zmbv-12.avi").read_bytes()
    assert data.count(b"00dc") == 26
    assert ds.avi_facts(data) == {"bytes": len(data), "riff_avi": True, "avi_frames": 12,
                                  "complete": True}


def test_a_capture_still_recording_counts_its_frame_chunks() -> None:
    data = (AVI / "dosbox-x-zmbv-running.avi").read_bytes()
    assert ds.avi_facts(data) == {"bytes": len(data), "riff_avi": True, "avi_frames": 9,
                                  "complete": False}


def test_a_capture_is_judged_by_what_is_in_it_and_not_by_its_size() -> None:
    """A recording that captured nothing and one that captured everything are both
    files of a plausible size."""
    facts = ds.avi_facts(fake_avi(frames=5428))
    assert facts["riff_avi"] is True
    assert facts["avi_frames"] == 5428
    assert facts["complete"] is True


def test_a_capture_still_in_progress_is_marked_incomplete_and_not_corrupt() -> None:
    """The index is written when the recording STOPS, so its absence is a state and
    not damage. A still cannot be extracted from one, which is why the difference has
    to reach the caller."""
    facts = ds.avi_facts(fake_avi(frames=40, complete=False))
    assert facts["complete"] is False and facts["avi_frames"] == 40


def test_something_that_is_not_a_capture_is_not_called_one() -> None:
    """The green's red: `riff_avi` has to be capable of being false."""
    facts = ds.avi_facts(b"this is not a video at all")
    assert facts["riff_avi"] is False
    assert facts["avi_frames"] == 0


def stopped(**over: object) -> Any:
    """A stand-in carrying only what `captures`/`frame` READ, so the refusals can be
    exercised without a process. Same reason `validate` is a pure function: a test
    that has to CONSTRUCT a session is a test that spawns an emulator the moment a
    guard is removed."""
    base: dict[str, object] = {"captures_dir": None, "capture_video": False}
    base.update(over)
    return SimpleNamespace(launch=SimpleNamespace(**base), _avi_facts={})


def test_a_session_that_was_not_recording_is_not_an_empty_capture(tmp_path: Path) -> None:
    """"Nothing was recording" and "the recording is empty" are different answers, and
    only one of them is about the guest.

    THE PHRASE MATCHED HERE IS THE ONE ONLY THIS BRANCH PRINTS. `match="no capture"`
    was the first attempt and it passed with the guard REMOVED, because the fall-
    through then raises "no capture appeared in ..." over an empty directory, which
    contains that substring too. A test that passes for the wrong reason is worse
    than no test, and it was found by deleting that guard and watching this case stay
    green.
    """
    with pytest.raises(ds.Invalid, match="nothing was recording"):
        ds.Session.captures(
            stopped(captures_dir=tmp_path, capture_video=False))


def test_a_recording_session_with_no_file_yet_says_why(tmp_path: Path) -> None:
    """The green's other half: with `capture_video` on, the refusal changes to the one
    about the file, which is what tells a caller to wait rather than to reconfigure."""
    with pytest.raises(ds.Invalid, match="no .avi file in"):
        ds.Session.captures(
            stopped(captures_dir=tmp_path, capture_video=True))


def test_the_captures_come_back_largest_last(tmp_path: Path) -> None:
    """The ORDER axis, and it is load-bearing: a still defaults to the last one, which
    must be the file carrying the program and not the text-mode boot before it."""
    (tmp_path / "a_000.avi").write_bytes(fake_avi(frames=40))
    (tmp_path / "a_001.avi").write_bytes(fake_avi(frames=5428))
    got = ds.Session.captures(
        stopped(captures_dir=tmp_path, capture_video=True))
    assert [c["avi_frames"] for c in got] == [40, 5428]


def test_a_capture_that_has_not_grown_is_not_read_again(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """`captures` is polled while a recording runs, and every poll re-read every file whole
    to count its frames. A file at the same size answers from the facts read last time; a
    file that grew is read again, and its new frame count is what comes back."""
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
    """Two captures is the normal case, and the cache is per FILE: a poll over two files
    that have not grown reads neither again. A file replaced by another of the same size
    is read again: the key carries the modification time beside the size."""
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


def test_a_negative_frame_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ds.Invalid, match="not a frame"):
        ds.Session.frame(
            stopped(captures_dir=tmp_path, capture_video=True), -1, tmp_path / "x.png")


# ------------------------------------------------------- the read's escape boundary

class FakeDrain:
    """The drain's state, as `Session._read` reaches for it, with the fields TYPED.

    It replaced a `SimpleNamespace`, which types as `Any` in every direction: the
    session it stands in for was untyped, so `_take()` returned `Any`, a `bytes`
    contract could be broken here with nothing to say so, and every access needed a
    `type: ignore[attr-defined]` that also hid a genuine typo.
    """

    def __init__(self, chunks: list[str]) -> None:
        self.dropped = 0
        self._pending = ""
        self._screen = ""
        self._raw_tail, self._raw_reads = "", 0
        self._eof = threading.Event()
        self._left = list(chunks)
        self._take: Callable[[], bytes] = self._next_chunk

    def _next_chunk(self) -> bytes:
        return self._left.pop(0).encode() if self._left else b""


class Reader:
    """`Session._read` bound to a `FakeDrain`, callable, carrying its own session.

    IT DRIVES THE REAL METHOD, and that is the point: this whole area had zero tests in
    either tier, so every property below was asserted by nobody. The live tier EXECUTES
    `_read` on every call and asserts nothing about the hold, the strip or the trim,
    which is the weakest kind of
    coverage -- it proves the code does not crash, not that it does the thing it was
    written for.

    IT IS A CLASS AND NOT A FUNCTION WITH AN ATTRIBUTE BOLTED ON. The previous shape
    declared `Callable[[float], str]` while every call site passed no argument, so
    strict mypy read five real "too few arguments" errors -- correct about the
    declaration and wrong about the code -- and the `session` handle needed an
    `attr-defined` ignore on every use. A double whose own type is a lie cannot hold
    the thing it doubles to a contract.
    """

    def __init__(self, chunks: list[str]) -> None:
        self.session = FakeDrain(chunks)

    def __call__(self, seconds: float = 0.0) -> str:
        return ds.Session._read(self.session, seconds)   # type: ignore[arg-type]


def reader(chunks: list[str]) -> Reader:
    return Reader(chunks)


# The same real data row, with ONE SGR change repainted in the middle of it, split
# three ways. The escape is identical in all three; only the chunk boundary moves.
MID_ROW = (
    "F000:0000E000 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49 42  ..............IB")
SPLIT_AT = 20                            # inside the hex, where ncurses changes attrs


@pytest.mark.parametrize("chunks", [
    pytest.param([MID_ROW[:SPLIT_AT] + "\x1b[1;2" + "m" + MID_ROW[SPLIT_AT:]],
                 id="whole-escape-in-one-read"),
    pytest.param([MID_ROW[:SPLIT_AT] + "\x1b[1;2", "m" + MID_ROW[SPLIT_AT:]],
                 id="split-with-text-before-the-escape"),
    pytest.param([MID_ROW[:SPLIT_AT], "\x1b[1;2", "m" + MID_ROW[SPLIT_AT:]],
                 id="split-with-the-escape-as-the-first-byte"),
])
def test_a_repaint_escape_survives_wherever_the_read_boundary_falls(
        chunks: list[str]) -> None:
    """WHERE THE CHUNK BOUNDARY FELL MAY NOT CHANGE WHAT WAS READ.

    MEASURED before the fix, on these three exact cases: 1 row, 1 row, and ZERO. The
    hold was given up when `held.start() == 0` -- precisely when the head was ALL
    there was to hold -- so the fragment was stripped as a lone escape and its final
    byte `m` was then injected into the row's hex, which `DATA_ROW` correctly refuses.
    `read_memory` answers that with INVALID: a FALSE one, from the narrow reader whose
    whole purpose is not lying about what it examined, arriving only when the boundary
    happened to fall there.
    """
    read = reader(chunks)
    text = "".join(read() for _ in chunks)
    assert "\x1b" not in text, f"an escape survived into the reading: {text!r}"
    rows = dcons.parse_data_view(text)
    assert len(rows) == 1, f"the row did not survive the boundary: {text!r}"
    assert rows[0] == MID_ROW, rows


def test_a_head_that_never_terminates_is_given_up_rather_than_held_forever() -> None:
    """THE BOUND IS WHAT LETS THE HOLD BE UNCONDITIONAL, so it is tested, not assumed.

    An OSC with no terminator matches `PARTIAL_TAIL` from the first byte of every
    later read, so an unbounded hold swallows the stream and the reader goes blind
    while reporting nothing wrong. That failure is silent, which is why the give-up
    arm exists and why the old position test is NOT an acceptable substitute for it.
    """
    read = reader(["\x1b]" + "x" * (ds.PENDING_MAX * 2)])
    text = read()
    assert len(text) > ds.PENDING_MAX, "the head was held past its bound"
    assert read.session._pending == "", (
        "the reader is still holding a head it has already emitted")


def test_a_well_formed_head_is_still_held_at_the_bound() -> None:
    """The control for the case above: the give-up arm must not fire on real escapes.

    Without this, `PENDING_MAX = 0` -- which is "never hold anything", i.e. the defect
    restored in a worse form -- passes the give-up test on its own.
    """
    read = reader(["EAX=0000\x1b[1;2", "m rest"])
    first = read()
    assert first == "EAX=0000", f"the head was not held: {first!r}"
    assert read.session._pending == "\x1b[1;2"
    assert read() == " rest"


def test_a_read_the_drain_dropped_bytes_out_of_is_refused() -> None:
    """The overflow refusal, which nothing asserted although the code has it.

    `terminal_bytes_dropped` is reported by `state()` and a contract test pins that
    it is REPORTED; nothing pinned that a read spanning a drop REFUSES. The live tier
    cannot reach it -- `DRAIN_KEEP` is 4 MiB and the live assertion is that the
    counter stays at zero.
    """
    read = reader(["EAX=00001234"])
    read.session._pending = "\x1b[1;2"
    # THE COUNTER HAS TO MOVE DURING THE READ, not merely be non-zero. My first probe
    # set it beforehand and reported that the guard did not fire; the guard was right
    # and the probe was the finding -- a session that overflowed an hour ago and has
    # been read cleanly since is not a session whose next reading has a hole in it.
    read.session._eof.set()
    orig = read.session._take

    def drops() -> bytes:
        read.session.dropped += 7
        return orig()

    read.session._take = drops
    with pytest.raises(ds.Invalid, match="not a reading"):
        read()
    assert read.session._pending == "", (
        "a head from a stream with a hole in it was kept for the next read")


def test_a_name_that_is_not_a_register_never_reaches_the_debugger() -> None:
    """THE GUARD IS EXERCISED, not just its frozenset read back.

    MEASURED: with the `SETTABLE` check deleted, the whole contract battery stayed
    green, because the only test near it asserted the CONTENTS of the frozenset -- a
    tautology about a literal. The live tier passes only valid names, so it was green
    there too. `SR` takes MULTIPLE pairs and this class appends a carriage return, so
    the hazard the docstring names is real: an unchecked name is a way to run commands
    the caller never asked for.
    """
    sent: list[str] = []
    fake = SimpleNamespace(altered=False, command=sent.append)
    for bad in ("eax 0 ; RUN", "cr3", "", "e a x"):
        with pytest.raises(ds.Invalid, match="not a register this debugger sets"):
            ds.Session.set_register(fake, bad, 1)   # type: ignore[arg-type]
    assert sent == [], f"a rejected name still reached the debugger: {sent}"
    assert fake.altered is False, (
        "a name that never reached the machine marked the session altered")


def test_set_register_refuses_a_value_its_register_cannot_hold_before_sending() -> None:
    """`SR` takes a hex word and the debugger keeps what fits, so a value wider than the
    register (or negative, which `:x` spells with a minus) would land as something else:
    refused at the layer that types `SR`, not only at the tool's door."""
    sent: list[str] = []
    fake = SimpleNamespace(altered=False, command=sent.append)
    for name, value in (("ax", 0x10000), ("eax", 1 << 32), ("cs", -1)):
        with pytest.raises(ds.Invalid, match="nothing was sent"):
            ds.Session.set_register(fake, name, value)   # type: ignore[arg-type]
    assert sent == [] and fake.altered is False, sent


def test_set_register_whose_pane_lacks_the_register_is_refused_and_still_altered() -> None:
    """The readback is a repaint; a pane that comes back without the register cannot say
    what landed, so the reply is a refusal that says so, and the session stays altered
    because the `SR` reached the machine."""
    sent: list[str] = []
    fake = SimpleNamespace(altered=False, command=sent.append, registers=lambda: {"EBX": "0"})
    with pytest.raises(ds.Invalid, match="without EAX after `SR`"):
        ds.Session.set_register(fake, "eax", 1)   # type: ignore[arg-type]
    assert sent == ["SR eax 1"], sent
    assert fake.altered is True
    fake.registers = lambda: {"EAX": "00000001"}
    ok = ds.Session.set_register(fake, "eax", 1)   # type: ignore[arg-type]
    assert ok["readback"] == "0x00000001" and ok["verified"] is True
    fake.registers = lambda: {"EAX": "00000002"}
    assert ds.Session.set_register(fake, "eax", 1)["verified"] is False   # type: ignore[arg-type]


def _pane_after_sr(pane: dict[str, str]) -> SimpleNamespace:
    """A session double whose pane, after the `SR`, is `pane`: the register block as the
    debugger paints it, 32-bit general registers and 16-bit segments, no 16-bit general
    name at all."""
    return SimpleNamespace(altered=False, command=lambda _text: "", registers=lambda: pane)


def test_a_segment_register_reads_back_under_its_own_name() -> None:
    """A segment register has no 32-bit form: the pane shows `CS`, and the readback is read
    there."""
    fake = _pane_after_sr({"EAX": "00000000", "CS": "0050", "DS": "0040"})
    got = ds.Session.set_register(fake, "cs", 0x50)   # type: ignore[arg-type]
    assert got["readback"] == "0x0050" and got["verified"] is True, got
    assert fake.altered is True
    # THE CONTROL: the same name against a pane holding another value is not verified.
    assert ds.Session.set_register(fake, "ds", 0x50)["verified"] is False   # type: ignore[arg-type]


def test_a_16_bit_name_is_read_back_as_the_low_half_of_its_register() -> None:
    """`ax` is the low half of `EAX`, and the pane shows only `EAX`: the readback is that half,
    whatever the high half holds."""
    fake = _pane_after_sr({"EAX": "ABCD1234", "EIP": "00010100", "CS": "0050"})
    got = ds.Session.set_register(fake, " AX", 0x1234)   # type: ignore[arg-type]
    assert got["readback"] == "0x1234" and got["verified"] is True, got
    assert got["register"] == "ax", got      # the name as `SR` takes it, not as it was asked
    ip = ds.Session.set_register(fake, "ip", 0x0100)   # type: ignore[arg-type]
    assert ip["readback"] == "0x0100" and ip["verified"] is True, ip
    # THE CONTROL: a low half that differs is not verified, whatever the high half holds.
    assert ds.Session.set_register(fake, "ax", 0x5678)["verified"] is False   # type: ignore[arg-type]
    # AND THE 32-BIT NAME IS UNCHANGED: the whole register, eight digits.
    wide = ds.Session.set_register(fake, "eax", 0xABCD1234)   # type: ignore[arg-type]
    assert wide["readback"] == "0xabcd1234" and wide["verified"] is True, wide


def test_every_settable_name_has_the_pane_register_and_width_it_is_read_back_at() -> None:
    """ONE TABLE says where each name `SR` takes is read back, and it covers `SETTABLE`
    exactly: a name added to one and not the other would reach the machine and then refuse
    its own readback."""
    assert set(ds.READBACK) == set(dcons.SETTABLE)
    for name, (pane, bits) in ds.READBACK.items():
        assert pane in dcons.REGISTER_NAMES, (name, pane)
        assert bits in (16, 32), (name, bits)
    assert ds.READBACK["cs"] == ("CS", 16) and ds.READBACK["es"] == ("ES", 16)
    assert ds.READBACK["ax"] == ("EAX", 16) and ds.READBACK["ip"] == ("EIP", 16)
    assert ds.READBACK["esp"] == ("ESP", 32)


# ------------------------------------------------------------ the symbol file's name

def test_an_ack_naming_a_truncated_filename_is_not_an_ack() -> None:
    """THE SILENT HAZARD IN THIS COMMAND, measured rather than imagined.

    This debugger cuts a `SV`/`LV` filename to twelve characters with no warning
    and reports success for whatever it used:

        SV ABCDEFGHIJKLMNOPQRST.BIN
          -> DEBUG: Variable list save (ABCDEFGHIJKL) : ok.

    and a 144,762-byte file called `ABCDEFGHIJKL`, no extension, appeared in the
    emulator's working directory. So searching the reply for `ok` is searching for a
    TRUE statement about a file the caller never named, and the echoed name is the only
    thing in the reply that can reveal it.

    IT USES THE MODULE'S OWN CONSTANTS, not a literal spelling of them. With the
    literals, lower-casing both constants -- a break that makes EVERY `load_symbols`
    fail against a debugger that uppercases its argument -- left this test green.
    """
    ok = f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"
    ds.Session._acked(ok, ds.SYM_SAVE_ECHO, ds.SYM_SAVE_NAME)

    # BOTH ECHOES, because only one of them was ever exercised here and `LV`'s is the
    # one every load goes through first. Verified against the emulator's own format
    # strings: `DEBUG: Variable list save (%s) : %s.` and `... load (%s) : %s.`
    ok_load = f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
    ds.Session._acked(ok_load, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    with pytest.raises(ds.Invalid, match="did not acknowledge"):
        ds.Session._acked(ok_load, ds.SYM_SAVE_ECHO, ds.SYM_SAVE_NAME)

    # The measured reply for a name it truncated. It contains `ok`, and it is not one.
    truncated = "DEBUG: Variable list save (ABCDEFGHIJKL) : ok.\n"
    with pytest.raises(ds.Invalid, match="truncates a filename"):
        ds.Session._acked(truncated, ds.SYM_SAVE_ECHO, "ABCDEFGHIJKLMNOPQRST.BIN")

    # And an outright failure, which is what an absolute path produces:
    #   SV /private/tmp/... -> Variable list save (/PRIVATE/TMP) : failure.
    failed = "DEBUG: Variable list save (/PRIVATE/TMP) : failure.\n"
    with pytest.raises(ds.Invalid, match="did not acknowledge"):
        ds.Session._acked(failed, ds.SYM_SAVE_ECHO, "/private/tmp/x.bin")


def test_an_ok_from_an_earlier_call_does_not_acknowledge_this_one() -> None:
    """THE SECOND AXIS, and the one the first version of `_acked` was blind to.

    `in` takes ANY occurrence in the delta, and this debugger's Output pane is a
    scrolling log: a repaint carries earlier replies along with it. Loading twice over
    one session is DOCUMENTED usage, because `LV` appends -- so the second call's
    delta holds the first call's `... : ok.` above its own `... : failure.`, and a
    substring search reports success for a load that did not happen.

    `selector` twenty lines away already anchors with `rfind` against exactly this.
    """
    delta = (f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
             f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"
             f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}) : failure.\n")
    with pytest.raises(ds.Invalid, match="OLDER ok"):
        ds.Session._acked(delta, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)


def test_both_filenames_this_module_uses_fit_inside_what_the_debugger_keeps() -> None:
    """A constant checked against the measured limit, so growing one of these names
    past twelve characters is caught here and not by a file appearing under a name
    nobody chose.

    AND THE CASE, which is the debugger's OTHER transformation of the argument and was
    untested: it UPPERCASES what it echoes (`/private/tmp/...` came back
    `(/PRIVATE/TMP)`), so a constant spelled in lower case would make every
    acknowledgement fail to match its own request.
    """
    assert ds.SYM_ARG_MAX == 12
    for name in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME):
        assert len(name) <= ds.SYM_ARG_MAX, name
        assert name == name.upper(), (
            f"{name!r} is not upper case, and the debugger uppercases the filename it "
            f"echoes back, so `_acked` would never match its own request")


# ------------------------------------------------- the symbol file, on the real path

def _loader(tmp_path: Path, reply: Callable[[str], str] | None = None) -> Any:
    """A stand-in with exactly what `load_symbols` reaches for.

    The REAL method is driven against it (`ds.Session.load_symbols(fake, data)`) rather
    than reimplemented, which is this file's existing idiom: what is worth exercising
    is the ordering, the refusals and the cleanup, and a double that reimplemented them
    would be agreeing with itself.
    """
    def default(text: str) -> str:
        if text.startswith("LV"):
            return f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
        # `SV` also WRITES the file, which is what the real debugger does and what the
        # `back.exists()` check exists to catch when it does not.
        (tmp_path / ds.SYM_SAVE_NAME).write_bytes(GOOD_LIST)
        return f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"

    # `_survey` answers the precondition: is the console listening at all. A stopped
    # machine is the ORDINARY case, so the double is stopped and the refusals below
    # supply their own running one -- otherwise every case here would be exercising
    # the guard instead of the path it is named for.
    #
    # THE MAPPING IS `parse_registers`' OWN ANSWER TO THAT TEXT, not a hand-written
    # one. A hand-written `{"CS": "0"}` beside a text reading `CS=0000` is something no
    # real `_survey` can produce -- harmless while `load_symbols` discards the return, and
    # a trap for the first caller that reads it. A double is captured from what the
    # real thing does, never authored from what it is believed to do.
    #
    # AND A LIMIT, said out loud: the real `_survey` SENDS `BPLIST` through `command`.
    # This one does not, so `sent == []` in the refusal cases below is a statement
    # about `LV` and `SV` only. Making it faithful is not a one-line change either:
    # `default` above routes anything not starting with `LV` into the `SV` arm, which
    # WRITES the save file, so a nudge going through `command` would create `back`
    # before `LV` ever ran and make the `back.exists()` check pass trivially.
    pane = "CS=0000  EIP=00000100  Real"
    return SimpleNamespace(launch=SimpleNamespace(cwd=tmp_path),
                           command=reply or default,
                           _survey=lambda: (pane, dcons.parse_registers(pane)),
                           alive=lambda: True, vars_held=0,
                           _acked=ds.Session._acked)


GOOD_LIST = (b"\x01\x00" + b"_x" + b"\0" * 14 + b"\x10\x00\x00\x00")

# THE PHRASE ONLY THE GUARD PRINTS, and it has to be checked rather than assumed.
# `takes no commands` was the first probe and it is NOT unique: the same commit put
# that wording into `_acked`'s refusal, so the probe answered to the very branch it
# was meant to be telling the guard apart from. This file already carries that lesson
# for another reader ("THE PHRASE MATCHED HERE IS THE ONE ONLY THIS BRANCH PRINTS"),
# and `test_the_guard_mark_names_no_other_refusal` below holds it by machine.
GUARD_MARK = "No file was written"


def _running() -> tuple[str, dict[str, str]]:
    """What `_survey` does when the console is not listening: no pane, so no reading."""
    raise ds.NotStopped("no register pane came back from `BPLIST` (emulator running). "
                        "A register read is only a reading when the machine is "
                        "stopped at the debugger")


def test_a_symbol_file_round_trips_and_leaves_nothing_behind(tmp_path: Path) -> None:
    """The control for every refusal below: the ordinary path works and cleans up.

    Without it, a helper that refused everything would satisfy all four of them.
    """
    got = ds.Session.load_symbols(_loader(tmp_path), GOOD_LIST)
    assert got == [("_x", 0x10)]
    for name in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME):
        assert not (tmp_path / name).exists(), f"{name} was left behind"


def test_a_load_past_what_the_debuggers_save_can_hold_is_refused_before_lv(
        tmp_path: Path) -> None:
    """`LV` appends and nothing clears the debugger's list, and its `SV` refuses a list past
    65535 names: a load that would carry the holding past that is refused BEFORE `LV`, which
    would otherwise append and then fail its own read-back as an unacknowledged save."""
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
    """`LV` acknowledged has appended its names whatever the read-back does next, so the holding
    the ceiling is judged against grows by them even when `SV` then fails."""
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


def test_a_running_machine_is_refused_before_a_byte_is_written(tmp_path: Path) -> None:
    """`LV` GOES THROUGH THE CONSOLE, and a running machine's console takes no commands.

    `step`, `run_to` and `watch` all settle this first. Without the same guard here the
    command goes out, is swallowed without a word, and comes back as `_acked` reporting
    a missing acknowledgement. (It is NOT "the one caller that does not ask": five more
    do not either, and the guard's comment names them.)

    AND THAT IS WHY THE REFUSAL BELONGS HERE rather than being explained better
    downstream: the `_acked` reply names a truncated filename, an older `ok` and a gone
    emulator while the SAME reply's data excludes all three. The caller is sent to check
    filenames while the answer is "stop the machine".

    TWO AXES, and the second was added because the first version was BLIND to place.
    That version asserted nothing was SENT and that no file was LEFT in the working
    directory -- and the second of those is unobservable, because `load_symbols`
    unlinks both files in a `finally` however it leaves. MEASURED: with the guard moved
    down to the line before the `LV`, so that the symbol file IS written into somebody's
    project first, all 85 tests stayed green while the refusal's own sentence ("Nothing
    was written") had become false.

    So the second case asks the question the cleanup cannot erase: with a working
    directory that CANNOT be written, a guard that comes first still refuses about the
    console, and one that comes after refuses about the file. The order is the property,
    not the presence.

    AND THAT SECOND CASE HAS TWO HOLES OF ITS OWN, both closed here. It rests on the
    write FAILING, so under `euid` 0 or on a filesystem that ignores mode bits it
    passes while testing nothing -- it now asserts its own precondition and skips
    rather than reporting a pass it did not earn. And a probe reading `takes no commands`
    is a phrase `_acked` can produce as well, so the break it exists for would satisfy it
    through the wrong branch; the probe is `GUARD_MARK`, whose uniqueness is held by a
    test of its own.

    THE OTHER DIRECTION OF THE ORDER IS A SEPARATE CASE, because it needs a state none
    of these reach: see `test_a_file_already_there_is_named_before_the_machine_is_read`.
    """
    sent: list[str] = []

    def never(text: str) -> str:
        sent.append(text)
        return ""

    fake = _loader(tmp_path, never)
    fake._survey = _running
    with pytest.raises(ds.Invalid, match=GUARD_MARK):
        ds.Session.load_symbols(fake, GOOD_LIST)
    assert sent == [], f"it sent {sent} into a console that takes none"

    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        # THE CASE'S OWN PRECONDITION, ASSERTED. Under `euid` 0, or on a filesystem
        # that ignores mode bits (a container overlay, FAT), the write SUCCEEDS and
        # every assertion below then passes while testing nothing -- the guard could
        # be sitting after `write_bytes` and this would still be green. So the
        # instrument declares itself INVALID rather than reporting a pass it did not
        # earn. That is the neighbour at `test_an_unwritable_working_directory_...`
        # failing loudly under root; without this, a case degrades in silence.
        try:
            (ro / "probe").write_bytes(b"")
        except OSError:
            pass
        else:
            (ro / "probe").unlink()
            pytest.skip("this filesystem/user ignores 0o555, so the case cannot bite")
        readonly = _loader(ro, never)
        readonly._survey = _running
        with pytest.raises(ds.Invalid) as caught:
            ds.Session.load_symbols(readonly, GOOD_LIST)
        assert "could not write" not in str(caught.value), (
            "it tried to write the symbol file BEFORE asking whether the machine "
            "could take the command at all")
        assert GUARD_MARK in str(caught.value)
    finally:
        ro.chmod(0o755)


def test_a_file_already_there_is_named_before_the_machine_is_read(
        tmp_path: Path) -> None:
    """THE OTHER DIRECTION OF THE SAME ORDER, and it was not gated at all.

    The guard's own comment justifies sitting AFTER the two checks that need nothing
    from the machine: reading the machine costs a settle, and a caller whose working
    directory already holds `SYMS.BIN` should hear about that rather than wait for a
    repaint first. Nothing held it. MEASURED: hoisting the guard above both checks
    left all 341 tests green, and the break is not a no-op -- with a running
    machine AND the file present, the refusal flips from naming the file to naming
    the machine, so the caller is told to go and stop a guest when what is in the way
    is a leftover in their own project.

    The reason no case reached it is that it needs BOTH conditions at once, and every
    other case here supplies a stopped `_survey`.
    """
    (tmp_path / ds.SYM_LOAD_NAME).write_bytes(b"somebody else's file")
    fake = _loader(tmp_path)
    fake._survey = _running
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.load_symbols(fake, GOOD_LIST)


def test_a_gone_emulator_is_not_told_to_arm_a_breakpoint(tmp_path: Path) -> None:
    """`NotStopped` HAS MORE THAN ONE CAUSE, and the refusal may not pick one.

    `_survey`'s own comment says so: an empty parse can be a running machine, a pane
    that did not repaint, or an emulator that died, and this module's thesis is that
    an INVALID says what it EXAMINED rather than choosing a diagnosis. The first
    version of this guard opened with "the machine is not stopped at the debugger"
    and closed with "Stop it first -- a breakpoint is how" whatever the cause -- so a
    caller whose emulator was GONE was told to stop a machine that does not exist and
    to arm a breakpoint in a debugger that is not there.

    `alive()` is the question that separates them, one line away, and `selector`,
    `read_memory` and `_survey` itself all already ask it.
    """
    fake = _loader(tmp_path)
    fake._survey = _running
    fake.alive = lambda: False
    with pytest.raises(ds.Invalid) as caught:
        ds.Session.load_symbols(fake, GOOD_LIST)
    said = str(caught.value)
    assert "GONE" in said, said
    assert "breakpoint" not in said, (
        "it prescribed a breakpoint to a caller with no emulator to arm one in")
    assert "No file was written" in said


def test_the_console_guard_catches_only_the_cause_it_names(tmp_path: Path) -> None:
    """THE EXCEPTION IDENTITY, which was ungated: `except Invalid` here was green.

    `NotStopped` is a subclass of `Invalid` and exists as a separate type for exactly
    this, its docstring recording a MEASURED case where catching the base class turned
    one refusal into a confident diagnosis of a cause nobody had observed. `_survey`
    reaches `command`, which has truthful refusals of its own (a hole in the terminal
    stream, say). Those must come through as themselves.
    """
    sent: list[str] = []

    def other() -> tuple[str, dict[str, str]]:
        raise ds.Invalid("unexpected_answer",
            "bytes were dropped, so this is not a reading of anything")

    def never(text: str) -> str:
        sent.append(text)
        return ""

    fake = _loader(tmp_path, never)
    fake._survey = other
    with pytest.raises(ds.Invalid) as caught:
        ds.Session.load_symbols(fake, GOOD_LIST)
    said = str(caught.value)
    assert "bytes were dropped" in said, said
    assert GUARD_MARK not in said, (
        "a refusal about the terminal was reported as a refusal about the console")
    assert sent == [], "it went on to send `LV` after a refusal it did not understand"


def test_the_guard_mark_names_no_other_refusal(tmp_path: Path) -> None:
    """A PROBE THAT MATCHES A SIBLING BRANCH IS NOT A PROBE, and this one nearly was.

    `takes no commands` was the first choice, and the SAME commit put that wording
    into `_acked`'s refusal -- so the break the case exists for (the guard moved
    below the write, on a filesystem where the write succeeds) would have satisfied it
    through `_acked`, green, testing nothing. Checking it once by hand is what this
    replaces: the other refusals are DRIVEN here and asked whether they answer to it.

    It exercises the branches rather than grepping the source, because what matters is
    what a caller RECEIVES, and because a text search for the mark would find this
    file's own definition of it.
    """
    with pytest.raises(ds.Invalid) as acked:
        ds.Session._acked("nothing like an ok", ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    assert GUARD_MARK not in str(acked.value)

    (tmp_path / ds.SYM_LOAD_NAME).write_bytes(b"")
    with pytest.raises(ds.Invalid) as exists:
        ds.Session.load_symbols(_loader(tmp_path), GOOD_LIST)
    assert GUARD_MARK not in str(exists.value)


def test_the_acknowledgement_refusal_keeps_the_tail_and_not_the_head() -> None:
    """WHAT SURVIVES THE 300-CHARACTER BOUND IS THE NEWEST EVIDENCE, not the oldest.

    `_acked` now tells the reader that the showing is what discriminates, so WHICH
    300 characters it keeps stops being cosmetic. Nothing pinned it: `[-300:]` ->
    `[:300]` was green, because the only fixture was shorter than the bound. This
    file already carries the same case for another reader
    (`test_the_limit_keeps_the_tail_and_not_the_head`), written because a head slice
    "answers every question with the boot".
    """
    out = "HEADMARK " + "x" * 400 + " TAILMARK"
    with pytest.raises(ds.Invalid) as caught:
        ds.Session._acked(out, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    said = str(caught.value)
    assert "TAILMARK" in said, said
    assert "HEADMARK" not in said, "it quoted the head, so the newest evidence is gone"


def test_a_missing_acknowledgement_names_every_cause_that_has_been_seen() -> None:
    """The refusal enumerates, so what it LEAVES OUT reads as excluded.

    It named three things and the reply that produced this test excluded all three by
    its own data, which leaves a caller with nothing. The one it did not name is the
    one that had happened: a machine that is RUNNING, whose console swallows the
    command. The guard above stops that reaching here, and this stays because `_acked`
    also covers `SV`, and because a list presented as closed is the defect rather than
    the missing entry.

    THE DELTA IS THE ONE THAT WAS MEASURED, verbatim: a running guest leaves its own
    E9 instrumentation on the screen and no acknowledgement anywhere. Which is the
    evidence the message now tells the reader how to read.
    """
    running = ("\x1b7\x1b8\r\nBochs port E9h: [+ 00000.000] PROBE . tick"
               "\x1b7\x1b8\r\nBochs port E9h: [+ 00001.000] PROBE . tick")
    with pytest.raises(ds.Invalid) as caught:
        ds.Session._acked(running, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
    said = str(caught.value)
    for clause in ("truncates a filename", "OLDER ok", "EMPTY", "RUNNING",
                   "not a closed list"):
        assert clause in said, f"the refusal no longer says {clause!r}: {said}"
    # And it still SHOWS what it saw, which is the half the reader discriminates on.
    assert "PROBE . tick" in said


def test_a_dangling_symlink_at_either_name_is_refused(tmp_path: Path) -> None:
    """`exists()` FOLLOWS symlinks, so a dangling one reads False and passes a guard
    written with it. `write_bytes` then creates the file at the link's TARGET --
    outside the working directory entirely -- and the cleanup unlinks only the link.

    This is the family `_same_place` was extracted for, one method away.
    """
    victim = tmp_path / "elsewhere" / "victim.bin"
    victim.parent.mkdir()
    (tmp_path / ds.SYM_LOAD_NAME).symlink_to(victim)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.load_symbols(_loader(tmp_path), GOOD_LIST)
    assert not victim.exists(), "it wrote through the link, outside the directory"


def test_an_unwritable_working_directory_is_a_refusal_and_not_a_traceback(
        tmp_path: Path) -> None:
    """`tool()` translates only `Invalid`, so a raw `PermissionError` reaches the
    caller as a traceback with no session block -- the reply this package's own
    docstring calls the worst one to hand over: the symbol file's write is translated."""
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
    """`BadSymbolText` is NOT an `Invalid`. Its own docstring says it is a distinct type
    "so the MCP layer can translate it" -- and the server translates it around
    `parse`/`plan`/`encode`, not around this call, which is the ONE place a malformed
    file can arrive from the emulator rather than from the caller."""
    def bad(text: str) -> str:
        if text.startswith("LV"):
            return f"DEBUG: {ds.SYM_LOAD_ECHO} ({ds.SYM_LOAD_NAME}{ds.SYM_OK}\n"
        # A header claiming two records over a file holding none.
        (tmp_path / ds.SYM_SAVE_NAME).write_bytes(b"\x02\x00" + b"\0" * 10)
        return f"DEBUG: {ds.SYM_SAVE_ECHO} ({ds.SYM_SAVE_NAME}{ds.SYM_OK}\n"

    with pytest.raises(ds.Invalid, match="cannot be read back"):
        ds.Session.load_symbols(_loader(tmp_path, bad), GOOD_LIST)


def test_the_descriptor_read_does_not_stitch_two_descriptors_together(
        tmp_path: Path) -> None:
    """The base from one descriptor and the limit from ANOTHER is a wrong answer of
    exactly the right shape -- and the limit is the independent fact a caller checks
    the base against, so a borrowed one hands their own assumption back as evidence.

    The screen here is the one that produces it: the answer's own `l:` never arrived
    (the pane scrolled, or the settle expired between its two lines) and a neighbouring
    descriptor's follows.

    IT TOOK TWO FIXES AND THE FIRST WAS NOT ENOUGH, which is why the case is written
    this way. Bounding the gap between `type:` and `l:` stops the two being STITCHED --
    but the pattern then simply slid forward and matched the next descriptor WHOLE:
    asked about CS, it answered `b:00008240 type:12 l:0000FFFF`, three fields all
    belonging to DS and all consistent with each other. So the read is anchored with
    `match` on a line beginning with the register's own name, which cannot slide.
    """
    screen = ("SelectorInfo CS:\r\n"
              "CS: b:00400000 type:1B parbg\r\n"
              + "x" * 400 + "\r\n"
              "DS: b:00008240 type:12 parbg\nl:0000FFFF dpl : 3 10010\r\n")
    fake = SimpleNamespace(command=lambda text: screen, alive=lambda: True)
    with pytest.raises(ds.Invalid, match="line of its own"):
        ds.Session.selector(fake, "CS")   # type: ignore[arg-type]

    # THE CONTROL: the same shape with this descriptor's own limit present reads fine,
    # so the refusal is about the missing field and not about the neighbour existing.
    whole = ("SelectorInfo CS:\r\n"
             "CS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 10011\r\n"
             "DS: b:00008240 type:12 parbg\nl:0000FFFF dpl : 3 10010\r\n")
    ok = SimpleNamespace(command=lambda text: whole, alive=lambda: True)
    got = ds.Session.selector(ok, "CS")    # type: ignore[arg-type]
    assert got == {"base": 0x00400000, "limit": 0x0023FFFF, "type": 0x1B, "big": 1}


def test_the_descriptor_read_takes_the_big_bit_from_the_fourth_digit() -> None:
    """`SELINFO`'s five digits under `parbg` are present, available, reserved, big and
    granularity, and big is the width a code segment decodes in. The captured CS line
    (`10011`) with its fourth digit changed to 0 reads 16-bit, and one with the digits gone is
    refused rather than read as either width."""
    line = "SelectorInfo CS:\r\nCS: b:00400000 type:1B parbg\nl:0023FFFF dpl : 3 {}\r\n"
    narrow = SimpleNamespace(command=lambda text: line.format("10001"), alive=lambda: True)
    assert ds.Session.selector(narrow, "CS")["big"] == 0    # type: ignore[arg-type]
    wide = SimpleNamespace(command=lambda text: line.format("10011"), alive=lambda: True)
    assert ds.Session.selector(wide, "CS")["big"] == 1    # type: ignore[arg-type]
    bare = SimpleNamespace(command=lambda text: line.format(""), alive=lambda: True)
    with pytest.raises(ds.Invalid, match="line of its own"):
        ds.Session.selector(bare, "CS")   # type: ignore[arg-type]


def test_the_descriptor_read_takes_the_answer_to_this_question(tmp_path: Path) -> None:
    """The OCCURRENCE axis, the sibling of `_acked`'s.

    Anchoring on a line that begins with the register's name stops the read sliding to
    a NEIGHBOURING descriptor. It does not, on its own, stop it reading an OLDER answer
    to the SAME question -- and this pane is a scrolling log, so asking twice leaves
    both answers on screen. The echo is searched with `rfind` and the descriptor line
    from there, so the answer is the one to the question just asked.
    """
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
    return SimpleNamespace(
        launch=dlaunch.Launch(conf=conf, cwd=tmp_path, seconds=60),
        where=lambda: {"cs": "00A7", "eip": "0", "mode": mode},
        command=lambda _t, **_k: "",
        breakpoints=lambda: list(held or []),
        alive=lambda: True, altered=False)


def test_arm_code_breakpoint_reads_the_list_back_and_refuses_a_wrong_mode(
        tmp_path: Path) -> None:
    """It stages a breakpoint WITHOUT releasing the machine, and the list read back is the
    proof -- not the acknowledgement, which scrolls. A 32-bit offset in real mode addresses
    nothing and is refused; an arm the debugger did not list is refused, not called done."""
    ok = _bp_fake(tmp_path, held=[{"index": "00", "entry": "BP 00A7:16DD80"}])
    got = ds.Session.arm_code_breakpoint(ok, 0x00A7, 0x16DD80)  # type: ignore[arg-type]
    assert got["entry"] == "BP 00A7:16DD80" and ok.altered is True

    real = _bp_fake(tmp_path, mode="Real")
    with pytest.raises(ds.Invalid, match="past 0xFFFF addresses nothing"):
        ds.Session.arm_code_breakpoint(real, 0x00A7, 0x16DD80)  # type: ignore[arg-type]

    unlisted = _bp_fake(tmp_path, held=[])          # debugger did not take it
    with pytest.raises(ds.Invalid, match="does not list a breakpoint"):
        ds.Session.arm_code_breakpoint(unlisted, 0x00A7, 0x100)  # type: ignore[arg-type]

    with pytest.raises(ds.Invalid, match="segment is 0x0000"):
        ds.Session.arm_code_breakpoint(ok, 0x1_0000, 0)  # type: ignore[arg-type]


def test_clear_code_breakpoint_reads_removal_back_and_is_honest_when_absent(
        tmp_path: Path) -> None:
    """`removed` is the machine's answer read AFTER the delete, and `BPDEL` renumbers so the
    index is looked up fresh. A breakpoint that was never there is `removed: False`, not an
    error."""
    present = _bp_fake(tmp_path, held=[{"index": "03", "entry": "BP 00A7:16DD80"}])
    # after BPDEL the list no longer holds it: swap the fake's answer post-command.
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
    """MEASURED: BPLIST numbers code breakpoints before interrupts whatever the arming
    order, so `BPDEL 0` on a list `00. BP 00A7:16DD80 / 01. BP 00A7:3D5E0 / 02. BPINT 31
    AH=00` deleted the `_main` breakpoint when the interrupt was meant. This finds the
    interrupt's row by its whole text, sends the index it holds NOW, and answers with the
    list read back. An AH is part of the identity, and an absent row is `removed: False`."""
    held = [{"index": "00", "entry": "BP 00A7:16DD80"},
            {"index": "01", "entry": "BP 00A7:3D5E0"},
            {"index": "02", "entry": "BPINT 31 AH=00"}]
    fake = _bp_fake(tmp_path, held=held)
    sent: list[str] = []
    fake.command = lambda text, **_k: sent.append(text)   # RECORD what goes to the console
    calls = {"n": 0}

    def bps() -> list[dict[str, str]]:
        calls["n"] += 1
        return held if calls["n"] == 1 else held[:2]
    fake.breakpoints = bps
    got = ds.Session.clear_interrupt_breakpoint(fake, 0x31, 0x00)  # type: ignore[arg-type]
    assert got["removed"] is True and got["entry"] == "BPINT 31 AH=00"
    assert sent == ["BPDEL 02"], sent                  # the interrupt's index, not 0

    other_ah = _bp_fake(tmp_path, held=held)
    other_sent: list[str] = []
    other_ah.command = lambda text, **_k: other_sent.append(text)
    gone = ds.Session.clear_interrupt_breakpoint(other_ah, 0x31, 0x05)  # type: ignore[arg-type]
    assert gone["removed"] is False and "no such breakpoint" in str(gone["note"])
    assert other_sent == [], other_sent
    assert dcons.interrupt_row(0x21, None) == "BPINT 21"
    assert dcons.interrupt_row(0x31, 0) == "BPINT 31 AH=00"


def test_clear_interrupt_breakpoint_removed_is_read_back_not_assumed(
        tmp_path: Path) -> None:
    """`removed` is what the list says AFTER the BPDEL, never that the delete was sent. If
    the row is STILL there on the read-back, `removed` is False. Seen against a debugger
    that ignores the delete (the row persists), which a hardcoded `removed = True` would
    hide. The watch and code cases next door hold the same line for their own lists."""
    held = [{"index": "00", "entry": "BPINT 21"}]
    fake = _bp_fake(tmp_path, held=held)
    sent: list[str] = []
    fake.command = lambda text, **_k: sent.append(text)
    fake.breakpoints = lambda: [dict(r) for r in held]     # the delete does not take
    got = ds.Session.clear_interrupt_breakpoint(fake, 0x21)  # type: ignore[arg-type]
    assert sent == ["BPDEL 00"], sent
    assert got["removed"] is False, got
    # AND THE RANGE REFUSALS, before the console is touched.
    for bad in (0x100, -1):
        with pytest.raises(ds.Invalid, match="interrupt number"):
            ds.Session.clear_interrupt_breakpoint(fake, bad)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="AH"):
        ds.Session.clear_interrupt_breakpoint(fake, 0x21, 0x100)  # type: ignore[arg-type]


def test_interrupt_row_round_trips_through_parse_and_parse_refuses_junk() -> None:
    """`interrupt_row` and `parse_interrupt_row` are exact inverses over every value the
    debugger prints (0..0xFF, both with and without AH), and `parse` refuses anything that
    is not one of those spellings -- so a ref that reached the store validated cannot become
    a malformed BPDEL, and the `INT 21` spelling the docs once used is rejected."""
    for n in (0, 0x21, 0xFF):
        for ah in (None, 0, 0x4C, 0xFF):
            assert dcons.parse_interrupt_row(dcons.interrupt_row(n, ah)) == (n, ah)
    for junk in ("INT 21", "BPINT 211", "BPINT 21 AH=", "BP 00A7:0100", "BPINT ZZ", ""):
        with pytest.raises(ds.Invalid, match="interrupt breakpoint row"):
            dcons.parse_interrupt_row(junk)


def test_bp_row_target_reads_seg_off_by_value_across_widths_and_kinds() -> None:
    """A row is recognised by the NUMBERS it carries, whatever width the debugger printed
    them at, and its kind is kept so a code breakpoint is told from a watch at one address.
    A row with no seg:off (an interrupt) is None. The widths and the BPINT shapes here are
    CAPTURED from the debugger elsewhere in this suite, not invented."""
    assert dcons.bp_row_target("BP 0087:12345") == ("BP", 0x87, 0x12345)
    assert dcons.bp_row_target("BP 00A7:0100") == ("BP", 0xA7, 0x100)
    assert dcons.bp_row_target("BP 00A7:100") == ("BP", 0xA7, 0x100)      # minimal width
    assert dcons.bp_row_target("BPMEM 0040:006C (00)") == ("BPMEM", 0x40, 0x6C)
    assert dcons.bp_row_target("BPPM 00AF:00006024 (00)") == ("BPPM", 0xAF, 0x6024)
    assert dcons.bp_row_target("BPPM 00AF:6024") == ("BPPM", 0xAF, 0x6024)  # same, narrow
    assert dcons.bp_row_target("BPINT 21") is None
    assert dcons.bp_row_target("BPINT 31 AH=00") is None


def test_arm_and_clear_recognise_a_breakpoint_by_value_not_by_printed_width(
        tmp_path: Path) -> None:
    """THE SHIPPED-BUG CLASS: the debugger can list a small offset minimal-width
    (`BP 00A7:100`) while the code built `BP 00A7:0100`. An exact-string read-back reported
    the breakpoint 'not armed' though it WAS set, and a clear then found nothing to remove.
    Matching by the parsed numbers survives it; the reply carries the debugger's own row."""
    listed = [{"index": "00", "entry": "BP 00A7:100"}]     # the debugger's minimal width
    ok = _bp_fake(tmp_path, held=listed)
    got = ds.Session.arm_code_breakpoint(ok, 0x00A7, 0x100)  # type: ignore[arg-type]
    assert got["entry"] == "BP 00A7:100"                    # read back, not reconstructed

    calls = {"n": 0}

    def bps() -> list[dict[str, str]]:
        calls["n"] += 1
        return listed if calls["n"] == 1 else []
    ok.breakpoints = bps
    gone = ds.Session.clear_code_breakpoint(ok, 0x00A7, 0x100)  # type: ignore[arg-type]
    assert gone["removed"] is True and gone["entry"] == "BP 00A7:100"


def test_read_bytes_returns_the_exact_n_bytes_at_the_address() -> None:
    """A watch needs the bytes themselves, not the screen. The rows arrive in paint order,
    so the bytes are keyed by absolute offset and read out in order; a length past the 128
    the data view paints is a region and is refused, pointing at memdump."""
    rows = [
        "0749:00000000 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F",
        "0749:00000010 10 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 1E 1F",
    ]
    fake = SimpleNamespace(read_memory=lambda _s, _o, mode=None: list(rows))
    assert ds.Session.read_bytes(fake, 0x749, 0, 4) == bytes([0, 1, 2, 3])  # type: ignore[arg-type]
    assert ds.Session.read_bytes(fake, 0x749, 0, 1) == bytes([0])  # type: ignore[arg-type]
    # a value straddling the row boundary is still contiguous by offset
    assert ds.Session.read_bytes(fake, 0x749, 0x0E, 4) == bytes([0x0E, 0x0F, 0x10, 0x11])  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="region"):
        ds.Session.read_bytes(fake, 0x749, 0, 200)  # type: ignore[arg-type]
    with pytest.raises(ds.Invalid, match="positive length"):
        ds.Session.read_bytes(fake, 0x749, 0, 0)  # type: ignore[arg-type]


def test_a_survey_that_saw_no_pane_names_a_dead_reader_before_blaming_the_machine() -> None:
    """The refusal read "emulator running" off `alive()` alone: a drain thread killed by a
    transient error makes every later read return nothing while the process is up, so a
    machine parked at the debugger was reported as running, the broken instrument as a
    quiet machine. When the reader is dead the refusal says so, with why it ended."""
    import threading
    from types import SimpleNamespace

    s = ds.Session.__new__(ds.Session)
    s.command = lambda text, **k: ""  # type: ignore[method-assign]
    s.proc = SimpleNamespace(poll=lambda: None)  # type: ignore[assignment]
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    s._drainer = dead
    s.drain_ended = "select failed: EBADF"
    with pytest.raises(ds.NotStopped, match="reader has DIED.*EBADF"):
        s._survey()
    # THE CONTROL: with the reader alive the refusal names the machine, as before.
    hold = threading.Event()
    live = threading.Thread(target=hold.wait, daemon=True)
    live.start()
    s._drainer = live
    s.drain_ended = ""
    try:
        with pytest.raises(ds.NotStopped, match="emulator running"):
            s._survey()
    finally:
        hold.set()


def test_close_records_which_ending_it_got() -> None:
    """Three endings, told apart on the object the server reads after the close: a process
    already gone is `died`; one that leaves on the first signal is `quit`; one that has to
    be SIGKILLed is `killed`."""
    import subprocess
    import threading
    from types import SimpleNamespace

    def bare(poll_answers: list[int | None], wait_raises: int) -> ds.Session:
        s = ds.Session.__new__(ds.Session)
        s._closing, s._closed = threading.Lock(), False   # what `__init__` gives a close
        polls: list[int | None] = list(poll_answers)
        # `wait_raises` counts STRETCHES that expire, not calls: `close` waits in slices
        # so it can paint its progress, so the double raises for that many stretches of
        # `TERM_GRACE` and then answers.
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
        s._stop = threading.Event()
        s._master = -1
        s.drain_ended = ""
        s.reap_failed = ""
        s.ended_how = "none"
        return s

    s = bare([0], 0)
    s.close()
    assert s.ended_how == "died"
    s = bare([None, 0], 0)
    s.close()
    assert s.ended_how == "quit"
    s = bare([None, 0], 1)
    s.close()
    assert s.ended_how == "killed" and s.reap_failed == ""

    # CANCELLED HALF-WAY, the close still ends: the cleanup a cancel asked for is this one.
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
        s._master = 99
        with pytest.raises(asyncio.CancelledError):
            s.close()
    assert raised == [True] and s.ended_how == "quit" and closed == [99], (s.ended_how, closed)


def _writer(memory: dict[str, bytes], mode: str = "Real",
            asked: list[tuple[Any, ...]] | None = None) -> tuple[ds.Session, list[str]]:
    """A session stopped in `mode` whose console records what `write_memory` sends and whose
    data view answers `memory["held"]` (a dict, so a test can move it between writes), noting
    each read in `asked` when given: the readback, not the acknowledgement, is what the tests
    judge."""
    sent: list[str] = []
    s = ds.Session.__new__(ds.Session)
    s.altered = False

    def command(text: str, settle: float = 0.6, timeout: float = 6.0) -> str:
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
    """`SM seg:off v1 v2 ...` takes a list of values on one input line; the bytes go out
    in short lines so no build reads a long one short, the offsets advance with them, and
    the whole range is read back once. The readback, not the acknowledgement, is the
    answer: a write the debugger takes into ROM changes nothing."""
    memory = {"held": bytes(range(20))}
    s, sent = _writer(memory)
    out = ds.Session.write_memory(s, 0x40, 0x100, bytes(range(20)))
    assert sent == ["SM 0040:0100 000 001 002 003 004 005 006 007",
                    "SM 0040:0108 008 009 00A 00B 00C 00D 00E 00F",
                    "SM 0040:0110 010 011 012 013"], sent
    assert out == {"bytes_written": 20, "readback": bytes(range(20)).hex(), "verified": True}
    assert s.altered is True
    memory["held"] = bytes(20)                       # ROM: the bytes did not change
    out = ds.Session.write_memory(s, 0x40, 0x100, bytes(range(20)))
    assert out["verified"] is False and out["readback"] == bytes(20).hex()
    # Empty is the method's own refusal; the ceiling past the data view is the registry's
    # (`dosbox_checks.write_data`), judged before a sequence runs, and held there.
    with pytest.raises(ds.Invalid, match="at least one byte"):
        ds.Session.write_memory(s, 0x40, 0x100, b"")
    with pytest.raises(ds.Invalid, match="offset"):
        ds.Session.write_memory(s, 0x40, 0x10000, b"\x00")


def test_write_memory_refuses_the_rom_range_and_a_dead_pty_is_named() -> None:
    """Measured on this build: `SM` into the BIOS ROM ends the emulator, so a real-mode
    write whose bytes touch the ROM range is refused before a line goes out. And a write
    to the terminal of an emulator that has died is an INVALID naming it, where it escaped
    as an I/O error with no session block."""
    s, sent = _writer({"held": b""})
    for seg, off in ((0xF000, 0xE05B), (0xC000, 0x0000), (0xBFFF, 0x0010)):
        with pytest.raises(ds.Invalid, match="ENDS the emulator"):
            ds.Session.write_memory(s, seg, off, b"\x99")
    assert sent == [] and s.altered is False
    s.read_bytes = lambda seg, off, n, mode=None: b"\x99"  # type: ignore[method-assign]
    assert ds.Session.write_memory(s, 0xBFFF, 0x000F, b"\x99")["verified"] is True
    # THE LAST BYTE IS BOUNDED TOO: a write starting under the ceiling whose tail would
    # run past it is refused whole, before any line goes out, where the start alone let
    # `SM xxxx:10000` reach the debugger. And the documented maximum is accepted.
    sent.clear()
    with pytest.raises(ds.Invalid, match="last byte"):
        ds.Session.write_memory(s, 0x0040, 0xFFF8, bytes(20))
    assert sent == []
    s.read_bytes = lambda seg, off, n, mode=None: bytes(n)  # type: ignore[method-assign]
    assert ds.Session.write_memory(s, 0x0040, 0xFF80, bytes(128))["verified"] is True
    with pytest.raises(ds.Invalid, match="a segment is 0x0000 to 0xFFFF"):
        ds.Session.write_memory(s, 0x10000, 0x0000, b"\x99")
    dead = ds.Session.__new__(ds.Session)
    dead.proc = SimpleNamespace(poll=lambda: 1)  # type: ignore[assignment]
    dead._master = -1
    dead._release = lambda data: None  # type: ignore[method-assign]
    with pytest.raises(ds.Invalid, match="GONE"):
        ds.Session._write(dead, b"x\r")
    # A WRITE THAT FAILS WITH THE PROCESS UP IS THE BUG IT LOOKS LIKE: the I/O error is
    # translated only for a dead emulator, and escapes as itself otherwise.
    alive = ds.Session.__new__(ds.Session)
    alive.proc = SimpleNamespace(poll=lambda: None)  # type: ignore[assignment]
    alive._master = -1
    alive._release = lambda data: None  # type: ignore[method-assign]
    with pytest.raises(OSError):
        ds.Session._write(alive, b"x\r")


def test_the_stop_surveys_e9_reader_refuses_a_log_that_is_not_there_yet(tmp_path: Path) -> None:
    """`e9_new_since` is the stop survey's reader and answers as `e9` does: a log the guest
    has not created yet is a channel that cannot be looked at, not zero lines. Answering
    `([], 0)` there made the default E9 block of every early stop a confident `count: 0`
    under `ok` while `e9='all'` on the same stop said the log was unavailable. The wait's
    reader keeps its own reading of an absent log: nothing yet is what a wait is for."""
    s = ds.Session.__new__(ds.Session)
    s.launch = SimpleNamespace(logfile=tmp_path / "not-yet.log")  # type: ignore[assignment]
    with pytest.raises(ds.Invalid, match="has not written anything yet"):
        ds.Session.e9_new_since(s, 0)
    assert ds.Session._e9_since(s, 0) == ([], 0)
    (tmp_path / "not-yet.log").write_text("Bochs port E9h: [+ 0.000] BOOT  . start\n")
    lines, offset = ds.Session.e9_new_since(s, 0)
    assert len(lines) == 1 and offset > 0


def test_the_launch_turns_the_quit_warning_off_so_close_is_a_quit(conf: Path) -> None:
    """With a program loaded, the emulator answers a SIGTERM by asking whether to quit
    anyway, and a session nobody is watching then sits behind that question until the
    SIGKILL: `close` reports `killed` for a guest that was merely busy. The launcher already
    turns the warning off; the session does the same, before the caller's own flags so a
    caller who wants the dialog back can still say so."""
    argv = dlaunch.build_argv(launch(conf))
    assert argv[argv.index("dosbox quit warning=false") - 1] == "-set"
    watched = dlaunch.build_argv(launch(conf, watched=True, window_flags=["-set", "sdl display=1"]))
    assert watched.index("dosbox quit warning=false") < watched.index("sdl display=1")


def test_a_byte_that_spells_a_flag_name_is_sent_as_a_number() -> None:
    """MEASURED on the real debugger: `SM 9000:0040 AC` wrote 00, `SM 9000:0060 0AC` wrote
    AC. The console's value parser reads a bare `AC` (and `AF`, `CF`, `DF`) as the FLAG of
    that name before it reads hex, so a byte value that spells one was silently replaced
    by the flag's value, zero, and every byte after it in the same `SM` went with it. A
    leading zero makes every value a number to that parser, so every byte is sent that way."""
    s, sent = _writer({"held": bytes.fromhex("11AC0000")})
    out = ds.Session.write_memory(s, 0x9000, 0x0000, bytes.fromhex("11AC0000"))
    assert sent == ["SM 9000:0000 011 0AC 000 000"], sent
    assert out["verified"] is True


def test_bytes_of_rows_reads_the_rows_by_their_own_offsets() -> None:
    """`read_memory(length)` hands back `hex` from the data view: the bytes are collected
    from the row that holds the offset onwards, across a row boundary, and a length the
    rows cannot serve is refused rather than padded. Over the captured view."""
    rows = dcons.parse_data_view(REAL_DATA_VIEW)
    assert dcons.bytes_of_rows(rows, 0xE000, 4) == "00000000"
    assert dcons.bytes_of_rows(rows, 0xE00E, 4) == "49424d20", "across the row boundary"
    with pytest.raises(ds.Invalid, match="holds"):
        dcons.bytes_of_rows(rows, 0xE000, 1000)
    with pytest.raises(ds.Invalid, match="holds 0 bytes"):
        dcons.bytes_of_rows(rows, 0x1000, 1)


def test_step_refuses_a_running_machine_in_its_own_words_not_a_register_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`step`'s first act is to read the position, so that reader's refusal escapes whole
    unless `step` settles the question itself: a running machine comes back with the text
    `registers` prints ("no register pane came back from BPLIST... A register read is only
    a reading when...").
    It describes the wrong tool: nothing about a register read tells a caller that a
    KEYSTROKE to a running guest is swallowed with no error anywhere, which is why `step`
    refuses at all."""
    session = cast(Any, ds.Session.__new__(ds.Session))
    monkeypatch.setattr(type(session), "where", lambda self: _running())
    monkeypatch.setattr(type(session), "alive", lambda self: True)
    with pytest.raises(ds.NotStopped) as caught:
        session.step(mode="over", count=1)
    said = str(caught.value)
    assert "register read" not in said, f"step is still using `registers`' words: {said!r}"
    assert "step" in said.lower(), said


def test_step_on_a_dead_emulator_escapes_as_itself_not_as_a_running_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE OTHER HALF OF `step`'s OWN REFUSAL. Giving `step` its own words for a running
    machine must not rewrite the refusal for a machine that is GONE: `_survey` tells those
    apart in its own words, and telling a caller whose emulator has exited to bring it back
    with `stop` sends them at a thing that cannot work. The entry checks `alive()` as the
    mid-loop handler does."""
    gone = ds.NotStopped("no register pane came back from `BPLIST` (emulator GONE)")
    session = cast(Any, ds.Session.__new__(ds.Session))
    monkeypatch.setattr(type(session), "where", lambda self: (_ for _ in ()).throw(gone))
    monkeypatch.setattr(type(session), "alive", lambda self: False)
    with pytest.raises(ds.NotStopped) as caught:
        session.step(mode="over", count=1)
    assert caught.value is gone, f"the dead-emulator refusal was rewritten: {caught.value}"


def test_step_with_a_dead_reader_escapes_as_itself_not_as_a_running_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader thread that ended answers nothing while the process is up: `_survey` names
    it, and `stop` cannot bring back what nothing will read."""
    dead = ds.NotStopped("no register pane came back from `BPLIST`, and the terminal reader "
                         "has DIED (EOF): nothing can come back from this session")
    session = cast(Any, ds.Session.__new__(ds.Session))
    session._drainer = SimpleNamespace(is_alive=lambda: False)
    monkeypatch.setattr(type(session), "where", lambda self: (_ for _ in ()).throw(dead))
    monkeypatch.setattr(type(session), "alive", lambda self: True)
    with pytest.raises(ds.NotStopped) as caught:
        session.step(mode="over", count=1)
    assert caught.value is dead, f"the dead-reader refusal was rewritten: {caught.value}"


def test_a_headless_caller_flag_reaches_argv(conf: Path) -> None:
    """A caller's `-set` (a fixed clock for a watchdog test) is an EMULATOR flag, not a
    placement one, so it travels under `flags` in either mode and reaches argv headless too."""
    clock = ["-set", "cpu cycles=fixed 3000"]
    headless = dlaunch.build_argv(launch(conf, flags=clock))
    assert pair_at(headless, "cpu cycles=fixed 3000"), headless
    watched = dlaunch.build_argv(launch(conf, watched=True, window_flags=["-set", "sdl display=1"],
                                   flags=clock))
    assert pair_at(watched, "cpu cycles=fixed 3000"), watched
    # AFTER the server's own defaults, so a caller's `-set` of the same key wins.
    assert headless.index("cpu cycles=fixed 3000") > headless.index("dosbox quit warning=false")


@pytest.mark.parametrize("flags", [["-set", "cpu", "cycles=fixed 3000"],
                                   ["-set cpu cycles=fixed 3000"], ["-set", ""]])
def test_a_shredded_or_glued_set_is_refused(conf: Path, flags: list[str]) -> None:
    """A `-set` whose value holds no space arrived shredded (`section key=value` is one token
    with a space in it), and DOSBox-X ignores the stray tokens at rc 0; a glued pair hangs it.
    Both are refused before a process exists."""
    with pytest.raises(ds.Invalid, match="bad_argument|-set"):
        dlaunch.validate(launch(conf, flags=flags))


@pytest.mark.parametrize("flags", [
    ["-time-limit", "0"], ["-conf", "other.conf"], ["-break-start"],
    ["-set", "sdl videodriver=cocoa"], ["-set", "log logfile=elsewhere.log"],
    ["-set", "dos  break on int3=false"], ["-set", "serial serial1=disabled"],
    ["-set", "cpu integration device=false"], ["-set", "dosbox captures=/tmp/x"],
    ["-savedir", "/tmp/states"], ["-c", "GAME.EXE"]])
def test_flags_may_not_retune_what_a_named_argument_owns(conf: Path, flags: list[str]) -> None:
    """`flags` carries the emulator's own options, never one this server sets from a named
    argument: the bound (`session_seconds`), the conf, the break at start, headless (`shared`),
    the log,
    the int 3 key, the serial route and the captures. Placed after ours, such a flag would
    quietly undo the argument it shadows (a `-time-limit 0` is no bound at all), so it is
    refused, naming the argument that owns it."""
    with pytest.raises(ds.Invalid, match="owns"):
        dlaunch.validate(launch(conf, flags=flags))


def test_flags_may_still_retune_the_defaults_no_argument_owns(conf: Path) -> None:
    """The quit warning and the clock are the caller's to set: nothing here names them."""
    dlaunch.validate(launch(conf, flags=["-set", "dosbox quit warning=true",
                                    "-set", "cpu cycles=fixed 3000"]))


def test_the_paging_mark_is_the_stop_surveys_and_a_later_survey_does_not_move_it(
        conf: Path) -> None:
    """The mark a stop is recorded with comes from the SAME repaint as its position: a later
    survey (a list read, a pointer follow) whose pane was cut before the EBP line must not turn
    a paged stop into an unplaced one."""
    session = object.__new__(ds.Session)
    head = "ooooRegister Overviewoooooooooooooooooooooooooooooooooooooooooo"
    top = "EAX=00000000  ESI=00000000  DS=00AF   ES=00AF   FS=008F   GS=00BF   SS=00AF Pr32\r\n"
    paged = (head + top +
             "EBX=00000000  EDI=00000000  CS=00A7   EIP=0015A694  C0 Z0 S0 O0 A0 P1 D0 I1 T0\r\n"
             "ECX=000000A7  EBP=002B8690PAGEPSE IOPL3  CPL3\r\n"
             f"ooooOutputoooooooooooooooooooooooooooooooo{dcons.BPLIST_HEADER}\r\n"
             "-------------------------------------------------------------------------\r\n")
    cut = head + top
    screens = iter([paged, cut])
    def command(_cmd: str, *_: Any, **__: Any) -> str:
        return next(screens)

    session.command = command  # type: ignore[method-assign,assignment]
    session._mark_stopped = lambda: None  # type: ignore[method-assign]
    session.stop_survey()
    assert session.paging is True
    with contextlib.suppress(ds.Invalid):     # a cut pane may refuse; the mark must not move
        session._survey()
    assert session.paging is True, "a later survey moved the stop's paging mark"


def test_a_stranger_that_takes_the_port_after_the_check_never_receives_the_input(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MEASURED LIVE: a port picked free and taken by another process before the emulator was
    up left the emulator listening beside it and the session connected to the OTHER process,
    so every key went to it while the replies said delivered. Here the stranger tries to take
    the port the moment the emulator is spawned, and the emulator double dials the port the
    session gave it: the session's socket must be the emulator's, never the stranger's."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    port = _free_port()
    stranger: list[socket.socket] = []
    dialled: list[socket.socket] = []

    class Child:
        pid = 4242

        def poll(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

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
                s.accept()            # the stranger was handed nothing
        assert ses is not None and ses._input is not None
        assert ses._input.getpeername() == dialled[0].getsockname(), "not the emulator's socket"
    finally:
        for s in stranger + dialled:
            s.close()
        if ses is not None:
            ses._stop.set()
            if ses._input is not None:
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
    dlaunch.listen_input(port).close()      # free again while the exception is still held
    assert held.value is not None


RECORDED = json.loads((Path(__file__).parent / "fixtures" / "console_replies" / "recorded.json")
                      .read_text(encoding="utf-8"))


def _replaying(chunks: list[tuple[float, str]]) -> ds.Session:
    """A session whose terminal hands back `chunks`, each once its offset has passed since the
    first read: the real `_read` and `_collect` over bytes a real debugger wrote."""
    ses = ds.Session.__new__(ds.Session)
    ses._eof, ses.dropped = threading.Event(), 0
    ses._pending, ses._raw_tail, ses._screen, ses._raw_reads = "", "", "", 0
    left, began = list(chunks), [0.0]

    def take() -> bytes:
        now = time.monotonic()
        if not began[0]:
            began[0] = now
        due = [c for c in left if now - began[0] >= c[0]]
        for c in due:
            left.remove(c)
        return "".join(raw for _, raw in due).encode("latin-1")
    ses._take = take  # type: ignore[method-assign]
    return ses


def _recorded(name: str) -> list[tuple[float, str]]:
    """A recorded reply, its first piece moved to arrive at once: when the debugger answered
    is not what these cases are about."""
    chunks = [(c["after_s"], c["raw"]) for c in RECORDED[name]["chunks"]]
    return [(at - chunks[0][0], raw) for at, raw in chunks]


def _collected(chunks: list[tuple[float, str]], settle: float = ds.SETTLE_S) -> tuple[str, float]:
    ses = _replaying(chunks)
    began = time.monotonic()
    got = ses._collect(settle, ds.REPLY_TIMEOUT_S, early=True)
    return got, time.monotonic() - began


def test_a_reply_ending_in_the_empty_input_line_is_whole_after_the_grace_not_the_settle(
        ) -> None:
    chunks = _recorded("prompt")
    got, took = _collected(chunks)
    assert got == dcons.ANSI.sub("", "".join(raw for _, raw in chunks))
    assert ds.REPLY_GRACE_S <= took < ds.REPLY_GRACE_S + 0.25, took


def test_a_piece_inside_the_grace_after_the_ending_is_still_this_replys() -> None:
    [(_, raw)] = _recorded("prompt")
    inside, _ = _collected([(0.0, raw), (ds.REPLY_GRACE_S / 2 + ds.COLLECT_SLICE_S, "tail")])
    assert inside.endswith("tail"), "the grace closed before a piece that arrived inside it"
    after, _ = _collected([(0.0, raw), (ds.REPLY_GRACE_S + 0.3, "tail")])
    assert not after.endswith("tail"), "the reply did not end at its terminator plus the grace"


def test_a_paged_listing_is_not_ended_by_its_input_line_which_still_holds_the_command(
        ) -> None:
    """A listing that pages draws the input line still holding the command, then the pager's
    line: cut there and the rest late, the collect still waits for the pager."""
    [(_, raw)] = _recorded("paged")
    cut = raw.index("Paged content")
    assert "I-> " in raw[:cut] and dcons.REPLY_END.search(raw[:cut]) is None
    got, _ = _collected([(0.0, raw[:cut]), (ds.REPLY_GRACE_S + 0.15, raw[cut:])])
    assert "Paged content: Hit ENTER to continue" in got


def test_a_reply_with_no_debugger_ending_keeps_the_settle() -> None:
    chunks = _recorded("running")
    assert dcons.REPLY_END.search("".join(raw for _, raw in chunks)) is None
    got, took = _collected(chunks, settle=0.3)
    assert got and took >= chunks[-1][0] + 0.3, took


def test_only_a_commands_reply_ends_early() -> None:
    """`resume` and `step` collect a stop's repaint with a settle of their own, which no
    recording measured ending early: their collect waits it out."""
    [(_, raw)] = _recorded("prompt")
    ses = _replaying([(0.0, raw)])
    began = time.monotonic()
    ses._collect(0.4, ds.REPLY_TIMEOUT_S)
    assert time.monotonic() - began >= 0.4


def test_the_conf_is_hashed_again_only_when_it_moves(tmp_path: Path) -> None:
    """Every reply says whether the conf changed; the hash is read again only when its size,
    mtime or inode moved, so a list of steps does not read the whole file per step."""
    import os

    import dosbox_launch as dl
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
    # The setup's cleanup signals the fake child's group: never a real process's.
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
    """`program` mounts the stub with `-c` after the conf's `[autoexec]`, so a letter the conf
    already mounted would run whatever is there: the stub takes the first one free from Y down,
    and a conf that mounts them all is refused naming its mounts."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\nfullscreen=false\n[autoexec]\nmount c .\n@MOUNT y /tmp\n"
                    "imgmount x disk.img -t hdd\nsubst W: C:\\TOOLS\n", encoding="utf-8")
    argv = dlaunch.build_argv(launch(conf, program="APP.EXE", input_port=5555))
    assert f'mount V "{dlaunch.GUEST_DIR}"' in argv and "V:\\INJECT.COM" in argv, argv
    every = "\n".join(f"mount {d} ." for d in "DEFGHIJKLMNOPQRSTUVWXY")
    conf.write_text(f"[autoexec]\n{every}\n", encoding="utf-8")
    with pytest.raises(ds.Invalid, match=r"no drive from Y: to D: is free.*mounts D:, E:"):
        dlaunch.validate(launch(conf, program="APP.EXE", input_port=5555))
    # WHAT NEEDS NO DRIVE IS NOT REFUSED: no program, or no input route.
    dlaunch.validate(launch(conf, program="", input_port=5555))
    dlaunch.validate(launch(conf, program="APP.EXE", input_port=None))


@pytest.mark.parametrize(("autoexec", "taken"), [
    ("mount -t cdrom d /cd", "D"), ("[AUTOEXEC]\nMOUNT y .", "Y"),
    ("imgmount -t floppy a a.img", "A"), ("subst x: c:\\tools", "X"),
])
def test_a_conf_s_mounts_are_read_past_options_case_and_a_bom(tmp_path: Path, autoexec: str,
                                                            taken: str) -> None:
    conf = tmp_path / "g.conf"
    head = "" if autoexec.startswith("[") else "[autoexec]\n"
    conf.write_text(f"{head}{autoexec}\n[sdl]\nmount q .\n", encoding="utf-8-sig")
    assert dlaunch.conf_mounts(conf) == [taken], "a mount outside [autoexec] counted, or missed"


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
    for count in (1, ds.STEP_MAX):
        ds.check_step("into", count)
    for count in (0, ds.STEP_MAX + 1):
        with pytest.raises(ds.Invalid) as e:
            ds.check_step("into", count)
        assert e.value.code == "bad_argument"
    for number, ah in ((0, None), (ds.BYTE_MAX, None), (0x21, 0), (0x21, ds.BYTE_MAX)):
        ds.check_interrupt(number, ah)
    for number, ah in ((-1, None), (ds.BYTE_MAX + 1, None), (0x21, ds.BYTE_MAX + 1)):
        with pytest.raises(ds.Invalid):
            ds.check_interrupt(number, ah)
    ds.check_dump_length(1)
    with pytest.raises(ds.Invalid):
        ds.check_dump_length(0)
