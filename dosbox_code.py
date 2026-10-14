"""Code at an address, read off the machine and decoded on the host: `disassemble` and the
operands it can name, and the instruction every stop reply carries.

The bytes come by `memdump`'s route (`dosbox_dump.dump_range`) into a scratch directory of the
call's own, so every refusal and every window that route has applies unchanged, and `length`
plus the longest instruction is read so the last line completes. The width they are decoded in
is the D bit of the segment the address is in, as the code pane's own decoder takes it:
real mode is 16-bit; in protected mode the register pane's `Pr32`/`Pr16` is CS's D bit, `SELINFO`
prints it for a selector another segment register holds, and the descriptor listings carry it
for one no register holds. Taking it from the stop's mode alone would decode a 16-bit DPMI
stub as 32-bit code while the machine sits in the client.

A 16-bit segment ends at offset 0xFFFF and the CPU wraps IP inside it, so a listing that would
run past the end is refused rather than read on into memory the code never reaches.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import dosbox_disasm as disasm
import dosbox_dump as dumping
import dosbox_machine as machine
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_symbols as sym
from dosbox_state import STATE

#: The most bytes one `disassemble` lists: a routine at a time, a listing a reply can carry whole.
LENGTH_MAX = 1024
#: Where a 16-bit segment ends: an offset past it wraps to the segment's start.
SEGMENT_END_16 = 0x10000
#: A selector whose index is 0: the null selector, which addresses nothing.
NULL_SELECTOR_MAX = 3


def check_length(length: object) -> None:
    """`length`, a whole number of bytes, 1 to `LENGTH_MAX`."""
    if isinstance(length, bool) or not isinstance(length, int) \
            or not 1 <= length <= LENGTH_MAX:
        raise ds.Invalid("bad_argument",
            f"length={length!r} is not a whole number of bytes from 1 to {LENGTH_MAX}")


# ------------------------------------------------------------------------ the code pane

class PaneLine(NamedTuple):
    """One line of the debugger's code pane: where, the bytes when it printed all of them
    (None when it cut them with `..` or could not read one, `pf` or `na`), and its text."""
    segment: str
    offset: int
    data: bytes | None
    text: str


_PANE_HEADER = re.compile(r"Code Overview(?:o+)")
_PANE_END = re.compile(r"o{4}(?:Output|Variable)")
_PANE_LINE = re.compile(
    r"^([0-9A-F]{4}):([0-9A-F]{8}) ((?:[0-9A-F]{2}|pf|na)*)(\.\.)?\s*(.*?)\s*$")


def pane_lines(screen: str) -> list[PaneLine]:
    """The code pane's lines, off the last pane the screen painted: a delta carries every
    repaint of the command, and an earlier one may be a partial update whose cells, with the
    cursor moves gone, run several lines together. The pane's first line follows its header's
    rule with no line break."""
    blocks = list(_PANE_HEADER.finditer(screen))
    if not blocks:
        return []
    rest = screen[blocks[-1].end():]
    end = _PANE_END.search(rest)
    out: list[PaneLine] = []
    for raw in (rest[:end.start()] if end else rest).splitlines():
        m = _PANE_LINE.match(raw)
        if m is None:
            continue
        pairs, cut = m.group(3), m.group(4)
        whole = not cut and "pf" not in pairs and "na" not in pairs and bool(pairs)
        out.append(PaneLine(m.group(1), int(m.group(2), 16),
                            bytes.fromhex(pairs) if whole else None, m.group(5)))
    return out


# ------------------------------------------------------------------- the stop's segments

class Segments:
    """The segments of the machine at a stop, each fact asked of it once: a segment's width and
    base, from the register pane, `SELINFO`, or the descriptor listings, whichever answers
    first without a round trip it has not already paid."""

    def __init__(self, session: ds.Session, where: dict[str, str],
                 registers: dict[str, str]) -> None:
        self.session = session
        self.registers = registers
        self.mode = where["mode"]
        self.real = self.mode == ds.REAL_MODE
        self._selinfo: dict[str, dict[str, int]] = {}
        self._reading: machine.Reading | None = None

    def holder(self, sel: int) -> str | None:
        """The segment register holding `sel` at this stop, CS first."""
        return next((r for r in ds.SELINFO_REGS
                     if r in self.registers and int(self.registers[r], 16) == sel), None)

    def selinfo(self, reg: str) -> dict[str, int]:
        if reg not in self._selinfo:
            self._selinfo[reg] = self.session.selector(reg)
        return self._selinfo[reg]

    def found(self) -> dict[str, Any]:
        """The GDT and LDT listings, read once, off the session's logfile."""
        if self._reading is None:
            if self.session.launch.logfile is None:
                raise ds.Invalid("no_channel",
                    "the descriptor listings this needs (a range past offset FFFF, or a "
                    "selector no segment register holds) come off the session's logfile: "
                    "`start` with `logfile`")
            self._reading = machine.read(self.session, frozenset({"gdt", "ldt"}))
        return self._reading.found

    def descriptor(self, sel: int) -> dict[str, Any]:
        found, table = self.found(), machine.table_of(sel)
        if table not in found:
            why = [n for n in (self._reading.notes if self._reading else []) if f"`{table}`" in n]
            raise ds.Invalid("unexpected_answer",
                f"`{table}` could not be read at this stop, so {sel:04X}'s descriptor is not "
                f"known: {'; '.join(why) or 'no reason recorded'}")
        row = dumping.addressable(found, sel)
        if row is None:
            raise ds.Invalid("bad_argument",
                f"{sel:04X} names no descriptor in `{table}` at this stop, so its bytes have "
                f"no address: `machine_map` lists the selectors")
        return row

    def _addressed(self, sel: int) -> None:
        if not self.real and sel <= NULL_SELECTOR_MAX:
            raise ds.Invalid("bad_argument",
                f"{sel:04X} is the null selector, which addresses nothing in protected mode")

    def bits(self, sel: int) -> tuple[int, str]:
        """The code size a line in segment `sel` decodes in, and where it was read."""
        if self.real:
            return 16, "real mode"
        self._addressed(sel)
        reg = self.holder(sel)
        if reg == "CS":
            return (32 if self.mode == "Pr32" else 16), f"the pane's {self.mode}"
        if reg is not None and self._reading is None:
            return (32 if self.selinfo(reg)["big"] else 16), f"SELINFO {reg}"
        row = self.descriptor(sel)
        return (32 if row.get("b") else 16), f"the {machine.table_of(sel).upper()} listing"

    def base(self, sel: int) -> int:
        """The linear base of segment `sel`."""
        if self.real:
            return dumping.real_linear(sel, 0)
        self._addressed(sel)
        return self._described(sel, "base")

    def limit(self, sel: int) -> int:
        """The last offset of protected-mode segment `sel`."""
        return self._described(sel, "limit")

    def _described(self, sel: int, field: str) -> int:
        reg = self.holder(sel)
        if reg is not None and self._reading is None:
            return self.selinfo(reg)[field]
        return int(self.descriptor(sel)[field], 16)


