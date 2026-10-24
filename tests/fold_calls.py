"""A tool a test walks by name, a fold named with its selector, `<tool> <value>` (`comment_write
save`, `declaration_list watch`): the value is the fold's `kind` for the declarations, its
`method` otherwise."""

from __future__ import annotations

import functools
from types import ModuleType
from typing import Any


def of(server: ModuleType, name: str) -> Any:
    """`name`'s tool on `server`, its selector bound when `name` is a fold's."""
    tool, _, value = name.partition(" ")
    fn = getattr(server, tool)
    if not value:
        return fn
    return functools.partial(fn, **{"kind" if tool.startswith("declaration_") else "method": value})
