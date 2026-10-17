"""Save states through the debugger's own commands, `SAVESTATE <file>` and `LOADSTATE <file>`
over the debugger channel (a DOSBox-X that carries them: the Optimiza/dosbox-x fork). They need
the debugger stopped, so a running guest is stopped for them and released again. A state is a
ZIP naming its `Program_Name`, `Machine_Type`, `Memory_Size`, `Time_Stamp` and
`DOSBox-X_Version`. The tools are `state_save(name)`, `state_load(name)` and `state_list`."""
from __future__ import annotations

import dataclasses
import time
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

import dosbox_mcp
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

META = {"DOSBox-X_Version": "DOSBox-X 2026.08.02 (SDL2)", "Program_Name": "PROBE",
        "Machine_Type": "svga_s3", "Memory_Size": "16", "Time_Stamp": "2026-09-10 03:58",
        "Save_Remark": ""}


def write_state(path: Path, **meta: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for k, v in {**META, **meta}.items():
            z.writestr(k, v)
        z.writestr("Memory", b"\0" * 64)
    return path


class Channel:
    """The emulator's end of the debugger channel as the fork answers the two commands: a
    save writes the file, a load reads it; `carries=False` answers as a build without them."""

    def __init__(self, session: StateFake, carries: bool = True) -> None:
        self.session, self.carries = session, carries
        self.sent: list[str] = []
        self.refuse = ""                     # a refusal of the fork's own, when set
        self.partial = False                 # a failed save leaves a half-written file
        self.raises: ds.Invalid | None = None

    def request(self, command: str, seconds: float = 5.0) -> tuple[bool, list[str]]:
        self.sent.append(command)
        assert self.session.parked, "a state command was sent with the guest running"
        verb, _, path = command.removeprefix("EXEC ").partition(" ")
        if self.raises is not None:
            raise self.raises
        if not self.carries:
            return False, ["*** Debugger command not recognized"]
        if self.refuse:
            if self.partial:
                Path(path).write_bytes(b"PK half")
            return False, [f"DEBUG: {verb} {self.refuse}", "*** Debugger command not recognized"]
        if verb == "SAVESTATE":
            write_state(Path(path))
            return True, [f"DEBUG: Saved {path}"]
        return True, [f"DEBUG: Loaded {path}"]


class StateFake:
    """The seams `state_save`/`state_load` rest on: the launch, whether the machine is parked,
    the break-in and the release, and the channel. The helpers are the REAL ones."""

    def __init__(self, state_dir: Path, *, parked: bool = True, carries: bool = True,
                 watched: bool = False) -> None:
        self.launch = ds.Launch(conf=state_dir.parent / "g.conf", cwd=state_dir.parent,
                                seconds=60, watched=watched, state_dir=state_dir)
        self.parked = parked
        self.control = Channel(self, carries)
        self.moves: list[str] = []
        self.altered = False
        self.stop_count = 0
        self.halts_on_release = False
        self.release_s = 0.0
        self.release_raises: ds.Invalid | None = None
        self.break_raises: ds.Invalid | None = None

    def at_debugger(self) -> bool:
        return self.parked

    def break_in(self, seconds: float = 5.0) -> float:
        if self.break_raises is not None:
            raise self.break_raises
        self.moves.append("break")
        self.parked = True
        return 0.05

    def resume(self) -> dict[str, object]:
        self.moves.append("resume")
        time.sleep(self.release_s)
        if self.release_raises is not None:
            raise self.release_raises
        self.parked = self.halts_on_release
        return {"halted": self.halts_on_release}

    def alive(self) -> bool:
        return True

    def state(self) -> dict[str, object]:
        return {"alive": True, "altered": self.altered}

    _state_dir = ds.Session._state_dir
    _state_command = ds.Session._state_command
    state_save = ds.Session.state_save
    state_load = ds.Session.state_load
    state_list = ds.Session.state_list


def as_session(fake: StateFake) -> ds.Session:
    return cast(ds.Session, fake)


@pytest.fixture(autouse=True)
def clean_session() -> Any:
    dstate.STATE.session = None
    dstate.STATE.clear_running_state()
    yield
    dstate.STATE.session = None
    dstate.STATE.clear_running_state()


def test_the_launch_turns_the_remark_dialog_off_and_names_the_save_directory(
        tmp_path: Path) -> None:
    """MEASURED: with `saveremark` at its default a save opens a dialog that takes the window
    away and writes nothing. So every session turns it off, and the slot directory is the
    caller's `state_dir`, passed as the option the build documents."""
    argv = ds.build_argv(ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60,
                                   state_dir=tmp_path / "states"))
    assert argv[argv.index("-savedir") + 1] == str(tmp_path / "states")
    i = argv.index("dosbox saveremark=false")
    assert argv[i - 1] == "-set"
    plain = ds.build_argv(ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60))
    assert "-savedir" not in plain and "dosbox saveremark=false" in plain


