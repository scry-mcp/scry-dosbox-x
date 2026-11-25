"""`start(profile=)`: a repository's run recipe, found and read before the launch."""

from __future__ import annotations

import inspect
import json
from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest
from scry_core import project_store

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
    assert Path(arguments["conf"]) == tmp_path / "cfg" / "probe.conf"
    assert Path(arguments["cwd"]) == tmp_path / "guest"
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


def test_a_named_profile_not_found_without_cwd_says_cwd_is_required(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ds.Invalid) as e:
        lifecycle.with_profile("nowhere", keys=KEYS, arguments=call(), given=())
    assert "cwd" in str(e.value), str(e.value)


@pytest.mark.parametrize(("refusal", "hinted"), [
    (ds.Invalid("bad_argument", "nothing found", searched=["/a"]), True),
    (ds.Invalid("bad_argument", "no .scry/start/x.json above /a, and it is not JSON"), False),
])
def test_the_cwd_hint_follows_the_stores_searched_field_not_its_words(
        monkeypatch: pytest.MonkeyPatch, refusal: ds.Invalid, hinted: bool) -> None:
    def applied(*_a: object, **_k: object) -> None:
        raise refusal
    monkeypatch.setattr(project_store, "applied", applied)
    with pytest.raises(ds.Invalid) as e:
        lifecycle.with_profile("guest", keys=KEYS, arguments=call(), given=())
    assert ("Pass `cwd`" in str(e.value)) is hinted, str(e.value)
    assert e.value.fields == refusal.fields, "the hint keeps what the store's refusal carried"


def test_a_profile_passed_as_a_path_not_found_carries_no_cwd_hint(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ds.Invalid) as e:
        lifecycle.with_profile(str(tmp_path / "missing.json"), keys=KEYS,
                               arguments=call(), given=())
    assert "cwd" not in str(e.value), str(e.value)


def test_a_key_no_start_takes_is_refused_by_name(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    stored(tmp_path, {**RECIPE, "steps": []})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ds.Invalid, match="steps"):
        lifecycle.with_profile("guest", keys=KEYS, arguments=call(), given=())


def test_start_with_no_conf_and_no_profile_is_refused_naming_the_argument() -> None:
    with pytest.raises(ds.Invalid, match="conf"):
        lifecycle.required(conf="", cwd="/guest", session_seconds=30)


def test_a_profile_sets_the_overlay_as_the_object_it_is_and_the_start_judges_it_as_the_model(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake
    from scry_core import overlay as ov

    from scry_dosbox_x import presence as dpresence
    from scry_dosbox_x import state as dstate
    stored(tmp_path, {"overlay": {"record": False}})
    seen: list[ov.Overlay] = []

    def lit(session: Any, asked: bool, shared: bool, overlay: ov.Overlay,
            drawn: Collection[str]) -> Any:
        seen.append(overlay)
        return dpresence.NEVER_DRAWN
    monkeypatch.setattr(dpresence, "open_shown", lit)
    dstate.STATE.session = None
    out = _start_on_a_booted_fake(tmp_path, monkeypatch, profile=str(tmp_path / ".scry" / "start"
                                                                  / "guest.json"))
    assert out["status"] == "ok", out
    assert "overlay" in out["profile"]["supplied"], out["profile"]
    assert seen == [ov.Overlay(record=False)]
    dstate.STATE.session = None


def test_a_kept_recipe_holds_the_overlay_as_json_and_only_when_it_is_not_the_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake

    from scry_dosbox_x import state as dstate
    for asked, kept in (({"record": False}, True), ({}, False)):
        dstate.STATE.session = None
        dstate.STATE.drafts = type(dstate.STATE.drafts)()
        out = _start_on_a_booted_fake(tmp_path, monkeypatch, overlay=asked)
        assert out["status"] == "ok", out
        documents = [c.document for c in dstate.STATE.drafts.kept.values()]
        if kept:
            assert documents and documents[0]["overlay"] == {
                "pointer": True, "record": False}
            json.dumps(documents[0])
        else:
            assert all("overlay" not in d for d in documents), documents
    dstate.STATE.session = None
