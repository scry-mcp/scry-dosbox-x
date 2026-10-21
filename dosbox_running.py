"""The RUNNING guest: what a stop is, and what the server does at the first contact after one.

A guest that runs answers no console command, so this module is about the two moments
around that: a stop the machine reached on its own is RECORDED by the first tool that
finds it and the queue of what was asked meanwhile is drained (`observe_stop`,
`drain_if_stopped`); and a stop a tool produced comes back as ONE survey of the screen
(`stop_reply`): where, the instruction there, by which declaration, the watches evaluated,
the registers and the E9 block, with the three arguments every stop tool shares validated
BEFORE the machine is moved (`e9_validate`).
"""

from __future__ import annotations

import copy
import re
from typing import Any, cast

from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_code as code
import dosbox_console as dcons
import dosbox_logs as dlogs
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE


def observe_stop(session: ds.Session) -> None:
    """A STOP THE GUEST REACHED ON ITS OWN IS RECORDED BY THE FIRST CONTACT THAT FINDS IT.
    The session counts every transition to "at the debugger"; when that count is not the
    one the last recorded stop carries, the machine has stopped since without any stop
    tool reporting it (a breakpoint fired during a wait or a key), so this surveys it once
    and remembers it, and `last_stop` and `registers(from_last_stop=True)` then
    describe the stop the machine is IN rather than the one before (otherwise `last_stop`
    names one stop while `registers` reads the address of the next)."""
    # THE TERMINAL IS LOOKED AT FIRST. The peek is what counts a stop nobody has read (the
    # prompt sitting in the drain), so a count read before it is the count as of the LAST
    # contact, and comparing that with the record says "nothing new" about a machine that
    # stopped minutes ago. Measured on a real guest: `status` kept naming the previous
    # stop while the memory breakpoint's own line sat unread in the buffer.
    if not session.at_debugger():
        return
    count = getattr(session, "stop_count", None)
    if count is None or count == STATE.last_stop.get("stop_count"):
        return
    try:
        where, registers, held = session.stop_survey()
    except ds.Invalid:
        return                                  # a cut pane: the next contact tries again
    machine = (where["mode"], registers)
    STATE.remember_stop(session, where, registers, held,
                   arming.attribute_stop(session, where=where, machine=machine,
                                         retrace_may_stop=True))
    # The account rides on THIS contact's reply, once.
    STATE.found_stop_last = {"stop_seq": STATE.last_stop["seq"], "pc": STATE.last_stop["at"],
                             "attribution": dict(STATE.last_stop["attribution"])}


def drain_if_stopped(session: ds.Session) -> None:
    """THE FIRST CONTACT AFTER A STOP APPLIES WHAT WAS PENDING. A breakpoint can fire while
    the caller is doing running-guest things (a wait, a key), so the stop is not always a
    stop TOOL's reply; whichever tool comes next finds the machine at the debugger
    (passively: no console round trip) and drains the queue, and its reply carries
    `applied_on_stop`. A stop tool still drains it itself, in `stop_reply`."""
    observe_stop(session)                  # a stop nobody reported is recorded first
    waiting = STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["load"] is not None
    fresh = STATE.pending["dirty"] or STATE.pending["drained_seq"] != STATE.last_stop.get("seq", 0)
    if waiting and fresh and session.at_debugger():
        arming.apply_pending(session)             # accumulates into `STATE.applied_last`


_E9_MODES = ("none", "all", "since")
#: THE E9 BLOCK'S `how` names a way the caller can take: the argument on the four tools that
#: take `e9` (`resume`, `step`, `run_to`, `run_for`), the log on every other stop.
E9_BY_ARGUMENT = ("pass e9='all', e9='lines:N', e9='since' or e9='seconds:N' (with "
                  "e9_stamp=<regex capturing the seconds>), with e9_filter=<pattern>, to include "
                  "the lines")
E9_BY_LOG = "this tool takes no `e9`: `log(pattern=\".\", channel=\"guest\")` reads the lines"


