"""Sections A, B, C, H and I of the live matrix: the package's own guest, which needs nothing from
anybody, driven in every machine state, at every argument edge, and across the calls that share
state.

WHERE EACH EXPECTATION COMES FROM is written beside it, as the cell's source: a `REFERENCE.md`
section, a tool's docstring, the refusal table in `scry_core.reply_contract`, or a known answer the
guest establishes (`probe.asm`: a `.COM` at offset 0x100 that writes a stamped line to port
0xE9 every few seconds and never exits; its bytes on disk say where its code and data are).
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from matrix_common import (
    CLOSED_BY,
    GUEST,
    NEVER_RUNS_CONTROL,
    NEVER_RUNS_STOPPER,
    NEVER_RUNS_TARGET,
    NO_SUCH_HOME_WHY,
    PKG,
    PROBE_CONF,
    SESSION_S,
    M,
    alive,
    boot,
    cells,
    clock_moved,
    close_whatever,
    conf_with_stub,
    conf_without_launch,
    ds,
    exec_of,
    free_port,
    hexint,
    into_dos,
    judged,
    must,
    no_session,
    note_spawn,
    ok,
    read_bytes,
    refused,
    reg_ref,
    release_running,
    resume_until,
    said,
    server,
    start_call,
)
from matrix_ledger import Cell

import dosbox_mcp

PROBE_COM = GUEST / "probe.com"
#: A Borland real-mode map this package builds and commits: symbols to load on a guest that has
#: none of its own. The name looked up is one the file declares.
FIXTURE_MAP = PKG / "tests" / "fixtures" / "borland-tlink16" / "MAPDEMO.MAP"
FIXTURE_SYMBOL = "MAP_DATA_SYMBOL"

#: Conventional memory nothing on the probe's machine loads into: a place to write, dump and
#: scan whose contents the matrix itself decides.
SCRATCH_SEG = 0x8000


class Probe:
    """Where the probe guest's own code and data sit, from its file: a `.COM` loads at offset
    0x100 of its segment, so a byte at file offset N is at `seg:0x100+N`. Each pattern is looked
    up once and has to occur where the source puts it."""

    def __init__(self, seg: int) -> None:
        body = PROBE_COM.read_bytes()
        self.seg = seg
        # `emit`: lodsb / test al,al / jz  -- writes each line to port 0xE9, a CHARACTER per pass.
        self.emit = 0x100 + _once(body, bytes.fromhex("AC84C074"))
        # `.s1` and `.spin`: the inner `loop $` of the settle before the first line and of the
        # pause between lines, where the guest spends nearly all of its time.
        first = body.index(bytes.fromhex("E2FE4B75"))
        self.settle = 0x100 + first
        self.spin = 0x100 + body.index(bytes.fromhex("E2FE4B75"), first + 1)
        # `cnt`: the five ASCII digits of the odometer, after the `[+ ` of the tick template.
        self.cnt = 0x100 + _once(body, b"[+ 00000.") + 3
        # `.pause`: `mov bx, 700`, reached ONCE per line, after it is written.
        self.pause = 0x100 + _once(body, bytes.fromhex("BBBC02B90000"))

    def at(self, off: int) -> str:
        return f"{self.seg:04X}:{off:04X}"


def _once(body: bytes, pattern: bytes) -> int:
    at = body.index(pattern)
    if body.find(pattern, at + 1) != -1:
        raise RuntimeError(f"{pattern.hex()} occurs more than once in {PROBE_COM.name}")
    return at


def into_probe() -> Probe:
    """From a stop in DOS to a stop INSIDE the probe, and where it is.

    Two waypoints, each checked against a known answer: the EXEC that loads `PROBE.COM` (the
    conf's own autoexec line), then the timer, since the probe calls no interrupt of its own. An
    INT 8 breakpoint stops at the HANDLER's entry, so the instruction the tick interrupted is
    the return address the CPU pushed at SS:SP (IP, then CS); the first stop whose interrupted
    segment holds `probe.com`'s own first bytes at 0x100 is inside the probe."""
    exec_of("PROBE", limit=8)
    head = PROBE_COM.read_bytes()[:16]
    must(M.call(server.breakpoint_interrupt, number=0x08), "arming INT 8")
    seg = 0

    def in_probe(regs: dict[str, Any]) -> bool:
        nonlocal seg
        seg = int.from_bytes(read_bytes(reg_ref(regs, "SS", "ESP"), 4)[2:], "little")
        return read_bytes(f"{seg:04X}:0100", 16) == head

    resume_until(in_probe, "a timer tick inside the probe", 40, seconds=10)
    must(M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 08"), "clearing INT 8")
    return Probe(seg)


# ================================================================ A: every tool, every state
#
# Four states: no session yet, stopped inside the guest, running headless with a stopper that
# never fires, and after `close`. Each tool is called with arguments valid for it, so the state
# is the only variable, and every reply's session block has to agree with the machine.

STATES = ("none", "stopped", "running", "closed")
#: The registered tools, a fold by each of its methods (`_folded`), set below `_STOPPED_ORDER`.
REGISTERED = list(dosbox_mcp.registered_tools())


def _folded(name: str) -> tuple[str, dict[str, Any]]:
    """A probe name, `<tool>` or a fold's `<tool> <value>`, as the tool and its selector: the
    value is the fold's `kind` for the declarations, its `method` otherwise."""
    tool, _, value = name.partition(" ")
    return tool, ({"kind" if tool.startswith("declaration_") else "method": value}
                  if value else {})
SCRATCH = f"{SCRATCH_SEG:04X}"
REF_DOC = "REFERENCE.md, "

#: Tools that answer with no session, and what they answer (docstrings).
_WITHOUT_SESSION: dict[str, tuple[Callable[[dict[str, Any]], bool], str]] = {
    "build_check": (lambda r: ok(r) and r.get("debugger") is True and no_session(r),
                    "build_check docstring: about the build, answers with no session"),
    "status": (lambda r: ok(r) and no_session(r),
               "status docstring: `alive: false` when there is none, under status ok"),
    "close": (lambda r: ok(r) and r.get("closed") is False and r.get("ended_by") == "none",
              "close docstring: `ended_by` none, nothing to close"),
    "start": (lambda r: ok(r) and alive(r), "start docstring: opens one session, parked"),
}

_WINDOWED = ("snapshot",)
_NEEDS_STOP = ("registers", "read_memory", "disassemble", "call_stack", "memdump", "find",
               "scan start",
               "scan filter", "scan clear", "debug", "set_register", "write", "step", "run_to",
               "run_for", "trace", "record", "audio_record",
               "resume", "machine_map", "interrupt_vectors", "palette", "screen_view",
               "screen_signature", "screen_wait", "comment_write add", "comment_write delete",
               "comment_write load", "map_write add", "map_find")
_NO_CAPTURE = ("capture_frame", "series_capture")
#: A directory no host has, spelled absolute on this one.
_ABSENT = Path(Path.cwd().anchor) / "nonexistent"
#: The media file tools read files and no machine, so they answer in every state alike; each is
#: asked about files that are not there, which its judge refuses by name.
MEDIA_ABSENT: dict[str, dict[str, Any]] = {
    "image_compare image": {"a": str(_ABSENT / "a.png"), "b": str(_ABSENT / "b.png")},
    "image_compare series": {"a": str(_ABSENT / "a.json"), "b": str(_ABSENT / "b.json")},
    "image_compare region": {"manifest": str(_ABSENT / "m.json")},
    "image_compare golden": {"manifest": str(_ABSENT / "m.json"),
                             "checksums": str(_ABSENT / "g.sha256")},
}


class Ctx:
    """What the valid arguments of a state depend on: where the probe is, and the value a
    register already holds (so forcing it back changes nothing the guest depends on)."""
    probe: Probe | None = None
    eax: int = 0


def _args(tool: str, state: str) -> dict[str, Any]:
    p = Ctx.probe
    control = p.at(p.spin) if p else NEVER_RUNS_CONTROL
    table: dict[str, dict[str, Any]] = {
        "build_check": {}, "status": {}, "close": {}, "registers": {}, "scan clear": {},
        "resume": {}, "stop": {}, "state_list": {}, "declaration_list breakpoint": {},
                                        "declaration_list watch": {},
        "captures": {},
        "start": {"conf": str(PROBE_CONF), "cwd": str(GUEST), "session_seconds": SESSION_S,
                  "logfile": M.fresh(".log"), "state_dir": M.fresh("-save")},
        "log": {"pattern": ".", "channel": "guest" if state == "running" else "emulator"},
        "log_wait": {"pattern": r"PROBE" if state == "running" else r"MATRIX_NEVER_LOGGED",
                     "channel": "guest", "seconds": 10},
        "read_memory": {"ref": "0000:0020", "length": 4},
        "disassemble": {"ref": "0000:0020", "length": 4},
        "call_stack": {},
        "memdump": {"ref": "0000:0400", "length": 16, "dest": M.fresh(".bin")},
        "find": {"data_hex": "00", "ref": f"{SCRATCH}:0000", "length": 16},
        "scan start": {"ref": f"{SCRATCH}:0000", "length": 16},
        "scan filter": {"operator": "="},
        "debug": {"command": "BPLIST"},
        "machine_map": {},
        "interrupt_vectors": {"number": 0x21},
        "palette": {"first": 0, "count": 2},
        "screen_view": {},
        "screen_signature": {},
        "screen_wait": {"text": "C:\\>PROBE.COM", "seconds": 10},
        "set_register": {"name": "eax", "value": Ctx.eax},
        "write": {"ref": f"{SCRATCH}:0100", "data_hex": "A55A"},
        "step": {"count": 1},
        "run_to": {"ref": NEVER_RUNS_TARGET, "seconds": 3, "control": control},
        "run_for": {"frames": 1},
        "trace": {"instructions": 16, "shape": "cs_ip", "dest": M.fresh(".trace"), "seconds": 30},
        "state_write save": {"name": f"matrix_a_{state}", "seconds": 10},
        # the stopped cells save before they load; the running ones meet the load first, and
        # load the state the stopped cells saved
        "state_write load": {"name": "matrix_a_stopped", "seconds": 10},
        "snapshot": {"dest": M.fresh(".png"), "seconds": 10},
        "record": {"frames": 2, "dest": M.fresh(".avi"), "seconds": 30},
        "audio_record": {"frames": 2, "dest": M.fresh(".wav"), "seconds": 30},
        "breakpoint_interrupt": {"number": 0x21, "ah": 0x4C},
        "symbols_load": {"path": str(FIXTURE_MAP), "base": "8000"},
        "symbols_find": {"name": FIXTURE_SYMBOL},
        "breakpoint_at": {"ref": "0000:0002"},
        "declaration_clear breakpoint": {"ref": "0000:0002"},
        "regpoint_add": {"condition": "AX==4C00"},
        "declaration_list regpoint": {},
        "declaration_clear regpoint": {"ref": "AX==4C00"},
        "watch_add": {"ref": "0040:006C", "mode": "show", "length": 4},
        "declaration_clear watch": {"ref": "0040:006C"},
        "send_keys": {"keys": ["a"]},
        "send_mouse": {"button": "left"},
        "capture_frame": {"frame": 0, "dest": M.fresh(".png")},
        "series_capture": {"first": 0, "last": 1},
        **MEDIA_ABSENT,
        "perform": {"steps": [{"op": "status"}]},
        "perform_export": {"dest": M.fresh(".json")},
        "drive": {"act": [{"op": "status"}]},
        "comment_write add": {"ref": COMMENT_REF, "text": "matrix A"},
        "comment_list": {},
        "comment_write delete": {"ref": COMMENT_REF},
        "comment_write save": {"dest": M.fresh(".comments.tsv")},
        "comment_write load": {"path": _header_only()},
        "map_write load": {"path": str(_ABSENT / "probe.scry-map.json")},
        "map_write add": {"screen": f"probe_{state}", "match": [[0, 0, 8, 1]]},
        "map_find": {},
        "map_write save": {"dest": M.fresh(f"-{state}.scry-map.json"), "overwrite": True},
    }
    return table[tool]


#: Where section A puts its one comment, inside the probe's scratch segment.
COMMENT_REF = f"{SCRATCH_SEG:04X}:0100"


def _header_only() -> str:
    """A comment file holding no comment: what loads with nothing to add, whatever the store."""
    path = Path(M.fresh(".comments.tsv"))
    path.write_text("# comments v1: ref\tcpu\tcreated_at\ttext\n", encoding="utf-8")
    return str(path)



def _exported(r: dict[str, Any]) -> bool:
    """A `perform_export` reply that wrote what it says: its file is `perform`'s own document,
    holding the steps it counts."""
    try:
        doc = json.loads(Path(str(r.get("path"))).read_text())
    except (OSError, ValueError):
        return False
    return (isinstance(r.get("steps"), int) and r["steps"] >= 1
            and isinstance(doc, dict) and len(doc.get("steps") or []) == r["steps"])


#: The sequences and the export answer alike stopped and running: a sequence waits for the
#: stop its steps need, and the export reads the recording, not the machine.
_SEQUENCES: dict[str, tuple[Callable[[dict[str, Any]], bool], str]] = {
    "perform": (lambda r: ok(r) and r.get("steps_completed") == 1, "perform docstring"),
    "perform_export": (lambda r: ok(r) and _exported(r),
                       "perform_export docstring: the session's recording, written"),
    "drive": (lambda r: ok(r) and (r.get("verify") or {}).get("checked") is False,
              "drive docstring: `checked: false` when no expect was given"),
}

def _unavailable(datum: object) -> bool:
    """A datum a reply could not read: `{available: false, why}`, the reason beside it."""
    return isinstance(datum, dict) and datum.get("available") is False and bool(datum.get("why"))


def _stopped(tool: str) -> tuple[Callable[[dict[str, Any]], bool], str]:
    """The expectation of each tool on a headless machine stopped inside the probe."""
    live = alive
    d: dict[str, tuple[Callable[[dict[str, Any]], bool], str]] = {
        "build_check": (lambda r: refused(r, "session_live"), "build_check docstring"),
        "start": (lambda r: refused(r, "session_live"), "start docstring: one machine"),
        "status": (lambda r: ok(r) and live(r) and "stop_seq" in (r.get("last_stop") or {})
                   and r.get("cpu_mode") in ("real", "protected", "paged"),
                   "status docstring: last_stop, cpu_mode of the stop it is in"),
        "log": (lambda r: ok(r) and isinstance(r.get("lines"), list),
                "log docstring: an empty `lines` is an answer"),
        "log_wait": (lambda r: refused(r, "wait_stopped")
                     and "stop_seq" in (r.get("last_stop") or {}),
                     REF_DOC + "The log: a wait on a stopped machine ends at once"),
        "registers": (lambda r: ok(r) and "CS" in (r.get("regs") or {}),
                      "registers docstring"),
        "read_memory": (lambda r: ok(r) and len(str(r.get("hex"))) == 8,
                        "read_memory docstring: `length` bytes as hex"),
        "memdump": (lambda r: ok(r) and r.get("bytes") == 16
                    and Path(str(r.get("path"))).stat().st_size == 16,
                    "memdump docstring: size checked for equality"),
        "find": (lambda r: ok(r) and isinstance(r.get("hits_total"), int), "find docstring"),
        "disassemble": (lambda r: ok(r) and r.get("code_bits") == 16 and bool(r.get("lines"))
                        and len(r.get("lines") or []) == len(r.get("flow") or []),
                        "disassemble docstring: a line and a flow per instruction, real mode "
                        "16-bit"),
        "call_stack": (lambda r: ok(r) and r.get("heuristic") is True
                       and len(r.get("calls") or []) >= 1 and bool(r.get("ended_why")),
                       "call_stack docstring: row 0 the stop, heuristic, why it ended"),
        "scan start": (lambda r: ok(r) and r.get("hits_total") == 16,
                       "scan start: docstring, every cell a candidate (16 bytes, one-byte cells)"),
        "scan filter": (lambda r: ok(r) and r.get("hits_total") == 16,
                        "scan filter: docstring, `=` alone keeps cells unchanged since the "
                        "open; the machine stayed stopped"),
        "scan clear": (lambda r: ok(r) and r.get("cleared") is True, "scan clear docstring"),
        "debug": (lambda r: ok(r) and bool(r.get("output")), "debug docstring"),
        "machine_map": (lambda r: ok(r) and r.get("cpu_mode") == "real"
                        and "PROBE" in {b.get("filename") for b in r.get("mcbs") or []},
                        "machine_map docstring; known: PROBE resident, real mode"),
        "interrupt_vectors": (lambda r: ok(r) and len(r.get("vectors") or []) == 1
                              and str((r.get("vectors") or [{}])[0].get("seg_off")).startswith(
                                  "F000:"),
                              "interrupt_vectors docstring; known: DOS answers INT 21h from "
                              "the firmware segment"),
        "screen_view": (lambda r: ok(r) and r.get("kind") == "text"
                        and "C:\\>PROBE.COM" in (r.get("text") or []),
                        "screen_view docstring; known: the autoexec launches PROBE.COM"),
        "screen_signature": (lambda r: ok(r) and len(str(r.get("signature"))) == 16
                             and r.get("kind") == "text",
                             "screen_signature docstring: 16 hex characters, the text family"),
        "screen_wait": (lambda r: ok(r) and r.get("already") is True and r.get("polls") == 0,
                        "screen_wait docstring: already on screen, the machine not moved"),
        "palette": (lambda r: ok(r) and r.get("entries") == 256
                    and r.get("rgb") == ["000000", "00002a"],
                    "palette docstring; known: the BIOS's standard set, entry 1 blue"),
        "set_register": (lambda r: ok(r) and r.get("verified") is True,
                         "set_register docstring: readback equals what was sent"),
        "write": (lambda r: ok(r) and r.get("verified") is True,
                  "write docstring: readback, verified"),
        "stop": (lambda r: ok(r) and r.get("interrupted") is False,
                 "stop docstring: `false` when already stopped"),
        "step": (lambda r: ok(r) and r.get("instructions_completed") == 1,
                 "step docstring: instructions_completed"),
        "run_to": (lambda r: ok(r) and r.get("verdict") == "TIMEOUT"
                   and int(r.get("control_hits") or 0) > 0,
                   REF_DOC + "Advancing the machine: a control turns a silence into a "
                   "measurement"),
        "run_for": (lambda r: ok(r) and r.get("verdict") == "ELAPSED" and r.get("polls") == 1,
                    REF_DOC + "Advancing the machine: a frame is one vertical retrace"),
        "trace": (lambda r: ok(r) and r.get("verdict") == "ELAPSED"
                  and (r.get("trace") or {}).get("instructions") == 16
                  and Path(str((r.get("trace") or {}).get("path"))).is_file(),
                  "trace docstring: `instructions` executed, the log in a file"),
        "state_write save": (lambda r: ok(r) and r.get("paused") is False,
                       "state_write save: docstring, by SAVESTATE, a parked machine stays parked"),
        "state_write load": (lambda r: ok(r) and r.get("paused") is False
                       and (r.get("session") or {}).get("altered") is True,
                       "state_write load: docstring, by LOADSTATE, the state the stopped cells "
                       "saved"),
        "snapshot": (lambda r: refused(r), "snapshot docstring: refused parked, windowed"),
        "record": (lambda r: ok(r) and r.get("verdict") == "ELAPSED" and r.get("ended") is True
                   and int(r.get("avi_frames") or 0) >= 1 and Path(str(r.get("path"))).is_file(),
                   "record docstring: two retraces, the AVI checked and moved to `dest`"),
        "audio_record": (lambda r: ok(r) and r.get("verdict") == "ELAPSED"
                         and r.get("kind") == "wav" and int(r.get("samples") or 0) > 0
                         and Path(str(r.get("path"))).is_file(),
                         "audio_record docstring: the mixer's WAV over two retraces, checked"),
        "state_list": (lambda r: ok(r) and isinstance(r.get("states"), list),
                       "state_list docstring: needs no window"),
        "breakpoint_interrupt": (lambda r: ok(r) and r.get("ref") == "BPINT 21 AH=4C",
                                 "breakpoint_interrupt docstring: the row spelling"),
        "symbols_load": (lambda r: ok(r) and int(r.get("kept") or 0) > 0,
                         REF_DOC + "Names for addresses: a real-mode map with a base"),
        "symbols_find": (lambda r: ok(r) and bool(r.get("symbols")),
                         "symbols_find docstring: by name"),
        "breakpoint_at": (lambda r: ok(r) and r.get("state") == "armed",
                          "breakpoint_at docstring: armed, read back"),
        "declaration_list breakpoint": (lambda r: ok(r) and r.get("debugger_read") is True
                            and any(b.get("ref") == "0000:0002" and b.get("state") == "armed"
                                    for b in r.get("breakpoints") or []),
                            "declaration_list breakpoint docstring: stopped, read live"),
        "declaration_clear breakpoint": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                             "declaration_clear breakpoint docstring"),
        "regpoint_add": (lambda r: ok(r) and r.get("ref") == "AX==4C00"
                         and r.get("state") == "armed" and r.get("entry") == "BPIF AX==4C00",
                         "regpoint_add docstring: armed, its row read back"),
        "declaration_list regpoint": (lambda r: ok(r) and any(
                                          g.get("ref") == "AX==4C00" and g.get("state") == "armed"
                                          for g in r.get("regpoints") or []),
                                      "declaration_list regpoint docstring: stopped, read live"),
        "declaration_clear regpoint": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                                       "declaration_clear regpoint docstring"),
        "watch_add": (lambda r: ok(r) and r.get("state") == "evaluated",
                      "watch_add docstring: a show watch is evaluated"),
        "declaration_list watch": (lambda r: ok(r) and any(w.get("ref") == "0040:006C"
                                               for w in r.get("watches") or []),
                       "declaration_list watch docstring"),
        "declaration_clear watch": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                        "declaration_clear watch docstring"),
        "send_keys": (lambda r: refused(r, "not_running"),
                      "send_keys docstring: refused on a machine stopped at the debugger"),
        "send_mouse": (lambda r: refused(r, "not_running"),
                       "send_mouse docstring: refused on a machine stopped at the debugger"),
        # Before it, this state's order has `memdump`, `map_write(method="save")` and others write
        # files, so the
        # list is not empty, and a session started without `capture_video` lists no video.
        "captures": (lambda r: ok(r) and isinstance(r.get("captures"), list)
                     and bool(r["captures"])
                     and all(c.get("avi_frames") in (1, 2) for c in r["captures"]
                             if c.get("kind") == "avi")
                     and all({"kind", "path", "present"} <= set(c) for c in r["captures"]),
                     "captures docstring: the files the tools wrote, the one video `record`'s"),
        "capture_frame": (lambda r: refused(r), "capture_frame docstring: needs capture_video"),
        "series_capture": (lambda r: refused(r, "no_channel"),
                           "series_capture docstring: needs capture_video"),
        **_SEQUENCES,
        "resume": (lambda r: ok(r) and "stop_seq" not in r,
                   "resume docstring: a stopper declared, it runs"),
        "comment_write add": (lambda r: ok(r)
                              and (r.get("comment") or {}).get("state") == "resolved",
                        "comment_write add: docstring at a real-mode SEG:OFF placed by arithmetic"),
        "comment_list": (lambda r: ok(r) and any(c.get("ref") == COMMENT_REF
                                                 for c in r.get("comments") or []),
                         "comment_list docstring"),
        "comment_write save": (lambda r: ok(r) and Path(str(r.get("path"))).is_file(),
                         "comment_write save docstring"),
        "comment_write load": (lambda r: ok(r) and r.get("parsed") == 0
                         and r.get("added") == 0, "comment_write load docstring"),
        "comment_write delete": (lambda r: ok(r)
                                 and (r.get("deleted") or {}).get("ref") == COMMENT_REF,
                           "comment_write delete docstring"),
        "map_write add": (lambda r: ok(r) and r.get("kind") == "text" and r.get("size") == [80, 25]
                    and len(str((r.get("match") or [{}])[0].get("signature"))) == 16,
                    "map_write add docstring: one read signs each crop, in the screen's own units"),
        "map_find": (lambda r: ok(r) and r.get("matched") is True
                     and r.get("screen") == "probe_stopped" and r.get("layer") == "session",
                     "map_find docstring: the screen just mapped, the session layer first"),
    }
    return d[tool]


