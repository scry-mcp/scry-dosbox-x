"""`presence`: which tools drive, held against the registry; the look as the channel's
`PRESENCE` takes it; what the emulator's answers mean (drawn, a build without the command, an
output it cannot draw on, a build of another protocol refused); a session with no window; the
pointer turned on by the first mouse move; and a start plan lighting the window. The words of
the layers protocol and the `overlay` of `start` and `status`."""

from __future__ import annotations

import asyncio
import contextlib
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core import overlay as ov
from scry_core import presence
from scry_core.reply_contract import Invalid

from scry_dosbox_x import control, lifecycle, server
from scry_dosbox_x import debugger as dbg
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


#: What the fork's `Describe` prints and what its parser refuses, which the fork's own tests hold
#: to the code; the server's cases below are about what it does with those words.
BARE = "PRESENCE off frames=0 pointer=0 output=none"
DRAWN = (True, ["PRESENCE held frames=65 pointer=0 output=720x400x32 px_read=46144 "
                "px_written=72240 bytes_presented=1256640 uploads=0 upload_bytes=0 "
                "layers=edge,pointer,record"])
UNDRAWABLE = (True, ["PRESENCE held frames=0 pointer=0 output=undrawable layers= "
                     "lacks=edge,pointer,record"])
ACTING = (True, ["PRESENCE acting frames=0 pointer=0 output=none"])
REFUSAL = (False, ["PRESENCE does not know the argument bogus",
                   "*** Debugger command not recognized"])


class _Session:
    """The session's debugger: the commands its build parses, and what each `exec` prints."""

    def __init__(self, *answers: tuple[bool, list[str]],
                 commands: frozenset[str] = frozenset({"PRESENCE"}), version: int = 4) -> None:
        self.answers = list(answers)
        self.commands = commands
        self.sent: list[str] = []
        self.bare = (True, [f"{BARE} version={version}"])

    def has(self, command: str) -> bool:
        return command in self.commands

    def exec(self, command: str, seconds: float | None = None, *,
             unless_silent: bool = False) -> tuple[bool, list[str]]:
        if command == "PRESENCE":
            return self.bare
        self.sent.append(command)
        return self.answers.pop(0)


def _shown(*answers: tuple[bool, list[str]], asked: bool = True, shared: bool = True,
           commands: frozenset[str] = frozenset({"PRESENCE"}), version: int = 4,
           overlay: ov.Overlay = ov.OVERLAY) -> tuple[presence.Shown, _Session]:
    s = _Session(*answers, commands=commands, version=version)
    return dpresence.open_shown(s, asked, shared, overlay), s


def test_a_build_with_the_command_is_drawn_and_its_answer_kept() -> None:
    shown, channel = _shown(DRAWN)
    assert shown.reply() is True
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert " pointer=0 " in channel.sent[0]
    assert isinstance(shown.adapter, dpresence.ChannelAdapter)
    assert shown.adapter.answer == DRAWN[1][0]
    assert dpresence.frames(shown.adapter.answer) == 65
    shown.close()


@pytest.mark.parametrize("version", [dpresence.PROTOCOL, None])
def test_a_delivery_that_waited_behind_a_request_the_channel_left_unanswered_is_not_sent(
        version: int | None) -> None:
    """The delivery is asked while another request still waits on the silent channel; with no
    version read yet, its bare probe is not sent either."""
    channel = control.ControlChannel(lambda: None)
    emulator = socket.create_connection((control.LOCAL_HOST, channel.port))
    heard: list[bytes] = []

    class OverChannel:
        control, commands = channel, frozenset({"PRESENCE"})

        def has(self, command: str) -> bool:
            return command in self.commands

        def exec(self, command: str, seconds: float | None = None,
                 **kw: Any) -> tuple[bool, list[str]]:
            return dbg.exec_lines(cast(Any, self), command, seconds, **kw)
    adapter = dpresence.ChannelAdapter(cast(Any, OverChannel()))
    adapter.version = version
    def unanswered() -> None:
        with contextlib.suppress(Invalid):
            channel.request("EXEC RUNSTATE", 0.3)
    tool = threading.Thread(target=unanswered)
    try:
        tool.start()
        time.sleep(0.05)
        with contextlib.suppress(Exception):
            adapter.show("acting", presence.Payload())
        tool.join()
        emulator.settimeout(0.2)
        with contextlib.suppress(TimeoutError):
            while got := emulator.recv(4096):
                heard.append(got)
    finally:
        emulator.close()
        channel.close()
    assert b"PRESENCE" not in b"".join(heard), heard


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
    """A refusal is the build's reason alone."""
    shown, _ = _shown(REFUSAL)
    said = shown.reply()
    assert isinstance(said, dict) and said["available"] is False
    assert said["why"] == ("the first delivery failed: RuntimeError: the debugger refused "
                           "PRESENCE: PRESENCE does not know the argument bogus / *** Debugger "
                           "command not recognized"), said
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


def _sent(channel: _Session, count: int) -> list[str]:
    """What the writer sent once it has sent `count` lines, and a moment more."""
    deadline = time.monotonic() + 5
    while len(channel.sent) < count and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.1)
    return channel.sent


def test_the_first_mouse_move_turns_the_pointer_on_once() -> None:
    shown, channel = _shown(DRAWN, DRAWN, DRAWN)
    reply = {"pointer": {"screen": {"x": 3, "y": 4, "width": 320, "height": 200}}}
    dpresence.mouse_sent(shown, reply, 3, 4, None, "click")
    dpresence.mouse_sent(shown, reply, 3, 4, None, "click")
    sent = _sent(channel, 2)
    assert len(sent) == 2 and " pointer=1 " in sent[1], sent
    shown.close()
    dpresence.mouse_sent(presence.Shown(), reply, 3, 4, None, "click")   # no presence: nothing


