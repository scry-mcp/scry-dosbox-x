"""Names for addresses: a toolchain's TEXT symbol list turned into the debugger's own.

WHY THIS EXISTS.  DOSBox-X's debugger does have a symbol facility -- `IV` names an
address, `SV` saves the list, `LV` loads one -- and it is easy to assume it has none,
which is the kind of false premise that makes the next reader design the wrong thing.
What it has no route for is getting THOUSANDS of names in: `IV` is one address typed at
a console, and it UPPERCASES what you type, so a C symbol table cannot be entered that
way even with patience.

WHAT IT DELIBERATELY DOES NOT DO: parse a binary.  It reads TEXT -- `nm` output, a
GNU `ld` link map, and the `Publics by ...` section of a Borland TLINK/TASM map --
because the alternative is a generic server learning COFF, then TDS, then DWARF, one
toolchain at a time.  Every DOS toolchain emits one of these three from a tool that
already knows its own format, and a stranger installing this pack can produce one
without this code knowing anything about their compiler.

THE FORMAT IS DOCUMENTED NOWHERE but in the debugger's own source (`CDebugVar::SaveVars` and
`LoadVars` in DOSBox-X's `src/debug/debug.cpp`) -- not in `README.debugger`, not in the
doxygen.  So it was also OPENED AND READ, by naming three addresses through the console
and saving them:

    IV 1234:5678 MYSYMBOL   ->  0300  "MYSYMBOL"...  b8 79 01 00
    IV 0:0 zero_lower       ->        "ZERO_LOWER"..  00 00 00 00
    IV A000:1F ABC...789    ->        "ABCDEFGHIJKLMNO"  1f 00 0a 00

    u16 LE   count
    count x  char[16]  name, NUL-padded
             u32 LE    LINEAR address

`1234:5678` stored as `0x000179B8` is `0x12340 + 0x5678`, so the address is LINEAR and
not the seg:off that was typed; `A000:001F` -> `0x000A001F` and `0000:0000` -> `0`
agree.  62 bytes for three records is `2 + 3*20` exactly.

FIVE MORE FACTS OF THE FORMAT, each of which decides something here:

- **The name field is 16 bytes, so 15 usable characters.**  `ABCDEFGHIJKLMNOPQRSTUV...`
  comes back as `ABCDEFGHIJKLMNO`.  In a real C program a large share of the names are
  longer than that, so truncation is the normal case and not an edge case, and
  truncating blindly loses many of them to collisions (every generated variant of
  an inner loop collapses onto one name).  Hence `_disambiguate`.
- **`IV` uppercases its argument; the FILE does not.**  `zero_lower` typed at the
  console is stored `ZERO_LOWER`, but a file written here holding `lower_case_sym` loads
  back byte-identical.  That is the whole reason this can carry C symbols at all.
- **`LV` APPENDS** (tests/fixtures/symbols-lv: a second load leaves both).  So a caller
  reloading a list gets both, and the round-trip count is a floor rather than an
  equality.
- **A `SV`/`LV` filename is TRUNCATED TO 12 CHARACTERS, SILENTLY, and reported `ok`.**
  `SV ABCDEFGHIJKLMNOPQRST.BIN` answers `ok` and writes the file as `ABCDEFGHIJKL`, no
  extension.  An absolute path fails the same way and at least says
  so (`/private/tmp/...` -> `Variable list save (/PRIVATE/TMP) : failure`).  Hence
  `SYM_ARG_MAX` in `dosbox_session.py` -- beside the two names actually sent, which is
  the only module that builds one -- and hence the caller of this module verifying the
  file it expected really appeared.
- **One load is capped by the format's own `u16` count and nothing lower**, and a
  session's loads together by what the debugger's `SV` can save back (`COUNT_MAX`,
  judged in `dosbox_symbol_file`), because `LV` appends.

WHAT THE NAMES ARE ACTUALLY GOOD FOR, said plainly because it is narrower than it
sounds: the debugger substitutes a name into the OPERAND of a memory reference
(`xor [ZERO_LOWER],dh`), not as a label on the instruction line.  So a code symbol does
not caption its own function in the code pane.  Resolving a name to an address, and an
address back to the nearest name, is this module's `find` half and runs here, on the
full untruncated table, where neither limit applies.

A FOURTH FORMAT, OPEN WATCOM'S MAP, opens its symbol section `Address        Symbol`,
its segment table
`Segment Class Group Address Size`, and a row carries a mark GLUED to the address
(`0001:00000015s helper_`; `s` static, `*` unreferenced, `+` referenced only locally, or
a space).

THE ADDRESS MODEL IS SECTIONED, AND A FLAT BASE IS THE SPECIAL CASE. Placing by adding
ONE flat `base` to an offset cannot read a Watcom map: it carries NO flat address
anywhere.  Its sections'
offsets OVERLAP -- 1 and 2 both start at 0 -- so one base folds two distinct symbols
onto one linear address, and under DOS/4GW those left-hand numbers are SELECTORS
assigned at load time, not paragraphs, so `section * 16` invents an address rather than
reading one.  The linker's own manual agrees in the one sentence it spends on the
subject: the map "specifies the RELATIVE location of all global symbols".

SO THE CONTRACT CHANGED INSTEAD OF THE READER BEING REFUSED.  A `Symbol` keeps
`(section, offset)` and placement is a separate step taking a base PER SECTION
(`resolve_bases`, `place`, `encode(..., section_bases=...)`).  A flat format is the
degenerate case -- one section, one base -- so this is one code path where there were
going to be two.

AND THE BORLAND 32-BIT READER IS THE SAME PROBLEM.  A Borland section table looks as
if it gave a section's start as a FULL address (`0001:00401000`), so that `start +
offset` were placeable with one base; a real ILINK32 map says otherwise: its `Start`
column reads `0001:00000000`, `0002:00000000`, `0003:00000000`, so a reader trusting it
builds `{1: 0, 2: 0, 3: 0}` and folds every section onto one address space, every
symbol plausible and every one on top of the others.  Both formats need the same table
from the same place.

THE BASES EXIST, JUST NOT IN THE MAP.  They are in the LINKED IMAGE: a DOS/4GW
executable is `LE`, and its object table gives each object a virtual size and a
relocation base, and those sizes agree with the map's own segment arithmetic, which is
what says the two files describe one program.  Reading binaries is the one thing this module
refuses to do, so those numbers come from the caller.  Whether a live descriptor read
can substitute is NOT known: under DOS/4GW's flat model the selectors may well share
one base while the objects sit at different offsets inside it, in which case a
descriptor answers a different question.  Unknown is written here as unknown.

Two real maps built from one source under DOSBox-X by Open Watcom 2.0 and Watcom C/C++
10.0a, linkers decades apart, carry the SAME layout, so this is a
stable target rather than a moving one.  And the manual documents the MAP and STATICS
options while specifying NOTHING about the map's columns or those marks, so the format's
only authority is the artefacts.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import TypeVar

# The record layout (see the module docstring). They are named rather than
# spelled inline because the encoder and the decoder must agree, and a decoder written
# against a remembered number is how a round-trip check passes over the wrong bytes.
NAME_FIELD = 16
NAME_MAX = NAME_FIELD - 1
ADDR_FIELD = 4
RECORD = NAME_FIELD + ADDR_FIELD
# THE COUNT IS A u16, AND IT BOUNDS THE DEBUGGER'S WHOLE LIST TOO: `SV` refuses to save a list
# longer than it (`CDebugVar::SaveVars` in DOSBox-X's `src/debug/debug.cpp`), and nothing but the
# emulator's shutdown empties the list (`CDebugVar::DeleteAll`), so every `LV` of a session adds
# to one holding that has to stay under it to be read back.
COUNT_MAX = 0xFFFF
ADDR_MAX = 0xFFFFFFFF

# THE SECTION INDEX OF A FORMAT THAT HAS NO SECTIONS. Negative because every one of
# these formats prints its index as unsigned hex, so no map can produce it -- which
# is what makes "a sectioned symbol was handed a flat base" a REFUSAL rather than a
# collision. Zero is not available: a Watcom map really does emit section 0.
FLAT = -1

# THE FIELD IS BYTES AND THE DEBUGGER CUTS A NAME AT THE FIRST NUL, so "encodable as
# ASCII" is NOT the gate this needs and was measurably not it: `_a\0b` and `_a\0c` are
# different Python strings, so `check()` called them distinct, and both decoded to `_a`
# -- two addresses under one visible name, which is the exact thing `check()` promises
# cannot happen. The gate is PRINTABLE ASCII, which makes string distinctness and byte
# distinctness the same question, and it rejects the empty name for the same reason: a
# record whose whole name field is padding names nothing.
PRINTABLE = re.compile(r"\A[\x20-\x7E]+\Z")

# THE FILENAME LIMIT DOES NOT LIVE HERE. A copy of it in this module would be the SAME
# CONSTANT UNDER A SECOND NAME, because the limit governs a FILENAME and this module
# builds none. The one that does the work
# is `SYM_ARG_MAX` in `dosbox_session.py`, beside the two names actually sent, used by
# the three places that check them and pinned by a test. Two names for one decision is
# the shape a clone detector cannot see and the shape that diverges silently, so the
# copy is gone rather than cross-referenced.

# `nm` prints `<addr> <type> <name>`, and an UNDEFINED symbol prints `        U name`
# with no address at all. The width is not assumed: a 64-bit `nm` prints sixteen digits
# for the same file, and pinning eight would silently match nothing there: a broken
# instrument reporting a clean result.
# `re.M` is not decoration: `_parse` walks line by line, where it changes nothing, but
# `looks_like_map` counts matches across the WHOLE text -- and without it `^` anchors
# only at the start of the string, so both counts would be 0 and the sniff would always
# answer "nm output". The case that asserts a link map IS recognised holds it; the mirror
# case (`nm` output is not a map) would pass either way, on `0 > 0`.
_NM = re.compile(r"^\s*([0-9a-fA-F]{4,16})\s+([A-Za-z])\s+(\S+)\s*$", re.M)

# GNU `ld --print-map` puts an address and a name on one line, the address `0x`-prefixed
# and the name in the second column. Anything else on the line (a section header, a fill,
# an archive member) does not match, which is the intent: this reads what it recognises
# and REPORTS the rest rather than guessing.
_MAP = re.compile(r"^\s+0x([0-9a-fA-F]+)\s+(\S+)\s*$", re.M)

# BORLAND: the `Publics by ...` section header of a TLINK/TASM map, and one row of it.
#
# THE HEADER IS THE ANCHOR AND THE ROW SHAPE IS NOT, which is the whole of why this
# works. In a real TLINK map the "Detailed map of segments" section ALSO opens every
# line with a `seg:off` pair --
#
#     0000:0000 0036 C=CODE   S=SFMAIN_TEXT    G=(none)  M=SFMAIN.ASM ACBP=48
#
# so a pattern matching the LINE would take the last token and emit a symbol called
# `ACBP=48`, ten of them, silently, in a table that then loads clean. Reading only what
# follows a `Publics by` header excludes that section by construction.
#
# `[ \t]` AND NEVER `\s`, in all three of these. `\s` matches a NEWLINE, and with
# `re.M` a `search` for `^\s*Address\s+Publics by \w+\s*$` therefore matches the
# two-line text "Address\nPublics by Name\n" -- so `looks_like_tlink` said yes to a
# file with no section in it, while `parse_tlink`'s per-line `match` said no, and
# `parse()` refused an ordinary file with a message about Borland. The sniff and the
# walk have to ask the SAME question, and `\s` makes one of them ask a looser one.
#
# THE HEADER MAY CARRY A TRAILING TOKEN. Ending the pattern at `\w+\s*$` lets anything
# after the section word kill the match, and in a map whose every `Publics by` header
# is annotated the reader then announces "it has NO `Publics by ...` section" about a
# file that visibly has one.
_TLINK_HEADER = re.compile(r"^[ \t]*Address[ \t]+Publics by[ \t]*\w+.*$", re.M)

# THE SEGMENT TABLE'S HEADER, which every Borland map opens with whether or not it went
# on to print any publics. It is what lets the two nothings be told apart: "this is a
# map I cannot read" and "this is a Borland map that carries no public symbols" are
# different facts, and the second is a statement about the LINK: a real map linked
# without `/m` opens with this header and has no `Publics by` section.
# `\r?$` AND NOT `[ \t]*$`: a Borland map is CRLF, and `re.M`'s `$` matches only before a
# `\n`, so a pattern without the `\r` misses every real map. That is why the fixture is
# kept with its line endings intact.
_TLINK_SEGMENTS = re.compile(
    r"^[ \t]*Start[ \t]+Stop[ \t]+Length[ \t]+Name[ \t]+Class[ \t]*\r?$", re.M)

# THE 32-BIT SEGMENT TABLE'S HEADER, which has NO `Stop` column -- that is what tells
# the two generations of this map apart, and it is not a guess: Embarcadero's own
# "Detailed-Segments Map File" page prints the 32-bit table as `Start Length Name Class`
# over rows like ` 0001:00401000 0000214D4H _TEXT  CODE`, while the 16-bit maps measured
# on this machine all carry `Start Stop Length Name Class`.
#
# IT IS AN ANCHOR AND NOT A LINE SHAPE, for exactly the reason spelled out above
# `_TLINK_HEADER`: the "Detailed map of segments" section ALSO opens every row with a
# `sect:offset` pair, so a pattern matching the LINE would take module rows for section
# definitions and build a table out of offsets INSIDE a section.
_TLINK_SECT_HEADER = re.compile(
    r"^[ \t]*Start[ \t]+Length[ \t]+Name[ \t]+Class[ \t]*\r?$", re.M)

# ` 0001:00000000 000008DCCH _TEXT                  CODE` -- a SECTION INDEX, the offset a
# segment of it begins at (zero for the first, and ILINK32 lists a section once per segment),
# its length, its name and its class.
#
# WHAT REFUSES A DETAILED-MAP ROW IS TWO GUARDS AND NEITHER OF THEM ALONE, which is
# worth stating precisely because the obvious reading is wrong in both directions. That
# row is ` 0001:00000108 0000004B C=CODE    S=_TEXT    G=(none)   M=HELLO32.C  ACBP=A9`: the
# same opening pair, a length with NO `H`, and FIVE trailing tokens where a section row
# has exactly two.
#
# So the `H` refuses it, AND the `$` anchoring those two tokens refuses it, and each is
# SUFFICIENT on its own: removing either one still refuses the row and only removing
# BOTH lets it through. A break of each in turn comes back GREEN, which is what a pair
# of sufficient guards looks like from the inside. Whoever deletes one of them will see
# nothing fail, and that is the reason this paragraph exists.
#
# `[Hh]` AND NOT `H`: every hex class beside it is case-insensitive, so a literal
# uppercase `H` was the one character in the row asserting a case nothing else does --
# and it fails TOTALLY rather than partially, because an empty section table sends every
# publics row of that map down the refusal path. Whether a real linker prints `h` is not
# known here; that it would be refused for the case of one letter is enough.
_TLINK_SECTION = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})[ \t]+([0-9A-Fa-f]+)[Hh]"
    r"[ \t]+(\S+)[ \t]+(\S+)[ \t]*$", re.M)

# A LINE THAT OPENS LIKE A SECTION ROW WITHOUT BEING ONE THIS READER CAN PARSE, the
# counterpart of `_TLINK_ROW_ANY` and there for the identical reason: it separates "the
# table ended" from "a section vanished". Without it the walk breaks at the first row it
# cannot read, so one malformed line -- a missing class column, a seven-digit start -- takes
# every section defined after it, and the publics of those sections were then refused
# with the message blaming a table that is visibly in the file.
_TLINK_SECTION_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}\b")

# ` 0001:00000130       _main` -- the 32-bit publics row: a SECTION INDEX and an offset
# INSIDE that section, eight hex digits wide.
#
# THE INDEX IS PRINTED IN DECIMAL AND IS READ HERE AS HEX, AND THE ARGUMENT THAT THIS IS
# HARMLESS DOES NOT HOLD. The shipped linker's own format strings (`ILINK32.DLL`,
# Borland C++ 5.02) say so: the row is ` %04d:%p ` and the section row
# is the same `%04d:` pair, so an eleventh section prints `0011` meaning eleven while
# everything here reads 0x11.
#
# IT IS NOT A PRIVATE JOIN KEY: were the index used only between the publics and the
# section table, both parsed by the same rule, the two would agree on a wrong number and the
# address would still come out right. But the index is stored on `Symbol.section` and is the
# key a CALLER supplies in `section_bases`, reading the map's printed `%04d`. The two sides
# are not parsed by the same rule -- one of them is a person.
#
# THE LOUD CASE is a map with ten or more sections: its tenth row prints `0010`, this
# stores 16, and a caller's `{10: ...}` is refused naming a section 16 that appears
# nowhere in their file. THE SILENT ONE is a map carrying BOTH a decimal 10 and a decimal
# 16: `int("0010", 16)` is 16, so section 10's symbols are filed under 16 and placed with
# section 16's base, and `place` cannot tell an aliased key from a legitimate one. The
# same holds for (11,17), (12,18) and so on.
#
# NO REAL MAP AT HAND HAS TEN SECTIONS, so this is
# UNOBSERVED, and it is written as a question that went unanswered
# rather than fixed on reasoning. Fixing it means reading the index as DECIMAL on both
# sides, which is a change to what every existing caller's keys mean, and no artefact
# here can say whether it is right.
#
# THE WIDTH IS EXACTLY EIGHT and does not overlap `_TLINK_ROW`'s four-to-five, so the
# two never compete for a row. That is deliberate: a lone eight-digit row CANNOT be told
# from an odd 16-bit one by looking at it.
#
# WHAT THE SECTION TABLE IS FOR: not positioning. `_tlink_place` keeps
# `(section, offset)` and `place` refuses a section the CALLER has not positioned, by
# name. The table is consulted for one thing only, and it is a yes-or-no:
# whether this file HAS one, which is what tells a short row apart from an odd one.
#
# THE MARK IS `Idle`, WITH A CAPITAL I, as a real ILINK32 map writes it; a lowercase
# `idle` here would refuse every flagged row of such a map:
#
#     0001:000071D0       @$bdele$qpv          parsed
#     0001:0000085C  Idle @jump$qv             REFUSED
#
# Every flagged row of such a map would be refused for the case of one letter, and `parse`
# would return the rest as a plausible answer with no exception raised.
#
# SO THE MARK IS PER FORMAT AND NOT GLOBAL: TLINK 16-bit writes `idle`, ILINK32 writes
# `Idle`, and each pattern carries its own. Making the match case-insensitive would
# "fix" this file while quietly accepting a spelling neither linker produces, which is
# how a reader stops being evidence about any particular toolchain.
# AND THE FORMAT DESCRIBES A WIN32 PROGRAM, WHICH THIS DEBUGGER DOES NOT RUN. Said here
# because the reader is kept deliberately and a reader kept in silence is one somebody
# will trust for the wrong thing. ILINK32 produces this map for a Windows executable,
# and no DOS toolchain emits it.
#
# SO WHAT IT IS GOOD FOR IS NARROWER THAN "this package reads four formats": the names
# load and resolve, and then the program they describe is one DOSBox-X cannot stop in.
# Kept deliberately, with the reason: it reads without losing a row, and it is
# the only real evidence this format's shape exists at all -- a DOS program in the same
# format would be read correctly by the same code.
_TLINK_ROW32 = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})[ \t]+(Idle[ \t]+)?(\S+)[ \t]*$",
    re.M)

# ` 0D74:00E21 idle  ACTIVEIMAN` -- a real-mode segmented address, an OPTIONAL `idle`
# mark, and the name. WHAT THAT MARK MEANS IS NOT KNOWN; the evidence against the
# obvious reading is written ONCE, on `Symbol.idle`, rather than restated here where a
# second copy could drift from it.
#
# THE OFFSET IS 4 TO 5 HEX DIGITS: this linker pads it to five (`00E21`), which is one
# wider than the sixteen bits it holds, and a `{4}` would have matched nothing at all.
# The upper bound is NOT a claim that five is all any linker prints: a 32-bit map
# writes eight (`0001:00000BE0`), and such a row is REFUSED by `_TLINK_ROW_ANY` below
# rather than folded, because `seg * 16 + off` is meaningless for a section index.
#
# THE `idle` GROUP CAPTURES, so the name is `group(4)`. Turning it into `(?:...)` is
# one character and it MOVES EVERY GROUP AFTER IT: an `idle` row's name then comes
# back as the FLAG -- a symbol called `idle`, at a plausible address, in a table that
# loads clean. Nothing about the match fails, which is why the numbering is re-read at
# the call site rather than assumed.
_TLINK_ROW = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4,5})[ \t]+(idle[ \t]+)?(\S+)[ \t]*$",
    re.M)

# A LINE THAT LOOKS LIKE A ROW WITHOUT BEING ONE THIS READER CAN PARSE. It is what
# separates "the section ended" from "a symbol vanished", and without that distinction
# the walk below cannot report an amputation.
_TLINK_ROW_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4,}:[0-9A-Fa-f]+\b")

# Symbols that name a SECTION or a compiler-generated local label rather than anything a
# person would look up. They are excluded by DEFAULT and counted, never dropped in
# silence: in a real binary they are a large share of the table and `.text` alone appears
# hundreds of times, which would otherwise dominate the collision accounting and hide
# the real ones. `..@15.l0` starts with a dot too, so ONE alternative covers both
# classes; spelt out as `^(\.|\.\.@)` the second branch is unreachable because
# alternation is ordered, two rules on paper and one in fact.
_NOISE = re.compile(r"^\.")

# The `nm` type letters whose VALUE IS NOT AN ADDRESS, so no base can place them.
#
#   C  a COMMON symbol -- an uninitialised global the linker has not allocated yet.
#      The column holds its SIZE: `00004000 C _big_table` for `int big_table[4096]`,
#      which is 16384 bytes and not an address.
#   A  an ABSOLUTE symbol -- a constant that is not relative to any section, so it
#      moves with no base: `.set _PORT, 0x3F8` prints `000003f8 A _PORT`
#      for a serial-port number that is nowhere in the program.
#
#   a  a LOCAL absolute -- the same construct as `A` minus one `.globl`. Leaving it out
#      on the reasoning that the local absolutes of one binary are all dotted names
#      `_NOISE` already excludes is a fact about ONE binary standing in for a rule, and
#      it fails two ways: `000003f8 a _localport` has an ordinary name, so `_NOISE` never
#      sees it and it lands at base+0x3F8; and `keep_noise=True` -- a parameter of the
#      `symbols_load` TOOL -- switches `_NOISE` off entirely, at which point even the
#      dotted ones are placed.
#   N  a DEBUGGING symbol, whose column holds a section-relative offset: a linked
#      binary carries hundreds of them, every one named `.comment`, e.g.
#      `00002210 N .comment`. `_NOISE` alone would save them, so `keep_noise=True`
#      would place every one.
#
# THE CASE CARRIES THE BINDING AND NOT THE CLASS, which is why `a` belongs here beside
# `A`: local and global are both absolute, and absolute is what makes a value unplaceable.
#
# WHAT IS DELIBERATELY NOT IN THE SET, because no instance of it has been seen: `n`,
# `i`, `I`. Adding a letter on reasoning alone is the mistake described one letter up.
# The probe that would settle any of them is
# `nm <binary> | awk '$2=="n"'` against a real target; an empty answer is not a reason
# to add it. `U`, `w` and `v` need no entry at all: `nm` prints NO address for them, so
# `_NM`'s three-column shape refuses those lines and `_parse` counts them as unreadable.
_UNPLACEABLE = frozenset("CAaN")


@dataclass
class ParseReport:
    """What a DIAGNOSTIC caller needs and `parse`'s two return values cannot carry.

    `parse` answers with the symbols and HOW MANY lines it could not read, which is what
    a loader needs and all it needs.  A sweep across somebody's real maps needs two more
    things and neither fits in that pair: WHICH reader ran, and WHICH rows were lost.  A
    count says a population was amputated; the row says what the amputation was, and it
    is the only form in which it can be acted on: a large `unreadable` says nothing at all,
    while one quoted `Idle @jump$qv` row is the whole defect.

    IT IS AN OUT-PARAMETER AND NOT A THIRD RETURN VALUE, deliberately.  `parse`,
    `parse_tlink` and `_parse` are called from the server, from the other parsers and
    from sixteen places in the suite; widening their tuple would churn every one of them
    to serve a caller none of them is.  Filling an object the caller supplied leaves
    every existing signature and every existing test untouched, and there is still ONE
    walk -- which is the property that matters, because a second walk written to answer
    "which rows" is a second walk that can disagree with the first about how many.

    ONE REPORT PER READ, AND REUSING ONE IS REFUSED. Nothing cleared the list and nothing
    stopped a second use: every writer APPENDS to `unreadable_rows` while `fmt` is
    OVERWRITTEN, so a report handed to two reads described the SECOND file's format and
    BOTH files' lost rows: two reads of a one-bad-row file leave
    `len(unreadable_rows) == 2` while `parse` returns 1 -- and the comment on that field
    says in as many words that those two cannot disagree. A `default_factory` list on a
    public dataclass invites exactly that reuse, so this is a guard rather than a
    docstring asking people not to.
    """

    # The reader that ran, from the same dispatch that ran it, never re-sniffed by the
    # caller: `parse` chooses in a fixed order and a caller asking the sniffs again is a
    # copy of that order which drifts the day the order changes.
    fmt: str = ""
    # THE ROWS, in the order the walk met them. The COUNT is `len()` of this, so the two
    # cannot disagree -- which is exactly what a separate counter beside a separate list
    # would eventually do.
    unreadable_rows: list[str] = field(default_factory=list)
    # WHETHER A READ HAS ALREADY FILLED THIS ONE. Private, and checked by `_claim` below
    # rather than by every writer: one place to be wrong instead of four.
    _used: bool = False

    def _claim(self, fmt: str) -> None:
        """Take this report for ONE read, or refuse it."""
        if self._used:
            raise BadSymbolText(
                "this ParseReport has already been filled by another read. Reusing one "
                "leaves `fmt` describing the last file and `unreadable_rows` holding "
                "every file's, so the count a reader gets back and the rows beside it "
                "stop describing the same population. Make a new one per read")
        self._used = True
        self.fmt = fmt


class BadSymbolText(Exception):
    """The text handed in is not a symbol list this module can read.

    It is a distinct type rather than a `ValueError` so the MCP layer can translate it
    into a refusal that names the caller's file, instead of it escaping as a traceback
    with no session block.
    """


@dataclass(frozen=True)
class Symbol:
    """One name and the OFFSET it has inside its selector.

    It is deliberately not a linear address. A toolchain emits offsets; the base is a
    property of the LOADED process and is not knowable from the text. Keeping the two
    apart is what stops a file produced on one run being used against another.
    """

    name: str
    offset: int
    # WHICH SECTION THAT OFFSET IS INSIDE. `FLAT` (below, and it is -1) means "this
    # format has none".
    #
    # THE FILE GIVES THIS, AND FOLDING `base + offset` WHILE READING WOULD THROW IT AWAY:
    # a wrong base could not then be corrected without re-reading, the sectioned formats
    # would need a second code path, and a caller would receive a FOLDED address with no
    # way to tell it had been folded wrongly. A TLINK32 map shows why at once: its section
    # table reads `{1: 0, 2: 0, 3: 0}`, so a fold at read time puts every symbol at a
    # plausible address and every one of them on top of the others.
    #
    # A FLAT FORMAT IS THE DEGENERATE CASE, not a second path: one section, one base --
    # the `base` every caller already passes. `nm`, a GNU map and a REAL-MODE Borland
    # map all sit here, and the last of those is not an omission: a real-mode segment IS
    # a paragraph, so `seg * 16 + off` is arithmetic the file fully determines and not a
    # base anybody has to supply.
    #
    # THE FLAT SENTINEL IS `-1` AND NOT `0`, because 0 IS A REAL SECTION INDEX: an Open
    # Watcom map prints `0000:00001234  __DOSseg__`, section zero, beside rows in
    # sections 1 and 2. With 0 as the sentinel, that symbol would be
    # placed with a FLAT base handed in for some other file's benefit -- silently, and
    # at an address belonging to nothing. A negative index is one no map can print,
    # because every one of these formats prints it as unsigned hex.
    #
    # KEYWORD-ONLY: as the THIRD positional, `Symbol("_main", 0x10, "T")` would mean
    # `section="T"` rather than `kind="T"` -- a change of meaning with no error anywhere,
    # which `place` would turn into a `KeyError` rather than a refusal, or, with an int
    # third argument, into a symbol quietly filed under a section that is really a kind.
    # `kw_only` makes the whole class of mistake inexpressible instead of relying on
    # every call site having used keywords, which is a property nobody re-checks.
    section: int = field(default=FLAT, kw_only=True)
    kind: str = field(default="?", kw_only=True)
    # THE `idle` MARK TLINK PRINTS BESIDE SOME PUBLICS, CARRIED AND NOT INTERPRETED.
    #
    # WHAT IT MEANS IS NOT KNOWN. The obvious reading, "TLINK prints `idle` beside a
    # public that lives in an overlay it has NOT made resident, so what sits at that
    # address is whatever is swapped in there at the moment you look", is false from
    # BOTH directions:
    #
    #   - The real map this reader was built against has NO overlay segments (`:OVY`
    #     and `STUBSEG` are both absent from its segment table) and dozens of flagged
    #     symbols. There are no overlays in that program for the mark to be about. Two
    #     publics in ONE of its segments differ in the mark, so it is not a property of
    #     the segment either.
    #   - `tests/fixtures/borland-tlink16/MAPDEMO.MAP`, built here precisely to settle
    #     this, IS linked with an overlay (`TLINK /o`), and the publics of the OVERLAID
    #     module are exactly the ones that come back UNFLAGGED, while the resident ones
    #     are all flagged. Backwards from the claim.
    #
    # NO REPLACEMENT EXPLANATION IS OFFERED. Swapping one guess for another produces the
    # same kind of wrong answer, so an unanswered question is recorded as a question
    # rather than as a mechanism. What would settle it is
    # Borland's own documentation of the map format, or a linker source.
    #
    # WHAT IS UNCHANGED, because none of it was ever the guess: the mark is READ, it is
    # carried on the SYMBOL rather than kept as a count on the side (`symbols_find`
    # answers about ONE name, and that caller is the one who most needs it), and it is
    # counted in `Plan.overlay_idle`. The other two parsers leave it False -- `nm` and a
    # GNU map print no such column.
    #
    # AND THE NAME `overlay_idle` INHERITS THE FALSE EXPLANATION. It is left alone here
    # rather than renamed in passing: it is part of the MCP tool's reply, so changing it
    # is an interface decision and not a comment fix. Recorded so the next reader knows
    # the name is a claim the file does not support.
    idle: bool = field(default=False, kw_only=True)


@dataclass
class Plan:
    """What an encode WOULD do, with every symbol accounted for.

    Every count here exists because the alternative is a tool that reports how many
    names it loaded and stays quiet about the ones it did not. `kept + excluded +
    unencodable` is asserted to equal `parsed`, in `check()`, so a symbol cannot leave
    this module without landing in exactly one bucket.
    """

    parsed: int = 0
    excluded_noise: int = 0
    excluded_pattern: int = 0
    # SYMBOLS WHOSE VALUE IS NOT AN ADDRESS, excluded and COUNTED rather than placed.
    # `nm` prints a COMMON symbol's SIZE in the address column and an ABSOLUTE symbol's
    # constant, so neither can be put on a map of the program: in a DJGPP object
    # `00004000 C _big_table` is 4096 ints x 4 bytes, and `.set _PORT, 0x3F8`
    # comes back as `000003f8 A _PORT` for a serial-port number that is not in the
    # program at all. Placed, they name whatever occupies those addresses.
    excluded_unplaceable: int = 0
    unencodable: list[str] = field(default_factory=list)
    truncated_names: int = 0
    disambiguated: int = 0
    # LINES THE PARSER COULD NOT READ, and deliberately NOT part of `check()`'s sum:
    # they never became symbols, so they are not in `parsed`. It is here because
    # `parsed` counts what was RECOGNISED, and a caller reading a plan whose buckets
    # add up has no other way to learn that the population was amputated on the way in.
    # `nm -C` writes `0016df30 T Foo::bar(int, char)`, whose name holds
    # spaces, so `_NM`'s single-token name column does not match it and the symbol
    # vanishes with `parsed` reporting one fewer and nothing saying why.
    unreadable: int = 0
    # HOW MANY EMITTED NAMES ARE NOT THE SYMBOL'S REAL NAME, which is the question a
    # caller actually has and which `truncated_names` does not answer: that one counts
    # names LONGER than the field, and a name that FITTED is mutilated too when it has
    # to carry a `~n`: for three copies of `_static_helper` (14 characters)
    # `truncated_names` reports 0 while two of the three names in the file are invented.
    renamed: int = 0
    # HOW MANY OF THE KEPT SYMBOLS CARRY BORLAND'S `idle` MARK, and it is a SUBSET of
    # `kept` rather than a bucket beside it. The NAME says "overlay" because that is the
    # obvious reading of the mark; the evidence against it is on `Symbol.idle`. The name
    # is kept because it is part of the MCP
    # tool's reply, and it is flagged here so nobody reads it as a statement of fact.
    #
    # IT IS A SUBSET OF `kept`, and that is the whole of why
    # it is NOT in `check()`'s sum below: the sum PARTITIONS `parsed`, these symbols are
    # already counted inside `kept`, and adding the term would make every Borland map
    # carrying the mark be refused as an accounting failure. In a real map a large share of
    # the symbols carry the flag, so EXCLUDING them is not an option either,
    # and the module's own idiom applies instead: place them, and count them so the
    # conditionality is visible. THE POPULATION IS SYMBOLS AND NOT ROWS: a map prints
    # each flagged symbol in both publics sections, and reading the row count doubles it.
    # `overlay_idle` and not `excluded_idle`: the prefix would say they were dropped.
    overlay_idle: int = 0
    symbols: list[Symbol] = field(default_factory=list)
    # PARALLEL TO `symbols`, BY INDEX, and never a dict keyed on the name: `nm` on a real
    # binary emits hundreds of names MORE THAN ONCE (several distinct addresses all called
    # `___FSEXT_call_open_handlers_wrapper.constprop.0`), so a name-keyed mapping keeps the
    # LAST of each and hands every one of them that same name, throwing away the distinct
    # forms this module had just computed.
    short: list[str] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return len(self.symbols)

    def check(self) -> None:
        """Every parsed symbol landed in exactly one bucket, or this is not a plan.

        A conservation check and not decoration: the accounting is what a caller reads
        instead of thousands of names, so an accounting that does not add up is a report
        about nothing.
        """
        # THE DISTINCTNESS IS ASSERTED HERE, in the constructor's own check, and not
        # only in a test. It is this module's central guarantee, and a guarantee that
        # lives only in a test is one that holds until somebody edits the function
        # without running that test.
        if len(set(self.short)) != len(self.short):
            dupes = sorted({s for s in self.short if self.short.count(s) > 1})
            raise BadSymbolText(
                f"{len(self.short) - len(set(self.short))} of {len(self.short)} "
                f"symbols were given a name belonging to another symbol, e.g. "
                f"{dupes[:3]}. A table that names two addresses the same is worse "
                f"than one that names neither")
        if len(self.short) != len(self.symbols):
            raise BadSymbolText(
                f"{len(self.short)} names for {len(self.symbols)} symbols: the two "
                f"lists are parallel by index and these cannot be zipped")
        # `overlay_idle` IS DELIBERATELY ABSENT FROM THIS SUM. Every term here is a
        # BUCKET and the sum is a PARTITION of `parsed`; `overlay_idle` describes
        # symbols that are already inside `kept`, so adding it would double-count them
        # and refuse every Borland map carrying an overlay. Same reasoning as
        # `unreadable`, arrived at from the other side: that one is outside because the
        # lines never became symbols, this one because the symbols are already in.
        # AND THE SUBSET RELATION IS ASSERTED, not merely asserted ABOUT. Keeping
        # `overlay_idle` out of the sum above rests entirely on it being a subset of
        # `kept`, and this class's own standard, four lines up, is that a guarantee living
        # only in a comment or a test holds until somebody edits the function.
        if not 0 <= self.overlay_idle <= self.kept:
            raise BadSymbolText(
                f"{self.overlay_idle} symbols carry the linker's `idle` mark, out "
                f"of {self.kept} kept. That is not a subset, so the count describes "
                f"some other population and the reply's arithmetic cannot be read")
        total = (self.kept + self.excluded_noise + self.excluded_pattern
                 + self.excluded_unplaceable + len(self.unencodable))
        if total != self.parsed:
            raise BadSymbolText(
                f"the accounting does not add up: parsed {self.parsed}, but "
                f"{self.kept} kept + {self.excluded_noise} section/label + "
                f"{self.excluded_pattern} filtered + {self.excluded_unplaceable} "
                f"unplaceable + {len(self.unencodable)} "
                f"unencodable = {total}. A report whose buckets do not sum to its "
                f"population is a report about nothing")


def parse_nm(text: str) -> list[Symbol]:
    """`nm` output in, symbols out. An UNDEFINED symbol is not one.

    A `U` line prints no address (`                 U _printf`), so it does not match
    `_NM`'s three-column shape at all and never becomes a symbol. THERE IS NO TYPE
    TEST HERE: `kind` is captured and `plan()` tests it against `_UNPLACEABLE`, which
    is what makes this column load-bearing rather than reportable. The `[A-Za-z]` in
    the pattern is a COLUMN, not a filter, and the exclusion of `U` is a consequence
    of the missing address rather than of the letter.
    """
    return _parse(text, _NM, addr_group=1, name_group=3, kind_group=2)[0]


def parse_map(text: str) -> list[Symbol]:
    """A GNU `ld` link map in, symbols out.

    A map has no type column, so every symbol comes back `kind="?"`. That is honest
    rather than lossy: a GNU map does not print a type column, so there is nothing to
    lose. MIND THE CONSEQUENCE: `?` is not in `_UNPLACEABLE`, so an absolute symbol reaching this
    parser is PLACED where the same symbol through `parse_nm` is excluded. The two
    paths disagree, and the map format is what makes it unavoidable.
    """
    return _parse(text, _MAP, addr_group=1, name_group=2, kind_group=None)[0]


def parse(text: str, report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """Sniff the format, parse it, and say HOW MANY LINES WERE NOT READ.

    This is the entry point a caller wants; `parse_tlink`, `parse_map` and `parse_nm`
    are the THREE it chooses between. It exists because the count of unreadable
    lines has to travel
    WITH the symbols to be worth anything: a caller handed a clean list and a plan
    whose buckets add up has no way to discover that the file was amputated on the way
    in.
    """
    # BORLAND IS ASKED FIRST, because a TLINK map scores ZERO on both of the other
    # two sniffs and would therefore land on `nm` and be refused with a message telling
    # the reader their file is not a symbol list -- about a file full of them.
    # BOTH SEGMENT-TABLE HEADERS, because "a Borland map that printed no publics" is a
    # statement about the LINK and it is just as true of a 32-bit one. Asking only about
    # the 16-bit table sent a 32-bit map with no publics to the `nm` parser, which then
    # told its reader the file is not a symbol list.
    #
    # THE 32-BIT HEADER NEEDS A ROW UNDER IT AND THE 16-BIT ONE DOES NOT, and that
    # asymmetry is deliberate. `Start Stop Length
    # Name Class` is five words including `Stop` and is not a sentence anything else
    # writes; `Start Length Name Class` is four ordinary English words, so ANY file
    # carrying that line and no `Publics by` header would be refused OUTRIGHT as a Borland
    # map, perfectly readable `nm` output included. This branch
    # RAISES rather than falling through to the other sniffs, so there is no recovery
    # from it. Requiring a section row to actually be there costs nothing on a real map
    # and makes the four words insufficient on their own.
    if ((_TLINK_SEGMENTS.search(text)
         or (_TLINK_SECT_HEADER.search(text) and _tlink_sections(text.splitlines())))
            and not looks_like_tlink(text)):
        # STAMPED BEFORE THE REFUSAL. The file WAS identified -- that is the whole
        # content of this branch -- so leaving `fmt` empty here would tell a diagnostic
        # caller the format was never established, about the one path that established it.
        if report is not None:
            report._claim("borland-tlink")
        raise BadSymbolText(
            "this has the segment-table header of a Borland TLINK/TASM map and no "
            "`Publics by ...` header, so there is no symbol here this can place. If it is a "
            "Borland map, it was linked without publics (TLINK `/m` writes them) or its "
            "symbol section is not spelled as this expects")
    if looks_like_tlink(text):
        # THE FORMAT IS STAMPED BEFORE THE WALK, so a refusal names the reader that
        # refused. Stamping it on the way out would leave `fmt` empty on exactly the
        # runs where a caller most wants to know which reader was asked.
        if report is not None:
            report._claim("borland-tlink")
        syms, unreadable = parse_tlink(text, report)
        if not syms:
            # THE TWO NOTHINGS AGAIN, and they are easy to get the wrong way round.
            # A section with rows this reader cannot parse is NOT an
            # empty section, and saying so sends the reader off to check their source
            # declares them PUBLIC -- about a file whose publics are all there and in a
            # shape this parser does not know. A 32-bit `Publics by` map
            # (`0001:00000BE0 _main`) is exactly that case: eight-digit offsets,
            # every row refused, and a diagnosis false in both halves.
            #
            # THE MESSAGE SAYS WHAT THE READER DOES. An eight-digit row IS placed,
            # against the table that positions its section, so "a 32-bit map cannot be
            # read" would be false. What is left here is the case that remains a
            # refusal -- no such table, or one that does not cover the section
            # the row names -- and the message has to say WHICH, or it sends the reader
            # to look for something that is already in their file.
            if unreadable:
                raise BadSymbolText(
                    f"this looks like a linker map with a `Publics by ...` section, "
                    f"and {unreadable} of its rows could not be placed, so none were. "
                    f"It reads two shapes: a real-mode row (`0D74:00E21  NAME`, four "
                    f"hex digits then four or five), folded `seg * 16 + off`; and a "
                    f"32-bit row (`0001:00000BE0  NAME`, four then eight), whose left "
                    f"half is a SECTION INDEX kept on the symbol and placed later from "
                    f"`section_bases`. None of them could be read: a row matched neither "
                    f"shape (an offset wider than the format allows, a mark this reader does "
                    f"not know, a column not where it expects), or matched the real-mode "
                    f"shape and was refused (an offset above 0xFFFF, or a short offset in a "
                    f"file that also has a 32-bit section table). The refused rows are the "
                    f"lines under the `Publics by ...` header that start like `SEG:OFFS`")
            raise BadSymbolText(
                "this has a `Publics by ...` header (the Borland TLINK/TASM shape) and no "
                "line under it that starts like `SEG:OFFS`. If it is a Borland map, its link "
                "published nothing: check the source declares the symbols PUBLIC")
        return syms, unreadable
    # WATCOM BEFORE THE OTHER TWO, for the same measured reason Borland goes first: its
    # rows score ZERO on both of the remaining sniffs, so without this a Watcom map
    # lands on the `nm` parser and comes back "no symbol lines were recognised in that
    # text" -- about a file full of them.
    if looks_like_watcom(text):
        if report is not None:
            report._claim("watcom")
        return parse_watcom(text, report)
    if looks_like_map(text):
        if report is not None:
            report._claim("gnu-ld-map")
        return _parse(text, _MAP, addr_group=1, name_group=2, kind_group=None,
                      report=report)
    if report is not None:
        report._claim("nm")
    return _parse(text, _NM, addr_group=1, name_group=3, kind_group=2, report=report)


def _parse(text: str, rx: re.Pattern[str], addr_group: int, name_group: int,
           kind_group: int | None,
           report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """The shared walk: the symbols, AND how many lines were not readable.

    EMPTY IS AN ERROR, never an empty list.

    A file that parsed to nothing and a program with no symbols are different facts,
    and returning `[]` for both is exactly the "instrument that examined nothing
    reporting a clean result", which says nothing true. So it raises, and the caller
    turns that into INVALID.
    """
    out: list[Symbol] = []
    unreadable = 0
    for line in text.splitlines():
        m = rx.match(line)
        if m is None:
            # COUNTED, NEVER DROPPED IN SILENCE. A blank line is not a failure to read
            # anything, so it does not count; every other unmatched line does, and the
            # number reaches the caller through `Plan.unreadable`.
            if line.strip():
                unreadable += 1
                # RECORDED WHEN A CALLER ASKED FOR THE ROWS, in the SAME branch that
                # increments the count. Two statements one after the other cannot report
                # different populations; a second pass looking for "the rows" could.
                if report is not None:
                    report.unreadable_rows.append(line)
            continue
        out.append(Symbol(
            name=m.group(name_group),
            offset=int(m.group(addr_group), 16),
            # `is not None`, not truthiness: group 0 is the whole match and is a
            # perfectly ordinary group number that would test FALSE and silently
            # become "?".
            kind=m.group(kind_group) if kind_group is not None else "?"))
    if not out:
        raise BadSymbolText(
            "no symbol lines were recognised in that text. `nm` output is "
            "`<hex address> <type> <name>`, a GNU link map is `<indent> 0x<hex> "
            "<name>`, a Borland TLINK map is a `Publics by ...` section of "
            "`SEG:OFFS  NAME` rows, and an Open Watcom map has its own symbol section; no "
            "line here matched the shape this text was read as (a line of `nm -C` output "
            "holds spaces and is not read), so there is nothing to load")
    return out, unreadable


def looks_like_tlink(text: str) -> bool:
    """A Borland TLINK/TASM map? Decided by its SECTION HEADER, not by a line shape.

    It is asked before the other two because a Borland map's segment table looks like
    neither `nm` nor GNU `ld` and scores zero on both, so without this it lands on the
    `nm` parser and comes back "no symbol lines were recognised in that text" -- a
    message telling the reader their file is not a symbol list, about a file holding
    hundreds of them.
    """
    return _TLINK_HEADER.search(text) is not None


@dataclass(frozen=True)
class Anchored:
    """Where a section of a linker map BEGINS, and what a row of it looks like.

    A format DECLARES these two and gets the walk below; it does not write the walk.
    The readers around this carry knowledge about particular linkers and stay their own; the
    ONE thing shared is the part where a copy can be silently wrong.
    """

    # The line that opens the section. IT IS THE ANCHOR AND A ROW SHAPE IS NOT, which is
    # measured and not stylistic: a Borland map's "Detailed map of segments" opens every
    # one of ITS rows with the same `seg:off` pair as the publics, so a pattern matching
    # the LINE gathers ten symbols called `ACBP=48`. Reading only what follows a header
    # excludes that section by construction.
    header: re.Pattern[str]
    # A LINE THAT LOOKS LIKE A ROW WITHOUT BEING ONE THE READER CAN PARSE. This is what
    # separates "the section ended" from "a row VANISHED", and without the distinction
    # the walk cannot report an amputation.
    row_shaped: re.Pattern[str]
    # LINES THAT ARE NEITHER A ROW NOR AN ENDING, declared per format because there is
    # no shape they share. A blank line is skipped for everybody and needs no
    # declaration; this is for a format that INTERLEAVES prose with its rows, and it
    # exists because one does: an Open Watcom map puts a `Module: <name>` line
    # before each object's symbols and an `======= ======` rule under its header, and
    # both of those are non-blank lines that do not look like rows -- so without this
    # the walk ENDS at the underline, one line into the section.
    skip: re.Pattern[str] | None = None


_R = TypeVar("_R")


def _anchored_sections(
        lines: list[str], spec: Anchored,
        read: Callable[[str], _R | None]) -> Iterator[tuple[list[_R], list[str]]]:
    """One (rows read, rows that looked like rows and were not) per matching header.

    WHY THIS IS THE ONE THING EXTRACTED. Every format here has to do four things in the
    same order -- find a header, walk its rows, STEP OVER one it cannot read, and COUNT
    that one -- and the third and fourth are exactly where a copy goes wrong without
    saying so, in opposite directions: a publics walk that BREAKS at the first
    unreadable row wherever it is lets one malformed line take the rest of the section
    with it while `unreadable` reports 0; a section walk with the same defect loses every
    section defined after such a row, whose publics are then refused with a message
    blaming a table visibly present in the file. One walk cannot drift from itself.

    IT YIELDS PER SECTION RATHER THAN MERGING, and that is not tidiness either: the
    publics walk wants EVERY matching section (a Borland map prints its publics twice,
    by name and by value) while the section-table walk wants only the FIRST (two tables
    merged into one namespace resolve the second unit's symbols against the first
    unit's bases -- plausible addresses, wrong program, nothing counted). Yielding lets
    each caller take what it needs without a flag deciding it, and because this is lazy,
    the caller that stops after one section never walks the rest.

    A BLANK LINE IS NOT A ROW AND NOT AN ENDING. TLINK puts one between a header and its
    rows, so treating it as either would end every walk at its first line or count every
    gap as a loss.

    WHAT ENDS A SECTION is a non-blank line that does not even LOOK like a row: the
    trailer (`Program entry point at ...`), the next section's header. Searching the
    whole remaining text instead would gather rows from wherever they next appeared,
    and a publics walk doing that returns a handful of symbols out of hundreds.
    """
    for i, line in enumerate(lines):
        if not spec.header.match(line):
            continue
        rows: list[_R] = []
        unreadable: list[str] = []
        for row in lines[i + 1:]:
            if not row.strip():
                continue
            # DECLARED PROSE, stepped over and NOT counted: it was never a row, so it is
            # not a loss. Checked BEFORE `read`, because a format whose prose happens to
            # parse as a row would otherwise turn a heading into a symbol.
            if spec.skip is not None and spec.skip.match(row):
                continue
            got = read(row)
            if got is None:
                # THE TWO NOTHINGS, TOLD APART. A line that looks like a row and cannot
                # be read is a row VANISHING: recorded and stepped over. Anything else
                # is the section ending.
                if spec.row_shaped.match(row):
                    unreadable.append(row)
                    continue
                break
            rows.append(got)
        yield rows, unreadable


# The two Borland sections, DECLARED. Each is a header plus the shape of a line that
# belongs to it; the walking is above and is written once.
_TLINK_PUBLICS = Anchored(header=_TLINK_HEADER, row_shaped=_TLINK_ROW_ANY)
_TLINK_SECTABLE = Anchored(header=_TLINK_SECT_HEADER, row_shaped=_TLINK_SECTION_ANY)


def _tlink_sections(lines: list[str]) -> dict[int, int]:
    """A 32-bit map's section table: index -> the offset its first listed segment begins at,
    which is zero in an ILINK32 map: the table says which sections the file HAS, and the
    caller's `section_bases` say where they went.

    Empty for a 16-bit map, which has no such table -- its rows carry a `Stop` column
    and flat `00000H` values, and its publics fold by `seg * 16` with nothing to look up.

    THE WALK IS ANCHORED ON THE HEADER, which is the same shape as the publics walk
    below and for the same measured reason: the "Detailed map of segments" section opens
    every one of ITS rows with a `sect:offset` pair as well, so a `findall` over the whole
    text would fill this table with offsets INSIDE a section, keyed by that section's own
    index. That heading is not a row, so it ends the walk before those rows are reached.

    AND IT STEPS OVER A ROW IT CANNOT READ RATHER THAN STOPPING, as the publics walk
    does. A `break` at the first non-match wherever it is lets a single malformed row --
    a missing class column, a seven-digit start -- silently discard every section
    defined AFTER it, and the publics of those sections are then refused with a message
    blaming a table that is visibly in the file. What ends the walk is a line that does
    not even OPEN like a section row.

    ONE TABLE, NOT EVERY TABLE IN THE FILE. Walking on for each matching header and
    merging them all into one namespace would resolve, for two maps concatenated -- or a
    map printing its table twice -- the second unit's symbols against the FIRST unit's
    bases. Plausible addresses, wrong program, nothing counted.

    WHAT IS NOT REPORTED, said out loud: a section row this cannot read is stepped over
    and NOTHING counts it. The loss is still visible, because the publics naming that
    section are then refused and DO reach `parse()`'s count -- but they are counted as
    unreadable PUBLICS, so the number points at the wrong half of the file. Nothing here
    can do better without a second counter, and the refusal message names the possibility
    instead.
    """
    # THE FIRST TABLE IS THE TABLE. `next` takes one section and stops; the walk is a
    # generator, so the rest of the file is never walked. That is what stops a second
    # table merging into this one.
    #
    # THE UNREADABLE ROWS ARE DISCARDED HERE, on purpose. The loss is still visible, because
    # the publics naming a section this could not read are then refused and DO reach
    # `parse()`'s count -- as unreadable PUBLICS, so the number points at the wrong half of the
    # file, and the refusal message names that possibility.
    walked = next(_anchored_sections(lines, _TLINK_SECTABLE, _TLINK_SECTION.match), None)
    if walked is None:
        return {}
    out: dict[int, int] = {}
    for m in walked[0]:
        # FIRST WINS WITHIN THE TABLE, so a file that names one index twice cannot
        # move symbols already resolved against the earlier value. Nothing reports the
        # repeat: two rows alone do not say which one is the mistake, and unlike the
        # two publics sections -- which are one set printed twice, so a disagreement
        # there is genuinely undecidable -- a repeat HERE is simply malformed. It is
        # left unreported because there is nowhere to report it that a caller reads,
        # not because it is defensible.
        out.setdefault(int(m.group(1), 16), int(m.group(2), 16))
    return out


def _refuse_if_mostly_unreadable(fmt: str, rows_read: int, unreadable: int) -> None:
    """A file most of which was DISCARDED may not come back as an ordinary result.

    `unreadable` is returned by every reader and, without this, NOTHING asserts it. A
    caller who does not look at that second value gets a well-formed list, a plan whose
    buckets add up, and a table that loads clean -- about a file the reader understood a
    minority of: a real ILINK32 map read with the wrong case for its `Idle` mark loses
    more than half its rows with no exception raised. That should be IMPOSSIBLE rather
    than documented.

    THE BAR IS "MORE LOST THAN KEPT", and it is a statement rather than a tuned number: a
    reading that discarded more rows than it understood is not a reading of that file. It
    needs no calibration and there is nothing to tune it against.

    BOTH SIDES ARE ROWS. Comparing `unreadable` -- rows, summed over EVERY section the
    walk yielded -- against `len(out)`, which is symbols AFTER de-duplication, counts the
    loss on a doubled population and the survivors on a halved one, because a Borland
    map prints its publics TWICE, and the effective bar becomes one THIRD rather than
    one half: the same file, at the same proportion of loss, is REFUSED when it prints
    both publics sections and ACCEPTED when it prints one. This is the same population
    trap this module documents for `overlay_idle`, repeated one function along.

    IT BINDS THE ANCHORED READERS ONLY, and that is the load-bearing half. For those,
    `unreadable` counts lines INSIDE a symbol section that LOOK like rows, so every one is
    a symbol lost. For the flat readers it counts every line that did not match, and a GNU
    `ld` map is MOSTLY not symbols by construction -- on the fixture in this package the
    unmatched lines outnumber the symbols several times over, which is that format
    working correctly.
    One ratio over both would refuse every GNU map ever written.
    """
    # `rows_read > 0` IS PART OF THE CONDITION, and not to soften it: a section that
    # yielded NOTHING already has its own refusal, and it is a better one -- it names the
    # two row shapes and tells the reader which half of the file to look at. Firing here
    # first would replace a specific diagnosis with a general one, which is the shape of a
    # regression this module has recorded before.
    if rows_read > 0 and unreadable > rows_read:
        raise BadSymbolText(
            f"this {fmt} map's symbol section holds {unreadable} rows this could not "
            f"read and only {rows_read} it could: MORE WAS DISCARDED THAN KEPT, so what "
            f"came back would be a minority of the file wearing the shape of all of "
            f"it. A row of a shape this reader does not know is the usual cause -- a "
            f"mark it does not expect, an offset wider than the format allows -- and "
            f"the rows are the lines in that section that look like rows and were not "
            f"read")


def parse_tlink(text: str, report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """The publics of a Borland TLINK/TASM map, as LINEAR offsets, and what it could
    not read.

    IT RETURNS A COUNT LIKE `_parse` DOES, and that is not symmetry for its own sake: the
    walk steps over a row it cannot read rather than stopping, so a section can lose rows
    anywhere, and a bare list with `unreadable = 0` would have `check()` accept a partial
    table as a complete, loadable one. That is the defect `Plan.unreadable` exists to make
    impossible.

    `seg:off` IS FOLDED TO `seg * 16 + off`, which is what the debugger's own var list
    stores and is therefore not a convention invented here: the captured golden shows
    `IV 1234:5678` typed and `0x000179B8` written, and `0x12340 + 0x5678` is `0x179B8`.

    THE SEGMENTS ARE RELATIVE TO WHERE DOS LOADED THE PROGRAM, so the caller supplies
    `base = load_segment * 16` and the ordinary flat addition places the table. That is
    why this needs no base policy of its own -- the existing one already expresses it,
    and adding a second would be two ways of saying the same thing.

    AND `base_from` CANNOT HELP HERE, which is worth knowing before reaching for it:
    `selector()` refuses in real mode by design, because there are no descriptors and
    the debugger answers `SELINFO` with an all-zero one that reads as a real selector
    based at 0. A real-mode base is supplied or it is not known.

    BOTH `Publics by Name` AND `Publics by Value` ARE READ, and the result is
    de-duplicated on (name, offset). They are the SAME set printed twice, with zero
    differences in a real map, so taking one and guessing which
    is present is a fragility for nothing, while taking both without de-duplicating
    would make every symbol collide with itself and `_disambiguate` invent a suffix for
    the second copy of each -- `~0`, since the search starts at zero, on half the
    rows. Two DIFFERENT symbols sharing a name survive as two, which is the case that
    matters and the one `_disambiguate` exists for.

    A LIMIT, said out loud because the code cannot close it: if the two sections
    DISAGREE -- the same name at two addresses -- that is indistinguishable here from
    two genuinely different symbols sharing a name, which is the case above. Both come
    back as two symbols and `_disambiguate` renames the second. Nothing reports that
    the file contradicted itself, because nothing can tell the two apart from the rows
    alone: the fixture with one address altered answers `parsed=4`,
    `disambiguated=1`, and no other signal.

    THE `idle` MARK IS READ AND CARRIED, AND DELIBERATELY NOT INTERPRETED. What it
    means is an open question -- the obvious explanation is false from both sides, and
    the evidence lives on `Symbol.idle`. It reaches
    the caller twice: on the symbol itself (`Symbol.idle`, which is what `symbols_find`
    answers with for one name) and as `Plan.overlay_idle`, whose NAME carries that same
    refuted explanation and is left alone here because it is part of the MCP tool's
    reply.

    WHAT THE COUNT IS STILL GOOD FOR, unchanged by any of that: it says how much of the
    table carries a mark the linker thought worth printing and this reader cannot
    account for, which is a thing to know about a table before trusting every address in
    it.

    THEY ARE STILL PLACED, and the number is the point rather than a filter: in a real
    map a large share of the symbols are flagged, so excluding them would throw away that
    much of the names.
    (MIND WHICH POPULATION THAT COUNTS. A file holds twice as many flagged ROWS, because
    both publics sections print the same set; the SYMBOLS are half that, and `overlay_idle` counts
    symbols. Reading the row count as a symbol count doubles it.) This module's idiom is
    a bucket that keeps the table TRUE beside a count that keeps the loss VISIBLE, and
    here the "loss" is not absence at all -- so the symbol stays, and the count says how
    much of the table carries a mark this reader passes through without being able to
    account for it.

    BOTH GENERATIONS OF THE MAP ARE READ, and which one this is comes from the ROWS
    rather than from a switch. A 16-bit row folds `seg * 16 + off`, which its own file
    fully determines; a 32-bit row keeps its SECTION INDEX and its offset inside that
    section, and nothing places it here. Such a row is neither refused nor counted
    here when the map's own table does not position it: it reaches `place`, which
    refuses a section the CALLER did not position, by name, and
    tells them which ones the table does hold.

    THE BASES ARE THE CALLER'S, AND FOR A 32-BIT MAP THERE IS A TABLE OF THEM. A 32-bit
    map is NOT placed with `base = 0` on the idea that its section starts carry the image
    base, and getting that wrong produces a refusal rather than a wrong answer:
    `encode(p, base=0)` yields `{FLAT: 0}` and every sectioned symbol is then refused
    by name. Pass `section_bases`. Where a section sits is not in the file, whose `Start`
    column prints zeros, so it comes from the linked image, which this module does not read.

    A LIMIT OF THE DE-DUPLICATION, said out loud: the key is `(name, offset)` and does
    NOT include the flag, so a symbol printed `idle` in one publics section and plain in
    the other keeps whichever row was read FIRST. Nothing reports the disagreement, for
    the same reason as the paragraph above it: two rows alone cannot say whether a file
    contradicted itself. No real map at hand does: the two sections agree on every row.
    """
    out: list[Symbol] = []
    unreadable = 0
    # ROWS READ, before de-duplication, so the ratio below compares like with like. It is
    # NOT `len(out)`: this reader deliberately walks a set the file prints twice.
    rows_read = 0
    seen: set[tuple[str, int, int]] = set()
    lines = text.splitlines()
    # READ BEFORE THE PUBLICS ARE WALKED, because a 32-bit row cannot be placed without
    # it. NOT because the table comes first in the file: this scans every line, so the
    # table may sit anywhere, and stating a positional guarantee as the reason would
    # invite a later reader to preserve a property nothing here depends on. It is empty
    # for a 16-bit map, at the cost of one failed header match PER LINE, which is
    # nothing measurable.
    # READ FOR ONE THING: whether this file HAS a section table at all, which is what
    # tells a short row apart from an odd one. It positions nothing -- see
    # `_tlink_place`, where the real artefact killed that model.
    sectioned = bool(_tlink_sections(lines))
    # EVERY MATCHING SECTION, because a Borland map prints its publics TWICE and the two
    # are one set. What each row means is this format's business (`_tlink_place`); the
    # walking is not, and it is written once above.
    for placed, bad in _anchored_sections(
            lines, _TLINK_PUBLICS, lambda row: _tlink_place(row, sectioned)):
        # THE COUNT IS `len()` OF THE ROWS, so the two cannot describe different
        # populations -- which a separate counter beside a separate list eventually
        # does.
        unreadable += len(bad)
        if report is not None:
            report.unreadable_rows.extend(bad)
        rows_read += len(placed)
        for name, section, offset, idle in placed:
            # THE KEY CARRIES THE SECTION. Without it, two symbols at the same offset in
            # DIFFERENT sections de-duplicate into one -- which on the real 32-bit map
            # is not hypothetical: its sections all start at 0, so equal offsets across
            # sections are ordinary.
            if (name, section, offset) in seen:
                continue
            seen.add((name, section, offset))
            # `?` AND NOT `T`, for the same reason `parse_map` answers `?`: a TLINK map
            # does not say whether a public is code or data, and both are printed in
            # this one section, so `T` would be a claim the file does not make, and `kind`
            # is not inert -- `plan()` compares it against `_UNPLACEABLE`, and
            # `symbols_find` reports it to the caller.
            out.append(Symbol(name=name, offset=offset, section=section, kind="?",
                              idle=idle))
    _refuse_if_mostly_unreadable("Borland TLINK/TASM", rows_read, unreadable)
    return out, unreadable


def _tlink_place(row: str, sectioned: bool) -> tuple[str, int, int, bool] | None:
    """One publics row as (name, SECTION, offset inside it, mark), or None.

    IT IS A FOUR-TUPLE AND THE OFFSET IS NOT "IN THE IMAGE". A 32-bit row's offset is
    relative to its section and is placed later; only a real-mode row's is complete, and
    that one carries `FLAT`.

    None means BOTH of the things the caller has to tell apart -- "this is not a row at
    all" and "this is a row I cannot place" -- and that is deliberate: the caller already
    separates them with `_TLINK_ROW_ANY`, which is the only test that can, and having two
    places decide it is how the two answers drift apart.

    THE TWO SHAPES ARE DISJOINT BY OFFSET WIDTH, four-to-five against exactly eight, so
    they never compete for a row, and the disjointness is asserted by a case of its own
    rather than left as a remark. THE ORDER IS LOAD-BEARING THE MOMENT THAT STOPS
    HOLDING, and in one direction only: the real-mode pattern is tried FIRST, so widening
    IT to eight digits makes every 32-bit row trip the sixteen-bit bound and be refused,
    while widening the 32-bit one changes nothing at all because the first pattern has
    already claimed the row. A real-mode row is never "read as a section index": the
    try-order makes it impossible, and the property is pinned on the patterns themselves.

    AND A SHORT OFFSET IN A FILE THAT HAS A SECTION TABLE IS AMBIGUOUS, so it is REFUSED.
    Without the table there is nothing to be ambiguous with and the row is real-mode by
    construction; WITH one, the file has said its left column is a section index, and
    folding `seg * 16` then produces exactly the "plausible small address bearing no
    relation to the program" this module refuses to invent -- 0xBF0 for a symbol the same
    file positions at 0x401BE0. Refusing puts it in the unreadable count where it can be
    seen.
    """
    m = _TLINK_ROW.match(row)
    if m is not None and sectioned:
        return None
    if m is not None:
        # THE GROUP NUMBERS ARE READ OFF THE PATTERN, not remembered: `idle` is a CAPTURING
        # group so the flag can be carried, the name is `group(4)`, and `group(3)` would
        # return the FLAG as the symbol's name, for the flagged rows only, with nothing
        # failing.
        seg, off = m.group(1), m.group(2)
        # SIXTEEN BITS, ENFORCED. The row regex allows five hex digits because this
        # linker pads to five, but five digits reach 0xFFFFF and a real-mode offset
        # does not. Folding `seg * 16 + off` on a wider value invents an address;
        # refusing it says a row was skipped. Folded, `0459:1FFFF`
        # comes back as a symbol at 0x2458F with every counter clean.
        if int(off, 16) > 0xFFFF:
            return None
        # REAL MODE IS FLAT AND THE FOLD IS COMPLETE INFORMATION. A real-mode segment IS
        # a paragraph, so `seg * 16 + off` is arithmetic this file fully determines --
        # nobody has to supply a section base for it, and there is no section to name.
        return (m.group(4), FLAT, int(seg, 16) * 16 + int(off, 16),
                m.group(3) is not None)
    m = _TLINK_ROW32.match(row)
    if m is None:
        return None
    # THE SECTION IS KEPT, NOT RESOLVED HERE. Looking the index up in the
    # map's own section table and returning `base + offset` fails on the real artefact:
    # an ILINK32 map's `Start` column is `section:offset` with every offset ZERO, so the
    # table reads `{1: 0, 2: 0, 3: 0}` and all three sections fold onto one address
    # space, every symbol plausible and every one on top of the others.
    #
    # WHAT IS DELETED IS THE ASSUMPTION THAT `Start` IS A BASE, and not the possibility
    # that some linker prints one: one artefact cannot establish that the documented
    # flavour never occurs. The column is still read (`_tlink_sections`), and it is no
    # longer what places anything.
    #
    # A SECTION INDEX IS NEVER COMPUTED FROM, either -- `index * 16` would put section 1
    # at 16 and section 2 at 32, a set of plausible small addresses bearing no relation
    # to the program. It is a JOIN KEY, and `place` refuses one the caller has not
    # positioned rather than defaulting it to zero.
    return (m.group(4), int(m.group(1), 16), int(m.group(2), 16),
            m.group(3) is not None)


# ---------------------------------------------------------------- Open Watcom's map
#
# THE FOURTH FORMAT, and it is the SECOND USER of the anchored walk rather than a second
# walk. What it declares is what any format declares: where its symbols start, what a row
# looks like, what a row-shaped line it cannot read looks like, and -- new here, because
# one format measurably needs it -- what prose to step over.
#
# Two real maps built from ONE source by linkers decades apart (Watcom C/C++ 10.0a and
# Open Watcom 2.0) emit the SAME layout, so
# this is a stable target and not a moving one. The vendor's manual documents the MAP and
# STATICS options and specifies NOTHING about the columns or the marks, so the format's
# only authority is the artefacts.

# `Address        Symbol`, under a `+   Memory Map   +` box. It is the anchor for the
# same reason every other header here is: the "Module Segments" table further down opens
# ITS rows with a `sect:offset` pair too.
_WATCOM_HEADER = re.compile(r"^[ \t]*Address[ \t]+Symbol[ \t]*\r?$", re.M)

# NEITHER A ROW NOR AN ENDING, and without this the walk stops ONE LINE IN. Two shapes
# an Open Watcom map prints: the `=======        ======` rule under every heading, and a
# `Module: <name>` line before each object file's symbols, interleaved with the rows.
_WATCOM_SKIP = re.compile(r"^[ \t]*(?:=+[ \t]+=+[ \t]*\r?$|Module:)")

# `0001:00000010s helper_` -- section, offset, a mark GLUED to the address, the name.
#
# THE MARK IS GLUED AND THAT IS THE FORMAT, not a quirk to be tolerated: there is no
# space between the last hex digit and the letter, so a pattern expecting whitespace
# there matches nothing at all. The legend the linker prints above its own symbols says
# what the letters are:
#
#     * = unreferenced symbol
#     + = symbol only referenced locally
#     s = symbol is static
#
# and a SPACE means none of the three. NONE of them is Borland's `idle`/`Idle`: they are
# statements about REFERENCES, not about an address being conditional, so `Symbol.idle`
# stays False for every Watcom symbol. `s` is carried as `kind`, where `nm`'s own
# lowercase-means-local convention already lives; the other two are read and dropped,
# which is stated here rather than left to be discovered.
_WATCOM_ROW = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})([*+s ])[ \t]*(\S+)[ \t]*\r?$")

# A line that opens like one of its rows without being one this can read.
_WATCOM_ROW_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4}:[0-9A-Fa-f]+")

_WATCOM_SYMBOLS = Anchored(header=_WATCOM_HEADER, row_shaped=_WATCOM_ROW_ANY,
                           skip=_WATCOM_SKIP)


def looks_like_watcom(text: str) -> bool:
    """An Open Watcom map? Decided by its symbol header AND a row under it.

    BOTH, for the reason the 32-bit Borland sniff already carries: `Address` and
    `Symbol` are two ordinary words, and a file that happens to carry them on one line
    would otherwise be claimed by this reader and then refused, with a message about
    Watcom, about a file that is nothing of the kind.
    """
    return (_WATCOM_HEADER.search(text) is not None
            and any(rows for rows, _ in _anchored_sections(
                text.splitlines(), _WATCOM_SYMBOLS, _WATCOM_ROW.match)))


def parse_watcom(text: str,
                 report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """The Memory Map of an Open Watcom link map: symbols, and what it could not read.

    IT KEEPS `(section, offset)` AND PLACES NOTHING, as every reader does, and here it is
    also the only honest thing this format allows: a Watcom map carries NO flat address
    anywhere. Its section offsets OVERLAP -- sections 1 and 2 both start at 0 -- and
    under DOS/4GW those left-hand numbers are SELECTORS assigned at load time, not
    paragraphs, so `section * 16` would invent an address rather than read one. The
    linker's own manual agrees in the one sentence it spends on the subject: the map
    "specifies the RELATIVE location of all global symbols".

    THE BASES EXIST, JUST NOT IN THIS FILE. A DOS/4GW executable is `LE` and
    its object table gives each object a size and a relocation base, the sizes agreeing
    with the map's own arithmetic. Reading binaries is this module's
    stated boundary, so those numbers come from the caller through `section_bases`.

    ONE SECTION IS WALKED, not every matching header. A loop that consumes the WHOLE
    generator has the defect `_tlink_sections` documents at length one function away:
    two maps concatenated -- or one map printing a second heading -- merge into one
    namespace and the second program's symbols are placed against the first program's
    bases. Plausible addresses, wrong program, nothing counted: two real maps joined end
    to end answer four symbols where either file alone has two.

    ONE is the right number: every real Watcom map at hand carries exactly ONE
    `Address        Symbol` heading. A
    Borland map is the format that prints its publics twice, and it is a different reader.
    """
    out: list[Symbol] = []
    unreadable = 0
    rows_read = 0
    seen: set[tuple[str, int, int]] = set()
    walked = next(_anchored_sections(text.splitlines(), _WATCOM_SYMBOLS,
                                     _WATCOM_ROW.match), None)
    for rows, bad in ([walked] if walked is not None else []):
        unreadable += len(bad)
        rows_read += len(rows)
        if report is not None:
            report.unreadable_rows.extend(bad)
        for m in rows:
            section, offset = int(m.group(1), 16), int(m.group(2), 16)
            name = m.group(4)
            # DE-DUPLICATED ON THE SAME KEY AS THE BORLAND READER. A Watcom map prints
            # its symbols once, so this catches only a genuine repeat, and those exist:
            # `__GETDS` and `___GETDSStart_` share 0001:000003dc, which are two
            # NAMES at one address and survive as two, and the key is what makes sure of
            # it.
            if (name, section, offset) in seen:
                continue
            seen.add((name, section, offset))
            # `s` IS STATIC AND BECOMES THE KIND. The other two marks say something
            # about REFERENCES (`*` unreferenced, `+` referenced only locally) and this
            # module has nowhere honest to put that, so they are read and dropped rather
            # than squeezed into a field that means something else.
            out.append(Symbol(name=name, offset=offset, section=section,
                              kind="s" if m.group(3) == "s" else "?", idle=False))
    _refuse_if_mostly_unreadable("Open Watcom", rows_read, unreadable)
    if not out:
        raise BadSymbolText(
            "this looks like an Open Watcom map and its Memory Map section holds no row "
            "this can read. A row is `0001:00000010s helper_` -- four hex digits, a "
            "colon, eight hex digits, then a mark GLUED to them (`*`, `+`, `s` or a "
            "space) and the name")
    return out, unreadable


def looks_like_map(text: str) -> bool:
    """Link map or `nm` output? Decided by CONTENT, never by a file extension.

    A build that writes `nm` output into a file called `.map`, or the reverse, is an
    ordinary thing, and picking the parser by filename means the wrong one runs and
    then reports "no symbol lines were recognised" while blaming the file's contents.

    It asks which parser recognises MORE lines -- a measurement rather than a guess --
    and in practice the loser scores zero. A tie goes to `nm`, which is the format a
    caller is far likelier to have produced deliberately.
    """
    return len(_MAP.findall(text)) > len(_NM.findall(text))


def _disambiguate(names: list[str]) -> tuple[list[str], int, int]:
    """Fifteen characters each, and NO TWO ALIKE across the whole list.

    TRUNCATING AND KEEPING THE FIRST WINNER IS THE OBVIOUS DESIGN AND IT IS WRONG
    HERE: on a real binary it silently discards a large share of the symbols, and the
    addresses it discards are not random -- they are
    every generated variant of the graphics library's inner loops, which is precisely
    the region where landing on an unnamed address is likeliest.

    NUMBERING WITHIN GROUPS OF ONE 15-CHARACTER PREFIX IS WRONG IN A WORSE WAY, because
    it looks right: it guarantees distinctness INSIDE a group and nothing at all between
    them, so a large share of symbols carry a name belonging to a DIFFERENT symbol while
    `disambiguated` counts renames and nothing says the rest collided. Two causes, both
    invisible to a per-group check: two groups whose keys differ only at the end
    shorten to the SAME stem and both start numbering at `~0` (`__accel_bank_stub` and
    `__accel_bank_switch` would both become `__accel_bank_~0`), and a name that genuinely
    CONTAINS a tilde can collide with a generated one.

    So the ledger is GLOBAL: a name is emitted only if nothing has taken it, and
    otherwise the index is SEARCHED rather than computed from a position in a group.
    Searching is what makes it correct -- a computed index cannot know what another
    group already used -- and it costs nothing at this scale, because the search only
    runs for a name that actually collided.

    THE ORDER IS THE INPUT'S ORDER, so the same text always produces the same file,
    which is what lets a golden exist over this at all. A name that fits and is unique
    is never touched.
    """
    truncated_names = sum(1 for n in names if len(n) > NAME_MAX)
    # TWO PASSES, AND THE FIRST ONE IS WHAT KEEPS THE PROMISE. Walking once in input order
    # would let a GENERATED name take a stem that a LATER symbol owns outright, which breaks the
    # promise three paragraphs up that "a name that fits and is unique is never
    # touched". The order that exposes it:
    #     ["abcdefghijklmXY1", "abcdefghijklmXY2", "abcdefghijklm~0"]
    # the third symbol is really CALLED `abcdefghijklm~0`, it fits, and it is unique in
    # the input -- and one pass would hand that name to the SECOND symbol, so the debugger
    # would point a real name at somebody else's address while `check()` saw perfect
    # distinctness. Reserving the outright winners first makes that inexpressible.
    stems = [n[:NAME_MAX] for n in names]
    # `Counter`, NOT `stems.count(s)` PER DISTINCT STEM, which would scan the whole list
    # once per stem, quadratic in the table, and `plan()` admits up to `COUNT_MAX` names
    # before calling here. One pass instead.
    seen_stems = Counter(stems)
    solo = {s for s, k in seen_stems.items() if k == 1}
    # RESERVED FIRST: every name that FITS WHOLE, and not `solo` -- stems that are
    # unique -- which is a DIFFERENT set, and the difference is the frequent case: a
    # name that fits in fifteen characters and is unique in the input is NOT solo when
    # some longer name truncates onto it, so nothing would protect it and the longer
    # name would take it.
    #
    # On `["abcdefghijklmnoXYZ", "abcdefghijklmno"]` that gives the FIRST the name
    # `abcdefghijklmno`, which is the complete, exact, untruncated name of the SECOND,
    # at a different address -- and renames the second `abcdefghijklm~0`. Every
    # counter clean, `check()` satisfied, and a person typing the real name lands on the
    # wrong function. That is the "name that LIES" this module says is worse than a
    # missing one. And ORDER-DEPENDENT: the same two names the other way round come out
    # right, so one link order would be correct and the other silently not.
    #
    # A name that fits whole can only be claimed by its own symbol, so reserving them
    # all makes the theft inexpressible rather than unlikely.
    fits_whole = {n for n in names if len(n) <= NAME_MAX}
    taken: set[str] = set(solo) | fits_whole
    out: list[str] = []
    disambiguated = 0
    # WHAT HAS ACTUALLY BEEN EMITTED, which `taken` is not: `taken` is seeded with names
    # RESERVED for symbols that have not been reached yet, so testing membership in it
    # cannot tell "somebody already has this" from "this is being held for me".
    emitted: set[str] = set()
    for n, cand in zip(names, stems, strict=True):
        # ITS OWN NAME, whole. A name that fits is in `taken` because it was reserved FOR
        # THIS symbol, so taking it is not a collision -- `cand == n` is what tells that
        # apart from a longer name reaching for somebody else's. A second symbol with the
        # SAME whole name is a genuine collision and falls through to be renamed.
        if cand == n and n not in emitted:
            emitted.add(n)
            out.append(n)
            continue
        # A UNIQUE STEM belonging to a name that does NOT fit: reserved so that no other
        # symbol's `~n` form can land on it, and handed to its owner here.
        if cand in solo and cand not in fits_whole and cand not in emitted:
            emitted.add(cand)
            out.append(cand)
            continue
        if cand not in taken:
            taken.add(cand)
            emitted.add(cand)
            out.append(cand)
            continue
        seq = 0
        while True:
            suffix = f"~{seq}"
            if len(suffix) > NAME_MAX:
                # Unreachable below the u16 ceiling `plan()` enforces before calling
                # here -- 65,535 names need at most `~65534`, six characters -- but it
                # is a raise and not an assert because the alternative is a NEGATIVE
                # slice, which silently produces a name from the WRONG END of the stem.
                raise BadSymbolText(
                    f"{n!r} cannot be given a distinct 15-character form: the index "
                    f"alone would need {len(suffix)} characters")
            alt = cand[:NAME_MAX - len(suffix)] + suffix
            if alt not in taken and alt not in emitted:
                break
            seq += 1
        taken.add(alt)
        emitted.add(alt)
        out.append(alt)
        disambiguated += 1
    return out, truncated_names, disambiguated


def plan(symbols: list[Symbol], pattern: str | None = None,
         keep_noise: bool = False, unreadable: int = 0) -> Plan:
    """Decide what goes in, and account for everything that does not.

    `pattern` is a regular expression matched against the FULL name, before truncation:
    filtering on the shortened form would make which symbols survive depend on which
    OTHER symbols were present, which is not a property a caller can reason about.

    `unreadable` is the count `parse()` returns and is carried through UNTOUCHED: it is
    not part of the conservation sum, because those lines never became symbols, and it
    is reported beside it, because a caller has no other way to learn the population
    was cut before it arrived.

    A `pattern` THAT WILL NOT COMPILE IS A `BadSymbolText`, not a traceback. It arrives
    from an MCP caller through `symbols_load`, whose only guard is `except
    BadSymbolText`, so a bare `re.compile` escapes the tool as a `re.PatternError` --
    no `status`, no `reason`, no session block: `symbols_load(...,
    pattern="(unclosed")` raises `missing ), unterminated subpattern at position 0`
    out of the tool. (It is spelled `re.error` on this package's declared floor of Python
    3.11 and `re.PatternError` from 3.13, which is an alias for the same class; both
    names are given so a reader on the supported minimum can match the evidence to what
    they see.)
    """
    p = Plan(parsed=len(symbols))
    try:
        rx = re.compile(pattern) if pattern else None
    except re.error as exc:
        raise BadSymbolText(
            f"that is not a usable pattern: {exc}. It is a Python regular expression "
            f"matched against the full symbol name") from None
    chosen: list[Symbol] = []
    for s in symbols:
        # A VALUE THAT IS NOT AN ADDRESS CANNOT BE PLACED, and it is excluded BEFORE
        # every other filter because it is a fact about the symbol rather than a
        # decision about the caller's selection.
        #
        # WHY IT IS EXCLUDED RATHER THAN REFUSING THE WHOLE FILE: this module's own
        # idiom. A bucket keeps the table TRUE while conservation keeps the loss
        # VISIBLE, and the `if not chosen:` guard at the end of this function refuses
        # when the filters leave nothing -- so pointing this at a `.o`, where these are
        # the whole population, still ends in a refusal rather than an empty file that
        # loads clean and names nothing.
        #
        # IT IS THAT GUARD AND NOT `check()`: a `Plan` with everything parsed and
        # everything excluded as unplaceable passes `check()` cleanly -- the
        # distinctness test is vacuous on an empty list, the parallel lengths agree at
        # zero, and the buckets sum -- so deleting the guard gives the empty file back.
        #
        # AND IT COSTS NOTHING ON THE REAL WORKLOAD. In a linked DJGPP binary `C` and
        # `A` are absent: they exist only in an unlinked object -- the linker allocates
        # commons into `.bss` and they become `B` -- so this bucket is empty for every
        # caller doing what the tool is for, and non-empty exactly for the one mistake
        # it catches. (The lowercase `a` symbols there are `.absolut`, already noise.)
        if s.kind in _UNPLACEABLE:
            p.excluded_unplaceable += 1
            continue
        if not keep_noise and _NOISE.match(s.name):
            p.excluded_noise += 1
            continue
        if rx is not None and not rx.search(s.name):
            p.excluded_pattern += 1
            continue
        # THE FIELD IS BYTES, so a name that is not PRINTABLE ASCII has no honest
        # representation in it. Encoding with `errors="replace"` would put a `?` in the
        # debugger and call it a symbol, which is a name that LIES -- worse than a
        # missing one. And the gate is PRINTABLE and not merely "ASCII" because a NUL
        # is ASCII: see `PRINTABLE`, where the two-addresses-one-name case is measured.
        if not PRINTABLE.match(s.name):
            p.unencodable.append(s.name)
            continue
        chosen.append(s)
    # AN EMPTY SELECTION IS INVALID, never a two-byte file. `_parse` already refuses a
    # text that parsed to nothing, and the path THROUGH the filters slipped past that
    # intent entirely: a mistyped `pattern` left `chosen` empty, `check()` passed on
    # 0 + 0 + n + 0 == n, `encode` wrote `b"\x00\x00"`, and the debugger loaded a
    # well-formed list of nothing while every count in the report read as success.
    if not chosen:
        raise BadSymbolText(
            f"nothing survived the filters: {p.parsed} parsed, {p.excluded_noise} "
            f"section/label, {p.excluded_pattern} filtered out by the pattern, "
            f"{p.excluded_unplaceable} whose value is not an address, "
            f"{len(p.unencodable)} unencodable. Writing this would produce a "
            f"well-formed EMPTY list, which loads without complaint and names nothing")
    if len(chosen) > COUNT_MAX:
        raise BadSymbolText(
            f"{len(chosen)} symbols will not fit: the count field is 16 bits, so "
            f"{COUNT_MAX} is the ceiling and writing more would wrap it into a short "
            f"list the debugger would read as complete. Narrow it with a pattern")
    short, truncated_names, disambiguated = _disambiguate([s.name for s in chosen])
    p.symbols = chosen
    p.truncated_names = truncated_names
    p.disambiguated = disambiguated
    p.short = short
    p.unreadable = unreadable
    # COUNTED OVER `chosen` AND NOT OVER `symbols`, which is the difference between a
    # number about THIS TABLE and a number about the file. A flagged symbol the caller's
    # `pattern` removed is not in the table being loaded, so counting it would tell the
    # caller part of what they hold is conditional when none of it is.
    p.overlay_idle = sum(1 for s in chosen if s.idle)
    p.renamed = sum(1 for s, n in zip(chosen, short, strict=True) if s.name != n)
    p.check()
    return p


def resolve_bases(base: int | None,
                  section_bases: Mapping[int, int] | None) -> dict[int, int]:
    """The caller's answer to "where does this program live", as one table.

    TWO WAYS IN, AND PASSING BOTH IS REFUSED. A field that is sometimes a
    number and sometimes a table cannot be declared honestly in an MCP tool's schema,
    and a refusal makes the ambiguity IMPOSSIBLE rather than documented. Which of the
    two would have won is precisely the thing nobody would notice getting wrong.

    `base` is the flat answer and becomes `{FLAT: base}`: one section, one base. It is
    `FLAT` (-1) and NOT `0`: a reader who takes it for `{0: base}` writes
    `section_bases={0: ...}` and meets a refusal naming section -1 for an ordinary `nm` file.
    `section_bases` is the sectioned one, a base per section index.

    NEITHER is also refused: a default of zero encodes
    a file that is well formed, loads without complaint, and names whatever occupies
    low memory -- a wrong answer wearing the shape of a right one.
    """
    if base is not None and section_bases is not None:
        raise BadSymbolText(
            "both `base` and `section_bases` were given, and they answer the same "
            "question two different ways. A flat format takes `base`; a sectioned one "
            "takes a base PER SECTION. Passing both leaves which one wins undecided, "
            "which is the kind of thing nobody notices getting wrong")
    if section_bases is not None:
        if not section_bases:
            raise BadSymbolText(
                "`section_bases` is empty, so it positions no section at all. That is "
                "not a flat program; it is a table that says nothing")
        return dict(section_bases)
    if base is None:
        raise BadSymbolText(
            "no base. A toolchain emits OFFSETS and the debugger's list holds LINEAR "
            "addresses, so something has to say where the program was loaded: `base` "
            "for a flat format, `section_bases` for a sectioned one. Defaulting to "
            "zero would name whatever occupies the bottom of the image")
    # KEYED ON `FLAT`, so a SECTIONED symbol handed a flat base is refused by `place`
    # rather than placed at it. That refusal is why readers place nothing, and it only works
    # because the sentinel is an index no map can print.
    return {FLAT: base}


def place(sym: Symbol, bases: Mapping[int, int]) -> int:
    """One symbol's LINEAR address, from its own section and the caller's table.

    PLACEMENT HAPPENS ONCE, HERE, and never while reading: the reader keeps what the file
    said (`section`, `offset`) and this turns it into an address when somebody supplies the
    missing half.

    A SECTION THE TABLE DOES NOT POSITION IS REFUSED, never defaulted to zero. A base of
    0 puts that whole section's symbols on top of whatever is at the bottom of the
    image, which is a wrong answer of exactly the right shape.
    """
    if sym.section not in bases:
        raise BadSymbolText(
            f"{sym.name} is in section {sym.section} and nothing says where that "
            f"section was loaded. The table positions {sorted(bases)}. Placing it "
            f"anyway would name whatever occupies that address instead")
    return bases[sym.section] + sym.offset


def joined(first: bytes, then: bytes) -> bytes:
    """Two encoded batches as one, the way the debugger's `LV` would hold them loaded one after
    the other: the count of both, then each one's records in order."""
    count = struct.unpack_from("<H", first)[0] + struct.unpack_from("<H", then)[0]
    if count > 0xFFFF:
        raise BadSymbolText(f"{count} symbols queued for one load: the file holds at most "
                            f"{0xFFFF}; stop the guest and load in two")
    return struct.pack("<H", count) + first[2:] + then[2:]


def encode(p: Plan, base: int | None = None, *,
           section_bases: Mapping[int, int] | None = None) -> bytes:
    """The plan plus WHERE THE PROGRAM WAS LOADED, as the bytes the debugger reads.

    `base` is the flat answer -- the selector's linear base, which on this platform is
    `SELINFO CS`'s `b:` field read off the machine actually running the program.
    `section_bases` is the sectioned one, and the two are mutually exclusive: see
    `resolve_bases`, which owns that refusal so it cannot be spelled two ways.

    NEITHER IS NOT A DEFAULT, and the requirement lives in `resolve_bases`: zero
    encodes a file that is well formed, loads without complaint, and names whatever
    else occupies low memory.
    """
    bases = resolve_bases(base, section_bases)
    # EVERY BASE IS BOUNDED AT BOTH ENDS, and the upper bound is not pedantry: only the
    # SUM was checked, so a base outside 32 bits sailed through whenever some offset
    # is negative enough to pull it back into range: base 0x100000000 with
    # offset -1 encodes happily as 0xFFFFFFFF.
    for index, one in sorted(bases.items()):
        if not 0 <= one <= ADDR_MAX:
            raise BadSymbolText(
                f"a base of 0x{one:X} (section {index}) is not a 32-bit linear base "
                f"address")
    out = bytearray(struct.pack("<H", len(p.symbols)))
    for s, name in zip(p.symbols, p.short, strict=True):
        # AN OFFSET IS NOT NEGATIVE. A toolchain does not emit one, so a negative here
        # means the text is not what it claims to be -- and checking only the SUM let
        # it through: offset -0x1000 against base 0x400000 encodes as
        # 0x3FF000, naming memory BELOW the program with no complaint.
        if s.offset < 0:
            raise BadSymbolText(
                f"{s.name} has offset {s.offset}, and an offset into a selector is "
                f"not negative. This text is not a symbol list for this program")
        linear = place(s, bases)
        # A LINEAR ADDRESS IS 32 BITS AND `struct` WOULD RAISE, but the message it
        # raises names neither the symbol nor the base, and a caller reading it would
        # blame the file rather than the base they passed.
        if not 0 <= linear <= ADDR_MAX:
            raise BadSymbolText(
                f"{s.name} at offset 0x{s.offset:X} in section {s.section}, plus base "
                f"0x{bases[s.section]:X}, is 0x{linear:X}, which is not a 32-bit "
                f"linear address. Either the base is not this program's or the text is "
                f"not this program's symbols")
        raw = name.encode("ascii")
        # A NAME THAT DOES NOT FIT CORRUPTS EVERY RECORD AFTER IT, in silence: the pad
        # would be `b"\0" * negative`, i.e. empty, so the record runs long and every
        # later one shifts -- a file that looks well formed and decodes to garbage.
        # `Plan` is a public dataclass with a public mutable `short`, so this is the
        # last place that can still say no.
        if len(raw) > NAME_MAX:
            raise BadSymbolText(
                f"{name!r} is {len(raw)} bytes and the field holds {NAME_MAX}. "
                f"Writing it would run past this record and shift every one after it")
        out += raw + b"\0" * (NAME_FIELD - len(raw)) + struct.pack("<I", linear)
    return bytes(out)


def decode(data: bytes) -> list[tuple[str, int]]:
    """The debugger's file back into names and LINEAR addresses.

    It exists so a load can be VERIFIED by reading back what the debugger saved rather
    than by trusting the `ok` it printed -- the same emulator that prints `ok` for a
    filename it truncated to twelve characters.

    A SHORT OR RAGGED FILE IS AN ERROR, not a short list. `count` is read from the file
    itself, so a truncated file otherwise decodes to however many whole records it
    happens to contain and reports that number as the answer.
    """
    if len(data) < 2:
        raise BadSymbolText(
            f"{len(data)} bytes cannot hold a var list: the count alone is 2")
    n, = struct.unpack_from("<H", data, 0)
    want = 2 + RECORD * n
    if len(data) != want:
        raise BadSymbolText(
            f"the file declares {n} records, which is {want} bytes, and it is "
            f"{len(data)}. A file that disagrees with its own header is not a reading")
    out: list[tuple[str, int]] = []
    for i in range(n):
        o = 2 + RECORD * i
        raw = data[o:o + NAME_FIELD].split(b"\0", 1)[0]
        addr, = struct.unpack_from("<I", data, o + NAME_FIELD)
        # `errors="replace"` HERE WOULD BE THE SAME LIE THIS MODULE REFUSES TO WRITE.
        # This function exists to VERIFY a load, so a byte the encoder would have
        # rejected has to stop the reading rather than come back as U+FFFD and be
        # compared, successfully, against a name that is not in the file.
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            raise BadSymbolText(
                f"record {i} holds a byte no name of ours can contain ({raw!r}). "
                f"This file was not written by this module, or it is damaged") from None
        out.append((name, addr))
    return out


NameIndex = dict[str, list[Symbol]]


def index_by_name(symbols: list[Symbol]) -> NameIndex:
    """Every symbol under its full name, in table order. Built once per load: a name is
    resolved on every arming, every re-arm of the stored declarations and every stop's
    watch evaluation, and a scan of the whole table per lookup made each of those
    linear in a listing that can hold thousands of names."""
    out: NameIndex = {}
    for s in symbols:
        out.setdefault(s.name, []).append(s)
    return out


def find_by_name(symbols: list[Symbol], name: str, index: NameIndex | None = None) -> list[Symbol]:
    """Symbols whose full name matches, exactly first and by prefix otherwise.

    Exact wins outright rather than being merged with the prefix hits: with `_main`
    exact and `_main_loop` a prefix, returning both ranked would make the caller choose
    between an answer and a guess. `index` is the table's own `index_by_name`, which
    answers the exact half without a scan; the prefix half is the scan, only on a miss.
    """
    # A COPY of the index's own bucket: a caller that edits its answer must not edit the index.
    exact = list(index[name]) if index is not None and name in index else (
        [s for s in symbols if s.name == name])
    if exact:
        return exact
    return [s for s in symbols if s.name.startswith(name)]


def find_by_offset(symbols: list[Symbol], offset: int,
                   section: int = FLAT) -> tuple[Symbol, int] | None:
    """The nearest symbol AT OR BELOW an offset IN ONE SECTION, and how far above it.

    This is the question you actually have in a debugger: you have stopped somewhere
    and want to know what you are inside. It answers with a distance rather than a
    bare name, because `_main + 0x4` and `_main + 0x9000` mean very different things
    and a name alone cannot tell them apart -- this table has no sizes in it, which is
    a limit of `nm` output and is why the delta is returned instead of being judged.

    `section` IS WHAT MAKES THE ANSWER SOUND. Offsets of different sections are different
    addresses, and the sections OVERLAP (`{1: 0, 2: 0, 3: 0}` on a real 32-bit map), so an
    offset compared across the whole list is answered with whichever symbol of ANY section
    happens to sit highest below it.

    `[Symbol("_main", 0x10, section=1), Symbol("_dataend", 0x20, section=2)]`
    asked about 0x100 would answer `_dataend +0xE0` -- a symbol from a different selector,
    with a plausible delta and no error. `_main` was the only right answer.

    THE DEFAULT IS THE FLAT CASE and not a convenience: a caller with a flat table has
    exactly one section and passing it would be ceremony, while a caller with a sectioned
    table that forgets this argument gets NOTHING back rather than the wrong symbol.
    A refusal instead of a confident wrong answer is this module's whole standard.
    """
    below = [s for s in symbols if s.section == section and s.offset <= offset]
    if not below:
        return None
    best = max(below, key=lambda s: s.offset)
    return best, offset - best.offset
