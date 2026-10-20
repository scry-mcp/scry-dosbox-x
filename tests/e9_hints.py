"""A spy on the `how` each stop's E9 block is built with, shared by the tests that pin which way a
stop's reply tells its caller to see the lines."""

from __future__ import annotations

from typing import Any

import pytest

import dosbox_running as running


def hints_heard(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Each stop's `how`, in order, as the stop's E9 block is built from it."""
    seen: list[str] = []
    real = running._stop_e9

    def heard(session: Any, e9: str, e9_filter: str, e9_stamp: str | None = None,
              how: str = running.E9_BY_LOG) -> dict[str, Any]:
        seen.append(how)
        return real(session, e9, e9_filter, e9_stamp, how)
    monkeypatch.setattr(running, "_stop_e9", heard)
    return seen
