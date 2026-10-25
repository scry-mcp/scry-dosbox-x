"""The session log: E9 and emulator channels, and how a caller filters and counts them."""

from __future__ import annotations

import re

from scry_core import vocabulary as vocab
from scry_core.reply_contract import Invalid

E9_LINE = re.compile(r"^Bochs port E9h: ")


# Guest E9 lines and emulator log lines share one file, so a channel is a selection of it.
LOG_CHANNELS = ("guest", "emulator", "all")


def compiled(pattern: str) -> re.Pattern[str]:
    """A caller's pattern, or a refusal naming it as theirs."""
    try:
        return re.compile(pattern)
    except re.error as e:
        raise Invalid("bad_argument", f"that is not a usable pattern: {e}") from None


def check_pattern(pattern: str) -> None:
    """A log tool's pattern: non-empty, as `drive`'s, and compiling."""
    if not pattern:
        raise Invalid("bad_argument",
                      "pattern is a non-empty regular expression ('.' for every line)")
    compiled(pattern)


def count_e9(text: str) -> int:
    """E9 lines in the log, whatever the pattern: tells "no match" from a silent channel."""
    return sum(1 for ln in text.splitlines() if E9_LINE.match(ln))


def check_channel(channel: str) -> None:
    vocab.one_of("channel", channel, LOG_CHANNELS, ". There is no `process` channel: the "
                 "emulator's stdout is the debugger's own terminal (`debug` reads it) and not a "
                 "log")


def channel_of(line: str) -> str:
    """Guest if the E9 prefix matches, else emulator."""
    return "guest" if E9_LINE.match(line) else "emulator"


def channel_lines(lines: list[str], channel: str) -> list[str]:
    """The lines of `channel`; `all` tags each `[guest] ` or `[emulator] `."""
    if channel == "all":
        return [f"[{channel_of(ln)}] {ln}" for ln in lines]
    return [ln for ln in lines if channel_of(ln) == channel]


def label_counts(lines: list[str]) -> dict[str, int]:
    """Lines per label: the first word after the prefix, tag and stamp."""
    counts: dict[str, int] = {}
    for ln in lines:
        payload = E9_LINE.sub("", re.sub(r"^\[(guest|emulator)\] ", "", ln))
        payload = re.sub(r"^\[[^\]]*\]\s*", "", payload)
        words = payload.split()
        if words:
            counts[words[0]] = counts.get(words[0], 0) + 1
    return counts


def log_hits(text: str, pattern: str, channel: str) -> list[str]:
    """Every matching line of `channel`, with no limit."""
    rx = compiled(pattern)
    check_channel(channel)
    return [ln for ln in channel_lines(text.splitlines(), channel) if rx.search(ln)]


def filter_log(text: str, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
    """(the newest `limit` matching lines of `channel`, total matched)."""
    check_e9_limit(limit)
    hits = log_hits(text, pattern, channel)
    return hits[-limit:], len(hits)


def filter_e9(text: str, pattern: str, limit: int) -> tuple[list[str], int]:
    """(the newest `limit` matching guest lines, total matched); the tail, not the boot."""
    return filter_log(text, pattern, limit, "guest")


LOG_LIMIT_MAX = 400


def check_e9_limit(limit: object) -> None:
    """Judge a log read's `limit` for `log` and `drive`."""
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