def _running(tool: str) -> tuple[Callable[[dict[str, Any]], bool], str]:
    """The expectation of each tool on a headless machine running with a stopper armed."""
    if tool in _NEEDS_STOP:
        return (lambda r: refused(r, "not_stopped") and alive(r),
                "the tool's docstring: needs the machine stopped; reply_contract not_stopped")
    if tool in _WINDOWED:
        return (lambda r: refused(r) and r.get("code") != "unknown_ref" and alive(r),
                "the tool's docstring: a windowed session only")
    if tool == "captures":
        # THE FILES THE TOOLS WROTE answer in any state; only a video needs `capture_video`.
        return _stopped(tool)
    if tool in _NO_CAPTURE:
        return (lambda r: refused(r) and alive(r), "the tool's docstring: needs capture_video")
    d: dict[str, tuple[Callable[[dict[str, Any]], bool], str]] = {
        "build_check": (lambda r: refused(r, "session_live"), "build_check docstring"),
        "start": (lambda r: refused(r, "session_live"), "start docstring"),
        "stop": (lambda r: ok(r) and r.get("interrupted") is True and r.get("via") == "break",
                 "stop docstring: BREAK down the debugger channel, headless too"),
        "status": (lambda r: ok(r) and alive(r) and _unavailable(r.get("cpu_mode")),
                   "status docstring: cpu_mode unavailable, with its why, while it runs"),
        "log": (lambda r: ok(r) and bool(r.get("lines")), "log docstring: works running"),
        "log_wait": (lambda r: ok(r) and "PROBE" in str(r.get("line")),
                     "log_wait docstring; known: probe.asm writes `PROBE . tick`"),
        "state_list": (lambda r: ok(r), "state_list docstring: answers while running"),
        "state_write save": (lambda r: ok(r) and r.get("paused") is True,
                       "state_write save: docstring, a running guest is stopped for it and "
                       "released"),
        "state_write load": (lambda r: ok(r) and r.get("paused") is True,
                       "state_write load: docstring, a running guest is stopped for it and "
                       "released"),
        "breakpoint_interrupt": (lambda r: ok(r) and r.get("state") == "pending",
                                 "breakpoint_interrupt docstring: stored pending"),
        "symbols_load": (lambda r: ok(r) and r.get("pending") is True,
                         REF_DOC + "Names for addresses: with an explicit base while it runs"),
        "symbols_find": (lambda r: ok(r) and bool(r.get("symbols")),
                         REF_DOC + "Names for addresses: the table answers at once"),
        "breakpoint_at": (lambda r: ok(r) and r.get("state") == "pending",
                          "breakpoint_at docstring: pending when the guest is running"),
        "declaration_list breakpoint": (lambda r: ok(r) and r.get("debugger_read") is False,
                            "declaration_list breakpoint docstring: running, debugger_read false"),
        "declaration_clear breakpoint": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                             "declaration_clear breakpoint docstring"),
        "regpoint_add": (lambda r: ok(r) and r.get("state") == "pending",
                         "regpoint_add docstring: pending while the guest runs"),
        "declaration_list regpoint": (lambda r: ok(r) and r.get("debugger_read") is False,
                                      "declaration_list regpoint docstring: running"),
        "declaration_clear regpoint": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                                       "declaration_clear regpoint docstring"),
        "watch_add": (lambda r: ok(r), "watch_add docstring"),
        "declaration_list watch": (lambda r: ok(r) and r.get("debugger_read") is False,
                       "declaration_list watch docstring: running, debugger_read false"),
        "declaration_clear watch": (lambda r: ok(r) and r.get("declarations_cleared") == 1,
                        "declaration_clear watch docstring"),
        "comment_list": (lambda r: ok(r) and (r.get("session") or {}).get("running") is True,
                         "comment_list docstring: answers on a running guest"),
        "comment_write save": (lambda r: ok(r) and Path(str(r.get("path"))).is_file(),
                         "comment_write save docstring: answers on a running guest"),
        "send_keys": (lambda r: refused(r, "no_channel"),
                      "send_keys docstring: no stub announced, so nothing would receive it"),
        "send_mouse": (lambda r: refused(r, "no_channel"),
                       "send_mouse docstring: no stub announced, so nothing would receive it"),
        **_SEQUENCES,
        "close": (lambda r: ok(r) and r.get("closed") is True and r.get("ended_by") == CLOSED_BY,
                  "close docstring: `quit`, a session launched here leaves on the signal; "
                  "`killed` on Windows, which terminates"),
    }
    return d[tool]


