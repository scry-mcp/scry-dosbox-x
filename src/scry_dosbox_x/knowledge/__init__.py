"""The IBM PC's dictionaries and the shared chips and cpus, loaded once and serving only what is
confirmed."""

from __future__ import annotations

from functools import cache
from importlib import resources
from pathlib import Path

import scry_core
from scry_core.knowledge import Base, Confirmation, shared
from scry_core.knowledge.confirmed import parse_second_check
from scry_core.knowledge.lock import parse_lock

from scry_dosbox_x.knowledge.support import PINS

SCOPE = "ibm-pc"
#: Outside `knowledge/`, where every JSON file is a dictionary.
LOCK = "knowledge.lock.json"
SECOND_CHECK = "knowledge.second-check.json"


_CORE = Path(scry_core.__file__).parent / "knowledge"


def confirmation() -> Confirmation:
    """This server's lock and second check merged with the shared dictionaries'."""
    folder = resources.files("scry_dosbox_x")
    return Confirmation.of(
        (parse_lock((folder / LOCK).read_text(encoding="utf-8"), LOCK), *shared.locks()),
        (parse_second_check((folder / SECOND_CHECK).read_text(encoding="utf-8"), SECOND_CHECK),
         shared.second_check()))


def load(fts5: bool | None = None) -> Base:
    return Base.load("scry_dosbox_x", _CORE / "chips", _CORE / "cpus", fts5=fts5, pins=PINS,
                     confirmation=confirmation())


@cache
def base() -> Base:
    return load()
