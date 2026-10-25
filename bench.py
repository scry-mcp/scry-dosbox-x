#!/usr/bin/env python3
"""Re-take the figures this package's documents rest on, and validate the instrument.

    python bench.py --conf your.conf --cwd /path/to/it [--json out.json]

The timer is checked against a known answer (a sleep) and a negative (a do-nothing call),
and every benched call must return an answer. Figures price the server, not the caller's
round trip. A run that is not a measurement prints INVALID on stderr and exits 3.
"""

from __future__ import annotations

import argparse
import functools
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
from scry_core.reply_contract import Invalid  # noqa: E402

import dosbox_binary as dbinary  # noqa: E402
import dosbox_console as dcons  # noqa: E402
import dosbox_launch as dlaunch  # noqa: E402
import dosbox_logs as dlogs  # noqa: E402
import dosbox_session as ds  # noqa: E402

STAMP = re.compile(r"\[\+\s*([0-9]+\.[0-9]+)\]")

# The application's own first line: the guest saying it is up, not a fixed wait.
MARKER = "BOOT  . start"

# Step is WINDOW_SECS / WINDOW_SAMPLES. The loop runs (WINDOW_SAMPLES + SETTLE_SAMPLES) * step;
# the rates span (WINDOW_SAMPLES - 1) * step, five intervals being the least worth a spread.
WINDOW_SECS = 30.0
WINDOW_SAMPLES = 6

# The first interval after `resume` still has the boot burst draining through the log
# pipeline and reads fast, so that sample is discarded.
SETTLE_SAMPLES = 1


def timed(fn: Callable[[], Any]) -> tuple[float, Any]:
    """One call, in milliseconds, with what it returned. The only timer here."""
    t0 = time.perf_counter()
    got = fn()
    return (time.perf_counter() - t0) * 1000.0, got


def validate_timer() -> dict[str, object]:
    """A known answer and a negative, through the same timer everything else uses."""
    known_ms = 250.0
    got, _ = timed(lambda: time.sleep(known_ms / 1000.0))
    err = abs(got - known_ms) / known_ms
    zero, _ = timed(lambda: None)
    ok = err < 0.05 and zero < 1.0
    return {"known_ms": known_ms, "read_ms": round(got, 2),
            "error_pct": round(err * 100, 2), "negative_ms": round(zero, 4),
            "ok": ok}


#: `SystemExit` with a string exits 1, not 3, so the exit code is set by hand.
INVALID_RC = 3


def invalid_line(why: str) -> None:
    """Say that this run is not a measurement, on stderr, in the one spelling."""
    print(f"INVALID: {why}", file=sys.stderr)


def no_measurement(why: str) -> NoReturn:
    """Say it and stop, with `INVALID_RC`.

    Not named `invalid`: the reply contract's source scan reserves that name.
    """
    invalid_line(why)
    raise SystemExit(INVALID_RC)