def _expect(tool: str, state: str) -> tuple[Callable[[dict[str, Any]], bool], str]:
    if tool in MEDIA_ABSENT:
        live = state in ("stopped", "running")
        return ((lambda r: refused(r, "bad_argument") and "no file at" in str(r.get("message"))
                 and (alive(r) if live else no_session(r))),
                f"{tool} docstring: reads files, in any state; a missing one refused by name")
    if tool == "map_write load":
        return ((lambda r: refused(r, "bad_argument") and "no map file" in str(r.get("message"))),
                "map_write load docstring: any state; a file that is not there refused by name")
    if tool == "map_write save":
        if state == "none":
            return ((lambda r: refused(r, "needs_call") and no_session(r)),
                    "map_write save docstring: nothing mapped yet is `needs_call`")
        return ((lambda r: ok(r) and Path(str(r.get("path"))).is_file()),
                "map_write save docstring: any state; the maps the server holds, written")
    if tool == "perform_export" and state in ("none", "closed"):
        # Before any `start` there is nothing recorded; a closed session's recording is still
        # the last one, and it exports with no machine.
        if state == "none":
            return (lambda r: refused(r, "no_recording") and no_session(r),
                    "perform_export docstring: `no_recording` before a `start` succeeded")
        return (lambda r: ok(r) and _exported(r) and no_session(r),
                "perform_export docstring: the last session's recording, no machine needed")
    if state in ("none", "closed"):
        if tool in _WITHOUT_SESSION:
            return _WITHOUT_SESSION[tool]
        return (lambda r: refused(r, "no_session") and no_session(r),
                "reply_contract no_session: no live machine, `start` first")
    predicate, source = _stopped(tool) if state == "stopped" else _running(tool)
    # A live machine in both states: every reply's session block has to say so.
    return (lambda r: predicate(r) and alive(r)), source


def _a_label(tool: str, state: str) -> str:
    return f"A {state:<7} {tool}"


def _a_cells() -> list[Cell]:
    out = [Cell(_a_label(t, s), _expect(t, s)[1]) for s in STATES for t in TOOLS
           if not (s == "stopped" and t == "close")]
    out.append(Cell("A running registers(from_last_stop)",
                    "registers docstring: `superseded`, marked, with last_stop"))
    out.append(Cell(SAVES_LABEL,
                    "state_write save: docstring, a running guest is stopped for it and "
                                 "released"))
    out.append(Cell("A stopped close", "close docstring: `quit` on a parked session"))
    return out


def _a_one(tool: str, state: str) -> dict[str, Any]:
    predicate, _ = _expect(tool, state)
    name, selector = _folded(tool)
    r = M.call(getattr(server, name), **selector, **_args(tool, state))
    note_spawn()
    M.judge(_a_label(tool, state), predicate(r), said(r))
    return r


#: A save on a running guest, over and over: a late repaint of the command's own can be read as a
#: stop, so one save proves too little.
SAVES = 30
SAVES_LABEL = f"A state_write save on a running guest leaves it running, {SAVES} times in a row"


def _saves_leave_it_running() -> None:
    for i in range(SAVES):
        r = M.call(server.state_write, method="save", name=f"matrix_a_loop_{i}", seconds=10)
        if not (ok(r) and (r.get("session") or {}).get("running") is True):
            M.judge(SAVES_LABEL, False, f"save {i + 1} of {SAVES}: {said(r)}")
            return
    M.judge(SAVES_LABEL, True, f"{SAVES} saves, the guest running after each")


