"""`screen_wait` judged at a declared stop (`on_breakpoint`, `on_watch`), from the server.

The machine is released retrace by retrace (`VRT`). A stop the named breakpoint made is a firing;
a change watch's stop cannot be told from a retrace by its address, so a stop is the watch's when
its bytes differ from the ones read at the stop before. A firing whose condition holds arms a
judgement at the next retrace, where the frame is whole; there the predicate ends the wait or the
machine is released again. DOSBox-X reads its screen without running the machine, so a firing
costs one stop and one read, and only the final stop is the reply's.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from scry_core import progress as mprogress
from scry_core import reply_contract as contract
from scry_core import stop_wait

from scry_dosbox_x import arming, grammar, placement
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

NO_LINE_WHY = "DOSBox-X's debugger reports no beam line at a stop"


def declared_row(spec: stop_wait.StopWait) -> dec.Declaration:
    """The declaration `spec` names; one that cannot stop the machine where a wait can tell it
    is refused before anything runs."""
    store = arming.current_store()
    kinds = (spec.kind,)
    held = store.held_ref(spec.ref, kinds)
    if held is None:
        raise stop_wait.no_such_row(spec, [d.ref for d in store.declarations()
                                           if d.kind == spec.kind])
    decl = next(d for d in store.declarations() if d.kind == spec.kind and d.ref == held)
    if spec.kind == "breakpoint" and decl.role != "stop":
        raise stop_wait.not_a_stop(held, decl.role)
    if spec.kind == "watch" and decl.watch_mode != "change":
        raise stop_wait.not_a_change_watch(held, str(decl.watch_mode))
    if spec.kind == "watch" and decl.by == "pointer":
        raise stop_wait.follows_pointer(held)
    return decl


class _Reader:
    """Registers and memory at the current stop, for the condition and a watch's bytes."""

    def __init__(self, session: ds.Session) -> None:
        self.session = session
        _, self.regs, _ = session.stop_survey()

    def register(self, name: str) -> int:
        value = grammar.register_value(self.regs, name)
        if value is None:
            raise ds.Invalid("bad_argument", f"the condition names {name!r}, which is no "
                             "register of this machine")
        return value

    def memory(self, ref: str, size: int) -> int:
        seg, off = placement.read_target(ref, "DS", self.session)
        return int.from_bytes(self.session.read_bytes(seg, off, size), "little")


class Watched(Protocol):
    name: str
    said: str
    examined: int

    def hit(self) -> dict[str, Any] | None: ...

    def state(self) -> dict[str, Any]: ...

    def why(self) -> str: ...


Advance = Callable[[ds.Session, float, float, ds.Progress], bool]
Cut = Callable[[ds.Session], "dict[str, Any] | None"]
Finish = Callable[[ds.Session, dict[str, Any]], dict[str, Any]]
#: The bound's stop: `out` when a `VRT` was still out; answers whether one stays armed.
Expire = Callable[[ds.Session, bool], bool]
#: The fields a refusal carries of the stop it ends at (`retrace._ended_at`).
Ended = Callable[[ds.Session], dict[str, Any]]


def screen_wait_at(session: ds.Session, spec: stop_wait.StopWait, watched: Watched,
                   seconds: float, progress: ds.Progress, advance: Advance, cut: Cut,
                   finish: Finish, expire: Expire, ended: Ended,
                   core_note: str = "") -> dict[str, Any]:
    """The wait itself. `advance`, `cut`, `finish`, `expire` and `ended` are `retrace`'s one
    retrace, its attribution of a breakpoint's stop, its stop reply, its stop at the bound and
    the fields of the stop a refusal ends at. `core_note` is added to a `never_fired` on a core
    that can pass over a breakpoint."""
    decl = declared_row(spec)
    width = (decl.width or 1) if spec.kind == "watch" else 0
    bytes_before = _watched_bytes(session, decl.ref, width) if width else None
    began = time.monotonic()
    deadline = began + seconds
    clock = mprogress.Ticker(seconds, progress)
    firings = examined = 0
    watched.examined = 0
    armed = False
    while True:
        clock.expired()
        out = False
        if time.monotonic() >= deadline or (out := advance(session, began, deadline,
                                                           ds.no_progress)):
            pending = expire(session, out)
            if not firings:
                e = stop_wait.never_fired(spec, seconds, firings=0, frames_examined=examined,
                                          retrace_pending=pending, **ended(session))
                raise (ds.Invalid(e.code, f"{e}; {core_note}", **e.fields) if core_note else e)
            return finish(session, {
                "verdict": contract.TIMEOUT, "predicate": watched.name, "already": False,
                "waited_s": round(time.monotonic() - began, 1),
                **stop_wait.fields(spec, firings, examined,
                                   contract.unavailable(NO_LINE_WHY)),
                **watched.state(), "retrace_pending": pending,
                "note": stop_wait.timeout_note(watched.said, spec, firings, examined, seconds,
                                               judged_at="at the retrace")
                        + (watched.why() if examined else "")})
        # Any declared breakpoint's stop is attributed, whatever is waited on: a watch's wait
        # must not take another row's mid-frame stop for a retrace.
        attribution = cut(session)
        fired = False
        if attribution is not None:
            if decl.ref not in (attribution.get("ref"), *attribution.get("refs", ())):
                raise ds.Invalid("wait_stopped",
                    f"another declared breakpoint stopped the machine, so the wait at "
                    f"{decl.ref!r} cannot go on", firings=firings, frames_examined=examined,
                    **{**ended(session), "cause": st.cause(attribution)}, retrace_pending=True)
            fired = True
        elif spec.kind == "watch":
            now = _watched_bytes(session, decl.ref, width)
            fired, bytes_before = now != bytes_before, now
            if fired:
                STATE.retrace_pending = True    # the `VRT` the watch's stop cut is still out
        if fired:
            firings += 1
            reader = _Reader(session)
            armed = armed or stop_wait.holds(spec.condition, reader.register, reader.memory)
        elif armed:
            examined += 1
            watched.examined = examined
            try:
                hit = watched.hit()
            except ds.Invalid as e:
                raise ds.Invalid(e.code, f"{e}; the wait had stopped at a retrace after a firing",
                                 **{**e.fields, "firings": firings, "frames_examined": examined,
                                    **ended(session)}) from None
            if hit is not None:
                return finish(session, {
                    "verdict": contract.TARGET, "predicate": watched.name, "already": False,
                    "waited_s": round(time.monotonic() - began, 1),
                    **stop_wait.fields(spec, firings, examined,
                                       contract.unavailable(NO_LINE_WHY)),
                    **watched.state(), **hit})
            armed = False
        clock.tick("screen_wait {said} at {ref}: {firings} firings, {elapsed:.0f}s of {bound:g}s",
                   said=watched.said, ref=decl.ref, firings=firings, bound=seconds)


def _watched_bytes(session: ds.Session, ref: str, width: int) -> bytes:
    seg, off = placement.read_target(ref, "DS", session)
    return session.read_bytes(seg, off, width)
