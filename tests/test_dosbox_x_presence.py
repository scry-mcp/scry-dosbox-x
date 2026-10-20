"""`dosbox_presence`: which tools drive, held against the registry; the look as the channel's
`PRESENCE` takes it; what the emulator's answers mean (drawn, a build without the command, an
output it cannot draw on); a session with no window; the arrow turned on by the first mouse
move; and a start plan lighting the window."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from scry_core import presence

import dosbox_control as control
import dosbox_lifecycle as lifecycle
import dosbox_presence as dpresence
import dosbox_x_server as server


def test_every_registered_tool_is_declared_driving_or_still_and_no_other() -> None:
    registered = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert presence.check_classified(registered, dpresence.DRIVING_TOOLS,
                                     dpresence.STILL_TOOLS) == []


def test_the_look_goes_to_the_channel_one_word_per_key_with_its_arrow() -> None:
    words = dict(w.split("=", 1) for w in dpresence.channel_args().split(" "))
    assert list(words) == ["rgb", "edge", "steps", "acting", "held", "fade", "outline", "size",
                           "sprite"]
    look = presence.LOOK
    assert words == {"rgb": f"{look.rgb:06X}", "edge": f"{look.edge:g}",
                     "steps": str(look.steps), "acting": f"{look.acting_alpha:.3f}",
                     "held": f"{look.held_alpha:.3f}", "fade": f"{look.fade_s:g}",
                     "outline": f"{look.pointer_outline_rgb:06X}",
                     "size": f"{look.pointer_size:g}", "sprite": "/".join(look.pointer)}


class _Channel:
    def __init__(self, answers: list[tuple[bool, list[str]]]) -> None:
        self.answers = answers
        self.sent: list[str] = []

    def request(self, command: str, seconds: float = control.REPLY_S) -> tuple[bool, list[str]]:
        self.sent.append(command)
        return self.answers.pop(0)


class _Session:
    def __init__(self, *answers: tuple[bool, list[str]]) -> None:
        self.control = _Channel(list(answers))


def _shown(*answers: tuple[bool, list[str]], asked: bool = True,
           shared: bool = True) -> tuple[dpresence.Shown, _Channel]:
    s = _Session(*answers)
    return dpresence.open_shown(s, asked, shared), s.control


DRAWN = (True, ["PRESENCE held frames=3 pointer=0 output=640x400x32"])


def test_a_build_with_the_command_is_drawn_and_its_answer_kept() -> None:
    shown, channel = _shown(DRAWN)
    assert shown.reply() is True
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert channel.sent[0].endswith(" pointer=0")
    assert shown.adapter is not None and dpresence.frames(shown.adapter.answer) == 3
    shown.close()


@pytest.mark.parametrize(("answer", "why"), [
    ((False, ["unknown request command"]), dpresence.NO_COMMAND),
    ((False, ["PRESENCE edge=9 is not a value it takes"]), "refused PRESENCE"),
])
def test_what_the_emulator_cannot_draw_is_said_in_place_of_true(
        answer: tuple[bool, list[str]], why: str) -> None:
    shown, _ = _shown(answer)
    said = shown.reply()
    assert isinstance(said, dict) and said["available"] is False and why in said["why"], said
    assert shown.held is None


def test_a_session_with_no_window_or_asked_off_sends_nothing() -> None:
    headless, quiet = _shown(shared=False)
    assert headless.reply() == {"available": False, "why": dpresence.NO_WINDOW}
    off, silent = _shown(asked=False)
    assert off.reply() is False
    assert quiet.sent == silent.sent == []


def test_status_says_false_with_no_session_and_unavailable_once_the_emulator_ended() -> None:
    assert lifecycle.presence_shown(None) is False

    class Ended:
        presence = dpresence.Shown(refused=True)

        def alive(self) -> bool:
            return False
    said = lifecycle.presence_shown(Ended())  # type: ignore[arg-type]
    assert isinstance(said, dict) and said["available"] is False, said


def test_a_stand_in_with_no_presence_reads_as_never_drawn() -> None:
    assert dpresence.of(object()).reply() is False
    assert dpresence.of(None).held is None


def test_the_first_mouse_move_turns_the_arrow_on_once() -> None:
    shown, channel = _shown(DRAWN, DRAWN, DRAWN)
    shown.pointer_moved()
    shown.pointer_moved()
    deadline = time.monotonic() + 5
    while len(channel.sent) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)
    assert len(channel.sent) == 2 and channel.sent[1].endswith(" pointer=1"), channel.sent
    shown.close()
    dpresence.Shown().pointer_moved()      # no presence: nothing to turn on


def test_a_start_parked_before_its_first_frame_is_still_drawn_once_there_is_one() -> None:
    shown, _ = _shown((True, ["PRESENCE held frames=0 pointer=0 output=none"]))
    assert shown.reply() is True
    shown.close()


def test_frames_reads_the_count_and_nothing_else() -> None:
    assert dpresence.frames("PRESENCE acting frames=12 pointer=1 output=1x1x32") == 12
    assert dpresence.frames("PRESENCE acting") is None


def test_a_start_plan_lights_the_window_while_it_runs(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    from test_dosbox_x_server import _start_on_a_booted_fake

    import dosbox_state as dstate
    shown: list[str] = []
    during: list[str] = []

    class Shows:
        def show(self, state: presence.State) -> None:
            shown.append(state)

    def lit(session: Any, asked: bool, shared: bool) -> dpresence.Shown:
        held, refused = presence.Presence.open(Shows(), {"perform"})
        return dpresence.Shown(held, refused)

    import dosbox_sequence as sequence
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
    import dosbox_inputs as inputs
    import dosbox_running as running
    import dosbox_state as dstate
    delivered = {"status": "ok", "delivered": True}

    def died(*_a: Any, **_k: Any) -> dict[str, Any]:
        dstate.STATE.session = None            # the emulator went while the move went in
        return delivered
    asked: list[int] = []

    def live() -> object:
        """A session the first time, buried after it, as `live()` buries a dead one."""
        asked.append(1)
        if len(asked) > 1:
            raise RuntimeError("no live session")
        return object()
    monkeypatch.setattr(running, "live", live)
    monkeypatch.setattr(server, "live", live)
    monkeypatch.setattr(inputs, "send_mouse", died)
    out = server.send_mouse(x=1, y=1)
    assert out["status"] == "ok" and out["delivered"] is True, out
