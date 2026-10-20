"""What answers on a running guest is ONE table, proven tool by tool rather than listed: every
tool a sequence can take is called on a machine that is not at the debugger, and the table
holds exactly the ones that answer without `not_stopped`. The reply's `answers_while_running`
and `perform`'s step vocabulary are read off the same table and the same registry."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from test_dosbox_x_server import NM_TEXT, _names, clean_session  # noqa: F401

import dosbox_declarations as dec
import dosbox_inputs as inputs
import dosbox_launch as dlaunch
import dosbox_mcp
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

#: What a session does WITHOUT the debugger's console: the log file, the guest's input,
#: the debugger channel, the capture directory, the state directory. Everything else it
#: does is a console command, and on a running guest a console command lands at the next
#: stop, unread.
NO_CONSOLE = {"alive", "state", "at_debugger", "log", "log_wait", "e9", "e9_mark",
              "e9_lines", "e9_new_since", "e9_since_mark", "e9_wait", "send_commands",
              "break_in", "state_save", "state_load",
              "state_list", "snapshot", "captures", "frame"}


class RunningGuest:
    """A session whose guest RUNS: `at_debugger()` is False, every console method refuses
    `NotStopped` the way the real one comes back empty, and what needs no console answers.
    A method this double does not know fails the test by name rather than passing."""

    def __init__(self, tmp_path: Path) -> None:
        self.altered = False
        self.stop_count = 1
        self.reap_failed = ""
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

    def log(self, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
        return [], 0

    def log_wait(self, pattern: str, seconds: float, channel: str,
                 **_: object) -> dict[str, object]:
        return {"verdict": "TARGET", "line": "x", "already": True}

    stub_protocol = inputs.STUB_PROTOCOL

    def send_commands(self, commands: list[bytes]) -> list[str]:
        """The stub's answer: one report line per `R`, as the real link hands back."""
        return ["STUB  . mouse x=0 y=0 buttons=0 max=639,199 mode=3 screen=720x400"
                for c in commands if c == b"R"]

    def break_in(self, seconds: float = 5.0, progress: object = None) -> float:
        self.stopped = True
        return 0.0

    def state_save(self, name: str, seconds: float = 20.0,
                   progress: object = None) -> dict[str, object]:
        return {"name": name}

    state_load = state_save

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

    def e9_lines(self) -> list[str]:
        return []

    # AT A STOP (after `stop`'s break-in) the survey answers, like the real one.
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

    survey_text = ""          # its survey paints no screen, so a stop's code pane is absent

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

#: The tools that are not steps: the session's own life, the two sequence tools, the export.
NOT_STEPS = {"build_check", "start", "close", "perform", "drive", "perform_export"}


