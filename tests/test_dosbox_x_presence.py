"""`presence`: which tools drive, held against the registry; the look as the channel's
`PRESENCE` takes it; what the emulator's answers mean (drawn, a build without the command, an
output it cannot draw on); a session with no window; the pointer turned on by the first mouse
move; and a start plan lighting the window. The words of protocol 3 (the layers, the caption sent
once, the keys, the paused state), the fallback on a build of protocol 2, the `overlay` of
`start` and `status`, and the input and stop events the server reports to the presence."""

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
from scry_core import abbreviation, boundary, overlay_timeline, presence
from scry_core import overlay as ov
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
        self.bare: tuple[bool, list[str]] = (
            True, CAPTURED[f"protocol{version}"]["bare_before_output"])

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


# ----------------------------------------------------------------------- protocol 3

#: What a build of protocol 3 draws before the record mark.
ALL = ("edge", "pointer", "keys", "calls", "pause")
NO_RECORD = ov.Overlay(record=False)
#: The words of the layers protocol 3 added to the look, in the order the adapter sends them.
PROTOCOL_3_LOOK = ("caption_text_rgb", "caption_alpha", "keycap_rgb", "keycap_text_rgb",
                   "keycap_alpha", "scroll_cps")


def _payload(**kw: Any) -> presence.Payload:
    return presence.Payload(layers=kw.pop("layers", ALL), **kw)


def _caption(text: str = "registers", serial: int = 1) -> overlay_timeline.Caption:
    return overlay_timeline.Caption(text, "read", 0x5AC8FA, serial)


def _adapter(version: int = 3, overlay: ov.Overlay = ov.OVERLAY, drawn: Collection[str] = ALL,
             ) -> tuple[dpresence.ChannelAdapter, _Session]:
    channel = _Session(DRAWN_3, DRAWN_3, DRAWN_3, DRAWN_3, version=version)
    return dpresence.ChannelAdapter(channel, overlay=overlay, drawn=drawn), channel


def _words(line: str) -> dict[str, str]:
    return dpresence.words(line)


def test_a_build_of_protocol_3_is_sent_the_layers_the_place_and_the_look_it_parses() -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(layers=("edge", "keys", "calls"), place="top"))
    sent = _words(channel.sent[0])
    look = presence.LOOK
    assert channel.sent[0].startswith("PRESENCE held rgb=")
    assert sent["layers"] == "edge,keys,calls", "the command names the layer as `overlay` does"
    assert sent["place"] == "top"
    assert sent["pointer"] == "0"
    assert {k: sent[k] for k in PROTOCOL_3_LOOK} == {
        "caption_text_rgb": f"{look.caption_text_rgb:06X}",
        "caption_alpha": f"{look.caption_alpha:g}",
        "keycap_rgb": f"{look.keycap_rgb:06X}", "keycap_text_rgb": f"{look.keycap_text_rgb:06X}",
        "keycap_alpha": f"{look.keycap_alpha:g}", "scroll_cps": f"{look.scroll_cps:g}"}
    assert not {"scroll", "cap_scale", "caption_in", "caption_out"} & sent.keys(), (
        "the fork's own fades stand, and no word is sent that the command does not parse")


def test_a_caption_longer_than_the_command_takes_is_cut_to_what_it_takes() -> None:
    adapter, channel = _adapter()
    adapter.show("acting", _payload(caption=_caption("x" * 400)))
    assert _words(channel.sent[0])["caption"] == "x" * dpresence.CAPTION_BYTES


def test_the_caption_is_sent_with_its_tint_percent_encoded_in_one_word() -> None:
    adapter, channel = _adapter()
    text = abbreviation.caption("write", {"address": "0x100", "path": "/srv/a/b c.bin"})
    adapter.show("acting", _payload(caption=_caption(text)))
    assert f"caption={dpresence.encoded(text, 160)} serial=1 tint=5AC8FA" in channel.sent[0]
    assert " " not in dpresence.encoded(text, 160) and "%20" in dpresence.encoded(text, 160)


