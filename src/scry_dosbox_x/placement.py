"""Symbol placement: a name or a raw `SEG:OFF` to the seg:off the debugger wants, per mode."""

from __future__ import annotations

import bisect
import dataclasses
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from scry_core import judges, prose
from scry_core import value_format as vf

from scry_dosbox_x import coff, grammar
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x import symbols as sym
from scry_dosbox_x.state import STATE


def decide_by(ref: str) -> str:
    """`address` for a raw `SEG:OFF`, `symbol` otherwise.

    The colon is the only tell: a demangled `ns::fn` would be refused by the seg:off parser,
    and `by="symbol"` forces the lookup."""
    if vf.parse_pointer(ref) is not None:
        return "pointer"
    return "address" if ":" in ref.strip() else "symbol"


def address_shape(ref: str, by: str | None = None) -> None:
    """Refuse an unparseable raw address before it is stored, or it stays `unarmable`."""
    chosen = decide_by(ref) if by is None else by
    if chosen == "address":
        parse_seg_off(ref)


_HEX_ADDR = re.compile(r"(?:0[xX])?[0-9a-fA-F]+")


def hex_arg(name: str, value: object) -> int:
    """A hex address argument, or a refusal naming it. `int(value, 16)` alone takes a sign and
    underscores; an integer is refused, not coerced, so no caller converts hex to decimal."""
    if not isinstance(value, str) or not _HEX_ADDR.fullmatch(value.strip()):
        raise ds.Invalid("bad_argument",
            f"{name} is {value!r}, which is not a hex address like `1000` or `0x1000` "
            f"(text, not a number: a decimal conversion is the mistake this refuses)")
    return int(value, 16)


def hex_bases(section_bases: dict[str, str]) -> dict[str, int]:
    """`section_bases` with every value through `hex_arg`, each refusal naming its section."""
    if not isinstance(section_bases, dict):
        raise ds.Invalid("bad_argument", f"section_bases is a mapping of section index to hex "
                         f"base; got {section_bases!r}")
    return {k: hex_arg(f"section_bases[{k!r}]", v) for k, v in section_bases.items()}


def parse_seg_off(ref: str) -> tuple[int, int]:
    """A raw `SEG:OFF` in hex into a pair; a bare linear number has no segment to arm at."""
    r = ref.strip()
    if ":" not in r:
        raise ds.Invalid("bad_argument",
            f"a raw address is SEG:OFF in hex (e.g. 00A7:0016DD80); got {ref!r}. A bare "
            f"linear address has no segment to arm at -- use a symbol, which carries one")
    seg_s, off_s = r.split(":", 1)
    # `int(..., 16)` alone takes `0038:-10` as offset -16.
    if not (_HEX_ADDR.fullmatch(seg_s.strip()) and _HEX_ADDR.fullmatch(off_s.strip())):
        raise ds.Invalid("bad_argument", f"{ref!r} is not a hex SEG:OFF: hex digits each side, "
                         "with or without `0x`, no sign")
    seg, off = int(seg_s, 16), int(off_s, 16)
    # Judged here so no tool takes a segment it cannot address (an armed one could never be
    # cleared); the offset's ceiling depends on the cpu mode and waits for the machine.
    ds.check_segment(seg)
    return seg, off


def _listening(session: ds.Session) -> None:
    """Refuse a placement against the registers of a machine that is not stopped."""
    session.require_stopped("a placement against its registers")


def _program_selectors(session: ds.Session, desc: dict[str, int],
                       measured_by_cs: bool) -> dict[str, int]:
    """CS and DS of this stop when they are the program's (protected mode, CS on the table's
    base); nothing at a real-mode stop, a running guest, or a DPMI host's code."""
    if not session.at_debugger():
        return {}
    where, regs = session.where_and_registers()
    if not where["mode"].startswith("Pr") or not {"CS", "DS"} <= set(regs):
        return {}
    if not measured_by_cs and session.selector("CS")["base"] != desc["base"]:
        return {}
    return {f"selector_{reg}": int(regs[reg], 16) for reg in ("CS", "DS")}


