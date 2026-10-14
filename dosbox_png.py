"""An indexed PNG, written with the standard library alone, and the file it goes to.

A picture of palette indices is written as one: each pixel's byte IS the index the guest put in
video memory, and the PLTE chunk carries the colours. A reader that wants the data reads the
indices back unchanged; a viewer shows the colours. Colour type 3, eight bits a sample, no
interlace, every row filtered with type 0, so the file's IDAT is the raster itself, deflated.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import dosbox_session as ds

SIGNATURE = b"\x89PNG\r\n\x1a\n"
#: Colour type 3 is "each pixel a palette index"; the PLTE chunk is then required.
INDEXED = 3
#: The most entries a PLTE holds: an index is one byte.
PLTE_MAX = 256

ALREADY_THERE = "already exists. This will not overwrite it: name a path that is not there yet"


def indexed(width: int, height: int, pixels: bytes,
            palette: Sequence[tuple[int, int, int]], clear: int | None = None) -> bytes:
    """The PNG file of a `width` x `height` raster of palette indices, row after row, and the
    palette's 8-bit `(r, g, b)` entries, 1 to 256 of them. `clear` names one index drawn fully
    transparent (a tRNS chunk), for pixels that stand for no entry at all. An index past the
    palette is refused: a viewer has no colour for it."""
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ValueError(f"{len(pixels)} pixels are not a {width} x {height} raster")
    if not 1 <= len(palette) <= PLTE_MAX:
        raise ValueError(f"a PLTE holds 1 to {PLTE_MAX} entries, not {len(palette)}")
    top = max(pixels) if clear is None else max(max(pixels), clear)
    if top >= len(palette):
        raise ValueError(f"index {top} is past the {len(palette)} entries of the palette")
    rows = b"".join(b"\x00" + pixels[y * width:(y + 1) * width] for y in range(height))
    chunks = (
        (b"IHDR", struct.pack(">IIBBBBB", width, height, 8, INDEXED, 0, 0, 0)),
        (b"PLTE", bytes(c for rgb in palette for c in rgb)),
        *(() if clear is None else ((b"tRNS", b"\xff" * clear + b"\x00"),)),
        (b"IDAT", zlib.compress(rows, 9)),
        (b"IEND", b""),
    )
    out = bytearray(SIGNATURE)
    for kind, body in chunks:
        out += struct.pack(">I", len(body)) + kind + body
        out += struct.pack(">I", zlib.crc32(kind + body))
    return bytes(out)


def write(dest: Path, width: int, height: int, data: bytes) -> dict[str, Any]:
    """`data` to `dest`, created there and never written over, and the reply's `image`. A write
    that fails part-way removes what it created, so the next call is not refused over it."""
    try:
        f = dest.open("xb")
    except FileExistsError:
        raise ds.Invalid("bad_argument", f"{dest} {ALREADY_THERE}") from None
    except (OSError, ValueError) as e:
        raise ds.Invalid("bad_argument", f"{dest} cannot be written: {e}") from None
    try:
        with f:
            f.write(data)
    except OSError as e:
        dest.unlink(missing_ok=True)
        raise ds.Invalid("bad_argument", f"{dest} cannot be written: {e}") from None
    return {"path": str(dest), "sha256": hashlib.sha256(data).hexdigest(), "width": width,
            "height": height, "indexed": True}
