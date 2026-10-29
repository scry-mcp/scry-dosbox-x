
from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from scry_core.reply_contract import Invalid

from scry_dosbox_x import paths


def _same_place(dest: Path, other: Path, *, inside: bool = True) -> bool:
    """Same file as `other`, or inside it (`inside=False`: only the same file)?

    Resolved and case-folded: string `==` misses APFS case spellings and symlinks.
    """
    here, there = dest.resolve(), other.resolve()
    if here == there or (inside and there in here.parents):
        return True
    low, prefix = str(here).casefold(), str(there).casefold()
    return low == prefix or (inside and low.startswith(prefix + os.sep))


def judge_collection(dest: Path, cwd: Path, written: list[Path], what: str) -> None:
    """Refuse, before the debugger runs, a `dest` that cannot be told from its own leftover.

    Directly in `cwd`, or at or inside a `written` place.
    """
    if _same_place(dest.parent, cwd, inside=False):
        raise Invalid("bad_argument",
            f"{dest} is in {cwd}, the emulator's working directory, where the debugger writes "
            f"its own {what} file: name a path outside it, or in a subdirectory of it")
    for c in written:
        if _same_place(dest, c):
            raise Invalid("bad_argument",
                f"{dest} is, or is inside, {c}, which is where the debugger writes its own "
                f"file. Collecting a {what} into the place it is collected FROM cannot be told "
                f"from the leftover this refuses")


def refuse_leftover(written: list[Path], what: str) -> None:
    """Refuse, never delete, a file already at a `written` place: it is somebody's.

    A dangling link counts: the debugger would write through it.
    """
    present = [c for c in written if paths.taken(c)]
    if present:
        raise Invalid("bad_argument",
            f"a {what} file is already sitting at {[str(c) for c in present]}. It is not this "
            f"{what} and this will not delete it: move it aside and ask again. The first of "
            f"those paths is the emulator's working directory, which is somebody's project")


def collect(source: Path, dest: Path, what: str,
            release: Callable[[], None] | None = None) -> Path:
    """Move the debugger's file to `dest`, falling back to copy and unlink across volumes.

    `release` lets go of a file the debugger still holds: Windows copies an open file and
    refuses to delete it, so the copy is made, `release` called, and the delete retried."""
    try:
        source.replace(dest)
    except OSError as exc:
        try:
            shutil.copyfile(source, dest)
            try:
                source.unlink()
            except PermissionError:
                if release is None:
                    raise
                release()
                source.unlink()
        except OSError as exc2:
            # A partial copy would be refused as somebody's next time.
            with contextlib.suppress(OSError):
                dest.unlink()
            raise Invalid("host_failed", f"the {what} was written to {source} and could not be "
                          f"moved to {dest}: {exc!r}, then {exc2!r}") from None
    return dest
