"""The X-COM Apocalypse demo on DOSBox-X: every file the game opens, read off its DOS calls.
`--help` says how to run it. The game is the reader's copy (`--cwd`); nothing of it is in this
repository.
"""

from __future__ import annotations

import hashlib
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
    expect,
    recording,
    window_args,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `demos` imports as it checks
from demos.host import (  # noqa: E402
    INPUT_TIMING,
    KEPT_ELSEWHERE,
    RETRACE_STOP,
    VOLATILE,
    checkout,
    isolated_store,
    missing_under,
    pictured,
    precheck,
    started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
#: The layers that exist for this demo: its calls, the keys and the mouse it sends.
#: The edition the demo was written against: the launcher and the CD image, as the game's own
#: installer leaves them. Another edition may lay its menus out elsewhere.
GAME = {Path("XCOMA/XCOMAPOC.EXE"):
        "123de1e6b94e0e75b01026820ba7528f63acd60acc62ad9b0793bf321187750e",
        Path("cd/X-COM Apocalypse.iso"):
        "6acb86ee7447e94cdc94fe8a7d089045b77da5debd197445f3d50c4b5c98ea44"}
#: The two menus by the signature of a button's label only each of them shows (Load Saved Game,
#: Superhuman), above where the game draws its pointer, and their buttons by name.
SCREEN_MAP = HERE / "xcom-screen-map.json"
#: How long a press is held: half a second of the game's frames.
HOLD_FRAMES = 35
#: The game has no symbols and no log of its own, but it finds every file by its exact name
#: before it opens it, so the DOS channel says where it is: the intro film it plays from the CD,
#: the title screen an Esc skips to, the main menu's picture and the city's map once Novice is
#: clicked.
INTRO, TITLES, MAIN_MENU = "smk/intro1\\.smk", "ufodata/titles\\.pcx", "ufodata/b-setup\\.pcx"
#: Once the main menu is drawn the game opens its nine save slots, the last one
#: `tactgame.09`: after that it waits for the player, and a press is read.
MENU_READY = "savegame/tactgame\\.09"
CITY_MAP = "UFODATA/CITYMAP1"
CITY_BUILT = "UFODATA/CITYMAP1\\.BLD"
WAIT_S = 120
#: The session's bound: the run takes a few minutes of the host's time.
SESSION_S = 900
#: Retraces recorded once the city's map is read, and the last three seconds of them the loop
#: shows: the city once it is drawn.
CITY_FRAMES, CITY_SKIP, CITY_SHOWN = 900, 700, 200
VOLATILE_GAME = {**VOLATILE,
                 "conf_digest": "the conf names the reader's copy and the run's directory",
                 "state_dir": "a directory in the session's own temporary directory",
                 "dos_calls": "a file in the session's own temporary directory",
                 "logfile": "a file in the run's own directory",
                 "time_s": "the guest's clock when the call was made, which the host's load moves",
                 "returned_s": "the guest's clock when the call returned"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def checked(run: Run) -> str:
    why = precheck(run) or missing_under(
        run, tuple(GAME), "the reader's copy of the game (XCOMA/ and cd/ as installed)")
    if why:
        return why
    for part, want in GAME.items():
        got = digest(checkout(run) / part)
        if got != want:
            return f"{part.as_posix()} is another edition (sha256 {got}); the demo needs {want}"
    return ""


def conf(run: Run) -> Path:
    """The demo's conf with the reader's copy and the run's overlay filled in."""
    overlay = run.dir / "c-overlay"
    overlay.mkdir(parents=True, exist_ok=True)
    text = (HERE / "xcom.conf").read_text()
    for token, value in (("@GAME@", checkout(run)), ("@OVERLAY@", overlay)):
        expect(text.count(token) == 1, f"xcom.conf holds {token} {text.count(token)} times")
        text = text.replace(token, str(value))
    written = run.dir / "xcom.conf"
    written.write_text(text)
    return written


def boot(run: Run) -> dict[str, Any]:
    return {**window_args(run), "conf": str(conf(run)), "cwd": str(checkout(run)),
            "program": "XCOMAPOC.EXE", "dos_calls": True, "session_seconds": SESSION_S,
            "logfile": str(run.dir / "xcom.log"),
            "captures_dir": str(run.dir / "xcom-captures")}


def reached(what: str) -> Any:
    """The DOS call the wait was for arrived, the call it names quoted as the program made it."""
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}: {reply.get('note')}")
        call = reply["call"]
        return f"{what}: {call.get('file', '').strip() or call['name']}"
    return check


def posted(reply: Reply, run: Run) -> str:
    expect(reply["posted"] >= 1, f"nothing went in: {reply['summary']}")
    return "the input went in"


def clicked(reply: Reply, run: Run) -> str:
    expect(reply["driver_arrived"] is True, f"the pointer did not arrive: {reply['summary']}")
    return f"pressed at {reply['x']},{reply['y']}"


def found(screen: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["matched"] is True and reply["screen"] == screen,
               f"the screen is {reply.get('screen', 'none of the map')}, not {screen}")
        return f"{screen}, {len(reply['controls'])} controls"
    return check


def on_screen(screen: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verdict"] == "TARGET", f"verdict {reply['verdict']}: {reply.get('note')}")
        return f"{screen} on screen"
    return check


def shown_on(name: str, screen: str, **example: Any) -> Step:
    return Step(name, "screen_wait", {"screen": screen, "seconds": WAIT_S}, on_screen(screen),
                volatile={**LANDED,
                          "waited_s": "wall-clock time the wait took",
                          "already": "whether the screen was whole when the wait began, which "
                                     "the host's speed decides",
                          "sampled_every": "how often the wait sampled",
                          "retrace_pending": "whether a retrace stop is left armed"},
                optional=ROM_NOTE, **example)


def released(button: str) -> list[Step]:
    """The press held for `HOLD_FRAMES`, the input's own duration, then let go: the game reads
    the button when it gets to it, and a click shorter than that falls between two reads."""
    return [Step(f"{button} held", "run_for", {"frames": HOLD_FRAMES, "seconds": WAIT_S},
                 lambda reply, run: f"held for {HOLD_FRAMES} frames", volatile=LANDED,
                 optional=ROM_NOTE),
            Step(f"{button} up", "send_mouse", {"action": "up"},
                 lambda reply, run: "released", volatile={**LANDED, **INPUT_TIMING},
                 optional=ROM_NOTE)]


def looked_up(reply: Reply, run: Run) -> str:
    calls = reply["calls"]
    names = {c.get("file", "").strip() for c in calls}
    expect(len(calls) >= 50, f"only {len(calls)} FindFirst calls")
    expect(CITY_MAP in names, f"no FindFirst for {CITY_MAP}")
    return f"{len(calls)} FindFirst calls, one per file the game opened, {CITY_MAP} among them"


#: Where a stop lands, and so the retraces counted from it: the game runs free between the
#: demo's waits, so the host's speed decides how far it got.
LANDED = {**RETRACE_STOP, **{key: "a stop lands where the host's speed had the game, and the "
                                  "retraces counted from it follow"
                             for key in ("summary", "frame", "frame_before", "frame_after",
                                         "emulated_before_s", "emulated_after_s", "cpu_mode",
                                         "polls")}}
#: A stop that lands inside a BIOS handler the game called gets a note saying so; where it lands
#: is the host's speed's doing.
ROM_NOTE = {"note": "a stop that lands inside a BIOS handler says so, and where a stop lands "
                    "follows the host's speed"}
#: What a wait on the DOS channel shows that the host's speed moves.
WAITED = {
    "waited_s": "wall-clock time the wait took",
    "already": "whether the call was held when the wait began, which the host's speed decides",
    "arrived_during": "whether the call came while the wait polled, which the host's speed "
                      "decides",
    "lines_before": "the calls held when the wait began, which the host's speed moves",
    "lines_total": "the calls held when the wait answered, which the host's speed moves",
    "lines_examined": "the calls held when the wait answered, which the host's speed moves",
    "calls_dropped": "the oldest calls past the server's hold, which the host's speed moves"}


def waited(name: str, pattern: str, what: str, **example: Any) -> Step:
    return Step(name, "log_wait", {"channel": "dos", "pattern": pattern, "seconds": WAIT_S},
                reached(what), volatile={**WAITED, "call": "the guest's clock stamps the call",
                                         "summary": "it carries how long the wait took"},
                **example)


STEPS = [
    Step("start", "start", boot, started, options=frozenset({"binary", "display"}),
         volatile={"summary": "it names where the host installed DOSBox-X and how long the "
                              "debugger took to answer",
                   **KEPT_ELSEWHERE},
         title="Start the game with its DOS calls recorded",
         ask="Start X-COM Apocalypse from my copy, recording every INT 21h call it makes.",
         shown=("status", "shared"),
         reads=("With `dos_calls`, the emulator writes each INT 21h call to a file of the "
                "session's; the `log` tool reads it back on the `dos` channel.")),
    Step("run", "resume", {}, lambda reply, run: "the game runs"),
    waited("intro", INTRO, "the intro film plays from the CD"),
    Step("skip", "send_keys", {"keys": ["esc"]}, posted),
    waited("titles", TITLES, "the intro is skipped"),
    Step("skip again", "send_keys", {"keys": ["esc"]}, posted),
    waited("main menu", MAIN_MENU, "the main menu is on its way"),
    waited("menu ready", MENU_READY, "the main menu has looked at its save slots"),
    Step("held", "stop", {}, lambda reply, run: "stopped on the way to the main menu",
         volatile=LANDED, optional=ROM_NOTE),
    Step("map", "screen_map_write", {"method": "load", "path": SCREEN_MAP},
         lambda reply, run: f"{reply['screens']} screens, {reply['controls']} controls"),
    # The game paints its menus without a call that says it is done, so the wait samples the
    # retraces until the menu's own button is on screen: no symbol, log or polled place is left.
    shown_on("main menu drawn", "main_menu",
             title="Wait for a screen by its name",
             ask="Wait until the main menu is on screen.",
             shown=("verdict", "screen"),
             reads=("The screen map knows the main menu by the signature of its Load Saved Game "
                    "button; "
                    "the wait runs the machine retrace by retrace until it is on screen.")),
    Step("found menu", "screen_map_find", {}, found("main_menu")),
    Step("campaign", "send_mouse", {"target": "start_campaign", "action": "down"}, clicked,
         volatile={**LANDED, **INPUT_TIMING}, optional=ROM_NOTE,
         title="Press a button by its name",
         ask="Press Start Campaign Game.",
         shown=("target", "screen", "driver_arrived"),
         reads=("The map gives the button's place, so the press names the button, not the "
                "pixels it covers.")),
    *released("campaign"),
    shown_on("difficulty drawn", "difficulty"),
    Step("found difficulty", "screen_map_find", {}, found("difficulty")),
    Step("novice", "send_mouse", {"target": "novice", "action": "down"}, clicked,
         volatile={**LANDED, **INPUT_TIMING}, optional=ROM_NOTE),
    *released("novice"),
    Step("on", "resume", {}, lambda reply, run: "the game runs"),
    waited("city", CITY_BUILT, "the campaign is loading its city"),
    Step("stopped", "stop", {}, lambda reply, run: "stopped with the city on its way",
         volatile=LANDED, optional=ROM_NOTE),
    recording("drawn", CITY_FRAMES),
    Step("files", "log", {"channel": "dos", "pattern": "find first", "limit": 400}, looked_up,
         volatile={"calls": "each call carries the guest's clock, which the host's load moves",
                   "lines_total": "the calls held when the log was read, which the host's speed "
                                  "moves while the game runs"},
         title="List the files the game looked for",
         ask="Which files did the game look for with FindFirst while the campaign loaded?",
         shown=("summary",),
         reads=("The game opens each file through a FindFirst of its exact name, so the DOS "
                "channel lists every file it read, the CD's film and the city's map among "
                "them.")),
    Step("screen", "screen_view", lambda run: {"dest": run.dir / "screen.png"}, pictured),
    Step("close", "close", {}, lambda reply, run: f"closed: {reply['ended_by']}"),
]

DEMO = Demo(
    name="xcom", root=ROOT, server=[sys.executable, "-m", "scry_dosbox_x.server"],
    readme=HERE / "README.md", steps=STEPS,
    capture=lambda run: run.dir / "screen.png",
    moments=(Moment("stopped", "drawn",
                    "The city of a new campaign, started from the menus, in 640 x 480.",
                    skip=CITY_SKIP, frames=CITY_SHOWN),),
    alt="X-COM Apocalypse loading a new campaign, then its city",
    offers=frozenset({"cwd", "display"}), reads=frozenset({"cwd"}), precheck=checked,
    volatile=VOLATILE_GAME,
    host_args={"cwd": "the reader's copy of the game, wherever it was installed",
               "conf": "the run's own directory",
               "display": DISPLAY,
               "logfile": "the run's own directory",
               "captures_dir": "the run's own directory"})

if __name__ == "__main__":
    isolated_store("xcom")
    sys.exit(core.main(DEMO))
