"""The argument checks a step passes BEFORE any step runs: one registry, by operation name,
pointing at the same functions each tool runs first when called on its own.

A value one step would refuse mid-list must be refused before the first step posts a key or
releases the machine, and the reply lists every refused step. Not checkable here, because it
depends on earlier steps or on the machine: symbol names, file existence, mode, selectors, live
addresses. Those refuse at their step, with `failed_at` and `ran`.

The functions take the step's arguments by name and ignore what they do not judge.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from scry_core import (
    judges,
    log_marks,
    media_tools,
    narrowing,
    picture,
    recording,
    screen_map,
)
from scry_core import (
    scan_vocabulary as words,
)
from scry_core import sequence as executor
from scry_core import sequence_account as account
from scry_core import value_format as vf
from scry_core import vocabulary as vocab

from scry_dosbox_x import (
    capture_files,
    code,
    grammar,
    inputs,
    machine,
    media,
    paths,
    placement,
    sequence,
    stepping,
)
from scry_dosbox_x import comment_file as cf
from scry_dosbox_x import dac as vgadac
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import find as finder
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import screen_pens as by_pens
from scry_dosbox_x import session as ds
from scry_dosbox_x import trace as tracing

Check = Callable[..., None]


def address_shape(ref: object, by: str = "auto") -> None:
    """`placement.address_shape` for a step whose ref may not be a string."""
    if not isinstance(ref, str):
        raise ds.Invalid("bad_argument", f"ref={ref!r} is not a string: a symbol or a SEG:OFF")
    placement.address_shape(ref, None if by == "auto" else by)


#: A breakpoint is never declared through a pointer (code does not move behind one).
BREAKPOINT_BY = ("auto", "symbol", "address")
WATCH_BY = (*BREAKPOINT_BY, "pointer")


def by_choice(by: object, family: tuple[str, ...]) -> None:
    vocab.one_of("by", by, family)


def declared(kind: str, ref: object, by: str) -> str:
    """The `by` the store will take the ref as, judged on a declaration built and dropped."""
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
    """A comment's ref by the comment file's rule, so a call and a file refuse the same refs."""
    if not isinstance(ref, str):
        raise ds.Invalid("bad_argument", f"ref={ref!r} is not a string: a symbol or a SEG:OFF")
    fault = cf.ref_fault(ref)
    if fault is not None:
        raise ds.Invalid("bad_argument", f"a comment's ref {fault}")


def comment_text(text: object) -> None:
    """A comment's text by the comment file's rule."""
    if not isinstance(text, str):
        raise ds.Invalid("bad_argument", f"text={text!r} is not text")
    fault = cf.text_fault(text)
    if fault is not None:
        raise ds.Invalid("bad_argument", f"a comment's text {fault}")


def check_add_comment(ref: object, text: object, **_: Any) -> None:
    comment_ref(ref)
    comment_text(text)


def check_delete_comment(ref: object, **_: Any) -> None:
    comment_ref(ref)


#: The widest number this debugger holds: its registers and addresses are 32-bit.
NUMBER_BITS = 32


def number(name: str, value: object) -> int:
    """`value` as an integer or hex spelling, at most `NUMBER_BITS` wide."""
    return judges.number(name, value, NUMBER_BITS, "this debugger")


def check_save_comments(dest: object, **_: Any) -> None:
    paths.dest_file("dest", dest)


def check_load_comments(path: object, **_: Any) -> None:
    paths.absolute("path", path)


# Bounds live here, not in a tool body, so the whole-list check of a sequence sees them.

def write_data(value: str) -> bytes:
    """A caller's hex bytes, parsed once, up to one read's reach (the readback's span)."""
    data = finder.hex_bytes("data_hex", value, verb="write")
    if len(data) > grammar.READ_BYTES_MAX:
        raise ds.Invalid("bad_argument",
            f"a write carries up to {grammar.READ_BYTES_MAX} bytes, what one read takes back for "
            f"the readback; {len(data)} is a region")
    return data


def read_length(length: int) -> None:
    """`read_memory`'s span: 1 to one read's reach."""
    if not 1 <= length <= grammar.READ_BYTES_MAX:
        raise ds.Invalid("bad_argument",
            f"length={length!r} is not 1 to {grammar.READ_BYTES_MAX}; above that the answer is "
            "`memdump`, which writes exactly the bytes asked for")


# A change watch arms one debugger row per byte, each checked at every guest instruction.
CHANGE_WATCH_MAX = 16
#: The debugger's `TAP` bounds: a count's range, a capture's block.
TAP_MAX = {"count": 1024, "capture": 128}
# A freeze arms one `FM` row per byte, each compared and written back after every instruction.
FREEZE_MAX = 16


def watch_width(mode: str, width: int) -> None:
    """A show watch is at most one read's reach; a change watch at most `CHANGE_WATCH_MAX`."""
    if mode == "show" and width > grammar.READ_BYTES_MAX:
        raise ds.Invalid("bad_argument",
            f"a show watch reads up to {grammar.READ_BYTES_MAX} bytes at a stop (what one read "
            f"takes); {width} is a region, and it would be stored only to report "
            f"'unreadable' at every stop. Use memdump for a region, or a smaller length")
    if mode in TAP_MAX and width > TAP_MAX[mode]:
        raise ds.Invalid("bad_argument",
            f"a {mode} watch is at most {TAP_MAX[mode]} bytes"
            + (": each row holds the whole block" if mode == "capture" else
               ": the debugger's tap takes no longer range")
            + f"; {width} is a region for memdump")
    if mode == "freeze" and width > FREEZE_MAX:
        raise ds.Invalid("bad_argument",
            f"a freeze watch is at most {FREEZE_MAX} bytes: it arms one debugger row per byte, "
            f"each written back after every instruction the guest runs; freeze the fields that "
            f"matter")
    if mode == "change" and width > CHANGE_WATCH_MAX:
        raise ds.Invalid("bad_argument",
            f"a change watch is at most {CHANGE_WATCH_MAX} bytes: it arms one debugger row "
            f"per byte, each checked at every instruction the guest runs; {width} bytes are a "
            f"show watch, or change watches on the fields that matter")


def _send_keys(keys: list[str], modifiers: list[str] | None = None, expect: str = "",
               seconds: float | None = None, **_: Any) -> None:
    inputs.check_keys(keys, modifiers, expect or None, seconds)


def _send_mouse(x: int | None = None, y: int | None = None, button: str = "",
                action: str = "", units: str = "screen", expect: str = "",
                seconds: float | None = None, target: str = "", to_x: int | None = None,
                to_y: int | None = None, **_: Any) -> None:
    inputs.check_mouse(x, y, button or None, action, units, expect or None, seconds,
                       target or None, to_x, to_y)


def check_load_map(path: str = "", scale: object = 1, margin: object = None, **_: Any) -> None:
    screen_map.check_path("path", path)
    screen_map.judged_view(scale, margin)


def check_add_map(screen: str = "", match: Any = None, controls: Any = None,
                  cells: str = "", anchor: object = "", **_: Any) -> None:
    vocab.one_of("cells", cells, screen_map.CELLS_WORDS)
    screen_map.check_add(screen, match, controls, cells, anchor)


def check_pointer_map(pointer: object = None, **_: Any) -> None:
    screen_map.check_pointer(pointer)


def check_save_map(dest: str = "", overwrite: bool = False, **_: Any) -> None:
    screen_map.check_save(dest, overwrite)


def _log(pattern: str, channel: str, limit: int = 40, since_mark: int = 0, **_: Any) -> None:
    dlogs.check_pattern(pattern)
    dlogs.check_e9_limit(limit)
    dlogs.check_channel(channel)
    log_marks.check_position(since_mark, channel)


def _log_wait(pattern: str, channel: str, seconds: float = 30.0, since_mark: int = 0,
              **_: Any) -> None:
    vocab.check_wait(seconds)
    dlogs.check_pattern(pattern)
    dlogs.check_channel(channel)
    log_marks.check_position(since_mark, channel)


def _step(count: int = 1, mode: str = "into", **_: Any) -> None:
    stepping.check_step(mode, count)


def _run_to(ref: str = "", control: str = "", seconds: float = 30.0, screen: str = "",
            **_: Any) -> None:
    vocab.check_wait(seconds)
    screen_map.check_run_to(ref, screen)
    if ref.strip():
        address_shape(ref)
    if not control and not screen:
        raise screen_map.no_control()
    if control:
        address_shape(control)


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ds.Invalid("bad_argument", f"{name}={value!r} is not a whole number of zero or more")
    return value


#: The largest integer a double holds exactly (the emulated clock is one).
RUN_FOR_MS_MAX = 2 ** 53


def optional_dest(dest: object) -> None:
    """A file `dest` whose empty string means the scratch's."""
    if dest != "":
        paths.dest_file("dest", dest)


def _trace(instructions: int, shape: str = "normal", dest: str = "", seconds: float = 60.0,
           **_: Any) -> None:
    tracing.check_arguments(instructions, shape)
    optional_dest(dest)
    vocab.check_wait(seconds)


def _run_for(milliseconds: int = 0, frames: int = 0, seconds: float = 30.0,
             **_: Any) -> None:
    ms, n = _count("milliseconds", milliseconds), _count("frames", frames)
    if ms > RUN_FOR_MS_MAX:
        raise ds.Invalid("bad_argument",
            f"milliseconds={ms} is past what the floating-point emulated clock counts exactly")
    if (ms > 0) == (n > 0):
        raise ds.Invalid("bad_argument",
            f"exactly one of milliseconds and frames is above zero; got milliseconds={ms}, "
            f"frames={n}")
    vocab.check_wait(seconds)


def _record(frames: int, dest: str = "", seconds: float = 60.0, **_: Any) -> None:
    if _count("frames", frames) < 1:
        raise ds.Invalid("bad_argument", f"frames={frames!r} is not a whole number of one or "
                         "more: the retraces the capture is on for")
    optional_dest(dest)
    vocab.check_wait(seconds)


def _audio_record(frames: int, dest: str = "", seconds: float = 60.0, kind: str = "wav",
                  **_: Any) -> None:
    if kind not in capture_files.AUDIO_KINDS:
        raise ds.Invalid("bad_argument",
                         f"kind={kind!r} is one of {', '.join(capture_files.AUDIO_KINDS)}")
    _record(frames, dest, seconds)


def _breakpoint_at(ref: str, by: str = "auto", **_: Any) -> None:
    by_choice(by, BREAKPOINT_BY)
    declared("breakpoint", ref, by)


def _breakpoint_interrupt(number: int, ah: int | None = None, **_: Any) -> None:
    ds.check_interrupt(number, ah)


def _regpoint_add(condition: str, **_: Any) -> None:
    grammar.condition_row(condition)


def _interrupt_vectors(number: int | None = None, **_: Any) -> None:
    if number is not None:
        ds.check_interrupt(number, None)


def tap_fields(mode: str, trigger: str, trigger_type: str, length: int, fmt: str
               ) -> tuple[str | None, str | None]:
    """A watch's `trigger` and `trigger_type` as stored: a capture's own, nothing on the others,
    which are refused one given. A read capture keeps the access alone: no length or fmt."""
    vocab.one_of("trigger_type", trigger_type, dec.TRIGGER_TYPES)
    if mode != "capture":
        if trigger or trigger_type != "w":
            raise ds.Invalid("bad_argument", f"trigger and trigger_type are a capture watch's; "
                             f"a {mode} watch takes neither")
        return None, None
    if trigger_type == "r":
        if trigger or length or fmt != "auto":
            raise ds.Invalid("bad_argument",
                             "a capture of reads keeps each read of `ref` itself, with no block: "
                             "no trigger, length or fmt")
        return None, "r"
    if not trigger:
        raise ds.Invalid("bad_argument", "a capture of writes names its trigger: each write of "
                         "`trigger` keeps a row holding the block at `ref`")
    by = placement.decide_by(trigger)
    if by == "pointer":
        raise ds.Invalid("bad_argument", f"trigger={trigger!r} goes through a pointer, and a tap "
                         "sits on one place for its life: name a symbol or a SEG:OFF")
    return dec.canonical_ref(trigger, by), "w"


def _watch_add(ref: str, mode: str, length: int = 0, fmt: str = "auto", by: str = "auto",
               trigger: str = "", trigger_type: str = "w", **_: Any) -> None:
    placement.to_invalid(lambda: dec.check_watch_mode(mode))
    by_choice(by, WATCH_BY)
    chosen = declared("watch", ref, by)
    _count("length", length)
    trig, side = tap_fields(mode, trigger, trigger_type, length, fmt)
    if mode in dec.KEPT_MODES:
        placement.to_invalid(lambda: dec.Declaration("watch", chosen, ref, width=1, fmt="u8",
                                                     watch_mode=mode, trigger=trig,
                                                     trigger_type=side))
        if trig is not None:
            declared("watch", trig, "auto")
        if side == "r":
            return
    if fmt == "auto":
        # A raw address has no table entry to take a size from.
        if chosen == "address" and length == 0:
            raise ds.Invalid("bad_argument",
                             f"a {mode} watch at an address needs a length in bytes, or a fmt "
                             f"that names its size (u16[8], char[16], {{x:i16,y:i16}}); "
                             f"{ref} was given neither")
        # A symbol with no length takes its width from the table at its step.
        watch_width(mode, length)
        return
    placement.to_invalid(lambda: dec.Declaration("watch", "address", "0000:0000",
                                                 width=length, fmt=fmt, watch_mode=mode,
                                                 trigger=trig, trigger_type=side))
    watch_width(mode, vf.parse(fmt).width_for(length))


def _read_memory(ref: str, length: int = 16, **_: Any) -> None:
    address_shape(ref)
    read_length(length)


def _disassemble(ref: str, length: int = 16, **_: Any) -> None:
    address_shape(ref)
    code.check_length(length)


def _memdump(ref: str, length: int, dest: str, **_: Any) -> None:
    address_shape(ref)
    ds.check_dump_length(length)
    paths.dest_file("dest", dest)


def _write(ref: str, data_hex: str, **_: Any) -> None:
    address_shape(ref)
    write_data(data_hex)


def _set_register(name: str, value: object, **_: Any) -> None:
    key = ds.check_register_name(name)
    ds.check_register_value(key, number("value", value))


def _symbols_load(path: str, base: str = "",
                  section_bases: dict[str, str] | None = None, types: str = "",
                  **_: Any) -> None:
    paths.absolute("path", path)
    if types:
        paths.absolute("types", types)
    if base and section_bases is not None:
        raise ds.Invalid("bad_argument",
            "`base` and `section_bases` are the two kinds of table, flat and "
                         "sectioned; give the one the map is, never both")
    if base:
        placement.hex_arg("base", base)
    if section_bases is not None:
        placement.hex_bases(section_bases)


def _find(ref: str, data_hex: str, length: int, **_: Any) -> None:
    address_shape(ref)
    finder.check_find_length(length, finder.check_pattern(data_hex))


def check_start_scan(ref: str, length: int, cell_bytes: int = 1, **_: Any) -> None:
    address_shape(ref)
    finder.check_scan_range(length, cell_bytes)


def check_filter_scan(operator: str = "=", value: object = None, **rest: Any) -> None:
    # Read at the call: importing `find` reaches this module, so its names are not yet
    # there at definition.
    finder.check_filter(operator, None if value is None else number("value", value),
                        rest.get("limit", words.HITS_DEFAULT))


def _machine_map(sections: list[str] | None = None, dest: str = "", **_: Any) -> None:
    narrowing.sections(sections, machine.SECTION_NAMES, machine.DEFAULT_SECTIONS)
    if dest:
        paths.fresh_dest("dest", dest)


def check_state(name: str, seconds: float = ds.STATE_WAIT_S, **_: Any) -> None:
    dlaunch.check_state_name(name)
    vocab.check_wait(seconds)


def _resume(seconds: float = 0.0, **_: Any) -> None:
    vocab.check_wait(seconds, zero_means="no wait")


#: Handed in by the server once its tools exist: this module cannot import the tools.
STEP_OPS: Callable[[], dict[str, Callable[..., Any]]] | None = None


def take_step_ops(ops: Callable[[], dict[str, Callable[..., Any]]]) -> None:
    """Register the server's step vocabulary."""
    global STEP_OPS
    STEP_OPS = ops


def steps_whole(name: str, steps: object) -> None:
    """A list of steps judged whole before the first runs; every refusal is listed."""
    if not isinstance(steps, list):
        raise ds.Invalid("bad_argument",
            f"{name} is a LIST of steps ({{'op': <name>, ...}}); got {steps!r}")
    assert STEP_OPS is not None, "the server registers its step vocabulary at import"
    ops = STEP_OPS()
    refused = sequence.preflight(steps, ops)
    if refused:
        first = refused[0]
        raise ds.Invalid("bad_argument", executor.refused_text(refused),
            ran=[], steps_completed=0, failed_at=first["step"], failed=first, errors=refused,
            **executor.vocabulary_named(refused, ops))


def _perform(steps: list[dict[str, Any]] | None = None, path: str = "",
             settle_seconds: float = 30.0, summaries: bool = False, **_: Any) -> None:
    recording.check_perform_arguments(steps, path)
    sequence.validate_wait(settle_seconds)
    account.check_summaries(summaries)
    if steps is not None:
        steps_whole("steps", steps)


def _start(plan: list[dict[str, Any]] | None = None, settle_seconds: float | None = None,
           **_: Any) -> None:
    """The plan is refused whole before the emulator boots."""
    if settle_seconds is not None and not plan:
        raise ds.Invalid("bad_argument", "`settle_seconds` bounds the waits of a `plan`, and "
                         "there is no plan: it would be silently ignored")
    if plan:
        sequence.validate_wait(sequence.SETTLE_DEFAULT_S if settle_seconds is None
                               else settle_seconds)
        steps_whole("plan", plan)


def _drive(act: list[dict[str, Any]], expect: str = "", seconds: float | None = None,
           pattern: str = ".", limit: int = 40, settle_seconds: float = 30.0,
           summaries: bool = False, **_: Any) -> None:
    try:
        _drive_arguments(act, expect, seconds, pattern, limit, settle_seconds, summaries)
    except ds.Invalid as e:
        raise sequence.drive_refused(e) from None


def _drive_arguments(act: list[dict[str, Any]], expect: str, seconds: float | None,
                     pattern: str, limit: int, settle_seconds: float, summaries: bool) -> None:
    account.check_summaries(summaries)
    if not isinstance(act, list) or not act:
        raise ds.Invalid("bad_argument",
            "act is a non-empty LIST of steps ({'op': <name>, ...}), the same shape `perform` "
            "takes")
    dlogs.check_pattern(pattern)
    dlogs.check_e9_limit(limit)
    inputs.check_expectation(expect or None, seconds)
    sequence.validate_wait(settle_seconds)
    steps_whole("act", act)


def _capture_frame(frame: int, dest: str, capture_path: str = "", **_: Any) -> None:
    ds.check_frame_args(frame, paths.dest_file("dest", dest))
    if capture_path:
        paths.absolute("capture_path", capture_path)


def _snapshot(dest: str = "", seconds: float = ds.SNAPSHOT_WAIT_S, **_: Any) -> None:
    optional_dest(dest)
    vocab.check_wait(seconds)


def _palette(first: object = 0, count: int = 0, scale: int = 0, dest: str = "",
             **_: Any) -> None:
    entries = vgadac.DAC_ENTRIES
    first = number("first", first)
    for name, value, top in (("first", first, entries - 1), ("count", count, entries)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= top:
            raise ds.Invalid("bad_argument", f"{name}={value!r} is not a whole number from 0 to "
                             f"{top}")
    if first + count > entries:
        raise ds.Invalid("bad_argument",
            f"first={first} and count={count} reach entry {first + count - 1}: the DAC holds "
            f"entries 0 to {entries - 1}")
    picture.check_scale(scale)
    optional_dest(dest)


def _screen_view(crop: list[int] | None = None, scale: int = 0, dest: str = "",
                 mode: str = "render", pens: list[int] | None = None,
                 point: list[int] | None = None, attach: bool = True, **_: Any) -> None:
    if crop is not None:
        judges.rect("crop", crop)
    picture.check_scale(scale)
    optional_dest(dest)
    by_pens.check_view(mode, pens, point, crop, scale, dest, attach)


def _screen_signature(crop: list[int] | None = None, **_: Any) -> None:
    if crop is not None:
        judges.rect("crop", crop)


#: The longest text a wait looks for: a row of the widest text mode.
SCREEN_TEXT_MAX = 132
#: `screen_wait`'s palette predicates: every DAC entry black, which is how a fade ends.
PALETTES = ("black",)
#: The largest sampling step it takes: at 70 Hz, 600 retraces is already 8.5 s of blind running.
SAMPLED_EVERY_MAX = 600


def _screen_wait(text: object = "", screen: object = "", palette: object = "", every: int = 0,
                 seconds: float = 30.0, **_: Any) -> None:
    named = [n for n, v in (("text", text), ("screen", screen), ("palette", palette)) if v]
    if len(named) != 1:
        raise ds.Invalid("bad_argument",
                         "screen_wait runs on exactly one of `text`, `screen` or `palette`; got "
                         f"{len(named)} of them. Each is a different read of the screen, and a "
                         "frame has the budget of one")
    if palette:
        vocab.one_of("palette", palette, PALETTES)
    if not isinstance(every, int) or isinstance(every, bool) or not 0 <= every <= SAMPLED_EVERY_MAX:
        raise ds.Invalid("bad_argument",
                         f"every={every!r} is 0 to {SAMPLED_EVERY_MAX} retraces: the step a "
                         "wait reads the screen at")
    if not text:
        return
    if not isinstance(text, str) or not 1 <= len(text) <= SCREEN_TEXT_MAX \
            or _CONTROL_CHARACTER.search(text):
        raise ds.Invalid("bad_argument",
            f"text={text!r} is not 1 to {SCREEN_TEXT_MAX} printable characters: it is matched "
            f"inside one row of the screen")
    # A row is read without trailing blanks and drawn in code page 437.
    # Imported here: `screen_wait`'s parameter shadows the module at the top of the function.
    from scry_dosbox_x import screen as dscreen
    undrawable = sorted(set(text) - set(dscreen.CP437))
    if text.endswith(" ") or undrawable:
        raise ds.Invalid("bad_argument",
            f"text={text!r} " + (f"holds {undrawable}, which code page 437 does not draw"
                                 if undrawable else "ends in a blank, and a row is read "
                                 "without its trailing blanks")
            + ": it could never be found")
    vocab.check_wait(seconds)


def _symbols_find(name: str = "", offset: int | None = None,
                  linear: str = "", limit: int = 10, **_: Any) -> None:
    placement.check_find_args(name or None, offset, linear or None, limit)


# Debugger commands that let the guest run, by first word. One sent through `debug` does not clear
# the stopped flag as `Session.release` does, so `last_stop` would keep naming the stop before it.
DEBUG_RELEASES = re.compile(r"\s*(" + "|".join(("RUN", "VRT", "RUNWATCH", "INT", "STEPIN",
                                                *ds.LOG_WORDS))
                            + r")(?:\s|$)", re.IGNORECASE)
# A line break would send a second request past the classifier.
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


def _debug(command: object, **_: Any) -> None:
    if not isinstance(command, str):
        raise ds.Invalid("bad_argument", f"command={command!r} is not text: one debugger command")
    if _CONTROL_CHARACTER.search(command):
        raise ds.Invalid("bad_argument",
            f"command={command!r} carries a control character: `debug` sends one command of "
            f"printable text, and a line break would be a second request on the channel")
    words = command.split()
    if len(words) > 1 and words[0].upper() == "DOSTRACE":
        raise ds.Invalid("bad_argument",
            "`DOSTRACE` with a file or `OFF` would move or end the trace the `dos` channel "
            "reads, which `start(dos_calls=True)` opened; `DOSTRACE` alone lists it")
    released = DEBUG_RELEASES.match(command)
    if released is not None:
        word = released.group(1).upper()
        instead = ("`run_for(frames=1)`, which runs to the next retrace" if word == "VRT" else
                   "`trace`, which runs a counted number of instructions with the log on"
                   if word in ds.LOG_WORDS else
                   "`step`, which reads where each instruction landed" if word == "STEPIN" else
                   "`resume`, with a breakpoint where the machine should stop")
        raise ds.Invalid("bad_argument",
            f"`{word}` lets the guest run, and a release sent here leaves `last_stop` naming the "
            f"stop before it. Release through {instead}: it reports the stop it reaches")


def _guest_file(path: str, **_: Any) -> None:
    paths.absolute("path", path)


def _folded(name: str) -> Check:
    """A fold's judge (`dosbox_folds.CHECKS`), read at the call: that module imports this one."""
    def check(**given: Any) -> None:
        from scry_dosbox_x import folds as dosbox_folds
        dosbox_folds.CHECKS[name](**given)
    return check


# An operation with no entry takes no values, or every value it takes needs the machine.
BY_OP: dict[str, Check] = {
    "send_keys": _send_keys, "send_mouse": _send_mouse,
    "log": _log, "log_wait": _log_wait,
    "resume": _resume, "step": _step, "run_to": _run_to, "run_for": _run_for,
    "record": _record, "audio_record": _audio_record,
    "trace": _trace,
    "breakpoint_at": _breakpoint_at, "breakpoint_interrupt": _breakpoint_interrupt,
    "regpoint_add": _regpoint_add,
    "watch_add": _watch_add, "read_memory": _read_memory, "disassemble": _disassemble,
    "memdump": _memdump,
    "write": _write, "set_register": _set_register,
    "symbols_load": _symbols_load, "symbols_find": _symbols_find,
    "capture_frame": _capture_frame, "find": _find,
    "debug": _debug, "interrupt_vectors": _interrupt_vectors,
    "palette": _palette, "screen_view": _screen_view, "screen_wait": _screen_wait,
    "screen_signature": _screen_signature, "series_capture": media.check_series_capture,
    **{name: media_tools.TOOLS[name].check for name in media.MEDIA_TOOLS},
    "snapshot": _snapshot, "perform": _perform, "drive": _drive, "start": _start,
    "machine_map": _machine_map,
    **{name: _folded(name) for name in ("declaration_list", "declaration_clear", "comment_write",
                                        "screen_map_write", "scan", "state_write", "port", "pic",
                                        "a20")},
    "guest_file": _guest_file,
}

SEQUENCES = frozenset({"perform", "drive"})
#: The tools that are no step of a sequence, named once; other sets are read off it.
NOT_STEPS = SEQUENCES | {"build_check", "start", "close", "perform_export", "window",
                         "promote"}

#: Tools deliberately without an entry, so an absent entry and a forgotten one differ: no
#: arguments, only valid values (`registers`), or no step (`build_check`, `perform_export`,
#: `close`).
MACHINE_JUDGES = frozenset({
    "status", "stop", "registers", "state_list", "captures", "call_stack", "comment_list",
    "screen_map_find",
}) | (NOT_STEPS - BY_OP.keys())


def check(tool: str, /, **given: Any) -> None:
    """The machine-independent checks of one tool, asked before the server asks for the session.
    An unknown name is a programmer's error, raised as an AssertionError."""
    if tool not in BY_OP and tool not in MACHINE_JUDGES:
        raise AssertionError(f"no such tool for a pre-gate check: {tool!r}")
    judge = BY_OP.get(tool)
    if judge is not None:
        judge(**given)


def probe_check(tool: str, given: dict[str, Any], effective: dict[str, Any]) -> None:
    """`check` in the shape `scry_core.probe.Check` takes; judges what the caller gave."""
    check(tool, **given)


def preflight(op: str, args: dict[str, Any]) -> None:
    """Run the operation's value checks on a step's arguments, as the synchronous tool would."""
    check = BY_OP.get(op)
    if check is None:
        return
    check(**args)
