"""Section O of the live matrix: whether DOSBox-X came to the front during the run, sampled from
outside it (`scry_core.focus_watch`) for its whole length.

It is two sections under one letter: the CONTROL opens the run and the VERDICT closes it, so the
watch the control starts samples every section between. The control, in the same harness the
verdict is taken in: one shared start forced in front, which the watch must see in front, and
one behind, which it must not; a watch that cannot see the first clears nothing, so without the
control the verdict is BLOCKED, as it is when too little ran or the watch could not sample:
never green, and never counted as the server's FAIL. Judged by process name, so another
DOSBox-X in front would count. Nothing is excluded: no tool clicks a menu any more, and section
G's windows open behind. The control's front start takes the owner's focus for a few seconds: a
run with this section is announced.
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
from scry_core import focus_watch

FLAGS_VAR = "DOSBOX_X_LIVE_WINDOW_FLAGS"
NAMES = {"dosbox-x"}
HOLD_S = 4.0
#: Shorter than this outside the exclusions, a judged window says too little to be a verdict.
MIN_JUDGED_MS = 60_000

O_CONTROL = cells(
    ("O the control: a shared start forced in front is seen in front",
     "known: macOS brings a newly launched app with a window to the front"),
    ("O the control: a shared start behind is never in front",
     "start docstring: `background`, true behind"),
)
O_VERDICT = cells(
    ("O no DOSBox-X came to the front while the sections ran",
     "REFERENCE.md, Input and the screen: nothing about the host is touched"),
)

#: The watch the control started, and its start of the judged window.
WATCH: list[focus_watch.FocusWatch] = []
SINCE: list[int] = []


def _now_ms() -> int:
    return int(time.time() * 1000)


def _flags() -> list[str]:
    return [ln for ln in ENV.get(FLAGS_VAR, "").splitlines() if ln.strip()]


def _hold(background: bool) -> tuple[int, int]:
    """One shared probe start, launched as asked, held, closed: its window, in ms."""
    began = _now_ms()
    boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, mode="shared",
         window_flags=_flags(), program="PROBE.COM", background=background)
    must(M.call(server.resume), "releasing the probe")
    time.sleep(HOLD_S)
    close_whatever()
    return began, _now_ms()


@M.section("O", "the focus gate's control, opening the run", O_CONTROL, FLAGS_VAR, place=0)
def section_o_control() -> None:
    tsv = Path(M.fresh("-focus.tsv"))
    watch = focus_watch.FocusWatch(tsv)
    watch.__enter__()
    WATCH.append(watch)
    print(f"  focus watch: {tsv}", flush=True)
    front, behind = _hold(background=False), _hold(background=True)
    seen = focus_watch.judge(watch.samples, NAMES, start_ms=front[0], end_ms=front[1])
    M.judge("O the control: a shared start forced in front is seen in front",
            seen.status == "TOOK_FOCUS", seen.reason)
    clean = focus_watch.judge(watch.samples, NAMES, start_ms=behind[0], end_ms=behind[1])
    M.judge("O the control: a shared start behind is never in front",
            clean.status == "CLEAN", clean.reason)
    if seen.status == "TOOK_FOCUS" and clean.status == "CLEAN":
        SINCE.append(behind[1])


@M.section("O", "the focus gate's verdict, closing the run", O_VERDICT, FLAGS_VAR, place=2)
def section_o_verdict() -> None:
    label = O_VERDICT[0].label
    if not WATCH:
        M.block_rest("the control never started the watch")
        return
    watch = WATCH.pop()
    watch.__exit__(None, None, None)
    if not SINCE:
        M.block_rest(f"the control did not hold, so the watch clears nothing; record {watch.path}")
        return
    end = _now_ms()
    judged = end - SINCE[0]
    if judged < MIN_JUDGED_MS:
        # TOO LITTLE RAN between the control and the verdict (O alone): no verdict to give.
        M.block_rest(f"{judged} ms ran after the control, too little to judge; "
                     f"record {watch.path}")
        return
    v = focus_watch.judge(watch.samples, NAMES, start_ms=SINCE[0], end_ms=end)
    if v.status == "INVALID":
        # THE INSTRUMENT, not the server: a sample it could not take, or a stretch unsampled.
        M.block_rest(f"the watch cannot judge the run: {v.reason}; record {watch.path}")
        return
    M.judge(label, v.status == "CLEAN",
            f"{v.status}: {v.reason}; record {watch.path}")
