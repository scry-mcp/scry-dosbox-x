"""The ReChip! demo's DOSBox-X binding, without an emulator: the checkout it needs and what its
log checks accept."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed

from demos.host import NORMAL_CORE
from demos.rechip import demo


def _checkout(folder: Path, *, built: bool = True) -> Path:
    for p in (demo.PROFILE, *(demo.BUILT if built else ())):
        (folder / p).parent.mkdir(parents=True, exist_ok=True)
        (folder / p).write_text("{}")
    return folder


@pytest.fixture(autouse=True)
def placed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo, "precheck", lambda run: "")


def test_the_demo_needs_a_built_checkout(tmp_path: Path) -> None:
    assert demo.checked(Run(dir=tmp_path)).startswith("pass --cwd")
    unbuilt = _checkout(tmp_path / "unbuilt", built=False)
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(unbuilt)})).startswith(
        "no build/RECHIPD.EXE or build/mcp.conf or build/RECHIPD.SYM")
    built = _checkout(tmp_path / "built")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(built)})) == ""


def test_the_call_adds_only_the_run_s_own_to_the_recipe(tmp_path: Path) -> None:
    built = _checkout(tmp_path / "built")
    assert demo.boot(Run(dir=tmp_path, options={"cwd": str(built)})) == {
        "profile": str(built / demo.PROFILE), "shared": True, "background": True,
        "display": 0, "symbols": str(built / demo.SYMBOLS), "flags": NORMAL_CORE,
        "captures_dir": str(tmp_path / "rechip-captures")}


def test_a_resume_must_leave_the_guest_running(tmp_path: Path) -> None:
    assert demo.released("on")(Reply({"session": {"running": True}}), Run(dir=tmp_path)) == "on"
    with pytest.raises(StepFailed, match="did not run"):
        demo.released("on")(Reply({"session": {"running": False}}), Run(dir=tmp_path))


def test_the_host_s_own_refusal_comes_first(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo, "precheck", lambda run: "no dosbox-x here")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(tmp_path)})) == "no dosbox-x here"


@pytest.mark.parametrize(("line", "pattern"), [
    ("[+   8.188] PERF  . audio play=1 rate=44100", demo.SOUNDING),
    ("[+  12.004] ACT   . play=0", demo.PAUSED),
    ("[+   8.298] ACT   . rewind", demo.REWOUND),
    ("[+   9.176] PERF  . fps=50 buf=11/10 rend=0ticks", demo.REPORT),
    ("[+  20.100] ask opens action=1 'Quit'", demo.ASKED),
    ("[+  21.300] ask res=1 action=1", demo.CONFIRMED),
])
def test_each_pattern_matches_the_line_the_program_writes(line: str, pattern: str) -> None:
    assert re.search(pattern, line), (pattern, line)


def test_a_wait_must_reach_its_target(tmp_path: Path) -> None:
    assert demo.targeted("up")(Reply({"verdict": "TARGET"}), Run(dir=tmp_path)) == "up"
    with pytest.raises(StepFailed, match="verdict TIMEOUT"):
        demo.targeted("up")(Reply({"verdict": "TIMEOUT", "note": "no line"}), Run(dir=tmp_path))


def test_the_report_is_waited_for_past_where_the_recipe_s_log_ends(tmp_path: Path) -> None:
    built = _checkout(tmp_path / "built")
    (built / demo.PROFILE).write_text('{"logfile": "${root}/logs/e9.log"}')
    (built / "logs").mkdir()
    (built / "logs" / "e9.log").write_bytes(b"x" * 1234)
    args = demo.next_report(Run(dir=tmp_path, options={"cwd": str(built)}))
    assert args["since_mark"] == 1234 and args["pattern"] == demo.REPORT


@pytest.mark.parametrize(("ticks", "ms"), [
    (0, 600),       # dark from 0 ms: the lit half is 400 to 800
    (40, 1000),     # lit from 400 ms: the next lit half is 1200 to 1600
    (79, 610),      # lit, near its end: the same next half
    (80, 600),      # dark from 800 ms
])
def test_the_run_ends_in_the_middle_of_the_next_lit_half(tmp_path: Path, ticks: int,
                                                        ms: int) -> None:
    run = Run(dir=tmp_path, replies={"ticks": Reply({"hex": ticks.to_bytes(4, "little").hex()})})
    to = demo.into_lit(run)["milliseconds"]
    assert to == ms
    end = ticks * demo.TICK_MS + to
    assert (end // demo.PULSE_MS) % 2 == 1 and end % demo.PULSE_MS == demo.PULSE_MS // 2


def test_the_look_check_names_the_screen_it_wanted(tmp_path: Path) -> None:
    check = demo.on_look("warning_lit")
    assert "warning_lit" in check(Reply({"screen": "warning_lit"}), Run(dir=tmp_path))
    with pytest.raises(StepFailed, match="not warning_lit"):
        check(Reply({"matched": False}), Run(dir=tmp_path))


def test_every_step_name_is_unique() -> None:
    names = [s.name for s in demo.DEMO.steps]
    assert len(names) == len(set(names)), "a step name is the key its reply is kept by"
