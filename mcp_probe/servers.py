"""This repository's MCP server, loaded without starting anything, as `scry_core.probe` reads it:

    uv run python -m scry_core.probe dosbox-x --servers mcp_probe/servers.py --tasks mcp_probe/tasks

The cap test and the probe read the SAME object the suite imports as `dosbox_x_server`, so a text
measured under the cap is the text a model was probed with, and the shape guard wraps the one copy
there is.
"""

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: The servers whose real runs this repository keeps, re-judged by its suite.
CAPTURED = ("dosbox-x",)


def load() -> dict[str, ModuleType]:
    """The server's MODULE by its registered name: `.mcp` is the server, and each tool is the
    module attribute of the same name.

    A test calls this at COLLECTION, never inside a test body: the root conftest's shape guard
    wraps every server module in `sys.modules` once collection ends, and fails on one imported
    after it."""
    return {"dosbox-x": importlib.import_module("dosbox_x_server")}


def _dosbox_check(tool: str, given: dict[str, Any], effective: dict[str, Any]) -> None:
    """dosbox-x's wrapper calls `check` with the arguments the caller GAVE: so does this."""
    import dosbox_checks

    dosbox_checks.check(tool, **given)


CHECKS = {"dosbox-x": _dosbox_check}
