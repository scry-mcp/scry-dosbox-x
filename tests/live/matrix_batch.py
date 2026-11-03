"""Section AA of the live matrix: what the debugger commands added to DOSBox-X do once
the machine exists, which the emulator's own unit tests cannot reach.

`MEMDUMPLIN`'s file name and its two refusals, `VGAMEMDUMP`'s file name, `PORTINFO` as typed
and the dynamic core's guard against a long run of one-byte instructions. The file-name cells
need a case-sensitive volume: run with `DOSBOX_X_LIVE_PRIVATE` naming a directory on one, so the
guests are copied there; a volume that folds case is detected and the cells are BLOCKED.
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from matrix_common import (
    ENV,
    GUEST,
    M,
    boot,
    cells,
    close_whatever,
    ok,
    read_bytes,
    said,
    server,
)
from matrix_dpmi import dpmi_client

from scry_dosbox_x import state as dstate

MIXED_NAME = "MixedCase.Bin"
FILE_CELLS = (
    "AA MEMDUMPLIN keeps the file name's case and holds the bytes the flat selector reads",
    "AA MEMDUMPLIN FFFFFF00 200 is refused and writes no file",
    "AA MEMDUMPLIN before any page tables are loaded is refused and leaves no data",
    "AA VGAMEMDUMP keeps the file name's case",
)
PORT_CELL = ("AA PORTINFO answers port 60 with R1=1 and an unclaimed port with zeros, and "
             "refuses 10000")
RUNSTATE_CELL = ("AA RUNSTATE names the BPIF row that stopped the machine, and no longer after "
                 "a step")
FRAMES_CELL = "AA RUNSTATE's frames stands still while the machine is stopped and a VRD redraws"
RUNWATCH_CELL = "AA a BPIF stop reached under RUNWATCH still names its row, until the next step"
TAP_CELL = "AA TAP refuses an offset past 32 bits and installs nothing"
DYNAMIC_CELL = "AA the dynamic core runs 3000 STI, 3000 CLI and 1500 STI;NOP and exits 0"
AA_CELLS = cells(
    (FILE_CELLS[0], "MEMDUMPLIN usage text: a dump by linear address, the name as typed"),
    (FILE_CELLS[1], "MEMDUMPLIN: a dump past the end of the 32-bit linear space"),
    (FILE_CELLS[2], "MEMDUMPLIN usage text: nothing until a DPMI host loaded the page tables; "
     "the file is opened before the walk, as MEMDUMPBIN's is"),
    (FILE_CELLS[3], "VGAMEMDUMP usage text: the file name as typed"),
    (PORT_CELL, "PORTINFO usage text: R1/R2/R4/W1/W2/W4 per port, hex within the I/O space"),
    (RUNSTATE_CELL, "RUNSTATE: `bpif=` rides the stop a BPIF row made and goes with the next run"),
    (FRAMES_CELL, "README.debugger RUNSTATE: frames counts the frames the guest started"),
    (RUNWATCH_CELL, "README.debugger RUNSTATE: bpif= stays until a run, a step or the row goes"),
    (TAP_CELL, "TAP usage text: hex seg:off, a 32-bit offset"),
    (DYNAMIC_CELL, "dynrec: a run of one-byte instructions no longer overruns the stub slots"),
)
#: A run of STI, of CLI and of STI;NOP pairs, each ended by RET.
DYNAMIC_PROGRAMS = {
    "STI.COM": b"\xFB" * 3000 + b"\xC3",
    "CLI.COM": b"\xFA" * 3000 + b"\xC3",
    "STINOP.COM": b"\xFB\x90" * 1500 + b"\xC3",
}
DYNAMIC_RUN_S = 90


#: The files the cells judge, in both spellings, written by the emulator into the guest's directory.
LEFTOVERS = tuple(n for name in (MIXED_NAME, "Wrap.Bin", "Early.Bin", "VgaCase.Bin")
                  for n in (name, name.upper()))


def _scrub() -> None:
    """Take away the files an earlier run left, so one is never judged as this run's."""
    for name in LEFTOVERS:
        (GUEST / name).unlink(missing_ok=True)


