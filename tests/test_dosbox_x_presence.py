"""`presence`: which tools drive, held against the registry; the look as the channel's
`PRESENCE` takes it; what the emulator's answers mean (drawn, a build without the command, an
output it cannot draw on); a session with no window; the pointer turned on by the first mouse
move; and a start plan lighting the window."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from scry_core import presence

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import lifecycle, server
from scry_dosbox_x import presence as dpresence


def test_every_registered_tool_is_declared_driving_or_still_and_no_other() -> None:
    registered = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert presence.check_classified(registered, dpresence.DRIVING_TOOLS,
                                     dpresence.STILL_TOOLS) == []


def test_the_look_goes_to_the_channel_one_word_per_key_with_its_pointer() -> None:
    words = dict(w.split("=", 1) for w in dpresence.channel_args().split(" "))
    assert list(words) == ["rgb", "edge", "steps", "acting", "held", "fade", "outline", "glide",
                           "sprite"]
    look = presence.LOOK
    assert words == {"rgb": f"{look.rgb:06X}", "edge": f"{look.edge:g}",
                     "steps": str(look.steps), "acting": f"{look.acting_alpha:.3f}",
                     "held": f"{look.held_alpha:.3f}", "fade": f"{look.fade_s:g}",
                     "outline": f"{dpresence.POINTER_OUTLINE_RGB:06X}",
                     "glide": f"{dpresence.POINTER_GLIDE_S:g}",
                     "sprite": "/".join(dpresence.POINTER)}


class _Session:
    """The session's debugger: the commands its build parses, and what each `exec` prints."""

    def __init__(self, *answers: tuple[bool, list[str]],
                 commands: frozenset[str] = frozenset({"PRESENCE"})) -> None:
        self.answers = list(answers)
        self.commands = commands
        self.sent: list[str] = []
        self.bare: tuple[bool, list[str]] = (
            True, ["PRESENCE off frames=0 pointer=0 output=none version=2"])

    def has(self, command: str) -> bool:
        return command in self.commands

    def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
        if command == "PRESENCE":
            return self.bare
        self.sent.append(command)
        return self.answers.pop(0)


def _shown(*answers: tuple[bool, list[str]], asked: bool = True, shared: bool = True,
           commands: frozenset[str] = frozenset({"PRESENCE"})) -> tuple[presence.Shown, _Session]:
    s = _Session(*answers, commands=commands)
    return dpresence.open_shown(s, asked, shared), s


DRAWN = (True, ["PRESENCE held frames=3 pointer=0 output=640x400x32"])


def test_a_build_with_the_command_is_drawn_and_its_answer_kept() -> None:
    shown, channel = _shown(DRAWN)
    assert shown.reply() is True
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert channel.sent[0].endswith(" pointer=0")
    assert isinstance(shown.adapter, dpresence.ChannelAdapter)
    assert dpresence.frames(shown.adapter.answer) == 3
    shown.close()


def test_a_build_whose_debugger_has_no_presence_command_is_said_unavailable_unsent() -> None:
    shown, debugger = _shown(commands=frozenset())
    said = shown.reply()
    assert said == {"available": False, "why": dpresence.NO_COMMAND}, said
    assert debugger.sent == [] and shown.held is None


def test_a_build_naming_presence_whose_debugger_does_not_parse_it_is_said_unavailable() -> None:
    """The bytes say PRESENCE, as the channel's own verb did; the debugger does not know it."""
    shown, _ = _shown((False, [dbg.NOT_RECOGNIZED]))
    assert shown.reply() == {"available": False, "why": dpresence.NO_COMMAND}


def test_what_the_command_refuses_is_said_in_place_of_true() -> None:
    """Captured off the build: a refusal names its reason, then the debugger's own line."""
    shown, _ = _shown((False, ["PRESENCE does not know the argument size", dbg.NOT_RECOGNIZED]))
    said = shown.reply()
    assert isinstance(said, dict) and said["available"] is False
    assert "refused PRESENCE" in said["why"] and "argument size" in said["why"], said
    assert dbg.NOT_RECOGNIZED not in said["why"], "the command was recognised; only a key was not"
    assert shown.held is None


