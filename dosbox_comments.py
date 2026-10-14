"""COMMENTS: a note on a place in the program, kept with the conf's declarations and carried to and
from the comment file a project versions beside its symbol file.

A comment is declared by a symbol or by a raw `SEG:OFF`. By symbol it is placed against whatever
table is loaded when it is read, so it follows the symbol through a rebuild; by address it stays
where it was put and is `stale` while the batch that described it is not held unchanged
(`dosbox_declarations.raw_staleness`).
Nothing is armed: the debugger has no comment of its own, so a comment is placed when it is
listed or matched and never fed to the machine.

THE PLACE IS THE LINEAR ADDRESS, so two spellings that alias one byte are one place: `start`, its
`0824:000B` and `0814:010B` all name the same comment. A symbol's linear is what `symbols_find`
answers for it; a raw `SEG:OFF` is read in the mode the machine is in, as every `SEG:OFF` this
server takes, real mode by arithmetic and protected mode through the selector's base. A place this
instant cannot work out (a name this table lacks, a selector whose base is not readable now) is
identified by its ref, so it still has exactly one comment.

WHICH REFS ALIAS ONE BYTE, AND WHETHER A RAW ONE LANDS AT ALL, DEPENDS ON THE INSTANT: the table
loaded and the mode of the stop. So a save refuses two comments at one place only where it can
place both, and a load refuses a file for neither: a file saved before `symbols_load`, or on a
running guest, holds rows a later stop finds at one place, and they are kept, as a rebuild keeps
them, and named; a row saved in protected mode is past FFFF at the real-mode park every session
starts at (and an interrupt vector's segment is the null selector in protected mode), so it is
kept `unarmable`, named, and placed at a stop whose mode holds it. A call is answered at this
stop, so `comment_add` still refuses such an address.
"""
from __future__ import annotations

import dataclasses
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

import dosbox_arming as arming
import dosbox_code as code
import dosbox_comment_file as cf
import dosbox_declarations as dec
import dosbox_dump as dumping
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_session as ds
import dosbox_state as st
import dosbox_symbols as sym
from dosbox_state import STATE

