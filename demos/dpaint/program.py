"""What both Deluxe Paint demos share: the release they were written for, the checks before a
run, their first steps, a drag, and their declaration."""

from __future__ import annotations

import hashlib
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from scry_core.demo import DISPLAY, Demo, Moment, Reply, Run, Step
from scry_core.verdict import Invalid

from demos import host
from demos.host import VOLATILE, expect

ROOT = Path(__file__).resolve().parents[2]
#: Deluxe Paint II v1.0's `DP.EXE`, the 1988 release on one 720k disk.
DP_SHA256 = "ab40db116de1235e330e7df398b4b90425925972c2553775e997c9aa25ae3a4b"
#: Where this release's DGROUP sits, in paragraphs past its load segment (the PSP's + 0x10): the
#: data segment every stop inside the program holds in DS.
DGROUP_PARAGRAPHS = 0x28C3
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
    expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}")
    stub = next((ln for ln in reply["e9"]["lines"] if "scry device=" in ln), "")
    if "motion=1" not in stub:
        raise Invalid("this DOSBox-X's input device takes no relative motion (the stub said "
                      f"{stub.split(': ', 1)[-1] or 'nothing'}), and Deluxe Paint draws a drag "
                      "from movement events: pass --binary with a build that carries it")
    return f"Deluxe Paint is up: the map names its screen {reply['screen']}"


def psp(reply: Reply) -> int:
    """`DP`'s PSP segment off a `machine_map` reply."""
    owners = {m["psp_seg"] for m in reply["mcbs"]
              if m.get("filename") == "DP" and m.get("notes") != "free"}
    expect(len(owners) == 1, f"DP's memory blocks name {sorted(owners)} as their PSP")
    return int(owners.pop(), 16)


def data_segment(reply: Reply) -> int:
    """The program's data segment off a `machine_map` reply: its load segment plus where this
    release keeps DGROUP."""
    return psp(reply) + 0x10 + DGROUP_PARAGRAPHS


def ds_segment(run: Run) -> int:
    return data_segment(run.replies["placed"])


def placed(reply: Reply, run: Run) -> str:
    return f"DP loaded with its PSP at {psp(reply):04X}, its data at {data_segment(reply):04X}"


def click(target: str, action: str = "") -> dict[str, Any]:
    """A click on control `target`, or with `action` a press or a release there."""
    return {"op": "send_mouse", "target": target, "button": "left",
            **({"action": action} if action else {})}


def drag(start: tuple[int, int], end: tuple[int, int]) -> list[dict[str, Any]]:
    """A drag as Deluxe Paint takes one: press, move, release, in one call."""
    return [{"op": "send_mouse", "x": start[0], "y": start[1], "button": "left",
             "action": "drag", "to_x": end[0], "to_y": end[1]}]


def opening(boot: Callable[[Run], dict[str, Any]], screen_map: Path, first: str) -> list[Step]:
    """Both Deluxe Paint demos' first steps: the session, the screen map, the program run until
    the map names its first screen, and where DOS loaded it. The program has no symbols and no
    log, and every place in it a stop could wait at runs hundreds of times a retrace (its loop
    polls), so the arrival is the screen itself, judged each retrace."""
    return [Step("start", "start", boot, started,
                 options=frozenset({"binary", "cwd", "display"}),
                 volatile={"summary": "it carries how long the debugger took to answer",
                           **host.KEPT_ELSEWHERE}),
            Step("map", "screen_map_write", {"method": "load", "path": screen_map},
                 lambda reply, run: f"{reply['screens']} screens and {reply['controls']} "
                                    "controls loaded"),
            Step("loaded", "screen_wait", {"screen": first, "seconds": WAIT_S}, loaded),
            Step("placed", "machine_map", {}, placed)]


def video(run: Run) -> Path:
    """Where the session records itself: Deluxe Paint draws inside the calls that drag, so its
    moments are stretches of the whole session's video."""
    return run.dir / "video"


def recorded(run: Run) -> dict[str, Any]:
    """`start`'s arguments for a session that records itself, into a folder emptied first."""
    shutil.rmtree(video(run), ignore_errors=True)
    return {"capture_video": True, "captures_dir": video(run)}


def counted(name: str) -> Step:
    """One retrace, whose reply counts the frame: where a moment of the loop begins or ends when
    the calls around it answer with summaries, which count none."""
    return Step(name, "run_for", {"frames": 1, "seconds": WAIT_S},
                lambda reply, run: f"frame {reply['frame']}",
                volatile={**host.RETRACE_STOP,
                          **{key: "it names the instruction or the clock a retrace stop lands "
                                  "on, which drift with the host's cycles"
                             for key in ("summary", "emulated_before_s", "emulated_after_s")}})


def declared(name: str, here: Path, steps: list[Step], moments: Sequence[Moment],
             alt: str) -> Demo:
    """A Deluxe Paint demo: run from the directory `--cwd` names, refused on any other build."""
    return Demo(
        name=name, root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
        readme=here / "README.md", steps=steps,
        capture=lambda run: run.dir / "screen.png", moments=moments, alt=alt, video=video,
        offers=frozenset({"cwd", "display"}), precheck=precheck,
        host_args={"cwd": "the directory holding the program", "display": DISPLAY,
                   "captures_dir": "the run's own directory"},
        volatile={**VOLATILE, **host.RETRACE_STOP})
