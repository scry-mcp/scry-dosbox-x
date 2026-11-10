"""Section R of the live matrix: the presence edge is drawn into the window, never into the
evidence, on the screen guest (`tests/guest/screen.asm`). Why: REFERENCE.md, The presence
indicator. The red for the capture cells is a scratch build (`DOSBOX_X_LEAK_BINARY`): the
binary under test built with `presence-leak.patch` applied, which paints the first row of the
source the capture reads while the overlay is on. `DOSBOX_X_STOCK_BINARY` names a release build,
whose debugger has no PRESENCE command (section S reads the same variable). The screen readers
have no red, since they read guest memory.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from matrix_common import (
    ENV,
    GUEST,
    MOUSE_CONF,
    STOPPED,
    M,
    advanced,
    boot,
    cells,
    close_whatever,
    must,
    ok,
    said,
    server,
    videos,
)
from scry_core import avi, presence, window_capture

from scry_dosbox_x import presence as dpresence  # isort: skip -- found through the path the matrix sets
from scry_dosbox_x.state import STATE  # isort: skip

LEAK_VAR = "DOSBOX_X_LEAK_BINARY"
STOCK_VAR = "DOSBOX_X_STOCK_BINARY"
SCREEN_CONF = GUEST / "screen.conf"
SCREEN_PROGRAM = "SCREEN.COM"
TO_13H, TO_LAST = 4, 2
#: Long enough for the writer to land a pending state and a stopped machine to repaint.
QUIET_S = 0.5
STRETCH_S = 2.0
#: The most of the window the pointer alone may span.
POINTER_SPAN = 0.25
#: Bounds the captures a settled frame may take, so an unsettled window blocks the cell.
SETTLE_CAPTURES = 6
SETTLE_GAP_S = 0.5
E9_OPEN = ["-set", "dosbox bochs debug port e9=true"]

R_CELLS = cells(
    ("R a shared start says presence true, and status the same",
     "REFERENCE.md, The presence indicator"),
    ("R the emulator counts frames drawn lit while the guest runs and when a stopped machine "
     "is repainted", "the PRESENCE channel command's answer: frames"),
    ("R the host's capture with the edge acting differs from it off on all four sides of the "
     "picture and nowhere deeper than the edge, towards orange",
     "REFERENCE.md, The presence indicator: on the inner sides of the picture"),
    ("R screen_view and screen_signature at the stop are byte-identical acting and off",
     "REFERENCE.md, The presence indicator: never into the evidence"),
    ("R snapshot, capture_frame and series_capture of a still screen are byte-identical acting "
     "and off", "REFERENCE.md, The presence indicator: never into the evidence"),
    ("R a build that paints where capture reads changes snapshot, capture_frame and "
     "series_capture: the comparison can fail",
     "REFERENCE.md, The presence indicator: after the frame was handed to capture"),
    ("R a build whose debugger has no PRESENCE answers presence unavailable, naming it",
     "presence: NO_COMMAND"),
    ("R a session with no window says it has none, and one asked off says false",
     "presence: NO_WINDOW"),
    ("R the first mouse move draws the pointer inside the picture, away from the edge, and only "
     "the pointer: with it turned off the same screen differs by those pixels alone",
     "REFERENCE.md, The presence indicator: an orange pointer stands on it"),
    ("R in the graphics modes the pointer is the sprite's height in guest pixels: the same "
     "number of rows at 320x200 and at 640x480",
     "REFERENCE.md, The presence indicator: sized by the guest's pixels"),
)
#: The mouse guest's mode keys and the rows each mode shows (`tests/guest/mouse.asm`).
GRAPHICS_MODES = (("g", 200), ("v", 480))
#: How far, as a share of the sprite's rows, the pointer's measured rows may be off: the window's
#: scaling smears an edge.
ROWS_TOLERANCE = 0.3


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


@contextmanager
def _by_hand() -> Iterator[dpresence.ChannelAdapter]:
    """The session's writer stopped, so nothing it retries lands over states sent by hand."""
    session = STATE.session
    assert session is not None
    session.presence.close()
    session.presence = presence.Shown()
    time.sleep(QUIET_S)
    try:
        yield dpresence.ChannelAdapter(session)
    finally:
        session.presence = dpresence.open_shown(session, asked=True, shared=True)


