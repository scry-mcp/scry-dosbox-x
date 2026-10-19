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
    assert out["status"] == "ok" and out["cut"]["available"] is False, out
    doc = json.loads((tmp_path / "s.json").read_text())
    assert doc["server"] == "dosbox-x" and doc["start"] == {"conf": "/x.conf"}
    assert [step["op"] for step in doc["steps"]] == ["write", "registers"]
    assert doc["steps"][1]["recorded"] == {"regs": regs["regs"]}
    assert out["checks"] == 1 and [d["op"] for d in out["dropped"]] == ["status", "comment_add"]
    assert out["summary"].startswith("perform_export: 2 steps, 1 check, 2 dropped to ")


def test_the_machine_around_a_call_is_the_sessions_stop_count_and_never_a_frame() -> None:
    """The count is the session's, which every return to the prompt moves, never the record of
    the last stop, which a stop nobody surveyed yet (a parked `state_load`) leaves behind."""
    ses = install()
    ses.stop_count = 4  # type: ignore[attr-defined]
    got = dosbox_mcp._machine()
    assert got == recording.Machine(running=False, seq=4)
    ses.alive = lambda: False  # type: ignore[method-assign]
    assert dosbox_mcp._machine().known is False, "a session that died is unreadable, not still"


def test_a_stop_the_session_counted_before_its_record_moves_no_later_call(
        tmp_path: pathlib.Path, recorder: recording.Recorder) -> None:
    ses = install()
    ses.stop_count = 1  # type: ignore[attr-defined]
    sent = ses.command

    def counted(text: str, **kw: object) -> str:
        # INSIDE a call, as a parked `state_load` counts its stop: counted, not surveyed. A count
        # that moved between two calls would be motion outside the recording, a cut.
        ses.stop_count = 2  # type: ignore[attr-defined]
        return sent(text, **kw)
    ses.command = counted  # type: ignore[method-assign]
    server.write(ref="F000:0000", data_hex="aa")
    ses.command = sent  # type: ignore[method-assign]
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
    "read_memory": ("hex",), "registers": ("regs",), "screen_signature": ("signature",),
    "golden_check": ("matched", "differing_total", "missing_total", "extra_total", "differing",
                     "missing", "extra"),
    "resume": "wall", "stop": "wall", "screen_wait": "wall",
    **dict.fromkeys(("memdump", "scan_start", "scan_filter", "scan_clear", "snapshot",
                     "capture_frame", "series_capture", "comment_add", "comment_delete",
                     "comment_save", "comment_load", "machine_map", "interrupt_vectors",
                     "palette", "screen_view", "image_diff", "series_diff", "region_track",
                     "map_save"),
                    "drop"),
    # A replay knows the map an identification was made against, and holds the find to it.
    "map_find": ("matched", "screen"),
    # The readers dropped by default, named so a reader that turns into a step is seen.
    **dict.fromkeys(("breakpoint_list", "build_check", "call_stack", "captures", "comment_list",
                     "disassemble", "find", "log", "log_wait", "state_list", "status",
                     "symbols_find", "watch_list"), "drop"),
}


def test_each_tool_is_exported_as_it_is_declared_and_the_rest_as_steps_or_dropped_reads() -> None:
    declared = dosbox_mcp.RECORDER.declared
    for tool, kind in declared.items():
        want = DECLARED.get(tool, "step")
        assert kind.export_as == want, (tool, kind.export_as, want)
    assert set(DECLARED) <= set(declared), sorted(set(DECLARED) - set(declared))


@pytest.mark.parametrize("conf", ["relative.conf", "absolute"])
def test_a_start_refused_over_the_live_session_keeps_its_recording(
        tmp_path: pathlib.Path, recorder: recording.Recorder, conf: str) -> None:
    """Refused while the session is live, whether by the session or by an argument judged
    before it: the start touched nothing, and the recording stays the live session's."""
    install()
    server.write(ref="F000:0000", data_hex="aa")
    given = tmp_path / "x.conf"
    given.write_text("")
    refused = server.start(conf=conf if conf != "absolute" else str(given), cwd=str(tmp_path),
                           seconds=30)
    assert refused["status"] == "INVALID" and refused["session"]["alive"] is True, refused
    rec = recorder.recording
    assert rec is not None and rec.start == {"conf": "/x.conf"}
    assert [c.op for c in rec.calls] == ["write"]


def test_a_start_with_a_plan_is_exported_and_its_document_replays_on_the_same_double(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PLAN THROUGH THE BOUNDARY, END TO END: `start(plan=)` runs its steps as a sequence's,
    the recording keeps them after the start (whose own arguments drop `plan`), and the document
    plays back through this server's `perform`, every `recorded` step held."""
    from test_dosbox_x_server import _start_on_a_booted_fake

    got = _start_on_a_booted_fake(tmp_path, monkeypatch, plan_wait=0,
                                  plan=[{"op": "write", "ref": "F000:0000", "data_hex": "aa"},
                                        {"op": "registers"}])
    assert got["status"] == "ok", got
    server.read_memory(ref="F000:0000", length=1)
    out = server.perform_export(path=str(tmp_path / "s.json"))
    assert out["status"] == "ok" and out["cut"]["available"] is False, out
    doc = json.loads((tmp_path / "s.json").read_text())
    assert "plan" not in doc["start"] and doc["entry"] == "dosbox_x_server.py"
    assert [step["op"] for step in doc["steps"]] == ["write", "registers", "read_memory"]
    played = server.perform(steps=doc["steps"])
    assert played["status"] == "ok", played
    assert played["held"] == sum(bool(s.get(recording.RECORDED)) for s in doc["steps"]) == 2


def test_the_declarations_the_recorder_reads_are_the_refs_the_list_tools_answer() -> None:
    """THE REPLAY'S PRECONDITION: the runner holds the replayed store, read through each list tool
    the recorder names, to what `_declared` read at the recorded start, so the two readings are one
    for every kind a `start` re-arms."""
    install()
    assert server.breakpoint_at(ref="F000:0010")["status"] == "ok"
    assert server.breakpoint_interrupt(number=0x21)["status"] == "ok"
    assert server.watch_add(ref="F000:0020", mode="show", length=2)["status"] == "ok"
    declared = dosbox_mcp._declared()
    assert set(declared) == set(dosbox_mcp.RECORDER.lists) <= set(dosbox_mcp.registered_tools())
    for tool, key in dosbox_mcp.RECORDER.lists.items():
        listed = getattr(server, tool)()[key]
        assert sorted(r["ref"] for r in listed) == sorted(declared[tool]), tool
    assert sum(len(refs) for refs in declared.values()) == 3
