"""The argument checks a step passes BEFORE any step runs: one registry, by operation name,
pointing at the SAME functions each tool runs first when it is called on its own. The check is
per tool, so a tool no batch dispatches (`find`, `scan_start`, `debug`) has its entry too.

A batch (`perform`, `start(plan=)`, `drive`'s act) is a list of the server's own operations,
and a value that one of them would refuse mid-list (a key name no route knows, a pattern that
does not compile, a step count past the ceiling) must be refused before the first step has
posted a key or released the machine: a half-run sequence leaves the guest in a state the
caller has to undo by hand. So what enters the queue goes through the checks the synchronous
call makes, and the reply lists EVERY refused step, so a caller fixes the batch once.

WHAT CANNOT BE CHECKED HERE, and the docstring of `perform` says so: a symbol name is judged
against the table loaded at the time its step runs (a `symbols_load` may be an earlier step of
the same list), a file's existence at the step (an earlier step may write it), and whatever
needs the machine (its mode, a selector, a live address). Those refuse at their step, with
`failed_at` and `ran` as the honest account.

The functions here take the step's arguments BY NAME and ignore what they do not judge, so a
registry entry is called with the step's own dict; `serial` says which input route the
session has, the one fact of the session a value check depends on.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

from scry_core import value_format as vf

import dosbox_code as code
import dosbox_comment_file as cf
import dosbox_declarations as dec
import dosbox_find as finder
import dosbox_inputs as inputs
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_running as running
import dosbox_screen as screen
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_trace as tracing

Check = Callable[..., None]


def address_shape(ref: object, by: str = "auto") -> None:
    """`placement.address_shape` for a step, whose ref may not even be a string: one that is not
    is refused here, not deferred to a step that would die on `.strip()` after earlier steps ran."""
    if not isinstance(ref, str):
        raise ds.Invalid("bad_argument", f"ref={ref!r} is not a string: a symbol or a SEG:OFF")
    placement.address_shape(ref, None if by == "auto" else by)


#: How a ref is taken, per family: a breakpoint is never declared through a pointer (code does
#: not move behind one), a watch may be.
BREAKPOINT_BY = ("auto", "symbol", "address")
WATCH_BY = (*BREAKPOINT_BY, "pointer")


def by_choice(by: object, family: tuple[str, ...]) -> None:
    if by not in family:
        raise ds.Invalid("bad_argument",
            f"`by` is {', '.join(family[:-1])} or {family[-1]}; got {by!r}")


def declared(kind: str, ref: object, by: str) -> str:
    """The ref as the store will take it, judged by the store's own rules on a declaration
    built and dropped: an address that parses, a pointer only for a watch and only in a pointer's
    shape. A `by` of `auto` is decided from the ref first, so `[g_p]` is a pointer here as it is
    at the call. The `by` it was taken as is handed back."""
    address_shape(ref, by)
    assert isinstance(ref, str)
    chosen = placement.decide_by(ref) if by == "auto" else by
    if kind == "watch":
        placement.to_invalid(lambda: dec.Declaration(kind, chosen, ref, width=1, fmt="u8",
                                                     watch_mode="show"))
    else:
        placement.to_invalid(lambda: dec.Declaration(kind, chosen, ref))
    return chosen


def comment_ref(ref: object) -> None:
    """A comment's ref, held to the comment file's rule for one, so a call and a file refuse
    the same refs: a symbol, or a hex `SEG:OFF` with its segment in sixteen bits (no pointer,
    no `+`, no `0x`, nothing that is not one visible word). The placement parser makes the
    numbers when the ref is placed, and every address this rule takes is one it parses."""
    if not isinstance(ref, str):
        raise ds.Invalid("bad_argument", f"ref={ref!r} is not a string: a symbol or a SEG:OFF")
    fault = cf.ref_fault(ref)
    if fault is not None:
        raise ds.Invalid("bad_argument", f"a comment's ref {fault}")


def comment_text(text: object) -> None:
    """A comment's text, by the comment file's rule: one visible line, at most the bytes a
    file of the format holds."""
    if not isinstance(text, str):
        raise ds.Invalid("bad_argument", f"text={text!r} is not text")
    fault = cf.text_fault(text)
    if fault is not None:
        raise ds.Invalid("bad_argument", f"a comment's text {fault}")


def _comment_add(ref: object, text: object, **_: Any) -> None:
    comment_ref(ref)
    comment_text(text)


def _comment_delete(ref: object, **_: Any) -> None:
    comment_ref(ref)


def _comment_save(dest: object, **_: Any) -> None:
    paths.absolute("dest", dest)


def _comment_load(source: object, **_: Any) -> None:
    paths.absolute("source", source)


# THE DATA VIEW'S REACH bounds three values a caller passes, and each bound lives here: a bound
# kept in a tool body is one the whole-list check of a sequence cannot see, so a list would run
# the steps before it and refuse mid-way.

def write_data(value: str) -> bytes:
    """A caller's hex bytes, judged and PARSED by the server's one hex parser, handed back so the
    tool that writes them never parses the text a second time. Up to the data view's reach,
    which is what the readback can cover in one read."""
    data = finder.hex_bytes("data_hex", value, verb="write")
    if len(data) > ds.DATA_VIEW_BYTES:
        raise ds.Invalid("bad_argument",
            f"a write carries up to {ds.DATA_VIEW_BYTES} bytes, the data view's reach for the "
            f"readback; {len(data)} is a region")
    return data


def read_length(length: int) -> None:
    """`read_memory`'s span: 1 to the data view's reach. Its type is judged before this, by the
    tool's schema or by a sequence's signature check."""
    if not 1 <= length <= ds.DATA_VIEW_BYTES:
        raise ds.Invalid("bad_argument",
            f"length={length!r} is not 1 to {ds.DATA_VIEW_BYTES}; above that the answer is "
            "`memdump`, which writes exactly the bytes asked for")


def show_watch_width(mode: str, width: int) -> None:
    """A show watch reads its bytes off the data view at every stop, so it is at most
    the view's reach; wider, it would be stored only to report 'unreadable' at each stop."""
    if mode == "show" and width > ds.DATA_VIEW_BYTES:
        raise ds.Invalid("bad_argument",
            f"a show watch reads up to {ds.DATA_VIEW_BYTES} bytes at a stop (the data "
            f"view's reach); {width} is a region, and it would be stored only to report "
            f"'unreadable' at every stop. Use memdump for a region, or a smaller length")


