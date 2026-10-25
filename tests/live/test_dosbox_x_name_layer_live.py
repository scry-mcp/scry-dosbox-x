"""The name layer against a real real-mode program."""
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
    """All six name-layer tools in one reach: declare, list, re-declare, watch, clear."""
    # The store persists on disk; isolating it keeps a re-run from meeting old declarations.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    load_seg, _cs, _eip = reach_realmode(tmp_path)
    watch = real_address(load_seg, REAL_VARIABLE)
    assert load_seg >= 0

    named = cast(dict[str, Any], server.breakpoint_at(ref=REAL_LOOP))
    assert named["status"] == "ok" and named["armed"] is True, named

    marked = cast(dict[str, Any], server.breakpoint_at(ref=REAL_MARKED))
    assert marked["status"] == "ok", marked
    assert marked.get("marked", False) is True and "linker's mark" in str(marked["note"]), marked

    # The walk's INT 21 is a declaration too.
    listed = cast(dict[str, Any], server.declaration_list("breakpoint"))
    states = {b["ref"]: b["state"] for b in listed["breakpoints"]}
    assert states.get(REAL_LOOP) == "armed", listed
    assert states.get(REAL_MARKED) == "armed", listed
    assert states.get("BPINT 21") == "armed", listed
    assert "foreign" not in listed, listed

    again = cast(dict[str, Any], server.breakpoint_at(ref=REAL_LOOP))
    assert again["status"] == "ok" and again.get("already_stored", False) is True, again
    assert again["armed"] is True, again
    rows = [b for b in cast(ds.Session, dstate.STATE.session).breakpoints()
            if b["entry"] == named["entry"]]
    assert len(rows) == 1, rows

    w = cast(dict[str, Any], server.watch_add(ref=watch, mode="change", length=4, fmt="u32"))
    assert w["status"] == "ok" and w["armed"] is True, w
    wl = cast(dict[str, Any], server.declaration_list("watch"))
    assert any(x["ref"] == watch and x["state"] == "armed" for x in wl["watches"]), wl

    # Clear must also disarm what the store placed, read back off the debugger.
    bc = cast(dict[str, Any], server.declaration_clear("breakpoint", all=True))
    assert bc["declarations_cleared"] == 3 and len(bc["disarmed"]) == 3, bc
    assert "BPINT 21" in bc["disarmed"], bc
    wc = cast(dict[str, Any], server.declaration_clear("watch", all=True))
    assert wc["declarations_cleared"] == 1, wc
    after = cast(dict[str, Any], server.declaration_list("breakpoint"))
    assert after["breakpoints"] == [], after
