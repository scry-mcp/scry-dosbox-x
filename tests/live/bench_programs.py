"""The DOS programs the live tier runs from the bench; their real names live only in the
bench's untracked `identity.json`."""
from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scry_core import live_bench as bench
from scry_core import verdict

BENCH_VAR = "DOSBOX_X_LIVE_BENCH"
UNSET = f"{BENCH_VAR} is not set: name the bench directory with it"


def _root() -> Path | None:
    held = os.environ.get(BENCH_VAR, "")
    return Path(held).expanduser().absolute() if held else None


ROOT = _root()
#: Unset: a path named after the variable, which no file is at.
BENCH = bench.Bench(ROOT or Path(BENCH_VAR))
IDENTITY = BENCH.root / "identity.json"
LABELS = ("dos-real16", "dos-real16-alt")
IDENTITY_KEYS = ("dir", "exe", "map", "launch", "process", "e9_line")
PATH_KEYS = ("exe", "map")
STUB_DIR = Path(__file__).resolve().parents[2] / "src" / "scry_dosbox_x" / "guest"


def _known(label: str, key: str = "dir") -> None:
    """Refuse an undeclared label or key."""
    if label not in LABELS or key not in IDENTITY_KEYS:
        raise KeyError(f"no identity key {label}.{key}: declare it in LABELS and IDENTITY_KEYS")


def _identity() -> tuple[dict[str, dict[str, str]], str]:
    """Every label's values, and why the file cannot be read."""
    if ROOT is None:
        return {}, UNSET
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
    """Why `label`'s identity cannot be used, or empty."""
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
    # the build matches the E9 line as Latin-1
    if held["process"] != held["process"].upper() or len(held["process"]) > 8:
        return (f"identity {label}.process is {held['process']!r}, not a DOS name of at most "
                f"eight capitals: set it in {IDENTITY}")
    try:
        held["e9_line"].encode("latin-1")
    except UnicodeEncodeError:
        return f"identity {label}.e9_line is not Latin-1: set it in {IDENTITY}"
    return ""


def value(label: str, key: str) -> str:
    """`label`'s `key`, or empty when its identity is unusable."""
    _known(label, key)
    return "" if identity_missing(label) else str(_DOC[label][key])


@dataclass(frozen=True)
class Program:
    """A program on the bench; a non-empty `clock_conf` supplies the session's fixed `cycles`."""
    label: str
    run_conf: str
    clock_conf: str = ""

    @property
    def root(self) -> Path:
        return BENCH.root / (value(self.label, "dir") or self.label)

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


DOS_REAL16 = Program("dos-real16", "SCRIPTS/dosbox-run.conf")
# its run conf plays at `cycles = max`, but a session's answers depend on the guest clock
DOS_REAL16_ALT = Program("dos-real16-alt", "SCRIPTS/dosbox-x-run.conf",
                 clock_conf="SCRIPTS/dosbox-x-gold.conf")


def opened(program: Program) -> list[str]:
    """Every file opened for `program`, relative to the bench."""
    files = [value(program.label, k) for k in PATH_KEYS]
    files += [f for f in (program.run_conf, program.clock_conf) if f]
    return [f"{value(program.label, 'dir')}/{f}" for f in files]


def _unpinned(program: Program) -> str:
    """Why an opened file is unpinned, or empty."""
    try:
        pinned = BENCH.pinned
    except verdict.Invalid as e:
        return f"bench {e}"
    off = next((p for p in opened(program) if p not in pinned), None)
    return "" if off is None else (
        f"program {program.label} opens {off}, which {BENCH.manifest} does not pin: pin it "
        "there, or name a file it pins")


def missing(program: Program) -> str:
    """Why `program` cannot run here, or empty."""
    return (identity_missing(program.label)
            or BENCH.missing(f"{value(program.label, 'dir')}/") or _unpinned(program))


def session_conf(program: Program, into: Path) -> Path:
    """`program`'s run conf made a session's, written to `into`; raises unless each edit matches.

    The stub goes before the first `set PATH`, which drops Z: (where MOUNT lives)."""
    text = (program.root / program.run_conf).read_text(encoding="utf-8")
    stub = f'mount g "{STUB_DIR}"\nG:\\SCRY.COM\n'
    # functions, not strings: `re` reads a backslash in a replacement as an escape
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
    """The clock conf's one fixed `cycles` line."""
    lines = re.findall(r"(?im)^cycles\s*=.*$",
                       (program.root / program.clock_conf).read_text(encoding="utf-8"))
    if len(lines) != 1 or "fixed" not in lines[0]:
        raise RuntimeError(f"{program.clock_conf} of {program.label} has {lines} where one fixed "
                           "`cycles` line was expected")
    return str(lines[0])


_PUBLIC = re.compile(r"^\s*([0-9A-F]{4}):([0-9A-F]{5})\s+(idle)?\s*(\S+)\s*$")


def public(program: Program, name: str) -> tuple[int, int, bool]:
    """The frame, offset and `idle` mark `program`'s map gives the public `name`."""
    for line in (program.root / program.map).read_text(encoding="latin-1").splitlines():
        if (m := _PUBLIC.match(line)) and m.group(4) == name:
            return int(m.group(1), 16), int(m.group(2), 16), m.group(3) is not None
    raise RuntimeError(f"{program.map} names no public {name}")
