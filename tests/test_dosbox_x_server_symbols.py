"""The DOSBox-X server: symbol tables, their bases and where a name is placed."""

from __future__ import annotations

import inspect
import shutil
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from dosbox_x_server_support import (  # noqa: E402
    ILINK32_BASES,
    ILINK32_MAP,
    MEASURED_BASE,
    NM_FRAGMENT,
    SELINFO_ZEROED,
    TLINK_TEXT,
    FakeSession,
    NamesFake,
    _loaded_then_restored,
    _names,
    _ok,
    _protected_table,
    _source,
    clean_session,  # noqa: E402, F401
    install,
)

from scry_dosbox_x import arming, inputs, placement, server
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x import symbols as dsym


def test_log_passes_the_callers_pattern_limit_and_channel_through() -> None:
    s = install()
    server.log(channel="guest", pattern="PERF", limit=7)
    assert s.log_calls == [("PERF", 7, "guest")]


def test_the_base_is_measured_off_the_machine_and_not_assumed(tmp_path: Path) -> None:
    """The one fact a symbol file cannot be built without, and the one place it lives."""
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "ok", got
    assert got["base"] == MEASURED_BASE, got
    assert got["limit"] == 0x0009FFFF, got
    assert got["base_from"] == "CS", got


def test_the_base_is_read_from_this_commands_echo_and_not_the_first_on_screen(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base_from="DS"))
    assert got["base"] == MEASURED_BASE, got
    assert got["base"] != 0x00008240, "it answered with the stack selector's base"


def test_an_explicit_base_reports_no_limit_rather_than_inventing_one(
        tmp_path: Path) -> None:
    install()
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base="100000"))
    assert got["base"] == 0x00100000, got
    assert got["limit"] == -1, got
    assert got["base_from"] == "caller", got


def test_every_parsed_symbol_is_accounted_for_in_the_reply(tmp_path: Path) -> None:
    """The counts are what a caller reads INSTEAD of the names, so they must sum."""
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["parsed"] == 4, got
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["unencodable_total"]) == got["parsed"], got
    assert got["excluded_sections"] == 1, got
    assert got["truncated_names"] == 1, got    # `_engine_load_midi` is 17 characters


def test_the_accounting_still_sums_when_the_unencodable_list_is_truncated(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    text = "".join(f"0000{i:04x} T _caf\u00e9{i}\n" for i in range(12)) + "00009999 T _ok\n"
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path, text)))
    assert got["parsed"] == 13, got
    assert got["unencodable_total"] == 12, got
    assert len(got["unencodable"]) == 8, "the list is capped, which is the point"
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["unencodable_total"]) == got["parsed"], got


def test_loaded_is_read_back_out_of_the_debugger_and_lv_appends(
        tmp_path: Path) -> None:
    """`ok` is not evidence: this emulator prints it for a filename it truncated."""
    install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src))
    assert first["loaded"] == first["kept"] == 3, first
    second = cast(dict[str, Any], server.symbols_load(path=src))
    assert second["kept"] == 3, second
    assert second["loaded"] == 6, second


def test_the_bytes_that_went_in_carry_the_measured_linear_address(
        tmp_path: Path) -> None:
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert ("_main", 0x0056DF20) in s.loaded, s.loaded


def test_a_source_that_is_not_a_symbol_list_is_refused_by_name(tmp_path: Path) -> None:
    install()
    src = _source(tmp_path, "make: *** No rule to make target 'all'.  Stop.\n")
    got = cast(dict[str, Any], server.symbols_load(path=src))
    assert got["status"] == "INVALID", got
    assert "djgpp32.sym" in got["message"], got
    assert "session" in got, got


def test_a_register_this_debugger_does_not_report_is_refused_not_sent(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   base_from="AX"))
    assert got["status"] == "INVALID", got
    assert "ZEROED" in got["message"], got


def test_a_pattern_narrows_by_the_full_name(tmp_path: Path) -> None:
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                   pattern="^_engine"))
    assert got["kept"] == 2, got
    assert got["excluded_pattern"] == 1, got   # `_main`; `.text` is a section


def test_an_overlay_symbol_reaches_the_caller_flagged_and_counted(tmp_path: Path)\
        -> None:
    """CONDITIONALITY AT THE BOUNDARY, which is the only place it is worth anything."""
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base="1000"))
    assert got["status"] == "ok", got
    assert got["kept"] == 2, got
    assert got["overlay_idle"] == 1, got
    # A SUBSET AND NOT A BUCKET: the counts above still partition `parsed`, so a caller
    # checking the accounting is not told a symbol went missing.
    assert (got["kept"] + got["excluded_sections"] + got["excluded_pattern"]
            + got["excluded_unplaceable"] + got["unencodable_total"]
            == got["parsed"] == 2), got

    flagged = cast(dict[str, Any], server.symbols_find(name="ACTIVEIMAN"))
    assert flagged["symbols"][0]["idle"] is True, flagged
    # THE CONTROL, without which `idle: True` hardcoded satisfies the line above.
    plain = cast(dict[str, Any], server.symbols_find(name="ACTIVE_CLS"))
    assert plain["symbols"][0]["idle"] is False, plain
    # AND THE OTHER BRANCH of the same tool, which builds its reply separately.
    linear = f"{0x1000 + 0x0D74 * 16 + 0x00E21:X}"
    by_addr = cast(dict[str, Any], server.symbols_find(linear=linear))
    assert by_addr["name"] == "ACTIVEIMAN" and by_addr["idle"] is True, by_addr


def test_an_nm_table_is_reported_with_no_overlay_symbols(tmp_path: Path) -> None:
    install(mode="Pr32")
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["overlay_idle"] == 0, got
    found = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert found["symbols"][0]["idle"] is False, found


def test_a_32_bit_map_reaches_the_caller_through_the_tool(tmp_path: Path) -> None:
    install()
    src = ILINK32_MAP
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases=ILINK32_BASES))
    assert got["status"] == "ok", got
    assert got["kept"] == 4 and got["unreadable"] == 0, got
    assert got["overlay_idle"] == 1, got

    at = {}
    for name, offset in (("_main", 0x130), ("_errno", 0x2090)):
        found = cast(dict[str, Any], server.symbols_find(name=name))
        one = found["symbols"][0]
        assert one["offset"] == offset, one
        assert one["idle"] is False, one
        at[name] = (one["section"], int(one["addr"], 16))
    assert at == {"_main": (1, 0x00401130), "_errno": (2, 0x00425090)}, at


