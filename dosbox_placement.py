"""The symbol PLACEMENT: a name or a raw `SEG:OFF` to the address the debugger wants.

The caller says the SAME thing for a DJGPP protected-mode program and a 16-bit real-mode
one: a symbol name, or a raw address, and NOTHING about mode or selectors.
The server does the dirty work below -- deciding which the ref is, resolving a name to an
offset, and turning that offset into the seg:off the debugger's own command wants, which
depends on the machine's mode and is exactly the number the plan exists to stop a caller
having to work out by hand.

The table itself is held in `dosbox_state` (it is cleared with the session); this module
is what reads it: which spelling a `ref` is, the offset a name resolves to, the seg:off
that offset arms at in THIS machine's mode, and the two tools that fill and query the
table, `symbols_load` and `symbols_find`.
"""

from __future__ import annotations

import bisect
import dataclasses
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from scry_core import value_format as vf

import dosbox_console as dcons
import dosbox_declarations as dec
import dosbox_paths as paths
import dosbox_session as ds
import dosbox_state as st
import dosbox_symbols as sym
from dosbox_state import STATE


def decide_by(ref: str) -> str:
    """`address` when the ref is a raw `SEG:OFF`, `symbol` otherwise. A C or ASM public is
    letters, digits and underscores and never carries a colon, so the shape decides and the
    caller never has to declare which they meant.

    THE COLON IS THE ONLY TELL, so a name that does carry one (a C++ demangled `ns::fn`)
    would be read as an address and then refused by the seg:off parser. That is a confusing
    refusal rather than a wrong action, and the escape is already there: pass `by="symbol"`
    to force a name lookup. The nm single-token column this reads never demangles, so the
    case does not arise on today's inputs; the override is the answer if it ever does."""
    if vf.parse_pointer(ref) is not None:
        return "pointer"
    return "address" if ":" in ref.strip() else "symbol"


def address_shape(ref: str, by: str | None = None) -> None:
    """A ref declared (or decided) as a raw address must parse as one, segment included, BEFORE it
    is stored: a malformed address that reaches the store is carried as `unarmable` forever, since
    the store deliberately tolerates what it already holds. A symbol is judged at its step."""
    chosen = decide_by(ref) if by is None else by
    if chosen == "address":
        parse_seg_off(ref)


#: A hex address as a caller writes one: digits, with or without `0x`, and nothing else.
_HEX_ADDR = re.compile(r"(?:0[xX])?[0-9a-fA-F]+")


def hex_arg(name: str, value: object) -> int:
    """A hex address argument, or a refusal that names the ARGUMENT.

    `int(value, 16)` alone accepts a sign and underscores, so `-400` would read as a negative
    base and `4_00` as 0x400, both in silence. AN INTEGER IS REFUSED, not coerced: the argument
    is text so that no caller has to convert hex to decimal.
    """
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
    """A raw `SEG:OFF` in hex into a pair. A bare linear number is refused: without a
    segment there is nothing to arm at, which is the whole reason symbols carry offsets."""
    r = ref.strip()
    if ":" not in r:
        raise ds.Invalid("bad_argument",
            f"a raw address is SEG:OFF in hex (e.g. 00A7:0016DD80); got {ref!r}. A bare "
            f"linear address has no segment to arm at -- use a symbol, which carries one")
    seg_s, off_s = r.split(":", 1)
    try:
        seg, off = int(seg_s, 16), int(off_s, 16)
    except ValueError:
        raise ds.Invalid("bad_argument", f"{ref!r} is not a hex SEG:OFF") from None
    # THE SEGMENT IS JUDGED HERE, where every raw ref becomes numbers, so no tool can take one it
    # cannot address: a segment past sixteen bits written by `memdump` lands nowhere the caller
    # meant, and armed by `breakpoint_at` persists a declaration nothing can ever clear. The
    # offset's ceiling depends on the cpu mode and waits for the machine.
    ds.check_segment(seg)
    return seg, off


def _listening(session: ds.Session) -> None:
    """Refuse, before anything is typed, a placement that would ask a console that is not
    listening: its nudge lands at the next stop, unread, and the declaration waits for that
    stop anyway."""
    if not session.at_debugger():
        raise ds.NotStopped("the guest is running, so nothing can be placed against its "
                            "registers now")


