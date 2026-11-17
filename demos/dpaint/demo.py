"""The Deluxe Paint demo: Electronic Arts' Deluxe Paint II (1988)
painting a sunset through the calls the README's prompt asks an MCP client to make, each answer
checked. `--help` says how to run it.

It paints the way a person would, with tools and colours picked by name off a screen map, and
stops once in the middle to do what no mouse macro can: two clicks on the palette and a value
scan between them find the byte where the program keeps its current colour, and a watch then
shows it at every stop. Each shape is checked by reading the pixels back out of video memory.

Nothing of the program is in this repository: `--cwd` names the directory holding `DP.EXE`,
which the session runs from and mounts as C:, and the demo refuses any `DP.EXE` other than the
release it was written for, because the colour's address and the picture are that build's.
Deluxe Paint takes the mouse as movement events, so the DOSBox-X has to be one whose input
device carries relative motion; without it a drag paints nothing between its button events.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scry_core.demo import Moment, Reply, Run, Step, main, window_args

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import host  # noqa: E402
from demos.dpaint.program import (  # noqa: E402
    click,
    declared,
    drag,
    ds_segment,
    opening,
    recorded,
)
from demos.host import expect, isolated_store, pictured  # noqa: E402

HERE = Path(__file__).resolve().parent
#: The palette indices of the swatches the screen map names.
COLOURS = {"navy": 1, "brown": 6, "blue": 9, "yellow": 14, "white": 15, "peach": 52,
           "orange": 55}
#: Where this build keeps the current colour: four static bytes of its data segment, which every
#: pick of a colour rewrites. A scan also keeps copies in the stack's frames, above the stack
#: pointer, which move with where the stop lands.
COLOUR_STATICS = (0x017C, 0x01AE, 0x0470, 0x10B0)
#: The scene, in screen pixels: the sky and the sea as rectangles corner to corner, the sun as a
#: centre and a point on its rim, the boat's hull and its mast and sail as line segments.
SKY, SEA = ((2, 14), (294, 112)), ((2, 113), (294, 198))
SUN = ((210, 112), (238, 112))
HULL = ((60, 150), (112, 158))
SAIL = [((86, 149), (86, 118)), ((86, 118), (108, 146)), ((108, 146), (86, 146))]
TEXT_AT = (20, 180)
WORD = "SCRY"


def boot(run: Run) -> dict[str, Any]:
    """A fresh log of this demo's own under the run's, so nothing an earlier run left is read,
    and the saved states there too: left out, they would go into the program's directory."""
    (run.dir / "dpaint-e9.log").unlink(missing_ok=True)
    return {**window_args(run), **recorded(run), "conf": HERE / "dpaint.conf",
            "session_seconds": 900, "program": "DP.EXE f",
            "logfile": run.dir / "dpaint-e9.log", "state_dir": run.dir / "dpaint-states"}


def found(reply: Reply, run: Run) -> str:
    expect(reply["matched"] is True and reply["screen"] == "paint", f"matched {reply}")
    return f"the painting screen, {len(reply['controls'])} controls named"


def picked(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["driver_arrived"] is True,
               f"the pointer read back at {reply['pointer']['screen']}")
        return what
    return check


def scan_start(run: Run) -> dict[str, Any]:
    return {"method": "start", "ref": f"{ds_segment(run):04X}:0000", "length": 0xFFFF,
            "cell_bytes": 1}


def candidates(reply: Reply, run: Run) -> str:
    return f"{reply['hits_total']} bytes of the data segment are candidates"


def narrowed(reply: Reply, run: Run) -> str:
    return f"{reply['hits_total']} bytes hold {reply['value']} now"


def colour_found(reply: Reply, run: Run) -> str:
    """The survivors below the stack pointer of the orange pick's stop are the static ones."""
    sp = int(run.replies["orange"]["regs"]["ESP"], 16) & 0xFFFF
    offsets = [int(hit["seg_off"].split(":")[1], 16) for hit in reply["hits"]]
    statics = tuple(o for o in offsets if o < sp)
    expect(statics == COLOUR_STATICS, f"the survivors below the stack pointer {sp:04X} are "
                                      f"{[f'{o:04X}' for o in statics]}")
    expect(reply["truncated"] is False, f"{reply['hits_total']} survivors, not all listed")
    return (f"{len(offsets)} bytes followed both clicks: {len(offsets) - len(statics)} in the "
            f"stack's frames above the stack pointer, and {len(statics)} static ones from "
            f"{ds_segment(run):04X}:{COLOUR_STATICS[0]:04X}")


def colour_ref(run: Run) -> str:
    return f"{ds_segment(run):04X}:{COLOUR_STATICS[0]:04X}"


