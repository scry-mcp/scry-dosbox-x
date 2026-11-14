"""The DOSBox-X server: lists, drive and input."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest
from dosbox_x_server_support import (  # noqa: E402
    E9_KEY_ACT,
    NamesFake,
    _guest,
    _log_wait_as_guest,
    _names,
    _source,
    _start_on_a_booted_fake,
    clean_session,  # noqa: E402, F401
    install,
)
from scry_core import host_program
from scry_core import reply_contract as contract
from scry_core import sequence_account as account
from scry_core import steps as step_judge
from scry_core import vocabulary as vocab
from scry_core.host_program import absolute as _abs

from scry_dosbox_x import checks, inputs, machine, run_state, running, sequence, server
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import docs as dosbox_docs
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import lifecycle as dosbox_lifecycle
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def test_an_empty_name_is_a_listing_and_not_a_lookup(tmp_path: Path) -> None:
    install()
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(name=""))
    assert got["status"] == "INVALID", got


def test_a_build_that_lists_the_option_but_carries_no_debugger_is_refused(
        tmp_path: Path) -> None:
    binary = tmp_path / "dosbox-x"
    binary.write_bytes(b"\x00a build with the option and no debugger\x00")
    with mock.patch("scry_core.binaries.shutil.which", lambda _n: str(binary)):
        got = cast(dict[str, Any], server.build_check())
    assert got["status"] == "INVALID" and "carries no debugger" in str(got["message"]), got


def test_perform_runs_steps_in_order_and_stops_at_the_first_failure(
        tmp_path: Path) -> None:
    syms = [dsym.Symbol("_main", 0x1000, kind="T"),
            dsym.Symbol("dup", 0x2000, kind="t"), dsym.Symbol("dup", 0x3000, kind="t")]
    _names(tmp_path, symbols=syms)
    out = server.perform(steps=[
        {"op": "breakpoint_at", "ref": "_main"},
        {"op": "breakpoint_at", "ref": "dup"},          # ambiguous -> fails here
        {"op": "breakpoint_at", "ref": "_main"},        # must NOT run
    ])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert out["steps_completed"] == 1, out
    assert [r["op"] for r in out["ran"]] == ["breakpoint_at"], out   # only the first SUCCEEDED
    assert out["failed"]["op"] == "breakpoint_at", out               # the second is here
    assert "names 2 symbols" in out["message"], out


def test_perform_refuses_an_unknown_op(tmp_path: Path) -> None:
    """The vocabulary is the server's own op names."""
    _names(tmp_path)
    unknown = server.perform(steps=[{"op": "warp_core"}, {"op": "nope"}])
    assert unknown["status"] == "INVALID" and "not a step" in unknown["message"]
    assert unknown["operations"] == sorted(server._step_ops()), unknown
    assert "resume" in unknown["operations"] and "warp_core" not in unknown["operations"]
    assert "see `operations`" in unknown["errors"][0]["message"], unknown
    assert "resume" not in unknown["message"], "the vocabulary is in `operations`, not here"
    known = server.perform(steps=[{"op": "registers", "nope": 1}])
    assert known["status"] == "INVALID" and "operations" not in known, known
    driven = server.drive(act=[{"op": "warp_core"}])
    assert driven["operations"] == sorted(server._step_ops()), driven
    # A malformed step carries failed_at like every other failure, not a missing key.
    shapeless = server.perform(steps=["registers"])   # not an {op: ...} object
    assert shapeless["status"] == "INVALID" and "not a" in shapeless["message"]
    assert shapeless["failed_at"] == 0, shapeless
    assert "available" not in shapeless["message"], "a reason, never a dict's repr"


