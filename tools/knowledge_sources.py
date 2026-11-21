"""The source index of the dictionaries: what the real sources say at every place an entry cites,
and the lists each dictionary must cover, captured from the sources and committed, so the ordinary
tests judge an entry with no network.

Two sources are read. Ralf Brown's interrupt list, release 61, from its four archives
(`inter61a.zip` to `inter61d.zip`, each held to its SHA-256). DOSBox-X, from a repository that
holds the pinned commit: files are read with `git show <pin>:<path>`, so the checkout's own
branch and working tree do not matter. A dictionary's `ref` names one place; this tool opens it.
For DOSBox-X the index keeps the line it finds there. For the list it keeps the SHA-256 of the
line and not the line: the entry's own `cites` holds the text, and the test that judges the index
hashes it.

Locators:
    rbil61:INTERRUP.G D-214C              the title line under the section header `D-214C`
    rbil61:INTERRUP.G D-2158@2            the second section with that header, when several have it
    rbil61:INTERRUP.G #01680 05h (5)      the row of table 01680 that starts with that text
    dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c
    dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x65 case 0x01     (a case inside that case)
    dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x57 if 0x00       (chosen by `if (reg_al == 0)`)
    dosbox-x:src/dos/dos_ioctl.cpp DOS_IOCTL case 0x00             (AH=44h's own switch)
    dosbox-x:include/dos_inc.h DOSERR_FILE_NOT_FOUND

EXIT CODES:
    0  the committed index equals what the sources say (or `--write` wrote it)
    1  they differ: the honest red
    2  bad usage
    3  INVALID: nothing was read, or something could not be (an archive that is not the pinned
       one, a pin the repository lacks, a ref that resolves to no line or to two)

Every run that reads the dictionaries and reaches the comparison or the write prints the total of
list lines they hold.
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

DOSBOX_X_PIN = PINS["dosbox-x"]
RBIL_PIN = PINS["rbil61"]
ARCHIVES = {
    "inter61a.zip": "8077536135c0290ff18a4a44cf63c56339f6127f053ee673f9895837248cc947",
    "inter61b.zip": "713e9e218eda694ed2bac8d5f02378f935f3e3132b79c92c44c14101e76b88a7",
    "inter61c.zip": "d7a059a1700c765adb9d4bf9dbe6289621aca6ff09c0583192764ee47e2b690a",
    "inter61d.zip": "0d0a04e84dd6a1db312157f3365fc7ee0b539af677944ace593df5236a563241",
}

_LABEL = r"(0x[0-9a-fA-F]+|[0-9]+|[A-Za-z_]\w*)"
_CASES = re.compile(rf"^(\s*)((?:case\s+{_LABEL}\s*:\s*)+)")
_ONE_CASE = re.compile(rf"case\s+{_LABEL}\s*:")
_IF_AL = re.compile(rf"\b(?:else\s+)?if\s*\(\s*(?:!\s*reg_al\b|reg_al\s*==\s*{_LABEL})")
_AL_SWITCH = re.compile(r"switch\s*\(\s*reg_al\s*\)")
_DEFINE = re.compile(r"^#define (DOSERR_\w+) (\d+)\s*$")
_NAMED = re.compile(r"^\s*#\s*define\s+(\w+)\s+(0x[0-9a-fA-F]+|[0-9]+)[uUlL]*\b")
#: A section header, with the register qualifier some carry: `D-214C`, `D-212E--DL00`,
#: `D-217160CL00`. The locator spells the id and the qualifier as the header does.
_RBIL_HEADER = re.compile(
    r"^--------([A-Za-z!-])-([0-9A-Fa-f]{2}(?:[0-9A-Fa-f]{2}){0,2})(-*[A-Z]{2}[0-9A-Fa-f]+)?-+\s*$")
_TABLE = re.compile(r"^\(Table (\d+)\)\s*$")
#: A condition that names the Windows build positively: its first branch is that build's alone.
_WINDOWS_ONLY = re.compile(r"(?<![!\w])(?<!! )(?:defined\s*\(\s*_?WIN32\s*\)|ifdef\s+_?WIN32\b)")
_DEAD_IF = re.compile(r"^\s*#\s*if\s+0\b")
_DIRECTIVE = re.compile(r"^\s*#\s*(\w+)")
_ROW_CODE = re.compile(r"^\s*[0-9A-Fa-f]{2}h \((\d+)\)")


class Invalid(Exception):
    """Something the tool could not establish: exit code 3, with the sentence to print."""


@dataclass(frozen=True)
class Handler:
    """One function of the emulator that answers calls: where it is, the register its first
    `switch` reads, and how a call number becomes a dictionary key."""

    path: str
    func: str
    interrupt: int
    #: `reg_ah` (the key is `INT/AH`, and `/AL` for a nested `switch (reg_al)`), `reg_ax` (the key
    #: is `INT/AH/AL` of the 16-bit label) or `reg_al` (a function that sees only the subfunction).
    selector: str = "reg_ah"
    #: Key bytes that come before the label: the function AH=44h's IOCTL code is the AL of.
    prefix: tuple[int, ...] = ()
    #: Top-level cases whose AL is chosen by `if (reg_al == N)` and not by a `switch`.
    if_cases: frozenset[int] = frozenset()
    #: Files besides `path` whose `#define NAME value` lines name the case labels.
    defines: tuple[str, ...] = ()


HANDLERS: tuple[Handler, ...] = (Handler("src/dos/dos.cpp", "DOS_21Handler", 0x21),)
#: A list a dictionary names in `complete_against`: the handlers whose keys it holds.
LIST_HANDLERS: dict[str, tuple[str, ...]] = {
    "dosbox-x:src/dos/dos.cpp DOS_21Handler": ("DOS_21Handler",),
}
#: DOSBox-X has no DPMI host (the guest's extender is one), so the sections of the list that
#: describe the DPMI calls are the list a dictionary of them covers.
DPMI_LIST = "rbil61:INTERRUP.N INT 31 DPMI sections"
_DPMI_TITLE = re.compile(r"^INT 31 P? ?- DPMI")


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


def digest(line: str) -> str:
    """What the index keeps of a list line."""
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _rbil_key(ident: str, qualified: bool = False) -> str:
    """`214C` is `0x21/0x4C`, `213302` is `0x21/0x33/0x02`, the mouse's `3303` is AX=0003 and so
    `0x33/0x00/0x03`. A section a register qualifies (`1012--BL10`) is a subcase of its number for
    INT 21h only: elsewhere the qualified section is no call of its own and has no key."""
    if len(ident) not in (4, 6) or not re.fullmatch(r"[0-9A-Fa-f]+", ident):
        return ""
    parts = [f"0x{ident[i:i + 2].upper()}" for i in range(0, len(ident), 2)]
    if parts[0] != "0x21" and qualified:
        return ""
    if parts[0] == "0x33" and len(parts) == 2:
        parts.insert(1, "0x00")
    return "/".join(parts)


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
    found = [(i, m.group(2), bool(m.group(3))) for i, ln in enumerate(lines)
             if (m := _RBIL_HEADER.match(ln)) and m.group(1) == category
             and m.group(2) + (m.group(3) or "") == ident]
    if nth:
        found = found[int(nth) - 1:int(nth)] if nth.isdigit() and int(nth) >= 1 else []
    if len(found) != 1:
        raise Invalid(f"rbil61:{locator}: {len(found)} sections have that header (one is needed; "
                      "`@2` picks the second of several)")
    return ksources.Row(lines[found[0][0] + 1], _rbil_key(found[0][1], found[0][2]))


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


def _value(label: str) -> int:
    """A case label's number: hex with `0x`, else decimal (`08` is 8, never an octal error)."""
    try:
        return int(label, 16 if label.lower().startswith("0x") else 10)
    except ValueError:
        raise Invalid(f"{label!r} is not a case label of hex or decimal digits") from None


