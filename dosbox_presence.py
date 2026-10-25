"""Presence on DOSBox-X: the edge plus a pointer arrow, drawn by the emulator's `PRESENCE` command.

It draws into the scaled output after the frame went to capture, so no capture or screen read
carries it. The arrow appears once the session has moved the guest's mouse.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from scry_core import presence
from scry_core.reply_contract import unavailable

#: Calls during which presence is `acting`; every other tool is `STILL_TOOLS`. Both are written
#: out so a new tool must be put on one side (the suite checks them against the registry).
#: `snapshot` is still: its capture trigger changes nothing the guest reads.
DRIVING_TOOLS = frozenset({
    "resume", "stop", "step", "run_to", "run_for", "trace", "screen_wait", "send_keys",
    "send_mouse", "drive", "perform", "state_write", "debug", "write", "set_register"})
STILL_TOOLS = frozenset({
    "breakpoint_at", "breakpoint_interrupt", "build_check", "call_stack", "capture_frame",
    "captures", "close", "comment_list", "comment_write", "declaration_clear",
    "declaration_list", "disassemble", "find", "image_compare", "interrupt_vectors", "log",
    "log_wait", "machine_map", "map_find", "map_write", "memdump", "palette", "perform_export",
    "read_memory", "registers", "scan", "screen_signature", "screen_view", "series_capture",
    "snapshot", "start", "state_list", "status", "symbols_find", "symbols_load", "watch_add"})

NO_COMMAND = "this DOSBox-X's debugger channel has no PRESENCE command"
NO_OUTPUT = ("this output cannot be drawn on (an 8-bit output, or the TrueType output while it "
             "shows text)")
NO_WINDOW = "a session started without `shared` has no window to draw on"


def channel_args(look: presence.Look = presence.LOOK) -> str:
        return (f"rgb={look.rgb:06X} edge={look.edge:g} steps={look.steps} "
            f"acting={look.acting_alpha:.3f} held={look.held_alpha:.3f} fade={look.fade_s:g} "
            f"outline={look.pointer_outline_rgb:06X} size={look.pointer_size:g} "
            f"glide={look.pointer_glide_s:g} sprite={'/'.join(look.pointer)}")


class Channel(Protocol):
    def request(self, command: str, seconds: float = ...) -> tuple[bool, list[str]]: ...


class HasChannel(Protocol):
    @property
    def control(self) -> Channel: ...


class ChannelAdapter:
    """`scry_core.presence.Adapter` over a session's debugger channel, read at each delivery."""

    def __init__(self, session: HasChannel, look: presence.Look = presence.LOOK) -> None:
        self._session = session
        self._args = channel_args(look)
        self.pointer = False
        self.answer = ""

    def show(self, state: presence.State) -> None:
        ok, lines = self._session.control.request(
            f"PRESENCE {state} {self._args} pointer={int(self.pointer)}")
        said = " / ".join(lines) or "no reason given"
        if not ok:
            raise (presence.Unavailable(NO_COMMAND) if "unknown request command" in said
                   else RuntimeError(f"the debugger channel refused PRESENCE: {said}"))
        self.answer = lines[0] if lines else ""
        # `output=none` is not refused: no frame has been drawn yet at the parked start.
        if "output=undrawable" in self.answer.split():
            raise presence.Unavailable(NO_OUTPUT)

    def wake(self) -> None:
        """Nothing to wake: this emulator repaints on its own."""

    def repaint(self, still: Callable[[], bool]) -> None:
        """Nothing: a guest parked at the debugger keeps drawing frames."""


def pointer_moved(shown: presence.Shown) -> None:
    """Turn the arrow on from the session's first mouse move."""
    adapter = shown.adapter
    if shown.held is None or not isinstance(adapter, ChannelAdapter) or adapter.pointer:
        return
    adapter.pointer = True
    shown.held.redeliver()


NEVER_DRAWN = presence.Shown()


def of(session: object) -> presence.Shown:
    """The session's presence; a stand-in with none reads as never drawn."""
    shown = getattr(session, "presence", NEVER_DRAWN)
    return shown if isinstance(shown, presence.Shown) else NEVER_DRAWN


def open_shown(session: HasChannel, asked: bool, shared: bool) -> presence.Shown:
    """A session's presence, its first state delivered before `start` answers."""
    if not asked:
        return presence.Shown()
    if not shared:
        return presence.Shown(refused=unavailable(NO_WINDOW))
    return presence.Presence.open(ChannelAdapter(session), DRIVING_TOOLS)


def frames(answer: str) -> int | None:
    for word in answer.split():
        if word.startswith("frames=") and word[len("frames="):].isdigit():
            return int(word[len("frames="):])
    return None
