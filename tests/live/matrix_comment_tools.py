"""Section N of the live matrix: the five comment tools on the probe guest, and the cells sections
D and F call for dos-real16 (a comment by symbol follows a rebuilt map, a raw one keeps its
batch) and the DPMI guest (one place through three spellings in protected mode).

The known answers are the probe's own (`probe.sym` at 8140 puts `start` at 0000824B) and the
comment file's format, whose expected bytes each cell builds from the rows the store answered,
never from a file the server wrote. Every section deletes the comments it made and clears the
breakpoints it declared before it ends: the store is the conf's and outlives the run.
"""
from __future__ import annotations

import contextlib
import os
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import bench_programs as bp
from matrix_common import (
    GUEST,
    M,
    advanced,
    boot,
    cells,
    judged,
    must,
    ok,
    refused,
    release_running,
    said,
    server,
)
from scry_core import prose

from scry_dosbox_x import state as dstate

HEADER = "# comments v1: ref\tcpu\tcreated_at\ttext"
#: A call that types at a running guest waits for a pane that never comes; one that types
#: nothing answers at once. The bound sits between the two.
UNTYPED_S = 2.0

N_CELLS = cells(
    ("N comment_write add by start lands at 0000824B, resolved", "known: probe.sym at 8140"),
    ("N 0824:000B, the same byte, replaces the text and keeps the ref start",
     "comment_write add: docstring at one comment per place"),
    ("N a raw 0814:0106 comment lands at 00008246",
     "REFERENCE.md, Breakpoints and watches: real mode"),
    ("N comment_list holds the two, each resolved", "comment_list docstring"),
    ("N disassemble ends each commented line with its text, and only those",
     "disassemble docstring: a line a comment is placed on ends ` // <text>`"),
    ("N status declarations do not count a comment", "REFERENCE.md, Breakpoints and watches"),
    ("N comment_write save writes the header and the two rows the contract spells",
     "REFERENCE.md, Breakpoints and watches: the comment file"),
    ("N deleted, loaded back and saved again, the file is byte for byte the same",
     "comment_write load docstring: the file a save wrote loads back whole"),
    ("N a second delete of the same ref is unknown_ref", "comment_write delete docstring"),
    ("N a bad text is refused: empty, a tab, an edge blank, 238 bytes",
     "comment_write add: docstring at one printable line, at most 237 UTF-8 bytes"),
    ("N a bad ref is refused: [g]+2, start+2, 0x824B, 0814:01G0",
     "comment_write add: docstring at no pointer, no symbol+offset, no 0x number"),
    ("N relative and unknown-~user paths are refused for save and load",
     "every path here is absolute or `~`-led"),
    ("N save refuses the store's own file, a FIFO and a file that is not a comment file, "
     "leaving each as it was", "comment_write save docstring"),
    ("N perform runs comment steps", "REFERENCE.md, Several calls as one"),
    ("N on a running guest list and save answer at once, asking the debugger nothing",
     "comment_list and comment_write save docstrings: they answer on a running guest"),
    ("N on a running guest add, delete and load are refused not_stopped",
     "their docstrings: they need the machine stopped"),
    ("N the comment outlives the session and is deleted in the next",
     "REFERENCE.md, Breakpoints and watches: the store is the conf's, on disk"),
)

DOS_REAL16_COMMENT_CELLS = (
    ("D a comment by COMPOSE_FRAME follows the symbol to the rebuilt map",
     "REFERENCE.md, Breakpoints and watches: a symbol follows a rebuild; known: the map copy moves "
     "COMPOSE_FRAME by 10h"),
    ("D a raw comment stays resolved over the rebuilt map loaded in the same session",
     "REFERENCE.md, Breakpoints and watches: a raw address is judged by the batch that "
     "describes it, still held"),
)
DPMI_COMMENT_CELLS = (
    ("F a comment by _tick and CS:offset are one place, the ref kept",
     "REFERENCE.md, Breakpoints and watches: protected mode through the selector's base"),
    ("F DS:offset is that place when DS has CS's base, another when not",
     "REFERENCE.md, Breakpoints and watches: the place is the linear address"),
    ("F comment_write save, delete, comment_write load, comment_write save: the same bytes",
     "comment_write load docstring: the file a save wrote loads back whole"),
)


