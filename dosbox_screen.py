"""THE SCREEN OF THE DOS MACHINE at a stop, read from the debugger's own `VGA` listings and from
video memory: the VGA's state (`machine_map`'s `vga` section), the DAC (`palette`), and what the
screen shows (`screen_view`, `screen_signature`, and `screen_wait`'s frame by frame read) in a text
mode or the chained 256-colour mode.

EVERY READING IS A LISTING OFF THE SESSION'S LOGFILE (`Session.listing`) or one dump of video
memory (`Session.memdump`), never a command that changes the machine. Never typed here: `VGA`
alone or with a subcommand outside `VGA_LISTINGS` and `DACPAL` (the console keeps an unknown
command on its input line), `VRD` (it redraws by restarting the VGA's frame timing, which the
guest can observe), `VGA DS` (it moves the display start) and `VGA FONTDUMP` (it writes a file
where the emulator runs).

THE NAMES ARE THE DEBUGGER'S: each listing's `key=value` words, the key lower-cased with `-` as
`_` and its `[RGB]` suffix dropped, the value the text it printed (`5fh`, `70.087Hz`, `M_TEXT`).
The parsers accept only the shapes the listings were captured printing (`tests/fixtures/vga/`).
"""
from __future__ import annotations

import dataclasses
import math
import re
import tempfile
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dosbox_machine as machine
import dosbox_paths as paths
import dosbox_png as png
import dosbox_session as ds

#: The listings that describe the VGA, in the order they are read: the section key, the
#: command, and the title the debugger opens the listing with.
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
VGA_DAC = "VGA DAC"

DACPAL = "VGA DACPAL"
DACPAL_TITLE = "VGA DAC palette (RGB):"
DAC_ENTRIES = 256
#: The DAC width the colours are widened from, as `VGA DAC` prints it.
DAC_BITS = 6
SIX_BIT_MAX = (1 << DAC_BITS) - 1
#: A row: its first index, then two groups of four entries split by a `-`.
DACPAL_GROUP = r"((?:[0-9a-f]{6} ){3}[0-9a-f]{6})"
DACPAL_ROW = re.compile(rf"([0-9a-f]{{2}}): {DACPAL_GROUP}-{DACPAL_GROUP} ?")
DACPAL_PER_ROW = 8

#: The Attribute Controller's sixteen palette registers, the one value printed with spaces:
#: four groups of four, a `-` between groups.
AC_GROUP = r"(?:[0-9a-f]{2} ){3}[0-9a-f]{2}"
AC_PALETTE = re.compile(rf"palette=\{{ ((?:{AC_GROUP}-){{3}}{AC_GROUP}) \}}")


def _key(word: str) -> str:
    return word.removesuffix("[RGB]").lower().replace("-", "_")


def parse_listing(text: str, title: str) -> dict[str, Any]:
    """One `VGA` listing as the mapping of its `key=value` words, the title line's included. The
    AC's `palette={ ... }` is the list of its sixteen hex texts. A word that is not `key=value`,
    a key printed twice, or a listing with no word at all is a shape this was not written
    against."""
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


def parse_dacpal(text: str) -> list[str]:
    """`VGA DACPAL`: the 256 entries in order, each as printed, six hex digits of three six-bit
    components (`00002a`); a component past six bits is not a six-bit DAC's."""
    lines = machine.listing_lines(text)
    if not lines or lines[0].rstrip() != DACPAL_TITLE:
        raise machine.Unreadable(lines[0] if lines else "")
    body = lines[1:]
    if len(body) != DAC_ENTRIES // DACPAL_PER_ROW:
        raise machine.Unreadable(body[-1] if body else lines[0])
    entries: list[str] = []
    for i, line in enumerate(body):
        m = DACPAL_ROW.fullmatch(line)
        if m is None or int(m[1], 16) != i * DACPAL_PER_ROW:
            raise machine.Unreadable(line)
        row = m[2].split() + m[3].split()
        if any(int(e[k:k + 2], 16) > SIX_BIT_MAX for e in row for k in (0, 2, 4)):
            raise machine.Unreadable(line)
        entries += row
    return entries


