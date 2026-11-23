"""The IBM PC's dictionaries and the shared chips, loaded once, serving only what is sealed."""

from __future__ import annotations

from functools import cache
from importlib import resources
from pathlib import Path

import scry_core
from scry_core.knowledge import Base, Confirmation, sealed, shared
from scry_core.knowledge import base as rows
from scry_core.knowledge.confirmed import parse_second_check
from scry_core.knowledge.lock import parse_lock

from scry_dosbox_x.knowledge.support import PINS

SCOPE = "ibm-pc"
#: Outside `knowledge/`, where every JSON file is a dictionary.
LOCK = "knowledge.lock.json"
SECOND_CHECK = "knowledge.second-check.json"
#: Beside `knowledge_rows/`, for the same reason.
ROWS_LOCK = "knowledge_index/rows-lock.json"
ROWS_SOURCES = ("scry_dosbox_x", "scry_core")


_CORE = Path(scry_core.__file__).parent / "knowledge"


def merged(*locks: sealed.Lock) -> sealed.Lock:
    """Every part `locks` seal; a part sealed twice is a `ValueError`."""
    held: dict[str, dict[str, sealed.Part]] = {}
    for lock in locks:
        for id_, parts in lock.sealed.items():
            twice = held.setdefault(id_, {}).keys() & parts.keys()
            if twice:
                raise ValueError(f"{id_}: two locks seal its part {', '.join(sorted(twice))}")
            held[id_].update(parts)
    return sealed.Lock(held, tuple(r for lock in locks for r in lock.reopened))


def rows_lock() -> sealed.Lock:
    own = resources.files("scry_dosbox_x") / ROWS_LOCK
    return merged(sealed.parse_lock(own.read_text(encoding="utf-8"), ROWS_LOCK),
                  shared.rows_lock())


def rows_base(fts5: bool | None = None) -> rows.Base:
    return rows.Base.load(*ROWS_SOURCES, lock=rows_lock(), fts5=fts5, pins=PINS)


@cache
def base() -> rows.Base:
    return rows_base()


def confirmation() -> Confirmation:
    """This server's lock and second check merged with the shared dictionaries'."""
    folder = resources.files("scry_dosbox_x")
    return Confirmation.of(
        (parse_lock((folder / LOCK).read_text(encoding="utf-8"), LOCK), *shared.locks()),
        (parse_second_check((folder / SECOND_CHECK).read_text(encoding="utf-8"), SECOND_CHECK),
         shared.second_check()))


def load(fts5: bool | None = None) -> Base:
    """The `scry-knowledge/1` base: scry-core's `named_call` and `notes.note` take no other."""
    return Base.load("scry_dosbox_x", _CORE / "chips", _CORE / "cpus", fts5=fts5, pins=PINS,
                     confirmation=confirmation())


@cache
def names_base() -> Base:
    return load()