def test_input_reaches_a_headless_session_and_the_mouse_needs_no_log(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["route"] == "guest"
    assert cast(dict[str, Any], server.send_mouse(button="left"))["route"] == "guest"
    fake.launch = dlaunch.Launch(conf=Path(_abs("x.conf")), cwd=Path(_abs()), seconds=60,
                                 logfile=None)
    nolog = cast(dict[str, Any], server.send_mouse(button="left"))
    assert nolog["status"] == "ok" and nolog["pointer"], nolog


def test_send_keys_composes_the_scan_bytes_as_key_commands(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False)
    fake.running = True
    got = cast(dict[str, Any], server.send_keys(keys=["a", "enter"],
                                                modifiers=["ctrl", "shift"]))
    assert got["status"] == "ok" and got["keys"] == ["a", "enter"], got
    assert got["modifiers"] == ["ctrl", "shift"]
    want = bytes([0x1D, 0x2A, 0x1E, 0x9E, 0x1C, 0x9C, 0xAA, 0x9D])
    assert fake.commands_sent == [[b"K" + bytes([b]) for b in want]], fake.commands_sent
    assert (got["route"], got["posted"], got["bytes"], got["frames"]) == ("guest", 2, 8, 8)
    assert "activated" not in got and "restored" not in got and "focus" not in got, got
    empty = cast(dict[str, Any], server.send_keys(keys=[]))
    assert empty["status"] == "INVALID" and "at least one key" in empty["message"]
    astr = cast(dict[str, Any], server.send_keys(keys=cast(Any, "enter")))
    assert astr["status"] == "INVALID" and "not a string" in astr["message"]
    assert len(fake.commands_sent) == 1, "a refused call must not have sent anything"


def test_a_held_key_is_sent_as_its_makes_and_released_as_its_breaks(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False)
    fake.running = True
    down = cast(dict[str, Any], server.send_keys(keys=["right"], modifiers=["shift"],
                                                 action="down"))
    assert down["status"] == "ok" and down["bytes"] == 3, down
    up = cast(dict[str, Any], server.send_keys(keys=["right"], modifiers=["shift"], action="up"))
    assert up["status"] == "ok", up
    sent = [list(batch) for batch in fake.commands_sent]
    assert sent == [[b"K\x2A", b"K\xE0", b"K\x4D"], [b"K\xE0", b"K\xCD", b"K\xAA"]], sent
    bad = cast(dict[str, Any], server.send_keys(keys=["a"], action="hold"))
    assert bad["status"] == "INVALID", bad


def test_send_mouse_moves_presses_and_reads_the_pointer_back(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.video_mode, fake.mouse_max = 0x13, (639, 199)
    moved = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert moved["status"] == "ok" and moved["route"] == "guest", moved
    # 320 x 200 pixels over a 640 x 200 driver range: x doubles to the middle of its
    # two coordinates, y stays.
    assert fake.commands_sent == [[b"R"], [b"M" + (201).to_bytes(2, "little")
                                          + (50).to_bytes(2, "little")], [b"R"]]
    assert moved["driver_arrived"] is True and "asked" not in moved
    assert moved["pointer"]["screen"] == {"x": 100, "y": 50, "width": 320, "height": 200}
    assert moved["pointer"]["mouse"] == {"x": 201, "y": 50, "max_x": 639, "max_y": 199}
    assert moved["pointer"]["bios_mode"] == "0x13" and moved["pointer"]["buttons"] == []
    fake.commands_sent.clear()
    both = cast(dict[str, Any], server.send_mouse(x=0, y=0, button="right"))
    assert fake.commands_sent[1] == [b"M\x01\x00\x00\x00", b"B\x81", b"B\x01"], fake.commands_sent
    assert both["button"] == "right" and both["action"] == "click"
    fake.commands_sent.clear()
    held = cast(dict[str, Any], server.send_mouse(button="left", action="down"))
    assert fake.commands_sent[1] == [b"B\x80"] and held["pointer"]["buttons"] == ["left"]
    server.send_mouse(button="left", action="up")
    assert fake.commands_sent[-2] == [b"B\x00"] and fake.buttons == 0
    server.send_mouse(button="middle", action="double")
    assert fake.commands_sent[-2] == [b"B\x82", b"B\x02", b"B\x82", b"B\x02"]
    server.send_mouse(button="left", action="triple")
    assert fake.commands_sent[-2] == [b"B\x80", b"B\x00"] * 3
    raw = cast(dict[str, Any], server.send_mouse(x=639, y=199, units="mouse"))
    assert raw["status"] == "ok" and raw["pointer"]["mouse"]["x"] == 639, raw
    assert raw["pointer"]["screen"]["x"] == 319


def test_an_action_with_no_button_presses_the_left_one_and_a_bare_move_presses_none(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.video_mode, fake.mouse_max = 0x13, (639, 199)
    bare = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert [c for c in fake.commands_sent if c and c[0][:1] == b"B"] == [], fake.commands_sent
    assert "button" not in bare, bare
    fake.commands_sent.clear()
    clicked = cast(dict[str, Any], server.send_mouse(x=100, y=50, action="click"))
    assert fake.commands_sent[1] == [b"M" + (201).to_bytes(2, "little")
                                     + (50).to_bytes(2, "little"), b"B\x80", b"B\x00"], \
        fake.commands_sent
    assert clicked["button"] == "left" and clicked["action"] == "click", clicked
    assert "no button pressed" not in clicked["summary"], clicked["summary"]
    fake.commands_sent.clear()
    server.send_mouse(button="right")                  # a button alone clicks it, as ever
    assert fake.commands_sent[1] == [b"B\x81", b"B\x01"], fake.commands_sent


def test_a_screen_move_no_program_pointer_judged_is_the_drivers_word_only(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.video_mode, fake.mouse_max = 0x13, (639, 199)
    unjudged = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert unjudged["driver_arrived"] is True and "arrived" not in unjudged, unjudged
    assert "program's own pointer not read" in unjudged["summary"], unjudged["summary"]
    driver = cast(dict[str, Any], server.send_mouse(x=100, y=50, units="mouse"))
    assert driver["arrived"] is True and "driver_arrived" not in driver, driver


def test_a_move_the_driver_placed_elsewhere_is_said_never_rounded_away(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.pointer_snaps = 8
    exact = cast(dict[str, Any], server.send_mouse(x=10, y=3))         # cell (10, 3)
    assert exact["driver_arrived"] is True and exact["pointer"]["screen"]["x"] == 10, exact
    off = cast(dict[str, Any], server.send_mouse(x=21, y=3, units="mouse"))
    assert off["status"] == "ok" and off["arrived"] is False, off
    assert off["asked"] == {"x": 21, "y": 3} and off["pointer"]["mouse"]["x"] == 16, off
    fake.pointer_snaps = 16                                             # cell 11 snaps into 10
    missed = cast(dict[str, Any], server.send_mouse(x=11, y=3))
    assert missed["driver_arrived"] is False and missed["pointer"]["screen"]["x"] == 10, missed
    assert missed["asked"] == {"x": 92, "y": 28}, missed


def test_a_program_s_own_range_is_landed_on_through_the_tool(tmp_path: Path) -> None:
    """Deluxe Paint's 0..2552 x 0..1592 in mode 13h, x kept even by the driver."""
    fake = _guest(tmp_path)
    fake.video_mode, fake.mouse_max, fake.pointer_snaps = 0x13, (2552, 1592), 2
    got = cast(dict[str, Any], server.send_mouse(x=40, y=60))
    assert got["driver_arrived"] is True and got["pointer"]["screen"]["x"] == 40, got
    assert (got["pointer"]["mouse"]["x"] // 8, got["pointer"]["mouse"]["y"] // 8) == (40, 60), got


def test_send_mouse_refuses_before_anything_is_sent(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    cases: list[tuple[Callable[[], dict[str, Any]], str]] = [
        (lambda: server.send_mouse(), "name a move"),
        (lambda: server.send_mouse(x=1), "BOTH `x` and `y`"),
        (lambda: server.send_mouse(x=cast(Any, 1.5), y=0), "whole number"),
        (lambda: server.send_mouse(x=cast(Any, True), y=0), "whole number"),
        (lambda: server.send_mouse(x=-1, y=0), "whole number"),
        (lambda: server.send_mouse(x=inputs.MAX_COORD + 1, y=0, units="mouse"), "to 32767"),
        (lambda: server.send_mouse(x=0, y=2**31, units="mouse"), "to 32767"),
        (lambda: server.send_mouse(button="wheel"), "button is one of"),
        (lambda: server.send_mouse(button="left", action="swipe"), "action is one of"),
        (lambda: server.send_mouse(x=1, y=1, units="pixels"), "units is one of"),
    ]
    for call, words in cases:
        got = call()
        assert got["status"] == "INVALID" and words in got["message"], (words, got)
    assert fake.commands_sent == [], "a refused call must not have sent anything"
    # the screen's own bounds, read from the stub: refused after the report, before the move
    off = cast(dict[str, Any], server.send_mouse(x=80, y=0))            # text 80 x 25
    assert off["status"] == "INVALID" and "outside the screen, 80 x 25" in off["message"], off
    raw = cast(dict[str, Any], server.send_mouse(x=640, y=0, units="mouse"))
    assert raw["status"] == "INVALID" and "outside the driver's range" in raw["message"], raw
    fake.video_mode = 0x101                                            # a VESA mode
    vesa = cast(dict[str, Any], server.send_mouse(x=1, y=1))
    assert vesa["status"] == "INVALID" and "units='mouse'" in vesa["message"], vesa
    assert all(cmds == [b"R"] for cmds in fake.commands_sent), fake.commands_sent
    ok = cast(dict[str, Any], server.send_mouse(x=1, y=1, units="mouse"))
    assert ok["status"] == "ok" and ok["pointer"]["screen"]["available"] is False, ok
    # THE TOP of the argument passes it and meets the driver's own range instead.
    top = cast(dict[str, Any], server.send_mouse(x=inputs.MAX_COORD, y=0, units="mouse"))
    assert "outside the driver's range" in top["message"], top


def test_a_stub_that_never_reports_is_named_and_a_malformed_report_refused(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.reports_lost = {1}
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert "no acknowledgement" in got["message"], got
    with pytest.raises(ds.Invalid, match="not in its shape"):
        inputs.parse_report("STUB  . mouse x=1 y=2")


def test_the_stub_must_have_announced_its_protocol_before_anything_is_sent(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.stub_protocol = ""
    fake.log = ["Bochs port E9h: BOOT  . start"]
    none = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert none["status"] == "INVALID" and "SCRY.COM" in none["message"], none
    fake.log.append("Bochs port E9h: STUB  . scry device=absent")
    absent = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert "integration device=true" in absent["message"], absent
    fake.log.append("Bochs port E9h: STUB  . scry device=present")
    old = cast(dict[str, Any], server.send_mouse(button="left"))
    assert "protocol none" in old["message"] and "another stub" in old["message"], old
    assert fake.commands_sent == []
    fake.log.append("Bochs port E9h: STUB  . scry device=present proto=2")
    stale = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert "protocol 2" in stale["message"] and fake.commands_sent == [], stale
    fake.log.append(f"Bochs port E9h: STUB  . scry device=present proto={inputs.STUB_PROTOCOL}")
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["status"] == "ok"
    assert fake.stub_protocol == inputs.STUB_PROTOCOL
    fake.log.clear()
    assert cast(dict[str, Any], server.send_keys(keys=["a"]))["status"] == "ok"


def test_send_keys_with_an_expectation_confirms_the_guest_reacted(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    fake.input_effect = E9_KEY_ACT
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=5))
    assert got["status"] == "ok" and got["posted"] == 1, got
    # `seen_before_waiting`, not `already`: the reaction was written AFTER the post (the
    # fake appends it on send) and was there when the wait first looked from the mark, and
    # `lines_before` says nothing sat between the mark and it.
    assert got["verify"] == {"checked": True, "seen": True, "expected": "key_cue_a",
                             "verdict": "TARGET", "line": E9_KEY_ACT,
                             "seen_before_waiting": True, "lines_before": 0, "waited_s": 0.0,
                             "lines_total": 1}, got["verify"]
    assert "already" not in got["verify"] and "effect" not in got
    # the mark is 1 line, taken before the post
    assert fake.wait_calls == [(inputs.program_reaction("key_cue_a"), 5, 1)], fake.wait_calls
    # THE DEFAULT BOUND is a named constant, passed through when `seconds` is omitted.
    server.send_keys(keys=["a"], expect="key_cue_a")
    assert fake.wait_calls[-1][1] == inputs.EFFECT_WAIT_DEFAULT_S


def test_send_keys_reports_a_swallowed_key_as_a_miss_not_a_success(tmp_path: Path) -> None:
    """THE FALSE SUCCESS THIS EXISTS TO REFUSE."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start", E9_KEY_ACT]   # a STALE match
    fake.input_effect = None                                              # the guest is silent
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=2))
    assert got["status"] == "ok" and got["verify"]["verdict"] == "TIMEOUT", got
    assert "miss on the pattern" in got["verify"]["note"], got["verify"]
    assert got["posted"] == 1 and got["route"] == "guest", got     # the post is still reported
    assert got["verify"]["checked"] is True and got["verify"]["seen"] is False, got["verify"]
    # from PAST the stale line
    assert fake.wait_calls == [(inputs.program_reaction("key_cue_a"), 2, 2)], fake.wait_calls
    assert fake.scancodes_sent == [bytes([0x1E, 0x9E])]


def test_send_keys_an_instrument_that_broke_is_not_reported_as_a_miss(
        tmp_path: Path) -> None:
    """ONLY AN EXPIRED BOUND IS A MISS."""
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.wait_raises = ds.Invalid("session_broken", "the emulator is GONE, 0.2s into a 10.0s wait")
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert got["status"] == "INVALID" and got["posted"] == 1, got
    assert got["verify"] == {"checked": False, "expected": "key_cue_a",
                             "why": "the emulator is GONE, 0.2s into a 10.0s wait"}, got
    assert "could NOT be verified" in got["message"] and "GONE" in got["message"], got["message"]
    assert "miss on the pattern" not in got["message"], got["message"]


def test_send_keys_without_an_expectation_says_it_did_not_verify(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "ok" and got["posted"] == 1, got
    assert got["verify"]["checked"] is False and "expect" in got["verify"]["why"], got
    assert fake.wait_calls == []
    orphan = cast(dict[str, Any], server.send_keys(keys=["a"], seconds=5))
    assert orphan["status"] == "INVALID" and "silently ignored" in orphan["message"], orphan
    assert len(fake.commands_sent) == 1, "the refused call must not have posted"


def test_send_keys_expectation_that_cannot_be_checked_is_refused_before_the_post(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.log = None                                   # a session with no logfile
    nolog = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert nolog["status"] == "INVALID" and "logfile" in nolog["message"], nolog
    fake.log = []
    badrx = cast(dict[str, Any], server.send_keys(keys=["a"], expect="(unclosed"))
    assert badrx["status"] == "INVALID" and "pattern" in badrx["message"].lower(), badrx
    nobound = cast(dict[str, Any], server.send_keys(keys=["a"], expect="x", seconds=0))
    assert nobound["status"] == "INVALID" and "bound" in nobound["message"], nobound
    # UNTYPED VALUES, as a perform step delivers them: a TypeError out of the comparison or
    # the regex compiler is a traceback the tool wrapper does not translate.
    astr = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": "x", "seconds": "3"}]))
    assert astr["status"] == "INVALID" and "is a number" in astr["message"], astr
    nonstr = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": 5}]))
    assert nonstr["status"] == "INVALID" and "expect is a string" in nonstr["message"], nonstr
    assert fake.commands_sent == [], "a refused verification must not have posted anything"
    empty = cast(dict[str, Any], server.send_keys(keys=["a"], expect=""))
    assert empty["status"] == "ok" and "unverified" in empty["summary"], "empty is not given"


def test_send_mouse_takes_the_same_expectation(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.input_effect = "Bochs port E9h: [+   1.000] UI    . ask via CLICK on button 0"
    hit = cast(dict[str, Any], server.send_mouse(button="left", expect="via CLICK"))
    assert hit["status"] == "ok" and hit["verify"]["seen"] is True, hit
    moved = cast(dict[str, Any], server.send_mouse(x=10, y=20, expect="via CLICK"))
    assert moved["status"] == "ok" and moved["verify"]["seen"] is True, moved
    assert fake.commands_sent[-2] == [b"M" + (84).to_bytes(2, "little")
                                      + (164).to_bytes(2, "little")]
    fake.input_effect = None
    miss = cast(dict[str, Any], server.send_mouse(button="left", expect="via CLICK",
                                                  seconds=1))
    assert miss["status"] == "ok" and miss["verify"]["verdict"] == "TIMEOUT", miss
    assert miss["pointer"]["mouse"]["x"] == 84 and miss["route"] == "guest", miss


def test_perform_stops_at_a_send_keys_step_whose_expectation_missed(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["a"], "expect": "key_cue_a", "seconds": 1},
        {"op": "status"}]))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 1 and "step 1 ('send_keys')" in out["note"], out
    assert out["ran"][0]["reply"]["posted"] == 1, out["ran"][0]
    # the missed step's own words are in the list's note, not only in `ran`
    assert "its own reply: send_keys (guest): effect not seen (TIMEOUT)" in out["note"], out
    assert "the guest wrote no line in the 1 s waited" in out["note"], out
    assert "status" not in [r["op"] for r in out["ran"]], "the steps after it were not sent"


def test_scan_sequence_composes_set1_makes_and_breaks_in_order() -> None:
    assert inputs.scan_sequence(["a"], "-") == bytes([0x1E, 0x9E])
    assert inputs.scan_sequence(["a", "enter"], "-") == bytes([0x1E, 0x9E, 0x1C, 0x9C])
    assert inputs.scan_sequence(["a"], "shift") == bytes([0x2A, 0x1E, 0x9E, 0xAA])
    assert inputs.scan_sequence(["up"], "ctrl+alt") == bytes(
        [0x1D, 0x38, 0xE0, 0x48, 0xE0, 0xC8, 0xB8, 0x9D])
    assert inputs.scan_sequence(["F11"], "-") == bytes([0x57, 0xD7])   # names are case-free
    assert inputs.scan_sequence(["a"], "shift", "down") == bytes([0x2A, 0x1E])
    assert inputs.scan_sequence(["a"], "shift", "up") == bytes([0x9E, 0xAA])
    assert inputs.scan_sequence(["up"], "-", "down") == bytes([0xE0, 0x48])
    assert inputs.scan_sequence(["up"], "-", "up") == bytes([0xE0, 0xC8])
    # A modifier held on its own, as a key, keeps a program from going idle.
    assert inputs.scan_sequence(["Shift"], "-", "down") == bytes([0x2A])
    assert inputs.scan_sequence(["shift"], "-", "up") == bytes([0xAA])
    assert inputs.scan_sequence(["ctrl", "alt"], "-", "down") == bytes([0x1D, 0x38])
    with pytest.raises(ds.Invalid, match="unknown key name"):
        inputs.scan_sequence(["a", "bogus"], "-")
    with pytest.raises(ds.Invalid, match="no command key"):
        inputs.scan_sequence(["a"], "cmd")


def test_send_keys_refuses_the_cap_and_a_miss_blames_no_window(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False)
    fake.running = True
    fake.input_effect = E9_KEY_ACT
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a"))
    assert got["status"] == "ok" and got["verify"]["seen"] is True, got
    shifted = cast(dict[str, Any], server.send_keys(keys=["b"], modifiers=["shift"]))
    assert fake.scancodes_sent[-1] == bytes([0x2A, 0x30, 0xB0, 0xAA]) and shifted["frames"] == 4
    capped = cast(dict[str, Any], server.send_keys(keys=["a"] * 65))
    assert capped["status"] == "INVALID" and "at most 64" in capped["message"], capped
    assert len(fake.scancodes_sent) == 2
    fake.input_effect = None
    miss = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=1))
    assert miss["verify"]["verdict"] == "TIMEOUT", miss
    assert "focus" not in miss["verify"]["note"], miss["verify"]["note"]


def test_drive_marks_acts_verifies_and_looks_from_the_mark(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.where_raises = True              # a RUNNING guest, as this key is sent to
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start", E9_KEY_ACT]   # a STALE cue
    fake.input_effect = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1 b=-1 on=1"
    asked: list[bool] = []
    where = fake.where

    def counted() -> Any:
        asked.append(True)
        return where()
    fake.where = counted  # type: ignore[method-assign]
    out = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect="key_cue_a", seconds=7,
        pattern="ACT", limit=10))
    assert out["status"] == "ok", out
    assert asked == [], "whether the guest runs is the session's flag, never a console command"
    act = out["act"]
    assert act["steps_completed"] == 1 and act["failed_at"]["available"] is False, act
    assert out["verify"]["seen"] is True and "on=1" in out["verify"]["line"], out["verify"]
    # from the mark
    assert fake.wait_calls[-1] == (inputs.program_reaction("key_cue_a"), 7.0, 2), fake.wait_calls
    e9 = out["looked"]["guest"]
    assert e9["available"] is True and e9["since_mark"] == 2, e9
    assert e9["lines_written"] == e9["lines_total"] == 1, e9
    assert e9["lines"] == [fake.input_effect], e9
    # THE CUT, THE FILTER AND THE COUNTS, each pinned by a fixture that separates them:
    # three lines land after the mark, one of which does not match `pattern`; `limit=1`
    # keeps the LAST matching one, `written` counts all three, `lines_total` the two.
    fake.log = [f"Bochs port E9h: [+   {i}.000] PERF  . tick={i}" for i in range(6)]
    mark_before = len(fake.log)
    fake.input_effect = "Bochs port E9h: [+   7.000] PERF  . tick=7"
    fake.after_effect = ["Bochs port E9h: [+   7.100] VU    . ball play=0",
                         "Bochs port E9h: [+   7.200] PERF  . tick=8"]
    out = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["b"]}],
                                             pattern="tick", limit=1))
    e9 = out["looked"]["guest"]
    assert e9["since_mark"] == mark_before, e9
    assert (e9["lines_written"], e9["lines_total"], len(e9["lines"])) == (3, 2, 1), e9
    assert e9["lines"] == [fake.after_effect[1]] and e9["pattern"] == "tick", e9
    assert out["verify"]["checked"] is False and "no `expect`" in out["verify"]["why"]
    assert "failed" not in out["act"], out["act"]


def test_drive_reports_a_miss_a_failed_act_and_refuses_what_it_cannot_do(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                      # the input goes to a RUNNING guest here
    fake.where_raises = True              # a RUNNING guest, as this key is sent to
    fake.input_effect = None
    miss = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                              expect="key_cue_a", seconds=1))
    assert miss["status"] == "ok" and miss["verify"]["verdict"] == "TIMEOUT", miss
    assert miss["act"]["steps_completed"] == 1 and miss["verify"]["seen"] is False, miss
    assert miss["looked"]["guest"]["lines_written"] == 0
    cut = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"], "expect": "never", "seconds": 1},
             {"op": "status"}], expect="key_cue_a"))
    assert cut["status"] == "ok" and cut["act"]["verdict"] == "TIMEOUT", cut
    assert cut["act"]["steps_completed"] == 1 and cut["verify"]["available"] is False, cut
    assert len(fake.wait_calls) == 2, "the overall expect must not be waited for after a cut act"
    # EVERY REFUSAL COMES BEFORE THE ACT MOVES ANYTHING: each of these carries a step that
    # would post a key, and none of them posts. An unknown op among the steps is refused up
    # front too, where `perform` would have run the steps before it.
    posted, waited = len(fake.commands_sent), len(fake.wait_calls)
    key = {"op": "send_keys", "keys": ["a"]}
    refusals: list[Callable[[], dict[str, Any]]] = [
        lambda: server.drive(act=[]),
        lambda: server.drive(act=[key], pattern="("),
        lambda: server.drive(act=[key], limit=0),
        lambda: server.drive(act=[key], seconds=3),
        lambda: server.drive(act=[key], settle_seconds=-1),   # 0 never waits; below is no bound
        lambda: server.drive(act=[key, {"op": "warp_core"}]),
        lambda: server.drive(act=[key, "not a step"])]
    for refusal in refusals:
        got = refusal()
        assert got["status"] == "INVALID", got
        # ONE SHAPE, whichever check refused it: the act's account, a verify and a look.
        assert {"act", "verify", "looked"} <= set(got) and "errors" not in got, got
        assert got["act"]["steps_completed"] == 0, got
    fake.log = None
    nolog = cast(dict[str, Any], server.drive(act=[key]))
    assert nolog["status"] == "INVALID" and "logfile" in nolog["message"]
    assert {"act", "verify", "looked"} <= set(nolog), nolog
    assert (len(fake.commands_sent), len(fake.wait_calls)) == (posted, waited), (
        "a refused drive must not have acted or waited")
    # `perform` refuses the same non-bound `wait`.
    assert cast(dict[str, Any], server.perform(steps=[{"op": "status"}],
                                               settle_seconds=-1))["status"] \
        == "INVALID"
    # AN EMPTY `expect` IS NO EXPECT, as everywhere an optional text is empty: the act runs and
    # nothing is verified, which the reply says.
    fake.log = []
    unchecked = cast(dict[str, Any], server.drive(act=[key], expect=""))
    assert unchecked["status"] == "ok" and unchecked["verify"]["checked"] is False, unchecked


def test_drive_carries_the_verify_refusals_own_code_when_the_instrument_broke(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.where_raises = True
    fake.input_effect = None
    fake.wait_raises = ds.Invalid("session_broken", "the emulator is GONE, 0.2s into a 1s wait")
    out = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                             expect="key_cue_a", seconds=1))
    assert out["status"] == "INVALID" and out["code"] == "session_broken", out
    assert "could NOT be verified" in out["message"] and "GONE" in out["message"], out
    assert out["verify"]["checked"] is False and out["verify"]["code"] == "session_broken"


def test_drive_verifies_a_stopped_guest_with_one_read_and_no_wait(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.halted = True                    # a resume that halts at once: the act ends stopped
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    miss = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], expect="key_cue_a",
                                              seconds=5))
    assert miss["status"] == "INVALID" and miss["verify"]["seen"] is False, miss
    assert "STOPPED at the debugger" in miss["verify"]["why"], miss["verify"]
    assert fake.wait_calls == [], "a stopped guest is read, not waited for"
    # the line the guest wrote BEFORE stopping (during the act) is the verification.
    fake.resume_effect = [E9_KEY_ACT]
    seen = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], expect="key_cue_a"))
    assert seen["status"] == "ok" and seen["verify"]["seen"] is True, seen
    assert seen["verify"]["waited_s"] == 0.0 and fake.wait_calls == []


def test_drive_takes_the_act_s_own_ending_over_the_session_flag(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, watched=True)
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]

    def ended(how: str) -> Any:
        account = {"status": "ok", "ran": [], "steps_completed": 1,
                   how: True if how == "still_running" else {"stop_seq": 2}}
        return lambda *_a, **_k: account
    for how, flag_running, waits in (("still_running", False, 1), ("stopped", True, 0)):
        fake.running = flag_running
        fake.wait_calls.clear()
        monkeypatch.setattr(sequence, "run_steps", ended(how))
        server.drive(act=[{"op": "status"}], expect="key_cue_a", seconds=1)
        assert len(fake.wait_calls) == waits, (how, fake.wait_calls)


def test_perform_a_running_ok_step_leaves_the_machine_as_it_found_it(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.input_effect = E9_KEY_ACT
    fake.halted = False              # the resume leaves the machine running...
    server.breakpoint_at(ref="00A7:0100")   # R1 ARMS before it resumes: the stop is coming
    fake.where_refusals = 2          # ...and it stops after two polls of the tail
    # THE RESUME LETS IT RUN, and only the resume: the machine is at rest until the F5, which
    # `resume` itself checks, and away from the debugger from then on.
    released: list[bool] = []
    real_resume = fake.resume

    def resume_and_run(**kw: Any) -> dict[str, object]:
        released.append(True)
        return real_resume(**kw)

    fake.resume = resume_and_run  # type: ignore[method-assign, assignment]
    fake.at_debugger = lambda: not released  # type: ignore[method-assign]
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "resume"},
        {"op": "send_keys", "keys": ["a"], "expect": "key_cue_a"},
        {"op": "status"}], settle_seconds=5.0))
    assert out["status"] == "ok" and out["steps_completed"] == 3, out
    assert out["ran"][1]["reply"]["verify"]["seen"] is True, out["ran"][1]
    assert "stopped" in out and "regs" in out["stopped"], out
    # the boundary half: a console op after a running-OK op still waits, and says so.
    fake.where_refusals = 0
    fake.where_raises = True
    fake.registers_raises = True
    released.clear()                  # at rest again for the next list's resume
    held = cast(dict[str, Any], server.perform(steps=[
        {"op": "resume"}, {"op": "status"}, {"op": "registers"}], settle_seconds=0.5))
    assert held["status"] == "ok" and held["verdict"] == "TIMEOUT", held
    assert held["steps_completed"] == 2 and "still running" in held["note"], held


def test_perform_waits_for_a_stop_before_a_console_step_after_a_resume(
        tmp_path: Path) -> None:
    """A `resume` that leaves the machine running ends the console-driven part."""
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_raises = True            # ...and the running machine refuses where()
    # a running-OK op after resume is fine (it does not touch the console)
    ok = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0.5)
    assert ok["status"] == "ok", ok
    # a console op after resume, with the machine never stopping, ends the list
    blocked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0.5)
    assert blocked["status"] == "ok" and blocked["verdict"] == "TIMEOUT", blocked
    assert "still running" in blocked["note"] and blocked["steps_completed"] == 1, blocked
    unasked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0)
    assert unasked["status"] == "INVALID" and unasked["code"] == "not_stopped", unasked
    assert unasked["failed_at"] == 1, unasked


def test_perform_tail_waits_for_the_stop_and_returns_the_enriched_reply(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_refusals = 2             # ...then the machine stops (a breakpoint fires)
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=2.0)
    assert out["status"] == "ok", out
    assert "stopped" in out and "base" not in out["stopped"], out
    stop = out["stopped"]
    assert "regs" in stop and "watches" in stop and "cause" in stop, stop


def test_perform_tail_says_so_if_the_machine_never_stops(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True            # never stops
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=0.5)
    assert out["status"] == "ok", out
    assert out["verdict"] == "TIMEOUT" and "did not stop" in out["note"], out
    assert "still_running" not in out, "no boolean restates the verdict"


def test_perform_console_step_after_resume_runs_once_the_machine_stops(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves it running
    fake.where_refusals = 2             # ...then the machine stops
    out = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=2.0)
    assert out["status"] == "ok", out
    assert [r["op"] for r in out["ran"]] == ["resume", "registers"], out


def test_perform_after_a_run_to_that_timed_out_needs_no_tail(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.runto_running = True           # run_to bound expired: interrupted, stopped
    fake.control_hits = 1          # the control fired: the TIMEOUT is a measurement
    out = server.perform(steps=[{"op": "run_to", "ref": "0000:0000", "control": "0000:0020"},
                                {"op": "registers"}], settle_seconds=2.0)
    assert out["status"] == "ok" and out["steps_completed"] == 2, out
    assert "stopped" not in out and "still_running" not in out, out


def test_perform_reports_a_gone_emulator_as_gone_not_still_running(
        tmp_path: Path) -> None:
    # TAIL: resume leaves running, the emulator dies during the run, the wait finds it gone.
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True
    fake.dies_on_resume = True          # alive when perform starts, dead after the resume
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=0.5)
    assert out["status"] == "INVALID" and out["code"] == "session_broken", out
    assert "GONE" in out["message"], out
    # BOUNDARY: a console op after a running step, emulator gone -> refused naming GONE.
    fake2 = _names(tmp_path)
    fake2.halted = False
    fake2.where_raises = True
    fake2.dies_on_resume = True
    blocked = server.perform(steps=[{"op": "resume"}, {"op": "registers"}], settle_seconds=0.5)
    assert blocked["status"] == "INVALID" and "GONE" in blocked["message"], blocked


def test_perform_a_deep_type_error_in_a_tool_is_not_masked_as_bad_arguments(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _names(tmp_path)
    # a real bad-argument name is still reported as such (bound before dispatch)
    bad = server.perform(steps=[{"op": "registers", "nope": 1}])
    assert bad["status"] == "INVALID" and "bad arguments" in bad["message"], bad
    # a TypeError from inside the tool body escapes rather than being masked
    monkeypatch.setattr(server, "registers", lambda: (_ for _ in ()).throw(TypeError("boom")))
    with pytest.raises(TypeError, match="boom"):
        server.perform(steps=[{"op": "registers"}])


def test_perform_tail_keeps_the_account_when_the_final_enrichment_refuses(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False                 # resume leaves running
    fake.where_refusals = 1             # the wait succeeds on the next poll
    fake.registers_raises = True        # _stop_reply reads registers and it refuses (cut pane)
    out = server.perform(steps=[{"op": "resume"}], settle_seconds=2.0)
    assert out["status"] == "ok", out   # the sequence account survives
    assert out["steps_completed"] == 1 and [r["op"] for r in out["ran"]] == ["resume"], out
    assert out["stopped"]["enrichment"]["available"] is False, out


def test_start_with_a_plan_runs_it_on_the_fresh_session_and_folds_the_boot_in(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")

    class Booted(NamesFake):
        argv = ["dosbox-x", "-conf", "g.conf"]
        def wait_ready(self, timeout: float = 30.0, progress: Any = None) -> float:
            return 0.5

    made: list[Booted] = []
    def build(_l: object) -> Booted:
        b = Booted(conf=conf)
        made.append(b)
        return b

    with mock.patch("scry_dosbox_x.server.ds.Session", build):
        out = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30,
            plan=[{"op": "registers"}]))
    assert out["status"] == "ok", out
    assert [r["op"] for r in out["ran"]] == ["registers"], out
    # THE BOOT IS FOLDED IN under `start`, stripped of status/session.
    assert out["start"].get("shared", False) is False and "argv" in out["start"], out
    assert "status" not in out["start"] and "session" not in out["start"], out

    # A plan that FAILS AT A STEP leaves the session OPEN (start does not close it): a symbol
    # watch with no size passes the list's check and is refused by its step. Clear the
    # session the first start installed, or this start refuses "already live" before the plan.
    dstate.STATE.session = None
    with mock.patch("scry_dosbox_x.server.ds.Session", build):
        failed = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30,
            plan=[{"op": "watch_add", "ref": "no_such", "mode": "show"}]))
    assert failed["status"] == "INVALID" and failed["failed_at"] == 0, failed
    # annotated `object` so mypy does not narrow `dstate.STATE.session` here and then call the
    # reassignment below unreachable (ruff rewrites getattr, so the annotation is the seam).
    still_open: object = dstate.STATE.session
    assert still_open is not None, "a failed plan closed the session"
    # AND no plan short-circuits to the plain boot reply.
    dstate.STATE.session = None
    with mock.patch("scry_dosbox_x.server.ds.Session", build):
        plain = cast(dict[str, Any], server.start(
            conf=str(conf), cwd=str(tmp_path), session_seconds=30))
    assert plain["status"] == "ok" and "ran" not in plain and "start" not in plain, plain


def test_perform_bad_arguments_for_a_step_are_reported_not_crashed(tmp_path: Path) -> None:
    _names(tmp_path)
    out = server.perform(steps=[{"op": "registers", "bogus": 1}])
    assert out["status"] == "INVALID" and "bad arguments" in out["message"], out


def test_start_with_a_plan_runs_it_on_the_fresh_session(tmp_path: Path) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    dstate.STATE.store = dec.DeclarationStore(str(conf), path=tmp_path / "decl.json")
    fake = NamesFake(conf=conf)
    dstate.STATE.session = fake  # type: ignore[assignment]
    # exercise the executor path start(plan=) uses, without re-booting: call _run_steps the
    # way start does, then assert the fold-in shape start applies.
    ran = sequence.run_steps(fake, [{"op": "registers"}], 1.0, server._step_ops())  # type: ignore[arg-type]
    assert ran["status"] == "ok" and ran["steps_completed"] == 1
    assert ran["ran"][0]["op"] == "registers"


@pytest.mark.skipif(sys.platform == "win32", reason="`-version` is not run on Windows")
def test_start_from_the_path_with_a_plan_says_which_build_under_start(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    on_path = host_program.write(tmp_path / "bin" / "dosbox-x", "import sys\n"
                                 "sys.stderr.write('DOSBox-X version path\\n')\nsys.exit(1)\n")
    monkeypatch.setenv("PATH", str(on_path.parent))
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, plan=[{"op": "status"}], settle_seconds=0,
                                  which=False)
    assert got["status"] == "ok", got
    assert (os.path.normcase(got["start"]["binary"]), got["start"]["binary_origin"],
            got["start"]["version"]) == (os.path.normcase(on_path), "PATH",
                                         "DOSBox-X version path"), got


def test_start_with_a_plan_keeps_session_as_the_last_key(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, plan=[{"op": "status"}], settle_seconds=0)
    assert got["status"] == "ok" and "start" in got, got
    assert list(got)[-1] == "session", f"the reply ends in {list(got)[-1]!r}, not `session`"


def test_step_and_run_to_enrich_a_stop_but_not_a_still_running_machine(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    stopped_step = cast(dict[str, Any], server.step(mode="over"))
    assert "regs" in stopped_step and "e9" in stopped_step
    fake.step_running = True
    ran = cast(dict[str, Any], server.step(mode="over"))
    assert ran["session"]["running"] is True and "running" not in ran, ran
    assert "regs" not in ran and "e9" not in ran and "pc" not in ran, ran
    fake.step_running, fake.running = False, False           # stopped again for the run
    stopped_run = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020"))
    assert stopped_run["verdict"] == "TARGET" and "watches" in stopped_run
    fake.runto_running, fake.control_hits = True, 1
    timed = cast(dict[str, Any], server.run_to(ref="0000:0010", control="0000:0020"))
    assert timed["verdict"] == "TIMEOUT" and "watches" in timed


def test_a_stop_a_sequence_found_moves_the_mark_its_block_starts_from(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.log = ["L1", "L2"]
    dstate.STATE.e9_offset = 0
    dstate.STATE.remember_stop(cast(ds.Session, fake), {"cs": "F000", "eip": "0000FFF0",
                                                        "mode": "Real"}, {}, [],
                               {"attributed": False})
    dstate.STATE.last_stop["picture"] = {}
    found = running.recorded_stop_reply(fake, {})  # type: ignore[arg-type]
    assert found["e9"]["lines"] == ["L1", "L2"] and found["e9"]["mark"] == 0, found["e9"]
    assert fake.log is not None
    fake.log += ["L3"]
    nxt = running.e9_block(fake)  # type: ignore[arg-type]
    assert nxt["lines"] == ["L3"] and nxt["mark"] > 0, nxt


def test_a_listed_row_carries_its_age_from_the_servers_clock_and_whose_it_is(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    then = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(dstate, "utc_now", lambda: then)
    _names(tmp_path)
    server.breakpoint_at(ref="_main")
    monkeypatch.setattr(dstate, "utc_now", lambda: then + timedelta(seconds=90))
    row = server.declaration_list("breakpoint")["breakpoints"][0]
    assert (row["ref"], row["age_s"], row["inherited"]) == ("_main", 90, False), row
    assert row["created_at"] == then.isoformat(timespec="seconds"), row


def test_a_stored_address_the_parser_refuses_is_listed_and_clearable(tmp_path: Path) -> None:
    _names(tmp_path)
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "0x1234"))  # type: ignore[union-attr]
    rows = server.declaration_list("breakpoint")["breakpoints"]
    assert rows[0]["state"] == "unarmable" and "cannot be read" in rows[0]["why"], rows
    assert server.declaration_clear("breakpoint", ref="0x1234")["declarations_cleared"] == 1


# ------------------------------- no wait at the end for a running-guest tail

def test_perform_does_not_wait_for_a_stop_when_the_last_step_was_a_running_guest_op(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True            # never stops
    # A RELEASE THE DOUBLE ITSELF RECORDS: after a running-guest step the sequence asks the
    # session whether the machine stopped, so the F5 (or a `run_to` that ran off) has to leave
    # it running there too, and each case parks it again before its own `resume`.
    released, ran_to = fake.resume, fake.run_to

    def _resume(**kw: Any) -> dict[str, object]:
        fake.running = True
        return released(**kw)

    def _run_to(*a: Any, **k: Any) -> dict[str, object]:
        fake.running = fake.runto_running
        return ran_to(*a, **k)

    fake.resume, fake.run_to = _resume, _run_to  # type: ignore[method-assign, assignment]
    began = time.monotonic()
    out = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=5.0)
    assert out["status"] == "ok" and out.get("still_running") is True, out
    assert time.monotonic() - began < 2.0, "the tail waited for a stop nobody asked for"
    assert "no stop was waited for" in out["note"], out
    fake.running = False
    began = time.monotonic()
    tail = server.perform(steps=[{"op": "resume"}], settle_seconds=0.6)
    assert tail.get("verdict") == "TIMEOUT" and time.monotonic() - began >= 0.5, tail
    fake.running = False
    # Declared at a stop whose mode the survey reads, so it is placed there and armed.
    fake.where_raises = False
    server.breakpoint_at(ref="00A7:0100")
    fake.where_raises = True
    began = time.monotonic()
    armed = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0.6)
    assert armed.get("verdict") == "TIMEOUT" and time.monotonic() - began >= 0.5, armed
    # `settle_seconds=0` NEVER waits, breakpoint or not, and says so.
    fake.running = False
    began = time.monotonic()
    zero = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=0)
    assert zero.get("still_running") is True and time.monotonic() - began < 0.5, zero
    assert "settle_seconds=0" in zero["note"], zero
    # A STALE raw address (another build's, never re-armed) cannot stop it: no wait.
    fake.running = False
    server.declaration_clear("breakpoint", all=True)
    dstate.STATE.session_origin = "s2"
    dstate.STATE.conf_fingerprint = "fp-now"
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "00A7:0200",  # type: ignore[union-attr]
                                      origin="s1", fingerprint="fp-old"))
    fake.running = False
    began = time.monotonic()
    stale = server.perform(steps=[{"op": "resume"}, {"op": "status"}], settle_seconds=5.0)
    assert stale.get("still_running") is True and time.monotonic() - began < 2.0, stale


# ------------------------------------- lists answer while the guest runs (T1)

def test_the_lists_answer_from_the_store_and_the_last_stop_while_the_guest_runs(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T"),
                                     dsym.Symbol("g_rate", 0x17A6EC, kind="d")])
    server.breakpoint_at(ref="_main")
    server.watch_add(ref="g_rate", mode="show", length=4, fmt="u32")
    fake.halted = True
    stop = server.resume()                       # the survey of this stop is remembered
    assert "stop_seq" in stop
    stopped = server.declaration_list("breakpoint")
    assert stopped["debugger_read"] is True and stopped["breakpoints"][0]["state"] == "armed"
    # THE GUEST RUNS: the console refuses, the lists do not.
    fake.halted = False
    fake.bp_raises = True
    fake.where_raises = True
    running = server.declaration_list("breakpoint")
    assert running["status"] == "ok", running
    assert running["debugger_read"] is False, running
    # stop 1 is the park the machine was found in at the first contact; the resume's halt
    # is stop 2, and that is what dates the answer.
    assert running["last_stop"]["stop_seq"] == 2, running
    assert running["last_stop"]["pc"] == "00A7:00000000", running
    assert running["breakpoints"][0]["ref"] == "_main"
    assert running["breakpoints"][0]["state"] == "armed", running      # as of the last stop
    watches = server.declaration_list("watch")
    assert watches["status"] == "ok" and watches["debugger_read"] is False, watches
    assert watches["watches"][0]["state"] == "evaluated", watches
    # NEVER STOPPED: nothing to date the answer by, and the rows still come.
    dstate.STATE.last_stop.clear()
    fresh = server.declaration_list("breakpoint")
    assert fresh["status"] == "ok" and fresh["last_stop"]["available"] is False, fresh
    assert fresh["breakpoints"][0]["state"] == "unarmable", fresh


def test_the_states_a_listing_still_gives_when_nothing_is_held(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    dstate.STATE.session_origin = "s2"
    server.breakpoint_interrupt(number=0x21)         # this session's: gone once its row is
    fake.rows.clear()
    dstate.STATE.store.add(dec.Declaration("breakpoint", "address", "00A7:0300",  # type: ignore[union-attr]
                                            cpu_mode="protected"))
    rows = {b["ref"]: b for b in server.declaration_list("breakpoint")["breakpoints"]}
    assert rows["BPINT 21"]["state"] == "gone" and rows["00A7:0300"]["state"] == "orphan", rows
    real = _names(tmp_path, symbols=[dsym.Symbol("_main", 0x1000, kind="T")], mode="Real",
                  base=-1)
    got = server.breakpoint_at(ref="_main")
    assert got["state"] == "unarmable" and "FLAT base" in got["why"], got
    assert real.rows == []


def test_perform_checks_every_op_before_running_any(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    out = server.perform(steps=[{"op": "send_keys", "keys": ["a"]}, {"op": "close"},
                                {"op": "status"}])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert out["steps_completed"] == 0 and out["ran"] == [], out
    assert fake.keys_sent == [] if hasattr(fake, "keys_sent") else True


def test_send_keys_names_a_stop_that_landed_during_the_wait_not_still_running(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False, input_port=5555)
    fake.running = True                      # a RUNNING guest, as this key is sent to
    fake.input_effect = None
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=5))
    assert got["status"] == "INVALID" and got["route"] == "guest", got
    assert got["posted"] == 1 and fake.scancodes_sent == [bytes([0x1E, 0x9E])], got
    assert got["verify"]["checked"] is True and got["verify"]["seen"] is False, got["verify"]
    assert got["verify"]["stopped_during_wait"] is True, got["verify"]
    assert "STOPPED at the debugger during the wait at 00A7:00000000" in got["message"], got
    assert "next resume" in got["message"] and "still running" not in got["message"], got["message"]
    assert "guest's log's to say" in got["message"], got["message"]   # never "the key sits in..."
    assert got["verify"]["waited_s"] == 0.4 and got["verify"]["lines_on_disk"] == 0, got["verify"]
    assert got["last_stop"]["pc"] == "00A7:00000000", got["last_stop"]
    assert fake.survey_calls == 1, "the stop is surveyed ONCE, by this reply"


def test_input_to_a_stopped_machine_on_a_build_with_no_run_state_is_refused_before_the_post(
        tmp_path: Path) -> None:
    """A parked post runs the machine retrace by retrace, which needs `RUNSTATE` to see them."""
    fake = _guest(tmp_path)
    fake.running = False                           # stopped, as a fresh session is
    fake.commands = frozenset(c for c in fake.commands if c != "RUNSTATE")
    fake.input_effect = None
    calls: list[Callable[[], dict[str, Any]]] = [
        lambda: server.send_keys(keys=["a"]),
        lambda: server.send_keys(keys=["a"], expect="key_cue_a", seconds=2),
        lambda: server.send_mouse(button="left")]
    for call in calls:
        got = call()
        assert got["status"] == "INVALID" and got["code"] == "no_channel", got
        assert "RUNSTATE" in got["message"], got["message"]
        assert "answers_while_running" not in got, got
    assert fake.commands_sent == [], "nothing was posted to a stopped machine"
    assert "posted" not in got


def test_drive_names_a_stop_that_landed_during_its_verify(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True                            # the act is sent to a RUNNING guest
    fake.input_effect = None
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                            expect="key_cue_a", seconds=1))
    assert got["status"] == "INVALID", got
    assert got["verify"]["stopped_during_wait"] is True, got["verify"]
    assert "STOPPED at the debugger during the wait at 00A7:00000000" in got["message"], got
    assert "no line matching `expect`" in got["message"], got["message"]
    assert got["last_stop"]["pc"] == "00A7:00000000", got["last_stop"]


def test_the_sequences_wait_for_a_stop_reports_its_progress(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True                    # running, and it stays running
    monkeypatch.setattr(run_state, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    out = sequence.run_steps(fake, [{"op": "resume"}], 0.3, server._step_ops(),  # type: ignore[arg-type]
                             lambda p, t, m: ticks.append(m))
    assert out.get("verdict") == "TIMEOUT", out
    assert ticks and ticks[0].startswith("waiting for the machine to stop: ")


def test_the_sequences_wait_for_a_stop_asks_the_run_state_and_sends_nothing_else(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    monkeypatch.setattr(fake, "alive", lambda: True)
    assert sequence._wait_for_stop(fake, 1.0) == "stopped"  # type: ignore[arg-type]
    assert fake.commands_sent == []
    fake.where_raises = True
    monkeypatch.setattr(run_state, "PROGRESS_EVERY_S", 0.0)
    ticks: list[str] = []
    assert sequence._wait_for_stop(fake, 0.6, lambda p, t, m: ticks.append(m)) == "running"  # type: ignore[arg-type]
    assert ticks and ticks[0].startswith("waiting for the machine to stop: "), ticks
    # A GONE emulator is still told apart from a running one.
    monkeypatch.setattr(fake, "alive", lambda: False)
    assert sequence._wait_for_stop(fake, 0.3) == "gone"  # type: ignore[arg-type]


def test_a_step_carrying_ctx_is_refused_before_it_runs(tmp_path: Path) -> None:
    _names(tmp_path)
    out = server.perform(steps=[{"op": "status"}, {"op": "resume", "ctx": "bogus"}])
    assert out["status"] == "INVALID" and out["failed_at"] == 1, out
    assert "ctx" in out["message"] and out["steps_completed"] == 0, "seen up front: nothing ran"


def test_the_verify_of_drive_forwards_the_progress_to_the_wait() -> None:
    class _Waits:
        log_wait = _log_wait_as_guest

        def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                    progress: ds.Progress = ds.no_progress) -> dict[str, object]:
            progress(1.0, seconds, "tick")
            return {"verdict": "TARGET", "line": "x", "already": False, "lines_total": 1,
                    "lines_before": 0,
                    "arrived_during": 1, "waited_s": 1.0, "lines_examined": 1}

    ticks: list[str] = []
    out = sequence._verify_after_wait(_Waits(), "x", 3.0, 0,  # type: ignore[arg-type]
                                      lambda p, t, m: ticks.append(m))
    assert ticks == ["tick"] and out["seen"] is True


def test_perform_carries_the_clients_context_to_its_wait(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end through the registered tool, from the worker thread the SDK uses."""
    import anyio

    got: list[str] = []

    class _Ctx:
        async def report_progress(self, progress: float, total: float | None = None,
                                  message: str | None = None) -> None:
            got.append(str(message))

    fake = _names(tmp_path)
    fake.halted = False
    fake.where_raises = True
    monkeypatch.setattr(run_state, "PROGRESS_EVERY_S", 0.0)

    async def main() -> None:
        await anyio.to_thread.run_sync(
            lambda: server.perform(steps=[{"op": "resume"}], settle_seconds=0.3, ctx=_Ctx()))

    anyio.run(main)
    assert got and got[0].startswith("waiting for the machine to stop")


def test_send_keys_hands_its_progress_to_the_wait_for_the_reaction() -> None:
    class _Route:
        launch = SimpleNamespace(watched=False, input_port=5555, logfile=None)
        stub_protocol = inputs.STUB_PROTOCOL
        keys_posted = 1
        inputs_written = releases_sent = 0

        def e9_mark(self) -> int:
            return 0

        @property
        def parked(self) -> bool:
            return self.at_debugger()

        def at_debugger(self) -> bool:
            return False

        def send_commands(self, commands: list[bytes]) -> list[str]:
            return []

        log_wait = _log_wait_as_guest

        def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                    progress: ds.Progress = ds.no_progress) -> dict[str, object]:
            progress(1.0, seconds, "tick")
            return {"verdict": "TARGET", "line": "READY", "already": False, "lines_total": 1,
                    "lines_before": 0,
                    "arrived_during": 1, "waited_s": 1.0, "lines_examined": 1}

    ticks: list[str] = []
    out = inputs.send_keys(_Route(), ["enter"], None, "READY", 2.0,  # type: ignore[arg-type]
                           lambda p, t, m: ticks.append(m))
    assert ticks == ["tick"] and out["verify"]["seen"] is True


def test_perform_checks_every_steps_arguments_before_any_step_runs(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    out = server.perform(steps=[{"op": "resume"}, {"op": "status", "bogus": 1}], settle_seconds=1.0)
    assert out["status"] == "INVALID" and "bad arguments" in out["message"], out
    assert out["steps_completed"] == 0 and out["ran"] == [] and out["failed_at"] == 1
    assert fake.stop_count == 0, "the resume never went out"
    out = server.perform(steps=[{"op": "resume"}, {"op": "status", "ctx": 1}], settle_seconds=1.0)
    assert out["status"] == "INVALID" and "`ctx`" in out["message"] and out["steps_completed"] == 0


# ------------------------------------------------- the pre-flight: values, not only shapes

def test_a_bad_value_in_a_later_step_runs_nothing_and_every_refusal_is_listed(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "send_keys", "keys": ["b"]},
        {"op": "send_keys", "keys": ["not_a_real_key_xyz"]},
        {"op": "log", "pattern": "(", "channel": "guest"}], settle_seconds=0.5))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert out["ran"] == [] and out["steps_completed"] == 0 and out["failed_at"] == 1, out
    assert fake.commands_sent == [], "a key was posted before the batch was checked"
    refused = cast(list[dict[str, Any]], out["errors"])
    assert [e["step"] for e in refused] == [1, 2], refused
    assert "not_a_real_key_xyz" in refused[0]["message"], refused[0]
    assert "pattern" in refused[1]["message"], refused[1]


def test_send_keys_refuses_an_unknown_name_before_the_window_is_touched(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.send_keys(keys=["a", "not_a_real_key_xyz"]))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "not_a_real_key_xyz" in out["message"], out
    assert fake.commands_sent == [], "an unknown name was sent"


def test_the_modifier_vocabulary_is_the_dos_keyboard_s() -> None:
    inputs.check_keys(["a"], ["shift", "CTRL", "alt", "option", "control"])
    with pytest.raises(ds.Invalid, match="no command key"):
        inputs.check_keys(["a"], ["cmd"])
    with pytest.raises(ds.Invalid, match="unknown modifier 'hyper'"):
        inputs.check_keys(["a"], ["hyper"])
    with pytest.raises(ds.Invalid, match="unknown key name 'bogus'"):
        inputs.check_keys(["bogus"], None)


@pytest.mark.parametrize(("op", "bad", "good"), [
    ("breakpoint_interrupt", {"number": 0x21, "ah": 0x100}, {"number": 0x21, "ah": 0x4C}),
    ("machine_map", {"sections": ["bogus"]}, {"sections": [machine.SECTION_NAMES[0]]}),
    ("scan", {"method": "filter", "operator": "=", "value": 1, "limit": 401},
     {"method": "filter", "operator": "=", "value": 1, "limit": 400}),
    ("send_keys", {"keys": ["a"], "seconds": 5.0}, {"keys": ["a"], "expect": "R", "seconds": 5.0}),
    ("send_keys", {"keys": ["a"], "expect": "R", "seconds": -1.0}, {"keys": ["a"], "expect": "R"}),
    ("send_keys", {"keys": ["a"], "modifiers": ["cmd"]}, {"keys": ["a"], "modifiers": ["shift"]}),
    ("send_mouse", {"x": 1, "y": 1, "seconds": 5.0},
     {"x": 1, "y": 1, "expect": "R", "seconds": 5.0}),
    ("send_mouse", {"x": 1, "y": 1, "expect": "R", "seconds": -1.0},
     {"x": 1, "y": 1, "expect": "R"}),
    ("send_mouse", {"button": "wheel"}, {"button": "middle"}),
    ("send_mouse", {"x": 3}, {"x": 3, "y": 4}),
    ("send_mouse", {"button": "left", "action": "hold"}, {"button": "left", "action": "down"}),
    ("send_mouse", {"x": 3, "y": 4, "units": "px"}, {"x": 3, "y": 4, "units": "mouse"}),
    ("log", {"pattern": "(", "channel": "guest", "limit": 5}, {"pattern": "x", "channel": "guest"}),
    ("log", {"pattern": "x", "channel": "guest", "limit": 0},
     {"pattern": "x", "channel": "guest", "limit": 1}),
    ("log", {"pattern": "x", "channel": "process"}, {"pattern": "x", "channel": "all"}),
    ("log_wait", {"pattern": "x", "channel": "guest", "seconds": 0},
     {"pattern": "x", "channel": "emulator", "seconds": 3}),
    ("resume", {"seconds": -1}, {"seconds": 0}),
    ("step", {"mode": "sideways"}, {"mode": "into", "count": 2}),
    ("run_to", {"ref": "ZZZZ:", "seconds": 5}, {"ref": "00A7:0100", "control": "00A7:0200"}),
    ("breakpoint_at", {"ref": "_main", "by": "guess"}, {"ref": "_main"}),
    ("breakpoint_interrupt", {"number": 0x100}, {"number": 0x21, "ah": 0x4C}),
    ("watch_add", {"ref": "_g", "mode": "show", "length": 2, "fmt": "u32"},
     {"ref": "_g", "mode": "change", "length": 4}),
    ("read_memory", {"ref": "00A7:zz"}, {"ref": "00A7:0100"}),
    ("memdump", {"ref": "_g", "length": 0, "dest": _abs("x", "d.bin")},
     {"ref": "_g", "length": 8, "dest": _abs("x", "d.bin")}),
    ("memdump", {"ref": "_g", "length": 8, "dest": "d.bin"},
     {"ref": "_g", "length": 8, "dest": _abs("x", "d.bin")}),
    ("write", {"ref": "_g", "data_hex": "abc"}, {"ref": "_g", "data_hex": "abcd"}),
    ("set_register", {"name": "xyz", "value": 1}, {"name": "ax", "value": 1}),
    ("set_register", {"name": "ax", "value": "1"}, {"name": "ax", "value": 0x1234}),
    ("symbols_load", {"path": _abs("x", "m.map"), "base": "1", "section_bases": {"1": "1"}},
     {"path": _abs("x", "m.map"), "base": "1"}),
    ("symbols_load", {"path": _abs("x", "m.map"), "base": 4096},
     {"path": _abs("x", "m.map"), "base": "0x1000"}),
    ("symbols_load", {"path": "m.map"}, {"path": _abs("x", "m.map")}),
    ("symbols_load", {"path": _abs("x", "m.map"), "types": "t"},
     {"path": _abs("x", "m.map"), "types": _abs("x", "t")}),
    ("capture_frame", {"frame": -1, "dest": _abs("x", "s.png")},
     {"frame": 3, "dest": _abs("x", "s.png")}),
    ("capture_frame", {"frame": 3, "dest": _abs("x", "s%03d.png")},
     {"frame": 3, "dest": _abs("x", "s.png")}),
    ("capture_frame", {"frame": 3, "dest": _abs("x", "s.png"), "capture_path": "c.avi"},
     {"frame": 3, "dest": _abs("x", "s.png"), "capture_path": _abs("x", "c.avi")}),
])
def test_every_registry_entry_refuses_its_bad_value_and_passes_its_good_one(
        op: str, bad: dict[str, Any], good: dict[str, Any]) -> None:
    with pytest.raises(ds.Invalid):
        checks.preflight(op, bad)
    checks.preflight(op, good)
    checks.preflight("status", {})        # no entry: nothing to judge


def test_perform_refuses_a_run_to_step_without_a_control_before_the_list_runs(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    out = cast(dict[str, Any], server.perform(steps=[{"op": "status"},
                                                     {"op": "run_to", "ref": "0000:0000"}]))
    assert out["status"] == "INVALID" and "no control" in str(out.get("errors")), out
    empty = cast(dict[str, Any], server.perform(steps=[
        {"op": "status"}, {"op": "run_to", "ref": "0000:0000", "control": ""}]))
    assert empty["status"] == "INVALID" and "no control" in str(empty.get("errors")), empty
    assert out.get("ran") in (None, []) and fake.runto_calls == [], out


@pytest.mark.parametrize("bad", [
    {"op": "read_memory", "ref": "0000:0000", "length": 129},
    {"op": "read_memory", "ref": "0000:0000", "length": 0},
    {"op": "write", "ref": "0000:0000", "data_hex": "00" * 129},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "length": 129},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "fmt": "u8[129]"},
    {"op": "watch_add", "ref": "0000:0000", "mode": "show", "fmt": "u16[65]"},
])
def test_perform_checks_the_data_view_ceilings_before_any_step_runs(
        tmp_path: Path, bad: dict[str, Any]) -> None:
    _names(tmp_path)
    out = server.perform(steps=[{"op": "status"}, bad])
    assert out["status"] == "INVALID" and out["ran"] == [], (bad, out)
    assert out["errors"][0]["step"] == 1 and out["errors"][0]["op"] == bad["op"], out


def test_drives_lines_ceiling_is_logs_ceiling_and_not_a_second_constant(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.where_raises = True
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 7)
    key = {"op": "send_keys", "keys": ["a"]}
    over = cast(dict[str, Any], server.drive(act=[key], limit=8))
    assert over["status"] == "INVALID" and "outside 1..7" in over["message"], over
    assert fake.commands_sent == [], "a refused drive must not have acted"
    at = cast(dict[str, Any], server.drive(act=[key], limit=7))
    assert at["status"] == "ok", at


def test_perform_a_step_missing_a_value_or_carrying_the_wrong_type_is_refused_not_crashed(
        tmp_path: Path) -> None:
    _names(tmp_path)
    out = server.perform(steps=[{"op": "step", "count": 1, "mode": "over"},
                                {"op": "watch_add", "ref": "F000:C9B0", "mode": "show"}])
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "length" in out["message"], out["message"]
    typed = server.perform(steps=[{"op": "step", "count": 1, "mode": "over"},
                                  {"op": "read_memory", "ref": "F000:C9B0", "length": "8"}])
    assert typed["status"] == "INVALID" and typed["code"] == "bad_argument", typed
    assert "step 2 ('read_memory') length is an integer; got '8'" in typed["message"], typed
    assert "not supported" not in typed["message"]


def test_every_step_check_takes_what_its_tool_takes_with_the_same_defaults() -> None:
    ops = server._step_ops()
    for op, check in checks.BY_OP.items():
        fn = ops.get(op) or getattr(server, op)      # a tool that is not a batch step
        tool = {n: p for n, p in inspect.signature(fn).parameters.items() if n != "ctx"}
        for name, param in inspect.signature(check).parameters.items():
            if param.kind is param.VAR_KEYWORD or name == "serial":
                continue
            assert name in tool, f"{op}: the check takes `{name}`, which the tool does not"
            if param.default is param.empty:
                assert tool[name].default is param.empty, (
                    f"{op}: the tool defaults `{name}` and the check requires it")
            elif tool[name].default is not param.empty:
                assert tool[name].default == param.default, (
                    f"{op}: `{name}` defaults to {tool[name].default!r} in the tool and "
                    f"{param.default!r} in the check")


def test_start_with_an_input_port_keeps_session_as_the_last_key(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    got = _start_on_a_booted_fake(tmp_path, monkeypatch, input_port=5555)
    assert got["status"] == "ok" and got["input_port"] == 5555 and "stub" in got, got
    assert list(got)[-1] == "session", f"the reply ends in {list(got)[-1]!r}, not `session`"


@pytest.mark.parametrize(("ah", "refusal"), [
    (None, None),                                  # an explicit null is the `| None` it declares
    (2, None),
    ("2", "section is "),                          # anything else is judged as the scalar
    (True, "section is "),                         # and a bool is never a number
])
def test_a_step_takes_null_for_an_optional_scalar_and_judges_anything_else(
    ah: Any, refusal: str | None,
) -> None:
    said = step_judge.wrong_type(server.symbols_find, {"name": "x", "section": ah})
    assert (said is None) if refusal is None else (said or "").startswith(refusal), said


def test_perform_with_summaries_cuts_every_step_but_the_last_and_counts_the_stops(
        tmp_path: Path) -> None:
    _names(tmp_path)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "step", "count": 1, "mode": "over"},
               {"op": "step", "count": 1, "mode": "over"}, {"op": "registers"}],
        summaries=True))
    assert out["status"] == "ok" and out["steps_total"] == 3 and out["truncated"] is False, out
    first, second, last = out["ran"]
    assert {"summary", "status", "stop_seq", "cause"} <= set(first["reply"]), first
    assert set(first["reply"]) <= {"summary", "status", "stop_seq", "cause",
                                   "stopped_on_its_own"}, first
    assert "regs" not in second["reply"] and "regs" in last["reply"], out["ran"]
    assert out["summary"] == "perform: 3 of 3 steps", out["summary"]
    rows = Path(out["ran_path"]).read_text(encoding="ascii").splitlines()
    replies = Path(out["replies_path"]).read_text(encoding="ascii").splitlines()
    assert len(rows) == len(replies) == 3, (rows, replies)
    assert json.loads(replies[0])["reply"]["regs"], replies[0]
    stops = out["stops"]
    assert stops["stop_seq_last"] == dstate.STATE.last_stop["seq"], stops
    assert stops["unaccounted"] == 0 and stops["surveyed"] >= 2, stops
    assert stops["surveyed"] == stops["stop_seq_last"] - stops["stop_seq_first"] + 1, stops
    assert list(stops["by_cause"].values()) == [stops["surveyed"]], stops
    assert next(iter(stops["by_cause"])).startswith("no declared code breakpoint"), stops
    plain = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}]))
    assert "steps_total" not in plain and "regs" in plain["ran"][0]["reply"], plain