def test_an_output_the_emulator_cannot_draw_on_is_said_unavailable() -> None:
    shown, _ = _shown(UNDRAWABLE)
    said = shown.reply()
    assert isinstance(said, dict) and said["why"] == dpresence.NO_OUTPUT, said
    assert shown.held is None


def test_a_start_parked_before_its_first_frame_is_still_drawn_once_there_is_one() -> None:
    shown, _ = _shown(ACTING)
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
        def show(self, state: presence.State, payload: presence.Payload) -> None:
            shown.append(state)

        def repaint(self, still: Callable[[], bool]) -> None:
            """A guest parked at the debugger draws on its own."""

        def wake(self) -> None:
            """No repaint waits here."""

    def lit(session: Any, asked: bool, shared: bool,
            overlay: ov.Overlay) -> presence.Shown:
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
    monkeypatch.setattr(dpresence, "mouse_sent", lambda *a: turned_on.append(a))
    out = server.send_mouse(x=1, y=1)
    assert out["delivered"] is False and turned_on == [], (out, turned_on)


def test_a_build_of_another_protocol_is_refused_by_name_and_nothing_is_sent() -> None:
    for version in (1, 2, 3, 5):
        session = _Session(commands=frozenset({"PRESENCE"}), version=version)
        shown = dpresence.open_shown(session, True, True)
        why = shown.reply()
        assert isinstance(why, dict) and why["available"] is False, why
        assert f"version {version}" in why["why"] and "needs version 4" in why["why"], why
        assert session.sent == [], "nothing is drawn on a build of another protocol"


def test_a_refused_bare_command_names_version_one() -> None:
    session = _Session(commands=frozenset({"PRESENCE"}))
    session.bare = (False, ["PRESENCE needs a state", dbg.NOT_RECOGNIZED])
    why = dpresence.open_shown(session, True, True).reply()
    assert isinstance(why, dict) and "needs version 4" in why["why"], why


def test_a_build_names_its_version_in_the_bare_answer() -> None:
    assert dpresence.build_version([f"{BARE} version=4"]) == 4
    assert dpresence.build_version(["PRESENCE needs a state"]) == 1


# ------------------------------------------------------------------------- the layers

ALL = ("edge", "pointer", "record")
NO_RECORD = ov.Overlay(record=False)


def _payload(**kw: Any) -> presence.Payload:
    return presence.Payload(layers=kw.pop("layers", ALL), **kw)


def _adapter(overlay: ov.Overlay = ov.OVERLAY
             ) -> tuple[dpresence.ChannelAdapter, _Session]:
    channel = _Session(DRAWN, DRAWN, DRAWN, DRAWN)
    return dpresence.ChannelAdapter(channel, overlay=overlay), channel


def _words(line: str) -> dict[str, str]:
    return dpresence.words(line)


def test_a_build_is_sent_the_layers_and_what_is_recorded() -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(recording="video"))
    sent = _words(channel.sent[0])
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert sent["layers"] == ",".join(ALL) and sent["rec"] == "video" and sent["pointer"] == "0"
    assert not {"place", "caption", "keys", "key_alpha", "tint", "scroll", "serial"} & set(sent), (
        "no word is sent that the command does not parse")


@pytest.mark.parametrize("recording", ["none", "video", "audio", "both"])
def test_the_record_mark_is_told_what_is_recorded_and_how_it_looks(
        recording: presence.Recording) -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(layers=ov.LAYERS, recording=recording))
    sent = _words(channel.sent[0])
    assert sent["layers"] == ",".join(ov.LAYERS) and sent["rec"] == recording
    assert (sent["record_rgb"], sent["record_blink_s"]) == (
        f"{presence.LOOK.record_rgb:06X}", f"{presence.LOOK.record_blink_s:g}")


def test_the_overlay_is_what_the_answer_says_and_nothing_more() -> None:
    adapter, _ = _adapter()
    adapter.show("held", _payload(layers=ov.LAYERS))
    assert adapter.overlay_reply() == {"layers": list(ov.LAYERS)}


def test_the_overlay_of_an_output_that_cannot_draw_names_each_layer_lacking() -> None:
    adapter, _ = _adapter()
    adapter.show("held", _payload())
    adapter.answer = UNDRAWABLE[1][0]
    said = adapter.overlay_reply()
    assert said["layers"] == [] and set(said["lacking"]) == set(ALL), said
    assert "undrawable" in said["lacking"]["edge"], said


def test_a_layer_not_asked_is_not_in_the_overlay() -> None:
    adapter, _ = _adapter(overlay=NO_RECORD)
    adapter.show("held", _payload())
    assert adapter.overlay_reply() == {"layers": ["edge", "pointer"]}


def test_a_start_asked_for_no_pointer_never_draws_one() -> None:
    shown, channel = _shown(DRAWN, DRAWN, DRAWN, overlay=ov.Overlay(pointer=False))
    assert shown.held is not None
    shown.held.moved(3, 4)
    time.sleep(0.2)
    assert all(_words(line)["pointer"] == "0" for line in channel.sent), channel.sent
    shown.close()


def test_start_and_status_say_the_overlay_only_of_a_presence_drawn() -> None:
    drawn, _ = _shown(DRAWN, overlay=NO_RECORD)
    assert dpresence.overlay_shown(drawn)["overlay"]["layers"] == ["edge", "pointer"]
    drawn.close()
    for none in (presence.Shown(), _shown(shared=False)[0], _shown(commands=frozenset())[0]):
        assert dpresence.overlay_shown(none) == {}, none