def _put(adapter: dpresence.ChannelAdapter, state: str) -> int | None:
    """`state` sent by hand (`off` too, which the session never sends); the frame count after."""
    if state == "off":
        ok_, lines = _debugger().exec("PRESENCE off")
        adapter.answer = lines[0] if ok_ and lines else ""
    else:
        adapter.show(state)  # type: ignore[arg-type]
    time.sleep(QUIET_S)
    return _frame_count(adapter)


def _frame_count(adapter: dpresence.ChannelAdapter) -> int | None:
    """The emulator's frame count now, without changing what is drawn."""
    state = adapter.answer.split()[1] if len(adapter.answer.split()) > 1 else "off"
    ok_, lines = _debugger().exec(f"PRESENCE {state}")
    return dpresence.frames(lines[0]) if ok_ and lines else None


def _debugger() -> Any:
    assert STATE.session is not None
    return STATE.session


def _window(tag: str) -> window_capture.Image | str:
    session = STATE.session
    assert session is not None
    try:
        return window_capture.capture(session.proc.pid, Path(M.fresh(f"-{tag}.png")))
    except window_capture.Blocked as e:
        return str(e)


def _stills() -> dict[str, str]:
    view = Path(M.fresh(".png"))
    shown = M.call(server.screen_view, dest=str(view), attach=False)
    sig = M.call(server.screen_signature)
    return {"screen_view": _digest(view) if ok(shown) else "",
            "screen_signature": str(sig.get("signature", "")) if ok(sig) else ""}


def _latest_capture() -> str:
    listed = videos()
    paths = [Path(str(c.get("path"))) for c in listed if isinstance(c, dict)]
    paths = [p for p in paths if p.is_file()]
    return str(max(paths, key=lambda p: p.stat().st_mtime)) if paths else ""


def _frame_of(capture: str, frame: int) -> str:
    dest = Path(M.fresh(".png"))
    r = M.call(server.capture_frame, frame=frame, dest=str(dest), capture_path=capture)
    return _digest(dest) if ok(r) else ""


def _series_of(capture: str, frames: list[int]) -> list[str]:
    dest = Path(M.fresh("-series"))
    r = M.call(server.series_capture, at_frames=frames, dest=str(dest), capture_path=capture)
    return [_digest(p) for p in sorted(dest.glob("*.png"))] if ok(r) and dest.is_dir() else []


def _recorded() -> int:
    capture = _latest_capture()
    return avi.count(Path(capture).read_bytes()) if capture else 0


def _spin_record(adapter: dpresence.ChannelAdapter) -> dict[str, Any]:
    """The guest released into its still spin, recorded with the edge off, then acting."""
    must(M.call(server.resume), "releasing the screen guest into its spin")
    out: dict[str, Any] = {}
    _put(adapter, "off")
    off_from = _recorded()
    time.sleep(STRETCH_S)
    off_to = _recorded()
    off_shot = Path(M.fresh(".png"))
    off_snap = M.call(server.snapshot, dest=str(off_shot))
    _put(adapter, "acting")
    on_from = _recorded()
    time.sleep(STRETCH_S)
    on_to = _recorded()
    on_shot = Path(M.fresh(".png"))
    on_snap = M.call(server.snapshot, dest=str(on_shot))
    # A still screen is redrawn only when the overlay moves, so count across a fade.
    lit = _frame_count(adapter)
    _put(adapter, "held")
    time.sleep(presence.LOOK.fade_s)
    after = _frame_count(adapter)
    must(M.call(server.stop), "stopping the spin")
    out["snapshot"] = (_digest(off_shot) if ok(off_snap) else "",
                       _digest(on_shot) if ok(on_snap) else "")
    capture = _latest_capture()
    listed = videos()
    total = max((int(c.get("avi_frames") or 0) for c in listed
                 if isinstance(c, dict) and str(c.get("path")) == capture), default=0)
    off_at, on_at = (off_from + off_to) // 2, (on_from + on_to) // 2
    out["capture_frame"] = (_frame_of(capture, off_at), _frame_of(capture, on_at))
    out["series_capture"] = tuple(_series_of(capture, [off_at, on_at]))
    out["frames_drawn_running"] = None if after is None or lit is None else after - lit
    out["capture"] = capture
    out["avi_frames"] = total
    return out


