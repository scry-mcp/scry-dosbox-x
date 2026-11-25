"""The bricks demo: `BRICKS.COM`, a game this repository builds, driven by the calls the README's
prompt asks an MCP client to make, each answer checked. `--help` says how to run it.

It walks a debugger through a game: the first stop inside the program, its symbols placed from
the segment DOS loaded it at, a breakpoint on the routine every falling brick goes through, the
score read by name, the routine that takes a life, the paddle moved by the keyboard and by the
mouse, and the same ball lost twice from one saved state, the second time with the lives frozen.
The session is windowed so the game can be watched, and nothing in it needs the window: the
saved states go down the debugger channel, the keys and the mouse in inside the guest. The saved
states need a DOSBox-X that carries SAVESTATE and LOADSTATE, and the freeze a build with heavy
debugging. Each moment is its own `record`, which runs the machine's frames from where the call
before it stopped, so a key or the pointer is inside the stretch it shows.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from scry_core import demo as core
from scry_core import motion
from scry_core.demo import (
    DISPLAY,
    RECORD_SECONDS,
    RECORD_TOOL,
    RECORDING_TIMING,
    Demo,
    Moment,
    Reply,
    Run,
    Step,
    recording,
    window_args,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    RETRACE_STOP,
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
#: The score once the ball has left the second brick: the breakpoint stops at the routine's
#: entry, so the second brick's points are counted by the first retrace after it is cleared.
TWO_POINTS = FIRST_POINTS * 2
#: Where three retraces after the second brick leave the ball: x, y, dx, dy.
BALL_AFTER = (188, 82, -2, 2)
PADDLE_HOME, PADDLE_STEP, RIGHTS, PADDLE_W = 140, 8, 3, 40
#: Where the demo puts the pointer, in screen pixels: the paddle centres itself under it.
MOUSE_AT = (240, 100)
#: The game's first life, and the state saved with the ball waiting on the paddle.
LIVES = 3
STATE = "before_the_miss"
#: The frames one moment records: about a second and a half at the game's 70 frames a second.
MOMENT_FRAMES = 110
#: The frames the breakpoint's moment asks for; the second brick stops it first.
BRICK_FRAMES = 200
WAIT_S = 60


def video(run: Run) -> Path:
    """Where the emulator writes a capture; each moment's `record` is moved out of it."""
    return run.dir / "video"


def low_byte(reply: Reply, register: str) -> int:
    return int(reply["regs"][register], 16) & 0xFF


def word(reply: Reply) -> int:
    """A little-endian 16-bit value out of `read_memory`'s hex."""
    raw = bytes.fromhex(reply["hex"])
    return raw[0] | raw[1] << 8


def capture_conf(run: Run) -> Path:
    """The game's conf with the line that boots the game taken out: the session records itself
    with `DX-CAPTURE`, which runs the program itself and can hold no second copy."""
    text = (HERE / "bricks.conf").read_text(encoding="utf-8")
    kept = [line for line in text.splitlines() if line.strip().casefold() != "bricks.com"]
    path = run.dir / "bricks-capture.conf"
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return path


def boot(run: Run) -> dict[str, Any]:
    """A fresh log and state directory of this demo's own under the run's, so nothing an earlier
    run left is counted again (`state_write(method="save")` never overwrites)."""
    (run.dir / "bricks-e9.log").unlink(missing_ok=True)
    states = run.dir / "bricks-states"
    shutil.rmtree(states, ignore_errors=True)
    shutil.rmtree(video(run), ignore_errors=True)
    return {**window_args(run), "conf": capture_conf(run), "cwd": HERE, "session_seconds": 900,
            "break_on_int3": True, "logfile": run.dir / "bricks-e9.log",
            "state_dir": states, "program": "BRICKS.COM",
            "captures_dir": video(run)}


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


