"""Save states through the emulator's own menu, and what the emulator does with them:
`Capture > Save state` writes `<state_dir>/<slot>.sav` and logs `Saved. (Slot N)`
stopped or running, but ONLY with `saveremark=false` (the default opens a remark dialog that
replaces the window and blocks); `Capture > Load state` logs `Loaded. (Slot N)` with the machine
RUNNING, and with the machine parked at the debugger it leaves the debugger dead (no `Loaded.`,
an empty Debug menu, `close` at exit code 1). A state is a ZIP naming its `Program_Name`,
`Machine_Type`, `Memory_Size`, `Time_Stamp` and `DOSBox-X_Version`. The tools are
`state_save(name)`, `state_load(name)` and `state_list`."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

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


class MenuFake:
    """The seams `state_save`/`state_load` rest on: the launch, whether the machine is
    parked, the log read since a mark, and the menu click. The click WRITES what the real
    emulator logs (`Saved.` / `Loaded.`) and, for a save, the slot file, so the wait sees
    exactly what a real session shows it."""

    def __init__(self, state_dir: Path, *, watched: bool = True, logfile: bool = True,
                 parked: bool = False, saves: bool = True, loads: bool = True,
                 fails: bool = False) -> None:
        self.launch = ds.Launch(conf=state_dir.parent / "g.conf", cwd=state_dir.parent, seconds=60,
                                watched=watched, state_dir=state_dir,
                                logfile=(state_dir.parent / "e9.log") if logfile else None)
        self.parked, self.saves, self.loads, self.fails = parked, saves, loads, fails
        self.lines: list[str] = ["Active save slot: 1 [Empty]"]
        self.clicks: list[tuple[str, str]] = []
        self.altered = False
        self.proc = type("P", (), {"pid": 4242})()

    def at_debugger(self) -> bool:
        return self.parked

    def alive(self) -> bool:
        return True

    def state(self) -> dict[str, object]:
        return {"alive": True, "altered": self.altered}

    # The two helpers under test are the REAL ones: only the seams are doubled.
    _state_dir = ds.Session._state_dir
    _await_state_line = ds.Session._await_state_line
    _log_tail_from = ds.Session._log_tail_from
    state_save = ds.Session.state_save
    state_load = ds.Session.state_load
    state_list = ds.Session.state_list

    def e9_mark(self) -> int:
        return len(self.lines)

    def _e9_since(self, offset: int, channel: str = "guest") -> tuple[list[str], int]:
        assert channel == "emulator"
        return list(self.lines[offset:]), len(self.lines)

    def click_menu(self, menu: str, item: str,
                   progress: ds.Progress = ds.no_progress) -> float:
        if not self.launch.watched:      # the real one refuses a headless session first
            raise ds.Invalid("no_channel", "this session is headless: there is no window")
        self.clicks.append((menu, item))
        if item == "Save state":
            self.lines.append("Saving state to slot: 1")
            if self.fails:
                self.lines.append("SAVE_FAILED")
            elif self.saves:
                assert self.launch.state_dir is not None
                write_state(self.launch.state_dir / "1.sav")
                self.lines.append("[03:58:10]: Saved. (Slot 1)")
        elif item == "Load state":
            self.lines.append("Loading state from slot: 1")
            if self.loads:
                self.lines.append("[03:58:26]: Loaded. (Slot 1)")
        return 12.3


def as_session(fake: MenuFake) -> ds.Session:
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
    away and writes nothing, stopped or running. So every session turns it off, and the
    slot directory is the caller's `state_dir`, passed as the option the build documents."""
    argv = ds.build_argv(ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60,
                                   state_dir=tmp_path / "states"))
    assert argv[argv.index("-savedir") + 1] == str(tmp_path / "states")
    i = argv.index("dosbox saveremark=false")
    assert argv[i - 1] == "-set"
    plain = ds.build_argv(ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60))
    assert "-savedir" not in plain and "dosbox saveremark=false" in plain


