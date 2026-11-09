"""Each closed vocabulary a tool argument is judged against is published as that argument's
JSON-schema `enum` (a `pattern` of its words in either case where the server takes any case),
and each bounded scalar its `minimum`/`maximum`, from the constant its judge reads: the client
sees the words and the bounds where it builds the call. The judge stays the argument's own
(`vocab.one_of`, a range check), so a word outside still gets the server's sentence."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest
from scry_core import media_tools, screen_map
from scry_core import scan_vocabulary as words
from scry_core import vocabulary as vocab
from scry_core.reply_contract import Invalid

from scry_dosbox_x import (
    advance,
    capture_files,
    checks,
    code,
    folds,
    grammar,
    hardware,
    inputs,
    machine,
    placement,
    server,
    start_symbols,
    stepping,
)
from scry_dosbox_x import dac as vgadac
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import find as finder
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import screen_pens as by_pens
from scry_dosbox_x import session as ds
from scry_dosbox_x import trace as tracing

CLOSED: list[tuple[str, str, tuple[Any, ...]]] = [
    ("log", "channel", dlogs.LOG_CHANNELS), ("log_wait", "channel", dlogs.LOG_CHANNELS),
    ("scan", "cell_bytes", finder.CELL_BYTES), ("scan", "operator", finder.OPERATORS),
    ("stop", "until", advance.STOP_UNTIL),
    ("step", "mode", stepping.STEP_MODES), ("trace", "shape", tracing.SHAPE_WORDS),
    ("breakpoint_at", "by", checks.BREAKPOINT_BY), ("watch_add", "by", checks.WATCH_BY),
    ("watch_add", "mode", dec.WATCH_MODES),
    ("watch_add", "trigger_type", dec.TRIGGER_TYPES),
    ("send_keys", "action", inputs.KEY_ACTIONS),
    ("send_mouse", "button", ("", *inputs.BUTTON_WORDS)),
    ("send_mouse", "action", ("", *inputs.ACTIONS)), ("send_mouse", "units", inputs.UNITS),
    ("machine_map", "sections", machine.SECTION_NAMES),
    ("declaration_list", "kind", ("", *folds.KINDS)), ("declaration_clear", "kind", folds.KINDS),
    ("screen_map_write", "cells", screen_map.CELLS_WORDS),
    ("screen_view", "mode", by_pens.MODES),
    # A fold's `method`, judged by `scry_core.methods` against the fold's own table.
    ("comment_write", "method", tuple(folds.COMMENT)),
    ("screen_map_write", "method", tuple(folds.MAP)),
    ("scan", "method", tuple(folds.SCAN)), ("state_write", "method", tuple(folds.STATE_METHODS)),
    ("image_compare", "method", tuple(media_tools.IMAGE_METHODS)),
    ("audio_compare", "method", tuple(media_tools.AUDIO_METHODS)),
    ("audio_record", "kind", tuple(capture_files.AUDIO_KINDS)),
    ("port", "method", tuple(folds.PORT)), ("port", "bits", tuple(hardware.BITS)),
    ("pic", "method", tuple(folds.PIC)), ("a20", "method", tuple(folds.A20)),
]
#: The two taken in any case: a pattern of their words, never an `enum` that would refuse one.
FOLDED: list[tuple[str, str, tuple[str, ...]]] = [
    ("symbols_load", "base_from", ds.SELINFO_REGS),
    ("start", "base_from", start_symbols.BASE_FROM),
    ("send_keys", "modifiers", inputs.MODIFIER_WORDS),
]
RANGES: list[tuple[str, str, int, int]] = [
    ("log", "limit", 1, dlogs.LOG_LIMIT_MAX), ("drive", "limit", 1, dlogs.LOG_LIMIT_MAX),
    ("scan", "limit", 1, words.HITS_MAX),
    ("read_memory", "length", 1, grammar.READ_BYTES_MAX),
    ("disassemble", "length", 1, code.LENGTH_MAX),
    ("symbols_find", "limit", 1, placement.SYMBOLS_LIMIT_MAX),
    ("step", "count", 1, stepping.STEP_MAX), ("trace", "instructions", 1, tracing.INSTRUCTIONS_MAX),
    ("breakpoint_interrupt", "number", 0, ds.BYTE_MAX),
    ("breakpoint_interrupt", "ah", 0, ds.BYTE_MAX), ("interrupt_vectors", "number", 0, ds.BYTE_MAX),
    ("send_mouse", "x", 0, inputs.MAX_COORD), ("send_mouse", "y", 0, inputs.MAX_COORD),
    ("send_mouse", "to_x", 0, inputs.MAX_COORD), ("send_mouse", "to_y", 0, inputs.MAX_COORD),
    ("start", "session_seconds", 1, dlaunch.MAX_SECONDS),
    ("start", "input_port", 0, dlaunch.INPUT_PORT_MAX),
    ("palette", "first", 0, vgadac.DAC_ENTRIES - 1), ("palette", "count", 0, vgadac.DAC_ENTRIES),
    ("pic", "irq", 0, hardware.IRQ_MAX),
    ("screen_wait", "every", 0, checks.SAMPLED_EVERY_MAX),
]
WAITS = ("seconds", "settle_seconds")
#: The waits whose 0 means no wait at all, so their floor is closed.
ZERO_MEANS = {("resume", "seconds"), ("perform", "settle_seconds"), ("drive", "settle_seconds"),
              ("start", "settle_seconds")}


def _schemas() -> dict[str, dict[str, Any]]:
    return {t.name: t.input_schema for t in asyncio.run(server.mcp.list_tools())}


def _scalar(prop: dict[str, Any]) -> dict[str, Any]:
    """The non-null branch of an optional argument, or the argument; a list's item."""
    branch = next((b for b in prop.get("anyOf", []) if b.get("type") != "null"), prop)
    return branch["items"] if branch.get("type") == "array" else branch


