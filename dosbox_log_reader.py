from __future__ import annotations

from pathlib import Path

from scry_core import log_marks
from scry_core import log_wait as core_wait
from scry_core import reply_contract as contract
from scry_core import vocabulary as vocab
from scry_core.progress import Progress, no_progress
from scry_core.reply_contract import Invalid

import dosbox_logs as dlogs
import dosbox_session as ds


def e9(ses: ds.Session, pattern: str, limit: int = 40) -> tuple[list[str], int]:
    """The guest's E9 lines matching `pattern`, filtered at the source."""
    return dlogs.filter_e9(ses._e9_text(), pattern, limit)


def log(ses: ds.Session, pattern: str, limit: int, channel: str,
        since_mark: int = 0) -> tuple[list[str], int]:
    """The log's `channel` filtered; with `since_mark`, only whole lines written after it."""
    dlogs.check_channel(channel)
    if since_mark:
        if channel == "guest":
            ses._e9_text()
        lines, _ = core_wait.lines_since(log_file_from(ses, since_mark, channel), since_mark)
        return dlogs.filter_log("\n".join(lines), pattern, limit, channel)
    if channel == "guest":
        return dlogs.filter_e9(ses._e9_text(), pattern, limit)
    return dlogs.filter_log(ses._log_text(), pattern, limit, channel)


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


def _log_text(ses: ds.Session) -> str:
    """The log text, or `no_channel` if there is no log yet."""
    log = require_logfile(ses, "log channel to filter")
    if not log.exists():
        raise Invalid("no_channel", f"no log at {log}: the emulator has not "
                      f"written anything yet, which is not the same as having "
                      f"nothing to say")
    return log.read_text(encoding="utf-8", errors="replace")


def _e9_text(ses: ds.Session) -> str:
    """The instrumentation log; no instrumentation at all is `no_channel`, not "no match"."""
    text = ses._log_text()
    if dlogs.count_e9(text) == 0:
        raise Invalid("no_channel",
            f"{ses.launch.logfile} carries no instrumentation at all. That is "
            f"not 'your pattern matched nothing', it is 'there is nothing to "
            f"match': either the guest has not reached its first trace yet, or "
            f"this build does not emit any")
    return text


def _e9_since(ses: ds.Session, offset: int, channel: str = "guest") -> tuple[list[str], int]:
    """The complete lines of `channel` after byte `offset`, and the new offset."""
    log = ses.launch.logfile
    assert log is not None            # the caller refuses a session without one
    lines, offset = core_wait.lines_since(log, offset)
    return dlogs.channel_lines(lines, channel), offset


def e9_new_since(ses: ds.Session, offset: int) -> tuple[list[str], int]:
    """The complete instrumentation lines after byte `offset` and the next offset.

    Refuses a log not created yet, unlike `_e9_since`, which a wait needs lenient.
    """
    log = require_logfile(ses, "instrumentation channel to summarise")
    if not log.exists():
        raise Invalid("no_channel",
            f"no log at {log}: the guest has not written "
                      f"anything yet, which is not the same as having nothing to say")
    return ses._e9_since(offset)


def e9_since_mark(ses: ds.Session, mark: int) -> list[str]:
    """Every complete instrumentation line after byte `mark`, uncut."""
    require_logfile(ses, "instrumentation channel to look at")
    lines, _ = ses._e9_since(mark)
    return lines


def e9_mark(ses: ds.Session) -> int:
    """The log's current size in bytes, the position `e9_wait(mark=)` starts from.

    The size, not the last newline: finding that would read the whole log, and a mark inside a
    line is right because `_e9_since` drops a line begun before the mark.
    """
    log = require_logfile(ses, "instrumentation channel to mark a position in")
    return log.stat().st_size if log.exists() else 0


def e9_wait(ses: ds.Session, pattern: str, seconds: float, mark: int = 0,
            progress: Progress = no_progress) -> dict[str, object]:
    """`log_wait` on the guest channel."""
    return ses.log_wait(pattern, seconds, "guest", mark, progress)


def log_wait(ses: ds.Session, pattern: str, seconds: float, channel: str, mark: int = 0,
             progress: Progress = no_progress) -> dict[str, object]:
    """WHEN a line of `channel` matching `pattern` happened (`scry_core.log_wait`).

    `verdict` is `TARGET` with the FIRST such line, or `TIMEOUT`; a stopped machine writes
    nothing, so waiting on one is refused (`E9Stopped`), as is a vanished emulator. `mark`
    (`e9_mark`) makes "already" mean "written since the mark".
    """
    vocab.check_wait(seconds)
    rx = dlogs.compiled(pattern)
    dlogs.check_channel(channel)
    # A log absent or empty of instrumentation is normal for a just-resumed guest.
    require_logfile(ses, "instrumentation channel to wait on, and waiting cannot "
                    "bring one into existence")
    offset = mark

    def fresh() -> list[str]:
        nonlocal offset
        lines, offset = ses._e9_since(offset, channel)
        return lines

    asked: list[bool] = []

    def stopped() -> bool:
        asked.append(ses.at_debugger())
        return asked[-1]

    got = core_wait.wait(rx, fresh, seconds=seconds, stopped=stopped,
                         alive=ses.alive, progress=progress,
                         label=f"log_wait {channel} /{pattern}/")
    if isinstance(got, core_wait.Found):
        return {"verdict": contract.TARGET, "pattern": pattern, "channel": channel,
                **got.fields()}
    if got.ending == "STOPPED":
        raise ds._wait_stopped(pattern, got.arrived_during, got.waited_s,
                               parked=asked[:1] == [True], at_bound=got.at_bound)
    if got.ending == "GONE":
        raise Invalid("session_broken", core_wait.gone_message(pattern, got, seconds))
    region = "in the log altogether" if mark == 0 else f"since the mark at byte {mark}"
    return {"verdict": contract.TIMEOUT, "pattern": pattern, "channel": channel,
            "arrived_during": got.arrived_during, "lines_examined": got.lines_examined,
            "waited_s": got.waited_s,
            "note": core_wait.timeout_note(pattern, got, region, "guest")}
