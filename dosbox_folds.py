"""The tools that fold one resource's operations (`scry_core.methods`): the declarations by `kind`,
and the comments, the screen map, the value scan and the saved states by `method`. Each method's
body runs behind the gate it needs and its judge is `dosbox_checks`', so the batch and the
surface ask one table (`dosbox_checks.BY_OP`)."""

from __future__ import annotations

from typing import Any

from scry_core import declaration_rows, judges, methods, screen_map
from scry_core import vocabulary as vocab
from scry_core.methods import Method

import dosbox_arming as arming
import dosbox_checks as checks
import dosbox_comments as comments
import dosbox_find as finder
import dosbox_placement as placement
import dosbox_screen as dscreen
import dosbox_session as ds
import dosbox_state as st
import dosbox_summaries as one_line
from dosbox_running import live
from dosbox_state import STATE

KINDS = tuple(one_line.DECLARATION_ROWS)
_LISTS = {"breakpoint": arming.list_breakpoints, "watch": arming.list_watches}
_CLEARS = {"breakpoint": arming.clear_breakpoints, "watch": arming.clear_watches}


def check_list_declarations(kind: str = "", **_: Any) -> None:
    vocab.one_of("kind", kind, ("", *KINDS))


def list_declarations(kind: str) -> dict[str, Any]:
    """Each kind's rows under its field, every kind when `kind` is empty
    (`scry_core.declaration_rows.merged`)."""
    check_list_declarations(kind)
    session = live()
    return declaration_rows.merged({one_line.DECLARATION_ROWS[k]: _LISTS[k](session)
                                    for k in ((kind,) if kind else KINDS)})


def check_clear_declarations(kind: str = "", ref: str = "", all: bool = False,
                             **_: Any) -> None:
    vocab.one_of("kind", kind, KINDS)
    checks.clear_scope(ref, all)


def clear_declarations(kind: str, ref: str, all: bool) -> dict[str, Any]:
    check_clear_declarations(kind, ref, all)
    return _CLEARS[kind](live(), None if all else ref)


def _add_comment(ref: str, text: str) -> dict[str, Any]:
    return comments.add_comment(live(), ref, text)


def _delete_comment(ref: str) -> dict[str, Any]:
    return comments.delete_comment(live(), ref)


def _save_comments(dest: str) -> dict[str, Any]:
    return comments.save_comments(live(), dest)


def _load_comments(path: str) -> dict[str, Any]:
    return comments.load_comments(live(), path)


COMMENT = {
    "add": Method(_add_comment, checks.check_add_comment, one_line.add_comment),
    "delete": Method(_delete_comment, checks.check_delete_comment, one_line.delete_comment),
    "save": Method(_save_comments, checks.check_save_comments, one_line.save_comments),
    "load": Method(_load_comments, checks.check_load_comments, one_line.load_comments),
}


def map_read(session: ds.Session) -> screen_map.Read:
    """The one screen read a map is matched against, `screen_signature`'s."""
    return lambda: dscreen.grid(session)[0]


def _add_map(screen: str, match: list[list[int]],
             controls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    session = live()
    ds.console_listening(session, "a listing")
    return st.reply(**STATE.maps.add(screen, match, controls, map_read(session)))


def _load_map(path: str) -> dict[str, Any]:
    return st.reply(**STATE.maps.load(path))


def _save_map(dest: str, overwrite: bool = False) -> dict[str, Any]:
    return st.reply(**STATE.maps.save(dest, overwrite))


MAP = {
    "add": Method(_add_map, checks.check_add_map, screen_map.add_line),
    "load": Method(_load_map, checks.check_load_map, screen_map.load_line),
    "save": Method(_save_map, checks.check_save_map, screen_map.save_line),
}


def _start_scan(ref: str, length: int, cell_bytes: int = 1) -> dict[str, Any]:
    session = live()
    ds.console_listening(session, "a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.start_scan(session, seg, off, length, cell_bytes))


def _filter_scan(operator: str = "=", value: judges.NumberArg | None = None,
                 limit: int = judges.HITS_DEFAULT) -> dict[str, Any]:
    session = live()
    ds.console_listening(session, "a search")
    number = None if value is None else checks.number("value", value)
    return st.reply(**finder.filter_scan(session, operator, number, limit))


def _clear_scan() -> dict[str, Any]:
    session = live()
    ds.console_listening(session, "a search")
    return st.reply(**finder.clear_scan(session))


SCAN = {
    "start": Method(_start_scan, checks.check_start_scan, one_line.start_scan),
    "filter": Method(_filter_scan, checks.check_filter_scan, one_line.filter_scan),
    "clear": Method(_clear_scan, lambda **_: None, one_line.clear_scan),
}


def _save_state(name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, Any]:
    return st.answer(live().save_state(name, seconds))


def _load_state(name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, Any]:
    session = live()
    try:
        return st.answer(session.load_state(name, seconds))
    finally:
        # A LOAD THAT REPLACED THE MACHINE, answered or cut short after it went (the session
        # decides, `dosbox_saved_states.load_state`): the table is kept and its base is measured
        # again at the next stop.
        if getattr(session, "machine_replaced", False):
            STATE.machine_replaced()


STATE_METHODS = {
    "save": Method(_save_state, checks.check_state, one_line.save_state),
    "load": Method(_load_state, checks.check_state, one_line.load_state),
}

#: Each fold's pre-gate judge, as `dosbox_checks.BY_OP` holds it.
CHECKS = {
    "declaration_list": check_list_declarations,
    "declaration_clear": check_clear_declarations,
    "comment_write": methods.fold_check(COMMENT),
    "map_write": methods.fold_check(MAP),
    "scan": methods.fold_check(SCAN),
    "state_write": methods.fold_check(STATE_METHODS),
}
