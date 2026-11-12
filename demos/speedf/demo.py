"""The Speed Fight demo on DOSBox-X: the PC game's own `.scry/` boots it. `--help` says how to
run it. The game is the reader's copy (`--cwd`); nothing of it is in this repository.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Run, Step, main
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
#: What the game's checkout holds: the program and its symbols, then what its store declares.
EXE, MAP = Path("EXES/SPEEDF.EXE"), Path("EXES/SPEEDF.MAP")
PROFILE = Path(".scry/start/dos.json")
#: The game's own deriver of a live-session conf; it writes `TMP/dosbox-mcp.conf`.
CONF_SCRIPT = Path("SCRIPTS/dosbox-mcp-conf.sh")
#: The normal core and a fixed clock: the dynamic core the game's conf keeps can pass a code
#: breakpoint over, and its `cycles=max` runs the guest as fast as the host can, so a slow or busy
#: host gives the game fewer cycles a second and it reaches each place later.
NORMAL_CORE_FIXED_CLOCK = ["-set", "cpu core=normal", "-set", "cpu cycles=fixed 50000"]
#: The game's first VESA call (`INT 10h AH=4Fh`), which neither DOS's boot nor the input stub
#: makes: the first stop there is inside the loaded game, and that stop places its map.
GAME_LOADED = {"number": "0x10", "ah": "0x4F"}
#: Called by `titulo_pantalla` once both planes of the title are drawn (SFTITLE.ASM); `draw_block`
#: runs many times on the way, so it is the run's control.
TITLE_DRAWN, DRAWING = "titulo_dibuja_cred", "draw_block"
WAIT_S = 120
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
    return {"profile": str(checkout(run) / PROFILE), "shared": True,
            "flags": NORMAL_CORE_FIXED_CLOCK,
            "captures_dir": str(run.dir / "speedf-captures")}


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
         volatile={"summary": "it carries how long the debugger took to answer",
                   "conf": "where the reader's copy of the game keeps its derived conf",
                   "name": "where the reader's copy of the game keeps its profile",
                   "held": "where the reader's copy of the game keeps its symbol table"},
         highlight=("`start(profile=...)` boots from the recipe the game's own repository "
                    "declares: the conf its script derives, the working directory, the "
                    "program spelled from where the autoexec leaves the guest, and the TLINK "
                    "map. The call gives only what is the run's own, and the reply says which "
                    "keys the recipe filled.")),
    Step("loaded", "breakpoint_interrupt", GAME_LOADED,
         lambda reply, run: f"a stop on {reply['ref']}"),
    Step("boot", "resume", {"seconds": WAIT_S}, map_placed,
         volatile={"waited_s": "wall-clock time the boot took"}),
    Step("unloaded", "declaration_clear", {"kind": "breakpoint", "all": True},
         lambda reply, run: "the boot's stop cleared"),
    Step("title", "run_to", {"ref": TITLE_DRAWN, "control": DRAWING, "seconds": WAIT_S},
         arrived(TITLE_DRAWN),
         highlight=("The run arrives by the game's own routine, not by time: `run_to` stops "
                    "where the title calls its credits line, once both planes are drawn, so "
                    "the picture that follows is the same on any host.")),
    Step("no credits", "read_memory", {"ref": "creditos", "length": 2}, word_is("creditos", 0),
         highlight=("`creditos` is read by name: the map `start` placed names the game's own "
                    "variables at the segment DOS loaded it at, the same name the arcade "
                    "build's map gives.")),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("close", "close", {}, quit_cleanly),
]

DEMO = Demo(
    name="speedf", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"cwd"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE_GAME,
    host_args={"cwd": "the reader's copy of the game, wherever it was cloned",
               "profile": "the reader's copy of the game, wherever it was cloned",
               "captures_dir": "the run's own directory"})

if __name__ == "__main__":
    isolated_store("speedf")
    sys.exit(main(DEMO))
