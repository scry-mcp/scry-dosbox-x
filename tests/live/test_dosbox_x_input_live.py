"""Phase 5, the driver's ACT half against a REAL guest: send_keys puts a key into a running
program and the program acts on it; send_mouse posts a click. This is R1's missing piece --
the CUE A demo the whole plan is measured against -- proved end to end through the MCP tools.

THE ROUTE IS A HOST EVENT TO THE FRONTMOST WINDOW, so these need a WINDOWED (shared) session
and macOS Accessibility trust for the process running pytest. They SKIP without the window
flags, and they will FAIL (not skip) if the host process is not Accessibility-trusted -- that
is the honest signal that the route is unavailable here, not a false pass.

They also STEAL FOCUS for about a second each (the window is brought frontmost and handed
back), so they are not for a machine someone is using at that moment.

They run on the package's DPMI guest (`dpmi_guest`), whose marks `dpmi.c` writes itself: the
cue key's answer, every key's arrival, a button press with the pointer, and a periodic line once
its INPUT LOOP is up, which every case waits for before its first key or click (the boot line is
written in the program's first instant, and a key posted before the loop reads input is
swallowed without a trace). The conf runs the package's serial stub, so the serial-route case
needs no window.

  DOSBOX_X_LIVE_WINDOW_FLAGS   `place-window dosbox`, one token per line; gates the window cases
  DOSBOX_X_WALK_MAX            ceiling on the resume-walk to the client (see the entry routes)
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, cast

import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_session as ds
import dosbox_x_server as server

pytestmark = pytest.mark.live

FLAGS = [ln for ln in os.environ.get("DOSBOX_X_LIVE_WINDOW_FLAGS", "").splitlines() if ln.strip()]
#: The window route needs a placed window; the serial route runs without one.
WINDOWED = pytest.mark.skipif(not FLAGS, reason="set DOSBOX_X_LIVE_WINDOW_FLAGS for the window "
                                                "route")
KEY_MARK, ARRIVAL_MARK, MOUSE_MARK = guest.KEY_MARK, guest.ARRIVAL_MARK, guest.MOUSE_MARK
BOOT_MARK, SETTLED_MARK = guest.BOOT_MARK, guest.SETTLED_MARK
SERIAL_PORT = 5555        # the port the serial-route case asks the emulator's COM1 to listen on
NUDGE_PX = 100            # the host delta the mouse case sends along X
NUDGE_MIN_MOVED = 25      # the guest must have moved at least this far along X for it
RECENTRE_JITTER = 8       # pixels of Y drift the capture's re-centring is allowed to leave
LEAK_DENOMINATOR = 5      # Y may move at most a fifth of what X moved (no axis leak)
LOOK_LINES = 400          # the drive case's look, wide enough to hold a short act's lines
CAPTURE_CLICKS_MAX = 3    # clicks allowed before one reaches the guest (the first captures)
BOOT_WAIT_S = 60
SETTLED_WAIT_S = 90


def _start_windowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                    seconds: int = 180) -> Path:
    """ONE windowed session on the DPMI build, the store isolated, the log in tmp_path.
    The three input cases share this boot exactly, which is why it is one function: the
    duplication gate caught it written out three times."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    log = tmp_path / "guest.log"
    r = cast(dict[str, Any], server.start(
        conf=str(guest.CONF), cwd=str(guest.GUEST), seconds=seconds, mode="shared",
        window_flags=FLAGS, logfile=str(log), program=guest.PROGRAM))
    assert r["status"] == "ok", r
    return log


def _input_loop_live() -> None:
    """Wait, on the guest's OWN log, until its input loop is up: the boot line, then the
    settled mark. Shared by every case that posts a key or a click, on either route, so none of
    them can post into the gap between the program starting and the program listening."""
    boot = cast(dict[str, Any], server.log_wait(channel="guest", pattern=BOOT_MARK,
                                                seconds=BOOT_WAIT_S))
    assert boot["status"] == "ok", boot
    settled = cast(dict[str, Any], server.log_wait(channel="guest", pattern=SETTLED_MARK,
                                                  seconds=SETTLED_WAIT_S))
    assert settled["status"] == "ok", settled


