"""The root conftest: it keeps the developer's own `DOSBOX_X_BINARY` out of every case, so the
binary ladder a case climbs is the one the case sets up."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def no_binary_variable(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("DOSBOX_X_BINARY", raising=False)
    yield
