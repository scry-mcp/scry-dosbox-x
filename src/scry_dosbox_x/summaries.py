"""THE ONE LINE EVERY REPLY OPENS WITH, one function per tool.

The MCP client paints a call's tool name, its arguments and its reply and nothing else, so two
calls of one tool are told apart only by what is IN the reply: the `summary`, written for a
person, in the tool's own words. Under `perform(summaries=True)` it heads the compact row an
earlier step is cut to.

EACH TOOL NAMES ITS OWN at registration (`server.tool(..., summary=...)`), and the
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

from scry_core import promote as core_promote
from scry_core import prose, screen_map, session_block, stop_wait
from scry_core import reply_contract as contract

from scry_dosbox_x import running

#: A tool's summary: the call's arguments (defaults applied) and its reply, to one line.
Summary = Callable[[dict[str, Any], dict[str, Any]], str]



#: A refusal's line, and the cut of its prose, are scry-core's, alike on both servers.
clipped, refusal = prose.clipped, prose.refusal


def _said(n: object, noun: str, plural: str | None = None) -> str:
    """A count beside its noun in the number it has (`scry_core.prose.counted`); a count a reply
    did not carry is shown as it came, with the plural."""
    if isinstance(n, int) and not isinstance(n, bool):
        return prose.counted(n, noun, plural)
    return f"{n} {plural or noun + 's'}"




def _at(pc: Any) -> str:
    """A stop's `pc` as a summary paints it: `?` when it is unavailable."""
    return pc if isinstance(pc, str) else "?"


def _block(reply: dict[str, Any], key: str) -> dict[str, Any]:
    value = reply.get(key)
    return value if isinstance(value, dict) else {}


def _effect(verify: dict[str, Any], none: str) -> str:
    """What an input's check found: seen, not seen, or `none` when no check ran."""
    return ("effect not checked" if verify.get("available") is False else
            "effect seen" if verify.get("seen") else
            f"effect not seen ({verify['verdict']})" if "verdict" in verify else
            "effect not seen" if verify.get("checked") else none)


# ------------------------------------------------------------------------------ session

def build_check(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"build_check: {reply.get('binary')} ({reply.get('binary_origin')}), debugger "
            f"{reply.get('debugger')}, heavy_debug {reply.get('heavy_debug')}")