def _expected(rows: list[dict[str, Any]]) -> bytes:
    """The comment file the contract spells for these listed rows: header, rows sorted by ref."""
    body = "".join(f"{r['ref']}\t\t{r['created_at']}\t{r['text']}\n"
                   for r in sorted(rows, key=lambda r: str(r["ref"])))
    return f"{HEADER}\n{body}".encode()


def _listed() -> list[dict[str, Any]]:
    return list(must(M.call(server.comment_list), "listing the comments").get("comments") or [])


def _taken(refs: set[str], linears: set[int]) -> list[str]:
    """The comments the store already holds under one of `refs` or at one of `linears`: a cell
    that would replace one of them blocks instead, so a project's own comments are never
    rewritten or deleted by a run."""
    return [f"{r['ref']} at {r.get('addr')}" for r in _listed()
            if r["ref"] in refs
            or (isinstance(r.get("addr"), str) and int(r["addr"], 16) in linears)]


def _delete_mine(mine: set[str]) -> None:
    for ref in sorted(mine & {str(r["ref"]) for r in _listed()}):
        must(M.call(server.comment_write, method="delete", ref=ref), f"deleting the comment {ref}")


def _round_trip(refs: set[str]) -> tuple[bool, str]:
    """Save, delete `refs`, load the file, save again: the two files equal byte for byte."""
    first, second = Path(M.fresh("-comments.tsv")), Path(M.fresh("-comments.tsv"))
    saved = M.call(server.comment_write, method="save", dest=str(first))
    for ref in sorted(refs):
        M.call(server.comment_write, method="delete", ref=ref)
    loaded = M.call(server.comment_write, method="load", path=str(first))
    again = M.call(server.comment_write, method="save", dest=str(second))
    same = ok(saved) and ok(loaded) and ok(again) and first.read_bytes() == second.read_bytes()
    return same, (f"save {said(saved, 50)}; load {said(loaded, 60)}; "
                  f"{'equal' if same else 'differ'}")


@M.section("N", "the comment tools on the probe guest", N_CELLS)
def section_n() -> None:
    boot()
    M.setup()
    advanced(M.call(server.run_for, frames=1), "a retrace into the probe's settle loop")
    must(M.call(server.symbols_load, path=str(GUEST / "probe.sym"), base="0x8140"),
         "loading probe.sym")
    taken = _taken({"start", "0814:0106", "emit"}, {0x824B, 0x8246, 0x8277})
    if taken:
        M.block_rest(f"the probe conf's store already comments these places: {taken}")
        return
    counted = must(M.call(server.status), "status").get("declarations")
    if not isinstance(counted, dict):
        raise RuntimeError(f"status carries no declarations count to hold a comment against: "
                           f"{counted!r}")
    mine = {"start", "0814:0106"}
    restarted = False
    try:
        _known_answers(counted)
        _refusals()
        r = M.call(server.perform, steps=[{"op": "comment_write", "method": "add", "ref": "emit",
                                           "text": "out"},
                                          {"op": "comment_list"}])
        judged("N perform runs comment steps", reply=r,
               holds=ok(r) and r.get("steps_completed") == 2)
        mine.add("emit")
        _running()
    finally:
        M.setup()
        if dstate.STATE.session is None or not dstate.STATE.session.at_debugger():
            M.call(server.close)
            boot()
            restarted = True
            M.setup()
        left = {str(r["ref"]) for r in _listed()} & mine
        _delete_mine(mine)
        gone = not ({str(r["ref"]) for r in _listed()} & mine)
        must(M.call(server.declaration_clear, kind="breakpoint", all=True),
             "clearing this section's breakpoints")
        if restarted:
            M.judge("N the comment outlives the session and is deleted in the next",
                    bool(left) and gone, f"held after the new start: {sorted(left)}")
        else:
            M.block("N the comment outlives the session and is deleted in the next",
                    "the section stopped before the running cells closed the session")
        must(M.call(server.close), "closing the probe")