def test_a_sectioned_map_refuses_a_section_the_caller_did_not_position(
        tmp_path: Path) -> None:
    install()
    src = ILINK32_MAP
    # THE TOOL DECORATOR TRANSLATES A REFUSAL INTO A REPLY rather than letting it
    # escape, which is the whole reason `Invalid` exists as its own type -- so the
    # assertion is on the reply, not on an exception.
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x401000", "3": "0x4289B8"}))
    assert got["status"] != "ok", got
    assert "section 2" in str(got["message"]), got["message"]
    assert "_errno" in str(got["message"]), got["message"]


def test_section_bases_keys_arrive_as_json_strings_and_are_read_as_numbers(
        tmp_path: Path) -> None:
    """JSON HAS NO INTEGER KEYS, so the table reaches this tool keyed on `"1"`."""
    install()
    src = ILINK32_MAP
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"0x1": "0x401000", "2": "0x423000", "3": "0x4289B8"}))
    assert got["kept"] == 4, got
    # AND A KEY THAT IS NOT A NUMBER IS REFUSED rather than silently dropped, because a
    # dropped key is a section that then reads as unpositioned.
    bad = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"_TEXT": "0x401000"}))
    assert bad["status"] != "ok", bad
    assert "section indices" in str(bad["message"]), bad["message"]


# ------------------------------------------------------------- finding one again

def test_find_refuses_before_anything_is_loaded() -> None:
    install()
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "INVALID", got
    assert "no symbol table" in got["message"], got


def test_find_by_linear_takes_the_base_back_off(tmp_path: Path) -> None:
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.symbols_find(linear="0056DF24"))
    assert got["name"] == "_main", got
    assert got["delta"] == 4, got


def test_find_by_linear_takes_hex_text_and_refuses_a_number(tmp_path: Path) -> None:
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    prefixed = cast(dict[str, Any], server.symbols_find(linear="0x56DF24"))
    assert prefixed["name"] == "_main" and prefixed["delta"] == 4, prefixed
    for bad in (0x0056DF24, "56DFZZ", "-56DF24"):
        got = cast(dict[str, Any], server.symbols_find(linear=bad))
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
        assert "linear is" in got["message"], got["message"]


def test_the_table_is_forgotten_when_the_session_goes(tmp_path: Path) -> None:
    """THE STALE-BASE GUARD, and it is the reason the table is cleared at all."""
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert cast(dict[str, Any], server.symbols_find(name="_main"))["status"] == "ok"
    server.close()
    got = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert got["status"] == "INVALID", got
    assert dstate.STATE.table == [], "the table outlived the session it was measured on"


def test_a_session_that_died_on_its_bound_takes_the_table_with_it(
        tmp_path: Path) -> None:
    """THE MOST DANGEROUS OF THE THREE CLEARING SITES, and the one no test reached."""
    s = install()
    server.symbols_load(path=_source(tmp_path))
    s._alive = False                      # what a bound expiring looks like from here
    got = cast(dict[str, Any], server.symbols_find(linear="0056DF24"))
    assert got["code"] == "session_broken", got
    server.close()
    assert dstate.STATE.table == [], "the table outlived the process it was measured on"


def test_a_new_session_does_not_inherit_the_previous_ones_table(
        tmp_path: Path) -> None:
    """The second untested site."""
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    assert dstate.STATE.table, "precondition: a table is installed"
    s._alive = False                    # the previous session's bound has expired
    server.start(conf=str(tmp_path / "nope.conf"), cwd=str(tmp_path), session_seconds=30)
    assert dstate.STATE.table == [], (
        "a new session inherited the previous one's table, so `symbols_find` would add "
        "a dead program's base to its offsets")


def test_a_start_refused_because_a_session_is_live_keeps_the_table(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    got = cast(dict[str, Any], server.start(conf=str(tmp_path / "x.conf"),
                                            cwd=str(tmp_path), session_seconds=30))
    assert got["status"] == "INVALID" and "already live" in got["message"], got
    assert cast(dict[str, Any],
                server.symbols_find(name="_main"))["status"] == "ok"


def test_a_selector_number_places_a_table_at_a_real_mode_stop(tmp_path: Path) -> None:
    s = FakeSession()                                       # real mode
    dstate.STATE.session = s                                # type: ignore[assignment]
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path), base_from="00af"))
    assert got["status"] == "ok" and got["base"] == MEASURED_BASE, got
    assert "SELINFO 00AF" in s.executed, s.executed
    assert dstate.STATE.base_measured_from == "00AF", dstate.STATE.base_measured_from
    for refused in ("ZZZZ", "12345", ""):
        bad = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path), base_from=refused))
        assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", (refused, bad)


def test_a_real_mode_map_with_no_base_is_refused_before_selinfo_is_asked(
        tmp_path: Path) -> None:
    class RealModeProgram(FakeSession):
        asked: list[str] = []

        def selector(self, reg: str) -> dict[str, int]:
            self.asked.append(reg)
            return ds.Session.selector(self, reg)      # type: ignore[arg-type]

    s = RealModeProgram()
    s.asked = []
    dstate.STATE.session = s                                # type: ignore[assignment]
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "real mode" in got["message"].lower() and "`base`" in got["message"], got
    assert "* 16" in got["message"], got
    assert s.asked == [], "SELINFO was asked in real mode"
    pr16 = FakeSession(mode="Pr16")
    dstate.STATE.session = pr16                             # type: ignore[assignment]
    measured = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert measured["status"] == "ok" and measured["base"] == MEASURED_BASE, measured


def test_an_absent_descriptor_is_refused_rather_than_placed_at_base_zero(
        tmp_path: Path) -> None:
    """THE GUARD THAT MATTERS MOST, because its failure mode is silent and plausible."""
    class Unset(FakeSession):
        """The double with the zeroed descriptor, on a protected-mode pane."""

        def where(self) -> dict[str, str]:
            return {"cs": "00A7", "eip": "00000000", "mode": "Pr32"}

        def exec(self, command: str, seconds: float | None = None) -> tuple[bool, list[str]]:
            return True, SELINFO_ZEROED

    s = Unset()
    dstate.STATE.session = s                                # type: ignore[assignment]
    got = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert got["status"] == "INVALID", got
    assert "no present descriptor" in got["message"], got
    assert "raw offset" in got["message"], got

    # AND THE CONTROL: an explicit base still goes through on that same machine, so the
    # refusal is about the DESCRIPTOR and not a helper that refuses everything.
    ok = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                  base="F0000"))
    assert ok["status"] == "ok", ok
    assert ("_main", 0x000F0000 + 0x0016DF20) in s.loaded, s.loaded