def test_a_session_with_no_window_or_asked_off_sends_nothing() -> None:
    headless, quiet = _shown(shared=False)
    assert headless.reply() == {"available": False, "why": dpresence.NO_WINDOW}
    off, silent = _shown(asked=False)
    assert off.reply() is False
    assert quiet.sent == silent.sent == []


def test_status_says_unavailable_once_the_emulator_ended() -> None:
    class Ended:
        presence = presence.Shown(refused=True)

        def alive(self) -> bool:
            return False
    said = lifecycle.presence_shown(Ended())  # type: ignore[arg-type]
    assert isinstance(said, dict) and said["available"] is False, said


def test_a_stand_in_with_no_presence_reads_as_never_drawn() -> None:
    assert dpresence.of(object()).reply() is False
    assert dpresence.of(None).held is None


def test_the_first_mouse_move_turns_the_pointer_on_once() -> None:
    shown, channel = _shown(DRAWN, DRAWN, DRAWN)
    dpresence.pointer_moved(shown)
    dpresence.pointer_moved(shown)
    deadline = time.monotonic() + 5
    while len(channel.sent) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)
    assert len(channel.sent) == 2 and channel.sent[1].endswith(" pointer=1"), channel.sent
    shown.close()
    dpresence.pointer_moved(presence.Shown())      # no presence: nothing to turn on


def test_an_output_the_emulator_cannot_draw_on_is_said_unavailable() -> None:
    shown, _ = _shown((True, ["PRESENCE held frames=0 pointer=0 output=undrawable"]))
    said = shown.reply()
    assert isinstance(said, dict) and said["why"] == dpresence.NO_OUTPUT, said
    assert shown.held is None


def test_a_start_parked_before_its_first_frame_is_still_drawn_once_there_is_one() -> None:
    shown, _ = _shown((True, ["PRESENCE held frames=0 pointer=0 output=none"]))
    assert shown.reply() is True
    shown.close()


def test_frames_reads_the_count_and_nothing_else() -> None:
    assert dpresence.frames("PRESENCE acting frames=12 pointer=1 output=1x1x32") == 12
    assert dpresence.frames("PRESENCE acting") is None