@WINDOWED
def test_send_keys_reaches_the_running_guest_and_it_acts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1's CUE A half: launch the guest in a WINDOW, let it run, send the cue key, and confirm
    the PROGRAM acted on it -- the E9 mark the app writes only from that key's handler. The
    key goes to a RUNNING guest (no breakpoint), which is the route AUTOTYPE and the console
    cannot serve. `posted` and the focus fields come back; `activated` proves the window was
    brought forward."""
    _start_windowed(tmp_path, monkeypatch)
    # let the guest boot and reach its input loop; the window is up and frontmost-able.
    server.resume()
    _input_loop_live()

    # THE KEY, to the running guest, WITH ITS EXPECTATION: `a` is the guest's cue key and the
    # mark is written only by the app's own handler for it. The tool marks the log, posts,
    # and confirms a NEW matching line -- the program ACTED, in the same reply.
    sent = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_MARK, seconds=30))
    assert sent["status"] == "ok", (
        f"the guest did not act on the key ({KEY_MARK} never logged): the host event did not "
        f"reach the running program. {sent.get('message')}")
    assert sent["posted"] == 1 and sent["activated"] is True, sent
    assert sent["effect"]["seen"] is True and re.search(KEY_MARK, sent["effect"]["line"]), sent

    # THE CONTROL, through the same route on the same run, and it is the MARK that it pins:
    # the cue line now sits in the log, so a key the program IGNORES (F11 is bound to
    # nothing) posted with the SAME expectation must come back a MISS. A wait from byte 0
    # would find the stale cue line and pass; only a wait from the mark misses. Without this
    # red beside the green, "verified" and "the verifier never looked" print the same thing.
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "INVALID" and "did not react" in missed["message"], missed
    assert missed["posted"] == 1 and missed["effect"]["seen"] is False, missed
    # AND THE MISS IS THE PROGRAM'S, NOT THE ROUTE'S: when the guest announces every key it
    # receives (its `key down <NAME>` arrival line), the ignored key is shown to have
    # ARRIVED -- so "did not react" above means "took it and did nothing", which is the two
    # facts this tool exists to keep apart.
    arrived = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK, seconds=5))
    assert arrived["status"] == "ok" and arrived["effect"]["seen"] is True, arrived


@WINDOWED
def test_a_sequence_sends_a_verified_key_to_the_running_guest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 as ONE `perform`: resume the fresh session, wait for the program to be up, send
    the cue key with its expectation, and read the log after it. `resume` leaves the guest
    running and every later step is a running-OK op, so the sequence runs to the end without
    a stop -- and the key step's reply carries the program's own reaction. This is the
    `[resume, send_keys]` shape the contract tier models with a double; here it is real."""
    _start_windowed(tmp_path, monkeypatch)
    # THE SAME "INPUT LOOP IS LIVE" WAIT AS THE OTHER CASES, spelled as sequence steps: the
    # boot line, then the settled mark.
    steps: list[dict[str, Any]] = [
        {"op": "resume"},
        {"op": "log_wait", "pattern": BOOT_MARK, "channel": "guest", "seconds": BOOT_WAIT_S},
        {"op": "log_wait", "pattern": SETTLED_MARK, "channel": "guest",
         "seconds": SETTLED_WAIT_S}]
    key_step = len(steps)
    steps += [
        {"op": "send_keys", "keys": ["a"], "expect": KEY_MARK, "seconds": 30},
        {"op": "log", "pattern": KEY_MARK, "channel": "guest"}]
    out = cast(dict[str, Any], server.perform(steps=steps, wait=5.0))
    assert out["status"] == "ok" and out["completed"] == len(steps), out
    assert out["ran"][key_step]["reply"]["effect"]["seen"] is True, out["ran"][key_step]
    # WHAT THE TAIL SAYS IS `resume`'S READING OF `halted`, not this case's subject: a boot
    # repaint can read as a halt (the open card on resume's two-step boot), in which case
    # the executor takes the machine as stopped and writes no tail. Either shape is
    # accepted here; the four steps ran and the key was seen, which is what this proves.
    assert out.get("still_running") is True or out["ran"][0]["reply"].get("halted"), out