def segments_at_stop(session: ds.Session) -> Segments:
    """The stop the machine is in, off one survey; refused before anything is typed when the
    console is not listening."""
    ds.console_listening(session, "a read of its code")
    where, registers = session.where_and_registers()
    return Segments(session, where, registers)


# ------------------------------------------------------------------------ disassemble

def read_code(segs: Segments, seg: int, off: int, length: int, bits: int) -> bytes:
    """`length` bytes from `seg:off` and up to `disasm.INSN_MAX` more, cut at the segment's
    end; a `length` that runs past the end of a 16-bit segment is refused. In protected mode a
    range that runs past offset FFFF is judged against the selector's limit, off the listings;
    the extra bytes alone never make a range cross: the dump stops at FFFF and the few bytes
    past it that complete the last instruction come off one `D`, which needs no listing, and
    never past the selector's limit."""
    want = length + disasm.INSN_MAX
    found: dict[str, Any] | None = None
    past_end = 0
    if bits == 16:
        room = SEGMENT_END_16 - off
        if length > room:
            raise ds.Invalid("bad_argument",
                f"{seg:04X}:{off:04X} is in a 16-bit segment, which ends at offset FFFF: the "
                f"CPU wraps IP to the segment's start there, so the bytes past it are not the "
                f"next instructions. "
                + (f"Ask for at most {room} bytes from there" if room > 0 else
                   "That offset is past the end"))
        want = min(want, room)
    elif not segs.real and off + length > SEGMENT_END_16:
        found = segs.found()
        limit = int(segs.descriptor(seg)["limit"], 16)
        want = max(length, min(want, limit - off + 1))
    elif not segs.real:
        over = max(0, off + want - SEGMENT_END_16)
        want -= over
        if over:
            past_end = min(over, max(0, segs.limit(seg) + 1 - SEGMENT_END_16))
    with tempfile.TemporaryDirectory(prefix="dosbox-disasm-") as scratch:
        dumped = dumping.dump_range(segs.session, seg, off, want, Path(scratch) / "code.bin",
                                    found=found)
        data = dumped.path.read_bytes()
    if past_end:
        data += segs.session.read_bytes(seg, SEGMENT_END_16, past_end, mode=segs.mode)
    return data


