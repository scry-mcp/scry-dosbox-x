"""The ledger behind `dosbox_x_live_matrix.py`: the sections and their cells, declared
before anything boots, the calls each cell made, and the verdict that closes the run.

It knows the server only through the call it makes: which arguments of a tool are waits, so a
call that could wait past the ceiling is never made. OK, FAIL and BLOCKED are defined once, in
the entry script's docstring.
"""
from __future__ import annotations

import inspect
import json
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

from scry_core import live_pool

EXIT_PASSED, EXIT_FAILED, EXIT_INVALID = 0, 1, 3

#: How long one call may be allowed to wait for the guest. A call whose own bound is longer is
#: never made: its cell is BLOCKED, because a matrix that waits out a hung channel measures the
#: wait. The session's own bound (`start`'s `seconds`) is not a wait.
WAIT_CEILING_S = 30.0
_WAIT_ARGS = ("seconds", "wait", "plan_wait")
_STEP_LISTS = ("steps", "act", "plan")

#: What a call may take beyond the wait it declares before it counts as hung: a console round
#: trip, and a step count at its ceiling, which settles every step.
CALL_GRACE_S = 180.0

#: How much of a failed session's log is kept beside the transcript.
EVIDENCE_TAIL_LINES = 200


class Blocked(Exception):
    """A call the matrix refuses to make, or one that never returned: its cell is BLOCKED."""


@dataclass(frozen=True)
class Cell:
    """One planned verdict: its label, unique in the run, and where its expectation comes from
    (a `REFERENCE.md` section, a docstring, or `known:` and what establishes it)."""
    label: str
    source: str


@dataclass
class Section:
    letter: str
    title: str
    cells: list[Cell]
    run: Callable[[], None]
    needs: str = ""              # the environment variable without which the section cannot run
    judged: dict[str, str] = field(default_factory=dict)
    # WHERE IN THE RUN, beside the letter order: a section that has to open the run or close it
    # (the focus gate's control and verdict, which span every other section) says so here.
    place: int = 1
    # A SECTION THAT TAKES THE FOCUS BY DESIGN runs alone in the run's own process, never in a
    # pool beside other jobs, which would then be judged on its window.
    alone: bool = False


def _waits(kw: dict[str, Any], params: dict[str, inspect.Parameter]) -> Iterator[tuple[str, Any]]:
    """Every wait a call declares, its own and those of the steps it carries."""
    for arg in _WAIT_ARGS:
        if arg in params:
            yield arg, kw.get(arg, params[arg].default)
    for lst in _STEP_LISTS:
        for step in kw.get(lst) or []:
            if isinstance(step, dict):
                for arg in _WAIT_ARGS:
                    if arg in step:
                        yield f"{lst}[{step.get('op')}].{arg}", step[arg]


