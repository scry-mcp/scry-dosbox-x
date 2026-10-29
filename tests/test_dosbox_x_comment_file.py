"""The comment file as this server reads and writes it (`comment_file`): one known answer
written by an independent writer, and one case per rule of the format."""
from __future__ import annotations

from pathlib import Path

import pytest
from scry_core import prose

from scry_dosbox_x import comment_file as cf
from scry_dosbox_x import server as dosbox_x_server  # noqa: F401 -- imports the envelope and the boundary the shape guard wraps

KNOWN = Path(__file__).parent / "fixtures" / "comments" / "known.comments.tsv"
STAMP = "2026-10-03T06:00:00+00:00"


def _file(*rows: str) -> str:
    return cf.HEADER + "\n" + "".join(r + "\n" for r in rows)


def _refused(text: str) -> str:
    with pytest.raises(cf.CommentFileError) as caught:
        cf.parse(text, "c.tsv")
    return str(caught.value)


# THE KNOWN ANSWER. The fixture is the format's known answer, written by an independent
# implementation of version 1 from the row set below, never by this module: a reader and writer
# that agree only with themselves would prove nothing about the format.
KNOWN_ROWS = [
    cf.Row("start", "", "2026-10-03T06:00:00+00:00", "entry point: sets up the counter"),
    cf.Row("_start", "", "2026-10-03T06:00:01+02:00", "C runtime entry, before main"),
    cf.Row("Start", "", "2026-10-03T06:00:02-05:00", "upper case is another symbol"),
    cf.Row("0814:010B", "", "2026-10-03T06:00:03+00:00", "raw address, canonical spelling"),
    cf.Row("emit", "", "2026-10-03T06:00:04.123456+00:00",
           "écrit l'octet au port E9 \U0001d11e señal ✓"),
    cf.Row("COMPOSE_FRAME", "", "2026-10-03T06:00:05+00:00", "é" * 118 + "x"),
    cf.Row("00A7:0045F880", "", "2026-10-03T06:00:06+00:00", "a 32-bit offset keeps its width"),
]


def test_rendering_the_known_rows_gives_the_known_file_byte_for_byte() -> None:
    assert cf.render(KNOWN_ROWS).encode("utf-8") == KNOWN.read_bytes()


def test_parsing_the_known_file_gives_the_known_rows_back_in_file_order() -> None:
    rows = cf.parse(KNOWN.read_bytes().decode("utf-8"))
    assert rows == sorted(KNOWN_ROWS, key=lambda r: (r.cpu, r.ref))
    assert [r.line for r in rows] == list(range(2, 2 + len(KNOWN_ROWS)))


def test_rows_are_written_in_code_point_order_digits_upper_underscore_lower() -> None:
    order = [line.split("\t")[0] for line in cf.render(KNOWN_ROWS).splitlines()[1:]]
    assert order == ["00A7:0045F880", "0814:010B", "COMPOSE_FRAME", "Start", "_start", "emit",
                     "start"]


def test_the_longest_text_is_the_formats_bound_in_bytes() -> None:
    assert cf.text_fault("é" * 118 + "x") is None
    assert "238 UTF-8 bytes" in str(cf.text_fault("é" * 119))
    assert cf.text_fault("x" * 237) is None


# THE HEADER.
def test_the_header_is_exact() -> None:
    assert "c.tsv:1" in _refused("# comments v2: ref\tcpu\tcreated_at\ttext\n")
    assert "c.tsv:1" in _refused("")
    assert "c.tsv:1" in _refused(cf.HEADER + " \n")


def test_a_byte_order_mark_before_the_header_is_refused_by_name() -> None:
    assert "byte order mark" in _refused("\ufeff" + _file())


def test_a_header_alone_is_an_empty_file() -> None:
    assert cf.parse(cf.HEADER + "\n") == []
    assert cf.render([]) == cf.HEADER + "\n"


# THE COLUMNS.
@pytest.mark.parametrize("line, columns", [("start", 1), ("start\t", 2),
                                           (f"start\t\t{STAMP}", 3)])
def test_a_row_of_fewer_than_four_columns_is_refused_naming_its_line(line: str,
                                                                    columns: int) -> None:
    assert ("c.tsv:2: a row is ref, cpu, created_at and text separated by tabs; this one has "
            + prose.counted(columns, "column")) in _refused(_file(line))


def test_the_text_is_the_rest_of_the_line_after_the_third_tab() -> None:
    (row,) = cf.parse(_file(f"start\t\t{STAMP}\ta: b"))
    assert row.text == "a: b"
    assert "c.tsv:2: the text" in _refused(_file(f"start\t\t{STAMP}\ta\tb"))


