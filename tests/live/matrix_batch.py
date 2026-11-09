"""Section AA of the live matrix: what the debugger commands added to DOSBox-X do once
the machine exists, which the emulator's own unit tests cannot reach.

`MEMDUMPLIN`'s file name and its two refusals, `VGAMEMDUMP`'s file name, `PORTINFO` as typed
and the dynamic core's guard against a long run of one-byte instructions. The file-name cells
need a case-sensitive volume: run with `DOSBOX_X_LIVE_PRIVATE` naming a directory on one, so the
guests are copied there; a volume that folds case is detected and the cells are BLOCKED.
"""
from __future__ import annotations

import array
import contextlib
import math
import os
import re
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

from matrix_common import (
    ENV,
    GUEST,
    M,
    boot,
    cells,
    close_whatever,
    ok,
    read_bytes,
    said,
    server,
)
from matrix_dpmi import dpmi_client

from scry_dosbox_x import state as dstate

MIXED_NAME = "MixedCase.Bin"
FILE_CELLS = (
    "AA MEMDUMPLIN keeps the file name's case and holds the bytes the flat selector reads",
    "AA MEMDUMPLIN FFFFFF00 200 is refused and writes no file",
    "AA MEMDUMPLIN before any page tables are loaded is refused and leaves no data",
    "AA VGAMEMDUMP keeps the file name's case",
)
PORT_CELL = ("AA PORTINFO answers port 60 with R1=1 and an unclaimed port with zeros, and "
             "refuses 10000")
RUNSTATE_CELL = ("AA RUNSTATE names the BPIF row that stopped the machine, and no longer after "
                 "a step")
FRAMES_CELL = "AA RUNSTATE's frames stands still while the machine is stopped and a VRD redraws"
RUNWATCH_CELL = "AA a BPIF stop reached under RUNWATCH still names its row, until the next step"
CHANNEL_CELL = "AA a debugger request is answered without waiting out the channel's socket poll"
TAP_CELL = "AA TAP refuses an offset past 32 bits and installs nothing"
DYNAMIC_CELL = "AA the dynrec core runs 3000 STI, 3000 CLI and 1500 STI;NOP and exits 0"
TAPDEL_CELL = "AA TAP then TAPDEL under core=auto leave the emulator alive and silent"
TRACE_CELL = "AA a DOSTRACE restarted with a call open gives the new file no row for that call"
#: How many recordings the level may take when the host drops blocks of one.
CDVOL_TRIES = 3
CDVOL_CELL = "AA full MSCDEX channel volume plays the track at its own level, not amplified"
EDGE_CELL = "AA a BPIF row stops the machine once per false-to-true change, not while it holds"
AA_CELLS = cells(
    (FILE_CELLS[0], "MEMDUMPLIN usage text: a dump by linear address, the name as typed"),
    (FILE_CELLS[1], "MEMDUMPLIN: a dump past the end of the 32-bit linear space"),
    (FILE_CELLS[2], "MEMDUMPLIN usage text: nothing until a DPMI host loaded the page tables; "
     "the file is opened before the walk, as MEMDUMPBIN's is"),
    (FILE_CELLS[3], "VGAMEMDUMP usage text: the file name as typed"),
    (PORT_CELL, "PORTINFO usage text: R1/R2/R4/W1/W2/W4 per port, hex within the I/O space"),
    (RUNSTATE_CELL, "RUNSTATE: `bpif=` rides the stop a BPIF row made and goes with the next run"),
    (FRAMES_CELL, "README.debugger RUNSTATE: frames counts the frames the guest started"),
    (RUNWATCH_CELL, "README.debugger RUNSTATE: bpif= stays until a run, a step or the row goes"),
    (CHANNEL_CELL, "debug_mcp: while a request is owed a reply the I/O thread polls at 1 ms"),
    (TAP_CELL, "TAP usage text: hex seg:off, a 32-bit offset"),
    (DYNAMIC_CELL, "dynrec: a run of one-byte instructions no longer overruns the stub slots"),
    (TAPDEL_CELL, "README.debugger TAPDEL: the page handler is put back and the machine goes on"),
    (TRACE_CELL, "dos.cpp DOSTRACE: a call begun in an earlier trace has no row in the new file"),
    (CDVOL_CELL, "cdrom_image.cpp: the volume scales each sample once, not the mixer too"),
    (EDGE_CELL, "README.debugger BPIF: a row rises once per false-to-true change of its condition"),
)
#: A run of STI, of CLI and of STI;NOP pairs, each ended by RET.
DYNAMIC_PROGRAMS = {
    "STI.COM": b"\xFB" * 3000 + b"\xC3",
    "CLI.COM": b"\xFA" * 3000 + b"\xC3",
    "STINOP.COM": b"\xFB\x90" * 1500 + b"\xC3",
}
DYNAMIC_RUN_S = 90


