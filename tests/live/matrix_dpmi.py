"""Section F of the live matrix: the package's DPMI guest (`tests/guest/dpmi.c`), a DJGPP client
under the host DOSBox-X provides, protected mode, paged, `nm` symbols. Its boot and its way out are
shared with the windowed section and the trace section."""
from __future__ import annotations

import time
from typing import Any

import dpmi_guest as guest
from matrix_code import DPMI_CODE_CELLS, dpmi_code
from matrix_comment_tools import DPMI_COMMENT_CELLS, dpmi_comments
from matrix_common import (
    M,
    boot,
    cells,
    clock_moved,
    dump_to_file,
    free_port,
    hexint,
    judged,
    must,
    ok,
    refused,
    release_running,
    said,
    server,
)
from matrix_programs import (
    NO_STUB,
    carries,
    refused_on_the_dynamic_core,
    stub_cell,
)
from matrix_screen import judge_program, program_cells

#: How many retraces the positions are quoted over.
RETRACES_PLACED = 10
#: The segment of the BIOS handlers a DJGPP guest spends part of every frame in.
BIOS_SEGMENT = "F000"

#: How long the program takes to leave after the confirm, before `close` is asked.
LEAVE_S = 3.0

KEY_CELLS = ("F send_keys a is answered by key_cue_a",
             "F perform runs keys and a log read while it runs",
             "F drive verifies the act from a mark", "F quit by keys: alt+x, right, enter",
             "F close after the guest left")

F_CELLS = cells(
    ("F the program carries its E9 channel", "known: dpmi.c writes `BOOT  . start` first"),
    ("F INT 31h AH=02h stops inside the DPMI client",
     "breakpoint_interrupt's description: 0x31 with ah=2 for DJGPP"),
    ("F the stub announces the serial route", "REFERENCE.md, Input and the screen"),
    ("F screen_view at the client's first stop reads the shell's page through a flat segment",
     "screen_view docstring: protected mode through the GDT or LDT; known: the program is "
     "typed at the prompt, and has not set its own mode yet"),
    ("F screen_wait for the program's command line answers at once, already on screen",
     "screen_wait docstring: already on screen, the machine not moved"),
    ("F symbols_load dpmi.sym measures its base off CS",
     "REFERENCE.md, Names for addresses: a flat map in protected mode"),
    ("F machine_map's LDT holds CS's descriptor at the base symbols_load measured",
     "machine_map docstring; REFERENCE.md, Names for addresses: the base off CS"),
    ("F machine_map's page runs hold _g_ticks's linear address",
     "machine_map docstring: paging runs; known: the u32 tick bumps"),
    ("F INT 08 lies in the CWSDPMI block, through the GDT and the pages",
     "interrupt_vectors docstring; known: the DPMI host owns the protected-mode IDT"),
    ("F memdump through flat 0038 x 0x20000 equals its two 0x10000 halves",
     "memdump docstring: a 32-bit selector within its limit is one command"),
    ("F memdump 0040:FFF0 x 0x20 is refused: a 16-bit segment wraps",
     "memdump docstring: a 16-bit protected segment is refused past offset 0xFFFF"),
    ("F memdump 0020:FFF0 x 0x20 is refused: past the limit reads zeros",
     "memdump docstring: past a selector's limit is refused"),
    ("F breakpoint_at _tick fires", "known: the guest calls tick once a retrace"),
    ("F a show watch on _g_ticks rides the stop", "known: the u32 tick bumps"),
    ("F the _tick stop's instruction names _tick at delta 0, 32-bit",
     "REFERENCE.md, What a stop returns: `instruction`, one SELINFO CS with a table"),
    ("F call_stack at _tick is heuristic, every listed return after a call",
     "call_stack docstring; REFERENCE.md, Reading and writing"),
    *DPMI_CODE_CELLS,
    *DPMI_COMMENT_CELLS,
    ("F trace on the conf's dynamic core is refused naming the core",
     "trace docstring: the count is proved per call"),
    ("F run_for stops ten times, each placed and surveyed",
     "REFERENCE.md, Advancing the machine; the positions quoted, no proportion required"),
    *program_cells("F", "M_LIN8"),
    ("F send_keys a is answered by key_cue_a", "send_keys docstring; known: `key_cue_a=` line"),
    ("F perform runs keys and a log read while it runs", "REFERENCE.md, Sequences in one call"),
    ("F drive verifies the act from a mark", "drive docstring"),
    ("F quit by keys: alt+x, right, enter",
     "known: alt+x asks before it quits, and right then enter answers quit"),
    ("F close after the guest left", "close docstring"),
)


