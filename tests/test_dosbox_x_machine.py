"""`machine_map` and the listing reader under it, against what a real debugger wrote.

The listings and screens are files under `fixtures/machine/`, captured from live sessions (its
PROVENANCE says where each one stopped), so the shapes the parsers accept are the debugger's.
Where a case changes a capture (one line edited, a screen cut at a line), it says so.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_dosbox_x_server import FakeSession, clean_session, install  # noqa: F401

import dosbox_console as dcons
import dosbox_logs as dlogs
import dosbox_machine as machine
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_summaries as one_line
import dosbox_symbols as sym
import dosbox_x_server as server

MACHINE = Path(__file__).parent / "fixtures" / "machine"

#: Every section a map can read, for the cases that judge the whole map.
EVERY = list(machine.SECTION_NAMES)


def cap(name: str) -> str:
    """A captured file as the reader hands it over: one character per byte."""
    return (MACHINE / name).read_bytes().decode("latin-1")


#: Where a bench's `VGA` listings were captured (`fixtures/vga/`): the probe's park is the reset
#: stop and dos-djgpp32's start-up stop is the one its machine listings were taken at; dos-real16's
#: were taken later in its run, the same program in the same mode.
VGA_BENCH = {"probe-reset": "probe-park", "dos-djgpp32": "dos-djgpp32-startup"}


def listing(bench: str, command: str) -> str:
    if command.startswith("VGA "):
        name = f"{VGA_BENCH.get(bench, bench)}-{command.replace(' ', '_')}.log.txt"
        return (MACHINE.parent / "vga" / name).read_bytes().decode("latin-1")
    return cap(f"{bench}-{command.replace(' ', '_')}.log.txt")


# ------------------------------------------------------------------ the parsers


def test_the_mcb_chain_keeps_every_block_with_its_heading_and_drops_the_chain_ends() -> None:
    rows = machine.parse_mcbs(listing("probe-booted", "DOS MCBS"))
    assert [r["filename"] for r in rows] == ["\x02", "COMMAND", "COMMAND", "PROBE", "PROBE",
                                             "SC", ""]
    assert rows[3] == {"memory": "conventional", "mcb_seg": "07C9", "size_bytes": 1168,
                       "psp_seg": "0814", "filename": "PROBE"}
    assert rows[0]["notes"] == "DOS" and rows[5]["memory"] == "upper"
    assert rows[6] == {"memory": "upper", "mcb_seg": "CC00", "size_bytes": 81904,
                       "psp_seg": "0000", "notes": "free", "filename": ""}
    assert all("END" not in r["filename"] for r in rows)


def test_a_free_block_keeps_its_stale_name_and_its_zero_psp_says_it_is_free() -> None:
    rows = machine.parse_mcbs(listing("dos-djgpp32", "DOS MCBS"))
    stale = [r for r in rows if r["mcb_seg"] == "3500"]
    assert stale == [{"memory": "conventional", "mcb_seg": "3500", "size_bytes": 61440,
                      "psp_seg": "0000", "notes": "free", "filename": "DJGPP32"}]
    assert [r["filename"] for r in rows if r["mcb_seg"] == "CC4A"] == ["CWSDPMI"]


def test_the_debuggers_data_address_note_is_not_a_block() -> None:
    """dos-real16's chain carries `(data addr ... past this MCB)` between two blocks: it
    describes the debugger's own data view, and the chain around it is read whole."""
    text = listing("dos-real16", "DOS MCBS")
    assert "(data addr" in text
    rows = machine.parse_mcbs(text)
    assert [r["mcb_seg"] for r in rows] == ["0450", "0700", "079B", "07C9", "0813", "083B",
                                            "0881", "9FFF", "CC00"]
    assert rows[6]["filename"] == "REAL16" and rows[6]["psp_seg"] == "0882"


def test_a_line_no_shape_matches_makes_the_whole_section_unreadable() -> None:
    """A partial chain reads as the whole chain, so one line the parser does not know
    refuses the section rather than being skipped."""
    text = listing("probe-booted", "DOS MCBS").replace("   07C9", "   07C9?", 1)
    with pytest.raises(machine.Unreadable) as got:
        machine.parse_mcbs(text)
    assert "07C9?" in got.value.line


@pytest.mark.parametrize(("old", "new"), [
    ("   07C9          1168     0814          PROBE",
     "   07C9          1168     0814 (env)      PROBE"),
    ("   CC00         81904     0000 (free)   \n", "   CC00         81904     0000 (fr\n"),
    ("   0450         10992     0008 (DOS)    \x02", "   0450         10992     0008 (DOS)   \x02"),
], ids=["a_note_the_debugger_never_printed", "a_note_cut_short", "a_note_padded_short"])
def test_an_mcb_row_whose_notes_column_is_not_a_known_note_is_unreadable(
        old: str, new: str) -> None:
    """Text in the notes column that is not a note the captures print refuses the chain,
    rather than being read as part of the block's name."""
    text = listing("probe-booted", "DOS MCBS")
    assert old in text
    with pytest.raises(machine.Unreadable) as got:
        machine.parse_mcbs(text.replace(old, new, 1))
    assert new.strip() in got.value.line


@pytest.mark.parametrize(("old", "new", "why"), [
    ("   E000  END OF CHAIN\n", "", "ended before its END OF CHAIN line"),
    ("   9FFF  END OF CHAIN\n", "", "printed a heading before the chain above it ended"),
    ("   E000  END OF CHAIN\n", "   E000  END OF CHAIN\n   E000  END OF CHAIN\n",
     "printed a line outside any heading's chain"),
], ids=["the_last_end_missing", "the_first_end_missing", "an_end_outside_a_chain"])
def test_an_mcb_chain_that_does_not_close_where_it_should_is_absent_and_says_why(
        tmp_path: Path, old: str, new: str, why: str) -> None:
    r = mapped_with(Edited("probe-booted", tmp_path / "x.log", "DOS MCBS", old, new))
    assert "mcbs" not in r and f"`DOS MCBS` {why}" in r["coverage_note"], r["coverage_note"]


def test_an_mcb_listing_cut_after_its_first_rows_or_with_no_block_is_not_the_chain() -> None:
    lines = listing("probe-booted", "DOS MCBS").split("\n")
    with pytest.raises(machine.Unreadable) as got:
        machine.parse_mcbs("\n".join(lines[:5]) + "\n")
    assert got.value.why.startswith("ended before") and got.value.line == lines[4]
    for no_block in (lines[0], "\n".join([lines[0], lines[1], "   9FFF  END OF CHAIN"])):
        with pytest.raises(machine.Unreadable) as got:
            machine.parse_mcbs(no_block + "\n")
        assert got.value.why.startswith("listed no block")


@pytest.mark.parametrize(("old", "new", "why", "quoted"), [
    ("   0700          2464     0701          COMMAND\n", "",
     "printed a block that does not start right past the one above it", "   079B"),
    ("   0813        622256     0814          PROBE\n", "",
     "closed a chain anywhere but right past its last block", "   9FFF  END OF CHAIN"),
    ("   07C9          1168     0814", "   07C9          1175     0814",
     "printed a size that is not whole paragraphs", "   07C9"),
], ids=["a_middle_block_missing", "a_last_block_missing", "a_size_not_in_paragraphs"])
def test_an_mcb_chain_that_does_not_walk_is_absent_and_says_where(
        tmp_path: Path, old: str, new: str, why: str, quoted: str) -> None:
    """The debugger walks a chain by the sizes, so each block after the first starts right past
    the one above it and END OF CHAIN right past the last: a block missing between two others
    or at the end, or a size that is not whole paragraphs, would otherwise read as the chain.
    A size off by less than a paragraph still lands its neighbour on the right segment."""
    r = mapped_with(Edited("probe-booted", tmp_path / "x.log", "DOS MCBS", old, new))
    assert "mcbs" not in r, r["mcbs"]
    assert f"`DOS MCBS` {why}: '{quoted}" in r["coverage_note"], r["coverage_note"]


def test_a_chain_with_no_block_is_cut_even_when_the_next_chain_has_blocks(tmp_path: Path) -> None:
    text = listing("probe-booted", "DOS MCBS")
    lines = text.split("\n")
    rows = lines[lines.index("Conventional memory:") + 1:lines.index("   9FFF  END OF CHAIN")]
    assert len(rows) == 5
    r = mapped_with(Edited("probe-booted", tmp_path / "x.log", "DOS MCBS",
                           "\n".join(rows) + "\n", ""))
    assert "mcbs" not in r, r["mcbs"]
    assert ("`DOS MCBS` listed no block in the chain this line closes: '   9FFF  END OF CHAIN'"
            in r["coverage_note"]), r["coverage_note"]