def test_a_failed_load_does_not_replace_a_table_that_was_working(
        tmp_path: Path) -> None:
    """A REFUSAL THAT ALSO CORRUPTS STATE inverts this module's one rule."""
    s = install(mode="Pr32")
    server.symbols_load(path=_source(tmp_path))
    good = cast(dict[str, Any], server.symbols_find(name="_main"))["symbols"][0]

    def refuse(data: bytes) -> list[tuple[str, int]]:
        raise ds.Invalid("unexpected_answer", "the debugger did not acknowledge it")

    s.load_symbols = refuse                     # type: ignore[method-assign]
    other = _source(tmp_path, "00001000 T _somebody_elses_main\n")
    bad = cast(dict[str, Any], server.symbols_load(path=other))
    assert bad["status"] == "INVALID", bad
    still = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert still["status"] == "ok", still
    assert still["symbols"][0] == good, "a refused load replaced a working table"


def test_the_descriptor_type_is_reported_so_a_caller_can_see_what_was_read(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    measured = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path)))
    assert measured["descriptor"] == 0x1B, measured
    given = cast(dict[str, Any], server.symbols_load(path=_source(tmp_path),
                                                     base="1000"))
    assert given["descriptor"] == -1, given


def test_a_limit_means_nothing_where_one_symbol_comes_back_and_is_not_refused_there(
) -> None:
    install(alive=True)
    dstate.STATE.install_table([dsym.Symbol(name="_main", offset=0x1000, kind="T"),
                                dsym.Symbol(name="_next", offset=0x2000, kind="T")])
    dstate.STATE.base.update(base=0x10000)
    try:
        zero = cast(dict[str, Any], server.symbols_find(offset=0x1004, limit=0))
        assert zero["status"] == "ok", zero
        assert zero["name"] == "_main"
        # AND IT IS STILL REFUSED WHERE IT MEANS SOMETHING, or this would have moved
        # the defect rather than fixed it.
        bad = cast(dict[str, Any], server.symbols_find(name="_ma", limit=0))
        assert bad["status"] == "INVALID", bad
        assert "would return nothing" in str(bad["message"])
        # AND A CEILING, because a `limit` with no top hands a whole table back under the
        # name of a lookup. The ceiling itself is taken, one past it refused,
        # and the offset branch, which never reads `limit`, is still not corrected about it.
        top = cast(dict[str, Any], server.symbols_find(name="_", limit=placement.SYMBOLS_LIMIT_MAX))
        assert top["status"] == "ok" and top["symbols_total"] == 2, top
        over = cast(dict[str, Any],
                    server.symbols_find(name="_", limit=placement.SYMBOLS_LIMIT_MAX + 1))
        assert over["status"] == "INVALID", over
        assert f"1..{placement.SYMBOLS_LIMIT_MAX}" in str(over["message"]), over
        fine = cast(dict[str, Any], server.symbols_find(offset=0x1004, limit=10 ** 6))
        assert fine["status"] == "ok", fine
    finally:
        dstate.STATE.forget_symbols()


def test_a_bad_pattern_is_a_refusal_and_not_a_traceback(tmp_path: Path) -> None:
    install(alive=True)
    src = tmp_path / "s.nm"
    src.write_text("00001000 T _main\n00002000 T _next\n", encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base="10000",
                                                   pattern="(unclosed"))
    assert got["status"] == "INVALID", got
    assert "not a usable pattern" in str(got["message"])
    assert "session" in got, "an INVALID reply must still carry the session block"
    # AND IT DOES NOT BLAME THE FILE. `BadSymbolText`'s translation prefixes the
    # caller's path, which is right for text that would not parse and wrong for an
    # argument typed at the tool: a refusal reading
    # `INVALID: /path/to/s.nm: that is not a usable pattern` names a file that is
    # perfectly readable and was read.
    assert str(src) not in str(got["message"]), (
        f"the refusal names the source file for a defect in the PATTERN: "
        f"{got['message']}")
    # THE GREEN BESIDE IT: a pattern that compiles still works, or this passes over a
    # `plan` that refuses every pattern.
    ok = cast(dict[str, Any], server.symbols_load(path=str(src), base="10000",
                                                  pattern="^_ma"))
    assert ok["status"] == "ok", ok
    # A LIMIT, SAID OUT LOUD: this asks whether the field has a ROW, not whether what is
    # written beside it is true. It catches a field going UNDESCRIBED; it cannot catch
    # one being described wrongly.


def test_read_memory_refuses_an_offset_that_will_not_fit_the_command() -> None:
    fake = install()
    got = cast(dict[str, Any], server.read_memory(ref="0000:00010000"))
    assert got["status"] == "INVALID", got
    # The ceiling is mode-aware; in the real mode this double reports, 0x10000 still
    # addresses nothing, and the refusal says so before anything is sent.
    assert "past 0xFFFF addresses nothing" in str(got["message"]), got["message"]
    assert fake.memdump_calls == []

