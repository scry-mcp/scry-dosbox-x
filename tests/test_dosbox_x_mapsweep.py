from __future__ import annotations

import json
from pathlib import Path

import pytest

import mapsweep

# Both publics sections print the same set, so de-duplication is exercised.
SMALL_MAP = (
    "\r\n"
    " Start  Stop   Length Name               Class\r\n"
    "\r\n"
    " 00000H 0ACD7H 0ACD8H _TEXT              CODE\r\n"
    "\r\n"
    "Detailed map of segments\r\n"
    "\r\n"
    " 0000:0000 0036 C=CODE   S=SFMAIN_TEXT    G=(none)  M=SFMAIN.ASM ACBP=48\r\n"
    "\r\n"
    "  Address         Publics by Name\r\n"
    "\r\n"
    " 0D74:00E21 idle  ACTIVEIMAN\r\n"
    " 0459:00123       ACTIVE_CLS\r\n"
    " 1247:0DFEB       ANIMPLANE\r\n"
    " 0459:00456       ANIMSHIP\r\n"
    "\r\n"
    "  Address         Publics by Value\r\n"
    "\r\n"
    " 0459:00123       ACTIVE_CLS\r\n"
    " 0459:00456       ANIMSHIP\r\n"
    " 0D74:00E21 idle  ACTIVEIMAN\r\n"
    " 1247:0DFEB       ANIMPLANE\r\n"
    "\r\n"
    "Program entry point at 0000:0000\r\n")


def _rows_replaced(text: str, old: str, new: str, count: int) -> str:
    """`text` with `old` replaced, asserted present `count` times (a no-op would pass silently)."""
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


# One symbol in both tables with an offset wider than 16 bits: a row by shape, not a symbol.
MAP_WITH_A_BAD_ROW = _rows_replaced(SMALL_MAP, " 0459:00123       ACTIVE_CLS\r\n",
                                    " 0459:1FFFF       ACTIVE_CLS\r\n", 2)

NO_PUBLICS_MAP = (
    "\r\n"
    " Start  Stop   Length Name               Class\r\n"
    "\r\n"
    " 00000H 0ACD7H 0ACD8H _TEXT              CODE\r\n"
    "\r\n"
    "Program entry point at 0000:0000\r\n")

NM_TEXT = (
    "0001c2b0 T _main\n"
    "0001c300 T _helper\n"
    "0001c340 D _table\n")


def _tree(tmp_path: Path, files: dict[str, str],
          manifest: dict[str, object]) -> tuple[Path, Path]:
    """A root holding the named files, and a manifest beside it. Returns (root, manifest)."""
    root = tmp_path / "root"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="latin-1")
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps(manifest), encoding="utf-8")
    return root, mf


def _run(root: Path, manifest: Path, *extra: str) -> tuple[int, str]:
    out: list[str] = []
    rc = mapsweep.main(["--root", str(root), "--manifest", str(manifest), *extra],
                       write=out.append)
    return rc, "\n".join(out)


def test_a_project_matching_its_expectation_is_green_and_says_what_it_read(
        tmp_path: Path) -> None:
    """The report carries symbols, overlay_idle and unreadable together."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 4, "overlay_idle": 1, "unreadable": 0}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "symbols=4" in out, out
    assert "overlay_idle=1" in out, out
    assert "unreadable=0" in out, out


def test_the_format_it_chose_is_reported_and_not_left_to_be_inferred(
        tmp_path: Path) -> None:
    """The format is sniffed from content, so the report names which reader ran."""
    root, mf = _tree(tmp_path,
                     {"proj/A.MAP": SMALL_MAP, "proj/B.SYM": NM_TEXT},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.SYM", "expect": {"symbols": 3}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "borland-tlink" in out, out
    assert "nm" in out, out


def test_a_symbol_count_that_moved_is_red_and_names_the_project(tmp_path: Path) -> None:
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 5}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    # The whole line: a bare name or axis also appears on green lines and in DISAGREES.
    assert "DISAGREES  ZULU: symbols: expected 5, read 4" in out, out


def test_an_overlay_count_that_moved_is_red_on_its_own(tmp_path: Path) -> None:
    """A total cannot see overlay_idle drifting alone."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 4, "overlay_idle": 0}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    assert "ZULU: overlay_idle: expected 0, read 1" in out, out


def test_an_unreadable_count_that_moved_is_red_on_its_own(tmp_path: Path) -> None:
    """An expectation written after a loss would hide it from the symbol count."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": MAP_WITH_A_BAD_ROW},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 3, "unreadable": 0}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    assert "ZULU: unreadable: expected 0, read 2" in out, out


def test_the_rows_it_could_not_place_are_quoted_and_not_merely_counted(
        tmp_path: Path) -> None:
    """A count says something was lost; the quoted row says what."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": MAP_WITH_A_BAD_ROW},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 3, "unreadable": 2}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "1FFFF" in out, f"the row itself is not in the report: {out}"


