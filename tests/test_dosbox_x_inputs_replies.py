"""What an input's reply hands back, by the keys and words a caller reads: the `verify` block on a
miss and on a stop during the wait, the echo of what was sent, the pointer's buttons, the bound
and the progress a mouse wait is given, and the stub's refusal before anything is sent."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import _names, clean_session  # noqa: F401

from scry_dosbox_x import inputs, retrace, run_state, server, summaries, taps
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

E9_KEY_ACT = "Bochs port E9h: [+   0.010] KEY   . key_cue_a"


def test_a_miss_says_what_it_waited_for_and_how_long_in_every_key() -> None:
    reaction = {"verdict": "TIMEOUT", "waited_s": 2.0, "arrived_during": 3, "lines_examined": 4,
                "note": "nothing new"}
    got = inputs.verify_block("key_cue_a", reaction)
    assert {k: got[k] for k in ("expected", "waited_s", "arrived_during", "lines_examined")} == {
        "expected": "key_cue_a", "waited_s": 2.0, "arrived_during": 3, "lines_examined": 4}, got


def test_a_key_with_no_expect_says_what_would_confirm_it(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["verify"]["why"] == (
        "no `expect` was given, so the reply says what went into the guest and NOT that the "
        "program took it; pass expect=<E9 pattern> to confirm its reaction"), got["verify"]


def test_a_stop_during_the_wait_keeps_the_echo_and_the_waits_own_words(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False, input_port=5555)
    fake.running = True
    fake.input_effect = None
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.send_keys(keys=["a"], expect="key_cue_a", seconds=5))
    assert (got["keys"], got["modifiers"]) == (["a"], []), got
    assert got["verify"]["expected"] == "key_cue_a", got["verify"]
    assert got["verify"]["why"].startswith("the machine STOPPED during the wait"), got["verify"]


def test_the_pointer_names_every_button_held() -> None:
    report = inputs.Report(x=0, y=0, buttons=6, max_x=639, max_y=199, mode=3, drawn=(640, 200))
    assert inputs._pointer(report)["buttons"] == ["right", "middle"]


def test_a_mouse_wait_takes_the_callers_bound_and_reports_its_progress(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    ticks: list[str] = []
    real_wait = fake.e9_wait

    def wait(pattern: str, seconds: float, mark: int = 0,
             progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        progress(1.0, 2.0, "waiting")
        return real_wait(pattern, seconds, mark, progress)
    fake.e9_wait = wait  # type: ignore[method-assign]
    inputs.send_mouse(fake, None, None, "left", "click", "screen", "key_cue_a", 0.3,  # type: ignore[arg-type]
                      lambda *a: ticks.append("tick"))
    assert fake.wait_calls[-1][1] == 0.3, fake.wait_calls
    assert ticks, "the wait's progress never reached the caller"
    aimed = {"centre": (1, 1), "target": "OK", "screen": "s", "identified_at_stop": 1,
             "kind": "text", "size": (80, 25)}
    ticks.clear()
    inputs.send_mouse_at(fake, aimed, "left", "click", "key_cue_a", 0.3,  # type: ignore[arg-type]
                         lambda *a: ticks.append("tick"))
    assert ticks, "the wait's progress never reached the caller through a target"


def _stub_session(tmp_path: Path, lines: list[str], stub_drive: str | None,
                  parked: bool = False, stop_count: int = 0) -> Any:
    asked: list[int] = []

    def since(mark: int) -> list[str]:
        asked.append(mark)
        return lines
    return SimpleNamespace(launch=SimpleNamespace(logfile=tmp_path / "e9.log",
                                                  stub_drive=stub_drive),
                           stub_protocol="", e9_since_mark=since, asked=asked,
                           parked=parked, stop_count=stop_count)


def test_a_stub_that_never_announced_is_refused_naming_the_line_and_the_way_in(
        tmp_path: Path) -> None:
    ses = _stub_session(tmp_path, [], None)
    with pytest.raises(ds.Invalid) as refused:
        inputs.require_stub(ses)
    said = str(refused.value)
    assert "`STUB  . scry` on E9" in said and "[autoexec]" in said, said
    assert "or `start(program=...)` loads it by itself" in said, said
    assert "mounted it on" not in said, said


@pytest.mark.parametrize("stop_count", [0, 1])
def test_a_guest_parked_before_its_first_instruction_is_refused_naming_that_and_the_next_call(
        tmp_path: Path, stop_count: int) -> None:
    """The stub has not announced because nothing has run, not because the conf lacks it."""
    ses = _stub_session(tmp_path, [], "Y", parked=True, stop_count=stop_count)
    with pytest.raises(ds.Invalid) as refused:
        inputs.require_stub(ses)
    said = str(refused.value)
    assert refused.value.code == "no_channel", said
    assert "has not run yet" in said and "`run_for` or `resume`" in said, said
    assert "[autoexec]" not in said and "mounted it on" not in said, said


def test_a_guest_that_ran_and_stopped_again_without_a_stub_still_names_the_conf(
        tmp_path: Path) -> None:
    ses = _stub_session(tmp_path, [], "Y", parked=True, stop_count=2)
    with pytest.raises(ds.Invalid) as refused:
        inputs.require_stub(ses)
    assert "has not run yet" not in str(refused.value) and "[autoexec]" in str(refused.value)


def test_a_stub_announced_in_the_log_is_read_from_its_start(tmp_path: Path) -> None:
    ses = _stub_session(tmp_path, [f"Bochs port E9h: STUB  . scry device=present "
                                   f"proto={inputs.STUB_PROTOCOL}"], None)
    inputs.require_stub(ses)
    assert ses.stub_protocol == inputs.STUB_PROTOCOL and ses.asked == [0], ses


def test_no_keys_is_refused_saying_send_keys_needs_one() -> None:
    with pytest.raises(ds.Invalid) as none:
        inputs.check_keys([], None)
    assert str(none.value) == "send_keys needs at least one key name", none.value


def test_a_cancel_among_a_parked_posts_retraces_leaves_the_machine_stopped(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The post found the machine stopped; a cancel that meets one of its retraces with the `VRT`
    out stops it where it stands rather than leave it running."""
    stopped: list[object] = []

    def cancelled(*_: object, **__: object) -> dict[str, object]:
        raise asyncio.CancelledError

    monkeypatch.setattr(retrace, "run_for", cancelled)
    def stop_at_bound(session: object) -> bool:
        stopped.append(session)
        return True

    monkeypatch.setattr(ds.Session, "stop_at_bound", stop_at_bound)
    monkeypatch.setattr(run_state, "read_run_state", lambda _s: True)
    session = SimpleNamespace(clock_ms=0.0)
    with pytest.raises(asyncio.CancelledError):
        inputs.Retraces(session)()  # type: ignore[arg-type]
    assert stopped == [session]


