"""The CAPTURES: the video DOSBox-X recorded for this session, and a still out of it.

Small today, and its own module on purpose: this is the seam the bounded video capture
and the audio capture of the emulator roadmap are born into, rather than added to the
server file. Both halves exist and they are not symmetric: the VIDEO is the emulator's
own doing and needs no keypress; the STILL is an extraction from that video with
`ffmpeg`, because the emulator's own screenshot is a mapper action with no
non-interactive trigger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dosbox_session as ds
import dosbox_state as st


def captures(session: ds.Session) -> dict[str, Any]:
    """The body of the `captures` tool."""
    return st.reply(captures=session.captures())


def capture_frame(session: ds.Session, at: int, dest: Path, source: Path | None) -> dict[str, Any]:
    """The body of the `capture_frame` tool; `dest` and `source` arrive judged absolute by
    the tool, `source` a file there."""
    read_from = source if source is not None else Path(str(session.captures()[-1]["path"]))
    path = session.frame(at, dest, read_from)
    return st.reply(path=str(path), bytes=path.stat().st_size, source=str(read_from), at=at)
