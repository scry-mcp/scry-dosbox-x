"""Every reply closes with `session`, composed by the `tool` decorator after the body."""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from collections.abc import Iterator
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dosbox_x_server_support import clean_session, install  # noqa: E402,F401  (the autouse teardown)

from scry_dosbox_x import checks  # noqa: E402
from scry_dosbox_x import mcp as dosbox_mcp  # noqa: E402
from scry_dosbox_x import server as s  # noqa: E402
from scry_dosbox_x import state as st  # noqa: E402


@pytest.fixture
def late_tool(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """A tool whose body writes to the machine after its envelope was built."""
    monkeypatch.setattr(checks, "check", lambda name, **given: None)
    def late_body() -> dict[str, Any]:
        reply = st.reply(first=1)
        assert st.STATE.session is not None
        st.STATE.session.altered = True
        reply["late"] = 2
        return reply

    registered = dosbox_mcp.tool("A late body", summary=lambda args, reply: "late: done")(
        late_body)
    yield registered
    s.mcp._tool_manager._tools.pop("late_body", None)
    dosbox_mcp.BOUNDARY.summaries.pop("late_body", None)


def test_the_decorator_puts_session_last_and_composes_it_after_the_body(late_tool: Any) -> None:
    install()
    out = late_tool()
    assert list(out)[0] == "summary" and list(out)[-1] == "session", list(out)
    assert out["late"] == 2 and out["first"] == 1, out
    assert out["session"]["altered"] is True, (
        "the block was composed before the body wrote to the machine", out["session"])


def test_a_schema_refusal_is_closed_by_the_same_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    real = dosbox_mcp.BOUNDARY.finished

    def spy(name: str, *a: Any, **k: Any) -> dict[str, Any]:
        seen.append(name)
        return real(name, *a, **k)

    monkeypatch.setattr(dosbox_mcp.BOUNDARY, "finished", spy)
    install().altered = True
    res = asyncio.run(s.mcp.call_tool("read_memory", {"ref": "F000:0000", "length": "x"}))
    out = json.loads("".join(c.text for c in res.content if getattr(c, "text", None)))
    assert seen == ["read_memory"] and out["code"] == "bad_argument", (seen, out)
    assert list(out)[0] == "summary" and list(out)[-1] == "session", list(out)
    assert out["session"]["altered"] is True, out["session"]


def test_close_reports_the_session_as_it_is_after_the_close() -> None:
    ses = install()
    ses.altered = True
    out = s.close()
    assert out["closed"] is True, out
    assert out["session"] == {"alive": False, "running": False, "altered": False}, out


def test_the_block_is_composed_under_the_lock_over_the_one_machine(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Composed outside it, a call that has just let go of the machine reads `STATE.session`
    while another call clears it."""
    held: list[bool] = []
    real = dosbox_mcp.BOUNDARY.finished

    def spy(*a: Any, **k: Any) -> dict[str, Any]:
        held.append(dosbox_mcp.LOCK.held_here())
        return real(*a, **k)

    monkeypatch.setattr(dosbox_mcp.BOUNDARY, "finished", spy)
    install()
    s.status()
    assert held == [True], held