def _unreadable(command: str, e: machine.Unreadable) -> str:
    return e.sentence(command)


def _read(session: ds.Session, command: str, parse: Callable[[str], Any]) -> Any:
    """One listing, live, parsed; one that printed nothing, or a line no shape matches, is
    refused saying which."""
    text = session.listing(command)
    if not machine.listing_lines(text):
        raise ds.Invalid("unexpected_answer", f"`{command}` printed nothing")
    try:
        return parse(text)
    except machine.Unreadable as e:
        raise ds.Invalid("unexpected_answer", _unreadable(command, e)) from None


def _vga(session: ds.Session, command: str) -> dict[str, Any]:
    """One `VGA` listing of `VGA_LISTINGS`, live, as its mapping."""
    title = TITLES[command]
    return dict(_read(session, command, lambda text: parse_listing(text, title)))


# ------------------------------------------------------------------ the vga section


def vga_section(session: ds.Session) -> tuple[dict[str, Any] | None, list[str], str]:
    """`machine_map`'s `vga` section: the seven listings under their keys and the commands they
    came from, or None and why. One listing that printed nothing, or a line no shape matches,
    makes the whole section absent, and the listings after it are not typed."""
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


# ------------------------------------------------------------------ what the screen can be

#: The reply's `source`: what a decoded screen is made of.
TEXT = "text"
INDICES = "indices"

PLANAR_WORDS = frozenset({"M_EGA", "M_LIN4"})
LINEAR_WORDS = frozenset({"M_LIN8", "M_LIN15", "M_LIN16", "M_LIN24", "M_LIN32"})


def source_of(mode: dict[str, Any]) -> str:
    """`text` for the text modes, `indices` for the chained 256-colour mode (13h's family), off
    `VGA MODE`'s own `mode` and `chained` words; every other mode is refused naming the word and
    why its picture is out of this reader's reach."""
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


# ------------------------------------------------------------------ the DAC


def channel(six_bits: int) -> int:
    """A six-bit DAC component as the eight-bit channel the emulator renders: its two top bits
    repeated below."""
    return (six_bits << 2) | (six_bits >> 4)


def rgb8(entry: str) -> tuple[int, int, int]:
    """An entry as `VGA DACPAL` prints it (`00002a`) to its eight-bit `(r, g, b)`."""
    r, g, b = (channel(int(entry[i:i + 2], 16)) for i in (0, 2, 4))
    return r, g, b


def color(entry: str) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb8(entry))


#: One entry's square in `palette`'s picture, and the squares a row.
SWATCH_PX = 16
SWATCHES_PER_ROW = 16


