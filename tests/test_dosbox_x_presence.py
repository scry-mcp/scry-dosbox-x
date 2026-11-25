"""`presence`: which tools drive, held against the registry; the look as the channel's
`PRESENCE` takes it; what the emulator's answers mean (drawn, a build without the command, an
output it cannot draw on); a session with no window; the pointer turned on by the first mouse
move; and a start plan lighting the window. The words of the layers protocol, the fallback on a
build of protocol 2, and the `overlay` of `start` and `status`."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
from collections.abc import Callable, Collection
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


#: The lines of two real builds, as their debugger printed them in a live session of this server.
CAPTURED = json.loads((Path(__file__).parent / "fixtures" / "presence-channel.json").read_text())


class _Session:
    """The session's debugger: the commands its build parses, and what each `exec` prints."""

    def __init__(self, *answers: tuple[bool, list[str]],
                 commands: frozenset[str] = frozenset({"PRESENCE"}), version: int = 2) -> None:
        self.answers = list(answers)
        self.commands = commands
        self.sent: list[str] = []
        # The latest captured build's words at the version this double announces: the fork
        # appends only its number to the line.
        source = "protocol2" if version == 2 else "protocol3"
        line = CAPTURED[source]["bare_before_output"][0]
        self.bare = (True, [line if version == 3 else
                            line.replace("version=3", f"version={version}")])

    def has(self, command: str) -> bool:
        return command in self.commands

    def exec(self, command: str, seconds: float | None = None, *,
             unless_silent: bool = False) -> tuple[bool, list[str]]:
        if command == "PRESENCE":
            return self.bare
        self.sent.append(command)
        return self.answers.pop(0)


def _shown(*answers: tuple[bool, list[str]], asked: bool = True, shared: bool = True,
           commands: frozenset[str] = frozenset({"PRESENCE"}), version: int = 2,
           overlay: ov.Overlay = ov.OVERLAY,
           drawn: Collection[str] = ov.LAYERS) -> tuple[presence.Shown, _Session]:
    s = _Session(*answers, commands=commands, version=version)
    return dpresence.open_shown(s, asked, shared, overlay, drawn), s


DRAWN = (True, CAPTURED["protocol2"]["drawn"])
DRAWN_3 = (True, CAPTURED["protocol3"]["drawn"])


def test_a_build_with_the_command_is_drawn_and_its_answer_kept() -> None:
    shown, channel = _shown(DRAWN)
    assert shown.reply() is True
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert channel.sent[0].endswith(" pointer=0")
    assert isinstance(shown.adapter, dpresence.ChannelAdapter)
    assert shown.adapter.answer == DRAWN[1][0]
    assert dpresence.frames(shown.adapter.answer) == 65
    shown.close()


@pytest.mark.parametrize("version", [dpresence.MIN_VERSION, None])
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
    """Captured off the build: a refusal is its reason alone."""
    shown, _ = _shown((False, CAPTURED["protocol2"]["refused_unknown_word"]))
    said = shown.reply()
    assert isinstance(said, dict) and said["available"] is False
    assert said["why"] == ("the first delivery failed: RuntimeError: the debugger refused "
                           "PRESENCE: PRESENCE does not know the argument bogus"), said
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
    assert len(sent) == 2 and sent[1].endswith(" pointer=1"), sent
    shown.close()
    dpresence.mouse_sent(presence.Shown(), reply, 3, 4, None, "click")   # no presence: nothing


def test_an_output_the_emulator_cannot_draw_on_is_said_unavailable() -> None:
    shown, _ = _shown((True, CAPTURED["protocol3"]["undrawable"]), version=3)
    said = shown.reply()
    assert isinstance(said, dict) and said["why"] == dpresence.NO_OUTPUT, said
    assert shown.held is None


def test_a_start_parked_before_its_first_frame_is_still_drawn_once_there_is_one() -> None:
    shown, _ = _shown((True, CAPTURED["protocol3"]["acting_before_output"]), version=3)
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

    def lit(session: Any, asked: bool, shared: bool, overlay: ov.Overlay,
            drawn: Collection[str]) -> presence.Shown:
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
    assert dpresence.build_version(CAPTURED["protocol2"]["bare_before_output"]) == 2
    assert dpresence.build_version(CAPTURED["protocol3"]["bare"]) == 3
    assert dpresence.build_version(["PRESENCE needs a state"]) == 1


