"""Every tool of the server against a real DOSBox-X: in every machine state, at every argument
edge, across the calls that share state, on the package's own guests and on two real DOS
programs, one line per cell.

The cells are declared before anything boots, so what was planned and never reached shows at
the end. A cell is OK when the reply matches what the tool publishes for that state and input,
FAIL when it contradicts it or raises, or when a section stops on an error before judging it,
and BLOCKED when it could not be run, with the reason: an input not given, a wait longer than
the per-call ceiling (never made), or a call that never returned. Cells that name a session
state check the reply's `session` block as well. Every call lands whole in a JSON Lines
transcript whose path is printed first and again beside the verdict; a failed cell keeps the
conf and the log tail of the session live at the time. The last line is the verdict, the one
above it `PLANNED <n> RUN <n> OK <n> FAIL <n> BLOCKED <n>`.

    timeout 7200 uv run python tests/live/dosbox_x_live_matrix.py      # from the clone's root

Exit 0 with no FAIL, 1 with any, 3 when the run is invalid (no cell ran, an unknown section
letter, a cell planned twice), 2 for an argument (it takes none). Interrupted, it still prints
the summary with the cells it never reached, and exits with the signal's code.

Sections A-C, F, H-N and P run on the package's own guests and need nothing. D and E run
dos-real16 and dos-real16-alt on their copies on the bench (`bench_programs`, filled and checked by
`python -m scry_core.live_bench`, the bench's `identity.json` saying what each label stands
for), each BLOCKED whole, as K's dos-real16 cells are, naming the file, when the identity is
incomplete or a copy is absent or off its pin. What a run takes from the environment:

    DOSBOX_X_BINARY               the emulator the sessions run (the PATH's `dosbox-x` unset);
                                  the state cells need one that carries SAVESTATE and
                                  LOADSTATE, the Optimiza/dosbox-x fork's build
    DOSBOX_X_LIVE_BENCH           the bench's root (`~/.local/share/scry-bench/dosbox-x` unset)
    DOSBOX_X_LIVE_WINDOW_FLAGS    G: the placement flags of a watched window, one token per
                                  line
    DOSBOX_X_LIVE_SECTIONS        the letters to run (`ABC`), all of them when unset
    DOSBOX_X_LIVE_JOBS            how many sections run at once, each in a process of its own
                                  (`scry_core.live_pool`); unset, half the host's CPUs; `1`,
                                  every section in this process, one after another

A run with more than one job runs the sections that open a window (G, and O, which opens and
closes the run) in this process, the rest as jobs; each job's log and summary are in
the directory printed as `jobs:`, and its transcript is appended to this run's.
"""
from __future__ import annotations

# FIRST, because importing it is what a pooled job takes its working copies by, and the sections
# below read where the guests are when they are imported.
import live_private  # isort: skip

import signal
import sys
from collections.abc import Callable
from pathlib import Path

import matrix_arguments  # noqa: F401 -- registers section L
import matrix_code  # noqa: F401 -- registers section M
import matrix_comment_tools  # noqa: F401 -- registers section N
import matrix_dos_real16  # noqa: F401 -- registers section D
import matrix_dos_real16_alt  # noqa: F401 -- registers section E
import matrix_dpmi  # noqa: F401 -- registers section F
import matrix_focus  # noqa: F401 -- registers section O, which opens and closes the run
import matrix_media  # noqa: F401 -- registers section Q
import matrix_mouse  # noqa: F401 -- registers section P
import matrix_probe  # noqa: F401 -- registers sections A to C, H and I
import matrix_screen  # noqa: F401 -- registers section J
import matrix_trace  # noqa: F401 -- registers section K
import matrix_window  # noqa: F401 -- registers section G
from matrix_common import ENV, M, close_whatever, isolate
from matrix_ledger import EXIT_INVALID, Section
from scry_core import live_pool

SECTIONS_VAR = "DOSBOX_X_LIVE_SECTIONS"
JOBS_VAR = "DOSBOX_X_LIVE_JOBS"
# Where a run that is one job of another declares what it judged; set by that run, never by hand.
SUMMARY_VAR = "DOSBOX_X_LIVE_SUMMARY"


def _leave(signum: int, _frame: object) -> None:
    """`timeout` ends a run with SIGTERM and a closed terminal with SIGHUP, and neither runs
    `atexit` on its own: turned into an exit, the summary is printed and no DOSBox-X of this run
    outlives it."""
    raise SystemExit(128 + signum)


def _jobs() -> int | None:
    """The job count asked for, the host's default when unset; None for a value that is none."""
    held = ENV.get(JOBS_VAR, "").strip()
    if not held:
        return live_pool.default_workers()
    return int(held) if held.isascii() and held.isdigit() and int(held) >= 1 else None


def _pool(workers: int) -> Callable[[list[Section]], live_pool.PoolResult]:
    """The pool callable `Ledger.run` hands its poolable sections to: one job per letter, this
    very script run with that letter alone, one line per job as it ends."""
    def run(sections: list[Section]) -> live_pool.PoolResult:
        out = Path(M.fresh("-jobs"))
        print(f"jobs: {workers} at once, logs and summaries in {out}", flush=True)
        letters = sorted({s.letter for s in sections})
        jobs = [live_pool.Job(
                    letter, [sys.executable, str(Path(__file__).resolve())],
                    env={SECTIONS_VAR: letter, JOBS_VAR: "1", live_private.PRIVATE_VAR: "1"},
                    planned=tuple(c.label for s in sections if s.letter == letter
                                  for c in s.cells))
                for letter in letters]

        def ended(r: live_pool.JobResult) -> None:
            counts = {k: sum(1 for v in r.outcomes().values() if v == k)
                      for k in ("OK", "FAIL", "BLOCKED")}
            print(f"  [{r.job.name}] OK {counts['OK']} FAIL {counts['FAIL']} "
                  f"BLOCKED {counts['BLOCKED']}  {r.elapsed_s:.0f} s  log: {r.log}", flush=True)
        return live_pool.run_pool(jobs, workers, out, SUMMARY_VAR, on_done=ended)
    return run


def main() -> int:
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _leave)
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
    pool = _pool(workers) if workers > 1 and not summary else None
    if pool is None and not summary:
        print("jobs: 1, every section in this process", flush=True)
    # A pooled run that pools nothing (one letter, or only the sections that run alone) runs
    # every section here, and says so in the plan line.
    return M.run(list(wanted), ENV, close_whatever, isolate, pool=pool,
                 summary=Path(summary) if summary else None)


if __name__ == "__main__":
    sys.exit(main())
