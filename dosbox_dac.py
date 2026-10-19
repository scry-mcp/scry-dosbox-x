"""The VGA's DAC, read off the debugger (`VGA DAC`, `VGA DACPAL`): its six-bit entries as colours,
and the palette tool's swatch of them."""

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


#: The DAC width the colours are widened from, as `VGA DAC` prints it.
DAC_BITS = 6


SIX_BIT_MAX = (1 << DAC_BITS) - 1


#: A row: its first index, then two groups of four entries split by a `-`.
DACPAL_GROUP = r"((?:[0-9a-f]{6} ){3}[0-9a-f]{6})"


DACPAL_ROW = re.compile(rf"([0-9a-f]{{2}}): {DACPAL_GROUP}-{DACPAL_GROUP} ?")


DACPAL_PER_ROW = 8


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


def swatches(first: int, count: int, dac: list[str]) -> tuple[png.Raster, int | None]:
    """`palette`'s picture of entries `first` to `first + count - 1`: one square per entry,
    sixteen a row, each pixel the entry's index into the whole DAC; and the index drawn
    transparent, for the squares past the last entry of a short last row, which stand for an
    index the reply did not return (None when the last row is full)."""
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
    """`VGA DAC` (its width and mask) and `VGA DACPAL` (its 256 entries). A DAC not in its
    six-bit mode is refused: every colour here is widened from six bits."""
    command = vga.COMMAND_OF["dac"]
    dac = vga.listed(session, command)
    if dac.get("bits") != str(DAC_BITS):
        raise ds.Invalid("unexpected_answer",
            f"`{command}` says bits={dac.get('bits')}, and the colours are widened from the "
            f"{DAC_BITS}-bit DAC only")
    return dac, list(vga.read_parsed(session, DACPAL, parse_dacpal))


def palette(session: ds.Session, first: int, count: int, scale: int, dest: Path | None,
            scratch: Path) -> dict[str, Any]:
    """The body of `palette`: the DAC's width, mask and entries, and their picture, written to
    `dest` or the session's scratch and attached. `count` 0 is every entry from `first`."""
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
