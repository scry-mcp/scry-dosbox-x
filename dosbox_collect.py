"""Files the emulator wrote where it runs, collected to where the caller asked for them: judged
before anything moves, never over somebody else's, and none left behind."""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from scry_core.reply_contract import Invalid

import dosbox_paths as paths


def _same_place(dest: Path, other: Path, *, inside: bool = True) -> bool:
    """Is `dest` the same file as `other`, or inside it, ON THIS FILESYSTEM? With
    `inside=False`, only the same file.

    IT IS NOT `==` AND `in .parents`, which compare path STRINGS over an unnormalised
    path. The hazard is a filesystem property -- whether `dest` is, or lies under, a place
    the debugger writes -- and spellings that are the same file escaped it, each
    reproducing the session-poisoning the guard exists to prevent:

    * CASE, on a case-folding filesystem. `MemDump.bin` is not `memdump.bin` to `==`
      and is the same file to APFS, which is the default on the platform every
      measurement in this package was taken on. `Session._memdump_candidates` already reasons
      about this in its own docstring and enumerates two spellings; the filesystem
      accepts all 2^11.
    * SYMLINKS. The working directory reached by two names gives two unequal paths.

    `resolve()` settles links (a relative `dest` never reaches here: `dosbox_paths` refuses
    it); the fold is compared
    explicitly because `resolve()` does not canonicalise case on macOS. Over-refusing
    (`cwd/memdump.bin/../d.bin`, which really resolves elsewhere) is not a risk here:
    `resolve` normalises `..` before the comparison.
    """
    here, there = dest.resolve(), other.resolve()
    if here == there or (inside and there in here.parents):
        return True
    # The fold, for a filesystem that has one. A separator is required after the
    # prefix so `/a/memdump.bin2` is not read as living inside `/a/memdump.bin`.
    low, prefix = str(here).casefold(), str(there).casefold()
    return low == prefix or (inside and low.startswith(prefix + os.sep))


def judge_collection(dest: Path, cwd: Path, written: list[Path], what: str) -> None:
    """Where a file the DEBUGGER writes (`what`: a dump, a trace) may be moved to, judged before
    the debugger is asked anything: not directly in the emulator's working directory, where the
    debugger drops its own file and a collected one cannot be told from a leftover (a
    subdirectory, a project's `TMP/`, carries no such hazard), and not, nor inside, any of the
    `written` places the debugger writes: a dump collected into the place it is collected FROM
    cannot be told from the leftover the next call refuses."""
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
    """A file already sitting where the debugger writes is somebody's, never this call's: it is
    REFUSED, never read or deleted, because the first of those places is the emulator's working
    directory, which is somebody's project, and an unlink that failed would hand the leftover
    back as this call's file. A dangling link is something there too: the debugger would write
    through it, onto whatever it names."""
    present = [c for c in written if paths.taken(c)]
    if present:
        raise Invalid("bad_argument",
            f"a {what} file is already sitting at {[str(c) for c in present]}. It is not this "
            f"{what} and this will not delete it: move it aside and ask again. The first of "
            f"those paths is the emulator's working directory, which is somebody's project")


def collect(source: Path, dest: Path, what: str) -> Path:
    """The debugger's file moved from where it wrote it to `dest`. `os.replace` cannot cross
    filesystems and `dest` is the caller's, so a move to another volume falls back to a copy and
    an unlink rather than leaving by a bare OSError."""
    try:
        source.replace(dest)
    except OSError as exc:
        try:
            shutil.copyfile(source, dest)
            source.unlink()
        except OSError as exc2:
            # A copy cut short is this call's and would be refused as somebody's next time.
            with contextlib.suppress(OSError):
                dest.unlink()
            raise Invalid("host_failed", f"the {what} was written to {source} and could not be "
                          f"moved to {dest}: {exc!r}, then {exc2!r}") from None
    return dest
