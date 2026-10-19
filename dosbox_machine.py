"""WHAT THE DOS MACHINE IS RIGHT NOW, read from the debugger's own listings: who is resident in
the MCB chain and where, the devices, the kernel's blocks, the XMS and EMS handles, the BIOS's
and the emulator's own blocks, the cpu's control registers and, in protected mode, the
descriptor tables and the page mapping.

EVERY SECTION IS ONE DEBUGGER COMMAND, read whole off the session's logfile
(`Session.listing`), and each parser accepts only the row shapes those listings were captured
printing (`tests/fixtures/machine/`). A line no shape matches makes its WHOLE section absent,
quoted in `coverage_note`, because a chain with one block skipped reads as the whole chain.

THE NAMES ARE THE DEBUGGER'S: a section is its command's word, a field its column's heading,
lower-cased with spaces as `_` and a unit kept as a suffix. Hex is kept as the text the debugger
printed; a size or a count is an integer.

THE INTERRUPT VECTORS come from a FILE, not a listing: `INTVEC` writes the table
(`Session.intvec`), and each handler is placed in the row of these listings that holds it,
through the descriptor tables and the page runs in protected mode, and named through the
loaded symbol table (`dosbox_placement`).
"""
from __future__ import annotations

import dataclasses
import functools
import re
from collections.abc import Callable
from typing import Any, NamedTuple

from scry_core import reply_contract as contract

import dosbox_logs as dlogs
import dosbox_placement as placement
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as st


class Unreadable(Exception):
    """A listing that is not one of the captured shapes: `line` is the line the note quotes and
    `why` the clause before it, a line no shape matches unless the parser says otherwise."""

    def __init__(self, line: str, why: str = "printed a line no known shape matches") -> None:
        super().__init__(line)
        self.line = line
        self.why = why

    def sentence(self, command: str) -> str:
        """What `command` printed that makes its section absent, for `coverage_note`."""
        return f"`{command}` {self.why}: {self.line!r}"


# The sentence the debugger answers a DOS listing with when there is nothing to enumerate:
# every one before DOS booted names the kernel, and `DOS EMS` on a machine without EMS names EMS.
REFUSAL = re.compile(r"^Cannot enumerate [^\n]+ while [^\n]+ is inactive\.$")


def refusal(text: str) -> str | None:
    """The debugger's refusal sentence when that is the whole listing, else None."""
    lines = listing_lines(text)
    return lines[0] if len(lines) == 1 and REFUSAL.match(lines[0]) else None


def listing_lines(text: str) -> list[str]:
    """The listing's lines, its trailing blank ones dropped. Split at the newline the emulator
    writes and nowhere else: a name DOS keeps can hold a byte (0x85, an accented letter in the
    DOS code page) that `splitlines` would take for a line break."""
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _after(text: str, *heading: str) -> list[str]:
    """The listing's lines after its fixed heading lines, which have to be there verbatim."""
    lines = listing_lines(text)
    for i, want in enumerate(heading):
        got = lines[i] if i < len(lines) else ""
        if got.rstrip() != want:
            raise Unreadable(got)
    return lines[len(heading):]


def _each(lines: list[str], row: re.Pattern[str]) -> list[re.Match[str]]:
    out = []
    for line in lines:
        m = row.match(line)
        if m is None:
            raise Unreadable(line)
        out.append(m)
    return out


# ------------------------------------------------------------------ DOS


MCB_HEADING = "MCB Seg  Size (bytes)  PSP Seg (notes)  Filename"
MCB_MEMORY = re.compile(r"^(Conventional|Upper) memory:$")
# The notes column is a fixed width, `(DOS)`, `(free)` or blank, and the filename starts after
# it: any other text there is a row this was not written against, not part of a name.
MCB_NOTES = {"(DOS)    ": "DOS", "(free)   ": "free"}
MCB_ROW = re.compile(
    r"^   ([0-9A-F]{4}) +(\d+)     ([0-9A-F]{4}) "
    rf"({'|'.join(map(re.escape, MCB_NOTES))}| {{9}})(.*?) *$")
