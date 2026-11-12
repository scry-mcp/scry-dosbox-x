"""The var-list converter, against bytes read out of the real debugger (goldens, no round trip)."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from scry_dosbox_x import symbols as sym

# Bytes DOSBox-X itself wrote for `IV 1234:5678 MYSYMBOL`, `IV 0:0 zero_lower` and a 36-char name
# (`IV` uppercases and keeps 15), transcribed from `xxd` of the file its `SV` produced.
REAL_THREE = bytes.fromhex(
    "0300"
    "4d59 5359 4d42 4f4c 0000 0000 0000 0000  b879 0100"
    "5a45 524f 5f4c 4f57 4552 0000 0000 0000  0000 0000"
    "4142 4344 4546 4748 494a 4b4c 4d4e 4f00  1f00 0a00"
    .replace(" ", ""))

# Captured by the round trip the module performs (`LV` a binary, `SV` the list), not by `IV`,
# which uppercases and truncates (tests/fixtures/symbols-lv/provenance.txt).
REAL_THREE_LOWER = (Path(__file__).parent / "fixtures" / "symbols-lv" / "three-lower.bin"
                    ).read_bytes()

# Transcribed `nm` output, source binary not kept: a 21-char name, a three-way collision,
# duplicate section symbols and a compiler label, the cases that decide the design.
NM_FRAGMENT = """\
0016df20 T _main
0005c830 T _engine_load_midi
0005aa20 T _engine_create
0012c7f0 T __poly_scanline_gcol8
0012d464 T __poly_scanline_grgb15
001306b4 T __poly_scanline_grgb15x
0006b58c t ..@15.l0
0013a020 t .text
00139dd0 t .text
002308b8 b .bss
"""

MEASURED_BASE = 0x00400000


def test_the_three_records_the_debugger_wrote_decode_to_what_was_typed() -> None:
    """The address is linear: typed `1234:5678` is stored as `0x179B8`."""
    got = sym.decode(REAL_THREE)
    assert got == [("MYSYMBOL", 0x000179B8),
                   ("ZERO_LOWER", 0x00000000),
                   ("ABCDEFGHIJKLMNO", 0x000A001F)]
    assert 0x1234 * 16 + 0x5678 == 0x000179B8
    assert 0xA000 * 16 + 0x1F == 0x000A001F


def test_encoding_those_same_three_reproduces_the_debuggers_bytes_exactly() -> None:
    syms = [sym.Symbol("MYSYMBOL", 0x000179B8),
            sym.Symbol("ZERO_LOWER", 0x00000000),
            sym.Symbol("ABCDEFGHIJKLMNO", 0x000A001F)]
    assert sym.encode(sym.plan(syms), base=0) == REAL_THREE


def test_a_record_is_twenty_bytes_and_the_header_is_two() -> None:
    assert len(REAL_THREE) == 2 + 3 * 20
    assert sym.RECORD == 20
    assert sym.NAME_MAX == 15


def test_nm_lines_parse_to_offsets_and_kinds() -> None:
    got = {s.name: s for s in sym.parse_nm(NM_FRAGMENT)}
    assert got["_main"].offset == 0x0016DF20
    assert got["_main"].kind == "T"
    assert got[".bss"].kind == "b"
    assert len(sym.parse_nm(NM_FRAGMENT)) == 10


def test_an_undefined_symbol_carries_no_address_and_is_not_one() -> None:
    """The population is asserted beside the exclusion, so a parser returning `[]` cannot pass."""
    text = NM_FRAGMENT + "                 U _some_import\n"
    got = sym.parse_nm(text)
    assert len(got) == len(sym.parse_nm(NM_FRAGMENT)) == 10, got
    assert all(s.name != "_some_import" for s in got)
    assert any(s.name == "_main" for s in got), (
        "the fragment's own symbols are gone too: this is a parser that excluded "
        "everything, not one that excluded the undefined symbol")


def test_text_that_is_not_a_symbol_list_is_an_error_and_not_an_empty_list() -> None:
    """Zero recognised lines and a program with no symbols are different facts."""
    with pytest.raises(sym.BadSymbolText, match="nothing to load"):
        sym.parse_nm("Makefile:12: warning: overriding recipe for target 'all'\n")


def test_a_link_map_parses_and_is_told_apart_from_nm_by_content() -> None:
    """The sniff is on content: a build may write `nm` output into a file called `.map`."""
    mapped = ("                0x000000000016df20                _main\n"
              "                0x000000000005c830                _engine_load_midi\n")
    assert sym.looks_like_map(mapped)
    assert not sym.looks_like_map(NM_FRAGMENT)
    got = sym.parse_map(mapped)
    assert [(s.name, s.offset) for s in got] == [("_main", 0x16DF20),
                                                 ("_engine_load_midi", 0x5C830)]


def test_a_collision_keeps_every_member_instead_of_dropping_the_losers() -> None:
    """Colliding names are all kept and renamed, not truncated to a first winner."""
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    poly = [n for n in p.short if n.startswith("__poly")]
    assert len(poly) == 3
    assert len(set(poly)) == 3, f"two symbols collapsed onto one name: {poly}"
    assert all(len(n) <= sym.NAME_MAX for n in p.short)
    assert p.disambiguated == 2
    assert p.truncated_names == 4


TWO_GROUPS_ONE_STEM = ("00001000 T _blender_black_a\n"
                       "00002000 T _blender_black_b\n"
                       "00003000 T _blender_blackXa\n"
                       "00004000 T _blender_blackXb\n")

REPEATED_FULL_NAME = ("00001000 t _static_helper\n"
                      "00002000 t _static_helper\n"
                      "00003000 t _static_helper\n")


def test_no_two_symbols_are_ever_given_the_same_name() -> None:
    """The central guarantee: distinct names across groups, not only within one."""
    for name, text in (("fragment", NM_FRAGMENT),
                       ("two groups one stem", TWO_GROUPS_ONE_STEM),
                       ("repeated full name", REPEATED_FULL_NAME)):
        p = sym.plan(sym.parse_nm(text))
        assert len(set(p.short)) == len(p.short), (
            f"{name}: {len(p.short) - len(set(p.short))} of {len(p.short)} symbols "
            f"share a name with another: {p.short}")
        assert len(p.short) == len(p.symbols), f"{name}: the lists are not parallel"


def test_two_groups_that_shorten_to_one_stem_do_not_both_start_at_zero() -> None:
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    assert len(set(p.short)) == 4, p.short


def test_a_name_nm_emits_more_than_once_yields_that_many_distinct_names() -> None:
    p = sym.plan(sym.parse_nm(REPEATED_FULL_NAME))
    assert len(p.short) == 3
    assert len(set(p.short)) == 3, p.short
    assert [s.offset for s in p.symbols] == [0x1000, 0x2000, 0x3000]


def test_a_symbol_whose_real_name_contains_a_tilde_does_not_collide_with_a_made_one() -> None:
    """The ledger is global because nothing stops a toolchain emitting `abcdefghijklm~0`."""
    out, _, _ = sym._disambiguate(
        ["abcdefghijklm~0", "abcdefghijklmXY1", "abcdefghijklmXY2"])
    assert len(set(out)) == 3, out


def test_a_name_that_fits_is_not_touched() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    by = dict(zip([s.name for s in p.symbols], p.short, strict=True))
    assert by["_main"] == "_main"
    assert by["_engine_create"] == "_engine_create"
    assert "~" not in by["_engine_create"]


def test_the_first_of_a_collision_keeps_its_plain_truncation() -> None:
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    assert p.short[0] == "_blender_black_a"[:sym.NAME_MAX]
    assert "~" not in p.short[0]


def test_the_emitted_names_are_a_pure_function_of_the_input_order() -> None:
    """The emitted list is asserted against a written-out expectation."""
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    assert p.short == ["_blender_black_", "_blender_blac~0",
                       "_blender_blackX", "_blender_blac~1"], p.short


def test_section_and_compiler_label_symbols_are_excluded_and_counted() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    assert p.excluded_noise == 4
    assert p.kept == 6
    assert all(not s.name.startswith(".") for s in p.symbols)
    back = sym.plan(sym.parse_nm(NM_FRAGMENT), keep_noise=True)
    assert back.excluded_noise == 0
    assert back.kept == 10


def test_every_parsed_symbol_lands_in_exactly_one_bucket() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="^_engine")
    assert p.parsed == 10
    assert p.kept + p.excluded_noise + p.excluded_pattern + len(p.unencodable) == 10
    assert p.kept == 2


def test_the_pattern_matches_the_full_name_not_the_shortened_one() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="_engine_load_midi$")
    assert [s.name for s in p.symbols] == ["_engine_load_midi"]


def test_a_non_ascii_name_is_refused_rather_than_replaced() -> None:
    p = sym.plan([sym.Symbol("_café", 0x10), sym.Symbol("_plain", 0x20)])
    assert p.unencodable == ["_café"]
    assert [s.name for s in p.symbols] == ["_plain"]


def test_the_base_is_added_to_every_offset() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="^_main$")
    got = sym.decode(sym.encode(p, MEASURED_BASE))
    assert got == [("_main", MEASURED_BASE + 0x0016DF20)]
    assert got[0][1] == 0x0056DF20


def test_a_name_too_long_for_the_field_is_refused_rather_than_shifting_the_file() -> None:
    p = sym.plan([sym.Symbol("_a", 0x10)])
    p.short = ["X" * 40]
    with pytest.raises(sym.BadSymbolText, match="past this record"):
        sym.encode(p, 0)


def test_a_base_that_pushes_a_symbol_past_32_bits_is_refused_by_name() -> None:
    p = sym.plan([sym.Symbol("_top", 0x1000)])
    with pytest.raises(sym.BadSymbolText, match="_top"):
        sym.encode(p, 0xFFFFFFFF)


def test_encode_refuses_when_nothing_says_where_the_program_was_loaded() -> None:
    """Asks the behaviour: a zero default would name whatever sits in low memory."""
    p = sym.plan([sym.Symbol("_x", 0x10)])
    with pytest.raises(sym.BadSymbolText, match="no base"):
        sym.encode(p)


def test_encode_refuses_a_flat_base_and_a_section_table_together() -> None:
    p = sym.plan([sym.Symbol("_x", 0x10)])
    with pytest.raises(sym.BadSymbolText, match="both"):
        sym.encode(p, 0x1000, section_bases={1: 0x400000})


def test_a_section_the_table_does_not_position_is_refused_and_not_placed_at_zero() -> None:
    p = sym.plan([sym.Symbol("_x", 0x10, section=2)])
    with pytest.raises(sym.BadSymbolText, match="section 2"):
        sym.encode(p, section_bases={1: 0x400000})


def test_an_empty_section_table_is_refused_rather_than_read_as_a_flat_program() -> None:
    p = sym.plan([sym.Symbol("_x", 0x10, section=1)])
    with pytest.raises(sym.BadSymbolText, match="positions no section"):
        sym.encode(p, section_bases={})


def test_two_sections_at_the_same_offset_land_at_different_addresses() -> None:
    """A shared base cannot express this: real Borland 32-bit sections all start at 0."""
    p = sym.plan([sym.Symbol("_a", 0xE4, section=1),
                  sym.Symbol("_b", 0xE4, section=2),
                  sym.Symbol("_c", 0xE4, section=3)])
    got = sym.decode(sym.encode(p, section_bases={1: 0x401000, 2: 0x423000,
                                                  3: 0x4289B8}))
    assert dict(got) == {"_a": 0x4010E4, "_b": 0x4230E4, "_c": 0x428A9C}, got


def test_a_file_that_disagrees_with_its_own_header_is_refused() -> None:
    with pytest.raises(sym.BadSymbolText, match="declares 3"):
        sym.decode(REAL_THREE[:-4])


def test_a_file_too_short_to_hold_even_a_count_says_so() -> None:
    with pytest.raises(sym.BadSymbolText, match="cannot hold"):
        sym.decode(b"\x03")


def test_more_symbols_than_the_count_field_holds_is_refused_not_wrapped() -> None:
    many = [sym.Symbol(f"_s{i}", i * 4) for i in range(sym.COUNT_MAX + 1)]
    with pytest.raises(sym.BadSymbolText, match="16 bits"):
        sym.plan(many)


def test_an_exact_name_wins_outright_over_its_prefixes() -> None:
    table = [sym.Symbol("_main", 0x100), sym.Symbol("_main_loop", 0x200)]
    assert [s.name for s in sym.find_by_name(table, "_main")] == ["_main"]
    assert len(sym.find_by_name(table, "_mai")) == 2


def test_prefix_matches_come_in_section_and_offset_order() -> None:
    table = [sym.Symbol("_late", 0x300), sym.Symbol("_early", 0x100),
             sym.Symbol("_other", 0x100, section=2), sym.Symbol("_mid", 0x200)]
    assert [s.name for s in sym.find_by_name(table, "_")] == ["_early", "_mid", "_late", "_other"]


def test_the_name_index_answers_exactly_what_the_scan_answers() -> None:
    table = [sym.Symbol("_main", 0x100), sym.Symbol("_main_loop", 0x200),
             sym.Symbol("_main", 0x300)]
    index = sym.index_by_name(table)
    assert index["_MAIN"] == [table[0], table[2]] and list(index) == ["_MAIN", "_MAIN_LOOP"]
    assert sym.find_by_name(table, "_main", index) == sym.find_by_name(table, "_main")
    assert len(sym.find_by_name(table, "_mai", index)) == 3
    assert sym.find_by_name(table, "_nope", index) == []
    got = sym.find_by_name(table, "_main", index)
    got.clear()
    assert len(index["_MAIN"]) == 2, "the caller emptied the index"


def test_a_lookup_ignores_case_and_answers_the_names_own_spelling() -> None:
    table = [sym.Symbol("ShowCredits", 0x100), sym.Symbol("ShowCreditsEnd", 0x200)]
    index = sym.index_by_name(table)
    for found in (sym.find_by_name(table, "showcredits"),
                  sym.find_by_name(table, "SHOWCREDITS", index)):
        assert [s.name for s in found] == ["ShowCredits"]
    assert [s.name for s in sym.find_by_name(table, "showcredits", index)] == ["ShowCredits"]
    assert len(sym.find_by_name(table, "showcr")) == 2
    assert len(sym.find_by_name(table, "SHOWCR", index)) == 2
    assert sym.find_by_name(table, "showcreditz", index) == []


def test_a_table_where_two_spellings_fold_to_one_is_refused_naming_both_lines() -> None:
    text = "00000100 T ShowCredits\n00000200 T other\n00000300 T showcredits\n"
    table = sym.parse_nm(text)
    with pytest.raises(sym.BadSymbolText) as caught:
        sym.check_folded(table, text)
    said = str(caught.value)
    assert "'ShowCredits' (line 1)" in said and "'showcredits' (line 3)" in said, said


def test_a_name_defined_twice_in_one_spelling_is_ambiguity_and_not_a_fold_clash() -> None:
    text = "00000100 T helper\n00000200 T helper\n00000300 T Other\n"
    sym.check_folded(sym.parse_nm(text), text)


def test_an_address_resolves_to_the_nearest_symbol_below_it_with_the_distance() -> None:
    """The table carries no sizes, so the delta is reported rather than judged."""
    table = sym.parse_nm(NM_FRAGMENT)
    found = sym.find_by_offset(table, 0x0016DF24)
    assert found is not None
    best, delta = found
    assert (best.name, delta) == ("_main", 4)


def test_two_symbols_at_one_offset_resolve_to_the_first_row_of_the_table(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Both lookups by address agree with the other server: the file's order decides a tie."""
    from scry_dosbox_x import placement
    from scry_dosbox_x import state as dstate
    table = [sym.Symbol("_zeta", 0x1000), sym.Symbol("_alpha", 0x1000), sym.Symbol("_next", 0x2000)]
    found = sym.find_by_offset(table, 0x1004)
    assert found is not None and found[0].name == "_zeta"
    monkeypatch.setattr(dstate.STATE, "table", table)
    monkeypatch.setattr(dstate.STATE, "table_generation", -9)
    monkeypatch.setattr(dstate.STATE, "base", {"base": 0})
    assert placement._nearest_offset(0x1004, sym.FLAT)["name"] == "_zeta"


