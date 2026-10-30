"""Names for addresses: a toolchain's text symbol list turned into the debugger's own.

DOSBox-X's debugger has `IV`/`SV`/`LV` but no route for thousands of names: `IV` takes one
address typed at a console and uppercases it. This writes the file `LV` reads, from text
(`nm`, a GNU `ld` map, a Borland TLINK/TASM `Publics by ...` section, an Open Watcom map),
never from a binary. The format is documented only in `CDebugVar::SaveVars`/`LoadVars`
(`src/debug/debug.cpp`):

    u16 LE count, then count x (char[16] name NUL-padded, u32 LE LINEAR address)

So there are 15 usable name characters (`_disambiguate`). `IV` uppercases but the file does
not; `LV` appends; `SV`/`LV` cut a filename to 12 characters and still print `ok`
(`SYM_ARG_MAX` in `session.py`). The u16 count bounds a session's loads together
(`COUNT_MAX`).

A `Symbol` keeps `(section, offset)` and `place` adds a base per section; a flat format is one
section. Watcom and ILINK32 maps carry no flat address, so the caller supplies the bases.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import TypeVar

NAME_FIELD = 16
NAME_MAX = NAME_FIELD - 1
ADDR_FIELD = 4
RECORD = NAME_FIELD + ADDR_FIELD
# A u16, and `SV` refuses a longer list, which every `LV` of a session adds to.
COUNT_MAX = 0xFFFF
ADDR_MAX = 0xFFFFFFFF

# Negative: no map prints it (unsigned hex), and 0 is a real Watcom section.
FLAT = -1

# Printable, not just ASCII: a NUL ends a name in the debugger, so `_a\0b` and `_a\0c` collide.
PRINTABLE = re.compile(r"\A[\x20-\x7E]+\Z")


# `re.M`: `looks_like_map` counts matches over the whole text.
_NM = re.compile(r"^\s*([0-9a-fA-F]{4,16})\s+([A-Za-z])\s+(\S+)\s*$", re.M)

_MAP = re.compile(r"^\s+0x([0-9a-fA-F]+)\s+(\S+)\s*$", re.M)

# `[ \t]`, never `\s` (it spans newlines under `re.M`, so the sniff and the walk disagree).
_TLINK_HEADER = re.compile(r"^[ \t]*Address[ \t]+Publics by[ \t]*\w+.*$", re.M)

_TLINK_SEGMENTS = re.compile(
    r"^[ \t]*Start[ \t]+Stop[ \t]+Length[ \t]+Name[ \t]+Class[ \t]*\r?$", re.M)

_TLINK_SECT_HEADER = re.compile(
    r"^[ \t]*Start[ \t]+Length[ \t]+Name[ \t]+Class[ \t]*\r?$", re.M)

# The `H` and the two-token tail each refuse a detailed-map row alone: removing one fails no test.
_TLINK_SECTION = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})[ \t]+([0-9A-Fa-f]+)[Hh]"
    r"[ \t]+(\S+)[ \t]+(\S+)[ \t]*$", re.M)

_TLINK_SECTION_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}\b")

# The index is printed in decimal (`%04d`) but read as hex, and callers key `section_bases` by
# it: `0010` reads as 16. Unverified, no ten-section map is at hand.
_TLINK_ROW32 = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})[ \t]+(Idle[ \t]+)?(\S+)[ \t]*$",
    re.M)

# The `idle` group captures: `(?:...)` would shift the groups and flagged rows would return
# the flag as the name. Five digits because this linker pads the offset to five.
_TLINK_ROW = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4,5})[ \t]+(idle[ \t]+)?(\S+)[ \t]*$",
    re.M)

_TLINK_ROW_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4,}:[0-9A-Fa-f]+\b")

_NOISE = re.compile(r"^\.")

_UNPLACEABLE = frozenset("CAaN")


@dataclass
class ParseReport:
    """Out-parameter reporting which reader ran and which rows were lost; one per read."""

    fmt: str = ""
    unreadable_rows: list[str] = field(default_factory=list)
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
    """The text is not a symbol list this module can read."""


@dataclass(frozen=True)
class Symbol:
    """One name and its offset inside a section."""

    name: str
    offset: int
    # `FLAT` = no sections. Never folded into `base + offset` at read time, which would stack
    # TLINK32's zero-based sections. Keyword-only so `Symbol(n, o, "T")` cannot mean `section="T"`.
    section: int = field(default=FLAT, kw_only=True)
    kind: str = field(default="?", kw_only=True)
    # Carried, not interpreted: the overlay reading is refuted (a map with no overlays has
    # flagged publics). `Plan.overlay_idle` keeps the name for the MCP reply.
    idle: bool = field(default=False, kw_only=True)


@dataclass
class Plan:
    """Every count of what an encode would do: `kept + excluded + unencodable == parsed`."""

    parsed: int = 0
    excluded_noise: int = 0
    excluded_pattern: int = 0
    excluded_unplaceable: int = 0
    unencodable: list[str] = field(default_factory=list)
    truncated_names: int = 0
    disambiguated: int = 0
    unreadable: int = 0
    renamed: int = 0
    # A subset of `kept` (symbols, not rows), so outside `check()`'s sum.
    overlay_idle: int = 0
    symbols: list[Symbol] = field(default_factory=list)
    short: list[str] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return len(self.symbols)

    def check(self) -> None:
        """Every parsed symbol landed in exactly one bucket, or this is not a plan."""
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
    """`nm` output in, symbols out; `plan()` tests `kind` against `_UNPLACEABLE`."""
    return _parse(text, _NM, addr_group=1, name_group=3, kind_group=2)[0]


def parse_map(text: str) -> list[Symbol]:
    """A GNU `ld` map in, symbols out, all `kind="?"` (so an absolute symbol is placed here)."""
    return _parse(text, _MAP, addr_group=1, name_group=2, kind_group=None)[0]


def parse(text: str, report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """Sniff the format and parse it: the symbols and how many lines were not read."""
    # Borland and Watcom first: their rows score zero on the other sniffs. The 32-bit header
    # needs a row under it because its four words are ordinary, and this branch raises.
    if ((_TLINK_SEGMENTS.search(text)
         or (_TLINK_SECT_HEADER.search(text) and _tlink_sections(text.splitlines())))
            and not looks_like_tlink(text)):
        if report is not None:
            report._claim("borland-tlink")
        raise BadSymbolText(
            "this has the segment-table header of a Borland TLINK/TASM map and no "
            "`Publics by ...` header, so there is no symbol here this can place. If it is a "
            "Borland map, it was linked without publics (TLINK `/m` writes them) or its "
            "symbol section is not spelled as this expects")
    if looks_like_tlink(text):
        if report is not None:
            report._claim("borland-tlink")
        syms, unreadable = parse_tlink(text, report)
        if not syms:
            # Unreadable rows are not an empty section; the message names what remains refused.
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
    """The shared walk: symbols and unreadable-line count; parsing to nothing raises."""
    out: list[Symbol] = []
    unreadable = 0
    for line in text.splitlines():
        m = rx.match(line)
        if m is None:
            if line.strip():
                unreadable += 1
                if report is not None:
                    report.unreadable_rows.append(line)
            continue
        out.append(Symbol(
            name=m.group(name_group),
            offset=int(m.group(addr_group), 16),
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
    """A Borland TLINK/TASM map? Decided by its header, not a line shape."""
    return _TLINK_HEADER.search(text) is not None


@dataclass(frozen=True)
class Anchored:
    """Where a map section begins and what a row of it looks like."""

    header: re.Pattern[str]
    row_shaped: re.Pattern[str]
    skip: re.Pattern[str] | None = None


_R = TypeVar("_R")


def _anchored_sections(
        lines: list[str], spec: Anchored,
        read: Callable[[str], _R | None]) -> Iterator[tuple[list[_R], list[str]]]:
    """Per matching header, yield (rows read, row-shaped lines not read).

    Breaking at the first unreadable row would silently lose the rest of the section. It
    yields per section: Borland's publics are printed twice, its section table is read once.
    """
    for i, line in enumerate(lines):
        if not spec.header.match(line):
            continue
        rows: list[_R] = []
        unreadable: list[str] = []
        for row in lines[i + 1:]:
            if not row.strip():
                continue
            if spec.skip is not None and spec.skip.match(row):
                continue
            got = read(row)
            if got is None:
                if spec.row_shaped.match(row):
                    unreadable.append(row)
                    continue
                break
            rows.append(got)
        yield rows, unreadable


_TLINK_PUBLICS = Anchored(header=_TLINK_HEADER, row_shaped=_TLINK_ROW_ANY)
_TLINK_SECTABLE = Anchored(header=_TLINK_SECT_HEADER, row_shaped=_TLINK_SECTION_ANY)


def _tlink_sections(lines: list[str]) -> dict[int, int]:
    """A 32-bit map's section table: index -> start offset (zero in ILINK32); empty for 16-bit.

    It only says which sections exist; positions come from `section_bases`. First table only.
    """
    walked = next(_anchored_sections(lines, _TLINK_SECTABLE, _TLINK_SECTION.match), None)
    if walked is None:
        return {}
    out: dict[int, int] = {}
    for m in walked[0]:
        out.setdefault(int(m.group(1), 16), int(m.group(2), 16))
    return out


def _refuse_if_mostly_unreadable(fmt: str, rows_read: int, unreadable: int) -> None:
    """Refuse a read that discarded more rows than it kept.

    Anchored readers only: a GNU map's unmatched lines outnumber its symbols by design.
    """
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
    """The publics of a Borland TLINK/TASM map and the count of rows it could not read.

    A 16-bit row folds to `seg * 16 + off` (the caller supplies `base = load_segment * 16`); a
    32-bit row keeps its section for `place`. Both publics sections are read and
    de-duplicated; if they disagree the first row wins, unreported.
    """
    out: list[Symbol] = []
    unreadable = 0
    rows_read = 0
    seen: set[tuple[str, int, int]] = set()
    lines = text.splitlines()
    sectioned = bool(_tlink_sections(lines))
    for placed, bad in _anchored_sections(
            lines, _TLINK_PUBLICS, lambda row: _tlink_place(row, sectioned)):
        unreadable += len(bad)
        if report is not None:
            report.unreadable_rows.extend(bad)
        rows_read += len(placed)
        for name, section, offset, idle in placed:
            if (name, section, offset) in seen:
                continue
            seen.add((name, section, offset))
            out.append(Symbol(name=name, offset=offset, section=section, kind="?",
                              idle=idle))
    _refuse_if_mostly_unreadable("Borland TLINK/TASM", rows_read, unreadable)
    return out, unreadable


def _tlink_place(row: str, sectioned: bool) -> tuple[str, int, int, bool] | None:
    """One publics row as (name, section, offset, idle mark), or None.

    None covers "not a row" and "a row I cannot place". The 16-bit pattern is tried first:
    widening it to eight digits would make every 32-bit row trip its bound. A short offset in
    a file with a section table is ambiguous and refused.
    """
    m = _TLINK_ROW.match(row)
    if m is not None and sectioned:
        return None
    if m is not None:
        seg, off = m.group(1), m.group(2)
        if int(off, 16) > 0xFFFF:
            return None
        return (m.group(4), FLAT, int(seg, 16) * 16 + int(off, 16),
                m.group(3) is not None)
    m = _TLINK_ROW32.match(row)
    if m is None:
        return None
    # Section kept, not resolved: ILINK32's `Start` is all zeros, so folding would stack
    # sections; `place` refuses an unpositioned one.
    return (m.group(4), int(m.group(1), 16), int(m.group(2), 16),
            m.group(3) is not None)



_WATCOM_HEADER = re.compile(r"^[ \t]*Address[ \t]+Symbol[ \t]*\r?$", re.M)

_WATCOM_SKIP = re.compile(r"^[ \t]*(?:=+[ \t]+=+[ \t]*\r?$|Module:)")

# `0001:00000010s helper_`: the mark is glued to the address. `*` and `+` are reference marks
# and are dropped; `s` (static) becomes `kind`. None is Borland's `idle`.
_WATCOM_ROW = re.compile(
    r"^[ \t]*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})([*+s ])[ \t]*(\S+)[ \t]*\r?$")

_WATCOM_ROW_ANY = re.compile(r"^[ \t]*[0-9A-Fa-f]{4}:[0-9A-Fa-f]+")

_WATCOM_SYMBOLS = Anchored(header=_WATCOM_HEADER, row_shaped=_WATCOM_ROW_ANY,
                           skip=_WATCOM_SKIP)


def looks_like_watcom(text: str) -> bool:
    """An Open Watcom map? Its symbol header and a row under it."""
    return (_WATCOM_HEADER.search(text) is not None
            and any(rows for rows, _ in _anchored_sections(
                text.splitlines(), _WATCOM_SYMBOLS, _WATCOM_ROW.match)))


def parse_watcom(text: str,
                 report: ParseReport | None = None) -> tuple[list[Symbol], int]:
    """The Memory Map of an Open Watcom link map: symbols and the count of unreadable rows.

    Only the first section is walked: concatenated maps would mix their bases.
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
            if (name, section, offset) in seen:
                continue
            seen.add((name, section, offset))
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
    """Link map or `nm` output? The parser recognising more lines wins; a tie goes to `nm`."""
    return len(_MAP.findall(text)) > len(_NM.findall(text))


