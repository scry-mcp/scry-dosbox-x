"""The source index of the dictionaries: what the real sources say at every place an entry cites,
and the lists each dictionary must cover, captured from the sources and committed, so the ordinary
tests judge an entry with no network.

Two sources are read. Ralf Brown's interrupt list, release 61, from its four archives
(`inter61a.zip` to `inter61d.zip`, each held to its SHA-256). DOSBox-X, from a repository that
holds the pinned commit: files are read with `git show <pin>:<path>`, so the checkout's own
branch and working tree do not matter. A dictionary's `ref` names one place; this tool opens it
and keeps the line it finds there.

Locators:
    rbil61:INTERRUP.G D-214C              the title line under the section header `D-214C`
    rbil61:INTERRUP.G D-2158@2            the second section with that header, when several have it
    rbil61:INTERRUP.G #01680 05h (5)      the row of table 01680 that starts with that text
    dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c
    dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x65 case 0x01     (inside the case of 0x65)
    dosbox-x:include/dos_inc.h DOSERR_FILE_NOT_FOUND

EXIT CODES:
    0  the committed index equals what the sources say (or `--write` wrote it)
    1  they differ: the honest red
    2  bad usage
    3  INVALID: nothing was read, or something could not be (an archive that is not the pinned
       one, a pin the repository lacks, a ref that resolves to no line or to two)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scry_core import verdict
from scry_core.knowledge import sources as ksources

from scry_dosbox_x.knowledge.support import PINS

OK, RED, INVALID = verdict.EXIT_PASS, verdict.EXIT_FAIL, verdict.EXIT_INVALID
USAGE = 2

ROOT = Path(__file__).resolve().parent.parent
DICTIONARIES = ROOT / "src" / "scry_dosbox_x" / "knowledge"
INDEX = ROOT / "tests" / "fixtures" / "knowledge" / "sources.json"
#: Beside the index: what the list's licence asks to be kept with excerpts of it.
NOTICE_NAME = "rbil61-notice.txt"
NOTICE_SECTIONS = ("COPYRIGHT", "DISCLAIMER", "AVAILABILITY", "CREDITS", "CONTACT_INFO")

DOSBOX_X_PIN = PINS["dosbox-x"]
RBIL_PIN = PINS["rbil61"]
ARCHIVES = {
    "inter61a.zip": "8077536135c0290ff18a4a44cf63c56339f6127f053ee673f9895837248cc947",
    "inter61b.zip": "713e9e218eda694ed2bac8d5f02378f935f3e3132b79c92c44c14101e76b88a7",
    "inter61c.zip": "d7a059a1700c765adb9d4bf9dbe6289621aca6ff09c0583192764ee47e2b690a",
    "inter61d.zip": "0d0a04e84dd6a1db312157f3365fc7ee0b539af677944ace593df5236a563241",
}

_HANDLER_START = re.compile(r"^static Bitu DOS_21Handler\(void\) \{")
_LABEL = r"(0x[0-9a-fA-F]+|[0-9]+)"
#: A case of the handler's own switch sits at one indent step: eight spaces or one tab.
_TOP_CASE = re.compile(rf"^(?: {{8}}|\t)case {_LABEL}:")
_ANY_CASE = re.compile(rf"^\s*case\s+{_LABEL}:")
_AL_SWITCH = re.compile(r"switch\s*\(\s*reg_al\s*\)")
_DEFINE = re.compile(r"^#define (DOSERR_\w+) (\d+)\s*$")
#: A section header, with the register qualifier some carry: `D-214C`, `D-212E--DL00`,
#: `D-217160CL00`. The locator spells the id and the qualifier as the header does.
_RBIL_HEADER = re.compile(
    r"^--------([A-Za-z!-])-([0-9A-Fa-f]+?)(-*[A-Z]{2}[0-9A-Fa-f]+)?-+\s*$")
_TABLE = re.compile(r"^\(Table (\d+)\)\s*$")
_WINDOWS_ONLY = re.compile(r"(?<!!)defined\(WIN32\)")
_ROW_CODE = re.compile(r"^\s*[0-9A-Fa-f]{2}h \((\d+)\)")


class Invalid(Exception):
    """Something the tool could not establish: exit code 3, with the sentence to print."""


@dataclass(frozen=True)
class Sources:
    """The two sources, opened once: the list's files by name, and the git repository."""

    rbil: Mapping[str, list[str]]
    repo: Path | None

    def file(self, path: str) -> list[str]:
        if self.repo is None:
            raise Invalid("no DOSBox-X repository was given (--dosbox-x)")
        try:
            done = subprocess.run(["git", "-C", str(self.repo), "show", f"{DOSBOX_X_PIN}:{path}"],
                                  capture_output=True, check=False)
        except OSError as bad:
            raise Invalid(f"git could not run to read {path}: {bad.strerror}") from bad
        if done.returncode != 0:
            raise Invalid(f"{path} at {DOSBOX_X_PIN[:12]} could not be read from {self.repo.name}: "
                          f"{done.stderr.decode('utf-8', 'replace').strip()}")
        return [ln.rstrip() for ln in done.stdout.decode("utf-8", "replace").split("\n")]


