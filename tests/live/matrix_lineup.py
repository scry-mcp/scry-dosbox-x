"""Section E of the live matrix: Line UP, TASM real mode, a map with a segment table and no
publics, so its memory is found by a scan with no map."""
from __future__ import annotations

import re
from pathlib import Path

import bench_programs as bp
from matrix_common import (
    M,
    boot,
    cells,
    exec_of,
    free_port,
    hexint,
    judged,
    ok,
    read_word,
    refused,
    said,
    server,
)
from matrix_programs import (
    KEY_NOT_AT_INT9,
    NO_STUB,
    carries,
    key_reaches_int9,
    mcb_psp,
    program_stop,
    program_timer,
    run_for,
    segment_start,
    slow_control,
    stub_cell,
)

LU_E9 = b"LineUp: startup OK"

KEY_CELLS = ("E a key through the serial stub reaches the game's INT 9",
             "E Tab is a coin: Credits: N on E9",
             "E a scan with no map finds the credit counter")
MOVES_CELL = "E a scan with no map keeps what moves without input"
SURVIVOR_CELL = "E the survivor reads and takes one write"

E_CELLS = cells(
    ("E the program carries its E9 channel", "known: an `info` build writes `[INF]` lines"),
    ("E symbols_load refuses a map with no publics",
     "tests/real-maps.json: refused, NO `Publics by ...` section"),
    ("E run_to with the game's timer as control runs for a bound and rests on it",
     "REFERENCE.md, Advancing the machine: at the bound the machine rests on the control"),
    ("E the stub announces the serial route", "REFERENCE.md, Input and the screen"),
    ("E log_wait LineUp: startup OK", "known: the game logs `LineUp: startup OK` at start"),
    (KEY_CELLS[0], "measured; known: the game owns INT 9 and reads its own key table"),
    (KEY_CELLS[1], "measured; known: an `info` build logs `Credits: N` on a coin"),
    (KEY_CELLS[2], "REFERENCE.md, Reading and writing; known: `Credits: N` gives the value"),
    (MOVES_CELL, "the fallback when no key reaches the game; REFERENCE.md, Reading and "
                 "writing: `!` keeps the cells changed since the open"),
    (SURVIVOR_CELL, "read_memory and write docstrings: the bytes read back"),
    ("E close", "close docstring"),
)

#: The window a scan with no map opens over the data segment: small enough that the cells
#: moving on their own come back listed (a reply lists at most 400), stepped across the segment
#: until one window does.
SCAN_WINDOW = 0x400


@M.section("E", "Line UP: real mode, a map with no publics, a scan with no map", E_CELLS)
def section_e() -> None:
    if why := bp.missing(bp.LINEUP):
        M.block_rest(why)
        return
    exe, mapf = bp.LINEUP.root / bp.LINEUP.exe, bp.LINEUP.root / bp.LINEUP.map
    e9 = carries(exe, LU_E9)
    if e9:
        M.judge("E the program carries its E9 channel", True, f"{LU_E9!r} in {exe.name}")
    else:
        M.block("E the program carries its E9 channel", "prod build, no E9")
    boot(conf=bp.session_conf(bp.LINEUP, Path(M.fresh("-conf"))), cwd=bp.LINEUP.root,
         program=bp.LINEUP.launch, input_port=free_port())
    M.setup()
    r = M.call(server.symbols_load, source=str(mapf), base="0")
    judged("E symbols_load refuses a map with no publics", reply=r,
           holds=refused(r, "bad_argument") and "Publics by" in str(r.get("message")))
    exec_of("LINEUP")
    program_stop()
    psp = mcb_psp("LINEUP")
    data = psp + 0x10 + (segment_start(mapf, "_DATA") >> 4)
    timer = program_timer(psp)
    r = run_for(timer, 8)
    judged("E run_to with the game's timer as control runs for a bound and rests on it",
           reply=r, holds=ok(r) and r.get("arrived") is False and r.get("running") is False
           and int((r.get("control") or {}).get("hits") or 0) > 0)
    stub = stub_cell("E the stub announces the serial route")
    if e9:
        r = M.call(server.log_wait, pattern="LineUp: startup OK", channel="guest", seconds=5)
        judged("E log_wait LineUp: startup OK", reply=r, holds=ok(r))
    else:
        M.block("E log_wait LineUp: startup OK", "prod build, no E9")
    control = slow_control(psp) or timer
    if stub and e9:
        M.block(MOVES_CELL, "the key route exists, so this section judges the key path instead")
        _coin(control, data)
    else:
        why = NO_STUB if not stub else "prod build, no E9: no `Credits: N` to scan for"
        for label in KEY_CELLS:
            M.block(label, why)
        _moves(control, data)
    M.call(server.scan_clear)
    r = M.call(server.close)
    judged("E close", reply=r, holds=ok(r) and r.get("closed") is True)