def test_the_caller_is_told_about_every_bucket_the_plan_carries(tmp_path: Path) -> None:
    """CONSERVATION AT THE BOUNDARY, which is the only place it is worth anything."""
    import dataclasses
    # THE THREE THAT TRAVEL BY ANOTHER ROUTE, each named with its reason: `unencodable`
    # goes out truncated to eight PLUS its own length, and `symbols`/`short` are the
    # table itself rather than a number about it.
    carried_otherwise = {"unencodable", "symbols", "short"}
    fields = {f.name for f in dataclasses.fields(dsym.Plan)}
    assert carried_otherwise < fields, f"an exception names no field: {fields}"
    counters = fields - carried_otherwise
    assert "overlay_idle" in counters, counters
    # THE REPLY, NOT THE SOURCE TEXT. Grepping `inspect.getsource(symbols_load)` for
    # `plan.<counter>` is a LEXICAL test of the axis "does the counter reach the caller":
    # `getsource` returns comments and the docstring too, so a counter named in one of
    # this function's (long) comments satisfies it while the key is gone from the returned
    # dict -- and so does `_unused = plan.truncated_names`. The caller then gets a
    # reply whose buckets do not sum to `parsed`, which is the property the docstring
    # says cannot happen.
    #
    # THE FIXTURE IS CHOSEN SO SEVERAL COUNTERS ARE NON-ZERO, because a reply full of
    # zeroes cannot tell a counter that travelled from one that was defaulted.
    install()
    src = tmp_path / "prog.sym"
    src.write_text(NM_FRAGMENT, encoding="utf-8")
    reply = cast(dict[str, Any], server.symbols_load(
        path=str(src), base="0", pattern="^_(keepme|map_demo)"))
    assert reply["status"] == "ok", reply
    plan = dsym.plan(dsym.parse(NM_FRAGMENT)[0], pattern="^_(keepme|map_demo)",
                     unreadable=0)
    # WHICH REPLY KEY CARRIES WHICH BUCKET, declared. Two weaker forms were tried and
    # both are recorded because each looked right:
    #
    #   `f"plan.{c}" in inspect.getsource(symbols_load)` -- LEXICAL. `getsource` returns
    #       comments and the docstring, so a counter named in a comment satisfied it with
    #       the key gone from the reply, and so did `_unused = plan.truncated_names`.
    #   `getattr(plan, c) in reply.values()` -- VALUE MEMBERSHIP, which is identity's
    #       opposite: it asks whether that NUMBER appears anywhere, and on a real fixture
    #       several buckets share a value: deleting the count from the reply
    #       entirely leaves this case GREEN, because some other field happens to hold the
    #       same number.
    #
    # The mapping is a second statement of the reply's shape and could drift, which is
    # why `counters` is derived from the dataclass and the mapping must cover it EXACTLY:
    # a bucket added to `Plan` fails here until somebody says where it goes.
    carries = {
        "parsed": "parsed", "excluded_noise": "excluded_sections",
        "excluded_pattern": "excluded_pattern",
        "excluded_unplaceable": "excluded_unplaceable",
        "truncated_names": "truncated_names",
        "disambiguated": "disambiguated", "renamed": "renamed",
        "unreadable": "unreadable", "overlay_idle": "overlay_idle",
    }
    assert set(carries) == counters, (
        f"the mapping and the dataclass disagree: {set(carries) ^ counters}")
    for field_name, key in carries.items():
        assert key in reply, f"symbols_load's reply has no `{key}`"
        # THE TYPE BEFORE THE VALUE, because `True == 1` and `False == 0`: every counter
        # here is a COUNT, and a bucket that turned into a flag would satisfy the equality
        # below against the 0 or 1 it happens to hold, which is the one drift this loop
        # could not see.
        assert type(reply[key]) is int, (
            f"reply[{key!r}] is {type(reply[key]).__name__}, and a count is an int")
        assert reply[key] == getattr(plan, field_name), (
            f"reply[{key!r}] is {reply[key]!r}, plan.{field_name} is "
            f"{getattr(plan, field_name)!r}")
    # AND THE FIXTURE HAS TO MAKE SEVERAL OF THEM MOVE, or every comparison above is
    # 0 == 0 and a reply of all zeroes would satisfy it.
    non_zero = [c for c in counters if getattr(plan, c)]
    assert len(non_zero) >= 4, f"this fixture leaves too much at zero to tell: {non_zero}"
    # A SECOND READ WITH A DIFFERENT FILTER, and this is the identity axis rather than
    # the presence one. The loop above catches a SWAP between two reply keys only when
    # their values differ, and on any one fixture some buckets coincide: if
    # `excluded_noise` and `excluded_pattern` are both 0, exchanging those two fields in
    # the reply comes back GREEN.
    #
    # Reading the SAME file twice under different `pattern`s moves the buckets by
    # different amounts, so a fixed swap has to survive BOTH vectors to stay invisible.
    other = cast(dict[str, Any], server.symbols_load(
        path=str(src), base="0", pattern="^_dropme"))
    plan2 = dsym.plan(dsym.parse(NM_FRAGMENT)[0], pattern="^_dropme", unreadable=0)
    for field_name, key in carries.items():
        assert other[key] == getattr(plan2, field_name), (
            f"second read: reply[{key!r}] is {other[key]!r}, plan.{field_name} is "
            f"{getattr(plan2, field_name)!r}")
    moved = [k for k in carries.values() if reply[k] != other[k]]
    assert len(moved) >= 3, f"the two reads barely differ, so a swap could hide: {moved}"
    # THE LIMIT, said out loud: two buckets equal in BOTH reads could still be exchanged
    # unseen. What closes that is a third fixture, not a stronger assertion here.
    # AND `unencodable` REACHES THE CALLER ANYWAY, so the exception list cannot become a
    # hiding place: it goes out truncated to eight PLUS its own length.
    assert "unencodable_total" in reply, sorted(reply)


# ------------------------------------- asking a SECTIONED table where you have stopped

def test_a_sectioned_table_answers_a_linear_address_without_being_told_the_section(
        tmp_path: Path) -> None:
    """THE BRANCH A CALLER WHO HAS STOPPED SOMEWHERE ACTUALLY USES."""
    install()
    src = ILINK32_MAP
    server.symbols_load(path=str(src), section_bases=ILINK32_BASES)
    # 0x40113C is 12 bytes past `_main`, which is section 1 offset 0x130.
    got = cast(dict[str, Any], server.symbols_find(linear="40113C"))
    assert got["name"] == "_main" and got["section"] == 1, got
    assert got["delta"] == 0xC, got
    # AND THE OTHER SECTION, at the SAME distance past its own symbol -- which a table
    # that ignored the section index would answer from section 1, because 0x42509C is
    # also above section 1's base.
    other = cast(dict[str, Any], server.symbols_find(linear="42509C"))
    assert other["name"] == "_errno" and other["section"] == 2, other
    assert other["delta"] == 0xC, other


def test_an_offset_alone_is_refused_on_a_sectioned_table(tmp_path: Path) -> None:
    """The sections OVERLAP, so a bare offset exists in every one of them."""
    install()
    src = ILINK32_MAP
    server.symbols_load(path=str(src), section_bases=ILINK32_BASES)
    got = cast(dict[str, Any], server.symbols_find(offset=0x2090))
    assert got["status"] != "ok", got
    assert "SECTIONED" in str(got["message"]), got["message"]
    # WITH THE SECTION NAMED it answers, and the two sections give DIFFERENT symbols for
    # the same offset -- which is the whole reason the bare form is refused.
    one = cast(dict[str, Any], server.symbols_find(offset=0x2090, section=1))
    two = cast(dict[str, Any], server.symbols_find(offset=0x2090, section=2))
    assert (one["name"], one["delta"]) == ("_main", 0x2090 - 0x130), one
    assert (two["name"], two["delta"]) == ("_errno", 0), two


def test_an_address_below_every_section_is_refused_rather_than_folded(
        tmp_path: Path) -> None:
    install()
    src = ILINK32_MAP
    server.symbols_load(path=str(src), section_bases=ILINK32_BASES)
    got = cast(dict[str, Any], server.symbols_find(linear="0x1000"))
    assert got["status"] != "ok", got
    assert "below every section" in str(got["message"]), got["message"]


def test_a_flat_table_refuses_a_question_about_a_section_it_does_not_have(
        tmp_path: Path) -> None:
    install()
    src = tmp_path / "prog.sym"
    src.write_text(NM_FRAGMENT, encoding="utf-8")
    server.symbols_load(path=str(src), base="0")
    got = cast(dict[str, Any], server.symbols_find(offset=0x1c350, section=2))
    assert got["status"] != "ok", got
    assert "loaded FLAT" in str(got["message"]), got["message"]
    # AND WITHOUT IT, the same question answers.
    ok = cast(dict[str, Any], server.symbols_find(offset=0x1c350))
    assert ok["name"] == "_keepme_main", ok


