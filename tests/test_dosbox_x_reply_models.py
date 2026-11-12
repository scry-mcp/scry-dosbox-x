from __future__ import annotations

import asyncio

import pytest
from scry_core import reply_schema, roster

from scry_dosbox_x import docs, replies, server


def test_every_tool_publishes_each_field_as_its_value_or_unavailable() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert tools and set(reply_schema._JUDGES) >= {t.name for t in tools}
    for t in tools:
        schema = t.output_schema
        assert schema is not None and schema["required"] == ["status"], t.name
        assert "summary" in schema["properties"], t.name
        for field in reply_schema.own_fields(replies.MODELS[t.name]):
            assert "anyOf" in schema["properties"][field], (t.name, field)


def test_a_real_tools_reply_with_a_field_its_model_does_not_name_fails() -> None:
    reply_schema.check("status", {"status": "ok", "cpu_mode": "real", "pending": {},
                                  "presence": False, "last_stop": {}})
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
    "screen_view": ("isolate", "pixel"),
    "captures": ("bytes",),
    "audio_compare": ("peak_dbfs", "rms_dbfs", "silent", "silence_spans", "onset_s",
                      "clipping_run", "clipped"),
}


def test_every_field_a_reply_sentence_names_is_in_its_model() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    wrong = reply_schema.sentence_faults(tools, replies.MODELS, REPLY_WORDS)
    assert not wrong, wrong


def test_every_tool_that_answers_with_a_stop_names_its_fields() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    lacks = reply_schema.stop_fields_lacking(tools, replies.MODELS, docs.STOP_FIELDS)
    assert not lacks, lacks


def test_record_answers_the_family_both_servers_declare() -> None:
    declared = set(roster.RECORD_REPLY_FIELDS)
    assert declared <= set(replies.MODELS["record"].__annotations__), declared


def test_record_speaks_the_words_scry_core_declares() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    doc = next(t for t in tools if t.name == "record").description or ""
    for words in (roster.RECORD_ARGS, roster.RECORD_CUT, roster.RECORD_REPLY):
        assert words in doc, words
