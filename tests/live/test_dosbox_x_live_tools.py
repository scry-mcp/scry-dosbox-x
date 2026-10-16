"""One live case per TOOL, driven through the server exactly as an MCP caller drives it.

WHY THIS FILE EXISTS BESIDE `test_dosbox_x_live.py`, WHICH ALREADY DRIVES A REAL
EMULATOR. That file exercises `Session`, the class. This one exercises EVERY tool the
server actually publishes -- the population comes from the MCP registry and is gated by
`test_every_tool_has_a_live_case_naming_it`, so the invariant is quoted here rather than
a count, which expires on its own the next time a tool is added. Until this file
existed NOT ONE live case went through them: the reply envelope, the `Invalid` to
`INVALID` translation, `_live()`'s handling of a session that has gone, and the
`_SESSION` global's whole life cycle had been seen only against a fake.

THE EVIDENCE THAT THE GAP WAS REAL, and it is not a hypothetical. `memdump` shipped
having NEVER ONCE WORKED: it collected the debugger's file from the captures
directory, the file lands in the emulator's working directory, and every dump ever
taken returned INVALID. Fifty-six contract tests were green over it, because a fake
session puts the file wherever the fake says. The rule that follows is the one this
file is built on: **a tool with no live case is a tool whose green means nothing**,
and choosing which tools "need" one by eye is exactly how that one got through. So it is
ALL of them, including the ones that look too simple to break.

WHAT EACH CASE ASSERTS IS THE TOOL'S OWN GUARANTEE, never merely that it returned.
`status: ok` was what `read_memory` reported while handing back a screen its own cap
had cut the requested address out of.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, cast

import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

# THE PATCHED CONF IS THE SIBLING FILE'S, and it is imported rather than copied. It
# strips a run-and-exit out of the caller's own config and REQUIRES the substitution
# to match, which is the property a second hand-written copy would silently lose the
# day the config's shape changes: a patch that quietly changed nothing leaves a case
# measuring the original under the patched one's name.
# THE PACKAGE'S OWN GUEST IS THE DEFAULT, and pointing the tier at a project is the
# override rather than the requirement.
#
# It used to be the other way round, and the cost was measured: with the tier aimed at a
# config whose guest was not one particular private application, NINE cases FAILED --
# not skipped -- while the README said it "SKIPS unless you point it at a config". The
# dependency was never the project's name; it is that the guest RUNS after a `resume`
# and EMITS instrumentation, which `resume`, `e9`, `e9_wait`, `step`-on-a-running-
# machine and the bound cases all rest on. `tests/guest/` holds 144 bytes that do
# exactly that and nothing else.
# IMPORTED, NOT REDEFINED. This block used to be a copy of the one in
# `test_dosbox_x_live.py`, and the copy THERE was read by nothing while this one did
# the work -- so there were two definitions of every override and one of them was
# dead. `conf_that_does_not_exit` already crosses this boundary (below), so the
# one-owner shape costs nothing.
from test_dosbox_x_live import (  # noqa: E402
    _HALF_A_PAIR,
    _OWN,
    CONF,
    CWD,
    GUEST_LATE,
    GUEST_MARK,
    GUEST_PROGRAM,
    conf_that_does_not_exit,
)

import dosbox_code as code
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

# WHERE A WATCHED WINDOW GOES IS NOT THIS PACKAGE'S TO DECIDE, and it is not this
# test's either. The server refuses a watched session with no placement flags rather
# than inventing a geometry, because that decision belongs to one helper for a whole
# fleet; a test that hardcoded a position would be putting that private layout back
# in, one layer down, in a package meant to be published.
#
# So the flags arrive the same way the conf does: from outside. NEWLINE-separated,
# because a placement flag is a `-set` PAIR and its second half contains a space
# (`sdl display=1`), so splitting on whitespace shreds it into an argument DOSBox-X
# does not recognise, and on this emulator an unrecognised argument does not fail, it
# hangs.
FLAGS_RAW = os.environ.get("DOSBOX_X_LIVE_WINDOW_FLAGS", "")
WINDOW_FLAGS = [ln for ln in FLAGS_RAW.splitlines() if ln.strip()]

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        bool(_HALF_A_PAIR), reason=_HALF_A_PAIR or "the pair is consistent"),
    pytest.mark.skipif(
        not Path(CONF).is_file(), reason=f"the live config {CONF} is not a file"),
    pytest.mark.skipif(
        str(_OWN / "probe.conf") == CONF and not (_OWN / "probe.com").is_file(),
        reason=f"the package's own guest {_OWN / 'probe.com'} is missing"),
]

# How long a case waits for the guest to reach a milestone of its own. It is a
# CEILING and not a sleep: every wait below polls and leaves the moment the property
# it is waiting on holds, so a fast machine pays nothing for it.
GUEST_WAIT = 45.0

# The two caps the server passes to `_delta`, named here because a case asserting
# `clipped` against them has to know which one its tool uses. They are the SERVER's
# numbers; a case comparing a reply's fields only with each other cannot fail, which
# is what the first version of the `debug` case did.
DEBUG_CAP = 4000
SMALL_CAP = 2000


def start_ok(**kw: Any) -> dict[str, Any]:
    """`start` with this fixture's conf, REFUSING to continue if it did not come up.

    The status is asserted here rather than in each case because an INVALID `start`
    makes every later assertion in that case a statement about nothing, and the
    reason string is the only thing that says why.
    """
    reply = cast(dict[str, Any], server.start(conf=CONF or "", cwd=CWD, **kw))
    assert reply["status"] == "ok", reply
    return reply


def wait_for(predicate: Any, seconds: float = GUEST_WAIT) -> bool:
    """Poll until it holds or the ceiling is reached. Never touches the session."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return False


def a_running_guest_that_has_logged(tmp_path: Path, seconds: int = 120,
                                    lines: int = 6) -> None:
    """Start with a log, release the guest until close (headless, nothing armed: the log
    is the way back), and wait until it has written `lines` instrumentation lines. Every
    E9 case opens this way, and a window in which the guest wrote nothing is INVALID, not
    a channel to measure against."""
    log = tmp_path / "guest.log"
    start_ok(seconds=seconds, logfile=str(log))
    server.resume()
    assert wait_for(lambda: log.exists() and ds.count_e9(
        log.read_text(encoding="utf-8", errors="replace")) >= lines), \
        "the guest emitted no instrumentation: this window measured nothing, INVALID"


# --------------------------------------------------------------- no session needed

def test_build_check_answers_about_this_build_and_names_the_whole_surface() -> None:
    """The one tool whose job is examining preconditions, asked of the real binary.

    IT ASSERTS THE SURFACE, not just that a binary was found. `registered_tools()`
    reads the MCP layer's own registry, so a case that only checked `debugger: true`
    would stay green over a server exposing nothing at all: `mcp.tool()` returns the
    function unchanged, which is what makes that break invisible to every ordinary
    test. Here the assertion runs against the process that would really serve them.
    """
    reply = cast(dict[str, Any], server.build_check())
    assert reply["status"] == "ok", reply
    assert reply["debugger"] is True
    assert Path(str(reply["binary"])).is_file()
    # THE LIST IS SPELLED OUT rather than compared with `server.registered_tools()`,
    # which is what `build_check` reads: that comparison would be the registry agreeing
    # with itself. Its twin lives in the contract file's
    # `test_every_tool_this_server_promises_is_actually_registered`, and NOTHING ties
    # the two literals together -- adding a tool means editing both, and forgetting one
    # is a red rather than a silent gap, which is the acceptable direction.
    assert set(reply["tools"]) == {
        "start", "status", "close", "log", "log_wait", "debug", "registers", "set_register",
        "write", "read_memory", "disassemble", "call_stack", "memdump", "find", "scan_start",
        "scan_filter", "scan_clear", "machine_map", "interrupt_vectors", "palette",
        "screen_view", "screen_signature", "screen_wait", "breakpoint_interrupt", "stop",
        "resume", "step", "run_to", "run_for", "trace", "breakpoint_at", "breakpoint_list",
        "breakpoint_clear", "watch_add", "watch_list", "watch_clear", "state_save",
        "state_load", "state_list", "snapshot", "captures", "capture_frame", "build_check",
        "symbols_load", "symbols_find", "send_keys", "send_mouse", "perform", "drive",
        "comment_add", "comment_list", "comment_delete", "comment_save", "comment_load"}
    # NO SESSION, so the envelope must say so rather than omitting the key: a caller
    # distinguishing "no session" from "the field is missing" cannot do it if the two
    # print the same thing.
    assert "session" in reply and reply["session"] is None


# ------------------------------------------------------------------------- opening

def test_start_headless_reaches_the_debugger_and_declares_what_it_launched() -> None:
    """A run that cannot say which run it was is not attributable to anything.

    The three tokens asserted are the three that decide what this session IS: the
    stop at the debugger (without it there is nothing to ask), the bound (without it
    an abandoned emulator runs until the machine is rebooted) and the emulator's own
    headless property (without it a window opens on somebody's desk).
    """
    reply = start_ok(seconds=60)
    argv = cast(list[str], reply["argv"])
    assert reply["mode"] == "headless"
    assert "-break-start" in argv
    assert argv[argv.index("-time-limit") + 1] == "60"
    # ADJACENCY, not mere presence: a `-set` pair that arrives split is an argument
    # this emulator neither refuses nor honours.
    assert argv[argv.index("sdl videodriver=dummy") - 1] == "-set"
    assert cast(float, reply["ready_after_s"]) > 0
    state = cast(dict[str, Any], reply["session"])
    assert state["alive"] is True and state["watched"] is False
    assert state["drain_alive"] is True, "the terminal reader never started"


@pytest.mark.windowed
@pytest.mark.skipif(not WINDOW_FLAGS,
                    reason="set DOSBOX_X_LIVE_WINDOW_FLAGS (one argv token per line, "
                           "as `place-window dosbox` prints them) to exercise the "
                           "watched path")
def test_start_shared_keeps_the_callers_flags_and_adds_no_dummy_driver() -> None:
    """The WATCHED path, on the real emulator, bounded to seconds.

    WHAT THIS COVERS IS THE MECHANISM AND NOT THE MODE'S INTENT, and the difference
    is worth stating because the case would otherwise look like it was validating
    something it cannot. `shared` means somebody is watching; nobody is watching this.
    What is checked is that the caller's tokens reach argv intact and adjacent, that
    the headless property is NOT added on top of them, and that a window session
    really comes up and answers. Where the window lands is the helper's decision and
    is not re-derived here.

    It is short and bounded for the same reason: the fleet rule sends an unwatched run
    to the secondary display, so the flags handed in already keep it off whatever the
    person is using, and it is gone in seconds either way.
    """
    reply = start_ok(seconds=30, mode="shared", window_flags=WINDOW_FLAGS)
    argv = cast(list[str], reply["argv"])
    assert reply["mode"] == "shared"
    assert "sdl videodriver=dummy" not in argv, "a watched session was forced headless"
    # THE TOKENS SURVIVE AS A RUN, in order: reversing them or gluing a pair is
    # exactly what an unrecognised argument is made of.
    joined, want = "\x00".join(argv), "\x00".join(WINDOW_FLAGS)
    assert want in joined, f"the placement flags did not arrive intact: {argv}"
    assert cast(dict[str, Any], reply["session"])["watched"] is True
    # AND IT REALLY CAME UP: a windowed session that reaches its debugger answers with
    # a value, which is the only evidence the flags were accepted rather than hung on.
    regs = cast(dict[str, Any], server.registers())
    assert regs["status"] == "ok", regs
    assert regs["registers"]["CS"] == "F000"


