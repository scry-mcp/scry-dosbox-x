"""A persistent store of debugging DECLARATIONS, keyed by the conf that identifies a guest.

The debugger holds the ARMED instances; this holds the INTENT -- a breakpoint or a watch,
declared BY a symbol name or BY a raw address. Storing the intent is what makes a rebuild
free: an address moves when you recompile, a symbol does not. So a declaration by name
re-resolves against the new symbol table and re-arms itself, and one whose symbol has
VANISHED is KEPT, unresolved and said out loud, rather than silently dropped -- it may be
something removed on purpose and about to come back, and `-O3` inlining makes a symbol
disappearing from one build an ordinary event rather than a rare one.

It is keyed by the conf's IDENTITY so two different guests do not inherit each other's
declarations, and it PERSISTS to disk so they survive closing the emulator, recompiling
the program, and restarting the session that drives it.

WHAT IT DOES NOT DO: it does not talk to the debugger and it does not hold a base. A
declaration by name resolves to an OFFSET against a symbol table; the LINEAR address is
that offset plus a base the running process supplies, applied when the caller arms it.
Keeping the base out is the same discipline `dosbox_symbols.Symbol` keeps: a file produced
on one run must not be usable against another by accident.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scry_core import fresh
from scry_core import value_format as vf
from scry_core.reply_contract import Invalid

import dosbox_comment_file as cf
import dosbox_console as dcons
import dosbox_symbols as sym

# THREE kinds: a code breakpoint and a watch, declared by symbol or by address, and an
# INTERRUPT breakpoint, which has no symbol to resolve and is declared by the debugger's
# own BPLIST spelling (`BPINT 21`, `BPINT 21 AH=4C`). It joined the store because it was
# the one armed thing nothing could list or clear: the console's `BPDEL` takes an index
# that is NOT the arming order, and clearing by index once deleted a code breakpoint.
COUNTED_KINDS = ("breakpoint", "watch", "interrupt")
# AND A COMMENT, which stops nothing and watches nothing: a note on a place, declared by a symbol
# (so it follows the symbol through a rebuild) or by a raw address. It lives here because what a
# comment needs is exactly what a declaration already has (a conf to belong to, a stamp, an
# origin, a build to be stale against), and it is kept out of `declarations()`, the list every
# reader that arms, counts or stops walks, so no comment is ever armed, counted or waited for.
KINDS = (*COUNTED_KINDS, "comment")
# And BY A POINTER: a watch whose place is reached THROUGH a pointer held at a global, the
# grammar being `[base]`, `[base]+0x28`, `[base]-0x4` or `base->field`, with `base` a symbol
# or a `SEG:OFF`. The address is resolved when the watch is armed and AGAIN at every stop,
# because the pointer can move; a breakpoint is never declared this way (code does not move
# behind a pointer, and a stop at a moving address is one nobody can attribute).
BY = ("symbol", "address", "pointer")
# An interrupt declaration's ref IS the debugger's BPLIST row spelling, so it is validated
# at the shape `dosbox_console.interrupt_row` produces and `parse_interrupt_row` reads. Its
# own regex, not imported from session: this module validates its own stored data and does
# not depend on the session layer.
INTERRUPT_ROW = re.compile(r"^BPINT [0-9A-Fa-f]{2}(?: AH=[0-9A-Fa-f]{2})?$")
# THE STAMP OF A RAW ROW DECLARED WHERE ITS PLACE IS NOT KNOWN, while a map is held (a
# protected-mode address at a real-mode stop): which batch describes it cannot be told, and
# the conf alone would let it be judged as a row no map described. It names no batch and no
# conf, so until a load of its session places it the row is `stale`; it is not hex, so no
# fingerprint can equal it.
PENDING_STAMP = "pending"
# THE CPU MODE A RAW ROW WAS PLACED IN: one SEG:OFF names one byte in real mode (a paragraph)
# and another in protected mode (a selector's base), so a row placed in one is judged and armed
# only at a stop of that mode. None on a row no stop has placed yet.
CPU_MODES = ("real", "protected")
# A watch has TWO halves: SHOW evaluates the bytes at every stop and arms NOTHING, and
# BREAK-ON-CHANGE arms a memory-change breakpoint and evaluates the bytes too. One ref is one
# watch -- see `add`.
# `show` was spelled `read` until "read" was left to name an access only: a stored row still
# carrying the old word is read as the new one (`Declaration.from_dict`).
WATCH_MODES = ("show", "change")
RETIRED_MODES = {"read": "show"}


def check_watch_mode(mode: str | None) -> None:
    """The mode is a word of the vocabulary, judged before anything about the size: a
    caller who typed a mode that does not exist is told that, not that the width is missing."""
    if mode not in WATCH_MODES:
        raise DeclarationError(f"mode is one of {WATCH_MODES}; got {mode!r}")
# A watch is N BYTES AT A NAME with a declared width and format: a symbol
# table gives addresses, not types, so there are no struct fields here.
# A watch is BYTES AT A NAME read as a FORMAT: a scalar (N of them, `width` bytes), an
# array (`u16[8]`), a string (`char[16]`) or a struct (`{x:i16,y:i16}`), the grammar of
# `value_format`.
FORMATS = tuple(vf.SCALARS)
FORMAT_WIDTH = {name: size for name, (_code, size) in vf.SCALARS.items()}


class DeclarationError(Exception):
    """A declaration that cannot be stored: malformed, or in conflict with one already
    held. It is a distinct type so the MCP layer can translate it into a refusal that
    names what was wrong, rather than letting it escape as a traceback."""


def same_place(a: Declaration, b: Declaration) -> bool:
    """Two declarations are ONE when they differ only in how their address is spelt."""
    from dataclasses import replace
    return replace(a, ref=canonical_ref(a.ref, a.by)) == replace(b, ref=canonical_ref(b.ref, b.by))


def canonical_ref(ref: str, by: str) -> str:
    """The one spelling a ref is stored and matched under: a `SEG:OFF` upper-case, its offset
    at the width of its bits (eight digits for one past FFFF, four for a 16-bit one, the
    debugger's own listing), so one place has one spelling however it was typed; anything else
    as typed, stripped. A `SEG:OFF` that does not parse is left as typed, for the tool's own
    refusal to name."""
    text = ref.strip()
    if by == "pointer":
        # THE BASE INSIDE A POINTER REF FOLDS LIKE A BARE ADDRESS, and
        # the ref is rebuilt in one shape.
        pr = vf.parse_pointer(text)
        if pr is not None:
            base = canonical_ref(pr.base, "address")
            if pr.field is not None:
                return f"{base}->{pr.field}"
            sign = "-" if pr.offset < 0 else "+"
            return f"[{base}]" + (f"{sign}0x{abs(pr.offset):x}" if pr.offset else "")
    if by != "address" or ":" not in text:
        return text
    seg_s, off_s = text.split(":", 1)
    try:
        seg, off = int(seg_s, 16), int(off_s, 16)
    except ValueError:
        return text
    return dcons.canonical_seg_off(seg, off)


@dataclass(frozen=True)
class Declaration:
    """One thing a caller wants armed, BY a symbol name or BY a raw address.

    `ref` is the symbol name when `by == "symbol"` and a canonical address string when
    `by == "address"` -- the store never parses the address, it only carries it, because
    what a raw address means (real segment, selector, linear) is the debugger's to know
    and the store is deliberately ignorant of the machine.

    The watch fields are meaningful only for `kind == "watch"` and are `None` on a
    breakpoint; `__post_init__` refuses any other combination, so an ill-formed
    declaration cannot be constructed rather than being caught three layers later.
    """

    kind: str
    by: str
    ref: str
    width: int | None = field(default=None, kw_only=True)
    fmt: str | None = field(default=None, kw_only=True)
    watch_mode: str | None = field(default=None, kw_only=True)
    # WHEN AND BY WHICH SESSION, kept OUT of equality: re-declaring the same thing from a
    # new session is the same declaration, adopted (see `DeclarationStore.add`), not a
    # second one. A raw-address breakpoint armed on the wrong selector in one session
    # re-arms itself in the next, and without a stamp nothing in the store can say which
    # session left it. `origin` is the session's own stamp; `created_at` is
    # when this declaration was made or last adopted.
    created_at: str | None = field(default=None, kw_only=True, compare=False)
    origin: str | None = field(default=None, kw_only=True, compare=False)
    # THE BUILD IT WAS DECLARED AGAINST: the stamp of the one batch that described its
    # address (`Build.stamp`; the batch itself is held in memory by the session that loaded
    # it), or the conf's fingerprint alone
    # where no batch did. A raw address is judged by it (`raw_staleness`); a name re-resolves
    # whatever the fingerprint. Out of equality like the stamps: the same thing declared
    # against a new build is adopted, not doubled.
    fingerprint: str | None = field(default=None, kw_only=True, compare=False)
    # AND THE CONF ALONE, on a comment: a batch's stamp hashes the conf and the batch together,
    # so without it a stale row's why could not tell a row made over another build from one
    # stored before the conf was kept (`raw_staleness`).
    conf_fingerprint: str | None = field(default=None, kw_only=True, compare=False)
    # AND THE MODE OF THE STOP THAT PLACED IT, on a raw row (`keeps_mode`, `CPU_MODES`), taken
    # with the stamp: the stamp says which build the address was read against, this says how it
    # was read.
    cpu_mode: str | None = field(default=None, kw_only=True, compare=False)
    # A COMMENT'S TEXT, out of equality like the stamps: the comment at a place is ONE
    # declaration whatever it says, and a new text replaces the old one rather than doubling it.
    text: str = field(default="", kw_only=True, compare=False)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise DeclarationError(f"kind is one of {KINDS}; got {self.kind!r}")
        if self.by not in BY:
            raise DeclarationError(f"`by` is one of {BY}; got {self.by!r}")
        if not self.ref:
            raise DeclarationError("a declaration needs a ref: a symbol name or an address")
        if self.by == "pointer":
            if self.kind != "watch":
                raise DeclarationError(
                    f"a {self.kind} is not declared through a pointer: a breakpoint is at "
                    "code, and a stop at an address that moves is one nobody can attribute")
            if vf.parse_pointer(self.ref) is None:
                raise DeclarationError(
                    f"{self.ref!r} is not a pointer ref: `[base]`, `[base]+0x28`, "
                    "`[base]-0x4` or `base->field`, with `base` a symbol or a SEG:OFF")
        if self.cpu_mode is not None and (self.cpu_mode not in CPU_MODES
                                          or not keeps_mode(self.kind, self.by)):
            raise DeclarationError(f"a cpu mode is one of {CPU_MODES}, on a raw breakpoint, "
                                   f"comment or watch; got {self.cpu_mode!r} on a {self.kind} by "
                                   f"{self.by}")
        if self.kind == "comment":
            self._check_comment()
        elif self.text:
            raise DeclarationError(f"a {self.kind} carries no text; only a comment does")
        if self.kind == "watch":
            check_watch_mode(self.watch_mode)
            if self.fmt is None:
                raise DeclarationError(
                    f"a watch needs a format, one of {FORMATS}, an array like u16[8], a "
                    "string like char[16] or a struct; got None")
            try:
                width = vf.parse(self.fmt).width_for(self.width or 0)
            except vf.FormatError as e:
                raise DeclarationError(str(e)) from None
            # A SIZED FORMAT NAMES ITS OWN WIDTH: the declaration carries it so every
            # reader of `width` (the armed length, the read) sees one number.
            object.__setattr__(self, "width", width)
        elif self.kind != "comment":  # breakpoint, interrupt
            extras = {"width": self.width, "fmt": self.fmt, "watch_mode": self.watch_mode}
            set_extras = {k: v for k, v in extras.items() if v is not None}
            if set_extras:
                raise DeclarationError(
                    f"a {self.kind} carries no watch fields; got {set_extras}")
            if self.kind == "interrupt":
                if self.by != "address":
                    raise DeclarationError(
                        "an interrupt breakpoint is declared by its number, never by a "
                        f"symbol: `by` must be 'address', got {self.by!r}")
                # THE REF IS THE DEBUGGER'S ROW SPELLING (`BPINT 21`), not `INT 21`: it is
                # matched against the live BPLIST by equality and parsed back to clear it,
                # so a wrong spelling would list as `gone` forever and wedge the clear.
                # Refused HERE so it cannot enter the store (a hand-edited file is refused
                # on load too, since from_dict runs through this).
                if not INTERRUPT_ROW.match(self.ref):
                    raise DeclarationError(
                        f"an interrupt ref is the debugger's row spelling, `BPINT NN` or "
                        f"`BPINT NN AH=NN` in hex; got {self.ref!r}")

    def _check_comment(self) -> None:
        """A comment holds to the comment file's rules, so a store edited by hand cannot hold
        one `comment_save` could not write: by symbol or by address, the shape agreeing with
        `by` (a colon makes an address), the file's ref, stamp and text rules, no watch field."""
        if self.by not in ("symbol", "address"):
            raise DeclarationError(f"a comment is declared by symbol or by address; got "
                                   f"{self.by!r}")
        if (":" in self.ref) != (self.by == "address"):
            raise DeclarationError(f"a comment by {self.by} cannot have the ref {self.ref!r}: "
                                   "an address carries a colon and a symbol does not")
        extras = {"width": self.width, "fmt": self.fmt, "watch_mode": self.watch_mode}
        set_extras = {k: v for k, v in extras.items() if v is not None}
        if set_extras:
            raise DeclarationError(f"a comment carries no watch fields; got {set_extras}")
        faults = (("ref", cf.ref_fault(self.ref)),
                  ("created_at", cf.stamp_fault(self.created_at or "")),
                  ("text", cf.text_fault(self.text)))
        for column, fault in faults:
            if fault is not None:
                raise DeclarationError(f"a stored comment's {column} {fault}")

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"kind": self.kind, "by": self.by, "ref": self.ref}
        if self.kind == "comment":
            d["text"] = self.text
        if self.kind == "watch":
            d.update(width=self.width, fmt=self.fmt, watch_mode=self.watch_mode)
        if self.created_at is not None:
            d["created_at"] = self.created_at
        if self.origin is not None:
            d["origin"] = self.origin
        if self.fingerprint is not None:
            d["fingerprint"] = self.fingerprint
        if self.conf_fingerprint is not None:
            d["conf_fingerprint"] = self.conf_fingerprint
        if self.cpu_mode is not None:
            d["cpu_mode"] = self.cpu_mode
        return d

    def adopted_by(self, origin: str | None, created_at: str | None,
                   fingerprint: str | None = None, cpu_mode: str | None = None) -> Declaration:
        """The same declaration with a new origin, stamp and build: what re-declaring it
        from another session does to the stored one; a build not carried (None) keeps what
        was held, with the mode it was read in."""
        held = fingerprint is None
        return Declaration(self.kind, self.by, self.ref, width=self.width, fmt=self.fmt,
                           watch_mode=self.watch_mode, created_at=created_at, origin=origin,
                           fingerprint=self.fingerprint if held else fingerprint,
                           cpu_mode=self.cpu_mode if held else cpu_mode)

    @staticmethod
    def from_dict(d: dict[str, object]) -> Declaration:
        """Rebuild a declaration from a stored object, refusing corruption as a
        `DeclarationError`. A hand-edited or truncated file is the case this exists for:
        every malformed shape (a non-numeric width, a missing field) has to come back as a
        NAMED refusal, because `__init__` reads this on start and the MCP layer translates
        only `DeclarationError` -- anything else escapes as a traceback with no context."""
        # A MISSING key is refused by name: `str(None)` is the four-letter word "None", a
        # truthy ref that sails past the refusal below.
        for key in ("kind", "by", "ref"):
            if d.get(key) is None:
                raise DeclarationError(f"a stored declaration lacks `{key}`: {d!r}")
        kind = str(d["kind"])
        by = str(d["by"])
        ref = str(d["ref"])
        ca, og, fp = d.get("created_at"), d.get("origin"), d.get("fingerprint")
        created_at = str(ca) if ca is not None else None
        origin = str(og) if og is not None else None
        fingerprint = str(fp) if fp is not None else None
        cm = d.get("cpu_mode")
        cpu_mode = str(cm) if cm is not None else None
        if kind == "comment":
            tx = d.get("text")
            if not isinstance(tx, str):
                raise DeclarationError(f"a stored comment's text is not text: {d!r}")
            cfp = d.get("conf_fingerprint")
            return Declaration(kind=kind, by=by, ref=ref, created_at=created_at,
                               origin=origin, fingerprint=fingerprint, text=tx,
                               conf_fingerprint=str(cfp) if cfp is not None else None,
                               cpu_mode=cpu_mode)
        if kind != "watch":
            return Declaration(kind=kind, by=by, ref=ref, created_at=created_at,
                               origin=origin, fingerprint=fingerprint, cpu_mode=cpu_mode)
        w = d.get("width")
        width: int | None
        if w is None:
            width = None
        else:
            try:
                width = int(w)          # type: ignore[call-overload]
            except (ValueError, TypeError):
                raise DeclarationError(
                    f"a stored watch has a non-integer width {w!r}") from None
        fmt = d.get("fmt")
        wm = d.get("watch_mode")
        # A ROW STORED UNDER A RETIRED MODE is read under its new word, and the next write
        # persists that word.
        mode = RETIRED_MODES.get(str(wm), str(wm)) if wm is not None else None
        return Declaration(kind=kind, by=by, ref=ref, width=width,
                           fmt=str(fmt) if fmt is not None else None,
                           watch_mode=mode,
                           created_at=created_at, origin=origin, fingerprint=fingerprint,
                           cpu_mode=cpu_mode)


