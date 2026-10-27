"""The running-guest table holds exactly the tools that answer without `not_stopped`."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

import fold_calls
import pytest
from dosbox_x_server_support import NM_TEXT, SessionGates, _names, clean_session  # noqa: F401

import dosbox_declarations as dec
import dosbox_folds as folds
import dosbox_inputs as inputs
import dosbox_launch as dlaunch
import dosbox_mcp
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

#: What a session does without the debugger's console; a running guest's console drops
#: anything typed at it, and it is not run at the next stop either.
NO_CONSOLE = {"alive", "state", "at_debugger", "log", "log_wait", "e9", "e9_mark",
              "e9_new_since", "e9_since_mark", "e9_wait", "send_commands",
              "break_in", "save_state", "load_state",
              "state_list", "snapshot", "captures", "frame", "run_state"}


class RunningGuest(SessionGates):
    """A session whose guest runs: console methods refuse `NotStopped`, the rest answer."""

    def __init__(self, tmp_path: Path) -> None:
        self.altered = False
        self.stop_count = 1
        self.reap_failed = ""
        self.drain_ended = ""
        self.ended_how = "none"
        self.launch = dlaunch.Launch(conf=tmp_path / "g.conf", cwd=tmp_path / "cwd", seconds=60,
                                watched=True)
        self.stopped = False
        self.asked: list[str] = []           # every console method called while it ran

    def alive(self) -> bool:
        return True

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return self.stopped

    def state(self) -> dict[str, object]:
        return {"pid": 1, "alive": True, "running": not self.stopped, "altered": self.altered}

    def log(self, pattern: str, limit: int, channel: str,
            since_mark: int = 0) -> tuple[list[str], int]:
        return [], 0

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 **_: object) -> dict[str, object]:
        return {"verdict": "TARGET", "line": "x", "already": True}

    stub_protocol = inputs.STUB_PROTOCOL

    def send_commands(self, commands: list[bytes]) -> list[str]:
        return ["STUB  . mouse x=0 y=0 buttons=0 max=639,199 mode=3 screen=720x400 "
                "vbe=3 attr=0 res=0x0" for c in commands if c == b"R"]

    def break_in(self, seconds: float = 5.0, progress: object = None) -> float:
        self.stopped = True
        return 0.0

    def save_state(self, name: str, seconds: float = 20.0,
                   progress: object = None) -> dict[str, object]:
        return {"name": name}

    load_state = save_state

    def state_list(self) -> dict[str, object]:
        return {"state_dir": "/x/save", "states": [],
                "working_slot": {"available": False, "why": "no working slot"}}

    def snapshot(self, dest: Path | None = None, seconds: float = 10.0,
                 progress: object = None) -> dict[str, object]:
        return {"path": str(dest)}

    def captures(self) -> list[dict[str, object]]:
        return [{"path": str(self.launch.cwd / "c.avi"), "bytes": 0, "frames": 0,
                 "complete": True}]

    def frame(self, at: int, dest: Path, source: Path | None = None) -> Path:
        dest.write_bytes(b"")
        return dest

    def e9_mark(self) -> int:
        return 0

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        return [], offset

    def where(self) -> dict[str, str]:
        if not self.stopped:
            self.asked.append("where")
            raise ds.NotStopped("the guest is running: `where` took nothing")
        return {"cs": "0814", "eip": "00000000", "mode": "Real"}

    def registers(self) -> dict[str, str]:
        if not self.stopped:
            self.asked.append("registers")
            raise ds.NotStopped("the guest is running: `registers` took nothing")
        return {"CS": "0814", "EIP": "00000000"}

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        return self.where(), self.registers()

    def breakpoints(self) -> list[dict[str, str]]:
        if not self.stopped:
            self.asked.append("breakpoints")
            raise ds.NotStopped("the guest is running: `breakpoints` took nothing")
        return []

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        return self.where(), self.registers(), []

    survey_text = ""

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        if not self.stopped:
            self.asked.append("read_bytes")
            raise ds.NotStopped("the guest is running: `read_bytes` took nothing")
        raise ds.Invalid("unexpected_answer", "this double paints no data view")

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name in NO_CONSOLE:
            raise AttributeError(name)

        def console(*_: object, **__: object) -> Any:
            if not self.stopped:
                self.asked.append(name)
                raise ds.NotStopped(f"the guest is running: `{name}` took nothing")
            raise AssertionError(f"the double was asked {name} at a stop")
        return console


def _running(tmp_path: Path) -> RunningGuest:
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    dstate.STATE.store = dec.DeclarationStore(str(conf), path=tmp_path / "decl.json")
    dstate.STATE.install_table([])
    fake = RunningGuest(tmp_path)
    dstate.STATE.session = fake  # type: ignore[assignment]
    return fake

NOT_STEPS = {"build_check", "start", "close", "perform", "drive", "perform_export"}


def _args(tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Valid arguments per step tool, so a refusal can only come from the machine's state."""
    source = tmp_path / "prog.sym"
    source.write_text(NM_TEXT, encoding="utf-8")
    return {
        "status": {}, "log": {"pattern": ".", "channel": "guest"},
        "log_wait": {"pattern": ".", "channel": "guest", "seconds": 0.1},
        "registers": {}, "read_memory": {"ref": "0000:0400"}, "disassemble": {"ref": "0000:0400"},
        "call_stack": {},
        "memdump": {"ref": "0000:0400", "length": 16, "dest": str(tmp_path / "d.bin")},
        "find": {"data_hex": "41", "ref": "0000:0400", "length": 16},
        "scan start": {"ref": "0000:0400", "length": 16}, "scan filter": {}, "scan clear": {},
        "debug": {"command": "R"}, "set_register": {"name": "ax", "value": 1},
        "write": {"ref": "0000:0400", "data_hex": "41"}, "resume": {}, "stop": {}, "step": {},
        "run_to": {"ref": "0000:0400", "control": "0000:0500"}, "run_for": {"frames": 1},
        "record": {"frames": 2}, "audio_record": {"frames": 2},
        "trace": {"instructions": 1, "dest": str(tmp_path / "t.log")}, "screen_wait": {"text": "A"},
        "state_write save": {"name": "boot"}, "state_write load": {"name": "boot"}, "snapshot": {},
        "state_list": {}, "breakpoint_interrupt": {"number": 0x21},
        "regpoint_add": {"condition": "AX==13"},
        "symbols_load": {"path": str(source)}, "symbols_find": {"name": "x"},
        "machine_map": {}, "interrupt_vectors": {}, "palette": {}, "screen_view": {},
        "screen_signature": {}, "breakpoint_at": {"ref": "0000:0400"},
        "declaration_list breakpoint": {},
        "declaration_clear breakpoint": {"all": True},
        "watch_add": {"ref": "0000:0400", "mode": "change", "length": 2},
        "declaration_list watch": {}, "declaration_clear watch": {"all": True},
        "send_keys": {"keys": ["a"]},
        "send_mouse": {"button": "left"}, "captures": {},
        "capture_frame": {"frame": 0, "dest": str(tmp_path / "f.png")},
        "comment_write add": {"ref": "0000:0400", "text": "x"}, "comment_list": {},
        "comment_write delete": {"ref": "0000:0400"},
        "comment_write save": {"dest": str(tmp_path / "c.tsv")},
        "comment_write load": {"path": str(tmp_path / "c.tsv")},
        "series_capture": {"at_frames": [0]},
        "image_compare image": {"a": "/nonexistent/a.png", "b": "/nonexistent/b.png"},
        "image_compare series": {"a": "/nonexistent/a.json", "b": "/nonexistent/b.json"},
        "image_compare region": {"manifest": "/nonexistent/m.json"},
        "image_compare golden": {"manifest": "/nonexistent/m.json",
                                 "checksums": "/nonexistent/g.sha256"},
        "audio_compare measure": {"path": "/nonexistent/s.wav"},
        "audio_compare diff": {"a": "/nonexistent/a.wav", "b": "/nonexistent/b.wav"},
        "map_write load": {"path": str(tmp_path / "none.scry-map.json")},
        "map_write save": {"dest": str(tmp_path / "x.scry-map.json")},
        "map_write add": {"screen": "s", "match": [[0, 0, 1, 1]]}, "map_find": {},
        "port read": {"port": 0x3DA}, "port write": {"port": 0x3C8, "value": 1},
        "pic read": {}, **{f"pic {a}": {"irq": 3} for a in ("mask", "unmask", "ack", "raise",
                                                            "lower")},
        "a20 read": {}, "a20 on": {}, "a20 off": {},
        "guest_file": {"path": str(tmp_path / "OUT.TXT")},
    }


