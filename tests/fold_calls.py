"""`<tool> <value>` binds a fold's selector."""

from __future__ import annotations

import functools
from types import ModuleType
from typing import Any


def of(server: ModuleType, name: str) -> Any:
    tool, _, value = name.partition(" ")
    fn = getattr(server, tool)
    if not value:
        return fn
    return functools.partial(fn, **{"kind" if tool.startswith("declaration_") else "method": value})
