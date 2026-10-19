"""Comments: the store's comment kind (kept out of every list that arms, counts or waits for a
stop), the place a comment lands on and the one-per-place rule, and the five tools over a session
double, file round trips included."""
from __future__ import annotations

import dataclasses
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_dosbox_x_code import pr32_machine
from test_dosbox_x_running_table import _running
from test_dosbox_x_server import (  # noqa: F401
    FakeSession,
    NamesFake,
    _Booted,
    _start_over_a_store,
    build_of,
    clean_session,
    install,
)

import dosbox_arming as arming
import dosbox_comment_file as cf
import dosbox_comments as comments
import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_machine as machine
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_symbols as dsym
import dosbox_x_server as server

STAMP = "2026-10-03T06:00:00+00:00"
#: The probe guest's own table (`tests/guest/probe.sym`) and the base it is loaded at.
PROBE = [("start", 0x10B), ("emit", 0x137), ("bump", 0x141), ("tick", 0x156), ("cnt", 0x159)]
PROBE_BASE = 0x8140


def comment(ref: str, text: str = "entry", **kw: Any) -> dec.Declaration:
    by = "address" if ":" in ref else "symbol"
    return dec.Declaration("comment", by, ref, text=text, created_at=kw.pop("created_at", STAMP),
                           **kw)


def probe_table(extra: list[tuple[str, int]] | None = None) -> None:
    dstate.STATE.install_table([dsym.Symbol(n, o) for n, o in PROBE + (extra or [])])
    dstate.STATE.base["base"] = PROBE_BASE


class Protected(FakeSession):
    """A stop in a 32-bit protected-mode program whose CS and DS are the selectors the captured
    `SELINFO` screen describes (base 00400000, limit 0023FFFF), as on dos-djgpp32."""

    def __init__(self) -> None:
        super().__init__(mode="Pr32")

    def registers(self) -> dict[str, str]:
        return {"EAX": "00001234", "CS": "00A7", "DS": "00AF"}


def ok(reply: dict[str, Any]) -> dict[str, Any]:
    assert reply["status"] == "ok", reply
    return reply


def refused(reply: dict[str, Any], code: str) -> str:
    assert (reply["status"], reply.get("code")) == ("INVALID", code), reply
    return str(reply["message"])


# ------------------------------------------------------------------------------- the store