with tempfile.TemporaryDirectory() as _scratch:
    PROBES = sorted(_args(Path(_scratch)))


def _answers(probe: str) -> bool:
    """Whether the table says this step answers on a running guest."""
    tool, _, value = probe.partition(" ")
    selector = {"kind" if tool.startswith("declaration_") else "method": value} if value else {}
    return sequence.answers_running(tool, selector)


def test_every_step_tool_has_arguments_here(tmp_path: Path) -> None:
    assert {p.partition(" ")[0] for p in _args(tmp_path)} == (
        set(dosbox_mcp.registered_tools()) - NOT_STEPS)


@pytest.mark.parametrize("probe", PROBES)
def test_the_table_holds_exactly_what_answers_on_a_running_guest(
        probe: str, tmp_path: Path) -> None:
    _running(tmp_path)
    got = fold_calls.of(server, probe)(**_args(tmp_path)[probe])
    refused = got.get("code") == "not_stopped"
    assert refused is not _answers(probe), (probe, got)


@pytest.mark.parametrize("probe", [p for p in PROBES if _answers(p)])
def test_no_tool_of_the_table_types_at_a_running_guests_console(
        probe: str, tmp_path: Path) -> None:
    """No table tool types at the console of a running guest."""
    fake = _running(tmp_path)
    fold_calls.of(server, probe)(**_args(tmp_path)[probe])
    assert fake.asked == [], (probe, fake.asked)


