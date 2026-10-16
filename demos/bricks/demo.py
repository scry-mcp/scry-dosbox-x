"""The bricks demo: `BRICKS.COM`, a game this repository builds, driven by the calls the README's
prompt asks an MCP client to make, each answer checked. `--help` says how to run it.

It walks a debugger through a game: the first stop inside the program, its symbols placed from
the segment DOS loaded it at, a breakpoint on the routine every falling brick goes through, the
score read by name, the paddle moved by the keyboard and by the mouse, and a state saved and
loaded. The session is windowed so the game can be watched, and nothing in it needs the window:
`stop` and the saved states go down the debugger channel, the keys and the mouse in inside the
guest. The saved states need a DOSBox-X that carries SAVESTATE and LOADSTATE (the fork).

Where the window goes is the host's to say, never this demo's: it asks the placement helper named
by `WINDOW_APP`, `<helper> dosbox` for a run nobody watches
and `<helper> dosbox --shared` with `--shared`. A run nobody watches that the helper cannot place
away from the owner's work (no helper, or a helper that places nothing, as on one display) is
refused rather than opened on top of it; `--shared` says somebody is watching, so it may open
where they look. The placement is the host's, so the transcript shows `<host>` for it.
"""

from __future__ import annotations

import atexit
import functools
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step, StepFailed, main

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: Where a watched window goes when there is no helper, or it places nothing (one display):
#: centred, where the person who asked to watch is looking.
CENTRED = ["-set", "sdl windowposition=,"]
HELPER_TIMEOUT_S = 10
#: These mirror bricks.asm, and the checks go red if the game moves them: the fixed serve's
#: first brick and its `(6 - row) * 10` points, then PADDLE_HOME and PADDLE_STEP.
FIRST_ROW, FIRST_COL, FIRST_POINTS = 5, 7, 10
SECOND_BRICK = (5, 6)
#: Where three retraces after the second brick leave the ball: x, y, dx, dy.
BALL_AFTER = (188, 82, -2, 2)
PADDLE_HOME, PADDLE_STEP, RIGHTS, PADDLE_W = 140, 8, 3, 40
#: Where the demo puts the pointer, in screen pixels: the paddle centres itself under it.
MOUSE_AT = (240, 100)
WAIT_S = 60


def expect(holds: bool, why: str) -> None:
    if not holds:
        raise StepFailed(why)


def low_byte(reply: Reply, register: str) -> int:
    return int(reply["registers"][register], 16) & 0xFF


def word(reply: Reply) -> int:
    """A little-endian 16-bit value out of `read_memory`'s hex."""
    raw = bytes.fromhex(reply["hex"])
    return raw[0] | raw[1] << 8