def target_for(offset: int, reg: str, session: ds.Session, *,
                machine: tuple[str, dict[str, str]] | None = None) -> tuple[int, int]:
    """The seg:off to arm at a symbol OFFSET, derived from the machine's mode.

    `machine` is an optional cached `(mode, registers)` read ONCE by the caller. It exists
    for the stop reply: resolving N watches and M breakpoints there would
    otherwise read `where` and `registers` N+M times, at a console round trip apiece, for a
    state that does not change across one stopped instant. Given it, this reads neither.

    Protected mode: the selector in `reg` (CS for code, DS for data) has the same base the
    symbols were placed against, so the symbol's own offset IS the breakpoint offset. Real
    mode: there are no selectors, so the address is the load paragraph plus the folded
    offset, split so the offset still fits the 16 bits a real-mode command allows.

    THE PROTECTED-MODE DATA PATH ASSUMES DS AND CS SHARE A BASE, which is true of the flat
    DPMI layout DJGPP builds (`symbols_load` documents it), and is what lets a data symbol
    placed against CS be armed through the live DS selector. A non-flat protected program
    where DS and CS have different bases would arm a data watch at DS_base+offset while the
    symbol's linear is CS_base+offset -- a wrong address this derivation does not detect.
    Break-on-change under paging is already the honest limit `watch_add` carries; a non-flat
    data layout is the same class and, if this server ever meets one, wants its own probe.
    """
    if machine is None:
        _listening(session)
    mode = machine[0] if machine is not None else session.where()["mode"]
    if mode.startswith("Pr"):
        regs = machine[1] if machine is not None else session.registers()
        return int(regs[reg], 16), offset
    if STATE.base.get("base", -1) < 0:
        raise ds.Invalid("bad_argument",
            "a real-mode symbol needs a FLAT base measured by symbols_load, and this table "
            "has none -- it is sectioned, or none is loaded. Load a real-mode map first")
    base_seg = STATE.base["base"] // 16
    ds.check_segment(base_seg)              # a base past a megabyte addresses nothing in real mode
    if offset <= 0xFFFF:
        return base_seg, offset
    linear = base_seg * 16 + offset          # a high real-mode offset (a data segment)
    if linear > 0xFFFFF:
        raise ds.Invalid("bad_argument",
            f"the symbol folds to linear 0x{linear:X}, past the 0xFFFFF a real-mode "
            f"seg:off can reach; the paragraph split would drop bit 20 and arm the wrong "
            f"address. Arm by an explicit SEG:OFF, or load this map in protected mode")
    return (linear >> 4) & 0xFFFF, linear & 0xF