def test_answers_while_running_is_the_table_and_the_five_that_answer_outside_a_list() -> None:
    table = [*sorted(sequence.GATE.listed(folds.METHODS)),
             "registers(from_last_stop=True)", "close", "drive", "perform", "perform_export"]
    assert table == dosbox_mcp._ANSWERS_WHILE_RUNNING


def test_perform_takes_every_registered_tool_but_the_lifecycle() -> None:
    assert set(server._step_ops()) == set(dosbox_mcp.registered_tools()) - NOT_STEPS


def test_a_stop_step_ends_the_run(tmp_path: Path) -> None:
    """After a release a `stop` ends the run, and the next console step does not wait."""
    fake = _names(tmp_path, watched=True)
    server.status()
    stops: list[int] = []

    def _stop(**_: Any) -> dict[str, Any]:
        stops.append(1)
        fake.running = False
        return {"status": "ok", "summary": "stop"}

    def _resume(**_: Any) -> dict[str, Any]:
        fake.running = True
        return {"status": "ok", "summary": "resume", "halted": False}

    ops = {**server._step_ops(), "stop": _stop, "resume": _resume}
    got = sequence.run_steps(fake, [{"op": "resume"}, {"op": "stop"},  # type: ignore[arg-type]
                              {"op": "registers"}], 0.2, ops, lambda *_: None, False)
    assert got["status"] == "ok", got
    assert [r["op"] for r in got["ran"]] == ["resume", "stop", "registers"], got
    assert stops == [1]
    got = sequence.run_steps(fake, [{"op": "resume"}, {"op": "stop"}],  # type: ignore[arg-type]
                             0.2, ops, lambda *_: None, False)
    assert got["status"] == "ok" and "still_running" not in got and "stopped" in got, got