def _handler(wanted: str, path: str | None = None) -> Handler:
    found = [h for h in HANDLERS if h.func == wanted and path in (None, h.path)]
    if len(found) != 1:
        raise Invalid(f"the tool opens {', '.join(h.func for h in HANDLERS)}; not {wanted!r}")
    return found[0]


def _body(index: Sources, handler: Handler) -> list[str]:
    lines = index.file(handler.path)
    name = re.escape(handler.func)
    start = re.compile(rf"^[A-Za-z_][\w \t*&:<>,]*\b{name}\s*\([^;]*\)\s*\{{\s*$")
    first = next((i for i, ln in enumerate(lines) if start.match(ln)), None)
    if first is None:
        raise Invalid(f"{handler.path} holds no {handler.func}")
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("}")), None)
    if last is None:
        raise Invalid(f"{handler.func} has no closing brace at column 0")
    return lines[first:last]


def _off(directive: str) -> bool:
    """Whether the first branch of this `#if` is code no host runs: the Windows build's alone, or
    `#if 0`."""
    return _WINDOWS_ONLY.search(directive) is not None or _DEAD_IF.match(directive) is not None


def _guarded(lines: Sequence[str]) -> list[tuple[str, bool]]:
    """Each line with whether it is in code the first branch of a `#if` holds that the list must
    leave out (`#if defined(WIN32)`, `#if 0`): what a call does must not depend on the host the
    list was captured on."""
    guards: list[bool] = []
    out: list[tuple[str, bool]] = []
    for ln in lines:
        found = _DIRECTIVE.match(ln)
        word = found.group(1) if found else ""
        if word in ("if", "ifdef", "ifndef"):
            guards.append(_off(ln))
        elif word in ("else", "elif") and guards:
            guards[-1] = False
        elif word == "endif" and guards:
            guards.pop()
        out.append((ln, any(guards)))
    return out