def resolve(segs: Segments, seg: int, insns: list[disasm.Insn]) -> list[dict[str, Any]]:
    """Every direct target and direct memory operand of the listing, placed and named: a
    near target in the line's own segment, a far one in the segment it names, a memory
    operand under the segment register it is read through, valued at this stop."""
    span = placement.symbol_span()
    rows: list[dict[str, Any]] = []
    for i, insn in enumerate(insns):
        for t in insn.targets:
            tseg = seg if t.far_segment is None else t.far_segment
            rows.append(_placed(segs, span, {"line": i, "operand": t.operand,
                                              "offset": f"{t.offset:#x}", "kind": "target",
                                              "segment": f"{tseg:04X}"}, tseg, t.offset))
        for m in insn.memory:
            held = segs.registers.get(m.segment_register)
            row = {"line": i, "operand": m.operand, "offset": f"{m.offset:#x}",
                   "kind": "memory", "segment": held, "register": m.segment_register}
            if held is None:
                rows.append({**_named(row, None, span), "why": f"the register pane showed no "
                             f"{m.segment_register}, so the operand has no segment"})
                continue
            rows.append(_placed(segs, span, row, int(held, 16), m.offset))
    return rows


def _named(row: dict[str, Any], linear: int | None,
           span: tuple[int, int] | None) -> dict[str, Any]:
    """A row's `linear`, `symbol` and `delta`: null outside the loaded table's span, where the
    nearest symbol below names memory the table does not describe."""
    near = (placement.nearest_symbol(linear)
            if linear is not None and span is not None and span[0] <= linear <= span[1]
            else None)
    row.update(linear=None if linear is None else f"{linear:08X}",
               symbol=near["name"] if near else None, delta=near["delta"] if near else None)
    return row


def _placed(segs: Segments, span: tuple[int, int] | None, row: dict[str, Any], seg: int,
            offset: int) -> dict[str, Any]:
    try:
        return _named(row, (segs.base(seg) + offset) & 0xFFFFFFFF, span)
    except ds.Invalid as e:
        return {**_named(row, None, span), "why": str(e)}