def test_a_start_plan_lights_the_window_while_it_runs(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake

    from scry_dosbox_x import state as dstate
    shown: list[str] = []
    during: list[str] = []

    class Shows:
        def show(self, state: presence.State) -> None:
            shown.append(state)

        def repaint(self, still: Callable[[], bool]) -> None:
            """A guest parked at the debugger draws on its own."""

        def wake(self) -> None:
            """No repaint waits here."""

    def lit(session: Any, asked: bool, shared: bool) -> presence.Shown:
        return presence.Presence.open(Shows(), ())

    from scry_dosbox_x import sequence
    real = sequence.run_steps

    def watched(session: Any, *a: Any, **k: Any) -> Any:
        during.append(session.presence.held._want)
        return real(session, *a, **k)
    monkeypatch.setattr(dpresence, "open_shown", lit)
    monkeypatch.setattr(sequence, "run_steps", watched)
    dstate.STATE.session = None
    out = _start_on_a_booted_fake(tmp_path, monkeypatch, plan=[{"op": "registers"}])
    assert out["status"] == "ok", out
    session: Any = dstate.STATE.session       # read after the start, which mypy cannot see set it
    assert session is not None and session.presence.held is not None
    assert during == ["acting"] and session.presence.held._want == "held"
    session.presence.close()
    dstate.STATE.session = None


def test_a_mouse_move_keeps_its_reply_when_the_session_dies_after_it(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import inputs, running
    from scry_dosbox_x import state as dstate
    delivered = {"status": "ok", "delivered": True, "route": "guest",
                 "pointer": {"x": 1, "y": 1}, "arrived": True,
                 "verify": {"checked": False, "why": "no expect"}}

    def died(*_a: Any, **_k: Any) -> dict[str, Any]:
        dstate.STATE.session = None            # the emulator went while the move went in
        return delivered
    asked: list[int] = []

    def live(probe: bool = True) -> object:
        """A session the first time, refused after it, as `live()` refuses a dead one."""
        asked.append(1)
        if len(asked) > 1:
            raise RuntimeError("no live session")
        return object()
    monkeypatch.setattr(running, "live", live)
    monkeypatch.setattr(server, "live", live)
    monkeypatch.setattr(inputs, "send_mouse", died)
    out = server.send_mouse(x=1, y=1)
    assert out["status"] == "ok" and out["delivered"] is True, out


def test_a_mouse_event_that_was_not_sent_leaves_the_pointer_off(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import inputs, running
    not_sent = {"status": "INVALID", "code": "host_failed", "delivered": False,
                "message": "the mouse event was NOT sent", "x": 1, "y": 1, "units": "screen",
                "verify": {"checked": False, "why": "nothing was sent"}}
    turned_on: list[object] = []
    monkeypatch.setattr(running, "live", lambda probe=True: object())
    monkeypatch.setattr(server, "live", lambda probe=True: object())
    monkeypatch.setattr(inputs, "send_mouse", lambda *_a, **_k: not_sent)
    monkeypatch.setattr(dpresence, "pointer_moved", turned_on.append)
    out = server.send_mouse(x=1, y=1)
    assert out["delivered"] is False and turned_on == [], (out, turned_on)


@pytest.mark.parametrize("bare, said", [
    ((False, ["PRESENCE needs a state", dbg.NOT_RECOGNIZED]), "version 1"),
    ((True, ["PRESENCE off frames=0 pointer=0 output=none version=1"]), "version 1"),
])
def test_a_build_older_than_the_pointers_pixel_size_is_said_unavailable_by_version(
        bare: tuple[bool, list[str]], said: str) -> None:
    session = _Session(commands=frozenset({"PRESENCE"}))
    session.bare = bare
    shown = dpresence.open_shown(session, True, True)
    why = shown.reply()
    assert isinstance(why, dict) and why["available"] is False and said in why["why"], why
    assert session.sent == [], "nothing was drawn on a build that would draw it wrong"


def test_a_build_names_its_version_in_the_bare_answer() -> None:
    assert dpresence.build_version(["PRESENCE off frames=0 pointer=0 output=none version=2"]) == 2
    assert dpresence.build_version(["PRESENCE needs a state"]) == 1


#: The INT 33h driver's default pointer, as DOSBox-X's driver holds it: a pixel is drawn where
#: the screen mask bit is clear, white where the cursor bit is set, else black.
SCREEN_MASK = (0x3FFF, 0x1FFF, 0x0FFF, 0x07FF, 0x03FF, 0x01FF, 0x00FF, 0x007F,
               0x003F, 0x001F, 0x01FF, 0x00FF, 0x30FF, 0xF87F, 0xF87F, 0xFCFF)
CURSOR_MASK = (0x0000, 0x4000, 0x6000, 0x7000, 0x7800, 0x7C00, 0x7E00, 0x7F00,
               0x7F80, 0x7C00, 0x6C00, 0x4600, 0x0600, 0x0300, 0x0300, 0x0000)


def test_the_pointer_is_the_dos_drivers_own_pointer() -> None:
    rows = ["".join("." if s >> b & 1 else "o" if c >> b & 1 else "X" for b in range(15, -1, -1))
            for s, c in zip(SCREEN_MASK, CURSOR_MASK, strict=True)]
    width = len(dpresence.POINTER[0])
    assert all(r[width:] == "." * (16 - width) for r in rows)
    assert tuple(r[:width] for r in rows) == dpresence.POINTER