def test_perform_with_summaries_shows_the_first_rows_and_says_it_cut(tmp_path: Path) -> None:
    _names(tmp_path)
    n = dstate.ROWS_SHOWN + 3
    out = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}] * n, summaries=True))
    assert out["steps_total"] == n and out["truncated"] is True, out
    assert len(out["ran"]) == dstate.ROWS_SHOWN + 1 and out["ran"][-1]["step"] == n - 1, out
    assert len(Path(out["ran_path"]).read_text(encoding="ascii").splitlines()) == n


def test_summaries_is_a_yes_or_a_no(tmp_path: Path) -> None:
    _names(tmp_path)
    calls: list[Callable[[], Any]] = [
        lambda: server.perform(steps=[{"op": "registers"}], summaries="yes"),
        lambda: server.drive(act=[{"op": "registers"}], summaries=1)]
    for call in calls:
        got = cast(dict[str, Any], call())
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "summaries is true or false" in got["message"], got["message"]


def test_the_stop_count_survives_a_session_closed_mid_batch() -> None:
    dstate.STATE.last_stop.clear()
    ran = [{"op": "resume", "reply": {"summary": "s", "status": "ok", "stop_seq": n,
                                      "cause": dstate.cause({"attributed": False,
                                                             "at": f"0814:000001{n:02X}"})}}
           for n in (6, 7, 8)]
    got = sequence.account_of(ran, True, keep_last=False, since=5)["stops"]
    assert got == {"stop_seq_first": 6, "stop_seq_last": 8, "surveyed": 3,
                   "by_cause": {dstate.cause_key(dstate.cause({"attributed": False,
                                                                  "at": "0814:00000100"})): 3},
                   "unaccounted": 0}, got