def brick_film(run: Run) -> dict[str, Any]:
    """The breakpoint's moment: `record` runs the ball from the first brick's stop, and the
    breakpoint stops it at the second brick before the bound."""
    dest = run.dir / "first-brick.avi"
    dest.unlink(missing_ok=True)
    return {"frames": BRICK_FRAMES, "dest": dest, "seconds": RECORD_SECONDS}


def brick_filmed(reply: Reply, run: Run) -> str:
    """The recording ends where the ball meets the second brick, and lasts a moment."""
    expect(reply.get("verdict") == "OTHER_STOP", f"the recording ended {reply.get('verdict')!r}")
    expect(str(reply.get("cause", "")).startswith("breakpoint brick_hit "),
           f"stopped by {reply.get('cause')}")
    got = (low_byte(reply, "EAX"), low_byte(reply, "EBX"), reply["watches"][0]["value"])
    expect(got == (*SECOND_BRICK, FIRST_POINTS), f"row, column and score {got}")
    held, per_second = motion.facts(Path(str(reply["path"])))
    seconds = held / per_second
    expect(seconds >= motion.CUT_SECONDS[0] - motion.SLACK_SECONDS,
           f"the recording lasts {seconds:.2f} s, and a moment lasts at least "
           f"{motion.CUT_SECONDS[0]:g} s")
    return f"the fall into the second brick, {held} frames in {seconds:.2f} s"


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


def listing_lives(reply: Reply, run: Run) -> str:
    lines = [ln.split(maxsplit=2)[-1] for ln in reply["lines"]]
    expect(any(text.startswith("dec byte") for text in lines), f"lose_life is {lines}")
    return f"lose_life opens with {lines[0]} and decrements the lives"


def pinned(reply: Reply, run: Run) -> str:
    expect((reply["state"], reply["frozen_hex"]) == ("armed", f"{LIVES:02x}"),
           f"{reply['state']} at {reply.get('frozen_hex')}")
    return f"the lives pinned at {LIVES}"


def lives_are(count: int) -> Any:
    def check(reply: Reply, run: Run) -> str:
        got = int(reply["hex"], 16)
        expect(got == count, f"lives read {got}, not {count}")
        return f"the lives read {count}"
    return check


def lost_twice(reply: Reply, run: Run) -> str:
    lines = [ln.split(": ", 1)[-1] for ln in reply["lines"]]
    expect(lines.count("LOST") == 2, f"the game logged {lines}")
    return "the game logged LOST twice: the same ball, lost twice"