def e9_validate(mode: str, e9_filter: str, e9_stamp: str | None = None) -> None:
    """Refuse a bad E9 mode or filter BEFORE the machine is moved. A stop reply's E9 block is
    a DISPLAY option, but the tools that carry it (resume/step/run_to) first RESUME the guest
    -- an irreversible act -- so a typo in `e9` must be caught before the F5, not after, or a
    whole stop reply is thrown away for a malformed optional parameter that could have been
    rejected up front. The regex is compiled here too, so a bad filter fails the same way.

    `seconds:N` NEEDS A STAMP. The guest's log carries no time this server knows how to read;
    a program that stamps its own lines (`[+SSSS.mmm]` from a monotonic guest clock, say)
    lends that knowledge through `e9_stamp`, a regex with ONE group that captures the seconds
    as a number. Without it the window is refused here, not served wrong."""
    if mode not in _E9_MODES and not mode.startswith(("lines:", "seconds:")):
        raise ds.Invalid("bad_argument",
            f"e9 is none | all | lines:N | since | seconds:N; got {mode!r}")
    if mode.startswith(("lines:", "seconds:")):
        _e9_count(mode)          # raises for a non-positive or non-integer N
    dlogs.compiled(e9_filter)       # raises for a bad regex, naming it as the caller's
    if e9_stamp is not None:
        if not isinstance(cast(object, e9_stamp), str) or not e9_stamp:
            raise ds.Invalid("bad_argument",
                "e9_stamp is a regular expression with ONE group capturing the "
                             "line's time in seconds")
        if dlogs.compiled(e9_stamp).groups != 1:
            raise ds.Invalid("bad_argument",
                f"e9_stamp must capture the seconds in exactly ONE group; "
                             f"{e9_stamp!r} has {dlogs.compiled(e9_stamp).groups}")
    if mode.startswith("seconds:") and e9_stamp is None:
        raise ds.Invalid("bad_argument",
            "a last-N-seconds window needs `e9_stamp`: a regex with one group "
                         "capturing each line's own time in seconds (the guest's clock), "
                         "because this server knows no timestamp of its own on the log. "
                         "Without one, use lines:N or since")


def e9_summary(session: ds.Session, mode: str, e9_filter: str,
                e9_stamp: str | None = None, how: str = E9_BY_LOG) -> dict[str, Any]:
    """The E9 block of a stop reply: OFF by default, carrying the COUNT and `how`, the way to
    see the lines (`e9=` on the tools that take one, `log` on every other stop), because the
    volume can blow up context and off-with-no-word leaves doubt. The switch is `none` | `all` |
    `lines:N` | `since` | `seconds:N`, with a filter.
    The mode is assumed already validated by `e9_validate` (before the guest was resumed).

    `since` shows only what the guest logged since the previous stop, off a mark keyed on the
    UNFILTERED line count, so a `since` window is the SAME whatever filter this or the earlier
    stop used -- the position in the log does not depend on how it is filtered. `seconds:N` is
    NOT served and says why: the guest's E9 log carries no per-line timestamp this server has
    measured, so a time window cannot be cut honestly -- a limitation carried to QA.
    """
    pat = dlogs.compiled(e9_filter)
    # THE DEFAULT PATH READS ONLY WHAT IS NEW. Every stop carries this block, and the
    # whole log was read from byte zero and filtered at each of them, even with nothing
    # asked for (`none`): quadratic in the session, the shape `e9_wait` had already left
    # behind. With no filter, `none` and `since` need only the lines since the previous
    # stop and a running total; a filter, or a mode that shows history, reads it whole.
    if mode in ("none", "since") and e9_filter == ".":
        mark = int(STATE.e9_mark.get("offset", 0))
        try:
            fresh_all, offset = session.e9_new_since(mark)
        except ds.Invalid as exc:
            return {"available": False, "why": str(exc)}
        if offset < mark:
            STATE.e9_mark["count"] = 0       # rewritten shorter: read from its start, counted so
        STATE.e9_mark["offset"] = offset
        unfiltered = int(STATE.e9_mark["count"]) + len(fresh_all)
        block: dict[str, Any] = {"lines_total": unfiltered, "unfiltered": unfiltered,
                                 "filter": e9_filter}
        if mode == "none":
            block["shown"] = 0
            block["how"] = how
        else:
            block.update(lines=fresh_all, shown=len(fresh_all), since_last_stop=len(fresh_all))
        return block
    try:
        every = session.e9_lines()                     # every E9 line, in order
    except ds.Invalid as exc:
        return {"available": False, "why": str(exc)}
    unfiltered = len(every)
    STATE.e9_mark["offset"] = session.e9_mark()
    filtered = [ln for ln in every if pat.search(ln)]
    block = {"lines_total": len(filtered), "unfiltered": unfiltered, "filter": e9_filter}
    if mode == "none":
        block["shown"] = 0
        block["how"] = how
    elif mode == "all":
        block["lines"], block["shown"] = filtered, len(filtered)
    elif mode.startswith("lines:"):
        block["lines"] = filtered[-_e9_count(mode):]
        block["shown"] = len(block["lines"])
    elif mode == "since":
        fresh = [ln for ln in every[STATE.e9_mark["count"]:] if pat.search(ln)]
        block["lines"], block["shown"], block["since_last_stop"] = fresh, len(fresh), len(fresh)
    elif e9_stamp is None:  # seconds:N with no stamp: validated away up front, said here too
        block["shown"] = 0
        block["unsupported"] = ("a last-N-seconds window needs `e9_stamp`, a regex with one "
                                "group capturing each line's own time in seconds")
    else:
        # THE WINDOW IS THE GUEST'S CLOCK, not the host's: "now" is the latest stamp any
        # line carries, and a line is in the window when its own stamp is within N of it.
        # A line without a stamp cannot be placed and is counted as such, never guessed.
        stamp = dlogs.compiled(e9_stamp)
        block.update(_last_seconds(every, filtered, stamp, _e9_count(mode)))
    return block