Entry = tuple[str, int]


@dataclass(frozen=True)
class Build:
    """One batch a `symbols_load` loaded, over a conf: the conf's fingerprint and every entry
    the batch placed, sorted, a line the batch repeats kept twice. Its span, lowest entry to
    highest, is the stretch of the program it describes, and a raw row is judged by the one
    batch that describes its address, never by everything loaded beside it. Held in memory
    only: a row carries its stamp, and the batches a session loads are what the stamp is
    judged against."""

    conf: str
    entries: tuple[Entry, ...]
    # THE STAMP AND THE SPAN ARE THE BATCH'S, taken once when it is made: every listing asks
    # them per row per held batch, and a real map holds thousands of entries.
    stamp: str = field(init=False, repr=False, compare=False)
    _span: tuple[int, int] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # The batch's identity: the same conf and the same entries are the same stamp, whatever
        # file or order carried them; a relinked batch moves an entry and the stamp.
        digest = hashlib.sha256(self.conf.encode())
        for entry in self.entries:
            digest.update(b"\0" + _entry_text(entry).encode("utf-8", "surrogatepass"))
        object.__setattr__(self, "stamp", digest.hexdigest()[:16])
        addrs = [a for _, a in self.entries]
        object.__setattr__(self, "_span", (min(addrs), max(addrs)) if addrs else None)

    @staticmethod
    def of(conf: str, entries: Sequence[Entry]) -> Build:
        return Build(conf=conf, entries=tuple(sorted(entries)))

    def covers(self, linear: int) -> bool:
        """Whether `linear` lies in the batch's span: a symbol of it at or below, one at or
        above."""
        return self._span is not None and self._span[0] <= linear <= self._span[1]