def test_a_batch_writes_both_files_or_neither_and_remakes_a_vanished_scratch(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = [{"step": 0, "op": "status", "reply": {"summary": "s", "status": "ok"}}]
    monkeypatch.setattr(dstate.STATE, "scratch", tmp_path / "gone")   # the OS cleaned it away
    made = account.files(sequence._batch_stem, rows, rows)
    assert made["ran_path"] and Path(made["replies_path"]).exists(), made
    real = account.write_jsonl
    calls: list[Path] = []

    def second_fails(path: Path, r: list[dict[str, Any]]) -> str:
        calls.append(path)
        out = real(path, r)
        if len(calls) == 2:
            raise OSError("disk full half way")
        return out

    monkeypatch.setattr(account, "write_jsonl", second_fails)
    failed = account.files(sequence._batch_stem, rows, rows)
    assert failed["ran_path"]["available"] is False and "disk full" in failed["ran_path"]["why"]
    assert not any(p.exists() for p in calls), [p for p in calls if p.exists()]


def test_drive_hands_summaries_to_its_act(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.drive(act=[{"op": "registers"}, {"op": "registers"}],
                                             summaries=True))
    act = got["act"]
    assert act["steps_total"] == 2 and act["ran_path"] and "stops" in act, act
    assert set(act["ran"][0]["reply"]) <= {"summary", "status", "stop_seq", "cause",
                                           "stopped_on_its_own"}, act["ran"][0]


@pytest.mark.parametrize("bad_step", [
    {"op": "symbols_find", "linear": "56DFZZ"},
    {"op": "symbols_load", "path": "x.map", "section_bases": {"1": 4096}}])
def test_a_list_refuses_a_bad_hex_address_before_its_first_step_runs(
        tmp_path: Path, bad_step: dict[str, Any]) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}, bad_step]))
    assert got["status"] == "INVALID" and got["ran"] == [], got
    assert [e["step"] for e in got["errors"]] == [1], got["errors"]


