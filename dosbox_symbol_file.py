"""A symbol table handed to the debugger as a file: written where the emulator reads it,
loaded, and its acknowledgement held to the name sent. Its own module because the debugger's
file commands change for reasons of their own; each function is a session method's body, and
`Session` delegates to it."""

from __future__ import annotations

import contextlib

from scry_core.reply_contract import Invalid

import dosbox_paths as paths
import dosbox_session as ds
import dosbox_symbols as symbols


def load_symbols(ses: ds.Session, data: bytes) -> list[tuple[str, int]]:
    """Put a var list into the debugger, and read back what it actually holds.

    `data` is the encoded list; the FILE is this module's business, because the
    debugger's filename argument survives only twelve characters and a caller's
    path cannot be passed through.

    IT VERIFIES BY READING THE LIST BACK, not by believing the `ok`. That is the
    same emulator that answers `ok` for a filename it silently truncated, and the
    round trip is the only thing that can say a record arrived with the name and
    the address it was given.

    THE COUNT COMES BACK AS A FLOOR AND NOT AN EQUALITY, because `LV` APPENDS
    (tests/fixtures/symbols-lv: a second load leaves both) and no debugger command empties the
    list. A caller loading twice gets both lists, and this returns everything the debugger
    holds rather than pretending the last load is all of it. The server places names from
    its own table, never the debugger's, so what an older load left there is the debugger's
    own display alone; and a load that would carry the holding past what `SV` can save
    (`symbols.COUNT_MAX`) is refused before `LV`, which would append it and then fail its
    read-back.

    The two files live in the emulator's WORKING DIRECTORY, which is somebody's
    project, so an existing file of either name is a REFUSAL rather than something
    to overwrite, and both are removed on the way out however this leaves.

    AND IT REFUSES A CONSOLE THAT IS NOT LISTENING, before the FILE is written:
    `LV` goes through the console, and one that is not listening swallows it
    without a word. See the guard below for why that is read here rather than
    inferred from the reply, and for what it does NOT claim.
    """
    if (full := vars_overflow(ses, data)) is not None:
        raise Invalid("bad_argument", full)
    for n in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME):
        if len(n) > ds.SYM_ARG_MAX:
            raise Invalid("bad_argument",
                f"{n!r} is {len(n)} characters and the debugger keeps "
                          f"{ds.SYM_ARG_MAX}; it would write a different file and "
                          f"report ok")
    into = ses.launch.cwd / ds.SYM_LOAD_NAME
    back = ses.launch.cwd / ds.SYM_SAVE_NAME
    # A DANGLING link named `SYMS.BIN` is something there (`paths.taken`): `write_bytes`
    # would create the file at the link's TARGET, anywhere on the filesystem, while the
    # cleanup below unlinked only the link.
    present = [p for p in (into, back) if paths.taken(p)]
    if present:
        raise Invalid("bad_argument",
            f"{[str(p) for p in present]} already exists in the emulator's working "
            f"directory, which is somebody's project. This will not overwrite it: "
            f"move it aside and ask again")
    # IS THE CONSOLE EVEN LISTENING? ASKED BEFORE THE FILE IS WRITTEN.
    #
    # `LV` goes through the console, and one that is not listening swallows it
    # without a word -- which arrives here as `_acked` reporting an acknowledgement
    # that never came, and that refusal would send the caller to look at filenames
    # (truncation, an older `ok`, a gone emulator) when none of them is the cause.
    #
    # THE PRECEDENT IS `step`, `run_to` AND `watch`, which all settle it first.
    # This is NOT the one caller that does not ask: `read_memory`, `set_register`,
    # `breakpoint_interrupt`, `memdump` and `selector` all type at the guest and
    # diagnose afterwards. What is closed here is ONE ROW of that table. The rest
    # are open, and two are worse than a bad message: `set_register` marks the
    # session `altered` BEFORE sending, so a refused write on a running machine
    # poisons that flag for the session's life.
    #
    # IT READS THE PANE AND NOT `where()`, which is the narrower half and the
    # deliberate one: `where()` refuses for two further reasons -- no CPU mode
    # token, a cut repaint with no CS/EIP -- and NEITHER stops a console taking
    # commands. Borrowing it would refuse loads that would have worked, which is
    # the widening `NotStopped`'s own docstring was written about.
    #
    # AND IT FAILS OPEN, WHICH IS THE PRICE OF THAT CHOICE AND IS DECLARED RATHER
    # THAN DISCOVERED: `parse_registers` is unanchored, so ONE register token
    # anywhere in the delta satisfies `_survey` -- `DS=0` inside a scrolling E9
    # line is enough. `where()`'s own comment says the same thing about it. When it
    # fails open the `LV` goes out to a deaf console and the caller lands back in
    # `_acked`, which is why `_acked` still names a RUNNING machine among what it
    # has seen. This guard narrows that window; it does not close it.
    #
    # AND IT GOES AFTER THE TWO CHECKS THAT NEED NOTHING FROM THE MACHINE, by
    # `run_to`'s precedent: reading the machine costs a settle, and a caller whose
    # working directory already holds `SYMS.BIN` should hear about that rather
    # than wait for a repaint first. That order is held in BOTH directions by
    # `test_a_running_machine_is_refused_before_a_byte_is_written` and by
    # `test_a_file_already_there_is_named_before_the_machine_is_read`, so hoisting
    # this above the two cheap checks goes red.
    try:
        ses._survey()
    except ds.NotStopped as exc:
        # WHICH CAUSE, ASKED RATHER THAN PICKED. `_survey` raises this for several
        # -- the machine is running, the pane did not repaint, the emulator died --
        # and its own comment forbids naming one as diagnosis. `alive()` is the
        # question that separates them, and it is the idiom `selector`,
        # `read_memory` and `_survey` itself already use.
        #
        # AND THE REMEDY HAS TO BE ONE THAT CAN BE CARRIED OUT from the state this
        # is raised in. "Stop it first with a breakpoint" cannot: arming one goes
        # through `self.command`, i.e. this same deaf console. And a host keypress
        # is a different path entirely, which `e9_wait`'s docstring in the server
        # explains. A refusal whose remedy cannot be carried out is the defect this
        # whole guard exists to remove, one level up.
        if not ses.alive():
            raise Invalid("session_broken",
                f"the emulator is GONE, so there is no console to take `LV` and "
                f"nothing to hold a symbol table. Start a session again. No file "
                f"was written. What the pane said: {exc}") from None
        raise Invalid("unexpected_answer",
            f"no register pane came back, so this console is not taking commands: "
            f"`LV` would be swallowed without a word, and that arrives here as an "
            f"acknowledgement that never came. The ordinary cause is a machine "
            f"that is RUNNING. AND A BREAKPOINT CANNOT BE ARMED FROM HERE TO STOP "
            f"IT: arming goes through this same console, so what stops the machine "
            f"is a breakpoint armed BEFORE it was released, or a fresh session. "
            f"No file was written. What the pane said: {exc}") from None
    try:
        try:
            into.write_bytes(data)
        except OSError as exc:
            # `tool()` translates only `Invalid`, so without this an unwritable
            # working directory escapes as a raw `PermissionError` with no session
            # block.
            raise Invalid("host_failed",
                f"could not write {into}: {exc!r}. The symbol file has "
                          f"to go in the emulator's working directory, because "
                          f"the debugger's filename argument survives only "
                          f"{ds.SYM_ARG_MAX} characters") from None
        out = ses.command(f"LV {ds.SYM_LOAD_NAME}")
        ses._acked(out, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
        # `LV` TOOK THEM: the holding is at least this much more, whatever the read-back says.
        ses.vars_held += int.from_bytes(data[:2], "little")
        out = ses.command(f"SV {ds.SYM_SAVE_NAME}")
        ses._acked(out, ds.SYM_SAVE_ECHO, ds.SYM_SAVE_NAME)
        if not back.exists():
            raise Invalid("unexpected_answer",
                f"the debugger reported saving {ds.SYM_SAVE_NAME} and no such file "
                f"is in {ses.launch.cwd}. Those disagree, so nothing here is a "
                f"reading of what it loaded")
        try:
            held = symbols.decode(back.read_bytes())
            ses.vars_held = len(held)
            return held
        except (symbols.BadSymbolText, OSError) as exc:
            # `BadSymbolText` is NOT an `Invalid` (a distinct type "so the MCP layer can
            # translate it"), and the server translates it for `parse`/`plan`/`encode`, not
            # for this call: a MALFORMED file from the emulator is translated here, or it
            # would escape as a traceback.
            raise Invalid("host_failed", f"the debugger saved {ds.SYM_SAVE_NAME} and it cannot be "
                          f"read back: {exc}. That is not a reading of what it "
                          f"loaded") from None
    finally:
        for p in (into, back):
            # SUPPRESSED, and only here: an `OSError` out of the cleanup would
            # REPLACE whatever the body raised, so a reasoned refusal about the
            # debugger would be handed over as a `PermissionError` about a file.
            with contextlib.suppress(OSError):
                p.unlink(missing_ok=True)


def vars_overflow(ses: ds.Session, data: bytes) -> str | None:
    """Why `data` cannot be loaded into this session's debugger at all, or None: `LV` appends and
    nothing clears the list, and `SV` cannot save one past `symbols.COUNT_MAX`, so a load that
    would carry the holding past it would append and then fail its read-back. Nothing but a new
    session changes that answer."""
    incoming = int.from_bytes(data[:2], "little")
    if ses.vars_held + incoming <= symbols.COUNT_MAX:
        return None
    return (f"the debugger's list holds {ses.vars_held} names and nothing clears it, so this "
            f"load's {incoming} would carry it past {symbols.COUNT_MAX}, which its save cannot "
            "hold. Load a narrower `pattern`, or start the session again for an empty list")


def _acked(out: str, echo: str, name: str) -> None:
    """The debugger said ok FOR THIS FILE, ON THIS CALL.

    Searching the delta for `ok` alone is not enough and that is the first point of
    this method: the filename is truncated at twelve characters without complaint,
    so `ok` can be a true statement about a file the caller never named.

    AND THE OCCURRENCE MATTERS AS MUCH AS THE NAME. `in` takes ANY occurrence in the
    delta, and the debugger's Output pane is a scrolling log whose repaint carries
    earlier replies along with it -- so on
    a SECOND `load_symbols` over one session, the FIRST call's `... : ok.` is still
    on screen and satisfies a check about a `LV` that has just answered `failure.`.
    Loading twice is documented usage, because `LV` appends. So it reads the LAST
    line that names this file, exactly as `selector` anchors with `rfind`: the
    same hazard, solved the same way in this class.

    It takes no `self`: nothing here touches the session.
    """
    head = f"{echo} ({name}"
    at = out.rfind(head)
    if at >= 0 and out[at:].startswith(head + ds.SYM_OK):
        return
    raise Invalid("unexpected_answer",
        f"the debugger did not acknowledge `{echo}` for {name!r} on this call. It "
        f"truncates a filename to {ds.SYM_ARG_MAX} characters and reports ok for "
        f"whatever it used, so an acknowledgement naming anything else is not this "
        f"one -- and an OLDER ok for this same name is not this one either. THE "
        f"SHOWING BELOW IS WHAT DISCRIMINATES, and it is read rather than guessed "
        f"at: EMPTY is the debugger saying nothing at all, which is what a gone "
        f"emulator looks like from here, and the GUEST'S OWN INSTRUMENTATION "
        f"scrolling past is a machine that is RUNNING, whose console takes no "
        f"commands and swallowed this one without a word. Those three are what has "
        f"been seen, not a closed list. What it showed: {out.strip()[-300:]!r}")
