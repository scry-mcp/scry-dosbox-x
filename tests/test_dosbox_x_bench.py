"""The bench's own guards; the emulator-driving half is not faked, a double measures itself."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bench
import dosbox_binary as dbinary
import dosbox_launch as dlaunch


def test_the_timer_reads_true_and_its_negative_reads_zero() -> None:
    """The known answer through the same timer, and its negative reads zero."""
    got = bench.validate_timer()
    assert got["ok"] is True, got
    assert isinstance(got["error_pct"], float) and got["error_pct"] < 5.0, got
    assert isinstance(got["negative_ms"], float) and got["negative_ms"] < 1.0, got


def test_a_call_that_answered_nothing_is_not_timed_as_a_fast_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A session that answered nothing is refused, not published as the fastest speed."""
    with pytest.raises(SystemExit) as caught:
        bench.bench("silent", lambda: "", 3, answered=bool)
    assert caught.value.code == bench.INVALID_RC, caught.value.code
    assert "INVALID" in capsys.readouterr().err, "the refusal says what it is, on stderr"


def test_a_call_that_did_answer_is_timed() -> None:
    """The control for the refusal, and the result shape: spread beside the median."""
    got = bench.bench("speaks", lambda: "EAX=00000000", 3, answered=bool)
    assert got["n"] == 3
    assert set(got) == {"median_ms", "min_ms", "max_ms", "n"}, got
    # `isinstance` on each subscript narrows it for mypy; an unchecked key stays `object`.
    lo, mid, hi = got["min_ms"], got["median_ms"], got["max_ms"]
    assert isinstance(lo, float) and isinstance(mid, float) and isinstance(hi, float), got
    assert lo <= mid <= hi, got


def test_the_guests_clock_is_read_as_the_maximum_and_not_the_last(
        tmp_path: Path) -> None:
    """The log is not monotone (boot self-checks precede the clock), so the maximum is read."""
    log = tmp_path / "guest.log"
    log.write_text("[+ 12.500] later\nnoise\n[+  0.125] a boot self-check\n")
    assert bench.newest(log) == 12.5


def test_a_log_that_is_not_there_is_not_a_zero(tmp_path: Path) -> None:
    """An absent or unreadable log answers None, never a 0.0 that would be subtracted."""
    assert bench.newest(tmp_path / "nothing.log") is None
    assert bench.newest(tmp_path) is None          # a directory
    (tmp_path / "empty.log").write_text("no stamps here\n")
    assert bench.newest(tmp_path / "empty.log") is None


def test_the_bench_refuses_without_its_two_inputs_and_names_the_flags(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """The refusal names the flags, not variables, and fires before the timer costs an emulator."""
    monkeypatch.setattr(sys, "argv", ["bench.py"])
    assert bench.main() == 3
    said = capsys.readouterr().err
    assert said.startswith("INVALID"), said
    assert "--conf" in said and "--cwd" in said, said
    # The old environment variables must not arm the run.
    monkeypatch.setenv("DOSBOX_X_LIVE_CONF", __file__)
    monkeypatch.setenv("DOSBOX_X_LIVE_CWD", str(Path(__file__).parent))
    assert bench.main() == 3, "the environment must no longer arm this bench"


def test_one_flag_without_the_other_is_refused_too(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """Control: either flag alone is refused, and both are named."""
    conf = tmp_path / "probe.conf"
    conf.write_text("[sdl]\n")
    for argv in (["bench.py", "--conf", str(conf)], ["bench.py", "--cwd", str(tmp_path)]):
        monkeypatch.setattr(sys, "argv", argv)
        assert bench.main() == 3, argv
        said = capsys.readouterr().err
        assert said.startswith("INVALID") and "--conf" in said and "--cwd" in said, (argv, said)
    # A --conf that is not a file is refused too.
    monkeypatch.setattr(sys, "argv", ["bench.py", "--conf", str(tmp_path / "nope.conf"),
                                      "--cwd", str(tmp_path)])
    assert bench.main() == 3
    assert "INVALID" in capsys.readouterr().err


def test_every_invalid_in_this_file_leaves_with_one_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every INVALID leaves with one exit code, and its message goes to stderr."""
    with pytest.raises(SystemExit) as caught:
        bench.no_measurement("a probe")
    assert caught.value.code == bench.INVALID_RC == 3, caught.value.code
    said = capsys.readouterr()
    assert said.err.strip() == "INVALID: a probe", said
    assert said.out == "", "a refusal does not go out with the figures"
    # Read as syntax: a substring count matches a docstring quoting the old shape.
    tree = ast.parse(Path(bench.__file__).read_text())
    raises = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
              and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "SystemExit"]
    assert raises, "the control: the helper itself still raises one, so this can see one"
    assert len(raises) == 1, (
        f"every stop leaves through `no_measurement`; raises at lines {raises}")
    # The reply contract's source scan reads `invalid` and `refusal` as its own.
    assert not hasattr(bench, "invalid"), "that name belongs to the reply contract"


def test_the_stamp_pattern_matches_what_this_guest_actually_prints() -> None:
    """The stamp pattern matches what the guest prints; a miss makes `newest` answer None."""
    assert bench.STAMP.findall("[+  1.250] something") == ["1.250"]
    assert bench.STAMP.findall("[+1] something") == [], "an integer is not a stamp"
    assert isinstance(bench.STAMP, re.Pattern)


def test_a_timer_that_fails_its_known_answer_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """A sleep that does not sleep reads far off the known answer: the check fails."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    assert bench.validate_timer()["ok"] is False


def _runnable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> None:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench.py", "--conf", str(conf), "--cwd", str(tmp_path),
                                      *extra])


