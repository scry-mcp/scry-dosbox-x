"""`promote`: what this session learned, kept and written by scry-core's `promote`."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from scry_core import promote as core

from scry_dosbox_x import lifecycle
from scry_dosbox_x.state import STATE

#: `start`'s arguments a recipe leaves to the run.
RUN_OWN = frozenset({"logfile", "state_dir", "input_port", "display", "size", "fullscreen",
                     "background", "plan", "settle_seconds", "captures_dir", "guest_files",
                     "profile"})
#: What a recipe may hold as a path.
PROMOTE_PATHS = lifecycle.START_PATHS
#: What a recipe cannot do without.
NEEDS = ("conf", "cwd", "session_seconds")
SERVER = "dosbox-x"


def guest_name(params: Mapping[str, Any]) -> str:
    """The name a guest is known by: its program's stem, else its conf's."""
    for key in ("program", "conf"):
        value = str(params.get(key) or "").strip()
        if value:
            if key == "conf":
                return Path(value.replace("\\", "/")).stem.lower()
            return Path(value.split()[0].replace("\\", "/")).stem.lower()
    return ""


def anchor(params: Mapping[str, Any]) -> str:
    """Where a start's guest lives: its `cwd`, else its `conf`'s directory."""
    cwd = str(params.get("cwd") or "").strip()
    conf = str(params.get("conf") or "").strip()
    return cwd or (str(Path(conf).parent) if conf else "")


@contextmanager
def launching(params: Mapping[str, Any], profile: str = "") -> Iterator[None]:
    """The guest this session runs and the project it runs in, set before the launch so a
    `plan`'s `add` knows both; a start that raises leaving no session of its own live leaves
    the live session's."""
    before, session = STATE.guest, STATE.session
    STATE.guest = guest_name(params)
    try:
        with STATE.drafts.starting(profile=profile, anchor=anchor(params),
                                   live=lambda: STATE.session):
            yield
    except BaseException:
        if STATE.session in (None, session):
            STATE.guest = before
        raise


def after_start(reply: dict[str, Any], params: Mapping[str, Any], *,
                block: Mapping[str, Any] | None, defaults: Mapping[str, Any]) -> dict[str, Any]:
    """`start`'s reply with the recipe kept, named by the guest without a profile."""
    return core.after_start(STATE.drafts, reply, params, block=block, guest=STATE.guest,
                            defaults=defaults, run_own=RUN_OWN, needs=NEEDS,
                            path_keys=PROMOTE_PATHS)


def after_map(method: str, reply: dict[str, Any]) -> dict[str, Any]:
    """A map's `add`, named by the guest without an entry read."""
    return core.after_map(STATE.drafts, STATE.maps, method, reply, guest=STATE.guest)


def promote(dry_run: bool = False, entries: list[str] | None = None,
            names: dict[str, str] | None = None, root: str = "") -> dict[str, Any]:
    """The `promote` tool's body, on this server's draft."""
    return core.promote(STATE.drafts, dry_run=dry_run, entries=entries, names=names, root=root,
                        state=scratch(), server=SERVER)


def after_close(reply: dict[str, Any], state: str) -> dict[str, Any]:
    """`close`'s reply, naming what it left waiting."""
    return core.after_close(STATE.drafts, reply, state=state)


def scratch() -> str:
    """The session's scratch, which a recipe writes as `${state}`."""
    return str(STATE.session_scratch()) if STATE.session is not None else ""
