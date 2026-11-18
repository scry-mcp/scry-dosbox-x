"""Section G of the live matrix: the tools on a WINDOWED session (stop, the saved states, the
screenshot, the video capture), on the probe guest and on the DPMI guest, and the mouse at two
window sizes, which must change nothing the guest reads. It opens windows on the main display
(two cells on display 1), launched BEHIND (`background=True`): nothing here clicks a menu or
takes the focus, and section O judges this stretch like any other."""
from __future__ import annotations

import sys
from pathlib import Path

import dpmi_guest as guest
from matrix_common import (
    GUEST,
    NEVER_RUNS_STOPPER,
    PROBE_CONF,
    SESSION_S,
    M,
    boot,
    cells,
    close_whatever,
    conf_without_launch,
    judged,
    must,
    ok,
    refused,
    release_running,
    server,
    start_call,
)
from matrix_dpmi import dpmi_boot, dpmi_leave
from scry_core import window as core_window
from scry_core import window_size

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DPMI_CELLS = ("G the DPMI guest: snapshot", "G the DPMI guest: a click reaches the program",
              "G the DPMI guest: stop inside the running program",
              "G the DPMI guest: quit by keys and close")

G_CELLS = cells(
    ("G stop brings a running guest back", "stop docstring: BREAK, `interrupted: true`"),
    ("G declared while running applies at stop",
     "REFERENCE.md, Running and stopping: applied_on_stop"),
    ("G state_write save while running", "state_write save docstring"),
    ("G state_list lists it", "state_list docstring"),
    ("G state_write load while running", "state_write load docstring"),
    ("G stop after the load", "state_write load: docstring, a running guest is released again"),
    ("G snapshot while running", "snapshot docstring"),
    ("G captures lists the recording", "captures docstring"),
    ("G capture_frame writes a PNG", "capture_frame docstring"),
    ("G capture_frame refuses a % in dest", "capture_frame docstring"),
    ("G capture_frame refuses a dest that exists", "capture_frame docstring"),
    ("G capture_frame refuses a frame past the end", "capture_frame docstring"),
    ("G start proves a window on the asked display, onscreen",
     "start docstring: `window`, the display asked for"),
    ("G the host lists that window where `window` says",
     "window docstring: the OS's own window list"),
    ("G display 1 windowed: the window is listed inside display 1, onscreen",
     "start docstring: `display`"),
    ("G display 1 full screen is refused by name on macOS and fills display 1 elsewhere",
     "start docstring: `display` with `fullscreen`"),
    ("G a headless start opens no window and `window` refuses it",
     "window docstring: no_channel without `shared`"),
    ("G in a window, cell 40,12 arrives at the driver's 320,96",
     "send_mouse docstring: inside the guest, so a window changes nothing"),
    (DPMI_CELLS[0], "snapshot docstring; the image is kept for the QA"),
    (DPMI_CELLS[1], "send_mouse docstring; known: the program logs `mouse btn=`"),
    (DPMI_CELLS[2], "stop docstring"),
    (DPMI_CELLS[3], "known: alt+x asks before it quits, and right then enter answers quit"),
)

#: What the QA looks at, printed at the end of the section.
KEEP: list[str] = []


def _probe() -> None:
    conf = conf_without_launch(PROBE_CONF, "PROBE.COM")
    caps = Path(M.fresh("-captures"))
    caps.mkdir()
    boot(conf=conf, cwd=GUEST, shared=True, background=True,
         program="PROBE.COM",
         capture_video=True, captures_dir=str(caps))
    must(M.call(server.resume), "releasing the probe")
    must(M.call(server.log_wait, pattern="PROBE", channel="guest", seconds=30),
         "the probe's first line")
    M.setup()
    r = M.call(server.stop)
    judged("G stop brings a running guest back", reply=r,
           holds=ok(r) and r.get("interrupted") is True and r.get("via") == "break")
    must(M.call(server.resume), "releasing the probe")
    pend = M.call(server.breakpoint_at, ref="0000:0009")
    r = M.call(server.stop)
    armed = [str(a) for a in (r.get("applied_on_stop") or {}).get("armed") or []]
    judged("G declared while running applies at stop", reply=r,
           holds=ok(pend) and pend.get("state") == "pending" and "0000:0009" in armed)
    must(M.call(server.declaration_clear, kind="breakpoint", all=True), "clearing 0000:0009")
    must(M.call(server.resume), "releasing the probe")
    M.setup()
    r = M.call(server.state_write, method="save", name="matrix-g", seconds=30)
    judged("G state_write save while running", reply=r,
           holds=ok(r) and Path(str(r.get("path"))).is_file() and int(r.get("bytes") or 0) > 0)
    r = M.call(server.state_list)
    judged("G state_list lists it", reply=r, holds=ok(r) and any(
        "matrix-g" in str(s.get("name", s)) for s in r.get("states") or []))
    r = M.call(server.state_write, method="load", name="matrix-g", seconds=30)
    judged("G state_write load while running", reply=r, holds=ok(r))
    r = M.call(server.stop)
    judged("G stop after the load", reply=r, holds=ok(r) and r.get("interrupted") is True)
    must(M.call(server.resume), "releasing the probe")
    shot = M.fresh(".png")
    r = M.call(server.snapshot, dest=shot, seconds=30)
    judged("G snapshot while running", reply=r,
           holds=ok(r) and Path(shot).is_file() and Path(shot).read_bytes()[:8] == PNG_MAGIC)
    r = M.call(server.captures)
    listed = [c for c in r.get("captures") or [] if c.get("kind") == "avi"]
    judged("G captures lists the recording", reply=r,
           holds=ok(r) and bool(listed) and all(c.get("avi_frames") is not None for c in listed))
    frame = M.fresh(".png")
    r = M.call(server.capture_frame, frame=0, dest=frame)
    judged("G capture_frame writes a PNG", reply=r,
           holds=ok(r) and Path(frame).is_file() and Path(frame).read_bytes()[:8] == PNG_MAGIC)
    KEEP.append(frame)
    r = M.call(server.capture_frame, frame=0, dest=M.fresh("-%03d.png"))
    judged("G capture_frame refuses a % in dest", reply=r, holds=refused(r))
    r = M.call(server.capture_frame, frame=0, dest=frame)
    judged("G capture_frame refuses a dest that exists", reply=r, holds=refused(r))
    r = M.call(server.capture_frame, frame=10_000_000, dest=M.fresh(".png"))
    judged("G capture_frame refuses a frame past the end", reply=r, holds=refused(r))
    r = M.call(server.send_mouse, x=40, y=12)
    judged("G in a window, cell 40,12 arrives at the driver's 320,96", reply=r,
           holds=landed(r))
    close_whatever()


