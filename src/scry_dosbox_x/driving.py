"""Run control for a `Session`: releasing the machine, waiting for its stop, and the runs built on
them (`run_to`, `resume`, a retrace, a `LOG`), with the breakpoints they arm and remove.

`Session` forwards the calls other modules make; `stepping` shares the breakpoint cleanup.
"""

from __future__ import annotations

import contextlib
import time

from scry_core import cancel
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.progress import Progress, no_progress
from scry_core.reply_contract import Invalid

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import grammar
from scry_dosbox_x import session as ds


def still_armed(exc: Invalid, target: str, began: float, ctl: str | None = None) -> Invalid:
    """The refusal that CARRIES the irreversible part."""
    also = f" (and so is the control at {ctl})" if ctl else ""
    return Invalid(exc.code,
                   f"{exc} -- and the breakpoint at {target}{also} is STILL ARMED after "
                   f"{round(time.monotonic() - began, 1)}s: this call wrote a trap byte "
                    f"into the guest and could not read the machine back to remove it, so "
                    f"it will stop the next `resume`")


def release(session: ds.Session, command: str) -> list[str]:
    """Let the machine run with `command` (`RUN`, `VRT`, the `LOG` family, `STEPIN`); a
    command the debugger refused released nothing."""
    try:
        ok, lines = session.exec(command)
    except BaseException:
        # sent, with no answer to say it was not taken: the next contact asks `RUNSTATE`
        session.forget_stop()
        raise
    if not ok:
        raise Invalid("unexpected_answer",
            f"the debugger refused `{command}`: {' / '.join(lines) or 'no reason given'}")
    session.forget_stop()
    return lines


def retrace(session: ds.Session, began: float, deadline: float,
            progress: Progress = no_progress) -> tuple[bool, float]:
    """Run to the next vertical retrace."""
    session.require_run_state("a retrace")
    release(session, ds.RETRACE_COMMAND)
    return ds.Session.await_stop(session, began, deadline, "the next retrace", progress,
                              label="run_for: the next retrace")


def log_cpu(session: ds.Session, word: str, count: int, began: float, deadline: float,
            progress: Progress = no_progress) -> tuple[bool, float]:
    """`word` of the `LOG` family with its `count` in hex (`LOGC 41`), sent as the release it
    is, and the stop it ends at asked of `RUNSTATE` until `deadline`."""
    if word not in ds.LOG_WORDS:
        raise ValueError(f"{word!r} is not a word of the LOG family")
    session.require_run_state("trace")
    command = f"{word} {dbg.typed_hex(count)}"
    release(session, command)
    return ds.Session.await_stop(session, began, deadline, f"`{command}`", progress,
                              label=f"trace: `{command}`")


def resume(session: ds.Session, look: bool = True) -> dict[str, object]:
    """Let the machine run, and with `look` SAY whether it stopped again straight away; without
    it the call returns after the release and a stop is what the next call finds."""
    output = "\n".join(release(session, "RUN"))
    if not session.has(dbg.RUNSTATE):
        return {"halted": contract.unavailable(
                    f"this build's debugger has no `{dbg.RUNSTATE}` command to say whether "
                    f"the machine stopped again ({dbg.COMMANDS_SECTION})"),
                "stopped_at": None, "output": output}
    if not look:
        return {"halted": False, "stopped_at": None, "output": output}
    began = time.monotonic()
    expired, _ = ds.Session.await_stop(session, began, began + ds.RESUME_LOOK_S, "a stop",
                                    label="resume")
    stopped_at: dict[str, str] | None = None
    if not expired:
        with contextlib.suppress(Invalid):
            stopped_at = session.where()
    return {"halted": not expired, "stopped_at": stopped_at, "output": output}


