"""The LineUp demo's DOSBox-X binding, without an emulator: where it refuses to start, the conf it
starts from, and where it places the game's symbols."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed
from scry_core.games import lineup

from demos.lineup import demo
from scry_dosbox_x import launch


def _game(folder: Path, *, with_map: bool = True) -> Path:
    (folder / "EXES").mkdir(parents=True)
    (folder / "EXES" / "LINEUP.EXE").write_bytes(b"MZ")
    if with_map:
        (folder / "EXES" / "LINEUP.MAP").write_text(" 0AA1:0422       Player1\n")
    return folder


@pytest.fixture(autouse=True)
def placed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host's own half answers yes, so what is judged here is the game's."""
    monkeypatch.setattr(demo, "precheck", lambda run: "")


def test_the_demo_needs_a_copy_of_the_game_with_its_map(tmp_path: Path) -> None:
    assert demo.checked(Run(dir=tmp_path)).startswith("pass --cwd")
    game = _game(tmp_path / "game", with_map=False)
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(game)})) == (
        f"no EXES/LINEUP.MAP under --cwd {game}")
    full = _game(tmp_path / "full")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(full)})) == ""


def test_the_conf_is_the_committed_one_and_the_map_goes_with_the_start(tmp_path: Path) -> None:
    game = _game(tmp_path / "game")
    args = demo.boot(Run(dir=tmp_path, options={"cwd": str(game)}))
    conf = Path(args["conf"]).read_text()
    assert conf == (demo.HERE / "lineup.conf").read_text().replace("@GUEST@",
                                                                    str(launch.GUEST_DIR))
    assert "@GUEST@" not in conf and "core=normal" in conf
    assert args["shared"] is True and "display" not in args
    assert args["symbols"] == tmp_path / "LINEUP.MAP"
    assert (tmp_path / "LINEUP.MAP").read_text() == (game / "EXES" / "LINEUP.MAP").read_text()


def test_the_boot_stop_must_have_placed_the_map(tmp_path: Path) -> None:
    placed = {"placed": True, "load_segment": "08ED", "loaded": 385}
    assert "its map placed at segment 08ED, 385 symbols" in demo.in_game(
        Reply({"verdict": "ELAPSED", "symbols_placed": placed}), Run(dir=tmp_path))
    for said in ({}, {"symbols_placed": {"placed": False, "why": "real mode"}}):
        with pytest.raises(StepFailed, match="placed no map"):
            demo.in_game(Reply({"verdict": "ELAPSED", **said}), Run(dir=tmp_path))


def test_the_binding_fires_every_action_the_script_declares() -> None:
    assert set(demo.INPUTS) == set(lineup.ACTIONS)
    names = [s.name for s in demo.DEMO.steps]
    assert len(names) == len(set(names)), "a step name is the key its reply is kept by"
    assert demo.BINDING.frames(2000) == 141