@pytest.mark.parametrize("text, limit, word", [
    ("a b%c", 160, "a%20b%25c"),
    ("tab\tnl\n", 160, "tab%09nl%0A"),
    ("caf\u00e9", 160, "caf?"),
    ("x" * 200, 160, "x" * 160),
    ("enter", 12, "enter"),
    ("a" * 20, 12, "a" * 12),
])
def test_a_text_is_one_ascii_word_of_at_most_the_bytes_the_command_takes(
        text: str, limit: int, word: str) -> None:
    assert dpresence.encoded(text, limit) == word


def test_a_caption_goes_once_when_new_and_again_for_a_new_call_of_the_same_text() -> None:
    adapter, channel = _adapter()
    adapter.show("acting", _payload(caption=_caption(serial=1)))
    adapter.show("held", _payload(caption=_caption(serial=1)))
    adapter.show("acting", _payload(caption=_caption(serial=2)))
    first, again, second = (_words(line) for line in channel.sent[:3])
    assert "caption" in first and "caption" not in again
    assert second["caption"] == first["caption"], "a new call of equal text is a new caption"
    assert (first["serial"], second["serial"]) == ("1", "2"), "the command tells them apart by it"


def test_a_call_that_ends_refused_sends_its_caption_again_in_the_refused_tint() -> None:
    adapter, channel = _adapter()
    adapter.show("acting", _payload(caption=_caption()))
    refused = overlay_timeline.Caption("registers", "refused", 0xFF453A, 1)
    adapter.show("held", _payload(caption=refused))
    assert "tint=FF453A" in channel.sent[1], channel.sent[1]


def test_a_caption_that_leaves_is_taken_away_with_an_empty_word_and_only_once() -> None:
    adapter, channel = _adapter()
    adapter.show("held", _payload(caption=_caption()))
    adapter.show("held", _payload())
    adapter.show("held", _payload())
    assert "caption" in _words(channel.sent[0])
    assert channel.sent[1].endswith(" caption="), channel.sent[1]
    assert "caption=" not in channel.sent[2]


def test_a_caption_a_delivery_did_not_take_is_sent_again() -> None:
    channel = _Session((False, CAPTURED["protocol3"]["refused_value"]), DRAWN_3, version=3)
    adapter = dpresence.ChannelAdapter(channel)
    with pytest.raises(RuntimeError, match="refused PRESENCE"):
        adapter.show("acting", _payload(caption=_caption()))
    adapter.show("acting", _payload(caption=_caption()))
    assert all(" caption=registers " in line for line in channel.sent), channel.sent


def test_the_keys_down_go_with_every_delivery_the_latest_eight_each_cut() -> None:
    adapter, channel = _adapter()
    names = tuple(f"key{i}" for i in range(10))
    adapter.show("held", _payload(keys=names))
    adapter.show("held", _payload())
    adapter.show("held", _payload(keys=("a" * 30,)))
    assert _words(channel.sent[0])["keys"] == ",".join(names[-8:])
    assert _words(channel.sent[2])["keys"] == "a" * dpresence.KEY_BYTES
    assert channel.sent[1].endswith(" keys="), "none held says so: a word left out keeps its value"


def test_a_layer_not_asked_sends_no_word_of_its_own() -> None:
    adapter, channel = _adapter(overlay=ov.Overlay(calls=False, keys=False))
    adapter.show("held", _payload(layers=("edge", "pointer", "pause"), keys=("a",),
                                  caption=_caption()))
    assert "keys=" not in channel.sent[0] and "caption=" not in channel.sent[0]


