"""`perform_export` on the session doubles: each tool's declared export, the machine, the reply."""

from __future__ import annotations

import inspect
import json
import pathlib
import sys
from collections.abc import Iterator

import pytest
from scry_core import recording

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dosbox_x_server_support import _names, clean_session, install  # noqa: E402,F401

from scry_dosbox_x import (
    inputs,  # noqa: E402
    server,  # noqa: E402
)
from scry_dosbox_x import mcp as dosbox_mcp  # noqa: E402
from scry_dosbox_x import state as dstate  # noqa: E402


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[recording.Recorder]:
    """The recorder as a successful `start` leaves it."""
    monkeypatch.setattr(dosbox_mcp.RECORDER, "recording",
                        recording.Recording({"conf": "/x.conf"}))
    yield dosbox_mcp.RECORDER


def test_with_nothing_recorded_the_export_is_no_recording(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(dosbox_mcp.RECORDER, "recording", None)
    out = server.perform_export(dest=str(tmp_path / "s.json"))
    assert out["status"] == "INVALID" and out["code"] == "no_recording", out


def test_a_session_on_the_double_is_exported_as_steps_checks_and_named_drops(
        tmp_path: pathlib.Path, recorder: recording.Recorder) -> None:
    install()
    server.write(ref="F000:0000", data_hex="aa")
    regs = server.registers()
    server.status()
    server.comment_write("add", ref="F000:0000", text="the entry")
    out = server.perform_export(dest=str(tmp_path / "s.json"))
    assert out["status"] == "ok" and out["cut"]["available"] is False, out
    doc = json.loads((tmp_path / "s.json").read_text())
    assert doc["server"] == "dosbox-x" and doc["start"] == {"conf": "/x.conf"}
    assert [step["op"] for step in doc["steps"]] == ["write", "registers"]
    assert doc["steps"][1]["recorded"] == {"regs": regs["regs"]}
    assert out["checks"] == 1 and [d["op"] for d in out["dropped"]] == ["status",
                                                                        "comment_write"]
    assert out["summary"].startswith("perform_export: 2 steps, 1 check, 2 dropped to ")


def test_input_sent_to_a_parked_machine_is_an_export_step(
        tmp_path: pathlib.Path, recorder: recording.Recorder,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A parked machine takes input by running retrace by retrace; the export keeps the call as
    a step the replay sends the same way, and drops nothing."""
    fake = _names(tmp_path)
    assert fake.parked
    monkeypatch.setattr(inputs, "send_keys", lambda *a, **k: dstate.reply(
        route="guest", posted=1, bytes=2, frames=2, verify={"why": "none given"}))
    monkeypatch.setattr(inputs, "send_mouse", lambda *a, **k: dstate.reply(
        route="guest", arrived=True, pointer={"x": 10, "y": 20}, verify={"why": "none given"}))
    assert server.send_keys(keys=["a"])["status"] == "ok"
    assert server.send_mouse(x=10, y=20, action="click", button="left")["status"] == "ok"
    out = server.perform_export(dest=str(tmp_path / "s.json"))
    doc = json.loads((tmp_path / "s.json").read_text())
    assert [step["op"] for step in doc["steps"]] == ["send_keys", "send_mouse"], doc["steps"]
    assert doc["steps"][0] == {"op": "send_keys", "keys": ["a"]}, doc["steps"][0]
    assert (doc["steps"][1]["x"], doc["steps"][1]["y"]) == (10, 20), doc["steps"][1]
    assert out["dropped"] == [], out


def test_the_machine_around_a_call_is_the_sessions_stop_count_and_never_a_frame() -> None:
    """The count is the session's, never the last stop's record."""
    ses = install()
    ses.stop_count = 4
    got = dosbox_mcp._machine()
    assert got == recording.Machine(running=False, seq=4)
    ses.alive = lambda: False  # type: ignore[method-assign]
    assert dosbox_mcp._machine().known is False, "a session that died is unreadable, not still"


def test_a_stop_the_session_counted_before_its_record_moves_no_later_call(
        tmp_path: pathlib.Path, recorder: recording.Recorder) -> None:
    ses = install()
    ses.stop_count = 1
    sent = ses.command

    def counted(text: str, seconds: float | None = None) -> str:
        # Inside a call, as a parked `state_write(method="load")` counts its stop unsurveyed.
        ses.stop_count = 2
        return sent(text, seconds)
    ses.command = counted  # type: ignore[method-assign]
    server.write(ref="F000:0000", data_hex="aa")
    ses.command = sent  # type: ignore[method-assign]
    server.status()
    server.comment_write("add", ref="F000:0000", text="after")
    out = server.perform_export(dest=str(tmp_path / "s.json"))
    assert [d["op"] for d in out["dropped"]] == ["status", "comment_write"], out


def test_the_export_and_the_lifecycle_are_never_recorded_and_never_a_step() -> None:
    assert {"close", "build_check", recording.EXPORT_TOOL} <= dosbox_mcp.RECORDER.outside
    assert recording.EXPORT_TOOL in dosbox_mcp.registered_tools()
    assert dosbox_mcp.RECORDER.plan in inspect.signature(server.start).parameters
    assert "perform_export" not in server._step_ops()
    assert dosbox_mcp.RECORDER.plan == "plan"


#: Stated twice so a moved declaration is seen: fields checked, a wall-clock run, a drop, or a step.
DECLARED = {
    "read_memory": ("hex",), "registers": ("regs",), "screen_signature": ("signature",),
    "image_compare": {"image": "drop", "series": "drop", "region": "drop",
                      "golden": ("matched", "differing_total", "missing_total", "extra_total",
                                 "differing", "missing", "extra")},
    "screen_map_write": {"add": "step", "load": "step", "pointer": "step", "save": "drop"},
    "resume": "wall", "wait": "wall", "stop": "wall",
    "screen_wait": recording.Counted("run_for", "frames", "polls"),
    **dict.fromkeys(("memdump", "scan", "snapshot", "capture_frame", "series_capture",
                     "comment_write", "machine_map", "interrupt_vectors", "palette",
                     "screen_view", "audio_compare"), "drop"),
    "screen_map_find": ("matched", "screen"),
    # A promotion is an approval, and the replay of one would write a store.
    "promote": "drop",
    "guest_file": ("state",),
    **dict.fromkeys(("declaration_list", "build_check", "call_stack", "captures",
                     "comment_list", "disassemble", "find", "log", "log_wait", "state_list",
                     "status", "symbols_find"), "drop"),
}


def test_each_tool_is_exported_as_it_is_declared_and_the_rest_as_steps_or_dropped_reads() -> None:
    declared = dosbox_mcp.RECORDER.declared
    for tool, kind in declared.items():
        want = DECLARED.get(tool, "step")
        got = ({m: d.export_as for m, d in kind.items()} if isinstance(kind, dict)
               else kind.export_as)
        assert got == want, (tool, got, want)
    assert set(DECLARED) <= set(declared), sorted(set(DECLARED) - set(declared))


@pytest.mark.parametrize("conf", ["relative.conf", "absolute"])
def test_a_start_refused_over_the_live_session_keeps_its_recording(
        tmp_path: pathlib.Path, recorder: recording.Recorder, conf: str) -> None:
    install()
    server.write(ref="F000:0000", data_hex="aa")
    given = tmp_path / "x.conf"
    given.write_text("")
    refused = server.start(conf=conf if conf != "absolute" else str(given), cwd=str(tmp_path),
                           session_seconds=30)
    assert refused["status"] == "INVALID" and refused["session"]["alive"] is True, refused
    rec = recorder.recording
    assert rec is not None and rec.start == {"conf": "/x.conf"}
    assert [c.op for c in rec.calls] == ["write"]


def test_a_start_with_a_plan_is_exported_and_its_document_replays_on_the_same_double(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start(plan=)` steps are recorded; the document replays through `perform`."""
    from dosbox_x_server_support import _start_on_a_booted_fake

    got = _start_on_a_booted_fake(tmp_path, monkeypatch, settle_seconds=0,
                                  plan=[{"op": "write", "ref": "F000:0000", "data_hex": "aa"},
                                        {"op": "registers"}])
    assert got["status"] == "ok", got
    server.read_memory(ref="F000:0000", length=1)
    out = server.perform_export(dest=str(tmp_path / "s.json"))
    assert out["status"] == "ok" and out["cut"]["available"] is False, out
    doc = json.loads((tmp_path / "s.json").read_text())
    assert "plan" not in doc["start"] and doc["entry"] == "scry_dosbox_x.server"
    assert "settle_seconds" not in doc["start"], doc["start"]
    assert [step["op"] for step in doc["steps"]] == ["write", "registers", "read_memory"]
    played = server.perform(steps=doc["steps"])
    assert played["status"] == "ok", played
    assert played["held"] == sum(bool(s.get(recording.RECORDED)) for s in doc["steps"]) == 2


def test_the_declarations_the_recorder_reads_are_the_refs_the_list_tools_answer() -> None:
    """Each list tool the recorder names answers with the refs `_declared` read at the start."""
    install()
    assert server.breakpoint_at(ref="F000:0010")["status"] == "ok"
    assert server.breakpoint_interrupt(number=0x21)["status"] == "ok"
    assert server.watch_add(ref="F000:0020", mode="show", length=2)["status"] == "ok"
    declared = dosbox_mcp.RECORDER._stored()
    assert set(declared) == set(dosbox_mcp.RECORDER.lists)
    assert set(dosbox_mcp.RECORDER.lists.values()) <= set(dosbox_mcp.registered_tools())
    for key, tool in dosbox_mcp.RECORDER.lists.items():
        listed = getattr(server, tool)()[key]
        assert sorted(r["ref"] for r in listed) == sorted(declared[key]), key
    assert sum(len(refs) for refs in declared.values()) == 3
