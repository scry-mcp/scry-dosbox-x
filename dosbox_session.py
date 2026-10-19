"""One live DOSBox-X session, held open, and the pseudo-terminal that drives it.

WHY A PSEUDO-TERMINAL AND NOT A PIPE.  DOSBox-X's debugger is ncurses, and its own
README says so: "On other systems including Linux and Mac OS X, DOSBox-X must be
started from a terminal in order to enable the debugger."  ncurses talks to a
TERMINAL, so a pipe is the wrong instrument and would fail for a reason that has
nothing to do with the question.

ECHO IS TURNED OFF BEFORE ANYTHING IS SPAWNED.  A terminal echoes by default, in the
driver rather than in the child, so it echoes whether or not the child exists.
MEASURED while this was being built: with no DOSBox-X running at all, a probe that
looked for its own command words in the terminal's output scored three of five checks
TRUE.  The stronger defence is the one in `command()`, which hands back only the
DELTA a command produced rather than a search over everything that ever arrived; echo
off covers the window before ncurses owns the terminal.

THE SESSION IS ONE OBJECT AND ITS GRAMMARS ARE NOT: what a session is launched with, judged and
built into a command line, is `dosbox_launch`'s; what the console prints, parsed, is
`dosbox_console`'s; the log's channels and filters are `dosbox_logs`'s; and the files the emulator
wrote, collected to where the caller asked, are `dosbox_collect`'s.
"""

from __future__ import annotations

import contextlib
import os
import pty
import re
import select
import shutil
import signal
import socket
import subprocess
import termios
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from scry_core import avi, cancel
from scry_core.progress import PROGRESS_EVERY_S as PROGRESS_EVERY_S
from scry_core.progress import Progress as Progress
from scry_core.progress import no_progress as no_progress
from scry_core.reply_contract import Invalid as Invalid

import dosbox_collect as dcollect
import dosbox_console as dcons
import dosbox_control as control
import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_paths as paths

# The var-list ENCODING lives next door, in a module with no emulator in it, so a
# golden can exist over the bytes without a machine. This file owns only the part that
# needs one: reading a descriptor base, and getting the file past a debugger that
# truncates its filename argument.
#
# IT IS `dosbox_symbols` AND NOT `symbols` for the reason `dosbox_x_server` records
# about its own name: a process that holds more than one Scry server imports them
# into one namespace, so a bare top-level `symbols` here would bind to whichever package
# imported one first, and a reverse-engineering pack is the kind of project that grows a
# `symbols.py` of its own.
import dosbox_symbols as symbols

# HOW LONG A HELD HEAD MAY GET before it is given up and emitted as text.
#
# The hold has to be bounded in SOME way, because an OSC with no terminator matches
# this pattern from the first byte of every subsequent read, so a hold with no limit
# swallows the whole stream and the reader goes permanently blind while reporting
# nothing wrong. What the hold may NOT be bounded by is the head's POSITION, which is
# what it was: `held.start() > 0` gave up precisely when the ESC was the first byte of
# the read, i.e. exactly when the head was ALL there was to hold.
#
# MEASURED on a real captured data row with one SGR change repainted mid-row and the
# same escape split three ways: whole in one read -> 1 row; split with text before the
# ESC -> 1 row; split with the ESC as the first byte -> ZERO rows, because the head was
# stripped as a lone fragment and its final byte `m` was then injected into the row's
# hex. `read_memory` answers that with INVALID -- a false one, from the narrow reader
# whose whole purpose is not lying about what it examined, and only when the chunk
# boundary happened to fall there.
#
# 4 KB is far past any real escape (the longest this debugger emits is a dozen bytes)
# and far short of a screenful, so the give-up arm is unreachable for well-formed input
# and prompt for the malformed kind.
PENDING_MAX = 4 * 1024


# HOW LONG A CONSOLE REPLY IS GIVEN (`Session.command`): quiet for `SETTLE_S` once something
# has arrived ends it, or for `REPLY_GRACE_S` when it ends in the debugger's own last words, and
# `REPLY_TIMEOUT_S` bounds it whatever arrives.
SETTLE_S = 0.6
REPLY_TIMEOUT_S = 6.0
# A reply that ends in the debugger's own last words (`dosbox_console.REPLY_END`) is whole after
# `REPLY_GRACE_S` of quiet, a margin over the gaps between the pieces of one reply; anything else
# (a command typed at a running guest) keeps the settle.
REPLY_GRACE_S = 0.15
# How the collect slices its wait, and how much raw terminal it keeps to look for that end.
COLLECT_SLICE_S = 0.05
RAW_TAIL_KEEP = 512


# WHERE EACH SETTABLE NAME IS READ BACK, and at what width in bits. The pane paints the 32-bit
# general registers and the 16-bit segments and nothing else: a segment is read under its own
# name (there is no `ECS`), and a 16-bit general name (`ax`) as the low half of the register
# one letter longer (`EAX`), since the whole register also carries a high half the write never
# touched.
READBACK: dict[str, tuple[str, int]] = {
    **{n.lower(): (n, 32) for n in dcons.WIDE_NAMES},
    **{n.lower(): (n, 16) for n in dcons.SEGMENT_NAMES},
    **{n: (f"E{n.upper()}", 16) for n in dcons.LOW_HALVES},
}

# A command that is guaranteed to REPAINT and changes nothing. `registers()` needs
# one: an empty line produces no repaint at all, so parsing its delta always found an
# empty pane and every register read came back INVALID.
#
# IT IS `BPLIST` AND THAT IS NOW LOAD-BEARING RATHER THAN INCIDENTAL: one repaint
# carries the register pane, the CPU mode token AND the breakpoint list, so `where()`
# gets the position and the mode from a SINGLE screen. It was chosen for being
# harmless; it turns out to be the most informative harmless command this debugger has.
#
# WHAT IT DOES NOT BUY: the readers do not share a round trip WITH EACH OTHER.
# `registers()`, `where()` and `breakpoints()` each call `_survey()`, and each `_survey()`
# sends its own `BPLIST`.
# One `run_to` therefore costs five of them. Sharing across calls would mean caching a
# screen, and a cached screen is a stale reading waiting to be handed over -- which is
# the trade this module refuses everywhere else.
NUDGE = "BPLIST"


# The keys the debugger's own help names: "F5 - Run." and "F10/F11 - Step over /
# trace into instruction." They go as terminal escape sequences with NO carriage
# return, exactly as `resume` sends F5: a return belongs to a typed command, and on
# this path it would land on a guest that is already running.
#
# MEASURED HERE, and only for F10: from reset at F000:FFF0, whose instruction is
# `jmp F000:E05B`, F10 lands at E05B. That is what the live case asserts.
#
# AN EARLIER NOTE CLAIMED F11 LANDS AT C9B0 FROM THE SAME POINT, and it is deleted
# rather than kept, because it cannot be reconciled with this file's own model: a `jmp`
# is neither a CALL nor an INT, so `over` and `into` must land in the SAME place, and
# `F000:E05B` is itself `jmp F000:C9B0`. Either that reading is right and the note was a
# misattributed second step, or one F11 executes two instructions -- in which case
# `step(mode="into")` reports `completed: 1` for an unknown number of instructions.
# NOT MEASURED HERE either way, so nothing here asserts it.
STEP_KEYS = {"over": b"\x1b[21~", "into": b"\x1b[23~"}

# F5, "Run.". It is a CONSTANT because two methods send it -- `resume` and the resume
# inside `run_to` -- and a second copy of an escape sequence is a second thing to get
# wrong, silently: a wrong key here does not fail, it does something else to the
# machine and the caller reads the reply as if the machine had run.
RUN_KEY = b"\x1b[15~"
# `VRT`: run, and stop at the next vertical retrace. A command typed with its return, and a
# release all the same, so it is written here and nowhere else (`run_for` is its one sender).
RETRACE_COMMAND = b"VRT\r"
# Every key that can leave the machine RUNNING, `run_for`'s typed `VRT` among them: what
# `at_debugger` is cleared by. Any other typed command that does the same is refused by `debug`
# (`dosbox_checks.DEBUG_RELEASES`).
RELEASE_KEYS = (RUN_KEY, STEP_KEYS["over"], STEP_KEYS["into"], RETRACE_COMMAND)
# THE `LOG` FAMILY, one word per line shape: typed with its hex count, each opens the CPU log and
# RELEASES the guest until the count runs out or a stop cuts it, so it clears `at_debugger` as a
# run key does. Spelled once here: `Session.log_cpu` types it and `debug` refuses it.
LOG_WORDS = ("LOG", "LOGS", "LOGL", "LOGC")
LOG_COMMAND = re.compile(rb"(?:" + "|".join(LOG_WORDS).encode() + rb") [0-9A-F]+\r")

# THE CEILING ON ONE `step` CALL, and it is a cost bound rather than a safety one.
#
# Every step is a keystroke and then a repaint that has to be READ BACK, because a
# step over a `CALL` is implemented as run-until-it-returns and a call that does not
# return leaves the machine RUNNING with the remaining keystrokes going nowhere. So
# the position is re-established after each one, which costs a settle per step; the cap
# bounds what a single question costs, and past it the caller wants `run_to`, which pays
# the settle once.
STEP_MAX = 64


# `MEMDUMPBIN [s]:[o] [len] [filename]` writes memory to a file in the debugger's working
# directory. `MEMDUMP_NAME` is the build's DEFAULT name, collected for a build that takes no
# file name; `MEMDUMP_FILE` is the one `memdump` passes.
MEMDUMP_NAME = "memdump.bin"
# Passed because a build whose parser reads an optional name and is given none reads that name
# from past the end of the line, so its file lands under a fragment of the arguments; a build
# that takes no name ignores it. Upper case and relative for the reason `INTVEC_FILE` is: the
# debugger upper-cases the line and writes into its working directory.
MEMDUMP_FILE = "MCPDUMP.BIN"
# The two lines `SaveMemoryBin` prints (upstream `src/debug/debug.cpp`): the binary dump's
# failure is NOT the text dump's "Memory dump failed". The Output pane is a scrollback, so the
# verdict is the LAST of the two on the screen; an earlier dump's success line is still there.
MEMDUMP_OK = "Memory dump binary success"
MEMDUMP_FAIL = "Memory binary dump failed"

# `INTVEC <file>` writes the vector table into the emulator's WORKING DIRECTORY, one line per
# vector (`INT nn:  SSSS:OOOO`), and the debugger upper-cases the whole command line, so the
# name is upper case here already. In real mode the file is the table at 0000:0000; in
# protected mode it is the IDT, selector pairs.
INTVEC_FILE = "MCPIVT.TXT"
INTVEC_OK = "Interrupt vector table written to"

# `SELINFO [segName]` prints `DS: b:00400000 type:13 parbg / l:0023FFFF dpl : 3 10011`, the
# five digits under `parbg`'s letters: present, available, reserved, big (the D/B bit, the
# width a code segment decodes in) and granularity (upstream `debug.cpp`, `SELINFO`). The
# base is the whole reason a symbol table can be placed at all: a toolchain emits
# OFFSETS and this debugger's var list stores LINEAR addresses, so `linear = base +
# offset` and nothing else can supply the base.
#
# IT TAKES A REGISTER NAME AND NOT A SELECTOR NUMBER, measured: `SELINFO AF` came back
# with an EMPTY name and a zeroed descriptor -- `: b:00000000 type:00 ... l:00000000` --
# rather than refusing. So a caller may only ask about a selector some register is
# currently holding, and asking about a number gets a plausible answer about nothing.
SELINFO_ECHO = "SelectorInfo"
# THE `.*?` BETWEEN `type:` AND `l:` IS BOUNDED, and that bound is the whole of its
# correctness. The answer arrives as TWO lines (`... parbg` then `l:0023FFFF ...`), so
# something has to span the break -- but unbounded under `re.S` it will happily run on
# to the NEXT descriptor's limit if this one's did not arrive, and report a base from
# one descriptor with a limit from another. MEASURED on constructed screens: fields
# 30,020 characters apart were stitched into one answer. The limit is the independent
# fact a caller checks the base against, so a limit belonging to somebody else is
# exactly the "hands the caller's own assumption back as evidence" failure the server's
# docstring names. 64 characters covers the real gap (the flag column plus a newline)
# and cannot reach a neighbouring descriptor.
SELINFO_FIELDS = re.compile(
    r"b:([0-9A-Fa-f]{8})\s+type:([0-9A-Fa-f]{2}).{0,64}?l:([0-9A-Fa-f]{8})"
    r"\s+dpl\s*:\s*([0-3])\s+([01])([01])([01])([01])([01])", re.S)


# A descriptor with `type:00` IS NOT PRESENT, and returning its base would be the
# worst answer this module can give: zero, which is a perfectly plausible base and
# would place every symbol at its raw offset. MEASURED, TWO different situations
# produce it, and neither is an error the debugger reports:
#
#   SELINFO CS  at `-break-start` (REAL MODE)  -> b:00000000 type:00 l:00000000
#   SELINFO AF  (a selector NUMBER, not a register name) -> the same, with an
#               empty name where the register would be
#
# Against a real protected-mode program the same command reads `type:1B` for code and
# `type:13` for data, so zero is the discriminator.
#
# THIS COMMENT USED TO SAY "bit 7 of that byte is the descriptor's PRESENT flag", AND
# THAT IS FALSE -- it was offered explicitly as "not a heuristic", which is the worst
# way to be wrong. Bit 7 is CLEAR in all four descriptors this package has captured,
# three of them present. The emulator's own format string is
# `%s: b:%08lX type:%02X parbg\n    l:%08lX dpl : %01X %1X%1X%1X%1X%1X`: `type` is the
# 5-bit S|type field (so at most 0x1F), and P is the first digit of the `parbg` column
# -- `10011` for the two present ones, `00000` in real mode. The guard is still right,
# for the real reason: a 5-bit type of 0 is a reserved descriptor type that cannot be
# loaded into a segment register at all.
SELINFO_ABSENT = 0
SELINFO_REGS = ("CS", "DS", "ES", "SS", "FS", "GS")

# `SV`/`LV` acknowledge with `Variable list save (NAME) : ok.` / `: failure.`, and the
# NAME they echo is the one they actually used -- which is not necessarily the one that
# was asked for. See `SYM_ARG_MAX`.
SYM_SAVE_ECHO = "Variable list save"
SYM_LOAD_ECHO = "Variable list load"
SYM_OK = ") : ok."

# A `SV`/`LV` FILENAME IS CUT TO TWELVE CHARACTERS, SILENTLY, AND REPORTED `ok`.
# MEASURED: `SV ABCDEFGHIJKLMNOPQRST.BIN` answered
# `Variable list save (ABCDEFGHIJKL) : ok.` and wrote a 144,762-byte file named
# `ABCDEFGHIJKL`, with no extension, into the emulator's working directory. An absolute
# path fails the same way and at least says so: `/private/tmp/claude-501/...` echoed
# `(/PRIVATE/TMP)` and `: failure.`
#
# So the names below are chosen to FIT, and the acknowledgement is compared against the
# name that was sent rather than merely searched for `ok` -- the echo is the only thing
# that can reveal a truncation, and it is the reason this module reads it at all.
SYM_ARG_MAX = 12
SYM_LOAD_NAME = "SYMS.BIN"
SYM_SAVE_NAME = "SYMSBK.BIN"


# THE CEILING ON ONE `run_to` WAIT, which is a different bound from the session's and
# needs its own reason. The session's bound stops an abandoned emulator; this one stops
# an abandoned QUESTION. A wait blocks the server's lock for its whole duration, so
# every other tool -- `status` and `e9` included, the two a caller reaches for when
# something looks stuck -- is unanswerable until it ends. Ten minutes is far past any
# breakpoint that is going to fire and short enough that a session is never wedged for
# an afternoon by one call.
RUN_TO_MAX = 10 * 60

# How often `e9_wait` re-reads the log while waiting. It is a POLL and not a watch,
# because the log is appended to by a process this does not own and there is no portable
# way to be woken by that. A tenth of a second is far finer than any question asked of a
# guest's own instrumentation and coarse enough that a ten-minute wait is six thousand
# reads rather than a spin.
E9_POLL = 0.1
#: How much of the newest line a waiting `log_wait` shows in its progress line.
LAST_LINE_SHOWN = 40
# A BOUNDED WAIT REPORTS PROGRESS WITH A MESSAGE, through a callback the server hands in, and
# polls for its call's cancellation at every turn: the vocabulary is `scry_core.progress`'s and
# `scry_core.cancel`'s, the same on every Scry server, so this module knows nothing of the
# protocol's `Context` and a test hands in a list.

# `_screen` is trimmed to this. A session held open for an investigation accumulates
# megabytes of repaints, and every append copied the whole buffer; `command()` no
# longer indexes into it, so trimming is safe.
SCREEN_KEEP = 256 * 1024

# THE TERMINAL IS DRAINED BY A THREAD, AND THAT IS NOT AN OPTIMISATION.
#
# A pty master's buffer is FINITE, and when it fills, the WRITER blocks -- in the
# kernel, not in anybody's code. The writer here is the emulator, so a session whose
# only reader is a tool call FREEZES THE MACHINE between questions.
#
# MEASURED during a QA round, and it is why this is a thread and not a longer timeout:
# three sessions sat at EXACTLY the same guest instant (`[+ 2.091]`, 20% of a
# soundfont load) for 105, 48 and 36 seconds of wall clock, and a single `registers`
# call moved the guest 7 seconds forward. Controls: with video capture and without,
# launched with `-c` and from the conf's `[autoexec]` -- the stall was identical, so
# neither is the cause. The same program in a batch run reached `[+ 27.463]` playing.
#
# It also explains why the contract tests could not see it: they always have a call
# in flight, which is precisely the condition under which the defect does not exist.
#
# THE NUMBER, which is a different question from the thread and needs its own reason.
# It is a CEILING ON MEMORY, not a working set: a repaint of this debugger's screen is
# ~4 KB, so 4 MB is about a thousand of them, far more than any reply needs and small
# enough that a session forgotten for an afternoon cannot grow without bound. It is
# deliberately LARGER than `SCREEN_KEEP` (256 KB), which is what `_screen` retains
# afterwards: the two bound different things, and reaching this one is an event a
# caller is told about (`_read` refuses the reading) while reaching that one is not.
DRAIN_KEEP = 4 * 1024 * 1024

# How long `close()` waits for the drain thread before it stops trusting it. It is a
# teardown budget, not a guess about the work: the thread's loop wakes every 0.05 s, so
# anything past a few tenths of a second means it is not coming back, and the caller is
# waiting on a session they have already asked to end.
DRAIN_JOIN_SECS = 2.0

# How long `ffmpeg` is given to pull one frame out of a capture. It is named rather
# than inline because it is the ONE bound in this module belonging to a tool that is
# not ours, and because `frame()` has to CATCH its expiry: `tool()` translates only
# `Invalid`, so a hung ffmpeg escaped as a raw `TimeoutExpired` traceback while
# `build_check` catches exactly that exception for exactly this reason.
FFMPEG_SECS = 120

# HOW LONG SIGTERM IS BELIEVED IN. Every session is launched with the emulator's quit
# warning OFF, and with it off a guest holding a program answers the TERM at once, running
# or stopped, in a window or headless: so this is a bound and not a wait the ordinary close
# spends. It stays small because what can still ignore the signal (a conf that puts the
# warning back, a build that does not answer under a pty) is not slow but deaf, and the
# SIGKILL behind it cannot be ignored. It is separate from the post-KILL reap budget so a
# close waits in proportion to what the wait can achieve; on a WATCHED session that wait
# sits on somebody's screen. The measured figures belong in the commit that took them.
TERM_GRACE = 2.0


# How often `wait_exit` asks whether the process is gone.
EXIT_POLL_S = 0.1


def wait_exit(proc: subprocess.Popen[Any], seconds: float, progress: Progress,
              what: str) -> int | None:
    """The process's exit code within `seconds`, or None: a `proc.wait(timeout)` that reports
    its progress, because `close` is a wait the owner watches and a quit that takes seconds
    looks exactly like a hung server without the line."""
    t0 = time.monotonic()
    next_tick = t0 + PROGRESS_EVERY_S
    while True:
        cancel.check()
        # SLICES OF THE REAL `wait`, not a `poll` loop: `wait` is what reaps the child, and
        # what the doubles of `close` speak.
        try:
            return int(proc.wait(timeout=EXIT_POLL_S))
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if now - t0 >= seconds:
            return None
        if now >= next_tick:
            next_tick = now + PROGRESS_EVERY_S
            progress(now - t0, None, f"{what}, {now - t0:.0f}s of {seconds:g}s")


# THE REFUSAL is `scry_core.reply_contract.Invalid` (a code of the
# table, the prose, the context), imported above so every module here raises one name.
# The three types below are the causes two callers act on and must not confuse, and each
# fixes its code in its constructor: a site cannot raise `NotStopped` under another word.


class NotStopped(Invalid):
    """No register pane came back: the machine is not stopped at the debugger, or it
    is gone.

    IT IS A SEPARATE TYPE BECAUSE TWO CALLERS ACT ON THIS CAUSE AND MUST NOT ACT ON ITS
    SIBLINGS. `step` and `run_to` both catch a failure to read the position and conclude
    "the machine is running" -- and `where()` refuses for three different reasons: no
    pane at all, a pane that names no CPU mode, and a partial pane carrying no CS/EIP.
    Catching the base class turned the last two into a confident diagnosis of a cause
    that had not been observed. MEASURED: a STOPPED machine whose pane carried no mode
    token was reported by `run_to` as "the bound expired with the machine still running,
    and the breakpoint is STILL ARMED -- it cannot be removed while the debugger is not
    listening", every clause of which was false.

    This package's thesis is that an INVALID says what it examined. A handler that
    widens one refusal into three inverts it, in the reply a caller reasons hardest
    about.
    """

    def __init__(self, message: str, **fields: Any) -> None:
        super().__init__("not_stopped", message, **fields)


