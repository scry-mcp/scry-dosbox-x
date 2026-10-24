"""The var-list converter, against bytes read out of the real debugger.

WHY A GOLDEN AND NOT A ROUND TRIP THROUGH THE MODULE'S OWN ENCODER: this format is
documented nowhere but in the debugger's source (`CDebugVar::SaveVars`); `README.debugger`
does not mention it, and neither does the doxygen. So the only thing that can say the
encoder is right is bytes that came OUT of DOSBox-X, and `REAL_THREE` below is exactly
that -- the bytes it wrote for three names typed at its console, transcribed from `xxd`.

An encoder tested only against its own decoder agrees with itself perfectly while both
are wrong, which is the whole failure mode here: there was no specification to be wrong
ABOUT until the file was opened.

`NM_FRAGMENT` is TRANSCRIBED from `i586-pc-msdosdjgpp-nm` output of a DJGPP program whose
binary is not kept, so nothing here can check it against its source and it stands as
authored to that shape. It is not a tidy sample -- it carries a 21-character name, a
three-way collision from a graphics library, duplicate section symbols and a compiler
label -- because those are the cases that decide the design. The real `nm` output this
suite does hold is `tests/fixtures/djgpp/` (with its PROVENANCE).
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

import dosbox_symbols as sym

# THE BYTES DOSBOX-X ITSELF WROTE, for:
#     IV 1234:5678 MYSYMBOL
#     IV 0:0 zero_lower          (stored uppercased: `IV` uppercases, the FILE does not)
#     IV A000:1F ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789   (stored as 15 characters)
# Transcribed from `xxd` of the file its `SV` produced.
REAL_THREE = bytes.fromhex(
    "0300"
    "4d59 5359 4d42 4f4c 0000 0000 0000 0000  b879 0100"
    "5a45 524f 5f4c 4f57 4552 0000 0000 0000  0000 0000"
    "4142 4344 4546 4748 494a 4b4c 4d4e 4f00  1f00 0a00"
    .replace(" ", ""))

# THE SECOND GOLDEN, and the one that carries the case this module actually loads.
#
# `REAL_THREE` above holds NO lowercase letter -- `IV` uppercases what is typed at it,
# so `zero_lower` was stored `ZERO_LOWER` -- while every name in `NM_FRAGMENT`
# below is lowercase, because that is what a C toolchain emits. So the property this
# whole module rests on, that a C symbol table survives the round trip, needs bytes of
# its own that run on every commit.
#
# CAPTURED by the round trip the module PERFORMS: a binary written, `LV` of it, `SV` of the
# list, and the bytes read back off disk (tests/fixtures/symbols-lv/PROVENANCE.txt).
#
# THE CAPTURE GOES THROUGH `LV`, NOT `IV`: typed with `IV` the names come back `_MAIN`,
# `_ENGINE_LOAD_MI` and `_POLY_SCANLINE` -- uppercased and truncated -- which would say a C
# table cannot survive at all. `IV` is the TYPING path; `LV` is the LOADING one, and the
# module only ever uses the second.
REAL_THREE_LOWER = (Path(__file__).parent / "fixtures" / "symbols-lv" / "three-lower.bin"
                    ).read_bytes()

# `nm` lines in that program's shape (see the module docstring: transcribed, source not kept).
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

# A DJGPP program's flat base under CWSDPMI, as `SELINFO CS` reads it
# (`CS: b:00400000 ... l:0023FFFF`); any plausible base serves these cases.
MEASURED_BASE = 0x00400000


# ------------------------------------------------------- the format, against the real bytes

def test_the_three_records_the_debugger_wrote_decode_to_what_was_typed() -> None:
    """The address is LINEAR, which is the fact the whole design rests on.

    `1234:5678` was TYPED and `0x000179B8` was STORED, and `0x12340 + 0x5678` is
    `0x179B8`. Had this been the seg:off that was typed, a toolchain's flat offsets
    could never have been placed at all.
    """
    got = sym.decode(REAL_THREE)
    assert got == [("MYSYMBOL", 0x000179B8),
                   ("ZERO_LOWER", 0x00000000),
                   ("ABCDEFGHIJKLMNO", 0x000A001F)]
    # The arithmetic spelled out, so a reader does not have to take the hex on trust.
    assert 0x1234 * 16 + 0x5678 == 0x000179B8
    assert 0xA000 * 16 + 0x1F == 0x000A001F


def test_encoding_those_same_three_reproduces_the_debuggers_bytes_exactly() -> None:
    """The encoder against the emulator's own output, byte for byte.

    This is the assertion that cannot be satisfied by agreeing with myself: the right
    hand side was produced by DOSBox-X.
    """
    syms = [sym.Symbol("MYSYMBOL", 0x000179B8),
            sym.Symbol("ZERO_LOWER", 0x00000000),
            sym.Symbol("ABCDEFGHIJKLMNO", 0x000A001F)]
    assert sym.encode(sym.plan(syms), base=0) == REAL_THREE


def test_a_record_is_twenty_bytes_and_the_header_is_two() -> None:
    """62 bytes for three records, from the real file. A layout drifting by one byte
    still decodes plausibly for a while, so the size is pinned independently."""
    assert len(REAL_THREE) == 2 + 3 * 20
    assert sym.RECORD == 20
    assert sym.NAME_MAX == 15


# ------------------------------------------------------------------------ parsing

def test_nm_lines_parse_to_offsets_and_kinds() -> None:
    got = {s.name: s for s in sym.parse_nm(NM_FRAGMENT)}
    assert got["_main"].offset == 0x0016DF20
    assert got["_main"].kind == "T"
    assert got[".bss"].kind == "b"
    assert len(sym.parse_nm(NM_FRAGMENT)) == 10


def test_an_undefined_symbol_carries_no_address_and_is_not_one() -> None:
    """`nm` prints `                 U _printf` for an import. It has no address, so it
    cannot be named at one, and a table that invented 0 for it would put a name on
    whatever occupies the bottom of the program.

    THE POPULATION IS ASSERTED BESIDE THE EXCLUSION, because the exclusion alone proves
    nothing: `assert all(s.name != "_some_import" for s in parse_nm(text))` is vacuously
    True over an empty list, so the case that exists to prove ONE symbol is excluded
    passes over a parser that excludes EVERY symbol. A `parse_nm` reduced to `return []`
    reddens every other case that calls it and would leave this one green, the only
    survivor.
    """
    text = NM_FRAGMENT + "                 U _some_import\n"
    got = sym.parse_nm(text)
    # THE EXCLUSION IS ONE SYMBOL AND NOT THE WHOLE TABLE: the fragment's own ten
    # survive, the undefined one does not, and the count is what tells those apart.
    assert len(got) == len(sym.parse_nm(NM_FRAGMENT)) == 10, got
    assert all(s.name != "_some_import" for s in got)
    assert any(s.name == "_main" for s in got), (
        "the fragment's own symbols are gone too: this is a parser that excluded "
        "everything, not one that excluded the undefined symbol")


def test_text_that_is_not_a_symbol_list_is_an_error_and_not_an_empty_list() -> None:
    """Zero recognised lines and a program with no symbols are different facts.

    Returning `[]` for both is the instrument that examined nothing reporting a clean
    result, which is the failure this package is written against.
    """
    with pytest.raises(sym.BadSymbolText, match="nothing to load"):
        sym.parse_nm("Makefile:12: warning: overriding recipe for target 'all'\n")


def test_a_link_map_parses_and_is_told_apart_from_nm_by_content() -> None:
    """GNU `ld --print-map` shape. The sniff is on CONTENT because a build writing `nm`
    output into a file called `.map` is an ordinary thing, and choosing by filename
    means the wrong parser runs and then blames the file."""
    mapped = ("                0x000000000016df20                _main\n"
              "                0x000000000005c830                _engine_load_midi\n")
    assert sym.looks_like_map(mapped)
    assert not sym.looks_like_map(NM_FRAGMENT)
    got = sym.parse_map(mapped)
    assert [(s.name, s.offset) for s in got] == [("_main", 0x16DF20),
                                                 ("_engine_load_midi", 0x5C830)]


# ------------------------------------------------------- what the 15-character field forces

def test_a_collision_keeps_every_member_instead_of_dropping_the_losers() -> None:
    """The three `__poly_scanline_*` names share their first fifteen characters.

    Truncating and keeping the first winner is the obvious design and it silently
    discards a large share of a real binary's symbols -- concentrated in exactly the
    generated inner loops where landing on an unnamed address is likeliest. So all
    three survive, distinctly, and the plan SAYS how many it had to rename.
    """
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    poly = [n for n in p.short if n.startswith("__poly")]
    assert len(poly) == 3
    assert len(set(poly)) == 3, f"two symbols collapsed onto one name: {poly}"
    assert all(len(n) <= sym.NAME_MAX for n in p.short)
    assert p.disambiguated == 2
    assert p.truncated_names == 4  # the three poly names and `_engine_load_midi` (17)


# ------------------------------------------------- distinctness, the central guarantee

# THESE THREE FIXTURES ARE THE CASES THAT DECIDE THE DESIGN, and none of them is in
# `NM_FRAGMENT`, which carries a three-way collision inside ONE group, the easy case: a
# reader can pass it and still hand one symbol's name to another.
TWO_GROUPS_ONE_STEM = ("00001000 T _blender_black_a\n"      # -> _blender_blac..
                       "00002000 T _blender_black_b\n"
                       "00003000 T _blender_blackXa\n"      # ...and so does this one
                       "00004000 T _blender_blackXb\n")

REPEATED_FULL_NAME = ("00001000 t _static_helper\n"          # `nm` really does this:
                      "00002000 t _static_helper\n"          # hundreds of names appear
                      "00003000 t _static_helper\n")         # more than once in a binary


def test_no_two_symbols_are_ever_given_the_same_name() -> None:
    """THE CENTRAL GUARANTEE, over every fixture at once.

    Enforced within a group of identical 15-character prefixes and nowhere else, it fails
    across groups: a large share of a real binary's symbols would carry a name belonging
    to a different symbol, while `disambiguated` reported the job done.
    """
    for name, text in (("fragment", NM_FRAGMENT),
                       ("two groups one stem", TWO_GROUPS_ONE_STEM),
                       ("repeated full name", REPEATED_FULL_NAME)):
        p = sym.plan(sym.parse_nm(text))
        assert len(set(p.short)) == len(p.short), (
            f"{name}: {len(p.short) - len(set(p.short))} of {len(p.short)} symbols "
            f"share a name with another: {p.short}")
        assert len(p.short) == len(p.symbols), f"{name}: the lists are not parallel"


def test_two_groups_that_shorten_to_one_stem_do_not_both_start_at_zero() -> None:
    """Cause one of the two, isolated. Numbering within a group cannot see that another
    group shortened onto the same stem: `__accel_bank_stub` and `__accel_bank_switch`
    both became `__accel_bank_~0` on the real binary -- two different functions at two
    different addresses under one name."""
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    assert len(set(p.short)) == 4, p.short


def test_a_name_nm_emits_more_than_once_yields_that_many_distinct_names() -> None:
    """Cause two. `nm` prints hundreds of names more than once in a real binary, e.g.
    several distinct addresses all called
    `___FSEXT_call_open_handlers_wrapper.constprop.0`. A mapping keyed on the NAME
    keeps the last of each and gives every one of them that same name."""
    p = sym.plan(sym.parse_nm(REPEATED_FULL_NAME))
    assert len(p.short) == 3
    assert len(set(p.short)) == 3, p.short
    assert [s.offset for s in p.symbols] == [0x1000, 0x2000, 0x3000]


def test_a_symbol_whose_real_name_contains_a_tilde_does_not_collide_with_a_made_one() -> None:
    """Cause three, and it is the reason the ledger has to be global rather than the
    suffix being reserved: nothing stops a toolchain emitting `abcdefghijklm~0`."""
    out, _, _ = sym._disambiguate(
        ["abcdefghijklm~0", "abcdefghijklmXY1", "abcdefghijklmXY2"])
    assert len(set(out)) == 3, out


def test_a_name_that_fits_is_not_touched() -> None:
    """The mirror of the cases above, and it is the one that stops "shorten everything"
    passing: a policy that mangled every name would satisfy every distinctness check."""
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    by = dict(zip([s.name for s in p.symbols], p.short, strict=True))
    assert by["_main"] == "_main"
    assert by["_engine_create"] == "_engine_create"      # exactly 14
    assert "~" not in by["_engine_create"]


def test_the_first_of_a_collision_keeps_its_plain_truncation() -> None:
    """A shortened name costs the reader something, so only the symbols that FORCE it
    pay. The first arrival keeps the plain 15-character form."""
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    assert p.short[0] == "_blender_black_a"[:sym.NAME_MAX]
    assert "~" not in p.short[0]


def test_the_emitted_names_are_a_pure_function_of_the_input_order() -> None:
    """A golden over this can only exist if the same text always gives the same file.

    It asserts the EMITTED LIST against a written-out expectation rather than comparing
    two calls in one process: `a == a` holds by construction for a pure function and
    would stay green over an implementation built on `set` iteration order, which is
    the only thing determinism here could plausibly be threatened by.
    """
    p = sym.plan(sym.parse_nm(TWO_GROUPS_ONE_STEM))
    # AND THE `~1` IS THE POINT: the second group's collision does not restart at zero,
    # because the ledger is global. Per-group numbering gave both groups `~0` here.
    assert p.short == ["_blender_black_", "_blender_blac~0",
                       "_blender_blackX", "_blender_blac~1"], p.short


def test_section_and_compiler_label_symbols_are_excluded_and_counted() -> None:
    """`.text` appears 558 times in the real output and `..@15.l0` is a compiler local.

    They are excluded by default because they would dominate the collision accounting
    and hide the real names, and they are COUNTED because a tool that quietly drops a
    third of its input is the thing this whole package refuses.
    """
    p = sym.plan(sym.parse_nm(NM_FRAGMENT))
    assert p.excluded_noise == 4                # ..@15.l0, .text, .text, .bss
    assert p.kept == 6
    assert all(not s.name.startswith(".") for s in p.symbols)
    back = sym.plan(sym.parse_nm(NM_FRAGMENT), keep_noise=True)
    assert back.excluded_noise == 0
    assert back.kept == 10


def test_every_parsed_symbol_lands_in_exactly_one_bucket() -> None:
    """The accounting is what a caller reads INSTEAD of the nine thousand names, so an
    accounting that does not sum to its population is a report about nothing."""
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="^_engine")
    assert p.parsed == 10
    assert p.kept + p.excluded_noise + p.excluded_pattern + len(p.unencodable) == 10
    assert p.kept == 2


def test_the_pattern_matches_the_full_name_not_the_shortened_one() -> None:
    """Filtering on the shortened form would make which symbols survive depend on which
    OTHER symbols happened to be present, since shortening is a property of the group.
    `_engine_load_midi` is 17 characters and must still be reachable by its real name."""
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="_engine_load_midi$")
    assert [s.name for s in p.symbols] == ["_engine_load_midi"]


def test_a_non_ascii_name_is_refused_rather_than_replaced() -> None:
    """The field is bytes. Encoding with `errors="replace"` would put a `?` in the
    debugger and call it a symbol -- a name that LIES, which is worse than a missing
    one."""
    p = sym.plan([sym.Symbol("_café", 0x10), sym.Symbol("_plain", 0x20)])
    assert p.unencodable == ["_café"]
    assert [s.name for s in p.symbols] == ["_plain"]


# ------------------------------------------------------------------------- the base

def test_the_base_is_added_to_every_offset() -> None:
    p = sym.plan(sym.parse_nm(NM_FRAGMENT), pattern="^_main$")
    got = sym.decode(sym.encode(p, MEASURED_BASE))
    assert got == [("_main", MEASURED_BASE + 0x0016DF20)]
    assert got[0][1] == 0x0056DF20      # what the live debugger was measured holding


def test_a_name_too_long_for_the_field_is_refused_rather_than_shifting_the_file() -> None:
    """`Plan.short` is public and mutable, and `encode` is the last place that can say
    no. Over-long, the pad becomes `b"" * negative` = empty, the record runs past twenty
    bytes and EVERY later record shifts -- a file that looks well formed and decodes to
    garbage, or to nothing if the total length happens to stay consistent."""
    p = sym.plan([sym.Symbol("_a", 0x10)])
    p.short = ["X" * 40]
    with pytest.raises(sym.BadSymbolText, match="past this record"):
        sym.encode(p, 0)


def test_a_base_that_pushes_a_symbol_past_32_bits_is_refused_by_name() -> None:
    """`struct` would raise on its own, with a message naming neither the symbol nor
    the base -- so a caller would blame their file for a base they passed."""
    p = sym.plan([sym.Symbol("_top", 0x1000)])
    with pytest.raises(sym.BadSymbolText, match="_top"):
        sym.encode(p, 0xFFFFFFFF)


def test_encode_refuses_when_nothing_says_where_the_program_was_loaded() -> None:
    """A default of zero would encode a file that is well-formed, loads without
    complaint, and names whatever occupies low memory: a wrong answer wearing the shape
    of a right one.

    IT USED TO ASK THE SIGNATURE -- that `base` had no default -- and that stopped
    expressing the requirement the moment `section_bases` became the other way to answer
    the same question: `base` now defaults to `None` and the requirement is UNCHANGED,
    only enforced at run time by `resolve_bases`. Asserting the BEHAVIOUR rather than
    the argument list is what survives the next way of supplying a base, and it is
    stronger: a signature can carry a required parameter that the body then ignores.
    """
    p = sym.plan([sym.Symbol("_x", 0x10)])
    with pytest.raises(sym.BadSymbolText, match="no base"):
        sym.encode(p)


def test_encode_refuses_a_flat_base_and_a_section_table_together() -> None:
    """Passing both leaves which one wins undecided, and a field that is
    sometimes a number and sometimes a table cannot be declared honestly in an MCP
    tool's schema. The refusal makes the ambiguity impossible rather than documented."""
    p = sym.plan([sym.Symbol("_x", 0x10)])
    with pytest.raises(sym.BadSymbolText, match="both"):
        sym.encode(p, 0x1000, section_bases={1: 0x400000})


