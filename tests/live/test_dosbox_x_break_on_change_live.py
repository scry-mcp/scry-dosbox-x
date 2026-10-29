from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import REAL_PROGRAM, reach_realmode

import dosbox_x_server as server

pytestmark = pytest.mark.live

# BIOS timer tick.
WATCH = "0040:006C"


@REAL_PROGRAM
def test_a_real_mode_change_watch_stops_the_machine_when_the_memory_changes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real-mode change-watch stops the machine."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    assert load_seg >= 0

    w = cast(dict[str, Any], server.watch_add(ref=WATCH, mode="change", length=2, fmt="u16"))
    assert w["status"] == "ok" and w["armed"] is True, w
    assert "caveat" not in w, w

    # reach_realmode left INT 21 armed.
    server.declaration_clear("breakpoint", all=True)

    out = cast(dict[str, Any], server.resume(seconds=30))
    assert out["status"] == "ok", out
    assert "pc" in out, (
        "a real-mode change-watch on memory that is changing did not stop the machine: "
        f"{out.get('session')}")
    assert out["cpu_mode"] == "real", out
    # Stops at the writing instruction, not the watched address.
    assert isinstance(out.get("regs"), dict) and out["regs"], out
    assert out["cause"].startswith("no declared code breakpoint"), out["cause"]