def _start(**kw: Any) -> dict[str, Any]:
    # The screen guest's conf leaves port e9 shut; `snapshot` needs the stub's announcement.
    return boot(conf=SCREEN_CONF, program=SCREEN_PROGRAM, break_on_int3=True, shared=True,
                background=True, capture_video=True,
                captures_dir=M.fresh("-cap"), flags=E9_OPEN, **kw)


def _pair_agrees(pair: Any) -> bool:
    return isinstance(pair, tuple | list) and len(pair) == 2 and all(pair) and pair[0] == pair[1]


@M.section("R", "the presence edge, drawn into the window and never into the evidence",
           R_CELLS, alone=True)
def section_r() -> None:
    started = _start(presence=True)
    status = M.call(server.status)
    M.judge(R_CELLS[0].label, started.get("presence") is True and status.get("presence") is True,
            f"start {started.get('presence')!r}, status {status.get('presence')!r}")
    for _ in range(TO_13H):
        advanced(M.call(server.resume, seconds=30), "walking to the mode 13h stop", STOPPED)
    with _by_hand() as adapter:
        dark = _put(adapter, "off")
        off_stills, off_window = _stills(), _window("off")
        lit = _put(adapter, "acting")
        on_stills, on_window = _stills(), _window("acting")
        for _ in range(TO_LAST):
            advanced(M.call(server.resume, seconds=30), "walking to the last stop", STOPPED)
        spin = _spin_record(adapter)
    repainted = None if dark is None or lit is None else lit - dark
    M.judge(R_CELLS[1].label, (repainted or 0) >= 1 and (spin["frames_drawn_running"] or 0) >= 10,
            f"stopped and repainted lit: {repainted}; while running, across a fade from acting: "
            f"{spin['frames_drawn_running']}")
    if isinstance(off_window, str) or isinstance(on_window, str):
        M.block(R_CELLS[2].label, off_window if isinstance(off_window, str) else str(on_window))
    else:
        _judge_window(R_CELLS[2].label, off_window, on_window)
    M.judge(R_CELLS[3].label, all(off_stills.values()) and off_stills == on_stills,
            f"off {off_stills}, acting {on_stills}")
    M.judge(R_CELLS[4].label, all(_pair_agrees(spin[k]) for k in
                                  ("snapshot", "capture_frame", "series_capture")),
            f"{ {k: spin[k] for k in ('snapshot', 'capture_frame', 'series_capture')} } "
            f"from {spin['avi_frames']} frames of {spin['capture']}")
    close_whatever()

    leak = ENV.get(LEAK_VAR, "").strip()
    if not leak:
        M.block(R_CELLS[5].label, f"{LEAK_VAR} is not set: no build paints where capture reads")
    else:
        _start(presence=True, binary=leak)
        for _ in range(TO_13H + TO_LAST):
            advanced(M.call(server.resume, seconds=30),
                     "walking the leaking build to the last stop", STOPPED)
        with _by_hand() as adapter:
            spun = _spin_record(adapter)
        M.judge(R_CELLS[5].label, all(spun[k][0] and spun[k][1] and spun[k][0] != spun[k][1]
                                      for k in ("snapshot", "capture_frame", "series_capture")),
                f"{ {k: spun[k] for k in ('snapshot', 'capture_frame', 'series_capture')} }")
        close_whatever()

    stock = ENV.get(STOCK_VAR, "").strip()
    if not stock:
        M.block(R_CELLS[6].label, f"{STOCK_VAR} is not set: no build without the command")
    else:
        r = _start(presence=True, binary=stock)
        why = r.get("presence")
        M.judge(R_CELLS[6].label, isinstance(why, dict) and why.get("why") == dpresence.NO_COMMAND,
                f"presence {why!r}: {said(r)}")
        close_whatever()

    headless = boot(conf=SCREEN_CONF, program=SCREEN_PROGRAM, presence=True)
    shown_headless = headless.get("presence")
    close_whatever()
    asked_off = _start(presence=False)
    M.judge(R_CELLS[7].label, shown_headless == {"available": False, "why": dpresence.NO_WINDOW}
            and asked_off.get("presence") is False,
            f"headless {shown_headless!r}, asked off {asked_off.get('presence')!r}")
    close_whatever()
    _pointer(R_CELLS[8].label)
    _pointer_rows(R_CELLS[9].label)