def open_archives(folder: Path) -> dict[str, list[str]]:
    """Every file of the pinned archives, as lines with the line ends and the trailing space
    taken off. An archive that is not the pinned one is INVALID."""
    files: dict[str, list[str]] = {}
    for name, digest in ARCHIVES.items():
        path = folder / name
        try:
            blob = path.read_bytes()
        except OSError as bad:
            raise Invalid(f"{name} could not be read from {folder}: {bad.strerror}") from bad
        if hashlib.sha256(blob).hexdigest() != digest:
            raise Invalid(f"{name} is not the archive of {RBIL_PIN}: its SHA-256 differs")
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for member in zf.namelist():
                files[member.upper()] = [
                    ln.rstrip() for ln in zf.read(member).decode("latin-1").split("\n")]
    return files


def notice(index: Sources) -> str:
    """The list's title, its licence, where to get new releases, its credits and its author's
    addresses, as `INTERRUP.1ST` gives them: what the licence asks to be preserved."""
    lines = index.rbil.get("INTERRUP.1ST")
    if not lines:
        raise Invalid("the archives hold no INTERRUP.1ST")
    heads = [(i, ln[11:].strip("-")) for i, ln in enumerate(lines) if ln.startswith("--------!---")]
    out = [*lines[:2], ""]
    for n, (i, name) in enumerate(heads):
        if name in NOTICE_SECTIONS:
            end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
            out += [*lines[i:end], ""]
    if sum(ln.startswith("--------!---") for ln in out) != len(NOTICE_SECTIONS):
        raise Invalid(f"INTERRUP.1ST does not hold the sections {', '.join(NOTICE_SECTIONS)}")
    return "\n".join(out).rstrip("\n") + "\n"


def _rbil_key(ident: str) -> str:
    """`214C` is `0x21/0x4C`, `213302` is `0x21/0x33/0x02`: only INT 21h sections have a key."""
    if not ident.startswith("21") or len(ident) not in (4, 6):
        return ""
    return "/".join(f"0x{ident[i:i + 2].upper()}" for i in range(0, len(ident), 2))


def resolve_rbil(index: Sources, locator: str) -> ksources.Row:
    name, _, where = locator.partition(" ")
    lines = index.rbil.get(name)
    if lines is None:
        raise Invalid(f"rbil61:{locator}: the archives hold no file {name}")
    if where.startswith("#"):
        table, _, prefix = where[1:].partition(" ")
        return _table_row(locator, lines, table, prefix)
    category, _, ident = where.partition("-")
    ident, _, nth = ident.partition("@")
    found = [(i, m.group(2)) for i, ln in enumerate(lines)
             if (m := _RBIL_HEADER.match(ln)) and m.group(1) == category
             and m.group(2) + (m.group(3) or "") == ident]
    if nth:
        found = found[int(nth) - 1:int(nth)] if nth.isdigit() and int(nth) >= 1 else []
    if len(found) != 1:
        raise Invalid(f"rbil61:{locator}: {len(found)} sections have that header (one is needed; "
                      "`@2` picks the second of several)")
    return ksources.Row(lines[found[0][0] + 1], _rbil_key(found[0][1]))


def _table_row(locator: str, lines: list[str], table: str, prefix: str) -> ksources.Row:
    start = next((i for i, ln in enumerate(lines) if (m := _TABLE.match(ln))
                  and m.group(1) == table), None)
    if start is None or not prefix:
        raise Invalid(f"rbil61:{locator}: no (Table {table}) in the file, or no row text")
    rows: list[str] = []
    for ln in lines[start + 1:]:
        if ln.startswith("--------") or _TABLE.match(ln):
            break
        if ln.strip().startswith(prefix):
            rows.append(ln)
    if len(rows) != 1:
        raise Invalid(f"rbil61:{locator}: {len(rows)} rows of the table start with {prefix!r} "
                      "(one is needed; extend the text to tell them apart)")
    code = _ROW_CODE.match(rows[0])
    return ksources.Row(rows[0], code.group(1) if code else "")


