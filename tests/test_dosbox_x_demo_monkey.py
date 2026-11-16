"""The Monkey Island demo without an emulator: which disc it refuses, the conf it starts from, the
lookout's script as bytecode, and how it reads and moves the CD driver's requests."""

from __future__ import annotations

import hashlib
import wave
from pathlib import Path

import pytest
from scry_core.demo import Reply, Run, StepFailed

from demos import host
from demos.monkey import demo, lookout


@pytest.fixture(autouse=True)
def placed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host's own half answers yes, so what is judged here is the disc's."""
    monkeypatch.setattr(host, "precheck", lambda run: "")


def _disc(folder: Path, monkeypatch: pytest.MonkeyPatch, sectors: int = 3) -> Path:
    """A disc of tiny BINs, whose digests the demo is told to expect."""
    folder.mkdir()
    pins = {}
    for n in range(1, 20):
        name = f"monkey{n:02d}.bin"
        (folder / name).write_bytes(bytes([n]) * demo.RAW_SECTOR * sectors)
    (folder / "monkey.cue").write_text("FILE \"monkey01.bin\" BINARY\n")
    for name in demo.DISC:
        pins[name] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    monkeypatch.setattr(demo, "DISC", pins)
    return folder


def _run(tmp_path: Path, cwd: Path | str | None) -> Run:
    return Run(dir=tmp_path, options={} if cwd is None else {"cwd": str(cwd)})


def test_the_demo_refuses_anything_but_the_disc_it_was_written_for(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert demo.precheck(_run(tmp_path, None)).startswith("pass --cwd")
    assert "absolute or ~-led" in demo.precheck(_run(tmp_path, "monkey-cd"))
    cd = _disc(tmp_path / "cd", monkeypatch)
    assert demo.precheck(_run(tmp_path, cd)) == ""
    (cd / "monkey18.bin").write_bytes(b"another pressing")
    assert "is not the one this demo was written for" in demo.precheck(_run(tmp_path, cd))
    (cd / "monkey18.bin").unlink()
    assert demo.precheck(_run(tmp_path, cd)).startswith("no monkey18.bin in")


def test_the_conf_mounts_the_readers_disc_and_a_c_drive_of_the_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cd = _disc(tmp_path / "cd", monkeypatch)
    args = demo.boot(_run(tmp_path, cd))
    conf = Path(args["conf"]).read_text()
    assert f'imgmount d "{cd / "monkey.cue"}" -t cdrom' in conf
    assert 'mount c "c"' in conf and (tmp_path / "c").is_dir()
    assert "@CD@" not in conf
    assert "core=normal" in conf and "cycles=fixed" in conf and "rate=44100" in conf
    assert args["program"] == "D:\\MONKEY.COM" and args["shared"] is True
    assert Path(args["state_dir"]).parent == tmp_path


def test_the_c_drive_is_mounted_by_the_same_line_wherever_the_run_sits(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cd = _disc(tmp_path / "cd", monkeypatch)
    lines = []
    for where in (tmp_path / "r", tmp_path / "a-run-directory-of-a-much-longer-name"):
        where.mkdir()
        args = demo.boot(_run(where, cd))
        assert args["cwd"] == where
        lines.append([line for line in Path(args["conf"]).read_text().splitlines()
                      if line.startswith("mount c ")])
    assert lines[0] == lines[1] and len(lines[0]) == 1
    start = next(step for step in demo.STEPS if step.tool == "start")
    assert isinstance(start.options, frozenset) and "cwd" not in start.options


def test_the_new_reply_starts_the_theme_and_chains_hole_by_hole_to_the_branchs_tail() -> None:
    laid = lookout.layout()
    assert [start for start, _ in laid] == [start for start, _, _ in lookout.HOLES]
    assert laid[0][1][:2] == bytes([0x1C, lookout.THEME_SOUND])
    landings = []
    for (start, data), (_, end, _) in zip(laid, lookout.HOLES, strict=True):
        assert start + len(data) <= end and data[-3] == 0x18
        landings.append(start + len(data) + int.from_bytes(data[-2:], "little", signed=True))
    assert landings == [s for s, _, _ in lookout.HOLES[1:]] + [lookout.TAIL[0]]


def test_every_speech_is_said_once_in_order_and_waits_for_its_message() -> None:
    body = b"".join(data[:-3] for _, data in lookout.layout())[2:]
    want = b"".join(lookout.line(who, said) for who, said in lookout.TALK)
    assert body == want
    assert lookout.line(lookout.LOOKOUT, ("a", "b")) == b"\x14\x02\x0fa\xff\x03b\x00\xae\x02"
    assert lookout.line(lookout.GUYBRUSH, ("a",)) == b"\xd8\x0fa\x00\xae\x02"


def test_a_conversation_too_long_for_the_holes_is_refused(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lookout, "TALK", lookout.TALK * 3)
    with pytest.raises(ValueError, match="do not fit"):
        lookout.layout()


def test_the_theme_starts_after_every_track_before_it_plus_the_lead_in(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cd = _disc(tmp_path / "cd", monkeypatch, sectors=3)
    assert demo.track_start(_run(tmp_path, cd)) == demo.LEAD_IN + 17 * 3
    assert demo.red_book(165375) == bytes([0, 45, 36, 0])


def _request(command: int, start: bytes = b"\0\0\0\0", count: int = 0) -> Reply:
    raw = bytes([22, 0, command]) + bytes(10) + b"\x01" + start + count.to_bytes(4, "little")
    return Reply({"hex": raw.hex()})


def test_the_driver_requests_are_told_apart_and_the_play_must_be_the_themes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run(tmp_path, _disc(tmp_path / "cd", monkeypatch))
    start = demo.red_book(demo.track_start(run))
    assert demo.stop_request(_request(0x85), run).startswith("STOP AUDIO")
    with pytest.raises(StepFailed, match="not STOP AUDIO"):
        demo.stop_request(_request(0x84), run)
    assert "the theme's first sector, for 12200" in demo.play_request(
        _request(0x84, start, 12200), run)
    with pytest.raises(StepFailed, match="not the theme's first sector"):
        demo.play_request(_request(0x84, demo.red_book(1), 12200), run)


def test_the_play_request_is_moved_to_the_logo_and_shortened_by_as_much(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run(tmp_path, _disc(tmp_path / "cd", monkeypatch))
    run.replies["third"] = Reply({"regs": {"ES": "0x0000220f", "EBX": "0x00001d78"}})
    run.replies["request 3"] = _request(0x84, demo.red_book(0), 12200)
    moved = demo.to_the_logo(run)
    assert moved["ref"] == "220F:1D86"
    data = bytes.fromhex(moved["data_hex"])
    assert data[:4] == demo.red_book(demo.track_start(run) + demo.LOGO)
    assert int.from_bytes(data[4:], "little") == 12200 - demo.LOGO


def test_a_recording_identical_to_the_disc_passes(tmp_path: Path) -> None:
    exact = Reply({"exact": True, "class": "exact", "envelope_correlation": 1.0,
                   "snr_db": {"available": False, "why": "the two are identical"}})
    assert "identical" in demo.same_track(exact, _run(tmp_path, None))


def test_a_recording_four_times_too_loud_is_named_for_what_it_is(tmp_path: Path) -> None:
    run = _run(tmp_path, None)
    assert demo.same_track(Reply({"exact": False, "class": "audible", "snr_db": 46.0,
                                    "envelope_correlation": 1.0}), run).startswith(
        "the reader's own track 18")
    with pytest.raises(StepFailed, match="four times as loud"):
        demo.same_track(Reply({"exact": False, "class": "different", "snr_db": -9.6,
                               "envelope_correlation": 0.99}), run)


def test_reads_and_writes_are_cut_at_the_tools_128_bytes() -> None:
    assert demo.spans(-3, 0xE2) == [(-3, 125), (125, 226)]
    assert demo.spans(0, 128) == [(0, 128)]
    assert demo.spans(0, 129) == [(0, 128), (128, 129)]


def test_the_reference_is_the_discs_track_from_the_logo_laid_as_late_as_the_mixer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cd = _disc(tmp_path / "cd", monkeypatch, sectors=demo.LOGO + 2)
    pcm = bytes(range(256)) * (demo.RAW_SECTOR * 2 // 256 + 1)
    with (cd / demo.THEME).open("r+b") as f:
        f.seek(demo.LOGO * demo.RAW_SECTOR)
        f.write(pcm[:demo.RAW_SECTOR * 2])
    run = _run(tmp_path, cd)
    run.replies["theme"] = Reply({"samples": 10, "path": str(tmp_path / "theme.wav")})
    args = demo.reference(run)
    assert args["align"] is False and args["a"] == str(tmp_path / "theme.wav")
    with wave.open(str(args["b"])) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100)
        frames = w.readframes(w.getnframes())
    assert frames == bytes(4 * demo.MIXER_LAG) + pcm[:(10 - demo.MIXER_LAG) * 4]
