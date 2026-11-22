"""The namer over the confirmed base."""

from __future__ import annotations

from scry_dosbox_x import knowledge, naming


def test_an_interrupt_is_named_by_its_function() -> None:
    named = naming.interrupt_call(knowledge.base(), 0x21, {"AX": 0x4C00})
    assert named is not None and (named.name, named.number) == ("exit", "0x21/0x4C")


def test_int_43h_is_not_the_xms_driver() -> None:
    base = knowledge.base()
    assert base.get("call", "0x43/0x08", knowledge.SCOPE) is not None
    assert naming.interrupt_call(base, 0x43, {"AH": 0x08}) is None
