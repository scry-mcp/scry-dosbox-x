"""What this server asks of a path a caller gives it, around scry-core's one judge of a path
(`scry_core.judges.absolute`), which the media file tools use too.

EVERY PATH ARGUMENT IS ABSOLUTE OR LED BY `~`, which is expanded. A relative path is judged
against one directory and used in another: this server's own working directory is wherever the
client launched it, the emulator's is the session's `cwd`, and a path that means one thing to the
judge and another to the writer is checked against the wrong file. `~` is what a person types,
and no shell stands between a client and this argument to expand it, so the judge does.

THE SHAPE is judged before the session gate (a value as wrong with no machine as with one); THE
FILESYSTEM at the call, on the filesystem of that moment, since an earlier step of a list may
change it: a file the tool writes (`fresh_dest`) has its directory and nothing at it yet, a
dangling link included; a file the tool reads (`input_file`) is a regular file.
"""

from __future__ import annotations

from pathlib import Path

from scry_core import judges
from scry_core.reply_contract import Invalid

#: The argument names that carry a path, on every tool that takes one. The inventory test holds
#: the registered tools' arguments of these names to its list, so a new one under one of these
#: names meets the rule or fails there; a path argument under a new name is added here first.
PATH_PARAMETERS = frozenset({"cwd", "conf", "logfile", "captures_dir", "state_dir", "dest",
                             "path", "capture_path", "types", "binary"})


def absolute(name: str, value: object) -> Path:
    """`value` as an absolute path, `~` expanded, or scry-core's refusal naming `name` and
    why."""
    return judges.absolute(name, value)


def taken(path: Path) -> bool:
    """Something is at `path`, a dangling link included: `exists()` follows a link and reads one
    pointing nowhere as absent, which a copy, or the debugger, would then write through."""
    return path.exists() or path.is_symlink()


def fresh_dest(name: str, value: str | Path) -> Path:
    """A file this tool is about to write: scry-core's `judges.fresh_file`, absolute or `~`-led,
    its directory there, nothing at it yet, a dangling link included."""
    return judges.fresh_file(name, str(value))


def resolved(name: str, path: Path) -> Path:
    """`path` with its links resolved, or the refusal. A loop names no file, and `resolve`
    either raises on one or, not being strict, hands the link back unresolved: both refused."""
    try:
        out = path.resolve()
        loop = out.is_symlink()
    except (OSError, RuntimeError) as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be resolved: {e}") from None
    if loop:
        raise Invalid("bad_argument",
            f"{name}: {path} cannot be resolved: it is a link loop, so it names no file")
    return out


def make_directory(name: str, path: Path) -> None:
    """A directory this server writes into, created with its parents now (one already there is
    taken as it is). A failed `mkdir` is the host's refusal, `host_failed`, never a traceback."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise Invalid("host_failed", f"{name}: {path} cannot be created: {e}") from None


def input_file(name: str, value: object, thing: str) -> Path:
    """A file this tool reads: absolute and a regular file there now."""
    path = absolute(name, value)
    try:
        there = path.is_file()
    except (OSError, ValueError) as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be looked at: {e}") from None
    if not there:
        raise Invalid("bad_argument", f"{name}: no {thing} at {path}")
    return path


def read_text(name: str, value: object, thing: str) -> str:
    """A caller's text file, read whole as UTF-8: one that is not is refused where it broke,
    rather than escaping as a traceback. A byte-order mark an editor wrote first is not part of
    the text, or it would stay glued to the file's first word."""
    path = input_file(name, value, thing)
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise Invalid("bad_argument",
            f"{name}: {path} is not UTF-8 text: byte {e.start} ({e.object[e.start:e.start + 1]!r}) "
            f"{e.reason}") from None
    except OSError as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be read: {e}") from None
