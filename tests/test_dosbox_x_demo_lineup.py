"""The LineUp demo's DOSBox-X binding, without an emulator: the game's own store, the conf its
script derives, and the document it replays."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from scry_core.demo import Reply, Run, StepFailed
from scry_core.games import lineup

from demos.lineup import demo


def _game(folder: Path, *, with_map: bool = True, with_store: bool = True) -> Path:
    (folder / "EXES").mkdir(parents=True)
    (folder / "EXES" / "LINEUP.EXE").write_bytes(b"MZ")
    if with_map:
        (folder / "EXES" / "LINEUP.MAP").write_text(" 0AA1:0422       Player1\n")
    if with_store:
        for name in (demo.PROFILE, demo.SCREEN_MAP, demo.SCRIPT, demo.CONF_SCRIPT):
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text("{}")
        (folder / demo.CONF_SCRIPT).write_text(
            "#!/bin/sh\nmkdir -p TMP && : > TMP/dosbox-x-mcp.conf\n")
        (folder / demo.CONF_SCRIPT).chmod(0o755)
    return folder


@pytest.fixture(autouse=True)
def placed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host's own half answers yes, so what is judged here is the game's."""
    monkeypatch.setattr(demo, "precheck", lambda run: "")


def test_the_demo_needs_a_copy_of_the_game_with_its_store(tmp_path: Path) -> None:
    assert demo.checked(Run(dir=tmp_path)).startswith("pass --cwd")
    bare = _game(tmp_path / "bare", with_store=False)
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(bare)})).startswith(
        "no .scry/start/dos.json")
    no_map = _game(tmp_path / "no-map", with_map=False)
    assert "EXES/LINEUP.MAP" in demo.checked(Run(dir=tmp_path, options={"cwd": str(no_map)}))
    full = _game(tmp_path / "full")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(full)})) == ""


def test_the_game_s_own_script_derives_the_conf_the_profile_names(tmp_path: Path) -> None:
    game = _game(tmp_path / "game")
    args = demo.boot(Run(dir=tmp_path, options={"cwd": str(game)}))
    assert args == {"profile": str(game / demo.PROFILE), "shared": True,
                    "captures_dir": str(tmp_path / "lineup-captures")}
    assert (game / "TMP" / "dosbox-x-mcp.conf").is_file()


def test_the_map_is_the_game_s_and_a_copy_goes_with_the_load(tmp_path: Path) -> None:
    game = _game(tmp_path / "game")
    run = Run(dir=tmp_path / "run", options={"cwd": str(game)})
    run.dir.mkdir()
    assert demo.at(run) == game / demo.SCREEN_MAP
    step = next(s for s in demo.steps() if s.name == "map")
    args = cast(Callable[[Run], dict[str, Any]], step.args)(run)
    assert args == {"method": "load", "path": run.dir / demo.SCREEN_MAP.name}
    assert (run.dir / demo.SCREEN_MAP.name).read_text() == "{}"


def test_the_script_is_the_document_and_every_step_of_it_must_run(tmp_path: Path) -> None:
    game = _game(tmp_path / "game")
    (game / demo.SCRIPT).write_text(json.dumps({
        "version": 3, "steps": [{"op": "status", "recorded": {"ok": True}}, {"op": "stop"}]}))
    run = Run(dir=tmp_path, options={"cwd": str(game)})
    assert demo.played(Reply({"steps_completed": 2, "held": 1}), run) == (
        "2 steps of the game's own document, 1 holding to it")
    with pytest.raises(StepFailed, match="1 of 2 steps ran"):
        demo.played(Reply({"steps_completed": 1, "held": 1}), run)
    with pytest.raises(StepFailed, match="0 steps held, the document records 1"):
        demo.played(Reply({"steps_completed": 2, "held": 0}), run)


def test_the_binding_fires_every_action_the_script_declares() -> None:
    assert set(demo.INPUTS) == set(lineup.ACTIONS)
    names = [s.name for s in demo.DEMO.steps]
    assert len(names) == len(set(names)), "a step name is the key its reply is kept by"
    assert demo.BINDING.frames(2000) == 141
