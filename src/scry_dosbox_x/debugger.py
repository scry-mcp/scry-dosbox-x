"""The debugger over its channel: one command and the lines it printed, and the survey a stop
is read through (`Session` delegates here; `run_state` asks `RUNSTATE`). Every reading is a
command that PRINTS its answer (`EXEC`): the debugger's screen reaches no client."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scry_core import cancel
from scry_core.reply_contract import Invalid

from scry_dosbox_x import control, grammar

if TYPE_CHECKING:
    from scry_dosbox_x import session as ds

#: `debug_mcp.cpp`'s `MAX_CAPTURE_LINES`: past it a reply's lines are dropped and counted.
CAPTURE_LINES = 16384
DISCARDED = re.compile(r"^\[(\d+) debug output lines discarded\]$")
NOT_RECOGNIZED = "*** Debugger command not recognized"

RUNSTATE = "RUNSTATE"
RUNSTATE_LINE = re.compile(r"^DEBUG: RUNSTATE (stopped|running) cycles=(\d+) ms=(\d+\.\d+)"
                           r"(?: frames=(\d+))?(?: bpif=([0-9A-F]+))?$")
NO_FRAMES_WHY = (f"this build's `{RUNSTATE}` prints no `frames=`, the count of display frames "
                 f"since power-on")
NORMAL_CORE_CYCLES = "the cycle count counts only what the normal core runs"
COMMANDS_SECTION = "REFERENCE.md, Debugger commands"

#: The survey's one `EV`: every register a stop reply carries, then the flags and CR0.
SURVEY_NAMES = (*grammar.REGISTER_NAMES, "EFLAGS", "CR0")
CR0_PE, CR0_PG, EFLAGS_VM = 1, 1 << 31, 1 << 17


def typed_hex(value: int, width: int = 0) -> str:
    """A debugger number: a bare `AF` is read as a name."""
    text = f"{value:0{width}X}"
    return f"0{text}" if text[0] in "ABCDEF" else text


def typed_addr(seg: int, off: int, off_width: int = 4) -> str:
    """`seg:off` as the debugger is typed it: each half a number, never a loaded symbol's name."""
    return f"{typed_hex(seg, 4)}:{typed_hex(off, off_width)}"


def exec_lines(session: ds.Session, command: str,
               seconds: float | None = None) -> tuple[bool, list[str]]:
    """`EXEC command`: whether the debugger took it, and every line it printed. A reply cut at
    the channel's capture cap is refused: a listing with a hole in it is no reading."""
    ok, lines = session.control.request(f"EXEC {command}", seconds or control.REPLY_S,
                                        poll=cancel.check)
    cut = DISCARDED.match(lines[-1]) if lines else None
    if cut is not None:
        raise Invalid("unexpected_answer",
            f"`{command}` printed more than the {CAPTURE_LINES} lines the debugger channel "
            f"keeps of one reply, and {cut.group(1)} were dropped: what came back is cut, so "
            f"it is not a reading")
    return ok, lines


def missing(command: str, what: str) -> Invalid:
    """The refusal for a build whose debugger lacks `command`."""
    return Invalid("no_channel",
        f"{what} needs the debugger's `{command}` command, and this build's debugger has none "
        f"({COMMANDS_SECTION}); `start`'s reply lists the ones it has as `debugger_commands`")


def _ev(session: ds.Session, names: tuple[str, ...]) -> dict[str, int]:
    """`EV` of `names`, by name: the debugger prints the values in hex on one line."""
    ok, lines = exec_lines(session, "EV " + " ".join(names))
    values = lines[-1].split() if ok and lines else []
    if len(values) != len(names) or not all(re.fullmatch(r"[0-9a-fA-F]+", v) for v in values):
        raise Invalid("unexpected_answer",
            f"`EV` of {len(names)} names answered {' / '.join(lines) or 'nothing'}, not one "
            f"value for each")
    return {name: int(value, 16) for name, value in zip(names, values, strict=True)}


def _spelled(name: str, value: int) -> str:
    return f"{value:04X}" if name in grammar.SEGMENT_NAMES else f"{value:08X}"


def survey(session: ds.Session) -> tuple[dict[str, str], dict[str, str], bool]:
    """Where a stopped machine is, its registers and whether paging is on: one `EV`, plus
    `SELINFO CS` in protected mode, whose code size the window's `Pr16`/`Pr32` is."""
    got = _ev(session, SURVEY_NAMES)
    registers = {name: _spelled(name, got[name]) for name in grammar.REGISTER_NAMES}
    paging = bool(got["CR0"] & CR0_PG)
    if not got["CR0"] & CR0_PE:
        mode = grammar.REAL_MODE
    elif got["EFLAGS"] & EFLAGS_VM:
        mode = grammar.V86_MODE
    else:
        mode = "Pr32" if session.selector("CS")["big"] else "Pr16"
    where = {"cs": registers["CS"], "eip": registers["EIP"], "mode": mode}
    return where, registers, paging
