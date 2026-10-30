"""COMMENTS: notes on places in the program, kept with the conf's declarations and carried to
and from the comment file versioned beside the symbol file.

By symbol a comment follows the symbol through a rebuild; by `SEG:OFF` it stays where it was put
and is `stale` while the batch that described it is not held unchanged. Nothing is armed.

The place is the linear address, so aliasing spellings (`start`, `0824:000B`, `0814:010B`) are
one comment. A place this instant cannot work out is identified by its ref.

Aliasing, and whether a raw ref lands at all, depend on the table loaded and the stop's mode. So
a save refuses two comments at one place only where it can place both, and a load refuses a file
for neither: such rows are kept and named, and a row saved in protected mode is kept `unarmable`
until a stop whose mode holds it. `comment_write(method="add")` still refuses such an address.
"""
from __future__ import annotations

import dataclasses
import os
import stat
from pathlib import Path
from typing import Any

from scry_core import fresh, judges, prose

from scry_dosbox_x import arming, code, grammar, paths, placement
from scry_dosbox_x import comment_file as cf
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import dump as dumping
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x import symbols as sym
from scry_dosbox_x.state import STATE

#: A comment file made new is readable by everyone, whatever the server's umask.
NEW_FILE_MODE = 0o644

#: Why a raw comment is `stale`, by `declarations.raw_staleness`'s answer.
_STALE_WHY = {
    "other": ("a raw address commented over another build: listed where it points now, which "
              "may not be the same code. Comment it again here, or load its file, to bring it "
              "to this build, or comment the symbol, which follows a rebuild"),
    "unrecorded": ("a raw address an earlier session commented before any map and that session "
                   "loaded none, so no build beyond the conf was recorded and which program it "
                   "names cannot be known: listed where it points now. Comment it again here, "
                   "or load its file, to bring it to this build, or comment the symbol, which "
                   "follows a rebuild"),
    "pending": ("a raw address commented where its place was not known while a map was held, "
                "in a session that loaded no map after it, so it was never placed under a map "
                "and which build it names was not recorded: listed where it points now. "
                "Comment it again here, or load its file, at a stop that places it"),
    "no_conf": ("a raw address stored without the conf it was placed over, so before a map it "
                "cannot be told from another conf's: judged by its build alone, it is placed "
                "again once the maps it was commented under are loaded. Comment it again here, "
                "or load its file, to bring it to this build"),
}

#: What a mode without a readable base says, while the guest runs.
_RUNNING_WHY = ("the machine runs: a selector's base is read at a stop, so this raw address is "
                "placed then")


