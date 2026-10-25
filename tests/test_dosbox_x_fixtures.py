"""Generated fixtures (each with its `build.sh`) read by the reader, unlike the manual sweep."""

from __future__ import annotations

import re
from pathlib import Path

import dosbox_symbols as sym

FIXTURES = Path(__file__).parent / "fixtures"
TLINK16 = FIXTURES / "borland-tlink16" / "MAPDEMO.MAP"
DJGPP_NM = FIXTURES / "djgpp" / "mapdemo.sym"
DJGPP_LD = FIXTURES / "djgpp" / "mapdemo.ld.map"
WATCOM = FIXTURES / "watcom" / "MAPDEMO.MAP"
ALL_FIXTURES = (TLINK16, DJGPP_NM, DJGPP_LD, WATCOM)


def _read(path: Path) -> tuple[list[sym.Symbol], sym.ParseReport]:
    assert path.is_file(), f"the fixture {path} is not there; run its build.sh"
    report = sym.ParseReport()
    syms, _ = sym.parse(path.read_text(encoding="latin-1"), report)
    # an empty read would make every count below true against nothing
    assert syms, f"{path} read to zero symbols, so nothing below examined anything"
    return syms, report



def test_the_generated_tlink_map_reads_at_its_own_counts() -> None:
    syms, report = _read(TLINK16)
    assert report.fmt == "borland-tlink", report.fmt
    assert len(syms) == 5, [s.name for s in syms]
    assert sum(1 for s in syms if s.idle) == 3, [(s.name, s.idle) for s in syms]
    assert report.unreadable_rows == [], report.unreadable_rows


def test_the_two_publics_sections_are_one_set_and_not_two() -> None:
    """TLINK prints its publics twice; read as two, each would collide with itself."""
    syms, _ = _read(TLINK16)
    names = sorted(s.name for s in syms)
    assert names == sorted(set(names)), names
    assert names == ["MAP_DATA_SYMBOL", "MAP_OVERLAID_ONE", "MAP_OVERLAID_TWO",
                     "MAP_RESIDENT_SAME_A", "MAP_RESIDENT_SAME_B"], names


def test_the_borland_fixture_folds_seg_times_sixteen_plus_offset() -> None:
    at = {s.name: s.offset for s in _read(TLINK16)[0]}
    assert at["MAP_OVERLAID_ONE"] == 0x23 * 16 + 0x0, at
    assert at["MAP_OVERLAID_TWO"] == 0x23 * 16 + 0x4, at
    assert at["MAP_RESIDENT_SAME_A"] == 0x0, at
    # a fold that ignored the offset would not keep the pair 4 bytes apart
    assert at["MAP_OVERLAID_TWO"] - at["MAP_OVERLAID_ONE"] == 4, at
    assert {s.section for s in _read(TLINK16)[0]} == {sym.FLAT}


def test_the_borland_fixture_really_collides_at_fifteen_characters() -> None:
    syms, _ = _read(TLINK16)
    by = {s.name: s for s in syms}
    a, b = "MAP_RESIDENT_SAME_A", "MAP_RESIDENT_SAME_B"
    assert a in by and b in by, sorted(by)
    # the premise: a rename pulling them apart fails here instead of testing nothing
    assert a[:sym.NAME_MAX] == b[:sym.NAME_MAX], (a[:sym.NAME_MAX], b[:sym.NAME_MAX])
    p = sym.plan(syms)
    p.check()
    assert p.disambiguated == 1, p.disambiguated
    assert len(set(p.short)) == len(p.short), p.short
    assert sorted(n for n in p.short if n.startswith("MAP_RESIDENT")) == \
        ["MAP_RESIDENT_SA", "MAP_RESIDENT_~0"], p.short


def test_the_djgpp_fixture_carries_the_addresses_nm_printed() -> None:
    at = {s.name: s.offset for s in _read(DJGPP_NM)[0]}
    long_one = "_map_demo_a_very_long_symbol_name"
    assert at[long_one] == 0x1F24, hex(at[long_one])
    assert at["_map_demo_short"] == 0x1F49, hex(at["_map_demo_short"])
    assert at["_map_demo_helper_alpha"] == 0x1F10, hex(at["_map_demo_helper_alpha"])
    assert at["_map_demo_absolute"] == 0x3F8, hex(at["_map_demo_absolute"])


def test_the_detailed_segment_map_does_not_leak_in_as_symbols() -> None:
    syms, _ = _read(TLINK16)
    assert not [s for s in syms if "=" in s.name], [s.name for s in syms]


def test_the_mark_is_read_per_symbol_and_is_not_a_property_of_the_segment() -> None:
    """What `idle` means is unknown; only that it is read per symbol is pinned."""
    idle = {s.name: s.idle for s in _read(TLINK16)[0]}
    assert idle["MAP_OVERLAID_ONE"] is False, idle
    assert idle["MAP_OVERLAID_TWO"] is False, idle
    assert idle["MAP_RESIDENT_SAME_A"] is True, idle
    assert idle["MAP_RESIDENT_SAME_B"] is True, idle



def test_the_generated_nm_listing_reads_and_carries_the_classes_it_was_written_for() -> None:
    """The source picks symbols for the reader's branches."""
    syms, report = _read(DJGPP_NM)
    assert report.fmt == "nm", report.fmt
    by_name = {s.name: s for s in syms}
    assert "_map_demo_a_very_long_symbol_name" in by_name, "the long name is gone"
    assert len("_map_demo_a_very_long_symbol_name") > sym.NAME_MAX
    alpha, bravo = "_map_demo_helper_alpha", "_map_demo_helper_bravo"
    assert alpha in by_name and bravo in by_name, sorted(by_name)
    assert alpha[:sym.NAME_MAX] == bravo[:sym.NAME_MAX], (alpha, bravo)
    # `A` is absolute (a port number), so no base places it
    assert by_name["_map_demo_absolute"].kind == "A", by_name["_map_demo_absolute"]


