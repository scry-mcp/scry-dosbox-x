"""Whether the program the guest was running is still the one DOS runs: the owner of the current
PSP, read off the debugger's `DOS MCBS` listing, and the fault DJGPP leaves on the text screen."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from channel_double import Machine, protected, session_over

from scry_dosbox_x import program
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate

# `DOS MCBS` as the scry build prints it with ReChip running (PSP 08DD), as measured.
RUNNING = """MCB Seg  Size (bytes)  PSP Seg (notes)  Filename
Conventional memory:
   0450         10992     0008 (DOS)    \u0002
   0700          2464     0701          COMMAND
   079B           720     0701          COMMAND
   07C9          1168     0814          SCRY
   0813          2016     0814          SCRY
   0892          1168     08DD          RECHIPD
   08DC         16640     08DD          RECHIPD
   0CED        164128     08DD          RECHIPD
   3500          4096     08DD          RECHIPD
   3601        434128     0000 (free)   +
   9FFF  END OF CHAIN
Upper memory:
   9FFF        180224     0008 (DOS)    SC
   CC00            96     08DD          RECHIPD
   CC07          1056     0000 (free)   $P$G
   CC4A         44304     CC4B          CWSDPMI
   D71C         36400     0000 (free)
   E000  END OF CHAIN"""
#: The same chain with a second command interpreter, the one the program started (a DOS shell).
WITH_A_CHILD_SHELL = RUNNING + "\n   0D00          2464     0D01          COMMAND"

FAULT = ["Exiting due to signal SIGSEGV", "Page fault at eip=0004e0a2, error=0004",
         "eax=00000000 ebx=00000000 ecx=00000000 edx=00000000", "Call frame traceback EIPs:",
         "  0x0004e0a2", "  0x00012345"]

GONE = {"state": "fault", "name": "RECHIPD", "seen_by": "DOS's current process is COMMAND "
        "(PSP 0701), no longer RECHIPD", "fault": FAULT}


class Reads:
    """The readings `observe` is given, counting each."""

    def __init__(self, listing: str = RUNNING, rows: list[str] | None = None) -> None:
        self.listing, self.rows, self.listed, self.shown = listing, rows, 0, 0

    def mcbs(self) -> str:
        self.listed += 1
        return self.listing

    def screen(self) -> list[str] | None:
        self.shown += 1
        return self.rows

    def see(self, watch: program.Watch, psp: int | None, expected: str | None = None,
            ran: bool = False) -> None:
        program.observe(watch, psp, self.mcbs, self.screen, expected, lambda: ran)


def test_the_owner_of_each_psp_is_read_off_its_own_block() -> None:
    got = program.owners(RUNNING)
    assert got == {0x701: "COMMAND", 0x814: "SCRY", 0x8DD: "RECHIPD", 0xCC4B: "CWSDPMI"}, got


@pytest.mark.parametrize("name", ["A&B", "#1", "(X)", "A-B", "~TMP", "X$"])
def test_a_name_is_read_whole_with_every_character_dos_allows_in_one(name: str) -> None:
    assert program.owners(f"   0892  1168  08DD          {name}") == {0x8DD: name}


def test_a_program_that_never_ran_is_not_reported_gone() -> None:
    watch, reads = program.Watch(), Reads()
    reads.see(watch, 0x701)
    assert program.block(watch) is None and reads.shown == 0


def test_a_running_program_is_not_reported_and_its_listing_is_read_once_per_psp() -> None:
    watch, reads = program.Watch(), Reads()
    for psp in (0x8DD, 0x8DD, 0x8DD):
        reads.see(watch, psp)
    assert program.block(watch) is None and reads.listed == 1, (reads.listed, program.block(watch))


def test_the_program_returning_to_the_shell_reads_as_exited_not_as_a_fault() -> None:
    watch, reads = program.Watch(), Reads(rows=["C:\\>X87.COM", "C:\\>"])
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    got = program.block(watch)
    assert got is not None and got["state"] == "exited" and got["name"] == "RECHIPD", got
    assert "fault" not in got and "0701" in got["seen_by"] and "COMMAND" in got["seen_by"], got


def test_a_dying_program_that_leaves_djgpps_fault_text_has_it_quoted() -> None:
    watch = program.Watch()
    reads = Reads(rows=["C:\\>RECHIPD.EXE", "", *FAULT, "", "C:\\>"])
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    got = program.block(watch)
    assert got is not None and got["state"] == "fault", got
    assert got["fault"] == FAULT, got


def test_a_fault_text_left_by_an_earlier_program_is_not_laid_on_a_later_one() -> None:
    """The screen still holds A's text above the row that ran B, which exited cleanly."""
    watch = program.Watch()
    listing = RUNNING.replace("RECHIPD", "B      ")
    reads = Reads(listing=listing, rows=[*FAULT, "C:\\>B", "hello", "C:\\>"])
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    got = program.block(watch)
    assert got is not None and got["state"] == "exited" and "fault" not in got, got


