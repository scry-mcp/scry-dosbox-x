"""The fixtures this package GENERATED, read by the reader that claims to read them.

WHY THEY EXIST.  The claim "this reads Borland TLINK maps and DJGPP `nm` output" rested
on material living OUTSIDE this repository: the author's own maps, one of them in an
unpublished project.  A stranger who clones this can check none of it, and neither can
CI.  So one artefact per toolchain is BUILT HERE from a source written here, committed,
and read by these cases -- which is what turns the claim into a fact a clone can check.

THEY SHIP WITH THEIR GENERATOR, which is the half that is easy to skip.  A captured
artefact whose recipe is lost cannot be re-captured, so every later question about it is
unanswerable: a discrepancy in a transcription of a map that went missing from disk can
be settled by nobody.  `build.sh` beside each fixture re-makes it, and the TLINK one comes
back BYTE-IDENTICAL from its own recipe.

WHAT THESE CASES ARE NOT.  They are not the sweep.  The sweep reads the real five maps
where they live and is declared MANUAL for that reason (`tests/gates-manual.txt`); these
run anywhere, on material this repository owns.
"""

from __future__ import annotations

import re
from pathlib import Path

import dosbox_symbols as sym

FIXTURES = Path(__file__).parent / "fixtures"
TLINK16 = FIXTURES / "borland-tlink16" / "MAPDEMO.MAP"
DJGPP_NM = FIXTURES / "djgpp" / "mapdemo.sym"
DJGPP_LD = FIXTURES / "djgpp" / "mapdemo.ld.map"
WATCOM = FIXTURES / "watcom" / "MAPDEMO.MAP"
# EVERY COMMITTED FIXTURE, in one place, so a case that walks "all of them" cannot be
# written against three of four. A name defined halfway down the file, AFTER the case
# that checks no fixture is a binary, is invisible to that case -- and `WATCOM` is the
# only one whose recipe leaves an `.exe` in the same directory.
ALL_FIXTURES = (TLINK16, DJGPP_NM, DJGPP_LD, WATCOM)


def _read(path: Path) -> tuple[list[sym.Symbol], sym.ParseReport]:
    assert path.is_file(), f"the fixture {path} is not there; run its build.sh"
    report = sym.ParseReport()
    syms, _ = sym.parse(path.read_text(encoding="latin-1"), report)
    # AN EMPTY READ IS NOT A PASS. A fixture that stopped carrying symbols would make
    # every count below trivially true against nothing.
    assert syms, f"{path} read to zero symbols, so nothing below examined anything"
    return syms, report


# ------------------------------------------------------------ Borland TLINK, 16-bit

def test_the_generated_tlink_map_reads_at_its_own_counts() -> None:
    """FIVE publics, THREE of them flagged, nothing unreadable.

    The numbers are written here rather than derived from the file, on purpose: a check
    that recomputes its expectation from the artefact under test moves WITH any break
    and can never fail.
    """
    syms, report = _read(TLINK16)
    assert report.fmt == "borland-tlink", report.fmt
    assert len(syms) == 5, [s.name for s in syms]
    assert sum(1 for s in syms if s.idle) == 3, [(s.name, s.idle) for s in syms]
    assert report.unreadable_rows == [], report.unreadable_rows


def test_the_two_publics_sections_are_one_set_and_not_two() -> None:
    """TLINK prints its publics twice -- by name and by value -- and they are the SAME
    set.  Read as two, every symbol collides with itself and the disambiguator invents a
    suffix for the second copy of each.  This fixture prints both sections, so it is the
    artefact that would show it."""
    syms, _ = _read(TLINK16)
    names = sorted(s.name for s in syms)
    assert names == sorted(set(names)), names
    assert names == ["MAP_DATA_SYMBOL", "MAP_OVERLAID_ONE", "MAP_OVERLAID_TWO",
                     "MAP_RESIDENT_SAME_A", "MAP_RESIDENT_SAME_B"], names