MCB_END = re.compile(r"^   ([0-9A-F]{4})  END OF CHAIN$")
#: Bytes in a paragraph, the unit of a segment and of an MCB's header and size.
PARAGRAPH_BYTES = 16
# Printed where the debugger's DATA VIEW points into a block: a fact about the debugger's view,
# which `read_memory` moves, and not about the chain, so it is known and dropped.
MCB_DATA_NOTE = re.compile(
    r"^   \(data addr [0-9A-F]{4}:[0-9A-F]{4} is \d+ bytes past this MCB\)$")


def next_mcb(mcb_seg: int, size_bytes: int) -> int:
    """The segment right past a block, where the next block's header sits: the block's own
    header paragraph, then its size."""
    return mcb_seg + 1 + size_bytes // PARAGRAPH_BYTES


def parse_mcbs(text: str) -> list[dict[str, Any]]:
    """`DOS MCBS`: one row per block, `memory` from the heading it sits under. The debugger
    walks each chain by the sizes and prints its END OF CHAIN at the segment right past the
    last block, so a chain is read whole or not at all: every block after a chain's first
    starts right past the one above it, every size is whole paragraphs, the END OF CHAIN
    line sits right past the last block, and a chain lists at least one block. A chain's first
    block has nothing in the listing to check it against. A free block keeps the stale name
    the debugger prints; its `psp_seg` of `0000` is what says it is free."""
    rows: list[dict[str, Any]] = []
    memory = None   # the heading whose chain is open, None between chains
    next_seg: int | None = None   # where the open chain's next header sits, None before its first
    lines = _after(text, MCB_HEADING)
    for line in lines:
        if MCB_DATA_NOTE.match(line):
            continue
        if heading := MCB_MEMORY.match(line):
            if memory is not None:
                raise Unreadable(line, "printed a heading before the chain above it ended")
            memory = heading.group(1).lower()
            continue
        if memory is None:
            raise Unreadable(line, "printed a line outside any heading's chain")
        if end := MCB_END.match(line):
            if next_seg is None:
                raise Unreadable(line, "listed no block in the chain this line closes")
            if int(end[1], 16) != next_seg:
                raise Unreadable(line, "closed a chain anywhere but right past its last block")
            memory, next_seg = None, None
            continue
        m = MCB_ROW.match(line)
        if m is None:
            raise Unreadable(line)
        seg, size = int(m[1], 16), int(m[2])
        if size % PARAGRAPH_BYTES:
            raise Unreadable(line, "printed a size that is not whole paragraphs")
        if next_seg is not None and seg != next_seg:
            raise Unreadable(line, "printed a block that does not start right past the one "
                                   "above it")
        next_seg = next_mcb(seg, size)
        row: dict[str, Any] = {"memory": memory, "mcb_seg": m[1], "size_bytes": int(m[2]),
                               "psp_seg": m[3]}
        if note := MCB_NOTES.get(m[4]):
            row["notes"] = note
        row["filename"] = m[5]
        rows.append(row)
    last = lines[-1] if lines else MCB_HEADING
    if memory is not None:
        raise Unreadable(last, "ended before its END OF CHAIN line; its last line")
    if not rows:
        raise Unreadable(last, "listed no block; its last line")
    return rows


DEVS_ROW = re.compile(
    r"^([0-9A-F]{4}:[0-9A-F]{4}) ([0-9A-F]{4})  ([0-9A-F]{4})  ([0-9A-F]{4})  (.*?) *$")


def parse_devs(text: str) -> list[dict[str, Any]]:
    """`DOS DEVS`: the device chain, each driver's header address and its words."""
    return [{"header": m[1], "attr": m[2], "strat": m[3], "intr": m[4], "name": m[5]}
            for m in _each(_after(text, "Header    Attr  Strat Intr  Name"), DEVS_ROW)]


KERN_ROW = re.compile(r"^([0-9a-fA-F]{4}) +(\d+) +(.*?) *$")


def parse_kern(text: str) -> list[dict[str, Any]]:
    """`DOS KERN`: the kernel's own blocks (its segments print in lower case)."""
    lines = _after(text, "DOS kernel memory blocks:", "Seg      Size (bytes)     What")
    return [{"seg": m[1], "size_bytes": int(m[2]), "what": m[3]} for m in _each(lines, KERN_ROW)]


XMS_ROW = re.compile(r"^ +(\d+) (\S+) +(0x[0-9a-fA-F]+) (\d+)$")


