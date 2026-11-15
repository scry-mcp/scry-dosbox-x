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

from scry_dosbox_x import checks, replies, server
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


def test_the_guest_is_noted_before_the_launch_so_a_plan_s_add_knows_it() -> None:
    mpromote.note_start({**START, "program": "LINEUP.EXE"})
    assert STATE.guest == "lineup"
    STATE.maps.session["play"] = screen()
    assert mpromote.after_map("add", {"screen": "play"})["kept"] == "kept 1 (promote to review)"
    assert STATE.drafts.entries() == ["maps/lineup"]


def test_a_start_keeps_its_recipe_without_the_run_s_own_arguments() -> None:
    mpromote.note_start(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    kept = STATE.drafts.kept["start", "probe"].document
    assert kept == {"format": "scry-start/1", "conf": "/x/probe.conf", "cwd": "/x",
                    "session_seconds": 900, "shared": True, "presence": False,
                    "break_on_int3": True}


def test_a_start_from_a_profile_is_named_by_the_profile_it_read() -> None:
    mpromote.note_start({**START, "program": "LINEUP.EXE"})
    STATE.drafts.loaded_entry("start", "dos")
    mpromote.keep_start({**START, "program": "LINEUP.EXE"}, defaults=server._START_DEFAULTS)
    assert STATE.drafts.entries() == ["start/dos"]


def test_a_start_with_no_program_and_no_conf_proposes_nothing() -> None:
    mpromote.note_start({**START, "conf": ""})
    assert mpromote.keep_start({**START, "conf": ""},
                               defaults=server._START_DEFAULTS) is False
    assert STATE.drafts.entries() == []


def test_a_map_add_is_named_by_the_entry_this_session_read() -> None:
    STATE.guest = "probe"
    STATE.maps.session_application = "lineup"
    STATE.maps.session["play"] = screen()
    reply = mpromote.after_map("add", {"screen": "play"})
    assert reply["kept"] == "kept 1 (promote to review)"
    assert STATE.drafts.entries() == ["maps/lineup"]
    assert STATE.drafts.kept["maps", "lineup"].document["application"] == "lineup"


def test_a_map_add_after_a_start_is_named_by_the_guest() -> None:
    STATE.guest = "probe"
    STATE.maps.session["play"] = screen()
    assert mpromote.after_map("add", {"screen": "play"})["kept"] == "kept 1 (promote to review)"
    assert STATE.drafts.entries() == ["maps/probe"]


def test_a_map_save_and_a_map_load_keep_nothing() -> None:
    STATE.guest = "probe"
    STATE.maps.session["play"] = screen()
    saved = mpromote.after_map("save", {"application": "lineup", "screens": 1})
    assert saved == {"application": "lineup", "screens": 1}
    assert mpromote.after_map("load", {"application": "lineup"}) == {"application": "lineup"}
    assert STATE.drafts.entries() == [] and STATE.drafts.loaded == {}


def test_a_map_add_with_no_screen_proposes_nothing() -> None:
    STATE.guest = "probe"
    assert mpromote.after_map("add", {"screen": "play"}) == {"screen": "play"}
    assert STATE.drafts.entries() == []


def test_a_map_add_with_no_name_at_all_proposes_nothing() -> None:
    STATE.maps.session["play"] = screen()
    assert mpromote.after_map("add", {"screen": "play"}) == {"screen": "play"}
    assert STATE.drafts.entries() == []


def test_an_export_keeps_its_document_named_by_the_file_it_wrote(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(perform_document()))
    reply = mpromote.after_export(STATE.drafts, {"path": str(path)}, mpromote.PROMOTE_PATHS)
    assert reply["kept"].startswith("kept 1 (promote to review)")
    assert STATE.drafts.entries() == ["perform/session"]


def test_an_export_after_a_replay_updates_the_entry_it_replayed(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(perform_document()))
    STATE.drafts.loaded_entry("perform", "dos")
    mpromote.after_export(STATE.drafts, {"path": str(path)}, mpromote.PROMOTE_PATHS)
    assert STATE.drafts.entries() == ["perform/dos"]


def test_a_replay_the_reader_refuses_marks_no_entry(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({**perform_document(), "version": 2}))
    assert server.perform(path=str(path))["code"] == "bad_argument"
    assert STATE.drafts.loaded_name("perform") == ""


def test_close_reports_what_was_left_unkept() -> None:
    mpromote.note_start(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    reply = server.close()
    assert reply["draft"] == ["start/probe"]
    assert reply["closed"] is False


def test_a_recipe_s_conf_also_says_where_the_store_is() -> None:
    STATE.drafts.keep("perform", "x", {"start": {"cwd": "/game/guest", "conf": "/game/run.conf"},
                                       "steps": [{"op": "a", "recorded": {"v": 1}}]})
    assert mpromote.starting()[:2] == ["/game/guest", "/game/run.conf"]


def test_close_leaves_out_what_the_store_already_holds(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    recipe = {**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)}
    mpromote.note_start(recipe)
    mpromote.keep_start(recipe, defaults=server._START_DEFAULTS)
    server.promote(entries=["start/probe"], root=str(tmp_path))
    mpromote.keep_start(recipe, defaults=server._START_DEFAULTS)
    assert STATE.drafts.entries() == ["start/probe"]
    assert "draft" not in server.close()


def test_a_promotion_empties_the_draft_and_close_then_says_nothing(tmp_path: Path) -> None:
    mpromote.note_start({**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)})
    mpromote.keep_start({**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)},
                        defaults=server._START_DEFAULTS)
    server.promote(entries=["start/probe"], root=str(tmp_path))
    assert STATE.drafts.entries() == []
    assert "draft" not in server.close()


