"""Path arguments are absolute or `~`-led, never relative."""

from __future__ import annotations

from pathlib import Path

from scry_core import judges
from scry_core.reply_contract import Invalid

#: Path-carrying argument names; the inventory test holds tools to this list.
PATH_PARAMETERS = frozenset({"cwd", "conf", "logfile", "captures_dir", "state_dir", "dest",
                             "path", "capture_path", "types", "binary"})


def absolute(name: str, value: object) -> Path:
    """`value` as an absolute path, `~` expanded, or a refusal."""
    return judges.absolute(name, value)


def taken(path: Path) -> bool:
    """Something is at `path`; `exists()` misses a dangling link."""
    return path.exists() or path.is_symlink()


def fresh_dest(name: str, value: str | Path) -> Path:
    """A file to write: its directory exists, nothing is at it."""
    return judges.fresh_file(name, str(value))


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
    """A caller's text file as UTF-8; `utf-8-sig` drops a leading BOM."""
    path = input_file(name, value, thing)
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise Invalid("bad_argument",
            f"{name}: {path} is not UTF-8 text: byte {e.start} ({e.object[e.start:e.start + 1]!r}) "
            f"{e.reason}") from None
    except OSError as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be read: {e}") from None
