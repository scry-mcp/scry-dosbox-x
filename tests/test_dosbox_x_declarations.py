"""The declaration store: it survives a rebuild, keeps a symbol that vanished, and does
not let two guests see each other's declarations.

These are pure -- a symbol table is a list of `Symbol`, no emulator -- so the store's four
load-bearing properties (persist, re-resolve, keep-the-vanished, isolate-by-conf) are held
here rather than behind a live session, where a false green would cost a boot to find.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import dosbox_declarations as dec
import dosbox_session as ds
import dosbox_symbols as sym


def _sym(name: str, offset: int, *, idle: bool = False) -> sym.Symbol:
    return sym.Symbol(name, offset, idle=idle)


def _store(tmp_path: Path, conf: str = "guest-a.conf") -> dec.DeclarationStore:
    return dec.DeclarationStore(conf, path=tmp_path / "declarations.json")


# ------------------------------------------------------------------ the model

def test_a_breakpoint_carries_no_watch_fields() -> None:
    """A watch field on a breakpoint is a mistake made inexpressible, not caught later."""
    dec.Declaration("breakpoint", "symbol", "_main")     # fine
    with pytest.raises(dec.DeclarationError, match="watch fields"):
        dec.Declaration("breakpoint", "symbol", "_main", width=4)


def test_a_watch_needs_a_mode_a_format_and_a_coherent_width() -> None:
    dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32", watch_mode="show")
    with pytest.raises(dec.DeclarationError, match="mode"):
        dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32")
    with pytest.raises(dec.DeclarationError, match="format"):
        dec.Declaration("watch", "symbol", "g_rate", width=4, watch_mode="show")
    one = dec.Declaration("watch", "symbol", "g_rate", width=0, fmt="u8", watch_mode="show")
    assert one.width == 1, "a scalar with no width is one value of it"
    # width must be a whole number of the format's own size: 3 bytes of u32 is not.
    with pytest.raises(dec.DeclarationError, match="whole number"):
        dec.Declaration("watch", "symbol", "g", width=3, fmt="u32", watch_mode="show")
    # 3 bytes of u8 IS three values, and is allowed (g_cue's a/b/on).
    dec.Declaration("watch", "symbol", "g_cue", width=3, fmt="u8", watch_mode="change")
    # the wider formats share the branch: 4 bytes of i32/f32 is one value; 5 is not.
    dec.Declaration("watch", "symbol", "g_pos", width=4, fmt="i32", watch_mode="show")
    dec.Declaration("watch", "symbol", "g_gain", width=8, fmt="f32", watch_mode="show")
    with pytest.raises(dec.DeclarationError, match="whole number"):
        dec.Declaration("watch", "symbol", "g", width=5, fmt="i32", watch_mode="show")


def test_unknown_kind_or_by_or_empty_ref_is_refused() -> None:
    with pytest.raises(dec.DeclarationError, match="kind"):
        dec.Declaration("stopwatch", "symbol", "_main")
    with pytest.raises(dec.DeclarationError, match="`by`"):
        dec.Declaration("breakpoint", "guess", "_main")
    with pytest.raises(dec.DeclarationError, match="needs a ref"):
        dec.Declaration("breakpoint", "symbol", "")


# --------------------------------------------------------- persistence (survives restart)

def test_a_declaration_survives_a_new_store_over_the_same_file(tmp_path: Path) -> None:
    """The close/start property: a store built fresh from the same file holds what an
    earlier one added. This is what a persisted declaration is FOR -- surviving the
    emulator closing and the session that drove it restarting."""
    s1 = _store(tmp_path)
    s1.add(dec.Declaration("breakpoint", "symbol", "_uicue_apply"))
    s1.add(dec.Declaration("watch", "symbol", "g_rate", width=4, fmt="u32",
                           watch_mode="change"))
    # A brand-new store object, as a later session would build, reading the same file.
    s2 = _store(tmp_path)
    refs = [(d.kind, d.ref) for d in s2.declarations()]
    assert refs == [("breakpoint", "_uicue_apply"), ("watch", "g_rate")]
    assert s2.declarations()[1].width == 4 and s2.declarations()[1].watch_mode == "change"


def test_a_corrupt_file_refuses_rather_than_silently_discarding(tmp_path: Path) -> None:
    """The declarations are meant to survive interruptions, so a file that cannot be read
    is a refusal to fix, never an empty store that has quietly lost them."""
    (tmp_path / "declarations.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="could not be read"):
        _store(tmp_path)


# ------------------------------------------------------- re-resolution across a rebuild (R4)

def test_a_rebuild_that_moves_a_symbol_re_resolves_to_the_new_offset(tmp_path: Path) -> None:
    """Example R4: the declaration is by NAME, so when the program is rebuilt and the
    symbol moves, resolving against the new table gives the new offset without the
    declaration being sent again. The two tables are the SAME program with the symbol at
    two offsets -- if they were not, this would not be exercising the thing it exists for.
    """
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "_uicue_apply"))
    before = [_sym("_uicue_apply", 0x0003D780), _sym("_main", 0x0016DF20)]
    after = [_sym("_uicue_apply", 0x0003D5E0), _sym("_main", 0x0016DD80)]  # rebuilt: moved

    r1 = s.resolve(before)
    assert [(x.state, x.offset) for x in r1] == [("resolved", 0x0003D780)]
    r2 = s.resolve(after)
    assert [(x.state, x.offset) for x in r2] == [("resolved", 0x0003D5E0)]


def test_a_vanished_symbol_is_kept_unresolved_not_dropped(tmp_path: Path) -> None:
    """Decision 8: a symbol that -O3 inlined away, or that was removed on purpose, STAYS
    in the list, resolves to nothing, and is said out loud -- it may come back."""
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "ensure_soundfont"))
    s.add(dec.Declaration("breakpoint", "symbol", "_main"))
    table = [_sym("_main", 0x0016DD80)]           # ensure_soundfont inlined away

    r = s.resolve(table)
    by_ref = {x.decl.ref: x for x in r}
    assert by_ref["ensure_soundfont"].state == "unresolved"
    assert by_ref["ensure_soundfont"].offset is None
    assert by_ref["_main"].state == "resolved" and by_ref["_main"].offset == 0x0016DD80
    # and it is still STORED, so a later build that brings the symbol back re-resolves it.
    assert "ensure_soundfont" in [d.ref for d in s.declarations()]


def test_a_by_address_declaration_needs_no_resolution(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add(dec.Declaration("watch", "address", "0040:006C", width=2, fmt="u16",
                          watch_mode="change"))
    r = s.resolve([_sym("_main", 0x100)])
    assert len(r) == 1 and r[0].state == "address" and r[0].offset is None


def test_an_ambiguous_name_resolves_to_the_lowest_offset_and_reports_the_count(
        tmp_path: Path) -> None:
    """A name a build defines more than once resolves to the lowest offset AND reports
    `matches > 1`, which is what lets the arming tool refuse it rather than arm the wrong
    one. A single-match resolution reports 1, so the two are distinguishable."""
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "static_helper"))
    s.add(dec.Declaration("breakpoint", "symbol", "_main"))
    table = [_sym("static_helper", 0x2000), _sym("static_helper", 0x1000),
             _sym("_main", 0x100)]
    by_ref = {x.decl.ref: x for x in s.resolve(table)}
    assert by_ref["static_helper"].offset == 0x1000 and by_ref["static_helper"].matches == 2
    assert by_ref["_main"].offset == 0x100 and by_ref["_main"].matches == 1


def test_resolve_name_is_the_single_source_used_by_resolve_and_the_server(
        tmp_path: Path) -> None:
    """The owner's QA call: ONE name->offset resolver. `resolve()` (plural, for
    symbols_load's re-resolution) delegates to `resolve_name`, and the server's live
    resolver consumes the same routine -- so this pins its contract directly: a by-address
    decl is `address`, an absent name `unresolved`, a match carries offset/matches, and the
    chosen symbol's `idle` mark rides through (which the server reads for the marked note)."""
    addr = dec.DeclarationStore.resolve_name(
        dec.Declaration("breakpoint", "address", "00A7:1000"), [])
    assert addr.state == "address"
    absent = dec.DeclarationStore.resolve_name(
        dec.Declaration("breakpoint", "symbol", "nope"), [_sym("other", 0x1)])
    assert absent.state == "unresolved"
    marked = dec.DeclarationStore.resolve_name(
        dec.Declaration("breakpoint", "symbol", "m"), [_sym("m", 0x1000, idle=True)])
    assert marked.state == "resolved" and marked.offset == 0x1000
    assert marked.matches == 1 and marked.idle is True
    # and resolve() (plural) gives the SAME answer per declaration, since it delegates.
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "m"))
    one = s.resolve([_sym("m", 0x1000, idle=True)])[0]
    assert (one.offset, one.matches, one.idle) == (0x1000, 1, True)


