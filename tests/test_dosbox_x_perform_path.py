"""`perform(path=)`: the document a session replays, and the two arguments that cannot come
together."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dosbox_x_server_support import clean_session, install  # noqa: E402,F401

from scry_dosbox_x import server  # noqa: E402


def _doc(tmp_path: pathlib.Path, **fields: Any) -> pathlib.Path:
    path = tmp_path / "script.json"
    body: dict[str, Any] = {"version": 3, "server": "dosbox-x",
                            "steps": [{"op": "no_such_tool"}], **fields}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_a_documents_steps_are_judged_as_the_whole_list(tmp_path: pathlib.Path) -> None:
    install()
    out = server.perform(path=str(_doc(tmp_path)))
    assert out["status"] == "INVALID" and out["errors"][0]["op"] == "no_such_tool", out
    assert out["steps_completed"] == 0, out


def test_a_document_replays_on_the_open_session(tmp_path: pathlib.Path) -> None:
    install()
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"version": 3,
                                "steps": [{"op": "registers"}, {"op": "registers"}]}))
    out = server.perform(path=str(path))
    assert out["status"] == "ok" and out["steps_completed"] == 2, out


def test_a_step_and_a_path_are_refused_before_the_step_list_is_judged(
        tmp_path: pathlib.Path) -> None:
    install()
    out = server.perform(steps=[{"op": "no_such_tool"}], path=str(_doc(tmp_path)))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "steps and path" in out["message"], out


def test_a_step_and_a_path_are_refused_together(tmp_path: pathlib.Path) -> None:
    install()
    out = server.perform(steps=[{"op": "registers"}], path=str(_doc(tmp_path)))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "steps and path" in out["message"], out


def test_neither_a_step_nor_a_path_is_refused() -> None:
    install()
    out = server.perform()
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "give steps, or path" in out["message"], out


def test_a_document_version_this_server_does_not_read_is_refused_by_name(
        tmp_path: pathlib.Path) -> None:
    install()
    out = server.perform(path=str(_doc(tmp_path, version=2)))
    assert out["status"] == "INVALID" and out["code"] == "bad_argument", out
    assert "version 2" in out["message"], out
