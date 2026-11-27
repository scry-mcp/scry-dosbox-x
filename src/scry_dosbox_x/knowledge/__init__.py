"""The IBM PC's dictionaries and the shared chips as rows, loaded once, serving only what is
sealed."""

from __future__ import annotations

from functools import cache
from importlib import resources

from scry_core.knowledge import base as rows
from scry_core.knowledge import quote, sealed, shared

from scry_dosbox_x.knowledge.support import PINS

SCOPE = "ibm-pc"
#: Beside `knowledge_rows/`, for the same reason.
ROWS_LOCK = "knowledge_index/rows-lock.json"
ROWS_INDEX = "knowledge_index/quotes.json"
ROWS_SOURCES = ("scry_dosbox_x", "scry_core")


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


def rows_index() -> quote.Quotes:
    """The index of this server's quotes and of the shared dictionaries'."""
    own = resources.files("scry_dosbox_x") / ROWS_INDEX
    return quote.merge(quote.parse_quotes(own.read_text(encoding="utf-8"), ROWS_INDEX),
                       shared.rows_index())


def rows_base(fts5: bool | None = None) -> rows.Base:
    return rows.Base.load(*ROWS_SOURCES, lock=rows_lock(), fts5=fts5, pins=PINS)


@cache
def base() -> rows.Base:
    return rows_base()
