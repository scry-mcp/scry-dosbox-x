"""The bricks demo: `BRICKS.COM`, a game this repository builds, driven by the calls the README's
prompt asks an MCP client to make, each answer checked. `--help` says how to run it.

It walks a debugger through a game: the first stop inside the program, its symbols placed from
the segment DOS loaded it at, a breakpoint on the routine every falling brick goes through, the
score read by name, the paddle moved by the keyboard and by the mouse, and a state saved and
loaded. The session is windowed so the game can be watched, and nothing in it needs the window:
`stop` and the saved states go down the debugger channel, the keys and the mouse in inside the
guest. The saved states need a DOSBox-X that carries SAVESTATE and LOADSTATE.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step, main

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    VOLATILE,
    expect,
    isolated_store,
    loaded,
    pictured,
    precheck,
    seen,
    started,
    symbols_at,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
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


def low_byte(reply: Reply, register: str) -> int:
    return int(reply["regs"][register], 16) & 0xFF


def word(reply: Reply) -> int:
    """A little-endian 16-bit value out of `read_memory`'s hex."""
    raw = bytes.fromhex(reply["hex"])
    return raw[0] | raw[1] << 8


def boot(run: Run) -> dict[str, Any]:
    """A fresh log and state directory of this demo's own under the run's, so nothing an earlier
    run left is counted again (`state_write(method="save")` never overwrites)."""
    (run.dir / "bricks-e9.log").unlink(missing_ok=True)
    states = run.dir / "bricks-states"
    shutil.rmtree(states, ignore_errors=True)
    return {"conf": HERE / "bricks.conf", "cwd": HERE, "session_seconds": 900, "shared": True,
            "break_on_int3": True, "logfile": run.dir / "bricks-e9.log",
            "state_dir": states}


def at_ready(reply: Reply, run: Run) -> str:
    expect(reply["instruction"]["text"] == "int 3", f"stopped at {reply['instruction']}")
    cs, eip = str(reply["pc"]).split(":")
    return f"the program's own int 3 at {cs}:{eip[-4:]}: loaded at {cs}"


def listing(reply: Reply, run: Run) -> str:
    first = reply["lines"][0].split(maxsplit=2)[-1]
    expect(first == "mov bh, bl", f"brick_hit opens with {first!r}")
    return f"brick_hit opens with: {first}"


def at_brick(row: int, col: int, score: int, which: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["cause"].startswith("breakpoint brick_hit "), f"stopped by {reply['cause']}")
        got = (low_byte(reply, "EAX"), low_byte(reply, "EBX"), reply["watches"][0]["value"])
        expect(got == (row, col, score), f"row, column and score {got}")
        return f"brick_hit for the {which} brick, row {row} column {col}, score {score}"
    return check


def score_is(points: int) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(word(reply) == points, f"score {word(reply)}, not {points}")
        return f"score {points}, read by name"
    return check


def frames(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "ELAPSED", f"verdict {reply['verdict']}")
    expect(reply["emulated_after_s"] > reply["emulated_before_s"], "the emulated clock stood still")
    return "three retraces, the emulated clock moved on"


def ball(reply: Reply, run: Run) -> str:
    raw = bytes.fromhex(reply["hex"])
    got = tuple(int.from_bytes(raw[i:i + 2], "little", signed=True) for i in (0, 2, 4, 6))
    expect(got == BALL_AFTER, f"the ball at {got}, not {BALL_AFTER}")
    x, y, dx, dy = got
    return f"the ball at ({x}, {y}) moving ({dx:+}, {dy:+})"


def keys_taken(reply: Reply, run: Run) -> str:
    lines = [ln.split(": ", 1)[-1] for ln in reply["looked"]["guest"]["lines"]]
    expect(lines.count("KEY R") == RIGHTS, f"the game logged {lines}")
    return f"the game logged {', '.join(lines)}"


def stopped(reply: Reply, run: Run) -> str:
    expect(reply["interrupted"] is True, f"interrupted {reply['interrupted']}")
    return "stopped through the debugger channel"


def paddle(reply: Reply, run: Run) -> str:
    want = PADDLE_HOME + PADDLE_STEP * RIGHTS
    expect(word(reply) == want, f"paddle at {word(reply)}, not {want}")
    return f"the paddle at x {want}: the middle, then {RIGHTS} steps right"


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
    expect(reply["driver_arrived"] is True and (screen["x"], screen["y"]) == MOUSE_AT,
           f"the pointer read back at {screen}, not {MOUSE_AT}")
    expect(reply["verify"]["seen"] is True, f"verify {reply['verify']}")
    return (f"the pointer read back at pixel {MOUSE_AT[0]},{MOUSE_AT[1]} and the game logged "
            f"MOUSE")


def restored(reply: Reply, run: Run) -> str:
    saved = word(run.replies["before save"])
    expect(word(reply) == saved, f"paddle at {word(reply)} after the load, saved at {saved}")
    return "the paddle is back where the state was saved: the load undid the left arrow"


