"""Section M of the live matrix: the code tools (`disassemble`, the instruction a stop carries,
`call_stack`), on the package's two guests, and the program cells D and F call for dos-real16
and the DPMI guest.

The known answers are the guests' own: the code guest's bytes are `code.com` and its routines
`code.sym` (both the assembler's), the probe's names are `probe.sym`. The bytes a listing shows
are held to the machine's memory as `read_memory` reads it; the decoder itself is held to the
debugger's code pane by the offline tests (`tests/disasm_control.py`), over panes a terminal
session captured, since the debugger channel carries no pane.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    STOPPED,
    M,
    advanced,
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

from scry_dosbox_x import (
    code,  # noqa: E402
    grammar,  # noqa: E402
)
from scry_dosbox_x import state as dstate

CODE_CONF = GUEST / "code.conf"
#: Where DOS loads both guests, and the base their `nm` tables are placed at.
LOAD = "0814"
GUEST_BASE = "0x8140"
#: The code guest's code, from `start` to its first data label.
CODE_GUEST_CODE = 0x75
#: How many publics the dos-real16 rule tries before it is a FAIL rather than a search.
DOS_REAL16_PUBLICS_TRIED = 40

M_CELLS = cells(
    ("M the code guest's code decodes on every boundary its listing places",
     "known: nasm's listing of code.asm, the bytes of code.com"),
    ("M the 386 prefixes decode in the code guest's 16-bit segment",
     "known: code.asm's `mov ecx, [ebx*4+dword_v]`, 67h and 66h"),
    ("M FE /7 is a line of its own, unknown, and decoding resumes after it",
     "disassemble docstring: `.byte`, `flow` unknown; known: code.asm after `park`"),
    ("M the code guest's listing holds the bytes memory holds",
     "disassemble docstring: decoded from memory; known: read_memory over the same span"),
    ("M disassemble(start, 32) on the probe holds the bytes memory holds",
     "disassemble docstring: decoded from memory; known: read_memory over the same span"),
    ("M disassemble holds memory's bytes at 128, 129 and the lengths whose tail reads as a flag",
     "disassemble docstring: 1..1024; known: read_memory over the same span"),
    ("M resolved on the probe: emit and bump at delta 0, cnt at delta 1",
     "disassemble docstring: resolved; known: probe.sym"),
    ("M no resolved without a table", "disassemble docstring: with a symbol table loaded"),
    ("M length 1 on a three-byte instruction is one line of three bytes",
     "disassemble docstring: the listing completes the instruction that straddles the end"),
    ("M lengths 0, -1 and 1025 are refused", "disassemble docstring: 1..1024"),
    ("M a 16-bit range past FFFF is refused naming the bytes that fit",
     "disassemble docstring: past the end of a 16-bit segment"),
    ("M perform runs disassemble as a step", "REFERENCE.md, Sequences in one call"),
    ("M the first int 3's stop carries its instruction from memory, as disassemble reads it",
     "REFERENCE.md, What a stop returns: `instruction`; known: code.asm's first int 3"),
    ("M the int 3 in inner names inner and its delta",
     "REFERENCE.md, What a stop returns: the nearest symbol; known: code.sym"),
    ("M the next stop's instruction is the park's jmp",
     "REFERENCE.md, What a stop returns: read from memory; known: code.asm's `park`"),
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
    ("D the first routine calling another public, disassembled, holds the bytes memory holds",
     "disassemble docstring: decoded from memory; known: memdump over the same span"),
    ("D its call carries the callee's name at delta 0, a `call` the decoder flows as one",
     "disassemble docstring: resolved; known: the program's own map"),
)
DPMI_CODE_CELLS = (
    ("F disassemble(_tick, 64) holds memory's bytes in Pr32, 32-bit operands among it",
     "REFERENCE.md, Reading and writing: the width is CS's D bit; known: read_memory"),
    ("F disassemble just below offset FFFF completes the line that straddles it, as memory "
     "holds it",
     "REFERENCE.md, Reading and writing: past FFFF in a 32-bit segment the bytes go on"),
)


def _bytes_of(lines: list[str]) -> bytes:
    return b"".join(bytes.fromhex(line.split()[1]) for line in lines)


def memory_holds(reply: dict[str, Any]) -> tuple[bool, str]:
    """Whether the listing's bytes are the machine's over the same span, read as many bytes
    at a time as it takes through `read_memory`; with what was compared."""
    lines = list(reply.get("lines") or [])
    listed = _bytes_of(lines)
    if not ok(reply) or not listed:
        return False, said(reply)
    seg_text, off_text = str(reply["seg_off"]).split(":")
    off = int(off_text, 16)
    seen = b""
    while len(seen) < len(listed):
        n = min(grammar.READ_BYTES_MAX, len(listed) - len(seen))
        r = M.call(server.read_memory, ref=f"{seg_text}:{off + len(seen):08X}", length=n)
        if not ok(r):
            return False, f"read_memory at {seg_text}:{off + len(seen):08X}: {said(r)}"
        seen += bytes.fromhex(str(r["hex"]))
    return listed == seen, (f"{len(lines)} lines, {len(listed)} bytes "
                            f"{'equal to' if listed == seen else 'differing from'} memory's")


@M.section("M", "the code tools on the package's guests", M_CELLS)
def section_m() -> None:
    _code_guest()
    _probe()


def _code_guest() -> None:
    boot(conf=CODE_CONF, break_on_int3=True)
    M.setup()
    first = advanced(M.call(server.resume, seconds=30), "the first int 3", STOPPED)
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
    held, why = memory_holds(r)
    M.judge("M the code guest's listing holds the bytes memory holds", held, why)
    must(M.call(server.symbols_load, path=str(GUEST / "code.sym"), base=GUEST_BASE),
         "loading code.sym")
    must(M.call(server.breakpoint_at, ref="middle"), "arming middle")
    advanced(M.call(server.resume, seconds=30), "running to middle", STOPPED)
    entry = M.call(server.call_stack)
    rows = [(c.get("symbol"), c.get("via")) for c in entry.get("calls") or []]
    M.judge("M call_stack at middle's first byte reads outer off SP, via entry",
            ok(entry) and rows[:2] == [("middle", "stop"), ("outer", "entry")], str(rows))
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing middle")
    inner = M.call(server.resume, seconds=30)
    _inner_stack()
    pic = inner.get("instruction") or {}
    M.judge("M the int 3 in inner names inner and its delta",
            ok(inner) and pic.get("address") == "0814:00000167" and pic.get("text") == "int 3"
            and (pic.get("symbol"), pic.get("delta")) == ("inner", 0x167 - 0x15E), str(pic))
    parked = M.call(server.run_for, frames=1)
    pic = parked.get("instruction") or {}
    M.judge("M the next stop's instruction is the park's jmp",
            ok(parked) and parked.get("verdict") == "ELAPSED"
            and pic.get("address") == parked.get("pc") == "0814:0000013A"
            and pic.get("bytes") == "EBFE" and pic.get("symbol") == "park"
            and pic.get("bytes_from") == "memory",
            f"{pic.get('address')} {pic.get('bytes')} {pic.get('bytes_from')} {pic.get('symbol')}")
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
            str(far.get("seg_off", "")).startswith(f"{LOAD}:")
            and str(far.get("call", "")).startswith("lcall"), str(far))
    seq = M.call(server.perform, steps=[{"op": "disassemble", "ref": "inner", "length": 8},
                                        {"op": "call_stack"}])
    judged("M perform runs disassemble and call_stack as steps", reply=seq,
           holds=ok(seq) and seq.get("steps_completed") == 2)


def _first_stop(stop: dict[str, Any]) -> None:
    pic = stop.get("instruction") or {}
    one = M.call(server.disassemble, ref=str(pic.get("address", f"{LOAD}:0102")), length=1)
    M.judge("M the first int 3's stop carries its instruction from memory, as disassemble "
            "reads it", ok(stop) and pic.get("address") == stop.get("pc")
            and pic.get("bytes_from") == "memory"
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
    advanced(M.call(server.run_for, frames=1), "a retrace into the probe's settle loop")
    bare = M.call(server.disassemble, ref=f"{LOAD}:010B", length=32)
    judged("M no resolved without a table", reply=bare, holds=ok(bare) and "resolved" not in bare)
    must(M.call(server.symbols_load, path=str(GUEST / "probe.sym"), base=GUEST_BASE),
         "loading probe.sym")
    r = M.call(server.disassemble, ref="start", length=32)
    held, why = memory_holds(r)
    M.judge("M disassemble(start, 32) on the probe holds the bytes memory holds", held, why)
    # The debugger is asked for length + 15 bytes: 157, 160, 192 and 208 land on 0xAC, 0xAF, 0xCF
    # and 0xDF; 128 and 129 are the sizes either side of the one that always read fine.
    sized = {n: memory_holds(M.call(server.disassemble, ref="start", length=n))
             for n in (128, 129, 157, 160, 192, 208, code.LENGTH_MAX)}
    M.judge("M disassemble holds memory's bytes at 128, 129 and the lengths whose tail reads as "
            "a flag", all(held for held, _ in sized.values()),
            "; ".join(f"{n}: {why}" for n, (held, why) in sized.items() if not held)
            or f"{len(sized)} lengths")
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
           holds=ok(seq) and seq.get("steps_completed") == 1)
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

def dos_real16_code() -> None:
    """The first public, by address, whose code up to the next public (at most 1024 bytes) holds
    a direct call to another public; disassembled and its bytes held to memory's."""
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
                 and isinstance(row.get("symbol"), str)
                 and row["symbol"] in publics - {this.name}
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
    held, why = memory_holds(r)
    M.judge(labels[0], held, f"{name} at {r['seg_off']}: {why}")
    target = next(sym for sym in table if sym.name == call["symbol"])
    base = int(dstate.STATE.base.get("base") or 0)
    linear = int(str(call.get("addr", "0x-1")), 16) if isinstance(call.get("addr"), str) else -1
    M.judge(labels[1], call["delta"] == 0 and linear == base + target.offset
            and (r.get("flow") or [])[int(call["line"])] == "call",
            f"{name} line {call['line']} calls {call['symbol']} at {call['seg_off']} "
            f"({call.get('addr')}; the table places it at {base + target.offset:#010x})")