def run_to(session: ds.Session, seg: int, off: int, seconds: float,
           control: tuple[int, int] | None = None,
           progress: Progress = no_progress) -> dict[str, object]:
    """Run until the machine reaches an address, and say where it really stopped."""
    # THE ARGUMENT CHECKS THAT NEED NOTHING FROM THE MACHINE GO FIRST.
    ds.check_segment(seg)
    vocab.check_wait(seconds)
    session.require_run_state("run_to")
    stopped = session.where()      # refuses a running machine BEFORE arming anything
    # THE OFFSET'S WIDTH IS THE CPU MODE'S.
    top = grammar.check_offset(off, stopped["mode"])
    target = f"{seg:04X}:{off:04X}"
    ctl = None
    if control is not None:
        cseg, coff = control
        if not 0 <= cseg <= 0xFFFF or not 0 <= coff <= top:
            raise Invalid("bad_argument", f"the control {cseg:04X}:{coff:X} is outside what "
                          f"{stopped['mode']} mode can address")
        ctl = f"{cseg:04X}:{coff:04X}"
        # THE SAME PLACE, NOT THE SAME SPELLING: in real mode `1234:0010` and `1235:0000` are
        # one byte.
        same = (ctl == target if str(stopped["mode"]).startswith("Pr")
                else cseg * 16 + coff == seg * 16 + off)
        if same:
            raise Invalid("bad_argument",
                f"the control {ctl} is the same address as the target {target}: "
                          "a control proves the target COULD have fired, and the target "
                          "cannot prove that about itself")
    session.altered |= session.arming_writes()
    session.command(f"BP {dbg.typed_addr(seg, off)}")
    if control is not None:
        session.command(f"BP {dbg.typed_addr(*control)}")
    armed = session.breakpoints()
    for spelled in [target] + ([ctl] if ctl is not None else []):
        if not any(f"BP {spelled}" == b["entry"] for b in armed):
            raise Invalid("readback_refused",
                f"the debugger does not list a breakpoint at {spelled} after being "
                f"told to set one. What it holds: {[b['entry'] for b in armed]}. "
                f"Resuming now would run the machine with nothing to stop it, and the "
                f"reply would blame the address rather than the arming")
    began = time.monotonic()
    deadline = began + seconds
    control_hits = 0
    at: dict[str, str] | None = None
    expired, interrupted = True, False
    # THE CONTROL LOOP: released, waited for, read; a stop AT the control is counted and the
    # machine let go again.
    try:
        while True:
            release(session, "RUN")
            expired, _saw_at = ds.Session.await_stop(session, began, deadline, target, progress)
            if expired:
                break
            try:
                at = session.where()
            except Invalid as exc:
                raise still_armed(exc, target, began, ctl) from None
            # THE TARGET IS ASKED FIRST.
            if control is None or stopped_at(at, seg, off):
                break
            if not stopped_at(at, control[0], control[1]):
                break
            control_hits += 1
            if time.monotonic() >= deadline:
                # AT REST ON THE CONTROL WITH NO BOUND LEFT: reported as a stop elsewhere, and
                # the bound DID run out, whatever the last wait saw.
                expired = True
                break
            at = None
        read_after_bound = at is None
        if at is None:
            # THE BOUND RAN OUT: the machine is stopped where it stands and read after the
            # loop, because it can be found at rest however the loop ended.
            try:
                interrupted = ds.Session.stop_at_bound(session)
                at = session.where()
            except Invalid as exc:
                raise still_armed(exc, target, began, ctl) from None
    except BaseException as e:
        if cancel.is_cancellation(e):
            abandon_run(session, [target] + ([ctl] if ctl is not None else []))
        raise
    # ARRIVAL IS THE SAME PLACE, NOT THE SAME SPELLING.
    arrived = stopped_at(at, seg, off)
    on_control = control is not None and stopped_at(at, control[0], control[1])
    if on_control and read_after_bound and not interrupted:
        control_hits += 1          # found resting on the control after the bound: it fired
    # THE TARGET AND THE CONTROL ARE OURS ON EVERY STOPPED OUTCOME: a `BP` is persistent, and
    # nobody asked to keep either.
    removals = remove_own(session, [target] + ([ctl] if ctl is not None else []))
    removed, cleanup = removals[0]
    control_removed = False
    if ctl is not None:
        control_removed, control_cleanup = removals[1]
        cleanup += control_cleanup
    # THE VERDICT IS WHAT ENDED THE RUN, read off the stop and not off the wait.
    if arrived:
        verdict, why = contract.TARGET, ""
    elif interrupted or (expired and on_control):
        verdict = contract.TIMEOUT
        why = (f"the {seconds:g} s bound ran out and the run was interrupted at "
               f"{at['cs']}:{at['eip']}" if interrupted else
               f"it came to rest ON the control {ctl} (its hit number {control_hits}) when "
               f"the bound ran out")
    else:
        verdict = contract.OTHER_STOP
        why = f"it stopped at {at['cs']}:{at['eip']}: something else got there first"
    rom = (f" If {target} is in ROM (a BIOS or option-ROM segment such as F000), that is "
           f"why: a code breakpoint in ROM is acknowledged, appears in BPLIST, and never "
           f"fires" if interrupted else "")
    return {"verdict": verdict, "target": target,
            "stopped_at": at, "waited_s": round(time.monotonic() - began, 3),
            "breakpoint_removed": removed,
            "control": control_block(ctl, control_hits,
                                              removed=control_removed),
            "note": cleanup.strip() if arrived else
                    f"{why}, and not at {target}{rom}." + (
                        cleanup if not removed else
                        f" The breakpoint at {target} was removed.{cleanup}")}


def stopped_at(at: dict[str, str], seg: int, off: int) -> bool:
    """Whether a stop position IS `seg:off`."""
    if str(at["mode"]).startswith("Pr"):
        return at["cs"] == f"{seg:04X}" and int(at["eip"], 16) == off
    return int(at["cs"], 16) * 16 + int(at["eip"], 16) == seg * 16 + off


def control_block(ctl: str | None, hits: int, *, removed: bool) -> dict[str, object]:
    """The `control` field of a `run_to` reply."""
    if ctl is None:
        return contract.unavailable("no control was named")
    return {"at": ctl, "hits": hits, "removed": removed}


def abandon_run(session: ds.Session, own: list[str]) -> None:
    """A RUN CANCELLED IN FLIGHT LEAVES NOTHING ARMED."""
    with cancel.shielded(), contextlib.suppress(Invalid, OSError):
        if not session.at_debugger():
            session.break_in()
        remove_own(session, own)


def remove_own(session: ds.Session, spelled: list[str]) -> list[tuple[bool, str]]:
    """Remove the breakpoints THIS call armed, on a stopped machine; for each, whether it
    went and the sentence a reply carries when it did not."""
    try:
        gone = ds.Session.delete_rows(session, [ds.entry_is(f"BP {s}") for s in spelled])
    except Invalid as exc:
        return [(False, f" The stop is sound; the cleanup could not be confirmed ({exc}). "
                        f"Assume the breakpoint at {s} is still armed.") for s in spelled]
    out: list[tuple[bool, str]] = []
    for s, (row, absent) in zip(spelled, gone, strict=True):
        if row is None:
            out.append((False, f" The breakpoint at {s} was not in the list at cleanup "
                               f"time, so nothing was removed and something else took it "
                               f"away."))
        elif not absent:
            out.append((False, f" `BPDEL` was sent and {s} is STILL in the debugger's "
                               f"list: it will stop the next `resume`."))
        else:
            out.append((True, ""))
    return out