def test_a_section_the_table_does_not_position_is_refused_and_not_placed_at_zero() -> None:
    """A base of 0 puts that whole section's symbols on top of whatever is at the bottom
    of the image: a wrong answer of exactly the right shape."""
    p = sym.plan([sym.Symbol("_x", 0x10, section=2)])
    with pytest.raises(sym.BadSymbolText, match="section 2"):
        sym.encode(p, section_bases={1: 0x400000})


def test_an_empty_section_table_is_refused_rather_than_read_as_a_flat_program() -> None:
    """"positions nothing" and "this program is flat" are different statements, and only
    one of them is something a caller meant to say."""
    p = sym.plan([sym.Symbol("_x", 0x10, section=1)])
    with pytest.raises(sym.BadSymbolText, match="positions no section"):
        sym.encode(p, section_bases={})


def test_two_sections_at_the_same_offset_land_at_different_addresses() -> None:
    """THE WHOLE POINT OF THE CALLER'S SECTION BASES, and the case a shared base cannot express.

    MEASURED on the real Borland 32-bit map, whose section table reads `{1: 0, 2: 0,
    3: 0}`: with the old model every section folded onto one address space and three
    symbols at the same offset in three different sections came back at ONE address,
    plausible and wrong. With the bases apart they are three addresses, and a reader
    that ignored the section index could not produce this answer.
    """
    p = sym.plan([sym.Symbol("_a", 0xE4, section=1),
                  sym.Symbol("_b", 0xE4, section=2),
                  sym.Symbol("_c", 0xE4, section=3)])
    got = sym.decode(sym.encode(p, section_bases={1: 0x401000, 2: 0x423000,
                                                  3: 0x4289B8}))
    assert dict(got) == {"_a": 0x4010E4, "_b": 0x4230E4, "_c": 0x428A9C}, got


# ------------------------------------------------------------------------ decoding

def test_a_file_that_disagrees_with_its_own_header_is_refused() -> None:
    """`count` is read from the file, so a truncated file otherwise decodes to however
    many whole records it happens to contain and reports that number as the answer."""
    with pytest.raises(sym.BadSymbolText, match="declares 3"):
        sym.decode(REAL_THREE[:-4])


def test_a_file_too_short_to_hold_even_a_count_says_so() -> None:
    with pytest.raises(sym.BadSymbolText, match="cannot hold"):
        sym.decode(b"\x03")


def test_more_symbols_than_the_count_field_holds_is_refused_not_wrapped() -> None:
    """The count is 16 bits. Writing more would wrap it into a SHORT list the debugger
    would read as complete, which is the silent-wrong-answer shape."""
    many = [sym.Symbol(f"_s{i}", i * 4) for i in range(sym.COUNT_MAX + 1)]
    with pytest.raises(sym.BadSymbolText, match="16 bits"):
        sym.plan(many)


# ------------------------------------------------------------------------ lookup

def test_an_exact_name_wins_outright_over_its_prefixes() -> None:
    """Ranked together, `_main` and `_main_loop` would make the caller choose between an
    answer and a guess."""
    table = [sym.Symbol("_main", 0x100), sym.Symbol("_main_loop", 0x200)]
    assert [s.name for s in sym.find_by_name(table, "_main")] == ["_main"]
    assert len(sym.find_by_name(table, "_mai")) == 2


def test_the_name_index_answers_exactly_what_the_scan_answers() -> None:
    """The index is the table by name, so an exact lookup through it is the scan's own
    answer (every duplicate, in table order) and a prefix still falls back to the scan.
    A name outside the index is a miss, never the scan's answer for a different table."""
    table = [sym.Symbol("_main", 0x100), sym.Symbol("_main_loop", 0x200),
             sym.Symbol("_main", 0x300)]
    index = sym.index_by_name(table)
    assert index["_main"] == [table[0], table[2]] and list(index) == ["_main", "_main_loop"]
    assert sym.find_by_name(table, "_main", index) == sym.find_by_name(table, "_main")
    assert len(sym.find_by_name(table, "_mai", index)) == 3
    assert sym.find_by_name(table, "_nope", index) == []
    got = sym.find_by_name(table, "_main", index)
    got.clear()
    assert len(index["_main"]) == 2, "the caller emptied the index"