def _pointer_difference(mode_key: str | None, x: int, y: int
                      ) -> tuple[dict[str, Any], str, window_capture.Difference | str]:
    """Captures after a mouse move and again with the pointer off: what differs is the pointer, or
    the reason it cannot be judged. `mode_key` first switches the mouse guest's BIOS mode."""
    boot(profile="mouse", conf=MOUSE_CONF, shared=True, background=True, presence=True)
    must(M.call(server.resume), "releasing the mouse guest")
    time.sleep(QUIET_S)
    if mode_key is not None:
        must(M.call(server.send_keys, keys=[mode_key], expect=r"MOUSE \. mode=", seconds=10),
             f"switching the mouse guest's mode with {mode_key!r}")
        time.sleep(QUIET_S)
    moved = M.call(server.send_mouse, x=x, y=y, units="screen")
    # Edge back to held first, so the two captures differ by the pointer alone.
    time.sleep(presence.LOOK.fade_s + QUIET_S)
    after = _settled("after-mouse")
    shown = dpresence.of(STATE.session)
    adapter = shown.adapter if isinstance(shown.adapter, dpresence.ChannelAdapter) else None
    answer = adapter.answer if adapter is not None else ""
    # The control: the same screen with the pointer off.
    if adapter is not None and shown.held is not None:
        adapter.pointer = False
        shown.held.redeliver()
    time.sleep(QUIET_S)
    hidden = _settled("pointer-off")
    if isinstance(hidden, str) or isinstance(after, str):
        return moved, answer, hidden if isinstance(hidden, str) else str(after)
    try:
        return moved, answer, window_capture.difference(hidden, after)
    except ValueError as e:
        return moved, answer, f"the window changed between its two captures: {e}"


def _pointer(label: str) -> None:
    moved, answer, d = _pointer_difference(None, 40, 12)      # a text cell
    if isinstance(d, str):
        M.block(label, d)
    else:
        M.judge(label, ok(moved) and "pointer=1" in answer and d.changed > 0
                and max(d.span) < POINTER_SPAN
                and d.deepest > window_capture.EDGE_REACH * presence.LOOK.edge,
                f"{said(moved)}; emulator {answer!r}; {d.changed} pixels changed over "
                f"{d.span[0]:.2f} x {d.span[1]:.2f} of the window, the deepest "
                f"{d.deepest:.3f} of the box's shorter side in")
    close_whatever()


def _pointer_rows(label: str) -> None:
    """The pointer's height in guest rows, measured in two graphics modes: a share of the window
    would give a number of rows that follows the mode, the sprite's own does not."""
    sprite_rows = len(dpresence.POINTER)
    measured: dict[str, float] = {}
    for key, guest_rows in GRAPHICS_MODES:
        close_whatever()
        _moved, _answer, d = _pointer_difference(key, 40, guest_rows // 2)
        if isinstance(d, str):
            M.block(label, d)
            close_whatever()
            return
        measured[f"{guest_rows} rows"] = round(d.span[1] * guest_rows, 1)
    M.judge(label, all(abs(rows - sprite_rows) <= ROWS_TOLERANCE * sprite_rows
                       for rows in measured.values()),
            f"guest rows the pointer spans, the sprite being {sprite_rows}: {measured}")
    close_whatever()


def _settled(tag: str) -> window_capture.Image | str:
    """The window once two captures in a row are alike, else the reason it cannot be judged."""
    last = _window(f"{tag}-1")
    for n in range(2, SETTLE_CAPTURES + 1):
        if isinstance(last, str):
            return last
        time.sleep(SETTLE_GAP_S)
        now = _window(f"{tag}-{n}")
        if isinstance(now, str) or now == last:
            return now
        last = now
    return (f"the window did not hold still over {SETTLE_CAPTURES} captures {SETTLE_GAP_S} s "
            "apart")


def _judge_window(label: str, off: window_capture.Image, on: window_capture.Image) -> None:
    try:
        d = window_capture.difference(off, on)
    except ValueError as e:
        M.block(label, f"the window changed between its two captures: {e}")
        return
    M.judge(label, *window_capture.edge_verdict(d))