#: Why a raw comment is `stale`, by `dosbox_declarations.raw_staleness`'s answer.
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
    """Where each comment lands at this instant, asking the machine at most once: the survey
    that names the mode (and, in protected mode, the selectors' bases) is taken only when a raw
    address needs it and only while the machine is stopped, so a listing on a running guest
    types nothing."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        self.stopped = session.at_debugger()
        self._segs: code.Segments | None = None

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
        """A held comment's place: `where` its ref lands, then `stale` for a raw address over
        another build, still with the `linear` it was given. One this stop cannot place (a
        load keeps those) keeps `refuse` and says it waits for a stop that can. One placed in
        the other cpu mode is not placed here at all: it waits for a stop of its own."""
        if (mode := placement.waits(decl, self.mode)) is not None:
            return {"state": "unarmable",
                    "why": placement.waits_why(mode, "Comment it again, or load its file,")}
        place = self.where(decl.by, decl.ref)
        if "refuse" in place:
            place["why"] = f"{place['refuse']}; {place['waits']}"
        if "linear" in place and (stale := placement.staleness(
                decl, lambda: place["linear"])) is not None:
            place.update(state="stale", why=_STALE_WHY[stale])
        return place

    def where(self, by: str, ref: str) -> dict[str, Any]:
        """`state` and, once placed, `linear` (an int) for a ref; `why` where the state is not
        `resolved`. A place that breaks a rule a call must refuse (an offset past what its
        segment holds) comes back with `refuse` set to the words of that refusal, and `waits`
        to the stop a held row of it waits for."""
        if by == "symbol":
            return _symbol_place(ref)
        seg, off = placement.parse_seg_off(ref)
        mode = self.mode()
        if mode is None:
            return {"state": "unarmable", "why": (
                "the machine has not stopped yet, so its mode is not known and a SEG:OFF cannot "
                "be placed")}
        if mode == ds.REAL_MODE:
            if off > ds.offset_ceiling(mode):
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
            # A SELECTOR THAT ADDRESSES NOTHING (null, or no descriptor) is the caller's to fix
            # and refused; only a base this stop cannot read now leaves the place for later.
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
    """The stop a raw row waits for when this protected-mode stop has no descriptor for its
    selector: a real-mode one reads the selector as a paragraph, up to offset FFFF."""
    real = off <= ds.offset_ceiling(ds.REAL_MODE)
    if seg <= code.NULL_SELECTOR_MAX:
        return (f"kept for a real-mode stop, where {seg:04X} is a paragraph" if real else
                "kept, though no stop places it: the null selector addresses nothing and a "
                "real-mode segment ends at FFFF")
    return (f"kept for a stop that places it: a real-mode one, or one whose tables describe "
            f"{seg:04X}" if real else f"kept for a stop whose tables describe {seg:04X}")


def _symbol_place(name: str) -> dict[str, Any]:
    """A symbol's place against the table loaded now: the linear `symbols_find` answers for
    it, or why there is none."""
    if not STATE.table:
        return {"state": "unresolved", "why": "no symbol table is loaded: `symbols_load` one and "
                                              "this comment is placed against it"}
    hits = STATE.name_index.get(name, [])
    if not hits:
        return {"state": "unresolved", "why": f"{name!r} is not a symbol of the table loaded "
                                              "now: kept, it may be back after a rebuild"}
    if len(hits) > 1:
        return {"state": "ambiguous", "why": (
            f"{name!r} names {len(hits)} symbols in this build, so its place would be a guess: "
            "comment it by address")}
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
        row["linear"] = f"{place['linear']:08X}"
    row["state"] = place["state"]
    if "why" in place:
        row["why"] = place["why"]
    return row


def _new(places: _Places, by: str, ref: str, text: str,
         created_at: str | None = None) -> dec.Declaration:
    """A comment of this session, of the batch that describes its place at this stop and of
    this stop's mode, with the conf it was placed over; stamped now unless the stamp is carried
    over (from a file, or kept through a move to this build)."""
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
    """A held comment given `text` at this stop: placed here, as a new one is. A raw row placed
    in the other cpu mode that this stop cannot place keeps that mode, for the stop of its own
    that places it; with a map held, where it would be stamped `pending` and lost to the next
    session, it keeps its whole record and only its text and date change."""
    new = _new(places, old.by, old.ref, text, created_at=created_at)
    if placement.waits(old, places.mode) is None or "linear" in places.where(old.by, old.ref):
        return new
    if new.fingerprint == dec.PENDING_STAMP:
        return dataclasses.replace(old, text=text, created_at=new.created_at)
    return dataclasses.replace(new, cpu_mode=old.cpu_mode)


def _this_sessions(decl: dec.Declaration, places: _Places) -> bool:
    """Whether a raw comment already carries what this stop would give it (`_taken`): this
    session, the batch that describes its place, this stop's mode, so a load giving it the
    text it holds has nothing to take."""
    new = _taken(places, decl, decl.text, decl.created_at)
    return (decl.origin, decl.fingerprint, decl.conf_fingerprint, decl.cpu_mode) == (
        new.origin, new.fingerprint, new.conf_fingerprint, new.cpu_mode)


def park_rows_take_the_map(session: ds.Session) -> str | None:
    """Stamp this session's raw comments that no batch described when they were placed, and
    its raw comments and breakpoints declared where their place was not known
    (`dec.PENDING_STAMP`), with what describes them now, so the next session judges them by it
    like any raw row: a protected-mode program parks in real mode, where its comment file
    loads, and its map can only be loaded at the protected-mode stop that follows, so the
    batch that arrives is what those rows never had, not another build. Another session's row
    is not taken: nothing says which map it was placed under. The store's write error, if it
    could not be written (the change is held in memory), else None."""
    store, conf = STATE.store, STATE.conf_fingerprint
    if store is None or STATE.session_origin is None or conf is None:
        return None
    mine = [d for d in (*store.comments(), *store.declarations())
            if dec.is_raw_code(d.kind, d.by) and d.origin == STATE.session_origin
            and (d.fingerprint == dec.PENDING_STAMP
                 or (d.kind == "comment" and d.fingerprint == conf))]
    places = _Places(session)
    taken = []
    for d in mine:
        try:
            # A row placed in the other mode is not this stop's to place.
            linear = (None if placement.waits(d, places.mode) is not None
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
    """One write of the store; a failed write is the host's refusal, the change kept in memory."""
    try:
        store.apply(**changes)
    except dec.StoreWriteError as e:
        raise ds.Invalid("host_failed", str(e), held_in_memory=True) from None


