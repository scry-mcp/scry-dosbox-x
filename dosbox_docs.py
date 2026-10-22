"""What a tool's docstring states that the code already knows, filled at registration by
scry-core's `docs.filled`: the picture's two sentences, the series' bound and the map file
tools' descriptions are scry-core's own values, and a number is the constant that enforces it,
never typed into the text."""
from __future__ import annotations

from scry_core import docs, log_marks, picture, recording, screen_map, series
from scry_core import vocabulary as vocab

import dosbox_checks as checks
import dosbox_code as code
import dosbox_comment_file as comment_file
import dosbox_console as console
import dosbox_find as finder
import dosbox_inputs as inputs
import dosbox_launch as launch
import dosbox_logs as logs
import dosbox_placement as placement
import dosbox_sequence as sequence
import dosbox_state as st
import dosbox_trace as trace

#: What every stop reply carries, named once for every tool that stops the machine.
STOP_FIELDS = (
    "the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `instruction`, `regs`, `watches`, "
    "`cause` and `e9`"
)

DOC_VALUES = {**picture.DOC_VALUES, **series.DOC_VALUES, **screen_map.DOC_VALUES,
              **recording.DOC_VALUES,
              "STOP_FIELDS": STOP_FIELDS,
              "DROPPED_SHOWN": str(recording.DROPPED_SHOWN),
              "RECORD_MAX": str(sequence.RECORD_MAX),
              **log_marks.DOC_VALUES,
              "LOG_LIMIT_MAX": str(logs.LOG_LIMIT_MAX), "WAIT_MAX_S": f"{vocab.WAIT_MAX_S:g}",
              "READ_MAX": str(console.DATA_VIEW_BYTES), "DISASM_MAX": str(code.LENGTH_MAX),
              "INSTRUCTIONS_MAX": str(trace.INSTRUCTIONS_MAX),
              "SYMBOLS_LIMIT_MAX": str(placement.SYMBOLS_LIMIT_MAX),
              "COMMENT_BYTES_MAX": str(comment_file.TEXT_MAX_BYTES),
              "EXPECT_WAIT_S": f"{inputs.DRIVE_EXPECT_WAIT_S:g}",
              "SETTLE_S": f"{sequence.SETTLE_DEFAULT_S:g}",
              "EFFECT_WAIT_S": f"{inputs.EFFECT_WAIT_DEFAULT_S:g}",
              "KEYS_MAX": str(inputs.MAX_KEYS_PER_CALL),
              "SESSION_MAX_S": str(launch.MAX_SECONDS),
              "INPUT_PORT_MIN": str(launch.INPUT_PORT_MIN),
              "INPUT_PORT_MAX": str(launch.INPUT_PORT_MAX),
              "STATE_NAME_MAX": str(launch.STATE_NAME_MAX),
              "HITS_MAX": str(finder.HITS_MAX), "HITS_DEFAULT": str(finder.HITS_DEFAULT),
              "DEBUG_TEXT_KEEP": str(st.DEBUG_TEXT_KEEP),
              "DETAIL_TEXT_KEEP": str(st.DETAIL_TEXT_KEEP),
              "SCREEN_TEXT_MAX": str(checks.SCREEN_TEXT_MAX),
              "SYMBOLS_SHOWN": str(trace.SYMBOLS_SHOWN),
              "ROWS_SHOWN": str(st.ROWS_SHOWN)}


def filled(name: str, doc: str) -> str:
    """`doc` with this server's values filled (`scry_core.docs.filled`)."""
    return docs.filled(name, doc, DOC_VALUES)
