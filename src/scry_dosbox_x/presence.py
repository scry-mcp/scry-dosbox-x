"""Presence on DOSBox-X: the edge, a pointer, and from protocol 3 the captions, the keycaps and
the pause mark, drawn by the emulator's `PRESENCE` command.

It draws into the scaled output after the frame went to capture, so no capture or screen read
carries it. The pointer appears once the session has moved the guest's mouse. A build that
announces protocol 2 is sent only what protocol 2 parses; the layers it lacks are named in the
`overlay` of `start` and `status`; so is a build of protocol 3 that predates the record mark.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from typing import Any, Protocol

from pydantic import ValidationError
from scry_core import overlay as ov
from scry_core import presence
from scry_core.reply_contract import Invalid, unavailable

from scry_dosbox_x import debugger as dbg

#: The two sides `scry_core.presence.check_classified` holds against the registry. `snapshot`
#: is still: its capture trigger changes nothing the guest reads.
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
#: The version that takes the layers of `overlay`.
PROTOCOL = 3
#: The layers a build of protocol 2 draws.
PROTOCOL_2_LAYERS = frozenset({"edge", "pointer"})
#: What the command takes of a caption and of the keys, in bytes.
CAPTION_BYTES = 160
KEY_BYTES = 12
KEYS_SHOWN = 8
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
    """The look, as the words every version of the command parses."""
    return (f"rgb={look.rgb:06X} edge={look.edge:g} steps={look.steps} "
            f"acting={look.acting_alpha:.3f} held={look.held_alpha:.3f} fade={look.fade_s:g} "
            f"outline={POINTER_OUTLINE_RGB:06X} glide={POINTER_GLIDE_S:g} "
            f"sprite={'/'.join(POINTER)}")


def caption_args(look: presence.Look = presence.LOOK) -> str:
    """The look of the layers protocol 3 added, as `Look` holds it: the command takes the scroll
    speed in characters a second and keeps its own fades."""
    return (f"caption_text_rgb={look.caption_text_rgb:06X} caption_alpha={look.caption_alpha:g} "
            f"keycap_rgb={look.keycap_rgb:06X} keycap_text_rgb={look.keycap_text_rgb:06X} "
            f"keycap_alpha={look.keycap_alpha:g} scroll_cps={look.scroll_cps:g}")


def record_args(look: presence.Look = presence.LOOK) -> str:
    """The look of the record mark, for a build that draws it."""
    return f"record_rgb={look.record_rgb:06X} record_blink_s={look.record_blink_s:g}"


def encoded(text: str, limit: int) -> str:
    """`text` as one word of the command: at most `limit` ASCII bytes, a space, a percent sign
    and any other byte outside the printable range as `%XX`."""
    data = text.encode("ascii", "replace")[:limit]
    return "".join(chr(b) if 0x21 <= b <= 0x7E and b != 0x25 else f"%{b:02X}" for b in data)


def words(answer: str) -> dict[str, str]:
    """The `key=value` words of an answer."""
    return dict(w.split("=", 1) for w in answer.split() if "=" in w)


class Debugger(Protocol):
    def has(self, command: str) -> bool: ...
    def exec(self, command: str, seconds: float | None = None, *,
             unless_silent: bool = False) -> tuple[bool, list[str]]: ...


class ChannelAdapter:
    """`scry_core.presence.Adapter` over a session's debugger, read at each delivery."""

    def __init__(self, session: Debugger, look: presence.Look = presence.LOOK,
                 overlay: ov.Overlay = ov.OVERLAY,
                 drawn: Collection[str] = ov.LAYERS) -> None:
        """`drawn`: the layers the build's PRESENCE can draw (`binary.presence_layers`), of
        which a build of protocol 2 draws only its own two."""
        self._session = session
        self._args = channel_args(look)
        self._caption_args = caption_args(look)
        self._record_args = record_args(look)
        self._overlay = overlay
        self._drawn = frozenset(drawn)
        # The caption the emulator holds, as last delivered: sent once, and again when its serial,
        # text or tint changes (a call that ended refused).
        self._caption: tuple[int, str, int] | None = None
        self.answer = ""
        self.version: int | None = None

    def show(self, state: presence.State, payload: presence.Payload) -> None:
        if not self._session.has("PRESENCE"):
            raise presence.Unavailable(NO_COMMAND)
        if self.version is None:
            self.version = build_version(self._session.exec("PRESENCE", unless_silent=True)[1])
        if self.version < MIN_VERSION:
            raise presence.Unavailable(
                f"this DOSBox-X's PRESENCE is version {self.version}, which draws the pointer at a "
                f"share of the window; version {MIN_VERSION} sizes it by the guest's pixels")
        line = (f"PRESENCE {self._state(state, payload)} {self._args} "
                f"pointer={int(payload.pointer is not None)}")
        caption = self._caption
        if self.version >= PROTOCOL:
            more, caption = self._protocol_words(payload)
            line += more
        # The writer retries a delivery refused on a silent channel on its own.
        ok, lines = self._session.exec(line, unless_silent=True)
        if not ok:
            if lines == [dbg.NOT_RECOGNIZED]:
                raise presence.Unavailable(NO_COMMAND)
            said = " / ".join(lines) or "no reason given"
            raise RuntimeError(f"the debugger refused PRESENCE: {said}")
        self._caption = caption
        self.answer = lines[0] if lines else ""
        # `output=none` is not refused: no frame has been drawn yet at the parked start.
        if "output=undrawable" in self.answer.split():
            raise presence.Unavailable(NO_OUTPUT)

    def _state(self, state: presence.State, payload: presence.Payload) -> str:
        """`paused` is a state of the command from protocol 3; before it the edge stays `held`."""
        paused = state == "held" and payload.paused and (self.version or 0) >= PROTOCOL
        return "paused" if paused else state

    def _protocol_words(self, payload: presence.Payload
                        ) -> tuple[str, tuple[int, str, int] | None]:
        """The words protocol 3 adds, and the caption the emulator holds once they are taken. A
        caption goes only when it is a new one or leaves."""
        layers = [layer for layer in payload.layers if layer in self._drawn]
        out = [f" layers={','.join(layers)} place={payload.place} {self._caption_args}"]
        if "record" in self._drawn:
            out.append(f" rec={payload.recording} {self._record_args}")
        if "keys" in payload.layers:
            out.append(" keys=" + ",".join(
                encoded(name, KEY_BYTES) for name in payload.keys[-KEYS_SHOWN:]))
        caption = payload.caption if "calls" in payload.layers else None
        held = None if caption is None else (caption.serial, caption.text, caption.rgb)
        if held != self._caption:
            out.append(" caption=" + ("" if caption is None
                                      else encoded(caption.text, CAPTION_BYTES)
                                      + f" serial={caption.serial} tint={caption.rgb:06X}"))
        return "".join(out), held

    def overlay_reply(self) -> ov.OverlayReply:
        """The `overlay` of `start` and `status`: the layers the last answer says are drawn."""
        asked = self._overlay.asked()
        said = words(self.answer)
        lacking: dict[ov.Layer, str] = {}
        if (self.version or 0) < PROTOCOL:
            why = (f"this DOSBox-X's PRESENCE is version {self.version}, which draws the edge and "
                   f"the pointer; version {PROTOCOL} draws this layer")
            lacking = {layer: why for layer in asked if layer not in PROTOCOL_2_LAYERS}
            return ov.reply(self._overlay, lacking)
        for layer in asked:
            if layer not in self._drawn:
                lacking[layer] = (
                    f"this DOSBox-X's PRESENCE is version {self.version}, but its build predates "
                    "the record mark" if layer == "record" else
                    f"this DOSBox-X's PRESENCE is version {self.version}, which does not draw "
                    "this layer")
        output = said.get("output", "none")
        lacks = set(said.get("lacks", "").split(","))
        for layer in asked:
            if layer in lacks and layer not in lacking:
                lacking[layer] = f"this DOSBox-X's output ({output}) cannot draw this layer"
        place = said.get("place")
        return ov.reply(self._overlay, lacking,
                        "top" if place == "top" else "bottom" if place == "bottom" else None)

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