def test_an_address_below_every_symbol_is_none_and_not_the_lowest_one() -> None:
    table = [sym.Symbol("_x", 0x1000)]
    assert sym.find_by_offset(table, 0x10) is None


def test_the_size_a_real_program_produces_encodes_and_decodes_intact() -> None:
    many = [sym.Symbol(f"_sym_{i:05d}", 0x1000 + i * 4) for i in range(7238)]
    data = sym.encode(sym.plan(many), MEASURED_BASE)
    assert len(data) == 2 + 20 * 7238 == 144762
    assert struct.unpack_from("<H", data, 0)[0] == 7238
    assert len(sym.decode(data)) == 7238


def test_a_line_the_parser_cannot_read_is_counted_and_not_dropped() -> None:
    """`nm -C` names hold spaces and match nothing: the line is counted as unreadable."""
    text = "0016df20 T _main\n0016df30 T Foo::bar(int, char)\n"
    syms, unreadable = sym.parse(text)
    assert [s.name for s in syms] == ["_main"]
    assert unreadable == 1, "the C++ line matched nothing and has to be counted"
    assert sym.plan(syms, unreadable=unreadable).unreadable == 1
    assert sym.parse("0016df20 T _main\n\n   \n")[1] == 0


def test_nothing_surviving_the_filters_is_refused_not_an_empty_file() -> None:
    syms = sym.parse_nm(NM_FRAGMENT)
    with pytest.raises(sym.BadSymbolText, match="nothing survived the filters"):
        sym.plan(syms, pattern="^_no_such_prefix")
    assert sym.plan(syms, pattern="^_main$").kept == 1


