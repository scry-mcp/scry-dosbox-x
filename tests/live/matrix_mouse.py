"""Section P of the live matrix: the input route inside the guest, keys and the mouse, on the
package's mouse guest (`tests/guest/mouse.asm`), which writes on E9 what the DOS mouse driver
says. Headless throughout: what is judged is what the guest read, never a window, so nothing here
opens one or touches the host's focus or pointer.

Every pointer cell is judged twice over: the reply's read-back, and the guest's own line, which
the driver wrote independently of the server's report."""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from scry_dosbox_x import inputs, launch  # isort: skip
from matrix_common import (
    GUEST,
    MOUSE_CONF,
    MOUSE_PROGRAM,
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

KEYS_CONF = GUEST / "keys.conf"
KEYS_PROGRAM = "KEYS.COM"
#: Far more cycles a millisecond than the host executes: the guest's clock then runs well below
#: the wall's, which is what a make and its break spaced by wall time fall short in.
STARVED_CYCLES = ["-set", "cpu cycles=fixed 1000000"]
#: A BIOS tick, and the share of the wall time a starved guest's own time may reach.
BIOS_TICK_S = 0.0549
STARVED_SHARE = 0.75
KEY_LINE = re.compile(r"KEYS \. ([0-9A-F]{2}) t=([0-9A-F]{4})")
TICK_WRAP = 0x10000
ANNOUNCE = rf"STUB  \. scry device=present proto={inputs.STUB_PROTOCOL}"
WAIT_S = 20
#: The guest's line for a pointer at (x, y) in the driver's coordinates.
POS = r"MOUSE \. pos x={x} y={y} "

P_CELLS = cells(
    ("P start loads the stub before the program, which announces our protocol",
     "docs/reference/input.md: `program` needs no conf line"),
    ("P a second copy the conf also runs stays out, and keys still arrive whole",
     "guest/scry.asm: already resident; known: the guest logs `key=97` for a"),
    ("P a second copy stays out though a TSR took INT 1Ch above the first",
     "guest/scry.asm: IRQ 4's vector asked too; known: hook1c.com logs its hook"),
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
     "session: the nullmodem is transparent, so 0xFF is data"),
    ("P VBE 103h: pixel 799,599 arrives one to one, the reply naming the VBE mode",
     "docs/reference/input.md: under a VBE mode the units are VBE's resolution"),
    ("P VBE 103h: pixel 420,310 arrives, and the guest's driver agrees",
     "send_mouse docstring; known: the driver's range after a reset is the mode's size"),
    ("P VBE 103h: a pixel past 800x600 is refused, naming the VBE mode",
     "send_mouse docstring: refused before anything is sent"),
    ("P VBE 108h, a text mode: cell 79,59 arrives on the driver's range",
     "docs/reference/input.md: a VBE text mode counts cells"),
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
    ("P a guest that owns INT 08 without chaining still takes a key and a click",
     "guest/scry.asm: the UART's own interrupt; known: mouse.asm's o takes the timer"),
    ("P without a logfile the mouse and a key go in, the pointer off the stub's link",
     "docs/reference/input.md: the report rides the stub's own serial link"),
    ("P with the emulator starved below real speed, a key's break still lands a BIOS tick after "
     "its make in the guest's own clock",
     "send_keys docstring: a BIOS tick apart; known: keys.asm logs each scan byte "
     "with the tick count"),
    ("P ReChip, VBE 105h in protected mode: pixel 800,600 arrives, eight coordinates a pixel",
     "docs/reference/input.md: Allegro's I33 driver sets its range to the screen"),
    ("P ReChip: Allegro draws its arrow with its focus on the pixel asked",
     "known: Allegro 4's default arrow has its focus at (1, 1), src/mouse.c mouse_x_focus"),
    ("P ReChip: audio_record takes its AY render off the SB16, and audio_compare hears it",
     "audio_record and audio_compare docstrings; known: a PT3 song plays from the start"),
)
#: The directory of a ReChip build (RECHIP.EXE, CWSDPMI.EXE and their data), a private bench.
RECHIP_VAR = "RECHIP_DIR"
RECHIP_SONG = "PT3\\ZHARA.PT3"
#: Allegro's own config, beside the program: its INT 33h driver reads the driver's position.
ALLEGRO_CFG = "[mouse]\r\nmouse = I33\r\n"
#: A clock the host holds in real time: past it DOSBox-X's mixer drops whole blocks, and
#: `audio_record` refuses a file shorter than its run.
RECHIP_CONF = """[sdl]
autolock=false

[dosbox]
machine=svga_s3
memsize=64
bochs debug port e9 = true

[video]
vmemsize=8

[cpu]
core=normal
cputype=pentium_iii
cycles=fixed 100000

[sblaster]
sbtype=sb16
irq=7
dma=1
hdma=5
sbbase=220

[autoexec]
mount c "rechip"
c:
set BLASTER=A220 I7 D1 H5 T6
"""


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _mouse_boot(conf: Any = MOUSE_CONF, **kw: Any) -> None:
    boot(conf=conf, program=MOUSE_PROGRAM, **kw)
    release_running()


