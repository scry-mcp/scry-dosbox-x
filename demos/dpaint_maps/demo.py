"""The Deluxe Paint screen-map demo: Deluxe Paint II (1988) at VGA 640 x 480 in 16 colours,
its menus, dialog buttons, tools and colours picked by screen-map names and its shapes dragged at
pixels, each answer checked. `--help` says how to run it.

Its menus drop only while the button is held: a press on a title opens one, the release over an
item chooses. The map knows each open menu, the Palette dialog, and the painting screen per tool
in hand, which the toolbox shows inverted; every move to another screen ends with `map_find`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import png
from scry_core.demo import Reply, Run, Step, main
from scry_core.verdict import Invalid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import host  # noqa: E402
from demos.dpaint.program import click, declared, drag, opening  # noqa: E402
from demos.host import display, expect, isolated_store, pictured  # noqa: E402

HERE = Path(__file__).resolve().parent
#: The colours the checked rows cross, by palette index; the brown slot holds orange once mixed,
#: and the frame is the white canvas left around the scene.
COLOURS = {"orange": 6, "blue": 1, "black": 0, "yellow": 14, "frame": 15}
#: The orange the dialog mixes, as the DAC holds it in six bits a channel: brown's red raised to
#: the top, its green and blue left as they were.
ORANGE_DAC = "3f1500"
#: Retraces the red arrow is held: past the 21 steps from brown's red to the top, so the channel
#: clamps there whatever the program's repeat rate.
HOLD_FRAMES = 120
#: Retraces a menu choice or a dialog button takes to draw what it opens or closes.
DRAWN_FRAMES = 20
#: Where the pointer waits off every region the map signs, over the toolbox's colour indicator:
#: on the canvas a shape tool draws it as a crosshair across the whole screen.
PARK = (610, 300)
#: The scene in screen pixels; the boat is lifted in a box of sea and stamped by its centre.
SKY, SEA = ((4, 14), (587, 259)), ((4, 260), (587, 475))
SUN = ((296, 259), (356, 259))
GLINTS = [((256, 272), (336, 272)), ((270, 284), (322, 284)), ((284, 296), (308, 296))]
HULL = ((100, 380), (180, 395))
MAST = ((140, 379), (140, 320))
SAIL = [((142, 322), (176, 374)), ((176, 374), (142, 374))]
LIFT = ((96, 316), (184, 399))
STAMP = (440, 357)
PARKED = {"op": "send_mouse", "x": PARK[0], "y": PARK[1]}


def boot(run: Run) -> dict[str, Any]:
    """A fresh log, and the saved states kept out of the program's directory."""
    (run.dir / "dpaint-maps-e9.log").unlink(missing_ok=True)
    return {"conf": HERE / "dpaint_maps.conf", "session_seconds": 900, "shared": True,
            "display": display(run), "program": "DP.EXE k",
            "logfile": run.dir / "dpaint-maps-e9.log",
            "state_dir": run.dir / "dpaint-maps-states"}


def found(name: str) -> Any:
    """`map_find`'s reply names screen `name`."""
    def check(reply: Reply, run: Run) -> str:
        expect(reply["matched"] is True and reply["screen"] == name,
               f"map_find answered {reply.get('screen', 'no screen')}, not {name}")
        return f"the map says: {name}"
    return check


def completed(reply: Reply) -> None:
    expect(reply["failed_at"].get("available") is False,
           f"{reply['steps_completed']} steps, failed at {reply['failed_at']}")


def landed(*screens: str) -> Any:
    """Every `map_find` of a `perform` names the screen its move was meant to land on, in
    order. The rows `ran` shows are summaries, so the check reads the whole replies, which the
    call keeps in a file beside them."""
    def check(reply: Reply, run: Run) -> str:
        completed(reply)
        if not isinstance(reply["replies_path"], str):
            raise Invalid(f"the call kept no replies to check: {reply['replies_path']}")
        rows = [json.loads(line) for line in
                Path(reply["replies_path"]).read_text(encoding="utf-8").splitlines()]
        short = [r["reply"]["verdict"] for r in rows
                 if r["op"] == "run_for" and r["reply"]["verdict"] != "ELAPSED"]
        expect(not short, f"a wait ended {short}, before its retraces")
        named = [r["reply"].get("screen", "no screen") for r in rows if r["op"] == "map_find"]
        expect(named == list(screens), f"the map named {named}, not {list(screens)}")
        return "the map named " + ", then ".join(screens)
    return check


def held(reply: Reply, run: Run) -> str:
    completed(reply)
    return (f"the brown slot picked, and red's arrow held {HOLD_FRAMES} retraces until the "
            "channel tops out")


def mixed(reply: Reply, run: Run) -> str:
    expect(reply["rgb"] == [ORANGE_DAC], f"the brown slot holds {reply['rgb']}")
    return f"the brown slot now holds {reply['colors'][0]}, orange"


def orange_swatch(run: Run) -> dict[str, Any]:
    """The mixed slot off the DAC, its swatch kept beside the transcript."""
    dest = run.dir / "orange.png"
    dest.unlink(missing_ok=True)
    return {"first": COLOURS["orange"], "count": 1, "dest": dest}