def test_with_the_umbs_linked_each_chain_walks_from_its_own_first_block() -> None:
    """With the UMBs linked, upstream's `LogMCBChain` walks the conventional chain on through
    the upper blocks to their END OF CHAIN, then lists the upper chain again from its own start:
    the probe capture edited to that shape. The upper chain's first block lies behind the END
    OF CHAIN above it, so a walk that kept its position past an END OF CHAIN would refuse it."""
    text = listing("probe-booted", "DOS MCBS")
    upper = text.split("Upper memory:\n", 1)[1]
    assert text.count("   9FFF  END OF CHAIN\n") == 1
    rows = machine.parse_mcbs(text.replace("   9FFF  END OF CHAIN\n", upper, 1))
    assert [(r["memory"], r["mcb_seg"]) for r in rows[-2:]] == [("upper", "9FFF"),
                                                               ("upper", "CC00")]


@pytest.mark.parametrize("bench", ["probe-booted", "dos-real16", "dos-djgpp32"])
def test_every_dos_and_bios_listing_parses_on_every_bench_that_has_it(bench: str) -> None:
    devs = machine.parse_devs(listing(bench, "DOS DEVS"))
    assert devs[0] == {"header": "0071:0048", "attr": "8004", "strat": "0000", "intr": "0000",
                       "name": "NUL"}
    kern = machine.parse_kern(listing(bench, "DOS KERN"))
    assert kern[0] == {"seg": "0070", "size_bytes": 16, "what": "DOS_IHSEG"}
    bios = machine.parse_bios_mem(listing(bench, "BIOS MEM"))
    callback_area = [r for r in bios if r["what"] == "DOSBox callback area"]
    assert callback_area == [{"start": "000fca00", "end": "000fdfff", "status": "ALLOC DYN",
                              "what": "DOSBox callback area"}]
    calls = machine.parse_callbacks(listing(bench, "CALLBACKS"))
    assert [c["desc"] for c in calls if c["desc"].startswith("DOS Int 2")][:2] == \
        ["DOS Int 20", "DOS Int 21"]
    assert calls[0] == {"number": 0, "desc": ""}
    assert machine.parse_emu_machine(listing(bench, "EMU MACHINE")) == "VGA S3 Trio"


def test_xms_handles_and_a_listing_with_a_header_and_no_row() -> None:
    assert machine.parse_xms(listing("dos-djgpp32", "DOS XMS")) == [
        {"handle": 1, "status": "ALLOC", "location": "0x00174000", "size_bytes": 535347200}]
    assert machine.parse_xms(listing("probe-booted", "DOS XMS")) == []


def test_ems_handles_carry_their_hex_size_as_bytes_and_the_pages_their_frame() -> None:
    handles, pages = machine.parse_ems(listing("dos-djgpp32", "DOS EMS"))
    assert handles == [{"handle": 0, "addr": "0x00110000", "size_bytes": 0x60000, "name": ""},
                       {"handle": 1, "addr": "0x00170000", "size_bytes": 0x4000, "name": ""}]
    assert pages[0] == {"handle": "--", "page": "0/", "start": "000e0000", "end": "000e3fff"}
    assert len(pages) == 4


def test_emu_mem_takes_the_debuggers_words_and_keeps_the_unit() -> None:
    assert machine.parse_emu_mem(listing("dos-djgpp32", "EMU MEM")) == {
        "a20_gate": "ON", "cpu_address_bits": 36, "cpu_address_mask": "0xfffffffff",
        "cpu_address_mask_current": "0xfffffffff", "memory_reported_size_bytes": 536870912}


def test_the_cpu_listing_in_protected_mode() -> None:
    cpu = machine.parse_cpu(listing("dos-djgpp32", "CPU"))
    assert cpu == {
        "cr0": "80000011", "cr2": "FFFFFFFF", "cr3": "00034000", "cpl": 3,
        "eflags": "00003206", "vm": 0, "iopl": 3, "nt": 0,
        "gdt": {"base": "000D16FE", "limit": "00000087"},
        "idt": {"base": "000D1B86", "limit": "000007FF"},
        "tr": {"selector": "0060", "base": "000D377A", "limit": "000000F1*1"},
        "ldt": {"selector": "0078", "base": "000D1786", "limit": "000003FF*1"}}
    assert machine.cpu_mode(cpu) == "paged"
    assert machine.cpu_mode(machine.parse_cpu(listing("probe-booted", "CPU"))) == "real"
    protected = dict(cpu, cr0="00000011")
    assert machine.cpu_mode(protected) == "protected"


def test_descriptor_tables_drop_their_empty_slots_and_keep_the_selector_symbols_use() -> None:
    gdt = machine.parse_descriptors(listing("dos-djgpp32", "GDT"), "GDT")
    assert gdt[0] == {"selector": "0008", "base": "000D16FE", "limit": "00000087", "type": "12",
                      "dpl": 0, "p": 1, "a": 0, "r": 0, "b": 0, "g": 0}
    assert all(r["selector"] not in ("0000", "0048", "0050", "0058") for r in gdt)
    ldt = machine.parse_descriptors(listing("dos-djgpp32", "LDT"), "LDT")
    code = [r for r in ldt if r["selector"] == "00A4"]
    assert code == [{"selector": "00A4", "base": "00400000", "limit": "002BFFFF", "type": "1B",
                     "dpl": 3, "p": 1, "a": 0, "r": 0, "b": 1, "g": 1}]
    assert not [r for r in ldt if r["base"] == "00000000" and r["limit"] == "00000000"
                and r["type"] == "00"]


@pytest.mark.parametrize("edit", [False, True], ids=["captured", "one_page_reflagged"])
def test_the_page_runs_expand_back_to_every_page_the_debugger_listed(edit: bool) -> None:
    """Lossless: each run, expanded page by page, gives back the listing's pages in order with
    their flags, `d` and `a`. Every captured page carries the same flags, so one edited copy
    gives a page different flags and nothing else."""
    text = listing("dos-djgpp32", "PAGING")
    if edit:
        lines = text.split("\n")
        lines[100] = lines[100].replace("flags [uw]", "flags [u-]")
        text = "\n".join(lines)
    runs = machine.parse_paging(text)
    pages = []
    for line in text.splitlines():
        m = re.match(r"page ([0-9A-F]+)xxx -> ([0-9A-F]+)xxx  flags (.+) \[d=(\d)\|a=(\d)\]$",
                     line)
        assert m, line
        pages.append((int(m[1], 16), int(m[2], 16), m[3], int(m[4]), int(m[5])))
    expanded = []
    for r in runs:
        first, last, phy = int(r["start"], 16) >> 12, int(r["end"], 16) >> 12, int(r["phy"], 16)
        assert int(r["end"], 16) & 0xFFF == 0xFFF
        for i in range(last - first + 1):
            expanded.append((first + i, (phy >> 12) + i, r["flags"], r["d"], r["a"]))
    assert expanded == pages
    assert len(runs) < len(pages)


def test_the_debuggers_refusal_before_dos_booted_is_a_refusal_not_a_listing() -> None:
    for command in ("DOS MCBS", "DOS DEVS", "DOS KERN", "DOS XMS", "DOS EMS"):
        text = listing("probe-reset", command)
        assert machine.refusal(text) == text.strip()
        assert "DOS kernel is inactive" in text
    assert machine.refusal(listing("dos-real16", "DOS EMS")) == \
        "Cannot enumerate EMS memory while EMS is inactive."
    assert machine.refusal(listing("probe-booted", "DOS MCBS")) is None


# ------------------------------------------------------------------ the reader