def test_a_nul_inside_a_name_cannot_put_two_addresses_under_one_name() -> None:
    """The debugger cuts a name at the first NUL, so `str` distinctness is not enough."""
    p = sym.plan([sym.Symbol("_a\x00b", 1), sym.Symbol("_a\x00c", 2),
                  sym.Symbol("_ok", 3)])
    assert p.kept == 1 and len(p.unencodable) == 2
    names = [n for n, _ in sym.decode(sym.encode(sym.plan(
        [sym.Symbol("_a", 1), sym.Symbol("_b", 2)]), 0))]
    assert len(set(names)) == len(names)


def test_an_empty_name_and_a_control_byte_are_refused() -> None:
    p = sym.plan([sym.Symbol("", 1), sym.Symbol("_a\tb", 2), sym.Symbol("_ok", 3)])
    assert p.kept == 1 and p.short == ["_ok"]
    assert p.unencodable == ["", "_a\tb"]


def test_a_negative_offset_and_an_oversized_base_are_refused() -> None:
    """Checking only the sum lets the two errors cancel."""
    with pytest.raises(sym.BadSymbolText, match="not negative"):
        sym.encode(sym.plan([sym.Symbol("_x", -0x1000)]), MEASURED_BASE)
    with pytest.raises(sym.BadSymbolText, match="not a 32-bit linear base"):
        sym.encode(sym.plan([sym.Symbol("_y", 1)]), 0x100000000)
    assert len(sym.encode(sym.plan([sym.Symbol("_z", 0)]), 0)) == 2 + sym.RECORD
    assert len(sym.encode(sym.plan([sym.Symbol("_z", 0)]), sym.ADDR_MAX)) == 2 + sym.RECORD


def test_a_generated_name_never_takes_a_real_name_that_fits_and_is_unique() -> None:
    names = ["abcdefghijklmXY1", "abcdefghijklmXY2", "abcdefghijklm~0"]
    short, _, _ = sym._disambiguate(names)
    assert short[2] == "abcdefghijklm~0", "the real name has to reach its own symbol"
    assert len(set(short)) == 3
    assert short[0] == "abcdefghijklmXY"


def test_renamed_counts_the_names_that_are_not_the_symbols_own() -> None:
    p = sym.plan(sym.parse_nm(REPEATED_FULL_NAME))
    assert p.truncated_names == 0, "every one of these fits: that is the point"
    assert p.renamed == 2 and p.disambiguated == 2
    q = sym.plan([sym.Symbol("_a_name_far_too_long_to_fit", 1)])
    assert q.truncated_names == 1 and q.renamed == 1