def test_a_failed_timer_publishes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    _runnable(tmp_path, monkeypatch)
    monkeypatch.setattr(bench, "validate_timer", lambda: {
        "known_ms": 250.0, "read_ms": 0.0, "error_pct": 100.0, "negative_ms": 0.0, "ok": False})

    def no_run(*_a: object, **_k: object) -> object:
        raise AssertionError("a measurement ran on a failed timer")
    monkeypatch.setattr(bench, "stamp", no_run)
    assert bench.main() == bench.INVALID_RC
    assert capsys.readouterr().err.startswith("INVALID"), "the failure was not said"


def test_the_published_medians_are_the_runs_medians(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """The headline figures are the medians of what the runs answered."""
    out = tmp_path / "bench.json"
    _runnable(tmp_path, monkeypatch, "--reps", "3", "--json", str(out), "--song", "S")
    monkeypatch.setattr(bench, "validate_timer", lambda: {
        "known_ms": 250.0, "read_ms": 250.0, "error_pct": 0.0, "negative_ms": 0.0, "ok": True})
    monkeypatch.setattr(bench, "stamp", lambda: {"machine": "m", "emulator": "e",
                                                 "load_average": "0"})
    totals, prompts, ups = iter([4.0, 6.0, 5.0]), iter([1.0, 4.0, 3.0]), iter([7.0, 9.0, 8.0])
    monkeypatch.setattr(bench, "batch_cost", lambda cwd, song: {"total_s": next(totals)})
    monkeypatch.setattr(bench, "reach_the_state", lambda conf, cwd: {
        "debugger_prompt_s": next(prompts), "application_up_s": next(ups)})
    monkeypatch.setattr(bench, "per_question", lambda conf, cwd: {})
    monkeypatch.setattr(bench, "advance_rate", lambda conf, cwd: {})
    assert bench.main() == 0
    got = json.loads(out.read_text())
    assert got["batch"]["total_s_median"] == 5.0, got["batch"]
    assert (got["reach"]["debugger_prompt_s_median"],
            got["reach"]["application_up_s_median"]) == (3.0, 8.0), got["reach"]


def test_the_rate_is_the_median_of_the_windows_after_the_settling_sample() -> None:
    """The first sample is dropped; the rate is the median of the windows between the rest."""
    samples = [(0.06, 0.0), (3.06, 3.0), (6.06, 4.0), (9.06, 6.0), (12.06, 8.2)]
    got = bench.window_rates(samples)
    assert (got["rate_median"], got["rate_min"], got["rate_max"]) == (0.667, 0.333, 0.733), got
    assert got["windows"] == 3 and got["discarded_settling_samples"] == 1, got
    assert got["samples"] == [(0.1, 0.0), (3.1, 3.0), (6.1, 4.0), (9.1, 6.0), (12.1, 8.2)], got


def _run_writing(log: Path, text: str | None) -> Any:
    def run(cmd: list[str], **kw: object) -> Any:
        assert cmd == ["make", "prof-log", "SONG=S", "SECS=30"], cmd
        assert kw["cwd"] == str(log.parent.parent) and kw["check"] is False, kw
        assert kw["stdout"] == kw["stderr"] == subprocess.DEVNULL, kw
        if text is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_bytes(text.encode("utf-8", "surrogateescape"))  # not valid UTF-8
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


@pytest.mark.parametrize(("written", "measured"), [
    (f"\udcff{bench.MARKER}\n", True), ("booted, no marker\n", False), (None, False)],
    ids=["answered", "no-marker", "nothing-written"])
def test_a_batch_is_timed_only_when_it_answered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                written: str | None, measured: bool) -> None:
    """A stale log is removed first; a batch is timed only when it answered."""
    log = tmp_path / "build" / "PROF.E9.log"
    log.parent.mkdir()
    log.write_text(f"{bench.MARKER}\n", encoding="utf-8")       # stale
    monkeypatch.setattr("subprocess.run", _run_writing(log, written))
    monkeypatch.setattr(bench, "timed", lambda fn: (9994.0, fn()))
    if measured:
        assert bench.batch_cost(tmp_path, "S") == {"total_s": 9.99}
        return
    with pytest.raises(SystemExit) as e:
        bench.batch_cost(tmp_path, "S")
    assert e.value.code == bench.INVALID_RC


