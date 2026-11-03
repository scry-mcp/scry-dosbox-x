"""A CALL THE CLIENT CANCELLED: the tool ends at once as it declared (`on_cancel`), and the next
reply, the outermost one, whatever tool it is, says once what the cancelled call left, since the
cancelled one answers nothing. The cancellation itself is the poll every bounded wait makes
(`scry_core.cancel.check`), raised here at the poll a case chooses.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest
from scry_core import cancel
from scry_core import progress as mprogress

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dosbox_x_server_support import FakeSession, clean_session, install  # noqa: E402,F401

from scry_dosbox_x import binary as binaries  # noqa: E402
from scry_dosbox_x import (
    checks,  # noqa: E402
    retrace,  # noqa: E402
    server,  # noqa: E402
)
from scry_dosbox_x import mcp as dosbox_mcp  # noqa: E402
from scry_dosbox_x import state as st  # noqa: E402


class _Running(FakeSession):
    """A guest that runs until a `BREAK` brings it back to the debugger."""

    running = False                            # what the fake's session block reads

    def __init__(self) -> None:
        super().__init__()
        self.at = False
        self.breaks = 0
        self.stop_count: int | None = None     # no counter unless a case gives it one

    @property
    def parked(self) -> bool:
        return self.at_debugger()

    def at_debugger(self) -> bool:
        return self.at

    def break_in(self, seconds: float = 5.0) -> float:
        self.breaks += 1
        self.at = True
        return 0.1


def _cancel_at(monkeypatch: pytest.MonkeyPatch, poll: int) -> None:
    """The call is cancelled at its `poll`-th poll, counting the one on entry; the calls after
    it are other requests, which nobody cancelled."""
    polls = [0]

    def check() -> None:
        if cancel.shielding():
            return
        polls[0] += 1
        if polls[0] == poll:
            raise asyncio.CancelledError
    monkeypatch.setattr(cancel, "check", check)


@pytest.fixture
def waiting_tool(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Tools whose body waits on a `Ticker` for a minute, one per declared end."""
    monkeypatch.setattr(checks, "check", lambda name, **given: None)
    made: dict[str, Any] = {}
    for end in cancel.ON_CANCEL:
        def body(ctx: Any = None) -> dict[str, Any]:
            clock = mprogress.Ticker(60.0, mprogress.no_progress)
            while not clock.expired():
                pass
            return st.reply()
        body.__name__ = body.__qualname__ = f"wait_{end}"
        made[end] = dosbox_mcp.tool(f"wait {end}", summary=lambda a, r: "waited",
                                    on_cancel=end)(body)
    yield made
    for end in cancel.ON_CANCEL:
        server.mcp._tool_manager._tools.pop(f"wait_{end}", None)
        dosbox_mcp.BOUNDARY.summaries.pop(f"wait_{end}", None)
        dosbox_mcp.BOUNDARY.declared_ends.pop(f"wait_{end}", None)


def _running() -> _Running:
    ses = _Running()
    st.STATE.session = ses  # type: ignore[assignment]
    return ses