def start(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # with a `plan` the start facts sit under `start` and the top level is the account
    facts = _block(reply, "start") or reply
    plan = ""
    if reply.get("ran") is not None:
        planned = _said(len(args.get("plan") or []), "step")
        plan = f", then {reply.get('steps_completed')} of {planned}"
    watched = "shared" if facts.get("shared") else "headless"
    return (f"start {Path(str(args.get('conf', ''))).name}: {watched} on "
            f"{facts.get('binary')} ({facts.get('binary_origin')}), debugger answered after "
            f"{facts.get('ready_after_s')}s{plan}")


def _word(value: Any) -> str:
    """A field a summary names, or "" when it is unavailable: an unavailable datum is a dict,
    and a dict is truthy, so it would be painted as its repr."""
    return value if isinstance(value, str) else ""


def status(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # THE REPLY'S OWN FACTS, never its block: the summary is read off the body's reply, before
    # the block is added. `declarations` is counted on every session and on none without.
    if "declarations" not in reply:
        return session_block.NO_SESSION_STATUS
    why = reply.get("pc", {}).get("why") if isinstance(reply.get("pc"), dict) else None
    if why == running.PC_GONE_WHY:
        return "status: DOSBox-X has exited, `close` it"
    released = why in (running.PC_RUNNING_WHY, running.PC_UNKNOWN_WHY)
    moved = (", the executable moved since its table was checked"
             if reply.get("image_changed_on_disk") is True else "")
    return f"status: alive, {'running' if released else 'stopped'}{moved}"


def close(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if not reply.get("closed"):
        return session_block.NO_SESSION_CLOSE
    code = reply.get("exit_code")
    said = (f"exit code {code}" if not isinstance(code, dict)
            else f"no exit code: {code.get('why')}")
    return f"close: {reply.get('ended_by')}, {said}"


# ------------------------------------------------------------------------ the guest's log

def log(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if "calls" in reply:
        return (f"log dos /{args.get('pattern', '')}/: {len(reply.get('calls') or [])} of "
                f"{_said(reply.get('lines_total'), 'call')}")
    return (f"log {args.get('channel', '')} /{args.get('pattern', '')}/: "
            f"{len(reply.get('lines') or [])} of {_said(reply.get('lines_total'), 'line')}")


def log_wait(args: dict[str, Any], reply: dict[str, Any]) -> str:
    head = f"log_wait {args.get('channel', '')} /{args.get('pattern', '')}/"
    if reply.get("verdict") == contract.TIMEOUT:
        return (f"{head}: TIMEOUT after {reply.get('waited_s')}s, "
                f"{_said(reply.get('arrived_during'), 'line')} arrived")
    when = "already in the log" if reply.get("already") else f"after {reply.get('waited_s')}s"
    return f"{head}: matched {when}"


# ------------------------------------------------------------- reading and writing

def registers(args: dict[str, Any], reply: dict[str, Any]) -> str:
    old = " (last stop)" if reply.get("superseded") else ""
    return f"registers{old}: {_said(len(_block(reply, 'regs')), 'register')}"


def read_memory(args: dict[str, Any], reply: dict[str, Any]) -> str:
    at = _at(reply.get("seg_off"))
    read = _said(len(str(reply.get("hex") or "")) // 2, "byte")
    shown = prose.hex_clipped(str(reply.get("hex") or ""))
    return f"read_memory {args.get('ref', '')}: {read} at {at}" + (f": {shown}" if shown else "")


def disassemble(args: dict[str, Any], reply: dict[str, Any]) -> str:
    at = _at(reply.get("seg_off"))
    lines = _said(len(reply.get("lines") or []), "line")
    return f"disassemble {args.get('ref', '')}: {lines} at {at}, {reply.get('code_bits')}-bit"


def call_stack(args: dict[str, Any], reply: dict[str, Any]) -> str:
    calls = reply.get("calls") or []
    first = calls[0] if calls and isinstance(calls[0], dict) else {}
    return (f"call_stack: {_said(len(calls), 'call')}, innermost "
            f"{_word(first.get('symbol')) or first.get('seg_off', '?')}, heuristic")


def memdump(args: dict[str, Any], reply: dict[str, Any]) -> str:
    dumped = _said(reply.get("bytes"), "byte")
    return f"memdump {args.get('ref', '')}: {dumped} to {reply.get('path')}"


def find(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"find {args.get('ref', '')}: {_said(reply.get('hits_total'), 'hit')} of "
            f"{args.get('data_hex')} in {_said(reply.get('length'), 'byte')}")


def start_scan(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"{args.get('ref', '')}, {reply.get('hits_total')} cells of "
            f"{_said(reply.get('cell_bytes'), 'byte')}")


def filter_scan(args: dict[str, Any], reply: dict[str, Any]) -> str:
    value = args.get("value")
    what = (args.get("operator") or "=") + ("" if value is None else f" {value}")
    return f"{what}, {_said(reply.get('hits_total'), 'survivor')}" + (
        ", scan closed" if reply.get("closed") else "") + (
        _listed(reply) if reply.get("truncated") else "")


def _listed(reply: dict[str, Any]) -> str:
    """How much of a cut survivor list a filter's reply holds."""
    shown = len(reply.get("hits") or [])
    return f", the first {shown} listed" if shown else ", none listed (`note` says why)"


def clear_scan(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return "cleared" if reply.get("cleared") else "nothing was open"


def debug(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"debug {args.get('command', '')!r}: {_said(reply.get('output_chars'), 'char')}"


def set_register(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"set_register {args.get('name', '')} = {args.get('value')}, verified "
            f"{reply.get('verified')}")


def write(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"write {args.get('ref', '')}: {_said(reply.get('bytes_written'), 'byte')}, verified "
            f"{reply.get('verified')}")


# ------------------------------------------------------------ advancing the machine

def resume(args: dict[str, Any], reply: dict[str, Any]) -> str:
    verdict = f"{reply['verdict']}, " if "verdict" in reply else ""
    where = (f"stopped at {_at(reply.get('pc'))}" if "pc" in reply
             else "running")
    return f"resume: {verdict}{where}"


def stop(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if runs := reply.get("runs_to_protected"):
        return f"stop: {runs} short runs, at {_at(reply.get('pc'))}"
    if not reply.get("interrupted"):
        return "stop: already stopped"
    return f"stop: {reply.get('via')}, at {_at(reply.get('pc'))}"


def step(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if "pc" in reply:
        where = f"at {_at(reply['pc'])}"
    elif _block(reply, "session").get("running"):
        where = f"running from {_at(reply.get('after'))}"
    else:
        where = f"at {_at(reply.get('after'))}, its survey cut"
    return f"step {args.get('count', 1)}: {reply.get('instructions_completed')} done, {where}"


def run_for(args: dict[str, Any], reply: dict[str, Any]) -> str:
    where = f"at {_at(reply.get('pc'))}"
    asked = (f"{args.get('milliseconds')} ms" if args.get("milliseconds")
             else f"{_said(args.get('frames'), 'frame')}")
    return f"run_for {asked}: {reply.get('verdict')}, {_said(reply.get('polls'), 'poll')}, {where}"


def trace(args: dict[str, Any], reply: dict[str, Any]) -> str:
    found = _block(reply, "trace")
    places = _said(found.get("addresses"), "address", "addresses")
    return (f"trace {args.get('instructions')} {args.get('shape')}: {reply.get('verdict')}, "
            f"{found.get('instructions')} executed at {places}, at "
            f"{_at(reply.get('pc'))}, to {found.get('path')}")


def run_to(args: dict[str, Any], reply: dict[str, Any]) -> str:
    out = (f"run_to {screen_map.run_to_named(args, reply)}: {reply.get('verdict', 'refused')} at "
           f"{_at(reply.get('pc'))}")
    # A COUNT, never `Nx`: `0x` reads as a hex prefix with nothing after it.
    return out + (f", control counted {reply['control_hits']}" if "control_hits" in reply
                  else "")


# ------------------------------------------------------------------------ the states

def save_state(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"{reply.get('name')}, {_said(reply.get('bytes'), 'byte')}, "
            f"{reply.get('program')} {reply.get('saved_at')}")


def load_state(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{reply.get('name')}, loaded"


def state_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    states = _said(len(reply.get("states") or []), "state")
    return f"state_list: {states} in {reply.get('state_dir')}"


def snapshot(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"snapshot: {_said(reply.get('bytes'), 'byte')} at {reply.get('path')}"


def _recording(tool: str, args: dict[str, Any], reply: dict[str, Any], got: str) -> str:
    head = f"{tool} {_said(args.get('frames'), 'frame')}: {reply.get('verdict')}"
    path = reply.get("path")
    if reply.get("ended") is False:
        return f"{head}, still recording until `close`"
    return f"{head}, {got} at {path}" if isinstance(path, str) else f"{head}, no file"


def record(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return _recording("record", args, reply, _said(reply.get("avi_frames"), "frame"))


def audio_record(args: dict[str, Any], reply: dict[str, Any]) -> str:
    kind = reply.get("kind") or args.get("kind", "wav")
    got = (f"{_said(reply.get('samples'), 'sample')} at {reply.get('sample_rate_hz')} Hz"
           + (", silent" if reply.get("sample_min") == reply.get("sample_max") else "")
           if kind == "wav" else _said(reply.get("bytes"), "byte"))
    return _recording(f"audio_record {kind}", args, reply, got)


# ---------------------------------------------------------------- names for addresses

def symbols_load(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # A LOAD WITH NOTHING TO CHECK WOULD READ LIKE A PROVED ONE: the line says which of the
    # two it is, and the full `why` stays in the reply's `checked`.
    line = (f"symbols_load: {reply.get('loaded')} loaded of {reply.get('parsed')} parsed, base "
            f"{reply.get('base')}")
    held = reply.get("debugger_holds")
    if isinstance(held, int) and not isinstance(held, bool):
        line += f", the debugger holds {_said(held, 'row')} (`LV` appends)"
    checked = _block(reply, "checked")
    if checked.get("available") is False:
        return f"{line}, not checked against a build: {clipped(str(checked.get('why', '')))}"
    against = checked.get("against")
    return (f"{line}, checked against {Path(against).name}" if isinstance(against, str) else line)


def symbols_find(args: dict[str, Any], reply: dict[str, Any]) -> str:
    if "symbols_total" in reply:    # the by-name question answers a list
        return f"symbols_find {reply.get('query')}: {_said(reply.get('symbols_total'), 'symbol')}"
    return f"symbols_find {reply.get('query')}: {reply.get('name')} at {reply.get('addr')}"


# ------------------------------------------------------------------------ declarations

def machine_map(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # THE SHAPE OF THE MACHINE ON THE LINE, from the FULL counts, so a cut section still says
    # how much there is.
    shape = ", ".join(f"{n} {part}" for part, n in _block(reply, "counts").items() if n)
    cut = ", some sections cut (see `counts`)" if reply.get("truncated") else ""
    left = reply.get("omitted") or []
    out = f", left out: {', '.join(left)} (see `omitted`)" if left else ""
    return (f"machine_map ({_word(reply.get('cpu_mode')) or 'mode unread'}): "
            f"{shape or 'no list section with rows'}{cut}{out}")


def interrupt_vectors(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # ONE VECTOR: where it points and what holds it. THE TABLE: how many vectors lie in a
    # program's block, by the block's name, which is the hook question. A count is given only
    # when every vector was placed against the MCB chain (the only section with program
    # blocks): a vector with no `addr`, or every one when paged with no page runs read, was
    # never matched, and counting it as in no block would be a guess.
    rows = [r for r in reply.get("vectors") or [] if isinstance(r, dict)]
    sources = _block(reply, "sources")
    runs_unread = reply.get("cpu_mode") == "paged" and "paging" not in sources
    not_placed = [r for r in rows if runs_unread or "addr" not in r]
    if args.get("number") is not None and len(rows) == 1:
        row = rows[0]
        held = next((f"{s} {_named(row[s])}" for s in ("mcbs", "kern", "bios_mem")
                     if isinstance(row.get(s), dict)),
                    "not placed (see `coverage_note`)" if not_placed else "held by no block read")
        return f"interrupt_vectors INT {row.get('number', 0):02X}: {row.get('seg_off')}, {held}"
    vectors = _said(len(rows), "vector")
    if "mcbs" not in sources:
        return f"interrupt_vectors: {vectors}, no MCB chain read to count program blocks in"
    if not_placed:
        return (f"interrupt_vectors: {vectors}, {len(not_placed)} not placed, so no program "
                "block is counted")
    programs: dict[str, int] = {}
    for row in rows:
        block = row.get("mcbs")
        if isinstance(block, dict) and "notes" not in block:
            name = str(block.get("filename"))
            programs[name] = programs.get(name, 0) + 1
    named = ", ".join(f"{n} {k}" for n, k in programs.items())
    return (f"interrupt_vectors: {vectors}, {sum(programs.values())} in program blocks"
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


def regpoint_add(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"regpoint_add {reply.get('ref', '')}: {reply.get('state')}"


#: Each kind's reply field, in the order a list of every kind names them.
DECLARATION_ROWS = {"breakpoint": "breakpoints", "regpoint": "regpoints", "watch": "watches"}


def declaration_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    kind = f" {args['kind']}" if args.get("kind") else ""
    return f"declaration_list{kind}: " + ", ".join(
        f"{len(reply[key])} {key} declared" for key in DECLARATION_ROWS.values() if key in reply)


def declaration_clear(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"declaration_clear {args.get('kind')} {args.get('ref') or 'all'}: "
            f"{reply.get('declarations_cleared')} cleared")


def _comment_place(row: object) -> str:
    """Where a comment row lands: its linear address, or its state when it has none now."""
    if not isinstance(row, dict):
        return "?"
    return str(row.get("addr") or row.get("state"))


def add_comment(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{args.get('ref', '')} at {_comment_place(reply.get('comment'))}, stored"


def comment_list(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"comment_list: {_said(reply.get('comments_total'), 'comment')}"


def delete_comment(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{args.get('ref', '')} at {_comment_place(reply.get('deleted'))} deleted"


def save_comments(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{_said(reply.get('comments_total'), 'comment')} to {reply.get('path')}"


def load_comments(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"{reply.get('parsed')} read, {reply.get('added')} added, "
            f"{reply.get('replaced_total')} replaced")


def watch_add(args: dict[str, Any], reply: dict[str, Any]) -> str:
    entry = str(reply.get("entry", ""))
    if entry.startswith("TAP "):
        return (f"watch_add {args.get('ref', '')}: {reply.get('mode')} watch armed as {entry}, "
                f"{_said(reply.get('length'), 'byte')}")
    if entry.startswith("FM "):
        return (f"watch_add {args.get('ref', '')}: freeze armed, "
                f"{_said(reply.get('length'), 'byte')} pinned at {reply.get('frozen_hex')}")
    return f"watch_add {args.get('ref', '')}: {reply.get('state')}"


# ------------------------------------------------------------------ input and captures

def send_keys(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"send_keys ({reply.get('route')}): "
            f"{_effect(_block(reply, 'verify'), 'posted, unverified')}{_parked(reply)}")


def _parked(reply: dict[str, Any]) -> str:
    """A post to a stopped machine: the retraces it ran and the frame it left it in."""
    if "polls" not in reply:
        return ""
    frame = reply.get("frame")
    return f", {_said(reply['polls'], 'retrace')}" + (
        f" to frame {frame}" if isinstance(frame, int) else "")


def send_mouse(args: dict[str, Any], reply: dict[str, Any]) -> str:
    pointer = _block(reply, "pointer")
    screen, mouse = pointer.get("screen"), pointer.get("mouse")
    at = (f"{screen['x']},{screen['y']}" if isinstance(screen, dict) and "x" in screen else
          f"{mouse['x']},{mouse['y']} (driver)" if isinstance(mouse, dict) else "unread")
    arrived = ("" if reply.get("arrived", reply.get("driver_arrived", True))
               else ", NOT where asked")
    if "driver_arrived" in reply:
        arrived += ", program's own pointer not read"
    pressed = "" if args.get("button") or reply.get("button") else "; no button pressed"
    program = pointer.get("program")
    widened = program.get("range_widened") if isinstance(program, dict) else None
    if isinstance(widened, dict):
        arrived += f", driver range widened to {widened['x']} x {widened['y']}"
    return (f"send_mouse: pointer at {at}{arrived}{pressed}; "
            f"{_effect(_block(reply, 'verify'), 'posted, unverified')}{_parked(reply)}")


def captures(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"captures: {_said(len(reply.get('captures') or []), 'file')}"


def palette(args: dict[str, Any], reply: dict[str, Any]) -> str:
    first, count = reply.get("first", 0), reply.get("count", 0)
    colors = reply.get("colors") or []
    which = (f"entry {first} {colors[0]}" if count == 1 and colors
             else f"entries {first} to {first + count - 1}")
    return f"palette: {which} of {reply.get('entries')}; {prose.picture(reply)}"



def _region(reply: dict[str, Any]) -> str:
    """The rectangle a reply read, as `wxh at [x, y]`, the media tools' own spelling."""
    crop = reply.get("crop")
    if not (isinstance(crop, list) and len(crop) == 4):
        return "the screen"
    x, y, w, h = crop
    return f"{w}x{h} at [{x}, {y}]"


def screen_view(args: dict[str, Any], reply: dict[str, Any]) -> str:
    mode = reply.get("mode")
    if mode == "histogram":
        return (f"screen_view histogram {reply.get('vga_mode')}: {reply.get('pens_used')} of "
                f"{_said(reply.get('entries'), 'pen')} used in {_region(reply)}")
    if mode == "isolate":
        return (f"screen_view isolate {reply.get('vga_mode')}: "
                f"{_said(reply.get('pixels'), 'pixel')} of pens {reply.get('pens')} in "
                f"{_region(reply)}; {prose.picture(reply)}")
    if mode == "pixel":
        return (f"screen_view pixel {reply.get('vga_mode')}: ({reply.get('x')}, {reply.get('y')}) "
                f"is pen {int(reply.get('pen') or 0):#x} {reply.get('color')}; "
                f"{prose.picture(reply)}")
    if isinstance(reply.get("image"), dict):
        return (f"screen_view {reply.get('vga_mode')}: {_region(reply)} pixels; "
                f"{prose.picture(reply)}")
    cursor = reply.get("cursor")
    at = f", cursor at {cursor[0]},{cursor[1]}" if isinstance(cursor, list) else ""
    return f"screen_view {reply.get('vga_mode')}: {_region(reply)} text{at}"


def screen_signature(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"screen_signature {reply.get('vga_mode')} {_region(reply)}: {reply.get('signature')}"


# The screen maps' and the promotion's lines are scry-core's, alike on both servers.
screen_map_find = screen_map.find_line
promote = core_promote.promote_line


def series_capture(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"series_capture: {reply.get('count')} AVI frames {reply.get('first')}.."
            f"{reply.get('last')}, {reply.get('distinct')} distinct, manifest "
            f"{reply.get('manifest')}")


def screen_wait(args: dict[str, Any], reply: dict[str, Any]) -> str:
    predicate = str(reply.get("predicate") or "text")
    asked = args.get(predicate) or ""
    said = (repr(asked) if predicate == "text" else "a changed screen"
            if predicate == "changed" else f"screen {asked!r}" if predicate == "screen"
            else f"a {asked} palette")
    point = reply.get("point")
    at = f"{point[0]},{point[1]}" if isinstance(point, list) else "?"
    after = stop_wait.summary_after(reply) or \
        f"after {prose.counted(int(reply.get('polls') or 0), 'retrace')}"
    if reply.get("verdict") == contract.TIMEOUT:
        return f"screen_wait {said}: TIMEOUT {after}"
    if reply.get("already"):
        where = f" at {at}" if isinstance(point, list) else ""
        return f"screen_wait {said}: already on screen{where}"
    if predicate != "text":
        return f"screen_wait {said}: found {after}"
    return f"screen_wait {said}: found at {at} {after}"


def capture_frame(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return (f"capture_frame {reply.get('frame')}: {_said(reply.get('bytes'), 'byte')} to "
            f"{reply.get('path')}")


# ---------------------------------------------------------------------- the sequences

def perform(args: dict[str, Any], reply: dict[str, Any]) -> str:
    # THE COUNT AND THE TAIL ON THE LINE: under `summaries=True` a nested list's line is all
    # its caller keeps, and `ok` alone tells a list that ended stopped from one still running.
    steps = reply.get("steps_total", len(args.get("steps") or []))
    done = f"perform: {reply.get('steps_completed')} of {_said(steps, 'step')}"
    stopped = reply.get("stopped")
    if isinstance(stopped, dict):
        seq = stopped.get("stop_seq")
        return f"{done}, stopped" + (f" (stop {seq})" if seq is not None else "")
    if reply.get("still_running"):
        return f"{done}, still running"
    if "until_frame" in reply:
        reached = reply.get("frame_reached")
        done += (f", frame {reached} of {reply['until_frame']}" if isinstance(reached, int)
                 else f", no frame read of {reply['until_frame']}")
    return f"{done}, {reply['verdict']}" if "verdict" in reply else done


def drive(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"drive: {_effect(_block(reply, 'verify'), 'no expectation')}"


def port_read(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{reply.get('bits')}-bit read of {reply.get('port')}: {reply.get('value')}"


def port_write(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"{reply.get('bits')}-bit write of {reply.get('value')} to {reply.get('port')}"


def pic_read(args: dict[str, Any], reply: dict[str, Any]) -> str:
    irqs = [r for r in reply.get("irqs") or [] if isinstance(r, dict)]
    masked = [str(r.get("irq")) for r in irqs if r.get("masked")]
    asked = [str(r.get("irq")) for r in irqs if r.get("requested")]
    return (f"{_said(len(reply.get('controllers') or []), 'controller')}, masked "
            f"{', '.join(masked) or 'none'}, requested {', '.join(asked) or 'none'}")


def pic_action(args: dict[str, Any], reply: dict[str, Any]) -> str:
    found = reply.get("line")
    line: dict[str, Any] = found if isinstance(found, dict) else {}
    held = [word for word, key in (("masked", "masked"), ("requested", "requested"),
                                   ("in service", "in_service")) if line.get(key)]
    return (f"IRQ {reply.get('irq')} {reply.get('method')} done; "
            f"its line reads {', '.join(held) or 'clear'}")


def a20(args: dict[str, Any], reply: dict[str, Any]) -> str:
    return f"the A20 gate is {'on' if reply.get('enabled') else 'off'}"


def guest_file(args: dict[str, Any], reply: dict[str, Any]) -> str:
    size = f", {_said(reply.get('bytes'), 'byte')}" if "bytes" in reply else ""
    return f"guest_file {args.get('path', '')}: {reply.get('state')}{size}"
