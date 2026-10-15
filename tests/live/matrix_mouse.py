"""Section P of the live matrix: the input route inside the guest, keys and the mouse, on the
package's mouse guest (`tests/guest/mouse.asm`), which writes on E9 what the DOS mouse driver
says. Headless throughout: what is judged is what the guest read, never a window, so nothing here
opens one or touches the host's focus or pointer.

Every pointer cell is judged twice over: the reply's read-back, and the guest's own line, which
the driver wrote independently of the server's report."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    M,
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

MOUSE_CONF = GUEST / "mouse.conf"
MOUSE_PROGRAM = "MOUSE.COM"
ANNOUNCE = r"STUB  \. inject device=present proto=2"
WAIT_S = 20
#: The guest's line for a pointer at (x, y) in the driver's coordinates.
POS = r"MOUSE \. pos x={x} y={y} "

P_CELLS = cells(
    ("P start loads the stub before the program, which announces protocol 2",
     "REFERENCE.md, Input and the screen: `program` needs no conf line"),
    ("P a second copy the conf also runs stays out, and keys still arrive whole",
     "guest/inject.asm: already resident; known: the guest logs `key=97` for a"),
    ("P a key reaches the guest: a is logged as key=97",
     "send_keys docstring; known: mouse.asm logs each key's ASCII"),
    ("P text mode: x=0 y=0 arrives, the driver at 0,0",
     "send_mouse docstring: `screen` units are cells in a text mode"),
    ("P text mode: the driver puts a raw 21 on its cell, said as not arrived",
     "send_mouse docstring: `arrived` false and `asked` when the driver placed it elsewhere"),
    ("P mode 13h: pixel 100,50 arrives, the driver at 200,50, the guest agrees",
     "send_mouse docstring; measured: 320 pixels over a 640 driver range"),
    ("P mode 13h: the far corner 319,199 arrives", "send_mouse docstring: the screen's own bounds"),
    ("P mode 12h: pixel 639,479 arrives one to one", "send_mouse docstring: 640x480 pixels"),
    ("P mode 12h: a coordinate pair of 0xFF bytes arrives whole, the driver at 255,255",
     "dosbox_session: the nullmodem is transparent, so 0xFF is data"),
    ("P a left click is seen by the guest: pressed once, then released",
     "send_mouse docstring: `click`; known: mouse.asm counts AX=05h presses"),
    ("P the right button is the driver's second bit, held and released",
     "send_mouse docstring: `right`; known: INT 33h AX=03h reports it as bit 1"),
    ("P a double click is two presses the guest counts",
     "send_mouse docstring: `double` is two clicks a tick apart"),
    ("P a drag: down holds the button in the read-back, up releases it",
     "send_mouse docstring: `down`, a move, `up`"),
    ("P a target off the screen is refused and the pointer does not move",
     "send_mouse docstring: refused before anything is sent"),
    ("P snapshot headless: the stub's command writes a PNG, no window and no menu",
     "snapshot docstring: taken inside the guest, any session"),
    ("P without a logfile the mouse is refused naming it, and a key still goes in",
     "send_mouse docstring: the read-back goes through the log"),
)


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _mouse_boot(conf: Any = MOUSE_CONF, **kw: Any) -> None:
    boot(conf=conf, program=MOUSE_PROGRAM, **kw)
    release_running()


def _count(pattern: str) -> int | None:
    """How many guest lines match so far, None when the log could not be read."""
    r = M.call(server.log, pattern=pattern, channel="guest", limit=1)
    total = r.get("lines_total")
    return total if ok(r) and isinstance(total, int) else None


def _guest_line(pattern: str) -> dict[str, Any]:
    return M.call(server.log_wait, pattern=pattern, channel="guest", seconds=WAIT_S)


def _arrived(r: dict[str, Any], screen: tuple[int, int], mouse: tuple[int, int]) -> bool:
    pointer = r.get("pointer") or {}
    at_screen = pointer.get("screen") or {}
    at_mouse = pointer.get("mouse") or {}
    return (ok(r) and r.get("arrived") is True
            and (at_screen.get("x"), at_screen.get("y")) == screen
            and (at_mouse.get("x"), at_mouse.get("y")) == mouse)


def _mode(key: str, number: int) -> None:
    must(M.call(server.send_keys, keys=[key], expect=rf"MOUSE \. mode={number}$",
                seconds=WAIT_S), f"switching the guest to mode {number}")


@M.section("P", "the input route inside the guest: keys and the mouse, headless", P_CELLS)
def section_p() -> None:
    caps = Path(M.fresh("-captures"))
    caps.mkdir()
    _mouse_boot(captures_dir=str(caps))
    r = _guest_line(ANNOUNCE)
    judged("P start loads the stub before the program, which announces protocol 2", reply=r,
           holds=ok(r))
    must(_guest_line(r"MOUSE \. reset"), "the guest reset the driver")
    r = M.call(server.send_keys, keys=["a"], expect=r"MOUSE \. key=97$", seconds=WAIT_S)
    judged("P a key reaches the guest: a is logged as key=97", reply=r,
           holds=ok(r) and r.get("route") == "guest")
    _pointer_cells()
    _buttons()
    before = _count(r"MOUSE \. pos")
    off = [M.call(server.send_mouse, x=320, y=0), M.call(server.send_mouse, x=0, y=200)]
    time.sleep(1)
    M.judge("P a target off the screen is refused and the pointer does not move",
            all(refused(r, "bad_argument") and "outside the screen" in str(r.get("message"))
                for r in off) and before is not None and _count(r"MOUSE \. pos") == before,
            f"{said(off[0], 60)}; {said(off[1], 60)}")
    shot = M.fresh(".png")
    r = M.call(server.snapshot, dest=shot, seconds=WAIT_S)
    judged("P snapshot headless: the stub's command writes a PNG, no window and no menu",
           reply=r, holds=ok(r) and r.get("route") == "guest" and Path(shot).is_file()
           and Path(shot).read_bytes()[:8] == PNG_MAGIC)
    must(M.call(server.close), "closing")
    _twice()
    _no_log()


def _pointer_cells() -> None:
    r = M.call(server.send_mouse, x=0, y=0)
    judged("P text mode: x=0 y=0 arrives, the driver at 0,0", reply=r,
           holds=_arrived(r, (0, 0), (0, 0)))
    r = M.call(server.send_mouse, x=21, y=8, units="mouse")
    judged("P text mode: the driver puts a raw 21 on its cell, said as not arrived", reply=r,
           holds=ok(r) and r.get("arrived") is False and r.get("asked") == {"x": 21, "y": 8}
           and (r.get("pointer") or {}).get("mouse", {}).get("x") == 16)
    _mode("g", 0x13)
    r = M.call(server.send_mouse, x=100, y=50)
    seen = _guest_line(POS.format(x=200, y=50))
    judged("P mode 13h: pixel 100,50 arrives, the driver at 200,50, the guest agrees",
           reply=r, holds=_arrived(r, (100, 50), (200, 50)) and ok(seen))
    r = M.call(server.send_mouse, x=319, y=199)
    judged("P mode 13h: the far corner 319,199 arrives", reply=r,
           holds=_arrived(r, (319, 199), (638, 199)))
    _mode("v", 0x12)
    r = M.call(server.send_mouse, x=639, y=479)
    judged("P mode 12h: pixel 639,479 arrives one to one", reply=r,
           holds=_arrived(r, (639, 479), (639, 479)))
    # ONE UNIT A STEP on both axes in 12h, so an odd coordinate is not the driver rounding it.
    r = M.call(server.send_mouse, x=255, y=255, units="mouse")
    judged("P mode 12h: a coordinate pair of 0xFF bytes arrives whole, the driver at 255,255",
           reply=r, holds=ok(r) and r.get("arrived") is True)
    _mode("g", 0x13)
    must(M.call(server.send_mouse, x=100, y=50), "the pointer back at 100,50")


def _buttons() -> None:
    released = _count(r"b=0 presses=0$")
    r = M.call(server.send_mouse, button="left", expect=r"b=1 presses=1$", seconds=WAIT_S)
    time.sleep(1)
    judged("P a left click is seen by the guest: pressed once, then released", reply=r,
           holds=ok(r) and (r.get("pointer") or {}).get("buttons") == []
           and released is not None and _count(r"b=0 presses=0$") == released + 1)
    r = M.call(server.send_mouse, button="right", action="down", expect=r" b=2 ",
               seconds=WAIT_S)
    up = M.call(server.send_mouse, button="right", action="up")
    judged("P the right button is the driver's second bit, held and released", reply=r,
           holds=ok(r) and (r.get("pointer") or {}).get("buttons") == ["right"]
           and ok(up) and (up.get("pointer") or {}).get("buttons") == [])
    before = M.call(server.log, pattern=r"b=1 presses=1$", channel="guest", limit=1)
    r = M.call(server.send_mouse, button="left", action="double")
    time.sleep(1)
    after = M.call(server.log, pattern=r"b=1 presses=1$", channel="guest", limit=1)
    pressed = (after.get("lines_total") or 0) - (before.get("lines_total") or 0)
    M.judge("P a double click is two presses the guest counts",
            ok(r) and ok(before) and ok(after) and pressed == 2,
            f"{pressed} presses counted; {said(r, 60)}")
    down = M.call(server.send_mouse, button="left", action="down")
    moved = M.call(server.send_mouse, x=150, y=60)
    up_r = M.call(server.send_mouse, button="left", action="up")
    judged("P a drag: down holds the button in the read-back, up releases it", reply=up_r,
           holds=ok(down) and (down.get("pointer") or {}).get("buttons") == ["left"]
           and ok(moved) and (moved.get("pointer") or {}).get("buttons") == ["left"]
           and ok(up_r) and (up_r.get("pointer") or {}).get("buttons") == [])


def _twice() -> None:
    """The conf runs the stub too, and `start` loads its own before the program: one copy
    stays, the other says so, and a key arrives whole (two parsers would split it)."""
    text = MOUSE_CONF.read_text(encoding="utf-8")
    stub = f'mount g "{GUEST.parent.parent / "guest"}"\nG:\\INJECT.COM\nc:\n'
    conf = M.fresh(".conf")
    with open(conf, "w", encoding="utf-8") as out:
        out.write(text.replace("[autoexec]\nmount c \".\"\nc:\n",
                               "[autoexec]\nmount c \".\"\n" + stub, 1))
    _mouse_boot(conf=conf)
    twice = _guest_line(r"STUB  \. inject already resident")
    r = M.call(server.send_keys, keys=["a", "b"], expect=r"MOUSE \. key=98$", seconds=WAIT_S)
    judged("P a second copy the conf also runs stays out, and keys still arrive whole",
           reply=r, holds=ok(twice) and ok(r))
    must(M.call(server.close), "closing")


def _no_log() -> None:
    _mouse_boot(logfile=None)
    r = M.call(server.send_mouse, button="left")
    key = M.call(server.send_keys, keys=["a"])
    judged("P without a logfile the mouse is refused naming it, and a key still goes in",
           reply=r, holds=refused(r, "no_channel") and "logfile" in str(r.get("message"))
           and ok(key) and key.get("route") == "guest")
    must(M.call(server.close), "closing")