def test_promote_reviews_and_writes_in_a_store_of_its_own(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    params = {**START, "conf": str(tmp_path / "probe.conf"), "cwd": str(tmp_path)}
    mpromote.note_start(params)
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
    mpromote.note_start(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    reply = server.promote(dry_run=True)
    assert reply["code"] == "bad_argument" and "root" in reply["message"]


def test_a_root_creates_the_store_only_on_the_approved_call(tmp_path: Path) -> None:
    repo = tmp_path / "game"
    repo.mkdir()
    params = {**START, "conf": str(repo / "probe.conf"), "cwd": str(repo)}
    mpromote.note_start(params)
    mpromote.keep_start(params, defaults=server._START_DEFAULTS)
    assert server.promote(dry_run=True, root=str(repo))["candidates"][0]["change"] == "new"
    assert not (repo / ".scry").exists()
    server.promote(entries=["start/probe"], root=str(repo))
    assert (repo / ".scry" / "start" / "probe.json").is_file()


def test_the_store_is_looked_for_from_the_recipe_s_own_working_directory() -> None:
    STATE.drafts.keep("start", "probe", {"format": "scry-start/1", "conf": "probe.conf",
                                         "cwd": "/somewhere/guest",
                                         "session_seconds": 900})
    assert "/somewhere/guest" in mpromote.starting()


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
    mpromote.note_start(START)
    mpromote.keep_start(START, defaults=server._START_DEFAULTS)
    assert set(STATE.drafts.kept["start", "probe"].own) == set(mpromote.RUN_OWN)


def test_the_recipe_s_directory_is_searched_before_this_process_s() -> None:
    STATE.drafts.keep("start", "probe", {"format": "scry-start/1", "conf": "probe.conf",
                                         "cwd": "/somewhere/guest",
                                         "session_seconds": 900})
    starts = mpromote.starting()
    assert starts[0] == "/somewhere/guest" and starts[-1] == os.getcwd()


def test_a_map_learned_from_a_loaded_recipe_is_looked_for_in_that_recipe_s_store(
        tmp_path: Path) -> None:
    source = f"{tmp_path}/game/.scry/start/dos.json"
    STATE.drafts.loaded_entry("start", "dos", source=source)
    STATE.drafts.keep("maps", "dos", {"format": "scry-screen-map/1", "screens": [screen()]})
    assert mpromote.starting()[0] == source


def test_a_perform_document_s_start_block_says_where_the_store_is() -> None:
    STATE.drafts.keep("perform", "x", {"start": {"cwd": "/game/guest"},
                                       "steps": [{"op": "a", "recorded": {"v": 1}}]})
    assert mpromote.starting()[0] == "/game/guest"


def test_an_export_looks_for_the_store_where_the_document_it_kept_points(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    (repo / ".scry").mkdir(parents=True)
    bare = tmp_path / "elsewhere"
    bare.mkdir()
    monkeypatch.chdir(bare)
    document = perform_document()
    document["start"]["cwd"] = str(repo)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(document))
    kept = mpromote.after_export(STATE.drafts, {"path": str(path)}, mpromote.PROMOTE_PATHS)
    assert kept["kept"] == "kept 1 (promote to review)"


def working_directory_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The working directory cannot be resolved, as when it was deleted: Windows refuses to
    delete a process's own working directory, so the state is reached without deleting it."""
    def gone() -> str:
        raise FileNotFoundError("the working directory")
    monkeypatch.setattr(os, "getcwd", gone)


def test_a_working_directory_that_is_gone_does_not_cost_the_reply(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    working_directory_gone(monkeypatch)
    kept_probe(tmp_path)
    assert mpromote.kept_line(STATE.drafts) == "kept 1 (promote to review)"


def test_a_promote_with_a_root_does_not_need_the_working_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    working_directory_gone(monkeypatch)
    kept_probe(tmp_path)
    assert server.promote(dry_run=True, root=str(tmp_path))["store"] == str(tmp_path / ".scry")


SETUP = [".scry/", ".scry/about.json", ".scry/README.md"]


def kept_probe(repo: Path, **more: Any) -> None:
    params = {**START, "conf": str(repo / "probe.conf"), "cwd": str(repo), **more}
    mpromote.note_start(params)
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


def test_a_kept_line_says_how_to_set_up_a_store_only_when_none_is_above(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    kept_probe(tmp_path)
    assert "no .scry/ above" in mpromote.kept_line(STATE.drafts)
    (tmp_path / ".scry").mkdir()
    assert mpromote.kept_line(STATE.drafts) == "kept 1 (promote to review)"


def test_a_store_above_the_server_s_own_directory_does_not_silence_the_hint(
        tmp_path: Path) -> None:
    kept_probe(tmp_path / "game")
    assert "no .scry/ above" in mpromote.kept_line(STATE.drafts)


def test_an_export_names_the_missing_store_too(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(perform_document()))
    kept = mpromote.after_export(STATE.drafts, {"path": str(path)}, mpromote.PROMOTE_PATHS)
    assert "no .scry/ above" in kept["kept"]
