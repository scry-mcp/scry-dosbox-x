"""Section J of the live matrix: the screen, read from the VGA's listings and video memory, on
the package's two guests. The probe guest gives the BIOS's own state; the screen guest
(`tests/guest/screen.asm`) draws things whose every byte is its own arithmetic and stops at its
own `int 3` after each, so every answer here is known before the run.

The program sections (D, F) judge the same tools on whole programs, through the helpers at the
end of this file."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    M,
    advanced,
    alive,
    boot,
    cells,
    judged,
    must,
    ok,
    read_bytes,
    refused,
    release_running,
    said,
    server,
    videos,
)

import dosbox_grammar as grammar

SCREEN_CONF = GUEST / "screen.conf"
SCREEN_PROGRAM = "SCREEN.COM"
#: What the guest's six stops show, in order (its header says why each exists).
SCREEN_STOPS = ("text", "start80", "dac01", "13h", "13h-start80", "12h")
#: `int 3`, the instruction every stop of the screen guest parks on.
INT3 = bytes.fromhex("CD03")
#: The VGA listings `machine_map`'s `vga` section is read from, in order.
VGA_COMMANDS = ["VGA MODE", "VGA CRTC", "VGA SEQ", "VGA GC", "VGA AC", "VGA DAC", "VGA DRAW"]

J_CELLS = cells(
    ("J palette at the park: 256 entries, every one zero",
     "measured: no video mode is set at the park, the DAC is unwritten"),
    ("J palette once booted: entry 1 is the BIOS's 00 00 2A, #0000aa",
     "palette docstring; known: the BIOS's standard set, its widening the emulator's"),
    ("J machine_map's vga once booted: M_TEXT, the seven listings named",
     "machine_map docstring: `vga`, one key per listing"),
    ("J palette first=256 is refused before anything is typed", "palette docstring: 0 to 255"),
    ("J palette with a relative dest is refused", "palette docstring: an absolute `dest`"),
    ("J the debugger takes a command after VGA DACPAL",
     "REFERENCE.md, The debugger channel: one request, the lines it printed"),
    ("J palette on a running guest is refused", "palette docstring: not_stopped"),
    ("J palette without a logfile reads its listings all the same",
     "REFERENCE.md, The debugger channel: every reading goes through it"),
    ("J the screen guest stops at its own int 3, six times",
     "start docstring: break_on_int3; known: screen.asm ends each step in `int 3`"),
    ("J the DAC write changes entry 1 to 3F 00 00 and no other",
     "known: screen.asm step 3 writes entry 1 through ports 3C8h and 3C9h"),
    ("J in 13h the DAC is the guest's ramp, entry by entry",
     "known: screen.asm step 4 sets entry i to (i & 3F, (i >> 1) & 3F, (i >> 2) & 3F)"),
    ("J palette's picture of the whole DAC is 256 x 256, its sha256 the file's",
     "palette docstring: sixteen squares a row, `image`"),
    ("J machine_map's vga names M_VGA chained in 13h and M_EGA in 12h",
     "machine_map docstring; known: screen.asm sets modes 13h and 12h"),
    ("J screen_view at the park is refused naming M_ERROR and capture_frame",
     "screen_view docstring: a mode not read, named; measured: no mode set at the park"),
    ("J screen_wait from the park finds PROBE.COM after a retrace or more, on its row",
     "screen_wait docstring; known: the autoexec echoes the launch line once DOS has booted"),
    ("J screen_wait for a string never printed expires with its polls and the last page",
     "screen_wait docstring: TIMEOUT with polls and text"),
    ("J screen_wait with an empty text is refused before anything is typed",
     "screen_wait docstring: 1 to 132 characters"),
    ("J screen_wait on a running guest is refused", "screen_wait docstring: not_stopped"),
    ("J screen_view once booted: C:\\>PROBE.COM on its row, the cursor under it",
     "screen_view docstring; known: the autoexec's four lines, the cursor on the fifth row"),
    ("J screen_signature is one string for the probe's still page, a retrace apart",
     "screen_signature docstring; known: the probe writes to port E9, never to the screen"),
    ("J screen_view with a dest in a text mode is refused", "screen_view docstring"),
    ("J screen_view and screen_signature on a running guest are refused",
     "screen_view and screen_signature docstrings: not_stopped"),
    ("J screen_view without a logfile is refused only for the screen it finds",
     "REFERENCE.md, The debugger channel: every reading goes through it"),
    ("J the text stop reads the guest's two lines, the cursor under them",
     "known: screen.asm step 1 prints two lines through DOS"),
    ("J the start-address stop shows the page from its second row",
     "known: screen.asm step 2 sets the CRTC start to 80"),
    ("J screen_signature moves when the page shown moves, and holds through a DAC write no "
     "cell shows",
     "screen_signature docstring: each cell in the colour it is shown in; known: step 2 moves "
     "the start and puts it back after its stop, step 3 changes entry 1, which no cell of "
     "DOS's attribute 07 draws"),
    ("J the 13h picture's pixel (x, y) is (x + y) & FF through the guest's DAC",
     "known: screen.asm step 4; REFERENCE.md, Input and the screen: the widening"),
    ("J the 13h picture equals the emulator's own capture of that frame, pixel for pixel",
     "REFERENCE.md, Input and the screen: each pixel doubled equals the capture's frame"),
    ("J the 13h start-address stop shows the picture from its next row",
     "known: screen.asm step 5 sets the CRTC start to 80, four bytes a unit"),
    ("J screen_view and screen_signature read the 12h stop from video memory",
     "REFERENCE.md, Input and the screen: the screen is read from video memory"),
    ("J the screen guest closes", "close docstring"),
)


def _rgb24(png: str) -> bytes:
    """A PNG's pixels as RGB, decoded by ffmpeg: one decoder for the server's indexed picture and
    for the emulator's own capture, so neither is judged by the code that wrote it."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-f", "rawvideo", "-pix_fmt",
                          "rgb24", "-"], capture_output=True, check=True, timeout=60)
    return out.stdout


