"""Stepping one instruction at a time; `Session` delegates here.

Into is the debugger's `STEPIN`. Over is composed here, because no build types one: the
instruction at the stop is disassembled host-side, and one that would run on past the next (a
CALL, an INT, a LOOP, a REP) gets a breakpoint at the next instruction and a `RUN`.
"""

from __future__ import annotations

import time

from scry_core import cancel
from scry_core import vocabulary as vocab
from scry_core.prose import counted
from scry_core.reply_contract import Invalid

from scry_dosbox_x import debugger as dbg
from scry_dosbox_x import disasm, driving, grammar
from scry_dosbox_x import session as ds

#: The ways to step, as `step` takes them.
STEP_MODES = ("over", "into")
# THE CEILING ON ONE `step` CALL, and it is a cost bound rather than a safety one.
STEP_MAX = 64
#: How long one step may take, a step over's run past a CALL, an INT, a LOOP or a REP included.
STEP_WAIT_S = 6.0
#: The mnemonics a step over runs past with a breakpoint, beside every CALL and INT (`disasm.CALL`):
#: a REP repeats its string instruction and a LOOP its body, each before the next instruction.
STEP_OVER_WORDS = ("rep", "loop")


def check_step(mode: str, count: int) -> None:
    vocab.one_of("mode", mode, STEP_MODES,
                 ": `over` runs a CALL to its return, `into` follows it")
    if not 1 <= count <= STEP_MAX:
        raise Invalid("bad_argument",
            f"a step count is 1 to {STEP_MAX}; got {count}. Each step is a command and a "
            f"reading of where it landed, so the ceiling is a cost bound: past it, use `run_to`")


def step(ses: ds.Session, count: int, mode: str) -> dict[str, object]:
    """`Session.step`: each step's landing read back, and what an un-stepped machine refuses."""
    check_step(mode, count)
    if not ses.has("STEPIN"):
        raise dbg.missing("STEPIN", "a step")
    if mode == "over":
        # `STEPIN` answers once its instruction ran; a step over may RUN past a CALL.
        ses.require_run_state("a step over")
    # THE REFUSAL IS THIS TOOL'S, not the position reader's.
    try:
        before = ses.where()
    except ds.NotStopped:
        if not ses.alive():
            raise
        raise ds.NotStopped(
            "a step needs the machine STOPPED at the debugger, and it is running: no step "
            "was sent. Bring it back with `stop` or a breakpoint armed before it ran") from None
    after, completed, running = before, 0, False
    # COUNTED PER STEP, because comparing only the ENDPOINTS answers a different question than
    # the one `moved` is asked.
    stalled, sent = 0, 0
    left: list[str] = []
    for _ in range(count):
        position_before = after
        try:
            sent += 1
            landed, interrupted, cleanup = _one_step(ses, after, mode)
            after = landed
            left += [cleanup] if cleanup else []
            if interrupted:
                # stopped by the bound inside what it stepped over: no further step
                completed += 1
                stalled += after == position_before
                break
        except ds.NotStopped:
            if not ses.alive():
                raise
            running = True
            break
        except Invalid as exc:
            # IT REPORTS THE STEPS SENT, NOT THE ONES READ BACK.
            raise Invalid(exc.code,
                f"{exc} -- and {sent} of {counted(count, f'`{mode}` step')} had ALREADY gone "
                f"to the machine when this happened, of which {completed} were CONFIRMED landed. "
                f"They are irreversible: this debugger has no un-step, so the machine is at "
                f"least {counted(completed, 'step')} past {before['cs']}:{before['eip']} and this "
                f"call could not read where that is") from None
        if after == position_before:
            stalled += 1
        completed += 1
    return {"mode": mode, "asked": count, "completed": completed,
            "running": running, "moved": stalled < completed,
            "stalled": stalled,
            "before": before, "after": after,
            **({"note": "".join(left).strip()} if left else {})}


def _one_step(ses: ds.Session, at: dict[str, str],
              mode: str) -> tuple[dict[str, str], bool, str]:
    """One step from `at`: where it landed, whether the bound interrupted it there, and the
    sentence a reply carries when its own breakpoint could not be removed."""
    nxt = _step_over_target(ses, at) if mode == "over" else None
    if nxt is None:
        ses._release("STEPIN")
        ses.mark_stopped()
        return ses.where(), False, ""
    target = f"{int(at['cs'], 16):04X}:{nxt:04X}"
    armed = any(grammar.bp_row_target(b["entry"]) == ("BP", int(at["cs"], 16), nxt)
                for b in ses.breakpoints())
    if not armed:
        ses.command(f"BP {target}")
    began = time.monotonic()
    expired, cleanup = False, ""
    try:
        ses._release("RUN")
        expired, _ = ds.Session.await_stop(ses, began, began + STEP_WAIT_S, target,
                                           label="step over")
        if expired:
            ses.stop_at_bound()
    except Invalid as exc:
        if armed:
            raise
        with cancel.shielded():
            removed = ses.at_debugger() and driving.remove_own(ses, [target])[0][0]
        if removed:
            raise
        raise driving.still_armed(exc, target, began) from None
    finally:
        with cancel.shielded():
            if not armed and ses.at_debugger():
                [(_removed, cleanup)] = driving.remove_own(ses, [target])
    return ses.where(), expired, cleanup

def _step_over_target(ses: ds.Session, at: dict[str, str]) -> int | None:
    """The offset after the instruction at `at` when a step over must run past it, else None."""
    bits = 32 if at["mode"] == "Pr32" else 16
    cs, eip = int(at["cs"], 16), int(at["eip"], 16)
    n = disasm.INSN_MAX if bits == 32 else min(disasm.INSN_MAX, 0x10000 - eip)
    raw = ses.read_bytes(cs, eip, n, mode=at["mode"])
    first = disasm.decode(raw, eip, bits)[:1]
    if not first:
        return None
    insn = first[0]
    # a `rep ret` returns: nothing after it is reached
    runs_on = insn.flow == disasm.CALL or (insn.flow != disasm.RETURN
                                           and insn.mnemonic.startswith(STEP_OVER_WORDS))
    return eip + len(insn.data) if runs_on else None
