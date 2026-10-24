"""The sweep: real linker maps read by the shipped reader, against what each one holds.

WHY IT EXISTS.  This package claims to read three toolchains' symbol output, and a format
is not demonstrated by one artefact, nor by numbers a person produced by hand: a number
nobody re-checks is a number that was true once.  So the sweep reads every real map on this
machine, in place, and compares what the reader makes of it against what the manifest
says it holds.

WHY THE MANIFEST IS THE ORACLE AND NOT A LOG.  A sweep that merely PRINTS what it read
is an instrument nobody re-runs, and its output is indistinguishable from the output of
a reader that has silently started dropping a quarter of every file.  Carrying the
expectation makes drift RED IN BOTH DIRECTIONS: a count that fell, and a count that
rose.  The second matters as much as the first, because a reader that suddenly finds
more symbols in an unchanged file has started reading something that is not a symbol.

WHY IT IS MANUAL AND NOT ON THE COMMIT PATH.  The material lives OUTSIDE this
repository -- one of the projects is unpublished -- and it is not versioned here: it is
the author's own material and this package is published.  On the
commit path this would therefore be INVALID in every clone but one, and a gate that is
almost always invalid is a gate people learn to ignore.  It is declared in
`tests/gates-manual.txt` with that reason.

WHY THE PATHS ARE RELATIVE AND THE ROOT ARRIVES AT RUN TIME.  A manifest naming
`/Users/<somebody>/Code/...` carries a username and a folder layout that mean nothing to
anyone else and that go stale the first time a directory moves.  The manifest names a
project by its REPOSITORY NAME and a path inside it; `--root` (or `MAPSWEEP_ROOT`) says
where those repositories live on this machine.

WHAT IT DOES NOT DO, said out loud, and there are TWO limits rather than one.

IT DOES NOT JUDGE WHETHER A COUNT IS CORRECT: it judges whether it MOVED.  The first
time a project's row is written, whatever the reader says becomes the expectation, so a
reader that was already wrong stays wrong and the sweep goes on agreeing with it.  What
closes that is reading the map -- a person's job, done once, exactly as blessing any
golden is.

AND IT PINS `parse`'s NUMBERS, NOT THE ONES THE MCP TOOL REPORTS.  `symbols_load`
answers with `plan.kept` and `plan.overlay_idle` computed AFTER `plan()` has applied the
section-label filter, the unplaceable classes, the caller's `pattern`, truncation and
collision renaming (`plan.parsed` is before them).  This counts symbols as the READER
produced them.  The two agree on a map with no filtered symbol, and part company the
moment one is filtered -- so a regression
inside `plan()` moves what a tool caller sees and moves NOTHING here.  Stated rather
than assumed, because an undeclared limit is the same as a claim.

EXIT CODES, and 1 is never conflated with 3:
    0  every project selected agreed with its expectation
    1  at least one DISAGREED. The honest red
    2  bad usage
    3  INVALID: nothing was examined, or something could not be. A missing manifest, a
       manifest that will not parse, no projects in it, a selection matching none, a
       path that is not there, a row that expects nothing. Never green, never red
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import dosbox_symbols as sym

OK, RED, USAGE, INVALID = 0, 1, 2, 3

# The three numbers a row may pin, and the ONLY three. An unknown key is a typo that
# would otherwise assert nothing while looking exactly like an assertion -- the shape
# this whole module exists to make impossible.
NUMERIC = ("symbols", "overlay_idle", "unreadable")

# How many unreadable rows are QUOTED per project. The count is exact for what it counts; this
# bounds the QUOTING, because hundreds of rows of one shape teach nothing the first three do
# not, and a report long enough to be skimmed is a report whose verdict gets skimmed
# with it. It says how many it withheld rather than trailing off.
QUOTE_MAX = 3


@dataclass
class Result:
    """One project, read. `disagreements` empty means it matched."""

    name: str
    path: Path
    fmt: str = ""
    symbols: int = 0
    overlay_idle: int = 0
    unreadable: int = 0
    rows: list[str] | None = None
    refused: str = ""
    disagreements: list[str] | None = None


class Invalid(Exception):
    """Something could not be examined. Distinct from a disagreement, on purpose: "the
    map changed" and "I never read the map" are different facts and only the first is a
    finding about the reader."""


def _expand(path: Path) -> Path:
    """`~` resolved, or INVALID -- never a traceback and never exit 1.

    `Path.expanduser()` RAISES `RuntimeError` when it cannot resolve a leading `~`: an
    unknown user (`~olduser/Code`, an invocation copied from another machine) or no home
    at all (a launchd job, a container). Uncaught, the process would die with a traceback
    and status **1** -- which this module documents as "at least one DISAGREED. The honest
    red" -- while nothing had been examined, exactly the conflation the docstring says
    never happens.
    """
    try:
        return path.expanduser()
    except RuntimeError as exc:
        raise Invalid(f"cannot resolve {str(path)!r}: {exc}. Nothing was examined, so "
                      f"this is not a finding about any map") from None


def _load_manifest(path: Path) -> tuple[dict[str, dict[str, object]], int]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Invalid(f"cannot read the manifest at {path}: {exc}") from None
    except ValueError as exc:
        raise Invalid(f"the manifest at {path} will not parse as JSON: {exc}") from None
    if not isinstance(raw, dict):
        raise Invalid(f"the manifest at {path} is not a JSON object, so it names no "
                      f"project at all")
    out: dict[str, dict[str, object]] = {}
    notes = 0
    for name, row in raw.items():
        # A KEY BEGINNING `_` IS PROSE. JSON has no comments, and a manifest of
        # expectations that cannot explain where its numbers came from is a list of
        # numbers nobody can check -- which is how a control quietly becomes a
        # superstition. One character, and it is deliberately NOT a general "skip
        # anything odd": a mistyped project name is still a project, still has no file,
        # and still comes back INVALID, so this cannot become a way to lose a row.
        if name.startswith("_"):
            notes += 1
            continue
        if not isinstance(row, dict) or "path" not in row:
            raise Invalid(f"project {name!r} has no `path`, so nothing says which file "
                          f"it is about")
        # RELATIVE, AND HELD BY A MECHANISM RATHER THAN BY THE AUTHOR REMEMBERING.
        # `Path("/root") / "/somewhere/else"` is `/somewhere/else` -- pathlib discards
        # the left side entirely -- so an absolute path sweeps green on ONE machine while
        # the report line names a root it never touched. `..` walks out the same way.
        # This file's own rule says a path names a repository and never a location; for
        # an instrument whose thesis is mechanism over memory, a rule held by nothing was
        # the gap worth closing.
        rel = Path(str(row["path"]))
        if rel.is_absolute() or ".." in rel.parts:
            raise Invalid(
                f"project {name!r} has path {str(row['path'])!r}, which is not relative "
                f"to the root. An absolute path or one carrying `..` escapes --root, so "
                f"the report would state a root it did not read")
        expect = row.get("expect")
        if not isinstance(expect, dict) or not expect:
            # A ROW THAT ASSERTS NOTHING IS NOT A LIGHTER ROW. It prints exactly like one
            # that passed, so the project silently leaves the control while still
            # appearing in its report.
            raise Invalid(f"project {name!r} expects nothing, so its line in the report "
                          f"is indistinguishable from one that passed. Give it "
                          f"`symbols`, `overlay_idle`, `unreadable` or `refused`")
        unknown = sorted(set(expect) - set(NUMERIC) - {"refused"})
        if unknown:
            raise Invalid(f"project {name!r} expects {unknown}, which this does not "
                          f"check. A key nothing reads asserts nothing while looking "
                          f"exactly like an assertion")
        # THE VALUES, NOT ONLY THE KEYS. Keys alone are one type-test short of the
        # claim, and every way through is a shape an author writes. All three pass a
        # keys-only check:
        #
        #   {"refused": ""}    `"" in anything` is True, so it matched EVERY refusal
        #                      message there is -- a placeholder written before the
        #                      wording is known accepts a reader regression wearing the
        #                      known state's costume, which is the one thing the
        #                      reason-matching exists to prevent.
        #   {"refused": null}  passed validation, matched nothing, and printed a line
        #                      BYTE-IDENTICAL to a row that pinned all three numbers.
        #   {"refused": "x", "symbols": 99999}
        #                      the refusal branch RETURNS before the numeric loop, so
        #                      those numbers were never compared and nothing said so.
        if "refused" in expect:
            wanted = expect["refused"]
            if not isinstance(wanted, str) or not wanted.strip():
                raise Invalid(
                    f"project {name!r} expects `refused` to be {wanted!r}, and it has to "
                    f"be a NON-EMPTY string: the expectation is the REASON, and an empty "
                    f"one matches every refusal message there is")
            also = sorted(set(expect) & set(NUMERIC))
            if also:
                raise Invalid(
                    f"project {name!r} expects a refusal AND {also}. A refused file "
                    f"yields no counts, so those would never be compared -- and a row "
                    f"whose expectations are silently not evaluated is worse than a row "
                    f"that never had them")
        for key in NUMERIC:
            if key not in expect:
                continue
            # `bool` FIRST, because it is a subclass of `int`: JSON `true` compares equal
            # to 1 and `false` to 0, so a row could pin a count with a token that is not
            # one and read as an assertion.
            if isinstance(expect[key], bool) or not isinstance(expect[key], int):
                raise Invalid(
                    f"project {name!r} expects {key} = {expect[key]!r}, which is not a "
                    f"whole number")
        out[name] = {"path": str(row["path"]), "expect": expect}
    # CHECKED AFTER THE NOTES ARE DROPPED, never before. A file holding nothing but
    # prose is syntactically a populated object, so testing `raw` would have let it
    # through to sweep zero projects and print like a clean run.
    if not out:
        raise Invalid(f"the manifest at {path} names no project, so there is nothing to "
                      f"sweep. An empty sweep is not a clean sweep")
    # THE PROSE COUNT TRAVELS WITH THE PROJECTS, so the report can say how many rows the
    # file held and how many were skipped. Two ways a project leaves in silence
    # otherwise: a name that begins `_`, which the skip above takes before it is even
    # checked for a `path`; and a DUPLICATE JSON key, which `json.loads` resolves to the
    # last occurrence with no warning. Neither is visible in a report that prints only
    # what it read -- 6 projects and 7 projects look identical to a reader who does not
    # already know the number.
    return out, notes


def _read(name: str, path: Path, expect: Mapping[str, object]) -> Result:
    """One project through the shipped reader, and what disagreed."""
    if not path.is_file():
        raise Invalid(f"{name}: {path} is not a file, so this project was NOT swept. "
                      f"That is not the same as its map having changed")
    report = sym.ParseReport()
    res = Result(name=name, path=path, disagreements=[])
    assert res.disagreements is not None
    try:
        # `latin-1` NEVER FAILS AND NEVER SUBSTITUTES a byte, where the tool reads UTF-8 with
        # `errors="replace"`: a map with high bytes (CP437 in a module name) can read
        # differently in the two, 0x85 even splitting a line here.
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise Invalid(f"{name}: cannot read {path}: {exc}") from None
    try:
        syms, unreadable = sym.parse(text, report)
    except sym.BadSymbolText as exc:
        res.fmt = report.fmt or "?"
        res.refused = str(exc)
        # THE ROWS SURVIVE THE REFUSAL, and this is the one path where they matter most: a
        # file refused for losing more rows than it kept is refused by a message that can
        # only describe them, and this caller holds the report that lists them. A count says
        # a population was cut; the row says what the cut was.
        res.rows = list(report.unreadable_rows)
        res.unreadable = len(res.rows)
        wanted = expect.get("refused")
        if not isinstance(wanted, str):
            res.disagreements.append(
                f"expected symbols and the reader REFUSED the file: {exc}")
        elif wanted not in res.refused:
            # THE REASON IS THE EXPECTATION, not the fact of refusing. Every refusal is a
            # refusal, so matching on "it was refused" accepts a file that started failing
            # for a different reason -- a reader regression wearing the known state's
            # costume.
            res.disagreements.append(
                f"refused, but not for the expected reason. expected to contain "
                f"{wanted!r}, got: {res.refused}")
        return res
    if isinstance(expect.get("refused"), str):
        res.disagreements.append(
            f"expected a refusal containing {expect['refused']!r}, but the file read "
            f"clean at {len(syms)} symbols")
    res.fmt = report.fmt or "?"
    res.symbols = len(syms)
    res.overlay_idle = sum(1 for s in syms if s.idle)
    res.unreadable = unreadable
    res.rows = list(report.unreadable_rows)
    for key in NUMERIC:
        if key not in expect:
            continue
        want = expect[key]
        got = getattr(res, key)
        if want != got:
            # BOTH DIRECTIONS. A count that ROSE against an unchanged file means the
            # reader has begun reading something that is not a symbol, which is the
            # quieter half and the one a "did it drop" test never sees.
            res.disagreements.append(f"{key}: expected {want}, read {got}")
    return res


def _render(res: Result, write: Callable[[str], None]) -> None:
    head = f"  {res.name:<12} {res.fmt:<14}"
    if res.refused:
        write(f"{head} REFUSED: {res.refused}")
    else:
        write(f"{head} symbols={res.symbols} overlay_idle={res.overlay_idle} "
              f"unreadable={res.unreadable}")
    for row in (res.rows or [])[:QUOTE_MAX]:
        write(f"                 unread line: {row.rstrip()}")
    extra = len(res.rows or []) - QUOTE_MAX
    if extra > 0:
        # SAID, NEVER TRAILED OFF. A report that stops quoting without saying it stopped
        # reads as a complete list of what was lost.
        write(f"                 ... and {extra} more row(s) not quoted here")
    for bad in res.disagreements or []:
        write(f"    DISAGREES  {res.name}: {bad}")


class _Parser(argparse.ArgumentParser):
    """ARGPARSE'S OWN OUTPUT GOES THROUGH `write`, because argparse writes to stdout/stderr
    directly and this module's whole seam is that a caller can drive `main` with a list and
    read what it said: a usage failure that came back as `rc == 2` and an EMPTY transcript could
    not say WHICH argument was wrong. Its three printing methods are routed here, not the
    process's streams, so nothing else that writes meanwhile is captured."""

    def __init__(self, write: Callable[[str], None], prog: str, description: str | None) -> None:
        super().__init__(prog=prog, description=description)
        self._write = write

    def _lines(self, text: str | None) -> None:
        for line in (text or "").splitlines():
            self._write(line)

    def print_usage(self, file: object = None) -> None:
        self._lines(self.format_usage())

    def print_help(self, file: object = None) -> None:
        self._lines(self.format_help())

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        self._lines(message)
        raise SystemExit(status)


