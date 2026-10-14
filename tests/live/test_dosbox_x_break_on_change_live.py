"""Phase 6bis, break-on-change against a REAL real-mode guest (decision 5's second half).

A change-watch armed on memory the guest writes STOPS the machine when that memory changes,
in real mode (BPM). This is the example S2 the plan measures against, and it is the one
place break-on-change gets an honest LIVE proof: Phase 1 measured BPPM firing on the paging
host rather than the program under DJGPP, so protected-mode break-on-change carries a caveat
instead of a live firing test, and real mode is where it is proven.

It runs Speed Fight's copy on the bench, sharing `reach_realmode`, and watches the BIOS timer
tick at 0040:006C: it advances 18.2 times a second in real mode whatever the program is doing,
so a change-watch on it fires within a frame, which is what proves the MECHANISM (BPM stops on
a write). The program's own variables need not move while it is still loading.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import REAL_PROGRAM, reach_realmode

import dosbox_x_server as server

pytestmark = pytest.mark.live

WATCH = "0040:006C"


@REAL_PROGRAM
def test_a_real_mode_change_watch_stops_the_machine_when_the_memory_changes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reach the program's loop, arm a break-on-change watch by address, clear the walk's
    interrupt breakpoint so ONLY the watch can stop the machine, then resume and confirm it
    HALTED because the memory changed. Real mode, so BPM and no caveat.

    THE STOP IS AT THE WRITING INSTRUCTION, not at the watched address -- that is what a
    memory-change breakpoint does, and it is why the enriched reply's attribution honestly
    says it cannot name which watch fired. So this asserts the machine stopped and stayed in
    real mode, not that CS:EIP equals the watch address."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    assert load_seg >= 0

    w = cast(dict[str, Any], server.watch_add(ref=WATCH, mode="change", length=2, fmt="u16"))
    assert w["status"] == "ok" and w["armed"] is True, w
    # REAL MODE: BPM, and no protected-mode caveat.
    assert w.get("caveat") is None, w

    # Clear the walk's interrupt breakpoint (reach_realmode left INT 21 armed), so the only
    # thing that can stop the next resume is the change-watch. breakpoint_clear takes the
    # interrupt family too now.
    server.breakpoint_clear()

    out = cast(dict[str, Any], server.resume())
    assert out["status"] == "ok", out
    assert out["halted"] is True, (
        "a real-mode change-watch on memory that is changing did not stop the machine: "
        f"{out.get('stopped_at')}")
    assert out["stopped_at"]["mode"] == "Real", out
    # The stop is enriched (Phase 4): registers came back, and attribution is honest that a
    # memory watch cannot be traced from the stop to the declaration.
    assert isinstance(out.get("registers"), dict) and out["registers"], out
    assert out["attribution"]["attributed"] is False, out["attribution"]