def test_nothing_below_the_asked_offset_names_the_section_it_looked_in(
        tmp_path: Path) -> None:
    install()
    src = ILINK32_MAP
    server.symbols_load(path=str(src), section_bases=ILINK32_BASES)
    got = cast(dict[str, Any], server.symbols_find(offset=0x10, section=1))
    assert got["status"] != "ok", got
    assert "section 1" in str(got["message"]), got["message"]


def test_decide_by_reads_the_shape_of_the_ref() -> None:
    assert placement.decide_by("_uicue_apply") == "symbol"
    assert placement.decide_by("00A7:0016DD80") == "address"


def test_a_bare_linear_address_is_refused_it_has_no_segment() -> None:
    with pytest.raises(ds.Invalid, match="no segment to arm at"):
        placement.parse_seg_off("0x400000")
    assert placement.parse_seg_off("00A7:16DD80") == (0xA7, 0x16DD80)


def test_target_for_takes_the_selector_in_protected_mode_and_the_paragraph_in_real() -> None:
    prot = NamesFake(mode="Pr32", cs="00A7")
    assert placement.target_for(0x16DD80, "CS", prot) == (0xA7, 0x16DD80)  # type: ignore[arg-type]
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0x7DF0, "limit": -1, "type": -1})
    real = NamesFake(mode="Real")
    assert placement.target_for(0x599, "CS", real) == (0x7DF, 0x599)   # type: ignore[arg-type]
    # a high real-mode offset (a data segment) is split so off <= 0xFFFF and folds back.
    seg, off = placement.target_for(0x140E0, "DS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0x7DF0 + 0x140E0 and off <= 0xFFFF


def test_run_to_takes_a_symbol_or_an_address_like_the_readers_do(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_uicue_apply", 0x3D5E0, kind="T"),
                                     dsym.Symbol("twice", 0x10, kind="t"),
                                     dsym.Symbol("twice", 0x20, kind="t")])
    by_name = cast(dict[str, Any],
                   server.run_to(ref="_uicue_apply", control="0000:0020", seconds=5))
    assert by_name["status"] == "ok" and by_name["verdict"] == "TARGET", by_name
    assert fake.runto_calls == [(0xA7, 0x3D5E0, 5)], fake.runto_calls   # CS, the symbol's offset
    # `target` is the SESSION'S spelling, handed back untouched (a second spelling beside
    # the note that quotes the first is two names for one address).
    assert by_name["ref"] == "_uicue_apply" and by_name["target"] == "00A7:3D5E0"
    by_addr = cast(dict[str, Any], server.run_to(ref="F000:0E05", control="0000:0020"))
    assert fake.runto_calls[-1] == (0xF000, 0xE05, 30.0)
    assert by_addr["target"] == "F000:0E05", by_addr
    absent = cast(dict[str, Any], server.run_to(ref="_nobody", control="0000:0020"))
    assert absent["status"] == "INVALID" and "not in the symbol table" in absent["message"], absent
    twice = cast(dict[str, Any], server.run_to(ref="twice", control="0000:0020"))
    assert twice["status"] == "INVALID" and "names 2 symbols" in twice["message"], twice
    empty = cast(dict[str, Any], server.run_to(ref="", control="0000:0020"))
    assert empty["status"] == "INVALID", empty            # not a DeclarationError traceback
    assert len(fake.runto_calls) == 2, "a refused ref must not have run anything"
    # THE OLD SPELLING IS GONE: the numeric pair is not a parameter any more.
    old = cast(dict[str, Any], server.perform(steps=[
        {"op": "run_to", "segment": 0, "offset": 0x10, "control": "0000:0020"}]))
    assert old["status"] == "INVALID" and "bad arguments" in old["message"], old


def test_the_key_vocabulary_is_the_scan_table_s() -> None:
    for name, code in inputs.SCAN_SET1.items():
        seq = inputs.scan_sequence([name], "-")
        assert seq == bytes(code) + bytes(code[:-1]) + bytes([code[-1] | 0x80]), name


def test_run_to_resolves_a_symbolic_control_and_perform_passes_one_through(
        tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("_hot", 0x3D5E0, kind="T")])
    fake.control_hits = 2
    got = cast(dict[str, Any], server.run_to(ref="00A7:00000010", control="_hot", seconds=1))
    assert got["status"] == "ok", got
    assert fake.last_control == (0xA7, 0x3D5E0), fake.last_control   # CS, the symbol's offset
    assert got["control_hits"] == 2 and got["controls"] == [
        {"ref": "_hot", "at": "00A7:3D5E0", "hits_in_run": 2, "removed": True}], got
    out = cast(dict[str, Any], server.perform(
        steps=[{"op": "run_to", "ref": "00A7:00000010", "control": "_hot", "seconds": 1}]))
    assert out["status"] == "ok" and out["steps_completed"] == 1, out
    assert out["ran"][0]["reply"]["control_hits"] == 2, out["ran"][0]


def test_real_mode_placement_at_its_exact_edges() -> None:
    real = NamesFake(mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0xF0000, "limit": -1, "type": -1})
    with pytest.raises(ds.Invalid, match="past the 0xFFFFF"):
        placement.target_for(0x10000, "CS", real)   # type: ignore[arg-type]
    seg, off = placement.target_for(0xFFFF, "CS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0xFFFFF and off <= 0xFFFF, (hex(seg), hex(off))
    dstate.STATE.base.update({"base": 0x10000})
    seg, off = placement.target_for(0x10000, "CS", real)   # type: ignore[arg-type]
    assert seg * 16 + off == 0x20000 and off <= 0xFFFF, (hex(seg), hex(off))


def test_a_symbol_past_the_first_megabyte_is_not_advised_an_explicit_seg_off_in_real_mode() -> None:
    """The debugger wraps a real-mode offset to 16 bits, so no SEG:OFF reaches that high there."""
    real = NamesFake(mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0x8ED00, "limit": -1, "type": -1})
    with pytest.raises(ds.Invalid) as raised:
        placement.target_for(0x1E367C, "DS", real)   # type: ignore[arg-type]
    text = str(raised.value)
    assert "protected-mode stop" in text and "explicit SEG:OFF" not in text, text


def test_a_sectioned_table_places_by_base_says_it_has_no_flat_one_and_counts_what_it_skipped(
        tmp_path: Path) -> None:
    fake = install()
    src = ILINK32_MAP
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x423000", "2": "0x401000", "3": "0x4289B8"}))
    assert got["status"] == "ok" and got["base"] == -1, got
    found = cast(dict[str, Any], server.symbols_find(linear="00423130"))
    assert found["name"] == "_main" and found["delta"] == 0, found
    real = NamesFake(mode="Real")
    with pytest.raises(ds.Invalid, match="FLAT base"):
        placement.target_for(0x10, "CS", real)   # type: ignore[arg-type]
    del fake


