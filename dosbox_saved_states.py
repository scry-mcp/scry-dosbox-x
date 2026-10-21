"""The emulator's saved states, written and read through the debugger channel's own
SAVESTATE and LOADSTATE, and listed off their directory. Its own module because the state
files and their commands change for reasons of their own; each function is a session method's
body, and `Session` delegates to it."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from scry_core import cancel, state_files
from scry_core import reply_contract as contract
from scry_core.reply_contract import Invalid

import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_paths as paths
import dosbox_session as ds


def _state_dir(ses: ds.Session) -> Path:
    if ses.launch.state_dir is None:
        return ses.launch.cwd / dlaunch.DEFAULT_STATE_SUBDIR
    return ses.launch.state_dir


def _state_command(ses: ds.Session, verb: str, path: Path, seconds: float) -> dict[str, object]:
    """`SAVESTATE` or `LOADSTATE` of `path` over the debugger channel, with the debugger
    stopped as the commands need it: a RUNNING guest is broken in on first and released
    again after, so the machine is left the way it was found. The reply's part:
    `paused` (it had to be stopped) and `waited_s` (the command alone, not the break-in or
    the release); whether it runs after the call is the session block's to say."""
    # WHETHER THE COMMAND WENT DOWN THE CHANNEL, which a load cut short reads (one cancelled
    # in the break-in sent nothing and replaced nothing), and whether it was answered ok.
    ses.state_sent = ses.state_answered = False
    if "\n" in str(path) or "\r" in str(path):
        raise Invalid("bad_argument", f"a state path is one line; got {str(path)!r}")
    paused = not ses.at_debugger()
    began = time.monotonic()
    marked: dict[str, object] = {}
    try:
        if paused:
            ses.break_in()
            began = time.monotonic()
        if verb == "LOADSTATE":
            # THE MARK IS TAKEN WITH THE GUEST PARKED AND THE LOAD NOT YET SENT: nothing is
            # written in between, so everything after it is the loaded machine's.
            marked = {"mark": channel_marks(ses)}
        ses.state_sent = True
        ok, lines = ses.control.request(f"EXEC {verb} {path}", seconds, poll=cancel.check)
        ses.state_answered = ok
    except BaseException as e:
        # AN EMULATOR THAT DIED UNDER THE COMMAND closes the channel, which reads as a drop the
        # channel redials: said as what it is, since nothing will answer again.
        if isinstance(e, Invalid) and not ses.alive():
            ds.gone_if_dead(ses, began, seconds, f"`{verb}`")
        # A COMMAND THAT ENDS EARLY, refused or cancelled (its waits poll, the break-in's
        # included), releases the guest it stopped, as its bound would. Best effort: the
        # command's own refusal or the cancellation is the answer, and one from the release
        # (a refusal, or the host's channel gone under it) would hide it; the end reads what
        # the machine was left as.
        if paused and (isinstance(e, Invalid) or cancel.is_cancellation(e)):
            with cancel.shielded(), contextlib.suppress(Invalid, OSError):
                if cancel.is_cancellation(e) and not ses.at_debugger():
                    ses.break_in()        # a BREAK sent lands; wait for it, then release
                if ses.at_debugger():
                    ses.resume_after_command()
        if isinstance(e, Invalid) and e.code == "no_channel":
            why = str(e).rstrip(".")
            raise Invalid("no_channel",
                          f"{verb} goes down the debugger channel, and {why}. The saved "
                          f"states need that channel and a build carrying the `{verb}` "
                          f"debugger command (REFERENCE.md, Saved states)"
                          ) from None
        raise
    waited = round(time.monotonic() - began, 2)
    if paused:
        ses.resume_after_command()             # `session.running` says where it is left
    if ok:
        return {"paused": paused, "waited_s": waited, **marked}
    said = " / ".join(line.strip() for line in lines if line.strip())
    if not any(line.startswith(f"DEBUG: {verb}") for line in lines):
        raise Invalid("no_channel",
            f"`{verb}` came back without the debugger's own answer to it "
                      f"({said or 'nothing came back'}): saved states need a build whose "
                      f"debugger carries `{verb}` (REFERENCE.md, Saved states)")
    raise Invalid("unexpected_answer",
        f"the emulator refused {verb} of {path}: {said}. Its log says why (a state of "
                  f"another DOSBox-X version, program, memory size or machine type is "
                  f"refused rather than asked about)")


