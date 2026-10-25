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
    return [found, "-defaultconf", "-fastlaunch", "-set", "sdl videodriver=dummy", "-exit"]


# Compiled only under `C_HEAVY_DEBUG`. Read from bytes: an unknown command poisons input.
HEAVY_DEBUG_MARK = b"LOGS/LOGL/LOGC [num]"
# Compiled only with `C_DEBUG`; `-helpdebug` lists `-break-start` regardless.
DEBUGGER_MARK = b"Debugger command not recognized"


_marks_seen: dict[tuple[str, int, int, bytes], bool] = {}


def _carries(binary: str, mark: bytes, what: str) -> bool:
    """Whether the build holds `mark`; cached by path, size, mtime."""
    real = os.path.realpath(binary)
    try:
        st = os.stat(real)
        key = (real, st.st_size, st.st_mtime_ns, mark)
        if key not in _marks_seen:
            _marks_seen[key] = mark in Path(real).read_bytes()
    except OSError as exc:
        raise Invalid("host_failed", f"{real} could not be read to see whether it carries "
                      f"{what}: {exc!r}") from None
    return _marks_seen[key]


def heavy_debug(binary: str) -> bool:
    """Whether the build at `binary` carries the CPU log."""
    return _carries(binary, HEAVY_DEBUG_MARK, "the CPU log")


def debugger(binary: str) -> bool:
    """Whether the build at `binary` carries the debugger."""
    return _carries(binary, DEBUGGER_MARK, "the debugger")