def frames(n: int) -> dict[str, Any]:
    return {"op": "run_for", "frames": n}


FIND = {"op": "map_find"}
Move = tuple[list[dict[str, Any]], str]


def moves(name: str, *made: Move) -> Step:
    """Moves between screens in one call, each followed by the map's word on where it landed."""
    steps = [op for ops, _ in made for op in (*ops, FIND)]
    return Step(name, "perform", {"steps": steps, "summaries": True},
                landed(*(screen for _, screen in made)))


def shape(picks: list[str], strokes: list[tuple[tuple[int, int], tuple[int, int]]],
          screen: str) -> Move:
    """A shape: its tool and colour by name, its drags, then the pointer parked, so the map can
    say which tool was in hand."""
    return [*(click(p) for p in picks), *(op for a, b in strokes for op in drag(a, b)),
            PARKED], screen


def row(y: int) -> Callable[[Run], dict[str, Any]]:
    """`screen_view`'s arguments for row `y` across the canvas, as a file the check reads."""
    def args(run: Run) -> dict[str, Any]:
        dest = run.dir / f"row-{y}.png"
        dest.unlink(missing_ok=True)
        return {"crop": [0, y, 592, 1], "scale": 1, "dest": dest, "attach": False}
    return args


def crossing(*spans: tuple[str, int]) -> Any:
    """A row, read off its picture's attribute indices, that crosses the scene's colours in
    this order: a boat that did not flip swaps two runs."""
    return host.crossing(COLOURS, lambda reply: png.decode(
        Path(reply["image"]["path"]).read_bytes()).pixels, *spans)


ROWS = {
    "sun row": (230, crossing(("frame", 4), ("orange", 239), ("yellow", 107), ("orange", 238),
                              ("frame", 4))),
    "glint row": (272, crossing(("frame", 4), ("blue", 252), ("yellow", 81), ("blue", 251),
                                ("frame", 4))),
    "sail row": (350, crossing(("frame", 4), ("blue", 136), ("black", 1), ("blue", 19),
                               ("yellow", 1), ("blue", 258), ("yellow", 1), ("blue", 20),
                               ("black", 1), ("blue", 147), ("frame", 4))),
    "hull row": (388, crossing(("frame", 4), ("blue", 96), ("black", 81), ("blue", 219),
                               ("black", 81), ("blue", 107), ("frame", 4))),
}

STEPS = [
    *opening(boot),
    Step("map", "map_write", {"method": "load", "path": HERE / "dpaint.scry-map.json"},
         lambda reply, run: f"{reply['screens']} screens and {reply['controls']} controls "
                            "loaded"),
    Step("is paint", "map_find", {}, found("paint: freehand")),
    moves("open Color", ([click("color", "down")], "color menu")),
    moves("choose Palette", ([click("palette", "up"), frames(DRAWN_FRAMES)], "palette")),
    Step("mix", "perform", {"steps": [click("brown"), click("red_up", "down"),
                                      frames(HOLD_FRAMES),
                                      {"op": "send_mouse", "button": "left", "action": "up"}],
                            "summaries": True}, held),
    Step("orange", "palette", orange_swatch, mixed),
    moves("sky, sun and sea", ([click("ok"), frames(DRAWN_FRAMES)], "paint: freehand"),
          shape(["rect_filled", "brown"], [SKY], "paint: rectangle"),
          shape(["circle_filled", "yellow"], [SUN], "paint: circle"),
          shape(["rect_filled", "blue"], [SEA], "paint: rectangle")),
    moves("glints and hull", shape(["line", "yellow"], GLINTS, "paint: line"),
          shape(["rect_filled", "black"], [HULL], "paint: rectangle")),
    moves("mast and sail", shape(["line", "black"], [MAST], "paint: line"),
          shape(["yellow"], SAIL, "paint: line")),
    moves("flip the boat", ([click("brush_grab"), PARKED], "paint: grab"),
          ([*drag(*LIFT), frames(10), PARKED], "paint: custom brush"),
          ([click("brush", "down")], "brush menu"),
          ([click("flip_horizontal", "up"), frames(DRAWN_FRAMES), PARKED],
           "paint: custom brush"),
          ([{"op": "send_mouse", "x": STAMP[0], "y": STAMP[1], "button": "left"}, frames(10),
            PARKED], "paint: custom brush")),
    moves("Pict, and the brush put down", ([click("pict", "down")], "pict menu"),
          ([{"op": "send_mouse", "button": "left", "action": "up"}, frames(10), PARKED],
           "paint: custom brush"),
          ([click("brush_dot"), click("freehand"), PARKED], "paint: freehand")),
    *(Step(name, "screen_view", row(y), check) for name, (y, check) in ROWS.items()),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]

DEMO = declared("dpaint_maps", HERE, STEPS)


if __name__ == "__main__":
    isolated_store("dpaint_maps")
    sys.exit(main(DEMO))