def _wait_stopped(pattern: str, arrived: int, waited_s: float,
                  bound: float | None = None) -> Invalid:
    """The refusal a wait gives for a machine at the debugger, the loop's and the expiry's in
    one shape, so the two cannot drift: a stopped guest writes nothing, the wait cannot end,
    and "still running" there would be about the process. The count is what was ON
    DISK, said as such: the emulator flushes its log in its own time, so a line the guest
    wrote before the stop can reach the file after this refusal (three lines stamped before
    the stop, read by `e9` afterwards, counted 0 here)."""
    when = (f"the bound of {bound}s expired and the machine is stopped at the debugger"
            if bound is not None else "the machine is stopped at the debugger")
    return E9Stopped(
        f"{when}, so a wait for {pattern!r} cannot end: a stopped guest writes nothing. "
        f"{arrived} line(s) were on disk from the wait's start to this refusal, none "
        f"matching; the emulator flushes its log in its own time, so `e9` may show more. "
        f"Resume it rather than waiting", waited_s=waited_s, arrived=arrived)


class E9Stopped(Invalid):
    """A wait that cannot end because the machine is at the DEBUGGER: a stopped guest writes
    nothing. Its own type because the server answers it differently from `E9Expired` -- the
    stop is named, with where the posted key went -- and from a broken instrument.
    `waited_s` is how long it looked before refusing and `arrived` how many lines were on
    disk in that time, so the reply can carry both as fields and not only as prose."""

    def __init__(self, message: str, *, waited_s: float, arrived: int) -> None:
        super().__init__("wait_stopped", message)
        self.waited_s = waited_s
        self.arrived = arrived


class E9Expired(Invalid):
    """`e9_wait` watched the whole bound, the channel was there, and nothing matched.

    A SEPARATE TYPE for the same reason `NotStopped` is one: a caller that turns a wait
    into a verdict ("the guest did not react to the key") must act on THIS cause and not
    on the other causes. `e9_wait` refuses for four things after it starts looking -- the
    bound expired, the machine STOPPED at the debugger (`E9Stopped`), the emulator is
    GONE, the log SHRUNK underneath -- and only the first two are observations about the
    guest. The other two are the instrument breaking, and a
    handler catching the base class turned a dead emulator into "the program swallowed
    the key", with the truth appended at the end of the sentence.
    """

    def __init__(self, message: str) -> None:
        super().__init__("wait_expired", message)


def avi_facts(data: bytes) -> dict[str, object]:
    """What is IN a capture, not merely how big it is.

    A recording that captured nothing and one that captured a whole session are both
    files of a plausible size, so the size has never been the evidence. `idx1` is the
    index, which is written when the recording STOPS -- so a capture without one is not
    corrupt, it is still in progress.
    """
    return {
        "bytes": len(data),
        "riff_avi": data[:4] == b"RIFF" and data[8:12] == b"AVI ",
        "frames": avi.count(data),       # `scry_core.avi` says which count and why
        # `complete` is INFORMATION, not a usability verdict: MEASURED, ffmpeg
        # extracts a frame from an unindexed capture perfectly well. What it says is
        # that the recording was FINALISED -- which happens when the recorded program
        # exits or the emulator exits cleanly, and NOT when the session is closed
        # underneath it.
        "complete": avi.finished(data),
    }


SCREENSHOT_COMMAND = b"S"   # the stub's opcode for the device's capture trigger (guest/inject.asm)
COMMAND_GAP_S = 0.06    # the pause between stub commands: just over one 18.2 Hz timer tick


BREAK_IN_WAIT_S = 5.0     # from BREAK on the channel to the debugger's prompt on the terminal
SNAPSHOT_WAIT_S = 10.0
# A STATE IS SAVED AND LOADED BY THE DEBUGGER'S OWN COMMANDS, `SAVESTATE <file>` and
# `LOADSTATE <file>` over the debugger channel, which only a DOSBox-X carrying them has (the
# Optimiza/dosbox-x fork, proposed upstream): no window, no menu, no dialog, and the reply
# says whether it acted. They need the debugger stopped, because loading a state replaces the
# timer's tick handlers and the channel is served from one while the guest runs. The bound is
# the command's reply: a state of a large machine is written for a second or two.
STATE_WAIT_S = 30.0


# ------------------------------------------------------------------ argument checks
# THE CHECKS THAT NEED NOTHING FROM THE MACHINE LIVE HERE AS FUNCTIONS, one per argument
# family, and the session methods call them first. They are also what `perform` runs over a
# WHOLE list before its first step: a batch enters through the same checks the synchronous
# call makes, so a value that would be refused mid-list is refused before anything ran.


def check_register_name(name: str) -> str:
    """The lower-case register `SR` takes, or the refusal naming the ones it does."""
    key = name.strip().lower()
    if key not in dcons.SETTABLE:
        raise Invalid("bad_argument", f"{name!r} is not a register this debugger sets. One of: "
                      f"{', '.join(sorted(dcons.SETTABLE))}")
    return key


def check_register_value(key: str, value: int) -> None:
    """A value `SR` can put in register `key`: within its width (`READBACK`), never negative,
    refused before anything is sent."""
    bits = READBACK[key][1]
    if value < 0:
        raise Invalid("bad_argument",
            f"value={value} is negative: {key} holds {bits} bits, 0 to {(1 << bits) - 1:#x}; "
            f"nothing was sent")
    if value >= 1 << bits:
        raise Invalid("bad_argument",
            f"value={value:#x} is wider than {key}'s {bits} bits (at most "
            f"{(1 << bits) - 1:#x}): nothing was sent")


def check_interrupt(number: int, ah: int | None) -> None:
    if not 0 <= number <= 0xFF:
        raise Invalid("bad_argument", f"an interrupt number is 0x00 to 0xFF; got {number}")
    if ah is not None and not 0 <= ah <= 0xFF:
        raise Invalid("bad_argument", f"AH is 0x00 to 0xFF; got {ah}")


def check_step(mode: str, count: int) -> None:
    if mode not in STEP_KEYS:
        raise Invalid("bad_argument", f"{mode!r} is not a way to step. It is one of "
                      f"{', '.join(sorted(STEP_KEYS))}: `over` runs a CALL to its "
                      f"return, `into` follows it")
    if not 1 <= count <= STEP_MAX:
        raise Invalid("bad_argument",
            f"a step count is 1 to {STEP_MAX}; got {count}. Each step is "
                      f"a keystroke AND a repaint read back to prove it landed, so "
                      f"the ceiling is a cost bound: past it, use `run_to`")


def check_wait_bound(seconds: float) -> None:
    """A wait is a bound: more than zero and at most `RUN_TO_MAX`, because with no ceiling
    the call would sit on something that is never going to arrive, holding the session's
    lock while it did."""
    if not 0 < seconds <= RUN_TO_MAX:
        raise Invalid("bad_argument",
            f"a wait of {seconds} is not a bound. It is more than zero "
                      f"and at most {RUN_TO_MAX}s: with no ceiling this would sit "
                      f"waiting for something that is never going to arrive, holding "
                      f"the session's lock while it did")


def check_dump_length(length: int) -> None:
    if length <= 0:
        raise Invalid("bad_argument", f"a dump of {length} bytes is not a dump")


def check_frame_args(at: int, dest: Path) -> None:
    """A frame index and a destination ffmpeg will not misread. A `%` ANYWHERE in the
    destination is refused: `-f image2` treats the WHOLE PATH as a printf template, so
    `shot%03d.png` writes `shot001.png` and leaves `dest` untouched, and a `%` in a parent
    misplaces the still exactly as one in the name does. Broader than the hazard on purpose
    (ffmpeg leaves a `%` with no valid conversion alone): that direction fails loudly, the
    other silently."""
    if at < 0:
        raise Invalid("bad_argument", f"frame {at} is not a frame")
    if "%" in str(dest):
        raise Invalid("bad_argument",
            f"a destination containing `%` is refused: {str(dest)!r}. "
                      f"The still is written through ffmpeg's image2 muxer, which "
                      f"reads the whole path as a numbering template and writes "
                      f"somewhere else")


def _still_armed(exc: Invalid, target: str, began: float, ctl: str | None = None) -> Invalid:
    """The refusal that CARRIES the irreversible part: a trap byte is in the guest and the row is
    still armed -- and so is the control, when one was armed, since a caller who clears only the
    target is stopped later at an address they never named."""
    also = f" (and so is the control at {ctl})" if ctl else ""
    return Invalid(exc.code,
                   f"{exc} -- and the breakpoint at {target}{also} is STILL ARMED after "
                   f"{round(time.monotonic() - began, 1)}s: this call wrote a trap byte "
                    f"into the guest and could not read the machine back to remove it, so "
                    f"it will stop the next `resume`")


def console_listening(session: Session, what: str) -> None:
    """Refuse, before anything is typed, a command for a console that is not listening: on
    a running guest it lands at the next stop, unread, and the reply read now is not its."""
    if not session.at_debugger():
        raise NotStopped(f"the guest is running, so the console cannot take {what}: a "
                         "command typed now lands at the next stop, unread")


def check_segment(seg: int) -> None:
    """A real-mode segment, held to sixteen bits: one sentence for every tool that takes one."""
    if not 0 <= seg <= 0xFFFF:
        raise Invalid("bad_argument", f"a segment is 0x0000 to 0xFFFF; got {seg}")


