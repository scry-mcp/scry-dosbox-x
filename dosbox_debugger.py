"""The debugger over its channel: one command and the lines it printed, the run state, and the
survey a stop is read through. `Session` delegates here.

Every reading is a command that PRINTS its answer (`EXEC`): the debugger's screen reaches no
client of the channel. Whether the machine is stopped is the `RUNSTATE` command a build may
carry.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from scry_core import cancel
from scry_core.progress import PROGRESS_EVERY_S, Progress, no_progress
from scry_core.reply_contract import Invalid

import dosbox_control as control
import dosbox_grammar as grammar

if TYPE_CHECKING:
    import dosbox_session as ds

#: `debug_mcp.cpp`'s `MAX_CAPTURE_LINES`: past it a reply's lines are dropped and counted.
CAPTURE_LINES = 16384
DISCARDED = re.compile(r"^\[(\d+) debug output lines discarded\]$")
NOT_RECOGNIZED = "*** Debugger command not recognized"

RUNSTATE = "RUNSTATE"
RUNSTATE_LINE = re.compile(r"^DEBUG: RUNSTATE (stopped|running) cycles=(\d+) ms=(\d+\.\d+)$")
#: What `RUNSTATE`'s `cycles` holds, as every reply that leans on it says.
NORMAL_CORE_CYCLES = "the cycle count counts only what the normal core runs"
COMMANDS_SECTION = "REFERENCE.md, Debugger commands"
#: The pause between two `RUNSTATE`s of a wait, one request in flight.
POLL_PAUSE_S = 0.02

#: The survey's one `EV`: every register a stop reply carries, then the flags and CR0.
SURVEY_NAMES = (*grammar.REGISTER_NAMES, "EFLAGS", "CR0")
CR0_PE, CR0_PG, EFLAGS_VM = 1, 1 << 31, 1 << 17


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


def no_run_state(what: str) -> Invalid:
    """A tool that waits for, or reads, a stop this build cannot see."""
    return missing(RUNSTATE, f"{what} waits for the machine to stop, which")


def unknown_after_release(what: str) -> Invalid:
    """A reading of a machine released on a build that cannot say whether it stopped since."""
    return Invalid("no_channel",
        f"the machine was let run, and this build's debugger has no `{RUNSTATE}` command to say "
        f"whether it has stopped since ({COMMANDS_SECTION}), so {what} could read a moving "
        f"machine. `stop` brings it back to the debugger, wherever it is")


def read_run_state(session: ds.Session) -> bool:
    """One `RUNSTATE`: whether the machine is stopped, with the cycles and the clock it gives."""
    return take_run_state(session, *exec_lines(session, RUNSTATE))


def take_run_state(session: ds.Session, ok: bool, lines: list[str]) -> bool:
    """`RUNSTATE`'s answer read into the session: stopped, its cycles and its clock."""
    found = RUNSTATE_LINE.match(lines[-1]) if ok and lines else None
    if found is None:
        raise Invalid("unexpected_answer",
            f"`{RUNSTATE}` answered {' / '.join(lines) or 'nothing'}, not its one line "
            f"`DEBUG: RUNSTATE stopped|running cycles=<n> ms=<t>`")
    session.cycles, session.clock_ms = int(found.group(2)), float(found.group(3))
    if found.group(1) == "stopped":
        session.mark_stopped()
        return True
    session.forget_stop()
    return False


def await_stop(session: ds.Session, began: float, deadline: float, target: str,
               progress: Progress = no_progress, label: str = "",
               look_once: bool = False) -> tuple[bool, float]:
    """Ask `RUNSTATE` until the machine stops or `deadline` passes: `(expired, seconds)`;
    `look_once` asks at least once, a bound of 0 included."""
    if not session.has(RUNSTATE):
        raise no_run_state(label or f"run_to {target}")
    next_tick = began + PROGRESS_EVERY_S
    looked = not look_once
    while not looked or time.monotonic() < deadline:
        now = time.monotonic()
        cancel.check()
        if now >= next_tick:
            next_tick = now + PROGRESS_EVERY_S
            progress(now - began, None, f"{label or f'run_to {target}'}: running "
                                        f"{now - began:.0f}s of {deadline - began:g}s")
        session.gone_if_dead(began, deadline - began, target)
        looked = True
        if read_run_state(session):
            return False, round(time.monotonic() - began, 1)
        time.sleep(POLL_PAUSE_S)
    return True, 0.0


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
