"""The session's two log channels, read: the guest's E9 stream off the log file and the
emulator's own lines, each since a mark, filtered, or waited for. Its own module because what a
log holds and how it is waited on change for reasons of their own; each function is a
session method's body, and `Session` delegates to it."""

from __future__ import annotations

import time

from scry_core import cancel
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


def _log_text(ses: ds.Session) -> str:
    """The log file, or the refusal that says which nothing: no logfile on the
    session, or a file the emulator has not created yet."""
    if ses.launch.logfile is None:
        raise Invalid("no_channel", "this session was started without a logfile, so there is "
                      "no log channel to filter")
    if not ses.launch.logfile.exists():
        raise Invalid("no_channel", f"no log at {ses.launch.logfile}: the emulator has not "
                      f"written anything yet, which is not the same as having "
                      f"nothing to say")
    return ses.launch.logfile.read_text(encoding="utf-8", errors="replace")


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
    """The COMPLETE lines of `channel` after byte `offset`, and the new offset.

    THREE DEFECTS DIE WITH THIS, and they were all one defect: the wait used to
    re-read the whole file and index it by LINE NUMBER.

    A HALF-WRITTEN LINE STOPS BEING A LINE. A log written through ordinary stdio
    ends MID-LINE between flushes -- that is the steady state while a writer is
    producing, not a rare race -- and `splitlines()` hands that fragment back as an
    element. `E9_LINE` matches it, because it only anchors the prefix. So the
    fragment CONSUMED A LINE INDEX, and when the rest of the line arrived the count
    did not grow: the completed line was never tested again. MEASURED, the caller
    got "a bound that expired" for a line that was sitting in the file, and `e9` on
    the same file found it. The mirror was as bad: when the fragment did match, it
    was returned as the guest's trace with its payload missing. Cutting at the last
    newline means a line is only ever seen whole, once.

    AND IT IS WHY THE COST IS BOUNDED. Re-reading the whole file every tenth of a
    second was MEASURED on a log of a few megabytes: gigabytes read and over a minute
    of CPU inside a ten-minute wait, with the server's lock held, growing
    quadratically as the log grows under it. Reading only what is new is the same
    answer for the size of the new part.

    A LOG THAT HAS SHRUNK IS REFUSED rather than resynchronised. Truncation or
    rotation makes every byte offset meaningless, and the two ways to carry on are
    both wrong: keeping the offset silently stops seeing anything, and resetting it
    re-reports old lines as new. It is rare and it is nameable, so it is named.
    """
    log = ses.launch.logfile
    assert log is not None            # the caller refuses a session without one
    if not log.exists():
        # NOT AN ERROR HERE. The guest may not have written yet, which is exactly
        # what a wait is for; `e9` refuses on this and this deliberately does not.
        return [], offset
    size = log.stat().st_size
    if size < offset:
        raise Invalid("session_broken",
            f"{log} has SHRUNK from {offset} bytes to {size} while this was "
            f"waiting: it was truncated or rotated underneath. Every offset into "
            f"it is now meaningless, and both ways of carrying on are wrong -- "
            f"keeping it sees nothing more, resetting it reports old lines as new")
    with log.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read()
    cut = chunk.rfind(b"\n") + 1
    if cut == 0:
        return [], offset
    # DECODED ONLY UP TO A NEWLINE, which is also what keeps a multi-byte character
    # from being split across two reads: `\n` is a byte boundary in UTF-8, so the
    # consumed prefix is always whole characters.
    text = chunk[:cut].decode("utf-8", errors="replace")
    return (dlogs.channel_lines(text.splitlines(), channel), offset + cut)