def test_state_save_clicks_the_menu_waits_for_saved_and_keeps_the_state_under_its_name(
        tmp_path: Path) -> None:
    fake = MenuFake(tmp_path / "save")
    out = ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert fake.clicks == [("Capture", "Save state")]
    assert out["name"] == "boot" and out["slot"] == 1
    assert Path(str(out["path"])) == tmp_path / "save" / "boot.sav"
    assert (tmp_path / "save" / "boot.sav").is_file(), "the slot file was copied under the name"
    assert out["program"] == "PROBE" and out["time_stamp"] == "2026-09-10 03:58"
    assert out["machine"] == "svga_s3" and out["memory_size"] == "16"
    assert out["version"] == "DOSBox-X 2026.08.02 (SDL2)" and cast(int, out["bytes"]) > 0
    assert str(out["saved_line"]).endswith("Saved. (Slot 1)")
    assert fake.altered is False, "saving alters nothing"
    # NEVER OVERWRITES: a name already taken is a refusal, not a silent replacement.
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    with pytest.raises(ds.Invalid, match="letters, digits"):
        ds.Session.state_save(as_session(fake), "a b", 5.0)


def test_a_dangling_link_named_like_the_state_is_refused_and_nothing_written_through(
        tmp_path: Path) -> None:
    """The slot file is copied to `<state_dir>/<name>.sav`; a dangling link there is a file
    there, or the copy would land wherever it points."""
    fake = MenuFake(tmp_path / "save")
    target = tmp_path / "elsewhere" / "theirs.sav"
    (tmp_path / "save").mkdir(exist_ok=True)
    (tmp_path / "save" / "boot.sav").symlink_to(target)
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.state_save(as_session(fake), "boot", 5.0)
    assert fake.clicks == [] and not target.exists()