def test_an_address_resolves_to_the_nearest_symbol_below_it_with_the_distance() -> None:
    """`_main+0x4` and `_main+0x9000` mean very different things and this table carries
    no sizes, so the delta is REPORTED rather than judged."""
    table = sym.parse_nm(NM_FRAGMENT)
    found = sym.find_by_offset(table, 0x0016DF24)
    assert found is not None
    best, delta = found
    assert (best.name, delta) == ("_main", 4)


def test_an_address_below_every_symbol_is_none_and_not_the_lowest_one() -> None:
    """Answering with the lowest symbol would put a name on an address that is not
    inside it, which is the confident wrong answer this package refuses."""
    table = [sym.Symbol("_x", 0x1000)]
    assert sym.find_by_offset(table, 0x10) is None


# --------------------------------------------------------- the size a real program produces

def test_the_size_a_real_program_produces_encodes_and_decodes_intact() -> None:
    """A real program's table, thousands of records, loads into the debugger and saves back
    whole, so nothing caps one load below the format's own ceiling. This asserts the
    encoder survives that size; the live case asserts the debugger does."""
    many = [sym.Symbol(f"_sym_{i:05d}", 0x1000 + i * 4) for i in range(7238)]
    data = sym.encode(sym.plan(many), MEASURED_BASE)
    assert len(data) == 2 + 20 * 7238 == 144762
    assert struct.unpack_from("<H", data, 0)[0] == 7238
    assert len(sym.decode(data)) == 7238


# ------------------------------------------- the seven the adversarial review measured
#
# Each of these is a defect that was LIVE and that the suite above was green over. They
# are grouped so the next reader can see the shape they share: six of the seven are a
# guarantee stated in a docstring that nothing was asking about.


def test_a_line_the_parser_cannot_read_is_counted_and_not_dropped() -> None:
    """MEASURED: `nm -C` emits `Foo::bar(int, char)`, whose name holds spaces, so the
    single-token name column does not match. Two lines went in, one symbol came out,
    and `parsed` said 1 -- accounting that adds up over an amputated population."""
    text = "0016df20 T _main\n0016df30 T Foo::bar(int, char)\n"
    syms, unreadable = sym.parse(text)
    assert [s.name for s in syms] == ["_main"]
    assert unreadable == 1, "the C++ line matched nothing and has to be counted"
    assert sym.plan(syms, unreadable=unreadable).unreadable == 1
    # A BLANK LINE IS NOT AN UNREADABLE ONE, or every file scores its own trailing
    # newline and the number stops meaning anything.
    assert sym.parse("0016df20 T _main\n\n   \n")[1] == 0


def test_nothing_surviving_the_filters_is_refused_not_an_empty_file() -> None:
    """`_parse` already refused a text that parsed to nothing; the path THROUGH the
    filters slipped past that intent. A mistyped pattern produced `b"\\x00\\x00"`: a
    well-formed list of nothing that loads without complaint and names nothing."""
    syms = sym.parse_nm(NM_FRAGMENT)
    with pytest.raises(sym.BadSymbolText, match="nothing survived the filters"):
        sym.plan(syms, pattern="^_no_such_prefix")
    # THE CONTROL, so this is not just "plan raises sometimes": the same call with a
    # pattern that matches is a plan.
    assert sym.plan(syms, pattern="^_main$").kept == 1


def test_a_nul_inside_a_name_cannot_put_two_addresses_under_one_name() -> None:
    """The central guarantee was expressed on `str` and the file is BYTES. `_a\\0b` and
    `_a\\0c` are different strings, so `check()` called them distinct, and the debugger
    cuts a name at the first NUL: both decoded to `_a`."""
    # THE THIRD SYMBOL IS LOAD-BEARING, and the first version of this test did without
    # it and failed: with both NUL names rejected the plan is EMPTY, which the guard
    # one test up now refuses. Two fixes composing correctly, and the fixture has to
    # exercise this one without tripping that one.
    p = sym.plan([sym.Symbol("_a\x00b", 1), sym.Symbol("_a\x00c", 2),
                  sym.Symbol("_ok", 3)])
    assert p.kept == 1 and len(p.unencodable) == 2
    # AND THE PROPERTY ITSELF, not just the gate: whatever survives, no two records
    # decode to the same name.
    names = [n for n, _ in sym.decode(sym.encode(sym.plan(
        [sym.Symbol("_a", 1), sym.Symbol("_b", 2)]), 0))]
    assert len(set(names)) == len(names)


def test_an_empty_name_and_a_control_byte_are_refused() -> None:
    """A record whose whole name field is padding names nothing, and a control byte is
    ASCII, which is why "encodable as ASCII" was the wrong gate."""
    p = sym.plan([sym.Symbol("", 1), sym.Symbol("_a\tb", 2), sym.Symbol("_ok", 3)])
    assert p.kept == 1 and p.short == ["_ok"]
    assert p.unencodable == ["", "_a\tb"]


def test_a_negative_offset_and_an_oversized_base_are_refused() -> None:
    """Only the SUM was checked, so the two errors CANCELLED. MEASURED: offset -0x1000
    against base 0x400000 encoded as 0x3FF000, naming memory below the program; and
    base 0x100000000 with offset -1 encoded as 0xFFFFFFFF."""
    with pytest.raises(sym.BadSymbolText, match="not negative"):
        sym.encode(sym.plan([sym.Symbol("_x", -0x1000)]), MEASURED_BASE)
    with pytest.raises(sym.BadSymbolText, match="not a 32-bit linear base"):
        sym.encode(sym.plan([sym.Symbol("_y", 1)]), 0x100000000)
    # THE CONTROL: the legitimate extremes still encode, so this did not simply narrow
    # the range until nothing passes.
    assert len(sym.encode(sym.plan([sym.Symbol("_z", 0)]), 0)) == 2 + sym.RECORD
    assert len(sym.encode(sym.plan([sym.Symbol("_z", 0)]), sym.ADDR_MAX)) == 2 + sym.RECORD


def test_a_generated_name_never_takes_a_real_name_that_fits_and_is_unique() -> None:
    """The module promises "a name that fits and is unique is never touched" and one
    pass in input order broke it: the third symbol below is really CALLED
    `abcdefghijklm~0`, and the SECOND one was given that name."""
    names = ["abcdefghijklmXY1", "abcdefghijklmXY2", "abcdefghijklm~0"]
    short, _, _ = sym._disambiguate(names)
    assert short[2] == "abcdefghijklm~0", "the real name has to reach its own symbol"
    assert len(set(short)) == 3
    # AND THE ORDER IS STILL THE INPUT'S, which is what lets a golden exist at all.
    assert short[0] == "abcdefghijklmXY"


def test_renamed_counts_the_names_that_are_not_the_symbols_own() -> None:
    """`truncated_names` counts names LONGER than the field, so it reported 0 on three
    copies of a 14-character name while two of the three in the file were invented."""
    p = sym.plan(sym.parse_nm(REPEATED_FULL_NAME))
    assert p.truncated_names == 0, "every one of these fits: that is the point"
    assert p.renamed == 2 and p.disambiguated == 2
    # AND IT COUNTS TRUNCATION TOO, so it is the whole question and not a second
    # partial answer sitting beside the first.
    q = sym.plan([sym.Symbol("_a_name_far_too_long_to_fit", 1)])
    assert q.truncated_names == 1 and q.renamed == 1


def test_decode_refuses_a_byte_no_name_of_ours_could_hold() -> None:
    """`decode` exists to VERIFY a load. Replacing an undecodable byte with U+FFFD let
    a caller compare successfully against a name that is not in the file."""
    data = struct.pack("<H", 1) + b"\xff_x" + b"\0" * 13 + struct.pack("<I", 0)
    with pytest.raises(sym.BadSymbolText, match="no name of ours can contain"):
        sym.decode(data)


def test_the_dead_duplicate_of_the_filename_limit_is_gone() -> None:
    """`NAME_ON_DISK_MAX` was the SAME constant as `dosbox_session.SYM_ARG_MAX` under a
    second name, in the module that builds no filenames. Two names for one decision is
    what a clone detector cannot see and what diverges in silence."""
    assert not hasattr(sym, "NAME_ON_DISK_MAX")


def test_a_value_that_is_not_an_address_is_excluded_and_counted() -> None:
    """`nm` prints a COMMON symbol's SIZE in the address column and an ABSOLUTE
    symbol's constant, so neither can be placed on a map of the program.

    MEASURED on objects built by this machine's own DJGPP before the fix: a plan over
    `nm` of a `.o` came back `parsed=8, kept=4, unencodable=0, truncated_names=0,
    renamed=0`
    -- every counter clean -- `check()` did not raise, and the emitted table put
    `_big_table` at linear 0x14000, which is its SIZE (4096 ints x 4 bytes), and
    `_PORT`, a `.set _PORT, 0x3F8` serial-port constant, at 0x103F8. Complete,
    plausible, loadable and entirely false.

    EXCLUDED AND COUNTED rather than refusing the file, which is this module's own
    idiom: the bucket keeps the table TRUE and conservation keeps the loss VISIBLE.
    """
    text = ("00004000 C _big_table\n"
            "00000100 C _other_common\n"
            "000003f8 A _PORT\n"
            "00000000 D _initialised\n"
            "0016df20 T _main\n")
    p = sym.plan(sym.parse_nm(text))
    assert p.excluded_unplaceable == 3, p
    assert [s.name for s in p.symbols] == ["_initialised", "_main"], p.symbols
    p.check()
    # AND THE ACCOUNTING STILL ADDS UP, which is what stops the exclusion being a
    # silent drop: `check()` refuses a report whose buckets do not sum to its
    # population, so a bucket that did not join the sum would fail here.
    assert p.parsed == p.kept + p.excluded_unplaceable + p.excluded_noise


def test_a_linked_program_loses_no_symbol_to_the_unplaceable_filter() -> None:
    """THE CONTROL, and it is what makes the exclusion cheap rather than a judgement.

    MEASURED on the linked DJGPP binary this package was built against: 9,653 symbols,
    of which `C` and `A` are ZERO. The linker allocates commons into `.bss`, where they
    become `B`, so these kinds exist only in an UNLINKED object -- the one mistake the
    filter catches. Without this case the filter could silently eat a real workload and
    the case above would still pass.
    """
    linked = "\n".join([
        "0016df20 T _main", "0005c830 T _engine_load_midi", "002308b8 b .bss",
        "00239000 B _some_global", "0013a020 t .text", "00230000 d .data",
    ]) + "\n"
    p = sym.plan(sym.parse_nm(linked))
    assert p.excluded_unplaceable == 0, p
    # Three kept (`_main`, `_engine_load_midi`, `_some_global`) and three excluded as
    # section noise (`.bss`, `.text`, `.data`) -- the point being that NONE of the six
    # falls into the unplaceable bucket.
    assert p.kept == 3, p
    assert p.excluded_noise == 3, p


# --------------------------------------------------- Borland TLINK / TASM (real mode)

