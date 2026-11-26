"""The namer over the confirmed base, and the switch that silences it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import clean_session, install  # noqa: F401
from scry_core.knowledge import Base
from scry_core.naming import Guarded, Named

from scry_dosbox_x import knowledge, naming, server
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as sym

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "fixtures" / "knowledge" / "names"
EXAMPLES = ROOT.parent / "docs" / "reference" / "examples.json"


@pytest.fixture
def sample() -> naming.DosboxNamer:
    """A namer over a base that holds ports and a vector, which the confirmed base does not yet."""
    return naming.DosboxNamer(Base.load(SAMPLE))


def test_an_interrupt_is_named_by_its_function() -> None:
    named = naming.interrupt_call(knowledge.base(), 0x21, {"AX": 0x4C00})
    assert named is not None and (named.name, named.number) == ("terminate with code", "0x21/0x4C")


def test_int_43h_is_not_the_xms_driver() -> None:
    base = knowledge.base()
    assert base.get("call", "0x43/0x08", knowledge.SCOPE) is not None
    assert naming.interrupt_call(base, 0x43, {"AH": 0x08}) is None


def test_an_interrupt_breakpoint_names_the_call_it_waits_for() -> None:
    got = naming.NAMER.arguments("breakpoint_interrupt", {"number": "0x21", "ah": "0x4C"})
    assert got["number"] == Named("call", "terminate with code", "0x21/0x4C",
                                  id="ibm-pc:call:0x21/0x4C")


@pytest.mark.parametrize("given", [{"number": "0x21"}, {"number": "0x43", "ah": "0x08"},
                                   {"number": "0x21", "ah": "0x72"}, {"number": 99999, "ah": 1}])
def test_an_interrupt_breakpoint_that_names_no_call_names_nothing(given: dict[str, Any]) -> None:
    assert naming.NAMER.arguments("breakpoint_interrupt", given) == {}



def test_a_port_is_named_for_the_direction_of_the_call(sample: naming.DosboxNamer) -> None:
    write = sample.arguments("port", {"method": "write", "port": "0x3C8", "value": 1})["port"]
    read = sample.arguments("port", {"method": "read", "port": 0x3C8})["port"]
    assert (write.name, read.name) == ("dac write index", "dac read index")
    assert write.number == "0x03C8"


def test_a_reply_names_the_port_and_the_vector_it_shows(sample: naming.DosboxNamer) -> None:
    read = sample.reply("port", {"port": "0x03C8", "bits": 8, "value": "0x28"})
    assert [(p, n.name, n.number) for p, n in read] == [("port", "dac read index", "0x03C8")]
    written = sample.reply("port", {"port": "0x03C8", "bits": 8, "value": "0x01",
                                    "readback": {"available": False}})
    assert [n.name for _, n in written] == ["dac write index"]
    vectors = sample.reply("interrupt_vectors", {"vectors": [{"number": "0x33"},
                                                             {"number": "0x34"}]})
    assert [(p, n.name) for p, n in vectors] == [("vectors[].number", "mouse driver")]


def test_a_number_the_base_does_not_hold_is_not_named(sample: naming.DosboxNamer) -> None:
    assert sample.reply("port", {"port": "0x0061"}) == []
    assert sample.reply("registers", {"port": "0x03C8"}) == []


def _place(symbols: list[sym.Symbol], base: int = 0x8DF0) -> None:
    dstate.STATE.install_table(symbols)
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": base})


def test_a_symbol_typed_as_a_ref_is_named_with_the_address_the_table_places_it_at() -> None:
    install()
    _place([sym.Symbol("score", 0x615)])
    got = naming.NAMER.arguments("read_memory", {"ref": "score", "length": 2})
    assert got == {"ref": Named("symbol", "score", "0x00009405")}


@pytest.mark.parametrize("ref", ["08DF:0615", "nothing", "0x615", "", "   "])
def test_a_ref_that_is_no_symbol_of_the_table_names_nothing(ref: str) -> None:
    install()
    _place([sym.Symbol("score", 0x615)])
    assert naming.NAMER.arguments("read_memory", {"ref": ref}) == {}


def test_a_symbol_the_table_gives_twice_or_in_sections_names_nothing() -> None:
    install()
    _place([sym.Symbol("score", 0x615), sym.Symbol("score", 0x700)])
    assert naming.NAMER.arguments("read_memory", {"ref": "score"}) == {}
    _place([sym.Symbol("score", 0x615)])
    dstate.STATE.section_bases[1] = 0x1000
    assert naming.NAMER.arguments("read_memory", {"ref": "score"}) == {}


def test_a_tool_that_takes_no_address_names_no_ref() -> None:
    install()
    _place([sym.Symbol("score", 0x615)])
    assert naming.NAMER.arguments("log", {"ref": "score"}) == {}


class _NoCall:
    """A session that fails on any call: the namer may read memory and nothing else."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the namer asked the emulator for {name}")