def test_a_load_somewhere_else_replaces_the_table_and_its_types(tmp_path: Path) -> None:
    one = tmp_path / "one.nm"
    one.write_text("00001000 D _rate\n         U _undefined\n", encoding="utf-8")
    _names(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=str(one), base="400000"))
    assert first["status"] == "ok" and first["unreadable"] == 1, first
    dstate.STATE.symbol_types["_RATE"] = "u16"           # as a types file would have set it
    again = cast(dict[str, Any], server.symbols_load(path=str(one), base="500000"))
    assert again["table_mode"] == "replaced" and dstate.STATE.symbol_types == {}, again


def test_target_for_refuses_a_real_mode_symbol_that_folds_past_1mb() -> None:
    real = NamesFake(mode="Real")
    dstate.STATE.base.clear()
    dstate.STATE.base.update({"base": 0xF0000, "limit": -1, "type": -1})
    with pytest.raises(ds.Invalid, match="past the 0xFFFFF"):
        placement.target_for(0x20000, "CS", real)   # type: ignore[arg-type]


def test_read_memory_takes_a_symbol_or_a_seg_off_ref(tmp_path: Path) -> None:
    fake = _names(tmp_path, symbols=[dsym.Symbol("g_rate", 0x17A6EC, kind="d")], ds_="00AF")
    fake.mem[(0x00AF, 0x17A6EC)] = bytes.fromhex("00112233")
    by_name = cast(dict[str, Any], server.read_memory(ref="g_rate", length=4))
    assert by_name["status"] == "ok" and by_name["seg_off"].startswith("00AF:")
    assert by_name["hex"] == "00112233" and by_name["length"] == 4, by_name
    assert by_name["seg_off"] == "00AF:0017A6EC", by_name
    by_addr = cast(dict[str, Any], server.read_memory(ref="00AF:0017A6EC", length=4))
    assert by_addr["seg_off"] == "00AF:0017A6EC", by_addr


def test_read_memory_refuses_an_unlocatable_or_ambiguous_target(tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("dup", 0x1, kind="d"),
                              dsym.Symbol("dup", 0x2, kind="d")])
    absent = cast(dict[str, Any], server.read_memory(ref="nope"))
    assert absent["status"] == "INVALID" and "not in the symbol table" in absent["message"]
    ambig = cast(dict[str, Any], server.read_memory(ref="dup"))
    assert ambig["status"] == "INVALID" and "names 2 symbols" in ambig["message"]
    # A BARE NUMBER (no colon) is a symbol lookup, not a linear address -- `_decide_by` keys
    # on the colon. Pinned directly so a regression that read bare hex as an address (the
    # confusion _decide_by's own docstring warns of) would redden here.
    numeric = cast(dict[str, Any], server.read_memory(ref="400000"))
    assert numeric["status"] == "INVALID" and "not in the symbol table" in numeric["message"]


def test_attribution_in_real_mode_compares_the_linear_address(tmp_path: Path) -> None:
    fake = _names(tmp_path, mode="Real")
    fake.cs, fake.eip = "1000", "00000010"        # linear 0x10010
    st = dstate.STATE.store
    assert st is not None
    st.add(dec.Declaration("breakpoint", "address", "0FFF:00000110"))   # 0xFFF0+0x110=0x10100? no
    st.add(dec.Declaration("breakpoint", "address", "1001:00000000"))   # linear 0x10010 -- same
    # the row as the debugger lists the declared paragraph, the stop through another alias
    held = [{"index": "0", "entry": "BP 1001:0000"}]
    hit = arming.attribute_stop(fake, where=fake.where(), held=held)  # type: ignore[arg-type]
    assert hit["attributed"] is True and hit["ref"] == "1001:00000000"


def test_the_front_door_sends_the_reader_to_the_generated_index_and_keeps_no_table() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    assert "## The tools" in readme, "the front door lost its tools section"
    tools = readme.split("## The tools", 1)[1].split("\n## ", 1)[0]
    assert "](REFERENCE.md)" in tools, "the tools section does not link the index"
    assert "| tool |" not in readme, "a hand-kept tool table is back in the front door"


def test_perform_checks_a_symbols_find_step_before_any_step_runs(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True, symbols=[dsym.Symbol("_main", 0x100, kind="T")])
    fake.running = True
    fake.where_raises = True
    fake.input_effect = None
    for bad in ({"op": "symbols_find", "name": "_m", "limit": 51},
                {"op": "symbols_find", "name": "_m", "limit": 0},
                {"op": "symbols_find", "name": "", "limit": 5},
                {"op": "symbols_find"},
                {"op": "symbols_find", "name": "_m", "linear": "100"},
                # UNTYPED VALUES, as a step delivers them: a string limit is a refusal,
                # never a TypeError out of the comparison (the auditor's input).
                {"op": "symbols_find", "name": "_m", "limit": "5"},
                {"op": "symbols_find", "name": "_m", "limit": True}):
        out = server.perform(steps=[{"op": "send_keys", "keys": ["a"]}, bad], settle_seconds=1.0)
        assert out["status"] == "INVALID" and out["ran"] == [], (bad, out)
        assert out["errors"][0]["step"] == 1 and out["errors"][0]["op"] == "symbols_find", out
    assert fake.commands_sent == [], "a refused list must not have posted a key"
    # What only its step can judge still refuses THERE: a name absent from the table is
    # not a preflight refusal, and the step before it runs.
    fake.running = False
    fake.halted = True
    out = server.perform(steps=[{"op": "status"}, {"op": "symbols_find", "name": "_m", "limit": 5}])
    assert out["status"] == "ok" and out["steps_completed"] == 2, out


def test_an_address_ref_has_one_spelling_and_a_clear_takes_any_of_them(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    out = server.breakpoint_at(ref="00a7:100")
    assert out["status"] == "ok" and out["ref"] == "00a7:100", out
    assert server.breakpoint_at(ref="00A7:0100").get("already_stored", False) is True
    cleared = server.declaration_clear("breakpoint", ref="0A7:00000100")
    assert cleared["declarations_cleared"] == 1, cleared
    assert not any(r["entry"].startswith("BP ") for r in fake.rows), fake.rows
    assert server.watch_add(ref="00AF:0100", mode="change", length=4)["ref"] == "00AF:0100"
    assert server.declaration_clear("watch", ref="00af:100")["declarations_cleared"] == 1


def test_a_second_load_with_a_narrower_pattern_keeps_what_the_first_one_placed(
        tmp_path: Path) -> None:
    install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src, pattern="_engine_create"))
    assert first["kept"] == 1, first
    second = cast(dict[str, Any], server.symbols_load(path=src, pattern="_main"))
    assert second["kept"] == 1, second
    assert second["table_mode"] == "accumulated", second
    assert second["table_total"] == 2, second
    got = cast(dict[str, Any], server.symbols_find(name="_engine_create"))
    assert got["status"] == "ok", got
    assert got["symbols_total"] == 1, (
        "the first load's symbol is gone from the table the second load left behind")