def test_a_project_expected_to_be_refused_is_green_when_it_is(tmp_path: Path) -> None:
    """A map with no publics is a known state, so it can be green."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                            "expect": {"refused": "no `Publics by ...` header"}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "refused" in out.lower(), out
    assert "borland-tlink" in out, out


def test_a_refusal_whose_reason_changed_is_red(tmp_path: Path) -> None:
    """The expectation is the message, or any new failure would pass as the known one."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                            "expect": {"refused": "some other reason entirely"}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    assert "some other reason entirely" in out, out
    assert "not for the expected reason" in out, out


def test_a_refusal_where_symbols_were_expected_is_red_and_quotes_the_reason(
        tmp_path: Path) -> None:
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP", "expect": {"symbols": 12}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    assert "Publics by" in out, out


def test_a_path_that_is_not_there_is_invalid_and_never_green(tmp_path: Path) -> None:
    """3 and not 1: "I did not read the map" is not a finding about the reader."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "GONE": {"path": "proj/NOPE.MAP", "expect": {"symbols": 1}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "NOPE.MAP" in out, out
    assert "is not a file" in out, out
    assert "NOT swept" in out, out


def test_a_manifest_with_no_projects_is_invalid(tmp_path: Path) -> None:
    """An instrument that examined nothing reports INVALID."""
    root, mf = _tree(tmp_path, {}, {})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "names no project" in out, out


def test_a_manifest_that_will_not_parse_is_invalid(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    mf = tmp_path / "manifest.json"
    mf.write_text("{ this is not json", encoding="utf-8")
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "will not parse as JSON" in out, out


def test_a_missing_manifest_is_invalid(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, tmp_path / "nope.json")
    assert rc == 3, out
    assert "cannot read the manifest" in out, out


def test_a_project_with_no_expectation_at_all_is_invalid(tmp_path: Path) -> None:
    """A row asserting nothing sits outside the control and prints like a pass."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "expects nothing" in out, out


