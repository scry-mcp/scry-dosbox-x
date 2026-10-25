"""Section K of the live matrix: `trace`, the debugger's CPU log counted in instructions, on the
package's probe guest, and the routines it names on dos-real16 and the DPMI guest.

The known answers are the guest's own arithmetic: at its settle loop `loop` takes one off ECX per
instruction it executes, so a trace of n instructions there leaves ECX n lower, at one address;
a breakpoint on the `dec bx` after the loop cuts a long trace exactly when ECX reaches zero, so
the instructions it executed are the ECX read before it; 200 instructions from `start` split
51, 144 and 5 over `start`, `emit` and `bump`, the tick string's length and the odometer's
digit. The emulator's account (the file's lines, the pane's counter) is what is judged against
them, never the other way round. On the two programs the known answer is the symbol table's: a
window from a routine's breakpoint starts at that routine's own linear address.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import bench_programs as bp
from matrix_common import (
    GUEST,
    M,
    boot,
    cells,
    hexint,
    judged,
    must,
    ok,
    refused,
    release_running,
    said,
    server,
)
from matrix_dos_real16 import dos_real16_main_loop
from matrix_dpmi import dpmi_client

import dosbox_trace as tracing

NORMAL_CORE_FLAGS = ["-set", "cpu core=normal"]
DYNAMIC_CORE_FLAGS = ["-set", "cpu core=dynamic"]
#: The settle loop's `loop` and the `dec bx` after it, offsets in the probe's segment.
SETTLE_LOOP = 0x106
AFTER_LOOP = 0x108
#: Instructions each shape's known answer executes; each of the four takes this much ECX.
PER_SHAPE = 64
#: The wait every trace here declares: under the matrix's own ceiling, and far above what the
#: probe's few thousand instructions take.
TRACE_S = 30
#: `start`, and the probe's own arithmetic over 200 instructions from it (the module docstring).
START = 0x10B
START_200 = {"start": 51, "emit": 144, "bump": 5}
#: Each program's start-up on the normal core, to its first stop in the program, with room to
#: spare: the normal core runs it far slower than the dynamic one its conf names.
DOS_REAL16_BOOT_S = 110
DPMI_BOOT_S = 100
BOOT_EXEMPT = "a program's start-up on the normal core can outlast the matrix's ceiling"
#: How many `_tick` windows the DPMI guest is given to produce one its join places whole: a window
#: can cross a stretch outside the client's code selector (a BIOS handler the DPMI host reflects),
#: whose lines get no linear address by design, and the next stop's window then judges again.
DPMI_WINDOWS = 3
#: The instructions a DPMI guest window takes from `_tick`: few enough to stay in the client's own
#: code, since its loop calls the BIOS through the DPMI host soon after, and a window that runs
#: into the host's real-mode stretch places no line at all.
DPMI_WINDOW = 16
DOS_REAL16_CELLS = ("K dos-real16, normal core: COMPOSE_FRAME's row starts at its own linear, 500 "
                "executed", "K dos-real16: the same window in long is placed whole")
DPMI_CELLS = ("K the DPMI guest, normal core: _tick's row starts at its own linear, "
              "through a selector base that is not zero",
              "K the DPMI guest: the same window in long is placed whole")

K_CELLS = cells(
    ("K build_check says heavy_debug before any start", "build_check docstring: heavy_debug"),
    *[(f"K {shape} at the settle loop: ECX {PER_SHAPE} lower, {PER_SHAPE} executed at one "
       f"address, {PER_SHAPE + 1} lines", "trace docstring; known: the probe's settle loop")
      for shape in tracing.SHAPES],
    ("K instructions=0 is refused", "trace docstring: 1 to the bound"),
    ("K instructions one past the bound is refused", "trace docstring: 1 to the bound"),
    ("K instructions=2**31 is refused", "trace docstring: 1 to the bound"),
    ("K an unknown shape is refused", "trace docstring: the four shapes"),
    ("K a relative dest is refused", "trace docstring: an absolute dest"),
    ("K a dest already there is refused and kept", "trace docstring: not there yet"),
    ("K a dest in the working directory is refused", "trace docstring: outside the working "
     "directory"),
    ("K debug LOG 10 is refused naming trace", "REFERENCE.md, The debugger channel"),
    ("K perform runs a trace step", "REFERENCE.md, Sequences in one call"),
    ("K no dest: trace-1 then trace-2 in the captures directory",
     "trace docstring: the next free trace-<n>.trace"),
    ("K a breakpoint cuts a trace: OTHER_STOP, the instructions equal to ECX",
     "trace docstring: OTHER_STOP; known: the loop ends when ECX reaches zero"),
    ("K after the cut the next trace is whole", "REFERENCE.md, Advancing the machine: the cut"),
    ("K a bound that runs out interrupts the trace: TIMEOUT, what ran collected, the log closed",
     "trace docstring: TIMEOUT, the run interrupted where it stood"),
    ("K the next trace after an interrupted one runs whole",
     "REFERENCE.md, Advancing the machine: the expiry"),
    ("K a running guest is refused not_stopped", "trace docstring: needs the machine stopped"),
    ("K the dynamic core: no_channel naming the core, the log kept at dest",
     "trace docstring: the count is proved per call"),
    ("K no dest and no captures directory is refused naming captures_dir",
     "trace docstring: empty dest needs a captures directory"),
    ("K the start window joins to start 51, emit 144, bump 5",
     "trace docstring: symbols; known: the probe's own arithmetic over its listing's labels"),
    (DOS_REAL16_CELLS[0], "trace docstring: symbols; known: the map's COMPOSE_FRAME"),
    (DOS_REAL16_CELLS[1], "REFERENCE.md, Advancing the machine: a long line says its own mode"),
    (DPMI_CELLS[0], "REFERENCE.md, Advancing the machine: through selector CS"),
    (DPMI_CELLS[1], "REFERENCE.md, Advancing the machine: a long line says its own mode"),
)


@M.section("K", "trace: the CPU log counted in instructions, on the probe guest", K_CELLS)
def section_k() -> None:
    left = [p for p in tracing.log_places(GUEST) if p.exists()]
    if left:
        M.block_rest(f"{left[0]} is already in the guest's directory: somebody's, never touched")
        return
    r = M.call(server.build_check)
    judged("K build_check says heavy_debug before any start", reply=r,
           holds=ok(r) and r.get("heavy_debug") is True)
    captures = Path(M.fresh("-captures"))
    captures.mkdir()
    boot(flags=NORMAL_CORE_FLAGS, captures_dir=str(captures))
    settle = must(M.call(server.run_for, frames=2), "into the settle loop")
    if hexint(str(settle.get("pc")).split(":")[-1]) != SETTLE_LOOP:
        M.block_rest(f"run_for(frames=2) did not land on the settle loop: {said(settle)}")
        return
    M.setup()
    for shape in tracing.SHAPES:
        _settle_shape(shape)
    _refusals()
    r = M.call(server.debug, command="LOG 10")
    judged("K debug LOG 10 is refused naming trace", reply=r,
           holds=refused(r, "bad_argument") and "`trace`" in str(r.get("message")))
    dest = M.fresh(".trace")
    r = M.call(server.perform, steps=[{"op": "trace", "instructions": 16, "shape": "cs_ip",
                                       "dest": dest, "seconds": TRACE_S}])
    judged("K perform runs a trace step", reply=r,
           holds=ok(r) and r.get("steps_completed") == 1 and Path(dest).is_file())
    one = M.call(server.trace, instructions=16, shape="cs_ip", seconds=TRACE_S)
    two = M.call(server.trace, instructions=16, shape="cs_ip", seconds=TRACE_S)
    paths = [str((x.get("trace") or {}).get("path")) for x in (one, two)]
    M.judge("K no dest: trace-1 then trace-2 in the captures directory",
            ok(one) and ok(two) and paths == [str(captures / "trace-1.trace"),
                                              str(captures / "trace-2.trace")]
            and all(Path(p).is_file() for p in paths), f"{paths}; {said(one, 60)}")
    _cut()
    _start_join()
    _expiry()
    release_running()
    M.setup()
    r = M.call(server.trace, instructions=16, dest=M.fresh(".trace"), seconds=TRACE_S)
    judged("K a running guest is refused not_stopped", reply=r, holds=refused(r, "not_stopped"))
    must(M.call(server.close), "closing the normal-core session")
    M.setup()
    _dynamic()
    _dos_real16()
    _dpmi()


def _no_log_left() -> bool:
    return not any(p.exists() for p in tracing.log_places(GUEST))


def _ecx() -> int:
    r = must(M.call(server.registers), "the registers")
    return hexint((r.get("regs") or {}).get("ECX")) or 0


def _settle_shape(shape: str) -> None:
    before = _ecx()
    M.setup()
    dest = M.fresh(".trace")
    r = M.call(server.trace, instructions=PER_SHAPE, shape=shape, dest=dest, seconds=TRACE_S)
    found = r.get("trace") or {}
    after = hexint((r.get("regs") or {}).get("ECX"))
    lines = len(Path(dest).read_bytes().splitlines()) if Path(dest).is_file() else None
    M.judge(f"K {shape} at the settle loop: ECX {PER_SHAPE} lower, {PER_SHAPE} executed at one "
            f"address, {PER_SHAPE + 1} lines",
            ok(r) and r.get("verdict") == "ELAPSED" and found.get("instructions") == PER_SHAPE
            and found.get("addresses") == 1 and after == before - PER_SHAPE
            and lines == PER_SHAPE + 1 and _no_log_left(),
            f"ECX {before:X} -> {after if after is None else f'{after:X}'}, {lines} lines; "
            f"{said(r, 80)}")


def _refusals() -> None:
    """Each refused before anything is typed: the machine stays where it was, and no log is
    left in the guest's directory."""
    def refusal(label: str, **kw: Any) -> None:
        r = M.call(server.trace, **{"instructions": 16, "seconds": TRACE_S, **kw})
        judged(label, reply=r, holds=refused(r, "bad_argument") and _no_log_left())

    refusal("K instructions=0 is refused", instructions=0, dest=M.fresh(".trace"))
    refusal("K instructions one past the bound is refused",
            instructions=tracing.INSTRUCTIONS_MAX + 1, dest=M.fresh(".trace"))
    refusal("K instructions=2**31 is refused", instructions=2 ** 31, dest=M.fresh(".trace"))
    refusal("K an unknown shape is refused", shape="wide", dest=M.fresh(".trace"))
    refusal("K a relative dest is refused", dest="relative.trace")
    there = Path(M.fresh(".trace"))
    there.write_bytes(b"the caller's")
    r = M.call(server.trace, instructions=16, dest=str(there), seconds=TRACE_S)
    judged("K a dest already there is refused and kept", reply=r,
           holds=refused(r, "bad_argument") and there.read_bytes() == b"the caller's")
    refusal("K a dest in the working directory is refused", dest=str(GUEST / "matrix.trace"))