def _says(command: str) -> tuple[bool, str]:
    """Whether the debugger took the command to its end, and what it printed."""
    r = M.call(server.debug, command=command)
    return (True, str(r.get("output", ""))) if ok(r) else (False, said(r))


def _case_sensitive(where: Path) -> bool:
    """Whether `where` holds two names that differ only in case, tried with files of this run."""
    a, b = where / "case-probe.tmp", where / "CASE-PROBE.TMP"
    for p in (a, b):
        p.write_bytes(p.name.encode())
    names = {p.name for p in where.iterdir()}
    for p in (a, b):
        p.unlink(missing_ok=True)
    return {a.name, b.name} <= names


def _names() -> set[str]:
    return {p.name for p in GUEST.iterdir()}


def _dpmi_files() -> None:
    stop, loaded = dpmi_client()
    if not (ok(stop) and ok(loaded)):
        _block_dpmi_cells(f"the DPMI guest did not stop: {said(stop)}; {said(loaded)}")
        return
    found = M.call(server.symbols_find, name="_g_ticks")
    sym = [s for s in found.get("symbols") or [] if s.get("name") == "_g_ticks"]
    linear = int(str(sym[0].get("addr")), 16) if sym else None
    if linear is None:
        _block_dpmi_cells(f"_g_ticks has no address: {said(found)}")
        return
    _took, said_out = _says(f"MEMDUMPLIN {linear:08X} 20 {MIXED_NAME}")
    names = _names()
    flat = M.call(server.memdump, ref=f"0038:{linear:08X}", length=0x20, dest=M.fresh(".bin"))
    read = read_bytes(f"0038:{linear:08X}", 0x20) if ok(flat) else None
    dumped = (GUEST / MIXED_NAME).read_bytes() if (GUEST / MIXED_NAME).is_file() else None
    M.judge(FILE_CELLS[0], MIXED_NAME in names and MIXED_NAME.upper() not in names
            and dumped is not None and dumped == read,
            f"{said_out[:80]!r}; names {sorted(n for n in names if 'ixed' in n.lower())}")
    took, wrapped = _says("MEMDUMPLIN FFFFFF00 200 Wrap.Bin")
    M.judge(FILE_CELLS[1], took and "past the end" in wrapped and "Wrap.Bin" not in _names()
            and "WRAP.BIN" not in _names() and "success" not in wrapped.lower(), wrapped[:120])
    close_whatever()


def _block_dpmi_cells(why: str) -> None:
    for label in FILE_CELLS[:2]:
        M.block(label, why)
    close_whatever()


def _before_page_tables(folds: bool) -> None:
    boot()
    took, early = _says("MEMDUMPLIN 0 10 Early.Bin")
    left = [GUEST / n for n in ("Early.Bin", "EARLY.BIN") if (GUEST / n).is_file()]
    M.judge(FILE_CELLS[2], took and "not mapped" in early and "success" not in early.lower()
            and all(p.stat().st_size == 0 for p in left), early[:120])
    if not folds:
        took, vga = _says("VGAMEMDUMP 0 10 VgaCase.Bin")
        names = _names()
        M.judge(FILE_CELLS[3], took and "success" in vga and "VgaCase.Bin" in names
                and "VGACASE.BIN" not in names, vga[:120])
    (read_ok, port_read), (none_ok, port_none), (over_ok, port_over) = (
        _says("PORTINFO 60"), _says("PORTINFO 2E8"), _says("PORTINFO 10000"))
    M.judge(PORT_CELL, read_ok and none_ok and over_ok and "PORTINFO 0060 R1=1" in port_read
            and "R1=0 R2=0 R4=0 W1=0 W2=0 W4=0" in port_none and "R1=" not in port_over,
            f"{port_read[:50]!r} / {port_none[:60]!r} / {port_over[:60]!r}")
    armed = M.call(server.regpoint_add, condition="bx == 0x100")
    stop = M.call(server.resume, seconds=30)
    named_ok, named = _says("RUNSTATE")
    stepped = M.call(server.step)
    after_ok, after = _says("RUNSTATE")
    M.judge(RUNSTATE_CELL, ok(armed) and ok(stop) and ok(stepped) and named_ok and after_ok
            and "bpif=" in named and "bpif=" not in after, f"{named[:90]!r} / {after[:90]!r}")
    _frames_and_tap()
    close_whatever()
    _runwatch()


