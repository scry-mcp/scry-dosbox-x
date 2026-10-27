"""Section Z of the live matrix: control and input. The frame a stop is in and `until_frame` on
the package's DOS guest (`tests/guest/dosio.asm`); keys and the mouse posted to a PARKED machine on
the mouse guest (`mouse.asm`); and the motion a program that reads no position sees, on the motion
guest (`mickeys.asm`). Headless throughout."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    M,
    advanced,
    boot,
    cells,
    close_whatever,
    ok,
    refused,
    said,
    server,
)
from matrix_machine import boot_dosio, dosio_dir

WAIT_S = 20
#: The motion guest's line, its sums since it began (`mickeys.asm`'s header).
SUMS = re.compile(r"MICKEY \. (counters|ps2) dx=(-?\d+) dy=(-?\d+) events=(\d+)")
#: Two places the text mode's cells hold exactly, so a move lands where it was asked.
FROM, TO = (96, 48), (296, 120)
#: INT 33h's default ratio: one mickey a unit across, two a unit down.
MICKEYS_PER_UNIT = (1, 2)

Z_CELLS = cells(
    ("Z run_for frames=10 moves the frame a stop is in by exactly 10",
     "run_for docstring: `frame_before`, `frame_after`; known: RUNSTATE's frames= counts VRTs"),
    ("Z perform until_frame repeats run_for until a stop reads the frame",
     "perform docstring: `until_frame`, `frame_reached`"),
    ("Z perform until_frame on a frame the machine already passed is refused",
     "perform docstring; the control: a frame behind cannot be reached"),
    ("Z send_keys to a parked machine runs it by retraces until the program reads the key",
     "send_keys docstring: a stopped machine is run retrace by retrace; known: mouse.asm logs "
     "`key=97` for a"),
    ("Z the parked post leaves the machine stopped at a retrace, frames later",
     "send_keys docstring: left stopped at a retrace, with the stop's fields"),
    ("Z a parked post's e9 holds what the guest wrote on every retrace it ran, not the last",
     "send_keys docstring: the stop; input.md: the guest's lines of every retrace"),
    ("Z send_mouse to a parked machine places the pointer and the guest reads it there",
     "send_mouse docstring; known: mouse.asm logs each new position"),
    ("Z a move reaches INT 33h's motion counters, unit for unit at the default ratio",
     "send_mouse docstring: `motion`; known: mickeys.asm sums AX=0Bh; the ratio is 8:8 and 16:8"),
    ("Z a move reaches the movement handler a program installs with AX=0Ch",
     "known: mickeys.asm counts its AX=0Ch handler's calls"),
    ("Z a move reaches a PS/2 mouse the program drives through the BIOS",
     "known: mickeys.asm P sums its INT 15h C2h packets"),
)


def _mickeys(mode: str = "") -> None:
    where = Path(M.fresh("-mickeys"))
    where.mkdir(parents=True)
    for name in ("mickeys.com", "mickeys.conf"):
        shutil.copy2(GUEST / name, where / name)
    boot(conf=where / "mickeys.conf", cwd=where, program=f"MICKEYS.COM {mode}".strip())
    M.call(server.resume)
    ready = M.call(server.log_wait, channel="guest", pattern=r"MICKEY \. ready", seconds=WAIT_S)
    if not ok(ready):
        raise RuntimeError(f"the motion guest never got ready: {said(ready)}")


def _sums() -> tuple[int, int, int] | None:
    """The guest's last sums: dx, dy and the events, None before its first."""
    lines = M.call(server.log, channel="guest", pattern="MICKEY . (counters|ps2) ",
                   limit=1).get("lines") or []
    found = SUMS.search(lines[-1]) if lines else None
    return None if found is None else (int(found[2]), int(found[3]), int(found[4]))


def _moved_to(x: int, y: int) -> tuple[dict[str, Any], tuple[int, int, int] | None]:
    """A move, and the sums once the guest has written the event it makes."""
    before = _sums()
    moved = M.call(server.send_mouse, x=x, y=y, units="mouse")
    after = before
    for _ in range(WAIT_S * 10):
        after = _sums()
        if after is not None and (before is None or after[2] > before[2]):
            break
        M.call(server.log_wait, channel="guest", pattern="MICKEY", seconds=0.1)
    return moved, after


