"""The log a session reads: the guest's E9 channel and the emulator's own lines, which channel a
line is on, and how a caller filters and counts them."""

from __future__ import annotations

import re

from scry_core import vocabulary as vocab
from scry_core.reply_contract import Invalid

# A live line of the guest's Bochs 0xE9 instrumentation, as DOSBox-X logs it.
E9_LINE = re.compile(r"^Bochs port E9h: ")


# THE CHANNELS OF THE ONE LOG FILE. DOSBox-X writes the guest's E9 lines and its own log
# lines (the categories its `log` section names) into the same file, so a channel is a
# SELECTION of that file: `guest` (the E9 lines), `emulator` (every other line), `all` (the
# file in order, each line tagged with its source). There is no `process` channel for the
# emulator's stdout, because this emulator's stdout is the debugger's own terminal and
# not a log.
LOG_CHANNELS = ("guest", "emulator", "all")


def compiled(pattern: str) -> re.Pattern[str]:
    """A caller's pattern, or the refusal that says it is THEIRS and not the guest's.

    ONE function because two readers take a pattern, and a message duplicated across
    both is how they drift: the second copy gets reworded, the two refusals stop
    agreeing, and nothing fails while they do it. The refusal has to say whose pattern
    is at fault, so it is worth exactly one definition.
    """
    try:
        return re.compile(pattern)
    except re.error as e:
        raise Invalid("bad_argument", f"that is not a usable pattern: {e}") from None


def count_e9(text: str) -> int:
    """How many instrumentation lines this log holds AT ALL, whatever the pattern.

    It is what lets the two nothings be told apart. A log with instrumentation in it
    and no line matching your pattern is an ANSWER; a log with none at all is a
    statement about the build or about how far the guest has got, and reporting it as
    an empty result is how a silent channel gets read as a clean one.
    """
    return sum(1 for ln in text.splitlines() if E9_LINE.match(ln))


def check_channel(channel: str) -> None:
    vocab.one_of("channel", channel, LOG_CHANNELS, ". There is no `process` channel: the "
                 "emulator's stdout is the debugger's own terminal (`debug` reads it) and not a "
                 "log")


def channel_of(line: str) -> str:
    """Which channel a line of the log belongs to: the guest's E9 prefix decides."""
    return "guest" if E9_LINE.match(line) else "emulator"


def channel_lines(lines: list[str], channel: str) -> list[str]:
    """The lines of `channel`, in order; for `all`, every line tagged `[guest] ` or
    `[emulator] ` so the reader knows the source of each without a second call."""
    if channel == "all":
        return [f"[{channel_of(ln)}] {ln}" for ln in lines]
    return [ln for ln in lines if channel_of(ln) == channel]


def label_counts(lines: list[str]) -> dict[str, int]:
    """How many lines carry each LABEL, the guest's own first word: what a program
    writes at the head of every trace (`BOOT`, `PERF`, `UI`) once the E9 prefix, a source
    tag and a bracketed stamp (`[+   0.000]`) are stepped over. One glance says who is
    talking; the `pattern` still selects."""
    counts: dict[str, int] = {}
    for ln in lines:
        payload = E9_LINE.sub("", re.sub(r"^\[(guest|emulator)\] ", "", ln))
        payload = re.sub(r"^\[[^\]]*\]\s*", "", payload)
        words = payload.split()
        if words:
            counts[words[0]] = counts.get(words[0], 0) + 1
    return counts


def log_hits(text: str, pattern: str, channel: str) -> list[str]:
    """EVERY matching line of `channel`, in order: the reader the server's own reductions
    (the stop reply's E9 block) build on, which need the whole channel and carry no
    caller's limit; `check_e9_limit` binds the caller-facing readers only."""
    rx = compiled(pattern)
    check_channel(channel)
    return [ln for ln in channel_lines(text.splitlines(), channel) if rx.search(ln)]


def filter_log(text: str, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
    """(the newest `limit` matching lines of `channel`, HOW MANY matched in total): the
    reader behind `log`, with `filter_e9` as its guest-channel spelling."""
    check_e9_limit(limit)
    hits = log_hits(text, pattern, channel)
    return hits[-limit:], len(hits)


def filter_e9(text: str, pattern: str, limit: int) -> tuple[list[str], int]:
    """(the newest `limit` matching lines, HOW MANY matched in total).

    THE TOTAL IS RETURNED SEPARATELY because the two are different answers: reporting
    the length of the slice under the name `matched` would hand a caller asking "how
    many times did this fire" the limit back, with no way to tell a genuine 40 from a
    truncated 5000.

    THE GUARD IS ON THE CHANNEL, not on the content: a line counts only when it IS an
    instrumentation line, never when it merely quotes one. A build log naming
    `src/loudness.c`, or a tool's report echoing a trace back, contains the words
    without being the thing.

    The tail is kept rather than the head, deliberately: the recent state is what a
    question is about, and a head slice answers with the boot every time.
    """
    return filter_log(text, pattern, limit, "guest")


# THE CEILING ON A LOG READ: a guard that calls the whole log "the haystack this exists to
# stop carrying" and then takes `limit=1000000` has allowed the same haystack with a number
# on it. Above this, narrow the pattern.
LOG_LIMIT_MAX = 400


def check_e9_limit(limit: object) -> None:
    """THE ONE JUDGE OF A LOG READ'S `limit`, `log`'s and `drive`'s look."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise Invalid("bad_argument", f"limit is a count of lines; got {limit!r}")
    if limit <= 0:
        raise Invalid("bad_argument",
            "a limit of zero or less would return the whole log, which is "
                      "the haystack this exists to stop carrying. Ask for a number "
                      "of lines")
    if limit > LOG_LIMIT_MAX:
        raise Invalid("bad_argument",
            f"limit={limit} is outside 1..{LOG_LIMIT_MAX}: above that the reply is the "
                      f"haystack again. Narrow the pattern instead")
