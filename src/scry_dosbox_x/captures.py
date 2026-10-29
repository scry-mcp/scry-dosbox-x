"""Files this session wrote, the video DOSBox-X recorded, and stills out of it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import judges

from scry_dosbox_x import capture_files, frames
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

#: Tools that write a file, and where their reply names it.
WRITERS: dict[str, Callable[[dict[str, Any]], object]] = {
    **{tool: (lambda r: r.get("path")) for tool in (
        "capture_frame", "snapshot", "memdump", "machine_map", "perform_export")},
    # A recording with no file answers `path` unavailable, which is not a string.
    **{tool: (lambda r: r.get("path")) for tool in ("record", "audio_record")},
    # Only `save` writes; `load` answers the `path` it read.
    "comment_write": lambda r: r.get("path") if "dropped_total" in r else None,
    "screen_map_write": lambda r: r.get("path") if "promoted" in r else None,
    **{tool: (lambda r: (r.get("image") or {}).get("path")) for tool in ("screen_view",
                                                                       "palette")},
    "series_capture": lambda r: r.get("manifest"),
    "trace": lambda r: (r.get("trace") or {}).get("path"),
}
SERIES = "series"
#: Their `kind` is the reply's, whatever `dest` is called.
RECORDINGS = ("record", "audio_record")


def note_written(tool: str, reply: dict[str, Any]) -> None:
    """Record an `ok` call's file for `captures`, kind being its extension or `series`."""
    where = WRITERS.get(tool)
    if where is None or reply.get("status", "ok") != "ok":
        return
    path = where(reply)
    if not isinstance(path, str) or not path:
        return
    kind = (SERIES if tool == "series_capture" else str(reply["kind"]) if tool in RECORDINGS
            else Path(path).suffix.lstrip(".") or "file")
    if (kind, path) not in STATE.written:
        STATE.written.append((kind, path))


#: A recording's facts by path, valid while its size and modification time are the same: the
#: listing is polled, and reading a clip whole at every poll is the cost.
_AVI_SEEN: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


def _avi_row(path: Path, size: int) -> dict[str, Any]:
    stamp = (size, path.stat().st_mtime_ns)
    held = _AVI_SEEN.get(str(path))
    if held is None or held[0] != stamp:
        held = (stamp, ds.avi_facts(path.read_bytes()))
        _AVI_SEEN[str(path)] = held
    return held[1]


def _row(kind: str, path: Path) -> dict[str, Any]:
    """One written file as `captures` lists it: present or not, its size, and for a recording
    whether its writer finished it and what it holds, re-read when it changed."""
    try:
        size = path.stat().st_size if path.is_file() else None
    except FileNotFoundError:
        size = None
    if size is None:
        return {"kind": kind, "path": str(path), "present": False}
    row: dict[str, Any] = {"kind": kind, "path": str(path), "present": True, "bytes": size}
    if kind == "avi":
        try:
            facts = _avi_row(path, size)
        except OSError:
            return row
        return {**row, **{k: v for k, v in facts.items() if k != "bytes"}}
    return {**row, **capture_files.facts(kind, path)}


def captures(session: ds.Session) -> dict[str, Any]:
    """The body of the `captures` tool: files in write order, then recorded videos."""
    rows = [_row(kind, Path(path)) for kind, path in STATE.written]
    for gone in set(_AVI_SEEN) - {path for _kind, path in STATE.written}:
        del _AVI_SEEN[gone]
    rows += [{"kind": "avi", "present": True, **video} for video in frames.videos(session)]
    return st.reply(captures=rows)


def capture_frame(session: ds.Session, at: int, dest: Path, source: Path | None) -> dict[str, Any]:
    """The body of the `capture_frame` tool; `dest` and `source` arrive judged absolute."""
    read_from = source if source is not None else Path(str(session.captures()[-1]["path"]))
    path = session.frame(at, dest, read_from)
    return st.reply(**judges.file_facts(path), capture_path=str(read_from), frame=at)