def _disambiguate(names: list[str]) -> tuple[list[str], int, int]:
    """Fifteen characters each and no two alike across the whole list.

    Numbering within a prefix group guarantees nothing between groups, so the ledger is
    global and the index searched. Output follows input order; a name that fits and is unique
    is untouched.
    """
    truncated_names = sum(1 for n in names if len(n) > NAME_MAX)
    # Two passes: in one, a generated name could take a stem a later symbol owns outright.
    stems = [n[:NAME_MAX] for n in names]
    seen_stems = Counter(stems)
    solo = {s for s, k in seen_stems.items() if k == 1}
    # Reserved: every name that fits whole, not only unique stems. Otherwise a longer name
    # truncating onto it (`abcdefghijklmnoXYZ` against `abcdefghijklmno`) takes it, the real
    # one is renamed, and typing the true name lands on the wrong function, order-dependently.
    fits_whole = {n for n in names if len(n) <= NAME_MAX}
    taken: set[str] = set(solo) | fits_whole
    out: list[str] = []
    disambiguated = 0
    emitted: set[str] = set()
    for n, cand in zip(names, stems, strict=True):
        if cand == n and n not in emitted:
            emitted.add(n)
            out.append(n)
            continue
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
                # Unreachable under the u16 ceiling; a raise because a slice would go negative.
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
    """Decide what goes in and account for everything that does not.

    `pattern` matches the full name before truncation. A bad pattern is a `BadSymbolText`:
    `symbols_load` guards only that.
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
        if s.kind in _UNPLACEABLE:
            p.excluded_unplaceable += 1
            continue
        if not keep_noise and _NOISE.match(s.name):
            p.excluded_noise += 1
            continue
        if rx is not None and not rx.search(s.name):
            p.excluded_pattern += 1
            continue
        if not PRINTABLE.match(s.name):
            p.unencodable.append(s.name)
            continue
        chosen.append(s)
    # Empty must refuse, or a mistyped `pattern` encodes an empty list that reports success.
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
    p.overlay_idle = sum(1 for s in chosen if s.idle)
    p.renamed = sum(1 for s, n in zip(chosen, short, strict=True) if s.name != n)
    p.check()
    return p


def resolve_bases(base: int | None,
                  section_bases: Mapping[int, int] | None) -> dict[int, int]:
    """The caller's answer to "where does the program live", as one table.

    Both `base` and `section_bases`, or neither, is refused.
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
    return {FLAT: base}