def test_the_stamp_names_the_build_the_ladder_found_and_refuses_one_with_no_version(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The stamp names the ladder's build; a build with no version is refused."""
    bench.build.cache_clear()
    monkeypatch.setattr(dbinary, "resolve",
                        lambda binary: dbinary.Resolved("/opt/dosbox-x", "DOSBOX_X_BINARY"))
    monkeypatch.setattr(dlaunch, "binary_facts",
                        lambda found, _s: {"version": f"DOSBox-X at {found.path}"})
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: SimpleNamespace(stdout="Mac16,10",
                                                                            stderr=""))
    monkeypatch.setattr("os.getloadavg", lambda: (1.0, 2.0, 3.0))
    got = bench.stamp()
    assert got == {"machine": "Mac16,10", "emulator": "DOSBox-X at /opt/dosbox-x",
                   "binary": "/opt/dosbox-x", "binary_origin": "DOSBOX_X_BINARY",
                   "load_average": (1.0, 2.0, 3.0)}, got
    monkeypatch.setattr(dlaunch, "binary_facts",
                        lambda found, _s: {"version": {"available": False,
                                                       "why": "printed nothing"}})
    with pytest.raises(SystemExit) as e:
        bench.stamp()
    assert e.value.code == bench.INVALID_RC
    bench.build.cache_clear()


def test_with_no_song_the_batch_is_not_run_and_the_result_says_why(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no song named the batch is not run; a default would time somebody else's file."""
    out = tmp_path / "bench.json"
    _runnable(tmp_path, monkeypatch, "--reps", "1", "--json", str(out))
    monkeypatch.setattr(bench, "validate_timer", lambda: {
        "known_ms": 250.0, "read_ms": 250.0, "error_pct": 0.0, "negative_ms": 0.0, "ok": True})
    monkeypatch.setattr(bench, "stamp", lambda: {"machine": "m", "emulator": "e",
                                                 "load_average": "0"})

    def no_batch(cwd: Path, song: str) -> dict[str, float]:
        raise AssertionError("the batch ran with no song named")

    monkeypatch.setattr(bench, "batch_cost", no_batch)
    monkeypatch.setattr(bench, "reach_the_state", lambda conf, cwd: {
        "debugger_prompt_s": 1.0, "application_up_s": 2.0})
    monkeypatch.setattr(bench, "per_question", lambda conf, cwd: {})
    monkeypatch.setattr(bench, "advance_rate", lambda conf, cwd: {})
    assert bench.main() == 0
    got = json.loads(out.read_text())
    assert got["batch"] == {"available": False, "why": "no --song named, so no batch was run"}
