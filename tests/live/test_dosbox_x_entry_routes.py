"""Re-runnable entry-route measurement cases for the DOSBox-X debugger.

The protected-mode route runs on the package's DPMI guest (`dpmi_guest`, a DJGPP program
under the DPMI host DOSBox-X provides); the real-mode route runs dos-real16's copy on the bench
(`bench_programs`), whose Borland map has publics, and SKIPS naming the file when a copy is
absent or off its pin. The walk's ceiling is DOSBOX_X_WALK_MAX: a count of interrupt stops
before the program's own code is reached, whose default fits both programs.

WHY THIS IS A RESUME-WALK AND NOT ONE CALL. A DPMI client's own code cannot be reached in
a single gesture: `run_to` refuses a 32-bit offset in real mode (the reset vector is real
mode), a code breakpoint armed at that reset folds `seg:off` to the wrong linear because
no selector table exists yet, and a linear breakpoint is a memory-CHANGE one, not a code
one. So the route is to break on the DPMI interrupt and resume until the machine is
running the client's OWN 32-bit code -- told apart from the 16-bit setup stub by BOTH the
CPU mode AND the segment limit, since a 16-bit stub selector cannot bracket the program's
address space. Real mode has no selector translation, so its only obstacle is finding the
load segment, read off the loop's CS against a known map frame and CONFIRMED by
resolving the stop's own address back to a nearby named symbol.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import bench_programs as bp
import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

pytestmark = pytest.mark.live

BIOS_SEG = 0xF000        # DOSBox-X's BIOS/callback segment; an INT stop here is firmware
# A CEILING on the resume-walk, not a count: reaching it is failure. The default fits both
# programs the walk runs on.
WALK_MAX = int(os.environ.get("DOSBOX_X_WALK_MAX", "40"))
SESSION_SECONDS = 300    # wall-clock bound for one measurement boot
STUB_LIMIT_MAX = 0xFFFF  # a 16-bit setup-stub selector cannot exceed this; the client does
DELTA_MAX = 0x2000       # a stop INSIDE a function sits no further than this below its symbol


def reach_djgpp(logfile: str | None = None) -> dict[str, int]:
    """Start the DPMI program, break on the DPMI interrupt, and resume until the machine
    is running the client's OWN 32-bit code. Returns the CS descriptor reached. SHARED with
    the stop-reply live file, so the two cannot drift on what counts as arrival.

    ARRIVAL is the 32-bit client, not the 16-bit setup stub. The stub also issues the
    watched interrupt, in Pr16 through a selector whose base can sit above low memory, so
    a base test alone admits it. What the stub cannot fake is a Pr32 mode paired with a
    selector limit past the 16-bit ceiling -- that pair is the client's code segment.

    THE INTERRUPT BREAKPOINT IS LEFT ARMED, deliberately: the walk's last stop IS one of
    its firings, and the caller decides what to do next. It is now a stored declaration,
    so `breakpoint_clear` removes it by its row text (the console's `BPDEL` numbers the
    list BP-first, not by arming order, which is why clearing it by index once deleted a
    code breakpoint); the walk leaves it for the caller rather than clearing it here.
    """
    r = server.start(conf=str(guest.CONF), cwd=str(guest.GUEST), seconds=SESSION_SECONDS,
                     logfile=logfile, program=guest.PROGRAM)
    assert r["status"] == "ok", r
    assert server.breakpoint_interrupt(number=0x31, ah=0x00)["status"] == "ok"
    for i in range(1, WALK_MAX + 1):
        res = cast(dict[str, Any], server.resume())
        assert res.get("status") == "ok", (
            f"the session went away at resume {i}: {res.get('message')}")
        assert res.get("halted"), (
            f"resume {i} did not halt: the DPMI walk needs the guest to keep issuing the "
            f"interrupt, and a guest that ran on has left the walk")
        at = res.get("stopped_at") or {}
        if at.get("mode") != "Pr32":       # the setup stub is Pr16; the client is Pr32
            continue
        try:
            sel = cast(ds.Session, dstate.STATE.session).selector("CS")
        except ds.Invalid:
            continue                        # no present descriptor here; keep walking
        if sel["limit"] > STUB_LIMIT_MAX:   # a 16-bit stub selector cannot reach here
            return sel
    raise AssertionError(f"never reached the client's 32-bit code in {WALK_MAX} resumes")


def test_djgpp_entry_reaches_the_client_and_symbols_place() -> None:
    """Break on the DPMI interrupt, resume to the client's own 32-bit code, then load
    symbols off the running client and resolve a name. The arrival test itself lives in
    `reach_djgpp`; what this case adds is that the symbols PLACE against what it reached."""
    sel = reach_djgpp()
    load = cast(dict[str, Any], server.symbols_load(source=str(guest.SYM)))
    assert load["status"] == "ok", load
    # symbols_load measures the base off the SAME descriptor the walk reached, so equality
    # is a consistency check, not the arrival proof -- the mode-and-limit gate above is.
    assert load["base"] == sel["base"], (
        "symbols_load measured a base other than the reached CS descriptor's")
    assert cast(int, load["loaded"]) > 0
    main = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert main["status"] == "ok" and main["symbols"], main
    # The reached selector's limit must BRACKET the program the symbols describe: `_main`
    # sits inside the segment. On the stub (limit <= the 16-bit ceiling) this would fail,
    # which is why it is a real check rather than the placer's own arithmetic echoed back.
    assert main["symbols"][0]["offset"] <= sel["limit"], (
        "the reached selector's limit does not bracket `_main`, so this is not the "
        "client's code segment")


#: Why the real-mode program cannot run here, naming the file, or empty; and the mark that skips
#: a case on it.
REAL_WHY_NOT = bp.missing(bp.DOS_REAL16)
REAL_PROGRAM = pytest.mark.skipif(bool(REAL_WHY_NOT), reason=REAL_WHY_NOT)
#: Where the walk catches dos-real16's own repeating INT 21: it reads its WAD in packets before
#: anything else, and that is this routine. A repin of the copy can move it, and the resolution
#: the entry case asserts names where it went.
REAL_LOOP = "XMS_CARGAR_WAD"
#: A public of the map that carries the linker's mark, and a variable of its `_DATA`.
REAL_MARKED = "ACTIVEIMAN"
REAL_VARIABLE = "TOTALTIME"


def real_address(load_seg: int, name: str) -> str:
    """`name`'s `SEG:OFF` with the program loaded at `load_seg`, from its map."""
    frame, offset, _marked = bp.public(bp.DOS_REAL16, name)
    return f"{load_seg + frame:04X}:{offset:04X}"