#: The order inside a state: what reads first, what arms and clears in pairs, and what changes
#: the state last. The running state opens with the wait that proves the guest runs.
_STOPPED_ORDER = [
    "build_check", "start", "status", "log", "log_wait", "registers", "read_memory",
    "disassemble", "call_stack", "memdump",
    "find", "scan start", "scan filter", "scan clear", "debug", "machine_map",
    "interrupt_vectors", "palette", "screen_view", "screen_signature", "screen_wait",
    "map_write add", "map_find", "map_write save", "map_write load",
    "set_register", "write", "stop",
    "step", "run_to", "run_for", "trace", "state_write save", "state_write load", "snapshot",
                  "record", "audio_record", "state_list",
    "breakpoint_interrupt", "symbols_load", "symbols_find", "comment_write add", "comment_list",
    "comment_write save", "comment_write load", "comment_write delete", "breakpoint_at",
                  "declaration_list breakpoint",
    "declaration_clear breakpoint", "regpoint_add", "declaration_list regpoint",
    "declaration_clear regpoint", "watch_add", "declaration_list watch",
                  "declaration_clear watch", "send_keys", "send_mouse",
    "captures", "capture_frame", "series_capture", *MEDIA_ABSENT, "perform", "drive",
    "perform_export"]


TOOLS = [p for t in REGISTERED
         for p in ([q for q in _STOPPED_ORDER if _folded(q)[0] == t and " " in q] or [t])]


@M.section("A", "every tool in every machine state, on the probe guest", _a_cells())
def section_a() -> None:
    missing = sorted(set(TOOLS) - set(_STOPPED_ORDER) - {"resume", "close"})
    missing += sorted({_folded(p)[0] for p in _STOPPED_ORDER} - set(REGISTERED))
    if missing:
        raise RuntimeError(f"tools this matrix has no order for: {missing}")
    for tool in TOOLS:
        if tool != "start":
            _a_one(tool, "none")
    _a_one("start", "none")
    M.setup()
    into_dos()
    Ctx.probe = into_probe()
    regs = M.call(server.registers)
    Ctx.eax = hexint((regs.get("regs") or {}).get("EAX")) or 0
    M.setup()
    for tool in _STOPPED_ORDER:
        _a_one(tool, "stopped")
        if tool == "breakpoint_interrupt":
            M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 21 AH=4C")
            M.setup()
    M.call(server.breakpoint_at, ref=NEVER_RUNS_STOPPER)
    M.setup()
    _a_one("resume", "stopped")
    _a_one("log_wait", "running")        # first: it is what proves the guest runs
    # In the stopped order, so a fold's method meets what an earlier tool declared (a watch
    # is cleared after `watch_add`), whatever order the server registers them in.
    for tool in [*(t for t in _STOPPED_ORDER if t in TOOLS), *(t for t in TOOLS
                                                                if t not in _STOPPED_ORDER)]:
        if tool not in ("log_wait", "close", "stop"):
            _a_one(tool, "running")
    r = M.call(server.registers, from_last_stop=True)
    M.judge("A running registers(from_last_stop)",
            ok(r) and r.get("superseded") is True
            and "stop_seq" in (r.get("last_stop") or {}), said(r))
    _saves_leave_it_running()
    _a_one("stop", "running")            # last of the running cells: it parks the machine
    M.setup()
    must(M.call(server.resume), "releasing the probe again for the running close")
    _a_one("close", "running")
    for tool in TOOLS:
        if tool != "start":
            _a_one(tool, "closed")
    _a_one("start", "closed")
    r = M.call(server.close)
    M.judge("A stopped close",
            ok(r) and r.get("closed") is True and r.get("ended_by") == CLOSED_BY, said(r))


# ================================================================ B: argument edges
#
# For every size, count, address or bound a tool takes: the maximum, one past it, and the
# overflow. The machine is stopped inside the probe unless a cell says otherwise.

HUGE = 2 ** 31

B_CELLS = cells(
    ("B read_memory length=128", "read_memory docstring: length 1 to 128"),
    ("B read_memory length=129", "read_memory docstring: length 1 to 128"),
    ("B read_memory length=0", "read_memory docstring: length 1 to 128"),
    ("B read_memory length=2**31", "read_memory docstring: length 1 to 128"),
    ("B write 128 bytes", "write docstring: up to 128 bytes, read back"),
    ("B write 129 bytes", "write docstring: up to 128 bytes"),
    ("B write odd hex digits", "write docstring: whole hex bytes, two digits each"),
    ("B write into ROM", "write docstring: a real-mode ROM address is refused, nothing sent"),
    ("B set_register cs reads back under its own name",
     "set_register docstring: a segment register, four digits, under its own name"),
    ("B set_register ax is verified with the high half set",
     "set_register docstring: a 16-bit name is the low half of its 32-bit register"),
    ("B memdump 64 KiB", "memdump docstring: size checked for equality"),
    ("B memdump dest exists", "memdump docstring: refused rather than overwriting"),
    ("B memdump dest ~nosuchuser", REF_DOC + "The session: a `~user` this host does not know"),
    ("B memdump dest in the emulator's cwd", "memdump docstring: a dest inside that directory"),
    ("B find length=400 of zeros", "find docstring; known: the region's own dump"),
    ("B find length=401 of zeros", "find docstring: at most 400 hits, the highest kept"),
    ("B scan 400 survivors listed", REF_DOC + "Reading and writing: `limit` 400 is the ceiling"),
    ("B scan 401 survivors cut", REF_DOC + "Reading and writing: `limit` 400 is the ceiling"),
    ("B scan 40 survivors listed by default", "scan filter: docstring, `limit` defaults to 40"),
    ("B scan 41 survivors cut by default", "scan filter: docstring, `limit` defaults to 40"),
    ("B scan start cell_bytes=3", "scan start: docstring, `cell_bytes` 1, 2 or 4"),
    ("B scan filter operator=~", "scan filter: docstring, the six operators"),
    ("B step count=64", "the ceiling dosbox_stepping.STEP_MAX declares, REFERENCE's Advancing "
                        "quotes; step docstring: instructions_completed is what landed"),
    ("B step count=65", "the ceiling dosbox_session.STEP_MAX declares"),
    ("B step count=0", "step docstring: a count of instructions"),
    ("B step mode=sideways", "step docstring: into or over"),
    ("B log limit=400", "log docstring: limit 1..400"),
    ("B log limit=401", "log docstring: limit 1..400"),
    ("B log limit=0", "log docstring: limit 1..400"),
    ("B log channel=process", "log docstring: `process` is refused by name"),
    ("B log pattern does not compile", "log docstring"),
    ("B log_wait seconds=600 already there", "log_wait docstring: (0, 600]; history first"),
    ("B log_wait seconds=600.5", "log_wait docstring: seconds in (0, 600]"),
    ("B log_wait seconds=0", "log_wait docstring: seconds in (0, 600]"),
    ("B run_to seconds=600 arrives", "the bound scry_core.vocabulary.WAIT_MAX_S declares, "
                                     "log_wait's published (0, 600]"),
    ("B run_to seconds=600.5", "the bound scry_core.vocabulary.WAIT_MAX_S declares"),
    ("B run_to seconds=0", "the bound scry_core.vocabulary.WAIT_MAX_S declares"),
    ("B run_to without a control", "run_to docstring: control is REQUIRED"),
    ("B run_to real-mode offset past FFFF", REF_DOC + "Advancing: refused in real mode"),
    ("B resume seconds=-1", "resume docstring: `seconds` is 0 or a bound up to the ceiling"),
    ("B symbols_find limit=50", "symbols_find docstring: limit 1..50"),
    ("B symbols_find limit=51", "symbols_find docstring: limit 1..50"),
    ("B symbols_find limit=0", "symbols_find docstring: limit 1..50"),
    ("B watch_add show length=128", "watch_add docstring: a show watch is at most 128 bytes"),
    ("B watch_add show length=129", "watch_add docstring: a show watch is at most 128 bytes"),
    ("B watch_add show length=2**31", "watch_add docstring: a length over the ceiling"),
    ("B breakpoint_interrupt number=0xFF", "an interrupt vector is one byte"),
    ("B breakpoint_interrupt number=0x100", "an interrupt vector is one byte"),
    ("B breakpoint_interrupt ah=0x100", "AH is one byte"),
    ("B send_mouse x=32767", "send_mouse docstring: a driver coordinate is 16-bit signed"),
    ("B send_mouse x=32768", "send_mouse docstring: a driver coordinate is 16-bit signed"),
    ("B send_mouse x=2**31", "send_mouse docstring: a driver coordinate is 16-bit signed"),
    ("B perform settle_seconds=600",
     REF_DOC + "Sequences: settle_seconds is a bound; its top is WAIT_MAX_S's"),
    ("B perform settle_seconds=600.5",
     REF_DOC + "Sequences: a settle_seconds that is not a bound"),
    ("B perform settle_seconds=-1", REF_DOC + "Sequences: a settle_seconds that is not a bound"),
    ("B drive limit=400", "drive docstring: log's ceiling of 400 at most"),
    ("B drive limit=401", "drive docstring: log's ceiling of 400 at most"),
    ("B send_keys 64 keys", "send_keys docstring: at most 64 per call"),
    ("B send_keys 65 keys", "send_keys docstring: at most 64 per call"),
    ("B send_keys unknown key", "send_keys docstring: an unknown key name"),
    ("B send_keys seconds without expect", "send_keys docstring: seconds without expect"),
    ("B start session_seconds=14400", "start docstring: at most 4 hours"),
    ("B start session_seconds=14401", "start docstring: at most 4 hours"),
    ("B start session_seconds=0", "start docstring: `session_seconds` out of range"),
)


def _bad(r: dict[str, Any]) -> bool:
    return refused(r, "bad_argument")


def _dump(ref: str, length: int) -> bytes:
    r = M.call(server.memdump, ref=ref, length=length, dest=M.fresh(".bin"))
    if not ok(r):
        raise RuntimeError(f"the known answer's own dump failed: {said(r)}")
    return Path(str(r["path"])).read_bytes()


def _b_find() -> None:
    base = f"{SCRATCH}:1000"
    region = _dump(base, 0x400)
    for n in (400, 401):
        want = [i for i in range(n) if region[i] == 0]
        if len(want) != n:
            M.block(f"B find length={n} of zeros", f"the region holds {n - len(want)} non-zero "
                    f"bytes, so the edge is not the one this cell is for")
            continue
        r = M.call(server.find, data_hex="00", ref=base, length=n)
        highest = [f"{SCRATCH_SEG:04X}:{0x1000 + i:08X}" for i in want[-400:]]
        good = (ok(r) and r.get("hits_total") == n and r.get("hits") == highest
                and r.get("truncated") is (n > 400))
        M.judge(f"B find length={n} of zeros", good,
                f"{said(r)}; expected {len(want)} hits from the dump")


