"""The LineUp demo on DOSBox-X: `scry_core.games.lineup` bound to the PC port. `--help` says how
to run it. The game is the reader's copy (`--cwd`); nothing of it is in this repository.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step, StepFailed, main
from scry_core.game_demo import Binding, Press, elapsed
from scry_core.games import lineup

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    VOLATILE,
    isolated_store,
    loaded,
    precheck,
    started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: The program and its symbols, in the reader's copy of the game.
EXE, MAP = Path("EXES/LINEUP.EXE"), Path("EXES/LINEUP.MAP")
#: Mode 13h: a 25.175 MHz dot clock over an 800 x 449 raster.
RATE_HZ = 25_175_000 / (800 * 449)
#: The keys the PC port reads for its first player (`Get_Control`).
INPUTS = {action: Press("send_keys", {"keys": [key]})
          for action, key in (("COIN", "tab"), ("START", "1"), ("RIGHT", "right"),
                              ("FIRE1", "space"), ("UP", "up"))}
#: Long enough for DOS to boot and EXEC the game, which is then in its attract.
BOOT_MS = 2000
#: Where the video memory and the ROMs begin: no program is loaded at or above it.
ROM_SEGMENT = 0xA000


def game(run: Run) -> Path:
    return Path(run.options["cwd"]).expanduser()


def checked(run: Run) -> str:
    if why := precheck(run):
        return why
    cwd = run.options.get("cwd")
    if not cwd:
        return "pass --cwd, the directory holding LineUp's PC port (EXES/LINEUP.EXE and its map)"
    missing = [p.as_posix() for p in (EXE, MAP) if not (game(run) / p).is_file()]
    return f"no {' or '.join(missing)} under --cwd {cwd}" if missing else ""


def boot(run: Run) -> dict[str, Any]:
    """The conf, with this checkout's stub written in, in the run's own directory."""
    conf = run.dir / "lineup.conf"
    conf.write_text((HERE / "lineup.conf").read_text(encoding="utf-8").replace(
        "@GUEST@", str(ROOT / "guest")), encoding="utf-8")
    states = run.dir / "lineup-states"
    shutil.rmtree(states, ignore_errors=True)
    return {"conf": conf, "session_seconds": 900, "shared": True,
            "state_dir": states, "captures_dir": run.dir / "lineup-captures"}


def symbols(run: Run) -> dict[str, Any]:
    """The game's map, copied into the run, placed at the load segment the boot stopped in."""
    copy = run.dir / MAP.name
    shutil.copyfile(game(run) / MAP, copy)
    return {"path": copy, "base": f"{segment(run.replies['boot']) * 16:x}"}


def segment(reply: Reply) -> int:
    return int(str(reply["pc"]).split(":")[0], 16)


def in_game(reply: Reply, run: Run) -> str:
    """The boot's stop is in the program's own code, whose segment is where DOS loaded it: a
    stop in ROM (a BIOS call) would place every symbol at the ROM's segment."""
    booted = elapsed("booted")(reply, run)
    if segment(reply) >= ROM_SEGMENT:
        raise StepFailed(f"the boot stopped at {reply['pc']}, outside the program, so its "
                         "segment is not the one DOS loaded the game at")
    return f"{booted}: DOS running the game, loaded at segment {segment(reply):04X}"


BINDING = Binding(
    platform="dosbox-x",
    boot=[Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
               volatile={"summary": "it carries how long the debugger took to answer"}),
          Step("boot", "run_for", {"milliseconds": BOOT_MS, "seconds": 120}, in_game),
          Step("symbols", "symbols_load", symbols, loaded)],
    inputs=INPUTS, rate_hz=RATE_HZ, sound=HERE / "music.wav", volatile=INPUT_TIMING)

DEMO = Demo(
    name="lineup", root=ROOT, server=[sys.executable, str(ROOT / "dosbox_x_server.py")],
    readme=HERE / "README.md", steps=lineup.steps(BINDING),
    capture=lambda run: run.dir / "screen.png",
    offers=frozenset({"cwd"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE,
    host_args={"cwd": "the reader's copy of the game, wherever it was cloned"})


if __name__ == "__main__":
    isolated_store("lineup")
    sys.exit(main(DEMO))
