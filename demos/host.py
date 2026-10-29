"""What the demos share: whether this host can start DOSBox-X, what differs between two honest
runs, a declaration store of each run's own, and the checks more than
one demo makes."""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import live_host
from scry_core.demo import Reply, Run, StepFailed

from scry_dosbox_x import binary as dosbox_binary


def precheck(run: Run) -> str:
    binary = run.options.get("binary")
    if binary and not Path(binary).expanduser().is_absolute():
        return f"the server takes absolute or ~-led paths only: --binary {binary}"
    argv = dosbox_binary.canary_for(binary or "")
    return live_host.canary(argv) if argv else ""


#: Reply keys whose values differ between two honest runs on any host, hidden in every demo's
#: transcript.
VOLATILE = {"argv": "the emulator's command line, which ends with the host's own arguments",
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


def run_lengths(pixels: bytes) -> list[tuple[int, int]]:
    """A row of pixels as (colour, how many) runs."""
    out: list[tuple[int, int]] = []
    for b in pixels:
        if out and out[-1][0] == b:
            out[-1] = (b, out[-1][1] + 1)
        else:
            out.append((b, 1))
    return out


def crossing(colours: dict[str, int], pixels: Callable[[Reply], bytes],
             *spans: tuple[str, int]) -> Any:
    """A row, read by `pixels` off the reply, that crosses `colours` in this order, each run
    exactly as long as the geometry draws it: a shape a pixel short or shifted changes a
    length."""
    def check(reply: Reply, run: Run) -> str:
        want = [(colours[n], k) for n, k in spans]
        got = run_lengths(pixels(reply))
        expect(got == want, f"the row runs {got}, not {want}")
        return "the row reads " + ", then ".join(f"{n} x {k}" for n, k in spans)
    return check
