"""What a capture file DOSBox-X wrote holds, read off its own bytes. The emulator writes the
lengths a WAV, a DRO 2.0 stream and a MIDI file declare only at close, so an open file never reads
as finished."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, NamedTuple

from scry_core import wav
from scry_core.reply_contract import unavailable

#: `audio_record`'s kinds and the debugger's `CAPTURE` word for each.
AUDIO_KINDS = {"wav": "WAV", "dro": "OPL", "mid": "MIDI"}
#: Mixer ticks (emulated milliseconds) a WAV may miss its span by: one at each end.
SPAN_TICKS = 2
NOT_FINISHED_WHY = "the file's header disagrees with it: its writer has not finished it"

DRO_MAGIC = b"DBRAWOPL"
_DRO_HEAD = struct.Struct("<8sHHIIBBBBBB")
MIDI_MAGIC = b"MThd"


class Dro(NamedTuple):
    """A finished DRO 2.0 stream."""
    pairs: int
    ms: int
    codemap: bytes
    short_delay: int
    long_delay: int
    body: bytes


def dro(path: Path) -> Dro | None:
    """The stream at `path` when its header agrees with the file, else None."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < _DRO_HEAD.size:
        return None
    magic, major, minor, pairs, ms, _hw, _fmt, _comp, short, long_, maplen = _DRO_HEAD.unpack_from(
        data)
    if magic != DRO_MAGIC or (major, minor) != (2, 0):
        return None
    start = _DRO_HEAD.size + maplen
    if len(data) != start + 2 * pairs:
        return None
    return Dro(pairs, ms, data[_DRO_HEAD.size:start], short, long_, data[start:])


def dro_events(stream: Dro) -> list[tuple[str, int, int]]:
    """Each pair as `("reg", register, value)` (a second chip's register plus 0x100) or
    `("delay", ms, 0)`."""
    out: list[tuple[str, int, int]] = []
    for code, value in zip(stream.body[0::2], stream.body[1::2], strict=True):
        if code == stream.short_delay:
            out.append(("delay", value + 1, 0))
        elif code == stream.long_delay:
            out.append(("delay", (value + 1) << 8, 0))
        else:
            index = code & 0x7F
            register = stream.codemap[index] if index < len(stream.codemap) else -1
            out.append(("reg", register | (0x100 if code & 0x80 else 0), value))
    return out


def midi_track_bytes(path: Path) -> int | None:
    """The bytes of a finished single-track MIDI file's events, or None: a `MThd` of six bytes
    then chunks whose lengths reach exactly the end of the file."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:4] != MIDI_MAGIC or len(data) < 14 or struct.unpack_from(">I", data, 4)[0] != 6:
        return None
    at, events = 14, 0
    while at + 8 <= len(data):
        size = struct.unpack_from(">I", data, at + 4)[0]
        at += 8 + size
        events += size
    return events if at == len(data) else None


def facts(kind: str, path: Path) -> dict[str, Any]:
    """What `captures` adds for a present recording other than an AVI: `complete` and the
    kind's counts; nothing for another kind."""
    if kind == "wav":
        head = wav.header(path)
        unread = unavailable(NOT_FINISHED_WHY)
        return ({"complete": False, "samples": unread, "channels": unread,
                 "sample_rate_hz": unread} if head is None else
                {"complete": True, "samples": head.samples, "channels": head.channels,
                 "sample_rate_hz": head.sample_rate})
    if kind == "dro":
        stream = dro(path)
        return ({"complete": False} if stream is None else
                {"complete": True, "opl_pairs": stream.pairs, "opl_ms": stream.ms})
    if kind == "mid":
        events = midi_track_bytes(path)
        return ({"complete": False} if events is None else
                {"complete": True, "midi_bytes": events})
    return {}
