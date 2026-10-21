"""A session's life: its `start` judged, launched, made ready, re-armed and its plan run, and its
`close`. The bodies of the two tools, which the server registers; its own module because how a
session comes up and goes down changes for reasons the tool registrations do not."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from scry_core import log_marks, narrowing
from scry_core import placement as window
from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_declarations as dec
import dosbox_launch as dlaunch
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_presence as dpresence
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE

#: How a refusal names the state directory `start` chose when the caller gave none.
DEFAULT_STATE_DIR = (f"the default state directory (`<cwd>/{dlaunch.DEFAULT_STATE_SUBDIR}`; "
                     "`state_dir` names another)")


def _window_flags(shared: bool, display: str) -> list[str]:
    """Where a watched window goes, as the host's placement helper says (`scry_core.placement`);
    a headless session has no window. No flags is an answer on a one-display host; no helper,
    or one that failed, refuses a watched start: inventing a geometry here is how windows end up
    off-screen or on the display nobody is looking at."""
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
          progress: ds.Progress, ops: Callable[[], sequence.Ops]) -> dict[str, Any]:
    """The body of the `start` tool; `ops` is the server's step vocabulary, for a `plan`. An
    optional text left empty is not given."""
    # THE PATHS FIRST: a path as wrong with a session live as with none is refused before
    # anything here acts (an expired session closed, the symbol table forgotten).
    cwd_given = paths.absolute("cwd", cwd)
    conf_path = paths.absolute("conf", conf)
    captures_path = paths.absolute("captures_dir", captures_dir) if captures_dir else None
    logfile_path = paths.absolute("logfile", logfile) if logfile else None
    state_path = paths.absolute("state_dir", state_dir) if state_dir else None
    if binary:
        paths.absolute("binary", binary)
    window.check_display(shared, display)
    shown_display = window.shared_display(shared, display)
    if STATE.session is not None:
        if STATE.session.alive():
            raise ds.Invalid("session_live", "a session is already live. `close` it first: two "
                             "emulators sharing one machine make every timing on it "
                             "a measurement of the neighbour as much as of the guest")
        # An EXPIRED session still owns its terminal. Dropping the object on the floor
        # leaked one descriptor per cycle in a process designed to be long-lived, and
        # restarting after a bound expires is the normal way to use this.
        #
        # AND THIS ONE CANNOT REPORT A REAP FAILURE, deliberately. It is reached only
        # under `not alive()`, so `close()` takes its dead branch, the signals never
        # run and `reap_failed` is never set: a consumer here would be unreachable.
        STATE.session.close()
        STATE.session = None
        STATE.clear_running_state()     # its stop and its queue, whatever this start then does
    # A NEW SESSION IS A NEW PROCESS AT A NEW BASE, so the previous one's table may not
    # survive into it. It is cleared here rather than only on the dead-session branch
    # above, because `start` is reached with no session at all far more often than with
    # an expired one, and that is precisely the path a stale table would ride through.
    STATE.forget_symbols()
    resolved = binaries.resolve(binary)

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
        # EVERY SESSION HAS THE INPUT ROUTE: input reaches the guest through that socket alone,
        # so a session started without a port could take no key and no click at all.
        input_port=input_port,
        state_dir=state_path if state_path is not None else cwd_path / dlaunch.DEFAULT_STATE_SUBDIR,
        binary=resolved.path,
        background=dlaunch.judge_background(background, shared),
    )
    dlaunch.validate(launch)
    if launch.program and launch.input_port is not None:
        launch = replace(launch, stub_drive=dlaunch.stub_drive(launch.conf))
    # KEY AND VALIDATE THE DECLARATION STORE BEFORE THE EMULATOR BOOTS. Its constructor
    # reads and parses the persisted file, and a corrupt or hand-edited one raises a
    # `DeclarationError` -- which, done after the session was up, escaped as a traceback
    # with the emulator running and no `session` block, and the next `start` then refused
    # "already live". Built here it fails as a clean INVALID with nothing started to clean
    # up. Keyed by the RESOLVED conf path so two spellings of one file are one identity and
    # two guests are two; `STATE.store` itself is assigned only once the session is ready, below.
    store = placement.to_invalid(lambda: dec.DeclarationStore(str(launch.conf.resolve())))
    # EVERYTHING ELSE JUDGED, then the two directories this server writes into, with their
    # parents: the emulator creates neither (a save into a missing state directory is logged as
    # `SAVE_FAILED`). A refusal past this point (a busy port) leaves them made.
    # A DEFAULT IS NAMED AS ONE: a caller who passed no `state_dir` is told which place was
    # chosen for them and which argument moves it, not handed an argument they never gave.
    state_name = "state_dir" if state_path is not None else DEFAULT_STATE_DIR
    for name, made in (("captures_dir", launch.captures_dir), (state_name, launch.state_dir)):
        if made is not None:
            paths.make_directory(name, made)
    # THE PROBE IS PART OF THE START: what it spends comes off the wait for the prompt.
    asked = time.monotonic()
    binary_facts = dlaunch.binary_facts(resolved, binaries.VERSION_TIMEOUT_S)
    session = ds.Session(launch)
    STATE.starting = session
    try:
        ready = session.wait_ready(
            timeout=max(ds.READY_TIMEOUT_S - (time.monotonic() - asked), 0.0), progress=progress)
    except ds.Invalid as e:
        # IT IS CLOSED BEFORE THE REFUSAL GOES OUT. Assigning first and waiting after
        # left a real emulator running behind an INVALID reply, with nothing in the
        # message telling the caller to close it and the next `start` refusing with a
        # different message that named neither problem.
        #
        # FOUR OF THE SIX `close()` SITES CAN TAKE THE LIVE BRANCH, and two of them
        # report a reap failure: this one, and the `close` tool in its `exit_code`. The
        # other two drop it deliberately and the reasons differ -- the `except
        # BaseException` arm below is already carrying an escaping exception with nowhere
        # to put a second message, and `main()`'s `finally` runs at process exit where
        # there is no reply left to write to. It is set inside `close()`'s `if self.proc.poll() is
        # None:` block, so it can only be produced by closing a session that is ALIVE: a
        # consumer on the DEAD branch, where `poll()` is non-None and the signals never run,
        # would read a field that closing an already-exited session leaves empty.
        #
        # `wait_ready` raising with the child still running is exactly the case where
        # SIGKILL can fail to reap, so this arm is where a stray emulator is most
        # likely and least visible.
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
    # The store was built and validated above, before the emulator started; it becomes the
    # live one only now the session is ready, so `STATE.store` is never set without a session.
    STATE.store = store
    STATE.session_origin = STATE.origin()
    STATE.conf_fingerprint = dlaunch.fingerprint(launch.conf)
    # THE RUNNING STATE IS CLEARED BEFORE THE FIRST STOP IS RECORDED, or the clearing
    # takes the record with it and the server holds no stop until the next contact.
    STATE.clear_running_state()
    rearm = arming.arm_at_start(session)   # before the park's survey, so the first stop lists them
    running.observe_stop(session)     # the park at the debugger is the session's first stop
    STATE.found_stop_last = {}        # ...its own, and never a stop "on its own" beside it
    session.presence = dpresence.open_shown(session, presence, shared)
    # WHERE THE STUB IS, said in the reply: a conf's autoexec that runs its own program has to
    # run the stub first, and a wheel install puts it wherever the package landed.
    started = st.reply(**st.process_facts(), shared=shared, display=shown_display,
                       ready_after_s=ready,
                       argv=session.argv, **binary_facts,
                       stub=str(dlaunch.GUEST_DIR / "INJECT.COM"),
                       input_port=contract.or_unavailable(session.launch.input_port,
                                                          "no input route was opened"),
                       background=launch.background, presence=dpresence.of(session).reply(),
                       **rearm)
    if not plan:
        return started
    # A PLAN RUNS ON THE FRESH SESSION, through the SAME executor `perform`
    # uses, so the two moments cannot drift. The started-reply is folded in under `start`
    # so a caller sees BOTH that the session came up and what the plan did; a plan that
    # fails leaves the session open at wherever it stopped, exactly as `perform` does.
    settle = sequence.SETTLE_DEFAULT_S if settle_seconds is None else settle_seconds
    # A PLAN DRIVES THE MACHINE as `perform` does, so the window is lit while it runs.
    with dpresence.of(session).driving():
        ran = sequence.run_steps(session, plan, settle, ops(), prechecked=True)
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


#: How a clean close's reply names the tails it left out.
CLOSE_HOW = ("close(detail=True) keeps the channels' last words on a clean quit too; once a close "
             "has answered the console's are gone (the logfile stays at its path)")


def _log_tail(session: ds.Session) -> str | dict[str, Any]:
    """The logfile's last words, or why there are none."""
    logfile = session.launch.logfile
    if logfile is None:
        return contract.unavailable("this session was started without a logfile")
    try:
        # THE END ONLY: a guest's log can run to hundreds of megabytes, and four bytes a
        # character covers any UTF-8 the tail holds.
        with Path(logfile).open("rb") as f:
            f.seek(max(f.seek(0, 2) - 4 * log_marks.TAIL_CHARS, 0))
            return f.read().decode("utf-8", errors="replace")[-log_marks.TAIL_CHARS:]
    except OSError as e:
        return contract.unavailable(f"the logfile could not be read: {e}")


