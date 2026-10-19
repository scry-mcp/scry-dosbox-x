"""What the sections on DOS programs share: reading a program's own build, finding where DOS
loaded it, stopping inside it, letting it run for a while, and whether a key reaches it.

Each of those sections reads its program's copies on the bench (`bench_programs`); the matrix
never builds and never reads a project's own tree. A `prod` build writes no E9 channel by
design, so a section checks the program's own E9 string first and BLOCKS, never fails, the cells
that read the channel.
"""
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

#: The segment of the emulator's own firmware and its DOS callbacks: a stop here is not a program.
FIRMWARE_SEG = 0xF000

#: Why a key cell cannot run when the stub never spoke: the route has no guest half.
NO_STUB = ("no STUB line in the log: the conf did not run the serial stub, so the "
           "serial route has no guest half and no key can be measured through it")

_ESCAPES = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[78()][0-9A-Z]?")


def carries(exe: Path, marker: bytes) -> bool:
    """The program's own E9 string is in its bytes: a build that writes the channel."""
    return marker in exe.read_bytes()


def mcb_psp(name: str) -> int:
    """The PSP segment DOS's memory chain gives the block of the program `name`, from the
    debugger's `DOS MCBS` listing. The delta is an ncurses repaint whose columns are placed by
    cursor moves, so once the escapes are gone the size runs into the MCB segment and only the
    PSP stays whole, right before the name."""
    r = M.call(server.debug, command="DOS MCBS")
    text = _ESCAPES.sub("", str(r.get("screen_delta")))
    rows = re.findall(r"([0-9A-F]{4})\s*" + re.escape(name), text, flags=re.IGNORECASE)
    if not ok(r) or not rows:
        raise RuntimeError(f"no {name} block in DOS MCBS: {said(r)}")
    return int(rows[0], 16)


def program_stop() -> int:
    """Stop at the program's own first DOS call and answer its code segment: an INT 21h
    breakpoint stops AT the caller's `int 21h`, so the first stop outside the emulator's own
    firmware after the EXEC is the program calling. Leaves INT 21h cleared."""
    must(M.call(server.breakpoint_interrupt, number=0x21), "arming INT 21h")
    regs = resume_until(lambda regs: hexint(regs["CS"]) != FIRMWARE_SEG,
                        "an INT 21h call outside the firmware", 12)
    must(M.call(server.breakpoint_clear, ref="BPINT 21"), "clearing INT 21h")
    return hexint(regs["CS"]) or 0


def program_timer(load: int) -> str:
    """The program's own timer handler, caught as it is installed: a change watch on the INT 8
    vector at `0000:0020` stops the machine at the instruction that writes it, which catches a
    program hooking the timer by writing the table without DOS. A handler in the program's RAM
    runs at every tick, which is what a `run_to` control has to be."""
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
    must(M.call(server.watch_clear), "clearing the change watch")
    return found


def slow_control(load: int) -> str | None:
    """A handler of the program's that fires a few times a second rather than at every tick:
    the sound card's IRQ (3 to 7, vectors 0Bh to 0Fh), where the program installed one. Each
    control hit costs a round trip, so the slower the control, the more of the guest's own
    time a bounded run covers."""
    for number in range(0x0B, 0x10):
        seg, off = vector(number)
        if load <= seg < CONVENTIONAL_TOP:
            return f"{seg:04X}:{off:04X}"
    return None


def run_for(control: str, seconds: float) -> dict[str, Any]:
    """Let the machine run for `seconds` and come back stopped: `run_to` a byte nothing
    executes with a handler of the program's as the control. The docstring allows a run whose
    bound expired to come back still running; the callers read memory next, so that outcome
    is refused here, named, rather than met as a reader's `not_stopped`."""
    r = M.call(server.run_to, ref=NEVER_RUNS_TARGET, seconds=seconds, control=control)
    if not (ok(r) and r.get("running") is False):
        raise RuntimeError(f"the run for {seconds:g} s did not come back stopped: {said(r)}")
    return r


def refused_on_the_dynamic_core(label: str) -> None:
    """A program's own conf runs the dynamic core, where the debugger logs at block boundaries:
    a trace there is refused by its own count, and the log it kept at `dest` is removed here."""
    dest = Path(M.fresh(".trace"))
    r = M.call(server.trace, instructions=16, dest=str(dest), seconds=30)
    M.judge(label, refused(r, "no_channel") and "cpu core=normal" in str(r.get("message"))
            and dest.is_file(), said(r))
    dest.unlink(missing_ok=True)