PLACE_KEYS = ("base", "limit", "type")


#: A protected-mode program's symbol at a stop that is not in protected mode.
OUTSIDE_THE_PROGRAM = (
    "the machine stopped outside the program: its table was loaded at a protected-mode stop, and "
    "this real-mode stop (a BIOS or DOS handler the program called into) has no selector to "
    "place its symbols through. A breakpoint armed before the release brings it back into the "
    "program's code")


def target_for(offset: int, reg: str, session: ds.Session, *,
                machine: tuple[str, dict[str, str]] | None = None) -> tuple[int, int]:
    """The seg:off to arm at a symbol OFFSET, derived from the machine's mode.

    `machine` is a `(mode, registers)` pair the caller read once, saving a channel round trip
    per declaration in a stop reply.

    Protected mode: the offset is the breakpoint offset. Real mode: the load paragraph plus
    the folded offset, split to fit 16 bits. Assumes DS and CS share a base (DJGPP's flat
    layout); a non-flat program would arm a data watch at the wrong address undetected.
    """
    if machine is None:
        _listening(session)
    mode = machine[0] if machine is not None else session.where()["mode"]
    selector = STATE.base.get(f"selector_{reg}")
    if selector is not None:
        if not mode.startswith("Pr"):
            raise ds.Invalid("bad_argument", OUTSIDE_THE_PROGRAM)
        return selector, offset
    if mode.startswith("Pr"):
        regs = machine[1] if machine is not None else session.registers()
        return int(regs[reg], 16), offset
    if STATE.base.get("base", -1) < 0:
        raise ds.Invalid("bad_argument",
            "a real-mode symbol needs a FLAT base from symbols_load (`base`), and this table "
            "has none -- it is sectioned, or none is loaded. Load a real-mode map first")
    base_seg = STATE.base["base"] // 16
    ds.check_segment(base_seg)              # a base past a megabyte addresses nothing in real mode
    if offset <= 0xFFFF:
        return base_seg, offset
    linear = base_seg * 16 + offset          # a high real-mode offset (a data segment)
    if linear > 0xFFFFF:
        raise ds.Invalid("bad_argument",
            f"the symbol folds to linear 0x{linear:X}, past the 0xFFFFF this paragraph split "
            f"can express; the split would drop bit 20 and arm the wrong "
            f"address. Arm by an explicit SEG:OFF, or load this map in protected mode")
    return (linear >> 4) & 0xFFFF, linear & 0xF


