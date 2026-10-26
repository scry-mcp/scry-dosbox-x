"""What `tests/guest/planes.asm` drew at each pixel, by its stop's mode word."""
from __future__ import annotations


def known(word: str, x: int, y: int) -> int | tuple[int, int, int]:
    if word == "M_EGA":
        return (x + y) & 0x0F
    if word == "M_VGA":
        return (2 * x + y) & 0xFF
    if word == "M_LIN8":
        return (x ^ y) & 0xFF
    if word == "M_LIN32":
        value = y << 12 | x
        return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    pixel = (y & 0xFF) << 8 | (x & 0xFF)
    green = 6 if word == "M_LIN16" else 5
    r, g, b = pixel >> (5 + green) & 0x1F, pixel >> 5 & ((1 << green) - 1), pixel & 0x1F
    return r << 3 | r >> 2, g << (8 - green) | g >> (2 * green - 8), b << 3 | b >> 2
