"""The live pytest tier through `scry_core.live_pool`: every live test that opens no window runs
as a job of its own, at most `DOSBOX_X_LIVE_JOBS` at once (unset, half the host's CPUs), and the
`windowed` ones after them, together and one after another, because a window that opens in
front takes the focus and would judge its neighbours.

    timeout 3600 uv run python tests/live/run_live_pytest.py      # from the clone's root

The emulator is `DOSBOX_X_BINARY`'s, else the PATH's `dosbox-x`; the saved-state case needs one
that carries SAVESTATE and LOADSTATE and is BLOCKED by any
other, by that build's own refusal.

Each job is pytest run in its own process on its tests, which records every test's outcome by
node id (passed OK, failed or errored FAIL, skipped BLOCKED with the reason) and declares them
as the job's summary. One line per job as it ends, then every test that did not pass and the
count. Before any of it, a canary refuses a host that cannot start DOSBox-X; after it, every
DOSBox-X the tests launched (recorded in a ledger of the run's own, `scry_core.live_bench`) is
proved gone, and one still alive is killed and FAILS the run. Exit 0 with every test OK or
BLOCKED, 1 with any FAIL, 3 when nothing was collected, the host refused or the merge cannot be
believed, 2 for an argument (it takes none) or a job count that is none.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import live_private  # isort: skip -- first: a pooled job's working copies (`live_private`)
import pytest
from scry_core import live_host, live_pool

import dosbox_binary  # isort: skip -- a module of the repository root, installed in its environment

ROOT = Path(__file__).resolve().parents[2]
JOBS_VAR = "DOSBOX_X_LIVE_JOBS"
SUMMARY_VAR = "DOSBOX_X_LIVE_SUMMARY"
# The node ids a child runs, one per line; set by the parent, never by hand.
NODES_VAR = "DOSBOX_X_LIVE_PYTEST_NODES"
PYTEST_ARGS = ["-q", "--no-cov", "-p", "no:cacheprovider", "-m", "live"]
EXIT_PASSED, EXIT_FAILED, EXIT_INVALID = 0, 1, 3
SCRATCH_PREFIX = "dosbox-x-live-pytest-"


class _Outcomes:
    """The pytest plugin a child runs with: each test's outcome, from its own reports."""

    def __init__(self) -> None:
        self.outcomes: dict[str, live_pool.Outcome] = {}
        self.reasons: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        node = report.nodeid
        if report.failed:
            self.outcomes[node] = "FAIL"
            last = report.longreprtext.strip().splitlines()[-1:] or ["no detail"]
            self.reasons[node] = f"{report.when}: {last[0]}"
        elif report.skipped and self.outcomes.get(node) != "FAIL":
            self.outcomes[node] = "BLOCKED"
            longrepr: Any = report.longrepr
            self.reasons[node] = str(longrepr[-1] if isinstance(longrepr, tuple) else longrepr)
        elif report.when == "call" and node not in self.outcomes:
            self.outcomes[node] = "OK"


def _child(summary: Path, nodes: list[str]) -> int:
    os.chdir(ROOT)      # the node ids are the root's, whatever directory the run began in
    began = time.monotonic()
    seen = _Outcomes()
    # A BASETEMP OF THE JOB'S OWN: pytest keeps only the newest few `pytest-<n>` directories
    # under its user's root in the temporary directory every job shares, so a job starting
    # beside others deletes a running job's `tmp_path`.
    basetemp = Path(tempfile.mkdtemp(prefix="dosbox-x-live-pytest-tmp-"))
    # THE NODE IDS GO LAST: the repository's `addopts` ends in `--cov`, whose value is optional,
    # so a node id right after it is taken as the coverage source and pytest runs every test.
    try:
        rc = pytest.main([*PYTEST_ARGS, "--basetemp", str(basetemp), *nodes], plugins=[seen])
    finally:
        shutil.rmtree(basetemp, ignore_errors=True)
    outcomes = {n: seen.outcomes.get(n, "FAIL") for n in nodes}
    reasons = {n: seen.reasons.get(n, f"never reported (pytest exit {rc})")
               for n, o in outcomes.items() if o != "OK"}
    live_pool.write_summary(summary, live_pool.Summary(
        tuple(nodes), outcomes, reasons, "", round(time.monotonic() - began, 3)))
    return int(rc)


def _collect(marks: str) -> list[str] | None:
    """The node ids pytest collects under `marks`, or None when collecting failed."""
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov",
                           "-p", "no:cacheprovider", "-m", marks], cwd=ROOT,
                          capture_output=True, text=True, check=False)
    if done.returncode not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        print(f"INVALID: collecting `{marks}` exited {done.returncode}:\n{done.stdout[-2000:]}"
              f"{done.stderr[-2000:]}", file=sys.stderr)
        return None
    return [ln for ln in done.stdout.splitlines() if "::" in ln and not ln.startswith(" ")]