class _Places:
    """Where each comment lands at this instant; the machine is surveyed at most once, only for
    a raw address and only while stopped, so a listing on a running guest types nothing."""

    def __init__(self, session: ds.Session, segs: code.Segments | None = None) -> None:
        self.session = session
        self.stopped = session.at_debugger()
        self._segs: code.Segments | None = segs

    def mode(self) -> str | None:
        """This stop's cpu mode as the debugger spells it; the last stop's while the guest
        runs, None before any."""
        if self.stopped:
            if self._segs is None:
                self._segs = code.segments_at_stop(self.session)
            return self._segs.mode
        last = STATE.last_machine()
        return None if last is None else last[0]

    def of(self, decl: dec.Declaration) -> dict[str, Any]:
        """A held comment's place: `where` its ref lands, `stale` for a raw address over another
        build. One this stop cannot place keeps `refuse` and says what it waits for."""
        again = "Comment it again, or load its file,"
        if (mode := placement.waits(decl, self.mode)) not in (None, dec.UNPLACED):
            return {"state": "unarmable", "why": placement.waits_why(mode, again)}
        place = self.where(decl.by, decl.ref)
        if "refuse" in place:
            place["why"] = f"{place['refuse']}; {place['waits']}"
        elif mode == dec.UNPLACED and "linear" in place:
            # Placing is a write, made by a call.
            return {"state": "unarmable", "why": placement.waits_why(mode, again)}
        if "linear" in place and (stale := placement.staleness(
                decl, lambda: place["linear"])) is not None:
            place.update(state="stale", why=_STALE_WHY[stale])
        return place

    def where(self, by: str, ref: str) -> dict[str, Any]:
        """`state`, `linear` once placed, `why` unless `resolved`. A place a call must refuse
        carries `refuse` (the refusal's words) and `waits` (the stop a held row waits for)."""
        if by == "symbol":
            return _symbol_place(ref)
        seg, off = placement.parse_seg_off(ref)
        mode = self.mode()
        if mode is None:
            return {"state": "unarmable", "why": (
                "the machine has not stopped yet, so its mode is not known and a SEG:OFF cannot "
                "be placed")}
        if grammar.real_segments(mode):
            if off > grammar.offset_ceiling(mode):
                why = f"{ref} has an offset past FFFF, the last a real-mode segment holds"
                return {"state": "unarmable", "why": why, "refuse": why, "waits": (
                    _waits_for_a_selector(seg, off) if seg <= code.NULL_SELECTOR_MAX else
                    "kept for a protected-mode stop, where an offset runs past FFFF")}
            return {"state": "resolved", "linear": dumping.real_linear(seg, off)}
        if not self.stopped:
            return {"state": "unarmable", "why": _RUNNING_WHY}
        assert self._segs is not None
        try:
            base, limit = self._segs.base(seg), self._segs.limit(seg)
        except ds.Invalid as e:
            # A selector that addresses nothing is the caller's to fix; only an unreadable base
            # leaves the place for later.
            if e.code == "bad_argument":
                return {"state": "unarmable", "why": str(e), "refuse": str(e),
                        "waits": _waits_for_a_selector(seg, off)}
            if e.code not in ("no_channel", "unexpected_answer"):
                raise
            return {"state": "unarmable", "why": f"{seg:04X}'s base cannot be read at this stop: "
                                                 f"{e}"}
        if off > limit:
            why = (f"{ref} is past {seg:04X}'s limit {limit:X}, so it names no byte of that "
                   "segment")
            return {"state": "unarmable", "why": why, "refuse": why,
                    "waits": f"kept for a stop at which {seg:04X}'s limit reaches it"}
        return {"state": "resolved", "linear": base + off}


def _waits_for_a_selector(seg: int, off: int) -> str:
    """The stop a raw row waits for when this protected-mode stop has no descriptor for it."""
    real = off <= grammar.offset_ceiling(grammar.REAL_MODE)
    if seg <= code.NULL_SELECTOR_MAX:
        return (f"kept for a real-mode stop, where {seg:04X} is a paragraph" if real else
                "kept, though no stop places it: the null selector addresses nothing and a "
                "real-mode segment ends at FFFF")
    return (f"kept for a stop that places it: a real-mode one, or one whose tables describe "
            f"{seg:04X}" if real else f"kept for a stop whose tables describe {seg:04X}")


def _symbol_place(name: str) -> dict[str, Any]:
    """A symbol's place against the table loaded now, or why there is none."""
    if not STATE.table:
        return {"state": "unresolved", "why": "no symbol table is loaded: `symbols_load` one and "
                                              "this comment is placed against it"}
    hits = STATE.name_index.get(sym.folded(name), [])
    if not hits:
        return {"state": "unresolved", "why": f"{name!r} is not a symbol of the table loaded "
                                              "now: kept, it may be back after a rebuild"}
    if len(hits) > 1:
        return {"state": "ambiguous", "why": prose.ambiguous_name(
            name, placement.candidates(name), placement.IN_THIS_BUILD)}
    try:
        return {"state": "resolved", "linear": placement.linear_of(hits[0])}
    except sym.BadSymbolText as e:
        return {"state": "unarmable", "why": str(e)}


def _key(ref: str, place: dict[str, Any]) -> tuple[str, Any]:
    """What makes two comments one: the linear address once placed, else the ref as stored."""
    if "linear" in place:
        return ("linear", place["linear"])
    return ("ref", ref)


