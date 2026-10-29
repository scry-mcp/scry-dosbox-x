"""The enriched stop reply against real programs: registers, watches, `cause`, E9 block."""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from scry_core.log_marks import STOP_LINES_SHOWN
from test_dosbox_x_entry_routes import (
    REAL_PROGRAM,
    REAL_VARIABLE,
    reach_djgpp,
    reach_realmode,
    real_address,
)

import dosbox_x_server as server
from dosbox_logs import LOG_LIMIT_MAX

pytestmark = pytest.mark.live

STOP_WAIT_S = 120.0     # how long the DJGPP case waits for its breakpoint once the guest runs


@REAL_PROGRAM
def test_a_stop_carries_the_registers_watches_attribution_and_e9(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real-mode stop carries registers, an evaluated show watch, a cause and the E9 shape."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    # No logfile on purpose: the E9 block under test is the unavailable shape.
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    watch = real_address(load_seg, REAL_VARIABLE)
    assert load_seg >= 0

    w = cast(dict[str, Any], server.watch_add(ref=watch, mode="show", length=4, fmt="u32"))
    assert w["status"] == "ok" and w["mode"] == "show", w

    out = cast(dict[str, Any], server.resume(seconds=30))
    assert out["status"] == "ok" and "pc" in out, out
    assert isinstance(out.get("regs"), dict) and out["regs"], out

    watched = {x["ref"]: x for x in out["watches"]}
    assert watch in watched, out
    assert watched[watch]["state"] == "evaluated" and "value" in watched[watch], watched[watch]

    assert isinstance(out["cause"], str), out                  # named, or an honest no
    assert out["e9"]["available"] is False, out["e9"]
    assert "started without a logfile" in out["e9"]["why"], out["e9"]


def test_a_djgpp_stop_returns_named_globals_together_with_the_e9_block(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A DPMI stop at a named breakpoint carries named watches and a served, bounded E9 block."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    reach_djgpp(logfile=str(tmp_path / "guest.log"))
    load = cast(dict[str, Any], server.symbols_load(path=str(guest.SYM)))
    assert load["status"] == "ok", load
    for name in guest.WATCHES:
        w = cast(dict[str, Any], server.watch_add(ref=name, mode="show", length=4, fmt="i32"))
        assert w["status"] == "ok" and w["state"] == "evaluated", w
    bp = cast(dict[str, Any], server.breakpoint_at(ref=guest.STOP))
    assert bp["status"] == "ok" and bp["armed"] is True, bp
    gone = cast(dict[str, Any], server.declaration_clear("breakpoint", ref="BPINT 31 AH=00"))
    assert gone["status"] == "ok", gone

    ran = cast(dict[str, Any], server.perform(steps=[{"op": "resume"}],
                                                settle_seconds=STOP_WAIT_S))
    assert ran["status"] == "ok" and ran["failed_at"]["available"] is False, ran
    out = cast(dict[str, Any], ran.get("stopped") or ran["ran"][-1]["reply"])
    assert str(out.get("cause")).startswith(f"breakpoint {guest.STOP} "), out
    assert isinstance(out["regs"], dict) and out["regs"], out
    watched = {x["ref"]: x for x in out["watches"]}
    for name in guest.WATCHES:
        assert name in watched, out
        assert watched[name]["state"] == "evaluated", watched[name]
        assert isinstance(watched[name]["value"], int), watched[name]
    blk = out["e9"]
    assert blk["lines_total"] > 0, f"the program was to have logged before {guest.STOP}: {blk}"
    assert blk["lines"] and len(blk["lines"]) <= min(blk["lines_total"], STOP_LINES_SHOWN), blk
    assert blk["truncated"] is (blk["lines_total"] > STOP_LINES_SHOWN), blk
    # The cut block's `how` must be a sendable call.
    if blk["truncated"]:
        got = cast(dict[str, Any], server.log(pattern=".", channel="guest",
                                              since_mark=blk["mark"], limit=LOG_LIMIT_MAX))
        assert got["status"] == "ok" and blk["how"].startswith("`log(pattern="), (blk, got)
        assert got["lines"][-len(blk["lines"]):] == blk["lines"], (got, blk)

    on = cast(dict[str, Any], server.step(mode="over"))
    assert on["status"] == "ok" and on["e9"]["mark"] >= blk["mark"], on
