from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest
from scry_core import reply_schema, roster
from scry_core.instruction import StopInstruction

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


def test_the_stop_and_trace_instruction_is_the_one_shared_shape() -> None:
    """Both servers answer `StopInstruction`, so a reader that learned one reply reads the other."""
    hinted = {name: get_type_hints(model).get("instruction")
              for name, model in replies.MODELS.items()}
    carried = {name: hint for name, hint in hinted.items() if hint is not None}
    assert {"stop", "trace"} <= set(carried), sorted(carried)
    wrong = {name: hint for name, hint in carried.items() if hint is not StopInstruction}
    assert not wrong, wrong


def test_a_real_tools_reply_with_a_field_its_model_does_not_name_fails() -> None:
    reply_schema.check("status", {"status": "ok", "cpu_mode": "real", "pending": {},
                                  "presence": False, "last_stop": {},
                                  "knowledge": {"served": 0, "held_back": 0}})
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


@pytest.mark.parametrize("tool", ["disassemble", "find", "memdump", "read_memory", "scan",
                                  "write"])
def test_a_tool_that_reads_or_writes_at_a_ref_echoes_it_and_says_so(tool: str) -> None:
    """Each answers the `ref` it was given beside `seg_off`, as scry-mame beside `addr`; every
    tool but `scan` always does, so its model requires it (CONTRIBUTING.md)."""
    model = replies.MODELS[tool]
    assert ("ref" in reply_schema.own_required(model)) is (tool != "scan"), tool
    doc = next(t for t in asyncio.run(server.mcp.list_tools()) if t.name == tool).description
    assert "ref" in reply_schema.reply_sentence_names(doc or ""), doc


def test_start_says_what_front_means_and_that_it_is_not_focus() -> None:
    """`start` lists `front` in its `window`, and "front" reads as holding the keyboard."""
    doc = next(t for t in asyncio.run(server.mcp.list_tools()) if t.name == "start").description
    assert ("`front` says no other application's window covers its centre, not that it has the "
            "keyboard focus") in " ".join((doc or "").split())
