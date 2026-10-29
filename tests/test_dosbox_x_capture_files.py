"""The capture files read off their own bytes: a DRO 2.0 stream and a MIDI file the sound guest's
session wrote (`tests/fixtures/captures/`), and each controlled edit that makes one unfinished."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from scry_dosbox_x import capture_files as files

CAPTURES = Path(__file__).parent / "fixtures" / "captures"
DRO = (CAPTURES / "eight-frames.dro").read_bytes()
MID = (CAPTURES / "eight-frames.mid").read_bytes()


def _at(tmp_path: Path, data: bytes, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_the_dro_holds_the_register_state_then_the_note(tmp_path: Path) -> None:
    stream = files.dro(_at(tmp_path, DRO, "a.dro"))
    assert stream is not None and stream.pairs == 11
    events = files.dro_events(stream)
    assert events[0] == ("reg", 0x01, 0x20) and events[-1] == ("reg", 0xB0, 0x31)


@pytest.mark.parametrize(("why", "data"), [
    ("magic", b"DBRAWOPX" + DRO[8:]),
    ("version", DRO[:8] + struct.pack("<HH", 1, 0) + DRO[12:]),
    ("length", DRO + b"\x00\x00"),
    ("short", DRO[:20]),
])
def test_a_dro_that_disagrees_with_its_header_is_none(tmp_path: Path, why: str,
                                                      data: bytes) -> None:
    assert files.dro(_at(tmp_path, data, "x.dro")) is None, why
    assert files.facts("dro", tmp_path / "x.dro") == {"complete": False}
    assert files.dro(tmp_path / "never.dro") is None


def test_the_delay_codes_and_the_second_chip_are_read_as_dro_2_writes_them() -> None:
    stream = files.Dro(pairs=4, ms=0, codemap=bytes([0x01, 0xB0]), short_delay=0x7A,
                       long_delay=0x7B, body=bytes([0x7A, 9, 0x7B, 1, 0x81, 0x31, 0x05, 7]))
    assert files.dro_events(stream) == [("delay", 10, 0), ("delay", 512, 0),
                                        ("reg", 0x1B0, 0x31), ("reg", -1, 7)]


def test_the_midi_file_counts_its_track_bytes(tmp_path: Path) -> None:
    assert files.midi_track_bytes(_at(tmp_path, MID, "a.mid")) == 12
    assert files.facts("mid", tmp_path / "a.mid") == {"complete": True, "midi_bytes": 12}


@pytest.mark.parametrize(("why", "data"), [
    ("magic", b"MThx" + MID[4:]),
    ("header length", MID[:4] + struct.pack(">I", 7) + MID[8:]),
    ("short", MID[:12]),
    ("a track still open", MID[:18] + struct.pack(">I", 0) + MID[22:]),
    ("bytes past the track", MID + b"\x00"),
])
def test_a_midi_file_whose_chunks_miss_its_end_is_none(tmp_path: Path, why: str,
                                                       data: bytes) -> None:
    assert files.midi_track_bytes(_at(tmp_path, data, "x.mid")) is None, why
    assert files.midi_track_bytes(tmp_path / "never.mid") is None


def test_a_kind_with_nothing_to_count_adds_nothing(tmp_path: Path) -> None:
    assert files.facts("trace", _at(tmp_path, b"x", "a.trace")) == {}