def _send_keys(keys: list[str], modifiers: list[str] | None = None, expect: str | None = None,
               seconds: float | None = None, focus: str = "return", *, serial: bool = False,
               **_: Any) -> None:
    inputs.check_keys(keys, modifiers, expect, seconds, focus, serial=serial)


def _send_mouse(button: str | None = None, x: int | None = None, y: int | None = None,
                dx: int | None = None, dy: int | None = None, place: str | None = None,
                expect: str | None = None, seconds: float | None = None, focus: str = "keep",
                **_: Any) -> None:
    inputs.check_mouse(button, x, y, dx, dy, place, expect, seconds, focus)


def _log(pattern: str, channel: str, limit: int = 40, **_: Any) -> None:
    ds.compiled(pattern)
    ds.check_e9_limit(limit)
    ds.check_channel(channel)


def _log_wait(pattern: str, channel: str, seconds: float = 30.0, **_: Any) -> None:
    ds.check_wait_bound(seconds)
    ds.compiled(pattern)
    ds.check_channel(channel)


def _display(e9: str = "none", e9_filter: str = ".", e9_stamp: str | None = None,
             **_: Any) -> None:
    running.e9_validate(e9, e9_filter, e9_stamp)


def _step(count: int = 1, mode: str = "into", **rest: Any) -> None:
    ds.check_step(mode, count)
    _display(**rest)


def _run_to(ref: str, control: str = "", seconds: float = 30.0, **rest: Any) -> None:
    ds.check_wait_bound(seconds)
    address_shape(ref)
    # THE CONTROL IS REQUIRED (the schema says so), and an empty one is no control: a list is
    # checked WHOLE before its first step runs, so a step without one is refused here.
    if not control:
        raise ds.Invalid("bad_argument",
            "no control is named: `run_to` measures nothing without one. A `control` is a "
            "second ref known to be hot on this screen (the vblank or timer handler, a loop "
            "the program is in): with it, a bound that expires proves the target did not "
            "run, and without it the silence could be the breakpoint never firing at all")
    address_shape(control)
    _display(**rest)


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ds.Invalid("bad_argument", f"{name}={value!r} is not a whole number of zero or more")
    return value


