"""The DOS programs the live tier runs from the bench: their copies, pinned by
`scry_core.live_bench` in the bench's own `bench.json`, one directory per program under the
bench's root (`DOSBOX_X_LIVE_BENCH`), each in its project's own layout; and `missing`, which says
why one cannot run. Shared by the matrix and the pytest live files; importing it reads the
bench's `identity.json` once and runs nothing.

A PROGRAM IS NAMED HERE BY ITS LABEL, never by its own name: what the case covers (`dos-real16`,
real mode with a Borland map) is what this tree says, and whatever names the program lives in
the bench's `identity.json`, beside the manifest, and nowhere tracked.

A program's session conf is DERIVED from its project's own run conf at run time, into a scratch
directory, so the bench pins what the project wrote and no file naming a path of this machine.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scry_core import live_bench as bench

BENCH = bench.root("dosbox-x")
#: The manifest of every file the live tier reads from the bench.
BENCH_MANIFEST = BENCH / "bench.json"
#: What each label stands for on this machine: `{label: {key: value}}`, every value a string.
IDENTITY = BENCH / "identity.json"
#: The labels, and the keys each one's identity carries: `dir`, its directory under the bench;
#: `exe` and `map`, its build inside it; `launch`, the line its run conf starts it with;
#: `process`, the name DOS gives its memory block; `e9_line`, the line it logs on the E9 port at
#: start.
LABELS = ("dos-real16", "dos-real16-alt")
IDENTITY_KEYS = ("dir", "exe", "map", "launch", "process", "e9_line")
PATH_KEYS = ("exe", "map")
#: The serial stub's directory, mounted and run by every derived conf: the guest half of the
#: serial route.
STUB_DIR = Path(__file__).resolve().parents[2] / "guest"
_reasons: dict[str, str] = {}


def _known(label: str, key: str = "dir") -> None:
    """A label or key the code does not declare is the code's mistake, on every host alike."""
    if label not in LABELS or key not in IDENTITY_KEYS:
        raise KeyError(f"no identity key {label}.{key}: declare it in LABELS and IDENTITY_KEYS")


