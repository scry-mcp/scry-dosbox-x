"""The running guest: recording a stop found at first contact, and the reply a stop returns."""

from __future__ import annotations

import copy
from typing import Any, Literal

from scry_core import log_marks
from scry_core import reply_contract as contract

import dosbox_arming as arming
import dosbox_code as code
import dosbox_comments as comments
import dosbox_debugger as dbg
import dosbox_grammar as grammar
import dosbox_logs as dlogs
import dosbox_session as ds
import dosbox_state as st
from dosbox_state import STATE


def observe_stop(session: ds.Session) -> None:
    """Record a stop the guest reached on its own, once, at the first contact that finds it."""
    # Peek first: the peek is what counts a stop nobody has read, so a count read before it
    # compares stale state and `status` keeps naming the previous stop.
    if not session.at_debugger():
        return
    count = getattr(session, "stop_count", None)
    if count is None or count == STATE.last_stop.get("stop_count"):
        return
    try:
        where, registers, held = session.stop_survey()
    except ds.Invalid:
        return                                  # an unreadable stop: the next contact tries again
    machine = (where["mode"], registers)
    STATE.remember_stop(session, where, registers, held,
                   arming.attribute_stop(session, where=where, machine=machine,
                                         retrace_may_stop=True, held=held))
    STATE.found_stop_last = {"stop_seq": STATE.last_stop["seq"], "pc": STATE.last_stop["at"],
                             "cause": st.cause(STATE.last_stop["attribution"])}


def drain_if_stopped(session: ds.Session) -> None:
    """Apply the pending queue at the first contact after a stop (`applied_on_stop`)."""
    observe_stop(session)
    waiting = (STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["remeasure"]
               or STATE.pending["load"] is not None)
    fresh = STATE.pending["dirty"] or STATE.pending["drained_seq"] != STATE.last_stop.get("seq", 0)
    # The stop `observe_stop` just read, never one reached since: that one is the next contact's
    # to record first.
    if waiting and fresh and session.parked:
        arming.apply_pending(session)


def e9_block(session: ds.Session) -> dict[str, Any]:
    """The guest's E9 lines since the previous stop (`log_marks.stop_block`); a log rewritten
    shorter is read from its start."""
    mark = STATE.e9_offset
    try:
        fresh, offset = session.e9_new_since(mark)
    except ds.Invalid as exc:
        return contract.unavailable(str(exc))
    if offset < mark:
        mark = 0
    STATE.e9_offset = offset
    return log_marks.stop_block(fresh, mark, "guest", dlogs.LOG_LIMIT_MAX)


def stop_reply(session: ds.Session, *, retrace_may_stop: bool = False,
               made_by: dict[str, str] | None = None,
               asked_by: Literal["stop", "cancel"] | None = None,
               **base: Any) -> dict[str, Any]:
    """What a stop always returns on top of `base`: position, `cause`, watches, registers, E9.
    `made_by` attributes a stop the calling tool made itself; `asked_by` names the cause when
    no declaration is at the address."""
    # One survey serves where, registers and the watches' list.
    arming.apply_pending(session)
    where, registers, held = session.stop_survey()
    machine = (where["mode"], registers)
    watches = arming.evaluate_watches(session, machine=machine, held=held)
    attribution = arming.attribute_stop(session, where=where, machine=machine,
                                        retrace_may_stop=retrace_may_stop and made_by is None,
                                        held=held)
    if made_by is not None:
        also = (attribution.get("refs") or [attribution["ref"]]
                if attribution.get("attributed") else [])
        attribution = {"attributed": True, **made_by, "at": attribution["at"],
                       **({"refs": also} if also else {})}
    elif asked_by is not None and not attribution.get("attributed"):
        attribution = {"attributed": True, "ref": asked_by, "by": asked_by,
                       "at": attribution["at"]}
    STATE.remember_stop(session, where, registers, held, attribution)
    # Marked under the new number, or the next contact drains this stop again.
    STATE.pending["drained_seq"] = STATE.last_stop["seq"]
    picture = STATE.last_stop["picture"] = code.stop_instruction(session, where, registers,
                                                                 comments.notes)
    e9 = e9_block(session)
    return st.reply(**{**base, **position(where, getattr(session, "paging", None))},
                    regs=st.shown_regs(registers), watches=watches,
                    cause=st.cause(attribution),
                    e9=e9, stop_seq=STATE.last_stop["seq"], **picture)


def recorded_stop_reply(session: ds.Session, recorded: dict[str, Any]) -> dict[str, Any]:
    """The enriched stop for one already recorded; never surveyed again, which would number
    it twice."""
    stop = STATE.last_stop
    machine = (str(stop["where"]["mode"]), dict(stop["registers"]))
    watches = arming.evaluate_watches(session, machine=machine, held=list(stop["held"]))
    if "picture" not in stop:
        stop["picture"] = code.stop_instruction(session, dict(stop["where"]),
                                                dict(stop["registers"]), comments.notes)
    return {**recorded_head(recorded), "regs": st.shown_regs(stop["registers"]),
            "watches": watches,
            "e9": e9_block(session), **copy.deepcopy(stop["picture"])}