def _known_answers(counted: object) -> None:
    a = M.call(server.comment_write, method="add", ref="start", text="entry")
    judged("N comment_write add by start lands at 0000824B, resolved", reply=a,
           holds=ok(a) and (a.get("comment") or {}).get("addr") == "0x0000824b"
           and (a.get("comment") or {}).get("state") == "resolved")
    b = M.call(server.comment_write, method="add", ref="0824:000B", text="entry, aliased")
    judged("N 0824:000B, the same byte, replaces the text and keeps the ref start", reply=b,
           holds=ok(b) and (b.get("comment") or {}).get("ref") == "start"
           and [r.get("text") for r in b.get("replaced_comments") or []] == ["entry"])
    c = M.call(server.comment_write, method="add", ref="0814:0106", text="the settle loop")
    judged("N a raw 0814:0106 comment lands at 00008246", reply=c,
           holds=ok(c) and (c.get("comment") or {}).get("addr") == "0x00008246")
    rows = [r for r in _listed() if r["ref"] in ("start", "0814:0106")]
    M.judge("N comment_list holds the two, each resolved",
            len(rows) == 2 and all(r.get("state") == "resolved" for r in rows), str(rows)[:160])
    d = M.call(server.disassemble, ref="0814:0106", length=8)
    lines = [str(x) for x in d.get("lines") or []]
    # The eight bytes are the settle loop's three instructions and `start`'s first.
    judged("N disassemble ends each commented line with its text, and only those", reply=d,
           holds=ok(d) and len(lines) == 4 and lines[0].endswith(" // the settle loop")
           and lines[3].endswith(" // entry, aliased")
           and not any(" // " in x for x in lines[1:3]))
    s = M.call(server.status)
    judged("N status declarations do not count a comment", reply=s,
           holds=ok(s) and s.get("declarations") == counted)
    first = Path(M.fresh("-comments.tsv"))
    saved = M.call(server.comment_write, method="save", dest=str(first))
    others = [r for r in _listed() if r["ref"] not in ("start", "0814:0106")]
    want = _expected(rows + others)
    M.judge("N comment_write save writes the header and the two rows the contract spells",
            ok(saved) and first.exists() and first.read_bytes() == want,
            f"{said(saved, 60)}; {first.read_bytes()[:120]!r}" if first.exists() else said(saved))
    for ref in ("start", "0814:0106"):
        must(M.call(server.comment_write, method="delete", ref=ref), f"deleting {ref}")
    loaded = M.call(server.comment_write, method="load", path=str(first))
    second = Path(M.fresh("-comments.tsv"))
    again = M.call(server.comment_write, method="save", dest=str(second))
    M.judge("N deleted, loaded back and saved again, the file is byte for byte the same",
            ok(loaded) and loaded.get("added") == 2 and ok(again)
            and second.read_bytes() == first.read_bytes(), said(loaded, 80))
    must(M.call(server.comment_write, method="delete", ref="0814:0106"), "deleting the raw comment")
    twice = M.call(server.comment_write, method="delete", ref="0814:0106")
    judged("N a second delete of the same ref is unknown_ref", reply=twice,
           holds=refused(twice, "unknown_ref"))
    must(M.call(server.comment_write, method="add", ref="0814:0106", text="the settle loop"),
         "re-adding")


def _refusals() -> None:
    texts = ["", "a\tb", " edge", "x" * 238]
    got = [M.call(server.comment_write, method="add", ref="start", text=t) for t in texts]
    M.judge("N a bad text is refused: empty, a tab, an edge blank, 238 bytes",
            all(refused(r, "bad_argument") for r in got), "; ".join(said(r, 40) for r in got))
    refs = ["[g]+2", "start+2", "0x824B", "0814:01G0"]
    got = [M.call(server.comment_write, method="add", ref=r, text="x") for r in refs]
    M.judge("N a bad ref is refused: [g]+2, start+2, 0x824B, 0814:01G0",
            all(refused(r, "bad_argument") for r in got), "; ".join(said(r, 40) for r in got))
    got = [M.call(server.comment_write, method="save", dest=p) for p in ("c.tsv",
                                                                         "~no-such-user-matrix/c.tsv")]
    got += [M.call(server.comment_write, method="load", path=p) for p in ("c.tsv",
                                                                          "~no-such-user-matrix/c.tsv")]
    M.judge("N relative and unknown-~user paths are refused for save and load",
            all(refused(r, "bad_argument") for r in got), "; ".join(said(r, 40) for r in got))
    store = Path(str(must(M.call(server.comment_list), "the store's path")["declarations"]["path"]))
    fifo = Path(M.fresh(".fifo"))
    if sys.platform != "win32":
        os.mkfifo(fifo)
    notes = Path(M.fresh(".txt"))
    notes.write_bytes(b"somebody's notes\n")
    before = store.read_bytes()
    label = ("N save refuses the store's own file, a FIFO and a file that is not a comment file, "
             "leaving each as it was")
    if sys.platform == "win32":
        M.block(label, "Windows has no FIFO")
    else:
        got = [M.call(server.comment_write, method="save", dest=str(p))
               for p in (store, fifo, notes)]
        M.judge(label, all(refused(r, "bad_argument") for r in got)
                and store.read_bytes() == before
                and notes.read_bytes() == b"somebody's notes\n" and fifo.is_fifo(),
                "; ".join(said(r, 40) for r in got))


