"""Saved states over the debugger channel's SAVESTATE and LOADSTATE; `Session` delegates here."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from scry_core import cancel, state_files
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.reply_contract import Invalid

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import paths
from scry_dosbox_x import session as ds


def _state_dir(ses: ds.Session) -> Path:
    return dlaunch.state_dir_of(ses.launch)


def _state_command(ses: ds.Session, verb: str, path: Path, seconds: float) -> dict[str, object]:
    """`SAVESTATE` or `LOADSTATE` of `path`; a running guest is broken in on and released after.
    Returns `paused` (it had to be stopped)."""
    # a load cancelled in the break-in sent nothing and replaced nothing
    ses.state_sent = ses.state_answered = False
    if "\n" in str(path) or "\r" in str(path):
        raise Invalid("bad_argument", f"a state path is one line; got {str(path)!r}")
    if not ses.has(verb):
        raise dbg.missing(verb, "a saved state")
    paused = not ses.at_debugger()
    began = time.monotonic()
    marked: dict[str, object] = {}
    try:
        if paused:
            ses.break_in()
            began = time.monotonic()
        if verb == "LOADSTATE":
            # parked and not yet sent: everything logged after the mark is the loaded machine's
            marked = {"mark": channel_marks(ses)}
        ses.state_sent = True
        # through `exec`: a load replaces the machine, so the stop's survey is dropped
        ok, lines = ses.exec(f"{verb} {path}", seconds)
        ses.state_answered = ok
    except BaseException as e:
        # a death under the command closes the channel, which reads as a drop it redials
        if isinstance(e, Invalid) and not ses.alive():
            ds.gone_if_dead(ses, began, seconds, f"`{verb}`")
        # release the guest this call stopped; best effort, so a failure of the release
        # does not hide the refusal or cancellation that is the answer
        if paused and (isinstance(e, Invalid) or cancel.is_cancellation(e)):
            with cancel.shielded(), contextlib.suppress(Invalid, OSError):
                if cancel.is_cancellation(e) and not ses.at_debugger():
                    ses.break_in()        # a BREAK sent lands; wait for it, then release
                if ses.at_debugger():
                    ses.resume()
        if isinstance(e, Invalid) and e.code == "no_channel":
            why = str(e).rstrip(".")
            raise Invalid("no_channel",
                          f"{verb} goes down the debugger channel, and {why}. The saved "
                          f"states need that channel and a build carrying the `{verb}` "
                          f"debugger command (REFERENCE.md, Saved states)"
                          ) from None
        raise
    if paused:
        ses.resume()             # `session.running` says where it is left
    if ok:
        return {"paused": paused, **marked}
    said = " / ".join(line.strip() for line in lines if line.strip())
    if not any(line.startswith(f"DEBUG: {verb}") for line in lines):
        raise Invalid("no_channel",
            f"`{verb}` came back without the debugger's own answer to it "
                      f"({said or 'nothing came back'}): saved states need a build whose "
                      f"debugger carries `{verb}` (REFERENCE.md, Saved states)")
    why = (" A state of another DOSBox-X version, program, memory size or machine type is "
           "refused rather than asked about." if verb == "LOADSTATE" else
           " The host would not take the file (a full volume answers `SAVE_FAILED`).")
    where = " The emulator's log says more." if ses.launch.logfile is not None else ""
    raise Invalid("unexpected_answer",
        f"the emulator refused {verb} of {path}: {said}.{why}{where}")


def channel_marks(ses: ds.Session) -> dict[str, object]:
    """`state_write(method="load")`'s `mark`: the log's end, equal on every channel (one file)."""
    if ses.launch.logfile is None:
        return contract.unavailable("this session was started without a logfile, so there is "
                                    "no log to mark")
    try:
        end = ses.e9_mark()
    except OSError as e:
        return contract.unavailable(f"the logfile could not be sized: {e}")
    return {channel: end for channel in dlogs.FILE_CHANNELS}


def save_state(ses: ds.Session, name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, object]:
    """Save the machine as `<state_dir>/<name>.sav`. Never overwrites; a failed save leaves no
    file, since the emulator writes in place and would otherwise hold the name broken."""
    dlaunch.check_state_name(name)
    vocab.check_wait(seconds)
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


def _replaced(ses: ds.Session) -> None:
    """The machine is the loaded one, whole or in part."""
    ses.altered = ses.machine_replaced = True
    ses.fired_entry = None
    _stub_replaced(ses)


def load_state(ses: ds.Session, name: str, seconds: float = ds.STATE_WAIT_S) -> dict[str, object]:
    """Load `<state_dir>/<name>.sav`. A parked guest stays parked and the load counts as a stop
    of its own. The session is altered from here on, also after a refusal other than a missing
    channel, since a load refused part-way may have replaced some of the machine."""
    ses.machine_replaced = False
    dlaunch.check_state_name(name)
    vocab.check_wait(seconds)
    state_dir = ses._state_dir()
    source = state_dir / f"{name}.sav"
    if (why := state_files.not_a_state(source)) is not None:
        raise state_files.refused_load(name, source, why)
    if not source.is_file():
        raise Invalid("unknown_ref",
            f"no state named {name!r} under {state_dir}: `state_list` says what is there")
    meta = dlaunch.state_meta(source)
    parked = ses.at_debugger()
    try:
        outcome = ses._state_command("LOADSTATE", source, seconds)
    except BaseException as e:
        # sent, then refused or cancelled: part of it may be loaded
        if ses.state_sent and not (isinstance(e, Invalid)
                                    and e.code in ("no_channel", "bad_argument")):
            _replaced(ses)
            if parked:
                ses.stop_count += 1
        raise
    _replaced(ses)
    if not outcome["paused"]:
        ses.stop_count += 1
    return {"name": name, "path": str(source),
            **{k: meta[k] for k in dlaunch.STATE_META}, **outcome}


def _stub_replaced(ses: ds.Session) -> None:
    """The input stub's last sequence went with the loaded memory (`Session.stub_replaced`)."""
    ds.Session.stub_replaced(ses)


def _listed(path: Path) -> dict[str, object] | None:
    """`state_meta` of a listed `.sav`, or None for one removed while the directory was read."""
    try:
        return dlaunch.state_meta(path)
    except FileNotFoundError:
        return None


def state_list(ses: ds.Session) -> dict[str, object]:
    """Every `.sav` under the state directory; works while the machine runs."""
    state_dir = ses._state_dir()
    files = sorted(state_dir.glob("*.sav")) if state_dir.is_dir() else []
    # the emulator's own numbered slot is not a named state
    named = [m for p in files if not p.stem.isdigit() and (m := _listed(p)) is not None]
    slots = [m for p in files if p.stem.isdigit() and (m := _listed(p)) is not None]
    return {"state_dir": str(state_dir), "states": named,
            "working_slot": slots[-1] if slots else contract.unavailable(
                "the emulator's own numbered slot has not been written")}
