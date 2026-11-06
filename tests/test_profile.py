"""`start(profile=)`: a repository's run recipe, found and read before the launch."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from scry_dosbox_x import lifecycle, replies, server
from scry_dosbox_x import session as ds

#: What a DOSBox-X profile may set: `start`'s own arguments but for the profile itself.
KEYS = tuple(name for name in inspect.signature(server.start).parameters
             if name not in ("ctx", "profile"))

RECIPE = {"conf": "cfg/probe.conf", "cwd": "guest", "session_seconds": 120}


def stored(root: Path, values: dict[str, Any], name: str = "guest") -> Path:
    path = root / ".scry" / "start" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"format": "scry-start/1", **values}), encoding="utf-8")
    return path


def call(**values: Any) -> dict[str, Any]:
    return {"conf": "", "cwd": "", "session_seconds": None, "program": "", **values}


def test_start_takes_a_profile() -> None:
    assert "profile" in inspect.signature(server.start).parameters


def test_the_reply_model_carries_the_profile_block() -> None:
    assert "profile" in replies.StartReply.__annotations__


def test_a_profile_fills_what_the_caller_did_not_give(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    stored(tmp_path, RECIPE)
    monkeypatch.chdir(tmp_path)
    arguments, block = lifecycle.with_profile("guest", keys=KEYS, arguments=call(), given=())
    assert arguments["conf"] == str(tmp_path / "cfg" / "probe.conf")
    assert arguments["cwd"] == str(tmp_path / "guest")
    assert arguments["session_seconds"] == 120
    assert block["supplied"] == ["conf", "cwd", "session_seconds"]


def test_a_callers_argument_wins_over_the_profile(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    stored(tmp_path, RECIPE)
    monkeypatch.chdir(tmp_path)
    arguments, block = lifecycle.with_profile("guest", keys=KEYS,
                                              arguments=call(conf="/mine/boot.conf"),
                                              given={"conf"})
    assert arguments["conf"] == "/mine/boot.conf"
    assert block["supplied"] == ["cwd", "session_seconds"]


def test_the_block_names_the_profile_and_the_file_it_read(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    entry = stored(tmp_path, RECIPE)
    monkeypatch.chdir(tmp_path)
    _arguments, block = lifecycle.with_profile("guest", keys=KEYS, arguments=call(), given=())
    assert block == {"name": "guest", "file": str(entry),
                     "supplied": ["conf", "cwd", "session_seconds"]}


def test_a_profile_found_nowhere_is_refused_naming_the_directories_searched(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ds.Invalid, match="searched"):
        lifecycle.with_profile("nowhere", keys=KEYS, arguments=call(), given=())


def test_a_key_no_start_takes_is_refused_by_name(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    stored(tmp_path, {**RECIPE, "steps": []})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ds.Invalid, match="steps"):
        lifecycle.with_profile("guest", keys=KEYS, arguments=call(), given=())


def test_start_with_no_conf_and_no_profile_is_refused_naming_the_argument() -> None:
    with pytest.raises(ds.Invalid, match="conf"):
        lifecycle.required(conf="", cwd="/guest", session_seconds=30)
