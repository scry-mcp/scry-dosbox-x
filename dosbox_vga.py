"""The VGA's listings read off the debugger: their grammar, the screen geometry they give,
and where video memory lies for a dump.

Every reading is a listing or one dump, never a command that changes the machine. Never sent:
bare `VGA` or an unknown subcommand, `VRD` (restarts the frame timing, which the guest can
observe), `VGA DS` (moves the display start) and `VGA FONTDUMP` (writes a file where the emulator
runs).

Keys are the debugger's `key=value` words, lower-cased, `-` as `_`, `[RGB]` dropped; values stay
the text printed. The parsers accept only shapes captured in `tests/fixtures/vga/`.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dosbox_machine as machine
import dosbox_session as ds

#: Section key, command and the title the debugger opens the listing with, in read order.
VGA_LISTINGS: tuple[tuple[str, str, str], ...] = (
    ("mode", "VGA MODE", "VGA mode info:"),
    ("crtc", "VGA CRTC", "VGA CRTC info:"),
    ("seq", "VGA SEQ", "VGA Sequencer info:"),
    ("gc", "VGA GC", "VGA Graphics controller info:"),
    ("ac", "VGA AC", "VGA Attribute Controller info:"),
    ("dac", "VGA DAC", "VGA DAC info:"),
    ("draw", "VGA DRAW", "VGA draw info:"),
)


TITLES = {command: title for _, command, title in VGA_LISTINGS}


#: The AC's sixteen palette registers: the one value printed with spaces, groups split by `-`.
AC_GROUP = r"(?:[0-9a-f]{2} ){3}[0-9a-f]{2}"


AC_PALETTE = re.compile(rf"palette=\{{ ((?:{AC_GROUP}-){{3}}{AC_GROUP}) \}}")


def _key(word: str) -> str:
    return word.removesuffix("[RGB]").lower().replace("-", "_")


def parse_listing(text: str, title: str) -> dict[str, Any]:
    """One `VGA` listing as its `key=value` mapping; the AC's `palette` is a list of hex texts.
    A word that is not `key=value`, a repeated key or an empty listing is refused."""
    lines = machine.listing_lines(text)
    if not lines or not lines[0].startswith(title):
        raise machine.Unreadable(lines[0] if lines else "")
    out: dict[str, Any] = {}
    for i, line in enumerate(lines):
        body = (line[len(title):] if i == 0 else line).strip()
        regs = AC_PALETTE.fullmatch(body)
        if regs is not None:
            pairs: list[tuple[str, Any]] = [("palette", re.split(r"[ -]", regs[1]))]
        else:
            pairs = []
            for word in body.split():
                key, eq, value = word.partition("=")
                if not eq or not key:
                    raise machine.Unreadable(line)
                pairs.append((key, value))
        for key, value in pairs:
            name = _key(key)
            if name in out:
                raise machine.Unreadable(line)
            out[name] = value
    if not out:
        raise machine.Unreadable(lines[0])
    return out


def _unreadable(command: str, e: machine.Unreadable) -> str:
    return e.sentence(command)


def read_parsed(session: ds.Session, command: str, parse: Callable[[str], Any]) -> Any:
    """One listing, live, parsed; empty or unmatched output is refused saying which."""
    text = session.listing(command)
    if not machine.listing_lines(text):
        raise ds.Invalid("unexpected_answer", f"`{command}` printed nothing")
    try:
        return parse(text)
    except machine.Unreadable as e:
        raise ds.Invalid("unexpected_answer", _unreadable(command, e)) from None


def listed(session: ds.Session, command: str) -> dict[str, Any]:
    """One `VGA` listing of `VGA_LISTINGS`, live, as its mapping."""
    title = TITLES[command]
    return dict(read_parsed(session, command, lambda text: parse_listing(text, title)))


def vga_section(session: ds.Session) -> tuple[dict[str, Any] | None, list[str], str]:
    """`machine_map`'s `vga` section: the listings by key and their commands, or None and why.
    One bad listing makes the section absent and the later ones are not asked."""
    found: dict[str, Any] = {}
    for key, command, title in VGA_LISTINGS:
        text = session.listing(command)
        if not machine.listing_lines(text):
            return None, [], f"`{command}` printed nothing"
        try:
            found[key] = parse_listing(text, title)
        except machine.Unreadable as e:
            return None, [], _unreadable(command, e)
    return found, [command for _, command, _ in VGA_LISTINGS], ""


#: The reply's `source`.
TEXT = "text"


INDICES = "indices"


PLANAR_WORDS = frozenset({"M_EGA", "M_LIN4"})


LINEAR_WORDS = frozenset({"M_LIN8", "M_LIN15", "M_LIN16", "M_LIN24", "M_LIN32"})


def source_of(mode: dict[str, Any]) -> str:
    """`text` or `indices` (chained 256-colour) off `VGA MODE`; any other mode is refused."""
    word = mode.get("mode")
    if word == "M_TEXT":
        return TEXT
    if word == "M_VGA" and mode.get("chained") == "1":
        return INDICES
    if word in PLANAR_WORDS or word == "M_VGA":
        why = ("a planar or unchained mode: the CPU window answers one plane per read, and "
               "choosing the plane writes a Graphics Controller register")
    elif word in LINEAR_WORDS:
        why = ("a linear-frame-buffer mode: the debugger's segmented dump does not reach the "
               "buffer in real mode, and no route to it is offered here in protected mode")
    elif word == "M_ERROR":
        why = "no video mode is set yet, as before the BIOS sets one"
    else:
        why = "a mode no decoder here is written for"
    raise ds.Invalid("no_channel",
        f"the screen is in `{word}`, {why}. The screen is read from video memory only in a text "
        f"mode and in the chained 256-colour mode (13h's); the image of what was displayed is "
        f"`capture_frame`, on a session started with `start(capture_video=True, program=...)`")


def hex_word(text: str) -> int:
    """A listing value printed in hex with a trailing `h` (`0140h`)."""
    return int(text.removesuffix("h"), 16)


#: The Graphics Controller's memory map select (misc bits 2-3).
MEMORY_MAP_SHIFT = 2


TEXT_BASES = {0b11: 0xB8000, 0b10: 0xB0000}


INDEXED_BASES = {0b00: 0xA0000, 0b01: 0xA0000}


WINDOW_BYTES = {TEXT: 0x8000, INDICES: 0x10000}


#: Bytes per character cell (char + attribute) or per pixel (index).
UNIT_BYTES = {TEXT: 2, INDICES: 1}


#: The listings that place the screen; `mode` first, as it alone says whether there is one.
SHAPE_KEYS = ("mode", "crtc", "gc", "draw")


COMMAND_OF = {key: command for key, command, _ in VGA_LISTINGS}


@dataclasses.dataclass(frozen=True)
class Geometry:
    """What the listings say the screen is: source, size, linear address, byte length, cursor."""
    word: str
    source: str
    width: int
    height: int
    linear: int
    length: int
    display_start: str
    cursor: list[int] | None

    def head(self) -> dict[str, Any]:
        """The reply's account of the screen."""
        return {"vga_mode": self.word, "kind": "text" if self.source == TEXT else "pixel",
                "width": self.width, "height": self.height}


