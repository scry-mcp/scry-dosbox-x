"""`symbols_load` by what it leaves for the next tool and what its reply says: the program's
selectors kept only when the table is the program's, carried into a batch added where it sits,
the account of a load deferred while the guest runs, a sectioned table's descriptor and what
`symbols_find` says of a section it lacks, the types a later batch may name, the refusals that
name the argument at fault, and a read of a name the table holds twice."""

from __future__ import annotations

import shutil
import struct
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import NamesFake, _names, clean_session  # noqa: F401

from scry_dosbox_x import placement, server
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def _map(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _ok(got: Any) -> dict[str, Any]:
    reply = cast(dict[str, Any], got)
    assert reply["status"] == "ok", reply
    return reply


def _selectors() -> dict[str, int]:
    return {k: v for k, v in dstate.STATE.base.items() if k.startswith("selector_")}


GUEST = Path(__file__).resolve().parent / "guest"


def test_a_load_stamps_the_executable_it_checked_the_table_against(tmp_path: Path) -> None:
    """A relink under a live session is not refused by the load: what catches it is the session
    remembering which file its table was compared with."""
    shutil.copy(GUEST / "dpmi.exe", tmp_path / "dpmi.exe")
    shutil.copy(GUEST / "dpmi.sym", tmp_path / "dpmi.sym")
    fake = _names(tmp_path)
    got = _ok(server.symbols_load(path=str(tmp_path / "dpmi.sym"), base="400000"))
    assert str(got["checked"].get("against", "")).endswith("dpmi.exe"), got["checked"]
    exe = tmp_path / "dpmi.exe"
    assert fake.image == {"path": str(exe), "size": exe.stat().st_size,
                          "mtime_ns": exe.stat().st_mtime_ns}, getattr(fake, "image", None)
    # a load its own build cannot be checked against clears it: nothing waits on that file
    _ok(server.symbols_load(path=_map(tmp_path, "plain.nm", "00001000 T _main\n"), base="400000"))
    assert fake.image is None, fake.image


def test_a_load_that_refuses_leaves_the_stamp_of_the_table_in_force(tmp_path: Path) -> None:
    """The alarm describes the table loaded now: a refused load installs none of its own."""
    shutil.copy(GUEST / "dpmi.exe", tmp_path / "dpmi.exe")
    shutil.copy(GUEST / "dpmi.sym", tmp_path / "dpmi.sym")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(tmp_path / "dpmi.sym"), base="400000"))
    stamp = fake.image
    assert stamp is not None and str(stamp["path"]).endswith("dpmi.exe"), fake.image
    typed = tmp_path / "types.txt"
    typed.write_text("a_name_the_table_lacks:u8\n", encoding="utf-8")
    refused = server.symbols_load(
        path=_map(tmp_path, "try.nm", "00001000 T _main\n"), base="400000",
        types=str(typed))
    assert refused["status"] == "INVALID", refused
    assert fake.image == stamp, fake.image


def _asking(fake: NamesFake) -> list[str]:
    asked: list[str] = []
    real = fake.selector

    def selector(reg: str) -> dict[str, int]:
        asked.append(reg)
        return real(reg)
    fake.selector = selector  # type: ignore[method-assign]
    return asked


def test_a_table_where_two_names_fold_to_one_is_refused_and_a_lookup_ignores_case(
        tmp_path: Path) -> None:
    _names(tmp_path)
    clash = _map(tmp_path, "clash.nm",
                 "00001000 T ShowCredits\n00002000 T x\n00003000 T showcredits\n")
    got = cast(dict[str, Any], server.symbols_load(path=clash, base="400000"))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "line 1" in got["message"] and "line 3" in got["message"], got["message"]
    assert not dstate.STATE.table, "a refused load installs nothing"
    _ok(server.symbols_load(path=_map(tmp_path, "ok.nm", "00001000 T ShowCredits\n"),
                            base="400000"))
    found = _ok(server.symbols_find(name="showcredits"))
    assert [row["name"] for row in found["symbols"]] == ["ShowCredits"], found
    armed = _ok(server.breakpoint_at(ref="showcredits"))
    assert armed["state"] == "armed" and armed["armed"] is True, armed


def test_a_table_measured_off_another_register_keeps_the_selectors_when_cs_agrees(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    asked = _asking(fake)
    _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"), base_from="DS"))
    assert asked == ["DS", "CS"], asked
    assert _selectors() == {"selector_CS": 0xA7, "selector_DS": 0xAF}, dstate.STATE.base


def test_a_base_the_caller_gave_keeps_no_selectors_where_cs_holds_another(
        tmp_path: Path) -> None:
    _names(tmp_path)
    _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"), base="500000"))
    assert _selectors() == {}, dstate.STATE.base
    _ok(server.symbols_load(path=_map(tmp_path, "b.nm", "00001000 T _main\n"), base="400000"))
    assert _selectors() == {"selector_CS": 0xA7, "selector_DS": 0xAF}, dstate.STATE.base


def test_a_batch_added_where_the_table_sits_carries_the_selectors_it_cannot_read(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"), base="400000"))
    fake.running = True
    _ok(server.symbols_load(path=_map(tmp_path, "b.nm", "00002000 T _second\n"),
                            base="400000"))
    assert _selectors() == {"selector_CS": 0xA7, "selector_DS": 0xAF}, dstate.STATE.base
    fake.running = False
    fake.cs, fake.ds = "00B7", "00BF"
    _ok(server.symbols_load(path=_map(tmp_path, "c.nm", "00003000 T _third\n"), base="400000"))
    assert _selectors() == {"selector_CS": 0xB7, "selector_DS": 0xBF}, "the stop's own win"


def test_a_load_while_the_guest_runs_says_its_re_arm_waits_for_the_stop(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    fake.running = True
    got = _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"),
                                  base="400000"))
    assert got["declarations"] == {
        "deferred": True,
        "note": "the re-arm runs at the next stop, after the debugger takes the load"}, got
    assert dstate.STATE.pending["dirty"] is True


def test_a_load_says_how_many_bytes_it_handed_the_debugger(tmp_path: Path) -> None:
    _names(tmp_path)
    got = _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"),
                                  base="400000"))
    assert got["bytes"] == 2 + dsym.RECORD, got


