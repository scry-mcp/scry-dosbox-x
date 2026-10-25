"""What the DOS machine's screen shows at a stop, in a text mode or the chained 256-colour mode."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scry_core import judges, picture, png, raster, screen_map
from scry_core.reply_contract import unavailable

import dosbox_dac as vgadac
import dosbox_paths as paths
import dosbox_session as ds
import dosbox_vga as vga

#: The IBM PC's glyphs for the control bytes 01-1F.
CONTROL_GLYPHS = "☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼"
#: 00 and FF draw as blank cells, so they read as the space a blank cell is.
CP437 = [" ", *CONTROL_GLYPHS,
         *(bytes([b]).decode("cp437") for b in range(0x20, 0x7F)), "⌂",
         *(bytes([b]).decode("cp437") for b in range(0x80, 0xFF)), " "]


def text_rows(page: bytes, width: int, height: int) -> list[str]:
    """Each row as text through code page 437's glyphs, trailing blanks dropped."""
    unit = vga.UNIT_BYTES[vga.TEXT]
    return ["".join(CP437[page[(r * width + c) * unit]] for c in range(width)).rstrip(" ")
            for r in range(height)]


def text_cells(page: bytes, ac: dict[str, Any], dac: list[str]) -> bytes:
    """Each text cell as `scry_core.raster` hashes it: CP437 byte, then foreground and
    background RGB as the VGA resolves them (AC palette register, `color-select`, then the DAC).
    With `mode_control` bit 3 (blink) the background has three bits and the fourth blinks."""
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
    """`crop` judged inside the screen, in characters or pixels."""
    unit = "characters" if shape.source == vga.TEXT else "pixels"
    return list(raster.inside(crop, shape.width, shape.height, f"the screen ({unit})"))


def screen_view(session: ds.Session, crop: Sequence[int] | None, scale: int, dest: Path | None,
                scratch: Path, attach: bool = True) -> dict[str, Any]:
    """The body of `screen_view`; `dest`, `scale` and `attach` are judged on the mode alone,
    before the other listings are typed."""
    picture.check_scale(scale)
    picture.check_attach(attach)
    if crop is not None:
        judges.rect("crop", crop)
    mode = vga.listed(session, vga.COMMAND_OF["mode"])
    source = vga.source_of(mode)
    if source == vga.TEXT and (dest is not None or scale or not attach):
        raise ds.Invalid("bad_argument", f"the screen is in `{mode.get('mode')}`, a text mode, "
                         f"which has no picture to write, scale or attach: leave `dest`, `scale` "
                         f"and `attach` out to read its text")
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
                     and x0 <= cursor[0] < x0 + w and y0 <= cursor[1] < y0 + h else
                     unavailable("the cursor is hidden or outside the crop"))
    else:
        _, dac = vgadac.read_dac(session)
        whole = png.Raster(shape.width, shape.height, data, tuple(vgadac.rgb8(e) for e in dac))
        reply["image"] = picture.publish(raster.cropped(whole, area), scale, dest, scratch,
                                         "screen", attach=attach)
    reply["display_start"] = shape.display_start
    return reply


def screen_signature(session: ds.Session, crop: Sequence[int] | None) -> dict[str, Any]:
    """The body of `screen_signature`: the signature of the screen or of `crop` of it."""
    if crop is not None:
        judges.rect("crop", crop)
    read, shape = grid(session)
    area = _crop(crop, shape)
    return {"signature": raster.signature(read.kind, shape.width, shape.height, read.cells,
                                          area),
            "kind": read.kind, **shape.head(), "crop": area}


def grid(session: ds.Session) -> tuple[screen_map.Grid, vga.Geometry]:
    """ONE read of the screen as `scry_core.raster` signs it, and its shape."""
    shape = vga.geometry(vga.read_listings(session))
    data = vga.read_screen(session, shape)
    _, dac = vgadac.read_dac(session)
    if shape.source == vga.TEXT:
        return screen_map.Grid("text", shape.width, shape.height,
                               text_cells(data, vga.listed(session, vga.COMMAND_OF["ac"]),
                                          dac)), shape
    lut = vgadac.dac_colours(dac)
    return screen_map.Grid("pixel", shape.width, shape.height,
                           b"".join(lut[i] for i in data)), shape