def resolve_ref(decl: dec.Declaration, reg: str, session: ds.Session, *,
                 machine: tuple[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """A declaration -> what the debugger needs to arm it, or the state that is not armable.

    Returns `state`, and when `armable` also `seg`, `off` and whether the symbol carries
    the linker's mark. The four states are DISTINCT on purpose, because a caller listing
    declarations has to tell them apart:

    * `armable` -- resolved to one address that can be worked out right now.
    * `unresolved` -- no such symbol in THIS build; kept, it may be back next build (dec 8).
    * `ambiguous` -- the name matches several symbols, so arming one would be a guess at the
      wrong address. Carries `matches` and a `why`. This is a REFUSAL to arm, not a state
      that resolves itself, and `breakpoint_at` turns it into an `Invalid` before storing.
    * `unarmable` -- resolved to a symbol, but its address cannot be derived at this instant:
      the machine is not stopped, or a real-mode table has no flat base, or it folds past
      the 1 MB a real-mode seg:off can reach. Carries a `why`. The intent is kept; it arms
      when the obstacle lifts.

    It does NOT raise for these: raising `Invalid` for ambiguity AND for every
    `target_for` obstacle would make a listing count a running machine and a missing base
    as `ambiguous` -- a state word that lies about what happened.
    """
    if decl.by == "pointer":
        return _resolve_pointer(decl, reg, session, machine)
    if decl.by == "address":
        # A STORED ADDRESS THE PARSER REFUSES IS A STATE, NOT A WEDGE: the file is the one
        # input the tools never validated (a hand edit, an older format), and raising here
        # made `breakpoint_list` and every `breakpoint_clear` die on that one row, so nothing
        # could list or remove it. `unarmable` with the parser's words lets both work.
        try:
            seg, off = parse_seg_off(decl.ref)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": f"stored address {decl.ref!r} cannot be "
                                                  f"read: {e}. Clear it by this ref"}
        return {"state": "armable", "seg": seg, "off": off, "marked": False}
    # ONE SOURCE OF NAMES (owner's QA call): the name->offset half goes through the store's
    # `resolve_name`, the same routine `symbols_load`'s re-resolution uses, so a symbol
    # resolves one way everywhere. This layer adds only the live seg:off (`target_for`),
    # which the store cannot know because it never touches the machine.
    r = dec.DeclarationStore.resolve_name(decl, STATE.table, STATE.name_index)
    if r.state == "unresolved":
        return {"state": "unresolved"}
    if r.matches > 1:
        return {"state": "ambiguous", "matches": r.matches,
                "why": f"{decl.ref!r} names {r.matches} symbols in this build, so arming "
                       f"one would be a guess at the wrong address. Disambiguate, or arm "
                       f"by address"}
    try:
        seg, off = target_for(cast(int, r.offset), reg, session, machine=machine)
    except ds.Invalid as e:
        return {"state": "unarmable", "why": str(e)}
    return {"state": "armable", "seg": seg, "off": off, "marked": r.idle}


def to_invalid(fn: Callable[[], Any]) -> Any:
    """Run a store call, translating its `DeclarationError` into an `Invalid` the way
    symbols_load already wraps `BadSymbolText` -- the server's `tool()` catches only
    `Invalid`, so a store refusal must become one or it escapes as a traceback."""
    try:
        return fn()
    except dec.DeclarationError as e:
        raise ds.Invalid("bad_argument", str(e)) from None


def _resolve_pointer(decl: dec.Declaration, reg: str, session: ds.Session,
                     machine: tuple[str, dict[str, str]] | None) -> dict[str, Any]:
    """A pointer ref against the machine NOW: the base placed like any data symbol (or read
    as a `SEG:OFF`), the pointer read there as a NEAR pointer in the base's own segment (its
    width from the base's `ptr16`/`ptr32` type, else the cpu mode's: four bytes in
    protected mode, two in real), plus the offset (a field's from the type). `armable` with
    the place and a `pointer` block, `null_pointer` when it holds zero (a state, never a
    watch at zero), `unresolved` with `why` for a base that is no global, `unarmable` for
    a machine that cannot be asked."""
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
                f"{pr.base!r} is not a symbol of this build and not a SEG:OFF, so there is no "
                f"pointer to start from: a stack local has no stable address, and a pointer "
                f"ref needs a GLOBAL (a symbol of the table, or an address) as its base")}
        if base.matches > 1:
            return {"state": "ambiguous", "matches": base.matches,
                    "why": f"{pr.base!r} names {base.matches} symbols in this build"}
        try:
            seg, off = target_for(cast(int, base.offset), reg, session, machine=machine)
        except ds.Invalid as e:
            return {"state": "unarmable", "why": str(e)}
    spec = STATE.symbol_types.get(pr.base.strip().upper())
    fmt = vf.parse(spec) if spec else None
    width = fmt.size if fmt is not None and fmt.kind == "pointer" else None
    offset, field_fmt = pr.offset, None
    if pr.field is not None:
        if (fmt is None or fmt.kind != "pointer" or fmt.target is None
                or fmt.target.kind != "struct"):
            return {"state": "unresolved", "why": (
                f"`{pr.base}->{pr.field}` needs {pr.base} typed as a pointer to a struct "
                f"(`ptr32{{...}}` or `ptr16{{...}}` in the `types` file); it is "
                f"{spec or 'untyped'}. Or name the offset: `[{pr.base}]+0x..`")}
        try:
            offset, field_fmt = vf.field_offset(fmt.target, pr.field)
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
    if not 0 <= target <= dcons.offset_ceiling(mode):
        return {"state": "unarmable", "pointer": info, "why": (
            f"the pointer plus the offset, {target:#x}, is outside what an offset can be "
            f"in {mode} mode")}
    info["target"] = st.seg_off(seg, target)
    return {"state": "armable", "seg": seg, "off": target, "marked": False, "pointer": info,
            "field_fmt": field_fmt}


def read_target(ref: str, reg: str, session: ds.Session, *,
                 machine: tuple[str, dict[str, str]] | None = None) -> tuple[int, int]:
    """The seg:off a reader (`read_memory`, `memdump`) should read at, from a `ref`: a symbol
    name or a raw `SEG:OFF`. ONE spelling: a numeric segment/offset pair is
    not a second way to say the same address.

    A read needs a concrete address NOW, so unlike a breakpoint it cannot keep an unresolved
    or ambiguous intent: an absent or doubly-defined name is REFUSED here, not stored.
    Resolution goes through the SAME `resolve_ref` the breakpoint and watch tools use, so a
    symbol resolves one way across the whole surface.
    """
    if decide_by(ref) == "address":
        return parse_seg_off(ref)
    # THE DECLARATION'S OWN REFUSALS (an empty ref) are translated like everywhere else: the
    # constructor raises `DeclarationError`, which the tool wrapper does not catch, so an
    # untranslated one escaped `read_memory(ref="")` as a traceback with no session block.
    decl = to_invalid(lambda: dec.Declaration("breakpoint", "symbol", ref))
    res = resolve_ref(decl, reg, session, machine=machine)
    if res["state"] == "armable":
        return res["seg"], res["off"]
    if res["state"] == "unresolved":
        raise ds.Invalid("unknown_ref", f"{ref!r} is not a symbol in this build, so there is no "
                         f"address to read")
    if not session.at_debugger():
        raise ds.NotStopped(f"the guest is running, so {ref!r} cannot be placed against "
                            f"its selector now, and a read needs the machine stopped anyway")
    raise ds.Invalid("unknown_ref",
        str(res.get("why", f"{ref!r} cannot be resolved to an address")))