def _args(tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Arguments each step tool accepts, valid by its own rules, so what the call meets is the
    machine's state and nothing before it."""
    source = tmp_path / "prog.sym"
    source.write_text(NM_TEXT, encoding="utf-8")
    return {
        "status": {}, "log": {"pattern": ".", "channel": "guest"},
        "log_wait": {"pattern": ".", "channel": "guest", "seconds": 0.1},
        "registers": {}, "read_memory": {"ref": "0000:0400"}, "disassemble": {"ref": "0000:0400"},
        "call_stack": {},
        "memdump": {"ref": "0000:0400", "length": 16, "dest": str(tmp_path / "d.bin")},
        "find": {"data_hex": "41", "ref": "0000:0400", "length": 16},
        "scan_start": {"ref": "0000:0400", "length": 16}, "scan_filter": {}, "scan_clear": {},
        "debug": {"command": "R"}, "set_register": {"name": "ax", "value": 1},
        "write": {"ref": "0000:0400", "data_hex": "41"}, "resume": {}, "stop": {}, "step": {},
        "run_to": {"ref": "0000:0400", "control": "0000:0500"}, "run_for": {"frames": 1},
        "trace": {"instructions": 1, "dest": str(tmp_path / "t.log")}, "screen_wait": {"text": "A"},
        "state_save": {"name": "boot"}, "state_load": {"name": "boot"}, "snapshot": {},
        "state_list": {}, "breakpoint_interrupt": {"number": 0x21},
        "symbols_load": {"path": str(source)}, "symbols_find": {"name": "x"},
        "machine_map": {}, "interrupt_vectors": {}, "palette": {}, "screen_view": {},
        "screen_signature": {}, "breakpoint_at": {"ref": "0000:0400"}, "breakpoint_list": {},
        "breakpoint_clear": {"all": True},
        "watch_add": {"ref": "0000:0400", "mode": "change", "length": 2},
        "watch_list": {}, "watch_clear": {"all": True}, "send_keys": {"keys": ["a"]},
        "send_mouse": {"button": "left"}, "captures": {},
        "capture_frame": {"frame": 0, "dest": str(tmp_path / "f.png")},
        "comment_add": {"ref": "0000:0400", "text": "x"}, "comment_list": {},
        "comment_delete": {"ref": "0000:0400"}, "comment_save": {"dest": str(tmp_path / "c.tsv")},
        "comment_load": {"path": str(tmp_path / "c.tsv")},
        "series_capture": {"frames": [0]},
        "image_diff": {"a": "/nonexistent/a.png", "b": "/nonexistent/b.png"},
        "series_diff": {"a": "/nonexistent/a.json", "b": "/nonexistent/b.json"},
        "region_track": {"manifest": "/nonexistent/m.json"},
        "golden_check": {"manifest": "/nonexistent/m.json",
                         "checksums": "/nonexistent/g.sha256"},
        "map_load": {"path": str(tmp_path / "none.scry-map.json")},
        "map_save": {"dest": str(tmp_path / "x.scry-map.json")},
        "map_add": {"screen": "s", "match": [[0, 0, 1, 1]]}, "map_find": {},
    }


def test_every_step_tool_has_arguments_here(tmp_path: Path) -> None:
    assert set(_args(tmp_path)) == set(dosbox_mcp.registered_tools()) - NOT_STEPS


@pytest.mark.parametrize("tool", sorted(set(dosbox_mcp.registered_tools()) - NOT_STEPS))
def test_the_table_holds_exactly_what_answers_on_a_running_guest(
        tool: str, tmp_path: Path) -> None:
    _running(tmp_path)
    got = getattr(server, tool)(**_args(tmp_path)[tool])
    refused = got.get("code") == "not_stopped"
    assert refused is (tool not in sequence.RUNNING_OK_OPS), (tool, got)


@pytest.mark.parametrize("tool", sorted(sequence.RUNNING_OK_OPS))
def test_no_tool_of_the_table_types_at_a_running_guests_console(
        tool: str, tmp_path: Path) -> None:
    """The table's own claim: on a running guest a console command lands at the next stop,
    unread, after its survey has sat out the whole wait for a pane that does not come."""
    fake = _running(tmp_path)
    getattr(server, tool)(**_args(tmp_path)[tool])
    assert fake.asked == [], (tool, fake.asked)


def test_answers_while_running_is_the_table_and_the_five_that_answer_outside_a_list() -> None:
    table = [*sorted(sequence.RUNNING_OK_OPS), "registers(from_last_stop=True)", "close",
             "drive", "perform", "perform_export"]
    assert table == dosbox_mcp._ANSWERS_WHILE_RUNNING


def test_perform_takes_every_registered_tool_but_the_lifecycle() -> None:
    assert set(server._step_ops()) == set(dosbox_mcp.registered_tools()) - NOT_STEPS


def test_a_stop_step_ends_the_run(tmp_path: Path) -> None:
    """After a release a `stop` runs at once and brings the guest back, and the next console
    step goes out without waiting for a stop that already happened: the session says it
    stopped, never the op's name."""
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
    # A LIST ENDING IN THE `stop` ends stopped: no tail reports a guest still running.
    got = sequence.run_steps(fake, [{"op": "resume"}, {"op": "stop"}],  # type: ignore[arg-type]
                             0.2, ops, lambda *_: None, False)
    assert got["status"] == "ok" and "still_running" not in got and "stopped" in got, got


def test_a_declaration_after_a_release_answers_pending(tmp_path: Path) -> None:
    """A declaration step after a release does not wait for a stop: it queues `pending`, as
    the same call outside a sequence does, and the guest stays running."""
    fake = _names(tmp_path, watched=True)
    server.status()
    released = fake.resume

    def _resume() -> dict[str, object]:
        fake.running = True              # the F5 went out and the guest runs
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
    """`registers(from_last_stop=True)` is in the instructions' running table, and a list sends
    it to a running guest at once, as a direct call answers."""
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


@pytest.mark.parametrize("ref", ["g_rate", "[g_rate]", "[0000:0400]"])
def test_a_declaration_by_name_on_a_running_guest_types_nothing(
        tmp_path: Path, ref: str) -> None:
    """Placing a symbol or a pointer needs the registers; on a running guest the nudge that
    asks for them would land at the next stop, unread. So nothing is typed, and the
    declaration is queued as it would be after typing."""
    fake = _running(tmp_path)
    dstate.STATE.install_table([dsym.Symbol("g_rate", 0x1000, kind="d")])
    got = (server.breakpoint_at(ref=ref) if not ref.startswith("[")
           else server.watch_add(ref=ref, mode="show", length=2))
    # A symbol queues for the next stop; a pointer is read at each stop, so it waits as
    # `unarmable` with the reason. Either way the console was not asked.
    assert got["status"] == "ok" and got["state"] in ("pending", "unarmable"), got
    assert fake.asked == [], fake.asked


def test_a_stop_the_stop_step_surveyed_is_not_numbered_again(tmp_path: Path) -> None:
    """The `stop` tool hands back its own stop; the tail names that one, and a second survey
    would number the same stop twice. It is still the ENRICHED stop REFERENCE promises when the
    last step met one: that survey's registers, watches and E9 summary."""
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
    """A declaration answered `pending` is armed only at a stop, so it cannot produce one:
    with nothing else declared the list returns at once, still running, and says why."""
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
    """A breakpoint can fire while a key goes in: the session says the guest stopped, so the
    list ends at that stop although the step was no `stop` and nothing declared could have
    been asked to produce it."""
    fake = _names(tmp_path, watched=True)
    server.status()

    def _resume(**_: Any) -> dict[str, Any]:
        fake.running = True
        return {"status": "ok", "summary": "resume", "halted": False}

    def _keys(**_: Any) -> dict[str, Any]:
        fake.running = False             # the guest stopped while the key went in
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
    """The arm queue holds refs, and a breakpoint and a change watch may share one: clearing
    one family's declaration while the guest runs leaves the other's arm queued."""
    _running(tmp_path)
    w = server.watch_add(ref="0814:0100", mode="change", length=2)
    b = server.breakpoint_at(ref="0814:0100")
    assert w["state"] == "pending" and b["state"] == "pending", (w, b)
    clear = server.breakpoint_clear if cleared == "breakpoint" else server.watch_clear
    c = clear(ref="0814:0100")
    assert c["status"] == "ok" and c["declarations_cleared"] == 1, c
    assert dstate.STATE.pending["arm"] == ["0814:0100"], dstate.STATE.pending
    gone = server.watch_clear if cleared == "breakpoint" else server.breakpoint_clear
    gone(all=True)                   # the other family cleared too: nothing left to arm
    assert dstate.STATE.pending["arm"] == [], dstate.STATE.pending


def test_a_list_is_judged_once_a_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-gate judges the list whole before the machine; the run does not judge it again."""
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