def test_stop_brings_a_running_headless_guest_back_through_the_debugger_channel() -> None:
    """`stop` sends BREAK down the emulator's own debugger channel: a headless guest released
    with nothing armed runs, `stop` brings it back and surveys the stop, and a second `stop`
    says it was already stopped. The release is checked running first, so a `stop` that
    found the machine parked could not pass for one that broke in."""
    start_ok(seconds=60)
    released = cast(dict[str, Any], server.resume())
    assert released["status"] == "ok" and released["halted"] is False, released
    back = cast(dict[str, Any], server.stop())
    assert back["status"] == "ok" and back["interrupted"] is True and back["how"] == "break", back
    assert "registers" in back and cast(float, back["waited_s"]) >= 0
    again = cast(dict[str, Any], server.stop())
    assert again["interrupted"] is False


# ------------------------------------------------------------------- what it is

def test_status_reports_the_live_session_and_not_a_remembered_one() -> None:
    """The fields a caller reasons with, read off a machine that really exists.

    `seconds_elapsed` is asserted to MOVE, which is the one thing a remembered state
    cannot do, and `drain_alive` to hold: a drain thread killed by a transient error
    makes every later read return nothing forever while `alive` still says true, so a
    session that has become a broken instrument reports itself as a quiet machine.
    """
    start_ok(seconds=60)
    first = cast(dict[str, Any], server.status())
    assert first["status"] == "ok"
    assert wait_for(lambda: cast(dict[str, Any], server.status())["session"][
        "seconds_elapsed"] > first["session"]["seconds_elapsed"], seconds=10), \
        "the elapsed time did not move: this is not a reading of a live session"
    later = cast(dict[str, Any], server.status())["session"]
    assert later["alive"] is True
    assert later["drain_alive"] is True and later["drain_ended"] == ""
    assert later["altered"] is False, "nothing wrote to this machine"
    assert later["terminal_bytes_dropped"] == 0, (
        "the terminal overflowed on an idle session, so a screen delta had a hole "
        "in it and the drain is not keeping up")
    # THE MACHINE FACTS, read off the park: the reset vector, in real mode, nothing declared.
    assert first["pc"] == "F000:0000FFF0" and first["cpu_mode"] == "real", first
    assert first["declarations"] == {"breakpoints": 0, "watches": 0}, first


# An `int 3` placed in free conventional memory after a `nop`: the debugger does not check a
# breakpoint on the FIRST instruction it runs after a resume (it would stop where it already
# is), so a trap placed there is stepped over whichever way the key is set, and the `nop` is
# what puts the trap second. `jmp $` keeps a guest that did not stop busy and harmless.
_TRAP_AT = "0050:00F0"
_TRAP = "90CCEBFE"


@pytest.mark.parametrize("key", [True, False], ids=["key_on", "key_off"])
def test_break_on_int3_stops_the_guests_own_int3_and_only_with_the_key(key: bool) -> None:
    """`start(break_on_int3=True)` stops the machine at the guest's own `int 3`, at the trap
    itself; without it the same trap runs through the guest's vector and the machine keeps
    running. The trap is reached once DOS is up: the key arms its breakpoint during DOS's
    start, and before that an `int 3` has no vector to go to."""
    start_ok(seconds=120, break_on_int3=key)
    server.breakpoint_interrupt(number=0x21)
    booted = cast(dict[str, Any], server.resume(seconds=30))
    assert booted["halted"] is True, "DOS never called INT 21h: nothing here was measured"
    server.breakpoint_clear(ref="BPINT 21")
    assert server.write(ref=_TRAP_AT, data_hex=_TRAP)["verified"] is True
    seg, off = (int(x, 16) for x in _TRAP_AT.split(":"))
    server.set_register(name="cs", value=seg)
    server.set_register(name="eip", value=off)
    here = cast(dict[str, Any], server.registers())["registers"]
    assert (int(here["CS"], 16), int(here["EIP"], 16)) == (seg, off), here
    ran = cast(dict[str, Any], server.resume(seconds=10))
    if key:
        assert ran["halted"] is True, ran
        assert ran["stopped_at"]["cs"] == f"{seg:04X}", ran
        assert int(ran["stopped_at"]["eip"], 16) == off + 1, ran     # at the trap, not past it
    else:
        assert ran["halted"] is False, ran


# ----------------------------------------------------------------- reading it

def test_registers_returns_a_value_the_caller_did_not_supply() -> None:
    """The reply a terminal echo cannot fabricate.

    An acknowledgement contains only words the caller typed. The reset vector does
    not: `CS=F000 EIP=0000FFF0` is where an x86 starts and it comes from the machine.
    Measured while this server was built, a probe looking for its own command words
    scored TRUE with no emulator running at all.
    """
    start_ok(seconds=60)
    reply = cast(dict[str, Any], server.registers())
    assert reply["status"] == "ok", reply
    regs = cast(dict[str, str], reply["registers"])
    assert regs["CS"] == "F000" and regs["EIP"] == "0000FFF0"
    # EAX IS NAMED DELIBERATELY. The register pane is painted with the alternate
    # character set, so a name abuts the run of fill in front of it; when the pattern
    # carried a word boundary, every register whose name followed a space was read and
    # EAX was the one that never matched. A case asserting "some registers came back"
    # is green over exactly that.
    assert "EAX" in regs


def test_set_register_takes_and_its_mark_survives_into_every_later_reply() -> None:
    """Two guarantees, and the second is the one a caller cannot recover for itself.

    The write is READ BACK, so a name this build does not expose cannot be reported
    as a successful write. And `altered` is then carried by EVERYTHING afterwards,
    the INVALID replies included: a measurement taken on a forced state is not a
    measurement of the program, and three questions later there is no other way to
    know the machine was pushed.
    """
    start_ok(seconds=60)
    assert cast(dict[str, Any], server.status())["session"]["altered"] is False
    reply = cast(dict[str, Any], server.set_register(name="ax", value=0x1234))
    assert reply["status"] == "ok", reply
    assert reply["registers"]["EAX"] == "00001234"
    assert reply["readback"] == "1234" and reply["verified"] is True
    assert reply["session"]["altered"] is True
    # ON A LATER REPLY, and on an INVALID one, which is where an earlier version of
    # this server dropped it and is the reply a caller reasons hardest about.
    assert cast(dict[str, Any], server.status())["session"]["altered"] is True
    invalid = cast(dict[str, Any], server.captures())
    assert invalid["status"] == "INVALID"
    assert invalid["session"]["altered"] is True, (
        "an INVALID reply stopped saying the machine had been written to")


def test_read_memory_answers_about_the_address_that_was_asked_for() -> None:
    """The case this tool never had, and it went RED the first time it was run.

    MEASURED during #317's refinement: `read_memory(0xF000,
    0xE000)` handed back a delta whose first surviving data row was `E040`. The row
    for the requested address was in what the debugger produced and NOT in what the
    tool returned, because the reply was sliced to its last 2000 characters and the
    debugger's screen carries its Output log BELOW its Data view. So the cap kept the
    emulator's boot chatter and threw away the memory, and the tool said `ok`.

    That is the same shape as the `memdump` defect and it survived for the same
    reason: nothing ever asked whether the answer was IN the answer.
    """
    start_ok(seconds=60)
    seg, off = 0xF000, 0xE000
    reply = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{off:08X}"))
    assert reply["status"] == "ok", reply
    assert reply["segment"] == seg and reply["offset"] == off
    rows = cast(list[str], reply["rows"])
    # THE ROW FOR THE ADDRESS THAT WAS ASKED FOR, AND IT IS THE FIRST: `D` starts its
    # data view at the address it was given, so anything else means the reply is about
    # somewhere near where the caller asked rather than where they asked.
    assert rows and rows[0].startswith(f"{seg:04X}:{off:08X}"), (
        f"the rows do not begin at {seg:04X}:{off:04X}, which is the address asked "
        f"about. They begin: {rows[:1]}")
    # NOT A SCREEN, and asserted by what is ABSENT rather than by re-matching the
    # pattern against its own output. `all(DATA_ROW.fullmatch(r))` cannot fail: every
    # element IS a `group(0)` of that pattern, so it fullmatches by construction, and
    # it stayed green over rows that had swallowed a pane header.
    joined = " ".join(rows)
    for stray in ("Overview", "Data view", "Output", "I->", "DEBUG:"):
        assert stray not in joined, f"{stray!r} came back inside the rows: {rows}"
    # AND THE COUNT IS THE SHAPE: `D` paints eight rows of sixteen bytes on this
    # build, so anything less means rows were dropped and anything more means the
    # delta carried a second repaint.
    assert len(rows) == 8, f"expected eight data rows, got {len(rows)}: {rows}"
    # AND IT IS REAL MEMORY, not a buffer of zeros: this build's BIOS names itself
    # here, which a wrong segment and an unmapped read cannot both produce.
    body = "\n".join(rows)
    assert "DOSBox-X BIOS" in body or "COMPATIBLE BIO" in body, body[:300]
    # THE ADDRESS IS RANGE-CHECKED, because out of range it would not fit the format
    # and the debugger would be sent a command nobody wrote.
    bad = cast(dict[str, Any], server.read_memory(ref="10000:00000000"))
    assert bad["status"] == "INVALID" and "segment" in str(bad["message"])


