"""Code at an address, decoded on the host: `disassemble` and the instruction every stop reply
carries.

The bytes come by `memdump`'s route (`dosbox_dump.dump_range`), so its refusals and windows apply
unchanged; `length` plus the longest instruction is read so the last line completes. The decode
width is the D bit of the segment the address is in, never the stop's mode alone, which would
decode a 16-bit DPMI stub as 32-bit while the machine sits in the client.

A 16-bit segment ends at offset 0xFFFF and the CPU wraps IP inside it, so a listing that would
run past the end is refused.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from scry_core.reply_contract import unavailable

import dosbox_disasm as disasm
import dosbox_dump as dumping
import dosbox_grammar as grammar
import dosbox_machine as machine
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
import dosbox_symbols as sym
from dosbox_state import STATE

#: The most bytes one `disassemble` lists, so a reply carries the listing whole.
LENGTH_MAX = 1024
#: Where a 16-bit segment ends; an offset past it wraps.
SEGMENT_END_16 = 0x10000
#: The null selector's highest value (index 0).
NULL_SELECTOR_MAX = 3


def check_length(length: object) -> None:
    """`length` is a whole number of bytes, 1 to `LENGTH_MAX`."""
    if isinstance(length, bool) or not isinstance(length, int) \
            or not 1 <= length <= LENGTH_MAX:
        raise ds.Invalid("bad_argument",
            f"length={length!r} is not a whole number of bytes from 1 to {LENGTH_MAX}")


class Segments:
    """The segments at a stop: width and base from the stop's own reading, `SELINFO` or the
    descriptor listings, whichever answers without a new round trip."""

    def __init__(self, session: ds.Session, where: dict[str, str],
                 registers: dict[str, str]) -> None:
        self.session = session
        self.registers = registers
        self.mode = where["mode"]
        self.real = grammar.real_segments(self.mode)
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
        """The GDT and LDT listings, read once."""
        if self._reading is None:
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
            return (32 if self.mode == "Pr32" else 16), f"the stop's {self.mode}"
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
    """The stop's segments off one survey; refused before anything is sent unless the machine
    is stopped."""
    session.require_stopped("a read of its code")
    where, registers = session.where_and_registers()
    return Segments(session, where, registers)


def read_code(segs: Segments, seg: int, off: int, length: int, bits: int) -> bytes:
    """`length` bytes from `seg:off` plus up to `disasm.INSN_MAX` more, cut at the segment's end;
    a `length` past the end of a 16-bit segment is refused. In protected mode a range past FFFF
    is judged against the selector's limit off the listings; the extra bytes alone never make
    it cross: the dump stops at FFFF and the few bytes completing the last instruction come from
    one more read, never past the limit."""
    want = length + disasm.INSN_MAX
    found: dict[str, Any] | None = None
    past_end = 0
    if bits == 16:
        room = SEGMENT_END_16 - off
        if length > room:
            raise ds.Invalid("bad_argument",
                f"{grammar.canonical_seg_off(seg, off)} is in a 16-bit segment, which ends at "
                f"offset FFFF: the CPU wraps IP to the segment's start there, so the bytes past it "
                f"are not the next instructions. "
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
    """Every direct target and memory operand of the listing, placed and named; a memory
    operand is read through its segment register's value at this stop."""
    span = placement.symbol_span()
    rows: list[dict[str, Any]] = []
    for i, insn in enumerate(insns):
        for t in insn.targets:
            tseg = seg if t.far_segment is None else t.far_segment
            rows.append(_placed(segs, span, {"line": i, "operand": t.operand, "kind": "target",
                                              "seg_off": st.seg_off(tseg, t.offset)},
                                tseg, t.offset))
        for m in insn.memory:
            held = segs.registers.get(m.segment_register)
            row = {"line": i, "operand": m.operand, "kind": "memory",
                   "register": m.segment_register}
            if held is None:
                gone = f"the stop's registers carry no {m.segment_register}, so the operand has " \
                       f"no segment"
                rows.append(_named({**row, "seg_off": unavailable(gone)}, None, span, gone))
                continue
            row["seg_off"] = st.seg_off(int(held, 16), m.offset)
            rows.append(_placed(segs, span, row, int(held, 16), m.offset))
    return rows


