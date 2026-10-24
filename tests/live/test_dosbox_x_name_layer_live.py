"""The name layer against a REAL real-mode program: breakpoints and watches by name, the
store cross-referenced with the debugger, and the marked-public note.

It runs dos-real16's copy on the bench, as the entry-route file does, and SKIPS naming the
file when a copy is absent or off its pin. The reach helper and the map's names are shared
from that file rather than copied, so the two cannot drift on how the program's own loop is
found.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)
from test_dosbox_x_entry_routes import (
    REAL_LOOP,
    REAL_MARKED,
    REAL_PROGRAM,
    REAL_VARIABLE,
    reach_realmode,
    real_address,
)

import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

pytestmark = pytest.mark.live


@REAL_PROGRAM
def test_the_name_layer_arms_lists_and_clears_against_a_real_program(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All six tools in one reach: declare a breakpoint by name and see it armed and in the
    list; declare a second on a MARKED public and see the note; add a break-on-change watch
    by address; list it; then clear both and confirm the debugger no longer holds them.

    THE STORE IS ISOLATED to a tmp state dir: it persists on disk by design (so a rebuild
    is free), so without this a re-run would meet its own earlier declarations as
    duplicates. `default_path` honours XDG_STATE_HOME, so pointing it at tmp is the seam.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    watch = real_address(load_seg, REAL_VARIABLE)
    assert load_seg >= 0

    # BY NAME -> armed, and stored.
    named = cast(dict[str, Any], server.breakpoint_at(ref=REAL_LOOP))
    assert named["status"] == "ok" and named["armed"] is True, named

    # A MARKED public says so in the reply, and is not refused.
    marked = cast(dict[str, Any], server.breakpoint_at(ref=REAL_MARKED))
    assert marked["status"] == "ok", marked
    assert marked.get("marked", False) is True and "linker's mark" in str(marked["note"]), marked

    # The list shows both as armed, the walk's INT 21 beside them (an interrupt
    # breakpoint is a declaration too), and no foreign entry the store did not place.
    listed = cast(dict[str, Any], server.declaration_list("breakpoint"))
    states = {b["ref"]: b["state"] for b in listed["breakpoints"]}
    assert states.get(REAL_LOOP) == "armed", listed
    assert states.get(REAL_MARKED) == "armed", listed
    assert states.get("BPINT 21") == "armed", listed
    assert "foreign" not in listed, listed

    # RE-DECLARING is a no-op that says so, and does not arm a second copy.
    again = cast(dict[str, Any], server.breakpoint_at(ref=REAL_LOOP))
    assert again["status"] == "ok" and again.get("already_stored", False) is True, again
    assert again["armed"] is True, again
    rows = [b for b in cast(ds.Session, dstate.STATE.session).breakpoints()
            if b["entry"] == named["entry"]]
    assert len(rows) == 1, rows

    # A break-on-change watch by ADDRESS (real mode, BPM), listed, then cleared.
    w = cast(dict[str, Any], server.watch_add(ref=watch, mode="change", length=4, fmt="u32"))
    assert w["status"] == "ok" and w["armed"] is True, w
    wl = cast(dict[str, Any], server.declaration_list("watch"))
    assert any(x["ref"] == watch and x["state"] == "armed" for x in wl["watches"]), wl

    # Clear removes the declarations AND disarms what the store placed: the two code
    # breakpoints and the interrupt, read back off the debugger's list.
    bc = cast(dict[str, Any], server.declaration_clear("breakpoint", all=True))
    assert bc["declarations_cleared"] == 3 and len(bc["disarmed"]) == 3, bc
    assert "BPINT 21" in bc["disarmed"], bc
    wc = cast(dict[str, Any], server.declaration_clear("watch", all=True))
    assert wc["declarations_cleared"] == 1, wc
    after = cast(dict[str, Any], server.declaration_list("breakpoint"))
    assert after["breakpoints"] == [], after