def e9_new_since(ses: ds.Session, offset: int) -> tuple[list[str], int]:
    """The complete instrumentation lines after byte `offset` and the offset to read
    from next: the stop survey's reader, so a stop pays for what the guest wrote since
    the previous one and not for the whole log again. It refuses what `e9` refuses: a
    session with no logfile has no channel, and a log the guest has not created yet
    cannot be looked at, which is not zero lines. The wait's reader keeps its own
    reading of an absent log, because nothing yet is what a wait is for."""
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
            "this session was started without a logfile, so there is no "
                      "instrumentation channel to summarise")
    if not ses.launch.logfile.exists():
        raise Invalid("no_channel",
            f"no log at {ses.launch.logfile}: the guest has not written "
                      f"anything yet, which is not the same as having nothing to say")
    return ses._e9_since(offset)


def e9_since_mark(ses: ds.Session, mark: int) -> list[str]:
    """Every complete instrumentation line written after byte `mark`, in order: the
    LOOK after an act. A session with no logfile has no channel; a log that has not
    appeared yet answers nothing, which is an answer about the window. The count is
    bounded by what the guest wrote, not by a limit here: the caller cuts."""
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
            "this session was started without a logfile, so there is no "
                      "instrumentation channel to look at")
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
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
            "this session was started without a logfile, so there is no "
                      "instrumentation channel to mark a position in")
    log = ses.launch.logfile
    return log.stat().st_size if log.exists() else 0


def e9_wait(ses: ds.Session, pattern: str, seconds: float, mark: int = 0,
            progress: Progress = no_progress) -> dict[str, object]:
    """`log_wait` on the guest channel: the wait `expect` and `drive` rest on."""
    return ses.log_wait(pattern, seconds, "guest", mark, progress)


