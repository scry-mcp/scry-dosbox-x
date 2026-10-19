"""The grammar of the debugger's console: what its terminal paints (the ANSI it strips, the prompt,
the pager), the register pane and the reply shapes its commands print, each parsed here and only
here."""

from __future__ import annotations

import re

from scry_core.reply_contract import Invalid

# Escape sequences an ncurses screen is made of. Stripped before anything is matched,
# because a reply's text is interleaved with cursor addressing.
#
# IT IS DELIBERATELY WIDER THAN CSI: an unstripped OSC leaks its payload into the
# buffer as ordinary text, and that buffer is what the prompt and the register pane
# are searched for.
ANSI = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"      # CSI, intermediates included
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC, BEL- or ST-terminated
    r"|\x1b[()][A-Z0-9]"              # charset selection
    r"|\x1b[=>]")


# An ESCAPE SEQUENCE can straddle two reads. Anything that looks like the start of one
# is HELD BACK and prepended to the next read rather than being stripped as text --
# otherwise its head lands in the buffer as literal junk and its tail as plain
# characters.
#
# WHAT IT DOES NOT DO. `PARTIAL_TAIL.search('EAX=0000')` is None, so a plain-text split
# mid-number is NOT held here: what saves such a value is `Session._collect` concatenating across
# reads, which is a different function's accident. And a multi-byte character cannot be
# held either: `Session._read`
# decodes with `errors="replace"` BEFORE this is consulted, so a split UTF-8 sequence
# is already a replacement character by then.
PARTIAL_TAIL = re.compile(r"\x1b(?:\[[0-9;?]*[ -/]*|\][^\x07\x1b]*|[()])?$")


# The debugger's own prompt. Its appearance is how "the debugger is up" is known,
# rather than a fixed sleep.
#
# IT HAS A SECOND READER AND THAT ONE IS LOAD-BEARING: `resume` uses it to tell a
# machine that ran on from one that stopped again, because it is the only thing in
# that delta which says the debugger has the keyboard back. The register pane does
# NOT come back there -- ncurses repaints changed cells only, and the pane's labels do
# not change -- so the reading that looks obvious is the one that fails. The twelve-run
# measurement behind that is in `resume`'s own docstring, beside the numbers.
PROMPT = "I->"


# THE PAGER. A listing longer than the debugger's Output pane stops after a page with this
# line under it and the command still on the input line, and from there every key is a key
# the pager eats: a command typed at it can strand its tail on the input line, and from there
# every later command concatenates onto it instead of running. `Q` alone, with no carriage
# return (the debugger's own "Q to exit paging"), prints the rest of the listing at once and
# empties the line, so it is the one key `Session.listing` sends there.
PAGER_MARK = "Paged content: Hit ENTER to continue"


PAGER_EXIT = b"Q"


# THE DEBUGGER'S OWN LAST WORDS: it closes the repaint that answers a command by redrawing its
# input line EMPTY (`I-> `, the cursor mark, erase to the end of the line, the cursor placed, the
# attributes reset), or by its pager's line when a listing pages; a listing that pages draws the
# input line still holding the command, which is why only the empty one counts. Nothing follows
# either until the next command.
_ATTRS = r"(?:\x1b\[[0-9;]*m)*"


REPLY_END = re.compile(
    r"(?:I-> _?\x1b\[K(?:\x1b\[\d+;\d+H|\r\x1b\[\d+d)\x1b\(B\x1b\[m" + _ATTRS
    + r"|Paged content: Hit ENTER to continue, Q to exit paging\x1b\[K(?:\x1b\[\d+;\d+H)?"
    r"\x1b\(B\x1b\[m" + _ATTRS + r"(?:\x1b\[\d+;\d+H)?)\Z")