def test_a_declaration_after_a_release_answers_pending(tmp_path: Path) -> None:
    """A declaration after a release queues `pending` and the guest stays running."""
    fake = _names(tmp_path, watched=True)
    server.status()
    released = fake.resume

    def _resume() -> dict[str, object]:
        fake.running = True
        return released()

    fake.resume = _resume  # type: ignore[method-assign]
    got = server.perform(steps=[{"op": "resume"}, {"op": "breakpoint_at", "ref": "0000:0400"}],
                         settle_seconds=0)
    assert got["status"] == "ok", got
    reply = got["ran"][1]["reply"]
    assert reply["state"] == "pending" and reply["armed"] is False, reply
    assert fake.running


def test_the_last_stops_registers_answer_in_a_list_without_waiting_for_a_stop(
        tmp_path: Path) -> None:
    """`registers(from_last_stop=True)` goes to a running guest at once."""
    fake = _names(tmp_path, watched=True)
    server.status()
    server.registers()                       # a stop surveyed, so there is a last one
    released = fake.resume

    def _resume() -> dict[str, object]:
        fake.running = True
        return released()

    fake.resume = _resume  # type: ignore[method-assign]
    got = server.perform(steps=[{"op": "resume"},
                                {"op": "registers", "from_last_stop": True}], settle_seconds=0)
    assert got["status"] == "ok" and got["ran"][1]["reply"]["regs"], got
    assert fake.running


def test_a_live_emulator_refusing_during_the_wait_is_its_own_answer_never_gone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path, watched=True)

    def overflow(*_a: Any, **_k: Any) -> Any:
        raise ds.Invalid("unexpected_answer", "the terminal offered more than one read holds")
    monkeypatch.setattr(ds.Session, "await_stop", overflow)
    with pytest.raises(ds.Invalid, match="more than one read holds"):
        sequence._wait_for_stop(fake, 1.0)  # type: ignore[arg-type]
    fake.alive = lambda: False  # type: ignore[method-assign]
    assert sequence._wait_for_stop(fake, 1.0) == "gone"  # type: ignore[arg-type]


