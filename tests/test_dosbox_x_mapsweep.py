"""The sweep: real maps from a caller's own build, read by the shipped reader, against
what they hold.

WHY IT EXISTS AND WHY IT IS NOT ON THE COMMIT PATH.  The package's claim to read a
toolchain rests on five real maps sitting outside this repository -- one of them in a
project that is not published -- and a format is not demonstrated by one file.  So the
sweep reads them where they live and reports per project, and it is declared MANUAL
(`tests/gates-manual.txt`) because on the commit path it would be INVALID in every
clone but this machine's, and a gate that is almost always invalid is one people learn
to ignore.

WHAT THIS FILE TESTS IS THE SWEEP, NOT THE MAPS.  Every case here builds its own tiny
manifest and its own map text under `tmp_path`, so the suite runs on a fresh clone with
none of that material present.  The sweep's own run against the real five is the manual
gate, and its expected numbers live in the manifest rather than here.

THE MANIFEST IS THE ORACLE, and that is the design.  A sweep that merely PRINTS what it
read is an instrument nobody re-reads; one that carries what each project is expected to
hold goes RED when reality and the expectation part company, in either direction.  That
is what makes "REAL16: 294 publics, 82 of them idle, 0 unreadable" a control rather than
a number somebody once wrote down.
"""

from __future__ import annotations

import json
from pathlib import Path

import mapsweep

# A Borland TLINK map with everything the sweep has to account for: a segment table, the
# "Detailed map of segments" trap, both publics sections printing the SAME set (so the
# de-duplication is exercised), one `idle` overlay symbol, and one row that opens like a
# row and cannot be read.  Written here rather than captured because what it must
# reproduce is the SHAPE the sweep reports on; the captured artefacts are the real five,
# which this file deliberately does not touch.
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

# The same map with ONE row this reader cannot place: a real-mode offset wider than the
# sixteen bits it holds.  It is a row by shape and not a symbol, which is precisely the
# distinction the sweep has to be able to REPORT rather than merely count.
MAP_WITH_A_BAD_ROW = SMALL_MAP.replace(
    " 0459:00123       ACTIVE_CLS\r\n",
    " 0459:1FFFF       ACTIVE_CLS\r\n")

# A Borland map that carries NO `Publics by ...` section at all -- which is dos-real16-alt's
# state, measured, and a fact about the LINK rather than about this reader.
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
    """A root holding the named files, and a manifest beside it. Returns (root, manifest).

    The manifest's paths are RELATIVE TO THE ROOT and the root arrives at run time, which
    is not tidiness: a tracked manifest naming an absolute path would carry this machine's
    username and folder layout into a package meant to be published.
    """
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


# --------------------------------------------------------------- the control it exists for

def test_a_project_matching_its_expectation_is_green_and_says_what_it_read(
        tmp_path: Path) -> None:
    """The shape of the real run: symbols, how many are conditional, and what was lost.

    The three numbers are asserted TOGETHER because they are the three the manual gate
    quotes, and a report that prints two of them is a control with a hole in it.
    """
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
    """WHICH READER RAN is half of what a sweep is for.

    The reader sniffs the format from the CONTENT, so a file that landed on the wrong
    parser reports a plausible count out of the wrong walk.  Printing the format is what
    lets a person notice that `nm` output in a file called `.MAP` was read as `nm` -- and
    it is what would have shown the opposite mistake too.
    """
    root, mf = _tree(tmp_path,
                     {"proj/A.MAP": SMALL_MAP, "proj/B.SYM": NM_TEXT},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.SYM", "expect": {"symbols": 3}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "borland-tlink" in out, out
    assert "nm" in out, out


# ----------------------------------------------------- a disagreement, on each axis alone

def test_a_symbol_count_that_moved_is_red_and_names_the_project(tmp_path: Path) -> None:
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 5}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    # THE WHOLE LINE. `assert "A" in out` was the old form and it could not fail: the
    # project was named `A` and `_render` writes the word DISAGREES, which contains one.
    # The one property in this test's name was untested, and so was the AXIS -- `symbols`
    # appears on every green line too. Hence a name no message can spell by accident.
    assert "DISAGREES  ZULU: symbols: expected 5, read 4" in out, out


def test_an_overlay_count_that_moved_is_red_on_its_own(tmp_path: Path) -> None:
    """The IDENTITY axis, and it is the one a total cannot see.

    `symbols` and `overlay_idle` move together under many breaks, so a sweep asserting
    only the total is green while a large part of a real table silently stops being
    flagged as conditional.
    """
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 4, "overlay_idle": 0}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    # THE DISAGREEMENT LINE, not the word: `overlay_idle=N` prints on every green row.
    assert "ZULU: overlay_idle: expected 0, read 1" in out, out