def _placed(s: sym.Symbol) -> dict[str, Any]:
    """One symbol: its name, what KIND the toolchain called it, both addresses, and
    whether that address is CONDITIONAL.

    Both addresses, because the caller needs whichever it needs.

    The offset is what the toolchain printed and the linear is what the debugger shows,
    and quoting only one of them makes the reader do the arithmetic that this tool
    exists to have got right once.
    """
    # `STATE.base["base"]`, never `.get(..., 0)`: base 0 is the exact value `selector`
    # refuses by name ("would place every symbol at its raw offset"), so defaulting to
    # it would dress a server bug as an answer. The read three lines away already
    # subscripts. A bug escapes as a bug.
    # `idle` IS THE ONE FIELD HERE THAT IS NOT AN ADDRESS: it is Borland's mark on that
    # row, passed through. What it MEANS is unknown -- the explanation once written here
    # was measured false, and the evidence is on `Symbol.idle`. Reported per symbol as
    # well as counted in `symbols_load`'s `overlay_idle`, because a total cannot tell
    # you whether THIS name carries it. False for every `nm` and GNU-map symbol:
    # neither format prints such a column.
    # THE SAME PLACEMENT THE ENCODER USED, asked of the same function. Adding
    # `STATE.base["base"]` here regardless would answer with the `-1` sentinel for every
    # symbol of a sectioned load -- a number, plausible, and wrong.
    return {"name": s.name, "kind": s.kind, "offset": s.offset, "section": s.section,
            "addr": st.flat(linear_of(s)), "idle": s.idle}


def linear_of(s: sym.Symbol) -> int:
    """A symbol's linear address against the table loaded now: the one placement `symbols_find`
    answers and a comment by name lands on."""
    bases = STATE.section_bases if STATE.section_bases else {sym.FLAT: STATE.base["base"]}
    return sym.place(s, bases)


def read_types(value: str) -> dict[str, str]:
    """A `types` file for `symbols_load`, named by an absolute path: the grammar's reader over
    the file's UTF-8 text, with a refusal that names the file and the line."""
    text = paths.read_text("types", value, "types file")
    try:
        return vf.read_types(text, value)
    except vf.FormatError as e:
        raise ds.Invalid("bad_argument", str(e)) from None