def _confirm(at: str, value: int) -> None:
    """The survivor read back at the value the scan kept it for, one write of another value,
    and the write read back."""
    before = read_word(at)
    w = M.call(server.write, ref=at, data_hex=((value + 1) & 0xFFFF).to_bytes(2, "little").hex())
    after = read_word(at)
    M.judge(SURVIVOR_CELL, before == value and ok(w) and w.get("verified") is True
            and after == (value + 1) & 0xFFFF, f"{at}: {before} -> {after}; {said(w, 60)}")


def _moves(control: str, data: int) -> None:
    """When no key can reach the game: the cells of its data segment that change on their own
    across two runs of a few seconds, and one survivor read, written and read back."""
    for start in range(0, 0x10000, SCAN_WINDOW):
        opened = M.call(server.scan_start, ref=f"{data:04X}:{start:04X}", length=SCAN_WINDOW,
                        width="word")
        run_for(control, 4)
        first = M.call(server.scan_filter, operator="!")
        if not ok(first) or not 1 <= int(first.get("survivors") or 0) <= 400:
            M.call(server.scan_clear)
            continue
        run_for(control, 4)
        second = M.call(server.scan_filter, operator="!")
        hits = second.get("hits") or []
        M.judge(MOVES_CELL, ok(opened) and ok(second) and 1 <= len(hits) <= 400,
                f"window {data:04X}:{start:04X}, {first.get('survivors')} then "
                f"{second.get('survivors')} survivors")
        if hits:
            _confirm(str(hits[0].get("address")), hexint(hits[0].get("value")) or 0)
        else:
            M.block(SURVIVOR_CELL, "no survivor listed")
        return
    M.block(MOVES_CELL, "no window of the data segment had 1 to 400 cells moving on their own")
    M.block(SURVIVOR_CELL, "no survivor")


def _coin(control: str, data: int) -> None:
    """With the serial route alive: a coin (Tab), its `Credits: N` on E9, and a scan over the
    data segment narrowed by that value."""
    opened = M.call(server.scan_start, ref=f"{data:04X}:0000", length=0x8000, width="word")
    try:
        reached = key_reaches_int9("tab")
    except RuntimeError as exc:
        for label in (*KEY_CELLS, SURVIVOR_CELL):
            M.block(label, str(exc))
        return
    if not reached:
        M.block(KEY_CELLS[0], KEY_NOT_AT_INT9)
        for label in (*KEY_CELLS[1:], SURVIVOR_CELL):
            M.block(label, "measured: the key never reached INT 9")
        return
    M.judge(KEY_CELLS[0], True, "the INT 9 breakpoint stopped the machine")
    run_for(control, 2)
    got = M.call(server.log, pattern=r"Credits: \d+", channel="guest", limit=1)
    lines = got.get("lines") or []
    credits = re.search(r"Credits: (\d+)", str(lines[-1])) if lines else None
    judged(KEY_CELLS[1], reply=got, holds=ok(got) and credits is not None)
    if credits is None:
        for label in (KEY_CELLS[2], SURVIVOR_CELL):
            M.block(label, "no `Credits: N` line after the coin, so no value to scan for")
        return
    value = int(credits.group(1))
    moved = M.call(server.scan_filter, operator="!")
    kept = M.call(server.scan_filter, operator="=", value=value)
    hits = kept.get("hits") or []
    M.judge(KEY_CELLS[2], ok(opened) and ok(moved) and ok(kept) and 1 <= len(hits) <= 400,
            f"value {value}: {said(kept, 80)}")
    if hits:
        _confirm(str(hits[0].get("address")), value)
    else:
        M.block(SURVIVOR_CELL, "no survivor to confirm")
