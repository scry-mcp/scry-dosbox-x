"""Every tool's reply is judged against its declared model (`scry_core.reply_schema`): each tool
has one, the published schema names its fields and constrains none, and a reply with a field its
model does not name fails the battery."""

from __future__ import annotations

import asyncio
from typing import Any

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

#: What each tool's `Reply` paragraphs quote that is no field of its reply: a row's own field,
#: a value it holds, an option or a program it names, BY TOOL, so a word allowed for one tool
#: never hides a field another tool's model lacks. A name in neither its model nor its row here
#: fails; a word kept here that its tool no longer quotes fails too.
REPLY_WORDS: dict[str, tuple[str, ...]] = {
    "close": ("quit",),
    "log_wait": ("logfile",),
    "disassemble": ("addr",),
    "debug": ("altered",),
    "stop": ("BREAK",),
    "run_for": ("VRT",),
    "breakpoint_interrupt": ("pending",),
    "comment_list": (*ROWS, "text", "addr", "why", "orphan"),
    "series_capture": ("capture_video", "ffmpeg"),
    "breakpoint_list": (*ROWS, "entry", "armed", "unresolved", "gone", "unarmable", "ambiguous",
                        "pending", "stale", "orphan", "marked"),
    "breakpoint_clear": ("ok",),
    "watch_list": (*ROWS, "mode", "length", "fmt", "stale"),
    "watch_clear": ("ok",),
}


def test_every_field_a_reply_sentence_names_is_in_its_model() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    wrong: dict[str, Any] = {}
    for t in tools:
        doc, model = t.description or "", replies.MODELS[t.name]
        allowed = set(REPLY_WORDS.get(t.name, ()))
        if not reply_schema.reply_sentence_names(doc) and reply_schema.own_fields(model):
            wrong[t.name] = "its description names no field of its reply"
        elif miss := reply_schema.unmodelled(
                doc, model, names | set(t.input_schema.get("properties", {})) | allowed):
            wrong[t.name] = miss
        elif unused := sorted(allowed - set(reply_schema.reply_sentence_names(doc))):
            wrong[t.name] = f"allowed and no longer quoted: {unused}"
    assert not wrong, wrong


def test_every_tool_that_answers_with_a_stop_names_its_fields() -> None:
    """The stop's fields reach a description through `STOP_FIELDS`, after a colon the sentence
    check reads as a list's: each is held to the model of every tool that quotes it."""
    fields = reply_schema.reply_sentence_names("Reply: " + docs.STOP_FIELDS.split(":", 1)[1])
    assert len(fields) > 5, fields
    quoting = [t for t in asyncio.run(server.mcp.list_tools())
               if docs.STOP_FIELDS in (t.description or "")]
    assert len(quoting) > 3, [t.name for t in quoting]
    held = {t.name: set(reply_schema.own_fields(replies.MODELS[t.name])) for t in quoting}
    lacks = {name: sorted(set(fields) - got) for name, got in held.items() if set(fields) - got}
    assert not lacks, lacks
