"""`tools/knowledge_sources.py`: the places it opens in Ralf Brown's list and in DOSBox-X's source,
the lists it captures, and its exit codes, over small sources written for the case."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import knowledge_sources as tool
import pytest
from scry_core.knowledge import Row

DOS_CPP = """\
static Bitu DOS_21Handler(void) {
    switch (reg_ah) {
        case 0x00:      /* Terminate Program */
            break;
        case 0x33:      /* Extended Break Checking */
            switch (reg_al) {
                case 0:reg_dl=1;break;         /* Get the breakcheck flag */
\t\tcase 5:reg_dl=3;break;
                case 08:reg_dl=8;break;
            }
            break;
        case 0x4c:                  /* EXIT Terminate with return code */   \r
            break;
        case 0x58:
            switch (reg_al) {
#if !defined(OSFREE)
                case 0:
                    break;
#endif
                default:
                    break;
            }
            break;
        case 0x5e:
#if defined(WIN32)
            reg_al = 1;
#else
            switch (reg_al) {
                case 0x02:
                    break;
            }
#endif
            break;
        case 0x5f:                  /* Network redirection */
#if defined(WIN32) && !defined(HX_DOS)
            switch(reg_al)
            {
                case    0x34:   //Set pipe state
                    break;
            }
#else
            reg_ax=1;
#endif
            break;
        case 0x60:
#if defined(WIN32)
            reg_ax = 2;
#endif
            switch (reg_al) {
                case 1:
                    break;
            }
            break;
\tcase 0x73:
            break;
    }
}

int other(void) {
    return 1;
}
"""
DOS_INC = """\
#define DOSERR_NONE 0
#define DOSERR_FILE_NOT_FOUND 2
#define DOSERR_RESERVED 14
#define DOSERR_FIXUP_OVERFLOW 14
"""
LIST_F = """\
--------D-212E--DL00-------------------------
INT 21 - DOS 1+ - SET VERIFY FLAG
\tAH = 2Eh
--------D-2158-------------------------------
INT 21 - DOS 2.11+ - GET OR SET MEMORY ALLOCATION STRATEGY
--------D-2158-------------------------------
INT 21 - DOS 5+ - GET OR SET UMB LINK STATE
--------D-217160CL00-------------------------
INT 21 - Windows95 - LONG FILENAME - "TRUENAME" - CANONICALIZE PATH
--------D-214C-------------------------------
INT 21 - DOS 2+ - "EXIT" - TERMINATE WITH RETURN CODE
(Table 01680)
Values for DOS extended error code:
 00h (0)   no error
 0Eh (14)  reserved
 0Eh (14)  (PTS-DOS 6.51+, S/DOS 1.0+) fixup overflow
"""
LIST_FIRST = """\
Interrupt List\t\t\tRelease 61\t\tLast change 16jul00
Copyright (c) 1989-1999,2000 Ralf Brown
--------!---FILELIST-------------------------
INTERRUP.A\tINT 00 through INT 10/BE
--------!---COPYRIGHT------------------------
Permission is granted to use and redistribute the files
--------!---DISCLAIMER-----------------------
no warranty
--------!---AVAILABILITY---------------------
get new releases here
--------!---ABBREVIATIONS--------------------
PC IBM PC
--------!---CREDITS--------------------------
1/85 Janet Jack  (original list)
--------!---CONTACT_INFO---------------------
write to the author
"""
DICTIONARY = {
    "format": "scry-knowledge/1", "dictionary": "int21", "kind": "call", "scope": "ibm-pc",
    "covers": "fixture", "complete_against": "dosbox-x:src/dos/dos.cpp DOS_21Handler",
    "entries": [{"key": "0x21/0x4C", "name": "exit", "description": "Ends the program.",
                 "behaviour": "Ends it.",
                 "sources": [
                     {"role": "documentation", "ref": "rbil61:INTERRUP.F D-214C",
                      "cites": 'INT 21 - DOS 2+ - "EXIT" - TERMINATE WITH RETURN CODE'},
                     {"role": "emulator",
                      "ref": "dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c",
                      "cites": "        case 0x4c:                  /* EXIT Terminate with "
                               "return code */"}]}],
}


@dataclass(frozen=True)
class Fake(tool.Sources):
    """The sources with DOSBox-X's files held in a mapping, and no git."""

    files: Mapping[str, str] = field(default_factory=dict)

    def file(self, path: str) -> list[str]:
        return [ln.rstrip() for ln in self.files[path].split("\n")]


def sources(cpp: str = DOS_CPP, inc: str = DOS_INC) -> Fake:
    return Fake({"INTERRUP.F": LIST_F.split("\n"), "INTERRUP.1ST": LIST_FIRST.split("\n")}, None,
                {"src/dos/dos.cpp": cpp, "include/dos_inc.h": inc})