# AN EXCERPT IN A REAL TLINK MAP'S SHAPE, CRLF and all, its rows chosen and edited by hand: the
# map it was cut from is not kept, so it stands as authored. Every property this parser turns
# on is in here: the segment table whose rows ALSO open with a `seg:off` pair, the FIVE-digit
# offset, the optional `idle` flag, the two identical publics sections, and the trailer. The
# real TLINK map this suite holds whole is `tests/fixtures/borland-tlink16/MAPDEMO.MAP`.
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
    """The trap, and it is why the anchor is the SECTION HEADER and not the line shape.

    A TLINK map's "Detailed map of segments" opens every row with a `seg:off` pair too,
    so a pattern matching the LINE takes the last token and emits symbols called
    `ACBP=48` -- plausible, silent, and in a table that then loads clean.
    """
    got, unreadable = sym.parse(TLINK_MAP)
    names = [s.name for s in got]
    assert names == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], names
    assert unreadable == 0
    assert not [n for n in names if "=" in n], f"the segment table leaked in: {names}"


def test_a_borland_address_is_folded_the_way_the_debugger_folds_it() -> None:
    """`seg:off` -> `seg * 16 + off`, which is not a convention invented here: the
    CAPTURED golden shows `IV 1234:5678` typed and `0x000179B8` stored.

    The arithmetic is spelled out so a reader does not take the hex on trust.
    """
    at = {s.name: s.offset for s in sym.parse_tlink(TLINK_MAP)[0]}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21 == 0xE561
    assert at["ANIMPLANE"] == 0x1247 * 16 + 0x0DFEB == 0x2045B
    # AND THE FIVE-DIGIT OFFSET IS THE ONE THAT WOULD HAVE BEEN MISSED: this linker pads
    # it one digit wider than the sixteen bits it holds, so a `{4}` matched nothing.
    assert 0x0DFEB <= 0xFFFF


def test_the_two_publics_sections_are_one_set_and_not_two() -> None:
    """TLINK prints the same symbols twice, by name and by value, with no difference
    between the two. Read without de-duplicating, every symbol
    collides with itself and `_disambiguate` invents a `~1` for all of them."""
    p = sym.plan(sym.parse_tlink(TLINK_MAP)[0])
    assert p.parsed == 3, p
    assert p.disambiguated == 0, "the same symbol twice was read as two"
    assert sorted(p.short) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"]


def test_two_different_symbols_sharing_a_name_still_survive_as_two() -> None:
    """THE CONTROL for the de-duplication: it is keyed on (name, offset), so it folds a
    symbol printed twice and does NOT fold two distinct symbols that share a name --
    the case `_disambiguate` exists for."""
    doubled = TLINK_MAP.replace(" 1247:0DFEB       ANIMPLANE\r\n",
                                " 1247:0DFEB       ANIMPLANE\r\n"
                                " 2000:00001       ANIMPLANE\r\n")
    got, _ = sym.parse_tlink(doubled)
    assert [s.name for s in got].count("ANIMPLANE") == 2, got


def test_a_borland_map_with_no_publics_says_so_instead_of_blaming_the_file() -> None:
    """The two nothings, told apart. Two real maps of one toolchain can differ exactly so,
    one with publics and one with none, and "no symbol lines were recognised in that text"
    for the second would tell the reader their file is not a symbol list, when what is true
    is that this LINK printed no publics."""
    segments_only = TLINK_MAP.split("  Address")[0]
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(segments_only)


def test_nm_and_gnu_maps_are_still_routed_to_their_own_parsers() -> None:
    """THE CONTROL FOR THE ROUTING, without which the Borland sniff could swallow
    everything and every case above would still pass."""
    assert not sym.looks_like_tlink(NM_FRAGMENT)
    assert len(sym.parse(NM_FRAGMENT)[0]) == 10
    gnu = ("                0x000000000016df20                _main\n"
           "                0x000000000005c830                _engine_load_midi\n")
    assert not sym.looks_like_tlink(gnu)
    assert [s.name for s in sym.parse(gnu)[0]] == ["_main", "_engine_load_midi"]


def test_a_c_symbol_table_survives_the_round_trip_with_its_case_intact() -> None:
    """THE PROPERTY THE WHOLE MODULE RESTS ON, against bytes the debugger wrote.

    Every symbol this exists to load is lowercase with a leading underscore, and the
    only golden that existed held three names without a lowercase letter between them.
    An encoder tested against its own decoder agrees with itself perfectly while both
    are wrong, which is why `REAL_THREE` exists at all -- and it could not answer this.

    CAPTURED by the round trip the module PERFORMS (`LV` a binary in, `SV` it back out),
    not by typing at the console: `IV` UPPERCASES and truncates, so a capture through it
    reports `_MAIN` and `_ENGINE_LOAD_MI` and says the opposite of what is true.
    """
    got = sym.decode(REAL_THREE_LOWER)
    assert got == [("_main", 0x000179B8),
                   ("_engine_load_mi", 0x00000870),
                   ("_poly_scanline_", 0x000A001F)]
    # AND THE ENCODER'S LAYOUT IS THE DEBUGGER'S: `SV` writes the debugger's own variable list,
    # so its bytes equalling the encoder's say the debugger read those records as it writes
    # its own, case and the fifteen-character cut included.
    syms = [sym.Symbol("_main", 0x000179B8), sym.Symbol("_engine_load_midi", 0x00000870),
            sym.Symbol("_poly_scanline_gcol8", 0x000A001F)]
    assert sym.encode(sym.plan(syms), base=0) == REAL_THREE_LOWER
    # THE CONTROL: the case really is what distinguishes these two goldens, so a
    # comparison that folded it would be satisfied by the uppercase one.
    assert any(c.islower() for n, _ in got for c in n)
    assert not any(c.islower() for n, _ in sym.decode(REAL_THREE) for c in n)


# --------------------------------------------------- what the eight cases above cannot see
#
# Every case below exists because a BREAK of the shipped code came back GREEN against
# the eight cases above it. They are grouped here rather than folded in beside their
# siblings so that the reason they exist stays legible: this block is the answer to
# "seen red along which axis".


def test_a_row_the_reader_cannot_parse_does_not_take_the_rest_of_the_section_with_it()\
        -> None:
    """THE AMPUTATION, and it is the defect `Plan.unreadable` exists to prevent.

    A walk that `break`s at the first row it cannot read, WHEREVER that row is, leaves
    `parse()` reporting `unreadable = 0` however firmly a comment says an amputated
    population cannot happen here. On this very input one symbol of four comes back,
    `unreadable` is 0, and `check()` accepts the result as a complete, loadable table.

    THE AXIS IS PLACE, not presence. The eight cases before this one all feed a section
    whose every row parses, so they pin `unreadable == 0` as a CONSTANT and never as a
    property -- and `break` -> `continue`, which is the whole of the old bug, was green
    against all of them.
    """
    amputated = TLINK_MAP.replace(
        " 1247:0DFEB       ANIMPLANE\r\n",
        " 0D74:000E21      SIXDIGITS\r\n 1247:0DFEB       ANIMPLANE\r\n")
    got, unreadable = sym.parse(amputated)
    names = [s.name for s in got]
    # The rows AFTER the unreadable one survive: that is what `break` destroyed.
    assert "ANIMPLANE" in names, f"the section was amputated: {names}"
    assert sorted(names) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], names
    # AND THE LOSS IS REPORTED. Twice, because the row appears in both publics sections
    # -- the count is of ROWS not read, not of symbols missing, and conflating them is
    # how a count starts lying about a set.
    assert unreadable == 2, unreadable



def test_a_publics_section_this_reader_cannot_parse_is_not_called_empty() -> None:
    """The two nothings, and a message that gets them the wrong way round.

    A genuinely empty `Publics by` section is a statement about the LINK. A section full
    of rows the reader cannot read is a statement about the READER, and saying the first
    about the second sends somebody off to declare symbols PUBLIC that are already there
    and already printed.

    An eight-digit row in a file with no section table is NOT the unreadable case: the
    reader keeps `(section, offset)` and placement is a later step, so that row READS -- and
    is refused at PLACE time, by name, if the caller does not position its section. The
    case that is genuinely unreadable is a row of a shape neither pattern knows.
    """
    unknown = ("  Address         Publics by Name\r\n"
               "\r\n"
               " 0001:0BE       _main\r\n"
               " 0001:0C4       _engine_load\r\n")
    with pytest.raises(sym.BadSymbolText, match="could not be placed"):
        sym.parse(unknown)
    # THE CONTROL: a genuinely empty section still gets the OTHER message, or the fix
    # would have been to replace one wrong diagnosis with a different wrong one.
    empty = "  Address         Publics by Name\r\n\r\nProgram entry point at 0000:0000\r\n"
    with pytest.raises(sym.BadSymbolText, match="no line under it that starts like"):
        sym.parse(empty)


def test_an_offset_wider_than_sixteen_bits_is_not_folded_into_an_address() -> None:
    """`{4,5}` is a fact about this linker's PADDING, not a widening of the field.

    Five hex digits reach 0xFFFFF and a real-mode offset does not, so `seg * 16 + off`
    on a wider value invents an address. MEASURED before the fix: ` 0459:1FFFF  FOO`
    came back as a symbol at 0x2458F with every counter clean.
    """
    got, unreadable = sym.parse_tlink(
        "  Address         Publics by Name\n"
        "\n"
        " 0459:00123       GOOD_ONE\n"
        " 0459:1FFFF       FOO\n"
        " 0459:00456       GOOD_TWO\n")
    # THE TWO GOOD ROWS ARE NOT PADDING. Without them the section is a MAJORITY loss and
    # is refused outright by `_refuse_if_mostly_unreadable`, which would make this case
    # pass for the wrong reason -- and stop asserting that the surrounding rows SURVIVE
    # the bad one, which is half of what the accounting is for.
    assert [s.name for s in got] == ["GOOD_ONE", "GOOD_TWO"], got
    assert unreadable == 1, unreadable


def test_the_sniff_and_the_walk_ask_the_same_question() -> None:
    """`\\s` matches a NEWLINE, so a header pattern written with it spans two lines.

    `looks_like_tlink("Address\\nPublics by Name\\n")` then answers True while the walk's
    per-line `match` answers False, and `parse()` trusts the looser one -- refusing an
    ordinary two-line file with a message about Borland maps. The axis is SHAPE: the two
    predicates have to be the same predicate.
    """
    across = "Address\nPublics by Name\n"
    assert not sym.looks_like_tlink(across), "the sniff still spans a newline"
    assert not sym._TLINK_SEGMENTS.search("Start\nStop\nLength\nName\nClass\n")
    # AND THE CONTROL, so the fix cannot be "reject everything": a real header on ONE
    # line is still recognised, CRLF and all.
    assert sym.looks_like_tlink("  Address         Publics by Name\r\n")


def test_a_section_header_carrying_a_trailing_token_is_still_a_section_header() -> None:
    """A pattern ending `\\w+\\s*$` lets any annotation after the section word kill the
    match -- and the reader then announces "it has NO `Publics by ...` section" about a
    file that visibly has two."""
    annotated = (TLINK_MAP.replace("Publics by Name", "Publics by Name   (overlay 1)")
                          .replace("Publics by Value", "Publics by Value   (overlay 1)"))
    got, _ = sym.parse(annotated)
    assert [s.name for s in got] == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], got


