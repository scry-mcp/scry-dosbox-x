"""A DOSBox-X demo's loop with the presence layers drawn in, from the timeline its own run wrote.

A demo declares the layers that exist for it: the call captions, the keycaps and the pointer.
Pillow and numpy (scry-core's `decorate` extra) are loaded only while a loop is made.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from scry_core import demo as core
from scry_core import motion, timeline
from scry_core import overlay as ov
from scry_core.verdict import Invalid

from scry_dosbox_x import presence, summaries

#: The layers a demo may declare, and those it may not, each with why.
CALLS: tuple[ov.Layer, ...] = ("calls",)
CALLS_AND_KEYS: tuple[ov.Layer, ...] = ("calls", "keys")
CALLS_AND_POINTER: tuple[ov.Layer, ...] = ("calls", "pointer")
ALL: tuple[ov.Layer, ...] = ("calls", "keys", "pointer")
LACKING: Mapping[ov.Layer, str] = {
    "pause": "a decorated demo draws no pause mark: a recording holds only frames the machine ran",
    "record": "a decorated demo draws no record mark: no capture carries one"}
#: The tools whose input a timeline carries; `perform` and `drive` hold others among their steps.
PRESSING_TOOLS = frozenset({"send_keys", "send_mouse", "perform", "drive"})


def declared(layers: Sequence[ov.Layer]) -> None:
    """Refuse, as `ValueError`, a layer a demo cannot declare."""
    for layer in layers:
        if layer in LACKING:
            raise ValueError(f"a demo declares no `{layer}` layer: {LACKING[layer]}")
        if layer not in ALL:
            raise ValueError(f"a demo declares `calls`, `keys` and `pointer`, not {layer!r}")


def _ops(tool: str, args: Mapping[str, Any], reply: Mapping[str, Any]
         ) -> list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    """The inputs a call made, each with its own arguments and reply: the call itself, or the
    steps a `perform` or the `act` of a `drive` ran."""
    if tool in ("send_keys", "send_mouse"):
        return [(tool, args, reply)]
    steps = args.get("steps" if tool == "perform" else "act") or []
    ran = reply.get("ran") if tool == "perform" else (reply.get("act") or {}).get("ran")
    found = []
    for at, got in enumerate(ran if isinstance(ran, list) else []):  # hidden in a transcript
        n = got.get("step", at)  # a list that kept summaries shows its first rows and its last step
        if n < len(steps) and steps[n].get("op") in ("send_keys", "send_mouse") \
                and isinstance(got.get("reply"), Mapping):
            found.append((str(steps[n]["op"]), steps[n], got["reply"]))
    return found


def _frame(reply: Mapping[str, Any], ends: int | None) -> int | None:
    """The frame an input ran to, as its reply or its summary says; None where neither does, and
    never past the end of its call."""
    said = reply.get("frame")
    frame = said if type(said) is int else summaries.frame_in(str(reply.get("summary", "")))
    return None if frame is None or ends is None else min(frame, ends)


def pressed(tool: str, args: Mapping[str, Any], reply: core.Reply) -> list[timeline.Event]:
    """The input a call fired, as the live overlay reports it: the keys of a `send_keys`, the
    pointer where a `send_mouse` left it and its button's presses."""
    if reply.get("status") != "ok":
        return []
    ends = core.counted(reply)[1]
    fired: list[timeline.Event] = []
    for op, given, got in _ops(tool, args, reply):
        if got.get("status") != "ok":
            continue
        frame = _frame(got, ends)
        if op == "send_keys":
            fired += [timeline.key(name, down, frame) for name, down in presence.key_edges(
                given.get("keys") or [], given.get("modifiers") or [],
                str(given.get("action") or "press"))]
            continue
        where = (presence.pointer_where(got, given.get("x"), given.get("y")) if "pointer" in got
                 else summaries.pointer_in(str(got.get("summary", ""))))
        if where is None and given.get("x") is not None:
            where = (int(given["x"]), int(given.get("y") or 0))
        if where is not None:
            fired.append(timeline.pointer(*where, frame))
        button = given.get("button") or ("left" if given.get("action") else "")
        if button:
            fired += [timeline.button(str(button), down, frame) for down in
                      presence.button_edges(str(given.get("action") or "click"))]
    return fired


def fired(steps: Sequence[core.Step]) -> list[core.Step]:
    """`steps` with `pressed` named for each that sends input and names no events of its own."""
    def naming(tool: str) -> Callable[[Mapping[str, Any], core.Reply], list[timeline.Event]]:
        return lambda args, reply: pressed(tool, args, reply)

    return [replace(step, events=naming(step.tool))
            if step.events is None and step.tool in PRESSING_TOOLS else step for step in steps]


