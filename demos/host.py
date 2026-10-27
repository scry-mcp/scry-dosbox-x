"""What the demos share: where their window opens, and whether this host can start DOSBox-X."""

from __future__ import annotations

import functools
from pathlib import Path

from scry_core import live_host
from scry_core import placement as window
from scry_core.demo import Run

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
