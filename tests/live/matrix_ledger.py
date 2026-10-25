"""The ledger behind `dosbox_x_live_matrix.py`; OK, FAIL and BLOCKED are defined there."""
from __future__ import annotations

import inspect
import json
import os
import shutil
import tempfile
import threading
import time
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Any

from scry_core import live_host, live_pool
from scry_core.verdict import EXIT_FAIL as EXIT_FAIL
from scry_core.verdict import EXIT_INVALID as EXIT_INVALID
from scry_core.verdict import EXIT_PASS as EXIT_PASS

#: A call waiting longer is never made: waiting out a hung channel measures the wait.
WAIT_CEILING_S = 30.0
_WAIT_ARGS = ("seconds", "settle_seconds")
_STEP_LISTS = ("steps", "act", "plan")

#: Slack past the declared wait: a console round trip, and a step count at its ceiling.
CALL_GRACE_S = 180.0

EVIDENCE_TAIL_LINES = 200


class Blocked(Exception):
    """A call refused or never returned."""


@dataclass(frozen=True)
class Cell:
    """One planned verdict: a unique label and where its expectation comes from."""
    label: str
    source: str


@dataclass
class Section:
    letter: str
    title: str
    cells: list[Cell]
    run: Callable[[], None]
    needs: str = ""              # env variable the section requires
    judged: dict[str, str] = field(default_factory=dict)
    place: int = 1               # 0 opens the run, 2 closes it
    alone: bool = False          # opens a window: never pooled


def _waits(kw: dict[str, Any], params: dict[str, inspect.Parameter]) -> Iterator[tuple[str, Any]]:
    """Every wait a call declares, its own and its steps'."""
    for arg in _WAIT_ARGS:
        if arg in params:
            yield arg, kw.get(arg, params[arg].default)
    for lst in _STEP_LISTS:
        for step in kw.get(lst) or []:
            if isinstance(step, dict):
                for arg in _WAIT_ARGS:
                    if arg in step:
                        yield f"{lst}[{step.get('op')}].{arg}", step[arg]


SCRATCH_PREFIX = "dosbox-x-live-matrix-"
#: Set by a pooled run for its jobs, never by hand.
SUMMARY_VAR = "DOSBOX_X_LIVE_SUMMARY"