def _last_seconds(every: list[str], filtered: list[str], stamp: re.Pattern[str],
                  n: int) -> dict[str, Any]:
    """The lines whose own stamp is within `n` seconds of the latest stamp in the log."""
    def at(line: str) -> float | None:
        m = stamp.search(line)
        if m is None:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None
    stamped = [t for t in (at(ln) for ln in every) if t is not None]
    if not stamped:
        return {"shown": 0, "lines": [], "unstamped": len(every),
                "unsupported": "no line in the log matched `e9_stamp`, so there is no clock "
                               "to cut a window on"}
    now = max(stamped)
    kept = [ln for ln in filtered if (t := at(ln)) is not None and t >= now - n]
    return {"lines": kept, "shown": len(kept), "now": now, "window_s": n,
            "unstamped": sum(1 for ln in filtered if at(ln) is None)}


def _e9_count(mode: str) -> int:
    """The N out of `lines:N` (or `seconds:N`), refused if it is not a positive integer."""
    try:
        n = int(mode.split(":", 1)[1])
    except ValueError:
        raise ds.Invalid("bad_argument", f"the N in {mode!r} is not an integer") from None
    if n <= 0:
        raise ds.Invalid("bad_argument", f"the N in {mode!r} must be positive")
    return n


def stop_reply(session: ds.Session, e9: str = "none", e9_filter: str = ".",
                e9_stamp: str | None = None, *, retrace_may_stop: bool = False,
                e9_how: str = E9_BY_LOG, made_by: dict[str, str] | None = None,
                **base: Any) -> dict[str, Any]:
    """What a stop ALWAYS returns, on top of the tool's own fields in `base`:
    where it stopped and by which declaration (attribution by address, or an honest
    cannot-say), the watches already evaluated, the registers, and the E9 summary, whose `how`
    is `e9_how` (a tool that takes no `e9` names what reads the lines instead). `made_by`, a
    stop the calling tool made itself (`run_to`'s target, whose breakpoint is gone by now),
    is attributed to it rather than looked for among the declarations. `altered`
    rides in the standard `session` block `st.reply` adds, so it is carried the same way here.
    """
    # ONE SURVEY for where AND registers (a round trip costs most of a second): they
    # read the same stopped screen, so taking two was one avoidable console round trip a stop.
    # ONE repaint for the three things a stop reads: where, registers and the list the
    # watches check against. Measured on dos-real16 before this: four `BPLIST` round trips
    # per stop, two of them for the same screen.
    arming.apply_pending(session)      # what the running guest kept the console from; the reply
    where, registers, held = session.stop_survey()   # carries the account via `st.reply`
    machine = (where["mode"], registers)
    watches = arming.evaluate_watches(session, machine=machine, held=held)
    attribution = arming.attribute_stop(session, where=where, machine=machine,
                                        retrace_may_stop=retrace_may_stop and made_by is None)
    if made_by is not None:
        # THE TOOL'S OWN STOP, and any declaration resolving to the same place named beside it.
        also = (attribution.get("refs") or [attribution["ref"]]
                if attribution.get("attributed") else [])
        attribution = {"attributed": True, **made_by, "at": attribution["at"],
                       **({"refs": also} if also else {})}
    STATE.remember_stop(session, where, registers, held, attribution)
    picture = STATE.last_stop["picture"] = code.stop_instruction(session, where, registers,
                                                                 session.survey_text)
    e9_block = _stop_e9(session, e9, e9_filter, e9_stamp, e9_how)
    # THE STOP'S NUMBER rides on its reply: it is what a batch with `summaries`
    # counts its stops by, and what `last_stop.stop_seq` later names.
    return st.reply(**{**base, **position(where, getattr(session, "paging", None))},
                    regs=registers, watches=watches, attribution=attribution,
                    e9=e9_block, stop_seq=STATE.last_stop["seq"], **picture)


