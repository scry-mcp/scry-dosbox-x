"""The shapes the doubles once only claimed, read from records of a live DOSBox-X and ffmpeg
(tests/fixtures/selinfo, states, symbols-lv, ffmpeg, build_check, each with its PROVENANCE):
where the server's own code can run over what the emulator really said, it does; the cases
named `the_record_...` hold a record's own content, the fact a double elsewhere rests on, so a
double that drifts from it has the record to be read against."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import dosbox_binary as binaries
import dosbox_saved_states as states
import dosbox_session as ds
import dosbox_x_server as server

FIX = Path(__file__).resolve().parent / "fixtures"


def _reply(path: Path) -> ds.Session:
    text = path.read_text(encoding="utf-8")
    return cast(ds.Session, SimpleNamespace(command=lambda _t, **_k: text,
                                            at_debugger=lambda: True))


@pytest.mark.parametrize(("name", "reg", "kind"), [
    ("dpmi-client-cs.txt", "CS", 0x1B), ("dpmi-client-ds.txt", "DS", 0x13)])
def test_a_dpmi_clients_selector_reads_as_its_flat_descriptor(name: str, reg: str,
                                                              kind: int) -> None:
    got = ds.Session.selector(_reply(FIX / "selinfo" / name), reg)
    assert got == {"base": 0x400000, "limit": 0x9FFFF, "type": kind, "big": 1}, got


def test_the_selector_at_the_reset_park_is_refused_as_no_descriptor() -> None:
    with pytest.raises(ds.Invalid) as e:
        ds.Session.selector(_reply(FIX / "selinfo" / "break-start-cs.txt"), "CS")
    assert e.value.code == "bad_argument" and "no present descriptor" in str(e.value)


def test_an_unknown_register_is_answered_under_a_blank_name_so_it_is_refused_unasked() -> None:
    """The debugger answers a name no register has with a zeroed descriptor and no name at all,
    which no reader can tell from a real one: the server refuses the name before asking."""
    reply = (FIX / "selinfo" / "break-start-af.txt").read_text(encoding="utf-8")
    assert "  : b:00000000" in reply and "AF: b:" not in reply
    asked: list[str] = []
    fake = cast(ds.Session, SimpleNamespace(command=asked.append, at_debugger=lambda: True))
    with pytest.raises(ds.Invalid):
        ds.Session.selector(fake, "AF")
    assert asked == [], "SELINFO was typed for a name the debugger cannot answer"


def test_the_record_shows_a_second_lv_adding_to_the_first() -> None:
    """What `symbols_load`'s accumulation and the `load_symbols` doubles stand on: after two
    loads the debugger holds both."""
    held = json.loads((FIX / "symbols-lv" / "lv-twice.json").read_text(encoding="utf-8"))
    first = {name for name, _ in held["after_first"]}
    second = {name for name, _ in held["after_second"]}
    assert first < second and len(second) == len(first) + 1, held


def _channel_answering(answer: list[Any]) -> Any:
    ok, lines = answer
    return SimpleNamespace(request=lambda *_a, **_k: (ok, lines))


@pytest.mark.parametrize(("fixture", "verb"), [
    ("loadstate-missing.json", "LOADSTATE"), ("loadstate-junk.json", "LOADSTATE"),
    ("savestate-full-disk.json", "SAVESTATE")])
def test_a_state_the_emulator_refused_is_named_in_its_own_words(fixture: str, verb: str) -> None:
    """The debugger's own answer, prefixed as the server reads it: a refusal of the emulator,
    never a build that lacks the command. A save's refusal names no cause of a load's."""
    answer = json.loads((FIX / "states" / fixture).read_text(encoding="utf-8"))
    session = SimpleNamespace(at_debugger=lambda: True, control=_channel_answering(answer),
                              alive=lambda: True, launch=SimpleNamespace(logfile=None))
    with pytest.raises(ds.Invalid) as e:
        states._state_command(cast(ds.Session, session), verb, Path("/dir/x.sav"), 5.0)
    said = str(e.value)
    assert e.value.code == "unexpected_answer" and f"refused {verb}" in said, said
    if verb == "SAVESTATE":
        assert "would not take the file" in said and "another DOSBox-X version" not in said, said
    else:
        assert "another DOSBox-X version" in said and "would not take" not in said, said
    assert "log says more" not in said, "a session with no logfile was sent to its log"
    logged = SimpleNamespace(**{**vars(session), "launch": SimpleNamespace(logfile=Path("/g")),
                                "e9_mark": lambda: 0})
    with pytest.raises(ds.Invalid) as e:
        states._state_command(cast(ds.Session, logged), verb, Path("/dir/x.sav"), 5.0)
    assert "log says more" in str(e.value), str(e.value)


def test_the_record_shows_a_full_disk_save_left_nothing_behind() -> None:
    reply = json.loads((FIX / "states" / "state-save-full-disk-reply.json").read_text("utf-8"))
    assert reply["state_save"]["status"] == "INVALID" and reply["on_disk"] == {}, reply


def test_the_record_shows_a_killed_emulator_reaped_and_said_to_have_died() -> None:
    closed = json.loads((FIX / "states" / "close-after-sigkill.json").read_text("utf-8"))
    assert (closed["ended_by"], closed["exit_code"], closed["closed"]) == ("died", -9, True)


def _build_answering(tmp_path: Path, record: str, carries: bool) -> tuple[Path, Any]:
    """A binary of this case's own, holding the debugger's text (and the CPU log's, as the
    recorded debugger build does) or not, and `subprocess.run` answering `-helpdebug` with the
    recorded listing."""
    help_text = json.loads((FIX / "build_check" / record).read_text("utf-8"))["helpdebug"]
    binary = tmp_path / record / "dosbox-x"
    binary.parent.mkdir()
    marks = binaries.DEBUGGER_MARK + b"\x00" + binaries.HEAVY_DEBUG_MARK if carries else b"none"
    binary.write_bytes(b"\x00" + marks + b"\x00")
    binary.chmod(0o755)
    return binary, lambda *_a, **_k: SimpleNamespace(stdout=help_text, stderr="")


def test_a_build_without_the_debugger_lists_the_option_too_and_is_refused_by_its_bytes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The recorded `-helpdebug` of a build configured without the debugger lists `-break-start`
    as a debugger build's does, so `build_check` over that listing decides by the binary."""
    for record, carries, status in (("no-debugger.json", False, "INVALID"),
                                    ("debugger.json", True, "ok")):
        binary, run = _build_answering(tmp_path, record, carries)
        monkeypatch.setattr("subprocess.run", run)
        got = server.build_check(binary=str(binary))
        said = json.loads((FIX / "build_check" / record).read_text("utf-8"))["build_check"]
        assert got["status"] == status == said["status"], (record, got)
        assert got.get("code") == said["code"], (record, got)
        if said["message"] is not None:
            assert got["message"] == said["message"].replace("<dir>", str(binary.parent)), got
        else:
            assert (got["debugger"], got["heavy_debug"]) == (said["debugger"],
                                                             said["heavy_debug"]), got


def test_the_record_names_a_still_after_its_conf() -> None:
    """The emulator names a snapshot `<stem>_NNN.png`, the stem the conf and the program share
    here (the snapshot double writes that shape; the server reads any new PNG, name unread)."""
    shot = json.loads((FIX / "states" / "snapshot-name.json").read_text("utf-8"))
    assert shot["path_name"] == "mouse_000.png" == shot["written_names"][0], shot


def test_the_record_shows_the_forced_format_writing_nothing_where_the_free_one_boxed() -> None:
    """Why `frame()` forces the format: the same past-the-end request into a `.mp4` gives a
    frameless container left to ffmpeg, and nothing with the format forced."""
    free = json.loads((FIX / "ffmpeg" / "past-end-mp4-unforced.json").read_text("utf-8"))
    forced = json.loads((FIX / "ffmpeg" / "past-end-mp4-forced.json").read_text("utf-8"))
    box = (FIX / "ffmpeg" / "past-end-unforced.mp4").read_bytes()
    assert free["returncode"] == forced["returncode"] == 0, (free, forced)
    assert free["output_bytes"] == len(box) and forced["output_bytes"] is None, (free, forced)
    assert not box.startswith(b"\x89PNG"), "the container would have passed as a still"