def test_a_borland_public_does_not_claim_to_be_code() -> None:
    """Every row was stamped `kind="T"`, which the map does not say.

    A TLINK `Publics by` section prints code and data publics together, so `?` is the
    honest answer and the one `parse_map` already gives. It stopped being cosmetic when
    `_UNPLACEABLE` arrived: `plan()` compares `kind`, and `symbols_find` reports it.
    """
    got, _ = sym.parse_tlink(TLINK_MAP)
    assert {s.kind for s in got} == {"?"}, got


def test_the_letters_whose_value_is_not_an_address_are_the_measured_ones() -> None:
    """THE SET'S CONTENTS, which no case asserted -- so widening it to `CAWV` (which
    excludes real, placeable, weak-defined symbols) was GREEN.

    Every letter here is one MEASURED on a real DJGPP artefact, and the two directions
    are asserted together because that is what pins a SET rather than a behaviour.
    """
    assert set(sym._UNPLACEABLE) == set("CAaN"), sym._UNPLACEABLE
    # The letters that carry a real address must NOT be in it. `W`/`V` are weak defined
    # symbols; `T t D d B b R r` are ordinary.
    assert not set("TtDdBbRrWVwv") & set(sym._UNPLACEABLE)


def test_a_local_absolute_and_a_debug_symbol_are_not_placed_either() -> None:
    """The lowercase half, and the letter the reasoning never considered.

    The set was UPPERCASE ONLY, justified by "the four in the measured binary are
    `.absolut`, which `_NOISE` already excludes by name". That is a fact about one
    binary doing the work of a rule, and it failed two ways. MEASURED on the linked
    DJGPP binary: 499 `N` symbols (`00002210 N .comment`, a section-relative offset)
    and 4 `a`, ALL of them placed the moment `keep_noise` is on -- and a lowercase `a`
    with an ordinary name was placed even with it off, because `_NOISE` never saw it.
    """
    # `_NOISE` cannot save this one: the name has no leading dot.
    p = sym.plan(sym.parse_nm("000003f8 a _localport\n0016df20 T _main\n"))
    assert p.excluded_unplaceable == 1, p
    assert [s.name for s in p.symbols] == ["_main"], p.symbols

    # AND `keep_noise=True` DOES NOT PUT THEM BACK, which is the half that made the
    # old reasoning circular: it rested on a filter the caller can switch off, and
    # `keep_noise` is a parameter of the `symbols_load` tool.
    real = ("00002210 N .comment\n00000000 a .absolut\n0016df20 T _main\n")
    kept = sym.plan(sym.parse_nm(real), keep_noise=True)
    assert kept.excluded_unplaceable == 2, kept
    assert [s.name for s in kept.symbols] == ["_main"], kept.symbols


def test_two_names_at_one_address_both_survive() -> None:
    """The OTHER half of the de-duplication key, which nothing asserted.

    The key is `(name, offset)`. Its `name` half has a control -- two symbols sharing a
    name -- and its `offset` half had none, so keying on the address ALONE was green.
    An aliased public (one label carrying two `PUBLIC` directives) is ordinary, and
    folding it silently loses a name the caller asked for.
    """
    aliased = TLINK_MAP.replace(
        " 1247:0DFEB       ANIMPLANE\r\n",
        " 1247:0DFEB       ANIMPLANE\r\n 1247:0DFEB       _animplane\r\n")
    got, _ = sym.parse_tlink(aliased)
    at = [s.name for s in got if s.offset == 0x1247 * 16 + 0x0DFEB]
    assert sorted(at) == ["ANIMPLANE", "_animplane"], got


def test_an_empty_selection_is_refused_by_the_guard_and_not_by_check() -> None:
    """A comment named the wrong mechanism, and a reader trusting it would have deleted
    the real one.

    `plan()`'s comment said `check()` "already refuses when the filters leave nothing".
    It does not: on an empty selection the distinctness test is vacuous, the parallel
    lengths agree at zero, and the buckets sum. The refusal is the `if not chosen:`
    guard. This case pins BOTH halves so the sentence cannot drift back.
    """
    empty = sym.Plan(parsed=2)
    empty.excluded_unplaceable = 2
    empty.check()          # must NOT raise -- that is the point

    with pytest.raises(sym.BadSymbolText, match="nothing survived the filters") as e:
        sym.plan(sym.parse_nm("00004000 C _big\n000003f8 A _PORT\n"))
    # AND THE MESSAGE ACCOUNTS FOR THEM: four zeroes over a population of two name no
    # cause at all.
    assert "2 whose value is not an address" in str(e.value), str(e.value)


# ------------------------------------- the overlay flag, which travels with its symbol

def test_an_overlay_symbol_is_placed_and_the_flag_travels_with_it() -> None:
    """`idle` is easy to MATCH AND THROW AWAY, with a docstring calling that a known limit.

    TLINK writes it beside a public living in an overlay it has NOT made resident, so
    that address holds whatever is swapped in when you look. Placing such a symbol is
    right -- a large part of a real map carries the flag, and losing
    that much of a table is the worse failure of the two -- but placing it
    with NOTHING SAID is a name pointing at a conditional address, indistinguishable in
    the reply from one that does not move.

    THE AXIS IS PRESENCE ON THE SYMBOL, not the count: a counter alone answers "how many
    of them", and `symbols_find` is asked about ONE name.
    """
    got, _ = sym.parse_tlink(TLINK_MAP)
    flagged = {s.name: s.idle for s in got}
    assert flagged == {"ACTIVEIMAN": True, "ACTIVE_CLS": False, "ANIMPLANE": False}, got
    # AND IT IS STILL PLACED, at the address the row gives. Excluding it would have
    # satisfied the line above just as well, so the address is asserted beside the flag.
    at = {s.name: s.offset for s in got}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21, at


def test_the_name_of_a_flagged_row_is_the_name_and_not_the_flag() -> None:
    """THE SILENT HALF of capturing that group: it moved the name from `group(3)` to
    `group(4)`.

    Left at 3, a flagged row comes back as a symbol CALLED `idle`, at a plausible
    address, and nothing anywhere fails -- the match succeeds, the fold is arithmetic,
    the buckets sum and the table loads clean. It shows up only on rows carrying the
    flag, which is why the fixture has exactly one and why this case exists apart from
    the one above it.
    """
    got, _ = sym.parse_tlink(TLINK_MAP)
    assert "idle" not in [s.name for s in got], got
    assert sorted(s.name for s in got) == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], got


def test_the_overlay_symbols_are_counted_and_do_not_break_the_accounting() -> None:
    """The rule that keeps every real map with an overlay loadable.

    `overlay_idle` is a SUBSET of `kept`, not a bucket beside it. Added to `check()`'s
    sum it double-counts, so a Borland map carrying a single overlay symbol is rejected
    as an accounting failure -- every real map carrying the mark.
    Both halves are asserted together because that is what pins a SUBSET rather than a
    number: the count is right AND the partition is untouched.
    """
    p = sym.plan(sym.parse_tlink(TLINK_MAP)[0])
    assert p.overlay_idle == 1, p
    assert p.kept == 3, p
    # THE PARTITION, spelled out rather than left to `check()`: the flagged symbol is
    # inside `kept` and in no bucket of its own.
    assert (p.kept + p.excluded_noise + p.excluded_pattern + p.excluded_unplaceable
            + len(p.unencodable)) == p.parsed == 3, p
    p.check()          # must NOT raise -- that is the point


def test_the_overlay_count_describes_the_table_and_not_the_file() -> None:
    """It counts over what SURVIVED the filters, which is a different set.

    A caller who narrowed with a `pattern` holds a table with none of the flagged
    symbols in it; counting them off the FILE would tell them part of what they loaded
    is conditional when none of it is. The axis is POPULATION, and counting `symbols`
    instead of `chosen` reproduces every other assertion in this block exactly.
    """
    narrowed = sym.plan(sym.parse_tlink(TLINK_MAP)[0], pattern="^ANIM")
    assert narrowed.kept == 1, narrowed
    assert narrowed.overlay_idle == 0, narrowed
    # THE CONTROL, or the assertion above is satisfied by a counter that is always 0:
    # the same map with a pattern that KEEPS the flagged symbol still counts it.
    kept = sym.plan(sym.parse_tlink(TLINK_MAP)[0], pattern="^ACTIVEI")
    assert kept.kept == 1 and kept.overlay_idle == 1, kept


def test_nm_and_gnu_symbols_are_not_flagged_idle() -> None:
    """THE CONTROL FOR THE DEFAULT: neither format has the concept, so a True there
    would be this parser inventing one.

    Without it, `idle=True` as the dataclass default satisfies every case above.
    """
    assert not any(s.idle for s in sym.parse_nm(NM_FRAGMENT))
    gnu = ("                0x000000000016df20                _main\n"
           "                0x000000000005c830                _engine_load_midi\n")
    assert not any(s.idle for s in sym.parse(gnu)[0])
    assert sym.plan(sym.parse_nm(NM_FRAGMENT)).overlay_idle == 0


# --------------------------------------------- the 32-bit map, and its own section table

# A REAL ILINK32 MAP, trimmed by deleting lines (tests/fixtures/borland-ilink32/PROVENANCE.txt).
# Two things in it a reader built from the vendor's documentation gets wrong: the segment
# table's `Start` is `section:offset` with every section starting at ZERO and section 2 listed
# again and again at growing offsets, so it is a segment list and never a table of bases; and
# the mark is `Idle`, with a capital I. Placement therefore comes from the caller
# (`section_bases`), and the column is read and not used. The `Detailed map of segments` rows
# open with the same `sect:offset` pair, which is the trap a scan of the whole file falls into.
ILINK32_MAP = (Path(__file__).parent / "fixtures" / "borland-ilink32" / "sections32.map"
               ).read_bytes().decode("latin-1")

# THE BASES A CALLER SUPPLIES FOR THAT MAP, DISTINCT on purpose: with every section at one
# base, a reader that consults the section index and one that ignores it place every symbol
# alike, so nothing about the index would be asserted -- and coverage cannot stand in for it,
# since an all-zero table executes every line of the lookup.
ILINK32_BASES = {1: 0x401000, 2: 0x423000, 3: 0x4289B8}

def _declared_sections(text: str) -> dict[int, int]:
    """index -> the extent its segments reach (the furthest `start + length`), READ OUT OF THE
    FIXTURE by a regex of this test's own: a section is listed once per segment it holds.

    A dict written out beside the fixture is not an oracle: both halves are hand-written,
    so editing one and not the other goes unnoticed. Shrinking the fixture's `_TEXT`
    length to `00000010H` -- which puts `_main` OUTSIDE its own section, the exact defect
    the containment case exists to catch -- leaves that case GREEN while the expected
    table still carries the old value.

    It is still INDEPENDENT of the parser, which is the property that matters: `dosbox_
    symbols` never reads the LENGTH column at all, so the containment check below is not
    the parser's own arithmetic restated.
    """
    rx = re.compile(r"^ ([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}) ([0-9A-Fa-f]+)[Hh] ", re.M)
    out: dict[int, int] = {}
    for i, start, ln in rx.findall(text):
        out[int(i, 16)] = max(out.get(int(i, 16), 0), int(start, 16) + int(ln, 16))
    assert out, "the fixture's section table did not parse: this oracle read nothing"
    return out