def _row(decl: dec.Declaration, place: dict[str, Any]) -> dict[str, Any]:
    row = arming.decl_row(decl)
    if arming.orphan(decl):
        row["orphan"] = True
    row["text"] = decl.text
    if "linear" in place:
        row["addr"] = st.flat(place["linear"])
    row["state"] = place["state"]
    if "why" in place:
        row["why"] = place["why"]
    return row


def _new(places: _Places, by: str, ref: str, text: str,
         created_at: str | None = None) -> dec.Declaration:
    """A comment of this session, batch, stop mode and conf; stamped now unless `created_at`
    is carried over."""
    linear = places.where(by, ref).get("linear")
    decl = dataclasses.replace(arming.declare("comment", by, ref, linear,
                                              cpu=places.mode() if linear is not None else None,
                                              text=text),
                               conf_fingerprint=STATE.conf_fingerprint)
    if created_at is None:
        return decl
    return dataclasses.replace(decl, created_at=created_at)


def _taken(places: _Places, old: dec.Declaration, text: str,
           created_at: str | None) -> dec.Declaration:
    """A held comment given `text` at this stop, placed as a new one is. A row this stop cannot
    place keeps its cpu mode; one that would be stamped `pending` keeps its whole record and
    changes only text and date."""
    new = _new(places, old.by, old.ref, text, created_at=created_at)
    if placement.waits(old, places.mode) in (None, dec.UNPLACED) \
            or "linear" in places.where(old.by, old.ref):
        return new
    if new.fingerprint == dec.PENDING_STAMP:
        return dataclasses.replace(old, text=text, created_at=new.created_at)
    return dataclasses.replace(new, cpu_mode=old.cpu_mode)


def _this_sessions(decl: dec.Declaration, places: _Places) -> bool:
    """Whether a raw comment already carries what `_taken` would give it at this stop."""
    new = _taken(places, decl, decl.text, decl.created_at)
    return (decl.origin, decl.fingerprint, decl.conf_fingerprint, decl.cpu_mode) == (
        new.origin, new.fingerprint, new.conf_fingerprint, new.cpu_mode)


def park_rows_take_the_map(session: ds.Session) -> str | None:
    """Stamp this session's raw comments and breakpoints that no batch described when placed
    (`dec.PENDING_STAMP`) with what describes them now: a protected-mode program parks in real
    mode, where its comment file loads, and its map arrives only at the later protected-mode
    stop. Another session's rows are left. Returns the store's write error, else None."""
    store, conf = STATE.store, STATE.conf_fingerprint
    if store is None or STATE.session_origin is None or conf is None \
            or not session.at_debugger():
        return None              # a row is placed only at a stop
    mine = [d for d in (*store.comments(), *store.declarations())
            if dec.is_raw_code(d.kind, d.by) and d.origin == STATE.session_origin
            and (d.cpu_mode is None or d.fingerprint == dec.PENDING_STAMP
                 or (d.kind == "comment" and d.fingerprint == conf))]
    places = _Places(session)
    taken = []
    for d in mine:
        try:
            # A row placed in the other mode is not this stop's to place.
            linear = (None if placement.waits(d, places.mode) not in (None, dec.UNPLACED)
                      else places.where(d.by, d.ref).get("linear"))
        except ds.Invalid:
            linear = None
        if linear is None:
            continue        # a place this stop cannot work out waits for a later load to take it
        stamp = placement.stamp_at(linear, raw=True)
        mode = placement.mode_word(places.mode())
        if (stamp, mode) != (d.fingerprint, d.cpu_mode):
            taken.append((d, dataclasses.replace(d, fingerprint=stamp, cpu_mode=mode)))
    try:
        store.apply(replaces=taken)
    except dec.StoreWriteError as e:
        return str(e)
    return None


def _apply(store: dec.DeclarationStore, **changes: Any) -> None:
    """One write of the store; a failed write is the host's refusal, nothing changed."""
    try:
        store.apply(**changes)
    except dec.StoreWriteError as e:
        raise ds.Invalid("host_failed", str(e)) from None


def _own_ref(decl: dec.Declaration) -> str:
    """A held comment's ref as a call spells it (a hand-edited store may hold one short)."""
    return dec.canonical_ref(decl.ref, decl.by)