def _cut() -> None:
    """A breakpoint on the `dec bx` after the loop stops the trace when ECX runs out."""
    ecx = _ecx()
    cs = (must(M.call(server.registers), "CS").get("regs") or {}).get("CS")
    ref = f"{cs}:{AFTER_LOOP:04X}"
    must(M.call(server.breakpoint_at, ref=ref), "arming the dec bx")
    M.setup()
    r = M.call(server.trace, instructions=100000, shape="cs_ip", dest=M.fresh(".trace"),
               seconds=TRACE_S)
    found = r.get("trace") or {}
    M.judge("K a breakpoint cuts a trace: OTHER_STOP, the instructions equal to ECX",
            ok(r) and r.get("verdict") == "OTHER_STOP" and found.get("instructions") == ecx
            and str(r.get("cause")).startswith(f"breakpoint {ref} ") and _no_log_left(),
            f"ECX {ecx}, {found.get('instructions')} executed; {said(r, 80)}")
    must(M.call(server.declaration_clear, kind="breakpoint", ref=ref), "clearing the dec bx")
    M.setup()
    dest = M.fresh(".trace")
    r = M.call(server.trace, instructions=16, shape="cs_ip", dest=dest, seconds=TRACE_S)
    lines = len(Path(dest).read_bytes().splitlines()) if Path(dest).is_file() else None
    judged("K after the cut the next trace is whole", reply=r,
           holds=ok(r) and r.get("verdict") == "ELAPSED" and lines == 17)


