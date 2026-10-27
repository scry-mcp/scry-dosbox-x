"""A persistent store of debugging declarations, keyed by the conf that identifies a guest.

It holds the intent, not the armed instances: a name re-resolves after a rebuild, and one
whose symbol vanished is kept unresolved, since `-O3` inlining makes that ordinary. It holds no
base, so a file from one run cannot be used against another by accident.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scry_core import declaration_file
from scry_core import value_format as vf
from scry_core.reply_contract import Invalid

import dosbox_comment_file as cf
import dosbox_grammar as grammar
import dosbox_symbols as sym

# An interrupt is declared by the debugger's BPLIST spelling (`BPINT 21`): `BPDEL` indexes are
# not the arming order.
COUNTED_KINDS = ("breakpoint", "watch", "interrupt", "regpoint")
# A comment stops and watches nothing, so it stays out of `declarations()`.
KINDS = (*COUNTED_KINDS, "comment")
# A pointer watch (`[base]+0x28`, `base->field`) re-resolves at every stop; code does not move.
# A registerpoint is declared by its condition (`expr`): it names no place.
BY = ("symbol", "address", "pointer", "expr")
# Its own regex rather than the session's: this module validates its own stored data.
INTERRUPT_ROW = re.compile(r"^BPINT [0-9A-Fa-f]{2}(?: AH=[0-9A-Fa-f]{2})?$")
# Raw row declared where its place is unknown while a map is held; not hex, so it equals no
# fingerprint.
PENDING_STAMP = "pending"
# One SEG:OFF names another byte per mode.
CPU_MODES = ("real", "protected")
# `show` arms nothing; `change` also arms a memory-change breakpoint; `count` and `capture` arm
# the debugger's `TAP`, which records without stopping; `freeze` pins each byte with `FM`.
WATCH_MODES = ("show", "change", "count", "capture", "freeze")
TAP_MODES = ("count", "capture")
#: The modes whose debugger object the server keeps by ref: armed at a stop, on one place.
KEPT_MODES = (*TAP_MODES, "freeze")
#: A capture's trigger is written (`w`) or read (`r`).
TRIGGER_TYPES = ("w", "r")
RETIRED_MODES = {"read": "show"}


def check_watch_mode(mode: str | None) -> None:
    """Refuse a mode outside the vocabulary, before any width complaint."""
    if mode not in WATCH_MODES:
        raise DeclarationError(f"mode is one of {WATCH_MODES}; got {mode!r}")
# The grammar of `value_format`: a scalar, an array (`u16[8]`), a string or a struct.
FORMATS = tuple(vf.SCALARS)
FORMAT_WIDTH = {name: size for name, (_code, size) in vf.SCALARS.items()}


class DeclarationError(Exception):
    """A declaration that cannot be stored; the MCP layer translates it into a refusal."""


def same_place(a: Declaration, b: Declaration) -> bool:
    """Whether two declarations differ only in how their address is spelt."""
    from dataclasses import replace
    return replace(a, ref=canonical_ref(a.ref, a.by)) == replace(b, ref=canonical_ref(b.ref, b.by))


def canonical_ref(ref: str, by: str) -> str:
    """The one spelling a ref is stored and matched under; an unparsable `SEG:OFF` is left as
    typed, for the tool's own refusal to name."""
    text = ref.strip()
    if by == "pointer":
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
    return grammar.canonical_seg_off(seg, off)


