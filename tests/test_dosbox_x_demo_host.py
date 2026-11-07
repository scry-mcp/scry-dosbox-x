"""What the game demos share through `demos.host`, without an emulator: the reader's copy, the
conf its own script derives, and the map the boot's stop places."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed

from demos import host
from scry_dosbox_x import launch

SCRIPT = Path("SCRIPTS/derive.sh")


def _copy(folder: Path, script: str) -> Path:
    (folder / SCRIPT).parent.mkdir(parents=True)
    (folder / SCRIPT).write_text(script)
    (folder / SCRIPT).chmod(0o755)
    (folder / "GAME.EXE").write_bytes(b"MZ")
    return folder


def test_a_copy_is_judged_by_what_it_lacks(tmp_path: Path) -> None:
    assert host.missing_under(Run(dir=tmp_path), (SCRIPT,), "the copy") == "pass --cwd, the copy"
    copy = _copy(tmp_path / "copy", "#!/bin/sh\n")
    run = Run(dir=tmp_path, options={"cwd": str(copy)})
    assert host.missing_under(run, (SCRIPT, Path("GAME.EXE")), "the copy") == ""
    assert host.missing_under(run, (Path("GAME.EXE"), Path("A.MAP"), Path("B.MAP")), "x") == (
        f"no A.MAP or B.MAP under --cwd {copy}")


def test_a_relative_copy_is_refused_before_start(tmp_path: Path) -> None:
    assert host.missing_under(Run(dir=tmp_path, options={"cwd": "../g"}), (), "x") == (
        "the server takes absolute or ~-led paths only: --cwd ../g")


def test_the_close_must_find_the_guest_gone(tmp_path: Path) -> None:
    assert host.quit_cleanly(Reply({"ended_by": "quit"}), Run(dir=tmp_path)).startswith("closed")
    with pytest.raises(StepFailed, match="ended by killed"):
        host.quit_cleanly(Reply({"ended_by": "killed"}), Run(dir=tmp_path))


def test_a_tilde_led_copy_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert host.checkout(Run(dir=tmp_path, options={"cwd": "~/g"})) == tmp_path / "g"


def test_the_game_s_script_derives_with_the_server_s_guest_directory(tmp_path: Path) -> None:
    copy = _copy(tmp_path / "copy", "#!/bin/sh\nprintf '%s\\n' \"$DOSBOX_GUEST\" > derived\n")
    host.conf_derived(Run(dir=tmp_path, options={"cwd": str(copy)}), SCRIPT)
    assert (copy / "derived").read_text().strip() == launch.GUEST_DIR.as_posix()


def test_a_script_that_refuses_ends_the_step_with_its_own_words(tmp_path: Path) -> None:
    copy = _copy(tmp_path / "copy", "#!/bin/sh\necho 'no stub' >&2\nexit 3\n")
    with pytest.raises(StepFailed, match="exited 3: no stub"):
        host.conf_derived(Run(dir=tmp_path, options={"cwd": str(copy)}), SCRIPT)


def test_the_boot_stop_must_have_placed_the_map(tmp_path: Path) -> None:
    placed = {"placed": True, "load_segment": "08ED", "loaded": 385}
    assert "its map placed at segment 08ED, 385 symbols" in host.map_placed(
        Reply({"verdict": "ELAPSED", "symbols_placed": placed}), Run(dir=tmp_path))
    for said in ({}, {"symbols_placed": {"placed": False, "why": "real mode"}}):
        with pytest.raises(StepFailed, match="placed no map"):
            host.map_placed(Reply({"verdict": "ELAPSED", **said}), Run(dir=tmp_path))
