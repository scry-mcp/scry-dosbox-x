"""Declared ends equal REFERENCE's table."""

from __future__ import annotations

import sys
from pathlib import Path

from scry_core import ends_table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scry_dosbox_x import mcp as dosbox_mcp  # noqa: E402
from scry_dosbox_x import server as dosbox_x_server  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent


def test_the_table_of_ends_is_the_declared_ends() -> None:
    declared = dosbox_mcp.BOUNDARY.declared_ends
    assert declared, "no tool is registered, so nothing was compared"
    assert ends_table.unlike((ROOT / "REFERENCE.md").read_text(), declared) == {}