def test_a_cancelled_wait_that_ends_stopped_breaks_in_and_the_next_reply_says_so(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    ses = _running()
    _cancel_at(monkeypatch, 3)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert ses.breaks == 1 and ses.at is True
    out = server.status()
    assert out["cancelled"]["tool"] == "wait_stop" and out["cancelled"]["left"] == "stopped", out
    assert out["summary"].startswith("after a cancelled wait_stop (stopped): "), out["summary"]
    assert list(out)[-1] == "session" and list(out)[-2] == "cancelled", list(out)
    assert "cancelled" not in server.status(), "the record rode on a second reply"


@pytest.mark.parametrize("commands", [binaries.COMMANDS, ()], ids=["runstate", "no-runstate"])
@pytest.mark.parametrize(("at_debugger", "word"), [(True, "stopped"), (False, "running")])
def test_the_status_summary_word_is_the_state_the_session_block_carries(
        at_debugger: bool, word: str, commands: tuple[str, ...]) -> None:
    install()
    ses = _running()
    ses.commands = frozenset(commands)
    ses.at = at_debugger
    ses.running = not at_debugger      # what the fake's block reads, as the real one reads its flag
    out = server.status()
    assert out["session"]["running"] is (not at_debugger), out
    assert out["summary"] == f"status: alive, {word}", out


def test_a_cancelled_wait_that_ends_as_it_was_leaves_the_guest_running(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    ses = _running()
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["none"]()
    assert ses.breaks == 0
    assert st.STATE.cancelled is not None and st.STATE.cancelled.left == "running"


def test_a_cancelled_wait_that_ends_killed_closes_the_session(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    ses = install()
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["kill"]()
    assert ses.closed == 1 and st.STATE.session is None
    assert st.STATE.cancelled is not None and st.STATE.cancelled.left == "closed"


def test_only_the_outer_reply_of_a_sequence_carries_the_record(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    _running().at = True
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["none"]()
    out = server.perform(steps=[{"op": "registers"}], settle_seconds=0.0)
    assert out.get("cancelled", {}).get("tool") == "wait_none", list(out)
    assert all("cancelled" not in (r.get("reply") or {}) for r in out.get("ran", [])), out


def test_a_call_cancelled_while_it_waited_for_the_lock_touches_nothing(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ses = install()
    _cancel_at(monkeypatch, 1)
    with pytest.raises(asyncio.CancelledError):
        server.write(ref="F000:0000", data_hex="aa")
    assert ses.altered is False


def test_a_retrace_out_when_the_call_is_cancelled_is_left_pending(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ses = _running()

    def retrace_cancelled(*a: Any, **k: Any) -> tuple[bool, float]:
        raise asyncio.CancelledError
    monkeypatch.setattr(ses, "retrace", retrace_cancelled, raising=False)
    st.STATE.retrace_pending = False
    with pytest.raises(asyncio.CancelledError):
        retrace._advance(ses, 0.0, 10.0, mprogress.no_progress)  # type: ignore[arg-type]
    assert st.STATE.retrace_pending is True


def test_a_tool_that_waits_and_declares_no_end_is_refused_at_registration() -> None:
    def waits(ctx: Any = None) -> dict[str, Any]:
        return {"status": "ok"}
    with pytest.raises(TypeError, match="on_cancel"):
        dosbox_mcp.tool("waits", summary=lambda a, r: "")(waits)


@pytest.mark.parametrize("end", ["stop", "kill"])
def test_a_call_cancelled_in_the_queue_applies_no_end_and_keeps_no_record(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any], end: str) -> None:
    """Cancelled before its body ran, the call did nothing, so it has nothing to end: a queued
    `start` that closed the session it never touched would be the worst of it."""
    install()
    ses = _running()
    _cancel_at(monkeypatch, 1)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool[end]()
    assert ses.breaks == 0 and ses.closed == 0 and st.STATE.session is not None
    assert st.STATE.cancelled is None


def test_a_second_cancel_keeps_the_name_of_the_first_no_reply_reported(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    _running()
    for _ in range(2):
        _cancel_at(monkeypatch, 2)
        with pytest.raises(asyncio.CancelledError):
            waiting_tool["none"]()
    out = server.status()
    assert out["cancelled"]["earlier"] == ["wait_none"], out["cancelled"]


def test_the_stop_end_hands_the_next_reply_what_the_stop_applied(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    """A declaration made while the guest ran is applied at the stop the end makes; the stop's
    own reply goes to nobody, so the account rides on the next one."""
    from scry_dosbox_x import running
    install()
    _running()

    def stop_reply(session: Any, **fields: Any) -> dict[str, Any]:
        st.STATE.applied_last["armed"] = ["F000:0100"]
        return st.reply(**fields)
    monkeypatch.setattr(running, "stop_reply", stop_reply)
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert server.status().get("applied_on_stop") == {"armed": ["F000:0100"]}


def test_the_stop_end_names_its_stop_as_the_cancelled_calls(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    """The stop the end makes on a running guest is the cancelled call's own: its reply is built
    to say so (`asked_by`), not that no declaration can be told."""
    from scry_dosbox_x import running
    install()
    _running()
    asked: list[dict[str, Any]] = []

    def stop_reply(session: Any, **fields: Any) -> dict[str, Any]:
        asked.append(fields)
        return {}
    monkeypatch.setattr(running, "stop_reply", stop_reply)
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert [f.get("asked_by") for f in asked] == ["cancel"], asked


def test_a_stop_of_its_own_the_call_had_reached_is_recorded_as_its_own(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    """Cancelled with the guest already at a stop nobody has read (its own retrace, its own
    breakpoint), the end records it as the call's, as the call's bound would have."""
    from scry_dosbox_x import running
    install()
    ses = _running()
    ses.at = True
    ses.stop_count = 7
    st.STATE.last_stop["stop_count"] = 6
    recorded: list[bool] = []

    def stop_or_base(*a: Any, **k: Any) -> dict[str, Any]:
        recorded.append(True)
        return {}
    monkeypatch.setattr(running, "stop_or_base", stop_or_base)
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert recorded == [True] and ses.breaks == 0


def test_a_retrace_already_heard_when_the_call_is_cancelled_is_not_left_pending(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ses = _running()
    ses.at = True

    def retrace_cancelled(*a: Any, **k: Any) -> tuple[bool, float]:
        raise asyncio.CancelledError
    monkeypatch.setattr(ses, "retrace", retrace_cancelled, raising=False)
    st.STATE.retrace_pending = True
    with pytest.raises(asyncio.CancelledError):
        retrace._advance(ses, 0.0, 10.0, mprogress.no_progress)  # type: ignore[arg-type]
    assert st.STATE.retrace_pending is False


def test_an_end_that_breaks_on_the_way_still_records_and_still_unwinds(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    ses = _running()

    def broken(seconds: float = 5.0) -> float:
        raise OSError("the pty went away")
    monkeypatch.setattr(ses, "break_in", broken)
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert st.STATE.cancelled is not None and st.STATE.cancelled.left == "unknown"


def test_a_kill_that_could_not_reap_is_not_called_closed(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    ses = install()

    def close(*a: Any, **k: Any) -> None:
        ses.closed += 1
        ses.reap_failed = "SIGKILL was sent and the process had not been reaped"
    monkeypatch.setattr(ses, "close", close)
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["kill"]()
    assert st.STATE.cancelled is not None and st.STATE.cancelled.left == "unknown"


def test_a_schema_refusal_whose_call_was_cancelled_spends_no_account(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import BaseModel, ValidationError

    class _M(BaseModel):
        n: int
    try:
        _M(n="x")  # type: ignore[arg-type]
    except ValidationError as e:
        cause = e
    install()
    st.STATE.cancelled = cancel.Cancelled("run_for", 1.0, "stopped")
    st.STATE.applied_last["armed"] = ["F000:0100"]
    _cancel_at(monkeypatch, 1)
    with pytest.raises(asyncio.CancelledError):
        dosbox_mcp.refusal("read_memory", {"ref": 5}, cause)
    assert st.STATE.cancelled is not None and st.STATE.applied_last, "an account was spent"


def test_a_step_of_a_sequence_cancelled_is_the_sequences_cancel_alone(
        monkeypatch: pytest.MonkeyPatch, waiting_tool: dict[str, Any]) -> None:
    install()
    _running().at = True
    _cancel_at(monkeypatch, 3)                 # perform's entry, the step's entry, its wait
    with pytest.raises(asyncio.CancelledError):
        server.perform(steps=[{"op": "wait_none"}], settle_seconds=0.0)
    out = server.status()
    assert out["cancelled"]["tool"] == "perform" and "earlier" not in out["cancelled"], out


def test_a_call_cancelled_as_its_body_returned_is_recorded_and_its_accounts_wait(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`st.reply` hands over a stop's accounts as the body builds its reply; a cancel that came as
    the body returned means nobody reads it, so the accounts go back for the next reply, and the
    call is recorded with no end applied."""
    install()
    ses = _running()
    ses.at = True
    st.STATE.found_stop_last = {"stop_seq": 7, "at": "F000:0000", "attribution": {}}
    st.STATE.applied_last.update({"armed": ["F000:0010"]})
    _cancel_at(monkeypatch, 2)               # the poll after the body, not the entry's
    with pytest.raises(asyncio.CancelledError):
        server.status()
    out = server.status()
    assert out["cancelled"]["tool"] == "status" and out["cancelled"]["left"] == "stopped", out
    assert out["stopped_on_its_own"]["stop_seq"] == 7, out
    assert out["applied_on_stop"] == {"armed": ["F000:0010"]}, out
    assert ses.breaks == 0


@pytest.mark.parametrize("captures", [True, False], ids=["captures-dir", "none"])
def test_a_cancelled_trace_ends_stopped_with_its_log_closed_and_the_file_kept(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path,
        waiting_tool: dict[str, Any], captures: bool) -> None:
    """A trace cancelled mid-run leaves the debugger's CPU log open; the `stop` end moves what it
    wrote aside (`LOGC 0` on a log the machine already closed opens a fresh one over the name) and
    closes it, before the stop is recorded: the close is a release and a return of its own, and
    recorded after it the next contact would find a stop nobody made. What it wrote goes where a
    trace with no `dest` goes, the session's captures directory, and to the working directory
    only for a session started with none."""
    from scry_dosbox_x import trace
    install()
    ses = _running()
    ses.launch.cwd = tmp_path
    home = tmp_path / "caps" if captures else tmp_path
    home.mkdir(exist_ok=True)
    ses.launch.captures_dir = home if captures else None
    ses.stop_count = 1
    st.STATE.last_stop["stop_count"] = 1
    written = trace.log_places(tmp_path)[0]
    written.write_text("one line the trace had written\n")
    typed: list[tuple[str, int]] = []

    def log_cpu(word: str, count: int, began: float, deadline: float,
                progress: Any = None) -> tuple[bool, float]:
        typed.append((word, count))
        written.write_text("")                 # a fresh log over the name, as the close opens
        ses.stop_count = (ses.stop_count or 0) + 1   # released and back at the prompt
        return False, 0.0
    monkeypatch.setattr(ses, "log_cpu", log_cpu)
    from scry_dosbox_x import running
    asked: list[Any] = []
    real = running.stop_reply

    def stop_reply(session: Any, **fields: Any) -> dict[str, Any]:
        asked.append(fields.get("asked_by"))
        return real(session, **fields)
    monkeypatch.setattr(running, "stop_reply", stop_reply)
    st.STATE.log_open = True
    _cancel_at(monkeypatch, 2)
    with pytest.raises(asyncio.CancelledError):
        waiting_tool["stop"]()
    assert ses.breaks == 1 and typed == [("LOGC", 0)], typed
    assert asked == ["cancel"], "the stop the end broke in for is the cancelled call's"
    assert st.STATE.log_open is False
    kept = sorted(home.glob("trace-cancelled-*.trace"))
    assert [k.read_text() for k in kept] == ["one line the trace had written\n"], kept
    assert not written.exists(), "the empty log the close opened was left behind"
    out = server.status()
    assert out["cancelled"]["left"] == "stopped", out
    assert "stopped_on_its_own" not in out, "the close was reported as a stop of its own"


def test_a_frame_whose_retrace_never_comes_still_reports_progress(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The line of a run by frames moves with each frame; while one frame's retrace does not
    come, the retrace's own wait still says the run is alive, on wall time, through it."""
    ses = install()
    ses.pane_clock_ms = 1000.0  # type: ignore[attr-defined]
    lines: list[tuple[float, float | None, str]] = []

    def stuck(began: float, deadline: float, progress: Any = None) -> tuple[bool, float]:
        for second in (1, 2, 3):               # the retrace's own wait, once a report period
            time.sleep(mprogress.PROGRESS_EVERY_S * 1.1)
            progress(float(second), None, f"run_for: the next retrace: running {second}s")
        raise asyncio.CancelledError           # the caller gave up on it
    monkeypatch.setattr(ses, "retrace", stuck)
    monkeypatch.setattr(mprogress, "PROGRESS_EVERY_S", 0.2)   # short, never zero: it is judged
    with pytest.raises(asyncio.CancelledError):
        retrace.run_for(ses, 5, 0, 30.0,  # type: ignore[arg-type]
                        lambda p, t, m: lines.append((p, t, m)))
    waiting = [m for _p, _t, m in lines if "frame 0 of 5" in m and "waiting for its retrace" in m]
    assert len(waiting) >= 2, lines           # it goes on saying so, on the wall clock


def test_accounts_given_back_one_after_another_accumulate_as_a_stops_do() -> None:
    """A cancelled `perform` gives back each answered step's account and then its end's stop:
    the next reply says all of them, as one stop's drains are joined (`arming.merge_applied`)."""
    from scry_dosbox_x import mcp as dosbox_mcp
    from scry_dosbox_x import state as dstate

    dstate.STATE.applied_last.clear()
    dosbox_mcp._keep_accounts({"applied_on_stop": {"armed": ["A"], "disarmed": [],
                                                   "symbols_loaded": True}})
    dosbox_mcp._keep_accounts({"applied_on_stop": {"armed": ["B"], "disarmed": ["C"],
                                                   "symbols_loaded": False}})
    assert dstate.STATE.applied_last == {"armed": ["A", "B"], "disarmed": ["C"],
                                         "symbols_loaded": True}
    dstate.STATE.applied_last.clear()