#: The files the cells judge, in both spellings, written by the emulator into the guest's directory.
LEFTOVERS = tuple(n for name in (MIXED_NAME, "Wrap.Bin", "Early.Bin", "VgaCase.Bin")
                  for n in (name, name.upper()))


def _scrub() -> None:
    """Take away the files an earlier run left, so one is never judged as this run's."""
    for name in LEFTOVERS:
        (GUEST / name).unlink(missing_ok=True)


def _says(command: str) -> tuple[bool, str]:
    """Whether the debugger took the command to its end, and what it printed."""
    r = M.call(server.debug, command=command)
    return (True, str(r.get("output", ""))) if ok(r) else (False, said(r))


def _case_sensitive(where: Path) -> bool:
    """Whether `where` holds two names that differ only in case, tried with files of this run."""
    a, b = where / "case-probe.tmp", where / "CASE-PROBE.TMP"
    for p in (a, b):
        p.write_bytes(p.name.encode())
    names = {p.name for p in where.iterdir()}
    for p in (a, b):
        p.unlink(missing_ok=True)
    return {a.name, b.name} <= names


def _names() -> set[str]:
    return {p.name for p in GUEST.iterdir()}


def _dpmi_files() -> None:
    stop, loaded = dpmi_client()
    if not (ok(stop) and ok(loaded)):
        _block_dpmi_cells(f"the DPMI guest did not stop: {said(stop)}; {said(loaded)}")
        return
    found = M.call(server.symbols_find, name="_g_ticks")
    sym = [s for s in found.get("symbols") or [] if s.get("name") == "_g_ticks"]
    linear = int(str(sym[0].get("addr")), 16) if sym else None
    if linear is None:
        _block_dpmi_cells(f"_g_ticks has no address: {said(found)}")
        return
    _took, said_out = _says(f"MEMDUMPLIN {linear:08X} 20 {MIXED_NAME}")
    names = _names()
    flat = M.call(server.memdump, ref=f"0038:{linear:08X}", length=0x20, dest=M.fresh(".bin"))
    read = read_bytes(f"0038:{linear:08X}", 0x20) if ok(flat) else None
    dumped = (GUEST / MIXED_NAME).read_bytes() if (GUEST / MIXED_NAME).is_file() else None
    M.judge(FILE_CELLS[0], MIXED_NAME in names and MIXED_NAME.upper() not in names
            and dumped is not None and dumped == read,
            f"{said_out[:80]!r}; names {sorted(n for n in names if 'ixed' in n.lower())}")
    took, wrapped = _says("MEMDUMPLIN FFFFFF00 200 Wrap.Bin")
    M.judge(FILE_CELLS[1], took and "past the end" in wrapped and "Wrap.Bin" not in _names()
            and "WRAP.BIN" not in _names() and "success" not in wrapped.lower(), wrapped[:120])
    close_whatever()


def _block_dpmi_cells(why: str) -> None:
    for label in FILE_CELLS[:2]:
        M.block(label, why)
    close_whatever()


