"""The committed guest binaries match their sources, and the live tier stays opt-in.

The first tier derives its expectations from the source and runs everywhere; the rebuild tier
needs `nasm` (or DJGPP), so a missing tool never turns the whole check into a skip.
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

from scry_dosbox_x import inputs, launch

GUEST = Path(__file__).resolve().parent / "guest"
LIVE = Path(__file__).resolve().parent / "live"
ASM = GUEST / "probe.asm"
COM = GUEST / "probe.com"
GUESTS = {"probe": 144, "screen": 212, "code": 195, "mouse": 465, "v86": 1328, "hook1c": 76,
          "planes": 812, "sound": 221, "tap": 78, "stack": 1088}


def _declared_strings(asm: Path = ASM) -> list[bytes]:
    """The `db "..."` literals of the source."""
    return [s.encode("ascii")
            for line in re.findall(r"\bdb\s+(.*)", asm.read_text(encoding="ascii"))
            for s in re.findall(r'"([^"]*)"', line)]


@pytest.mark.parametrize("name", GUESTS)
def test_the_committed_guest_carries_what_its_source_declares(name: str) -> None:
    """Every protocol string the source declares is in the committed binary."""
    blob = (GUEST / f"{name}.com").read_bytes()
    strings = _declared_strings(GUEST / f"{name}.asm")
    assert strings, f"no `db \"...\"` literal found in {name}.asm: this check read nothing"
    for s in strings:
        assert s in blob, (
            f"{name}.asm declares {s!r} and {name}.com does not contain it: the binary is "
            f"not the assembly of the source beside it")


@pytest.mark.parametrize(("name", "size"), GUESTS.items())
def test_the_guests_size_is_the_one_every_document_states(name: str, size: int) -> None:
    """The binary has the size it had when its source was last assembled here."""
    com = GUEST / f"{name}.com"
    assert com.stat().st_size == size, com.stat().st_size


def test_the_late_milestone_the_source_declares_is_the_one_it_tests_for() -> None:
    """The odometer comparison and the line announcing it agree."""
    text = ASM.read_text(encoding="ascii")
    digits = re.findall(r"cmp\s+word\s+\[cnt\+\d\],\s*'(\d\d)'", text)
    assert len(digits) == 2, digits
    tested = "".join(digits)
    late = next(s for s in _declared_strings() if b"late" in s).decode("ascii")
    announced = re.search(r"\[\+ (\d+)\.", late)
    assert announced is not None, late
    assert announced.group(1).endswith(tested), (
        f"the guest tests for a counter ending {tested} and announces "
        f"{announced.group(1)}: the milestone and the line naming it disagree")


def _nasm_major() -> int:
    said = subprocess.run(["nasm", "-v"], capture_output=True, text=True, check=False).stdout
    found = re.search(r"version (\d+)\.", said)
    return int(found.group(1)) if found else 0


#: The committed binaries are nasm 3's: nasm 2 emits the operand- and address-size prefixes
#: (0x66, 0x67) of one instruction in the other order, a valid encoding with other bytes.
NASM_MAJOR = 3


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the binary cannot be reassembled")
@pytest.mark.skipif(shutil.which("nasm") is not None and _nasm_major() < NASM_MAJOR,
                    reason=f"the binaries are nasm {NASM_MAJOR}'s, and nasm 2 orders prefixes "
                           "differently")
@pytest.mark.parametrize("name", GUESTS)
def test_the_guest_binary_is_exactly_what_its_source_assembles_to(tmp_path: Path,
                                                                    name: str) -> None:
    """Reassembling the source gives the committed binary byte for byte."""
    asm, com = GUEST / f"{name}.asm", GUEST / f"{name}.com"
    out = tmp_path / "reassembled.com"
    r = subprocess.run(["nasm", "-f", "bin", str(asm), "-o", str(out)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"{name}.asm does not assemble: {r.stderr}"
    assert out.read_bytes() == com.read_bytes(), (
        f"{name}.com ({com.stat().st_size} bytes) is not the assembly of {name}.asm "
        f"({out.stat().st_size} bytes). Reassemble it: "
        f"nasm -f bin tests/guest/{name}.asm -o tests/guest/{name}.com")


DEMOS = GUEST.parent.parent / "demos"


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the binary cannot be reassembled")
@pytest.mark.skipif(shutil.which("nasm") is not None and _nasm_major() < NASM_MAJOR,
                    reason=f"the binaries are nasm {NASM_MAJOR}'s, and nasm 2 orders prefixes "
                           "differently")
@pytest.mark.parametrize("demo,name", [("bricks", "bricks"), ("mines", "mines")])
def test_a_demos_program_is_exactly_what_its_source_assembles_to(tmp_path: Path, demo: str,
                                                                 name: str) -> None:
    """The demos' own programs are committed binaries too: the README's transcript is their run."""
    asm, com = DEMOS / demo / f"{name}.asm", DEMOS / demo / f"{name.upper()}.COM"
    out = tmp_path / "reassembled.com"
    r = subprocess.run(["nasm", "-f", "bin", str(asm), "-o", str(out)], cwd=tmp_path,
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"{asm.name} does not assemble: {r.stderr}"
    assert out.read_bytes() == com.read_bytes(), (
        f"{com.name} is not the assembly of {asm.name}. Reassemble it: "
        f"nasm -f bin demos/{demo}/{asm.name} -o demos/{demo}/{com.name}")


def test_the_resident_check_reads_a_one_digit_protocol_number() -> None:
    """`resident` compares `SIG_LEN - 1` bytes at the distance its own signature has, so a
    stub whose signature is a byte longer is not recognised as a copy of itself: revisit the
    check (a fixed-width number, or the prefix found by scanning) before the protocol has two
    digits."""
    assert len(inputs.STUB_PROTOCOL) == 1, inputs.STUB_PROTOCOL


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the stub cannot be reassembled")
@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the stub cannot be reassembled to compare")
def test_the_packaged_stub_is_exactly_what_its_source_assembles_to(tmp_path: Path) -> None:
    """The stub ships to every guest, so a binary behind its source runs an older protocol."""
    stub = launch.GUEST_DIR
    out = tmp_path / "SCRY.COM"
    r = subprocess.run(["nasm", "-f", "bin", str(stub / "scry.asm"), "-o", str(out)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"scry.asm does not assemble: {r.stderr}"
    assert out.read_bytes() == (stub / "SCRY.COM").read_bytes(), (
        "SCRY.COM is not the assembly of scry.asm. Reassemble it: "
        "nasm -f bin src/scry_dosbox_x/guest/scry.asm -o src/scry_dosbox_x/guest/SCRY.COM")
    assert out.stat().st_size < 2048, (
        "the stub stays resident in the guest's conventional memory, so it is kept tiny")


#: A global label in a `nasm -l` listing: offset, bytes, undotted name, then what follows it.
_GLOBAL_LABEL = re.compile(r"^\s*\d+ ([0-9A-F]{8}) \S+\s+([A-Za-z_]\w*):\s*(\w+)")
_DATA = ("db", "dw", "dd")


@pytest.mark.skipif(shutil.which("nasm") is None,
                    reason="no `nasm` on PATH, so the listing cannot be produced")
@pytest.mark.parametrize("name", ["probe", "code"])
def test_the_guest_symbols_are_its_global_labels(tmp_path: Path, name: str) -> None:
    """The `.sym` table is one row per global label: `T` for code, `D` for data."""
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
    """`tests/live/dpmi_guest.py`, loaded as the live tier does."""
    # its sibling imports (`live_private`) need tests/live on the path whatever ran first
    if str(LIVE) not in sys.path:
        sys.path.insert(0, str(LIVE))
    spec = importlib.util.spec_from_file_location("dpmi_guest", LIVE / "dpmi_guest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_dpmi_guest_carries_the_marks_and_names_the_live_tier_reads() -> None:
    """Every mark and name the live tier reads is in the committed binary and table."""
    guest = _dpmi_guest()
    exe = guest.EXE.read_bytes()
    for mark in (guest.BOOT_MARK, guest.KEY_MARK, guest.MOUSE_MARK, guest.ASK_MARK,
                 "key down %s%s", "F11", "TICK  . ticks=%lu", "ask res=%d", "[+%04lu.%03lu] "):
        assert mark.encode() in exe, mark
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
DPMI_CFLAGS = ["-O1", "-fno-omit-frame-pointer", "-Wall", "-Wextra", "-Wshadow", "-Werror"]


@pytest.mark.skipif(not DJGPP_GCC.is_file(),
                    reason="no DJGPP cross compiler under $DJDIR (default ~/djgpp), so the guest "
                           "cannot be rebuilt")
def test_the_dpmi_guest_is_exactly_what_its_source_builds_to(tmp_path: Path) -> None:
    """Rebuilding `dpmi.c` gives the committed binary and `nm` gives its table."""
    guest = _dpmi_guest()
    out = tmp_path / "dpmi.exe"
    r = subprocess.run([str(DJGPP_GCC), *DPMI_CFLAGS, "-o", str(out), str(GUEST / "dpmi.c")],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"dpmi.c does not build: {r.stderr}"
    s = subprocess.run([str(DJGPP_BIN / "i586-pc-msdosdjgpp-strip"), "--strip-debug", str(out)],
                       capture_output=True, text=True, check=False)
    assert s.returncode == 0, f"the strip failed: {s.stderr}"
    assert out.read_bytes() == guest.EXE.read_bytes(), (
        "dpmi.exe is not the build of dpmi.c: rebuild it with the command in dpmi.c's header")
    nm = subprocess.run([str(DJGPP_BIN / "i586-pc-msdosdjgpp-nm"), str(guest.EXE)],
                        capture_output=True, text=True, check=False)
    assert nm.returncode == 0, nm.stderr
    assert nm.stdout == guest.SYM.read_text(), "dpmi.sym is not `nm dpmi.exe`"


def test_the_live_interlock_is_declared_in_the_package() -> None:
    """The package deselects the live tier itself."""
    here = Path(__file__).resolve().parent.parent
    mine = tomllib.loads((here / "pyproject.toml").read_text(encoding="utf-8"))
    section = mine.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "not live" in section.get("addopts", ""), (
        "this package does not deselect the live tier by itself, so a clone runs an emulator "
        "per case")
    assert any(m.startswith("live:") for m in section.get("markers", [])), section


#: The tap guest's places the tap tests name, each with the instruction the listing puts there.
TAP_PLACES = {0x11D: bytes.fromhex("FE063801"), 0x126: bytes.fromhex("A33C01"),
              0x129: bytes.fromhex("A03E01"), 0x138: bytes.fromhex("00A55AC3")}


def test_the_tap_guests_places_are_where_its_tests_say() -> None:
    """`w_inc`, `w_pair`, `r_poll` and `count` at the offsets the tap tests and fixtures name."""
    blob = (GUEST / "tap.com").read_bytes()
    moved = {f"{at:04X}": blob[at - 0x100:at - 0x100 + len(want)].hex()
             for at, want in TAP_PLACES.items() if blob[at - 0x100:].startswith(want) is False}
    assert not moved, f"tap.com moved its places: {moved}; the tests and fixtures name the old ones"

