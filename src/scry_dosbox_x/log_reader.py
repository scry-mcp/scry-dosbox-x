from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path

from scry_core import cancel, judges, log_marks
from scry_core import log_wait as core_wait
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.progress import Progress, no_progress
from scry_core.prose import counted
from scry_core.reply_contract import Invalid

from scry_dosbox_x import control, stub_link
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import session as ds


def e9(ses: ds.Session, pattern: str, limit: int = 40) -> tuple[list[str], int]:
    """The guest's E9 lines matching `pattern`, filtered at the source."""
    return dlogs.filter_e9(ses.e9_text(), pattern, limit)


def log(ses: ds.Session, pattern: str, limit: int, channel: str,
        since_mark: int = 0) -> tuple[list[str], int]:
    """The log's `channel` filtered; with `since_mark`, only whole lines written after it."""
    dlogs.check_channel(channel)
    if since_mark:
        if channel == "guest":
            ses.e9_text()
        lines, _ = core_wait.lines_since(log_file_from(ses, since_mark, channel), since_mark)
        return dlogs.filter_log("\n".join(lines), pattern, limit, channel)
    if channel == "guest":
        return dlogs.filter_e9(ses.e9_text(), pattern, limit)
    return dlogs.filter_log(ses.log_text(), pattern, limit, channel)


def log_file_from(ses: ds.Session, since_mark: int, channel: str) -> Path:
    """The session's logfile, after `log_marks.check_since_mark`."""
    log = require_logfile(ses, "log channel to read from a mark")
    log_marks.check_since_mark(since_mark, log.stat().st_size if log.exists() else 0,
                               "session" if channel == "all" else channel)
    return log


def require_logfile(ses: ds.Session, what: str) -> Path:
    """The session's logfile, or `no_channel` naming `what` it lacks."""
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
                      f"this session was started without a logfile, so there is no {what}")
    return ses.launch.logfile


def log_text(ses: ds.Session) -> str:
    """The log text, or `no_channel` if there is no log yet."""
    log = require_logfile(ses, "log channel to filter")
    if not log.exists():
        raise Invalid("no_channel", f"no log at {log}: the emulator has not "
                      f"written anything yet, which is not the same as having "
                      f"nothing to say")
    return log.read_text(encoding="utf-8", errors="replace")


def e9_text(ses: ds.Session) -> str:
    """The instrumentation log; no instrumentation at all is `no_channel`, not "no match"."""
    text = ses.log_text()
    if dlogs.count_e9(text) == 0:
        raise Invalid("no_channel",
            f"{ses.launch.logfile} carries no instrumentation at all. That is "
            f"not 'your pattern matched nothing', it is 'there is nothing to "
            f"match': either the guest has not reached its first trace yet, or "
            f"this build does not emit any")
    return text


def in_flight_note(ses: ds.Session) -> str:
    """Whether lines may still be in flight: a running emulator flushes its log in its own
    time, so a line the guest has just written may not be in the file yet, and its absence
    from a `log` read is not proof it was never written. A parked one writes nothing further,
    so the caveat says nothing."""
    if ses.parked:
        return ""
    return ("the emulator flushes its log in its own time, so a line the guest has just "
            "written may not be in the file yet")


def lost_lines_note(ses: ds.Session) -> str:
    """Whether the logfile is shorter than it has been: lines a read returned earlier are gone,
    and the shrink is said once. A growing log is the norm and says nothing."""
    log = ses.launch.logfile
    if log is None or not log.exists():
        return ""
    size = log.stat().st_size
    if ses.log_seen_bytes <= size:
        ses.log_seen_bytes = size
        return ""
    note = (f"the log lost lines it once held: it is {size} bytes now and was "
            f"{ses.log_seen_bytes}, so a line read earlier can now answer as never written")
    ses.log_seen_bytes = size
    return note


def e9_since(ses: ds.Session, offset: int, channel: str = "guest") -> tuple[list[str], int]:
    """The complete lines of `channel` after byte `offset`, and the new offset."""
    log = ses.launch.logfile
    assert log is not None            # the caller refuses a session without one
    lines, offset = core_wait.lines_since(log, offset)
    return dlogs.channel_lines(lines, channel), offset


def e9_new_since(ses: ds.Session, offset: int) -> tuple[list[str], int]:
    """The complete instrumentation lines after byte `offset` and the next offset.

    Refuses a log not created yet, unlike `e9_since`, which a wait needs lenient.
    """
    log = require_logfile(ses, "instrumentation channel to summarise")
    if not log.exists():
        raise Invalid("no_channel",
            f"no log at {log}: the guest has not written "
                      f"anything yet, which is not the same as having nothing to say")
    return ses.e9_since(offset)


def e9_since_mark(ses: ds.Session, mark: int) -> list[str]:
    """Every complete instrumentation line after byte `mark`, uncut."""
    require_logfile(ses, "instrumentation channel to look at")
    lines, _ = ses.e9_since(mark)
    return lines


def e9_mark(ses: ds.Session) -> int:
    """The log's current size in bytes, the position `e9_wait(mark=)` starts from.

    The size, not the last newline: finding that would read the whole log, and a mark inside a
    line is right because `e9_since` drops a line begun before the mark.
    """
    log = require_logfile(ses, "instrumentation channel to mark a position in")
    return log.stat().st_size if log.exists() else 0