def close(progress: ds.Progress, detail: bool = False) -> dict[str, Any]:
    """The body of the `close` tool."""
    if STATE.session is None:
        return st.reply(closed=False, ended_by="none", note="there was no session")
    # THE SESSION'S LAST ACCOUNT, read before it ends: what the process was, at the top, so its
    # `pid` is the process this call ended, and the block as it stood.
    facts, was = st.process_facts(), st.session_block()
    rc = STATE.session.close(progress=progress)
    # THE LAST WORDS ARE READ AFTER THE EXIT, so they hold what the emulator said on its way
    # out; the console's are what the drain still holds, the log's are the file's.
    clean = STATE.session.ended_how == "quit" and rc == 0
    tails = ({"stdout_tail": STATE.session.console_tail(log_marks.TAIL_CHARS),
              "errorlog_tail": _log_tail(STATE.session)} if detail or not clean
             else narrowing.omission(["stdout_tail", "errorlog_tail"], CLOSE_HOW))
    # READ AFTER THE CLOSE, because that is when it can be set: a child SIGKILLed and never
    # reaped has no exit code, and `exit_code` says why in its place (an emulator may still
    # be on the machine). Not in `state()`: `was` is captured before `close()` runs.
    unreaped = STATE.session.reap_failed
    ended_by = STATE.session.ended_how
    STATE.session = None
    STATE.forget_symbols()
    STATE.clear_running_state()
    exit_code = contract.or_unavailable(
        None if unreaped else rc,
        f"the emulator was SIGKILLed and not reaped ({unreaped}): it may still be on the "
        f"machine" if unreaped else "the emulator's exit code could not be read")
    return {"status": "ok", "closed": True, **facts, "ended_by": ended_by,
            "exit_code": exit_code, **tails, "session": was}