def _b_scan() -> None:
    for n in (400, 401):
        M.call(server.scan, method="clear")
        opened = M.call(server.scan, method="start", ref=f"{SCRATCH}:1000", length=n)
        r = M.call(server.scan, method="filter", operator="=", limit=400)
        if n == 400:
            good = (ok(opened) and ok(r) and r.get("hits_total") == 400
                    and len(r.get("hits") or []) == 400 and r.get("truncated") is False)
        else:
            good = (ok(opened) and ok(r) and r.get("hits_total") == 401
                    and r.get("hits") == [] and r.get("truncated") is True
                    and bool(r.get("note")))
        label = "B scan 400 survivors listed" if n == 400 else "B scan 401 survivors cut"
        M.judge(label, good, said(r))
    for n in (40, 41):
        M.call(server.scan, method="clear")
        opened = M.call(server.scan, method="start", ref=f"{SCRATCH}:1000", length=n)
        r = M.call(server.scan, method="filter", operator="=")
        listed = n <= 40
        M.judge(f"B scan {n} survivors {'listed' if listed else 'cut'} by default",
                ok(opened) and ok(r) and r.get("hits_total") == n
                and len(r.get("hits") or []) == (n if listed else 40)
                and r.get("truncated") is (not listed), said(r))
    M.call(server.scan, method="clear")


def _b_serial() -> None:
    """The key edges need a running guest on the serial route: a second boot with a port."""
    close_whatever()
    boot(conf=conf_with_stub(PROBE_CONF, "PROBE.COM"), input_port=free_port())
    into_dos()
    release_running()
    must(M.call(server.log_wait, pattern=r"STUB  \. inject device=present", channel="guest",
                seconds=30), "the stub's announce")
    M.setup()
    r = M.call(server.send_keys, keys=["a"] * 64)
    judged("B send_keys 64 keys", reply=r, holds=ok(r) and r.get("route") == "guest"
            and r.get("posted") == 64)
    r = M.call(server.send_keys, keys=["a"] * 65)
    judged("B send_keys 65 keys", reply=r, holds=_bad(r))
    r = M.call(server.send_keys, keys=["matrix_no_such_key"])
    judged("B send_keys unknown key", reply=r, holds=_bad(r))
    r = M.call(server.send_keys, keys=["a"], seconds=5)
    judged("B send_keys seconds without expect", reply=r, holds=_bad(r))
    close_whatever()


@M.section("B", "argument edges: the maximum, one past it, the overflow", B_CELLS)
def section_b() -> None:
    boot()
    into_dos()
    p = into_probe()
    M.setup()
    for n, label, good in ((128, "B read_memory length=128", None),
                           (129, "B read_memory length=129", _bad),
                           (0, "B read_memory length=0", _bad),
                           (HUGE, "B read_memory length=2**31", _bad)):
        r = M.call(server.read_memory, ref=f"{SCRATCH}:0000", length=n)
        judged(label, reply=r, holds=good(r) if good else ok(r) and len(str(r.get("hex"))) == 256)
    data = bytes(range(128)).hex().upper()
    r = M.call(server.write, ref=f"{SCRATCH}:0000", data_hex=data)
    judged("B write 128 bytes", reply=r, holds=ok(r) and r.get("verified") is True)
    r = M.call(server.write, ref=f"{SCRATCH}:0000", data_hex=data + "00")
    judged("B write 129 bytes", reply=r, holds=_bad(r))
    r = M.call(server.write, ref=f"{SCRATCH}:0000", data_hex="ABC")
    judged("B write odd hex digits", reply=r, holds=_bad(r))
    r = M.call(server.write, ref="F000:0000", data_hex="00")
    judged("B write into ROM", reply=r, holds=refused(r) and alive(M.call(server.status)))
    # CS IS WRITTEN WITH THE VALUE IT HOLDS: another would move the probe's code out from under
    # it. EAX is put back after the 16-bit cell, for the same reason.
    regs = must(M.call(server.registers), "the registers the set_register cells start from")
    cs, eax = (int(str(regs["regs"][k]), 16) for k in ("CS", "EAX"))
    r = M.call(server.set_register, name="cs", value=cs)
    judged("B set_register cs reads back under its own name", reply=r,
           holds=ok(r) and r.get("verified") is True and r.get("readback") == f"{cs:#06x}")
    must(M.call(server.set_register, name="eax", value=0xABCD0000), "EAX with its high half set")
    r = M.call(server.set_register, name="ax", value=0x1234)
    judged("B set_register ax is verified with the high half set", reply=r,
           holds=ok(r) and r.get("verified") is True and r.get("readback") == "0x1234"
           and r.get("regs", {}).get("EAX") == "0xabcd1234")
    must(M.call(server.set_register, name="eax", value=eax), "EAX put back")
    r = M.call(server.memdump, ref=f"{SCRATCH}:0000", length=0x10000, dest=M.fresh(".bin"))
    judged("B memdump 64 KiB", reply=r, holds=ok(r) and r.get("bytes") == 0x10000
            and Path(str(r.get("path"))).stat().st_size == 0x10000)
    there = M.fresh(".bin")
    Path(there).write_bytes(b"keep")
    r = M.call(server.memdump, ref=f"{SCRATCH}:0000", length=16, dest=there)
    judged("B memdump dest exists", reply=r,
           holds=refused(r) and Path(there).read_bytes() == b"keep")
    if NO_SUCH_HOME_WHY:
        M.block("B memdump dest ~nosuchuser", NO_SUCH_HOME_WHY)
    else:
        r = M.call(server.memdump, ref=f"{SCRATCH}:0000", length=16,
                   dest="~matrix_no_such_user/x.bin")
        judged("B memdump dest ~nosuchuser", reply=r,
               holds=refused(r, "bad_argument")
               and "home directory this host cannot find" in str(r.get("message")))
    inside = GUEST / "matrix-dump-inside-cwd.bin"
    r = M.call(server.memdump, ref=f"{SCRATCH}:0000", length=16, dest=str(inside))
    judged("B memdump dest in the emulator's cwd", reply=r,
           holds=refused(r) and not inside.exists())
    inside.unlink(missing_ok=True)
    _b_find()
    _b_scan()
    r = M.call(server.scan, method="start", ref=f"{SCRATCH}:0000", length=16, cell_bytes=3)
    judged("B scan start cell_bytes=3", reply=r, holds=_bad(r))
    M.call(server.scan, method="start", ref=f"{SCRATCH}:0000", length=16)
    r = M.call(server.scan, method="filter", operator="~")
    judged("B scan filter operator=~", reply=r, holds=refused(r))
    M.call(server.scan, method="clear")
    M.setup()
    r = M.call(server.step, count=64)
    done = r.get("instructions_completed")
    judged("B step count=64", reply=r, holds=ok(r) and isinstance(done, int)
            and (done == 64 or (done < 64 and (r.get("session") or {}).get("running") is True)))
    for label, kw in (("B step count=65", {"count": 65}), ("B step count=0", {"count": 0}),
                      ("B step mode=sideways", {"mode": "sideways"})):
        r = M.call(server.step, **kw)
        judged(label, reply=r, holds=_bad(r))
    for n, label, want in ((400, "B log limit=400", True), (401, "B log limit=401", False),
                           (0, "B log limit=0", False)):
        r = M.call(server.log, pattern=".", channel="emulator", limit=n)
        judged(label, reply=r, holds=ok(r) if want else _bad(r))
    r = M.call(server.log, pattern=".", channel="process")
    judged("B log channel=process", reply=r, holds=refused(r, "bad_argument", "no_channel"))
    r = M.call(server.log, pattern="(", channel="emulator")
    judged("B log pattern does not compile", reply=r, holds=_bad(r))
    held = M.call(server.log, pattern=".", channel="emulator", limit=1)
    if not (ok(held) and held.get("lines")):
        raise RuntimeError("the emulator channel holds no line for the 600 s wait to find")
    r = M.call(server.log_wait, exempt="the line is already in the log",
               pattern=".", channel="emulator", seconds=600)
    judged("B log_wait seconds=600 already there", reply=r,
           holds=ok(r) and r.get("already") is True)
    r = M.call(server.log_wait, exempt="refused before any wait",
               pattern=".", channel="emulator", seconds=600.5)
    judged("B log_wait seconds=600.5", reply=r, holds=_bad(r))
    r = M.call(server.log_wait, pattern=".", channel="emulator", seconds=0)
    judged("B log_wait seconds=0", reply=r, holds=_bad(r))
    r = M.call(server.run_to, exempt="the probe's own loop runs at every instruction",
               ref=p.at(p.spin), seconds=600, control=NEVER_RUNS_CONTROL)
    judged("B run_to seconds=600 arrives", reply=r, holds=ok(r) and r.get("verdict") == "TARGET")
    r = M.call(server.run_to, exempt="refused before any wait",
               ref=p.at(p.spin), seconds=600.5, control=NEVER_RUNS_CONTROL)
    judged("B run_to seconds=600.5", reply=r, holds=_bad(r))
    r = M.call(server.run_to, ref=p.at(p.spin), seconds=0, control=NEVER_RUNS_CONTROL)
    judged("B run_to seconds=0", reply=r, holds=_bad(r))
    # NO CONTROL is spelled empty here: an omitted one is the schema's refusal, which an
    # in-process call cannot reach (Python refuses the call before any tool runs).
    r = M.call(server.run_to, ref=p.at(p.spin), seconds=3, control="")
    judged("B run_to without a control", reply=r, holds=_bad(r))
    r = M.call(server.run_to, ref="0000:10000", seconds=3, control=p.at(p.spin))
    judged("B run_to real-mode offset past FFFF", reply=r, holds=refused(r))
    # A stopper that fires at the next tick, so a negative bound that were NOT refused would
    # release the machine for one tick rather than for good.
    M.call(server.breakpoint_interrupt, number=0x08)
    M.setup()
    r = M.call(server.resume, seconds=-1)
    judged("B resume seconds=-1", reply=r,
           holds=_bad(r) and (r.get("session") or {}).get("alive") is True)
    M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 08")
    M.setup()
    M.call(server.symbols_load, path=str(FIXTURE_MAP), base="8000")
    M.setup()
    for n, label, want in ((50, "B symbols_find limit=50", True),
                           (51, "B symbols_find limit=51", False),
                           (0, "B symbols_find limit=0", False)):
        r = M.call(server.symbols_find, name="MAP", limit=n)
        judged(label, reply=r, holds=ok(r) if want else _bad(r))
    for n, label in ((128, "B watch_add show length=128"), (129, "B watch_add show length=129"),
                     (HUGE, "B watch_add show length=2**31")):
        r = M.call(server.watch_add, ref=f"{SCRATCH}:0000", mode="show", length=n)
        judged(label, reply=r, holds=ok(r) if n == 128 else refused(r))
    M.call(server.declaration_clear, kind="watch", all=True)
    M.setup()
    r = M.call(server.breakpoint_interrupt, number=0xFF)
    judged("B breakpoint_interrupt number=0xFF", reply=r,
           holds=ok(r) and r.get("ref") == "BPINT FF")
    M.call(server.declaration_clear, kind="breakpoint", ref="BPINT FF")
    M.setup()
    r = M.call(server.breakpoint_interrupt, number=0x100)
    judged("B breakpoint_interrupt number=0x100", reply=r, holds=_bad(r))
    r = M.call(server.breakpoint_interrupt, number=0x21, ah=0x100)
    judged("B breakpoint_interrupt ah=0x100", reply=r, holds=_bad(r))
    # THE TOP passes the argument check and meets the machine (stopped here); one past it and
    # the overflow are refused before anything is asked of it.
    r = M.call(server.send_mouse, x=32767, y=0, units="mouse")
    judged("B send_mouse x=32767", reply=r, holds=refused(r, "not_running"))
    for x, label in ((32768, "B send_mouse x=32768"), (HUGE, "B send_mouse x=2**31")):
        r = M.call(server.send_mouse, x=x, y=0, units="mouse")
        judged(label, reply=r, holds=_bad(r))
    r = M.call(server.perform, exempt="no step of it waits", steps=[{"op": "status"}],
               settle_seconds=600)
    judged("B perform settle_seconds=600", reply=r,
           holds=ok(r) and r.get("steps_completed") == 1)
    r = M.call(server.perform, exempt="refused before any step",
               steps=[{"op": "status"}], settle_seconds=600.5)
    judged("B perform settle_seconds=600.5", reply=r, holds=_bad(r))
    r = M.call(server.perform, steps=[{"op": "status"}], settle_seconds=-1)
    judged("B perform settle_seconds=-1", reply=r, holds=_bad(r))
    for n, label in ((400, "B drive limit=400"), (401, "B drive limit=401")):
        r = M.call(server.drive, act=[{"op": "status"}], limit=n)
        judged(label, reply=r, holds=ok(r) if n == 400 else _bad(r))
    _b_serial()
    for n, label in ((14401, "B start session_seconds=14401"), (0, "B start session_seconds=0")):
        r = start_call(conf=str(PROBE_CONF), cwd=str(GUEST),
                       session_seconds=n, state_dir=M.fresh("-save"))
        judged(label, reply=r, holds=_bad(r) and no_session(r))
        close_whatever()
    r = start_call(conf=str(PROBE_CONF), cwd=str(GUEST),
                   session_seconds=14400, state_dir=M.fresh("-save"))
    judged("B start session_seconds=14400", reply=r, holds=ok(r) and alive(r))