def test_a_wait_step_that_ran_out_ends_the_list_and_a_run_that_did_goes_on(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    out = cast(dict[str, Any], server.perform(steps=[
        {"op": "log_wait", "pattern": "NEVER", "channel": "guest", "seconds": 1},
        {"op": "status"}]))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 1 and "step 1 ('log_wait')" in out["note"], out
    fake.running = False
    fake.runto_running, fake.control_hits = True, 1
    ran = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_to", "ref": "0000:0010", "control": "0000:0020"}, {"op": "status"}]))
    assert ran["status"] == "ok" and ran["steps_completed"] == 2 and "verdict" not in ran, ran


def test_a_list_that_waited_mid_way_and_ends_running_carries_no_target(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.halted = False
    fake.where_refusals = 2                     # the first resume's stop lands a moment later
    released, calls = fake.resume, [0]

    def resume(**kw: Any) -> dict[str, object]:
        calls[0] += 1
        fake.running = calls[0] == 2            # the second one runs on, nothing to stop it
        return released(**kw)

    fake.resume = resume  # type: ignore[method-assign, assignment]
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "resume"}, {"op": "registers"}, {"op": "resume"}, {"op": "status"}],
        settle_seconds=2.0))
    assert out["status"] == "ok" and out.get("still_running") is True, out
    assert "verdict" not in out, out