def test_the_wait_names_an_emulator_gone_at_its_bound_or_under_a_read_and_nothing_else(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """At the bound dead is `gone`, live is `running`; a failed read is `gone` only if dead."""
    fake = _names(tmp_path, watched=True)
    monkeypatch.setattr(ds.Session, "await_stop", lambda *_a, **_k: (True, 0.0))
    assert sequence._wait_for_stop(fake, 1.0) == "running"  # type: ignore[arg-type]
    fake.alive = lambda: False  # type: ignore[method-assign]
    assert sequence._wait_for_stop(fake, 1.0) == "gone"  # type: ignore[arg-type]

    def dead_pty(*_a: Any, **_k: Any) -> Any:
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(ds.Session, "await_stop", dead_pty)
    assert sequence._wait_for_stop(fake, 1.0) == "gone"  # type: ignore[arg-type]
    fake.alive = lambda: True  # type: ignore[method-assign]
    with pytest.raises(OSError):
        sequence._wait_for_stop(fake, 1.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("ref", ["g_rate", "[g_rate]", "[0000:0400]"])
def test_a_declaration_by_name_on_a_running_guest_types_nothing(
        tmp_path: Path, ref: str) -> None:
    """A symbol or pointer needs registers, so nothing is typed and the declaration queues."""
    fake = _running(tmp_path)
    dstate.STATE.install_table([dsym.Symbol("g_rate", 0x1000, kind="d")])
    got = (server.breakpoint_at(ref=ref) if not ref.startswith("[")
           else server.watch_add(ref=ref, mode="show", length=2))
    assert got["status"] == "ok" and got["state"] in ("pending", "unarmable"), got
    assert fake.asked == [], fake.asked


def test_a_stop_the_stop_step_surveyed_is_not_numbered_again(tmp_path: Path) -> None:
    """The tail reuses the `stop` tool's own stop, enriched, rather than surveying again."""
    fake = _names(tmp_path, watched=True)
    server.status()
    released = fake.resume

    def _resume() -> dict[str, object]:
        fake.running = True
        return released()

    fake.resume = _resume  # type: ignore[method-assign]
    got = server.perform(steps=[{"op": "resume"}, {"op": "stop"}])
    assert got["status"] == "ok", got
    stop = got["ran"][1]["reply"]
    for key in ("stop_seq", "pc", "cpu_mode", "regs", "watches", "e9"):
        assert got["stopped"][key] == stop[key], (key, got["stopped"], stop)
    picture = [k for k in ("instruction",) if k in stop]
    assert picture, f"the stop step's reply carries no instruction: {sorted(stop)}"
    assert all(got["stopped"][k] == stop[k] for k in picture), (got["stopped"], stop)


def test_a_queued_declaration_is_not_a_stopper_the_tail_waits_for(tmp_path: Path) -> None:
    """A `pending` declaration cannot produce a stop, so the list returns at once."""
    fake = _names(tmp_path, watched=True)
    server.status()
    released = fake.resume

    def _resume() -> dict[str, object]:
        fake.running = True
        return released()

    fake.resume = _resume  # type: ignore[method-assign]
    fake.where_raises = True
    began = time.monotonic()
    got = server.perform(steps=[{"op": "resume"}, {"op": "breakpoint_at", "ref": "0000:0400"}],
                         settle_seconds=3)
    assert time.monotonic() - began < 2.0, got
    assert got.get("still_running") is True and "nothing declared" in got["note"], got


def test_a_stop_a_running_guest_step_met_ends_the_run_whatever_the_step(
        tmp_path: Path) -> None:
    """A stop met during any step ends the list there."""
    fake = _names(tmp_path, watched=True)
    server.status()

    def _resume(**_: Any) -> dict[str, Any]:
        fake.running = True
        return {"status": "ok", "summary": "resume", "halted": False}

    def _keys(**_: Any) -> dict[str, Any]:
        fake.running = False
        return {"status": "ok", "summary": "keys"}

    ops = {**server._step_ops(), "resume": _resume, "send_keys": _keys}
    got = sequence.run_steps(fake, [{"op": "resume"},  # type: ignore[arg-type]
                                    {"op": "send_keys", "keys": ["a"]}],
                             0.2, ops, lambda *_: None, False)
    assert got["status"] == "ok" and "still_running" not in got, got
    assert "regs" in got["stopped"], got


@pytest.mark.parametrize("cleared", ["breakpoint", "watch"])
def test_clearing_one_family_keeps_the_queued_arm_of_the_other_at_the_same_ref(
        tmp_path: Path, cleared: str) -> None:
    """Clearing one family at a shared ref leaves the other's queued arm."""
    _running(tmp_path)
    w = server.watch_add(ref="0814:0100", mode="change", length=2)
    b = server.breakpoint_at(ref="0814:0100")
    assert w["state"] == "pending" and b["state"] == "pending", (w, b)
    other = "watch" if cleared == "breakpoint" else "breakpoint"
    c = server.declaration_clear(cleared, ref="0814:0100")
    assert c["status"] == "ok" and c["declarations_cleared"] == 1, c
    assert dstate.STATE.pending["arm"] == ["0814:0100"], dstate.STATE.pending
    server.declaration_clear(other, all=True)
    assert dstate.STATE.pending["arm"] == [], dstate.STATE.pending


def test_a_list_is_judged_once_a_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-gate judges the list once; the run does not judge it again."""
    _names(tmp_path)
    calls: list[int] = []
    real = sequence.preflight

    def counted(*a: Any) -> Any:
        calls.append(1)
        return real(*a)
    monkeypatch.setattr(sequence, "preflight", counted)
    assert server.perform(steps=[{"op": "status"}])["status"] == "ok"
    assert len(calls) == 1
    calls.clear()
    assert server.drive(act=[{"op": "status"}])["status"] == "ok"
    assert len(calls) == 1
