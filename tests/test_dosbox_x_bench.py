"""The shipped measuring instrument's own guards, at the contract tier.

`bench.py` is INFRASTRUCTURE, not a scratch script: it publishes the figures this
server's cost claims rest on. It carries its own known-answer validation, and until
this file existed NOTHING RAN IT except a live bench somebody launched by hand -- so
the instrument that exists to stop a number lying was itself ungated. Measured: 0%
coverage, `CoverageWarning: Module bench was never imported`.

What is here is the half a contract tier can reach: the timer's known answer with its
negative, and the refusal that stops a session which answered NOTHING being published
as a fast one. The emulator-driving half (`reach_the_state`, `per_question`,
`advance_rate`) is out of reach by construction and is not faked, because a double for
the thing being measured measures the double.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path

import pytest

import bench


def test_the_timer_reads_true_and_its_negative_reads_zero() -> None:
    """The known answer, through the SAME timer every figure comes from.

    Both halves are needed and neither substitutes for the other: without the known
    answer every number below is a reading with no evidence the clock is honest, and
    without the negative a call that DID NOTHING and a call that was genuinely fast
    print the same thing.
    """
    got = bench.validate_timer()
    assert got["ok"] is True, got
    assert isinstance(got["error_pct"], float) and got["error_pct"] < 5.0, got
    assert isinstance(got["negative_ms"], float) and got["negative_ms"] < 1.0, got


def test_a_call_that_answered_nothing_is_not_timed_as_a_fast_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`answered` is REQUIRED, and this is why.

    `Session.command` returns "" when the screen said nothing at all -- not an
    exception, so nothing else refuses it. A bench without this guard times a session
    that answered nothing and publishes the result as a SPEED, which is the fastest
    number the instrument can possibly produce and the only one that means nothing.
    """
    with pytest.raises(SystemExit) as caught:
        bench.bench("silent", lambda: "", 3, answered=bool)
    assert caught.value.code == bench.INVALID_RC, caught.value.code
    assert "INVALID" in capsys.readouterr().err, "the refusal says what it is, on stderr"


def test_a_call_that_did_answer_is_timed() -> None:
    """The control. A refusal test on its own passes when the guard refuses EVERYTHING.

    It also pins the SHAPE of a result: the spread is published beside the median,
    because one number with no spread cannot be told from one sample.
    """
    got = bench.bench("speaks", lambda: "EAX=00000000", 3, answered=bool)
    assert got["n"] == 3
    assert set(got) == {"median_ms", "min_ms", "max_ms", "n"}, got
    # THE MEDIAN IS TYPE-ASSERTED NOW, and its two neighbours already were. That is the
    # whole of it, and this comment first claimed something FALSE and more interesting:
    # that an `isinstance` on a subscript "narrows NOTHING". It narrows fine --
    # `assert isinstance(d["a"], float)` then `reveal_type(d["a"])` gives `float` while
    # an unchecked key gives `object`, measured. Which is exactly why mypy reported two
    # errors and not three: `min_ms` and `max_ms` WERE narrowed and the median simply
    # was never checked. The locals are for readability; the fix is the third
    # `isinstance`.
    lo, mid, hi = got["min_ms"], got["median_ms"], got["max_ms"]
    assert isinstance(lo, float) and isinstance(mid, float) and isinstance(hi, float), got
    assert lo <= mid <= hi, got


def test_the_guests_clock_is_read_as_the_maximum_and_not_the_last(
        tmp_path: Path) -> None:
    """THE LOG IS NOT MONOTONE, so "the last stamp" is not "the latest time".

    This guest emits its boot self-checks before the profiler's clock starts, so a
    reader taking the final line goes BACKWARDS at boot. That is also why
    `advance_rate` may not quote monotonicity as evidence of anything -- taking the
    maximum makes a sequence of these non-decreasing by construction.
    """
    log = tmp_path / "guest.log"
    log.write_text("[+ 12.500] later\nnoise\n[+  0.125] a boot self-check\n")
    assert bench.newest(log) == 12.5


def test_a_log_that_is_not_there_is_not_a_zero(tmp_path: Path) -> None:
    """An absent or unreadable log answers None, never a time.

    A 0.0 would read as "the guest's clock is at zero", which is a MEASUREMENT, and
    the caller would subtract it from something.
    """
    assert bench.newest(tmp_path / "nothing.log") is None
    assert bench.newest(tmp_path) is None          # a directory: OSError, not a crash
    (tmp_path / "empty.log").write_text("no stamps here\n")
    assert bench.newest(tmp_path / "empty.log") is None