@functools.cache
def placement(shared: bool) -> tuple[list[str], str]:
    """The window flags the host's helper gives, one argument a line, or why there are none."""
    helper = os.environ.get("WINDOW_APP", "").strip()
    if not helper:
        return (CENTRED, "") if shared else ([], (
            "WINDOW_APP names no placement helper, so the window would open wherever the "
            "emulator likes, likely on top of your work; set it, or pass --shared if you are "
            "watching"))
    try:
        said = subprocess.run([helper, "dosbox", *(["--shared"] if shared else [])],
                              capture_output=True, text=True, timeout=HELPER_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"the placement helper {helper} could not be run: {e}"
    if said.returncode != 0:
        return [], (f"the placement helper {helper} answered exit code {said.returncode}: "
                    f"{said.stderr.strip() or said.stdout.strip()}")
    flags = [ln for ln in said.stdout.splitlines() if ln.strip()]
    if not flags and shared:
        return CENTRED, ""
    if not flags:
        return [], ("the placement helper has nowhere to put a window away from your work (one "
                    "display); pass --shared if you are watching")
    return flags, ""


def precheck(run: Run) -> str:
    binary = run.options.get("binary")
    if binary and not Path(binary).is_absolute():
        return f"the server takes absolute paths only: --binary {binary}"
    return placement(bool(run.options.get("shared")))[1]


def boot(run: Run) -> dict[str, Any]:
    """A fresh log and state directory of this demo's own under the run's, so nothing an earlier
    run left is counted again (`state_save` never overwrites)."""
    (run.dir / "bricks-e9.log").unlink(missing_ok=True)
    states = run.dir / "bricks-states"
    shutil.rmtree(states, ignore_errors=True)
    # `mode` "shared" is the server's windowed mode; the demo's own --shared only decides
    # where the window goes.
    return {"conf": HERE / "bricks.conf", "cwd": HERE, "seconds": 900, "mode": "shared",
            "window_flags": placement(bool(run.options.get("shared")))[0],
            "break_on_int3": True, "logfile": run.dir / "bricks-e9.log",
            "state_dir": states}


def started(reply: Reply, run: Run) -> str:
    return f"{reply['mode']} DOSBox-X, parked at the debugger before DOS boots"


def at_ready(reply: Reply, run: Run) -> str:
    expect(reply["instruction"]["text"] == "int 3", f"stopped at {reply['instruction']}")
    cs = reply["stopped_at"]["cs"]
    return f"the program's own int 3 at {cs}:{reply['stopped_at']['eip'][-4:]}: loaded at {cs}"


def symbols(run: Run) -> dict[str, Any]:
    """The table is offsets from the program's segment, so its base is that segment * 16."""
    cs = int(run.replies["ready"]["stopped_at"]["cs"], 16)
    return {"source": HERE / "bricks.sym", "base": f"{cs * 16:x}"}


def loaded(reply: Reply, run: Run) -> str:
    expect(reply["kept"] == reply["parsed"] > 0, f"{reply['kept']} of {reply['parsed']} kept")
    return f"{reply['kept']} symbols placed at base {reply['base']:#x}"


def listing(reply: Reply, run: Run) -> str:
    first = reply["lines"][0].split(maxsplit=2)[-1]
    expect(first == "mov bh, bl", f"brick_hit opens with {first!r}")
    return f"brick_hit opens with: {first}"


def at_brick(row: int, col: int, score: int, which: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["attribution"].get("ref") == "brick_hit",
               f"stopped by {reply['attribution']}")
        got = (low_byte(reply, "EAX"), low_byte(reply, "EBX"), reply["watches"][0]["value"])
        expect(got == (row, col, score), f"row, column and score {got}")
        return f"brick_hit for the {which} brick, row {row} column {col}, score {score}"
    return check


def score_is(points: int) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(word(reply) == points, f"score {word(reply)}, not {points}")
        return f"score {points}, read by name"
    return check


def pictured(reply: Reply, run: Run) -> str:
    expect(Path(reply["image"]["path"]).is_file(), f"no picture at {reply['image']['path']}")
    return f"mode {reply['mode']}, {reply['width']}x{reply['height']} by palette index"


def frames(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "ELAPSED", f"verdict {reply['verdict']}")
    return f"three retraces, the emulated clock from {reply['emulated_before_s']:.4f} s to " \
           f"{reply['emulated_after_s']:.4f} s"


def ball(reply: Reply, run: Run) -> str:
    raw = bytes.fromhex(reply["hex"])
    got = tuple(int.from_bytes(raw[i:i + 2], "little", signed=True) for i in (0, 2, 4, 6))
    expect(got == BALL_AFTER, f"the ball at {got}, not {BALL_AFTER}")
    x, y, dx, dy = got
    return f"the ball at ({x}, {y}) moving ({dx:+}, {dy:+})"


def keys_taken(reply: Reply, run: Run) -> str:
    lines = [ln.split(": ", 1)[-1] for ln in reply["looked"]["e9"]["lines"]]
    expect(lines.count("KEY R") == RIGHTS, f"the game logged {lines}")
    return f"the game logged {', '.join(lines)}"


def stopped(reply: Reply, run: Run) -> str:
    expect(reply["interrupted"] is True, f"interrupted {reply['interrupted']}")
    return "stopped through the debugger channel"


def paddle(reply: Reply, run: Run) -> str:
    want = PADDLE_HOME + PADDLE_STEP * RIGHTS
    expect(word(reply) == want, f"paddle at {word(reply)}, not {want}")
    return f"the paddle at x {want}: the middle, then {RIGHTS} steps right"


def seen(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["effect"]["seen"] is True, f"effect {reply['effect']}")
        return what
    return check


def moved(reply: Reply, run: Run) -> str:
    want = MOUSE_AT[0] - PADDLE_W // 2
    # Right of where the keys left it by more than a step, so the left arrow that follows can
    # never be clamped into a no-op that leaves the paddle where the save put it.
    expect(want > word(run.replies["paddle"]) + PADDLE_STEP, "MOUSE_AT is too far left")
    expect(word(reply) == want, f"the paddle is at {word(reply)}, not centred under the "
                                f"pointer at {want}")
    return f"the paddle at x {want}, centred under the pointer at pixel {MOUSE_AT[0]}"


def pointed(reply: Reply, run: Run) -> str:
    screen = reply["pointer"]["screen"]
    expect(reply["arrived"] is True and (screen["x"], screen["y"]) == MOUSE_AT,
           f"the pointer read back at {screen}, not {MOUSE_AT}")
    expect(reply["effect"]["seen"] is True, f"effect {reply['effect']}")
    return (f"the pointer read back at pixel {MOUSE_AT[0]},{MOUSE_AT[1]} and the game logged "
            f"MOUSE")


def restored(reply: Reply, run: Run) -> str:
    saved = word(run.replies["before save"])
    expect(word(reply) == saved, f"paddle at {word(reply)} after the load, saved at {saved}")
    return "the paddle is back where the state was saved: the load undid the left arrow"


#: Values a `stop` shows, which land wherever the game is when the break arrives.
BREAK_STOP = {key: "the stop lands wherever the game is when the break arrives"
             for key in ("summary", "registers", "instruction", "stopped_at", "attribution",
                         "watches", "e9")}
#: Counts an input step reports that depend on when the host delivered the input, not on what
#: the game did with it.
INPUT_TIMING = {key: "it depends on when the host delivered the input"
                for key in ("lines_before", "seen_before_waiting", "lines_total", "written",
                            "since_mark")}
#: The data view around the paddle, which holds the frame counter a `stop` catches anywhere.
MOUSE_PLACED = {"rows": "the data view around the paddle holds the frame counter, which a "
                        "`stop` catches at any frame"}

STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("ready", "resume", {"seconds": WAIT_S}, at_ready),
    Step("symbols", "symbols_load", symbols, loaded),
    Step("look", "disassemble", {"ref": "brick_hit", "length": 32}, listing),
    Step("break", "breakpoint_at", {"ref": "brick_hit"},
         lambda reply, run: f"breakpoint {reply['entry']}"),
    Step("watch", "watch_add", {"ref": "score", "mode": "show", "fmt": "u16"},
         lambda reply, run: "score shown at every stop"),
    Step("first brick", "resume", {"seconds": WAIT_S},
         at_brick(FIRST_ROW, FIRST_COL, 0, "first")),
    Step("second brick", "resume", {"seconds": WAIT_S},
         at_brick(*SECOND_BRICK, FIRST_POINTS, "second")),
    Step("score", "read_memory", {"ref": "score", "length": 2}, score_is(FIRST_POINTS)),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("unbreak", "breakpoint_clear", {}, lambda reply, run: "breakpoint cleared"),
    Step("frames", "run_for", {"frames": 3, "seconds": WAIT_S}, frames,
         volatile={key: "a retrace stop lands at any instruction of the game's retrace poll"
                   for key in ("summary", "registers", "instruction", "stopped_at",
                               "attribution")}),
    Step("ball", "read_memory", {"ref": "ball_x", "length": 8}, ball),
    Step("play", "resume", {}, lambda reply, run: "the game runs"),
    Step("keys", "drive", {"act": [{"op": "send_keys", "keys": ["right"], "expect": "KEY R",
                                    "seconds": 10}] * RIGHTS,
                           "pattern": "KEY|PLAYER"}, keys_taken, volatile=INPUT_TIMING),
    Step("pause", "stop", {}, stopped, volatile=BREAK_STOP),
    Step("paddle", "read_memory", {"ref": "paddle_x", "length": 2}, paddle,
         volatile={"rows": "the data view around the paddle holds the frame counter, which "
                           "a `stop` catches at any frame"}),
    Step("again", "resume", {}, lambda reply, run: "the game runs"),
    Step("mouse on", "send_keys", {"keys": ["m"], "expect": "MOUSE ON$", "seconds": 10},
         seen("M handed the paddle to the mouse: the game logged MOUSE ON"),
         volatile=INPUT_TIMING),
    Step("mouse", "send_mouse", {"x": MOUSE_AT[0], "y": MOUSE_AT[1], "expect": "MOUSE$",
                                 "seconds": 10},
         pointed, volatile=INPUT_TIMING),
    Step("mouse off", "send_keys", {"keys": ["m"], "expect": "MOUSE OFF$", "seconds": 10},
         seen("M took the paddle back, so the pointer moves nothing from here on"),
         volatile=INPUT_TIMING),
    Step("mark", "stop", {}, stopped, volatile=BREAK_STOP),
    Step("before save", "read_memory", {"ref": "paddle_x", "length": 2}, moved,
         volatile=MOUSE_PLACED),
    Step("on again", "resume", {}, lambda reply, run: "the game runs"),
    Step("save", "state_save", {"name": "bricks"},
         lambda reply, run: f"state saved as {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries the state's size and time", "bytes": "the state is "
                   "compressed, so its size follows the frame it was taken at"}),
    Step("left", "send_keys", {"keys": ["left"], "expect": "KEY L$", "seconds": 10},
         seen("the left arrow moved the paddle after the save"), volatile=INPUT_TIMING),
    Step("load", "state_load", {"name": "bricks"},
         lambda reply, run: f"state loaded from {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries how long the load took"}),
    Step("halt", "stop", {}, stopped, volatile=BREAK_STOP),
    Step("restored", "read_memory", {"ref": "paddle_x", "length": 2}, restored,
         volatile=MOUSE_PLACED),
    Step("play on", "resume", {}, lambda reply, run: "the game runs"),
    Step("serve", "send_keys", {"keys": ["space"], "expect": "SERVE$", "seconds": 10},
         seen("SPACE served the ball that was waiting on the paddle"), volatile=INPUT_TIMING),
    Step("unwatch", "watch_clear", {}, lambda reply, run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['how']}"),
]


