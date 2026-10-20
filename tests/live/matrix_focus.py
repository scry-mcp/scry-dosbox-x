"""Section O of the live matrix: whether DOSBox-X came to the front, or any display's Space
moved, during the run, sampled from outside it (`scry_core.focus_watch`) for its whole length.

It is two sections under one letter: the CONTROL opens the run and the VERDICT closes it, so the
watch the control starts samples every section between. The control, in the same harness the
verdict is taken in: one shared start forced in front, which the watch must see in front, and
one behind, which it must not, and the owner's Space moved and put back on purpose, which it
must see move; a watch that does not hold all three clears nothing, so without
the control the verdict is BLOCKED, as it is when too little ran or the watch could not sample:
never green, and never counted as the server's FAIL. Judged by process name, so another
DOSBox-X in front would count. Nothing is excluded: no tool clicks a menu any more, and section
G's windows open behind. The control's front start takes the owner's focus for a few seconds
and its Space control moves the owner's Space and back: a run with this section is announced.
"""
from __future__ import annotations

import time
from pathlib import Path

from matrix_common import (
    ENV,
    GUEST,
    PROBE_CONF,
    M,
    boot,
    cells,
    close_whatever,
    conf_without_launch,
    must,
    server,
)
from scry_core import focus_gate, focus_watch

FLAGS_VAR = "DOSBOX_X_LIVE_WINDOW_FLAGS"
NAMES = {"dosbox-x"}

O_CONTROL = cells(
    ("O the control: a shared start forced in front is seen in front",
     "known: macOS brings a newly launched app with a window to the front"),
    ("O the control: a shared start behind is never in front",
     "start docstring: `background`, true behind; and it moves no Space"),
    ("O the control: a Space moved on purpose is seen moved",
     "scry_core.focus_watch: SPACE_CHANGED"),
)
O_VERDICT = cells(
    ("O no DOSBox-X came to the front and no Space moved while the sections ran",
     "REFERENCE.md, Input and the screen: nothing about the host is touched"),
)

#: The watch the control started, and its start of the judged window.
WATCH: list[focus_watch.FocusWatch] = []
SINCE: list[int] = []


def _flags() -> list[str]:
    return [ln for ln in ENV.get(FLAGS_VAR, "").splitlines() if ln.strip()]


def _hold(background: bool) -> tuple[int, int]:
    """One shared probe start, launched as asked, held, closed: its window, in ms."""
    began = focus_watch.now_ms()
    boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, shared=True,
         window_flags=_flags(), program="PROBE.COM", background=background)
    must(M.call(server.resume), "releasing the probe")
    time.sleep(focus_gate.HOLD_S)
    close_whatever()
    return began, focus_watch.now_ms()


@M.section("O", "the focus gate's control, opening the run", O_CONTROL, FLAGS_VAR, place=0)
def section_o_control() -> None:
    tsv = Path(M.fresh("-focus.tsv"))
    watch = focus_watch.FocusWatch(tsv)
    watch.__enter__()
    WATCH.append(watch)
    print(f"  focus watch: {tsv}", flush=True)
    c = focus_gate.control(watch, NAMES, _hold)
    for spec, judged in zip(O_CONTROL, (c.front, c.behind, c.space), strict=True):
        if judged.status == "BLOCKED":
            M.block(spec.label, judged.reason)
        else:
            M.judge(spec.label, judged.status == "OK", judged.reason)
    if c.since is not None:
        SINCE.append(c.since)


@M.section("O", "the focus gate's verdict, closing the run", O_VERDICT, FLAGS_VAR, place=2)
def section_o_verdict() -> None:
    if not WATCH:
        M.block_rest("the control never started the watch")
        return
    v = focus_gate.verdict(WATCH.pop(), NAMES, SINCE[0] if SINCE else None,
                            focus_watch.now_ms())
    if v.status == "BLOCKED":
        M.block_rest(v.reason)
    else:
        M.judge(O_VERDICT[0].label, v.status == "OK", v.reason)
