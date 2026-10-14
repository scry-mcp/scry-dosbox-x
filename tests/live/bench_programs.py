"""The DOS programs the live tier runs from the bench: their copies, pinned by
`scry_core.live_bench` in `bench.json` beside this file, one directory per program under the
bench's root (`DOSBOX_X_LIVE_BENCH`), each in its project's own layout; and `missing`, which says
why one cannot run. Shared by the matrix and the pytest live files; runs nothing at import.

A program's session conf is DERIVED from its project's own run conf at run time, into a scratch
directory, so the bench pins what the project wrote and no file naming a path of this machine.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scry_core import live_bench as bench

#: The tracked manifest of every file the live tier reads from the bench.
BENCH_MANIFEST = Path(__file__).resolve().parent / "bench.json"
BENCH = bench.root("dosbox-x")
#: The serial stub's directory, mounted and run by every derived conf: the guest half of the
#: serial route.
STUB_DIR = Path(__file__).resolve().parents[2] / "guest"
_reasons: dict[str, str] = {}


@dataclass(frozen=True)
class Program:
    """A program on the bench: its directory's name, its project's run conf, its build, the line
    that conf launches it with, which a session's `program=` types instead, and the conf whose
    fixed `cycles` a session takes when the run conf plays at another clock (empty: the run
    conf's own clock is the session's)."""
    name: str
    run_conf: str
    exe: str
    map: str
    launch: str
    clock_conf: str = ""

    @property
    def root(self) -> Path:
        return BENCH / self.name


SPEEDF = Program("speedf", "SCRIPTS/dosbox-run.conf", "EXES/SPEEDF.EXE", "EXES/SPEEDF.MAP",
                 "..\\exes\\speedf.exe")
# Line UP's run conf plays at `cycles = max`, and its project's own session conf takes the fixed
# clock its goldens are judged at instead: a session asks questions whose answer is the guest's
# clock.
LINEUP = Program("lineup", "SCRIPTS/dosbox-x-run.conf", "EXES/LINEUP.EXE", "EXES/LINEUP.MAP",
                 "EXES\\LINEUP.EXE", clock_conf="SCRIPTS/dosbox-x-gold.conf")


def missing(program: Program) -> str:
    """Why `program`'s copies cannot be used, naming the first absent or wrong one, or empty."""
    if program.name not in _reasons:
        _reasons[program.name] = bench.missing("dosbox-x", BENCH_MANIFEST, f"{program.name}/")
    return _reasons[program.name]


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
            raise RuntimeError(f"{program.run_conf} of {program.name} has {n} lines matching "
                               f"{pattern!r} where one was expected, so the session conf cannot "
                               "be derived from it")
    into.mkdir(parents=True, exist_ok=True)
    out = into / f"{program.name}-session.conf"
    out.write_text(text, encoding="utf-8")
    return out


def _fixed_clock(program: Program) -> str:
    """The one `cycles` line of `program`'s clock conf, refused unless it is a fixed clock."""
    lines = re.findall(r"(?im)^cycles\s*=.*$",
                       (program.root / program.clock_conf).read_text(encoding="utf-8"))
    if len(lines) != 1 or "fixed" not in lines[0]:
        raise RuntimeError(f"{program.clock_conf} of {program.name} has {lines} where one fixed "
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
