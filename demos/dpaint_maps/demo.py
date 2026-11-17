"""The Deluxe Paint screen-map demo: Deluxe Paint II (1988) at VGA 640 x 480 in 16 colours,
its menus, dialog buttons, tools and colours picked by screen-map names, its shapes dragged at
pixels and SCRY typed with the text tool, each answer checked. `--help` says how to run it.

Its menus drop only while the button is held: a press on a title opens one, the release over an
item chooses. The map knows each open menu, the Palette dialog, and the painting screen per tool
in hand, which the toolbox shows inverted; every move to another screen ends with `screen_map_find`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import png
from scry_core.demo import Moment, Reply, Run, Step, main, window_args
from scry_core.verdict import Invalid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import host  # noqa: E402
from demos.dpaint.program import (  # noqa: E402
    WAIT_S,
    click,
    counted,
    declared,
    drag,
    ds_segment,
    opening,
    recorded,
)
from demos.host import expect, isolated_store, pictured  # noqa: E402

HERE = Path(__file__).resolve().parent
#: The colours the checked rows cross, by palette index; the brown slot holds orange once mixed,
#: and the frame is the white canvas left around the scene.
COLOURS = {"orange": 6, "blue": 1, "black": 0, "yellow": 14, "frame": 15}
#: The orange the dialog mixes, as the DAC holds it in six bits a channel: brown's red raised to
#: the top, its green and blue left as they were.
ORANGE_DAC = "3f1500"
#: Where this release keeps brown's red while the palette dialog mixes it, in its data segment,
#: and the top of a six-bit channel.
BROWN_RED, RED_TOP = 0x31BC, 0x3F
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
#: Where the text tool's cursor is put down, in the sky; the word is typed there.
TEXT_AT = (40, 60)
WORD = "SCRY"
PARKED = {"op": "send_mouse", "x": PARK[0], "y": PARK[1]}


def boot(run: Run) -> dict[str, Any]:
    """A fresh log, and the saved states kept out of the program's directory."""
    (run.dir / "dpaint-maps-e9.log").unlink(missing_ok=True)
    return {**window_args(run), **recorded(run), "conf": HERE / "dpaint-maps.conf",
            "session_seconds": 900, "program": "DP.EXE k",
            "logfile": run.dir / "dpaint-maps-e9.log",
            "state_dir": run.dir / "dpaint-maps-states"}


def found(name: str) -> Any:
    """`screen_map_find`'s reply names screen `name`."""
    def check(reply: Reply, run: Run) -> str:
        expect(reply["matched"] is True and reply["screen"] == name,
               f"screen_map_find answered {reply.get('screen', 'no screen')}, not {name}")
        return f"the map says: {name}"
    return check


def completed(reply: Reply) -> None:
    failed = reply["failed_at"]
    expect(isinstance(failed, dict) and failed.get("available") is False,
           f"{reply['steps_completed']} steps, failed at {failed}")


def landed(*screens: str) -> Any:
    """Every `screen_map_find` of a `perform` names the screen its move was meant to land on, in
    order. The rows `ran` shows are summaries, so the check reads the whole replies, which the
    call keeps in a file beside them."""
    def check(reply: Reply, run: Run) -> str:
        completed(reply)
        if not isinstance(reply["replies_path"], str):
            raise Invalid(f"the call kept no replies to check: {reply['replies_path']}")
        rows = [json.loads(line) for line in
                Path(reply["replies_path"]).read_text(encoding="utf-8").splitlines()]
        short = [r["reply"]["verdict"] for r in rows
                 if r["op"] == "screen_wait" and r["reply"]["verdict"] != "TARGET"]
        expect(not short, f"a wait ended {short}, before its screen")
        named = [r["reply"].get("screen", "no screen")
                 for r in rows if r["op"] == "screen_map_find"]
        expect(named == list(screens), f"the map named {named}, not {list(screens)}")
        return "the map named " + ", then ".join(screens)
    return check


def mix(run: Run) -> dict[str, Any]:
    """Pick brown, press red's arrow, wait for brown's red to reach the top, release."""
    red = f"{ds_segment(run):04X}:{BROWN_RED:04X}"
    return {"steps": [click("brown"),
                      {"op": "watch_add", "ref": red, "mode": "change", "fmt": "u8"},
                      click("red_up", "down"),
                      {"op": "screen_wait", "screen": "palette", "on_watch": red,
                       "condition": f"b@{red} == {RED_TOP:#x}", "seconds": WAIT_S},
                      {"op": "send_mouse", "button": "left", "action": "up"},
                      {"op": "declaration_clear", "kind": "watch", "all": True}],
            "summaries": True}


def held(reply: Reply, run: Run) -> str:
    completed(reply)
    return "the brown slot picked, and red's arrow held until brown's red reached the top"


def mixed(reply: Reply, run: Run) -> str:
    expect(reply["rgb"] == [ORANGE_DAC], f"the brown slot holds {reply['rgb']}")
    return f"the brown slot now holds {reply['colors'][0]}, orange"


def orange_swatch(run: Run) -> dict[str, Any]:
    """The mixed slot off the DAC, its swatch kept beside the transcript."""
    dest = run.dir / "orange.png"
    dest.unlink(missing_ok=True)
    return {"first": COLOURS["orange"], "count": 1, "dest": dest}


