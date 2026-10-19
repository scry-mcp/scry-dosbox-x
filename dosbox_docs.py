"""What a tool's docstring states that the code already knows, filled at registration by
scry-core's `docs.filled`: the picture's two sentences, the series' bound and the map file
tools' descriptions are scry-core's own values, and a number is the constant that enforces it,
never typed into the text."""
from __future__ import annotations

from scry_core import docs, picture, recording, screen_map, series

import dosbox_code as code
import dosbox_comment_file as comment_file
import dosbox_console as console
import dosbox_logs as logs
import dosbox_placement as placement
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_trace as trace

#: What every stop reply carries, named once for every tool that stops the machine.
STOP_FIELDS = (
    "the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, "
    "`attribution` and `e9`"
)

DOC_VALUES = {**picture.DOC_VALUES, **series.DOC_VALUES, **screen_map.DOC_VALUES,
              "STOP_FIELDS": STOP_FIELDS,
              "DROPPED_SHOWN": str(recording.DROPPED_SHOWN),
              "RECORD_MAX": str(sequence.RECORD_MAX),
              "LOG_LIMIT_MAX": str(logs.LOG_LIMIT_MAX), "WAIT_MAX_S": f"{ds.RUN_TO_MAX:g}",
              "READ_MAX": str(console.DATA_VIEW_BYTES), "DISASM_MAX": str(code.LENGTH_MAX),
              "INSTRUCTIONS_MAX": str(trace.INSTRUCTIONS_MAX),
              "SYMBOLS_LIMIT_MAX": str(placement.SYMBOLS_LIMIT_MAX),
              "COMMENT_BYTES_MAX": str(comment_file.TEXT_MAX_BYTES)}


def filled(name: str, doc: str) -> str:
    """`doc` with this server's values filled (`scry_core.docs.filled`)."""
    return docs.filled(name, doc, DOC_VALUES)