def _handler(index: Sources) -> list[str]:
    lines = index.file("src/dos/dos.cpp")
    first = next((i for i, ln in enumerate(lines) if _HANDLER_START.match(ln)), None)
    if first is None:
        raise Invalid("src/dos/dos.cpp holds no DOS_21Handler")
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("}")), None)
    if last is None:
        raise Invalid("DOS_21Handler has no closing brace at column 0")
    return lines[first:last]


def _regions(body: list[str]) -> list[tuple[str, list[str]]]:
    """The handler's top-level cases, each with the lines up to the next one."""
    heads = [(i, m.group(1)) for i, ln in enumerate(body) if (m := _TOP_CASE.match(ln))]
    return [(label, body[i:heads[n + 1][0] if n + 1 < len(heads) else len(body)])
            for n, (i, label) in enumerate(heads)]


def _nested(region: list[str]) -> list[tuple[str, str]]:
    """The cases of the `switch (reg_al)` inside a top-level case, with their lines. Code under
    `#if defined(WIN32)` is the Windows build's alone (named pipes, in AH=5Fh) and is left out:
    what a call does must not depend on the host the list was captured on."""
    guards: list[bool] = []
    inside = False
    found: list[tuple[str, str]] = []
    for ln in region:
        word = ln.lstrip().split(None, 1)[0] if ln.strip() else ""
        if word in ("#if", "#ifdef", "#ifndef"):
            guards.append(_WINDOWS_ONLY.search(ln) is not None)
        elif word in ("#else", "#elif") and guards:
            guards[-1] = False
        elif word == "#endif" and guards:
            guards.pop()
        elif any(guards):
            continue
        elif _AL_SWITCH.search(ln):
            inside = True
        elif inside and (m := _ANY_CASE.match(ln)):
            found.append((m.group(1), ln))
    return found


def _value(label: str) -> int:
    """A case label's number: hex with `0x`, else decimal (`08` is 8, never an octal error)."""
    try:
        return int(label, 16 if label.lower().startswith("0x") else 10)
    except ValueError:
        raise Invalid(f"{label!r} is not a case label of hex or decimal digits") from None


def _case_key(labels: Sequence[str]) -> str:
    return "/".join(["0x21", *(f"0x{_value(x):02X}" for x in labels)])


def resolve_dosbox_x(index: Sources, locator: str) -> ksources.Row:
    path, _, tail = locator.partition(" ")
    if tail.startswith("DOSERR_"):
        define = tail.split()[0]
        hits = [m for ln in index.file(path) if (m := _DEFINE.match(ln)) and m.group(1) == define]
        if len(hits) != 1:
            raise Invalid(f"dosbox-x:{locator}: {len(hits)} defines of {define} (one is needed)")
        return ksources.Row(hits[0].group(0).rstrip(), str(int(hits[0].group(2))))
    symbol, *cases = tail.split(" case ")
    if symbol != "DOS_21Handler" or path != "src/dos/dos.cpp" or not 1 <= len(cases) <= 2:
        raise Invalid(f"dosbox-x:{locator}: the tool opens `DOS_21Handler case X [case Y]` and "
                      "the DOSERR_ defines")
    labels = [c.strip() for c in cases]
    wanted = _value(labels[0])
    tops = [(label, region) for label, region in _regions(_handler(index))
            if _value(label) == wanted]
    if len(tops) != 1:
        raise Invalid(f"dosbox-x:{locator}: {len(tops)} top-level cases of {labels[0]}")
    if len(labels) == 1:
        return ksources.Row(tops[0][1][0], _case_key(labels))
    inner = [ln for label, ln in _nested(tops[0][1]) if _value(label) == _value(labels[1])]
    if len(inner) != 1:
        raise Invalid(f"dosbox-x:{locator}: {len(inner)} cases of {labels[1]} inside "
                      f"case {labels[0]}")
    return ksources.Row(inner[0], _case_key(labels))


def list_dos_21(index: Sources) -> tuple[str, ...]:
    """Every function and subfunction the handler's own switches have a case for."""
    keys: list[str] = []
    for label, region in _regions(_handler(index)):
        keys.append(_case_key([label]))
        keys += [_case_key([label, inner]) for inner, _ in _nested(region)]
    return tuple(dict.fromkeys(keys))


def list_doserr(index: Sources) -> tuple[str, ...]:
    """Every distinct code `include/dos_inc.h` names with a `DOSERR_` define."""
    codes = [int(m.group(2)) for ln in index.file("include/dos_inc.h")
             if (m := _DEFINE.match(ln))]
    return tuple(str(c) for c in sorted(set(codes)))


LISTS: dict[str, Callable[[Sources], tuple[str, ...]]] = {
    "dosbox-x:src/dos/dos.cpp DOS_21Handler": list_dos_21,
    "dosbox-x:include/dos_inc.h DOSERR_*": list_doserr,
}
RESOLVERS: dict[str, Callable[[Sources, str], ksources.Row]] = {
    "rbil61": resolve_rbil, "dosbox-x": resolve_dosbox_x}