def load(session: ds.Session, source: str, src: Path, base: int | None, base_from: str,
         pattern: str | None, keep_noise: bool, section_bases: dict[str, int] | None,
         rearm_declarations: Callable[[ds.Session], dict[str, Any]],
         take_the_map: Callable[[ds.Session], str | None],
         types: dict[str, str] | None = None) -> dict[str, Any]:
    """The body of the `symbols_load` tool: parse `src` (the caller's `source`, judged a file
    there), place it, install the table here and in the
    debugger (or queue the debugger's half while the guest runs), then `rearm` the stored
    declarations against the new table and stamp this session's raw comments the new batch
    describes (`take_the_map`, the store's write error or None). Both are handed in because
    the layers above import this one, not the other way round."""
    # THE MAP IS READ LENIENTLY: a DOS toolchain's map may carry code page 437 bytes in a path
    # or a comment, and the parser counts the lines it cannot read (a `types` file is strict).
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # `tool()` translates only `Invalid`, so a file the host will not read (its mode, a
        # race) would come back as a bare `OSError` with no session block.
        raise ds.Invalid("bad_argument",
            f"cannot read {src}: {exc!r}. That is the symbol list this "
                         f"was asked to load, so there is nothing to load") from None
    try:
        # `parse` rather than the two halves by hand: it sniffs the format AND counts
        # the lines it could not read, and that count has to travel with the symbols to
        # be worth anything. Choosing the parser here and calling the counting one
        # separately would be two walks that can disagree.
        syms, unreadable = sym.parse(text)
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", f"{source}: {e}") from None
    # `plan` IS OUTSIDE THAT BLOCK, and the prefix is why. `BadSymbolText`'s own
    # docstring says the MCP layer translates it into "a refusal that NAMES THE
    # CALLER'S FILE", which is right for text that could not be parsed and WRONG for a
    # `pattern` that will not compile: that refusal came back as
    # `INVALID: /path/to/prog.sym: that is not a usable pattern: ...`, blaming a file
    # that is perfectly fine for an argument typed at the tool. The un-prefixed form is
    # the one `encode`'s refusal ten lines below already uses, for the same reason.
    try:
        plan = sym.plan(syms, pattern=pattern, keep_noise=keep_noise,
                        unreadable=unreadable)
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", str(e)) from None
    # AN EXPLICIT BASE COMES WITH NO LIMIT, and `-1` says so rather than inventing one.
    # The limit is the independent fact that lets a caller check the base is really this
    # program's -- it bracketed the binary's own top `nm` address, which is how the
    # measured base was identified at all -- so a fabricated limit would hand the
    # caller's own assumption back to them as evidence for itself.
    # A SECTIONED MAP IS PLACED FROM A TABLE, AND NOTHING IS PROBED FOR IT. There is
    # no descriptor to read: the bases come from the caller because they are not in the
    # file and this server does not parse the binary that has them. So `base_from` is
    # not consulted, and the reply says `caller` for the same reason it does with an
    # explicit `base`.
    #
    # THE KEYS ARRIVE AS STRINGS because JSON has no integer keys, and they are
    # converted HERE rather than being accepted as they come: a section index is a
    # number in every one of these formats, and a table keyed on `"1"` would match no
    # symbol while looking exactly like one that does.
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
        # REAL MODE HAS NO DESCRIPTOR TO MEASURE, and the pane already says so: asked there,
        # this build's `SELINFO` prints no descriptor line at all inside a program, so the
        # refusal would be the parser's and name the wrong cause.
        if base is None and session.where()["mode"] == dcons.REAL_MODE:
            raise ds.Invalid("bad_argument",
                "the machine is in real mode, where there is no descriptor to measure a base "
                "from: pass `base` as hex text, the load segment * 16 (segment 0x0800 is "
                "\"8000\"). Placed at base 0, every symbol would sit at its raw offset")
        desc = (session.selector(base_from) if base is None
                else {"base": base, "limit": -1, "type": -1})
    try:
        data = (sym.encode(plan, section_bases=bases) if bases is not None
                else sym.encode(plan, desc["base"]))
    except sym.BadSymbolText as e:
        raise ds.Invalid("bad_argument", str(e)) from None
    # THE TABLE IS INSTALLED ONLY AFTER THE DEBUGGER HAS TAKEN THE FILE, and the order
    # is the whole of it. `load_symbols` refuses on SEVEN paths at the time of writing
    # -- a pre-existing file, a console not listening, an unwritable directory, `LV`
    # unacknowledged, `SV` unacknowledged, the saved file missing, the saved file
    # undecodable -- and that is what has been seen rather than a closed list, which is
    # the point: a count of them goes stale, and a count is not what the ordering rests on.
    # Installing first meant a REFUSED load still replaced a table that was working:
    # the caller got INVALID from here and `ok` from `symbols_find`, answering out of a
    # table the debugger does not hold. A refusal that also corrupts state inverts this
    # module's one rule, that a refusal is visible and a wrong answer is not.
    # THE TABLE ACCUMULATES, the way the debugger's own `LV` does. Loading in narrow
    # batches is the reasonable thing to do with thousands of symbols, and while this table
    # was REPLACED by every load, the second batch dropped the first one's symbols out of
    # `symbols_find` and orphaned any breakpoint armed on them: the debugger kept its row,
    # this side no longer knew the name, and nothing could clear it.
    #
    # IT ACCUMULATES ONLY WHILE THE PLACEMENT HOLDS. The table stores OFFSETS and the base
    # places them, so carrying earlier symbols across a load that moved the base would
    # silently re-place them at addresses nobody measured. A load that changes the base or
    # the section bases REPLACES, and the reply says which of the two happened.
    same_place = (bool(STATE.table) and dict(STATE.base) == dict(desc)
                  and dict(STATE.section_bases) == dict(bases or {}))
    # THE TYPES ARE JUDGED BEFORE ANYTHING IS WRITTEN, and that ordering is the whole of it.
    # A name typed that the table will not carry is a refusal, because a type nothing
    # carries would be honoured by nothing. Judged AFTER the debugger has taken the file
    # and the table is installed, one typo in a `types` name would refuse the call with
    # the debugger's list already grown and this side's table already changed: a refusal
    # that also corrupts state, which is the one thing the ordering above exists to
    # prevent. The names judged against are the ones
    # the table WILL hold, which for an accumulating load includes an earlier batch's.
    known = {s.name.upper() for s in plan.symbols}
    if same_place:
        known |= {s.name.upper() for s in STATE.table}
    unknown = sorted(n for n in (types or {}) if n not in known)
    if unknown:
        raise ds.Invalid("bad_argument",
                         f"types are named for symbols the table lacks: {unknown[:5]}")
    STATE.pending["load"] = None            # a newer load supersedes one still queued
    if session.at_debugger():
        held = session.load_symbols(data)
        pending = False
    else:
        # THE GUEST RUNS: the table is held here at once (so `symbols_find` and the name
        # layer answer), and the debugger's list is loaded at the next stop, with the
        # re-arm that follows a load. Reached only with an explicit base: measuring one
        # needs the console and refuses above. Decided by the passive check, because the
        # session's own refusal for a running load is a plain `Invalid`.
        STATE.pending["load"] = data
        STATE.pending["dirty"] = True
        held, pending = [], True
    STATE.install_table(plan.symbols, accumulate=same_place)
    table_mode = "accumulated" if same_place else "replaced"
    # THE TYPES ACCUMULATE WITH THE TABLE, or a type declared on the first batch would be
    # lost while its symbol stayed: the same silent degradation, one layer up.
    if not same_place:
        STATE.symbol_types.clear()
    STATE.symbol_types.update(types or {})
    STATE.base.clear()
    STATE.base.update(desc)
    # THE TABLE IS KEPT TOO, so `symbols_find` reports the same linear address the
    # debugger holds. Without it that tool would fall back to `STATE.base["base"]`, which for
    # a sectioned load is the `-1` sentinel above -- a number, plausible, and wrong for
    # every symbol.
    STATE.section_bases.clear()
    if bases is not None:
        STATE.section_bases.update(bases)
    # RE-RESOLVE every stored declaration against the NEW table and re-arm the
    # code ones that resolve. This is what makes a rebuild free -- relaunch, symbols_load
    # the new map, and the breakpoints follow the program to their new addresses without
    # being sent again. It runs here because this is the moment the map changed.
    # THE BATCH IS HELD BEFORE THE RE-ARM judges which raw addresses are stale against it.
    take_the_batch(plan.symbols, accumulate=same_place)
    rearm = ({"deferred": True, "note": "re-armed at the next stop, after the load"}
             if pending else rearm_declarations(session))
    if (unwritten := take_the_map(session)) is not None:
        raise ds.Invalid("host_failed",
            f"the symbols are loaded and the declarations re-armed, but {unwritten}: the "
            "comments this session placed before any map are held in memory as this map's, "
            "and the next write that succeeds puts them on disk", held_in_memory=True)
    return st.reply(base=desc["base"], limit=desc["limit"], descriptor=desc["type"],
                  declarations=rearm, pending=pending,
                  base_from=("caller" if base is not None else base_from.upper()),
                  parsed=plan.parsed, kept=plan.kept,
                  excluded_sections=plan.excluded_noise,
                  excluded_pattern=plan.excluded_pattern,
                  excluded_unplaceable=plan.excluded_unplaceable,
                  unencodable=plan.unencodable[:8],
                  unencodable_total=len(plan.unencodable),
                  truncated_names=plan.truncated_names,
                  disambiguated=plan.disambiguated,
                  # `renamed` is the one a caller actually wants and `truncated_names`
                  # is not it: that one counts names LONGER than the field, while a
                  # name that fitted is mutilated too when it has to carry a `~n`.
                  # `unreadable` is how many lines of the file matched no format at
                  # all -- the population was cut before any of these buckets saw it.
                  renamed=plan.renamed, unreadable=plan.unreadable,
                  # `overlay_idle` is a SUBSET of `kept`, not a bucket beside it, which
                  # is why it does not disturb the sum the four fields above make with
                  # `parsed`. It is here because it is the one number that says how much
                  # of the table you just loaded names a CONDITIONAL address.
                  overlay_idle=plan.overlay_idle,
                  # WHAT HAPPENED TO THE TABLE, said out loud rather than left to be
                  # discovered by a `symbols_find` that comes back empty.
                  table_mode=table_mode, table_total=len(STATE.table),
                  loaded=len(held), bytes=len(data), symbols_typed=len(types or {}))