def _until(frame: object) -> None:
    if not isinstance(frame, int):
        for cell in Z_CELLS[1:3]:
            M.block(cell.label, f"the stop read no frame to count from: {frame}")
        return
    target = frame + 6
    window = M.call(server.perform, steps=[{"op": "run_for", "frames": 1}], summaries=True,
                    until_frame=target)
    M.judge(Z_CELLS[1].label, ok(window) and window.get("frame_reached") == target
            and window.get("steps_completed") == 6, said(window))
    behind = M.call(server.perform, steps=[{"op": "run_for", "frames": 1}], summaries=True,
                    until_frame=target)
    M.judge(Z_CELLS[2].label, refused(behind, "bad_argument")
            and f"stands at frame {target}" in str(behind.get("message")), said(behind))


@M.section("Z", "frames, input to a parked machine and the motion counters, on the package's "
           "guests", Z_CELLS)
def section_z() -> None:
    boot_dosio(dosio_dir())
    ran = advanced(M.call(server.run_for, frames=10), "run_for(frames=10)")
    before, after = ran.get("frame_before"), ran.get("frame_after")
    M.judge(Z_CELLS[0].label, isinstance(before, int) and isinstance(after, int)
            and after - before == 10 and ran.get("frame") == after,
            f"frame {before} -> {after}, stop {ran.get('frame')}")
    _until(ran.get("frame"))
    close_whatever()

    boot(conf=GUEST / "mouse.conf", program="MOUSE.COM")
    M.call(server.resume)
    M.call(server.log_wait, channel="guest", pattern=r"MOUSE \. reset", seconds=WAIT_S)
    parked = M.call(server.stop)
    keyed = M.call(server.send_keys, keys=["a"], expect=r"MOUSE \. key=97", seconds=WAIT_S)
    M.judge(Z_CELLS[3].label, ok(keyed) and (keyed.get("verify") or {}).get("seen") is True
            and int(keyed.get("polls") or 0) >= 1, said(keyed))
    status = M.call(server.status)
    frames = (parked.get("frame"), keyed.get("frame"))
    M.judge(Z_CELLS[4].label, ok(parked) and (status.get("session") or {}).get("running") is False
            and isinstance(frames[0], int) and isinstance(frames[1], int)
            and frames[1] > frames[0]
            and str(keyed.get("cause")).startswith("the retrace the input's post ran to"),
            f"frames {frames}, cause {keyed.get('cause')}")
    two = M.call(server.send_keys, keys=["b", "c"])
    lines = " ".join((two.get("e9") or {}).get("lines") or [])
    M.judge(Z_CELLS[5].label, ok(two) and "key=98" in lines and "key=99" in lines
            and int(two.get("polls") or 0) > 1, f"{two.get('polls')} retraces: {lines[:120]}")
    pointed = M.call(server.send_mouse, x=FROM[0], y=FROM[1], units="mouse",
                     expect=rf"MOUSE \. pos x={FROM[0]} y={FROM[1]} ", seconds=WAIT_S)
    M.judge(Z_CELLS[6].label, ok(pointed) and pointed.get("arrived") is True
            and (pointed.get("verify") or {}).get("seen") is True, said(pointed))
    close_whatever()

    _mickeys()
    _moved_to(*FROM)
    moved, first = _moved_to(*TO)
    sums = _sums()
    want = ((TO[0] - FROM[0]) * MICKEYS_PER_UNIT[0], (TO[1] - FROM[1]) * MICKEYS_PER_UNIT[1])
    _, settled = _moved_to(*FROM)
    got = None if first is None or settled is None else (settled[0] - first[0],
                                                          settled[1] - first[1])
    M.judge(Z_CELLS[7].label, ok(moved) and moved.get("motion") is True
            and got == (-want[0], -want[1]), f"back from {TO} to {FROM}: {got}, want "
            f"{(-want[0], -want[1])}; {sums}")
    M.judge(Z_CELLS[8].label, first is not None and settled is not None
            and settled[2] > first[2] > 0, f"events {first} -> {settled}")
    close_whatever()

    _mickeys("P")
    _moved_to(*FROM)
    _, packets = _moved_to(*TO)
    M.judge(Z_CELLS[9].label, packets is not None and packets[2] > 0
            and (packets[0], packets[1]) != (0, 0), f"ps2 sums {packets}")
    close_whatever()
