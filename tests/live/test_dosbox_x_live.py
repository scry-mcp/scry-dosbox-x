"""Live tier against a real `dosbox-x`; set `DOSBOX_X_LIVE_CONF` and `_CWD` both or neither."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from live_private import guest_dir
from scry_core import prose

import dosbox_binary as binaries
import dosbox_grammar as grammar
import dosbox_launch as dlaunch
import dosbox_session as ds

_OWN = guest_dir()


def _override(name: str, default: str) -> str:
    """An env override; blank falls back to the default (a blank pattern would match every line)."""
    return os.environ.get(name, "").strip() or default


CONF = _override("DOSBOX_X_LIVE_CONF", str(_OWN / "probe.conf"))
CWD = _override("DOSBOX_X_LIVE_CWD", str(_OWN))

GUEST_PROGRAM = _override("DOSBOX_X_LIVE_PROGRAM", "PROBE.COM")
GUEST_MARK = _override("DOSBOX_X_LIVE_MARK", "PROBE")
GUEST_LATE = _override("DOSBOX_X_LIVE_LATE", "late")

_PAIR = [n for n in ("DOSBOX_X_LIVE_CONF", "DOSBOX_X_LIVE_CWD")
         if os.environ.get(n, "").strip()]
_HALF_A_PAIR = ("set BOTH DOSBOX_X_LIVE_CONF and DOSBOX_X_LIVE_CWD or NEITHER: "
                f"only {_PAIR[0]} is set, so the config and the directory it mounts "
                "would come from different places") if len(_PAIR) == 1 else ""

LIVE_MARKS = [
    pytest.mark.live,
    pytest.mark.skipif(
        bool(_HALF_A_PAIR), reason=_HALF_A_PAIR or "the pair is consistent"),
    pytest.mark.skipif(
        not Path(CONF).is_file(),
        reason=f"the live config {CONF} is not a file"),
    pytest.mark.skipif(
        str(_OWN / "probe.conf") == CONF and not (_OWN / "probe.com").is_file(),
        reason=f"the package's own guest {_OWN / 'probe.com'} is missing"),
]
pytestmark = LIVE_MARKS


@pytest.fixture
def session(tmp_path: Path) -> Iterator[ds.Session]:
    log = tmp_path / "guest.log"
    build = binaries.resolve("").path
    s = ds.Session(dlaunch.Launch(
        conf=Path(CONF), cwd=Path(CWD), seconds=90, logfile=log, binary=build,
        debugger_headless=binaries.debugger_headless(build),
        debugger_commands=frozenset(binaries.debugger_commands(build))))
    yield s
    s.close()


def test_the_debugger_comes_up_and_answers_with_a_value(session: ds.Session) -> None:
    """The register readback is the emulator's value, not an echo."""
    session.wait_ready()
    written = session.set_register("ax", 0x1234)
    assert written["readback"] == "0x1234" and written["verified"] is True
    assert session.state()["altered"] is True


def test_a_breakpoint_gives_control_back(session: ds.Session) -> None:
    """Control returns after a resume."""
    session.wait_ready()
    assert "INT 21" in session.breakpoint_interrupt(0x21)
    ran = session.resume()
    assert ran["halted"] is True, ran
    assert ran["stopped_at"] is not None, (
        f"the machine stopped and the position could not be read back. That is a real "
        f"state and not a failure, but this case cannot tell it from a wrong address, "
        f"so it refuses rather than guessing: {ran}")
    stopped = cast(dict[str, str], ran["stopped_at"])
    # A stopped machine does not move: a fresh pane must agree.
    again = session.registers()
    assert (stopped["cs"], stopped["eip"]) == (again["CS"], again["EIP"]), (
        f"`resume` said the machine stopped at {stopped['cs']}:{stopped['eip']} and a "
        f"pane read straight afterwards says {again['CS']}:{again['EIP']}. The machine "
        f"cannot have moved, so one of the two is not a reading of it")
    assert stopped["mode"] in grammar.CPU_MODES, stopped
    assert session.set_register("bx", 0x4321)["readback"] == "0x4321"


def test_the_instrumentation_channel_tells_the_two_nothings_apart(session: ds.Session) -> None:
    """Stopped, the log has no instrumentation: INVALID, not an empty answer."""
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
    """A failure before `close()` must not leak an emulator."""
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD), seconds=60))
    try:
        s.wait_ready()
        assert s.alive()
    finally:
        s.close()
    assert not s.alive()