def take_the_batch(symbols: list[sym.Symbol], accumulate: bool) -> None:
    """Hold the batch a load of `symbols` placed, over this session's conf: beside the batches
    before it (`accumulate`), as the debugger's list keeps them, or alone after a replace."""
    conf = STATE.conf_fingerprint
    if conf is None:
        return
    batch = dec.Build.of(conf, [(s.name, linear_of(s)) for s in symbols])
    STATE.map_batches = [*STATE.map_batches, batch] if accumulate else [batch]


def stamp_at(linear: int | None, raw: bool) -> str | None:
    """The stamp a row placed at `linear` takes now: the most recently loaded batch whose span
    holds it, kept in the store for the rows that will name it, or the conf alone where no
    batch describes it. A raw code row (`raw`) whose place is not known now while a batch is
    held is `dec.PENDING_STAMP`, and takes its batch when a load of its session places it."""
    cover, stamp = _stamp_now(linear, raw)
    if cover is not None and STATE.store is not None:
        STATE.store.keep_build(cover)
    return stamp


def _stamp_now(linear: int | None, raw: bool) -> tuple[dec.Build | None, str | None]:
    """`stamp_at`'s answer and the batch it names, written nowhere."""
    cover = next((b for b in reversed(STATE.map_batches)
                  if linear is not None and b.covers(linear)), None)
    if cover is not None:
        return cover, cover.stamp
    if raw and linear is None and STATE.map_batches:
        return None, dec.PENDING_STAMP
    return None, STATE.conf_fingerprint