def overlay_of(value: object) -> ov.Overlay:
    """`start`'s `overlay`: the model, or the object a profile holds, judged as the model."""
    if isinstance(value, ov.Overlay):
        return value
    try:
        return ov.Overlay.model_validate(value)
    except ValidationError as e:
        raise Invalid("bad_argument", f"overlay: {e.errors()[0]['loc']} {e.errors()[0]['msg']}; "
                      f"it takes the booleans calls, keys, pointer and pause, and place "
                      f"(top, bottom or auto)") from None


def keys_sent(shown: presence.Shown, keys: Iterable[str], modifiers: Iterable[str],
              action: str) -> None:
    """Report a `send_keys` that went in: the modifiers and the keys held by `press` and `down`,
    let go by `press` and `up`."""
    names = [name.lower() for name in (*modifiers, *keys)]
    if action != "up":
        for name in names:
            shown.key(name, True)
    if action != "down":
        for name in reversed(names):
            shown.key(name, False)


def mouse_sent(shown: presence.Shown, reply: dict[str, Any], x: int | None, y: int | None,
               button: str | None, action: str) -> None:
    """Report a `send_mouse` that went in: the pointer where the driver now reports it, else
    where it was sent, then the button's presses."""
    where: dict[str, Any] = {}
    pointer = reply.get("pointer")
    if isinstance(pointer, dict):
        screen = pointer.get("screen")
        mouse = pointer.get("mouse")
        where = screen if isinstance(screen, dict) and "x" in screen else (
            mouse if isinstance(mouse, dict) else {})
    shown.moved(int(where.get("x", x or 0)), int(where.get("y", y or 0)))
    if button is None:
        return
    if action != "up":
        shown.button(button, True)
    if action != "down":
        shown.button(button, False)


def overlay_shown(shown: presence.Shown) -> dict[str, Any]:
    """`{"overlay": ...}` for a session whose presence is drawn, and nothing for one that is
    off or cannot be."""
    adapter = shown.adapter
    if shown.held is None or shown.reply() is not True or not isinstance(adapter, ChannelAdapter):
        return {}
    return {"overlay": adapter.overlay_reply()}


NEVER_DRAWN = presence.Shown()


def of(session: object) -> presence.Shown:
    """The session's presence; a stand-in with none reads as never drawn."""
    shown = getattr(session, "presence", NEVER_DRAWN)
    return shown if isinstance(shown, presence.Shown) else NEVER_DRAWN


def open_shown(session: Debugger, asked: bool, shared: bool,
               overlay: ov.Overlay = ov.OVERLAY,
               drawn: Collection[str] = ov.LAYERS) -> presence.Shown:
    """A session's presence, its first state delivered before `start` answers."""
    if not asked:
        return presence.Shown()
    if not shared:
        return presence.Shown(refused=unavailable(NO_WINDOW))
    return presence.Presence.open(ChannelAdapter(session, overlay=overlay, drawn=drawn),
                                  DRIVING_TOOLS,
                                  overlay=overlay)


def frames(answer: str) -> int | None:
    word = words(answer).get("frames", "")
    return int(word) if word.isdigit() else None
