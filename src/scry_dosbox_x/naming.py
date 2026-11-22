"""What a number is called on this machine."""

from __future__ import annotations

from collections.abc import Mapping

from scry_core import naming
from scry_core.knowledge import Base
from scry_core.naming import Named

from scry_dosbox_x import knowledge

#: The XMS driver's key borrows its multiplex number, and it is called far: INT 43h is no call.
XMS_KEY = 0x43


def interrupt_call(base: Base, interrupt: int, registers: Mapping[str, int]) -> Named | None:
    if interrupt == XMS_KEY:
        return None
    return naming.named_call(base, knowledge.SCOPE, interrupt, registers)