def test_drive_says_its_check_was_not_made_when_the_act_ran_out(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.input_effect = None
    got = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"], "expect": "never", "seconds": 1}],
        expect="key_cue_a"))
    assert got["verify"]["available"] is False, got
    assert got["summary"] == "drive: effect not checked", got["summary"]


def test_drive_says_its_act_ended_after_its_last_step_when_the_emulator_went(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _names(tmp_path, watched=True)
    server.breakpoint_interrupt(number=0x21)            # something declared: the tail waits
    monkeypatch.setattr(sequence, "_wait_for_stop", lambda *a, **k: "gone")
    got = cast(dict[str, Any], server.drive(act=[{"op": "resume"}], settle_seconds=1))
    assert got.get("code") == "session_broken", {k: got[k] for k in ("summary", "status")}
    assert "GONE" in got["message"] and "available" not in got["message"], got
    assert "after its last step" in got["message"], got["message"]


def test_a_step_whose_survey_came_back_cut_is_not_said_to_be_running(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.registers_raises = True
    got = cast(dict[str, Any], server.step())
    assert got["session"]["running"] is False and "enrichment" in got, got
    assert "running" not in got["summary"], got["summary"]


def test_drive_carries_its_acts_own_code_when_no_step_failed(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.halted = False                         # the resume leaves the guest running
    fake.where_raises = True                    # ...and it stays running: no prompt to hear
    got = cast(dict[str, Any], server.drive(act=[{"op": "resume"}, {"op": "registers"}],
                                            settle_seconds=0))
    assert got["code"] == "not_stopped", {k: got.get(k) for k in ("code", "message")}


def test_start_refuses_a_settle_bound_with_no_plan_to_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`settle_seconds` bounds a plan's waits: with no plan it would be silently ignored."""
    def launched(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("the start was not refused: it reached the launch")
    monkeypatch.setattr(dosbox_lifecycle, "start", launched)
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    got = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path), session_seconds=60,
                                            settle_seconds=5))
    assert got["code"] == "bad_argument" and "plan" in got["message"], got


def test_a_refused_list_answers_the_contracts_shape(tmp_path: Path) -> None:
    _names(tmp_path)
    contract.check_refusal("perform", cast(dict[str, Any], server.perform(
        steps=[{"op": "registers"}, {"op": "write", "ref": "nowhere", "data_hex": "00"}])))


def test_drive_waits_for_its_expect_five_seconds_by_default(tmp_path: Path) -> None:
    assert inputs.DRIVE_EXPECT_WAIT_S == 5.0
    assert dosbox_docs.DOC_VALUES["EXPECT_WAIT_S"] == "5"
    fake = _names(tmp_path, watched=True)
    fake.running = True
    server.drive(act=[{"op": "send_keys", "keys": ["a"]}], expect="key_cue_a")
    assert fake.wait_calls and fake.wait_calls[-1][1] == 5.0, fake.wait_calls


def test_a_plans_wait_is_held_to_the_one_wait_bound_before_anything_is_spawned(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a))
    conf = tmp_path / "x.conf"
    conf.write_text("[autoexec]\n")
    out = cast(dict[str, Any], server.start(conf=str(conf), cwd=str(tmp_path),
                                            session_seconds=60,
                                            plan=[{"op": "registers"}],
                                            settle_seconds=vocab.WAIT_MAX_S + 1))
    assert out["code"] == "bad_argument", out
    assert out["message"].startswith(f"settle_seconds={vocab.WAIT_MAX_S + 1} is not a bound"), out
    assert spawned == [], "refused before anything was spawned"



