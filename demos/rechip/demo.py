"""The ReChip! demo on DOSBox-X: the program's own `.scry/` boots its DEV build, and its log says
what the keys did. `--help` says how to run it. The program is the reader's checkout (`--cwd`),
built; nothing of it is in this repository.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from scry_core.demo import Demo, Loop, Reply, Run, Step, expect, main

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    DISPLAY,
    INPUT_TIMING,
    VOLATILE,
    checkout,
    isolated_store,
    missing_under,
    pictured,
    precheck,
    quit_cleanly,
    seen,
    started,
    window,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: What the checkout holds once `make mcp-conf` ran: the recipe, the DEV build and the conf
#: the recipe names.
PROFILE = Path(".scry/start/dev.json")
BUILT = (Path("build/RECHIPD.EXE"), Path("build/mcp.conf"))
#: The lines the DEV build writes to its E9 channel (the program's own rule names them): the
#: app is up and the song sounds; a key reached the app; the transport toggled; the quit confirm.
SOUNDING = r"PERF  \. audio play=1"
PAUSED = r"ACT   \. play=0"
ASKED = r"ask opens"
CONFIRMED = r"ask res=1"
WAIT_S = 120
VOLATILE_PROGRAM = {**VOLATILE,
                    "conf": "where the reader's checkout keeps its derived conf",
                    "state_dir": "a directory in the session's own temporary directory",
                    "window": "the host's display and the window it fits",
                    "file": "where the reader's checkout keeps its store",
                    "conf_digest": "`make mcp-conf` writes the checkout's own paths into the "
                                   "conf"}
#: What a key's confirmation reports that the host decides: the input lands on a running program
#: when the host delivers it, and the line carries the program's own clock stamp of that moment.
KEY_TIMING = {**INPUT_TIMING, "line": "the program's own clock stamp on the line"}
#: What a wait on the log and a stop report that depends on when the host got there, not on
#: what the program did: the wall time, the line counts and the stamp, the stop's own place.
LOG_TIMING = {**INPUT_TIMING,
              "summary": "it carries how long the wait took",
              "waited_s": "wall-clock time the wait took",
              "line": "the program's own clock stamp on the line",
              "already": "whether the line was there before the wait began",
              "arrived_during": "how many lines arrived while waiting",
              "lines_examined": "how many lines were read"}
STOP_PLACE = {"pc": "where the program happened to be", "frame": "the frame the stop landed on",
              "regs": "the registers at that instant", "instruction": "the instruction there",
              "following": "the instructions after it", "e9": "the log's tail at that instant",
              "cpu_mode": "the mode at that instant", "summary": "it names the stop's place"}


def checked(run: Run) -> str:
    return precheck(run) or missing_under(
        run, (PROFILE, *BUILT), "the reader's checkout of ReChip!, after `make mcp-conf`")


def boot(run: Run) -> dict[str, Any]:
    return {**window(run), "profile": str(checkout(run) / PROFILE),
            "captures_dir": str(run.dir / "rechip-captures")}


def released(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["session"].get("running") is True,
               f"the guest did not run: {reply['session']}")
        return what
    return check


def logged(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}: {reply.get('note')}")
        return what
    return check


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer",
                   "conf": "where the reader's checkout keeps its derived conf",
                   "name": "where the reader's checkout keeps its profile"},
         highlight=("`start(profile=...)` boots from the recipe the program's own repository "
                    "declares: the line `make mcp-conf` prints, the DEV build opening the demo "
                    "song unattended, the conf with its boot line removed, the E9 log. The call "
                    "gives only what is the run's own, and the reply says which keys the recipe "
                    "filled.")),
    Step("run", "resume", {"seconds": 0},
         released("DOS boots and the autoexec hands over to the program")),
    Step("sounding", "log_wait", {"pattern": SOUNDING, "channel": "guest", "seconds": WAIT_S},
         logged("the app is up and the song sounds"), volatile=LOG_TIMING,
         highlight=("The program's own log says when it is up and when the song sounds, two "
                    "different lines: `log_wait` on the guest channel waits for the second, on "
                    "a running machine.")),
    Step("pause", "send_keys", {"keys": ["space"], "expect": "key down SPACE", "seconds": 10},
         seen("space reached the app"), volatile=KEY_TIMING,
         highlight=("`send_keys` with `expect` proves the key reached the application, not "
                    "only that the host sent one: the program logs every key it takes, by "
                    "name.")),
    Step("paused", "log_wait", {"pattern": PAUSED, "channel": "guest", "seconds": 10},
         logged("the transport stopped"), volatile=LOG_TIMING),
    Step("hold", "stop", {}, lambda reply, run: "the machine stopped", volatile=STOP_PLACE),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("go on", "resume", {"seconds": 0}, released("the program runs on")),
    Step("quit", "send_keys", {"keys": ["x"], "modifiers": ["alt"], "expect": ASKED,
                               "seconds": 10},
         seen("File, Quit: the song is dirty, so the confirm opened"), volatile=KEY_TIMING),
    Step("confirm", "send_keys", {"keys": ["right", "enter"], "expect": CONFIRMED,
                                  "seconds": 10},
         seen("Quit without saving"), volatile=KEY_TIMING,
         highlight=("The program is left by its own keys, and its log says which button the "
                    "confirm took, so the session closes over a guest that has quit rather "
                    "than one killed under a running program.")),
    Step("close", "close", {}, quit_cleanly),
]

DEMO = Demo(
    name="rechip", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png", loop=Loop("screen"),
    offers=frozenset({"cwd", "display"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE_PROGRAM,
    host_args={"cwd": "the reader's checkout of the program, wherever it was cloned",
               "display": DISPLAY,
               "profile": "the reader's checkout of the program, wherever it was cloned",
               "captures_dir": "the run's own directory"})

if __name__ == "__main__":
    isolated_store("rechip")
    sys.exit(main(DEMO))