@pytest.mark.parametrize("recording", ["none", "video", "audio", "both"])
def test_a_build_with_the_record_mark_is_told_what_is_recorded_and_how_the_mark_looks(
        recording: presence.Recording) -> None:
    adapter, channel = _adapter(drawn=ov.LAYERS)
    adapter.show("held", _payload(layers=ov.LAYERS, recording=recording))
    sent = _words(channel.sent[0])
    assert sent["layers"] == ",".join(ov.LAYERS) and sent["rec"] == recording
    assert (sent["record_rgb"], sent["record_blink_s"]) == (
        f"{presence.LOOK.record_rgb:06X}", f"{presence.LOOK.record_blink_s:g}")


def test_a_layer_not_asked_still_tells_a_build_with_the_record_mark_nothing_is_recorded() -> None:
    adapter, channel = _adapter(overlay=NO_RECORD, drawn=ov.LAYERS)
    adapter.show("held", _payload())
    sent = _words(channel.sent[0])
    assert sent["layers"] == ",".join(ALL) and sent["rec"] == "none"


def test_a_build_of_protocol_3_without_the_record_mark_is_sent_no_word_it_rejects() -> None:
    adapter, channel = _adapter(drawn=ALL)
    adapter.show("held", _payload(layers=ov.LAYERS, recording="video"))
    line = channel.sent[0]
    assert "record" not in line and "rec=" not in line, line
    assert _words(line)["layers"] == ",".join(ALL)


def test_what_a_build_without_the_record_mark_refuses_is_never_sent_to_it() -> None:
    """The refusals are 158f511fa's own, captured; a delivery that carried a word of them would
    lose the whole line."""
    refused = CAPTURED["protocol3"]
    argument = [refused[key][0].removeprefix("PRESENCE does not know the argument ")
                for key in ("refused_record_word", "refused_record_look")]
    layer = refused["refused_record_layer"][0].split()[1].removeprefix("layers=")
    assert argument == ["rec", "record_rgb"] and layer.endswith(",record"), refused
    adapter, channel = _adapter(drawn=ALL)
    adapter.show("held", _payload(layers=ov.LAYERS, recording="both"))
    sent = _words(channel.sent[0])
    assert not set(argument) & set(sent) and "record" not in sent["layers"].split(","), sent


def test_the_overlay_of_a_build_with_the_record_mark_draws_it_as_its_answer_says() -> None:
    recorded = CAPTURED["protocol3_record"]
    assert dpresence.build_version(recorded["bare"]) == 3
    assert "record" in _words(recorded["bare"][0])["layers"].split(",")
    adapter, _ = _adapter(drawn=ov.LAYERS)
    adapter.show("held", _payload(layers=ov.LAYERS))
    adapter.answer = recorded["drawn"][0]
    assert adapter.overlay_reply() == {"layers": list(ov.LAYERS), "place": "bottom"}


def test_the_overlay_names_each_layer_the_build_is_not_drawing_and_not_only_the_record() -> None:
    adapter, channel = _adapter(drawn=("edge", "pointer"))
    adapter.show("held", _payload(layers=ov.LAYERS))
    assert _words(channel.sent[0])["layers"] == "edge,pointer"
    said = adapter.overlay_reply()
    assert set(said["lacking"]) == {"keys", "calls", "pause", "record"}, said


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
    monkeypatch.setattr(support, "_layers_of", lambda _found: list(ALL))
    dstate.STATE.session = None
    _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert out["status"] == "ok" and handed[0] == list(ov.LAYERS) and handed[1] == list(ALL), handed


def test_the_overlay_of_a_build_without_the_record_mark_names_it_lacking() -> None:
    adapter, _ = _adapter(drawn=ALL)
    adapter.show("held", _payload())
    said = adapter.overlay_reply()
    assert said["layers"] == list(ALL) and set(said["lacking"]) == {"record"}, said
    assert "predates the record mark" in said["lacking"]["record"], said


@pytest.mark.parametrize("state, paused, version, word", [
    ("held", True, 3, "paused"), ("acting", True, 3, "acting"), ("held", False, 3, "held"),
    ("held", True, 2, "held")])
