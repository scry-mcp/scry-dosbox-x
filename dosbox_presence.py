"""PRESENCE ON DOSBOX-X: the edge `scry_core.presence` holds, and an arrow at the guest's pointer,
drawn by the emulator itself through its debugger channel's `PRESENCE` command.

WHERE IT IS DRAWN decides whether it can reach the evidence: into the scaled output just before
the frame is presented, after it was handed to capture, so no capture or screen read carries it
(REFERENCE.md, The presence indicator, names them).

EVERY STATE GOES OVER THE CHANNEL WITH THE WHOLE LOOK, so the emulator holds no look of its own
and a tuning of `scry_core.presence.LOOK` lands here unchanged. The arrow is drawn once the
session has moved the guest's mouse: a program driven by keys alone shows the edge only.
"""

from __future__ import annotations

from typing import Protocol

from scry_core import presence
from scry_core.reply_contract import unavailable

#: The calls during which the session drives the machine, so presence is `acting`: a call that
#: can move the guest on or change what it holds (it lets the machine run or stops it, feeds it
#: input, writes its memory or registers, restores it), or that cannot be told from one
#: (`debug`, any debugger command). `snapshot` is still: the capture trigger it sends changes
#: nothing the guest reads. Every other tool is `STILL_TOOLS`, and the two lists are
#: written out so a new tool has to be put on one side: the suite holds them against the
#: registry.
DRIVING_TOOLS = frozenset({
    "resume", "stop", "step", "run_to", "run_for", "trace", "screen_wait", "send_keys",
    "send_mouse", "drive", "perform", "state_load", "debug", "write", "set_register"})
STILL_TOOLS = frozenset({
    "breakpoint_at", "breakpoint_clear", "breakpoint_interrupt", "breakpoint_list",
    "build_check", "call_stack", "capture_frame", "captures", "close", "comment_add",
    "comment_delete", "comment_list", "comment_load", "comment_save", "disassemble", "find",
    "golden_check", "image_diff", "interrupt_vectors", "log", "log_wait", "machine_map",
    "map_add", "map_find", "map_load", "map_save", "memdump", "palette", "perform_export",
    "read_memory", "region_track", "registers", "scan_clear", "scan_filter", "scan_start",
    "screen_signature", "screen_view", "series_capture", "series_diff", "snapshot", "start",
    "state_list", "state_save", "status", "symbols_find", "symbols_load", "watch_add",
    "watch_clear", "watch_list"})

#: What a build whose channel lacks the command is said to lack.
NO_COMMAND = "this DOSBox-X's debugger channel has no PRESENCE command"
#: What an output the emulator cannot draw on is said to be.
NO_OUTPUT = ("this output cannot be drawn on (an 8-bit output, or the TrueType output while it "
             "shows text)")
#: What a session started without a window is said to lack.
NO_WINDOW = "a session started without `shared` has no window to draw on"


def channel_args(look: presence.Look = presence.LOOK) -> str:
    """The look as `PRESENCE` takes it, one `key=value` word each."""
    return (f"rgb={look.rgb:06X} edge={look.edge:g} steps={look.steps} "
            f"acting={look.acting_alpha:.3f} held={look.held_alpha:.3f} fade={look.fade_s:g} "
            f"outline={look.pointer_outline_rgb:06X} size={look.pointer_size:g} "
            f"sprite={'/'.join(look.pointer)}")


class Channel(Protocol):
    """What the adapter sends on: a session's debugger channel."""

    def request(self, command: str, seconds: float = ...) -> tuple[bool, list[str]]: ...


class HasChannel(Protocol):
    @property
    def control(self) -> Channel: ...


class ChannelAdapter:
    """`scry_core.presence.Adapter` over a session's debugger channel, read at each delivery so
    a failure to reach it is that delivery's. `pointer` turns the arrow on, from the session's
    first mouse move on."""

    def __init__(self, session: HasChannel, look: presence.Look = presence.LOOK) -> None:
        self._session = session
        self._args = channel_args(look)
        self.pointer = False
        #: The emulator's last answer (what it drew, how many frames, on which output), which
        #: only the live matrix reads: section R counts frames off it.
        self.answer = ""

    def show(self, state: presence.State) -> None:
        ok, lines = self._session.control.request(
            f"PRESENCE {state} {self._args} pointer={int(self.pointer)}")
        said = " / ".join(lines) or "no reason given"
        if not ok:
            raise (presence.Unavailable(NO_COMMAND) if "unknown request command" in said
                   else RuntimeError(f"the debugger channel refused PRESENCE: {said}"))
        self.answer = lines[0] if lines else ""
        # `output=none` is not refused: a session parked at its start has drawn no frame yet,
        # and the overlay goes on the first one there is. An output it can never draw on is.
        if "output=undrawable" in self.answer.split():
            raise presence.Unavailable(NO_OUTPUT)


def pointer_moved(shown: presence.Shown) -> None:
    """The session moved the guest's mouse: the arrow is drawn from now on."""
    adapter = shown.adapter
    if shown.held is None or not isinstance(adapter, ChannelAdapter) or adapter.pointer:
        return
    adapter.pointer = True
    shown.held.redeliver()


NEVER_DRAWN = presence.Shown()


def of(session: object) -> presence.Shown:
    """The presence of whatever holds the session's place: a stand-in for the session that
    carries none (the suite's doubles) reads as one never drawn."""
    shown = getattr(session, "presence", NEVER_DRAWN)
    return shown if isinstance(shown, presence.Shown) else NEVER_DRAWN


def open_shown(session: HasChannel, asked: bool, shared: bool) -> presence.Shown:
    """A session's presence, its first state delivered before `start` answers: unavailable with
    why on a session with no window, on a build whose channel has no `PRESENCE`, or on an output
    the emulator cannot draw on."""
    if not asked:
        return presence.Shown()
    if not shared:
        return presence.Shown(refused=unavailable(NO_WINDOW))
    return presence.Presence.open(ChannelAdapter(session), DRIVING_TOOLS)


def frames(answer: str) -> int | None:
    """The frames the emulator drew the overlay on, read off its answer, or None: the live
    matrix's count."""
    for word in answer.split():
        if word.startswith("frames=") and word[len("frames="):].isdigit():
            return int(word[len("frames="):])
    return None
