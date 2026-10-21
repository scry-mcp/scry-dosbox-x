"""The working copies one job of a pooled live run takes before anything else is imported.

DOSBox-X's debugger writes its own files under fixed names (`DEBUGGER_FILES`) into the
emulator's working directory, so two sessions on one directory read and refuse each other's,
and tests that pass alone fail side by side. A job that runs beside others therefore works on
copies of its own of the package's guests, of the bricks demo and of the bench, in the layout
the confs mount relative to (`tests/guest` and `demos/bricks` beside `guest`). Copies and not
links: a DOS program that writes into its own files must not reach the originals. They are taken
when this module is first imported, which every module that reads where the guests are does
before it reads it.

THE PARENT REMOVES THEM, never the job: a job SIGKILLed (a pool's bound, an OOM) runs none of
its own exit code, so its copies go in the directory the pooled run made for it (`PRIVATE_VAR`)
and the run removes it as the job ends, however it ended (`Copies`).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

#: A job's private directory, made by its pooled run: set, the job takes its copies there.
PRIVATE_VAR = "DOSBOX_X_LIVE_PRIVATE"
GUEST_VAR = "DOSBOX_X_LIVE_GUEST_DIR"
BRICKS_VAR = "DOSBOX_X_LIVE_BRICKS_DIR"
BENCH_VAR = "DOSBOX_X_LIVE_BENCH"
#: The files the debugger writes into its working directory under fixed names (`MCPDUMP.BIN` is
#: the dump this server names; a build that ignores the name writes `MEMDUMP.BIN`): a copy never
#: takes one an earlier run left behind.
DEBUGGER_FILES = ("SYMS.BIN", "SYMSBK.BIN", "MEMDUMP.BIN", "MCPDUMP.BIN")
REPO = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = Path.home() / ".local" / "share" / "scry-bench" / "dosbox-x"


def guest_dir() -> Path:
    """The package's guest directory this process works in: its own copy in a pooled job."""
    held = os.environ.get(GUEST_VAR, "")
    return Path(held) if held else REPO / "tests" / "guest"


def bricks_dir() -> Path:
    """The bricks demo's directory this process starts its sessions in: its own copy in a
    pooled job (`take_private_copies`)."""
    held = os.environ.get(BRICKS_VAR, "")
    return Path(held) if held else REPO / "demos" / "bricks"


@dataclass(frozen=True)
class Copies:
    """A pooled run's place for its jobs' copies: `env(name)` is what the job named `name` adds
    to its environment to take them there, and `ended(name)` removes them, from the pool's
    hook as that job ends, so they never pile up for the length of the run."""
    place: Path

    def env(self, name: str) -> dict[str, str]:
        return {PRIVATE_VAR: str(self.place / name)}

    def ended(self, name: str) -> None:
        shutil.rmtree(self.place / name, ignore_errors=True)


@contextlib.contextmanager
def copies_of_jobs() -> Iterator[Copies]:
    """The run's `Copies`, and whatever a job left there removed when the block ends."""
    # RESOLVED, as the server resolves every path it is given: the temporary directory is
    # reached through a link on macOS, and a cell comparing a path the server returns with an
    # unresolved one would fail on the spelling.
    place = Path(tempfile.mkdtemp(prefix="dosbox-x-live-job-")).resolve()
    try:
        yield Copies(place)
    finally:
        shutil.rmtree(place, ignore_errors=True)


def take_private_copies() -> None:
    """In a job the pooled run marked (`PRIVATE_VAR`, the directory it made for this job), copy
    the guests, the bricks demo and the bench there and point this process at the copies, once;
    anywhere else, nothing."""
    if not os.environ.get(PRIVATE_VAR) or (os.environ.get(GUEST_VAR)
                                            and os.environ.get(BRICKS_VAR)):
        return
    root = Path(os.environ[PRIVATE_VAR])
    if not root.is_absolute():
        raise SystemExit(f"{PRIVATE_VAR}={root} is not the absolute directory a pooled run "
                         "makes for its job")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "tests" / "guest", root / "tests" / "guest")
    shutil.copytree(REPO / "guest", root / "guest")
    shutil.copytree(REPO / "demos" / "bricks", root / "demos" / "bricks",
                    ignore=shutil.ignore_patterns("__pycache__", *DEBUGGER_FILES))
    os.environ[GUEST_VAR] = str(root / "tests" / "guest")
    os.environ[BRICKS_VAR] = str(root / "demos" / "bricks")
    bench = Path(os.environ.get(BENCH_VAR, "") or DEFAULT_BENCH).expanduser()
    if bench.is_dir():
        shutil.copytree(bench, root / "bench", symlinks=True)
        os.environ[BENCH_VAR] = str(root / "bench")


take_private_copies()