def _start_join() -> None:
    """From a breakpoint on `start` (cleared first), with the guest's own listing loaded at its
    segment: the three routines in the probe's proportions, nothing unplaced."""
    cs = str((must(M.call(server.registers), "CS").get("regs") or {}).get("CS"))
    must(M.call(server.symbols_load, path=str(GUEST / "probe.sym"),
                base=f"{int(cs, 16) * 16:X}"), "loading probe.sym")
    r = _window(f"{cs}:{START:04X}", 200, "normal")
    found = r.get("trace") or {}
    rows = {s.get("symbol"): s.get("instructions") for s in found.get("symbols") or []}
    M.judge("K the start window joins to start 51, emit 144, bump 5",
            ok(r) and rows == START_200 and found.get("unplaced") == 0
            and Path(str(found.get("set_path"))).is_file(), f"{rows}; {said(r, 80)}")


def _linear_of(name: str) -> str:
    r = must(M.call(server.symbols_find, name=name), f"finding {name}")
    rows = [s for s in r.get("symbols") or [] if s.get("name") == name]
    if len(rows) != 1:
        raise RuntimeError(f"{name} is not one symbol of the table: {said(r)}")
    return str(rows[0]["addr"])


def _window(ref: str, instructions: int, shape: str) -> dict[str, Any]:
    """A trace from `ref`'s breakpoint, armed for the one stop and cleared before the trace."""
    must(M.call(server.breakpoint_at, ref=ref), f"arming {ref}")
    must(M.call(server.resume, seconds=TRACE_S), f"running to {ref}")
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), f"clearing {ref}")
    M.setup()
    return M.call(server.trace, instructions=instructions, shape=shape, dest=M.fresh(".trace"),
                  seconds=TRACE_S)


