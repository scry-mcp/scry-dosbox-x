"""The Minesweeper demo: `MINES.COM`, a game this repository builds, played at VESA 800 x 600 by
the calls the README's prompt asks an MCP client to make, each answer checked. `--help` says how
to run it.

It walks a debugger through a program with several screens: every screen recognised off the
screen map before a click lands on it, the menu used by name, the mines read out of the game's
memory by symbol, the board cleared without a miss, and then a mine stepped on on purpose so its
explosion can be recorded off the Sound Blaster and held, sample for sample, against the
recording committed beside this file (`boom.wav`). The recording starts where the click's post
leaves the machine, a few retraces after the game took the click, so it holds the explosion from
there on: what it holds is decided by the game's sound and timing and by the input route's own
pacing, and a change to any of them makes that check fail. The run's own `run.wav`, beside its
transcript, is then the new reference to copy over it. The session is windowed so the game can be
watched; nothing in it needs the window. Each moment is its own `record`, which runs the
machine's frames from where the call before it stopped, so the board it changed is on screen.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from scry_core import demo as core
from scry_core.demo import (
    DISPLAY,
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
#: The layers that exist for this demo: its calls and the mouse it sends.
#: These mirror mines.asm: a beginner's board, its cells' size, and where the pointer waits
#: while a screen is read, off every region the map signs.
ROWS, COLS, MINES, CELL = 9, 9, 10, 24
PARK = (790, 590)
#: How many mines the demo flags before it clears the board.
FLAGGED = 2
#: Retraces recorded from where the click's post leaves the machine: the explosion lasts 0.6 s,
#: the screen retraces 70 times a second, and the post has already run a few of them.
BOOM_FRAMES = 45
#: The retraces run at the win, which the explosion's reference sound was made with.
WIN_FRAMES = 240
#: The frames one moment records: about two seconds at the game's retrace rate, and inside the
#: shortest and longest a moment may last.
MOMENT_FRAMES = 130
WAIT_S = 60


def boot(run: Run) -> dict[str, Any]:
    """A fresh log and state directory of this demo's own under the run's: the server writes no
    file over an existing one."""
    (run.dir / "mines-e9.log").unlink(missing_ok=True)
    (run.dir / "run.wav").unlink(missing_ok=True)
    states = run.dir / "mines-states"
    shutil.rmtree(states, ignore_errors=True)
    return {**window_args(run), "conf": HERE / "mines.conf", "cwd": HERE, "session_seconds": 900,
            "program": "MINES.COM", "break_on_int3": True,
            "logfile": run.dir / "mines-e9.log", "state_dir": states}


def at_ready(reply: Reply, run: Run) -> str:
    expect(reply["instruction"]["text"] == "int 3", f"stopped at {reply['instruction']}")
    cs = str(reply["pc"]).split(":")[0]
    return f"the program's own int 3, in VBE mode 103h, loaded at {cs}"


def found(name: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["matched"] is True and reply["screen"] == name,
               f"screen_map_find answered {reply.get('screen', 'no screen')}, not {name}")
        named = ", ".join(c["name"] for c in reply["controls"])
        return f"the {name} screen, its controls {named}"
    return check


def size(reply: Reply, run: Run) -> str:
    rows, cols = bytes.fromhex(reply["hex"])
    expect((rows, cols) == (ROWS, COLS), f"a {rows} x {cols} board, not {ROWS} x {COLS}")
    return f"rows {rows}, cols {cols}"


def mines_of(reply: Reply) -> list[tuple[int, int]]:
    cells = bytes.fromhex(reply["hex"])
    return [divmod(i, COLS) for i, b in enumerate(cells) if b]


def mines_read(reply: Reply, run: Run) -> str:
    at = mines_of(reply)
    expect(len(at) == MINES, f"{len(at)} mines in the board, not {MINES}")
    return "mines at " + ", ".join(f"{r},{c}" for r, c in at)


def origin(run: Run, step: str = "origin") -> tuple[int, int]:
    raw = bytes.fromhex(run.replies[step]["hex"])
    return int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:], "little")


def origin_read(reply: Reply, run: Run) -> str:
    raw = bytes.fromhex(reply["hex"])
    x, y = int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:], "little")
    expect((x, y) == ((800 - COLS * CELL) // 2, 24 + (552 - ROWS * CELL) // 2),
           f"the board's corner at {x},{y}")
    return f"the board's top-left corner at pixel {x},{y}"


def centre(run: Run, row: int, col: int) -> tuple[int, int]:
    x, y = origin(run)
    return x + col * CELL + CELL // 2, y + row * CELL + CELL // 2


def plan(mines: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The fewest clicks that open every safe cell, the game's own flood fill played out: a cell
    with no mine around it opens its neighbours, so one click opens a whole empty region. Only
    mines are flagged (`flags` takes them from `mines`), because a click on a flagged safe cell
    would be ignored and the board would never be cleared."""
    mined = set(mines)

    def around(r: int, c: int) -> list[tuple[int, int]]:
        return [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if (dr or dc) and 0 <= r + dr < ROWS and 0 <= c + dc < COLS]

    opened: set[tuple[int, int]] = set()
    clicks = []
    for cell in ((r, c) for r in range(ROWS) for c in range(COLS)):
        if cell in mined or cell in opened:
            continue
        clicks.append(cell)
        todo = [cell]
        opened.add(cell)
        while todo:
            here = todo.pop()
            if any(n in mined for n in around(*here)):
                continue
            for n in around(*here):
                if n not in mined and n not in opened:
                    opened.add(n)
                    todo.append(n)
    return clicks