def test_state_save_sends_savestate_of_the_named_file_and_reads_it_back(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save")
    out = ds.Session.state_save(as_session(fake), "boot", 5.0)
    dest = tmp_path / "save" / "boot.sav"
    assert fake.control.sent == [f"EXEC SAVESTATE {dest}"]
    assert out["name"] == "boot" and Path(str(out["path"])) == dest and dest.is_file()
    assert out["program"] == "PROBE" and out["time_stamp"] == "2026-09-10 03:58"
    assert out["machine"] == "svga_s3" and out["memory_size"] == "16"
    assert out["version"] == "DOSBox-X 2026.08.02 (SDL2)" and cast(int, out["bytes"]) > 0
    assert out["paused"] is False and fake.moves == [], "a parked machine is left parked"
    assert fake.altered is False, "saving alters nothing"
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    with pytest.raises(ds.Invalid, match="letters, digits"):
        ds.Session.state_save(as_session(fake), "a b", 5.0)
    assert len(fake.control.sent) == 1, "a refused save sends nothing"


def test_a_running_guest_is_stopped_for_the_command_and_released_again(tmp_path: Path) -> None:
    """The commands need the debugger stopped (a load replaces the timer's tick handlers, and
    the channel is served from one while the guest runs), so the session breaks in, sends,
    and releases: the machine is left as it was found, and `paused` says it was stopped."""
    fake = StateFake(tmp_path / "save", parked=False)
    out = ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert out["paused"] is True and fake.moves == ["break", "resume"] and fake.parked is False
    loaded = ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert loaded["paused"] is True and fake.moves[2:] == ["break", "resume"]
    fake.control.refuse = "failed: x (the log says why)"
    with pytest.raises(ds.Invalid):
        ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert fake.moves[4:] == ["break", "resume"], "released again even when the load is refused"


def test_a_dangling_link_named_like_the_state_is_refused_and_nothing_written_through(
        tmp_path: Path) -> None:
    """A dangling link at `<state_dir>/<name>.sav` is a file there, or the save would land
    wherever it points."""
    fake = StateFake(tmp_path / "save")
    target = tmp_path / "elsewhere" / "theirs.sav"
    (tmp_path / "save").mkdir(exist_ok=True)
    (tmp_path / "save" / "boot.sav").symlink_to(target)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert fake.control.sent == [] and not target.exists()


def test_a_build_without_the_commands_is_no_channel_naming_the_fork(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", carries=False)
    with pytest.raises(ds.Invalid) as exc:
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert exc.value.code == "no_channel" and "Optimiza/dosbox-x" in str(exc.value)
    write_state(tmp_path / "save" / "boot.sav")
    with pytest.raises(ds.Invalid) as exc:
        ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert exc.value.code == "no_channel"


def test_a_refusal_of_the_fork_s_own_is_unexpected_answer_saying_why(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save")
    write_state(tmp_path / "save" / "boot.sav")
    for refusal in ("failed: x (the log says why)", "requires the debugger to be stopped",
                    "slot must be 1 to 100"):
        fake.control.refuse = refusal
        with pytest.raises(ds.Invalid) as exc:
            ds.Session.state_load(as_session(fake), "boot", 5.0)
        assert exc.value.code == "unexpected_answer" and refusal in str(exc.value)


def test_state_load_needs_a_named_state_and_marks_altered(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save")
    source = write_state(tmp_path / "save" / "boot.sav", Time_Stamp="2026-09-09 20:53")
    out = ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert fake.control.sent == [f"EXEC LOADSTATE {source}"]
    assert out["name"] == "boot" and out["time_stamp"] == "2026-09-09 20:53"
    assert out["paused"] is False and fake.parked is True, "a parked machine stays parked"
    assert fake.altered is True
    with pytest.raises(ds.Invalid, match="no state named") as exc:
        ds.Session.state_load(as_session(fake), "nope", 5.0)
    assert exc.value.code == "unknown_ref" and len(fake.control.sent) == 1


def test_state_list_reads_every_state_with_its_metadata_and_needs_no_window(
        tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save")
    assert ds.Session.state_list(as_session(fake)) == {"state_dir": str(tmp_path / "save"),
                                                        "states": [], "working_slot": None}
    write_state(tmp_path / "save" / "boot.sav")
    write_state(tmp_path / "save" / "1.sav", Program_Name="OTHER")
    (tmp_path / "save" / "junk.sav").write_bytes(b"not a zip")
    out = ds.Session.state_list(as_session(fake))
    names = [s["name"] for s in cast(list[dict[str, Any]], out["states"])]
    assert names == ["boot", "junk"]
    by = {s["name"]: s for s in cast(list[dict[str, Any]], out["states"])}
    assert by["boot"]["program"] == "PROBE"
    assert cast(dict[str, Any], out["working_slot"])["program"] == "OTHER"
    assert "not a save state" in str(by["junk"]["note"]) and "program" not in by["junk"]


def test_the_tools_carry_the_envelope_and_the_summaries_name_the_state(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", parked=False)
    dstate.STATE.session = fake  # type: ignore[assignment]
    saved = cast(dict[str, Any], server.state_save(name="boot"))
    assert saved["status"] == "ok" and saved["session"]["altered"] is False
    assert saved["summary"] == (f"state_save boot: {saved['bytes']} bytes, "
                                "PROBE 2026-09-10 03:58")
    listed = cast(dict[str, Any], server.state_list())
    assert listed["summary"] == "state_list: 1 states in " + str(tmp_path / "save")
    loaded = cast(dict[str, Any], server.state_load(name="boot"))
    assert loaded["status"] == "ok" and loaded["session"]["altered"] is True
    assert loaded["summary"] == f"state_load boot: loaded in {loaded['waited_s']}s"
    for name in ("state_save", "state_load", "state_list"):
        assert name in dosbox_mcp.registered_tools()
    assert "state_list" in dosbox_mcp._ANSWERS_WHILE_RUNNING
    assert "state_load" in dosbox_mcp._ANSWERS_WHILE_RUNNING


def test_state_list_keeps_the_working_slot_apart_from_the_named_states(tmp_path: Path) -> None:
    """Counting the emulator's own slot file as a state reports one state too many: it sits
    in `states` beside the copy under the name. The numbered slot is the working file and is
    reported as such, once; `states` holds the names."""
    fake = StateFake(tmp_path / "save")
    write_state(tmp_path / "save" / "boot.sav")
    write_state(tmp_path / "save" / "1.sav", Program_Name="OTHER")
    out = ds.Session.state_list(as_session(fake))
    assert [s["name"] for s in cast(list[dict[str, Any]], out["states"])] == ["boot"]
    slot = cast(dict[str, Any], out["working_slot"])
    assert slot["name"] == "1" and slot["program"] == "OTHER"
    (tmp_path / "save" / "1.sav").unlink()
    assert ds.Session.state_list(as_session(fake))["working_slot"] is None


# ------------------------------------------------------------------ the screenshot

class ShotFake(StateFake):
    """The screenshot's seam: the stub's `S` command writes `<captures_dir>/<conf>_NNN.png`,
    on a running machine only (parked, the stub never reaches its tick)."""

    def __init__(self, state_dir: Path, **kw: Any) -> None:
        super().__init__(state_dir, **{"parked": False, **kw})
        self.launch = ds.Launch(conf=state_dir.parent / "g.conf", cwd=state_dir.parent,
                                seconds=60, watched=self.launch.watched,
                                captures_dir=state_dir.parent / "caps",
                                logfile=state_dir.parent / "e9.log")
        self.shots = 0
        self.sent: list[list[bytes]] = []
        self.writes = True                   # False: the stub took the command, nothing came
        self.stub_protocol = "2"

    def send_commands(self, commands: list[bytes]) -> int:
        self.sent.append(list(commands))
        if commands == [ds.SCREENSHOT_COMMAND] and self.writes and not self.parked:
            assert self.launch.captures_dir is not None
            self.launch.captures_dir.mkdir(exist_ok=True)
            shot = self.launch.captures_dir / f"g_{self.shots:03d}.png"
            shot.write_bytes(b"\x89PNG" + bytes(20))
            self.shots += 1
        return 1


def test_snapshot_refuses_a_dangling_link_dest_and_sends_nothing(tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save")
    link = tmp_path / "shot.png"
    link.symlink_to(tmp_path / "nowhere" / "x.png")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.snapshot(as_session(fake), link, 5.0)
    assert fake.sent == [] and link.is_symlink()


def test_snapshot_sends_the_stub_s_command_and_hands_back_the_new_png_or_moves_it_to_dest(
        tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save", watched=False)      # headless: no window is needed
    out = ds.Session.snapshot(as_session(fake), None, 5.0)
    assert fake.sent == [[b"S"]]
    assert Path(str(out["path"])) == tmp_path / "caps" / "g_000.png" and out["bytes"] == 24
    assert out["route"] == "guest" and cast(float, out["waited_s"]) >= 0
    dest = tmp_path / "shot.png"
    again = ds.Session.snapshot(as_session(fake), dest, 5.0)
    assert again["path"] == str(dest) and dest.is_file()
    assert not (tmp_path / "caps" / "g_001.png").exists(), "moved, not copied"
    with pytest.raises(ds.Invalid, match="exists"):
        ds.Session.snapshot(as_session(fake), dest, 5.0)
    with pytest.raises(ds.Invalid, match="relative"):
        ds.Session.snapshot(as_session(fake), Path("shot.png"), 5.0)


def test_a_snapshot_that_cannot_be_moved_is_host_failed_naming_where_the_png_is(
        tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save")
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0o555)
    try:
        with pytest.raises(ds.Invalid) as e:
            ds.Session.snapshot(as_session(fake), shut / "s.png", 5.0)
    finally:
        shut.chmod(0o755)
    left = list((tmp_path / "caps").glob("*.png"))
    assert e.value.code == "host_failed" and len(left) == 1 and str(left[0]) in str(e.value)
    assert not (shut / "s.png").exists()


def test_snapshot_refuses_parked_and_a_command_that_produced_no_file(tmp_path: Path) -> None:
    """Parked at the debugger the stub never reaches its tick, so it is refused there with
    nothing sent; and a command with no new PNG behind it within the bound is a wait that
    expired, naming the directory watched."""
    parked = ShotFake(tmp_path / "save", parked=True)
    with pytest.raises(ds.Invalid, match="RUNNING") as exc:
        ds.Session.snapshot(as_session(parked), None, 5.0)
    assert exc.value.code == "not_running" and parked.sent == [], "nothing is sent parked"
    silent = ShotFake(tmp_path / "save")
    silent.writes = False
    with pytest.raises(ds.Invalid, match="no new PNG") as exc:
        ds.Session.snapshot(as_session(silent), None, 0.3)
    assert exc.value.code == "wait_expired" and str(tmp_path / "caps") in str(exc.value)


def test_the_snapshot_tool_carries_the_envelope_and_is_named_like_the_siblings(
        tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save")

    def through_the_real_one(dest: Path | None = None, seconds: float = 10.0,
                             progress: ds.Progress = ds.no_progress) -> dict[str, object]:
        return ds.Session.snapshot(as_session(fake), dest, seconds, progress)
    fake.snapshot = through_the_real_one  # type: ignore[attr-defined]
    dstate.STATE.session = fake  # type: ignore[assignment]
    out = cast(dict[str, Any], server.snapshot())
    assert out["status"] == "ok" and out["route"] == "guest"
    assert out["summary"] == f"snapshot: {out['bytes']} bytes at {out['path']}"
    fake.stub_protocol = ""                         # a guest that never announced the stub
    fake.launch = dataclasses.replace(fake.launch, logfile=tmp_path / "e9.log")
    fake.e9_since_mark = lambda mark: []  # type: ignore[attr-defined]
    refused = cast(dict[str, Any], server.snapshot())
    assert refused["status"] == "INVALID" and refused["code"] == "no_channel", refused
    assert "snapshot" in dosbox_mcp.registered_tools()
    assert "snapshot" in dosbox_mcp._ANSWERS_WHILE_RUNNING


def test_a_save_that_failed_leaves_no_file_holding_the_name(tmp_path: Path) -> None:
    """The emulator removes the target and writes in place, so a failure part-way leaves a
    broken file; the session removes it, or the name is refused for ever after."""
    fake = StateFake(tmp_path / "save")
    fake.control.refuse, fake.control.partial = "failed: x (the log says why)", True
    with pytest.raises(ds.Invalid):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert not (tmp_path / "save" / "boot.sav").exists()
    fake.control.refuse = ""
    assert ds.Session.state_save(as_session(fake), "boot", 5.0)["name"] == "boot"


def test_waited_s_is_the_command_alone_not_the_release(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", parked=False)
    fake.release_s = 0.3
    out = ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert out["paused"] is True and cast(float, out["waited_s"]) < 0.3


def test_running_says_whether_the_released_guest_runs(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", parked=False)
    assert ds.Session.state_save(as_session(fake), "a", 5.0)["running"] is True
    fake.parked, fake.halts_on_release = False, True
    assert ds.Session.state_save(as_session(fake), "b", 5.0)["running"] is False
    parked = StateFake(tmp_path / "other")
    assert ds.Session.state_save(as_session(parked), "c", 5.0)["running"] is False


def test_a_release_that_fails_does_not_hide_the_command_s_own_failure(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", parked=False)
    fake.control.raises = ds.Invalid("host_failed", "the reply never ended")
    fake.release_raises = ds.Invalid("session_broken", "the emulator is gone")
    with pytest.raises(ds.Invalid) as exc:
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert exc.value.code == "host_failed" and fake.moves == ["break", "resume"]


def test_a_break_in_that_fails_sends_nothing_and_releases_nothing(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save", parked=False)
    fake.break_raises = ds.Invalid("unexpected_answer", "no prompt")
    with pytest.raises(ds.Invalid):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert fake.control.sent == [] and fake.moves == []


def test_a_path_of_two_lines_is_refused_before_the_break_in(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "sa\nve", parked=False)
    with pytest.raises(ds.Invalid) as exc:
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert exc.value.code == "bad_argument" and fake.moves == [] and fake.control.sent == []


def test_a_missing_channel_names_the_fork_and_alters_nothing(tmp_path: Path) -> None:
    fake = StateFake(tmp_path / "save")
    write_state(tmp_path / "save" / "boot.sav")
    # The channel's own wording, which ends without a full stop.
    fake.control.raises = ds.Invalid("no_channel", "the emulator never dialled the debugger "
                                     "channel, so a running guest cannot be reached")
    with pytest.raises(ds.Invalid) as exc:
        ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert exc.value.code == "no_channel" and "Optimiza/dosbox-x" in str(exc.value)
    assert "cannot be reached. The saved states" in str(exc.value), "one sentence each"
    assert fake.altered is False
    fake.control.raises = None
    fake.control.carries = False
    with pytest.raises(ds.Invalid):
        ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert fake.altered is False


def test_a_parked_load_is_a_stop_of_its_own(tmp_path: Path) -> None:
    """The record of the stop before describes a machine the load replaced: the count moves,
    so the next reader surveys again instead of naming the old position."""
    fake = StateFake(tmp_path / "save")
    write_state(tmp_path / "save" / "boot.sav")
    ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert fake.stop_count == 1
    running = StateFake(tmp_path / "save", parked=False)
    ds.Session.state_load(as_session(running), "boot", 5.0)
    assert running.stop_count == 0, "a released guest's next stop is counted when it comes"


def test_a_snapshot_whose_call_is_cancelled_stops_waiting_for_the_picture(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from scry_core import cancel

    def check() -> None:
        raise asyncio.CancelledError
    fake = ShotFake(tmp_path / "save", watched=False)
    fake.writes = False                                   # the picture never comes
    monkeypatch.setattr(cancel, "check", check)
    began = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        ds.Session.snapshot(as_session(fake), None, 5.0)
    assert time.monotonic() - began < 1.0, "the wait ran on to its bound"
