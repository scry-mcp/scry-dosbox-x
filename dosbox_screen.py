"""WHAT THE DOS MACHINE'S SCREEN SHOWS at a stop (`screen_view`, `screen_signature`), in a text mode
or the chained 256-colour mode: the screen's place and size from the VGA's listings
(`dosbox_vga`), its colours from the DAC (`dosbox_dac`), its cells from one dump of video memory.
`screen_wait` reads the text screen frame by frame through `dosbox_retrace`'s watch.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scry_core import judges, picture, png, raster

import dosbox_dac as vgadac
import dosbox_paths as paths
import dosbox_session as ds
import dosbox_vga as vga

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
    unit = vga.UNIT_BYTES[vga.TEXT]
    return ["".join(CP437[page[(r * width + c) * unit]] for c in range(width)).rstrip(" ")
            for r in range(height)]


def text_cells(page: bytes, ac: dict[str, Any], dac: list[str]) -> bytes:
    """Each character cell of a text page as `scry_core.raster` hashes it: its code page 437
    byte, then the RGB of its foreground and of its background as the VGA resolves them. An
    attribute's nibble picks an Attribute Controller palette register; with `mode_control` bit
    7 the register's low four bits take `color-select`'s bits 0-1 above them, else its six bits
    stand; `color-select`'s bits 2-3 are the top two; the DAC entry there is the colour. With
    `mode_control` bit 3 (blink) the background has three bits and the fourth blinks."""
    try:
        regs = [int(r, 16) for r in ac["palette"]]
        mode_control, select = vga.hex_word(ac["mode_control"]), vga.hex_word(ac["color_select"])
    except (KeyError, ValueError) as e:
        raise ds.Invalid("unexpected_answer", f"`VGA AC` lacks a word a text cell's colour is "
                         f"resolved by, or prints it in another shape: {e}") from None
    blink = bool(mode_control & 0x08)

    def index(nibble: int) -> int:
        reg = regs[nibble]
        low = ((select & 0x03) << 4 | reg & 0x0F) if mode_control & 0x80 else reg & 0x3F
        return (select & 0x0C) << 4 | low

    lut = vgadac.dac_colours(dac)
    out = bytearray()
    for i in range(0, len(page), vga.UNIT_BYTES[vga.TEXT]):
        char, attr = page[i], page[i + 1]
        back = (attr >> 4) & (0x07 if blink else 0x0F)
        out += bytes([char]) + lut[index(attr & 0x0F)] + lut[index(back)]
    return bytes(out)


def _crop(crop: Sequence[int] | None, shape: vga.Geometry) -> list[int]:
    """`crop` on the screen, in its own units (characters or pixels), judged inside it."""
    unit = "characters" if shape.source == vga.TEXT else "pixels"
    return list(raster.inside(crop, shape.width, shape.height, f"the screen ({unit})"))


def screen_view(session: ds.Session, crop: Sequence[int] | None, scale: int, dest: Path | None,
                scratch: Path) -> dict[str, Any]:
    """The body of `screen_view`: the text a text mode shows, or the 256-colour picture,
    written to `dest` or the scratch and attached; `crop` in characters or pixels. What `dest`
    and `scale` may be is judged on the mode alone, before the other listings are typed."""
    picture.check_scale(scale)
    if crop is not None:
        judges.rect("crop", crop)
    mode = vga.listed(session, vga.COMMAND_OF["mode"])
    source = vga.source_of(mode)
    if source == vga.TEXT and (dest is not None or scale):
        raise ds.Invalid("bad_argument", f"the screen is in `{mode.get('mode')}`, a text mode, "
                         f"which has no picture to write or scale: leave `dest` and `scale` out "
                         f"to read its text")
    if dest is not None:
        paths.fresh_dest("dest", dest)
    listings = {"mode": mode, **{key: vga.listed(session, vga.COMMAND_OF[key])
                                 for key in vga.SHAPE_KEYS[1:]}}
    shape = vga.geometry(listings)
    area = _crop(crop, shape)
    data = vga.read_screen(session, shape)
    reply = shape.head()
    reply["crop"] = area
    x0, y0, w, h = area
    if shape.source == vga.TEXT:
        rows = text_rows(data, shape.width, shape.height)
        cursor = shape.cursor
        reply.update(text=[row[x0:x0 + w].rstrip(" ") for row in rows[y0:y0 + h]],
                     cursor=[cursor[0] - x0, cursor[1] - y0] if cursor is not None
                     and x0 <= cursor[0] < x0 + w and y0 <= cursor[1] < y0 + h else None)
    else:
        _, dac = vgadac.read_dac(session)
        whole = png.Raster(shape.width, shape.height, data, tuple(vgadac.rgb8(e) for e in dac))
        reply["image"] = picture.publish(raster.cropped(whole, area), scale, dest, scratch,
                                         "screen")
    reply["display_start"] = shape.display_start
    return reply


def screen_signature(session: ds.Session, crop: Sequence[int] | None) -> dict[str, Any]:
    """The body of `screen_signature`: `scry_core.raster`'s signature of the screen, or of
    `crop` of it, a text cell resolved through the Attribute Controller and the DAC
    (`text_cells`), a pixel through the DAC."""
    if crop is not None:
        judges.rect("crop", crop)
    shape = vga.geometry(vga.read_listings(session))
    area = _crop(crop, shape)
    data = vga.read_screen(session, shape)
    _, dac = vgadac.read_dac(session)
    kind: raster.Kind
    if shape.source == vga.TEXT:
        cells, kind = text_cells(data, vga.listed(session, vga.COMMAND_OF["ac"]), dac), "text"
    else:
        lut = vgadac.dac_colours(dac)
        cells, kind = b"".join(lut[i] for i in data), "pixel"
    return {"signature": raster.signature(kind, shape.width, shape.height, cells, area),
            "kind": kind, **shape.head(), "crop": area}