def flags(run: Run) -> dict[str, Any]:
    first = mines_of(run.replies["mines"])[:FLAGGED]
    return {"steps": [{"op": "send_mouse", "x": x, "y": y, "button": "right",
                       "expect": f"FLAG {r} {c}$", "seconds": 10}
                      for r, c in first for x, y in [centre(run, r, c)]],
            "summaries": True}


def flagged(reply: Reply, run: Run) -> str:
    expect(reply["steps_completed"] == FLAGGED, f"{reply['steps_completed']} flags of {FLAGGED}")
    return f"{FLAGGED} mines flagged with the right button"


def first_safe(run: Run) -> tuple[int, int]:
    """The first cell the memory says is safe, and the one its own click opens."""
    return plan(mines_of(run.replies["mines"]))[0]


def safe_click(run: Run) -> dict[str, Any]:
    r, c = first_safe(run)
    x, y = centre(run, r, c)
    return {"x": x, "y": y, "button": "left", "expect": f"REVEAL {r} {c} "}


def safe_opened(reply: Reply, run: Run) -> str:
    r, c = first_safe(run)
    expect(reply["verify"]["seen"] is True, f"verify {reply['verify']}")
    return f"a left click on the safe cell at {r},{c}: the game revealed it"


def clear(run: Run) -> dict[str, Any]:
    """The plan's clicks but the one the demo already made."""
    clicks = plan(mines_of(run.replies["mines"]))[1:]
    return {"steps": [{"op": "send_mouse", "x": x, "y": y, "button": "left",
                       "expect": f"REVEAL {r} {c} "}
                      for r, c in clicks for x, y in [centre(run, r, c)]],
            "summaries": True}


def cleared(reply: Reply, run: Run) -> str:
    wanted = len(plan(mines_of(run.replies["mines"]))) - 1
    expect(reply["steps_completed"] == wanted,
           f"{reply['steps_completed']} of {wanted} clicks, failed at {reply['failed_at']}")
    return f"{wanted} clicks opened every safe cell, none on a mine"


def drawn(what: str) -> Any:
    """A run to the game's loop, which it re-enters only once a click's drawing is done."""
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}")
        return what
    return check


def back_in_loop(name: str, what: str) -> Step:
    return Step(name, "run_to", {"ref": "main_loop", "control": "retrace", "seconds": WAIT_S},
                drawn(what))


def won(reply: Reply, run: Run) -> str:
    expect(reply["lines_total"] == 1, f"the game logged WIN {reply['lines_total']} times")
    return "the game logged WIN"


def parked(reply: Reply, run: Run) -> str:
    expect(reply["driver_arrived"] is True,
           f"the pointer read back at {reply['pointer']['screen']}")
    return f"the pointer parked at {PARK[0]},{PARK[1]}, off every region the map signs"


def first_mine(run: Run) -> tuple[int, int]:
    return mines_of(run.replies["next mines"])[0]


