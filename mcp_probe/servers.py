"""This repository's MCP server, loaded without starting anything, as `scry_core.probe` reads it:

    uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py --tasks mcp_probe/tasks

The cap test and the probe read the SAME object the suite imports as `dosbox_x_server`, so a text
measured under the cap is the text a model was probed with, and the shape guard wraps the one copy
there is.
"""

from pathlib import Path
from types import ModuleType

import dosbox_checks
import dosbox_x_server

ROOT = Path(__file__).resolve().parent.parent
#: The servers whose real runs this repository keeps, re-judged by its suite.
CAPTURED = ("dosbox-x",)


def load() -> dict[str, ModuleType]:
    """The server's module by its registered name (`scry_core.probe_checks` says how)."""
    return {"dosbox-x": dosbox_x_server}


CHECKS = {"dosbox-x": dosbox_checks.probe_check}