def test_the_list_holds_every_top_level_and_nested_case_of_the_handler() -> None:
    assert tool.list_dos_21(sources()) == (
        "0x21/0x00", "0x21/0x33", "0x21/0x33/0x00", "0x21/0x33/0x05", "0x21/0x33/0x08",
        "0x21/0x4C", "0x21/0x58", "0x21/0x58/0x00", "0x21/0x5E", "0x21/0x5E/0x02", "0x21/0x5F",
        "0x21/0x60", "0x21/0x60/0x01", "0x21/0x73")


def test_the_list_leaves_out_the_cases_only_the_windows_build_has() -> None:
    assert "0x21/0x5F/0x34" not in tool.list_dos_21(sources())


def test_a_case_in_the_other_branch_of_a_windows_guard_and_after_it_is_kept() -> None:
    keys = tool.list_dos_21(sources())
    assert "0x21/0x5E/0x02" in keys and "0x21/0x60/0x01" in keys
    assert "0x21/0x58/0x00" in keys


def test_a_label_with_a_leading_zero_is_decimal_and_a_label_that_is_no_number_is_refused() -> None:
    row = tool.resolve_dosbox_x(sources(), "src/dos/dos.cpp DOS_21Handler case 0x33 case 08")
    assert row.key == "0x21/0x33/0x08"
    with pytest.raises(tool.Invalid, match="not a case label"):
        tool.resolve_dosbox_x(sources(), "src/dos/dos.cpp DOS_21Handler case 0x33 case zz")


def test_a_place_that_two_lines_name_is_refused_not_chosen() -> None:
    top = DOS_CPP.replace("        case 0x00:", "        case 0x4c:\n        case 0x00:")
    nested = DOS_CPP.replace("                case 0:reg_dl=1;break;",
                             "                case 5:reg_dl=1;break;")
    define = DOS_INC + "#define DOSERR_NONE 0\n"
    with pytest.raises(tool.Invalid, match="2 top-level"):
        tool.resolve_dosbox_x(sources(top), "src/dos/dos.cpp DOS_21Handler case 0x4c")
    with pytest.raises(tool.Invalid, match="2 cases"):
        tool.resolve_dosbox_x(sources(nested), "src/dos/dos.cpp DOS_21Handler case 0x33 case 5")
    with pytest.raises(tool.Invalid, match="2 defines"):
        tool.resolve_dosbox_x(sources(inc=define), "include/dos_inc.h DOSERR_NONE")


def test_a_nested_case_is_resolved_under_its_own_top_level_case() -> None:
    row = tool.resolve_dosbox_x(sources(), "src/dos/dos.cpp DOS_21Handler case 0x33 case 5")
    assert row == Row("\t\tcase 5:reg_dl=3;break;", "0x21/0x33/0x05")


def test_a_case_line_keeps_its_indent_and_loses_the_space_and_the_line_end_after_it() -> None:
    row = tool.resolve_dosbox_x(sources(), "src/dos/dos.cpp DOS_21Handler case 0x4c")
    assert row.line == "        case 0x4c:                  /* EXIT Terminate with return code */"


def test_a_nested_case_indented_by_tabs_stays_nested() -> None:
    assert tool.resolve_dosbox_x(
        sources(), "src/dos/dos.cpp DOS_21Handler case 0x33 case 5").key == "0x21/0x33/0x05"
    assert "0x21/0x05" not in tool.list_dos_21(sources())


def test_a_case_indented_by_a_tab_is_a_top_level_case() -> None:
    assert tool.resolve_dosbox_x(sources(), "src/dos/dos.cpp DOS_21Handler case 0x73").key == (
        "0x21/0x73")


@pytest.mark.parametrize("locator", [
    "src/dos/dos.cpp DOS_21Handler case 0x99",
    "src/dos/dos.cpp DOS_21Handler case 0x33 case 9",
    "src/dos/dos.cpp DOS_21Handler case 0x5f case 0x34",
    "src/dos/dos.cpp other case 0x00",
    "src/dos/dos.cpp DOSERR_NO_SUCH",
])
def test_a_place_that_is_not_there_is_refused(locator: str) -> None:
    with pytest.raises(tool.Invalid):
        tool.resolve_dosbox_x(sources(), locator)


def test_a_define_gives_its_value_as_the_key() -> None:
    row = tool.resolve_dosbox_x(sources(), "include/dos_inc.h DOSERR_FILE_NOT_FOUND")
    assert row == Row("#define DOSERR_FILE_NOT_FOUND 2", "2")


