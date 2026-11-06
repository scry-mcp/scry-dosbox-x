"""Section L of the live matrix: arguments judged, and the debugger's own files, on the
package's probe guest.

`memdump` past a segment's 64 KiB: the known answer is a second dump the debugger reads inside
one segment, which cannot wrap, and the control is the bytes the wrap would have given, which
differ. The debugger's own files: a link planted where it writes (`MCPDUMP.BIN`, the name
`memdump` passes; `memdump.bin`, the default of a build that takes none; `LOGCPU.TXT`),
pointing into a missing directory, at a free name, or relative, is refused before anything is
typed, and the link and its target are judged after. Every planted link and every target it
could have produced are removed by the cell that planted them.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    NO_SUCH_HOME_WHY,
    PROBE_CONF,
    SESSION_S,
    M,
    advanced,
    boot,
    cells,
    close_whatever,
    dump_to_file,
    hexint,
    must,
    no_session,
    ok,
    refused,
    said,
    server,
)

from scry_dosbox_x import paths
from scry_dosbox_x import session as ds
from scry_dosbox_x import trace as tracing

#: A `~user` no host has: the one `~` spelling the judge still refuses.
UNKNOWN_HOME = "~no-such-user-matrix"

#: The probe's own segment at its settle loop.
PROBE_SEG = 0x0814
#: The segment whose offset 0 is the probe segment's offset 0xFFF0: what lies past 0814:FFFF.
PAST_PROBE_SEG = PROBE_SEG + 0x0FFF
CONSOLE_CELL = "L the console still answers a dump after every refusal"
PROFILE_CELL = ("L start from a .scry/start profile boots the guest, the call's own "
                "cwd kept and the reply naming the file and what it filled")
PERFORM_CELL = "L perform runs find, debug and state_list as steps"
LISTED_CELL = ("L a refusal on a running guest lists breakpoint_at, stop and close as "
               "answering")
PENDING_CELL = "L a breakpoint_at step after a release answers pending, and the run stops"
CLEAR_CELL = ("L all=True clears every breakpoint, and every watch; no ref, an empty ref and "
              "both are refused")
WINDOWS_CELL = ("L memdump 0000:0000 x 1 MiB holds in windows 1, 9, 12 and 15 what each "
                "segment holds there, not window 0")
#: Places in four windows of the megabyte whose bytes are not zero on the probe (the program
#: past its 64 KiB, the top of conventional memory, the video BIOS, the system BIOS): a window
#: of zeros, or window 0 again, cannot pass for any of them.
WINDOW_PROBES = ("1813:0000", "9FFF:0000", "C000:0000", "F8DB:0000")

L_CELLS = cells(
    (WINDOWS_CELL,
     "memdump docstring: real-mode windows; known: a dump inside one segment cannot wrap"),
    ("L memdump 0814:FFF0 x 0x20 equals 1813:0000 x 0x20, not the wrap to 0814:0000",
     "memdump docstring: real-mode windows; known: the same linear bytes"),
    ("L memdump past FFFF:FFFF is refused and writes nothing",
     "memdump docstring: up to FFFF:FFFF"),
    ("L a dangling MCPDUMP.BIN into a missing directory is refused, nothing written",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a dangling MCPDUMP.BIN to a free name is refused, nothing written",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a dangling memdump.bin into a missing directory is refused, nothing written",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a dangling memdump.bin to a free name is refused, nothing written",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a dangling LOGCPU.TXT into a missing directory is refused before LOG",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a dangling LOGCPU.TXT to a free name is refused before LOG",
     "REFERENCE.md, The session: a dangling link is a file there"),
    ("L a relative dangling LOGCPU.TXT is refused before LOG",
     "REFERENCE.md, The session: a dangling link is a file there"),
    (CONSOLE_CELL, "debug docstring: refused `bad_argument` before anything is typed"),
    ("L start with cwd from an unknown ~user is refused naming cwd, nothing started",
     "start docstring: every path is absolute or `~`-led, `~` expanded"),
    ("L start with a relative conf is refused naming conf, nothing started",
     "start docstring: every path is absolute"),
    ("L start(savedir=) is refused by the schema", "start docstring: `state_dir`"),
    ("L status and state_list name state_dir, and no savedir",
     "status docstring: state_dir; state_list docstring"),
    ("L every dest relative or from an unknown ~user is refused, nothing written",
     "REFERENCE.md, The session: every path you give is absolute or starts with `~`"),
    ("L a dest that is a dangling link is refused and nothing written through it",
     "REFERENCE.md, The session: nothing at a file a tool writes, a dangling link included"),
    ("L with no session, a value wrong with no machine answers bad_argument, never no_session",
     "REFERENCE.md, What every reply carries: judged before the session gate"),
    (CLEAR_CELL,
     "declaration_clear breakpoint and declaration_clear watch docstrings: all with `all=True`; "
     "neither `ref` "
                 "nor `all`, or both, is `bad_argument`"),
    (PERFORM_CELL, "perform docstring: every tool but `build_check`, `start`, `close`, "
                   "`perform`, `drive` and `perform_export` is a step"),
    (LISTED_CELL, "REFERENCE.md, Sequences in one call: the one table"),
    (PENDING_CELL, "perform docstring: after a `resume` the steps `answers_while_running` lists "
                   "run at once; breakpoint_at docstring: `pending` while the guest is running"),
    (PROFILE_CELL, "start docstring: `profile`, and the reply's `profile` block"),
)
#: Each wrong with no machine at all: a state name, a scan, a register, a bound, a list.
NO_MACHINE_NEEDED: tuple[tuple[str, dict[str, Any]], ...] = (
    ("state_write", {"method": "save", "name": "abc\n", "seconds": 5}), ("state_write",
                                                                         {"method": "load",
                                                                          "name": "1",
                                                                          "seconds": 5}),
    ("state_write", {"method": "save", "name": "a" * 65, "seconds": 5}), ("scan",
                                                                          {"method": "filter",
                                                                           "operator": "?"}),
    ("scan", {"method": "start", "ref": "0000:0400", "length": 3, "cell_bytes": 2}),
    ("set_register", {"name": "ax", "value": 0x10000}), ("resume", {"seconds": -1}),
    ("run_to", {"ref": "0000:0100", "control": ""}),
    ("breakpoint_at", {"ref": "[g_p]", "by": "pointer"}),
    ("perform", {"steps": [{"op": "nope"}]}), ("drive", {"act": [], "limit": 0}))
#: Every tool that writes a `dest`, with the rest of a call that would otherwise run.
DEST_TOOLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("memdump", {"ref": f"{PROBE_SEG:04X}:0000", "length": 0x10}),
    ("trace", {"instructions": 16, "shape": "cs_ip", "seconds": 30}),
    ("palette", {}), ("screen_view", {}), ("snapshot", {}), ("capture_frame", {"frame": 0}))


@contextmanager
def planted(name: str, target: Path) -> Iterator[tuple[Path, Path]]:
    """A link named `name` in the guest's directory, pointing at `target`; the link, and
    whatever a write through it produced, are removed after. Yields the link and where its
    target resolves."""
    link = GUEST / name
    landed = target if target.is_absolute() else GUEST / target
    os.symlink(target, link)
    try:
        yield link, landed
    finally:
        link.unlink(missing_ok=True)
        if landed.is_file():
            landed.unlink()


def _leftovers() -> list[Path]:
    names = (ds.MEMDUMP_FILE, ds.MEMDUMP_NAME, ds.MEMDUMP_NAME.upper(), tracing.LOG_FILE,
             tracing.LOG_FILE.lower())
    return [GUEST / n for n in names if paths.taken(GUEST / n)]


@M.section("L", "arguments judged, and the debugger's own files", L_CELLS)
def section_l() -> None:
    left = _leftovers()
    if left:
        M.block_rest(f"{left[0]} is already in the guest's directory: somebody's, never touched")
        return
    _start_refusals()
    _no_machine_needed()
    state_dir = Path(M.fresh("-states"))
    boot(state_dir=str(state_dir))
    settle = advanced(M.call(server.run_for, frames=2), "into the settle loop")
    if hexint(str(settle.get("pc")).split(":")[0]) != PROBE_SEG:
        M.block_rest(f"run_for(frames=2) did not stop in the probe's segment: {said(settle)}")
        return
    M.setup()
    _windows()
    _links()
    _state_dir_named(state_dir)
    _dests()
    _empty_ref_clears()
    _running_table()
    r, data = dump_to_file(f"{PROBE_SEG:04X}:0000", 0x10)
    M.judge(CONSOLE_CELL, ok(r) and data is not None and len(data) == 0x10, said(r))
    _profile()


def _profile() -> None:
    """A store of this run's own, holding the guest as a path relative to it, found by `cwd`;
    the section's own session is closed first, since one guest at a time is the server's rule."""
    close_whatever()
    root = Path(M.fresh("-store"))
    shutil.copytree(GUEST, root / "guest")
    store = root / ".scry" / "start"
    store.mkdir(parents=True)
    entry = store / "probe-profile.json"
    entry.write_text(json.dumps({"format": "scry-start/1", "conf": "guest/probe.conf",
                                 "cwd": "guest", "session_seconds": SESSION_S,
                                 "presence": False}), encoding="utf-8")
    r = start_through_the_schema(profile="probe-profile", cwd=str(root / "guest"))
    raw = r.get("profile")
    shown: dict[str, Any] = raw if isinstance(raw, dict) else {}
    shown_file = Path(str(shown.get("file", "")))
    M.judge(PROFILE_CELL, ok(r) and shown_file.resolve() == entry.resolve()
            and shown.get("supplied") == ["conf", "presence", "session_seconds"]
            and isinstance(r.get("pid"), int), said(r))
    close_whatever()


def start_through_the_schema(**arguments: object) -> dict[str, object]:
    """`start` as a client calls it, through the MCP schema, which is what refuses an argument
    the tool does not take; the reply in this server's envelope."""
    res = asyncio.run(server.mcp.call_tool("start", arguments))
    reply: dict[str, object] = json.loads(
        "".join(getattr(c, "text", "") for c in res.content))
    return reply


