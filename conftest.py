"""Unit cases never see the developer's DOSBOX_X_BINARY; live cases keep it."""

from collections.abc import Iterator
from pathlib import Path

import pytest

LIVE = Path(__file__).resolve().parent / "tests" / "live"


@pytest.fixture(autouse=True)
def no_binary_variable(request: pytest.FixtureRequest,
                       monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if not request.node.path.is_relative_to(LIVE):
        monkeypatch.delenv("DOSBOX_X_BINARY", raising=False)
    yield
