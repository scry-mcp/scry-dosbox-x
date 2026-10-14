"""The root conftest: it loads the shape guard every reply of this server's suite is held to, and
keeps the developer's own `DOSBOX_X_BINARY` out of every case, so the binary ladder a case climbs
is the one the case sets up."""

from collections.abc import Iterator

import pytest
from scry_core.reply_shapes import one_word_one_shape as one_word_one_shape


@pytest.fixture(autouse=True)
def no_binary_variable(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("DOSBOX_X_BINARY", raising=False)
    yield