def _widen(six: int) -> int:
    return (six << 2) | (six >> 4)


def _known_13h(shift_rows: int) -> bytes:
    """The guest's 13h picture as RGB, from its own arithmetic: pixel (x, y) is index
    (x + y) & FF of the ramp, widened; from `shift_rows` rows on, and zero past the window's
    written bytes."""
    index = bytes((x + y) & 0xFF for y in range(200) for x in range(320)) + bytes(320)
    ramp = [(_widen(i & 0x3F), _widen((i >> 1) & 0x3F), _widen((i >> 2) & 0x3F))
            for i in range(256)]
    return b"".join(bytes(ramp[i]) for i in index[shift_rows * 320:shift_rows * 320 + 64000])


def _doubled(rgb: bytes, width: int, height: int) -> bytes:
    """A picture with every pixel doubled each way, as the emulator renders 13h at 640 x 400."""
    rows = [b"".join(rgb[(y * width + x) * 3:(y * width + x) * 3 + 3] * 2 for x in range(width))
            for y in range(height)]
    return b"".join(row + row for row in rows)


def _ramp() -> list[str]:
    return [f"{i & 0x3F:02x}{(i >> 1) & 0x3F:02x}{(i >> 2) & 0x3F:02x}"
            for i in range(256)]


@M.section("J", "the screen from the VGA's listings and video memory, on the package's guests",
           J_CELLS)
def section_j() -> None:
    _probe()
    _screen_guest()