@dataclass(frozen=True)
class Declaration:
    """One thing a caller wants armed, by a symbol name or by a raw address.

    The store never parses an address: what it means is the debugger's to know.
    """

    kind: str
    by: str
    ref: str
    width: int | None = field(default=None, kw_only=True)
    fmt: str | None = field(default=None, kw_only=True)
    watch_mode: str | None = field(default=None, kw_only=True)
    created_at: str | None = field(default=None, kw_only=True, compare=False)
    origin: str | None = field(default=None, kw_only=True, compare=False)
    # `Build.stamp` of the batch that described the address, else the conf's fingerprint.
    fingerprint: str | None = field(default=None, kw_only=True, compare=False)
    # Separates a row made over another build from one stored before the conf was kept.
    conf_fingerprint: str | None = field(default=None, kw_only=True, compare=False)
    cpu_mode: str | None = field(default=None, kw_only=True, compare=False)
    text: str = field(default="", kw_only=True, compare=False)
    #: A write capture's trigger, the place whose writes it keeps a row of the block at.
    trigger: str | None = field(default=None, kw_only=True)
    #: A capture's access side: `w` a write of `trigger`, `r` a read of `ref` itself.
    trigger_type: str | None = field(default=None, kw_only=True)

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
        if (self.kind == "regpoint") != (self.by == "expr"):
            raise DeclarationError("a registerpoint, and only a registerpoint, is declared by "
                                   f"its condition (`expr`); got a {self.kind} by {self.by}")
        if self.kind == "regpoint":
            # A wrong spelling would list as `gone` forever and wedge the clear.
            try:
                canonical = grammar.condition_row(self.ref)
            except Invalid as e:
                raise DeclarationError(str(e)) from None
            if canonical != self.ref:
                raise DeclarationError(f"a registerpoint ref is its condition as `BPIF` prints "
                                       f"it back ({canonical!r}); got {self.ref!r}")
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
            # A sized format names its own width; every reader of `width` sees that one.
            object.__setattr__(self, "width", width)
            self._check_tap()
        elif self.kind != "comment":  # breakpoint, interrupt
            extras = {"width": self.width, "fmt": self.fmt, "watch_mode": self.watch_mode,
                      "trigger": self.trigger, "trigger_type": self.trigger_type}
            set_extras = {k: v for k, v in extras.items() if v is not None}
            if set_extras:
                raise DeclarationError(
                    f"a {self.kind} carries no watch fields; got {set_extras}")
            if self.kind == "interrupt":
                if self.by != "address":
                    raise DeclarationError(
                        "an interrupt breakpoint is declared by its number, never by a "
                        f"symbol: `by` must be 'address', got {self.by!r}")
                # A wrong spelling would list as `gone` forever and wedge the clear.
                if not INTERRUPT_ROW.match(self.ref):
                    raise DeclarationError(
                        f"an interrupt ref is the debugger's row spelling, `BPINT NN` or "
                        f"`BPINT NN AH=NN` in hex; got {self.ref!r}")

    def _check_tap(self) -> None:
        """A count names no trigger; a write capture names one; a read capture is its own."""
        if self.watch_mode not in TAP_MODES:
            if self.trigger is not None or self.trigger_type is not None:
                raise DeclarationError(f"a {self.watch_mode} watch carries no trigger")
            if self.watch_mode != "freeze":
                return
        if self.by not in ("symbol", "address"):
            raise DeclarationError(f"a {self.watch_mode} watch is declared by symbol or by "
                                   f"address: it sits on one place for its life; got "
                                   f"{self.by!r}")
        if self.watch_mode == "freeze":
            return
        if self.watch_mode == "count":
            if self.trigger is not None or self.trigger_type is not None:
                raise DeclarationError("a count watch carries no trigger")
            return
        if self.trigger_type not in TRIGGER_TYPES:
            raise DeclarationError(f"a capture's trigger_type is one of {TRIGGER_TYPES}; got "
                                   f"{self.trigger_type!r}")
        if (self.trigger is None) != (self.trigger_type == "r"):
            raise DeclarationError("a write capture names its trigger, and a read capture is "
                                   "of its own ref, with none")

    def _check_comment(self) -> None:
        """Hold a comment to the comment file's rules, so a hand-edited store cannot break them."""
        if self.by not in ("symbol", "address"):
            raise DeclarationError(f"a comment is declared by symbol or by address; got "
                                   f"{self.by!r}")
        if (":" in self.ref) != (self.by == "address"):
            raise DeclarationError(f"a comment by {self.by} cannot have the ref {self.ref!r}: "
                                   "an address carries a colon and a symbol does not")
        extras = {"width": self.width, "fmt": self.fmt, "watch_mode": self.watch_mode,
                  "trigger": self.trigger, "trigger_type": self.trigger_type}
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
            if self.trigger is not None:
                d["trigger"] = self.trigger
            if self.trigger_type is not None:
                d["trigger_type"] = self.trigger_type
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
        """The same declaration re-declared from another session; a None build keeps the held."""
        held = fingerprint is None
        return Declaration(self.kind, self.by, self.ref, width=self.width, fmt=self.fmt,
                           watch_mode=self.watch_mode, created_at=created_at, origin=origin,
                           fingerprint=self.fingerprint if held else fingerprint,
                           cpu_mode=self.cpu_mode if held else cpu_mode,
                           trigger=self.trigger, trigger_type=self.trigger_type)

    @staticmethod
    def from_dict(d: dict[str, object]) -> Declaration:
        """Rebuild a declaration from a stored object, refusing corruption as `DeclarationError`."""
        # `str(None)` is "None", a truthy ref that would sail past the refusal below.
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
        mode = RETIRED_MODES.get(str(wm), str(wm)) if wm is not None else None
        trigger, side = d.get("trigger"), d.get("trigger_type")
        return Declaration(kind=kind, by=by, ref=ref, width=width,
                           fmt=str(fmt) if fmt is not None else None,
                           watch_mode=mode,
                           created_at=created_at, origin=origin, fingerprint=fingerprint,
                           cpu_mode=cpu_mode,
                           trigger=str(trigger) if trigger is not None else None,
                           trigger_type=str(side) if side is not None else None)


