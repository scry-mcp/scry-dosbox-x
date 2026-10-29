"""This server's half of the version 1 comment file format (`scry_core.comment_file`).

The cpu column is always empty here: this server drives one processor and refuses a filled one.
"""

from __future__ import annotations

import re

from scry_core import comment_file as core
from scry_core.comment_file import (
    HEADER,
    TEXT_MAX_BYTES,
    CommentFileError,
    Row,
    stamp_fault,
    text_fault,
)

__all__ = ["HEADER", "TEXT_MAX_BYTES", "CommentFileError", "Row", "cpu_fault", "parse",
           "ref_fault", "render", "stamp_fault", "text_fault"]

_SEG_OFF = re.compile(r"(?:0[xX])?([0-9A-Fa-f]+):(?:0[xX])?([0-9A-Fa-f]+)")


def ref_fault(ref: str) -> str | None:
    """What a ref breaks, or None: a symbol or a raw `SEG:OFF`, never a run-time place."""
    if ref == "":
        return "is empty"
    if ref[0] == "#":
        return "starts with `#`, which a reader skips as a comment line"
    if any(c.isspace() or not c.isprintable() for c in ref):
        return "holds whitespace or a character that is not printable"
    if any(mark in ref for mark in ("[", "]", "->")):
        return (f"{ref!r} is a pointer, a place read at run time; a comment names a place that "
                "stays put: a symbol or a SEG:OFF")
    if "+" in ref:
        return (f"{ref!r} adds an offset; a comment names a symbol or a SEG:OFF as it stands, "
                "so name the address itself")
    if ":" not in ref:
        if ref.lower().startswith("0x"):
            return (f"{ref!r} is a bare number; an address here is a SEG:OFF in hex, as "
                    "0814:010B")
        return None
    m = _SEG_OFF.fullmatch(ref)
    if m is None:
        return f"{ref!r} has a colon, so it is an address, and is not a hex SEG:OFF"
    if int(m.group(1), 16) > 0xFFFF:
        return f"{ref!r} has a segment past 0xFFFF"
    if int(m.group(2), 16) > 0xFFFFFFFF:
        return f"{ref!r} has an offset past 0xFFFFFFFF"
    return None


def cpu_fault(cpu: str) -> str | None:
    """What the cpu column breaks, or None."""
    return None if cpu == "" else (f"column is {cpu!r}; this server drives one processor and "
                                   "writes the column empty")


POLICY = core.Policy(ref_fault=ref_fault, cpu_fault=cpu_fault)


parse, render = POLICY.parse, POLICY.render
