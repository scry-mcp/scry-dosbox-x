"""The input a DOSBox-X demo's steps sent, as its run's timeline carries it: read from the
committed runs of the demos, which stand in for an emulator."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from demo_transcripts import timeline_of  # noqa: E402
from scry_core.demo import Reply, Step

from demos import decorated
from scry_dosbox_x import presence, summaries

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("bricks", "dpaint", "dpaint_maps", "lineup", "mines", "monkey", "rechip", "speedf",
         "xcom")


def _module(name: str) -> Any:
    return importlib.import_module(f"demos.{name}.demo")


def _timeline(name: str) -> dict[str, Any]:
    return timeline_of(decorated.prepared(_module(name).DEMO),
                       ROOT / "demos" / name / "TRANSCRIPT.md")


def _events(name: str, step: str) -> list[dict[str, Any]]:
    return [e for call in _timeline(name)["calls"] if call["step"] == step
            for e in call["events"]]


def test_a_drive_of_key_presses_is_each_key_down_and_up() -> None:
    assert [(e["name"], e["down"]) for e in _events("bricks", "keys")] == [("right", True),
                                                                           ("right", False)] * 3


def test_a_mouse_move_is_the_pointer_where_the_driver_read_it() -> None:
    assert _events("bricks", "mouse") == [{"kind": "pointer", "x": 240, "y": 100, "frame": 143}]


def test_each_input_of_a_perform_is_an_event_at_the_frame_its_own_summary_says() -> None:
    first = _events("dpaint", "word")[:6]
    assert [(e["kind"], e.get("x"), e.get("name"), e.get("down"), e["frame"]) for e in first] == [
        ("pointer", 314, None, None, 513), ("button", None, "left", True, 513),
        ("button", None, "left", False, 513), ("pointer", 20, None, None, 538),
        ("button", None, "left", True, 538), ("button", None, "left", False, 538)]


def test_modifiers_go_down_before_the_keys_and_come_up_after_them() -> None:
    held = [(e["name"], e["down"]) for e in _events("dpaint", "word") if e["kind"] == "key"]
    assert held[:2] == [("shift", True), ("s", True)] and held[-2:] == [("s", False),
                                                                        ("shift", False)]


def test_a_key_held_down_goes_down_in_one_call_and_up_in_a_later_one() -> None:
    held = [(e["name"], e["down"], e["frame"]) for e in _events("lineup", "fire again")]
    assert held == [("up", True, 786), ("up", False, 863)]


@pytest.mark.parametrize("name", NAMES)
def test_every_committed_run_makes_a_timeline_the_decorator_can_read(name: str) -> None:
    kinds = {e["kind"] for call in _timeline(name)["calls"] for e in call["events"]}
    assert ("key" in kinds) == ("keys" in _module(name).LAYERS)
    assert ({"pointer", "button"} & kinds != set()) == ("pointer" in _module(name).LAYERS)
    assert "calls" in _module(name).LAYERS
    decorated.declared(_module(name).LAYERS)


def test_a_refused_call_fires_nothing() -> None:
    refused = Reply({"status": "refused", "summary": "send_keys: refused"})
    assert decorated.pressed("send_keys", {"keys": ["a"]}, refused) == []


def test_a_step_that_names_its_own_events_keeps_them() -> None:
    mine = Step("mine", "send_keys", {}, lambda reply, run: "", events=lambda a, r: ())
    assert decorated.fired([mine])[0].events is mine.events


def test_only_the_tools_that_send_input_are_given_the_extractor() -> None:
    steps = [Step(tool, tool, {}, lambda reply, run: "")
             for tool in ("send_keys", "send_mouse", "perform", "drive", "run_for")]
    assert [s.events is not None for s in decorated.fired(steps)] == [True] * 4 + [False]


@pytest.mark.parametrize(("reply", "want"), [
    ({"pointer": {"screen": {"x": 3, "y": 4}, "mouse": {"x": 9, "y": 9}}}, (3, 4)),
    ({"pointer": {"mouse": {"x": 9, "y": 8}}}, (9, 8)),
    ({}, (5, 6))])
def test_the_pointer_is_where_the_driver_reports_it_else_where_it_was_sent(
        reply: dict[str, Any], want: tuple[int, int]) -> None:
    assert presence.pointer_where(reply, 5, 6) == want


@pytest.mark.parametrize(("action", "keys", "mods"), [
    ("press", [("ctrl", True), ("a", True), ("a", False), ("ctrl", False)], ["ctrl"]),
    ("down", [("ctrl", True), ("a", True)], ["ctrl"]),
    ("up", [("a", False), ("ctrl", False)], ["ctrl"])])
def test_what_a_send_keys_does_to_the_keycaps(action: str, keys: list[tuple[str, bool]],
                                              mods: list[str]) -> None:
    assert presence.key_edges(["A"], mods, action) == keys


@pytest.mark.parametrize(("action", "edges"), [("click", [True, False]), ("down", [True]),
                                               ("up", [False])])
def test_what_a_send_mouse_does_to_its_button(action: str, edges: list[bool]) -> None:
    assert presence.button_edges(action) == edges


def test_a_summary_gives_back_the_pointer_and_frame_the_formatter_wrote() -> None:
    said = summaries.send_mouse({"button": "left"}, {
        "pointer": {"screen": {"x": 302, "y": 51}}, "polls": 25, "frame": 613})
    assert (summaries.pointer_in(said), summaries.frame_in(said)) == ((302, 51), 613)
    assert summaries.pointer_in("send_mouse: pointer at unread") is None
    assert summaries.frame_in("send_keys (guest): sent") is None


@pytest.mark.parametrize("name", NAMES)
def test_every_moment_of_a_demo_ends_at_a_step_its_committed_run_holds(name: str) -> None:
    module = _module(name)
    shown = decorated.passes(_timeline(name), module.DEMO)
    assert [one["calls"][-1]["step"] for one in shown] == [m.until for m in module.DEMO.moments]


def _compact(n: int, summary: str, **fields: Any) -> dict[str, Any]:
    return {"step": n, "op": "send_mouse", "reply": {"status": "ok", "summary": summary, **fields}}


def test_a_performed_list_longer_than_the_rows_a_reply_shows_pairs_each_row_with_its_step() -> None:
    steps = [{"op": "send_mouse", "x": n, "y": n} for n in range(30)]
    steps[29]["button"] = "left"
    ran = [_compact(n, f"send_mouse: pointer at {n},{n}; sent, 1 frames to frame {100 + n}")
           for n in range(24)] + [_compact(29, "send_mouse: pointer at 29,29; sent, 1 frames to "
                                                "frame 129", frame=129, pointer={
                                                    "screen": {"x": 29, "y": 29}})]
    fired = decorated.pressed("perform", {"steps": steps}, Reply({"status": "ok", "ran": ran}))
    assert [(f.kind, f.frame) for f in fired[-3:]] == [("pointer", 129), ("button", 129),
                                                       ("button", 129)]
    assert len(fired) == 24 + 3


def test_a_compact_row_gives_the_place_its_summary_says_and_not_the_one_sent() -> None:
    ran = [_compact(0, "send_mouse: pointer at 80,90 (driver); sent, reaction not checked")]
    fired = decorated.pressed("perform", {"steps": [{"op": "send_mouse", "x": 5, "y": 6,
                                                     "units": "mouse"}]},
                              Reply({"status": "ok", "ran": ran}))
    assert [(f.x, f.y) for f in fired] == [(80, 90)]


def test_the_frame_a_summary_gives_is_the_last_one_it_names() -> None:
    assert summaries.frame_in("send_keys (guest): saw 'scroll to frame 7', 3 frames to frame 90") \
        == 90