def _row(r: dict[str, Any], name: str) -> dict[str, Any]:
    return next((s for s in (r.get("trace") or {}).get("symbols") or []
                 if s.get("symbol") == name), {})


def _bench_ready(program: bp.Program, labels: tuple[str, ...]) -> bool:
    """Whether `program` can be traced, or its cells BLOCKED: a copy absent or off its pin, or a
    log already in its working directory (somebody's, never touched)."""
    left = [p for p in tracing.log_places(program.root) if p.exists()]
    reason = bp.missing(program) or (
        f"{left[0]} is already there: somebody's, never touched" if left else "")
    if reason:
        for label in labels:
            M.block(label, reason)
    return not reason


def _judge_rest(labels: tuple[str, ...], judged_ones: set[str], exc: Exception) -> None:
    """A bench that failed part-way fails its own cells, not the other bench's."""
    for label in labels:
        if label not in judged_ones:
            M.judge(label, False, f"the bench stopped first: {type(exc).__name__}: {exc}")


def _dos_real16() -> None:
    if not _bench_ready(bp.DOS_REAL16, DOS_REAL16_CELLS):
        return
    done: set[str] = set()
    try:
        dos_real16_main_loop(wait=DOS_REAL16_BOOT_S, exempt=BOOT_EXEMPT, flags=NORMAL_CORE_FLAGS)
        own = _linear_of("COMPOSE_FRAME")
        r = _window("COMPOSE_FRAME", 500, "cs_ip")
        row = _row(r, "COMPOSE_FRAME")
        M.judge(DOS_REAL16_CELLS[0], ok(r) and (r.get("trace") or {}).get("instructions") == 500
                and row.get("first") == own, f"COMPOSE_FRAME at {own}: {row}; {said(r, 80)}")
        done.add(DOS_REAL16_CELLS[0])
        r = _window("COMPOSE_FRAME", 500, "long")
        row = _row(r, "COMPOSE_FRAME")
        M.judge(DOS_REAL16_CELLS[1], ok(r) and row.get("first") == own
                and tracing.NO_LINEAR not in str((r.get("trace") or {}).get("note")),
                f"{row}; {said(r, 80)}")
        done.add(DOS_REAL16_CELLS[1])
    except Exception as exc:  # noqa: BLE001 -- the other bench still runs; this one says why
        _judge_rest(DOS_REAL16_CELLS, done, exc)
    finally:
        M.call(server.declaration_clear, kind="breakpoint", all=True)
        M.call(server.close)


