"""Sections X and Y of the live matrix, on the package's DOS guest (`tests/guest/dosio.asm`): its
DOS calls traced with their results, its ports, its interrupt controller and a frozen byte (X),
and the file it leaves, the emulator's own log categories and a session with no trace (Y). Each
answer is the guest's own: the files it opens, the error DOS gives the missing one, the counter
only its timer handler moves, the bytes it writes."""
from __future__ import annotations

import shutil
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

DOSIO_FILES = ("dosio.com", "dosio.conf", "in.txt")
#: `dosio.asm`'s counter, at this offset of the segment DOS loads it at (its listing).
TICKS_OFFSET = 0x18F
OUT = "OUT.TXT"


def dosio_dir() -> Path:
    """A scratch copy of the guest's directory: it writes OUT.TXT where it runs."""
    where = Path(M.fresh("-dosio"))
    where.mkdir(parents=True)
    for name in DOSIO_FILES:
        shutil.copy2(GUEST / name, where / name)
    return where


def boot_dosio(where: Path, tail: str = "W", **kw: Any) -> dict[str, Any]:
    started = boot(conf=where / "dosio.conf", cwd=where,
                   program=f"DOSIO.COM {tail}".strip(), **kw)
    advanced(M.call(server.run_for, milliseconds=3000), "run_for(milliseconds=3000)")
    return started


def _calls(pattern: str) -> list[dict[str, Any]]:
    return M.call(server.log, channel="dos", pattern=pattern, limit=400).get("calls") or []


def _ticks(psp: str) -> int:
    got = M.call(server.read_memory, ref=f"{psp[2:]}:{TICKS_OFFSET:04X}", length=1)
    return int(str(got.get("hex")), 16) if ok(got) else -1


X_CELLS = cells(
    ("X log dos lists the guest's opens with their results, the missing file with error 2",
     "log docstring: the DOS channel; known: dosio.asm opens IN.TXT, then MISSING.TXT"),
    ("X log dos tells the shell's EXEC from the program's own calls by caller and PSP",
     "REFERENCE.md, The log: `caller`, `psp`; measured: the shell runs in the BIOS segment"),
    ("X log_wait dos answers at once for a traced call and times out on one never made",
     "log_wait docstring"),
    ("X port reads the master PIC's mask at 21h, bit for bit what pic lists masked",
     "port and pic docstrings; known: port 21h reads the 8259's interrupt mask register"),
    ("X port writes a DAC entry, and palette then shows it",
     "port docstring; palette docstring: the DAC's six-bit entries"),
    ("X port refuses an access no device answers, by port, size and side",
     "port docstring: Refused; measured: 2E8h has no device, 3DAh is an 8-bit read only"),
    ("X pic mask 0 stops the counter the timer moves, and unmask resumes it",
     "pic docstring; known: dosio.asm's on_tick is the only writer of ticks"),
    ("X a freeze holds the counter while the guest runs; cleared, it moves again",
     "watch_add docstring: freeze; known: dosio.asm's ticks"),
    ("X a breakpoint declared before a freeze stops the guest right after a write the freeze "
     "undoes", "watch_add docstring: freeze; known: tap.asm writes pair at w_pair, then r_poll"),
)
#: `tap.asm`'s word `pair`, written at `w_pair` once a tick, and the instruction after it.
TAP_PAIR, TAP_R_POLL = "0814:013C", "0814:0129"


@M.section("X", "the DOS calls, the ports, the interrupt controller and a frozen byte, on the "
           "package's DOS guest", X_CELLS)
