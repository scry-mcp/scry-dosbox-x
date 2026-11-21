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
from typing import Any

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
        case 0x57:                  /* Get/Set File's Date and Time */
            if (reg_al == 0x00) {
                break;
            } else if (reg_al == 0x01) {
                break;
            } else {
                LOG(LOG_DOSMISC,LOG_ERROR)("unsupported %X",reg_al);
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
IOCTL_CPP = """\
bool DOS_IOCTL(void) {
\tswitch(reg_al) {
\tcase 0x00:\t\t/* Get Device Information */
\t\treturn true;
\tcase 0x0D:\t\t/* Generic block device request */
\tcase 0x11:\t\t/* query generic ioctl capability */
\t\tswitch (reg_cl) {
\t\tcase 0x40:
\t\t\tbreak;
\t\t}
\t\treturn true;
\t}
\treturn false;
}
"""
DICTIONARY: dict[str, Any] = {
    "format": "scry-knowledge/1", "dictionary": "int21", "kind": "call", "scope": "ibm-pc",
    "covers": "fixture", "complete_against": next(iter(tool.LIST_HANDLERS)),
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
    return Fake({"INTERRUP.F": LIST_F.split("\n")}, None,
                {"src/dos/dos.cpp": cpp, "include/dos_inc.h": inc,
                 "src/dos/dos_ioctl.cpp": IOCTL_CPP})


def test_the_list_holds_every_top_level_and_nested_case_of_the_handler() -> None:
    assert tool.list_dos_21(sources()) == (
        "0x21/0x00", "0x21/0x33", "0x21/0x33/0x00", "0x21/0x33/0x05", "0x21/0x33/0x08",
        "0x21/0x4C", "0x21/0x58", "0x21/0x58/0x00", "0x21/0x57", "0x21/0x5E", "0x21/0x5E/0x02",
        "0x21/0x5F", "0x21/0x60", "0x21/0x60/0x01", "0x21/0x73")


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
        (self.repo / "src" / "dos" / "dos_ioctl.cpp").write_text(IOCTL_CPP, encoding="utf-8")
        (self.repo / "include" / "dos_inc.h").write_text(DOS_INC, encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "fixture")
        monkeypatch.setattr(tool, "DOSBOX_X_PIN", _git(self.repo, "rev-parse", "HEAD"))
        digests: dict[str, str] = {}
        for name, members in (("inter61a.zip", {"INTERRUP.F": LIST_F}),
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
    name = next(iter(tool.LIST_HANDLERS))
    assert doc["lists"][name][:2] == ["0x21/0x00", "0x21/0x33"]
    assert doc["rows"]["dosbox-x:src/dos/dos.cpp DOS_21Handler case 0x4c"]["line"] == (
        "        case 0x4c:                  /* EXIT Terminate with return code */")


def test_a_list_line_is_kept_as_its_digest_and_never_as_its_text(world: World) -> None:
    world.run("--write")
    text = world.index.read_text(encoding="utf-8")
    row = json.loads(text)["rows"]["rbil61:INTERRUP.F D-214C"]
    assert row == {"digest": tool.digest('INT 21 - DOS 2+ - "EXIT" - TERMINATE WITH RETURN CODE'),
                   "key": "0x21/0x4C"}
    assert "TERMINATE WITH RETURN CODE" not in text


def test_every_run_prints_how_many_list_lines_the_dictionaries_hold(world: World) -> None:
    rc, out = world.run("--write")
    assert rc == tool.OK and "list lines held: 1" in out[0], out
    rc, out = world.run()
    assert rc == tool.OK and "list lines held: 1" in out[0], out


def test_the_list_lines_held_count_each_cited_place_once() -> None:
    entry = DICTIONARY["entries"][0]
    twice = {"entries": [entry, entry]}
    only_emulator = {"entries": [{"sources": [entry["sources"][1]]}]}
    assert tool.list_lines_held([DICTIONARY]) == 1
    assert tool.list_lines_held([twice, DICTIONARY]) == 1
    assert tool.list_lines_held([only_emulator]) == 0
    assert tool.list_lines_held([]) == 0


def test_a_row_that_changed_in_the_sources_is_red_and_named(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    row = "rbil61:INTERRUP.F D-214C"
    doc["rows"][row]["digest"] = tool.digest("INT 21 - DOS 2+ - EXIT")
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and any(row in ln and "digest" in ln for ln in out)


def test_a_list_that_changed_in_the_sources_is_red(world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    del doc["lists"][next(iter(tool.LIST_HANDLERS))][-1]
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    assert world.run()[0] == tool.RED


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


# Handlers that are not DOS_21Handler: other registers, other layouts of the same C.

BIOS_CPP = """\
static Bitu INT15_Handler(void) {
    if (machine == MCH_AMSTRAD && reg_ah < 0x07) {
        switch(reg_ah) {
            case 0x00:
            case 0x01:
                break;
        }
    }
    switch (reg_ah) {
    case 0x06:                  /* a lone brace: { */
        break;
    case 0x53: // APM
        if (reg_al == 0x01) { reg_ax = '{'; }
        switch(reg_al) {
            case 0x00:
                break;
\t    case 0x07:
                switch(reg_cx) {
                    case 0x1: // standby
                        break;
                }
                break;
        }
        break;
\tcase 0xC2: case 0xC3:
        break;
    }
    return CBRET_NONE;
}
static Bitu INT1A_Handler(void) {
    switch (reg_ah) {
    case 0x7F:
        break;
    }
}
"""
MOUSE_CPP = """\
static Bitu INT33_Handler(void) {
    switch (reg_ax) {
    case 0x0000:    /* Mouse: reset */
        break;
\tcase 0x0003:\t/* position */
        break;
    case 0x53c1:
        break;
    }
}
"""
XMS_CPP = """\
#define\tXMS_GET_VERSION\t\t\t0x00u
#define XMS_QUERY_ANY_FREE_MEMORY\t\t\t0x88u
Bitu XMS_Handler(void) {
\tswitch (reg_ah) {
\tcase XMS_GET_VERSION:\t\t\t/* 00 */
        if (x) {
        }
\t\tbreak;
\tcase XMS_QUERY_ANY_FREE_MEMORY:
\t\tbreak;
\t}
}
"""
BIOS_HANDLERS = (
    tool.Handler("src/ints/bios.cpp", "INT15_Handler", 0x15),
    tool.Handler("src/ints/bios.cpp", "INT1A_Handler", 0x1A),
    tool.Handler("src/ints/mouse.cpp", "INT33_Handler", 0x33, "reg_ax"),
    tool.Handler("src/ints/xms.cpp", "XMS_Handler", 0x43),
)


@pytest.fixture
def others(monkeypatch: pytest.MonkeyPatch) -> Fake:
    monkeypatch.setattr(tool, "HANDLERS", BIOS_HANDLERS)
    return Fake({}, None, {"src/ints/bios.cpp": BIOS_CPP, "src/ints/mouse.cpp": MOUSE_CPP,
                           "src/ints/xms.cpp": XMS_CPP})


def _keys(index: Fake, func: str) -> tuple[str, ...]:
    return tuple(tool.handler_keys(index, tool._handler(func)))


def test_the_outermost_switch_is_the_handlers_not_a_deeper_one_before_it(others: Fake) -> None:
    assert _keys(others, "INT15_Handler") == (
        "0x15/0x06", "0x15/0x53", "0x15/0x53/0x00", "0x15/0x53/0x07", "0x15/0xC2", "0x15/0xC3")


def test_a_switch_inside_a_case_is_not_read_and_a_brace_in_a_comment_or_a_literal_is_not_counted(
        others: Fake) -> None:
    keys = _keys(others, "INT15_Handler")
    assert "0x15/0x53/0x07" in keys and "0x15/0x53/0x01" not in keys
    assert not any(k.endswith("/0x01") for k in keys) and "0x15/0xC3" in keys


def test_two_handlers_of_one_file_do_not_read_each_others_cases(others: Fake) -> None:
    assert _keys(others, "INT1A_Handler") == ("0x1A/0x7F",)


def test_a_switch_on_ax_gives_the_key_of_its_two_bytes(others: Fake) -> None:
    assert _keys(others, "INT33_Handler") == ("0x33/0x00/0x00", "0x33/0x00/0x03", "0x33/0x53/0xC1")
    row = tool.resolve_dosbox_x(others, "src/ints/mouse.cpp INT33_Handler case 0x53c1")
    assert row == Row("    case 0x53c1:", "0x33/0x53/0xC1")


def test_a_case_named_by_a_define_with_a_suffix_is_the_number_it_defines(others: Fake) -> None:
    assert _keys(others, "XMS_Handler") == ("0x43/0x00", "0x43/0x88")
    row = tool.resolve_dosbox_x(others, "src/ints/xms.cpp XMS_Handler case 0x88")
    assert row.line.strip() == "case XMS_QUERY_ANY_FREE_MEMORY:"


def test_a_case_label_that_is_a_name_with_no_define_is_refused(others: Fake) -> None:
    broken = Fake({}, None, {"src/ints/xms.cpp": XMS_CPP.replace("#define\tXMS_GET_VERSION", "//")})
    with pytest.raises(tool.Invalid, match="XMS_GET_VERSION"):
        tool.handler_keys(broken, tool._handler("XMS_Handler"))


@pytest.mark.parametrize(("ident", "qualified", "key"), [
    ("1012", False, "0x10/0x12"), ("104F02", False, "0x10/0x4F/0x02"),
    ("3303", False, "0x33/0x00/0x03"), ("2F1680", False, "0x2F/0x16/0x80"),
    ("1012", True, ""), ("212E", True, "0x21/0x2E"), ("10FF1", False, ""), ("10", False, "")])
def test_a_section_header_gives_the_call_key_its_numbers_spell(
        ident: str, qualified: bool, key: str) -> None:
    assert tool._rbil_key(ident, qualified) == key


def test_the_dpmi_sections_are_the_ones_the_list_titles_so_and_nothing_else() -> None:
    first = ["--------E-310000-----------------", "INT 31 P - DPMI 0.9+ - ALLOCATE LDT DESCRIPTORS",
             "--------E-31EE00------------------", "INT 31 - DOS32 v3.0+ - GET VERSION",
             "--------E-310401-----------------", "INT 31 P - DPMI 1.0+ - GET CAPABILITIES",
             "--------E-310100BX0001-----------", "INT 31 P - DPMI 0.9+ - A QUALIFIED SECTION",
             "--------D-31---------------------", "INT 31 - overwritten by CP/M jump"]
    assert tool.list_dpmi(Fake({"INTERRUP.N": first}, None)) == ("0x31/0x00/0x00", "0x31/0x04/0x01")


@pytest.mark.parametrize("chain", ["""\
#if defined(WIN32)
        if (a) {
#elif defined(MACOSX)
        if (b) {
#else
        if (c) {
#endif
""", """\
#if defined(MACOSX)
        if (b) {
#else
        if (c) {
#endif
"""])
def test_only_one_branch_of_a_preprocessor_chain_counts_its_braces(
        monkeypatch: pytest.MonkeyPatch, chain: str) -> None:
    cpp = f"""\
static Bitu INT2A_Handler(void) {{
    switch (reg_ah) {{
    case 0x01:
{chain}            x();
        }}
        break;
    case 0x02:
        break;
    }}
}}
"""
    monkeypatch.setattr(tool, "HANDLERS", (tool.Handler("src/x.cpp", "INT2A_Handler", 0x2A),))
    fake = Fake({}, None, {"src/x.cpp": cpp})
    assert tuple(tool.handler_keys(fake, tool._handler("INT2A_Handler"))) == (
        "0x2A/0x01", "0x2A/0x02")


def _only(monkeypatch: pytest.MonkeyPatch, func: str, cpp: str, **kw: object) -> Fake:
    monkeypatch.setattr(tool, "HANDLERS", (tool.Handler("src/x.cpp", func, 0x2B, **kw),))  # type: ignore[arg-type]
    return Fake({}, None, {"src/x.cpp": cpp})


def _handler_keys(fake: Fake, func: str) -> tuple[str, ...]:
    return tuple(tool.handler_keys(fake, tool._handler(func)))


def test_code_no_host_runs_or_that_is_commented_out_gives_no_case(
        monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _only(monkeypatch, "INT2B_Handler", """\
static Bitu INT2B_Handler(void) {
    // switch (reg_ah) {
    switch (reg_ah) {
    case 0x01:
#if 0
    case 0x02:
#endif
#ifdef WIN32
    case 0x03:
#else
    case 0x04:
#endif
#if !defined(WIN32)
    case 0x05:
#else
    case 0x06:
#endif
#if defined(MACOSX)
    case 0x07:
#else
    case 0x08:
#endif
    /* a long comment { that goes on
    case 0x09:
    still { in it */
    case 0x0A: s = "}";
        break;
    }
}
""")
    assert _handler_keys(fake, "INT2B_Handler") == (
        "0x2B/0x01", "0x2B/0x04", "0x2B/0x05", "0x2B/0x06", "0x2B/0x07", "0x2B/0x08", "0x2B/0x0A")


def test_a_test_of_not_al_is_the_subfunction_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _only(monkeypatch, "INT2B_Handler", """\
static Bitu INT2B_Handler(void) {
    switch (reg_ah) {
    case 0x5e:
        if (!reg_al && !secure) {
            break;
        }
        break;
    }
}
""", if_cases=frozenset({0x5E}))
    assert _handler_keys(fake, "INT2B_Handler") == ("0x2B/0x5E", "0x2B/0x5E/0x00")


@pytest.mark.parametrize(("cpp", "message"), [
    ("""\
static Bitu INT2B_Handler(void) {
    switch (reg_ah) {
    case 0x01:
        break;
    }
    switch (reg_ah) {
    case 0x02:
        break;
    }
}
""", "same indent"),
    ("""\
static Bitu INT2B_Handler(void) {
    switch (reg_ah) {
    case 0x01u:
        break;
    }
}
""", "cannot read"),
])
def test_a_handler_the_tool_cannot_read_whole_is_refused_not_listed_short(
        monkeypatch: pytest.MonkeyPatch, cpp: str, message: str) -> None:
    fake = _only(monkeypatch, "INT2B_Handler", cpp)
    with pytest.raises(tool.Invalid, match=message):
        tool.handler_keys(fake, tool._handler("INT2B_Handler"))


@pytest.mark.parametrize(("header", "locator", "key"), [
    ("--------X-1AB101-----------", "X-1AB101", "0x1A/0xB1/0x01"),
    ("--------E-67DE00-----------", "E-67DE00", "0x67/0xDE/0x00"),
    ("--------N-2FB800-----------", "N-2FB800", "0x2F/0xB8/0x00"),
    ("--------V-1012--BL10-------", "V-1012--BL10", ""),
    ("--------D-217160CL00-------", "D-217160CL00", "0x21/0x71/0x60"),
])
def test_a_section_header_whose_id_is_all_hex_letters_is_one_id_not_an_id_and_a_qualifier(
        header: str, locator: str, key: str) -> None:
    fake = Fake({"INTERRUP.Z": [header, "INT XX - A TITLE"]}, None)
    assert tool.resolve_rbil(fake, f"INTERRUP.Z {locator}").key == key


def test_a_run_that_finds_the_index_red_still_says_how_many_list_lines_are_held(
        world: World) -> None:
    world.run("--write")
    doc = json.loads(world.index.read_text(encoding="utf-8"))
    doc["rows"]["rbil61:INTERRUP.F D-214C"]["digest"] = "0" * 64
    world.index.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rc, out = world.run()
    assert rc == tool.RED and "list lines held: 1" in out, out