def channel_marks(ses: ds.Session) -> dict[str, object]:
    """`state_load`'s `mark`: where the log ends now, one number per channel `log` takes, all
    equal because one file holds the three (`scry_core.log_marks`); unavailable with no logfile,
    or when the host could not size it."""
    if ses.launch.logfile is None:
        return contract.unavailable("this session was started without a logfile, so there is "
                                    "no log to mark")
    try:
        end = ses.e9_mark()
    except OSError as e:
        return contract.unavailable(f"the logfile could not be sized: {e}")
    return {channel: end for channel in dlogs.LOG_CHANNELS}


def state_save(ses: ds.Session, name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, object]:
    """Save the machine under `name` as `<state_dir>/<name>.sav`, by the debugger's own
    `SAVESTATE` (`_state_command`), and read the file back for what it says about
    itself. Running or parked, headless or windowed. Never overwrites, and a save that
    failed leaves no file behind: the emulator removes the old one and writes the new one
    in place, so a failure part-way would otherwise hold the name with a broken state.
    Saving alters nothing."""
    dlaunch.check_state_name(name)
    ds.check_wait_bound(seconds)
    state_dir = ses._state_dir()
    dest = state_dir / f"{name}.sav"
    if paths.taken(dest):         # a dangling link too: the save would write through it
        raise Invalid("bad_argument",
            f"a state named {name!r} already exists at {dest}: pick another name, "
                      "this never overwrites")
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        outcome = ses._state_command("SAVESTATE", dest, seconds)
    except BaseException:                  # a refusal, a cancel or a defect alike
        if not ses.state_answered:         # answered ok, only the release failed: it is whole
            dest.unlink(missing_ok=True)   # it was not there before this call
        raise
    if not dest.is_file():
        raise Invalid("unexpected_answer",
            f"the emulator answered SAVESTATE and {dest} is not there")
    meta = dlaunch.state_meta(dest)
    return {"name": name, "path": str(dest), "bytes": meta["bytes"],
            **{k: meta[k] for k in dlaunch.STATE_META}, **outcome}


def state_load(ses: ds.Session, name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, object]:
    """Load the state `name` from `<state_dir>/<name>.sav` by the debugger's own
    `LOADSTATE`. Running or parked: a running guest is stopped for it and released again,
    a parked one stays parked, at the loaded machine's position, which counts as a stop
    of its own: the record of the stop before describes a machine that is gone. It
    REPLACES the machine, so the session is altered from here on, and after any refusal
    but a missing channel too, since a load refused part-way may have replaced some of
    it."""
    dlaunch.check_state_name(name)
    ds.check_wait_bound(seconds)
    state_dir = ses._state_dir()
    source = state_dir / f"{name}.sav"
    if (why := state_files.not_a_state(source)) is not None:
        raise Invalid("unknown_ref",
            f"no state named {name!r} to load: at {source} {why}, and `state_save` refuses "
                      "the name while it is there")
    if not source.is_file():
        raise Invalid("unknown_ref",
            f"no state named {name!r} under {state_dir}: `state_list` says what is there")
    meta = dlaunch.state_meta(source)
    parked = ses.at_debugger()
    try:
        outcome = ses._state_command("LOADSTATE", source, seconds)
    except BaseException as e:
        # CUT SHORT AFTER IT WAS SENT, refused or cancelled: some of it may be loaded, so the
        # session is altered and, parked, the stop record before it may describe a machine
        # that is gone, as a load that answered does. Cut short before, it replaced nothing.
        if ses.state_sent and not (isinstance(e, Invalid)
                                    and e.code in ("no_channel", "bad_argument")):
            ses.altered = True
            if parked:
                ses.stop_count += 1
        raise
    ses.altered = True
    if not outcome["paused"]:
        ses.stop_count += 1
    return {"name": name, "path": str(source),
            **{k: meta[k] for k in dlaunch.STATE_META}, **outcome}


def _listed(path: Path) -> dict[str, object] | None:
    """`state_meta` of a listed `.sav`, or None for one removed while the directory was read."""
    try:
        return dlaunch.state_meta(path)
    except FileNotFoundError:
        return None


def state_list(ses: ds.Session) -> dict[str, object]:
    """Every `.sav` under the state directory with what it says about itself. A reading
    of a directory: no window, no console, works while the machine runs."""
    state_dir = ses._state_dir()
    files = sorted(state_dir.glob("*.sav")) if state_dir.is_dir() else []
    # THE WORKING SLOT IS NOT A NAMED STATE: the emulator's own numbered file sits
    # beside the copies, and listed among them it counts one state too many.
    named = [m for p in files if not p.stem.isdigit() and (m := _listed(p)) is not None]
    slots = [m for p in files if p.stem.isdigit() and (m := _listed(p)) is not None]
    return {"state_dir": str(state_dir), "states": named,
            "working_slot": slots[-1] if slots else contract.unavailable(
                "the emulator's own numbered slot has not been written")}
