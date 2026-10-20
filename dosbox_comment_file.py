"""THE COMMENT FILE: one line per comment, the record a project versions beside its symbol file.

    # comments v1: ref<TAB>cpu<TAB>created_at<TAB>text
    0814:010B<TAB><TAB>2026-10-03T06:00:00+00:00<TAB>the counter's first store
    start<TAB><TAB>2026-10-03T06:00:12+00:00<TAB>entry point: sets up the counter

The format is `scry_core.comment_file`'s, which every reader of version 1 shares; this module is
this server's half of it: a ref as a file spells it here (a symbol or a raw `SEG:OFF`) and the cpu
column. The column belongs to the format, which also serves machines with more than one
processor; this server drives one, writes it empty, and refuses a file that fills it, since a row
for a processor it does not have could only be placed somewhere it was not meant. What a ref
names, where it lands and whether two spellings alias one place are the server's, which holds the
table and the machine.
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

#: A raw address as a file spells it: hex digits either side of the one colon, no `0x`.
_SEG_OFF = re.compile(r"([0-9A-Fa-f]+):([0-9A-Fa-f]+)")


def ref_fault(ref: str) -> str | None:
    """What a ref breaks, or None. A ref is a symbol or a raw `SEG:OFF`, and the colon is what
    tells them apart without the table: with one, hex digits either side and the segment within
    sixteen bits; without one, a name. Either way no whitespace or unprintable character, no
    leading `#` (a reader skips that line as a comment), and none of the forms a place that
    moves at run time is written in: a pointer (`[` `]`, `->`), an offset added (`+`), or a
    `0x` prefix, since an address here always carries its segment."""
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
    if ref.lower().startswith("0x"):
        return f"{ref!r} is a bare number; an address here is a SEG:OFF in hex, as 0814:010B"
    if ":" not in ref:
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
    """What the cpu column breaks, or None: this server writes it empty and reads it empty."""
    return None if cpu == "" else (f"column is {cpu!r}; this server drives one processor and "
                                   "writes the column empty")


POLICY = core.Policy(ref_fault=ref_fault, cpu_fault=cpu_fault)


def parse(text: str, where: str = "the comment file") -> list[Row]:
    """Every row of a comment file's text, or the refusal naming the first line that breaks the
    format (`scry_core.comment_file.parse`), held to this server's columns."""
    return core.parse(text, where, POLICY)


def render(rows: list[Row]) -> str:
    """The file's text for `rows` (`scry_core.comment_file.render`), held to this server's
    columns."""
    return core.render(rows, POLICY)