def _guest_line_count(pattern: str) -> int | None:
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
    judged("P start loads the stub before the program, which announces our protocol", reply=r,
           holds=ok(r))
    must(_guest_line(r"MOUSE \. reset"), "the guest reset the driver")
    r = M.call(server.send_keys, keys=["a"], expect=r"MOUSE \. key=97$", seconds=WAIT_S)
    judged("P a key reaches the guest: a is logged as key=97", reply=r,
           holds=ok(r) and r.get("route") == "guest")
    _pointer_cells()
    _buttons()
    before = _guest_line_count(r"MOUSE \. pos")
    off = [M.call(server.send_mouse, x=320, y=0), M.call(server.send_mouse, x=0, y=200)]
    time.sleep(1)
    M.judge("P a target off the screen is refused and the pointer does not move",
            all(refused(r, "bad_argument") and "outside the screen" in str(r.get("message"))
                for r in off)
            and before is not None and _guest_line_count(r"MOUSE \. pos") == before,
            f"{said(off[0], 60)}; {said(off[1], 60)}")
    shot = M.fresh(".png")
    r = M.call(server.snapshot, dest=shot, seconds=WAIT_S)
    judged("P snapshot headless: the stub's command writes a PNG, no window and no menu",
           reply=r, holds=ok(r) and r.get("route") == "guest" and Path(shot).is_file()
           and Path(shot).read_bytes()[:8] == PNG_MAGIC)
    _timer_owned()
    must(M.call(server.close), "closing")
    _twice()
    _twice(hooked=True)
    _no_log()
    _keys_spacing()
    _rechip()


def _keys_spacing() -> None:
    """The guest's own tick count at each scan byte, with the emulator starved."""
    label = next(c.label for c in P_CELLS if c.label.startswith("P with the emulator starved"))
    boot(conf=KEYS_CONF, program=KEYS_PROGRAM, flags=STARVED_CYCLES)
    release_running()
    must(_guest_line(r"KEYS \. up"), "the keys guest is up")
    began = time.monotonic()
    sent = M.call(server.send_keys, keys=["a", "b", "c"], expect=r"KEYS \. AE t=",
                  seconds=WAIT_S)
    wall_s = time.monotonic() - began
    heard = M.call(server.log, pattern=KEY_LINE.pattern, channel="guest", limit=40)
    scans = [(int(m[1], 16), int(m[2], 16)) for line in heard.get("lines", [])
             if (m := KEY_LINE.search(line))]
    makes = {code: tick for code, tick in scans if code < 0x80}
    gaps = {f"{code:02X}": (tick - makes[code & 0x7F]) % TICK_WRAP
            for code, tick in scans if code >= 0x80 and code & 0x7F in makes}
    emulated_s = ((scans[-1][1] - scans[0][1]) % TICK_WRAP) * BIOS_TICK_S if scans else 0.0
    if emulated_s >= STARVED_SHARE * wall_s:
        M.block(label, f"the host kept this emulator near real speed ({emulated_s:.2f} s of the "
                       f"guest's time in {wall_s:.2f} s), so nothing here was starved")
    else:
        M.judge(label, ok(sent) and len(gaps) == 3 and all(gap >= 1 for gap in gaps.values()),
                f"{said(sent, 60)}; ticks from each make to its break {gaps}, "
                f"{emulated_s:.2f} s of the guest's time in {wall_s:.2f} s")
    must(M.call(server.close), "closing")


def _timer_owned() -> None:
    """Many games take INT 08 and never chain the BIOS, so INT 1Ch never runs again."""
    replies = [M.call(server.send_keys, keys=["o"], expect=r"MOUSE \. timer=owned$",
                      seconds=WAIT_S),
               M.call(server.send_keys, keys=["a"], expect=r"MOUSE \. key=97$", seconds=WAIT_S),
               M.call(server.send_mouse, button="left", expect=r"b=1 presses=1$",
                      seconds=WAIT_S)]
    M.judge("P a guest that owns INT 08 without chaining still takes a key and a click",
            all(ok(r) and (r.get("verify") or {}).get("seen") is True for r in replies),
            "; ".join(said(r, 60) for r in replies))


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
    _vbe_cells()
    _mode("g", 0x13)
    must(M.call(server.send_mouse, x=100, y=50), "the pointer back at 100,50")