def _entry_text(entry: Entry) -> str:
    return f"{entry[0]}\t{entry[1]:X}"


def is_raw_code(kind: str, by: str) -> bool:
    """Whether a row is a raw code breakpoint or comment, the rows the batch rule judges."""
    return kind in ("breakpoint", "comment") and by == "address"


def keeps_mode(kind: str, by: str) -> bool:
    """Whether a row keeps the mode of the stop that placed it: every row at a raw `SEG:OFF`,
    whose segment is a selector in protected mode and a paragraph in real mode."""
    return by == "address" and kind in ("breakpoint", "comment", "watch")


#: What a raw row with no cpu mode waits for: a stop that places it. No stop has (it was declared
#: while the guest ran, declared or loaded where its stop could not place it, or stored before
#: modes were kept).
UNPLACED = "unplaced"


def waits(decl: Declaration, stop_mode: Callable[[], str | None]) -> str | None:
    """Why a raw row is neither judged nor armed at this stop, or None when it is judged
    here. A raw `SEG:OFF` names one byte in real mode and another in protected mode, so a row is
    placed, stamped and armed only at a stop, carries that stop's mode, and is judged and armed
    only at a stop of that mode: the mode it waits for when this stop's (`stop_mode`, one of
    `CPU_MODES` or None, asked only of a row that recorded one) is another, or `UNPLACED` for a
    row no stop placed, which waits in either mode until one does. Every reader that judges or
    arms a raw row asks this first."""
    if not keeps_mode(decl.kind, decl.by):
        return None
    if decl.cpu_mode is None:
        return UNPLACED
    return None if stop_mode() == decl.cpu_mode else decl.cpu_mode


