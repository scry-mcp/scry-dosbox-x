"""Every tool's reply is judged against its declared model (`scry_core.reply_schema`): each tool
has one, the published schema names its fields and constrains none, and a reply with a field its
model does not name fails the battery."""

from __future__ import annotations

import asyncio

import pytest
from scry_core import reply_schema

import dosbox_x_server as server


def test_every_tool_publishes_its_models_field_names_and_no_constraint() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert tools and set(reply_schema._JUDGES) >= {t.name for t in tools}
    for t in tools:
        schema = t.output_schema
        assert schema is not None and schema["required"] == ["status"], t.name
        assert "summary" in schema["properties"] and all(
            spec == {} for spec in schema["properties"].values()), t.name


def test_a_real_tools_reply_with_a_field_its_model_does_not_name_fails() -> None:
    reply_schema.check("status", {"status": "ok", "cpu_mode": "real"})
    with pytest.raises(ValueError):
        reply_schema.check("status", {"status": "ok", "alive": False, "stray": 1})