def test_an_unreadable_count_that_moved_is_red_on_its_own(tmp_path: Path) -> None:
    """A row lost on the way in does NOT move the symbol count against an expectation
    written after the loss, which is exactly how an amputation becomes the new normal."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": MAP_WITH_A_BAD_ROW},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 3, "unreadable": 0}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    # Same shape: `unreadable=N` is on every green row, so the axis has to be asserted
    # through the DISAGREES line or the case passes over a report that lost it.
    assert "ZULU: unreadable: expected 0, read 2" in out, out


def test_the_rows_it_could_not_place_are_quoted_and_not_merely_counted(
        tmp_path: Path) -> None:
    """"and which" is the plan's word, and a count cannot answer it.

    A number tells a reader that something was lost; the row tells them WHAT, which is the
    only form in which the loss can be acted on.  MEASURED as the difference that matters:
    `unreadable=2` on the real TLINK32 map says nothing, while one quoted `Idle` row says
    the whole defect.
    """
    root, mf = _tree(tmp_path, {"proj/A.MAP": MAP_WITH_A_BAD_ROW},
                     {"ZULU": {"path": "proj/A.MAP",
                            "expect": {"symbols": 3, "unreadable": 2}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "1FFFF" in out, f"the row itself is not in the report: {out}"


# ------------------------------------------------------------------- refusal, both ways

def test_a_project_expected_to_be_refused_is_green_when_it_is(tmp_path: Path) -> None:
    """dos-real16-alt's case, and why the sweep may not simply go red on a refusal.

    A map with no `Publics by` section is a statement about that project's LINK, is
    already recorded as its own card, and is expected to stay that way until that project
    changes.  A sweep that went red on it every run would be red for ever, and the reason
    decision 30 declares this manual is that a gate nobody can ever get green is one
    people learn to ignore.
    """
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                            "expect": {"refused": "no `Publics by ...` header"}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "refused" in out.lower(), out
    # AND THE FORMAT IS REPORTED ON THE REFUSAL PATH TOO. It is the path where a reader
    # most wants it -- "which reader refused this" is the whole question -- and it is
    # stamped by a DIFFERENT line from the clean path's, so the clean path's case cannot
    # see it go blank. MEASURED: with the refusal's stamp removed, every other case here
    # stayed green.
    assert "borland-tlink" in out, out


def test_a_refusal_whose_reason_changed_is_red(tmp_path: Path) -> None:
    """The expectation is the MESSAGE and not the fact of refusing.

    Every refusal is a refusal, so matching on "it was refused" would accept a file that
    started failing for an entirely different reason -- which is a reader regression
    wearing the costume of the known state.
    """
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                            "expect": {"refused": "some other reason entirely"}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    # THE MESSAGE, because the reason IS the product here: quoting what was expected
    # beside what was got is the whole of this branch, and rc=1 alone would pass over a
    # report reduced to the word "refused".
    assert "some other reason entirely" in out, out
    assert "not for the expected reason" in out, out


def test_a_refusal_where_symbols_were_expected_is_red_and_quotes_the_reason(
        tmp_path: Path) -> None:
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP", "expect": {"symbols": 12}}})
    rc, out = _run(root, mf)
    assert rc == 1, out
    assert "Publics by" in out, out


# --------------------------------------------------------------- INVALID, never green

def test_a_path_that_is_not_there_is_invalid_and_never_green(tmp_path: Path) -> None:
    """3 and not 1, because "the map changed" and "I did not read the map" are different
    facts and only one of them is a finding about the reader."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "GONE": {"path": "proj/NOPE.MAP", "expect": {"symbols": 1}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "NOPE.MAP" in out, out
    # AND THE DIAGNOSIS, not only the verdict. MEASURED: with the `is_file` guard removed
    # the run still exits 3, through the read failing, so a case asserting the code alone
    # is GREEN over a report that has stopped saying which of the two things went wrong.
    # The verdict is the same and the message is the product.
    assert "is not a file" in out, out
    assert "NOT swept" in out, out


def test_a_manifest_with_no_projects_is_invalid(tmp_path: Path) -> None:
    """An instrument that examined nothing reports INVALID, never a clean bill of health.

    THE MESSAGE IS ASSERTED TOO. Every INVALID here exits 3, so the code alone cannot
    tell an empty MANIFEST from an empty SELECTION -- and MEASURED, removing this guard
    lands on the selection's message, which sends the reader to look at a `--project`
    they never typed.
    """
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
    # Every INVALID exits 3, so the code alone cannot tell an unreadable manifest from
    # one that will not parse from a row that expects nothing.
    assert "cannot read the manifest" in out, out