def shape(name: str, tool: str | None, colour: str | None,
          strokes: list[tuple[tuple[int, int], tuple[int, int]]]) -> Step:
    """One shape in one call: its tool and colour picked by name off the map, then its drags."""
    steps = ([click(tool)] if tool else []) + ([click(colour)] if colour else [])
    steps += [op for a, b in strokes for op in drag(a, b)]
    shown = COLOURS[colour] if colour else None

    def check(reply: Reply, run: Run) -> str:
        expect(reply["steps_completed"] == len(steps), f"{reply['steps_completed']} of "
               f"{len(steps)} steps, failed at {reply['failed_at']}")
        watched = reply["ran"][-1]["reply"]["watches"][0]["value"]
        if shown is not None:
            expect(watched == shown, f"the colour byte shows {watched}, not {colour}'s {shown}")
        picked = f"{colour}, the colour byte at {watched}, " if colour else ""
        return f"{picked}{len(strokes)} drag{'s' if len(strokes) > 1 else ''}"
    return Step(name, "perform", {"steps": steps, "summaries": True}, check)


def typed(reply: Reply, run: Run) -> str:
    expect(reply["steps_completed"] == 4, f"{reply['steps_completed']} of 4 steps, failed at "
                                           f"{reply['failed_at']}")
    return (f"{WORD} typed at {TEXT_AT[0]},{TEXT_AT[1]}, then the line tool again, which ends "
            "the text")


def row(y: int, x: int, length: int) -> dict[str, Any]:
    """`read_memory`'s arguments for `length` pixels of row `y` from `x`, in mode 13h."""
    return {"ref": f"A000:{y * 320 + x:04X}", "length": length}


def crossing(*spans: tuple[str, int]) -> Any:
    """A row of video memory that crosses the scene's colours in this order."""
    return host.crossing(COLOURS, lambda reply: bytes.fromhex(reply["hex"]), *spans)


STEPS = [
    *opening(boot, HERE / "dpaint-screen-map.json", "paint"),
    Step("find", "screen_map_find", {}, found),
    Step("blue", "send_mouse", {"target": "blue", "button": "left"},
         picked("blue picked off the palette"),
         title="Click a control by its name",
         ask="Pick blue on Deluxe Paint's palette.",
         shown=("summary", "target", "driver_arrived"),
         reads=("The screen map says where `blue` sits, so the call holds no coordinates. "
                "`driver_arrived` is true when the program's own mouse driver reports the "
                "pointer there.")),
    Step("scan", "scan", scan_start, candidates),
    Step("is blue", "scan", {"method": "filter", "value": COLOURS["blue"], "limit": 8},
         narrowed),
    Step("orange", "send_mouse", {"target": "orange", "button": "left"},
         picked("orange picked off the palette")),
    Step("is orange", "scan", {"method": "filter", "value": COLOURS["orange"]}, colour_found,
         title="Find the byte that holds the colour",
         ask="Orange is picked now. Keep only the bytes of the scan that hold orange's number.",
         shown=("summary", "hits_total"),
         reads=("`hits_total` counts the bytes still in the scan: they held blue's number, then "
                "orange's. The ones below the stack pointer are the program's own variables.")),
    Step("unscan", "scan", {"method": "clear"}, lambda reply, run: "scan closed"),
    Step("watch", "watch_add", lambda run: {"ref": colour_ref(run), "mode": "show",
                                            "fmt": "u8"},
         lambda reply, run: "the colour byte shown at every stop"),
    shape("sky", "rect_filled", "peach", [SKY]),
    shape("sun", "circle_filled", "yellow", [SUN]),
    shape("sea", "rect_filled", "navy", [SEA]),
    shape("hull", None, "brown", [HULL]),
    shape("sail", "line", "white", SAIL),
    Step("word", "perform", {"steps": [
        click("text"),
        {"op": "send_mouse", "x": TEXT_AT[0], "y": TEXT_AT[1], "button": "left"},
        {"op": "send_keys", "keys": list(WORD), "modifiers": ["shift"]},
        click("line")], "summaries": True}, typed),
    Step("sun row", "read_memory", lambda run: row(100, 160, 128),
         crossing(("peach", 25), ("yellow", 51), ("peach", 52)),
         title="Read the picture back out of video memory",
         ask="Read 128 bytes of video memory from row 100, column 160.",
         shown=("summary", "length"),
         reads=("In this video mode each byte is one pixel's colour number. The row holds 25 "
                "pixels of sky, 51 of sun and 52 of sky, as painted.")),
    Step("boat row", "read_memory", lambda run: row(154, 30, 112),
         crossing(("navy", 30), ("brown", 53), ("navy", 29))),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("unwatch", "declaration_clear", {"kind": "watch", "all": True},
         lambda reply, run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


MOMENTS = (
    Moment("watch", "sun", "Each `perform` picks a tool and a colour by name and drags: the sky, "
                           "then the sun."),
    Moment("sun", "hull", "Two more `perform` calls paint the sea and the boat's hull."),
    Moment("sail", "word", "The text tool, a click and `send_keys`: SCRY, typed into the picture."),
)

DEMO = declared("dpaint", HERE, STEPS, MOMENTS, "Deluxe Paint painting a sunset by itself")


if __name__ == "__main__":
    isolated_store("dpaint")
    sys.exit(main(DEMO))
