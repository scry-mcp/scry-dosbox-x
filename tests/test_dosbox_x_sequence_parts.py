"""The small parts a sequence is built of, each against its whole answer: how a stop is counted,
the recorded stop's guard, and the two verify blocks a step reads its reaction with. Whole
dictionaries, because a key renamed is a reply a caller can no longer read."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

import dosbox_inputs as inputs
import dosbox_running as guest
import dosbox_sequence as seq
import dosbox_session as ds
import dosbox_state as st


@pytest.mark.parametrize(("attribution", "key"), [
    ({"attributed": True, "ref": "_tick", "by": "symbol", "at": "0814:00000106"},
     "breakpoint _tick (by symbol)"),
    ({"attributed": True, "ref": "_tick", "by": "run_to", "at": "0814:00000106"},
     "run_to's target _tick"),
    ({"attributed": False, "at": "0814:0000010A", "why": "none"},
     "no declared code breakpoint: the debugger keeps no hit flag and a memory watch stops at "
     "the instruction that wrote, so which declaration fired cannot be told"),
    ({"attributed": False, "at": "0814:0106", "retrace_pending": True},
     "most likely the retrace stop a `run_for` left armed: no declared code breakpoint"),
], ids=["declared", "run_to", "unattributed", "retrace"])
def test_a_stop_is_counted_under_its_cause_without_the_address(attribution: dict[str, Any],
                                                               key: str) -> None:
    """One declaration is one key wherever it stopped the machine: the address is the part of
    `cause` that varies, and the rest names the declaration or why none can be named."""
    cause = st.cause(attribution)
    assert attribution["at"] in cause and seq._cause_key({"cause": cause}) == key


def test_a_recorded_stop_whose_read_refuses_keeps_the_record(
        monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = {"stop_seq": 3, "pc": "0814:00000106"}

    def refuse(_session: Any, _recorded: Any) -> Any:
        raise ds.Invalid("unexpected_answer", "a cut pane")

    monkeypatch.setattr(guest, "recorded_stop_reply", refuse)
    got = seq._recorded_stop(cast(ds.Session, SimpleNamespace()), recorded)
    assert got == {**recorded, "enrichment": {"available": False, "why": "a cut pane"}}
    session = SimpleNamespace()
    monkeypatch.setattr(guest, "recorded_stop_reply",
                        lambda s, r: {**r, "regs": {}, "same_session": s is session})
    assert seq._recorded_stop(cast(ds.Session, session), recorded) == {
        **recorded, "regs": {}, "same_session": True}


def _since(lines: list[str] | ds.Invalid, mark: int = 0) -> ds.Session:
    def e9_since_mark(asked: int) -> list[str]:
        assert asked == mark, f"read since {asked}, not the step's mark {mark}"
        if isinstance(lines, ds.Invalid):
            raise lines
        return lines
    return cast(ds.Session, SimpleNamespace(e9_since_mark=e9_since_mark))


def test_the_verify_at_a_stop_answers_whole_in_each_of_its_three_cases() -> None:
    expect = "KEY L"
    none = seq._verify_at_a_stop(_since(["BOOT"]), expect, 0)
    assert none == {"checked": True, "seen": False, "expected": expect, "waited_s": 0.0,
                    "lines_on_disk": 1, "why": none["why"]} and "STOPPED" in none["why"], none
    lines = ["BOOT", "STUB . key KEY L", "after"]
    seen = seq._verify_at_a_stop(_since(lines, mark=7), expect, 7)
    assert seen == inputs.verify_block(expect, {
        "verdict": "TARGET", "line": lines[1], "already": True, "lines_before": 1,
        "waited_s": 0.0, "lines_total": 1}), seen
    refused = seq._verify_at_a_stop(_since(ds.Invalid("no_channel", "no logfile")), expect, 0)
    assert refused == {"checked": False, "expected": expect, "why": "no logfile",
                       "code": "no_channel"}


def test_the_verify_after_a_wait_answers_whole_when_the_machine_stops_or_refuses(
        monkeypatch: pytest.MonkeyPatch) -> None:
    expect = "KEY L"
    observed: list[Any] = []
    monkeypatch.setattr(guest, "observe_stop", observed.append)

    asked: list[Any] = []

    def waiting(raised: ds.Invalid) -> ds.Session:
        def e9_wait(*a: Any, **k: Any) -> Any:
            asked.append((a, k))
            raise raised
        return cast(ds.Session, SimpleNamespace(e9_wait=e9_wait))

    stopped = ds.E9Stopped("the machine is at the debugger", waited_s=0.4, arrived=2)
    session = waiting(stopped)
    got = seq._verify_after_wait(session, expect, 1.0, 7)
    (args, kw), = asked
    assert args == (inputs.program_reaction(expect), 1.0) and kw["mark"] == 7, asked
    assert observed == [session], "the stop the wait met was not recorded for this session"
    assert got == {"checked": True, "seen": False, "expected": expect,
                   "stopped_during_wait": True, "waited_s": 0.4, "lines_on_disk": 2,
                   "why": "the machine is at the debugger"}, got
    refused = seq._verify_after_wait(waiting(ds.Invalid("no_channel", "no logfile")),
                                     expect, 1.0, 0)
    assert refused == {"checked": False, "expected": expect, "why": "no logfile",
                       "code": "no_channel"}