class Session:
    """A DOSBox-X process that stays put between questions.

    THE THREE THINGS ITS CONTRACT ENFORCES, so they do not depend on anyone
    remembering:

    * A session it cannot reproduce is REFUSED, and refused BEFORE the process
      exists. A guarantee that leaves alive what it just declared invalid is not a
      guarantee.
    * A read that found nothing says which KIND of nothing it found. "No line matched"
      and "there was no log to match against" are different answers and only one of
      them is a result.
    * A session that has been WRITTEN to carries `altered` in every later reply, the
      INVALID ones included. A measurement taken on a forced state is not a
      measurement of the program, and an INVALID reply is exactly the one a caller
      reasons hardest about.
    """

    def __init__(self, launch: dlaunch.Launch) -> None:
        dlaunch.validate(launch)
        self.launch = launch
        self.conf_digest = dlaunch.digest(launch.conf)
        self.altered = False
        # THE STUB'S PROTOCOL once the guest announced it (`dosbox_inputs.require_stub`), so
        # the log is searched for the announce once per session, not once per key.
        self.stub_protocol = ""
        self.started_at = time.monotonic()
        self._screen = ""
        self._at_debugger = False   # set by the prompt, cleared by a run key
        self.stop_count = 0         # how many times the flag went False -> True: each is a
        #                             stop the server may not have observed through a tool
        self.paging: bool | None = None   # the last stop survey's PAGE/NOPG, None unread
        self.survey_text = ""                 # the last stop survey's screen, its code pane
        self.pane_clock_ms: float | None = None   # `pfi=` of the last stop or placing survey
        self.pane_cycles: int | None = None       # `cc=` of the same survey
        self._peek_carry = ""       # the tail of the last passive peek, for a split prompt
        self._pending = ""      # an escape or character split across two reads
        self._raw_tail = ""     # the last raw terminal bytes read, escapes kept (`REPLY_END`)
        self._raw_reads = 0     # how many reads brought raw bytes, escapes alone included

        # What the drain thread fills and `_read` empties. `dropped` is not
        # bookkeeping: the buffer is bounded, so a session left alone for long enough
        # discards its OLDEST bytes, and a caller has no other way to tell a stream it
        # saw whole from one with a hole in it.
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._eof = threading.Event()
        self.dropped = 0
        # WHY THE DRAINER ENDED, and never just THAT it ended. `_eof` is set by four
        # different endings -- a real EOF, `_stop` from `close()`, and an error out of
        # either `select` or `os.read` -- and a drainer killed by a transient error
        # makes every later read return "" forever while `alive` still says true. A
        # session that is a broken instrument reporting itself as a quiet machine is
        # the one failure this module exists to prevent.
        self._drainer: threading.Thread | None = None
        self.drain_ended = ""
        self._avi_facts: dict[tuple[str, int, int], dict[str, object]] = {}
        # HOW THE SESSION ENDED, set by `close` and read by the server beside `exit_code`,
        # one word each: `quit` (it left on the first signal), `killed` (SIGKILL,
        # which a session under a pty always needs), `died` (already gone when `close` was
        # called), `none` (not closed yet).
        self.ended_how = "none"
        # Set only when SIGKILL was sent and the child had still not been reaped.
        #
        # IT IS NOT IN `state()`, because a copy there would be inert. It can
        # only be set DURING `close()`, and every caller discards the session straight
        # afterwards -- so a copy in `state()` is unreachable by construction. The
        # `close` tool reads it off the object after closing and reports it beside
        # `exit_code`, which is the reply that would otherwise be a bare null.
        self.reap_failed = ""

        # THE WHOLE SETUP IS UNDER `finally`, because three calls between opening the
        # terminal and handing it to the child can raise, and on any of them the
        # object is never bound to anything: nothing could ever reach `close()` to
        # reclaim the descriptors.
        listener = (dlaunch.listen_input(launch.input_port) if launch.input_port is not None
                    else None)                        # before any process exists
        if listener is not None:
            launch = self.launch = replace(launch, input_port=listener.getsockname()[1])
        try:
            self.control = control.ControlChannel(lambda: self.proc.poll())
            launch = self.launch = replace(launch, control_port=self.control.port)
            self._master, slave = pty.openpty()
        except BaseException:
            if listener is not None:
                listener.close()
            if getattr(self, "control", None) is not None:
                self.control.close()
            raise
        try:
            attrs = termios.tcgetattr(slave)
            attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ECHOE | termios.ECHOK)
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
            self.argv = dlaunch.build_argv(launch)
            self.proc = subprocess.Popen(
                self.argv, cwd=str(launch.cwd), stdin=slave, stdout=slave,
                stderr=slave, env=dlaunch.launch_environment(launch.background),
                start_new_session=True, close_fds=True)
            # STARTED HERE AND NOT LAZILY ON THE FIRST READ: the window this closes
            # is the one between the child being born and the first question, which
            # is exactly when the boot chatter fills the buffer.
            self._drainer = threading.Thread(target=self._drain, name="dosbox-drain",
                                             daemon=True)
            self._drainer.start()
            # THE INPUT SOCKET IS ACCEPTED NOW, before the guest runs a single instruction
            # (`-break-start` holds it at reset): the nullmodem dials from the emulator's
            # init, and a guest polling a serial port with no peer BLOCKS the emulator
            # ("Nullmodem: block on polling", its own log line).
            self._input: socket.socket | None = None
            if listener is not None:
                self._input = dlaunch.accept_input(listener, dlaunch.INPUT_CONNECT_S,
                                                   self.proc.poll)
        except BaseException:
            if listener is not None:
                listener.close()
            self.control.close()
            # THE CHILD IS KILLED HERE, and this arm is why. Before the drain thread
            # existed, `Popen` was the LAST statement in this block, so nothing could
            # raise once a process existed. Now two statements follow it, and both can
            # raise for real: `Thread.start()` with `RuntimeError("can't start new
            # thread")`, or the `KeyboardInterrupt`/`SystemExit` that `except
            # BaseException` is written for. Closing the master and re-raising without
            # touching `self.proc` would leave an emulator running under a bound of up
            # to `dosbox_launch.MAX_SECONDS` with NO object anywhere able to reach `close()`
            # -- which is exactly the six-left-running disaster `dosbox_launch.validate`'s
            # docstring is about, arriving by a different door.
            with contextlib.suppress(Exception):
                proc = getattr(self, "proc", None)
                if proc is not None and proc.poll() is None:
                    self._signal_group(signal.SIGKILL)
                    proc.wait(timeout=5)
            self._stop.set()
            # THE DRAIN THREAD IS JOINED BEFORE THE DESCRIPTOR IS CLOSED, as `close()` does
            # and for its reason: besides an interrupt, a dial that never came arrives
            # here seconds later with the thread selecting on `_master`. Closing under it
            # leaves it reading a number the kernel is free to hand to the next session's
            # pty.
            drainer = getattr(self, "_drainer", None)
            if drainer is not None:
                drainer.join(timeout=2.0)
            with contextlib.suppress(OSError):
                os.close(self._master)
            raise
        finally:
            with contextlib.suppress(OSError):
                os.close(slave)

    # ------------------------------------------------------------------ reading

    def _drain(self) -> None:
        """Read the terminal for as long as it lives. See `DRAIN_KEEP` for why.

        It runs whether or not anybody is asking anything, because the thing it is
        preventing is the emulator BLOCKING on a full buffer, and that happens
        precisely when nobody is asking.

        It drops the OLDEST bytes on overflow rather than the newest: what a caller
        wants from a terminal is the current screen, and the repaint that carries it
        is the most recent thing in there. The drop is COUNTED, and `_read` REFUSES
        the reading it lands in rather than handing back a stream with a hole.

        HOW IT ENDED IS RECORDED, because `_eof` alone cannot say. Four endings reach
        it and only one of them is normal; a drainer killed by a transient error makes
        every later read return "" forever while `state()` still reports `alive`.
        """
        ended = "the descriptor reached end of file"
        while not self._stop.is_set():
            try:
                ready, _, _ = select.select([self._master], [], [], 0.05)
            except (OSError, ValueError) as exc:
                ended = f"select on the terminal failed: {exc!r}"
                break
            if not ready:
                continue
            try:
                chunk = os.read(self._master, 65536)
            except OSError as exc:
                ended = f"reading the terminal failed: {exc!r}"
                break
            if not chunk:
                break
            with self._lock:
                self._buf += chunk
                over = len(self._buf) - DRAIN_KEEP
                if over > 0:
                    del self._buf[:over]
                    self.dropped += over
        else:
            ended = "stopped deliberately by close()"
        self.drain_ended = ended
        self._eof.set()

    def _take(self) -> bytes:
        with self._lock:
            got = bytes(self._buf)
            self._buf.clear()
        return got

    def _read(self, seconds: float) -> str:
        """Whatever the terminal offered within `seconds`, with the escapes stripped.

        It consumes what the drain thread collected instead of reading the descriptor
        itself. Two readers on one pty would race for the same bytes, and the loser of
        that race is whichever one a caller is waiting on.

        An incomplete escape at the end is HELD, not stripped, WHEREVER IT STARTS --
        including at offset zero, where the head is all there is: see `PARTIAL_TAIL`
        and `PENDING_MAX`. The hold is bounded by LENGTH and not by position, because
        an unterminated OSC would otherwise swallow the stream.

        A READING THE DRAIN DROPPED BYTES OUT OF IS REFUSED, NOT RETURNED, and that
        is the whole reason the counter is checked here rather than only reported in
        `state()`. MEASURED by executing the real regexes: a hole landing inside a
        repaint leaves `'\\x1b[0000EAX=00001234  ESI=00000000'`, whose CSI branch eats
        the `E` of `EAX` as its terminator, so the pane parses to `{'ESI': ...}` with
        EAX simply absent. `registers()` raises only on an EMPTY parse, so that
        partial mapping is returned AS a reading, and `set_register` then reports
        "the write did not take" for a write that took perfectly -- a confident,
        specific, wrong diagnosis whose only cause was the session being left alone
        long enough to overflow. Refusing costs the caller one retry against a
        now-drained buffer; the alternative costs them a false answer.
        """
        end = time.monotonic() + seconds
        dropped_before = self.dropped
        out = b""
        while time.monotonic() < end:
            out += self._take()
            if self._eof.is_set():
                break
            time.sleep(0.02)
        out += self._take()     # whatever landed during the final slice
        lost = self.dropped - dropped_before
        if lost:
            # The held escape head belongs to a stream that no longer exists.
            self._pending = ""
            raise Invalid("unexpected_answer",
                f"the terminal buffer overflowed and {lost} bytes were discarded "
                f"during this read, so what came back has a hole in it and is not a "
                f"reading. The buffer is drained now: ask again")
        raw = self._pending + out.decode("utf-8", errors="replace")
        held = dcons.PARTIAL_TAIL.search(raw)
        if held and len(raw) - held.start() <= PENDING_MAX:
            self._pending = raw[held.start():]
            raw = raw[:held.start()]
        else:
            # No head, or one that has grown past PENDING_MAX and is not an escape
            # this debugger is going to finish. Give it up as text.
            self._pending = ""
        if raw:
            self._raw_tail = (self._raw_tail + raw)[-RAW_TAIL_KEEP:]
            self._raw_reads += 1
        text = dcons.ANSI.sub("", raw)
        self._screen = (self._screen + text)[-SCREEN_KEEP:]
        return text

    def _mark_stopped(self) -> None:
        """The machine is at the debugger: set the flag, and count the transition, so a stop
        nobody's tool reply reported (a breakpoint firing during a wait or a key) is still a
        countable event the server can observe on its next contact."""
        if not self._at_debugger:
            self.stop_count += 1
        self._at_debugger = True

    def at_debugger(self) -> bool:
        """Whether the machine is parked at the debugger, answered WITHOUT a console round
        trip: the flag the run keys clear and the prompt sets, plus a peek at whatever the
        terminal has offered since -- a breakpoint that fired while nobody was reading
        announces itself with the prompt, and that text is sitting in the drain. A running
        machine costs nothing to ask; `where()` would cost its whole nudge timeout."""
        if not self._at_debugger:
            try:
                seen = self._peek_carry + self._read(0.0)
                if dcons.PROMPT in seen:
                    self._mark_stopped()
                self._peek_carry = seen[-dcons.STOP_CARRY:]   # a prompt split across two peeks
            except Invalid:
                pass          # a dropped-bytes reading; the flag stands as it was
        return self._at_debugger

    def wait_ready(self, timeout: float = 30.0, progress: Progress = no_progress) -> float:
        """Seconds until the debugger prompt appears; INVALID if it never does. The longest
        wait a session makes, and the one the owner watches: it reports where it is.

        It watches the PROCESS as well as the terminal. When the emulator exits at
        once -- an unknown driver name aborts at SDL init, for instance -- the master
        reports readable immediately and every read returns nothing, so a loop that
        only reads spins at full tilt for the whole timeout and then GUESSES at the
        cause. Asking `poll()` turns that into an answer and gives the loop something
        to wait on.
        """
        t0 = time.monotonic()
        seen = ""
        next_tick = t0 + PROGRESS_EVERY_S
        while time.monotonic() - t0 < timeout:
            cancel.check()
            seen += self._read(0.2)
            if dcons.PROMPT in self._screen:
                self._mark_stopped()    # born stopped: the prompt answered
                return round(time.monotonic() - t0, 3)
            now = time.monotonic()
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - t0, None, f"start: waiting for the debugger prompt, "
                                         f"{now - t0:.0f}s of {timeout:g}s")
            rc = self.proc.poll()
            if rc is not None:
                raise Invalid("session_broken",
                    f"the emulator exited with code {rc} before the debugger came "
                    f"up. That is not a slow start: the last thing it said was "
                    f"{seen.strip()[-400:]!r}")
            time.sleep(0.05)
        # IT NAMES WHAT WAS SEEN AND NOT A CAUSE. "The build carries no debugger" is
        # only one of several things that produce this observation: the prompt is a
        # ONE-TIME marker, so the drain can discard it on overflow and `_screen` can trim
        # it out at SCREEN_KEEP, and
        # either loss indicts a build that has a debugger and printed its prompt.
        # `registers()` states the rule this was breaking: a module whose thesis is
        # that INVALID must be honest about what it examined may not pick a cause.
        raise Invalid("session_broken",
            f"the debugger prompt did not appear within {timeout}s and the emulator "
            f"is still running (terminal bytes discarded so far: {self.dropped}). "
            f"A build with no debugger looks like this, and so does a prompt that "
            f"arrived and was lost. The last thing seen was {seen.strip()[-400:]!r}")

    # ------------------------------------------------------------------ driving

    def _release(self, data: bytes) -> None:
        """What a RUN KEY means for this session's own state, decided ONCE for `resume`,
        `step` and `run_to`. From here the machine may be running, so three things go:

        The STOPPED FLAG. The TAIL a passive peek carried: a chunk that ends at the prompt
        leaves the whole prompt in it, and after the release the next peek reassembled a stop
        out of the carry alone. And WHATEVER THE TERMINAL OFFERED BEFORE THE KEY, drained.
        What the drain buys is exact and narrower than it first looked: a console op's
        repaint ends with the prompt, and left unread it made a machine the F5 let run read
        as `halted` off text painted before the key. What it does NOT buy is a delta free of
        the previous listing: the F5's own repaint carries the debugger's Output pane, which
        replays the last console output, so "Breakpoint list:" in a resume's delta is the
        pane and not a leak (MEASURED: three empty drains over a quiet machine before
        the key, and four listings in the delta after it). The drain lives here, for every
        key that lets the machine go, because a stale `EIP=` left by the read-back before
        the key makes a ten-minute bound "expire" a quarter of a second in.
        """
        if data not in RELEASE_KEYS and LOG_COMMAND.fullmatch(data) is None:
            return
        self._at_debugger = False
        self._peek_carry = ""
        with contextlib.suppress(Invalid):     # a dropped-bytes reading: text the release discards
            self._read(0.0)

    def _write(self, data: bytes) -> None:
        """Write it ALL. A pty master's buffer is finite, so a single `os.write` can
        take a prefix and drop the rest, which the debugger then runs as a truncated
        command while the caller reads the delta as a reply to the whole one."""
        self._release(data)
        try:
            while data:
                data = data[os.write(self._master, data):]
        except OSError as e:
            # A DEAD EMULATOR CLOSES ITS END OF THE PTY, and the write then fails with an
            # I/O error that escaped as a traceback with no session block: the reply this
            # module calls the worst one to hand over. Named as what it is when the process
            # is gone; a write that failed with the process up is the bug it looks like.
            if not self.alive():
                raise Invalid("session_broken",
                    f"the emulator is GONE (exit code {self.proc.poll()}): the "
                              f"terminal refused the write ({e.strerror}). Nothing more "
                              f"can be asked of this session; `close` it and `start` "
                              f"again") from None
            raise

    def command(self, text: str, settle: float = SETTLE_S,
                timeout: float = REPLY_TIMEOUT_S) -> str:
        """Send one debugger command and return what the screen produced FOR IT.

        The reply is the delta this call accumulated, never a search over everything
        that ever arrived: an earlier version searched the whole buffer, so a marker
        produced during the twelve seconds of boot satisfied a check named for a reply
        to a command typed afterwards.

        THE QUIET TIMER ONLY STARTS ONCE SOMETHING HAS ARRIVED. Starting it
        immediately meant a debugger that took longer than `settle` to repaint was
        reported as having said NOTHING -- an INVALID caused by this loop rather than
        by the emulator.

        LIMIT, said out loud: this returns what the TERMINAL produced, not a parsed
        answer. The debugger is a full-screen ncurses application, so a reply arrives
        as a repaint of a pane, interleaved with the rest of the screen. For a value,
        use the narrow readers below, which look for that value.
        """
        return self._keys(text.encode() + b"\r", settle, timeout)

    def _keys(self, data: bytes, settle: float = SETTLE_S,
              timeout: float = REPLY_TIMEOUT_S) -> str:
        """`data` typed as it is, and what the screen produced for it: `command`'s round
        trip for a key that is not a command line (`PAGER_EXIT`)."""
        # WHAT THE TERMINAL STILL HOLDS IS NOT THIS COMMAND'S REPLY. A repaint the previous
        # command delivered after its own collect had gone quiet sits in the drain; taken as
        # this command's first bytes it starts the settle timer, and the real answer arrives
        # after the loop has stopped. MEASURED on a real guest: `run_to` deleted its target and
        # then its control with two `BPDEL` in a row, the list read back after the second still
        # showed the control, and a `BPLIST` typed by hand right after showed it gone. The
        # leftover is read for the one thing it can honestly say, a prompt (the same passive
        # peek `at_debugger` makes), and discarded.
        with contextlib.suppress(Invalid):        # a dropped-bytes reading: nothing to keep
            stale = self._peek_carry + self._read(0.0)
            if dcons.PROMPT in stale:
                self._mark_stopped()
            self._peek_carry = stale[-dcons.STOP_CARRY:]
        self._write(data)
        reply = self._collect(settle, timeout, early=True)
        # THE PROMPT IS COUNTED WHEREVER IT IS READ. A command typed at a RUNNING guest is
        # swallowed, but its collect window stays open for up to `timeout`, and a breakpoint
        # that fires inside it prints the prompt INTO this reply -- with no register pane, so
        # the reader refuses `NotStopped`, and before this line nothing recorded the stop:
        # every passive peek afterwards found an empty terminal, a wait sat out its bound
        # to say "still running", and the next key was refused for a machine that had been
        # parked throughout.
        # Seeded from, and feeding, the passive peek's carry: a prompt split across the end
        # of this reply and the next read is found either way (an auditor's finding).
        seen = self._peek_carry + reply
        if dcons.PROMPT in seen:
            self._mark_stopped()
        self._peek_carry = seen[-dcons.STOP_CARRY:]
        return reply

    def listing(self, command: str) -> str:
        """A debugger LISTING (`DOS MCBS`, `GDT`, `PAGING`...), whole, read off the session's
        logfile: the bytes the emulator appended to it from the moment `command` was typed,
        one character per byte, because a name DOS keeps in guest memory is bytes and never
        UTF-8.

        THE FILE AND NOT THE SCREEN. The debugger writes every listing's rows into the logfile
        with their columns intact, while the repaint draws those columns with cursor moves
        the escape strip removes, so on the screen a segment and a size run together
        (`045010992`). A session started without `logfile` has no such channel and is
        refused before anything is typed.

        THE PAGER IS ANSWERED WITH `PAGER_EXIT` AND NOTHING ELSE (see `PAGER_MARK`). An input
        line that is not empty once the prompt is back, a pager still waiting after `Q`
        among them, is refused naming what it holds. The listing is in the file by the time
        the prompt is back, so the file is read once.
        """
        logfile = self.launch.logfile
        if logfile is None:
            raise Invalid("no_channel",
                f"`{command}` is read off the session's logfile and this session was "
                f"started without one, which the screen cannot stand in for: it loses "
                f"the listing's columns. `start` with `logfile`")
        begin = logfile.stat().st_size if logfile.exists() else 0
        reply = self.command(command)
        if dcons.at_pager(reply):
            reply = self._keys(dcons.PAGER_EXIT)
        held = dcons.input_line(reply)
        if held is None:
            raise Invalid("unexpected_answer",
                f"no prompt came back for `{command}`, so what the logfile holds is not "
                f"known to be the whole listing, and the console may still be paging it: "
                f"`close` this session. What the screen showed: {reply.strip()[-200:]!r}")
        if held:
            raise Invalid("unexpected_answer",
                f"after `{command}` the debugger's input line holds {held!r}: the next "
                f"command would be appended to it rather than run. `close` this session")
        try:
            with logfile.open("rb") as f:
                size = f.seek(0, os.SEEK_END)
                if size < begin:
                    raise Invalid("session_broken",
                        f"{logfile} shrank from {begin} to {size} bytes while `{command}` "
                        f"ran: it was truncated or replaced, so what it holds now is not "
                        f"this listing")
                f.seek(begin)
                return f.read().decode("latin-1")
        except FileNotFoundError:
            raise Invalid("no_channel", f"no log at {logfile}: the emulator has not "
                          f"written it, so `{command}` left nothing to read") from None

    def _collect(self, settle: float, timeout: float, early: bool = False) -> str:
        """What arrives until it has been quiet for `settle`, once something has arrived;
        `timeout` bounds it whatever arrives. `early`, the reply to a command: it is whole
        after `REPLY_GRACE_S` of quiet once it ends in the debugger's last words (`REPLY_END`).
        Quiet is counted from the last bytes of any kind, escapes alone included."""
        got = ""
        deadline = time.monotonic() + timeout
        last_s, reads = 0.0, self._raw_reads
        while time.monotonic() < deadline:
            chunk = self._read(COLLECT_SLICE_S)
            if chunk or self._raw_reads != reads:
                reads, last_s = self._raw_reads, time.monotonic()
            if chunk:
                got += chunk
            elif got:                      # only ONCE something has arrived
                ended = early and dcons.REPLY_END.search(self._raw_tail) is not None
                if time.monotonic() - last_s >= (min(settle, REPLY_GRACE_S) if ended
                                                 else settle):
                    break
        return got

    def _survey(self) -> tuple[str, dict[str, str]]:
        """ONE repaint, and everything that can be read off it.

        It nudges the screen with a command that repaints and changes nothing, because
        a pane that has not repainted since the last question would hand back the last
        question's answer, and an empty line produces no repaint at all.

        IT RETURNS THE WHOLE TEXT BESIDE THE REGISTERS because three different things
        are read from one screen -- the registers, the CPU mode and the breakpoint list
        -- and asking three times would cost three settles for a screen that carries
        all of them at once. `registers()` is this with the text dropped.

        THE REGISTER PANE IS THE PRECONDITION FOR ALL THREE. If it did not come back,
        the machine is not stopped at the debugger, and a breakpoint list or a mode
        token read off that same dead screen would be a leftover rather than a reading.
        So the refusal lives here, once, rather than in each reader.
        """
        text = self.command(NUDGE)
        found = dcons.parse_registers(text)
        if not found:
            # THE MESSAGE NAMES WHAT WAS SEEN, not a cause. An empty parse has several
            # possible causes -- the machine is running, the pane did not repaint, the
            # emulator died -- and a module whose thesis is that INVALID must be honest
            # about what it examined may not pick one and present it as diagnosis. One
            # cause it CAN see is named: a dead reader thread returns nothing for every
            # command while the process is up, and "running" would then be the broken
            # instrument reporting itself as a quiet machine.
            drainer = getattr(self, "_drainer", None)
            if drainer is not None and not drainer.is_alive():
                raise NotStopped(
                    f"no register pane came back from `{NUDGE}`, and the terminal reader "
                    f"has DIED ({self.drain_ended or 'no reason recorded'}): nothing can "
                    f"come back from this session whatever the machine does. `close` it "
                    f"and `start` again")
            raise NotStopped(
                f"no register pane came back from `{NUDGE}` (emulator "
                f"{'running' if self.alive() else 'GONE'}). A register read is only "
                f"a reading when the machine is stopped at the debugger")
        return text, found

    def registers(self) -> dict[str, str]:
        """The register pane, as a mapping. INVALID when the pane says nothing."""
        return self._survey()[1]

    def where(self) -> dict[str, str]:
        """WHERE THE MACHINE IS STOPPED: the address and the mode it is in.

        INVALID if it is not stopped, which is the refusal `step`, `run_to` and `watch`
        all rest on -- each of them sends something that a running machine swallows
        without a word, so "am I allowed to ask this at all" has to be settled first
        and settled by a reading rather than by a hope.

        The mode is part of the position and not a separate question: the same sixteen
        bits after `CS=` mean a paragraph of physical memory in real mode and an index
        into a descriptor table in protected mode, so an address quoted without it is
        not an address.
        """
        at = dcons.where_from(self._survey()[0])
        self._mark_stopped()       # a position was read: the prompt answered
        return at

    def stop_survey(self) -> tuple[dict[str, str], dict[str, str], list[dict[str, str]]]:
        """Everything a STOP REPLY reads, off ONE repaint: where, the registers and the
        breakpoint list. The nudge that repaints IS `BPLIST`, so the list is on the same
        screen as the pane; reading it again for the watches cost a second round trip per
        stop for a screen already in hand. A missing listing on
        that screen is refused the way `breakpoints()` refuses it."""
        text, regs = self._survey()
        where = dcons.where_from(text)
        # THE PAGING MARK AND THE CLOCK ARE THIS REPAINT'S, like the position: set here, so a
        # later survey (the list read below, a pointer follow) cannot move them off the stop.
        self.paging = dcons.parse_paging(text)
        self.survey_text = text
        self.pane_clock_ms = dcons.parse_pane_clock(text)
        self.pane_cycles = dcons.parse_pane_cycles(text)
        if dcons.BPLIST_HEADER not in text:
            # The pane came back whole and the listing did not (a cut repaint): one fresh
            # read of the list, which is what the stop paid before this method existed,
            # rather than refusing an enrichment the pane already supports.
            return where, regs, self.breakpoints()
        return where, regs, dcons.parse_breakpoints(text)

    def where_and_registers(self) -> tuple[dict[str, str], dict[str, str]]:
        """Both readings off ONE survey, so a stop reply pays a single console round trip
        for where AND registers instead of two of the same screen (decision 35: a console
        round trip costs most of a second). `where` carries the same checks `where()` makes; the
        registers are the permissive last-wins mapping `registers()` hands back."""
        text, regs = self._survey()
        self.pane_clock_ms = dcons.parse_pane_clock(text)
        self.pane_cycles = dcons.parse_pane_cycles(text)
        return dcons.where_from(text), regs

    def breakpoints(self) -> list[dict[str, str]]:
        """What the debugger currently holds, READ OFF IT rather than remembered.

        This is the verification every arming here goes through, and it exists because
        the acknowledgements cannot be trusted: the Output pane scrolls, so a delta
        carries earlier `DEBUG: Set breakpoint at ...` lines verbatim, and a second
        arming of the SAME address is indistinguishable from a repaint of the first
        one's success. A list has no such problem -- the entry is either in it or not.
        """
        text, _ = self._survey()
        if dcons.BPLIST_HEADER not in text:
            raise Invalid("unexpected_answer",
                f"`{NUDGE}` repainted a register pane but printed no {dcons.BPLIST_HEADER!r}. "
                f"An empty list and a listing that never happened both come back as no "
                f"rows, and only one of them means nothing is armed")
        return dcons.parse_breakpoints(text)

    def read_memory(self, seg: int, off: int, mode: str | None = None) -> list[str]:
        """The data-view rows at an address, and INVALID unless THAT address is among
        them.

        IT IS A NARROW READER, which it had not been. This module's own docstrings
        tell a caller wanting a VALUE to use the readers that look for that value
        rather than reading a screen, and memory was the one that did not have one:
        the server ran `command()` and sliced the result, so the tool inherited every
        weakness `command()` declares and none of the checking `registers()` does.

        THE ADDRESS ASKED FOR IS THE ASSERTION, not merely that some rows came back.
        A screen full of somebody else's rows is rows too, and that is exactly what
        the sliced version returned: the debugger's data view holds eight rows and the
        cut fell inside them, so the reply was well formed, plausible, `ok`, and about
        the wrong four rows.
        """
        check_segment(seg)
        # THE OFFSET'S WIDTH IS THE CPU MODE'S, decision 38: the shipped clamp was a flat
        # 0xFFFF, which refuses EVERY 32-bit protected-mode address -- and every DJGPP
        # global is one (`_main` sits at 0x16DF20). `run_to` and `watch` both take the
        # ceiling from `offset_ceiling(mode)`; `read_memory` was the THIRD site nobody
        # brought in, and `dosbox_console.offset_ceiling`'s own docstring already named the family.
        # `where()` gives the mode AND refuses a running machine, before the `D` goes out.
        # A CACHED `mode` skips that survey (decision 35): a stop reply has just read the
        # machine once and passes the mode in, so N show watches do not re-survey it N
        # times. It is only ever passed when the machine is known stopped (the reply read
        # `where` to get here), so the running-machine guard it bypasses is already met.
        top = dcons.offset_ceiling(mode if mode is not None else self.where()["mode"])
        if not 0 <= off <= top:
            raise Invalid("bad_argument",
                f"an offset is 0x0 to 0x{top:X} in this CPU mode; got 0x{off:X}."
                          f" In real mode an offset past 0xFFFF addresses nothing")
        rows = dcons.parse_data_view(self.command(f"D {seg:04X}:{off:04X}"))
        if not rows:
            # NO CAUSE IS NAMED, per this class's own rule. An empty parse has several
            # of them -- the machine is running, the pane did not repaint, the
            # emulator is gone -- and picking one is the diagnosis this module refuses
            # to make.
            raise Invalid("unexpected_answer",
                f"no data view came back for D {seg:04X}:{off:04X} (emulator "
                f"{'running' if self.alive() else 'GONE'}). Several things produce "
                f"this and none of them is picked here: the machine is running, the "
                f"pane did not repaint, the emulator is gone")
        # TWO REPAINTS OF ONE VIEW ARE ONE VIEW. MEASURED live, through the MCP transport,
        # on a stopped Pr32 machine: one `D` produced a delta holding the eight rows TWICE
        # (the pane is painted with the `Set data overview` acknowledgement and again on
        # the settle), and this handed back sixteen rows for an eight-row pane. Each
        # address is kept once, at the place it was LAST painted: the last repaint is
        # the newest reading, and the order stays the paint order the docstring promises.
        newest: dict[str, str] = {}
        for r in rows:
            addr = r.split()[0]
            newest.pop(addr, None)
            newest[addr] = r
        rows = list(newest.values())
        want = f"{seg:04X}:{off:08X}"
        if not any(r.startswith(want) for r in rows):
            # THE ROWS ARE IN PAINT ORDER, which is not address order, so this says
            # what it HAS rather than describing where they "start".
            raise Invalid("unexpected_answer",
                f"the screen came back with {len(rows)} data row(s) and none of them "
                f"is {want}, the address that was asked for. What came back: "
                f"{[r.split()[0] for r in rows[:4]]}. That is a reading of somewhere "
                f"else")
        return rows

    def read_bytes(self, seg: int, off: int, n: int, mode: str | None = None) -> bytes:
        """Exactly `n` bytes at seg:off, for a watch to render as a value.

        `read_memory` gives eight rows of sixteen bytes as TEXT, for a human to read; a
        watch needs the bytes THEMSELVES, so this reads the same data view and returns the
        `n` bytes at the address rather than the screen. The rows arrive in PAINT order,
        not address order, so the bytes are gathered into a map keyed by absolute offset
        and read out in order -- the same reason `read_memory` asserts the address is
        present rather than trusting the first row to be it.

        UP TO 128 BYTES, the eight rows one `D` paints. A watch wider than that is a region,
        not a value, and `memdump` is the tool for a region; asking here is refused rather
        than served by a silent second read the caller did not see.
        """
        if n <= 0:
            raise Invalid("bad_argument", f"a read needs a positive length; got {n}")
        if n > dcons.DATA_VIEW_BYTES:
            raise Invalid("bad_argument",
                f"read_bytes reads up to {dcons.DATA_VIEW_BYTES} bytes (the data view's reach); "
                          f"{n} is a region -- use memdump")
        by_off: dict[int, int] = {}
        for r in self.read_memory(seg, off, mode=mode):
            m = dcons.DATA_ROW.search(r)
            if m is None:
                continue
            base = int(m.group(2), 16)
            for i, pair in enumerate(m.group(3).split()):
                by_off[base + i] = int(pair, 16)
        try:
            return bytes(by_off[off + i] for i in range(n))
        except KeyError:
            raise Invalid("unexpected_answer",
                f"the data view for {seg:04X}:{off:04X} did not cover all {n} bytes "
                f"asked for; it painted {len(by_off)} from the start address") from None

    # How many bytes one `SM` carries: the debugger takes a list of values after the
    # address on one input line, and a short line is one every build reads whole.
    WRITE_CHUNK = 8

    # THE ROM OF A REAL-MODE MACHINE, by linear address: the option ROMs and the BIOS.
    # Measured on this build: `SM` into it does not write and does not refuse, it ENDS the
    # emulator, so a write there is refused before anything is sent.
    ROM_LINEAR = (0xC0000, 0xFFFFF)

    def write_memory(self, seg: int, off: int, data: bytes,
                     mode: str | None = None) -> dict[str, object]:
        """Write `data` at seg:off through the debugger's `SM`, READ IT BACK, and mark the
        session altered for good.

        `SM seg:off v1 v2 ...` sets bytes from the address on; the bytes go out in short
        lines, and the whole range is then read back off the data view, so `readback` is
        what memory holds now and `verified` whether that is what was sent. A readback that
        cannot be made is the refusal, since nothing was checked. Up to the data view's
        reach, which is what the readback can cover in one read: the caller's bound is
        `dosbox_checks.write_data`'s, judged before a sequence runs. A real-mode address in the
        ROM range is refused: measured, `SM` there ends the emulator instead of writing.
        """
        if not data:
            raise Invalid("bad_argument", "a write needs at least one byte")
        check_segment(seg)
        mode = mode if mode is not None else self.where()["mode"]
        top = dcons.offset_ceiling(mode)
        if not 0 <= off <= top:
            raise Invalid("bad_argument",
                f"an offset is 0x0 to 0x{top:X} in this CPU mode; got 0x{off:X}")
        # THE LAST BYTE IS BOUNDED TOO. A write is a range, and a range starting under the
        # ceiling whose tail runs past it would send `SM seg:10000`, an offset the segment
        # cannot address, to a debugger that takes it without a word.
        if off + len(data) - 1 > top:
            raise Invalid("bad_argument",
                f"the write's last byte would be at 0x{off + len(data) - 1:X}, past "
                          f"the 0x{top:X} an offset can reach in this CPU mode: "
                          f"{len(data)} bytes from 0x{off:X} do not fit in the segment")
        if not mode.startswith("Pr"):
            lo, hi = seg * 16 + off, seg * 16 + off + len(data) - 1
            if hi >= self.ROM_LINEAR[0] and lo <= self.ROM_LINEAR[1]:
                raise Invalid("bad_argument",
                    f"{seg:04X}:{off:04X} is in the ROM range (linear 0x{lo:X}, "
                    f"0x{self.ROM_LINEAR[0]:X}-0x{self.ROM_LINEAR[1]:X}): measured on this "
                    f"build, the debugger's `SM` into it does not write and does not "
                    f"refuse, it ENDS the emulator. Nothing was sent")
        self.altered = True
        for i in range(0, len(data), self.WRITE_CHUNK):
            chunk = data[i:i + self.WRITE_CHUNK]
            # EVERY VALUE LEADS WITH A ZERO. MEASURED on this build: the console's value
            # parser reads a bare `AC` (and `AF`, `CF`, `DF`) as the FLAG of that name before
            # it reads hex, so `SM ... AC` wrote the flag's value, zero, and took every byte
            # after it in the same line with it; `0AC` is a number to that parser and lands.
            values = " ".join(f"0{b:02X}" for b in chunk)
            self.command(f"SM {seg:04X}:{off + i:04X} {values}")
        back = self.read_bytes(seg, off, len(data), mode=mode)
        return {"written": len(data), "readback": back.hex(), "verified": back == data}

    def set_register(self, name: str, value: int) -> dict[str, object]:
        """Write a register, READ IT BACK, and mark the session altered for good.

        The name is checked against the set this debugger accepts rather than passed
        through. `SR` takes MULTIPLE pairs and this class appends a carriage return,
        so an unchecked name is a way to run commands the caller never named.

        The write is read back off the pane, under the register that holds the name and at
        the name's own width (`READBACK`): `readback` is what the register holds now, and
        `verified` whether that equals what was sent. A register the debugger masks or
        answers otherwise is doing its job, so a mismatch is reported and not refused; a
        pane that came back without the register is the refusal, since nothing was read.
        The session is altered either way, because the attempt reached the machine.
        """
        key = check_register_name(name)
        check_register_value(key, value)
        self.altered = True
        self.command(f"SR {key} {value:x}")
        regs = self.registers()
        pane, bits = READBACK[key]
        got = regs.get(pane)
        if got is None:
            raise Invalid("readback_refused",
                f"the pane came back without {pane} after `SR`, so the "
                          f"write could not be read back. The session is marked altered "
                          f"anyway, because the attempt reached the machine")
        held = int(got, 16) & ((1 << bits) - 1)
        return {"registers": regs, "readback": f"{held:0{bits // 4}X}", "verified": held == value}

    def breakpoint_interrupt(self, number: int, ah: int | None = None) -> str:
        """Break on an interrupt. The one way control comes BACK on this platform.

        `number` and `ah` are the debugger's own HEX values, matching its help
        (`BPINT [intNr] [ah]`): pass 0x21 for DOS, which in decimal is 33. Passing 21
        meaning "21 hex" arms interrupt 0x15 instead, silently, so the range is
        checked but the meaning is the caller's to get right.

        A HOST KEYPRESS is not this module's route: joncampbell123/dosbox-x#4026,
        open, reports that on macOS you cannot break back into the debugger once
        emulation has begun, because the shortcut maps to a key the keyboards do not
        have. A breakpoint is the emulator stopping ITSELF, which is a different path,
        and it was MEASURED working.
        """
        check_interrupt(number, ah)
        arg = f"BPINT {number:02X}" + (f" {ah:02X}" if ah is not None else "")
        out = self.command(arg)
        # READ THE LIST BACK, exactly as `run_to` and `watch` do, and for the reason
        # this module states everywhere else: nothing here believes an acknowledgement.
        #
        # WHAT WAS HERE INSTEAD COULD NOT FAIL. The test was `"reakpoint" not in out`,
        # and `BPLIST_HEADER` is `"Breakpoint list:"`, which CONTAINS it -- while
        # `NUDGE` IS `BPLIST`, so every register read in this class puts that header on
        # the scrolling Output pane. After any other tool had run, the acknowledgement
        # was unfailable. MEASURED in a real session: the delta for this
        # very call carried SEVEN `Breakpoint list:` blocks before the real
        # acknowledgement, so an unrecognised `BPINT` would have been reported `ok`
        # and the caller would have resumed with nothing to stop the machine.
        # THE ROW'S TWO FORMS ARE CAPTURED, not remembered. MEASURED with both armed
        # at once:
        #     00. BPINT 21
        #     01. BPINT 31 AH=00
        # so the AH half is `" AH=%02X"` and is ABSENT rather than defaulted when the
        # caller gave none. It is compared whole and not by prefix, because `BPINT 31`
        # is a prefix of `BPINT 31 AH=00` and matching loosely would report an arming
        # on ANY AH as the one that was asked for.
        armed = dcons.interrupt_row(number, ah)
        if not any(row["entry"] == armed for row in self.breakpoints()):
            raise Invalid("readback_refused",
                f"`{arg}` is not in the debugger's breakpoint list, so it "
                          f"was not armed. Resuming now would run with nothing to "
                          f"stop the machine. What it showed: {out.strip()[-300:]!r}")
        return out

    def retrace(self, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """Run to the next vertical retrace: `VRT` typed as a release, and the stop heard by
        the prompt until `deadline`, `run_to`'s wait (`(expired, saw_at)`). No settle per frame:
        the prompt is the stop, so a frame costs the retrace and nothing typed after it."""
        self._write(RETRACE_COMMAND)
        return Session._await_stop(self, began, deadline, "the next retrace", progress,
                                   label="run_for: the next retrace")

    def log_cpu(self, word: str, count: int, began: float, deadline: float,
                progress: Progress = no_progress) -> tuple[bool, float]:
        """`word` of the `LOG` family with its `count` in hex (`LOGC 41`), typed as the release it
        is, and the stop it ends at heard by the prompt until `deadline`: `(expired, saw_at)`,
        `retrace`'s shape. The log closes and stops the machine when the count runs out, or a
        stop comes first and leaves it open."""
        if word not in LOG_WORDS:
            raise ValueError(f"{word!r} is not a word of the LOG family")
        command = f"{word} {count:X}"
        self._write(command.encode() + b"\r")
        return Session._await_stop(self, began, deadline, f"`{command}`", progress,
                                   label=f"trace: `{command}`")

    def resume(self) -> dict[str, object]:
        """Let the machine run, and SAY whether it actually left the debugger.

        F5 is sent WITHOUT a trailing carriage return: the return belongs to typed
        commands, and on this path it would land on a guest that is already running.
        `screen` is what the terminal produced FOR the key: whatever it still held from
        before -- the repaint of a console op that ran just before this in the same call --
        is drained as the key goes out (`_release`), so the prompt the previous op left
        behind is not read as this key's halt. The F5's own repaint still carries the
        debugger's Output pane, which replays the last console output (a listing typed
        before the key shows up in it, however long the machine sat quiet), so the delta is
        the screen and never a count of anything. The drain is one snapshot: a repaint
        landing in the instant between it and the key is read as the key's own.

        THIS USED TO RETURN A BARE SCREEN AND EXAMINE NOTHING, which is the defect it
        was rewritten to close: `ok` for a machine still sitting at the debugger is
        indistinguishable from `ok` for one that ran, and the symptom it produces is a
        guest that looks hung. A session was closed over exactly that.

        `halted` IS THE PROMPT COMING BACK, AND THAT IS A MEASUREMENT rather than the
        obvious reading. The obvious reading is to parse the register pane out of the
        delta, and it does not work: this debugger is a full-screen ncurses application
        that repaints only the cells that CHANGED, so a machine that stops again
        redraws its code and data panes while the register pane's labels -- `EAX=` and
        the rest -- stay exactly as they were and are never sent. MEASURED over
        controlled resumes scored against `where()`: the prompt in the delta agrees with
        the machine on every one, the pane header is never present, and a non-empty
        `parse_registers` agrees on about half.

        So the pane reading would answer "running" for a machine at the debugger, which
        is the very defect this closes, and its half is worse than it looks: on one of
        those deltas `parse_registers` glued the repainted DIGITS of
        several fields into `CS=081401080100FF91C81440026`, a value no register ever
        held. The prompt is the debugger saying it has the keyboard back, and nothing
        else on this screen says that.

        `stopped_at` IS READ BACK AND NOT TAKEN FROM THE DELTA, because the delta does
        not carry an address either -- see above. It is `where()`, the same reader
        `step`, `run_to` and `watch` rest on, and it is asked ONLY when the prompt came
        back: on a machine that ran, the nudge would be swallowed with no error
        anywhere and would buy a settle for nothing. Measured cost, a console round trip
        on the halted path and none at all on the ordinary one.

        IT IS A READING AND NOT A RETRY. Nothing here sends F5 again. A tool that
        resumed until something worked would be guessing how many stops a
        configuration has, and how many it has is not a thing this can know.

        AND `halted: True` WITH `stopped_at: None` IS A REAL STATE, not an oversight:
        the prompt came back but the position could not be read off the repaint that
        followed -- a cut pane, which `where()` refuses rather than composing an
        address out of two of them. The two fields are separate because they answer
        different questions and one can be had without the other.

        WHAT `halted: False` DOES NOT ESTABLISH, said out loud: it is the ABSENCE of a
        marker, and an emulator that has gone produces the same absence. What tells
        those apart is `alive` -- but it lives in the reply's `session` block, so it is
        there only while there IS a session to report. An emulator already found dead is
        buried by the server's `live`, which then REFUSES, and that reply carries
        `session: null` and therefore no `alive` at all; there it is the refusal's own
        text that says so, exactly as `live` already does for `altered`.

        THIS PARAGRAPH USED TO END "and every reply carries it", which is a checkable
        claim and was false on the one path it nominates: with no live session this tool
        answers `{"status": "INVALID", "reason": ..., "session": null}`.
        """
        self._write(RUN_KEY)
        text = self._collect(settle=1.0, timeout=8.0)
        halted = dcons.PROMPT in text
        if halted:
            self._mark_stopped()
        stopped_at: dict[str, str] | None = None
        if halted:
            try:
                stopped_at = self.where()
            except Invalid:
                # NOT re-raised. A machine that stopped again is an ORDINARY outcome --
                # it is what a breakpoint is for -- so refusing here would invent a
                # verdict out of an observation, and would do it on the one tool every
                # other one begins with.
                stopped_at = None
        return {"screen": text, "halted": halted, "stopped_at": stopped_at}

    # --------------------------------------------------------------- the debugging

    def step(self, count: int = 1, mode: str = "into") -> dict[str, object]:
        """Advance the machine one instruction at a time, VERIFYING each one landed.

        `over` is F10 and `into` is F11, which is the debugger's own pairing. The
        difference only shows at a `CALL` or an `INT`: `into` follows it, `over` runs
        the whole thing and stops after it.

        WHAT THE READ-BACK PROVES, EXACTLY: that the machine is STILL STOPPED after
        the key. It does not prove the instruction executed -- a key the debugger
        ignored leaves a pane that parses perfectly -- so `completed` is "keys sent to a
        machine that was still there afterwards", and `moved` reports whether the
        position actually changed. They are separate because an instruction CAN
        legitimately not move EIP (a jump to itself), so a mismatch is a fact for the
        caller and not an error this may declare.

        AND THAT IS WHY EVERY STEP IS READ BACK RATHER THAN COUNTED OUT. A step over a
        `CALL` is implemented as run-until-it-returns, so a call that does NOT return
        -- one that jumps away, one that waits on hardware, one that ends the program
        -- leaves the machine RUNNING, and every remaining keystroke goes to a debugger
        that is not listening. Sending `count` keys and reporting `count` steps would
        then be a fabricated number of exactly the right shape. So the position is
        re-established after each key, and a step that does not come back ENDS the loop:
        `completed` is what actually happened and `running` says why it stopped short.

        IT REFUSES ON A MACHINE THAT IS NOT STOPPED, before sending anything. A
        keystroke to a running guest is swallowed with no error anywhere, so without
        this the tool's reply would describe a machine it never touched.

        AND A REFUSAL MID-LOOP NAMES THE STEPS ALREADY TAKEN, because they cannot be
        undone. `where()` refuses three ways, and only one is `NotStopped`: a pane naming
        no CPU mode and a CUT repaint carrying no `CS`/`EIP` are PLAIN `Invalid`, and
        catching the first alone lets the other two escape whole (MEASURED against a
        double that steps four times and then hands back a partial pane: five keystrokes
        reached the machine and the caller was told about none of them). It STILL
        refuses, deliberately: a reading that could not be made is not an answer, and
        replying here would have this method claim a position it just failed to read.
        The refusal carries the irreversible part.

        THE COST: a settle per step, on the repaint that proves it landed. `STEP_MAX` bounds one
        call at 64 for that reason alone -- for anything longer the question is `run_to`,
        which pays the settle once however far the machine travels.
        """
        check_step(mode, count)
        # THE REFUSAL IS THIS TOOL'S, not the position reader's. `where()` is the first thing
        # a step does, and its `NotStopped` let escape whole tells a caller who asked to STEP
        # "no register pane came back ... a register read is only a reading when the machine
        # is stopped", which describes a tool they did not call and says nothing about why a
        # step needs a stopped machine. The cause is the same and the words are this method's.
        try:
            before = self.where()
        except NotStopped:
            # A DEAD EMULATOR IS NOT A RUNNING ONE, and the mid-loop handler below has
            # always known that. Rewriting every `NotStopped` as "it is running" told a
            # caller whose emulator had exited to bring it back with `stop`, which cannot
            # work: `_survey` distinguishes gone, reader-dead and running in its own words,
            # so only the RUNNING case gets this method's message and the rest escape as
            # themselves. The docstring promises exactly that.
            if not self.alive():
                raise
            raise NotStopped(
                "a step needs the machine STOPPED at the debugger, and it is running: a "
                "step is a KEYSTROKE (F10/F11) to the debugger's window, and a keystroke to "
                "a running guest is swallowed with no error anywhere, so stepping now would "
                "report a machine it never touched. Nothing was sent. Bring it back with "
                "`stop` or a breakpoint armed before it ran (the "
                "position could not be read, which is how a running machine is known here)"
            ) from None
        after, completed, running = before, 0, False
        # COUNTED PER STEP, because comparing only the ENDPOINTS answers a different
        # question than the one `moved` is asked. A two-instruction loop (`L: nop` /
        # `jmp L`) returns to where it started, so endpoint comparison reports
        # `moved: false` -- which this method's own docstring says means "a key the
        # debugger ignored" -- for two steps that both moved. The two states were
        # indistinguishable; now `moved` is whether ANY step changed position, and
        # `stalled` is how many did not, which is the number that actually names a
        # swallowed keystroke.
        stalled, sent = 0, 0
        for _ in range(count):
            position_before = after
            # `_write` AND `_collect` ARE INSIDE THE TRY. `_collect` calls `_read`, and
            # `_read` RAISES `Invalid` when the drain thread dropped bytes -- so with them
            # outside, a long run over a terminal that overflows would answer "the
            # terminal buffer overflowed" with no mention of the irreversible steps
            # already taken, which is exactly the failure this handler exists to
            # prevent, reached by another door.
            try:
                sent += 1
                self._write(STEP_KEYS[mode])
                self._collect(settle=0.4, timeout=6.0)
                after = self.where()
            except NotStopped:
                # THE MACHINE IS GONE OR IT IS RUNNING, AND THOSE ARE NOT THE SAME
                # ANSWER. A dead emulator has no partial result worth reporting -- the
                # steps that "completed" were measured against a machine that no longer
                # exists -- so that one is left to escape as the refusal it is. A
                # RUNNING one is an honest outcome of stepping and is reported as such.
                if not self.alive():
                    raise
                running = True
                break
            except Invalid as exc:
                # AND EVERY OTHER `Invalid` FROM `where()`, WHICH USED TO SAY NOTHING
                # ABOUT THE STEPS ALREADY TAKEN. `NotStopped` is only one of the three
                # ways that method refuses; the other two -- a pane naming no CPU mode,
                # and a CUT repaint carrying no `CS`/`EIP` -- are PLAIN `Invalid` and
                # escaped this loop whole. MEASURED against a double that steps four
                # times and then hands back a partial pane: five keystrokes had reached
                # the machine and the caller was told about none of them.
                #
                # THAT IS NOT LIKE LOSING A READ. A step is IRREVERSIBLE -- this
                # debugger has no un-step -- so a caller who asked for ten and got an
                # exception has a machine in a position neither of them can name.
                #
                # IT STILL REFUSES, and deliberately: a reading that could not be made
                # is not an answer, and turning this into a reply would be this module
                # claiming to know a position it just failed to read. What changes is
                # that the refusal now CARRIES the irreversible part, so `completed` is
                # recoverable from the message instead of being lost with it.
                if isinstance(exc, NotStopped):
                    raise
                # IT REPORTS THE KEYSTROKES SENT, NOT THE ONES READ BACK. `completed`
                # only rises AFTER the
                # position is confirmed, so at this point `sent` keys have reached the
                # machine and `completed` is one fewer -- and this branch is reached
                # only when the pane DID come back, i.e. the machine is still at the
                # debugger and that last key almost certainly took effect. Quoting the
                # smaller number under-states the irreversible damage, which is the one
                # direction this message may not err in.
                raise Invalid(exc.code,
                    f"{exc} -- and {sent} `{mode}` keystroke(s) of {count} had ALREADY "
                    f"gone to the machine when this happened, of which {completed} were "
                    f"CONFIRMED landed. They are irreversible: this debugger has no "
                    f"un-step, so the machine is at least {completed} step(s) past "
                    f"{before['cs']}:{before['eip']} and this call could not read where "
                    f"that is") from None
            if after == position_before:
                stalled += 1
            completed += 1
        return {"mode": mode, "asked": count, "completed": completed,
                "running": running, "moved": stalled < completed,
                "stalled": stalled,
                "before": before, "after": after}

    def run_to(self, seg: int, off: int, seconds: float,
               control: tuple[int, int] | None = None,
               progress: Progress = no_progress) -> dict[str, object]:
        """Run until the machine reaches an address, and say where it really stopped.

        `control` is a second `(seg, off)` armed beside the target, known to be HOT: when
        it fires the machine is released again and the hit counted, so a target that never
        fires within the bound is a MEASUREMENT (the control proves breakpoints work here)
        and not a silence. A code breakpoint in ROM is the case (below): acknowledged,
        listed, and never firing. The control is removed on every stopped outcome; the
        caller never asked to keep it. Each hit costs a position read, a console round trip,
        so a control that fires a few times a run is the right one.

        Three outcomes, and they are kept apart because conflating any two of them
        hands back a confident wrong answer:

          arrived            it stopped at the address that was asked for.
          stopped elsewhere  it stopped, at something else -- another breakpoint got
                             there first, which is ordinary and is NOT an arrival.
          still running      it did not come to rest at the debugger. The machine is
                             running, which means no other tool here can answer
                             anything until it stops.

        THE OUTCOME IS READ FROM `arrived` AND `running`, NEVER FROM `bound_expired`
        ALONE. That flag is the WAIT's measurement -- did the loop give up on the clock
        -- and it is on EVERY return, including the arrival and the stop elsewhere,
        because the position is read AFTER the loop gives up and the machine can be
        found at rest however the loop ended. `bound_expired` SPLITS the still-running
        outcome, which has two causes that want different next moves: either the clock
        ran out with nothing happening, or the debugger announced a stop, the wait left
        early, and the nudge that followed came back cut. One note for both would
        contradict itself inside one reply: "the bound expired" beside a `waited_s`
        of nothing.

        THE STOP IS HEARD BY THE PROMPT, NOT ONLY BY A REGISTER REPAINT. This debugger
        repaints only the cells that changed, so a machine that stops again redraws its
        code pane while `EAX=` and the rest stay put and are never sent: the prompt
        agrees with the machine on every stop, the pane on about half of them. A wait
        listening to the pane alone reports a machine that stopped within milliseconds
        after the FULL bound as `bound_expired: true` beside `running: false` and a
        concrete `stopped_at`: a timeout, by the flag, for a machine that sat at the
        debugger throughout.

        THE WAIT CONSULTS THE EMULATOR AND SCANS ONLY WHAT IS NEW, as `e9_wait` does. A
        session that dies the instant the machine is released would otherwise burn the
        whole bound, `RUN_TO_MAX`, with the server's lock held; and re-parsing the whole
        accumulated terminal every poll is quadratic in the length of the wait. A
        bounded carry keeps a register that
        arrives split across two reads from being missed.

        THE BREAKPOINT IS CONFIRMED BY READING THE LIST BACK before the machine is let
        go. `DEBUG: Set breakpoint at ...` is printed into a SCROLLING pane, so an
        acknowledgement can be a repaint of an earlier one -- and "it never arrived"
        and "it was never armed" are completely different findings that an unverified
        arming makes indistinguishable.

        AND IT REMOVES THE BREAKPOINT IT CREATED, once it has arrived. A `BP` is
        persistent, so a `run_to` that left it behind would silently stop the NEXT
        `resume` at an address the caller had finished with. It is removed by looking
        its index up again rather than reusing the one from arming: `BPDEL` renumbers.
        WHEN IT DID NOT ARRIVE THE BREAKPOINT STAYS, and the reason differs by path,
        which an earlier version of this paragraph got wrong by giving only one. On the
        TIMED-OUT path the machine is running and will not take the command. On the
        STOPPED-ELSEWHERE path it would take it perfectly well: the breakpoint is kept
        DELIBERATELY, because the caller has not reached what they asked for and
        removing it would take away the thing they are still waiting on. Either way the
        reply says the breakpoint is still armed rather than claiming a cleanup that did
        not happen.

        THE ONE TRAP THIS CANNOT CLOSE, MEASURED HERE AND DOCUMENTED NOWHERE: A CODE
        BREAKPOINT IN ROM IS ACKNOWLEDGED AND NEVER FIRES. `BP F000:E05B` and
        `BP F000:C9B0` both came back `DEBUG: Set breakpoint at ...`, both appeared in
        `BPLIST`, and neither stopped a machine that provably executed them -- the
        reset vector jumps to E05B, which jumps to C9B0. The same command at a RAM
        address (`BP 0087:0234`) fired on the first attempt. Two controls rule out the
        obvious explanations: it is NOT the dynamic core (a `core=normal` run behaved
        identically) and it is NOT a missing feature (`HEAVYLOG` is in the binary, so
        heavy debugging is compiled in). The likely mechanism is the usual one -- the
        debugger arms a breakpoint by writing a trap byte into memory, and a write to
        ROM is silently absorbed -- but that is an EXPLANATION and not a measurement,
        because the arming happens after the machine is released and cannot be observed
        from a stopped debugger. What is measured is the behaviour, and this cannot
        detect it in advance for the same reason. So it goes in the non-arrival note,
        where the caller is already asking why.
        """
        # THE ARGUMENT CHECKS THAT NEED NOTHING FROM THE MACHINE GO FIRST. Reading the
        # machine costs a settle, and a caller who passed `seconds=0` was made to wait
        # for one only to be told a constant was out of range -- and on a RUNNING
        # machine they were told about the register pane instead of about the argument
        # that was actually wrong.
        check_segment(seg)
        check_wait_bound(seconds)
        stopped = self.where()      # refuses a running machine BEFORE arming anything
        # THE OFFSET'S WIDTH IS THE CPU MODE'S. Clamping to 16 bits would refuse
        # essentially every interesting protected-mode address (a DJGPP `_main` sits
        # well past 0xFFFF), and the debugger takes a wide one: `BP 0087:00012345` is
        # accepted and listed as `BP 0087:12345`, because its list prints a MINIMUM of
        # four hex digits rather than exactly four, which is why the `:04X` this
        # compares with still matches a wider one.
        top = dcons.offset_ceiling(stopped["mode"])
        if not 0 <= off <= top:
            raise Invalid("bad_argument",
                f"an offset is 0x0 to 0x{top:X} in {stopped['mode']} mode; got "
                f"0x{off:X}. In real mode an offset past 0xFFFF addresses nothing, and "
                f"this debugger would accept it and then never fire")
        target = f"{seg:04X}:{off:04X}"
        ctl = None
        if control is not None:
            cseg, coff = control
            if not 0 <= cseg <= 0xFFFF or not 0 <= coff <= top:
                raise Invalid("bad_argument", f"the control {cseg:04X}:{coff:X} is outside what "
                              f"{stopped['mode']} mode can address")
            ctl = f"{cseg:04X}:{coff:04X}"
            # THE SAME PLACE, NOT THE SAME SPELLING: in real mode `1234:0010` and `1235:0000`
            # are one byte, and a control on the target's own byte would be counted as a
            # control hit at every arrival, and the machine released through its target.
            same = (ctl == target if str(stopped["mode"]).startswith("Pr")
                    else cseg * 16 + coff == seg * 16 + off)
            if same:
                raise Invalid("bad_argument",
                    f"the control {ctl} is the same address as the target {target}: "
                              "a control proves the target COULD have fired, and the target "
                              "cannot prove that about itself")
        # ARMING IS A WRITE TO THE MACHINE, so the session is marked BEFORE the command
        # goes out and stays marked whatever happens next. The debugger arms a code
        # breakpoint by putting a trap byte in memory -- this module's own non-arrival
        # note says so -- and `run_to` leaves that byte in place on two of its three
        # outcomes. Until now only `set_register` set this flag, so a caller could take
        # a `read_memory` over a watched address and read the trap as program bytes
        # under a header stating the session had not been written to. A measurement on
        # a forced state is not a measurement of the program, and that is the whole
        # reason this flag exists.
        self.altered = True
        self.command(f"BP {target}")
        if ctl is not None:
            self.command(f"BP {ctl}")
        armed = self.breakpoints()
        for spelled in [target] + ([ctl] if ctl is not None else []):
            if not any(f"BP {spelled}" == b["entry"] for b in armed):
                raise Invalid("readback_refused",
                    f"the debugger does not list a breakpoint at {spelled} after being "
                    f"told to set one. What it holds: {[b['entry'] for b in armed]}. "
                    f"Resuming now would run the machine with nothing to stop it, and the "
                    f"reply would blame the address rather than the arming")
        # THE TERMINAL IS DRAINED BEFORE THE MACHINE IS RELEASED -- by `_write` itself, for
        # every run key (`_release`) -- and without it the wait was decided by text that
        # arrived BEFORE it started: the read-back above leaves a whole register pane in the
        # buffer, so the first `_read` after F5 saw an `EIP=` and broke out instantly.
        # MEASURED, a ten-minute `run_to` returned "the bound expired" after a quarter of a
        # second. The drain sat on this line alone until `resume` was found to need it too.
        began = time.monotonic()
        deadline = began + seconds
        control_hits = 0
        at: dict[str, str] | None = None
        expired, saw_at = True, 0.0
        # THE CONTROL LOOP: released, waited for, read; a stop AT the control is counted and
        # the machine let go again, anything else ends the run. Without a control it is one
        # pass, which is what this method always was.
        try:
            while True:
                self._write(RUN_KEY)
                expired, saw_at = Session._await_stop(self, began, deadline, target, progress)
                if expired:
                    break
                try:
                    at = self.where()
                except NotStopped:
                    if not self.alive():
                        raise
                    # THE ANNOUNCED STOP THAT IS NOT ONE: handled below, as the running outcome
                    # whose `bound_expired` is False.
                    break
                except Invalid as exc:
                    # THE OTHER TWO WAYS `where()` REFUSES, caught with something attached. It
                    # has three (the machine is not stopped, the pane names no CPU mode, and a
                    # CUT repaint carries no `CS`/`EIP`) and only the first is `NotStopped`.
                    # Letting the other two escape whole would leave `run_to` with no
                    # `waited_s`, no `bound_expired`, and NO WORD about the breakpoint now
                    # sitting armed in a machine this call has already written to, where it
                    # will stop the next `resume` at an address nobody recorded.
                    #
                    # IT STILL REFUSES, and that is the point rather than an accident. A pane
                    # naming no CPU mode is NOT a running machine, and reporting it as one is
                    # the exact defect
                    # `test_a_partial_pane_is_refused_rather_than_called_a_running_machine`
                    # exists to pin: every clause of "the bound expired with the machine still
                    # running" was false for it. So the reading stays refused and the refusal
                    # CARRIES the irreversible part, which is the same shape `step` takes.
                    raise _still_armed(exc, target, began, ctl) from None
                # THE TARGET IS ASKED FIRST. A stop that is the target is an arrival whatever else
                # it is; only a stop that is NOT the target can be a control hit to run past.
                if control is None or Session._stopped_at(at, seg, off):
                    break
                if not Session._stopped_at(at, control[0], control[1]):
                    break
                control_hits += 1
                if time.monotonic() >= deadline:
                    # AT REST ON THE CONTROL WITH NO BOUND LEFT: reported as a stop elsewhere,
                    # and the bound DID run out, whatever the last wait saw.
                    expired = True
                    break
                at = None
        except BaseException as e:
            if cancel.is_cancellation(e):
                Session._abandon_run(self, [target] + ([ctl] if ctl is not None else []))
            raise
        if at is None:
            # THE WAIT GAVE UP (or the announcement was not a stop): the position is read
            # AFTER the loop, because the machine can be found at rest however the loop
            # ended, and `bound_expired` reports the wait rather than the machine.
            try:
                at = self.where()
            except NotStopped:
                if not self.alive():
                    raise
                # WHICH OF THE THREE IT WAS. The early one is reached the moment the
                # debugger announces a stop (prompt or repaint) and the nudge afterwards
                # comes back cut; "the bound expired" on that path would sit beside a
                # `waited_s` of nothing, a reply contradicting itself in one object.
                why = ("the bound expired with the machine still running"
                       if expired else
                       f"the debugger announced a stop after {saw_at}s but the machine "
                       f"was not stopped at the debugger when it was asked, so this is "
                       f"NOT an expired bound")
                still = (f" and so is the control at {ctl}, which fired {control_hits}x"
                         if ctl is not None else "")
                return {"target": target, "arrived": False, "running": True,
                        "stopped_at": None, "waited_s": round(time.monotonic() - began, 3),
                        "bound_expired": expired,
                        "breakpoint_removed": False,
                        "control": Session._control_block(ctl, control_hits, removed=False),
                        "note": f"{why}, and "
                                f"the breakpoint at {target} is STILL ARMED{still} -- it "
                                f"cannot be removed while the debugger is not listening. "
                                f"Every other tool here will refuse until it stops. If "
                                f"{target} is in ROM (a BIOS or option-ROM segment such as "
                                f"F000), that is why: MEASURED, a code breakpoint in ROM is "
                                f"acknowledged, appears in BPLIST, and never fires"}
            except Invalid as exc:
                raise _still_armed(exc, target, began, ctl) from None
        # ARRIVAL IS THE SAME PLACE, NOT THE SAME SPELLING. In real mode many seg:off pairs
        # alias one physical byte, and the CPU stops with the PROGRAM'S CS:IP while the
        # breakpoint was armed at whatever paragraph the caller (or the symbol layer, which
        # folds a map frame onto the load paragraph) chose: a breakpoint that fired then read
        # as "stopped elsewhere" and was left armed. Protected mode compares selector and
        # offset directly, because the breakpoint was armed at the live selector.
        arrived = Session._stopped_at(at, seg, off)
        on_control = control is not None and Session._stopped_at(at, control[0], control[1])
        removed, cleanup = False, ""
        if arrived:
            removed, cleanup = Session._remove_own_breakpoint(self, target)
        control_removed = False
        if ctl is not None:
            # THE CONTROL IS OURS ON EVERY STOPPED OUTCOME: nobody asked to keep it, and left
            # behind it would stop the caller's next `resume` at a place they never named.
            control_removed, control_cleanup = Session._remove_own_breakpoint(self, ctl)
            cleanup += control_cleanup
        # `bound_expired` IS ON EVERY RETURN, not only the one that needed it, and it
        # carries the MEASUREMENT on both. A field that appears on one branch is a
        # field a caller must first discover the shape of the reply to read, and this
        # class's own doubles are the evidence: two of them drifted from the field sets
        # they stand in for.
        #
        # IT IS `expired` AND NOT `False`, which is a correction found by breaking it: the
        # bound CAN expire and the machine still be found at the target, because the
        # arrival is read AFTER the loop gives up. Hardcoding False there reported a
        # bound that demonstrably ran out as one that did not, and made the case
        # asserting it unfalsifiable.
        return {"target": target, "arrived": arrived, "running": False,
                "stopped_at": at, "waited_s": round(time.monotonic() - began, 3),
                "bound_expired": expired,
                "breakpoint_removed": removed,
                "control": Session._control_block(ctl, control_hits,
                                                  removed=control_removed),
                "note": cleanup.strip() if arrived else
                        (f"it came to rest ON the control {ctl} (its hit number "
                         f"{control_hits}) when the bound ran out, and not at {target}"
                         if on_control else
                         f"it stopped at {at['cs']}:{at['eip']} and not at {target}: "
                         f"something else got there first") +
                        f". The breakpoint at {target} is still armed"
                        + (f". The wait ran its full {seconds}s bound before this "
                           f"stop was read, which is what `bound_expired` reports: "
                           f"the machine is at rest, whatever the flag looks like"
                           if expired else "")
                        + cleanup}

    def _await_stop(self, began: float, deadline: float, target: str,
                    progress: Progress = no_progress, label: str = "") -> tuple[bool, float]:
        """Listen for the debugger to announce a stop, until `deadline`: `(expired, saw_at)`,
        reporting the seconds spent through `progress` as it listens. `label` heads the
        progress line when the wait is not `run_to`'s (the sequence executor's wait for the
        next console step says what it waits for in its own words).

        CALLED AS `Session._await_stop(self, ...)` from `run_to`, like the other three helpers
        below: the suite drives `run_to` through scripted doubles that are not `Session`s and
        carry only what the method reaches for, so a helper looked up on `self` is a helper
        the doubles do not have.

        WAITING IS DONE ON THE TERMINAL AND NOT BY ASKING. Every question here is a
        command typed at a debugger that is not reading while the guest runs, so a
        poll would queue keystrokes to be executed at whatever the machine stops on.
        A stop hands the keyboard back to the debugger, which prints its PROMPT, so
        the arrival announces itself and this only has to be listening. The register
        pane is NOT a reliable announcement (`run_to`'s docstring has the count): it is
        repainted only when its cells changed.
        """
        carry = ""
        next_tick = began + PROGRESS_EVERY_S
        while (now := time.monotonic()) < deadline:
            cancel.check()
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - began, None, f"{label or f'run_to {target}'}: running "
                                            f"{now - began:.0f}s of {deadline - began:g}s")
            # THE DEATH IS CHECKED IN THE LOOP, the fix `e9_wait` already carries and
            # this one did not. Without it a session that died the instant the machine
            # was released burned the WHOLE bound -- up to RUN_TO_MAX, ten minutes --
            # with the server's lock held, so `status` could not even be asked. MEASURED
            # against a dead double: the whole bound spent polling, and `alive()`
            # consulted ZERO times until the loop was over.
            if not self.alive():
                raise Invalid("session_broken",
                    f"the emulator is GONE, {round(time.monotonic() - began, 1)}s into "
                    f"a {round(deadline - began, 1)}s wait for {target}. Nothing will "
                    f"arrive, so a longer bound would not help: this needs a new session, "
                    f"not a bigger number")
            # ONLY THE FRESH TEXT IS SCANNED, PLUS A BOUNDED CARRY. Re-parsing the whole
            # accumulated terminal every poll is quadratic in the length of the wait,
            # which is the defect `e9_wait` measured on its side and fixed. MEASURED here on
            # the same regex: doubling the polls quadrupled the cost, against a flat cost
            # for the fresh-only form, with the server's lock held throughout.
            #
            # THE CARRY IS WHY THIS IS NOT SIMPLY "SCAN THE NEW PART". A read is cut
            # wherever the pipe happened to be, so `EIP=00001` can arrive in one poll
            # and `000` in the next; scanning each chunk alone would miss a match the
            # accumulating version found, which would be trading a cost defect for a
            # correctness one. `STOP_CARRY` covers the longest `NAME=` head `REGISTER`
            # needs to fire (its value group is `+`, so a value split across reads still
            # matches on its head) and the whole prompt, so neither announcement can be
            # lost to a split.
            fresh = carry + self._read(0.25)
            # EITHER ANNOUNCEMENT ENDS THE WAIT. The prompt is the one a stop reliably
            # sends (see the docstring); the register repaint is kept because a first
            # stop after a fresh pane does resend it, and it costs one regex.
            if dcons.PROMPT in fresh or dcons.parse_registers(fresh).get("EIP"):
                if dcons.PROMPT in fresh:
                    self._mark_stopped()   # heard here, before any reader consumes it
                # THE MOMENT IS STAMPED HERE, where it happened, and not after `where()`
                # has run (a NUDGE plus a collect, up to its own timeout): read there, a
                # repaint seen at once is reported as arriving after the whole nudge, and
                # the two `monotonic()` calls disagree inside one reply.
                return False, round(time.monotonic() - began, 1)
            carry = fresh[-dcons.STOP_CARRY:]
        return True, 0.0

    @staticmethod
    def _stopped_at(at: dict[str, str], seg: int, off: int) -> bool:
        """Whether a stop position IS `seg:off`: by selector and offset in protected mode, by
        physical address in real mode, where many `seg:off` pairs alias one byte."""
        if str(at["mode"]).startswith("Pr"):
            return at["cs"] == f"{seg:04X}" and int(at["eip"], 16) == off
        return int(at["cs"], 16) * 16 + int(at["eip"], 16) == seg * 16 + off

    @staticmethod
    def _control_block(ctl: str | None, hits: int, *, removed: bool) -> dict[str, object] | None:
        """The `control` field of a `run_to` reply: `null` when none was given, else where it
        was armed, how many times it fired, and whether it was removed again. ONE key on every
        reply, so a caller never has to discover the shape first."""
        if ctl is None:
            return None
        return {"at": ctl, "hits": hits, "removed": removed}

    def _abandon_run(self, own: list[str]) -> None:
        """A RUN CANCELLED IN FLIGHT LEAVES NOTHING ARMED: it has no reply to say what it left,
        so the guest is brought back with `BREAK` and the breakpoints it armed are removed,
        shielded, as a run stopped elsewhere removes its control. A terminal that cannot answer
        leaves them, and the stop end then reads the machine as it finds it."""
        with cancel.shielded(), contextlib.suppress(Invalid, OSError):
            if not self.at_debugger():
                self.break_in()
            for spelled in own:
                Session._remove_own_breakpoint(self, spelled)

    def _remove_own_breakpoint(self, spelled: str) -> tuple[bool, str]:
        """Remove a breakpoint THIS call armed, on a stopped machine: `(removed, note)`.

        THE CLEANUP MAY NOT DESTROY THE RESULT. It is three more round trips after the
        machine has ALREADY arrived, and any of them can refuse (a pane that did not
        repaint, a listing with no header, a dropped read). Letting that escape threw
        away a true arrival and handed the caller INVALID about a breakpoint list -- so
        the failure is reported as what it is, a cleanup that could not be confirmed,
        beside the arrival that did happen.

        LOOKED UP AGAIN, not reused: `BPDEL` renumbers what is left, and the index recorded
        at arming time is only correct if nothing has been deleted since. Finding it by its
        own text cannot go stale that way.
        """
        try:
            here = self.breakpoints()
            mine = [b for b in here if f"BP {spelled}" == b["entry"]]
            if not mine:
                return False, (f" The breakpoint at {spelled} was not in the list at "
                               f"cleanup time, so nothing was removed and something "
                               f"else took it away.")
            self.command(f"BPDEL {mine[0]['index']}")
            removed = not any(f"BP {spelled}" == b["entry"] for b in self.breakpoints())
            if not removed:
                return False, (f" `BPDEL` was sent and {spelled} is STILL in the "
                               f"debugger's list: it will stop the next `resume`.")
            return True, ""
        except Invalid as exc:
            return False, (f" The arrival is sound; the cleanup could not be confirmed "
                           f"({exc}). Assume the breakpoint at {spelled} is still armed.")

    def watch(self, segment: int, offset: int) -> dict[str, object]:
        """Break when a piece of memory CHANGES, choosing the command for the caller. The
        arming half of a change watch: `watch_add` resolves the name and comes here.

        IT FIRES ON A CHANGE AND NOT ON AN ACCESS, which is the debugger's own wording
        ("Set memory breakpoint (memory change)") and the thing most likely to be
        misread. A read never fires it, and neither does a write that stores the value
        already there -- so a location being hammered with the same byte looks, through
        this, exactly like one nothing touches.

        THE SELECTOR-VERSUS-SEGMENT CHOICE IS EATEN HERE, which is the whole reason
        this is a tool rather than a spelling of three debugger commands. Given
        `segment` and `offset` it reads the CPU MODE off the machine and sends `BPM` in
        real mode and `BPPM` in protected mode -- the same sixteen bits, two completely
        different meanings, and the debugger accepts either without comment. A caller
        who had to make that choice would have to make it correctly on every call, in a
        session whose mode changes underneath them as the program boots.

        THERE IS NO LINEAR FORM, ON PURPOSE: `BPLM` watches a LINEAR address, and a DPMI
        program runs PAGED, so the frame named belongs to whoever holds it at that instant
        -- MEASURED, an attempt to watch a static in a DJGPP binary that way fired on
        unrelated code and never on the app. The raw tool that offered it was retired.
        """
        # THE MACHINE IS READ FIRST: a command typed at a running guest is a refusal with
        # a side effect, and `command()` appends a carriage return that `resume`'s own
        # docstring says must never land on a running machine.
        cpu = self.where()["mode"]
        check_segment(segment)
        top = dcons.offset_ceiling(cpu)
        if not 0 <= offset <= top:
            raise Invalid("bad_argument", f"an offset is 0x0 to 0x{top:X} in {cpu} mode; got "
                          f"0x{offset:X}")
        # THE THREE LIST SPELLINGS ARE MEASURED, NOT DERIVED. What the debugger
        # PRINTS in `BPLIST` is not what you SEND, and it is not uniform:
        #
        #   BPM  0040:006C   -> `BPMEM 0040:006C (00)`      offset %04X
        #   BPPM 00AF:6024   -> `BPPM 00AF:00006024 (00)`   offset %08X, no `MEM`
        #   BPLM 000B8000    -> `BPLM 000B8000 (00)`
        #
        # Deriving them (`BPPMEM 00AF:6024`, say) is wrong on BOTH axes, so EVERY
        # protected-mode watch would arm the breakpoint and then refuse, with a
        # message blaming the one cause that was not it; and a test fixture AUTHORED
        # from the same belief as the code cannot see it, which is why these three
        # came off a real debugger.
        if cpu.startswith("Pr"):
            command = f"BPPM {segment:04X}:{offset:04X}"
            entry = f"BPPM {segment:04X}:{offset:08X}"
        else:
            command = f"BPM {segment:04X}:{offset:04X}"
            entry = f"BPMEM {segment:04X}:{offset:04X}"
        # SAME AS `run_to`: arming is a write, and a watch is NEVER removed by this
        # method, so the mark is if anything more owed here than there.
        self.altered = True
        self.command(command)
        # READ BACK, for the same reason `run_to` does: the acknowledgement is printed
        # into a scrolling pane and can be a repaint of an older one. The list entry's
        # trailing byte count is not compared -- what is being confirmed is that a
        # watch on THIS address exists, not how this build formats its widths.
        held = self.breakpoints()
        if not any(b["entry"].startswith(entry) for b in held):
            raise Invalid("readback_refused",
                f"the debugger does not list a watch matching `{entry}` after `{command}`. "
                f"What it holds: {[b['entry'] for b in held]}. A watch that was never "
                f"armed and one that never fires are the same silence")
        # `mode` IS THE MACHINE'S CPU MODE, the reading the command was chosen from.
        return {"command": command, "mode": cpu, "armed": entry, "breakpoints": held,
                "fires_on": "a CHANGE to the value, never a read and never a write of "
                            "the value already there"}

    # -------------------------------------------------------- staged code breakpoints

    def arm_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        """Arm a CODE breakpoint at `seg:off` and LEAVE THE MACHINE STOPPED.

        This is `run_to`'s arming half without the release: `run_to` arms one breakpoint
        and starts the machine in the SAME gesture, so several cannot be staged and then
        the machine let go ONCE -- which is the only workable shape on this platform,
        because a breakpoint canNOT be armed once the guest is running. The reply carries
        the debugger's list read BACK, never the acknowledgement, for the scrolling-pane
        reason `run_to` states: a `DEBUG: Set breakpoint at ...` can be a repaint.

        THE ADDRESS'S WIDTH IS THE CPU MODE'S, from `where()`, which also refuses a running
        machine before anything is written. Arming writes a trap byte, so the session is
        marked `altered` here as `run_to` and `watch` mark it.
        """
        stopped = self.where()      # refuses a running machine BEFORE arming
        check_segment(seg)
        top = dcons.offset_ceiling(stopped["mode"])
        if not 0 <= off <= top:
            raise Invalid("bad_argument",
                f"an offset is 0x0 to 0x{top:X} in {stopped['mode']} mode; got "
                          f"0x{off:X}. In real mode an offset past 0xFFFF addresses "
                          f"nothing, and the debugger would accept it and then never fire")
        target = f"{seg:04X}:{off:04X}"
        self.altered = True
        self.command(f"BP {target}")
        held = self.breakpoints()
        want = ("BP", seg, off)
        listed = next((b for b in held if dcons.bp_row_target(b["entry"]) == want), None)
        if listed is None:
            raise Invalid("readback_refused",
                f"the debugger does not list a breakpoint at {target} after being told to "
                f"set one. What it holds: {[b['entry'] for b in held]}. It was NOT armed, "
                f"so a caller releasing the machine now would run with nothing to stop it")
        return {"target": target, "entry": listed["entry"], "breakpoints": held}

    def clear_code_breakpoint(self, seg: int, off: int) -> dict[str, object]:
        """Remove a code breakpoint at `seg:off`, by its own text, and READ THE LIST BACK.

        It looks the index up freshly rather than trusting a remembered one, because
        `BPDEL` renumbers what is left, so a stale index deletes the wrong row. `removed`
        is the machine's answer, not this method's claim: it is true only when the entry
        is gone from the list read after the delete.
        """
        stopped = self.where()
        top = dcons.offset_ceiling(stopped["mode"])
        if not (0 <= seg <= 0xFFFF and 0 <= off <= top):
            raise Invalid("bad_argument", f"{seg:X}:{off:X} is not an address this mode can hold")
        want = ("BP", seg, off)
        target = f"BP {seg:04X}:{off:04X}"
        mine = [b for b in self.breakpoints() if dcons.bp_row_target(b["entry"]) == want]
        if not mine:
            return {"entry": target, "removed": False, "note": "no such breakpoint to remove"}
        self.command(f"BPDEL {mine[0]['index']}")
        removed = not any(dcons.bp_row_target(b["entry"]) == want for b in self.breakpoints())
        return {"entry": mine[0]["entry"], "removed": removed}

    def clear_interrupt_breakpoint(self, number: int,
                                   ah: int | None = None) -> dict[str, object]:
        """Remove an interrupt breakpoint by its own ROW TEXT, and READ THE LIST BACK.

        It is `clear_code_breakpoint` for the `BPINT` family, and it exists because the
        console was the only way to remove one and the console takes an INDEX: `BPDEL n`
        numbers the list as the debugger prints it, which is NOT the arming order --
        MEASURED, a session that armed `BPINT 31` first and two `BP`s after listed the
        code breakpoints at 00 and 01 and the interrupt at 02, so `BPDEL 0` deleted the
        wrong one. The row is found by its whole text (the spelling `breakpoint_interrupt`
        already captures), the index looked up fresh, and `removed` is what the list says
        AFTER the delete, never what this method sent.
        """
        check_interrupt(number, ah)
        self.where()                      # refuses a running machine before the console
        want = dcons.interrupt_row(number, ah)
        mine = [b for b in self.breakpoints() if b["entry"] == want]
        if not mine:
            return {"entry": want, "removed": False, "note": "no such breakpoint to remove"}
        self.command(f"BPDEL {mine[0]['index']}")
        removed = not any(b["entry"] == want for b in self.breakpoints())
        return {"entry": want, "removed": removed}

    # ------------------------------------------------------------------ the log

    def e9(self, pattern: str, limit: int = 40) -> tuple[list[str], int]:
        """The guest's own instrumentation, FILTERED at the source.

        The whole point of a live session is that what crosses back is the answer and
        not a haystack with the answer in it, so the filtering happens here and the
        caller receives lines rather than a log.

        It distinguishes the two kinds of nothing, which is the contract this module
        exists to enforce: a log with no instrumentation AT ALL is INVALID, and a log
        with instrumentation but nothing matching is an empty list, which is an answer.
        """
        return dlogs.filter_e9(self._e9_text(), pattern, limit)

    def e9_lines(self) -> list[str]:
        """EVERY line of the guest's instrumentation, in order, with `e9`'s guard on the
        channel: what the stop reply's E9 block reduces from. It carries no `limit`
        because the reduction is the server's, and the caller-facing ceiling on `e9` and
        `log` refused the whole-log read this block needs (measured: `1 << 30` as the
        limit, refused as a haystack, and every stop's `e9` block came back
        `available: false`)."""
        return dlogs.log_hits(self._e9_text(), ".", "guest")

    def log(self, pattern: str, limit: int, channel: str) -> tuple[list[str], int]:
        """The log's `channel`, filtered at the source: the guest's E9 lines with `e9`'s
        own guard (a file with no instrumentation is no channel), the emulator's own
        lines, or the whole file tagged."""
        dlogs.check_channel(channel)
        if channel == "guest":
            return dlogs.filter_e9(self._e9_text(), pattern, limit)
        return dlogs.filter_log(self._log_text(), pattern, limit, channel)

    def _log_text(self) -> str:
        """The log file, or the refusal that says which nothing: no logfile on the
        session, or a file the emulator has not created yet."""
        if self.launch.logfile is None:
            raise Invalid("no_channel", "this session was started without a logfile, so there is "
                          "no log channel to filter")
        if not self.launch.logfile.exists():
            raise Invalid("no_channel", f"no log at {self.launch.logfile}: the emulator has not "
                          f"written anything yet, which is not the same as having "
                          f"nothing to say")
        return self.launch.logfile.read_text(encoding="utf-8", errors="replace")

    def _e9_text(self) -> str:
        """The instrumentation log, or the refusal that says WHICH nothing.

        The three guards are `e9`'s, lifted so `e9_wait` cannot answer for reasons `e9`
        refuses on. They are the difference between "your pattern matched
        nothing" and "there was no channel to match against", which is this module's
        thesis in one method.
        """
        text = self._log_text()
        if dlogs.count_e9(text) == 0:
            raise Invalid("no_channel",
                f"{self.launch.logfile} carries no instrumentation at all. That is "
                f"not 'your pattern matched nothing', it is 'there is nothing to "
                f"match': either the guest has not reached its first trace yet, or "
                f"this build does not emit any")
        return text

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        """The COMPLETE lines of `channel` after byte `offset`, and the new offset.

        THREE DEFECTS DIE WITH THIS, and they were all one defect: the wait used to
        re-read the whole file and index it by LINE NUMBER.

        A HALF-WRITTEN LINE STOPS BEING A LINE. A log written through ordinary stdio
        ends MID-LINE between flushes -- that is the steady state while a writer is
        producing, not a rare race -- and `splitlines()` hands that fragment back as an
        element. `E9_LINE` matches it, because it only anchors the prefix. So the
        fragment CONSUMED A LINE INDEX, and when the rest of the line arrived the count
        did not grow: the completed line was never tested again. MEASURED, the caller
        got "a bound that expired" for a line that was sitting in the file, and `e9` on
        the same file found it. The mirror was as bad: when the fragment did match, it
        was returned as the guest's trace with its payload missing. Cutting at the last
        newline means a line is only ever seen whole, once.

        AND IT IS WHY THE COST IS BOUNDED. Re-reading the whole file every tenth of a
        second was MEASURED on a log of a few megabytes: gigabytes read and over a minute
        of CPU inside a ten-minute wait, with the server's lock held, growing
        quadratically as the log grows under it. Reading only what is new is the same
        answer for the size of the new part.

        A LOG THAT HAS SHRUNK IS REFUSED rather than resynchronised. Truncation or
        rotation makes every byte offset meaningless, and the two ways to carry on are
        both wrong: keeping the offset silently stops seeing anything, and resetting it
        re-reports old lines as new. It is rare and it is nameable, so it is named.
        """
        log = self.launch.logfile
        assert log is not None            # the caller refuses a session without one
        if not log.exists():
            # NOT AN ERROR HERE. The guest may not have written yet, which is exactly
            # what a wait is for; `e9` refuses on this and this deliberately does not.
            return [], offset
        size = log.stat().st_size
        if size < offset:
            raise Invalid("session_broken",
                f"{log} has SHRUNK from {offset} bytes to {size} while this was "
                f"waiting: it was truncated or rotated underneath. Every offset into "
                f"it is now meaningless, and both ways of carrying on are wrong -- "
                f"keeping it sees nothing more, resetting it reports old lines as new")
        with log.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read()
        cut = chunk.rfind(b"\n") + 1
        if cut == 0:
            return [], offset
        # DECODED ONLY UP TO A NEWLINE, which is also what keeps a multi-byte character
        # from being split across two reads: `\n` is a byte boundary in UTF-8, so the
        # consumed prefix is always whole characters.
        text = chunk[:cut].decode("utf-8", errors="replace")
        return (dlogs.channel_lines(text.splitlines(), channel), offset + cut)

    def e9_new_since(self, offset: int) -> tuple[list[str], int]:
        """The complete instrumentation lines after byte `offset` and the offset to read
        from next: the stop survey's reader, so a stop pays for what the guest wrote since
        the previous one and not for the whole log again. It refuses what `e9` refuses: a
        session with no logfile has no channel, and a log the guest has not created yet
        cannot be looked at, which is not zero lines. The wait's reader keeps its own
        reading of an absent log, because nothing yet is what a wait is for."""
        if self.launch.logfile is None:
            raise Invalid("no_channel",
                "this session was started without a logfile, so there is no "
                          "instrumentation channel to summarise")
        if not self.launch.logfile.exists():
            raise Invalid("no_channel",
                f"no log at {self.launch.logfile}: the guest has not written "
                          f"anything yet, which is not the same as having nothing to say")
        return self._e9_since(offset)

    def e9_since_mark(self, mark: int) -> list[str]:
        """Every complete instrumentation line written after byte `mark`, in order: the
        LOOK after an act. A session with no logfile has no channel; a log that has not
        appeared yet answers nothing, which is an answer about the window. The count is
        bounded by what the guest wrote, not by a limit here: the caller cuts."""
        if self.launch.logfile is None:
            raise Invalid("no_channel",
                "this session was started without a logfile, so there is no "
                          "instrumentation channel to look at")
        lines, _ = self._e9_since(mark)
        return lines

    def e9_mark(self) -> int:
        """WHERE THE LOG ENDS RIGHT NOW, as a byte position `e9_wait(mark=)` starts from.

        It is what turns "did the guest react to THIS event" into an answerable question:
        a wait from the mark sees only what was written after it, so a line that matched
        the pattern ten seconds ago is history and not the reaction. A log that does not
        exist yet marks at 0, which is the same statement -- everything the guest will
        write is after it. A session with no logfile has no channel to mark.

        THE SIZE, NOT THE LAST NEWLINE, deliberately. A writer flushes mid-line, so the
        mark can land inside a line; `_e9_since` then drops that line's tail as a fragment
        that is not an instrumentation line, which is right -- a line BEGUN before the mark
        belongs to before it. Finding the last newline would mean reading the whole file,
        which on a multi-megabyte log is the cost `_e9_since` was written to avoid.
        """
        if self.launch.logfile is None:
            raise Invalid("no_channel",
                "this session was started without a logfile, so there is no "
                          "instrumentation channel to mark a position in")
        log = self.launch.logfile
        return log.stat().st_size if log.exists() else 0

    def e9_wait(self, pattern: str, seconds: float, mark: int = 0,
                progress: Progress = no_progress) -> dict[str, object]:
        """`log_wait` on the guest channel: the wait `expect` and `drive` rest on."""
        return self.log_wait(pattern, seconds, "guest", mark, progress)

    def log_wait(self, pattern: str, seconds: float, channel: str, mark: int = 0,
                 progress: Progress = no_progress) -> dict[str, object]:
        """WHEN a line of `channel` matching `pattern` happened -- whether it already has,
        or not yet.
        While it waits it reports the seconds spent, and the lines that arrived, through
        `progress`.

        `mark` is the byte position the search starts from (`e9_mark`): with it, "already"
        means "written since the mark", and everything before the mark is invisible. That
        is the difference between "the cue has fired at some point" and "the cue fired in
        response to the key just posted", and it is the whole of what `send_keys`'
        verification rests on.

        BOTH SEMANTICS, IN ONE TOOL, and that is the whole design rather than a
        convenience. Between launching the emulator and asking, the thing you are
        waiting for may ALREADY have gone past; a tool that only waits would then sit
        out its whole bound and report that it never happened, which is false and
        expensive. So this looks at what the log already holds FIRST, and only waits if
        it has to. `already` says which of the two answers you got, because they mean
        different things: one is history, the other is something you were present for.

        WHICH OCCURRENCE: the FIRST. The question this answers is "when did it happen",
        and for a line that fired more than once the first time is the answer;
        `lines_total` says how many there were, so a caller who wanted the latest knows
        there is one. (`e9` is the tool for the recent state -- it keeps the newest.)

        A BOUND THAT EXPIRES IS INVALID, never an empty answer, and the message says
        what was examined: how long it watched, how many instrumentation lines went by,
        and that the channel was there. A caller who asked "wait for X" and got "no
        lines" cannot tell "X did not happen in this window" from "there was nothing to
        match against", and this package refuses to print the same thing for both.

        WHAT YOU CAN DO WITH THE MOMENT, and it is narrower than it looks. A guest
        writing traces is a guest that is RUNNING, so ordinarily the machine is still
        running when this returns from a wait, and this debugger's console does not
        accept commands then -- which every reader here demonstrates by refusing. So you
        ordinarily cannot arm a breakpoint at the moment this hands you, and you must
        ASK rather than assume: a breakpoint armed earlier can fire between the line
        being written and the poll that reads it, and this reply carries no `running`
        field. The reason is the CONSOLE and not dosbox-x #4026, which is about breaking
        in with a host keypress -- a different path, and one `breakpoint_interrupt`
        records as MEASURED working. What the moment is for: choosing an address to arm
        on the NEXT run, before the machine is released.
        """
        check_wait_bound(seconds)
        rx = dlogs.compiled(pattern)
        dlogs.check_channel(channel)
        kind = "instrumentation" if channel == "guest" else channel
        # THE ONLY REFUSAL THAT SURVIVES THE WAIT, and `e9`'s other two deliberately do
        # not. A session with no logfile has no channel and waiting cannot create one.
        # But a log that does not EXIST yet, and a log with no instrumentation IN it,
        # are the ordinary state of a guest that has just been resumed -- and `e9`
        # refuses on both. Lifting all three would make this tool unable to wait for the
        # guest's FIRST trace: MEASURED, `start` then `resume` then `e9_wait("BOOT")`
        # refuses at once against its bound, for a line that arrives a fraction of a
        # second later, while `_e9_text`'s own message names that very case ("the guest
        # has not reached its first trace yet"). The two states are reported in the
        # expiry instead, where they are an ANSWER about the window.
        if self.launch.logfile is None:
            raise Invalid("no_channel",
                "this session was started without a logfile, so there is no "
                          "instrumentation channel to wait on, and waiting cannot "
                          "bring one into existence")
        began = time.monotonic()
        lines, offset = self._e9_since(mark, channel)
        total = len(lines)

        # EVERY COUNT IS "SINCE THE MARK", and the field says so by its name. With the
        # default mark the examined region is the whole log; with a mark it is what was
        # written after it, and a field called `lines_in_log` then lied by exactly the
        # lines before the mark. `since_mark` rides along so a reader can tell which.
        def found(hit: list[str], already: bool, before: int) -> dict[str, object]:
            # `lines_before` is how many lines sit between the mark and the match: a
            # reaction that landed AFTER a post (the mark is taken before it) shows as such,
            # which `already` alone cannot say -- from a mark, `already` means "there when
            # the wait first looked", history or not.
            return {"line": hit[0], "already": already, "lines_total": len(hit),
                    "lines_before": before, "arrived_during": total - len(lines),
                    "waited_s": 0.0 if already else round(time.monotonic() - began, 3),
                    "lines_examined": total, "since_mark": mark}

        def last_look() -> dict[str, object] | None:
            """ONE LAST READ BEFORE ANY REFUSAL FROM INSIDE THE WAIT, the same for all three
            (gone, stopped, expired): the loop checks the condition FIRST and reads LAST, so a
            line written after the final read and before the condition was never looked for
            -- the canonical case being a guest's EXIT trace, written on its way out, and for
            a stop the reaction logged just before the breakpoint on its handler fired."""
            nonlocal offset, total
            fresh, offset = self._e9_since(offset, channel)
            total += len(fresh)
            hit = [ln for ln in fresh if rx.search(ln)]
            return found(hit, False, total - len(fresh) + fresh.index(hit[0])) if hit else None

        hits = [ln for ln in lines if rx.search(ln)]
        if hits:
            return found(hits, True, lines.index(hits[0]))
        deadline = began + seconds
        next_tick = began + PROGRESS_EVERY_S
        newest = ""
        while (now := time.monotonic()) < deadline:
            cancel.check()
            if now >= next_tick:
                next_tick = now + PROGRESS_EVERY_S
                progress(now - began, None,
                         f"log_wait {channel} /{pattern}/: {now - began:.0f}s of "
                         f"{seconds:g}s, {total - len(lines)} lines arrived"
                         + (f", last: {newest[:LAST_LINE_SHOWN]}" if newest else ""))
            # A STOPPED GUEST WRITES NOTHING, so a wait on one cannot end well and its
            # expiry would blame the program. MEASURED: a breakpoint
            # from another session parked the guest mid-plan and this sat out 40 s to say
            # "the emulator is still running". Asked every poll, because a breakpoint can
            # fire during the wait too; the answer is passive (no console round trip).
            if self.at_debugger():
                if (late := last_look()) is not None:
                    return late
                raise _wait_stopped(pattern, total - len(lines),
                                    round(time.monotonic() - began, 3))
            # THE DEATH IS CHECKED IN THE LOOP, not once in the message at the end.
            # Consulted only while composing the refusal, a session that died at the
            # start would burn the WHOLE bound, with the server's lock held so `status`
            # could not be asked, before saying so, and then advise asking again with a
            # longer bound, which is the one thing that cannot help a dead emulator.
            if not self.alive():
                # ONE LAST READ BEFORE REFUSING, and the refusal's own next sentence is
                # why it must happen: nothing more WILL be written, so this is the last
                # chance to read what already was. The loop checks `alive()` FIRST and
                # reads LAST, so a line written after the final read and before the
                # death was never looked for at all -- and that is the canonical case,
                # waiting for a guest's exit trace. MEASURED against a double whose
                # guest writes its trace on the way out: the line was sitting unread in
                # the log at the instant of refusal, and `e9` on the same log found it.
                if (late := last_look()) is not None:
                    return late
                raise Invalid("session_broken",
                    f"the emulator is GONE, {round(time.monotonic() - began, 1)}s into "
                    f"a {seconds}s wait for {pattern!r}, and a final read of the log "
                    f"after it died found nothing matching either. Nothing more will "
                    f"be written, so a longer bound would not help: this needs a new "
                    f"session, not a bigger number")
            time.sleep(E9_POLL)
            fresh, offset = self._e9_since(offset, channel)
            total += len(fresh)
            newest = fresh[-1].strip() if fresh else newest
            seen = [ln for ln in fresh if rx.search(ln)]
            if seen:
                return found(seen, False, total - len(fresh) + fresh.index(seen[0]))
        # AND ONE LAST READ HERE TOO, for the same reason on the other path: the loop
        # leaves on the CLOCK, so whatever the guest wrote between the final poll and
        # the deadline -- up to a whole `E9_POLL` -- had never been looked for. The
        # window is small and the answer it holds is exactly the one being waited for.
        if (late := last_look()) is not None:
            return late
        # THE COUNT IS THE ONE THAT ANSWERS THE QUESTION BEING ASKED. The log's TOTAL under
        # the words "went past" would make a wait during which NOTHING happened, on a log
        # carrying five thousand earlier traces, say "5000 instrumentation line(s) went
        # past", which anyone diagnosing a silent guest reads as a live channel. The two
        # numbers are different facts and both are given, and the second one is named for
        # the region it counts, since with a mark the examined region is not the log.
        during = total - len(lines)
        # THE EXPIRY ASKS TOO. The loop asks at every poll, so a stop it sees refuses at once;
        # a stop that lands after the last poll and before the clock would otherwise reach
        # a refusal saying "The emulator is still running" (the PROCESS) while the debugger
        # held the machine. Passive, like the loop's.
        if self.at_debugger():
            raise _wait_stopped(pattern, during, round(time.monotonic() - began, 3), seconds)
        region = "in the log altogether" if mark == 0 else f"since the mark at byte {mark}"
        # HOISTED OUT OF THE f-STRING because a line break inside a replacement field is
        # 3.12 syntax and this package targets 3.11 -- `ruff` caught it, `mypy` did not.
        silent = ("" if during else
                  " The guest wrote NOTHING at all in this window, so the question may "
                  "be whether it is still emitting rather than what it emitted.")
        raise E9Expired(
            f"nothing matched {pattern!r} in {round(time.monotonic() - began, 1)}s. "
            f"{during} {kind} line(s) arrived DURING the wait ({total} "
            f"{region}), so this is a bound that expired and not 'there was "
            f"nothing to match against'.{silent} The emulator is still running. Asking "
            f"again with a longer bound is a different question from asking whether "
            f"the line ever appears")

    def memdump(self, seg: int, off: int, length: int, dest: Path) -> Path:
        """Memory to a FILE, returning the path it ended up at.

        `MEMDUMPBIN` writes into the debugger's working directory under `MEMDUMP_FILE` (why a
        name is passed at all is that constant's comment); the emulator is never told `dest`,
        which is where this MOVES the file to. WHERE the file can land is
        `_memdump_candidates`' business.

        `dest` IS USED, AND THE CHECK IS ON THE FILE THE DEBUGGER WROTE. Accepting
        `dest`, never using it and then checking it has two outcomes and both are
        wrong: normally the caller's path does not exist, so every dump reports INVALID
        and blames the emulator; and when anything happens to be sitting at that path
        already, the tool returns `ok` with a byte count for a file of UNRELATED bytes,
        which the caller then reads as guest memory.
        """
        check_segment(seg)
        check_dump_length(length)
        candidates = self._memdump_candidates()
        # Judged before the debugger writes anything, so a refusal leaves no dump behind to
        # poison the next call: the place (`judge_collection`), a leftover (`refuse_leftover`),
        # and `dest` itself (`paths.fresh_dest`: its directory there, nothing at it). The
        # helpers are shared with `trace`, which collects its log the same way.
        dcollect.judge_collection(dest, self.launch.cwd, candidates, "dump")
        dcollect.refuse_leftover(candidates, "dump")
        paths.fresh_dest("dest", dest)
        # EVERY REFUSAL FROM THE COMMAND ON TAKES THIS CALL'S FILE AWAY. `refuse_leftover` proved
        # no candidate was there before it, so one there now is the debugger's answer to it;
        # left behind, it is refused as somebody's by every later dump on the session.
        try:
            out = self.command(f"MEMDUMPBIN {seg:04X}:{off:04X} {length:X} {MEMDUMP_FILE}")
            said = [ln for ln in out.splitlines() if MEMDUMP_OK in ln or MEMDUMP_FAIL in ln]
            if not said or MEMDUMP_OK not in said[-1]:
                raise Invalid("unexpected_answer",
                    f"the debugger did not report a successful dump. What it "
                              f"showed: {out.strip()[-300:]!r}")
            source = next((c for c in candidates if c.exists()), None)
            if source is None:
                raise Invalid("unexpected_answer", f"the debugger reported success and none of "
                              f"{[str(c) for c in candidates]} exists. Those disagree, so "
                              f"this is not a reading")
            # THE SIZE IS THE ONE THING TYING THESE BYTES TO THIS REQUEST, so it is checked
            # for EQUALITY and not for being non-empty: `length` is in hand, and `> 0`
            # accepts any file at all.
            got = source.stat().st_size
            if got != length:
                raise Invalid("readback_refused",
                    f"asked the debugger for {length} bytes and {source} holds "
                              f"{got}. That is not the dump that was asked for")
            return dcollect.collect(source, dest, "dump")
        except BaseException as exc:
            # A HOST ERROR TOO (the terminal broke after the debugger wrote): whatever escapes,
            # the file is this call's. One this cannot remove is named by the next call's
            # leftover refusal, so the failure is not lost; it must not replace the one raised.
            kept: dict[Path, str] = {}
            for c in candidates:
                try:
                    c.unlink()
                except FileNotFoundError:
                    pass
                except OSError as gone:
                    # One file under both spellings, where the filesystem folds case: named once.
                    try:
                        again = any(c.samefile(k) for k in kept)
                    except OSError:
                        again = False
                    if not again:
                        kept[c] = f"{c} ({gone.strerror})"
            if isinstance(exc, Invalid) and exc.code == "host_failed":
                after = (f"That file could not be removed: {', '.join(kept.values())}, so the "
                         f"next dump is refused over it until it is moved aside" if kept else
                         "That file was removed, so the next dump is not refused over it")
                raise Invalid(exc.code, f"{exc}. {after}") from None
            raise

    def intvec(self) -> str:
        """The interrupt vector table as the debugger's `INTVEC` writes it, one character per
        byte. The file is this server's own, named `INTVEC_FILE` in the emulator's working
        directory: one already sitting there, a dangling link included (the debugger would
        write through it), is somebody else's and is REFUSED, never read or deleted, under
        either spelling as `memdump` checks; one there after the command is this call's,
        removed whatever happens."""
        names = [self.launch.cwd / INTVEC_FILE, self.launch.cwd / INTVEC_FILE.lower()]
        dcollect.refuse_leftover(names, "vector table")
        try:
            out = self.command(f"INTVEC {INTVEC_FILE}")
            written = next((p for p in names if p.exists()), None)
            if written is None:
                raise Invalid("unexpected_answer",
                    f"no {INTVEC_FILE} appeared in {self.launch.cwd} after `INTVEC`. What "
                    f"the debugger showed: {out.strip()[-300:]!r}")
            if INTVEC_OK not in out:
                raise Invalid("unexpected_answer",
                    f"the debugger did not report the table written, so {written} is not "
                    f"known to be whole. What it showed: {out.strip()[-300:]!r}")
            return written.read_bytes().decode("latin-1")
        finally:
            for p in names:
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()

    def _memdump_candidates(self) -> list[Path]:
        """Every place the dump could land, MEASURED rather than read off the help.

        The name this server passes, `MEMDUMP_FILE` in the WORKING DIRECTORY, comes first.
        The default name of a build that takes none is looked for in BOTH places and under
        both spellings: the debugger's help names `memdump.bin` without saying where, the
        file of the requested length is in the working directory and not the captures
        directory on the build that was measured, and that is one build on one platform. A
        filesystem that folds case also hides which of the two names is on disk, so neither
        is assumed.
        """
        names = (MEMDUMP_NAME, MEMDUMP_NAME.upper())
        places = [self.launch.cwd]
        if self.launch.captures_dir is not None:
            places.append(self.launch.captures_dir)
        seen: list[Path] = [self.launch.cwd / MEMDUMP_FILE]
        for place in places:
            for name in names:
                path = place / name
                if path not in seen:
                    seen.append(path)
        return seen

    # ------------------------------------------------------------------ symbols

    def selector(self, reg: str) -> dict[str, int]:
        """A segment register's descriptor BASE and LIMIT, as numbers, its type, and `big`,
        its D/B bit: 1 when a code segment decodes 32-bit.

        This is the load-time fact a symbol table cannot be placed without: a toolchain
        emits offsets inside a selector and the debugger's var list stores LINEAR
        addresses, so somebody has to supply `base`, and only the running machine knows
        it. MEASURED on a DJGPP program under CWSDPMI: `CS` and `DS` both come back
        `b:00400000 l:0023FFFF`, and that limit matching the highest address in the
        binary's own `nm` output is what identifies the base as this program's.

        IT IS ANCHORED ON THE ECHO OF THIS COMMAND and not on the first `b:` in the
        delta. The debugger overlays a descriptor line into the REGISTER pane as well
        (`ss: b:00008240 type:12 parbg`), so a search over the whole screen can return
        the stack selector's base for a question about the code selector -- a wrong
        answer of exactly the right shape, which is the sort this module exists to
        refuse.

        A register this debugger does not report is refused HERE rather than being sent
        and read back as a zeroed descriptor: `SELINFO` answers an unknown argument
        with an empty name and an all-zero base, which is indistinguishable from a real
        null-base selector.
        """
        name = reg.upper()
        if name not in SELINFO_REGS:
            raise Invalid("bad_argument",
                f"{reg!r} is not a segment register this debugger reports. It takes "
                f"one of {', '.join(SELINFO_REGS)}, and it answers anything else with "
                f"a ZEROED descriptor rather than an error, which reads as a real "
                f"selector based at 0")
        out = self.command(f"SELINFO {name}")
        marker = f"{SELINFO_ECHO} {name}:"
        at = out.rfind(marker)
        if at < 0:
            raise Invalid("unexpected_answer",
                f"the debugger did not echo `{marker}` (emulator "
                f"{'running' if self.alive() else 'GONE'}). A descriptor read is only "
                f"a reading when the machine is stopped at the debugger. What it "
                f"showed: {out.strip()[-300:]!r}")
        # ANCHORED ON THE ANSWER'S OWN LINE, which begins with the register's name.
        # A bounded SEARCH from the echo is not enough and that correction is measured:
        # with this descriptor's `l:` missing, the pattern simply slid forward and
        # matched the NEXT descriptor completely -- asked about CS, answered with DS's
        # base, type and limit, all three consistent with each other and none of them
        # about the register that was asked for. `match` cannot slide.
        line = out.find(f"{name}: b:", at)
        m = SELINFO_FIELDS.match(out, line + len(name) + 2) if line >= 0 else None
        if m is None:
            raise Invalid("unexpected_answer",
                f"`{marker}` came back with no complete base/type/limit on a "
                          f"`{name}:` line of its own. A descriptor read that has to "
                          f"take a field from somewhere else is not a reading. What it "
                          f"showed: {out[at:at + 300]!r}")
        base, kind, limit = (int(m.group(1), 16), int(m.group(2), 16),
                             int(m.group(3), 16))
        # AN ABSENT DESCRIPTOR IS REFUSED RATHER THAN REPORTED AS BASE 0. This is the
        # whole reason the type field is read: a selector with no present descriptor (one
        # nothing has set up, or real mode at the reset vector) answers with an all-zero
        # one, so a caller placing a symbol table
        # against it would put every name at its raw offset -- a confident wrong answer
        # of exactly the right shape, and silent.
        if kind == SELINFO_ABSENT:
            raise Invalid("bad_argument",
                f"{name} has no present descriptor (type:00, base 0, limit 0). Either "
                f"this machine is in REAL MODE, where there are none and a base of 0 "
                f"would place every symbol at its raw offset, or {name} holds a "
                f"selector nothing has set up. Reach the point where your program is "
                f"actually running, or pass the base explicitly")
        return {"base": base, "limit": limit, "type": kind, "big": int(m.group(8))}

    def load_symbols(self, data: bytes) -> list[tuple[str, int]]:
        """Put a var list into the debugger, and read back what it actually holds.

        `data` is the encoded list; the FILE is this module's business, because the
        debugger's filename argument survives only twelve characters and a caller's
        path cannot be passed through.

        IT VERIFIES BY READING THE LIST BACK, not by believing the `ok`. That is the
        same emulator that answers `ok` for a filename it silently truncated, and the
        round trip is the only thing that can say a record arrived with the name and
        the address it was given.

        THE COUNT COMES BACK AS A FLOOR AND NOT AN EQUALITY, because `LV` APPENDS:
        measured, loading three names on top of two left five. A caller loading twice
        gets both lists, and this returns everything the debugger holds rather than
        pretending the last load is all of it.

        The two files live in the emulator's WORKING DIRECTORY, which is somebody's
        project, so an existing file of either name is a REFUSAL rather than something
        to overwrite, and both are removed on the way out however this leaves.

        AND IT REFUSES A CONSOLE THAT IS NOT LISTENING, before the FILE is written:
        `LV` goes through the console, and one that is not listening swallows it
        without a word. See the guard below for why that is read here rather than
        inferred from the reply, and for what it does NOT claim.
        """
        for n in (SYM_LOAD_NAME, SYM_SAVE_NAME):
            if len(n) > SYM_ARG_MAX:
                raise Invalid("bad_argument",
                    f"{n!r} is {len(n)} characters and the debugger keeps "
                              f"{SYM_ARG_MAX}; it would write a different file and "
                              f"report ok")
        into = self.launch.cwd / SYM_LOAD_NAME
        back = self.launch.cwd / SYM_SAVE_NAME
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
        # that never came. MEASURED: that refusal named a truncated filename, an older
        # `ok` and a gone emulator, and the same reply's own data excluded all three
        # (`SYMS.BIN` is 8 characters, it was the session's first load, `alive` was
        # true). The caller was sent to look at filenames.
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
            self._survey()
        except NotStopped as exc:
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
            if not self.alive():
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
                              f"{SYM_ARG_MAX} characters") from None
            out = self.command(f"LV {SYM_LOAD_NAME}")
            self._acked(out, SYM_LOAD_ECHO, SYM_LOAD_NAME)
            out = self.command(f"SV {SYM_SAVE_NAME}")
            self._acked(out, SYM_SAVE_ECHO, SYM_SAVE_NAME)
            if not back.exists():
                raise Invalid("unexpected_answer",
                    f"the debugger reported saving {SYM_SAVE_NAME} and no such file "
                    f"is in {self.launch.cwd}. Those disagree, so nothing here is a "
                    f"reading of what it loaded")
            try:
                return symbols.decode(back.read_bytes())
            except (symbols.BadSymbolText, OSError) as exc:
                # `BadSymbolText` is NOT an `Invalid`, and its own docstring says it is
                # a distinct type "so the MCP layer can translate it" -- which the
                # server does for `parse`/`plan`/`encode` and not for this call. So the
                # one place a MALFORMED file can arrive from the emulator was the one
                # place it escaped as a traceback.
                raise Invalid("host_failed", f"the debugger saved {SYM_SAVE_NAME} and it cannot be "
                              f"read back: {exc}. That is not a reading of what it "
                              f"loaded") from None
        finally:
            for p in (into, back):
                # SUPPRESSED, and only here: an `OSError` out of the cleanup would
                # REPLACE whatever the body raised, so a reasoned refusal about the
                # debugger would be handed over as a `PermissionError` about a file.
                with contextlib.suppress(OSError):
                    p.unlink(missing_ok=True)

    @staticmethod
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

        It takes no `self`: nothing here touches the session, and the three `type:
        ignore[arg-type]` its tests needed were the smell that said so.
        """
        head = f"{echo} ({name}"
        at = out.rfind(head)
        if at >= 0 and out[at:].startswith(head + SYM_OK):
            return
        raise Invalid("unexpected_answer",
            f"the debugger did not acknowledge `{echo}` for {name!r} on this call. It "
            f"truncates a filename to {SYM_ARG_MAX} characters and reports ok for "
            f"whatever it used, so an acknowledgement naming anything else is not this "
            f"one -- and an OLDER ok for this same name is not this one either. THE "
            f"SHOWING BELOW IS WHAT DISCRIMINATES, and it is read rather than guessed "
            f"at: EMPTY is the debugger saying nothing at all, which is what a gone "
            f"emulator looks like from here, and the GUEST'S OWN INSTRUMENTATION "
            f"scrolling past is a machine that is RUNNING, whose console takes no "
            f"commands and swallowed this one without a word. Those three are what has "
            f"been seen, not a closed list. What it showed: {out.strip()[-300:]!r}")

    # ------------------------------------------------------------------ capture

    def captures(self) -> list[dict[str, object]]:
        """The capture files this session has produced, with what is IN them.

        It reports the frame count and the index, not just the size, because a
        capture that recorded nothing and one that recorded the whole session are
        both files and both plausible sizes. The size alone has never been the
        evidence.

        TWO FILES IS THE NORMAL CASE, not a fault: DX-CAPTURE restarts its recording
        when the guest changes video mode, so a program that boots in DOS text and
        then goes graphical leaves a small first file and the real one after it. They
        are returned largest last.
        """
        if self.launch.captures_dir is None:
            raise Invalid("no_channel", "this session was started without a captures directory, so "
                          "there is nowhere for a capture to have been written")
        if not self.launch.capture_video:
            raise Invalid("no_channel", "this session was not started with capture_video, so "
                          "nothing was recording. That is not an empty capture, it "
                          "is no capture")
        out: list[dict[str, object]] = []
        # THE FACTS OF A FILE THAT HAS NOT CHANGED ARE THE FACTS READ LAST TIME: this is
        # the tool a caller polls while a recording runs, and reading every capture whole
        # at each poll to count its frames is the cost. One entry per file, keyed by its
        # size AND its modification time, so a file replaced by another of the same size
        # is read again; the entries of files no longer listed leave with this rebuild.
        fresh: dict[tuple[str, int, int], dict[str, object]] = {}
        for f in sorted(self.launch.captures_dir.glob("*.avi"),
                        key=lambda p: p.stat().st_size):
            stat = f.stat()
            key = (str(f), stat.st_size, stat.st_mtime_ns)
            facts = self._avi_facts.get(key)
            if facts is None:
                facts = avi_facts(f.read_bytes())
            fresh[key] = facts
            out.append({"path": str(f), **facts})
        self._avi_facts = fresh
        if not out:
            raise Invalid("unexpected_answer",
                f"no capture appeared in {self.launch.captures_dir}. Two causes, and "
                f"they need different answers: the recording stops when the captured "
                f"PROGRAM exits, so a session still running may not have written one "
                f"yet; OR the program never started, because `program` is passed with "
                f"`-c`, which runs AFTER the conf's [autoexec] section -- a conf whose "
                f"autoexec ends in `exit` quits before it is reached")
        return out

    def frame(self, at: int, dest: Path, source: Path | None = None) -> Path:
        """ONE still image out of the capture, at frame `at`.

        WHY IT COMES FROM THE VIDEO AND NOT FROM THE EMULATOR. DOSBox-X's own
        screenshot is a MAPPER action and needs a keypress, so there is no
        non-interactive trigger for it; the video does have one. The still is
        therefore an extraction, and it requires the capture to have been recording.

        `ffmpeg` is an OPTIONAL dependency and its absence is said out loud rather
        than worked around: a tool that quietly produces nothing is worse than one
        that names what is missing.

        IT ALWAYS WRITES A PNG, whatever `dest` is called, and the caller is told so
        here because nothing in the reply says it. The encoder is forced rather than
        inferred from the extension: see the argv below for what inferring it was
        measured doing.
        """
        if shutil.which("ffmpeg") is None:
            raise Invalid("host_failed", "a still is extracted from the capture with `ffmpeg`, and "
                          "there is none on PATH. The video itself does not need it; "
                          "only this does")
        check_frame_args(at, dest)
        paths.fresh_dest("dest", dest)
        src = source or Path(str(self.captures()[-1]["path"]))
        # A `%` ANYWHERE IN THE DESTINATION IS REFUSED. `-f image2` treats the WHOLE
        # PATH as a printf template, so `shot%03d.png` makes ffmpeg write `shot001.png`
        # and leave `dest` untouched -- after which this method refuses, blaming "a
        # frame past the end" for an extraction that worked perfectly.
        #
        # IT IS `str(dest)` AND NOT `dest.name`: what ffmpeg opens is the EXPANDED
        # path, so a `%` in a parent misplaces the still exactly as one in the name
        # does, and the name alone covers the half a caller is least likely to write.
        #
        # THE OUTCOME DEPENDS ON WHETHER THE EXPANSION ALREADY EXISTS, and both halves
        # were observed: with a literal `run%d/` directory there and `run1/` absent,
        # ffmpeg fails with nothing written anywhere, and with
        # it present it writes a perfectly good PNG there, at a path the caller never
        # named and with no error. The second is the one worth refusing for, and it
        # cannot be told from the first in advance.
        #
        # It is deliberately broader than the hazard: ffmpeg leaves a `%` with no valid
        # conversion alone (`fifty%.png` is written as itself), so those are refused
        # unnecessarily. That direction fails loudly and the other fails silently.
        #
        # `dest` is judged absent by `paths.fresh_dest` above, so whatever sits there
        # after ffmpeg is this extraction and not a stale image: nothing is deleted to
        # make that true.
        try:
            got = subprocess.run(
                # THE FORMAT IS FORCED, and this is not tidiness: without it ffmpeg
                # picks the encoder from `dest`'s EXTENSION, which is the caller's.
                # MEASURED on ffmpeg 9.0.1 with this exact argv: asking for a frame
                # PAST THE END of a real capture writes nothing for a `.png`
                # destination but a 1307-byte FRAMELESS CONTAINER for an `.mp4` one,
                # at exit code ZERO -- so every term of the guard below was false and
                # `frame()` handed that container back as a still. With the format
                # forced, the same request writes NO FILE and the guard fires.
                #
                # It also means this tool's promise ("ONE still image") no longer
                # depends on the caller spelling the extension the way it meant.
                ["ffmpeg", "-v", "error", "-y", "-i", str(src),
                 "-vf", f"select='eq(n\\,{at})'", "-fps_mode", "passthrough",
                 "-frames:v", "1", "-f", "image2", "-c:v", "png", str(dest)],
                capture_output=True, text=True, check=False, timeout=FFMPEG_SECS)
        except subprocess.TimeoutExpired:
            # AS `Invalid`, NOT AS A TRACEBACK. `tool()` translates only `Invalid`, so
            # this escaped raw while `build_check` catches the same exception twelve
            # lines of comment deep for the same reason. Two of this module's contracts
            # break at once when it escapes: the reply stops saying WHICH nothing it
            # found, and it stops carrying the session's state at all.
            raise Invalid("host_failed", f"`ffmpeg` did not return within {FFMPEG_SECS}s pulling "
                          f"frame {at} from {src}. That is the tool hanging, not an "
                          f"answer about the capture") from None
        # THE EXIT CODE IS READ, and it was not. MEASURED on ffmpeg 7.x: a frame past
        # the end of a capture writes NO file for a `.png` destination but a 261-byte
        # frameless container for an `.mp4` one, so "a file exists and is non-empty" is
        # not the same question as "ffmpeg succeeded". Only the size was asked.
        if got.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
            # THE TWO ARMS SAY DIFFERENT THINGS, because they ARE different things and
            # merging them picks a cause. A non-zero exit code is ffmpeg reporting its
            # own failure and the reason is in hand; an empty or absent output with a
            # ZERO code is the frame-past-the-end shape, where the cause is a guess.
            # This module's rule, stated in `wait_ready`: INVALID names what was seen.
            said = (got.stdout + got.stderr).strip()[-300:]
            if got.returncode != 0:
                raise Invalid("host_failed",
                    f"ffmpeg exited {got.returncode} extracting frame {at} "
                              f"from {src} and said: {said!r}. Any file it left behind "
                              f"is not a frame")
            raise Invalid("host_failed",
                f"ffmpeg exited 0 but no image came out of {src} at frame {at}. It "
                f"said: {said!r}. The commonest cause is a frame past the end: "
                f"`captures` reports how many there are. An unindexed capture is NOT "
                f"the cause -- MEASURED, a frame comes out of one of those fine")
        # AND THE BYTES ARE AN IMAGE. Forcing the format above should make this
        # unreachable, which is exactly why it is cheap to assert: the failure it
        # guards against was a well-formed file of the wrong KIND, and "a file exists
        # and is not empty" could not tell the difference.
        if dest.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise Invalid("host_failed",
                f"what ffmpeg left at {dest} is not a PNG, so it is not the "
                          f"still that was asked for")
        return dest

    # ------------------------------------------------------------------ input to the guest

    def break_in(self, seconds: float = BREAK_IN_WAIT_S) -> float:
        """Bring a RUNNING guest back to the debugger through its control channel's `BREAK`
        (`dosbox_control`), headless or windowed alike, and wait for its prompt: the seconds
        it took. No window, no menu and no focus: the request is the debugger hotkey sent
        over a socket, polled by the emulator's own timer while the guest runs."""
        ok, lines = self.control.request("BREAK")
        if not ok:
            raise Invalid("unexpected_answer",
                f"the debugger channel refused BREAK: {' / '.join(lines) or 'no reason given'}")
        began = time.monotonic()
        while time.monotonic() - began < seconds:
            cancel.check()
            if self.at_debugger():
                return round(time.monotonic() - began, 2)
            time.sleep(0.05)
        raise Invalid("unexpected_answer",
            f"the debugger channel accepted BREAK and the debugger's prompt did not "
                      f"appear within {seconds} s: the guest may still be running")

    def _state_dir(self) -> Path:
        if self.launch.state_dir is None:
            return self.launch.cwd / "save"
        return self.launch.state_dir

    def _state_command(self, verb: str, path: Path, seconds: float) -> dict[str, object]:
        """`SAVESTATE` or `LOADSTATE` of `path` over the debugger channel, with the debugger
        stopped as the commands need it: a RUNNING guest is broken in on first and released
        again after, so the machine is left the way it was found. The reply's part:
        `paused` (it had to be stopped), `running` (it runs after the call: false for a
        parked one, and for a released one that halted again at once) and `waited_s` (the
        command alone, not the break-in or the release)."""
        if "\n" in str(path) or "\r" in str(path):
            raise Invalid("bad_argument", f"a state path is one line; got {str(path)!r}")
        paused = not self.at_debugger()
        began = time.monotonic()
        try:
            if paused:
                self.break_in()
                began = time.monotonic()
            ok, lines = self.control.request(f"EXEC {verb} {path}", seconds, poll=cancel.check)
        except BaseException as e:
            # A COMMAND THAT ENDS EARLY, refused or cancelled (its waits poll, the break-in's
            # included), releases the guest it stopped, as its bound would. Best effort: the
            # command's own refusal is the answer, and one from the release would hide it.
            if paused and (isinstance(e, Invalid) or cancel.is_cancellation(e)):
                with cancel.shielded(), contextlib.suppress(Invalid):
                    if cancel.is_cancellation(e) and not self.at_debugger():
                        self.break_in()        # a BREAK sent lands; wait for it, then release
                    if self.at_debugger():
                        self.resume()
            if isinstance(e, Invalid) and e.code == "no_channel":
                why = str(e).rstrip(".")
                raise Invalid("no_channel",
                              f"{verb} goes down the debugger channel, and {why}. The saved "
                              f"states need that channel and a build carrying {verb}: the "
                              f"Optimiza/dosbox-x fork has both (REFERENCE.md, Saved states)"
                              ) from None
            raise
        waited = round(time.monotonic() - began, 2)
        running = not self.resume()["halted"] if paused else False
        if ok:
            return {"paused": paused, "running": running, "waited_s": waited}
        said = " / ".join(line.strip() for line in lines if line.strip())
        if not any(line.startswith(f"DEBUG: {verb}") for line in lines):
            raise Invalid("no_channel",
                f"this DOSBox-X has no `{verb}` debugger command ({said or 'no answer'}): "
                          f"saved states need a build that carries it, the Optimiza/dosbox-x "
                          f"fork (REFERENCE.md, Saved states)")
        raise Invalid("unexpected_answer",
            f"the emulator refused {verb} of {path}: {said}. Its log says why (a state of "
                      f"another DOSBox-X version, program, memory size or machine type is "
                      f"refused rather than asked about)")

    def state_save(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        """Save the machine under `name` as `<state_dir>/<name>.sav`, by the debugger's own
        `SAVESTATE` (`_state_command`), and read the file back for what it says about
        itself. Running or parked, headless or windowed. Never overwrites, and a save that
        failed leaves no file behind: the emulator removes the old one and writes the new one
        in place, so a failure part-way would otherwise hold the name with a broken state.
        Saving alters nothing."""
        dlaunch.check_state_name(name)
        check_wait_bound(seconds)
        state_dir = self._state_dir()
        dest = state_dir / f"{name}.sav"
        if paths.taken(dest):         # a dangling link too: the save would write through it
            raise Invalid("bad_argument",
                f"a state named {name!r} already exists at {dest}: pick another name, "
                          "this never overwrites")
        state_dir.mkdir(parents=True, exist_ok=True)
        try:
            outcome = self._state_command("SAVESTATE", dest, seconds)
        except BaseException:                  # a refusal, a cancel or a defect alike
            dest.unlink(missing_ok=True)       # it was not there before this call
            raise
        if not dest.is_file():
            raise Invalid("unexpected_answer",
                f"the emulator answered SAVESTATE and {dest} is not there")
        meta = dlaunch.state_meta(dest)
        return {"name": name, "path": str(dest), "bytes": meta["bytes"],
                **{k: meta.get(k, "") for k in dlaunch.STATE_META}, **outcome}

    def state_load(self, name: str, seconds: float = STATE_WAIT_S) -> dict[str, object]:
        """Load the state `name` from `<state_dir>/<name>.sav` by the debugger's own
        `LOADSTATE`. Running or parked: a running guest is stopped for it and released again,
        a parked one stays parked, at the loaded machine's position, which counts as a stop
        of its own: the record of the stop before describes a machine that is gone. It
        REPLACES the machine, so the session is altered from here on, and after any refusal
        but a missing channel too, since a load refused part-way may have replaced some of
        it."""
        dlaunch.check_state_name(name)
        check_wait_bound(seconds)
        state_dir = self._state_dir()
        source = state_dir / f"{name}.sav"
        if not source.is_file():
            raise Invalid("unknown_ref",
                f"no state named {name!r} under {state_dir}: `state_list` says what is there")
        meta = dlaunch.state_meta(source)
        parked = self.at_debugger()
        try:
            outcome = self._state_command("LOADSTATE", source, seconds)
        except BaseException as e:
            # CUT SHORT AFTER IT WAS SENT, refused or cancelled: some of it may be loaded, so the
            # session is altered and, parked, the stop record before it may describe a machine
            # that is gone, as a load that answered does.
            if not (isinstance(e, Invalid) and e.code in ("no_channel", "bad_argument")):
                self.altered = True
                if parked:
                    self.stop_count += 1
            raise
        self.altered = True
        if not outcome["paused"]:
            self.stop_count += 1
        return {"name": name, "path": str(source),
                **{k: meta.get(k, "") for k in dlaunch.STATE_META}, **outcome}

    def snapshot(self, dest: Path | None = None, seconds: float = SNAPSHOT_WAIT_S,
                 progress: Progress = no_progress) -> dict[str, object]:
        """One still of the RUNNING screen, taken INSIDE the guest: the input stub's `S`
        command writes the integration device's capture trigger, and the emulator writes the
        `.png` under the captures directory (`captures_dir` given to `start`, or `capture/`
        under its working directory), with no window and no menu. Confirmed by the NEW file,
        and moved to `dest` when one is given (absolute, not there yet). REFUSED with the
        machine parked: the stub takes its commands on the timer tick, which a machine
        stopped at the debugger never reaches. The caller has checked the stub is resident."""
        check_wait_bound(seconds)
        folder = (self.launch.captures_dir if self.launch.captures_dir is not None
                  else self.launch.cwd / "capture")
        target = None if dest is None else paths.fresh_dest("dest", dest)
        if self.at_debugger():
            raise Invalid("not_running",
                "a screenshot is taken of a RUNNING machine only: the stub takes its commands "
                          "on the timer tick, which a machine parked at the debugger never "
                          "reaches. `resume`, then snapshot")
        before = set(folder.glob("*.png")) if folder.is_dir() else set()
        self.send_commands([SCREENSHOT_COMMAND])
        began = time.monotonic()
        while True:
            cancel.check()
            new = sorted((set(folder.glob("*.png")) if folder.is_dir() else set()) - before)
            if new:
                path = new[-1]
                size = path.stat().st_size
                time.sleep(0.2)
                if size and path.stat().st_size == size:     # the writer is done with it
                    break
            if time.monotonic() - began >= seconds:
                raise Invalid("wait_expired",
                    f"no new PNG appeared under {folder} within {seconds:g} s of the command")
            time.sleep(0.1)
        if target is not None:
            path = dcollect.collect(path, target, "screenshot")
        return {"route": "guest", "path": str(path), "bytes": path.stat().st_size,
                "waited_s": round(time.monotonic() - began, 2)}

    def state_list(self) -> dict[str, object]:
        """Every `.sav` under the state directory with what it says about itself. A reading
        of a directory: no window, no console, works while the machine runs."""
        state_dir = self._state_dir()
        files = sorted(state_dir.glob("*.sav")) if state_dir.is_dir() else []
        # THE WORKING SLOT IS NOT A NAMED STATE: the emulator's own numbered file sits
        # beside the copies, and listed among them it counts one state too many.
        named = [dlaunch.state_meta(p) for p in files if not p.stem.isdigit()]
        slots = [dlaunch.state_meta(p) for p in files if p.stem.isdigit()]
        return {"state_dir": str(state_dir), "states": named,
                "working_slot": slots[-1] if slots else None}

    def send_commands(self, commands: list[bytes]) -> int:
        """The input route's post: each framed command goes down the socket the session
        connected at start, and the guest's resident stub carries out one per timer tick.
        Returns how many bytes went. A socket the emulator closed (its bound expired) is
        reported as the route being gone, not as a delivery."""
        if self._input is None:
            raise Invalid("no_channel", "this session has no input route: its socket was "
                          "never connected")
        if not commands:
            raise Invalid("bad_argument", "nothing to send")
        # ONE COMMAND PER TICK, PACED FROM HERE AS WELL AS QUEUED THERE. The stub carries out
        # one command per timer tick because the emulated 8042 holds one byte; a whole
        # sequence written in one burst once overran the guest's UART (the emulator logged
        # `Overrun RX:1` and the key never came). The stub's FIFO queues a burst, and the gap
        # below keeps the arrivals under the tick rate regardless, so neither half has to be
        # right alone. A command's own bytes go together: five fit the FIFO whole.
        try:
            for i, command in enumerate(commands):
                if i:
                    time.sleep(COMMAND_GAP_S)
                self._input.sendall(command)
        except OSError as e:
            raise Invalid("session_broken",
                f"the input socket is gone ({e}): the emulator closed its end, so "
                          f"nothing more was delivered") from None
        return sum(len(c) for c in commands)

    # ------------------------------------------------------------------ closing

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self, grace: float = 8.0, progress: Progress = no_progress) -> int | None:
        """End the session and leave nothing behind (`_close`), EVEN WHEN THE CALL IS CANCELLED
        HALF-WAY: the cancel lands in the wait for the exit, and an emulator signalled but never
        waited on is the one thing a cancel must not leave, so the close runs again, shielded and
        silent, and the cancellation goes on unwinding once it has."""
        try:
            return self._close(grace, progress)
        except BaseException as e:
            if not cancel.is_cancellation(e):
                raise
            with cancel.shielded():
                self._close(grace)
            raise

    def _close(self, grace: float = 8.0, progress: Progress = no_progress) -> int | None:
        """End the session and leave nothing behind; a second call finishes what an interrupted
        one began, and never closes the terminal twice.

        A live session outlives the turn, which is the one hazard a batch launcher
        does not have. The bound is the backstop and this is the deliberate act; both
        exist because either alone leaves a case uncovered -- and note the backstop is
        the one that survives this process being killed, since a `finally` does not
        run on SIGKILL.

        `grace` IS THE WAIT AFTER SIGKILL, FLOORED AT ONE SECOND, and SIGTERM gets
        `TERM_GRACE` of its own: with the quit warning off on every argv the ordinary session
        answers the TERM at once, so that budget is a bound on a signal that is expected to
        land, and what still ignores it is deaf rather than slow (see that constant). One
        budget for both would spend the post-KILL reap budget on every close of a used
        session. The floor exists because `grace=0` is a
        reasonable reading of "do not wait" and SIGKILL still needs reaping.

        THE DESCRIPTOR IS CLOSED UNDER `finally`. Without it, a second `wait` that
        times out takes the exception out of here with the master still open and the
        caller's session state still pointing at a half-closed object.

        The process GROUP is signalled, not just the child: `start_new_session` put
        it in its own, so anything it spawned would otherwise be missed.
        """
        try:
            if self.proc.poll() is not None:
                # A process that left on this close's own SIGTERM quit; one found gone, died.
                self.ended_how = "quit" if getattr(self, "_termed", False) else "died"
            else:
                self._signal_group(signal.SIGTERM)
                self._termed = True
                if wait_exit(self.proc, TERM_GRACE, progress,
                             "close: waiting for the emulator to leave on SIGTERM") is not None:
                    self.ended_how = "quit"
                else:
                    self.ended_how = "killed"
                    self._signal_group(signal.SIGKILL)
                    # THE SIGKILL WAIT IS FLOORED, and a caller cannot ask for none.
                    # `close(grace=0)` is a reasonable reading of "do not wait" and it
                    # produced the state this class forbids: the child SIGKILLed, the
                    # TimeoutExpired suppressed, `None` returned as the exit code, and
                    # the server then dropping its reference -- an un-reaped process
                    # nothing can reach. SIGKILL cannot be ignored, so the only
                    # question is how long reaping takes, and a second is far past it.
                    # AND AN EXPIRY HERE IS RECORDED, not merely survived. Suppressing
                    # it and returning `self.proc.returncode` hands back None for a
                    # child that was SIGKILLed and not yet reaped, and the server then
                    # drops its reference: an un-reaped process nothing can reach, with
                    # `exit_code: null` as the only trace. The drain-thread join eleven
                    # lines below already does the right thing with its own expiry;
                    # this is the same treatment for this one.
                    if wait_exit(self.proc, max(grace, 1.0), progress,
                                 "close: waiting for the SIGKILLed emulator to be reaped") is None:
                        # THE MESSAGE STATES THE FACT AND NOTHING ABOUT A REPLY.
                        # Both earlier wordings named an `exit_code` "below" or "in
                        # this reply", and both dangled: the field is consumed by two
                        # different tools and only one of them has an exit code.
                        self.reap_failed = (
                            f"SIGKILL was sent and the process had not been reaped "
                            f"{max(grace, 1.0)}s later")
        finally:
            # THE INPUT SOCKET GOES FIRST, and quietly: the emulator's end is dying or dead
            # by now, and a socket left open is a descriptor leaked per session.
            sock = getattr(self, "_input", None)
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
                self._input = None
            channel = getattr(self, "control", None)
            if channel is not None:
                channel.close()
            # THE THREAD IS STOPPED BEFORE THE DESCRIPTOR IS CLOSED, and the order is
            # the whole point: closing first leaves it selecting on a number the
            # kernel is free to hand to the next file this process opens.
            #
            # AND THE JOIN IS CHECKED, because a `join(timeout=...)` that EXPIRES
            # produces exactly the state this ordering exists to prevent, silently:
            # `join` returns None either way. If the thread outlives the wait, the
            # descriptor is DELIBERATELY LEAKED rather than closed. One leaked fd in a
            # process that is ending a session is cheap; a recycled fd being read by a
            # stale drainer -- into the next session's buffer -- is not, and in a
            # long-lived MCP server the next fd is the next session's own terminal.
            self._stop.set()
            if self._drainer is not None:
                self._drainer.join(timeout=DRAIN_JOIN_SECS)
            if self._drainer is not None and self._drainer.is_alive():
                self.drain_ended = (f"the drain thread did not stop within "
                                    f"{DRAIN_JOIN_SECS} s; the terminal descriptor was "
                                    f"left open on purpose rather than recycled under "
                                    f"a live reader")
            elif not getattr(self, "_master_closed", False):
                self._master_closed = True
                with contextlib.suppress(OSError):
                    os.close(self._master)
        # None, not -1: `subprocess` encodes a signal death as a NEGATIVE number, so
        # -1 is the genuine code for "killed by SIGHUP" and cannot double as "unknown".
        return self.proc.returncode

    def _signal_group(self, sig: int) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(os.getpgid(self.proc.pid), sig)

    def state(self) -> dict[str, object]:
        """What every reply carries, `altered` included."""
        changed: bool | None = None
        with contextlib.suppress(OSError):
            changed = (self.launch.conf.is_file()
                       and dlaunch.digest(self.launch.conf) != self.conf_digest)
        return {
            "pid": self.proc.pid,
            "alive": self.alive(),
            "altered": self.altered,
            "conf": str(self.launch.conf),
            "conf_digest": self.conf_digest,
            "conf_changed_on_disk": changed,
            "watched": self.launch.watched,
            "seconds_bound": self.launch.seconds,
            "seconds_elapsed": round(time.monotonic() - self.started_at, 1),
            # NOT `guest_bytes_dropped`, which is what this was called for a few hours
            # and was a name that LIED in both directions. What overflows is the
            # EMULATOR'S TERMINAL -- ncurses repaints, SDL banners, and the log when no
            # `logfile` is set. The GUEST's own instrumentation is the 0xE9 stream,
            # which `e9()` reads off `launch.logfile` on disk and which this counter
            # cannot touch: a zero here never meant the guest's output was intact, and
            # a nonzero never meant any of it was lost.
            "terminal_bytes_dropped": self.dropped,
            # WHETHER THE READER IS STILL ALIVE, which no other field answers. A
            # drainer killed by a transient error makes every later read return ""
            # forever while `alive` still says true, so the session becomes a broken
            # instrument reporting itself as a quiet machine.
            "drain_alive": self._drainer is not None and self._drainer.is_alive(),
            "drain_ended": self.drain_ended,
            # WHETHER THIS SESSION RECORDS, said up front: without it the only way to learn
            # was to call `captures` and read the refusal.
            "captures": (str(self.launch.captures_dir) if self.launch.captures_dir is not None
                         else "on, in the emulator's own directory")
                        if self.launch.capture_video else "off",
            # WHERE `state_save` writes and `state_list` reads, said on every reply so a
            # project knows which directory holds its states without asking twice.
            "state_dir": str(self.launch.state_dir) if self.launch.state_dir is not None
                         else "the emulator's own save/ under its working directory",
        }