def passes(document: Mapping[str, Any], demo: core.Demo) -> list[dict[str, Any]]:
    """The timeline per moment: the calls up to the step that ends it. A state load rewinds the
    frame count, so one frame number belongs to two passes of a run."""
    steps = [call["step"] for call in document["calls"]]
    shown = []
    for moment in demo.moments:
        if moment.until not in steps:
            raise Invalid(f"the timeline holds no call of step {moment.until!r}, so the moment "
                          "it ends cannot be decorated")
        shown.append({**document, "calls": document["calls"][:steps.index(moment.until) + 1]})
    return shown


def _drawing() -> Any:
    """`scry_core.decorate`, which needs the extra; `Invalid` naming it when it is not installed."""
    try:
        from scry_core import decorate
    except ImportError as e:
        raise Invalid("a demo's loop is decorated with Pillow and numpy, scry-core's `decorate` "
                      "extra: install it (`uv sync --extra decorate`)") from e
    return decorate


def starts(demo: core.Demo, run: core.Run, cuts: Sequence[motion.Cut]) -> list[int]:
    """The emulator frame each cut's recording shows at its frame 0. A `record` step's recording
    begins where its reply began; a moment of the session's own video begins where the step
    before it ended, which is as many frames into the file as the cut's first frame says."""
    tools = {step.name: step.tool for step in demo.steps}
    ended: dict[str, int] = {}
    for step in demo.steps:
        reply = run.replies.get(step.name)
        frame = None if reply is None else core._last(reply.data, core.FRAME_KEY)
        if frame is not None or ended:
            ended[step.name] = frame if frame is not None else list(ended.values())[-1]
    found = []
    for moment, cut in zip(demo.moments, cuts, strict=True):
        if tools[moment.until] == core.RECORD_TOOL:
            begun = core.counted(run.replies[moment.until])[0]
            if begun is None:
                raise Invalid(f"the reply of the `record` step {moment.until!r} says no frame "
                              "it began at, so its clip cannot be placed in the run's timeline")
            found.append(begun)
        elif moment.after in ended:
            found.append(ended[moment.after] + moment.skip - cut.first)
        else:
            raise Invalid(f"no reply up to step {moment.after!r} counts a frame, so the moment "
                          "it begins cannot be placed in the run's timeline")
    return found


def decorator(demo: core.Demo, run: core.Run, document: Mapping[str, Any],
              layers: Sequence[ov.Layer], cuts: Sequence[motion.Cut]) -> motion.Decorator:
    """What `motion.build` draws each of `cuts` with."""
    declared(layers)
    decorate = _drawing()
    style = decorate.Style.of(ov.Overlay(calls="calls" in layers, keys="keys" in layers,
                                         pointer="pointer" in layers, pause=False, record=False))
    first = starts(demo, run, cuts)
    drawn = [decorate.for_loop(one, first, style) for one in passes(document, demo)]

    def each(n: int, numbers: Sequence[int], pictures: Sequence[motion.Picture],
             rate: Any, box: motion.Box) -> list[motion.Picture]:
        shown: list[motion.Picture] = drawn[n](n, numbers, pictures, rate, box)
        return shown
    return each


@contextlib.contextmanager
def _replaced(owner: Any, name: str, value: Any) -> Iterator[None]:
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def prepared(demo: core.Demo) -> core.Demo:
    """`demo` with the input its steps send named for its timeline."""
    return replace(demo, steps=fired(demo.steps))


def main(demo: core.Demo, layers: Sequence[ov.Layer], argv: Sequence[str] | None = None) -> int:
    """The demo's command line with its loop drawn in `layers`; the runner has no seam for a
    decorator, so for the run it is handed this module's."""
    declared(layers)
    real_execute, real_build = core.execute, motion.build

    def execute(demo_: core.Demo, run: core.Run, transcript: Path,
                update_readme: bool = False) -> int:
        if update_readme and demo_.moments:
            _drawing()  # before the emulator runs, not after

        def build(cuts: Sequence[motion.Cut], work: Path,
                  decorate: motion.Decorator | None = None) -> motion.Built:
            # The runner names its files from the transcript's stem and exports no name for it.
            written = core._beside(transcript).timeline
            if not written.is_file():
                raise Invalid(f"the run wrote no timeline at {written}, and a clip is decorated "
                              "only from its run's timeline")
            document = timeline.loads(written.read_text(encoding="utf-8"))
            return real_build(cuts, work, decorator(demo_, run, document, layers, cuts))

        with _replaced(motion, "build", build):
            return real_execute(demo_, run, transcript, update_readme)

    with _replaced(core, "execute", execute):
        return core.main(prepared(demo), argv)