def step_on(run: Run) -> dict[str, Any]:
    r, c = first_mine(run)
    x, y = centre(run, r, c)
    return {"x": x, "y": y, "button": "left", "expect": f"BOOM {r} {c}$"}


def stepped(reply: Reply, run: Run) -> str:
    r, c = first_mine(run)
    expect(reply["driver_arrived"] is True,
           f"the pointer read back at {reply['pointer']['screen']}")
    expect(reply["verify"]["seen"] is True, f"verify {reply['verify']}")
    return (f"a left click on the mine at {r},{c}, the machine left stopped a few retraces "
            f"later, the explosion already sounding")


def boom_said(reply: Reply, run: Run) -> str:
    r, c = first_mine(run)
    lines = [ln.split(": ", 1)[-1] for ln in reply["lines"]]
    expect(lines == [f"BOOM {r} {c}"], f"the game logged {lines}")
    return f"the game logged BOOM {r} {c}"


def recorded(reply: Reply, run: Run) -> str:
    expect(reply["verdict"] == "ELAPSED", f"verdict {reply['verdict']}")
    return f"{BOOM_FRAMES} retraces recorded from where the click left the machine"


def heard(reply: Reply, run: Run) -> str:
    left = reply["measures"][0]
    expect(left["silent"] is False, f"the recording is silent: {left}")
    return f"a sound, peaking at {left['peak_dbfs']} dBFS"


def exact(reply: Reply, run: Run) -> str:
    expect(reply["exact"] is True, f"the explosion differs from boom.wav: {reply['class']}, "
                                   f"{reply['snr_db']} dB")
    return "the explosion is boom.wav, sample for sample"



STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer"}),
    Step("ready", "resume", {"seconds": WAIT_S}, at_ready),
    Step("symbols", "symbols_load", symbols_at(HERE / "mines.sym"), loaded),
    Step("map", "screen_map_write", {"method": "load", "path": HERE / "mines-screen-map.json"},
         lambda reply, run: f"{reply['screens']} screens and {reply['controls']} controls "
                            "loaded"),
    Step("title", "run_to", {"ref": "main_loop", "control": "retrace", "seconds": WAIT_S},
         drawn("the game's loop reached: the title drawn and the pointer up"),
         title="Run to a routine by its name",
         ask="Run the game until it reaches `main_loop`.",
         shown=("summary", "verdict"),
         reads=("`TARGET` means the run stopped at `main_loop`, where the game goes once its "
                "title is drawn. So the screen read next is whole on any computer.")),
    Step("is title", "screen_map_find", {}, found("title")),
    recording("title seen", MOMENT_FRAMES),
    Step("play", "send_mouse", {"target": "start", "button": "left", "expect": "NEW 9 9 10$"},
         seen("a click on the title started a beginner's game"), volatile=INPUT_TIMING),
    back_in_loop("board drawn", "the board drawn"),
    Step("is board", "screen_map_find", {}, found("board")),
    Step("menu", "send_mouse", {"target": "game", "button": "left", "expect": "MENU OPEN$"},
         seen("Game opened the menu"), volatile=INPUT_TIMING),
    back_in_loop("menu drawn", "the menu drawn"),
    Step("is menu", "screen_map_find", {}, found("menu")),
    Step("level", "send_mouse", {"target": "beginner", "button": "left", "expect": "NEW 9 9 10$"},
         seen("Beginner started a new beginner's game"), volatile=INPUT_TIMING),
    back_in_loop("board drawn again", "the new board drawn"),
    Step("is board again", "screen_map_find", {}, found("board")),
    Step("size", "read_memory", {"ref": "rows", "length": 2}, size),
    Step("mines", "read_memory", {"ref": "mines", "length": ROWS * COLS}, mines_read,
         title="Read the board out of memory",
         ask="Read the 81 bytes at `mines`, the game's own table of where the mines are.",
         shown=("summary", "length"),
         reads=("`mines` is a symbol of the build, one byte per cell. Where the mines are is "
                "data the server can read and a player cannot.")),
    recording("mines read", MOMENT_FRAMES),
    Step("origin", "read_memory", {"ref": "board_x", "length": 4}, origin_read),
    Step("flags", "perform", flags, flagged),
    Step("safe", "send_mouse", safe_click, safe_opened, volatile=INPUT_TIMING),
    recording("safe opened", MOMENT_FRAMES),
    Step("clear", "perform", clear, cleared,
         title="Clear the board in one call",
         ask=("Open every safe cell with as few clicks as the game's flood fill allows, waiting "
              "for the game to log each reveal."),
         shown=("summary", "steps_completed"),
         reads=("Each click waits for the line the game logs when it reveals that cell, so a "
                "click that missed fails at once. `perform` sends them all as one call.")),
    recording("board cleared", MOMENT_FRAMES),
    back_in_loop("cleared drawn", "the last reveal and the win dialog drawn"),
    Step("won", "log", {"channel": "guest", "pattern": "WIN$"}, won),
    Step("park", "send_mouse", {"x": PARK[0], "y": PARK[1]}, parked),
    Step("is win", "screen_map_find", {}, found("win")),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    # These retraces are part of what the explosion is compared from, sample for sample: the
    # reference was recorded with as many between the win and the click that follows.
    Step("win", "run_for", {"frames": WIN_FRAMES, "seconds": WAIT_S},
         lambda reply, run: f"{WIN_FRAMES} retraces with the win dialog up",
         volatile={**RETRACE_STOP,
                   **{key: "it names the instruction or the clock a retrace stop lands on, "
                           "which drift with the host's cycles"
                      for key in ("summary", "emulated_before_s", "emulated_after_s")},
                   "cycles": "the emulator's own count, a few cycles apart from run to run"},
         optional={"note": "it comes only when the stop landed in a ROM handler, which is the "
                           "host's"}),
    Step("again", "send_mouse", {"target": "ok", "button": "left", "expect": "NEW 9 9 10$"},
         seen("OK started the next game"), volatile=INPUT_TIMING),
    back_in_loop("next board drawn", "the next board drawn"),
    Step("next mines", "read_memory", {"ref": "mines", "length": ROWS * COLS}, mines_read),
    Step("mine", "send_mouse", step_on, stepped, volatile=INPUT_TIMING),
    Step("boom", "log", {"channel": "guest", "pattern": "BOOM"}, boom_said),
    Step("record", "audio_record", lambda run: {"frames": BOOM_FRAMES,
                                                "dest": run.dir / "run.wav"}, recorded,
         volatile={"path": "the run's own directory"}),
    Step("exact", "audio_compare", lambda run: {"method": "diff", "a": run.dir / "run.wav",
                                                "b": HERE / "boom.wav", "align": False},
         exact, volatile={"a": "the run's own directory"},
         title="Compare a sound with its reference",
         ask="Compare the explosion you recorded with `boom.wav`, sample by sample.",
         shown=("summary", "exact"),
         reads=("`exact` is true only when every sample is equal. The recording comes from the "
                "emulated Sound Blaster's digital output, not from the speakers.")),
    recording("explosion shown", MOMENT_FRAMES),
    Step("heard", "audio_compare", lambda run: {"method": "measure",
                                                "path": run.dir / "run.wav"}, heard,
         volatile={"path": "the run's own directory"}),
    Step("park again", "send_mouse", {"x": PARK[0], "y": PARK[1]}, parked),
    Step("is lose", "screen_map_find", {}, found("lose")),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]


DEMO = Demo(
    name="mines", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    moments=(Moment("is title", "title seen",
                    "`screen_map_find` names the screen the game is showing: the title."),
             Moment("mines", "mines read",
                    "`read_memory` reads the 81 bytes that say where the mines are."),
             Moment("safe", "safe opened",
                    "`send_mouse` clicks a cell the memory says is safe, and the game reveals "
                    "it."),
             Moment("clear", "board cleared",
                    "One `perform` sends the rest of the clicks, and the board opens."),
             Moment("exact", "explosion shown",
                    "The explosion recorded from the emulated Sound Blaster equals `boom.wav`.")),
    alt="Minesweeper read out of memory and cleared click by click without a miss, then a mine "
        "stepped on",
    precheck=precheck, offers=frozenset({"display"}),
    host_args={"display": DISPLAY},
    volatile=VOLATILE)


if __name__ == "__main__":
    isolated_store("mines")
    sys.exit(core.main(DEMO))