def test_a_project_with_no_expectation_at_all_is_invalid(tmp_path: Path) -> None:
    """A row that asserts nothing is not a lighter row, it is a project silently outside
    the control -- and it prints exactly like one that passed."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "expects nothing" in out, out


def test_a_selection_that_matches_no_project_is_invalid(tmp_path: Path) -> None:
    """`--project TYPO` running zero projects and exiting 0 is the same defect one level
    up: a scope that selected nothing must not read as everything passing."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    rc, out = _run(root, mf, "--project", "TYPO")
    assert rc == 3, out
    # It NAMES the typo and what it could have meant. Falling through to the generic
    # "matched no project" is a true sentence that hides which word was wrong.
    assert "TYPO" in out, out


def test_no_root_at_all_is_invalid_rather_than_reading_relative_to_the_cwd(
        tmp_path: Path) -> None:
    """A relative path resolved against whatever directory the caller happened to be in
    is how a sweep reads somebody else's file and reports about this one."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    lines: list[str] = []
    rc = mapsweep.main(["--manifest", str(mf)], write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 3, out
    # THE WORST DEGRADATION OF THE FOUR, and the reason this guard is not decoration.
    # MEASURED with it removed: the run still exits 3, and reports `p/A.MAP is not
    # there` -- about a file that IS there. It blames the material for a missing
    # argument, which is a diagnosis pointing at the wrong repository.
    assert "no root" in out, out


# --------------------------------------------------------------------- selection, usage

def test_project_selects_one_and_leaves_the_others_unread(tmp_path: Path) -> None:
    root, mf = _tree(tmp_path,
                     {"proj/A.MAP": SMALL_MAP, "proj/B.SYM": NM_TEXT},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.SYM", "expect": {"symbols": 999}}})
    rc, out = _run(root, mf, "--project", "ZULU")
    assert rc == 0, out
    assert "B" not in out.replace("BORLAND", "").replace("borland", ""), out


def test_an_unknown_option_exits_rather_than_being_ignored(tmp_path: Path) -> None:
    """An ignored option leaves the setting at its default, and a run that measured the
    wrong thing is indistinguishable from one that measured the right one."""
    out: list[str] = []
    rc = mapsweep.main(["--nonsense"], write=out.append, env={})
    assert rc == 2, out


# ------------------------------------------------------- notes inside a JSON manifest

def test_a_key_beginning_with_an_underscore_is_a_note_and_not_a_project(
        tmp_path: Path) -> None:
    """JSON HAS NO COMMENTS, and a manifest of expectations that cannot explain itself is
    a list of numbers nobody can check.

    The convention is one character and it is the whole of it: a key beginning `_` is
    prose.  Anything else is a project, so a mistyped project name is still a project
    with no file and still comes back INVALID -- which is the property that stops this
    convention becoming a way to lose a row.
    """
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"_why": ["this row explains the next one"],
                      "ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 0, out
    assert "_why" not in out, out


def test_a_manifest_of_nothing_but_notes_is_invalid(tmp_path: Path) -> None:
    """A file that is all prose examined nothing, and must not print like a clean run."""
    root, mf = _tree(tmp_path, {}, {"_why": ["prose"], "_and": ["more prose"]})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "names no project" in out, out


# --------------------------------------------- the guards that had no case at all

def test_an_unknown_expect_key_is_invalid_and_names_it(tmp_path: Path) -> None:
    """The guard whose own comment is "A key nothing reads asserts nothing while looking
    exactly like an assertion" -- and which nothing exercised.

    Every other case in this file supplies only the four known keys, so deleting the
    guard left the whole suite green while a row spelled `symbolz` swept clean pinning
    nothing. That is the module's central failure, inside the module written against it.
    """
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbolz": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "symbolz" in out and "does not check" in out, out


def test_a_row_with_no_path_is_invalid_and_names_the_project(tmp_path: Path) -> None:
    """`_tree` always writes a path, so this guard had no case either."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "ZULU" in out and "no `path`" in out, out


def test_more_unreadable_rows_than_it_quotes_says_how_many_it_withheld(
        tmp_path: Path) -> None:
    """"SAID, NEVER TRAILED OFF" is the rule and nothing tested it.

    No fixture here produced more than two unreadable rows, so the truncation branch
    never ran: deleting it left a 292-row loss printing three rows and stopping, which
    reads as a complete list of what was lost.
    """
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
    """The one occasion the row IS the whole diagnosis: a file refused for losing more rows
    than it kept is refused by a message that can only describe them, and the sweep holds the
    report that lists them, so it quotes them."""
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
    """A comprehension here lets the FIRST missing file abort the sweep and throw away
    every project already read.

    That matters beyond tidiness: one manifest row points at a BUILD ARTEFACT, so an
    unbuilt tree makes the documented invocation print one line about that project and
    nothing about the ones that were fine. By this module's own
    criterion, a gate that is INVALID whenever an unrelated tree is unbuilt is one people
    learn to ignore.
    """
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "GONE": {"path": "proj/NOPE.MAP", "expect": {"symbols": 1}}})
    rc, out = _run(root, mf)
    # INVALID OUTRANKS everything: one project could not be examined.
    assert rc == 3, out
    # AND WHAT WAS READ IS STILL REPORTED, which is the half that was lost.
    assert "ZULU         borland-tlink  symbols=4" in out, out
    assert "NOPE.MAP" in out and "is not a file" in out, out
    assert "could NOT be examined" in out, out