@WINDOWED
def test_drive_looks_acts_and_verifies_in_one_call(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop an autonomous session runs: ONE `drive` sends the cue key, verifies the
    program's reaction from a mark taken before the act, and hands back what the guest wrote
    since -- the cue line among them, and nothing from before the mark."""
    _start_windowed(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()
    out = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect=KEY_MARK, seconds=30,
        pattern=".", limit=LOOK_LINES))
    assert out["status"] == "ok", out
    verify = out["verify"]
    assert verify["seen"] is True and re.search(KEY_MARK, verify["line"]), verify
    e9 = out["looked"]["e9"]
    assert e9["available"] is True and e9["written"] >= 1, e9
    assert any(re.search(KEY_MARK, ln) for ln in e9["lines"]), e9
    # THE CONTROL ON THE MARK, with the filter wide open: the boot line was written before
    # the mark, so a look that reached before it would carry it. `lines` is wide enough that
    # the cut cannot be what hides it (the boot line sits first, the cut keeps the last).
    assert e9["written"] <= LOOK_LINES, "raise LOOK_LINES: the cut would hide the control"
    assert not any(re.search(BOOT_MARK, ln) for ln in e9["lines"]), \
        "the look reached before the mark"


def test_the_serial_route_sends_a_verified_key_with_no_window_at_all(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE HEADLESS ROUTE, end to end: a session started with `input_port` on a conf whose
    autoexec runs the shipped stub, no window, no focus, no Accessibility grant. The stub
    announces the device answered, the cue key goes down the socket, and the program ACTS
    (its own cue line, from a mark taken before the send); the control is a key the program
    ignores, whose ARRIVAL line is seen while the cue's is not. The reply says which route
    answered, and the mouse is refused on it rather than sent nowhere."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    r = cast(dict[str, Any], server.start(
        conf=str(guest.CONF), cwd=str(guest.GUEST), seconds=180, mode="headless",
        logfile=str(tmp_path / "guest.log"), input_port=SERIAL_PORT, program=guest.PROGRAM))
    assert r["status"] == "ok", r
    assert "cpu integration device=true" in r["argv"], r["argv"]
    server.resume(until_close=True)      # headless and nothing armed: the log is the way back
    stub = cast(dict[str, Any], server.log_wait(channel="guest", pattern="STUB  . inject device=",
                                                seconds=60))
    assert stub["status"] == "ok" and "device=present" in stub["line"], stub
    _input_loop_live()
    sent = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_MARK, seconds=15))
    assert sent["status"] == "ok" and sent["route"] == "serial", sent
    assert sent["effect"]["seen"] is True and re.search(KEY_MARK, sent["effect"]["line"]), sent
    assert sent["ticks"] == 2 and "activated" not in sent, sent
    ignored = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK,
                                                    seconds=10))
    assert ignored["status"] == "ok" and ignored["effect"]["seen"] is True, ignored
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "INVALID" and "did not react" in missed["message"], missed
    mouse = cast(dict[str, Any], server.send_mouse(button="left"))
    assert mouse["status"] == "INVALID" and "KEYS only" in mouse["message"], mouse


@WINDOWED
def test_send_mouse_captures_clicks_and_moves_the_guest_pointer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE MOUSE, END TO END, as the guest sees it. The pointer is placed at the window's
    centre, the first click CAPTURES the mouse (the emulator swallows it, which the tool
    reports as a miss and nothing else), the next click ARRIVES with the guest's own
    coordinates, and a relative nudge moves the guest pointer along the axis nudged and no
    other. The focus is KEPT throughout: a captured mouse is released the moment the window
    loses it, which is what turned every click into a swallowed capture attempt before."""
    _start_windowed(tmp_path, monkeypatch)
    server.resume()
    # THE PROGRAM'S INPUT LOOP MUST BE UP before the first click, not just its boot line: a
    # capture attempted while the guest is still installing its drivers does not stick, and
    # the click that should have arrived afterwards is swallowed as a fresh capture.
    _input_loop_live()
    # THE WINDOW'S CENTRE, as the window server reports it: placing the pointer there keeps
    # the capture's re-centring warp from moving the guest's pointer.
    placed = cast(dict[str, Any], server.send_mouse(place="center"))
    assert placed["status"] == "ok" and placed["restore"] == "kept", placed
    assert placed["window"] is not None and placed["window"][2] > 0, placed
    # THE CAPTURING CLICK IS THE EMULATOR'S, not the program's, and it is reported as a miss;
    # the click the guest sees is the next one -- or the one after, when the window server
    # delivered the first before the capture took. So: click until the guest logs one,
    # within a small bound, and the miss count is part of the record rather than a failure.
    first: dict[str, Any] = {}
    misses = 0
    for _ in range(CAPTURE_CLICKS_MAX):
        first = cast(dict[str, Any], server.send_mouse(button="left", expect=MOUSE_MARK,
                                                       seconds=3))
        assert first["posted"] == 1, first
        if first["status"] == "ok":
            break
        misses += 1
    assert first["status"] == "ok" and first["effect"]["seen"] is True, (
        f"no click reached the guest in {CAPTURE_CLICKS_MAX} attempts: {first}")
    assert misses >= 1, "the capturing click was not swallowed: is autolock off in the conf?"
    gx, gy = _guest_xy(first["effect"]["line"])
    nudged = cast(dict[str, Any], server.send_mouse(dx=NUDGE_PX, dy=0))
    assert nudged["status"] == "ok" and nudged["restore"] == "kept", nudged
    second = cast(dict[str, Any], server.send_mouse(button="left", expect=MOUSE_MARK,
                                                    seconds=5))
    assert second["status"] == "ok", second
    nx, ny = _guest_xy(second["effect"]["line"])
    # X grown by a real amount (the guest's driver scales a delta as it likes, so the shape
    # is asserted and not the figure), Y within the few pixels the capture's re-centring can
    # leave, AND no axis leak: a nudge that moved Y by more than a small share of what it
    # moved X is the fight between warps and deltas this route was measured to have once.
    moved_x, moved_y = nx - gx, abs(ny - gy)
    assert moved_x >= NUDGE_MIN_MOVED and moved_y <= RECENTRE_JITTER, (
        f"a nudge along X moved the guest pointer from ({gx},{gy}) to ({nx},{ny}); the "
        f"expected shape is X grown and Y untouched")
    assert moved_y * LEAK_DENOMINATOR <= moved_x, (
        f"the nudge leaked into Y: X moved {moved_x}, Y moved {moved_y}")
    assert isinstance(ds.Launch.binary, str)       # a touch of the module, keeps the import used


def _guest_xy(line: str) -> tuple[int, int]:
    m = re.search(r"x=(\d+) y=(\d+)", line)
    assert m, f"the mouse line carries no x=/y=: {line!r}"
    return int(m.group(1)), int(m.group(2))