# The register pane.
#
# NO WORD BOUNDARY, and that is the whole lesson of this line. An ncurses pane is
# painted as runs of cells and the debugger draws its frames with the DEC alternate
# character set, which arrives here as ordinary letters -- so a register name abuts
# the run in front of it. MEASURED against a live emulator, the screen carried
# `...ooooooooooooEAX=00001234  ESI=00000000`, where `\b` finds no boundary between
# `o` and `E`. The effect was silent and one-sided: every register whose name happened
# to follow a space was read, and EAX -- the one a caller sets to prove the machine
# answered -- was the one that never matched.
#
# The names are spelled out rather than built from character classes, longest first,
# so a shorter name cannot win inside a longer one.
WIDE_NAMES = ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP")


SEGMENT_NAMES = ("CS", "DS", "ES", "FS", "GS", "SS")


REGISTER_NAMES = WIDE_NAMES + SEGMENT_NAMES


REGISTER = re.compile(f"({'|'.join(REGISTER_NAMES)})=([0-9A-F]+)")


# How much of the previous read `run_to`'s wait carries forward, so a register that
# arrives split across two reads is still matched.
#
# IT IS THE NAME PLUS ITS `=`, AND NOTHING MORE, which is smaller than it first looks
# and is the whole of what must be carried. `REGISTER` is `(NAME)=([0-9A-F]+)` with a
# `+` on the value, so the moment ONE hex digit has arrived the prefix matches on its
# own: `EIP=0000E05` is a match, and the `B` landing in the next read costs nothing.
# The only split that loses a match is one falling inside `NAME=` itself, and the
# widest of those is the whole of it.
#
# THE FIRST VERSION WAS `... + 1 + 32` and its comment called it DERIVED while
# describing "a value wider than any 32-bit register this debugger prints" -- a
# hand-picked 32 wearing a derivation's clothes, and the term that would have gone
# stale. An adversarial pass could not pin it at any width, for the reason above:
# every fixture needing a carry wider than `NAME=` already matched without one.
EIP_CARRY = max(len(n) for n in REGISTER_NAMES) + 1


# The wait in `run_to` listens for TWO announcements of a stop, the prompt and a register
# repaint, and its carry has to be wide enough that neither can straddle two reads.
STOP_CARRY = max(EIP_CARRY, len(PROMPT))


# What `SR` will accept as a register name. It is checked rather than trusted: `SR`
# takes MULTIPLE pairs ("SR [reg] [value] - Set register value. Multiple pairs
# allowed"), and `command()` appends a carriage return, so an unchecked name is a way
# to run debugger commands the caller never named.
LOW_HALVES = frozenset({"ax", "bx", "cx", "dx", "si", "di", "bp", "sp", "ip"})


SETTABLE = frozenset(n.lower() for n in REGISTER_NAMES) | LOW_HALVES


# THE CPU MODE, AS A POSITIVE TOKEN IN EVERY DIRECTION.
#
# MEASURED, in one session walked from reset to a DJGPP client:
#
#   SS=0000 Real     at F000:FFF0, before anything has switched mode
#   SS=008F Pr16     inside CWSDPMI's 16-bit stub
#   SS=008F Pr32     in the 32-bit client
#
# WHY A POSITIVE TOKEN MATTERS HERE, and it is the whole reason this is a regex over
# three alternatives rather than a test for the ABSENCE of `Pr`: a pane that did not
# repaint, a machine that is running and an emulator that has gone all produce text
# with no `Pr` in it. Read as an absence, every one of them answers "real mode" -- and
# `watch` would then send `BPM` where the machine wanted `BPPM`, which the debugger
# accepts and arms against a segment that does not exist. A missing token is INVALID
# here, never a mode.
REAL_MODE = "Real"


CPU_MODES = (REAL_MODE, "Pr16", "Pr32")


