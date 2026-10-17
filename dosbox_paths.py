"""The one judge of a path a caller gives this server's own tools (the media file tools,
scry-core's, judge theirs with scry-core's, to the same rule).

EVERY PATH ARGUMENT IS ABSOLUTE, AND NOTHING HERE EXPANDS `~`. A relative path is judged
against one directory and used in another: this server's own working directory is wherever
the client launched it, the emulator's is the session's `cwd`, and a path that means one thing
to the judge and another to the writer is checked against the wrong file. And `~` is a shell's
spelling, not a path: `Path("~/x")` is a relative path whose first component is a directory
named `~`, so the home directory is written out instead. Both are refused with the reason, so a
caller learns the rule once.

THE SHAPE is judged before the session gate (a value as wrong with no machine as with one); THE
FILESYSTEM at the call, on the filesystem of that moment, since an earlier step of a list may
change it: a file the tool writes (`fresh_dest`) has its directory and nothing at it yet, a
dangling link included; a file the tool reads (`input_file`) is a regular file.
"""

from __future__ import annotations

from pathlib import Path

from scry_core.reply_contract import Invalid

#: The argument names that carry a path, on every tool that takes one. The inventory test holds
#: the registered tools' arguments of these names to its list, so a new one under one of these
#: names meets the rule or fails there; a path argument under a new name is added here first.
PATH_PARAMETERS = frozenset({"cwd", "conf", "logfile", "captures_dir", "state_dir", "dest",
                             "source", "types", "binary"})


def absolute(name: str, value: object) -> Path:
    """`value` as an absolute path, or the refusal naming `name` and why: not text, empty, a
    NUL or a lone surrogate (no file name can hold either), `~`, or relative."""
    if not isinstance(value, str):
        raise Invalid("bad_argument", f"{name}={value!r} is not a path")
    if not value:
        raise Invalid("bad_argument", f"{name} is empty: it names an absolute path")
    if "\x00" in value:
        raise Invalid("bad_argument", f"{name}={value!r} carries a NUL, which no path holds")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise Invalid("bad_argument",
            f"{name}={value!r} carries a lone surrogate, which no file name holds") from None
    if value.startswith("~"):
        try:
            home = f"{Path.home()}/..."
        except RuntimeError:          # no home this process can name; the rule stands anyway
            home = "the home directory, spelled in full"
        raise Invalid("bad_argument",
            f"{name}={value!r} starts with `~`, which nothing here expands: write the home "
            f"directory out ({home})")
    path = Path(value)
    if not path.is_absolute():
        raise Invalid("bad_argument",
            f"{name}={value!r} is relative: it would be judged against one directory and used "
            f"in another. Every path here is absolute")
    return path


def taken(path: Path) -> bool:
    """Something is at `path`, a dangling link included: `exists()` follows a link and reads one
    pointing nowhere as absent, which a copy, or the debugger, would then write through."""
    return path.exists() or path.is_symlink()


def fresh_dest(name: str, value: str | Path) -> Path:
    """A file this tool is about to write: absolute, its directory there, nothing at it yet. A
    path the filesystem cannot even look at is refused the same way, never raised."""
    path = absolute(name, str(value))
    try:
        if taken(path):
            raise Invalid("bad_argument",
                f"{name}: {path} already exists. This will not overwrite it: name a path that "
                f"is not there yet, or move that file aside and ask again")
        if not path.parent.is_dir():
            raise Invalid("bad_argument",
                f"{name}: {path.parent} is not a directory, so {path.name} has nowhere to go")
    except (OSError, ValueError) as e:
        raise Invalid("bad_argument", f"{name}: {path} cannot be looked at: {e}") from None
    return path


def write_new(path: Path, data: bytes, what: str) -> Path:
    """`data` to `path`, created here and nowhere else: a file that appeared since `fresh_dest`
    judged it is refused, never overwritten, and a write that fails takes the file away rather
    than leaving a short one where the caller will look."""
    try:
        out = path.open("xb")
    except FileExistsError:
        raise Invalid("bad_argument",
            f"{path} appeared while {what} was read. This will not overwrite it: name a path "
            f"that is not there yet") from None
    except OSError as e:
        raise Invalid("host_failed", f"cannot write {what} to {path}: {e!r}") from None
    try:
        with out:
            out.write(data)
    except OSError as e:
        path.unlink(missing_ok=True)
        raise Invalid("host_failed", f"cannot write {what} to {path}: {e!r}") from None
    return path


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
