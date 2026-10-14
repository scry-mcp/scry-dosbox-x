#!/usr/bin/env python3
"""Re-take every figure this package's README publishes, and validate the instrument.

    python bench.py --conf your.conf --cwd /path/to/it [--json out.json]

WHY IT SHIPS HERE: a measurement with no artefact is a claim about a session that
ended. A reader cannot re-take it, cannot see what was actually timed, and therefore
cannot see which of the numbers are about this code and which are about the machine or
about a constant somebody chose. A script that lives in a scratch directory and is
thrown away leaves its figures published with nothing behind them.

WHAT IT VALIDATES ABOUT ITSELF, before any figure is believed (Abrash: an instrument
lies until proven against a known answer):

* a KNOWN-ANSWER on the timer -- a sleep of a known length, measured through the same
  path as everything else, must come back within a few percent;
* a NEGATIVE on the timer -- a call that does nothing must come back at essentially
  zero, so "fast" and "not measured" cannot print the same thing;
* every benched call is CHECKED for having returned an answer, because three of the
  five raise on failure and `debug` does not: `command()` returns "" on total silence
  and that is not an error, so a bench could happily time a session saying nothing.

WHAT IT DELIBERATELY EXCLUDES: the caller's latency. The per-question figures are timed
in this process, around the call, so they price THE SERVER. An agent timing its own
round trips reads seconds for the same work; both are real and only one is about this
code.

AND THE ONE FIGURE IT REFUSES TO PUBLISH AS A RATIO. See `advance_rate`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

sys.path.append(str(Path(__file__).resolve().parent))

import dosbox_session as ds  # noqa: E402

STAMP = re.compile(r"\[\+\s*([0-9]+\.[0-9]+)\]")

# The guest milestone every "reaching the state" figure waits for. It is the
# application's own first line, so it is the guest saying it is up rather than a fixed
# wait chosen here.
MARKER = "BOOT  . start"

# THE SAMPLING STEP IS `WINDOW_SECS / WINDOW_SAMPLES`, and that is the only thing
# either constant names directly. Two spans follow from it and they are NOT equal: the loop
# RUNS for `(WINDOW_SAMPLES + SETTLE_SAMPLES) * step` and the rates it REPORTS cover
# `(WINDOW_SAMPLES - 1) * step`. With the values below that is 35 s of running for 25 s
# of reported span. Neither is `WINDOW_SECS`, and the coincidence that first-to-last
# equals it holds only while `SETTLE_SAMPLES` is 1. With the
# values below the loop takes 7 samples 5 s apart, so it RUNS for 35 s and the rates it
# reports cover the 25 s between the 6 samples it keeps. Six kept samples give five
# intervals, the smallest number from which a SPREAD is worth quoting.
WINDOW_SECS = 30.0
WINDOW_SAMPLES = 6

# The first sample after `resume` is DISCARDED, and the reason is the LOG PIPELINE, not
# a baseline. An earlier comment said it "straddles the moment `base` is taken", which
# described a `base` this code no longer takes: the earliest rate here is already
# between two real samples. What is true is that the first interval after `resume`
# begins with the guest's boot burst still draining, so it reads fast; the discard costs
# one sample of the seven and removes that transient from the median.
SETTLE_SAMPLES = 1


def timed(fn: Callable[[], Any]) -> tuple[float, Any]:
    """One call, in milliseconds, with what it returned. The only timer here."""
    t0 = time.perf_counter()
    got = fn()
    return (time.perf_counter() - t0) * 1000.0, got


def validate_timer() -> dict[str, object]:
    """A known answer and a negative, through the SAME timer everything else uses.

    Without the known answer, every figure below is a number with no evidence that the
    clock reads true. Without the negative, a call that did nothing and a call that was
    genuinely fast print the same thing.
    """
    known_ms = 250.0
    got, _ = timed(lambda: time.sleep(known_ms / 1000.0))
    err = abs(got - known_ms) / known_ms
    zero, _ = timed(lambda: None)
    ok = err < 0.05 and zero < 1.0
    return {"known_ms": known_ms, "read_ms": round(got, 2),
            "error_pct": round(err * 100, 2), "negative_ms": round(zero, 4),
            "ok": ok}


#: WHAT A RUN THAT IS NOT A MEASUREMENT EXITS WITH, and it is 3 everywhere in this package: a
#: figure that could not be taken is not a failure of the thing being measured. `SystemExit`
#: with a STRING does not give that -- CPython prints the string and exits 1 -- so both halves
#: are done by hand here rather than by an argument that looks as though it would.
INVALID_RC = 3


def invalid_line(why: str) -> None:
    """Say that this run is not a measurement, in ONE spelling, on stderr.

    THE WORD IS THE HELPER'S AND NOT THE CALLER'S: nine sites wrote the prefix by hand, which
    is nine chances to spell it differently, and a caller grepping for it would find eight.
    Stderr because a diagnostic sharing a channel with the figures is one somebody's parser
    reads as data.
    """
    print(f"INVALID: {why}", file=sys.stderr)


def no_measurement(why: str) -> NoReturn:
    """Say it and stop, with `INVALID_RC`.

    IT IS NOT CALLED `invalid`, and that is not taste: the reply contract's own source scan
    reserves `Invalid`, `invalid` and `refusal` for a refusal carrying a code from its table,
    and a function here wearing one of those names is read as one of those. It was, and the
    scan said so.
    """
    invalid_line(why)
    raise SystemExit(INVALID_RC)


def bench(label: str, fn: Callable[[], Any], n: int,
          answered: Callable[[Any], bool]) -> dict[str, object]:
    """`n` calls of one thing, with the median and the spread.

    `answered` is REQUIRED and is not decoration: `Session.command` returns "" when the
    screen said nothing at all, which is not an exception, so a bench without it times
    a session that answered nothing and publishes the result as a speed.
    """
    times: list[float] = []
    for _ in range(n):
        ms, got = timed(fn)
        if not answered(got):
            no_measurement(f"`{label}` returned nothing on call "
                             f"{len(times) + 1}; this would have been timed as a fast "
                             f"answer")
        times.append(ms)
    return {"median_ms": round(statistics.median(times), 1),
            "min_ms": round(min(times), 1), "max_ms": round(max(times), 1), "n": n}


def newest(log: Path) -> float | None:
    """The guest's own clock, off the LOGFILE on disk, never through the session.

    Every read through the session drains the terminal, which is the exact condition
    under which the defect this measures does not occur. Asking would create it.

    IT TAKES THE MAXIMUM because this guest's log is not monotone: its boot self-checks
    are emitted before the profiler's clock starts. That also means a sequence of these
    CANNOT DECREASE, which is why `advance_rate` does not quote monotonicity as
    evidence of anything (see there).
    """
    try:
        found = [float(x) for x in STAMP.findall(log.read_text(errors="replace"))]
    except OSError:
        return None
    return max(found) if found else None


def batch_cost(cwd: Path, song: str) -> dict[str, float]:
    """What one question costs run as a BATCH: launch, reach the state, read, tear down.

    IT TIMES THE COMMAND AND CHECKS THE ANSWER AFTERWARDS rather than during. An
    earlier version polled `build/PROF.E9.log` while the run was in flight to split out
    "reaching the state", and reported INVALID three times running: that file is written
    at the END. The honest split lives in `reach_the_state`, on the path whose log
    really is progressive.
    """
    log = cwd / "build" / "PROF.E9.log"
    if log.exists():
        log.unlink()          # so a STALE log cannot be read as this run's answer
    ms, _ = timed(lambda: subprocess.run(
        ["make", "prof-log", f"SONG={song}", "SECS=30"], cwd=str(cwd),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False))
    if not log.exists() or MARKER not in log.read_text(errors="replace"):
        no_measurement(f"the batch produced no {MARKER!r}, so this timed a "
                         f"run that never answered")
    return {"total_s": round(ms / 1000.0, 2)}


def reach_the_state(conf: Path, cwd: Path) -> dict[str, float]:
    """Two costs, because the criterion needs the second and they are not the same.

    The debugger prompt is when the SESSION can be asked things; the marker is when the
    APPLICATION is up. Both are the guest saying so rather than a wait chosen here.
    """
    log = Path("/tmp/dosbox-bench-reach.log")
    if log.exists():
        log.unlink()
    t0 = time.perf_counter()
    s = ds.Session(ds.Launch(conf=conf, cwd=cwd, seconds=180, logfile=log))
    try:
        s.wait_ready()
        prompt = time.perf_counter() - t0
        s.resume()
        deadline = time.perf_counter() + 120
        while time.perf_counter() < deadline:
            if log.exists() and MARKER in log.read_text(errors="replace"):
                break
            time.sleep(0.05)
        else:
            no_measurement(f"{MARKER!r} never appeared on the live path")
        up = time.perf_counter() - t0
    finally:
        s.close()
    return {"debugger_prompt_s": round(prompt, 2), "application_up_s": round(up, 2)}


def per_question(conf: Path, cwd: Path) -> dict[str, object]:
    """What each tool costs against a session already stopped where you want it.

    THE SETTLE IS SWEPT, and that is the difference between a measurement of this
    emulator and a measurement of a constant this package chose. `command()` breaks
    only after `settle` seconds of QUIET, so most of a console question's cost is that
    parameter rather than the machine. Publishing the default alone invites the reader
    to attribute all of it to DOSBox-X.
    """
    log = Path("/tmp/dosbox-bench-q.log")
    if log.exists():
        log.unlink()
    s = ds.Session(ds.Launch(conf=conf, cwd=cwd, seconds=300, logfile=log))
    out: dict[str, object] = {}
    try:
        ms, _ = timed(s.wait_ready)
        out["reach_the_debugger_s"] = round(ms / 1000.0, 2)

        def nonempty(r: Any) -> bool:
            return bool(r)

        out["registers"] = bench("registers", s.registers, 7, nonempty)
        out["read_memory"] = bench(
            "read_memory", lambda: s.read_memory(0xF000, 0xE000), 7, nonempty)
        out["debug"] = bench("debug", lambda: s.command("BPLIST"), 7,
                             lambda r: bool(str(r).strip()))

        # THE SWEEP: the same call at three settles, so a reader can see how much of
        # the figure is ours. Each still checks it got a real pane back.
        def at_settle(st: float) -> Callable[[], dict[str, str]]:
            """The default argument is bound HERE and not in a lambda's parameter list:
            a late-bound closure over the loop variable would time the LAST settle
            three times and report it under three different labels."""
            return lambda: ds.parse_registers(s.command(ds.NUDGE, settle=st))

        sweep: dict[str, object] = {}
        for settle in (0.6, 0.3, 0.1):
            sweep[str(settle)] = bench(f"registers@settle={settle}",
                                       at_settle(settle), 5, nonempty)
        out["settle_sweep"] = sweep

        s.resume()
        deadline = time.perf_counter() + 60
        while time.perf_counter() < deadline:
            if log.exists() and ds.count_e9(log.read_text(errors="replace")) > 5:
                break
            time.sleep(0.5)
        # `e9`'s COST IS A FUNCTION OF LOG SIZE: it reads the whole file and counts
        # every line. Publishing one figure without the size makes a property of a
        # six-line file read as a property of the tool.
        e9_lines = ds.count_e9(log.read_text(errors="replace"))
        out["e9"] = bench("e9", lambda: s.log("Bochs", 10, "guest"), 15,
                          lambda r: bool(r[0]))
        out["e9_log_lines"] = e9_lines
        out["status"] = bench("status", s.state, 15, nonempty)
    finally:
        ms, _ = timed(s.close)
        out["close_a_running_session_s"] = round(ms / 1000.0, 2)
    return out


def advance_rate(conf: Path, cwd: Path) -> dict[str, object]:
    """How fast the guest runs while NOBODY is asking it anything.

    THE FIGURE PUBLISHED IS THE MEDIAN OF THE PER-WINDOW RATES, not the ratio of the
    whole span, and the first window is DISCARDED. That is a correction of a measured
    artefact rather than a refinement:

    an earlier version divided (last stamp - first stamp) by the wall span and reported
    **1.019**, i.e. the guest running FASTER than real time. Broken into its six
    windows, the same data reads 1.199, 0.978, 0.901, 1.130, 0.869, 1.043 -- the entire
    surplus lives in the FIRST window, taken when the log pipeline is at its most backed
    up after the boot burst. Windows two to six give a MEDIAN of 0.978, below real time,
    which is what `cycles=fixed` should produce. (0.984 is their MEAN, and this
    docstring quoted it while the code below computes the median: a figure no run of
    this instrument could print.)

    AND MONOTONICITY IS NOT REPORTED AS EVIDENCE, because `newest()` is a MAXIMUM over
    a growing file and therefore cannot decrease. The old text offered "monotonic across
    all six samples" as corroboration; it would have held if the guest had frozen solid.
    What IS evidence is the SPREAD, so that is what is published.
    """
    log = Path("/tmp/dosbox-bench-rate.log")
    if log.exists():
        log.unlink()
    s = ds.Session(ds.Launch(conf=conf, cwd=cwd, seconds=240, logfile=log))
    try:
        s.wait_ready()
        s.resume()
        deadline = time.perf_counter() + 90
        while newest(log) is None and time.perf_counter() < deadline:
            time.sleep(0.5)
        if newest(log) is None:
            no_measurement("the guest emitted no clock at all")

        step = WINDOW_SECS / WINDOW_SAMPLES
        samples: list[tuple[float, float]] = []
        t0 = time.perf_counter()
        while len(samples) < WINDOW_SAMPLES + SETTLE_SAMPLES:
            time.sleep(step)
            g = newest(log)
            if g is None:
                no_measurement("the guest clock vanished mid-window")
            samples.append((time.perf_counter() - t0, g))
            if not s.alive():
                no_measurement("the emulator exited inside the window")
    finally:
        s.close()

    used = samples[SETTLE_SAMPLES:]
    rates = [(g1 - g0) / (w1 - w0)
             for (w0, g0), (w1, g1) in zip(used, used[1:], strict=False)]
    return {
        "rate_median": round(statistics.median(rates), 3),
        "rate_min": round(min(rates), 3), "rate_max": round(max(rates), 3),
        "windows": len(rates),
        "discarded_settling_samples": SETTLE_SAMPLES,
        "samples": [(round(w, 1), g) for w, g in samples],
    }


def stamp() -> dict[str, object]:
    """The machine and the emulator build, READ BACK rather than assumed.

    `dosbox-x -version` writes to STDERR. An earlier version read `.stdout`, got an
    empty string, and shipped `"emulator": []` in silence -- so the README's version
    stamp was true by luck rather than by record, in the one field whose whole job is
    to make the run attributable.
    """
    def run(*cmd: str) -> str:
        got = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return (got.stdout + got.stderr).strip()

    ver = run("dosbox-x", "-version").splitlines()
    if not ver:
        no_measurement("dosbox-x reported no version, so this run cannot "
                         "be attributed to a build")
    return {"machine": run("sysctl", "-n", "hw.model"),
            "emulator": ver[0],
            "load_average": os.getloadavg()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # REQUIRED, AND SAID IN THE HELP RATHER THAN BY `required=True`: argparse would refuse
    # in its own words at its own exit code, and the refusal below is this tool's, at 3.
    ap.add_argument("--conf", type=Path, help="(required) the config file to measure")
    ap.add_argument("--cwd", type=Path,
                    help="(required) the working directory that config runs in")
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--song", default=r"D:\MIDI\DESCENT.MID")
    args = ap.parse_args()

    # BOTH ARE REQUIRED AND BOTH ARE FLAGS. They arrived by environment while this same
    # parser already took `--json`, `--reps` and `--song`: two equally required inputs
    # coming through a different door is an incoherence, not a need, and a caller who
    # spells one of them wrong in a shell gets a run on somebody else's program rather
    # than a refusal. The refusal names the FLAGS, because those are what the caller typed.
    conf, cwd = args.conf, args.cwd
    if not (conf and cwd and conf.is_file() and cwd.is_dir()):
        invalid_line("pass --conf a config file and --cwd the working directory it "
              "runs in; this bench measures YOUR program and has no default to fall "
              "back on")
        return INVALID_RC

    check = validate_timer()
    print(f"timer known-answer: asked {check['known_ms']} ms, read "
          f"{check['read_ms']} ms ({check['error_pct']}% off); a do-nothing call "
          f"reads {check['negative_ms']} ms")
    if not check["ok"]:
        invalid_line("the timer failed its own known answer, so nothing below is a "
              "measurement")
        return INVALID_RC

    out: dict[str, Any] = {"timer": check, **stamp()}
    print(f"machine: {out['machine']} | {out['emulator']} | load {out['load_average']}")

    runs = [batch_cost(cwd, args.song) for _ in range(args.reps)]
    out["batch"] = {"runs": runs,
                    "total_s_median": round(
                        statistics.median(r["total_s"] for r in runs), 2)}
    reach = [reach_the_state(conf, cwd) for _ in range(args.reps)]
    out["reach"] = {
        "runs": reach,
        "debugger_prompt_s_median": round(
            statistics.median(r["debugger_prompt_s"] for r in reach), 2),
        "application_up_s_median": round(
            statistics.median(r["application_up_s"] for r in reach), 2)}
    out["live"] = per_question(conf, cwd)
    out["advance"] = advance_rate(conf, cwd)

    print(json.dumps({k: v for k, v in out.items() if k != "timer"}, indent=2))
    if args.json:
        args.json.write_text(json.dumps(out, indent=2))
        print(f"written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
