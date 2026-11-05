"""The bodies of the `start`, `window` and `close` tools, which the server registers."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from scry_core import log_marks, narrowing, session_block, window_size
from scry_core import reply_contract as contract
from scry_core import window as core_window

from scry_dosbox_x import (
    arming,
    inputs,
    paths,
    placement,
    run_state,
    running,
    sequence,
    start_symbols,
)
from scry_dosbox_x import binary as binaries
from scry_dosbox_x import conf as dconf
from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import declarations as dec
from scry_dosbox_x import dos_calls as dos_calls_trace
from scry_dosbox_x import guest_files as guest
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import presence as dpresence
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

#: How a refusal names the default state directory.
DEFAULT_STATE_DIR = ("the default state directory (the session's scratch, gone at `close`; "
                     "`state_dir` names another)")


def _judge_window(wanted: core_window.WindowRequest | None, conf: Path,
                  flags: list[str]) -> core_window.WindowRequest | None:
    """What the conf's `sdl output` decides about the request: `surface` fills the display by
    switching its video mode, leaving the window off screen, and ignores a size. A watched window
    with no stated size gets the largest 4:3 one the usable area holds, where the output takes
    one and the conf gives none of its own."""
    if wanted is None:
        return None
    wanted = replace(wanted, dpi_aware=dconf.dpi_awareness(conf, flags))
    output = dconf.sdl_output(conf, flags)
    if wanted.fullscreen and output == "surface":
        raise ds.Invalid("bad_argument",
                         "`fullscreen` with `sdl output=surface` switches the display's video "
                         "mode and leaves the window off screen: leave `output` to the conf's "
                         "other choices (`opengl`, `openglnb`), or start with `fullscreen=false`")
    honoured = dconf.honours_window_size(output, sys.platform)
    if wanted.size is not None and not honoured:
        raise ds.Invalid("bad_argument",
                         f"`size` is ignored under `sdl output={output}` on this host: the window "
                         "would keep the conf's size. Use an OpenGL or Direct3D `output`, or "
                         "start without `size`")
    own = dconf.states_window_size(conf, flags)
    if not honoured or own:
        return wanted
    return core_window.fit_size(
        wanted, lambda usable, scale: window_size.aspect_fit((4, 3), usable, scale, sys.platform))


def _refuse_unreaped(session: ds.Session, cause: ds.Invalid) -> None:
    """A start that failed after the emulator was killed, if the kill did not reap it."""
    if session.reap_failed:
        raise ds.Invalid("session_broken", f"{cause} -- and worse, {session.reap_failed}, so an "
                         f"emulator may still be running. Check for a stray "
                         f"`dosbox-x` before starting again") from None


def start(conf: str, cwd: str, session_seconds: int, shared: bool,
          flags: list[str] | None, break_on_int3: bool,
          program: str, logfile: str, capture_video: bool, captures_dir: str,
          plan: list[dict[str, Any]] | None, settle_seconds: float | None, input_port: int,
          state_dir: str, binary: str, background: bool | None, presence: bool,
          dos_calls: bool, log_categories: dict[str, str] | None, guest_files: list[str] | None,
          progress: ds.Progress, ops: Callable[[], sequence.Ops], *, symbols: str = "",
          base_from: str = start_symbols.PROGRAM, display: int | None = None,
          fullscreen: bool | None = None, size: str | None = None) -> dict[str, Any]:
    """The body of the `start` tool; `ops` is the server's step vocabulary, for a `plan`."""
    # Paths first: refused before anything acts (an expired session closed, symbols forgotten).
    cwd_given = paths.absolute("cwd", cwd)
    conf_path = paths.absolute("conf", conf)
    captures_path = paths.absolute("captures_dir", captures_dir) if captures_dir else None
    logfile_path = paths.absolute("logfile", logfile) if logfile else None
    state_path = paths.absolute("state_dir", state_dir) if state_dir else None
    if binary:
        paths.absolute("binary", binary)
    guest_paths = guest.check_guest_files(guest_files)
    held = start_symbols.check(symbols, base_from)
    wanted = _judge_window(core_window.requested(shared, display, fullscreen, size,
                                                 emulator="dosbox-x"),
                           conf_path, list(flags or []))
    if STATE.session is not None:
        if STATE.session.alive():
            raise ds.Invalid("session_live", "a session is already live. `close` it first: two "
                             "emulators sharing one machine make every timing on it "
                             "a measurement of the neighbour as much as of the guest")
        # An expired session still owns its channel. Not consuming `reap_failed` is deliberate:
        # under `not alive()` `close()` never signals, so it is never set.
        STATE.session.close()
        STATE.session = None
        STATE.clear_running_state()     # its stop and its queue, whatever this start then does
    # A new process at a new base: the previous table must not survive, and `start` mostly
    # arrives with no session at all, so clearing only on the expired branch would miss it.
    STATE.forget_symbols()
    resolved = binaries.resolve(binary)
    commands_built = frozenset(binaries.debugger_commands(resolved.path))
    if dos_calls and dos_calls_trace.DOSTRACE not in commands_built:
        raise dbg.missing(dos_calls_trace.DOSTRACE, "`start(dos_calls=True)`")

    cwd_path = paths.resolved("cwd", cwd_given)
    launch = dlaunch.Launch(
        conf=conf_path, cwd=cwd_path, seconds=session_seconds,
        window=wanted,
        flags=list(flags or []),
        core=dconf.cpu_core(conf_path, list(flags or [])),
        break_on_int3=break_on_int3,
        program=program or None,
        capture_video=capture_video,
        captures_dir=captures_path,
        logfile=logfile_path,
        log_categories=dict(log_categories or {}),
        # Input reaches the guest through this socket alone.
        input_port=input_port,
        state_dir=(state_path if state_path is not None
                   else STATE.session_scratch() / dlaunch.DEFAULT_STATE_SUBDIR),
        binary=resolved.path,
        bundle=resolved.bundle or "",
        debugger_headless=binaries.debugger_headless(resolved.path),
        debugger_commands=commands_built,
        background=core_window.judge_background(background, shared),
    )
    dlaunch.validate(launch)
    if launch.program and launch.input_port is not None:
        launch = replace(launch, stub_drive=dlaunch.stub_drive(launch.conf))
    # Built before the emulator boots: a corrupt persisted file then fails as a clean INVALID
    # with nothing to clean up. Keyed by the resolved conf path, so two spellings are one identity.
    store = placement.to_invalid(lambda: dec.DeclarationStore(dlaunch.store_identity(launch)))
    # The emulator creates neither directory (a save into a missing one logs `SAVE_FAILED`).
    state_name = "state_dir" if state_path is not None else DEFAULT_STATE_DIR
    for name, made in (("captures_dir", launch.captures_dir), (state_name, launch.state_dir)):
        if made is not None:
            paths.make_directory(name, made)
    # The probe is part of the start: what it spends comes off the wait for the debugger.
    asked = time.monotonic()
    binary_facts = dlaunch.binary_facts(resolved, binaries.VERSION_TIMEOUT_S)
    # Taken before the emulator boots: a file the guest writes later is then never "before".
    STATE.guest_files = guest.take(guest_paths)
    session = ds.Session(launch)
    STATE.starting = session
    try:
        ready = session.wait_ready(
            timeout=max(run_state.READY_TIMEOUT_S - (time.monotonic() - asked), 0.0),
            progress=progress)
    except ds.Invalid as e:
        # Closed before the refusal goes out, or an emulator keeps running behind an INVALID.
        # `wait_ready` raising with the child alive is where a stray emulator is most likely.
        session.close(progress=progress)
        _refuse_unreaped(session, e)
        raise
    except BaseException:
        session.close(progress=progress)
        raise
    finally:
        STATE.starting = None
    STATE.session = session
    STATE.maps.started()
    STATE.store = store
    STATE.session_origin = STATE.origin()
    STATE.conf_fingerprint = dlaunch.fingerprint(launch.conf)
    # Cleared first, or the clearing takes the first stop record with it.
    STATE.clear_running_state()
    if dos_calls:
        try:
            STATE.dos_calls = dos_calls_trace.begin(session)
        except BaseException as e:
            session.close(progress=progress)
            STATE.session = None
            STATE.store = None
            STATE.clear_running_state()
            if isinstance(e, ds.Invalid):
                _refuse_unreaped(session, e)
            raise
    STATE.start_symbols = held
    rearm = arming.arm_at_start(session)   # before the park's survey, so the first stop lists them
    running.observe_stop(session)     # the park at the debugger is the session's first stop
    STATE.found_stop_last = {}        # ...its own, and never a stop "on its own" beside it
    # A refusal here leaves the session live, as its message says: `window` and `close` still act.
    seen: dict[str, Any] = {}
    try:
        if wanted is not None:
            seen = {"window": core_window.prove(session.pid, wanted).block()}
    finally:    # the live session a refusal leaves carries the presence it was asked for
        session.presence = dpresence.open_shown(session, presence, shared)
    commands: dict[str, Any] = ({"debugger_commands": sorted(session.commands)}
                                if session.commands else {})
    channels: dict[str, Any] = {}
    if STATE.dos_calls is not None:
        channels["dos_calls"] = str(STATE.dos_calls.path)
    if launch.log_categories:
        channels["log_categories"] = dict(launch.log_categories)
    if STATE.guest_files:
        channels["guest_files"] = [{"path": str(p), "before": f.shown()}
                                   for p, f in STATE.guest_files.items()]
    holding: dict[str, Any] = ({"symbols": {"held": held.path, "base_from": held.base_from}}
                               if held is not None else {})
    started = st.reply(**st.process_facts(), shared=shared,
                       ready_after_s=ready,
                       argv=session.argv, **binary_facts,
                       **commands,
                       stub=str(dlaunch.GUEST_DIR / dlaunch.STUB_FILE),
                       input_port=contract.or_unavailable(session.launch.input_port,
                                                          "no input route was opened"),
                       background=launch.background, presence=dpresence.of(session).reply(),
                       **seen, **channels, **rearm,
                       **holding,
                       **_notes(launch))
    if not plan:
        return started
    # A failing plan leaves the session open where it stopped, as `perform` does.
    settle = sequence.SETTLE_DEFAULT_S if settle_seconds is None else settle_seconds
    # A PLAN DRIVES THE MACHINE as `perform` does, so the window is lit while it runs.
    with dpresence.of(session).driving():
        ran = sequence.run_steps(session, plan, settle, ops())
    return st.extend(ran, start={k: v for k, v in started.items()
                                 if k not in ("status", "session")})


