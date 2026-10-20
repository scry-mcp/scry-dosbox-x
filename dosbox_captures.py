"""The CAPTURES: the files this session's tools wrote, the video DOSBox-X recorded, and a still
out of it. The ledger is filled by the server's one call path, so `captures` lists what the tools
handed back without each tool remembering to. The VIDEO is the emulator's own doing and needs no
keypress; a still OUT OF IT is an extraction with `ffmpeg`, and a still of the running screen is
`snapshot`, the stub's command to the integration device's capture trigger.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from scry_core import judges

import dosbox_frames as frames
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

#: The tools that write a file a caller named or the scratch holds, and where their reply names
#: it: a series by its manifest, a trace and a picture inside their blocks, every other by
#: `path`.
WRITERS: dict[str, Callable[[dict[str, Any]], object]] = {
    **{tool: (lambda r: r.get("path")) for tool in (
        "capture_frame", "snapshot", "memdump", "machine_map", "comment_save", "perform_export",
        "map_save")},
    **{tool: (lambda r: (r.get("image") or {}).get("path")) for tool in ("screen_view",
                                                                       "palette")},
    "series_capture": lambda r: r.get("manifest"),
    "trace": lambda r: (r.get("trace") or {}).get("path"),
}
#: A series is listed by its manifest, under this kind.
SERIES = "series"


def note_written(tool: str, reply: dict[str, Any]) -> None:
    """A call that answered `ok` and wrote a file: kept for `captures`, under the file's
    extension (`png`, `bin`, `json`, `tsv`, `trace`) or `series`."""
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
    """One written file as `captures` lists it, read now: there or not, and its size."""
    try:
        size = path.stat().st_size if path.is_file() else None
    except FileNotFoundError:
        size = None
    if size is None:
        return {"kind": kind, "path": str(path), "present": False}
    return {"kind": kind, "path": str(path), "present": True, "bytes": size}


def captures(session: ds.Session) -> dict[str, Any]:
    """The body of the `captures` tool: every file this session wrote, in the order it wrote
    them, then the video the emulator recorded (`capture_video`), largest last. An empty list
    is an answer: nothing was written."""
    rows = [_row(kind, Path(path)) for kind, path in STATE.written]
    rows += [{"kind": "avi", "present": True, **video} for video in frames.videos(session)]
    return st.reply(captures=rows)


def capture_frame(session: ds.Session, at: int, dest: Path, source: Path | None) -> dict[str, Any]:
    """The body of the `capture_frame` tool; `dest` and `source` arrive judged absolute by
    the tool, `source` a file there."""
    read_from = source if source is not None else Path(str(session.captures()[-1]["path"]))
    path = session.frame(at, dest, read_from)
    return st.reply(**judges.file_facts(path), capture_path=str(read_from), frame=at)
