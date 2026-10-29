"""What the DOS machine's screen shows at a stop, in a text mode or a graphics mode."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scry_core import fresh, judges, picture, png, raster, screen_map
from scry_core.reply_contract import unavailable

from scry_dosbox_x import dac as vgadac
from scry_dosbox_x import frames, paths, vga
from scry_dosbox_x import screen_pens as by_pens
from scry_dosbox_x import session as ds
from scry_dosbox_x import video_memory as video

#: `snapshot`'s `route` when it reads video memory at a stop (the running route is `guest`).
STOP_ROUTE = "video_memory"
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


def ac_indices(ac: dict[str, Any]) -> bytes:
    """The DAC entry each of the sixteen colours resolves to: the colour masked by
    `color-plane-en`, its AC palette register, then `color-select` (bits 5-4 replacing the
    register's when `mode_control` bit 7 says so)."""
    try:
        regs = [int(r, 16) for r in ac["palette"]]
        mode_control, select = vga.hex_word(ac["mode_control"]), vga.hex_word(ac["color_select"])
        enabled = vga.hex_word(ac["color_plane_en"]) & 0x0F
    except (KeyError, ValueError) as e:
        raise ds.Invalid("unexpected_answer", f"`VGA AC` lacks a word a colour is resolved "
                         f"by, or prints it in another shape: {e}") from None

    def index(nibble: int) -> int:
        reg = regs[nibble & enabled]
        low = ((select & 0x03) << 4 | reg & 0x0F) if mode_control & 0x80 else reg & 0x3F
        return (select & 0x0C) << 4 | low
    return bytes(index(n) for n in range(16))


def text_cells(page: bytes, ac: dict[str, Any], dac: list[str]) -> bytes:
    """Each text cell as `scry_core.raster` hashes it: CP437 byte, then foreground and
    background RGB as the VGA resolves them (`ac_indices`, then the DAC). With `mode_control`
    bit 3 (blink) the background has three bits and the fourth blinks."""
    resolved = ac_indices(ac)
    blink = bool(vga.hex_word(ac["mode_control"]) & 0x08)

    def index(nibble: int) -> int:
        return resolved[nibble]

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
                scratch: Path, attach: bool = True, view: str = "render",
                pens: list[int] | None = None, point: list[int] | None = None) -> dict[str, Any]:
    """The body of `screen_view`; `dest`, `scale` and `attach` are judged on the mode alone,
    before the other listings are typed. `view` is the tool's `mode`, the VGA mode being `mode`
    here."""
    picture.check_scale(scale)
    picture.check_attach(attach)
    if crop is not None:
        judges.rect("crop", crop)
    by_pens.check_view(view, pens, point, None if crop is None else list(crop), scale,
                       "" if dest is None else str(dest), attach)
    mode = vga.listed(session, vga.COMMAND_OF["mode"])
    source = vga.source_of(mode)
    if source == vga.TEXT and view != "render":
        raise by_pens.needs_pens(view, f"the screen is in `{mode.get('mode')}`, a text mode")
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
    reply["mode"] = view
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
        whole = pixels(session, shape, data)
        if whole.palette is None and view != "render":
            raise by_pens.needs_pens(
                view, f"the screen is in `{mode.get('mode')}`, drawn in direct colour")
        if view == "render":
            reply["screen_indexed"] = whole.palette is not None
            if whole.palette is not None:
                reply["entries"] = len(whole.palette)
            reply["image"] = picture.publish(raster.cropped(whole, area), scale, dest, scratch,
                                             "screen", attach=attach)
        else:
            reply.update(by_pens.view(whole, view, pens, point, area, scale, dest, scratch,
                                      attach))
    reply["display_start"] = shape.display_start
    return reply


def still(session: ds.Session, dest: Path | None) -> dict[str, Any]:
    """`snapshot` at a stop: the graphics screen as one unscaled PNG written from video memory
    through the decoder `screen_view` uses, at `dest` or the next free name in the captures
    directory."""
    listings = vga.read_listings(session)
    if vga.source_of(listings["mode"]) == vga.TEXT:
        raise ds.Invalid("no_channel", f"the screen is in `{listings['mode'].get('mode')}`, a "
                         f"text mode, which has no picture to snapshot at a stop: `screen_view` "
                         f"reads its text, or `resume` and snapshot the running screen")
    if dest is not None:
        paths.fresh_dest("dest", dest)
    shape = vga.geometry(listings)
    data = png.encode(pixels(session, shape, vga.read_screen(session, shape)))
    if dest is None:
        path = fresh.numbered(frames.folder(session), lambda n: f"snapshot-{n}.png", data,
                              "the snapshot")
    else:
        fresh.create(dest, data, "the snapshot", named_by_caller=True)
        path = dest
    return {"route": STOP_ROUTE, **judges.file_facts(path)}


def screen_signature(session: ds.Session, crop: Sequence[int] | None) -> dict[str, Any]:
    """The body of `screen_signature`: the signature of the screen or of `crop` of it."""
    if crop is not None:
        judges.rect("crop", crop)
    read, shape = grid(session)
    area = _crop(crop, shape)
    return {"signature": raster.signature(read.kind, shape.width, shape.height, read.cells,
                                          area),
            "kind": read.kind, **shape.head(), "crop": area}


def shown_dac(session: ds.Session) -> list[str]:
    """The DAC entry each index shows: the DAC is looked up at the index AND the PEL mask."""
    info, dac = vgadac.read_dac(session)
    mask = vga.hex_word(info.get("pel_mask", "ffh"))
    return [dac[i & mask] for i in range(len(dac))]


def grid(session: ds.Session, indices: bool = False) -> tuple[screen_map.Grid, vga.Geometry]:
    """ONE read of the screen as `scry_core.raster` signs it, and its shape; `indices` adds the
    DAC indices of a mode drawn through the DAC."""
    shape = vga.geometry(vga.read_listings(session))
    data = vga.read_screen(session, shape)
    if shape.source == vga.TEXT:
        dac = shown_dac(session)
        return screen_map.Grid("text", shape.width, shape.height,
                               text_cells(data, vga.listed(session, vga.COMMAND_OF["ac"]),
                                          dac)), shape
    picture = pixels(session, shape, data)
    drawn = (raster.index_cells(picture.pixels)
             if indices and picture.palette is not None else None)
    return screen_map.Grid("pixel", shape.width, shape.height, raster.rgb(picture), drawn), shape


def pixels(session: ds.Session, shape: vga.Geometry, data: bytes) -> png.Raster:
    """The picture `data` holds in `shape`'s mode: indices with the DAC as their palette, or
    RGB in a 15-, 16- or 32-bit linear mode, which uses no palette."""
    if shape.source == vga.LINEAR and vga.LINEAR_BYTES[shape.word] > 1:
        return png.Raster(shape.width, shape.height, video.rgb(shape, data))
    dac = shown_dac(session)
    if shape.source == vga.PLANAR:
        resolved = ac_indices(vga.listed(session, vga.COMMAND_OF["ac"]))
        indices = video.planar(shape, data).translate(resolved + bytes(range(16, 256)))
    elif shape.source in vga.MEMORY_SOURCES:
        indices = video.indices(shape, data)
    else:
        indices = data
    return png.Raster(shape.width, shape.height, indices, tuple(vgadac.rgb8(e) for e in dac))
