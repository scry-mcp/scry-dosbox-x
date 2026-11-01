"""The window DOSBox-X's live session asked for."""

from __future__ import annotations

from scry_core.window import WindowRequest
from scry_core.window_stand_ins import hosts

from scry_dosbox_x.state import STATE


def asked() -> tuple[int, WindowRequest] | None:
    session = STATE.session
    if session is None or session.launch.window is None:
        return None
    return session.pid, session.launch.window


def obeying() -> hosts.Obeying:
    return hosts.Obeying(asked)


def window_if(watched: bool) -> WindowRequest | None:
    return WindowRequest(0, False, (0, 0)) if watched else None