def test_a_parked_posts_count_watch_counts_since_the_stop_the_post_began_at(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Each retrace of the post is a stop that moves the baseline; the reply's `since_last_stop`
    is what the whole post saw, not the last retrace's share."""
    monkeypatch.setattr(run_state, "read_run_state", lambda _s: True)
    # Totals as the debugger lists them where the post begins: 10 and 9 are what the last stop a
    # tool reported held, and the stop the post found (an `observe_stop`) was 20 and 9 by then.
    monkeypatch.setattr(taps, "listed", lambda _s: {7: {"total": 20}, 8: {"total": 9}})
    monkeypatch.setitem(dstate.STATE.taps, "tap", SimpleNamespace(id=7, last_total=10))
    row = {"ref": "tap", "tally_id": "7", "total": 25, "since_last_stop": 2}
    fell = {"ref": "gone", "tally_id": "8", "total": 3, "since_last_stop": 3}
    monkeypatch.setitem(dstate.STATE.taps, "gone", SimpleNamespace(id=8, last_total=9))
    run = inputs.Retraces(SimpleNamespace(clock_ms=0.0))  # type: ignore[arg-type]
    run.last = {"watches": [row, fell, {"ref": "freeze", "mode": "freeze"}]}
    got = run.fields()["watches"]
    assert (got[0]["since_last_stop"], "reset" in got[0]) == (5, False), got
    assert (got[1]["since_last_stop"], got[1]["reset"]) == (3, True), got
    assert got[2] == {"ref": "freeze", "mode": "freeze"}, got


def test_a_mouse_summary_says_when_the_move_widened_the_drivers_range() -> None:
    program: dict[str, Any] = {"x": 900, "y": 600, "corrections": 5,
                               "range_widened": {"x": 2050, "y": 767}}
    reply: dict[str, Any] = {"pointer": {"screen": {"x": 900, "y": 600}, "program": program},
                             "arrived": True, "verify": {"checked": False}}
    args = {"x": 900, "y": 600, "button": "left"}
    assert "driver range widened to 2050 x 767" in summaries.send_mouse(args, reply)
    program.pop("range_widened")
    assert "widened" not in summaries.send_mouse(args, reply)


@pytest.mark.parametrize(("args", "said"), [
    ({"x": 365, "y": 8}, True),
    ({"x": 365, "y": 8, "button": "left"}, False),
    ({"x": 365, "y": 8, "button": "left", "action": "drag"}, False),
])
def test_a_mouse_summary_says_when_no_button_was_pressed(args: dict[str, Any], said: bool) -> None:
    """A move with no `button` presses nothing, which a check that saw no effect must not hide."""
    reply = {"pointer": {"screen": {"x": 365, "y": 8}}, "arrived": True,
             "verify": {"checked": True, "verdict": "TIMEOUT"}}
    line = summaries.send_mouse(args, reply)
    assert ("no button pressed" in line) is said, line
