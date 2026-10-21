"""Which DOSBox-X a session runs: scry-core's ladder (`scry_core.binaries`) with this server's
rungs, climbed once per `start` or `build_check`; the canary that proves the host can start it;
and whether the build carries the debugger and the CPU log, read off its own bytes.
"""

from __future__ import annotations

import os
from pathlib import Path

from scry_core import binaries
from scry_core.reply_contract import Invalid

#: The ladder is scry-core's (`scry_core.binaries`); this server names its rungs. The executable
#: name is also what a `ps` line of a session started with no `binary` carries.
LADDER = binaries.Ladder(product="DOSBox-X", executable="dosbox-x", variable="DOSBOX_X_BINARY")
EMULATOR_NAME, VARIABLE = LADDER.executable, LADDER.variable
ARGUMENT, PATH_RUNG = binaries.ARGUMENT, binaries.PATH_RUNG
Resolved = binaries.Resolved
resolve = LADDER.resolve
why_not, version, facts = binaries.why_not, binaries.version, binaries.facts
VERSION_TIMEOUT_S = binaries.VERSION_TIMEOUT_S


def canary_for(binary: str = "") -> list[str] | None:
    """The DOSBox-X the ladder resolves for `binary`, in a form that initialises SDL as a
    headless session does and ENDS BY ITSELF: the built-in conf, no window, `-exit` once its
    autoexec (which runs nothing) is done (`scry_core.live_host.canary`). None when nothing
    resolves: the session's own `start` refuses that, naming the ladder."""
    try:
        found = resolve(binary).path
    except Invalid:
        return None
    return [found, "-defaultconf", "-fastlaunch", "-set", "sdl videodriver=dummy", "-exit"]


# THE HELP LINE THE DEBUGGER COMPILES ONLY UNDER `C_HEAVY_DEBUG`, beside the `LOG` family it
# documents: a build that carries it has the CPU log. Read off the binary's bytes, never by
# typing `LOG` to find out (a command the debugger does not know poisons its input line).
HEAVY_DEBUG_MARK = b"LOGS/LOGL/LOGC [num]"
# AND THE DEBUGGER'S OWN ANSWER to a command it does not know, compiled only with `C_DEBUG`: a
# build configured `--disable-debug` still lists `-break-start` in `-helpdebug` (the option
# parser is there either way), so the help text alone cannot say the debugger is.
DEBUGGER_MARK = b"Debugger command not recognized"


_marks_seen: dict[tuple[str, int, int, bytes], bool] = {}


def _carries(binary: str, mark: bytes, what: str) -> bool:
    """Whether the build at `binary` holds `mark`, cached per (real path, size, mtime) so a
    rebuilt binary is read again."""
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
