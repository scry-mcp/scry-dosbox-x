"""The reply contract of a refusal, fixed for every tool: `status`, `code`, `message`.

A contract test and not a grep, because a grep reads the source text rather than the reply
a caller actually receives. This one walks every tool this server registers through the two
gates every tool crosses (no machine, a running machine) and fixes the envelope those gates
produce; the class that holds the contract is `scry_core.reply_contract.Invalid`, and the exception
family here (`NotStopped`, `E9Stopped`) carries
its code in the constructor so a site cannot raise one under the wrong word.

Every case here was written to go RED against the server before the contract existed.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fold_calls
import pytest
from scry_core import media_tools
from scry_core import reply_contract as contract

import dosbox_mcp
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

PACKAGE = Path(__file__).resolve().parent.parent
# `mapsweep.py` is a command-line tool with a refusal type of its own, outside the reply.
SOURCES = sorted(p for p in PACKAGE.glob("*.py") if p.name != "mapsweep.py")

# The arguments a tool needs to be CALLED at all; the gate refuses before any is judged.
_ARGS: dict[str, dict[str, Any]] = {
    "series_capture": {"at_frames": [0]},
    "map_write": {"method": "save", "dest": "/nonexistent/x.scry-map.json"},
    "image_compare": {"method": "image", "a": "/nonexistent/a.png", "b": "/nonexistent/b.png"},
    "start": {"conf": "/nonexistent.conf", "cwd": "rel", "session_seconds": 10},
    "log": {"pattern": ".", "channel": "guest"},
    "declaration_clear": {"kind": "watch", "all": True},
    "log_wait": {"pattern": ".", "channel": "guest", "seconds": 0.01},
    "memdump": {"ref": "0100:0000", "length": 16, "dest": "/nonexistent-dir/dump.bin"},
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
    "trace": {"instructions": 1, "dest": "/tmp/dosbox-x-contract-never-written.trace"},
    "screen_wait": {"text": "C:"},
    "breakpoint_interrupt": {"number": 0x21},
    "symbols_load": {"path": "/nonexistent.nm"},
    "symbols_find": {"name": "x"},
    "breakpoint_at": {"ref": "x"},
    "watch_add": {"ref": "x", "mode": "show", "length": 2},
    "send_keys": {"keys": ["enter"]},
    "send_mouse": {"button": "left"},
    "capture_frame": {"frame": 1, "dest": "/nonexistent-dir/x.png"},
    "state_write": {"method": "load", "name": "x"},
    "perform": {"steps": [{"op": "status"}]},
    "perform_export": {"dest": "/nonexistent/session.json"},
    "drive": {"act": [{"op": "status"}], "pattern": "."},
    "comment_write": {"method": "add", "ref": "x", "text": "t"},
}


def _tools() -> list[str]:
    names = dosbox_mcp.registered_tools()
    assert len(names) > 20, "the walk found almost no tools, so it examined nothing"
    return names


@pytest.mark.parametrize("name", _tools())
def test_every_tool_answers_the_contract_with_no_machine(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE FIRST GATE. With no machine, every tool that needs one refuses `no_session`;
    `start` refuses its argument before spawning anything; `build_check` on a host with no
    emulator says the host failed it; `status` and `close` answer `ok` about the absence."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    # NO MACHINE IS THIS CASE'S PREMISE, set here rather than inherited from the case before it.
    monkeypatch.setattr(dstate.STATE, "session", None)
    reply = fold_calls.of(server, name)(**_ARGS.get(name, {}))
    if name in ("status", "close"):
        assert reply["status"] == "ok" and "code" not in reply and "message" not in reply, reply
        return
    # A media file tool needs no machine: it refuses the missing file it was handed. A map's
    # file methods need none either: a save refuses the empty map.
    expected = {"start": "bad_argument", "build_check": "host_failed",
                "perform_export": "bad_argument", "map_write": "needs_call",
                **dict.fromkeys(media_tools.IMAGE_TOOLS, "bad_argument")}.get(name, "no_session")
    contract.check_refusal(name, reply, expected)


class _Running:
    """A machine that RUNS and nothing else: every question of the session is refused the
    way the real one refuses it, so what is fixed here is the envelope and not the gate."""

    altered = False
    reap_failed = ""
    ended_how = "none"
    launch = SimpleNamespace(cwd=Path("/"), logfile=None, watched=False, conf=Path("/x.conf"))

    def alive(self) -> bool:
        return True

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return False

    def state(self) -> dict[str, object]:
        return {"alive": True, "altered": False, "running": True}

    def __getattr__(self, name: str) -> Any:
        def refuse(*a: Any, **k: Any) -> Any:
            raise ds.NotStopped(f"the guest is running, so `{name}` has no state to answer from")
        return refuse


# The readers whose FIRST gate is the machine. `breakpoint_interrupt` asks the declaration
# store first and `symbols_load` reads its file first, by their own contracts, so a running
# machine is not the refusal they answer with here.
_READERS = ["registers", "read_memory", "memdump", "find", "scan", "debug", "step", "run_to",
            "run_for", "trace", "write", "set_register"]


@pytest.mark.parametrize("name", _READERS)
def test_every_reader_refuses_a_running_machine_with_the_contract(name: str) -> None:
    """THE SECOND GATE: `not_stopped`, with the two context fields beside the envelope."""
    dstate.STATE.session = _Running()  # type: ignore[assignment]
    reply = fold_calls.of(server, name)(**_ARGS.get(name, {}))
    contract.check_refusal(name, reply, "not_stopped")
    assert "last_stop" in reply and "answers_while_running" in reply, reply


def test_the_exception_family_carries_its_code_in_the_constructor() -> None:
    """A site that raises `NotStopped` cannot put it under another word."""
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
    """The class checks at RUNTIME; the contract's own scan reads the sources so a code typed
    wrong in a branch no test reaches is caught here, and a code cannot be computed from a
    string at runtime."""
    seen = contract.codes_written_in(SOURCES)
    assert len(seen) > 100, "the scan found almost no refusals, so it examined nothing"
    wrong = [(f, n, c) for f, n, c in seen if c not in contract.CODES]
    assert not wrong, wrong