# IT IS ANCHORED ON THE `SS=` LINE, and that is not tidiness -- an unanchored version
# was a live wrong answer. `Real` is an ordinary English word, the Output pane is a
# scrolling LOG carrying DOSBox-X's own messages and the guest's E9 lines, and that
# pane is painted BELOW the register pane. So a bare `\b(Real|Pr16|Pr32)\b` taking the
# LAST match deliberately preferred the one region of the screen that can say anything
# at all: a `Pr32` machine whose log happened to carry the word "Real" answered `Real`,
# and `watch` then sent `BPM` where the machine wanted `BPPM` -- which this debugger
# accepts and arms against a segment that does not exist.
#
# The token's place is fixed: it closes the `SS=` line of the register pane
# (`SS=008F Pr32`). Anchoring there means only a register pane can supply it.
CPU_MODE = re.compile(rf"SS=[0-9A-F]{{4}}\s+({'|'.join(CPU_MODES)})\b")


# PAGING, THE OTHER HALF OF "WHAT MODE", read off the same pane: the debugger paints `PAGE`
# or `NOPG` straight after EBP's value, with no space (`EBP=00000000NOPG  IOPL0  CPL0` in
# real mode, `EBP=002B8690PAGEPSE IOPL3  CPL3` under a DJGPP client). Anchored on `EBP=`
# for the reason `CPU_MODE` is anchored on `SS=`: both words can turn up in the log pane.
PAGING = re.compile(r"EBP=[0-9A-F]{8}(PAGE|NOPG)")


# THE PANE'S OWN EMULATED CLOCK, in milliseconds since the machine started: `pfi=` beside the FPU
# row. Only a full repaint labels it; the delta a stop prints carries its changed digits bare, so
# it is read off a survey and never off a stop's own delta.
PANE_CLOCK = re.compile(r"pfi=([0-9]+\.[0-9]+)")


# THE PANE'S INSTRUCTION COUNTER, `cc=` closing the ESP row before the run state (`RUN`, `HLT`).
# Anchored on that TAIL and not on `ESP=`: a repaint can glue other text over the label before it
# (`dpl : 3 10011    cc=1963039400RUN` under a DJGPP client). On the normal core the counter
# moves by one per instruction executed; a dynamic core leaves it where it was.
PANE_CYCLES = re.compile(r"cc=([0-9]+) *[A-Z]+\r?$", re.M)


# ONE ROW OF THE DEBUGGER'S BREAKPOINT LIST, as `BPLIST` prints it:
#
#   00. BPMEM 0040:006C (00)
#   01. BP F000:E05B
#
# The index is captured because `BPDEL` takes one, and the REST OF THE LINE is kept
# whole rather than split into a kind and an address: the forms differ per breakpoint
# type (`BPMEM` carries a trailing byte count, `BPINT` names an interrupt and an AH)
# and this module needs to RECOGNISE an entry it created, not to model every shape the
# debugger can print.
#
# IT IS NOT ANCHORED TO THE START OF A LINE, and it was -- the last of the three pane
# patterns to learn what `REGISTER` and `DATA_ROW` each learned from a measured defect.
# This debugger's repaints GLUE content to whatever precedes it with no newline (the
# captures in the test file show `ooooOutputoooo...Breakpoint list:`), so a row arriving
# as `----------------00. BP F000:FFF0` matched nothing. The bad direction is not the
# refusal: it is `run_to`'s cleanup, which reads `removed = not any(...)` and would
# report `breakpoint_removed: true` for a breakpoint still sitting in the machine.
# `$` with `re.M` still anchors the END, and the two hex digits must be followed by a
# dot AND whitespace, which is what keeps it off `pfi=0.992628993` and `92.464754300`.
BREAKPOINT_ROW = re.compile(r"\s*([0-9A-F]{2})\.\s+(\S.*?)\s*$", re.M)


# The header `BPLIST` prints above its list. The LAST one in a delta is the one that
# belongs to the command just sent: this debugger's Output pane is a SCROLLING LOG, so
# a repaint carries earlier listings and earlier acknowledgements along with the new
# one. MEASURED -- a second `BPLIST` came back with two headers, and a `BPM` delta
# carried the `DEBUG: Set breakpoint at F000:E05B` from a `BP` sent before it.
#
# That is why nothing here believes an acknowledgement. A breakpoint is confirmed by
# READING THE LIST BACK, the same discipline `load_symbols` uses on the var list and
# for the same reason: this emulator will happily reprint somebody else's success.
BPLIST_HEADER = "Breakpoint list:"


