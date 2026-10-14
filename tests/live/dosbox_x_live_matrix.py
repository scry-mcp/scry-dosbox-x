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

Sections A-C, F and H-N run on the package's own guests and need nothing. D and E run
dos-real16 and dos-real16-alt on their copies on the bench (`bench_programs`, filled and checked by
`python -m scry_core.live_bench`, the bench's `identity.json` saying what each label stands
for), each BLOCKED whole, as K's dos-real16 cells are, naming the file, when the identity is
incomplete or a copy is absent or off its pin. What a run takes from the environment:

    DOSBOX_X_LIVE_BENCH           the bench's root (`~/.local/share/scry-bench/dosbox-x` unset)
    DOSBOX_X_LIVE_WINDOW_FLAGS    G: the placement flags of a watched window, one token per
                                  line
    DOSBOX_X_LIVE_SECTIONS        the letters to run (`ABC`), all of them when unset
"""
from __future__ import annotations

import signal
import sys

import matrix_arguments  # noqa: F401 -- registers section L
import matrix_code  # noqa: F401 -- registers section M
import matrix_comment_tools  # noqa: F401 -- registers section N
import matrix_dos_real16  # noqa: F401 -- registers section D
import matrix_dos_real16_alt  # noqa: F401 -- registers section E
import matrix_dpmi  # noqa: F401 -- registers section F
import matrix_probe  # noqa: F401 -- registers sections A to C, H and I
import matrix_screen  # noqa: F401 -- registers section J
import matrix_trace  # noqa: F401 -- registers section K
import matrix_window  # noqa: F401 -- registers section G
from matrix_common import ENV, M, close_whatever, isolate
from matrix_ledger import EXIT_INVALID

SECTIONS_VAR = "DOSBOX_X_LIVE_SECTIONS"


def _leave(signum: int, _frame: object) -> None:
    """`timeout` ends a run with SIGTERM and a closed terminal with SIGHUP, and neither runs
    `atexit` on its own: turned into an exit, the summary is printed and no DOSBox-X of this run
    outlives it."""
    raise SystemExit(128 + signum)


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
    return M.run(list(wanted), ENV, close_whatever, isolate)


if __name__ == "__main__":
    sys.exit(main())