def test_a_comment_carries_its_text_and_round_trips_through_the_store_file(
        tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    store.apply(adds=[comment("start", "entry point"), comment("0814:010B", "the store")])
    again = dec.DeclarationStore("g", path=tmp_path / "d.json").comments()
    assert [(d.ref, d.by, d.text, d.created_at) for d in again] == [
        ("start", "symbol", "entry point", STAMP), ("0814:010B", "address", "the store", STAMP)]


@pytest.mark.parametrize("kw, said", [
    ({"text": ""}, "text is empty"), ({"text": "a\tb"}, "not printable"),
    ({"text": "x" * 238}, "238 UTF-8 bytes"), ({"created_at": "2026-10-03"}, "created_at"),
    ({"created_at": None}, "created_at"), ({"ref": "start+2"}, "adds an offset"),
    ({"ref": "0x824B"}, "bare number"), ({"by": "pointer", "ref": "[g]"}, "through a pointer"),
    ({"by": "symbol", "ref": "0814:010B"}, "carries a colon"),
    ({"width": 2}, "no watch fields")])
def test_a_comment_the_file_could_not_hold_cannot_be_built(kw: dict[str, Any],
                                                            said: str) -> None:
    fields: dict[str, Any] = {"kind": "comment", "by": "symbol", "ref": "start", "text": "x",
                              "created_at": STAMP, **kw}
    with pytest.raises(dec.DeclarationError, match=said):
        dec.Declaration(fields.pop("kind"), fields.pop("by"), fields.pop("ref"), **fields)


def test_only_a_comment_carries_text() -> None:
    with pytest.raises(dec.DeclarationError, match="only a comment"):
        dec.Declaration("breakpoint", "symbol", "start", text="x")


def test_a_hand_edited_store_holding_a_comment_no_file_could_hold_is_refused_on_load(
        tmp_path: Path) -> None:
    (tmp_path / "d.json").write_text(
        '{"g": [{"kind": "comment", "by": "symbol", "ref": "start", "created_at": '
        f'"{STAMP}", "text": "a\\tb"}}]}}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="stored comment's text"):
        dec.DeclarationStore("g", path=tmp_path / "d.json")
    (tmp_path / "d.json").write_text(
        '{"g": [{"kind": "comment", "by": "symbol", "ref": "start", "created_at": '
        f'"{STAMP}"}}]}}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="text is not text"):
        dec.DeclarationStore("g", path=tmp_path / "d.json")


#: Batches over conf `c`: A describes 1000..9000, B is A relinked, H lies above both.
_A = dec.Build.of("c", [("_main", 0x1000), ("_rest", 0x9000)])
_B = dec.Build.of("c", [("_main", 0x1010), ("_rest", 0x9000)])
_H = dec.Build.of("c", [("_helper", 0xA000), ("_end", 0xB000)])


@pytest.mark.parametrize("ref, stamp, row_conf, batches, linear, conf, want", [
    ("start", "old", None, [_B], 0x2000, "c", None),               # a name is never stale
    ("0814:010B", "old", None, [_B], 0x2000, None, None),          # no conf: nothing judged
    # its batch held, whatever came after it
    ("0814:010B", _A.stamp, "c", [_A], 0x2000, "c", None),
    ("0814:010B", _A.stamp, "c", [_A, _B], 0x2000, "c", None),
    ("0814:010B", _A.stamp, "c", [_B, _A], 0x2000, "c", None),
    # another batch describes the place
    ("0814:010B", _A.stamp, "c", [_B], 0x2000, "c", "other"),
    ("0814:010B", _A.stamp, "c", [_B], None, "c", "other"),        # place unknown: described
    ("0814:010B", "c", "c", [_A], 0x2000, "c", "unrecorded"),
    ("0814:010B", "c", None, [_A], 0x2000, "c", "unrecorded"),     # its stamp is its conf
    ("0814:010B", "d", "d", [_A], 0x2000, "c", "other"),
    # no batch describes it: a row made under a map whose batch is gone is stale, and only a
    # row stamped with the conf alone is judged by the conf
    ("0814:010B", _A.stamp, "c", [], 0x2000, "c", "other"),
    ("0814:010B", _A.stamp, "c", [_H], 0x2000, "c", "other"),
    ("0814:010B", "c", None, [_H], 0x2000, "c", None),
    ("0814:010B", _A.stamp, None, [], 0x2000, "c", "no_conf"),
    ("0814:010B", _A.stamp, "d", [_H], 0x2000, "c", "other"),
    ("0814:010B", "d", "d", [], 0x2000, "c", "other"),
])
def test_a_raw_comment_is_judged_by_the_batch_that_describes_its_place(
        ref: str, stamp: str, row_conf: str | None, batches: list[dec.Build],
        linear: int | None, conf: str | None, want: str | None) -> None:
    decl = comment(ref, fingerprint=stamp, conf_fingerprint=row_conf)
    assert dec.raw_staleness(decl, conf, batches, lambda: linear) == want


def test_the_place_is_not_asked_while_the_rows_batch_is_held() -> None:
    def never() -> int:
        raise AssertionError("asked")
    decl = comment("0814:010B", fingerprint=_A.stamp, conf_fingerprint="c")
    assert dec.raw_staleness(decl, "c", [_B, _A], never) is None
    assert dec.raw_staleness(decl, "c", [], never) == "other", "no batch held: none to ask"


def test_a_comment_never_goes_through_add_which_would_ignore_its_text(tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    with pytest.raises(dec.DeclarationError, match="goes through apply"):
        store.add(comment("start"))


def test_apply_makes_every_change_and_writes_the_file_once(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    a, b = comment("start", "a"), comment("emit", "b")
    store.apply(adds=[a, b])
    writes: list[int] = []
    real = store._persist

    def counted() -> None:
        writes.append(1)
        real()
    monkeypatch.setattr(store, "_persist", counted)
    c = comment("start", "c")
    store.apply(adds=[comment("bump", "d")], replaces=[(a, c)], removes=[b])
    assert writes == [1]
    assert [(d.ref, d.text) for d in store.comments()] == [("start", "c"), ("bump", "d")]


def test_a_store_write_that_fails_keeps_the_change_in_memory_and_says_so(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")

    def fails() -> None:
        raise OSError("disk full")
    monkeypatch.setattr(store, "_persist", fails)
    with pytest.raises(dec.StoreWriteError, match="disk full"):
        store.apply(adds=[comment("start")])
    assert [d.ref for d in store.comments()] == ["start"]


def test_comments_are_in_no_list_of_what_stops_or_watches(tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    store.apply(adds=[comment("start"), comment("0814:010B")])
    assert store.declarations() == []
    assert len(store.comments()) == 2


# ------------------------------------------------- what arms, counts or waits sees no comment

def test_a_stored_comment_leaves_status_declarations_unchanged() -> None:
    install()
    before = ok(server.status())["declarations"]
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    ok(server.comment_add(ref="0814:0106", text="the loop"))
    assert ok(server.status())["declarations"] == before == {"breakpoints": 0, "watches": 0}


def test_with_only_a_comment_nothing_can_stop_the_guest(tmp_path: Path) -> None:
    _running(tmp_path)
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("start"), comment("0814:010B")])
    assert not arming.something_can_stop_it()
    # THE CONTROL: the same store with one code breakpoint beside them can stop it.
    assert store.add(dec.Declaration("breakpoint", "address", "0814:010B"))
    assert arming.something_can_stop_it()


def test_the_two_brooms_leave_comments_and_the_two_lists_show_none() -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    ok(server.breakpoint_at(ref="emit"))
    ok(server.watch_add(ref="cnt", mode="show", length=2))
    assert [b["ref"] for b in ok(server.breakpoint_list())["breakpoints"]] == ["emit"]
    assert [w["ref"] for w in ok(server.watch_list())["watches"]] == ["cnt"]
    ok(server.breakpoint_clear(all=True))
    ok(server.watch_clear(all=True))
    assert [c["ref"] for c in ok(server.comment_list())["comments"]] == ["start"]


# ----------------------------------------------------------------- the place, one per place

def test_a_symbol_comment_is_placed_where_symbols_find_places_it() -> None:
    install()
    probe_table()
    got = ok(server.comment_add(ref="start", text="entry"))
    found = ok(server.symbols_find(name="start"))["symbols"][0]["addr"]
    assert got["comment"]["addr"] == found == "0x0000824b"
    assert got["comment"]["state"] == "resolved" and "why" not in got["comment"]
    assert (got["replaced_comments"], got["declarations"]["persistent"]) == ([], True)
    assert got["declarations"]["path"] == str(cast(dec.DeclarationStore, dstate.STATE.store).path)
    assert got["session"]["altered"] is False


def test_an_alias_of_a_commented_place_replaces_its_text_and_keeps_its_ref() -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    got = ok(server.comment_add(ref="0824:000B", text="entry, aliased"))
    assert (got["comment"]["ref"], got["comment"]["by"], got["comment"]["text"]) == (
        "start", "symbol", "entry, aliased")
    assert [(r["ref"], r["text"]) for r in got["replaced_comments"]] == [("start", "entry")]
    again = ok(server.comment_add(ref="814:10b", text="third spelling"))
    assert again["comment"]["ref"] == "start"
    assert ok(server.comment_list())["comments_total"] == 1


def test_a_raw_comment_is_stored_canonical_and_placed_by_real_mode_arithmetic() -> None:
    install()
    got = ok(server.comment_add(ref="814:106", text="the loop"))
    assert (got["comment"]["ref"], got["comment"]["addr"]) == ("0814:0106", "0x00008246")


def test_a_symbol_with_no_table_or_absent_from_it_is_stored_unresolved() -> None:
    install()
    got = ok(server.comment_add(ref="start", text="entry"))
    assert got["comment"]["state"] == "unresolved" and "addr" not in got["comment"]
    assert "symbols_load" in got["note"]
    probe_table()
    gone = ok(server.comment_add(ref="nowhere", text="kept"))
    assert gone["comment"]["state"] == "unresolved" and "not a symbol" in gone["note"]
    listed = {c["ref"]: c for c in ok(server.comment_list())["comments"]}
    assert listed["start"]["addr"] == "0x0000824b" and listed["start"]["state"] == "resolved"


def test_an_ambiguous_symbol_is_refused_and_nothing_stored() -> None:
    install()
    probe_table([("twice", 0x10), ("twice", 0x20)])
    assert "2 symbols" in refused(server.comment_add(ref="twice", text="x"), "ambiguous_ref")
    assert ok(server.comment_list())["comments_total"] == 0


def test_a_real_mode_offset_past_ffff_is_refused() -> None:
    install()
    assert "past FFFF" in refused(server.comment_add(ref="0814:10000", text="x"),
                                  "bad_argument")
    assert ok(server.comment_list())["comments_total"] == 0


def test_a_protected_mode_address_is_placed_through_its_selectors_base() -> None:
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_add(ref="00A7:00001000", text="in the code"))
    assert got["comment"]["addr"] == "0x00401000"
    alias = ok(server.comment_add(ref="00AF:1000", text="same byte through DS"))
    assert alias["comment"]["ref"] == "00A7:1000"
    assert "limit 23FFFF" in refused(server.comment_add(ref="00A7:00240000", text="x"),
                                     "bad_argument")


def install_store() -> None:
    session = dstate.STATE.session
    install()
    dstate.STATE.session = session


def test_a_selector_whose_base_cannot_be_read_is_stored_by_its_ref_and_said_so() -> None:
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_add(ref="0038:000B8000", text="the text page"))
    assert got["comment"]["state"] == "unarmable" and "addr" not in got["comment"]
    assert "logfile" in got["note"]
    same = ok(server.comment_add(ref="38:B8000", text="again"))
    assert [r["text"] for r in same["replaced_comments"]] == ["the text page"]


def test_comments_a_rebuild_brought_to_one_place_are_kept_and_reached_by_their_own_ref() -> None:
    install()
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("0814:010B", "raw"), comment("start", "by name")])
    probe_table()
    rows = ok(server.comment_list())["comments"]
    assert [r["addr"] for r in rows] == ["0x0000824b", "0x0000824b"]
    gone = ok(server.comment_delete(ref="start"))
    assert gone["deleted"]["text"] == "by name"
    assert [c.ref for c in store.comments()] == ["0814:010B"]


def test_a_delete_reaches_by_place_and_a_miss_names_what_is_held() -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    got = ok(server.comment_delete(ref="0824:000B"))
    assert (got["deleted"]["ref"], got["declarations"]["persistent"]) == ("start", True)
    ok(server.comment_add(ref="emit", text="out"))
    assert "'emit'" in refused(server.comment_delete(ref="start"), "unknown_ref")


def test_a_raw_comment_over_another_build_lists_stale_with_its_place() -> None:
    install()
    dstate.STATE.conf_fingerprint = "now"
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("0814:010B", "old", fingerprint="then",
                              conf_fingerprint="then")])
    (row,) = ok(server.comment_list())["comments"]
    assert (row["state"], row["addr"]) == ("stale", "0x0000824b") and "another build" in row["why"]