# The banner the debugger paints at the top of the register pane, and therefore the
# only reliable mark of where one REPAINT ends and the next begins. `parse_last_pane`
# rests on it, so it is measured rather than assumed:, three
# consecutive surveys each carried exactly ONE occurrence, at the same offset, above
# fifteen register hits in a fixed order.
#
# IT IS THE TEXT AND NOT THE BOX-DRAWING AROUND IT. The terminal renders the banner's
# rule as runs of `o` (`ooooRegister Overviewoooo...`), whose length depends on the
# window, so anchoring on those would be anchoring on a geometry.
PANE_HEADER = "Register Overview"


# ONE ROW OF THE DEBUGGER'S DATA VIEW, matched by its SHAPE and not by which pane it
# was found in.
#
# WHY BY SHAPE. The panes are separated by headers drawn in the DEC alternate
# character set, which arrives here as runs of `o`, and anchoring on those would tie
# the one reader that returns MEMORY to how this build decorates its frames. The shape
# is unambiguous on its own: sixteen space-separated byte pairs after an address is
# something only the data view emits. In particular it cannot match a CODE row, whose
# bytes are run together (`F000:0000FFF0 EA5BE000F0          jmp  F000:E05B`), so the
# first pair test fails on the missing space -- and the code overview sits on the same
# screen, showing the same segment, in rows that begin identically.
#
# THERE IS NO `^`, AND ITS ABSENCE IS THE WHOLE LESSON OF THIS LINE, exactly as it is
# for REGISTER above. An ncurses pane is painted as runs of cells, so the pane HEADER
# abuts the first row with no newline between them and the screen carries
# `ooooData view (segmented)oooo...ooooF000:0000E000 00 00 ...`. Anchored at line
# start, that row does not match -- and it is the FIRST row, which is the one at the
# address the caller asked about. MEASURED with the anchor in place: eight rows on
# screen, SEVEN parsed, and the missing one was E000 for a caller who asked for E000.
# The same defect as the register pattern's, in the same file, found by a test written
# after that comment had already explained it.
#
# The ASCII gutter is OPTIONAL because it is not the evidence. It is bounded at 16 and
# NO CHARACTER OF IT MAY BEGIN AN ADDRESS: without that, a row followed immediately by
# the next one had its gutter swallow the next row's ADDRESS, so the scan resumed
# mid-token and that row was lost entirely. `[^\r\n]` cannot prevent it, because the two
# rows are on ONE line to begin with, which is the whole reason this pattern is not
# anchored.
#
# THE LOOKAHEAD IS INSIDE THE REPETITION, AND THE FIRST ATTEMPT PUT IT OUTSIDE. That
# version guarded only the gutter's FIRST character, so it worked for an EMPTY gutter
# and for a FULL one and failed for every length between. MEASURED across all 17
# lengths: 0 and 16 recovered both rows, 1 through 15 lost the second and produced the
# INVALID that says "that is a reading of somewhere else" about a row present in the
# string it had just parsed -- verbatim the failure the fix claimed to remove. Its test
# and the check beside it were calibrated on length 0, so both were green: the axis moved
# was the lookahead's PRESENCE and never the gutter's LENGTH.
# The data view is eight rows of sixteen bytes on this build: the most `read_memory` can
# hand back as `hex` from a row's start.
DATA_VIEW_BYTES = 128


_ROW_BYTES = re.compile(r"([0-9A-F]{4}):([0-9A-F]{4,8})((?: [0-9A-F]{2})+)")


