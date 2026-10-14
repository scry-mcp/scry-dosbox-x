"""Section M of the live matrix: the code tools (`disassemble`, the instruction a stop carries,
`call_stack`), on the package's two guests, and the program cells D and F call for dos-real16
and the DPMI guest.

The known answers are the guests' own: the code guest's bytes are `code.com` and its routines
`code.sym` (both the assembler's), the probe's names are `probe.sym`. The debugger's code pane is
the control `disassemble` is held to, through the comparison the offline tests use
(`tests/disasm_control.py`), and the pane is never what decides a known answer.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    PKG,
    M,
    boot,
    cells,
    judged,
    must,
    ok,
    refused,
    release_running,
    said,
    server,
)

import dosbox_state as dstate

sys.path.insert(0, str(PKG / "tests"))

import disasm_control as control  # noqa: E402

import dosbox_code as code  # noqa: E402
import dosbox_disasm as disasm  # noqa: E402

CODE_CONF = GUEST / "code.conf"
#: Where DOS loads both guests, and the base their `nm` tables are placed at.
LOAD = "0814"
GUEST_BASE = "8140"
#: The code guest's code, from `start` to its first data label.
CODE_GUEST_CODE = 0x75
#: How many panes a walk takes at most: eleven lines each, far past any routine judged here.
PANE_WALK_MAX = 40
#: How many publics the dos-real16 rule tries before it is a FAIL rather than a search.
DOS_REAL16_PUBLICS_TRIED = 40

M_CELLS = cells(
    ("M the code guest's code decodes on every boundary its listing places",
     "known: nasm's listing of code.asm, the bytes of code.com"),
    ("M the 386 prefixes decode in the code guest's 16-bit segment",
     "known: code.asm's `mov ecx, [ebx*4+dword_v]`, 67h and 66h"),
    ("M FE /7 is a line of its own, unknown, and decoding resumes after it",
     "disassemble docstring: `.byte`, `flow` unknown; known: code.asm after `park`"),
    ("M the code guest's pane agrees with disassemble, FE /7 excepted",
     "REFERENCE.md, Reading and writing: the pane is the control"),
    ("M disassemble(start, 32) on the probe agrees with the pane",
     "REFERENCE.md, Reading and writing: the pane is the control"),
    ("M resolved on the probe: emit and bump at delta 0, cnt at delta 1",
     "disassemble docstring: resolved; known: probe.sym"),
    ("M no resolved without a table", "disassemble docstring: with a symbol table loaded"),
    ("M length 1 on a three-byte instruction is one line of three bytes",
     "disassemble docstring: the listing completes the instruction that straddles the end"),
    ("M lengths 0, -1 and 1025 are refused", "disassemble docstring: 1..1024"),
    ("M a 16-bit range past FFFF is refused naming the bytes that fit",
     "disassemble docstring: past the end of a 16-bit segment"),
    ("M perform runs disassemble as a step", "REFERENCE.md, Sequences in one call"),
    ("M the first int 3's stop carries its instruction off the pane, as disassemble reads it",
     "REFERENCE.md, What a stop returns: `instruction`; known: code.asm's first int 3"),
    ("M the int 3 in inner names inner and its delta",
     "REFERENCE.md, What a stop returns: the nearest symbol; known: code.sym"),
    ("M after a C elsewhere, the next stop's instruction is still the park's jmp",
     "REFERENCE.md, What a stop returns: the pane or one `D`; known: code.asm's `park`"),
    ("M call_stack at the frameless int 3 lists the stop alone and why",
     "call_stack docstring; known: code.asm's first int 3, BP zeroed"),
    ("M call_stack at middle's first byte reads outer off SP, via entry",
     "call_stack docstring: entry; known: code.asm's far call into middle"),
    ("M call_stack at inner's int 3 lists inner, middle, outer and the main line, the E9 log's "
     "entries reversed", "call_stack docstring; known: code.asm's frames and its E9 lines"),
    ("M call_stack's far row is in the far pointer's segment and its call is the far one",
     "call_stack docstring: near or far as the call says; known: code.asm's `call far`"),
    ("M perform runs disassemble and call_stack as steps", "REFERENCE.md, Sequences in one call"),
    ("M call_stack on a running guest is refused", "call_stack docstring: needs it stopped"),
    ("M call_stack with no session is refused", "every tool: no_session"),
    ("M disassemble on a running guest is refused", "disassemble docstring: needs it stopped"),
    ("M disassemble with no session is refused", "every tool: no_session"),
)

#: The program cells, declared in their sections.
DOS_REAL16_CODE_CELLS = (
    ("D the first routine calling another public, disassembled, agrees with the pane",
     "REFERENCE.md, Reading and writing: the pane is the control"),
    ("D its call carries the callee's name, the pane calling the same offset",
     "disassemble docstring: resolved; the pane is the control"),
)
DPMI_CODE_CELLS = (
    ("F disassemble(_tick, 64) agrees with the pane in Pr32, 32-bit operands among it",
     "REFERENCE.md, Reading and writing: the width is CS's D bit, the pane the control"),
    ("F disassemble just below offset FFFF completes the line that straddles it, as one `D` reads",
     "REFERENCE.md, Reading and writing: past FFFF in a 32-bit segment the read-ahead is a `D`"),
)


def _bytes_of(lines: list[str]) -> bytes:
    return b"".join(bytes.fromhex(line.split()[1]) for line in lines)


def walk_pane(segment: int, start: int, end: int) -> list[code.PaneLine]:
    """The pane after `C`, at `start` and then at the last line each pane showed, until a pane
    reaches `end`; every line of the segment, each address once."""
    seen: dict[int, code.PaneLine] = {}
    at = start
    for _ in range(PANE_WALK_MAX):
        r = must(M.call(server.debug, command=f"C {segment:04X}:{at:08X}"), "moving the pane")
        mine = [p for p in code.pane_lines(str(r.get("screen_delta")))
                if p.segment == f"{segment:04X}"]
        for p in mine:
            seen.setdefault(p.offset, p)
        later = [p.offset for p in mine if p.offset > at]
        if not later or max(later) >= end:
            break
        at = max(later)
    return [seen[o] for o in sorted(seen)]


def against_the_pane(reply: dict[str, Any], names: dict[str, int]) -> control.Verdict:
    """`disassemble`'s listing, as the reply wrote it, against the pane walked over the same
    bytes; a line of the reply the walk never showed is a disagreement, so a short walk cannot
    pass for a whole one."""
    seg, off, length = int(reply["segment"]), int(reply["offset"]), int(reply["length"])
    said_lines = [_said(line, flow) for line, flow in
                  zip(reply.get("lines") or [], reply.get("flow") or [], strict=False)]
    pane = walk_pane(seg, off, off + length)
    verdict = control.compare(pane, f"{seg:04X}", said_lines, names)
    shown = {p.offset for p in pane}
    # A line the pane got wrong covers its own bytes, where the decoder's lines are not compared.
    shown |= {o for p in pane if p.data and any(e.opcode(p.data) for e in control.EXCEPTIONS)
              for o in range(p.offset, p.offset + len(p.data))}
    verdict.disagreements += [f"{seg:04X}:{i.offset:08X}: not in the pane walked"
                              for i in said_lines if i.offset not in shown]
    return verdict


def _said(line: str, flow: str) -> disasm.Insn:
    """One line of the reply read back into the decoder's record: its address, its bytes, its
    text and its flow, so the comparison judges what the reply said and not a second decoding."""
    where, raw, *rest = line.split(None, 2)
    mnemonic, _, operands = (rest[0] if rest else "").partition(" ")
    return disasm.Insn(int(where.split(":")[1], 16), bytes.fromhex(raw), mnemonic, operands,
                       flow)


@M.section("M", "the code tools on the package's guests", M_CELLS)
def section_m() -> None:
    _code_guest()
    _probe()


def _code_guest() -> None:
    boot(conf=CODE_CONF, break_on_int3=True)
    M.setup()
    first = must(M.call(server.resume, until_close=True, seconds=30), "the first int 3")
    _first_stop(first)
    flat = M.call(server.call_stack)
    M.judge("M call_stack at the frameless int 3 lists the stop alone and why",
            ok(flat) and flat.get("heuristic") is True and len(flat.get("calls") or []) == 1
            and "frame pointer is zero" in str(flat.get("ended_why")), said(flat))
    r = M.call(server.disassemble, ref=f"{LOAD}:0100", length=CODE_GUEST_CODE)
    com = (GUEST / "code.com").read_bytes()
    listed = _bytes_of(list(r.get("lines") or []))
    starts = {int(line.split()[0].split(":")[1], 16) for line in r.get("lines") or []}
    placed = _listing_boundaries()
    if placed is None:
        M.block("M the code guest's code decodes on every boundary its listing places",
                "no `nasm` on PATH to list code.asm")
    else:
        M.judge("M the code guest's code decodes on every boundary its listing places",
                ok(r) and listed.startswith(com[:CODE_GUEST_CODE]) and len(placed) > 20
                and placed <= starts,
                f"{len(placed)} boundaries, missing {sorted(hex(a) for a in placed - starts)}")
    lines = list(r.get("lines") or [])
    by_at = {int(ln.split()[0].split(":")[1], 16): ln for ln in lines}
    M.judge("M the 386 prefixes decode in the code guest's 16-bit segment",
            ok(r) and r.get("code_bits") == 16 and by_at.get(0x122, "").split()[1]
            == "67668B0C9D79010000" and by_at.get(0x122, "").endswith(
                "mov ecx, dword ptr [ebx*4 + 0x179]"), by_at.get(0x122, said(r)))
    flows = dict(zip([int(ln.split()[0].split(":")[1], 16) for ln in lines],
                     r.get("flow") or [], strict=False))
    M.judge("M FE /7 is a line of its own, unknown, and decoding resumes after it",
            by_at.get(0x13C, "").endswith(".byte 0xfe") and flows.get(0x13C) == "unknown"
            and by_at.get(0x13D, "").endswith("clc"), f"{by_at.get(0x13C)} / {by_at.get(0x13D)}")
    v = against_the_pane(r, {}) if ok(r) else control.Verdict(0, [said(r)], [])
    M.judge("M the code guest's pane agrees with disassemble, FE /7 excepted",
            v.compared > 0 and not v.disagreements and v.excepted == ["0814:0000013C"],
            f"{v.compared} compared, excepted {v.excepted}, {v.disagreements[:2]}")
    must(M.call(server.symbols_load, source=str(GUEST / "code.sym"), base=GUEST_BASE),
         "loading code.sym")
    must(M.call(server.breakpoint_at, ref="middle"), "arming middle")
    must(M.call(server.resume, seconds=30), "running to middle")
    entry = M.call(server.call_stack)
    rows = [(c.get("symbol"), c.get("via")) for c in entry.get("calls") or []]
    M.judge("M call_stack at middle's first byte reads outer off SP, via entry",
            ok(entry) and rows[:2] == [("middle", "stop"), ("outer", "entry")], str(rows))
    must(M.call(server.breakpoint_clear), "clearing middle")
    inner = M.call(server.resume, until_close=True, seconds=30)
    _inner_stack()
    pic = inner.get("instruction") or {}
    M.judge("M the int 3 in inner names inner and its delta",
            ok(inner) and pic.get("at") == "0814:00000167" and pic.get("text") == "int 3"
            and (pic.get("symbol"), pic.get("delta")) == ("inner", 0x167 - 0x15E), str(pic))
    must(M.call(server.debug, command="C 0000:0000"), "moving the pane away")
    parked = M.call(server.run_for, frames=1)
    pic = parked.get("instruction") or {}
    at = parked.get("stopped_at") or {}
    M.judge("M after a C elsewhere, the next stop's instruction is still the park's jmp",
            ok(parked) and pic.get("at") == f"{at.get('cs')}:{at.get('eip')}" == "0814:0000013A"
            and pic.get("bytes") == "EBFE" and pic.get("symbol") == "park",
            f"{pic.get('at')} {pic.get('bytes')} {pic.get('bytes_from')} {pic.get('symbol')}")
    must(M.call(server.close), "closing the code guest")


def _inner_stack() -> None:
    walked = M.call(server.call_stack)
    calls = walked.get("calls") or []
    entered = [ln.rsplit(" ", 1)[-1] for ln in
               M.call(server.log, pattern="CODE . enter", channel="guest").get("lines") or []]
    names = [c.get("symbol") for c in calls]
    M.judge("M call_stack at inner's int 3 lists inner, middle, outer and the main line, the "
            "E9 log's entries reversed",
            ok(walked) and names[:3] == ["inner", "middle", "outer"] == entered[::-1]
            and len(calls) == 4 and names[3] == "known",
            f"{names}; E9 entered {entered}; {walked.get('ended_why')}")
    far = calls[2] if len(calls) > 2 else {}
    M.judge("M call_stack's far row is in the far pointer's segment and its call is the far one",
            str(far.get("addr", "")).startswith(f"{LOAD}:")
            and str(far.get("call", "")).startswith("lcall"), str(far))
    seq = M.call(server.perform, steps=[{"op": "disassemble", "ref": "inner", "length": 8},
                                        {"op": "call_stack"}])
    judged("M perform runs disassemble and call_stack as steps", reply=seq,
           holds=ok(seq) and seq.get("completed") == 2)


def _first_stop(stop: dict[str, Any]) -> None:
    pic = stop.get("instruction") or {}
    at = stop.get("stopped_at") or {}
    one = M.call(server.disassemble, ref=str(pic.get("at", f"{LOAD}:0102")), length=1)
    M.judge("M the first int 3's stop carries its instruction off the pane, as disassemble "
            "reads it", ok(stop) and pic.get("at") == f"{at.get('cs')}:{at.get('eip')}"
            and pic.get("bytes_from") == "code pane"
            and [ln.split(None, 2)[-1] for ln in one.get("lines") or []] == [pic.get("text")],
            f"{pic} / {one.get('lines')}")


def _listing_boundaries() -> set[int] | None:
    if shutil.which("nasm") is None:
        return None
    with tempfile.TemporaryDirectory(prefix="matrix-code-") as scratch:
        listing = Path(scratch) / "code.lst"
        subprocess.run(["nasm", "-f", "bin", "-l", str(listing), str(GUEST / "code.asm"),
                        "-o", str(Path(scratch) / "code.com")], check=True, timeout=60)
        rows = listing.read_text(encoding="latin-1").splitlines()
    out = set()
    for row in rows:
        cols = row.split()
        if len(cols) >= 3 and len(cols[1]) == 8:
            try:
                at = int(cols[1], 16)
            except ValueError:
                continue
            if at < CODE_GUEST_CODE and not cols[2].startswith("["):
                out.add(0x100 + at)
    return out


def _probe() -> None:
    boot()
    M.setup()
    must(M.call(server.run_for, frames=1), "a retrace into the probe's settle loop")
    bare = M.call(server.disassemble, ref=f"{LOAD}:010B", length=32)
    judged("M no resolved without a table", reply=bare, holds=ok(bare) and "resolved" not in bare)
    must(M.call(server.symbols_load, source=str(GUEST / "probe.sym"), base=GUEST_BASE),
         "loading probe.sym")
    r = M.call(server.disassemble, ref="start", length=32)
    v = against_the_pane(r, {}) if ok(r) else control.Verdict(0, [said(r)], [])
    M.judge("M disassemble(start, 32) on the probe agrees with the pane",
            v.compared > 0 and not v.disagreements and not v.excepted,
            f"{v.compared} compared, {v.disagreements[:2]}")
    named = {(row.get("line"), row.get("kind")): (row.get("symbol"), row.get("delta"))
             for row in r.get("resolved") or []}
    M.judge("M resolved on the probe: emit and bump at delta 0, cnt at delta 1",
            named.get((1, "target")) == ("emit", 0) and named.get((2, "target")) == ("bump", 0)
            and named.get((3, "memory")) == ("cnt", 1), str(named)[:160])
    one = M.call(server.disassemble, ref="start", length=1)
    M.judge("M length 1 on a three-byte instruction is one line of three bytes",
            ok(one) and [ln.split()[1] for ln in one.get("lines") or []] == ["BE5601"],
            str(one.get("lines")))
    bad = [M.call(server.disassemble, ref="start", length=n) for n in (0, -1, 1025)]
    M.judge("M lengths 0, -1 and 1025 are refused",
            all(refused(b, "bad_argument") for b in bad), "; ".join(said(b, 50) for b in bad))
    past = M.call(server.disassemble, ref=f"{LOAD}:FFF8", length=16)
    judged("M a 16-bit range past FFFF is refused naming the bytes that fit", reply=past,
           holds=refused(past, "bad_argument") and "at most 8 bytes" in str(past.get("message")))
    seq = M.call(server.perform, steps=[{"op": "disassemble", "ref": "emit", "length": 8}])
    judged("M perform runs disassemble as a step", reply=seq,
           holds=ok(seq) and seq.get("completed") == 1)
    release_running()
    M.setup()
    run = M.call(server.disassemble, ref="start", length=8)
    judged("M disassemble on a running guest is refused", reply=run,
           holds=refused(run, "not_stopped"))
    run = M.call(server.call_stack)
    judged("M call_stack on a running guest is refused", reply=run,
           holds=refused(run, "not_stopped"))
    must(M.call(server.close), "closing the probe")
    gone = M.call(server.disassemble, ref="start", length=8)
    judged("M disassemble with no session is refused", reply=gone,
           holds=refused(gone, "no_session"))
    gone = M.call(server.call_stack)
    judged("M call_stack with no session is refused", reply=gone,
           holds=refused(gone, "no_session"))


# -------------------------------------------------------------------- the program cells

def _debugger_names() -> dict[str, int]:
    """The names the pane prints in an operand, to the offset they stand for in a flat table
    (code and data share one base, so a symbol's offset is the operand's): the debugger keeps
    fifteen characters of a name, so a shortened name two symbols share stands for neither."""
    out: dict[str, int] = {}
    clash: set[str] = set()
    for s in dstate.STATE.table:
        short = s.name[:15]
        if short in out:
            clash.add(short)
        out[short] = s.offset
    return {k: v for k, v in out.items() if k not in clash}


def dos_real16_code() -> None:
    """The first public, by address, whose code up to the next public (at most 1024 bytes) holds
    a direct call to another public; disassembled and held to the pane."""
    labels = [c[0] for c in DOS_REAL16_CODE_CELLS]
    table = sorted(dstate.STATE.table, key=lambda s: s.offset)
    publics = {s.name for s in table}
    chosen: tuple[str, dict[str, Any], dict[str, Any]] | None = None
    for this, after in list(zip(table, table[1:], strict=False))[:DOS_REAL16_PUBLICS_TRIED]:
        length = min(after.offset - this.offset, code.LENGTH_MAX)
        if length <= 0:
            continue
        r = M.call(server.disassemble, ref=this.name, length=length)
        calls = [row for row in r.get("resolved") or []
                 if row.get("kind") == "target" and row.get("delta") == 0
                 and row.get("symbol") in publics - {this.name}
                 and (r.get("flow") or [])[int(row["line"])] == "call"]
        if ok(r) and calls:
            chosen = (this.name, r, calls[0])
            break
    if chosen is None:
        for label in labels:
            M.judge(label, False,
                    f"no public of the first {DOS_REAL16_PUBLICS_TRIED} calls another")
        return
    name, r, call = chosen
    v = against_the_pane(r, {})
    M.judge(labels[0], v.compared > 0 and not v.disagreements,
            f"{name} at {r['segment']:04X}:{r['offset']:04X}, {v.compared} compared, "
            f"{v.disagreements[:2]}")
    at = int(r["lines"][int(call["line"])].split()[0].split(":")[1], 16)
    pane = [p for p in walk_pane(int(r["segment"]), at, at + 1) if p.offset == at]
    shown = {int(n, 16) for n in re.findall(r"[0-9A-F]+", pane[0].text)} if pane else set()
    calls_there = bool(pane) and pane[0].text.startswith("call") \
        and int(call["offset"], 16) in shown
    M.judge(labels[1], calls_there, f"{name} line {call['line']} calls {call['symbol']}; the "
            f"pane there: {pane[0].text if pane else 'not shown'}")


def dpmi_code() -> None:
    """`_tick` decoded from the stop in the client, against the pane in `Pr32`."""
    r = M.call(server.disassemble, ref="_tick", length=64)
    v = against_the_pane(r, _debugger_names()) if ok(r) else control.Verdict(
        0, [said(r)], [])
    wide = [ln for ln in r.get("lines") or [] if any(
        w in ln.split(None, 2)[-1] for w in ("eax", "ebp", "esp", "dword"))]
    M.judge(DPMI_CODE_CELLS[0][0], ok(r) and r.get("code_bits") == 32 and v.compared > 0
            and not v.disagreements and bool(wide),
            f"{r.get('code_bits_from')}, {v.compared} compared, {v.disagreements[:2]}, "
            f"{len(wide)} lines with a 32-bit operand")
    # The code segment runs on past 64 KiB, so a listing ending just below FFFF has a last line
    # that straddles it: its bytes are held against one data-view read of the same span.
    seg = r.get("segment")
    near = M.call(server.disassemble, ref=f"{seg:04X}:0000FFF0", length=16) \
        if isinstance(seg, int) else {}
    got = _bytes_of(near.get("lines") or []) if ok(near) else b""
    session = dstate.STATE.session
    seen = session.read_bytes(seg, 0xFFF0, len(got)) \
        if got and isinstance(seg, int) and session is not None else b""
    M.judge(DPMI_CODE_CELLS[1][0], ok(near) and "unknown" not in (near.get("flow") or [])
            and len(got) > 0x10 and got == seen,
            f"{(near.get('lines') or [said(near)])[-1:]}, {len(got)} bytes, "
            f"{'equal' if got == seen else 'differ from'} the data view's")