def conf_that_does_not_exit(tmp_path: Path) -> Path:
    """The caller's conf without launch line and `exit` (`-c` runs after `[autoexec]`)."""
    text = Path(CONF).read_text(encoding="utf-8", errors="replace")
    # Counted separately; `\r?` because a CRLF conf puts `$` before `\n`.
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
    """DX-CAPTURE records a headless session and a frame comes out of it."""
    caps = tmp_path / "caps"
    caps.mkdir()
    s = ds.Session(dlaunch.Launch(
        conf=conf_that_does_not_exit(tmp_path), cwd=Path(CWD), seconds=60,
        program=GUEST_PROGRAM,
        capture_video=True, captures_dir=caps))
    try:
        s.wait_ready()
        s.resume()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            files = sorted(caps.glob("*.avi"), key=lambda f: f.stat().st_size)
            if files and cast(int, ds.avi_facts(files[-1].read_bytes())["avi_frames"]) > 200:
                break
            time.sleep(1.0)
    finally:
        s.close()

    got = ds.Session.captures(s)
    biggest = got[-1]
    assert biggest["riff_avi"] is True, got
    assert cast(int, biggest["avi_frames"]) > 100, got

    shot = tmp_path / "shot.png"
    ds.Session.frame(s, 60, shot, Path(str(got[-1]["path"])))
    assert shot.stat().st_size > 1000
    assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "that is not a PNG"


def test_a_dump_really_lands_and_carries_the_bytes_that_were_asked_for(
        tmp_path: Path) -> None:
    """The dump lands with the bytes asked for; F000:E000 because it is not uniform at reset."""
    dest = tmp_path / "dump.bin"
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD), seconds=90))
    try:
        s.wait_ready()
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
    left = [p for p in candidates if p.exists()]
    assert not left, f"the dump was left behind at {left}"


GUEST_STAMP = re.compile(r"\[\+\s*([0-9]+\.[0-9]+)\]")

QUIET_SECONDS = 25.0


def newest_guest_stamp(log: Path) -> float | None:
    """The guest's own clock, off the LOGFILE; the maximum, since a stamp may reset."""
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = [float(x) for x in GUEST_STAMP.findall(text)]
    return max(found) if found else None


def test_the_machine_keeps_running_while_nobody_is_asking(tmp_path: Path) -> None:
    """The guest runs while nobody asks.

    Measured on the LOGFILE: a session read drains the pty and would hide the freeze.
    """
    log = tmp_path / "guest.log"
    s = ds.Session(dlaunch.Launch(conf=Path(CONF), cwd=Path(CWD),
                             seconds=180, logfile=log))
    try:
        s.wait_ready()
        s.resume()
        deadline = time.monotonic() + 60
        base = None
        while base is None and time.monotonic() < deadline:
            base = newest_guest_stamp(log)
            if base is None:
                time.sleep(1.0)
        assert base is not None, "the guest emitted no instrumentation at all: INVALID"

        # Sampling throughout separates a rate from one buffered flush.
        samples: list[tuple[float, float]] = []
        quiet_start = time.monotonic()
        deadline = quiet_start + QUIET_SECONDS
        while time.monotonic() < deadline:
            time.sleep(QUIET_SECONDS / 10.0)
            now = newest_guest_stamp(log)
            if now is not None:
                samples.append((round(time.monotonic() - quiet_start, 2), now))
            if not s.alive():
                pytest.skip("the emulator exited during the quiet window, so this "
                            "window measured a shutdown and not a running guest")
        moved = newest_guest_stamp(log)
    finally:
        s.close()

    assert moved is not None, "the guest clock vanished from the log: INVALID"
    assert len(samples) >= 5, f"only {len(samples)} samples: this window measured nothing"
    advanced = moved - base
    # The stamp counts ticks; a frozen guest gives 0.
    assert advanced >= 2.0, (
        f"the guest odometer moved {advanced:.0f} ticks in {QUIET_SECONDS} s of wall "
        f"clock with nobody asking it anything (from {base} to {moved}, samples "
        f"{samples}). A terminal nobody drains blocks the emulator and looks like this; "
        f"so does a host with no time to spare. What is certain is that it did not move.")
    steps = sum(1 for (_, a), (_, b) in zip(samples, samples[1:], strict=False) if b > a)
    assert steps >= 2, (
        f"the clock moved in {prose.counted(steps, 'step')} across {len(samples)} samples "
        f"({samples}): that is a buffer flushing, not a machine running")