def test_a_cpu_column_filled_is_refused_this_server_has_one_processor() -> None:
    message = _refused(_file(f"start\t:maincpu\t{STAMP}\tentry"))
    assert "c.tsv:2: the cpu column" in message and "one processor" in message


# THE STAMP.
@pytest.mark.parametrize("stamp", ["2026-10-03T06:00:00", "2026-10-03 06:00:00+00:00",
                                   "2026-10-03", "yesterday", "",
                                   "2026-13-03T06:00:00+00:00", "Tuesday"])
def test_a_stamp_without_a_time_an_offset_or_the_t_is_refused(stamp: str) -> None:
    assert "c.tsv:2: the created_at" in _refused(_file(f"start\t\t{stamp}\tentry"))


@pytest.mark.parametrize("stamp", ["2026-10-03T06:00:00.5+00:00", "2026-10-03T06:00:00-05:30",
                                   "2026-10-03T06:00:00Z"])
def test_a_stamp_with_fractions_and_any_offset_is_taken(stamp: str) -> None:
    assert cf.parse(_file(f"start\t\t{stamp}\tentry"))[0].created_at == stamp


# THE TEXT.
@pytest.mark.parametrize("text, said", [
    ("", "is empty"), ("a\x07b", "not printable"), ("a\u2028b", "not printable"),
    (" entry", "whitespace"), ("entry ", "whitespace"), ("entry\u00a0", "not printable"),
    ("x" * 238, "238 UTF-8 bytes")])
def test_a_text_that_is_not_one_visible_line_is_refused(text: str, said: str) -> None:
    fault = cf.text_fault(text)
    assert fault is not None and said in fault
    assert "c.tsv:2: the text" in _refused(_file(f"start\t\t{STAMP}\t{text}"))


def test_a_text_with_a_tab_is_refused_in_a_row_to_write() -> None:
    with pytest.raises(cf.CommentFileError, match="the text"):
        cf.render([cf.Row("start", "", STAMP, "a\tb")])


# THE REF.
@pytest.mark.parametrize("ref", ["0x0814:010B", "0814:0x010B", "0X00A7:0X0000204B"])
def test_a_seg_off_with_0x_halves_is_the_spelling_a_register_reads_back_and_is_taken(
        ref: str) -> None:
    """`registers` answers `CS` as `0x0814`, so a ref built from it carries the prefix: it is a
    SEG:OFF all the same, as every other address argument takes it."""
    assert cf.ref_fault(ref) is None


@pytest.mark.parametrize("ref, said", [
    ("#start", "`#`"), ("st art", "whitespace"), ("st\u00a0art", "whitespace"),
    ("[g_p]", "pointer"), ("[g_p]+4", "pointer"), ("g_p->x", "pointer"),
    ("g_p[0", "pointer"), ("g_p]", "pointer"),
    ("start+2", "adds an offset"), ("0x824B", "bare number"), ("0X824B", "bare number"),
    ("0814:", "not a hex SEG:OFF"), ("0814:01G0", "not a hex SEG:OFF"),
    ("ns::fn", "not a hex SEG:OFF"), ("0x0814:0x", "not a hex SEG:OFF"),
    ("10000:0000", "segment past"), ("0814:100000000", "offset past")])
def test_a_ref_that_is_not_a_symbol_or_a_seg_off_is_refused(ref: str, said: str) -> None:
    fault = cf.ref_fault(ref)
    assert fault is not None and said in fault
    if ref.startswith("#"):
        # A READER SKIPS THAT LINE as a note, which is exactly why a writer may not emit it.
        assert cf.parse(_file(f"{ref}\t\t{STAMP}\tentry")) == []
        with pytest.raises(cf.CommentFileError, match="the ref starts with `#`"):
            cf.render([cf.Row(ref, "", STAMP, "entry")])
    else:
        assert "c.tsv:2: the ref" in _refused(_file(f"{ref}\t\t{STAMP}\tentry"))


def test_an_empty_ref_is_refused() -> None:
    assert cf.ref_fault("") == "is empty"
    with pytest.raises(cf.CommentFileError, match="the ref is empty"):
        cf.render([cf.Row("", "", STAMP, "entry")])


@pytest.mark.parametrize("ref", ["start", "_g_eng_rate", "COMPOSE_FRAME", "814:10b",
                                 "0814:010B", "00A7:0045F880", "FFFF:FFFFFFFF", "a.b$c@d"])
def test_a_symbol_or_a_hex_seg_off_is_a_ref(ref: str) -> None:
    assert cf.ref_fault(ref) is None