def test_debug_hands_back_a_delta_and_says_whether_it_kept_all_of_it() -> None:
    """The one tool with no server-side guardrail, so its honesty IS its contract.

    A general command cannot be reduced by MEANING, because the server does not know
    what the caller asked. So the cap stays, and what this asserts is that the reply
    DECLARES it: a caller must be able to tell a whole delta from a slice, and while
    the cap was undeclared the docstring above it boasted about handing back the
    honest thing.
    """
    start_ok(seconds=60)
    reply = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert reply["status"] == "ok", reply
    assert reply["command"] == "BPLIST"
    assert "Breakpoint list" in str(reply["screen_delta"])
    # THE TWO FIELDS THAT MAKE THE CAP READABLE, ASSERTED AGAINST THE CAP and not
    # against each other. The first version compared `screen_chars` with
    # `len(screen_delta)` and recomputed `clipped` from the same two, which holds for
    # EVERY input by construction: `len(out[-keep:]) == min(len(out), keep)`. So the
    # exact defect the docstring names -- reporting the SLICE length as `screen_chars`
    # -- was green, and so was breaking the cap.
    delta, chars = str(reply["screen_delta"]), cast(int, reply["screen_chars"])
    assert len(delta) <= DEBUG_CAP
    assert reply["clipped"] is (chars > DEBUG_CAP), (
        f"clipped={reply['clipped']} with {chars} characters against a {DEBUG_CAP} cap")
    if not reply["clipped"]:
        # UNCLIPPED, `screen_chars` MUST BE THE WHOLE DELTA. That is the assertion the
        # slice-length defect fails, and it can only be made on this branch.
        assert chars == len(delta), (
            f"screen_chars {chars} is not the length of an unclipped delta ({len(delta)})")
    resumed = cast(dict[str, Any], server.resume())
    assert resumed["clipped"] is (
        cast(int, resumed["screen_chars"]) > SMALL_CAP), resumed["screen_chars"]

    # WHERE THE `clipped: True` BRANCH IS COVERED, AND WHY IT IS NOT COVERED HERE.
    #
    # This case used to close by DELEGATING it: "an ordinary BPLIST repaint is ~2972
    # characters, which is under this tool's 4000 cap and over the 2000 that `resume`
    # and `breakpoint_interrupt` use, so the clipped branch is exercised THERE rather
    # than pretended at here." MEASURED on a real emulator, that delegation
    # is FALSE. `resume` never sees the BPLIST repaint; it sees its own, and against a
    # QUIET guest its own is 1542 characters. `debug("BPLIST")` is 2973 and
    # `debug("HELP")` -- the longest listing this debugger prints -- is 3083. Every one
    # of them is under its cap, so BOTH assertions above take the FALSE branch, every
    # run, and neither can fail for the reason it names.
    #
    # AND THE OBVIOUS REPAIR IS A TRAP, so it is written down rather than left for the
    # next person to walk into. Asking `HELP` again HERE, after the `resume` above,
    # does come back `clipped: True` at 5308 characters -- and it is not the command's
    # answer at all: the machine is RUNNING, the console swallows the command, and what
    # comes back is the guest's own instrumentation chatter. MEASURED, `"BPLIST" in
    # delta` is False and `"EIP=" in delta` is False; the text is E9 trace lines. An
    # assertion there would go green on a delta that answers nothing, and it would do
    # so only because THIS guest is a chatty instrumented application -- which is the
    # live tier's project dependency wearing a different hat.
    #
    # SO IT IS DECLARED RATHER THAN FAKED. On a STOPPED machine on this build no
    # ordinary command reaches `debug`'s cap, so the true branch is not reachable from
    # here honestly. It is covered at CONTRACT tier, on a screen built to exceed the
    # cap, in `test_a_delta_longer_than_the_cap_is_cut_and_says_so`. What is asserted
    # live is the relation on the branch that IS reachable, above.


def test_memdump_lands_the_exact_bytes_and_leaves_nothing_behind(
        tmp_path: Path) -> None:
    """Through the tool, which is the layer that had never run it against a machine.

    THE ADDRESS WAS MEASURED, not reasoned. The session is stopped at the reset
    vector, before the BIOS has initialised anything, so the obvious choice is
    worthless: 256 bytes at `0000:0400` hold ONE distinct value on this build and so
    do 256 at `F000:0000`, while `F000:E000` holds 26. Only the third can tell a real
    read from a buffer of zeros, which is the whole reason for looking at the content.
    """
    start_ok(seconds=90)
    dest = tmp_path / "dump.bin"
    reply = cast(dict[str, Any], server.memdump(
        ref="F000:0000E000", length=256, dest=str(dest)))
    assert reply["status"] == "ok", reply
    assert reply["path"] == str(dest), "it reported a path it did not write to"
    assert reply["bytes"] == 256 and dest.stat().st_size == 256
    body = dest.read_bytes()
    assert len(set(body)) > 1, ("every byte is identical, which is what a wrong "
                                "segment and a truncated write both look like")
    # THE LIST OF PLACES IS ASKED OF THE MODULE and never written out here: a
    # hand-copied pair of names silently stops covering a third location the day one
    # is added, which is precisely how the original defect was framed.
    left = [p for p in cast(ds.Session, dstate.STATE.session)._memdump_candidates()
            if p.exists()]
    assert not left, f"the dump was left behind at {left}"


# --------------------------------------------------------------- letting it run

def test_breakpoint_interrupt_arms_the_interrupt_it_was_given_and_not_another() -> None:
    """The hex-for-decimal trap, asserted against the debugger's own acknowledgement.

    `number` is the debugger's HEX value, so DOS is 33 and passing 21 arms interrupt
    0x15 instead, silently. A case that only checked "it was acknowledged" is green
    over that, because the debugger acknowledges the wrong breakpoint just as
    cheerfully. What is asserted is the interrupt NAMED BACK.
    """
    start_ok(seconds=60)
    reply = cast(dict[str, Any], server.breakpoint_interrupt(number=0x21, ah=0x4C))
    assert reply["status"] == "ok", reply
    assert "INT 21 AH=4C" in str(reply["screen_delta"]), reply["screen_delta"][-400:]


def test_resume_lets_the_guest_advance() -> None:
    """The guest genuinely RUNS, evidenced by text that cannot appear while stopped.

    THE INDEPENDENT EVIDENCE IS KEPT, and that is deliberate now that `resume` answers
    for itself (#382). `halted: False` is this tool's own reading, so resting the case
    on it alone would let the tool mark its own homework -- a `halted` hardwired to
    False would pass. DOS bringing up COMMAND.COM is something only a running machine
    produces, and the two must AGREE.
    """
    start_ok(seconds=90)
    reply = cast(dict[str, Any], server.resume())
    assert reply["status"] == "ok", reply
    # Headless with nothing armed: the guest is read through its log until `close`.
    ran = str(reply["screen_delta"])
    assert any(m in ran for m in ("COMMAND.COM", "EMS page frame", "XMS:")), ran[-400:]
    assert reply["halted"] is False, reply
    assert reply["stopped_at"] is None, reply
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True


def test_e9_returns_matching_lines_and_counts_all_of_them(tmp_path: Path) -> None:
    """THE POSITIVE PATH, which no live case had ever exercised.

    Both live cases this channel had were INVALID branches: no logfile, and a log
    with no instrumentation. Neither ever saw a line come back. So the tool's actual
    job -- filtering at the source so what crosses into the conversation is the
    answer and not the haystack -- rested on fixtures, which is the shape `memdump`
    shipped broken in.

    AND THE COUNT IS THE POINT, not merely that lines arrived. `lines_total` is how many
    matched and `lines` is what came back; reporting the slice's length under
    the first name meant a caller asking "how many times did this fire" got their own
    limit back and could not tell a genuine 40 from a truncated 5000. It is asserted
    with a limit DELIBERATELY SMALLER than the number of hits, because with limit at
    or above the total the two are equal and the break is invisible.
    """
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log(channel="guest", pattern="Bochs port E9h", limit=2))
    assert reply["status"] == "ok", reply
    lines = cast(list[str], reply["lines"])
    assert len(lines) == 2 and len(reply["lines"]) == 2
    assert cast(int, reply["lines_total"]) > 2, (
        f"lines_total ({reply['lines_total']}) is not more than what came back, so this "
        f"case cannot tell the total from the slice")
    assert reply["truncated"] is True
    assert all(ln.startswith("Bochs port E9h:") for ln in lines), lines
    # AN EMPTY MATCH IS AN ANSWER AND NOT AN INVALID, which is the distinction this
    # whole channel exists to keep. The pattern is one the guest cannot emit.
    empty = cast(dict[str, Any], server.log(channel="guest", pattern="zzz-no-guest-emits-this",
                                            limit=5))
    assert empty["status"] == "ok", empty
    assert empty["lines"] == [] and empty["lines_total"] == 0


def test_captures_and_a_still_come_out_of_a_real_recording(tmp_path: Path) -> None:
    """Both halves, on one recording, because a still is an EXTRACTION from the video.

    They share a session deliberately: the still cannot exist without the video, so
    splitting them would mean recording twice to assert one thing each.

    IT WAITS ON THE PROPERTY IT ASSERTS, not on a proxy. Waiting for the file to reach
    a SIZE and then asserting its FRAME COUNT is two thresholds that can disagree, and
    they did: a loop broke at 200 KB with 89 frames against an assertion of 100.

    The conf is the caller's with its run-and-exit removed, and the removal is
    REQUIRED to match: `program` is passed with `-c`, which runs AFTER `[autoexec]`,
    so a conf ending in `exit` quits before it is reached, and a patch that quietly
    changed nothing would leave this measuring the original conf under the patched
    one's name.
    """
    caps = tmp_path / "caps"
    caps.mkdir()
    conf = conf_that_does_not_exit(tmp_path)
    reply = cast(dict[str, Any], server.start(
        conf=str(conf), cwd=CWD, seconds=120,
        program=GUEST_PROGRAM,
        capture_video=True, captures_dir=str(caps)))
    assert reply["status"] == "ok", reply
    server.resume()

    def enough() -> bool:
        files = sorted(caps.glob("*.avi"), key=lambda f: f.stat().st_size)
        return bool(files) and cast(
            int, ds.avi_facts(files[-1].read_bytes())["frames"]) > 200

    assert wait_for(enough, seconds=90), "no capture reached 200 frames: INVALID"

    got = cast(dict[str, Any], server.captures())
    assert got["status"] == "ok", got
    files = cast(list[dict[str, Any]], got["captures"])
    biggest = files[-1]
    assert biggest["riff_avi"] is True, files
    assert cast(int, biggest["frames"]) > 100, files
    # LARGEST LAST is a guarantee and not an accident: a program that boots in text
    # and then goes graphical leaves a small first file and the real one after it, so
    # a caller taking "the capture" takes the wrong one if this order flips.
    assert [f["bytes"] for f in files] == sorted(f["bytes"] for f in files), files

    shot = tmp_path / "shot.png"
    frame = cast(dict[str, Any], server.capture_frame(at=60, dest=str(shot)))
    assert frame["status"] == "ok", frame
    assert frame["path"] == str(shot)
    assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "that is not a PNG"
    assert frame["bytes"] == shot.stat().st_size > 1000
    # `at` IS NOT EVIDENCE: the server echoes back the number it was given, so
    # asserting it is asserting a value this test supplied.
    #
    # WHAT TIES THE STILL TO THE FRAME ASKED FOR is that a DIFFERENT frame gives a
    # DIFFERENT image.
    #
    # THE REASON THIS COMMENT USED TO GIVE BELONGED TO ANOTHER GUEST -- "the guest is
    # animating (its startup reveal)" was a private application's, and `probe.com`
    # writes to port 0xE9 and never touches the screen. So the assertion was left
    # resting on a mechanism that no longer exists, which is not the same as being
    # wrong: it was UNEXPLAINED, and an adversarial pass predicted it would now be
    # flaky or dead.
    #
    # MEASURED instead of assumed, with the control the case cannot run for itself:
    # frames 60 and 61 come back BYTE-IDENTICAL (sha 93c604a8...), 60 and 180 differ,
    # and frame 60 reproduces byte-identically across two SEPARATE sessions. So the
    # frame is stable, `at=` really reaches the frame asked for, and the difference
    # between 60 and 180 is content and not noise -- a stronger guarantee than the old
    # comment claimed, and the first one anybody checked.
    #
    # Without this assertion, `select='eq(n\,{at})'` hardcoded to frame 0 -- or
    # defaulting to the wrong capture -- is green every time, and the whole extraction
    # guarantee has no coverage on either tier.
    other = tmp_path / "shot2.png"
    second = cast(dict[str, Any], server.capture_frame(at=180, dest=str(other)))
    assert second["status"] == "ok", second
    assert other.read_bytes() != shot.read_bytes(), (
        "frames 60 and 180 came out byte-identical, so `at` is reaching nothing and "
        "any frame number would return this same image")