def bytes_of_rows(rows: list[str], off: int, length: int) -> str:
    """`length` bytes from offset `off` out of the data-view `rows`, as hex, read off the
    rows' own offsets and never by position: a row is `SEG:OFFSET` and sixteen bytes, so the
    bytes are collected from the row that holds `off` onwards. INVALID when the rows do not
    hold that many bytes from there."""
    held: dict[int, int] = {}
    for row in rows:
        # The row's OWN offset and bytes, whatever their width: the data view prints eight
        # hex digits and sixteen bytes on this build, and a row is read by what it says.
        m = _ROW_BYTES.search(row)
        if m is None:
            continue
        start = int(m.group(2), 16)
        for i, byte in enumerate(m.group(3).split()):
            held[start + i] = int(byte, 16)
    out: list[str] = []
    for a in range(off, off + length):
        if a not in held:
            raise Invalid("readback_refused",
                f"the data view holds {len(out)} bytes from offset {off:#x}, not the "
                f"{length} asked for: ask for fewer, or `memdump` the range")
        out.append(f"{held[a]:02x}")
    return "".join(out)


DATA_ROW = re.compile(
    r"([0-9A-F]{4}):([0-9A-F]{8})((?: [0-9A-F]{2}){16})"
    r"(?:  ((?:(?![0-9A-F]{4}:[0-9A-F]{8})[^\r\n]){0,16}))?")


def parse_registers(text: str) -> dict[str, str]:
    """The register pane of a debugger screen, as a mapping.

    Pure, so it can be held to a fixture rather than to a live emulator: what makes
    a reading trustworthy is that the VALUE came back, and that is a property of the
    text.

    IT IS LAST-WINS PER REGISTER, INDEPENDENTLY, which is what `parse_last_pane` exists
    to correct for anyone composing an ADDRESS out of two of them. This one keeps the
    permissive behaviour on purpose: `registers()` hands the whole mapping back for a
    human to read, and there the newest value of each is the useful answer.
    """
    return dict(REGISTER.findall(text))


def where_from(text: str) -> dict[str, str]:
    """The position (cs, eip, mode) parsed from an already-surveyed screen -- `where()`'s
    logic as a MODULE function, so a double that delegates `where`/`where_and_registers` to
    the real Session needs no extra method to stand in for it. Splitting it as a METHOD
    broke every such double at once (they had no `where_from`); a free function reads
    nothing off `self`, so nothing has to.
    """
    # THE LAST PANE, NOT THE WHOLE TEXT. `_survey`'s mapping is last-wins per register, so a
    # delta holding an old whole pane above a cut one composes an address out of both and
    # the `missing` check below cannot see it. `parse_last_pane` keeps only the newest
    # repaint, so a cut one comes back SHORT and the refusal fires.
    regs = parse_last_pane(text)
    cpu = parse_mode(text)
    if cpu is None:
        raise Invalid("unexpected_answer",
            f"the register pane came back but names no CPU mode (expected one of "
            f"{', '.join(CPU_MODES)}). Without it an address is ambiguous: the same "
            f"sixteen bits are a paragraph in real mode and a selector in protected mode")
    # THE TWO REGISTERS THIS IS ABOUT ARE REQUIRED. A CUT delta can carry `EAX=` and a mode
    # token and no `CS=`/`EIP=`; an empty eip handed on would die in `run_to` at
    # `int('', 16)` with a traceback, the worst reply from the method whose job is saying
    # where you are.
    missing = [n for n in ("CS", "EIP") if not regs.get(n)]
    if missing:
        raise Invalid("unexpected_answer",
            f"the register pane came back but carries no {' and no '.join(missing)}"
            f" (it had: {sorted(regs)}). That is a partial repaint, not a position: an "
            f"empty address would be passed on as if it were one")
    return {"cs": regs["CS"], "eip": regs["EIP"], "mode": cpu}