def test_the_borland_fixture_folds_seg_times_sixteen_plus_offset() -> None:
    """THE ADDRESS, which is the product of this whole package, asserted against this
    fixture.

    Names, counts, marks and the segment-table trap are pinned elsewhere; this pins the
    arithmetic that turns `0023:0000` into an offset.  Changing the fold to
    `seg * 8 + off` would leave every other case in this module green, and the property
    would be caught only by text written inside the test file, never against an artefact
    a real linker emitted.
    """
    at = {s.name: s.offset for s in _read(TLINK16)[0]}
    # Read off the fixture's own rows: MAP_OVERLAID_ONE is ` 0023:0000`, ..._TWO is
    # ` 0023:0004`, and the two residents are ` 0000:0000` / ` 0000:0004`.
    assert at["MAP_OVERLAID_ONE"] == 0x23 * 16 + 0x0, at
    assert at["MAP_OVERLAID_TWO"] == 0x23 * 16 + 0x4, at
    assert at["MAP_RESIDENT_SAME_A"] == 0x0, at
    # AND THE PAIR IS 4 BYTES APART, which a fold with the wrong multiplier keeps but a
    # fold that ignored the offset entirely would not.
    assert at["MAP_OVERLAID_TWO"] - at["MAP_OVERLAID_ONE"] == 4, at
    # THE SECTION IS FLAT, because a real-mode map determines its own address completely.
    assert {s.section for s in _read(TLINK16)[0]} == {sym.FLAT}


def test_the_borland_fixture_really_collides_at_fifteen_characters() -> None:
    """THE COLLISION THE DISAMBIGUATOR EXISTS FOR, on an artefact a linker emitted.

    Names like `MAP_RESIDENT_ONE` / `MAP_RESIDENT_TWO` shorten to `MAP_RESIDENT_ON` and
    `MAP_RESIDENT_TW` -- distinct at index 13. A fixture built from those shortens to five
    distinct strings, performs exactly ZERO disambiguation, and still reads as the case
    that proves the feature. So the pair here shares its first fifteen characters.
    """
    syms, _ = _read(TLINK16)
    by = {s.name: s for s in syms}
    a, b = "MAP_RESIDENT_SAME_A", "MAP_RESIDENT_SAME_B"
    assert a in by and b in by, sorted(by)
    # THE PREMISE, read off the fixture rather than written here: if a rename ever pulls
    # them apart, this fails instead of the case quietly stopping to test anything.
    assert a[:sym.NAME_MAX] == b[:sym.NAME_MAX], (a[:sym.NAME_MAX], b[:sym.NAME_MAX])
    p = sym.plan(syms)
    p.check()
    assert p.disambiguated == 1, p.disambiguated
    assert len(set(p.short)) == len(p.short), p.short
    # AND NEITHER OF THEM WAS GIVEN THE OTHER'S NAME: exactly one keeps its own stem.
    assert sorted(n for n in p.short if n.startswith("MAP_RESIDENT")) == \
        ["MAP_RESIDENT_SA", "MAP_RESIDENT_~0"], p.short


def test_the_djgpp_fixture_carries_the_addresses_nm_printed() -> None:
    """The same gap on the other flat format: names and kinds were pinned, addresses were
    not. These four are read straight off `mapdemo.sym`."""
    at = {s.name: s.offset for s in _read(DJGPP_NM)[0]}
    long_one = "_map_demo_a_very_long_symbol_name"
    assert at[long_one] == 0x1F24, hex(at[long_one])
    assert at["_map_demo_short"] == 0x1F49, hex(at["_map_demo_short"])
    assert at["_map_demo_helper_alpha"] == 0x1F10, hex(at["_map_demo_helper_alpha"])
    assert at["_map_demo_absolute"] == 0x3F8, hex(at["_map_demo_absolute"])


def test_the_detailed_segment_map_does_not_leak_in_as_symbols() -> None:
    """The trap the header anchor exists for: that section opens every row with a
    `seg:off` pair too, so a pattern matching the LINE emits symbols called `ACBP=48`."""
    syms, _ = _read(TLINK16)
    assert not [s for s in syms if "=" in s.name], [s.name for s in syms]


