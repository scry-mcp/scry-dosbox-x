"""The live tier's own machinery, on no emulator: the matrix's `Ledger` and its `main` (where a
run's scratch goes on every way it ends, the canary that refuses a host, the proof that no
DOSBox-X outlived the run), `run_live_pytest`'s end, and the canary's form."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from scry_core import live_host

import dosbox_binary
import dosbox_x_server  # noqa: F401 -- imports the boundary the shape guard wraps, before the runners

LIVE = Path(__file__).parent / "live"
ROOT = Path(__file__).parents[1]


@pytest.fixture(autouse=True)
def host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The host's temporary directory the test's own, a canary that passes, and what a run sets
    in the environment undone with the case."""
    monkeypatch.syspath_prepend(str(LIVE))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(live_host, "canary", lambda _argv: "")
    for var in (live_host.LEDGER_VAR, live_host.SCRATCH_VAR, "DOSBOX_X_LIVE_SUMMARY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def lm() -> ModuleType:
    return importlib.import_module("matrix_ledger")


def _ledger(lm: ModuleType, *sections: tuple[str, list[str], Any]) -> Any:
    m = lm.Ledger()
    for letter, labels, body in sections:
        m.section(letter, letter, [lm.Cell(x, "test") for x in labels])(
            (lambda b=body: b(m)) if body else (lambda: None))
    return m


def _run(m: Any, summary: Path | None = None, pool: Any = None) -> int:
    rc: int = m.run([], {}, lambda: None, lambda _letter: None, pool=pool, summary=summary)
    return rc


def _launched() -> None:
    """What a job's session does at its spawn: one launch in the ledger the run named, of a
    pid long gone, so the end check has something to examine and finds it not alive; outside
    a run that named one, a session records nothing."""
    if (ledger := live_host.EmulatorLedger.from_environment()) is not None:
        ledger.record(99999999, "dosbox-x")


def _pool(lm: ModuleType, outcomes: dict[str, str], invalid: str = "") -> Any:
    lp = lm.live_pool

    def run(_sections: Any) -> Any:
        _launched()
        return lp.PoolResult([], invalid, outcomes, {})
    return run


def _out(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().out.rstrip().splitlines()


def test_a_ledger_makes_no_directory_until_the_run_writes(lm: ModuleType, tmp_path: Path) -> None:
    m = lm.Ledger()
    assert not m.scratch.exists() and list(tmp_path.iterdir()) == []
    m.unfinished()
    assert list(tmp_path.iterdir()) == []


def test_a_green_run_removes_its_scratch_and_its_jobs(
        lm: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m = _ledger(lm, ("A", ["a1"], None), ("B", ["b1"], None))
    for letter in "AB":
        job = Path(m.host.job_env(letter)[live_host.SCRATCH_VAR])
        job.mkdir(parents=True)
        assert job.parent.parent == m.scratch
    m.host.begin(None, "DOSBox-X")
    assert _run(m, pool=_pool(lm, {"a1": "OK", "b1": "OK"})) == lm.EXIT_PASS
    assert "scratch removed, the transcript with it" in _out(capsys)
    assert list(tmp_path.iterdir()) == []


def test_a_red_run_keeps_its_scratch_and_names_it_before_its_verdict(
        lm: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    m = _ledger(lm, ("C", ["c1"], lambda m: m.judge("c1", False)))
    assert _run(m) == lm.EXIT_FAIL
    assert _out(capsys)[-2:] == [f"kept: {m.scratch}", "==> LIVE MATRIX FAILED"]


def test_a_pooled_job_leaves_its_scratch_to_its_parent_and_proves_nothing(
        lm: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("DOSBOX_X_LIVE_SUMMARY", str(tmp_path / "summary.json"))
    monkeypatch.setenv(live_host.LEDGER_VAR, str(tmp_path / "the parents.tsv"))
    monkeypatch.setattr(live_host.EmulatorLedger, "reap", lambda _s: pytest.fail("a job reaped"))
    m = _ledger(lm, ("A", ["a1"], lambda m: m.judge("a1", True)))
    assert m.host.job and m.host.begin(["dosbox-x"], "DOSBox-X") == ""
    assert _run(m, summary=tmp_path / "summary.json") == lm.EXIT_PASS
    out = "\n".join(_out(capsys))
    assert "scratch removed" not in out and "kept:" not in out and m.scratch.is_dir()


@pytest.mark.parametrize(("plan", "pool"), [
    ([("A", ["a1"], None), ("B", ["a1"], None)], None),
    ([("A", ["a1"], lambda m: m.block("a1", "no bench"))], None),
    ([("A", ["a1"], None), ("B", ["b1"], None)], ("a job declared a cell nobody planned",)),
], ids=["a cell planned twice", "no cell ran", "a pool that cannot be believed"])
def test_a_run_that_ends_invalid_keeps_its_scratch_and_says_invalid_last(
        lm: ModuleType, capsys: pytest.CaptureFixture[str], plan: list[Any],
        pool: tuple[str] | None) -> None:
    m = _ledger(lm, *plan)
    m.made()
    pooled = _pool(lm, {"a1": "OK", "b1": "OK"}, pool[0]) if pool else None
    assert _run(m, pool=pooled) == lm.EXIT_INVALID
    m.unfinished()  # what `main`'s `finally` runs
    out = _out(capsys)
    assert out[-2] == f"kept: {m.scratch}" and out[-1].startswith("==> LIVE MATRIX INVALID")


def test_a_run_that_breaks_half_way_keeps_its_scratch_and_names_it(
        lm: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    def interrupted(_m: Any) -> None:
        raise KeyboardInterrupt
    m = _ledger(lm, ("A", ["a1"], interrupted))
    with pytest.raises(KeyboardInterrupt):
        _run(m)
    m.unfinished()
    assert f"kept: {m.scratch}" in _out(capsys)


def test_an_emulator_that_outlived_the_run_fails_it_by_name_beside_the_verdict(
        lm: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    m = _ledger(lm, ("A", ["a1"], lambda m: m.judge("a1", True)))
    m.host.begin(["dosbox-x"], "DOSBox-X")
    assert os.environ[live_host.LEDGER_VAR] == str(m.scratch / live_host.LEDGER_NAME)
    order: list[str] = []
    m.on_end = lambda: order.append("close")

    def reap(_self: Any) -> Any:
        order.append("reap")
        return live_host.Leftovers(1, 1, ((77, "U"),))
    monkeypatch.setattr(live_host.EmulatorLedger, "reap", reap)
    assert _run(m) == lm.EXIT_FAIL
    out = "\n".join(_out(capsys))
    assert order == ["close", "reap"]
    assert "FAIL  1 emulator(s) outlived the run" in out and "pid 77 state U" in out
    assert out.endswith("==> LIVE MATRIX FAILED")


# ================================================================ the matrix's `main`


@pytest.fixture
def matrix(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The matrix's entry script, its sections registered and none of them run."""
    module = importlib.import_module("dosbox_x_live_matrix")
    monkeypatch.setattr(module.signal, "signal", lambda *_a: None)
    monkeypatch.setattr(module, "ENV", {})
    fresh = importlib.import_module("matrix_ledger").Ledger()
    fresh.sections = module.M.sections
    monkeypatch.setattr(module, "M", fresh)
    monkeypatch.setattr(fresh, "run", lambda *_a, **_k: pytest.fail("a section ran"))
    return module


@pytest.mark.parametrize(("argv", "env", "code"), [
    (["m", "extra"], {}, 2),
    (["m"], {"DOSBOX_X_LIVE_SECTIONS": "Z"}, 3),
    (["m"], {"DOSBOX_X_LIVE_JOBS": "none"}, 2),
], ids=["an argument", "a section that is none", "a job count that is none"])
def test_a_matrix_that_stops_before_its_start_leaves_nothing(
        matrix: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        argv: list[str], env: dict[str, str], code: int) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(matrix, "ENV", env)
    monkeypatch.setattr(live_host, "canary", lambda _argv: pytest.fail("a canary launched"))
    assert matrix.main() == code
    assert list(tmp_path.iterdir()) == []


def test_a_matrix_on_a_host_that_cannot_start_dosbox_x_is_invalid_and_makes_nothing(
        matrix: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["m"])
    monkeypatch.setattr(dosbox_binary, "canary_for", lambda _b="": ["/opt/dosbox-x"])
    monkeypatch.setattr(live_host, "canary", lambda _argv: "dosbox-x (pid 5) did not return")
    assert matrix.main() == matrix.EXIT_INVALID
    assert _out(capsys)[-1] == (
        "==> LIVE MATRIX INVALID: host canary: dosbox-x (pid 5) did not return")
    assert list(tmp_path.iterdir()) == []


def test_a_matrix_that_breaks_goes_through_the_runs_end(
        matrix: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    def broken(*_a: Any, **_k: Any) -> int:
        matrix.M.made()
        raise RuntimeError("a section's own defect")
    monkeypatch.setattr(sys, "argv", ["m"])
    monkeypatch.setattr(matrix.M, "run", broken)
    monkeypatch.setattr(dosbox_binary, "canary_for", lambda _b="": None)
    with pytest.raises(RuntimeError):
        matrix.main()
    assert f"kept: {matrix.M.scratch}" in _out(capsys)


def test_the_pool_hands_each_job_a_scratch_inside_the_runs(
        matrix: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    lp = matrix.live_pool
    seen: list[Any] = []

    def run_pool(jobs: list[Any], *_a: Any, **_k: Any) -> Any:
        seen.extend(jobs)
        return lp.PoolResult([], "", {}, {})
    monkeypatch.setattr(lp, "run_pool", run_pool)
    matrix._pool(2)([s for s in matrix.M.sections if s.letter in "AB"])
    assert seen and all(Path(j.env[live_host.SCRATCH_VAR]).parent.parent == matrix.M.scratch
                        for j in seen)


def test_each_job_s_copies_go_as_that_job_ends_not_at_the_pool_s_end(
        matrix: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The pool's hook removes a job's copies the moment that job ends, so they never pile up
    for the length of the run; the pool's own end removes what a killed job left."""
    lp = matrix.live_pool
    private = importlib.import_module("live_private")
    gone_by_then: list[bool] = []

    def run_pool(jobs: list[Any], *_a: Any, on_done: Any = None, **_k: Any) -> Any:
        for job in jobs:
            mine = Path(job.env[private.PRIVATE_VAR])
            mine.mkdir(parents=True)
            (mine / "copy").write_text("x")
            on_done(lp.JobResult(job, 0, tmp_path / "log", 0.0, None))
            gone_by_then.append(not mine.exists())
        return lp.PoolResult([], "", {}, {})

    monkeypatch.setattr(lp, "run_pool", run_pool)
    matrix._pool(2)([s for s in matrix.M.sections if s.letter in "AB"])
    assert gone_by_then == [True, True], gone_by_then


# ================================================================ run_live_pytest's end


@pytest.fixture
def rlp(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """`run_live_pytest` collecting one test, its pool answering it OK, its canary passing."""
    module = importlib.import_module("run_live_pytest")
    monkeypatch.setattr(module, "_collect", lambda marks: ["t.py::a"] if "not" in marks else [])
    monkeypatch.setattr(module.signal, "signal", lambda *_a: None)
    monkeypatch.setattr(sys, "argv", ["run_live_pytest.py"])
    monkeypatch.delenv(module.JOBS_VAR, raising=False)
    lp = module.live_pool
    def run(*_a: Any, **_k: Any) -> Any:
        _launched()
        return lp.PoolResult([], "", {"t.py::a": "OK"}, {})
    monkeypatch.setattr(lp, "run_pool", run)
    return module


def test_the_pytest_tier_refuses_a_host_that_cannot_start_dosbox_x_before_collecting(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(dosbox_binary, "canary_for", lambda _b="": ["/opt/dosbox-x"])
    monkeypatch.setattr(live_host, "canary", lambda _argv: "dosbox-x did not return")
    monkeypatch.setattr(rlp, "_collect", lambda _m: pytest.fail("collected on a refused host"))
    assert rlp.main() == rlp.EXIT_INVALID
    assert _out(capsys)[-1] == "==> LIVE PYTEST INVALID: host canary: dosbox-x did not return"
    assert list(tmp_path.iterdir()) == []


def test_the_pytest_tier_fails_on_an_emulator_its_tests_left_alive(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(live_host.EmulatorLedger, "reap",
                        lambda _self: live_host.Leftovers(1, 1))
    assert rlp.main() == rlp.EXIT_FAIL
    out = "\n".join(_out(capsys))
    assert "FAIL  1 emulator(s) outlived the run" in out and "kept: " in out


def test_the_pytest_tier_green_leaves_nothing(rlp: ModuleType, tmp_path: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    assert rlp.main() == rlp.EXIT_PASS
    assert "scratch removed, the transcript with it" in _out(capsys)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("broken", ["the pool", "the proof"])
def test_the_pytest_tier_that_breaks_keeps_its_logs_and_still_proves_its_emulators_gone(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], broken: str) -> None:
    reaped: list[bool] = []

    def reap(_self: Any) -> Any:
        reaped.append(True)
        if broken == "the proof":
            raise OSError("ps answered rc=1")
        return live_host.Leftovers()
    monkeypatch.setattr(live_host.EmulatorLedger, "reap", reap)
    if broken == "the pool":
        def stopped(*_a: Any, **_k: Any) -> Any:
            raise KeyboardInterrupt
        monkeypatch.setattr(rlp.live_pool, "run_pool", stopped)
        with pytest.raises(KeyboardInterrupt):
            rlp.main()
    else:
        assert rlp.main() == rlp.EXIT_FAIL
    out = "\n".join(_out(capsys))
    assert reaped == [True] and "kept: " in out


def test_nothing_collected_ends_the_run_before_its_invalid(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(rlp, "_collect", lambda _m: [])
    assert rlp.main() == rlp.EXIT_INVALID
    assert _out(capsys)[-1] == (
        "==> LIVE PYTEST INVALID: no live test was collected, so there is no verdict")


# ================================================================ the canary's form


def test_the_canary_is_the_resolved_binary_in_a_form_that_ends_by_itself(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dosbox_binary, "resolve",
                        lambda _b: dosbox_binary.Resolved("/opt/dosbox-x", "PATH"))
    assert dosbox_binary.canary_for() == ["/opt/dosbox-x", "-defaultconf", "-fastlaunch", "-set",
                                          "sdl videodriver=dummy", "-exit"]


def test_no_binary_is_no_canary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(dosbox_binary.VARIABLE, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert dosbox_binary.canary_for() is None


def test_the_bricks_demo_refuses_a_host_that_cannot_start_dosbox_x(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "demos" / "bricks"))
    demo = importlib.import_module("demo")
    monkeypatch.setattr(demo, "unplaced", lambda _where: "")
    monkeypatch.setattr(dosbox_binary, "canary_for", lambda _b="": ["/opt/dosbox-x"])
    monkeypatch.setattr(live_host, "canary", lambda _argv: "dosbox-x did not return")
    assert demo.precheck(demo.Run(dir=ROOT, options={})) == "dosbox-x did not return"
    monkeypatch.setattr(dosbox_binary, "canary_for", lambda _b="": None)
    assert demo.precheck(demo.Run(dir=ROOT, options={})) == ""


def test_a_green_pytest_tier_that_launched_no_emulator_is_invalid(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    lp = rlp.live_pool
    monkeypatch.setattr(lp, "run_pool",
                        lambda *_a, **_k: lp.PoolResult([], "", {"t.py::a": "OK"}, {}))
    assert rlp.main() != rlp.EXIT_PASS
    assert any("the ledger recorded no emulator launch" in line for line in _out(capsys))


def test_each_pytest_job_runs_in_a_basetemp_of_its_own_and_leaves_it_behind(
        rlp: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """pytest keeps only the newest few `pytest-<n>` directories under the temporary directory
    every job shares, so a job beside others deleted a running job's `tmp_path`: each child
    hands pytest a basetemp of its own, and removes it as it ends."""
    seen: list[Path] = []

    def main(args: list[str], plugins: list[Any]) -> int:
        at = Path(args[args.index("--basetemp") + 1])
        assert at.is_dir() and at.is_relative_to(tmp_path), at
        seen.append(at)
        return 0

    monkeypatch.setattr(rlp.pytest, "main", main)
    monkeypatch.chdir(tmp_path)
    for n in (1, 2):
        rlp._child(tmp_path / f"summary-{n}.json", [f"tests/live/x.py::t{n}"])
    assert len(seen) == 2 and seen[0] != seen[1], seen
    assert not any(p.exists() for p in seen), "a job's basetemp outlived it"