def recorded_stop_reply(session: ds.Session, recorded: dict[str, Any]) -> dict[str, Any]:
    """The enriched stop for one already recorded (`STATE.as_of_current`), built off that
    record: its registers, the watches evaluated and the E9 summary read now, and the
    instruction it is on, decoded here off the screen its survey read when no reply has yet.
    Never surveyed again, which would number the same stop twice."""
    stop = STATE.last_stop
    machine = (str(stop["where"]["mode"]), dict(stop["registers"]))
    watches = arming.evaluate_watches(session, machine=machine, held=list(stop["held"]))
    if "picture" not in stop:
        stop["picture"] = code.stop_instruction(session, dict(stop["where"]),
                                                dict(stop["registers"]), session.survey_text)
    return {**recorded_head(recorded), "regs": dict(stop["registers"]),
            "watches": watches,
            "e9": _stop_e9(session, "none", "."), **copy.deepcopy(stop["picture"])}


def _stop_e9(session: ds.Session, e9: str, e9_filter: str, e9_stamp: str | None = None,
             how: str = E9_BY_LOG) -> dict[str, Any]:
    """A stop's E9 block, and the since-last-stop mark moved to it: the offset and the count
    move together, or the next `since` with a filter starts lines before the one without. The
    mark is the UNFILTERED count, so the next `since` is independent of whichever filter this
    stop or that one used; not moved when the log is unavailable."""
    block = e9_summary(session, e9, e9_filter, e9_stamp, how)
    if "unfiltered" in block:
        STATE.e9_mark["count"] = int(block["unfiltered"])
    return block


def stop_or_base(session: ds.Session, stopped: bool, e9: str, e9_filter: str,
                  e9_stamp: str | None, base: dict[str, Any], *,
                  retrace_may_stop: bool = False, e9_how: str = E9_BY_LOG,
                  made_by: dict[str, str] | None = None) -> dict[str, Any]:
    """The enriched stop reply when the machine STOPPED, else just the tool's base answer.
    A halt whose POSITION cannot be read (a cut pane leaves `where` refusing, which `resume`'s
    read-back meets as a stop with no position) is not discarded: the halt is a real
    observation, so the base fields stand and the enrichment is marked unavailable with why,
    rather than the whole reply becoming INVALID for a read that could not be made."""
    if not stopped:
        return st.reply(**base)
    try:
        return stop_reply(session, e9=e9, e9_filter=e9_filter, e9_stamp=e9_stamp,
                          retrace_may_stop=retrace_may_stop, e9_how=e9_how, made_by=made_by,
                          **base)
    except ds.Invalid as e:
        return st.reply(enrichment={"available": False, "why": str(e)}, **base)


def cpu_mode_of(mode: str, paging: bool | None) -> str | dict[str, Any]:
    """The cpu mode of a stop in `status`'s words, `real`, `protected`, `paged` or the pane's own
    `VM86`, off the pane's mode word and its paging mark; unavailable when the two do not place
    it."""
    if mode == dcons.REAL_MODE:
        return "real"
    if mode == dcons.V86_MODE:
        return dcons.V86_MODE
    if mode.startswith("Pr") and paging is not None:
        return "paged" if paging else "protected"
    return contract.unavailable(
        f"the pane named the mode {mode!r} and "
        f"{'no PAGE/NOPG mark' if paging is None else 'a paging mark'}, which does not place "
        f"it as real, protected or paged")