def test_decode_refuses_a_byte_no_name_of_ours_could_hold() -> None:
    data = struct.pack("<H", 1) + b"\xff_x" + b"\0" * 13 + struct.pack("<I", 0)
    with pytest.raises(sym.BadSymbolText, match="no name of ours can contain"):
        sym.decode(data)


def test_the_dead_duplicate_of_the_filename_limit_is_gone() -> None:
    assert not hasattr(sym, "NAME_ON_DISK_MAX")


def test_a_value_that_is_not_an_address_is_excluded_and_counted() -> None:
    """`nm` prints a COMMON symbol's size and an ABSOLUTE one's constant as the address."""
    text = ("00004000 C _big_table\n"
            "00000100 C _other_common\n"
            "000003f8 A _PORT\n"
            "00000000 D _initialised\n"
            "0016df20 T _main\n")
    p = sym.plan(sym.parse_nm(text))
    assert p.excluded_unplaceable == 3, p
    assert [s.name for s in p.symbols] == ["_initialised", "_main"], p.symbols
    p.check()
    assert p.parsed == p.kept + p.excluded_unplaceable + p.excluded_noise


def test_a_linked_program_loses_no_symbol_to_the_unplaceable_filter() -> None:
    """The control: a linked binary has no `C` or `A`, so the filter eats nothing real."""
    linked = "\n".join([
        "0016df20 T _main", "0005c830 T _engine_load_midi", "002308b8 b .bss",
        "00239000 B _some_global", "0013a020 t .text", "00230000 d .data",
    ]) + "\n"
    p = sym.plan(sym.parse_nm(linked))
    assert p.excluded_unplaceable == 0, p
    assert p.kept == 3, p
    assert p.excluded_noise == 3, p


# Authored in a real TLINK map's shape (map not kept); the real one is
# tests/fixtures/borland-tlink16/MAPDEMO.MAP. The segment table rows also open with `seg:off`.
TLINK_MAP = (
    "\r\n"
    " Start  Stop   Length Name               Class\r\n"
    "\r\n"
    " 00000H 0ACD7H 0ACD8H _TEXT              CODE\r\n"
    "\r\n"
    "Detailed map of segments\r\n"
    "\r\n"
    " 0000:0000 0036 C=CODE   S=SFMAIN_TEXT    G=(none)  M=SFMAIN.ASM ACBP=48\r\n"
    " 0003:0006 0000 C=CODE   S=SFLOG_TEXT     G=(none)  M=SFLOG.C    ACBP=28\r\n"
    "\r\n"
    "  Address         Publics by Name\r\n"
    "\r\n"
    " 0D74:00E21 idle  ACTIVEIMAN\r\n"
    " 0459:00123       ACTIVE_CLS\r\n"
    " 1247:0DFEB       ANIMPLANE\r\n"
    "\r\n"
    "  Address         Publics by Value\r\n"
    "\r\n"
    " 0459:00123       ACTIVE_CLS\r\n"
    " 0D74:00E21 idle  ACTIVEIMAN\r\n"
    " 1247:0DFEB       ANIMPLANE\r\n"
    "\r\n"
    "Program entry point at 0000:0000\r\n")


def test_a_borland_map_is_read_and_its_segment_table_is_not_mistaken_for_symbols() -> None:
    """The anchor is the section header: segment-table rows also open with `seg:off`."""
    got, unreadable = sym.parse(TLINK_MAP)
    names = [s.name for s in got]
    assert names == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], names
    assert unreadable == 0
    assert not [n for n in names if "=" in n], f"the segment table leaked in: {names}"


def test_a_borland_address_is_folded_the_way_the_debugger_folds_it() -> None:
    at = {s.name: s.offset for s in sym.parse_tlink(TLINK_MAP)[0]}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21 == 0xE561
    assert at["ANIMPLANE"] == 0x1247 * 16 + 0x0DFEB == 0x2045B
    assert 0x0DFEB <= 0xFFFF


def test_the_two_publics_sections_are_one_set_and_not_two() -> None:
    """TLINK prints the publics twice; without de-duplicating, each collides with itself."""
    p = sym.plan(sym.parse_tlink(TLINK_MAP)[0])
    assert p.parsed == 3, p
    assert p.disambiguated == 0, "the same symbol twice was read as two"
    assert sorted(p.short) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"]


def test_two_different_symbols_sharing_a_name_still_survive_as_two() -> None:
    doubled = TLINK_MAP.replace(" 1247:0DFEB       ANIMPLANE\r\n",
                                " 1247:0DFEB       ANIMPLANE\r\n"
                                " 2000:00001       ANIMPLANE\r\n")
    got, _ = sym.parse_tlink(doubled)
    assert [s.name for s in got].count("ANIMPLANE") == 2, got


def test_a_borland_map_with_no_publics_says_so_instead_of_blaming_the_file() -> None:
    """A link with no publics is a statement about the link, not about the file."""
    segments_only = TLINK_MAP.split("  Address")[0]
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(segments_only)


def test_nm_and_gnu_maps_are_still_routed_to_their_own_parsers() -> None:
    assert not sym.looks_like_tlink(NM_FRAGMENT)
    assert len(sym.parse(NM_FRAGMENT)[0]) == 10
    gnu = ("                0x000000000016df20                _main\n"
           "                0x000000000005c830                _engine_load_midi\n")
    assert not sym.looks_like_tlink(gnu)
    assert [s.name for s in sym.parse(gnu)[0]] == ["_main", "_engine_load_midi"]


def test_a_c_symbol_table_survives_the_round_trip_with_its_case_intact() -> None:
    """Bytes captured through `LV`/`SV`; `IV` uppercases and truncates, so it cannot answer."""
    got = sym.decode(REAL_THREE_LOWER)
    assert got == [("_main", 0x000179B8),
                   ("_engine_load_mi", 0x00000870),
                   ("_poly_scanline_", 0x000A001F)]
    syms = [sym.Symbol("_main", 0x000179B8), sym.Symbol("_engine_load_midi", 0x00000870),
            sym.Symbol("_poly_scanline_gcol8", 0x000A001F)]
    assert sym.encode(sym.plan(syms), base=0) == REAL_THREE_LOWER
    assert any(c.islower() for n, _ in got for c in n)
    assert not any(c.islower() for n, _ in sym.decode(REAL_THREE) for c in n)


def test_a_row_the_reader_cannot_parse_does_not_take_the_rest_of_the_section_with_it()\
        -> None:
    """A `break` at the first unreadable row amputates the section with `unreadable` at 0."""
    amputated = TLINK_MAP.replace(
        " 1247:0DFEB       ANIMPLANE\r\n",
        " 0D74:000E21      SIXDIGITS\r\n 1247:0DFEB       ANIMPLANE\r\n")
    got, unreadable = sym.parse(amputated)
    names = [s.name for s in got]
    assert "ANIMPLANE" in names, f"the section was amputated: {names}"
    assert sorted(names) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], names
    assert unreadable == 2, unreadable