def mouse_paddle(reply: Reply, run: Run) -> str:
    want = MOUSE_AT[0] - PADDLE_W // 2
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
    Step("start", "start", boot, started, options=frozenset({"binary", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("ready", "resume", {"seconds": WAIT_S}, at_ready),
    Step("symbols", "symbols_load", symbols_at(HERE / "bricks.sym"), loaded),
    Step("look", "disassemble", {"ref": "brick_hit", "length": 32}, listing),
    Step("break", "breakpoint_at", {"ref": "brick_hit"},
         lambda reply, run: f"breakpoint {reply['entry']}",
         title="Set a breakpoint by a name",
         ask="Put a breakpoint on `brick_hit`.",
         shown=("summary", "entry", "by"),
         reads=("`brick_hit` is a label of the symbol table the build wrote, so `by` says "
                "`symbol`. `armed` means the breakpoint is set in the debugger, at the address "
                "`entry` gives.")),
    Step("watch", "watch_add", {"ref": "score", "mode": "show", "fmt": "u16"},
         lambda reply, run: "score shown at every stop"),
    Step("first brick", "resume", {"seconds": WAIT_S},
         at_brick(FIRST_ROW, FIRST_COL, 0, "first"),
         title="Run until the program stops itself",
         ask="Let the game run until that breakpoint stops it, and tell me the score.",
         shown=("summary", "verdict", "cause"),
         reads=("`OTHER_STOP` means the breakpoint stopped the run, not a time limit. `cause` "
                "names it; the whole reply also holds `watches`, the score read by its name.")),
    # The breakpoint's moment: the recording runs the ball from the first stop and ends where the
    # breakpoint stops it again, at the second brick. A code breakpoint is all that can stop it.
    Step("brick seen", RECORD_TOOL, brick_film, brick_filmed, volatile=RECORDING_TIMING),
    Step("unbreak", "declaration_clear", {"kind": "breakpoint", "all": True}, lambda reply,
         run: "breakpoint cleared"),
    Step("frames", "run_for", {"frames": 3, "seconds": WAIT_S}, frames,
         volatile={key: "a retrace stop lands at any instruction of the game's retrace poll"
                   for key in ("summary", "regs", "instruction", "pc", "cause",
                               "emulated_before_s", "emulated_after_s")}),
    Step("ball", "read_memory", {"ref": "ball_x", "length": 8}, ball),
    # The picture is taken here, before any input, from where the ball read left the machine.
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("score", "read_memory", {"ref": "score", "length": 2}, score_is(TWO_POINTS)),
    recording("score seen", MOMENT_FRAMES),
    # The second act: the routine that takes a life, then the same ball lost twice from one
    # saved state. The first arrow key is where the game hands the paddle over, so the ball
    # waits on it and the recording after the keys shows the paddle they moved.
    Step("lives routine", "disassemble", {"ref": "lose_life", "length": 16}, listing_lives),
    Step("break lives", "breakpoint_at", {"ref": "lose_life"},
         lambda reply, run: f"breakpoint {reply['entry']} on lose_life"),
    Step("key right", "send_keys", {"keys": ["right"], "expect": "KEY R$"},
         seen("the right arrow took the paddle from the game"), volatile=INPUT_TIMING),
    Step("key left", "send_keys", {"keys": ["left"], "expect": "KEY L$"},
         seen("the left arrow moved the paddle back"), volatile=INPUT_TIMING),
    Step("key right again", "send_keys", {"keys": ["right"], "expect": "KEY R$"},
         seen("the right arrow moved it again"), volatile=INPUT_TIMING),
    recording("keys seen", MOMENT_FRAMES),
    Step("save", "state_write", {"method": "save", "name": STATE},
         lambda reply, run: f"state saved as {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries the state's size and time", "bytes": "the state is "
                   "compressed, so its size follows the frame it was taken at"}),
    Step("serve", "send_keys", {"keys": ["space"], "expect": "SERVE$", "seconds": 10},
         seen("SPACE served the ball that was waiting on the paddle"), volatile=INPUT_TIMING),
    Step("miss", "resume", {"seconds": WAIT_S},
         lambda reply, run: f"the stop at {reply['cause']}",
         volatile={**BREAK_STOP, "watches": "the score shown at the stop is the game's"}),
    Step("past", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the breakpoint on lose_life cleared"),
    Step("carry", "run_to", {"ref": "carry", "control": "retrace", "seconds": WAIT_S},
         lambda reply, run: f"{reply['verdict']}: the next ball waits on the paddle"),
    Step("shown", "run_for", {"frames": 20, "seconds": WAIT_S},
         lambda reply, run: "20 retraces with the status line redrawn",
         volatile={**RETRACE_STOP,
                   **{key: "it names the instruction or the clock a retrace stop lands on, "
                           "which drift with the host's cycles"
                      for key in ("summary", "emulated_before_s", "emulated_after_s")},
                   "cycles": "the emulator's own count, a few cycles apart from run to run"}),
    Step("lives", "read_memory", {"ref": "lives", "length": 1}, lives_are(LIVES - 1)),
    Step("load", "state_write", {"method": "load", "name": STATE},
         lambda reply, run: f"state loaded from {Path(str(reply['path'])).name}",
         volatile={"summary": "it carries how long the load took",
                   "mark": "the game ran until the load, so where its log ended then follows "
                   "the frame it was sent at"}),
    Step("pin", "watch_add", {"ref": "lives", "mode": "freeze", "length": 1}, pinned),
    Step("break again", "breakpoint_at", {"ref": "lose_life"},
         lambda reply, run: f"breakpoint {reply['entry']} on lose_life again"),
    Step("serve 2", "send_keys", {"keys": ["space"], "expect": "SERVE$", "seconds": 10},
         seen("SPACE served the same ball from the saved machine"), volatile=INPUT_TIMING),
    Step("miss 2", "resume", {"seconds": WAIT_S},
         lambda reply, run: f"the stop at {reply['cause']} again",
         volatile={**BREAK_STOP, "watches": "the score shown at the stop is the game's"}),
    Step("past 2", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the breakpoint cleared"),
    Step("carry 2", "run_to", {"ref": "carry", "control": "retrace", "seconds": WAIT_S},
         lambda reply, run: f"{reply['verdict']}: the next ball waits on the paddle"),
    Step("shown 2", "run_for", {"frames": 20, "seconds": WAIT_S},
         lambda reply, run: "20 retraces with the status line redrawn",
         volatile={**RETRACE_STOP,
                   **{key: "it names the instruction or the clock a retrace stop lands on, "
                           "which drift with the host's cycles"
                      for key in ("summary", "emulated_before_s", "emulated_after_s")},
                   "cycles": "the emulator's own count, a few cycles apart from run to run"}),
    Step("lives 2", "read_memory", {"ref": "lives", "length": 1}, lives_are(LIVES),
         title="Hold a value against the program's own writes",
         ask=("The same ball was just lost again: read `lives` now that `watch_add` freezes "
              "it."),
         shown=("summary", "hex"),
         reads=("A freeze is the debugger putting a byte back after every instruction. The game "
                "took the life and the status line still reads 3: `frozen_hex` is the value "
                "`watch_add` holds.")),
    recording("lives held", MOMENT_FRAMES),
    Step("log 2", "log", {"channel": "guest", "pattern": "SERVE|HIT|LOST"}, lost_twice),
    Step("mouse on", "send_keys", {"keys": ["m"], "expect": "MOUSE ON$", "seconds": 10},
         seen("M handed the paddle to the mouse: the game logged MOUSE ON"),
         volatile=INPUT_TIMING),
    Step("mouse", "send_mouse", {"x": MOUSE_AT[0], "y": MOUSE_AT[1], "expect": "MOUSE$"},
         pointed, volatile=INPUT_TIMING),
    recording("pointer seen", MOMENT_FRAMES),
    Step("paddle", "read_memory", {"ref": "paddle_x", "length": 2}, mouse_paddle),
    Step("unwatch", "declaration_clear", {"kind": "watch", "all": True}, lambda reply,
         run: "watch cleared"),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


DEMO = Demo(
    name="bricks", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", front=ROOT / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    moments=(Moment("first brick", "brick seen",
                    "`resume` runs the game to the breakpoint on `brick_hit`, and the ball falls "
                    "into the next brick."),
             Moment("score", "score seen",
                    "`read_memory` reads the score by its name: twenty points from the two "
                    "bricks the ball broke."),
             Moment("key right again", "keys seen",
                    "`send_keys` steps the paddle right, left and right; the game logs each key."),
             Moment("lives 2", "lives held",
                    "With `lives` frozen, the same ball is lost and the status line still reads "
                    "3."),
             Moment("mouse", "pointer seen",
                    "`send_mouse` puts the pointer at 240,100 and the paddle centres itself "
                    "under it.")),
    alt="Bricks on its DOS version: a breakpoint at a brick, the score, the paddle stepped by "
        "the keys and by the mouse, and the lives frozen",
    precheck=precheck, offers=frozenset({"display"}),
    host_args={"display": DISPLAY, "captures_dir": "the run's own directory"},
    volatile={**VOLATILE, "saved_at": "the wall-clock time a state was saved at"})


if __name__ == "__main__":
    isolated_store("bricks")
    sys.exit(core.main(DEMO))