def parse_xms(text: str) -> list[dict[str, Any]]:
    """`DOS XMS`: the allocated handles; the heading with no row is an empty list."""
    lines = _after(text, "XMS memory handles:", "Handle Status Location Size (bytes)")
    return [{"handle": int(m[1]), "status": m[2], "location": m[3], "size_bytes": int(m[4])}
            for m in _each(lines, XMS_ROW)]


EMS_TITLE = re.compile(r"^EMS memory \(type [^)]*\) handles:$")
EMS_ROW = re.compile(r"^ +(\d+) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) ?(.*?) *$")
EMS_FRAME = re.compile(r"^EMS page frame 0x[0-9a-fA-F]+-0x[0-9a-fA-F]+$")
EMS_PAGES_HEADING = "Handle Page(p/l) Address"
EMS_PAGE = re.compile(r"^(\S+) +(\d+/\d*) +([0-9a-fA-F]{8})-([0-9a-fA-F]{8})$")


def parse_ems(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """`DOS EMS`: the handles, and the page frame's pages. The listing prints a handle's size
    in HEX under `Size (bytes)`, and it is handed back as the integer it is. The frame's own
    line is dropped: its pages are the second list."""
    lines = listing_lines(text)
    if not lines or not EMS_TITLE.match(lines[0]):
        raise Unreadable(lines[0] if lines else "")
    body = _after("\n".join(lines[1:]), "Handle Address  Size (bytes)    Name")
    handles: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    in_pages = False
    for line in body:
        if EMS_FRAME.match(line):
            continue
        if line.rstrip() == EMS_PAGES_HEADING:
            in_pages = True
            continue
        m = (EMS_PAGE if in_pages else EMS_ROW).match(line)
        if m is None:
            raise Unreadable(line)
        if in_pages:
            pages.append({"handle": m[1], "page": m[2], "start": m[3], "end": m[4]})
        else:
            handles.append({"handle": int(m[1]), "addr": st.flat(int(m[2], 16)),
                            "size_bytes": int(m[3], 16), "name": m[4]})
    return handles, pages


# ------------------------------------------------------------------ BIOS and emulator


BIOS_ROW = re.compile(r"^([0-9a-fA-F]{8})-([0-9a-fA-F]{8}) (FREE|ALLOC +[A-Z]+) *(.*?) *$")


def parse_bios_mem(text: str) -> list[dict[str, Any]]:
    """`BIOS MEM`: the BIOS's blocks, free ones included; `status` with its words single-spaced."""
    lines = _after(text, "BIOS memory blocks:", "Region            Status What")
    return [{"start": m[1], "end": m[2], "status": " ".join(m[3].split()), "what": m[4]}
            for m in _each(lines, BIOS_ROW)]


CALLBACK_ROW = re.compile(r"^  \[(\d+)\] func=0x[0-9a-fA-F]+ desc='(.*)'$")
CALLBACK_END = re.compile(r"^-+$")


def parse_callbacks(text: str) -> list[dict[str, Any]]:
    """`CALLBACKS`: the emulator's callback slots as printed, an empty one included. The host
    function pointer is dropped: it differs every run and names nothing in the guest."""
    lines = _after(text, "Callbacks")
    if not lines or not CALLBACK_END.match(lines[-1]):
        raise Unreadable(lines[-1] if lines else "")
    return [{"number": int(m[1]), "desc": m[2]} for m in _each(lines[:-1], CALLBACK_ROW)]


EMU_MEM_ROW = re.compile(r"^([A-Za-z0-9 ]+?): +(\S+)( bytes)?$")


def parse_emu_mem(text: str) -> dict[str, Any]:
    """`EMU MEM`: each `label: value` line under its label's words; a decimal number is an
    integer, anything else (`ON`, a mask) the text printed."""
    out: dict[str, Any] = {}
    for m in _each(_after(text, "Emulator memory:"), EMU_MEM_ROW):
        key = m[1].lower().replace(" ", "_") + ("_bytes" if m[3] else "")
        out[key] = int(m[2]) if m[2].isdigit() else m[2]
    return out


MACHINE_ROW = re.compile(r"^Machine: (.+?) *$")


def parse_emu_machine(text: str) -> str:
    """`EMU MACHINE`: the machine line's text."""
    lines = _after(text, "Emulator machine:")
    rows = _each(lines, MACHINE_ROW)
    if len(rows) != 1:
        raise Unreadable(lines[1] if len(lines) > 1 else "")
    return rows[0][1]


# ------------------------------------------------------------------ the cpu


CPU_ROWS = (
    re.compile(r"^cr0:([0-9A-F]{8}) cr2:([0-9A-F]{8}) cr3:([0-9A-F]{8})  cpl=(\d)$"),
    re.compile(r"^eflags:([0-9A-F]{8}) \[vm=(\d) iopl=(\d) nt=(\d)\]$"),
    re.compile(r"^GDT base=([0-9A-F]{8}) limit=([0-9A-F]{8})$"),
    re.compile(r"^IDT base=([0-9A-F]{8}) limit=([0-9A-F]{8})$"),
    re.compile(r"^TR selector=([0-9A-F]{4}), base=([0-9A-F]{8}) limit=([0-9A-F]{8}\*\d+)$"),
    re.compile(r"^LDT selector=([0-9A-F]{4}), base=([0-9A-F]{8}) limit=([0-9A-F]{8}\*\d+)$"),
)


def parse_cpu(text: str) -> dict[str, Any]:
    """`CPU`: the control registers, the flags the debugger breaks out, and the four tables'
    registers; a limit keeps the debugger's `*n` granularity suffix."""
    lines = listing_lines(text)
    if len(lines) != len(CPU_ROWS):
        raise Unreadable(lines[len(CPU_ROWS)] if len(lines) > len(CPU_ROWS) else
                         (lines[-1] if lines else ""))
    m = [row.match(line) for row, line in zip(CPU_ROWS, lines, strict=True)]
    for match, line in zip(m, lines, strict=True):
        if match is None:
            raise Unreadable(line)
    cr, fl, gdt, idt, tr, ldt = (x for x in m if x is not None)
    return {"cr0": cr[1], "cr2": cr[2], "cr3": cr[3], "cpl": int(cr[4]),
            "eflags": fl[1], "vm": int(fl[2]), "iopl": int(fl[3]), "nt": int(fl[4]),
            "gdt": {"base": gdt[1], "limit": gdt[2]}, "idt": {"base": idt[1], "limit": idt[2]},
            "tr": {"selector": tr[1], "base": tr[2], "limit": tr[3]},
            "ldt": {"selector": ldt[1], "base": ldt[2], "limit": ldt[3]}}


#: cr0's protection-enable and paging bits.
CR0_PE = 1
CR0_PG = 1 << 31
#: The `cpu_mode` words whose selectors name descriptors.
PROTECTED_MODES = frozenset({"protected", "paged"})


def cpu_mode(cpu: dict[str, Any]) -> str:
    """`real`, `protected` or `paged`, the words `status` uses, read off this listing's own cr0
    so the sections it gates come from the same moment."""
    cr0 = int(cpu["cr0"], 16)
    if not cr0 & CR0_PE:
        return "real"
    return "paged" if cr0 & CR0_PG else "protected"


DESC_TOP = re.compile(r"^([0-9A-F]{4}): b:([0-9A-F]{8}) type: ([0-9A-F]{2}) parbg$")
DESC_BOTTOM = re.compile(r"^ +l:([0-9A-F]{8}) dpl : (\d)  ([01]{5})$")


def parse_descriptors(text: str, table: str) -> list[dict[str, Any]]:
    """`GDT` or `LDT`: each descriptor's two lines as one row, its `parbg` digits under their
    letters. An all-zero slot (base, limit, type and bits) is a slot nothing set up, dropped."""
    lines = listing_lines(text)
    title = re.compile(rf"^{table} Base:[0-9A-F]{{8}} Limit:[0-9A-F]{{8}}$")
    if not lines or not title.match(lines[0]):
        raise Unreadable(lines[0] if lines else "")
    body = lines[1:]
    if len(body) % 2:
        raise Unreadable(body[-1])
    rows: list[dict[str, Any]] = []
    for top_line, bottom_line in zip(body[::2], body[1::2], strict=True):
        top, bottom = DESC_TOP.match(top_line), DESC_BOTTOM.match(bottom_line)
        if top is None:
            raise Unreadable(top_line)
        if bottom is None:
            raise Unreadable(bottom_line)
        if (top[2], bottom[1], top[3], bottom[3]) == ("00000000", "00000000", "00", "00000"):
            continue
        row: dict[str, Any] = {"selector": top[1], "base": top[2], "limit": bottom[1],
                               "type": top[3], "dpl": int(bottom[2])}
        row.update(zip("parbg", (int(bit) for bit in bottom[3]), strict=True))
        rows.append(row)
    return rows


PAGE_ROW = re.compile(r"^page ([0-9A-F]+)xxx -> ([0-9A-F]+)xxx  flags (.+?) \[d=(\d)\|a=(\d)\]$")
PAGE_SIZE = 0x1000


def parse_paging(text: str) -> list[dict[str, Any]]:
    """`PAGING`: the present pages, merged into runs contiguous in linear AND physical memory
    with identical flags, `d` and `a`, so expanding a run page by page gives the listing back.
    `start` and `end` are the run's linear bytes, `phy` the physical address of its start."""
    runs: list[dict[str, Any]] = []
    last: tuple[int, int, str, int, int] | None = None
    for m in _each(listing_lines(text), PAGE_ROW):
        lin, phy = int(m[1], 16), int(m[2], 16)
        kind = (m[3], int(m[4]), int(m[5]))
        if last is not None and lin == last[0] + 1 and phy == last[1] + 1 \
                and kind == last[2:]:
            runs[-1]["end"] = f"{lin * PAGE_SIZE + PAGE_SIZE - 1:08X}"
        else:
            runs.append({"start": f"{lin * PAGE_SIZE:08X}",
                         "end": f"{lin * PAGE_SIZE + PAGE_SIZE - 1:08X}",
                         "phy": f"{phy * PAGE_SIZE:08X}", "flags": kind[0], "d": kind[1],
                         "a": kind[2]})
        last = (lin, phy, *kind)
    return runs


# ------------------------------------------------------------------ the map


Parser = Callable[[str], Any]


class Section(NamedTuple):
    """One debugger command and the reply keys it fills; `DOS EMS` fills two, and its parser
    returns one value per name."""
    names: tuple[str, ...]
    command: str
    parse: Parser


#: The sections read in every mode, in order.
EVERY_MODE: tuple[Section, ...] = (
    Section(("mcbs",), "DOS MCBS", parse_mcbs),
    Section(("devs",), "DOS DEVS", parse_devs),
    Section(("kern",), "DOS KERN", parse_kern),
    Section(("xms",), "DOS XMS", parse_xms),
    Section(("ems", "ems_pages"), "DOS EMS", parse_ems),
    Section(("bios_mem",), "BIOS MEM", parse_bios_mem),
    Section(("callbacks",), "CALLBACKS", parse_callbacks),
    Section(("emu_mem",), "EMU MEM", parse_emu_mem),
    Section(("machine",), "EMU MACHINE", parse_emu_machine),
    Section(("cpu",), "CPU", parse_cpu),
)

#: Only in protected mode: in real mode the debugger reads the interrupt vector table as
#: descriptors.
DESCRIPTOR_TABLES: tuple[Section, ...] = (
    Section(("gdt",), "GDT", functools.partial(parse_descriptors, table="GDT")),
    Section(("ldt",), "LDT", functools.partial(parse_descriptors, table="LDT")),
)
#: Only with paging on.
PAGE_TABLE = Section(("paging",), "PAGING", parse_paging)


@dataclasses.dataclass
class Reading:
    """What one pass over the listings found, whole: each section present, the command behind
    it, why each absent one is absent, and the mode the `CPU` listing put the machine in."""
    mode: str | None = None
    found: dict[str, Any] = dataclasses.field(default_factory=dict)
    sources: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    notes: list[str] = dataclasses.field(default_factory=lambda: [
        "read from the debugger's own listings at this stop, through the session's logfile"])

    def take(self, session: ds.Session, section: Section) -> None:
        """One command's sections, or the reason they are absent."""
        text = session.listing(section.command)
        which = (" and ".join(f"`{n}`" for n in section.names)
                 + (" are" if len(section.names) > 1 else " is"))
        said = refusal(text)
        if said is not None:
            self.notes.append(f"{which} absent: `{section.command}` answered \"{said}\"")
            return
        if not listing_lines(text):
            self.notes.append(f"{which} absent: `{section.command}` printed nothing")
            return
        try:
            value = section.parse(text)
        except Unreadable as e:
            self.notes.append(f"{which} absent: {e.sentence(section.command)}")
            return
        parts = value if len(section.names) > 1 else (value,)
        for name, part in zip(section.names, parts, strict=True):
            self.found[name] = part
            self.sources[name] = [section.command]


def read(session: ds.Session, wanted: frozenset[str] | None = None) -> Reading:
    """Every section this machine's mode has, read live and whole, one command each; with
    `wanted`, only the sections named there (and always `cpu`, which says the mode)."""
    reading = Reading()

    def take(section: Section) -> None:
        if wanted is None or "cpu" in section.names or wanted & set(section.names):
            reading.take(session, section)

    for section in EVERY_MODE:
        take(section)
    if "cpu" in reading.found:
        reading.mode = cpu_mode(reading.found["cpu"])
    if reading.mode is None:
        reading.notes.append("`gdt`, `ldt` and `paging` are absent: without the `CPU` listing "
                             "the mode is unknown")
        return reading
    if reading.mode == "real":
        reading.notes.append("`gdt` and `ldt` are absent: the cpu is in real mode, where the "
                             "debugger reads the interrupt vector table as descriptors")
    else:
        for section in DESCRIPTOR_TABLES:
            take(section)
    if reading.mode == "paged":
        take(PAGE_TABLE)
    else:
        reading.notes.append("`paging` is absent: paging is off")
    return reading


def add_section(reply: dict[str, Any], name: str, value: Any, sources: list[str],
                why: str) -> None:
    """A section read outside `read` put into `machine_map`'s reply the way `read`'s own are:
    `value` under `name` with its `sources`, or, when `value` is None, absent and `why` added to
    `coverage_note`."""
    if value is None:
        reply["coverage_note"] += f". `{name}` is absent: {why}"
        return
    reply[name] = value
    reply["sources"][name] = sources


#: Every section `machine_map` can answer, in reply order; `vga` is `dosbox_vga`'s, read last.
SECTION_NAMES: tuple[str, ...] = (
    *(n for s in EVERY_MODE for n in s.names), *(n for s in DESCRIPTOR_TABLES for n in s.names),
    *PAGE_TABLE.names, "vga")
#: What a map answers when it is asked for no section: the DOS machine, the cpu and, in protected
#: mode, the descriptor tables. Left out: the BIOS's blocks and callbacks, the VGA's registers and
#: the page runs, which together are most of a whole map and are seldom the question.
DEFAULT_SECTIONS = frozenset({"mcbs", "devs", "kern", "xms", "ems", "ems_pages", "emu_mem",
                              "machine", "cpu", "gdt", "ldt"})


#: How a short map asks for the rest: the sections it left out, or every row of a cut list.
MAP_HOW = ("sections=[...] names the sections to read; dest=<absolute path> writes every section "
           "read whole")
MAP_CUT_HOW = "dest=<absolute path> writes every row of every section read"


def sections_of(mode: str | None) -> list[str]:
    """The sections a machine in `mode` has: no descriptor table in real mode or when the mode
    is unknown, and page runs only with paging on."""
    absent = {"gdt", "ldt", "paging"} if mode in (None, "real") else (
        set() if mode == "paged" else {"paging"})
    return [n for n in SECTION_NAMES if n not in absent]


def machine_map(session: ds.Session, chosen: list[str]) -> dict[str, Any]:
    """`read` of the `chosen` sections (and `CPU`, which says the mode), then the reply:
    `cpu_mode`, the sections, `counts` (each list's full length), `sources` and `coverage_note`.
    `vga` is the caller's to add. Lists are WHOLE here: cutting them is the reply's business."""
    reading = read(session, frozenset(chosen))
    found = {n: v for n, v in reading.found.items() if n in chosen}
    return {"cpu_mode": contract.or_unavailable(reading.mode, NO_MODE_WHY), **found,
            "counts": {n: len(v) for n, v in found.items() if isinstance(v, list)},
            "sources": {n: v for n, v in reading.sources.items() if n in chosen},
            "coverage_note": ". ".join(reading.notes)}


def cut_lists(whole: dict[str, Any]) -> dict[str, Any]:
    """`whole` with each list cut at the server's list ceiling, and `truncated` saying whether
    any was."""
    ceiling = dlogs.LOG_LIMIT_MAX
    return {**{n: (v[:ceiling] if n in whole["counts"] else v) for n, v in whole.items()},
            "truncated": any(n > ceiling for n in whole["counts"].values())}


# ------------------------------------------------------------------ the interrupt vectors


INTVEC_ROW = re.compile(r"^INT ([0-9A-F]{2}):  ([0-9A-F]{4}):([0-9A-F]{4,8})$")
VECTOR_COUNT = 256


def parse_intvec(text: str) -> list[dict[str, Any]]:
    """The file `INTVEC` writes: every vector, `INT nn:  SSSS:OOOO`, in order. A file that is
    not the whole table, in order, is not the table."""
    rows = _each(listing_lines(text), INTVEC_ROW)
    if [int(m[1], 16) for m in rows] != list(range(VECTOR_COUNT)):
        raise Unreadable(f"{len(rows)} rows, not vectors 00 to FF in order")
    return [{"number": int(m[1], 16), "seg_off": st.seg_off(int(m[2], 16), int(m[3], 16))}
            for m in rows]


#: The sections whose rows can hold a handler, asked in this order, and the ones a vector is
#: placed through (the mode comes with the `CPU` listing, which `read` always takes).
HOLDER_SECTIONS = ("mcbs", "kern", "bios_mem")
PLACEMENT_SECTIONS = frozenset({*HOLDER_SECTIONS, "gdt", "ldt", "paging"})

#: A selector's table-indicator bit and its requested-privilege mask: the descriptor listings
#: print a selector with the indicator kept and the privilege cleared.
SELECTOR_TI_BIT = 0x4
SELECTOR_RPL_MASK = 0x3


def _held_range(section: str, row: dict[str, Any]) -> tuple[int, int]:
    """The bytes a row of a holder section covers, `[start, end)`. An MCB's block is its header
    paragraph and the `size_bytes` after it; a kernel block its `size_bytes` from its segment;
    a BIOS region its inclusive `start`-`end`."""
    if section == "mcbs":
        seg = int(row["mcb_seg"], 16)
        return seg * PARAGRAPH_BYTES, next_mcb(seg, int(row["size_bytes"])) * PARAGRAPH_BYTES
    if section == "kern":
        start = int(row["seg"], 16) * PARAGRAPH_BYTES
        return start, start + int(row["size_bytes"])
    return int(row["start"], 16), int(row["end"], 16) + 1


def table_of(sel: int) -> str:
    """The descriptor table a selector names: the LDT when its table indicator is set."""
    return "ldt" if sel & SELECTOR_TI_BIT else "gdt"


def descriptor(found: dict[str, Any], sel: int) -> dict[str, Any] | None:
    """The row of `table_of(sel)` the selector names, its requested privilege cleared (the
    listing prints a selector with RPL 0); None when the table carries no such row. What a
    caller requires of the row (present, code, a privilege) is the caller's to judge."""
    want = f"{sel & ~SELECTOR_RPL_MASK:04X}"
    rows: list[dict[str, Any]] = found.get(table_of(sel)) or []
    return next((r for r in rows if r["selector"] == want), None)


def vector_linear(addr: str, mode: str | None, found: dict[str, Any]) -> tuple[int | None, str]:
    """Where a vector's handler is, as a linear address, and why not when it cannot be said. In
    real mode `segment*16 + offset`; in protected mode the base of the descriptor the selector
    names, in the LDT when its table indicator is set, plus the offset."""
    seg_text, off_text = addr.split(":")
    sel, off = int(seg_text, 16), int(off_text, 16)
    if mode == "real":
        return sel * PARAGRAPH_BYTES + off, ""
    if mode is None:
        return None, "the mode is unknown"
    table = table_of(sel)
    if table not in found:
        return None, f"`{table}` is absent"
    row = descriptor(found, sel)
    if row is None:
        return None, f"their selector names no descriptor in `{table}`"
    return int(row["base"], 16) + off, ""


def physical_address(linear: int, runs: list[dict[str, Any]]) -> int | None:
    """A linear address through the page runs, or None when no run maps it."""
    for run in runs:
        start = int(run["start"], 16)
        if start <= linear <= int(run["end"], 16):
            return int(run["phy"], 16) + linear - start
    return None


def holder(address: int, found: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """The first row of `HOLDER_SECTIONS`, in that order, whose bytes hold `address`."""
    for section in HOLDER_SECTIONS:
        for row in found.get(section, []):
            low, high = _held_range(section, row)
            if low <= address < high:
                return section, row
    return None


#: `cpu_mode` when the `CPU` listing could not be read or placed the mode nowhere.
NO_MODE_WHY = "the `CPU` listing was unreadable, so the mode is not known"
NO_LOGFILE_BLOCKS = "no vector has a holder: the blocks are"
NO_LOGFILE_TABLES = ("no vector has a holder, an `addr` or a `symbol`: the blocks and the "
                     "descriptor tables are")
NO_LOGFILE_WHY = (" read off the session's logfile and this session was started without one "
                  "(`start` with `logfile`)")


def interrupt_vectors(session: ds.Session, number: int | None) -> dict[str, Any]:
    """The table `INTVEC` writes, each vector with its handler's linear address, the row of the
    MCB chain, the kernel's blocks or the BIOS's that holds it, and the nearest symbol; one
    vector when `number` is given. Without a logfile there are no listings: no row has a
    holder, in protected mode none has an `addr` or a `symbol` either (the descriptor tables
    are listings too), and the mode is the one `status` reports."""
    try:
        rows = parse_intvec(session.intvec())
    except Unreadable as e:
        raise ds.Invalid("unexpected_answer",
            f"`INTVEC` wrote a file that is not the vector table: {e.line}") from None
    tables_unread = False
    if session.launch.logfile is None:
        facts = running.status_facts(session).get("cpu_mode")
        mode = facts if isinstance(facts, str) else None       # unavailable: the mode unknown
        tables_unread = mode in PROTECTED_MODES
        reading = Reading(mode=mode, notes=[
            (NO_LOGFILE_TABLES if tables_unread else NO_LOGFILE_BLOCKS) + NO_LOGFILE_WHY])
    else:
        reading = read(session, PLACEMENT_SECTIONS)
    reading.sources = {"vectors": ["INTVEC"], **reading.sources}
    if all(r["seg_off"] == st.seg_off(0, 0) for r in rows):
        reading.notes.append("every vector is 0000:0000: nothing has filled the table yet")
    elif not tables_unread:
        reading.notes.extend(_place(rows, reading))
    chosen = [r for r in rows if number is None or r["number"] == number]
    return {"cpu_mode": contract.or_unavailable(reading.mode, NO_MODE_WHY), "vectors": chosen,
            "counts": {"vectors": len(rows),
                       "held": sum(1 for r in rows if any(s in r for s in HOLDER_SECTIONS)),
                       "named": sum(1 for r in rows if "symbol" in r)},
            "sources": reading.sources, "coverage_note": ". ".join(reading.notes)}


def _vectors(n: int) -> str:
    return f"{n} vector{'' if n == 1 else 's'}"


def _place(rows: list[dict[str, Any]], reading: Reading) -> list[str]:
    """Each row's `addr`, the holder row and its `symbol`, in place; what could not be placed,
    and why, comes back as notes."""
    without: dict[str, int] = {}
    unmapped = 0
    found = reading.found
    pages = found.get("paging") if reading.mode == "paged" else None
    holders = any(s in found for s in HOLDER_SECTIONS) and (
        reading.mode != "paged" or pages is not None)
    notes = []
    if reading.mode == "paged" and pages is None:
        notes.append("no vector has a holder: the blocks are matched through the page runs, "
                     "and `paging` is absent")
    span = placement.symbol_span()
    for row in rows:
        lin, why = vector_linear(row["seg_off"], reading.mode, found)
        if lin is None:
            without[why] = without.get(why, 0) + 1
            continue
        row["addr"] = st.flat(lin)
        if holders:
            address = lin if pages is None else physical_address(lin, pages)
            if address is None:
                unmapped += 1
            elif (held := holder(address, found)) is not None:
                row[held[0]] = held[1]
        if span is not None and span[0] <= lin <= span[1]:
            symbol = placement.nearest_symbol(lin)
            if symbol is not None:
                row["symbol"] = symbol
    notes += [f"no `addr` for {_vectors(n)}: {why}" for why, n in without.items()]
    if unmapped:
        notes.append(f"no holder for {_vectors(unmapped)}: no page run maps their linear "
                     f"address")
    return notes