def test_a_selection_that_matches_no_project_is_invalid(tmp_path: Path) -> None:
    """A scope that selected nothing must not read as everything passing."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    rc, out = _run(root, mf, "--project", "TYPO")
    assert rc == 3, out
    # Names the typo rather than the generic "matched no project".
    assert "TYPO" in out, out


def test_no_root_at_all_is_invalid_rather_than_reading_relative_to_the_cwd(
        tmp_path: Path) -> None:
    """A relative path must not resolve against the caller's cwd."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    lines: list[str] = []
    rc = mapsweep.main(["--manifest", str(mf)], write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 3, out
    assert "no root" in out, out


def test_project_selects_one_and_leaves_the_others_unread(tmp_path: Path) -> None:
    root, mf = _tree(tmp_path,
                     {"proj/A.MAP": SMALL_MAP, "proj/B.SYM": NM_TEXT},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.SYM", "expect": {"symbols": 999}}})
    rc, out = _run(root, mf, "--project", "ZULU")
    assert rc == 0, out
    assert "YANKEE" not in out and "B.SYM" not in out, out


def test_an_unknown_option_exits_rather_than_being_ignored(tmp_path: Path) -> None:
    """An ignored option would leave a default silently in force."""
    out: list[str] = []
    rc = mapsweep.main(["--nonsense"], write=out.append, env={})
    assert rc == 2 and any("--nonsense" in line for line in out), out


def test_argparses_own_words_reach_the_transcript_and_not_the_process(
        capsys: pytest.CaptureFixture[str]) -> None:
    """argparse output, help included, goes through `write` only."""
    out: list[str] = []
    assert mapsweep.main(["--help"], write=out.append, env={}) == mapsweep.OK
    assert any("--manifest" in line for line in out), out
    assert capsys.readouterr() == ("", "")


def test_a_key_beginning_with_an_underscore_is_a_note_and_not_a_project(
        tmp_path: Path) -> None:
    """JSON has no comments, so a `_` key is prose; any other key stays a project."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"_why": ["this row explains the next one"],
                      "ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "_why" not in out, out


def test_a_manifest_of_nothing_but_notes_is_invalid(tmp_path: Path) -> None:
    """A manifest of only prose examined nothing."""
    root, mf = _tree(tmp_path, {}, {"_why": ["prose"], "_and": ["more prose"]})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "names no project" in out, out


def test_an_unknown_expect_key_is_invalid_and_names_it(tmp_path: Path) -> None:
    """A misspelled key asserts nothing while looking like an assertion."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbolz": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "symbolz" in out and "does not check" in out, out


def test_a_row_with_no_path_is_invalid_and_names_the_project(tmp_path: Path) -> None:
    """A row without a path is INVALID."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "ZULU" in out and "no `path`" in out, out


def test_more_unreadable_rows_than_it_quotes_says_how_many_it_withheld(
        tmp_path: Path) -> None:
    """Truncating the quoted rows says how many were withheld."""
    rows = "".join(f" 0001:0000{i:04X}       _plain{i}\r\n" for i in range(9))
    rows += "".join(f" 0459:1FFF{i:01X}       _wide{i}\r\n" for i in range(5))
    root, mf = _tree(tmp_path, {"proj/A.MAP":
                                "  Address         Publics by Name\r\n\r\n" + rows},
                     {"ZULU": {"path": "proj/A.MAP",
                               "expect": {"symbols": 9, "unreadable": 5}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert out.count("unread line:") == 3, out
    assert "and 2 more row(s) not quoted here" in out, out


def test_a_refused_file_still_quotes_the_rows_it_could_not_place(tmp_path: Path) -> None:
    """A file refused for losing more rows than it kept still quotes them."""
    rows = "".join(f" 0001:0000{i:04X}       _plain{i}\r\n" for i in range(2))
    rows += "".join(f" 0459:1FFF{i:01X}       _wide{i}\r\n" for i in range(5))
    root, mf = _tree(tmp_path, {"proj/A.MAP":
                                "  Address         Publics by Name\r\n\r\n" + rows},
                     {"ZULU": {"path": "proj/A.MAP",
                               "expect": {"refused": "MORE WAS DISCARDED THAN KEPT"}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "unread line:  0459:1FFF0" in out, out


def test_one_unreadable_path_does_not_discard_the_projects_already_read(
        tmp_path: Path) -> None:
    """The first missing file must not discard the projects already read."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "GONE": {"path": "proj/NOPE.MAP", "expect": {"symbols": 1}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "ZULU         borland-tlink  symbols=4" in out, out
    assert "NOPE.MAP" in out and "is not a file" in out, out
    assert "could NOT be examined" in out, out


def test_the_header_says_how_many_rows_the_manifest_held(tmp_path: Path) -> None:
    """The header carries the denominator, since notes and duplicate keys drop rows."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP, "proj/B.MAP": SMALL_MAP},
                     {"_why": ["prose"],
                      "ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.MAP", "expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "2 of 2 project(s) under" in out, out
    assert "1 note row(s) skipped" in out, out


def test_selecting_one_project_says_so_against_the_whole_manifest(
        tmp_path: Path) -> None:
    """`--project` must not claim the whole manifest was satisfied."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP, "proj/B.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.MAP", "expect": {"symbols": 999}}})
    rc, out = _run(root, mf, "--project", "ZULU")
    assert rc == 0, out
    assert "1 of 2 project(s) as the manifest says" in out, out


def test_a_tilde_that_cannot_be_resolved_is_invalid_and_not_a_red(
        tmp_path: Path) -> None:
    """`expanduser()` raises on an unknown user; that is INVALID, not red."""
    lines: list[str] = []
    rc = mapsweep.main(["--manifest", "~nosuchuser4242/m.json", "--root", str(tmp_path)],
                       write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 3, out
    assert "cannot resolve" in out or "cannot read the manifest" in out, out


def test_a_manifest_path_that_escapes_the_root_is_invalid(tmp_path: Path) -> None:
    """pathlib discards the root for an absolute path, and `..` walks out."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": str(tmp_path / "root" / "proj" / "A.MAP"),
                               "expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "not relative to the root" in out, out


def test_an_expectation_that_is_not_a_number_is_invalid(tmp_path: Path) -> None:
    """JSON `true` compares equal to 1, so a bool must not pin a count."""
    for bad in (True, "4", 4.5, None):
        root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                         {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": bad}}})
        rc, out = _run(root, mf)
        assert rc == 3, (bad, out)
        assert "not a whole number" in out, (bad, out)


def test_an_empty_refused_string_is_invalid_because_it_matches_everything(
        tmp_path: Path) -> None:
    """`"" in anything` is True, so an empty string would accept every refusal."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP", "expect": {"refused": ""}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "NON-EMPTY string" in out, out


def test_expecting_a_refusal_and_a_count_together_is_invalid(tmp_path: Path) -> None:
    """The refusal branch skips the numeric comparison, so the combination is refused."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                               "expect": {"refused": "no `Publics by ...` header",
                                          "symbols": 99999}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "expects a refusal AND" in out, out


def test_a_usage_error_reaches_the_caller_through_the_write_seam(tmp_path: Path) -> None:
    """A usage error names the bad argument in the transcript."""
    lines: list[str] = []
    rc = mapsweep.main(["--nonsense"], write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 2, out
    assert "nonsense" in out, out