class Logfile:
    """The two halves a listing arrives in, as a real session sees them: the screen `command`
    returns (and the repaint a key returns), and the bytes the emulator appends to its logfile
    for that command. `shrink` truncates the file during the command, as a rotated log would."""

    def __init__(self, tmp: Path, screens: list[str], logged: list[bytes], *,
                 logfile: bool = True, shrink: bool = False) -> None:
        self.path = tmp / "session.log"
        self.path.write_bytes(b"what the boot already wrote\n")
        self.launch = SimpleNamespace(logfile=self.path if logfile else None, cwd=tmp)
        self.screens = list(screens)
        self.logged = list(logged)
        self.typed: list[bytes] = []
        self.shrink = shrink

    def _keys(self, data: bytes, settle: float = ds.SETTLE_S,
              timeout: float = ds.REPLY_TIMEOUT_S) -> str:
        self.typed.append(data)
        if self.shrink:
            self.path.write_bytes(b"")
        if self.logged:
            with self.path.open("ab") as f:
                f.write(self.logged.pop(0))
        return self.screens.pop(0)

    def command(self, text: str, settle: float = ds.SETTLE_S,
                timeout: float = ds.REPLY_TIMEOUT_S) -> str:
        return self._keys(text.encode() + b"\r", settle, timeout)

    def listing(self, command: str) -> str:
        return ds.Session.listing(cast(ds.Session, self), command)


def test_a_listing_that_fits_is_read_off_the_logfile_from_where_the_command_began(
        tmp_path: Path) -> None:
    log = (MACHINE / "probe-booted-DOS_MCBS.log.txt").read_bytes()
    ses = Logfile(tmp_path, [cap("probe-booted-DOS_MCBS.screen.txt")], [log])
    assert ses.listing("DOS MCBS") == log.decode("latin-1")
    assert ses.typed == [b"DOS MCBS\r"]


def test_a_paged_listing_is_answered_with_q_alone_and_read_whole(tmp_path: Path) -> None:
    """The first page leaves the command on the input line and the pager's marker under it;
    `Q` with no carriage return prints the rest and empties the line. Nothing else is typed."""
    log = (MACHINE / "probe-booted-DOS_KERN.log.txt").read_bytes()
    first, rest = log[:845], log[845:]
    ses = Logfile(tmp_path, [cap("probe-booted-DOS_KERN.screen.txt"),
                             cap("probe-booted-DOS_KERN.q.txt")], [first, rest])
    assert ses.listing("DOS KERN") == log.decode("latin-1")
    assert ses.typed == [b"DOS KERN\r", b"Q"]


def test_an_input_line_that_still_holds_a_command_is_refused_and_nothing_more_is_typed(
        tmp_path: Path) -> None:
    """A repaint whose input line still holds text means the next command would be appended to
    it rather than run: refused, naming what the line holds."""
    paged = cap("probe-booted-CALLBACKS.screen.txt")
    held = paged[:paged.rindex("^ Paged content")]
    ses = Logfile(tmp_path, [held], [b""])
    with pytest.raises(ds.Invalid) as got:
        ses.listing("CALLBACKS")
    assert got.value.code == "unexpected_answer" and "CALLBACKS" in str(got.value)
    assert ses.typed == [b"CALLBACKS\r"]


def test_a_pager_still_waiting_after_q_is_refused_and_q_is_not_typed_twice(
        tmp_path: Path) -> None:
    paged = cap("probe-booted-DOS_KERN.screen.txt")
    ses = Logfile(tmp_path, [paged, paged], [b"", b""])
    with pytest.raises(ds.Invalid) as got:
        ses.listing("DOS KERN")
    assert got.value.code == "unexpected_answer" and "close" in str(got.value)
    assert ses.typed == [b"DOS KERN\r", b"Q"]


def test_a_session_without_a_logfile_is_refused_before_anything_is_typed(tmp_path: Path) -> None:
    ses = Logfile(tmp_path, [], [], logfile=False)
    with pytest.raises(ds.Invalid) as got:
        ses.listing("DOS MCBS")
    assert got.value.code == "no_channel" and "logfile" in str(got.value)
    assert ses.typed == []


def test_no_prompt_back_is_not_a_listing_and_says_to_close(tmp_path: Path) -> None:
    """The screen's first page, cut before its prompt (an edited capture): what the file holds
    is not known to be whole, and the pager may still be waiting."""
    paged = cap("probe-booted-DOS_KERN.screen.txt")
    ses = Logfile(tmp_path, [paged[:paged.rindex(dcons.PROMPT)]], [b""])
    with pytest.raises(ds.Invalid) as got:
        ses.listing("DOS KERN")
    assert got.value.code == "unexpected_answer" and "close" in str(got.value)
    assert ses.typed == [b"DOS KERN\r"]


def test_a_logfile_that_shrank_under_the_read_is_refused(tmp_path: Path) -> None:
    ses = Logfile(tmp_path, [cap("probe-booted-DOS_MCBS.screen.txt")], [b""], shrink=True)
    with pytest.raises(ds.Invalid) as got:
        ses.listing("DOS MCBS")
    assert got.value.code == "session_broken"


def test_a_name_byte_above_ascii_survives_the_read_and_the_parse(tmp_path: Path) -> None:
    """A block's name is guest bytes: 0x85 (an accented letter in the DOS code page) comes back
    as itself, and is not taken for a line break that would cut the row (an edited capture)."""
    log = (MACHINE / "probe-booted-DOS_MCBS.log.txt").read_bytes().replace(b"PROBE", b"PR\x85BE")
    ses = Logfile(tmp_path, [cap("probe-booted-DOS_MCBS.screen.txt")], [log])
    rows = machine.parse_mcbs(ses.listing("DOS MCBS"))
    assert [r["filename"] for r in rows if r["psp_seg"] == "0814"] == ["PR\x85BE", "PR\x85BE"]


def test_the_pager_and_the_input_line_are_read_at_the_last_prompt() -> None:
    """A marker an earlier listing left in the scrollback above a clean prompt is not this
    reply's pager (the paged capture, then the `Q` repaint after it)."""
    paged, rest = cap("probe-booted-DOS_KERN.screen.txt"), cap("probe-booted-DOS_KERN.q.txt")
    assert dcons.at_pager(paged) and not dcons.at_pager(paged + rest)
    assert dcons.input_line(paged + rest) == "" and dcons.input_line("no prompt") is None
    assert dcons.input_line(paged[:paged.rindex("^ Paged")]) == "DOS KERN"


# ------------------------------------------------------------------ the tool


class Bench(FakeSession):
    """A stopped machine whose debugger answers each listing with what a real one wrote on
    `bench`; a command it was never captured answering is a failure of the case, not an
    empty listing."""

    def __init__(self, bench: str, logfile: Path | None) -> None:
        super().__init__()
        self.bench = bench
        self.launch = SimpleNamespace(cwd=Path("/"), logfile=logfile, watched=False,
                                      input_port=None, captures_dir=None)
        self.asked: list[str] = []

    def _memdump_candidates(self) -> list[Path]:
        return ds.Session._memdump_candidates(cast(ds.Session, self))

    def listing(self, command: str) -> str:
        if self.launch.logfile is None:
            return ds.Session.listing(cast(ds.Session, self), command)
        self.asked.append(command)
        return listing(self.bench, command)


def dos_listings(asked: list[str]) -> list[str]:
    """What a map asked of the DOS machine: the `vga` section's listings come after these and
    are `test_dosbox_x_screen.py`'s to judge."""
    return [c for c in asked if not c.startswith("VGA ")]