# ------------------------------------------------------------------------ closing

def test_close_clears_the_session_so_the_next_tool_says_there_is_none() -> None:
    """Closing is TWO things, and the second is the one that had no live case.

    The emulator ends, and the server stops pointing at it. Leaving the global set
    made `status` keep reporting a corpse and made the next `start` leak its terminal
    rather than reclaim it, and the reply carrying `closed: true` looks identical
    either way.

    THE REPLY CARRIES THE STATE AS IT WAS, deliberately: a caller needs to know what
    they just ended, and `_reply` cannot say it afterwards because there is nothing
    left to ask.
    """
    start_ok(seconds=60)
    reply = cast(dict[str, Any], server.close())
    assert reply["status"] == "ok" and reply["closed"] is True
    assert reply["session"] is not None, "it did not say what it had just closed"
    assert dstate.STATE.session is None, "the server is still pointing at a dead session"
    # WHAT A CALLER SEES NEXT, which is the half that matters: every tool needing a
    # machine must now refuse, rather than reading nothing and calling it an answer.
    after = cast(dict[str, Any], server.registers())
    assert after["status"] == "INVALID" and "no live session" in str(after["message"])
    assert cast(dict[str, Any], server.status())["session"] is None
    # CLOSING TWICE IS NOT A FAILURE: the bound can have got there first, and a
    # caller told to always close what they opened must be able to.
    again = cast(dict[str, Any], server.close())
    assert again["status"] == "ok" and again["closed"] is False


def test_closing_a_running_session_does_not_wait_out_a_signal_it_ignores() -> None:
    """The cost of ending a session that was actually USED, which is every real one, and
    the SHAPE of that ending now that `start` turns the quit warning off.

    THAT IS WHAT THIS CASE WATCHES FOR REGRESSION. A running session USED to ignore the
    SIGTERM -- the emulator opened its "Quit anyway?" dialog and sat behind it until the
    SIGKILL, so a resumed session closed by signal death (a negative exit code) after
    spending the whole grace. With the warning off it ANSWERS the TERM and exits cleanly:
    `how: quit`, exit code 0, in a fraction of a second. So the ending to assert is a
    clean quit and not a kill, and the timing bar is now headroom rather than the knife
    edge it was.

    THE BAR IS 5 s AND IT STILL BITES on the one regression it can: delete the signalling
    entirely and `Session.close` returns in ~0.05 s with the emulator running on to its
    bound -- so `proc.poll()` being non-None is what proves the process was really ended,
    and `took < 5` that the close did not sit waiting on a dialog nobody answers (which is
    what a quit warning left back on would reintroduce).

    ONLY A REAL EMULATOR CAN FAIL THIS. A fake session's `close` returns at once, so
    neither the ending's shape nor how long the process takes to answer a signal is a
    property any contract test has access to.
    """
    start_ok(seconds=90)
    resumed = cast(dict[str, Any], server.resume())
    # IT MUST REALLY HAVE RUN, or this measures the stopped path under the running
    # path's name and passes for the wrong reason. Since #382 `resume` answers that
    # itself, and the independent evidence stays beside it: a tool's own reading is not
    # what a case about somebody else's timing should rest on.
    assert any(m in str(resumed["screen_delta"])
               for m in ("COMMAND.COM", "EMS page frame", "XMS:")), resumed
    assert resumed["halted"] is False, resumed
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True

    # THE PROCESS IS HELD ONTO BEFORE CLOSING, because `closed: True` is set by the
    # server whenever a session existed and is not a fact about the emulator. Without
    # this, the case's BEST pass was `Session.close` doing nothing at all: delete the
    # signalling entirely and `took` drops to ~0.05 s, `closed` is still True, the case
    # goes green FASTER than before, and the emulator runs on to its bound.
    proc = cast(ds.Session, dstate.STATE.session).proc
    t0 = time.monotonic()
    reply = cast(dict[str, Any], server.close())
    took = time.monotonic() - t0
    assert reply["closed"] is True
    assert proc.poll() is not None, (
        "the emulator is STILL RUNNING after close returned. `closed: true` says a "
        "session was there, not that it ended")
    # A CLEAN QUIT, not a kill: with the quit warning off the running emulator answers
    # the TERM and exits 0, which is the whole point of forcing it off. `how: killed`
    # here would mean the warning came back (a conf overriding the server's `-set`) or
    # the guest wedged.
    assert reply["how"] == "quit", (
        f"close ended a running session by {reply['how']!r}, not a clean quit: the "
        f"emulator ignored the TERM, so the quit warning is back on")
    assert cast(int, reply["exit_code"]) == 0, (
        f"exit code {reply['exit_code']}: a clean quit on SIGTERM exits 0")
    assert took < 5.0, (
        f"closing a running session took {took:.2f}s. With the quit warning off the "
        f"emulator answers the TERM at once; a wait this long means it is sitting behind "
        f"a dialog nobody will answer, the failure forcing the warning off exists to "
        f"prevent. The honest ceiling is TERM_GRACE ({ds.TERM_GRACE}s) plus the drain "
        f"join ({ds.DRAIN_JOIN_SECS}s)")


# ----------------------------------------------------------------- symbols_load / find

def test_a_real_mode_session_refuses_rather_than_placing_at_base_zero(
        tmp_path: Path) -> None:
    """The guard, against the machine that really produces the trap.

    A session at `-break-start` is in real mode, where there are no descriptors to measure
    a base from; taken as `base = 0`, every symbol would be placed at its raw offset --
    loading cleanly, reporting `ok`, naming whatever occupies low memory. The refusal is
    read off the register pane before `SELINFO` is asked, and names `base` as the remedy.
    Only a real emulator can show that the pane really says real mode here.
    """
    start_ok(seconds=60)
    regs = cast(dict[str, Any], server.registers())["registers"]
    assert regs["CS"] == "F000", (
        f"expected a session stopped at the reset vector, got CS={regs['CS']}")
    src = tmp_path / "probe.sym"
    src.write_text("0000fff0 T _reset_vector\n", encoding="utf-8")
    got = cast(dict[str, Any], server.symbols_load(source=str(src)))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert "real mode" in got["message"] and "`base`" in got["message"], got


def test_symbols_load_places_a_real_list_through_the_whole_chain(
        tmp_path: Path) -> None:
    """Descriptor refused, base supplied, file written, `LV`, `SV`, decode, lookup.

    IT IS DELIBERATELY NOT DJGPP-SPECIFIC. This package serves every DOS project, so a
    live case needing one toolchain's runtime would be testing the caller. The base is
    passed explicitly -- which the case above establishes is the honest thing to do on a
    real-mode session -- and 0xF0000 is CS=F000's, so the linear addresses it produces
    are real addresses on this machine.

    WHAT ONLY A REAL EMULATOR CAN SHOW, and the reason this exists beside the contract
    cases: that a file written into the emulator's working directory is the one `LV`
    opens, that the debugger holds what it was given, and that the filename survives a
    command which truncates it to twelve characters and reports `ok` for whatever it
    used.
    """
    start_ok(seconds=90)
    src = tmp_path / "probe.sym"
    # `nm` output in `nm`'s shape. The offsets sit inside the ROM segment, so with the
    # base below they name real addresses.
    src.write_text("00000000 T _rom_start\n"
                   "0000fff0 T _reset_vector\n"
                   "0000abcd t _somewhere_in_rom\n", encoding="utf-8")

    got = cast(dict[str, Any], server.symbols_load(source=str(src), base="F0000"))
    assert got["status"] == "ok", got
    assert got["parsed"] == 3 and got["kept"] == 3, got
    # THE ROUND TRIP IS THE ASSERTION. `ok` is not evidence from this emulator.
    assert got["loaded"] == 3, (
        f"the debugger reported ok and holds {got['loaded']} records. Those disagree, "
        f"so nothing here is a reading of what it loaded")

    found = cast(dict[str, Any], server.symbols_find(name="_reset_vector"))
    assert found["status"] == "ok", found
    assert found["symbols"][0]["linear"] == 0x000FFFF0, found

    # AND BACK THE OTHER WAY, which is the question you actually have when stopped:
    # what am I inside? `F000:FFF0` is where this session is parked.
    where = cast(dict[str, Any], server.symbols_find(linear="000FFFF2"))
    assert (where["name"], where["delta"]) == ("_reset_vector", 2), where


def test_symbols_load_leaves_no_file_behind_in_the_working_directory(
        tmp_path: Path) -> None:
    """The two files live in the emulator's WORKING DIRECTORY, which is somebody's
    project. A debugger cannot be told a path -- its filename argument survives twelve
    characters -- so the files have to go there, and they have to leave.

    MEASURED while this was being built: a `SV` to a long absolute path answered
    `failure` and a `SV` to a long relative one answered `ok` for a DIFFERENT file. The
    working directory is the only place this can put them, so cleaning up is the whole
    of the contract.
    """
    start_ok(seconds=60)
    cwd = Path(CWD)
    # THE SOURCE GOES IN `tmp_path`. Only `SYMS.BIN`/`SYMSBK.BIN` have to be in the
    # emulator's working directory -- the debugger's filename argument survives twelve
    # characters -- and this file is read host-side. Putting it in the caller's project
    # was ironic in the one case whose whole point is that nothing is left there.
    src = tmp_path / "probe.sym"
    src.write_text("00001000 T _x\n", encoding="utf-8")
    try:
        # The base is explicit because this session is in real mode, where reading one
        # is correctly refused. What this case is about is the FILES, not the base.
        got = cast(dict[str, Any], server.symbols_load(source=str(src),
                                                       base="F0000"))
        assert got["status"] == "ok", got
    finally:
        src.unlink(missing_ok=True)
    # ASSERT FIRST, THEN CLEAN UP WHATEVER IS THERE. A RED here means a file is sitting
    # in the caller's repository, and leaving it would poison every later run of this
    # case with a refusal about a file the NEXT run did not put there. Measured for
    # real: an earlier run of this case did exactly that, and its leftover made the
    # following live case fail for the wrong reason.
    left = [n for n in (ds.SYM_LOAD_NAME, ds.SYM_SAVE_NAME) if (cwd / n).exists()]
    for name in left:
        (cwd / name).unlink()
    assert not left, f"{left} was left in {cwd}, which is somebody's project"