def parse_last_pane(text: str) -> dict[str, str]:
    """The registers of the LAST repaint only, so an address cannot be composed of two.

    `parse_registers` is `dict(findall(...))`, so every register is last-wins on its
    own. A delta carrying an old whole pane above a CUT one therefore yields a mapping
    that NEITHER repaint holds -- `CS` from the first and `EIP` from the second -- and
    the pair looks perfectly well formed, so the `missing` check downstream cannot see
    it. MEASURED on a fixture built from two panes: `where()` answered
    `{'cs': '0087', 'eip': '00012345'}` for a machine no repaint ever showed there, and
    `run_to` turned that into `arrived: True`.

    IT IS ANCHORED ON THE PANE'S OWN HEADER, not on the rule "a pane cannot name the
    same register twice" with a REPEAT as the start of the next repaint. That rule only
    sees a boundary when the two fragments OVERLAP in register names, and it fails in
    both directions:

      * TWO DISJOINT FRAGMENTS MERGE SILENTLY. A stale tail from `EIP` onwards
        (`EIP ECX EBP EDX ESP`) followed by a fresh head cut before `EIP`
        (`EAX ... CS`) repeats nothing, so every register comes back with `EIP` from one
        repaint and `CS` from the other, `missing` empty and `parse_mode` answering from
        the fresh half: verbatim the wrong answer the paragraph above describes.
      * AND IT REFUSES A COMPLETE PANE. The same stale tail followed by a WHOLE fresh
        repaint resets at the fresh `EIP`, throwing away the fresh `CS` read moments
        before, so `where()` refuses a delta whose last repaint was unambiguous.

    THE HEADER IS A MEASURED MARKER, not an inference from names: every repaint this
    debugger paints carries exactly one `Register Overview` banner, at the same offset,
    with the register hits in a fixed order after it.

    So the last banner is where the newest repaint starts. Two consequences, both
    deliberately in the refusing direction:

      * NO BANNER AT ALL means no complete repaint arrived in this delta, and `{}` is
        returned rather than a mapping assembled from fragments.
      * A REGISTER REPEATING AFTER THE LAST BANNER means a further, HEADERLESS fragment
        is sitting on top of it, and there is no way to say which repaint each value
        came from. `{}` again: a refusal beats a wrong answer of the right shape.
    """
    head = text.rfind(PANE_HEADER)
    if head < 0:
        return {}
    pane: dict[str, str] = {}
    for name, value in REGISTER.findall(text[head:]):
        if name in pane:
            return {}
        pane[name] = value
    return pane


def offset_ceiling(mode: str) -> int:
    """How wide an offset may be in a given CPU mode.

    ONE function because BOTH `run_to` and `watch` need the rule and a copy of it in
    each is a copy that can be fixed in one place only -- which is what happened: the
    16-bit clamp was corrected on `run_to` and left standing on `watch`, so a watch on
    a DJGPP static past 0xFFFF was refused outright while a breakpoint on one was not.

    In protected mode an offset is 32 bits, and MEASURED, the debugger takes one:
    `BP 0087:00012345` was accepted and listed as `BP 0087:12345`. In real mode
    anything past 0xFFFF addresses nothing, and this debugger would accept it and then
    never fire, which is the silent direction.

    IT IS NAMED FOR WHAT IT RETURNS, a ceiling, and not for a flag such as `wide`
    that would be True in REAL mode and then select the NARROW ceiling: a name saying
    the opposite of what it holds, one line above the comparison it feeds.
    """
    return 0xFFFFFFFF if mode.startswith("Pr") else 0xFFFF


def parse_pane_clock(text: str) -> float | None:
    """The emulated milliseconds the last pane on the screen paints, None when none says."""
    found = PANE_CLOCK.findall(text)
    return float(found[-1]) if found else None


def parse_pane_cycles(text: str) -> int | None:
    """The `cc=` the last pane on the screen paints, None when none says."""
    found = PANE_CYCLES.findall(text)
    return int(found[-1]) if found else None


def parse_paging(text: str) -> bool | None:
    """Whether the pane says paging is on (`PAGE`) or off (`NOPG`), the last pane winning as
    in `parse_mode`; None when no pane on the screen says either, which is not "off"."""
    found = PAGING.findall(text)
    return None if not found else found[-1] == "PAGE"


