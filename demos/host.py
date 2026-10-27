"""What the demos share: where their window opens, whether this host can start DOSBox-X, what
differs between two honest runs, a declaration store of each run's own, and the checks more than
one demo makes."""

from __future__ import annotations

import atexit
import functools
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from scry_core import live_host
from scry_core import placement as window
from scry_core.demo import Reply, Run, StepFailed

import dosbox_binary


def display(run: Run) -> str:
    return "main" if run.options.get("shared") else "secondary"


@functools.cache
def unplaced(where: str) -> str:
    """Why the placement helper cannot open the window on `where`, or ''. A run nobody watches
    is never opened on top of the reader's work."""
    placed = window.ask("dosbox", True, where)
    if placed.flags is None:
        return placed.why
    if not placed.flags and where == "secondary":
        return ("the placement helper has nowhere to put a window away from your work (one "
                "display); pass --shared if you are watching")
    return ""


def precheck(run: Run) -> str:
    binary = run.options.get("binary")
    if binary and not Path(binary).expanduser().is_absolute():
        return f"the server takes absolute or ~-led paths only: --binary {binary}"
    if why := unplaced(display(run)):
        return why
    argv = dosbox_binary.canary_for(binary or "")
    return live_host.canary(argv) if argv else ""


#: Reply keys whose values differ between two honest runs on any host, hidden in every demo's
#: transcript.
VOLATILE = {"argv": "the emulator's command line, which carries the host's window placement",
            "elapsed_s": "wall-clock time since the session started",
            "waited_s": "wall-clock time a wait took",
            "ready_after_s": "wall-clock time the debugger took to answer",
            "binary": "where the host installed DOSBox-X",
            "mark": "a byte position in the session's log, which also holds the debugger's "
                    "answers to as many polls as the host's clock let a wait send",
            "input_port": "the free port the host picked for the input route",
            "binary_origin": "how the host's DOSBox-X was found",
            "version": "the host's DOSBox-X build",
            "output": "what the debugger printed for the command, which the server says to "
                      "read a stop from and never a value",
            "output_chars": "the length of that output",
            "ran_path": "a file in the session's own temporary directory",
            "replies_path": "a file in the session's own temporary directory"}


def isolated_store(demo: str) -> None:
    """The server keeps breakpoints and watches on disk, keyed by the conf, and re-arms them on
    the next start: a run that failed half-way would arm its declarations for the next one. So
    each run gets a store of its own, gone when it ends."""
    store = tempfile.mkdtemp(prefix=f"{demo}-demo-state-")
    atexit.register(shutil.rmtree, store, ignore_errors=True)
    os.environ["XDG_STATE_HOME"] = store


#: Counts an input step reports that depend on when the host delivered the input, not on what
#: the game did with it.
INPUT_TIMING = {key: "it depends on when the host delivered the input"
                for key in ("lines_before", "seen_before_waiting", "lines_total", "lines_written",
                            "since_mark")}


def expect(holds: bool, why: str) -> None:
    if not holds:
        raise StepFailed(why)


def seen(what: str) -> Any:
    def check(reply: Reply, run: Run) -> str:
        expect(reply["verify"]["seen"] is True, f"verify {reply['verify']}")
        return what
    return check


def pictured(reply: Reply, run: Run) -> str:
    expect(Path(reply["image"]["path"]).is_file(), f"no picture at {reply['image']['path']}")
    return f"mode {reply['vga_mode']}, {reply['width']}x{reply['height']} by palette index"


def loaded(reply: Reply, run: Run) -> str:
    expect(reply["kept"] == reply["parsed"] > 0, f"{reply['kept']} of {reply['parsed']} kept")
    return f"{reply['kept']} symbols placed at base {reply['base']:#x}"


def started(reply: Reply, run: Run) -> str:
    watched = "shared" if reply.get("shared", False) else "headless"
    return f"{watched} DOSBox-X, parked at the debugger before DOS boots"


def symbols_at(table: Path) -> Any:
    """`symbols_load`'s arguments for a table of offsets from the program's segment, placed at
    the segment the `ready` step stopped in: its base is that segment * 16."""
    def args(run: Run) -> dict[str, Any]:
        cs = int(str(run.replies["ready"]["pc"]).split(":")[0], 16)
        return {"path": table, "base": f"{cs * 16:x}"}
    return args