@pytest.mark.parametrize("which", ["load", "save"])
def test_a_file_already_sitting_at_either_name_is_refused_not_overwritten(
        which: str, tmp_path: Path) -> None:
    """The mirror of the case above, and the one that stops "delete on the way in"
    passing it: a file of that name that this did not put there is the caller's.

    BOTH NAMES, because the docstring says "either" and only one was exercised.
    """
    start_ok(seconds=60)
    cwd = Path(CWD)
    intruder = cwd / (ds.SYM_LOAD_NAME if which == "load" else ds.SYM_SAVE_NAME)
    src = tmp_path / "probe.sym"
    src.write_text("00001000 T _x\n", encoding="utf-8")
    intruder.write_bytes(b"not mine")
    try:
        got = cast(dict[str, Any], server.symbols_load(source=str(src),
                                                       base="F0000"))
        assert got["status"] == "INVALID", got
        assert "will not overwrite" in got["message"], got
        assert intruder.read_bytes() == b"not mine", "it overwrote the caller's file"
    finally:
        intruder.unlink(missing_ok=True)


# ------------------------------------------------------------------- the debugging

# WHERE A FRESH SESSION IS STOPPED, and what the instruction there does. Every case
# below is anchored on it because it is the one point in a DOS machine's life that is
# the same on every host and every conf: the reset vector, whose five bytes are
# `EA 5B E0 00 F0` -- `jmp F000:E05B`. That makes the target of ONE step a fact about
# the x86 and not about this build, which is what a live assertion needs.
RESET_CS, RESET_EIP = "F000", "0000FFF0"
AFTER_ONE_STEP = "0000E05B"

# WHICH HALF OF THAT IS ARCHITECTURAL, because the first version of this comment said
# both were. The reset ADDRESS `F000:FFF0` is the x86's and is the same everywhere. The
# DESTINATION `E05B` is DOSBox-X's own BIOS reset entry -- its `BIOS_DEFAULT_RESET_
# LOCATION`, following the IBM PC POST convention -- so it is a property of THIS
# emulator's ROM image. If this constant ever stops matching, the emulator changed;
# `step` is not the thing to go and audit.

# How many `INT 21` calls `a_return_address_in_ram` will walk past looking for one made
# from RAM. It is a CEILING on a search, not a count: the early calls of a boot come
# from the BIOS in ROM, and how many there are before a program makes one is the
# guest's business. Reaching it is a failure that says so, never a silent pass.
BIOS_CALLS_TO_SKIP = 40


def test_step_advances_by_exactly_one_instruction_and_says_where_it_landed() -> None:
    """A step is only a step if the machine MOVED, and moved to the right place.

    The reset vector is `jmp F000:E05B`, so one step over it lands at E05B and nowhere
    else. Asserting the destination rather than "the address changed" is the difference
    between proving the keystroke executed THAT instruction and proving the emulator
    did something.

    THE MODE COMES BACK TOO, and it is `Real` here: the same sixteen bits after `CS=`
    would be a selector three seconds later in the boot, and an address quoted without
    its mode is not an address.
    """
    start_ok(seconds=60)
    reply = cast(dict[str, Any], server.step(mode="over", count=1))
    assert reply["status"] == "ok", reply
    assert reply["before"] == {"cs": RESET_CS, "eip": RESET_EIP, "mode": "Real"}
    assert reply["after"] == {"cs": RESET_CS, "eip": AFTER_ONE_STEP, "mode": "Real"}
    assert reply["completed"] == 1 and reply["running"] is False


def test_stepping_a_running_machine_refuses_instead_of_pressing_keys_at_nobody(
        ) -> None:
    """THE REFUSAL, against a machine that is really running.

    WHAT ONLY THIS TIER SHOWS is narrower than the first version of this docstring
    claimed ("it cannot be shown against a double"). That the tool sends NOTHING is
    asserted at contract tier, on the keys the double records. What a double cannot
    produce is the CONSEQUENCE of not refusing: a real running guest swallows a
    keystroke with no error anywhere, so the reply would have described a machine the
    tool never touched, and only a real emulator is silent in that particular way.
    """
    start_ok(seconds=60)
    server.resume()
    reply = cast(dict[str, Any], server.step(mode="over", count=1))
    assert reply["status"] == "INVALID", reply
    # THE CODE FIRST, because it is the declared half of the refusal and `message` is the
    # half written for a human, so a rewording moves the one a caller must not be coupled
    # to. But `not_stopped` is shared: `where`'s register-pane refusal carries it too, and
    # a test one tier down exists precisely to stop `step` handing back THAT wording. So
    # the code alone would let the very regression its neighbour guards pass here. The
    # phrase below is the one only `step`'s own message has, and it is the same one pinned
    # in `test_dosbox_x_debug.py`.
    assert reply["code"] == "not_stopped", reply
    assert "a step is a KEYSTROKE" in reply["message"], reply


def a_return_address_in_ram() -> tuple[int, int]:
    """Stop the guest at one of its own `INT 21` calls, and give back where that call
    RETURNS to. Leaves the machine stopped with no breakpoints armed.

    IT HAS TO BE RAM, and that is the whole reason this helper exists rather than a
    literal. MEASURED: a code breakpoint in ROM is acknowledged,
    is listed by `BPLIST`, and NEVER FIRES -- `F000:E05B` and `F000:C9B0` were both
    tried, both are provably executed (the reset vector jumps to the first, which jumps
    to the second), and neither stopped the machine. So a case anchored on the reset
    vector would test `run_to`'s failure path while claiming to test its success one.

    AND IT HAS TO BE A FUTURE ADDRESS, which is the harder half: any address a stopped
    machine can name is one it has already reached. `INT` is what solves it without
    disassembling anything -- `CD 21` is two bytes and an interrupt returns to the
    instruction after it, so EIP+2 is a genuine future address, exactly reachable, and
    the arithmetic is the x86's rather than this guest's. The alternative was a literal
    from one project's boot, in a package that serves every DOS project.

    THE ASSUMPTION, said out loud: the first `INT 21` this catches is not `AH=4C`,
    which terminates and never returns. A boot's first DOS call is not a terminate, and
    if it ever were, this fails visibly rather than passing.
    """
    reply = cast(dict[str, Any], server.breakpoint_interrupt(number=0x21))
    assert reply["status"] == "ok", reply
    # THE EARLY `INT 21`s COME FROM THE BIOS ITSELF, in ROM -- MEASURED, the first one
    # of this boot is called from F000:0000DAC6 -- so this walks forward until one is
    # called from RAM, which is a program rather than the firmware. The bound is a
    # bound and not a guess about the count: if a guest never reaches one, this says so
    # instead of looping.
    seg = eip = 0
    for _ in range(BIOS_CALLS_TO_SKIP):
        server.resume()
        regs = cast(dict[str, Any], server.registers())
        assert regs["status"] == "ok", regs
        seg = int(regs["registers"]["CS"], 16)
        eip = int(regs["registers"]["EIP"], 16)
        if seg != 0xF000:
            break
    else:
        pytest.fail(
            f"every one of {BIOS_CALLS_TO_SKIP} INT 21 calls was made from the BIOS "
            f"ROM segment (last: {seg:04X}:{eip:08X}). A code breakpoint there is "
            f"acknowledged and never fires, so this case cannot measure what it is "
            f"named for: INVALID, not a pass")
    # THE TWO BYTES ARE READ, not assumed. `eip + 2` is the return address only for the
    # two-byte `CD 21` form, and `BPINT 21` fires on ANY entry to the vector -- including
    # the `pushf` + far-`CALL` form a TSR or DPMI hook chain uses, where the return
    # address is not eip+2 at all. Checking turns a wrong guess into a visible refusal
    # instead of a case that mysteriously never arrives.
    rows = cast(dict[str, Any], server.read_memory(ref=f"{seg:04X}:{eip:08X}"))
    assert rows["status"] == "ok", rows
    row = next(r for r in cast(list[str], rows["rows"])
               if r.startswith(f"{seg:04X}:{eip:08X}"))
    opcode = row.split()[1:3]
    assert opcode == ["CD", "21"], (
        f"the stop at {seg:04X}:{eip:08X} is not a two-byte `CD 21` (it reads "
        f"{opcode}), so eip+2 is not the return address and this case would be "
        f"measuring an address the machine never reaches: INVALID, not a pass")
    # ONLY A CODE BREAKPOINT MAY STOP IT AFTER THIS. Left armed, the interrupt
    # breakpoint would stop the machine at the very next DOS call and `run_to` would
    # report an arrival it had nothing to do with -- a green for the wrong reason,
    # which is worse than a red.
    server.debug(command="BPDEL *")
    return seg, eip + 2


def a_hot_address() -> str:
    """The timer interrupt's handler, read off the guest's own vector table (INT 8 at
    `0000:0020`): it runs eighteen times a second whatever the program does, which is what
    a CONTROL has to be. Read rather than assumed, so the address is this guest's."""
    vec = cast(dict[str, Any], server.read_memory(ref="0000:0020", length=4))
    assert vec["status"] == "ok", vec
    raw = bytes.fromhex(vec["hex"])
    off, seg = int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:], "little")
    return f"{seg:04X}:{off:04X}"


def test_run_to_arrives_at_a_real_address_and_takes_its_breakpoint_away() -> None:
    """The whole chain against a real debugger: arm, read the list back, resume, stop,
    and REMOVE what was armed.

    The removal is asserted through the debugger's own list rather than through the
    reply's own field, because `breakpoint_removed` is this tool's claim and the list
    is the machine's answer. A `BP` is persistent, so a leftover would silently stop
    the next `resume` at an address the caller had finished with.
    """
    start_ok(seconds=120)
    seg, off = a_return_address_in_ram()
    # The control is REQUIRED and its silence is irrelevant when the target ARRIVES: at the
    # park the BIOS has not filled the vector table yet, so there is no hot address to read,
    # and a RAM byte the boot never executes serves as the control of an arriving run.
    reply = cast(dict[str, Any], server.run_to(ref=f"{seg:04X}:{off:04X}", seconds=30,
                                               control="0000:0001"))
    assert reply["status"] == "ok", reply
    assert reply["arrived"] is True, reply
    assert reply["stopped_at"]["cs"] == f"{seg:04X}", reply
    assert int(reply["stopped_at"]["eip"], 16) == off, reply
    assert reply["breakpoint_removed"] is True, reply
    # READ THE LAST LISTING, not the screen. A substring search over the delta is what
    # this case did first and it FAILED against a correct removal: the Output pane
    # SCROLLS, so `run_to`'s own earlier listings are still on it, and the row was found
    # in a repaint of the state before the delete. That is the hazard
    # `parse_breakpoints` exists for, met by the test written to check it.
    #
    # AND A SENTINEL, because `not in []` is true. `parse_breakpoints` returns an empty
    # list when the header is absent -- its own docstring says every caller must check
    # for the header rather than reading "no rows" as "nothing armed" -- and
    # `screen_delta` is a POSITIONAL tail, so a listing whose header falls outside the
    # window certifies a removal off a read that never happened. Arming a second
    # breakpoint and requiring it to be PRESENT in the same listing makes an empty
    # answer red.
    server.debug(command="BP F000:E05B")
    left = cast(dict[str, Any], server.debug(command="BPLIST"))
    held = [b["entry"] for b in ds.parse_breakpoints(str(left["screen_delta"]))]
    assert "BP F000:E05B" in held, (
        f"the sentinel is not in the listing, so this read examined nothing and its "
        f"verdict about the removal is worth nothing: {held}")
    assert f"BP {seg:04X}:{off:04X}" not in held, held


