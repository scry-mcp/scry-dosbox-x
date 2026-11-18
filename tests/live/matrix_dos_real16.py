"""Section D of the live matrix: dos-real16, TASM real mode, a Borland map with publics."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import bench_programs as bp
from matrix_code import DOS_REAL16_CODE_CELLS, dos_real16_code
from matrix_comment_tools import DOS_REAL16_COMMENT_CELLS, dos_real16_comments
from matrix_common import (
    STOPPED,
    M,
    advanced,
    boot,
    cells,
    clock_moved,
    exec_of,
    free_port,
    hexint,
    judged,
    must,
    ok,
    read_word,
    said,
    server,
)
from matrix_programs import (
    KEY_NOT_AT_INT9,
    NO_STUB,
    PSP_BYTES,
    carries,
    guarded,
    image_end,
    key_reaches_int9,
    mcb_psp,
    program_stop,
    refused_on_the_dynamic_core,
    segment_start,
    stub_cell,
    sym,
)
from matrix_screen import judge_program, program_cells

D_CELLS = cells(
    ("D the program carries its E9 channel", "known: an `info` build writes `[INF]` lines"),
    ("D the load segment from DOS MCBS", "known: the program's MCB, its PSP + 0x10"),
    ("D symbols_load REAL16.MAP at that base", "REFERENCE.md, Names for addresses: real mode"),
    ("D symbols_find COMPOSE_FRAME", "known: the map's publics carry it"),
    ("D machine_map holds the REAL16 block at the load segment, covering the map's image",
     "machine_map docstring; known: DOS gives the program all free memory"),
    ("D INT 08 and INT 09 lie in the REAL16 block, named NEW_IRQ_VIDEO and NEW_KEY_PC",
     "interrupt_vectors docstring; known: the map's publics, the handlers the game installs"),
    ("D INT 1C lies in the SCRY block", "known: the serial stub hooks the timer tick"),
    ("D trace on the conf's dynamic core is refused naming the core",
     "trace docstring: the count is proved per call"),
    ("D log_wait Entering main loop", "known: the game logs `Entering main loop` at start"),
    ("D breakpoint_at COMPOSE_FRAME fires three frames",
     "known: COMPOSE_FRAME runs every frame; REFERENCE.md, What a stop returns: cause"),
    *DOS_REAL16_CODE_CELLS,
    *DOS_REAL16_COMMENT_CELLS,
    ("D COMPOSE_FRAME hits over ten retraces, quoted",
     "measured, never required to equal the retraces: the game's pace is its own"),
    ("D run_for frames=10 lands ten retraces in the program",
     "REFERENCE.md, Running and stopping: a frame is one retrace"),
    ("D the stub announces the serial route", "REFERENCE.md, Input and the screen"),
    ("D a word scan opened at an odd offset keeps TOTALTIME",
     "REFERENCE.md, Reading and writing; known: the map puts TOTALTIME at an odd offset"),
    ("D Tab through the serial stub reaches the game's INT 9",
     "measured; known: the game owns INT 9 and Tab is its coin key"),
    ("D the coin adds to CREDITOS", "measured; known: the map's CREDITOS"),
    *program_cells("D", "M_LIN15"),
    ("D close", "close docstring"),
)

#: How many retraces the game's own frames are counted over.
RETRACES_QUOTED = 10
#: How many frames the scan waits for TOTALTIME to move before its cell is BLOCKED.
FRAMES_FOR_A_CHANGE = 120


@M.section("D", "dos-real16: real mode, a Borland map with publics", D_CELLS)
def section_d() -> None:
    if why := bp.missing(bp.DOS_REAL16):
        M.block_rest(why)
        return
    exe, mapf = bp.DOS_REAL16.root / bp.DOS_REAL16.exe, bp.DOS_REAL16.root / bp.DOS_REAL16.map
    e9 = carries(exe, bp.DOS_REAL16.e9_line.encode("latin-1"))
    if e9:
        M.judge("D the program carries its E9 channel", True,
                f"{bp.DOS_REAL16.e9_line!r} in {exe.name}")
    else:
        M.block("D the program carries its E9 channel", "prod build, no E9")
    got = dos_real16_main_loop()
    cs, psp, load = got["cs"], got["psp"], got["load"]
    code_paras = segment_start(mapf, "_DATA") >> 4
    M.judge("D the load segment from DOS MCBS", load <= cs < load + code_paras,
            f"PSP {psp:04X}, load {load:04X}, the program's first INT 21h from {cs:04X}, "
            f"its code {code_paras:04X} paragraphs by the map")
    r = got["loaded"]
    judged("D symbols_load REAL16.MAP at that base", reply=r,
           holds=ok(r) and int(r.get("kept") or 0) > 0)
    r = got["found"]
    found = [s for s in r.get("symbols") or [] if s.get("name") == "COMPOSE_FRAME"]
    judged("D symbols_find COMPOSE_FRAME", reply=r, holds=ok(r) and len(found) == 1)
    M.setup()
    guarded("D machine_map holds the REAL16 block at the load segment, covering the map's image",
            lambda: _machine(psp, mapf))
    _vectors()
    refused_on_the_dynamic_core("D trace on the conf's dynamic core is refused naming the core")
    if e9:
        r = M.call(server.log_wait, pattern="Entering main loop", channel="guest", seconds=5)
        judged("D log_wait Entering main loop", reply=r, holds=ok(r))
    else:
        M.block("D log_wait Entering main loop", "prod build, no E9")
    b = M.call(server.breakpoint_at, ref="COMPOSE_FRAME")
    stops = [M.call(server.resume, seconds=30) for _ in range(3)]
    M.judge("D breakpoint_at COMPOSE_FRAME fires three frames",
            ok(b) and b.get("state") == "armed" and all(
                ok(s) and "stop_seq" in s
                and str(s.get("cause")).startswith("breakpoint COMPOSE_FRAME ") for s in stops),
            "; ".join(said(s, 60) for s in stops))
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing COMPOSE_FRAME")
    dos_real16_code()
    dos_real16_comments(mapf, f"0x{load * 16:X}")
    M.setup()
    _retraces(load)
    judge_program("D", "M_LIN15")
    stub = stub_cell("D the stub announces the serial route")
    guarded("D a word scan opened at an odd offset keeps TOTALTIME", _scan)
    if stub:
        _coin()
    else:
        M.block("D Tab through the serial stub reaches the game's INT 9", NO_STUB)
        M.block("D the coin adds to CREDITOS", NO_STUB)
    r = M.call(server.close)
    judged("D close", reply=r, holds=ok(r) and r.get("closed") is True)


def dos_real16_main_loop(wait: float = 30, exempt: str = "", **kw: Any) -> dict[str, Any]:
    """Boot, load the map at the program's segment, stop at ATRCT_RUN; return replies and segments.

    COMPOSE_FRAME also runs during start-up, so only ATRCT_RUN proves the main loop was entered.
    """
    mapf = bp.DOS_REAL16.root / bp.DOS_REAL16.map
    boot(conf=bp.session_conf(bp.DOS_REAL16, Path(M.fresh("-conf"))), cwd=bp.DOS_REAL16.root,
         program=bp.DOS_REAL16.launch, input_port=free_port(), **kw)
    exec_of(bp.DOS_REAL16.process)
    cs = program_stop()
    psp = mcb_psp(bp.DOS_REAL16.process)
    load = psp + 0x10
    loaded = M.call(server.symbols_load, path=str(mapf), base=f"0x{load * 16:X}")
    found = M.call(server.symbols_find, name="COMPOSE_FRAME")
    must(M.call(server.breakpoint_at, ref="ATRCT_RUN"), "arming ATRCT_RUN")
    must(M.call(server.resume, exempt=exempt, seconds=wait), "running to ATRCT_RUN")
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing ATRCT_RUN")
    return {"cs": cs, "psp": psp, "load": load, "loaded": loaded, "found": found}


def _machine(psp: int, mapf: Path) -> tuple[bool, str]:
    """The program's MCB covers its PSP and the map's image; DOS gave it all free memory."""
    r = M.call(server.machine_map)
    rows = [b for b in r.get("mcbs") or [] if b.get("filename") == bp.DOS_REAL16.process
            and hexint(b.get("psp_seg")) == psp and hexint(b.get("mcb_seg")) == psp - 1]
    need = PSP_BYTES + image_end(mapf)
    return (ok(r) and len(rows) == 1 and int(rows[0]["size_bytes"]) >= need,
            f"{rows} against {need} bytes; {said(r, 60)}")


def _vectors() -> None:
    """The game hooks INT 08/09 with mapped handlers; the serial stub hooks the timer tick."""
    r = M.call(server.interrupt_vectors)
    rows = {int(v["number"], 16): v for v in r.get("vectors") or []}
    hooked = [(rows.get(n, {}).get("mcbs") or {}).get("filename") for n in (0x08, 0x09)]
    named = [((rows.get(n, {}).get("symbol") or {}).get("name"),
              (rows.get(n, {}).get("symbol") or {}).get("delta")) for n in (0x08, 0x09)]
    M.judge("D INT 08 and INT 09 lie in the REAL16 block, named NEW_IRQ_VIDEO and NEW_KEY_PC",
            ok(r) and hooked == [bp.DOS_REAL16.process] * 2
            and named == [("NEW_IRQ_VIDEO", 0), ("NEW_KEY_PC", 0)], f"{hooked} {named}")
    tick = (rows.get(0x1C, {}).get("mcbs") or {}).get("filename")
    M.judge("D INT 1C lies in the SCRY block", ok(r) and tick == "SCRY",
            f"INT 1C {rows.get(0x1C, {}).get('seg_off')} in {tick}")


def _retraces(load: int) -> None:
    """Count COMPOSE_FRAME hits over ten retraces, then run ten retraces unarmed.

    An `OTHER_STOP` frame leaves its retrace pending, so both outcomes are counted. The hits are
    quoted, never required to equal ten: the game paces itself. The breakpoint is armed before
    any retrace run because on a dynamic core a later one can fail to cut a frame.
    """
    must(M.call(server.breakpoint_at, ref="COMPOSE_FRAME"), "arming COMPOSE_FRAME")
    retraces = hits = calls = 0
    replies: list[dict[str, Any]] = []
    while retraces < RETRACES_QUOTED and calls < 4 * RETRACES_QUOTED:
        r = M.call(server.run_for, frames=1)
        replies.append(r)
        calls += 1
        if r.get("verdict") == "OTHER_STOP" \
                and str(r.get("cause")).startswith("breakpoint COMPOSE_FRAME "):
            hits += 1
        elif r.get("verdict") == "ELAPSED":
            retraces += 1
        else:
            break
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing COMPOSE_FRAME")
    M.judge("D COMPOSE_FRAME hits over ten retraces, quoted",
            retraces == RETRACES_QUOTED and all(ok(x) for x in replies),
            f"COMPOSE_FRAME {hits} times over {retraces} retraces ({calls} calls)")
    r = M.call(server.run_for, frames=10)
    moved = clock_moved(r)
    judged("D run_for frames=10 lands ten retraces in the program", reply=r,
           holds=ok(r) and r.get("verdict") == "ELAPSED" and r.get("polls") == 10
           and moved is not None and moved > 0
           and (hexint(str(r.get("pc")).split(":")[0]) or 0) >= load)


def _scan() -> tuple[bool, str]:
    """Cheat-search loop: word scan on TOTALTIME's odd offset, `=`, `!`, `=`.

    COMPOSE_FRAME is a code breakpoint, so the scanned bytes carry no debugger trap.
    """
    seg, off = sym("TOTALTIME")
    at = f"{seg:04X}:{off:04X}"
    opened = M.call(server.scan, method="start", ref=f"{seg:04X}:{off - 0x100:04X}", length=0x200,
                    cell_bytes=2)
    first_value = read_word(at)
    first = M.call(server.scan, method="filter", operator="=", value=first_value)
    must(M.call(server.breakpoint_at, ref="COMPOSE_FRAME"), "arming COMPOSE_FRAME")
    value = first_value
    for _ in range(FRAMES_FOR_A_CHANGE):
        advanced(M.call(server.resume, seconds=10), "resume(seconds=10)", STOPPED)
        value = read_word(at)
        if value != first_value:
            break
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing COMPOSE_FRAME")
    if value == first_value:
        M.call(server.scan, method="clear")
        raise RuntimeError(f"TOTALTIME kept {value} over {FRAMES_FOR_A_CHANGE} frames")
    moved = M.call(server.scan, method="filter", operator="!")
    last = M.call(server.scan, method="filter", operator="=", value=value, limit=400)
    lin = [hexint(h.get("addr")) for h in last.get("hits") or []]
    M.call(server.scan, method="clear")
    return (off % 2 == 1 and ok(opened) and ok(first) and ok(moved) and ok(last)
            and seg * 16 + off in lin,
            f"TOTALTIME {at} {first_value} -> {value}; {said(last, 80)}")


def _coin() -> None:
    """Tab reaches the game's INT 9 (the stop), and CREDITOS rises a few frames later."""
    seg, off = sym("CREDITOS")
    before = read_word(f"{seg:04X}:{off:04X}")
    try:
        reached = key_reaches_int9("tab")
    except RuntimeError as exc:
        M.block("D Tab through the serial stub reaches the game's INT 9", str(exc))
        M.block("D the coin adds to CREDITOS", str(exc))
        return
    if not reached:
        M.block("D Tab through the serial stub reaches the game's INT 9", KEY_NOT_AT_INT9)
        M.block("D the coin adds to CREDITOS", "measured: the key never reached INT 9")
        return
    M.judge("D Tab through the serial stub reaches the game's INT 9", True,
            "the INT 9 breakpoint stopped the machine")
    must(M.call(server.breakpoint_at, ref="COMPOSE_FRAME"), "arming COMPOSE_FRAME")
    for _ in range(5):
        advanced(M.call(server.resume, seconds=10), "resume(seconds=10)", STOPPED)
    after = read_word(f"{seg:04X}:{off:04X}")
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing COMPOSE_FRAME")
    M.judge("D the coin adds to CREDITOS", after > before, f"CREDITOS {before} -> {after}")