class Ledger:
    """Everything one run records. One instance per process. The transcript is JSON Lines, one
    record per call, tagged with the cell it fed and that cell's verdict."""

    def __init__(self) -> None:
        self.scratch = Path(tempfile.mkdtemp(prefix="dosbox-x-live-matrix-"))
        self.transcript = self.scratch / "transcript.jsonl"
        self.evidence = self.scratch / "evidence"
        self.sections: list[Section] = []
        self.current: Section | None = None
        self.calls: list[dict[str, Any]] = []
        self.tally = {"OK": 0, "FAIL": 0, "BLOCKED": 0}
        self.failed: list[str] = []
        self.blocked_why: list[tuple[str, str]] = []
        #: The detail of every cell that is not OK, for the summary a pooled run declares.
        self.reasons: dict[str, str] = {}
        self.kept: list[Path] = []
        #: What a FAIL keeps: the conf and the log of the session live when it failed.
        self.session_files: Callable[[], tuple[Path | None, Path | None]] = lambda: (None, None)
        #: What ends a call that never returned: the emulator it is talking to.
        self.on_hang: Callable[[], None] = lambda: None
        self._names = count(1)
        self._evidence_seq = count(1)
        print(f"transcript: {self.transcript}", flush=True)

    # ------------------------------------------------------------------ declaring

    def section(self, letter: str, title: str, cells: list[Cell], needs: str = "",
                place: int = 1, alone: bool = False
                ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a section with the cells it will judge, before anything runs. `place` 0 runs
        it before every section of place 1, 2 after them; within a place, by letter. `alone`:
        it takes the focus by design, so a pooled run keeps it out of the pool."""
        def register(fn: Callable[[], None]) -> Callable[[], None]:
            self.sections.append(Section(letter, title, cells, fn, needs, place=place,
                                         alone=alone))
            return fn
        return register

    # ------------------------------------------------------------------ calling

    def call(self, fn: Callable[..., Any], exempt: str = "", **kw: Any) -> dict[str, Any]:
        """Call a tool as the client would and keep the whole reply for the transcript.

        Arguments the tool does not take are the matrix's own bug and raise here, before the
        call. A wait above the ceiling, the call's own or a step's, is not made (`Blocked`)
        unless `exempt` says why it cannot wait that long. A call still running past its
        declared wait plus `CALL_GRACE_S` is hung: the emulator is ended under it and the cell
        is BLOCKED. An exception the tool raises becomes a reply carrying it, so the cell that
        reads it FAILs by name."""
        name = getattr(fn, "__name__", repr(fn))
        signature = inspect.signature(fn)
        signature.bind(**kw)
        bound = 0.0
        for arg, value in _waits(kw, dict(signature.parameters)):
            if name == "start" and arg == "seconds":
                continue
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

    def fresh(self, suffix: str) -> str:
        """An absolute path in this run's scratch that does not exist yet."""
        return str(self.scratch / f"n{next(self._names)}{suffix}")

    # ------------------------------------------------------------------ judging

    def _flush(self, label: str, verdict: str) -> None:
        sec = self.current
        tag = f"[{sec.letter}] {sec.title}" if sec else "(none)"
        with self.transcript.open("a", encoding="utf-8") as fh:
            for rec in self.calls:
                fh.write(json.dumps({"section": tag, "cell": label, "verdict": verdict, **rec},
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
        """The verdict of one planned cell, once. A label nobody planned, or judged twice, is
        this script's own defect and fails under its own name."""
        if label not in self._rest():
            label, holds = f"UNPLANNED OR REPEATED: {label}", False
        self._count(label, "OK" if holds else "FAIL", detail)
        return holds

    def block(self, label: str, reason: str) -> None:
        """BLOCKED, with the reason, for a planned cell not judged yet; anything else is the
        script's own defect and fails under its own name."""
        if label not in self._rest():
            self._count(f"UNPLANNED OR REPEATED: {label}", "FAIL", reason)
            return
        self._count(label, "BLOCKED", reason)

    def block_rest(self, reason: str) -> None:
        """Every cell of the current section not judged yet, BLOCKED with one reason. A section
        that still means to judge a later cell blocks the others by name instead."""
        for label in self._rest():
            self._count(label, "BLOCKED", reason)

    def setup(self) -> None:
        """Calls made between cells (a boot, a stopper) go to the transcript as setup."""
        self._flush("(setup)", "setup")

    def _keep(self, label: str) -> None:
        """Copy the live session's conf and the tail of its log out of the way, so a cell that
        fails once leaves something to read after the session is gone, and say so when no
        session was live. A copy that fails costs this cell its evidence and nothing else."""
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

    # ------------------------------------------------------------------ the run

    def _section(self, sec: Section, env: dict[str, str], isolate: Callable[[str], None]) -> None:
        """One section, and what its end means. `Blocked` and an unset variable BLOCK what is
        left. Any other exception is a defect met while running, the matrix's or the server's,
        and it may not read as a pass: the first cell left FAILs with it, the rest are BLOCKED.
        A cell the section returned without judging is the script's defect, a FAIL."""
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
        """Run the sections asked for, in letter order, and answer the exit code; `sections`
        empty is all of them. The summary is printed however the run ends, an interruption
        included, with the cells it never reached counted BLOCKED.

        `pool` runs the place-1 sections that are not `alone` as jobs of their own and answers
        their merged result, which is counted here as if they had run in this process; the
        `alone` ones follow in this process. `summary` is where a run that is one of those jobs
        declares what it judged, however it ends."""
        chosen = sorted((s for s in self.sections if not sections or s.letter in sections),
                        key=lambda s: (s.place, s.letter))
        labels = [c.label for s in self.sections for c in s.cells]
        twice = sorted({x for x in labels if labels.count(x) > 1})
        planned = sum(len(s.cells) for s in chosen)
        print(f"PLANNED {planned} cells in {len(chosen)} sections "
              f"({', '.join(s.letter for s in chosen)})", flush=True)
        if twice:
            print(f"INVALID: the plan names these cells twice: {twice}", flush=True)
            return EXIT_INVALID
        began = time.monotonic()
        pooled = ([s for s in chosen if s.place == 1 and not s.alone] if pool is not None
                  else [])
        if len({s.letter for s in pooled}) < 2:
            pooled = []          # one job is no pool: it runs here, its rows live
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
        if invalid:
            print(f"==> LIVE MATRIX INVALID: {invalid}")
            return EXIT_INVALID
        run = self.tally["OK"] + self.tally["FAIL"]
        if run == 0:
            print("==> LIVE MATRIX INVALID: no cell ran, so there is no verdict")
            return EXIT_INVALID
        print("==> LIVE MATRIX " + ("FAILED" if self.failed else "PASSED"))
        return EXIT_FAILED if self.failed else EXIT_PASSED

    def _adopt(self, pooled: list[Section], result: live_pool.PoolResult) -> str:
        """The pooled sections' cells counted as judged here, in plan order, and their jobs'
        transcripts appended to this run's; answers why the merge is INVALID, or empty."""
        for sec in pooled:
            print(f"\n== [{sec.letter}] {sec.title} (pooled)", flush=True)
            self.current = sec
            for c in sec.cells:
                self._tally(c.label, result.outcomes[c.label], result.reasons.get(c.label, ""))
        for r in result.results:
            # A JOB'S EXIT CODE THAT ITS SUMMARY DOES NOT EXPLAIN is a failure of its own: a
            # cell judged under a label nobody planned, or twice, fails the child by that name
            # and never reaches the summary, which may declare only the planned labels. 1 is a
            # FAIL and 3 a run with nothing judged; anything else is a child that did not end
            # by itself.
            declared_fail = any(v == "FAIL" for v in r.outcomes().values())
            if (r.rc == 1 and not declared_fail) or r.rc not in (0, 1, 3, None):
                self._tally(f"JOB {r.job.name} EXITED {r.rc}, WHICH ITS SUMMARY DOES NOT "
                            "EXPLAIN", "FAIL", str(r.log))
        with self.transcript.open("a", encoding="utf-8") as out:
            for r in result.results:
                if r.summary is not None and Path(r.summary.transcript).is_file():
                    out.write(Path(r.summary.transcript).read_text(encoding="utf-8"))
        return result.invalid

    def _declare(self, path: Path, chosen: list[Section], elapsed: float) -> None:
        """This run's cells as one job of a pooled run declares them (`live_pool`)."""
        outcomes: dict[str, live_pool.Outcome] = {}
        for sec in chosen:
            for c in sec.cells:
                outcomes[c.label] = sec.judged.get(c.label, "BLOCKED")  # type: ignore[assignment]
        reasons = {k: v for k, v in self.reasons.items() if k in outcomes}
        live_pool.write_summary(path, live_pool.Summary(
            tuple(outcomes), outcomes, reasons, str(self.transcript), round(elapsed, 3)))

    def _summary(self, planned: int, elapsed: float) -> None:
        """The recap above the verdict: every BLOCKED reason and every FAIL again, so the tail
        of the output carries the reasons beside the word that judges them."""
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
    """One result line, the word in a fixed column so the labels line up."""
    print(f"  {word:<7}  {label}{'  ' + detail if detail else ''}", flush=True)