#: How many frames a guest is given, a slice at a time, to be loaded into the MCB chain.
BOOT_SLICE_FRAMES = 10
BOOT_SLICES_MAX = 6


def test_machine_map_is_honest_before_dos_and_finds_the_guest_after(tmp_path: Path) -> None:
    """At the park `start` leaves, DOS has not booted, so the chain is ABSENT with the
    debugger's own sentence rather than an empty list; a few frames later the guest's program
    is a block of the chain, the descriptor lists are there exactly when the mode is not
    real, and the console still answers a command after the paged listings (`Q` left the
    input line empty)."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.machine_map())
    assert park["status"] == "ok" and "mcbs" not in park, park
    assert "DOS kernel is inactive" in park["coverage_note"], park["coverage_note"]
    assert park["cpu"]["cr0"] and park["bios_mem"], park
    program = Path(GUEST_PROGRAM).stem.upper()
    for _ in range(BOOT_SLICES_MAX):
        assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
        booted = cast(dict[str, Any], server.machine_map())
        assert booted["status"] == "ok", booted
        if program in {b["filename"] for b in booted.get("mcbs", [])}:
            break
    assert program in {b["filename"] for b in booted["mcbs"]}, booted["mcbs"]
    assert ("gdt" in booted) == (booted["cpu_mode"] != "real"), booted["coverage_note"]
    assert booted["counts"]["mcbs"] == len(booted["mcbs"]) and booted["sources"]["mcbs"]
    after = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert ds.BPLIST_HEADER in after["screen_delta"] \
        and "not recognized" not in after["screen_delta"], after["screen_delta"][-200:]


def test_palette_reads_the_dac_before_and_after_the_bios_sets_it(tmp_path: Path) -> None:
    """At the park no video mode is set and the DAC is all zero; once the guest runs in a text
    mode the BIOS has loaded its standard set, whose entry 1 is blue (00, 00, 2A). The picture
    comes back as the file it names, the console still answers a command after the paged
    `VGA DACPAL`, and an entry past the DAC is refused before anything is typed."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.palette())
    assert park["status"] == "ok" and park["entries"] == 256, park
    assert set(park["rgb"]) == {"000000"}, park["rgb"][:4]
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    dest = tmp_path / "dac.png"
    one = cast(dict[str, Any], server.palette(first=1, count=1, dest=str(dest)))
    assert one["status"] == "ok", one
    assert one["rgb"] == ["00002a"] and one["colors"] == ["#0000aa"], one
    assert one["image"]["path"] == str(dest) and dest.stat().st_size > 0
    after = cast(dict[str, Any], server.debug(command="BPLIST"))
    assert ds.BPLIST_HEADER in after["screen_delta"] \
        and "not recognized" not in after["screen_delta"], after["screen_delta"][-200:]
    bad = cast(dict[str, Any], server.palette(first=256))
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", bad


def test_screen_view_reads_the_text_the_guest_was_launched_from(tmp_path: Path) -> None:
    """Before the BIOS sets a mode there is no screen to read, and the refusal names the mode and
    the capture route; once the guest runs in text, the line DOS echoed to launch it is on the
    screen, the cursor is on it, and the same screen folds to the same number twice."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    park = cast(dict[str, Any], server.screen_view())
    assert park["status"] == "INVALID" and park["code"] == "no_channel", park
    assert "`M_ERROR`" in park["message"] and "capture_frame" in park["message"]
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    view = cast(dict[str, Any], server.screen_view())
    assert view["status"] == "ok" and view["source"] == "text", view
    assert (view["width"], view["height"]) == (80, 25)
    program = Path(GUEST_PROGRAM).name.upper()
    assert program and any(row.upper().endswith(program) for row in view["text"]), view["text"]
    launched = next(i for i, row in enumerate(view["text"]) if row.upper().endswith(program))
    assert view["cursor"] == [0, launched + 1], (view["cursor"], view["text"])
    one = cast(dict[str, Any], server.screen_signature())
    two = cast(dict[str, Any], server.screen_signature())
    assert one["status"] == two["status"] == "ok", (one, two)
    assert one["signature"] == two["signature"] and one["source"] == "text"
    bad = cast(dict[str, Any], server.screen_view(dest=str(tmp_path / "text.png")))
    assert bad["status"] == "INVALID" and bad["code"] == "bad_argument", bad


def test_screen_wait_runs_until_the_launch_line_is_on_screen(tmp_path: Path) -> None:
    """From the park, where no mode is set, the wait runs retrace by retrace until DOS has echoed
    the guest's launch line, and stops there; a string the guest never prints expires with what
    it examined."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    program = Path(GUEST_PROGRAM).name.upper()
    found = cast(dict[str, Any], server.screen_wait(text=program, seconds=120))
    assert found["status"] == "ok" and found["already"] is False, found
    assert found["polls"] >= 1 and found["line"].upper().endswith(program), found
    assert found["registers"] and "stop_seq" in found
    again = cast(dict[str, Any], server.screen_wait(text=program, seconds=5))
    assert again["status"] == "ok" and again["already"] is True and again["polls"] == 0, again
    gone = cast(dict[str, Any], server.screen_wait(text="NO GUEST PRINTS THIS", seconds=3))
    assert gone["status"] == "INVALID" and gone["code"] == "wait_expired", gone
    assert gone["polls"] >= 1 and any(program in row.upper() for row in gone["text"]), gone


def test_interrupt_vectors_places_the_dos_handler_and_leaves_no_file(tmp_path: Path) -> None:
    """Once DOS runs, INT 21h points into a block one of the listings holds and the table is
    every vector; the file the debugger wrote is gone from the working directory, and one
    planted there is refused and left alone. Without a logfile the table still comes back,
    in the mode `status` reports, and no vector has a holder."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    one = cast(dict[str, Any], server.interrupt_vectors(number=0x21))
    assert one["status"] == "ok" and len(one["vectors"]) == 1, one
    row = one["vectors"][0]
    assert row["number"] == 0x21 and row["addr"] != "0000:0000", row
    assert any(k in row for k in ("mcbs", "kern", "bios_mem")), one["coverage_note"]
    whole = cast(dict[str, Any], server.interrupt_vectors())
    assert whole["status"] == "ok" and len(whole["vectors"]) == 256
    left = Path(CWD) / ds.INTVEC_FILE
    assert not left.exists(), "the server's own file is removed"
    left.write_text("planted by the live case")
    try:
        refused = cast(dict[str, Any], server.interrupt_vectors())
        assert refused["code"] == "bad_argument" and left.read_text() == "planted by the live case"
    finally:
        left.unlink()
    server.close()
    start_ok(seconds=120)
    assert server.run_for(frames=BOOT_SLICE_FRAMES)["verdict"] == "ELAPSED"
    bare = cast(dict[str, Any], server.interrupt_vectors(number=0x21))
    mode = status_mode()
    assert bare["status"] == "ok" and mode is not None and bare["cpu_mode"] == mode, bare
    assert ("linear" in bare["vectors"][0]) == (mode == "real"), bare
    assert "logfile" in bare["coverage_note"] and not any(
        k in bare["vectors"][0] for k in ("mcbs", "kern", "bios_mem")), bare


def status_mode() -> Any:
    return cast(dict[str, Any], server.status()).get("cpu_mode")


def test_run_for_lands_its_retraces_and_the_pane_clock_says_how_far() -> None:
    """Frames are the debugger's retraces, and the known answer is the display's own rate: the
    probe guest's text mode refreshes at 70 Hz, so two frames move the pane's emulated clock
    by two of its periods. The first call starts at the park, whose first retrace comes
    part of a period in, which is why the rate is judged on the second. A timed run lands on
    the first retrace at or past its mark, so it overshoots by under one period."""
    start_ok(seconds=120)
    first = cast(dict[str, Any], server.run_for(frames=3))
    assert first["status"] == "ok", first
    assert first["verdict"] == "ELAPSED" and first["polls"] == 3 and first["running"] is False
    assert first["emulated_after_s"] > first["emulated_before_s"], first
    second = cast(dict[str, Any], server.run_for(frames=2))
    assert second["status"] == "ok" and second["verdict"] == "ELAPSED", second
    moved = second["emulated_after_s"] - second["emulated_before_s"]
    assert moved == pytest.approx(2 / 70, rel=0.2), f"two retraces moved the clock {moved} s"
    at = second["stopped_at"]
    assert server.status()["pc"] == f"{at['cs']}:{at['eip']}", "status names this stop"
    asked_ms = 50
    timed = cast(dict[str, Any], server.run_for(milliseconds=asked_ms))
    assert timed["status"] == "ok" and timed["verdict"] == "ELAPSED", timed
    covered = timed["emulated_after_s"] - timed["emulated_before_s"]
    assert asked_ms / 1000 <= covered < asked_ms / 1000 + 1 / 70, f"{covered} s landed"
    refused = cast(dict[str, Any], server.debug(command="VRT"))
    assert refused["code"] == "bad_argument" and "run_for" in refused["message"], refused


def test_disassemble_decodes_what_memory_holds_and_names_the_probes_calls(
        tmp_path: Path) -> None:
    """The probe's `start` decoded on the host: every line's bytes are the bytes `read_memory`
    reads there, the debugger's own pane after `C` starts its lines at the same addresses with
    the same bytes, and with `probe.sym` loaded the two calls name `emit` and `bump` and the
    counter's operand names `cnt` one byte in. A length the tool does not take is refused
    before anything is read."""
    start_ok(seconds=180, logfile=str(tmp_path / "guest.log"))
    parked = cast(dict[str, Any], server.run_for(frames=1))
    assert parked["status"] == "ok" and parked["stopped_at"]["eip"] == "00000106", parked
    loaded = cast(dict[str, Any], server.symbols_load(source=str(_OWN / "probe.sym"),
                                                      base="8140"))
    assert loaded["status"] == "ok", loaded
    got = cast(dict[str, Any], server.disassemble(ref="start", length=16))
    assert got["status"] == "ok" and got["code_bits"] == 16, got
    listed = [(ln.split()[0], ln.split()[1]) for ln in got["lines"]]
    raw = cast(dict[str, Any], server.read_memory(ref="0814:010B", length=16))["hex"]
    assert "".join(b for _a, b in listed).upper().startswith(raw.upper()), (listed, raw)
    pane = cast(dict[str, Any], server.debug(command="C 0814:010B"))["screen_delta"]
    shown = {f"{p.segment}:{p.offset:08X}": p.data for p in code.pane_lines(pane)}
    assert all(shown.get(a) == bytes.fromhex(b) for a, b in listed), (listed, shown)
    named = {(r["line"], r["kind"]): (r["symbol"], r["delta"]) for r in got["resolved"]}
    assert named[(1, "target")] == ("emit", 0) and named[(2, "target")] == ("bump", 0)
    assert named[(3, "memory")] == ("cnt", 1), named
    refused = cast(dict[str, Any], server.disassemble(ref="start", length=0))
    assert refused["code"] == "bad_argument", refused


def test_comments_follow_the_symbol_one_per_place_and_round_trip_through_a_file(
        tmp_path: Path) -> None:
    """On the probe with `probe.sym` at 8140: a comment by `start` lands where `symbols_find`
    places it, `0824:000B` (the same byte) replaces its text and keeps its ref, `status` counts
    no comment as a declaration, and the file `comment_save` writes is the one `comment_load`
    reads back into a second save byte for byte. Every comment made here is deleted again, so
    the probe conf's store is left as it was found."""
    start_ok(seconds=120, logfile=str(tmp_path / "guest.log"))
    assert cast(dict[str, Any], server.run_for(frames=1))["status"] == "ok"
    assert cast(dict[str, Any], server.symbols_load(source=str(_OWN / "probe.sym"),
                                                    base="8140"))["status"] == "ok"
    held = {c["ref"] for c in cast(dict[str, Any], server.comment_list())["comments"]}
    assert not held & {"start", "0814:0106"}, f"the store already comments these: {held}"
    counted = cast(dict[str, Any], server.status())["declarations"]
    linear = cast(dict[str, Any], server.symbols_find(name="start"))["symbols"][0]["linear"]
    added = cast(dict[str, Any], server.comment_add(ref="start", text="entry"))
    assert added["status"] == "ok" and added["comment"]["linear"] == f"{linear:08X}", added
    aliased = cast(dict[str, Any], server.comment_add(ref="0824:000B", text="entry, aliased"))
    assert aliased["comment"]["ref"] == "start", aliased
    assert [r["text"] for r in aliased["replaced_comments"]] == ["entry"], aliased
    assert cast(dict[str, Any], server.status())["declarations"] == counted
    first, second = tmp_path / "a.comments.tsv", tmp_path / "b.comments.tsv"
    try:
        saved = cast(dict[str, Any], server.comment_save(dest=str(first)))
        assert saved["status"] == "ok", saved
        assert "start\t\t" in first.read_text(encoding="utf-8")
        assert cast(dict[str, Any], server.comment_delete(ref="start"))["status"] == "ok"
        loaded = cast(dict[str, Any], server.comment_load(source=str(first)))
        assert loaded["status"] == "ok" and loaded["added_total"] == 1, loaded
        assert cast(dict[str, Any], server.comment_save(dest=str(second)))["status"] == "ok"
        assert first.read_bytes() == second.read_bytes()
    finally:
        for ref in {c["ref"] for c in cast(dict[str, Any], server.comment_list())["comments"]} \
                - held:
            server.comment_delete(ref=ref)