#: Why a place has no symbol; outside the span the nearest symbol below would be misleading.
NO_TABLE_WHY = "no symbol table is loaded"
OUTSIDE_SPAN_WHY = "outside the loaded table's span"


def _named(row: dict[str, Any], linear: int | None, span: tuple[int, int] | None,
           unplaced: str = "its segment's base could not be read") -> dict[str, Any]:
    """A row's `addr`, `symbol` and `delta`, each unavailable with its reason: `unplaced` when
    there is no linear address, else no table or outside its span."""
    if linear is None:
        gone = unavailable(unplaced)
        row.update(addr=gone, symbol=gone, delta=gone)
        return row
    near = (placement.nearest_symbol(linear)
            if span is not None and span[0] <= linear <= span[1] else None)
    why = unavailable(NO_TABLE_WHY if span is None else OUTSIDE_SPAN_WHY)
    row.update(addr=st.flat(linear), symbol=near["name"] if near else why,
               delta=near["delta"] if near else why)
    return row


def _placed(segs: Segments, span: tuple[int, int] | None, row: dict[str, Any], seg: int,
            offset: int) -> dict[str, Any]:
    try:
        return _named(row, (segs.base(seg) + offset) & 0xFFFFFFFF, span)
    except ds.Invalid as e:
        return _named(row, None, span, str(e))


def disassemble(session: ds.Session, ref: str, length: int) -> dict[str, Any]:
    """The `disassemble` reply: `length` bytes from `ref`, one instruction a line."""
    segs = segments_at_stop(session)
    seg, off = placement.read_target(ref, "CS", session, machine=(segs.mode, segs.registers))
    bits, bits_from = segs.bits(seg)
    insns = disasm.decode(read_code(segs, seg, off, length, bits), off, bits, length)
    reply: dict[str, Any] = {
        "seg_off": st.seg_off(seg, off), "length": length, "code_bits": bits,
        "code_bits_from": bits_from, "lines": [i.line(seg) for i in insns],
        "flow": [i.flow for i in insns], "flow_source": disasm.SOURCE}
    if STATE.table:
        reply["resolved"] = resolve(segs, seg, insns)
    return reply


def stop_instruction(session: ds.Session, where: dict[str, str],
                     registers: dict[str, str]) -> dict[str, Any]:
    """The stop's `instruction` for its reply, or unavailable with its `why`: the bytes at CS:EIP
    read from memory, never past the end of a 16-bit segment, decoded as one instruction."""
    segs = Segments(session, where, registers)
    cs, eip = int(where["cs"], 16), int(where["eip"], 16)
    bits = segs.bits(cs)[0]
    at = f"{where['cs']}:{where['eip']}"
    n = disasm.INSN_MAX if bits == 32 else min(disasm.INSN_MAX, SEGMENT_END_16 - eip)
    try:
        raw = session.read_bytes(cs, eip, n, mode=segs.mode)
    except ds.Invalid as e:
        return {"instruction": unavailable(f"no bytes at {at}: {e}")}
    first = disasm.decode(raw, eip, bits)[:1]
    if not first or first[0].flow == disasm.UNKNOWN:
        return _no_instruction(at, raw)
    insn = first[0]
    picture: dict[str, Any] = {"seg_off": at, "bytes": insn.data.hex().upper(),
                               "text": insn.text, "flow": insn.flow, "code_bits": bits,
                               "bytes_from": "memory"}
    return {"instruction": {**picture, **_stop_symbol(segs, cs, eip)}}


