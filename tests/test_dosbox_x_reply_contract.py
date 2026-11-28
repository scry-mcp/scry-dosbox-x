"""The reply contract of a refusal, fixed for every tool: `status`, `code`, `message`."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fold_calls
import pytest
from scry_core import media_tools, png, reply_schema, series
from scry_core import reply_contract as contract
from scry_core.host_program import absolute as _abs
from scry_core.host_program import temporary as _tmp

from scry_dosbox_x import mcp as dosbox_mcp
from scry_dosbox_x import server
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

PACKAGE = Path(server.__file__).resolve().parent
SOURCES = sorted(PACKAGE.glob("*.py"))

_ARGS: dict[str, dict[str, Any]] = {
    "series_capture": {"at_frames": [0]},
    "screen_map_write": {"method": "save", "dest": _abs("nonexistent", "x-screen-map.json")},
    "image_compare": {"method": "image", "a": _abs("nonexistent", "a.png"),
                      "b": _abs("nonexistent", "b.png")},
    "audio_compare": {"method": "diff", "a": _abs("nonexistent", "a.wav"),
                      "b": _abs("nonexistent", "b.wav")},
    "start": {"conf": _abs("nonexistent.conf"), "cwd": "rel", "session_seconds": 10},
    "log": {"pattern": ".", "channel": "guest"},
    "declaration_clear": {"kind": "watch", "all": True},
    "log_wait": {"pattern": ".", "channel": "guest", "seconds": 0.01},
    "memdump": {"ref": "0100:0000", "length": 16, "dest": _abs("nonexistent-dir", "dump.bin")},
    "find": {"ref": "0100:0000", "length": 16, "data_hex": "00"},
    "scan": {"method": "start", "ref": "0100:0000", "length": 16},
    "read_memory": {"ref": "0100:0000"},
    "disassemble": {"ref": "0100:0000"},
    "call_stack": {},
    "debug": {"command": "R"},
    "set_register": {"name": "AX", "value": 1},
    "write": {"ref": "0100:0000", "data_hex": "00"},
    "run_to": {"ref": "0100:0000", "control": "0100:0020"},
    "run_for": {"frames": 1},
    "record": {"frames": 2},
    "audio_record": {"frames": 2},
    "trace": {"instructions": 1, "dest": _tmp("dosbox-x-contract-never-written.trace")},
    "screen_wait": {"text": "C:"},
    "breakpoint_interrupt": {"number": 0x21},
    "regpoint_add": {"condition": "AX==13"},
    "symbols_load": {"path": _abs("nonexistent.nm")},
    "symbols_find": {"name": "x"},
    "breakpoint_at": {"ref": "x"},
    "watch_add": {"ref": "x", "mode": "show", "length": 2},
    "send_keys": {"keys": ["enter"]},
    "send_mouse": {"button": "left"},
    "capture_frame": {"frame": 1, "dest": _abs("nonexistent-dir", "x.png")},
    "state_write": {"method": "load", "name": "x"},
    "perform": {"steps": [{"op": "status"}]},
    "perform_export": {"dest": _abs("nonexistent", "session.json")},
    "drive": {"act": [{"op": "status"}], "pattern": "."},
    "comment_write": {"method": "add", "ref": "x", "text": "t"},
    "port": {"method": "read", "port": 0x3DA},
    "pic": {"method": "read"},
    "a20": {"method": "read"},
    "guest_file": {"path": _abs("nonexistent", "OUT.TXT")},
}


def _tools() -> list[str]:
    names = dosbox_mcp.registered_tools()
    assert len(names) > 20, "the walk found almost no tools, so it examined nothing"
    return names


@pytest.mark.parametrize("name", _tools())
def test_every_tool_answers_the_contract_with_no_machine(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First gate: with no machine each tool refuses `no_session` or its own argument."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    # set here rather than inherited from the previous case
    monkeypatch.setattr(dstate.STATE, "session", None)
    reply = fold_calls.of(server, name)(**_ARGS.get(name, {}))
    if name in ("status", "close"):
        assert reply["status"] == "ok" and "code" not in reply and "message" not in reply, reply
        return
    # media tools refuse their missing file; a map save refuses the empty map
    expected = {"promote": "bad_argument", "start": "bad_argument", "build_check": "host_failed",
                "perform_export": "bad_argument", "screen_map_write": "needs_call",
                # reads a host file, no machine: one `start` did not fingerprint is refused
                "guest_file": "bad_argument",
                # asks nothing of a machine: with nothing to look up, its own judge refuses
                "knowledge_find": "bad_argument",
                **dict.fromkeys(media_tools.IMAGE_TOOLS + media_tools.AUDIO_TOOLS,
                                "bad_argument")}.get(name, "no_session")
    contract.check_refusal(name, reply, expected)


def _frame(lit: set[tuple[int, int]]) -> png.Raster:
    """A black 3x2 picture with the pixels in `lit` white."""
    width, height = 3, 2
    px = bytearray(bytes((0, 0, 0)) * (width * height))
    for x, y in lit:
        at = (y * width + x) * 3
        px[at:at + 3] = bytes((255, 255, 255))
    return png.Raster(width, height, bytes(px))


def _manifest(folder: Path, frames: dict[int, png.Raster]) -> str:
    """The `scry-series/1` manifest of `frames` in `folder`, as `image_compare` takes it."""
    folder.mkdir()
    for n, picture in frames.items():
        (folder / series.frame_name(n)).write_bytes(png.encode(picture))
    return str(series.write_manifest(folder, "test", "frame_number", None,
                                     sorted(frames))["manifest"])


def test_a_series_that_cannot_differ_answers_the_reply_model(tmp_path: Path) -> None:
    """The `control_silent` refusal names the series that never changed, as its model says."""
    dstate.STATE.session = None
    a = _manifest(tmp_path / "a", {1: _frame(set()), 2: _frame(set())})
    b = _manifest(tmp_path / "b", {1: _frame(set()), 2: _frame({(0, 0)})})
    reply = fold_calls.of(server, "image_compare")(method="series", a=a, b=b)
    contract.check_refusal("image_compare", reply, "control_silent")
    assert reply["series"] == "a", reply
    reply_schema.check("image_compare", reply)


class _Running:
    """A machine that runs and refuses every question the way the real one does."""

    altered = False
    reap_failed = ""
    drain_failure = ""
    ended_how = "none"
    launch = SimpleNamespace(cwd=Path(_abs()), logfile=None, watched=False,
                             conf=Path(_abs("x.conf")), core="auto")

    def alive(self) -> bool:
        return True

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return False

    def state(self, *, unless_silent: bool = False) -> dict[str, object]:
        return {"alive": True, "altered": False, "running": True}

    def __getattr__(self, name: str) -> Any:
        def refuse(*a: Any, **k: Any) -> Any:
            raise ds.NotStopped(f"the guest is running, so `{name}` has no state to answer from")
        return refuse


# `breakpoint_interrupt` and `symbols_load` consult their own store or file first
_READERS = ["registers", "read_memory", "memdump", "find", "scan", "debug", "step", "run_to",
            "run_for", "trace", "write", "set_register"]


@pytest.mark.parametrize("name", _READERS)
def test_every_reader_refuses_a_running_machine_with_the_contract(name: str) -> None:
    """Second gate: `not_stopped`, with its two context fields."""
    dstate.STATE.session = _Running()  # type: ignore[assignment]
    reply = fold_calls.of(server, name)(**_ARGS.get(name, {}))
    contract.check_refusal(name, reply, "not_stopped")
    assert "last_stop" in reply and "answers_while_running" in reply, reply


def test_the_exception_family_carries_its_code_in_the_constructor() -> None:
    """A raised `NotStopped` cannot carry another code."""
    assert ds.NotStopped("x").code == "not_stopped"
    assert ds.E9Stopped("x", waited_s=1.0, arrived=0).code == "wait_stopped"
    assert isinstance(ds.NotStopped("x"), contract.Invalid)
    with pytest.raises(TypeError, match="not a code"):
        contract.Invalid("nonsense", "x")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reserved"):
        contract.Invalid("bad_argument", "x", reason="x")


def test_the_envelope_refuses_a_malformed_refusal() -> None:
    with pytest.raises(TypeError, match="code"):
        dstate.reply(status="INVALID", message="x")
    with pytest.raises(TypeError, match="reason"):
        dstate.reply(status="INVALID", code="bad_argument", message="x", reason="x")
    with pytest.raises(TypeError, match="ok"):
        dstate.reply(code="bad_argument")
    bad = dstate.reply(**contract.refusal("control_silent", "cold", control="0000:0020"))
    assert list(bad)[:3] == ["status", "code", "message"] and bad["control"] == "0000:0020"


def test_every_code_written_in_the_sources_is_in_the_table() -> None:
    """A code typed wrong in a branch no test reaches is caught by reading the sources."""
    seen = contract.codes_written_in(SOURCES)
    assert len(seen) > 100, "the scan found almost no refusals, so it examined nothing"
    wrong = [(f, n, c) for f, n, c in seen if c not in contract.CODES]
    assert not wrong, wrong