def _start_refusals() -> None:
    """With no session yet, so each refusal is the path's and never `session_live`; a start
    that came up instead of refusing is closed at once, so the next cell judges its own call."""
    # A `~` IS EXPANDED, so the refusal left to judge is a home this host cannot find.
    if NO_SUCH_HOME_WHY:
        M.block("L start with cwd from an unknown ~user is refused naming cwd, nothing started",
                NO_SUCH_HOME_WHY)
    else:
        r = M.call(server.start, conf=str(PROBE_CONF), cwd=f"{UNKNOWN_HOME}/x",
                   session_seconds=60)
        _close_if_up(r)
        M.judge("L start with cwd from an unknown ~user is refused naming cwd, nothing started",
                refused(r, "bad_argument") and "cwd=" in str(r.get("message"))
                and "home directory this host cannot find" in str(r.get("message"))
                and no_session(r), said(r))
    r = M.call(server.start, conf="probe.conf", cwd=str(GUEST), session_seconds=60)
    _close_if_up(r)
    M.judge("L start with a relative conf is refused naming conf, nothing started",
            refused(r, "bad_argument") and "conf='probe.conf'" in str(r.get("message"))
            and no_session(r), said(r))
    r = M.call(start_through_the_schema, conf=str(PROBE_CONF), cwd=str(GUEST),
               session_seconds=60, savedir=M.fresh("-states"))
    _close_if_up(r)
    M.judge("L start(savedir=) is refused by the schema",
            refused(r, "bad_argument") and "savedir" in str(r.get("message"))
            and no_session(r), said(r))


