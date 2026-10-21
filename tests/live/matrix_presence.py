"""Section R of the live matrix: the presence edge, drawn by DOSBox-X into the window and never
into the evidence, on the screen guest (`tests/guest/screen.asm`), whose screen holds still at
its mode 13h stop and in the spin after its last one. Why it cannot reach the evidence is in
REFERENCE.md, The presence indicator; this section proves each claim with a control that can go
red.

DRAWN: the emulator's own count of frames drawn with the overlay, in its answer to `PRESENCE`,
rises while the guest runs lit and when a stopped machine is repainted. SEEN: the host's capture
of the window with the edge `acting` against the same stopped machine with it `off` differs on
all four sides and nowhere deeper than the edge, towards orange; a host that does not grant the
capture BLOCKS that cell.

NEVER IN THE EVIDENCE: `screen_view` and `screen_signature` at the stop, and `snapshot`,
`capture_frame` and `series_capture` of the still spin, with the edge `off` and `acting`; the
state is set by hand over the channel, the session's own writer stopped. The red: a scratch build
that paints the same rim where capture reads (`DOSBOX_X_LEAK_BINARY`) must change `snapshot` and
`capture_frame`. The screen readers have no red of their own: they read the guest's memory,
which no host-side drawing reaches, so their cell confirms where they read. A stock build answers
presence unavailable naming the command it lacks (`DOSBOX_X_STOCK_BINARY`), and a session with no
window says it has none.
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
    M,
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

import dosbox_presence as dpresence  # isort: skip -- found through the path the matrix sets
from dosbox_state import STATE  # isort: skip

FLAGS_VAR = "DOSBOX_X_LIVE_WINDOW_FLAGS"
LEAK_VAR = "DOSBOX_X_LEAK_BINARY"
STOCK_VAR = "DOSBOX_X_STOCK_BINARY"
SCREEN_CONF = GUEST / "screen.conf"
SCREEN_PROGRAM = "SCREEN.COM"
#: The screen guest's stops up to its mode 13h picture, and the rest up to its last one.
TO_13H, TO_LAST = 4, 2
#: Long enough for the session's writer to land a state it had pending, and for a stopped
#: machine's loop to repaint a state it was sent.
QUIET_S = 0.5
#: How long each stretch of the spin is recorded with the edge in one state.
STRETCH_S = 2.0
#: The most of the window the arrow alone may span: a sprite, nothing like the edge's frame.
ARROW_SPAN = 0.25
#: A bound on the captures a settled frame may take, so a window that never holds still blocks
#: the cell instead of stalling it; two in a row alike end it sooner, `SETTLE_GAP_S` apart.
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
    ("R a build that paints the rim where capture reads changes snapshot and capture_frame: "
     "the comparison can fail", "REFERENCE.md, The presence indicator: after the frame was "
     "handed to capture"),
    ("R a build whose channel has no PRESENCE answers presence unavailable, naming it",
     "dosbox_presence: NO_COMMAND"),
    ("R a session with no window says it has none, and one asked off says false",
     "dosbox_presence: NO_WINDOW"),
    ("R the first mouse move draws the arrow inside the picture, away from the edge, and only "
     "the arrow: turned off again, those pixels go back",
     "REFERENCE.md, The presence indicator: an orange arrow marks the guest's pointer"),
)
MOUSE_CONF = GUEST / "mouse.conf"
MOUSE_PROGRAM = "MOUSE.COM"


def _flags() -> list[str]:
    return [ln for ln in ENV.get(FLAGS_VAR, "").splitlines() if ln.strip()]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


@contextmanager
def _by_hand() -> Iterator[dpresence.ChannelAdapter]:
    """The session's writer stopped, so nothing it retries lands over the block, which sends
    states itself through an adapter of its own; a fresh one is opened after."""
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
    """`state` sent by hand (`off` included, which the session itself never sends), and the
    emulator's frame count once a stopped machine has had time to repaint it."""
    if state == "off":
        ok_, lines = _channel().request("PRESENCE off")
        adapter.answer = lines[0] if ok_ and lines else ""
    else:
        adapter.show(state)  # type: ignore[arg-type]
    time.sleep(QUIET_S)
    return _count(adapter)


def _count(adapter: dpresence.ChannelAdapter) -> int | None:
    """The emulator's frame count now, asked without changing what is drawn."""
    state = adapter.answer.split()[1] if len(adapter.answer.split()) > 1 else "off"
    ok_, lines = _channel().request(f"PRESENCE {state}")
    return dpresence.frames(lines[0]) if ok_ and lines else None


def _channel() -> Any:
    assert STATE.session is not None
    return STATE.session.control


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
    r = M.call(server.series_capture, frames=frames, dest=str(dest), capture_path=capture)
    return [_digest(p) for p in sorted(dest.glob("*.png"))] if ok(r) and dest.is_dir() else []


def _recorded() -> int:
    """The frames the capture being written holds so far."""
    capture = _latest_capture()
    return avi.count(Path(capture).read_bytes()) if capture else 0


