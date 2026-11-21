"""The IBM PC's dictionaries, loaded once from this package's JSON files."""

from __future__ import annotations

from functools import cache

from scry_core.knowledge import Base

from scry_dosbox_x.knowledge.support import PINS

SCOPE = "ibm-pc"


@cache
def base() -> Base:
    return Base.load("scry_dosbox_x", pins=PINS)
