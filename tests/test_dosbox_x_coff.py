"""A text table checked against the executable it was made for: the DPMI guest's own `dpmi.exe`
and `dpmi.sym` are the known answer, a copy whose code symbols moved by a relink is the stale
table, and an image with no COFF table or none at all is a check that could not be made."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scry_dosbox_x import coff
from scry_dosbox_x import session as ds
from scry_dosbox_x import symbols as sym

GUEST = Path(__file__).resolve().parent / "guest"


def _parsed(table: Path) -> list[sym.Symbol]:
    return sym.parse(table.read_text(encoding="utf-8"))[0]


def test_the_guests_table_agrees_with_its_executable() -> None:
    got = coff.check(GUEST / "dpmi.sym", _parsed(GUEST / "dpmi.sym"))
    assert got["against"].endswith("dpmi.exe") and got["agree"] > 100, got


def test_is_coff_tells_a_djgpp_image_from_a_real_mode_exe(tmp_path: Path) -> None:
    assert coff.is_coff(GUEST / "dpmi.exe") is True
    real = tmp_path / "real.exe"
    real.write_bytes(b"MZ" + bytes(510))
    assert coff.is_coff(real) is False
    assert coff.is_coff(tmp_path / "missing.exe") is False


def test_a_stripped_coff_image_is_still_coff(tmp_path: Path) -> None:
    whole = bytearray((GUEST / "dpmi.exe").read_bytes())
    start = coff._coff_start(bytes(whole))
    whole[start + 8:start + 12] = bytes(4)            # the symbol table's offset, zeroed
    stripped = tmp_path / "dpmi.exe"
    stripped.write_bytes(bytes(whole))
    assert coff.is_coff(stripped) is True


def test_a_table_of_a_relinked_build_is_refused_naming_what_differs(tmp_path: Path) -> None:
    shutil.copy(GUEST / "dpmi.exe", tmp_path / "dpmi.exe")
    rows = []
    for line in (GUEST / "dpmi.sym").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in "Tt":
            parts[0] = f"{int(parts[0], 16) + 0xD0:08x}"
        rows.append(" ".join(parts))
    stale = tmp_path / "dpmi.sym"
    stale.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ds.Invalid) as e:
        coff.check(stale, _parsed(stale))
    assert e.value.code == "bad_argument" and "disagree" in str(e.value), str(e.value)
    assert "in dpmi.exe" in str(e.value) and "more" in str(e.value), str(e.value)


def test_no_executable_or_none_with_a_coff_table_is_said_not_judged(tmp_path: Path) -> None:
    table = tmp_path / "prog.sym"
    shutil.copy(GUEST / "dpmi.sym", table)
    alone = coff.check(table, _parsed(table))
    assert alone["available"] is False and "no executable" in alone["why"], alone
    (tmp_path / "PROG.EXE").write_bytes(b"MZ" + bytes(510))
    real = coff.check(table, _parsed(table))
    assert real["available"] is False and "no COFF symbol table" in real["why"], real


@pytest.mark.parametrize(("cut", "said"), [
    (2, "the MZ header is cut"), (40, "shorter than its MZ header says"), (0.6, "is cut")],
    ids=["mz-only", "header-only", "in-strings"])
def test_a_cut_image_is_said_never_a_traceback(tmp_path: Path, cut: float, said: str) -> None:
    whole = (GUEST / "dpmi.exe").read_bytes()
    size = int(len(whole) * cut) if isinstance(cut, float) else cut
    (tmp_path / "dpmi.exe").write_bytes(whole[:size])
    shutil.copy(GUEST / "dpmi.sym", tmp_path / "dpmi.sym")
    got = coff.check(tmp_path / "dpmi.sym", _parsed(tmp_path / "dpmi.sym"))
    assert got["available"] is False and said in got["why"] and "real-mode" not in got["why"], got


def test_a_table_with_no_symbol_kinds_is_said_as_such(tmp_path: Path) -> None:
    shutil.copy(GUEST / "dpmi.exe", tmp_path / "dpmi.exe")
    table = tmp_path / "dpmi.sym"
    shutil.copy(GUEST / "dpmi.sym", table)
    kindless = [sym.Symbol(s.name, s.offset) for s in _parsed(table)]
    got = coff.check(table, kindless)
    assert got["available"] is False and "no symbol kinds" in got["why"], got


def test_a_stripped_image_is_said_stripped_never_real_mode(tmp_path: Path) -> None:
    """A go32 image whose COFF header holds no symbol table (`strip` ran) is a protected-mode
    program with nothing to compare, not a real-mode one."""
    whole = bytearray((GUEST / "dpmi.exe").read_bytes())
    start = coff._coff_start(bytes(whole))
    whole[start + 8:start + 12] = bytes(4)            # the symbol table's offset, zeroed
    (tmp_path / "dpmi.exe").write_bytes(bytes(whole))
    shutil.copy(GUEST / "dpmi.sym", tmp_path / "dpmi.sym")
    got = coff.check(tmp_path / "dpmi.sym", _parsed(tmp_path / "dpmi.sym"))
    assert got["available"] is False and "stripped" in got["why"], got
    assert "real-mode" not in got["why"], got
