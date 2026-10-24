"""Phase 6, the sequence (`perform`) against a REAL DJGPP guest: one call runs a list of
the server's own operations, and `perform`'s resume-boundary carries it across the run to
the breakpoint it was heading for.

This is the "one call" shape the plan is measured against, minus the keystroke: reach the
client, then a SINGLE `perform` that loads symbols, declares a show watch and a breakpoint
BY NAME, and resumes. `perform` waits for the stop the resume was heading for
and hands back the ENRICHED reply at it -- the watch evaluated, the attribution naming the
symbol. R1's full CUE A sequence adds `send_keys`, which is deferred behind the driver
design, so this proves everything the sequence does that needs no keystroke.

It runs on the package's DPMI guest, and SHARES `reach_djgpp` with the stop-reply case.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import reach_djgpp

import dosbox_x_server as server

pytestmark = pytest.mark.live


def test_a_perform_sequence_runs_by_name_and_stops_where_it_was_headed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reach the client, then ONE `perform`: load the symbols, add a show watch and a
    breakpoint BY NAME, resume. The sequence runs the steps in order; the resume leaves the
    machine running, so `perform` WAITS for the stop the breakpoint produces
    and returns the enriched reply at it -- the watch read to a value, the attribution
    naming the symbol. The steps say only names; the server did the seg:off and mode work."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    reach_djgpp(logfile=str(tmp_path / "guest.log"))

    # THE SEQUENCE CLEARS THE WALK'S INTERRUPT FIRST. reach_djgpp leaves `BPINT 31 AH=00`
    # armed (its docstring says so), so a bare resume would stop at the next DPMI interrupt,
    # not at the caller's breakpoint. Clearing it by name is
    # the interrupt-clear, and it is why the two pieces belong together: a
    # clean sequence to a code breakpoint needs the walk's interrupt gone.
    steps: list[dict[str, Any]] = [
        {"op": "symbols_load", "path": str(guest.SYM)}]
    for name in guest.WATCHES:
        steps.append({"op": "watch_add", "ref": name, "mode": "show", "length": 4, "fmt": "i32"})
    steps.append({"op": "breakpoint_clear", "ref": "BPINT 31 AH=00"})   # the walk's interrupt
    steps.append({"op": "breakpoint_at", "ref": guest.STOP})
    steps.append({"op": "resume"})

    out = cast(dict[str, Any], server.perform(steps=steps, settle_seconds=120.0))
    assert out["status"] == "ok", out
    assert out["failed_at"]["available"] is False, out
    assert [s["op"] for s in out["ran"]][-1] == "resume", out

    # THE STOP AT THE USER'S BREAKPOINT, whether the resume halted there itself or the tail
    # waited for it: the enriched reply is on the resume's own reply when it halted at once,
    # else in `out["stopped"]`. Read whichever carries the attribution.
    resume_reply = out["ran"][-1]["reply"]
    stop = out.get("stopped") or resume_reply
    assert stop["cause"].startswith(f"breakpoint {guest.STOP} "), stop["cause"]
    watched = {x["ref"]: x for x in stop["watches"]}
    for name in guest.WATCHES:
        assert watched[name]["state"] == "evaluated" and "value" in watched[name], watched[name]