@contextlib.contextmanager
def _typed() -> Iterator[list[str]]:
    """Every request the block sends the debugger, through the session's one channel to it."""
    session = dstate.STATE.session
    if session is None:
        raise RuntimeError("no session to count the requests of")
    channel = session.control
    real = channel.request
    sent: list[str] = []

    def counted(command: str, *args: Any, **kwargs: Any) -> tuple[bool, list[str]]:
        sent.append(command)
        return real(command, *args, **kwargs)
    channel.request = counted  # type: ignore[method-assign]
    try:
        yield sent
    finally:
        del channel.request


def _running() -> None:
    """The guest released with a stopper that never runs: list and save timed and the requests
    they send the debugger counted, the run-state question aside, against a stopped reader that
    must send one (the counter's control); add, delete and load refused."""
    with _typed() as control:
        M.call(server.read_memory, ref="0000:0400", length=2)
    release_running()
    M.setup()
    timed: list[tuple[dict[str, Any], float, int]] = []
    for fn, kw in ((server.comment_list, {}),
                   (server.comment_write, {"method": "save", "dest": M.fresh("-comments.tsv")})):
        t0 = time.monotonic()
        with _typed() as writes:
            r = M.call(fn, **kw)
        timed.append((r, time.monotonic() - t0,
                      sum(1 for w in writes if w != "EXEC RUNSTATE")))
    M.judge("N on a running guest list and save answer at once, asking the debugger nothing",
            bool(control) and all(ok(r) and dt < UNTYPED_S and n == 0 for r, dt, n in timed)
            and timed[0][0]["session"]["running"] is True,
            f"control sent {len(control)}; "
            + "; ".join(f"{said(r, 40)} in {dt:.2f}s, sent {n}" for r, dt, n in timed))
    got = [M.call(server.comment_write, method="add", ref="bump", text="x"),
           M.call(server.comment_write, method="delete", ref="start"),
           M.call(server.comment_write, method="load", path=str(GUEST / "probe.sym"))]
    M.judge("N on a running guest add, delete and load are refused not_stopped",
            all(refused(r, "not_stopped") for r in got), "; ".join(said(r, 40) for r in got))
    M.setup()
    must(M.call(server.close), "closing the running guest")


# -------------------------------------------------------------------- the program cells

#: COMPOSE_FRAME's public line, whatever build placed it: frame, offset, the gap, the name.
_MAP_LINE = re.compile(r"^( [0-9A-F]{4}:)([0-9A-F]{5})(\s+COMPOSE_FRAME)$", re.MULTILINE)


