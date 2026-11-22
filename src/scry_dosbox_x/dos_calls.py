"""The `dos` channel of `log` and `log_wait`: every INT 21h the guest made since `start`, as the
debugger's `DOSTRACE` records it, one row as DOS takes a call and one as DOS hands it back,
paired here by number into a call with its result (`docs/reference/machine.md`, `log`)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scry_core import judges, prose
from scry_core import log_wait as core_wait
from scry_core.progress import Ticker
from scry_core.reply_contract import Invalid

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import knowledge
from scry_dosbox_x import logs as dlogs
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as st
from scry_dosbox_x.state import STATE

DOSTRACE = "DOSTRACE"
CHANNEL = "dos"
STATUS_LINE = re.compile(r"^DEBUG: DOSTRACE (ON|OFF) CALLS=(\d+) ROWS=(\d+) DROPPED=(\d+) "
                         r"FILE=(.+)$")
ENTRY = re.compile(r"^E N=(\d+) T=([0-9.]+) M=([RVP]) CS=([0-9A-F]{4}) IP=([0-9A-F]{4}) "
                   r"PSP=([0-9A-F]{4}) AX=([0-9A-F]{4}) BX=([0-9A-F]{4}) CX=([0-9A-F]{4}) "
                   r"DX=([0-9A-F]{4}) SI=([0-9A-F]{4}) DI=([0-9A-F]{4}) DS=([0-9A-F]{4}) "
                   r"ES=([0-9A-F]{4}) NAME=(.*)$")
RETURN = re.compile(r"^R N=(\d+) T=([0-9.]+) AX=([0-9A-F]{4}) BX=([0-9A-F]{4}) "
                    r"CX=([0-9A-F]{4}) DX=([0-9A-F]{4}) CF=([01]) SWITCHED=([01])$")
CAP = re.compile(r"^X ROWS_MAX=(\d+)$")
MODES = {"R": "real", "V": "v86", "P": "protected"}

#: The first function that reports failure by the carry: older ones answer in AL.
CARRY_ERA = 0x38
POLL_S = 0.05
#: How many patterns a trace remembers the matches of.
PATTERNS_KEPT = 8
#: How many calls the server holds: past it the oldest go, so a chatty program cannot grow the
#: server without bound.
CALLS_KEPT = 50_000
#: How much of the file one parse takes, so the window is enforced between slices.
CHUNK_BYTES = 4 << 20


@dataclass
class Trace:
    """What has been read of one session's trace file, so a read parses only what is new."""

    path: Path
    offset: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)
    by_n: dict[int, dict[str, Any]] = field(default_factory=dict)
    capped: int | None = None
    #: How many calls from the front have gone past `CALLS_KEPT`; `n` stays the file's number.
    dropped: int = 0
    partial: bytes = b""
    #: How many calls from the front have their `line`; a returned call's is set at its return.
    rendered: int = 0
    #: The refusal of the first row of no known shape, kept because the read that met it had
    #: already moved `offset` past the rest of its chunk.
    broken: str | None = None
    #: Per pattern: how many calls from the front are final (returned), and the matches among them.
    matched: dict[str, tuple[int, list[dict[str, Any]]]] = field(default_factory=dict)


def function_name(ah: int) -> str:
    """What INT 21h function `ah` is called in the base, or its number when the base holds no
    confirmed entry for it."""
    named = knowledge.base().get("call", f"0x21/0x{ah:02X}", knowledge.SCOPE)
    return named.name if named is not None else f"0x{ah:02X}"


def error_name(code: int) -> str:
    """What DOS error `code` is called in the base, or its number when the base holds no
    confirmed entry for it."""
    named = knowledge.base().get("error", str(code), knowledge.SCOPE)
    return named.name if named is not None else str(code)


def _regs(names: tuple[str, ...], values: tuple[str, ...]) -> dict[str, str]:
    return {n: f"0x{v}" for n, v in zip(names, values, strict=True)}


def _seconds(ms: str) -> float:
    """`T=` is the emulator's `PIC_FullIndex()`, in milliseconds."""
    return float(ms) / 1000


def _render(call: dict[str, Any]) -> str:
    """The call as one line, which `pattern` is matched against."""
    file = f" {call['file']}" if call.get("file") else ""
    if not call["returned"]:
        result = "no return yet"
    elif call["switched"]:
        result = "did not return to its caller"
    elif "error" in call:
        result = f"error {_named(call['error']['code'], call['error']['name'])}"
    else:
        result = f"AX={call['out']['ax']}"
    return (f"#{call['n']} {call['caller']} psp {call['psp']} "
            f"{_named(call['function'], call['name'])}{file} -> {result}")


def _named(number: object, name: str) -> str:
    """`number name`, or the number alone when it stands for its own name."""
    return str(number) if name == str(number) else f"{number} {name}"


