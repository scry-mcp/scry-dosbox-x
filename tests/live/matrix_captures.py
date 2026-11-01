"""Sections T and U of the live matrix: a stretch of sound and screen recorded at a stop
(`CAPTURE`), on the package's sound guest (`tests/guest/sound.asm`), and the accesses a tap keeps
without stopping (`TAP`), on its tap guest (`tests/guest/tap.asm`). Each answer is the guest's
own: the OPL table and the notes its source plays, the counter and the pcs its listing places."""
from __future__ import annotations

import re
import wave
from pathlib import Path
from typing import Any

from matrix_common import (
    GUEST,
    STOPPED,
    M,
    advanced,
    boot,
    cells,
    close_whatever,
    ok,
    refused,
    said,
    server,
)

from scry_dosbox_x import capture_files

SOUND_CONF, TAP_CONF = GUEST / "sound.conf", GUEST / "tap.conf"
#: `tap.asm`'s places in the segment DOS loads a `.COM` at on this conf, read off its listing.
COUNT, POLLED, W_INC, W_PAIR, R_POLL = ("0814:0138", "0814:013E", "0814:0000011D",
                                        "0814:00000126", "0814:00000129")
#: The mixer's samples a run may miss its span by (`capture_files.SPAN_TICKS` ticks).
TICK_SAMPLES = 48


def opl_table() -> list[tuple[int, int]]:
    """`sound.asm`'s register table, read from the source the guest was assembled from."""
    text = (GUEST / "sound.asm").read_text()
    body = text.split("opl_table:", 1)[1].split("opl_end:", 1)[0]
    return [(int(r, 16), int(v, 16))
            for r, v in re.findall(r"db\s+0x([0-9A-Fa-f]{2}),\s*0x([0-9A-Fa-f]{2})", body)]


T_CELLS = cells(
    ("T audio_record's WAV over 70 retraces holds the run's span and the guest's tone",
     "audio_record docstring; known: sound.asm's 1 kHz square"),
    ("T audio_record's DRO holds the guest's OPL table and its voice keyed again",
     "audio_record docstring; known: sound.asm's opl_table, and the key bit each tick"),
    ("T audio_record's MIDI file holds middle C's note",
     "audio_record docstring; known: sound.asm sends 90 3C at each tick"),
    ("T record over 10 retraces writes an AVI of 10 frames",
     "record docstring; known: one frame per retrace"),
    ("T a kind already on is refused, and nothing runs",
     "record and audio_record docstrings: Refused"),
    ("T captures lists each recording, each complete",
     "captures docstring"),
    ("T audio_compare hears the WAV, finds it exact against itself and different from silence",
     "audio_compare docstring; known: sound.asm's tone, and a silent copy of the WAV's format"),
)


def _silent_twin(path: Path) -> Path:
    """A WAV of `path`'s format and length holding only zeros: the control the tone must
    differ from."""
    with wave.open(str(path), "rb") as src:
        params, frames = src.getparams(), src.getnframes()
    twin = Path(M.fresh(".wav"))
    with wave.open(str(twin), "wb") as out:
        out.setparams(params)
        out.writeframes(bytes(frames * params.nchannels * params.sampwidth))
    return twin


def _compared(wav: dict[str, Any]) -> tuple[bool, str]:
    if not ok(wav):
        return False, said(wav)
    path = Path(str(wav.get("path")))
    heard = M.call(server.audio_compare, method="measure", path=str(path))
    same = M.call(server.audio_compare, method="diff", a=str(path), b=str(path))
    other = M.call(server.audio_compare, method="diff", a=str(_silent_twin(path)), b=str(path))
    measures = heard.get("measures") or [{}]
    holds = (ok(heard) and all(m.get("silent") is False for m in measures)
             and ok(same) and same.get("exact") is True
             and ok(other) and other.get("exact") is False and other.get("class") == "different")
    return holds, f"{said(heard, 60)}; {said(same, 40)}; {said(other, 60)}"