def _indent(line: str) -> int:
    return len(line.expandtabs(8)) - len(line.expandtabs(8).lstrip())


def _named(index: Sources, handler: Handler) -> dict[str, str]:
    """The `#define NAME value` lines of the handler's file and of its `defines` files."""
    found: dict[str, str] = {}
    for path in (handler.path, *handler.defines):
        for ln in index.file(path):
            if m := _NAMED.match(ln):
                found[m.group(1)] = m.group(2)
    return found


def _braces(line: str, comment: bool) -> tuple[int, int, bool]:
    """The `{` and `}` of one line that are code (not in a comment, a string or a character
    literal), and whether a block comment is still open at its end."""
    opens = closes = 0
    i, quote = 0, ""
    while i < len(line):
        two, ch = line[i:i + 2], line[i]
        if comment:
            if two == "*/":
                comment, i = False, i + 1
        elif quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif two == "//":
            break
        elif two == "/*":
            comment, i = True, i + 1
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            opens += 1
        elif ch == "}":
            closes += 1
        i += 1
    return opens, closes, comment


def _block(lines: Sequence[tuple[str, bool]],
           first: int) -> tuple[int, dict[int, int], set[int]]:
    """The index of the line that closes the block `lines[first]` opens, the brace depth at the
    start of each line up to it, and the lines that start inside a block comment. Braces are
    counted outside comments and literals; of the branches of a `#if` only one is counted: the
    first, or the next when the first is the Windows build's alone or `#if 0`. A block that never
    closes runs to the end."""
    depth, opened, comment = 0, False, False
    #: Per open `#if`: whether its branch now is left out, and whether one was counted already.
    skipping: list[tuple[bool, bool]] = []
    at: dict[int, int] = {}
    commented: set[int] = set()
    for i in range(first, len(lines)):
        at[i] = depth
        if comment:
            commented.add(i)
        text = lines[i][0].strip()
        if text.startswith("#") and not comment:
            found = _DIRECTIVE.match(text)
            word = found.group(1) if found else ""
            if word in ("if", "ifdef", "ifndef"):
                off = _off(text)
                skipping.append((off, not off))
            elif word in ("else", "elif") and skipping:
                skipping[-1] = (skipping[-1][1], True)
            elif word == "endif" and skipping:
                skipping.pop()
            continue
        if lines[i][1] or any(off for off, _ in skipping):
            continue
        opens, closes, comment = _braces(lines[i][0], comment)
        depth += opens
        opened = opened or opens > 0
        depth -= closes
        if opened and depth <= 0:
            return i, at, commented
    return len(lines) - 1, at, commented


