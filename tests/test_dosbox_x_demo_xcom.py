"""The X-COM Apocalypse demo without an emulator: which copy of the game it refuses, the conf it
starts from, and how it reads the DOS calls and the screen."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed

from demos import host
from demos.xcom import demo


@pytest.fixture(autouse=True)
def placed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host's own half answers yes, so what is judged here is the game's copy."""
    monkeypatch.setattr(host, "precheck", lambda run: "")
    monkeypatch.setattr(demo, "precheck", lambda run: "")


def _game(folder: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of tiny files, whose digests the demo is told to expect."""
    pins = {}
    for n, part in enumerate(demo.GAME):
        (folder / part).parent.mkdir(parents=True, exist_ok=True)
        (folder / part).write_bytes(bytes([n + 1]) * 64)
        pins[part] = hashlib.sha256((folder / part).read_bytes()).hexdigest()
    monkeypatch.setattr(demo, "GAME", pins)
    return folder


def _run(tmp_path: Path, cwd: Path | str | None) -> Run:
    return Run(dir=tmp_path / "run", options={} if cwd is None else {"cwd": str(cwd)})


def test_the_demo_refuses_anything_but_the_edition_it_was_written_for(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert demo.checked(_run(tmp_path, None)).startswith("pass --cwd")
    assert "absolute or ~-led" in demo.checked(_run(tmp_path, "x-com"))
    game = _game(tmp_path / "game", monkeypatch)
    assert demo.checked(_run(tmp_path, game)) == ""
    (game / "XCOMA/XCOMAPOC.EXE").write_bytes(b"another edition")
    assert "is another edition" in demo.checked(_run(tmp_path, game))
    (game / "XCOMA/XCOMAPOC.EXE").unlink()
    assert demo.checked(_run(tmp_path, game)).startswith("no XCOMA/XCOMAPOC.EXE under")


def test_the_conf_lays_the_runs_overlay_over_the_readers_copy(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game(tmp_path / "game", monkeypatch)
    run = _run(tmp_path, game)
    run.dir.mkdir()
    args = demo.boot(run)
    conf = Path(args["conf"]).read_text()
    assert f'mount c "{game}"' in conf
    assert f'mount -t overlay c "{run.dir / "c-overlay"}"' in conf
    assert (run.dir / "c-overlay").is_dir()
    assert "@GAME@" not in conf and "@OVERLAY@" not in conf
    assert Path(args["conf"]).parent == run.dir and args["cwd"] == str(game)
    assert args["program"] == "XCOMAPOC.EXE" and args["dos_calls"] is True


def test_a_conf_without_its_token_is_refused(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game(tmp_path / "game", monkeypatch)
    run = _run(tmp_path, game)
    run.dir.mkdir()
    template = tmp_path / "xcom.conf"
    template.write_text("[autoexec]\nmount c \"@GAME@\"\n")
    monkeypatch.setattr(demo, "HERE", tmp_path)
    with pytest.raises(StepFailed, match="@OVERLAY@"):
        demo.conf(run)


def test_a_wait_passes_only_when_its_call_arrived(tmp_path: Path) -> None:
    run = _run(tmp_path, None)
    check = demo.reached("the main menu is drawn")
    reply = Reply({"verdict": "TARGET", "call": {"file": "ufodata/b-setup.pcx  ", "name": "x"}})
    assert check(reply, run) == "the main menu is drawn: ufodata/b-setup.pcx"
    free = Reply({"verdict": "TARGET", "call": {"name": "get free disk space"}})
    assert check(free, run) == "the main menu is drawn: get free disk space"
    with pytest.raises(StepFailed, match="TIMEOUT"):
        check(Reply({"verdict": "TIMEOUT", "note": "not seen"}), run)


def test_an_input_that_went_nowhere_fails(tmp_path: Path) -> None:
    run = _run(tmp_path, None)
    assert demo.posted(Reply({"posted": 1, "summary": "posted"}), run) == "the input went in"
    with pytest.raises(StepFailed, match="nothing went in"):
        demo.posted(Reply({"posted": 0, "summary": "no stub"}), run)


def test_a_click_whose_pointer_never_arrived_fails(tmp_path: Path) -> None:
    run = _run(tmp_path, None)
    reply = Reply({"driver_arrived": True, "x": 317, "y": 186, "summary": "clicked"})
    assert demo.clicked(reply, run) == "pressed at 317,186"
    with pytest.raises(StepFailed, match="did not arrive"):
        demo.clicked(Reply({"driver_arrived": False, "summary": "no stub"}), run)


def test_the_files_step_needs_the_citys_map_among_many_lookups(tmp_path: Path) -> None:
    run = _run(tmp_path, None)
    calls = [{"file": f"UFODATA/F{n}"} for n in range(60)]
    with pytest.raises(StepFailed, match=demo.CITY_MAP):
        demo.looked_up(Reply({"calls": calls}), run)
    calls.append({"file": demo.CITY_MAP + "  "})
    assert "61 FindFirst calls" in demo.looked_up(Reply({"calls": calls}), run)
    with pytest.raises(StepFailed, match="only 1"):
        demo.looked_up(Reply({"calls": [{"file": demo.CITY_MAP}]}), run)
