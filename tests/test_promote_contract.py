"""scry-core's `PromoteContract` over this server's own `start`, `promote` and `close`, on a
booted fake."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _start_on_a_booted_fake
from scry_core import conformance, screen_map
from scry_core import promote as core_promote

from scry_dosbox_x import server
from scry_dosbox_x.state import STATE


class _Subject:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        monkeypatch.setattr(STATE, "drafts", core_promote.Drafts())
        monkeypatch.setattr(STATE, "maps", screen_map.Maps())
        monkeypatch.setattr(STATE, "guest", "")

    def start(self, project: Path, name: str) -> dict[str, Any]:
        return _start_on_a_booted_fake(project, self.monkeypatch, program=f"{name.upper()}.EXE")

    def promote(self, **arguments: Any) -> dict[str, Any]:
        return cast(dict[str, Any], server.promote(**arguments))

    def close(self) -> dict[str, Any]:
        return cast(dict[str, Any], server.close())


class TestDosboxXPromotion(conformance.PromoteContract):
    @pytest.fixture
    def subject(self, monkeypatch: pytest.MonkeyPatch) -> _Subject:
        return _Subject(monkeypatch)
