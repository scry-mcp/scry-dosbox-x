"""A picture from video memory as the VGA holds it, in the planar, unchained and linear modes."""
from __future__ import annotations

import functools
import struct

from scry_dosbox_x import vga

#: Each byte as eight bytes of 0 or 1, its high bit first: a plane's eight pixels.
_BITS = [int.from_bytes(bytes((b >> (7 - i)) & 1 for i in range(8)), "big") for b in range(256)]


def _rows(shape: vga.Geometry, data: bytes, width_bytes: int) -> list[bytes]:
    return [data[y * shape.stride:y * shape.stride + width_bytes] for y in range(shape.height)]


def planar(shape: vga.Geometry, data: bytes) -> bytes:
    """One byte a pixel, the 4-bit colour its four planes' bits make (plane 0 the low bit)."""
    out = bytearray()
    for row in _rows(shape, data, shape.width // 8 * vga.PLANES):
        for a in range(0, len(row), vga.PLANES):
            bits = (_BITS[row[a]] | _BITS[row[a + 1]] << 1 | _BITS[row[a + 2]] << 2
                    | _BITS[row[a + 3]] << 3)
            out += bits.to_bytes(8, "big")
    return bytes(out)


def indices(shape: vga.Geometry, data: bytes) -> bytes:
    """One byte a pixel, unchained or 8-bit linear: interleaved planes put pixel x at byte x."""
    return b"".join(_rows(shape, data, shape.width))


@functools.cache
def _wide_table(green_bits: int) -> list[bytes]:
    """Each 16-bit pixel as RGB (5 bits red and blue, `green_bits` green), widened by repeating
    each channel's high bits."""
    def wide(value: int, bits: int) -> int:
        return (value << (8 - bits) | value >> (2 * bits - 8)) & 0xFF
    table = []
    for w in range(1 << 16):
        g = (w >> 5) & ((1 << green_bits) - 1)
        r = (w >> (5 + green_bits)) & 0x1F
        table.append(bytes((wide(r, 5), wide(g, green_bits), wide(w & 0x1F, 5))))
    return table


def rgb(shape: vga.Geometry, data: bytes) -> bytes:
    """Three bytes a pixel in a 15-, 16- or 32-bit linear mode (32: blue, green, red, unused)."""
    size = vga.LINEAR_BYTES[shape.word]
    flat = b"".join(_rows(shape, data, shape.width * size))
    if size == 4:
        out = bytearray(len(flat) // 4 * 3)
        out[0::3], out[1::3], out[2::3] = flat[2::4], flat[1::4], flat[0::4]
        return bytes(out)
    table = _wide_table(6 if shape.word == "M_LIN16" else 5)
    return b"".join(table[w] for (w,) in struct.iter_unpack("<H", flat))