def _own_ref(decl: dec.Declaration) -> str:
    """A held comment's ref as a call spells it: a store edited by hand may hold an address
    short."""
    return dec.canonical_ref(decl.ref, decl.by)


def _reach(held: list[tuple[dec.Declaration, dict[str, Any]]], canonical: str,
           key: tuple[str, Any]) -> tuple[dec.Declaration, dict[str, Any]] | None:
    """The comment a call reaches: the one whose own ref it spells, else the first held at the
    place it names. Several comments a rebuild brought to one place are all kept, and a call
    that spells one of their refs reaches that one."""
    own = next((h for h in held if _own_ref(h[0]) == canonical), None)
    if own is not None:
        return own
    return next((h for h in held if _key(h[0].ref, h[1]) == key), None)


def _placed_comments(places: _Places,
                     store: dec.DeclarationStore) -> list[tuple[dec.Declaration, dict[str, Any]]]:
    return [(d, places.of(d)) for d in store.comments()]


def _the_ref(ref: str, places: _Places) -> tuple[str, str, dict[str, Any]]:
    """A caller's ref as stored (`by`, canonical spelling) and its place now; an ambiguous name
    or a place that breaks a rule is refused here, before anything is stored."""
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

def comment_add(session: ds.Session, ref: str, text: str) -> dict[str, Any]:
    """The body of the `comment_add` tool."""
    store = arming.current_store()
    ds.console_listening(session, "a comment, whose raw address is read in the mode of a stop")
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
    return st.reply(comment=_row(new, place), replaced_comments=replaced, persistent=True,
                    path=str(store.path), **_note(place))


def comment_list(session: ds.Session) -> dict[str, Any]:
    """The body of the `comment_list` tool."""
    store = arming.current_store()
    places = _Places(session)
    rows = [_row(d, p) for d, p in _placed_comments(places, store)]
    shown, truncated = _shown(rows)
    running: dict[str, Any] = ({} if places.stopped else
                               {"running": True, "last_stop": STATE.as_of()})
    return st.reply(comments=shown, comments_total=len(rows), truncated=truncated,
                    persistent=True, path=str(store.path), **running)


def comment_delete(session: ds.Session, ref: str) -> dict[str, Any]:
    """The body of the `comment_delete` tool."""
    store = arming.current_store()
    ds.console_listening(session, "a comment's place, read in the mode of a stop")
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
    return st.reply(deleted=_row(old, old_place), persistent=True, path=str(store.path),
                    **_note(old_place))


# ------------------------------------------------------------------------------- the file

def _judged_dest(dest: str, store: dec.DeclarationStore) -> tuple[Path, list[cf.Row] | None]:
    """`dest` as a file this call may write, and the rows of the comment file already there
    (None when there is none). Refused, and left as it is: a link, anything but a regular
    file, a file that is not a whole comment file, and the store's own file."""
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
                f"dest: {path} is the declaration store's own file; a comment file goes "
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


def _write(path: Path, text: str) -> None:
    """The file written whole or not at all: a temporary beside it, then moved over it. A new
    file is 0644; one replaced keeps its mode."""
    tmp: str | None = None
    try:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError as e:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)
        raise ds.Invalid("host_failed", f"dest: {path} could not be written: {e}") from None


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
    """A file names each place once, so two comments this instant places at one byte (a
    rebuild brings a raw address and a symbol together) are refused by name before anything
    is written."""
    if sharing := _sharing(placed):
        other, ref = sharing[0]
        raise ds.Invalid("bad_argument",
            f"{other!r} and {ref!r} are comments at one place, which a comment file "
            "names once: `comment_delete` one of them, or `comment_add` the place again "
            "to keep one text, then save")


