"""The LineUp demo's DOSBox-X binding, without an emulator: where it refuses to start, the conf it
starts from, and where it places the game's symbols."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed
from scry_core.games import lineup

from demos.lineup import demo


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


def test_the_conf_is_the_committed_one_with_this_checkouts_stub_written_in(
        tmp_path: Path) -> None:
    args = demo.boot(Run(dir=tmp_path))
    conf = Path(args["conf"]).read_text()
    assert conf == (demo.HERE / "lineup.conf").read_text().replace("@GUEST@",
                                                                    str(demo.ROOT / "guest"))
    assert "@GUEST@" not in conf and "core=normal" in conf
    assert (args["shared"], args["display"]) == (True, "secondary")


def test_the_symbols_go_at_the_segment_the_boot_stopped_in(tmp_path: Path) -> None:
    game = _game(tmp_path / "game")
    run = Run(dir=tmp_path, options={"cwd": str(game)},
              replies={"boot": Reply({"pc": "08ED:00001CAE"})})
    args = demo.symbols(run)
    assert args == {"path": tmp_path / "LINEUP.MAP", "base": "8ed0"}
    assert (tmp_path / "LINEUP.MAP").read_text() == (game / "EXES" / "LINEUP.MAP").read_text()


@pytest.mark.parametrize("pc", ["F000:0000CA40", "C000:00000010"])
def test_a_boot_that_stopped_in_rom_is_no_load_segment(tmp_path: Path, pc: str) -> None:
    reply = Reply({"verdict": "ELAPSED", "pc": pc})
    with pytest.raises(StepFailed, match="outside the program"):
        demo.in_game(reply, Run(dir=tmp_path))
    assert "loaded at segment 08ED" in demo.in_game(
        Reply({"verdict": "ELAPSED", "pc": "08ED:00001CAE"}), Run(dir=tmp_path))


def test_the_binding_fires_every_action_the_script_declares() -> None:
    assert set(demo.INPUTS) == set(lineup.ACTIONS)
    names = [s.name for s in demo.DEMO.steps]
    assert len(names) == len(set(names)), "a step name is the key its reply is kept by"
    assert demo.BINDING.frames(2000) == 141