def _vbe(key: str, number: int) -> None:
    must(M.call(server.send_keys, keys=[key], expect=rf"MOUSE \. vbe={number}$",
                seconds=WAIT_S), f"switching the guest to VBE mode {number:#x}")


def _vbe_cells() -> None:
    _vbe("s", 0x103)
    r = M.call(server.send_mouse, x=799, y=599)
    judged("P VBE 103h: pixel 799,599 arrives one to one, the reply naming the VBE mode",
           reply=r, holds=_arrived(r, (799, 599), (799, 599))
           and (r.get("pointer") or {}).get("vbe_mode") == "0x103")
    # Off the centre, where the reset leaves the pointer and the guest has already logged it.
    r = M.call(server.send_mouse, x=420, y=310)
    seen = _guest_line(POS.format(x=420, y=310))
    judged("P VBE 103h: pixel 420,310 arrives, and the guest's driver agrees", reply=r,
           holds=_arrived(r, (420, 310), (420, 310)) and ok(seen))
    r = M.call(server.send_mouse, x=800, y=0)
    judged("P VBE 103h: a pixel past 800x600 is refused, naming the VBE mode", reply=r,
           holds=refused(r, "bad_argument") and "800 x 600 in VBE mode 0x103" in str(
               r.get("message")))
    _vbe("w", 0x108)
    r = M.call(server.send_mouse, x=79, y=59)
    # The middle of the cell's span: the driver snaps a BIOS text mode to its cell, not this one.
    judged("P VBE 108h, a text mode: cell 79,59 arrives on the driver's range", reply=r,
           holds=_arrived(r, (79, 59), (636, 476)))


