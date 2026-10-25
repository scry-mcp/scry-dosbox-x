"""What a list of operations hands back, by the keys a caller reads: a refused list's account, the
batch files numbered per call, the final stop's enrichment when its pane is cut, the stops
account and the stop the last step surveyed, `drive`'s one shape on a refusal and its look when
the log goes, its waits (the act's, carrying the caller's progress, and its own for `expect`),
and `run_steps`' default of whole replies."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _names, clean_session  # noqa: F401
from scry_core import sequence as executor

import dosbox_running as running
import dosbox_sequence as sequence
import dosbox_session as ds
import dosbox_x_server as server


def test_a_refused_list_says_which_step_failed_and_every_refusal(tmp_path: Path) -> None:
    _names(tmp_path)
    got = cast(dict[str, Any], server.perform(steps=[{"op": "status"}, {"op": "nope"}]))
    assert got["failed_at"] == 1 and got["failed"] == got["errors"][0], got
    assert [e["op"] for e in got["errors"]] == ["nope"], got


def test_each_batch_writes_files_of_its_own(tmp_path: Path) -> None:
    _names(tmp_path)
    first = cast(dict[str, Any], server.perform(steps=[{"op": "registers"}], summaries=True))
    second = cast(dict[str, Any], server.perform(steps=[{"op": "status"}], summaries=True))
    assert Path(first["ran_path"]).name.startswith("batch-") and first["ran_path"] != \
        second["ran_path"], (first["ran_path"], second["ran_path"])
    assert Path(first["ran_path"]).read_text(encoding="ascii") != \
        Path(second["ran_path"]).read_text(encoding="ascii")
    n1 = int(Path(first["ran_path"]).name.split("-")[1].split(".")[0])
    n2 = int(Path(second["ran_path"]).name.split("-")[1].split(".")[0])
    assert n2 == n1 + 1, (n1, n2)


def test_run_steps_keeps_every_reply_whole_by_default(tmp_path: Path) -> None:
    fake = _names(tmp_path)
    got = sequence.run_steps(fake, [{"op": "registers"}], 30.0,  # type: ignore[arg-type]
                             server._step_ops())
    assert "ran_path" not in got and "regs" in got["ran"][0]["reply"], got


def test_a_final_stop_whose_pane_is_cut_keeps_the_account_and_says_why(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def cut(*_: Any, **__: Any) -> dict[str, Any]:
        raise ds.Invalid("unexpected_answer", "cut")
    monkeypatch.setattr(running, "stop_reply", cut)
    assert sequence._final_stop(cast(ds.Session, None)) == {
        "enrichment": {"available": False, "why": "cut"}}


def test_a_look_whose_log_went_says_so_in_the_guests_block() -> None:
    class Gone:
        def e9_since_mark(self, mark: int) -> list[str]:
            raise ds.Invalid("unexpected_answer", "gone")
    assert sequence._look(cast(ds.Session, Gone()), 0, ".", 10) == {
        "guest": {"available": False, "why": "gone"}}


def test_a_drive_refused_before_its_act_has_drives_whole_shape(tmp_path: Path) -> None:
    refused = sequence.drive_refused(ds.Invalid("no_channel", "no log", argument="expect"))
    assert refused.fields["argument"] == "expect", refused.fields
    assert refused.fields["act"] == {"ran": [], "steps_completed": 0,
                                     "failed": executor.none_failed(),
                                     "failed_at": executor.none_failed()}, refused.fields
    assert refused.fields["verify"] == {"checked": False,
                                        "why": "the act was refused before anything ran"}
    assert refused.fields["looked"]["available"] is False, refused.fields


def test_a_drive_whose_wait_met_a_stop_carries_its_act_and_its_look(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=True)
    fake.running = True
    fake.input_effect = None
    fake.stops_during_wait = True
    stopped = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect="key_cue_a", seconds=1))
    assert stopped["status"] == "INVALID", stopped
    assert {"act", "looked", "verify"} <= set(stopped), sorted(stopped)


def test_the_account_counts_the_stops_numbered_since_the_list_began(tmp_path: Path) -> None:
    """The stops block reads the failed step's or the tail's stop (`also`) beside the rows, and
    ends at the session's own record when that is newer, so a stop no reply surveyed is
    counted as unaccounted."""
    import dosbox_state as dstate
    _names(tmp_path)
    dstate.STATE.last_stop["seq"] = 5
    machine = sequence._Dosbox(cast(ds.Session, None), True)
    assert machine.since == 5
    dstate.STATE.last_stop["seq"] = 7
    tail = {"stop_seq": 6, "cause": "breakpoint _main (by symbol) at 00A7:00001000"}
    got = sequence.account_of([], True, False, 5, [tail])["stops"]
    assert (got["surveyed"], got["stop_seq_last"], got["unaccounted"]) == (1, 7, 1), got
    assert machine.account([], False, [tail])["stops"]["surveyed"] == 1
    dstate.STATE.last_stop.clear()
    none = sequence.account_of([], True, False, 0)["stops"]
    assert none["stop_seq_first"]["available"] is False and none["unaccounted"] == 0, none
    assert sequence._Dosbox(cast(ds.Session, None), True).since == 0


def test_a_stop_the_last_step_surveyed_is_taken_from_its_reply_and_any_other_off_the_record(
        tmp_path: Path) -> None:
    fake = _names(tmp_path)
    recorded = running.stop_reply(fake)  # type: ignore[arg-type]
    machine = sequence._Dosbox(fake, False)  # type: ignore[arg-type]
    surveys = fake.survey_calls
    own = {"stop_seq": recorded["stop_seq"], "regs": {"EAX": "0xDEAD"}}
    took = machine.rested([{"reply": own}])
    assert took is not None and took["regs"] == {"EAX": "0xDEAD"}, took
    assert fake.survey_calls == surveys, "a stop the step surveyed was surveyed again"
    other = {"stop_seq": recorded["stop_seq"] + 5, "regs": {"EAX": "0xDEAD"}}
    off_record = machine.rested([{"reply": other}])
    assert off_record is not None and off_record["stop_seq"] == recorded["stop_seq"], off_record
    assert off_record["regs"] != {"EAX": "0xDEAD"}, off_record


E9_CUE = "Bochs port E9h: [+   9.000] ACT   . key_cue_a=1 b=-1 on=1"


def _driving(tmp_path: Path) -> Any:
    fake = _names(tmp_path, watched=True)
    fake.log = ["Bochs port E9h: [+   0.000] BOOT  . start"]
    return fake


def test_a_drive_whose_act_failed_or_whose_verify_broke_still_carries_act_and_look(
        tmp_path: Path) -> None:
    fake = _driving(tmp_path)
    fake.registers_raises = True
    failed = cast(dict[str, Any], server.drive(act=[{"op": "registers"}]))
    assert failed["status"] == "INVALID" and {"act", "looked"} <= set(failed), failed
    fake.registers_raises = False
    fake.running = True
    fake.input_effect = None
    fake.wait_raises = ds.Invalid("unexpected_answer", "the log went")
    broke = cast(dict[str, Any], server.drive(act=[{"op": "send_keys", "keys": ["a"]}],
                                              expect="key_cue_a", seconds=1))
    assert broke["status"] == "INVALID" and {"act", "looked"} <= set(broke), broke


def test_a_drive_ending_running_waits_for_its_effect_and_reports_progress(
        tmp_path: Path) -> None:
    """The act leaves the guest running, so the effect is waited for (it arrives during the
    wait, not before it), and the wait's progress reaches the caller."""
    fake = _driving(tmp_path)
    fake.running = True
    fake.input_effect = None
    real_wait = fake.e9_wait

    def arriving(pattern: str, seconds: float, mark: int = 0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        progress(0.5, seconds, "waiting")
        fake.log.append(E9_CUE)
        return cast(dict[str, object], real_wait(pattern, seconds, mark, progress))
    fake.e9_wait = arriving
    said: list[str] = []
    got = sequence.drive(fake, server._step_ops(), [{"op": "send_keys", "keys": ["a"]}],
                         "key_cue_a", 2.0, ".", 10, 30.0,
                         lambda *a: said.append(str(a[-1])))
    assert got["status"] == "ok" and got["verify"]["seen"] is True, got
    assert "waiting" in " ".join(said), said


def test_a_drive_at_a_stop_does_not_count_a_line_written_before_its_mark(tmp_path: Path) -> None:
    fake = _driving(tmp_path)
    fake.log.append(E9_CUE)                  # the cue, written before the act's mark
    got = cast(dict[str, Any], server.drive(act=[{"op": "status"}], expect="key_cue_a"))
    assert got["status"] == "INVALID" and got["code"] == "wait_stopped", got



def test_a_drive_hands_its_progress_to_the_act_s_own_waits(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A console step after a key waits for the stop first, and that wait reports through the
    caller's progress like the drive's own wait does."""
    fake = _driving(tmp_path)
    fake.running = True
    fake.input_effect = None

    def stops(session: Any, seconds: float, progress: ds.Progress = ds.no_progress) -> str:
        progress(0.5, None, "waiting for the stop")
        session.running = False
        return "stopped"
    monkeypatch.setattr(sequence, "_wait_for_stop", stops)
    said: list[str] = []
    got = sequence.drive(fake, server._step_ops(),
                         [{"op": "send_keys", "keys": ["a"]}, {"op": "registers"}], None, 2.0,
                         ".", 10, 30.0, lambda *a: said.append(str(a[-1])))
    assert got["status"] == "ok", got
    assert "waiting for the stop" in said, said


def test_a_drive_with_an_expectation_leaves_the_wait_to_it_not_to_the_list_s_tail(
        tmp_path: Path) -> None:
    """An act ending with the guest running and something declared that could stop it: with an
    `expect` the drive's own wait is the wait, so the list does not sit out its settle for a
    stop first."""
    fake = _driving(tmp_path)
    added = cast(dict[str, Any], server.breakpoint_at(ref="00A7:00000010"))
    assert added["status"] == "ok", added
    fake.running = True
    fake.input_effect = None
    real_wait = fake.e9_wait

    def arriving(pattern: str, seconds: float, mark: int = 0,
                 progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        fake.log.append(E9_CUE)
        return cast(dict[str, object], real_wait(pattern, seconds, mark, progress))
    fake.e9_wait = arriving
    got = sequence.drive(fake, server._step_ops(), [{"op": "send_keys", "keys": ["a"]}],
                         "key_cue_a", 2.0, ".", 10, 30.0, lambda *a: None)
    assert got["status"] == "ok" and got["verify"]["seen"] is True, got
    assert "`drive`'s wait for `expect` is the wait" in str(got["act"]), got["act"]