def test_a_store_that_cannot_be_written_is_host_failed_and_the_comment_still_listed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    install()
    store = cast(dec.DeclarationStore, dstate.STATE.store)

    def fails() -> None:
        raise OSError("read-only")
    monkeypatch.setattr(store, "_persist", fails)
    got = server.comment_add(ref="0814:0106", text="x")
    refused(got, "host_failed")
    assert got["held_in_memory"] is True
    assert ok(server.comment_list())["comments_total"] == 1


# ------------------------------------------------------------------ a running guest

def test_a_running_guest_lists_and_saves_but_add_delete_and_load_refuse(tmp_path: Path) -> None:
    fake = _running(tmp_path)
    dstate.STATE.last_stop.update(seq=1, at="0814:0106", attribution={}, when=0.0, clock="c",
                                  held=[], where={"mode": "Real"}, registers={})
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("0814:010B", "raw"), comment("00A7:00001000", "pm")])
    listed = ok(server.comment_list())
    assert listed["session"]["running"] is True and listed["last_stop"]["stop_seq"] == 1
    assert [r.get("addr") for r in listed["comments"]] == ["0x0000824b", "0x00001a70"]
    dstate.STATE.last_stop["where"] = {"mode": "Pr32"}
    pm = ok(server.comment_list())["comments"]
    assert [r["state"] for r in pm] == ["unarmable", "unarmable"]
    assert "machine runs" in pm[0]["why"]
    ok(server.comment_save(dest=str(tmp_path / "c.tsv")))
    for got in (server.comment_add(ref="start", text="x"), server.comment_delete(ref="0814:010B"),
                server.comment_load(path=str(tmp_path / "c.tsv"))):
        refused(got, "not_stopped")
    assert fake.asked == []


# ----------------------------------------------------------------------------- comment_save

def test_save_writes_the_comment_file_sorted_whole(tmp_path: Path) -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    ok(server.comment_add(ref="0814:0106", text="the loop"))
    dest = tmp_path / "probe.comments.tsv"
    got = ok(server.comment_save(dest=str(dest)))
    assert (got["path"], got["comments_total"], got["dropped_comments"], got["dropped_total"],
            got["truncated"]) == (str(dest), 2, [], 0, False)
    lines = dest.read_text(encoding="utf-8").split("\n")
    assert lines[0] == cf.HEADER and lines[-1] == ""
    assert [ln.split("\t")[0] for ln in lines[1:-1]] == ["0814:0106", "start"]
    assert [ln.split("\t")[3] for ln in lines[1:-1]] == ["the loop", "entry"]
    assert stat.S_IMODE(dest.stat().st_mode) == 0o644


def test_an_empty_store_saves_the_header_alone(tmp_path: Path) -> None:
    install()
    got = ok(server.comment_save(dest=str(tmp_path / "e.tsv")))
    assert got["comments_total"] == 0
    assert (tmp_path / "e.tsv").read_bytes() == (cf.HEADER + "\n").encode()


def test_save_over_a_comment_file_names_what_it_drops_and_keeps_its_mode(tmp_path: Path) -> None:
    install()
    dest = tmp_path / "c.tsv"
    dest.write_text(cf.render([cf.Row("gone", "", STAMP, "x"), cf.Row("814:10b", "", STAMP, "y")]),
                    encoding="utf-8")
    os.chmod(dest, 0o600)
    ok(server.comment_add(ref="0814:010B", text="kept"))
    got = ok(server.comment_save(dest=str(dest)))
    assert got["dropped_comments"] == [{"ref": "gone"}]
    assert got["dropped_total"] == 1 and "dropped_comments" in got["note"]
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_save_refuses_and_leaves_alone_what_is_not_a_comment_file_to_replace(
        tmp_path: Path) -> None:
    install()
    ok(server.comment_add(ref="0814:010B", text="x"))
    notes = tmp_path / "notes.txt"
    notes.write_bytes(b"my notes\n")
    latin = tmp_path / "latin.tsv"
    latin.write_bytes(cf.HEADER.encode() + b"\nstart\t\t" + STAMP.encode() + b"\t\xe9\n")
    link = tmp_path / "link.tsv"
    link.symlink_to(notes)
    fifo = tmp_path / "fifo.tsv"
    os.mkfifo(fifo)
    for dest, said in ((notes, "not a comment file"), (latin, "not UTF-8"), (link, "is a link"),
                       (tmp_path, "not a regular file"), (fifo, "not a regular file"),
                       (tmp_path / "no" / "c.tsv", "not a directory")):
        assert said in refused(server.comment_save(dest=str(dest)), "bad_argument"), dest
    assert notes.read_bytes() == b"my notes\n"
    assert latin.read_bytes().endswith(b"\t\xe9\n")


