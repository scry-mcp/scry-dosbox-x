"""The ReChip! demo on DOSBox-X: the program's own `.scry/` boots its DEV build, and its log says
what the keys did. `--help` says how to run it. The program is the reader's checkout (`--cwd`),
built; nothing of it is in this repository.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scry_core.demo import DISPLAY, Demo, Loop, Reply, Run, Step, expect, main, window_args

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    NORMAL_CORE,
    VOLATILE,
    checkout,
    isolated_store,
    missing_under,
    pictured,
    precheck,
    quit_cleanly,
    seen,
    started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: What the checkout holds once `make mcp-conf` ran: the recipe, the DEV build and the conf
#: the recipe names.
PROFILE = Path(".scry/start/dev.json")
SYMBOLS = Path("build/RECHIPD.SYM")
BUILT = (Path("build/RECHIPD.EXE"), Path("build/mcp.conf"), SYMBOLS)
#: The warning button's two looks.
SCREEN_MAP = HERE / "rechip-screen-map.json"
#: The program's 100 Hz counter, and how it pulses the warning button: lit through each odd
#: `PULSE_MS` of it, dark through each even one.
TICKS = "_g_ticks"
TICK_MS = 10
PULSE_MS = 400
#: The lines the DEV build writes to its E9 channel (the program's own rule names them): the
#: app is up and the song sounds; a key reached the app; the transport toggled; the quit confirm.
SOUNDING = r"PERF  \. audio play=1"
PAUSED = r"ACT   \. play=0"
REWOUND = r"ACT   \. rewind"
#: The report the program writes once a second of its own time.
REPORT = r"PERF  \. fps="
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
              "cpu_mode": "the mode at that instant", "summary": "it names the stop's place",
              "cause": "it names the address the stop landed at"}
#: What a stop the host placed says only sometimes: the server adds `note` where the place needs
#: a word (a ROM handler the program called into), and where the stop lands is the host's.
STOP_NOTE = {"note": "it comes only when the stop landed in a ROM handler, which is the host's"}
#: What a run from the stop reports that follows where the host stopped it.
RUN_SPAN = {key: "it counts from the stop, which landed when the host got there"
            for key in ("polls", "emulated_before_s", "emulated_after_s", "frame_before",
                        "frame_after", "cycles", "stop_seq", "summary")}
#: What the wait for the dark look reports that the host decides.
WAIT_PLACE = {**STOP_PLACE, **RUN_SPAN, "waited_s": "wall-clock time the wait took"}


def checked(run: Run) -> str:
    return precheck(run) or missing_under(
        run, (PROFILE, *BUILT), "the reader's checkout of ReChip!, after `make mcp-conf`")


def boot(run: Run) -> dict[str, Any]:
    return {**window_args(run), "profile": str(checkout(run) / PROFILE),
            "symbols": str(checkout(run) / SYMBOLS), "flags": NORMAL_CORE,
            "captures_dir": str(run.dir / "rechip-captures")}


def next_report(run: Run) -> dict[str, Any]:
    """The next report written past where the log ends now. The playhead is drawn from the audio
    already queued, so for a moment after the rewind it still shows where the pause landed; the
    second report after the rewind comes a second of the program's time later, long past that
    queue, and the playhead is at the first row."""
    recipe = json.loads((checkout(run) / PROFILE).read_text(encoding="utf-8"))
    log = Path(recipe["logfile"].replace("${root}", str(checkout(run))))
    return {"pattern": REPORT, "channel": "guest", "seconds": 10,
            "since_mark": log.stat().st_size}


def into_lit(run: Run) -> dict[str, Any]:
    """Run to the middle of the next lit half of the pulse, so the wait for the dark look always
    runs to its first frame, wherever in the pulse the stop landed."""
    now = int.from_bytes(bytes.fromhex(run.replies["ticks"]["hex"]), "little") * TICK_MS
    half = now // PULSE_MS
    lit = half + (2 if half % 2 else 1)
    return {"milliseconds": lit * PULSE_MS + PULSE_MS // 2 - now, "seconds": 10}


def on_look(name: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply.get("screen") == name, f"the screen is not {name}: {dict(reply)}")
        return f"the warning button shows {name}"
    return check


def released(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["session"].get("running") is True,
               f"the guest did not run: {reply['session']}")
        return what
    return check


def targeted(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}: {reply.get('note')}")
        return what
    return check


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "cwd", "display"}),
         volatile={"summary": "it carries how long the debugger took to answer",
                   "conf": "where the reader's checkout keeps its derived conf",
                   "name": "where the reader's checkout keeps its profile",
                   "held": "where the reader's checkout keeps its symbol table",
                   "against": "where the reader's checkout keeps its build"},
         highlight=("`start(profile=...)` boots from the recipe the program's own repository "
                    "declares: the line `make mcp-conf` prints, the DEV build opening the demo "
                    "song unattended, the conf with its boot line removed, the E9 log. The call "
                    "gives only what is the run's own, and the reply says which keys the recipe "
                    "filled.")),
    Step("run", "resume", {"seconds": 0},
         released("DOS boots and the autoexec hands over to the program")),
    Step("sounding", "log_wait", {"pattern": SOUNDING, "channel": "guest", "seconds": WAIT_S},
         targeted("the app is up and the song sounds"), volatile=LOG_TIMING,
         highlight=("The program's own log says when it is up and when the song sounds, two "
                    "different lines: `log_wait` on the guest channel waits for the second, on "
                    "a running machine.")),
    Step("pause", "send_keys", {"keys": ["space"], "expect": "key down SPACE", "seconds": 10},
         seen("space reached the app"), volatile=KEY_TIMING,
         highlight=("`send_keys` with `expect` proves the key reached the application, not "
                    "only that the host sent one: the program logs every key it takes, by "
                    "name.")),
    Step("paused", "log_wait", {"pattern": PAUSED, "channel": "guest", "seconds": 10},
         targeted("the transport stopped"), volatile=LOG_TIMING),
    Step("rewind", "send_keys", {"keys": ["home"], "expect": REWOUND, "seconds": 10},
         seen("home put the song back at its first row"), volatile=KEY_TIMING,
         highlight=("Where the pause lands is the host's, so the still is not taken there: "
                    "home rewinds the paused song to its first row and the program logs it.")),
    Step("report", "log_wait", next_report, targeted("the program reported after the rewind"),
         volatile=LOG_TIMING),
    Step("settled", "log_wait", next_report,
         targeted("a second report: the playhead is at the first row"), volatile=LOG_TIMING),
    Step("hold", "stop", {"until": "protected"},
         lambda reply, run: "the machine stopped in the program, its symbols placed",
         volatile={**STOP_PLACE,
                   "path": "where the reader's checkout keeps its symbol table",
                   "runs_to_protected": "how many short runs reached the program, which "
                                        "follows where the host stopped it"},
         optional=STOP_NOTE),
    Step("ticks", "read_memory", {"ref": TICKS, "length": 4},
         lambda reply, run: "the program's own counter, which sets the pulse",
         volatile={"hex": "the counter at the stop, which landed when the host got there",
                   "seg_off": "the selector the stop's data segment held, which follows where "
                              "the host stopped it",
                   "summary": "it quotes the counter"}),
    Step("into lit", "run_for", into_lit,
         lambda reply, run: "to the middle of the next lit half of the pulse",
         volatile={**STOP_PLACE, **RUN_SPAN}, optional=STOP_NOTE),
    Step("map", "screen_map_write", {"method": "load", "path": SCREEN_MAP},
         lambda reply, run: f"{reply['screens']} looks of the warning button"),
    Step("lit", "screen_map_find", {}, on_look("warning_lit")),
    # The edge logs nothing, so it is sampled retrace by retrace from the middle of a lit half.
    Step("dark", "screen_wait", {"screen": "warning_dark", "seconds": 10},
         targeted("the first frame it went dark"), volatile=WAIT_PLACE, optional=STOP_NOTE,
         highlight=("The warning button pulses on the program's own counter, so the picture "
                    "is taken on its edge: `read_memory` reads the counter, `run_for` goes to "
                    "the middle of the next lit half, and `screen_wait` on the mapped dark look "
                    "stops on its first frame.")),
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
               "captures_dir": "the run's own directory",
               "symbols": "the reader's checkout of the program, wherever it was cloned",
               "since_mark": "a byte position in the log, where it ended before the wait: how "
                             "much the program wrote is the host's pace",
               "milliseconds": "how far the stop was from the pulse's next lit half, which "
                               "follows where the host stopped it"})

if __name__ == "__main__":
    isolated_store("rechip")
    sys.exit(main(DEMO))