def disassemble(session: ds.Session, ref: str, length: int) -> dict[str, Any]:
    """`length` bytes from `ref` decoded one instruction a line, the reply `disassemble`
    hands back."""
    segs = segments_at_stop(session)
    seg, off = placement.read_target(ref, "CS", session, machine=(segs.mode, segs.registers))
    bits, bits_from = segs.bits(seg)
    insns = disasm.decode(read_code(segs, seg, off, length, bits), off, bits, length)
    reply: dict[str, Any] = {
        "segment": seg, "offset": off, "length": length, "code_bits": bits,
        "code_bits_from": bits_from, "lines": [i.line(seg) for i in insns],
        "flow": [i.flow for i in insns], "flow_source": disasm.SOURCE}
    if STATE.table:
        reply["resolved"] = resolve(segs, seg, insns)
    return reply


# ------------------------------------------------------------------- the stop's instruction

def stop_instruction(session: ds.Session, where: dict[str, str], registers: dict[str, str],
                     screen: str) -> dict[str, Any]:
    """The instruction a stop is on, for its reply: `instruction` with its bytes, text, flow and
    nearest symbol, or `instruction` null and `instruction_why`. `screen` is that stop's own
    survey.

    The bytes come off the survey the stop already read when they can: the debugger moves its
    code pane to CS:EIP whenever a stop lands outside it, so the pane's line there is on the
    stop's screen, and it is taken when the pane printed all its bytes and they decode as
    exactly one instruction. Otherwise (a `C` left the pane holding the stop's address
    elsewhere, a repaint was cut, or the pane decoded the line in a width that is not the
    segment's, as it does in real mode for a segment number a descriptor answers) one `D` reads
    them off the data view, never past the end of a 16-bit segment."""
    segs = Segments(session, where, registers)
    cs, eip = int(where["cs"], 16), int(where["eip"], 16)
    bits = segs.bits(cs)[0]
    at = f"{where['cs']}:{where['eip']}"
    line = next((p for p in pane_lines(screen)
                 if p.segment == where["cs"] and p.offset == eip and p.data is not None), None)
    insn = disasm.one(line.data, eip, bits) if line is not None and line.data else None
    source = "code pane"
    if insn is None:
        source = "data view"
        n = disasm.INSN_MAX if bits == 32 else min(disasm.INSN_MAX, SEGMENT_END_16 - eip)
        try:
            raw = session.read_bytes(cs, eip, n, mode=segs.mode)
        except ds.Invalid as e:
            return {"instruction": None, "instruction_why": f"no bytes at {at}: {e}"}
        first = disasm.decode(raw, eip, bits)[:1]
        if not first or first[0].flow == disasm.UNKNOWN:
            return _no_instruction(at, raw)
        insn = first[0]
    picture: dict[str, Any] = {"at": at, "bytes": insn.data.hex().upper(), "text": insn.text,
                               "flow": insn.flow, "code_bits": bits, "bytes_from": source}
    return {"instruction": {**picture, **_stop_symbol(segs, cs, eip)}}


def _no_instruction(at: str, data: bytes) -> dict[str, Any]:
    return {"instruction": None, "instruction_why": (
        f"the bytes at {at} ({data[:1].hex().upper()}...) start no instruction")}


def _stop_symbol(segs: Segments, cs: int, eip: int) -> dict[str, Any]:
    """`symbol` and `delta` of the stop's address, null with no table or outside its span; in
    protected mode CS's base costs one `SELINFO CS`, asked only with a table loaded. A table
    that cannot place its symbols names nothing here: the stop is still a stop."""
    try:
        span = placement.symbol_span()
    except sym.BadSymbolText:
        span = None
    if span is None:
        return {"symbol": None, "delta": None}
    try:
        linear: int | None = (segs.base(cs) + eip) & 0xFFFFFFFF
    except ds.Invalid:
        linear = None
    named = _named({}, linear, span)
    return {"symbol": named["symbol"], "delta": named["delta"]}


# ------------------------------------------------------------------------ the call stack

#: How many rows a walk lists before it stops and says `truncated`.
CALL_STACK_MAX = 16
#: The longest and the shortest call instruction a return address is checked against.
CALL_LONGEST, CALL_SHORTEST = 7, 2
#: What one `D` is asked for: the view paints eight rows from the address's own row, so from an
#: address inside a row it promises one row less.
VIEW_READ = ds.DATA_VIEW_BYTES - 16


