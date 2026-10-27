"""Helpers shared by the DOS-program sections."""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from matrix_common import (
    CONVENTIONAL_TOP,
    NEVER_RUNS_TARGET,
    M,
    hexint,
    must,
    ok,
    refused,
    resume_until,
    said,
    server,
    vector,
)

#: Emulator firmware and DOS callbacks: a stop here is not the program.
FIRMWARE_SEG = 0xF000

NO_STUB = ("no STUB line in the log: the conf did not run the serial stub, so the "
           "serial route has no guest half and no key can be measured through it")



def carries(exe: Path, marker: bytes) -> bool:
    return marker in exe.read_bytes()


def mcb_psp(name: str) -> int:
    """The PSP segment of `name`'s block, off the `DOS MCBS` listing."""
    r = M.call(server.debug, command="DOS MCBS")
    text = str(r.get("output"))
    rows = re.findall(r"([0-9A-F]{4})\s*" + re.escape(name), text, flags=re.IGNORECASE)
    if not ok(r) or not rows:
        raise RuntimeError(f"no {name} block in DOS MCBS: {said(r)}")
    return int(rows[0], 16)


def program_stop() -> int:
    """The code segment at the program's first INT 21h call."""
    must(M.call(server.breakpoint_interrupt, number=0x21), "arming INT 21h")
    regs = resume_until(lambda regs: hexint(regs["CS"]) != FIRMWARE_SEG,
                        "an INT 21h call outside the firmware", 12)
    must(M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 21"), "clearing INT 21h")
    return hexint(regs["CS"]) or 0


def program_timer(load: int) -> str:
    """The program's timer handler, caught as it is written to the INT 8 vector."""
    must(M.call(server.watch_add, ref="0000:0020", mode="change", length=4, fmt="u32"),
         "arming the change watch on the INT 8 vector")
    found = ""

    def hooked(_regs: dict[str, Any]) -> bool:
        nonlocal found
        seg, off = vector(0x08)
        found = f"{seg:04X}:{off:04X}" if load <= seg < CONVENTIONAL_TOP else ""
        return bool(found)

    if not hooked({}):
        resume_until(hooked, "the program hooking INT 8", 8)
    must(M.call(server.declaration_clear, kind="watch", all=True), "clearing the change watch")
    return found


def slow_control(load: int) -> str | None:
    """The program's sound card IRQ handler, if any: a rare control covers more guest time."""
    for number in range(0x0B, 0x10):
        seg, off = vector(number)
        if load <= seg < CONVENTIONAL_TOP:
            return f"{seg:04X}:{off:04X}"
    return None


def run_for(control: str, seconds: float) -> dict[str, Any]:
    """Run for `seconds` via `run_to` a byte nothing executes."""
    r = M.call(server.run_to, ref=NEVER_RUNS_TARGET, seconds=seconds, control=control)
    if not (ok(r) and (r.get("session") or {}).get("running") is False):
        raise RuntimeError(f"the run for {seconds:g} s did not come back stopped: {said(r)}")
    return r


def refused_on_the_dynamic_core(label: str) -> None:
    """The dynamic core logs once per block, so a trace is refused by count."""
    dest = Path(M.fresh(".trace"))
    r = M.call(server.trace, instructions=16, dest=str(dest), seconds=30)
    M.judge(label, refused(r, "no_channel") and "cpu core=normal" in str(r.get("message"))
            and dest.is_file(), said(r))
    dest.unlink(missing_ok=True)


def stub_cell(label: str) -> bool:
    """No STUB line means the conf never ran it: BLOCKED."""
    r = M.call(server.log, pattern=r"STUB\s+\.\s+scry device=", channel="guest", limit=5)
    lines = [str(x) for x in r.get("lines") or []]
    if ok(r) and not lines:
        M.block(label, NO_STUB)
        return False
    present = any("device=present" in x for x in lines)
    M.judge(label, ok(r) and present, said(r))
    return present


KEY_ARRIVAL_S = 10.0

#: BLOCKS rather than fails: the silence does not say which link (byte, IRQ1, breakpoint) failed.
KEY_NOT_AT_INT9 = (f"measured: no INT 9 stop within {KEY_ARRIVAL_S:g} s of the post, with the "
                   "stub present; which link stayed quiet is not determined here")


def key_reaches_int9(key: str) -> bool:
    """Whether `key` stops at INT 9, at the vector's own CS:IP; if not, the machine is left
    running, or stopped elsewhere."""
    must(M.call(server.breakpoint_interrupt, number=0x09), "arming INT 9")
    r = M.call(server.resume)
    if not (ok(r) and "stop_seq" not in r):
        raise RuntimeError(f"the machine did not run: {said(r)}")
    posted = M.call(server.send_keys, keys=[key])
    # The make reaching INT 9 parks the machine before the stub can acknowledge it.
    if not (ok(posted) or refused(posted, "wait_stopped")):
        raise RuntimeError(f"posting {key}: {said(posted)}")
    deadline = time.monotonic() + KEY_ARRIVAL_S
    while time.monotonic() < deadline:
        status = M.call(server.status)
        if isinstance(status.get("cpu_mode"), str):
            must(M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 09"),
                 "clearing INT 9")
            seg, off = vector(0x09)
            pc = str((status.get("last_stop") or {}).get("pc", ""))
            at = [hexint(part) for part in pc.split(":")] if ":" in pc else []
            return at == [seg, off]
        time.sleep(0.25)
    return False


def guarded(label: str, run: Callable[[], tuple[bool, str]]) -> None:
    """A preparation failure BLOCKS the cell."""
    try:
        holds, detail = run()
    except RuntimeError as exc:
        M.block(label, str(exc))
        return
    M.judge(label, holds, detail)


def sym(name: str) -> tuple[int, int]:
    """A `SEG:OFF` for a symbol; the table's offset can pass 64 KiB."""
    r = M.call(server.symbols_find, name=name)
    rows = [s for s in r.get("symbols") or [] if s.get("name") == name]
    lin = hexint(rows[0].get("addr")) if ok(r) and rows else None
    if lin is None:
        raise RuntimeError(f"{name} is not in the table: {said(r)}")
    seg = (lin >> 4) - 0x100
    return seg, lin - seg * 16


PSP_BYTES = 0x100

_MAP_SEGMENT = re.compile(r"^ ([0-9A-F]{5})H ([0-9A-F]{5})H ([0-9A-F]{5})H ")


def image_end(mapf: Path) -> int:
    stops = [int(m[2], 16) for line in mapf.read_text(encoding="latin-1").splitlines()
             if (m := _MAP_SEGMENT.match(line))]
    if not stops:
        raise RuntimeError(f"no segment table in {mapf}")
    return max(stops) + 1


def segment_start(mapf: Path, segment: str) -> int:
    for line in mapf.read_text(encoding="latin-1").splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[3] == segment and cols[0].endswith("H"):
            return int(cols[0][:-1], 16)
    raise RuntimeError(f"no {segment} row in {mapf}'s segment table")
