"""The session's two log channels, read: the guest's E9 stream off the log file and the
emulator's own lines, each since a mark, filtered, or waited for. Its own module because what a
log holds and how it is waited on change for reasons of their own; each function is a
session method's body, and `Session` delegates to it."""

from __future__ import annotations

from pathlib import Path

from scry_core import log_wait as core_wait
from scry_core import reply_contract as contract
from scry_core.progress import Progress, no_progress
from scry_core.reply_contract import Invalid

import dosbox_logs as dlogs
import dosbox_session as ds


def e9(ses: ds.Session, pattern: str, limit: int = 40) -> tuple[list[str], int]:
    """The guest's own instrumentation, FILTERED at the source.

    The whole point of a live session is that what crosses back is the answer and
    not a haystack with the answer in it, so the filtering happens here and the
    caller receives lines rather than a log.

    It distinguishes the two kinds of nothing, which is the contract this module
    exists to enforce: a log with no instrumentation AT ALL is INVALID, and a log
    with instrumentation but nothing matching is an empty list, which is an answer.
    """
    return dlogs.filter_e9(ses._e9_text(), pattern, limit)


def e9_lines(ses: ds.Session) -> list[str]:
    """EVERY line of the guest's instrumentation, in order, with `e9`'s guard on the
    channel: what the stop reply's E9 block reduces from. It carries no `limit`
    because the reduction is the server's, and the caller-facing ceiling on `e9` and
    `log` refused the whole-log read this block needs (measured: `1 << 30` as the
    limit, refused as a haystack, and every stop's `e9` block came back
    `available: false`)."""
    return dlogs.log_hits(ses._e9_text(), ".", "guest")


def log(ses: ds.Session, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
    """The log's `channel`, filtered at the source: the guest's E9 lines with `e9`'s
    own guard (a file with no instrumentation is no channel), the emulator's own
    lines, or the whole file tagged."""
    dlogs.check_channel(channel)
    if channel == "guest":
        return dlogs.filter_e9(ses._e9_text(), pattern, limit)
    return dlogs.filter_log(ses._log_text(), pattern, limit, channel)


def require_logfile(ses: ds.Session, what: str) -> Path:
    """The session's logfile, or the log readers' refusal of a session with none, `no_channel`,
    naming `what` it lacks. A tool that needs the log for a listing says which, in its own."""
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
                      f"this session was started without a logfile, so there is no {what}")
    return ses.launch.logfile


def _log_text(ses: ds.Session) -> str:
    """The log file, or the refusal that says which nothing: no logfile on the
    session, or a file the emulator has not created yet."""
    log = require_logfile(ses, "log channel to filter")
    if not log.exists():
        raise Invalid("no_channel", f"no log at {log}: the emulator has not "
                      f"written anything yet, which is not the same as having "
                      f"nothing to say")
    return log.read_text(encoding="utf-8", errors="replace")


def _e9_text(ses: ds.Session) -> str:
    """The instrumentation log, or the refusal that says WHICH nothing.

    The three guards are `e9`'s, lifted so `e9_wait` cannot answer for reasons `e9`
    refuses on. They are the difference between "your pattern matched
    nothing" and "there was no channel to match against", which is this module's
    thesis in one method.
    """
    text = ses._log_text()
    if dlogs.count_e9(text) == 0:
        raise Invalid("no_channel",
            f"{ses.launch.logfile} carries no instrumentation at all. That is "
            f"not 'your pattern matched nothing', it is 'there is nothing to "
            f"match': either the guest has not reached its first trace yet, or "
            f"this build does not emit any")
    return text


def _e9_since(ses: ds.Session, offset: int, channel: str = "guest") -> tuple[list[str], int]:
    """The COMPLETE lines of `channel` after byte `offset`, and the new offset: the log read
    whole lines at a time (`scry_core.log_wait.lines_since`), so a line half-written between
    two flushes is seen once and whole, and a read costs what is new rather than the whole
    log again. A log not there yet is nothing yet, which is what a wait is for, and a log
    rewritten shorter than the offset is read from its start."""
    log = ses.launch.logfile
    assert log is not None            # the caller refuses a session without one
    lines, offset = core_wait.lines_since(log, offset)
    return dlogs.channel_lines(lines, channel), offset


def e9_new_since(ses: ds.Session, offset: int) -> tuple[list[str], int]:
    """The complete instrumentation lines after byte `offset` and the offset to read
    from next: the stop survey's reader, so a stop pays for what the guest wrote since
    the previous one and not for the whole log again. It refuses what `e9` refuses: a
    session with no logfile has no channel, and a log the guest has not created yet
    cannot be looked at, which is not zero lines. The wait's reader keeps its own
    reading of an absent log, because nothing yet is what a wait is for."""
    log = require_logfile(ses, "instrumentation channel to summarise")
    if not log.exists():
        raise Invalid("no_channel",
            f"no log at {log}: the guest has not written "
                      f"anything yet, which is not the same as having nothing to say")
    return ses._e9_since(offset)