def test_a_publics_section_this_reader_cannot_parse_is_not_called_empty() -> None:
    """An empty section is about the link; unreadable rows are about the reader."""
    unknown = ("  Address         Publics by Name\r\n"
               "\r\n"
               " 0001:0BE       _main\r\n"
               " 0001:0C4       _engine_load\r\n")
    with pytest.raises(sym.BadSymbolText, match="could not be placed"):
        sym.parse(unknown)
    empty = "  Address         Publics by Name\r\n\r\nProgram entry point at 0000:0000\r\n"
    with pytest.raises(sym.BadSymbolText, match="no line under it that starts like"):
        sym.parse(empty)


def test_an_offset_wider_than_sixteen_bits_is_not_folded_into_an_address() -> None:
    """Five digits are this linker's padding, not a wider field: `1FFFF` would invent an address."""
    got, unreadable = sym.parse_tlink(
        "  Address         Publics by Name\n"
        "\n"
        " 0459:00123       GOOD_ONE\n"
        " 0459:1FFFF       FOO\n"
        " 0459:00456       GOOD_TWO\n")
    assert [s.name for s in got] == ["GOOD_ONE", "GOOD_TWO"], got
    assert unreadable == 1, unreadable


def test_the_sniff_and_the_walk_ask_the_same_question() -> None:
    """`\\s` matches a newline, so the header sniff must not span two lines."""
    across = "Address\nPublics by Name\n"
    assert not sym.looks_like_tlink(across), "the sniff still spans a newline"
    assert not sym._TLINK_SEGMENTS.search("Start\nStop\nLength\nName\nClass\n")
    assert sym.looks_like_tlink("  Address         Publics by Name\r\n")


def test_a_section_header_carrying_a_trailing_token_is_still_a_section_header() -> None:
    annotated = (TLINK_MAP.replace("Publics by Name", "Publics by Name   (overlay 1)")
                          .replace("Publics by Value", "Publics by Value   (overlay 1)"))
    got, _ = sym.parse(annotated)
    assert [s.name for s in got] == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], got


def test_a_borland_public_does_not_claim_to_be_code() -> None:
    got, _ = sym.parse_tlink(TLINK_MAP)
    assert {s.kind for s in got} == {"?"}, got


def test_the_letters_whose_value_is_not_an_address_are_the_measured_ones() -> None:
    """Pins the set in both directions, so widening it cannot stay green."""
    assert set(sym._UNPLACEABLE) == set("CAaN"), sym._UNPLACEABLE
    assert not set("TtDdBbRrWVwv") & set(sym._UNPLACEABLE)


def test_a_local_absolute_and_a_debug_symbol_are_not_placed_either() -> None:
    p = sym.plan(sym.parse_nm("000003f8 a _localport\n0016df20 T _main\n"))
    assert p.excluded_unplaceable == 1, p
    assert [s.name for s in p.symbols] == ["_main"], p.symbols

    real = ("00002210 N .comment\n00000000 a .absolut\n0016df20 T _main\n")
    kept = sym.plan(sym.parse_nm(real), keep_noise=True)
    assert kept.excluded_unplaceable == 2, kept
    assert [s.name for s in kept.symbols] == ["_main"], kept.symbols


def test_two_names_at_one_address_both_survive() -> None:
    """The de-duplication key is `(name, offset)`; the offset half needs its own control."""
    aliased = TLINK_MAP.replace(
        " 1247:0DFEB       ANIMPLANE\r\n",
        " 1247:0DFEB       ANIMPLANE\r\n 1247:0DFEB       _animplane\r\n")
    got, _ = sym.parse_tlink(aliased)
    at = [s.name for s in got if s.offset == 0x1247 * 16 + 0x0DFEB]
    assert sorted(at) == ["ANIMPLANE", "_animplane"], got


def test_an_empty_selection_is_refused_by_the_guard_and_not_by_check() -> None:
    """`check()` is vacuous on an empty selection; the refusal is `plan()`'s own guard."""
    empty = sym.Plan(parsed=2)
    empty.excluded_unplaceable = 2
    empty.check()

    with pytest.raises(sym.BadSymbolText, match="nothing survived the filters") as e:
        sym.plan(sym.parse_nm("00004000 C _big\n000003f8 A _PORT\n"))
    assert "2 whose value is not an address" in str(e.value), str(e.value)


def test_an_overlay_symbol_is_placed_and_the_flag_travels_with_it() -> None:
    """A placed `idle` symbol must say so on the symbol itself, not only in a counter."""
    got, _ = sym.parse_tlink(TLINK_MAP)
    flagged = {s.name: s.idle for s in got}
    assert flagged == {"ACTIVEIMAN": True, "ACTIVE_CLS": False, "ANIMPLANE": False}, got
    at = {s.name: s.offset for s in got}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21, at


def test_the_name_of_a_flagged_row_is_the_name_and_not_the_flag() -> None:
    got, _ = sym.parse_tlink(TLINK_MAP)
    assert "idle" not in [s.name for s in got], got
    assert sorted(s.name for s in got) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], got


def test_the_overlay_symbols_are_counted_and_do_not_break_the_accounting() -> None:
    """`overlay_idle` is a subset of `kept`, not a bucket beside it."""
    p = sym.plan(sym.parse_tlink(TLINK_MAP)[0])
    assert p.overlay_idle == 1, p
    assert p.kept == 3, p
    assert (p.kept + p.excluded_noise + p.excluded_pattern + p.excluded_unplaceable
            + len(p.unencodable)) == p.parsed == 3, p
    p.check()


def test_the_overlay_count_describes_the_table_and_not_the_file() -> None:
    """Counts over what survived the filters."""
    narrowed = sym.plan(sym.parse_tlink(TLINK_MAP)[0], pattern="^ANIM")
    assert narrowed.kept == 1, narrowed
    assert narrowed.overlay_idle == 0, narrowed
    kept = sym.plan(sym.parse_tlink(TLINK_MAP)[0], pattern="^ACTIVEI")
    assert kept.kept == 1 and kept.overlay_idle == 1, kept


def test_nm_and_gnu_symbols_are_not_flagged_idle() -> None:
    assert not any(s.idle for s in sym.parse_nm(NM_FRAGMENT))
    gnu = ("                0x000000000016df20                _main\n"
           "                0x000000000005c830                _engine_load_midi\n")
    assert not any(s.idle for s in sym.parse(gnu)[0])
    assert sym.plan(sym.parse_nm(NM_FRAGMENT)).overlay_idle == 0


ILINK32_MAP = (Path(__file__).parent / "fixtures" / "borland-ilink32" / "sections32.map"
               ).read_bytes().decode("latin-1")

