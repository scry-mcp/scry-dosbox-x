"""The one thing the contract tests cannot show: that this drives a REAL emulator.

It is separated from the rest because it needs `dosbox-x` on the PATH and a DOS
config, and because it takes tens of seconds rather than milliseconds. The config is
this package's OWN by default (`tests/guest/`), so the only thing it needs from the
machine is `dosbox-x` on the PATH. It SKIPS when a precondition is missing -- and it
says WHICH, because "skipped" and "passed" must not print the same thing.

Point it at your own program instead with `DOSBOX_X_LIVE_CONF` plus that config's
working directory in `DOSBOX_X_LIVE_CWD` -- BOTH or NEITHER, because DOSBox-X configs
mount relative paths, so the directory is part of the fixture and not a detail. Setting
one of the two used to pair a stranger's config with this package's directory and
refuse neither.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from live_private import guest_dir

import dosbox_console as dcons
import dosbox_launch as dlaunch
import dosbox_session as ds

# THE PACKAGE'S OWN GUEST IS THE DEFAULT, and pointing the tier at a project is the
# override rather than the requirement.
#
# It used to be the other way round, and the cost was measured: with the tier aimed at a
# config whose guest was not one particular private application, NINE cases FAILED --
# not skipped -- while the README said it "SKIPS unless you point it at a config". The
# dependency was never the project's name; it is that the guest RUNS after a `resume`
# and EMITS instrumentation, which `resume`, `e9`, `e9_wait`, `step`-on-a-running-
# machine and the bound cases all rest on. `tests/guest/` holds 144 bytes that do
# exactly that and nothing else.
_OWN = guest_dir()


def _override(name: str, default: str) -> str:
    """One `DOSBOX_X_LIVE_*` override, resolved the SAME WAY as the other four.

    THE FIVE USED TWO IDIOMS AND THEREFORE HAD THREE BEHAVIOURS on an exported-but-
    EMPTY value, which is an ordinary thing to have in a shell (`export X=` in a
    profile, a CI variable with no value). MEASURED, all three:

      * `... or default` -- CONF and CWD -- fell back SILENTLY, so a caller who meant
        their own config ran the package's guest and was told nothing.
      * `get(name, default)` -- PROGRAM -- kept the empty string, and
        `"".split()[0]` raised `IndexError: list index out of range` out of a fixture,
        so two cases ERRORED rather than skipped.
      * `get(name, default)` -- MARK -- kept it too, and an empty pattern compiles to a
        regex matching EVERY line while `"" in <anything>` is True, so the case passed
        having asserted nothing about the guest at all. That is the worst of the three:
        the other two are loud.

    Whitespace is stripped for the same reason: a trailing newline off a `$(...)` is
    the same mistake wearing different bytes.
    """
    return os.environ.get(name, "").strip() or default


CONF = _override("DOSBOX_X_LIVE_CONF", str(_OWN / "probe.conf"))
CWD = _override("DOSBOX_X_LIVE_CWD", str(_OWN))

# The guest's launch line and the two tokens it logs. THEY LIVE HERE AND NOWHERE ELSE:
# `test_dosbox_x_live_tools.py` imports them from this module, because both files
# carried their own copy of this block and the copy in THIS one was read by nothing --
# a constant with a comment explaining why it exists, in the file that never used it.
# Two definitions of one override is how a caller's tokens get read from the wrong one.
GUEST_PROGRAM = _override("DOSBOX_X_LIVE_PROGRAM", "PROBE.COM")
GUEST_MARK = _override("DOSBOX_X_LIVE_MARK", "PROBE")
GUEST_LATE = _override("DOSBOX_X_LIVE_LATE", "late")

# CONF AND CWD ARE ONE FIXTURE, NOT TWO SETTINGS, and defaulting them independently is
# how you get a pairing nobody chose: this module's own header says "DOSBox-X configs
# mount relative paths, so the directory is part of the fixture". Setting only CWD runs
# the PACKAGE's `probe.conf` with `mount c "."` pointing somewhere that has no
# `PROBE.COM`; setting only CONF resolves a stranger's relative mounts against
# `tests/guest/`. Both or neither.
_PAIR = [n for n in ("DOSBOX_X_LIVE_CONF", "DOSBOX_X_LIVE_CWD")
         if os.environ.get(n, "").strip()]
_HALF_A_PAIR = ("set BOTH DOSBOX_X_LIVE_CONF and DOSBOX_X_LIVE_CWD or NEITHER: "
                f"only {_PAIR[0]} is set, so the config and the directory it mounts "
                "would come from different places") if len(_PAIR) == 1 else ""

# TWO MARKS, AND THE FIRST ONE IS THE GUARD. `live` is deselected by the root config, so
# reaching this tier takes an explicit `-m live` rather than an environment variable that
# happens to be exported. Before it existed, the commit-time pytest run
# with no exclusion -- would have launched eight emulators for anyone with
# `DOSBOX_X_LIVE_CONF` set, while a second runner in this package carefully passed
# `--ignore tests/live`.
# An exclusion applied in one runner and not the other is not an exclusion.
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        bool(_HALF_A_PAIR), reason=_HALF_A_PAIR or "the pair is consistent"),
    # THE CONFIG AND THE GUEST BINARY, because the config alone is not the fixture.
    # With `probe.com` absent, DOS prints `Bad command or file name`, RETURNS, and the
    # `exit` that `probe.conf` calls unreachable then runs -- so the emulator shuts
    # down seconds into the window and the flagship case SKIPS, which is a green
    # meaning nothing looked.
    pytest.mark.skipif(
        not Path(CONF).is_file(),
        reason=f"the live config {CONF} is not a file"),
    pytest.mark.skipif(
        str(_OWN / "probe.conf") == CONF and not (_OWN / "probe.com").is_file(),
        reason=f"the package's own guest {_OWN / 'probe.com'} is missing"),
]


@pytest.fixture
def session(tmp_path: Path) -> Iterator[ds.Session]:
    log = tmp_path / "guest.log"
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD),
                             seconds=90, logfile=log))
    yield s
    s.close()


def test_the_debugger_comes_up_and_answers_with_a_value(session: ds.Session) -> None:
    """The reply a terminal echo cannot fabricate.

    An acknowledgement like "Set Register success." contains only words the caller
    typed; the VALUE in the register pane is the emulator's. Measured while building
    this: with echo left on and no emulator running at all, a check looking for its
    own command words scored TRUE.
    """
    session.wait_ready()
    written = session.set_register("ax", 0x1234)
    assert written["readback"] == "1234" and written["verified"] is True
    assert session.state()["altered"] is True


def test_a_breakpoint_gives_control_back(session: ds.Session) -> None:
    """Three separate things, because "the debugger answers" was already true BEFORE
    resuming and so cannot be the evidence that control returned."""
    session.wait_ready()
    assert "INT 21" in session.breakpoint_interrupt(0x21)
    ran = session.resume()
    # (i) the guest genuinely ADVANCED: text that cannot appear while stopped.
    screen = cast(str, ran["screen"])
    assert any(m in screen for m in ("COMMAND.COM", "EMS page frame", "XMS:"))
    # (ii) AND THE TOOL SAW IT TOO. An INT 21 breakpoint was armed above, so this
    # resume is the halted direction against a real emulator: `halted` must be True
    # and the address must be the one the machine really stopped at. Before #382 this
    # reply carried no field a caller could read for it.
    assert ran["halted"] is True, ran
    # THE STATE THE DOCSTRING CALLS ORDINARY IS NAMED, not subscripted. `cast` is a
    # no-op at run time, so `stopped_at[...]` on the documented `halted: True` with
    # `stopped_at: None` died with a bare `TypeError` -- an ERROR with no message,
    # indistinguishable from a real defect.
    assert ran["stopped_at"] is not None, (
        f"the machine stopped and the position could not be read back. That is a real "
        f"state and not a failure, but this case cannot tell it from a wrong address, "
        f"so it refuses rather than guessing: {ran}")
    stopped = cast(dict[str, str], ran["stopped_at"])
    # AND THE ADDRESS IS COMPARED AGAINST AN INDEPENDENT READ, which is what the
    # comment above always claimed and what NO assertion here did. The line that stood
    # here was `stopped_at["mode"] in dcons.CPU_MODES`, and it CANNOT FAIL: `parse_mode`
    # only ever answers a member of that tuple, and `where()` refuses the `None`, so
    # it held whatever `resume` handed it -- a `stopped_at` replaced by a constant
    # passed this case green. A stopped machine does not move, so a FRESH pane has to
    # name the same place; that is the reading `resume` cannot fake.
    again = session.registers()
    assert (stopped["cs"], stopped["eip"]) == (again["CS"], again["EIP"]), (
        f"`resume` said the machine stopped at {stopped['cs']}:{stopped['eip']} and a "
        f"pane read straight afterwards says {again['CS']}:{again['EIP']}. The machine "
        f"cannot have moved, so one of the two is not a reading of it")
    assert stopped["mode"] in dcons.CPU_MODES, stopped
    # (iii) and it takes a NEW command afterwards, carrying a NEW value.
    assert session.set_register("bx", 0x4321)["readback"] == "4321"


def test_the_instrumentation_channel_tells_the_two_nothings_apart(session: ds.Session) -> None:
    """Stopped at the debugger, the guest has not run, so the log holds DOSBox-X's own
    lines and no instrumentation at all. That is INVALID and not an empty answer -- a
    caller told "nothing matched" would conclude something about their pattern."""
    session.wait_ready()
    with pytest.raises(ds.Invalid, match="no instrumentation at all"):
        session.e9("anything")


def test_a_session_without_a_logfile_refuses_to_pretend(tmp_path: Path) -> None:
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD), seconds=30))
    try:
        s.wait_ready()
        with pytest.raises(ds.Invalid, match="no (instrumentation|log) channel"):
            s.e9("x")
    finally:
        s.close()


def test_close_leaves_nothing_behind(tmp_path: Path) -> None:
    """THE `finally` IS THE POINT OF THIS CASE, and it was the one case in this file
    without one. `wait_ready` raises `Invalid` on a build with no debugger and the
    assertion below can fail, and on either path `close()` never ran: an emulator
    lived out its 60 s bound and the terminal descriptor leaked, from the case named
    for leaving nothing behind. Nothing counts leaked emulators on this tier, so nothing
    else would have said so.
    """
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD), seconds=60))
    try:
        s.wait_ready()
        assert s.alive()
    finally:
        s.close()
    assert not s.alive()


def conf_that_does_not_exit(tmp_path: Path) -> Path:
    """The caller's conf with its run-and-exit removed, and the mounts kept.

    `program` is passed with `-c`, and MEASURED, `-c` runs AFTER the `[autoexec]`
    section: a conf whose autoexec ends in `exit` quits before it is reached. So this
    parameter needs a conf of a particular shape, and the honest way to test it is to
    BUILD that shape rather than to pretend the caller's own conf has it.

    The substitution is REQUIRED to match. A patch that quietly changes nothing would
    leave this measuring the original conf under the label of the patched one.
    """
    text = Path(CONF).read_text(encoding="utf-8", errors="replace")
    # THE LAUNCH LINE AND THE `exit`, COUNTED SEPARATELY, whichever program the caller
    # pointed at. Three things were wrong with doing it in one alternation and a
    # `n < 2` guard, and all three are MEASURED against this package's own conf:
    #
    #   * `n >= 2` never required ONE OF EACH. Two `exit` lines satisfied it while the
    #     launch line SURVIVED -- and a surviving launch line means the guest starts
    #     from `[autoexec]` and the `-c` program this case exists to test never runs.
    #     That is verbatim the failure the docstring above says the count prevents.
    #   * `(?i)` PLUS A SHORT NAME ATE REAL SETTINGS. With `DOSBOX_X_LIVE_PROGRAM=c`
    #     the pattern deleted `core=normal`, `cputype=pentium`, `cycles=fixed 10000`
    #     and `c:` -- n=5, the guard satisfied, `PROBE.COM` and `exit` both left in
    #     place, and the case running against a conf with its CPU section destroyed.
    #     Anchoring on a word boundary is what stops a program name being a prefix of
    #     a config key; `(?i)` stays, because DOS names are case-blind.
    #   * A CRLF CONF matched ONCE. `re.M`'s `$` sits before the `\n`, so `^exit$`
    #     cannot match `exit\r` while `^PROBE\.COM.*$` matches happily -- `.` eats the
    #     `\r`. A conf authored on Windows, for a DOS project, skipped both cases with
    #     a message blaming its shape.
    launch = re.escape(GUEST_PROGRAM.split()[0])
    patched, n_launch = re.subn(rf"(?mi)^{launch}\b.*\r?$", "", text)
    patched, n_exit = re.subn(r"(?mi)^exit[ \t]*\r?$", "", patched)
    if n_launch < 1 or n_exit < 1:
        pytest.skip("this conf is not the shape this case patches "
                    f"(launch lines matched {n_launch}, `exit` matched {n_exit}; "
                    "it needs both, each at the start of its own line)")
    out = tmp_path / "nolaunch.conf"
    out.write_text(patched, encoding="utf-8")
    return out


def test_both_halves_of_the_capture_against_a_real_emulator(tmp_path: Path) -> None:
    """The VIDEO and the STILL, on the real path, with nobody at the keyboard.

    This is the one thing no fixture can show: that DX-CAPTURE really records a
    headless session and that a frame really comes out of what it wrote. The still is
    an EXTRACTION from the video, because the emulator's own screenshot is a mapper
    action and has no non-interactive trigger.

    It waits for the INDEX rather than for a fixed time: a frame cannot be pulled from
    a recording that is still open, and how long the guest takes is the guest's.
    """
    caps = tmp_path / "caps"
    caps.mkdir()
    s = ds.Session(dlaunch.Launch(
        conf=conf_that_does_not_exit(tmp_path), cwd=Path(CWD), seconds=60,
        program=GUEST_PROGRAM,
        capture_video=True, captures_dir=caps))
    try:
        s.wait_ready()
        s.resume()
        # WAIT ON THE PROPERTY THIS ASSERTS, not on a proxy for it. Waiting on the
        # file's SIZE and then asserting its FRAME COUNT is two thresholds that can
        # disagree, and they did: the loop broke at 200 KB with 89 frames against an
        # assertion of 100.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            files = sorted(caps.glob("*.avi"), key=lambda f: f.stat().st_size)
            if files and cast(int, ds.avi_facts(files[-1].read_bytes())["frames"]) > 200:
                break
            time.sleep(1.0)
    finally:
        s.close()

    got = ds.Session.captures(s)
    biggest = got[-1]
    assert biggest["riff_avi"] is True, got
    assert cast(int, biggest["frames"]) > 100, got
    # `complete` is NOT asserted, and its absence here is the finding: the program
    # under capture runs forever, so the recording is never finalised and the file
    # carries no index. MEASURED, that does not matter -- a frame comes out anyway,
    # which is what the next lines prove and what an earlier docstring wrongly denied.

    shot = tmp_path / "shot.png"
    ds.Session.frame(s, 60, shot)
    assert shot.stat().st_size > 1000
    assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "that is not a PNG"


def test_a_dump_really_lands_and_carries_the_bytes_that_were_asked_for(
        tmp_path: Path) -> None:
    """The case whose absence let a tool ship having never once worked.

    `memdump` collected from the CAPTURES directory, on the strength of a sentence in
    the debugger's help. MEASURED during #317's QA: the file lands in the emulator's
    WORKING directory instead, so every dump ever taken reported INVALID -- correct
    behaviour (the debugger claimed success and the disk disagreed, so the tool
    refused to call it a reading) from a tool looking in the wrong place. Nothing
    caught it because nothing ran it against a real emulator.

    THE LENGTH IS ASSERTED FOR EQUALITY, not merely that a file appeared: a stale file
    from an earlier run is also a file, and the size is what ties this one to THIS
    request. THE CONTENT IS ASSERTED TOO: a uniform buffer is what a wrong segment,
    unmapped memory and a truncated write all produce alike.

    IT DUMPS THE BIOS ROM AND NOT THE BIOS DATA AREA, and the address was MEASURED
    rather than reasoned. The session is stopped at the RESET VECTOR, before the BIOS
    has initialised anything, so the obvious choice is worthless here: probed on this
    build, 256 bytes at `0000:0400` hold ONE distinct value and so do 256 at
    `F000:0000`, while `F000:E000` holds 26. Only the third can tell a real read from
    a buffer of zeros, which is the whole point of looking at the content at all.
    """
    dest = tmp_path / "dump.bin"
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD), seconds=90))
    try:
        s.wait_ready()
        # THE PRE-EXISTING FILE IS REFUSED, and it is asked here rather than assumed:
        # this tool used to DELETE whatever sat at those paths, and the first of them
        # is the emulator's working directory, which is somebody's repository.
        candidates = s._memdump_candidates()
        planted = candidates[0]
        planted.write_bytes(b"not this dump")
        try:
            with pytest.raises(ds.Invalid, match="already sitting at"):
                s.memdump(0xF000, 0xE000, 256, dest)
            assert planted.read_bytes() == b"not this dump", "it deleted a caller's file"
        finally:
            planted.unlink()
        got = s.memdump(0xF000, 0xE000, 256, dest)
    finally:
        s.close()
    assert got == dest
    assert dest.stat().st_size == 256, "that is not the dump that was asked for"
    body = dest.read_bytes()
    assert len(set(body)) > 1, ("every byte is identical, which is what a wrong "
                                "segment and a truncated write both look like")
    # And it leaves nothing behind. THE LIST IS ASKED OF THE MODULE, never written out
    # here: a hand-copied pair of names silently stops covering a third location or a
    # third spelling the day one is added.
    left = [p for p in candidates if p.exists()]
    assert not left, f"the dump was left behind at {left}"


GUEST_STAMP = re.compile(r"\[\+\s*([0-9]+\.[0-9]+)\]")

# How long the machine is left completely alone. Long enough that a flush lag cannot
# be mistaken for the guest running, short enough to stay inside a session's bound.
QUIET_SECONDS = 25.0


def newest_guest_stamp(log: Path) -> float | None:
    """The guest's own clock, off the LOGFILE. Never through the session -- see below.

    IT TAKES THE MAXIMUM, NOT THE LAST LINE, and the difference is not pedantry: the
    stamp is not guaranteed monotone. The paragraph this replaces described a DIFFERENT
    guest -- a private application whose profiler clock reset during boot, so `[+ 0.049]`
    was followed by `[+ 0.000]` -- and it survived the swap to `tests/guest/probe.com`
    unchanged, describing a log nobody in this repository can produce any more.

    WHAT IS TRUE OF THE GUEST THAT ACTUALLY RUNS: `probe.com`'s odometer rises by one
    per line and WRAPS at 99999, and a maximum is exactly what a wrap breaks -- after
    it, the maximum never rises again. At ~3 s a line that is about 83 hours into one
    session, so no run reaches it; the maximum is kept because a caller pointing this at
    their OWN program brings back the reset case, which is the one it was written for.
    """
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = [float(x) for x in GUEST_STAMP.findall(text)]
    return max(found) if found else None


def test_the_machine_keeps_running_while_nobody_is_asking(tmp_path: Path) -> None:
    """The defect this test exists for, and the reason no contract test could see it.

    A pty master's buffer is finite, so when it fills the WRITER blocks -- and the
    writer is the emulator. While the only reader was a tool call, the machine froze
    between questions. MEASURED before the drain thread existed: three sessions stuck
    at EXACTLY `[+ 2.091]` for 105, 48 and 36 seconds of wall clock, and one
    `registers` call moved the guest forward by 7 guest-seconds.

    IT MEASURES THE LOGFILE ON DISK AND NEVER ASKS THE SESSION, which is the load
    bearing decision here: every read through the session drains the terminal, so a
    test that asked the server whether the guest had moved would be creating the very
    condition under which the bug does not happen. It could not fail.

    The stamp is the GUEST's own clock, which the host does not control, so a busy
    machine cannot fake a pass.
    """
    log = tmp_path / "guest.log"
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD),
                             seconds=180, logfile=log))
    try:
        s.wait_ready()
        s.resume()
        # The BASE is taken after resume and is REQUIRED: without a guest clock at all
        # there is nothing to compare, and "it never started" would read as "it never
        # advanced" -- a pass for the wrong reason is the failure this whole suite is
        # written against.
        deadline = time.monotonic() + 60
        base = None
        while base is None and time.monotonic() < deadline:
            base = newest_guest_stamp(log)
            if base is None:
                time.sleep(1.0)
        assert base is not None, "the guest emitted no instrumentation at all: INVALID"

        # NOW THE SILENCE. Not one call that touches the TERMINAL in here. `alive()`
        # is `proc.poll()`, which does no terminal I/O, so it cannot create the
        # condition under test and is safe to ask -- and it has to be asked, see below.
        #
        # IT SAMPLES THROUGHOUT rather than taking two readings, and that is the
        # control that separates a RATE from a single flush. With only a start and an
        # end, a frozen guest whose log buffer happens to flush once inside the window
        # is indistinguishable from one running smoothly. Sampling is a file read, so
        # it costs nothing and drains nothing.
        samples: list[tuple[float, float]] = []
        quiet_start = time.monotonic()
        deadline = quiet_start + QUIET_SECONDS
        while time.monotonic() < deadline:
            time.sleep(QUIET_SECONDS / 10.0)
            now = newest_guest_stamp(log)
            if now is not None:
                samples.append((round(time.monotonic() - quiet_start, 2), now))
            # A LEGITIMATE STOP IS NOT A DRAIN BUG. This conf's autoexec runs the app
            # and then `exit`, so when the app quits DOSBox-X quits: without this the
            # case reports a frozen guest for a machine that ended normally, and the
            # flush that death produces could even push it over the bar in the other
            # direction.
            if not s.alive():
                pytest.skip("the emulator exited during the quiet window, so this "
                            "window measured a shutdown and not a running guest")
        moved = newest_guest_stamp(log)
    finally:
        s.close()

    assert moved is not None, "the guest clock vanished from the log: INVALID"
    assert len(samples) >= 5, f"only {len(samples)} samples: this window measured nothing"
    advanced = moved - base
    # THE FLOOR IS IN TICKS, BECAUSE THE STAMP IS A TICK COUNT. It used to be
    # `QUIET_SECONDS / 5.0`, and every number in the paragraph justifying it -- "30.65
    # guest seconds in 30 s of wall clock", "~1500 bytes per guest second", "a 4 KB
    # flush releases ~2.7 guest seconds" -- described a DIFFERENT guest: a private
    # application whose stamp was a profiler clock in seconds. `probe.com`'s stamp is an
    # odometer that rises by ONE per line, so the derivation was arithmetic about a
    # quantity this guest does not emit, and the floor it produced was 5.0.
    #
    # MEASURED on this machine, `cycles=fixed 10000`, reading the case's own logfile:
    # the odometer reaches **5** over the whole session. So the old floor of 5.0 was
    # passing by a margin of ZERO -- one line slower and this case goes red blaming a
    # pty deadlock, on a host that is merely busy.
    #
    # TWO IS THE FLOOR AND THE SHAPE BELOW IS WHAT MAKES IT ENOUGH. A frozen guest
    # advances by 0, which 2 catches with room to spare; the thing 5.0 was reaching for
    # -- a single buffered flush releasing a backlog and looking like progress -- is a
    # question about STEPS and not about distance, and it is asserted directly, four
    # lines down, where it belongs.
    assert advanced >= 2.0, (
        f"the guest odometer moved {advanced:.0f} ticks in {QUIET_SECONDS} s of wall "
        f"clock with nobody asking it anything (from {base} to {moved}, samples "
        f"{samples}). A terminal nobody drains blocks the emulator and looks like this; "
        f"so does a host with no time to spare. What is certain is that it did not move.")
    # THE SHAPE, which one flush cannot fake: a running guest advances in MORE than a
    # single step. A frozen one releases its backlog once and then sits still.
    steps = sum(1 for (_, a), (_, b) in zip(samples, samples[1:], strict=False) if b > a)
    assert steps >= 2, (
        f"the clock moved in {steps} step(s) across {len(samples)} samples "
        f"({samples}): that is a buffer flushing, not a machine running")