def _dro_holds_the_table(r: dict[str, Any]) -> bool:
    stream = capture_files.dro(Path(str(r.get("path"))))
    if stream is None:
        return False
    regs = [(reg, value) for kind, reg, value in capture_files.dro_events(stream) if kind == "reg"]
    keyed = [value for reg, value in regs if reg == 0xB0]
    wanted = [(reg, value) for reg, value in opl_table() if value and reg != 0xB0]
    return all(pair in regs for pair in wanted) and 0x31 in keyed


@M.section("T", "sound and screen recorded at a stop, on the package's sound guest", T_CELLS)
def section_t() -> None:
    boot(conf=SOUND_CONF, captures_dir=M.fresh("-cap"))
    advanced(M.call(server.run_for, frames=20), "run_for(frames=20)")
    wav = M.call(server.audio_record, seconds=30, frames=70, dest=M.fresh(".wav"))
    span = float(wav.get("emulated_s") or 0)
    M.judge(T_CELLS[0].label, ok(wav) and wav.get("kind") == "wav"
            and abs(int(wav.get("samples") or 0) - span * 48000) <= 2 * TICK_SAMPLES
            and int(wav.get("sample_min") or 0) < int(wav.get("sample_max") or 0), said(wav))
    dro = M.call(server.audio_record, seconds=30, frames=70, kind="dro", dest=M.fresh(".dro"))
    M.judge(T_CELLS[1].label, ok(dro) and _dro_holds_the_table(dro), said(dro))
    mid = M.call(server.audio_record, seconds=30, frames=70, kind="mid", dest=M.fresh(".mid"))
    held = Path(str(mid.get("path"))).read_bytes() if ok(mid) else b""
    M.judge(T_CELLS[2].label, ok(mid) and b"\x90\x3c" in held, said(mid))
    avi = M.call(server.record, seconds=30, frames=10, dest=M.fresh(".avi"))
    M.judge(T_CELLS[3].label, ok(avi) and avi.get("avi_frames") == 10, said(avi))
    M.call(server.debug, command="CAPTURE WAV ON")
    busy = M.call(server.audio_record, seconds=30, frames=2)
    M.call(server.debug, command="CAPTURE WAV OFF")
    M.judge(T_CELLS[4].label, refused(busy, "no_channel") and "already on" in str(
        busy.get("message")), said(busy))
    listed = M.call(server.captures).get("captures") or []
    recorded = [c for c in listed if c.get("kind") in ("wav", "dro", "mid", "avi")]
    M.judge(T_CELLS[5].label, sorted(c["kind"] for c in recorded) == ["avi", "dro", "mid", "wav"]
            and all(c.get("complete") is True for c in recorded), str(recorded)[:140])
    M.judge(T_CELLS[6].label, *_compared(wav))
    close_whatever()


U_CELLS = cells(
    ("U a count tallies each write of the counter by value and by writer",
     "watch_add docstring; known: tap.asm's w_inc and w_pair, once a tick"),
    ("U a capture of writes keeps each one with the block from before it",
     "watch_add docstring; known: tap.asm's count, one more each tick"),
    ("U a capture of reads keeps each read of the polled byte",
     "watch_add docstring; known: tap.asm's r_poll, once a tick"),
    ("U a stop survey counts what came since the last stop",
     "REFERENCE.md, Declarations"),
    ("U a tap is refused on a running machine",
     "watch_add docstring: count and capture need the machine STOPPED"),
    ("U a stretch with no OPL write has no DRO, and says why",
     "audio_record docstring: a run with no OPL or MIDI event has no file"),
    ("U declaration_clear removes every tap",
     "declaration_clear docstring"),
    ("U a row names the display frame it was made in",
     "watch_add docstring: first_rows; known: tap.asm writes once a BIOS tick"),
    ("U a state load taps the declared watches again, and they go on counting",
     "state_write docstring: load; known: the scry build's load resets the page handlers"),
)


def _watch(ref: str) -> dict[str, Any]:
    rows = M.call(server.declaration_list, kind="watch").get("watches") or []
    return next((w for w in rows if w.get("ref") == ref), {})