# Distinct on purpose: with one shared base a reader ignoring the section index passes.
ILINK32_BASES = {1: 0x401000, 2: 0x423000, 3: 0x4289B8}

def _declared_sections(text: str) -> dict[int, int]:
    """index -> furthest extent its segments reach, read independently of the parser."""
    rx = re.compile(r"^ ([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}) ([0-9A-Fa-f]+)[Hh] ", re.M)
    out: dict[int, int] = {}
    for i, start, ln in rx.findall(text):
        out[int(i, 16)] = max(out.get(int(i, 16), 0), int(start, 16) + int(ln, 16))
    assert out, "the fixture's section table did not parse: this oracle read nothing"
    return out


def test_a_32_bit_row_keeps_its_section_and_is_placed_by_the_callers_table() -> None:
    """Every `Start` offset in a real ILINK32 map is zero: placement comes from the caller."""
    got, unreadable = sym.parse(ILINK32_MAP)
    assert unreadable == 0, unreadable
    assert len(got) == 4, got
    kept = {s.name: (s.section, s.offset) for s in got}
    assert kept == {"_main": (1, 0x00000130), "_errno": (2, 0x00002090),
                    "_g_count": (2, 0x000022D4), "___xxInfo": (3, 0x00000000)}, kept
    placed = dict(sym.decode(sym.encode(sym.plan(got),
                                        section_bases=ILINK32_BASES)))
    assert placed == {"_main": 0x00401130, "_errno": 0x00425090,
                      "_g_count": 0x004252D4, "___xxInfo": 0x004289B8}, placed


def test_every_offset_lands_inside_the_length_its_own_section_declared() -> None:
    """Checked against the LENGTH column, which the parser never reads."""
    declared = _declared_sections(ILINK32_MAP)
    syms = sym.parse_tlink(ILINK32_MAP)[0]
    assert len(syms) == 4, syms
    for one in syms:
        assert one.section in declared, f"{one.name} names section {one.section}"
        extent = declared[one.section]
        assert 0 <= one.offset < extent, (
            f"{one.name} at {one.offset:#x} is outside its own section's "
            f"{extent:#x} bytes")
    assert {one.section for one in syms} == set(declared), declared


def test_the_detailed_map_row_is_not_taken_for_a_section() -> None:
    """`Detailed map of segments` rows also open with `sect:offset`."""
    sections = sym._tlink_sections(ILINK32_MAP.splitlines())
    assert sorted(sections) == [1, 2, 3], sections
    assert "Detailed map of segments" in ILINK32_MAP
    assert " 0001:00000108 0000004B C=CODE" in ILINK32_MAP

    inline = [" Start         Length     Name               Class",
              "",
              " 0001:00000108 0000004B C=CODE    S=_TEXT    G=(none)   M=HELLO32.C  ACBP=A9"]
    assert sym._tlink_sections(inline) == {}, sym._tlink_sections(inline)


def test_the_section_table_is_only_read_under_its_own_header() -> None:
    loose = [" 0001:00401000 0000214D4H _TEXT              CODE",
             " 0002:00423000 0000059B8H _DATA              DATA"]
    assert sym._tlink_sections(loose) == {}, sym._tlink_sections(loose)
    assert sym._tlink_sections([" Start         Length     Name               Class",
                                "", *loose]) == {1: 0x00401000, 2: 0x00423000}


def test_the_two_row_shapes_cannot_claim_the_same_row() -> None:
    """The order the two patterns are tried in is safe because the offset widths do not overlap."""
    real_mode = " 0D74:00E21 idle  ACTIVEIMAN"
    flat = " 0001:00000130       _main"
    assert sym._TLINK_ROW.match(real_mode) and not sym._TLINK_ROW32.match(real_mode)
    assert sym._TLINK_ROW32.match(flat) and not sym._TLINK_ROW.match(flat)


def test_a_section_the_caller_did_not_position_is_refused_and_never_placed_at_zero() -> None:
    """The refusal belongs to placing, so it can name the unpositioned section."""
    orphan = ILINK32_MAP.replace(" 0002:00002090       _errno\r\n",
                                 " 0002:00002090       _errno\r\n"
                                 " 0009:00000100       _nowhere\r\n", 1)
    assert orphan.count("_nowhere") == 1, "the substitution matched nothing"
    got, unreadable = sym.parse(orphan)
    assert unreadable == 0, unreadable
    assert sorted(s.name for s in got) == ["___xxInfo", "_errno", "_g_count", "_main",
                                           "_nowhere"], got
    with pytest.raises(sym.BadSymbolText, match="section 9") as e:
        sym.encode(sym.plan(got), section_bases=ILINK32_BASES)
    assert "_nowhere" in str(e.value), str(e.value)


def test_a_32_bit_map_with_no_section_table_still_reads_and_still_needs_its_bases() -> None:
    wide = ("  Address         Publics by Name\r\n"
            "\r\n"
            " 0001:00000BE0       _main\r\n")
    got, unreadable = sym.parse(wide)
    assert [(s.name, s.section, s.offset) for s in got] == [("_main", 1, 0xBE0)], got
    assert unreadable == 0, unreadable
    with pytest.raises(sym.BadSymbolText, match="section 1"):
        sym.encode(sym.plan(got), section_bases={2: 0x400000})
    with pytest.raises(sym.BadSymbolText, match="section 1"):
        sym.encode(sym.plan(got), 0x400000)


def test_the_16_bit_path_is_untouched_by_the_section_table() -> None:
    assert sym._tlink_sections(TLINK_MAP.splitlines()) == {}
    at = {s.name: s.offset for s in sym.parse_tlink(TLINK_MAP)[0]}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21
    assert at["ANIMPLANE"] == 0x1247 * 16 + 0x0DFEB
    assert len(at) == 3, at


def test_a_32_bit_map_that_printed_no_publics_says_so_too() -> None:
    segments_only = ILINK32_MAP.split("  Address")[0]
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(segments_only)


def test_a_32_bit_row_carries_the_mark_too_and_it_is_spelled_idle() -> None:
    """ILINK32 spells the mark `Idle`; a lowercase pattern would refuse every flagged row."""
    at = {s.name: s.idle for s in sym.parse_tlink(ILINK32_MAP)[0]}
    assert at == {"_main": False, "_errno": False, "_g_count": True, "___xxInfo": False}, at
    where = {s.name: (s.section, s.offset) for s in sym.parse_tlink(ILINK32_MAP)[0]}
    assert where["_g_count"] == (2, 0x000022D4), where
    lower = ILINK32_MAP.replace(" Idle _g_count", " idle _g_count")
    assert lower.count(" idle _g_count") == 2, "the substitution did not reach both tables"
    got, unreadable = sym.parse_tlink(lower)
    assert unreadable == 2, unreadable
    assert "_g_count" not in [s.name for s in got], got


