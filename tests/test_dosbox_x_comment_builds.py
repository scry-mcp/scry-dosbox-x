"""When a raw comment is `stale`: the whole rule as one table of sessions, and the inputs that
probed it, each driven through `start`, `comment_write(method="add")`,
`comment_write(method="load")` and `symbols_load` as a
client drives them.

A raw row records the one batch that described its address when it was placed or loaded (the
conf and that batch's entries), or the conf alone where no batch did, and the session that did
it. It is fresh while that batch is held unchanged, and stale where a held batch describes its
address otherwise or where none does and that batch is gone; a row stamped with the conf alone
is judged by the conf where no batch describes it. The table's rows
are the plan's Decision log rows of the same names."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from dosbox_x_server_support import (  # noqa: F401
    FakeSession,
    _start_over_a_store,
    clean_session,
    install,
)
from test_dosbox_x_comments import (
    STAMP,
    Protected,
    _file,
    _ParkedInRealMode,
    _rows_by_ref,
    install_store,
    ok,
    probe_table,
    refused,
)

from scry_dosbox_x import comment_file as cf
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import grammar, server
from scry_dosbox_x import state as dstate

#: A real-mode row placed at the park, which no batch describes; a protected-mode row made under
#: a map, in the first batch's span; a protected-mode row past FFFF, in that span too, which the
#: real-mode park keeps waiting and the map's stop places; a row that span holds at either base;
#: a row only the second batch's span holds. CS's base is 00400000, as each map's.
P, Q, W, V, R = "0814:0106", "00A7:2000", "00A7:00062310", "00A7:00120000", "00A7:00185000"
SPELLED = {W: "00A7:00062310"}
MODE = {P: grammar.REAL_MODE, Q: "Pr32", W: "Pr32", V: "Pr32", R: "Pr32"}


class _Sessions:
    """One conf and its store across sessions, each parked in real mode as dos-djgpp32's is, the
    map loaded at the protected-mode stop that follows."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp, self.mp = tmp_path, monkeypatch
        # A SECOND BATCH of the same program at the same base (A2) accumulates. Each first
        # batch spans 1000..170000 and each second one lies above it. The S maps share a name,
        # as `nm` output of one program cut in two repeats its statics: A2S repeats AS's line,
        # A2T holds a second static of that name at another address, and BS is AS relinked with
        # that name kept where it was; AM is AS relinked with only that static moved, A2M is
        # A2T relinked with only its static moved.
        texts = {"A": "00001000 T _main\n00170000 T _rest\n",
                 "B": "00001010 T _main\n00170000 T _rest\n",       # A relinked
                 "A2": "00180000 T _helper\n",
                 "AS": "00001000 T _main\n00170000 t _shared\n",
                 "BS": "00001010 T _main\n00170000 t _shared\n",
                 "A2S": "00180000 T _helper\n00170000 t _shared\n",
                 "A2T": "00180000 T _helper\n00190000 t _shared\n",
                 "AM": "00001000 T _main\n00170040 t _shared\n",
                 "A2M": "00180000 T _helper\n00190040 t _shared\n",
                 # A relinked SHORTER, its span ending below Q, and LONGER at the front, its
                 # span starting above Q: neither describes Q any more.
                 "C": "00001000 T _main\n00001800 T _rest\n",
                 "D": "00003000 T _main\n00172000 T _rest\n"}
        self.maps = {k: tmp_path / f"{k.lower()}.map" for k in texts}
        for k, text in texts.items():
            self.maps[k].write_text(text, encoding="utf-8")
        self.conf_text = "[sdl]\n"
        self.booted: Any = None

    def step(self, step: str) -> None:
        verb, _, arg = step.partition(" ")
        if verb == "start":
            if self.booted is not None:
                dstate.STATE.session = None
                dstate.STATE.store = None
                dstate.STATE.forget_symbols()
            got, self.booted = _start_over_a_store(self.tmp, self.mp, {},
                                                   double=_ParkedInRealMode,
                                                   conf_text=self.conf_text)
            ok(got)
        elif verb == "add":
            self.booted.mode = MODE[arg] if arg != P else grammar.REAL_MODE
            ok(server.comment_write("add", ref=arg, text="same text"))
        elif verb == "load":
            ok(server.comment_write("load", path=str(_file(self.tmp, (SPELLED.get(arg, arg),
                                                               "same text")))))
        elif verb == "map":
            # `map A`, `map A @500000` at another base, `map AS /_main` with a pattern.
            name, _, extra = arg.partition(" ")
            base = extra[1:] if extra.startswith("@") else "0x400000"
            pattern = extra[1:] if extra.startswith("/") else None
            self.booted.mode = "Pr32"
            ok(server.symbols_load(path=str(self.maps[name]), base=base, pattern=pattern))
        elif verb == "bp":
            self.booted.mode = MODE[arg]
            ok(server.breakpoint_at(ref=arg))
        elif verb == "pmload":
            # A PROTECTED-MODE STOP, whatever the ref's own mode.
            self.booted.mode = "Pr32"
            ok(server.comment_write("load", path=str(_file(self.tmp, (SPELLED.get(arg, arg),
                                                               "same text")))))
        elif verb in ("realload", "realbp"):
            # A REAL-MODE STOP AFTER THE MAP, where a protected-mode row cannot be placed: the
            # file loads it waiting, and the breakpoint is declared without a place.
            self.booted.mode = grammar.REAL_MODE
            ok(server.comment_write("load", path=str(_file(self.tmp, (SPELLED.get(arg, arg),
                                                               "same text"))))
               if verb == "realload" else server.breakpoint_at(ref=arg))
        elif verb in ("runbp", "realrunbp"):
            # DECLARED WHILE THE GUEST RUNS, after a stop of that mode (`runbp` protected,
            # `realrunbp` real): stored and queued, `pending`. The guest is left running.
            self.booted.mode = "Pr32" if verb == "runbp" else grammar.REAL_MODE
            where, regs = self.booted.where_and_registers()
            dstate.STATE.remember_stop(self.booted, where, regs, [], {})
            self.booted.running = True
            assert ok(server.breakpoint_at(ref=arg))["state"] == "pending"
        elif verb in ("pmstop", "realstop"):
            # THE GUEST STOPS in that mode, and the first call after the stop drains the queue.
            self.booted.running = False
            self.booted.mode = "Pr32" if verb == "pmstop" else grammar.REAL_MODE
            where, regs = self.booted.where_and_registers()
            dstate.STATE.remember_stop(self.booted, where, regs, [], {})
            ok(server.declaration_list("breakpoint"))
        elif verb == "conf":
            self.conf_text = "[sdl]\nfullscreen=false\n"
        elif verb == "strip":
            # A STORE WRITTEN BEFORE THE CONF WAS RECORDED beside the build: the one comment
            # row loses its `conf_fingerprint`, asserted to have held one.
            store = dstate.STATE.store
            assert store is not None
            doc = json.loads(store.path.read_text(encoding="utf-8"))   # conf -> declarations
            rows = [d for conf, decls in doc.items() if conf != "builds" for d in decls
                    if d.get("kind") == "comment"]
            assert len(rows) == 1 and rows[0].pop("conf_fingerprint", None) is not None, doc
            store.path.write_text(json.dumps(doc), encoding="utf-8")
        else:
            raise AssertionError(f"no step {step!r}")

    def state(self, key: str) -> dict[str, Any]:
        # `real <key>` and `pm <key>` list the row at a stop of that mode; a bare key lists it
        # in the mode its ref is written for (`MODE`).
        at, _, rest = key.partition(" ")
        stop = {"real": grammar.REAL_MODE, "pm": "Pr32"}.get(at)
        key = rest if stop is not None else key
        verb, _, ref = key.rpartition(" ")
        self.booted.mode = stop or MODE[ref]
        if verb == "bp":
            rows: dict[str, dict[str, Any]] = {
                b["ref"]: b for b in server.declaration_list("breakpoint")["breakpoints"]}
            return rows[ref]
        return _rows_by_ref()[ref]