def _span(lines: Sequence[tuple[str, bool]], switch: re.Pattern[str],
          names: Mapping[str, str]) -> list[tuple[int, str, str]]:
    """The cases of the outermost `switch` matching `switch` in `lines`, each with its index and
    its line: the cases directly inside its braces (so a `switch` inside a case is not read),
    several labels of one line apart. A label that is a name is the number its `#define` gives,
    and a name with none is INVALID, as is a line that starts with `case` and that the tool cannot
    read, and two switches of the register at the same indent (the tool reads one)."""
    starts = [i for i, (ln, windows) in enumerate(lines)
              if not windows and switch.match(ln.lstrip())]
    if not starts:
        return []
    shallowest = min(_indent(lines[i][0]) for i in starts)
    firsts = [i for i in starts if _indent(lines[i][0]) == shallowest]
    if len(firsts) > 1:
        raise Invalid(f"{len(firsts)} switches of the same register stand at the same indent "
                      f"(the first at line {firsts[0] + 1} of the function): the tool reads one")
    first = firsts[0]
    last, at, commented = _block(lines, first)
    found: list[tuple[int, str, str]] = []
    for i in range(first + 1, last):
        ln, windows = lines[i]
        if windows or at[i] != 1 or i in commented:
            continue
        head = _CASES.match(ln)
        if head is None:
            if re.match(r"case\s", ln.lstrip()):
                raise Invalid(f"a case line the tool cannot read: {ln.strip()!r}")
            continue
        for m in _ONE_CASE.finditer(head.group(2)):
            label = m.group(1)
            if not label[0].isdigit():
                if label not in names:
                    raise Invalid(f"the case label {label!r} is no number and no `#define` of "
                                  "the handler's files")
                label = names[label]
            found.append((i, label, ln))
    return found


def _regions(index: Sources, handler: Handler,
             body: list[str]) -> list[tuple[str, list[str]]]:
    """The top-level cases of the handler's own switch, each with the lines up to the next one."""
    own = re.compile(rf"switch\s*\(\s*{handler.selector}\s*\)")
    heads = _span(_guarded(body), own, _named(index, handler))
    ends = sorted({i for i, _, _ in heads})
    out: list[tuple[str, list[str]]] = []
    for i, label, _ in heads:
        later = [e for e in ends if e > i]
        out.append((label, body[i:later[0] if later else len(body)]))
    return out


def _nested(handler: Handler, top: str, region: list[str],
            names: Mapping[str, str]) -> list[tuple[str, str, str]]:
    """The AL values a top-level case tells apart, each with its line and how it is told (`case`
    or `if`): the cases of its `switch (reg_al)`, and for the handler's `if_cases` the
    `if (reg_al == N)` tests."""
    found = [(label, ln, "case")
             for _, label, ln in _span(_guarded(region), _AL_SWITCH, names)]
    if _value(top) in handler.if_cases:
        for ln, windows in _guarded(region):
            if windows or not (m := _IF_AL.search(ln)):
                continue
            found.append((m.group(1) if m.group(1) is not None else "0", ln, "if"))
    return found