def place(sym: Symbol, bases: Mapping[int, int]) -> int:
    """One symbol's linear address; a section the table does not position is refused, never zero."""
    if sym.section not in bases:
        raise BadSymbolText(
            f"{sym.name} is in section {sym.section} and nothing says where that "
            f"section was loaded. The table positions {sorted(bases)}. Placing it "
            f"anyway would name whatever occupies that address instead")
    return bases[sym.section] + sym.offset


def joined(first: bytes, then: bytes) -> bytes:
    """Two encoded batches as `LV` would hold them loaded one after the other."""
    count = struct.unpack_from("<H", first)[0] + struct.unpack_from("<H", then)[0]
    if count > 0xFFFF:
        raise BadSymbolText(f"{count} symbols queued for one load: the file holds at most "
                            f"{0xFFFF}; stop the guest and load in two")
    return struct.pack("<H", count) + first[2:] + then[2:]


def encode(p: Plan, base: int | None = None, *,
           section_bases: Mapping[int, int] | None = None) -> bytes:
    """The plan plus where the program was loaded, as the bytes the debugger reads."""
    bases = resolve_bases(base, section_bases)
    for index, one in sorted(bases.items()):
        if not 0 <= one <= ADDR_MAX:
            raise BadSymbolText(
                f"a base of 0x{one:X} (section {index}) is not a 32-bit linear base "
                f"address")
    out = bytearray(struct.pack("<H", len(p.symbols)))
    for s, name in zip(p.symbols, p.short, strict=True):
        if s.offset < 0:
            raise BadSymbolText(
                f"{s.name} has offset {s.offset}, and an offset into a selector is "
                f"not negative. This text is not a symbol list for this program")
        linear = place(s, bases)
        if not 0 <= linear <= ADDR_MAX:
            raise BadSymbolText(
                f"{s.name} at offset 0x{s.offset:X} in section {s.section}, plus base "
                f"0x{bases[s.section]:X}, is 0x{linear:X}, which is not a 32-bit "
                f"linear address. Either the base is not this program's or the text is "
                f"not this program's symbols")
        raw = name.encode("ascii")
        if len(raw) > NAME_MAX:
            raise BadSymbolText(
                f"{name!r} is {len(raw)} bytes and the field holds {NAME_MAX}. "
                f"Writing it would run past this record and shift every one after it")
        out += raw + b"\0" * (NAME_FIELD - len(raw)) + struct.pack("<I", linear)
    return bytes(out)