def _entry(found: re.Match[str]) -> dict[str, Any]:
    g = found.groups()
    ah = int(g[6][:2], 16)
    call: dict[str, Any] = {
        "n": int(g[0]), "time_s": _seconds(g[1]), "cpu_mode": MODES[g[2]],
        "caller": f"{g[3]}:{g[4]}", "psp": f"0x{g[5]}", "function": f"0x{ah:02X}",
        "name": function_name(ah),
        "in": _regs(("ax", "bx", "cx", "dx", "si", "di", "ds", "es"), g[6:14]),
        "returned": False, "switched": False,
    }
    if g[14]:
        call["file"] = g[14]
    return call


def _returned(call: dict[str, Any], found: re.Match[str]) -> None:
    g = found.groups()
    call["returned"], call["switched"] = True, g[7] == "1"
    call["returned_s"] = _seconds(g[1])
    if call["switched"]:
        # The registers and carry are of whatever runs now (a parent, an EXEC's child).
        return
    call["out"] = {**_regs(("ax", "bx", "cx", "dx"), g[2:6]), "cf": int(g[6])}
    ah = int(call["function"], 16)
    if call["out"]["cf"] and ah >= CARRY_ERA:
        code = int(g[2], 16)
        call["error"] = {"code": code, "name": error_name(code)}


def read(trace: Trace) -> Trace:
    """Parse what the file gained since the last read, a slice at a time, so the window holds
    however much the guest wrote while nobody asked."""
    if trace.broken is not None:
        raise Invalid("unexpected_answer", trace.broken)
    try:
        with trace.path.open("rb") as f:
            f.seek(trace.offset)
            while chunk := f.read(CHUNK_BYTES):
                trace.offset += len(chunk)
                _ingest(trace, chunk)
                _trim(trace)
    except OSError as e:
        raise Invalid("host_failed", f"the DOS call trace {trace.path} could not be read: "
                      f"{e!r}") from None
    return trace


def _ingest(trace: Trace, chunk: bytes) -> None:
    """The rows of `chunk`, after the cut line the last one left, into calls."""
    lines = (trace.partial + chunk).split(b"\n")
    trace.partial = lines.pop()
    for raw in lines:
        # A trace written in text mode on Windows ends each row with CR LF.
        line = raw.decode("latin-1").rstrip("\r")
        if (entry := ENTRY.match(line)) is not None:
            call = _entry(entry)
            trace.calls.append(call)
            trace.by_n[call["n"]] = call
        elif (r := RETURN.match(line)) is not None:
            held = trace.by_n.get(int(r.group(1)))
            if held is not None:
                _returned(held, r)
                held["line"] = _render(held)
        elif (c := CAP.match(line)) is not None:
            trace.capped = int(c.group(1))
        else:
            trace.broken = (f"the DOS call trace {trace.path} holds a line that is no row of "
                            f"`{DOSTRACE}`: {line[:120]!r}; the rows after it were not read, so "
                            "the trace is not trusted from here on: `close` and `start` again "
                            "for a trace to read")
            raise Invalid("unexpected_answer", trace.broken)
    for call in trace.calls[trace.rendered:]:
        call.setdefault("line", _render(call))
    trace.rendered = len(trace.calls)


def _trim(trace: Trace) -> None:
    """Let the oldest calls go past `CALLS_KEPT`, with everything that points at them."""
    cut = len(trace.calls) - CALLS_KEPT
    if cut <= 0:
        return
    for call in trace.calls[:cut]:
        trace.by_n.pop(call["n"], None)
    del trace.calls[:cut]
    trace.dropped += cut
    trace.rendered -= cut
    first = trace.calls[0]["n"]
    for pattern, (settled, kept) in trace.matched.items():
        trace.matched[pattern] = (max(settled - cut, 0), [c for c in kept if c["n"] >= first])


def seen(trace: Trace) -> int:
    """How many calls the trace has had, dropped ones included: what a wait counts arrivals by."""
    return trace.dropped + len(trace.calls)


def begin(session: ds.Session) -> Trace:
    """Turn the trace on at `start`, into a file of this session's scratch."""
    if not session.has(DOSTRACE):
        raise dbg.missing(DOSTRACE, "`start(dos_calls=True)`")
    path = STATE.session_scratch() / f"dos-calls-{session.proc.pid}.trace"
    ok, lines = session.exec(f"{DOSTRACE} {path}")
    found = next((m for m in map(STATUS_LINE.match, lines) if m is not None), None)
    if not ok or found is None or found.group(1) != "ON" or Path(found.group(5)) != path:
        raise Invalid("unexpected_answer", f"`{DOSTRACE} {path}` answered "
                      f"{' / '.join(lines) or 'nothing'}, not the line saying it records there")
    return Trace(path)


def _trace() -> Trace:
    trace = STATE.dos_calls
    if trace is None:
        raise Invalid("no_channel", "this session records no DOS calls: start it with "
                      "`dos_calls=True` (a build whose debugger has `DOSTRACE`)")
    return read(trace)