def section_x() -> None:
    boot_dosio(dosio_dir(), dos_calls=True)
    opened = _calls(r"open ")
    mine = [c for c in opened if c.get("file") in ("IN.TXT", "MISSING.TXT")]
    missing = next((c for c in mine if c.get("file") == "MISSING.TXT"), {})
    found = next((c for c in mine if c.get("file") == "IN.TXT"), {})
    M.judge(X_CELLS[0].label, len(mine) == 2 and found.get("returned") is True
            and "error" not in found and (found.get("out") or {}).get("cf") == 0
            and missing.get("error") == {"code": 2, "name": "file not found"},
            str(mine)[:140])
    psp = str(found.get("psp"))
    shell = [c for c in _calls("exec") if str(c.get("file", "")).upper().endswith("DOSIO.COM")]
    M.judge(X_CELLS[1].label, bool(shell) and shell[0].get("psp") != psp
            and str(shell[0].get("caller")).startswith("F000:")
            and str(found.get("caller")).startswith(psp[2:] + ":"), str(shell[:1])[:140])
    at_once = M.call(server.log_wait, channel="dos", pattern="MISSING", seconds=5)
    M.call(server.breakpoint_at, ref="0000:0001")
    M.call(server.resume)
    never = M.call(server.log_wait, channel="dos", pattern="MATRIX_NEVER_CALLED", seconds=2)
    M.call(server.stop)
    M.call(server.declaration_clear, kind="breakpoint", all=True)
    M.judge(X_CELLS[2].label, ok(at_once) and at_once.get("already") is True
            and (at_once.get("call") or {}).get("file") == "MISSING.TXT"
            and ok(never) and never.get("verdict") == "TIMEOUT", f"{said(at_once)} / {said(never)}")
    imr = M.call(server.port, method="read", port=0x21)
    listed = M.call(server.pic, method="read")
    mask_bits = sum(1 << int(r["irq"]) for r in listed.get("irqs") or []
                    if r.get("masked") and int(r["irq"]) < 8)
    M.judge(X_CELLS[3].label, ok(imr) and ok(listed)
            and int(str(imr.get("value")), 16) == mask_bits,
            f"{said(imr)} / masked {mask_bits:#04x}")
    wrote = [M.call(server.port, method="write", port=0x3C8, value=5)]
    wrote += [M.call(server.port, method="write", port=0x3C9, value=v) for v in (63, 21, 0)]
    shown = M.call(server.palette, first=5, count=1)
    M.judge(X_CELLS[4].label, all(ok(w) for w in wrote) and ok(shown)
            and (shown.get("rgb") or [None])[0] == "3f1500", said(shown))
    no_device = M.call(server.port, method="read", port=0x2E8)
    wide = M.call(server.port, method="read", port=0x3DA, bits=16)
    written = M.call(server.port, method="write", port=0x3DA, value=0)
    M.judge(X_CELLS[5].label, all(refused(r, "no_channel") and "no device" in str(r.get("message"))
                                  for r in (no_device, wide, written)),
            f"{said(no_device, 60)} / {said(wide, 40)} / {said(written, 40)}")
    t0 = _ticks(psp)
    masked = M.call(server.pic, method="mask", irq=0)
    advanced(M.call(server.run_for, milliseconds=1000), "run_for(milliseconds=1000)")
    t1 = _ticks(psp)
    unmasked = M.call(server.pic, method="unmask", irq=0)
    advanced(M.call(server.run_for, milliseconds=1000), "run_for(milliseconds=1000)")
    t2 = _ticks(psp)
    M.judge(X_CELLS[6].label, ok(masked) and ok(unmasked) and t0 == t1 >= 0 and t2 != t1,
            f"ticks {t0:#x} masked -> {t1:#x}, unmasked -> {t2:#x}")
    ref = f"{psp[2:]}:{TICKS_OFFSET:04X}"
    frozen = M.call(server.watch_add, ref=ref, mode="freeze", length=1)
    held_at = _ticks(psp)
    stop = advanced(M.call(server.run_for, milliseconds=1000), "run_for over the freeze")
    surveyed: dict[str, Any] = next(
        (w for w in stop.get("watches") or [] if w.get("ref") == ref), {})
    still = _ticks(psp)
    cleared = M.call(server.declaration_clear, kind="watch", ref=ref)
    advanced(M.call(server.run_for, milliseconds=1000), "run_for(milliseconds=1000)")
    moved = _ticks(psp)
    M.judge(X_CELLS[7].label, ok(frozen) and frozen.get("state") == "armed"
            and surveyed.get("state") == "holding" and held_at == still and ok(cleared)
            and bool(cleared.get("disarmed")) and moved != still,
            f"{said(frozen, 50)}; {held_at:#x} -> {still:#x} -> {moved:#x}; {surveyed}"[:200])
    close_whatever()
    boot(conf=GUEST / "tap.conf", break_on_int3=True)
    advanced(M.call(server.resume, seconds=30), "resume(seconds=30)", STOPPED)
    M.call(server.breakpoint_at, ref=TAP_R_POLL)
    pinned = M.call(server.watch_add, ref=TAP_PAIR, mode="freeze", length=2)
    stop = M.call(server.resume, seconds=10)
    M.judge(X_CELLS[8].label, ok(pinned) and ok(stop) and stop.get("pc") == "0814:00000129",
            said(stop))
    close_whatever()