#: The largest integer a double holds exactly: the pane's clock is compared as one.
RUN_FOR_MS_MAX = 2 ** 53


def optional_path(name: str, value: object) -> None:
    """A path argument whose empty string means none: when given, it is absolute."""
    if value != "":
        paths.absolute(name, value)


def _trace(instructions: int, shape: str = "normal", dest: str = "", seconds: float = 60.0,
           **_: Any) -> None:
    tracing.check_arguments(instructions, shape)
    optional_path("dest", dest)
    ds.check_wait_bound(seconds)


def _run_for(milliseconds: int = 0, frames: int = 0, seconds: float = 30.0,
             **rest: Any) -> None:
    ms, n = _count("milliseconds", milliseconds), _count("frames", frames)
    if ms > RUN_FOR_MS_MAX:
        raise ds.Invalid("bad_argument",
            f"milliseconds={ms} is past what the pane's floating-point clock counts exactly")
    if (ms > 0) == (n > 0):
        raise ds.Invalid("bad_argument",
            f"exactly one of milliseconds and frames is above zero; got milliseconds={ms}, "
            f"frames={n}")
    ds.check_wait_bound(seconds)
    _display(**rest)


def _breakpoint_at(ref: str, by: str = "auto", **_: Any) -> None:
    by_choice(by, BREAKPOINT_BY)
    declared("breakpoint", ref, by)


def _breakpoint_interrupt(number: int, ah: int | None = None, **_: Any) -> None:
    ds.check_interrupt(number, ah)


def _interrupt_vectors(number: int | None = None, **_: Any) -> None:
    if number is not None:
        ds.check_interrupt(number, None)


def _watch_add(ref: str, mode: str, length: int = 0, fmt: str = "auto", by: str = "auto",
               **_: Any) -> None:
    placement.to_invalid(lambda: dec.check_watch_mode(mode))
    by_choice(by, WATCH_BY)
    chosen = declared("watch", ref, by)
    _count("length", length)
    if fmt == "auto":
        # THE SIZE COMES FROM THE TABLE when the caller gave none, and a raw address has no
        # table entry: it needs a length or a fmt here, while a name's type is the tool's to
        # look up once the session answers.
        if chosen == "address" and length == 0:
            raise ds.Invalid("bad_argument",
                             f"a {mode} watch at an address needs a length in bytes, or a fmt "
                             f"that names its size (u16[8], char[16], {{x:i16,y:i16}}); "
                             f"{ref} was given neither")
        # A symbol with no length takes its width from the table at its step; a length given
        # is the width, whatever scalar the tool then picks for it.
        show_watch_width(mode, length)
        return
    # THE DECLARATION'S OWN VALIDATION, on a declaration that is built and dropped: the
    # format and the length against it are the model's rules, judged once there.
    placement.to_invalid(lambda: dec.Declaration("watch", "address", "0000:0000",
                                                 width=length, fmt=fmt, watch_mode=mode))
    show_watch_width(mode, vf.parse(fmt).width_for(length))


def _read_memory(ref: str, length: int = 16, **_: Any) -> None:
    address_shape(ref)
    read_length(length)


def _disassemble(ref: str, length: int = 16, **_: Any) -> None:
    address_shape(ref)
    code.check_length(length)


def _memdump(ref: str, length: int, dest: str, **_: Any) -> None:
    address_shape(ref)
    ds.check_dump_length(length)
    paths.absolute("dest", dest)


def _write(ref: str, data_hex: str, **_: Any) -> None:
    address_shape(ref)
    write_data(data_hex)