def test_a_machine_held_stopped_is_the_paused_state_of_a_build_that_has_one(
        state: presence.State, paused: bool, version: int, word: str) -> None:
    adapter, channel = _adapter(version)
    adapter.show(state, _payload(paused=paused))
    assert channel.sent[0].split()[1] == word


def test_a_build_of_protocol_2_is_sent_only_the_words_it_parses() -> None:
    adapter, channel = _adapter(version=2)
    adapter.show("acting", _payload(caption=_caption(), keys=("a",), paused=True,
                                    pointer=presence.Pointer(1, 2)))
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
    assert adapter.overlay_reply() == {"layers": list(ALL), "place": "bottom"}
    adapter.answer = CAPTURED["protocol3"]["undrawable"][0]
    said = adapter.overlay_reply()
    assert said["layers"] == [] and said["place"] == "bottom", said
    assert set(said["lacking"]) == set(ALL)
    assert "undrawable" in said["lacking"]["calls"], said


def test_the_overlay_of_a_build_of_protocol_2_names_the_layers_it_lacks() -> None:
    adapter, channel = _adapter(version=2)
    adapter.show("held", _payload())
    said = adapter.overlay_reply()
    assert said["layers"] == ["edge", "pointer"] and said["place"] == "auto", said
    assert set(said["lacking"]) == {"calls", "keys", "pause", "record"}
    assert "version 2" in said["lacking"]["calls"], said


def test_a_layer_not_asked_is_not_named_lacking_on_a_build_of_protocol_2() -> None:
    adapter, _ = _adapter(version=2, overlay=ov.Overlay(calls=False, pause=False))
    adapter.show("held", _payload())
    assert set(adapter.overlay_reply()["lacking"]) == {"keys", "record"}


def test_start_and_status_say_the_overlay_only_of_a_presence_drawn() -> None:
    drawn, _ = _shown(DRAWN_3, version=3, overlay=NO_RECORD)
    assert dpresence.overlay_shown(drawn)["overlay"]["layers"] == list(ALL)
    drawn.close()
    for none in (presence.Shown(), _shown(shared=False)[0], _shown(commands=frozenset())[0]):
        assert dpresence.overlay_shown(none) == {}, none


def test_an_overlay_is_the_model_or_the_object_a_profile_holds() -> None:
    assert dpresence.overlay_of(ov.OVERLAY) is ov.OVERLAY
    assert dpresence.overlay_of({"calls": False, "place": "top"}) == ov.Overlay(
        calls=False, place="top")
    for bad in ({"calls": "no"}, {"colour": True}, {"place": "left"}, 3):
        with pytest.raises(Invalid) as e:
            dpresence.overlay_of(bad)
        assert e.value.code == "bad_argument" and "overlay" in str(e.value), bad


class _Reports:
    """The input and pause events a `Shown` is told, in order."""

    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []
        self.shown = presence.Shown()
        for name in ("key", "moved", "button", "paused"):
            setattr(self.shown, name, self._record(name))

    def _record(self, name: str) -> Callable[..., None]:
        def record(*a: Any) -> None:
            self.events.append((name, *a))
        return record


@pytest.mark.parametrize("action, expected", [
    ("press", [("key", "ctrl", True), ("key", "a", True), ("key", "a", False),
               ("key", "ctrl", False)]),
    ("down", [("key", "ctrl", True), ("key", "a", True)]),
    ("up", [("key", "a", False), ("key", "ctrl", False)]),
])
def test_keys_sent_are_reported_as_the_modifiers_and_keys_going_down_and_up(
        action: str, expected: list[tuple[Any, ...]]) -> None:
    reports = _Reports()
    dpresence.keys_sent(reports.shown, ["A"], ["Ctrl"], action)
    assert reports.events == expected


