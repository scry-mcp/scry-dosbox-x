"""`promote`: what a session learned, kept as a candidate and written on approval."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest
from scry_core import given, media_replies, screen_map, tool_replies
from scry_core import promote as core_promote
from scry_core.reply_contract import Invalid

from scry_dosbox_x import checks, lifecycle, replies, server
from scry_dosbox_x import promote as mpromote
from scry_dosbox_x import state as dst

STATE = dst.STATE

START: dict[str, Any] = {
    "conf": "/x/probe.conf", "cwd": "/x", "session_seconds": 900, "program": "",
    "logfile": "", "state_dir": "/tmp/run", "shared": True, "presence": False,
    "break_on_int3": True, "captures_dir": "", "guest_files": None, "plan": None,
    "settle_seconds": None, "input_port": 0, "display": None, "size": None,
    "fullscreen": None, "background": None, "flags": None, "binary": "", "symbols": "",
}


def noted(params: dict[str, Any]) -> None:
    """What a start that ran leaves noted: `launching` once its launch returned."""
    with mpromote.launching(params):
        pass


def screen(name: str = "play") -> screen_map.Screen:
    return screen_map.Screen(name, "text", (80, 25), (((0, 0, 8, 1), "0" * 16),), (),
                             "rgb", "")


def perform_document() -> dict[str, Any]:
    return {"version": 3, "server": "dosbox-x", "entry": "probe",
            "start": {"conf": "/x/probe.conf", "cwd": "/x"},
            "steps": [{"op": "read_memory", "ref": "0x10", "length": 2,
                       "recorded": {"data": "abcd"}}],
            "needs": {"states": [], "declarations": {}}}


@pytest.fixture(autouse=True)
def fresh_drafts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ambient = tmp_path / "ambient"
    (ambient / ".scry").mkdir(parents=True)
    monkeypatch.chdir(ambient)
    STATE.drafts = core_promote.Drafts()
    STATE.maps = screen_map.Maps()
    STATE.guest = ""


def test_the_tool_takes_the_review_and_the_approval() -> None:
    names = set(inspect.signature(server.promote).parameters)
    assert {"dry_run", "entries", "names", "root"} <= names


def test_the_reply_models_carry_what_a_promotion_says() -> None:
    assert "kept" in replies.StartReply.__annotations__
    assert "kept" in media_replies.PerformExportFields.__annotations__
    assert "kept" in tool_replies.MapWriteFields.__annotations__
    assert "draft" in replies.CloseReply.__annotations__
    assert "candidates" in replies.PromoteReply.__annotations__


def test_promote_is_no_step_of_a_sequence() -> None:
    assert "promote" in checks.NOT_STEPS and "promote" in checks.MACHINE_JUDGES


def test_a_guest_is_named_by_its_program_s_own_stem() -> None:
    assert mpromote.guest_name({"program": "MOUSE.COM", "conf": "/x/p.conf"}) == "mouse"
    assert mpromote.guest_name({"program": "C:\\GAMES\\LINEUP.EXE"}) == "lineup"
    assert mpromote.guest_name({"program": "", "conf": "/x/PROBE.CONF"}) == "probe"
    assert mpromote.guest_name({"conf": "/x/My Games/probe.conf"}) == "probe"
    assert mpromote.guest_name({}) == ""


def test_a_refused_start_leaves_the_live_session_s_guest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(**_arguments: Any) -> dict[str, Any]:
        raise Invalid("session_live", "a session is already live")
    monkeypatch.setattr(lifecycle, "start", refused)
    STATE.guest = "probe"
    got = server.start(conf=str(tmp_path / "lineup.conf"), cwd=str(tmp_path),
                       session_seconds=60, program="LINEUP.EXE")
    assert got["code"] == "session_live" and STATE.guest == "probe", (got, STATE.guest)


def test_the_guest_is_noted_before_the_launch_so_a_plan_s_add_knows_it() -> None:
    with mpromote.launching({**START, "program": "LINEUP.EXE"}):
        assert STATE.guest == "lineup"
        STATE.maps.session["play"] = screen()
        kept = mpromote.after_map("add", {"screen": "play"})["kept"]
    assert kept.startswith("kept 1 (promote to review)")
    assert STATE.drafts.entries() == ["maps/lineup"]


def test_a_start_keeps_its_recipe_without_the_run_s_own_arguments() -> None:
    noted(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    kept = STATE.drafts.held("start", "probe")[0].document
    assert kept == {"format": "scry-start/1", "conf": "/x/probe.conf", "cwd": "/x",
                    "session_seconds": 900, "shared": True, "presence": False,
                    "break_on_int3": True}


def test_a_start_from_a_profile_is_named_by_the_profile_it_read() -> None:
    noted({**START, "program": "LINEUP.EXE"})
    STATE.drafts.loaded_entry("start", "dos")
    mpromote.keep_start({**START, "program": "LINEUP.EXE"}, defaults=server._START_DEFAULTS)
    assert STATE.drafts.entries() == ["start/dos"]


def test_a_start_with_no_program_and_no_conf_proposes_nothing() -> None:
    noted({**START, "conf": ""})
    assert mpromote.keep_start({**START, "conf": ""},
                               defaults=server._START_DEFAULTS) is False
    assert STATE.drafts.entries() == []


def test_a_map_add_is_named_by_the_entry_this_session_read() -> None:
    STATE.guest = "probe"
    STATE.maps.session_application = "lineup"
    STATE.maps.session["play"] = screen()
    reply = mpromote.after_map("add", {"screen": "play"})
    assert reply["kept"].startswith("kept 1 (promote to review)")
    assert STATE.drafts.entries() == ["maps/lineup"]
    assert STATE.drafts.held("maps", "lineup")[0].document["application"] == "lineup"


def test_a_map_add_after_a_start_is_named_by_the_guest() -> None:
    STATE.guest = "probe"
    STATE.maps.session["play"] = screen()
    kept = mpromote.after_map("add", {"screen": "play"})["kept"]
    assert kept.startswith("kept 1 (promote to review)")
    assert STATE.drafts.entries() == ["maps/probe"]


def test_a_map_save_and_a_map_load_keep_nothing() -> None:
    STATE.guest = "probe"
    STATE.maps.session["play"] = screen()
    saved = mpromote.after_map("save", {"application": "lineup", "screens": 1})
    assert saved == {"application": "lineup", "screens": 1}
    assert STATE.drafts.entries() == [] and STATE.drafts.loaded == {}


def test_a_map_load_keeps_nothing_and_names_the_entry_it_read(tmp_path: Path) -> None:
    read = str(tmp_path / ".scry" / "maps" / "lineup-screen-map.json")
    loaded = {"application": "lineup", "path": read}
    assert mpromote.after_map("load", loaded) == loaded
    assert STATE.drafts.entries() == []
    assert (STATE.drafts.loaded_name("maps"), STATE.drafts.sources["maps"]) == ("lineup", read)


def test_a_map_loaded_from_another_store_and_added_to_belongs_to_that_store(
        tmp_path: Path) -> None:
    (tmp_path / "game").mkdir()
    with STATE.drafts.starting(anchor=str(tmp_path / "game")):
        pass
    other = tmp_path / "other" / ".scry" / "maps" / "lineup-screen-map.json"
    other.parent.mkdir(parents=True)
    mpromote.after_map("load", {"application": "lineup", "path": str(other)})
    STATE.maps.session_application = "lineup"
    STATE.maps.session["play"] = screen()
    mpromote.after_map("add", {"screen": "play"})
    assert STATE.drafts.held("maps", "lineup")[0].project == str(tmp_path / "other")


def test_a_map_add_with_no_screen_proposes_nothing() -> None:
    STATE.guest = "probe"
    assert mpromote.after_map("add", {"screen": "play"}) == {"screen": "play"}
    assert STATE.drafts.entries() == []


def test_a_map_add_with_no_name_at_all_proposes_nothing() -> None:
    STATE.maps.session["play"] = screen()
    assert mpromote.after_map("add", {"screen": "play"}) == {"screen": "play"}
    assert STATE.drafts.entries() == []


def exported(path: Path) -> dict[str, Any]:
    return core_promote.after_export(STATE.drafts, {"path": str(path)}, mpromote.PROMOTE_PATHS)


def test_an_export_keeps_its_document_named_by_the_file_it_wrote(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(perform_document()))
    assert exported(path)["kept"].startswith("kept 1 (promote to review)")
    assert STATE.drafts.entries() == ["perform/session"]


def test_an_export_after_a_replay_updates_the_entry_it_replayed(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(perform_document()))
    STATE.drafts.loaded_entry("perform", "dos")
    exported(path)
    assert STATE.drafts.entries() == ["perform/dos"]


def test_a_replay_the_reader_refuses_marks_no_entry(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({**perform_document(), "version": 2}))
    assert server.perform(path=str(path))["code"] == "bad_argument"
    assert STATE.drafts.loaded_name("perform") == ""


def test_close_reports_what_was_left_unkept() -> None:
    noted(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    reply = server.close()
    assert reply["draft"] == ["start/probe"]
    assert reply["closed"] is False


def test_close_leaves_out_what_the_store_already_holds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    recipe = {**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)}
    noted(recipe)
    mpromote.keep_start(recipe, defaults=server._START_DEFAULTS)
    server.promote(entries=["start/probe"], root=str(tmp_path))
    mpromote.keep_start(recipe, defaults=server._START_DEFAULTS)
    assert STATE.drafts.entries() == ["start/probe"]
    assert "draft" not in server.close()


def test_a_promotion_empties_the_draft_and_close_then_says_nothing(tmp_path: Path) -> None:
    noted({**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)})
    mpromote.keep_start({**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)},
                        defaults=server._START_DEFAULTS)
    server.promote(entries=["start/probe"], root=str(tmp_path))
    assert STATE.drafts.entries() == []
    assert "draft" not in server.close()


def test_promote_reviews_and_writes_in_a_store_of_its_own(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    params = {**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)}
    noted(params)
    mpromote.keep_start(params, defaults=server._START_DEFAULTS)
    review = server.promote(dry_run=True, root=str(tmp_path))
    assert [c["entry"] for c in review["candidates"]] == ["start/probe"]
    written = server.promote(entries=["start/probe"], root=str(tmp_path))
    assert written["written"][0]["file"] == ".scry/start/probe.json"
    document = json.loads((tmp_path / ".scry" / "start" / "probe.json").read_text())
    assert document["conf"] == "${root}/probe.conf" and document["cwd"] == "${root}"


def test_a_promotion_with_no_store_names_root(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    noted(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    reply = server.promote(dry_run=True)
    assert reply["code"] == "bad_argument" and "root" in reply["message"]


def test_a_root_creates_the_store_only_on_the_approved_call(tmp_path: Path) -> None:
    repo = tmp_path / "game"
    repo.mkdir()
    params = {**START, "conf": str(repo / "probe.conf"), "cwd": str(repo)}
    noted(params)
    mpromote.keep_start(params, defaults=server._START_DEFAULTS)
    assert server.promote(dry_run=True, root=str(repo))["candidates"][0]["change"] == "new"
    assert not (repo / ".scry").exists()
    server.promote(entries=["start/probe"], root=str(repo))
    assert (repo / ".scry" / "start" / "probe.json").is_file()


def test_a_start_that_only_loads_its_profile_learned_nothing() -> None:
    STATE.drafts.loaded_entry("start", "dos")
    with given.remembered({"profile", "state_dir"}):
        assert mpromote.keep_start({**START, "program": "LINEUP.EXE"},
                                   defaults=server._START_DEFAULTS) is False
    assert STATE.drafts.entries() == []
    with given.remembered({"profile", "session_seconds"}):
        assert mpromote.keep_start({**START, "program": "LINEUP.EXE"},
                                   defaults=server._START_DEFAULTS) is True


def test_a_kept_start_leaves_the_run_s_own_keys_to_the_store() -> None:
    noted(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    assert set(STATE.drafts.held("start", "probe")[0].own) == set(mpromote.RUN_OWN)


def test_a_start_s_guest_lives_in_its_cwd_else_its_conf_s_directory() -> None:
    assert mpromote.anchor({"cwd": " /game/guest ", "conf": "/elsewhere/run.conf"}) == \
        "/game/guest"
    assert mpromote.anchor({"cwd": "", "conf": "/game/run.conf"}) == str(Path("/game"))
    assert mpromote.anchor({}) == ""


def test_a_recipe_belongs_to_the_project_its_guest_runs_in(tmp_path: Path) -> None:
    game = tmp_path / "game"
    (game / ".scry").mkdir(parents=True)
    (game / "guest").mkdir()
    kept_probe(game / "guest")
    assert STATE.drafts.held("start", "probe")[0].project == str(game)
    assert server.promote(dry_run=True)["store"] == str(game / ".scry")


def test_a_recipe_read_from_a_profile_belongs_to_the_profile_s_store(tmp_path: Path) -> None:
    profile = tmp_path / "game" / ".scry" / "start" / "dos.json"
    profile.parent.mkdir(parents=True)
    bench = tmp_path / "bench"
    bench.mkdir()
    params = {**START, "conf": str(bench / "dos.conf"), "cwd": str(bench)}
    with mpromote.launching(params, str(profile)):
        pass
    with given.remembered({"profile", "session_seconds"}):
        mpromote.keep_start(params, defaults=server._START_DEFAULTS)
    assert STATE.drafts.held("start", "dos")[0].project == str(tmp_path / "game")


def test_a_refused_start_leaves_the_live_session_s_project(tmp_path: Path) -> None:
    (tmp_path / "game").mkdir()
    noted({**START, "cwd": str(tmp_path / "game")})
    with pytest.raises(Invalid), mpromote.launching({**START, "cwd": str(tmp_path)}):
        raise Invalid("session_live", "a session is already live")
    STATE.maps.session["play"] = screen()
    mpromote.after_map("add", {"screen": "play"})
    assert STATE.drafts.held("maps", "probe")[0].project == str(tmp_path / "game")


def test_a_start_refused_with_its_own_session_live_keeps_its_guest_and_project(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "game").mkdir()
    monkeypatch.setattr(STATE, "session", None)
    noted({**START, "cwd": str(tmp_path / "old")})
    with pytest.raises(Invalid), mpromote.launching(
            {**START, "cwd": str(tmp_path / "game"), "program": "LINEUP.EXE"}):
        monkeypatch.setattr(STATE, "session", object())
        raise Invalid("window_not_visible", "the window never appeared")
    assert STATE.guest == "lineup" and STATE.drafts.started_in == str(tmp_path / "game")


def test_two_projects_each_keep_their_own_recipe_and_store(tmp_path: Path) -> None:
    game, bare = tmp_path / "game", tmp_path / "bare"
    (game / ".scry").mkdir(parents=True)
    (bare / ".git").mkdir(parents=True)
    kept_probe(game, program="ALPHA.EXE")
    kept_probe(bare, program="BETA.EXE")
    kept = core_promote.kept_line(STATE.drafts)
    assert f"start/beta: no .scry/ in {bare}" in kept and f"root={bare})" in kept, kept
    review = server.promote(dry_run=True)
    assert review["store"] == str(game / ".scry")
    assert [c["entry"] for c in review["candidates"]] == ["start/alpha"]
    assert [u["entry"] for u in review["unwritable"]] == ["start/beta"]
    refused = server.promote(entries=["start/alpha", "start/beta"])
    assert refused["code"] == "bad_argument" and "start/beta" in refused["message"]
    server.promote(entries=["start/alpha"])
    assert not (game / ".scry" / "start" / "beta.json").exists()
    assert not (bare / ".scry").exists()


def working_directory_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The working directory cannot be resolved, as when it was deleted: Windows refuses to
    delete a process's own working directory, so the state is reached without deleting it."""
    def gone() -> str:
        raise FileNotFoundError("the working directory")
    monkeypatch.setattr(os, "getcwd", gone)