def _dictionaries(folder: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as bad:
            raise Invalid(f"{path.name} could not be read as a dictionary: {bad}") from bad
        docs.append(doc)
    if not docs:
        raise Invalid(f"{folder} holds no dictionary: there is nothing to capture rows for")
    return docs


def capture(index: Sources, folder: Path = DICTIONARIES) -> dict[str, Any]:
    """The index of what the dictionaries of `folder` cite and must cover."""
    rows: dict[str, dict[str, str]] = {}
    lists: dict[str, list[str]] = {}
    for doc in _dictionaries(folder):
        against = doc.get("complete_against", "")
        if against not in LISTS:
            raise Invalid(f"{doc.get('dictionary')}: complete_against {against!r} is a list this "
                          f"tool does not know ({', '.join(LISTS)})")
        lists[against] = list(LISTS[against](index))
        for entry in doc.get("entries", []):
            for src in entry.get("sources", []):
                if not isinstance(src, dict) or not isinstance(src.get("ref"), str):
                    raise Invalid(f"{doc.get('dictionary')}: a source of "
                                  f"{entry.get('key')!r} has no `ref` text")
                scheme, _, locator = src["ref"].partition(":")
                if scheme not in RESOLVERS:
                    raise Invalid(f"{src['ref']}: this tool opens {', '.join(RESOLVERS)}")
                row = RESOLVERS[scheme](index, locator)
                rows[src["ref"]] = {"line": row.line, **({"key": row.key} if row.key else {})}
    if not rows:
        raise Invalid("no entry cites a source: nothing was captured")
    return {"format": ksources.INDEX_FORMAT,
            "pins": dict(PINS),
            "rows": dict(sorted(rows.items())), "lists": dict(sorted(lists.items()))}


def render(doc: Mapping[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as bad:
        raise Invalid(f"{path} could not be read: {bad.strerror}") from bad


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge_sources.py", description="Capture or compare the source index of the "
        "dictionaries.", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False)
    parser.add_argument("--archives", type=Path, required=True,
                        help="folder holding inter61a.zip to inter61d.zip")
    parser.add_argument("--dosbox-x", type=Path, required=True, dest="repo",
                        help="a DOSBox-X repository that holds the pinned commit")
    parser.add_argument("--write", action="store_true",
                        help="write the index instead of comparing it")
    parser.add_argument("--index", type=Path, default=INDEX, help="the committed index")
    parser.add_argument("--dictionaries", type=Path, default=DICTIONARIES,
                        help="the folder of dictionaries")
    return parser


def main(argv: Sequence[str], write: Callable[[str], None] = print) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as bad:
        return USAGE if bad.code not in (0, None) else OK
    try:
        index = Sources(open_archives(args.archives), args.repo)
        made = render(capture(index, args.dictionaries))
        made_notice = notice(index)
        notice_path = args.index.with_name(NOTICE_NAME)
        if args.write:
            try:
                args.index.parent.mkdir(parents=True, exist_ok=True)
                args.index.write_text(made, encoding="utf-8")
                notice_path.write_text(made_notice, encoding="utf-8")
            except OSError as bad:
                raise Invalid(f"{args.index.parent} could not be written: {bad.strerror}") from bad
            write(f"wrote {args.index.name} ({made.count(chr(10))} lines) and {NOTICE_NAME}")
            return OK
        held, held_notice = _read(args.index), _read(notice_path)
    except Invalid as bad:
        write(f"INVALID: {bad}")
        return INVALID
    if held == made and held_notice == made_notice:
        write(f"the index equals the sources: {len(json.loads(made)['rows'])} rows")
        return OK
    if held_notice != made_notice:
        write(f"{NOTICE_NAME}: the sources say something else than the committed notice")
    try:
        now, then = json.loads(made), json.loads(held)
    except json.JSONDecodeError as bad:
        write(f"INVALID: {args.index} is not JSON: {bad}")
        return INVALID
    if not isinstance(then, dict):
        write(f"INVALID: {args.index} is not a JSON object")
        return INVALID
    told = 0
    for section in ("rows", "lists", "pins"):
        for key in sorted(set(now[section]) | set(then.get(section, {}))):
            if now[section].get(key) != then.get(section, {}).get(key):
                told += 1
                write(f"{section.rstrip('s')} {key!r}: the sources say {now[section].get(key)!r}, "
                      f"the index holds {then.get(section, {}).get(key)!r}")
    if not told and held != made:
        write(f"{args.index.name} holds what the sources say, written another way: write it "
              "again with --write")
    return RED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
