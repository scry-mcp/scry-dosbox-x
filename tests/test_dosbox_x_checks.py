"""The pre-gate checks (`dosbox_checks`), by the words a caller acts on: each refusal names the
argument it refuses, the value it got and the bound it holds, and a default a step may leave out
is one the tool would take. Driven through `check` and `preflight`, the two doors the server
and a sequence use."""

from __future__ import annotations

from typing import Any

import pytest

import dosbox_checks as checks
import dosbox_session as ds
import dosbox_x_server  # noqa: F401  (registers the step vocabulary the list checks read)


def _refused(tool: str, **given: Any) -> str:
    with pytest.raises(ds.Invalid) as refused:
        checks.check(tool, **given)
    assert refused.value.code == "bad_argument", refused.value.code
    return str(refused.value)


@pytest.mark.parametrize(("tool", "given", "starts"), [
    ("drive", {"act": [{"op": "status"}], "pattern": ""},
     "pattern is a non-empty regular expression ('.' for every line)"),
    ("drive", {"act": []}, "act is a non-empty LIST of steps"),
    ("log", {"pattern": "", "channel": "guest"},
     "pattern is a non-empty regular expression ('.' for every line)"),
    ("log_wait", {"pattern": "", "channel": "guest"},
     "pattern is a non-empty regular expression ('.' for every line)"),
    ("palette", {"first": "zz"}, "first='zz'"),
    ("perform", {"steps": "x"}, "steps is a LIST of steps ({'op': <name>, ...}); got 'x'"),
    ("start", {"plan": "x"}, "plan is a LIST of steps"),
    ("run_for", {"milliseconds": -1}, "milliseconds=-1 is not a whole number"),
    ("run_for", {"frames": -1}, "frames=-1"),
    ("scan", {"method": "filter", "operator": "=", "value": "zz"}, "value='zz'"),
    ("set_register", {"name": "eax", "value": "zz"}, "value='zz'"),
    ("screen_signature", {"crop": [1, 2]}, "crop=[1, 2]"),
    ("screen_view", {"crop": [1, 2]}, "crop=[1, 2]"),
    ("symbols_load", {"path": "/abs/x.map", "base": "zz"}, "base is 'zz'"),
    ("write", {"ref": "0000:0000", "data_hex": "zz"}, "data_hex='zz'"),
    ("send_mouse", {"target": "t", "x": 1},
     "`target` names where the pointer goes: give it, or `x` and `y`, not both"),
])
def test_a_refusal_opens_with_the_argument_it_refuses(
        tool: str, given: dict[str, Any], starts: str) -> None:
    said = _refused(tool, **given)
    assert said.startswith(starts), said


@pytest.mark.parametrize(("tool", "given", "holds"), [
    ("log", {"pattern": ".", "channel": "emulator", "since_mark": -1}, "for the emulator channel"),
    ("log_wait", {"pattern": ".", "channel": "emulator", "since_mark": -1},
     "for the emulator channel"),
    ("palette", {"first": "0x100"}, "first=256 is not a whole number from 0 to 255"),
    ("palette", {"count": 257}, "count=257 is not a whole number from 0 to 256"),
    ("palette", {"first": 200, "count": 100},
     "first=200 and count=100 reach entry 299: the DAC holds entries 0 to 255"),
    ("run_for", {"milliseconds": 2 ** 53 + 1}, "floating-point clock"),
    ("run_for", {"milliseconds": 1, "frames": 1}, "exactly one of milliseconds and frames"),
    ("start", {"settle_seconds": 5},
     "`settle_seconds` bounds the waits of a `plan`, and there is no plan"),
    ("symbols_load", {"path": "/abs/x.map", "base": "0x0", "section_bases": {"a": "0x0"}},
     "`base` and `section_bases` are the two kinds of table"),
    ("write", {"ref": "0000:0000", "data_hex": ""}, "data_hex is empty: nothing to write"),
    ("send_keys", {"keys": ["a"], "seconds": 5},
     "`seconds` bounds the wait for the guest's reaction, and without `expect` there is no "
     "reaction to wait for"),
    ("send_keys", {"keys": []}, "send_keys needs at least one key name"),
    ("send_mouse", {"target": "t", "units": "mouse"}, "`target` goes with units 'screen'"),
    ("send_mouse", {"x": -1, "y": 0}, "`x` is a whole number from 0 to 32767, in `units`; got -1"),
    ("send_mouse", {"x": 0, "y": -1}, "`y` is a whole number from 0 to 32767, in `units`; got -1"),
    ("send_mouse", {"target": 5}, "target is a control's name on the screen `map_find` matched; "
                                  "got 5"),
])
def test_a_refusal_names_the_value_and_the_bound(
        tool: str, given: dict[str, Any], holds: str) -> None:
    said = _refused(tool, **given)
    assert holds in said, said


def test_a_unit_the_mouse_does_not_know_is_explained_whole() -> None:
    said = _refused("send_mouse", x=0, y=0, units="bogus")
    assert said.endswith("`screen` counts cells in a text mode and pixels in a graphics one, as "
                         "`screen_view` does; `mouse` the driver's own coordinates"), said


def test_the_clock_bound_and_the_one_of_two_rule_let_the_edges_through() -> None:
    checks.check("run_for", milliseconds=2 ** 53)
    checks.check("run_for", milliseconds=1)
    checks.check("run_for", frames=1)


def test_a_scan_step_without_a_cell_size_is_judged_one_byte_a_cell() -> None:
    """A step judged by the preflight with an argument left out is judged as the tool would run
    it, with its own default: one byte a cell, so a length of 3 is whole cells and passes, and a
    cell size named that does not divide it is refused."""
    checks.preflight("scan", {"method": "start", "ref": "0000:0000", "length": 3})
    with pytest.raises(ds.Invalid):
        checks.preflight("scan", {"method": "start", "ref": "0000:0000", "length": 3,
                                  "cell_bytes": 2})


def test_a_step_whose_keys_are_not_a_list_is_refused_naming_keys() -> None:
    with pytest.raises(ds.Invalid) as refused:
        checks.preflight("send_keys", {"keys": "enter"})
    assert str(refused.value).startswith("keys is a LIST of names"), refused.value