# -------------------------------------------------------------- isolation by conf (dec. 24)

def test_two_confs_do_not_see_each_others_declarations(tmp_path: Path) -> None:
    """Decision 24: keyed by conf identity over one file. A symbol from another binary
    would arm at a plausible and wrong address, so the two lists never mix."""
    path = tmp_path / "declarations.json"
    a = dec.DeclarationStore("dos-djgpp32.conf", path=path)
    b = dec.DeclarationStore("dos-real16.conf", path=path)
    a.add(dec.Declaration("breakpoint", "symbol", "_uicue_apply"))
    b.add(dec.Declaration("breakpoint", "symbol", "ATRCT_RUN"))
    # each sees only its own, whether read live or rebuilt from the shared file.
    assert [d.ref for d in a.declarations()] == ["_uicue_apply"]
    assert [d.ref for d in b.declarations()] == ["ATRCT_RUN"]
    a_reloaded = dec.DeclarationStore("dos-djgpp32.conf", path=path)
    assert [d.ref for d in a_reloaded.declarations()] == ["_uicue_apply"]


def test_an_empty_conf_identity_is_refused(tmp_path: Path) -> None:
    with pytest.raises(dec.DeclarationError, match="conf identity"):
        dec.DeclarationStore("", path=tmp_path / "declarations.json")