def _probe() -> None:
    boot()
    M.setup()
    r = M.call(server.palette)
    judged("J palette at the park: 256 entries, every one zero", reply=r,
           holds=ok(r) and r.get("entries") == 256 and set(r.get("rgb") or []) == {"000000"})
    r = M.call(server.screen_view)
    judged("J screen_view at the park is refused naming M_ERROR and capture_frame", reply=r,
           holds=refused(r, "no_channel") and "`M_ERROR`" in str(r.get("message"))
           and "capture_frame" in str(r.get("message")))
    r = M.call(server.screen_wait, text="PROBE.COM", seconds=30)
    judged("J screen_wait from the park finds PROBE.COM after a retrace or more, on its row",
           reply=r, holds=ok(r) and r.get("already") is False and int(r.get("polls") or 0) >= 1
           and r.get("point") == [4, 3] and r.get("line") == "C:\\>PROBE.COM")
    r = M.call(server.screen_view)
    judged("J screen_view once booted: C:\\>PROBE.COM on its row, the cursor under it",
           reply=r, holds=ok(r) and (r.get("text") or [""] * 4)[3] == "C:\\>PROBE.COM"
           and r.get("cursor") == [0, 4])
    one = M.call(server.screen_signature)
    advanced(M.call(server.run_for, frames=1), "one more retrace on the probe")
    two = M.call(server.screen_signature)
    M.judge("J screen_signature is one string for the probe's still page, a retrace apart",
            ok(one) and ok(two) and isinstance(one.get("signature"), str)
            and one.get("signature") == two.get("signature"),
            f"{one.get('signature')} then {two.get('signature')}")
    r = M.call(server.screen_view, dest=M.fresh(".png"))
    judged("J screen_view with a dest in a text mode is refused", reply=r,
           holds=refused(r, "bad_argument"))
    r = M.call(server.screen_wait, text="")
    judged("J screen_wait with an empty text is refused before anything is typed", reply=r,
           holds=refused(r, "bad_argument"))
    r = M.call(server.screen_wait, text="NO GUEST PRINTS THIS", seconds=3)
    judged("J screen_wait for a string never printed expires with its polls and the last page",
           reply=r, holds=ok(r) and r.get("verdict") == "TIMEOUT"
           and int(r.get("polls") or 0) >= 1 and "C:\\>PROBE.COM" in (r.get("text") or []))
    r = M.call(server.palette, first=1, count=1)
    judged("J palette once booted: entry 1 is the BIOS's 00 00 2A, #0000aa", reply=r,
           holds=ok(r) and r.get("rgb") == ["00002a"] and r.get("colors") == ["#0000aa"])
    r = M.call(server.debug, command="BPLIST")
    judged("J the debugger takes a command after VGA DACPAL", reply=r,
           holds=ok(r) and "not recognized" not in str(r.get("output"))
           and grammar.BPLIST_HEADER in str(r.get("output")))
    r = M.call(server.machine_map, sections=["vga"])
    vga = r.get("vga") or {}
    judged("J machine_map's vga once booted: M_TEXT, the seven listings named", reply=r,
           holds=ok(r) and (vga.get("mode") or {}).get("mode") == "M_TEXT"
           and (r.get("sources") or {}).get("vga") == VGA_COMMANDS)
    r = M.call(server.palette, first=256)
    judged("J palette first=256 is refused before anything is typed", reply=r,
           holds=refused(r, "bad_argument"))
    r = M.call(server.palette, dest="relative.png")
    judged("J palette with a relative dest is refused", reply=r, holds=refused(r, "bad_argument"))
    release_running()
    M.setup()
    r = M.call(server.palette)
    judged("J palette on a running guest is refused", reply=r,
           holds=refused(r, "not_stopped") and alive(r))
    r = M.call(server.screen_wait, text="PROBE.COM", seconds=3)
    judged("J screen_wait on a running guest is refused", reply=r,
           holds=refused(r, "not_stopped") and alive(r))
    view, sig = M.call(server.screen_view), M.call(server.screen_signature)
    M.judge("J screen_view and screen_signature on a running guest are refused",
            refused(view, "not_stopped") and refused(sig, "not_stopped") and alive(sig),
            f"{view.get('code')}, {sig.get('code')}")
    must(M.call(server.close), "closing the probe")
    boot(logfile="")
    M.setup()
    r = M.call(server.palette)
    judged("J palette without a logfile reads its listings all the same", reply=r,
           holds=ok(r) and r.get("entries") == 256)
    # At the reset park no video mode is set, which is the refusal it may give.
    r = M.call(server.screen_view)
    judged("J screen_view without a logfile is refused only for the screen it finds", reply=r,
           holds=(ok(r) or refused(r, "no_channel")) and "logfile" not in str(r.get("message")))
    must(M.call(server.close), "closing the probe without a logfile")


