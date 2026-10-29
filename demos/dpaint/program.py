"""What both Deluxe Paint demos share: the release they were written for, the checks before a
run, their first steps, a drag, and their declaration."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Reply, Run, Step
from scry_core.verdict import Invalid

from demos import host
from demos.host import VOLATILE, expect

ROOT = Path(__file__).resolve().parents[2]
#: Deluxe Paint II v1.0's `DP.EXE`, the 1988 release on one 720k disk.
DP_SHA256 = "ab40db116de1235e330e7df398b4b90425925972c2553775e997c9aa25ae3a4b"
#: Retraces from the start to the painting screen, with the program loaded and drawn.
BOOT_FRAMES = 400
WAIT_S = 60


def copy_check(run: Run) -> str:
    """Why the program cannot be run: no `--cwd`, a relative one, no `DP.EXE` there, or
    another build's."""
    where = run.options.get("cwd")
    if not where:
        return ("pass --cwd with the directory holding Deluxe Paint II's DP.EXE; this "
                "repository carries none of the program")
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


def click(target: str, action: str = "") -> dict[str, Any]:
    """A click on control `target`, or with `action` a press or a release there."""
    return {"op": "send_mouse", "target": target, "button": "left",
            **({"action": action} if action else {})}


def drag(start: tuple[int, int], end: tuple[int, int]) -> list[dict[str, Any]]:
    """A drag as Deluxe Paint takes one: press, move, release, in one call."""
    return [{"op": "send_mouse", "x": start[0], "y": start[1], "button": "left",
             "action": "drag", "to_x": end[0], "to_y": end[1]}]


def opening(boot: Callable[[Run], dict[str, Any]]) -> list[Step]:
    """Both Deluxe Paint demos' first steps: the session, then the program up and drawn."""
    return [Step("start", "start", boot, started, options=frozenset({"binary", "cwd"}),
                 volatile={"summary": "it carries how long the debugger took to answer"}),
            Step("loaded", "run_for", {"frames": BOOT_FRAMES, "seconds": WAIT_S}, loaded)]


def declared(name: str, here: Path, steps: list[Step]) -> Demo:
    """A Deluxe Paint demo: run from the directory `--cwd` names, refused on any other build."""
    return Demo(
        name=name, root=ROOT, server=[sys.executable, str(ROOT / "dosbox_x_server.py")],
        readme=here / "README.md", steps=steps,
        capture=lambda run: run.dir / "screen.png",
        offers=frozenset({"cwd"}), precheck=precheck,
        host_args={"cwd": "the directory holding the program"},
        volatile=VOLATILE)