def e9_wait(ses: ds.Session, pattern: str, seconds: float, mark: int = 0,
            progress: Progress = no_progress,
            advance: stub_link.Advance | None = None) -> dict[str, object]:
    """`log_wait` on the guest channel; `advance` runs a parked machine a retrace per look."""
    if advance is None:
        return ses.log_wait(pattern, seconds, "guest", mark, progress)
    return log_wait(ses, pattern, seconds, "guest", mark, progress, advance)


def _parked_wait(rx: re.Pattern[str], pattern: str, channel: str, seconds: float,
                 fresh: Callable[[], list[str]], advance: stub_link.Advance) -> dict[str, object]:
    """A parked machine run a retrace before each look after the first, until a line matches or
    `seconds` of the GUEST's time have passed, so a replay takes the retraces this one did. A
    host too slow to run them within the longest wait is refused, never read as a miss."""
    began, start = time.monotonic(), advance.clock_ms
    first = fresh()
    total, new = len(first), first
    while True:
        hits = [ln for ln in new if rx.search(ln)]
        if hits:
            return {"verdict": contract.TARGET, "pattern": pattern, "channel": channel,
                    "line": hits[0], "already": new is first, "lines_total": len(hits),
                    "lines_before": total - len(new) + new.index(hits[0]),
                    "arrived_during": total - len(first),
                    "waited_s": round(time.monotonic() - began, 1), "lines_examined": total}
        if advance.clock_ms - start >= seconds * 1000:
            break
        cancel.check()
        if time.monotonic() - began > vocab.WAIT_MAX_S:
            raise Invalid("not_settled",
                f"{seconds:g} s of the guest's time did not pass in {vocab.WAIT_MAX_S:g} s of "
                f"the host's, run a retrace at a time: the wait for /{pattern}/ is no answer")
        advance()
        new = fresh()
        total += len(new)
    arrived = total - len(first)
    return {"verdict": contract.TIMEOUT, "pattern": pattern, "channel": channel,
            "arrived_during": arrived, "lines_examined": total,
            "waited_s": round(time.monotonic() - began, 1),
            "note": f"nothing matched /{pattern}/ in {seconds:g} s of the guest's time, run a "
                    f"retrace at a time: {counted(arrived, 'line')} arrived during the wait. The "
                    f"machine is stopped where the wait ended"}


def log_wait(ses: ds.Session, pattern: str, seconds: float, channel: str, mark: int = 0,
             progress: Progress = no_progress,
             advance: stub_link.Advance | None = None) -> dict[str, object]:
    """WHEN a line of `channel` matching `pattern` happened (`scry_core.log_wait`).

    `verdict` is `TARGET` with the FIRST such line, or `TIMEOUT`; a stopped machine writes
    nothing, so waiting on one is refused (`E9Stopped`), as is a vanished emulator, unless
    `advance` runs it, bounded by the guest's own time (`_parked_wait`). `mark` (`e9_mark`) makes
    "already" mean "written since the mark".
    """
    vocab.check_wait(seconds)
    rx = judges.regex("pattern", pattern)
    dlogs.check_channel(channel)
    # A log absent or empty of instrumentation is normal for a just-resumed guest.
    require_logfile(ses, "instrumentation channel to wait on, and waiting cannot "
                    "bring one into existence")
    offset = mark

    def fresh() -> list[str]:
        nonlocal offset
        lines, offset = ses.e9_since(offset, channel)
        return lines

    if advance is not None:
        return _parked_wait(rx, pattern, channel, seconds, fresh, advance)
    asked: list[bool] = []
    silent: list[Invalid] = []

    def stopped() -> bool:
        # Each question to a silent channel costs its whole bound, so asking at every look
        # would run the wait far past its own: once silent, the file alone is read.
        if silent:
            return False
        try:
            at = ses.at_debugger()
        except Invalid as e:
            # A channel busy in a long host call (a guest stuck in FindFirst) is not a stop.
            if e.code == "host_failed":
                silent.append(e)
                return False
            raise
        asked.append(at)
        return at

    got = core_wait.wait(rx, fresh, seconds=seconds, stopped=stopped,
                         alive=ses.alive, progress=progress,
                         label=f"log_wait {channel} /{pattern}/")
    if isinstance(got, core_wait.Found):
        return {"verdict": contract.TARGET, "pattern": pattern, "channel": channel,
                **got.fields()}
    if got.ending == "STOPPED":
        raise ds.wait_stopped(pattern, got.arrived_during, got.waited_s,
                               parked=asked[:1] == [True], at_bound=got.at_bound)
    if got.ending == "GONE":
        raise Invalid("session_broken", core_wait.gone_message(pattern, got, seconds))
    region = "in the log altogether" if mark == 0 else f"since the mark at byte {mark}"
    run_state = core_wait.STILL_RUNNING
    if silent:
        why = (silent[0].silence if isinstance(silent[0], control.ChannelSilent)
               else "the debugger channel did not answer when asked")
        run_state = (f"Whether the machine is running or stopped is not known: {why}, and "
                     f"{control.UNTIL_IT_ENDS}")
    note = core_wait.timeout_note(pattern, got, region, "guest", run_state=run_state)
    return {"verdict": contract.TIMEOUT, "pattern": pattern, "channel": channel,
            "arrived_during": got.arrived_during, "lines_examined": got.lines_examined,
            "waited_s": got.waited_s, "note": note}