def stub_cell(label: str) -> bool:
    """The serial stub announces itself on E9 when the conf ran it (REFERENCE.md, Input and the
    screen); read on a stopped machine, the log's history answers at once. A `present` line is
    the route and an `absent` one a FAIL of it. NO line means the conf never ran the stub, which
    is the program's conf and not the server: BLOCKED, and the answer is whether keys can go."""
    r = M.call(server.log, pattern=r"STUB\s+\.\s+inject device=", channel="guest", limit=5)
    lines = [str(x) for x in r.get("lines") or []]
    if ok(r) and not lines:
        M.block(label, NO_STUB)
        return False
    present = any("device=present" in x for x in lines)
    M.judge(label, ok(r) and present, said(r))
    return present


#: How long a key has to reach the keyboard controller, polled on `status`.
KEY_ARRIVAL_S = 10.0

#: Why a key with no INT 9 stop BLOCKS its cell rather than failing it: REFERENCE promises the
#: stub's injection, not that a program's INT 9 fires on it, and the silence alone does not say
#: which of the two (the byte, the program's IRQ1, the interrupt breakpoint) stayed quiet.
KEY_NOT_AT_INT9 = (f"measured: no INT 9 stop within {KEY_ARRIVAL_S:g} s of the post, with the "
                   "stub present; which link stayed quiet is not determined here")


def key_reaches_int9(key: str) -> bool:
    """Send `key` to the running program with an INT 9 breakpoint armed, and say whether the
    machine stopped: an INT 9 fires only when a key reaches the keyboard controller, so a stop is
    the key arriving and no stop within the bound the measurement that it did not. Stopped, the
    breakpoint is cleared; not stopped, the machine is left running for the caller to close."""
    must(M.call(server.breakpoint_interrupt, number=0x09), "arming INT 9")
    r = M.call(server.resume)
    if not (ok(r) and "stop_seq" not in r):
        raise RuntimeError(f"the machine did not run: {said(r)}")
    must(M.call(server.send_keys, keys=[key]), f"posting {key}")
    deadline = time.monotonic() + KEY_ARRIVAL_S
    while time.monotonic() < deadline:
        if M.call(server.status).get("cpu_mode") is not None:
            must(M.call(server.breakpoint_clear, ref="BPINT 09"), "clearing INT 9")
            return True
        time.sleep(0.25)
    return False


def guarded(label: str, run: Callable[[], tuple[bool, str]]) -> None:
    """Judge one cell whose preparation can fail for a reason that is not the tool's: such a
    failure BLOCKS the cell with the reason instead of failing it."""
    try:
        holds, detail = run()
    except RuntimeError as exc:
        M.block(label, str(exc))
        return
    M.judge(label, holds, detail)


def sym(name: str) -> tuple[int, int]:
    """A real-mode `SEG:OFF` for a symbol, from the linear address the table places it at. The
    table's `offset` is from the load base, which can run past a segment's 64 KiB, so the pair
    is chosen here: a segment 0x100 paragraphs below the byte leaves room below the offset and
    keeps the linear address's parity, which is what a word scan lines up on."""
    r = M.call(server.symbols_find, name=name)
    rows = [s for s in r.get("symbols") or [] if s.get("name") == name]
    lin = hexint(rows[0].get("linear")) if ok(r) and rows else None
    if lin is None:
        raise RuntimeError(f"{name} is not in the table: {said(r)}")
    seg = (lin >> 4) - 0x100
    return seg, lin - seg * 16


#: The PSP a DOS program's block opens with, before its load image.
PSP_BYTES = 0x100

_MAP_SEGMENT = re.compile(r"^ ([0-9A-F]{5})H ([0-9A-F]{5})H ([0-9A-F]{5})H ")


def image_end(mapf: Path) -> int:
    """One past the highest byte any segment of the map's own segment table declares."""
    stops = [int(m[2], 16) for line in mapf.read_text(encoding="latin-1").splitlines()
             if (m := _MAP_SEGMENT.match(line))]
    if not stops:
        raise RuntimeError(f"no segment table in {mapf}")
    return max(stops) + 1


def segment_start(mapf: Path, segment: str) -> int:
    """A segment's start in the map's own segment table, `Start Stop Length Name Class`."""
    for line in mapf.read_text(encoding="latin-1").splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[3] == segment and cols[0].endswith("H"):
            return int(cols[0][:-1], 16)
    raise RuntimeError(f"no {segment} row in {mapf}'s segment table")
