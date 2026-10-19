"""THE ONE LINE EVERY REPLY OPENS WITH, one function per tool.

The MCP client paints a call's tool name, its arguments and its reply and nothing else, so two
calls of one tool are told apart only by what is IN the reply: the `summary`, written for a
person, in the tool's own words. Under `perform(summaries=True)` it heads the compact row an
earlier step is cut to.

EACH TOOL NAMES ITS OWN at registration (`dosbox_x_server.tool(..., summary=...)`), and the
argument is required: a tool registered without one fails at import, so no tool can lack one.
A refusal's line is the envelope's (`refusal`), the same for every tool, and never reaches
these.

Every function takes the call's arguments as the caller gave them, defaults applied, and the
reply the tool built, and returns one line. It reads the reply with `.get`, never by key: a
summary that raised over a field a reply did not carry would turn an answer into a traceback.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

#: A tool's summary: the call's arguments (defaults applied) and its reply, to one line.
Summary = Callable[[dict[str, Any], dict[str, Any]], str]

# Where a refusal's prose is cut for the line: the whole of it is in `message`.
REFUSAL_CHARS_SHOWN = 120


def clipped(text: str, limit: int = REFUSAL_CHARS_SHOWN) -> str:
    """A long refusal cut for the summary line: at a word, with a mark saying the rest is in
    `message`. A cut inside a word reads as a word that does not exist."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit + 1)
    return text[:cut if cut > 0 else limit] + "..."


def refusal(name: str, reply: dict[str, Any]) -> str:
    """Every tool's line for a reply that is not `ok`: the status, the code, and the prose cut
    at a word."""
    return (f"{name}: {reply.get('status')} ({reply.get('code')}), "
            f"{clipped(str(reply.get('message', '')))}")


def _at(stop: Any) -> str:
    return f"{stop['cs']}:{stop['eip']}" if isinstance(stop, dict) else "?"


def _block(reply: dict[str, Any], key: str) -> dict[str, Any]:
    value = reply.get(key)
    return value if isinstance(value, dict) else {}


def _effect(effect: dict[str, Any], none: str) -> str:
    """What an input's check found: seen, not seen, or `none` when no check ran."""
    return ("effect seen" if effect.get("seen") else
            "effect not seen" if effect.get("checked") else none)


# ------------------------------------------------------------------------------ session

def build_check(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"build_check: {reply.get('binary')} ({reply.get('binary_origin')}), debugger "
            f"{reply.get('debugger')}, heavy_debug {reply.get('heavy_debug')}")


