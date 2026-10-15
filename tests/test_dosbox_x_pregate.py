"""What needs no machine is judged before the session gate: a value as wrong with no session
as with one answers `bad_argument`, never `no_session`. And the schema says what a tool
requires, the body never contradicting it."""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from test_dosbox_x_server import _names, clean_session, install  # noqa: F401

import dosbox_find as finder
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server


def _refused(reply: Any, code: str = "bad_argument", *words: str) -> dict[str, Any]:
    r = cast(dict[str, Any], reply)
    assert r["status"] == "INVALID" and r["code"] == code, r
    for w in words:
        assert w in r["message"], (w, r["message"])
    return r


def _call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    res = asyncio.run(server.mcp.call_tool(name, args))
    reply: dict[str, Any] = json.loads("".join(getattr(c, "text", "") for c in res.content))
    return reply


# ------------------------------------------------------------------ state names


@pytest.mark.parametrize(("name", "words"), [
    ("abc\n", "letters, digits"), ("a" * 65, "64"), ("1", "slot"), ("42", "slot"),
    ("a b", "letters, digits"), ("", "letters, digits"), ("-a", "letters, digits")])
@pytest.mark.parametrize("tool", ["state_save", "state_load"])
def test_a_state_name_is_judged_with_no_session(tool: str, name: str, words: str) -> None:
    _refused(getattr(server, tool)(name=name), "bad_argument", words)


@pytest.mark.parametrize("name", ["a" * 64, "boot", "a1", "1a", "A_b-c"])
def test_a_state_name_of_the_rule_reaches_the_gate(name: str) -> None:
    _refused(server.state_save(name=name), "no_session")


def test_a_state_wait_out_of_bounds_is_judged_with_no_session() -> None:
    _refused(server.state_save(name="boot", seconds=0), "bad_argument")
    _refused(server.state_load(name="boot", seconds=601), "bad_argument")
    _refused(server.snapshot(seconds=-1), "bad_argument")


# ------------------------------------------------------------------ the pre-gate list


@pytest.mark.parametrize(("tool", "kw", "words"), [
    ("scan_filter", {"operator": "?"}, "operator"),
    ("scan_filter", {"operator": "=", "value": -1}, "value"),
    ("snapshot", {"dest": "rel.png"}, "relative"),
    ("state_save", {"name": "a b"}, "letters"),
    ("resume", {"seconds": -1}, "seconds"),
    ("resume", {"e9": "bogus"}, "e9"),
    ("perform", {"steps": [{"op": "nope"}]}, "nope"),
    ("perform", {"steps": [{"op": "read_memory", "ref": "00A7:zz"}]}, "00A7:zz"),
    ("perform", {"steps": [{"op": "registers"}], "wait": -1}, "wait"),
    ("perform", {"steps": [{"op": "registers"}], "summaries": "yes"}, "summaries"),
    ("drive", {"act": [], "limit": 0}, "act"),
    ("drive", {"act": [{"op": "send_keys", "keys": ["a"]}], "limit": 0}, "limit"),
    ("drive", {"act": [{"op": "send_keys", "keys": ["a"]}], "pattern": "("}, "pattern"),
    ("drive", {"act": [{"op": "send_keys", "keys": ["a"]}], "seconds": 5}, "expect"),
    ("set_register", {"name": "ax", "value": 0x10000}, "16"),
    ("set_register", {"name": "eax", "value": 1 << 32}, "32"),
    ("set_register", {"name": "cs", "value": -1}, "negative"),
    ("scan_start", {"ref": "0000:0400", "length": 3, "width": "word"}, "whole number"),
    ("run_to", {"ref": "0000:0100", "control": ""}, "control"),
    ("breakpoint_at", {"ref": "[g_p]", "by": "pointer"}, "auto, symbol or address"),
    ("breakpoint_at", {"ref": "[g_p]"}, "not declared through a pointer"),
    ("watch_add", {"ref": "foo", "mode": "show", "length": 4, "by": "pointer"},
     "not a pointer ref"),
    ("watch_add", {"ref": "1000:0000", "mode": "show", "length": -5}, "length=-5"),
    ("send_keys", {"keys": ["bogus_key_name"]}, "unknown key name"),
    ("find", {"ref": "1000:0000", "data_hex": "00", "length": -5}, "-5"),
    ("find", {"ref": "1000:0000", "data_hex": "0000", "length": 1}, "shorter"),
    ("resume", {"seconds": "5"}, "not a number"),
    ("resume", {"seconds": math.nan}, "not a number"),
])
def test_a_value_wrong_with_no_machine_is_bad_argument_not_no_session(
        tool: str, kw: dict[str, Any], words: str) -> None:
    _refused(getattr(server, tool)(**kw), "bad_argument", words)