Entry = tuple[str, int]


@dataclass(frozen=True)
class Build:
    """One batch a `symbols_load` loaded: the conf's fingerprint and its sorted entries (a
    repeated line kept twice). A raw row is judged by the one batch whose span describes its
    address. Held in memory only; a row carries just the stamp."""

    conf: str
    entries: tuple[Entry, ...]
    stamp: str = field(init=False, repr=False, compare=False)
    _span: tuple[int, int] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
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
        """Whether `linear` lies between the batch's lowest and highest entry."""
        return self._span is not None and self._span[0] <= linear <= self._span[1]


def _entry_text(entry: Entry) -> str:
    return f"{entry[0]}\t{entry[1]:X}"


def is_raw_code(kind: str, by: str) -> bool:
    """Whether a row is a raw code breakpoint or comment, the rows batches judge."""
    return kind in ("breakpoint", "comment") and by == "address"


def keeps_mode(kind: str, by: str) -> bool:
    """Whether a row keeps the cpu mode of its placing stop: any raw `SEG:OFF` row."""
    return by == "address" and kind in ("breakpoint", "comment", "watch")


#: What a raw row with no cpu mode waits for: a stop that places it.
UNPLACED = "unplaced"


def waits(decl: Declaration, stop_mode: Callable[[], str | None]) -> str | None:
    """Why a raw row is neither judged nor armed at this stop, or None when it is judged here.

    The answer is the mode it waits for, or `UNPLACED`. `stop_mode` is asked only of a row that
    recorded a mode."""
    if not keeps_mode(decl.kind, decl.by):
        return None
    if decl.cpu_mode is None:
        return UNPLACED
    return None if stop_mode() == decl.cpu_mode else decl.cpu_mode


def raw_staleness(decl: Declaration, conf: str | None, batches: Sequence[Build],
                  place_now: Callable[[], int | None]) -> str | None:
    """Why a raw code breakpoint or comment is not known to be this build's, or None when it is.

    Fresh while the batch its stamp names is held (`batches`). Otherwise a held batch describing
    its address (`place_now`, asked only then; None counts as described) makes it `other`, or
    `unrecorded` when the conf alone is the stamp. With none describing it: `other` if it
    recorded a conf, else `no_conf`. `PENDING_STAMP` is `pending`. By-symbol rows, interrupts
    and watches are never stale, and with no conf nothing is judged.
    """
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

    `state` is `address`, `resolved` or `unresolved` (a vanished symbol is kept). `matches`
    counts the symbols the name resolved to, so the arming tool can refuse an ambiguous name.
    """

    decl: Declaration
    state: str
    offset: int | None = None
    section: int | None = None
    matches: int = 0
    idle: bool = False    # the linker's mark on the chosen symbol, passed through


def default_path() -> Path:
    """Where the declarations live by default: a state directory, not a cache."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "dosbox-x-debug" / "declarations.json"


def _one_comment_per_ref(decls: Sequence[Declaration]) -> None:
    """Refuse a ref held twice: a comment file holds one row per ref."""
    seen: set[str] = set()
    for d in decls:
        if d.kind != "comment":
            continue
        ref = canonical_ref(d.ref, d.by)
        if ref in seen:
            raise DeclarationError(f"a stored comment at {ref!r} twice: a comment file holds "
                                   "one row per ref, and so does the store")
        seen.add(ref)


#: Key an older store wrote batches under: ignored on read, dropped on the next write.
BUILDS_KEY = "builds"


class StoreWriteError(Exception):
    """The store's file could not be written and the change was rolled back (`_commit`)."""