def decode(data: bytes) -> list[tuple[str, int]]:
    """The debugger's file back into names and linear addresses, to verify a load."""
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
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            raise BadSymbolText(
                f"record {i} holds a byte no name of ours can contain ({raw!r}). "
                f"This file was not written by this module, or it is damaged") from None
        out.append((name, addr))
    return out


NameIndex = dict[str, list[Symbol]]


def folded(name: str) -> str:
    """The form a name is looked up by: a caller types a routine as it reads it, and a map may
    spell it in another case."""
    return name.upper()


def index_by_name(symbols: list[Symbol]) -> NameIndex:
    """Every symbol under its folded full name, in table order; built once per load."""
    out: NameIndex = {}
    for s in symbols:
        out.setdefault(folded(s.name), []).append(s)
    return out


def find_by_name(symbols: list[Symbol], name: str, index: NameIndex | None = None) -> list[Symbol]:
    """Symbols whose full name matches, case ignored: exact outright, else by prefix, in section
    and offset order. Each keeps its own spelling."""
    key = folded(name)
    exact = list(index[key]) if index is not None and key in index else (
        [s for s in symbols if folded(s.name) == key])
    if exact:
        return exact
    return sorted((s for s in symbols if folded(s.name).startswith(key)),
                  key=lambda s: (s.section, s.offset))