def test_a_32_bit_row_keeps_its_section_and_is_placed_by_the_callers_table() -> None:
    """The reader keeps what the file said, and placement is a
    later step that DEMANDS its bases.

    Resolving the row against the map's own `Start` column while reading does not survive
    a real artefact: every `Start` offset there is zero, so all three sections fold onto
    one address space and every symbol comes back plausible and on top of another. The
    section index survives to the symbol, and the caller says where each section went.
    """
    got, unreadable = sym.parse(ILINK32_MAP)
    assert unreadable == 0, unreadable
    # THE COUNT, because a name-keyed dict COLLAPSES a doubled emission in silence. This
    # fixture prints both publics sections, so the de-duplication is exercised here, and
    # without this line it is exercised without being observed.
    assert len(got) == 4, got
    kept = {s.name: (s.section, s.offset) for s in got}
    assert kept == {"_main": (1, 0x00000130), "_errno": (2, 0x00002090),
                    "_g_count": (2, 0x000022D4), "___xxInfo": (3, 0x00000000)}, kept
    # AND THE ADDRESSES, once the caller answers. The bases are DISTINCT, which is
    # what makes this assertion able to fail at all: with a shared base a reader that
    # consults the section index and one that ignores it give the same answer.
    placed = dict(sym.decode(sym.encode(sym.plan(got),
                                        section_bases=ILINK32_BASES)))
    assert placed == {"_main": 0x00401130, "_errno": 0x00425090,
                      "_g_count": 0x004252D4, "___xxInfo": 0x004289B8}, placed



def test_every_offset_lands_inside_the_length_its_own_section_declared() -> None:
    """CONSISTENCY with the LENGTH column, the oracle the file itself carries.

    It is checked against the LENGTH column, which the parser NEVER reads: a symbol
    carrying section N must have an offset inside N's own declared extent. An oracle
    built from anything the parser reads would be the parser's arithmetic written twice.

    THE EXTENTS ARE READ OUT OF THE FIXTURE, not written beside it -- see
    `_declared_sections`, whose docstring carries the measured reason. And the population
    is asserted BEFORE the loop, because a `for` over an empty list passes every
    assertion inside it: this file already documents that failure by name.
    """
    declared = _declared_sections(ILINK32_MAP)
    syms = sym.parse_tlink(ILINK32_MAP)[0]
    assert len(syms) == 4, syms
    for one in syms:
        assert one.section in declared, f"{one.name} names section {one.section}"
        extent = declared[one.section]
        assert 0 <= one.offset < extent, (
            f"{one.name} at {one.offset:#x} is outside its own section's "
            f"{extent:#x} bytes")
    # EVERY DECLARED SECTION IS EXERCISED, so a fixture that grows a section nothing
    # references cannot quietly stop being checked.
    assert {one.section for one in syms} == set(declared), declared



def test_the_detailed_map_row_is_not_taken_for_a_section() -> None:
    """THE TRAP, and it is the same one the publics walk was built around.

    `Detailed map of segments` opens every row with a `sect:offset` pair as well, so a
    table built by scanning the whole file would take its rows for sections. The walk is
    anchored on the table's HEADER, and the row's shape (no `H` on the length, five trailing
    tokens) refuses it a second time; the table positions nothing, so the INDICES it reads
    are what is asserted, and the shape alone is put to the test below.
    """
    sections = sym._tlink_sections(ILINK32_MAP.splitlines())
    assert sorted(sections) == [1, 2, 3], sections
    # AND THE CONTROL: the trap row really is in the fixture, so this is not passing
    # over a file that never contained one.
    assert "Detailed map of segments" in ILINK32_MAP
    assert " 0001:00000108 0000004B C=CODE" in ILINK32_MAP

    # AND THE ROW SHAPE IS ISOLATED FROM THE HEADER ANCHOR, because with both in place
    # either one alone is enough and neither is individually necessary: here the trap row
    # sits INSIDE the walk's own range, so only the shape can refuse it.
    inline = [" Start         Length     Name               Class",
              "",
              " 0001:00000108 0000004B C=CODE    S=_TEXT    G=(none)   M=HELLO32.C  ACBP=A9"]
    assert sym._tlink_sections(inline) == {}, sym._tlink_sections(inline)


def test_the_section_table_is_only_read_under_its_own_header() -> None:
    """THE ANCHOR, isolated from the shape guard that was covering for it.

    A well-formed section ROW is not a section table: the same three columns can be
    printed by anything, and this module's whole Borland reader is built on the rule that
    the HEADER decides which lines are read. With the anchor gone a scan of the file
    picks these up wherever they appear.
    """
    loose = [" 0001:00401000 0000214D4H _TEXT              CODE",
             " 0002:00423000 0000059B8H _DATA              DATA"]
    assert sym._tlink_sections(loose) == {}, sym._tlink_sections(loose)
    # THE CONTROL, or "refuses everything" passes this: the same rows UNDER the header
    # are read.
    assert sym._tlink_sections([" Start         Length     Name               Class",
                                "", *loose]) == {1: 0x00401000, 2: 0x00423000}


def test_the_two_row_shapes_cannot_claim_the_same_row() -> None:
    """WHY THE ORDER THEY ARE TRIED IN DOES NOT MATTER, asserted instead of assumed.

    `_tlink_place` tries the real-mode pattern first, so ANY widening of the 32-bit one
    is invisible to every case that feeds it real material -- MEASURED, widening it to
    `{4,8}` was green across the whole suite. What makes the order safe is that the two
    offset widths do not overlap, and that is a property, so it is pinned as one.

    The direction that bites is a real-mode row read as a SECTION INDEX: `0D74` is not a
    section any table positions, so the symbol is refused rather than folded, and every
    real map on this machine stops parsing.
    """
    real_mode = " 0D74:00E21 idle  ACTIVEIMAN"
    flat = " 0001:00000130       _main"
    assert sym._TLINK_ROW.match(real_mode) and not sym._TLINK_ROW32.match(real_mode)
    assert sym._TLINK_ROW32.match(flat) and not sym._TLINK_ROW.match(flat)



def test_a_section_the_caller_did_not_position_is_refused_and_never_placed_at_zero() -> None:
    """A base of 0 would name whatever occupies the bottom of the image.

    That is a wrong answer of exactly the right shape -- it loads, it looks like every
    other symbol, and it is silently about the wrong program.

    THE REFUSAL BELONGS TO PLACING AND NOT TO READING: a reader that drops such a row as
    unreadable tells the caller a row was lost and not WHICH SECTION nobody positioned.
    The row survives to the symbol instead, and the refusal names the section and lists
    the ones the table does hold.
    """
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
    """THE OTHER DIRECTION OF THE SAME RULE.

    A reader that placed while reading could only REFUSE a file with eight-digit rows and
    no section table outright, because nothing positions the section. Keeping
    `(section, offset)` it reads: the row says section 1, offset 0xBE0, and that is what the
    file said. What nobody may do is invent the missing half -- encoding it without a base
    for section 1 is refused, by name.
    """
    wide = ("  Address         Publics by Name\r\n"
            "\r\n"
            " 0001:00000BE0       _main\r\n")
    got, unreadable = sym.parse(wide)
    assert [(s.name, s.section, s.offset) for s in got] == [("_main", 1, 0xBE0)], got
    assert unreadable == 0, unreadable
    with pytest.raises(sym.BadSymbolText, match="section 1"):
        sym.encode(sym.plan(got), section_bases={2: 0x400000})
    # AND A FLAT BASE DOES NOT QUIETLY SERVE A SECTIONED SYMBOL: that collapse is what
    # keeping the section makes impossible.
    with pytest.raises(sym.BadSymbolText, match="section 1"):
        sym.encode(sym.plan(got), 0x400000)


def test_the_16_bit_path_is_untouched_by_the_section_table() -> None:
    """THE CONTROL FOR THE WHOLE PHASE: a real-mode map has no such table, so reading one
    must change nothing about it.

    Without this, a 32-bit reader that swallowed the 16-bit path -- resolving `0D74` as a
    section index and finding nothing -- passes every case above it while every real map
    on this machine stops parsing.
    """
    assert sym._tlink_sections(TLINK_MAP.splitlines()) == {}
    at = {s.name: s.offset for s in sym.parse_tlink(TLINK_MAP)[0]}
    assert at["ACTIVEIMAN"] == 0x0D74 * 16 + 0x00E21
    assert at["ANIMPLANE"] == 0x1247 * 16 + 0x0DFEB
    assert len(at) == 3, at


def test_a_32_bit_map_that_printed_no_publics_says_so_too() -> None:
    """The two nothings again, for the generation that had neither.

    Its segment table carries no `Stop` column, so the 16-bit detector did not recognise
    it -- and a 32-bit map with no publics went to the `nm` parser and came back "no
    symbol lines were recognised in that text", about a linker map.
    """
    segments_only = ILINK32_MAP.split("  Address")[0]
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(segments_only)


# ------------------------------------------- what the review of the block above found
#
# Every case here exists because a BREAK came back GREEN against the cases before it,
# or because an auditor read a claim in the source that the code did not support. They
# are grouped so the reason they exist stays legible.


def test_a_32_bit_row_carries_the_mark_too_and_it_is_spelled_idle() -> None:
    """THE PRODUCT OF THE TWO FEATURES, which neither half's cases crossed.

    The mark had six cases on the real-mode branch and the 32-bit branch had none, so
    hardcoding that branch to `True` -- every symbol of every 32-bit map reported as
    carrying it -- was GREEN across the whole suite, and so was deleting the alternative
    from the pattern, since no 32-bit fixture row had one.

    AND THE SPELLING IS PART OF IT: ILINK32 writes `Idle`, and a lowercase pattern refuses
    every flagged row over the case of one letter while `parse` returns the rest with no
    exception raised.
    """
    at = {s.name: s.idle for s in sym.parse_tlink(ILINK32_MAP)[0]}
    assert at == {"_main": False, "_errno": False, "_g_count": True, "___xxInfo": False}, at
    # AND IT IS STILL KEPT, with its section and offset intact -- the mark must not have
    # become an exclusion on this branch either.
    where = {s.name: (s.section, s.offset) for s in sym.parse_tlink(ILINK32_MAP)[0]}
    assert where["_g_count"] == (2, 0x000022D4), where
    # THE LOWERCASE SPELLING IS NOT ACCEPTED, which is the half that keeps this reader
    # evidence about a particular linker rather than about linkers in general.
    lower = ILINK32_MAP.replace(" Idle _g_count", " idle _g_count")
    assert lower.count(" idle _g_count") == 2, "the substitution did not reach both tables"
    got, unreadable = sym.parse_tlink(lower)
    assert unreadable == 2, unreadable
    assert "_g_count" not in [s.name for s in got], got