def test_the_codes_the_source_defines_are_listed_once_each() -> None:
    assert tool.list_doserr(sources()) == ("0", "2", "14")


def test_a_section_title_is_the_row_and_the_header_gives_the_key() -> None:
    row = tool.resolve_rbil(sources(), "INTERRUP.F D-214C")
    assert row == Row('INT 21 - DOS 2+ - "EXIT" - TERMINATE WITH RETURN CODE',
                                    "0x21/0x4C")


@pytest.mark.parametrize(("locator", "key"), [("INTERRUP.F D-212E--DL00", "0x21/0x2E"),
                                              ("INTERRUP.F D-217160CL00", "0x21/0x71/0x60")])
def test_a_header_with_a_register_qualifier_is_spelled_as_it_is_and_keys_without_it(
        locator: str, key: str) -> None:
    assert tool.resolve_rbil(sources(), locator).key == key


def test_a_header_two_sections_share_needs_the_one_it_means() -> None:
    with pytest.raises(tool.Invalid, match="2 sections"):
        tool.resolve_rbil(sources(), "INTERRUP.F D-2158")
    assert tool.resolve_rbil(sources(), "INTERRUP.F D-2158@2").line.endswith("UMB LINK STATE")


def test_a_table_row_is_found_by_its_start_and_gives_its_decimal_code() -> None:
    row = tool.resolve_rbil(sources(), "INTERRUP.F #01680 00h (0)")
    assert row == Row(" 00h (0)   no error", "0")


def test_two_table_rows_that_start_alike_are_told_apart_by_more_text() -> None:
    with pytest.raises(tool.Invalid, match="2 rows"):
        tool.resolve_rbil(sources(), "INTERRUP.F #01680 0Eh (14)")
    assert tool.resolve_rbil(sources(), "INTERRUP.F #01680 0Eh (14)  reserved").key == "14"


@pytest.mark.parametrize("locator", ["INTERRUP.Z D-214C", "INTERRUP.F D-2199",
                                     "INTERRUP.F #09999 00h (0)", "INTERRUP.F #01680 77h"])
def test_a_list_place_that_is_not_there_is_refused(locator: str) -> None:
    with pytest.raises(tool.Invalid):
        tool.resolve_rbil(sources(), locator)


def test_the_notice_keeps_the_licence_the_credits_and_the_author_and_nothing_else() -> None:
    text = tool.notice(sources())
    assert text.splitlines()[0].startswith("Interrupt List")
    for kept in ("COPYRIGHT", "DISCLAIMER", "AVAILABILITY", "CREDITS", "CONTACT_INFO"):
        assert f"--------!---{kept}" in text
    assert "ABBREVIATIONS" not in text and "FILELIST" not in text


def test_a_list_without_its_credits_gives_no_notice() -> None:
    first = LIST_FIRST.replace("--------!---CREDITS", "--------!---OTHER")
    with pytest.raises(tool.Invalid, match="does not hold the sections"):
        tool.notice(Fake({"INTERRUP.1ST": first.split("\n")}, None))


# The command, over a real git repository and real archives of the fixture sources.


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t.invalid", *args],
        capture_output=True, text=True, check=True)
    return done.stdout.strip()


class World:
    """A repository holding the fixture source at one commit, the archives of the fixture list,
    and a folder of one dictionary."""

    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo, self.zips, self.dicts = tmp / "repo", tmp / "zips", tmp / "dicts"
        self.index = tmp / "out" / "sources.json"
        for folder in (self.repo / "src" / "dos", self.repo / "include", self.zips, self.dicts):
            folder.mkdir(parents=True)
        (self.repo / "src" / "dos" / "dos.cpp").write_text(DOS_CPP, encoding="utf-8")
        (self.repo / "include" / "dos_inc.h").write_text(DOS_INC, encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "fixture")
        monkeypatch.setattr(tool, "DOSBOX_X_PIN", _git(self.repo, "rev-parse", "HEAD"))
        digests: dict[str, str] = {}
        for name, members in (("inter61a.zip", {"INTERRUP.F": LIST_F,
                                                 "INTERRUP.1ST": LIST_FIRST}),
                              ("inter61b.zip", {}), ("inter61c.zip", {}), ("inter61d.zip", {})):
            with zipfile.ZipFile(self.zips / name, "w") as zf:
                for member, text in members.items():
                    zf.writestr(member, text.replace("\n", "\r\n"))
            digests[name] = hashlib.sha256((self.zips / name).read_bytes()).hexdigest()
        monkeypatch.setattr(tool, "ARCHIVES", digests)
        (self.dicts / "int21.json").write_text(json.dumps(DICTIONARY), encoding="utf-8")

    def run(self, *extra: str) -> tuple[int, list[str]]:
        out: list[str] = []
        rc = tool.main(["--archives", str(self.zips), "--dosbox-x", str(self.repo),
                        "--index", str(self.index), "--dictionaries", str(self.dicts), *extra],
                       write=out.append)
        return rc, out


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


