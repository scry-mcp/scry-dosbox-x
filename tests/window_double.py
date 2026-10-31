"""A window host whose emulator opens its window where its argv says."""

from __future__ import annotations

from scry_core.window import Display, Seen, WindowRequest

from scry_dosbox_x.state import STATE


def window_if(watched: bool) -> WindowRequest | None:
    """The window request of a launch the test calls watched."""
    return WindowRequest(0, False) if watched else None


DISPLAYS = [Display(0, (0, 0, 1920, 1080)), Display(1, (1920, 0, 1920, 1080))]


class ObeyingHost:
    def displays(self) -> list[Display]:
        return list(DISPLAYS)

    def windows(self) -> list[Seen]:
        session = STATE.session
        asked = None if session is None else session.launch.window
        if session is None or asked is None:
            return []
        x, y, width, height = DISPLAYS[asked.display].bounds
        bounds = (x, y, width, height) if asked.fullscreen else (x + 100, y + 100, 640, 400)
        return [Seen(pid=session.pid, number=1, bounds=bounds, onscreen=True)]

    def above(self, window: Seen) -> list[Seen]:
        return []

    def activate(self, window: Seen) -> str:
        return ""


class Absent(ObeyingHost):
    """No window is ever listed."""

    def windows(self) -> list[Seen]:
        return []


class Covered(ObeyingHost):
    """Off screen until activated."""

    def __init__(self) -> None:
        self.activations = 0

    def windows(self) -> list[Seen]:
        return [Seen(w.pid, w.number, w.bounds, self.activations > 0) for w in super().windows()]

    def activate(self, window: Seen) -> str:
        self.activations += 1
        return ""


class Dragged(ObeyingHost):
    """The owner dragged the window to the other display after it opened."""

    def windows(self) -> list[Seen]:
        x, y, width, height = DISPLAYS[1].bounds
        return [Seen(w.pid, w.number, (x + 100, y + 100, 640, 400), True)
                for w in super().windows()]


class Stuck(ObeyingHost):
    """Listed but never shown, whatever is done to bring it forward."""

    def windows(self) -> list[Seen]:
        return [Seen(w.pid, w.number, w.bounds, False) for w in super().windows()]