def e9_since_mark(ses: ds.Session, mark: int) -> list[str]:
    """Every complete instrumentation line written after byte `mark`, in order: the
    LOOK after an act. A session with no logfile has no channel; a log that has not
    appeared yet answers nothing, which is an answer about the window. The count is
    bounded by what the guest wrote, not by a limit here: the caller cuts."""
    require_logfile(ses, "instrumentation channel to look at")
    lines, _ = ses._e9_since(mark)
    return lines


def e9_mark(ses: ds.Session) -> int:
    """WHERE THE LOG ENDS RIGHT NOW, as a byte position `e9_wait(mark=)` starts from.

    It is what turns "did the guest react to THIS event" into an answerable question:
    a wait from the mark sees only what was written after it, so a line that matched
    the pattern ten seconds ago is history and not the reaction. A log that does not
    exist yet marks at 0, which is the same statement -- everything the guest will
    write is after it. A session with no logfile has no channel to mark.

    THE SIZE, NOT THE LAST NEWLINE, deliberately. A writer flushes mid-line, so the
    mark can land inside a line; `_e9_since` then drops that line's tail as a fragment
    that is not an instrumentation line, which is right -- a line BEGUN before the mark
    belongs to before it. Finding the last newline would mean reading the whole file,
    which on a multi-megabyte log is the cost `_e9_since` was written to avoid.
    """
    log = require_logfile(ses, "instrumentation channel to mark a position in")
    return log.stat().st_size if log.exists() else 0


def e9_wait(ses: ds.Session, pattern: str, seconds: float, mark: int = 0,
            progress: Progress = no_progress) -> dict[str, object]:
    """`log_wait` on the guest channel: the wait `expect` and `drive` rest on."""
    return ses.log_wait(pattern, seconds, "guest", mark, progress)


def log_wait(ses: ds.Session, pattern: str, seconds: float, channel: str, mark: int = 0,
             progress: Progress = no_progress) -> dict[str, object]:
    """WHEN a line of `channel` matching `pattern` happened, whether it already has or not yet
    (`scry_core.log_wait`): `verdict` `TARGET` with the line, or `TIMEOUT` with what arrived
    while it waited. A machine STOPPED at the debugger writes nothing, so a wait on one is
    refused (`E9Stopped`), and so is an emulator that went away.

    `mark` is the byte position the search starts from (`e9_mark`): with it, "already" means
    "written since the mark", which is the difference between "the cue has fired at some
    point" and "the cue fired in response to the key just posted".

    WHICH OCCURRENCE: the FIRST. The question this answers is "when did it happen";
    `lines_total` says how many there were, and `e9` is the tool for the recent state.

    WHAT YOU CAN DO WITH THE MOMENT is narrower than it looks: a guest writing traces is a
    guest that is RUNNING, so the console does not accept commands when this returns. What
    the moment is for: choosing an address to arm on the NEXT run, before the machine is
    released.
    """
    ds.check_wait_bound(seconds)
    rx = dlogs.compiled(pattern)
    dlogs.check_channel(channel)
    # THE ONLY REFUSAL BEFORE THE WAIT. A log that does not EXIST yet, or holds no
    # instrumentation yet, is the ordinary state of a guest just resumed, and waiting for its
    # FIRST trace is what this is for; a session with no logfile has no channel to wait on.
    require_logfile(ses, "instrumentation channel to wait on, and waiting cannot "
                    "bring one into existence")
    offset = mark

    def fresh() -> list[str]:
        nonlocal offset
        lines, offset = ses._e9_since(offset, channel)
        return lines

    got = core_wait.wait(rx, fresh, seconds=seconds, stopped=ses.at_debugger,
                         alive=ses.alive, progress=progress,
                         label=f"log_wait {channel} /{pattern}/")
    if isinstance(got, core_wait.Found):
        return {"verdict": contract.TARGET, "pattern": pattern, "channel": channel,
                **got.fields(), "since_mark": mark}
    if got.how == "STOPPED":
        raise ds._wait_stopped(pattern, got.arrived_during, got.waited_s, got.at_bound)
    if got.how == "GONE":
        raise Invalid("session_broken", core_wait.gone_message(pattern, got, seconds))
    region = "in the log altogether" if mark == 0 else f"since the mark at byte {mark}"
    # THE BOUND RAN OUT AND THE WAIT ANSWERED: a verdict, not a refusal. The machine still
    # runs, and the caller decides whether to wait longer.
    return {"verdict": contract.TIMEOUT, "pattern": pattern, "channel": channel,
            "arrived_during": got.arrived_during, "lines_examined": got.lines_examined,
            "waited_s": got.waited_s, "since_mark": mark,
            "note": core_wait.timeout_note(pattern, got, region, "guest")}
