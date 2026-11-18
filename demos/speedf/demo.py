"""The Speed Fight demo on DOSBox-X: the PC game's own `.scry/` boots it. `--help` says how to
run it. The game is the reader's copy (`--cwd`); nothing of it is in this repository.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scry_core.demo import DISPLAY, Demo, Moment, Run, Step, main, recording, window_args
from scry_core.game_demo import arrived, word_is

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    VOLATILE,
    checkout,
    conf_derived,
    isolated_store,
    map_placed,
    missing_under,
    pictured,
    precheck,
    quit_cleanly,
    started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: What the game's copy holds: the program and its symbols, then what its store declares.
EXE, MAP = Path("EXES/SPEEDF.EXE"), Path("EXES/SPEEDF.MAP")
PROFILE = Path(".scry/start/dos.json")
#: The game's own deriver of a live-session conf; it writes `TMP/dosbox-mcp.conf`.
CONF_SCRIPT = Path("SCRIPTS/dosbox-mcp-conf.sh")
#: The normal core and a fixed clock: the dynamic core the game's conf keeps can pass a code
#: breakpoint over, and its `cycles=max` runs the guest as fast as the host can, so a slow or busy
#: host gives the game fewer cycles a second and it reaches each place later. The clock is one
#: the game plays its match at speed on: on a slower one the puck crawls.
NORMAL_CORE_FIXED_CLOCK = ["-set", "cpu core=normal", "-set", "cpu cycles=fixed 300000"]
#: The game's first VESA call (`INT 10h AH=4Fh`), which neither DOS's boot nor the input stub
#: makes: the first stop there is inside the loaded game, and that stop places its map.
GAME_LOADED = {"number": "0x10", "ah": "0x4F"}
#: Called by `titulo_pantalla` once both planes of the title are drawn (SFTITLE.ASM); `draw_block`
#: runs many times on the way, so it is the run's control.
TITLE_DRAWN, DRAWING = "titulo_dibuja_cred", "draw_block"
#: The attract's demo entry, where the game starts playing itself (SFDEMO.ASM), and the video
#: interrupt that runs every frame on the way there.
DEMO_STARTS, EVERY_FRAME = "startdemo", "new_irq_video"
WAIT_S = 120
#: The retraces recorded of the game playing itself, and the three seconds of them the loop
#: shows: the match once its first serve is hit.
PLAYS_FRAMES, PLAYS_SKIP, PLAYS_SHOWN = 380, 160, 210
#: The reader's copy of the game is where this host keeps things; the replies that name it are
#: hidden in the transcript.
VOLATILE_GAME = {**VOLATILE,
                 "conf": "where the reader's copy of the game keeps its derived conf",
                 "state_dir": "a directory in the session's own temporary directory",
                 "window": "the host's display and the window it fits",
                 "file": "where the reader's copy of the game keeps its store",
                 "path": "a file inside the reader's copy of the game",
                 "conf_digest": "the derived conf names the host's guest directory"}


def checked(run: Run) -> str:
    return precheck(run) or missing_under(
        run, (EXE, MAP, PROFILE, CONF_SCRIPT),
        "the reader's copy of the game (its EXES/, its .scry/ and its SCRIPTS/)")


def boot(run: Run) -> dict[str, Any]:
    """The game's own conf, derived by its own script, then the profile that names it."""
    conf_derived(run, CONF_SCRIPT)
    return {**window_args(run), "profile": str(checkout(run) / PROFILE),
            "flags": NORMAL_CORE_FIXED_CLOCK,
            "captures_dir": str(run.dir / "speedf-captures")}


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer",
                   "conf": "where the reader's copy of the game keeps its derived conf",
                   "name": "where the reader's copy of the game keeps its profile",
                   "held": "where the reader's copy of the game keeps its symbol table",
                   "logfile": "where the reader's copy of the game keeps the guest's log"},
         title="Start from the game's own start profile",
         ask="Start Speed Fight from the start profile in its `.scry/start/` folder.",
         shown=("status", "kept"),
         reads=("A start profile is a saved set of `start` arguments: the call adds only what is "
                "this run's own. `kept` says a candidate was saved for `promote`; the whole reply "
                "lists what the file filled in `profile.supplied`.")),
    Step("loaded", "breakpoint_interrupt", GAME_LOADED,
         lambda reply, run: f"a stop on {reply['ref']}"),
    Step("boot", "resume", {"seconds": WAIT_S}, map_placed,
         volatile={"waited_s": "wall-clock time the boot took"}),
    Step("unloaded", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the boot's stop cleared"),
    Step("title", "run_to", {"ref": TITLE_DRAWN, "control": DRAWING, "seconds": WAIT_S},
         arrived(TITLE_DRAWN),
         title="Run until the title is drawn",
         ask="Run the game to `titulo_dibuja_cred`, counting `draw_block` on the way.",
         shown=("summary", "verdict", "control_hits"),
         reads=("`TARGET` means the run stopped where the title calls its credits line, once "
                "both planes are drawn. `control_hits` counts a routine that ran many times "
                "meanwhile.")),
    Step("no credits", "read_memory", {"ref": "creditos", "length": 2}, word_is("creditos", 0),
         title="Read a variable by its name",
         ask="Read the game's `creditos` variable.",
         shown=("summary", "hex"),
         reads=("`creditos` is a name from the game's symbol map, resolved at the segment DOS "
                "loaded the program at. The arcade build's map gives the same name.")),
    Step("to the demo", "run_to", {"ref": DEMO_STARTS, "control": EVERY_FRAME,
                                   "seconds": WAIT_S}, arrived(DEMO_STARTS)),
    recording("plays", PLAYS_FRAMES),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("close", "close", {}, quit_cleanly),
]

DEMO = Demo(
    name="speedf", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    moments=(Moment("to the demo", "plays",
                    "`run_to` stops where the game starts playing itself, and `record` films "
                    "the match.", skip=PLAYS_SKIP, frames=PLAYS_SHOWN),),
    alt="Speed Fight playing its own demo match on the DOS version",
    offers=frozenset({"cwd", "display"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE_GAME,
    host_args={"cwd": "the reader's copy of the game",
               "display": DISPLAY,
               "profile": "the reader's copy of the game",
               "captures_dir": "the run's own directory"})

if __name__ == "__main__":
    isolated_store("speedf")
    sys.exit(main(DEMO))