def test_the_index_written_from_the_sources_equals_them(world: World) -> None:
    assert world.run("--write")[0] == tool.OK
    rc, out = world.run()
    assert rc == tool.OK and "the index equals the sources: 2 rows" in out[0], out
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    assert doc["lists"]["dosbox-x:src/dos/dos.cpp DOS_21Handler"][:2] == ["0x21/0x00", "0x21/0x33"]
    assert doc["rows"]["dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c"]["line"] == (
        "        case 0x4c:                  /* EXIT Terminate with return code */")


def test_a_row_that_changed_in_the_sources_is_red_and_named(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    row = "rbil61:INTERRUP.F D-214C"
    doc["rows"][row]["line"] = "INT 21 - DOS 2+ - EXIT"
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and any(row in ln and "TERMINATE WITH RETURN CODE" in ln for ln in out)


def test_a_list_that_changed_in_the_sources_is_red(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    del doc["lists"]["dosbox-x:src/dos/dos.cpp DOS_21Handler"][-1]
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    assert world.run()[0] == tool.RED


def test_a_notice_that_changed_is_red(world: World) -> None:
    world.run("--write")
    notice = world.index.with_name(tool.NOTICE_NAME)
    notice.write_text(notice.read_text(encoding="utf-8") + "extra\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and any(tool.NOTICE_NAME in ln for ln in out)


def test_an_archive_that_is_not_the_pinned_one_is_invalid(world: World) -> None:
    (world.zips / "inter61b.zip").write_bytes(b"not the pinned archive")
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "inter61b.zip is not the archive" in out[0], out


def test_a_missing_archive_is_invalid(world: World) -> None:
    (world.zips / "inter61d.zip").unlink()
    assert world.run("--write")[0] == tool.INVALID


def test_a_pin_the_repository_lacks_is_invalid(
        world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool, "DOSBOX_X_PIN", "0" * 40)
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "could not be read" in out[0], out


def test_a_folder_with_no_dictionary_captures_nothing_and_is_invalid(world: World) -> None:
    (world.dicts / "int21.json").unlink()
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "nothing to capture" in out[0], out


def test_dictionaries_whose_entries_cite_nothing_capture_nothing_and_are_invalid(
        world: World) -> None:
    doc = json.loads((world.dicts / "int21.json").read_text(encoding="utf-8"))
    doc["entries"] = []
    (world.dicts / "int21.json").write_text(json.dumps(doc), encoding="utf-8")
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "nothing was captured" in out[0], out


def test_a_dictionary_citing_a_place_that_is_not_there_is_invalid(world: World) -> None:
    doc = json.loads((world.dicts / "int21.json").read_text(encoding="utf-8"))
    doc["entries"][0]["sources"][1]["ref"] = "dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x99"
    (world.dicts / "int21.json").write_text(json.dumps(doc), encoding="utf-8")
    assert world.run("--write")[0] == tool.INVALID


def test_a_list_the_tool_does_not_know_is_invalid(world: World) -> None:
    doc = json.loads((world.dicts / "int21.json").read_text(encoding="utf-8"))
    doc["complete_against"] = "dosbox-x:src/dos/dos.cpp Something_Else"
    (world.dicts / "int21.json").write_text(json.dumps(doc), encoding="utf-8")
    assert world.run("--write")[0] == tool.INVALID


def test_git_that_cannot_run_is_invalid_not_a_crash(
        world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_git(*_: object, **__: object) -> None:
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(subprocess, "run", no_git)
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "git could not run" in out[0], out


def test_an_index_that_cannot_be_written_is_invalid_not_a_crash(
        world: World, tmp_path: Path) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    world.index = blocker / "sources.json"
    rc, out = world.run("--write")
    assert rc == tool.INVALID and "could not be written" in out[0], out


def test_a_pin_that_moved_is_red_and_said(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    doc["pins"]["dosbox-x"] = "0" * 40
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and any("pin 'dosbox-x'" in ln for ln in out), out


def test_an_index_written_another_way_is_red_and_says_so(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    world.index.write_text(json.dumps(doc, indent=4) + "\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and out and "written another way" in out[-1], out


def test_a_missing_index_is_invalid_not_red(world: World) -> None:
    assert world.run()[0] == tool.INVALID


def test_an_unknown_option_exits_with_the_usage_code() -> None:
    assert tool.main(["--nonsense"], write=lambda _: None) == tool.USAGE