def resolve_ref(decl: dec.Declaration, reg: str, session: ds.Session, *,
                 machine: tuple[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """A declaration -> what the debugger needs to arm it, or the state that is not armable.

    Returns `state` (and `seg`, `off`, the linker's mark when `armable`); never raises:

    * `armable` -- one address, workable now.
    * `unresolved` -- no such symbol in this build; kept for the next one.
    * `ambiguous` -- several matches (`matches`, `why`); `breakpoint_at` refuses it.
    * `unarmable` -- resolved, but no address now (`why`): guest running, no flat base, or
      past the 1 MB real mode reaches. The intent is kept.
    """
    if decl.by == "pointer":
        return _resolve_pointer(decl, reg, session, machine)
    if decl.by == "address":
        # The file is the one unvalidated input; raising here would make list and clear die
        # on one bad row, so it could never be removed.
        try:
            seg, off = parse_seg_off(decl.ref)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": f"stored address {decl.ref!r} cannot be "
                                                  f"read: {e}. Clear it by this ref"}
        return {"state": "armable", "seg": seg, "off": off, "marked": False}
    # Same `resolve_name` as `symbols_load`'s re-resolution; only the live seg:off is added here.
    r = dec.DeclarationStore.resolve_name(decl, STATE.table, STATE.name_index)
    if r.state == "unresolved":
        return {"state": "unresolved"}
    if r.matches > 1:
        return {"state": "ambiguous", "matches": r.matches,
                "why": prose.ambiguous_name(decl.ref, candidates(decl.ref), IN_THIS_BUILD)}
    try:
        seg, off = target_for(cast(int, r.offset), reg, session, machine=machine)
    except ds.Invalid as e:
        return {"state": "unarmable", "why": str(e)}
    return {"state": "armable", "seg": seg, "off": off, "marked": r.idle}


IN_THIS_BUILD = "this build"


def candidates(name: str) -> list[str]:
    """The table's own addresses of every symbol `name` names, in the table's order: the offset,
    with its section when the table has several."""
    hits = STATE.name_index.get(sym.folded(name), [])
    several = len({s.section for s in hits}) > 1
    return [f"section {s.section} {s.offset:#x}" if several else f"{s.offset:#x}" for s in hits]


def to_invalid(fn: Callable[[], Any]) -> Any:
    """Run a store call, turning `DeclarationError` into the `Invalid` `tool()` catches."""
    try:
        return fn()
    except dec.DeclarationError as e:
        raise ds.Invalid("bad_argument", str(e)) from None


def _resolve_pointer(decl: dec.Declaration, reg: str, session: ds.Session,
                     machine: tuple[str, dict[str, str]] | None) -> dict[str, Any]:
    """A pointer ref against the machine now: a NEAR pointer read at the base in its segment
    (width from `ptr16`/`ptr32`, else 4 bytes protected, 2 real) plus the offset.
    `null_pointer` when it holds zero, never a watch at zero."""
    pr = vf.parse_pointer(decl.ref)
    assert pr is not None
    if machine is None:
        try:
            _listening(session)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": str(e)}
    if ":" in pr.base:
        try:
            seg, off = parse_seg_off(pr.base)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": str(e)}
    else:
        base = dec.DeclarationStore.resolve_name(
            dec.Declaration("breakpoint", "symbol", pr.base), STATE.table, STATE.name_index)
        if base.state == "unresolved":
            return {"state": "unresolved", "why": (
                f"{pr.base!r} {NOT_IN_TABLE} and is not a SEG:OFF, so there is no "
                f"pointer to start from: a stack local has no stable address, and a pointer "
                f"ref needs a GLOBAL (a symbol of the table, or an address) as its base")}
        if base.matches > 1:
            return {"state": "ambiguous", "matches": base.matches,
                    "why": prose.ambiguous_name(pr.base, candidates(pr.base), IN_THIS_BUILD)}
        try:
            seg, off = target_for(cast(int, base.offset), reg, session, machine=machine)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": str(e)}
    spec = STATE.symbol_types.get(pr.base.strip().upper())
    fmt = vf.parse(spec) if spec else None
    width = fmt.size if fmt is not None and fmt.kind == "pointer" else None
    offset = pr.offset
    if pr.field is not None:
        if (fmt is None or fmt.kind != "pointer" or fmt.target is None
                or fmt.target.kind != "struct"):
            return {"state": "unresolved", "why": (
                f"`{pr.base}->{pr.field}` needs {pr.base} typed as a pointer to a struct "
                f"(`ptr32{{...}}` or `ptr16{{...}}` in the `types` file); it is "
                f"{spec or 'untyped'}. Or name the offset: `[{pr.base}]+0x..`")}
        try:
            offset, _ = vf.field_offset(fmt.target, pr.field)
        except vf.FormatError as e:
            return {"state": "unresolved", "why": str(e)}
    try:
        mode = machine[0] if machine is not None else session.where()["mode"]
        pw = width or (4 if mode.startswith("Pr") else 2)
        raw = session.read_bytes(seg, off, pw, mode=mode)
    except ds.Invalid as e:
        return {"state": "unarmable", "why": str(e)}
    value = int.from_bytes(raw, "little")
    info: dict[str, Any] = {"at": st.seg_off(seg, off), "length": pw,
                            "value": f"{value:04X}", "offset": offset}
    if pr.field is not None:
        info["field"] = pr.field
    if value == 0:
        return {"state": "null_pointer", "pointer": info, "why": (
            f"the pointer at {info['at']} is null, so there is nothing to watch yet; the "
            f"declaration is kept and re-resolved at every stop")}
    target = value + offset
    if not 0 <= target <= grammar.offset_ceiling(mode):
        return {"state": "unarmable", "pointer": info, "why": (
            f"the pointer plus the offset, {target:#x}, is outside what an offset can be "
            f"in {mode} mode")}
    info["target"] = st.seg_off(seg, target)
    return {"state": "armable", "seg": seg, "off": target, "marked": False, "pointer": info}


def read_target(ref: str, reg: str, session: ds.Session, *,
                 machine: tuple[str, dict[str, str]] | None = None) -> tuple[int, int]:
    """The seg:off a reader (`read_memory`, `memdump`) reads at, from a symbol or a `SEG:OFF`.

    A read needs an address now, so an absent or ambiguous name is refused, not stored.
    """
    if decide_by(ref) == "address":
        return parse_seg_off(ref)
    # An empty ref raises `DeclarationError`, which the tool wrapper does not catch.
    decl = to_invalid(lambda: dec.Declaration("breakpoint", "symbol", ref))
    res = resolve_ref(decl, reg, session, machine=machine)
    if res["state"] == "armable":
        return res["seg"], res["off"]
    if res["state"] == "unresolved":
        raise ds.Invalid("unknown_ref", f"{ref!r} {NOT_IN_TABLE}, so there is no address to "
                         f"read")
    if not session.at_debugger():
        why = res.get("why")
        raise ds.NotStopped(f"{why}; and a read needs the machine stopped anyway" if why else
                            f"the guest is running, so {ref!r} cannot be placed now, and a "
                            f"read needs the machine stopped anyway")
    raise ds.Invalid("ambiguous_ref" if res["state"] == "ambiguous" else "unknown_ref",
        str(res.get("why", f"{ref!r} cannot be resolved to an address")))


def _placed(s: sym.Symbol) -> dict[str, Any]:
    """One symbol: name, kind, the toolchain's offset and the debugger's linear address (so
    the reader does no arithmetic), and whether the address is conditional (`idle`)."""
    # `idle` is Borland's overlay mark passed through, per symbol because the `overlay_idle`
    # total cannot say whether this name carries it; false for `nm` and GNU-map symbols.
    return {"name": s.name, "kind": s.kind, "offset": s.offset, "section": s.section,
            "addr": st.flat(linear_of(s)), "idle": s.idle}


def linear_of(s: sym.Symbol) -> int:
    """A symbol's linear address against the table loaded now."""
    bases = STATE.section_bases if STATE.section_bases else {sym.FLAT: STATE.base["base"]}
    return sym.place(s, bases)


def read_types(value: str) -> dict[str, str]:
    """A `types` file for `symbols_load`, by absolute path; a refusal names file and line."""
    text = judges.read_text("types", value, "types file")
    try:
        return vf.read_types(text, value)
    except vf.FormatError as e:
        raise ds.Invalid("bad_argument", str(e)) from None


def load(session: ds.Session, source: str, src: Path, base: int | None, base_from: str,
         pattern: str | None, keep_noise: bool, section_bases: dict[str, int] | None,
         rearm_declarations: Callable[[ds.Session], dict[str, Any]],
         take_the_map: Callable[[ds.Session], str | None],
         types: dict[str, str] | None = None) -> dict[str, Any]:
    """The body of `symbols_load`: parse, place, install the table here and in the debugger
    (queued while the guest runs), re-arm stored declarations, stamp raw comments
    (`take_the_map`: the store's write error or None). Callbacks avoid an import cycle."""
    # Lenient: a DOS map may carry code page 437 bytes.
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ds.Invalid("bad_argument",
            f"cannot read {src}: {exc!r}. That is the symbol list this "
                         f"was asked to load, so there is nothing to load") from None
    try:
        syms, unreadable = sym.parse(text)
        sym.check_folded(syms, text)
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", f"{source}: {e}") from None
    # A stale table resolves every name a few bytes off and nothing in it says so.
    checked = coff.check(src, syms)
    # No file prefix: a pattern that will not compile is not the file's fault.
    try:
        plan = sym.plan(syms, pattern=pattern, keep_noise=keep_noise,
                        unreadable=unreadable)
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", str(e)) from None
    # An explicit base has limit -1, not an invented one. A sectioned map probes nothing, so
    # `base_from` is not consulted. JSON keys arrive as strings; a `"1"` key matches no symbol.
    bases: dict[int, int] | None = None
    if section_bases is not None:
        try:
            bases = {int(k, 0): v for k, v in section_bases.items()}
        except (TypeError, ValueError) as exc:
            raise ds.Invalid("bad_argument",
                f"`section_bases` keys must be section indices: {exc}. They arrive as "
                f"JSON strings and are read as numbers, so `{{\"1\": \"0x401000\"}}` is the "
                f"shape") from None
        desc = {"base": -1, "limit": -1, "type": -1}
    else:
        # `SELINFO` prints no descriptor line in real mode, so the parser's refusal would
        # name the wrong cause.
        if base is None and grammar.real_segments(session.where()["mode"]):
            raise ds.Invalid("bad_argument",
                "the machine is in real mode, where there is no descriptor to measure a base "
                "from: pass `base` (a flat map) as hex text, the load segment * 16 (segment "
                "0x0800 is \"8000\"), or `section_bases` (a sectioned map). Placed at base 0, "
                "every symbol would sit at its raw offset")
        desc = (session.selector(base_from) if base is None
                else {"base": base, "limit": -1, "type": -1})
        # A later stop may hold another program's selectors or none; symbols keep the program's.
        desc.update(_program_selectors(session, desc,
                                       base is None and base_from.upper() == "CS"))
    try:
        data = (sym.encode(plan, section_bases=bases) if bases is not None
                else sym.encode(plan, desc["base"]))
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", str(e)) from None
    # Installed only after the debugger has taken the file, which can refuse. It accumulates
    # like `LV` (or batches orphan earlier breakpoints) while the placement holds; a moved
    # base or section bases REPLACES, as old offsets would re-place unmeasured.
    same_place = (bool(STATE.table)
                  and all(STATE.base.get(k) == desc.get(k) for k in PLACE_KEYS)
                  and dict(STATE.section_bases) == dict(bases or {}))
    if same_place:
        # Keep the selectors it was measured with when this stop cannot give them.
        for key in ("selector_CS", "selector_DS"):
            if key in STATE.base and key not in desc:
                desc[key] = STATE.base[key]
    # Types are judged before anything is written, against the names the table will hold
    # (an accumulating load includes the earlier batches).
    known = {s.name.upper() for s in plan.symbols}
    if same_place:
        known |= {s.name.upper() for s in STATE.table}
    unknown = sorted(n for n in (types or {}) if n not in known)
    if unknown:
        raise ds.Invalid("bad_argument",
                         f"types are named for symbols the table lacks: {unknown[:5]}")
    # A queued batch is joined when this one accumulates, superseded when it replaces.
    queued = STATE.pending["load"]
    if queued and same_place:
        try:
            data = sym.joined(queued, data)
        except sym.BadSymbolText as e:
            raise ds.Invalid("bad_argument", str(e)) from None
    if session.at_debugger():
        held = session.load_symbols(data)
        STATE.pending["load"] = None
        pending = False
    else:
        # Guest running: held here now, loaded into the debugger at the next stop.
        STATE.pending["load"] = data
        STATE.pending["dirty"] = True
        held, pending = [], True
    STATE.install_table(plan.symbols, accumulate=same_place)
    table_mode = "accumulated" if same_place else "replaced"
    if not same_place:
        STATE.symbol_types.clear()
    STATE.symbol_types.update(types or {})
    STATE.base.clear()
    STATE.base.update(desc)
    STATE.base_measured_from = base_from.upper() if base is None and bases is None else None
    # `symbols_find` places by these; the flat base is the `-1` sentinel for a sectioned load.
    STATE.section_bases.clear()
    if bases is not None:
        STATE.section_bases.update(bases)
    # Breakpoints follow a rebuild's new map. The batch is held before the re-arm judges
    # raw addresses stale against it.
    take_the_batch(plan.symbols, accumulate=same_place)
    # Taken first so the re-arm arms what the load placed; a running guest places nothing.
    unwritten = None if pending else take_the_map(session)
    rearm = ({"deferred": True,
              "note": "the re-arm runs at the next stop, after the debugger takes the load"}
             if pending else rearm_declarations(session))
    if unwritten is not None:
        raise ds.Invalid("host_failed",
            f"the symbols are loaded and the re-arm ran, but {unwritten}: the comments this "
            "session placed before any map keep their place as it was, and a later load "
            "takes them")
    return st.reply(base=desc["base"], limit=desc["limit"], descriptor=desc["type"],
                  declarations=rearm, pending=pending, checked=checked,
                  base_from=("caller" if base is not None else base_from.upper()),
                  parsed=plan.parsed, kept=plan.kept,
                  excluded_sections=plan.excluded_noise,
                  excluded_pattern=plan.excluded_pattern,
                  excluded_unplaceable=plan.excluded_unplaceable,
                  unencodable=plan.unencodable[:8],
                  unencodable_total=len(plan.unencodable),
                  truncated_names=plan.truncated_names,
                  disambiguated=plan.disambiguated,
                  # `truncated_names` misses a name that fitted but carries a `~n`.
                  renamed=plan.renamed, unreadable=plan.unreadable,
                  # A subset of `kept`, not a bucket beside it.
                  overlay_idle=plan.overlay_idle,
                  table_mode=table_mode, table_total=len(STATE.table),
                  loaded=len(held), bytes=len(data), symbols_typed=len(types or {}))


def take_the_batch(symbols: list[sym.Symbol], accumulate: bool) -> None:
    """Hold the batch a load placed, beside earlier ones (`accumulate`) or alone."""
    conf = STATE.conf_fingerprint
    if conf is None:
        return
    batch = dec.Build.of(conf, [(s.name, linear_of(s)) for s in symbols])
    # A map loaded again replaces its own batch.
    kept = [held for held in STATE.map_batches if held.stamp != batch.stamp]
    STATE.map_batches = [*kept, batch] if accumulate else [batch]


def stamp_at(linear: int | None, raw: bool) -> str | None:
    """The stamp a row at `linear` takes: the latest batch whose span holds it, else the conf.
    A raw code row with no known place while a batch is held is `dec.PENDING_STAMP`."""
    cover = next((b for b in reversed(STATE.map_batches)
                  if linear is not None and b.covers(linear)), None)
    if cover is not None:
        return cover.stamp
    if raw and linear is None and STATE.map_batches:
        return dec.PENDING_STAMP
    return STATE.conf_fingerprint


def staleness(decl: dec.Declaration, place_now: Callable[[], int | None]) -> str | None:
    """Why a raw row is not known to be this build's (`dec.raw_staleness`), or None.
    A pending row of this session is judged by the stamp it takes where it is placed now."""
    if decl.fingerprint == dec.PENDING_STAMP and decl.origin == STATE.session_origin \
            and STATE.session_origin is not None:
        linear = place_now()
        stamp = stamp_at(linear, raw=True)
        decl, place_now = dataclasses.replace(decl, fingerprint=stamp), lambda: linear
    return dec.raw_staleness(decl, STATE.conf_fingerprint, STATE.map_batches, place_now)


def is_stale(decl: dec.Declaration, place_now: Callable[[], int | None]) -> bool:
    return staleness(decl, place_now) is not None


def mode_word(cpu: str | None) -> str | None:
    """A stop's cpu mode as a raw row records it (`dec.CPU_MODES`); VM86 is real; else None."""
    if cpu is not None and grammar.real_segments(cpu):
        return "real"
    return "protected" if cpu is not None and cpu.startswith("Pr") else None


NOT_IN_TABLE = ("is not in the symbol table loaded now (none is loaded, or it does not define "
                "the name)")


def waits(decl: dec.Declaration, cpu: Callable[[], str | None]) -> str | None:
    """`dec.waits` at this stop: the mode a raw row waits for, `dec.UNPLACED`, or None when
    judged here. A waiting row is `unarmable`, named by `waits_why`."""
    return dec.waits(decl, lambda: mode_word(cpu()))


def waits_why(mode: str, again: str, here: bool = True) -> str:
    """Why a row placed in `mode` (or `dec.UNPLACED`) waits; `again` is the gesture that
    places it, offered only when `here` (this stop can place the address)."""
    if mode == dec.UNPLACED:
        return ("no stop has placed it (declared while the guest ran, declared or loaded where "
                "its stop could not place it, or stored before modes were kept), and a SEG:OFF "
                "names one byte in real mode and another in protected mode: judged and armed "
                f"in neither until a stop places it. {again} at a stop that places it")
    said = (f"placed at a {mode}-mode stop, and its SEG:OFF names another byte in the other "
            f"mode: judged and armed only at a {mode}-mode stop")
    if not here:
        return f"{said}, which it waits for (this one cannot place it in its own mode)"
    return f"{said}. {again} at this stop to place it in this mode"


SYMBOLS_LIMIT_MAX = 50


def check_find_args(name: str | None, offset: int | None, linear: str | None,
                    limit: int) -> None:
    """The refusals `symbols_find` makes on its arguments alone; shared so a list's preflight
    refuses the same step before an earlier one has pressed a key."""
    given = [x is not None for x in (name, offset, linear)]
    if sum(given) != 1:
        raise ds.Invalid("bad_argument", "ask for exactly one of `name`, `offset` or `linear`. Two "
                         "questions in one call cannot both be the answer, and none "
                         "is not a question")
    if linear is not None:
        hex_arg("linear", linear)
    if name is None:
        return
    if isinstance(limit, bool) or not isinstance(limit, int):
        # A list step delivers untyped values; a string would be an untranslated TypeError.
        raise ds.Invalid("bad_argument", f"limit is a number of symbols; got {limit!r}")
    if limit <= 0:
        raise ds.Invalid("bad_argument",
            f"a limit of {limit} would return nothing and call it a "
                         f"result")
    if limit > SYMBOLS_LIMIT_MAX:
        raise ds.Invalid("bad_argument",
            f"limit={limit} is outside 1..{SYMBOLS_LIMIT_MAX}: each symbol answered "
                         f"costs the conversation a row, and a prefix that matches more "
                         f"than that is a listing, not a lookup. Narrow the name")
    if not name:
        raise ds.Invalid("bad_argument",
            "an empty name matches every symbol by prefix, which is "
                         "a listing and not a lookup. Ask for a name")


def find(name: str | None, offset: int | None, section: int | None,
         linear_hex: str | None, limit: int) -> dict[str, Any]:
    """The body of the `symbols_find` tool, answering off the table held here."""
    if not STATE.table:
        raise ds.Invalid("no_channel", "no symbol table is loaded. `symbols_load` one first; an "
                         "answer from an empty table would be a reading of nothing")
    check_find_args(name, offset, linear_hex, limit)
    linear = None if linear_hex is None else hex_arg("linear", linear_hex)
    if name is not None:
        hits = sym.find_by_name(STATE.table, name, STATE.name_index)
        return st.reply(query=name, symbols_total=len(hits),
                      symbols=[_placed(s) for s in hits[:limit]],
                      truncated=len(hits) > limit)
    # The table holds offsets, so the base comes off `linear`; a stale base answers silently
    # wrong, hence `_forget_symbols` on every session change.
    if not STATE.section_bases:
        if section is not None and section != sym.FLAT:
            raise ds.Invalid("bad_argument",
                f"this table was loaded FLAT, so it has no section {section}. Ask "
                f"without `section`, or reload with `section_bases` if the map is "
                f"sectioned")
        want_section = sym.FLAT
    elif section is not None:
        want_section = section
    elif linear is not None:
        # A linear address names its section: the greatest base at or below it.
        want_section = _linear_section(linear)
    else:
        raise ds.Invalid("bad_argument",
            f"this table is SECTIONED and an offset alone does not name an address: "
            f"its sections overlap, so 0x{offset:X} is a different address in each of "
            f"{sorted(STATE.section_bases)}. Pass `section`, or ask by `linear`, which says "
            f"which section it is in by itself")
    if offset is not None:
        want = offset
    else:
        assert linear is not None      # exactly one of the three was given, checked above
        base = (STATE.section_bases[want_section] if STATE.section_bases else STATE.base["base"])
        want = linear - base
    return st.reply(**_nearest_offset(want, want_section))


def _linear_section(linear: int) -> int:
    """The section of a sectioned table a linear address falls in."""
    under = [i for i, b in STATE.section_bases.items() if b <= linear]
    if not under:
        raise ds.Invalid("unknown_ref",
            f"0x{linear:X} is below every section this table was placed at "
            f"({ {i: hex(b) for i, b in sorted(STATE.section_bases.items())} }), so no "
            f"section of this table places an address there")
    return max(under, key=lambda i: STATE.section_bases[i])


def _nearest_offset(want: int, section: int) -> dict[str, Any]:
    """The nearest symbol of `section` at or below offset `want`, by bisection over
    `_offset_index`; the first in the table wins at one offset."""
    offsets, symbols = _offset_index().get(section, ([], []))
    i = bisect.bisect_right(offsets, want) - 1
    if i < 0:
        raise ds.Invalid("unknown_ref",
            f"nothing in section {section} sits at or below offset {want:#x}. That "
            f"is an answer about the TABLE, not about the program: it means this address "
            f"is below the lowest symbol loaded in that section, or the section has none")
    best = symbols[i]
    return {"query": f"0x{want:X}", **_placed(best), "delta": want - best.offset}


OffsetIndex = dict[int, tuple[list[int], list[sym.Symbol]]]
_index: tuple[int, OffsetIndex] | None = None


def _offset_index() -> OffsetIndex:
    """Per section, the distinct offsets ascending and the first symbol at each, built once per
    table generation."""
    global _index
    if _index is None or _index[0] != STATE.table_generation:
        sections: OffsetIndex = {}
        for s in sorted(STATE.table, key=lambda s: (s.section, s.offset)):   # stable: table order
            offsets, symbols = sections.setdefault(s.section, ([], []))
            if not offsets or offsets[-1] != s.offset:
                offsets.append(s.offset)
                symbols.append(s)
        _index = (STATE.table_generation, sections)
    return _index[1]


def nearest_symbol(linear: int) -> dict[str, Any] | None:
    """What `symbols_find(linear=)` answers, without the reply; None where it would refuse."""
    try:
        section = _linear_section(linear) if STATE.section_bases else sym.FLAT
        if section not in _offset_index():
            return None
        base = STATE.section_bases[section] if STATE.section_bases else STATE.base["base"]
        return _nearest_offset(linear - base, section)
    except ds.Invalid:
        return None


_span: tuple[object, tuple[int, int]] | None = None


def symbol_span() -> tuple[int, int] | None:
    """The lowest and highest linear address the table places a symbol at, None with no table;
    past either end the nearest symbol names memory the table does not describe."""
    global _span
    if not STATE.table:
        return None
    key = (STATE.table_generation, tuple(sorted(STATE.base.items())),
           tuple(sorted(STATE.section_bases.items())))
    if _span is None or _span[0] != key:
        placed = [linear_of(s) for s in STATE.table]
        _span = (key, (min(placed), max(placed)))
    return _span[1]
