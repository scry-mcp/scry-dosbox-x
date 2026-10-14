"""THE COMMENT FILE: one line per comment, the record a project versions beside its symbol file.

    # comments v1: ref<TAB>cpu<TAB>created_at<TAB>text
    0814:010B<TAB><TAB>2026-10-03T06:00:00+00:00<TAB>the counter's first store
    start<TAB><TAB>2026-10-03T06:00:12+00:00<TAB>entry point: sets up the counter

Four fields split on the first three tabs, the text LAST, so the text is the rest of the line
and nothing in it is ever quoted or escaped; a comment cannot hold a tab or a newline, which the
text rule refuses with every other character that is not printable. Rows are written sorted by
cpu, then ref, in code-point order, so saving again moves nothing that did not change and a
`git diff` of the file shows exactly the comments that did. There is no column for the build: a
raw address read into another build is trusted for it, which is why a comment meant to survive a
rebuild is made by symbol.

The `cpu` column belongs to the format, which also serves machines with more than one processor.
This server drives one, writes the column empty, and refuses a file that fills it, since a row
for a processor it does not have could only be placed somewhere it was not meant.

This module judges the FILE and nothing else: the header, the columns, a text, a ref and a stamp
as a file spells them, one (ref, cpu) twice. What a ref names, where it lands and whether two
spellings alias one place are the server's, which holds the table and the machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

#: Line 1, exactly: the version mark a reader checks before anything else.
HEADER = "# comments v1: ref\tcpu\tcreated_at\ttext"
# THE LONGEST TEXT, IN UTF-8 BYTES, is the format's and not this server's: version 1 holds a text
# to this bound, so a file written here is one every reader of version 1 takes, and a reader with
# a looser bound would write files the others refuse. Bytes and not characters, because a file is
# bytes and the bound has to mean the same thing to every reader whatever it counts in.
TEXT_MAX_BYTES = 237
_BOM = "\ufeff"
#: A raw address as a file spells it: hex digits either side of the one colon, no `0x`.
_SEG_OFF = re.compile(r"([0-9A-Fa-f]+):([0-9A-Fa-f]+)")


@dataclass(frozen=True)
class Row:
    """The four columns of one comment line, in file order, plus where it was read."""

    ref: str
    cpu: str
    created_at: str
    text: str
    #: Which line of the file held it (2 is the first after the header), so a refusal of the
    #: row can point at it; 0 when the row was built in memory and never read.
    line: int = field(default=0, compare=False)


class CommentFileError(ValueError):
    """Raised by `parse` for text that is not a comment file and by `render` for rows that would
    not make one; the message says which line, or which ref, and why."""


def text_fault(text: str) -> str | None:
    """Why `text` cannot be a comment, or None when it can. A comment is one visible line: not
    empty, every character printable (so no tab or line break), no blank at either end, and no
    longer than `TEXT_MAX_BYTES` once encoded. A call, the store and a file all ask this."""
    unprintable = [c for c in text if not c.isprintable()]
    if text == "":
        return "is empty"
    if unprintable:
        return (f"holds {unprintable[0]!r}, which is not printable: one comment is one line "
                "of text")
    if text[0].isspace() or text[-1].isspace():
        return "starts or ends with whitespace, which nobody reading the file can see"
    # MEASURED LAST: a lone surrogate cannot be encoded at all, and the printable rule has
    # already refused it by name.
    size = len(text.encode("utf-8"))
    if size > TEXT_MAX_BYTES:
        return (f"is {size} UTF-8 bytes, past the {TEXT_MAX_BYTES} a comment file of version 1 "
                "holds")
    return None


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


def stamp_fault(stamp: str) -> str | None:
    """What a `created_at` breaks, or None: a date AND a time with its offset from UTC, the
    store's own stamp, so a file read on another machine means the same instant."""
    wrong = (f"{stamp!r} is not a stamp with a date, a time and an offset from UTC, as "
             "`YYYY-MM-DDTHH:MM:SS+00:00`")
    if "T" not in stamp:
        return wrong
    try:
        return None if datetime.fromisoformat(stamp).utcoffset() is not None else wrong
    except ValueError:
        return wrong