# ONE REF TWICE: the format keys a row by its ref, which is what the refusal says; which refs
# alias one place is the server's question, not the file's.
def test_one_ref_on_two_lines_is_refused_naming_both() -> None:
    message = _refused(_file(f"start\t\t{STAMP}\ta", f"emit\t\t{STAMP}\tb",
                             f"start\t\t{STAMP}\tc"))
    assert "c.tsv:4" in message and "line 2" in message
    assert "one comment per ref" in message and "place" not in message


def test_one_ref_twice_is_refused_in_rows_to_write() -> None:
    with pytest.raises(cf.CommentFileError, match="twice: a file holds one comment per ref$"):
        cf.render([cf.Row("start", "", STAMP, "a"), cf.Row("emit", "", STAMP, "b"),
                   cf.Row("start", "", STAMP, "c")])


# LINE ENDS AND SKIPPED LINES.
def test_crlf_reads_as_lf() -> None:
    crlf = _file(f"start\t\t{STAMP}\tentry").replace("\n", "\r\n")
    assert cf.parse(crlf) == [cf.Row("start", "", STAMP, "entry")]


def test_a_lone_carriage_return_is_refused_not_taken_for_a_line_break() -> None:
    assert "c.tsv:2: a carriage return" in _refused(
        _file(f"start\t\t{STAMP}\tentry\remit\t\t{STAMP}\tx"))


def test_blank_lines_and_hash_lines_after_the_header_are_skipped() -> None:
    text = _file("", " \t ", "# a note the project keeps", f"start\t\t{STAMP}\tentry", "#")
    (row,) = cf.parse(text)
    assert (row.ref, row.line) == ("start", 5)


def test_only_spaces_and_tabs_make_a_blank_line_any_other_blank_is_a_row() -> None:
    assert "c.tsv:2: a row is ref" in _refused(_file("\x0c"))


def test_a_file_without_its_final_newline_still_reads() -> None:
    assert cf.parse(cf.HEADER + f"\nstart\t\t{STAMP}\tentry") == [
        cf.Row("start", "", STAMP, "entry")]


# THE WRITER REFUSES WHAT THE READER WOULD.
@pytest.mark.parametrize("row", [
    cf.Row("start+2", "", STAMP, "x"), cf.Row("start", "cpu", STAMP, "x"),
    cf.Row("start", "", "2026-10-03", "x"), cf.Row("start", "", STAMP, " x"),
    cf.Row("start", "", STAMP, "x" * 238), cf.Row("0814:01G0", "", STAMP, "x")])
def test_render_refuses_every_row_parse_would_refuse(row: cf.Row) -> None:
    with pytest.raises(cf.CommentFileError):
        cf.render([row])
    line = "\t".join((row.ref, row.cpu, row.created_at, row.text))
    _refused(_file(line))


def test_what_render_writes_parse_reads_back() -> None:
    rows = [cf.Row("emit", "", STAMP, "b"), cf.Row("0814:010B", "", STAMP, "a")]
    assert cf.parse(cf.render(rows)) == sorted(rows, key=lambda r: r.ref)


def test_a_lone_surrogate_is_refused_as_unprintable_not_raised_as_an_encoding_error() -> None:
    assert "not printable" in str(cf.text_fault("a\udc80"))
    assert "c.tsv:2: the text" in _refused(_file(f"start\t\t{STAMP}\ta\udc80"))
    with pytest.raises(cf.CommentFileError, match="the text"):
        cf.render([cf.Row("start", "", STAMP, "a\ud800")])


def test_every_accepted_ref_and_text_written_together_reads_back_whole() -> None:
    refs = ["start", "_g_eng_rate", "COMPOSE_FRAME", "814:10b", "0814:010B", "00A7:0045F880",
            "FFFF:FFFFFFFF", "a.b$c@d"]
    texts = ["x", "é" * 118 + "x", "\U0001d11e" * 59 + "x", "a: b", "entry, aliased"]
    rows = [cf.Row(ref, "", STAMP, texts[i % len(texts)]) for i, ref in enumerate(refs)]
    assert cf.parse(cf.render(rows)) == sorted(rows, key=lambda r: r.ref)


@pytest.mark.parametrize("ref", ["814:10b", "0814:010B", "00A7:0045F880", "FFFF:FFFFFFFF",
                                 "0:0"])
def test_every_address_the_rule_takes_is_one_the_placement_parser_parses(ref: str) -> None:
    """The rule judges the spelling and the placement parser makes the numbers: an address the
    rule let through and the parser refused would pass every check and fail at its place."""
    from scry_dosbox_x import placement
    assert cf.ref_fault(ref) is None
    seg, off = placement.parse_seg_off(ref)
    assert f"{seg:X}:{off:X}" == ":".join(f"{int(h, 16):X}" for h in ref.split(":"))
