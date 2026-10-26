"""Section W of the live matrix: the screen read from video memory itself (`VGAMEMDUMP`), on the
package's planes guest (`tests/guest/planes.asm`), whose six stops each hold a picture made of
its own arithmetic in a mode the CPU's window cannot read whole."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from matrix_common import GUEST, M, boot, cells, close_whatever, ok, said, server
from planes_known import known
from scry_core import judges

PLANES_PROGRAM = "PLANES.COM"
SCREEN_CONF = GUEST / "screen.conf"
#: Each stop's mode word and size, in the guest's order.
STOPS = (("M_EGA", 640, 480), ("M_VGA", 320, 200), ("M_LIN8", 640, 480),
         ("M_LIN15", 640, 480), ("M_LIN16", 640, 480), ("M_LIN32", 640, 480))

W_CELLS = cells(*(
    (f"W screen_view in {word} is the guest's own picture, pixel for pixel",
     "screen_view docstring; known: planes.asm's header, step by step")
    for word, _, _ in STOPS), (
    "W screen_signature answers in every mode read from video memory",
    "screen_signature docstring"))


def _ac_index(vga: dict[str, Any], nibble: int) -> int:
    """A 16-colour index through the AC's palette register, as the BIOS left its controls."""
    return int(vga["ac"]["palette"][nibble], 16) & 0x3F


def _matches(word: str, width: int, height: int, view: dict[str, Any]) -> bool:
    raster, _ = judges.picture_file("image", Path(view["image"]["path"]))
    vga = M.call(server.machine_map, sections=["vga"]).get("vga") or {}
    # A small mode's picture is enlarged a whole number of times; its pixels are read through it.
    scale = raster.width // width
    for y in range(0, height, 23):
        for x in range(0, width, 17):
            want = known(word, x, y)
            if raster.palette is None:
                at = (y * scale * raster.width + x * scale) * 3
                if tuple(raster.pixels[at:at + 3]) != want:
                    return False
            else:
                assert isinstance(want, int)
                index = _ac_index(vga, want) if word == "M_EGA" else want
                if raster.pixels[y * scale * raster.width + x * scale] != index:
                    return False
    return True


@M.section("W", "the screen read from video memory, on the package's planes guest", W_CELLS)
def section_w() -> None:
    boot(conf=SCREEN_CONF, program=PLANES_PROGRAM, break_on_int3=True)
    signed = True
    for cell, (word, width, height) in zip(W_CELLS, STOPS, strict=False):
        stop = M.call(server.resume, seconds=30)
        view = M.call(server.screen_view, dest=M.fresh(".png"), attach=False)
        sig = M.call(server.screen_signature)
        signed = signed and ok(sig) and sig.get("kind") == "pixel"
        M.judge(cell.label, ok(stop) and ok(view) and view.get("vga_mode") == word
                and (view.get("width"), view.get("height")) == (width, height)
                and _matches(word, width, height, view), said(view))
    M.judge(W_CELLS[-1].label, signed, "every stop's signature was a pixel one")
    close_whatever()