def _jobs(nodes: list[str], prefix: str, together: bool,
          copies: live_private.Copies) -> list[live_pool.Job]:
    me = [sys.executable, str(Path(__file__).resolve())]
    groups = [nodes] if together else [[n] for n in nodes]
    return [live_pool.Job(f"{prefix}{i:03d}", me,
                          env={NODES_VAR: "\n".join(g), **copies.env(f"{prefix}{i:03d}")},
                          planned=tuple(g)) for i, g in enumerate(groups, 1) if g]


def _leave(signum: int, _frame: object) -> None:
    """`timeout` ends a run with SIGTERM and a closed terminal with SIGHUP: turned into an exit,
    the pool's stop reaches the children, which run in process groups of their own."""
    raise SystemExit(128 + signum)


def main() -> int:
    # SIGHUP is POSIX's; Windows has SIGTERM alone.
    for sig in (signal.SIGTERM, getattr(signal, "SIGHUP", signal.SIGTERM)):
        signal.signal(sig, _leave)
    if sys.argv[1:]:
        print(f"usage: {sys.argv[0]} (no arguments; see the docstring for the variables)",
              file=sys.stderr)
        return 2
    if summary := os.environ.get(SUMMARY_VAR, ""):
        return _child(Path(summary), os.environ.get(NODES_VAR, "").splitlines())
    held = os.environ.get(JOBS_VAR, "").strip()
    if held and not (held.isascii() and held.isdigit() and int(held) >= 1):
        print(f"{JOBS_VAR}={held!r} is not a job count: a whole number, at least 1",
              file=sys.stderr)
        return 2
    workers = int(held) if held else live_pool.default_workers()
    run = live_host.LiveRun.for_process(SCRATCH_PREFIX, job=False)
    if why := run.begin(dosbox_binary.canary_for(), "DOSBox-X"):
        print(f"==> LIVE PYTEST INVALID: {why}", flush=True)
        return EXIT_INVALID
    # EVERY EXIT GOES THROUGH THE RUN'S END: one that never reached its verdict (a collection
    # that failed, an exception, a signal made an exit) still proves its emulators gone and keeps
    # its logs, named.
    try:
        return _run(run, workers)
    finally:
        run.unfinished(lambda: None)


def _run(run: live_host.LiveRun, workers: int) -> int:
    pooled, windowed = _collect("live and not windowed"), _collect("live and windowed")
    if pooled is None or windowed is None:
        return EXIT_INVALID
    if not pooled and not windowed:
        run.unfinished(lambda: None)
        print("==> LIVE PYTEST INVALID: no live test was collected, so there is no verdict")
        return EXIT_INVALID
    out = run.made()
    print(f"jobs: {workers} at once, then {len(windowed)} windowed in turn; logs in {out}",
          flush=True)

    def ended(r: live_pool.JobResult) -> None:
        copies.ended(r.job.name)
        bad = [n for n, o in r.outcomes().items() if o != "OK"]
        word = "FAIL" if any(o == "FAIL" for o in r.outcomes().values()) else (
            "BLOCKED" if bad else "OK")
        print(f"  {word:<7}  {r.job.name}  {r.elapsed_s:.0f} s  "
              f"{', '.join(r.job.planned) if len(r.job.planned) == 1 else ''}", flush=True)

    began = time.monotonic()
    results = []
    with live_private.copies_of_jobs() as copies:
        if pooled:
            results.append(live_pool.run_pool(_jobs(pooled, "p", False, copies), workers, out,
                                              SUMMARY_VAR, on_done=ended))
        if windowed:
            results.append(live_pool.run_pool(_jobs(windowed, "w", True, copies), 1, out,
                                              SUMMARY_VAR, on_done=ended))
    outcomes = {k: v for r in results for k, v in r.outcomes.items()}
    reasons = {k: v for r in results for k, v in r.reasons.items()}
    for node, outcome in outcomes.items():
        if outcome != "OK":
            print(f"  {outcome:<7}  {node}  {reasons.get(node, '')}")
    count = {k: sum(1 for v in outcomes.values() if v == k) for k in ("OK", "FAIL", "BLOCKED")}
    print(f"elapsed: {time.monotonic() - began:.0f} s")
    print(f"tests: {len(outcomes)}  OK {count['OK']}  FAIL {count['FAIL']}  "
          f"BLOCKED {count['BLOCKED']}")
    invalid = "; ".join(r.invalid for r in results if r.invalid)
    if line := run.close(lambda: None):
        print(line, flush=True)
        count["FAIL"] += 1
    run.finished = True
    # THE LOGS ARE THE EVIDENCE OF A RED RUN, kept and named; a green one leaves nothing.
    run.leave(kept=bool(invalid or count["FAIL"]))
    if invalid:
        print(f"==> LIVE PYTEST INVALID: {invalid}")
        return EXIT_INVALID
    print("==> LIVE PYTEST " + ("FAILED" if count["FAIL"] else "PASSED"))
    return EXIT_FAILED if count["FAIL"] else EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