def test_a_working_directory_that_is_gone_does_not_cost_the_reply(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".scry").mkdir()
    working_directory_gone(monkeypatch)
    kept_probe(tmp_path)
    assert core_promote.kept_line(STATE.drafts) == "kept 1 (promote to review)"


def test_a_promote_with_a_root_does_not_need_the_working_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    working_directory_gone(monkeypatch)
    kept_probe(tmp_path)
    assert server.promote(dry_run=True, root=str(tmp_path))["store"] == str(tmp_path / ".scry")


SETUP = [".scry/", ".scry/about.json", ".scry/README.md"]


def kept_probe(repo: Path, **more: Any) -> None:
    params = {**START, "conf": str(repo / "probe.conf"), "cwd": str(repo), **more}
    noted(params)
    mpromote.keep_start(params, defaults=server._START_DEFAULTS)


def test_an_approved_promotion_into_a_bare_repository_sets_up_the_store(tmp_path: Path) -> None:
    repo = tmp_path / "game"
    repo.mkdir()
    kept_probe(repo)
    review = server.promote(dry_run=True, root=str(repo))
    assert review["would_create"] == SETUP and "created" not in review
    assert not (repo / ".scry").exists()
    written = server.promote(entries=["start/probe"], root=str(repo))
    assert written["created"] == SETUP and "would_create" not in written
    assert json.loads((repo / ".scry" / "about.json").read_text())["server"] == "dosbox-x"
    assert (repo / ".scry" / "README.md").is_file()


def test_a_second_promotion_creates_nothing_more(tmp_path: Path) -> None:
    kept_probe(tmp_path)
    server.promote(entries=["start/probe"], root=str(tmp_path))
    kept_probe(tmp_path, session_seconds=901)
    assert "created" not in server.promote(entries=["start/probe"], root=str(tmp_path))


def test_a_kept_line_says_how_to_set_up_a_store_only_when_none_is_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    kept_probe(tmp_path)
    assert f"no .scry/ in {tmp_path}" in core_promote.kept_line(STATE.drafts)
    (tmp_path / ".scry").mkdir()
    assert core_promote.kept_line(STATE.drafts) == "kept 1 (promote to review)"


def test_a_store_in_the_server_s_own_directory_does_not_silence_the_hint(
        tmp_path: Path) -> None:
    (tmp_path / "game").mkdir()
    kept_probe(tmp_path / "game")
    assert f"no .scry/ in {tmp_path / 'game'}" in core_promote.kept_line(STATE.drafts)


def test_an_export_names_the_missing_store_too(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(perform_document()))
    noted({**START, "cwd": str(tmp_path)})
    assert f"no .scry/ in {tmp_path}" in exported(path)["kept"]
