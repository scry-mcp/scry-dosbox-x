"""Section O of the live matrix: DOSBox-X never came to the front and no Space moved during the run.

The control opens the run and the verdict closes it; without a control that held, or with no
section between them, the verdict is BLOCKED, never green, though a stolen focus is still a FAIL.
The control's start in front and its Space move take the owner's desk, so they run only with
SCRY_FOCUS_CONTROL=1. So does the full-screen cell on macOS, a Space of its own there: it runs
here, before the judged window opens.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from matrix_common import (
    ENV,
    GUEST,
    PROBE_CONF,
    SESSION_S,
    M,
    boot,
    cells,
    close_whatever,
    conf_without_launch,
    judged,
    must,
    refused,
    server,
    start_call,
)
from matrix_window import landed
from scry_core import focus_gate, focus_watch

NAMES = {"dosbox-x"}

O_CONTROL = cells(
    ("O the control: a shared start forced in front is seen in front",
     "known: macOS brings a newly launched app with a window to the front"),
    ("O the control: a shared start behind is never in front",
     "start docstring: `background`, true behind; and it moves no Space"),
    ("O the control: a Space moved on purpose is seen moved",
     "scry_core.focus_watch: SPACE_CHANGED"),
)
O_FULL_SCREEN = cells(
    ("O in a full-screen window the same cell arrives at the same driver coordinates",
     "REFERENCE.md, Input and the screen: the window's scale changes nothing the guest sees"),
)
O_VERDICT = cells(
    ("O no DOSBox-X came to the front and no Space moved while the sections ran",
     "REFERENCE.md, Input and the screen: nothing about the host is touched"),
)

WATCH: list[focus_watch.FocusWatch] = []
SINCE: list[int] = []


def _hold(background: bool) -> tuple[int, int]:
    """Start a shared probe, hold it, close it; return its window in ms."""
    began = focus_watch.now_ms()
    boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, shared=True,
         program="PROBE.COM", background=background)
    must(M.call(server.resume), "releasing the probe")
    time.sleep(focus_gate.HOLD_S)
    close_whatever()
    return began, focus_watch.now_ms()


def _full_screen() -> None:
    """The probe guest filling the display: the same cell, the same driver coordinates."""
    label = O_FULL_SCREEN[0].label
    if sys.platform == "darwin" and ENV.get(focus_gate.OPT_IN_VAR) != "1":
        M.block(label, "a full-screen window takes a Space of its own and runs only when asked: "
                       f"set {focus_gate.OPT_IN_VAR}=1 on an idle machine")
        return
    try:
        r = start_call(conf=str(conf_without_launch(PROBE_CONF, "PROBE.COM")), cwd=str(GUEST),
                       session_seconds=SESSION_S, logfile=M.fresh(".log"),
                       state_dir=M.fresh("-save"), shared=True, display=0, fullscreen=True,
                       background=True, program="PROBE.COM")
        # A build may refuse a parked full-screen start and leave the session live.
        if not refused(r, "window_not_visible"):
            must(r, "start did not come up")
        must(M.call(server.resume), "releasing the probe")
        must(M.call(server.log_wait, pattern="PROBE", channel="guest", seconds=30),
             "the probe's first line")
        r = M.call(server.send_mouse, x=40, y=12)
        judged(label, reply=r, holds=landed(r))
    finally:
        close_whatever()
        time.sleep(focus_gate.SPACE_SETTLE_S)


@M.section("O", "the focus gate's control, opening the run", O_CONTROL + O_FULL_SCREEN,
           opens=True)
def section_o_control() -> None:
    tsv = Path(M.fresh("-focus.tsv"))
    watch = focus_watch.FocusWatch(tsv)
    watch.__enter__()
    WATCH.append(watch)
    print(f"  focus watch: {tsv}", flush=True)
    c = focus_gate.control(watch, NAMES, _hold)
    for spec, cell in zip(O_CONTROL, (c.front, c.behind, c.space), strict=True):
        if cell.status == "BLOCKED":
            M.block(spec.label, cell.reason)
        else:
            M.judge(spec.label, cell.status == "OK", cell.reason)
    _full_screen()
    if c.since is not None:
        SINCE.append(focus_watch.now_ms())


@M.section("O", "the focus gate's verdict, closing the run", O_VERDICT, spans=True)
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