def _names_its_mode(cpu_mode: object) -> bool:
    """A stop's `cpu_mode` as a word, or the unavailable datum with the reason the pane gave."""
    return isinstance(cpu_mode, str) or (
        isinstance(cpu_mode, dict) and cpu_mode.get("available") is False
        and bool(cpu_mode.get("why")))


def _cs_of(reply: dict[str, Any]) -> str:
    """The code segment of a stop reply's `pc`, empty when the reply names no position."""
    pc = reply.get("pc")
    return pc.split(":")[0] if isinstance(pc, str) else ""


def dpmi_boot(**kw: Any) -> None:
    boot(conf=guest.CONF, cwd=guest.GUEST, program=guest.PROGRAM, input_port=free_port(), **kw)


def dpmi_client(wait: float = 30, exempt: str = "",
                **kw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Booted, stopped at the DPMI client's first INT 31h AH=02h, `dpmi.sym` loaded with its
    base measured off CS: the stop's reply and the load's, for the caller to judge."""
    dpmi_boot(**kw)
    M.setup()
    must(M.call(server.breakpoint_interrupt, number=0x31, ah=0x02), "arming INT 31h AH=02h")
    stop = M.call(server.resume, exempt=exempt, seconds=wait)
    return stop, M.call(server.symbols_load, path=str(guest.SYM), base_from="CS")


def dpmi_leave() -> tuple[bool, str, dict[str, Any]]:
    """Leaving as the guest asks: alt+x opens the question, `right` then `enter` answers quit;
    then `close`."""
    first = M.call(server.send_keys, keys=["x"], modifiers=["alt"], expect=guest.ASK_MARK,
                   seconds=15)
    second = M.call(server.send_keys, keys=["right", "enter"], expect=guest.ANSWER_MARK,
                    seconds=15)
    time.sleep(LEAVE_S)
    closed = M.call(server.close)
    return ok(first) and ok(second), f"{said(first, 60)}; {said(second, 60)}", closed


def _machine(client_cs: str, base: object) -> None:
    """The DPMI client's code selector carries the table indicator, so its descriptor is the
    LDT row at `CS` with the privilege level cleared (the listing prints selectors with the
    indicator set), and that row's base is the one `symbols_load` measured; a variable the
    guest keeps lies in exactly one of the page runs, which names its physical page."""
    r = M.call(server.machine_map, sections=["ldt", "paging"])
    selector = f"{(hexint(client_cs) or 0) & 0xFFFC:04X}"
    rows = [d for d in r.get("ldt") or [] if d.get("selector") == selector]
    M.judge("F machine_map's LDT holds CS's descriptor at the base symbols_load measured",
            ok(r) and r.get("cpu_mode") == "paged" and len(rows) == 1
            and hexint(rows[0].get("base")) == hexint(base),
            f"CS {client_cs}: {rows}, symbols_load base {base}; {said(r, 60)}")
    found = M.call(server.symbols_find, name="_g_ticks")
    sym = [s for s in found.get("symbols") or [] if s.get("name") == "_g_ticks"]
    lin = hexint(sym[0].get("addr")) if sym else None
    runs = [p for p in r.get("paging") or [] if lin is not None
            and (hexint(p.get("start")) or 0) <= lin <= (hexint(p.get("end")) or 0)]
    M.judge("F machine_map's page runs hold _g_ticks's linear address",
            ok(r) and len(runs) == 1 and hexint(runs[0].get("phy")) is not None,
            f"_g_ticks {lin if lin is None else hex(lin)}: {runs}")


def _dumps() -> None:
    """CWSDPMI's own GDT as a live read of this stop found it: 0038 a flat 32-bit data segment,
    0040 a 16-bit one based at 400h, 0020 a 32-bit one whose limit is 0xFFFF. The flat one is a
    positive control (a 32-bit segment never wrapped): the same memory in two halves inside its
    limit. The two refusals are what tell the descriptor judgement from no judgement."""
    whole, data = dump_to_file("0038:00000000", 0x20000)
    low, lo = dump_to_file("0038:00000000", 0x10000)
    high, hi = dump_to_file("0038:00010000", 0x10000)
    M.judge("F memdump through flat 0038 x 0x20000 equals its two 0x10000 halves",
            ok(whole) and ok(low) and ok(high) and lo is not None and hi is not None
            and data == lo + hi and lo != hi, f"{said(whole, 60)}; {said(high, 60)}")
    for label, ref, words in (
            ("F memdump 0040:FFF0 x 0x20 is refused: a 16-bit segment wraps", "0040:0000FFF0",
             "16-bit"),
            ("F memdump 0020:FFF0 x 0x20 is refused: past the limit reads zeros", "0020:0000FFF0",
             "limit 0000FFFF")):
        r, got = dump_to_file(ref, 0x20)
        M.judge(label, refused(r, "bad_argument") and words in str(r.get("message"))
                and got is None, said(r))


def _placed_retraces(program_cs: str) -> None:
    """Ten `run_for(frames=1)`, each with its own stop reply, the positions quoted by where they
    fall: the DPMI client's code selector (read at the INT 31h stop), the BIOS handlers, or
    elsewhere (the DPMI host). A retrace lands wherever the cpu is, so no share is required;
    what is required is that every stop was surveyed and names a mode, or says why it cannot:
    a protected-mode pane that paints no PAGE/NOPG mark leaves paging unknown, and no register
    the survey reads (CR0 is not among them) settles it."""
    stops = [M.call(server.run_for, frames=1) for _ in range(RETRACES_PLACED)]
    at = [_cs_of(s) for s in stops]
    program = sum(1 for cs in at if cs == program_cs)
    bios = sum(1 for cs in at if cs == BIOS_SEGMENT)
    M.judge("F run_for stops ten times, each placed and surveyed",
            all(ok(s) and s.get("verdict") == "ELAPSED" and s.get("polls") == 1
                and (clock_moved(s) or 0) > 0 and s.get("regs")
                and _names_its_mode(s.get("cpu_mode"))
                for s in stops),
            f"program {program}, BIOS {bios}, other {len(at) - program - bios}: "
            + " ".join(str(s.get("pc")) for s in stops))


@M.section("F", "the DPMI guest: DJGPP, protected mode, paged, nm symbols", F_CELLS)
def section_f() -> None:
    M.judge("F the program carries its E9 channel", carries(guest.EXE, guest.BOOT_MARK.encode()),
            f"{guest.BOOT_MARK!r} in {guest.EXE.name}")
    r, loaded = dpmi_client()
    client_cs = _cs_of(r)
    judged("F INT 31h AH=02h stops inside the DPMI client", reply=r,
           holds=ok(r) and "stop_seq" in r and r.get("cpu_mode") in ("protected", "paged"))
    stub = stub_cell("F the stub announces the serial route")
    r = M.call(server.screen_view)
    judged("F screen_view at the client's first stop reads the shell's page through a flat "
           "segment", reply=r, holds=ok(r) and guest.PROGRAM in "\n".join(r.get("text") or [])
           and r.get("kind") == "text")
    r = M.call(server.screen_wait, text=guest.PROGRAM, seconds=10)
    judged("F screen_wait for the program's command line answers at once, already on screen",
           reply=r, holds=ok(r) and r.get("already") is True and r.get("polls") == 0
           and guest.PROGRAM in str(r.get("line")))
    judged("F symbols_load dpmi.sym measures its base off CS", reply=loaded,
           holds=ok(loaded) and int(loaded.get("kept") or 0) > 0
           and loaded.get("base") is not None)
    _machine(client_cs, loaded.get("base"))
    _dumps()
    r = M.call(server.interrupt_vectors, number=0x08)
    row = (r.get("vectors") or [{}])[0]
    M.judge("F INT 08 lies in the CWSDPMI block, through the GDT and the pages",
            ok(r) and r.get("cpu_mode") == "paged" and str(row.get("seg_off")).startswith("0018:")
            and (row.get("mcbs") or {}).get("filename") == "CWSDPMI", str(row)[:160])
    must(M.call(server.breakpoint_clear, all=True), "clearing INT 31h")
    b = M.call(server.breakpoint_at, ref="_tick")
    w = M.call(server.watch_add, ref="_g_ticks", mode="show", length=4, fmt="u32")
    r = M.call(server.resume, seconds=30)
    judged("F breakpoint_at _tick fires", reply=r,
           holds=ok(b) and ok(r) and "stop_seq" in r
           and str(r.get("cause")).startswith("breakpoint _tick "))
    pic = r.get("instruction") or {}
    M.judge("F the _tick stop's instruction names _tick at delta 0, 32-bit",
            (pic.get("symbol"), pic.get("delta"), pic.get("code_bits")) == ("_tick", 0, 32),
            str(pic))
    walked = M.call(server.call_stack)
    calls = walked.get("calls") or []
    M.judge("F call_stack at _tick is heuristic, every listed return after a call",
            ok(walked) and walked.get("heuristic") is True and walked.get("code_bits") == 32
            and calls[0].get("symbol") == "_tick" and len(calls) >= 2
            and all(str(c.get("call", "")).startswith(("call", "lcall")) for c in calls[1:]),
            f"{[(c.get('symbol'), c.get('via')) for c in calls]}; {walked.get('ended_why')}")
    watches = r.get("watches") or []
    M.judge("F a show watch on _g_ticks rides the stop",
            ok(w) and any(x.get("ref") == "_g_ticks" and isinstance(x.get("value"), int)
                          for x in watches), str(watches)[:120])
    must(M.call(server.breakpoint_clear, all=True), "clearing _tick")
    dpmi_code()
    dpmi_comments()
    refused_on_the_dynamic_core("F trace on the conf's dynamic core is refused naming the core")
    # AFTER the cells that place a symbol against the stop's CS: ten retraces leave the machine
    # wherever the last one lands, the DPMI host's selector included.
    _placed_retraces(client_cs)
    judge_program("F", "M_LIN8")
    if not stub:
        for label in KEY_CELLS:
            M.block(label, NO_STUB)
        return
    # A stopper on `load_file`, which has run by the first `_tick` stop: one declared that never
    # fires.
    release_running(guest.LOADED_ONCE)
    M.setup()
    r = M.call(server.send_keys, keys=["a"], expect=guest.KEY_MARK, seconds=15)
    judged("F send_keys a is answered by key_cue_a", reply=r,
           holds=ok(r) and (r.get("verify") or {}).get("seen") is True)
    r = M.call(server.perform, steps=[
        {"op": "send_keys", "keys": ["a"], "expect": guest.KEY_MARK, "seconds": 15},
        {"op": "log", "pattern": guest.KEY_MARK, "channel": "guest", "limit": 5}], settle_seconds=0)
    judged("F perform runs keys and a log read while it runs", reply=r,
           holds=ok(r) and r.get("steps_completed") == 2)
    r = M.call(server.drive, act=[{"op": "send_keys", "keys": ["a"]}], expect=guest.KEY_MARK,
               seconds=15, pattern="key")
    judged("F drive verifies the act from a mark", reply=r,
           holds=ok(r) and (r.get("verify") or {}).get("seen") is True
           and bool(((r.get("looked") or {}).get("guest") or {}).get("lines")))
    holds, detail, closed = dpmi_leave()
    M.judge("F quit by keys: alt+x, right, enter", holds, detail)
    judged("F close after the guest left", reply=closed,
           holds=ok(closed) and closed.get("ended_by") in ("quit", "died"))