def swatches(first: int, count: int, dac: list[str]) -> tuple[int, int, bytes]:
    """`palette`'s picture of entries `first` to `first + count - 1`: one square per entry,
    sixteen a row, each pixel the entry's index into the whole DAC. A square past the last
    entry of a short last row is an index the reply did not return, drawn transparent."""
    cols, rows = min(count, SWATCHES_PER_ROW), math.ceil(count / SWATCHES_PER_ROW)
    short = cols * rows > count
    filler = first + count if first + count < DAC_ENTRIES else first - 1
    width, height = cols * SWATCH_PX, rows * SWATCH_PX
    out = bytearray()
    for y in range(height):
        for x in range(width):
            k = (y // SWATCH_PX) * SWATCHES_PER_ROW + x // SWATCH_PX
            out.append(first + k if k < count else filler)
    data = png.indexed(width, height, bytes(out), [rgb8(e) for e in dac],
                       clear=filler if short else None)
    return width, height, data


def read_dac(session: ds.Session) -> tuple[dict[str, Any], list[str]]:
    """`VGA DAC` (its width and mask) and `VGA DACPAL` (its 256 entries). A DAC not in its
    six-bit mode is refused: every colour here is widened from six bits."""
    dac = _vga(session, VGA_DAC)
    if dac.get("bits") != str(DAC_BITS):
        raise ds.Invalid("unexpected_answer",
            f"`{VGA_DAC}` says bits={dac.get('bits')}, and the colours are widened from the "
            f"{DAC_BITS}-bit DAC only")
    return dac, list(_read(session, DACPAL, parse_dacpal))


def palette(session: ds.Session, first: int, count: int, dest: Path | None) -> dict[str, Any]:
    """The body of `palette`: the DAC's width, mask and entries, and with `dest` their
    picture. `count` 0 is every entry from `first`."""
    if dest is not None:
        paths.fresh_dest("dest", dest)
    dac, entries = read_dac(session)
    count = count or DAC_ENTRIES - first
    chosen = entries[first:first + count]
    reply: dict[str, Any] = {"entries": len(entries), "first": first, "count": len(chosen),
                             "colors": [color(e) for e in chosen], "rgb": chosen,
                             "bits": DAC_BITS, "pel_mask": dac.get("pel_mask")}
    if dest is not None:
        width, height, data = swatches(first, count, entries)
        reply["image"] = png.write(dest, width, height, data)
    return reply


# ------------------------------------------------------------------ where the screen is


def hex_word(text: str) -> int:
    """A value the `VGA` listings print in hex with an `h` after it (`0140h`, `4fh`, `0h`)."""
    return int(text.removesuffix("h"), 16)


#: The Graphics Controller's memory map select (misc bits 2-3): where the CPU window lies.
MEMORY_MAP_SHIFT = 2
TEXT_BASES = {0b11: 0xB8000, 0b10: 0xB0000}
INDEXED_BASES = {0b00: 0xA0000, 0b01: 0xA0000}
#: How far each family's window reaches from its base: 32 KiB of text, 64 KiB of pixels.
WINDOW_BYTES = {TEXT: 0x8000, INDICES: 0x10000}
#: The bytes one character cell, or one pixel, takes in its window: a character byte and its
#: attribute, or the pixel's index.
UNIT_BYTES = {TEXT: 2, INDICES: 1}
#: The listings that place the screen, by their section key; `mode` first, because it alone
#: says whether there is a screen this reads.
SHAPE_KEYS = ("mode", "crtc", "gc", "draw")
COMMAND_OF = {key: command for key, command, _ in VGA_LISTINGS}


@dataclasses.dataclass(frozen=True)
class Geometry:
    """What the listings say the screen is: its `source`, its size in characters or pixels, the
    linear address its first byte lies at, how many bytes it is, and, in a text mode, where the
    cursor stands."""
    word: str
    source: str
    width: int
    height: int
    linear: int
    length: int
    display_start: str
    cursor: list[int] | None

    def head(self) -> dict[str, Any]:
        """The reply's account of the screen: its mode, what it is made of, its size."""
        return {"mode": self.word, "source": self.source, "width": self.width,
                "height": self.height}


def geometry(listings: dict[str, dict[str, Any]]) -> Geometry:
    """The screen's shape from the debugger's own words, `listings` keyed as `SHAPE_KEYS`. A row
    of characters (or of pixels, in 13h) is the draw state's `addrline-total` scan lines of
    the `height` it renders: the CRTC's cell height, doubled when it double-scans (`maxscnl`
    bit 7, INT 10h's 200-line text), which its low five bits alone do not say; addresses go to
    bytes by the mode's own `addr-shift`; the window lies where the memory map select puts it.
    A layout this does not decode is refused rather than read wrong: a logical row wider than
    the screen, a split screen, pixel panning."""
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


#: A data segment's descriptor type, read/write or read-only, expand-up, accessed or not.
DATA_TYPES = range(0x10, 0x14)


@dataclasses.dataclass(frozen=True)
class Tables:
    """How an address is reached at this stop: the cpu mode `CPU` says, whether the cpu runs a
    virtual-8086 task (whose segments are paragraphs), and the descriptor tables and page runs
    a selector is chosen from."""
    cpu_mode: str
    v86: bool
    found: dict[str, Any]


def _v86(reading: machine.Reading) -> bool:
    return bool(reading.found.get("cpu", {}).get("vm"))


def tables_from(reading: machine.Reading) -> Tables:
    """A reading of the cpu's listings as the `Tables` a selector is chosen from; one whose `CPU`
    listing could not be read says nothing about how the screen is reached."""
    if reading.mode is None:
        raise ds.Invalid("unexpected_answer", "the `CPU` listing could not be read, so the cpu "
                         "mode the screen is reached through is unknown")
    return Tables(reading.mode, _v86(reading), reading.found)


def read_tables(session: ds.Session) -> Tables:
    """`CPU`, and in protected mode `GDT` and `LDT`, and with paging on `PAGING`."""
    return tables_from(machine.read(session, frozenset({"gdt", "ldt", "paging"})))


def selector_for(linear: int, length: int, tables: Tables) -> tuple[int, int]:
    """The `SEG:OFF` a dump of `length` bytes at `linear` is asked through. In real mode, and in
    a virtual-8086 task, the segment is the paragraph. In protected mode it is the lowest
    selector, the GDT's first, of a present data segment whose base and limit cover the bytes.
    With paging on, only if every page of them maps to the same physical address: a linear
    address that pages elsewhere would be RAM read as the screen."""
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
    """`length` bytes at `SEG:OFF` through the debugger's dump, into a scratch directory of this
    call's own that is gone before it returns."""
    with tempfile.TemporaryDirectory(prefix="dosbox-x-screen-") as scratch:
        return session.memdump(seg, off, length, Path(scratch) / "screen.bin").read_bytes()


# ------------------------------------------------------------------ what the screen shows


#: What code page 437 draws for the control bytes: the IBM PC's glyphs for 01-1F, and 7F.
CONTROL_GLYPHS = "☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
#: 00 and FF draw as blank cells, so they read as the space a blank cell is.
CP437 = [" ", *CONTROL_GLYPHS,
         *(bytes([b]).decode("cp437") for b in range(0x20, 0x7F)), "⌂",
         *(bytes([b]).decode("cp437") for b in range(0x80, 0xFF)), " "]


def text_rows(page: bytes, width: int, height: int) -> list[str]:
    """Each row as the screen shows it: the character bytes through code page 437's glyphs,
    trailing blanks dropped; the attribute bytes are not text."""
    unit = UNIT_BYTES[TEXT]
    return ["".join(CP437[page[(r * width + c) * unit]] for c in range(width)).rstrip(" ")
            for r in range(height)]


def read_listings(session: ds.Session) -> dict[str, dict[str, Any]]:
    """The four listings that place the screen, `VGA MODE` first, so a mode this does not read
    is refused before the other three are typed."""
    listings = {SHAPE_KEYS[0]: _vga(session, COMMAND_OF[SHAPE_KEYS[0]])}
    source_of(listings[SHAPE_KEYS[0]])
    for key in SHAPE_KEYS[1:]:
        listings[key] = _vga(session, COMMAND_OF[key])
    return listings


def read_screen(session: ds.Session, shape: Geometry) -> bytes:
    """The screen's bytes, reached through the address `selector_for` chooses at this stop."""
    seg, off = selector_for(shape.linear, shape.length, read_tables(session))
    return dump(session, seg, off, shape.length)


def signature(shape: Geometry, data: bytes, dac: list[str]) -> int:
    """One number for what is on screen: the mode word, the size, every byte the picture is
    drawn from (characters and attributes, or pixels) and the 256 DAC entries, folded by CRC-32,
    so a changed character, colour attribute or palette entry is a changed number. The cursor
    is not folded, nor the Attribute Controller's own palette registers."""
    head = f"{shape.word}|{shape.width}|{shape.height}|".encode()
    return zlib.crc32(head + data + bytes.fromhex("".join(dac)))


def screen_view(session: ds.Session, dest: Path | None) -> dict[str, Any]:
    """The body of `screen_view`: the text a text mode shows, or the 256-colour picture as an
    indexed PNG at `dest`. What `dest` must be is judged on the mode alone, before the other
    listings are typed."""
    mode = _vga(session, COMMAND_OF["mode"])
    source = source_of(mode)
    if source == TEXT and dest is not None:
        raise ds.Invalid("bad_argument", f"the screen is in `{mode.get('mode')}`, a text mode, "
                         f"which has no picture to write: leave `dest` out to read its text")
    if source == INDICES and dest is None:
        raise ds.Invalid("bad_argument", f"the screen is in `{mode.get('mode')}`, the "
                         f"256-colour mode: its picture needs `dest`, an absolute path not "
                         f"there yet")
    if dest is not None:
        paths.fresh_dest("dest", dest)
    listings = {"mode": mode, **{key: _vga(session, COMMAND_OF[key]) for key in SHAPE_KEYS[1:]}}
    shape = geometry(listings)
    data = read_screen(session, shape)
    reply = shape.head()
    if shape.source == TEXT:
        reply.update(text=text_rows(data, shape.width, shape.height), cursor=shape.cursor)
    else:
        assert dest is not None
        _, dac = read_dac(session)
        image = png.indexed(shape.width, shape.height, data, [rgb8(e) for e in dac])
        reply["image"] = png.write(dest, shape.width, shape.height, image)
    reply["display_start"] = shape.display_start
    return reply


def screen_signature(session: ds.Session) -> dict[str, Any]:
    """The body of `screen_signature`."""
    shape = geometry(read_listings(session))
    data = read_screen(session, shape)
    _, dac = read_dac(session)
    return {"signature": signature(shape, data, dac), **shape.head()}


class TextWatch:
    """The text screen read stop after stop, at the cost a wait can pay each frame: `VGA MODE`
    (the mode word and the display start), `VGA DRAW` (the size the screen renders), `VGA GC`
    (where the page lies: the switch to the monochrome mode moves it to B0000 and leaves the
    other two as they were), `CPU` (how it is reached), and one dump. `VGA CRTC` is read once,
    as it places only the cursor, which a wait does not return; the descriptor tables are
    re-read only when the cpu mode, or whether a virtual-8086 task runs, changes: a guest can
    enter protected mode under an unchanged text screen."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self.crtc: dict[str, Any] | None = None
        self.cpu: tuple[str, bool] | None = None
        self.tables: Tables | None = None

    def rows(self) -> list[str] | None:
        """The rows the text screen shows now, or None when the screen is not in a text mode."""
        mode = _vga(self.session, COMMAND_OF["mode"])
        if mode.get("mode") != "M_TEXT":
            return None
        draw, gc = (_vga(self.session, COMMAND_OF[key]) for key in ("draw", "gc"))
        if self.crtc is None:
            self.crtc = _vga(self.session, COMMAND_OF["crtc"])
        shape = geometry({"mode": mode, "crtc": self.crtc, "gc": gc, "draw": draw})
        reading = machine.read(self.session, frozenset())
        cpu = (str(reading.mode), _v86(reading))
        if cpu != self.cpu or self.tables is None:
            self.cpu = cpu
            self.tables = tables_from(reading) if reading.mode == "real" \
                else read_tables(self.session)
        seg, off = selector_for(shape.linear, shape.length, self.tables)
        return text_rows(dump(self.session, seg, off, shape.length), shape.width, shape.height)


def find_text(rows: list[str], text: str) -> tuple[list[int], str] | None:
    """Where `text` first appears inside one row: `[column, row]` and that row."""
    for r, row in enumerate(rows):
        c = row.find(text)
        if c >= 0:
            return [c, r], row
    return None
