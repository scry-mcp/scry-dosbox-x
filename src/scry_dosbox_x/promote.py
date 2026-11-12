"""`promote`: what this session learned, kept as a candidate and written on approval."""

from __future__ import annotations

import os
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from scry_core import given, project_store
from scry_core import promote as core

from scry_dosbox_x import lifecycle
from scry_dosbox_x.state import STATE

#: `start`'s arguments a recipe leaves to the run: this session's files, port and window.
RUN_OWN = frozenset({"logfile", "state_dir", "input_port", "display", "size", "fullscreen",
                     "background", "plan", "settle_seconds", "captures_dir", "guest_files",
                     "profile"})
#: What a recipe may hold as a path.
PROMOTE_PATHS = lifecycle.START_PATHS
#: What a recipe cannot do without: `start`'s own pre-gate demands them.
NEEDS = ("conf", "cwd", "session_seconds")
SERVER = "dosbox-x"


def has_store(drafts: core.Drafts) -> bool:
    """Whether a `.scry/` is above the project the draft names; unreadable or nameless says yes."""
    try:
        own = os.getcwd()
        starts = [path for path in core.starting(drafts, recipe_paths) if path != own]
        return not starts or project_store.root(starts) is not None
    except OSError:
        return True


def kept_line(drafts: core.Drafts) -> str:
    """Core's kept line, told if a store exists."""
    return core.kept_line(drafts, has_store(drafts))


def after_export(drafts: core.Drafts, reply: dict[str, Any],
                 path_keys: Collection[str]) -> dict[str, Any]:
    """The export's reply, its store sought after the keep."""
    kept = core.after_export(drafts, reply, path_keys)
    return {**kept, "kept": kept_line(drafts)} if "kept" in kept else kept


def guest_name(params: Mapping[str, Any]) -> str:
    """The name a guest is known by: its program's stem, else its conf's."""
    for key in ("program", "conf"):
        value = str(params.get(key) or "").strip()
        if value:
            if key == "conf":
                return Path(value.replace("\\", "/")).stem.lower()
            return Path(value.split()[0].replace("\\", "/")).stem.lower()
    return ""


def note_start(params: Mapping[str, Any]) -> None:
    """The guest this session runs, set before the launch so a `plan`'s `add` knows it."""
    STATE.guest = guest_name(params)


def keep_start(params: Mapping[str, Any], *, defaults: Mapping[str, Any]) -> bool:
    """This start's recipe, named by the profile it read or the guest."""
    name = STATE.drafts.loaded_name("start") or STATE.guest
    if not name:
        return False
    if STATE.drafts.loaded_name("start") and core.only_the_run(given.names(), RUN_OWN):
        return False
    document: dict[str, Any] = {"format": project_store.FORMAT}
    document.update({name: value for name, value in params.items()
                     if name in defaults and name not in RUN_OWN
                     and value != defaults[name]})
    return STATE.drafts.keep("start", name, document, needs=NEEDS, path_keys=PROMOTE_PATHS,
                             own=sorted(RUN_OWN))


def after_map(method: str, reply: dict[str, Any]) -> dict[str, Any]:
    """A map's `add` keeps what it learned, named by this session's entry or the guest."""
    application = STATE.maps.session_application or STATE.guest
    if method != "add" or not application:
        return reply
    if STATE.drafts.keep("maps", application, STATE.maps.document(application)):
        return {**reply, "kept": kept_line(STATE.drafts)}
    return reply


def promote(dry_run: bool = False, entries: list[str] | None = None,
            names: dict[str, str] | None = None, root: str = "") -> dict[str, Any]:
    """The `promote` tool's body, on this server's draft."""
    try:
        starts = starting()
    except OSError:
        starts = []
    return core.promote(STATE.drafts, dry_run=dry_run, entries=entries, names=names, root=root,
                        starting=starts, state=scratch(), server=SERVER)


def starting() -> list[str]:
    """Where the store is looked for, as core orders it from this server's recipe paths."""
    return core.starting(STATE.drafts, recipe_paths)


def after_close(reply: dict[str, Any], state: str) -> dict[str, Any]:
    """`close`'s reply, naming what it left waiting."""
    return core.after_close(STATE.drafts, reply, starting=starting, state=state)


def recipe_paths(recipe: Mapping[str, Any]) -> list[str]:
    """What in a recipe says which repository it belongs to: the guest's directory, its conf."""
    return [str(recipe.get("cwd") or ""), str(recipe.get("conf") or "")]


def scratch() -> str:
    """The session's scratch, which a recipe writes as `${state}`."""
    return str(STATE.session_scratch()) if STATE.session is not None else ""
