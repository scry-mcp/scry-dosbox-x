"""Section G of the live matrix: the tools that need a window (the menu, the mouse, the saved
states, the screenshot) and the video capture, on the probe guest and on the DPMI guest. It opens
windows where the placement flags say, and the mouse takes the focus while it runs; the section
prints a line saying so before it starts."""
from __future__ import annotations

from pathlib import Path

import dpmi_guest as guest
from matrix_common import (
    ENV,
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

FLAGS_VAR = "DOSBOX_X_LIVE_WINDOW_FLAGS"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DPMI_CELLS = ("G the DPMI guest: snapshot", "G the DPMI guest: a click reaches the program",
              "G the DPMI guest: stop inside the running program",
              "G the DPMI guest: quit by keys and close")

G_CELLS = cells(
    ("G stop brings a running guest back", "stop docstring: the menu, `interrupted: true`"),
    ("G declared while running applies at stop", "REFERENCE.md, Advancing: applied_on_stop"),
    ("G state_save while running", "state_save docstring"),
    ("G state_list lists it", "state_list docstring"),
    ("G state_load while running", "state_load docstring"),
    ("G stop after the load", "state_load docstring: resume, state_load, stop"),
    ("G snapshot while running", "snapshot docstring"),
    ("G captures lists the recording", "captures docstring"),
    ("G capture_frame writes a PNG", "capture_frame docstring"),
    ("G capture_frame refuses a % in dest", "capture_frame docstring"),
    ("G capture_frame refuses a dest that exists", "capture_frame docstring"),
    ("G capture_frame refuses a frame past the end", "capture_frame docstring"),
    ("G send_mouse place=center", "send_mouse docstring: the window route"),
    ("G send_mouse dx=2000", "send_mouse docstring: the ceiling of one call's motion"),
    (DPMI_CELLS[0], "snapshot docstring; the image is kept for the QA"),
    (DPMI_CELLS[1], "send_mouse docstring; known: the program logs `mouse btn=`"),
    (DPMI_CELLS[2], "stop docstring"),
    (DPMI_CELLS[3], "known: alt+x asks before it quits, and right then enter answers quit"),
)

#: What the QA looks at, printed at the end of the section.
KEEP: list[str] = []


def _flags() -> list[str]:
    return [ln for ln in ENV.get(FLAGS_VAR, "").splitlines() if ln.strip()]


def _probe() -> None:
    conf = conf_without_launch(PROBE_CONF, "PROBE.COM")
    caps = Path(M.fresh("-captures"))
    caps.mkdir()
    boot(conf=conf, cwd=GUEST, mode="shared", window_flags=_flags(), program="PROBE.COM",
         capture_video=True, captures_dir=str(caps))
    must(M.call(server.resume), "releasing the probe")
    must(M.call(server.log_wait, pattern="PROBE", channel="guest", seconds=30),
         "the probe's first line")
    M.setup()
    r = M.call(server.stop)
    judged("G stop brings a running guest back", reply=r,
           holds=ok(r) and r.get("interrupted") is True and r.get("how") == "menu")
    must(M.call(server.resume), "releasing the probe")
    pend = M.call(server.breakpoint_at, ref="0000:0009")
    r = M.call(server.stop)
    armed = [str(a) for a in (r.get("applied_on_stop") or {}).get("armed") or []]
    judged("G declared while running applies at stop", reply=r,
           holds=ok(pend) and pend.get("state") == "pending" and "0000:0009" in armed)
    must(M.call(server.breakpoint_clear), "clearing 0000:0009")
    must(M.call(server.resume), "releasing the probe")
    M.setup()
    r = M.call(server.state_save, name="matrix_g", seconds=30)
    judged("G state_save while running", reply=r,
           holds=ok(r) and Path(str(r.get("path"))).is_file() and int(r.get("bytes") or 0) > 0)
    r = M.call(server.state_list)
    judged("G state_list lists it", reply=r, holds=ok(r) and any(
        "matrix_g" in str(s.get("name", s)) for s in r.get("states") or []))
    r = M.call(server.state_load, name="matrix_g", seconds=30)
    judged("G state_load while running", reply=r, holds=ok(r))
    r = M.call(server.stop)
    judged("G stop after the load", reply=r, holds=ok(r) and r.get("interrupted") is True)
    must(M.call(server.resume), "releasing the probe")
    shot = M.fresh(".png")
    r = M.call(server.snapshot, dest=shot, seconds=30)
    judged("G snapshot while running", reply=r, holds=ok(r) and Path(shot).is_file())
    r = M.call(server.captures)
    listed = r.get("captures") or []
    judged("G captures lists the recording", reply=r,
           holds=ok(r) and bool(listed) and all(c.get("frames") is not None for c in listed))
    frame = M.fresh(".png")
    r = M.call(server.capture_frame, at=0, dest=frame)
    judged("G capture_frame writes a PNG", reply=r,
           holds=ok(r) and Path(frame).is_file() and Path(frame).read_bytes()[:8] == PNG_MAGIC)
    KEEP.append(frame)
    r = M.call(server.capture_frame, at=0, dest=M.fresh("-%03d.png"))
    judged("G capture_frame refuses a % in dest", reply=r, holds=refused(r))
    r = M.call(server.capture_frame, at=0, dest=frame)
    judged("G capture_frame refuses a dest that exists", reply=r, holds=refused(r))
    r = M.call(server.capture_frame, at=10_000_000, dest=M.fresh(".png"))
    judged("G capture_frame refuses a frame past the end", reply=r, holds=refused(r))
    r = M.call(server.send_mouse, place="center")
    judged("G send_mouse place=center", reply=r, holds=ok(r) and r.get("route") == "window")
    r = M.call(server.send_mouse, dx=2000, dy=0)
    judged("G send_mouse dx=2000", reply=r, holds=ok(r))
    close_whatever()


def _dpmi() -> None:
    dpmi_boot(mode="shared", window_flags=_flags())
    release_running(NEVER_RUNS_STOPPER)
    must(M.call(server.log_wait, pattern=guest.SETTLED_MARK, channel="guest", seconds=30),
         "the guest's first TICK line")
    M.setup()
    shot = M.fresh("-dpmi.png")
    r = M.call(server.snapshot, dest=shot, seconds=30)
    judged(DPMI_CELLS[0], reply=r, holds=ok(r) and Path(shot).is_file())
    KEEP.append(shot)
    M.call(server.send_mouse, place="center")
    # With `autolock`, the first click inside the window captures the mouse and may itself be
    # swallowed (REFERENCE.md, Input and the screen); the judged click is the second.
    M.call(server.send_mouse, button="left")
    r = M.call(server.send_mouse, button="left", expect=guest.MOUSE_MARK, seconds=10)
    judged(DPMI_CELLS[1], reply=r, holds=ok(r) and (r.get("effect") or {}).get("seen") is True)
    r = M.call(server.stop)
    judged(DPMI_CELLS[2], reply=r, holds=ok(r) and r.get("interrupted") is True)
    must(M.call(server.resume), "releasing the DPMI guest")
    holds, detail, closed = dpmi_leave()
    M.judge(DPMI_CELLS[3], holds and ok(closed), f"{detail}; {closed.get('summary')}")


@M.section("G", "the windowed tools, on the probe guest and on the DPMI guest", G_CELLS,
           FLAGS_VAR)
def section_g() -> None:
    print("  a window opens on the display the placement flags name, and send_mouse takes "
          "the focus while it runs", flush=True)
    _probe()
    _dpmi()
    print(f"  kept for the QA: {' '.join(KEEP)}", flush=True)