class DeclarationStore:
    """The declarations for one guest, backed by a file shared by every guest.

    Stores over one file with different identities cannot see each other's rows: a symbol from
    another binary would arm at a wrong address.
    """

    def __init__(self, conf_identity: str, path: Path | None = None) -> None:
        if not conf_identity:
            raise DeclarationError("a store needs a non-empty conf identity to key by")
        self._conf = conf_identity
        self._path = path or default_path()
        rows = declaration_file.rows(declaration_file.read(self._path, DeclarationError),
                                     conf_identity, DeclarationError)
        self._items = [Declaration.from_dict(d) for d in rows]
        _one_comment_per_ref(self._items)

    def _commit(self, mine: list[Declaration], new: list[Declaration]) -> None:
        """This conf's rows become `new` and are written; a failed write puts them back."""
        old = list(mine)
        mine[:] = new
        try:
            self._persist()
        except OSError as e:
            mine[:] = old
            raise DeclarationError(f"the declaration file {self._path} could not be written "
                                   f"({e}); nothing was changed") from None
        except BaseException:
            mine[:] = old
            raise

    def _persist(self) -> None:
        declaration_file.write(self._path, self._conf, [d.to_dict() for d in self._items],
                               DeclarationError, self._drop_my_builds)

    def _drop_my_builds(self, raw: dict[str, object]) -> None:
        every = raw.get(BUILDS_KEY)
        if isinstance(every, Mapping):
            rest = {k: v for k, v in every.items() if k != self._conf}
            if rest:
                raw[BUILDS_KEY] = rest
            else:
                raw.pop(BUILDS_KEY)

    def _mine(self) -> list[Declaration]:
        return self._items

    @property
    def path(self) -> Path:
        """The file this store persists to."""
        return self._path

    def declarations(self) -> list[Declaration]:
        """This conf's declarations that stop or watch, in the order added (no comments)."""
        return [d for d in self._mine() if d.kind in COUNTED_KINDS]

    def comments(self) -> list[Declaration]:
        """This conf's comments, in the order they were added."""
        return [d for d in self._mine() if d.kind == "comment"]

    def apply(self, *, adds: Sequence[Declaration] = (),
              replaces: Sequence[tuple[Declaration, Declaration]] = (),
              removes: Sequence[Declaration] = ()) -> None:
        """Several comment changes persisted once, so a load lands whole or not at all.

        A row of another kind may be replaced only by itself with new stamps. A row not held is
        a programmer's error. A failed write rolls everything back (`StoreWriteError`)."""
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
        """The stored spelling of `ref` among `kinds`, matched in any spelling, else None."""
        return next((d.ref for d in self._mine() if d.kind in kinds
                     and canonical_ref(d.ref, d.by) == canonical_ref(ref, d.by)), None)

    def add(self, decl: Declaration) -> bool:
        """Store a declaration; True when new, False when held already (then adopted).

        An exact duplicate is a no-op, not a refusal, so re-running a declaration script after
        every compile works. One conflict is refused: a watch with the same `ref` in the other
        half (`show` against `change`), since a change watch already reports its bytes at every
        stop and a clear of the ref has to name one declaration.
        """
        if decl.kind == "comment":
            raise DeclarationError("a comment goes through apply: add adopts by equality, "
                                   "which ignores a comment's text")
        mine = self._mine()
        i = next((i for i, d in enumerate(mine) if same_place(d, decl)), None)
        if i is not None:
            # A half-stamped duplicate must not blank the other half.
            held = mine[i]
            origin = decl.origin if decl.origin is not None else held.origin
            created = decl.created_at if decl.created_at is not None else held.created_at
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
                # Two shapes under one ref would share a debugger row and orphan half a clear.
                raise DeclarationError(
                    f"{decl.ref!r} is already declared as a {d.watch_mode} watch of width "
                    f"{d.width} rendered as {d.fmt}; clear it before declaring it another way")
        self._commit(mine, [*mine, decl])
        return True

    def remove(self, *, ref: str | None = None,
               kind: str | tuple[str, ...] | None = None) -> int:
        """Drop declarations and return how many went, in one write.

        No argument clears everything for this conf; `ref` and `kind` (one or several) narrow
        it and compose.
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
        """Resolve one declaration against a table, the routine the server's resolver shares.

        A name defined more than once resolves to the lowest offset with `matches > 1`.
        `index` is the table's `index_by_name`.
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

        The server resolves per declaration through `_resolve_ref`, not this whole-list form.
        An ambiguous name is not refused here: a rebuild might disambiguate it.
        """
        index = sym.index_by_name(symbols)
        return [self.resolve_name(decl, symbols, index) for decl in self._mine()]
