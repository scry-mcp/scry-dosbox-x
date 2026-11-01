"""Section S of the live matrix: a build whose debugger carries none of the optional commands, the
release named by `DOSBOX_X_STOCK_BINARY`. A session starts and answers every reading at the stop
it parks at; what needs a command it lacks is refused naming it, before anything acts. Why:
REFERENCE.md, Debugger commands.
"""
from __future__ import annotations

from typing import Any

from matrix_common import (
    ENV,
    MOUSE_CONF,
    MOUSE_PROGRAM,
    M,
    boot,
    cells,
    close_whatever,
    must,
    ok,
    refused,
    said,
    server,
)
from matrix_presence import STOCK_VAR

from scry_dosbox_x.session import Session  # isort: skip -- found through the path the matrix sets

S_CELLS = cells(
    ("S build_check answers the build with none of the scry build's optional debugger commands",
     "REFERENCE.md, Debugger commands: `debugger_commands`"),
    ("S start parks the guest at the debugger",
     "REFERENCE.md, Debugger commands: a session starts"),
    ("S registers, read_memory, disassemble, machine_map and screen_view answer at the park",
     "REFERENCE.md, Debugger commands: every reading answers at the stop start leaves"),
    ("S send_keys goes in to the released guest", "REFERENCE.md, Debugger commands: input works"),
    ("S run_to, run_for, trace, screen_wait, step, regpoint_add and a bounded resume are "
     "refused naming their command, before anything acts",
     "REFERENCE.md, Debugger commands: refused `no_channel` naming it"),
    ("S resume with no bound releases, a reading after it is refused, and stop brings the "
     "machine back to readings", "REFERENCE.md, Debugger commands: stop brings it back"),
)

WAIT_S = 20
#: The debugger commands a release carries; every other one is the scry build's.
STOCK_COMMANDS = {"PIC", "A20"}
#: What each refusal names; a release built without the CPU log refuses `trace` for that first.
_NEEDS = {"run_to": ("RUNSTATE",), "run_for": ("RUNSTATE",), "trace": ("RUNSTATE", "heavy_debug"),
          "screen_wait": ("RUNSTATE",), "step": ("STEPIN",), "resume": ("RUNSTATE",),
          "regpoint_add": ("BPIF",)}


def _refused_naming(r: dict[str, Any], names: tuple[str, ...]) -> bool:
    return refused(r, "no_channel") and any(n in str(r.get("message")) for n in names)


@M.section("S", "a build with no optional debugger command, the release", S_CELLS)
def section_s() -> None:
    stock = ENV.get(STOCK_VAR, "").strip()
    if not stock:
        M.block_rest(f"{STOCK_VAR} is not set: no release build to run")
        return
    checked = M.call(server.build_check, binary=stock)
    have = set(checked.get("debugger_commands") or [])
    M.judge(S_CELLS[0].label, ok(checked) and have <= STOCK_COMMANDS, said(checked))
    started = boot(binary=stock)
    M.judge(S_CELLS[1].label, ok(started) and started["session"]["running"] is False,
            said(started))
    reads = [M.call(server.registers), M.call(server.read_memory, ref="F000:FFF0", length=16),
             M.call(server.disassemble, ref="F000:FFF0", length=5),
             M.call(server.machine_map, sections=["control"]), M.call(server.screen_view)]
    # At the reset vector no video mode is set yet: `screen_view` names its refusal.
    M.judge(S_CELLS[2].label, all(ok(r) for r in reads[:4])
            and (ok(reads[4]) or refused(reads[4], "no_channel")),
            "; ".join(said(r, 50) for r in reads))
    sent: list[str] = []
    channel = Session.exec

    def counted(self: Session, command: str, seconds: float | None = None) -> Any:
        sent.append(command)
        return channel(self, command, seconds)
    Session.exec = counted  # type: ignore[method-assign]
    try:
        asked = {"run_to": M.call(server.run_to, ref="F000:E05B", control="0000:0001",
                                       seconds=1),
                 "run_for": M.call(server.run_for, frames=1),
                 "trace": M.call(server.trace, instructions=1, dest=M.fresh(".trace"),
                                       seconds=1),
                 "screen_wait": M.call(server.screen_wait, text="C:", seconds=1),
                 "step": M.call(server.step),
                 "regpoint_add": M.call(server.regpoint_add, condition="AX==1"),
                 "resume": M.call(server.resume, seconds=1)}
    finally:
        Session.exec = channel  # type: ignore[method-assign]
    M.judge(S_CELLS[4].label, all(_refused_naming(r, _NEEDS[k]) for k, r in asked.items())
            and not [c for c in sent if c.split()[0] in ("RUN", "VRT", "LOG", "LOGC", "STEPIN")],
            "; ".join(f"{k}: {said(r, 40)}" for k, r in asked.items()) + f"; sent {sent}")
    released = M.call(server.resume)
    after = M.call(server.registers)
    stopped = M.call(server.stop)
    again = M.call(server.registers)
    M.judge(S_CELLS[5].label, ok(released) and refused(after, "no_channel")
            and "`RUNSTATE`" in str(after.get("message")) and ok(stopped) and ok(again),
            "; ".join(said(r, 40) for r in (released, after, stopped, again)))
    close_whatever()
    boot(binary=stock, conf=MOUSE_CONF, program=MOUSE_PROGRAM)
    must(M.call(server.resume), "releasing the mouse guest")
    must(M.call(server.log_wait, pattern=r"STUB  \. scry", channel="guest", seconds=WAIT_S),
         "the input stub announcing itself")
    keys = M.call(server.send_keys, keys=["a"], expect=r"MOUSE \. key=97$", seconds=WAIT_S)
    M.judge(S_CELLS[3].label, ok(keys) and keys.get("verify", {}).get("seen") is True, said(keys))
    close_whatever()
