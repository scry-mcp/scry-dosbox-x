"""Section Q of the live matrix: the media layer's scenarios, each asked twice over one answer, on
the screen guest (`tests/guest/screen.asm`) recorded with `capture_video`.

THE PAIR IS THE POINT. A new tool has no "before" of its own, so each scenario is answered the
way a session answers it with the tools it had and the new way, from the same files, and both
must reach the same answer. What each way cost (calls, the text units of its replies, the
visual tokens of the pictures they attached) is in the cell's detail.

S1, "which frames of the capture changed in region R": the hand way extracts each AVI frame with
`capture_frame` and compares the region's pixels here, with this file's own comparison; the new
way is `series_capture` and `region_track` over the same frames of the same file. S2, "is this
screen the golden": the golden is the 13h picture at the guest's 13h stop; the hand way looks at
the screen again and compares pixels, the new way compares one string; its control is the same
question at the next stop, where the guest moved the display start, which must come out no.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from matrix_common import M, boot, cells, ok, server
from matrix_screen import SCREEN_CONF, SCREEN_PROGRAM
from scry_core import png, raster, traffic

#: The region S1 asks about: the top of the 13h picture, where the guest's display start move
#: shows; and the most frames of the capture it reads.
S1_CROP = [0, 0, 320, 8]
S1_FRAMES_MAX = 24

Q_CELLS = cells(
    ("Q S1 hand: capture_frame per frame finds which frames of the capture changed in the crop",
     "known: compared here, pixel by pixel, from ffmpeg's own extraction of each frame"),
    ("Q S1 new: series_capture and region_track find the same frames, with no picture",
     "series_capture and region_track docstrings"),
    ("Q S1 cost: the new way takes fewer calls",
     "the honest comparison of a new tool is the job it replaces"),
    ("Q S2 hand: screen_view attaches the 13h screen and its pixels equal the golden's",
     "screen_view docstring: the picture, attached"),
    ("Q S2 new: screen_signature equals the golden's signature, and differs at the next stop",
     "screen_signature docstring; known: the guest's next step moves the display start"),
    ("Q S2 cost: the new way attaches no picture", "REFERENCE.md, Media files: a number first"),
)


def _cost(since: int) -> dict[str, int]:
    """Calls, text units and image tokens of the replies recorded since `since`."""
    replies = [c["reply"] for c in M.calls[since:]]
    return {"calls": len(replies), "units": sum(traffic.json_units(r) for r in replies),
            "image_tokens": sum(traffic.image_tokens(r) for r in replies)}


def _to_stop(name: str) -> None:
    """Resume the screen guest to its next `int 3`."""
    r = M.call(server.resume, seconds=30)
    if not (ok(r) and "stop_seq" in r):
        raise RuntimeError(f"the screen guest did not stop at its {name} step: {r}")


@M.section("Q", "the media layer: each scenario the hand way and the new way, over one answer",
           Q_CELLS)
def section_q() -> None:
    boot(conf=SCREEN_CONF, program=SCREEN_PROGRAM, break_on_int3=True, capture_video=True,
         captures_dir=M.fresh("-cap"))
    M.setup()
    for name in ("text", "start80", "dac01", "13h"):
        _to_stop(name)
    # S2 at the 13h stop: the golden, then the two ways.
    golden = M.fresh(".png")
    made = M.call(server.screen_view, scale=1, dest=golden)
    want = png.decode(Path(golden).read_bytes()) if ok(made) else None
    start = len(M.calls)
    look = M.call(server.screen_view)
    image = look.get("image") or {}
    # The attached picture is the screen enlarged; the golden enlarged by the same factor is
    # the same picture, pixel for pixel, when the screen is the golden.
    hand_ok = (want is not None and ok(look) and image.get("inline") is True
               and png.decode(Path(image["path"]).read_bytes())
               == png.enlarged(want, int(image.get("scale", 1))))
    hand_s2 = _cost(start)
    M.judge(Q_CELLS[3].label, hand_ok, f"cost {hand_s2}; {look.get('summary')}")
    start = len(M.calls)
    sig = M.call(server.screen_signature)
    new_s2 = _cost(start)
    golden_sig = raster.picture_signature(want) if want is not None else None
    _to_stop("13h-start80")
    later = M.call(server.screen_signature)
    M.judge(Q_CELLS[4].label, ok(sig) and sig.get("signature") == golden_sig and ok(later)
            and later.get("signature") != golden_sig,
            f"golden {golden_sig}, now {sig.get('signature')}, next stop {later.get('signature')}; "
            f"cost {new_s2}")
    M.judge(Q_CELLS[5].label, new_s2["image_tokens"] == 0 < hand_s2["image_tokens"],
            f"hand {hand_s2}, new {new_s2}")
    # S1 over the capture the 13h steps wrote: the newest file, by its number.
    caps = M.call(server.captures).get("captures") or []
    last: dict[str, Any] = max(caps, key=lambda c: str(c.get("path")), default={})
    count = min(int(last.get("frames") or 0), S1_FRAMES_MAX)
    source = str(last.get("path"))
    start = len(M.calls)
    pictures: list[bytes] = []
    for frame in range(count):
        dest = M.fresh(".png")
        r = M.call(server.capture_frame, at=frame, dest=dest, source=source)
        if ok(r):
            pictures.append(raster.rgb(raster.cropped(png.decode(Path(dest).read_bytes()),
                                                      S1_CROP)))
    hand = [i for i in range(1, len(pictures)) if pictures[i] != pictures[i - 1]]
    hand_s1 = _cost(start)
    M.judge(Q_CELLS[0].label, count >= 3 and len(pictures) == count and bool(hand),
            f"{count} frames of {source}, changes at {hand}; cost {hand_s1}")
    start = len(M.calls)
    series = M.call(server.series_capture, first=0, last=count - 1, crop=S1_CROP, source=source)
    track = (M.call(server.region_track, manifest=series["manifest"], measure="changed_pixels")
             if ok(series) else series)
    new = [f for f, _ in track.get("transitions", [])] if ok(track) else []
    new_s1 = _cost(start)
    # The guest moves the display start inside the capture, so the crop changes: an answer of no
    # change on either side is a missed crop, never agreement.
    M.judge(Q_CELLS[1].label, ok(series) and bool(hand) and new == hand
            and new_s1["image_tokens"] == 0,
            f"changes at {new} (hand {hand}); cost {new_s1}; {track.get('summary')}")
    # Cheaper only counts when the new way answered: a refused series is one call too.
    M.judge(Q_CELLS[2].label, ok(series) and ok(track) and new_s1["calls"] < hand_s1["calls"],
            f"hand {hand_s1}, new {new_s1}")
    M.call(server.close)
