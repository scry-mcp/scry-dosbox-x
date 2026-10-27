"""The bricks demo: `BRICKS.COM`, a game this repository builds, driven by the calls the README's
prompt asks an MCP client to make, each answer checked. `--help` says how to run it.

It walks a debugger through a game: the first stop inside the program, its symbols placed from
the segment DOS loaded it at, a breakpoint on the routine every falling brick goes through, the
score read by name, the paddle moved by the keyboard and by the mouse, and a state saved and
loaded. The session is windowed so the game can be watched, and nothing in it needs the window:
`stop` and the saved states go down the debugger channel, the keys and the mouse in inside the
guest. The saved states need a DOSBox-X that carries SAVESTATE and LOADSTATE. Where the window
goes is `demos/host.py`'s to decide.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step, StepFailed, main

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import display, precheck  # noqa: E402

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


def expect(holds: bool, why: str) -> None:
    if not holds:
        raise StepFailed(why)


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
    # `shared` is the server's windowed session; the demo's own --shared only decides where the
    # window goes.
    return {"conf": HERE / "bricks.conf", "cwd": HERE, "session_seconds": 900, "shared": True,
            "display": display(run),
            "break_on_int3": True, "logfile": run.dir / "bricks-e9.log",
            "state_dir": states}


def started(reply: Reply, run: Run) -> str:
    watched = "shared" if reply.get("shared", False) else "headless"
    return f"{watched} DOSBox-X, parked at the debugger before DOS boots"


def at_ready(reply: Reply, run: Run) -> str:
    expect(reply["instruction"]["text"] == "int 3", f"stopped at {reply['instruction']}")
    cs, eip = str(reply["pc"]).split(":")
    return f"the program's own int 3 at {cs}:{eip[-4:]}: loaded at {cs}"


def symbols(run: Run) -> dict[str, Any]:
    """The table is offsets from the program's segment, so its base is that segment * 16."""
    cs = int(str(run.replies["ready"]["pc"]).split(":")[0], 16)
    return {"path": HERE / "bricks.sym", "base": f"{cs * 16:x}"}


def loaded(reply: Reply, run: Run) -> str:
    expect(reply["kept"] == reply["parsed"] > 0, f"{reply['kept']} of {reply['parsed']} kept")
    return f"{reply['kept']} symbols placed at base {reply['base']:#x}"


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


def pictured(reply: Reply, run: Run) -> str:
    expect(Path(reply["image"]["path"]).is_file(), f"no picture at {reply['image']['path']}")
    return f"mode {reply['vga_mode']}, {reply['width']}x{reply['height']} by palette index"


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


def seen(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verify"]["seen"] is True, f"verify {reply['verify']}")
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
#: Counts an input step reports that depend on when the host delivered the input, not on what
#: the game did with it.
INPUT_TIMING = {key: "it depends on when the host delivered the input"
                for key in ("lines_before", "seen_before_waiting", "lines_total", "lines_written",
                            "since_mark")}

STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("ready", "resume", {"seconds": WAIT_S}, at_ready,
         shown=("summary", "cause", "instruction")),
    Step("symbols", "symbols_load", symbols, loaded,
         shown=("summary", "base")),
    Step("look", "disassemble", {"ref": "brick_hit", "length": 32}, listing),
    Step("break", "breakpoint_at", {"ref": "brick_hit"},
         lambda reply, run: f"breakpoint {reply['entry']}",
         shown=("summary", "entry")),
    Step("watch", "watch_add", {"ref": "score", "mode": "show", "fmt": "u16"},
         lambda reply, run: "score shown at every stop"),
    Step("first brick", "resume", {"seconds": WAIT_S},
         at_brick(FIRST_ROW, FIRST_COL, 0, "first"),
         shown=("summary", "cause", "watches")),
    Step("second brick", "resume", {"seconds": WAIT_S},
         at_brick(*SECOND_BRICK, FIRST_POINTS, "second")),
    Step("score", "read_memory", {"ref": "score", "length": 2}, score_is(FIRST_POINTS),
         shown=("summary", "hex")),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("unbreak", "declaration_clear", {"kind": "breakpoint", "all": True}, lambda reply,
         run: "breakpoint cleared"),
    Step("frames", "run_for", {"frames": 3, "seconds": WAIT_S}, frames,
         volatile={key: "a retrace stop lands at any instruction of the game's retrace poll"
                   for key in ("summary", "regs", "instruction", "pc",
                               "cause")}),
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
         shown=("summary", "hex")),
    Step("play on", "resume", {}, lambda reply, run: "the game runs"),
    Step("serve", "send_keys", {"keys": ["space"], "expect": "SERVE$", "seconds": 10},
         seen("SPACE served the ball that was waiting on the paddle"), volatile=INPUT_TIMING),
    Step("unwatch", "declaration_clear", {"kind": "watch", "all": True}, lambda reply,
         run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


DEMO = Demo(
    name="bricks", root=ROOT, server=[sys.executable, str(ROOT / "dosbox_x_server.py")],
    readme=HERE / "README.md", front=ROOT / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"shared"}), reads=frozenset({"shared"}), precheck=precheck,
    volatile={"argv": "the emulator's command line, which carries the host's window placement",
              "elapsed_s": "wall-clock time since the session started",
              "waited_s": "wall-clock time a wait took", "ready_after_s": "wall-clock time "
              "the debugger took to answer",
              "saved_at": "the wall-clock time a state was saved at",
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
