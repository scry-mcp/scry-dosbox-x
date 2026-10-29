"""`screen_view`'s views by pen: which pixels hold a pen, which pens a region uses, which pen is
under a point. A pen is the DAC entry a pixel of a palette-indexed mode holds, so text and
direct-colour modes have none and refuse these views by name."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scry_core import picture, png, raster
from scry_core.pens import (
    INDEX_MODES,
    MODES,
    PENS_MAX,
    POINT_RINGS,
    hex_colour,
    isolated,
    isolation,
    pixel_crop,
    runs,
)
from scry_core.reply_contract import Invalid

__all__ = ["INDEX_MODES", "MODES", "PENS_MAX", "check_view", "needs_pens", "view"]
#: A VGA DAC's last entry.
PEN_LIMIT = 255


def check_view(mode: str, pens: list[int] | None, point: list[int] | None,
               crop: list[int] | None, scale: int, dest: str, attach: bool) -> None:
    """The arguments of a view, judged before the machine is asked: the mode, the arguments that
    mode takes and no other (one it would ignore is refused, never dropped), and their shapes."""
    if mode not in MODES:
        raise Invalid("bad_argument", f"mode={mode!r} is one of {', '.join(MODES)}")
    if (pens is not None) != (mode == "isolate"):
        raise Invalid("bad_argument", "`pens` goes with mode `isolate`, and `isolate` needs it: "
                      "the pens to show")
    if pens is not None and not (
            isinstance(pens, list) and 1 <= len(pens) <= PENS_MAX
            and all(isinstance(p, int) and not isinstance(p, bool) and 0 <= p <= PEN_LIMIT
                    for p in pens)):
        raise Invalid("bad_argument",
                      f"pens={pens!r}: 1..{PENS_MAX} pen numbers, each 0..{PEN_LIMIT}")
    if (point is not None) != (mode == "pixel"):
        raise Invalid("bad_argument", "`point` goes with mode `pixel`, and `pixel` needs it: "
                      "[x, y] on the screen")
    if point is not None and not (
            isinstance(point, list) and len(point) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in point)):
        raise Invalid("bad_argument", f"point={point!r} is [x, y], each at or above zero")
    if crop is not None and mode == "pixel":
        raise Invalid("bad_argument", "mode `pixel` takes `point` instead of `crop`")
    if mode == "histogram" and (scale or dest or attach is not True):
        raise Invalid("bad_argument", "mode `histogram` answers no picture, so `scale`, `dest` "
                      "and `attach` would do nothing")


def needs_pens(mode: str, why: str) -> Invalid:
    """The refusal of a view by pens on a screen that holds none."""
    return Invalid("no_channel", f"{why}, so it holds no pens: mode `{mode}` needs a "
                   "palette-indexed graphics mode, and `render` shows what the screen holds")


def view(whole: png.Raster, mode: str, pens: list[int] | None, point: list[int] | None,
         area: list[int], scale: int, dest: Path | None, scratch: Path,
         attach: bool) -> dict[str, Any]:
    """The reply fields of a view by pens over the palette-indexed screen `whole`."""
    palette = whole.palette
    assert palette is not None
    fields: dict[str, Any] = {"screen_indexed": True, "entries": len(palette)}
    if mode == "pixel":
        assert point is not None
        return fields | _pixel(whole, point, scale, dest, scratch, attach)
    window = raster.cropped(whole, area)
    fields["crop"] = area
    if mode == "histogram":
        counts: dict[int, int] = {}
        for pen in window.pixels:
            counts[pen] = counts.get(pen, 0) + 1
        fields.update(histogram=[[p, counts[p]] for p in sorted(counts)], pens_used=len(counts),
                      unused=runs([p for p in range(len(palette)) if p not in counts]))
        return fields
    selected = set(pens or ())
    if mode == "isolate":
        x0, y0, w, _ = area
        fields.update(isolation(window.pixels, w, x0, y0, selected))
        window = png.Raster(window.width, window.height, window.pixels,
                            tuple(isolated(c, p in selected) for p, c in enumerate(palette)))
    fields["image"] = picture.publish(window, scale, dest, scratch, "screen", attach=attach)
    return fields


def _pixel(whole: png.Raster, point: list[int], scale: int, dest: Path | None, scratch: Path,
           attach: bool) -> dict[str, Any]:
    x, y = point
    if x >= whole.width or y >= whole.height:
        raise Invalid("bad_argument", f"point [{x}, {y}] is off the {whole.width}x{whole.height} "
                      "screen")
    assert whole.palette is not None
    pen = whole.pixels[y * whole.width + x]
    crop = pixel_crop(x, y, whole.width, whole.height)
    cx, cy, cw, ch = crop
    window = raster.cropped(whole, crop)
    colours = png.Raster(cw, ch, raster.rgb(window))
    rings: list[picture.Ring] = [(x - cx, y - cy, 1, 1, rgb, gap)
                                 for gap, rgb in enumerate(POINT_RINGS, 1)]
    return {"x": x, "y": y, "pen": pen, "color": hex_colour(whole.palette[pen]),
            "crop": crop, "point_in_crop": [x - cx, y - cy],
            "image": picture.publish(colours, scale, dest, scratch, "pixel", rings=rings,
                                     border=len(POINT_RINGS), attach=attach)}
