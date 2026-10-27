"""The bodies of the `start` and `close` tools, which the server registers."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from scry_core import log_marks, narrowing, session_block
from scry_core import placement as window
from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_debugger as dbg
import dosbox_declarations as dec
import dosbox_dos_calls as dos_calls_trace
import dosbox_guest_files as guest
import dosbox_launch as dlaunch
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_presence as dpresence
import dosbox_process as dprocess
import dosbox_run_state as run_state
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

#: How a refusal names the default state directory.
DEFAULT_STATE_DIR = (f"the default state directory (`<cwd>/{dlaunch.DEFAULT_STATE_SUBDIR}`; "
                     "`state_dir` names another)")


def _window_flags(shared: bool, display: str) -> list[str]:
    """The watched window's flags from the host placement helper; none for a headless session.
    No flags is a one-display host's answer: DOSBox-X sizes its own window, so it opens
    unplaced."""
    if not shared:
        return []
    placed = window.ask("dosbox", True, display)
    if placed.flags is None:
        raise ds.Invalid("host_failed", f"a watched session needs its window placed, and "
                         f"{placed.why}. Fix that, or start without `shared`")
    return placed.flags


def start(conf: str, cwd: str, session_seconds: int, shared: bool,
          display: str, flags: list[str] | None, break_on_int3: bool,
          program: str, logfile: str, capture_video: bool, captures_dir: str,
          plan: list[dict[str, Any]] | None, settle_seconds: float | None, input_port: int,
          state_dir: str, binary: str, background: bool | None, presence: bool,
          dos_calls: bool, log_categories: dict[str, str] | None, guest_files: list[str] | None,
          progress: ds.Progress, ops: Callable[[], sequence.Ops]) -> dict[str, Any]:
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
    window.check_display(shared, display)
    shown_display = window.shared_display(shared, display)
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
        watched=shared,
        window_flags=_window_flags(shared, shown_display),
        flags=list(flags or []),
        break_on_int3=break_on_int3,
        program=program or None,
        capture_video=capture_video,
        captures_dir=captures_path,
        logfile=logfile_path,
        log_categories=dict(log_categories or {}),
        # Input reaches the guest through this socket alone.
        input_port=input_port,
        state_dir=state_path if state_path is not None else cwd_path / dlaunch.DEFAULT_STATE_SUBDIR,
        binary=resolved.path,
        debugger_headless=binaries.debugger_headless(resolved.path),
        debugger_commands=commands_built,
        background=dlaunch.judge_background(background, shared),
    )
    dlaunch.validate(launch)
    if launch.program and launch.input_port is not None:
        launch = replace(launch, stub_drive=dlaunch.stub_drive(launch.conf))
    # Built before the emulator boots: a corrupt persisted file then fails as a clean INVALID
    # with nothing to clean up. Keyed by the resolved conf path, so two spellings are one identity.
    store = placement.to_invalid(lambda: dec.DeclarationStore(str(launch.conf.resolve())))
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
        if session.reap_failed:
            raise ds.Invalid("session_broken", f"{e} -- and worse, {session.reap_failed}, so an "
                             f"emulator may still be running. Check for a stray "
                             f"`dosbox-x` before starting again") from None
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
        except ds.Invalid:
            session.close(progress=progress)
            STATE.session = None
            raise
    rearm = arming.arm_at_start(session)   # before the park's survey, so the first stop lists them
    running.observe_stop(session)     # the park at the debugger is the session's first stop
    STATE.found_stop_last = {}        # ...its own, and never a stop "on its own" beside it
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
    started = st.reply(**st.process_facts(), shared=shared, display=shown_display,
                       ready_after_s=ready,
                       argv=session.argv, **binary_facts,
                       **commands,
                       stub=str(dlaunch.GUEST_DIR / "INJECT.COM"),
                       input_port=contract.or_unavailable(session.launch.input_port,
                                                          "no input route was opened"),
                       background=launch.background, presence=dpresence.of(session).reply(),
                       **channels, **rearm)
    if not plan:
        return started
    # A failing plan leaves the session open where it stopped, as `perform` does.
    settle = sequence.SETTLE_DEFAULT_S if settle_seconds is None else settle_seconds
    # A PLAN DRIVES THE MACHINE as `perform` does, so the window is lit while it runs.
    with dpresence.of(session).driving():
        ran = sequence.run_steps(session, plan, settle, ops())
    return st.extend(ran, start={k: v for k, v in started.items()
                                 if k not in ("status", "session")})


def presence_shown(session: ds.Session | None) -> bool | dict[str, Any]:
    """What `status` says of the presence: the session's, `false` with no session open, and
    unavailable once its emulator has ended, whatever the last delivery said."""
    if session is None:
        return False
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
        # A guest log can run to hundreds of megabytes; 4 bytes covers any UTF-8 character.
        with Path(logfile).open("rb") as f:
            f.seek(max(f.seek(0, 2) - 4 * log_marks.TAIL_CHARS, 0))
            return f.read().decode("utf-8", errors="replace")[-log_marks.TAIL_CHARS:]
    except OSError as e:
        return contract.unavailable(f"the logfile could not be read: {e}")


def close(progress: ds.Progress, detail: bool = False) -> dict[str, Any]:
    """The body of the `close` tool."""
    if STATE.session is None:
        return st.reply(closed=False, ended_by="none", note=session_block.NO_SESSION_CLOSE_NOTE)
    # Read before the session ends, so `pid` is the process this call ended.
    facts, was = st.process_facts(), st.session_block()
    rc = STATE.session.close(progress=progress)
    # After the exit, so every file the emulator held is closed and flushed.
    left = {"guest_files": guest.at_close()} if STATE.guest_files else {}
    # Read after the exit so the tails hold what the emulator said on the way out.
    clean = STATE.session.ended_how == "quit" and rc == 0
    tails = ({"stdout_tail": STATE.session.stdout_tail(log_marks.TAIL_CHARS),
              "errorlog_tail": _log_tail(STATE.session)} if detail or not clean
             else narrowing.omission(["stdout_tail", "errorlog_tail"], CLOSE_HOW))
    # Set only by the close: a SIGKILLed, unreaped child has no exit code.
    unreaped = STATE.session.reap_failed
    drained = STATE.session.drain_ended
    ended_by = STATE.session.ended_how
    STATE.session = None
    STATE.forget_symbols()
    STATE.clear_running_state()
    exit_code = contract.or_unavailable(
        None if unreaped else rc,
        f"the emulator was SIGKILLed and not reaped ({unreaped}): it may still be on the "
        f"machine" if unreaped else "the emulator's exit code could not be read")
    return {"status": "ok", "closed": True, **facts, "ended_by": ended_by,
            "exit_code": exit_code, **tails, **left,
            **({"note": f"the emulator's output reader: {drained}"}
               if drained and drained != dprocess.DRAIN_EOF else {}),
            "session": was}