def reach_realmode(into: Path, logfile: str | None = None) -> tuple[int, int, int]:
    """Start the real-mode program on a session conf derived into `into`, break on INT 21,
    reach its OWN repeating INT 21 (past the loader), derive the load segment from that CS and
    the map frame, and load the map at that base. Returns (load_seg, prog_cs, prog_eip).
    SHARED with the name-layer, stop-reply and break-on-change live files so they cannot drift
    on how the program's own loop is found.

    `logfile` is passed to `start` for a case that reads the guest's E9 channel; without it
    every E9 block answers `available: False`."""
    frame = bp.public(bp.DOS_REAL16, REAL_LOOP)[0]
    r = server.start(conf=str(bp.session_conf(bp.DOS_REAL16, into)), cwd=str(bp.DOS_REAL16.root),
                     seconds=SESSION_SECONDS, logfile=logfile, program=bp.DOS_REAL16.launch)
    assert r["status"] == "ok", r
    assert server.breakpoint_interrupt(number=0x21)["status"] == "ok"
    first_nonbios: str | None = None
    prev: str | None = None
    caught: tuple[int, int] | None = None      # (segment, offset) of the program's loop
    for _ in range(WALK_MAX):
        res = cast(dict[str, Any], server.resume())
        assert res.get("status") == "ok", (
            f"the session went away mid-walk: {res.get('message')}")
        at = res.get("stopped_at")
        # A cut pane is `halted` with `stopped_at` None -- a real state. Do NOT let its CS
        # default to the BIOS segment (that would misfile it and desync the repeat check);
        # skip it, and skip a guest that ran on.
        if not res.get("halted") or not at:
            continue
        cs = at["cs"]
        seg = int(cs, 16)
        if seg != BIOS_SEG and first_nonbios is None:
            first_nonbios = cs             # the loader (COMMAND.COM), which EXECs the program
        # The program runs its own INT 21 loop from its OWN segment; the loader makes only
        # a couple of consecutive calls. The first repeating non-BIOS, non-loader segment
        # is the program running its own code.
        if seg != BIOS_SEG and cs != first_nonbios and cs == prev:
            caught = (seg, int(at["eip"], 16))
            break
        prev = cs if seg != BIOS_SEG else prev
    assert caught is not None, "never caught the program's own INT 21 loop"
    prog_cs, prog_eip = caught
    load_seg = prog_cs - frame
    assert load_seg >= 0, f"frame {frame:#x} exceeds the program CS {prog_cs:#x}"
    mapf = bp.DOS_REAL16.root / bp.DOS_REAL16.map
    load = cast(dict[str, Any], server.symbols_load(source=str(mapf), base=f"{load_seg * 16:X}"))
    assert load["status"] == "ok", load
    return load_seg, prog_cs, prog_eip


@REAL_PROGRAM
def test_realmode_entry_finds_the_load_segment_and_symbols_place(tmp_path: Path) -> None:
    """Break on INT 21, reach the program's own INT 21 loop (not the loader), derive the
    load segment from its CS and the known map frame, and CONFIRM the derived base by
    resolving the stop's own address back to a nearby symbol -- a wrong frame lands far
    from any symbol or below the table, so the resolution is what makes this bite."""
    load_seg, prog_cs, prog_eip = reach_realmode(tmp_path)
    # THE NON-TAUTOLOGICAL CHECK: resolve the stop's REAL address (prog_cs:prog_eip folded)
    # back through the loaded table. The stop is INSIDE the loop's function the caller
    # named, so with the right base it resolves to THAT symbol, a short distance below.
    # A wrong frame shifts the offset and resolves to a different symbol, or below the
    # table -- which the placer's own `base + offset` echo could never show.
    here = cast(dict[str, Any], server.symbols_find(linear=f"{prog_cs * 16 + prog_eip:X}"))
    assert here["status"] == "ok", (
        f"the derived base {load_seg * 16:#x} resolves the running stop to nothing, so it "
        f"is not where the program is: {here.get('message')}")
    assert here["name"] == REAL_LOOP, (
        f"the stop resolves to {here.get('name')}, not the named loop symbol "
        f"{REAL_LOOP}, so the derived base places the program wrong")
    assert 0 <= cast(int, here["delta"]) <= DELTA_MAX, (
        f"the stop is {here['delta']:#x} below {here.get('name')}, further than a stop "
        f"inside that function should sit -- the base is off")