def mapped(bench: str, tmp_path: Path) -> dict[str, Any]:
    s = Bench(bench, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    reply = cast(dict[str, Any], server.machine_map(sections=EVERY))
    reply["_asked"] = dos_listings(s.asked)
    return reply


def test_real_mode_reads_the_dos_machine_and_leaves_the_descriptor_tables_absent(
        tmp_path: Path) -> None:
    r = mapped("probe-booted", tmp_path)
    assert r["status"] == "ok" and r["cpu_mode"] == "real"
    assert [b["filename"] for b in r["mcbs"] if b["psp_seg"] == "0814"] == ["PROBE", "PROBE"]
    for absent in ("gdt", "ldt", "paging"):
        assert absent not in r and absent not in r["counts"] and absent not in r["sources"]
    assert "real mode" in r["coverage_note"]
    assert r["_asked"] == ["DOS MCBS", "DOS DEVS", "DOS KERN", "DOS XMS", "DOS EMS", "BIOS MEM",
                           "CALLBACKS", "EMU MEM", "EMU MACHINE", "CPU"]
    assert r["sources"]["mcbs"] == ["DOS MCBS"] and r["sources"]["ems_pages"] == ["DOS EMS"]
    assert r["counts"]["mcbs"] == len(r["mcbs"]) and r["truncated"] is False
    assert r["xms"] == [] and r["counts"]["xms"] == 0
    assert r["session"]["altered"] is False


def test_paged_protected_mode_adds_the_descriptor_tables_and_the_page_runs(
        tmp_path: Path) -> None:
    r = mapped("dos-djgpp32", tmp_path)
    assert r["cpu_mode"] == "paged"
    assert r["_asked"][-3:] == ["GDT", "LDT", "PAGING"]
    assert any(d["selector"] == "00A4" and d["base"] == "00400000" for d in r["ldt"])
    assert r["sources"]["paging"] == ["PAGING"] and r["counts"]["paging"] == len(r["paging"])


def test_before_dos_booted_the_dos_sections_are_absent_quoting_the_debugger(
        tmp_path: Path) -> None:
    r = mapped("probe-reset", tmp_path)
    assert r["status"] == "ok"
    for absent in ("mcbs", "devs", "kern", "xms", "ems", "ems_pages"):
        assert absent not in r and absent not in r["sources"]
    assert ('`mcbs` is absent: `DOS MCBS` answered "Cannot enumerate MCB list while DOS '
            'kernel is inactive."') in r["coverage_note"]
    assert '`ems` and `ems_pages` are absent: `DOS EMS` answered' in r["coverage_note"]
    assert r["cpu"]["cr0"] == "00000010" and r["bios_mem"]


def test_a_listing_cut_at_the_ceiling_says_so_and_counts_the_whole(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 5)
    r = mapped("probe-booted", tmp_path)
    assert r["truncated"] is True
    assert len(r["callbacks"]) == 5 and r["counts"]["callbacks"] > 5


def test_a_list_exactly_at_the_ceiling_is_whole(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    longest = max(len(machine.parse_callbacks(listing("probe-booted", "CALLBACKS"))),
                  len(machine.parse_bios_mem(listing("probe-booted", "BIOS MEM"))))
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", longest)
    r = mapped("probe-booted", tmp_path)
    assert r["truncated"] is False and max(r["counts"].values()) == longest


def test_the_map_one_line_gives_the_mode_and_every_non_empty_count(tmp_path: Path) -> None:
    r = mapped("probe-booted", tmp_path)
    assert r["summary"].startswith("machine_map (real): 7 mcbs, "), r["summary"]
    assert "xms" not in r["summary"], "a section with no row is not on the line"
    assert "cut" not in r["summary"]


def test_the_map_one_line_says_some_sections_were_cut(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 5)
    assert mapped("probe-booted", tmp_path)["summary"].endswith(
        ", some sections cut (see `counts`)")


class Edited(Bench):
    """A bench whose listing of one command is a capture with one edit applied."""

    def __init__(self, bench: str, logfile: Path, command: str, old: str, new: str) -> None:
        super().__init__(bench, logfile)
        self.edit = (command, old, new)

    def listing(self, command: str) -> str:
        text = super().listing(command)
        which, old, new = self.edit
        if command == which:
            assert old in text
            text = text.replace(old, new, 1)
        return text


def mapped_with(s: Bench) -> dict[str, Any]:
    install()
    dstate.STATE.session = cast(ds.Session, s)
    reply = cast(dict[str, Any], server.machine_map(sections=EVERY))
    reply["_asked"] = dos_listings(s.asked)
    return reply


def test_protected_mode_without_paging_reads_the_tables_and_not_the_pages(
        tmp_path: Path) -> None:
    """dos-djgpp32's `CPU` listing with cr0's paging bit cleared (an edited capture)."""
    r = mapped_with(Edited("dos-djgpp32", tmp_path / "x.log", "CPU", "cr0:80000011",
                           "cr0:00000011"))
    assert r["cpu_mode"] == "protected" and "gdt" in r and "ldt" in r and "paging" not in r
    assert r["_asked"][-2:] == ["GDT", "LDT"]
    assert "`paging` is absent: paging is off" in r["coverage_note"]


def test_an_unreadable_cpu_listing_reads_no_table_and_says_the_mode_is_unknown(
        tmp_path: Path) -> None:
    r = mapped_with(Edited("dos-djgpp32", tmp_path / "x.log", "CPU", "cpl=3", "cpl=?"))
    assert r["cpu_mode"]["available"] is False and "cpu" not in r and "gdt" not in r
    assert r["_asked"][-1] == "CPU"
    assert "`cpu` is absent" in r["coverage_note"] and "mode is unknown" in r["coverage_note"]
    assert r["summary"].startswith("machine_map (mode unread): "), r["summary"]


def test_an_unknown_mode_omits_no_table_it_cannot_say_the_machine_has(tmp_path: Path) -> None:
    """An unknown mode has no descriptor table to leave out, as real mode has none."""
    install()
    dstate.STATE.session = cast(ds.Session, CpuUnknown("dos-djgpp32", tmp_path / "x.log",
                                                       tmp_path))
    r = cast(dict[str, Any], server.machine_map(sections=["mcbs"]))
    assert r["status"] == "ok" and not {"gdt", "ldt"} & set(r.get("omitted", [])), r


def test_without_a_logfile_an_unknown_mode_reads_no_table_and_says_so(tmp_path: Path) -> None:
    """A protected pane that painted no PAGE/NOPG mark leaves the mode unknown: the vectors are
    answered with no holder, never a crash on the unknown mode."""
    _, r = _vectors_with_no_logfile(tmp_path, None)
    assert r["status"] == "ok" and r["cpu_mode"]["available"] is False, r
    assert "no vector has a holder:" in r["coverage_note"], r["coverage_note"]


def test_real_mode_says_why_each_table_is_absent(tmp_path: Path) -> None:
    note = mapped("probe-booted", tmp_path)["coverage_note"]
    assert "`gdt` and `ldt` are absent: the cpu is in real mode" in note
    assert "`paging` is absent: paging is off" in note


def test_without_a_logfile_machine_map_is_refused_naming_it(tmp_path: Path) -> None:
    s = Bench("probe-booted", None)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.machine_map())
    assert r["status"] == "INVALID" and r["code"] == "no_channel"
    assert "logfile" in r["message"] and s.asked == []


def test_a_running_guest_is_refused_not_stopped(tmp_path: Path) -> None:
    s = Bench("probe-booted", tmp_path / "x.log")
    s.at_debugger = lambda: False  # type: ignore[method-assign]
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.machine_map())
    assert r["status"] == "INVALID" and r["code"] == "not_stopped" and s.asked == []


def test_perform_runs_machine_map_as_a_step(tmp_path: Path) -> None:
    s = Bench("probe-booted", tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.perform(steps=[{"op": "machine_map"}]))
    assert r["status"] == "ok" and r["steps_completed"] == 1, r


@pytest.mark.parametrize(("parse", "name", "old", "new"), [
    (machine.parse_devs, "probe-booted-DOS_DEVS", "Header    Attr", "Header   Attr"),
    (machine.parse_kern, "probe-booted-DOS_KERN", "0070           16", "0070  sixteen"),
    (machine.parse_xms, "dos-djgpp32-DOS_XMS", "     1 ALLOC  0x", "     1 ALLOC  "),
    (machine.parse_ems, "dos-djgpp32-DOS_EMS", "(type Mixed) handles:", "handles:"),
    (machine.parse_ems, "dos-djgpp32-DOS_EMS", "--        0/", "--        x/"),
    (machine.parse_callbacks, "probe-booted-CALLBACKS", "--------------\n", ""),
    (machine.parse_emu_machine, "probe-booted-EMU_MACHINE", "Machine: ", "Machine "),
    (machine.parse_cpu, "dos-djgpp32-CPU", "*1\n", "*1\nan eighth line\n"),
    (lambda t: machine.parse_descriptors(t, "GDT"), "dos-djgpp32-GDT", "GDT Base:", "GDT base:"),
    (lambda t: machine.parse_descriptors(t, "GDT"), "dos-djgpp32-GDT", "0008: b:", "0008: B:"),
    (lambda t: machine.parse_descriptors(t, "GDT"), "dos-djgpp32-GDT", "dpl : 0  10000",
     "dpl : 0  1000x"),
    (lambda t: machine.parse_descriptors(t, "GDT"), "dos-djgpp32-GDT",
     "\n      l:000011FC dpl : 3  10000\n", "\n"),
    (machine.parse_paging, "dos-djgpp32-PAGING", "page 00000xxx", "page 00000yyy"),
])
def test_every_parser_refuses_a_listing_whose_shape_moved(
        parse: Any, name: str, old: str, new: str) -> None:
    """One edit to a capture, the kind a different debugger build would print: the parser
    names the line it cannot read rather than handing back what it could."""
    text = cap(f"{name}.log.txt")
    assert old in text
    with pytest.raises(machine.Unreadable):
        parse(text.replace(old, new, 1))


