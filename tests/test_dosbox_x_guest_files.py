"""The guest's file channel: a file fingerprinted before the run, judged after it, and the
emulator's own log categories chosen at `start`."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import install
from scry_core.reply_contract import Invalid

import dosbox_guest_files as guest
import dosbox_launch as dlaunch
import dosbox_state as dstate
import dosbox_x_server as server


def _judged(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], server.guest_file(path=str(path)))


def _taken(*paths: Path) -> None:
    install()
    dstate.STATE.guest_files = guest.take(list(paths))


def test_a_file_the_guest_wrote_is_written_with_its_bytes(tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    _taken(out)
    out.write_bytes(b"SCRY")
    got = _judged(out)
    assert got["status"] == "ok" and got["state"] == "written" and got["bytes"] == 4, got
    assert got["before"] == {"exists": False}


def test_a_file_never_written_is_absent_and_invalid(tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    _taken(out)
    got = _judged(out)
    assert got["status"] == "INVALID" and got["code"] == "readback_refused", got
    assert got["state"] == "absent" and "left no file" in got["message"]


def test_a_file_left_empty_is_empty_and_invalid(tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    _taken(out)
    out.write_bytes(b"")
    got = _judged(out)
    assert got["status"] == "INVALID" and got["state"] == "empty", got


def test_a_file_from_before_the_run_untouched_is_unchanged_and_invalid(tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    out.write_bytes(b"SCRY")
    _taken(out)
    got = _judged(out)
    assert got["status"] == "INVALID" and got["state"] == "unchanged", got
    assert got["before"]["exists"] is True and got["before"]["bytes"] == 4


def test_the_same_bytes_written_again_are_written_and_say_so(tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    out.write_bytes(b"SCRY")
    _taken(out)
    stat = out.stat()
    out.write_bytes(b"SCRY")
    os.utime(out, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    got = _judged(out)
    assert got["state"] == "written" and got["same_bytes"] is True, got


def test_a_path_start_did_not_fingerprint_is_refused(tmp_path: Path) -> None:
    _taken(tmp_path / "OUT.TXT")
    got = _judged(tmp_path / "OTHER.TXT")
    assert got["code"] == "bad_argument" and "not fingerprinted" in got["message"], got


#: An absolute path on this host, which a Windows drive letter is part of.
_A = Path(Path.cwd().anchor, "a")


@pytest.mark.parametrize(("given", "said"), [
    ("OUT.TXT", "list"), (["rel/OUT.TXT"], "absolute"),
    ([str(_A / "OUT.TXT"), str(_A / "OUT.TXT")], "twice"),
    ([str(_A / str(i)) for i in range(guest.GUEST_FILES_MAX + 1)], "at most")])
def test_guest_files_that_cannot_be_fingerprinted_are_refused(given: Any, said: str) -> None:
    with pytest.raises(Invalid) as e:
        guest.check_guest_files(given)
    assert e.value.code == "bad_argument" and said in str(e.value), str(e.value)


def test_close_carries_each_file_s_state(tmp_path: Path) -> None:
    out, never = tmp_path / "OUT.TXT", tmp_path / "NEVER.TXT"
    _taken(out, never)
    out.write_bytes(b"x")
    states = {g["path"]: g["state"] for g in guest.at_close()}
    assert states == {str(out): "written", str(never): "absent"}


def test_log_categories_each_become_a_set_of_the_log_section(tmp_path: Path) -> None:
    launch = dlaunch.Launch(conf=tmp_path / "g.conf", cwd=tmp_path, seconds=60,
                            logfile=tmp_path / "x.log",
                            log_categories={"files": "normal", "pit": "debug"})
    argv = dlaunch.build_argv(launch)
    assert "log files=normal" in argv and "log pit=debug" in argv, argv


@pytest.mark.parametrize(("given", "logfile", "said"), [
    ({"filez": "debug"}, True, "log_categories key"), ({"files": "loud"}, True, "files"),
    ({"files": "debug"}, False, "no `logfile`")])
def test_log_categories_a_build_would_ignore_are_refused(given: dict[str, str], logfile: bool,
                                                         said: str) -> None:
    with pytest.raises(Invalid) as e:
        dlaunch.check_log_categories(given, logfile)
    assert e.value.code == "bad_argument" and said in str(e.value), str(e.value)


def test_a_log_category_set_through_flags_is_refused_as_log_categories_own() -> None:
    with pytest.raises(Invalid) as e:
        dlaunch.check_flags("flags", ["-set", "log files=debug"])
    assert "log_categories" in str(e.value)


def test_a_file_the_guest_turned_into_a_directory_is_unreadable_not_a_failed_close(
        tmp_path: Path) -> None:
    out = tmp_path / "OUT.TXT"
    _taken(out)
    out.mkdir()
    states = guest.at_close()
    assert states[0]["state"] == "unreadable" and "why" in states[0], states


def test_a_large_output_is_hashed_in_chunks_never_read_whole(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    big = tmp_path / "OUT.BIN"
    big.write_bytes(b"\x5a" * 3_000_007)

    def refuse(self: Path) -> bytes:
        raise AssertionError("the whole file was read into memory")

    monkeypatch.setattr(Path, "read_bytes", refuse)
    seen = guest.fingerprint(big)
    assert seen.size == 3_000_007
    monkeypatch.undo()
    assert seen.sha256 == hashlib.sha256(big.read_bytes()).hexdigest()