@pytest.mark.parametrize("button, action, expected", [
    ("left", "click", [("button", "left", True), ("button", "left", False)]),
    ("left", "double", [("button", "left", True), ("button", "left", False)]),
    ("right", "down", [("button", "right", True)]),
    ("right", "up", [("button", "right", False)]),
    ("left", "drag", [("button", "left", True), ("button", "left", False)]),
    (None, "click", []),
])
def test_a_mouse_call_is_reported_as_the_pointer_then_its_buttons(
        button: str | None, action: str, expected: list[tuple[Any, ...]]) -> None:
    reports = _Reports()
    dpresence.mouse_sent(reports.shown, {"pointer": {"screen": {"x": 5, "y": 6}}}, 1, 2,
                         button, action)
    assert reports.events == [("moved", 5, 6), *expected]


def test_a_mouse_call_is_reported_where_the_driver_says_else_where_it_was_sent() -> None:
    reports = _Reports()
    unmapped = {"pointer": {"screen": {"available": False, "why": "x"},
                            "mouse": {"x": 70, "y": 80}}}
    dpresence.mouse_sent(reports.shown, unmapped, 1, 2, None, "click")
    dpresence.mouse_sent(reports.shown, {}, 1, 2, None, "click")
    dpresence.mouse_sent(reports.shown, {}, None, None, None, "click")
    assert reports.events == [("moved", 70, 80), ("moved", 1, 2), ("moved", 0, 0)]


def _serving(monkeypatch: pytest.MonkeyPatch) -> _Reports:
    """The input tools of the server run with a live session and the reports of its presence
    caught."""
    from scry_dosbox_x import running
    reports = _Reports()
    monkeypatch.setattr(running, "live", lambda probe=True: object())
    monkeypatch.setattr(server, "live", lambda probe=True: object())
    monkeypatch.setattr(dpresence, "of", lambda session: reports.shown)
    return reports


def test_the_servers_input_tools_report_what_they_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import inputs
    reports = _serving(monkeypatch)
    monkeypatch.setattr(inputs, "send_keys", lambda *a, **k: {
        "status": "ok", "route": "guest", "posted": 1, "bytes": 2, "frames": 2,
        "verify": {"checked": False, "why": "no expect"}})
    monkeypatch.setattr(inputs, "send_mouse", lambda *a, **k: {
        "status": "ok", "delivered": True, "route": "guest", "arrived": True,
        "pointer": {"x": 9, "y": 8, "screen": {"x": 9, "y": 8}},
        "verify": {"checked": False, "why": "no expect"}})
    server.send_keys(keys=["enter"], modifiers=["shift"])
    server.send_mouse(x=9, y=8, button="left")
    assert reports.events == [
        ("key", "shift", True), ("key", "enter", True), ("key", "enter", False),
        ("key", "shift", False), ("moved", 9, 8), ("button", "left", True),
        ("button", "left", False)]


def test_keys_that_were_not_sent_are_not_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from scry_dosbox_x import inputs
    reports = _serving(monkeypatch)
    monkeypatch.setattr(inputs, "send_keys", lambda *a, **k: {"status": "INVALID",
                                                             "delivered": False})
    server.send_keys(keys=["enter"])
    assert reports.events == []


class _StopState:
    """What `mark_stopped` and `forget_stop` read and write of a session."""

    def __init__(self, parked: bool) -> None:
        self._at_debugger = parked
        self.stop_count = 0
        self._surveyed: object = None
        self._run_unknown = False
        self.fired_entry: str | None = None
        self.paused: list[bool] = []
        paused = self.paused

        class Told(presence.Shown):
            def paused(self, stopped: bool) -> None:
                paused.append(stopped)
        self.presence = Told()


def test_a_stop_and_a_release_tell_the_presence_the_machine_is_held_or_running() -> None:
    from scry_dosbox_x import session as ds
    state = _StopState(parked=False)
    ds.Session.mark_stopped(cast(Any, state))
    ds.Session.mark_stopped(cast(Any, state))
    ds.Session.forget_stop(cast(Any, state))
    ds.Session.forget_stop(cast(Any, state))
    assert state.paused == [True, False], "told when the state changes, not at every look"


