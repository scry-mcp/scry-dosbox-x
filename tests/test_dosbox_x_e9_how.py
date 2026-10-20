"""A stop's E9 block names a way the caller can take to see the lines: the `e9` argument on the
four tools that take one, `log` on every other stop, each hint held to the signature it names."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any, cast

import pytest
from e9_hints import hints_heard
from test_dosbox_x_screen import waiting

import dosbox_running as running
import dosbox_state as dstate
import dosbox_x_server as server

E9_TOOLS = ("resume", "step", "run_to", "run_for")


def _named(how: str) -> set[str]:
    return set(re.findall(r"(\w+)=", how))


def test_the_argument_hint_names_only_what_each_e9_tool_takes() -> None:
    for tool in E9_TOOLS:
        params = inspect.signature(getattr(server, tool)).parameters
        assert _named(running.E9_BY_ARGUMENT) <= set(params), tool


def test_the_log_hint_names_log_with_every_argument_it_requires() -> None:
    params = inspect.signature(server.log).parameters
    required = {n for n, p in params.items() if p.default is inspect.Parameter.empty}
    named = _named(running.E9_BY_LOG)
    assert "`log(" in running.E9_BY_LOG and "e9=" not in running.E9_BY_LOG
    assert named <= set(params) and required <= named, (named, required)
    for tool in ("stop", "screen_wait", "perform", "trace"):
        assert "e9" not in inspect.signature(getattr(server, tool)).parameters, tool


def test_a_stop_screen_wait_reaches_names_the_log(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """`screen_wait` takes no `e9`, so the stop it reaches names `log`."""
    seen = hints_heard(monkeypatch)
    # THE DOUBLE IS THIS CASE'S ALONE: the session it installs goes back with the patch.
    monkeypatch.setattr(dstate.STATE, "session", dstate.STATE.session)
    waiting(["probe-park", "probe-booted"], 1, tmp_path)
    r = cast(dict[str, Any], server.screen_wait(text="PROBE.COM", seconds=10))
    assert r["status"] == "ok" and seen == [running.E9_BY_LOG], (r, seen)