FIND = {"op": "screen_map_find"}
Move = tuple[list[dict[str, Any]], str]


def moves(name: str, *made: Move, volatile: dict[str, str] | None = None,
          **example: Any) -> Step:
    """Moves between screens in one call, each followed by the map's word on where it landed."""
    steps = [op for ops, screen in made
             for op in (*ops, {"op": "screen_wait", "screen": screen, "seconds": WAIT_S}, FIND)]
    return Step(name, "perform", {"steps": steps, "summaries": True},
                landed(*(screen for _, screen in made)), volatile=volatile or {}, **example)


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
    "word row": (57, crossing(("frame", 4), ("orange", 37), ("black", 4), ("orange", 3),
                              ("black", 2), ("orange", 6), ("black", 5), ("orange", 4),
                              ("black", 5), ("orange", 518), ("frame", 4))),
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
    *opening(boot, HERE / "dpaint-screen-map.json", "paint: freehand"),
    Step("is paint", "screen_map_find", {}, found("paint: freehand")),
    moves("open Color", ([click("color", "down")], "color menu")),
    moves("choose Palette", ([click("palette", "up"), {"op": "run_to", "screen": "palette"}],
                             "palette"),
          volatile={"summary": "a row's summary names the instruction its retrace stop lands "
                               "on, which drifts with the host's cycles"}),
    counted("dialog open"),
    # The arrow is held until the program's own copy of brown's red reaches the top: a change
    # watch on that byte, and the wait judged only at its firings, filtered by the value.
    Step("mix", "perform", mix, held,
         title="Hold a button until a value is reached",
         ask=("Pick brown, hold the red arrow of the Palette dialog until brown's red reaches "
              "the top, then release."),
         shown=("summary", "steps_completed"),
         reads=("`send_mouse` presses and releases as two steps. Between them `screen_wait` looks "
                "only when a watch on the program's copy of brown's red fires, so the arrow is "
                "held exactly long enough.")),
    counted("mixed"),
    Step("orange", "palette", orange_swatch, mixed,
         title="Read a colour back from the video card",
         ask="Read the palette entry the dialog just mixed, and save a swatch of it.",
         shown=("summary", "rgb", "colors"),
         reads=("`palette` reads the video card's own colour table: `rgb` as its six-bit values, "
                "`colors` as the colour the screen shows. Only the program's dialog changed "
                "it.")),
    moves("sky, sun and sea", ([click("ok")], "paint: freehand"),
          shape(["rect_filled", "brown"], [SKY], "paint: rectangle"),
          shape(["circle_filled", "yellow"], [SUN], "paint: circle"),
          shape(["rect_filled", "blue"], [SEA], "paint: rectangle")),
    moves("glints and hull", shape(["line", "yellow"], GLINTS, "paint: line"),
          shape(["rect_filled", "black"], [HULL], "paint: rectangle")),
    moves("mast and sail", shape(["line", "black"], [MAST], "paint: line"),
          shape(["yellow"], SAIL, "paint: line")),
    moves("SCRY", ([click("black"), click("text"), PARKED], "paint: text"),
          ([{"op": "send_mouse", "x": TEXT_AT[0], "y": TEXT_AT[1], "button": "left"},
            {"op": "send_keys", "keys": list(WORD), "modifiers": ["shift"]},
            click("freehand"), PARKED], "paint: freehand")),
    counted("boat drawn"),
    moves("flip the boat", ([click("brush_grab"), PARKED], "paint: grab"),
          ([*drag(*LIFT), PARKED], "paint: custom brush"),
          ([click("brush", "down")], "brush menu"),
          ([click("flip_horizontal", "up"), PARKED],
           "paint: custom brush"),
          ([{"op": "send_mouse", "x": STAMP[0], "y": STAMP[1], "button": "left"},
            PARKED], "paint: custom brush"),
         title="Chain menus, drags and clicks in one call",
         ask="Lift the boat as a brush, flip it from the Brush menu and stamp the mirror image.",
         shown=("summary", "steps_completed"),
         reads=("After each move the screen map is asked which screen is showing, because the "
                "same pixels mean another tool in hand. The whole reply lists the screens it "
                "named.")),
    counted("boat flipped"),
    moves("Pict, and the brush put down", ([click("pict", "down")], "pict menu"),
          ([{"op": "send_mouse", "button": "left", "action": "up"}, PARKED],
           "paint: custom brush"),
          ([click("brush_dot"), click("freehand"), PARKED], "paint: freehand")),
    # The last step that moves the machine counts its frame: the loop's moments are found in the
    # session's video counting back from it.
    counted("last frame"),
    *(Step(name, "screen_view", row(y), check) for name, (y, check) in ROWS.items()),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]

MOMENTS = (
    Moment("dialog open", "mixed",
           "`send_mouse` holds the red arrow of the Palette dialog until the brown slot is "
           "orange."),
    Moment("boat drawn", "boat flipped",
           "One `perform` lifts the boat as a brush, flips it from the Brush menu and stamps it.",
           skip=16, frames=170),
)

DEMO = declared("dpaint_maps", HERE, STEPS, MOMENTS,
                "Deluxe Paint mixing a colour in its Palette dialog, then flipping a boat")


if __name__ == "__main__":
    isolated_store("dpaint_maps")
    sys.exit(main(DEMO))