def test_save_refuses_the_declaration_stores_own_file() -> None:
    install()
    path = cast(dec.DeclarationStore, dstate.STATE.store).path
    ok(server.comment_add(ref="0814:010B", text="x"))
    before = path.read_bytes()
    for spelled in (str(path), str(path).upper()):
        assert "store's own file" in refused(server.comment_save(dest=spelled), "bad_argument")
    assert path.read_bytes() == before


@pytest.mark.parametrize("dest", ["c.tsv", "./c.tsv", ""])
def test_a_dest_that_is_not_absolute_is_refused_without_a_session(dest: str) -> None:
    refused(server.comment_save(dest=dest), "bad_argument")


# ----------------------------------------------------------------------------- comment_load

def _file(tmp_path: Path, *rows: tuple[str, str], name: str = "in.tsv") -> Path:
    path = tmp_path / name
    path.write_text(cf.render([cf.Row(r, "", STAMP, t) for r, t in rows]), encoding="utf-8")
    return path


def test_load_adds_replaces_keeps_and_reports_each(tmp_path: Path) -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="old text"))
    ok(server.comment_add(ref="emit", text="same"))
    ok(server.comment_add(ref="bump", text="only the store"))
    src = _file(tmp_path, ("0824:000B", "new text"), ("emit", "same"), ("cnt", "added"))
    got = ok(server.comment_load(path=str(src)))
    assert (got["parsed"], got["added"], got["replaced_total"], got["unchanged"],
            got["comments_total"], got["truncated"]) == (3, 1, 1, 1, 4, False)
    assert [(r["ref"], r["text"]) for r in got["replaced_comments"]] == [("start", "old text")]
    held = {c["ref"]: c["text"] for c in ok(server.comment_list())["comments"]}
    assert held == {"start": "new text", "emit": "same", "bump": "only the store",
                    "cnt": "added"}


def test_a_file_naming_one_place_twice_loads_both_and_says_a_save_will_refuse_them(
        tmp_path: Path) -> None:
    """Which refs alias one byte depends on the table and the mode of the stop a file is loaded
    at, so a load never refuses a file for it: both are kept, as a rebuild leaves them, and the
    note names them."""
    install()
    probe_table()
    src = _file(tmp_path, ("start", "a"), ("0814:010B", "b"), ("emit", "c"))
    got = ok(server.comment_load(path=str(src)))
    assert (got["added"], got["comments_total"]) == (3, 3)
    assert "'0814:010B' and 'start'" in got["note"] and "comment_save" in got["note"]
    rows = ok(server.comment_list())["comments"]
    assert sorted(r["addr"] for r in rows) == ["0x0000824b", "0x0000824b", "0x00008277"]


def test_a_file_row_reaches_the_comment_its_ref_spells_before_an_alias_reaches_it(
        tmp_path: Path) -> None:
    """`start` in the file is the held `start`; its alias in the same file is a second comment,
    never a second replacement of the one row."""
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="held"))
    src = _file(tmp_path, ("0824:000B", "alias"), ("start", "held"))
    got = ok(server.comment_load(path=str(src)))
    assert (got["added"], got["replaced_total"], got["unchanged"]) == (1, 0, 1)
    held = {c.ref: c.text for c in cast(dec.DeclarationStore, dstate.STATE.store).comments()}
    assert held == {"start": "held", "0824:000B": "alias"}


def test_a_file_spelling_one_address_twice_loads_nothing_and_names_both_lines(
        tmp_path: Path) -> None:
    """Two spellings of one `SEG:OFF` are one ref whatever the machine's state, so the file
    breaks the one-row-per-ref rule and is refused as the format refuses it."""
    install()
    src = tmp_path / "in.tsv"
    src.write_text(cf.HEADER + f"\n0814:010B\t\t{STAMP}\ta\n0814:10b\t\t{STAMP}\tb\n",
                   encoding="utf-8")
    message = refused(server.comment_load(path=str(src)), "bad_argument")
    assert f"{src}:3" in message and "line 2" in message
    assert ok(server.comment_list())["comments_total"] == 0

def test_two_file_rows_at_a_held_place_replace_it_once_and_add_the_other(
        tmp_path: Path) -> None:
    install()
    probe_table()
    ok(server.comment_add(ref="0814:010B", text="held"))
    src = _file(tmp_path, ("0824:000B", "first"), ("start", "second"))
    got = ok(server.comment_load(path=str(src)))
    assert (got["replaced_total"], got["added"]) == (1, 1)
    held = {c.ref: c.text for c in cast(dec.DeclarationStore, dstate.STATE.store).comments()}
    assert held == {"0814:010B": "first", "start": "second"}


def test_a_file_the_format_refuses_loads_nothing_and_names_the_line(tmp_path: Path) -> None:
    install()
    src = tmp_path / "bad.tsv"
    src.write_text(cf.HEADER + f"\nstart\t\t{STAMP}\tok\nemit\t:cpu\t{STAMP}\tno\n",
                   encoding="utf-8")
    assert f"{src}:3" in refused(server.comment_load(path=str(src)), "bad_argument")
    lone_cr = tmp_path / "cr.tsv"
    lone_cr.write_bytes(cf.HEADER.encode() + b"\nstart\t\t" + STAMP.encode() + b"\ta\rb\n")
    assert "carriage return" in refused(server.comment_load(path=str(lone_cr)), "bad_argument")
    assert ok(server.comment_list())["comments_total"] == 0


def _rows_by_ref() -> dict[str, dict[str, Any]]:
    return {r["ref"]: r for r in ok(server.comment_list())["comments"]}


@pytest.mark.parametrize("protected, fine, ref, said, waits", [
    (False, "0814:0106", "0814:10000", "past FFFF", "kept for a protected-mode stop"),
    (True, "00A7:00001000", "00A7:00240000", "limit 23FFFF",
     "kept for a stop at which 00A7's limit reaches it"),
    (True, "00A7:00001000", "0000:0100", "null selector", "kept for a real-mode stop"),
    (True, "00A7:00001000", "0000:00010000", "null selector", "no stop places it"),
    (False, "0814:0106", "0000:00010000", "past FFFF", "no stop places it")])