def test_the_overlay_count_is_a_count_and_not_a_flag() -> None:
    """`== 1` accepts `True`, so this needs two flagged symbols."""
    two = TLINK_MAP.replace(" 0459:00123       ACTIVE_CLS\r\n",
                            " 0459:00123 idle  ACTIVE_CLS\r\n")
    p = sym.plan(sym.parse_tlink(two)[0])
    assert p.overlay_idle == 2, p
    assert not isinstance(p.overlay_idle, bool), type(p.overlay_idle)


def test_an_overlay_count_that_is_not_a_subset_of_kept_is_refused() -> None:
    p = sym.plan(sym.parse_nm("0016df20 T _main\n"))
    assert p.kept == 1 and p.overlay_idle == 0, p
    p.check()
    p.overlay_idle = 2
    with pytest.raises(sym.BadSymbolText, match="not a subset"):
        p.check()


def test_a_section_row_the_reader_cannot_parse_does_not_truncate_the_table() -> None:
    """The amputation again, in the section-table walk."""
    rows = [" Start         Length     Name               Class",
            "",
            " 0001:00401000 0000214D4H _TEXT              CODE",
            " 0004:00500000 00000010H _STACK",
            " 0002:00423000 0000059B8H _DATA              DATA"]
    got = sym._tlink_sections(rows)
    assert got == {1: 0x00401000, 2: 0x00423000}, got
    ended = sym._tlink_sections([*rows[:3], "Detailed map of segments",
                                 " 0002:00423000 0000059B8H _DATA              DATA"])
    assert ended == {1: 0x00401000}, ended


def test_only_the_first_section_table_is_read() -> None:
    h = " Start         Length     Name               Class"
    got = sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE",
                               "", h, "", " 0002:00800000 0000059B8H _DATA DATA"])
    assert got == {1: 0x00401000}, got


def test_a_repeated_section_index_keeps_the_row_that_came_first() -> None:
    h = " Start         Length     Name               Class"
    got = sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE",
                               " 0001:00800000 0000214D4H _TEXT CODE"])
    assert got == {1: 0x00401000}, got


def test_a_section_length_in_lowercase_hex_is_still_a_section() -> None:
    h = " Start         Length     Name               Class"
    assert sym._tlink_sections([h, "", " 0001:00401000 0000214d4h _TEXT CODE"]) \
        == {1: 0x00401000}
    assert sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE"]) \
        == {1: 0x00401000}


def test_a_short_offset_in_a_file_that_has_a_section_table_is_refused() -> None:
    """The mirror rule: a short row in a file with a section table is not `seg * 16 + off`."""
    assert sym._tlink_place(" 0001:00BE0       _main", True) is None
    assert sym._tlink_place(" 0001:00BE0       _main", False) == (
        "_main", sym.FLAT, 0x0BF0, False)


def test_an_nm_file_carrying_four_ordinary_words_is_not_a_borland_map() -> None:
    """`Start Length Name Class` alone is ordinary English; a section row must follow."""
    text = "0016df20 T _main\n Start   Length   Name   Class\n0005c830 T _engine_load\n"
    got, _ = sym.parse(text)
    assert [s.name for s in got] == ["_main", "_engine_load"], got
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(ILINK32_MAP.split("  Address")[0])


_WALK = sym.Anchored(header=re.compile(r"^HEAD$", re.M),
                     row_shaped=re.compile(r"^ROW"))


def _digits(row: str) -> int | None:
    """Readable is `ROW <number>`; other `ROW...` is unreadable; anything else ends the section."""
    return int(row[4:]) if row.startswith("ROW ") and row[4:].isdigit() else None


def test_the_walk_steps_over_an_unreadable_row_instead_of_ending_the_section() -> None:
    """Stepping over a bad row, not breaking, keeps truncation from reading as completeness."""
    lines = ["HEAD", "ROW 1", "ROW bad", "ROW 3", "ROW 4"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 3, 4], rows
    assert bad == ["ROW bad"], bad


def test_the_walk_counts_the_row_it_stepped_over_and_does_not_drop_it_in_silence() -> None:
    lines = ["HEAD", "ROW 1", "ROW x", "ROW y", "ROW 2"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 2], rows
    assert len(bad) == 2 and bad == ["ROW x", "ROW y"], bad


def test_a_line_that_is_not_row_shaped_ends_the_section_and_is_not_counted() -> None:
    lines = ["HEAD", "ROW 1", "Program entry point at 0000:0000", "ROW 2"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1], rows
    assert bad == [], bad


def test_a_blank_line_neither_ends_the_section_nor_counts_as_a_loss() -> None:
    lines = ["HEAD", "", "ROW 1", "", "ROW 2", ""]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 2], rows
    assert bad == [], bad


def test_the_walk_yields_one_result_per_section_and_does_not_merge_them() -> None:
    """The publics walk wants every section, the section-table walk only the first."""
    lines = ["HEAD", "ROW 1", "-", "HEAD", "ROW 2", "ROW bad"]
    got = list(sym._anchored_sections(lines, _WALK, _digits))
    assert [rows for rows, _ in got] == [[1], [2]], got
    assert [bad for _, bad in got] == [[], ["ROW bad"]], got


def test_the_walk_is_lazy_so_a_caller_that_wants_one_section_walks_only_that_one() -> None:
    seen: list[str] = []

    def watched(row: str) -> int | None:
        seen.append(row)
        return _digits(row)

    lines = ["HEAD", "ROW 1", "-", "HEAD", "ROW 2"]
    first = next(sym._anchored_sections(lines, _WALK, watched))
    assert first == ([1], []), first
    assert "ROW 2" not in seen, seen


def test_a_file_with_no_matching_header_yields_nothing_rather_than_an_empty_section() -> None:
    assert list(sym._anchored_sections(["ROW 1", "ROW 2"], _WALK, _digits)) == []


def test_two_unreadable_rows_in_one_section_are_counted_as_two_and_not_as_one() -> None:
    """The count is of rows, not sections."""
    two_bad = TLINK_MAP.replace(
        " 0459:00123       ACTIVE_CLS\r\n 1247:0DFEB       ANIMPLANE\r\n",
        " 0459:1FFFF       ACTIVE_CLS\r\n 1247:FFFFF       ANIMPLANE\r\n", 1)
    assert two_bad != TLINK_MAP, "the substitution matched nothing, so this tests nothing"
    report = sym.ParseReport()
    got, unreadable = sym.parse_tlink(two_bad, report)
    assert [s.name for s in got] == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], \
        [s.name for s in got]
    assert unreadable == 2, unreadable
    assert [r.strip() for r in report.unreadable_rows] == [
        "0459:1FFFF       ACTIVE_CLS", "1247:FFFFF       ANIMPLANE"], report.unreadable_rows


