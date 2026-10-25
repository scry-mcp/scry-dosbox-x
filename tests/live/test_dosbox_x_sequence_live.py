"""One `perform` sequence against a real DJGPP guest."""
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
    """The sequence stops at its named breakpoint with the enriched reply."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    reach_djgpp(logfile=str(tmp_path / "guest.log"))

    # reach_djgpp leaves `BPINT 31 AH=00` armed; a resume would stop there.
    steps: list[dict[str, Any]] = [
        {"op": "symbols_load", "path": str(guest.SYM)}]
    for name in guest.WATCHES:
        steps.append({"op": "watch_add", "ref": name, "mode": "show", "length": 4, "fmt": "i32"})
    steps.append({"op": "declaration_clear", "kind": "breakpoint",
                  "ref": "BPINT 31 AH=00"})
    steps.append({"op": "breakpoint_at", "ref": guest.STOP})
    steps.append({"op": "resume"})

    out = cast(dict[str, Any], server.perform(steps=steps, settle_seconds=120.0))
    assert out["status"] == "ok", out
    assert out["failed_at"]["available"] is False, out
    assert [s["op"] for s in out["ran"]][-1] == "resume", out

    resume_reply = out["ran"][-1]["reply"]
    stop = out.get("stopped") or resume_reply
    assert stop["cause"].startswith(f"breakpoint {guest.STOP} "), stop["cause"]
    watched = {x["ref"]: x for x in stop["watches"]}
    for name in guest.WATCHES:
        assert watched[name]["state"] == "evaluated" and "value" in watched[name], watched[name]
