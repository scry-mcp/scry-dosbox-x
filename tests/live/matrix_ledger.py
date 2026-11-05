"""The core ledger, bound to this server's scratch and summary variable."""

from scry_core.live_ledger import (
    CALL_GRACE_S,
    EVIDENCE_TAIL_LINES,
    WAIT_CEILING_S,
    Blocked,
    Cell,
    Ledger,
    Section,
    cannot_be_judged,
    chosen_sections,
)
from scry_core.verdict import EXIT_FAIL, EXIT_INVALID, EXIT_PASS

SCRATCH_PREFIX = "dosbox-x-live-matrix-"
#: Set by a pooled run, never by hand.
SUMMARY_VAR = "DOSBOX_X_LIVE_SUMMARY"

__all__ = [
    "CALL_GRACE_S", "EVIDENCE_TAIL_LINES", "EXIT_FAIL", "EXIT_INVALID", "EXIT_PASS",
    "SCRATCH_PREFIX", "SUMMARY_VAR", "WAIT_CEILING_S", "Blocked", "Cell", "Ledger", "Section",
    "cannot_be_judged", "chosen_sections",
]
