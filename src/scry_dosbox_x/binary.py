from __future__ import annotations

import os
from pathlib import Path

from scry_core import binaries
from scry_core.reply_contract import Invalid

#: `ps` shows this name when `start` gets no `binary`.
LADDER = binaries.Ladder(product="DOSBox-X", executable="dosbox-x", variable="DOSBOX_X_BINARY")
EXECUTABLE_NAME, VARIABLE = LADDER.executable, LADDER.variable
ARGUMENT, PATH_RUNG = binaries.ARGUMENT, binaries.PATH_RUNG
Resolved = binaries.Resolved
resolve = LADDER.resolve
why_not, version, facts = binaries.why_not, binaries.version, binaries.facts
VERSION_TIMEOUT_S = binaries.VERSION_TIMEOUT_S


def canary_for(binary: str = "") -> list[str] | None:
    """Argv of a headless DOSBox-X that exits by itself; None if unresolved."""
    try:
        found = resolve(binary).path
    except Invalid:
        return None
    return [found, "-defaultconf", "-fastlaunch", NO_FOLDER_PROMPT, "-set",
            "sdl videodriver=dummy", "-exit"]


#: On every launch: else a macOS build asks for its folder in a dialog SIGTERM cannot end.
NO_FOLDER_PROMPT = "-nopromptfolder"

# Compiled only under `C_HEAVY_DEBUG`. Read from bytes: an unknown command poisons input.
HEAVY_DEBUG_MARK = b"LOGS/LOGL/LOGC [num]"
# Compiled only with `C_DEBUG`; `-helpdebug` would list `-break-start` regardless.
DEBUGGER_MARK = b"Debugger command not recognized"
#: Commands a build may lack, found as the parser's NUL-bounded literals, not the help text's.
COMMANDS = ("RUNSTATE", "STEPIN", "SAVESTATE", "LOADSTATE", "PRESENCE", "VGAMEMDUMP", "BPIF",
            "CAPTURE", "TAP", "PORTINFO", "DOSTRACE", "PIC", "A20", "MEMDUMPLIN")
#: The tools a build without the command cannot serve, as REFERENCE.md's command table says.
DISABLES = {
    "RUNSTATE": ("run_to", "run_for", "trace", "screen_wait", "step (mode over)",
                 "resume (with a bound)", "input to a stopped machine", "readings after a release"),
    "STEPIN": ("step",),
    "SAVESTATE": ("state_write",),
    "LOADSTATE": ("state_write",),
    "PRESENCE": ("the presence indicator",),
    "VGAMEMDUMP": ("screen_view and screen_signature in a planar, unchained or linear mode",),
    "BPIF": ("regpoint_add",),
    "CAPTURE": ("record", "audio_record"),
    "TAP": ("watch_add (mode count or capture)",),
    "PORTINFO": ("port",),
    "DOSTRACE": ("log and log_wait on the dos channel", "start (dos_calls)"),
    "PIC": ("pic",),
    "A20": ("a20",),
    "MEMDUMPLIN": ("reads by linear address", "send_mouse steering a protected-mode pointer"),
}
#: Bare names a release also carries for something else: found by a literal only the command has.
USAGE_MARKS = {name: b"\0DEBUG: " + name.encode() + b" usage: " for name in ("CAPTURE", "TAP")}
USAGE_MARKS |= {"PIC": b"\0MASKIRQ\0", "A20": b"A20 gate is %s"}
#: The debugger with no screen, which needs no terminal or console.
HEADLESS_MARK = b"\0debugger headless\0"


def command_mark(name: str) -> bytes:
    return USAGE_MARKS.get(name, b"\0" + name.encode() + b"\0")


MARKS = (HEAVY_DEBUG_MARK, DEBUGGER_MARK, HEADLESS_MARK, *(command_mark(n) for n in COMMANDS))


_marks_seen: dict[tuple[str, int, int], frozenset[bytes]] = {}


def _carries(binary: str, mark: bytes, what: str) -> bool:
    """Whether the build holds `mark`; all marks are read in one pass, cached by path and stat."""
    real = os.path.realpath(binary)
    try:
        st = os.stat(real)
        key = (real, st.st_size, st.st_mtime_ns)
        if key not in _marks_seen:
            data = Path(real).read_bytes()
            _marks_seen[key] = frozenset(m for m in MARKS if m in data)
    except OSError as exc:
        raise Invalid("host_failed", f"{real} could not be read to see whether it carries "
                      f"{what}: {exc!r}") from None
    return mark in _marks_seen[key]


def heavy_debug(binary: str) -> bool:
    return _carries(binary, HEAVY_DEBUG_MARK, "the CPU log")


def debugger(binary: str) -> bool:
    return _carries(binary, DEBUGGER_MARK, "the debugger")


def debugger_headless(binary: str) -> bool:
    return _carries(binary, HEADLESS_MARK, "`debugger headless`")


def debugger_commands(binary: str) -> list[str]:
    """Which of `COMMANDS` the build's debugger parses, in `COMMANDS`' order."""
    return [name for name in COMMANDS
            if _carries(binary, command_mark(name), f"the `{name}` command")]


def debugger_commands_missing(found: list[str]) -> list[dict[str, object]]:
    """Each of `COMMANDS` not in `found`, with the tools it takes away."""
    return [{"command": name, "disables": list(DISABLES[name])}
            for name in COMMANDS if name not in found]