def test_a_start_lights_the_pause_mark_of_a_machine_it_leaves_stopped(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake

    from scry_dosbox_x import state as dstate
    told: list[bool] = []

    def lit(session: Any, asked: bool, shared: bool, overlay: ov.Overlay,
            drawn: Collection[str]) -> presence.Shown:
        class Told(presence.Shown):
            def paused(self, stopped: bool) -> None:
                told.append(stopped)
        return Told()
    monkeypatch.setattr(dpresence, "open_shown", lit)
    dstate.STATE.session = None
    out = _start_on_a_booted_fake(tmp_path, monkeypatch)
    assert out["status"] == "ok", out
    assert told == [True], "the park at the debugger is the start's first state"
    dstate.STATE.session = None


def test_a_start_refuses_a_bad_overlay_before_anything_acts(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake

    from scry_dosbox_x import state as dstate
    dstate.STATE.session = None
    refused = _start_on_a_booted_fake(tmp_path, monkeypatch, overlay={"colour": 1})
    assert refused["status"] == "INVALID" and refused["code"] == "bad_argument", refused
    assert dstate.STATE.session is None, "nothing was started"


def _presence_status(shown: presence.Shown) -> dict[str, Any]:
    from scry_dosbox_x import state as dstate

    class Live:
        presence = shown

        def alive(self) -> bool:
            return True
    dstate.STATE.session = Live()  # type: ignore[assignment]
    try:
        from scry_dosbox_x import lifecycle
        return lifecycle.presence_facts(cast(Any, dstate.STATE.session))
    finally:
        dstate.STATE.session = None


def test_status_says_the_overlay_beside_the_presence_while_it_is_drawn() -> None:
    shown, _ = _shown(DRAWN_3, version=3, overlay=ov.Overlay(keys=False, record=False))
    said = _presence_status(shown)
    assert said["presence"] is True
    assert said["overlay"] == {"layers": ["edge", "pointer", "calls", "pause"], "place": "bottom"}
    shown.close()
    assert "overlay" not in _presence_status(presence.Shown(refused=True))


def test_the_start_reply_and_the_status_reply_say_the_overlay(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake, install

    from scry_dosbox_x import state as dstate
    real = dpresence.open_shown
    monkeypatch.setattr(
        dpresence, "open_shown", lambda session, asked, shared, overlay, drawn: real(
            _Session(DRAWN_3, version=3), asked, True, overlay, ALL))
    dstate.STATE.session = None
    out = _start_on_a_booted_fake(tmp_path, monkeypatch, overlay={"keys": False, "record": False})
    assert out["status"] == "ok" and out["presence"] is True, out
    assert out["overlay"] == {"layers": ["edge", "pointer", "calls", "pause"], "place": "bottom"}
    held = cast(Any, dstate.STATE.session).presence
    held.close()
    dstate.STATE.session = None
    live: Any = install()
    live.presence = _shown(DRAWN_3, version=3, overlay=NO_RECORD)[0]
    said = server.status()
    assert said["presence"] is True and said["overlay"]["layers"] == list(ALL), said
    live.presence.close()
    dstate.STATE.session = None


def test_what_the_overlay_asked_reaches_the_command_through_the_first_delivery() -> None:
    shown, channel = _shown(DRAWN_3, version=3, overlay=ov.Overlay(calls=False, place="top"))
    sent = _words(channel.sent[0])
    assert sent["layers"] == "edge,pointer,keys,pause,record" and sent["place"] == "top"
    shown.close()


def test_a_call_heard_by_the_presence_is_delivered_as_a_caption() -> None:
    shown, channel = _shown(DRAWN_3, DRAWN_3, DRAWN_3, DRAWN_3, version=3)
    assert shown.held is not None
    call = boundary.Call("read_memory", {"ref": "0x10"}, False, True)
    shown.held.began(call)
    shown.held.ended(call, "ok")
    sent = _sent(channel, 2)
    assert any(" caption=read_memory%200x10 serial=" in line and " tint=5AC8FA" in line
               for line in sent), sent
    shown.close()


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