def start(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # with a `plan` the start facts sit under `start` and the top level is the account
    facts = _block(reply, "start") or reply
    plan = ""
    if reply.get("ran") is not None:
        plan = f", then {reply.get('completed')} of {len(args.get('plan') or [])} steps"
    return (f"start {Path(str(args.get('conf', ''))).name}: {facts.get('mode')} on "
            f"{facts.get('binary')} ({facts.get('binary_origin')}), debugger answered after "
            f"{facts.get('ready_after_s')}s{plan}")


def status(args: dict[str, Any], reply: dict[str, Any]) -> str:
    ses = _block(reply, "session")
    if not ses:
        return "status: no session"
    return (f"status: {'alive' if ses.get('alive') else 'gone'}, "
            f"{ses.get('seconds_elapsed')}s of a {ses.get('seconds_bound')}s bound")


def close(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if not reply.get("closed"):
        return f"close: {reply.get('note')}"
    reap = f", reap failed: {reply.get('reap_failed')}" if reply.get("reap_failed") else ""
    return f"close: {reply.get('how')}, exit code {reply.get('exit_code')}{reap}"


# ------------------------------------------------------------------------ the guest's log

def log(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"log {args.get('channel', '')} /{args.get('pattern', '')}/: "
            f"{len(reply.get('lines') or [])} of {reply.get('lines_total')} lines")


def log_wait(args: dict[str, Any], reply: dict[str, Any]) -> str:
    when = "already in the log" if reply.get("already") else f"after {reply.get('waited_s')}s"
    return f"log_wait {args.get('channel', '')} /{args.get('pattern', '')}/: matched {when}"


# ------------------------------------------------------------- reading and writing

def registers(args: dict[str, Any], reply: dict[str, Any]) -> str:
    stale = " (last stop)" if reply.get("stale") else ""
    return f"registers{stale}: {len(_block(reply, 'registers'))} registers"


def read_memory(args: dict[str, Any], reply: dict[str, Any]) -> str:
    seg, off = reply.get("segment"), reply.get("offset")
    at = f"{seg:04X}:{off:04X}" if isinstance(seg, int) and isinstance(off, int) else "?"
    return f"read_memory {args.get('ref', '')}: {len(reply.get('rows') or [])} rows at {at}"


def disassemble(args: dict[str, Any], reply: dict[str, Any]) -> str:
    seg, off = reply.get("segment"), reply.get("offset")
    at = f"{seg:04X}:{off:08X}" if isinstance(seg, int) and isinstance(off, int) else "?"
    return (f"disassemble {args.get('ref', '')}: {len(reply.get('lines') or [])} lines at {at}, "
            f"{reply.get('code_bits')}-bit")


def call_stack(args: dict[str, Any], reply: dict[str, Any]) -> str:
    calls = reply.get("calls") or []
    first = calls[0] if calls and isinstance(calls[0], dict) else {}
    return (f"call_stack: {len(calls)} calls, innermost "
            f"{first.get('symbol') or first.get('addr', '?')}, heuristic")


def memdump(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"memdump {args.get('ref', '')}: {reply.get('bytes')} bytes to {reply.get('path')}"


def find(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"find {args.get('ref', '')}: {reply.get('hits_total')} hits of "
            f"{args.get('data_hex')} in {reply.get('length')} bytes")


def scan_start(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"scan_start {args.get('ref', '')}: {reply.get('candidates')} {reply.get('width')} "
            f"candidates")


def scan_filter(args: dict[str, Any], reply: dict[str, Any]) -> str:
    what = f"{args.get('operator', '=')} {args.get('value')}"
    return f"scan_filter {what}: {reply.get('survivors')} survivors" + (
        ", scan closed" if reply.get("closed") else "") + (
        ", not listed (over `limit`)" if reply.get("truncated") else "")


def scan_clear(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return "scan_clear: cleared" if reply.get("cleared") else "scan_clear: nothing was open"


def debug(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"debug {args.get('command', '')!r}: {reply.get('screen_chars')} chars"


def set_register(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"set_register {args.get('name', '')} = {args.get('value')}, verified "
            f"{reply.get('verified')}")


def write(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"write {args.get('ref', '')}: {reply.get('written')} bytes, verified "
            f"{reply.get('verified')}")


# ------------------------------------------------------------ advancing the machine

def resume(args: dict[str, Any], reply: dict[str, Any]) -> str:
    halted = reply.get("halted")
    return f"resume: {'halted at ' + _at(reply.get('stopped_at')) if halted else 'running'}"


def stop(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if not reply.get("interrupted"):
        return "stop: already stopped"
    return f"stop: {reply.get('how')}, at {reply.get('stopped_at')} after {reply.get('waited_s')}s"


def step(args: dict[str, Any], reply: dict[str, Any]) -> str:
    where = "running" if reply.get("running") else f"at {_at(reply.get('after'))}"
    return f"step {args.get('count', 1)}: {reply.get('completed')} done, {where}"


def run_for(args: dict[str, Any], reply: dict[str, Any]) -> str:
    where = "running" if reply.get("running") else f"at {_at(reply.get('stopped_at'))}"
    asked = (f"{args.get('milliseconds')} ms" if args.get("milliseconds")
             else f"{args.get('frames')} frames")
    return f"run_for {asked}: {reply.get('verdict')}, {reply.get('polls')} polls, {where}"


def trace(args: dict[str, Any], reply: dict[str, Any]) -> str:
    found = _block(reply, "trace")
    return (f"trace {args.get('instructions')} {args.get('shape')}: {reply.get('verdict')}, "
            f"{found.get('instructions')} executed at {found.get('addresses')} addresses, at "
            f"{_at(reply.get('stopped_at'))}, to {found.get('path')}")


def run_to(args: dict[str, Any], reply: dict[str, Any]) -> str:
    ref = args.get("ref", "")
    if reply.get("arrived"):
        out = f"run_to {ref}: arrived"
    elif reply.get("running"):
        out = f"run_to {ref}: still running"
    else:
        out = f"run_to {ref}: stopped at {_at(reply.get('stopped_at'))}"
    control = _block(reply, "control")
    # A COUNT, never `Nx`: `0x` reads as a hex prefix with nothing after it.
    return out + (f", control counted {control.get('hits')}" if control else "")


# ------------------------------------------------------------------------ the states

def state_save(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"state_save {reply.get('name')}: {reply.get('bytes')} bytes, "
            f"{reply.get('program')} {reply.get('time_stamp')}")


def state_load(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"state_load {reply.get('name')}: loaded in {reply.get('waited_s')}s"


def state_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"state_list: {len(reply.get('states') or [])} states in {reply.get('state_dir')}"


def snapshot(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"snapshot: {reply.get('bytes')} bytes at {reply.get('path')}"


# ---------------------------------------------------------------- names for addresses

def symbols_load(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"symbols_load: {reply.get('loaded')} loaded of {reply.get('parsed')} parsed, base "
            f"{reply.get('base')}")


def symbols_find(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if "symbols_total" in reply:    # the by-name question answers a list
        return f"symbols_find {reply.get('query')}: {reply.get('symbols_total')} symbols"
    return f"symbols_find {reply.get('query')}: {reply.get('name')} at {reply.get('linear')}"


# ------------------------------------------------------------------------ declarations

def machine_map(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # THE SHAPE OF THE MACHINE ON THE LINE, from the FULL counts, so a cut section still says
    # how much there is.
    shape = ", ".join(f"{n} {part}" for part, n in _block(reply, "counts").items() if n)
    cut = ", some sections cut (see `counts`)" if reply.get("truncated") else ""
    left = reply.get("omitted") or []
    out = f", left out: {', '.join(left)} (see `omitted`)" if left else ""
    return (f"machine_map ({reply.get('cpu_mode') or 'mode unread'}): "
            f"{shape or 'no list section with rows'}{cut}{out}")


def interrupt_vectors(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # ONE VECTOR: where it points and what holds it. THE TABLE: how many vectors lie in a
    # program's block, by the block's name, which is the hook question. A count is given only
    # when every vector was placed against the MCB chain (the only section with program
    # blocks): a vector with no `linear`, or every one when paged with no page runs read, was
    # never matched, and counting it as in no block would be a guess.
    rows = [r for r in reply.get("vectors") or [] if isinstance(r, dict)]
    sources = _block(reply, "sources")
    runs_unread = reply.get("cpu_mode") == "paged" and "paging" not in sources
    not_placed = [r for r in rows if runs_unread or "linear" not in r]
    if args.get("number") is not None and len(rows) == 1:
        row = rows[0]
        held = next((f"{s} {_named(row[s])}" for s in ("mcbs", "kern", "bios_mem")
                     if isinstance(row.get(s), dict)),
                    "not placed (see `coverage_note`)" if not_placed else "held by no block read")
        return f"interrupt_vectors INT {row.get('number', 0):02X}: {row.get('addr')}, {held}"
    if "mcbs" not in sources:
        return (f"interrupt_vectors: {len(rows)} vectors, no MCB chain read to count program "
                f"blocks in")
    if not_placed:
        return (f"interrupt_vectors: {len(rows)} vectors, {len(not_placed)} not placed, so no "
                f"program block is counted")
    programs: dict[str, int] = {}
    for row in rows:
        block = row.get("mcbs")
        if isinstance(block, dict) and "notes" not in block:
            name = str(block.get("filename"))
            programs[name] = programs.get(name, 0) + 1
    named = ", ".join(f"{n} {k}" for n, k in programs.items())
    return (f"interrupt_vectors: {len(rows)} vectors, {sum(programs.values())} in program blocks"
            + (f" ({named})" if named else ""))


def _named(row: dict[str, Any]) -> str:
    """A holder row in a few words: a block's name and, for a free or DOS block, that note (a
    free block keeps a stale name); a BIOS region's description, or its range when it has
    none."""
    if "mcb_seg" in row:
        note = f" ({row['notes']})" if row.get("notes") else ""
        return f"{row.get('mcb_seg')} {row.get('filename') or ''}".rstrip() + note
    return str(row.get("what") or f"{row.get('start', row.get('seg'))} {row.get('status', '')}")


def breakpoint_at(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"breakpoint_at {args.get('ref', '')}: {reply.get('state')}"


def breakpoint_interrupt(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"breakpoint_interrupt {reply.get('ref', '')}: "
            f"{'stored' if reply.get('stored') else 'kept'}")


def breakpoint_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"breakpoint_list: {len(reply.get('breakpoints') or [])} declared"


def breakpoint_clear(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"breakpoint_clear {args.get('ref') or 'all'}: "
            f"{reply.get('declarations_cleared')} cleared")


def _comment_place(row: object) -> str:
    """Where a comment row lands: its linear address, or its state when it has none now."""
    if not isinstance(row, dict):
        return "?"
    return str(row.get("linear") or row.get("state"))


def comment_add(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"comment_add {args.get('ref', '')}: {_comment_place(reply.get('comment'))}, stored"


def comment_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"comment_list: {reply.get('comments_total')} comment(s)"


def comment_delete(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"comment_delete {args.get('ref', '')}: {_comment_place(reply.get('deleted'))} "
            "deleted")


def comment_save(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"comment_save: {reply.get('comments_total')} comment(s) to {reply.get('dest')}"


def comment_load(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"comment_load: {reply.get('parsed')} read, {reply.get('added_total')} added, "
            f"{reply.get('replaced_total')} replaced")


def watch_add(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"watch_add {args.get('ref', '')}: {reply.get('state')}"


def watch_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"watch_list: {len(reply.get('watches') or [])} declared"


def watch_clear(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"watch_clear {args.get('ref') or 'all'}: "
            f"{reply.get('declarations_cleared')} cleared")


# ------------------------------------------------------------------ input and captures

def send_keys(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"send_keys ({reply.get('route')}): "
            f"{_effect(_block(reply, 'effect'), 'posted, unverified')}")


def send_mouse(args: dict[str, Any], reply: dict[str, Any]) -> str:
    pointer = _block(reply, "pointer")
    screen, mouse = pointer.get("screen"), pointer.get("mouse")
    at = (f"{screen['x']},{screen['y']}" if isinstance(screen, dict) else
          f"{mouse['x']},{mouse['y']} (driver)" if isinstance(mouse, dict) else "unread")
    arrived = "" if reply.get("arrived", True) else ", NOT where asked"
    return (f"send_mouse: pointer at {at}{arrived}; "
            f"{_effect(_block(reply, 'effect'), 'posted, unverified')}")


def captures(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"captures: {len(reply.get('captures') or [])} files"


def palette(args: dict[str, Any], reply: dict[str, Any]) -> str:
    first, count = reply.get("first", 0), reply.get("count", 0)
    colors = reply.get("colors") or []
    which = (f"entry {first} {colors[0]}" if count == 1 and colors
             else f"entries {first} to {first + count - 1}")
    return f"palette: {which} of {reply.get('entries')}; {_picture(reply)}"


def _picture(reply: dict[str, Any]) -> str:
    """The picture's half of a view's line: its size, its scale and whether it is attached."""
    image = reply.get("image") or {}
    shown = "inline" if image.get("inline") else "not inlined"
    return f"{image.get('width')}x{image.get('height')} PNG x{image.get('scale')}, {shown}"


def _region(reply: dict[str, Any]) -> str:
    """The rectangle a reply read, as `wxh at [x, y]`, the media tools' own spelling."""
    crop = reply.get("crop")
    if not (isinstance(crop, list) and len(crop) == 4):
        return "the screen"
    x, y, w, h = crop
    return f"{w}x{h} at [{x}, {y}]"


def screen_view(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if isinstance(reply.get("image"), dict):
        return f"screen_view {reply.get('mode')}: {_region(reply)} pixels; {_picture(reply)}"
    cursor = reply.get("cursor")
    at = f", cursor at {cursor[0]},{cursor[1]}" if isinstance(cursor, list) else ""
    return f"screen_view {reply.get('mode')}: {_region(reply)} text{at}"


def screen_signature(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"screen_signature {reply.get('mode')} {_region(reply)}: {reply.get('signature')}"


def series_capture(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"series_capture: {reply.get('count')} AVI frames {reply.get('first')}.."
            f"{reply.get('last')}, {reply.get('distinct')} distinct, manifest "
            f"{reply.get('manifest')}")


def screen_wait(args: dict[str, Any], reply: dict[str, Any]) -> str:
    point = reply.get("point")
    at = f"{point[0]},{point[1]}" if isinstance(point, list) else "?"
    if reply.get("already"):
        return f"screen_wait {args.get('text')!r}: already on screen at {at}"
    return (f"screen_wait {args.get('text')!r}: found at {at} after {reply.get('polls')} "
            f"retrace(s)")


def capture_frame(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"capture_frame {args.get('at')}: {reply.get('bytes')} bytes to "
            f"{reply.get('path')}")


# ---------------------------------------------------------------------- the sequences

def perform_export(args: dict[str, Any], reply: dict[str, Any]) -> str:
    cut = f", cut at call {reply['cut']['call']}" if reply.get("cut") else ""
    return (f"perform_export: {reply['steps']} steps, {reply['checks']} checks, "
            f"{reply['dropped_total']} dropped{cut} to {reply['path']}")


def perform(args: dict[str, Any], reply: dict[str, Any]) -> str:
    steps = reply.get("steps_total", len(args.get("steps") or []))
    return f"perform: {reply.get('completed')} of {steps} steps"


def drive(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"drive: {_effect(_block(reply, 'verify'), 'no expectation')}"