def test_a_program_that_prints_a_fault_words_mid_line_is_not_a_fault() -> None:
    watch = program.Watch()
    reads = Reads(rows=["C:\\>RECHIPD.EXE", "the log says Page fault at 3", "C:\\>"])
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    got = program.block(watch)
    assert got is not None and got["state"] == "exited", got


def test_the_exit_is_judged_once_and_the_screen_is_read_once() -> None:
    watch, reads = program.Watch(), Reads(rows=FAULT)
    reads.see(watch, 0x8DD)
    for _ in range(3):
        reads.see(watch, 0x701)
    assert reads.shown == 1, reads.shown


def test_a_screen_that_cannot_be_read_still_says_the_program_exited() -> None:
    watch, reads = program.Watch(), Reads(rows=None)
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    got = program.block(watch)
    assert got is not None and got["state"] == "exited" and "fault" not in got, got


def test_a_program_started_after_the_exit_clears_it() -> None:
    watch, reads = program.Watch(), Reads(rows=FAULT)
    reads.see(watch, 0x8DD)
    reads.see(watch, 0x701)
    assert program.block(watch) is not None
    reads.see(watch, 0x8DD)
    assert program.block(watch) is None


def test_an_unreadable_listing_or_psp_changes_nothing() -> None:
    watch, reads = program.Watch(), Reads(listing="")
    reads.see(watch, 0x8DD)
    reads.see(watch, None)
    reads.see(watch, 0)
    assert program.block(watch) is None and watch.running is None


def test_a_command_interpreter_the_program_started_is_not_the_program_ending() -> None:
    """A DOS shell the program opened owns a PSP named COMMAND too; the program is suspended."""
    watch, reads = program.Watch(), Reads(listing=WITH_A_CHILD_SHELL, rows=None)
    reads.see(watch, 0x8DD)
    reads.see(watch, 0xD01)
    assert program.block(watch) is None, program.block(watch)
    reads.see(watch, 0x701)
    assert program.block(watch) is not None


def test_the_stub_loaded_by_the_start_is_not_the_program_that_ended() -> None:
    watch, reads = program.Watch(), Reads()
    reads.see(watch, 0x814)
    reads.see(watch, 0x701)
    assert program.block(watch) is None and watch.running is None


def test_only_the_program_the_start_launched_counts_as_the_program() -> None:
    watch, reads = program.Watch(), Reads()
    reads.see(watch, 0xCC4B, expected="RECHIPD")
    reads.see(watch, 0x701, expected="RECHIPD")
    assert program.block(watch) is None, "CWSDPMI owned DOS for a moment, it is not the program"


def test_a_program_that_died_before_any_stop_saw_it_is_known_by_what_the_start_launched() -> None:
    watch, reads = program.Watch(), Reads(rows=FAULT)
    reads.see(watch, 0x701, expected="RECHIPD", ran=True)
    got = program.block(watch)
    assert got is not None and got["name"] == "RECHIPD" and got["state"] == "fault", got


def test_a_program_that_has_not_written_yet_is_not_reported_gone() -> None:
    watch, reads = program.Watch(), Reads(rows=None)
    reads.see(watch, 0x701, expected="RECHIPD", ran=False)
    assert program.block(watch) is None and reads.shown == 0


