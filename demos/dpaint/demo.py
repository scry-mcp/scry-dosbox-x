"""The Deluxe Paint demo: Electronic Arts' Deluxe Paint II (1988), from the reader's own copy,
painting a sunset through the calls the README's prompt asks an MCP client to make, each answer
checked. `--help` says how to run it.

It paints the way a person would, with tools and colours picked by name off a screen map, and
stops once in the middle to do what no mouse macro can: two clicks on the palette and a value
scan between them find the byte where the program keeps its current colour, and a watch then
shows it at every stop. Each shape is checked by reading the pixels back out of video memory.

Nothing of the program is in this repository: `--cwd` names the directory of the reader's copy,
which the session runs from and mounts as C:, and the demo refuses any `DP.EXE` other than the
release it was written for, because the colour's address and the picture are that build's.
Deluxe Paint takes the mouse as movement events, so the DOSBox-X has to be one whose input
device carries relative motion; without it a drag paints nothing between its button events.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step, StepFailed, main
from scry_core.verdict import Invalid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos import host  # noqa: E402
from demos.host import display  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: Deluxe Paint II v1.0's `DP.EXE`, the 1988 release on one 720k disk.
DP_SHA256 = "ab40db116de1235e330e7df398b4b90425925972c2553775e997c9aa25ae3a4b"
#: The palette indices of the swatches the screen map names.
COLOURS = {"navy": 1, "brown": 6, "blue": 9, "yellow": 14, "white": 15, "peach": 52,
           "orange": 55}
#: Where this build keeps the current colour: four static bytes of its data segment, which every
#: pick of a colour rewrites. A scan also keeps copies in the stack's frames, above the stack
#: pointer, which move with where the stop lands.
COLOUR_STATICS = (0x017C, 0x01AE, 0x0470, 0x10B0)
#: Retraces from the start to the painting screen, with the program loaded and drawn.
BOOT_FRAMES = 400
#: The scene, in screen pixels: the sky and the sea as rectangles corner to corner, the sun as a
#: centre and a point on its rim, the boat's hull and its mast and sail as line segments.
SKY, SEA = ((2, 14), (294, 112)), ((2, 113), (294, 198))
SUN = ((210, 112), (238, 112))
HULL = ((60, 150), (112, 158))
SAIL = [((86, 149), (86, 118)), ((86, 118), (108, 146)), ((108, 146), (86, 146))]
TEXT_AT = (20, 180)
WORD = "SCRY"
WAIT_S = 60


def expect(holds: bool, why: str) -> None:
    if not holds:
        raise StepFailed(why)


def ds_segment(run: Run) -> int:
    return int(run.replies["loaded"]["regs"]["DS"], 16)


def copy_check(run: Run) -> str:
    """Why the reader's copy cannot be used: no `--cwd`, a relative one, no `DP.EXE` there, or
    another build's."""
    where = run.options.get("cwd")
    if not where:
        return ("pass --cwd with the directory of your own copy of Deluxe Paint II, the one "
                "holding DP.EXE; this repository carries none of the program")
    if not Path(where).expanduser().is_absolute():
        return f"the server takes absolute or ~-led paths only: --cwd {where}"
    exe = Path(where).expanduser() / "DP.EXE"
    if not exe.is_file():
        return f"no DP.EXE in {where}: --cwd names the directory the program runs from"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    if digest != DP_SHA256:
        return (f"{exe} is not the Deluxe Paint II v1.0 this demo was written for (sha256 "
                f"{digest}); the address of its colour and its picture are that release's")
    return ""


def precheck(run: Run) -> str:
    return copy_check(run) or host.precheck(run)


def boot(run: Run) -> dict[str, Any]:
    """A fresh log of this demo's own under the run's, so nothing an earlier run left is read,
    and the saved states there too: left out, they would go into the reader's copy."""
    (run.dir / "dpaint-e9.log").unlink(missing_ok=True)
    return {"conf": HERE / "dpaint.conf", "session_seconds": 900, "shared": True,
            "display": display(run), "program": "DP.EXE f",
            "logfile": run.dir / "dpaint-e9.log", "state_dir": run.dir / "dpaint-states"}


def started(reply: Reply, run: Run) -> str:
    return "DOSBox-X in a window, parked at the debugger before DOS boots"


def loaded(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "ELAPSED", f"verdict {reply['verdict']}")
    stub = next((ln for ln in reply["e9"]["lines"] if "scry device=" in ln), "")
    if "motion=1" not in stub:
        raise Invalid("this DOSBox-X's input device takes no relative motion (the stub said "
                      f"{stub.split(': ', 1)[-1] or 'nothing'}), and Deluxe Paint draws a drag "
                      "from movement events: pass --binary with a build that carries it")
    return f"{BOOT_FRAMES} retraces: Deluxe Paint is up, its data segment at {reply['regs']['DS']}"


def found(reply: Reply, run: Run) -> str:
    expect(reply["matched"] is True and reply["screen"] == "paint", f"matched {reply}")
    return f"the painting screen, {len(reply['controls'])} controls named"


def picked(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["arrived"] is True, f"the pointer read back at {reply['pointer']['screen']}")
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
            f"stack's frames above {sp:04X}, and {len(statics)} static ones from "
            f"{ds_segment(run):04X}:{COLOUR_STATICS[0]:04X}")