# ================================================================ C: across calls
#
# What one call leaves for the next: the declaration store per conf across close and start,
# the scan's lifecycle, `altered`, a sequence that fails half-way, what was declared while the
# guest ran, and the probe's own known answers (its counter, its log line, its loop).

C_CELLS = cells(
    ("C altered false after start and reads", REF_DOC + "What every reply carries: altered"),
    ("C altered true after a write, and stays", REF_DOC + "What every reply carries: altered"),
    ("C read_memory and memdump agree", "known: both read the bytes `write` put there"),
    ("C debug of a command the debugger does not take says so in its note",
     "debug docstring: `note`"),
    ("C the command after it runs on its own", REF_DOC + "The debugger channel"),
    ("C find finds what write wrote", "known: the bytes `write` put there, once"),
    ("C scan start while a scan is open", "scan start: docstring, one scan at a time"),
    ("C scan ! keeps the one cell written", REF_DOC + "Reading and writing: `!` since the open"),
    ("C scan closing = answers its own iterations", REF_DOC + "Reading and writing: iterations"),
    ("C scan clear with nothing open", "scan clear docstring: a no-op that says so"),
    ("C breakpoint_interrupt twice is already_stored", "breakpoint_interrupt docstring"),
    ("C a second ref on the same byte is refused", REF_DOC + "Declarations: one row"),
    ("C declaration_clear breakpoint of an unknown ref",
     REF_DOC + "Declarations: a ref matching nothing"),
    ("C status counts the declarations", REF_DOC + "Advancing the machine: declarations"),
    ("C regpoint_add refuses a term the debugger does not take, naming its shape",
     "regpoint_add docstring: Refused"),
    ("C a registerpoint stops the guest as its condition comes true, and the stop names it",
     "regpoint_add docstring; known: probe.asm's pause counts BX down from 700"),
    ("C run_to arrives in the probe and removes its breakpoint",
     REF_DOC + "Advancing the machine; known: probe.asm `emit`"),
    ("C a show watch rides the stop with the counter's digits",
     REF_DOC + "Declarations; known: probe.asm's ASCII odometer"),
    ("C the stop's e9 since the previous stop", REF_DOC + "Advancing: What a stop returns"),
    ("C perform ending in resume carries the stop", REF_DOC + "Sequences in one call"),
    ("C perform summaries writes both files", REF_DOC + "Sequences: summaries"),
    ("C perform refuses a bad step before running any", REF_DOC + "Sequences: checked whole"),
    ("C perform refuses read_memory length=129 before running any",
     REF_DOC + "Sequences: argument VALUES go through each tool's own checks"),
    ("C perform stops at a step that fails", REF_DOC + "Sequences; reply_contract step_failed"),
    ("C drive refuses when a step fails", "drive docstring: INVALID when a step failed"),
    ("C drive sees a new probe line", "drive docstring; known: the probe logs every few s"),
    ("C log_wait answers history at once", REF_DOC + "The log: already, waited_s 0.0"),
    ("C log_wait expiry is a TIMEOUT", REF_DOC + "The log: a bound that expires"),
    ("C a breakpoint and a change watch at one ref, declared while running, both armed",
     REF_DOC + "Declarations: what is declared while it runs is armed at the next stop"),
    ("C declared while running applies at the next stop",
     REF_DOC + "Advancing: what is asked while running is applied at the next stop"),
    ("C a change watch on the counter stops the probe",
     REF_DOC + "Declarations: break on change, real mode; known: `bump` writes cnt"),
    ("C a raw breakpoint from another session on the same build re-arms",
     REF_DOC + "Declarations: a raw SEG:OFF is kept per build, re-armed at start"),
    ("C declaring it again adopts it", REF_DOC + "Declarations: declaring it again adopts it"),
    ("C another conf inherits nothing", REF_DOC + "Declarations: keyed by the conf"),
    ("C start with a plan", REF_DOC + "The session: plan"),
    ("C start with program runs it after the autoexec", REF_DOC + "The session: program"),
)


def _c_memory() -> None:
    fresh = M.call(server.status)
    r = M.call(server.read_memory, ref=f"{SCRATCH}:2000", length=8)
    judged("C altered false after start and reads", reply=r,
            holds=(fresh.get("session") or {}).get("altered") is False
            and (r.get("session") or {}).get("altered") is False)
    w = M.call(server.write, ref=f"{SCRATCH}:2000", data_hex="0102030405060708")
    later = M.call(server.status)
    judged("C altered true after a write, and stays", reply=w,
            holds=(w.get("session") or {}).get("altered") is True
            and (later.get("session") or {}).get("altered") is True)
    r = M.call(server.read_memory, ref=f"{SCRATCH}:2000", length=8)
    d = M.call(server.memdump, ref=f"{SCRATCH}:2000", length=8, dest=M.fresh(".bin"))
    judged("C read_memory and memdump agree", reply=d,
            holds=ok(r) and ok(d) and str(r.get("hex")).upper() == "0102030405060708"
            and Path(str(d.get("path"))).read_bytes().hex().upper() == "0102030405060708")
    M.call(server.write, ref=f"{SCRATCH}:3000", data_hex="DEADBEEFDEADBEEF")
    r = M.call(server.find, data_hex="DEADBEEFDE", ref=f"{SCRATCH}:3000", length=16)
    hits = r.get("hits") or []
    judged("C find finds what write wrote", reply=r, holds=ok(r) and r.get("hits_total") == 1
            and len(hits) == 1 and hexint(str(hits[0]).split(":")[1]) == 0x3000)


def _c_console() -> None:
    left = M.call(server.debug, command="VGA")
    judged("C debug of a command the debugger does not take says so in its note",
           reply=left, holds=ok(left) and "did not take it" in str(left.get("note", "")))
    after = M.call(server.debug, command="BPLIST")
    regs = M.call(server.registers)
    judged("C the command after it runs on its own", reply=after,
           holds=ok(after) and "Breakpoint list" in str(after.get("output", ""))
           and "note" not in after and ok(regs))


def _c_scan() -> None:
    M.call(server.scan, method="clear")
    opened = M.call(server.scan, method="start", ref=f"{SCRATCH}:2000", length=8)
    again = M.call(server.scan, method="start", ref=f"{SCRATCH}:2000", length=8)
    judged("C scan start while a scan is open", reply=again, holds=ok(opened) and refused(again))
    M.call(server.write, ref=f"{SCRATCH}:2003", data_hex="FF")
    moved = M.call(server.scan, method="filter", operator="!")
    hits = moved.get("hits") or []
    judged("C scan ! keeps the one cell written", reply=moved,
            holds=ok(moved) and moved.get("hits_total") == 1 and len(hits) == 1
            and hexint(hits[0].get("addr")) == SCRATCH_SEG * 16 + 0x2003
            and hexint(hits[0].get("value")) == 0xFF)
    closing = M.call(server.scan, method="filter", operator="=")
    judged("C scan closing = answers its own iterations", reply=closing,
            holds=ok(closing) and closing.get("hits_total") == 0 and closing.get("closed") is True
            and closing.get("iterations") == 2)
    r = M.call(server.scan, method="clear")
    judged("C scan clear with nothing open", reply=r, holds=ok(r) and r.get("cleared") is False)


def _c_declarations(p: Probe) -> None:
    first = M.call(server.breakpoint_interrupt, number=0x21, ah=0x3D)
    again = M.call(server.breakpoint_interrupt, number=0x21, ah=0x3D)
    judged("C breakpoint_interrupt twice is already_stored", reply=again,
            holds=ok(first) and ok(again) and again.get("already_stored") is True)
    held = M.call(server.breakpoint_at, ref="0000:0010")
    alias = M.call(server.breakpoint_at, ref="0001:0000")
    judged("C a second ref on the same byte is refused", reply=alias,
            holds=ok(held) and refused(alias) and "0000:0010" in str(alias.get("message")))
    r = M.call(server.declaration_clear, kind="breakpoint", ref="0000:0999")
    judged("C declaration_clear breakpoint of an unknown ref", reply=r,
            holds=refused(r, "unknown_ref") and "0000:0010" in str(r.get("message")))
    r = M.call(server.status)
    judged("C status counts the declarations", reply=r,
            holds=ok(r) and (r.get("declarations") or {}).get("breakpoints") == 2)
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    M.setup()
    r = M.call(server.run_to, ref=p.at(p.emit), seconds=10, control=p.at(p.spin))
    # The debugger's own list, through the tool that reads it back: an entry this store never
    # declared is listed `foreign`, which is where a breakpoint `run_to` failed to remove would
    # sit. A raw `BPLIST` screen would not do: its Output pane scrolls, so the arming listing
    # from before the run is still painted above the new one.
    listed = M.call(server.declaration_list, kind="breakpoint")
    left = [str(f) for f in listed.get("foreign") or []]
    judged("C run_to arrives in the probe and removes its breakpoint", reply=r,
            holds=ok(r) and r.get("verdict") == "TARGET" and r.get("target_disarmed") is True
            and hexint(str(r.get("pc")).split(":")[-1]) == p.emit and ok(listed)
            and not any(f"{p.emit:04X}" in f and f"{p.seg:04X}" in f for f in left))