def _dpmi() -> None:
    done: set[str] = set()
    try:
        stop, loaded = dpmi_client(wait=DPMI_BOOT_S, exempt=BOOT_EXEMPT, flags=NORMAL_CORE_FLAGS)
        must(stop, "the DPMI client's first INT 31h")
        base = must(loaded, "dpmi.sym off CS").get("base")
        must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing INT 31h")
        own = _linear_of("_tick")
        seen: list[str] = []
        joined = False
        for _ in range(DPMI_WINDOWS):
            r = _window("_tick", DPMI_WINDOW, "cs_ip")
            row = _row(r, "_tick")
            note = str((r.get("trace") or {}).get("note"))
            joined = ok(r) and row.get("first") == own and tracing.NO_LINEAR not in note
            seen.append(f"{row.get('first')} {note[:60]}")
            if joined or tracing.NO_LINEAR not in note:
                break
        M.judge(DPMI_CELLS[0], joined and isinstance(base, int) and base != 0,
                f"_tick at {own}, base {base}: {seen}")
        done.add(DPMI_CELLS[0])
        r = _window("_tick", DPMI_WINDOW, "long")
        row = _row(r, "_tick")
        M.judge(DPMI_CELLS[1], ok(r) and row.get("first") == own
                and tracing.NO_LINEAR not in str((r.get("trace") or {}).get("note")),
                f"{row}; {said(r, 80)}")
        done.add(DPMI_CELLS[1])
    except Exception as exc:  # noqa: BLE001 -- a bench's failure is its own cells' verdict
        _judge_rest(DPMI_CELLS, done, exc)
    finally:
        M.call(server.declaration_clear, kind="breakpoint", all=True)
        M.call(server.close)


def _expiry() -> None:
    """The bound runs out with the log running: the run is interrupted where it stands, what
    ran is collected as a TIMEOUT, the log closed and nothing left in the guest's directory, so
    the next trace runs whole."""
    r = M.call(server.trace, instructions=tracing.INSTRUCTIONS_MAX, shape="cs_ip",
               dest=M.fresh(".trace"), seconds=1)
    judged("K a bound that runs out interrupts the trace: TIMEOUT, what ran collected, the log "
           "closed", reply=r,
           holds=ok(r) and r.get("verdict") == "TIMEOUT"
           and int((r.get("trace") or {}).get("instructions") or 0) > 0 and _no_log_left())
    M.setup()
    dest = M.fresh(".trace")
    r = M.call(server.trace, instructions=16, shape="cs_ip", dest=dest, seconds=TRACE_S)
    lines = len(Path(dest).read_bytes().splitlines()) if Path(dest).is_file() else None
    judged("K the next trace after an interrupted one runs whole", reply=r,
           holds=ok(r) and r.get("verdict") == "ELAPSED" and lines == 17 and _no_log_left())


def _dynamic() -> None:
    boot(flags=DYNAMIC_CORE_FLAGS)
    must(M.call(server.run_for, frames=2), "into the settle loop, dynamic core")
    M.setup()
    dest = M.fresh(".trace")
    r = M.call(server.trace, instructions=16, dest=dest, seconds=TRACE_S)
    judged("K the dynamic core: no_channel naming the core, the log kept at dest", reply=r,
           holds=refused(r, "no_channel") and "cpu core=normal" in str(r.get("message"))
           and (r.get("trace") or {}).get("path") == dest and Path(dest).is_file()
           and _no_log_left())
    r = M.call(server.trace, instructions=16, seconds=TRACE_S)
    judged("K no dest and no captures directory is refused naming captures_dir", reply=r,
           holds=refused(r, "bad_argument") and "captures_dir" in str(r.get("message")))
    must(M.call(server.close), "closing the dynamic-core session")