def test_the_unplaceable_classes_are_excluded_and_counted_not_dropped() -> None:
    syms, _ = _read(DJGPP_NM)
    p = sym.plan(syms)
    p.check()
    # `short` holds 15-character stems, so the full name alone could never be found there
    assert "_map_demo_absolute" not in [x.name for x in p.symbols], "the absolute was kept"
    assert "_map_demo_absol" not in p.short, "the absolute was placed under its stem"
    # identity, not just a count: many `N` symbols would keep it high if `A` left _UNPLACEABLE
    absolutes = [x for x in syms if x.kind == "A"]
    assert [x.name for x in absolutes] == ["_map_demo_absolute"], absolutes
    assert p.excluded_unplaceable == len([x for x in syms if x.kind in sym._UNPLACEABLE])
    assert p.excluded_unplaceable > len(absolutes), p.excluded_unplaceable


def test_the_generated_ld_map_reads_as_a_gnu_map_and_reports_what_it_skipped() -> None:
    syms, report = _read(DJGPP_LD)
    assert report.fmt == "gnu-ld-map", report.fmt
    assert len(syms) > 100, len(syms)
    assert report.unreadable_rows, "a GNU map with nothing skipped is not a GNU map"
    assert len(report.unreadable_rows) > len(syms), (
        len(report.unreadable_rows), len(syms))


def test_every_fixture_is_text_and_none_of_them_is_a_binary() -> None:
    assert len(ALL_FIXTURES) == 4, ALL_FIXTURES
    for path in ALL_FIXTURES:
        data = path.read_bytes()
        assert b"\x00" not in data, f"{path} carries NUL bytes, so it is not text"




def test_the_generated_watcom_map_reads_and_nothing_in_it_is_lost() -> None:
    syms, report = _read(WATCOM)
    assert report.fmt == "watcom", report.fmt
    assert report.unreadable_rows == [], report.unreadable_rows
    rows = _watcom_rows(WATCOM.read_text(encoding="latin-1"))
    assert len(syms) == len(rows) == 69, (len(syms), len(rows))


def _watcom_rows(text: str) -> list[str]:
    """The symbol rows, bracketed on the linker's box drawing and not on the parser's anchor."""
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if "|   Memory Map   |" in line:
            inside = True
            continue
        if inside and out and line.strip().startswith("+-"):
            break
        if inside and re.match(r"^[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}", line):
            out.append(line)
    assert out, "the oracle found no rows, so it is measuring its own brackets"
    return out


def test_a_module_line_does_not_end_the_watcom_walk() -> None:
    """Without declaring `Module:` and `=====` lines as prose the walk ends at the first rule."""
    text = WATCOM.read_text(encoding="latin-1")
    assert "Module:" in text, "the fixture carries no Module: line, so this tests nothing"
    modules = [line for line in text.splitlines() if line.startswith("Module:")]
    assert len(modules) > 3, modules
    syms, _ = _read(WATCOM)
    assert len(syms) > 10, syms


def test_the_watcom_mark_is_glued_to_the_address_and_s_becomes_the_kind() -> None:
    """The mark has no space after the address; `s` (static) becomes `kind`."""
    syms, _ = _read(WATCOM)
    by_name = {s.name: s for s in syms}
    assert "map_demo_local_" in by_name, sorted(by_name)[:10]
    assert by_name["map_demo_local_"].kind == "s", by_name["map_demo_local_"]
    assert by_name["map_demo_reached_"].kind == "?", by_name["map_demo_reached_"]
    assert not [s for s in syms if s.idle], [s.name for s in syms if s.idle]


def test_the_watcom_fixture_spans_more_than_one_section() -> None:
    syms, _ = _read(WATCOM)
    sections = {s.section for s in syms}
    assert len(sections) >= 2, sections
    by_name = {s.name: s for s in syms}
    assert by_name["map_demo_local_"].section != by_name["_map_demo_table"].section, by_name


def test_section_zero_is_real_and_is_why_the_flat_sentinel_is_negative() -> None:
    """A Watcom map emits section 0 (`__DOSseg__`), so the no-sections sentinel `FLAT` is -1."""
    syms, _ = _read(WATCOM)
    assert 0 in {s.section for s in syms}, {s.section for s in syms}
    assert sym.FLAT < 0, sym.FLAT
    assert sym.FLAT not in {s.section for s in syms}


def test_the_watcom_symbols_place_at_distinct_addresses_from_the_callers_bases() -> None:
    """Bases 1 and 2 come from the linked image, 0x8000 for section 0 is chosen.

    The equalities discriminate; a `!=` would be a tautology, as the offsets differ.
    """
    syms, _ = _read(WATCOM)
    bases = {0: 0x8000, 1: 0x10000, 2: 0x20000}
    placed = dict(sym.decode(sym.encode(sym.plan(syms), section_bases=bases)))
    local = [s for s in syms if s.name == "map_demo_local_"][0]
    table = [s for s in syms if s.name == "_map_demo_table"][0]
    assert local.section != table.section, (local, table)
    assert placed[local.name[:sym.NAME_MAX]] == bases[local.section] + local.offset
    assert placed[table.name[:sym.NAME_MAX]] == bases[table.section] + table.offset
    assert bases[local.section] != bases[table.section], bases