def test_a_stop_at_the_shell_before_the_program_wrote_does_not_hide_its_later_death() -> None:
    """The first stop finds the shell and the log empty; the program then runs and dies; the next
    stop finds the same PSP, which must be read again."""
    watch, reads = program.Watch(), Reads(rows=FAULT)
    reads.see(watch, 0x701, expected="RECHIPD", ran=False)
    reads.see(watch, 0x701, expected="RECHIPD", ran=True)
    got = program.block(watch)
    assert got is not None and got["state"] == "fault", got
    assert reads.listed == 1, "the listing is read once for the PSP"


def test_a_wait_that_expired_with_the_guest_silent_leads_with_that_fact() -> None:
    got = program.lead({"verdict": "TIMEOUT", "arrived_during": 0, "waited_s": 10.0}, None)
    assert got.startswith("the guest wrote no line in the 10 s waited"), got


def test_a_note_that_already_says_the_guest_wrote_nothing_is_not_given_it_twice() -> None:
    note = "nothing matched. The guest wrote NOTHING at all in this window, so ..."
    wait = {"verdict": "TIMEOUT", "arrived_during": 0, "waited_s": 10.0, "note": note}
    assert program.lead(wait, None) == ""


def test_a_wait_that_expired_with_the_program_gone_leads_with_that_and_not_with_silence() -> None:
    got = program.lead({"verdict": "TIMEOUT", "arrived_during": 0, "waited_s": 10.0}, GONE)
    assert got.startswith("RECHIPD has ended on a fault"), got
    assert "wrote no line" not in got, got


def test_a_wait_that_expired_on_a_slow_guest_does_not_claim_it_died() -> None:
    """Lines kept arriving, so nothing in the wait says the program is gone."""
    assert program.lead({"verdict": "TIMEOUT", "arrived_during": 7, "waited_s": 10.0}, None) == ""
    assert program.lead({"verdict": "TIMEOUT", "waited_s": 10.0}, None) == ""


def test_a_stale_exit_does_not_lead_a_wait_in_which_the_guest_kept_writing() -> None:
    """The program was relaunched without a stop seeing it: seven lines arrived in the wait."""
    got = program.lead({"verdict": "TIMEOUT", "arrived_during": 7, "waited_s": 5.0}, GONE)
    assert got == "", got


def _stopped_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[str] | None,
                  ) -> tuple[ds.Session, dict[str, int]]:
    """A real `Session` over the channel double, whose `DOS MCBS` prints `RUNNING` and whose
    current PSP the case moves."""
    machine = protected(Machine())
    now = {"psp": 0x8DD}
    machine.hooks["EV"] = lambda body: (
        (True, [f"{now['psp']:x}"]) if body == "EV PSPSEG" else None)
    machine.hooks["DOS"] = lambda body: (True, RUNNING.splitlines())
    monkeypatch.setattr(ds.Session, "_text_rows", lambda self: rows)
    return session_over(machine, tmp_path), now


def _next_stop(session: ds.Session) -> None:
    session.forget_stop()
    session.mark_stopped()
    session.stop_survey()
    session.watch_program()


def test_the_session_block_carries_the_program_only_once_it_is_gone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, now = _stopped_over(tmp_path, monkeypatch, ["C:\\>RECHIPD.EXE", *FAULT, "C:\\>"])
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    assert "program" not in dstate.session_block(), dstate.session_block()
    now["psp"] = 0x701
    _next_stop(session)
    got = dstate.session_block()
    assert got["program"]["state"] == "fault" and got["program"]["fault"] == FAULT, got
    assert "program" not in dstate.process_facts(), "`status` would carry it twice"


