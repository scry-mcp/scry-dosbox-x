"""Whether the program the guest ran is still the one DOS runs, read at the stops."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

#: A line of the resident stub, not the program's.
STUB_LINE = r"(?-i:STUB[ ]{2}\.[ ])"

#: The name DOSBox-X's own command interpreter gives its memory blocks.
SHELL = "COMMAND"

#: `   0892         1168     08DD          RECHIPD`: block, size, owning PSP, name.
_MCB_ROW = re.compile(r"^\s*([0-9A-Fa-f]{4})\s+\d+\s+([0-9A-Fa-f]{4})"
                      r"(?:\s+\([^)]*\))?\s+([\w$~!-]+)")
#: What DJGPP prints on the screen as a program dies; it never reaches the E9 log.
_FAULT_FROM = re.compile(r"Exiting due to signal|General Protection Fault|Page [Ff]ault|"
                         r"Stack [Ff]ault|Invalid [Oo]pcode|Divide [Ee]rror")
_PROMPT = re.compile(r"^[A-Za-z]:\\.*>")
FAULT_ROWS = 24
#: PSP segments that name free memory and DOS itself.
_NOT_A_PROGRAM = (0x0000, 0x0008)


def owners(listing: str) -> dict[int, str]:
    """Program name by PSP segment, from `DOS MCBS`; the PSP's own block wins."""
    by_psp: dict[int, str] = {}
    own: dict[int, str] = {}
    for line in listing.splitlines():
        row = _MCB_ROW.match(line)
        if row is None:
            continue
        block, psp, name = int(row[1], 16), int(row[2], 16), row[3]
        if psp in _NOT_A_PROGRAM:
            continue
        by_psp.setdefault(psp, name)
        if block == psp - 1:
            own[psp] = name
    return {**by_psp, **own}


@dataclass
class Watch:
    """Who owned DOS at the last stop, and what became of the program."""

    psp: int | None = None
    owner: str | None = None
    running: str | None = None
    ended: dict[str, Any] | None = None


def observe(watch: Watch, psp: int | None, listing: Callable[[], str],
            screen: Callable[[], list[str] | None],
            launched: Callable[[], str | None] = lambda: None) -> None:
    """Fold in one stop's current PSP; `listing` and `screen` are read only when it changes.
    `launched` names the program the start ran once its log shows it wrote: a first stop may
    find the shell where none had seen the program."""
    if not psp:
        return
    if psp == watch.psp and watch.owner is not None:
        return
    owner = owners(listing()).get(psp)
    watch.psp, watch.owner = psp, owner
    if owner is None:
        return
    if owner == SHELL:
        if watch.running is None:
            watch.running = launched()
        if watch.running is not None and watch.ended is None:
            watch.ended = _ended(watch.running, psp, screen())
        return
    watch.running, watch.ended = owner, None


def _ended(name: str, psp: int, rows: list[str] | None) -> dict[str, Any]:
    seen = f"DOS's current process is {SHELL} (PSP {psp:04X}), no longer {name}"
    quoted = _fault(rows)
    return {"state": "fault" if quoted else "exited", "name": name, "seen_by": seen,
            **({"fault": quoted} if quoted else {})}


def _fault(rows: list[str] | None) -> list[str]:
    """The rows from a fault text's first line to DOS's prompt, without blank rows at the end."""
    for at, row in enumerate(rows or []):
        if _FAULT_FROM.search(row):
            quoted = [r.rstrip() for r in (rows or [])[at:at + FAULT_ROWS]]
            quoted = quoted[:next((i for i, r in enumerate(quoted) if _PROMPT.match(r)),
                                  len(quoted))]
            while quoted and not quoted[-1].strip():
                quoted.pop()
            return quoted
    return []


def lead(wait: dict[str, Any], gone: dict[str, Any] | None) -> str:
    """What an expired wait's note opens with: the program is gone, else the guest wrote nothing."""
    if gone is not None:
        how = "ended on a fault" if gone["state"] == "fault" else "exited"
        return f"{gone['name']} has {how} ({gone['seen_by']}), so nothing in the guest can react. "
    waited = wait.get("waited_s")
    if wait.get("arrived_during") == 0 and isinstance(waited, int | float):
        return f"the guest wrote no line in the {waited:g} s waited. "
    return ""


def watch_of(session: object) -> Watch:
    """The session's watch, made at its first stop."""
    return cast(Watch, vars(session).setdefault("_watch", Watch()))


def gone(session: object) -> dict[str, Any] | None:
    """The session's `program` block; a stand-in for a session answers too."""
    watch = vars(session).get("_watch")
    return None if watch is None else block(watch)


def block(watch: Watch) -> dict[str, Any] | None:
    return None if watch.ended is None else dict(watch.ended)