def parse_mode(text: str) -> str | None:
    """The CPU mode a debugger screen reports, or None if it does not report one.

    None is an ANSWER ABOUT THE TEXT and not a mode: the caller decides what to do
    with a screen that named none, and every caller here refuses. Returning "Real" for
    a screen with no token would be the same wrong-answer-of-the-right-shape that
    `selector` refuses when a real-mode descriptor reads as base 0.

    THE LAST ONE WINS, because the pane scrolls: a delta can carry a repaint of an
    earlier register pane above the current one, and the mode being asked about is the
    one the machine is in NOW.

    A LIMIT, said out loud, and HALF of it is now closed. This and `parse_registers` are
    each last-wins over the same text, and nothing checks they came from the SAME
    repaint. The half that WAS closed is the worse one: `parse_registers` is last-wins
    PER REGISTER, so a delta could compose an address out of a `CS` from one repaint and
    an `EIP` from another -- MEASURED, `where()` answered `{'cs': '0087', 'eip':
    '00012345'}` for a machine no repaint ever showed there, and `run_to` turned it into
    `arrived: True`. `parse_last_pane` is what `where()` reads now, so the address comes
    from one repaint or the refusal fires.

    WHAT IS STILL OPEN is the MODE against that address: this function is last-wins over
    the whole text independently of which pane the registers came from, so a delta
    holding an old real-mode pane below a newer protected one can still pair a mode with
    an address from a different repaint. Both readers are anchored to the register pane,
    so the window is narrow; it is not closed.
    """
    found = CPU_MODE.findall(text)
    return found[-1] if found else None


def parse_breakpoints(text: str) -> list[dict[str, str]]:
    """The debugger's breakpoint list, from the LAST listing in the text.

    `BPLIST` prints a header and then one indexed row per breakpoint. Taking the last
    header is not tidiness: the Output pane is a scrolling log, so a delta routinely
    holds an earlier listing as well, and reading from the FIRST one answers with the
    breakpoints that existed before the command that was just sent -- which is exactly
    the state a caller runs this to find out has changed.

    An empty list is an honest answer: the debugger prints the header with no rows
    when nothing is armed. A text with NO header at all returns empty too, and that is
    why every caller here checks for the header itself rather than treating "no rows"
    as "nothing armed": a pane that never repainted also has no rows.
    """
    at = text.rfind(BPLIST_HEADER)
    if at < 0:
        return []
    return [{"index": i, "entry": e}
            for i, e in BREAKPOINT_ROW.findall(text[at + len(BPLIST_HEADER):])]


# The kind token and the seg:off of a breakpoint row, as NUMBERS. `BP F000:E05B`,
# `BPMEM 0040:006C (00)`, `BPPM 00AF:00006024 (00)` all parse; `BPINT 21 AH=4C` does not,
# because it names an interrupt and not an address, and has no seg:off to match.
_BP_ROW_ADDR = re.compile(r"^(BP[A-Z]*)\s+([0-9A-Fa-f]+):([0-9A-Fa-f]+)")


def interrupt_row(number: int, ah: int | None) -> str:
    """The BPLIST row an interrupt breakpoint is listed as, in the debugger's own spelling.
    CAPTURED with both forms armed at once (`00. BPINT 21`,
    `01. BPINT 31 AH=00`): the AH half is ABSENT, not defaulted, when none was given. ONE
    function because three places need the same string -- the arming read-back, the clear,
    and the store's declaration -- and a spelling kept in three places drifts."""
    return f"BPINT {number:02X}" + (f" AH={ah:02X}" if ah is not None else "")


_INT_ROW = re.compile(r"^BPINT ([0-9A-Fa-f]{2})(?: AH=([0-9A-Fa-f]{2}))?$")


