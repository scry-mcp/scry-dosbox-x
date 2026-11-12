"""Path arguments are absolute or `~`-led, never relative."""

from __future__ import annotations

from pathlib import Path

from scry_core import file_names, judges
from scry_core.reply_contract import Invalid

#: Path-carrying argument names; the inventory test holds tools to this list.
PATH_PARAMETERS = frozenset({"cwd", "conf", "logfile", "captures_dir", "state_dir", "dest",
                             "path", "capture_path", "types", "binary"})


def absolute(name: str, value: object) -> Path:
    return judges.absolute(name, value)


def taken(path: Path) -> bool:
    """Something is at `path`; `exists()` misses a dangling link."""
    return path.exists() or path.is_symlink()


def dest_file(name: str, value: object) -> Path:
    """A file a tool will write, under the name it is written as; the place is not looked at."""
    return file_names.caller_file(judges.absolute(name, value), name)


def named_dest(name: str, value: object) -> Path:
    """A file a tool will write, under the name the caller gave it (`~` expanded, absolute):
    the file-name rule of `scry_core.file_names` is of the names a server makes up, not of a
    caller's own `dest`, which the caller reads back by. The place is not looked at."""
    return judges.absolute(name, value)


def fresh_dest(name: str, value: str | Path) -> Path:
    return judges.fresh_file(name, str(value))


def fresh_named_dest(name: str, value: str | Path) -> Path:
    """`named_dest`, in an existing directory, with nothing there yet."""
    path = named_dest(name, str(value))
    try:
        there = path.parent.is_dir()
    except OSError as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be looked at: {e}") from None
    if not there:
        raise Invalid("bad_argument", f"{name}: {path.parent} is not a directory, so "
                      f"{path.name} has nowhere to go")
    try:
        taken = path.exists() or path.is_symlink()
    except OSError as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be looked at: {e}") from None
    if taken:
        raise Invalid("bad_argument", f"{name}: {path} already exists. This will not overwrite "
                      "it: name a path that is not there yet")
    return path


def fresh_folder(name: str, value: str | Path) -> Path:
    return judges.fresh_folder(name, str(value))


def resolved(name: str, path: Path) -> Path:
    """`path` with links resolved; a link loop (raised or left unresolved) is refused."""
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
    """Create a directory and parents; failure is `host_failed`."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise Invalid("host_failed", f"{name}: {path} cannot be created: {e}") from None