def comment_save(session: ds.Session, dest: str) -> dict[str, Any]:
    """The body of the `comment_save` tool."""
    store = arming.current_store()
    path, before = _judged_dest(dest, store)
    _one_per_place(_placed_comments(_Places(session), store))
    held = store.comments()
    text = cf.render([cf.Row(d.ref, "", d.created_at or "", d.text) for d in held])
    mine = {_own_ref(d) for d in held}
    dropped = [{"ref": r.ref, "cpu": None} for r in before or []
               if _canonical_file_ref(r.ref) not in mine]
    _write(path, text)
    shown, truncated = _shown(dropped)
    note = ({"note": f"{len(dropped)} comment(s) the replaced file held and this store does not "
                     "are gone from it: `dropped_comments`"} if dropped else {})
    return st.reply(dest=str(path), comments_total=len(held), dropped_comments=shown,
                    dropped_total=len(dropped), truncated=truncated, **note)


def comment_load(session: ds.Session, source: str) -> dict[str, Any]:
    """The body of the `comment_load` tool."""
    store = arming.current_store()
    ds.console_listening(session, "comments, whose raw addresses are read in the mode of a stop")
    path = paths.input_file("source", source, "comment file")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ds.Invalid("bad_argument", f"source: {path} cannot be read: {e}") from None
    rows = _rows_of(raw, "source", path)
    places = _Places(session)
    incoming: list[tuple[dec.Declaration, dict[str, Any]]] = []
    line_of: dict[str, int] = {}
    for r in rows:
        by = placement.decide_by(r.ref)
        canonical = dec.canonical_ref(r.ref, by)
        decl = _new(places, by, canonical, r.text, created_at=r.created_at)
        if (first := line_of.setdefault(decl.ref, r.line)) != r.line:
            raise ds.Invalid("bad_argument",
                f"source: {path}:{r.line} spells line {first}'s {decl.ref} again: one comment "
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
        # A ROW REACHES THE COMMENT ITS REF SPELLS before an alias of it can, and each held
        # comment is reached once: two rows at one place are two comments, never two
        # replacements of one.
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
            # TAKEN INTO THIS SESSION, ref and stamp kept: the file says this place holds this
            # text in the build it is loaded into, so a row of another build is brought to this
            # one, and a row an earlier session left at the park becomes this session's, which
            # the map that follows then takes. Judged by the record and not by the listed
            # state, which a row this stop cannot place never reaches.
            replaces.append((old, _taken(places, old, old.text, old.created_at)))
    adds = [d for d, _ in added]
    _apply(store, adds=adds, replaces=replaces)
    shown, truncated = _shown(replaced)
    notes = [f"the file won at {len(replaced)} place(s): the store's old text is in "
             "`replaced_comments`"] if replaced else []
    if waiting := [d.ref for d, place in incoming if "refuse" in place]:
        notes.append(f"{len(waiting)} row(s) this stop cannot place are kept `unarmable`, "
                     f"each `why` naming the stop it waits for: {waiting[:st.ROWS_SHOWN]}")
    if sharing := _sharing([*held, *added]):
        notes.append(f"{len(sharing)} comment(s) share a place with another, "
                     f"{sharing[0][0]!r} and {sharing[0][1]!r} first: a comment file names a "
                     "place once, so `comment_save` refuses them until `comment_delete` "
                     "leaves one at each")
    note = {"note": "; ".join(notes)} if notes else {}
    return st.reply(source=str(path), parsed=len(rows), added_total=len(adds),
                    replaced_comments=shown, replaced_total=len(replaced), truncated=truncated,
                    unchanged_total=unchanged, comments_total=len(store.comments()),
                    persistent=True, path=str(store.path), **note)