def test_a_watcom_section_with_no_readable_row_refuses_and_does_not_return_empty() -> None:
    """Calls the reader directly: through `parse` the refusal is unreachable."""
    header = ("                        +----------------+\r\n"
              "                        |   Memory Map   |\r\n"
              "                        +----------------+\r\n"
              "\r\n"
              "Address        Symbol\r\n"
              "=======        ======\r\n"
              "\r\n"
              "Module: NOTHING.OBJ\r\n")
    with pytest.raises(sym.BadSymbolText, match="Open Watcom"):
        sym.parse_watcom(header)


def test_the_dedupe_key_carries_the_section_in_both_sectioned_readers() -> None:
    """The same name at the same offset in different sections is two symbols."""
    watcom = ("Address        Symbol\r\n"
              "=======        ======\r\n"
              "Module: A.OBJ\r\n"
              "0001:00000010  twice_over\r\n"
              "0002:00000010  twice_over\r\n")
    got, unreadable = sym.parse_watcom(watcom)
    assert unreadable == 0, unreadable
    assert [(s.name, s.section, s.offset) for s in got] == [
        ("twice_over", 1, 0x10), ("twice_over", 2, 0x10)], got

    borland = ("  Address         Publics by Name\r\n"
               "\r\n"
               " 0001:00000010       twice_over\r\n"
               " 0002:00000010       twice_over\r\n")
    got2, _ = sym.parse_tlink(borland)
    assert [(s.name, s.section, s.offset) for s in got2] == [
        ("twice_over", 1, 0x10), ("twice_over", 2, 0x10)], got2

    twice, _ = sym.parse_watcom(watcom + "0001:00000010  twice_over\r\n")
    assert len(twice) == 2, twice


def test_a_section_most_of_which_was_discarded_is_refused_and_not_returned() -> None:
    """More rows lost than kept is refused, not returned as a clean table."""
    rows = "".join(f" 0001:0000{i:04X}  Idle _flagged{i}\r\n" for i in range(6))
    rows += "".join(f" 0001:0001{i:04X}       _plain{i}\r\n" for i in range(4))
    lower = rows.replace("Idle", "idle")
    with pytest.raises(sym.BadSymbolText, match="MORE WAS DISCARDED THAN KEPT") as e:
        sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + lower)
    assert "6 rows this could not read" in str(e.value), str(e.value)
    assert "only 4 it could" in str(e.value), str(e.value)

    got, unreadable = sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + rows)
    assert len(got) == 10 and unreadable == 0, (len(got), unreadable)


def test_a_minority_loss_is_still_returned_with_its_count_and_not_refused() -> None:
    rows = "".join(f" 0001:0000{i:04X}       _plain{i}\r\n" for i in range(9))
    rows += " 0459:1FFFF       _too_wide\r\n"
    got, unreadable = sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + rows)
    assert len(got) == 9, got
    assert unreadable == 1, unreadable


def test_the_ratio_does_not_bind_the_flat_readers_where_it_would_refuse_every_gnu_map() -> None:
    """A GNU `ld` map is mostly non-symbol lines, so the ratio applies to anchored readers only."""
    ld = ("Memory Configuration\r\n"
          "Name             Origin             Length\r\n"
          "*default*        0x00000000         0xffffffff\r\n"
          "Linker script and memory map\r\n"
          " .text          0x0001c2b0      0x1234\r\n"
          "                0x0001c2b0                _main\r\n"
          " *fill*         0x0001c2c0         0x4\r\n"
          "LOAD /some/archive.a\r\n")
    got, unreadable = sym.parse(ld)
    assert [s.name for s in got] == ["_main"], got
    assert unreadable > len(got), (unreadable, len(got))


def test_a_watcom_map_reads_through_parse_with_no_report_at_all() -> None:
    text = ("Address        Symbol\r\n"
            "=======        ======\r\n"
            "Module: A.OBJ\r\n"
            "0001:00000010s helper_\r\n"
            "0002:00000004+ _table\r\n")
    got, unreadable = sym.parse(text)
    assert [(s.name, s.section, s.kind) for s in got] == [
        ("helper_", 1, "s"), ("_table", 2, "?")], got
    assert unreadable == 0, unreadable


def test_a_name_that_fits_whole_is_never_given_to_a_different_symbol() -> None:
    """A whole name must not go to a longer name truncating onto it, in either order."""
    for order in (["abcdefghijklmnoXYZ", "abcdefghijklmno"],
                  ["abcdefghijklmno", "abcdefghijklmnoXYZ"]):
        got, _, _ = sym._disambiguate(order)
        short_at = order.index("abcdefghijklmno")
        assert got[short_at] == "abcdefghijklmno", (order, got)
        assert got[1 - short_at] != "abcdefghijklmno", (order, got)
        assert len(set(got)) == 2, got


def test_two_symbols_that_genuinely_share_a_whole_name_are_still_told_apart() -> None:
    got, _, disambiguated = sym._disambiguate(["_helper", "_helper", "_helper"])
    assert got[0] == "_helper", got
    assert len(set(got)) == 3, got
    assert disambiguated == 2, disambiguated


def test_find_by_offset_does_not_answer_out_of_a_different_section() -> None:
    """Nearest-symbol search is within one section, since sections overlap."""
    table = [sym.Symbol("_main", 0x10, section=1),
             sym.Symbol("_dataend", 0x20, section=2)]
    got = sym.find_by_offset(table, 0x100, 1)
    assert got is not None and got[0].name == "_main", got
    assert got[1] == 0xF0, got
    other = sym.find_by_offset(table, 0x100, 2)
    assert other is not None and other[0].name == "_dataend", other
    assert sym.find_by_offset(table, 0x100, 3) is None
    assert sym.find_by_offset(table, 0x100) is None


def test_a_parse_report_may_not_be_used_for_two_reads() -> None:
    """`unreadable_rows` appends while `fmt` is overwritten, so a reused report would lie."""
    text = ("  Address         Publics by Name\r\n"
            "\r\n"
            " 0459:00123       A\r\n"
            " 0459:00456       B\r\n"
            " 0459:1FFFF       C\r\n")
    report = sym.ParseReport()
    _, unreadable = sym.parse(text, report)
    assert unreadable == len(report.unreadable_rows) == 1, report.unreadable_rows
    with pytest.raises(sym.BadSymbolText, match="already been filled"):
        sym.parse(text, report)
    again = sym.ParseReport()
    _, u2 = sym.parse(text, again)
    assert u2 == len(again.unreadable_rows) == 1, again.unreadable_rows


def test_the_var_list_s_count_takes_its_edges() -> None:
    assert sym.decode(b"\0\0") == []
    with pytest.raises(sym.BadSymbolText):
        sym.decode(b"\0")
    full = struct.pack("<H", 0xFFFF)
    assert struct.unpack_from("<H", sym.joined(full, b"\0\0"))[0] == 0xFFFF
    with pytest.raises(sym.BadSymbolText):
        sym.joined(full, struct.pack("<H", 1))