def test_snapshot_refuses_a_dangling_link_dest_and_clicks_nothing(tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save")
    link = tmp_path / "shot.png"
    link.symlink_to(tmp_path / "nowhere" / "x.png")
    with pytest.raises(ds.Invalid, match="already exists"):
        ds.Session.snapshot(as_session(fake), link, 5.0)
    assert fake.clicks == [] and link.is_symlink()


def test_state_save_refuses_headless_no_logfile_and_a_save_the_emulator_never_confirmed(
        tmp_path: Path) -> None:
    """And a PARKED machine: measured, the file is written there and loading it back kills
    the debugger, so the save is refused before the click with that reason."""
    parked = MenuFake(tmp_path / "save", parked=True)
    with pytest.raises(ds.Invalid, match="RUNNING") as exc:
        ds.Session.state_save(as_session(parked), "x", 5.0)
    assert exc.value.code == "not_running" and parked.clicks == []
    with pytest.raises(ds.Invalid, match="headless"):
        ds.Session.state_save(as_session(MenuFake(tmp_path / "save", watched=False)), "x", 5.0)
    with pytest.raises(ds.Invalid, match="logfile"):
        ds.Session.state_save(as_session(MenuFake(tmp_path / "save", logfile=False)), "x", 5.0)
    silent = MenuFake(tmp_path / "save", saves=False)
    with pytest.raises(ds.Invalid, match="Saved") as exc:
        ds.Session.state_save(as_session(silent), "x", 0.2)
    assert exc.value.code == "wait_expired"
    # MEASURED: a save directory the emulator cannot write is answered with SAVE_FAILED,
    # which ends the wait at once as a refusal that names the directory.
    failing = MenuFake(tmp_path / "save", fails=True)
    with pytest.raises(ds.Invalid, match="SAVE_FAILED") as exc:
        ds.Session.state_save(as_session(failing), "x", 5.0)
    assert exc.value.code == "unexpected_answer" and str(tmp_path / "save") in str(exc.value)


def test_state_load_needs_the_machine_running_and_a_named_state_and_marks_altered(
        tmp_path: Path) -> None:
    """MEASURED: a load with the machine parked at the debugger leaves the debugger dead.
    The named state is copied into the working slot BEFORE the click, so what the
    emulator loads is what the caller named."""
    fake = MenuFake(tmp_path / "save")
    write_state(tmp_path / "save" / "boot.sav", Time_Stamp="2026-09-09 20:53")
    write_state(tmp_path / "save" / "1.sav")           # the slot holds something else
    out = ds.Session.state_load(as_session(fake), "boot", 5.0)
    assert fake.clicks == [("Capture", "Load state")]
    assert out["name"] == "boot" and out["slot"] == 1
    assert str(out["loaded_line"]).endswith("Loaded. (Slot 1)")
    assert out["time_stamp"] == "2026-09-09 20:53", "the slot file is the named one now"
    assert fake.altered is True
    assert "not checked" in str(out["verified"]), "the machine keeps running; nothing reads it"
    with pytest.raises(ds.Invalid, match="no state named") as exc:
        ds.Session.state_load(as_session(fake), "nope", 5.0)
    assert exc.value.code == "unknown_ref"
    parked = MenuFake(tmp_path / "save", parked=True)
    with pytest.raises(ds.Invalid, match="RUNNING") as exc:
        ds.Session.state_load(as_session(parked), "boot", 5.0)
    assert exc.value.code == "not_running" and parked.clicks == [], "refused before the click"


def test_state_list_reads_every_state_with_its_metadata_and_needs_no_window(
        tmp_path: Path) -> None:
    fake = MenuFake(tmp_path / "save", watched=False, logfile=False)
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
    fake = MenuFake(tmp_path / "save")
    dstate.STATE.session = fake  # type: ignore[assignment]
    saved = cast(dict[str, Any], server.state_save(name="boot"))
    assert saved["status"] == "ok" and saved["session"]["altered"] is False
    assert saved["summary"] == (f"state_save boot: slot 1, {saved['bytes']} bytes, "
                                "PROBE 2026-09-10 03:58")
    listed = cast(dict[str, Any], server.state_list())
    assert listed["summary"] == "state_list: 1 states in " + str(tmp_path / "save")
    loaded = cast(dict[str, Any], server.state_load(name="boot"))
    assert loaded["status"] == "ok" and loaded["session"]["altered"] is True
    assert loaded["summary"] == "state_load boot: slot 1, Loaded. after 12.3s"
    for name in ("state_save", "state_load", "state_list"):
        assert name in server.registered_tools()
    assert "state_list" in server._ANSWERS_WHILE_RUNNING
    assert "state_load" in server._ANSWERS_WHILE_RUNNING


# ------------------------------------------------------------ the menu click itself

class ClickFake:
    """A session with a window and a pid, for the REAL `click_menu` and `break_in`."""

    def __init__(self, tmp_path: Path, *, watched: bool = True, parked: bool = False) -> None:
        self.launch = ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60,
                                watched=watched)
        self.proc = type("P", (), {"pid": 4242})()
        self.parked = parked
        self.clicks: list[tuple[str, str]] = []

    def at_debugger(self) -> bool:
        return self.parked

    def click_menu(self, menu: str, item: str,
                   progress: ds.Progress = ds.no_progress) -> float:
        self.clicks.append((menu, item))
        return 0.5


def _ran(stdout: str, returncode: int = 0) -> Any:
    def run(*_a: Any, **_k: Any) -> Any:
        return type("R", (), {"stdout": stdout, "stderr": "", "returncode": returncode})()
    return run


class _Osascript:
    """A `Popen` double for the menu click: alive for `polls` polls, then done with `stdout`."""

    def __init__(self, stdout: str, polls: int = 0, returncode: int = 0) -> None:
        self.stdout_text, self.polls, self.returncode = stdout, polls, returncode
        self.killed = False

    def poll(self) -> int | None:
        if self.polls > 0:
            self.polls -= 1
            return None
        return self.returncode

    def communicate(self) -> tuple[str, str]:
        return self.stdout_text, ""

    def kill(self) -> None:
        self.killed = True


def _popen(stdout: str, polls: int = 0, returncode: int = 0) -> Any:
    return lambda *_a, **_k: _Osascript(stdout, polls, returncode)