class Ledger:
    """Everything one run records; the transcript is JSON Lines."""

    def __init__(self) -> None:
        self.host = live_host.LiveRun.for_process(SCRATCH_PREFIX,
                                                  job=bool(os.environ.get(SUMMARY_VAR)))
        self.scratch = self.host.scratch
        self.transcript = self.scratch / "transcript.jsonl"
        self.evidence = self.scratch / "evidence"
        self.sections: list[Section] = []
        self.current: Section | None = None
        self.calls: list[dict[str, Any]] = []
        self.tally = {"OK": 0, "FAIL": 0, "BLOCKED": 0}
        self.failed: list[str] = []
        self.blocked_why: list[tuple[str, str]] = []
        self.reasons: dict[str, str] = {}
        self.kept: list[Path] = []
        #: The conf and log of the live session, kept on a FAIL.
        self.session_files: Callable[[], tuple[Path | None, Path | None]] = lambda: (None, None)
        self.on_hang: Callable[[], None] = lambda: None
        self.on_end: Callable[[], None] = lambda: None
        self._names = count(1)
        self._evidence_seq = count(1)

    def made(self) -> Path:
        """This run's scratch, made on first use."""
        return self.host.made()

    def section(self, letter: str, title: str, cells: list[Cell], needs: str = "",
                place: int = 1, alone: bool = False
                ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a section and its cells."""
        def register(fn: Callable[[], None]) -> Callable[[], None]:
            self.sections.append(Section(letter, title, cells, fn, needs, place=place,
                                         alone=alone))
            return fn
        return register

    def call(self, fn: Callable[..., Any], exempt: str = "", **kw: Any) -> dict[str, Any]:
        """Call a tool as the client would, keeping the whole reply.

        A wait above the ceiling raises `Blocked` unless `exempt` says why; a call past its
        wait plus `CALL_GRACE_S` ends the emulator and raises `Blocked`. A tool exception
        becomes the reply."""
        name = getattr(fn, "__name__", repr(fn))
        signature = inspect.signature(fn)
        signature.bind(**kw)
        bound = 0.0
        for arg, value in _waits(kw, dict(signature.parameters)):
            if isinstance(value, int | float) and not isinstance(value, bool):
                bound = max(bound, float(value))
                if value > WAIT_CEILING_S and not exempt:
                    raise Blocked(f"{name}({arg}={value}) may wait past the "
                                  f"{WAIT_CEILING_S:g} s ceiling")
        box: dict[str, Any] = {}

        def work() -> None:
            try:
                box["reply"] = fn(**kw)
            except Exception as exc:  # noqa: BLE001 -- the reply IS the evidence of the exception
                box["reply"] = {"exception": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()}

        began = time.monotonic()
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(bound + CALL_GRACE_S)
        hung = worker.is_alive()
        if hung:
            self.on_hang()
            worker.join(10)
        reply: dict[str, Any] = box.get("reply", {"hung": True})
        self.calls.append({"tool": name, "args": kw, "exempt": exempt,
                           "wall_s": round(time.monotonic() - began, 3), "reply": reply})
        if hung:
            raise Blocked(f"{name} did not return within {bound + CALL_GRACE_S:g} s; "
                          f"the emulator was ended under it")
        return reply

    def tmp(self, prefix: str) -> Path:
        """A new directory under the run's scratch."""
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.made()))

    def fresh(self, suffix: str) -> str:
        """An absolute path in this run's scratch that does not exist yet."""
        return str(self.made() / f"n{next(self._names)}{suffix}")

    def _close_run(self) -> None:
        """Close the machine; a DOSBox-X that outlived the run is a FAIL."""
        if line := self.host.close(self.on_end):
            print(line, flush=True)
            self.failed.append(line.removeprefix("FAIL  "))
            self.tally["FAIL"] += 1

    def unfinished(self) -> None:
        """End a run that never reached its verdict."""
        self.host.unfinished(self.on_end)

    def _flush(self, label: str, verdict: str) -> None:
        sec = self.current
        tag = f"[{sec.letter}] {sec.title}" if sec else "(none)"
        with (self.made() / self.transcript.name).open("a", encoding="utf-8") as fh:
            for rec in self.calls:
                fh.write(json.dumps({"section": tag, "label": label, "verdict": verdict, **rec},
                                    default=str) + "\n")
        self.calls.clear()

    def _count(self, label: str, verdict: str, detail: str) -> None:
        if self.current is None:
            raise RuntimeError(f"cell {label!r} judged outside any section")
        self._tally(label, verdict, detail)
        if verdict == "FAIL":
            self._keep(label)
        self._flush(label, verdict)

    def _tally(self, label: str, verdict: str, detail: str) -> None:
        assert self.current is not None
        _row(verdict, label, detail)
        self.current.judged[label] = verdict
        self.tally[verdict] += 1
        if verdict != "OK":
            self.reasons[label] = detail
        if verdict == "FAIL":
            self.failed.append(label)
        elif verdict == "BLOCKED":
            self.blocked_why.append((label, detail))

    def _rest(self) -> list[str]:
        if self.current is None:
            return []
        return [c.label for c in self.current.cells if c.label not in self.current.judged]

    def judge(self, label: str, holds: bool, detail: str = "") -> bool:
        """The verdict of one planned cell; an unplanned or repeated label FAILs."""
        if label not in self._rest():
            label, holds = f"UNPLANNED OR REPEATED: {label}", False
        self._count(label, "OK" if holds else "FAIL", detail)
        return holds

    def block(self, label: str, reason: str) -> None:
        """BLOCK a planned cell not judged yet; anything else FAILs."""
        if label not in self._rest():
            self._count(f"UNPLANNED OR REPEATED: {label}", "FAIL", reason)
            return
        self._count(label, "BLOCKED", reason)

    def block_rest(self, reason: str) -> None:
        """BLOCK every cell of the current section not judged yet."""
        for label in self._rest():
            self._count(label, "BLOCKED", reason)

    def setup(self) -> None:
        """Flush calls made between cells (a boot, a stopper) as setup."""
        self._flush("(setup)", "setup")

    def _keep(self, label: str) -> None:
        """Copy the live session's conf and log tail aside, so a FAIL leaves evidence."""
        conf, log = self.session_files()
        if conf is None and log is None:
            print(f"  evidence: none for {label}, no session was live", flush=True)
            return
        slug = "".join(ch if ch.isalnum() else "-" for ch in label).strip("-")[:80] or "cell"
        dest = self.evidence / f"{next(self._evidence_seq):03d}-{slug}"
        try:
            dest.mkdir(parents=True)
            if conf is not None and conf.is_file():
                shutil.copy2(conf, dest / conf.name)
            if log is not None and log.is_file():
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                (dest / f"{log.name}.tail").write_text(
                    "\n".join(lines[-EVIDENCE_TAIL_LINES:]) + "\n", encoding="utf-8")
            self.kept.append(dest)
        except OSError as exc:
            print(f"  evidence NOT kept for {label}: {exc}", flush=True)

    def _section(self, sec: Section, env: dict[str, str], isolate: Callable[[str], None]) -> None:
        """`Blocked` BLOCKs the rest; another exception FAILs the first cell left."""
        if sec.needs and not env.get(sec.needs, "").strip():
            self.block_rest(f"{sec.needs} is not set")
            return
        try:
            isolate(sec.letter)
            sec.run()
        except Blocked as exc:
            self.calls.append({"tool": "(matrix)", "args": {}, "reply": {"blocked": str(exc)}})
            self.block_rest(f"blocked: {exc}")
        except Exception as exc:  # noqa: BLE001 -- reported as a FAIL, never swallowed
            why = f"section aborted: {type(exc).__name__}: {exc}"
            self.calls.append({"tool": "(matrix)", "args": {},
                               "reply": {"exception": why, "traceback": traceback.format_exc()}})
            rest = self._rest()
            if rest:
                self._count(rest[0], "FAIL", why)
            self.block_rest(why)
        for label in self._rest():
            self._count(label, "FAIL", "never reached: the section ended without judging it")

    def run(self, sections: list[str], env: dict[str, str], teardown: Callable[[], None],
            isolate: Callable[[str], None],
            pool: Callable[[list[Section]], live_pool.PoolResult] | None = None,
            summary: Path | None = None) -> int:
        """Run the sections asked for (none means all) and answer the exit code.

        `pool` runs the place-1 sections that are not `alone` as jobs."""
        print(f"transcript: {self.transcript}", flush=True)
        chosen = sorted((s for s in self.sections if not sections or s.letter in sections),
                        key=lambda s: (s.place, s.letter))
        labels = [c.label for s in self.sections for c in s.cells]
        twice = sorted({x for x in labels if labels.count(x) > 1})
        planned = sum(len(s.cells) for s in chosen)
        print(f"PLANNED {planned} cells in {len(chosen)} sections "
              f"({', '.join(s.letter for s in chosen)})", flush=True)
        if twice:
            self.unfinished()
            print(f"==> LIVE MATRIX INVALID: the plan names these cells twice: {twice}",
                  flush=True)
            return EXIT_INVALID
        began = time.monotonic()
        pooled = ([s for s in chosen if s.place == 1 and not s.alone] if pool is not None
                  else [])
        if len({s.letter for s in pooled}) < 2:
            pooled = []          # one job is no pool
        invalid = ""
        try:
            for sec in chosen:
                if pooled and sec is pooled[0]:
                    invalid = self._adopt(pooled, pool(pooled))  # type: ignore[misc]
                if sec in pooled:
                    continue
                print(f"\n== [{sec.letter}] {sec.title}", flush=True)
                self.current = sec
                try:
                    self._section(sec, env, isolate)
                finally:
                    teardown()
                    self.setup()
        finally:
            for sec in chosen:
                self.current = sec
                self.block_rest("the run was interrupted before this cell")
            self._flush("(interrupted)", "setup")
            self._summary(planned, time.monotonic() - began)
            if summary is not None:
                self._declare(summary, chosen, time.monotonic() - began)
        self._close_run()
        self.host.finished = True
        run = self.tally["OK"] + self.tally["FAIL"]
        self.host.leave(kept=bool(invalid or run == 0 or self.failed))
        if invalid:
            print(f"==> LIVE MATRIX INVALID: {invalid}")
            return EXIT_INVALID
        if run == 0:
            print("==> LIVE MATRIX INVALID: no cell ran, so there is no verdict")
            return EXIT_INVALID
        print("==> LIVE MATRIX " + ("FAILED" if self.failed else "PASSED"))
        return EXIT_FAIL if self.failed else EXIT_PASS

    def _adopt(self, pooled: list[Section], result: live_pool.PoolResult) -> str:
        """Count the pooled cells here; answers why the merge is INVALID, or empty."""
        for sec in pooled:
            print(f"\n== [{sec.letter}] {sec.title} (pooled)", flush=True)
            self.current = sec
            for c in sec.cells:
                self._tally(c.label, result.outcomes[c.label], result.reasons.get(c.label, ""))
        for r in result.results:
            # An unplanned label fails the child yet never reaches its summary.
            declared_fail = any(v == "FAIL" for v in r.outcomes().values())
            if (r.rc == 1 and not declared_fail) or r.rc not in (0, 1, 3, None):
                self._tally(f"JOB {r.job.name} EXITED {r.rc}, WHICH ITS SUMMARY DOES NOT "
                            "EXPLAIN", "FAIL", str(r.log))
        with (self.made() / self.transcript.name).open("a", encoding="utf-8") as out:
            for r in result.results:
                if r.summary is not None and Path(r.summary.transcript).is_file():
                    out.write(Path(r.summary.transcript).read_text(encoding="utf-8"))
        return result.invalid

    def _declare(self, path: Path, chosen: list[Section], elapsed: float) -> None:
        """Write this run's cells as a pooled job declares them."""
        outcomes: dict[str, live_pool.Outcome] = {}
        for sec in chosen:
            for c in sec.cells:
                outcomes[c.label] = sec.judged.get(c.label, "BLOCKED")  # type: ignore[assignment]
        reasons = {k: v for k, v in self.reasons.items() if k in outcomes}
        live_pool.write_summary(path, live_pool.Summary(
            tuple(outcomes), outcomes, reasons, str(self.transcript), round(elapsed, 3)))

    def _summary(self, planned: int, elapsed: float) -> None:
        """Repeat every BLOCKED reason and FAIL above the verdict."""
        print(f"\ntranscript: {self.transcript}")
        if self.kept:
            print(f"evidence: {self.evidence}")
        print(f"elapsed: {elapsed:.0f} s\nrecap:")
        for label, reason in self.blocked_why:
            _row("BLOCKED", label, reason)
        for label in self.failed:
            _row("FAIL", label)
        run = self.tally["OK"] + self.tally["FAIL"]
        print(f"PLANNED {planned} RUN {run} OK {self.tally['OK']} "
              f"FAIL {self.tally['FAIL']} BLOCKED {self.tally['BLOCKED']}", flush=True)


def _row(word: str, label: str, detail: str = "") -> None:
    """One result line."""
    print(f"  {word:<7}  {label}{'  ' + detail if detail else ''}", flush=True)