def test_the_mark_is_read_per_symbol_and_is_not_a_property_of_the_segment() -> None:
    """WHAT `idle` MEANS IS UNKNOWN, and this case pins only what is observed.

    One tempting explanation is "a public that lives in an overlay TLINK has not made
    resident".  This fixture refutes it: it is linked WITH an overlay (`/o`), and the two
    publics of the overlaid module are exactly the two that come back UNFLAGGED, while the
    three resident ones are flagged.  A real map with no overlay segments at all and many
    flagged symbols refutes it from the other side.

    So no explanation is asserted here, because no explanation is known, and swapping one
    guess for another is how the first one got written.  What IS asserted is the
    behaviour the reader really has and really needs: the mark is read PER SYMBOL, so two
    symbols can differ in it, and it travels on the symbol rather than being inferred
    from anything else.
    """
    idle = {s.name: s.idle for s in _read(TLINK16)[0]}
    assert idle["MAP_OVERLAID_ONE"] is False, idle
    assert idle["MAP_OVERLAID_TWO"] is False, idle
    assert idle["MAP_RESIDENT_SAME_A"] is True, idle
    assert idle["MAP_RESIDENT_SAME_B"] is True, idle


# ------------------------------------------------------------------- DJGPP, nm and ld

def test_the_generated_nm_listing_reads_and_carries_the_classes_it_was_written_for() -> None:
    """The source picks its symbols for the reader's BRANCHES, not for tidiness: a name
    past the 15-character field, two statics that truncate to the same 15, an absolute
    whose value is a port number and not an address."""
    syms, report = _read(DJGPP_NM)
    assert report.fmt == "nm", report.fmt
    by_name = {s.name: s for s in syms}
    assert "_map_demo_a_very_long_symbol_name" in by_name, "the long name is gone"
    assert len("_map_demo_a_very_long_symbol_name") > sym.NAME_MAX
    # THE TWO STATICS TRUNCATE TO THE SAME FIFTEEN, which is the collision the
    # disambiguator exists for. Asserted on the fixture rather than on a string written
    # here, so a source edit that pulls them apart fails instead of passing quietly.
    alpha, bravo = "_map_demo_helper_alpha", "_map_demo_helper_bravo"
    assert alpha in by_name and bravo in by_name, sorted(by_name)
    assert alpha[:sym.NAME_MAX] == bravo[:sym.NAME_MAX], (alpha, bravo)
    # `A` is ABSOLUTE: `.set _map_demo_absolute, 0x3F8` is a port number that is nowhere
    # in the program, so no base places it.
    assert by_name["_map_demo_absolute"].kind == "A", by_name["_map_demo_absolute"]


def test_the_unplaceable_classes_are_excluded_and_counted_not_dropped() -> None:
    """The whole idiom of this module: a bucket that keeps the table TRUE beside a count
    that keeps the loss VISIBLE."""
    syms, _ = _read(DJGPP_NM)
    p = sym.plan(syms)
    p.check()
    # THE ABSOLUTE BY NAME, in BOTH forms, because one of them asserts nothing:
    # `n == "_map_demo_absolute"` over `p.short` is unsatisfiable for every possible
    # input, since `short` holds names TRUNCATED to fifteen characters and that name is
    # eighteen. Only the stem is what `short` could ever contain.
    assert "_map_demo_absolute" not in [x.name for x in p.symbols], "the absolute was kept"
    assert "_map_demo_absol" not in p.short, "the absolute was placed under its stem"
    # AND THE IDENTITY, not just a positive count. `excluded_unplaceable > 0` was carried
    # entirely by other symbols: this fixture has many of type `N` and exactly ONE
    # of type `A`, so dropping `A` from `_UNPLACEABLE` would leave the count high and the
    # case green. The `A` is the one the fixture's source says it exists for.
    absolutes = [x for x in syms if x.kind == "A"]
    assert [x.name for x in absolutes] == ["_map_demo_absolute"], absolutes
    assert p.excluded_unplaceable == len([x for x in syms if x.kind in sym._UNPLACEABLE])
    assert p.excluded_unplaceable > len(absolutes), p.excluded_unplaceable