#: Why a stop's position is unavailable: the survey that would place it came back cut.
CUT_POSITION_WHY = "the stop's survey came back cut, so its position could not be read"


def position(where: dict[str, str] | None, paging: bool | None) -> dict[str, Any]:
    """Where a machine stopped, as every stop reply says it: `pc`, the `SSSS:OOOOOOOO` every
    DOS ref takes, and `cpu_mode` (`cpu_mode_of`); both unavailable when no survey placed it."""
    if where is None:
        return {"pc": contract.unavailable(CUT_POSITION_WHY),
                "cpu_mode": contract.unavailable(CUT_POSITION_WHY)}
    return {"pc": f"{where['cs']}:{where['eip']}", "cpu_mode": cpu_mode_of(where["mode"], paging)}


def recorded_head(recorded: dict[str, Any]) -> dict[str, Any]:
    """The head of a stop reply built off the record rather than a survey of its own: the
    record as `STATE.as_of_current` names it, and the `position` of the stop it names."""
    stop = STATE.last_stop
    return {**recorded, **position(dict(stop["where"]), stop.get("paging"))}


def status_facts(session: ds.Session | None) -> dict[str, Any]:
    """What `status` adds about the MACHINE: `pc`, where it is NOW, read off the pane at a stop
    (one console round trip), so a command that moved CS:IP
    inside the stop (`INTT`, `set_register`) is seen, the stop's own pc staying in `last_stop`;
    `cpu_mode` (`stop_cpu_mode`); and `declarations`, this server's own declarations counted
    per family in any state, which are records and so present on a running machine too. No
    session: none of them."""
    if session is None:
        return {}
    facts: dict[str, Any] = {"cpu_mode": stop_cpu_mode(session)}
    if session.alive() and session.at_debugger():
        try:
            now = session.where()
        except ds.Invalid as e:
            facts["pc"] = contract.unavailable(
                f"the pane was not readable ({e}), and `last_stop` is the stop before")
        else:
            facts["pc"] = f"{now['cs']}:{now['eip']}"
    else:
        facts["pc"] = contract.unavailable(
            "the guest is running (or gone): `pc` is read off a stopped machine's register "
            "pane, and `last_stop` says where it was last seen")
    families = {"breakpoints": 0, "watches": 0}
    for decl in (STATE.store.declarations() if STATE.store is not None else []):
        families["watches" if decl.kind == "watch" else "breakpoints"] += 1
    facts["declarations"] = families
    return facts


def stop_cpu_mode(session: ds.Session) -> str | dict[str, Any]:
    """The cpu mode of the stop the machine is in, off its recorded survey (no console round
    trip: a command inside a stop does not switch the mode); unavailable while the guest runs,
    when that stop's survey was cut, or when the pane does not place it."""
    if not (session.alive() and session.at_debugger()):
        return contract.unavailable(
            "the guest is running (or gone): the mode is read off a stopped machine's "
            "register pane, and `last_stop` says where it was last seen")
    if STATE.as_of_current(session) is None:
        # THE RECORD IS NOT THIS STOP'S: its survey was cut, so the record still holds the
        # previous one, and naming that as the stop the machine is in would be a confident
        # wrong answer of the right shape.
        return contract.unavailable(
            "the stop the machine is in was not readable yet (a cut pane; the next contact "
            "retries), and `last_stop` is the one before it")
    return cpu_mode_of(str(STATE.last_stop.get("where", {}).get("mode", "")),
                       STATE.last_stop.get("paging"))


def live() -> ds.Session:
    """The session, or INVALID: `no_session` with none, `session_broken` with `exit_code` for
    one whose emulator died under it.

    A DEAD SESSION IS KEPT UNTIL `close`: its `session` block still says whether
    it was written to (`altered`), which a caller measuring a forced state must not lose, and
    `close` collects the exit before the scratch goes. Every call that needs the machine answers
    `session_broken` until then; a `start` closes it first."""
    ses = STATE.session
    if ses is None:
        raise ds.Invalid("no_session", "there is no live session. `start` one first; a reply from "
                         "a dead session would be a reading of nothing.")
    if not ses.alive():
        exit_code = ses.proc.poll()
        raise ds.Invalid("session_broken",
                         f"DOSBox-X exited with code {exit_code} under this session: `close` "
                         f"collects what it left, then `start` a new one", exit_code=exit_code)
    drain_if_stopped(ses)
    return ses
