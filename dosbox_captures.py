"""Files this session wrote, the video DOSBox-X recorded, and stills out of it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import judges

import dosbox_frames as frames
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

#: Tools that write a file, and where their reply names it.
WRITERS: dict[str, Callable[[dict[str, Any]], object]] = {
    **{tool: (lambda r: r.get("path")) for tool in (
        "capture_frame", "snapshot", "memdump", "machine_map", "perform_export")},
    # Only `save` writes; `load` answers the `path` it read.
    "comment_write": lambda r: r.get("path") if "dropped_total" in r else None,
    "map_write": lambda r: r.get("path") if "promoted" in r else None,
    **{tool: (lambda r: (r.get("image") or {}).get("path")) for tool in ("screen_view",
                                                                       "palette")},
    "series_capture": lambda r: r.get("manifest"),
    "trace": lambda r: (r.get("trace") or {}).get("path"),
}
SERIES = "series"


def note_written(tool: str, reply: dict[str, Any]) -> None:
    """Record an `ok` call's file for `captures`, kind being its extension or `series`."""
    where = WRITERS.get(tool)
    if where is None or reply.get("status", "ok") != "ok":
        return
    path = where(reply)
    if not isinstance(path, str) or not path:
        return
    kind = SERIES if tool == "series_capture" else Path(path).suffix.lstrip(".") or "file"
    if (kind, path) not in STATE.written:
        STATE.written.append((kind, path))


def _row(kind: str, path: Path) -> dict[str, Any]:
    """One written file as `captures` lists it: present or not, and its size."""
    try:
        size = path.stat().st_size if path.is_file() else None
    except FileNotFoundError:
        size = None
    if size is None:
        return {"kind": kind, "path": str(path), "present": False}
    return {"kind": kind, "path": str(path), "present": True, "bytes": size}


def captures(session: ds.Session) -> dict[str, Any]:
    """The body of the `captures` tool: files in write order, then recorded videos."""
    rows = [_row(kind, Path(path)) for kind, path in STATE.written]
    rows += [{"kind": "avi", "present": True, **video} for video in frames.videos(session)]
    return st.reply(captures=rows)


def capture_frame(session: ds.Session, at: int, dest: Path, source: Path | None) -> dict[str, Any]:
    """The body of the `capture_frame` tool; `dest` and `source` arrive judged absolute."""
    read_from = source if source is not None else Path(str(session.captures()[-1]["path"]))
    path = session.frame(at, dest, read_from)
    return st.reply(**judges.file_facts(path), capture_path=str(read_from), frame=at)