def _set_register(name: str, value: int, **_: Any) -> None:
    key = ds.check_register_name(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ds.Invalid("bad_argument", f"a register value is an integer; got {value!r}")
    ds.check_register_value(key, value)


def _symbols_load(source: str, base: str | None = None,
                  section_bases: dict[str, str] | None = None, types: str | None = None,
                  **_: Any) -> None:
    paths.absolute("source", source)
    if types is not None:
        paths.absolute("types", types)
    if base is not None and section_bases is not None:
        raise ds.Invalid("bad_argument",
            "`base` and `section_bases` are the two kinds of table, flat and "
                         "sectioned; give the one the map is, never both")
    if base is not None:
        placement.hex_arg("base", base)
    if section_bases is not None:
        placement.hex_bases(section_bases)


def _find(ref: str, data_hex: str, length: int, **_: Any) -> None:
    address_shape(ref)
    finder.check_find_length(length, finder.check_pattern(data_hex))


def _scan_start(ref: str, length: int, width: str = "byte", **_: Any) -> None:
    address_shape(ref)
    finder.check_scan_range(length, width)


def _scan_filter(operator: str = "=", value: int | None = None, **_: Any) -> None:
    finder.check_filter(operator, value)


def _state(name: str, seconds: float = ds.STATE_WAIT_S, **_: Any) -> None:
    ds.check_state_name(name)
    ds.check_wait_bound(seconds)


def _resume(seconds: float = 0.0, **rest: Any) -> None:
    if isinstance(seconds, bool) or not isinstance(seconds, int | float) or math.isnan(seconds):
        raise ds.Invalid("bad_argument",
            f"seconds={seconds!r} is not a number of seconds; 0 is no bound")
    if seconds < 0:
        raise ds.Invalid("bad_argument", f"seconds={seconds!r} is negative; 0 is no bound")
    _display(**rest)


#: The server's step vocabulary, handed in by the server once its tools exist: a list is judged
#: against the tools a step dispatches to, which this module cannot import.
STEP_OPS: Callable[[], dict[str, Callable[..., Any]]] | None = None


def steps_whole(name: str, steps: object) -> None:
    """A list of the server's operations judged whole, every step's op, argument names and
    values, before the first one runs; every refusal is listed, as the sequence lists them.
    The input route is the session's fact, so a key step is judged here as the window route
    takes it and again, on the session's own route, once the session answers."""
    if not isinstance(steps, list):
        raise ds.Invalid("bad_argument",
            f"{name} is a LIST of steps ({{'op': <name>, ...}}); got {steps!r}")
    assert STEP_OPS is not None, "the server registers its step vocabulary at import"
    refused = sequence.preflight(steps, STEP_OPS(), serial=False)
    if refused:
        first = refused[0]
        raise ds.Invalid("bad_argument",
            f"{len(refused)} step(s) refused before anything ran: "
            + "; ".join(f"step {e['step']} ({e['op']!r}) {e['message']}" for e in refused)
            + ". Nothing was run",
            ran=[], completed=0, failed_at=first["step"], failed=first, errors=refused)


def _perform(steps: list[dict[str, Any]], wait: float = 30.0, summaries: bool = False,
             **_: Any) -> None:
    sequence.validate_wait(wait)
    sequence.validate_summaries(summaries)
    steps_whole("steps", steps)


def _start(plan: list[dict[str, Any]] | None = None, plan_wait: float = 30.0,
           **_: Any) -> None:
    """`start` judges its paths and its launch itself, before anything starts; its plan is a
    list like `perform`'s, refused whole before the emulator boots rather than after it."""
    if plan:
        sequence.validate_wait(plan_wait)
        steps_whole("plan", plan)


def _drive(act: list[dict[str, Any]], expect: str | None = None, seconds: float | None = None,
           pattern: str = ".", limit: int = 40, wait: float = 30.0, summaries: bool = False,
           **_: Any) -> None:
    sequence.validate_summaries(summaries)
    if not isinstance(act, list) or not act:
        raise ds.Invalid("bad_argument",
            "act is a non-empty LIST of steps ({'op': <name>, ...}), the same shape `perform` "
            "takes")
    if not isinstance(pattern, str) or not pattern:
        raise ds.Invalid("bad_argument",
            "pattern is a non-empty regular expression over the E9 log ('.' for everything)")
    ds.compiled(pattern)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= ds.LOG_LIMIT_MAX:
        raise ds.Invalid("bad_argument",
            f"limit is between 1 and {ds.LOG_LIMIT_MAX}; got {limit!r}")
    if expect is not None:
        if not isinstance(expect, str) or not expect:
            raise ds.Invalid("bad_argument",
                "expect is a non-empty regular expression over the E9 log")
        ds.compiled(expect)
    wait_s = inputs.EFFECT_WAIT_DEFAULT_S if seconds is None else seconds
    if isinstance(wait_s, bool) or not isinstance(wait_s, int | float) \
            or not 0 < wait_s <= ds.RUN_TO_MAX:
        raise ds.Invalid("bad_argument",
            f"seconds is a bound between 0 and {ds.RUN_TO_MAX}; got {seconds!r}")
    if expect is None and seconds is not None:
        raise ds.Invalid("bad_argument",
            "`seconds` bounds the wait for `expect`, and there is no `expect`: it would be "
            "silently ignored")
    sequence.validate_wait(wait)
    steps_whole("act", act)


def _capture_frame(at: int, dest: str, source: str | None = None, **_: Any) -> None:
    ds.check_frame_args(at, paths.absolute("dest", dest))
    if source is not None:
        paths.absolute("source", source)


def _snapshot(dest: str = "", seconds: float = ds.SNAPSHOT_WAIT_S, **_: Any) -> None:
    optional_path("dest", dest)
    ds.check_wait_bound(seconds)


def _palette(first: int = 0, count: int = 0, dest: str = "", **_: Any) -> None:
    entries = screen.DAC_ENTRIES
    for name, value, top in (("first", first, entries - 1), ("count", count, entries)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= top:
            raise ds.Invalid("bad_argument", f"{name}={value!r} is not a whole number from 0 to "
                             f"{top}")
    if first + count > entries:
        raise ds.Invalid("bad_argument",
            f"first={first} and count={count} reach entry {first + count - 1}: the DAC holds "
            f"entries 0 to {entries - 1}")
    optional_path("dest", dest)


def _screen_view(dest: str = "", **_: Any) -> None:
    optional_path("dest", dest)


#: The longest text a wait looks for: a row of the widest text mode.
SCREEN_TEXT_MAX = 132


def _screen_wait(text: object, seconds: float = 30.0, **_: Any) -> None:
    if not isinstance(text, str) or not 1 <= len(text) <= SCREEN_TEXT_MAX \
            or _CONTROL_CHARACTER.search(text):
        raise ds.Invalid("bad_argument",
            f"text={text!r} is not 1 to {SCREEN_TEXT_MAX} printable characters: it is matched "
            f"inside one row of the screen")
    # A ROW IS READ WITHOUT ITS TRAILING BLANKS, and drawn in code page 437: a text ending in a
    # blank, or holding a character the screen cannot draw, could never be found.
    undrawable = sorted(set(text) - set(screen.CP437))
    if text.endswith(" ") or undrawable:
        raise ds.Invalid("bad_argument",
            f"text={text!r} " + (f"holds {undrawable}, which code page 437 does not draw"
                                 if undrawable else "ends in a blank, and a row is read "
                                 "without its trailing blanks")
            + ": it could never be found")
    ds.check_wait_bound(seconds)


def _symbols_find(name: str | None = None, offset: int | None = None,
                  linear: str | None = None, limit: int = 10, **_: Any) -> None:
    placement.check_find_args(name, offset, linear, limit)


# THE CONSOLE COMMANDS THAT LET THE GUEST RUN, by their first word. A run key goes through
# `Session._release`, which clears the stopped flag; a typed command does not, so after one the
# session goes on naming the stop before it. `VRT` runs to the next retrace, `RUNWATCH` runs on
# repainting, `INT` runs a handler to its return, the `LOG` family runs with the CPU log on;
# `INTT`, `TIMERIRQ` and `HEAVYLOG` stay at the debugger.
DEBUG_RELEASES = re.compile(r"\s*(" + "|".join(("VRT", "RUNWATCH", "INT", *ds.LOG_WORDS))
                            + r")(?:\s|$)", re.IGNORECASE)
# The whole string reaches the terminal, so a line break would type a second command past the
# classifier and an escape is a key (the run key among them).
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


def _debug(command: object, **_: Any) -> None:
    if not isinstance(command, str):
        raise ds.Invalid("bad_argument", f"command={command!r} is not text: one debugger command")
    if _CONTROL_CHARACTER.search(command):
        raise ds.Invalid("bad_argument",
            f"command={command!r} carries a control character: `debug` types one command of "
            f"printable text, and a line break or an escape reaches the console as a second "
            f"command or a key")
    released = DEBUG_RELEASES.match(command)
    if released is not None:
        word = released.group(1).upper()
        instead = ("`run_for(frames=1)`, which runs to the next retrace" if word == "VRT" else
                   "`trace`, which runs a counted number of instructions with the log on"
                   if word in ds.LOG_WORDS else
                   "`resume`, with a breakpoint where the machine should stop")
        raise ds.Invalid("bad_argument",
            f"`{word}` lets the guest run, and a typed release leaves `last_stop` naming the "
            f"stop before it. Release through {instead}: it reports the stop it reaches")


# The registry: an operation with no entry has nothing to judge before its step (it takes
# no values, or every value it takes needs the machine).
BY_OP: dict[str, Check] = {
    "send_keys": _send_keys, "send_mouse": _send_mouse,
    "log": _log, "log_wait": _log_wait,
    "resume": _resume, "step": _step, "run_to": _run_to, "run_for": _run_for,
    "trace": _trace,
    "breakpoint_at": _breakpoint_at, "breakpoint_interrupt": _breakpoint_interrupt,
    "watch_add": _watch_add, "read_memory": _read_memory, "disassemble": _disassemble,
    "memdump": _memdump,
    "write": _write, "set_register": _set_register,
    "symbols_load": _symbols_load, "symbols_find": _symbols_find,
    "capture_frame": _capture_frame, "find": _find, "scan_start": _scan_start,
    "debug": _debug, "interrupt_vectors": _interrupt_vectors,
    "palette": _palette, "screen_view": _screen_view, "screen_wait": _screen_wait,
    "snapshot": _snapshot, "scan_filter": _scan_filter, "state_save": _state,
    "state_load": _state, "perform": _perform, "drive": _drive, "start": _start,
    "comment_add": _comment_add, "comment_delete": _comment_delete,
    "comment_save": _comment_save, "comment_load": _comment_load,
}

#: TOOLS DELIBERATELY WITHOUT AN ENTRY, named so an absent entry and a forgotten one cannot
#: look alike. They take only a path their body judges first (`build_check`'s `binary`), or no
#: argument at all (`status`, `close`, `stop`, `scan_clear`, `state_list`, `breakpoint_list`,
#: `watch_list`, `captures`, `machine_map`, `screen_signature`, `call_stack`,
#: `comment_list`); or a flag every value of which is valid
#: (`registers`); or a `ref` that matches only against the declarations the session's store
#: holds (`breakpoint_clear`, `watch_clear`).
MACHINE_JUDGES = frozenset({
    "build_check", "status", "close", "stop", "registers", "scan_clear", "state_list",
    "breakpoint_list", "breakpoint_clear", "watch_list", "watch_clear", "captures",
    "machine_map", "screen_signature", "call_stack", "comment_list",
})


def check(tool: str, /, **given: Any) -> None:
    """The machine-independent half of one tool's checks, asked BEFORE the server asks for
    the session: a value as wrong with no session as with one is refused without booting
    a machine to hear it. A tool in `MACHINE_JUDGES` passes straight through; a name this
    registry has never heard of is a programmer's error here, raised as such. `send_keys` is
    judged here as the window route takes it, the route with every modifier, and again past
    the gate on the route the session has, which is the session's own fact."""
    if tool not in BY_OP and tool not in MACHINE_JUDGES:
        raise AssertionError(f"no such tool for a pre-gate check: {tool!r}")
    judge = BY_OP.get(tool)
    if judge is not None:
        judge(**given)


def probe_check(tool: str, given: dict[str, Any], effective: dict[str, Any]) -> None:
    """`check` in the shape `scry_core.probe.Check` takes: the server's `tool()` wrapper judges
    the arguments the caller GAVE, so the probe does the same and `effective` is not used."""
    check(tool, **given)


def preflight(op: str, args: dict[str, Any], *, serial: bool) -> None:
    """Run the operation's value checks on a step's arguments, raising the refusal the
    synchronous tool would have raised. Called by the sequence over every step before the
    first one runs."""
    check = BY_OP.get(op)
    if check is None:
        return
    if op == "send_keys":
        check(serial=serial, **args)
    else:
        check(**args)