def raw_staleness(decl: Declaration, conf: str | None, batches: Sequence[Build],
                  place_now: Callable[[], int | None]) -> str | None:
    """Why a raw code breakpoint or comment is not known to be this build's, or None when it
    is. It is judged by the one batch that describes its address, never by the history of
    loads: fresh while the batch its stamp names is held unchanged (`batches`, every batch
    loaded since the last replace), whichever batch came after it. Otherwise a held batch
    that describes its address (`place_now`, asked only then, since in protected mode it costs
    a read) is the program saying something else there: `other`, or
    `unrecorded` for a row stamped with the conf alone, placed where no map had been, whose
    map was never recorded. A place this instant cannot work out (None) is taken as described,
    the side that arms nothing. A row no batch describes is judged by the conf alone only when
    the conf alone is its stamp, made with no map describing it; a row made under a map whose
    batch is not held is `stale` whatever describes its address now, because the map it was
    made under no longer vouches for the code there (the map at a base past it, relinked
    shorter or longer), and nothing else here does: `other`, or `no_conf` for a row that
    recorded no conf beside its stamp (a breakpoint, a comment stored before the conf was
    kept). A row declared where its place was not known while a map was held, and that no load
    of its session placed (`PENDING_STAMP`), is `pending`: nothing says which batch it was
    under, so it is `stale` everywhere, at the next park too.

    A raw address does not re-resolve against anything, so re-arming it blind on a relinked
    program lands it on whatever the linker put there: it is kept and listed `stale`, and
    re-declaring it here adopts it. A by-SYMBOL declaration is never stale: it is re-placed
    against the new table, which is the whole point of keeping it. An interrupt and a watch
    are never stale either: nothing re-arms them across sessions. A session with no conf
    recorded judges nothing: there is no build to compare against."""
    if not is_raw_code(decl.kind, decl.by) or conf is None:
        return None
    stamp = decl.fingerprint
    if stamp is not None and any(b.stamp == stamp for b in batches):
        return None
    if stamp == PENDING_STAMP:
        return "pending"
    linear = place_now() if batches else None
    described = bool(batches) and (linear is None or any(b.covers(linear) for b in batches))
    if stamp == conf:
        return "unrecorded" if described else None
    return "other" if described or decl.conf_fingerprint is not None else "no_conf"


