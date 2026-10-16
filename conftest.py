"""The root conftest: it keeps the developer's own `DOSBOX_X_BINARY` out of every unit case, so
the binary ladder a case climbs is the one the case sets up. A LIVE case keeps it: it runs the
emulator the developer named, as the live matrix does."""

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