def row_fault(r: Row) -> str | None:
    """What one row breaks, or None, naming its column: the rules `parse` holds a line to and
    `render` holds a row to, so a file this module writes is one it reads."""
    if (fault := ref_fault(r.ref)) is not None:
        return f"the ref {fault}"
    if r.cpu:
        return (f"the cpu column is {r.cpu!r}; this server drives one processor and writes the "
                "column empty")
    if (fault := stamp_fault(r.created_at)) is not None:
        return f"the created_at {fault}"
    if (fault := text_fault(r.text)) is not None:
        return f"the text {fault}"
    return None


def _row_of(line: str, lineno: int, where: str) -> Row | None:
    """The row one line after the header holds, None for a line a reader skips (blank or a
    `#` note), or the refusal naming the line."""
    if "\r" in line:
        raise CommentFileError(f"{where}:{lineno}: a carriage return that does not end the "
                               "line; lines end in LF, or CRLF")
    if line.strip(" \t") == "" or line[0] == "#":
        return None
    ref, sep1, rest = line.partition("\t")
    cpu, sep2, rest = rest.partition("\t")
    stamp, sep3, text = rest.partition("\t")
    if not (sep1 and sep2 and sep3):
        columns = 1 + line.count("\t")
        raise CommentFileError(f"{where}:{lineno}: a row is ref, cpu, created_at and text "
                               f"separated by tabs; this one has {columns} column(s)")
    row = Row(ref, cpu, stamp, text, line=lineno)
    if (fault := row_fault(row)) is not None:
        raise CommentFileError(f"{where}:{lineno}: {fault}")
    return row


def parse(text: str, where: str = "the comment file") -> list[Row]:
    """Every row of a comment file's text, or the refusal naming the first line that breaks the
    format: no header (or another one, or a byte order mark before it), a row of fewer than four
    columns, a row breaking `row_fault`, one (ref, cpu) on two lines. CRLF reads as LF, and a CR
    anywhere else is refused rather than taken for a line break; lines of nothing but spaces and
    tabs, and lines starting with `#`, are skipped after the header. `where` names the file in a
    refusal."""
    first, _, body = text.replace("\r\n", "\n").partition("\n")
    if first != HEADER:
        said = ("starts with a byte order mark" if first[:1] == _BOM
                else f"is {first[:80]!r}")
        raise CommentFileError(f"{where}:1: the first line {said}, and a comment file's is "
                               f"exactly {HEADER!r}")
    rows: list[Row] = []
    line_of: dict[tuple[str, str], int] = {}
    for lineno, line in enumerate(body.split("\n"), 2):
        row = _row_of(line, lineno, where)
        if row is None:
            continue
        held = line_of.setdefault((row.ref, row.cpu), lineno)
        if held != lineno:
            raise CommentFileError(f"{where}:{lineno}: {row.ref!r} again, already on line "
                                   f"{held}: one comment per ref")
        rows.append(row)
    return rows


def render(rows: list[Row]) -> str:
    """The file's text for `rows`: the header, then one line per row sorted by cpu and ref in
    code-point order, every line ended by LF. A row `parse` would refuse (`row_fault`, or one
    (ref, cpu) twice) is refused here instead, so nothing is written that cannot be read back."""
    lines = [HEADER]
    previous: tuple[str, str] | None = None
    # SORTED FIRST, so one (cpu, ref) twice lands on adjacent rows and one look back finds it.
    for r in sorted(rows, key=lambda r: (r.cpu, r.ref)):
        if (fault := row_fault(r)) is not None:
            raise CommentFileError(f"{r.ref!r}: {fault}")
        if previous == (r.cpu, r.ref):
            raise CommentFileError(f"{r.ref!r} twice: a file holds one comment per ref")
        previous = (r.cpu, r.ref)
        lines.append("\t".join((r.ref, r.cpu, r.created_at, r.text)))
    return "\n".join(lines) + "\n"