def _reach(held: list[tuple[dec.Declaration, dict[str, Any]]], canonical: str,
           key: tuple[str, Any]) -> tuple[dec.Declaration, dict[str, Any]] | None:
    """The comment a call reaches: the one whose ref it spells, else the first at its place."""
    own = next((h for h in held if _own_ref(h[0]) == canonical), None)
    if own is not None:
        return own
    return next((h for h in held if _key(h[0].ref, h[1]) == key), None)


def _placed_comments(places: _Places,
                     store: dec.DeclarationStore) -> list[tuple[dec.Declaration, dict[str, Any]]]:
    return [(d, places.of(d)) for d in store.comments()]


def notes(segs: code.Segments) -> dict[int, str]:
    """Each comment placed at this stop, by its linear address, the stop's survey reused: what
    `disassemble` and a stop's `instruction` show beside the code."""
    store = STATE.store
    if store is None or not store.comments():
        return {}
    places = _Places(segs.session, segs)
    return {place["linear"] & 0xFFFFFFFF: d.text for d, place in _placed_comments(places, store)
            if place.get("state") == "resolved" and "linear" in place}


def _the_ref(ref: str, places: _Places) -> tuple[str, str, dict[str, Any]]:
    """A caller's ref as stored (`by`, canonical) and its place now; refused here if bad."""
    by = placement.decide_by(ref)
    canonical = dec.canonical_ref(ref, by)
    place = places.where(by, canonical)
    if place["state"] == "ambiguous":
        raise ds.Invalid("ambiguous_ref", place["why"])
    if "refuse" in place:
        raise ds.Invalid("bad_argument", place["refuse"])
    return by, canonical, place


def _note(place: dict[str, Any]) -> dict[str, Any]:
    return {"note": place["why"]} if "why" in place else {}