def test_a_file_row_this_stop_cannot_place_loads_unarmable_and_named(
        tmp_path: Path, protected: bool, fine: str, ref: str, said: str, waits: str) -> None:
    """Where a raw address lands depends on the mode of the stop, so a load keeps a row this
    stop cannot place, `unarmable` with why, names it in `note`, and loads the rest; a call
    naming that address is still refused, since a call is answered at this stop. The why names
    the stop the row waits for, and a row past its selector's limit waits for a descriptor
    that reaches it, which no change of mode brings."""
    if protected:
        dstate.STATE.session = Protected()  # type: ignore[assignment]
        install_store()
    else:
        install()
    got = ok(server.comment_load(path=str(_file(tmp_path, (fine, "fine"), (ref, "past")))))
    held = dec.canonical_ref(ref, "address")
    assert got["added"] == 2 and held in got["note"]
    rows = _rows_by_ref()
    assert rows[dec.canonical_ref(fine, "address")]["state"] == "resolved"
    assert rows[held]["state"] == "unarmable" and "addr" not in rows[held]
    assert said in rows[held]["why"] and waits in rows[held]["why"]
    assert "mode holds" not in rows[held]["why"] + got["note"]
    assert said in refused(server.comment_add(ref=ref, text="x"), "bad_argument")


def test_a_protected_mode_save_loads_at_the_real_mode_park_and_is_placed_back(
        tmp_path: Path) -> None:
    """Every session starts parked in real mode, so a file saved at a protected-mode stop has
    to load there: its rows past FFFF wait, unplaced, for the next protected-mode stop, and a
    save from that stop writes the same bytes."""
    install()
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    ok(server.comment_add(ref="00A7:00045F80", text="pm"))
    saved, again = tmp_path / "pm.tsv", tmp_path / "again.tsv"
    ok(server.comment_save(dest=str(saved)))
    install()
    got = ok(server.comment_load(path=str(saved)))
    assert got["added"] == 1 and "00A7:45F80" in got["note"]
    assert _rows_by_ref()["00A7:45F80"]["state"] == "unarmable"
    ok(server.comment_save(dest=str(again)))
    assert again.read_bytes() == saved.read_bytes()
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    row = _rows_by_ref()["00A7:45F80"]
    assert (row["state"], row["addr"]) == ("resolved", "0x00445f80")


def test_a_real_mode_save_loads_at_a_protected_mode_stop_and_is_placed_back(
        tmp_path: Path) -> None:
    """The mirror: a vector of the interrupt table, saved at the park, names the null selector
    at a protected-mode stop, so it waits there and is placed again in real mode."""
    install()
    ok(server.comment_add(ref="0000:0084", text="int 21h vector"))
    saved = tmp_path / "real.tsv"
    ok(server.comment_save(dest=str(saved)))
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_load(path=str(saved)))
    assert got["added"] == 1 and "0000:0084" in got["note"]
    assert "null selector" in _rows_by_ref()["0000:0084"]["why"]
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    row = _rows_by_ref()["0000:0084"]
    assert (row["state"], row["addr"]) == ("resolved", "0x00000084")


def test_a_stale_comment_with_the_files_text_is_brought_to_this_build(tmp_path: Path) -> None:
    install()
    dstate.STATE.conf_fingerprint = "now"
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("0814:010B", "same", fingerprint="then",
                              conf_fingerprint="then")])
    got = ok(server.comment_load(path=str(_file(tmp_path, ("0814:010B", "same")))))
    assert (got["unchanged"], got["added"], got["replaced_total"]) == (1, 0, 0)
    (row,) = ok(server.comment_list())["comments"]
    assert row["state"] == "resolved" and row["created_at"] == STAMP


@pytest.mark.parametrize("ref, waits_in_protected_mode", [
    ("00A7:45F80", False), ("0000:0084", True)])
def test_a_stale_row_with_the_files_text_loaded_where_it_waits_is_brought_to_this_build(
        tmp_path: Path, ref: str, waits_in_protected_mode: bool) -> None:
    """A held raw row from another build that the file gives the same text is brought to this
    build at a stop that cannot place it too, so the next stop of its mode places it rather
    than listing it stale. Both directions: past FFFF at the real-mode park, the interrupt
    table's null selector at a protected-mode stop."""
    here, there = ((Protected, FakeSession) if waits_in_protected_mode
                   else (FakeSession, Protected))
    dstate.STATE.session = here()  # type: ignore[assignment]
    install_store()
    dstate.STATE.conf_fingerprint = "now"
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment(ref, "same", fingerprint="then", conf_fingerprint="then")])
    got = ok(server.comment_load(path=str(_file(tmp_path, (ref, "same")))))
    assert (got["unchanged"], got["added"], got["replaced_total"]) == (1, 0, 0)
    dstate.STATE.session = there()  # type: ignore[assignment]
    row = _rows_by_ref()[ref]
    assert (row["state"], row["created_at"]) == ("resolved", STAMP), row