def _frames(text: str) -> int | None:
    found = re.search(r"frames=(\d+)", text)
    return int(found.group(1)) if found else None


def _frames_and_tap() -> None:
    _, before = _says("RUNSTATE")
    redraw_ok, _ = _says("VRD")
    _, after = _says("RUNSTATE")
    M.judge(FRAMES_CELL, redraw_ok and _frames(before) is not None
            and _frames(before) == _frames(after), f"{before[-40:]!r} / {after[-40:]!r}")
    took, tapped = _says("TAP W 0:100000010 tap-off.txt")
    listed_ok, listing = _says("TAPLIST")
    leftover = (GUEST / "tap-off.txt").exists()
    _says("TAPDEL *")
    with contextlib.suppress(OSError):
        (GUEST / "tap-off.txt").unlink(missing_ok=True)
    M.judge(TAP_CELL, took and "usage" in tapped and listed_ok and "INSTALLED=1" not in listing
            and not leftover, f"{tapped[:80]!r} / {listing[:60]!r}")


def _runwatch() -> None:
    """A BPIF stop reached by RUNWATCH, sent to the session directly: the server's `debug` tool
    refuses the commands that release the guest."""
    boot()
    armed = M.call(server.regpoint_add, condition="bx == 0x100")
    ses = dstate.STATE.session
    named, after = "", ""
    if ses is not None and ok(armed):
        ses.exec("RUNWATCH")
        for _ in range(10):
            time.sleep(2)
            named = "\n".join(ses.exec("RUNSTATE")[1])
            if "stopped" in named:
                break
        ses.exec("STEPIN")
        after = "\n".join(ses.exec("RUNSTATE")[1])
    M.judge(RUNWATCH_CELL, "stopped" in named and "bpif=" in named and "stopped" in after
            and "bpif=" not in after, f"{named[-60:]!r} / {after[-60:]!r}")
    close_whatever()


def _dynamic_core() -> None:
    binary = ENV.get("DOSBOX_X_BINARY", "")
    if not binary or not Path(binary).is_file():
        M.block_rest("DOSBOX_X_BINARY does not name the emulator this cell runs directly")
        return
    where = M.tmp("-dynamic-")
    exits: dict[str, int | str] = {}
    fell_back = False
    for name, body in DYNAMIC_PROGRAMS.items():
        (where / name).write_bytes(body)
        conf = where / f"{name}.conf"
        conf.write_text(f'[cpu]\ncore=dynamic\ncputype=pentium\n[autoexec]\nmount c "{where}"\n'
                        f"c:\n{name}\nexit\n", encoding="ascii")
        run_env: dict[str, Any] = {**os.environ, "SDL_VIDEODRIVER": "dummy"}
        try:
            done = subprocess.run([binary, "-conf", str(conf), "-nogui", "-exit",
                                   "-set", "sdl waitonerror=false"], env=run_env, cwd=where,
                                  capture_output=True, timeout=DYNAMIC_RUN_S, check=False)
        except subprocess.TimeoutExpired:
            exits[name] = "timeout"
            continue
        exits[name] = done.returncode
        # A build with no dynamic core runs the normal one and exits 0 without trying the guard.
        fell_back = fell_back or b"switching back to normal" in done.stdout + done.stderr
    M.judge(DYNAMIC_CELL, set(exits.values()) == {0} and not fell_back,
            f"exit codes {exits}; fell back to the normal core: {fell_back}")


@M.section("AA", "the debugger commands added to DOSBox-X and the dynamic core guard, on the "
           "package's guests", AA_CELLS)
def section_aa() -> None:
    _scrub()
    _dynamic_core()
    folds = not _case_sensitive(GUEST)
    if folds:
        for label in (FILE_CELLS[0], FILE_CELLS[1], FILE_CELLS[3]):
            M.block(label, f"{GUEST} folds case: run with DOSBOX_X_LIVE_PRIVATE on a "
                    "case-sensitive volume")
    else:
        _dpmi_files()
    _before_page_tables(folds)
    _scrub()