def test_the_namer_asks_the_emulator_for_nothing_over_every_example() -> None:
    install()
    dstate.STATE.session = cast(Any, _NoCall())
    _place([sym.Symbol("score", 0x615)])
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    assert examples, "INVALID: no example was read"
    for tool, one in examples.items():
        naming.NAMER.arguments(tool, one["call"])
        naming.NAMER.reply(tool, one["reply"])


def test_the_guard_counts_a_namer_that_fails_and_leaves_the_reply_alone() -> None:
    class Broken:
        def arguments(self, tool: str, given: Any) -> Any:
            raise RuntimeError("no")

        def reply(self, tool: str, reply: Any) -> Any:
            raise RuntimeError("no")

    guard = Guarded(Broken())
    assert guard.arguments("port", {}) == {}
    assert guard.failed() == {"count": 1, "last": "RuntimeError: no"}


def _reply_to_an_exit_breakpoint() -> dict[str, Any]:
    return cast(dict[str, Any], server.breakpoint_interrupt(number="0x21", ah="0x4C"))


def test_a_reply_names_the_call_its_arguments_state() -> None:
    install()
    named = _reply_to_an_exit_breakpoint()["names"]
    assert named == [{"field": "given.number", "number": "0x21/0x4C", "kind": "call",
                      "name": "terminate with code", "id": "ibm-pc:call:0x21/0x4C"}]


def test_with_the_names_off_a_reply_has_no_names() -> None:
    install()
    dstate.STATE.names = False
    try:
        assert "names" not in _reply_to_an_exit_breakpoint()
    finally:
        dstate.STATE.names = True


def test_start_takes_the_switch_and_a_refused_start_leaves_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dosbox_x_server_support import _start_on_a_booted_fake
    monkeypatch.setattr(dstate.STATE, "names", True)
    first = _start_on_a_booted_fake(tmp_path, monkeypatch, names=False)
    assert first["status"] == "ok", first
    assert dstate.STATE.names is False
    again = _start_on_a_booted_fake(tmp_path, monkeypatch, names=True)
    assert again["code"] == "session_live" and dstate.STATE.names is False, again


def test_the_switch_is_a_key_of_a_start_profile() -> None:
    assert "names" in server._PROFILE_KEYS and server._START_DEFAULTS["names"] is True


def test_status_counts_what_is_served_and_what_is_held_back() -> None:
    install()
    base = knowledge.base()
    got = cast(dict[str, Any], server.status())
    assert got["knowledge"] == {"served": len(base), "held_back": base.held_back}
    assert "names_failed" not in got


def test_status_says_a_namer_failed_and_no_reply_does(monkeypatch: pytest.MonkeyPatch) -> None:
    install()
    monkeypatch.setattr(naming.GUARD, "_count", 0)
    monkeypatch.setattr(naming.GUARD, "_last", "")

    def broken(tool: str, given: Any) -> Any:
        raise RuntimeError("no")

    monkeypatch.setattr(naming.NAMER, "arguments", broken)
    assert "names" not in _reply_to_an_exit_breakpoint()
    got = cast(dict[str, Any], server.status())
    assert got["names_failed"]["last"] == "RuntimeError: no" and got["names_failed"]["count"] > 0