# ------------------------------------------------------------------------- the layers

#: What a build with `PRESENCE` and the record mark draws.
ALL = ("edge", "pointer", "record")
NO_RECORD = ov.Overlay(record=False)


def _payload(**kw: Any) -> presence.Payload:
    return presence.Payload(layers=kw.pop("layers", ALL), **kw)


def _adapter(version: int = 4, overlay: ov.Overlay = ov.OVERLAY, drawn: Collection[str] = ALL,
             ) -> tuple[dpresence.ChannelAdapter, _Session]:
    channel = _Session(DRAWN_3, DRAWN_3, DRAWN_3, DRAWN_3, version=version)
    return dpresence.ChannelAdapter(channel, overlay=overlay, drawn=drawn), channel


def _words(line: str) -> dict[str, str]:
    return dpresence.words(line)


def test_a_build_is_sent_the_layers_it_draws_and_what_is_recorded() -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(recording="video"))
    sent = _words(channel.sent[0])
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert sent["layers"] == ",".join(ALL) and sent["rec"] == "video" and sent["pointer"] == "0"
    assert not {"place", "caption", "keys", "key_alpha", "tint", "serial"} & set(sent), (
        "no word is sent that the command does not parse")


@pytest.mark.parametrize("recording", ["none", "video", "audio", "both"])
def test_a_build_with_the_record_mark_is_told_what_is_recorded_and_how_the_mark_looks(
        recording: presence.Recording) -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(layers=ov.LAYERS, recording=recording))
    sent = _words(channel.sent[0])
    assert sent["layers"] == ",".join(ov.LAYERS) and sent["rec"] == recording
    assert (sent["record_rgb"], sent["record_blink_s"]) == (
        f"{presence.LOOK.record_rgb:06X}", f"{presence.LOOK.record_blink_s:g}")


def test_a_layer_not_asked_still_tells_a_build_with_the_record_mark_nothing_is_recorded() -> None:
    adapter, channel = _adapter(overlay=NO_RECORD)
    adapter.show("held", _payload())
    sent = _words(channel.sent[0])
    assert sent["layers"] == ",".join(ALL) and sent["rec"] == "none"


def test_a_build_without_the_record_mark_is_sent_no_word_it_rejects() -> None:
    adapter, channel = _adapter(drawn=("edge", "pointer"))
    adapter.show("held", _payload(layers=ov.LAYERS, recording="video"))
    line = channel.sent[0]
    assert "record" not in line and "rec=" not in line, line
    assert _words(line)["layers"] == "edge,pointer"


def test_what_a_build_without_the_record_mark_refuses_is_never_sent_to_it() -> None:
    """The refusals are 158f511fa's own, captured; a delivery that carried a word of them would
    lose the whole line."""
    refused = CAPTURED["protocol3"]
    argument = [refused[key][0].removeprefix("PRESENCE does not know the argument ")
                for key in ("refused_record_word", "refused_record_look")]
    layer = refused["refused_record_layer"][0].split()[1].removeprefix("layers=")
    assert argument == ["rec", "record_rgb"] and layer.endswith(",record"), refused
    adapter, channel = _adapter(drawn=("edge", "pointer"))
    adapter.show("held", _payload(layers=ov.LAYERS, recording="both"))
    sent = _words(channel.sent[0])
    assert not set(argument) & set(sent) and "record" not in sent["layers"].split(","), sent


def test_the_overlay_of_a_build_with_the_record_mark_draws_it_as_its_answer_says() -> None:
    recorded = CAPTURED["protocol3_record"]
    assert dpresence.build_version(recorded["bare"]) == 3
    assert "record" in _words(recorded["bare"][0])["layers"].split(",")
    adapter, _ = _adapter()
    adapter.show("held", _payload(layers=ov.LAYERS))
    adapter.answer = recorded["drawn"][0]
    assert adapter.overlay_reply() == {"layers": list(ov.LAYERS)}