def test_the_overlay_count_is_a_count_and_not_a_flag() -> None:
    """`== 1` ACCEPTS `True`, so every assertion on this counter was satisfied by a bool.

    Replacing `sum(...)` with `any(...)` left the entire suite green: `True == 1` and
    `False == 0`, and mypy is happy because `bool` subclasses `int`. On a real map with
    dozens of flagged symbols the tool would then report 1, and the number is the whole
    point of the field.

    The axis is VALUE, not presence, and it needed a fixture with TWO flagged symbols:
    with one, a count and a flag are indistinguishable by construction.
    """
    two = TLINK_MAP.replace(" 0459:00123       ACTIVE_CLS\r\n",
                            " 0459:00123 idle  ACTIVE_CLS\r\n")
    p = sym.plan(sym.parse_tlink(two)[0])
    assert p.overlay_idle == 2, p
    # AND IT IS AN `int`, not a `bool` that compares equal to one. `isinstance(True, int)`
    # is True, so the type has to be excluded by name.
    assert not isinstance(p.overlay_idle, bool), type(p.overlay_idle)


def test_an_overlay_count_that_is_not_a_subset_of_kept_is_refused() -> None:
    """The relation the whole design rests on, enforced instead of asserted ABOUT.

    Keeping `overlay_idle` out of `check()`'s partition is justified in three separate
    comments by it being a SUBSET of `kept`. Nothing enforced that, so `overlay_idle`
    could exceed `kept` and `check()` accepted it -- and this class's own standard, in
    the paragraph above the distinctness test, is that a guarantee living only in a test
    holds until somebody edits the function without running that test.
    """
    p = sym.plan(sym.parse_nm("0016df20 T _main\n"))
    assert p.kept == 1 and p.overlay_idle == 0, p
    p.check()                      # the control: it passes before being broken
    p.overlay_idle = 2
    with pytest.raises(sym.BadSymbolText, match="not a subset"):
        p.check()


def test_a_section_row_the_reader_cannot_parse_does_not_truncate_the_table() -> None:
    """The amputation, arriving a second time in a new walk.

    The publics walk learned to tell "the section ended" from "a symbol vanished" and to
    step over the second. This walk `break`s at the first non-match wherever it is, so a
    single malformed row -- a missing class column, a seven-digit start -- discarded
    every section defined AFTER it. The publics of those sections were then refused, and
    the refusal blamed a section table that is visibly in the file.
    """
    rows = [" Start         Length     Name               Class",
            "",
            " 0001:00401000 0000214D4H _TEXT              CODE",
            " 0004:00500000 00000010H _STACK",
            " 0002:00423000 0000059B8H _DATA              DATA"]
    got = sym._tlink_sections(rows)
    assert got == {1: 0x00401000, 2: 0x00423000}, got
    # AND THE WALK STILL ENDS, or the fix is "read the whole file": a line that does not
    # even OPEN like a section row is the table finishing.
    ended = sym._tlink_sections([*rows[:3], "Detailed map of segments",
                                 " 0002:00423000 0000059B8H _DATA              DATA"])
    assert ended == {1: 0x00401000}, ended


def test_only_the_first_section_table_is_read() -> None:
    """Two maps concatenated resolve the second unit's symbols against the FIRST unit's
    bases: plausible addresses, wrong program, nothing counted.

    An outer walk that continues past a table it has already read merges every later one
    into the same dict.
    """
    h = " Start         Length     Name               Class"
    got = sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE",
                               "", h, "", " 0002:00800000 0000059B8H _DATA DATA"])
    assert got == {1: 0x00401000}, got


def test_a_repeated_section_index_keeps_the_row_that_came_first() -> None:
    """Documented behaviour with no case: `setdefault`, so a later row cannot move
    symbols already resolved against the earlier value.

    The axis is ORDER. Swapping it for a plain assignment reproduced every other fixture
    exactly, because none of them names an index twice.
    """
    h = " Start         Length     Name               Class"
    got = sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE",
                               " 0001:00800000 0000214D4H _TEXT CODE"])
    assert got == {1: 0x00401000}, got


def test_a_section_length_in_lowercase_hex_is_still_a_section() -> None:
    """One literal `H` among four case-insensitive hex classes, and it fails TOTALLY.

    An empty section table sends every publics row of that map down the refusal path, so
    a map printing `0000214d4h` was refused whole -- and told its reader the section
    table was missing, about a file that has one.
    """
    h = " Start         Length     Name               Class"
    assert sym._tlink_sections([h, "", " 0001:00401000 0000214d4h _TEXT CODE"]) \
        == {1: 0x00401000}
    assert sym._tlink_sections([h, "", " 0001:00401000 0000214D4H _TEXT CODE"]) \
        == {1: 0x00401000}



def test_a_short_offset_in_a_file_that_has_a_section_table_is_refused() -> None:
    """The MIRROR of the rule that a long row in a file with no section table is a section
    index.

    A four-or-five-digit row is folded `seg * 16 + off`, which is right for a real-mode
    map and wrong in a file whose own section table says its left column is an index --
    0xBF0 for a symbol that file puts elsewhere entirely, a "plausible small address
    bearing no relation to the program" produced with every counter clean.

    THE ARGUMENT IS NOW A BOOLEAN, and that is the model change showing through: what
    this branch ever needed from the table was WHETHER THERE IS ONE, never what it said.
    Passing the table itself invited the reading that its VALUES mattered here, which is
    exactly the belief the real artefact refuted.
    """
    assert sym._tlink_place(" 0001:00BE0       _main", True) is None
    # THE CONTROL: with no section table there is nothing to be ambiguous with, and the
    # row is real-mode by construction. Refusing it there would break every real map.
    assert sym._tlink_place(" 0001:00BE0       _main", False) == (
        "_main", sym.FLAT, 0x0BF0, False)


def test_an_nm_file_carrying_four_ordinary_words_is_not_a_borland_map() -> None:
    """A MISREAD the 32-bit shapes invite, and the branch RAISES so there is no recovery
    from it.

    `Start Stop Length Name Class` is five words including `Stop` and is not a sentence
    anything else writes. `Start Length Name Class` is four ordinary English words, so a
    sniff on that line alone refuses any file carrying it and no `Publics by` header as a
    Borland map -- including readable `nm` output, which must parse. The header has to
    have a section ROW under it.
    """
    text = "0016df20 T _main\n Start   Length   Name   Class\n0005c830 T _engine_load\n"
    got, _ = sym.parse(text)
    assert [s.name for s in got] == ["_main", "_engine_load"], got
    # THE CONTROL, so the fix is not "never refuse": a real 32-bit map that printed no
    # publics still gets told so.
    with pytest.raises(sym.BadSymbolText, match="no `Publics by ...` header"):
        sym.parse(ILINK32_MAP.split("  Address")[0])


# --------------------------------------------------------------------- the anchored walk
#
# The ONE walk the readers share, tested where it lives rather than only through the
# format that uses it. The accounting below -- step over a row you cannot read, and COUNT
# it -- is the whole reason it is shared: two copies of it can go wrong separately.

_WALK = sym.Anchored(header=re.compile(r"^HEAD$", re.M),
                     row_shaped=re.compile(r"^ROW"))


def _digits(row: str) -> int | None:
    """A row is readable when it is `ROW <number>`. Anything else that starts `ROW` is
    row-shaped and unreadable; anything else at all ends the section."""
    return int(row[4:]) if row.startswith("ROW ") and row[4:].isdigit() else None


def test_the_walk_steps_over_an_unreadable_row_instead_of_ending_the_section() -> None:
    """THE DEFECT THIS EXISTS TO PREVENT, and it is not hypothetical: a walk that BREAKS
    at the first row it cannot read, wherever that row is, amputates the section.

    On a four-symbol section with one bad row third, one symbol comes back, `unreadable`
    reports 0, and the accounting check accepts the result as a complete, loadable table.
    Truncation reported as completeness is the exact failure this module is written
    against.
    """
    lines = ["HEAD", "ROW 1", "ROW bad", "ROW 3", "ROW 4"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 3, 4], rows
    assert bad == ["ROW bad"], bad


def test_the_walk_counts_the_row_it_stepped_over_and_does_not_drop_it_in_silence() -> None:
    """The count is `len()` of the ROWS, so the two cannot describe different populations
    -- which a counter kept beside a separate list eventually does."""
    lines = ["HEAD", "ROW 1", "ROW x", "ROW y", "ROW 2"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 2], rows
    assert len(bad) == 2 and bad == ["ROW x", "ROW y"], bad


def test_a_line_that_is_not_row_shaped_ends_the_section_and_is_not_counted() -> None:
    """"The section ended" and "a row vanished" are different facts, and the walk cannot
    report an amputation without telling them apart. A trailer is not a loss."""
    lines = ["HEAD", "ROW 1", "Program entry point at 0000:0000", "ROW 2"]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1], rows
    assert bad == [], bad


def test_a_blank_line_neither_ends_the_section_nor_counts_as_a_loss() -> None:
    """TLINK puts one between a header and its rows. Treated as an ending, every walk
    stops at its first line; treated as a loss, every gap is reported as an amputation."""
    lines = ["HEAD", "", "ROW 1", "", "ROW 2", ""]
    (rows, bad), = sym._anchored_sections(lines, _WALK, _digits)
    assert rows == [1, 2], rows
    assert bad == [], bad


def test_the_walk_yields_one_result_per_section_and_does_not_merge_them() -> None:
    """The two callers want opposite things and neither gets a flag to say so.

    The publics walk wants EVERY matching section, because a Borland map prints its
    publics twice and the two are one set. The section-table walk wants only the FIRST,
    because two tables merged into one namespace resolve the second unit's symbols
    against the first unit's bases -- plausible addresses, wrong program, nothing
    counted. Yielding per section is what lets each take what it needs.
    """
    lines = ["HEAD", "ROW 1", "-", "HEAD", "ROW 2", "ROW bad"]
    got = list(sym._anchored_sections(lines, _WALK, _digits))
    assert [rows for rows, _ in got] == [[1], [2]], got
    assert [bad for _, bad in got] == [[], ["ROW bad"]], got


def test_the_walk_is_lazy_so_a_caller_that_wants_one_section_walks_only_that_one() -> None:
    """It is not an optimisation, it is what makes "the first table is the table" hold
    without a flag: `next()` takes one and the rest of the file is never visited."""
    seen: list[str] = []

    def watched(row: str) -> int | None:
        seen.append(row)
        return _digits(row)

    lines = ["HEAD", "ROW 1", "-", "HEAD", "ROW 2"]
    first = next(sym._anchored_sections(lines, _WALK, watched))
    assert first == ([1], []), first
    assert "ROW 2" not in seen, seen


def test_a_file_with_no_matching_header_yields_nothing_rather_than_an_empty_section() -> None:
    """An empty section and a file that has none are different facts; a caller that
    cannot tell them apart reports "this map has no symbols" about a map it never
    found the symbols of."""
    assert list(sym._anchored_sections(["ROW 1", "ROW 2"], _WALK, _digits)) == []