def stop_or_base(session: ds.Session, stopped: bool, base: dict[str, Any], *,
                 retrace_may_stop: bool = False,
                 made_by: dict[str, str] | None = None,
                 asked_by: Literal["stop", "cancel"] | None = None) -> dict[str, Any]:
    """The enriched stop reply when the machine stopped, else the tool's base answer.
    A halt whose position cannot be read keeps the base fields and marks the
    enrichment unavailable."""
    if not stopped:
        return st.reply(**base)
    try:
        return stop_reply(session, retrace_may_stop=retrace_may_stop, made_by=made_by,
                          asked_by=asked_by, **base)
    except ds.Invalid as e:
        return st.reply(enrichment={"available": False, "why": str(e)}, **base)


def cpu_mode_of(mode: str, paging: bool | None) -> str | dict[str, Any]:
    """The cpu mode in `status`'s words (`real`, `protected`, `paged`, `VM86`), or unavailable."""
    if mode == grammar.REAL_MODE:
        return "real"
    if mode == grammar.V86_MODE:
        return grammar.V86_MODE
    if mode.startswith("Pr") and paging is not None:
        return "paged" if paging else "protected"
    return contract.unavailable(
        f"the stop read the mode {mode!r} and "
        f"{'no paging bit' if paging is None else 'a paging bit'}, which does not place "
        f"it as real, protected or paged")


CUT_POSITION_WHY = "the stop's survey could not be read, so its position is not known"


def position(where: dict[str, str] | None, paging: bool | None) -> dict[str, Any]:
    """Where a machine stopped: `pc` (`SSSS:OOOOOOOO`) and `cpu_mode`."""
    if where is None:
        return {"pc": contract.unavailable(CUT_POSITION_WHY),
                "cpu_mode": contract.unavailable(CUT_POSITION_WHY)}
    return {"pc": f"{where['cs']}:{where['eip']}", "cpu_mode": cpu_mode_of(where["mode"], paging)}


def recorded_head(recorded: dict[str, Any]) -> dict[str, Any]:
    """The head of a stop reply built off the record rather than a survey."""
    stop = STATE.last_stop
    return {**recorded, **position(dict(stop["where"]), stop.get("paging"))}


PC_RUNNING_WHY = ("the guest is running: `pc` is read off a stopped machine's registers, and "
                  "`last_stop` says where it was last seen")
PC_UNKNOWN_WHY = ("the guest was let run, and this build's debugger has no `RUNSTATE` command to "
                  "say whether it stopped since: `stop` brings it back, and `last_stop` says "
                  "where it was last seen")
PC_GONE_WHY = "DOSBox-X has exited: `last_stop` says where the guest was last seen"


def status_facts(session: ds.Session | None, stopped: bool) -> dict[str, Any]:
    """What `status` adds about the machine: `pc` now (read off the registers, so a
    `set_register` inside the stop shows), `cpu_mode`, and `declarations` counted per family.
    `stopped` is the call's one reading of the run state: a running guest costs one `RUNSTATE`."""
    if session is None:
        return {}
    facts: dict[str, Any] = {"cpu_mode": stop_cpu_mode(session, stopped)}
    if stopped:
        try:
            now = session.where()
        except ds.Invalid as e:
            facts["pc"] = contract.unavailable(
                f"the registers were not readable ({e}), and `last_stop` is the stop before")
        else:
            facts["pc"] = f"{now['cs']}:{now['eip']}"
    elif not session.alive():
        facts["pc"] = contract.unavailable(PC_GONE_WHY)
    else:
        facts["pc"] = contract.unavailable(PC_RUNNING_WHY if session.has(dbg.RUNSTATE)
                                           else PC_UNKNOWN_WHY)
    families = {"breakpoints": 0, "watches": 0, "regpoints": 0}
    for decl in (STATE.store.declarations() if STATE.store is not None else []):
        families[{"watch": "watches", "regpoint": "regpoints"}.get(decl.kind, "breakpoints")] += 1
    facts["declarations"] = families
    return facts


def stop_cpu_mode(session: ds.Session, stopped: bool | None = None) -> str | dict[str, Any]:
    """The cpu mode of the stop the machine is in, off its recorded survey; `stopped` the
    caller's reading of the run state, asked here when there is none."""
    if stopped is None:
        stopped = session.alive() and session.at_debugger()
    if not stopped:
        return contract.unavailable(
            "the guest is running (or gone): the mode is read off a stopped machine, and "
            "`last_stop` says where it was last seen")
    if STATE.as_of_current(session) is None:
        # The survey was cut, so the record is still the previous stop's.
        return contract.unavailable(
            "the stop the machine is in was not readable yet (the next contact retries), and "
            "`last_stop` is the one before it")
    return cpu_mode_of(str(STATE.last_stop.get("where", {}).get("mode", "")),
                       STATE.last_stop.get("paging"))


def live() -> ds.Session:
    """The session, or INVALID: `no_session`, or `session_broken` with `exit_code`.

    A dead session is kept until `close`, so its `session` block still says whether it was
    written to (`altered`)."""
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
