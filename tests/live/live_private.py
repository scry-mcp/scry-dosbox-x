"""The working copies one job of a pooled live run takes before anything else is imported.

DOSBox-X's debugger writes its own files under fixed names (`SYMS.BIN`, `SYMSBK.BIN`,
`MEMDUMP.BIN`) into the emulator's working directory, so two sessions on one guest directory
read and refuse each other's: measured, three live tests failed side by side that pass alone.
A job that runs beside others therefore works on copies of its own of the package's guests and
of the bench, in the layout the confs mount relative to (`tests/guest` beside `guest`), and
removes them when it ends. Copies and not links: a DOS program that writes into its own files
must not reach the originals. They are taken when this module is first imported, which every
module that reads where the guests are does before it reads it.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

PRIVATE_VAR = "DOSBOX_X_LIVE_PRIVATE"
GUEST_VAR = "DOSBOX_X_LIVE_GUEST_DIR"
BENCH_VAR = "DOSBOX_X_LIVE_BENCH"
REPO = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = Path.home() / ".local" / "share" / "scry-bench" / "dosbox-x"


def guest_dir() -> Path:
    """The package's guest directory this process works in: its own copy in a pooled job."""
    held = os.environ.get(GUEST_VAR, "")
    return Path(held) if held else REPO / "tests" / "guest"


def take_private_copies() -> None:
    """In a job the pooled run marked (`PRIVATE_VAR`), copy the guests and the bench and point
    this process at the copies, once; anywhere else, nothing."""
    if not os.environ.get(PRIVATE_VAR) or os.environ.get(GUEST_VAR):
        return
    # RESOLVED, as the server resolves every path it is given: the temporary directory is
    # reached through a link on macOS, and a cell comparing a path the server returns with an
    # unresolved one would fail on the spelling.
    root = Path(tempfile.mkdtemp(prefix="dosbox-x-live-job-")).resolve()
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    shutil.copytree(REPO / "tests" / "guest", root / "tests" / "guest")
    shutil.copytree(REPO / "guest", root / "guest")
    os.environ[GUEST_VAR] = str(root / "tests" / "guest")
    bench = Path(os.environ.get(BENCH_VAR, "") or DEFAULT_BENCH).expanduser()
    if bench.is_dir():
        shutil.copytree(bench, root / "bench", symlinks=True)
        os.environ[BENCH_VAR] = str(root / "bench")


take_private_copies()