#: Values a `stop` shows, which land wherever the game is when the break arrives.
BREAK_STOP = {key: "the stop lands wherever the game is when the break arrives"
             for key in ("summary", "regs", "instruction", "pc", "frame", "cause",
                         "watches", "e9")}

STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("ready", "resume", {"seconds": WAIT_S}, at_ready,
         shown=("summary", "cause", "instruction")),
    Step("symbols", "symbols_load", symbols_at(HERE / "bricks.sym"), loaded,
         shown=("summary", "base")),
    Step("look", "disassemble", {"ref": "brick_hit", "length": 32}, listing),
    Step("break", "breakpoint_at", {"ref": "brick_hit"},
         lambda reply, run: f"breakpoint {reply['entry']}",
         shown=("summary", "entry"),
         highlight=("A breakpoint asked for by name. `brick_hit` is a label in the symbol table "
                    "the build generated, so the server turns it into the address the program "
                    "actually loaded at and arms the debugger there; the reply says it was "
                    "resolved `by: symbol`.")),
    Step("watch", "watch_add", {"ref": "score", "mode": "show", "fmt": "u16"},
         lambda reply, run: "score shown at every stop"),
    Step("first brick", "resume", {"seconds": WAIT_S},
         at_brick(FIRST_ROW, FIRST_COL, 0, "first"),
         shown=("summary", "cause", "watches"),
         highlight=("`resume` hands the machine back and returns when the debugger stops it again. "
                    "The stop carries what a person would otherwise type commands for: the "
                    "registers, the instruction under the program counter with its symbol, the "
                    "cause, and the value of the watch armed a step earlier, the score, read by "
                    "name. The line the game itself wrote to the debugger's port E9 comes in the "
                    "same reply: the game says which brick fell, the registers say where.")),
    Step("second brick", "resume", {"seconds": WAIT_S},
         at_brick(*SECOND_BRICK, FIRST_POINTS, "second")),
    Step("score", "read_memory", {"ref": "score", "length": 2}, score_is(FIRST_POINTS),
         shown=("summary", "hex")),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("unbreak", "declaration_clear", {"kind": "breakpoint", "all": True}, lambda reply,
         run: "breakpoint cleared"),
    Step("frames", "run_for", {"frames": 3, "seconds": WAIT_S}, frames,
         volatile={key: "a retrace stop lands at any instruction of the game's retrace poll"
                   for key in ("summary", "regs", "instruction", "pc", "cause",
                               "emulated_before_s", "emulated_after_s")}),
    Step("ball", "read_memory", {"ref": "ball_x", "length": 8}, ball),
    Step("play", "resume", {}, lambda reply, run: "the game runs"),
    Step("keys", "drive", {"act": [{"op": "send_keys", "keys": ["right"], "expect": "KEY R",
                                    "seconds": 10}] * RIGHTS,
                           "pattern": "KEY|PLAYER"}, keys_taken, volatile=INPUT_TIMING,
         shown=("looked",)),
    Step("pause", "stop", {}, stopped, volatile=BREAK_STOP),
    Step("paddle", "read_memory", {"ref": "paddle_x", "length": 2}, paddle),
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
    Step("before save", "read_memory", {"ref": "paddle_x", "length": 2}, moved),
    Step("on again", "resume", {}, lambda reply, run: "the game runs"),
    Step("save", "state_write", {"method": "save", "name": "bricks"},
         lambda reply, run: f"state saved as {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries the state's size and time", "bytes": "the state is "
                   "compressed, so its size follows the frame it was taken at"},
         shown=("name",)),
    Step("left", "send_keys", {"keys": ["left"], "expect": "KEY L$", "seconds": 10},
         seen("the left arrow moved the paddle after the save"), volatile=INPUT_TIMING),
    Step("load", "state_write", {"method": "load", "name": "bricks"},
         lambda reply, run: f"state loaded from {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries how long the load took",
                   "mark": "the game ran until the load, so where its log ended then follows "
                   "the frame it was sent at"},
         shown=("name",)),
    Step("halt", "stop", {}, stopped, volatile=BREAK_STOP),
    Step("restored", "read_memory", {"ref": "paddle_x", "length": 2}, restored,
         shown=("summary", "hex"),
         highlight=("A saved state is the whole machine, not the game's own save. After the save "
                    "the left arrow moves the paddle, the load puts the machine back, and the "
                    "paddle read back is where it was before the arrow.")),
    Step("play on", "resume", {}, lambda reply, run: "the game runs"),
    Step("serve", "send_keys", {"keys": ["space"], "expect": "SERVE$", "seconds": 10},
         seen("SPACE served the ball that was waiting on the paddle"), volatile=INPUT_TIMING),
    Step("unwatch", "declaration_clear", {"kind": "watch", "all": True}, lambda reply,
         run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


DEMO = Demo(
    name="bricks", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", front=ROOT / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    precheck=precheck,
    volatile={**VOLATILE, "saved_at": "the wall-clock time a state was saved at"})


if __name__ == "__main__":
    isolated_store("bricks")
    sys.exit(main(DEMO))