def _no_instruction(at: str, data: bytes) -> dict[str, Any]:
    return {"instruction": unavailable(
        f"the bytes at {at} ({data[:1].hex().upper()}...) start no instruction")}


def _stop_symbol(segs: Segments, cs: int, eip: int) -> dict[str, Any]:
    """`symbol` and `delta` of the stop's address; in protected mode CS's base costs one
    `SELINFO CS`, asked only with a table loaded. A table that cannot place its symbols names
    nothing: the stop still stands."""
    try:
        span = placement.symbol_span()
    except sym.BadSymbolText:
        span = None
    if span is None:
        none = unavailable(NO_TABLE_WHY)
        return {"symbol": none, "delta": none}
    try:
        linear: int | None = (segs.base(cs) + eip) & 0xFFFFFFFF
    except ds.Invalid as e:
        linear, unplaced = None, f"CS's base could not be read: {e}"
    else:
        unplaced = ""
    named = _named({}, linear, span, unplaced or "unplaced")
    return {"symbol": named["symbol"], "delta": named["delta"]}


#: Rows a walk lists before it says `truncated`.
CALL_STACK_MAX = 16
#: Longest and shortest call instruction checked against a return address.
CALL_LONGEST, CALL_SHORTEST = 7, 2
#: What one read of the walk takes, reused while it covers the reads after it.
VIEW_READ = grammar.READ_BYTES_MAX


class _Views:
    """Memory read in pieces of `VIEW_READ`, each reused while it covers a read; a read stops at
    `end`, the segment's, so the walk wraps its offsets itself."""

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
    """The longest call, near or far as asked, that ends exactly at `seg:ret`."""
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
    """One walk of the frame chain at the current stop."""

    def __init__(self, session: ds.Session) -> None:
        self.segs = segments_at_stop(session)
        regs = self.segs.registers
        missing = [r for r in ("SS", "ESP", "EBP") if r not in regs]
        if missing:
            raise ds.Invalid("unexpected_answer",
                f"the registers read at this stop carry no {', '.join(missing)}, so there is no "
                f"stack to walk: ask again")
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
        """A row at `seg:off`; a return address is named by the routine its call is in (a call
        ending a routine returns to the next one's first byte), `delta` from that routine."""
        out: dict[str, Any] = {
            "seg_off": st.seg_off(seg, off), "via": via,
            "call": unavailable("the stop itself: no call leads to it") if call is None
            else call.text,
            "bp": unavailable("no frame was read beside it") if frame is None
            else f"{frame:0{self.slot * 2}X}"}
        try:
            base = self.segs.base(seg)
        except ds.Invalid as e:
            return _named(out, None, self.span, f"the segment's base could not be read: {e}")
        linear = (base + off) & 0xFFFFFFFF
        if call is None:
            return _named(out, linear, self.span)
        site = _named({}, (base + call.offset) & 0xFFFFFFFF, self.span)
        out.update(addr=st.flat(linear), symbol=site["symbol"],
                   delta=site["delta"] if isinstance(site["symbol"], dict) else
                   site["delta"] + (off - call.offset))
        return out

    def word(self, off: int) -> int:
        return int.from_bytes(self.views.read(self.ss, off, self.slot), "little")

    def returned(self, at: int, frame: int | None, via: str) -> dict[str, Any] | None:
        """The row for the return address at SS:`at`, read near then far, each kept only when a
        call of that kind ends there."""
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
        """Where the caller's return address is when the stop is outside its routine's frame: at
        SP on `push bp`/`enter` or on `ret`, one slot up on the `mov bp, sp` after `push bp`."""
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
        return self.span is not None and isinstance(row["addr"], str) \
            and not self.span[0] <= int(row["addr"], 16) <= self.span[1]

    def chain(self, calls: list[dict[str, Any]]) -> str:
        """Append the frame chain from BP to `calls`; returns why the walk ended."""
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
    """The `call_stack` reply: callers guessed from frame pointers, a row kept only where its
    return address follows a real call."""
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