class _Views:
    """Memory off the data view, each `D` read once and reused while it covers what is asked;
    a read never runs past `end`, the end of a 16-bit segment, and hands back only the bytes
    before it: the view runs on past FFFF painting the segment's first bytes again, which the
    CPU reaches only by wrapping an offset, so the walk wraps its offsets itself."""

    def __init__(self, session: ds.Session, mode: str, end: int) -> None:
        self.session, self.mode, self.end = session, mode, end
        self.views: list[tuple[int, int, bytes]] = []

    def read(self, seg: int, off: int, n: int) -> bytes:
        for vseg, voff, data in self.views:
            if vseg == seg and voff <= off and off + n <= voff + len(data):
                return data[off - voff:off - voff + n]
        data = self.session.read_bytes(seg, off, min(max(n, VIEW_READ), self.end - off),
                                       mode=self.mode)
        self.views.append((seg, off, data))
        return data[:n]


def call_ending_at(views: _Views, seg: int, ret: int, bits: int,
                   far: bool) -> disasm.Insn | None:
    """The call that ends exactly at `seg:ret`, near or far as asked: the longest of two to
    seven bytes before it, and none before the segment's start, that decodes as one call of
    that kind."""
    reach = min(CALL_LONGEST, ret)
    if reach < CALL_SHORTEST:
        return None
    before = views.read(seg, ret - reach, reach)
    for n in range(reach, CALL_SHORTEST - 1, -1):
        got = disasm.one(before[-n:], ret - n, bits)
        if got is not None and got.flow == disasm.CALL \
                and got.mnemonic == ("lcall" if far else "call"):
            return got
    return None