def colour_ref(run: Run) -> str:
    return f"{ds_segment(run):04X}:{COLOUR_STATICS[0]:04X}"


def click(target: str) -> dict[str, Any]:
    return {"op": "send_mouse", "target": target, "button": "left"}


def drag(start: tuple[int, int], end: tuple[int, int]) -> list[dict[str, Any]]:
    """A drag as Deluxe Paint takes one: press, move, release."""
    return [{"op": "send_mouse", "x": start[0], "y": start[1], "button": "left",
             "action": "down"},
            {"op": "send_mouse", "x": end[0], "y": end[1]},
            {"op": "send_mouse", "button": "left", "action": "up"}]


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


def row(y: int, x: int, length: int) -> dict[str, Any]:
    """`read_memory`'s arguments for `length` pixels of row `y` from `x`, in mode 13h."""
    return {"ref": f"A000:{y * 320 + x:04X}", "length": length}


def runs(reply: Reply) -> list[tuple[int, int]]:
    """A row of pixels as (colour, how many) runs."""
    out: list[tuple[int, int]] = []
    for b in bytes.fromhex(reply["hex"]):
        if out and out[-1][0] == b:
            out[-1] = (b, out[-1][1] + 1)
        else:
            out.append((b, 1))
    return out


def crossing(*spans: tuple[str, int]) -> Any:
    """A row that crosses the scene's colours in this order, each run exactly as long as the
    geometry draws it: a shape a pixel short or shifted changes a length."""
    def check(reply: Reply, run: Run) -> str:
        want = [(COLOURS[n], k) for n, k in spans]
        expect(runs(reply) == want, f"the row runs {runs(reply)}, not {want}")
        return "the row reads " + ", then ".join(f"{n} x {k}" for n, k in spans)
    return check


def pictured(reply: Reply, run: Run) -> str:
    expect(Path(reply["image"]["path"]).is_file(), f"no picture at {reply['image']['path']}")
    return f"mode {reply['vga_mode']}, {reply['width']}x{reply['height']} by palette index"


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("loaded", "run_for", {"frames": BOOT_FRAMES, "seconds": WAIT_S}, loaded),
    Step("map", "map_write", {"method": "load", "path": HERE / "dpaint.scry-map.json"},
         lambda reply, run: f"{reply['screens']} screen and {reply['controls']} controls "
                            "loaded"),
    Step("find", "map_find", {}, found),
    Step("blue", "send_mouse", {"target": "blue", "button": "left"},
         picked("blue picked off the palette")),
    Step("scan", "scan", scan_start, candidates),
    Step("is blue", "scan", {"method": "filter", "value": COLOURS["blue"], "limit": 8},
         narrowed),
    Step("orange", "send_mouse", {"target": "orange", "button": "left"},
         picked("orange picked off the palette")),
    Step("is orange", "scan", {"method": "filter", "value": COLOURS["orange"]}, colour_found),
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
        click("line")], "summaries": True},
        lambda reply, run: f"{WORD} typed at {TEXT_AT[0]},{TEXT_AT[1]}, then the line tool "
                           "again, which ends the text"),
    Step("sun row", "read_memory", lambda run: row(100, 160, 128),
         crossing(("peach", 25), ("yellow", 51), ("peach", 52))),
    Step("boat row", "read_memory", lambda run: row(154, 30, 112),
         crossing(("navy", 30), ("brown", 53), ("navy", 29))),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("unwatch", "declaration_clear", {"kind": "watch", "all": True},
         lambda reply, run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


DEMO = Demo(
    name="dpaint", root=ROOT, server=[sys.executable, str(ROOT / "dosbox_x_server.py")],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"cwd", "shared"}), reads=frozenset({"shared"}), precheck=precheck,
    host_args={"cwd": "the directory of the reader's own copy of the program"},
    volatile={"argv": "the emulator's command line, which carries the host's window placement",
              "elapsed_s": "wall-clock time since the session started",
              "waited_s": "wall-clock time a wait took", "ready_after_s": "wall-clock time "
              "the debugger took to answer",
              "window": "where the host put the emulator's window",
              "binary": "where the host installed DOSBox-X",
              "mark": "a byte position in the session's log, which also holds the debugger's "
              "answers to as many polls as the host's clock let a wait send",
              "input_port": "the free port the host picked for the input route",
              "binary_origin": "how the host's DOSBox-X was found",
              "version": "the host's DOSBox-X build",
              "output": "what the debugger printed for the command, which the server says to "
                        "read a stop from and never a value",
              "output_chars": "the length of that output", "clipped": "whether it was cut",
              "ran_path": "a file in the session's own temporary directory",
              "replies_path": "a file in the session's own temporary directory",
              })


def isolated_store() -> None:
    """The server keeps watches on disk, keyed by the conf, and re-arms them on the next start:
    a run that failed half-way would arm its watch for the next one. So each run gets a store of
    its own, gone when it ends."""
    store = tempfile.mkdtemp(prefix="dpaint-demo-state-")
    atexit.register(shutil.rmtree, store, ignore_errors=True)
    os.environ["XDG_STATE_HOME"] = store


if __name__ == "__main__":
    isolated_store()
    sys.exit(main(DEMO))