def test_two_unreadable_rows_in_one_section_are_counted_as_two_and_not_as_one() -> None:
    """THE COUNT IS OF ROWS AND NOT OF SECTIONS, which is a distinction nothing here
    could see until this case existed.

    MEASURED as a surviving break: replacing `unreadable += len(bad)` with
    `unreadable += 1 if bad else 0` left the whole suite green AND the five real maps
    byte-identical -- because every one of them reads with `unreadable = 0`, so a
    per-section count and a per-row count agree everywhere the control can look. A
    section losing five symbols would then have reported one.

    THE ROWS ARE ASSERTED BESIDE THE COUNT, on purpose: the count is the number a caller
    reads and the rows are what makes it actionable, and a break that moves one without
    the other is exactly what this pins.
    """
    two_bad = TLINK_MAP.replace(
        " 0459:00123       ACTIVE_CLS\r\n 1247:0DFEB       ANIMPLANE\r\n",
        " 0459:1FFFF       ACTIVE_CLS\r\n 1247:FFFFF       ANIMPLANE\r\n", 1)
    assert two_bad != TLINK_MAP, "the substitution matched nothing, so this tests nothing"
    report = sym.ParseReport()
    got, unreadable = sym.parse_tlink(two_bad, report)
    assert [s.name for s in got] == ["ACTIVEIMAN", "ACTIVE_CLS", "ANIMPLANE"], \
        [s.name for s in got]
    # TWO in the FIRST section (the by-Name one); the by-Value section still holds the
    # good rows, which is why the symbols above survive.
    assert unreadable == 2, unreadable
    assert [r.strip() for r in report.unreadable_rows] == [
        "0459:1FFFF       ACTIVE_CLS", "1247:FFFFF       ANIMPLANE"], report.unreadable_rows


def test_a_watcom_section_with_no_readable_row_refuses_and_does_not_return_empty() -> None:
    """EMPTY IS AN ERROR, never an empty list -- this module's rule, applied to the
    fourth format.

    A file that parsed to nothing and a program with no symbols are different facts, and
    returning `[]` for both is the "instrument that examined nothing reporting a clean
    result", which says nothing true.

    IT CALLS THE READER DIRECTLY, on purpose. `parse` never reaches here with nothing,
    because `looks_like_watcom` requires a readable row before it will claim a file --
    so the refusal is unreachable through the front door and reachable through this one,
    which is a public function. MEASURED as a surviving break: deleting the refusal left
    the whole suite green.
    """
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
    """The SAME NAME at the same offset in DIFFERENT sections is TWO symbols.

    THE FIRST VERSION OF THIS CASE DID NOT BITE, and the reason is worth keeping: it used
    two DIFFERENT names, so `(name, offset)` separated them perfectly well and dropping
    the section from the key changed nothing. MEASURED -- both readers survived that
    break green. The collision needs the name to be equal, which is the only thing the
    section is left deciding.

    On these formats it is not hypothetical: the sections OVERLAP. Every section of the
    real Borland 32-bit map starts at 0 and a Watcom map's sections 1 and 2 both do, so
    equal offsets across sections are ordinary rather than rare -- and a linker that
    emits a name in two sections then loses one of them with every counter clean.
    """
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

    # AND A GENUINE REPEAT IS STILL ONE SYMBOL, or the key would have stopped
    # de-duplicating rather than started distinguishing. This is the half that keeps a
    # Borland map's two publics sections from doubling every name.
    twice, _ = sym.parse_watcom(watcom + "0001:00000010  twice_over\r\n")
    assert len(twice) == 2, twice




def test_a_section_most_of_which_was_discarded_is_refused_and_not_returned() -> None:
    """THE KNOWN ANSWER, and it is the real defect rather than an invented one.

    A real ILINK32 map read with the wrong case for its `Idle` mark loses more rows than it
    keeps, and `parse` raises nothing: a caller who does not read the second return value
    gets a well-formed list, a plan whose buckets add up, and a table that loads clean, about
    a file the reader understood a minority of.

    THE SHAPE IS BUILT HERE rather than read off tests/fixtures/borland-ilink32, which keeps
    four publics: the proportion is what matters and it is what this builds, more rows lost
    than kept.
    """
    rows = "".join(f" 0001:0000{i:04X}  Idle _flagged{i}\r\n" for i in range(6))
    rows += "".join(f" 0001:0001{i:04X}       _plain{i}\r\n" for i in range(4))
    lower = rows.replace("Idle", "idle")   # the spelling this reader does NOT accept
    with pytest.raises(sym.BadSymbolText, match="MORE WAS DISCARDED THAN KEPT") as e:
        sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + lower)
    assert "6 rows this could not read" in str(e.value), str(e.value)
    assert "only 4 it could" in str(e.value), str(e.value)

    # THE CONTROL, and without it this asserts nothing about the ratio: the SAME rows
    # spelled the way the linker really spells them read clean, all ten of them. So the
    # refusal is about the proportion lost and not about the file being unusual.
    got, unreadable = sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + rows)
    assert len(got) == 10 and unreadable == 0, (len(got), unreadable)


def test_a_minority_loss_is_still_returned_with_its_count_and_not_refused() -> None:
    """THE OTHER SIDE OF THE BAR, and it is what keeps the guard from being a blanket
    refusal.

    A file with one bad row among many is a file worth reading, and the module's own
    idiom applies: a bucket that keeps the table TRUE beside a count that keeps the loss
    VISIBLE. Refusing here would throw away nine good symbols over one bad row.
    """
    rows = "".join(f" 0001:0000{i:04X}       _plain{i}\r\n" for i in range(9))
    rows += " 0459:1FFFF       _too_wide\r\n"
    got, unreadable = sym.parse_tlink("  Address         Publics by Name\r\n\r\n" + rows)
    assert len(got) == 9, got
    assert unreadable == 1, unreadable


def test_the_ratio_does_not_bind_the_flat_readers_where_it_would_refuse_every_gnu_map() -> None:
    """THE PER-FORMAT HALF, and it is the load-bearing one.

    For an ANCHORED reader `unreadable` counts lines INSIDE a symbol section that LOOK
    like rows, so every one is a symbol lost. For a FLAT reader it counts every line that
    did not match, and a GNU `ld` map is MOSTLY not symbols by construction -- MEASURED
    on this package's own fixture, 912 unmatched against 228 symbols. One ratio over both
    would refuse every GNU map ever written, which is a guard that breaks the thing it
    was meant to protect.
    """
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
    """THE ORDINARY CALL, and the coverage ratchet is what noticed it was missing.

    `report` is optional and every Watcom case written so far passed one, so the branch
    an ordinary caller takes -- `parse(text)`, two return values, no diagnostics -- had
    never run. A `None` there is not a detail: it is what `symbols_load` itself would do
    if it stopped asking for a report.
    """
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
    """THE WORST THING THIS MODULE CAN DO, and it did it: hand one symbol's EXACT,
    complete, untruncated name to a DIFFERENT symbol at a different address.

    The reservation pass keyed on the STEM -- `stems.count(s) == 1` -- and a name that
    fits in fifteen characters is NOT a unique stem when some longer name truncates onto
    it, which by this module's own measurement is the normal case (35.7% of names are
    longer than the field). So nothing protected it and the longer name took it.

    MEASURED: `["abcdefghijklmnoXYZ", "abcdefghijklmno"]` came back with the FIRST named
    `abcdefghijklmno`. Every counter clean, `check()` satisfied -- the names were
    distinct, after all -- and somebody typing the real name lands on the wrong function.
    That is the "name that LIES", which this module says is worse than a missing one.

    AND IT WAS ORDER-DEPENDENT, so the same program linked in a different order gave a
    different answer and one of the two was silently wrong. Both orders are asserted
    here for that reason.
    """
    for order in (["abcdefghijklmnoXYZ", "abcdefghijklmno"],
                  ["abcdefghijklmno", "abcdefghijklmnoXYZ"]):
        got, _, _ = sym._disambiguate(order)
        short_at = order.index("abcdefghijklmno")
        assert got[short_at] == "abcdefghijklmno", (order, got)
        assert got[1 - short_at] != "abcdefghijklmno", (order, got)
        assert len(set(got)) == 2, got


def test_two_symbols_that_genuinely_share_a_whole_name_are_still_told_apart() -> None:
    """THE MIRROR, and it is what stops the fix above becoming a different defect: a
    name that fits is reserved, but two symbols really carrying the SAME name is a
    genuine collision and the second must still be renamed."""
    got, _, disambiguated = sym._disambiguate(["_helper", "_helper", "_helper"])
    assert got[0] == "_helper", got
    assert len(set(got)) == 3, got
    assert disambiguated == 2, disambiguated


def test_find_by_offset_does_not_answer_out_of_a_different_section() -> None:
    """A DECISION-36 REGRESSION, caught by an adversarial reading and not by any test.

    Before it, every producer folded its offsets into ONE space and comparing them across
    the whole list was sound. The two sectioned readers broke that precondition and this
    function was not revisited -- and these formats' sections OVERLAP, so the situation
    is ordinary rather than contrived.

    MEASURED: `[_main @ 1:0x10, _dataend @ 2:0x20]` asked about 0x100 answered
    `_dataend +0xE0` -- a symbol from a different selector, with a plausible delta and no
    error, when `_main` was the only right answer.
    """
    table = [sym.Symbol("_main", 0x10, section=1),
             sym.Symbol("_dataend", 0x20, section=2)]
    got = sym.find_by_offset(table, 0x100, 1)
    assert got is not None and got[0].name == "_main", got
    assert got[1] == 0xF0, got
    other = sym.find_by_offset(table, 0x100, 2)
    assert other is not None and other[0].name == "_dataend", other
    # A SECTION NOBODY IS IN COMES BACK EMPTY, which is a refusal rather than the nearest
    # symbol of some other section.
    assert sym.find_by_offset(table, 0x100, 3) is None
    # AND THE FLAT DEFAULT DOES NOT REACH SECTIONED SYMBOLS: a caller that forgot the
    # argument gets nothing back rather than a confident wrong answer.
    assert sym.find_by_offset(table, 0x100) is None


def test_a_parse_report_may_not_be_used_for_two_reads() -> None:
    """Every writer APPENDS to `unreadable_rows` while `fmt` is OVERWRITTEN, so a report
    handed to two reads described the SECOND file's format and BOTH files' lost rows --
    while the comment on that field says the count and the rows cannot disagree.

    MEASURED: two reads of a one-bad-row section left `len(unreadable_rows) == 2` and
    `parse` returned 1.
    """
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
    # A FRESH ONE IS FINE, or the guard would have made the object single-use per process
    # rather than per read.
    again = sym.ParseReport()
    _, u2 = sym.parse(text, again)
    assert u2 == len(again.unreadable_rows) == 1, again.unreadable_rows


def test_the_var_list_s_count_takes_its_edges() -> None:
    """An empty list is two bytes and decodes to nothing; two batches joining to exactly the
    count the file holds load, one more is refused."""
    assert sym.decode(b"\0\0") == []
    with pytest.raises(sym.BadSymbolText):
        sym.decode(b"\0")
    full = struct.pack("<H", 0xFFFF)
    assert struct.unpack_from("<H", sym.joined(full, b"\0\0"))[0] == 0xFFFF
    with pytest.raises(sym.BadSymbolText):
        sym.joined(full, struct.pack("<H", 1))