def test_the_overlay_names_each_layer_the_build_is_not_drawing_and_not_only_the_record() -> None:
    adapter, channel = _adapter(drawn=("edge", "pointer"))
    adapter.show("held", _payload(layers=ov.LAYERS))
    assert _words(channel.sent[0])["layers"] == "edge,pointer"
    said = adapter.overlay_reply()
    assert set(said["lacking"]) == {"record"}, said


def test_a_start_hands_the_layers_its_build_draws_to_the_presence(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import dosbox_x_server_support as support
    from dosbox_x_server_support import _start_on_a_booted_fake

    from scry_dosbox_x import state as dstate
    handed: list[Collection[str]] = []

    def lit(session: Any, asked: bool, shared: bool, overlay: ov.Overlay,
            drawn: Collection[str]) -> presence.Shown:
        handed.append(drawn)
        return presence.Shown()
    monkeypatch.setattr(dpresence, "open_shown", lit)
    dstate.STATE.session = None
    out = _start_on_a_booted_fake(tmp_path, monkeypatch)
    monkeypatch.setattr(support, "_layers_of", lambda _found: list(("edge", "pointer")))
    dstate.STATE.session = None
    _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert out["status"] == "ok" and handed[0] == list(ov.LAYERS) \
        and handed[1] == ["edge", "pointer"], handed


def test_the_overlay_of_a_build_without_the_record_mark_names_it_lacking() -> None:
    adapter, _ = _adapter(drawn=("edge", "pointer"))
    adapter.show("held", _payload())
    said = adapter.overlay_reply()
    assert said["layers"] == ["edge", "pointer"] and set(said["lacking"]) == {"record"}, said
    assert "predates the record mark" in said["lacking"]["record"], said


def test_a_build_of_protocol_2_is_sent_only_the_words_it_parses() -> None:
    adapter, channel = _adapter(version=2)
    adapter.show("acting", _payload(pointer=presence.Pointer(1, 2)))
    sent = _words(channel.sent[0])
    assert list(sent) == ["rgb", "edge", "steps", "acting", "held", "fade", "outline", "glide",
                          "sprite", "pointer"] and sent["pointer"] == "1", channel.sent[0]


def test_a_start_asked_for_no_pointer_never_draws_one() -> None:
    shown, channel = _shown(DRAWN_3, DRAWN_3, DRAWN_3, version=3,
                            overlay=ov.Overlay(pointer=False))
    assert shown.held is not None
    shown.held.moved(3, 4)
    time.sleep(0.2)
    assert all(_words(line)["pointer"] == "0" for line in channel.sent), channel.sent
    shown.close()


def test_the_overlay_of_a_build_of_protocol_3_is_what_its_answer_draws_and_lacks() -> None:
    adapter, _ = _adapter(overlay=NO_RECORD)
    adapter.show("held", _payload())
    assert adapter.overlay_reply() == {"layers": ["edge", "pointer"]}
    adapter.answer = CAPTURED["protocol3"]["undrawable"][0]
    said = adapter.overlay_reply()
    assert said["layers"] == [], said
    assert set(said["lacking"]) == {"edge", "pointer"}
    assert "undrawable" in said["lacking"]["edge"], said


def test_the_overlay_of_a_build_of_protocol_2_names_the_layers_it_lacks() -> None:
    adapter, channel = _adapter(version=2)
    adapter.show("held", _payload())
    said = adapter.overlay_reply()
    assert said["layers"] == ["edge", "pointer"], said
    assert set(said["lacking"]) == {"record"}
    assert "version 2" in said["lacking"]["record"], said


def test_a_layer_not_asked_is_not_named_lacking_on_a_build_of_protocol_2() -> None:
    adapter, _ = _adapter(version=2, overlay=ov.Overlay(pointer=False))
    adapter.show("held", _payload())
    assert set(adapter.overlay_reply()["lacking"]) == {"record"}


def test_start_and_status_say_the_overlay_only_of_a_presence_drawn() -> None:
    drawn, _ = _shown(DRAWN_3, version=3, overlay=NO_RECORD)
    assert dpresence.overlay_shown(drawn)["overlay"]["layers"] == ["edge", "pointer"]
    drawn.close()
    for none in (presence.Shown(), _shown(shared=False)[0], _shown(commands=frozenset())[0]):
        assert dpresence.overlay_shown(none) == {}, none