def _screen_guest() -> None:
    boot(conf=SCREEN_CONF, program=SCREEN_PROGRAM, break_on_int3=True, capture_video=True,
         captures_dir=M.fresh("-cap"))
    M.setup()
    landed: list[str] = []
    dacs: dict[str, list[str]] = {}
    modes: dict[str, Any] = {}
    sigs: dict[str, Any] = {}
    for stop in SCREEN_STOPS:
        M.setup()
        r = M.call(server.resume, seconds=30)
        here = str(r.get("pc"))
        if ok(r) and "stop_seq" in r and read_bytes(here, 2) == INT3:
            landed.append(stop)
        if stop in ("start80", "dac01", "13h"):
            dacs[stop] = M.call(server.palette).get("rgb") or []
        if stop == "13h":
            dest = M.fresh(".png")
            pic = M.call(server.palette, scale=1, dest=dest)
            image = pic.get("image") or {}
            path = Path(dest)
            judged("J palette's picture of the whole DAC is 256 x 256, its sha256 the file's",
                   reply=pic, holds=ok(pic) and (image.get("width"), image.get("height"))
                   == (256, 256) and path.is_file()
                   and image.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest())
        if stop in ("13h", "12h"):
            vga = M.call(server.machine_map, sections=["vga"]).get("vga") or {}
            modes[stop] = vga.get("mode") or {}
        if stop in ("text", "start80", "dac01"):
            sigs[stop] = M.call(server.screen_signature).get("signature")
        _screen_cells(stop)
    M.judge("J the screen guest stops at its own int 3, six times",
            landed == list(SCREEN_STOPS), f"landed on int 3 at {landed}")
    before, after = dacs.get("start80", []), dacs.get("dac01", [])
    changed = [i for i in range(min(len(before), len(after))) if before[i] != after[i]]
    M.judge("J the DAC write changes entry 1 to 3F 00 00 and no other",
            len(before) == len(after) == 256 and changed == [1] and after[1] == "3f0000",
            f"changed {changed}, entry 1 {before[1:2]} -> {after[1:2]}")
    M.judge("J in 13h the DAC is the guest's ramp, entry by entry", dacs.get("13h") == _ramp(),
            f"first entries {dacs.get('13h', [])[:4]}")
    M.judge("J screen_signature moves when the page shown moves, and holds through a DAC write "
            "no cell shows",
            all(isinstance(sigs.get(k), str) for k in ("text", "start80", "dac01"))
            and sigs["text"] != sigs["start80"] and sigs["dac01"] == sigs["text"], f"{sigs}")
    m13, m12 = modes.get("13h", {}), modes.get("12h", {})
    M.judge("J machine_map's vga names M_VGA chained in 13h and M_EGA in 12h",
            (m13.get("mode"), m13.get("chained"), m12.get("mode")) == ("M_VGA", "1", "M_EGA"),
            f"13h {m13.get('mode')} chained {m13.get('chained')}, 12h {m12.get('mode')}")
    r = M.call(server.close)
    judged("J the screen guest closes", reply=r, holds=ok(r) and r.get("closed") is True)