def test_call_stack_at_the_probes_settle_loop_lists_the_stop_and_why_it_ended(
        tmp_path: Path) -> None:
    """The probe keeps no frame pointer, so the walk at its settle `loop` has the stop as its
    row 0 and whatever its BP leads to, says why it ended and is marked heuristic; the code
    guest's frames are section M's known answers."""
    start_ok(seconds=120, logfile=str(tmp_path / "guest.log"))
    parked = cast(dict[str, Any], server.run_for(frames=1))
    assert parked["status"] == "ok", parked
    got = cast(dict[str, Any], server.call_stack())
    assert got["status"] == "ok" and got["heuristic"] is True, got
    assert got["calls"][0]["addr"] == f"{parked['stopped_at']['cs']}:" \
        f"{parked['stopped_at']['eip']}" and got["ended_why"], got


def test_trace_executes_the_count_it_was_asked_and_hands_the_log_over(tmp_path: Path) -> None:
    """At the probe guest's settle loop `loop` takes one off ECX per instruction it executes,
    so a trace of n instructions there moves ECX by exactly n: the guest's own arithmetic, not
    the emulator's account of it. The file holds n + 1 lines, the last the instruction it
    stopped at; nothing is left in the working directory; `debug` refuses the `LOG` family."""
    start_ok(seconds=180)
    parked = cast(dict[str, Any], server.run_for(frames=2))
    assert parked["status"] == "ok" and parked["stopped_at"]["eip"] == "00000106", parked
    ecx = int(parked["registers"]["ECX"], 16)
    assert ecx > 16, "the settle loop has room for the whole trace"
    dest = tmp_path / "settle.trace"
    got = cast(dict[str, Any], server.trace(instructions=16, shape="cs_ip", dest=str(dest)))
    assert got["status"] == "ok" and got["verdict"] == "ELAPSED", got
    assert got["trace"]["instructions"] == 16 and got["trace"]["addresses"] == 1, got["trace"]
    assert int(got["registers"]["ECX"], 16) == ecx - 16, (ecx, got["registers"])
    assert len(dest.read_bytes().splitlines()) == 17
    assert not any((Path(CWD) / n).exists() for n in ("LOGCPU.TXT", "logcpu.txt"))
    refused = cast(dict[str, Any], server.debug(command="LOG 10"))
    assert refused["code"] == "bad_argument" and "`trace`" in refused["message"], refused


def test_run_to_arrives_at_an_aliased_real_mode_spelling_of_the_same_byte() -> None:
    """MANY SEG:OFF PAIRS NAME ONE BYTE IN REAL MODE, and the symbol layer arms through the
    load paragraph while the CPU stops with the program's own CS:IP. The breakpoint is armed
    one paragraph DOWN from the address the machine will stop at (`seg-1:off+16`, the same
    linear byte): the debugger fires it -- so it matches the linear address -- and the reply
    must read `arrived`, with `stopped_at` in the CPU's spelling and the breakpoint removed.
    Seen red with the string compare: "stopped elsewhere", breakpoint left armed."""
    start_ok(seconds=120)
    seg, off = a_return_address_in_ram()
    alias = f"{seg - 1:04X}:{off + 16:04X}"
    reply = cast(dict[str, Any], server.run_to(ref=alias, seconds=30, control="0000:0001"))
    assert reply["status"] == "ok" and reply["target"] == alias, reply
    assert reply["arrived"] is True, reply
    assert reply["stopped_at"]["cs"] == f"{seg:04X}", reply      # the CPU's own spelling
    assert int(reply["stopped_at"]["eip"], 16) == off, reply
    assert reply["breakpoint_removed"] is True, reply


def test_a_bound_that_expires_reports_a_running_machine_and_an_armed_breakpoint(
        ) -> None:
    """THE NEGATIVE, on the same tool, in the same session shape.

    Without it "arrived" and "the harness never looked" print the same `ok`. The
    address is one the boot does not execute, and the wait is short, so the bound is
    reached rather than waited out -- and the reply must then say BOTH things that are
    true: the machine is running, and the breakpoint could not be taken away because
    the debugger is no longer listening.
    """
    start_ok(seconds=90)
    # Into the program first, so the BIOS has filled the vector table and the timer
    # handler, read off it, is a control that fires whatever the program does.
    seg, off = a_return_address_in_ram()
    into = cast(dict[str, Any], server.run_to(ref=f"{seg:04X}:{off:04X}", seconds=30,
                                              control="0000:0001"))
    assert into["arrived"] is True, into
    hot = a_hot_address()
    assert hot != "0000:0000", "the vector table is filled once the BIOS ran"
    reply = cast(dict[str, Any], server.run_to(ref="0000:0001", seconds=3, control=hot))
    assert reply["status"] == "ok", reply
    assert reply["control"]["hits"] > 0, "the timer handler fired: the silence is a measurement"
    assert reply["arrived"] is False and reply["bound_expired"] is True, reply
    # MEASURED with the control: at the bound the machine is at rest ON the control (the
    # last hit was not released again), so `running` is false and `stopped_at` is the
    # control's address; the target's breakpoint stays armed either way.
    assert reply["running"] is False and reply["stopped_at"]["cs"] == hot[:4], reply
    assert reply["breakpoint_removed"] is False, reply
    assert "still armed" in str(reply["note"]).lower(), reply

def test_e9_wait_answers_a_line_that_had_already_gone_past(tmp_path: Path) -> None:
    """THE QUERY HALF, against a real guest. The boot trace fires within a second of the
    program starting, so by the time this asks it is HISTORY -- and a tool that only
    waited would sit out its whole bound and then report that it never happened."""
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log_wait(channel="guest", pattern=GUEST_MARK, seconds=30))
    assert reply["status"] == "ok", reply
    assert reply["already"] is True, reply
    assert reply["waited_s"] == 0.0, reply
    assert GUEST_MARK in str(reply["line"]), reply
    assert cast(int, reply["lines_examined"]) > 5, reply


def test_e9_wait_really_waits_for_a_line_that_has_not_happened_yet(
        tmp_path: Path) -> None:
    """THE WAIT HALF, and it must REQUIRE the wait, not accept either outcome.

    The first version branched on `already` and asserted something in each arm -- and
    both assertions were entailed by the field they branched on (`already: False` is
    produced at one site that always sets a measured `waited_s` past one poll;
    `already: True` at one site that sets the literal 0.0). So it could not fail on the
    property it is named for, and if the guest happened to have logged the line already
    it passed through the other arm having measured NOTHING, with nobody told.

    IT ESTABLISHES ITS OWN PRECONDITION instead: `e9` must report the pattern is not
    there YET. If it already is, this window cannot demonstrate a wait, and that is
    INVALID rather than a pass. There is a small race between that check and the call --
    if the line lands in between, this goes RED, which is the acceptable direction.
    """
    # A LATE milestone of this guest's own boot, asked for while the guest is still
    # early in it, so the wait here is for the FIRST line only. `e9` is the control: it
    # says whether there is anything to wait for.
    a_running_guest_that_has_logged(tmp_path, seconds=180, lines=1)
    late = GUEST_LATE
    before = cast(dict[str, Any], server.log(channel="guest", pattern=late, limit=1))
    assert before["status"] == "ok", before
    assert before["lines_total"] == 0, (
        f"{late!r} had ALREADY been logged {before['lines_total']} time(s) before this "
        f"asked, so this window cannot demonstrate a wait at all: INVALID, not a pass")

    reply = cast(dict[str, Any], server.log_wait(channel="guest", pattern=late, seconds=120))
    assert reply["status"] == "ok", reply
    assert reply["already"] is False, reply
    assert 0.0 < cast(float, reply["waited_s"]) < 120.0, reply
    assert cast(int, reply["arrived_during"]) > 0, reply