def _window() -> None:
    """The window `start` proves is the one the host lists, and a headless run has none."""
    host = core_window.host()
    r = boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, shared=True,
             display=0, background=True, program="PROBE.COM")
    block = r.get("window")
    judged("G start proves a window on the asked display, onscreen", reply=r,
           holds=isinstance(block, dict) and block.get("display") == 0
           and block.get("onscreen") is True)
    listed = [w for w in host.windows() if w.pid == r.get("pid")]
    said_by = M.call(server.window)
    main = core_window.main_window(r.get("pid", 0), listed)
    where = tuple((said_by.get("window") or {}).get("bounds", {}).values())
    judged("G the host lists that window where `window` says", reply=said_by,
           holds=ok(said_by) and main is not None and main.bounds == where)
    close_whatever()
    _on_display_one("G display 1 windowed: the window is listed inside display 1, onscreen", False)
    _on_display_one("G display 1 full screen is refused by name on macOS and fills display 1 "
                    "elsewhere", True)
    r = boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, background=True,
             program="PROBE.COM")
    refusal = M.call(server.window)
    judged("G a headless start opens no window and `window` refuses it", reply=refusal,
           holds=refused(refusal, "no_channel")
           and not [w for w in host.windows() if w.pid == r.get("pid")])
    close_whatever()


def _on_display_one(label: str, fullscreen: bool) -> None:
    """The window list, not the reply, says the window is on the second display: a host with one
    display cannot ask."""
    host = core_window.host()
    shown = host.displays()
    if len(shown) < 2:
        M.block(label, f"this host has {len(shown)} display(s): display 1 does not exist")
        return
    if fullscreen and sys.platform == window_size.DOSBOX_X_HALTED_MAIN_ONLY_ON:
        before = {w.number for w in host.windows()}
        r = start_call(conf=str(conf_without_launch(PROBE_CONF, "PROBE.COM")), cwd=str(GUEST),
                       shared=True, display=1, fullscreen=True, background=True,
                       session_seconds=SESSION_S, program="PROBE.COM")
        judged(label, reply=r, holds=refused(r, "bad_argument")
               and {w.number for w in host.windows()} <= before)
        return
    r = boot(conf=conf_without_launch(PROBE_CONF, "PROBE.COM"), cwd=GUEST, shared=True,
             display=1, fullscreen=fullscreen, background=True, program="PROBE.COM")
    main = core_window.main_window(r.get("pid", 0), host.windows())
    bounds = shown[1].bounds
    holds = (ok(r) and main is not None and main.onscreen
             and (main.bounds == bounds if fullscreen
                  else bounds[0] <= main.bounds[0] < bounds[0] + bounds[2]
                  and bounds[1] <= main.bounds[1] < bounds[1] + bounds[3]))
    judged(label, reply=r, holds=holds)
    close_whatever()


def landed(r: dict[str, object]) -> bool:
    pointer = r.get("pointer")
    mouse = pointer.get("mouse") if isinstance(pointer, dict) else None
    return (ok(r) and r.get("arrived", r.get("driver_arrived")) is True and isinstance(mouse, dict)
            and (mouse.get("x"), mouse.get("y")) == (320, 96))


def _dpmi() -> None:
    dpmi_boot(shared=True, background=True)
    release_running(NEVER_RUNS_STOPPER)
    must(M.call(server.log_wait, pattern=guest.SETTLED_MARK, channel="guest", seconds=30),
         "the guest's first TICK line")
    M.setup()
    shot = M.fresh("-dpmi.png")
    r = M.call(server.snapshot, dest=shot, seconds=30)
    judged(DPMI_CELLS[0], reply=r, holds=ok(r) and Path(shot).is_file())
    KEEP.append(shot)
    r = M.call(server.send_mouse, button="left", expect=guest.MOUSE_MARK, seconds=10)
    judged(DPMI_CELLS[1], reply=r, holds=ok(r) and (r.get("verify") or {}).get("seen") is True)
    r = M.call(server.stop)
    judged(DPMI_CELLS[2], reply=r, holds=ok(r) and r.get("interrupted") is True)
    must(M.call(server.resume), "releasing the DPMI guest")
    holds, detail, closed = dpmi_leave()
    M.judge(DPMI_CELLS[3], holds and ok(closed), f"{detail}; {closed.get('summary')}")


@M.section("G", "the windowed tools, on the probe guest and on the DPMI guest", G_CELLS,
           alone=True)
def section_g() -> None:
    print("  windows open behind, on the main display (two cells on display 1)", flush=True)
    try:
        _window()
        _probe()
        _dpmi()
    finally:
        close_whatever()
    print(f"  kept for the QA: {' '.join(KEEP)}", flush=True)
