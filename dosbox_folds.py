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
import dosbox_hardware as hardware
import dosbox_placement as placement
import dosbox_regpoints as regpoints
import dosbox_screen as dscreen
import dosbox_session as ds
import dosbox_state as st
import dosbox_summaries as one_line
from dosbox_running import live
from dosbox_state import STATE

KINDS = tuple(one_line.DECLARATION_ROWS)
_LISTS = {"breakpoint": arming.list_breakpoints, "regpoint": regpoints.list_regpoints,
          "watch": arming.list_watches}
_CLEARS = {"breakpoint": arming.clear_breakpoints, "regpoint": regpoints.clear_regpoints,
           "watch": arming.clear_watches}


def check_list_declarations(kind: str = "", **_: Any) -> None:
    declaration_rows.chosen_kinds(kind, KINDS)


def list_declarations(kind: str) -> dict[str, Any]:
    """Each kind's rows under its field, every kind when `kind` is empty
    (`scry_core.declaration_rows.merged`)."""
    session = live()
    return declaration_rows.merged({one_line.DECLARATION_ROWS[k]: _LISTS[k](session)
                                    for k in declaration_rows.chosen_kinds(kind, KINDS)})


def check_clear_declarations(kind: str = "", ref: str = "", all: bool = False,
                             **_: Any) -> None:
    vocab.one_of("kind", kind, KINDS)
    vocab.check_clear_scope(ref, all, kind)


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
    """The one screen read a map is matched against, `screen_signature`'s, with the palette
    indices when a screen signed by index asks for them."""
    return lambda indices=False: dscreen.grid(session, indices)[0]


def _add_map(screen: str, match: list[list[int]],
             controls: list[dict[str, Any]] | None = None, cells: str = "rgb") -> dict[str, Any]:
    session = live()
    session.require_stopped("a listing")
    return st.reply(**STATE.maps.add(screen, match, controls, map_read(session), cells))


def _load_map(path: str, scale: int = 1, margin: list[int] | None = None) -> dict[str, Any]:
    return st.reply(**STATE.maps.load(path, scale, margin))


def _save_map(dest: str, overwrite: bool = False) -> dict[str, Any]:
    return st.reply(**STATE.maps.save(dest, overwrite))


MAP = {
    "add": Method(_add_map, checks.check_add_map, screen_map.add_line),
    "load": Method(_load_map, checks.check_load_map, screen_map.load_line),
    "save": Method(_save_map, checks.check_save_map, screen_map.save_line),
}


def _start_scan(ref: str, length: int, cell_bytes: int = 1) -> dict[str, Any]:
    session = live()
    session.require_stopped("a search")
    seg, off = placement.read_target(ref, "DS", session)
    return st.reply(ref=ref, **finder.start_scan(session, seg, off, length, cell_bytes))


def _filter_scan(operator: str = "=", value: judges.NumberArg | None = None,
                 limit: int = judges.HITS_DEFAULT) -> dict[str, Any]:
    session = live()
    session.require_stopped("a search")
    number = None if value is None else checks.number("value", value)
    return st.reply(**finder.filter_scan(session, operator, number, limit))


def _clear_scan() -> dict[str, Any]:
    session = live()
    session.require_stopped("a search")
    return st.reply(**finder.clear_scan(session))


SCAN = {
    "start": Method(_start_scan, checks.check_start_scan, one_line.start_scan),
    "filter": Method(_filter_scan, checks.check_filter_scan, one_line.filter_scan),
    "clear": Method(_clear_scan, methods.no_check, one_line.clear_scan),
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

def _port_read(port: judges.NumberArg, bits: int = 8) -> dict[str, Any]:
    return hardware.port_read(live(), port, bits)


def _port_write(port: judges.NumberArg, value: judges.NumberArg, bits: int = 8
                ) -> dict[str, Any]:
    return hardware.port_write(live(), port, value, bits)


PORT = {
    "read": Method(_port_read, hardware.check_port, one_line.port_read),
    "write": Method(_port_write, hardware.check_port_write, one_line.port_write),
}


def _pic_read() -> dict[str, Any]:
    return hardware.pic_read(live())


def _pic_action(action: str) -> Method:
    def body(irq: int) -> dict[str, Any]:
        return hardware.pic_action(live(), action, irq)
    return Method(body, hardware.check_pic, one_line.pic_action)


PIC = {"read": Method(_pic_read, methods.no_check, one_line.pic_read),
       **{action: _pic_action(action) for action in hardware.PIC_ACTIONS}}


def _a20_read() -> dict[str, Any]:
    return hardware.a20_read(live())


def _a20_on() -> dict[str, Any]:
    return hardware.a20_set(live(), True)


def _a20_off() -> dict[str, Any]:
    return hardware.a20_set(live(), False)


A20 = {"read": Method(_a20_read, methods.no_check, one_line.a20),
       "on": Method(_a20_on, methods.no_check, one_line.a20),
       "off": Method(_a20_off, methods.no_check, one_line.a20)}

#: Each `method` fold's method names, which the running gate is held to.
METHODS = {"comment_write": tuple(COMMENT), "screen_map_write": tuple(MAP), "scan": tuple(SCAN),
           "state_write": tuple(STATE_METHODS), "port": tuple(PORT), "pic": tuple(PIC),
           "a20": tuple(A20)}

#: Each fold's pre-gate judge, as `dosbox_checks.BY_OP` holds it.
CHECKS = {
    "declaration_list": check_list_declarations,
    "declaration_clear": check_clear_declarations,
    "comment_write": methods.fold_check(COMMENT),
    "screen_map_write": methods.fold_check(MAP),
    "scan": methods.fold_check(SCAN),
    "state_write": methods.fold_check(STATE_METHODS),
    "port": methods.fold_check(PORT),
    "pic": methods.fold_check(PIC),
    "a20": methods.fold_check(A20),
}