def dpmi_code() -> None:
    """`_tick` decoded from the stop in the client, its bytes held to memory's in `Pr32`."""
    r = M.call(server.disassemble, ref="_tick", length=64)
    held, why = memory_holds(r)
    wide = [ln for ln in r.get("lines") or [] if any(
        w in ln.split(None, 2)[-1] for w in ("eax", "ebp", "esp", "dword"))]
    M.judge(DPMI_CODE_CELLS[0][0], ok(r) and r.get("code_bits") == 32 and held and bool(wide),
            f"{r.get('code_bits_from')}, {why}, {len(wide)} lines with a 32-bit operand")
    # The code segment runs on past 64 KiB, so a listing ending just below FFFF has a last line
    # that straddles it: its bytes are held against one read of the same span.
    seg = int(str(r["seg_off"]).split(":")[0], 16) if ok(r) else None
    near = M.call(server.disassemble, ref=f"{seg:04X}:0000FFF0", length=16) \
        if seg is not None else {}
    got = _bytes_of(near.get("lines") or []) if ok(near) else b""
    session = dstate.STATE.session
    seen = session.read_bytes(seg, 0xFFF0, len(got)) \
        if got and seg is not None and session is not None else b""
    M.judge(DPMI_CODE_CELLS[1][0], ok(near) and "unknown" not in (near.get("flow") or [])
            and len(got) > 0x10 and got == seen,
            f"{(near.get('lines') or [said(near)])[-1:]}, {len(got)} bytes, "
            f"{'equal to' if got == seen else 'differing from'} memory's")
