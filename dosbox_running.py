"""The RUNNING guest: what a stop is, and what the server does at the first contact after one.

A guest that runs answers no console command, so this module is about the two moments
around that: a stop the machine reached on its own is RECORDED by the first tool that
finds it and the queue of what was asked meanwhile is drained (`observe_stop`,
`drain_if_stopped`); and a stop a tool produced comes back as ONE survey of the screen
(`stop_reply`): where, the instruction there, by which declaration, the watches evaluated,
the registers and the E9 block.
"""

from __future__ import annotations

import copy
from typing import Any

from scry_core import log_marks
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
                                         retrace_may_stop=True, held=held))
    # The account rides on THIS contact's reply, once.
    STATE.found_stop_last = {"stop_seq": STATE.last_stop["seq"], "pc": STATE.last_stop["at"],
                             "cause": st.cause(STATE.last_stop["attribution"])}


def drain_if_stopped(session: ds.Session) -> None:
    """THE FIRST CONTACT AFTER A STOP APPLIES WHAT WAS PENDING. A breakpoint can fire while
    the caller is doing running-guest things (a wait, a key), so the stop is not always a
    stop TOOL's reply; whichever tool comes next finds the machine at the debugger
    (passively: no console round trip) and drains the queue, and its reply carries
    `applied_on_stop`. A stop tool still drains it itself, in `stop_reply`."""
    observe_stop(session)                  # a stop nobody reported is recorded first
    waiting = (STATE.pending["arm"] or STATE.pending["disarm"] or STATE.pending["remeasure"]
               or STATE.pending["load"] is not None)
    fresh = STATE.pending["dirty"] or STATE.pending["drained_seq"] != STATE.last_stop.get("seq", 0)
    if waiting and fresh and session.at_debugger():
        arming.apply_pending(session)             # accumulates into `STATE.applied_last`


def e9_block(session: ds.Session) -> dict[str, Any]:
    """The guest's E9 lines since the previous stop, as every stop reply shows them
    (`log_marks.stop_block`, the guest channel's): the count whole, the newest few, and the mark
    they start at, from which `log` reads the rest. Unavailable with why when there is no log
    to read; a log rewritten shorter is read from its start."""
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
               made_by: dict[str, str] | None = None, by_stop: bool = False,
               **base: Any) -> dict[str, Any]:
    """What a stop ALWAYS returns, on top of the tool's own fields in `base`:
    where it stopped and by which declaration (its `cause`: a declaration matched by address, or
    why none can be named), the watches already evaluated, the registers, and the guest's E9
    lines since the previous stop (`e9_block`). `made_by`, a
    stop the calling tool made itself (`run_to`'s target, whose breakpoint is gone by now),
    is attributed to it rather than looked for among the declarations; `by_stop`, the caller's own
    `stop`, names the call when no declaration is at the address. `altered`
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
                                        retrace_may_stop=retrace_may_stop and made_by is None,
                                        held=held)
    if made_by is not None:
        # THE TOOL'S OWN STOP, and any declaration resolving to the same place named beside it.
        also = (attribution.get("refs") or [attribution["ref"]]
                if attribution.get("attributed") else [])
        attribution = {"attributed": True, **made_by, "at": attribution["at"],
                       **({"refs": also} if also else {})}
    elif by_stop and not attribution.get("attributed"):
        # A STOP THE CALLER ASKED FOR, with no declaration at its address: the call is the cause.
        # One that is there keeps its name, since the guest may have reached it as BREAK went.
        attribution = {"attributed": True, "ref": "stop", "by": "stop", "at": attribution["at"]}
    STATE.remember_stop(session, where, registers, held, attribution)
    # THIS STOP'S DRAIN IS THE ONE ABOVE: marked under the number the stop has just been given,
    # or the next contact would take it for a stop nobody drained and drain again.
    STATE.pending["drained_seq"] = STATE.last_stop["seq"]
    picture = STATE.last_stop["picture"] = code.stop_instruction(session, where, registers,
                                                                 session.survey_text)
    e9 = e9_block(session)
    # THE STOP'S NUMBER rides on its reply: it is what a batch with `summaries`
    # counts its stops by, and what `last_stop.stop_seq` later names.
    return st.reply(**{**base, **position(where, getattr(session, "paging", None))},
                    regs=st.shown_regs(registers), watches=watches,
                    cause=st.cause(attribution),
                    e9=e9, stop_seq=STATE.last_stop["seq"], **picture)


def recorded_stop_reply(session: ds.Session, recorded: dict[str, Any]) -> dict[str, Any]:
    """The enriched stop for one already recorded (`STATE.as_of_current`), built off that
    record: its registers, the watches evaluated and the E9 block read now, and the
    instruction it is on, decoded here off the screen its survey read when no reply has yet.
    Never surveyed again, which would number the same stop twice."""
    stop = STATE.last_stop
    machine = (str(stop["where"]["mode"]), dict(stop["registers"]))
    watches = arming.evaluate_watches(session, machine=machine, held=list(stop["held"]))
    if "picture" not in stop:
        stop["picture"] = code.stop_instruction(session, dict(stop["where"]),
                                                dict(stop["registers"]), session.survey_text)
    return {**recorded_head(recorded), "regs": st.shown_regs(stop["registers"]),
            "watches": watches,
            "e9": e9_block(session), **copy.deepcopy(stop["picture"])}


def stop_or_base(session: ds.Session, stopped: bool, base: dict[str, Any], *,
                 retrace_may_stop: bool = False,
                 made_by: dict[str, str] | None = None) -> dict[str, Any]:
    """The enriched stop reply when the machine STOPPED, else just the tool's base answer.
    A halt whose POSITION cannot be read (a cut pane leaves `where` refusing, which `resume`'s
    read-back meets as a stop with no position) is not discarded: the halt is a real
    observation, so the base fields stand and the enrichment is marked unavailable with why,
    rather than the whole reply becoming INVALID for a read that could not be made."""
    if not stopped:
        return st.reply(**base)
    try:
        return stop_reply(session, retrace_may_stop=retrace_may_stop, made_by=made_by, **base)
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


#: Why `status` has no `pc`, one text per cause, so its summary can say which without a second
#: field: `alive` and `running` are the session block's.
PC_RUNNING_WHY = ("the guest is running: `pc` is read off a stopped machine's register pane, and "
                  "`last_stop` says where it was last seen")
PC_GONE_WHY = "DOSBox-X has exited: `last_stop` says where the guest was last seen"


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
        facts["pc"] = contract.unavailable(PC_RUNNING_WHY if session.alive() else PC_GONE_WHY)
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
