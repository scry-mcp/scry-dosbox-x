from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import bench_programs as bp
import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

from scry_dosbox_x import server
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

pytestmark = pytest.mark.live

BIOS_SEG = 0xF000
WALK_MAX = int(os.environ.get("DOSBOX_X_WALK_MAX", "40"))
SESSION_SECONDS = 300
RESUME_S = 30
STUB_LIMIT_MAX = 0xFFFF
DELTA_MAX = 0x2000


def reach_djgpp(logfile: str | None = None) -> dict[str, int]:
    """Resume to the client's own 32-bit code and return its CS; the INT breakpoint stays armed.

    The 16-bit setup stub also issues the interrupt, so arrival needs Pr32 and a wide limit.
    """
    r = server.start(conf=str(guest.CONF), cwd=str(guest.GUEST),
                     session_seconds=SESSION_SECONDS,
                     logfile=logfile, program=guest.PROGRAM)
    assert r["status"] == "ok", r
    assert server.breakpoint_interrupt(number=0x31, ah=0x00)["status"] == "ok"
    for i in range(1, WALK_MAX + 1):
        res = cast(dict[str, Any], server.resume(seconds=RESUME_S))
        assert res.get("status") == "ok", (
            f"the session went away at resume {i}: {res.get('message')}")
        assert "pc" in res, (
            f"resume {i} did not halt: the DPMI walk needs the guest to keep issuing the "
            f"interrupt, and a guest that ran on has left the walk")
        try:
            held = cast(ds.Session, dstate.STATE.session)
            if held.where().get("mode") != "Pr32":
                continue
            sel = held.selector("CS")
        except ds.Invalid:
            continue
        if sel["limit"] > STUB_LIMIT_MAX:
            return sel
    raise AssertionError(f"never reached the client's 32-bit code in {WALK_MAX} resumes")


def test_djgpp_entry_reaches_the_client_and_symbols_place() -> None:
    """Symbols loaded off the reached client place against its selector."""
    sel = reach_djgpp()
    load = cast(dict[str, Any], server.symbols_load(path=str(guest.SYM)))
    assert load["status"] == "ok", load
    assert int(load["base"], 16) == sel["base"], (
        "symbols_load measured a base other than the reached CS descriptor's")
    assert cast(int, load["loaded"]) > 0
    main = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert main["status"] == "ok" and main["symbols"], main
    assert int(main["symbols"][0]["offset"], 16) <= sel["limit"], (
        "the reached selector's limit does not bracket `_main`, so this is not the "
        "client's code segment")


#: Empty, or why the real-mode program cannot run here (naming the file).
REAL_WHY_NOT = bp.missing(bp.DOS_REAL16)
REAL_PROGRAM = pytest.mark.skipif(bool(REAL_WHY_NOT), reason=REAL_WHY_NOT)
REAL_LOOP = "XMS_CARGAR_WAD"
REAL_MARKED = "ACTIVEIMAN"
REAL_VARIABLE = "TOTALTIME"


def real_address(load_seg: int, name: str) -> str:
    """`name`'s `SEG:OFF` with the program loaded at `load_seg`."""
    frame, offset, _marked = bp.public(bp.DOS_REAL16, name)
    return f"{load_seg + frame:04X}:{offset:04X}"


def reach_realmode(into: Path, logfile: str | None = None) -> tuple[int, int, int]:
    """Reach the program's own INT 21 loop, load its map there; return (load_seg, CS, EIP)."""
    frame = bp.public(bp.DOS_REAL16, REAL_LOOP)[0]
    r = server.start(conf=str(bp.session_conf(bp.DOS_REAL16, into)), cwd=str(bp.DOS_REAL16.root),
                     session_seconds=SESSION_SECONDS, logfile=logfile, program=bp.DOS_REAL16.launch)
    assert r["status"] == "ok", r
    assert server.breakpoint_interrupt(number=0x21)["status"] == "ok"
    first_nonbios: str | None = None
    prev: str | None = None
    caught: tuple[int, int] | None = None
    for _ in range(WALK_MAX):
        res = cast(dict[str, Any], server.resume(seconds=RESUME_S))
        assert res.get("status") == "ok", (
            f"the session went away mid-walk: {res.get('message')}")
        pc = res.get("pc")
        # a cut pane or a guest that ran on carries no `pc`; defaulting its CS to BIOS would
        # desync the repeat check
        if not isinstance(pc, str):
            continue
        cs, eip = pc.split(":")
        seg = int(cs, 16)
        if seg != BIOS_SEG and first_nonbios is None:
            first_nonbios = cs
        # the loader makes only a couple of consecutive calls; a repeat is the program's loop
        if seg != BIOS_SEG and cs != first_nonbios and cs == prev:
            caught = (seg, int(eip, 16))
            break
        prev = cs if seg != BIOS_SEG else prev
    assert caught is not None, "never caught the program's own INT 21 loop"
    prog_cs, prog_eip = caught
    load_seg = prog_cs - frame
    assert load_seg >= 0, f"frame {frame:#x} exceeds the program CS {prog_cs:#x}"
    mapf = bp.DOS_REAL16.root / bp.DOS_REAL16.map
    load = cast(dict[str, Any], server.symbols_load(path=str(mapf), base=f"0x{load_seg * 16:X}"))
    assert load["status"] == "ok", load
    return load_seg, prog_cs, prog_eip


@REAL_PROGRAM
def test_realmode_entry_finds_the_load_segment_and_symbols_place(tmp_path: Path) -> None:
    """The derived load segment resolves the stop back to the named loop symbol."""
    load_seg, prog_cs, prog_eip = reach_realmode(tmp_path)
    here = cast(dict[str, Any], server.symbols_find(linear=f"0x{prog_cs * 16 + prog_eip:X}"))
    assert here["status"] == "ok", (
        f"the derived base {load_seg * 16:#x} resolves the running stop to nothing, so it "
        f"is not where the program is: {here.get('message')}")
    assert here["name"] == REAL_LOOP, (
        f"the stop resolves to {here.get('name')}, not the named loop symbol "
        f"{REAL_LOOP}, so the derived base places the program wrong")
    assert 0 <= cast(int, here["delta"]) <= DELTA_MAX, (
        f"the stop is {here['delta']:#x} below {here.get('name')}, further than a stop "
        f"inside that function should sit -- the base is off")