class _Walk:
    """One walk of the frame chain, at the stop the machine is in."""

    def __init__(self, session: ds.Session) -> None:
        self.segs = segments_at_stop(session)
        regs = self.segs.registers
        missing = [r for r in ("SS", "ESP", "EBP") if r not in regs]
        if missing:
            raise ds.Invalid("unexpected_answer",
                f"the register pane showed no {', '.join(missing)} at this stop (a cut "
                f"repaint), so there is no stack to walk: ask again")
        self.cs, self.ss = int(regs["CS"], 16), int(regs["SS"], 16)
        self.bits = self.segs.bits(self.cs)[0]
        self.slot = self.bits // 8
        self.mask = (1 << self.bits) - 1
        self.eip, self.sp, self.bp = (int(regs[r], 16) & self.mask
                                      for r in ("EIP", "ESP", "EBP"))
        self.views = _Views(session, self.segs.mode, self.mask + 1)
        try:
            self.span = placement.symbol_span()
        except sym.BadSymbolText:
            self.span = None
        self.code_seg = self.cs

    def row(self, seg: int, off: int, via: str, call: disasm.Insn | None,
            frame: int | None) -> dict[str, Any]:
        """A row at `seg:off`; for a return address, named by the routine its call is in (a
        call that ends a routine returns to the next one's first byte), `delta` the return's
        distance from that routine."""
        out: dict[str, Any] = {"addr": f"{seg:04X}:{off:08X}", "via": via,
                               "call": None if call is None else call.text,
                               "bp": None if frame is None else f"{frame:0{self.slot * 2}X}"}
        try:
            base = self.segs.base(seg)
        except ds.Invalid:
            return _named(out, None, self.span)
        linear = (base + off) & 0xFFFFFFFF
        if call is None:
            return _named(out, linear, self.span)
        site = _named({}, (base + call.offset) & 0xFFFFFFFF, self.span)
        out.update(linear=f"{linear:08X}", symbol=site["symbol"],
                   delta=None if site["symbol"] is None else
                   site["delta"] + (off - call.offset))
        return out

    def word(self, off: int) -> int:
        return int.from_bytes(self.views.read(self.ss, off, self.slot), "little")

    def returned(self, at: int, frame: int | None, via: str) -> dict[str, Any] | None:
        """The row for the return address at SS:`at`, read as near first and as far second,
        each kept only when a call of that kind ends there; no far reading when its segment's
        slot would lie past the end of the stack segment."""
        ret = self.word(at)
        near = call_ending_at(self.views, self.code_seg, ret, self.bits, far=False)
        if near is not None:
            return self.row(self.code_seg, ret, via, near, frame)
        if at + 2 * self.slot - 1 > self.mask:
            return None
        far_seg = self.word(at + self.slot) & 0xFFFF
        far = call_ending_at(self.views, far_seg, ret, self.bits, far=True)
        if far is None:
            return None
        self.code_seg = far_seg
        return self.row(far_seg, ret, via, far, frame)

    def entry(self, stop: dict[str, Any]) -> int | None:
        """Where the caller's return address is when the stop is outside its routine's frame:
        at SP on `push bp` or `enter` at the routine's own address, one slot up on the
        `mov bp, sp` right after that `push bp` (wrapped as the stack pointer wraps), and at SP
        on the `ret` that leaves it, the frame already undone. One read covers the byte before
        the stop and the instruction."""
        start = max(self.eip - 1, 0)
        code_bytes = self.views.read(self.cs, start, disasm.INSN_MAX + 1)
        first = disasm.decode(code_bytes[self.eip - start:], self.eip, self.bits)[:1]
        opening = first[0].text if first else ""
        table = self.span is not None
        if first and first[0].flow == disasm.RETURN:
            return self.sp
        if opening in ("push bp", "push ebp") or opening.startswith("enter"):
            return self.sp if not table or stop["delta"] == 0 else None
        if opening in ("mov bp, sp", "mov ebp, esp") and self.eip > 0 \
                and code_bytes[:1] == b"\x55":
            up = (self.sp + self.slot) & self.mask
            return up if not table or stop["delta"] == 1 else None
        return None

    def outside(self, row: dict[str, Any]) -> bool:
        return self.span is not None and row["linear"] is not None \
            and not self.span[0] <= int(row["linear"], 16) <= self.span[1]

    def chain(self, calls: list[dict[str, Any]]) -> str:
        """The rows of the frame chain from BP, appended to `calls`; why the walk ended."""
        frame = self.bp
        while len(calls) < CALL_STACK_MAX:
            if frame == 0:
                return "the frame pointer is zero: no frame below this one"
            if frame + 2 * self.slot - 1 > self.mask:
                return f"the frame at SS:{frame:X} runs past the end of the stack segment"
            saved = self.word(frame)
            got = self.returned(frame + self.slot, frame, "bp_chain")
            if got is None:
                return (f"the return address beside the frame at SS:{frame:X} follows no "
                        f"call instruction")
            calls.append(got)
            if self.outside(got):
                return "the return address lies outside the loaded symbol table"
            if saved == 0:
                return "the saved frame pointer is zero: the outermost frame"
            if saved <= frame:
                return f"the saved frame pointer {saved:X} does not rise above {frame:X}"
            frame = saved
        return ""


def call_stack(session: ds.Session) -> dict[str, Any]:
    """The chain of callers of the routine the stop is in, the reply `call_stack` hands back:
    guessed from the frame pointers, a row kept only where its return address follows a real
    call instruction."""
    walk = _Walk(session)
    calls = [walk.row(walk.cs, walk.eip, "stop", None, None)]
    try:
        at = walk.entry(calls[0])
        got = walk.returned(at, None, "entry") if at is not None else None
        if got is not None:
            calls.append(got)
        why = ("the return address lies outside the loaded symbol table"
               if got is not None and walk.outside(got) else walk.chain(calls))
    except ds.Invalid as e:
        why = f"a read failed: {e}"
    return {"heuristic": True, "code_bits": walk.bits, "calls": calls,
            "truncated": not why,
            "ended_why": why or f"{CALL_STACK_MAX} rows, the most one walk lists"}
