"""A stub DOSBox-X build carrying the debugger's mark."""

from __future__ import annotations

from pathlib import Path

from scry_core import host_program

import dosbox_binary as binaries

BANNER = "DOSBox-X version 0.0.0 SDL2, a stub build"


def build(where: Path, *, version: str = f"sys.stderr.write({BANNER!r}); sys.exit(1)",
          helpdebug: str = "print('-break-start')", name: str = "dosbox-x") -> Path:
    """`version`, `helpdebug`: the Python answering each option."""
    mark = binaries.DEBUGGER_MARK.decode()
    exe = host_program.write(where / name, f"# {mark}\nimport os, sys\n"
                             f"if sys.argv[1:2] == ['-version']:\n    {version}\n"
                             f"if sys.argv[1:2] == ['-helpdebug']:\n    {helpdebug}\n")
    if exe.suffix == ".cmd":           # read from the file the host runs
        with exe.open("a", encoding="utf-8") as fh:
            fh.write(f"rem {mark}\r\n")
    return exe
