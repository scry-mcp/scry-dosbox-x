"""The live pytest tier through `scry_core.live_pool`: every live test that opens no window runs
as a job of its own, at most `DOSBOX_X_LIVE_JOBS` at once (unset, half the host's CPUs), and the
`windowed` ones after them, together and one after another, because a window or a menu click
takes the focus and would judge its neighbours.

    timeout 3600 uv run python tests/live/run_live_pytest.py      # from the clone's root

Each job is pytest run in its own process on its tests, which records every test's outcome by
node id (passed OK, failed or errored FAIL, skipped BLOCKED with the reason) and declares them
as the job's summary. One line per job as it ends, then every test that did not pass and the
count. Exit 0 with every test OK or BLOCKED, 1 with any FAIL, 3 when nothing was collected or
the merge cannot be believed, 2 for an argument (it takes none) or a job count that is none.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import live_private  # isort: skip -- first: a pooled job's working copies (`live_private`)
import pytest
from scry_core import live_pool

ROOT = Path(__file__).resolve().parents[2]
JOBS_VAR = "DOSBOX_X_LIVE_JOBS"
SUMMARY_VAR = "DOSBOX_X_LIVE_SUMMARY"
# The node ids a child runs, one per line; set by the parent, never by hand.
NODES_VAR = "DOSBOX_X_LIVE_PYTEST_NODES"
PYTEST_ARGS = ["-q", "--no-cov", "-p", "no:cacheprovider", "-m", "live"]
EXIT_PASSED, EXIT_FAILED, EXIT_INVALID = 0, 1, 3


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
    # THE NODE IDS GO LAST: the repository's `addopts` ends in `--cov`, whose value is optional,
    # so a node id right after it is taken as the coverage source and pytest runs every test.
    rc = pytest.main([*PYTEST_ARGS, *nodes], plugins=[seen])
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


def _jobs(nodes: list[str], prefix: str, together: bool) -> list[live_pool.Job]:
    me = [sys.executable, str(Path(__file__).resolve())]
    groups = [nodes] if together else [[n] for n in nodes]
    return [live_pool.Job(f"{prefix}{i:03d}", me,
                          env={NODES_VAR: "\n".join(g), live_private.PRIVATE_VAR: "1"},
                          planned=tuple(g)) for i, g in enumerate(groups, 1) if g]


def _leave(signum: int, _frame: object) -> None:
    """`timeout` ends a run with SIGTERM and a closed terminal with SIGHUP: turned into an exit,
    the pool's stop reaches the children, which run in process groups of their own."""
    raise SystemExit(128 + signum)


def main() -> int:
    for sig in (signal.SIGTERM, signal.SIGHUP):
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
    pooled, windowed = _collect("live and not windowed"), _collect("live and windowed")
    if pooled is None or windowed is None:
        return EXIT_INVALID
    if not pooled and not windowed:
        print("INVALID: no live test was collected, so there is no verdict")
        return EXIT_INVALID
    out = Path(tempfile.mkdtemp(prefix="dosbox-x-live-pytest-"))
    print(f"jobs: {workers} at once, then {len(windowed)} windowed in turn; logs in {out}",
          flush=True)

    def ended(r: live_pool.JobResult) -> None:
        bad = [n for n, o in r.outcomes().items() if o != "OK"]
        word = "FAIL" if any(o == "FAIL" for o in r.outcomes().values()) else (
            "BLOCKED" if bad else "OK")
        print(f"  {word:<7}  {r.job.name}  {r.elapsed_s:.0f} s  "
              f"{', '.join(r.job.planned) if len(r.job.planned) == 1 else ''}", flush=True)

    began = time.monotonic()
    results = []
    if pooled:
        results.append(live_pool.run_pool(_jobs(pooled, "p", False), workers, out, SUMMARY_VAR,
                                          on_done=ended))
    if windowed:
        results.append(live_pool.run_pool(_jobs(windowed, "w", True), 1, out, SUMMARY_VAR,
                                          on_done=ended))
    outcomes = {k: v for r in results for k, v in r.outcomes.items()}
    reasons = {k: v for r in results for k, v in r.reasons.items()}
    for node, outcome in outcomes.items():
        if outcome != "OK":
            print(f"  {outcome:<7}  {node}  {reasons.get(node, '')}")
    count = {k: sum(1 for v in outcomes.values() if v == k) for k in ("OK", "FAIL", "BLOCKED")}
    print(f"elapsed: {time.monotonic() - began:.0f} s")
    print(f"tests: {len(outcomes)}  OK {count['OK']}  FAIL {count['FAIL']}  "
          f"BLOCKED {count['BLOCKED']}")
    if invalid := "; ".join(r.invalid for r in results if r.invalid):
        print(f"==> LIVE PYTEST INVALID: {invalid}")
        return EXIT_INVALID
    print("==> LIVE PYTEST " + ("FAILED" if count["FAIL"] else "PASSED"))
    return EXIT_FAILED if count["FAIL"] else EXIT_PASSED


if __name__ == "__main__":
    sys.exit(main())