def _key(handler: Handler, *labels: str) -> str:
    values = [_value(x) for x in labels]
    if handler.selector == "reg_ax":
        if len(values) != 1 or values[0] > 0xFFFF:
            raise Invalid(f"{handler.func}: a 16-bit case label is one value up to 0xFFFF")
        parts = [handler.interrupt, values[0] >> 8, values[0] & 0xFF]
    else:
        parts = [handler.interrupt, *handler.prefix, *values]
    return "/".join(f"0x{p:02X}" for p in parts)


def handler_keys(index: Sources, handler: Handler) -> list[str]:
    """Every function and subfunction the handler's own switches and tests tell apart."""
    keys: list[str] = []
    names = _named(index, handler)
    for label, region in _regions(index, handler, _body(index, handler)):
        keys.append(_key(handler, label))
        if handler.selector == "reg_ah":
            keys += [_key(handler, label, inner)
                     for inner, _, _ in _nested(handler, label, region, names)]
    return list(dict.fromkeys(keys))


def resolve_dosbox_x(index: Sources, locator: str) -> ksources.Row:
    path, _, tail = locator.partition(" ")
    if tail.startswith("DOSERR_"):
        define = tail.split()[0]
        hits = [m for ln in index.file(path) if (m := _DEFINE.match(ln)) and m.group(1) == define]
        if len(hits) != 1:
            raise Invalid(f"dosbox-x:{locator}: {len(hits)} defines of {define} (one is needed)")
        return ksources.Row(hits[0].group(0).rstrip(), str(int(hits[0].group(2))))
    func, _, rest = tail.partition(" ")
    asked = re.fullmatch(r"case (\S+)(?: (case|if) (\S+))?", rest)
    handler = next((h for h in HANDLERS if h.func == func and h.path == path), None)
    if handler is None or asked is None:
        raise Invalid(f"dosbox-x:{locator}: the tool opens "
                      f"`<file> <handler> case X [case Y | if Y]` of "
                      f"{', '.join(h.func for h in HANDLERS)}, and the DOSERR_ defines")
    top, how, inner = asked.groups()
    tops = [(label, region) for label, region in _regions(index, handler, _body(index, handler))
            if _value(label) == _value(top)]
    if len(tops) != 1:
        raise Invalid(f"dosbox-x:{locator}: {len(tops)} top-level cases of {top}")
    if inner is None:
        return ksources.Row(tops[0][1][0], _key(handler, top))
    if handler.selector != "reg_ah":
        raise Invalid(f"dosbox-x:{locator}: {handler.func} has no nested cases")
    names = _named(index, handler)
    lines = [ln for label, ln, told in _nested(handler, tops[0][0], tops[0][1], names)
             if _value(label) == _value(inner) and told == how]
    if len(lines) != 1:
        kind = "cases" if how == "case" else "tests"
        raise Invalid(f"dosbox-x:{locator}: {len(lines)} {kind} of {inner} inside case {top}")
    return ksources.Row(lines[0], _key(handler, top, inner))


def list_keys(index: Sources, name: str) -> tuple[str, ...]:
    keys = [k for fn in LIST_HANDLERS[name] for k in handler_keys(index, _handler(fn))]
    return tuple(dict.fromkeys(keys))


def list_dos_21(index: Sources) -> tuple[str, ...]:
    return list_keys(index, next(iter(LIST_HANDLERS)))


def list_doserr(index: Sources) -> tuple[str, ...]:
    """Every distinct code `include/dos_inc.h` names with a `DOSERR_` define."""
    codes = [int(m.group(2)) for ln in index.file("include/dos_inc.h")
             if (m := _DEFINE.match(ln))]
    return tuple(str(c) for c in sorted(set(codes)))