@dataclass(frozen=True)
class Resolved:
    """A declaration paired with where it currently points.

    `state` is `address` for a by-address declaration (nothing to resolve, the caller's
    address stands), `resolved` when a by-symbol declaration's name is in the current
    table, and `unresolved` when it is not -- a vanished symbol is kept, never dropped.
    `offset` and `section` are the resolution and are `None` in the other two states.

    `matches` is HOW MANY symbols the name resolved to: 1 for the ordinary case, MORE when
    the build defines the name more than once, and 0 when there was nothing to match (a
    by-address or an unresolved declaration). It is here so the tool that ARMS can refuse
    an ambiguous name -- which it could not do if a two-symbol resolution came back looking
    exactly like a one-symbol one.
    """

    decl: Declaration
    state: str
    offset: int | None = None
    section: int | None = None
    matches: int = 0
    idle: bool = False    # the linker's mark on the chosen symbol, passed through


def default_path() -> Path:
    """Where the declarations live when the caller names no file: an XDG state directory,
    so they survive a session and are not mistaken for a cache to be cleared."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "dosbox-x-debug" / "declarations.json"


def _one_comment_per_ref(decls: Sequence[Declaration]) -> None:
    """A comment file holds one row per ref, so the store holds one comment per ref too: a store
    holding a ref twice could not be saved."""
    seen: set[str] = set()
    for d in decls:
        if d.kind != "comment":
            continue
        ref = canonical_ref(d.ref, d.by)
        if ref in seen:
            raise DeclarationError(f"a stored comment at {ref!r} twice: a comment file holds "
                                   "one row per ref, and so does the store")
        seen.add(ref)


#: The key under which an older store wrote the batches its rows named, beside the conf
#: identities: ignored on read, and this conf's entry dropped on the next write.
BUILDS_KEY = "builds"


class StoreWriteError(Exception):
    """The store's file could not be written, and the change it carried was rolled back: memory
    never holds what the file does not, as every write of the store promises (`_commit`)."""


class DeclarationStore:
    """The declarations for ONE guest, backed by a file shared by every guest.

    The file is a mapping from conf identity to a list of declarations, so opening a store
    for one conf reads the whole file but exposes only that conf's list; a write persists
    the whole file. Two stores over the same file and different identities cannot see each
    other's declarations, on purpose: a symbol from another binary would arm at
    a plausible and wrong address. `BUILDS_KEY` is no conf identity (those are resolved
    paths), so an older file's batches are never read as a conf's rows.
    """

    def __init__(self, conf_identity: str, path: Path | None = None) -> None:
        if not conf_identity:
            raise DeclarationError("a store needs a non-empty conf identity to key by")
        self._conf = conf_identity
        self._path = path or default_path()
        raw = self._read_raw()
        self._items = self._decls_for(raw, conf_identity)

    @staticmethod
    def _decls_for(raw: dict[str, object], conf: str) -> list[Declaration]:
        """This conf's declarations out of the whole file, refusing a shape that is not a
        list of objects. Without this a `{conf: "oops"}` file iterated a string into
        `from_dict`, and a `{conf: [1]}` fed it an int -- both escaping as an
        `AttributeError` rather than the named refusal this file promises."""
        items = raw.get(conf, [])
        if not isinstance(items, list):
            raise DeclarationError(
                f"conf {conf!r} maps to a {type(items).__name__}, not a list of "
                f"declarations")
        out: list[Declaration] = []
        for d in items:
            if not isinstance(d, dict):
                raise DeclarationError(
                    f"a declaration under {conf!r} is a {type(d).__name__}, not an "
                    f"object: {d!r}")
            out.append(Declaration.from_dict(d))
        _one_comment_per_ref(out)
        return out

    def _read_raw(self) -> dict[str, object]:
        """The whole file as it is on disk right now, or empty when there is none."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise DeclarationError(
                f"the declaration file {self._path} could not be read: {exc}. It is not "
                f"discarded -- fix or remove it rather than lose what it holds") from None
        if not isinstance(raw, dict):
            raise DeclarationError(
                f"the declaration file {self._path} is not a mapping of conf to "
                f"declarations; it holds a {type(raw).__name__}")
        return raw

    def _commit(self, mine: list[Declaration], new: list[Declaration]) -> None:
        """This conf's rows become `new` and are written; a write that fails puts them back,
        so memory never holds what the file does not (the next `start` reads the file)."""
        old = list(mine)
        mine[:] = new
        try:
            self._persist()
        except OSError as e:
            # THE HOST REFUSED THE WRITE: the store's own error, so the tools answer a refusal
            # where a bare OSError would reach the caller as a traceback.
            mine[:] = old
            raise DeclarationError(f"the declaration file {self._path} could not be written "
                                   f"({e}); nothing was changed") from None
        except BaseException:
            mine[:] = old
            raise

    def _persist(self) -> None:
        # RE-READ THE FILE AND REPLACE ONLY THIS CONF'S ENTRY, so a second store opened for
        # a DIFFERENT guest does not clobber it: each store holds only its own conf in
        # memory, and writing the whole in-memory picture would erase every conf this store
        # never loaded. Found by the isolation test, which is exactly this shape.
        #
        # THIS ASSUMES A SINGLE WRITER, which is what this server is: the MCP server holds
        # ONE session and serialises its tools under one lock, so the read-modify-write
        # below is never interleaved with its own. It is NOT locked against a SECOND
        # process writing the same file at the same instant -- two servers over one file
        # could each read before the other's `os.replace` and lose an add. That is a race
        # this design does not run and does not guard; a lock file would be the fix if it
        # ever did. `os.replace` still makes each individual write atomic, so no reader ever
        # sees a half-written file.
        raw = self._read_raw()
        raw[self._conf] = [d.to_dict() for d in self._items]
        every = raw.get(BUILDS_KEY)
        if isinstance(every, Mapping):
            rest = {k: v for k, v in every.items() if k != self._conf}
            if rest:
                raw[BUILDS_KEY] = rest
            else:
                raw.pop(BUILDS_KEY)
        # WHOLE OR NOT AT ALL (`fresh.replace`): the declarations are meant to survive exactly
        # the interruptions a plain truncate-then-write is most exposed to.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fresh.replace(self._path, json.dumps(raw, indent=2, sort_keys=True).encode(),
                      "the declarations file", named_by_caller=False)

    def _mine(self) -> list[Declaration]:
        return self._items

    @property
    def path(self) -> Path:
        """The file this store persists to."""
        return self._path

    def declarations(self) -> list[Declaration]:
        """This conf's declarations that stop or watch, in the order they were added: every
        reader that arms, counts or waits for a stop walks this list, and a comment is in none
        of those businesses (`comments()` holds them)."""
        return [d for d in self._mine() if d.kind in COUNTED_KINDS]

    def comments(self) -> list[Declaration]:
        """This conf's comments, in the order they were added."""
        return [d for d in self._mine() if d.kind == "comment"]

    def apply(self, *, adds: Sequence[Declaration] = (),
              replaces: Sequence[tuple[Declaration, Declaration]] = (),
              removes: Sequence[Declaration] = ()) -> None:
        """Several comment changes made together and persisted ONCE, so a load lands whole or
        not at all; a row of another kind may be replaced only by itself with new stamps. A
        replaced or removed row is found by identity among those held; one that is not held is
        a programmer's error, and so is a second comment under a held ref.
        No change writes nothing. If the file cannot be written every change is rolled back and
        `StoreWriteError` says so."""
        if any(d.kind != "comment" for d in (*adds, *removes)) or any(
                new.kind != "comment" and new != old for old, new in replaces):
            raise DeclarationError("apply changes comments only, and restamps another kind in "
                                   "place; the other changes go through add and remove, which "
                                   "judge their conflicts")
        if not (adds or replaces or removes):
            return
        mine = self._mine()
        updated = list(mine)
        for old, new in replaces:
            at = next((i for i, d in enumerate(updated) if d is old), None)
            if at is None:
                raise DeclarationError(f"apply was asked to replace a {new.kind} this store "
                                       "does not hold")
            updated[at] = new
        gone = {id(d) for d in removes}
        updated = [d for d in updated if id(d) not in gone]
        if len(updated) != len(mine) - len(gone):
            raise DeclarationError("apply was asked to remove a comment this store does not "
                                   "hold")
        updated += adds
        _one_comment_per_ref(updated)
        try:
            self._commit(mine, updated)
        except DeclarationError as e:
            raise StoreWriteError(str(e)) from None
        except Invalid as e:
            raise StoreWriteError(f"the declaration file {self._path} could not be written "
                                  f"({e}); nothing was changed") from None

    def held_ref(self, ref: str, kinds: tuple[str, ...]) -> str | None:
        """The stored spelling of `ref` among declarations of `kinds`, an address matched
        in any spelling; None when nothing is held under it. The caller's ref is read the
        way EACH held declaration was declared (its own `by`), never guessed."""
        return next((d.ref for d in self._mine() if d.kind in kinds
                     and canonical_ref(d.ref, d.by) == canonical_ref(ref, d.by)), None)

    def add(self, decl: Declaration) -> bool:
        """Store a declaration; True when it is NEW, False when this exact one was already
        held -- then ADOPTED by the caller's origin and stamp, not a refusal.

        AN EXACT DUPLICATE IS A NO-OP, not a refusal. The store persists across a
        rebuild by design, so whoever re-runs their declaration
        script after every compile -- the very workflow the store exists for -- would
        otherwise meet their own earlier declarations as a hard INVALID and have to clear
        before declaring. Nothing is stored twice; the caller learns it was already there and
        can re-arm if the debugger no longer holds it.

        ONE conflict is still refused: for a watch, the SAME `ref` carrying the OTHER half
        -- a `show` where a `change` already sits, or the reverse. A change watch reports its
        bytes at every stop already, so the show beside it would be the same reading twice,
        and a `watch_clear` of the ref has to name one declaration.
        """
        if decl.kind == "comment":
            raise DeclarationError("a comment goes through apply: add adopts by equality, "
                                   "which ignores a comment's text")
        mine = self._mine()
        i = next((i for i, d in enumerate(mine) if same_place(d, decl)), None)
        if i is not None:
            # ADOPTED, not ignored: the session re-declaring it becomes its origin, so a
            # raw address is no longer `stale` here, and the
            # stamp says when. Each half is taken from the re-declaration only when it
            # CARRIES one, so a stampless duplicate changes nothing and a half-stamped
            # one cannot blank the other half, which would turn an origin into None and
            # the declaration into a legacy one.
            held = mine[i]
            origin = decl.origin if decl.origin is not None else held.origin
            created = decl.created_at if decl.created_at is not None else held.created_at
            # A DECLARATION NO STOP PLACED (made while the guest runs, or where this stop
            # cannot place it) does not overwrite the place of a row a stop did: the held row
            # keeps its build and its mode, and is placed again only at a stop of that mode.
            placed = decl.fingerprint is not None and (decl.cpu_mode is not None
                                                       or held.cpu_mode is None)
            build, mode = ((decl.fingerprint, decl.cpu_mode) if placed
                           else (held.fingerprint, held.cpu_mode))
            if (origin, created, build, mode) != (held.origin, held.created_at,
                                                  held.fingerprint, held.cpu_mode):
                self._commit(mine, [*mine[:i], held.adopted_by(origin, created, build, mode),
                                    *mine[i + 1:]])
            return False
        if decl.kind == "watch":
            for d in mine:
                if d.kind != "watch" or d.by != decl.by \
                        or canonical_ref(d.ref, d.by) != canonical_ref(decl.ref, decl.by):
                    continue
                if d.watch_mode != decl.watch_mode:
                    raise DeclarationError(
                        f"{decl.ref!r} already has a {d.watch_mode!r} watch, and one ref "
                        f"may not be both a show AND a change watch: a change watch reports "
                        f"its value at every stop as a show watch does, so the one there "
                        f"already shows it")
                # ONE REF, ONE SHAPE: another width or format under the same name would be
                # a second declaration sharing one debugger row, and a clear by ref could
                # only half account for it, leaving the other orphaned.
                raise DeclarationError(
                    f"{decl.ref!r} is already declared as a {d.watch_mode} watch of width "
                    f"{d.width} rendered as {d.fmt}; clear it before declaring it another way")
        self._commit(mine, [*mine, decl])
        return True

    def remove(self, *, ref: str | None = None,
               kind: str | tuple[str, ...] | None = None) -> int:
        """Drop declarations and return how many went, in ONE write.

        With no argument it clears EVERYTHING for this conf. `ref` clears every declaration
        naming that symbol or address. `kind` clears one family, or several given together:
        breakpoints WITHOUT touching watches, and the reverse. The two compose: a
        `ref` and a `kind` together clear only that ref within that family.
        """
        kinds = (kind,) if isinstance(kind, str) else kind
        bad = [k for k in kinds or () if k not in KINDS]
        if bad:
            raise DeclarationError(f"kind is one of {KINDS}; got {bad[0]!r}")
        mine = self._mine()
        keep = [d for d in mine
                if not ((ref is None or d.ref == ref) and (kinds is None or d.kind in kinds))]
        removed = len(mine) - len(keep)
        if removed:
            self._commit(mine, keep)
        return removed

    @staticmethod
    def resolve_name(decl: Declaration, symbols: list[sym.Symbol],
                     index: sym.NameIndex | None = None) -> Resolved:
        """Resolve ONE by-symbol declaration against a table -- the single source of the
        name->offset half, so the store's re-resolution (below) and the server's live
        resolver cannot disagree on what a name means. A by-address declaration needs no
        table and comes back `address`. A name absent from this build is `unresolved` and
        kept; a name defined more than once resolves to the LOWEST offset and
        reports `matches > 1`, so the arming tool can refuse an ambiguity the store still
        keeps. The chosen symbol's `idle` mark is carried through for the marked-public note.
        `index` is the table's `index_by_name`, so a caller resolving many names against
        one table pays one scan for all of them and not one per name.
        """
        if decl.by == "address":
            return Resolved(decl, state="address")
        hits = (index.get(decl.ref, []) if index is not None
                else [s for s in symbols if s.name == decl.ref])
        if not hits:
            return Resolved(decl, state="unresolved")
        best = min(hits, key=lambda s: s.offset)
        return Resolved(decl, state="resolved", offset=best.offset, section=best.section,
                        matches=len(hits), idle=best.idle)

    def resolve(self, symbols: list[sym.Symbol]) -> list[Resolved]:
        """Re-point every declaration against a symbol table, keeping the vanished ones.

        Declarations by name follow the program across a rebuild, and this is the
        machine-free half of that. It delegates to `resolve_name`,
        the single name->offset routine. NOTE it is NOT what the server calls on a
        `symbols_load`: the server re-resolves per declaration through `_resolve_ref`, which
        also shares `resolve_name`, so the two cannot disagree; this whole-list form is here
        for a caller that wants every declaration's resolution at once. A by-address
        declaration needs no table and comes back `address`; a name absent from this build is
        `unresolved` and stays in the list, never dropped.

        AN AMBIGUOUS NAME -- one this build defines more than once -- resolves to the
        lowest offset and reports `matches > 1`, because refusing here would lose the
        declaration a rebuild might disambiguate. The tool that ARMS reads that count and
        refuses before it can arm the wrong one; the store keeps the intent either way.
        """
        index = sym.index_by_name(symbols)
        return [self.resolve_name(decl, symbols, index) for decl in self._mine()]
