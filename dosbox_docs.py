"""What a tool's docstring states that the code already knows, filled at registration by
scry-core's `docs.filled`: the picture's two sentences and the series' bound are scry-core's own
values, and a number is the constant that enforces it, never typed into the text."""
from __future__ import annotations

from scry_core import docs, picture, recording, series

import dosbox_sequence as sequence

DOC_VALUES = {**picture.DOC_VALUES, **series.DOC_VALUES,
          "DROPPED_SHOWN": str(recording.DROPPED_SHOWN),
          "RECORD_MAX": str(sequence.RECORD_MAX)}


def filled(name: str, doc: str) -> str:
    """`doc` with this server's values filled (`scry_core.docs.filled`)."""
    return docs.filled(name, doc, DOC_VALUES)