def _before_page_tables(folds: bool) -> None:
    boot()
    took, early = _says("MEMDUMPLIN 0 10 Early.Bin")
    left = [GUEST / n for n in ("Early.Bin", "EARLY.BIN") if (GUEST / n).is_file()]
    M.judge(FILE_CELLS[2], took and "not mapped" in early and "success" not in early.lower()
            and all(p.stat().st_size == 0 for p in left), early[:120])
    if not folds:
        took, vga = _says("VGAMEMDUMP 0 10 VgaCase.Bin")
        names = _names()
        M.judge(FILE_CELLS[3], took and "success" in vga and "VgaCase.Bin" in names
                and "VGACASE.BIN" not in names, vga[:120])
    (read_ok, port_read), (none_ok, port_none), (over_ok, port_over) = (
        _says("PORTINFO 60"), _says("PORTINFO 2E8"), _says("PORTINFO 10000"))
    M.judge(PORT_CELL, read_ok and none_ok and over_ok and "PORTINFO 0060 R1=1" in port_read
            and "R1=0 R2=0 R4=0 W1=0 W2=0 W4=0" in port_none and "R1=" not in port_over,
            f"{port_read[:50]!r} / {port_none[:60]!r} / {port_over[:60]!r}")
    armed = M.call(server.regpoint_add, condition="bx == 0x100")
    stop = M.call(server.resume, seconds=30)
    named_ok, named = _says("RUNSTATE")
    stepped = M.call(server.step)
    after_ok, after = _says("RUNSTATE")
    M.judge(RUNSTATE_CELL, ok(armed) and ok(stop) and ok(stepped) and named_ok and after_ok
            and "bpif=" in named and "bpif=" not in after, f"{named[:90]!r} / {after[:90]!r}")
    _frames_and_tap()
    close_whatever()
    _runwatch()


def _frames(text: str) -> int | None:
    found = re.search(r"frames=(\d+)", text)
    return int(found.group(1)) if found else None


def _frames_and_tap() -> None:
    _, before = _says("RUNSTATE")
    redraw_ok, _ = _says("VRD")
    _, after = _says("RUNSTATE")
    M.judge(FRAMES_CELL, redraw_ok and _frames(before) is not None
            and _frames(before) == _frames(after), f"{before[-40:]!r} / {after[-40:]!r}")
    took, tapped = _says("TAP W 0:100000010 tap-off.txt")
    listed_ok, listing = _says("TAPLIST")
    leftover = (GUEST / "tap-off.txt").exists()
    _says("TAPDEL *")
    with contextlib.suppress(OSError):
        (GUEST / "tap-off.txt").unlink(missing_ok=True)
    M.judge(TAP_CELL, took and "usage" in tapped and listed_ok and "INSTALLED=1" not in listing
            and not leftover, f"{tapped[:80]!r} / {listing[:60]!r}")


def _runwatch() -> None:
    """A BPIF stop reached by RUNWATCH, sent to the session directly: the server's `debug` tool
    refuses the commands that release the guest."""
    boot()
    armed = M.call(server.regpoint_add, condition="bx == 0x100")
    ses = dstate.STATE.session
    named, after = "", ""
    if ses is not None and ok(armed):
        ses.exec("RUNWATCH")
        for _ in range(10):
            time.sleep(2)
            named = "\n".join(ses.exec("RUNSTATE")[1])
            if "stopped" in named:
                break
        ses.exec("STEPIN")
        after = "\n".join(ses.exec("RUNSTATE")[1])
    M.judge(RUNWATCH_CELL, "stopped" in named and "bpif=" in named and "stopped" in after
            and "bpif=" not in after, f"{named[-60:]!r} / {after[-60:]!r}")
    close_whatever()


#: Requests asked back to back; the poll the reply used to wait out is 50 ms, a served one is a
#: few ms.
CHANNEL_REQUESTS = 40
CHANNEL_MEDIAN_LIMIT_S = 0.02