def _matching(trace: Trace, pattern: str) -> list[dict[str, Any]]:
    """The calls whose line `pattern` matches. A returned call's line no longer changes, so the
    matches among the calls before the first unreturned one are kept per pattern."""
    rx = judges.regex("pattern", pattern)
    settled, kept = trace.matched.pop(pattern, (0, []))
    stable: list[dict[str, Any]] = list(kept)
    tail: list[dict[str, Any]] = []
    pending = False
    for i in range(settled, len(trace.calls)):
        call = trace.calls[i]
        pending = pending or not call["returned"]
        if rx.search(call["line"]):
            (tail if pending else stable).append(call)
        if not pending:
            settled = i + 1
    trace.matched[pattern] = (settled, stable)
    while len(trace.matched) > PATTERNS_KEPT:
        del trace.matched[next(iter(trace.matched))]
    return stable + tail


def _capped(trace: Trace) -> dict[str, Any]:
    if trace.capped is None:
        return {}
    return {"note": f"the trace stopped at its {prose.counted(trace.capped, 'row')}: calls "
                    "after that were not recorded"}


def _dropped(trace: Trace) -> dict[str, Any]:
    return {"calls_dropped": trace.dropped} if trace.dropped else {}


def log(pattern: str, limit: int, since_mark: int, labels: bool = False) -> dict[str, Any]:
    """The body of `log(channel="dos")`."""
    if labels:
        raise Invalid("bad_argument", "`labels` counts log lines by their first word, and the "
                      "DOS channel answers calls: each already names its `function`")
    if since_mark:
        raise Invalid("bad_argument", "`since_mark` is a byte of the session log, and the DOS "
                      "channel reads its own trace: narrow it with `pattern` (each call starts "
                      "`#<n>`)")
    dlogs.check_e9_limit(limit)
    hits = _matching(_trace(), pattern)
    trace = STATE.dos_calls
    assert trace is not None
    return st.reply(pattern=pattern, channel=CHANNEL, lines_total=len(hits),
                    truncated=len(hits) > limit, calls=hits[-limit:], **_capped(trace),
                    **_dropped(trace))


def _peek(session: ds.Session) -> tuple[bool, bool]:
    """Whether the machine is at the debugger and whether the emulator is gone; a peek that fails
    on an emulator that has since gone is that, the trace still holding what it wrote."""
    try:
        stopped = session.at_debugger()
    except ds.Invalid:
        if session.alive():
            raise
        return False, True
    return stopped, not session.alive()


def _arrived(trace: Trace, pattern: str, call: dict[str, Any], before: int,
             ticker: Ticker) -> dict[str, Any]:
    return st.reply(verdict="TARGET", pattern=pattern, channel=CHANNEL, call=call,
                    already=False, waited_s=ticker.elapsed(), lines_before=before,
                    lines_total=seen(trace), arrived_during=seen(trace) - before,
                    lines_examined=len(trace.calls), **_dropped(trace))


def log_wait(session: ds.Session, pattern: str, seconds: float, since_mark: int,
             progress: ds.Progress) -> dict[str, Any]:
    """The body of `log_wait(channel="dos")`: the first call matching `pattern`, at once if the
    trace already holds it, else as it arrives, up to `seconds`."""
    if since_mark:
        raise Invalid("bad_argument", "`since_mark` is a byte of the session log, and the DOS "
                      "channel reads its own trace: narrow it with `pattern`")
    trace = _trace()
    before = seen(trace)
    hits = _matching(trace, pattern)
    if hits:
        return st.reply(verdict="TARGET", pattern=pattern, channel=CHANNEL, call=hits[0],
                        already=True, waited_s=0.0, lines_before=before,
                        lines_total=before, arrived_during=0, lines_examined=len(trace.calls),
                        **_dropped(trace))
    ticker = Ticker(seconds, progress)
    parked = None
    while not ticker.expired():
        # Both asked before the read, so the read is the last word on a stop or a death, as in
        # the guest channel's wait.
        stopped, gone = _peek(session)
        parked = stopped if parked is None else parked
        read(trace)
        found = _matching(trace, pattern)
        if found:
            return _arrived(trace, pattern, found[0], before, ticker)
        arrived = seen(trace) - before
        if gone:
            raise Invalid("session_broken", core_wait.gone_message(
                pattern, core_wait.Ended("GONE", arrived, seen(trace), ticker.elapsed()),
                seconds))
        if stopped:
            raise ds.wait_stopped(pattern, arrived, ticker.elapsed(), parked=parked is True,
                                   at_bound=False)
        ticker.tick("waiting {elapsed:.0f} s for a DOS call matching {pattern!r}",
                    pattern=pattern)
        time.sleep(POLL_S)
    # One look after the last sleep: a call that came in it is found, not timed out.
    read(trace)
    if found := _matching(trace, pattern):
        return _arrived(trace, pattern, found[0], before, ticker)
    note = f"no DOS call matching {pattern!r} in {seconds:g} s"
    capped = _capped(trace).get("note")
    return st.reply(verdict="TIMEOUT", pattern=pattern, channel=CHANNEL,
                    waited_s=ticker.elapsed(), arrived_during=seen(trace) - before,
                    lines_examined=len(trace.calls), **_dropped(trace),
                    note=f"{note}; {capped}" if capped else note)