def test_e9_wait_says_a_bound_expired_rather_than_answering_nothing(
        tmp_path: Path) -> None:
    """INVALID, not an empty answer, and the message names what it examined -- against a
    real channel that really has instrumentation in it, which is the only way to show
    the refusal is about the BOUND and not about the channel."""
    a_running_guest_that_has_logged(tmp_path)

    reply = cast(dict[str, Any], server.log_wait(
        channel="guest", pattern="a_string_this_guest_will_never_log", seconds=3))
    assert reply["status"] == "INVALID", reply
    assert "expired" in reply["message"], reply
    # THE TWO COUNTS ARE DIFFERENT FACTS and the refusal must give both: what arrived
    # DURING the window, and what the log holds altogether. Reporting the second under
    # the first's name read, to anyone diagnosing a silent guest, as a live channel.
    assert "arrived DURING the wait" in reply["message"], reply
    assert "in the log altogether" in reply["message"], reply


def test_write_lands_in_ram_and_is_read_back_and_a_write_into_rom_is_refused() -> None:
    """The readback on the real debugger: bytes written into RAM come back as sent,
    `verified: true`, and every later reply carries `altered` from the first write on. A
    write into the BIOS ROM is refused before anything is sent, and the emulator is still
    there afterwards: measured, `SM` into that range ends the emulator, exit code 1."""
    start_ok(seconds=60)
    ram = cast(dict[str, Any], server.write(ref="0040:0100", data_hex="1234abcd"))
    assert ram["status"] == "ok" and ram["verified"] is True, ram
    assert ram["readback"] == "1234abcd" and ram["written"] == 4
    assert ram["session"]["altered"] is True
    rows = cast(dict[str, Any], server.read_memory(ref="0040:0100"))["rows"]
    assert rows[0].split()[1:5] == ["12", "34", "AB", "CD"], rows[0]
    rom = cast(dict[str, Any], server.write(ref="F000:E05B", data_hex="99"))
    assert rom["status"] == "INVALID" and "ENDS the emulator" in rom["message"], rom
    assert cast(dict[str, Any], server.status())["session"]["alive"] is True


#: A byte of the BIOS data area's inter-application block (0040:00F0), free for a test to own.
_MARK_AT = "0000:000004F0"


def _byte_at(ref: str) -> str:
    reply = cast(dict[str, Any], server.read_memory(ref=ref, length=1))
    assert reply["status"] == "ok", reply
    return str(reply["hex"]).upper()


def test_states_round_trip_headless_through_the_debugger_commands(tmp_path: Path) -> None:
    """A state saved and loaded with no window, by the debugger's own SAVESTATE and LOADSTATE
    (a build that carries them: `DOSBOX_X_BINARY` the fork's; any other is BLOCKED here, by
    its own refusal). The known answer is a byte: written AA, saved, written 55 (the control,
    read back as 55), loaded, read back AA. Parked, the machine stays parked; running, it is
    stopped for the command and released again (`paused`), and `stop` still reaches it."""
    state_dir = tmp_path / "states"
    started = cast(dict[str, Any], server.start(
        conf=str(conf_that_does_not_exit(tmp_path)), cwd=CWD, seconds=120,
        program=GUEST_PROGRAM, logfile=str(tmp_path / "e9.log"), state_dir=str(state_dir)))
    assert started["status"] == "ok", started
    empty = cast(dict[str, Any], server.state_list())
    assert empty["status"] == "ok" and empty["states"] == [], empty
    missing = cast(dict[str, Any], server.state_load(name="live"))
    assert missing["status"] == "INVALID" and missing["code"] == "unknown_ref", missing
    assert server.write(ref=_MARK_AT, data_hex="AA")["verified"] is True
    saved = cast(dict[str, Any], server.state_save(name="live"))
    if saved.get("code") == "no_channel":
        pytest.skip(f"this DOSBox-X carries no SAVESTATE: {saved['message']}")
    assert saved["status"] == "ok" and saved["paused"] is False, saved
    assert Path(str(saved["path"])) == state_dir / "live.sav"
    assert saved["program"] and saved["time_stamp"] and saved["version"].startswith("DOSBox-X")
    assert server.write(ref=_MARK_AT, data_hex="55")["verified"] is True
    assert _byte_at(_MARK_AT) == "55", "the control: the byte changed after the save"
    loaded = cast(dict[str, Any], server.state_load(name="live"))
    assert loaded["status"] == "ok" and loaded["paused"] is False, loaded
    assert loaded["session"]["altered"] is True
    assert _byte_at(_MARK_AT) == "AA", "the load brought the saved machine back"
    released = cast(dict[str, Any], server.resume())
    assert released["halted"] is False, released
    running = cast(dict[str, Any], server.state_save(name="running"))
    assert running["status"] == "ok" and running["paused"] is True, running
    again = cast(dict[str, Any], server.state_load(name="running"))
    assert again["status"] == "ok" and again["paused"] is True, again
    shot = cast(dict[str, Any], server.snapshot(dest=str(tmp_path / "shot.png")))
    assert shot["status"] == "ok" and (tmp_path / "shot.png").stat().st_size > 0, shot
    listed = cast(dict[str, Any], server.state_list())
    names = sorted(str(s["name"]) for s in cast(list[dict[str, Any]], listed["states"]))
    assert names == ["live", "running"], listed
    back = cast(dict[str, Any], server.stop())
    assert back["status"] == "ok" and back["interrupted"] is True, back


# ------------------------------------------------------------- searching memory

def test_find_locates_the_bytes_a_dump_of_the_same_range_starts_with(tmp_path: Path) -> None:
    """Through the tool, against the range `memdump`'s case measured as holding 26 distinct
    values: the first four bytes of a dump of it are searched for, so the expected hit is
    KNOWN from the machine and not reasoned, and a pattern LONGER than the range is the
    refusal that proves the tool looked at its arguments before the debugger."""
    start_ok(seconds=90)
    dest = tmp_path / "range.bin"
    dump = cast(dict[str, Any], server.memdump(ref="F000:0000E000", length=256, dest=str(dest)))
    assert dump["status"] == "ok", dump
    head = dest.read_bytes()[:4].hex()
    reply = cast(dict[str, Any], server.find(ref="F000:0000E000", length=256, data_hex=head))
    assert reply["status"] == "ok", reply
    assert reply["hits"][0] == "F000:0000E000" and reply["hits_total"] >= 1, reply
    assert reply["truncated"] is False
    left = [p for p in cast(ds.Session, dstate.STATE.session)._memdump_candidates()
            if p.exists()]
    assert not left, f"the search left its dump behind at {left}"
    short = cast(dict[str, Any], server.find(ref="F000:0000E000", length=2, data_hex=head))
    assert short["status"] == "INVALID" and short["code"] == "bad_argument", short


def test_scan_narrows_to_every_zero_cell_and_closes_once() -> None:
    """The debugger's own scanner, driven end to end over the range `memdump`'s case
    measured as holding ONE value at the reset vector (`0000:0400`, the BIOS data area,
    all zero), so every count below is known from the machine: 256 candidates, 256
    survivors of `= 0` listed whole across the pages the tool turns, none of `!= 0`
    (which closes the scan), a second instance refused while one is open, and a clear
    that says nothing was open. `F000:E000` is NOT used: at the reset vector the BIOS
    segment is aliased high and `MEMFIND` refuses its range (measured), which `find`
    does not mind because `MEMDUMPBIN` reads it."""
    start_ok(seconds=90)
    opened = cast(dict[str, Any], server.scan_start(ref="0000:00000400", length=256))
    assert opened["status"] == "ok", opened
    assert opened["candidates"] == 256 and opened["cell_bytes"] == 1, opened
    again = cast(dict[str, Any], server.scan_start(ref="0000:00000400", length=16))
    assert again["status"] == "INVALID" and "one is open" in again["message"], again
    kept = cast(dict[str, Any], server.scan_filter(operator="=", value=0))
    assert kept["status"] == "ok", kept
    assert kept["survivors"] == 256 and kept["closed"] is False, kept
    assert len(kept["hits"]) == 256, kept["summary"]
    assert kept["hits_total"] == 256 and kept["truncated"] is False, kept["summary"]
    assert kept["hits"][0] == {"address": "0000:00000400", "linear": "0x00000400", "value": 0}
    assert kept["hits"][-1]["address"] == "0000:000004FF"
    wide = cast(dict[str, Any], server.scan_filter(operator="=", value=0x1FF))
    assert wide["status"] == "INVALID" and "is wider than the open scan's" in wide["message"], wide
    # THE DEBUGGER'S OWN COUNT after the refused filter: a filter that does not close prints
    # it, so this is the check that a refusal did not move it, which the server's arithmetic
    # on the close could not show.
    again = cast(dict[str, Any], server.scan_filter(operator="=", value=0))
    assert again["iterations"] == kept["iterations"] + 1, (kept["iterations"], again)
    gone = cast(dict[str, Any], server.scan_filter(operator="!", value=0))
    assert gone["status"] == "ok" and gone["closed"] is True and gone["survivors"] == 0, gone
    # THE CLOSING LINE CARRIES NO COUNT, so the server's own: one past the last it read (the
    # refused filter above reached no count).
    assert gone["iterations"] == again["iterations"] + 1, (again["iterations"], gone)
    nothing = cast(dict[str, Any], server.scan_clear())
    assert nothing["status"] == "ok" and nothing["cleared"] is False, nothing
    orphan = cast(dict[str, Any], server.scan_filter(operator="=", value=0))
    assert orphan["status"] == "INVALID" and "scan_start" in orphan["message"], orphan
    reopened = cast(dict[str, Any], server.scan_start(ref="0000:00000400", length=16))
    assert reopened["status"] == "ok", reopened
    cleared = cast(dict[str, Any], server.scan_clear())
    assert cleared["status"] == "ok" and cleared["cleared"] is True, cleared


def test_a_filter_with_no_value_compares_with_the_scan_as_it_opened() -> None:
    """`!` with no value is "changed since the scan OPENED", not since the previous filter:
    of two cells, the one changed once and then left alone keeps passing `!`, and written
    back to its opening value it stops, which closes the scan. The cells are free RAM at the
    reset vector, written here, so every value is known."""
    start_ok(seconds=90)
    assert server.write(ref="0050:0200", data_hex="1111111122222222")["verified"] is True
    opened = cast(dict[str, Any], server.scan_start(ref="0050:0200", length=8, width="dword"))
    assert opened["candidates"] == 2, opened
    server.write(ref="0050:0200", data_hex="33333333")
    once = cast(dict[str, Any], server.scan_filter(operator="!"))
    assert once["survivors"] == 1 and once["hits"][0]["address"] == "0050:00000200", once
    still = cast(dict[str, Any], server.scan_filter(operator="!"))
    assert still["survivors"] == 1 and still["iterations"] == once["iterations"] + 1, still
    server.write(ref="0050:0200", data_hex="11111111")
    back = cast(dict[str, Any], server.scan_filter(operator="!"))
    assert back["closed"] is True and back["survivors"] == 0, back
    assert back["iterations"] == still["iterations"] + 1, back
