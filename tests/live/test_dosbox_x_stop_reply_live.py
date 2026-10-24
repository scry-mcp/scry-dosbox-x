"""The enriched stop reply against REAL programs: a stop carries the registers, the watches
EVALUATED, its `cause`, and the E9 block, the guest's lines since the previous stop, bounded.

The real-mode case runs dos-real16's copy on the bench, as the other real-mode live files do;
the DJGPP case runs on the package's DPMI guest. It SHARES `reach_realmode` and `reach_djgpp` so it
cannot drift on how each program is reached.

TWO CASES, BECAUSE THE TWO SESSIONS PROVE DIFFERENT HALVES. The real-mode session is started
WITHOUT a logfile, so its E9 block can only be the honest `available: False` shape, naming the
missing log, and that is what the real-mode case asserts. The SERVED shape (the count whole,
the newest lines, the mark they start at, and a `log` call that reads the rest) needs a guest
that logs, which is the DPMI guest; that case also brings several globals declared by NAME
back TOGETHER on one stop.

  DOSBOX_X_WALK_MAX       ceiling on the resume-walk to the client (see the entry routes)
"""
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
    """Reach the program's own INT 21 loop, declare a show watch by address, resume to the
    next stop, and read the ENRICHED reply: the registers came back, the watch was evaluated
    to a value without being asked, the attribution is present (named or an honest cannot-say
    ), and the E9 block says why it has nothing to show."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    # WITHOUT A LOGFILE, so the E9 block under test is the unavailable one whatever build the
    # bench holds: the served shape is the DJGPP case's.
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    watch = real_address(load_seg, REAL_VARIABLE)
    assert load_seg >= 0

    # A SHOW WATCH (it arms nothing), by address so no symbol is assumed.
    w = cast(dict[str, Any], server.watch_add(ref=watch, mode="show", length=4, fmt="u32"))
    assert w["status"] == "ok" and w["mode"] == "show", w

    # reach_realmode left INT 21 armed and the guest at its loop; the next resume stops
    # again, and THAT reply is the enriched one under test.
    out = cast(dict[str, Any], server.resume())
    assert out["status"] == "ok" and "pc" in out, out
    assert isinstance(out.get("regs"), dict) and out["regs"], out

    watched = {x["ref"]: x for x in out["watches"]}
    assert watch in watched, out
    assert watched[watch]["state"] == "evaluated" and "value" in watched[watch], watched[watch]

    assert isinstance(out["cause"], str), out                  # named, or an honest no
    # NO CHANNEL, so the block is the unavailable shape and says WHY: there is no log to read.
    # The served shape is the DJGPP case's.
    assert out["e9"]["available"] is False, out["e9"]
    assert "started without a logfile" in out["e9"]["why"], out["e9"]


def test_a_djgpp_stop_returns_named_globals_together_with_the_e9_block(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R2 in the flesh, on the real DPMI program: reach its 32-bit code, load the symbols,
    declare show watches BY NAME on several globals and a breakpoint BY NAME on a function
    it calls once it has logged, then resume until THAT breakpoint is the attributed stop.
    The reply carries the registers, every watch evaluated to a value, the `cause` naming the
    symbol, and the E9 block with a positive count, the newest lines and, when cut, the `log`
    call that reads the rest; one step from there is a stop with a block of its own.

    THE WALK'S INTERRUPT IS CLEARED FIRST. `reach_djgpp` leaves `BPINT 31 AH=00` armed, and
    with it every resume stops at the runtime's next DPMI call instead of at the breakpoint:
    a guest that keeps calling the DPMI host outruns any walk bound. Clearing it by its row
    leaves the code breakpoint as the only thing that can stop the machine. And the stop is
    WAITED FOR: `resume` answers at once and says whether the machine halted, so the run to
    a breakpoint that fires later goes through `perform`, which bridges a resume to the
    stop it was heading for and hands back the enriched reply at it."""
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
    # The enriched reply sits on the resume's own reply when it halted at once, else in
    # `stopped`, written by the tail that waited for it.
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
    # THE CUT BLOCK'S `how` IS A CALL AS IT CAN BE SENT: sent, it reads the lines the stop cut.
    if blk["truncated"]:
        got = cast(dict[str, Any], server.log(pattern=".", channel="guest",
                                              since_mark=blk["mark"], limit=LOG_LIMIT_MAX))
        assert got["status"] == "ok" and blk["how"].startswith("`log(pattern="), (blk, got)
        assert got["lines"][-len(blk["lines"]):] == blk["lines"], (got, blk)

    # A STEP IS A STOP TOO, and its block holds only what the guest logged since this one.
    on = cast(dict[str, Any], server.step(mode="over"))
    assert on["status"] == "ok" and on["e9"]["mark"] >= blk["mark"], on