def _close_if_up(r: dict[str, Any]) -> None:
    if ok(r):
        M.call(server.close)


def _no_machine_needed() -> None:
    wrong = []
    for tool, kw in NO_MACHINE_NEEDED:
        r = M.call(getattr(server, tool), **kw)
        if not refused(r, "bad_argument"):
            wrong.append(f"{tool}({kw}): {said(r, 60)}")
    M.judge("L with no session, a value wrong with no machine answers bad_argument, never "
            "no_session", not wrong, "; ".join(wrong) or f"{len(NO_MACHINE_NEEDED)} refused")


def _empty_ref_clears() -> None:
    """Two breakpoint declarations and two watches, each family cleared whole by `all=True`, the
    other left alone until its own broom; an empty ref, no scope at all and both are refused and
    clear nothing."""
    cs = f"{PROBE_SEG:04X}"
    for r in (M.call(server.breakpoint_at, ref=f"{cs}:0108"),
              M.call(server.breakpoint_interrupt, number=0x60),
              M.call(server.watch_add, ref=f"{cs}:0100", mode="show", length=2),
              M.call(server.watch_add, ref=f"{cs}:0102", mode="show", length=2)):
        must(r, "declaring before the brooms")
    unscoped = [M.call(server.declaration_clear, kind="breakpoint", ref=""),
                M.call(server.declaration_clear, kind="breakpoint"),
                M.call(server.declaration_clear, kind="breakpoint", ref="x", all=True),
                M.call(server.declaration_clear, kind="watch", ref=""),
                M.call(server.declaration_clear, kind="watch"),
                M.call(server.declaration_clear, kind="watch", ref="x", all=True)]
    kept = M.call(server.declaration_list, kind="watch")
    bps = M.call(server.declaration_clear, kind="breakpoint", all=True)
    left = M.call(server.declaration_list, kind="watch")
    ws = M.call(server.declaration_clear, kind="watch", all=True)
    after = M.call(server.declaration_list, kind="breakpoint")
    M.judge(CLEAR_CELL,
            all(refused(r, "bad_argument") for r in unscoped)
            and len(kept.get("watches") or []) == 2
            and ok(bps) and bps.get("declarations_cleared") == 2 and ok(ws)
            and ws.get("declarations_cleared") == 2 and len(left.get("watches") or []) == 2
            and ok(after) and not after.get("breakpoints"),
            f"{said(bps, 60)}; {said(ws, 60)}")