# ONE ROW PER LINE OF THE TABLE, and a row may name several sessions: `start` begins one.
# A `load` gives the row the text the store already holds, so it is the unchanged path. A key
# `bp <ref>` is the raw breakpoint at that ref, judged by the same build: `armed` or `stale`.
# A raw row records the cpu mode of the stop that placed it, and is judged only at a stop of
# that mode: B1-B29 place and list each ref in its own mode, the mode rows (B30-B33) place a
# row in one mode and list it in the other, a key's `real` or `pm` naming the listing's stop.
# A row no stop placed (no mode) waits in either mode, `unarmable`: B8's and B21's `W`, B29's
# rows before a load of their session places them, and the rows declared while the guest runs
# (B34-B36) until the stop that arms them gives them its mode.
TABLE = [
    ("B1 park row, no map yet", ["start", f"add {P}"], {P: "resolved"}),
    ("B2 park row added, then the first map", ["start", f"add {P}", "map A"], {P: "resolved"}),
    ("B2 park row loaded, then the first map", ["start", f"load {P}", "map A"],
     {P: "resolved"}),
    ("B2 waiting row loaded at the park, then the first map", ["start", f"load {W}", "map A"],
     {W: "resolved"}),
    ("B3 park row no batch describes, a second map in the same session",
     ["start", f"add {P}", "map A", "map B"], {P: "resolved"}),
    ("B3 park row a map describes, a second map in the same session",
     ["start", f"load {W}", "map A", "map B"], {W: "resolved"}),
    ("B3 park row a map describes, its map then another in the next session",
     ["start", f"load {W}", "map A", "start", "map A", "map B"], {W: "resolved"}),
    ("B3 row made under a map, a second map in the same session",
     ["start", "map A", f"add {Q}", "map B"], {Q: "resolved"}),
    ("B4 park row taken by a map, next session's park",
     ["start", f"add {P}", "map A", "start"], {P: "resolved"}),
    ("B4 row made under a map, next session's park",
     ["start", "map A", f"add {Q}", f"bp {Q}", "start"], {Q: "stale", f"bp {Q}": "stale"}),
    ("B5 same map next session",
     ["start", f"add {P}", "map A", f"add {Q}", "start", "map A"],
     {P: "resolved", Q: "resolved"}),
    ("B5 map A, then B, then A again",
     ["start", f"add {P}", "map A", "start", "map B", "start", "map A"], {P: "resolved"}),
    ("B6 relinked map next session",
     ["start", f"add {P}", "map A", f"add {Q}", "start", "map B"],
     {P: "resolved", Q: "stale"}),
    ("B6 waiting row loaded at the park, relinked map next session",
     ["start", f"load {W}", "map A", "start", "map B"], {W: "stale"}),
    ("B7 park row of a session with no map, next session's park",
     ["start", f"add {P}", "start"], {P: "resolved"}),
    ("B8 park row no batch describes, of a session with no map, next session's map",
     ["start", f"add {P}", "start", "map A"], {P: "resolved"}),
    ("B8 park row a map describes, of a session with no map, next session's map",
     ["start", f"load {W}", "start", "map A"], {W: ("unarmable", "no stop has placed it")}),
    ("B9 reloaded at this park, then the map",
     ["start", f"add {P}", "start", f"load {P}", "map A"], {P: "resolved"}),
    ("B9 re-added at this park, then the map",
     ["start", f"add {P}", "start", f"add {P}", "map A"], {P: "resolved"}),
    ("B9 reloaded at this park, then the map, then the next session over it",
     ["start", f"add {P}", "start", f"load {P}", "map A", "start", "map A"],
     {P: "resolved"}),
    ("B9 waiting row reloaded at this park, then the map",
     ["start", f"load {W}", "start", f"load {W}", "map A"], {W: "resolved"}),
    ("B10 another map's row loaded after this map",
     ["start", "map B", f"add {Q}", "start", "map A", f"load {Q}"], {Q: "resolved"}),
    ("B10 another map's waiting row loaded at the park, then this map",
     ["start", f"load {W}", "map B", "start", f"load {W}", "map A"], {W: "resolved"}),
    ("B10 the B8 row loaded after this map",
     ["start", f"add {P}", "start", "map A", f"load {P}"], {P: "resolved"}),
    ("B11 another map's row, not loaded",
     ["start", "map B", f"add {Q}", "start", "map A"], {Q: "stale"}),
    ("B12 the conf edited, next session's park",
     ["start", f"add {P}", "conf", "start"], {P: "stale"}),
    ("B12 the conf edited, next session's same map",
     ["start", f"add {P}", "map A", "conf", "start", "map A"], {P: "stale"}),
    ("B13 park row, a second batch of the same program in the same session",
     ["start", f"add {P}", "map A", "map A2"], {P: "resolved"}),
    ("B13 park row, both batches again in the next session",
     ["start", f"add {P}", "map A", "map A2", "start", "map A", "map A2"], {P: "resolved"}),
    ("B13 row made after both batches, both again in the next session",
     ["start", "map A", "map A2", f"add {Q}", "start", "map A", "map A2"], {Q: "resolved"}),
    ("B13 row made after both batches, the first relinked in the next session",
     ["start", "map A", "map A2", f"add {Q}", "start", "map B", "map A2"], {Q: "stale"}),
    ("B13 the same map loaded twice",
     ["start", f"add {P}", "map A", "map A"], {P: "resolved"}),
    ("B13 the same batch loaded again after the second",
     ["start", f"add {P}", "map A", "map A2", "map A2"], {P: "resolved"}),
    ("B13 a relinked map, then the real one again in the same session",
     ["start", f"add {P}", "map A", "map B", "map A"], {P: "resolved"}),
    ("B13 breakpoint, both batches again",
     ["start", "map A", "map A2", f"bp {Q}", "start", "map A", "map A2"], {f"bp {Q}": "armed"}),
    ("B13 breakpoint, the first batch relinked",
     ["start", "map A", "map A2", f"bp {Q}", "start", "map B", "map A2"], {f"bp {Q}": "stale"}),
    ("B14 row under a map stored without its conf, next session's park",
     ["start", "map A", f"add {Q}", "strip", "start"],
     {Q: ("stale", "conf it was placed over")}),
    ("B14 row under a map stored without its conf, its map again",
     ["start", "map A", f"add {Q}", "strip", "start", "map A"], {Q: "resolved"}),
    ("B14 row under a map stored without its conf, another map",
     ["start", "map A", f"add {Q}", "strip", "start", "map B"], {Q: "stale"}),
    ("B15 batches sharing a name at one address, both again",
     ["start", "map AS", "map A2S", f"add {Q}", f"bp {Q}", "start", "map AS", "map A2S"],
     {Q: "resolved", f"bp {Q}": "armed"}),
    ("B15 batches sharing a name at one address, the first relinked",
     ["start", "map AS", "map A2S", f"add {Q}", f"bp {Q}", "start", "map BS", "map A2S"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B15 row made after the first batch, then the second sharing a name at one address",
     ["start", "map AS", f"add {Q}", "map A2S"], {Q: "resolved"}),
    ("B16 batches sharing a name at two addresses, both again",
     ["start", "map AS", "map A2T", f"add {Q}", "start", "map AS", "map A2T"],
     {Q: "resolved"}),
    ("B16 row made after the first batch, then a second static of that name",
     ["start", "map AS", f"add {Q}", "map A2T"], {Q: "resolved"}),
    ("B17 disjoint batches in the other order",
     ["start", "map A", "map A2", f"add {Q}", f"bp {Q}", "start", "map A2", "map A"],
     {Q: "resolved", f"bp {Q}": "armed"}),
    ("B17 row taken by the first batch alone, both batches in the other order",
     ["start", f"add {P}", "map A", "map A2", "start", "map A2", "map A"], {P: "resolved"}),
    ("B17 batches sharing a name at two addresses in the other order",
     ["start", "map AS", "map A2T", f"add {Q}", "start", "map A2T", "map AS"],
     {Q: "resolved"}),
    ("B18 the real batches loaded back over a relinked first batch",
     ["start", "map AS", "map A2S", f"add {Q}", "map BS", "map AS", "map A2S"],
     {Q: "resolved"}),
    ("B18 a relinked first batch over both, same session",
     ["start", "map AS", "map A2S", f"add {Q}", "map BS"], {Q: "resolved"}),
    ("B19 the same map at another base, same session",
     ["start", "map A", f"add {V}", "map A @0x500000"], {V: "stale"}),
    ("B19 the same map at another base, next session",
     ["start", "map A", f"add {V}", f"bp {V}", "start", "map A @0x500000"],
     {V: "stale", f"bp {V}": "stale"}),
    ("B20 the same map with a pattern that leaves a name out, next session",
     ["start", "map AS", f"add {Q}", f"bp {Q}", "start", "map AS /_main"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B21 park row stored without its conf, next session's park",
     ["start", f"add {P}", "strip", "start"], {P: "resolved"}),
    ("B21 park row no batch describes, stored without its conf, next session's map",
     ["start", f"add {P}", "strip", "start", "map A"], {P: "resolved"}),
    ("B21 park row a map describes, stored without its conf, next session's map",
     ["start", f"load {W}", "strip", "start", "map A"],
     {W: ("unarmable", "no stop has placed it")}),
    ("B22 batches naming one static at two addresses, the first relinked moving only it",
     ["start", "map AS", "map A2T", f"add {Q}", f"bp {Q}", "start", "map AM", "map A2T"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B22 batches naming one static at one address, the first relinked moving only it",
     ["start", "map AS", "map A2S", f"add {Q}", f"bp {Q}", "start", "map AM", "map A2S"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B23 a row kept by a batch that adds names, a relinked detour and back",
     ["start", "map A", f"add {Q}", "map A2", "map B", "map A"], {Q: "resolved"}),
    ("B23 the same detour, its relinked middle",
     ["start", "map A", f"add {Q}", "map A2", "map B"], {Q: "resolved"}),
    ("B24 a detour map and back, a row made after, the right map next session",
     ["start", "map A", "map B", "map A", f"add {Q}", f"bp {Q}", "start", "map A"],
     {Q: "resolved", f"bp {Q}": "armed"}),
    ("B25 a first batch relinked within one session, after the row",
     ["start", "map AS", "map A2T", f"add {Q}", "map AM", "map A2T"], {Q: "resolved"}),
    ("B26 a row the second batch describes, the first relinked next session",
     ["start", "map AS", "map A2T", f"add {R}", f"bp {R}", "start", "map AM", "map A2T"],
     {R: "resolved", f"bp {R}": "armed"}),
    ("B26 a row the second batch describes, that batch relinked next session",
     ["start", "map AS", "map A2T", f"add {R}", f"bp {R}", "start", "map AS", "map A2M"],
     {R: "stale", f"bp {R}": "stale"}),
    ("B27 the same map at a base past the row, same session",
     ["start", "map A", f"add {V}", "map A @0x600000"], {V: "stale"}),
    ("B27 the same map at a base past the row, next session",
     ["start", "map A", f"add {V}", f"bp {V}", "start", "map A @0x600000"],
     {V: "stale", f"bp {V}": "stale"}),
    ("B28 the map relinked shorter, its span ending below the row, next session",
     ["start", "map A", f"add {Q}", f"bp {Q}", "start", "map C"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B28 the map relinked longer at the front, its span starting above the row, next session",
     ["start", "map A", f"add {Q}", f"bp {Q}", "start", "map D"],
     {Q: "stale", f"bp {Q}": "stale"}),
    ("B29 a row loaded and a breakpoint declared at a real-mode stop after map A, next park",
     ["start", "map A", f"realload {W}", f"realbp {W}", "start"],
     {f"real {W}": ("unarmable", "kept for a protected-mode stop"),
      f"real bp {W}": ("unarmable", "no stop has placed it")}),
    ("B29 the same two, listed at the protected-mode stop that follows, no load since",
     ["start", "map A", f"realload {W}", f"realbp {W}"],
     {W: ("unarmable", "no stop has placed it"),
      f"bp {W}": ("unarmable", "no stop has placed it")}),
    ("B29 the same two, next session map A",
     ["start", "map A", f"realload {W}", f"realbp {W}", "start", "map A"],
     {W: "unarmable", f"bp {W}": "unarmable"}),
    ("B29 the same two, next session map B (relinked over them)",
     ["start", "map A", f"realload {W}", f"realbp {W}", "start", "map B"],
     {W: "unarmable", f"bp {W}": "unarmable"}),
    ("B29 the same two, next session map C (not over them)",
     ["start", "map A", f"realload {W}", f"realbp {W}", "start", "map C"],
     {W: "unarmable", f"bp {W}": "unarmable"}),
    ("B29 the same two, a later map in the same session places them",
     ["start", "map A", f"realload {W}", f"realbp {W}", "map A"],
     {W: "resolved", f"bp {W}": "armed"}),
    ("B29 the same two, placed by a later map, next session map A",
     ["start", "map A", f"realload {W}", f"realbp {W}", "map A", "start", "map A"],
     {W: "resolved", f"bp {W}": "armed"}),
    ("B29 the same two, placed by a later map, next session map C (not over them)",
     ["start", "map A", f"realload {W}", f"realbp {W}", "map A", "start", "map C"],
     {W: "stale", f"bp {W}": "stale"}),
    ("B30 a row a real-mode stop places after map A, the protected-mode stop that follows",
     ["start", "map A", f"realload {Q}", f"realbp {Q}"],
     {Q: ("unarmable", "real-mode stop"), f"bp {Q}": ("unarmable", "real-mode stop")}),
    ("B30 the same two, a real-mode stop that follows",
     ["start", "map A", f"realload {Q}", f"realbp {Q}"],
     {f"real {Q}": "resolved", f"real bp {Q}": "armed"}),
    ("B30 the same two, next session map A",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", "start", "map A"],
     {Q: "unarmable", f"bp {Q}": "unarmable", f"real {Q}": "resolved",
      f"real bp {Q}": "armed"}),
    ("B30 the same two, next session map C (not over them)",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", "start", "map C"],
     {Q: "unarmable", f"bp {Q}": "unarmable", f"real {Q}": "resolved",
      f"real bp {Q}": "armed"}),
    ("B30 the same two, next session map D (not over them)",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", "start", "map D"],
     {Q: "unarmable", f"bp {Q}": "unarmable"}),
    ("B30 the same two, next session's park",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", "start"],
     {f"real {Q}": "resolved", f"real bp {Q}": "armed"}),
    ("B30 the same two, declared and loaded again at the protected-mode stop",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", f"bp {Q}", f"load {Q}"],
     {Q: "resolved", f"bp {Q}": "armed"}),
    ("B30 the same two, taken into protected mode, next session map C (not over them)",
     ["start", "map A", f"realload {Q}", f"realbp {Q}", f"bp {Q}", f"load {Q}", "start",
      "map C"], {Q: "stale", f"bp {Q}": "stale"}),
    ("B30 the same two, loaded again at a protected-mode stop that cannot place them",
     ["start", "map A", f"realload {P}", f"realbp {P}", f"pmload {P}", "start", "map C"],
     {P: "resolved", f"bp {P}": "armed", f"pm {P}": "unarmable"}),
    ("B31 a row the real-mode park places from its file, then the map",
     ["start", f"load {Q}", "map A"], {Q: "unarmable", f"real {Q}": "resolved"}),
    ("B31 a park row, the protected-mode stop of its map",
     ["start", f"add {P}", "map A"], {f"pm {P}": ("unarmable", "real-mode stop"),
                                      P: "resolved"}),
    ("B32 a row placed at a protected-mode stop under map A, a real-mode stop that follows",
     ["start", "map A", f"add {Q}", f"bp {Q}"],
     {f"real {Q}": ("unarmable", "protected-mode stop"),
      f"real bp {Q}": ("unarmable", "protected-mode stop")}),
    ("B32 the same two, next session's park",
     ["start", "map A", f"add {Q}", f"bp {Q}", "start"],
     {f"real {Q}": "unarmable", f"real bp {Q}": "unarmable"}),
    ("B32 the same two, next session map A",
     ["start", "map A", f"add {Q}", f"bp {Q}", "start", "map A"],
     {Q: "resolved", f"bp {Q}": "armed", f"real {Q}": "unarmable"}),
    ("B33 two placed at a protected-mode stop with no map, next session's protected stop",
     ["start", f"add {Q}", f"bp {Q}", "start"],
     {Q: "resolved", f"bp {Q}": "gone", f"real {Q}": "unarmable",
      f"real bp {Q}": "unarmable"}),
    ("B33 the same two, declared again at that stop",
     ["start", f"add {Q}", f"bp {Q}", "start", f"bp {Q}"], {f"bp {Q}": "armed"}),
    ("B34 declared running after a protected-mode stop, no map, armed at the next one",
     ["start", f"runbp {Q}", "pmstop"], {f"bp {Q}": "armed"}),
    ("B34 the same, next session's park",
     ["start", f"runbp {Q}", "pmstop", "start"],
     {f"real bp {Q}": ("unarmable", "protected-mode stop")}),
    ("B34 the same, next session's protected-mode stop",
     ["start", f"runbp {Q}", "pmstop", "start"], {f"bp {Q}": "gone"}),
    ("B34 declared running after a real-mode stop under map A, armed there, next session map C",
     ["start", "map A", f"realrunbp {Q}", "realstop", "start", "map C"],
     {f"bp {Q}": ("unarmable", "real-mode stop"), f"real bp {Q}": "armed"}),
    ("B34 declared running after a protected-mode stop under map A, armed there, next map C",
     ["start", "map A", f"runbp {Q}", "pmstop", "start", "map C"], {f"bp {Q}": "stale"}),
    ("B35 declared running, no stop since",
     ["start", f"runbp {Q}"], {f"bp {Q}": "pending"}),
    ("B35 declared running, no stop since, next session",
     ["start", f"runbp {Q}", "start"],
     {f"real bp {Q}": ("unarmable", "no stop has placed it"),
      f"bp {Q}": ("unarmable", "no stop has placed it")}),
    ("B35 a real-mode address declared running, no stop since, next session's park",
     ["start", f"realrunbp {P}", "start"], {f"bp {P}": ("unarmable", "no stop has placed it")}),
    ("B36 placed at a protected-mode stop, declared again running, a real-mode stop next",
     ["start", f"bp {Q}", f"runbp {Q}", "realstop"], {f"real bp {Q}": "pending"}),
    ("B36 the same, then a protected-mode stop",
     ["start", f"bp {Q}", f"runbp {Q}", "realstop", "pmstop"], {f"bp {Q}": "armed"}),
]


@pytest.mark.parametrize("steps, want", [(s, w) for _, s, w in TABLE],
                         ids=[i for i, _, _ in TABLE])
def test_a_raw_comments_state_across_sessions_and_maps(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, steps: list[str],
        want: dict[str, Any]) -> None:
    run = _Sessions(tmp_path, monkeypatch)
    for step in steps:
        run.step(step)
    for ref, expected in want.items():
        state, why = expected if isinstance(expected, tuple) else (expected, None)
        row = run.state(ref)
        assert row["state"] == state, row
        if why is not None:
            assert why in row["why"], row


def test_a_map_loaded_while_the_guest_runs_places_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A row is placed only at a stop: a `symbols_load` while the guest runs leaves this
    session's row no stop placed with no mode, and the stop that follows places it."""
    run = _Sessions(tmp_path, monkeypatch)
    for step in ("start", f"realrunbp {P}"):
        run.step(step)
    ok(server.symbols_load(path=str(run.maps["A"]), base="0x400000"))
    store = dstate.STATE.store
    assert store is not None

    def mode() -> str | None:
        return next(d for d in store.declarations() if d.ref == P).cpu_mode

    assert mode() is None
    run.step("realstop")
    assert mode() == "real"


def test_the_store_writes_no_batch_and_drops_the_one_an_older_store_wrote(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A row is judged by the stamp it carries against the batches this session loaded, so the
    batch's entries are written nowhere: a record no reader uses is a second copy of the map
    that only goes stale. One an older store wrote for this conf leaves with the next write,
    and another conf's is left as it is."""
    run = _Sessions(tmp_path, monkeypatch)
    for step in ["start", "map AS", "map A2T", f"add {Q}", f"bp {Q}"]:
        run.step(step)
    store = dstate.STATE.store
    assert store is not None
    doc = json.loads(store.path.read_text(encoding="utf-8"))
    assert "builds" not in doc, doc
    doc["builds"] = {str(store._conf): {"s": {"conf": "c", "entries": []}},
                     "other": {"t": {"conf": "o", "entries": []}}}
    store.path.write_text(json.dumps(doc), encoding="utf-8")
    ok(server.comment_write("delete", ref=Q))
    after = json.loads(store.path.read_text(encoding="utf-8"))
    assert after["builds"] == {"other": {"t": {"conf": "o", "entries": []}}}, after


@pytest.mark.parametrize("builds", [
    {"g": {"s": {"conf": "c"}}}, {"g": {"s": {"conf": "c", "entries": ["_a 10"]}}},
    {"g": {"s": "not a mapping"}}, {"g": "x"}, [], "x",
])
def test_a_batch_an_older_store_wrote_is_ignored_whatever_its_shape(
        tmp_path: Path, builds: Any) -> None:
    path = tmp_path / "d.json"
    path.write_text(json.dumps({"g": [], "builds": builds}), encoding="utf-8")
    assert dec.DeclarationStore("g", path=path).declarations() == []


def test_a_breakpoint_declared_again_in_the_other_mode_is_armed_again_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The debugger fixes a breakpoint's address when its row is made, in that stop's mode, so
    the row a real-mode declaration armed is another byte at a protected-mode stop though it
    reads the same: declared again there, the row is cleared and armed again. Declared again in
    its own mode, the row is kept."""
    run = _Sessions(tmp_path, monkeypatch)
    for step in ("start", "map A", f"realbp {Q}"):
        run.step(step)
    seen: list[str] = []

    def logged(name: str) -> Any:
        real = getattr(run.booted, name)

        def call(seg: int, off: int) -> Any:
            seen.append(f"{name} {seg:04X}:{off:04X}")
            return real(seg, off)
        return call

    for name in ("arm_code_breakpoint", "clear_code_breakpoint"):
        monkeypatch.setattr(run.booted, name, logged(name))
    run.step(f"realbp {Q}")
    assert seen == []
    run.step(f"bp {Q}")
    assert seen == ["clear_code_breakpoint 00A7:2000", "arm_code_breakpoint 00A7:2000"]
    run.step(f"bp {Q}")
    assert len(seen) == 2


def test_a_raw_rows_cpu_mode_round_trips_and_only_a_raw_code_row_carries_one() -> None:
    """The mode a raw row was placed in survives the store file; a symbol, an interrupt or a
    word outside the two modes is refused, so a store edited by hand cannot hold one."""
    held = dec.Declaration("breakpoint", "address", "00A7:2000", cpu_mode="protected")
    assert dec.Declaration.from_dict(held.to_dict()).cpu_mode == "protected"
    assert "cpu_mode" not in dec.Declaration("breakpoint", "address", "00A7:2000").to_dict()
    for kind, by, ref, mode in [("breakpoint", "symbol", "_main", "real"),
                                ("interrupt", "address", "BPINT 21", "real"),
                                ("breakpoint", "address", "00A7:2000", "Pr32")]:
        with pytest.raises(dec.DeclarationError, match="cpu mode"):
            dec.Declaration(kind, by, ref, cpu_mode=mode)


def test_a_batch_is_its_conf_and_entries_and_spans_its_lowest_to_its_highest() -> None:
    a = dec.Build.of("c", [("_s", 3), ("_main", 1), ("_s", 3)])
    assert a.entries == (("_main", 1), ("_s", 3), ("_s", 3)), "sorted, a repeated line kept"
    assert a.stamp == dec.Build.of("c", [("_s", 3), ("_s", 3), ("_main", 1)]).stamp, "no order"
    assert a.stamp != dec.Build.of("c", [("_main", 1), ("_s", 3)]).stamp, "the repeat counts"
    assert a.stamp != dec.Build.of("d", a.entries).stamp, "another conf"
    assert a.stamp != dec.Build.of("c", [("_main", 2), ("_s", 3), ("_s", 3)]).stamp, "relinked"
    # A stored row carries its stamp, so the recipe may never drift from what wrote it: this is
    # the digest the recipe gave for that batch, kept as a literal rather than recomputed here.
    assert a.stamp == "1182701ba80a27c7", a.stamp
    assert [a.covers(x) for x in (0, 1, 2, 3, 4)] == [False, True, True, True, False]
    assert not dec.Build.of("c", []).covers(0)


def test_a_batch_hashes_its_entries_once_however_many_rows_ask(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # THE STAMP IS THE BATCH'S, NOT THE ROW'S: a map of thousands of lines asked once per row
    # per held batch on every listing would rehash it at the per-row rate.
    batch = dec.Build.of("c", [(f"_s{i}", 0x1000 + i) for i in range(64)])
    calls: list[bytes] = []
    real = hashlib.sha256

    def counted(data: bytes = b"") -> Any:
        calls.append(data)
        return real(data)
    monkeypatch.setattr(hashlib, "sha256", counted)
    row = dec.Declaration("breakpoint", "address", "00A7:2000", fingerprint="elsewhere")
    for _ in range(100):
        assert dec.raw_staleness(row, "c", [batch], lambda: 0x1010) == "other"
        assert batch.stamp
    assert calls == [], "the stamp was taken when the batch was made"
    assert dec.Build.of("c", batch.entries).stamp == batch.stamp, "and it is the same stamp"


def test_a_row_this_session_takes_into_its_map_keeps_its_stamp_and_names_this_session(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A reload of a row an earlier session left adopts it, as `comment_write(method="add")` adopts:
    this
    session's origin, the build that follows, and the row's own `created_at`."""
    run = _Sessions(tmp_path, monkeypatch)
    for step in ("start", f"add {P}", "start"):
        run.step(step)
    before = run.state(P)
    got = ok(server.comment_write("load", path=str(_file(tmp_path, (P, "same text")))))
    assert (got["unchanged"], got["added"], got["replaced_total"]) == (1, 0, 0)
    after = run.state(P)
    assert after["created_at"] == before["created_at"]
    assert after["origin"] == dstate.STATE.session_origin
    assert before["origin"] != after["origin"], (before, after)


# ------------------------------------------------- rows a stop cannot place, and their whys

def test_a_protected_mode_save_loads_waiting_at_the_real_mode_park(tmp_path: Path) -> None:
    install()
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    ok(server.comment_write("add", ref="00A7:00045F80", text="pm"))
    saved = tmp_path / "pm.tsv"
    ok(server.comment_write("save", dest=str(saved)))
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_write("load", path=str(saved)))
    row = _rows_by_ref()["00A7:00045F80"]
    assert got["added"] == 1 and row["state"] == "unarmable" and "addr" not in row


@pytest.mark.parametrize("off", ["00010000", "FFFFFFFF"])
def test_one_past_ffff_and_the_formats_top_offset_wait_at_the_park_beside_a_placed_symbol(
        tmp_path: Path, off: str) -> None:
    install()
    probe_table()
    got = ok(server.comment_write("load", path=str(_file(tmp_path, (f"00A7:{off}", "edge"),
                                                  ("start", "s")))))
    ref = dec.canonical_ref(f"00A7:{off}", "address")
    rows = _rows_by_ref()
    assert got["added"] == 2 and ref in got["note"]
    assert rows[ref]["state"] == "unarmable" and rows["start"]["state"] == "resolved"


def test_offset_ffff_is_placed_at_the_park_and_named_nowhere(tmp_path: Path) -> None:
    install()
    got = ok(server.comment_write("load", path=str(_file(tmp_path, ("00A7:0000FFFF", "top")))))
    assert _rows_by_ref()["00A7:FFFF"]["state"] == "resolved" and "note" not in got


def test_a_waiting_row_is_deleted_at_the_park(tmp_path: Path) -> None:
    install()
    ok(server.comment_write("load", path=str(_file(tmp_path, ("00A7:00045F80", "pm")))))
    ok(server.comment_write("delete", ref="00A7:00045F80"))
    assert ok(server.comment_list())["comments_total"] == 0


@pytest.mark.parametrize("ref, back", [("0000:0084", "0x00000084"), ("0003:0400", "0x00000430")])
def test_a_real_mode_save_waits_at_a_protected_mode_stop_and_is_placed_back(
        tmp_path: Path, ref: str, back: str) -> None:
    """The interrupt table's segment and the last null selector (RPL 3)."""
    install()
    ok(server.comment_write("add", ref=ref, text="real"))
    saved = tmp_path / "real.tsv"
    ok(server.comment_write("save", dest=str(saved)))
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_write("load", path=str(saved)))
    row = _rows_by_ref()[ref]
    assert got["added"] == 1 and ref in got["note"]
    assert row["state"] == "unarmable" and "null selector" in row["why"], row
    # At a real-mode stop it still waits: no stop placed it. Loaded again there, it is placed.
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    waiting = _rows_by_ref()[ref]
    assert waiting["state"] == "unarmable" and "no stop has placed it" in waiting["why"], waiting
    ok(server.comment_write("load", path=str(saved)))
    assert (_rows_by_ref()[ref]["state"], _rows_by_ref()[ref]["addr"]) == ("resolved", back)


def test_a_segment_no_descriptor_holds_waits_beside_one_placed_at_a_protected_mode_stop(
        tmp_path: Path) -> None:
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_write("load", path=str(_file(tmp_path, ("0814:010B", "real"),
                                                  ("00A7:00001000", "pm")))))
    rows = _rows_by_ref()
    assert got["added"] == 2 and rows["00A7:1000"]["state"] == "resolved"
    assert rows["0814:010B"]["state"] == "unarmable"


def test_a_row_past_its_selectors_limit_waits_for_that_limit_not_a_mode(tmp_path: Path) -> None:
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    install_store()
    got = ok(server.comment_write("load", path=str(_file(tmp_path, ("00A7:00240000", "past")))))
    why = _rows_by_ref()["00A7:00240000"]["why"]
    assert "limit reaches it" in why and "mode holds" not in why + got["note"], why
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    assert _rows_by_ref()["00A7:00240000"]["state"] == "unarmable"


@pytest.mark.parametrize("ref, key, at_park, at_pm", [
    ("0000:00010000", "0000:00010000", "no stop places it", "no stop places it"),
    ("0003:00010000", "0003:00010000", "no stop places it", "no stop places it"),
    ("0000:0001FFFF", "0000:0001FFFF", "no stop places it", "no stop places it"),
    ("0004:00010000", "0004:00010000", "kept for a protected-mode stop", None),
])
def test_the_why_of_a_row_past_ffff_names_only_a_stop_that_places_it(
        tmp_path: Path, ref: str, key: str, at_park: str, at_pm: str | None) -> None:
    """A null selector past FFFF is placed by no stop, at the park or at a protected-mode
    stop; selector 0004 is no null selector, so a protected-mode stop may place it."""
    dstate.STATE.session = FakeSession()  # type: ignore[assignment]
    install_store()
    ok(server.comment_write("load", path=str(_file(tmp_path, (ref, "x")))))
    park_why = _rows_by_ref()[key]["why"]
    dstate.STATE.session = Protected()  # type: ignore[assignment]
    pm_why = _rows_by_ref()[key]["why"]
    assert at_park in park_why, park_why
    if at_pm is not None:
        assert at_pm in pm_why, pm_why


# --------------------------------------------------------------- the format's own words

def test_the_format_refuses_one_ref_twice_in_its_own_words() -> None:
    header = cf.HEADER + "\n"
    with pytest.raises(cf.CommentFileError) as read:
        cf.parse(header + f"start\t\t{STAMP}\ta\nstart\t\t{STAMP}\tb\n", "c.tsv")
    with pytest.raises(cf.CommentFileError) as written:
        cf.render([cf.Row("0814:010B", "", STAMP, "a"), cf.Row("0814:010B", "", STAMP, "b")])
    for e in (read, written):
        assert "one comment per ref" in str(e.value) and "place" not in str(e.value)


def test_one_address_in_two_spellings_is_refused_and_two_aliases_load_with_a_note(
        tmp_path: Path) -> None:
    install()
    two = _file(tmp_path, ("0814:010B", "a"), ("0814:0000010B", "b"), name="two.tsv")
    assert "one comment per ref" in refused(server.comment_write("load", path=str(two)),
                                            "bad_argument")
    alias = _file(tmp_path, ("0814:010B", "a"), ("0824:000B", "b"), name="alias.tsv")
    assert "share a place" in ok(server.comment_write("load", path=str(alias)))["note"]


# ------------------------------------------- a held row of another build, given its text

def test_a_held_row_of_another_build_given_another_text_is_this_builds(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The replaced path stamps this session's build too: map B's row, the file's new text
    loaded at the park of a session that then loads map A. The row is one the park cannot
    place, so the map's stop is the first that does (a row the park places is real-mode's: B31)."""
    run = _Sessions(tmp_path, monkeypatch)
    for step in ("start", "map B", f"add {W}", "start"):
        run.step(step)
    got = ok(server.comment_write("load", path=str(_file(tmp_path, (W, "a new text")))))
    run.step("map A")
    assert got["replaced_total"] == 1 and run.state(W)["state"] == "resolved"


@pytest.mark.parametrize("ref, held_in, then", [
    ("00A7:00045F80", grammar.REAL_MODE, "Pr32"), ("0000:0084", "Pr32", grammar.REAL_MODE),
    ("00A7:00045F80", "Pr32", "Pr32")])
def test_a_held_row_of_another_build_given_its_text_where_it_waits_or_not_is_brought(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref: str, held_in: str,
        then: str) -> None:
    """Map B's session holds the row; the next session parks, reaches a stop of `held_in`'s
    mode, loads the file with the same text, loads map A and is listed at a stop of `then`'s
    mode: brought to map A's build, its stamp kept."""
    run = _Sessions(tmp_path, monkeypatch)
    run.step("start")
    run.booted.mode = "Pr32" if ref.startswith("00A7") else grammar.REAL_MODE
    ok(server.comment_write("add", ref=ref, text="same"))
    run.step("map B")
    run.step("start")
    run.booted.mode = held_in
    got = ok(server.comment_write("load", path=str(_file(tmp_path, (ref, "same")))))
    assert got["unchanged"] == 1, got
    created = _rows_by_ref()[ref]["created_at"]
    run.step("map A")
    run.booted.mode = then
    row = _rows_by_ref()[ref]
    assert (row["state"], row["created_at"]) == ("resolved", created), row
