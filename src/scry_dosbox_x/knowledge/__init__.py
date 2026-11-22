"""The IBM PC's dictionaries, loaded once and serving only what is confirmed."""

from __future__ import annotations

from functools import cache
from importlib import resources

from scry_core.knowledge import Base, Confirmation
from scry_core.knowledge.confirmed import parse_second_check
from scry_core.knowledge.lock import parse_lock

from scry_dosbox_x.knowledge.support import PINS

SCOPE = "ibm-pc"
#: Outside `knowledge/`, where every JSON file is a dictionary.
LOCK = "knowledge.lock.json"
SECOND_CHECK = "knowledge.second-check.json"


def confirmation() -> Confirmation:
    folder = resources.files("scry_dosbox_x")
    return Confirmation.of(
        (parse_lock((folder / LOCK).read_text(encoding="utf-8"), LOCK),),
        (parse_second_check((folder / SECOND_CHECK).read_text(encoding="utf-8"), SECOND_CHECK),))


@cache
def base() -> Base:
    return Base.load("scry_dosbox_x", pins=PINS, confirmation=confirmation())