def _shown(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    return rows[:st.ROWS_SHOWN], len(rows) > st.ROWS_SHOWN


# ------------------------------------------------------------------------------- the tools

def add_comment(session: ds.Session, ref: str, text: str) -> dict[str, Any]:
    """The body of the `comment_write(method="add")` tool."""
    store = arming.current_store()
    session.require_stopped("a comment, whose raw address is read in the mode of a stop")
    places = _Places(session)
    by, canonical, place = _the_ref(ref, places)
    held = _reach(_placed_comments(places, store), canonical, _key(canonical, place))
    replaced: list[dict[str, Any]] = []
    if held is None:
        new = _new(places, by, canonical, text)
        _apply(store, adds=[new])
    else:
        old, old_place = held
        new = _taken(places, old, text, None)
        place = places.of(new)
        _apply(store, replaces=[(old, new)])
        replaced.append(_row(old, old_place))
    return st.reply(comment=_row(new, place), replaced_comments=replaced,
                    **_store_fields(store), **_note(place))


def _store_fields(store: dec.DeclarationStore) -> dict[str, Any]:
    """The declaration store a call read or changed; `path` alone names a file a tool wrote."""
    return {"declarations": {"persistent": True, "path": str(store.path)}}


def comment_list(session: ds.Session) -> dict[str, Any]:
    """The body of the `comment_list` tool."""
    store = arming.current_store()
    places = _Places(session)
    rows = [_row(d, p) for d, p in _placed_comments(places, store)]
    shown, truncated = _shown(rows)
    running: dict[str, Any] = {} if places.stopped else {"last_stop": STATE.dated()}
    return st.reply(comments=shown, comments_total=len(rows), truncated=truncated,
                    **_store_fields(store), **running)


def delete_comment(session: ds.Session, ref: str) -> dict[str, Any]:
    """The body of the `comment_write(method="delete")` tool."""
    store = arming.current_store()
    session.require_stopped("a comment's place, read in the mode of a stop")
    places = _Places(session)
    by = placement.decide_by(ref)
    canonical = dec.canonical_ref(ref, by)
    held = _reach(_placed_comments(places, store), canonical,
                  _key(canonical, places.where(by, canonical)))
    if held is None:
        refs = [d.ref for d in store.comments()]
        raise ds.Invalid("unknown_ref",
            f"no comment is at {ref!r}, by its ref or its place; the store holds "
            f"{refs[:st.ROWS_SHOWN] if refs else 'none'}")
    old, old_place = held
    _apply(store, removes=[old])
    return st.reply(deleted=_row(old, old_place), **_store_fields(store), **_note(old_place))


# ------------------------------------------------------------------------------- the file

def _judged_dest(dest: str, store: dec.DeclarationStore) -> tuple[Path, list[cf.Row] | None]:
    """`dest` as a file this call may write, and the comment rows already there (None if none);
    a link, a non-regular file, a non-comment file and the store's own file are refused."""
    path = paths.absolute("dest", dest)
    try:
        if path.is_symlink():
            raise ds.Invalid("bad_argument",
                f"dest: {path} is a link; name the file itself, so what is replaced is what "
                "was named")
        if not path.parent.is_dir():
            raise ds.Invalid("bad_argument",
                f"dest: {path.parent} is not a directory, so {path.name} has nowhere to go")
        if os.path.normcase(str(path.parent.resolve() / path.name)).casefold() == \
                os.path.normcase(str(store.path.resolve())).casefold():
            raise ds.Invalid("bad_argument",
                f"dest: {path} is the declaration store's own file (compared without regard "
                "to case); a comment file goes "
                "beside the symbol file, as <symbol file stem>.comments.tsv")
        if not paths.taken(path):
            return path, None
        if not stat.S_ISREG(path.stat().st_mode):
            raise ds.Invalid("bad_argument",
                f"dest: {path} is not a regular file, so it is not a comment file to replace")
        raw = path.read_bytes()
    except OSError as e:
        raise ds.Invalid("bad_argument", f"dest: {path} cannot be looked at: {e}") from None
    return path, _rows_of(raw, "dest", path)


def _rows_of(raw: bytes, name: str, path: Path) -> list[cf.Row]:
    """A file's bytes as comment rows, or the refusal naming the line that broke."""
    try:
        return cf.parse(raw.decode("utf-8"), str(path))
    except UnicodeDecodeError as e:
        raise ds.Invalid("bad_argument",
            f"{name}: {path} is not UTF-8 text: byte {e.start} {e.reason}, so it is not a "
            "comment file") from None
    except cf.CommentFileError as e:
        raise ds.Invalid("bad_argument", f"{name}: {path} is not a comment file: {e}") from None


def _canonical_file_ref(ref: str) -> str:
    return dec.canonical_ref(ref, placement.decide_by(ref))


def _sharing(placed: list[tuple[dec.Declaration, dict[str, Any]]]) -> list[tuple[str, str]]:
    """Every comment at a place an earlier one already holds, as (the earlier ref, its ref)."""
    seen: dict[tuple[str, Any], str] = {}
    pairs: list[tuple[str, str]] = []
    for d, place in placed:
        other = seen.setdefault(_key(d.ref, place), d.ref)
        if other != d.ref:
            pairs.append((other, d.ref))
    return pairs


def _one_per_place(placed: list[tuple[dec.Declaration, dict[str, Any]]]) -> None:
    """A file names each place once: two comments at one byte are refused before any write."""
    if sharing := _sharing(placed):
        other, ref = sharing[0]
        raise ds.Invalid("bad_argument",
            f"{other!r} and {ref!r} are comments at one place, which a comment file "
            "names once: `comment_write(method=\"delete\")` one of them, or "
            "`comment_write(method=\"add\")` the place again "
            "to keep one text, then save")


def save_comments(session: ds.Session, dest: str) -> dict[str, Any]:
    """The body of the `comment_write(method="save")` tool."""
    store = arming.current_store()
    path, before = _judged_dest(dest, store)
    _one_per_place(_placed_comments(_Places(session), store))
    held = store.comments()
    text = cf.render([cf.Row(_own_ref(d), "", d.created_at or "", d.text) for d in held])
    mine = {_own_ref(d) for d in held}
    dropped = [{"ref": r.ref} for r in before or []
               if _canonical_file_ref(r.ref) not in mine]
    fresh.replace(path, text.encode("utf-8"), "dest:", new_mode=NEW_FILE_MODE)
    shown, truncated = _shown(dropped)
    note = ({"note": f"{prose.counted(len(dropped), 'comment')} the replaced file held and this "
                     "store does not are gone from it: `dropped_comments`"} if dropped else {})
    return st.reply(path=str(path), comments_total=len(held), dropped_comments=shown,
                    dropped_total=len(dropped), truncated=truncated, **note)


def load_comments(session: ds.Session, given: str) -> dict[str, Any]:
    """The body of the `comment_write(method="load")` tool."""
    store = arming.current_store()
    session.require_stopped("comments, whose raw addresses are read in the mode of a stop")
    path = judges.existing_file("path", given, "comment file")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ds.Invalid("bad_argument", f"path: {path} cannot be read: {e}") from None
    rows = _rows_of(raw, "path", path)
    places = _Places(session)
    incoming: list[tuple[dec.Declaration, dict[str, Any]]] = []
    line_of: dict[str, int] = {}
    for r in rows:
        by = placement.decide_by(r.ref)
        canonical = dec.canonical_ref(r.ref, by)
        decl = _new(places, by, canonical, r.text, created_at=r.created_at)
        if (first := line_of.setdefault(decl.ref, r.line)) != r.line:
            raise ds.Invalid("bad_argument",
                f"path: {path}:{r.line} spells line {first}'s {decl.ref} again: one comment "
                "per ref, so nothing was loaded")
        incoming.append((decl, places.of(decl)))
    held = _placed_comments(places, store)
    spelled = {decl.ref for decl, _ in incoming}
    reached_ids: set[int] = set()
    added: list[tuple[dec.Declaration, dict[str, Any]]] = []
    replaces: list[tuple[dec.Declaration, dec.Declaration]] = []
    replaced: list[dict[str, Any]] = []
    unchanged = 0
    for decl, place in incoming:
        # A row reaches the comment its ref spells before an alias can; each is reached once.
        open_ = [h for h in held if id(h[0]) not in reached_ids
                 and (_own_ref(h[0]) == decl.ref or _own_ref(h[0]) not in spelled)]
        reached = _reach(open_, decl.ref, _key(decl.ref, place))
        if reached is None:
            added.append((decl, place))
            continue
        old, old_place = reached
        reached_ids.add(id(old))
        if old.text != decl.text:
            replaces.append((old, _taken(places, old, decl.text, decl.created_at)))
            replaced.append(_row(old, old_place))
            continue
        unchanged += 1
        if old.by == "address" and not _this_sessions(old, places):
            # The file vouches for this text in this build: adopt the row into this session.
            # Judged by the record, not the listed state, which an unplaceable row never reaches.
            replaces.append((old, _taken(places, old, old.text, old.created_at)))
    adds = [d for d, _ in added]
    _apply(store, adds=adds, replaces=replaces)
    shown, truncated = _shown(replaced)
    notes = [f"the file won at {prose.counted(len(replaced), 'place')}: the store's old text is in "
             "`replaced_comments`"] if replaced else []
    if waiting := [d.ref for d, place in incoming if "refuse" in place]:
        notes.append(f"{prose.counted(len(waiting), 'row')} this stop cannot place, kept "
                     f"`unarmable`, each `why` naming the stop it waits for: "
                     f"{waiting[:st.ROWS_SHOWN]}")
    if sharing := _sharing([*held, *added]):
        notes.append(f"{prose.counted(len(sharing), 'comment')} share a place with another, "
                     f"{sharing[0][0]!r} and {sharing[0][1]!r} first: a comment file names a "
                     "place once, so `comment_write(method=\"save\")` refuses them until "
                     "`comment_write(method=\"delete\")` "
                     "leaves one at each")
    note = {"note": "; ".join(notes)} if notes else {}
    return st.reply(path=str(path), parsed=len(rows), added=len(adds),
                    replaced_comments=shown, replaced_total=len(replaced), truncated=truncated,
                    unchanged=unchanged, comments_total=len(store.comments()),
                    **_store_fields(store), **note)

