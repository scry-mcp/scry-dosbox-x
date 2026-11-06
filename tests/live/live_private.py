"""Per-job copies of the guests, bricks demo and bench, taken at first import.

The debugger's fixed-name files collide between sessions in one directory. The parent removes
the copies (`Copies`): a SIGKILLed job runs no exit code.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PRIVATE_VAR = "DOSBOX_X_LIVE_PRIVATE"
GUEST_VAR = "DOSBOX_X_LIVE_GUEST_DIR"
BRICKS_VAR = "DOSBOX_X_LIVE_BRICKS_DIR"
BENCH_VAR = "DOSBOX_X_LIVE_BENCH"
DEBUGGER_FILES = ("SYMS.BIN", "SYMSBK.BIN", "MEMDUMP.BIN", "MCPDUMP.BIN")
REPO = Path(__file__).resolve().parents[2]
DEFAULT_BENCH = Path.home() / ".local" / "share" / "scry-bench" / "dosbox-x"


def guest_dir() -> Path:
    held = os.environ.get(GUEST_VAR, "")
    return Path(held) if held else REPO / "tests" / "guest"


def bricks_dir() -> Path:
    held = os.environ.get(BRICKS_VAR, "")
    return Path(held) if held else REPO / "demos" / "bricks"


@dataclass(frozen=True)
class Copies:
    place: Path

    def env(self, name: str) -> dict[str, str]:
        return {PRIVATE_VAR: str(self.place / name)}

    def ended(self, name: str) -> None:
        shutil.rmtree(self.place / name, ignore_errors=True)


@contextlib.contextmanager
def copies_of_jobs() -> Iterator[Copies]:
    # Resolved: macOS temp is behind a link, and cells compare path spellings.
    place = Path(tempfile.mkdtemp(prefix="dosbox-x-live-job-")).resolve()
    try:
        yield Copies(place)
    finally:
        shutil.rmtree(place, ignore_errors=True)


def take_private_copies() -> None:
    """In a pooled job, copy the guests, bricks and bench and point at the copies."""
    if not os.environ.get(PRIVATE_VAR):
        return
    root = Path(os.environ[PRIVATE_VAR])
    if not root.is_absolute():
        raise SystemExit(f"{PRIVATE_VAR}={root} is not the absolute directory a pooled run "
                         "makes for its job")
    # A pair already under this job's own root is done; the repository's is not.
    held = (os.environ.get(GUEST_VAR, ""), os.environ.get(BRICKS_VAR, ""))
    if all(here and Path(here).is_relative_to(root) for here in held):
        return
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "tests" / "guest", root / "tests" / "guest")
    shutil.copytree(REPO / "src" / "scry_dosbox_x" / "guest",
                    root / "src" / "scry_dosbox_x" / "guest")
    shutil.copytree(REPO / "demos" / "bricks", root / "demos" / "bricks",
                    ignore=shutil.ignore_patterns("__pycache__", *DEBUGGER_FILES))
    os.environ[GUEST_VAR] = str(root / "tests" / "guest")
    os.environ[BRICKS_VAR] = str(root / "demos" / "bricks")
    bench = Path(os.environ.get(BENCH_VAR, "") or DEFAULT_BENCH).expanduser()
    if bench.is_dir():
        shutil.copytree(bench, root / "bench", symlinks=True)
        os.environ[BENCH_VAR] = str(root / "bench")


take_private_copies()