def _c_regpoints() -> None:
    bad = M.call(server.regpoint_add, condition="AX=13")
    judged("C regpoint_add refuses a term the debugger does not take, naming its shape",
           reply=bad, holds=refused(bad, "bad_argument") and "&&" in str(bad.get("message")))
    armed = M.call(server.regpoint_add, condition="bx == 0x100")
    r = M.call(server.resume, seconds=30)
    regs = r.get("regs") or {}
    cause = str(r.get("cause"))
    judged("C a registerpoint stops the guest as its condition comes true, and the stop names it",
           reply=r, holds=ok(armed) and armed.get("ref") == "BX==100" and ok(r)
           and r.get("verdict") == "OTHER_STOP" and (hexint(regs.get("EBX")) or 0) & 0xFFFF == 0x100
           and "BX==100" in cause)
    M.call(server.declaration_clear, kind="regpoint", all=True)
    M.setup()


def _c_stops(p: Probe) -> None:
    w = M.call(server.watch_add, ref=p.at(p.cnt), mode="show", fmt="char[5]")
    b = M.call(server.breakpoint_at, ref=p.at(p.pause))
    r = M.call(server.resume, seconds=10)
    watches = r.get("watches") or []
    value = str(watches[0].get("value")) if watches else ""
    judged("C a show watch rides the stop with the counter's digits", reply=r,
            holds=ok(w) and ok(b) and ok(r) and "stop_seq" in r
            and len(value.strip("'\"")) == 5 and value.strip("'\"").isdigit())
    r = M.call(server.resume, seconds=10)
    e9 = r.get("e9") or {}
    lines = e9.get("lines") or []
    judged("C the stop's e9 since the previous stop", reply=r,
            holds=ok(r) and "stop_seq" in r and bool(lines)
            and any("PROBE" in str(x) for x in lines))
    r = M.call(server.perform, steps=[{"op": "status"}, {"op": "resume"}], settle_seconds=10)
    judged("C perform ending in resume carries the stop", reply=r,
            holds=ok(r) and isinstance(r.get("stopped"), dict))
    r = M.call(server.perform, steps=[{"op": "status"}, {"op": "registers"}], summaries=True)
    judged("C perform summaries writes both files", reply=r,
            holds=ok(r) and Path(str(r.get("ran_path"))).is_file()
            and Path(str(r.get("replies_path"))).is_file())
    for label, bad in (
            ("C perform refuses a bad step before running any", {"op": "step", "count": 65}),
            ("C perform refuses read_memory length=129 before running any",
             {"op": "read_memory", "ref": "0000:0000", "length": 129})):
        r = M.call(server.perform, steps=[{"op": "status"}, bad])
        errors = r.get("errors") or []
        judged(label, reply=r,
                holds=refused(r) and r.get("ran") == [] and any(e.get("step") == 1 for e in errors))
    M.call(server.declaration_clear, kind="watch", all=True)
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    M.setup()


def _c_sequences() -> None:
    """A step that fails at its turn: a name looked up with no table loaded."""
    r = M.call(server.perform, steps=[{"op": "status"},
                                      {"op": "symbols_find", "name": "MATRIX_NO_SUCH"}])
    judged("C perform stops at a step that fails", reply=r,
            holds=refused(r, "step_failed") and r.get("failed_at") == 1
            and len(r.get("ran") or []) >= 1)
    r = M.call(server.drive, act=[{"op": "symbols_find", "name": "MATRIX_NO_SUCH"}])
    judged("C drive refuses when a step fails", reply=r, holds=refused(r))


def _c_running() -> None:
    release_running()
    M.setup()
    r = M.call(server.drive, act=[{"op": "status"}], expect=r"PROBE \. tick", seconds=15,
               pattern="PROBE")
    judged("C drive sees a new probe line", reply=r,
            holds=ok(r) and (r.get("verify") or {}).get("seen") is True)
    r = M.call(server.log_wait, pattern=r"PROBE \. tick", channel="guest", seconds=5)
    judged("C log_wait answers history at once", reply=r,
            holds=ok(r) and r.get("already") is True and r.get("waited_s") == 0.0)
    r = M.call(server.log_wait, pattern="MATRIX_NEVER_LOGGED", channel="guest", seconds=3)
    judged("C log_wait expiry is a TIMEOUT", reply=r,
           holds=ok(r) and r.get("verdict") == "TIMEOUT")


def _c_pending(p: Probe) -> None:
    """A stop the matrix can predict: a breakpoint on `.pause`, armed before the release,
    fires after the probe's next line. A breakpoint declared WHILE it runs is pending, and the first
    tool that finds the machine stopped applies it and says so."""
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    M.call(server.breakpoint_at, ref=p.at(p.pause))
    M.call(server.resume)
    M.setup()
    pend = M.call(server.breakpoint_at, ref="0000:0007")
    found: dict[str, Any] = {}
    # `status` is the only tool asked while waiting: whichever tool first finds the machine
    # stopped is the one that records the stop and applies what was pending, so a second tool
    # polled in between would take the answer this cell reads.
    for _ in range(30):
        found = M.call(server.status)
        if found.get("stopped_on_its_own"):
            break
        time.sleep(0.5)
    armed = (found.get("applied_on_stop") or {}).get("armed") or []
    judged("C declared while running applies at the next stop", reply=found,
            holds=ok(pend) and pend.get("state") == "pending"
            and bool(found.get("stopped_on_its_own"))
            and "0000:0007" in [str(a) for a in armed])
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    _c_two_families(p)
    w = M.call(server.watch_add, ref=p.at(p.cnt + 4), mode="change", length=1, fmt="u8")
    r = M.call(server.resume, seconds=10)
    judged("C a change watch on the counter stops the probe", reply=r,
            holds=ok(w) and w.get("armed") is True and ok(r) and "stop_seq" in r
            and str(r.get("pc")).split(":")[0] == f"{p.seg:04X}")
    M.call(server.declaration_clear, kind="watch", all=True)
    M.setup()


def _c_two_families(p: Probe) -> None:
    """Two families queued under one ref while the guest runs: the stop that follows arms both,
    and the debugger's own list holds both rows."""
    M.call(server.breakpoint_at, ref=p.at(p.pause))
    M.call(server.resume)
    M.setup()
    ref = "0000:0009"            # an interrupt vector's byte: nothing runs or writes it here
    w = M.call(server.watch_add, ref=ref, mode="change", length=1, fmt="u8")
    b = M.call(server.breakpoint_at, ref=ref)
    found: dict[str, Any] = {}
    for _ in range(30):
        found = M.call(server.status)
        if found.get("stopped_on_its_own"):
            break
        time.sleep(0.5)
    listing = str(M.call(server.debug, command="BPLIST").get("output", ""))
    judged("C a breakpoint and a change watch at one ref, declared while running, both armed",
           reply=found, holds=w.get("state") == "pending" and b.get("state") == "pending"
           and ref in [str(a) for a in (found.get("applied_on_stop") or {}).get("armed") or []]
           and f"BP {ref}" in listing and f"BPMEM {ref}" in listing)
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    M.call(server.declaration_clear, kind="watch", all=True)
    M.setup()


def _c_store() -> None:
    """Across `close` and `start` on the same conf, then on another. Declared on a stopped
    machine, so the row is armed before the session that owns it goes away."""
    M.call(server.breakpoint_at, ref="0000:0006")
    close_whatever()
    boot()
    M.setup()
    r = M.call(server.declaration_list, kind="breakpoint")
    row = [b for b in r.get("breakpoints") or [] if b.get("ref") == "0000:0006"]
    judged("C a raw breakpoint from another session on the same build re-arms", reply=r,
            holds=ok(r) and r.get("debugger_read") is True and len(row) == 1
            and row[0].get("state") == "armed")
    r = M.call(server.breakpoint_at, ref="0000:0006")
    judged("C declaring it again adopts it", reply=r,
           holds=ok(r) and r.get("already_stored") is True)
    close_whatever()
    other = Path(M.fresh(".conf"))
    other.write_text(PROBE_CONF.read_text(encoding="utf-8"), encoding="utf-8")
    boot(conf=other)
    M.setup()
    r = M.call(server.declaration_list, kind="breakpoint")
    judged("C another conf inherits nothing", reply=r,
            holds=ok(r) and not any(b.get("ref") == "0000:0006"
                                    for b in r.get("breakpoints") or []))
    close_whatever()


def _c_start() -> None:
    r = start_call(conf=str(PROBE_CONF), cwd=str(GUEST), session_seconds=SESSION_S,
                   state_dir=M.fresh("-save"), plan=[{"op": "status"}, {"op": "registers"}])
    judged("C start with a plan", reply=r, holds=ok(r) and isinstance(r.get("start"), dict)
            and len(r.get("ran") or []) == 2 and list(r)[-1] == "session")
    close_whatever()
    conf = conf_without_launch(PROBE_CONF, "PROBE.COM")
    log = M.fresh(".log")
    boot(conf=conf, program="PROBE.COM", logfile=log)
    release_running()
    r = M.call(server.log_wait, pattern=r"PROBE \. tick", channel="guest", seconds=30)
    judged("C start with program runs it after the autoexec", reply=r, holds=ok(r))
    close_whatever()


@M.section("C", "behaviours across calls, on the probe guest", C_CELLS)
def section_c() -> None:
    boot()
    into_dos()
    p = into_probe()
    M.setup()
    _c_memory()
    _c_console()
    _c_scan()
    _c_declarations(p)
    _c_regpoints()
    _c_stops(p)
    _c_sequences()
    _c_pending(p)
    _c_store()
    boot()
    into_dos()
    M.setup()
    _c_running()
    close_whatever()
    _c_start()


# ================================================================ H: run_for by retraces
#
# The known answer is the display's own rate: the probe guest's text mode refreshes at 70 Hz, so
# N retraces move the pane's emulated clock by N of its periods. The guest's two `loop $` are the
# hot addresses a breakpoint cuts a frame on.