def staleness(decl: dec.Declaration, place_now: Callable[[], int | None]) -> str | None:
    """Why a raw row is not known to be this build's, judged by the batch that describes it
    (`dec.raw_staleness`), or None. `place_now` gives its linear address at this instant.
    A pending row of this session is judged by the stamp it takes where it is placed now,
    since within one session a held batch is the running program; only a load writes that
    stamp, so a session that loads no map after it leaves the row pending."""
    if decl.fingerprint == dec.PENDING_STAMP and decl.origin == STATE.session_origin \
            and STATE.session_origin is not None:
        linear = place_now()
        _, stamp = _stamp_now(linear, raw=True)
        decl, place_now = dataclasses.replace(decl, fingerprint=stamp), lambda: linear
    return dec.raw_staleness(decl, STATE.conf_fingerprint, STATE.map_batches, place_now)


def is_stale(decl: dec.Declaration, place_now: Callable[[], int | None]) -> bool:
    return staleness(decl, place_now) is not None


def mode_word(cpu: str | None) -> str | None:
    """A stop's cpu mode as a raw row records it (`dec.CPU_MODES`), from the debugger's
    spelling (`Real`, `Pr16`, `Pr32`); None for a mode not known."""
    if cpu == dcons.REAL_MODE:
        return "real"
    return "protected" if cpu is not None and cpu.startswith("Pr") else None


def waits(decl: dec.Declaration, cpu: Callable[[], str | None]) -> str | None:
    """The mode a raw row waits for at this stop (`cpu` gives its spelling, asked only for a row
    that recorded one): the mode it was placed in, when this stop's is the other or is not
    known; None when the row is judged here. A SEG:OFF read in the other mode is another byte,
    so such a row is neither judged nor armed: it is `unarmable`, named by `waits_why`."""
    if decl.cpu_mode is None or not dec.is_raw_code(decl.kind, decl.by):
        return None
    return None if mode_word(cpu()) == decl.cpu_mode else decl.cpu_mode


def waits_why(mode: str, again: str) -> str:
    """Why a row placed in `mode` waits at a stop of the other mode; `again` is the gesture that
    places it in this one."""
    return (f"placed at a {mode}-mode stop, and its SEG:OFF names another byte in the other "
            f"mode: judged and armed only at a {mode}-mode stop. {again} at this stop to place "
            "it in this mode")


# THE CEILING ON A NAME LOOKUP: a `limit` with no top hands a whole table back under the
# name of a lookup.
SYMBOLS_LIMIT_MAX = 50


