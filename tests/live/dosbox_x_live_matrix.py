"""Every tool of the server against a real DOSBox-X.

    uv run python tests/live/dosbox_x_live_matrix.py

Exit 0 no FAIL, 1 FAIL, 3 invalid, 2 argument. Env:
DOSBOX_X_BINARY, DOSBOX_X_LIVE_BENCH, WINDOW_APP, DOSBOX_X_LEAK_BINARY, DOSBOX_X_STOCK_BINARY,
DOSBOX_X_LIVE_SECTIONS (letters), DOSBOX_X_LIVE_JOBS (default half the CPUs).
"""
from __future__ import annotations

# First: jobs take their copies on import.
import live_private  # isort: skip

import signal
import sys
from collections.abc import Callable
from pathlib import Path

import matrix_arguments  # noqa: F401
import matrix_code  # noqa: F401
import matrix_comment_tools  # noqa: F401
import matrix_dos_real16  # noqa: F401
import matrix_dos_real16_alt  # noqa: F401
import matrix_dpmi  # noqa: F401
import matrix_focus  # noqa: F401
import matrix_media  # noqa: F401
import matrix_mouse  # noqa: F401
import matrix_presence  # noqa: F401
import matrix_probe  # noqa: F401
import matrix_screen  # noqa: F401
import matrix_trace  # noqa: F401
import matrix_v86  # noqa: F401
import matrix_window  # noqa: F401
from matrix_common import ENV, M, close_whatever, isolate
from matrix_ledger import EXIT_INVALID, SUMMARY_VAR, Section
from scry_core import live_pool

import dosbox_binary  # isort: skip

SECTIONS_VAR = "DOSBOX_X_LIVE_SECTIONS"
JOBS_VAR = "DOSBOX_X_LIVE_JOBS"


def _leave(signum: int, _frame: object) -> None:
    """Neither signal runs `atexit`; an exit does."""
    raise SystemExit(128 + signum)


def _jobs() -> int | None:
    held = ENV.get(JOBS_VAR, "").strip()
    if not held:
        return live_pool.default_workers()
    return int(held) if held.isascii() and held.isdigit() and int(held) >= 1 else None


def _pool(workers: int) -> Callable[[list[Section]], live_pool.PoolResult]:
    def run(sections: list[Section]) -> live_pool.PoolResult:
        out = Path(M.fresh("-jobs"))
        print(f"jobs: {workers} at once, logs and summaries in {out}", flush=True)
        letters = sorted({s.letter for s in sections})

        def ended(r: live_pool.JobResult) -> None:
            copies.ended(r.job.name)
            counts = {k: sum(1 for v in r.outcomes().values() if v == k)
                      for k in ("OK", "FAIL", "BLOCKED")}
            print(f"  [{r.job.name}] OK {counts['OK']} FAIL {counts['FAIL']} "
                  f"BLOCKED {counts['BLOCKED']}  {r.elapsed_s:.0f} s  log: {r.log}", flush=True)
        with live_private.copies_of_jobs() as copies:
            jobs = [live_pool.Job(
                        letter, [sys.executable, str(Path(__file__).resolve())],
                        env={SECTIONS_VAR: letter, JOBS_VAR: "1", **copies.env(letter),
                             **M.host.job_env(letter)},
                        planned=tuple(c.label for s in sections if s.letter == letter
                                      for c in s.cells))
                    for letter in letters]
            return live_pool.run_pool(jobs, workers, out, SUMMARY_VAR, on_done=ended)
    return run


def main() -> int:
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _leave)
    try:
        return _main()
    finally:
        M.unfinished()


def _main() -> int:
    if sys.argv[1:]:
        print(f"usage: {sys.argv[0]} (no arguments; see the docstring for the variables)",
              file=sys.stderr)
        return 2
    letters = {s.letter for s in M.sections}
    wanted = ENV.get(SECTIONS_VAR, "").strip().upper()
    unknown = sorted(set(wanted) - letters)
    if unknown:
        print(f"INVALID: {SECTIONS_VAR} names no section {unknown}; "
              f"there are {''.join(sorted(letters))}", file=sys.stderr)
        return EXIT_INVALID
    workers = _jobs()
    if workers is None:
        print(f"{JOBS_VAR}={ENV[JOBS_VAR]!r} is not a job count: a whole number, at least 1",
              file=sys.stderr)
        return 2
    summary = ENV.get(SUMMARY_VAR, "")
    if why := M.host.begin(dosbox_binary.canary_for(), "DOSBox-X"):
        print(f"==> LIVE MATRIX INVALID: {why}", flush=True)
        return EXIT_INVALID
    pool = _pool(workers) if workers > 1 and not summary else None
    if pool is None and not summary:
        print("jobs: 1, every section in this process", flush=True)
    return M.run(list(wanted), ENV, close_whatever, isolate, pool=pool,
                 summary=Path(summary) if summary else None)


if __name__ == "__main__":
    sys.exit(main())