def test_the_generated_ld_map_reads_as_a_gnu_map_and_reports_what_it_skipped() -> None:
    """A GNU link map is MOSTLY not symbols -- section headers, fills, archive members --
    so a high unreadable count here is the format's own shape and not damage.  It is in
    the fixtures because it is the one artefact that makes that ratio concrete."""
    syms, report = _read(DJGPP_LD)
    assert report.fmt == "gnu-ld-map", report.fmt
    assert len(syms) > 100, len(syms)
    # THE ROWS ARE RECORDED, not merely counted. A count says a population was cut; the
    # rows say what the cut was, and that is the only form it can be acted on in.
    assert report.unreadable_rows, "a GNU map with nothing skipped is not a GNU map"
    assert len(report.unreadable_rows) > len(syms), (
        len(report.unreadable_rows), len(syms))


def test_every_fixture_is_text_and_none_of_them_is_a_binary() -> None:
    """This module reads TEXT and refuses to parse a binary, which is its stated
    boundary.  A fixture that slipped in as a linked image would be 148 KB nothing reads
    -- and the generators delete theirs for exactly that reason."""
    assert len(ALL_FIXTURES) == 4, ALL_FIXTURES
    for path in ALL_FIXTURES:
        data = path.read_bytes()
        assert b"\x00" not in data, f"{path} carries NUL bytes, so it is not text"


# --------------------------------------------------------------------- Open Watcom


def test_the_generated_watcom_map_reads_and_nothing_in_it_is_lost() -> None:
    """THE FOURTH FORMAT, read by the SECOND user of the anchored walk.

    The count is asserted against the file's own rows rather than against a number
    written here, because what this case is really about is that nothing was DROPPED:
    a Watcom map interleaves `Module:` lines with its rows, and a walk that took one of
    those for an ending would stop partway through and report a clean, short answer.
    """
    syms, report = _read(WATCOM)
    assert report.fmt == "watcom", report.fmt
    assert report.unreadable_rows == [], report.unreadable_rows
    rows = _watcom_rows(WATCOM.read_text(encoding="latin-1"))
    assert len(syms) == len(rows) == 69, (len(syms), len(rows))


def _watcom_rows(text: str) -> list[str]:
    """The symbol rows, found by a rule of this test's OWN and not by the parser's.

    IT BRACKETS ON THE LINKER'S BOX DRAWING, `|   Memory Map   |` above and the next
    `+---+` rule below, and neither appears anywhere in `dosbox_symbols`. The first
    version opened on the `Address        Symbol` line, which IS the reader's own anchor
    (`_WATCOM_HEADER`) -- so a break that moved or mis-anchored the header would have
    moved the parser and this oracle in the SAME direction, and the only thing left
    separating them was a number written here.
    """
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
    """THE DECLARED PROSE, and the reason `Anchored.skip` exists at all.

    A Watcom map puts a `Module: <name>` line before each object's symbols and an
    `======= ======` rule under its own heading. Neither is blank and neither looks like
    a row, so without a declaration the walk ENDS at the rule -- one line into a section
    holding 69 symbols -- and reports a clean, empty answer.
    """
    text = WATCOM.read_text(encoding="latin-1")
    assert "Module:" in text, "the fixture carries no Module: line, so this tests nothing"
    modules = [line for line in text.splitlines() if line.startswith("Module:")]
    assert len(modules) > 3, modules
    syms, _ = _read(WATCOM)
    # SYMBOLS FROM AFTER THE FIRST `Module:` LINE, which is the half a walk that stopped
    # early would be missing.
    assert len(syms) > 10, syms


def test_the_watcom_mark_is_glued_to_the_address_and_s_becomes_the_kind() -> None:
    """The format's own legend, which it prints above its symbols:

        * = unreferenced symbol
        + = symbol only referenced locally
        s = symbol is static

    THERE IS NO SPACE between the last hex digit and the letter, so a pattern expecting
    whitespace there matches nothing at all. `s` is carried as `kind`, where `nm`'s own
    lowercase-means-local convention already lives; the other two say something about
    REFERENCES and this module has nowhere honest to put that.
    """
    syms, _ = _read(WATCOM)
    by_name = {s.name: s for s in syms}
    assert "map_demo_local_" in by_name, sorted(by_name)[:10]
    assert by_name["map_demo_local_"].kind == "s", by_name["map_demo_local_"]
    assert by_name["map_demo_reached_"].kind == "?", by_name["map_demo_reached_"]
    # AND NONE OF THE THREE MARKS IS BORLAND'S `idle`: they are statements about
    # references, not about an address being conditional.
    assert not [s for s in syms if s.idle], [s.name for s in syms if s.idle]


