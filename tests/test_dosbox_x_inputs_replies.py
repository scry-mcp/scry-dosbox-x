"""What an input's reply hands back, by the keys and words a caller reads: the `verify` block on a
miss and on a stop during the wait, the echo of what was sent, the pointer's buttons, the bound
and the progress a mouse wait is given, and the stub's refusal before anything is sent."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_dosbox_x_server import _names, clean_session  # noqa: F401

import dosbox_inputs as inputs
import dosbox_session as ds
import dosbox_x_server as server

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
    assert got["verify"]["why"].startswith("the machine is stopped at the debugger"), got["verify"]


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


def _stub_session(tmp_path: Path, lines: list[str], stub_drive: str | None) -> Any:
    asked: list[int] = []

    def since(mark: int) -> list[str]:
        asked.append(mark)
        return lines
    return SimpleNamespace(launch=SimpleNamespace(logfile=tmp_path / "e9.log",
                                                  stub_drive=stub_drive),
                           stub_protocol="", e9_since_mark=since, asked=asked)


def test_a_stub_that_never_announced_is_refused_naming_the_line_and_the_way_in(
        tmp_path: Path) -> None:
    ses = _stub_session(tmp_path, [], None)
    with pytest.raises(ds.Invalid) as refused:
        inputs.require_stub(ses)
    said = str(refused.value)
    assert "`STUB  . inject` on E9" in said and "[autoexec]" in said, said
    assert "or `start(program=...)` loads it by itself" in said, said
    assert "mounted it on" not in said, said


def test_a_stub_announced_in_the_log_is_read_from_its_start(tmp_path: Path) -> None:
    ses = _stub_session(tmp_path, [f"Bochs port E9h: STUB  . inject device=present "
                                   f"proto={inputs.STUB_PROTOCOL}"], None)
    inputs.require_stub(ses)
    assert ses.stub_protocol == inputs.STUB_PROTOCOL and ses.asked == [0], ses


def test_no_keys_is_refused_saying_send_keys_needs_one() -> None:
    with pytest.raises(ds.Invalid) as none:
        inputs.check_keys([], None)
    assert str(none.value) == "send_keys needs at least one key name", none.value