def list_dpmi(index: Sources) -> tuple[str, ...]:
    """Every INT 31h section of the list whose title says DPMI, as the key its header gives."""
    lines = index.rbil.get("INTERRUP.N")
    if lines is None:
        raise Invalid("the archives hold no INTERRUP.N")
    keys = [_rbil_key(m.group(2)) for i, ln in enumerate(lines[:-1])
            if (m := _RBIL_HEADER.match(ln)) and m.group(1) == "E" and not m.group(3)
            and _DPMI_TITLE.match(lines[i + 1])]
    return tuple(dict.fromkeys(k for k in keys if k))


def _lister(name: str) -> Callable[[Sources], tuple[str, ...]]:
    return lambda index: list_keys(index, name)


def lists() -> dict[str, Callable[[Sources], tuple[str, ...]]]:
    named = {name: _lister(name) for name in LIST_HANDLERS}
    named["dosbox-x:include/dos_inc.h DOSERR_*"] = list_doserr
    named[DPMI_LIST] = list_dpmi
    return named


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


def list_lines_held(docs: Sequence[Mapping[str, Any]]) -> int:
    """How many lines of Ralf Brown's list the dictionaries hold: the distinct places of the list
    their entries cite, each one line. It is reported and never judged."""
    cited = (src["ref"] for doc in docs for entry in doc.get("entries", [])
             for src in entry.get("sources", []))
    return len({ref for ref in cited if str(ref).startswith("rbil61:")})


def capture(index: Sources, folder: Path = DICTIONARIES) -> dict[str, Any]:
    """The index of what the dictionaries of `folder` cite and must cover."""
    rows: dict[str, dict[str, str]] = {}
    covered: dict[str, list[str]] = {}
    known = lists()
    docs = _dictionaries(folder)
    for doc in docs:
        against = doc.get("complete_against", "")
        if against not in known:
            raise Invalid(f"{doc.get('dictionary')}: complete_against {against!r} is a list this "
                          f"tool does not know ({', '.join(known)})")
        covered[against] = list(known[against](index))
        for entry in doc.get("entries", []):
            for src in entry.get("sources", []):
                if not isinstance(src, dict) or not isinstance(src.get("ref"), str):
                    raise Invalid(f"{doc.get('dictionary')}: a source of "
                                  f"{entry.get('key')!r} has no `ref` text")
                scheme, _, locator = src["ref"].partition(":")
                if scheme not in RESOLVERS:
                    raise Invalid(f"{src['ref']}: this tool opens {', '.join(RESOLVERS)}")
                row = RESOLVERS[scheme](index, locator)
                shown = {"digest": digest(row.line)} if scheme == "rbil61" else {"line": row.line}
                rows[src["ref"]] = {**shown, **({"key": row.key} if row.key else {})}
    if not rows:
        raise Invalid("no entry cites a source: nothing was captured")
    return {"format": ksources.INDEX_FORMAT,
            "pins": dict(PINS),
            "rows": dict(sorted(rows.items())), "lists": dict(sorted(covered.items()))}


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
        held_lines = list_lines_held(_dictionaries(args.dictionaries))
        if args.write:
            try:
                args.index.parent.mkdir(parents=True, exist_ok=True)
                args.index.write_text(made, encoding="utf-8")
            except OSError as bad:
                raise Invalid(f"{args.index.parent} could not be written: {bad.strerror}") from bad
            write(f"wrote {args.index.name} ({made.count(chr(10))} lines); "
                  f"list lines held: {held_lines}")
            return OK
        held = _read(args.index)
    except Invalid as bad:
        write(f"INVALID: {bad}")
        return INVALID
    if held == made:
        write(f"the index equals the sources: {len(json.loads(made)['rows'])} rows; "
              f"list lines held: {held_lines}")
        return OK
    try:
        now, then = json.loads(made), json.loads(held)
    except json.JSONDecodeError as bad:
        write(f"INVALID: {args.index} is not JSON: {bad}")
        return INVALID
    if not isinstance(then, dict):
        write(f"INVALID: {args.index} is not a JSON object")
        return INVALID
    write(f"list lines held: {held_lines}")
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