def check_find_args(name: str | None, offset: int | None, linear: str | None,
                    limit: int) -> None:
    """The refusals `symbols_find` makes on its ARGUMENTS alone, before the table is looked
    at: one question per call, a `linear` that is hex text, and on the name question a
    `limit` inside the ceiling and a name that is not empty. One function, so the preflight of
    a list refuses the same step `find` would, before an earlier step has pressed a key."""
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
        # A step of a list delivers its values untyped: a string here is a refusal, not a
        # TypeError out of the comparison below that the tool wrapper does not translate.
        raise ds.Invalid("bad_argument", f"limit is a number of symbols; got {limit!r}")
    # THE REFUSAL IS ON THE BRANCH THAT READS IT. Above the split it would fire for
    # `offset` and `linear` too, branches that answer with one symbol and never slice:
    # there `limit=1` and `limit=10` return byte-identical replies, so refusing
    # `limit=0` would correct a caller about an argument the code they reached never
    # looked at.
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
    # `linear` is what the DEBUGGER shows and this table holds OFFSETS, so the base
    # comes back off here. It is the base the table was PLACED against, which is why
    # `_forget_symbols` runs on every session change: against a stale base this
    # subtraction is silently wrong rather than absent, and a wrong answer of the right
    # shape is the one thing worse than a refusal.
    # WHICH SECTION THE QUESTION IS ABOUT, because offsets in different sections are
    # different addresses and this table can hold both: an offset compared across sections
    # answers with whichever
    # symbol of ANY section sat highest below it -- a symbol from another selector, with
    # a plausible delta and no error.
    if not STATE.section_bases:
        # A FLAT TABLE HAS EXACTLY ONE SECTION, so naming it would be ceremony -- and
        # naming a DIFFERENT one is a question about a section this table does not have.
        if section is not None and section != sym.FLAT:
            raise ds.Invalid("bad_argument",
                f"this table was loaded FLAT, so it has no section {section}. Ask "
                f"without `section`, or reload with `section_bases` if the map is "
                f"sectioned")
        want_section = sym.FLAT
    elif section is not None:
        want_section = section
    elif linear is not None:
        # A LINEAR ADDRESS ANSWERS THE QUESTION ITSELF: it falls inside exactly one
        # section's base, and picking the greatest base at or below it is the same
        # arithmetic the encoder did in the other direction. This is the branch a caller
        # who has stopped somewhere actually uses, so making them work out the section
        # first would be handing back the sum they came here to have computed.
        want_section = _linear_section(linear)
    else:
        raise ds.Invalid("bad_argument",
            f"this table is SECTIONED and an offset alone does not name an address: "
            f"its sections overlap, so 0x{offset:X} exists in each of "
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
    """The section of a SECTIONED table a linear address falls in: the greatest base at or
    below it."""
    under = [i for i, b in STATE.section_bases.items() if b <= linear]
    if not under:
        raise ds.Invalid("unknown_ref",
            f"0x{linear:X} is below every section this table was placed at "
            f"({ {i: hex(b) for i, b in sorted(STATE.section_bases.items())} }), so it "
            f"is not an address in this program")
    return max(under, key=lambda i: STATE.section_bases[i])


def _nearest_offset(want: int, section: int) -> dict[str, Any]:
    """The nearest symbol of `section` at or below offset `want`, as `symbols_find` answers it:
    by bisection over the table sorted once (`_offset_index`). Among symbols at one offset the
    first in the table wins."""
    offsets, symbols = _offset_index().get(section, ([], []))
    i = bisect.bisect_right(offsets, want) - 1
    if i < 0:
        raise ds.Invalid("unknown_ref",
            f"nothing in section {section} sits at or below offset {want:#x}. That "
            f"is an answer about the TABLE, not about the program: it means this address "
            f"is below the lowest symbol loaded in that section")
    best = symbols[i]
    return {"query": f"0x{want:X}", **_placed(best), "delta": want - best.offset}


OffsetIndex = dict[int, tuple[list[int], list[sym.Symbol]]]
_index: tuple[int, OffsetIndex] | None = None


def _offset_index() -> OffsetIndex:
    """Per section, the table's distinct offsets ascending and the first symbol at each, built
    once per table (`STATE.table_generation`) rather than walked per address."""
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
    """What `symbols_find(linear=)` answers for `linear`, without the reply around it: the
    nearest symbol at or below, its fields and `delta`; None where it would refuse (below
    every section, or below the lowest symbol of its own section)."""
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
    """The lowest and highest linear address the loaded table places a symbol at, None with
    no table: past either end the nearest symbol names memory the table does not describe.
    Computed once per table and placement, since every stop reply asks."""
    global _span
    if not STATE.table:
        return None
    key = (STATE.table_generation, tuple(sorted(STATE.base.items())),
           tuple(sorted(STATE.section_bases.items())))
    if _span is None or _span[0] != key:
        placed = [linear_of(s) for s in STATE.table]
        _span = (key, (min(placed), max(placed)))
    return _span[1]