# ------------------------------------------------------------------ add / remove (dec. 10)

def _boom(*_a: object, **_k: object) -> None:
    raise AssertionError("_persist was called when nothing should have been written")


def test_an_exact_duplicate_is_a_no_op_that_says_so(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner's call at QA: a declaration script re-run after every compile meets its
    own earlier declarations, and a refusal there defeats the store's reason to persist.
    `add` answers True for a new declaration and False for one already held, stores
    nothing twice, and writes nothing to disk for the no-op."""
    s = _store(tmp_path)
    assert s.add(dec.Declaration("breakpoint", "symbol", "_main")) is True
    # A NO-OP MUST NOT PERSIST, proved without a clock: `_persist` goes through
    # `json.dump`, so if the duplicate `add` tried to write, this raises. mtime is a
    # filesystem-resolution proxy (HFS+/FAT tick to a whole second) and was the weaker
    # check its own name promised to make.
    monkeypatch.setattr(json, "dump", _boom)
    assert s.add(dec.Declaration("breakpoint", "symbol", "_main")) is False
    monkeypatch.undo()
    assert [d.ref for d in s.declarations()] == ["_main"]
    # a watch duplicate goes through the same equality, fields and all.
    w = dec.Declaration("watch", "symbol", "g", width=4, fmt="u32", watch_mode="show")
    assert s.add(w) is True
    assert s.add(w) is False
    assert len(s.declarations()) == 2


def test_an_interrupt_breakpoint_is_a_declaration_by_number(tmp_path: Path) -> None:
    """An interrupt breakpoint has no symbol to resolve and is held by the debugger's own
    spelling, so it is declared `by="address"` and refuses a symbol or any watch field.
    It clears with the breakpoint family (decision 10's "without touching watches")."""
    s = _store(tmp_path)
    # THE REF IS THE DEBUGGER'S ROW SPELLING, not `INT 21`: the server matches it against
    # the live BPLIST by equality and parses it back to clear it.
    assert s.add(dec.Declaration("interrupt", "address", "BPINT 21 AH=4C")) is True
    with pytest.raises(dec.DeclarationError, match="row spelling"):
        dec.Declaration("interrupt", "address", "INT 21")           # the wrong spelling
    with pytest.raises(dec.DeclarationError, match="row spelling"):
        dec.Declaration("interrupt", "address", "BPINT 21 AH=")     # malformed
    with pytest.raises(dec.DeclarationError, match="never by a symbol"):
        dec.Declaration("interrupt", "symbol", "BPINT 21")
    with pytest.raises(dec.DeclarationError, match="carries no watch fields"):
        dec.Declaration("interrupt", "address", "BPINT 21", width=4)
    with pytest.raises(dec.DeclarationError, match="needs a ref"):
        dec.Declaration("interrupt", "address", "")
    # A HAND-EDITED FILE WITH THE WRONG SPELLING IS REFUSED ON LOAD, not on next clear:
    # from_dict runs through __post_init__, so the corrupt ref cannot enter a live store.
    (tmp_path / "declarations.json").write_text(
        '{"' + s._conf + '": [{"kind": "interrupt", "by": "address", "ref": "INT 21"}]}',
        encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="row spelling"):
        dec.DeclarationStore(s._conf, path=tmp_path / "declarations.json")


def test_one_address_may_not_be_both_show_and_change_watch(tmp_path: Path) -> None:
    """One ref is one watch: a change watch reports its value at every stop already, so a show
    watch beside it would be the same reading twice, and `watch_clear` of the ref names one."""
    s = _store(tmp_path)
    s.add(dec.Declaration("watch", "symbol", "g_cue", width=1, fmt="u8", watch_mode="show"))
    with pytest.raises(dec.DeclarationError, match="both a show AND a change watch"):
        s.add(dec.Declaration("watch", "symbol", "g_cue", width=1, fmt="u8",
                              watch_mode="change"))
    # a DIFFERENT address may carry the other half.
    s.add(dec.Declaration("watch", "symbol", "g_rate", width=1, fmt="u8",
                          watch_mode="change"))


def test_remove_clears_all_by_ref_or_by_kind_and_the_two_compose(tmp_path: Path) -> None:
    """Decision 10: clear one by name, clear all, and clear breakpoints WITHOUT touching
    watches (and the reverse)."""
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "_main"))
    s.add(dec.Declaration("breakpoint", "symbol", "_uicue_apply"))
    s.add(dec.Declaration("watch", "symbol", "_main", width=4, fmt="u32",
                          watch_mode="change"))

    # clear only breakpoints; the watch on the same ref survives.
    assert s.remove(kind="breakpoint") == 2
    assert [(d.kind, d.ref) for d in s.declarations()] == [("watch", "_main")]

    s.add(dec.Declaration("breakpoint", "symbol", "_main"))
    # clear only ref "_main" of kind breakpoint; the watch on "_main" survives.
    assert s.remove(ref="_main", kind="breakpoint") == 1
    assert [(d.kind, d.ref) for d in s.declarations()] == [("watch", "_main")]

    # clear everything.
    assert s.remove() == 1
    assert s.declarations() == []


