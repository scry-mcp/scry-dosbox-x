"""The breakpoint list as a live run printed it (tests/fixtures/bplist/PROVENANCE.txt)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dosbox_x_server_support import _names, clean_session  # noqa: F401

import dosbox_arming as arming
import dosbox_console as dcons
import dosbox_session as ds
import dosbox_state as dstate

BPLIST = Path(__file__).parent / "fixtures" / "bplist"


def rows(name: str) -> list[dict[str, str]]:
    return dcons.parse_breakpoints((BPLIST / name).read_text(encoding="utf-8"))


def test_each_kind_of_row_is_read_as_the_debugger_prints_it() -> None:
    two = ["BPMEM 0000:0501 (00)", "BPMEM 0000:0500 (00)"]
    assert [r["entry"] for r in rows("bplist-bpmem.txt")] == two
    assert [r["entry"] for r in rows("bplist-bplm.txt")] == ["BPLM 00000600 (00)", *two]
    assert [r["entry"] for r in rows("bplist-bppm.txt")] == [
        *(f"BPPM 00AF:{0x19A17 - i:08X} (00)" for i in range(4)), "BPINT 31 AH=02"]
    assert rows("bplist-vm86.txt") == [{"index": "00", "entry": "BP 0814:0221"},
                                      {"index": "01", "entry": "BP 0000:0001"}]
    assert dcons.bp_row_target("BPMEM 0000:0500 (00)") == ("BPMEM", 0, 0x500)
    assert dcons.bp_row_target("BPPM 00AF:00019A14 (00)") == ("BPPM", 0xAF, 0x19A14)
    assert dcons.bp_row_target("BPLM 00000600 (00)") == ("BPLM", 0, 0x600)


def test_the_list_is_newest_first_and_a_delete_renumbers_what_is_left() -> None:
    """Deleting the middle row moves every later row up one index, so an index is never kept."""
    memory = ["BPLM 00000600 (00)", "BPMEM 0000:0501 (00)", "BPMEM 0000:0500 (00)"]
    before = rows("bpdel-before.txt")
    assert [r["entry"] for r in before] == ["BP F000:0300", "BP F000:0200", "BP F000:0100",
                                            *memory]
    after = rows("bpdel-after.txt")
    assert after == [{"index": f"{i:02d}", "entry": e} for i, e in enumerate(
        ["BP F000:0300", "BP F000:0100", *memory])]


def test_a_clear_deletes_the_row_at_its_index_now_and_reads_it_gone(tmp_path: Path) -> None:
    """The first row armed is listed last, at 02, never at the 00 it had when armed."""
    after = [r for r in rows("bpdel-before.txt") if r["entry"] != "BP F000:0100"]
    lists = [rows("bpdel-before.txt"), [{**r, "index": f"{i:02d}"} for i, r in enumerate(after)]]
    sent: list[str] = []

    def command(text: str, **_: Any) -> str:
        sent.append(text)
        return ""
    s = SimpleNamespace(where=lambda: {"cs": "F000", "eip": "0", "mode": "Real"},
                        command=command, breakpoints=lambda: lists.pop(0))
    s.delete_rows = lambda picks: ds.Session.delete_rows(s, picks)  # type: ignore[arg-type]
    got = ds.Session.clear_code_breakpoint(s, 0xF000, 0x100)  # type: ignore[arg-type]
    assert sent == ["BPDEL 02"] and got == {"entry": "BP F000:0100", "removed": True}, got


def test_a_linear_memory_row_can_stop_a_running_guest(tmp_path: Path) -> None:
    _names(tmp_path)
    dstate.STATE.last_stop.update(held=[r for r in rows("bplist-bplm.txt")
                                        if r["entry"].startswith("BPLM ")])
    assert arming.something_can_stop_it(), "a BPLM row listed at the last stop was not counted"
    dstate.STATE.last_stop.update(held=[])
    assert not arming.something_can_stop_it(), "the control: with no row nothing can stop it"


def _captured(name: str) -> Any:
    import json
    return json.loads((BPLIST / name).read_text(encoding="utf-8"))


def test_a_breakpoint_declared_at_a_vm86_stop_arms_and_names_the_stop_as_a_live_run_did(
        tmp_path: Path) -> None:
    import dosbox_running as running
    import dosbox_x_server as server
    live = _captured("vm86-arm.json")
    fake = _names(tmp_path, mode="VM86", cs="0814")
    fake.eip = "00000221"
    got = server.breakpoint_at(ref="0814:0221")
    keys = ("status", "by", "armed", "state", "marked")
    # `OmitEmpty` drops a false `marked` from the reply; the capture still carries it.
    assert {k: got.get(k, False) for k in keys} == {k: live["breakpoint_at"][k] for k in keys}, got
    stop = running.stop_reply(fake)  # type: ignore[arg-type]
    assert stop["cause"] == live["resume"]["cause"] and stop["cpu_mode"] == "VM86", stop


def _same(got: Any, live: Any, keys: tuple[str, ...]) -> None:
    assert {k: got[k] for k in keys} == {k: live[k] for k in keys}, (got, live)


def test_the_watches_a_live_run_armed_answer_as_it_did(tmp_path: Path) -> None:
    import dosbox_symbols as dsym
    import dosbox_x_server as server
    keys = ("status", "by", "mode", "fmt", "length", "armed", "state", "entries")
    _names(tmp_path, mode="Real", cs="0000", ds_="0000")
    _same(server.watch_add(ref="0000:0500", mode="change", length=2),
          _captured("real-change-watch.json")["watch_add"], keys)
    _names(tmp_path, symbols=[dsym.Symbol("_g_ticks", 0x19A14, kind="D")])
    _same(server.watch_add(ref="_g_ticks", mode="change", length=4),
          _captured("bppm.json"), (*keys, "caveat"))


def test_a_pointer_watch_on_a_null_head_answers_as_a_live_run_did(tmp_path: Path) -> None:
    import dosbox_x_server as server
    live = _captured("pointer-watches.json")
    _names(tmp_path, mode="Real", cs="0000", ds_="0040")
    keys = ("status", "by", "mode", "fmt", "length", "armed", "state", "why", "pointer")
    _same(server.watch_add(ref="[0040:001A]", mode="show", length=2), live["show"], keys)
    _same(server.watch_add(ref="[0040:001C]", mode="change", length=2), live["change"], keys)


def test_a_saved_comment_keeps_the_width_its_offset_was_read_with(tmp_path: Path) -> None:
    """An offset past FFFF keeps its eight digits through a load and a save, a 16-bit one four."""
    import dosbox_declarations as dec
    assert dec.canonical_ref("00A7:0045F880", "address") == "00A7:0045F880"
    assert dec.canonical_ref("00a7:45f880", "address") == "00A7:0045F880"
    assert dec.canonical_ref("814:10b", "address") == "0814:010B"
    assert dec.canonical_ref("00A7:00000100", "address") == "00A7:0100", "one place, one spelling"
    assert dec.canonical_ref("[00A7:0045F880]+0x4", "pointer") == "[00A7:0045F880]+0x4"


def test_a_linear_watch_armed_at_the_console_is_listed_as_nobody_s(tmp_path: Path) -> None:
    import dosbox_x_server as server
    fake = _names(tmp_path, mode="Real", cs="0000", ds_="0000")
    fake.rows[:] = [r for r in rows("bplist-bplm.txt") if r["entry"].startswith("BPLM ")]
    got = server.declaration_list("watch")
    assert got["foreign"] == {"watches": ["BPLM 00000600 (00)"]}, got["foreign"]


def test_the_session_arms_a_change_watch_with_the_command_and_row_a_live_run_saw() -> None:
    live = _captured("real-change-watch.json")["watch_add"]
    sent: list[str] = []

    def command(text: str, **_: Any) -> str:
        sent.append(text)
        return ""
    s = SimpleNamespace(where=lambda: {"cs": "0000", "eip": "0", "mode": "Real"},
                        command=command, breakpoints=lambda: rows("bplist-bpmem.txt"),
                        altered=False)
    got = ds.Session.watch(s, 0x0000, 0x0500)  # type: ignore[arg-type]
    assert sent == [live["command"]] and got["armed"] == live["entry"], (sent, got)


def test_memory_under_an_armed_change_watch_reads_as_the_program_wrote_it() -> None:
    """The bytes a live read returned under an armed `BPMEM` are the ones written, not a trap."""
    live = _captured("real-change-watch.json")
    assert live["watch_add"]["armed"] is True and live["watch_add"]["entry"].startswith("BPMEM ")
    assert live["read_memory"]["hex"] == live["write"]["readback"] == "5aa5", live


def test_two_stale_rows_of_a_moved_watch_are_both_deleted_whatever_the_renumbering(
        tmp_path: Path) -> None:
    """A delete renumbers the rows below it, so the second index is read after the first goes."""
    fake = _names(tmp_path, mode="Real", cs="0000", ds_="0000")
    for off in (0x500, 0x600, 0x700):
        fake.watch(segment=0, offset=off)        # listed newest first, as the debugger does
    rows_ = [{"kind": "watch", "seg": 0, "off": off, "entry": f"BPMEM 0000:{off:04X}"}
             for off in (0x500, 0x600, 0x700)]
    stale = [rows_[1], rows_[0]]                 # the upper row first: its delete moves the other
    kept = arming._drop_stale(fake, rows_, stale)  # type: ignore[arg-type]
    assert kept == "" and [r["entry"] for r in fake.rows] == ["BPMEM 0000:0700 (00)"], fake.rows


def test_a_console_linear_watch_at_a_server_watch_s_place_is_neither_taken_nor_deleted(
        tmp_path: Path) -> None:
    """`BPLM 600` and a server watch at 0000:0600 name one byte; the linear row stays foreign."""
    import dosbox_x_server as server
    fake = _names(tmp_path, mode="Real", cs="0000", ds_="0000")
    added = server.watch_add(ref="0000:0600", mode="change", length=1)
    assert added["armed"] is True, added
    fake.rows[:] = [{"index": "00", "entry": "BPLM 00000600 (00)"}, *fake.rows]
    fake._relist(fake.rows)
    assert server.declaration_list("watch")["foreign"] == {"watches": ["BPLM 00000600 (00)"]}
    gone = server.declaration_clear("watch", ref="0000:0600")
    assert [r["entry"] for r in fake.rows] == ["BPLM 00000600 (00)"], (gone, fake.rows)
    assert gone["disarmed"] == ["BPMEM 0000:0600 (00)"], gone
