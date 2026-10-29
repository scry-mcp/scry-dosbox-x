"""A symbol table handed to the debugger as a file, its acknowledgement held to the name sent."""

from __future__ import annotations

import contextlib

from scry_core.reply_contract import Invalid

from scry_dosbox_x import paths, symbols
from scry_dosbox_x import session as ds


def load_symbols(ses: ds.Session, data: bytes) -> list[tuple[str, int]]:
    """Put a var list into the debugger and read back what it actually holds.

    The read-back is the verification: the emulator answers `ok` for a truncated filename.
    The count is a floor, since `LV` appends and nothing empties the list.

    The two files live in somebody's project directory: an existing one is a refusal, and both
    are removed on the way out.
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
    # a DANGLING link is something there: write_bytes would create the file at its target
    present = [p for p in (into, back) if paths.taken(p)]
    if present:
        raise Invalid("bad_argument",
            f"{[str(p) for p in present]} already exists in the emulator's working "
            f"directory, which is somebody's project. This will not overwrite it: "
            f"move it aside and ask again")
    try:
        try:
            into.write_bytes(data)
        except OSError as exc:
            # `tool()` translates only `Invalid`, not a raw PermissionError
            raise Invalid("host_failed",
                f"could not write {into}: {exc!r}. The symbol file has "
                          f"to go in the emulator's working directory, because "
                          f"the debugger's filename argument survives only "
                          f"{ds.SYM_ARG_MAX} characters") from None
        out = ses.command(f"LV {ds.SYM_LOAD_NAME}")
        ses._acked(out, ds.SYM_LOAD_ECHO, ds.SYM_LOAD_NAME)
        # LV took them: the holding is at least this much more, whatever the read-back says
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
            # not an `Invalid`, and the server translates it only for parse/plan/encode
            raise Invalid("host_failed", f"the debugger saved {ds.SYM_SAVE_NAME} and it cannot be "
                          f"read back: {exc}. That is not a reading of what it "
                          f"loaded") from None
    finally:
        for p in (into, back):
            # an OSError here would replace the reasoned refusal the body raised
            with contextlib.suppress(OSError):
                p.unlink(missing_ok=True)


def vars_overflow(ses: ds.Session, data: bytes) -> str | None:
    """Why `data` cannot be loaded at all (the holding would pass `symbols.COUNT_MAX`), or None."""
    incoming = int.from_bytes(data[:2], "little")
    if ses.vars_held + incoming <= symbols.COUNT_MAX:
        return None
    return (f"the debugger's list holds {ses.vars_held} names and nothing clears it, so this "
            f"load's {incoming} would carry it past {symbols.COUNT_MAX}, which its save cannot "
            "hold. Load a narrower `pattern`, or start the session again for an empty list")


def _acked(out: str, echo: str, name: str) -> None:
    """The debugger said ok for this file on this call.

    Reads the LAST line naming the file, the one this call's command printed.
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