def test_click_menu_finds_the_item_by_name_and_names_what_stopped_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The script names the menu and the item; the answer is the item's own name, and
    anything else is the emulator's refusal quoted. A headless session is refused before
    System Events is asked; a host without the grant is told where it is given."""
    fake = ClickFake(tmp_path)
    monkeypatch.setattr(ds, "accessibility_trusted", lambda: True)
    monkeypatch.setattr(ds, "other_emulators", lambda own, binary: [])   # alone on the host here
    monkeypatch.setattr(subprocess, "Popen", _popen("Save state\n"))
    took = ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state")
    assert took >= 0
    monkeypatch.setattr(subprocess, "Popen", _popen("no Capture > Save state item\n"))
    with pytest.raises(ds.Invalid, match="could not be clicked") as exc:
        ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state")
    assert exc.value.code == "host_failed" and "no Capture > Save state item" in str(exc.value)

    monkeypatch.setattr(ds, "MENU_CLICK_TIMEOUT_S", 0.25)
    monkeypatch.setattr(subprocess, "Popen", _popen("never\n", polls=10_000))
    with pytest.raises(ds.Invalid, match="did not answer") as exc:
        ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state")
    assert exc.value.code == "host_failed"
    monkeypatch.setattr(ds, "accessibility_trusted", lambda: False)
    with pytest.raises(ds.Invalid, match="Accessibility") as exc:
        ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state")
    assert exc.value.code == "host_failed"
    headless = ClickFake(tmp_path, watched=False)
    calls: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a))
    with pytest.raises(ds.Invalid, match="headless") as exc:
        ds.Session.click_menu(cast(ds.Session, headless), "Capture", "Save state")
    assert exc.value.code == "no_channel" and calls == [], "refused before System Events"


def test_break_in_clicks_the_debug_item_and_waits_for_the_prompt(tmp_path: Path) -> None:
    parked = ClickFake(tmp_path, parked=True)
    assert ds.Session.break_in(cast(ds.Session, parked), seconds=1.0) >= 0
    assert parked.clicks == [(ds.BREAK_IN_MENU, ds.BREAK_IN_ITEM)]
    running = ClickFake(tmp_path, parked=False)
    with pytest.raises(ds.Invalid, match="did not appear") as exc:
        ds.Session.break_in(cast(ds.Session, running), seconds=0.1)
    assert exc.value.code == "unexpected_answer"


def test_the_log_tail_and_the_default_save_directory_and_the_refusals_without_a_logfile(
        tmp_path: Path) -> None:
    """The unterminated last line is read raw (a `Loaded.` sat there while a wait of
    complete lines expired, measured); no logfile and an unreadable one read as nothing;
    the default save directory is `save` under the cwd; and the waits refuse without a
    logfile rather than watching nothing."""
    fake = MenuFake(tmp_path / "save")
    log = fake.launch.logfile
    assert log is not None
    log.write_text("first line\n[04:28:33]: Loaded. (Slot 1)")
    assert ds.Session._log_tail_from(cast(ds.Session, fake), 0) == ["[04:28:33]: Loaded. (Slot 1)"]
    assert ds.Session._log_tail_from(cast(ds.Session, fake), len("first line\n") + 200) == []
    log.unlink()
    log.mkdir()          # a directory where the file should be: open() refuses, read as nothing
    assert ds.Session._log_tail_from(cast(ds.Session, fake), 0) == []
    nolog = MenuFake(tmp_path / "save", logfile=False)
    assert ds.Session._log_tail_from(cast(ds.Session, nolog), 0) == []
    with pytest.raises(ds.Invalid, match="logfile") as exc:
        ds.Session._await_state_line(cast(ds.Session, nolog), ds.STATE_SAVED_LINE, 0, 1.0, "x")
    assert exc.value.code == "no_channel"
    write_state(tmp_path / "save" / "boot.sav")
    with pytest.raises(ds.Invalid, match="logfile"):
        ds.Session.state_load(as_session(nolog), "boot", 5.0)
    bare = MenuFake(tmp_path / "save", watched=False, logfile=False)
    bare.launch = ds.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60)
    assert ds.Session.state_list(as_session(bare))["state_dir"] == str(tmp_path / "save")


def test_a_saved_line_with_no_slot_file_behind_it_is_refused_naming_the_directory(
        tmp_path: Path) -> None:
    """The emulator wrote into a directory this session does not read (a `state_dir` it did
    not take, say): the acknowledgement is there and the file is not, and that is said."""
    fake = MenuFake(tmp_path / "save")
    real_click = fake.click_menu

    def click_without_a_file(menu: str, item: str,
                             progress: ds.Progress = ds.no_progress) -> float:
        took = real_click(menu, item, progress)
        (tmp_path / "save" / "1.sav").unlink()
        return took
    fake.click_menu = click_without_a_file  # type: ignore[method-assign]
    with pytest.raises(ds.Invalid, match="is not there") as exc:
        ds.Session.state_save(as_session(fake), "x", 5.0)
    assert exc.value.code == "unexpected_answer" and str(tmp_path / "save") in str(exc.value)


# ------------------------------------------ one emulator at a time for a menu click

def test_click_menu_refuses_while_another_emulator_is_alive_naming_it(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """MEASURED with two servers up at once: three `Capture > Take screenshot` clicks sent
    by pid to one emulator produced three PNGs in the OTHER session's guest (the two
    windows sat on the same spot of the same display, and System Events activated the
    wrong instance of one bundle). Until the route is proven process-exact, a click with
    another `dosbox-x` alive is refused, naming the pids, and nothing is sent."""
    fake = ClickFake(tmp_path)
    monkeypatch.setattr(ds, "accessibility_trusted", lambda: True)
    monkeypatch.setattr(ds, "other_emulators", lambda own, binary: [1984, 2001])
    calls: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a))
    with pytest.raises(ds.Invalid, match="1984") as exc:
        ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state")
    assert exc.value.code == "host_failed" and "2001" in str(exc.value)
    assert calls == [], "nothing was sent to System Events"
    monkeypatch.setattr(ds, "other_emulators", lambda own, binary: [])
    monkeypatch.setattr(subprocess, "Popen", _popen("Save state\n"))
    assert ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state") >= 0


def test_other_emulators_reads_ps_by_binary_name_and_leaves_its_own_pid_out(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The listing is `ps` read by `awk` requiring the binary's basename on the line, the
    fleet's form: a helper process whose ARGUMENTS name the binary is not an emulator."""
    listing = ("  PID ARGS\n"
               " 4242 /opt/homebrew/bin/dosbox-x -conf a.conf\n"
               " 1984 dosbox-x -conf b.conf\n"
               "  777 python server.py dosbox-x\n"
               " 2001 /usr/local/bin/dosbox-x\n")
    monkeypatch.setattr(subprocess, "run", _ran(listing))
    assert ds.other_emulators(4242, "dosbox-x") == [1984, 2001]
    assert ds.other_emulators(1, "/opt/homebrew/bin/dosbox-x") == [1984, 2001, 4242]
    monkeypatch.setattr(subprocess, "run", _ran("", returncode=1))
    with pytest.raises(ds.Invalid, match="ps") as exc:
        ds.other_emulators(4242, "dosbox-x")
    assert exc.value.code == "host_failed", "a listing that failed is not an empty listing"


