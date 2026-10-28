"""Section G of the live matrix: the tools on a WINDOWED session (stop, the saved states, the
screenshot, the video capture), on the probe guest and on the DPMI guest, and the mouse at two
window sizes, which must change nothing the guest reads. It opens windows where the placement
flags say, launched BEHIND (`background=True`): nothing here clicks a menu or takes the focus,
and section O judges this stretch like any other."""
from __future__ import annotations

from pathlib import Path

import dpmi_guest as guest
from matrix_common import (
    GUEST,
    NEVER_RUNS_STOPPER,
    PROBE_CONF,
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
)
from matrix_dpmi import dpmi_boot, dpmi_leave

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DPMI_CELLS = ("G the DPMI guest: snapshot", "G the DPMI guest: a click reaches the program",
              "G the DPMI guest: stop inside the running program",
              "G the DPMI guest: quit by keys and close")

G_CELLS = cells(
    ("G stop brings a running guest back", "stop docstring: BREAK, `interrupted: true`"),
    ("G declared while running applies at stop", "REFERENCE.md, Advancing: applied_on_stop"),
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
    ("G in a window, cell 40,12 arrives at the driver's 320,96",
     "send_mouse docstring: inside the guest, so a window changes nothing"),
    ("G at a 1280x800 window the same cell arrives at the same driver coordinates",
     "REFERENCE.md, Input and the screen: the window's scale changes nothing the guest sees"),
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
    r = M.call(server.state_write, method="save", name="matrix_g", seconds=30)
    judged("G state_write save while running", reply=r,
           holds=ok(r) and Path(str(r.get("path"))).is_file() and int(r.get("bytes") or 0) > 0)
    r = M.call(server.state_list)
    judged("G state_list lists it", reply=r, holds=ok(r) and any(
        "matrix_g" in str(s.get("name", s)) for s in r.get("states") or []))
    r = M.call(server.state_write, method="load", name="matrix_g", seconds=30)
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
           holds=_landed(r))
    close_whatever()


def _landed(r: dict[str, object]) -> bool:
    pointer = r.get("pointer")
    mouse = pointer.get("mouse") if isinstance(pointer, dict) else None
    return (ok(r) and r.get("arrived") is True and isinstance(mouse, dict)
            and (mouse.get("x"), mouse.get("y")) == (320, 96))


def _scaled() -> None:
    """The probe guest again, its window drawn at twice the size: the pointer is set inside the
    guest, so the same cell lands on the same driver coordinates."""
    conf = conf_without_launch(PROBE_CONF, "PROBE.COM")
    flags = ["-set", "sdl output=opengl", "-set", "sdl windowresolution=1280x800"]
    boot(conf=conf, cwd=GUEST, shared=True, flags=flags, background=True,
         program="PROBE.COM")
    must(M.call(server.resume), "releasing the probe")
    must(M.call(server.log_wait, pattern="PROBE", channel="guest", seconds=30),
         "the probe's first line")
    r = M.call(server.send_mouse, x=40, y=12)
    judged("G at a 1280x800 window the same cell arrives at the same driver coordinates",
           reply=r, holds=_landed(r))
    close_whatever()


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
    print("  windows open behind, where the host's own arguments put them", flush=True)
    try:
        _probe()
        _scaled()
        _dpmi()
    finally:
        close_whatever()
    print(f"  kept for the QA: {' '.join(KEEP)}", flush=True)