def test_remove_persists(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "_main"))
    s.remove(ref="_main")
    assert dec.DeclarationStore("guest-a.conf",
                                path=tmp_path / "declarations.json").declarations() == []


def test_remove_with_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    with pytest.raises(dec.DeclarationError, match="kind is one of"):
        _store(tmp_path).remove(kind="stopwatch")


# ---------------------------------------------------------- where the file lives (dec. 9)

def test_default_path_is_a_durable_state_dir_not_the_project(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Decision 9 wants the declarations to survive a session; a cache dir or the
    emulator's working directory (the caller's project) would be the wrong home."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    p = dec.default_path()
    assert p == tmp_path / "state" / "dosbox-x-debug" / "declarations.json"
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    fallback = dec.default_path()
    assert fallback.parts[-3:] == (".local", "state", "dosbox-x-debug") or \
        fallback.name == "declarations.json"
    assert "cache" not in str(fallback).lower()


# --------------------------------------------------------- the file's own failure modes

def test_a_file_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    """A JSON array or scalar is not conf-to-declarations; refuse it rather than crash
    deeper or silently start empty over data somebody meant to keep."""
    (tmp_path / "declarations.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="not a mapping"):
        _store(tmp_path)


def test_a_conf_mapping_to_a_non_list_is_refused_not_a_traceback(tmp_path: Path) -> None:
    """A hand-edited `{"guest-a.conf": "oops"}` iterates the string into from_dict and
    escapes as an AttributeError unless it is caught; it must be a named refusal instead."""
    (tmp_path / "declarations.json").write_text('{"guest-a.conf": "oops"}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="not a list"):
        _store(tmp_path)


def test_a_non_object_declaration_entry_is_refused(tmp_path: Path) -> None:
    (tmp_path / "declarations.json").write_text('{"guest-a.conf": [1, 2]}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="not an object"):
        _store(tmp_path)


def test_a_stored_watch_with_a_non_integer_width_is_refused(tmp_path: Path) -> None:
    (tmp_path / "declarations.json").write_text(
        '{"guest-a.conf": [{"kind":"watch","by":"symbol","ref":"g",'
        '"width":"three","fmt":"u8","watch_mode":"read"}]}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="non-integer width"):
        _store(tmp_path)


def test_a_failed_write_cleans_up_its_temporary(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The atomic-write promise: if the write fails, no half-written file and no temp are
    left behind, so the next read still sees the last good state."""
    s = _store(tmp_path)
    s.add(dec.Declaration("breakpoint", "symbol", "_main"))       # one good write

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(ds.Invalid, match="disk full") as e:
        s.add(dec.Declaration("breakpoint", "symbol", "_uicue_apply"))
    assert e.value.code == "host_failed", "the server chose the store's path"
    assert not list(tmp_path.glob(".*.tmp")), "a temporary write file was left behind"
    # the last GOOD state is intact: the failed add did not corrupt the file.
    monkeypatch.undo()
    reloaded = dec.DeclarationStore("guest-a.conf", path=tmp_path / "declarations.json")
    assert [d.ref for d in reloaded.declarations()] == ["_main"]


# --------------------------------------------- age and origin (owner's decision)

def test_a_declaration_remembers_when_and_by_which_session_it_was_made(
        tmp_path: Path) -> None:
    """MEASURED on a real guest: a raw-address breakpoint armed in one session on the
    wrong selector re-armed itself in the next, and nothing in the store could say which
    session had left it. A declaration carries `created_at` and `origin`; both round-trip
    through the file; neither takes part in equality, so re-declaring the same thing from a
    new session is the SAME declaration (adopted, below), not a second one."""
    a = dec.Declaration("breakpoint", "address", "00A7:5C6F0",
                        created_at="2026-09-03T10:00:00", origin="s1")
    b = dec.Declaration("breakpoint", "address", "00A7:5C6F0",
                        created_at="2026-09-03T11:00:00", origin="s2")
    assert a == b
    assert dec.Declaration.from_dict(a.to_dict()) == a
    assert dec.Declaration.from_dict(a.to_dict()).origin == "s1"
    st = _store(tmp_path)
    assert st.add(a) is True
    assert st.add(b) is False                       # already held ...
    kept = st.declarations()[0]
    assert kept.origin == "s2" and kept.created_at == "2026-09-03T11:00:00", (
        "... and ADOPTED by the session that re-declared it: the origin moves to s2")
    again = _store(tmp_path)                       # re-read from disk
    assert again.declarations()[0].origin == "s2"


def test_a_raw_address_from_another_session_is_stale_and_a_symbol_is_not() -> None:
    """The owner's decision: a by-ADDRESS declaration left by another session
    is kept but not re-armed, marked stale; a by-SYMBOL one re-resolves as always, because
    a name is re-placed against the new table while a raw address is re-armed blind. One
    with no origin recorded (a file from before this field) is stale too: it is exactly
    the case nobody can vouch for."""
    one = dec.Build.of("c", [("_main", 0x1000), ("_rest", 0x9000)])
    relinked = dec.Build.of("c", [("_main", 0x1010), ("_rest", 0x9000)])
    addr = dec.Declaration("breakpoint", "address", "00A7:5C6F0", origin="s1",
                           fingerprint=one.stamp)
    name = dec.Declaration("breakpoint", "symbol", "_main", origin="s1", fingerprint=one.stamp)
    legacy = dec.Declaration("breakpoint", "address", "0040:006C")

    def at() -> int:
        return 0x2000
    assert dec.raw_staleness(addr, "c", [relinked], at) == "other"
    assert dec.raw_staleness(addr, "c", [one], at) is None, (
        "another session over the same build re-arms")
    assert dec.raw_staleness(name, "c", [relinked], at) is None
    assert dec.raw_staleness(legacy, "c", [], at) == "no_conf"
    assert dec.raw_staleness(addr, None, [relinked], at) is None, (
        "no conf recorded for the session: nothing judged")


def test_adoption_takes_only_the_halves_the_re_declaration_carries(tmp_path: Path) -> None:
    """A half-stamped duplicate must not blank the other half: a first version turned an
    origin into None (a legacy declaration, stale everywhere) when the re-declaration
    carried only a stamp. And a watch or an interrupt is never stale: nothing re-arms
    them across sessions."""
    st = _store(tmp_path)
    st.add(dec.Declaration("breakpoint", "address", "00A7:5C6F0",
                           created_at="t1", origin="s1"))
    st.add(dec.Declaration("breakpoint", "address", "00A7:5C6F0", created_at="t2"))
    kept = st.declarations()[0]
    assert (kept.origin, kept.created_at) == ("s1", "t2"), kept
    st.add(dec.Declaration("breakpoint", "address", "00A7:5C6F0"))
    assert st.declarations()[0].origin == "s1"
    watch = dec.Declaration("watch", "address", "0040:006C", width=4, fmt="u32",
                            watch_mode="change", origin="s1")
    intr = dec.Declaration("interrupt", "address", "BPINT 21", origin="s1")
    for decl in (watch, intr):
        assert dec.raw_staleness(decl, "c", [], lambda: None) is None


def test_a_stored_declaration_lacking_a_key_is_refused_not_named_none(tmp_path: Path) -> None:
    """`str(d.get("ref"))` turns an ABSENT ref into the four-letter name "None", a truthy
    ref that sails past the refusal written for it."""
    (tmp_path / "declarations.json").write_text(
        '{"guest-a.conf": [{"kind":"watch","by":"symbol","width":4,"fmt":"u32",'
        '"watch_mode":"read"}]}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="lacks `ref`"):
        _store(tmp_path)
    (tmp_path / "declarations.json").write_text(
        '{"guest-a.conf": [{"by":"symbol","ref":"g"}]}', encoding="utf-8")
    with pytest.raises(dec.DeclarationError, match="lacks `kind`"):
        _store(tmp_path)


def test_one_ref_carries_one_watch_shape(tmp_path: Path) -> None:
    """A ref declared again with another width or format would be a SECOND declaration under
    the same name: two rows in the store, one debugger row between them, and a clear by ref
    that could only half account for it. Refused until it is cleared."""
    store = _store(tmp_path)
    store.add(dec.Declaration("watch", "symbol", "g", width=4, fmt="u32", watch_mode="change"))
    with pytest.raises(dec.DeclarationError, match="already declared.*width 4.*clear it"):
        store.add(dec.Declaration("watch", "symbol", "g", width=8, fmt="u32",
                                  watch_mode="change"))
    with pytest.raises(dec.DeclarationError, match="already declared"):
        store.add(dec.Declaration("watch", "symbol", "g", width=4, fmt="i32",
                                  watch_mode="change"))
    assert store.add(dec.Declaration("watch", "symbol", "g", width=4, fmt="u32",
                                     watch_mode="change")) is False, "the same shape adopts"
    assert len(store.declarations()) == 1


def test_resolve_name_through_the_index_is_the_scan_resolution() -> None:
    """One table, one index, every declaration: the indexed resolution carries the same
    state, offset, match count and idle mark as the scan, duplicate names included."""
    table = [_sym("_a", 0x300), _sym("_a", 0x100, idle=True), _sym("_b", 0x200)]
    index = sym.index_by_name(table)
    for ref in ("_a", "_b", "_missing"):
        d = dec.Declaration("breakpoint", "symbol", ref)
        scan = dec.DeclarationStore.resolve_name(d, table)
        fast = dec.DeclarationStore.resolve_name(d, table, index)
        assert (fast.state, fast.offset, fast.matches, fast.idle) == (
            scan.state, scan.offset, scan.matches, scan.idle), ref
    assert dec.DeclarationStore.resolve_name(
        dec.Declaration("breakpoint", "symbol", "_a"), table, index).offset == 0x100


def test_a_write_that_fails_leaves_the_store_as_the_file_holds_it(tmp_path: Path) -> None:
    """The file is the record: an add or a remove whose write fails changes nothing, so a
    caller told INVALID does not meet the row listed anyway, and a clear that failed does not
    come back at the next start as a breakpoint the caller thought gone."""
    path = tmp_path / "decl.json"
    store = dec.DeclarationStore("/conf", path=path)
    store.add(dec.Declaration("breakpoint", "symbol", "_main"))
    before = store.declarations()
    path.unlink()
    path.mkdir()                                  # the next write cannot replace it
    with pytest.raises(dec.DeclarationError):
        store.add(dec.Declaration("breakpoint", "symbol", "_other"))
    assert store.declarations() == before, store.declarations()
    with pytest.raises(dec.DeclarationError):
        store.remove(ref="_main")
    assert store.declarations() == before, store.declarations()


def test_a_full_volume_under_an_add_is_a_refusal_never_a_traceback(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The host refusing the write (a full volume, a permission) comes out as the store's own
    error, which the tools answer as a refusal, and the row is not kept."""
    from scry_core import fresh

    store = dec.DeclarationStore("/conf", path=tmp_path / "decl.json")

    def full(*_a: object, **_k: object) -> None:
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(fresh, "replace", full)
    with pytest.raises(dec.DeclarationError, match="No space left"):
        store.add(dec.Declaration("breakpoint", "symbol", "_main"))
    assert store.declarations() == []