Y_CELLS = cells(
    ("Y a session started without dos_calls answers no_channel naming dos_calls",
     "log docstring: the DOS channel needs `dos_calls`"),
    ("Y guest_file: the file the guest wrote is written with its bytes, while it runs and at "
     "close", "guest_file and close docstrings; known: dosio.asm writes SCRY"),
    ("Y guest_file: a file left from before and not written again is unchanged, INVALID",
     "guest_file docstring: `unchanged`"),
    ("Y guest_file: a file never written is absent, INVALID", "guest_file docstring: `absent`"),
    ("Y guest_file: a file created and left empty is empty, INVALID",
     "guest_file docstring: `empty`; known: dosio.asm's `E`"),
    ("Y log_categories puts the emulator's own file lines in the emulator channel",
     "start docstring: `log_categories`; measured: `files` logs each open by name"),
)


@M.section("Y", "the file the guest leaves and the emulator's log categories, on the package's "
           "DOS guest", Y_CELLS)
def section_y() -> None:
    where = dosio_dir()
    out, never = where / OUT, where / "NEVER.TXT"
    boot_dosio(where, "W", guest_files=[str(out), str(never)],
               log_categories={"files": "normal"})
    untraced = M.call(server.log, channel="dos", pattern=".")
    M.judge(Y_CELLS[0].label, refused(untraced, "no_channel")
            and "dos_calls" in str(untraced.get("message")), said(untraced))
    M.call(server.breakpoint_at, ref="0000:0001")
    M.call(server.resume)
    running = M.call(server.guest_file, path=str(out))
    files = M.call(server.log, channel="emulator", pattern=r"file open command 0 file IN\.TXT")
    absent = M.call(server.guest_file, path=str(never))
    closed = M.call(server.close)
    at_close = {g.get("path"): g for g in closed.get("guest_files") or []}
    M.judge(Y_CELLS[1].label, ok(running) and running.get("state") == "written"
            and running.get("bytes") == 4 and out.read_bytes() == b"SCRY"
            and (running.get("session") or {}).get("running") is True
            and at_close.get(str(out), {}).get("state") == "written", said(running))
    M.judge(Y_CELLS[3].label, refused(absent, "readback_refused")
            and absent.get("state") == "absent"
            and at_close.get(str(never), {}).get("state") == "absent", said(absent))
    M.judge(Y_CELLS[5].label, ok(files) and int(files.get("lines_total") or 0) >= 1, said(files))
    boot_dosio(where, "", guest_files=[str(out)])
    left = M.call(server.guest_file, path=str(out))
    close_whatever()
    M.judge(Y_CELLS[2].label, refused(left, "readback_refused")
            and left.get("state") == "unchanged", said(left))
    out.unlink()
    boot_dosio(where, "E", guest_files=[str(out)])
    empty = M.call(server.guest_file, path=str(out))
    close_whatever()
    M.judge(Y_CELLS[4].label, refused(empty, "readback_refused")
            and empty.get("state") == "empty" and empty.get("bytes") == 0, said(empty))
