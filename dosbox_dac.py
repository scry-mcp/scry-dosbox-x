"""The VGA DAC read off the debugger, and the palette tool's swatch of it."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from scry_core import picture, png

import dosbox_machine as machine
import dosbox_paths as paths
import dosbox_session as ds
import dosbox_vga as vga

DACPAL = "VGA DACPAL"


DACPAL_TITLE = "VGA DAC palette (RGB):"


DAC_ENTRIES = 256


DAC_BITS = 6


SIX_BIT_MAX = (1 << DAC_BITS) - 1


#: A row: first index, then two groups of four entries split by `-`.
DACPAL_GROUP = r"((?:[0-9a-f]{6} ){3}[0-9a-f]{6})"


DACPAL_ROW = re.compile(rf"([0-9a-f]{{2}}): {DACPAL_GROUP}-{DACPAL_GROUP} ?")


DACPAL_PER_ROW = 8


def parse_dacpal(text: str) -> list[str]:
    """`VGA DACPAL`: the 256 entries as printed (`00002a`); a component past six bits is refused."""
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


def channel(six_bits: int) -> int:
    """A six-bit component as the emulator's eight-bit channel: top two bits repeated below."""
    return (six_bits << 2) | (six_bits >> 4)


def rgb8(entry: str) -> tuple[int, int, int]:
    """An entry (`00002a`) to its eight-bit `(r, g, b)`."""
    r, g, b = (channel(int(entry[i:i + 2], 16)) for i in (0, 2, 4))
    return r, g, b


def color(entry: str) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb8(entry))


SWATCH_PX = 16


SWATCHES_PER_ROW = 16


def swatches(first: int, count: int, dac: list[str]) -> tuple[png.Raster, int | None]:
    """One square per entry, each pixel its index into the whole DAC; plus the filler index
    drawn transparent for a short last row (None when full)."""
    cols, rows = min(count, SWATCHES_PER_ROW), math.ceil(count / SWATCHES_PER_ROW)
    short = cols * rows > count
    filler = first + count if first + count < DAC_ENTRIES else first - 1
    width, height = cols * SWATCH_PX, rows * SWATCH_PX
    out = bytearray()
    for y in range(height):
        for x in range(width):
            k = (y // SWATCH_PX) * SWATCHES_PER_ROW + x // SWATCH_PX
            out.append(first + k if k < count else filler)
    return (png.Raster(width, height, bytes(out), tuple(rgb8(e) for e in dac)),
            filler if short else None)


def read_dac(session: ds.Session) -> tuple[dict[str, Any], list[str]]:
    """`VGA DAC` (width, mask) and `VGA DACPAL`; a DAC not in six-bit mode is refused."""
    command = vga.COMMAND_OF["dac"]
    dac = vga.listed(session, command)
    if dac.get("bits") != str(DAC_BITS):
        raise ds.Invalid("unexpected_answer",
            f"`{command}` says bits={dac.get('bits')}, and the colours are widened from the "
            f"{DAC_BITS}-bit DAC only")
    return dac, list(vga.read_parsed(session, DACPAL, parse_dacpal))


def palette(session: ds.Session, first: int, count: int, scale: int, dest: Path | None,
            scratch: Path) -> dict[str, Any]:
    """The body of `palette`; `count` 0 is every entry from `first`."""
    picture.check_scale(scale)
    if dest is not None:
        paths.fresh_dest("dest", dest)
    dac, entries = read_dac(session)
    count = count or DAC_ENTRIES - first
    chosen = entries[first:first + count]
    swatch, clear = swatches(first, count, entries)
    return {"entries": len(entries), "first": first, "count": len(chosen),
            "colors": [color(e) for e in chosen], "rgb": chosen,
            "bits": DAC_BITS, "pel_mask": dac.get("pel_mask"),
            # No recorder: `captures` lists the emulator's own recordings only.
            "image": picture.publish(swatch, scale, dest, scratch, "palette", clear=clear)}


def dac_colours(dac: list[str]) -> list[bytes]:
    """Each DAC entry as the RGB bytes the emulator renders it in."""
    return [bytes(rgb8(e)) for e in dac]
