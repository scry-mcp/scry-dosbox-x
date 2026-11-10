"""The LineUp demo on DOSBox-X: the PC port's own `.scry/` boots it and the `perform` document it
declares is replayed on that session. `--help` says how to run it. The game is the reader's copy
(`--cwd`); nothing of it is in this repository.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scry_core import recording
from scry_core.demo import Demo, Reply, Run, Step, expect, main
from scry_core.game_demo import Binding, Press, map_load
from scry_core.games import lineup

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    VOLATILE,
    checkout,
    conf_derived,
    isolated_store,
    map_placed,
    missing_under,
    precheck,
    started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: What the game's checkout holds: the program and its symbols, then what its store declares.
EXE, MAP = Path("EXES/LINEUP.EXE"), Path("EXES/LINEUP.MAP")
PROFILE = Path(".scry/start/dos.json")
SCREEN_MAP = Path(".scry/maps/lineup-screen-map.json")
SCRIPT = Path(".scry/perform/dos.json")
#: The game's own deriver of a live-session conf; it writes `TMP/dosbox-x-mcp.conf`.
CONF_SCRIPT = Path("SCRIPTS/dosbox-x-mcp-conf.sh")
#: Mode 13h: a 25.175 MHz dot clock over an 800 x 449 raster.
RATE_HZ = 25_175_000 / (800 * 449)
#: The keys the PC port reads for its first player (`Get_Control`).
INPUTS = {action: Press("send_keys", {"keys": [key]})
          for action, key in (("COIN", "tab"), ("START", "1"), ("RIGHT", "right"),
                              ("FIRE1", "space"), ("UP", "up"))}
#: The reference the recording must equal: the same build mixes other samples on Windows, the
#: same ones run after run.
SOUND = "music-win32.wav" if sys.platform == "win32" else "music.wav"
#: Long enough for DOS to boot and EXEC the game, which is then in its attract.
BOOT_MS = 2000
#: The reader's copy of the game is where this host keeps things; the replies that name it are
#: hidden in the transcript.
VOLATILE_GAME = {**VOLATILE,
                 "conf": "where the reader's copy of the game keeps its derived conf",
                 "state_dir": "a directory in the session's own temporary directory",
                 "window": "the host's display and the window it fits",
                 "file": "where the reader's copy of the game keeps its store",
                 "path": "a file inside the reader's copy of the game"}


def game(run: Run) -> Path:
    return checkout(run)


def checked(run: Run) -> str:
    return precheck(run) or missing_under(
        run, (EXE, MAP, PROFILE, SCREEN_MAP, SCRIPT, CONF_SCRIPT),
        "the reader's copy of the game (its EXES/, its .scry/ and its SCRIPTS/)")


def boot(run: Run) -> dict[str, Any]:
    """The game's own conf, derived by its own script, then the profile that names it."""
    conf_derived(run, CONF_SCRIPT)
    return {"profile": str(game(run) / PROFILE), "shared": True,
            "captures_dir": str(run.dir / "lineup-captures")}


def at(run: Run) -> Path:
    """The game's screen map, in the same checkout the profile boots from."""
    return game(run) / SCREEN_MAP


def played(reply: Reply, run: Run) -> str:
    """Every step of the document the game declares ran, and each check it carries held."""
    doc = recording.read_document(str(game(run) / SCRIPT))
    steps = doc["steps"]
    expect(reply.get("steps_completed") == len(steps),
           f"{reply.get('steps_completed')} of {len(steps)} steps ran: "
           f"{reply.get('note') or reply}")
    held = sum(bool(step.get(recording.RECORDED)) for step in steps)
    expect(reply.get("held") == held, f"{reply.get('held')} steps held, the document records "
                                      f"{held}")
    return f"{len(steps)} steps of the game's own document, {held} holding to it"


def steps() -> list[Step]:
    """The platform's boot, the game's map, the game's own script, then the epilogue."""
    return [*BINDING.boot,
            map_load("map", at),
            Step("script", "perform",
                 lambda run: {"path": str(game(run) / SCRIPT), "summaries": True}, played,
                 highlight=("`perform` replays the script the game's own `.scry/perform/` "
                            "declares, in one call: the same symbols, screens and inputs, each "
                            "step held to what the document records.")),
            *lineup.epilogue(BINDING)]


BINDING = Binding(
    platform="dosbox-x",
    boot=[Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
               volatile={"summary": "it carries how long the debugger took to answer",
                         "conf": "where the reader's copy of the game keeps its derived conf",
                         "name": "where the reader's copy of the game keeps its profile",
                         "held": "where the reader's copy of the game keeps its symbol table"}),
          Step("boot", "run_for", {"milliseconds": BOOT_MS, "seconds": 120}, map_placed)],
    inputs=INPUTS, rate_hz=RATE_HZ, sound=HERE / SOUND, map=at, volatile=INPUT_TIMING)

DEMO = Demo(
    name="lineup", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=steps(),
    capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"cwd"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE_GAME,
    host_args={"cwd": "the reader's copy of the game, wherever it was cloned",
               "profile": "the reader's copy of the game, wherever it was cloned",
               "path": "a file of the reader's copy of the game",
               "captures_dir": "the run's own directory"})

if __name__ == "__main__":
    isolated_store("lineup")
    sys.exit(main(DEMO))
