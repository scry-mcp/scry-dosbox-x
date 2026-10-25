"""The screen maps on this server, on the captured screens of `test_dosbox_x_screen`: a screen
mapped from the one in front of the caller, found again off one read, saved and loaded, a
control acted on by name, and every refusal before anything is read or sent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import clean_session, install  # noqa: F401  (the autouse teardown)
from scry_core import screen_map
from test_dosbox_x_screen import screen_bench

import dosbox_inputs as inputs
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

#: The prompt row of the booted probe's text screen, and a control on it.
PROMPT = [0, 3, 4, 1]
CONTROL = {"name": "prompt", "rect": [0, 3, 4, 1]}


@pytest.fixture(autouse=True)
def fresh_maps() -> None:
    dstate.STATE.maps = screen_map.Maps()


def _ok(reply: Any) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "ok", r
    return r


def test_a_screen_mapped_from_the_one_in_front_is_found_again_off_one_read(
        tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    added = _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    assert (added["kind"], added["size"], added["controls"]) == ("text", [80, 25], 1)
    signature = added["match"][0]["signature"]
    assert signature == _ok(server.screen_signature(crop=PROMPT))["signature"]
    s.dumps.clear()
    found = _ok(server.map_find())
    assert (found["matched"], found["screen"], found["layer"]) == (True, "prompt", "session")
    assert found["controls"] == [{"name": "prompt", "rect": [0, 3, 4, 1], "centre": [2, 3]}]
    assert s.dumps == [(0xB800, 0, 4000)], "one screen read per identification"
    assert found["summary"] == "map_find: prompt (session), 1 control"


def test_a_screen_of_another_mode_matches_nothing_and_says_what_it_tried(tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT]))
    screen_bench("screen-13h", tmp_path)
    found = _ok(server.map_find())
    assert found["matched"] is False and "screen" not in found
    assert (found["kind"], found["size"], found["screens_tried"], found["screens_mapped"]) == (
        "pixel", [320, 200], 0, 1)


def test_saved_screens_become_the_file_layer_and_load_back(tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    path = tmp_path / "probe.scry-map.json"
    saved = _ok(server.map_write("save", dest=str(path)))
    assert saved["promoted"] == ["prompt"] and json.loads(path.read_text())["application"] == (
        "probe")
    refused = cast(dict[str, Any], server.map_write("save", dest=str(path)))
    assert refused["code"] == "bad_argument", refused
    dstate.STATE.maps = screen_map.Maps()
    loaded = _ok(server.map_write("load", path=str(path)))
    assert (loaded["application"], loaded["screens"], loaded["controls"]) == ("probe", 1, 1)
    assert _ok(server.map_find())["layer"] == "file"


def test_a_start_empties_the_session_layer_and_keeps_the_file(tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              ) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake

    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT]))
    path = tmp_path / "probe.scry-map.json"
    _ok(server.map_write("save", dest=str(path)))
    _ok(server.map_write("add", screen="again", match=[PROMPT]))
    server.close()
    _ok(_start_on_a_booted_fake(tmp_path, monkeypatch))
    assert list(dstate.STATE.maps.session) == [] and list(dstate.STATE.maps.file) == ["prompt"]
    assert dstate.STATE.maps.found is None
    server.close()


@pytest.mark.parametrize(("call", "code"), [
    (lambda p: server.map_find(), "needs_call"),
    (lambda p: server.map_write("save", dest=str(p / "x.scry-map.json")), "needs_call"),
    (lambda p: server.map_write("load", path=str(p / "no.scry-map.json")), "bad_argument"),
    (lambda p: server.map_write("load", path="relative.scry-map.json"), "bad_argument"),
    (lambda p: server.map_write("load", path=str(p / "x.json")), "bad_argument"),
    (lambda p: server.map_write("add", screen="", match=[PROMPT]), "bad_argument"),
    (lambda p: server.map_write("add", screen="s", match=[]), "bad_argument"),
    (lambda p: server.map_write("add", screen="s", match=[[0, 0, 0, 1]]), "bad_argument"),
    (lambda p: server.map_write("add", screen="s", match=[PROMPT], controls=[{"name": "a"}]),
     "bad_argument"),
    (lambda p: server.map_write("save", dest=str(p / "x.scry-map.json"), overwrite="yes"),
     "bad_argument"),
], ids=["find with nothing mapped", "save with nothing mapped", "a file that is not there",
        "a relative path", "a name without the map suffix", "an empty screen name",
        "no region", "an empty region", "a control without its rect",
        "an overwrite that is no yes or no"])
def test_what_the_map_tools_refuse(tmp_path: Path, call: Any, code: str) -> None:
    s = screen_bench("probe-booted", tmp_path)
    got = cast(dict[str, Any], call(tmp_path))
    assert got["status"] == "INVALID" and got["code"] == code, got
    if code == "bad_argument":
        assert s.dumps == [], "refused before the screen was read"


def test_perform_refuses_a_misshapen_map_step_before_any_step_runs(tmp_path: Path) -> None:
    s = screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.perform(steps=[
        {"op": "palette"}, {"op": "map_write", "method": "add", "screen": "s", "match": "row 3"},
        {"op": "map_write", "method": "save", "dest": str(tmp_path / "x.scry-map.json"),
         "overwrite": "yes"}]))
    assert r["status"] == "INVALID" and [e["step"] for e in r["errors"]] == [1, 2], r
    assert "overwrite" in r["errors"][1]["message"], r["errors"][1]
    assert s.asked == [] and s.dumps == []


# ------------------------------------------------------------------ a control, by name


@pytest.mark.parametrize(("kw", "said"), [
    ({"target": "prompt", "x": 1, "y": 1}, "not both"),
    ({"target": "prompt", "units": "mouse"}, "the screen's units"),
    ({"target": ""}, "name a move"),
], ids=["a target and a place", "a target in mouse units", "an empty target is none"])
def test_a_target_is_refused_before_anything_is_sent(kw: dict[str, Any], said: str) -> None:
    r = cast(dict[str, Any], server.send_mouse(**kw))
    assert r["status"] == "INVALID" and r["code"] == "bad_argument" and said in r["message"]


def test_a_target_needs_an_identification_and_a_control_the_screen_has(tmp_path: Path) -> None:
    r = cast(dict[str, Any], server.send_mouse(target="prompt"))
    assert r["code"] == "needs_call" and "map_find" in r["message"], r
    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    _ok(server.map_find())
    r = cast(dict[str, Any], server.send_mouse(target="serve"))
    assert r["code"] == "unknown_ref" and "its controls: prompt" in r["message"], r


def test_a_target_moves_the_pointer_to_its_controls_centre_and_says_which(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    _ok(server.map_find())
    sent: list[tuple[Any, ...]] = []

    def send(session: Any, x: Any, y: Any, button: Any, action: Any, units: Any, *rest: Any,
             ) -> dict[str, Any]:
        sent.append((x, y, button, units, rest[-1]["size"], rest[0], rest[1]))
        return {"status": "ok", "route": "guest", "arrived": True}
    monkeypatch.setattr(inputs, "send_mouse", send)
    r = _ok(server.send_mouse(target="prompt", button="left", expect="clicked", seconds=3))
    assert sent == [(2, 3, "left", "screen", (80, 25), "clicked", 3)], (
        "the centre, in the screen's units, with the caller's expectation")
    assert (r["target"], r["screen"]) == ("prompt", "prompt")


def test_a_target_names_the_stop_its_identification_was_read_at(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = screen_bench("probe-booted", tmp_path)
    stop: tuple[Any, ...] = ({"cs": "F000", "eip": "0000FFF0", "mode": "Real"}, {}, [],
                             {"attributed": False})
    for _ in range(7):
        dstate.STATE.remember_stop(cast(Any, s), *stop)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    _ok(server.map_find())
    dstate.STATE.remember_stop(cast(Any, s), *stop)          # a later stop: still stop 7's
    monkeypatch.setattr(inputs, "send_mouse", lambda *a, **k: {"status": "ok"})
    assert _ok(server.send_mouse(target="prompt"))["identified_at_stop"] == 7
    def cut(*a: Any) -> Any:
        raise ds.Invalid("host_failed", "the pane was cut")
    cast(Any, s).stop_count = 99                              # a stop with no record of its own
    monkeypatch.setattr(s, "stop_survey", cut)
    _ok(server.map_find())
    assert _ok(server.send_mouse(target="prompt"))["identified_at_stop"]["available"] is False


@pytest.mark.parametrize(("mode", "said"), [
    (0x13, "shows a pixel 320x200 screen now"),
    (0x6A, "shows a mode this server does not map now"),
], ids=["another mode", "an unmapped mode"])
def test_a_target_on_a_guest_no_longer_showing_its_screen_is_refused(mode: int,
                                                                     said: str) -> None:
    aimed = {"target": "prompt", "screen": "prompt", "kind": "text", "size": (80, 25)}
    report = inputs.Report(0, 0, 0, 639, 199, mode, (640, 400))
    with pytest.raises(ds.Invalid, match=said) as e:
        inputs._still_the_screen(report, aimed)
    assert e.value.code == "needs_call" and "`map_find` again" in str(e.value)
    inputs._still_the_screen(inputs.Report(0, 0, 0, 639, 199, 0x03, (640, 400)), aimed)


def test_a_control_off_the_screen_it_read_is_refused_and_keeps_nothing(tmp_path: Path) -> None:
    screen_bench("probe-booted", tmp_path)
    r = cast(dict[str, Any], server.map_write("add", screen="prompt", match=[PROMPT],
                                              controls=[{"name": "far", "rect": [78, 0, 4, 1]}]))
    assert r["code"] == "bad_argument" and "control 'far' rect" in r["message"], r
    assert dstate.STATE.maps.session == {}


def test_an_export_keeps_the_map_an_identification_was_made_against_and_replays_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`map_write(method="load")` and `map_write(method="add")` are steps, `map_find` a check
    holding to what it matched, and
    `map_write(method="save")` is dropped (a replay would find its file there): the exported list,
    played on a
    server that knows no map, identifies the same screen."""
    from scry_core import recording

    import dosbox_mcp
    screen_bench("probe-booted", tmp_path)
    _ok(server.map_write("add", screen="prompt", match=[PROMPT], controls=[CONTROL]))
    path = tmp_path / "probe.scry-map.json"
    _ok(server.map_write("save", dest=str(path)))
    monkeypatch.setattr(dosbox_mcp.RECORDER, "recording", recording.Recording({"conf": "/x"}))
    _ok(server.map_write("load", path=str(path)))
    _ok(server.map_write("add", screen="row", match=[[0, 0, 80, 1]]))
    _ok(server.map_find())
    _ok(server.map_write("save", dest=str(tmp_path / "again.scry-map.json")))
    out = _ok(server.perform_export(dest=str(tmp_path / "s.json")))
    steps = json.loads((tmp_path / "s.json").read_text())["steps"]
    assert [(s["op"], s.get("method")) for s in steps] == [
        ("map_write", "load"), ("map_write", "add"), ("map_find", None)]
    assert steps[2]["recorded"] == {"matched": True, "screen": "row"}
    assert [d["op"] for d in out["dropped"]] == ["map_write"]
    dstate.STATE.maps = screen_map.Maps()
    played = _ok(server.perform(steps=steps))
    assert played["steps_completed"] == 3, played