def test_a_stop_survey_alone_reads_no_process(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A frame of a timed run is surveyed to tell a cut from a retrace; it costs no PSP read."""
    session, _ = _stopped_over(tmp_path, monkeypatch, None)
    session.stop_survey()
    sent = session.control.sent  # type: ignore[attr-defined]
    assert not any("PSPSEG" in command for command in sent), sent


def test_a_stop_whose_debugger_prints_no_psp_adds_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    machine = protected(Machine())
    machine.hooks["EV"] = lambda body: ((True, ["unknown name"]) if body == "EV PSPSEG" else None)
    session = session_over(machine, tmp_path)
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    assert "program" not in dstate.session_block(), dstate.session_block()


def test_the_note_of_a_timed_out_reply_opens_with_the_lead(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dstate.STATE, "session", None)
    flat = dstate.reply(verdict="TIMEOUT", arrived_during=0, waited_s=3.0,
                        note="nothing matched /x/ in 3s")
    assert flat["note"] == "the guest wrote no line in the 3 s waited. nothing matched /x/ in 3s"
    nested = dstate.reply(verify={"verdict": "TIMEOUT", "arrived_during": 0, "waited_s": 2.0,
                                  "note": "no new line matching the pattern"})
    opening = "the guest wrote no line in the 2 s waited. "
    assert nested["verify"]["note"].startswith(opening), nested
    hit = dstate.reply(verdict="TARGET", arrived_during=0, waited_s=3.0, note="found it")
    assert hit["note"] == "found it", hit


def test_a_note_added_after_the_reply_was_built_is_led_too(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_for` adds its verdict and note with `extend`, after `reply` ran."""
    monkeypatch.setattr(dstate.STATE, "session", None)
    built = dstate.reply(waited_s=1.0, arrived_during=0)
    got = dstate.extend(built, verdict="TIMEOUT", note="the bound ran out")
    assert got["note"] == "the guest wrote no line in the 1 s waited. the bound ran out", got


def test_a_program_that_is_gone_leads_every_expired_wait_of_the_session(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, now = _stopped_over(tmp_path, monkeypatch, FAULT)
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    now["psp"] = 0x701
    _next_stop(session)
    got = dstate.reply(verdict="TIMEOUT", arrived_during=0, waited_s=3.0, note="no stop")
    assert got["note"].startswith("RECHIPD has ended on a fault"), got


def test_a_run_to_whose_control_stayed_silent_says_the_program_is_gone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, now = _stopped_over(tmp_path, monkeypatch, FAULT)
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    now["psp"] = 0x701
    _next_stop(session)
    silent = dstate.reply(status="INVALID", code="control_silent",
                          message="the control 1000:0 never fired within 3 s")
    assert silent["message"].startswith("RECHIPD has ended on a fault"), silent
    other = dstate.reply(status="INVALID", code="cut_by_other_stop", message="another stop")
    assert other["message"] == "another stop", other


def _launched_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, log: str) -> ds.Session:
    """A session whose start ran `RECHIPD.EXE`, whose log holds `log`, stopped at the shell."""
    session, _ = _stopped_over(tmp_path, monkeypatch, FAULT)
    logfile = tmp_path / "g.log"
    logfile.write_text(log)
    session.launch = dataclasses.replace(session.launch, program="RECHIPD.EXE D:\\X.MID -a",
                                         logfile=logfile)
    return session


def test_a_stop_at_the_shell_after_a_free_run_names_the_program_the_log_shows_ran(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _launched_over(
        tmp_path, monkeypatch,
        "Bochs port E9h: [+   0.100] STUB  . scry device=present proto=6 motion=1\n"
        "Bochs port E9h: [+  11.257] PERF  . audio play=1\n")
    session.control.hooks["EV"] = lambda body: (  # type: ignore[attr-defined]
        (True, ["701"]) if body == "EV PSPSEG" else None)
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    got = dstate.session_block()["program"]
    assert got["state"] == "fault" and got["name"] == "RECHIPD", got


def test_a_log_with_only_the_stubs_lines_does_not_say_the_program_ran(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _launched_over(
        tmp_path, monkeypatch,
        "Bochs port E9h: [+   0.100] STUB  . scry device=present proto=6 motion=1\n")
    session.control.hooks["EV"] = lambda body: (  # type: ignore[attr-defined]
        (True, ["701"]) if body == "EV PSPSEG" else None)
    monkeypatch.setattr(dstate.STATE, "session", session)
    session.stop_survey()
    session.watch_program()
    assert "program" not in dstate.session_block(), dstate.session_block()