def _screen_cells(stop: str) -> None:
    """`screen_view` at one stop of the screen guest, judged against what the guest drew."""
    if stop == "text":
        r = M.call(server.screen_view)
        judged("J the text stop reads the guest's two lines, the cursor under them", reply=r,
               holds=ok(r) and (r.get("text") or [])[:3] == ["SCREEN GUEST: TEXT", "SECOND ROW",
                                                            ""] and r.get("cursor") == [0, 2])
    elif stop == "start80":
        r = M.call(server.screen_view)
        judged("J the start-address stop shows the page from its second row", reply=r,
               holds=ok(r) and (r.get("text") or [""])[0] == "SECOND ROW"
               and r.get("display_start") == "50h")
    elif stop in ("13h", "13h-start80"):
        dest = M.fresh(".png")
        r = M.call(server.screen_view, scale=1, dest=dest)
        got = _rgb24(dest) if ok(r) else b""
        shift = 0 if stop == "13h" else 1
        label = ("J the 13h picture's pixel (x, y) is (x + y) & FF through the guest's DAC"
                 if stop == "13h" else "J the 13h start-address stop shows the picture from its "
                 "next row")
        image = r.get("image") or {}
        judged(label, reply=r, holds=ok(r) and (image.get("width"), image.get("height"))
               == (320, 200) and got == _known_13h(shift))
        if stop == "13h":
            _against_the_capture(got)
    elif stop == "12h":
        _from_video_memory("J screen_view and screen_signature read the 12h stop from video "
                           "memory", "M_EGA")


def _against_the_capture(picture: bytes) -> None:
    """The last frame the capture wrote before this stop (the guest draws nothing after its
    retraces), against the server's picture doubled each way as the emulator renders 13h."""
    caps = videos()
    # THE NEWEST FILE, by its number: the recording restarts at every mode change and the reply
    # orders by size, so the largest is not always the one being written.
    last: dict[str, Any] = max(caps, key=lambda c: str(c.get("path")), default={})
    frames = int(last.get("avi_frames") or 0)
    dest = M.fresh(".png")
    r = M.call(server.capture_frame, frame=max(frames - 1, 0), dest=dest,
               capture_path=str(last.get("path") or ""))
    frame = _rgb24(dest) if ok(r) else b""
    want = _doubled(picture, 320, 200)
    differing = sum(1 for i in range(0, min(len(frame), len(want)), 3)
                    if frame[i:i + 3] != want[i:i + 3])
    M.judge("J the 13h picture equals the emulator's own capture of that frame, pixel for pixel",
            bool(picture) and len(frame) == len(want) and differing == 0,
            f"frame {frames - 1} of {last.get('path')}: {differing} pixels differ")


# ------------------------------------------------------------------ the programs


def program_cells(letter: str, word: str) -> list[tuple[str, str]]:
    """The screen cells a program section declares, for a program drawing in `word`."""
    return [(f"{letter} machine_map's vga says {word}", "machine_map docstring: `vga`; measured"),
            (f"{letter} palette answers the 256 entries of the DAC", "palette docstring"),
            (f"{letter} screen_view and screen_signature read {word} from video memory",
             "REFERENCE.md, Input and the screen: the screen is read from video memory")]


def judge_program(letter: str, word: str) -> None:
    """The machine stopped inside the section's program, drawing in `word`."""
    r = M.call(server.machine_map, sections=["vga"])
    mode = ((r.get("vga") or {}).get("mode") or {}).get("mode")
    judged(f"{letter} machine_map's vga says {word}", reply=r, holds=ok(r) and mode == word)
    r = M.call(server.palette)
    judged(f"{letter} palette answers the 256 entries of the DAC", reply=r,
           holds=ok(r) and r.get("entries") == 256 and len(r.get("colors") or []) == 256)
    _from_video_memory(f"{letter} screen_view and screen_signature read {word} from video memory",
                       word)


def _from_video_memory(label: str, word: str) -> None:
    view = M.call(server.screen_view, dest=M.fresh(".png"), attach=False)
    sig = M.call(server.screen_signature)
    M.judge(label, ok(view) and view.get("vga_mode") == word and ok(sig)
            and sig.get("kind") == "pixel", f"{said(view)}; {said(sig)}")
