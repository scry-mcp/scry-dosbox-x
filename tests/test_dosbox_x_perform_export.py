"""`perform_export`: the session since its `start`, written as `perform`'s own document, on the
doubles a session runs on here. The rules of the export are scry-core's (`scry_core.recording`);
what is this server's is what each tool is declared to become, the machine it reads around a
call, and the tool's own reply."""

from __future__ import annotations

import inspect
import json
import pathlib
import sys
from collections.abc import Iterator

import pytest
from scry_core import recording

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from test_dosbox_x_server import clean_session, install  # noqa: E402,F401

import dosbox_mcp  # noqa: E402
import dosbox_x_server as server  # noqa: E402


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[recording.Recorder]:
    """The server's recorder as a `start` that succeeded leaves it: a recording begun."""
    monkeypatch.setattr(dosbox_mcp.RECORDER, "recording",
                        recording.Recording({"conf": "/x.conf"}))
    yield dosbox_mcp.RECORDER


def test_with_nothing_recorded_the_export_is_no_recording(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(dosbox_mcp.RECORDER, "recording", None)
    out = server.perform_export(path=str(tmp_path / "s.json"))
    assert out["status"] == "INVALID" and out["code"] == "no_recording", out


def test_a_session_on_the_double_is_exported_as_steps_checks_and_named_drops(
        tmp_path: pathlib.Path, recorder: recording.Recorder) -> None:
    install()
    server.write(ref="F000:0000", data_hex="aa")
    regs = server.registers()
    server.status()
    server.comment_add(ref="F000:0000", text="the entry")
    out = server.perform_export(path=str(tmp_path / "s.json"))
    assert out["status"] == "ok" and out["cut"] is None, out
    doc = json.loads((tmp_path / "s.json").read_text())
    assert doc["server"] == "dosbox-x" and doc["start"] == {"conf": "/x.conf"}
    assert [step["op"] for step in doc["steps"]] == ["write", "registers"]
    assert doc["steps"][1]["recorded"] == {"registers": regs["registers"]}
    assert out["checks"] == 1 and [d["op"] for d in out["dropped"]] == ["status", "comment_add"]
    assert out["summary"].startswith("perform_export: 2 steps, 1 checks, 2 dropped to ")


def test_the_machine_around_a_call_is_the_sessions_stop_count_and_never_a_frame() -> None:
    """The count is the session's, which every return to the prompt moves, never the record of
    the last stop, which a stop nobody surveyed yet (a parked `state_load`) leaves behind."""
    ses = install()
    ses.stop_count = 4  # type: ignore[attr-defined]
    got = dosbox_mcp._machine()
    assert got == recording.Machine(running=False, frame=None, seq=4)
    ses.alive = lambda: False  # type: ignore[method-assign]
    assert dosbox_mcp._machine().known is False, "a session that died is unreadable, not still"


def test_a_stop_the_session_counted_before_its_record_moves_no_later_call(
        tmp_path: pathlib.Path, recorder: recording.Recorder) -> None:
    ses = install()
    ses.stop_count = 1  # type: ignore[attr-defined]
    server.write(ref="F000:0000", data_hex="aa")
    ses.stop_count = 2  # type: ignore[attr-defined]  # a parked state_load: counted, not surveyed
    server.status()
    server.comment_add(ref="F000:0000", text="after")
    out = server.perform_export(path=str(tmp_path / "s.json"))
    assert [d["op"] for d in out["dropped"]] == ["status", "comment_add"], out


def test_the_export_and_the_lifecycle_are_never_recorded_and_never_a_step() -> None:
    assert {"close", "build_check", recording.EXPORT_TOOL} <= dosbox_mcp.RECORDER.outside
    assert recording.EXPORT_TOOL in dosbox_mcp.registered_tools()
    assert dosbox_mcp.RECORDER.plan in inspect.signature(server.start).parameters
    assert "perform_export" not in server._step_ops()
    assert dosbox_mcp.RECORDER.plan == "plan"


#: What each tool's calls become in an export, stated here a second time so a declaration that
#: moves is seen: a check of fields, a run the wall clock ends, a drop, or (absent) a step.
DECLARED = {
    "read_memory": ("hex",), "registers": ("registers",), "screen_signature": ("signature",),
    "golden_check": ("matched", "differing", "missing", "extra"),
    "resume": "wall", "stop": "wall", "screen_wait": "wall",
    **dict.fromkeys(("memdump", "scan_start", "scan_filter", "scan_clear", "snapshot",
                     "capture_frame", "series_capture", "comment_add", "comment_delete",
                     "comment_save", "comment_load", "machine_map", "interrupt_vectors",
                     "palette", "screen_view", "image_diff", "series_diff", "region_track"),
                    "drop"),
}


def test_each_tool_is_exported_as_it_is_declared_and_the_rest_as_steps_or_dropped_reads() -> None:
    declared = dosbox_mcp.RECORDER.declared
    for tool, kind in declared.items():
        want = DECLARED.get(tool, "drop" if kind.read_only else "step")
        assert kind.export_as == want, (tool, kind.export_as, want)
    assert set(DECLARED) <= set(declared), sorted(set(DECLARED) - set(declared))