def test_a_types_name_the_table_lacks_is_refused_before_anything_is_written(
        tmp_path: Path) -> None:
    s = install(mode="Pr32")
    src = _source(tmp_path)
    first = cast(dict[str, Any], server.symbols_load(path=src, pattern="_engine_create"))
    assert first["table_total"] == 1, first
    loaded_before = list(s.loaded)
    types_file = tmp_path / "dos-djgpp32.types"
    types_file.write_text("_no_such_symbol: u32\n", encoding="utf-8")
    bad = cast(dict[str, Any], server.symbols_load(path=src, pattern="_main",
                                                   types=str(types_file)))
    assert bad["status"] == "INVALID", bad
    assert "types are named for symbols the table lacks" in bad["message"], bad
    assert s.loaded == loaded_before, "the debugger's list grew on a call that refused"
    still = cast(dict[str, Any], server.symbols_find(name="_engine_create"))
    assert still["symbols_total"] == 1, still
    gone = cast(dict[str, Any], server.symbols_find(name="_main"))
    assert gone["symbols_total"] == 0, "the refused load's symbols landed in the table anyway"


@pytest.mark.parametrize("spelled", ["0x1000", "1000", "0X1000"])
def test_symbols_load_takes_its_base_as_hex_text(tmp_path: Path, spelled: str) -> None:
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base=spelled))
    assert got["status"] == "ok", got
    assert got["base"] == 0x1000, got


@pytest.mark.parametrize("bad", [4096, "-1000", "10_00", "0xZZ", ""])
def test_symbols_load_refuses_a_base_that_is_not_hex_text(tmp_path: Path, bad: object) -> None:
    install()
    src = tmp_path / "real16.map"
    src.write_text(TLINK_TEXT, encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(path=str(src), base=bad))
    assert got["code"] == "bad_argument" and "base" in got["message"], got


def test_section_bases_are_hex_text_too(tmp_path: Path) -> None:
    install()
    src = ILINK32_MAP
    got = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": "0x401000", "2": "423000", "3": "4289B8"}))
    assert got["status"] == "ok" and got["kept"] == 4, got
    bad = cast(dict[str, Any], server.symbols_load(
        path=str(src), section_bases={"1": 0x401000}))
    assert bad["code"] == "bad_argument" and "section_bases" in bad["message"], bad


def test_a_bare_step_is_one_step_into_and_find_takes_the_pattern_first(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    asked: list[dict[str, Any]] = []
    real = fake.step

    def recording(**kw: Any) -> dict[str, object]:
        asked.append(kw)
        return real(**kw)

    monkeypatch.setattr(fake, "step", recording)
    server.step()
    assert asked == [{"mode": "into", "count": 1}], asked

    def order(fn: Callable[..., Any]) -> list[str]:
        return [p for p in inspect.signature(fn).parameters if p != "ctx"]

    assert order(server.find)[:3] == ["data_hex", "ref", "length"], order(server.find)
    assert order(server.step)[:2] == ["count", "mode"], order(server.step)


def test_log_waits_stop_refusal_names_the_pattern_and_the_stop(tmp_path: Path) -> None:
    """`wait_stopped` from `log_wait` carries what was waited for and the stop it met."""
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.stops_during_wait = True
    got = cast(dict[str, Any], server.log_wait(channel="guest", pattern="never", seconds=1))
    assert got["code"] == "wait_stopped" and got["pattern"] == "never", got
    assert got["last_stop"]["pc"] == "00A7:00000000", got


def test_one_map_loaded_again_is_held_once_and_a_forgotten_table_takes_its_bases(
        tmp_path: Path) -> None:
    nm = tmp_path / "one.nm"
    nm.write_text("00001000 T _main\n", encoding="utf-8")
    _names(tmp_path)
    dstate.STATE.conf_fingerprint = "conf"
    for _ in range(3):
        assert server.symbols_load(path=str(nm), base="400000")["status"] == "ok"
    assert len(dstate.STATE.map_batches) == 1, "one map loaded again is not another batch"
    dstate.STATE.section_bases[1] = 0x1000
    dstate.STATE.forget_symbols()
    assert dstate.STATE.section_bases == {}, "a forgotten table kept its section bases"


def test_a_stop_outside_the_program_says_so_for_every_symbol(tmp_path: Path) -> None:
    fake = _protected_table(tmp_path)
    fake.mode, fake.cs, fake.ds = "Real", "F000", "0040"
    read = server.read_memory(ref="_g_eng_rate", length=4)
    assert read["status"] == "INVALID" and "outside the program" in read["message"], read
    assert "0x0000 to 0xFFFF" not in read["message"], read
    bp = server.breakpoint_at(ref="_main")
    assert bp["state"] == "unarmable" and "outside the program" in bp["why"], bp


def test_a_table_of_another_build_is_refused_and_the_loaded_one_stays(tmp_path: Path) -> None:
    guest = Path(__file__).resolve().parent / "guest"
    fake = _names(tmp_path)
    good = tmp_path / "good" / "dpmi.sym"
    good.parent.mkdir()
    shutil.copy(guest / "dpmi.sym", good)
    shutil.copy(guest / "dpmi.exe", good.parent / "dpmi.exe")
    loaded = _ok(server.symbols_load(path=str(good), base_from="CS"))
    assert loaded["checked"]["agree"] > 100, loaded["checked"]
    stale = tmp_path / "stale" / "dpmi.sym"
    stale.parent.mkdir()
    shutil.copy(guest / "dpmi.exe", stale.parent / "dpmi.exe")
    stale.write_text("".join(
        f"{int(p[0], 16) + 0xD0:08x} {p[1]} {p[2]}\n" if len(p) == 3 and p[1] == "T" else ln + "\n"
        for ln in good.read_text(encoding="utf-8").splitlines() for p in [ln.split()]),
        encoding="utf-8")
    before, base, loads = list(dstate.STATE.table), dict(dstate.STATE.base), fake.loads
    refused = server.symbols_load(path=str(stale), base_from="CS")
    assert refused["status"] == "INVALID" and "another build's" in refused["message"], refused
    assert dstate.STATE.table == before and dict(dstate.STATE.base) == base, "state moved"
    assert fake.loads == loads, "the debugger was handed the refused table"


def test_a_second_batch_at_the_same_base_accumulates_whatever_stop_it_is_loaded_at(
        tmp_path: Path) -> None:
    first, second = tmp_path / "a.nm", tmp_path / "b.nm"
    first.write_text("0016dd80 T _main\n", encoding="utf-8")
    second.write_text("0017ee90 T _other\n", encoding="utf-8")
    fake = _names(tmp_path)
    _ok(server.symbols_load(path=str(first), base="400000"))
    fake.mode = "Real"
    got = _ok(server.symbols_load(path=str(second), base="400000"))
    assert got["table_mode"] == "accumulated", got
    assert {s.name for s in dstate.STATE.table} >= {"_main", "_other"}


def test_a_table_loaded_while_the_guest_runs_takes_no_selectors_from_the_last_stop(
        tmp_path: Path) -> None:
    nm = tmp_path / "rm.nm"
    nm.write_text("00000100 T _start\n", encoding="utf-8")
    fake = _names(tmp_path)
    server.status()                                  # a protected-mode stop recorded
    fake.running = True
    assert server.symbols_load(path=str(nm), base="8000")["status"] == "ok"
    fake.running, fake.mode = False, "Real"
    got = server.breakpoint_at(ref="_start")
    assert got["state"] == "armed", got


def test_symbols_load_hands_keep_noise_on_and_reads_a_map_with_a_byte_no_utf8_reads(
        tmp_path: Path) -> None:
    nm = tmp_path / "prog.nm"
    nm.write_bytes(b"00001000 t .text\n0016dd80 T _main\n\xb0 not a row\n")
    _names(tmp_path)
    plain = _ok(server.symbols_load(path=str(nm), base="400000"))
    _names(tmp_path)
    noisy = _ok(server.symbols_load(path=str(nm), base="400000", keep_noise=True))
    assert plain["excluded_sections"] == 1 and noisy["excluded_sections"] == 0, (plain, noisy)
    assert noisy["kept"] == plain["kept"] + 1 and plain["unreadable"] == 1, (plain, noisy)


def test_a_state_load_keeps_the_table_and_its_base_is_measured_again_at_the_next_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf)))
    assert loaded["status"] == "ok" and dstate.STATE.base["base"] == 0x00400000, loaded
    monkeypatch.setattr(type(fake), "selector",
                        lambda self, reg: {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B})
    fake.eip = "00001004"                           # stopped in `_tick`, the program's code
    dstate.STATE.pending["remeasure"] = True        # what a state load leaves
    out = arming.apply_pending(cast(Any, fake))
    assert dstate.STATE.table and dstate.STATE.base["base"] == 0x00500000, dstate.STATE.base
    assert out["base_remeasured"] == {"register": "CS", "from": "0x00400000",
                                      "to": "0x00500000"}, out
    assert dstate.STATE.pending["remeasure"] is False