def _buttons() -> None:
    released = _guest_line_count(r"b=0 presses=0$")
    r = M.call(server.send_mouse, button="left", expect=r"b=1 presses=1$", seconds=WAIT_S)
    time.sleep(1)
    judged("P a left click is seen by the guest: pressed once, then released", reply=r,
           holds=ok(r) and (r.get("verify") or {}).get("seen") is True
           and (r.get("pointer") or {}).get("buttons") == []
           and released is not None and _guest_line_count(r"b=0 presses=0$") == released + 1)
    r = M.call(server.send_mouse, button="right", action="down", expect=r" b=2 ",
               seconds=WAIT_S)
    up = M.call(server.send_mouse, button="right", action="up")
    judged("P the right button is the driver's second bit, held and released", reply=r,
           holds=ok(r) and (r.get("verify") or {}).get("seen") is True
           and (r.get("pointer") or {}).get("buttons") == ["right"]
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


def _twice(hooked: bool = False) -> None:
    """The conf runs the stub too, and `start` loads its own before the program: one copy
    stays, the other says so, and a key arrives whole (two parsers would split it). `hooked`
    loads `hook1c.com` on both sides of the conf's copy, so whichever copy runs first sits
    behind it."""
    text = MOUSE_CONF.read_text(encoding="utf-8")
    hook = "C:\\HOOK1C.COM\n" if hooked else ""
    stub = f'mount g "{launch.GUEST_DIR}"\n{hook}G:\\SCRY.COM\n{hook}c:\n'
    conf = M.fresh(".conf")
    with open(conf, "w", encoding="utf-8") as out:
        out.write(text.replace("[autoexec]\nmount c \".\"\nc:\n",
                               "[autoexec]\nmount c \".\"\n" + stub, 1))
    _mouse_boot(conf=conf)
    twice = _guest_line(r"STUB  \. scry already resident")
    r = M.call(server.send_keys, keys=["a", "b"], expect=r"MOUSE \. key=98$", seconds=WAIT_S)
    name = ("P a second copy stays out though a TSR took INT 1Ch above the first" if hooked
            else "P a second copy the conf also runs stays out, and keys still arrive whole")
    copies = _guest_line_count(r"STUB  \. scry device=present")
    judged(name, reply=r, holds=ok(twice) and ok(r) and copies == 1
           and (not hooked or _guest_line_count(r"HOOK1C \. int 1Ch hooked") == 2))
    must(M.call(server.close), "closing")


def _no_log() -> None:
    _mouse_boot(logfile=None)
    r = M.call(server.send_mouse, button="left")
    key = M.call(server.send_keys, keys=["a"])
    judged("P without a logfile the mouse and a key go in, the pointer off the stub's link",
           reply=r, holds=ok(r) and bool(r.get("pointer")) and ok(key)
           and key.get("route") == "guest")
    must(M.call(server.close), "closing")


def _rechip() -> None:
    """ReChip (DJGPP, Allegro 4, VBE 105h through CWSDPMI), a private program: a copy of the
    build the variable names runs in this run's scratch, since it writes its settings beside
    itself, with Allegro told to read the driver (`ALLEGRO_CFG`)."""
    labels = [c.label for c in P_CELLS if c.label.startswith("P ReChip")]
    held = os.environ.get(RECHIP_VAR, "")
    if not held or not (Path(held) / "RECHIP.EXE").is_file():
        for label in labels:
            M.block(label, f"{RECHIP_VAR} names no directory holding RECHIP.EXE: ReChip is a "
                           f"private program, run only where its build is named")
        return
    place = Path(M.fresh("-rechip"))
    shutil.copytree(held, place / "rechip")
    (place / "rechip" / "ALLEGRO.CFG").write_text(ALLEGRO_CFG, encoding="ascii")
    conf = place / "rechip.conf"
    conf.write_text(RECHIP_CONF, encoding="ascii")
    boot(conf=conf, cwd=place, program=f"RECHIP.EXE {RECHIP_SONG}", captures_dir=M.fresh("-cap"))
    must(M.call(server.resume), "letting ReChip start")
    _rechip_pointer()
    _rechip_sound()
    must(M.call(server.close), "closing")


def _allegro_ready() -> dict[str, Any]:
    """Allegro sets the driver's range to its screen, eight coordinates a pixel, once it is up."""
    for _ in range(90):
        r = M.call(server.send_mouse, x=0, y=0, units="mouse")
        if ok(r) and ((r.get("pointer") or {}).get("mouse") or {}).get("max_x") == 1023 * 8:
            return r
        time.sleep(1)
    raise RuntimeError(f"ReChip's Allegro never set the driver's range: {said(r)}")


#: A still stretch of ReChip's screen, the menu bar's empty middle: the arrow is the only change.
STILL = [580, 0, 48, 40]
TIP = (600, 4)
#: Allegro 4 draws its default arrow from one pixel up and left of the pointer.
ALLEGRO_FOCUS = (1, 1)


def _crop(name: str) -> str:
    must(M.call(server.stop), f"stopping for {name}")
    dest = M.fresh(f"-{name}.png")
    must(M.call(server.screen_view, crop=STILL, scale=1, dest=dest, attach=False),
         f"reading {name}")
    must(M.call(server.resume), "running ReChip again")
    return dest


def _screens_identical(a: str, b: str) -> bool:
    r = M.call(server.image_compare, method="image", a=a, b=b)
    return ok(r) and r.get("differing_pixels") == 0


def _main_screen() -> str:
    """The still stretch once ReChip has left its loading screen (the first crop, taken as
    Allegro came up) and holds still: two crops a second apart, alike, and unlike the first."""
    loading = previous = _crop("away")
    for _ in range(60):
        time.sleep(1)
        now = _crop("away")
        if not _screens_identical(now, loading) and _screens_identical(now, previous):
            return now
        previous = now
    raise RuntimeError("ReChip's main screen never held still")


def _rechip_pointer() -> None:
    _allegro_ready()
    away = _main_screen()
    r = M.call(server.send_mouse, x=800, y=600)
    judged("P ReChip, VBE 105h in protected mode: pixel 800,600 arrives, eight coordinates a "
           "pixel", reply=r, holds=_arrived(r, (800, 600), (6404, 4804))
           and (r.get("pointer") or {}).get("vbe_mode") == "0x105")
    must(M.call(server.send_mouse, x=TIP[0], y=TIP[1]), "the pointer to the still stretch")
    there = _crop("there")
    diff = M.call(server.image_compare, method="image", a=away, b=there)
    box = diff.get("bbox")
    M.judge("P ReChip: Allegro draws its arrow with its focus on the pixel asked",
            ok(diff) and isinstance(box, list)
            and (STILL[0] + box[0] + ALLEGRO_FOCUS[0], STILL[1] + box[1] + ALLEGRO_FOCUS[1])
            == TIP, said(diff))


def _rechip_sound() -> None:
    must(M.call(server.stop), "stopping for the recording")
    wav = M.call(server.audio_record, seconds=30, frames=140, dest=M.fresh(".wav"))
    heard = (M.call(server.audio_compare, method="measure", path=str(wav.get("path")))
             if ok(wav) else wav)
    measures = heard.get("measures") or [{}]
    M.judge("P ReChip: audio_record takes its AY render off the SB16, and audio_compare hears it",
            ok(wav) and ok(heard) and all(m.get("silent") is False for m in measures),
            f"{said(wav, 60)}; {said(heard, 80)}")
    must(M.call(server.resume), "running ReChip again")