def _identity() -> tuple[dict[str, dict[str, str]], str]:
    """Every label's values, and why the file cannot be read (empty when it can)."""
    remedy = (f"write {IDENTITY} beside bench.json: one object per label ({', '.join(LABELS)}), "
              f"each with {', '.join(IDENTITY_KEYS)} as strings")
    try:
        doc = json.loads(IDENTITY.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"identity ABSENT: {remedy}"
    except (OSError, ValueError) as e:
        return {}, f"identity UNREADABLE ({e}): {remedy}"
    if not isinstance(doc, dict) or not all(isinstance(v, dict) for v in doc.values()):
        return {}, f"identity NOT AN OBJECT OF OBJECTS: {remedy}"
    return doc, ""


_DOC, _DOC_WHY = _identity()


def identity_missing(label: str) -> str:
    """Why `label`'s identity cannot be used, or empty when it carries every key as a string."""
    _known(label)
    if _DOC_WHY:
        return _DOC_WHY
    held = _DOC.get(label)
    if held is None:
        return (f"identity names no {label!r}: add it to {IDENTITY} with "
                f"{', '.join(IDENTITY_KEYS)}")
    for key in IDENTITY_KEYS:
        if not isinstance(held.get(key), str) or not held[key]:
            return (f"identity {label}.{key} is {held.get(key)!r}, not a non-empty string: "
                    f"set it in {IDENTITY}")
    if Path(held["dir"]).name != held["dir"] or held["dir"] in (".", ".."):
        return (f"identity {label}.dir is {held['dir']!r}, not one directory name: set it in "
                f"{IDENTITY}")
    # DOS spells a memory block's name in capitals, at most eight, and the E9 line is matched
    # as Latin-1 bytes in the build
    if held["process"] != held["process"].upper() or len(held["process"]) > 8:
        return (f"identity {label}.process is {held['process']!r}, not a DOS name of at most "
                f"eight capitals: set it in {IDENTITY}")
    try:
        held["e9_line"].encode("latin-1")
    except UnicodeEncodeError:
        return f"identity {label}.e9_line is not Latin-1: set it in {IDENTITY}"
    return ""


def value(label: str, key: str) -> str:
    """`label`'s `key`, or empty when its identity cannot be used, which `missing` reports: a
    value read here is used only on a program that is not BLOCKED."""
    _known(label, key)
    return "" if identity_missing(label) else str(_DOC[label][key])


@dataclass(frozen=True)
class Program:
    """A program on the bench: its label, its project's run conf and the conf whose fixed
    `cycles` a session takes when the run conf plays at another clock (empty: the run conf's own
    clock is the session's). The rest is its identity's; `launch` is what a session's
    `program=` types instead."""
    label: str
    run_conf: str
    clock_conf: str = ""

    @property
    def root(self) -> Path:
        return BENCH / (value(self.label, "dir") or self.label)

    @property
    def exe(self) -> str:
        return value(self.label, "exe")

    @property
    def map(self) -> str:
        return value(self.label, "map")

    @property
    def launch(self) -> str:
        return value(self.label, "launch")

    @property
    def process(self) -> str:
        return value(self.label, "process")

    @property
    def e9_line(self) -> str:
        return value(self.label, "e9_line")


# real mode, built by TASM, a Borland map with publics
SPEEDF = Program("dos-real16", "SCRIPTS/dosbox-run.conf")
# real mode, a map with a segment table and no publics. Its run conf plays at `cycles = max`, and
# its project's own session conf takes the fixed clock its goldens are judged at instead: a
# session asks questions whose answer is the guest's clock.
LINEUP = Program("dos-real16-alt", "SCRIPTS/dosbox-x-run.conf",
                 clock_conf="SCRIPTS/dosbox-x-gold.conf")


def opened(program: Program) -> list[str]:
    """Every file the live code opens for `program`, relative to the bench: its build and its
    map, its run conf and, where it has one, its clock conf."""
    files = [value(program.label, k) for k in PATH_KEYS]
    files += [f for f in (program.run_conf, program.clock_conf) if f]
    return [f"{value(program.label, 'dir')}/{f}" for f in files]


def _unpinned(program: Program) -> str:
    """The first file `program` opens that the manifest does not pin, as a reason, or empty: a
    file opened unpinned would be read unchecked."""
    try:
        pinned = {e.path for e in bench.load(BENCH_MANIFEST)}
    except bench.Invalid as e:
        return f"bench {e}"
    off = next((p for p in opened(program) if p not in pinned), None)
    return "" if off is None else (
        f"program {program.label} opens {off}, which {BENCH_MANIFEST} does not pin: pin it "
        "there, or name a file it pins")


def manifest_absent() -> str:
    """Why there is no manifest to judge the copies by, or empty: it is not tracked, so `fill`
    cannot make it, and the remedy is to put the bench's own back."""
    if BENCH_MANIFEST.is_file():
        return ""
    return (f"bench manifest ABSENT: {BENCH_MANIFEST} pins every copy and is kept only in the "
            "bench; restore it there, then `python -m scry_core.live_bench check`")


def missing(program: Program) -> str:
    """Why `program` cannot run here, or empty: its identity, then its copies (naming the first
    absent or wrong one), then whether every file it opens is one the manifest pins."""
    if program.label not in _reasons:
        _reasons[program.label] = (
            identity_missing(program.label) or manifest_absent()
            or bench.missing("dosbox-x", BENCH_MANIFEST, f"{value(program.label, 'dir')}/")
            or _unpinned(program))
    return _reasons[program.label]


def session_conf(program: Program, into: Path) -> Path:
    """`program`'s run conf made a session's, written to `into`: the serial stub mounted and run
    just before its first `set PATH` (which drops Z:, where MOUNT lives, so a stub after it
    never runs), its launch line and its `exit` removed, so `start(program=...)` runs it, and,
    where the program names one, its `cycles` line taken from its clock conf. The launch line,
    the `exit` and the `cycles` line must each match exactly once, and a `set PATH` at least
    once, or this refuses: an edit that matched nothing would run the project's conf unchanged
    under the session's name."""
    text = (program.root / program.run_conf).read_text(encoding="utf-8")
    stub = f'mount g "{STUB_DIR}"\nG:\\INJECT.COM\n'
    # Functions, never template strings: `re` reads a backslash in a replacement as an escape,
    # and a DOS path carries one.
    # (pattern, replacement, how many to replace: every one, or the first `set PATH` only)
    edits: list[tuple[str, Callable[[re.Match[str]], str], int]] = [
        (rf"(?im)^{re.escape(program.launch)}\s*$", lambda _m: "", 0),
        (r"(?im)^exit\s*$", lambda _m: "", 0),
        (r"(?im)^set\s+path=.*$", lambda m: stub + m.group(0), 1),
    ]
    if program.clock_conf:
        clock = _fixed_clock(program)
        edits.append((r"(?im)^cycles\s*=.*$", lambda _m: clock, 0))
    for pattern, replacement, count in edits:
        text, n = re.subn(pattern, replacement, text, count=count)
        if n != 1:
            raise RuntimeError(f"{program.run_conf} of {program.label} has {n} lines matching "
                               f"{pattern!r} where one was expected, so the session conf cannot "
                               "be derived from it")
    into.mkdir(parents=True, exist_ok=True)
    out = into / f"{program.label}-session.conf"
    out.write_text(text, encoding="utf-8")
    return out


def _fixed_clock(program: Program) -> str:
    """The one `cycles` line of `program`'s clock conf, refused unless it is a fixed clock."""
    lines = re.findall(r"(?im)^cycles\s*=.*$",
                       (program.root / program.clock_conf).read_text(encoding="utf-8"))
    if len(lines) != 1 or "fixed" not in lines[0]:
        raise RuntimeError(f"{program.clock_conf} of {program.label} has {lines} where one fixed "
                           "`cycles` line was expected")
    return str(lines[0])


#: A Borland map's public: `SSSS:OOOOO`, the linker's `idle` mark when it has one, the name.
_PUBLIC = re.compile(r"^\s*([0-9A-F]{4}):([0-9A-F]{5})\s+(idle)?\s*(\S+)\s*$")


def public(program: Program, name: str) -> tuple[int, int, bool]:
    """The frame and offset `program`'s map gives the public `name`, and whether it carries the
    linker's mark."""
    for line in (program.root / program.map).read_text(encoding="latin-1").splitlines():
        if (m := _PUBLIC.match(line)) and m.group(4) == name:
            return int(m.group(1), 16), int(m.group(2), 16), m.group(3) is not None
    raise RuntimeError(f"{program.map} names no public {name}")