def test_the_watcom_fixture_spans_more_than_one_section() -> None:
    """FINDING A6, and it is a property of the FIXTURE rather than of any harness.

    With every symbol in one section, a reader that consults the section index and one
    that ignores it entirely produce byte-identical output -- so the case asserts
    nothing about the one feature it exists for. Coverage cannot stand in for it either:
    a one-section fixture EXECUTES every line of the lookup.
    """
    syms, _ = _read(WATCOM)
    sections = {s.section for s in syms}
    assert len(sections) >= 2, sections
    # CODE AND DATA, named: `map_demo_local_` is a function and `_map_demo_table` is an
    # array, so they cannot be in the same section unless the fixture stopped being what
    # its source says it is.
    by_name = {s.name: s for s in syms}
    assert by_name["map_demo_local_"].section != by_name["_map_demo_table"].section, by_name


def test_section_zero_is_real_and_is_why_the_flat_sentinel_is_negative() -> None:
    """It decides a constant: `0000:00001234  __DOSseg__`.

    A Watcom map really emits section ZERO. With 0 as the "this format has no sections"
    sentinel, that symbol would be placed with a FLAT base handed in for some other
    file's benefit -- silently, at an address belonging to nothing. `FLAT` is -1, an
    index no map can print, because every one of these formats prints it as unsigned hex.
    """
    syms, _ = _read(WATCOM)
    assert 0 in {s.section for s in syms}, {s.section for s in syms}
    assert sym.FLAT < 0, sym.FLAT
    assert sym.FLAT not in {s.section for s in syms}


def test_the_watcom_symbols_place_at_distinct_addresses_from_the_callers_bases() -> None:
    """A Watcom map carries NO flat address anywhere and its sections OVERLAP, so the
    bases come from the caller -- from the executable's own object table, which this
    module does not read because it does not parse binaries.

    TWO OF THE THREE BASES ARE READ off the linked image of the pair this format was
    pinned against -- object 1 at 0x10000, object 2 at 0x20000. THE THIRD IS CHOSEN, and
    saying so matters: section 0 exists only because `__DOSseg__` is in it, and 0x8000 is
    a number picked so that symbol can be positioned at all. Presenting all three as
    read off the image would hide which one is a choice.

    AND THE DISCRIMINATION IS THE TWO EQUALITIES, not an inequality. A `!=` between these
    two reads as "the assertion a shared base cannot make" and is a TAUTOLOGY on this
    fixture: `map_demo_local_` is at offset 0x10 and `_map_demo_table` at 0x04, so ANY
    base assignment -- shared or per-section -- puts them at different addresses. This
    fixture carries no cross-section offset collision; the case that needs one is
    `test_two_sections_at_the_same_offset_land_at_different_addresses`,
    which uses 0xE4 three times.
    """
    syms, _ = _read(WATCOM)
    bases = {0: 0x8000, 1: 0x10000, 2: 0x20000}
    placed = dict(sym.decode(sym.encode(sym.plan(syms), section_bases=bases)))
    local = [s for s in syms if s.name == "map_demo_local_"][0]
    table = [s for s in syms if s.name == "_map_demo_table"][0]
    assert local.section != table.section, (local, table)
    assert placed[local.name[:sym.NAME_MAX]] == bases[local.section] + local.offset
    assert placed[table.name[:sym.NAME_MAX]] == bases[table.section] + table.offset
    # A READER THAT IGNORED THE SECTION would place both against ONE base, so each of the
    # two equalities above is what fails -- and this line says why it has to be an
    # equality: the same two symbols under a single base 0x10000 give 0x10010 and
    # 0x10004, which are still different from each other and still both wrong.
    assert bases[local.section] != bases[table.section], bases
