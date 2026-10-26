"""Registerpoints: a stop when a condition on the registers comes true, wherever the program
is, armed as the debugger's `BPIF` (`regpoint_add`, and `declaration_list` and
`declaration_clear` of kind `regpoint`). A build without `BPIF` is refused by name."""

from __future__ import annotations

import functools
from typing import Any, cast

import dosbox_arming as arming
import dosbox_debugger as dbg
import dosbox_grammar as grammar
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

BPIF = "BPIF"
#: The armed-row record a registerpoint leaves (`STATE.note_armed`).
SPEC_KIND = "cond"


def entry_of(row: str) -> str:
    """The `BPLIST` row a canonical condition lists as."""
    return f"{grammar.CONDITION_ROW}{row}"


def spec_of(row: str) -> dict[str, Any]:
    return {"kind": SPEC_KIND, "row": row, "entry": entry_of(row)}


def _require(session: ds.Session) -> None:
    if not session.has(BPIF):
        raise dbg.missing(BPIF, "a registerpoint")


def regpoint_add(session: ds.Session, condition: str) -> dict[str, Any]:
    """The body of the `regpoint_add` tool: stored, then armed now or at the next stop."""
    _require(session)
    row = grammar.condition_row(condition)
    entry = entry_of(row)
    decl = arming.declare("regpoint", "expr", row)
    store = arming.current_store()
    head: dict[str, Any] = {"ref": row, "by": "expr", "condition": row, "stored": True}
    if not session.at_debugger():
        is_new = cast(bool, placement.to_invalid(lambda: store.add(decl)))
        return st.reply(**head, already_stored=not is_new, while_running=True, armed=False,
                        state="pending", **STATE.queue_arm(row))
    held = any(b["entry"] == entry for b in session.breakpoints())
    # Stored first, as its twins are: a store that cannot be written leaves nothing armed
    # unaccounted for.
    is_new = cast(bool, placement.to_invalid(lambda: store.add(decl)))
    if not held:
        try:
            session.condition_breakpoint(row)
        except ds.Invalid:
            if is_new:
                placement.to_invalid(lambda: store.remove(ref=row, kind="regpoint"))
            raise
    STATE.note_armed(row, spec_of(row))
    return st.reply(**head, already_stored=not is_new, while_running=False, armed=True,
                    state="armed", entry=entry,
                    **({"note": "this registerpoint was already armed"} if held else {}))


def list_regpoints(session: ds.Session) -> dict[str, Any]:
    """The body of the `declaration_list(kind="regpoint")` tool."""
    store = arming.current_store()
    held, read, _ = STATE.list_basis(session)
    out: list[dict[str, Any]] = []
    mine: set[str] = set()
    for decl in store.declarations():
        if decl.kind != "regpoint":
            continue
        item = arming.decl_row(decl)
        item.update(condition=decl.ref, entry=entry_of(decl.ref))
        if any(b["entry"] == item["entry"] for b in held):
            item["state"] = "armed"
            mine.add(item["entry"])
        else:
            item["state"] = "gone"
        out.append(item)
    arming.pending_states(out)
    queued = {str(spec["entry"]) for spec in STATE.pending["disarm"]}
    foreign = [b["entry"] for b in held if b["entry"].startswith(grammar.CONDITION_ROW)
               and b["entry"] not in mine and b["entry"] not in queued]
    dated: dict[str, Any] = {} if read else {"last_stop": STATE.dated()}
    return st.reply(regpoints=out, foreign=foreign, debugger_read=read, **dated)


def clear_regpoints(session: ds.Session, ref: str | None) -> dict[str, Any]:
    """The body of the `declaration_clear(kind="regpoint")` tool."""
    store = arming.current_store()
    ref = arming.require_a_match(store, None if ref is None else grammar.condition_row(ref),
                                 ("regpoint",))
    running = not session.at_debugger()
    going = [d for d in store.declarations()
             if d.kind == "regpoint" and (ref is None or d.ref == ref)]
    removed = cast(int, placement.to_invalid(lambda: store.remove(ref=ref, kind="regpoint")))
    disarmed: list[str] = []
    pending_disarm: list[str] = []
    for decl in going:
        STATE.armed.pop(("bp", decl.ref), None)
        arming.disarm_one(spec_of(decl.ref), decl.ref, running, disarmed, pending_disarm,
                          functools.partial(session.clear_condition_breakpoint, decl.ref))
    arming.unqueue_cleared(store)
    return st.reply(declarations_cleared=removed, disarmed=disarmed,
                    pending_disarm=pending_disarm,
                    note=arming.pending_note(running, pending_disarm))