DEMO = Demo(
    name="bricks", root=ROOT, server=[sys.executable, str(ROOT / "dosbox_x_server.py")],
    readme=HERE / "README.md", steps=STEPS, capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"shared"}), reads=frozenset({"shared"}), precheck=precheck,
    host_args={"window_flags": "where this host puts the window"},
    volatile={"argv": "the emulator's command line, which carries the host's window placement",
              "seconds_elapsed": "wall-clock time since the session started",
              "waited_s": "wall-clock time a wait took", "ready_after_s": "wall-clock time "
              "the debugger took to answer",
              "time_stamp": "the wall-clock time a state was saved at",
              "window": "where the host put the emulator's window",
              "binary": "where the host installed DOSBox-X",
              "input_port": "the free port the host picked for the input route",
              "binary_origin": "how the host's DOSBox-X was found",
              "version": "the host's DOSBox-X build",
              "screen_delta": "the debugger's repaint, a positional tail the server says to "
                              "read a stop from and never a value",
              "screen_chars": "the length of that repaint", "clipped": "whether it was cut",
              })


def isolated_store() -> None:
    """The server keeps breakpoints and watches on disk, keyed by the conf, and re-arms them on
    the next start: a run that failed half-way would arm its breakpoint for the next one. So
    each run gets a store of its own, gone when it ends."""
    store = tempfile.mkdtemp(prefix="bricks-demo-state-")
    atexit.register(shutil.rmtree, store, ignore_errors=True)
    os.environ["XDG_STATE_HOME"] = store


if __name__ == "__main__":
    isolated_store()
    sys.exit(main(DEMO))
