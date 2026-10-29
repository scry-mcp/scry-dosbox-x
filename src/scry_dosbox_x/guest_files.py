"""The guest's file channel: a file a DOS program leaves on a mounted drive, which is how it hands
a result back (`PROG.EXE > OUT.TXT`). Each file `start(guest_files=)` names is fingerprinted
before the emulator boots, so `guest_file` and `close` can tell the three failures a bare
existence test lets through: absent, empty, and unchanged since before the run
(`docs/reference/files.md`, The guest's files)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scry_core.reply_contract import Invalid

from scry_dosbox_x import paths
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

#: The states that mean the guest handed nothing back, or nothing the host can read.
FAILED = ("absent", "empty", "unchanged", "unreadable")
GUEST_FILES_MAX = 16
HASH_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True)
class Print:
    """What a file was: absent, or its size, modification time and digest."""

    exists: bool
    size: int = 0
    mtime_ns: int = 0
    sha256: str = ""

    def shown(self) -> dict[str, Any]:
        if not self.exists:
            return {"exists": False}
        return {"exists": True, "bytes": self.size, "sha256": self.sha256}


def fingerprint(path: Path) -> Print:
    digest = hashlib.sha256()
    size = 0
    try:
        st_ = path.stat()
        with path.open("rb") as f:
            while chunk := f.read(HASH_CHUNK_BYTES):
                digest.update(chunk)
                size += len(chunk)
    except FileNotFoundError:
        return Print(False)
    except OSError as e:
        raise Invalid("host_failed", f"{path} could not be read: {e!r}") from None
    return Print(True, size, st_.st_mtime_ns, digest.hexdigest())


def check_guest_files(guest_files: object) -> list[Path]:
    """`start`'s `guest_files`: absolute host paths, each once, none a directory."""
    if guest_files is None:
        return []
    if not isinstance(guest_files, list) or not all(isinstance(p, str) for p in guest_files):
        raise Invalid("bad_argument", "guest_files is a list of paths")
    if len(guest_files) > GUEST_FILES_MAX:
        raise Invalid("bad_argument", f"guest_files names {len(guest_files)} files; at most "
                      f"{GUEST_FILES_MAX}")
    out = [paths.absolute("guest_files", p) for p in guest_files]
    if len(set(out)) != len(out):
        raise Invalid("bad_argument", "guest_files names one file twice")
    for p in out:
        if p.is_dir():
            raise Invalid("bad_argument", f"guest_files: {p} is a directory, not a file the "
                          "guest writes")
    return out


def take(files: list[Path]) -> dict[Path, Print]:
    """Each file as it is before the run."""
    return {p: fingerprint(p) for p in files}


def verdict(path: Path, before: Print) -> dict[str, Any]:
    """What the guest left at `path` against what was there before the run; `unreadable`, with
    why, when the host cannot read what is there now (a directory, a file it may not open)."""
    try:
        now = fingerprint(path)
    except Invalid as e:
        return {"path": str(path), "state": "unreadable", "before": before.shown(),
                "why": str(e)}
    if not now.exists:
        said = "absent"
    elif now.size == 0:
        said = "empty"
    elif now == before:
        said = "unchanged"
    else:
        said = "written"
    out: dict[str, Any] = {"path": str(path), "state": said, "before": before.shown(),
                           **({"bytes": now.size, "sha256": now.sha256} if now.exists else {})}
    if said == "written" and before.exists and now.sha256 == before.sha256:
        out["same_bytes"] = True
    return out


def guest_file(path: str) -> dict[str, Any]:
    """The body of the `guest_file` tool."""
    asked = paths.absolute("path", path)
    taken = STATE.guest_files
    if asked not in taken:
        named = ", ".join(str(p) for p in taken) or "none"
        raise Invalid("bad_argument", f"{asked} was not fingerprinted at `start`, so whether it "
                      f"changed since cannot be told; `start(guest_files=[...])` names the files "
                      f"(this session's: {named})")
    found = verdict(asked, taken[asked])
    if found["state"] in FAILED:
        why = {"absent": "the guest left no file there",
               "empty": "the guest left the file empty",
               "unchanged": "the file is the one that was there before the run: the guest did "
                            "not write it",
               "unreadable": f"the host cannot read what is there ({found.get('why')})"}[
                   found["state"]]
        return st.reply(status="INVALID", code="readback_refused",
                        message=f"{asked}: {why}. A file a DOS program still holds open may sit "
                                "in the emulator's buffer until it is closed", **found)
    return st.reply(**found)


def at_close() -> list[dict[str, Any]]:
    """Each fingerprinted file's verdict, for `close`'s reply."""
    return [verdict(p, before) for p, before in STATE.guest_files.items()]