def parse_interrupt_row(row: str) -> tuple[int, int | None]:
    """The `(number, ah)` an interrupt row names, the inverse of `interrupt_row`. Refuses a
    string that is not one of its spellings, so a corrupt stored ref fails as INVALID here
    rather than reaching the console as a malformed `BPDEL`."""
    m = _INT_ROW.match(row.strip())
    if m is None:
        raise Invalid("unexpected_answer",
            f"{row!r} is not an interrupt breakpoint row (BPINT NN [AH=NN])")
    return int(m.group(1), 16), (int(m.group(2), 16) if m.group(2) is not None else None)


def bp_row_target(entry: str) -> tuple[str, int, int] | None:
    """A BPLIST row's kept text as `(kind, seg, off)` by VALUE, or None if it holds no
    seg:off.

    RECOGNITION IS BY THE NUMBERS, NEVER BY A RECONSTRUCTED SPELLING, because the width
    the debugger prints an offset at is not fixed: MEASURED, one watch address came back
    as both `BPPM 00AF:6024` and `BPPM 00AF:00006024`, and a code offset accepted as
    `BP 0087:00012345` listed as `BP 0087:12345`. So `f"BP {seg:04X}:{off:04X}"` compared
    for equality against the row the debugger actually printed reports a breakpoint that
    IS set as absent -- and then clears nothing and arms a duplicate. Parsing the fields
    and comparing the integers is immune to which width it chose. The kind token is kept
    so a code breakpoint (`BP`) is told from a memory watch (`BPMEM`/`BPPM`/`BPLM`) at the
    same address, which is the one thing the number alone cannot say.
    """
    m = _BP_ROW_ADDR.match(entry.strip())
    if m is None:
        return None
    return m.group(1), int(m.group(2), 16), int(m.group(3), 16)


def parse_data_view(text: str) -> list[str]:
    """The data-view rows of a debugger screen, in the order they were painted.

    Pure, like `parse_registers` and for the same reason: what makes a reading
    trustworthy is that the BYTES came back, and that is a property of the text.

    IT EXISTS BECAUSE THE ALTERNATIVE IS A SLICE BY POSITION, and a slice takes the wrong
    end: this debugger paints its Output log BELOW its Data view, so the screen's last
    2000 characters are the emulator's boot chatter and what is thrown away is the
    memory. MEASURED: `D F000:E000` produces a delta longer than that cap in which the
    row for E000 is present, and the capped reply begins rows later. A tool answering
    `ok` without containing its own answer.

    IT SEARCHES RATHER THAN MATCHING WHOLE LINES, so what comes back is the row and not
    the pane decoration around it. See `DATA_ROW` for why a row is not at the start of
    its line, and for what anchoring there was measured to cost.

    AND IT TAKES EVERY MATCH ON A LINE, NOT THE FIRST. The same repaint mechanism that
    glues a pane header to the row after it glues ROWS to each other, so `.search` --
    which returns one match per line -- silently dropped every row but the first
    whenever two arrived without a newline between them. MEASURED on the pattern: two
    complete rows, gutters and all, parsed to ONE, and asking for the second address
    then produced an INVALID whose text asserted "that is a reading of somewhere else"
    about a row sitting in the string it had just parsed.
    """
    return [m.group(0) for raw in text.splitlines()
            for m in DATA_ROW.finditer(raw)]


def input_line(reply: str) -> str | None:
    """What the debugger's input line holds at the LAST prompt of `reply`, its cursor
    dropped: empty for a console ready to take a command, None when no prompt came back."""
    at = reply.rfind(PROMPT)
    if at < 0:
        return None
    return reply[at + len(PROMPT):].strip().removesuffix("_").strip()


def at_pager(reply: str) -> bool:
    """Whether `reply` ends at the pager: its marker under the LAST prompt, so a marker an
    earlier listing left in the Output pane's scrollback is not taken for this one's."""
    at = reply.rfind(PROMPT)
    return at >= 0 and PAGER_MARK in reply[at:]