def test_the_bench_refuses_without_its_two_inputs_and_names_the_flags(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """THE REFUSAL NAMES WHAT THE CALLER TYPED. Both inputs used to arrive by environment
    while this same parser already took three flags, so a caller who misspelled one got a
    run against somebody else's program instead of a refusal; and a refusal that named
    variables sent them looking in the wrong place. It fires BEFORE the timer's known
    answer, so a run with no program to measure costs no emulator."""
    monkeypatch.setattr(sys, "argv", ["bench.py"])
    assert bench.main() == 3
    said = capsys.readouterr().err
    assert said.startswith("INVALID"), said
    assert "--conf" in said and "--cwd" in said, said
    # AND THE VARIABLES ARE GONE: setting them does not arm the run any more, which is the
    # whole point of the move. Without this the old door could stay open unnoticed.
    monkeypatch.setenv("DOSBOX_X_LIVE_CONF", __file__)
    monkeypatch.setenv("DOSBOX_X_LIVE_CWD", str(Path(__file__).parent))
    assert bench.main() == 3, "the environment must no longer arm this bench"


def test_one_flag_without_the_other_is_refused_too(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    """THE CONTROL FOR THE CASE ABOVE, and it is what stops the guard passing on either
    input alone: both are required, and a bench given a config with no working directory
    would run it from wherever the caller happened to stand."""
    conf = tmp_path / "probe.conf"
    conf.write_text("[sdl]\n")
    for argv in (["bench.py", "--conf", str(conf)], ["bench.py", "--cwd", str(tmp_path)]):
        monkeypatch.setattr(sys, "argv", argv)
        assert bench.main() == 3, argv
        said = capsys.readouterr().err
        # THE MESSAGE IS ASSERTED HERE TOO, not just the code: half a pair is the case where a
        # caller is most likely to have typed the OTHER flag wrong, so the refusal has to name
        # both of them rather than only the one that is missing.
        assert said.startswith("INVALID") and "--conf" in said and "--cwd" in said, (argv, said)
    # AND A --conf THAT IS NOT A FILE is refused as surely as a missing one: the check is
    # what the path IS, not that the caller typed something.
    monkeypatch.setattr(sys, "argv", ["bench.py", "--conf", str(tmp_path / "nope.conf"),
                                      "--cwd", str(tmp_path)])
    assert bench.main() == 3
    assert "INVALID" in capsys.readouterr().err


def test_every_invalid_in_this_file_leaves_with_one_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ONE SPELLING PER CONCEPT, and this one had two. `main`'s own guards returned 3 while
    every other INVALID raised `SystemExit` with a STRING, which CPython prints and exits 1
    on: measured, with its control (`SystemExit(3)` gives 3, `SystemExit("...")` gives 1). A
    caller reading the code rather than the text got two answers to one question.

    The message goes to STDERR, because a diagnostic that shares a channel with the figures
    is a diagnostic somebody's parser reads as data."""
    with pytest.raises(SystemExit) as caught:
        bench.no_measurement("a probe")
    assert caught.value.code == bench.INVALID_RC == 3, caught.value.code
    said = capsys.readouterr()
    # THE PREFIX IS THE HELPER'S. Nine sites used to write it by hand, which is nine chances
    # to spell it differently and a caller grepping for it finding eight.
    assert said.err.strip() == "INVALID: a probe", said
    assert said.out == "", "a refusal does not go out with the figures"
    # AND NO RAW `SystemExit` SURVIVES: a tenth site added later would be the drift again,
    # and this is the only thing that would notice. READ AS SYNTAX, not as text, for the
    # reason this package's own code scan is an AST walk: a substring count answers about a
    # docstring that QUOTES the old shape, and misses a live one wrapped across two lines.
    tree = ast.parse(Path(bench.__file__).read_text())
    raises = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
              and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "SystemExit"]
    assert raises, "the control: the helper itself still raises one, so this can see one"
    assert len(raises) == 1, (
        f"every stop leaves through `no_measurement`; raises at lines {raises}")
    # AND THE NAME IS NOT THE CONTRACT'S. `Invalid`, `invalid` and `refusal` are what the
    # reply contract's source scan reads as a refusal carrying a code from its table; a
    # function here wearing one is read as one, and the scan said so when it did.
    assert not hasattr(bench, "invalid"), "that name belongs to the reply contract"


def test_the_stamp_pattern_matches_what_this_guest_actually_prints() -> None:
    """The one literal in the instrument that a rename elsewhere can silently break.

    A pattern that matches nothing makes `newest` answer None forever, which the
    caller reads as "no log", and the bench then measures a guest it believes is not
    running.
    """
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
    """The instrument's wiring, its measurements doubled: the headline figures are the medians
    of what the runs answered."""
    out = tmp_path / "bench.json"
    _runnable(tmp_path, monkeypatch, "--reps", "3", "--json", str(out))
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