#: The probe guest's text mode refresh, the rate a retrace count is judged against.
TEXT_MODE_HZ = 70
#: What a timed run is asked for. Its last retrace lands at or past the mark and under one frame
#: beyond it.
TIMED_MS = 50
#: Just past `run_for`'s wall-clock ceiling, `WAIT_MAX_S`.
PAST_THE_BOUND = 600.5

H_CELLS = cells(
    ("H run_for frames=3 lands three retraces", REF_DOC + "Advancing: a frame is one retrace"),
    ("H run_for frames=2 moves the pane clock two 70 Hz periods",
     REF_DOC + "Advancing: the pane's emulated clock; known: text mode at 70 Hz"),
    ("H status names the run_for stop", "status docstring: pc of the stop it is in"),
    ("H run_for milliseconds=50 stops on the first retrace at or past 50 ms",
     REF_DOC + "Advancing: counts the same clock, one frame of granularity"),
    ("H milliseconds=-1 is refused", "dosbox_checks: a whole number of zero or more"),
    ("H frames=0 with milliseconds=0 is refused",
     "dosbox_checks: exactly one of milliseconds and frames"),
    ("H frames and milliseconds both set is refused",
     "dosbox_checks: exactly one of milliseconds and frames"),
    ("H frames=-1 is refused", "dosbox_checks: a whole number of zero or more"),
    ("H seconds=0 is refused", "the bound scry_core.vocabulary.WAIT_MAX_S declares"),
    ("H seconds=600.5 is refused", "the bound scry_core.vocabulary.WAIT_MAX_S declares"),
    ("H a breakpoint on the guest's loop ends it OTHER_STOP",
     REF_DOC + "Advancing: OTHER_STOP, cause; known: probe.asm `.s1` and `.spin`"),
    ("H the next release stops at the pending retrace, named",
     REF_DOC + "Advancing: retrace_pending, the first stop no declaration explains"),
    ("H debug VRT is refused naming run_for", "debug docstring: a command that lets the guest "
     "run"),
    ("H a running guest is refused", "run_for docstring: needs the machine stopped"),
)


@M.section("H", "run_for by display retraces, on the probe guest", H_CELLS)
def section_h() -> None:
    boot()
    into_dos()
    p = into_probe()
    M.setup()
    r = M.call(server.run_for, frames=3)
    judged("H run_for frames=3 lands three retraces", reply=r,
           holds=ok(r) and r.get("verdict") == "ELAPSED" and r.get("polls") == 3
           and (clock_moved(r) or 0) > 0)
    r = M.call(server.run_for, frames=2)
    moved = clock_moved(r)
    M.judge("H run_for frames=2 moves the pane clock two 70 Hz periods",
            ok(r) and moved is not None
            and abs(moved - 2 / TEXT_MODE_HZ) <= 0.2 * 2 / TEXT_MODE_HZ,
            f"moved {moved} s; {said(r, 80)}")
    s = M.call(server.status)
    M.judge("H status names the run_for stop", ok(s) and s.get("pc") == r.get("pc"),
            f"status pc {s.get('pc')}, run_for at {r.get('pc')}")
    r = M.call(server.run_for, milliseconds=TIMED_MS)
    moved = clock_moved(r)
    asked = TIMED_MS / 1000
    M.judge("H run_for milliseconds=50 stops on the first retrace at or past 50 ms",
            ok(r) and r.get("verdict") == "ELAPSED" and moved is not None
            and asked <= moved < asked + 1 / TEXT_MODE_HZ,
            f"moved {moved} s over {r.get('polls')} polls; {said(r, 80)}")
    for label, kw in (("H frames=0 with milliseconds=0 is refused", {}),
                      ("H milliseconds=-1 is refused", {"milliseconds": -1}),
                      ("H frames and milliseconds both set is refused",
                       {"frames": 2, "milliseconds": 50}),
                      ("H frames=-1 is refused", {"frames": -1}),
                      ("H seconds=0 is refused", {"frames": 1, "seconds": 0}),
                      ("H seconds=600.5 is refused", {"frames": 1, "seconds": PAST_THE_BOUND})):
        r = M.call(server.run_for, exempt="refused before any wait", **kw)
        judged(label, reply=r, holds=refused(r, "bad_argument"))
    loops = (p.at(p.settle), p.at(p.spin))
    for ref in loops:
        must(M.call(server.breakpoint_at, ref=ref), f"arming the loop at {ref}")
    r = M.call(server.run_for, frames=5)
    M.judge("H a breakpoint on the guest's loop ends it OTHER_STOP",
            ok(r) and r.get("verdict") == "OTHER_STOP" and r.get("retrace_pending") is True
            and any(str(r.get("cause")).startswith(f"breakpoint {ref} ") for ref in loops),
            said(r))
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing the loops")
    must(M.call(server.breakpoint_at, ref=NEVER_RUNS_STOPPER), "arming a stopper that never fires")
    r = M.call(server.resume, seconds=5)
    M.judge("H the next release stops at the pending retrace, named",
            ok(r) and "stop_seq" in r
            and str(r.get("cause")).startswith("most likely the retrace stop"), said(r))
    r = M.call(server.debug, command="VRT")
    judged("H debug VRT is refused naming run_for", reply=r,
           holds=refused(r, "bad_argument") and "run_for" in str(r.get("message")))
    s = M.call(server.status)
    stopped = isinstance(s.get("cpu_mode"), str)
    r = M.call(server.resume) if stopped else s
    if stopped and not (ok(r) and "stop_seq" not in r):
        M.block("H a running guest is refused", f"the machine did not run: {said(r)}")
    else:
        r = M.call(server.run_for, frames=1)
        judged("H a running guest is refused", reply=r,
               holds=refused(r, "not_stopped") and alive(r))
    close_whatever()


# ================================================================ I: the DOS machine
#
# What the machine is, read from the debugger's own listings: before DOS boots, with the probe
# resident, without the logfile the listings are read from, and with the guest running.

PARK_SENTENCE = "Cannot enumerate MCB list while DOS kernel is inactive."
#: What a file the matrix plants where the debugger writes its table holds.
LEFTOVER = "a file the matrix planted\n"

I_CELLS = cells(
    ("I machine_map at the park: mcbs absent, the debugger's sentence quoted",
     REF_DOC + "Reading and writing: an absent section says why"),
    ("I machine_map with the probe resident: PROBE and COMMAND blocks, real mode, no gdt",
     "machine_map docstring; known: COMMAND.COM runs PROBE.COM, real mode"),
    ("I the debugger takes a command after the listings",
     REF_DOC + "The debugger channel: one request, the lines it printed"),
    ("I interrupt_vectors at the park: every vector 0000:0000, the debugger's sentence quoted",
     "interrupt_vectors docstring: before DOS has filled the table"),
    ("I interrupt_vectors number=0x21: F000:D100 in the DOSBox callback area",
     "interrupt_vectors docstring; known: DOS answers INT 21h from a callback"),
    ("I interrupt_vectors whole: 256 vectors, and the file is gone",
     "interrupt_vectors docstring: the server's own file is read and removed"),
    ("I interrupt_vectors number=256 is refused", "interrupt_vectors docstring: 0 to 255"),
    ("I interrupt_vectors number=-1 is refused", "interrupt_vectors docstring: 0 to 255"),
    ("I a leftover MCPIVT.TXT is refused and left in place",
     "interrupt_vectors docstring: somebody else's file is left where it is"),
    ("I machine_map on a running guest is refused", "machine_map docstring: not_stopped"),
    ("I interrupt_vectors on a running guest is refused",
     "interrupt_vectors docstring: not_stopped"),
    ("I machine_map without a logfile reads its listings all the same",
     "REFERENCE.md, The debugger channel: every reading goes through it"),
)


@M.section("I", "the DOS machine from the debugger's listings, on the probe guest", I_CELLS)
def section_i() -> None:
    boot()
    M.setup()
    r = M.call(server.machine_map)
    judged("I machine_map at the park: mcbs absent, the debugger's sentence quoted", reply=r,
           holds=ok(r) and "mcbs" not in r and PARK_SENTENCE in str(r.get("coverage_note")))
    r = M.call(server.interrupt_vectors)
    judged("I interrupt_vectors at the park: every vector 0000:0000, the debugger's sentence "
           "quoted", reply=r,
           holds=ok(r) and {v.get("seg_off") for v in r.get("vectors") or []} == {"0000:00000000"}
           and PARK_SENTENCE in str(r.get("coverage_note")))
    into_dos()
    into_probe()
    M.setup()
    r = M.call(server.machine_map)
    names = {b.get("filename") for b in r.get("mcbs") or []}
    judged("I machine_map with the probe resident: PROBE and COMMAND blocks, real mode, no gdt",
           reply=r, holds=ok(r) and {"PROBE", "COMMAND"} <= names
           and r.get("cpu_mode") == "real" and "gdt" not in r)
    r = M.call(server.interrupt_vectors, number=0x21)
    row = (r.get("vectors") or [{}])[0]
    judged("I interrupt_vectors number=0x21: F000:D100 in the DOSBox callback area", reply=r,
           holds=ok(r) and row.get("seg_off") == "F000:0000D100"
           and (row.get("bios_mem") or {}).get("what") == "DOSBox callback area")
    r = M.call(server.interrupt_vectors)
    judged("I interrupt_vectors whole: 256 vectors, and the file is gone", reply=r,
           holds=ok(r) and len(r.get("vectors") or []) == 256
           and not (GUEST / ds.INTVEC_FILE).exists())
    for n in (256, -1):
        r = M.call(server.interrupt_vectors, number=n)
        judged(f"I interrupt_vectors number={n} is refused", reply=r,
               holds=refused(r, "bad_argument"))
    planted = GUEST / ds.INTVEC_FILE
    planted.write_text(LEFTOVER)
    try:
        r = M.call(server.interrupt_vectors)
        judged("I a leftover MCPIVT.TXT is refused and left in place", reply=r,
               holds=refused(r, "bad_argument") and planted.read_text() == LEFTOVER)
    finally:
        planted.unlink()
    r = M.call(server.debug, command="BPLIST")
    judged("I the debugger takes a command after the listings", reply=r,
           holds=ok(r) and "not recognized" not in str(r.get("output"))
           and "Breakpoint list:" in str(r.get("output")))
    release_running()
    M.setup()
    r = M.call(server.machine_map)
    judged("I machine_map on a running guest is refused", reply=r,
           holds=refused(r, "not_stopped") and alive(r))
    r = M.call(server.interrupt_vectors)
    judged("I interrupt_vectors on a running guest is refused", reply=r,
           holds=refused(r, "not_stopped") and alive(r) and not (GUEST / ds.INTVEC_FILE).exists())
    close_whatever()
    boot(logfile="")
    M.setup()
    r = M.call(server.machine_map)
    judged("I machine_map without a logfile reads its listings all the same", reply=r,
           holds=ok(r) and "logfile" not in str(r.get("coverage_note")))
    close_whatever()
