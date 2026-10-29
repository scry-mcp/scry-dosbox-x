"""What a tool's docstring states that the code already knows, filled at registration by
scry-core's `docs.filled`: the picture's two sentences, the series' bound and the map file
tools' descriptions are scry-core's own values, and a number is the constant that enforces it,
never typed into the text."""
from __future__ import annotations

from scry_core import comment_file as core_comments
from scry_core import (
    docs,
    frame_window,
    log_marks,
    picture,
    recording,
    screen_map,
    series,
    state_files,
)
from scry_core import (
    scan_vocabulary as words,
)
from scry_core import vocabulary as vocab

from scry_dosbox_x import (
    binary,
    capture_files,
    checks,
    grammar,
    guest_files,
    inputs,
    launch,
    logs,
    placement,
    sequence,
    trace,
)
from scry_dosbox_x import screen_pens as by_pens
from scry_dosbox_x import state as st

#: What every stop reply carries, named once for every tool that stops the machine.
STOP_FIELDS = (
    "the stop: `pc` (`SSSS:OOOOOOOO`), `cpu_mode`, `stop_seq`, `frame`, `instruction`, `regs`, "
    "`watches`, `cause` and `e9`"
)

DOC_VALUES = {**picture.DOC_VALUES, **series.DOC_VALUES, **screen_map.DOC_VALUES,
              **core_comments.DOC_VALUES,
              **recording.DOC_VALUES,
              "STOP_FIELDS": STOP_FIELDS,
              "SPAN_TICKS": str(capture_files.SPAN_TICKS),
              "RECORD_MAX": str(sequence.RECORD_MAX),
              "UNTIL_STEPS_MAX": str(frame_window.UNTIL_STEPS_MAX),
              **log_marks.DOC_VALUES,
              "LOG_LIMIT_MAX": str(logs.LOG_LIMIT_MAX), "WAIT_MAX_S": f"{vocab.WAIT_MAX_S:g}",
              "READ_MAX": str(grammar.READ_BYTES_MAX),
              "DEBUGGER_COMMANDS": ", ".join(f"`{c}`" for c in binary.COMMANDS),
              "CHANGE_WATCH_MAX": str(checks.CHANGE_WATCH_MAX),
              "TAP_COUNT_MAX": str(checks.TAP_MAX["count"]),
              "FREEZE_MAX": str(checks.FREEZE_MAX),
              "GUEST_FILES_MAX": str(guest_files.GUEST_FILES_MAX),
              "TAP_BLOCK_MAX": str(checks.TAP_MAX["capture"]),
              "INSTRUCTIONS_MAX": str(trace.INSTRUCTIONS_MAX),
              "SYMBOLS_LIMIT_MAX": str(placement.SYMBOLS_LIMIT_MAX),
              "SCREEN_PENS_MAX": str(by_pens.PENS_MAX),
              "EXPECT_WAIT_S": f"{inputs.DRIVE_EXPECT_WAIT_S:g}",
              "SETTLE_S": f"{sequence.SETTLE_DEFAULT_S:g}",
              "EFFECT_WAIT_S": f"{inputs.EFFECT_WAIT_DEFAULT_S:g}",
              "KEYS_MAX": str(inputs.MAX_KEYS_PER_CALL),
              "INPUT_PORT_MIN": str(launch.INPUT_PORT_MIN),
              "INPUT_PORT_MAX": str(launch.INPUT_PORT_MAX),
              "STATE_NAME_MAX": str(state_files.STATE_NAME_MAX),
              "HITS_MAX": str(words.HITS_MAX), "HITS_DEFAULT": str(words.HITS_DEFAULT),
              "DEBUG_TEXT_KEEP": str(st.DEBUG_TEXT_KEEP),
              "DETAIL_TEXT_KEEP": str(st.DETAIL_TEXT_KEEP),
              "SCREEN_TEXT_MAX": str(checks.SCREEN_TEXT_MAX),
              "SYMBOLS_SHOWN": str(trace.SYMBOLS_SHOWN)}


def filled(name: str, doc: str) -> str:
    """`doc` with this server's values filled (`scry_core.docs.filled`)."""
    return docs.filled(name, doc, DOC_VALUES)