def _channel_latency() -> None:
    boot()
    spans: list[float] = []
    for _ in range(CHANNEL_REQUESTS):
        began = time.monotonic()
        took, _ = _says("RUNSTATE")
        spans.append(time.monotonic() - began)
        if not took:
            break
    spans.sort()
    median = spans[len(spans) // 2]
    M.judge(CHANNEL_CELL, len(spans) == CHANNEL_REQUESTS and median < CHANNEL_MEDIAN_LIMIT_S,
            f"median {median * 1000:.1f} ms of {len(spans)} requests, limit "
            f"{CHANNEL_MEDIAN_LIMIT_S * 1000:.0f} ms")
    close_whatever()


#: A register the probe guest never writes, so only this cell decides when the condition changes.
EDGE_CONDITION = "bp == 0x5a5a"
EDGE_RISES = 3
EDGE_BOUND_S = 5
EDGE_QUIET_S = 2


def _bpif_edge() -> None:
    """The row fires on each false-to-true change of its condition and stays quiet while the
    condition holds or is false: stop, make it true, run, and count the stops."""
    boot()
    armed = M.call(server.regpoint_add, condition=EDGE_CONDITION)
    stops = quiet = 0
    seen = ""
    if ok(armed):
        for _ in range(EDGE_RISES):
            M.call(server.set_register, name="bp", value=0x5A5A)
            rose = M.call(server.resume, seconds=EDGE_BOUND_S)
            if ok(rose) and rose.get("verdict") == "OTHER_STOP":
                seen = _says("RUNSTATE")[1]
                stops += "bpif=" in seen
            held = M.call(server.resume, seconds=EDGE_QUIET_S)
            if ok(held) and held.get("verdict") == "TIMEOUT":
                M.call(server.stop)
                M.call(server.set_register, name="bp", value=0)
                low = M.call(server.resume, seconds=EDGE_QUIET_S)
                quiet += ok(low) and low.get("verdict") == "TIMEOUT"
                M.call(server.stop)
            else:
                break
    M.judge(EDGE_CELL, stops == EDGE_RISES and quiet == EDGE_RISES,
            f"{stops} of {EDGE_RISES} rises stopped with a bpif row, {quiet} quiet runs while the "
            f"condition held or was false; last RUNSTATE {seen[-60:]!r}")
    close_whatever()


TAP_RUN_S = 3

#: Sets the audio channel volume of drive D: (MSCDEX IOCTL output, control block 3) to 255 on both
#: channels, then plays 20 s of the first audio track (red book 00:02:00, 1500 sectors); built from
#: a source of 91 bytes. The two volume bytes sit in `0300ff01ff02`.
CDVOL_GUEST = bytes.fromhex(
    "8c0e32010e07b81015b90300bb2201cd2fb81015b90300bb4501cd2fb400cd16ebfa1a000c0000000000000000"
    "0000003c01000009000000000000000300ff01ff02000300160084000000000000000000000100020000dc0500"
    "00")
CDVOL_TONE_PEAK = 8000
CDVOL_RUN_S = 4
#: Full volume must give the track back at its own level, within this share.
CDVOL_LEVEL_TOLERANCE = 0.1
CDVOL_FRAMES = 40


def _cd_tone(where: Path) -> None:
    """20 s of a 441 Hz sine in 44.1 kHz 16-bit stereo, as a raw red book track and its cue."""
    one = [round(CDVOL_TONE_PEAK * math.sin(2 * math.pi * i / 100)) for i in range(100)]
    pcm = array.array("h")
    for _ in range(44100 * 20 // 100):
        for v in one:
            pcm.extend((v, v))
    (where / "tone.bin").write_bytes(pcm.tobytes())
    cue = 'FILE "tone.bin" BINARY\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
    (where / "tone.cue").write_text(cue, encoding="ascii")


def _wav_peak(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        samples = array.array("h", w.readframes(w.getnframes()))
    return max((abs(v) for v in samples), default=0)


def _cd_peak(where: Path, volume: int) -> tuple[int, str]:
    """The loudest sample of the mixer's output while the guest plays the tone at `volume`."""
    guest = bytearray(CDVOL_GUEST)
    at = guest.index(bytes.fromhex("0300ff01ff02"))
    guest[at + 2] = guest[at + 4] = volume
    (where / "CDVOL.COM").write_bytes(bytes(guest))
    conf = where / f"cdvol{volume}.conf"
    conf.write_text("[sdl]\nautolock=false\n[dosbox]\nmachine=svga_s3\nmemsize=16\n[cpu]\n"
                    "core=normal\ncputype=pentium\ncycles=fixed 10000\n[autoexec]\n"
                    f'mount c "{where}"\nimgmount d "{where / "tone.cue"}" -t iso\nc:\nCDVOL.COM\n',
                    encoding="ascii")
    wav: dict[str, Any] = {}
    tries = 0
    # A busy host's mixer can drop blocks; the server refuses that recording, and the level is
    # still judged only on one it accepted.
    while tries < CDVOL_TRIES:
        tries += 1
        boot(conf=conf, cwd=where, captures_dir=M.fresh("-cap"))
        M.call(server.resume, seconds=CDVOL_RUN_S)
        M.call(server.stop)
        wav = M.call(server.audio_record, frames=CDVOL_FRAMES, seconds=20, dest=M.fresh(".wav"))
        close_whatever()
        if wav.get("code") != "readback_refused":
            break
    peak = _wav_peak(Path(str(wav.get("path")))) if ok(wav) and wav.get("path") else 0
    return peak, f"{said(wav, 70)} (try {tries} of {CDVOL_TRIES})"


def _cd_volume() -> None:
    where = M.tmp("-cdvol-")
    _cd_tone(where)
    full, said_full = _cd_peak(where, 255)
    half, said_half = _cd_peak(where, 128)
    ratio = half / full if full else 0.0
    M.judge(CDVOL_CELL, abs(full / CDVOL_TONE_PEAK - 1) < CDVOL_LEVEL_TOLERANCE
            and abs(ratio - 128 / 255) < CDVOL_LEVEL_TOLERANCE,
            f"peak {full} at volume 255 and {half} at 128 (ratio {ratio:.3f}); the tone's own peak "
            f"is {CDVOL_TONE_PEAK}; {said_full}; {said_half}")

#: `mov ah,8; int 21h` (waits for a key, inside DOS), then echoes it with AH=2 and exits.
TRACE_GUEST = bytes.fromhex("b408cd2188c2b402cd21b8004ccd21")
TRACE_WAIT_S = 3


def _dostrace_restart() -> None:
    """A trace turned off and on again while a call is still inside DOS: that call returns after
    the restart and the new file, numbering from 1, must not get its row."""
    where = M.tmp("-dostrace-")
    (where / "TRACE.COM").write_bytes(TRACE_GUEST)
    conf = where / "trace.conf"
    conf.write_text("[sdl]\nautolock=false\n[dosbox]\nmachine=svga_s3\nmemsize=16\n[cpu]\n"
                    "core=normal\ncputype=pentium\ncycles=fixed 10000\n[autoexec]\n"
                    f'mount c "{where}"\nc:\nTRACE.COM\n', encoding="ascii")
    boot(conf=conf, cwd=where)
    ses = dstate.STATE.session
    if ses is None:
        M.judge(TRACE_CELL, False, "no session after boot")
        return

    def raw(command: str) -> tuple[bool, str]:
        """The command sent to the session itself: the server's `debug` refuses the trace
        commands, which its `dos` channel reads."""
        text = "\n".join(ses.exec(command)[1])
        return "usage" not in text and "already on" not in text and "cannot" not in text, text

    # `start` opens a trace only when asked for `dos_calls`, which this boot is not; the OFF
    # makes sure none is on, and `one.txt` is where the call about to be left open begins.
    raw("DOSTRACE OFF")
    started = (raw("DOSTRACE one.txt")[0], "")
    M.call(server.resume, seconds=TRACE_WAIT_S)
    M.call(server.stop)
    restarted = (raw("DOSTRACE OFF"), raw("DOSTRACE two.txt"))
    # The key goes into the BIOS keyboard buffer (an 'a', head 1Eh, tail 20h): this guest loads no
    # input stub, and the call in DOS polls that buffer.
    keyed = M.call(server.write, ref="0040:001E", data_hex="611e")
    M.call(server.write, ref="0040:001A", data_hex="1e002000")
    M.call(server.resume)
    time.sleep(TRACE_WAIT_S)
    M.call(server.stop)
    raw("DOSTRACE OFF")
    rows = {name: (where / name).read_text().splitlines() if (where / name).is_file() else []
            for name in ("one.txt", "two.txt")}
    entered = {r.split()[1] for r in rows["one.txt"] if r.startswith("E ")}
    returned_before = {r.split()[1] for r in rows["one.txt"] if r.startswith("R ")}
    waiting = [r for r in rows["one.txt"] if r.startswith("E ") and r.split()[1] not in
               {f for f in returned_before} and "AX=08" in r]
    open_call = waiting[0].split()[1] if waiting else ""
    first = rows["two.txt"][:1]
    new_call = [r for r in rows["two.txt"] if r.startswith("E N=1 ") and "AX=02" in r]
    returned = [r for r in rows["two.txt"] if r.startswith("R N=1 ")]
    M.judge(TRACE_CELL, started[0] and all(took for took, _ in restarted) and len(waiting) == 1
            and entered - returned_before == {open_call}
            and bool(first) and first[0].startswith("E N=1 ") and len(new_call) == 1
            and len(returned) == 1, f"one.txt {len(rows['one.txt'])} rows, two.txt "
            f"{len(rows['two.txt'])} rows, first {first!r}, R N=1 rows {len(returned)}; "
            f"open call N={open_call}; one.txt tail {[r[:40] for r in rows['one.txt'][-2:]]}; "
            f"two.txt head {[r[:40] for r in rows['two.txt'][:3]]}; key: {said(keyed)[:90]}")
    close_whatever()


def _tapdel_auto() -> None:
    """TAP installs a page handler, TAPDEL puts it back, with the machine run in between. TAP is
    refused while the dynamic core is the current one, so the page is tapped from real mode and
    only a guest entering protected mode would hand it to that core (not driven here). On a
    sanitizer build the process's own report decides (`ASAN_OPTIONS` names the log read)."""
    where = M.tmp("-tapdel-")
    previous = os.environ.get("ASAN_OPTIONS")
    os.environ["ASAN_OPTIONS"] = ":".join(
        o for o in (previous, f"log_path={where / 'asan'}", "detect_leaks=0") if o)
    try:
        boot(flags=["-set", "cpu core=auto"])
        steps = []
        for command in ("TAP W 0:100 tap-dyn.txt", "TAPLIST"):
            steps.append(_says(command))
        M.call(server.resume, seconds=TAP_RUN_S)
        M.call(server.stop)
        steps.append(_says("TAPDEL *"))
        M.call(server.resume, seconds=TAP_RUN_S)
        stopped = M.call(server.stop)
        listing = _says("TAPLIST")
    finally:
        if previous is None:
            os.environ.pop("ASAN_OPTIONS", None)
        else:
            os.environ["ASAN_OPTIONS"] = previous
    reports = sorted(p.name for p in where.glob("asan*"))
    alive = ok(stopped) and ok(M.call(server.status))
    installed = "INSTALLED=1" in steps[1][1]
    removed = listing[0] and "INSTALLED=1" not in listing[1]
    M.judge(TAPDEL_CELL, all(took for took, _ in steps) and installed and removed and alive
            and not reports, f"installed {installed}, removed {removed}, alive {alive}, "
            f"sanitizer reports {reports}, last listing {listing[1][-60:]!r}")
    (GUEST / "tap-dyn.txt").unlink(missing_ok=True)
    close_whatever()


def _dynamic_core() -> None:
    binary = ENV.get("DOSBOX_X_BINARY", "")
    if not binary or not Path(binary).is_file():
        M.block_rest("DOSBOX_X_BINARY does not name the emulator this cell runs directly")
        return
    where = M.tmp("-dynamic-")
    exits: dict[str, int | str] = {}
    fell_back = False
    for name, body in DYNAMIC_PROGRAMS.items():
        (where / name).write_bytes(body)
        conf = where / f"{name}.conf"
        conf.write_text(f'[cpu]\ncore=dynamic_rec\ncputype=pentium\n[autoexec]\nmount c "{where}"\n'
                        f"c:\n{name}\nexit\n", encoding="ascii")
        run_env: dict[str, Any] = {**os.environ, "SDL_VIDEODRIVER": "dummy"}
        try:
            done = subprocess.run([binary, "-conf", str(conf), "-nogui", "-exit",
                                   "-set", "sdl waitonerror=false"], env=run_env, cwd=where,
                                  capture_output=True, timeout=DYNAMIC_RUN_S, check=False)
        except subprocess.TimeoutExpired:
            exits[name] = "timeout"
            continue
        exits[name] = done.returncode
        # A build with no dynamic core runs the normal one and exits 0 without trying the guard.
        fell_back = fell_back or b"switching back to normal" in done.stdout + done.stderr
    M.judge(DYNAMIC_CELL, set(exits.values()) == {0} and not fell_back,
            f"exit codes {exits}; fell back to the normal core: {fell_back}")


@M.section("AA", "the debugger commands added to DOSBox-X and the dynamic core guard, on the "
           "package's guests", AA_CELLS, alone=True)
def section_aa() -> None:
    _scrub()
    _dynamic_core()
    _channel_latency()
    _bpif_edge()
    _tapdel_auto()
    _dostrace_restart()
    _cd_volume()
    folds = not _case_sensitive(GUEST)
    if folds:
        for label in (FILE_CELLS[0], FILE_CELLS[1], FILE_CELLS[3]):
            M.block(label, f"{GUEST} folds case: run with DOSBOX_X_LIVE_PRIVATE on a "
                    "case-sensitive volume")
    else:
        _dpmi_files()
    _before_page_tables(folds)
    _scrub()