def _notes(launch: dlaunch.Launch) -> dict[str, str]:
    """What `start` has to say beyond its facts: the dynamic core's limit, and a stub the conf runs
    that speaks another protocol than this server, which would only show at the first input."""
    said = [dlaunch.DYNAMIC_CORE_BREAKPOINTS] if dlaunch.is_dynamic(launch.core) else []
    said += [f"the conf runs {where}, a stub of protocol {proto}, and this server speaks "
             f"{inputs.STUB_PROTOCOL}: its first key or mouse call will be refused (`no_channel`); "
             f"mount this package's `guest` directory instead"
             for where, proto in dconf.stub_protocols(launch.conf, launch.cwd)
             if proto != inputs.STUB_PROTOCOL]
    return {"note": " ".join(said)} if said else {}


def window(session: ds.Session, front: bool) -> dict[str, Any]:
    """The body of the `window` tool: where the watched window is, brought forward on `front`."""
    fields = core_window.answer(session.pid, session.launch.window, front=front,
                                launched_behind=session.launch.background)
    size = fields.get("size")
    if (isinstance(size, dict) and size.get("matches") is False and session.parked
            and session.stop_count <= 1 and "note" not in fields):
        fields["note"] = ("the window takes the size asked at the guest's first video mode, so it "
                          "reads the emulator's own size until the guest has run: `resume` it and "
                          "read `window` again")
    return st.reply(**fields)


