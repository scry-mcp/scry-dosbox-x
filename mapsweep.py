"""The sweep: real linker maps read by the shipped reader, against what each one holds.

The manifest carries the expected counts, so drift is red in both directions: a count that
rose means the reader started reading something that is not a symbol. It is manual, not on
the commit path (`tests/gates-manual.txt`): the maps live outside this repository and would
make the gate INVALID in every other clone. Manifest paths name a repository and a path
inside it; `--root` (or `MAPSWEEP_ROOT`) says where those repositories live.

Two limits. It judges whether a count moved, not whether it is correct: the first time a row
is written, whatever the reader says becomes the expectation. And it pins `parse`'s numbers,
not `symbols_load`'s `plan.kept` and `plan.overlay_idle`, which come after `plan()` filters,
so a regression inside `plan()` moves nothing here.

EXIT CODES:
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

NUMERIC = ("symbols", "overlay_idle", "unreadable")

# Bounds the quoting only; the count stays exact.
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
    """Something could not be examined, which is not a disagreement about a map."""


def _expand(path: Path) -> Path:
    """`~` resolved, or INVALID.

    `expanduser()` raises `RuntimeError` on an unknown user or no home.
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
        # A key beginning `_` is prose (JSON has no comments). Deliberately not a general
        # skip: a mistyped project name still comes back INVALID.
        if name.startswith("_"):
            notes += 1
            continue
        if not isinstance(row, dict) or "path" not in row:
            raise Invalid(f"project {name!r} has no `path`, so nothing says which file "
                          f"it is about")
        # pathlib discards the left side of `Path("/root") / "/abs"`, and `..` walks out
        # too, so the report would name a root it never read.
        rel = Path(str(row["path"]))
        if rel.is_absolute() or ".." in rel.parts:
            raise Invalid(
                f"project {name!r} has path {str(row['path'])!r}, which is not relative "
                f"to the root. An absolute path or one carrying `..` escapes --root, so "
                f"the report would state a root it did not read")
        expect = row.get("expect")
        if not isinstance(expect, dict) or not expect:
            # A row asserting nothing prints exactly like one that passed.
            raise Invalid(f"project {name!r} expects nothing, so its line in the report "
                          f"is indistinguishable from one that passed. Give it "
                          f"`symbols`, `overlay_idle`, `unreadable` or `refused`")
        unknown = sorted(set(expect) - set(NUMERIC) - {"refused"})
        if unknown:
            raise Invalid(f"project {name!r} expects {unknown}, which this does not "
                          f"check. A key nothing reads asserts nothing while looking "
                          f"exactly like an assertion")
        # Values as well as keys: `""` matches any refusal, and numbers beside `refused`
        # would never be compared.
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
            # `bool` first: it is an `int` subclass, and `true` would pin a count of 1.
            if isinstance(expect[key], bool) or not isinstance(expect[key], int):
                raise Invalid(
                    f"project {name!r} expects {key} = {expect[key]!r}, which is not a "
                    f"whole number")
        out[name] = {"path": str(row["path"]), "expect": expect}
    # After the notes are dropped: a file of nothing but prose is a populated object.
    if not out:
        raise Invalid(f"the manifest at {path} names no project, so there is nothing to "
                      f"sweep. An empty sweep is not a clean sweep")
    # The note count lets the report show skipped rows.
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
        # `latin-1` never fails nor substitutes, unlike the tool's UTF-8 with
        # `errors="replace"`: high bytes (CP437) can read differently, 0x85 splitting a line.
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise Invalid(f"{name}: cannot read {path}: {exc}") from None
    try:
        syms, unreadable = sym.parse(text, report)
    except sym.BadSymbolText as exc:
        res.fmt = report.fmt or "?"
        res.refused = str(exc)
        res.rows = list(report.unreadable_rows)
        res.unreadable = len(res.rows)
        wanted = expect.get("refused")
        if not isinstance(wanted, str):
            res.disagreements.append(
                f"expected symbols and the reader REFUSED the file: {exc}")
        elif wanted not in res.refused:
            # The reason is the expectation: a different refusal is a reader regression.
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
        write(f"                 ... and {extra} more row(s) not quoted here")
    for bad in res.disagreements or []:
        write(f"    DISAGREES  {res.name}: {bad}")


class _Parser(argparse.ArgumentParser):
    """argparse with its output routed through `write`, so a usage failure is in the transcript."""

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
    """`write` and `env` are seams for driving this without a shell."""
    environ = os.environ if env is None else env
    ap = _Parser(write, "mapsweep", __doc__ and __doc__.splitlines()[0])
    ap.add_argument("--manifest", default=environ.get("MAPSWEEP_MANIFEST", ""),
                    help="the project list (default: $MAPSWEEP_MANIFEST)")
    ap.add_argument("--root", default=environ.get("MAPSWEEP_ROOT", ""),
                    help="where those projects live (default: $MAPSWEEP_ROOT)")
    ap.add_argument("--project", action="append", default=[],
                    help="sweep only this project; repeatable")
    try:
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
            # Not the working directory: that would read somebody else's file.
            raise Invalid("no root. Pass --root or set MAPSWEEP_ROOT to the directory "
                          "the projects live in; the manifest's paths are relative to it")
        manifest, notes = _load_manifest(_expand(Path(args.manifest)))
        wanted = list(args.project)
        unknown = [p for p in wanted if p not in manifest]
        if unknown:
            raise Invalid(f"--project named {unknown}, which the manifest does not hold. "
                          f"It holds {sorted(manifest)}")
        # No emptiness check: the manifest and `unknown` checks leave nothing unselectable.
        selected = [n for n in manifest if not wanted or n in wanted]
        root = _expand(Path(args.root))
    except Invalid as exc:
        write(f"mapsweep: INVALID: {exc}")
        return INVALID

    # Read every project before INVALID decides: one unbuilt tree must not discard the rest.
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
    # INVALID outranks red: "I could not look" is not a finding about a map.
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
    # State the denominator: `--project X` narrows the scope.
    write(f"mapsweep: {len(results)} of {len(manifest)} project(s) as the manifest says")
    return OK


if __name__ == "__main__":  # pragma: no cover - the shell entry point
    raise SystemExit(main())
