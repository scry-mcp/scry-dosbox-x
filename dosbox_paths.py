"""Path arguments are absolute or `~`-led, never relative."""

from __future__ import annotations

from pathlib import Path

from scry_core import judges
from scry_core.reply_contract import Invalid

#: Path-carrying argument names; the inventory test holds tools to this list.
PATH_PARAMETERS = frozenset({"cwd", "conf", "logfile", "captures_dir", "state_dir", "dest",
                             "path", "capture_path", "types", "binary"})


def absolute(name: str, value: object) -> Path:
    return judges.absolute(name, value)


def taken(path: Path) -> bool:
    """Something is at `path`; `exists()` misses a dangling link."""
    return path.exists() or path.is_symlink()


def fresh_dest(name: str, value: str | Path) -> Path:
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