def test_a_list_begun_on_a_running_guest_waits_for_its_stop_before_a_console_step(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake._running = True
    out = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}], settle_seconds=0.3))
    assert out["status"] == "ok" and out["verdict"] == "TIMEOUT", out
    assert out["steps_completed"] == 0 and "still running" in out["note"], out


def test_a_terminal_that_overflows_while_the_list_waits_ends_it_with_what_ran(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    fake._running = True

    def overflowed(*_a: Any, **_k: Any) -> tuple[bool, float]:
        raise ds.Invalid("unexpected_answer", "the terminal buffer overflowed and 4096 bytes "
                         "were discarded during this read")

    monkeypatch.setattr(ds.Session, "await_stop", overflowed)
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "send_keys", "keys": ["a"]}, {"op": "registers"}], settle_seconds=0.5))
    assert out["code"] == "unexpected_answer" and "overflowed" in out["message"], out
    assert [s["op"] for s in out["ran"]] == ["send_keys"] and out["steps_completed"] == 1, out


def test_drive_with_an_expect_leaves_the_wait_to_it_on_a_running_guest(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True, mode="Real")
    declared = cast(dict[str, Any], server.breakpoint_at(ref="0814:0100"))
    assert declared["status"] == "ok", declared        # something that can stop the guest
    fake.running = True
    fake.where_raises = True
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    out = cast(dict[str, Any], server.drive(act=[{"op": "status"}], expect="NEVER_LOGGED",
                                            seconds=0.2, settle_seconds=1.0))
    assert out["act"].get("verdict") != "TIMEOUT", out["act"]
    assert out["verify"].get("available") is not False, out["verify"]