@pytest.mark.parametrize(("tool", "arg", "words"), CLOSED, ids=[f"{t}.{a}" for t, a, _ in CLOSED])
def test_a_closed_argument_publishes_its_judges_words(tool: str, arg: str,
                                                      words: tuple[Any, ...]) -> None:
    assert _scalar(_schemas()[tool]["properties"][arg]).get("enum") == list(words)


@pytest.mark.parametrize(("tool", "arg", "words"), FOLDED, ids=[f"{t}.{a}" for t, a, _ in FOLDED])
def test_a_vocabulary_taken_in_any_case_publishes_a_pattern_that_takes_every_case(
        tool: str, arg: str, words: tuple[str, ...]) -> None:
    item = _scalar(_schemas()[tool]["properties"][arg])
    assert "enum" not in item
    for word in words:
        for spelled in (word, word.lower(), word.upper()):
            assert re.fullmatch(item["pattern"], spelled), (word, spelled)
    assert not re.fullmatch(item["pattern"], "nope")


@pytest.mark.parametrize(("tool", "arg", "lo", "hi"), RANGES,
                         ids=[f"{t}.{a}" for t, a, _, _ in RANGES])
def test_a_ranged_argument_publishes_its_judges_bounds(tool: str, arg: str, lo: int,
                                                       hi: int) -> None:
    prop = _scalar(_schemas()[tool]["properties"][arg])
    assert (prop.get("minimum"), prop.get("maximum")) == (lo, hi), prop


def test_every_wait_publishes_the_one_bound_and_nothing_publishes_what_no_row_holds() -> None:
    with pytest.raises(Invalid):
        vocab.check_wait(0)            # the judge refuses the floor the schema leaves open
    vocab.check_wait(0, zero_means="no wait")
    for wild in (10**400, float("nan"), float("inf"), True, "3"):
        with pytest.raises(Invalid, match="is not a bound"):
            vocab.check_wait(wild)
    enums, ranges, waits = set(), set(), 0
    for tool, schema in _schemas().items():
        for arg, prop in schema["properties"].items():
            scalar = _scalar(prop)
            if "enum" in scalar or "pattern" in scalar:
                enums.add((tool, arg))
            if arg in WAITS:
                waits += 1
                low = "minimum" if (tool, arg) in ZERO_MEANS else "exclusiveMinimum"
                bound = (scalar.get(low), scalar.get("maximum"))
                assert bound == (0, vocab.WAIT_MAX_S), (tool, arg)
            elif "maximum" in scalar:
                ranges.add((tool, arg))
    assert waits, "no wait was found: the schema read examined nothing"
    assert ranges == {(t, a) for t, a, _, _ in RANGES}
    assert enums == {(t, a) for t, a, _ in CLOSED} | {(t, a) for t, a, _ in FOLDED}