def _line_of(text: str, name: str) -> int | str:
    """The first line of `text` that ends in `name` as its own word, else one that holds it."""
    lines = text.splitlines()
    for ends in (True, False):
        for number, line in enumerate(lines, 1):
            words = line.split()
            if words and (words[-1] == name if ends else name in words):
                return number
    return "unknown"


def check_folded(symbols: list[Symbol], text: str) -> None:
    """Refuse a table in which two differently spelled names fold to one, naming both lines of
    `text`: a lookup ignores case and could not tell them apart. The same spelling twice is
    ambiguity, which lookups already report."""
    first: dict[str, str] = {}
    for s in symbols:
        seen = first.setdefault(folded(s.name), s.name)
        if seen != s.name:
            raise BadSymbolText(
                f"{seen!r} (line {_line_of(text, seen)}) and {s.name!r} (line "
                f"{_line_of(text, s.name)}) are one name once case is ignored, and a lookup "
                f"ignores case, so it could not tell them apart. Rename one in the map")


def find_by_offset(symbols: list[Symbol], offset: int,
                   section: int = FLAT) -> tuple[Symbol, int] | None:
    """The nearest symbol at or below an offset in one section, and the distance above it.

    The `FLAT` default returns nothing for a sectioned table rather than a wrong symbol.
    """
    below = [s for s in symbols if s.section == section and s.offset <= offset]
    if not below:
        return None
    best = max(below, key=lambda s: s.offset)
    return best, offset - best.offset