def bench(label: str, fn: Callable[[], Any], n: int,
          answered: Callable[[Any], bool]) -> dict[str, object]:
    """`n` calls of one thing, with the median and the spread.

    `answered` is required: `Session.command` returns "" on total silence without raising.
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
    """The guest's own clock, off the logfile on disk, never through the session.

    A read through the session drains the terminal, which hides the measured defect.
    The maximum is taken: boot self-checks are stamped before the profiler's clock
    starts, so the log is not monotone.
    """
    try:
        found = [float(x) for x in STAMP.findall(log.read_text(errors="replace"))]
    except OSError:
        return None
    return max(found) if found else None


def batch_cost(cwd: Path, song: str) -> dict[str, float]:
    """What one question costs run as a batch: launch, reach the state, read, tear down.

    The log is written at the end, so it is checked afterwards, not polled.
    """
    log = cwd / "build" / "PROF.E9.log"
    if log.exists():
        log.unlink()          # a stale log must not read as this run's answer
    ms, _ = timed(lambda: subprocess.run(
        ["make", "prof-log", f"SONG={song}", "SECS=30"], cwd=str(cwd),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False))
    if not log.exists() or MARKER not in log.read_text(errors="replace"):
        no_measurement(f"the batch produced no {MARKER!r}, so this timed a "
                         f"run that never answered")
    return {"total_s": round(ms / 1000.0, 2)}


def reach_the_state(conf: Path, cwd: Path) -> dict[str, float]:
    """Debugger prompt (the session can be asked) and application up (the marker appears)."""
    log = Path("/tmp/dosbox-bench-reach.log")
    if log.exists():
        log.unlink()
    t0 = time.perf_counter()
    s = ds.Session(dlaunch.Launch(binary=build().path, conf=conf,
                                  cwd=cwd, seconds=180, logfile=log))
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
            no_measurement(f"{MARKER!r} did not appear on the live path within the wait")
        up = time.perf_counter() - t0
    finally:
        s.close()
    return {"debugger_prompt_s": round(prompt, 2), "application_up_s": round(up, 2)}


def per_question(conf: Path, cwd: Path) -> dict[str, object]:
    """What each tool costs against a session already stopped where you want it.

    The reply grace is swept: a console reply ending in the debugger's last words breaks
    after `REPLY_GRACE_S` of quiet, so part of its cost is that parameter, not the machine.
    """
    log = Path("/tmp/dosbox-bench-q.log")
    if log.exists():
        log.unlink()
    s = ds.Session(dlaunch.Launch(binary=build().path, conf=conf,
                                  cwd=cwd, seconds=300, logfile=log))
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

        sweep: dict[str, object] = {}
        default = ds.REPLY_GRACE_S
        try:
            for grace in (0.6, 0.3, default):
                ds.REPLY_GRACE_S = grace
                sweep[str(grace)] = bench(f"registers@grace={grace}",
                                          lambda: dcons.parse_registers(s.command(ds.NUDGE)),
                                          5, nonempty)
        finally:
            ds.REPLY_GRACE_S = default
        out["grace_sweep"] = sweep

        s.resume()
        deadline = time.perf_counter() + 60
        while time.perf_counter() < deadline:
            if log.exists() and dlogs.count_e9(log.read_text(errors="replace")) > 5:
                break
            time.sleep(0.5)
        # e9 reads and counts the whole log, so its cost needs the size beside it.
        e9_lines = dlogs.count_e9(log.read_text(errors="replace"))
        out["e9"] = bench("e9", lambda: s.log("Bochs", 10, "guest"), 15,
                          lambda r: bool(r[0]))
        out["e9_log_lines"] = e9_lines
        out["status"] = bench("status", s.state, 15, nonempty)
    finally:
        ms, _ = timed(s.close)
        out["close_a_running_session_s"] = round(ms / 1000.0, 2)
    return out


def advance_rate(conf: Path, cwd: Path) -> dict[str, object]:
    """How fast the guest runs while nobody is asking it anything.

    Published is the median of the per-window rates with the first window discarded: the
    whole-span ratio can read above 1.0 because the surplus sits in the first window, taken
    while the log pipeline is backed up after the boot burst. Monotonicity is not evidence,
    since `newest()` is a maximum over a growing file; the spread is.
    """
    log = Path("/tmp/dosbox-bench-rate.log")
    if log.exists():
        log.unlink()
    s = ds.Session(dlaunch.Launch(binary=build().path, conf=conf,
                                  cwd=cwd, seconds=240, logfile=log))
    try:
        s.wait_ready()
        s.resume()
        deadline = time.perf_counter() + 90
        while newest(log) is None and time.perf_counter() < deadline:
            time.sleep(0.5)
        if newest(log) is None:
            no_measurement("no clock stamp could be read from the guest's log (none written, "
                           "or the log unreadable)")

        step = WINDOW_SECS / WINDOW_SAMPLES
        samples: list[tuple[float, float]] = []
        t0 = time.perf_counter()
        while len(samples) < WINDOW_SAMPLES + SETTLE_SAMPLES:
            time.sleep(step)
            g = newest(log)
            if g is None:
                no_measurement("the guest's log no longer yields a clock stamp mid-window")
            samples.append((time.perf_counter() - t0, g))
            if not s.alive():
                no_measurement("the emulator exited inside the window")
    finally:
        s.close()

    return window_rates(samples)


def window_rates(samples: list[tuple[float, float]]) -> dict[str, object]:
    """`advance_rate`'s figures off its (wall seconds, guest seconds) samples."""
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


@functools.cache
def build() -> dbinary.Resolved:
    """The build the server's own ladder lands on, so bench and session never differ."""
    try:
        return dbinary.resolve("")
    except Invalid as e:
        no_measurement(f"no build to measure: {e}")


def stamp() -> dict[str, object]:
    """The machine and emulator build, read back; stderr is read too, the banner lands there."""
    found = build()
    ver = dlaunch.binary_facts(found, dbinary.VERSION_TIMEOUT_S)["version"]
    if not isinstance(ver, str):
        no_measurement(f"{found.path} reported no version ({ver['why']}), so this run cannot "
                       "be attributed to a build")
    machine = subprocess.run(("sysctl", "-n", "hw.model"), capture_output=True, text=True,
                             check=False)
    return {"machine": (machine.stdout + machine.stderr).strip(), "emulator": ver,
            "binary": found.path, "binary_origin": found.origin,
            "load_average": os.getloadavg()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # Not `required=True`: argparse would refuse at its own exit code, and the refusal below is 3.
    ap.add_argument("--conf", type=Path, help="(required) the config file to measure")
    ap.add_argument("--cwd", type=Path,
                    help="(required) the working directory that config runs in")
    ap.add_argument("--json", type=Path, help="write the full result here")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--song", help="the song your `make prof-log` plays; with none named, "
                                   "the batch figure is not taken")
    args = ap.parse_args()

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
        invalid_line("the timer check failed (its known answer, or the cost of a call that "
                     "does nothing), so nothing below is a measurement")
        return INVALID_RC

    out: dict[str, Any] = {"timer": check, **stamp()}
    print(f"machine: {out['machine']} | {out['emulator']} | load {out['load_average']}")

    if args.song:
        runs = [batch_cost(cwd, args.song) for _ in range(args.reps)]
        out["batch"] = {"runs": runs,
                        "total_s_median": round(
                            statistics.median(r["total_s"] for r in runs), 2)}
    else:
        out["batch"] = {"available": False, "why": "no --song named, so no batch was run"}
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