class Silent(Bench):
    """A bench whose debugger printed nothing for one command."""

    def __init__(self, bench: str, logfile: Path, command: str) -> None:
        super().__init__(bench, logfile)
        self.silent = command

    def listing(self, command: str) -> str:
        text = super().listing(command)
        return "" if command == self.silent else text


def test_a_listing_that_printed_nothing_is_absent_and_says_so(tmp_path: Path) -> None:
    r = mapped_with(Silent("probe-booted", tmp_path / "x.log", "DOS DEVS"))
    assert "devs" not in r and "`devs` is absent: `DOS DEVS` printed nothing" in r["coverage_note"]


# ------------------------------------------------------------------ the interrupt vectors


def vectors_file(bench: str) -> str:
    return cap(f"{bench}-INTVEC.txt")


@pytest.mark.parametrize("bench", ["probe-reset", "probe-booted", "dos-real16", "dos-djgpp32"])
def test_the_intvec_file_parses_to_every_vector_in_order(bench: str) -> None:
    rows = machine.parse_intvec(vectors_file(bench))
    assert [r["number"] for r in rows] == list(range(256))
    if bench == "probe-reset":
        assert {r["seg_off"] for r in rows} == {"0000:00000000"}
    else:
        assert rows[0x21]["seg_off"] in ("F000:0000D100", "F000:0000D0A0", "002B:00003AA4")


def test_an_intvec_file_that_is_not_the_whole_table_is_not_the_table() -> None:
    lines = vectors_file("probe-booted").split("\n")
    with pytest.raises(machine.Unreadable):
        machine.parse_intvec("\n".join(lines[:200]))
    with pytest.raises(machine.Unreadable):
        machine.parse_intvec("\n".join([lines[1], lines[0], *lines[2:]]))


class IntvecBench(Bench):
    """A bench whose `INTVEC` writes the captured file into its working directory, with the
    captured end of the screen that answered it (`probe-booted-INTVEC.screen.txt`, the same
    line on every bench)."""

    def __init__(self, bench: str, logfile: Path | None, cwd: Path, *,
                 writes: bool = True, says: bool = True) -> None:
        super().__init__(bench, logfile)
        self.launch = SimpleNamespace(cwd=cwd, logfile=logfile, watched=False, input_port=None)
        self.writes = writes
        self.says = says
        self.typed: list[str] = []

    def command(self, text: str, **_: object) -> str:
        self.typed.append(text)
        if text == f"INTVEC {ds.INTVEC_FILE}" and self.writes:
            (self.launch.cwd / ds.INTVEC_FILE).write_bytes(
                (MACHINE / f"{self.bench}-INTVEC.txt").read_bytes())
            return cap("probe-booted-INTVEC.screen.txt") if self.says else "I-> _"
        return "I-> _"

    def intvec(self) -> str:
        return ds.Session.intvec(cast(ds.Session, self))


def vectors_of(s: Bench, **kw: Any) -> dict[str, Any]:
    install()
    dstate.STATE.session = cast(ds.Session, s)
    return cast(dict[str, Any], server.interrupt_vectors(**kw))


def test_real_mode_vectors_land_in_the_bios_block_that_holds_them(tmp_path: Path) -> None:
    r = vectors_of(IntvecBench("probe-booted", tmp_path / "x.log", tmp_path), number=0x21)
    assert r["status"] == "ok" and r["cpu_mode"] == "real"
    [row] = r["vectors"]
    assert row["number"] == 0x21 and row["seg_off"] == "F000:0000D100", row
    assert row["addr"] == "0x000fd100", row
    assert row["bios_mem"]["what"] == "DOSBox callback area" and "mcbs" not in row
    assert r["counts"]["vectors"] == 256 and r["sources"]["vectors"] == ["INTVEC"]
    assert not (tmp_path / ds.INTVEC_FILE).exists(), "the server's own file is removed"


# dos-real16's two handlers as its own Borland map places them (REAL16.MAP publics
# `0366:000CB NEW_IRQ_VIDEO` and `0366:00095 NEW_KEY_PC`, offsets from the image start), at the
# load base matrix section D derives (PSP 0882 + 0x10 paragraphs).
DOS_REAL16_BASE = 0x8920
DOS_REAL16_PUBLICS = (("NEW_KEY_PC", 0x3660 + 0x95), ("NEW_IRQ_VIDEO", 0x3660 + 0xCB))


