"""Presence on DOSBox-X: the edge plus a pointer, drawn by the emulator's `PRESENCE` command.

It draws into the scaled output after the frame went to capture, so no capture or screen read
carries it. The pointer appears once the session has moved the guest's mouse.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from scry_core import presence
from scry_core.reply_contract import unavailable

from scry_dosbox_x import debugger as dbg

#: Calls during which presence is `acting`; every other tool is `STILL_TOOLS`. Both are written
#: out so a new tool must be put on one side (the suite checks them against the registry).
#: `snapshot` is still: its capture trigger changes nothing the guest reads.
DRIVING_TOOLS = frozenset({
    "resume", "stop", "step", "run_to", "run_for", "trace", "screen_wait", "send_keys",
    "send_mouse", "drive", "perform", "state_write", "debug", "write", "set_register", "record",
    "audio_record", "port", "pic", "a20"})
STILL_TOOLS = frozenset({
    "audio_compare", "breakpoint_at", "breakpoint_interrupt", "build_check", "call_stack",
    "capture_frame", "captures", "close", "comment_list", "comment_write", "declaration_clear",
    "declaration_list", "disassemble", "find", "guest_file", "image_compare",
    "interrupt_vectors", "log",
    "log_wait", "machine_map", "screen_map_find", "screen_map_write", "memdump", "palette",
    "perform_export",
    "read_memory", "registers", "regpoint_add", "scan", "screen_signature", "screen_view",
    "series_capture", "window",
    "snapshot", "start", "state_list", "status", "symbols_find", "symbols_load", "wait",
    "watch_add", "promote"})

NO_COMMAND = "this DOSBox-X's debugger has no PRESENCE command"
NO_OUTPUT = ("this output cannot be drawn on (an 8-bit output, or the TrueType output while it "
             "shows text)")
NO_WINDOW = "a session started without `shared` has no window to draw on"
#: The bare command names the build's version; a build that refuses the bare form is version 1.
MIN_VERSION = 2
#: The INT 33h driver's default graphics pointer, hot spot top-left: `X` outline, `o` fill, `.`
#: untouched. One cell per guest pixel, it matches a DOS program's own pointer.
POINTER = (
    "XX.........",
    "XoX........",
    "XooX.......",
    "XoooX......",
    "XooooX.....",
    "XoooooX....",
    "XooooooX...",
    "XoooooooX..",
    "XooooooooX.",
    "XoooooXXXXX",
    "XooXooX....",
    "XoXXXooX...",
    "XX..XooX...",
    ".....XooX..",
    ".....XooX..",
    "......XX...",
)
POINTER_OUTLINE_RGB = 0x2A1400
#: A look, not a promise: the button may follow the move by one BIOS tick, which is shorter.
POINTER_GLIDE_S = 0.1


def channel_args(look: presence.Look = presence.LOOK) -> str:
        return (f"rgb={look.rgb:06X} edge={look.edge:g} steps={look.steps} "
            f"acting={look.acting_alpha:.3f} held={look.held_alpha:.3f} fade={look.fade_s:g} "
            f"outline={POINTER_OUTLINE_RGB:06X} glide={POINTER_GLIDE_S:g} "
            f"sprite={'/'.join(POINTER)}")


class Debugger(Protocol):
    def has(self, command: str) -> bool: ...
    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]: ...


class ChannelAdapter:
    """`scry_core.presence.Adapter` over a session's debugger, read at each delivery."""

    def __init__(self, session: Debugger, look: presence.Look = presence.LOOK) -> None:
        self._session = session
        self._args = channel_args(look)
        self.pointer = False
        self.answer = ""
        self.version: int | None = None

    def show(self, state: presence.State) -> None:
        if not self._session.has("PRESENCE"):
            raise presence.Unavailable(NO_COMMAND)
        if self.version is None:
            self.version = build_version(self._session.exec("PRESENCE")[1])
        if self.version < MIN_VERSION:
            raise presence.Unavailable(
                f"this DOSBox-X's PRESENCE is version {self.version}, which draws the pointer at a "
                f"share of the window; version {MIN_VERSION} sizes it by the guest's pixels")
        ok, lines = self._session.exec(
            f"PRESENCE {state} {self._args} pointer={int(self.pointer)}")
        if not ok:
            # A refused key also ends with the debugger's own line, after its reason.
            if lines == [dbg.NOT_RECOGNIZED]:
                raise presence.Unavailable(NO_COMMAND)
            said = " / ".join(ln for ln in lines if ln != dbg.NOT_RECOGNIZED) or "no reason given"
            raise RuntimeError(f"the debugger refused PRESENCE: {said}")
        self.answer = lines[0] if lines else ""
        # `output=none` is not refused: no frame has been drawn yet at the parked start.
        if "output=undrawable" in self.answer.split():
            raise presence.Unavailable(NO_OUTPUT)

    def wake(self) -> None:
        """Nothing to wake: this emulator repaints on its own."""

    def repaint(self, still: Callable[[], bool]) -> None:
        """Nothing: a guest parked at the debugger keeps drawing frames."""


def build_version(lines: list[str]) -> int:
    """The `version=N` word of the bare command's answer; 1 when it has none."""
    for word in " ".join(lines).split():
        if word.startswith("version=") and word[len("version="):].isdigit():
            return int(word[len("version="):])
    return 1


def pointer_moved(shown: presence.Shown) -> None:
    """Turn the pointer on from the session's first mouse move."""
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


def open_shown(session: Debugger, asked: bool, shared: bool) -> presence.Shown:
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