@M.section("U", "accesses kept without stopping, on the package's tap guest", U_CELLS)
def section_u() -> None:
    boot(conf=TAP_CONF, break_on_int3=True, state_dir=M.fresh("-save"))
    advanced(M.call(server.resume, seconds=30), "resume(seconds=30)", STOPPED)
    M.call(server.declaration_clear, kind="watch", all=True)
    count = M.call(server.watch_add, ref=COUNT, mode="count", length=8)
    block = M.call(server.watch_add, ref="0814:013C", mode="capture", trigger=COUNT, length=2,
                   fmt="u16")
    reads = M.call(server.watch_add, ref=POLLED, mode="capture", trigger_type="r")
    stop = M.call(server.run_for, frames=20)
    surveyed = {w.get("ref"): w for w in stop.get("watches") or []}
    tallied = _watch(COUNT)
    writers = {w.get("pc"): w.get("count") for w in tallied.get("writers") or []}
    M.judge(U_CELLS[0].label, ok(count) and tallied.get("state") == "tallied"
            and set(writers) == {W_INC, W_PAIR} and writers[W_INC] == writers[W_PAIR] >= 4,
            str(tallied)[:140])
    rows = _watch("0814:013C").get("first_rows") or []
    # The trigger is `count`; the block is `pair`, which holds the count's copy from the tick
    # before, so each row's block is the written count less one.
    M.judge(U_CELLS[1].label, ok(block) and len(rows) >= 4
            and all(r.get("pc") == W_INC and r.get("block") == int(r["data"], 16) - 1
                    for r in rows), str(rows[:2])[:140])
    read = _watch(POLLED).get("first_rows") or []
    M.judge(U_CELLS[2].label, ok(reads) and len(read) >= 4
            and all(r.get("pc") == R_POLL and r.get("data") == "0x00420000" for r in read),
            str(read[:2])[:140])
    first = surveyed.get(COUNT, {})
    again = M.call(server.run_for, frames=8)
    later = {w.get("ref"): w for w in again.get("watches") or []}.get(COUNT, {})
    M.judge(U_CELLS[3].label, ok(stop) and stop.get("verdict") == again.get("verdict") == "ELAPSED"
            and first.get("since_last_stop") == first.get("total")
            and int(later.get("since_last_stop") or 0) == int(later.get("total") or 0)
            - int(first.get("total") or 0) and "first_rows" not in first, str(later)[:140])
    M.call(server.resume)
    running = M.call(server.watch_add, ref="0814:013D", mode="count", length=1)
    M.call(server.stop)
    M.judge(U_CELLS[4].label, refused(running, "not_stopped"), said(running))
    none = M.call(server.audio_record, seconds=30, frames=4, kind="dro")
    M.judge(U_CELLS[5].label, ok(none) and isinstance(none.get("path"), dict)
            and none["path"].get("available") is False, said(none))
    cleared = M.call(server.declaration_clear, kind="watch", all=True)
    M.judge(U_CELLS[6].label, ok(cleared) and sorted(cleared.get("disarmed") or []) == [
        "TAP 1", "TAP 2", "TAP 3"], said(cleared))
    frames = [r.get("frame") for r in rows]
    M.judge(U_CELLS[7].label, all(isinstance(f, int) for f in frames)
            and frames == sorted(set(frames)) and 0 < frames[0] <= int(stop.get("frame") or 0)
            and frames[-1] <= int(again.get("frame") or 0), str(frames))
    M.call(server.watch_add, ref=COUNT, mode="count", length=8)
    M.call(server.state_write, method="save", name="tapload")
    M.call(server.run_for, frames=10)
    loaded = M.call(server.state_write, method="load", name="tapload")
    after = M.call(server.run_for, frames=20)
    counted = {w.get("ref"): w for w in after.get("watches") or []}.get(COUNT, {})
    M.judge(U_CELLS[8].label, ok(loaded) and (loaded.get("taps") or {}).get("rearmed") == [COUNT]
            and counted.get("state") == "tallied" and int(counted.get("total") or 0) >= 4,
            str(loaded.get("taps")) + " " + str(counted)[:100])
    close_whatever()