def geometry(listings: dict[str, dict[str, Any]]) -> Geometry:
    """The screen's shape from `listings` keyed as `SHAPE_KEYS`. Rows come from the draw state's
    `addrline-total` (the CRTC cell height, doubled on double-scan, which `maxscnl`'s low five
    bits alone do not say); addresses go to bytes by `addr-shift`. A wider logical row, a split
    screen or pixel panning is refused rather than read wrong."""
    mode, crtc, gc, draw = (listings[key] for key in SHAPE_KEYS)
    source = source_of(mode)
    try:
        lines_per_row = int(draw["addrline_total"])
        height = int(draw["height"]) // lines_per_row if lines_per_row > 0 else 0
        width = int(draw["blocks"]) if source == TEXT else int(draw["width"])
        shift = int(mode["addr_shift"])
        start = hex_word(mode["disp_start"]) << shift
        row_bytes = int(mode["scanlen"]) << (shift + 1)
        memory_map = (hex_word(gc["misc"]) >> MEMORY_MAP_SHIFT) & 0b11
        cursor_at = hex_word(crtc["curs_loc"]) - hex_word(mode["disp_start"])
        cursor_on = draw["curs_en"] == "1"
        plain = (draw["has_split"], mode["pel_pan"], mode["byte_skip"]) == ("0", "0", "0")
    except (KeyError, ValueError) as e:
        raise ds.Invalid("unexpected_answer",
            f"the `VGA` listings lack a word the screen is placed by, or print it in another "
            f"shape: {e}") from None
    word = str(mode.get("mode"))
    bases = TEXT_BASES if source == TEXT else INDEXED_BASES
    if memory_map not in bases or width <= 0 or height <= 0:
        raise ds.Invalid("no_channel",
            f"`{word}` with the memory map select {memory_map:02b} and a {width} x {height} "
            f"screen places no picture this reads")
    if row_bytes != width * UNIT_BYTES[source] or not plain:
        raise ds.Invalid("no_channel",
            f"`{word}` is laid out in a way this does not decode (rows of {row_bytes} bytes for "
            f"a screen {width} wide, a split screen, or panning), so its bytes are not read as "
            f"a picture they would misplace")
    length = width * height * UNIT_BYTES[source]
    if start + length > WINDOW_BYTES[source]:
        raise ds.Invalid("no_channel",
            f"the screen starts {start} bytes into its window and is {length} bytes long, past "
            f"the window's {WINDOW_BYTES[source]}: where it wraps is not read here")
    cursor = None
    if source == TEXT and cursor_on and 0 <= cursor_at < width * height:
        cursor = [cursor_at % width, cursor_at // width]
    return Geometry(word, source, width, height, bases[memory_map] + start, length,
                    str(mode["disp_start"]), cursor)


#: Data-segment descriptor types: expand-up, read-only or read/write, accessed or not.
DATA_TYPES = range(0x10, 0x14)


@dataclasses.dataclass(frozen=True)
class Tables:
    """How an address is reached at this stop: cpu mode, virtual-8086 or not, and the tables."""
    cpu_mode: str
    v86: bool
    found: dict[str, Any]


def in_v86(reading: machine.Reading) -> bool:
    return bool(reading.found.get("control", {}).get("vm"))


def tables_from(reading: machine.Reading) -> Tables:
    """A reading as `Tables`; an unreadable `CPU` listing is refused."""
    if reading.mode is None:
        raise ds.Invalid("unexpected_answer", "the `CPU` listing could not be read, so the cpu "
                         "mode the screen is reached through is unknown")
    return Tables(reading.mode, in_v86(reading), reading.found)


def read_tables(session: ds.Session) -> Tables:
    """`CPU`, and in protected mode `GDT` and `LDT`, and with paging on `PAGING`."""
    return tables_from(machine.read(session, frozenset({"gdt", "ldt", "paging"})))


def selector_for(linear: int, length: int, tables: Tables) -> tuple[int, int]:
    """The `SEG:OFF` a dump of `length` bytes at `linear` is asked through: the paragraph in real
    mode or v86, else the lowest selector (GDT first) of a present data segment covering the
    bytes. With paging on, only if every page maps to itself, else RAM would be read as screen."""
    if tables.cpu_mode == "paged":
        pages = tables.found.get("paging")
        if pages is None:
            raise ds.Invalid("no_channel", "paging is on and `PAGING` could not be read, so no "
                             "address can be shown to reach the screen")
        for page in range(linear & ~(machine.PAGE_SIZE - 1), linear + length, machine.PAGE_SIZE):
            if machine.physical_address(page, pages) != page:
                raise ds.Invalid("no_channel",
                    f"the page at {page:08X} is not mapped to the same physical address, so "
                    f"the screen is not where a linear read would find it")
    if tables.cpu_mode == "real" or tables.v86:
        return linear >> 4, linear & 0xF
    for table in ("gdt", "ldt"):
        rows = sorted(tables.found.get(table) or [], key=lambda r: int(r["selector"], 16))
        for row in rows:
            base, limit = int(row["base"], 16), int(row["limit"], 16)
            if row.get("p") == 1 and int(row["type"], 16) in DATA_TYPES \
                    and base <= linear and linear + length - 1 <= base + limit:
                return int(row["selector"], 16), linear - base
    raise ds.Invalid("no_channel",
        f"no present data segment in the GDT or the LDT covers {length} bytes at {linear:08X}"
        + ("" if "gdt" in tables.found else ": `GDT` could not be read"))


def dump(session: ds.Session, seg: int, off: int, length: int) -> bytes:
    """`length` bytes at `SEG:OFF` through the debugger's dump, via a throwaway directory."""
    with tempfile.TemporaryDirectory(prefix="dosbox-x-screen-") as scratch:
        return session.memdump(seg, off, length, Path(scratch) / "screen.bin").read_bytes()


def read_listings(session: ds.Session) -> dict[str, dict[str, Any]]:
    """The listings that place the screen, `VGA MODE` first so an unread mode stops early."""
    listings = {SHAPE_KEYS[0]: listed(session, COMMAND_OF[SHAPE_KEYS[0]])}
    source_of(listings[SHAPE_KEYS[0]])
    for key in SHAPE_KEYS[1:]:
        listings[key] = listed(session, COMMAND_OF[key])
    return listings


def read_screen(session: ds.Session, shape: Geometry) -> bytes:
    """The screen's bytes, reached through the address `selector_for` chooses at this stop."""
    seg, off = selector_for(shape.linear, shape.length, read_tables(session))
    return dump(session, seg, off, shape.length)