def test_the_header_says_how_many_rows_the_manifest_held(tmp_path: Path) -> None:
    """Two ways a project leaves in silence: a name beginning `_`, and a DUPLICATE JSON
    key (which `json.loads` resolves to the last occurrence with no warning).

    Neither is visible in a report that prints only what it read -- six projects and
    seven print identically to anyone who does not already know the number. The header
    carries the DENOMINATOR now, and says how many rows were prose.
    """
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
    """`--project X` narrows the scope to one row of many, and the closing line used to
    claim THE MANIFEST was satisfied -- with the header's bare count as the only signal,
    and only for a reader who already knew how many rows there were."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP, "proj/B.MAP": SMALL_MAP},
                     {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": 4}},
                      "YANKEE": {"path": "proj/B.MAP", "expect": {"symbols": 999}}})
    rc, out = _run(root, mf, "--project", "ZULU")
    assert rc == 0, out
    assert "1 of 2 project(s) as the manifest says" in out, out


def test_a_tilde_that_cannot_be_resolved_is_invalid_and_not_a_red(
        tmp_path: Path) -> None:
    """`Path.expanduser()` RAISES on an unknown user, and only `Invalid` was caught -- so
    the process died with a traceback and status ONE, which this module documents as "the
    honest red", while nothing had been examined."""
    lines: list[str] = []
    rc = mapsweep.main(["--manifest", "~nosuchuser4242/m.json", "--root", str(tmp_path)],
                       write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 3, out
    assert "cannot resolve" in out or "cannot read the manifest" in out, out


def test_a_manifest_path_that_escapes_the_root_is_invalid(tmp_path: Path) -> None:
    """`Path("/root") / "/elsewhere"` is `/elsewhere` -- pathlib discards the left side --
    so an absolute path sweeps green on ONE machine while the report names a root it
    never touched. `..` walks out the same way."""
    root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                     {"ZULU": {"path": str(tmp_path / "root" / "proj" / "A.MAP"),
                               "expect": {"symbols": 4}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "not relative to the root" in out, out


def test_an_expectation_that_is_not_a_number_is_invalid(tmp_path: Path) -> None:
    """JSON `true` compares equal to 1 and `false` to 0, so a row could pin a count with
    a token that is not one and read as an assertion."""
    for bad in (True, "4", 4.5, None):
        root, mf = _tree(tmp_path, {"proj/A.MAP": SMALL_MAP},
                         {"ZULU": {"path": "proj/A.MAP", "expect": {"symbols": bad}}})
        rc, out = _run(root, mf)
        assert rc == 3, (bad, out)
        assert "not a whole number" in out, (bad, out)


def test_an_empty_refused_string_is_invalid_because_it_matches_everything(
        tmp_path: Path) -> None:
    """`"" in anything` is True. A placeholder written before the wording is known
    accepted EVERY refusal message there is -- a reader regression wearing the known
    state's costume, which is the one thing the reason-matching exists to prevent."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP", "expect": {"refused": ""}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "NON-EMPTY string" in out, out


def test_expecting_a_refusal_and_a_count_together_is_invalid(tmp_path: Path) -> None:
    """The refusal branch returns before the numeric comparison, so those numbers were
    never compared and nothing said so. A row whose expectations are silently not
    evaluated is worse than one that never had them."""
    root, mf = _tree(tmp_path, {"proj/L.MAP": NO_PUBLICS_MAP},
                     {"LIMA": {"path": "proj/L.MAP",
                               "expect": {"refused": "no `Publics by ...` header",
                                          "symbols": 99999}}})
    rc, out = _run(root, mf)
    assert rc == 3, out
    assert "expects a refusal AND" in out, out


def test_a_usage_error_reaches_the_caller_through_the_write_seam(tmp_path: Path) -> None:
    """argparse writes to stdout/stderr directly, so a usage failure came back as rc 2
    and an EMPTY transcript -- nothing inside the seam could say WHICH argument was
    wrong. The seam exists so the suite can drive this without a shell."""
    lines: list[str] = []
    rc = mapsweep.main(["--nonsense"], write=lines.append, env={})
    out = "\n".join(lines)
    assert rc == 2, out
    assert "nonsense" in out, out