def log_wait(ses: ds.Session, pattern: str, seconds: float, channel: str, mark: int = 0,
             progress: Progress = no_progress) -> dict[str, object]:
    """WHEN a line of `channel` matching `pattern` happened -- whether it already has,
    or not yet.
    While it waits it reports the seconds spent, and the lines that arrived, through
    `progress`.

    `mark` is the byte position the search starts from (`e9_mark`): with it, "already"
    means "written since the mark", and everything before the mark is invisible. That
    is the difference between "the cue has fired at some point" and "the cue fired in
    response to the key just posted", and it is the whole of what `send_keys`'
    verification rests on.

    BOTH SEMANTICS, IN ONE TOOL, and that is the whole design rather than a
    convenience. Between launching the emulator and asking, the thing you are
    waiting for may ALREADY have gone past; a tool that only waits would then sit
    out its whole bound and report that it never happened, which is false and
    expensive. So this looks at what the log already holds FIRST, and only waits if
    it has to. `already` says which of the two answers you got, because they mean
    different things: one is history, the other is something you were present for.

    WHICH OCCURRENCE: the FIRST. The question this answers is "when did it happen",
    and for a line that fired more than once the first time is the answer;
    `lines_total` says how many there were, so a caller who wanted the latest knows
    there is one. (`e9` is the tool for the recent state -- it keeps the newest.)

    A BOUND THAT EXPIRES IS INVALID, never an empty answer, and the message says
    what was examined: how long it watched, how many instrumentation lines went by,
    and that the channel was there. A caller who asked "wait for X" and got "no
    lines" cannot tell "X did not happen in this window" from "there was nothing to
    match against", and this package refuses to print the same thing for both.

    WHAT YOU CAN DO WITH THE MOMENT, and it is narrower than it looks. A guest
    writing traces is a guest that is RUNNING, so ordinarily the machine is still
    running when this returns from a wait, and this debugger's console does not
    accept commands then -- which every reader here demonstrates by refusing. So you
    ordinarily cannot arm a breakpoint at the moment this hands you, and you must
    ASK rather than assume: a breakpoint armed earlier can fire between the line
    being written and the poll that reads it, and this reply carries no `running`
    field. The reason is the CONSOLE and not dosbox-x #4026, which is about breaking
    in with a host keypress -- a different path, and one `breakpoint_interrupt`
    records as MEASURED working. What the moment is for: choosing an address to arm
    on the NEXT run, before the machine is released.
    """
    ds.check_wait_bound(seconds)
    rx = dlogs.compiled(pattern)
    dlogs.check_channel(channel)
    kind = "instrumentation" if channel == "guest" else channel
    # THE ONLY REFUSAL THAT SURVIVES THE WAIT, and `e9`'s other two deliberately do
    # not. A session with no logfile has no channel and waiting cannot create one.
    # But a log that does not EXIST yet, and a log with no instrumentation IN it,
    # are the ordinary state of a guest that has just been resumed -- and `e9`
    # refuses on both. Lifting all three would make this tool unable to wait for the
    # guest's FIRST trace: MEASURED, `start` then `resume` then `e9_wait("BOOT")`
    # refuses at once against its bound, for a line that arrives a fraction of a
    # second later, while `_e9_text`'s own message names that very case ("the guest
    # has not reached its first trace yet"). The two states are reported in the
    # expiry instead, where they are an ANSWER about the window.
    if ses.launch.logfile is None:
        raise Invalid("no_channel",
            "this session was started without a logfile, so there is no "
                      "instrumentation channel to wait on, and waiting cannot "
                      "bring one into existence")
    began = time.monotonic()
    lines, offset = ses._e9_since(mark, channel)
    total = len(lines)

    # EVERY COUNT IS "SINCE THE MARK", and the field says so by its name. With the
    # default mark the examined region is the whole log; with a mark it is what was
    # written after it, and a field called `lines_in_log` then lied by exactly the
    # lines before the mark. `since_mark` rides along so a reader can tell which.
    def found(hit: list[str], already: bool, before: int) -> dict[str, object]:
        # `lines_before` is how many lines sit between the mark and the match: a
        # reaction that landed AFTER a post (the mark is taken before it) shows as such,
        # which `already` alone cannot say -- from a mark, `already` means "there when
        # the wait first looked", history or not.
        return {"line": hit[0], "already": already, "lines_total": len(hit),
                "lines_before": before, "arrived_during": total - len(lines),
                "waited_s": 0.0 if already else round(time.monotonic() - began, 3),
                "lines_examined": total, "since_mark": mark}

    def last_look() -> dict[str, object] | None:
        """ONE LAST READ BEFORE ANY REFUSAL FROM INSIDE THE WAIT, the same for all three
        (gone, stopped, expired): the loop checks the condition FIRST and reads LAST, so a
        line written after the final read and before the condition was never looked for
        -- the canonical case being a guest's EXIT trace, written on its way out, and for
        a stop the reaction logged just before the breakpoint on its handler fired."""
        nonlocal offset, total
        fresh, offset = ses._e9_since(offset, channel)
        total += len(fresh)
        hit = [ln for ln in fresh if rx.search(ln)]
        return found(hit, False, total - len(fresh) + fresh.index(hit[0])) if hit else None

    hits = [ln for ln in lines if rx.search(ln)]
    if hits:
        return found(hits, True, lines.index(hits[0]))
    deadline = began + seconds
    next_tick = began + ds.PROGRESS_EVERY_S
    newest = ""
    while (now := time.monotonic()) < deadline:
        cancel.check()
        if now >= next_tick:
            next_tick = now + ds.PROGRESS_EVERY_S
            progress(now - began, None,
                     f"log_wait {channel} /{pattern}/: {now - began:.0f}s of "
                     f"{seconds:g}s, {total - len(lines)} lines arrived"
                     + (f", last: {newest[:ds.LAST_LINE_SHOWN]}" if newest else ""))
        # A STOPPED GUEST WRITES NOTHING, so a wait on one cannot end well and its
        # expiry would blame the program. MEASURED: a breakpoint
        # from another session parked the guest mid-plan and this sat out 40 s to say
        # "the emulator is still running". Asked every poll, because a breakpoint can
        # fire during the wait too; the answer is passive (no console round trip).
        if ses.at_debugger():
            if (late := last_look()) is not None:
                return late
            raise ds._wait_stopped(pattern, total - len(lines),
                                round(time.monotonic() - began, 3))
        # THE DEATH IS CHECKED IN THE LOOP, not once in the message at the end.
        # Consulted only while composing the refusal, a session that died at the
        # start would burn the WHOLE bound, with the server's lock held so `status`
        # could not be asked, before saying so, and then advise asking again with a
        # longer bound, which is the one thing that cannot help a dead emulator.
        if not ses.alive():
            # ONE LAST READ BEFORE REFUSING, and the refusal's own next sentence is
            # why it must happen: nothing more WILL be written, so this is the last
            # chance to read what already was. The loop checks `alive()` FIRST and
            # reads LAST, so a line written after the final read and before the
            # death was never looked for at all -- and that is the canonical case,
            # waiting for a guest's exit trace. MEASURED against a double whose
            # guest writes its trace on the way out: the line was sitting unread in
            # the log at the instant of refusal, and `e9` on the same log found it.
            if (late := last_look()) is not None:
                return late
            raise Invalid("session_broken",
                f"the emulator is GONE, {round(time.monotonic() - began, 1)}s into "
                f"a {seconds}s wait for {pattern!r}, and a final read of the log "
                f"after it died found nothing matching either. Nothing more will "
                f"be written, so a longer bound would not help: this needs a new "
                f"session, not a bigger number")
        time.sleep(ds.E9_POLL)
        fresh, offset = ses._e9_since(offset, channel)
        total += len(fresh)
        newest = fresh[-1].strip() if fresh else newest
        seen = [ln for ln in fresh if rx.search(ln)]
        if seen:
            return found(seen, False, total - len(fresh) + fresh.index(seen[0]))
    # AND ONE LAST READ HERE TOO, for the same reason on the other path: the loop
    # leaves on the CLOCK, so whatever the guest wrote between the final poll and
    # the deadline -- up to a whole `E9_POLL` -- had never been looked for. The
    # window is small and the answer it holds is exactly the one being waited for.
    if (late := last_look()) is not None:
        return late
    # THE COUNT IS THE ONE THAT ANSWERS THE QUESTION BEING ASKED. The log's TOTAL under
    # the words "went past" would make a wait during which NOTHING happened, on a log
    # carrying five thousand earlier traces, say "5000 instrumentation line(s) went
    # past", which anyone diagnosing a silent guest reads as a live channel. The two
    # numbers are different facts and both are given, and the second one is named for
    # the region it counts, since with a mark the examined region is not the log.
    during = total - len(lines)
    # THE EXPIRY ASKS TOO. The loop asks at every poll, so a stop it sees refuses at once;
    # a stop that lands after the last poll and before the clock would otherwise reach
    # a refusal saying "The emulator is still running" (the PROCESS) while the debugger
    # held the machine. Passive, like the loop's.
    if ses.at_debugger():
        raise ds._wait_stopped(pattern, during, round(time.monotonic() - began, 3), seconds)
    region = "in the log altogether" if mark == 0 else f"since the mark at byte {mark}"
    # HOISTED OUT OF THE f-STRING because a line break inside a replacement field is
    # 3.12 syntax and this package targets 3.11 -- `ruff` caught it, `mypy` did not.
    silent = ("" if during else
              " The guest wrote NOTHING at all in this window, so the question may "
              "be whether it is still emitting rather than what it emitted.")
    raise ds.E9Expired(
        f"nothing matched {pattern!r} in {round(time.monotonic() - began, 1)}s. "
        f"{during} {kind} line(s) arrived DURING the wait ({total} "
        f"{region}), so this is a bound that expired and not 'there was "
        f"nothing to match against'.{silent} The emulator is still running. Asking "
        f"again with a longer bound is a different question from asking whether "
        f"the line ever appears")