def test_a_state_load_asks_the_next_stop_to_measure_a_measured_base_again(
        tmp_path: Path) -> None:
    _names(tmp_path, symbols=[dsym.Symbol("_tick", 0x1000, kind="T")])
    dstate.STATE.base_measured_from = "CS"
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is True
    dstate.STATE.pending["remeasure"] = False
    dstate.STATE.base_measured_from = None
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is False


def test_the_base_measured_again_takes_the_program_s_selectors_with_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    out = arming.apply_pending(cast(Any, fake))
    assert dstate.STATE.base["selector_CS"] == 0xB7, dstate.STATE.base
    assert out["base_remeasured"]["to"] == "0x00500000", out
    assert placement.target_for(0x1000, "CS", cast(Any, fake))[0] == 0xB7


def test_a_stop_outside_the_program_s_code_leaves_the_base_to_measure_at_the_next(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    asked: list[str] = []

    def selector(self: Any, reg: str) -> dict[str, int]:
        asked.append(reg)
        return {"base": 0x00500000, "limit": 0x0023FFFF, "type": 0x1B}

    monkeypatch.setattr(type(fake), "selector", selector)
    for mode, eip in (("Real", "00001004"), ("Pr32", "00F00000")):   # a handler; a host's code
        fake.mode, fake.eip = mode, eip
        out = arming.apply_pending(cast(Any, fake))
        assert dstate.STATE.base["base"] == 0x00400000 and "base_remeasured" not in out, out
        assert dstate.STATE.pending["remeasure"] is True
        assert any("not in the program's protected-mode code" in w
                   for w in out["still_pending"]), out
    assert asked == [], "a stop outside the program asks no descriptor"


def test_a_pending_measure_is_said_by_status_and_drained_by_the_next_contact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _loaded_then_restored(tmp_path, monkeypatch)
    assert dstate.STATE.pending_summary()["base_remeasure"] is True
    from scry_dosbox_x import running
    running.drain_if_stopped(cast(Any, fake))
    assert dstate.STATE.base["base"] == 0x00500000, dstate.STATE.base
    assert dstate.STATE.pending_summary()["base_remeasure"] is False


def test_a_load_refused_before_it_was_sent_replaced_nothing(tmp_path: Path) -> None:
    from scry_dosbox_x import saved_states as saved
    ses = SimpleNamespace(machine_replaced=True, state_sent=True,
                          state_dir=lambda: tmp_path)
    with pytest.raises(ds.Invalid) as refusal:
        saved.load_state(cast(Any, ses), "nope")
    assert refusal.value.code == "unknown_ref" and ses.machine_replaced is False


def test_a_state_load_through_the_server_asks_the_next_stop_for_the_base(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    assert cast(dict[str, Any], server.symbols_load(path=str(mapf)))["status"] == "ok"
    dstate.STATE.pending["remeasure"] = False

    def loads(self: Any, name: str, seconds: float = 20.0) -> dict[str, object]:
        self.machine_replaced = name == "here"
        if name != "here":
            raise ds.Invalid("unknown_ref", f"no state named {name!r}")
        return {"name": name, "paused": True, "path": "/x/save/s.sav", "version": "1",
                "program": "p", "machine": "vga", "memory_mb": 16, "saved_at": "2026-01-01"}

    monkeypatch.setattr(type(fake), "load_state", loads, raising=False)
    assert cast(dict[str, Any], server.state_write("load", name="gone"))["code"] == "unknown_ref"
    assert dstate.STATE.pending_summary()["base_remeasure"] is False
    assert cast(dict[str, Any], server.state_write("load", name="here"))["status"] == "ok"
    assert dstate.STATE.pending_summary()["base_remeasure"] is True
    assert dict(dstate.STATE.pending)["dirty"] is True


def test_a_base_the_caller_gave_is_never_measured_again(tmp_path: Path) -> None:
    """A base `symbols_load` was handed is the caller's: a state load leaves it as it is."""
    _names(tmp_path)
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _tick\n", encoding="utf-8")
    loaded = cast(dict[str, Any], server.symbols_load(path=str(mapf), base="400000"))
    assert loaded["status"] == "ok", loaded
    assert dstate.STATE.base_measured_from is None
    dstate.STATE.machine_replaced()
    assert dstate.STATE.pending["remeasure"] is False