def _spin_record(adapter: dpresence.ChannelAdapter) -> dict[str, Any]:
    """The guest released into its still spin, recorded with the edge off, then acting: the
    snapshot of each stretch and frames from each, read back once it is stopped again."""
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
    # A FADE WHILE IT RUNS: a still screen is not drawn again until the overlay itself moves, so
    # the count is read across one, from acting back to held.
    lit = _count(adapter)
    _put(adapter, "held")
    time.sleep(presence.LOOK.fade_s)
    after = _count(adapter)
    must(M.call(server.stop), "stopping the spin")
    out["snapshot"] = (_digest(off_shot) if ok(off_snap) else "",
                       _digest(on_shot) if ok(on_snap) else "")
    capture = _latest_capture()
    listed = videos()
    total = max((int(c.get("avi_frames") or 0) for c in listed
                 if isinstance(c, dict) and str(c.get("path")) == capture), default=0)
    # A frame from the middle of each stretch, by the frames recorded at its two ends.
    off_at, on_at = (off_from + off_to) // 2, (on_from + on_to) // 2
    out["capture_frame"] = (_frame_of(capture, off_at), _frame_of(capture, on_at))
    out["series_capture"] = tuple(_series_of(capture, [off_at, on_at]))
    out["frames_drawn_running"] = None if after is None or lit is None else after - lit
    out["capture"] = capture
    out["avi_frames"] = total
    return out


def _start(**kw: Any) -> dict[str, Any]:
    # E9 OPEN, which the screen guest's conf leaves shut: `snapshot` needs the input stub's
    # announcement there.
    return boot(conf=SCREEN_CONF, program=SCREEN_PROGRAM, break_on_int3=True, shared=True,
                window_flags=_flags(), background=True, capture_video=True,
                captures_dir=M.fresh("-cap"), flags=E9_OPEN, **kw)


def _same(pair: Any) -> bool:
    return isinstance(pair, tuple | list) and len(pair) == 2 and all(pair) and pair[0] == pair[1]


@M.section("R", "the presence edge, drawn into the window and never into the evidence",
           R_CELLS, FLAGS_VAR, alone=True)
def section_r() -> None:
    started = _start(presence=True)
    status = M.call(server.status)
    M.judge(R_CELLS[0].label, started.get("presence") is True and status.get("presence") is True,
            f"start {started.get('presence')!r}, status {status.get('presence')!r}")
    for _ in range(TO_13H):
        must(M.call(server.resume, seconds=30), "walking to the mode 13h stop")
    with _by_hand() as adapter:
        dark = _put(adapter, "off")
        off_stills, off_window = _stills(), _window("off")
        lit = _put(adapter, "acting")
        on_stills, on_window = _stills(), _window("acting")
        for _ in range(TO_LAST):
            must(M.call(server.resume, seconds=30), "walking to the last stop")
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
    M.judge(R_CELLS[4].label, all(_same(spin[k]) for k in
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
            must(M.call(server.resume, seconds=30), "walking the leaking build to the last stop")
        with _by_hand() as adapter:
            spun = _spin_record(adapter)
        M.judge(R_CELLS[5].label, all(spun[k][0] and spun[k][1] and spun[k][0] != spun[k][1]
                                      for k in ("snapshot", "capture_frame")),
                f"{ {k: spun[k] for k in ('snapshot', 'capture_frame')} }")
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
    _arrow(R_CELLS[8].label)


def _arrow(label: str) -> None:
    """The mouse guest running in a window, captured after a mouse move and again with the arrow
    turned off: the difference is the arrow, inside the picture where the edge never reaches."""
    boot(conf=MOUSE_CONF, program=MOUSE_PROGRAM, shared=True, window_flags=_flags(),
         background=True, presence=True)
    must(M.call(server.resume), "releasing the mouse guest")
    time.sleep(QUIET_S)
    moved = M.call(server.send_mouse, x=40, y=12, units="screen")    # a text cell
    # The edge back to held before either capture, so the two differ by the arrow alone.
    time.sleep(presence.LOOK.fade_s + QUIET_S)
    after = _settled("after-mouse")
    shown = dpresence.of(STATE.session)
    adapter = shown.adapter if isinstance(shown.adapter, dpresence.ChannelAdapter) else None
    answer = adapter.answer if adapter is not None else ""
    # THE CONTROL: the same screen with the arrow turned off. Whatever the guest drew of its own
    # for the move is in both captures, so what differs is the arrow alone.
    if adapter is not None and shown.held is not None:
        adapter.pointer = False
        shown.held.redeliver()
    time.sleep(QUIET_S)
    hidden = _settled("arrow-off")
    if isinstance(hidden, str) or isinstance(after, str):
        M.block(label, hidden if isinstance(hidden, str) else str(after))
    else:
        try:
            d = window_capture.difference(hidden, after)
        except ValueError as e:
            M.block(label, f"the window changed between its two captures: {e}")
        else:
            M.judge(label, ok(moved) and "pointer=1" in answer and d.changed > 0
                    and max(d.span) < ARROW_SPAN
                    and d.deepest > window_capture.EDGE_REACH * presence.LOOK.edge,
                    f"{said(moved)}; emulator {answer!r}; {d.changed} pixels changed over "
                    f"{d.span[0]:.2f} x {d.span[1]:.2f} of the window, the deepest "
                    f"{d.deepest:.3f} of the box's shorter side in")
    close_whatever()


def _settled(tag: str) -> window_capture.Image | str:
    """The window once two captures in a row are alike, within `SETTLE_CAPTURES`: a frame half
    drawn under load is not judged, and a window that never holds still says so as the block's
    reason rather than as a FAIL of what it shows; a capture the host refuses is its reason."""
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