@pytest.mark.parametrize(("tool", "kw"), [
    ("set_register", {"name": "ax", "value": 0xFFFF}),
    ("set_register", {"name": "eax", "value": 0xFFFFFFFF}),
    ("set_register", {"name": "cs", "value": 0}),
    ("scan_start", {"ref": "0000:0400", "length": 4, "width": "word"}),
    ("scan_filter", {"operator": "!"}),
    ("resume", {"seconds": 0}),
    ("perform", {"steps": [{"op": "registers"}]}),
    ("drive", {"act": [{"op": "send_keys", "keys": ["a"]}], "expect": "x"}),
    ("watch_add", {"ref": "[g_p]", "mode": "show", "length": 4, "by": "pointer"}),
    ("watch_add", {"ref": "[g_p]", "mode": "show", "length": 4}),
    ("breakpoint_at", {"ref": "g_p"}),
    ("send_keys", {"keys": ["a"]}),
    ("find", {"ref": "1000:0000", "data_hex": "00", "length": 1}),
])
def test_the_edge_of_each_rule_reaches_the_gate(tool: str, kw: dict[str, Any]) -> None:
    _refused(getattr(server, tool)(**kw), "no_session")


@pytest.mark.parametrize("step", [
    {"op": "send_keys", "keys": 5}, {"op": "set_register", "name": 7, "value": 1},
    {"op": "state_save", "name": ["boot"]}])
@pytest.mark.parametrize("tool", ["perform", "drive"])
def test_a_step_value_of_the_wrong_type_is_a_refusal_not_a_traceback(
        tool: str, step: dict[str, Any]) -> None:
    args: dict[str, Any] = {"steps": [step]}
    if tool == "drive":
        args = {"act": [step], "expect": "x"}
    r = _refused(_call(tool, args), "bad_argument")
    assert "Traceback" not in r["message"] and "Error" not in r["message"], r


def test_watch_add_names_its_own_by_words() -> None:
    _refused(server.watch_add(ref="x", mode="show", length=4, by="nope"), "bad_argument",
             "auto, symbol, address or pointer")


# ------------------------------------------------------------------ run_to and the clears


def test_run_to_without_a_control_is_refused_by_the_schema() -> None:
    reply = _call("run_to", {"ref": "0000:0100"})
    _refused(reply, "bad_argument", "refused by the schema", "control")


def test_an_empty_ref_clears_every_declaration_of_the_family(tmp_path: Path) -> None:
    syms = [dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T")]
    _names(tmp_path, symbols=syms)
    server.breakpoint_at(ref="_uicue_apply")
    server.breakpoint_interrupt(number=0x21)
    server.watch_add(ref="00AF:0100", mode="change", length=4)
    server.watch_add(ref="00AF:0200", mode="show", length=4)
    cleared = cast(dict[str, Any], server.breakpoint_clear(ref=""))
    assert cleared["status"] == "ok" and cleared["declarations_cleared"] == 2, cleared
    gone = cast(dict[str, Any], server.watch_clear(ref=""))
    assert gone["status"] == "ok" and gone["declarations_cleared"] == 2, gone
    assert dstate.STATE.store is not None and dstate.STATE.store.declarations() == []


def test_a_null_ref_is_the_schemas_refusal() -> None:
    install()
    _refused(_call("breakpoint_clear", {"ref": None}), "bad_argument", "refused by the schema",
             "ref")


# ------------------------------------------------------------------ a scan's cell


class Scanner:
    def __init__(self) -> None:
        self.typed: list[str] = []

    def command(self, text: str, **_: object) -> str:
        self.typed.append(text)
        return "I-> _"


def test_a_value_wider_than_the_open_scans_cell_is_refused_before_mems() -> None:
    s = Scanner()
    dstate.STATE.scan_cell_bytes = 1
    try:
        with pytest.raises(ds.Invalid, match="byte") as e:
            finder.scan_filter(cast(ds.Session, s), "=", 0x100)
    finally:
        dstate.STATE.scan_cell_bytes = None
    assert e.value.code == "bad_argument" and s.typed == []


# ------------------------------------------------------------------ start's plan


def test_a_start_plan_is_judged_whole_before_anything_starts(tmp_path: Path) -> None:
    """A plan is a list of steps like `perform`'s, refused whole before the emulator boots: a
    bad step answered after the boot left a running emulator and a state directory behind."""
    conf = tmp_path / "g.conf"
    conf.write_text("[sdl]\n", encoding="utf-8")
    booted: list[ds.Launch] = []

    def boot(launch: ds.Launch) -> Any:
        booted.append(launch)
        raise ds.Invalid("session_broken", "not starting anything")
    kw: dict[str, Any] = {"conf": str(conf), "cwd": str(tmp_path), "seconds": 60}
    with mock.patch("dosbox_binary.shutil.which", lambda _n: "/somewhere/dosbox-x"), \
         mock.patch("dosbox_x_server.ds.Session", boot):
        _refused(server.start(**kw, plan=[{"op": "nope"}]), "bad_argument", "nope")
        _refused(server.start(**kw, plan=[{"op": "registers"}], plan_wait=-1), "bad_argument",
                 "wait")
        assert booted == [] and not (tmp_path / "save").exists()
        # the control: a plan of the rule reaches the boot
        _refused(server.start(**kw, plan=[{"op": "registers"}]), "session_broken")
    assert len(booted) == 1