def presence_shown(session: ds.Session) -> bool | dict[str, Any]:
    """What `status` says of the presence: the session's, and unavailable once its emulator has
    ended, whatever the last delivery said."""
    if not session.alive():
        return contract.unavailable("the session's emulator has ended")
    return dpresence.of(session).reply()


CLOSE_HOW = ("close(detail=True) keeps the emulator's last words on a clean quit too; once a close "
             "has answered its output is gone (the logfile stays at its path)")


def _log_tail(session: ds.Session) -> str | dict[str, Any]:
    """The logfile's last words, or why there are none."""
    logfile = session.launch.logfile
    if logfile is None:
        return contract.unavailable("this session was started without a logfile")
    try:
        return log_marks.tail(Path(logfile))
    except OSError as e:
        return contract.unavailable(f"the logfile could not be read: {e}")


def close(progress: ds.Progress, detail: bool = False) -> dict[str, Any]:
    """The body of the `close` tool."""
    if STATE.session is None:
        none = contract.unavailable("no session was running")
        return st.reply(closed=False, ended_by="none", pid=none, exit_code=none,
                        note=session_block.NO_SESSION_CLOSE_NOTE)
    # Read before the session ends, so `pid` is the process this call ended.
    facts = st.process_facts()
    rc = STATE.session.close(progress=progress)
    # After the exit, so every file the emulator held is closed and flushed.
    left = {"guest_files": guest.at_close()} if STATE.guest_files else {}
    # Read after the exit so the tails hold what the emulator said on the way out.
    clean = STATE.session.ended_how == "quit" and rc == 0
    tails = narrowing.last_words(
        {"stdout_tail": STATE.session.stdout_tail(log_marks.TAIL_CHARS),
         "errorlog_tail": _log_tail(STATE.session)}, clean=clean, detail=detail, how=CLOSE_HOW)
    # Set only by the close: a SIGKILLed, unreaped child has no exit code.
    unreaped = STATE.session.reap_failed
    drained = STATE.session.drain_failure
    ended_by = STATE.session.ended_how
    STATE.session = None
    STATE.forget_symbols()
    STATE.clear_running_state()
    exit_code = contract.or_unavailable(
        None if unreaped else rc,
        f"the emulator was SIGKILLed and not reaped ({unreaped}): it may still be on the "
        f"machine" if unreaped else "the emulator's exit code could not be read")
    notes = [f"the emulator's output reader: {drained}"] if drained else []
    return {"status": "ok", "closed": True, **facts, "ended_by": ended_by,
            "exit_code": exit_code, **tails, **left,
            **({"note": " ".join(notes)} if notes else {}),
            "session": st.session_block()}