def test_a_file_row_whose_selector_this_stop_does_not_describe_waits_for_one_that_does(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A selector the descriptor tables of this stop do not hold names no byte here, so the
    row waits, and its why names the two stops that place it: a real-mode one, where the
    selector is a paragraph, or one whose tables describe it."""
    tables = {"gdt": [], "ldt": [{"selector": "008C", "base": "00000000", "limit": "0000FFFF",
                                  "type": "1B", "b": 0}]}
    monkeypatch.setattr(machine, "read", lambda *_a, **_k: SimpleNamespace(found=tables,
                                                                           notes=[]))
    pr32_machine(tmp_path / "x.log")
    got = ok(server.comment_load(path=str(_file(
        tmp_path, ("0097:0010", "nowhere"), ("0097:00010000", "past a paragraph")))))
    assert got["added"] == 2 and "0097:0010" in got["note"]
    rows = _rows_by_ref()
    row = rows["0097:0010"]
    assert row["state"] == "unarmable" and "names no descriptor" in row["why"], row
    assert "a real-mode one, or one whose tables describe 0097" in row["why"], row
    assert rows["0097:10000"]["why"].endswith("kept for a stop whose tables describe 0097")
    assert "names no descriptor" in refused(server.comment_add(ref="0097:0010", text="x"),
                                            "bad_argument")


class _ParkedInRealMode(_Booted):
    """`start` parks at the debugger in real mode, before a DOS extender switches the program
    to protected mode, as on dos-djgpp32."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(mode=dcons.REAL_MODE, **kw)


def test_a_file_loaded_at_the_real_mode_park_is_placed_after_the_protected_mode_symbols_load(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """dos-djgpp32's order: `start` parks in real mode, the comment file loads there (its
    protected-mode row waits), the program switches mode, and only then can `symbols_load` read
    the selector's base. A row placed before any map was placed against the conf alone, and the
    map that arrives is what it never had, not another build: it is placed, not stale. The
    control: a row placed over another map is stale over this one."""
    mapf, other = tmp_path / "prog.map", tmp_path / "other.map"
    mapf.write_text("0016dd80 T _main\n", encoding="utf-8")
    other.write_text("0016dd90 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    conf = (tmp_path / "g.conf").resolve()
    cast(dec.DeclarationStore, dstate.STATE.store).apply(adds=[comment(
        "00A7:2000", "over another map",
        fingerprint=build_of(conf, other.read_text(encoding="utf-8")))])
    loaded = ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00045F80", "pm")))))
    assert loaded["added"] == 1 and "00A7:45F80" in loaded["note"]
    booted.mode = "Pr32"
    ok(server.symbols_load(path=str(mapf), base="400000"))
    rows = _rows_by_ref()
    assert (rows["00A7:45F80"]["state"], rows["00A7:45F80"].get("addr")) == (
        "resolved", "0x00445f80"), rows["00A7:45F80"]
    assert rows["00A7:2000"]["state"] == "stale", rows["00A7:2000"]


def _a_new_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NamesFake:
    """The session ends and another `start`s over the same conf and the same store file."""
    dstate.STATE.session = None
    dstate.STATE.store = None
    dstate.STATE.forget_symbols()
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    return booted


@pytest.mark.parametrize("park_row", ["added", "loaded"])
@pytest.mark.parametrize("relinked", [False, True])
def test_a_row_placed_before_the_map_in_an_earlier_session_is_stale_over_a_relinked_map(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, park_row: str, relinked: bool) -> None:
    """A row placed at the park takes the batch of the map this session loads that describes
    it, so the next session judges it by that batch like any other raw row: placed over the
    same map, stale over a relinked one. A real-mode park row no batch describes is judged by
    the conf alone. The control is a row added after the map in the first session."""
    mapf, other = tmp_path / "prog.map", tmp_path / "other.map"
    mapf.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    other.write_text("00001000 T _start\n0016dd90 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    if park_row == "added":
        ref, mode = "0814:0106", dcons.REAL_MODE
        ok(server.comment_add(ref=ref, text="at the park"))
    else:
        ref, mode = "00A7:62310", "Pr32"
        ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00062310", "at the park")))))
    booted.mode = "Pr32"
    ok(server.symbols_load(path=str(mapf), base="400000"))
    ok(server.comment_add(ref="00A7:2000", text="after the map"))
    booted = _a_new_session(tmp_path, monkeypatch)
    booted.mode = "Pr32"
    ok(server.symbols_load(path=str(other if relinked else mapf), base="400000"))
    after_map = _rows_by_ref()["00A7:2000"]
    booted.mode = mode
    park = _rows_by_ref()[ref]
    want = "stale" if relinked else "resolved"
    assert (after_map["state"], park["state"]) == (
        want, want if park_row == "loaded" else "resolved"), (after_map, park)


def test_a_row_placed_before_the_map_is_placed_over_a_second_map_of_the_same_session(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first map's batch is the park row's; a second, relinked map in the same session
    leaves that batch held, and one session runs one program."""
    mapf, other = tmp_path / "prog.map", tmp_path / "other.map"
    mapf.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    other.write_text("00001000 T _start\n0016dd90 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00062310", "at the park")))))
    booted.mode = "Pr32"
    ok(server.symbols_load(path=str(mapf), base="400000"))
    ok(server.symbols_load(path=str(other), base="400000"))
    assert _rows_by_ref()["00A7:62310"]["state"] == "resolved"


def test_a_row_another_session_left_before_any_map_is_not_taken_into_this_sessions_map(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only this session's rows take its map: one an earlier session placed with no map
    loaded names no build but the conf, and it stays stale over a map that describes it."""
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00062310", "no map here")))))
    booted = _a_new_session(tmp_path, monkeypatch)
    booted.mode = "Pr32"
    assert _rows_by_ref()["00A7:62310"]["state"] == "resolved"
    ok(server.symbols_load(path=str(mapf), base="400000"))
    assert _rows_by_ref()["00A7:62310"]["state"] == "stale"


def test_a_store_that_cannot_take_the_maps_build_is_host_failed_and_held_in_memory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The park row's new build is written with the store; a store that cannot be written
    says so, the table is loaded and the row is this build's for the rest of the session."""
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00062310", "at the park")))))
    store = cast(dec.DeclarationStore, dstate.STATE.store)

    def fails() -> None:
        raise OSError("read-only")
    monkeypatch.setattr(store, "_persist", fails)
    booted.mode = "Pr32"
    got = server.symbols_load(path=str(mapf), base="400000")
    assert "symbols are loaded" in refused(got, "host_failed") and got["held_in_memory"] is True
    assert dstate.STATE.table
    assert _rows_by_ref()["00A7:62310"]["state"] == "resolved"


def test_a_park_row_this_stop_cannot_place_leaves_the_map_loaded_and_the_row_as_it_was(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mapf = tmp_path / "prog.map"
    mapf.write_text("00001000 T _start\n0016dd80 T _main\n", encoding="utf-8")
    got, booted = _start_over_a_store(tmp_path, monkeypatch, {}, double=_ParkedInRealMode)
    ok(got)
    ok(server.comment_load(path=str(_file(tmp_path, ("00A7:00062310", "at the park")))))

    def unreadable(*_: Any) -> dict[str, Any]:
        raise ds.Invalid("unexpected_answer", "a descriptor this stop cannot read")
    monkeypatch.setattr(comments._Places, "where", unreadable)
    booted.mode = "Pr32"
    ok(server.symbols_load(path=str(mapf), base="400000"))
    (row,) = cast(dec.DeclarationStore, dstate.STATE.store).comments()
    assert row.fingerprint == dstate.STATE.conf_fingerprint and dstate.STATE.table


def test_save_then_load_into_a_fresh_store_then_save_is_byte_identical(tmp_path: Path) -> None:
    install()
    probe_table()
    for ref, text in (("start", "entry"), ("0814:0106", "the loop"), ("emit", "é \U0001d11e")):
        ok(server.comment_add(ref=ref, text=text))
    first, second = tmp_path / "a.tsv", tmp_path / "b.tsv"
    ok(server.comment_save(dest=str(first)))
    for ref in ("start", "0814:0106", "emit"):
        ok(server.comment_delete(ref=ref))
    install()
    probe_table()
    assert ok(server.comment_load(path=str(first)))["added"] == 3
    ok(server.comment_save(dest=str(second)))
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("source", ["in.tsv", "./in.tsv"])
def test_a_source_that_is_not_absolute_is_refused_without_a_session(source: str) -> None:
    refused(server.comment_load(path=source), "bad_argument")


# ------------------------------------------------------ judged before the session gate

@pytest.mark.parametrize("call", [
    lambda: server.comment_add(ref="", text="x"), lambda: server.comment_add(ref="[g]+2", text="x"),
    lambda: server.comment_add(ref="start+2", text="x"),
    lambda: server.comment_add(ref="0x824B", text="x"),
    lambda: server.comment_add(ref="0814:01G0", text="x"),
    lambda: server.comment_add(ref="10000:0000", text="x"),
    lambda: server.comment_add(ref="start", text="a\tb"),
    lambda: server.comment_add(ref="start", text=" edge"),
    lambda: server.comment_add(ref="start", text="x" * 238),
    lambda: server.comment_delete(ref=""), lambda: server.comment_delete(ref="g->f"),
])
def test_a_bad_ref_or_text_is_bad_argument_with_no_session(call: Any) -> None:
    refused(call(), "bad_argument")


def _performing() -> None:
    install().launch.input_port = None          # no input socket: `perform` asks before any step


def test_a_perform_list_with_a_bad_comment_step_is_refused_whole() -> None:
    _performing()
    got = server.perform(steps=[{"op": "comment_add", "ref": "0814:0106", "text": "fine"},
                                {"op": "comment_add", "ref": "start", "text": ""},
                                {"op": "comment_delete", "ref": "[g]"}])
    message = refused(got, "bad_argument")
    assert "text is empty" in message and "pointer" in message
    assert ok(server.comment_list())["comments_total"] == 0


def test_perform_runs_comment_steps() -> None:
    _performing()
    got = ok(server.perform(steps=[{"op": "comment_add", "ref": "0814:0106", "text": "a"},
                                   {"op": "comment_list"}]))
    assert got["steps_completed"] == 2


# ------------------------------------------------------------ the descriptions name the keys

def _reply_clause(tool: str) -> str:
    doc = getattr(server, tool).__doc__ or ""
    return doc[doc.index("Reply:"):doc.index("Reference:")]


def test_each_description_names_every_key_its_replies_carry(tmp_path: Path) -> None:
    """Every key a reply carries beside the envelope, and every key of the rows it lists, is
    named in backticks in that tool's own Reply clause, which is where a caller looks."""
    install()
    probe_table()
    replies: dict[str, list[dict[str, Any]]] = {t: [] for t in (
        "comment_add", "comment_list", "comment_delete", "comment_save", "comment_load")}
    replies["comment_add"].append(ok(server.comment_add(ref="nowhere", text="unresolved")))
    replies["comment_add"].append(ok(server.comment_add(ref="start", text="a")))
    replies["comment_add"].append(ok(server.comment_add(ref="0824:000B", text="b")))
    replies["comment_list"].append(ok(server.comment_list()))
    dest = tmp_path / "c.tsv"
    dest.write_text(cf.render([cf.Row("gone", "", STAMP, "x")]), encoding="utf-8")
    replies["comment_save"].append(ok(server.comment_save(dest=str(dest))))
    replies["comment_delete"].append(ok(server.comment_delete(ref="nowhere")))
    src = _file(tmp_path, ("start", "c"), ("emit", "d"))
    replies["comment_load"].append(ok(server.comment_load(path=str(src))))
    envelope = {"summary", "status", "session"}
    rows: set[str] = set()
    for tool, got in replies.items():
        clause = _reply_clause(tool)
        keys = {k for r in got for k in r} - envelope
        for r in got:
            for nested in ("comment", "deleted"):
                rows |= set(r.get(nested) or {})
            for listed in ("comments", "replaced_comments"):
                rows |= {k for row in r.get(listed) or [] for k in row}
            keys |= {k for row in r.get("dropped_comments") or [] for k in row}
        unnamed = sorted(k for k in keys if f"`{k}`" not in clause)
        assert not unnamed, (tool, unnamed)
    # A COMMENT ROW IS DESCRIBED ONCE, where the rows are listed; the other replies say theirs
    # are the same rows.
    unnamed_rows = sorted(k for k in rows if f"`{k}`" not in _reply_clause("comment_list"))
    assert not unnamed_rows, unnamed_rows


def test_the_list_description_names_every_state_a_row_can_take() -> None:
    clause = _reply_clause("comment_list")
    for state in ("resolved", "unresolved", "ambiguous", "stale", "unarmable"):
        assert f"`{state}`" in clause, state


def test_each_reply_opens_with_its_one_line(tmp_path: Path) -> None:
    install()
    probe_table()
    assert ok(server.comment_add(ref="start", text="a"))["summary"] == \
        "comment_add start: 0x0000824b, stored"
    assert ok(server.comment_add(ref="nowhere", text="b"))["summary"] == \
        "comment_add nowhere: unresolved, stored"
    assert ok(server.comment_list())["summary"] == "comment_list: 2 comments"
    dest = tmp_path / "c.tsv"
    assert ok(server.comment_save(dest=str(dest)))["summary"] == \
        f"comment_save: 2 comments to {dest}"
    assert ok(server.comment_delete(ref="start"))["summary"] == \
        "comment_delete start: 0x0000824b deleted"
    assert ok(server.comment_load(path=str(dest)))["summary"] == \
        "comment_load: 2 read, 1 added, 0 replaced"


def test_save_refuses_two_comments_at_one_place_and_writes_nothing(tmp_path: Path) -> None:
    """A file names each place once, so a store holding two comments a rebuild brought to one
    place is refused naming both refs."""
    install()
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("0814:010B", "raw"), comment("start", "by name")])
    probe_table()
    dest = tmp_path / "c.tsv"
    message = refused(server.comment_save(dest=str(dest)), "bad_argument")
    assert "'0814:010B'" in message and "'start'" in message and not dest.exists()
    ok(server.comment_delete(ref="0814:010B"))
    ok(server.comment_save(dest=str(dest)))
    install()
    probe_table()
    assert ok(server.comment_load(path=str(dest)))["added"] == 1


def test_a_temporary_the_host_refuses_is_host_failed_and_leaves_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    def refuses(*_: object, **__: object) -> None:
        raise PermissionError("read-only directory")
    install()
    monkeypatch.setattr(os, "replace", refuses)
    assert "read-only" in refused(server.comment_save(dest=str(tmp_path / "c.tsv")),
                                  "host_failed")
    assert list(tmp_path.iterdir()) == []


def test_a_null_selector_is_refused_not_stored() -> None:
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    assert "null selector" in refused(server.comment_add(ref="0000:0100", text="x"),
                                      "bad_argument")
    assert ok(server.comment_list())["comments_total"] == 0
    # HELD ALREADY (a store from a real-mode session), the same address lists, unplaced and why:
    # one row a selector cannot address must not take the whole listing down.
    cast(dec.DeclarationStore, dstate.STATE.store).apply(adds=[comment("0000:0100")])
    (row,) = ok(server.comment_list())["comments"]
    assert row["state"] == "unarmable" and "null selector" in row["why"]


def test_apply_refuses_another_kind_and_a_row_it_does_not_hold(tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    held = comment("start")
    store.apply(adds=[held])
    with pytest.raises(dec.DeclarationError, match="comments only"):
        store.apply(adds=[dec.Declaration("breakpoint", "symbol", "start")])
    with pytest.raises(dec.DeclarationError, match="replace a comment"):
        store.apply(replaces=[(comment("start"), comment("start", "x"))])
    with pytest.raises(dec.DeclarationError, match="remove a comment"):
        store.apply(removes=[comment("start")])
    assert store.comments() == [held] and store.comments()[0] is held


def test_apply_restamps_another_kind_in_place_and_refuses_any_other_change_of_it(
        tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    bp = dec.Declaration("breakpoint", "address", "00A7:2000", fingerprint=dec.PENDING_STAMP)
    store.add(bp)
    (held,) = store.declarations()
    with pytest.raises(dec.DeclarationError, match="comments only"):
        store.apply(replaces=[(held, dec.Declaration("breakpoint", "address", "00A7:2004"))])
    store.apply(replaces=[(held, dataclasses.replace(held, fingerprint="0123456789abcdef"))])
    (row,) = dec.DeclarationStore("g", path=tmp_path / "d.json").declarations()
    assert row == bp and row.fingerprint == "0123456789abcdef"


def test_a_raw_comment_on_a_guest_that_has_not_stopped_yet_is_unplaced_and_says_why(
        tmp_path: Path) -> None:
    _running(tmp_path)
    cast(dec.DeclarationStore, dstate.STATE.store).apply(adds=[comment("0814:010B")])
    (row,) = ok(server.comment_list())["comments"]
    assert row["state"] == "unarmable" and "not stopped yet" in row["why"]


def test_a_comment_from_a_store_that_kept_no_origin_is_marked_orphan() -> None:
    install()
    dstate.STATE.session_origin = "this-session"
    cast(dec.DeclarationStore, dstate.STATE.store).apply(adds=[comment("0814:010B")])
    (row,) = ok(server.comment_list())["comments"]
    assert row["orphan"] is True and row["origin"]["available"] is False


# ------------------------------------- a file a save wrote loads, whatever the machine's state

def test_a_file_saved_before_symbols_load_loads_after_it(tmp_path: Path) -> None:
    """At the park no table is loaded, so `start` has no place yet and a raw comment at the
    byte it will name is saved beside it; the same file loads once the table names that byte."""
    install()
    ok(server.comment_add(ref="start", text="a"))
    ok(server.comment_add(ref="0814:010B", text="b"))
    dest = tmp_path / "c.tsv"
    assert ok(server.comment_save(dest=str(dest)))["comments_total"] == 2
    probe_table()
    assert ok(server.comment_load(path=str(dest)))["unchanged"] == 2
    install()
    probe_table()
    got = ok(server.comment_load(path=str(dest)))
    assert (got["added"], got["comments_total"]) == (2, 2)


def test_a_file_saved_on_a_running_protected_mode_guest_loads_at_the_next_stop(
        tmp_path: Path) -> None:
    """A running guest's selector bases are not read, so a raw protected-mode comment and a
    symbol at its byte are saved as two rows; the stop that places both still takes the file."""
    _running(tmp_path)
    probe_table([("pmsym", 0x401000 - PROBE_BASE)])
    cast(dec.DeclarationStore, dstate.STATE.store).apply(
        adds=[comment("00A7:00001000", "raw"), comment("pmsym", "by name")])
    dstate.STATE.last_stop.update(seq=1, at="00A7:1000", attribution={}, when=0.0, clock="c",
                                  held=[], where={"mode": "Pr32"}, registers={})
    dest = tmp_path / "c.tsv"
    assert ok(server.comment_save(dest=str(dest)))["comments_total"] == 2
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    probe_table([("pmsym", 0x401000 - PROBE_BASE)])
    got = ok(server.comment_load(path=str(dest)))
    assert (got["added"], got["comments_total"]) == (2, 2)
    assert "'00A7:1000' and 'pmsym'" in got["note"]


def test_a_hand_edited_store_holding_one_comment_ref_twice_is_refused_on_load(
        tmp_path: Path) -> None:
    """A comment file holds one row per ref, so a store that holds a ref twice could not be
    saved: it is refused when read, as every comment no file could hold is."""
    row = ('{"kind": "comment", "by": "address", "ref": "0814:%s", '
           f'"created_at": "{STAMP}", "text": "%s"}}')
    (tmp_path / "d.json").write_text(
        '{"g": [' + row % ("010B", "a") + ", " + row % ("10b", "b") + "]}", encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="'0814:010B' twice"):
        dec.DeclarationStore("g", path=tmp_path / "d.json")


def test_apply_refuses_a_second_comment_under_a_held_ref(tmp_path: Path) -> None:
    store = dec.DeclarationStore("g", path=tmp_path / "d.json")
    held = comment("0814:010B", "a")
    store.apply(adds=[held])
    with pytest.raises(dec.DeclarationError, match="'0814:010B' twice"):
        store.apply(adds=[comment("0814:010B", "b")])
    assert store.comments() == [held]
    store.apply(replaces=[(held, comment("0814:010B", "b"))])
    assert [c.text for c in store.comments()] == ["b"]


def test_a_load_that_changes_nothing_writes_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """A header-only file, or one whose every row the store already holds as it is, leaves the
    store's file alone, so a store the host will not let it write is no refusal of a no-op."""
    install()
    probe_table()
    ok(server.comment_add(ref="start", text="entry"))
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    writes: list[int] = []

    def refuses() -> None:
        writes.append(1)
        raise OSError("read-only")
    monkeypatch.setattr(store, "_persist", refuses)
    empty = tmp_path / "empty.tsv"
    empty.write_text(cf.HEADER + "\n", encoding="utf-8")
    for src in (empty, _file(tmp_path, ("start", "entry"))):
        got = ok(server.comment_load(path=str(src)))
        assert got["added"] + got["replaced_total"] == 0
    assert writes == []


def test_a_held_address_in_another_spelling_is_reached_by_its_own_ref(tmp_path: Path) -> None:
    """A store edited by hand may spell an address short; a call or a file row spelling it in
    full reaches it as its own ref even where its place cannot be worked out, rather than
    adding the same ref a second time."""
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    store = cast(dec.DeclarationStore, dstate.STATE.store)
    store.apply(adds=[comment("38:B8000", "short")])
    got = ok(server.comment_add(ref="0038:000B8000", text="full"))
    assert [r["text"] for r in got["replaced_comments"]] == ["short"]
    loaded = ok(server.comment_load(path=str(_file(tmp_path, ("0038:B8000", "file")))))
    assert (loaded["replaced_total"], loaded["added"]) == (1, 0)
    assert [(c.ref, c.text) for c in store.comments()] == [("38:B8000", "file")]
