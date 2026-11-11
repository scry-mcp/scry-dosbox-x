"""The Speed Fight demo's DOSBox-X binding, without an emulator: what it demands of the game's
copy and what it adds to the game's recipe. The pieces it shares with the other game demos are
judged in test_dosbox_x_demo_host.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from scry_core.demo import Run

from demos.speedf import demo

#: What the game's copy has to hold, as the demo names it.
REQUIRED = ("EXES/SPEEDF.EXE", "EXES/SPEEDF.MAP", ".scry/start/dos.json",
            "SCRIPTS/dosbox-mcp-conf.sh")


@pytest.fixture(autouse=True)
def host_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host's own half answers yes, so what is judged here is the game's."""
    monkeypatch.setattr(demo, "precheck", lambda run: "")


def _copy(folder: Path, *, without: str = "") -> Path:
    for name in REQUIRED:
        if name != without:
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text("x")
    return folder


def test_each_file_the_copy_lacks_is_named(tmp_path: Path) -> None:
    for missing in REQUIRED:
        copy = _copy(tmp_path / missing.replace("/", "_"), without=missing)
        assert demo.checked(Run(dir=tmp_path, options={"cwd": str(copy)})) == (
            f"no {missing} under --cwd {copy}")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(_copy(tmp_path / "whole"))})) == ""


def test_the_call_adds_the_window_and_its_captures_to_the_recipe(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    derived: list[Path] = []
    monkeypatch.setattr(demo, "conf_derived", lambda run, script: derived.append(script))
    copy = _copy(tmp_path / "copy")
    assert demo.boot(Run(dir=tmp_path, options={"cwd": str(copy)})) == {
        "profile": str(copy / demo.PROFILE), "shared": True,
        "flags": demo.NORMAL_CORE_FIXED_CLOCK,
        "captures_dir": str(tmp_path / "speedf-captures")}
    assert derived == [demo.CONF_SCRIPT], "the game's own deriver ran first"


def test_the_host_s_own_refusal_comes_first(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo, "precheck", lambda run: "no dosbox-x here")
    assert demo.checked(Run(dir=tmp_path, options={"cwd": str(tmp_path)})) == "no dosbox-x here"


def test_every_step_name_is_unique() -> None:
    names = [s.name for s in demo.DEMO.steps]
    assert len(names) == len(set(names)), "a step name is the key its reply is kept by"