def test_other_emulators_sees_a_neighbour_running_the_session_s_own_build(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A session started with `binary` naming a build under another name: a second emulator of
    that build is a neighbour too, and one of another name still is not."""
    listing = ("  PID ARGS\n"
               " 4242 /opt/dbx/dosbox-x-dev -conf a.conf\n"
               " 1984 /opt/dbx/dosbox-x-dev -conf b.conf\n"
               " 2001 /opt/other/emu -conf c.conf\n")
    monkeypatch.setattr(subprocess, "run", _ran(listing))
    assert ds.other_emulators(4242, "/opt/dbx/dosbox-x-dev") == [1984]


def test_state_list_keeps_the_working_slot_apart_from_the_named_states(tmp_path: Path) -> None:
    """Counting the emulator's own slot file as a state reports one state too many: it sits
    in `states` beside the copy under the name. The numbered slot is the working file and is
    reported as such, once; `states` holds the names."""
    fake = MenuFake(tmp_path / "save", watched=False, logfile=False)
    write_state(tmp_path / "save" / "boot.sav")
    write_state(tmp_path / "save" / "1.sav", Program_Name="OTHER")
    out = ds.Session.state_list(as_session(fake))
    assert [s["name"] for s in cast(list[dict[str, Any]], out["states"])] == ["boot"]
    slot = cast(dict[str, Any], out["working_slot"])
    assert slot["name"] == "1" and slot["program"] == "OTHER"
    (tmp_path / "save" / "1.sav").unlink()
    assert ds.Session.state_list(as_session(fake))["working_slot"] is None


# ------------------------------------------------------------------ the screenshot

class ShotFake(MenuFake):
    """The screenshot's seams: the click writes `<captures_dir>/<conf>_NNN.png` when the
    machine runs (measured: parked, the emulator defers the file until it runs again)."""

    def __init__(self, state_dir: Path, **kw: Any) -> None:
        super().__init__(state_dir, **kw)
        self.launch = ds.Launch(conf=state_dir.parent / "g.conf", cwd=state_dir.parent,
                                seconds=60, watched=self.launch.watched,
                                captures_dir=state_dir.parent / "caps",
                                logfile=self.launch.logfile)
        self.shots = 0

    def click_menu(self, menu: str, item: str,
                   progress: ds.Progress = ds.no_progress) -> float:
        if item == "Take screenshot":
            if not self.launch.watched:
                raise ds.Invalid("no_channel", "this session is headless: there is no window")
            self.clicks.append((menu, item))
            if not self.parked:
                assert self.launch.captures_dir is not None
                self.launch.captures_dir.mkdir(exist_ok=True)
                shot = self.launch.captures_dir / f"g_{self.shots:03d}.png"
                shot.write_bytes(b"\x89PNG" + bytes(20))
                self.shots += 1
            return 4.5
        return super().click_menu(menu, item, progress)


def test_snapshot_clicks_the_menu_and_hands_back_the_new_png_or_moves_it_to_dest(
        tmp_path: Path) -> None:
    fake = ShotFake(tmp_path / "save")
    out = ds.Session.snapshot(as_session(fake), None, 5.0)
    assert fake.clicks == [("Capture", "Take screenshot")]
    assert Path(str(out["path"])) == tmp_path / "caps" / "g_000.png" and out["bytes"] == 24
    assert out["click_s"] == 4.5 and cast(float, out["waited_s"]) >= 0
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


def test_snapshot_refuses_parked_headless_and_a_click_that_produced_no_file(tmp_path: Path) -> None:
    """MEASURED: parked at the debugger the click is taken and the file appears only when
    the machine runs again, so it is refused there; and a click with no new PNG behind it
    within the bound is a wait that expired, naming the directory watched."""
    parked = ShotFake(tmp_path / "save", parked=True)
    with pytest.raises(ds.Invalid, match="RUNNING") as exc:
        ds.Session.snapshot(as_session(parked), None, 5.0)
    assert exc.value.code == "not_running" and parked.clicks == []
    with pytest.raises(ds.Invalid, match="headless"):
        ds.Session.snapshot(as_session(ShotFake(tmp_path / "save", watched=False)), None, 5.0)
    silent = ShotFake(tmp_path / "save")
    silent.click_menu = lambda menu, item, progress=None: 4.5  # type: ignore[method-assign]
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
    assert out["status"] == "ok"
    assert out["summary"] == f"snapshot: {out['bytes']} bytes at {out['path']}"
    assert "snapshot" in server.registered_tools()
    assert "snapshot" in server._ANSWERS_WHILE_RUNNING


def test_click_menu_reports_its_progress_while_system_events_walks_the_menus(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A menu click that paints nothing while it walks the menus makes a slow click and a
    hung one look the same. The click polls the script and reports the seconds and what it is
    looking for, on the fleet's cadence, until the script answers."""
    fake = ClickFake(tmp_path)
    monkeypatch.setattr(ds, "accessibility_trusted", lambda: True)
    monkeypatch.setattr(ds, "other_emulators", lambda own, binary: [])
    monkeypatch.setattr(ds, "PROGRESS_EVERY_S", 0.05)
    monkeypatch.setattr(subprocess, "Popen", _popen("Save state\n", polls=6))
    ticks: list[tuple[float, float, str]] = []
    took = ds.Session.click_menu(cast(ds.Session, fake), "Capture", "Save state",
                                 lambda p, t, m: ticks.append((p, t, m)))
    assert took >= 0.5 and len(ticks) >= 2, ticks
    assert all(t == ds.MENU_CLICK_TIMEOUT_S for _, t, _ in ticks)
    assert "Capture > Save state" in ticks[-1][2] and "System Events" in ticks[-1][2]