def test_a_program_hooking_the_timer_and_the_keyboard_holds_them_by_name(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r = vectors_of(IntvecBench("dos-real16", tmp_path / "x.log", tmp_path))
    rows = {v["number"]: v for v in r["vectors"]}
    for n in (0x08, 0x09):
        assert rows[n]["mcbs"]["filename"] == "REAL16" and "symbol" not in rows[n]
    assert rows[0x1C]["mcbs"]["filename"] == "INJECT"
    install_dos_real16_table(monkeypatch)
    r = vectors_of(IntvecBench("dos-real16", tmp_path / "x.log", tmp_path))
    rows = {v["number"]: v for v in r["vectors"]}
    assert (rows[0x08]["symbol"]["name"], rows[0x08]["symbol"]["delta"]) == ("NEW_IRQ_VIDEO", 0)
    assert (rows[0x09]["symbol"]["name"], rows[0x09]["symbol"]["delta"]) == ("NEW_KEY_PC", 0)
    assert "symbol" not in rows[0x21], "below the table's lowest symbol names nothing"


def install_dos_real16_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """dos-real16's two publics as the table `symbols_load` would hold them, flat, at its base;
    `clean_session` forgets them after the case."""
    dstate.STATE.install_table([sym.Symbol(n, off) for n, off in DOS_REAL16_PUBLICS])
    monkeypatch.setitem(dstate.STATE.base, "base", DOS_REAL16_BASE)


def test_protected_mode_vectors_go_through_the_descriptor_and_the_pages(tmp_path: Path) -> None:
    """dos-djgpp32 under CWSDPMI: INT 08's selector names a GDT descriptor whose page maps to
    itself, inside the CWSDPMI block; INT 21's names the privilege-3 descriptor with the same
    base."""
    r = vectors_of(IntvecBench("dos-djgpp32", tmp_path / "x.log", tmp_path))
    assert r["cpu_mode"] == "paged"
    rows = {v["number"]: v for v in r["vectors"]}
    assert rows[0x08]["addr"] == "0x000cfff0" and rows[0x08]["mcbs"]["filename"] == "CWSDPMI"
    assert rows[0x21]["addr"] == "0x000d0054" and rows[0x21]["mcbs"]["filename"] == "CWSDPMI"
    assert set(r["sources"]) >= {"vectors", "gdt", "ldt", "paging", "mcbs"}


def test_before_dos_booted_the_table_is_all_zero_and_nothing_is_placed(tmp_path: Path) -> None:
    r = vectors_of(IntvecBench("probe-reset", tmp_path / "x.log", tmp_path))
    assert r["status"] == "ok" and len(r["vectors"]) == 256
    assert all(set(v) == {"number", "seg_off"} for v in r["vectors"])
    assert "every vector is 0000:0000" in r["coverage_note"]
    assert "Cannot enumerate MCB list while DOS kernel is inactive." in r["coverage_note"]


def test_without_a_logfile_the_table_comes_back_and_no_vector_has_a_holder(
        tmp_path: Path) -> None:
    s = IntvecBench("probe-booted", None, tmp_path)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    dstate.STATE.remember_stop(cast(ds.Session, s), {"cs": "0814", "eip": "00000106",
                                                     "mode": "Real"}, {}, [], {"attributed": False})
    r = cast(dict[str, Any], server.interrupt_vectors(number=0x21))
    assert r["status"] == "ok" and [v["seg_off"] for v in r["vectors"]] == ["F000:0000D100"]
    assert r["cpu_mode"] == "real" and r["vectors"][0]["addr"] == "0x000fd100", r
    assert r["summary"] == "interrupt_vectors INT 21: F000:0000D100, held by no block read"
    assert not any(k in r["vectors"][0] for k in ("mcbs", "kern", "bios_mem"))
    assert "logfile" in r["coverage_note"] and s.asked == []


def test_a_leftover_file_is_refused_and_left_where_it_is(tmp_path: Path) -> None:
    for name in (ds.INTVEC_FILE, ds.INTVEC_FILE.lower()):
        left = tmp_path / name
        left.write_text("somebody's file")
        s = IntvecBench("probe-booted", tmp_path / "x.log", tmp_path)
        r = vectors_of(s)
        # A filesystem that folds case finds either spelling under the other name.
        assert r["status"] == "INVALID" and r["code"] == "bad_argument"
        assert ds.INTVEC_FILE in r["message"].upper()
        assert "already sitting at" in r["message"], "not the one leftover refusal"
        assert left.read_text() == "somebody's file" and s.typed == []
        left.unlink()


def test_a_dangling_link_where_the_table_goes_is_refused_and_nothing_written_through_it(
        tmp_path: Path) -> None:
    """A link pointing nowhere is somebody's too: the debugger would write the table through
    it, onto whatever the link names, and the clean-up would remove only the link."""
    target = tmp_path / "elsewhere" / "theirs.txt"
    target.parent.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    for name in (ds.INTVEC_FILE, ds.INTVEC_FILE.lower()):
        (cwd / name).symlink_to(target)
        s = IntvecBench("probe-booted", tmp_path / "x.log", cwd)
        r = vectors_of(s)
        assert r["status"] == "INVALID" and r["code"] == "bad_argument", r
        assert (cwd / name).is_symlink() and not target.exists() and s.typed == []
        (cwd / name).unlink()


def test_no_file_after_intvec_is_refused(tmp_path: Path) -> None:
    r = vectors_of(IntvecBench("probe-booted", tmp_path / "x.log", tmp_path, writes=False))
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer"


@pytest.mark.parametrize("number", [256, -1])
def test_a_number_outside_the_table_is_refused_before_the_machine(number: int) -> None:
    r = cast(dict[str, Any], server.interrupt_vectors(number=number))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and not r["session"]["alive"]


def test_perform_checks_the_vector_number_before_any_step_runs(tmp_path: Path) -> None:
    s = IntvecBench("probe-booted", tmp_path / "x.log", tmp_path)
    install()
    dstate.STATE.session = cast(ds.Session, s)
    r = cast(dict[str, Any], server.perform(steps=[{"op": "machine_map"},
                                                   {"op": "interrupt_vectors", "number": 300}]))
    assert r["status"] == "INVALID" and s.asked == [] and s.typed == []
    r = cast(dict[str, Any], server.perform(steps=[{"op": "machine_map"},
                                                   {"op": "interrupt_vectors", "number": 8}]))
    assert r["status"] == "ok" and r["steps_completed"] == 2


def test_a_running_guest_is_refused_before_intvec_is_typed(tmp_path: Path) -> None:
    s = IntvecBench("probe-booted", tmp_path / "x.log", tmp_path)
    s.at_debugger = lambda: False  # type: ignore[method-assign]
    r = vectors_of(s)
    assert r["code"] == "not_stopped" and s.typed == []


def test_a_file_written_without_the_debuggers_word_is_refused_and_removed(
        tmp_path: Path) -> None:
    r = vectors_of(IntvecBench("probe-booted", tmp_path / "x.log", tmp_path, says=False))
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer"
    assert not (tmp_path / ds.INTVEC_FILE).exists()


def test_a_linear_address_goes_through_the_page_run_that_maps_it() -> None:
    """dos-djgpp32's program pages are not mapped to themselves: linear 00401000 is the first
    page of a run whose physical start is 00174000."""
    runs = machine.parse_paging(listing("dos-djgpp32", "PAGING"))
    assert machine.physical_address(0x00401234, runs) == 0x00174234
    assert machine.physical_address(0xFFFFF000, runs) is None


def test_a_run_maps_its_own_first_and_last_byte_and_neither_neighbour() -> None:
    runs = machine.parse_paging(listing("dos-djgpp32", "PAGING"))
    assert runs
    for run in runs:
        start, end, phy = int(run["start"], 16), int(run["end"], 16), int(run["phy"], 16)
        assert machine.physical_address(start, [run]) == phy
        assert machine.physical_address(end, [run]) == phy + end - start
        assert machine.physical_address(start - 1, [run]) is None
        assert machine.physical_address(end + 1, [run]) is None


def test_the_holder_is_the_first_section_in_order_that_holds_the_address() -> None:
    """The kernel's `xms_callback` block (c400) lies inside DOS's upper-memory block (9FFF), and
    the chain is asked first."""
    found = {"mcbs": machine.parse_mcbs(listing("probe-booted", "DOS MCBS")),
             "kern": machine.parse_kern(listing("probe-booted", "DOS KERN")),
             "bios_mem": machine.parse_bios_mem(listing("probe-booted", "BIOS MEM"))}
    held = machine.holder(0xC4000, found)
    assert held is not None and held[0] == "mcbs" and held[1]["mcb_seg"] == "9FFF"
    held = machine.holder(0x00700, found)
    assert held is not None and held[0] == "kern" and held[1]["what"] == "DOS_IHSEG"


def test_a_sectioned_table_with_no_symbol_below_a_vector_names_nothing_and_answers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sections of a table and a vector inside the span, below the lowest symbol of the
    section it falls in: that row has no `symbol`, and the table still comes back."""
    dstate.STATE.install_table([sym.Symbol("low", 0x100, section=1),
                                sym.Symbol("high", 0x900, section=2)])
    monkeypatch.setitem(dstate.STATE.section_bases, 1, 0x0000)
    monkeypatch.setitem(dstate.STATE.section_bases, 2, 0xC000)
    r = vectors_of(IntvecBench("dos-real16", tmp_path / "x.log", tmp_path))
    assert r["status"] == "ok", r
    rows = {v["number"]: v for v in r["vectors"]}
    assert "symbol" not in rows[0x08] and rows[0x08]["addr"] == "0x0000c04b"


class PagesUnread(IntvecBench):
    """dos-djgpp32 with one line of its `PAGING` listing edited, so the section is absent."""

    def listing(self, command: str) -> str:
        text = super().listing(command)
        return text.replace("page 00000xxx", "page 00000yyy", 1) if command == "PAGING" else text


def test_paged_with_the_page_listing_absent_says_so_instead_of_blaming_the_pages(
        tmp_path: Path) -> None:
    r = vectors_of(PagesUnread("dos-djgpp32", tmp_path / "x.log", tmp_path))
    assert r["status"] == "ok" and r["counts"]["held"] == 0
    note = r["coverage_note"]
    assert "`paging` is absent" in note and "no page run maps" not in note


def test_the_one_line_says_a_free_block_is_free_and_a_table_with_no_chain_read_says_so() -> None:
    free = {"memory": "conventional", "mcb_seg": "3500", "size_bytes": 61440, "psp_seg": "0000",
            "notes": "free", "filename": "DJGPP32"}
    line = one_line.interrupt_vectors({"number": 8}, {"vectors": [
        {"number": 8, "seg_off": "3600:00000000", "mcbs": free}]})
    assert line == "interrupt_vectors INT 08: 3600:00000000, mcbs 3500 DJGPP32 (free)"
    region = {"start": "000f0000", "end": "000f8daf", "status": "FREE", "what": ""}
    region_line = one_line.interrupt_vectors({"number": 1}, {"vectors": [
        {"number": 1, "seg_off": "F000:00000100", "bios_mem": region}]})
    assert region_line.endswith("bios_mem 000f0000 FREE")
    unplaced = one_line.interrupt_vectors({"number": None}, {
        "vectors": [{"number": n, "seg_off": "F000:00000000"} for n in range(256)],
        "sources": {"vectors": ["INTVEC"]}})
    assert unplaced == ("interrupt_vectors: 256 vectors, no MCB chain read to count program "
                        "blocks in")


class Breaks(IntvecBench):
    """`INTVEC` writes the file and then the console call fails."""

    def command(self, text: str, **_: object) -> str:
        super().command(text)
        raise ds.Invalid("session_broken", "the emulator went away after writing")


class Unmapped(IntvecBench):
    """dos-djgpp32's table with INT 60 pointed through the program's LDT code selector at the
    page just below the program's first mapped one."""

    def command(self, text: str, **_: object) -> str:
        out = super().command(text)
        written = self.launch.cwd / ds.INTVEC_FILE
        if written.exists():
            table = written.read_text(encoding="latin-1")
            assert table.count("INT 60:  002B:3BA0") == 1
            written.write_text(table.replace("INT 60:  002B:3BA0", "INT 60:  00A7:0000"),
                               encoding="latin-1")
        return out


def test_a_handler_on_a_page_no_run_maps_has_no_holder_and_the_note_says_why(
        tmp_path: Path) -> None:
    r = vectors_of(Unmapped("dos-djgpp32", tmp_path / "x.log", tmp_path))
    rows = {v["number"]: v for v in r["vectors"]}
    assert rows[0x60]["addr"] == "0x00400000"
    assert not {"mcbs", "kern", "bios_mem"} & set(rows[0x60]), rows[0x60]
    assert rows[0x08]["mcbs"]["filename"] == "CWSDPMI"
    assert "no holder for 1 vector: no page run maps their linear address" in r["coverage_note"]
    # Placed, on no present page, so in no block: the count stands without it.
    assert r["summary"] == "interrupt_vectors: 256 vectors, 255 in program blocks (CWSDPMI 255)"


class Rewritten(IntvecBench):
    """A bench whose `INTVEC` file is the captured one with one edit applied."""

    def __init__(self, bench: str, logfile: Path | None, cwd: Path, old: str, new: str) -> None:
        super().__init__(bench, logfile, cwd)
        self.edit = (old, new)

    def command(self, text: str, **_: object) -> str:
        out = super().command(text)
        written = self.launch.cwd / ds.INTVEC_FILE
        if written.exists():
            table = written.read_text(encoding="latin-1")
            assert table.count(self.edit[0]) == 1
            written.write_text(table.replace(*self.edit), encoding="latin-1")
        return out


def test_a_selector_naming_no_descriptor_leaves_that_vector_unplaced_and_says_why(
        tmp_path: Path) -> None:
    r = vectors_of(Rewritten("dos-djgpp32", tmp_path / "x.log", tmp_path,
                             "INT 60:  002B:3BA0", "INT 60:  0100:3BA0"))
    rows = {v["number"]: v for v in r["vectors"]}
    assert set(rows[0x60]) == {"number", "seg_off"} and "addr" in rows[0x61]
    assert ("no `addr` for 1 vector: their selector names no descriptor in `gdt`"
            in r["coverage_note"]), r["coverage_note"]


def test_a_file_that_is_not_the_whole_table_is_refused_and_removed(tmp_path: Path) -> None:
    r = vectors_of(Rewritten("probe-booted", tmp_path / "x.log", tmp_path,
                             "INT FF:  ", "INT FE:  "))
    assert r["status"] == "INVALID" and r["code"] == "unexpected_answer", r
    assert "not the vector table" in r["message"]
    assert not (tmp_path / ds.INTVEC_FILE).exists()


def test_the_servers_own_file_is_removed_when_the_command_fails_after_writing_it(
        tmp_path: Path) -> None:
    r = vectors_of(Breaks("probe-booted", tmp_path / "x.log", tmp_path))
    assert r["code"] == "session_broken" and not (tmp_path / ds.INTVEC_FILE).exists()
    again = vectors_of(IntvecBench("probe-booted", tmp_path / "x.log", tmp_path))
    assert again["status"] == "ok", "the next call is not refused over this call's file"


def test_a_selector_is_looked_up_in_its_own_table_or_named_as_missing() -> None:
    found = {"gdt": machine.parse_descriptors(listing("dos-djgpp32", "GDT"), "GDT"),
             "ldt": machine.parse_descriptors(listing("dos-djgpp32", "LDT"), "LDT")}
    assert machine.vector_linear("00A7:1234", "paged", found) == (0x00401234, "")
    assert machine.vector_linear("002B:3AA4", "paged", found) == (0x000CC5B0 + 0x3AA4, "")
    lin, why = machine.vector_linear("0100:0000", "paged", found)
    assert lin is None and "names no descriptor in `gdt`" in why
    assert machine.vector_linear("0018:0000", None, found)[0] is None
    assert machine.vector_linear("0018:0000", "paged", {})[1] == "`gdt` is absent"


@pytest.mark.parametrize(("address", "section", "key", "value"), [
    (0x04500, "mcbs", "mcb_seg", "0450"),        # the block's own header paragraph
    (0x06FFF, "mcbs", "mcb_seg", "0450"),        # its last byte
    (0x07000, "mcbs", "mcb_seg", "0700"),        # the next block's header
    (0xFFF53, "bios_mem", "what", "BIOS default handler location"),   # a one-byte region
    (0xFFF54, "bios_mem", "what", "BIOS default INT5 location"),
    (0x0070F, "kern", "what", "DOS_IHSEG"),      # a kernel block's last byte
    (0x00710, "kern", "what", "DOS_INFOBLOCK_SEG"),
])
def test_a_holder_covers_its_own_bytes_and_not_one_more(
        address: int, section: str, key: str, value: str) -> None:
    found = {"mcbs": machine.parse_mcbs(listing("probe-booted", "DOS MCBS")),
             "kern": machine.parse_kern(listing("probe-booted", "DOS KERN")),
             "bios_mem": machine.parse_bios_mem(listing("probe-booted", "BIOS MEM"))}
    held = machine.holder(address, found)
    assert held is not None and held[0] == section and held[1][key] == value


def test_the_counts_say_how_many_vectors_are_held_and_named(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_dos_real16_table(monkeypatch)
    r = vectors_of(IntvecBench("dos-real16", tmp_path / "x.log", tmp_path))
    held = sum(1 for v in r["vectors"] if {"mcbs", "kern", "bios_mem"} & set(v))
    named = sum(1 for v in r["vectors"] if "symbol" in v)
    assert r["counts"] == {"vectors": 256, "held": held, "named": named} and named == 2


def test_a_table_whose_mcb_chain_was_not_read_counts_no_program_block(tmp_path: Path) -> None:
    """At the reset park `DOS MCBS` is refused while `BIOS MEM` is read: the one-line cannot
    say how many vectors lie in program blocks, because only the chain has program blocks."""
    r = vectors_of(IntvecBench("probe-reset", tmp_path / "x.log", tmp_path))
    assert "bios_mem" in r["sources"] and "mcbs" not in r["sources"]
    assert r["summary"] == "interrupt_vectors: 256 vectors, no MCB chain read to count program " \
                           "blocks in"


def test_the_table_one_line_counts_program_blocks_and_not_free_ones() -> None:
    program = {"mcb_seg": "0813", "psp_seg": "0814", "filename": "PROBE"}
    free = {"mcb_seg": "3500", "psp_seg": "0000", "notes": "free", "filename": "DJGPP32"}
    line = one_line.interrupt_vectors({}, {
        "vectors": [{"number": 8, "addr": "0x00008200", "mcbs": program},
                    {"number": 9, "addr": "0x00035100", "mcbs": free},
                    {"number": 10, "seg_off": "F000:00000000", "addr": "0x000f0000"}],
        "sources": {"vectors": ["INTVEC"], "mcbs": ["DOS MCBS"]}})
    assert line == "interrupt_vectors: 3 vectors, 1 in program blocks (PROBE 1)"


class ProtectedNoPaging(IntvecBench):
    """dos-djgpp32 with its `CPU` listing's paging bit cleared (an edited capture)."""

    def listing(self, command: str) -> str:
        text = super().listing(command)
        if command != "CPU":
            return text
        assert "cr0:80000011" in text
        return text.replace("cr0:80000011", "cr0:00000011", 1)


def test_protected_mode_without_paging_places_a_handler_at_its_linear_address(
        tmp_path: Path) -> None:
    """INT 08's descriptor puts its handler at linear 000CFFF0, inside the CWSDPMI block; with
    paging off the linear address is the physical one."""
    r = vectors_of(ProtectedNoPaging("dos-djgpp32", tmp_path / "x.log", tmp_path))
    assert r["cpu_mode"] == "protected" and "paging" not in r["sources"]
    rows = {v["number"]: v for v in r["vectors"]}
    assert rows[0x08]["addr"] == "0x000cfff0" and rows[0x08]["mcbs"]["filename"] == "CWSDPMI"


def _vectors_with_no_logfile(tmp_path: Path, paging: bool | None) -> tuple[Any, dict[str, Any]]:
    """`interrupt_vectors(0x08)` at a Pr32 stop of a session started with no logfile, its pane's
    PAGE/NOPG mark `paging` (None: the pane painted none)."""
    s = IntvecBench("dos-djgpp32", None, tmp_path)
    s.paging = paging  # type: ignore[attr-defined]
    install()
    dstate.STATE.session = cast(ds.Session, s)
    dstate.STATE.remember_stop(cast(ds.Session, s), {"cs": "00A7", "eip": "00001234",
                                                     "mode": "Pr32"}, {}, [], {"attributed": False})
    return s, cast(dict[str, Any], server.interrupt_vectors(number=0x08))


@pytest.mark.parametrize("paging", [False, True], ids=["protected", "paged"])
def test_without_a_logfile_in_protected_mode_the_note_says_no_linear_and_why(
        tmp_path: Path, paging: bool) -> None:
    s, r = _vectors_with_no_logfile(tmp_path, paging)
    assert r["status"] == "ok" and r["cpu_mode"] == ("paged" if paging else "protected"), r
    assert set(r["vectors"][0]) == {"number", "seg_off"}
    note = r["coverage_note"]
    assert "no vector has a holder, an `addr` or a `symbol`" in note, note
    assert "descriptor tables" in note and "is absent" not in note, note
    assert r["summary"] == ("interrupt_vectors INT 08: 0018:00003A40, not placed "
                            "(see `coverage_note`)")
    assert s.asked == []


class CpuUnknown(IntvecBench):
    """dos-djgpp32 with its `CPU` listing's cr0 edited to no known shape, so the mode is unknown."""

    def listing(self, command: str) -> str:
        text = super().listing(command)
        if command != "CPU":
            return text
        assert "cr0:80000011" in text
        return text.replace("cr0:80000011", "cr0:8000001?", 1)


@pytest.mark.parametrize(("make", "number", "unplaced"), [
    (lambda p: PagesUnread("dos-djgpp32", p / "x.log", p), 0x08, 256),
    (lambda p: CpuUnknown("dos-djgpp32", p / "x.log", p), 0x08, 256),
    (lambda p: Rewritten("dos-djgpp32", p / "x.log", p, "INT 60:  002B:3BA0", "INT 60:  0100:3BA0"),
     0x60, 1),
], ids=["paged_with_no_page_runs", "mode_unknown", "a_selector_with_no_descriptor"])
def test_with_the_chain_read_a_vector_not_placed_gives_no_program_block_count(
        tmp_path: Path, make: Any, number: int, unplaced: int) -> None:
    """The MCB chain was read, yet some vector was never matched against it: counting the
    program blocks then would count that vector as in none, which is not known."""
    r = vectors_of(make(tmp_path))
    assert "mcbs" in r["sources"], r["sources"]
    assert r["summary"] == (f"interrupt_vectors: 256 vectors, {unplaced} not placed, so no "
                            f"program block is counted"), r["summary"]
    one = vectors_of(make(tmp_path), number=number)
    [row] = one["vectors"]
    assert one["summary"] == (f"interrupt_vectors INT {number:02X}: {row['seg_off']}, not placed "
                              f"(see `coverage_note`)"), one["summary"]
    whole = vectors_of(IntvecBench("dos-djgpp32", tmp_path / "x.log", tmp_path))
    assert whole["summary"] == ("interrupt_vectors: 256 vectors, 256 in program blocks "
                                "(CWSDPMI 256)"), "the same bench with every listing read counts"




# ------------------------------------------------------------------ narrowing the map


def asked_for(bench: str, tmp_path: Path, **kw: Any) -> dict[str, Any]:
    s = Bench(bench, tmp_path / "x.log")
    install()
    dstate.STATE.session = cast(ds.Session, s)
    reply = cast(dict[str, Any], server.machine_map(**kw))
    reply["_asked"] = s.asked
    return reply


def test_the_default_map_reads_the_dos_sections_and_names_the_rest_it_left_out(
        tmp_path: Path) -> None:
    r = asked_for("probe-booted", tmp_path)
    assert r["status"] == "ok" and r["cpu_mode"] == "real"
    assert r["_asked"] == ["DOS MCBS", "DOS DEVS", "DOS KERN", "DOS XMS", "DOS EMS", "EMU MEM",
                           "EMU MACHINE", "CPU"]
    for left in ("bios_mem", "callbacks", "vga"):
        assert left not in r and left not in r["counts"] and left not in r["sources"]
    # Real mode has no paging and no descriptor tables, so none is offered as left out.
    assert r["omitted"] == ["bios_mem", "callbacks", "vga"]
    assert "sections=" in r["how"] and "dest=" in r["how"]


def test_a_paged_default_also_names_the_page_runs_it_left_out(tmp_path: Path) -> None:
    r = asked_for("dos-djgpp32", tmp_path)
    assert r["cpu_mode"] == "paged" and "gdt" in r and "ldt" in r and "paging" not in r
    assert r["omitted"] == ["bios_mem", "callbacks", "paging", "vga"]
    assert "PAGING" not in r["_asked"]


def test_sections_reads_only_the_ones_named_and_the_cpu_for_the_mode(tmp_path: Path) -> None:
    r = asked_for("dos-djgpp32", tmp_path, sections=["paging", "ems_pages"])
    assert r["_asked"] == ["DOS EMS", "CPU", "PAGING"]
    assert "paging" in r and "ems_pages" in r
    assert "ems" not in r and "cpu" not in r and "mcbs" not in r
    assert set(r["sources"]) == {"paging", "ems_pages"} and set(r["counts"]) == set(r["sources"])
    assert "devs" in r["omitted"] and "paging" not in r["omitted"]


def test_every_section_named_leaves_nothing_out(tmp_path: Path) -> None:
    r = asked_for("probe-booted", tmp_path, sections=list(machine.SECTION_NAMES))
    assert "omitted" not in r and "how" not in r
    assert r["bios_mem"] and r["callbacks"] and r["vga"]


@pytest.mark.parametrize("sections, said", [([], "a list naming at least one section"),
                                            (["mcbs", "nope"], "'nope', none of them a section")])
def test_a_bad_section_list_is_refused_before_any_listing(
        tmp_path: Path, sections: list[str], said: str) -> None:
    r = asked_for("probe-booted", tmp_path, sections=sections)
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and said in r["message"]
    assert r["_asked"] == []


def test_dest_writes_every_section_asked_whole_where_the_reply_is_cut(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 5)
    dest = tmp_path / "map.json"
    r = asked_for("dos-djgpp32", tmp_path, sections=["paging"], dest=str(dest))
    assert r["status"] == "ok" and r["path"] == str(dest) and r["truncated"] is True
    assert len(r["paging"]) == 5
    whole = json.loads(dest.read_text())
    assert len(whole["paging"]) == r["counts"]["paging"] > 5
    assert whole["cpu_mode"] == "paged" and whole["sources"] == r["sources"]


def test_a_cut_reply_without_dest_says_how_to_have_it_whole(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dlogs, "LOG_LIMIT_MAX", 5)
    r = asked_for("dos-djgpp32", tmp_path, sections=["paging"])
    # Sections were left out too, so `how` names both ways, `dest` among them.
    assert r["truncated"] is True and "path" not in r and r["how"] == machine.MAP_HOW
    whole = asked_for("dos-djgpp32", tmp_path, sections=EVERY)
    assert "omitted" not in whole and whole["how"] == machine.MAP_CUT_HOW


def test_the_one_line_says_how_many_sections_a_default_map_left_out(tmp_path: Path) -> None:
    assert asked_for("probe-booted", tmp_path)["summary"].endswith(
        ", left out: bios_mem, callbacks, vga (see `omitted`)")
    assert "left out" not in asked_for("probe-booted", tmp_path, sections=EVERY)["summary"]


def test_a_dest_the_host_cannot_write_is_host_failed_and_leaves_no_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "map.json"
    real = Path.open

    def refusing(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        if self == dest and "x" in mode:
            fh = real(self, mode, *a, **k)

            class Full:
                def __enter__(self) -> Full:
                    return self

                def __exit__(self, *_: object) -> None:
                    fh.close()

                def write(self, _text: str) -> int:
                    raise OSError(28, "No space left on device")
            return Full()
        return real(self, mode, *a, **k)
    monkeypatch.setattr(Path, "open", refusing)
    r = asked_for("probe-booted", tmp_path, dest=str(dest))
    assert r["status"] == "INVALID" and r["code"] == "host_failed", r
    assert not dest.exists()


def test_a_dest_already_there_is_refused_before_any_listing(tmp_path: Path) -> None:
    taken = tmp_path / "map.json"
    taken.write_text("{}")
    r = asked_for("probe-booted", tmp_path, dest=str(taken))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and r["_asked"] == []
    assert taken.read_text() == "{}"
