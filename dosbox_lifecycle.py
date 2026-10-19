"""A session's life: its `start` judged, launched, made ready, re-armed and its plan run, and its
`close`. The bodies of the two tools, which the server registers; its own module because how a
session comes up and goes down changes for reasons the tool registrations do not."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_binary as binaries
import dosbox_declarations as dec
import dosbox_launch as dlaunch
import dosbox_paths as paths
import dosbox_placement as placement
import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE


def start(conf: str, cwd: str, seconds: int, mode: str, window_flags: list[str] | None,
          flags: list[str] | None, break_on_int3: bool, program: str | None,
          logfile: str | None, capture_video: bool, captures_dir: str | None,
          plan: list[dict[str, Any]] | None, plan_wait: float, input_port: int | None,
          state_dir: str | None, binary: str, background: bool | None,
          progress: ds.Progress, ops: Callable[[], sequence.Ops]) -> dict[str, Any]:
    """The body of the `start` tool; `ops` is the server's step vocabulary, for a `plan`."""
    # THE PATHS FIRST: a path as wrong with a session live as with none is refused before
    # anything here acts (an expired session closed, the symbol table forgotten).
    cwd_given = paths.absolute("cwd", cwd)
    conf_path = paths.absolute("conf", conf)
    captures_path = (paths.absolute("captures_dir", captures_dir)
                     if captures_dir is not None else None)
    logfile_path = paths.absolute("logfile", logfile) if logfile is not None else None
    state_path = paths.absolute("state_dir", state_dir) if state_dir is not None else None
    if binary:
        paths.absolute("binary", binary)
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
    # A NEW SESSION IS A NEW PROCESS AT A NEW BASE, so the previous one's table may not
    # survive into it. It is cleared here rather than only on the dead-session branch
    # above, because `start` is reached with no session at all far more often than with
    # an expired one, and that is precisely the path a stale table would ride through.
    STATE.forget_symbols()
    if mode not in ("headless", "shared"):
        raise ds.Invalid("bad_argument", f"unknown mode {mode!r}: it is `headless` or `shared`")
    resolved = binaries.resolve(binary)

    cwd_path = paths.resolved("cwd", cwd_given)
    launch = dlaunch.Launch(
        conf=conf_path, cwd=cwd_path, seconds=seconds,
        watched=(mode == "shared"),
        window_flags=list(window_flags or []),
        flags=list(flags or []),
        break_on_int3=break_on_int3,
        program=program,
        capture_video=capture_video,
        captures_dir=captures_path,
        logfile=logfile_path,
        # EVERY SESSION HAS THE INPUT ROUTE: input reaches the guest through that socket alone,
        # so a session started without a port could take no key and no click at all.
        input_port=input_port if input_port is not None else 0,
        state_dir=state_path if state_path is not None else cwd_path / "save",
        binary=resolved.path,
        background=dlaunch.judge_background(background, mode == "shared"),
    )
    dlaunch.validate(launch)
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
    for name, made in (("captures_dir", launch.captures_dir), ("state_dir", launch.state_dir)):
        if made is not None:
            paths.make_directory(name, made)
    binary_facts = binaries.facts(resolved)
    session = ds.Session(launch)
    STATE.starting = session
    try:
        ready = session.wait_ready(progress=progress)
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
    # WHERE THE STUB IS, said in the reply: a conf's autoexec that runs its own program has to
    # run the stub first, and a wheel install puts it wherever the package landed.
    started = st.reply(mode=mode, ready_after_s=ready, argv=session.argv, **binary_facts,
                       stub=str(dlaunch.GUEST_DIR / "INJECT.COM"),
                       input_port=session.launch.input_port,
                       background=launch.background,
                       **rearm)
    if not plan:
        return started
    # A PLAN RUNS ON THE FRESH SESSION, through the SAME executor `perform`
    # uses, so the two moments cannot drift. The started-reply is folded in under `start`
    # so a caller sees BOTH that the session came up and what the plan did; a plan that
    # fails leaves the session open at wherever it stopped, exactly as `perform` does.
    ran = sequence.run_steps(session, plan, plan_wait, ops(), prechecked=True)
    return st.extend(ran, start={k: v for k, v in started.items()
                                 if k not in ("status", "session")})


def close(progress: ds.Progress) -> dict[str, Any]:
    """The body of the `close` tool."""
    if STATE.session is None:
        return st.reply(closed=False, ended_by="none", note="there was no session")
    was = STATE.session.state()
    rc = STATE.session.close(progress=progress)
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
    return {"status": "ok", "closed": True, "ended_by": ended_by, "exit_code": exit_code,
            "session": was}
