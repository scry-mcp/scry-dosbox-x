from __future__ import annotations

import asyncio

import pytest
from scry_core import reply_schema

import dosbox_docs as docs
import dosbox_replies as replies
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


ROWS = ("ref", "by", "cpu", "created_at", "origin", "inherited", "age_s", "state")

#: Words a tool's `Reply` text quotes that are no field of its reply, per tool.
REPLY_WORDS: dict[str, tuple[str, ...]] = {
    "close": ("quit", "why"),
    "step": ("over",),
    "log_wait": ("logfile",),
    "status": ("alive", "running", "altered"),
    "screen_signature": ("dest", "scale"),
    "captures": ("bytes",),
}


def test_every_field_a_reply_sentence_names_is_in_its_model() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    wrong = reply_schema.sentence_faults(tools, replies.MODELS, REPLY_WORDS)
    assert not wrong, wrong


def test_every_tool_that_answers_with_a_stop_names_its_fields() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    lacks = reply_schema.stop_fields_lacking(tools, replies.MODELS, docs.STOP_FIELDS)
    assert not lacks, lacks
