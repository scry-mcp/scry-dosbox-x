"""What a tool's docstring states that the code already knows, filled at registration: the
picture's two sentences are scry-core's, from the code that attaches the picture, and a number is
the constant that enforces it, never typed into the text."""
from __future__ import annotations

import re

from scry_core import picture, recording
from scry_core import series as core_series

VALUES = {"PICTURE": picture.DESCRIBED, "PICTURE_ARGS": picture.ARGUMENTS,
          "SERIES_MAX": str(core_series.SERIES_MAX),
          "DROPPED_SHOWN": str(recording.DROPPED_SHOWN),
          "RECORD_MAX": str(recording.RECORD_MAX)}
_PLACEHOLDER = re.compile(r"\{[A-Z_]+\}")


def filled(name: str, doc: str) -> str:
    """`doc` with every `{NAME}` of `VALUES` filled, or a failure at import naming what is left: a
    placeholder that reaches a client reads as a word, not as a missing number."""
    for key, value in VALUES.items():
        doc = doc.replace("{" + key + "}", value)
    left = _PLACEHOLDER.findall(doc)
    if left:
        raise TypeError(f"{name}'s docstring names {left}, which nothing fills")
    return doc