def dos_real16_comments(mapf: Path, base: str) -> None:
    """A copy of the map with COMPOSE_FRAME 10h later stands in for a rebuild: the map itself is
    never written. Loaded, the symbol comment moves with it, and a raw comment at the place
    the symbol now reaches stays resolved: the real map's batch that described it is still held,
    and one session runs one program; the real map loaded again brings the symbol back."""
    labels = [c[0] for c in DOS_REAL16_COMMENT_CELLS]
    text = mapf.read_text(encoding="latin-1")
    # Its two lines, by name and by value, at one place: both move, or there is no rebuild.
    places = {m.group(1) + m.group(2) for m in _MAP_LINE.finditer(text)}
    shifted, n = _MAP_LINE.subn(lambda m: f"{m.group(1)}{int(m.group(2), 16) + 0x10:05X}"
                                          f"{m.group(3)}", text)
    if n != 2 or len(places) != 1:
        for label in labels:
            M.block(label, f"the map names COMPOSE_FRAME {prose.counted(n, 'time')} at "
                           f"{sorted(places)}, not the two lines at one place the copy "
                           "moves: no rebuild to load")
        return
    moved = M.tmp("dosbox-x-matrix-") / Path(bp.DOS_REAL16.map).name
    moved.write_text(shifted, encoding="latin-1")
    here = must(M.call(server.symbols_find, name="COMPOSE_FRAME"), "COMPOSE_FRAME")
    linear = int(here["symbols"][0]["addr"], 16)
    after = linear + 0x10
    raw = f"{after >> 4:04X}:{after & 0xF:04X}"
    mine = {"COMPOSE_FRAME", raw}
    taken = _taken(mine, {linear, after})
    if taken:
        for label in labels:
            M.block(label, f"dos-real16's store already comments these places: {taken}")
        return
    try:
        must(M.call(server.comment_write, method="add", ref="COMPOSE_FRAME",
                    text="builds the frame"), "by name")
        must(M.call(server.comment_write, method="add", ref=raw, text="16 bytes in"), "by address")
        must(M.call(server.symbols_load, path=str(moved), base=base), "the rebuilt map")
        there = M.call(server.symbols_find, name="COMPOSE_FRAME")
        rows = {str(r["ref"]): r for r in _listed()}
        by_name, by_addr = rows.get("COMPOSE_FRAME") or {}, rows.get(raw) or {}
        moved_ok = ok(there) and int(there["symbols"][0]["addr"], 16) == after
        M.judge(labels[0], moved_ok and by_name.get("addr") == f"0x{after:08x}",
                f"symbols_find {said(there, 60)}; the comment {by_name}")
        kept = by_addr.get("state") == "resolved" and by_addr.get("addr") == f"0x{after:08x}"
        must(M.call(server.symbols_load, path=str(mapf), base=base), "the real map again")
        rows = {str(r["ref"]): r for r in _listed()}
        back = (rows.get("COMPOSE_FRAME") or {}).get("addr") == f"0x{linear:08x}" \
            and (rows.get(raw) or {}).get("state") == "resolved"
        M.judge(labels[1], kept and back, f"over the copy {by_addr}; over the map {rows.get(raw)}")
    finally:
        M.setup()
        _delete_mine(mine)


def dpmi_comments() -> None:
    """At the `_tick` stop: the symbol, CS:offset and (when DS shares CS's base) DS:offset
    name one place, and the round trip through a file keeps every byte."""
    labels = [c[0] for c in DPMI_COMMENT_CELLS]
    found = must(M.call(server.symbols_find, name="_tick"), "_tick")
    linear = int(found["symbols"][0]["addr"], 16)
    regs = must(M.call(server.registers), "the stop's registers")
    values = regs["regs"]
    cs, ds = str(values.get("CS")), str(values.get("DS"))
    session = dstate.STATE.session
    assert session is not None
    cs_base, ds_base = session.selector("CS")["base"], session.selector("DS")["base"]
    off = linear - cs_base
    mine = {"_tick"}
    taken = _taken(mine, {linear, ds_base + off})
    if taken:
        for label in labels:
            M.block(label, f"the store already comments these places: {taken}")
        return
    try:
        must(M.call(server.comment_write, method="add", ref="_tick", text="the tick"), "by name")
        r = M.call(server.comment_write, method="add", ref=f"{cs}:{off:08X}",
                   text="the tick, by CS")
        M.judge(labels[0], ok(r) and (r.get("comment") or {}).get("ref") == "_tick"
                and (r.get("comment") or {}).get("addr") == f"0x{linear:08x}"
                and len(r.get("replaced_comments") or []) == 1, said(r, 120))
        d = M.call(server.comment_write, method="add", ref=f"{ds}:{off:08X}",
                   text="the tick, by DS")
        if ds_base == cs_base:
            holds = ok(d) and (d.get("comment") or {}).get("ref") == "_tick"
        else:
            holds = ok(d) and not d.get("replaced_comments")
            mine.add(str((d.get("comment") or {}).get("ref")))
        M.judge(labels[1], holds, f"CS base {cs_base:X}, DS base {ds_base:X}: {said(d, 100)}")
        same, detail = _round_trip(mine)
        M.judge(labels[2], same, detail)
    finally:
        M.setup()
        _delete_mine(mine)