def _probe_offset(name: str) -> int:
    """An offset the probe's own symbol file names."""
    for line in (GUEST / "probe.sym").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields[-1:] == [name]:
            return int(fields[0], 16)
    raise LookupError(f"probe.sym names no {name}")


def _running_table() -> None:
    """Every tool is a step, and what answers on a running guest is one table. A breakpoint on
    `.pause` stops the probe after each of its lines, about three seconds apart, which is the
    window the running cells are asked in."""
    def at(off: int) -> str:
        return f"{PROBE_SEG:04X}:{off:04X}"
    body = (GUEST / "probe.com").read_bytes()
    pause = 0x100 + body.index(bytes.fromhex("BBBC02"))     # `mov bx, 700`, after a line
    r = M.call(server.perform, steps=[
        {"op": "find", "data_hex": "5B2B20", "ref": at(0x100), "length": 0x100},
        {"op": "debug", "command": "BPLIST"}, {"op": "state_list"}])
    M.judge(PERFORM_CELL, ok(r) and [s.get("op") for s in r.get("ran") or []]
            == ["find", "debug", "state_list"], said(r))
    must(M.call(server.breakpoint_at, ref=at(pause)), "a stopper after the next line")
    must(M.call(server.resume), "released")
    r = M.call(server.registers)
    M.judge(LISTED_CELL, refused(r, "not_stopped") and {"breakpoint_at", "stop", "close"}
            <= set(r.get("answers_while_running") or []), said(r))
    found: dict[str, Any] = {}
    for _ in range(30):
        found = M.call(server.status)
        if found.get("stopped_on_its_own"):
            break
        time.sleep(0.5)
    if not found.get("stopped_on_its_own"):
        M.block_rest(f"the probe did not stop at .pause: {said(found)}")
        return
    r = M.call(server.perform, steps=[
        {"op": "resume"}, {"op": "breakpoint_at", "ref": at(_probe_offset("start"))}],
        settle_seconds=10)
    ran = r.get("ran") or []
    declared = ran[1].get("reply") or {} if len(ran) > 1 else {}
    M.judge(PENDING_CELL, ok(r) and declared.get("state") == "pending"
            and bool(r.get("stopped")), said(r))
    M.call(server.declaration_clear, kind="breakpoint", all=True)


def _state_dir_named(state_dir: Path) -> None:
    st = M.call(server.status)
    listed = M.call(server.state_list)
    M.judge("L status and state_list name state_dir, and no savedir",
            ok(st) and ok(listed) and st.get("state_dir") == str(state_dir)
            and "savedir" not in st and listed.get("state_dir") == str(state_dir)
            and "savedir" not in listed, f"{st.get('state_dir')}; {said(listed, 60)}")


def _dests() -> None:
    refusals: list[str] = []
    spellings = ("relative.out",) if NO_SUCH_HOME_WHY else (
        "relative.out", f"{UNKNOWN_HOME}/matrix-tilde.out")
    for spelled in spellings:
        for tool, kw in DEST_TOOLS:
            r = M.call(getattr(server, tool), **kw, dest=spelled)
            if not refused(r, "bad_argument") or f"dest='{spelled}'" not in str(r.get("message")):
                refusals.append(f"{tool}({spelled}): {said(r, 60)}")
    stray = [p for p in (GUEST / "relative.out",) if paths.taken(p)]
    M.judge("L every dest relative or from an unknown ~user is refused, nothing written",
            not refusals and not stray, "; ".join(refusals + [str(p) for p in stray]) or "all")
    for p in stray:              # a regression wrote them; they are this cell's, not the tree's
        p.unlink()
    target = Path(M.fresh("-nowhere")) / "x"
    link = Path(M.fresh(".bin"))
    os.symlink(target, link)
    try:
        r = M.call(server.memdump, ref=f"{PROBE_SEG:04X}:0000", length=0x10, dest=str(link))
        M.judge("L a dest that is a dangling link is refused and nothing written through it",
                refused(r, "bad_argument") and "already exists" in str(r.get("message"))
                and link.is_symlink() and not target.exists(), said(r))
    finally:
        link.unlink(missing_ok=True)