# A real ILINK32 map of three sections (tests/fixtures/borland-ilink32/provenance.txt).
ILINK32_MAP = Path(__file__).parent / "fixtures" / "borland-ilink32" / "sections32.map"
ILINK32_BASES = {"1": "401000", "2": "423000", "3": "4289B8"}


def test_a_sectioned_table_has_no_descriptor(tmp_path: Path) -> None:
    _names(tmp_path)
    got = _ok(server.symbols_load(path=str(ILINK32_MAP), section_bases=ILINK32_BASES))
    assert got["limit"]["available"] is False and got["descriptor"]["available"] is False, got
    assert got["summary"].startswith(f"symbols_load: {got['loaded']} loaded of "), got["summary"]
    assert "available" not in got["summary"] and ", base" not in got["summary"], got["summary"]


def test_a_real_mode_stop_with_no_base_names_both_ways_to_give_one(tmp_path: Path) -> None:
    _names(tmp_path, mode="Real")
    got = cast(dict[str, Any], server.symbols_load(
        path=_map(tmp_path, "a.nm", "00001000 T _main\n")))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    for said in ("`base`", "`section_bases`", '"8000"'):
        assert said in got["message"], said


def test_types_may_name_a_symbol_of_any_batch_the_table_holds(tmp_path: Path) -> None:
    _names(tmp_path)
    _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 D _old\n"), base="400000"))
    types = _map(tmp_path, "t.txt", "_old: ptr32\n_new: u16\n")
    _ok(server.symbols_load(path=_map(tmp_path, "b.nm", "00002000 D _new\n"), base="400000",
                            types=types))


def test_types_for_symbols_the_table_lacks_are_named_five_at_most(tmp_path: Path) -> None:
    _names(tmp_path)
    types = _map(tmp_path, "t.txt", "".join(f"_absent{i}: u16\n" for i in range(6)))
    got = cast(dict[str, Any], server.symbols_load(
        path=_map(tmp_path, "a.nm", "00001000 D _main\n"), base="400000", types=types))
    assert got["status"] == "INVALID", got
    listed = got["message"].split("lacks: ", 1)[1]
    assert listed.count("_ABSENT") == 5, listed


def test_a_types_file_that_is_not_there_is_refused_naming_types(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.symbols_load(
        path=_map(tmp_path, "a.nm", "00001000 D _main\n"), base="400000",
        types=str(tmp_path / "absent.txt")))
    assert got["status"] == "INVALID" and got["message"].startswith("types:"), got


def test_a_batch_that_would_overfill_the_queued_one_is_refused_and_the_table_kept(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=_map(tmp_path, "a.nm", "00001000 T _main\n"), base="400000"))
    fake.running = True
    dstate.STATE.pending["load"] = struct.pack("<H", dsym.COUNT_MAX) + bytes(
        dsym.RECORD * dsym.COUNT_MAX)
    before = list(dstate.STATE.table)
    got = cast(dict[str, Any], server.symbols_load(
        path=_map(tmp_path, "b.nm", "00002000 T _second\n"), base="400000"))
    assert got["status"] == "INVALID" and "queued for one load" in got["message"], got
    assert dstate.STATE.table == before


def test_a_section_the_table_does_not_hold_is_refused_by_name(tmp_path: Path) -> None:
    _names(tmp_path)
    _ok(server.symbols_load(path=str(ILINK32_MAP), section_bases=ILINK32_BASES))
    got = cast(dict[str, Any], server.symbols_find(offset=0x10, section=4))
    assert got["status"] == "INVALID" and got["code"] == "unknown_ref", got
    assert "nothing in section 4" in got["message"], got


def test_a_linear_address_in_a_section_the_table_does_not_hold_is_refused_by_name(
        tmp_path: Path) -> None:
    _names(tmp_path)
    _ok(server.symbols_load(path=str(ILINK32_MAP), section_bases=ILINK32_BASES))
    got = cast(dict[str, Any], server.symbols_find(linear="10", section=4))
    assert got["status"] == "INVALID" and got["code"] == "unknown_ref", got
    assert "nothing in section 4" in got["message"], got


def test_section_bases_that_are_no_mapping_are_refused_naming_them() -> None:
    with pytest.raises(ds.Invalid) as refused:
        placement.hex_bases("400000")  # type: ignore[arg-type]
    assert str(refused.value).startswith("section_bases is a mapping of section index"), refused


def test_a_read_of_an_ambiguous_name_while_the_guest_runs_says_why(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_twice", 0x10, kind="D"),
                                     dsym.Symbol("_twice", 0x20, kind="D")])
    fake.running = True
    with pytest.raises(ds.NotStopped) as refused:
        placement.read_target("_twice", "DS", fake)  # type: ignore[arg-type]
    assert "names 2 symbols" in str(refused.value), refused.value

