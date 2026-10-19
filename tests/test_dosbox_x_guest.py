"""THE LIVE TIER'S FIXTURE: its guest binary, and the interlock that keeps it
from running by accident. Neither had a case on the commit path.

The guest binary is the assembly of the guest source, and nothing said so.

`tests/guest/probe.com` is 144 VERSIONED BYTES and `tests/guest/probe.asm` is presented
everywhere -- in the README, in `probe.conf`, in both live modules -- as its source and
its record. Nothing compared them. Edit the `.asm` and the live tier goes on running the
old binary, silently, for as long as nobody notices; every behavioural claim in that
file (the rate, the milestone, the odometer) would then be a claim about a file it does
not describe.

TWO TIERS, AND THE SECOND IS THE ONE THAT NEEDS A TOOL. The first derives its
expectations FROM the source and needs nothing installed, so it runs on every commit on
any machine. The second reassembles and compares byte for byte, and can only run where
`nasm` is. Splitting them is what stops the whole check quietly becoming a skip on a
machine without the assembler -- a gate that skips is not a gate, and a gate whose only
case skips is worse than none because its name still appears in the report.

MEASURED when this was written: `nasm -f bin probe.asm` reproduces the committed 144
bytes exactly, so the pair was correct and merely ungated.

The DPMI guest (`dpmi.c`, built with DJGPP) has the same two tiers: what the tier reads off it is
checked against the committed binary and table everywhere, and the rebuild, where DJGPP is.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

GUEST = Path(__file__).resolve().parent / "guest"
LIVE = Path(__file__).resolve().parent / "live"
ASM = GUEST / "probe.asm"
COM = GUEST / "probe.com"
#: Every NASM guest this package owns, with the size its binary has: the probe the live tier runs,
#: the screen guest whose stops are the screen tools' known answers, and the code guest whose
#: frames and bytes are the code tools'.
GUESTS = {"probe": 144, "screen": 212, "code": 195, "mouse": 331}


def _declared_strings(asm: Path = ASM) -> list[bytes]:
    """The `db "..."` literals of the source, DERIVED rather than restated here.

    Writing them out in this file would make it a second copy of the guest's protocol,
    which is the thing that goes stale: the test would then agree with itself while
    both drifted from the binary. Read from the source, a changed literal shows up as a
    changed expectation and the comparison against the `.com` is what decides.
    """
    return [s.encode("ascii")
            for line in re.findall(r"\bdb\s+(.*)", asm.read_text(encoding="ascii"))
            for s in re.findall(r'"([^"]*)"', line)]


@pytest.mark.parametrize("name", GUESTS)
def test_the_committed_guest_carries_what_its_source_declares(name: str) -> None:
    """The tier that needs no assembler, so it runs everywhere the contract tier does.

    It cannot prove the `.com` IS the assembly of the `.asm` -- only reassembly does
    that, below -- but it catches the case that will actually happen: a protocol string
    edited in the source and the binary left behind. The live tier greps these exact
    bytes out of the log.
    """
    blob = (GUEST / f"{name}.com").read_bytes()
    strings = _declared_strings(GUEST / f"{name}.asm")
    assert strings, f"no `db \"...\"` literal found in {name}.asm: this check read nothing"
    for s in strings:
        assert s in blob, (
            f"{name}.asm declares {s!r} and {name}.com does not contain it: the binary is "
            f"not the assembly of the source beside it")


@pytest.mark.parametrize(("name", "size"), GUESTS.items())
def test_the_guests_size_is_the_one_every_document_states(name: str, size: int) -> None:
    """144, and it is asserted because it was stated as 34 in three separate files.

    A size is the cheapest possible description of a binary and it was wrong in three
    of the four places that gave one. Pinning it here means the next document to quote
    a number has something to be wrong against.
    """
    com = GUEST / f"{name}.com"
    assert com.stat().st_size == size, com.stat().st_size


def test_the_late_milestone_the_source_declares_is_the_one_it_tests_for() -> None:
    """The odometer comparison and the string it announces have to agree.

    They did not: the comment beside that comparison said `01000` and `tick 50` while
    the two `cmp` immediates read `00` and `05` and the emitted line says `00005`. The
    comment is prose and this is the pair that has to hold -- both DERIVED from the
    source, so neither can be restated wrongly here.
    """
    text = ASM.read_text(encoding="ascii")
    digits = re.findall(r"cmp\s+word\s+\[cnt\+\d\],\s*'(\d\d)'", text)
    assert len(digits) == 2, digits
    tested = "".join(digits)                       # the last four digits it fires on
    late = next(s for s in _declared_strings() if b"late" in s).decode("ascii")
    announced = re.search(r"\[\+ (\d+)\.", late)
    assert announced is not None, late
    assert announced.group(1).endswith(tested), (
        f"the guest tests for a counter ending {tested} and announces "
        f"{announced.group(1)}: the milestone and the line naming it disagree")


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the binary cannot be reassembled")
@pytest.mark.parametrize("name", GUESTS)
def test_the_guest_binary_is_exactly_what_its_source_assembles_to(tmp_path: Path,
                                                                    name: str) -> None:
    """The whole claim, where the tool exists to settle it.

    This is the only case that proves the pair; the ones above narrow the gap for
    machines without an assembler. It is deliberately NOT the only case, because
    `skipif` on the sole check of a property means the property is unchecked on any
    machine that lacks the tool and the report says `skipped`, which reads as fine.
    """
    asm, com = GUEST / f"{name}.asm", GUEST / f"{name}.com"
    out = tmp_path / "reassembled.com"
    r = subprocess.run(["nasm", "-f", "bin", str(asm), "-o", str(out)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"{name}.asm does not assemble: {r.stderr}"
    assert out.read_bytes() == com.read_bytes(), (
        f"{name}.com ({com.stat().st_size} bytes) is not the assembly of {name}.asm "
        f"({out.stat().st_size} bytes). Reassemble it: "
        f"nasm -f bin tests/guest/{name}.asm -o tests/guest/{name}.com")


#: A global label in a `nasm -l` listing: line number, offset, bytes, then a name with no
#: leading dot, and what follows it: a data directive or an instruction.
_GLOBAL_LABEL = re.compile(r"^\s*\d+ ([0-9A-F]{8}) \S+\s+([A-Za-z_]\w*):\s*(\w+)")
_DATA = ("db", "dw", "dd")


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the listing cannot be produced")
@pytest.mark.parametrize("name", ["probe", "code"])
def test_the_guest_symbols_are_its_global_labels(tmp_path: Path, name: str) -> None:
    """`probe.sym` and `code.sym`, the `nm` text the name layer reads, are each guest's own
    listing: one row per global label at the origin plus its offset, `T` for code and `D` for
    data, as `nm` prints a program. The data rows are what close the table above the last
    routine, so its body is inside the span a symbol is placed in."""
    listing = tmp_path / f"{name}.lst"
    r = subprocess.run(["nasm", "-f", "bin", "-l", str(listing), str(GUEST / f"{name}.asm"),
                        "-o", str(tmp_path / f"{name}.com")],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    origin = 0x100
    rows = [f"{origin + int(m.group(1), 16):08x} {'D' if m.group(3) in _DATA else 'T'} "
            f"{m.group(2)}"
            for line in listing.read_text(encoding="latin-1").splitlines()
            if (m := _GLOBAL_LABEL.match(line))]
    assert len(rows) >= 3, f"the listing gave {rows}: the label pattern matched almost nothing"
    assert (GUEST / f"{name}.sym").read_text(encoding="ascii").splitlines() == rows


def _dpmi_guest() -> Any:
    """`tests/live/dpmi_guest.py`, the guest's marks and names as the live tier reads them."""
    # ITS SIBLINGS ARE ITS IMPORTS (`live_private`), as the live tier runs it from `tests/live`:
    # put there, not left to whichever file of a whole run put that directory on the path first.
    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))
    spec = importlib.util.spec_from_file_location("dpmi_guest", LIVE / "dpmi_guest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_dpmi_guest_carries_the_marks_and_names_the_live_tier_reads() -> None:
    """The tier that needs no DJGPP: every literal mark the live tier waits for is in the
    committed binary, and every name it stops at or watches is in the committed table, as
    code or as data. A mark renamed in `dpmi.c` and not in `dpmi_guest.py` is red here rather
    than a live wait that times out."""
    guest = _dpmi_guest()
    exe = guest.EXE.read_bytes()
    for mark in (guest.BOOT_MARK, guest.KEY_MARK, guest.MOUSE_MARK, guest.ASK_MARK,
                 "key down %s%s", "F11", "TICK  . ticks=%lu", "ask res=%d", "[+%04lu.%03lu] "):
        assert mark.encode() in exe, mark
    # the marks the tier matches as patterns, against the lines those formats print
    for pattern, line in ((guest.SETTLED_MARK, "TICK  . ticks=60"),
                          (guest.ARRIVAL_MARK, "key down F11"), (guest.ANSWER_MARK, "ask res=1"),
                          (guest.E9_STAMP, "[+0001.234] BOOT  . start")):
        assert re.search(pattern, line), pattern
    kinds = {row.split()[2]: row.split()[1] for row in guest.SYM.read_text().splitlines()
             if len(row.split()) == 3}
    assert {kinds.get(name) for name in (guest.STOP, guest.LOADED_ONCE, "_main")} == {"T"}
    assert {kinds.get(name) for name in guest.WATCHES} == {"B"}


DJGPP_BIN = Path(os.environ.get("DJDIR") or Path.home() / "djgpp") / "bin"
DJGPP_GCC = DJGPP_BIN / "i586-pc-msdosdjgpp-gcc"
#: The build `dpmi.c`'s header names.
DPMI_CFLAGS = ["-O1", "-fno-omit-frame-pointer", "-Wall", "-Wextra", "-Wshadow", "-Werror"]


@pytest.mark.skipif(not DJGPP_GCC.is_file(),
                    reason="no DJGPP cross compiler under $DJDIR (default ~/djgpp), so the guest "
                           "cannot be rebuilt")
def test_the_dpmi_guest_is_exactly_what_its_source_builds_to(tmp_path: Path) -> None:
    """The DJGPP build is reproducible: the same source gives the same bytes, so the committed
    binary is compared byte for byte, and its table is `nm`'s own text for it."""
    guest = _dpmi_guest()
    out = tmp_path / "dpmi.exe"
    r = subprocess.run([str(DJGPP_GCC), *DPMI_CFLAGS, "-o", str(out), str(GUEST / "dpmi.c")],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"dpmi.c does not build: {r.stderr}"
    assert out.read_bytes() == guest.EXE.read_bytes(), (
        "dpmi.exe is not the build of dpmi.c: rebuild it with the command in dpmi.c's header")
    nm = subprocess.run([str(DJGPP_BIN / "i586-pc-msdosdjgpp-nm"), str(guest.EXE)],
                        capture_output=True, text=True, check=False)
    assert nm.returncode == 0, nm.stderr
    assert nm.stdout == guest.SYM.read_text(), "dpmi.sym is not `nm dpmi.exe`"


def test_the_live_interlock_is_declared_in_the_package() -> None:
    """The live tier is opt-in in the PACKAGE: a stranger clones it and runs `pytest`, and
    without the marker and its `-m 'not live'` default that clone collects the whole live
    tier, one emulator per case. A guard that rests on live modules skipping without
    `DOSBOX_X_LIVE_CONF` is an accident that disappears the day the tier gets a guest of its
    own, so the property is declared here and held."""
    here = Path(__file__).resolve().parent.parent
    mine = tomllib.loads((here / "pyproject.toml").read_text(encoding="utf-8"))
    section = mine.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "-m 'not live'" in section.get("addopts", ""), (
        "this package does not deselect the live tier by itself, so a clone runs an emulator "
        "per case")
    assert any(m.startswith("live:") for m in section.get("markers", [])), section