def _windows() -> None:
    whole, data = dump_to_file("0000:0000", 0x100000)
    wrong: list[str] = []
    for ref in WINDOW_PROBES:
        seg = int(ref.split(":")[0], 16)
        at = seg * 16
        r, piece = dump_to_file(ref, 0x100)
        if not ok(r) or piece is None or not any(piece):
            wrong.append(f"{ref}: {said(r, 40)}, nonzero={piece is not None and any(piece)}")
        elif data is None or data[at:at + 0x100] != piece or piece == data[at & 0xFFFF:][:0x100]:
            wrong.append(f"{ref}: the 1 MiB dump at {at:#x} is not it, or is window 0's")
    M.judge(WINDOWS_CELL,
            ok(whole) and data is not None and len(data) == 0x100000 and not wrong,
            "; ".join(wrong) or said(whole, 60))
    across, wrapped = dump_to_file(f"{PROBE_SEG:04X}:FFF0", 0x20)
    after, truth = dump_to_file(f"{PAST_PROBE_SEG:04X}:0000", 0x20)
    start, head = dump_to_file(f"{PROBE_SEG:04X}:0000", 0x10)
    M.judge("L memdump 0814:FFF0 x 0x20 equals 1813:0000 x 0x20, not the wrap to 0814:0000",
            ok(across) and ok(after) and ok(start) and wrapped is not None and truth is not None
            and wrapped == truth and head is not None and truth[0x10:] != head,
            f"{said(across, 60)}; {said(after, 60)}")
    dest = Path(M.fresh(".bin"))
    r = M.call(server.memdump, ref="FFFF:0010", length=0x10000, dest=str(dest))
    M.judge("L memdump past FFFF:FFFF is refused and writes nothing",
            refused(r, "bad_argument") and "FFFF:FFFF" in str(r.get("message"))
            and not dest.exists() and not _leftovers(), said(r))


def _links() -> None:
    for name, label, target in (
            (ds.MEMDUMP_FILE,
             "L a dangling MCPDUMP.BIN into a missing directory is refused, nothing written",
             Path(M.fresh("-nowhere")) / "x"),
            (ds.MEMDUMP_FILE, "L a dangling MCPDUMP.BIN to a free name is refused, nothing written",
             Path(M.fresh(".free"))),
            (ds.MEMDUMP_NAME,
             "L a dangling memdump.bin into a missing directory is refused, nothing written",
             Path(M.fresh("-nowhere")) / "x"),
            (ds.MEMDUMP_NAME, "L a dangling memdump.bin to a free name is refused, nothing written",
             Path(M.fresh(".free"))),
    ):
        with planted(name, target) as (link, landed):
            dest = Path(M.fresh(".bin"))
            r = M.call(server.memdump, ref=f"{PROBE_SEG:04X}:0000", length=0x10, dest=str(dest))
            M.judge(label, refused(r, "bad_argument") and link.is_symlink()
                    and not landed.exists() and not dest.exists() and not dest.is_symlink(),
                    said(r))
    for label, target in (
            ("L a dangling LOGCPU.TXT into a missing directory is refused before LOG",
             Path(M.fresh("-nowhere")) / "x"),
            ("L a dangling LOGCPU.TXT to a free name is refused before LOG",
             Path(M.fresh(".free"))),
            ("L a relative dangling LOGCPU.TXT is refused before LOG",
             Path(f"matrix-rel-{os.getpid()}.txt")),
    ):
        with planted(tracing.LOG_FILE, target) as (link, landed):
            deeper = Path(M.fresh("-deeper")) / "still"
            deeper.mkdir(parents=True)
            r = M.call(server.trace, instructions=16, shape="cs_ip",
                       dest=str(deeper / "l.trace"), seconds=30)
            M.judge(label, refused(r, "bad_argument")
                    and "already sitting at" in str(r.get("message")) and link.is_symlink()
                    and not landed.exists() and not (deeper / "l.trace").exists(), said(r))