def main(argv: Sequence[str] | None = None, *,
         write: Callable[[str], None] = print,
         env: Mapping[str, str] | None = None) -> int:
    """`write` and `env` are SEAMS, so the suite drives this without a shell or a real
    machine: every case builds its own root and its own manifest under `tmp_path`."""
    environ = os.environ if env is None else env
    ap = _Parser(write, "mapsweep", __doc__ and __doc__.splitlines()[0])
    ap.add_argument("--manifest", default=environ.get("MAPSWEEP_MANIFEST", ""),
                    help="the project list (default: $MAPSWEEP_MANIFEST)")
    ap.add_argument("--root", default=environ.get("MAPSWEEP_ROOT", ""),
                    help="where those projects live (default: $MAPSWEEP_ROOT)")
    ap.add_argument("--project", action="append", default=[],
                    help="sweep only this project; repeatable")
    try:
        # An UNKNOWN OPTION EXITS. Ignored, it leaves the setting at its default, and a
        # run that measured the wrong thing prints exactly like one that measured the
        # right one. What argparse says goes through `write` (`_Parser`).
        args = ap.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        return USAGE if code not in (0, None) else OK

    try:
        if not args.manifest:
            raise Invalid("no manifest. Pass --manifest or set MAPSWEEP_MANIFEST: this "
                          "sweep reads material that lives outside the repository, so "
                          "there is no default that is true on two machines")
        if not args.root:
            # NOT the working directory. A relative path resolved against wherever the
            # caller happened to stand is how a sweep reads somebody else's file and
            # reports about this one.
            raise Invalid("no root. Pass --root or set MAPSWEEP_ROOT to the directory "
                          "the projects live in; the manifest's paths are relative to it")
        manifest, notes = _load_manifest(_expand(Path(args.manifest)))
        wanted = list(args.project)
        unknown = [p for p in wanted if p not in manifest]
        if unknown:
            raise Invalid(f"--project named {unknown}, which the manifest does not hold. "
                          f"It holds {sorted(manifest)}")
        # NO EMPTINESS CHECK HERE, and its absence is deliberate rather than an
        # oversight: `_load_manifest` refuses an empty manifest and the `unknown` check
        # above refuses a name it does not hold, so between them there is no input that
        # reaches this line with nothing selected. A guard here would be unreachable,
        # advertising an INVALID cause that cannot occur.
        selected = [n for n in manifest if not wanted or n in wanted]
        root = _expand(Path(args.root))
    except Invalid as exc:
        write(f"mapsweep: INVALID: {exc}")
        return INVALID

    # EVERY PROJECT IS READ, AND WHAT WAS READ IS REPORTED, before any INVALID decides
    # the verdict. As a comprehension the FIRST unreadable path would abort it and throw
    # away the projects already read: a mistyped `--root` prints one line blaming one map
    # for the argument, and one tree whose symbol file is build output not yet built
    # discards every good reading to say one thing about the missing one. By this
    # module's own criterion, a
    # gate that is INVALID whenever an unrelated tree is unbuilt is a gate people learn
    # to ignore.
    results: list[Result] = []
    invalid: list[str] = []
    for name in selected:
        try:
            results.append(_read(name, root / str(manifest[name]["path"]),
                                 manifest[name]["expect"]))  # type: ignore[arg-type]
        except Invalid as exc:
            invalid.append(str(exc))

    write(f"mapsweep: {len(selected)} of {len(manifest)} project(s) under {root}"
          + (f" ({notes} note row(s) skipped)" if notes else ""))
    for res in results:
        _render(res, write)
    bad = [r for r in results if r.disagreements]
    # INVALID OUTRANKS RED, because "I could not look" is not a finding about a map and
    # must not be reported as one. Both are said, in that order, so a run that could not
    # read one project still hands over what the others showed.
    for line in invalid:
        write(f"mapsweep: INVALID: {line}")
    if bad:
        write(f"mapsweep: {len(bad)} of {len(results)} project(s) read DISAGREE with the "
              f"manifest")
    if invalid:
        write(f"mapsweep: {len(invalid)} of {len(selected)} project(s) could NOT be "
              f"examined, so this run is not a verdict about them")
        return INVALID
    if bad:
        return RED
    # THE DENOMINATOR IS SAID. `--project X` narrows the scope to one row of the manifest,
    # and a closing line claiming the MANIFEST was satisfied would be read as the whole of
    # it by anyone who did not count the rows.
    write(f"mapsweep: {len(results)} of {len(manifest)} project(s) as the manifest says")
    return OK


if __name__ == "__main__":  # pragma: no cover - the shell entry point
    raise SystemExit(main())
